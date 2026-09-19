"""OpenTelemetry tracing shared by the Banking API and the Fraud service.

Traces are exported over OTLP/HTTP to Jaeger. Kafka records carry a W3C
``traceparent`` header so the consumer can continue the producer trace.

Asynchronous limitation: a Banking → Kafka → Fraud chain spans two processes
and a broker. The consumer continues the propagated trace context, but the
originating HTTP request has usually finished by the time the record is
consumed, so the trace shows a hand-off rather than one continuous request.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

CORRELATION_HEADER = "correlation_id"
TRACEPARENT_HEADER = "traceparent"

_configured = False


def configure_tracing(
    service_name: str,
    endpoint: str | None,
    enabled: bool = True,
) -> bool:
    """Install a global TracerProvider exporting over OTLP/HTTP.

    Returns True when an exporter was installed. When tracing is disabled or no
    endpoint is configured the global provider is left untouched so spans are
    simply dropped instead of failing.
    """
    global _configured
    if _configured or not enabled or not endpoint:
        return _configured

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5))
    )
    trace.set_tracer_provider(provider)
    _configured = True
    return True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given instrumentation scope."""
    return trace.get_tracer(name)


def inject_context_headers(
    correlation_id: str | None = None,
) -> list[tuple[str, bytes]]:
    """Build Kafka headers carrying ``traceparent`` and ``correlation_id``.

    Both values are separate UTF-8 byte headers. ``correlation_id`` is an
    application identifier and is deliberately not part of the W3C trace
    context.
    """
    carrier: dict[str, str] = {}
    inject(carrier)
    headers: list[tuple[str, bytes]] = []
    if correlation_id:
        headers.append((CORRELATION_HEADER, correlation_id.encode("utf-8")))
    traceparent = carrier.get(TRACEPARENT_HEADER)
    if traceparent:
        headers.append((TRACEPARENT_HEADER, traceparent.encode("utf-8")))
    return headers


def extract_context(headers: Any) -> Any:
    """Extract W3C trace context from Kafka or HTTP headers."""
    carrier: dict[str, str] = {}
    for key, value in dict(headers or {}).items():
        if isinstance(value, str):
            carrier[str(key)] = value
    return extract(carrier)


def extract_header(
    record_headers: Any,
    name: str,
) -> str | None:
    """Return one decoded Kafka header value, tolerating missing bytes."""
    for key, value in record_headers or []:
        if key == name and value is not None:
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return None
    return None


def current_traceparent() -> str | None:
    """Return the active W3C traceparent string, if a span is recording."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get(TRACEPARENT_HEADER)
