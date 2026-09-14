from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.events import EventEnvelope
from backend.app.infrastructure.persistence.models import OutboxEventModel


def add_outbox_event(session: Session, event: EventEnvelope) -> None:
    session.add(
        OutboxEventModel(
            id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.to_dict(),
            occurred_at=event.occurred_at,
        )
    )


class OutboxRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def pending(self, limit: int = 25) -> list[OutboxEventModel]:
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(OutboxEventModel)
                    .where(OutboxEventModel.published_at.is_(None))
                    .order_by(OutboxEventModel.created_at)
                    .limit(limit)
                )
            )

    def mark_published(self, event_id: str) -> None:
        with self._session_factory.begin() as session:
            event = session.get(OutboxEventModel, event_id)
            if event is not None:
                event.published_at = datetime.now(UTC)
                event.last_error = None

    def record_failure(self, event_id: str, error: Exception) -> None:
        with self._session_factory.begin() as session:
            event = session.get(OutboxEventModel, event_id)
            if event is not None:
                event.attempt_count += 1
                event.last_attempt_at = datetime.now(UTC)
                event.last_error = str(error)[:1000]


def event_message(event: OutboxEventModel) -> dict[str, Any]:
    return dict(event.payload)
