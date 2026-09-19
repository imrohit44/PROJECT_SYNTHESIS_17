"""Fraud Kafka producer and outbox publisher.

Publishes risk.assessed events to the shared pybank.events topic (the same
topic Banking publishes and consumes), forwarding correlation_id and
traceparent as separate UTF-8 Kafka headers.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Any

import structlog
from confluent_kafka import KafkaError, KafkaException, Message, Producer
from services.common.tracing import CORRELATION_HEADER, TRACEPARENT_HEADER

from .database import SessionLocal
from .metrics import record_outbox_backlog, record_outbox_publish_failure
from .outbox import OutboxRepository

logger = structlog.get_logger(__name__)


class KafkaEventProducer:
    """Thin wrapper around confluent_kafka.Producer with delivery checking."""

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._topic = topic
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    def publish(
        self,
        key: str,
        value: dict[str, Any],
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        from typing import cast

        delivery_errors: list[KafkaError] = []

        def on_delivery(error: KafkaError | None, _message: Message) -> None:
            if error is not None:
                delivery_errors.append(error)

        produce_headers = cast("list[tuple[str, str | bytes | None]] | None", headers)
        self._producer.produce(
            self._topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            headers=produce_headers,
            callback=on_delivery,
        )
        self._producer.flush(10)
        if delivery_errors:
            raise KafkaException(delivery_errors[0])


class OutboxPublisher:
    """Publishes pending fraud outbox events and records the outcome."""

    def __init__(
        self, repository: OutboxRepository, producer: KafkaEventProducer
    ) -> None:
        self._repository = repository
        self._producer = producer

    def publish_once(self, limit: int = 50) -> int:
        events = self._repository.pending(limit)
        record_outbox_backlog(len(events))
        published = 0
        for event in events:
            headers: list[tuple[str, bytes]] = []
            if event.correlation_id:
                headers.append(
                    (CORRELATION_HEADER, event.correlation_id.encode("utf-8"))
                )
            if event.traceparent:
                headers.append((TRACEPARENT_HEADER, event.traceparent.encode("utf-8")))
            body = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "payload": event.payload,
                "schema_version": int(event.schema_version),
                "occurred_at": event.occurred_at.isoformat(),
            }
            try:
                self._producer.publish(event.aggregate_id, body, headers)
            except Exception as error:
                record_outbox_publish_failure()
                self._repository.mark_failed(event.event_id, str(error))
                logger.error(
                    "fraud_outbox_publish_failed",
                    event_id=event.event_id,
                    error=str(error),
                )
                continue
            self._repository.mark_published(event.event_id, datetime.now(UTC))
            published += 1
            logger.info(
                "fraud_outbox_event_published",
                event_id=event.event_id,
                event_type=event.event_type,
            )
        return published


class OutboxPublisherThread(threading.Thread):
    """Background thread that drains the fraud outbox to Kafka."""

    def __init__(
        self, bootstrap_servers: str, topic: str, interval_seconds: float = 2.0
    ) -> None:
        super().__init__(name="fraud-outbox-publisher", daemon=True)
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        producer = KafkaEventProducer(self._bootstrap_servers, self._topic)
        while not self._stop.is_set():
            try:
                with SessionLocal() as db:
                    OutboxPublisher(OutboxRepository(db), producer).publish_once()
            except Exception as error:
                logger.error("fraud_outbox_publisher_failed", error=str(error))
            self._stop.wait(self._interval_seconds)
