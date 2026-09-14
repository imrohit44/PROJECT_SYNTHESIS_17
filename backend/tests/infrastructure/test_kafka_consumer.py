from backend.app.infrastructure.kafka import AuditConsumer
from backend.app.infrastructure.persistence.models import ProcessedEventModel


def test_audit_consumer_is_idempotent(session_factory) -> None:
    consumer = AuditConsumer.__new__(AuditConsumer)
    consumer._group_id = "test-group"
    consumer._session_factory = session_factory
    event = {"event_id": "event-1", "event_type": "transfer.completed"}

    assert consumer.process_event(event)
    assert not consumer.process_event(event)

    with session_factory() as session:
        processed = session.query(ProcessedEventModel).all()
        assert len(processed) == 1
        assert processed[0].event_id == "event-1"
