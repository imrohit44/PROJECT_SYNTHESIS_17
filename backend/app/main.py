"""PyBank Banking API entrypoint.

Observability wiring lives here:

* structlog JSON logging on stdout (one JSON object per line)
* ``X-Correlation-ID`` middleware
* HTTP Prometheus metrics using bounded route-template labels
* liveness (``/health``), readiness (``/ready``) and ``/metrics`` endpoints
* OpenTelemetry HTTP instrumentation exported to Jaeger over OTLP

Kafka is asynchronous transport only. PostgreSQL remains the source of truth.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.errors import register_exception_handlers
from backend.app.api.v1.router import router as api_router
from backend.app.core.config import get_settings
from backend.app.infrastructure.kafka import (
    AuditConsumer,
    AuditConsumerThread,
    KafkaEventProducer,
    OutboxPublisher,
    OutboxPublisherThread,
)
from backend.app.infrastructure.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from backend.app.infrastructure.outbox import OutboxRepository
from backend.app.infrastructure.persistence.database import create_session_factory
from backend.app.infrastructure.readiness import is_ready, readiness_report
from backend.app.notifications.consumer import (
    RealtimeConsumerThread,
    RealtimeKafkaConsumer,
)
from backend.app.notifications.service import (
    NotificationChannel,
    NotificationService,
    WebSocketChannel,
    WhatsAppChannel,
)
from backend.app.notifications.whatsapp import MetaCloudWhatsAppProvider
from backend.app.realtime.manager import get_websocket_manager
from services.common.observability import (
    CORRELATION_ID_HEADER,
    CorrelationIdMiddleware,
    configure_structlog,
)
from services.common.tracing import configure_tracing

SERVICE_NAME = "banking"

settings = get_settings()
configure_structlog(SERVICE_NAME, settings.log_level)
OTLP_ENDPOINT = settings.otel_exporter_otlp_endpoint
configure_tracing(SERVICE_NAME, OTLP_ENDPOINT, settings.otel_tracing_enabled)
logger = structlog.get_logger(__name__)

KAFKA_TOPIC = f"{settings.kafka_topic_prefix}.events"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "banking_starting",
        app_env=settings.app_env,
        kafka_enabled=settings.kafka_enabled,
        kafka_topic=KAFKA_TOPIC,
    )
    workers: list[
        OutboxPublisherThread | AuditConsumerThread | RealtimeConsumerThread
    ] = []
    if settings.kafka_enabled:
        session_factory = create_session_factory(settings.database_url)
        producer = KafkaEventProducer(settings.kafka_bootstrap_servers, KAFKA_TOPIC)
        workers.append(
            OutboxPublisherThread(
                OutboxPublisher(OutboxRepository(session_factory), producer)
            )
        )
        workers.append(
            AuditConsumerThread(
                AuditConsumer(
                    settings.kafka_bootstrap_servers,
                    KAFKA_TOPIC,
                    settings.kafka_consumer_group,
                    session_factory,
                )
            )
        )
        # Phase 15: Kafka -> notification fan-out. Fail-closed for the worker,
        # fail-open for banking: a consumer construction failure must never take
        # the core API offline.
        try:
            ws_manager = get_websocket_manager()
            provider = MetaCloudWhatsAppProvider(
                api_url=settings.whatsapp_api_url,
                phone_number_id=settings.whatsapp_phone_number_id,
                access_token=settings.whatsapp_access_token,
                timeout_seconds=settings.whatsapp_timeout_seconds,
            )
            channels: list[NotificationChannel] = [WebSocketChannel(ws_manager)]
            if settings.whatsapp_enabled:
                channels.append(
                    WhatsAppChannel(
                        provider,
                        session_factory,
                        enabled=settings.whatsapp_enabled,
                    )
                )
            notification_service = NotificationService(channels)
            workers.append(
                RealtimeConsumerThread(
                    RealtimeKafkaConsumer(
                        bootstrap_servers=settings.kafka_bootstrap_servers,
                        topic=KAFKA_TOPIC,
                        group_id=settings.realtime_consumer_group,
                        session_factory=session_factory,
                        notification_service=notification_service,
                    )
                )
            )
        except Exception as error:
            logger.warning("realtime_consumer_disabled", error=str(error))
        for worker in workers:
            worker.start()
    try:
        yield
    finally:
        for worker in workers:
            worker.stop()
        logger.info("banking_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", CORRELATION_ID_HEADER],
)
app.add_middleware(CorrelationIdMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add hardening headers to every response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count/latency and emit one structured JSON access log."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        route = request.scope.get("route")
        template = getattr(route, "path", None) or "unmatched"
        labels = {
            "method": request.method,
            "route": template,
            "status": str(response.status_code),
        }
        HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_ms / 1000)
        HTTP_REQUESTS_TOTAL.labels(**labels).inc()
        logger.info(
            "http_request",
            method=request.method,
            request_path=request.url.path,
            status_code=response.status_code,
            duration=duration_ms,
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)

if settings.otel_tracing_enabled:
    FastAPIInstrumentor.instrument_app(app)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["health"], summary="Liveness probe")
async def health() -> dict[str, str]:
    """Liveness only: stays 200 even when dependencies are unavailable."""
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/ready", tags=["health"], summary="Readiness probe")
async def ready(response: Response) -> dict[str, object]:
    """Readiness: verifies PostgreSQL, Redis and Kafka with bounded timeouts."""
    report = readiness_report(settings)
    is_service_ready = is_ready(report)
    response.status_code = 200 if is_service_ready else 503
    return {
        "status": "ready" if is_service_ready else "not_ready",
        "dependencies": report,
    }


@app.get("/metrics", tags=["health"], summary="Prometheus metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
