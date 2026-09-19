"""Structured JSON logging and correlation-id helpers shared by both services.

Every application log line written through this module is a single JSON object
on stdout, so ``json.loads(line)`` succeeds without stripping a prefix such as
``INFO:backend.app.main:``.
"""

from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 128

_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """Return a fresh UUID4 correlation id."""
    return str(uuid.uuid4())


def is_valid_correlation_id(value: str | None) -> bool:
    """True when a client supplied correlation id is safe to log and echo."""
    if not value or len(value) > MAX_CORRELATION_ID_LENGTH:
        return False
    return all(char.isprintable() and not char.isspace() for char in value)


def bind_correlation_id(correlation_id: str | None) -> None:
    """Bind a correlation id for the current context (request or worker)."""
    _correlation_id_ctx.set(correlation_id)


def clear_correlation_id() -> None:
    """Remove the correlation id from the current context."""
    _correlation_id_ctx.set(None)


def get_correlation_id() -> str | None:
    """Return the correlation id bound to the current context, if any."""
    return _correlation_id_ctx.get()


def _inject_service(service_name: str) -> Any:
    def processor(
        _logger: Any, _method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        event_dict.setdefault("service", service_name)
        return event_dict

    return processor


def _inject_correlation_id(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    correlation_id = _correlation_id_ctx.get()
    if correlation_id:
        event_dict.setdefault("correlation_id", correlation_id)
    return event_dict


def _shared_processors(service_name: str) -> list[Any]:
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _inject_service(service_name),
        _inject_correlation_id,
    ]


def configure_structlog(service_name: str, level: str = "INFO") -> None:
    """Configure structlog and stdlib logging for pure-JSON stdout output.

    A single ``ProcessorFormatter`` renders both structlog events and standard
    library records (uvicorn, sqlalchemy, alembic) as JSON, and the uvicorn
    loggers are pointed at the same handler so no plain-text line is emitted.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    shared = _shared_processors(service_name)

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(log_level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False
        uvicorn_logger.setLevel(log_level)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Preserve or generate ``X-Correlation-ID`` for every request.

    A client supplied value is kept when it is short and printable; otherwise a
    UUID4 is generated. The id is bound to the correlation context variable,
    stored on ``request.state``, and returned in the response header.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = (
            supplied
            if supplied and is_valid_correlation_id(supplied)
            else new_correlation_id()
        )
        request.state.correlation_id = correlation_id
        bind_correlation_id(correlation_id)
        try:
            response: Response = await call_next(request)
        finally:
            clear_correlation_id()
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
