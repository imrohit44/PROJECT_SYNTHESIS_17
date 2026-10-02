"""Project Synthesis 17 Fraud / Risk service.

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
from services.fraud.graph import GraphClient, GraphRiskAnalyzer, GraphSettings
from services.fraud.ml.model import FraudModelLoadError, load_model
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
# Phase 12: ML combination weights (documented defaults; configurable).
ML_RULE_WEIGHT = float(os.getenv("ML_RULE_WEIGHT", "0.6"))
ML_ML_WEIGHT = float(os.getenv("ML_ML_WEIGHT", "0.4"))
# Phase 13: Neo4j is advisory. A missing client/config degrades to a
# rules + ML only service; it must never block fraud assessments.
GRAPH_ENABLED = os.getenv("GRAPH_ENABLED", "true").lower() == "true"

configure_structlog(SERVICE_NAME, LOG_LEVEL)
configure_tracing(SERVICE_NAME, OTLP_ENDPOINT, OTEL_ENABLED)
logger = structlog.get_logger(__name__)

# Set during lifespan; advisory-only, used by /ready for graph status.
_graph_analyzer: GraphRiskAnalyzer | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load the ML model ONCE at startup. A missing or invalid artifact is a
    # fail-fast startup error, never a silent "ML disabled" state.
    try:
        model = load_model()
    except FraudModelLoadError as error:
        logger.error("fraud_model_load_failed", error=str(error))
        raise

    if not RUN_MIGRATIONS:
        Base.metadata.create_all(bind=engine)

    graph_client: GraphClient | None = None
    graph_analyzer: GraphRiskAnalyzer | None = None
    if GRAPH_ENABLED:
        # One driver for the whole application lifetime; non-fatal on failure.
        graph_client = GraphClient(GraphSettings.from_env())
        graph_client.connect()
        graph_analyzer = GraphRiskAnalyzer(graph_client)
        global _graph_analyzer
        _graph_analyzer = graph_analyzer
        logger.info(
            "fraud_graph_client_initialized",
            graph_available=graph_analyzer.is_available(),
        )

    consumer_thread = FraudConsumerThread(
        FraudConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_CONSUMER_GROUP,
            topic=KAFKA_TOPIC,
            model=model,
            rule_weight=ML_RULE_WEIGHT,
            ml_weight=ML_ML_WEIGHT,
            graph=graph_analyzer,
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
        model_version=model.metadata.model_version,
        ml_threshold=model.metadata.threshold,
        rule_weight=ML_RULE_WEIGHT,
        ml_weight=ML_ML_WEIGHT,
        graph_version=graph_analyzer.graph_version if graph_analyzer else None,
    )
    try:
        yield
    finally:
        consumer_thread.stop()
        publisher_thread.stop()
        if graph_client is not None:
            graph_client.close()
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
    """Readiness: verifies PostgreSQL and Kafka with bounded timeouts.

    Neo4j status is reported as an advisory field and never gates readiness.
    """
    graph_available = (
        _graph_analyzer.is_available() if _graph_analyzer is not None else None
    )
    report = readiness_report(KAFKA_BOOTSTRAP_SERVERS, graph_available)
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
        "rule_score": assessment.rule_score,
        "ml_probability": assessment.ml_probability,
        "combined_score": assessment.combined_score,
        "model_version": assessment.model_version,
        "graph_score": assessment.graph_score,
        "graph_adjustment": assessment.graph_adjustment,
        "final_score": assessment.final_score,
        "graph_signals": assessment.graph_signals,
        "graph_version": assessment.graph_version,
        "created_at": assessment.created_at.isoformat(),
    }
