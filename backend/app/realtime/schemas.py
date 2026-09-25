"""Typed contracts for WebSocket real-time messages.

WebSocket messages are user-facing notifications only, NOT the financial
source of truth. Internal Kafka envelopes, database row IDs, JWTs, and passwords
are never included.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RealtimeMessage(BaseModel):
    """Sanitized, typed message delivered to browser WebSockets."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Message type identifier, e.g. transaction.completed")
    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Event or delivery identifier for deduplication",
    )
    occurred_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for end-to-end trace linkage",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe, bounded user-appropriate payload",
    )
