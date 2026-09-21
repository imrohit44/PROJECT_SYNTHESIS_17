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
from datetime import UTC, datetime
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
from services.fraud.graph import GraphRiskAnalyzer
from services.fraud.ml.model import FraudModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application.events import EventEnvelope
from ..domain.models import RiskAssessment
from ..domain.risk import CombinedRiskEngine, map_level
from ..domain.rules import RuleEngine
from .database import SessionLocal
from .metrics import (
    record_assessment_created,
    record_assessment_failure,
    record_duplicate_event,
    record_event_consumed,
    record_graph_failure,
    record_graph_operation,
    record_graph_projection,
    record_graph_signal,
    record_ml_high_risk,
    record_ml_prediction,
)
from .models import FraudAssessmentModel, ProcessedEventModel
from .outbox import add_outbox_event

logger = structlog.get_logger(__name__)

TRANSFER_COMPLETED = "transfer.completed"
RISK_ASSESSED = "risk.assessed"


def event_occurred_ts(event: dict[str, Any]) -> float:
    """Epoch seconds for the event, defaulting to now when unparsable."""
    raw = event.get("occurred_at")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return datetime.now(UTC).timestamp()


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
        graph: GraphRiskAnalyzer | None = None,
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
        # Phase 13: optional graph analyzer (Neo4j advisory dependency).
        self._graph = graph
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

        # Phase 13: graph projection + analysis. Neo4j is advisory — on any
        # failure the graph contribution becomes neutral (0.0) and the
        # assessment still completes on the rule + ML baseline.
        combined_score = assessment.risk_score
        graph_score: float | None = None
        graph_adjustment: float | None = None
        graph_signals: list[str] = []
        graph_version: str | None = None
        graph_available = False
        if self._graph is not None:
            source_account_id = str(payload.get("source_account_id", ""))
            destination_account_id = str(payload.get("destination_account_id", ""))
            graph_version = self._graph.graph_version
            try:
                self._graph.project(
                    source_account_id=source_account_id,
                    destination_account_id=destination_account_id,
                    source_customer_id=str(payload.get("source_customer_id", "")),
                    destination_customer_id=str(
                        payload.get("destination_customer_id", "")
                    ),
                    transaction_id=str(transaction_id),
                    amount=str(payload.get("amount", "0")),
                    created_ts=event_occurred_ts(event),
                )
                record_graph_projection("success")
            except Exception as error:
                record_graph_projection("failure")
                record_graph_failure("project")
                logger.warning(
                    "fraud_graph_projection_failed",
                    event_id=event_id,
                    error=str(error),
                )
                graph_score, graph_adjustment = 0.0, 0.0
            else:
                try:
                    analysis = self._graph.analyze_transfer(
                        source_account_id, destination_account_id
                    )
                    graph_available = True
                    graph_score = analysis.graph_score
                    graph_signals = analysis.graph_signals
                    graph_adjustment = self._graph.adjustment_for(graph_score)
                    record_graph_operation("analyze", "success")
                    for signal in graph_signals:
                        record_graph_signal(signal)
                except Exception as error:
                    # Graceful degradation: neutral graph contribution.
                    graph_score, graph_adjustment = 0.0, 0.0
                    record_graph_failure("analyze")
                    record_graph_operation("analyze", "failure")
                    logger.warning(
                        "fraud_graph_unavailable",
                        event_id=event_id,
                        error=str(error),
                    )

        if graph_adjustment is not None:
            final_score = min(1.0, combined_score + graph_adjustment)
            risk_level = map_level(final_score)
            reasons = assessment.reasons + [
                signal for signal in graph_signals if signal not in assessment.reasons
            ]
        else:
            final_score = combined_score
            risk_level = assessment.risk_level
            reasons = assessment.reasons

        db.add(ProcessedEventModel(event_id=event_id, consumer_group=self._group_id))
        db.add(
            FraudAssessmentModel(
                assessment_id=assessment.assessment_id,
                event_id=assessment.event_id,
                transaction_id=assessment.transaction_id,
                # risk_score stays the Phase 12 rule + ML baseline
                # (combined_score); final_score adds the graph contribution.
                risk_score=combined_score,
                risk_level=risk_level.value,
                reasons=reasons,
                correlation_id=correlation_id,
                rule_score=assessment.rule_score,
                ml_probability=assessment.ml_probability,
                combined_score=combined_score,
                model_version=assessment.model_version,
                graph_score=graph_score,
                graph_adjustment=graph_adjustment,
                final_score=final_score,
                graph_signals=graph_signals,
                graph_version=graph_version,
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
                    "risk_score": combined_score,
                    "risk_level": risk_level.value,
                    "reasons": reasons,
                    "rule_score": assessment.rule_score,
                    "ml_probability": assessment.ml_probability,
                    "model_version": assessment.model_version,
                    "graph_score": graph_score,
                    "graph_adjustment": graph_adjustment,
                    "final_score": final_score,
                    "graph_signals": graph_signals,
                    "graph_version": graph_version,
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

        record_assessment_created(risk_level.value)
        logger.info(
            "fraud_assessment_created",
            event_id=event_id,
            transaction_id=assessment.transaction_id,
            risk_level=risk_level.value,
            risk_score=combined_score,
            ml_probability=assessment.ml_probability,
            combined_score=combined_score,
            model_version=assessment.model_version,
            graph_score=graph_score,
            graph_adjustment=graph_adjustment,
            final_score=final_score,
            graph_version=graph_version,
            graph_available=graph_available,
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
