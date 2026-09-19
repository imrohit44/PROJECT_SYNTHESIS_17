"""Dependency readiness probes for the Banking service.

Each probe uses a bounded timeout and returns a boolean. Results are exposed as
a mapping of dependency name to ``ok``/``unavailable``; credentials and
connection strings are never returned to callers.
"""

from __future__ import annotations

from typing import Any

from confluent_kafka.admin import AdminClient
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, text

POSTGRES_TIMEOUT_SECONDS = 2
KAFKA_TIMEOUT_SECONDS = 3


def check_postgres(database_url: str) -> bool:
    """Return True when a trivial query succeeds against PostgreSQL."""
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": POSTGRES_TIMEOUT_SECONDS},
        )
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except Exception:
        return False
    return True


def check_redis(redis_url: str | None) -> bool:
    """Return True when Redis answers PING, or when caching is not configured."""
    if not redis_url:
        return True
    client: Redis = Redis.from_url(
        redis_url,
        socket_connect_timeout=POSTGRES_TIMEOUT_SECONDS,
        socket_timeout=POSTGRES_TIMEOUT_SECONDS,
    )
    try:
        client.ping()
    except (RedisError, OSError):
        return False
    finally:
        client.close()
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


def readiness_report(settings: Any) -> dict[str, str]:
    """Return per-dependency readiness as ``ok`` or ``unavailable``.

    Credentials and connection strings are deliberately excluded.
    """
    report: dict[str, str] = {
        "postgres": "ok" if check_postgres(settings.database_url) else "unavailable"
    }
    report["redis"] = "ok" if check_redis(settings.redis_url) else "unavailable"
    if settings.kafka_enabled:
        report["kafka"] = (
            "ok" if check_kafka(settings.kafka_bootstrap_servers) else "unavailable"
        )
    return report


def is_ready(report: dict[str, str]) -> bool:
    """Return True only when every checked dependency reported ``ok``."""
    return all(status == "ok" for status in report.values())
