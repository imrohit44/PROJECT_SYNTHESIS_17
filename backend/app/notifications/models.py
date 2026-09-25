"""Notification domain model and channel abstraction.

Notifications are channel-neutral representations of user-facing alerts.
Channels (WebSocket, WhatsApp) implement the NotificationChannel interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Notification:
    """Channel-neutral notification data object."""

    event_type: str
    recipient_user_id: str
    title: str
    message: str
    severity: str = "info"  # "info" | "warning" | "high"
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class NotificationChannel(ABC):
    """Abstract interface for a notification delivery channel."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the name of the channel (e.g. 'websocket', 'whatsapp')."""
        ...

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Deliver the notification. Return True on success, False on failure."""
        ...
