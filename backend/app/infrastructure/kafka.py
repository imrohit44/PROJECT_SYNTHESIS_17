from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime

from confluent_kafka import Consumer, KafkaError, KafkaException, Message, Producer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.outbox import OutboxRepository, event_message
from backend.app.infrastructure.persistence.models import ProcessedEventModel

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})
        self._topic = topic

    def publish(self, key: str, value: dict) -> None:
        error_holder: list[KafkaError] = []

        def on_delivery(error: KafkaError | None, _: Message) -> None:
            if error is not None:
                error_holder.append(error)

        self._producer.produce(
            self._topic,
            key=key,
            value=json.dumps(value).encode("utf-8"),
            callback=on_delivery,
        )
        self._producer.flush(10)
        if error_holder:
            raise KafkaException(error_holder[0])


class OutboxPublisher:
    def __init__(
        self, repository: OutboxRepository, producer: KafkaEventProducer
    ) -> None:
        self._repository = repository
        self._producer = producer

    def publish_once(self) -> int:
        published = 0
        for event in self._repository.pending():
            try:
                message = event_message(event)
                self._producer.publish(event.aggregate_id, message)
            except Exception as error:
                self._repository.record_failure(event.id, error)
                logger.warning("outbox publish failed", extra={"event_id": event.id})
                continue
            self._repository.mark_published(event.id)
            published += 1
            logger.info("outbox event published", extra={"event_id": event.id})
        return published


class OutboxPublisherThread:
    def __init__(
        self, publisher: OutboxPublisher, interval_seconds: float = 2.0
    ) -> None:
        self._publisher = publisher
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

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

    def close(self) -> None:
        self._consumer.close()

    def poll_once(self, timeout: float = 1.0) -> bool:
        message = self._consumer.poll(timeout)
        if message is None:
            return False
        if message.error():
            raise KafkaException(message.error())
        value = message.value()
        if value is None:
            return False
        event = json.loads(value.decode("utf-8"))
        self.process_event(event)
        self._consumer.commit(message=message)
        return True

    def process_event(self, event: dict) -> bool:
        event_id = str(event["event_id"])
        with self._session_factory.begin() as session:
            if session.get(
                ProcessedEventModel,
                {"event_id": event_id, "consumer_group": self._group_id},
            ):
                return False
            session.add(
                ProcessedEventModel(
                    event_id=event_id,
                    consumer_group=self._group_id,
                    event_type=str(event["event_type"]),
                    processed_at=datetime.now(UTC),
                )
            )
            try:
                session.flush()
            except IntegrityError:
                return False
        logger.info("audit event processed", extra={"event_id": event_id})
        return True


class AuditConsumerThread:
    def __init__(self, consumer: AuditConsumer) -> None:
        self._consumer = consumer
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

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
            except Exception:
                logger.warning("audit consumer poll failed")
                time.sleep(2)
