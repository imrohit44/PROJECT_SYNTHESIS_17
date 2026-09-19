"""Fraud outbox persistence.

Each risk.assessed event stores the correlation id and traceparent captured at
consume time so they survive the asynchronous hop to Kafka.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..application.events import EventEnvelope
from .models import OutboxEventModel


def add_outbox_event(
    db: Session,
    event: EventEnvelope,
    correlation_id: str | None = None,
    traceparent: str | None = None,
) -> None:
    """Append an event to the fraud outbox within the caller transaction."""
    db.add(
        OutboxEventModel(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            schema_version=str(event.schema_version),
            correlation_id=correlation_id,
            traceparent=traceparent,
            occurred_at=event.occurred_at,
        )
    )


class OutboxRepository:
    """Reads and updates pending fraud outbox events."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def pending(self, limit: int = 50) -> list[OutboxEventModel]:
        return list(
            self._db.scalars(
                select(OutboxEventModel)
                .where(OutboxEventModel.published_at.is_(None))
                .order_by(OutboxEventModel.occurred_at)
                .limit(limit)
            )
        )

    def count_pending(self) -> int:
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(OutboxEventModel.published_at.is_(None))
            )
            or 0
        )

    def mark_published(self, event_id: str, published_at: datetime) -> None:
        event = self._db.get(OutboxEventModel, event_id)
        if event is not None:
            event.published_at = published_at
            event.error_message = None
            self._db.commit()

    def mark_failed(self, event_id: str, error: str) -> None:
        event = self._db.get(OutboxEventModel, event_id)
        if event is not None:
            event.error_message = error[:500]
            self._db.commit()
