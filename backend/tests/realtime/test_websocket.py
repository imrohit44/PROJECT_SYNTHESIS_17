"""Phase 15: WebSocket auth, lifecycle, and user isolation over HTTP."""

from __future__ import annotations

import anyio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.main import app
from backend.app.realtime.manager import WebSocketManager, get_websocket_manager
from backend.app.realtime.tickets import get_ticket_store, set_ticket_store


def test_websocket_rejects_anonymous_and_invalid_tokens(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws?ticket=invalid-ticket"):
            pass


def test_websocket_auth_and_user_isolation(
    client: TestClient,
    token_factory,  # type: ignore[no-untyped-def]
) -> None:
    alice = token_factory(name="WsAlice", email="wsalice@example.com")
    bob = token_factory(name="WsBob", email="wsbob@example.com")
    manager = WebSocketManager()
    app.dependency_overrides[get_websocket_manager] = lambda: manager
    store = get_ticket_store()
    try:
        with client.websocket_connect(
            f"/api/v1/ws?ticket={store.issue(alice['user_id'])}"
        ) as alice_ws:
            hello = alice_ws.receive_json()
            assert hello["type"] == "connection.established"
            assert "user_id" not in hello["data"]

            with client.websocket_connect(
                f"/api/v1/ws?ticket={store.issue(bob['user_id'])}"
            ) as bob_ws:
                assert bob_ws.receive_json()["type"] == "connection.established"

                async def _send() -> int:
                    return await manager.send_to_user(
                        alice["user_id"],
                        {"type": "transfer.completed", "data": {"title": "hi"}},
                        event_type="transfer.completed",
                    )

                alice_ws.send_text("ping")
                assert alice_ws.receive_text() == "pong"
                bob_ws.send_text("ping")
                assert bob_ws.receive_text() == "pong"
                assert anyio.run(_send) == 1
                assert manager.connection_count_for_user(alice["user_id"]) == 1
                assert manager.connection_count_for_user(bob["user_id"]) == 1
        assert manager.connection_count_for_user(alice["user_id"]) == 0
    finally:
        app.dependency_overrides.pop(get_websocket_manager, None)
        set_ticket_store(None)


def test_websocket_ticket_is_single_use() -> None:
    """A ticket must authorize exactly one socket, never a replayed one."""
    from backend.app.realtime.tickets import get_ticket_store

    store = get_ticket_store()
    ticket = store.issue("user-x")
    assert store.consume(ticket) == "user-x"
    assert store.consume(ticket) is None
