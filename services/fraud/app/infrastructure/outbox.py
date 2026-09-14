from datetime import datetime

from sqlalchemy.orm import Session

from ..application.events import EventEnvelope
from .models import OutboxEventModel


def add_outbox_event(db: Session, event: EventEnvelope) -> None:
    db_event = OutboxEventModel(
        event_id=event.event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        payload=event.payload,
        schema_version=str(event.schema_version),
        occurred_at=event.occurred_at,
    )
    db.add(db_event)


class OutboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_events(self, limit: int = 100) -> list[OutboxEventModel]:
        return (
            self.db.query(OutboxEventModel)
            .filter(OutboxEventModel.published_at == None)
            .limit(limit)
            .all()
        )

    def mark_published(self, event_id: str, published_at: datetime) -> None:
        event = (
            self.db.query(OutboxEventModel)
            .filter(OutboxEventModel.event_id == event_id)
            .first()
        )
        if event:
            event.published_at = published_at
            self.db.commit()

    def mark_failed(self, event_id: str, error: str) -> None:
        event = (
            self.db.query(OutboxEventModel)
            .filter(OutboxEventModel.event_id == event_id)
            .first()
        )
        if event:
            event.error_message = error
            self.db.commit()
