"""Fraud Kafka consumer.

Consumes transfer.completed events from the shared pybank.events topic (the
same topic Banking publishes to), evaluates the deterministic risk rules, and
appends a risk.assessed event to the fraud outbox in the same transaction.

Processing is idempotent: an event_id is recorded once per consumer group, so
re-delivery never creates a second assessment. Kafka offsets are committed only
after the database transaction succeeds, which keeps the flow at-least-once
without duplicating assessments.
"""

from __future__ import annotations

import json
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, Message
from services.common.observability import (
    bind_correlation_id,
    clear_correlation_id,
    get_correlation_id,
)
from services.common.tracing import (
    CORRELATION_HEADER,
    current_traceparent,
    extract_header,
    get_tracer,
)
from services.fraud.ml.model import FraudModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application.events import EventEnvelope
from ..domain.models import RiskAssessment
from ..domain.risk import CombinedRiskEngine
from ..domain.rules import RuleEngine
from .database import SessionLocal
from .metrics import (
    record_assessment_created,
    record_assessment_failure,
    record_duplicate_event,
    record_event_consumed,
    record_ml_high_risk,
    record_ml_prediction,
)
from .models import FraudAssessmentModel, ProcessedEventModel
from .outbox import add_outbox_event

logger = structlog.get_logger(__name__)

TRANSFER_COMPLETED = "transfer.completed"
RISK_ASSESSED = "risk.assessed"


