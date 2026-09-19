"""Phase 11 observability: correlation ids, JSON logs, metrics, readiness."""

from __future__ import annotations

import json
import uuid

import pytest
import structlog
from fastapi.testclient import TestClient

from services.common.observability import (
    CORRELATION_ID_HEADER,
    configure_structlog,
)


def test_correlation_id_generated_when_absent(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    uuid.UUID(response.headers[CORRELATION_ID_HEADER])


def test_correlation_id_preserved_and_returned(client: TestClient) -> None:
    supplied = f"test-correlation-{uuid.uuid4().hex[:8]}"
    response = client.get("/health", headers={CORRELATION_ID_HEADER: supplied})
    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == supplied


def test_health_is_liveness_even_when_dependencies_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.app.main.readiness_report",
        lambda _settings: {"postgres": "down", "redis": "down", "kafka": "down"},
    )
    assert client.get("/health").status_code == 200


def test_ready_returns_503_on_dependency_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.app.main.readiness_report",
        lambda _settings: {
            "postgres": "ok",
            "redis": "ok",
            "kafka": "unavailable",
        },
    )
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "kafka" in response.json()["dependencies"]


def test_ready_returns_200_when_dependencies_up(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.app.main.readiness_report",
        lambda _settings: {"postgres": "ok", "redis": "ok", "kafka": "ok"},
    )
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_exposes_no_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.app.main.readiness_report",
        lambda _settings: {"postgres": "ok", "redis": "ok", "kafka": "ok"},
    )
    body = client.get("/ready").text.lower()
    for secret in ("password", "secret", "jwt", "token"):
        assert secret not in body


def _latest_json_log_line(out: str, event: str) -> dict[str, object]:
    """Return the last JSON log line in captured stdout for the given event."""
    matches = [
        json.loads(line)
        for line in out.splitlines()
        if line.strip().startswith("{") and f'"{event}"' in line
    ]
    assert matches, f"expected a JSON log line for event {event!r} in: {out[-500:]}"
    line_value = matches[-1]
    assert isinstance(line_value, dict)
    return line_value


def test_structured_logs_are_valid_json_with_required_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_structlog("banking-test")
    structlog.get_logger("pybank.phase11.test").info("test_event")
    record = _latest_json_log_line(capsys.readouterr().out, "test_event")
    assert record["event"] == "test_event"
    assert record["service"] == "banking-test"
    assert record["level"] == "info"
    assert "timestamp" in record


def test_structured_logs_carry_no_secrets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_structlog("banking-test")
    structlog.get_logger("pybank.phase11.test").info("login attempt")
    record = _latest_json_log_line(capsys.readouterr().out, "login attempt")
    assert "password" not in json.dumps(record).lower()


def test_metrics_endpoint_exposes_expected_families(client: TestClient) -> None:
    client.get("/health")
    body = client.get("/metrics").text
    for family in (
        "http_requests_total",
        "http_request_duration_seconds",
        "transfers_total",
        "transfer_failures_total",
        "outbox_pending_events",
        "outbox_publish_failures_total",
    ):
        assert family in body


def test_metric_labels_are_bounded(client: TestClient) -> None:
    body = client.get("/metrics").text
    for forbidden in (
        "customer_id",
        "account_id",
        "transaction_id",
        "event_id",
        "correlation_id",
    ):
        assert f"{forbidden}=" not in body
