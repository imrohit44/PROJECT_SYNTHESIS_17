"""Kafka consumer for real-time WebSocket and WhatsApp notifications.

Consumes pybank.events with consumer group pybank-realtime-consumer.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.persistence.models import (
    AccountModel,
    ProcessedEventModel,
    TransactionModel,
    UserModel,
)
from backend.app.notifications.models import Notification
from backend.app.notifications.service import NotificationService
from services.common.observability import bind_correlation_id
from services.common.tracing import CORRELATION_HEADER, extract_header, get_tracer

logger = structlog.get_logger(__name__)


class RealtimeKafkaConsumer:
    """Consumes Kafka banking and fraud events and dispatches notifications."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        session_factory: sessionmaker[Session],
        notification_service: NotificationService,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._topic = topic
        self._group_id = group_id
        self._session_factory = session_factory
        self._notification_service = notification_service
        self._loop = loop
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def start(self) -> None:
        self._consumer.subscribe([self._topic])
        logger.info(
            "realtime_consumer_subscribed",
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
            logger.error("realtime_event_malformed")
            self._consumer.commit(message=message, asynchronous=False)
            return False

        header_cid = extract_header(message.headers(), CORRELATION_HEADER)
        bind_correlation_id(header_cid)
        processed = self.process_event(event, correlation_id=header_cid)
        self._consumer.commit(message=message, asynchronous=False)
        return processed

    def process_event(
        self, event: dict[str, Any], correlation_id: str | None = None
    ) -> bool:
        """Process one event idempotently and dispatch notifications."""
        event_id = str(event.get("event_id", ""))
        event_type = str(event.get("event_type", ""))
        if not event_id or not event_type:
            return False

        # Idempotency check in DB
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
                    event_type=event_type,
                    processed_at=datetime.now(UTC),
                )
            )
            try:
                session.flush()
            except IntegrityError:
                return False

        notifications = self._build_notifications(event, correlation_id=correlation_id)
        if not notifications:
            return True

        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("realtime.kafka_consume") as span:
            span.set_attribute("event_type", event_type)
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)

            for notif in notifications:
                self._dispatch(notif)

        return True

    def _build_notifications(
        self, event: dict[str, Any], correlation_id: str | None = None
    ) -> list[Notification]:
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        event_id = event.get("event_id", "")
        occurred_at = event.get("occurred_at", datetime.now(UTC).isoformat())

        notifications: list[Notification] = []

        if event_type == "transfer.completed":
            amount = payload.get("amount", "0.00")
            source_cust = payload.get("source_customer_id")
            dest_cust = payload.get("destination_customer_id")

            if source_cust:
                user_id = self._find_user_id_by_customer(source_cust)
                if user_id:
                    message = f"Your transfer of Rs.{amount} was sent."
                    notifications.append(
                        Notification(
                            event_type="transfer.completed",
                            recipient_user_id=user_id,
                            title="Transfer completed",
                            message=message,
                            severity="info",
                            correlation_id=correlation_id,
                            event_id=f"{event_id}-sender",
                            occurred_at=occurred_at,
                            metadata={"amount": amount, "role": "sender"},
                        )
                    )

            if dest_cust and dest_cust != source_cust:
                user_id = self._find_user_id_by_customer(dest_cust)
                if user_id:
                    notifications.append(
                        Notification(
                            event_type="transfer.completed",
                            recipient_user_id=user_id,
                            title="Money received",
                            message=f"You received a transfer of ₹{amount}.",
                            severity="info",
                            correlation_id=correlation_id,
                            event_id=f"{event_id}-receiver",
                            occurred_at=occurred_at,
                            metadata={"amount": amount, "role": "receiver"},
                        )
                    )

        elif event_type == "risk.assessed":
            risk_level = str(payload.get("risk_level", "LOW")).upper()
            transaction_id = payload.get("transaction_id", "")

            user_id = self._find_user_id_by_transaction(transaction_id)
            if user_id:
                if risk_level == "HIGH":
                    alert = "A transfer needs attention: elevated risk."
                    notifications.append(
                        Notification(
                            event_type="fraud.risk_assessed",
                            recipient_user_id=user_id,
                            title="Security Alert",
                            message=alert,
                            severity="high",
                            correlation_id=correlation_id,
                            event_id=f"{event_id}-risk",
                            occurred_at=occurred_at,
                            metadata={"risk_level": "HIGH"},
                        )
                    )
                elif risk_level == "MEDIUM":
                    notifications.append(
                        Notification(
                            event_type="fraud.risk_assessed",
                            recipient_user_id=user_id,
                            title="Security Notice",
                            message="Your transfer risk assessment is available.",
                            severity="warning",
                            correlation_id=correlation_id,
                            occurred_at=occurred_at,
                            metadata={"risk_level": "MEDIUM"},
                        )
                    )

        return notifications

    def _find_user_id_by_customer(self, customer_id: str) -> str | None:
        with self._session_factory() as session:
            user = session.scalar(
                select(UserModel).where(UserModel.customer_id == customer_id)
            )
            return user.id if user else None

    def _find_user_id_by_transaction(self, transaction_id: str) -> str | None:
        with self._session_factory() as session:
            txn = session.get(TransactionModel, transaction_id)
            if not txn:
                return None
            account = session.get(AccountModel, txn.account_id)
            if not account:
                return None
            user = session.scalar(
                select(UserModel).where(UserModel.customer_id == account.customer_id)
            )
            return user.id if user else None

    def _dispatch(self, notification: Notification) -> None:
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._notification_service.dispatch(notification),
                self._loop,
            )
        else:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._notification_service.dispatch(notification),
                        loop,
                    )
                else:
                    loop.run_until_complete(
                        self._notification_service.dispatch(notification)
                    )
            except RuntimeError:
                asyncio.run(self._notification_service.dispatch(notification))


class RealtimeConsumerThread:
    """Background worker thread running RealtimeKafkaConsumer poll loop."""

    def __init__(self, consumer: RealtimeKafkaConsumer) -> None:
        self._consumer = consumer
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="realtime-consumer", daemon=True
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
                logger.warning("realtime_consumer_poll_failed", error=str(error))
                time.sleep(2)