class FraudConsumer:
    """Turns transfer.completed events into fraud assessments."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
        model: FraudModel | None = None,
        rule_weight: float = 0.6,
        ml_weight: float = 0.4,
    ) -> None:
        self._topic = topic
        self._group_id = group_id
        # Deterministic rules remain the foundation; when a model artifact is
        # provided the combined engine adds the ML probability signal.
        self._rules = RuleEngine()
        self._combined: CombinedRiskEngine | None = (
            CombinedRiskEngine(model, rule_weight=rule_weight, ml_weight=ml_weight)
            if model is not None
            else None
        )
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )

    def start(self) -> None:
        self._consumer.subscribe([self._topic])
        logger.info(
            "fraud_consumer_subscribed",
            topic=self._topic,
            consumer_group=self._group_id,
        )

    def close(self) -> None:
        self._consumer.close()

    def poll_once(self, timeout: float = 1.0) -> bool:
        """Poll one record and process it. Returns True when work was done."""
        message = self._consumer.poll(timeout)
        if message is None:
            return False

        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                return False
            logger.error("fraud_kafka_error", error=str(error))
            return False

        raw_value = message.value()
        if raw_value is None:
            logger.warning("fraud_kafka_empty_value")
            self._commit(message)
            return False

        try:
            event: dict[str, Any] = json.loads(raw_value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            logger.error("fraud_kafka_malformed_event", error=str(error))
            self._commit(message)
            return False

        correlation_id = extract_header(message.headers(), CORRELATION_HEADER)
        bind_correlation_id(correlation_id)
        try:
            processed = self.process_event(event)
        finally:
            clear_correlation_id()

        self._commit(message)
        return processed

    def _commit(self, message: Message) -> None:
        try:
            self._consumer.commit(message=message, asynchronous=False)
        except Exception as error:
            logger.error("fraud_kafka_commit_failed", error=str(error))

    def process_event(self, event: dict[str, Any]) -> bool:
        """Assess one event. Returns True when a new assessment was stored."""
        if str(event.get("event_type", "")) != TRANSFER_COMPLETED:
            return False

        event_id = str(event.get("event_id", ""))
        if not event_id:
            logger.warning("fraud_event_missing_id")
            return False

        record_event_consumed()

        with SessionLocal() as db:
            if self._already_processed(db, event_id):
                record_duplicate_event()
                logger.info("fraud_duplicate_event", event_id=event_id)
                return False

            tracer = get_tracer(__name__)
            with tracer.start_as_current_span("fraud.risk_evaluation") as span:
                span.set_attribute("pybank.event_id", event_id)
                outcome = self._assess(db, event, event_id)
                span.set_attribute("pybank.outcome", outcome)

        if outcome == "created":
            return True
        if outcome == "duplicate":
            record_duplicate_event()
            return False
        record_assessment_failure()
        return False

    def _already_processed(self, db: Session, event_id: str) -> bool:
        return (
            db.get(
                ProcessedEventModel,
                {"event_id": event_id, "consumer_group": self._group_id},
            )
            is not None
        )

    def _assess(self, db: Session, event: dict[str, Any], event_id: str) -> str:
        payload = event.get("payload") or {}
        transaction_id = payload.get("source_transaction_id") or payload.get(
            "transaction_id"
        )
        if transaction_id is None:
            logger.error("fraud_event_missing_transaction_id", event_id=event_id)
            return "failed"

        try:
            amount = Decimal(str(payload.get("amount", "0")))
        except (InvalidOperation, TypeError, ValueError):
            logger.error("fraud_event_invalid_amount", event_id=event_id)
            return "failed"

        correlation_id = get_correlation_id()
        traceparent = current_traceparent()

        try:
            assessment = self._evaluate(event_id, str(transaction_id), amount, payload)
        except Exception as error:
            # Fail the assessment clearly instead of pretending ML succeeded.
            # Banking has already committed; Kafka offset stays uncommitted
            # semantics intact because the event is simply not recorded here.
            record_ml_prediction("failure")
            logger.error(
                "fraud_ml_prediction_failed",
                event_id=event_id,
                error=str(error),
            )
            return "failed"
        record_ml_prediction("success")
        if "ML_HIGH_RISK" in assessment.reasons:
            record_ml_high_risk()

        db.add(ProcessedEventModel(event_id=event_id, consumer_group=self._group_id))
        db.add(
            FraudAssessmentModel(
                assessment_id=assessment.assessment_id,
                event_id=assessment.event_id,
                transaction_id=assessment.transaction_id,
                risk_score=assessment.risk_score,
                risk_level=assessment.risk_level.value,
                reasons=assessment.reasons,
                correlation_id=correlation_id,
                rule_score=assessment.rule_score,
                ml_probability=assessment.ml_probability,
                combined_score=assessment.risk_score,
                model_version=assessment.model_version,
            )
        )
        add_outbox_event(
            db,
            EventEnvelope(
                event_type=RISK_ASSESSED,
                aggregate_type="risk_assessment",
                aggregate_id=assessment.assessment_id,
                payload={
                    "assessment_id": assessment.assessment_id,
                    "event_id": event_id,
                    "transaction_id": assessment.transaction_id,
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level.value,
                    "reasons": assessment.reasons,
                    "rule_score": assessment.rule_score,
                    "ml_probability": assessment.ml_probability,
                    "model_version": assessment.model_version,
                },
            ),
            correlation_id=correlation_id,
            traceparent=traceparent,
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info("fraud_duplicate_event", event_id=event_id)
            return "duplicate"

        record_assessment_created(assessment.risk_level.value)
        logger.info(
            "fraud_assessment_created",
            event_id=event_id,
            transaction_id=assessment.transaction_id,
            risk_level=assessment.risk_level.value,
            risk_score=assessment.risk_score,
            ml_probability=assessment.ml_probability,
            combined_score=assessment.risk_score,
            model_version=assessment.model_version,
        )
        return "created"

    def _evaluate(
        self,
        event_id: str,
        transaction_id: str,
        amount: Decimal,
        payload: dict[str, Any],
    ) -> RiskAssessment:
        if self._combined is not None:
            return self._combined.evaluate(event_id, transaction_id, amount, payload)
        return self._rules.evaluate(event_id, transaction_id, amount)


class FraudConsumerThread(threading.Thread):
    """Background thread running the fraud consumer poll loop."""

    def __init__(self, consumer: FraudConsumer) -> None:
        super().__init__(name="fraud-consumer", daemon=True)
        self._consumer = consumer
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self._consumer.start()
        while not self._stop.is_set():
            try:
                self._consumer.poll_once(1.0)
            except Exception as error:
                logger.error("fraud_consumer_poll_failed", error=str(error))
                time.sleep(2)
        self._consumer.close()
