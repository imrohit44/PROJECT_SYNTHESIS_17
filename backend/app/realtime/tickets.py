"""Short-lived, single-use tickets for WebSocket authentication.

Browsers cannot attach an ``Authorization`` header to a WebSocket handshake,
so a credential must travel in the URL. Putting the raw JWT in the query string
is a poor choice: full URLs land in uvicorn access logs, proxy logs and browser
history, which would leak a long-lived bearer token.

Instead the client exchanges its JWT for an opaque ticket over an ordinary
authenticated HTTP request, then opens the socket with only that ticket:

    POST /api/v1/ws/ticket   Authorization: Bearer <jwt>   -> {"ticket": "..."}
    GET  /api/v1/ws?ticket=...                             -> authenticated socket

The ticket is a 256-bit random string, not a credential: it carries no claims,
authorizes nothing else, expires within seconds, and is destroyed on first
use. Even if one is captured from a log it is already spent or worthless.

Redis is used because it is already part the stack and provides the atomic
``GETDEL`` needed for single-use semantics. This is a short-lived key store,
not a distributed WebSocket fan-out; that remains out of scope.
"""

from __future__ import annotations

import secrets
import time
from typing import Protocol

import structlog
from redis import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)

DEFAULT_TICKET_TTL_SECONDS = 30


class TicketStore(Protocol):
    """Issues and single-use-consumes WebSocket tickets."""

    def issue(self, user_id: str) -> str: ...

    def consume(self, ticket: str) -> str | None:
        """Return the user_id bound to ``ticket``, or None. Consumes it."""


class InMemoryTicketStore:
    """Process-local store. Used when Redis is disabled and in tests."""

    def __init__(self, ttl_seconds: int = DEFAULT_TICKET_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._issued: dict[str, tuple[str, float]] = {}

    def issue(self, user_id: str) -> str:
        ticket = secrets.token_urlsafe(32)
        self._issued[ticket] = (user_id, time.monotonic() + self._ttl)
        self._prune()
        return ticket

    def consume(self, ticket: str) -> str | None:
        record = self._issued.pop(ticket, None)
        if record is None:
            return None
        user_id, expires_at = record
        if time.monotonic() > expires_at:
            logger.info("websocket_ticket_expired")
            return None
        return user_id

    def _prune(self) -> None:
        now = time.monotonic()
        for key in [k for k, (_, exp) in self._issued.items() if now > exp]:
            del self._issued[key]


class RedisTicketStore:
    """Redis-backed single-use ticket store (atomic GETDEL)."""

    def __init__(
        self,
        client: Redis,
        ttl_seconds: int = DEFAULT_TICKET_TTL_SECONDS,
        key_prefix: str = "pybank:ws-ticket",
    ) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    def issue(self, user_id: str) -> str:
        ticket = secrets.token_urlsafe(32)
        self._client.setex(self._key(ticket), self._ttl, user_id)
        return ticket

    def consume(self, ticket: str) -> str | None:
        """Atomically fetch and delete, so a ticket is usable exactly once."""
        try:
            value = self._client.getdel(self._key(ticket))
        except RedisError:
            # Fail closed: an unreachable store must not authorise anyone.
            logger.warning("websocket_ticket_store_unavailable")
            return None
        return str(value) if value is not None else None

    def _key(self, ticket: str) -> str:
        return f"{self._prefix}:{ticket}"


_store_instance: TicketStore | None = None


def create_ticket_store(redis_url: str | None, ttl_seconds: int) -> TicketStore:
    """Build the best available store, degrading to in-memory if Redis is absent."""
    if not redis_url:
        logger.info("websocket_ticket_store_in_memory", reason="no_redis_url")
        return InMemoryTicketStore(ttl_seconds)
    return RedisTicketStore(
        Redis.from_url(redis_url, decode_responses=True), ttl_seconds
    )


def get_ticket_store() -> TicketStore:
    """Return the process-local ticket store singleton."""
    global _store_instance
    if _store_instance is None:
        from backend.app.core.config import get_settings

        settings = get_settings()
        _store_instance = create_ticket_store(
            settings.redis_url, settings.websocket_ticket_ttl_seconds
        )
    return _store_instance


def set_ticket_store(store: TicketStore | None) -> None:
    """Override the singleton (tests)."""
    global _store_instance
    _store_instance = store
