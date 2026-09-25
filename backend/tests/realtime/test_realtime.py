"""Phase 15: manager isolation, mapping, and WhatsApp boundaries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.notifications.models import Notification
from backend.app.notifications.service import WebSocketChannel
from backend.app.realtime.manager import WebSocketManager
from backend.app.realtime.schemas import RealtimeMessage


class _StubWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:  # type: ignore[no-untyped-def]
        self.sent.append(message)


class _FailingWebSocket(_StubWebSocket):
    async def send_json(self, message: dict) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("socket broken")


@pytest.mark.asyncio
async def test_websocket_manager_user_isolation() -> None:
    manager = WebSocketManager()
    socket_a = _StubWebSocket()
    socket_b = _StubWebSocket()
    await manager.connect("user-a", socket_a)  # type: ignore[arg-type]
    await manager.connect("user-b", socket_b)  # type: ignore[arg-type]

    delivered = await manager.send_to_user(
        "user-a", {"type": "transfer.completed"}, event_type="transfer.completed"
    )
    assert delivered == 1
    assert len(socket_a.sent) == 1
    assert socket_b.sent == []
    await manager.disconnect("user-a", socket_a)  # type: ignore[arg-type]
    await manager.disconnect("user-b", socket_b)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_websocket_manager_cleanup_and_failure() -> None:
    manager = WebSocketManager()
    good = _StubWebSocket()
    bad = _FailingWebSocket()
    await manager.connect("user-a", good)  # type: ignore[arg-type]
    await manager.connect("user-a", bad)  # type: ignore[arg-type]
    delivered = await manager.send_to_user("user-a", {"type": "x"})
    assert delivered == 1
    assert manager.connection_count_for_user("user-a") == 1
    await manager.disconnect("user-a", good)  # type: ignore[arg-type]
    assert manager.connection_count_for_user("user-a") == 0


def test_realtime_message_forbids_extra_and_internal_fields() -> None:
    message = RealtimeMessage(
        type="transfer.completed",
        event_id="evt-1",
        occurred_at="2026-01-01T00:00:00+00:00",
        correlation_id="corr-1",
        data={"title": "Transfer completed", "message": "ok", "severity": "info"},
    )
    dumped = message.model_dump()
    assert dumped["type"] == "transfer.completed"
    assert "password" not in dumped["data"]
    with pytest.raises(ValidationError):
        RealtimeMessage(
            type="x",
            data={},
            password="secret",  # type: ignore[call-arg]
        )


@pytest.mark.asyncio
async def test_websocket_channel_delivers_only_to_recipient() -> None:
    manager = WebSocketManager()
    socket_a = _StubWebSocket()
    await manager.connect("user-a", socket_a)  # type: ignore[arg-type]
    channel = WebSocketChannel(manager)
    note = Notification(
        event_type="transfer.completed",
        recipient_user_id="user-a",
        title="Transfer completed",
        message="Your transfer completed.",
        severity="info",
        correlation_id="corr-1",
        event_id="evt-1",
    )
    assert await channel.send(note) is True
    other = Notification(
        event_type="transfer.completed",
        recipient_user_id="user-b",
        title="Transfer completed",
        message="Your transfer completed.",
        severity="info",
        correlation_id="corr-1",
        event_id="evt-2",
    )
    assert await channel.send(other) is False
    assert len(socket_a.sent) == 1
