"""Dependency readiness probes for the Fraud service.

The fraud service depends on PostgreSQL and Kafka only; it never calls the
Banking API synchronously.
"""

from __future__ import annotations

from confluent_kafka.admin import AdminClient

from .database import engine

POSTGRES_TIMEOUT_SECONDS = 2
KAFKA_TIMEOUT_SECONDS = 3


def check_postgres() -> bool:
    """Return True when a trivial query succeeds against the fraud database."""
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception:
        return False
    return True


def check_kafka(bootstrap_servers: str) -> bool:
    """Return True when the broker answers a metadata request."""
    admin = AdminClient(
        {
            "bootstrap.servers": bootstrap_servers,
            "socket.timeout.ms": KAFKA_TIMEOUT_SECONDS * 1000,
        }
    )
    try:
        admin.list_topics(timeout=KAFKA_TIMEOUT_SECONDS)
    except Exception:
        return False
    return True


def readiness_report(
    bootstrap_servers: str, graph_available: bool | None = None
) -> dict[str, str]:
    """Return per-dependency readiness as ``ok`` or ``unavailable``.

    ``neo4j`` is an ADVISORY entry: the graph is an analytical enrichment, not
    a baseline dependency, so its status is reported but never gates readiness.
    """
    report = {
        "postgres": "ok" if check_postgres() else "unavailable",
        "kafka": "ok" if check_kafka(bootstrap_servers) else "unavailable",
    }
    if graph_available is not None:
        report["neo4j"] = "ok" if graph_available else "unavailable"
    return report


# Only these dependencies gate readiness; advisory entries (e.g. neo4j) do not.
REQUIRED_DEPENDENCIES: tuple[str, ...] = ("postgres", "kafka")


def is_ready(report: dict[str, str]) -> bool:
    """Return True only when every REQUIRED dependency reported ``ok``."""
    return all(report.get(dependency) == "ok" for dependency in REQUIRED_DEPENDENCIES)
