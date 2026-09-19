"""PyBank Fraud / Risk service.

Runs as an independent FastAPI service. It consumes transfer.completed events
from Kafka, evaluates deterministic risk rules, stores fraud_assessments in its
own PostgreSQL database, and publishes risk.assessed back to Kafka through its
own transactional outbox.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from services.common.observability import CorrelationIdMiddleware, configure_structlog
from services.common.tracing import configure_tracing
from sqlalchemy.orm import Session

from .infrastructure.database import Base, engine, get_db
from .infrastructure.kafka_consumer import FraudConsumer, FraudConsumerThread
from .infrastructure.kafka_producer import OutboxPublisherThread
from .infrastructure.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from .infrastructure.models import FraudAssessmentModel
from .infrastructure.readiness import is_ready, readiness_report

SERVICE_NAME = "fraud"
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "pybank-fraud-consumer")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "pybank.events")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_ENABLED = os.getenv("OTEL_TRACING_ENABLED", "false").lower() == "true"
RUN_MIGRATIONS = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"

configure_structlog(SERVICE_NAME, LOG_LEVEL)
configure_tracing(SERVICE_NAME, OTLP_ENDPOINT, OTEL_ENABLED)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if not RUN_MIGRATIONS:
        Base.metadata.create_all(bind=engine)

    consumer_thread = FraudConsumerThread(
        FraudConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_CONSUMER_GROUP,
            topic=KAFKA_TOPIC,
        )
    )
    publisher_thread = OutboxPublisherThread(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, topic=KAFKA_TOPIC
    )
    consumer_thread.start()
    publisher_thread.start()
    logger.info(
        "fraud_service_started",
        topic=KAFKA_TOPIC,
        consumer_group=KAFKA_CONSUMER_GROUP,
    )
    try:
        yield
    finally:
        consumer_thread.stop()
        publisher_thread.stop()
        logger.info("fraud_service_stopped")


app = FastAPI(title="PyBank Fraud Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    route = request.scope.get("route")
    template = getattr(route, "path", None) or "unmatched"
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    labels = {
        "method": request.method,
        "route": template,
        "status": str(response.status_code),
    }
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(elapsed)
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    return response


@app.get("/health", summary="Liveness probe")
def health_check() -> dict[str, str]:
    """Liveness only: stays 200 even when dependencies are unavailable."""
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/ready", summary="Readiness probe")
def readiness_check(response: Response) -> dict[str, object]:
    """Readiness: verifies PostgreSQL and Kafka with bounded timeouts."""
    report = readiness_report(KAFKA_BOOTSTRAP_SERVERS)
    ready = is_ready(report)
    response.status_code = 200 if ready else 503
    return {"status": "ready" if ready else "not_ready", "dependencies": report}


@app.get("/metrics", summary="Prometheus metrics")
def metrics_endpoint() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get(
    "/api/v1/risk-assessments/{transaction_id}",
    summary="Fetch a risk assessment by transaction id",
)
def get_risk_assessment(
    transaction_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    assessment = (
        db.query(FraudAssessmentModel)
        .filter(FraudAssessmentModel.transaction_id == transaction_id)
        .first()
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return {
        "assessment_id": assessment.assessment_id,
        "event_id": assessment.event_id,
        "transaction_id": assessment.transaction_id,
        "risk_score": assessment.risk_score,
        "risk_level": assessment.risk_level,
        "reasons": assessment.reasons,
        "correlation_id": assessment.correlation_id,
        "created_at": assessment.created_at.isoformat(),
    }
