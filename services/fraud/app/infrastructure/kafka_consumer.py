import json
import logging
import threading
from decimal import Decimal

from confluent_kafka import Consumer, KafkaError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application.events import EventEnvelope
from ..domain.rules import RuleEngine
from .database import SessionLocal
from .models import FraudAssessmentModel, ProcessedEventModel
from .outbox import add_outbox_event

logger = logging.getLogger(__name__)


class FraudConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str, topic_prefix: str):
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self.topic = f"{topic_prefix}.transfer.completed"
        self.group_id = group_id
        self.rule_engine = RuleEngine()

    def process_event(self, db: Session, event_data: dict) -> None:
        event_id = event_data.get("event_id")
        event_type = event_data.get("event_type")

        if event_type != "transfer.completed":
            return

        try:
            processed_event = ProcessedEventModel(
                event_id=event_id, consumer_group=self.group_id
            )
            db.add(processed_event)
            db.flush()
        except IntegrityError:
            db.rollback()
            logger.info(
                f"Event {event_id} already processed by group {self.group_id}. Skipping."
            )
            return

        payload = event_data.get("payload", {})
        transaction_id = payload.get("source_transaction_id")
        amount = Decimal(str(payload.get("amount", 0)))

        assessment = self.rule_engine.evaluate(str(event_id), str(transaction_id), amount)

        db_assessment = FraudAssessmentModel(
            assessment_id=assessment.assessment_id,
            event_id=assessment.event_id,
            transaction_id=assessment.transaction_id,
            risk_score=assessment.risk_score,
            risk_level=assessment.risk_level.value,
            reasons=assessment.reasons,
            created_at=assessment.created_at,
        )
        db.add(db_assessment)

        risk_event = EventEnvelope(
            event_type="risk.assessed",
            aggregate_type="risk_assessment",
            aggregate_id=assessment.assessment_id,
            payload={
                "transaction_id": assessment.transaction_id,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level.value,
                "reasons": assessment.reasons,
            },
        )
        add_outbox_event(db, risk_event)
        db.commit()
        logger.info(
            f"Processed event {event_id}, assessment {assessment.assessment_id}"
        )

    def consume_loop(self):
        self.consumer.subscribe([self.topic])
        logger.info(f"Subscribed to {self.topic}")

        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(msg.error())
                    break

            try:
                event_data = json.loads(msg.value().decode("utf-8"))
                with SessionLocal() as db:
                    self.process_event(db, event_data)
                self.consumer.commit(msg)
            except Exception as e:
                logger.error(f"Error processing message: {e}")


class FraudConsumerThread(threading.Thread):
    def __init__(self, bootstrap_servers: str, group_id: str, topic_prefix: str):
        super().__init__(daemon=True)
        self.consumer = FraudConsumer(bootstrap_servers, group_id, topic_prefix)

    def run(self):
        self.consumer.consume_loop()
