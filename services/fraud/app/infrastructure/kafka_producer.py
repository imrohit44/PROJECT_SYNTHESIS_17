import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from confluent_kafka import Producer

from .database import SessionLocal
from .outbox import OutboxRepository

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    def __init__(self, bootstrap_servers: str, topic_prefix: str = "pybank"):
        self.producer = Producer({"bootstrap.servers": bootstrap_servers})
        self.topic_prefix = topic_prefix

    def publish(self, event_type: str, event_dict: dict[str, Any]) -> None:
        topic = f"{self.topic_prefix}.{event_type}"
        self.producer.produce(
            topic,
            key=event_dict["aggregate_id"].encode("utf-8"),
            value=json.dumps(event_dict).encode("utf-8"),
        )
        self.producer.poll(0)

    def flush(self) -> None:
        self.producer.flush()


class OutboxPublisher:
    def __init__(self, repository: OutboxRepository, producer: KafkaEventProducer):
        self.repository = repository
        self.producer = producer

    def publish_once(self) -> int:
        events = self.repository.get_pending_events(limit=50)
        published_count = 0
        for event in events:
            try:
                event_dict = {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": event.aggregate_id,
                    "payload": event.payload,
                    "schema_version": int(event.schema_version),
                    "occurred_at": event.occurred_at.isoformat(),
                }
                self.producer.publish(event.event_type, event_dict)
                self.producer.flush()
                self.repository.mark_published(event.event_id, datetime.now(UTC))
                published_count += 1
            except Exception as e:
                logger.error(f"Failed to publish outbox event {event.event_id}: {e}")
                self.repository.mark_failed(event.event_id, str(e))
        return published_count


class OutboxPublisherThread(threading.Thread):
    def __init__(self, bootstrap_servers: str, topic_prefix: str):
        super().__init__(daemon=True)
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix

    def run(self):
        producer = KafkaEventProducer(self.bootstrap_servers, self.topic_prefix)
        while True:
            try:
                with SessionLocal() as db:
                    repo = OutboxRepository(db)
                    publisher = OutboxPublisher(repo, producer)
                    publisher.publish_once()
            except Exception as e:
                logger.error(f"Error in outbox publisher thread: {e}")
            time.sleep(2.0)
