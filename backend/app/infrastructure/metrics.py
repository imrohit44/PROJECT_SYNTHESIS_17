"""Prometheus metrics for the Banking service.

Every metric here is wired to a real execution path. Labels are bounded to
``method``, route template and ``status``; identifiers such as customer,
account, transaction, event or correlation ids are never used as labels.
"""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the banking API",
    ["method", "route", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route", "status"],
)
TRANSFERS_TOTAL = Counter(
    "transfers_total",
    "Total successful transfers",
)
TRANSFER_FAILURES_TOTAL = Counter(
    "transfer_failures_total",
    "Total failed transfer attempts",
)
OUTBOX_PENDING_EVENTS = Gauge(
    "outbox_pending_events",
    "Banking outbox events waiting to be published",
)
OUTBOX_PUBLISH_FAILURES_TOTAL = Counter(
    "outbox_publish_failures_total",
    "Banking outbox publish failures",
)


def record_transfer_success() -> None:
    """Increment the successful transfer counter."""
    TRANSFERS_TOTAL.inc()


def record_transfer_failure() -> None:
    """Increment the failed transfer counter."""
    TRANSFER_FAILURES_TOTAL.inc()


def record_outbox_backlog(count: int) -> None:
    """Publish the current number of unpublished outbox events."""
    OUTBOX_PENDING_EVENTS.set(count)


def record_outbox_publish_failure() -> None:
    """Increment the outbox publish failure counter."""
    OUTBOX_PUBLISH_FAILURES_TOTAL.inc()
