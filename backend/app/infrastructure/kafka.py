"""Banking Kafka integration: event producer, outbox publisher, audit consumer.

Kafka is asynchronous transport only. PostgreSQL remains authoritative for
balances, accounts, transactions, transfers and the outbox.

Records carry correlation metadata as separate UTF-8 headers:

correlation_id: Application identifier for the request that produced the event.
traceparent: W3C trace context so the consumer can continue the producer trace.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException, Message, Producer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.metrics import (
    record_outbox_backlog,
    record_outbox_publish_failure,
)
from backend.app.infrastructure.outbox import OutboxRepository, event_message
from backend.app.infrastructure.persistence.models import ProcessedEventModel
from services.common.observability import bind_correlation_id, clear_correlation_id
from services.common.tracing import (
    CORRELATION_HEADER,
    TRACEPARENT_HEADER,
    extract_header,
    get_tracer,
)

logger = structlog.get_logger(__name__)


def event_headers(event: Any) -> list[tuple[str, bytes]]:
    """Build Kafka headers from a stored outbox row.

    correlation_id and traceparent are always separate UTF-8 byte headers.
    """
    headers: list[tuple[str, bytes]] = []
    correlation_id = getattr(event, "correlation_id", None)
    traceparent = getattr(event, "traceparent", None)
    if correlation_id:
        headers.append((CORRELATION_HEADER, str(correlation_id).encode("utf-8")))
    if traceparent:
        headers.append((TRACEPARENT_HEADER, str(traceparent).encode("utf-8")))
    return headers


class KafkaEventProducer:
    """Publishes JSON events with optional headers and verifies delivery."""

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._topic = topic
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    @property
    def topic(self) -> str:
        return self._topic

    def publish(
        self,
        key: str,
        value: dict[str, Any],
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
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
    """Publishes pending outbox events and records the outcome."""

    def __init__(
        self, repository: OutboxRepository, producer: KafkaEventProducer
    ) -> None:
        self._repository = repository
        self._producer = producer

    def publish_once(self) -> int:
        record_outbox_backlog(self._repository.count_pending())
        published = 0
        tracer = get_tracer(__name__)
        for event in self._repository.pending():
            try:
                with tracer.start_as_current_span("kafka.publish") as span:
                    span.set_attribute(
                        "messaging.destination.name", self._producer.topic
                    )
                    span.set_attribute("pybank.event_type", event.event_type)
                    self._producer.publish(
                        event.aggregate_id,
                        event_message(event),
                        event_headers(event),
                    )
            except Exception as error:
                record_outbox_publish_failure()
                self._repository.record_failure(event.id, error)
                logger.warning(
                    "outbox_publish_failed", event_id=event.id, error=str(error)
                )
                continue
            self._repository.mark_published(event.id)
            published += 1
            logger.info(
                "outbox_event_published",
                event_id=event.id,
                event_type=event.event_type,
            )
        record_outbox_backlog(self._repository.count_pending())
        return published


class OutboxPublisherThread:
    """Background thread draining the banking outbox."""

    def __init__(
        self, publisher: OutboxPublisher, interval_seconds: float = 2.0
    ) -> None:
        self._publisher = publisher
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="outbox-publisher", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._publisher.publish_once()
            self._stop.wait(self._interval_seconds)


class AuditConsumer:
    """Records processed event ids so banking processing stays idempotent."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._topic = topic
        self._group_id = group_id
        self._session_factory = session_factory
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
            "audit_consumer_subscribed",
            topic=self._topic,
            consumer_group=self._group_id,
        )

    def close(self) -> None:
        self._consumer.close()

    def poll_once(self, timeout: float = 1.0) -> bool:
        message = self._consumer.poll(timeout)
        if message is None:
            return False

        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                return False
            raise KafkaException(error)

        raw_value = message.value()
        if raw_value is None:
            self._consumer.commit(message=message, asynchronous=False)
            return False

        try:
            event: dict[str, Any] = json.loads(raw_value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.error("audit_event_malformed")
            self._consumer.commit(message=message, asynchronous=False)
            return False

        bind_correlation_id(extract_header(message.headers(), CORRELATION_HEADER))
        try:
            processed = self.process_event(event)
        finally:
            clear_correlation_id()
        self._consumer.commit(message=message, asynchronous=False)
        return processed

    def process_event(self, event: dict[str, Any]) -> bool:
        """Return True when the delivery was new, False when already processed."""
        event_id = str(event.get("event_id", ""))
        if not event_id:
            return False
        with self._session_factory.begin() as session:
            if (
                session.get(
                    ProcessedEventModel,
                    {"event_id": event_id, "consumer_group": self._group_id},
                )
                is not None
            ):
                return False
            session.add(
                ProcessedEventModel(
                    event_id=event_id,
                    consumer_group=self._group_id,
                    event_type=str(event.get("event_type", "unknown")),
                    processed_at=datetime.now(UTC),
                )
            )
            try:
                session.flush()
            except IntegrityError:
                return False
        logger.info("audit_event_processed", event_id=event_id)
        return True


class AuditConsumerThread:
    """Background thread running the audit consumer poll loop."""

    def __init__(self, consumer: AuditConsumer) -> None:
        self._consumer = consumer
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="audit-consumer", daemon=True
        )

    def start(self) -> None:
        self._consumer.start()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._consumer.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._consumer.poll_once(1.0)
            except Exception as error:
                logger.warning("audit_consumer_poll_failed", error=str(error))
                time.sleep(2)
