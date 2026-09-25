"""Phase 15: notification mapping, WhatsApp adapter, consumer routing."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.persistence.models import (
    AccountModel,
    CustomerModel,
    TransactionModel,
    UserModel,
)
from backend.app.notifications.consumer import RealtimeKafkaConsumer
from backend.app.notifications.models import Notification
from backend.app.notifications.service import NotificationService, WhatsAppChannel
from backend.app.notifications.whatsapp import WhatsAppProvider


class _FakeProvider(WhatsAppProvider):
    def __init__(self, ok: bool = True) -> None:
        self.calls: list[tuple[str, str]] = []
        self._ok = ok

    async def send_message(
        self,
        recipient_phone: str,
        message: str,
        correlation_id: str | None = None,
    ) -> bool:
        self.calls.append((recipient_phone, message))
        return self._ok


def _seed_user_customer(
    session_factory: sessionmaker[Session],
    *,
    user_id: str,
    customer_id: str,
    phone: str | None = None,
) -> None:
    with session_factory.begin() as session:
        session.add(
            CustomerModel(
                id=customer_id, name="Test", email=f"{user_id}@ex.test", phone=phone
            )
        )
        session.add(
            UserModel(
                id=user_id,
                customer_id=customer_id,
                email=f"{user_id}@ex.test",
                password_hash="x",
                role="customer",
                is_active=True,
            )
        )


def _consumer(session_factory: sessionmaker[Session]) -> RealtimeKafkaConsumer:
    consumer = RealtimeKafkaConsumer.__new__(RealtimeKafkaConsumer)
    consumer._session_factory = session_factory  # type: ignore[attr-defined]
    consumer._group_id = "test-group"  # type: ignore[attr-defined]
    consumer._notification_service = None  # type: ignore[attr-defined, assignment]
    consumer._loop = None  # type: ignore[attr-defined]
    return consumer


def _note(
    user_id: str, severity: str = "info", event_type: str = "transfer.completed"
) -> Notification:
    return Notification(
        event_type=event_type,
        recipient_user_id=user_id,
        title="Transfer completed",
        message="Your transfer completed.",
        severity=severity,
        correlation_id="corr-1",
        event_id="evt-1",
    )


@pytest.mark.asyncio
async def test_low_risk_stays_silent_on_whatsapp(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_user_customer(
        session_factory, user_id="u-low", customer_id="c-low", phone="+10000000001"
    )
    provider = _FakeProvider(ok=True)
    channel = WhatsAppChannel(provider, session_factory, enabled=True)
    service = NotificationService([channel])
    low_risk = Notification(
        event_type="fraud.risk_assessed",
        recipient_user_id="u-low",
        title="ok",
        message="low risk informational",
        severity="info",
        event_id="e-low",
    )
    results = await service.dispatch(low_risk)
    assert results == {}
    assert provider.calls == []


@pytest.mark.asyncio
async def test_high_risk_uses_whatsapp_without_leaking_phone(
    session_factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    _seed_user_customer(
        session_factory, user_id="u-high", customer_id="c-high", phone="+10000000002"
    )
    provider = _FakeProvider(ok=True)
    channel = WhatsAppChannel(provider, session_factory, enabled=True)
    service = NotificationService([channel])
    high = Notification(
        event_type="fraud.risk_assessed",
        recipient_user_id="u-high",
        title="Security Alert",
        message="A transfer requires attention.",
        severity="high",
        event_id="e-high",
    )
    with caplog.at_level("INFO"):
        results = await service.dispatch(high)
    assert results == {"whatsapp": True}
    assert len(provider.calls) == 1
    assert "+10000000002" not in caplog.text


@pytest.mark.asyncio
async def test_whatsapp_disabled_and_failure_paths(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_user_customer(
        session_factory, user_id="u-off", customer_id="c-off", phone="+10000000003"
    )
    provider = _FakeProvider(ok=True)
    off = WhatsAppChannel(provider, session_factory, enabled=False)
    assert await off.send(_note("u-off", severity="high")) is False
    assert provider.calls == []

    _seed_user_customer(
        session_factory, user_id="u-fail", customer_id="c-fail", phone="+10000000004"
    )
    failing = WhatsAppChannel(_FakeProvider(ok=False), session_factory, enabled=True)
    service = NotificationService([failing])
    results = await service.dispatch(_note("u-fail", severity="high"))
    assert results == {"whatsapp": False}


def test_consumer_maps_transfer_to_sender_and_receiver(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_user_customer(
        session_factory, user_id="u-src", customer_id="c-src", phone="+10000000005"
    )
    _seed_user_customer(
        session_factory, user_id="u-dst", customer_id="c-dst", phone="+10000000006"
    )
    consumer = _consumer(session_factory)
    event = {
        "event_id": "evt-transfer-1",
        "event_type": "transfer.completed",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "payload": {
            "amount": "25.00",
            "source_customer_id": "c-src",
            "destination_customer_id": "c-dst",
        },
    }
    made = consumer._build_notifications(event, correlation_id="corr-x")
    recipients = {n.recipient_user_id for n in made}
    assert recipients == {"u-src", "u-dst"}
    assert all(n.correlation_id == "corr-x" for n in made)
    assert all("c-src" not in n.message and "c-dst" not in n.message for n in made)


def test_consumer_risk_mapping_and_low_risk_silence(
    session_factory: sessionmaker[Session],
) -> None:
    _seed_user_customer(
        session_factory, user_id="u-risk", customer_id="c-risk", phone="+10000000007"
    )
    with session_factory.begin() as session:
        session.add(
            AccountModel(
                id="acc-risk-1",
                customer_id="c-risk",
                account_type="savings",
                status="active",
                balance=100,
            )
        )
        session.add(
            TransactionModel(
                id="txn-risk-1",
                account_id="acc-risk-1",
                transaction_type="transfer",
                status="completed",
                amount=50,
                source_account_id="acc-risk-1",
                destination_account_id="acc-risk-1",
            )
        )
    consumer = _consumer(session_factory)
    high = {
        "event_id": "evt-risk-high",
        "event_type": "risk.assessed",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "payload": {"risk_level": "HIGH", "transaction_id": "txn-risk-1"},
    }
    made = consumer._build_notifications(high, correlation_id="corr-h")
    assert len(made) == 1
    assert made[0].recipient_user_id == "u-risk"
    assert made[0].severity == "high"
    assert "probability" not in made[0].message.lower()
    low = {
        "event_id": "evt-risk-low",
        "event_type": "risk.assessed",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "payload": {"risk_level": "LOW", "transaction_id": "txn-risk-1"},
    }
    assert consumer._build_notifications(low) == []


def test_consumer_idempotent_process_event(
    session_factory: sessionmaker[Session],
) -> None:
    dispatched: list[Notification] = []
    consumer = _consumer(session_factory)

    def _record(notification: Notification) -> None:
        dispatched.append(notification)

    consumer._dispatch = _record  # type: ignore[method-assign]
    _seed_user_customer(
        session_factory, user_id="u-idem", customer_id="c-idem", phone="+10000000008"
    )
    event = {
        "event_id": "evt-idem-1",
        "event_type": "transfer.completed",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "payload": {
            "amount": "10.00",
            "source_customer_id": "c-idem",
            "destination_customer_id": "c-idem",
        },
    }
    assert consumer.process_event(event, correlation_id="corr-1") is True
    assert consumer.process_event(event, correlation_id="corr-1") is False
    assert len(dispatched) == 1
