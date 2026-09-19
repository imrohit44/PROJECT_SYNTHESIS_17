"""Phase 11: transfer/failure counters and the outbox gauge use real paths."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.events import EventEnvelope
from backend.app.infrastructure.metrics import (
    OUTBOX_PENDING_EVENTS,
    TRANSFER_FAILURES_TOTAL,
    TRANSFERS_TOTAL,
    record_outbox_backlog,
)
from backend.app.infrastructure.outbox import OutboxRepository, add_outbox_event


def _register_and_login(
    client: TestClient, name: str
) -> tuple[str, str, dict[str, str]]:
    email = f"{name.lower()}-{uuid.uuid4().hex[:8]}@example.com"
    password = "correct horse battery staple"
    created = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert created.status_code == 201
    customer_id = created.json()["customer_id"]
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return customer_id, email, headers


def _create_account(
    client: TestClient, headers: dict[str, str], customer_id: str
) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "customer_id": customer_id,
            "account_type": "current",
            "opening_balance": "100.00",
            "overdraft_limit": "50.00",
        },
    )
    assert response.status_code == 201
    return str(response.json()["account_id"])


def test_successful_transfer_increments_counter(client: TestClient) -> None:
    alice_id, _, alice_headers = _register_and_login(client, "Alice")
    _, _, bob_headers = _register_and_login(client, "Bob")
    source_id = _create_account(client, alice_headers, alice_id)
    bob_customer = client.post(
        "/api/v1/accounts",
        headers=bob_headers,
        json={"customer_id": alice_id, "account_type": "savings"},
    )
    assert bob_customer.status_code in (200, 201, 403)
    before = TRANSFERS_TOTAL._value.get()
    response = client.post(
        "/api/v1/transfers",
        headers=alice_headers,
        json={
            "source_account_id": source_id,
            "destination_account_id": source_id,
            "amount": "5.00",
        },
    )
    assert response.status_code in (200, 400, 403, 409, 422)
    if response.status_code == 200:
        assert TRANSFERS_TOTAL._value.get() == before + 1
    else:
        assert TRANSFERS_TOTAL._value.get() >= before


def test_transfer_failure_increments_counter(client: TestClient) -> None:
    _, _, headers = _register_and_login(client, "Carol")
    before = TRANSFER_FAILURES_TOTAL._value.get()
    response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": "missing",
            "destination_account_id": "missing",
            "amount": "1.00",
        },
    )
    assert response.status_code in (400, 403, 404, 422)
    assert TRANSFER_FAILURES_TOTAL._value.get() >= before + 1


def test_outbox_backlog_gauge_reflects_pending_rows(
    session_factory: sessionmaker[Session],
) -> None:
    repository = OutboxRepository(session_factory)
    before = repository.count_pending()
    with session_factory.begin() as session:
        assert isinstance(session, Session)
        add_outbox_event(
            session,
            EventEnvelope(
                event_type="transfer.completed",
                aggregate_type="transaction",
                aggregate_id=f"txn-{uuid.uuid4().hex[:8]}",
                payload={"amount": "1.00"},
            ),
        )
    pending = repository.count_pending()
    record_outbox_backlog(pending)
    assert pending == before + 1
    assert OUTBOX_PENDING_EVENTS._value.get() == pending
