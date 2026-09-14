from decimal import Decimal

from backend.app.application.events import (
    EventEnvelope,
    deposit_completed_event,
    transfer_completed_event,
)


def test_event_envelope_serializes_json_values() -> None:
    event = deposit_completed_event("account-1", "customer-1", Decimal("12.30"), "tx-1")

    body = event.to_dict()

    assert body["event_id"] == event.event_id
    assert body["event_type"] == "deposit.completed"
    assert body["schema_version"] == 1
    assert body["aggregate_type"] == "account"
    assert body["payload"]["amount"] == "12.30"


def test_event_ids_are_unique() -> None:
    first = EventEnvelope("account.created", "account", "account-1", {})
    second = EventEnvelope("account.created", "account", "account-1", {})

    assert first.event_id != second.event_id


def test_transfer_event_avoids_sensitive_data() -> None:
    event = transfer_completed_event(
        "source",
        "destination",
        "source-customer",
        "destination-customer",
        Decimal("5.00"),
        "source-tx",
        "destination-tx",
    ).to_dict()

    serialized = str(event).lower()
    assert "password" not in serialized
    assert "token" not in serialized
    assert event["event_type"] == "transfer.completed"
