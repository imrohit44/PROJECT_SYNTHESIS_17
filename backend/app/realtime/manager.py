"""WebSocket connection management and typed message delivery.

Connections are mapped process-locally:
user_id -> set of active WebSocket instances.

Architectural boundary note:
This connection manager is process-local. A multi-instance deployment would
require a distributed fan-out mechanism (such as Redis Pub/Sub), but that
is deferred. WebSocket delivery is best-effort and client notification only;
PostgreSQL and Kafka remain the financial sources of truth.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import WebSocket

from backend.app.infrastructure.metrics import (
    REALTIME_MESSAGE_FAILURES_TOTAL,
    REALTIME_MESSAGES_SENT_TOTAL,
    REALTIME_WEBSOCKET_CONNECTIONS_TOTAL,
    REALTIME_WEBSOCKET_DISCONNECTS_TOTAL,
)
from services.common.tracing import get_tracer

logger = structlog.get_logger(__name__)


class WebSocketManager:
    """Manages active WebSockets keyed by authenticated user ID."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Register a new active WebSocket connection for a user."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
        REALTIME_WEBSOCKET_CONNECTIONS_TOTAL.inc()
        logger.info("websocket_connected", user_id=user_id)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        REALTIME_WEBSOCKET_DISCONNECTS_TOTAL.inc()
        logger.info("websocket_disconnected", user_id=user_id)

    def active_users(self) -> list[str]:
        """Return user IDs currently having at least one active connection."""
        return list(self._connections.keys())

    def connection_count_for_user(self, user_id: str) -> int:
        """Return the count of active WebSockets for a given user."""
        return len(self._connections.get(user_id, set()))

    async def send_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
        event_type: str = "notification",
        correlation_id: str | None = None,
    ) -> int:
        """Deliver a message to all active WebSockets owned by user_id.

        Returns the number of successful socket deliveries.
        Never delivers to sockets belonging to other users.
        """
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("realtime.websocket_send") as span:
            span.set_attribute("event_type", event_type)
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)

            async with self._lock:
                sockets = list(self._connections.get(user_id, set()))

            if not sockets:
                return 0

            successful = 0
            dead_sockets: list[WebSocket] = []

            for ws in sockets:
                try:
                    await ws.send_json(message)
                    successful += 1
                    REALTIME_MESSAGES_SENT_TOTAL.labels(event_type=event_type).inc()
                except Exception as error:
                    REALTIME_MESSAGE_FAILURES_TOTAL.labels(event_type=event_type).inc()
                    logger.warning(
                        "websocket_send_failed",
                        event_type=event_type,
                        error=str(error),
                    )
                    dead_sockets.append(ws)

            if dead_sockets:
                async with self._lock:
                    if user_id in self._connections:
                        for ws in dead_sockets:
                            self._connections[user_id].discard(ws)
                        if not self._connections[user_id]:
                            del self._connections[user_id]

            return successful


# Global process-local connection manager singleton
_manager_instance: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """Return the application process-local WebSocket manager."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WebSocketManager()
    return _manager_instance
