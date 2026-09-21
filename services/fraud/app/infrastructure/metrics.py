"""Prometheus metrics for the Fraud service.

Every metric is wired to a real execution path in the Kafka consumer, the
outbox publisher or the HTTP layer. Labels stay bounded to ``method``, route
template, ``status`` and ``risk_level``.
"""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the fraud service",
    ["method", "route", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route", "status"],
)
FRAUD_EVENTS_CONSUMED_TOTAL = Counter(
    "fraud_events_consumed_total",
    "Total transfer.completed events consumed from Kafka",
)
FRAUD_ASSESSMENTS_TOTAL = Counter(
    "fraud_assessments_total",
    "Total fraud risk assessments created",
    ["risk_level"],
)
FRAUD_ASSESSMENT_FAILURES_TOTAL = Counter(
    "fraud_assessment_failures_total",
    "Total fraud assessments that failed to complete",
)
FRAUD_DUPLICATE_EVENTS_TOTAL = Counter(
    "fraud_duplicate_events_total",
    "Total duplicate Kafka events ignored by the fraud consumer",
)
FRAUD_ML_PREDICTIONS_TOTAL = Counter(
    "fraud_ml_predictions_total",
    "Total ML fraud predictions attempted",
    ["outcome"],
)
FRAUD_ML_HIGH_RISK_TOTAL = Counter(
    "fraud_ml_high_risk_total",
    "ML predictions at or above the documented high-risk threshold",
)
FRAUD_GRAPH_QUERIES_TOTAL = Counter(
    "fraud_graph_queries_total",
    "Graph analysis operations attempted",
    ["operation", "result"],
)
FRAUD_GRAPH_FAILURES_TOTAL = Counter(
    "fraud_graph_failures_total",
    "Graph operations that failed (Neo4j unavailable or errored)",
    ["operation"],
)
FRAUD_GRAPH_PROJECTION_TOTAL = Counter(
    "fraud_graph_projection_total",
    "Transfer projections written to Neo4j",
    ["result"],
)
FRAUD_GRAPH_RISK_SIGNALS_TOTAL = Counter(
    "fraud_graph_risk_signals_total",
    "Graph risk signals raised, by bounded signal type",
    ["signal_type"],
)
OUTBOX_PENDING_EVENTS = Gauge(
    "outbox_pending_events",
    "Fraud outbox events waiting to be published",
)
OUTBOX_PUBLISH_FAILURES_TOTAL = Counter(
    "outbox_publish_failures_total",
    "Fraud outbox publish failures",
)


def record_event_consumed() -> None:
    """Increment the consumed-event counter."""
    FRAUD_EVENTS_CONSUMED_TOTAL.inc()


def record_assessment_created(risk_level: str) -> None:
    """Increment the assessment counter for a bounded risk level label."""
    FRAUD_ASSESSMENTS_TOTAL.labels(risk_level=risk_level).inc()


def record_assessment_failure() -> None:
    """Increment the assessment failure counter."""
    FRAUD_ASSESSMENT_FAILURES_TOTAL.inc()


def record_duplicate_event() -> None:
    """Increment the duplicate-event counter."""
    FRAUD_DUPLICATE_EVENTS_TOTAL.inc()


def record_ml_prediction(outcome: str) -> None:
    """Increment the ML prediction counter (bounded 'outcome' label)."""
    FRAUD_ML_PREDICTIONS_TOTAL.labels(outcome=outcome).inc()


def record_ml_high_risk() -> None:
    """Increment the ML high-risk counter."""
    FRAUD_ML_HIGH_RISK_TOTAL.inc()


def record_graph_operation(operation: str, result: str) -> None:
    """Increment the graph operation counter (bounded operation/result labels)."""
    FRAUD_GRAPH_QUERIES_TOTAL.labels(operation=operation, result=result).inc()


def record_graph_failure(operation: str) -> None:
    """Increment the graph failure counter for a bounded operation label."""
    FRAUD_GRAPH_FAILURES_TOTAL.labels(operation=operation).inc()


def record_graph_projection(result: str) -> None:
    """Increment the graph projection counter (bounded result label)."""
    FRAUD_GRAPH_PROJECTION_TOTAL.labels(result=result).inc()


def record_graph_signal(signal_type: str) -> None:
    """Increment a graph risk-signal counter (bounded signal_type label)."""
    FRAUD_GRAPH_RISK_SIGNALS_TOTAL.labels(signal_type=signal_type).inc()


def record_outbox_backlog(count: int) -> None:
    """Publish the current number of unpublished fraud outbox events."""
    OUTBOX_PENDING_EVENTS.set(count)


def record_outbox_publish_failure() -> None:
    """Increment the outbox publish failure counter."""
    OUTBOX_PUBLISH_FAILURES_TOTAL.inc()
