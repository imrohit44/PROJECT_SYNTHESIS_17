# Phase 11 Verification Report

## Executive Summary

Phase 11 observability was verified against the live Compose stack on
2026-09-19. Banking and Fraud both report real readiness, and a real
authenticated transfer flows through PostgreSQL, the banking outbox, Kafka
`pybank.events`, the Fraud consumer, `fraud_assessments`, the Fraud outbox,
and back to Kafka as `risk.assessed` with the same correlation id.

## Quality Gates

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Backend tests | `pytest backend/tests -q` | PASS: 61 passed, 3 skipped | Run 2026-09-19; observability tests cover correlation, readiness, metrics, JSON logs |
| Backend lint | `ruff check .` | PASS | All checks passed |
| Backend format | `ruff format --check .` | PASS | 122 files already formatted |
| Backend types | `mypy .` | PASS | No issues in 77 source files |
| Fraud tests | `pytest services/fraud/tests -q` | PASS: 3 passed | Run 2026-09-19 |
| Fraud lint/format | `ruff check/format services/fraud` | PASS | All checks passed; 16 files formatted |
| Fraud types | `mypy --config-file services/fraud/mypy.ini services/fraud/app` | PASS | No issues in 12 source files |
| Frontend test/lint/typecheck/build | `npm run test/lint/typecheck/build` | PASS | 12 tests passed; 1713 modules built |

Note: plain `mypy services/fraud` is intentionally unsupported because the
repository-root config excludes that tree; the fraud config command above is
the supported check.

## Docker Runtime

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Build current source | `docker compose build backend fraud` | PASS | Rebuilt 2026-09-19 after CRLF entrypoint fix |
| Bring up stack | `docker compose up -d` | PASS | `artifacts/phase11/runtime/evidence.json` compose section |
| Nine services | `docker compose ps` | PASS | postgres/redis/kafka/banking/fraud/prometheus/grafana/jaeger/frontend Up/healthy |

Startup bugs fixed during verification: `.dockerignore` excluded
`infrastructure/` mounts, and both entrypoint scripts had CRLF endings causing
exit 255. Both were fixed without new architecture.

## Health and Readiness

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Banking `/health -> 200` | `GET :8000/health` | PASS | `{"status":"ok","service":"banking"}` |
| Banking `/ready -> 200` | `GET :8000/ready` | PASS | `postgres/redis/kafka: ok` |
| Fraud `/health -> 200` | `GET :8001/health` | PASS | `{"status":"ok","service":"fraud"}` |
| Fraud `/ready -> 200` | `GET :8001/ready` | PASS | `postgres/kafka: ok` |
| Redis down | `docker compose stop redis` | PASS | `/health -> 200`, `/ready -> 503` with `redis: unavailable` |
| Redis restored | `docker compose start redis` | PASS | `/ready -> 200` |
| No credentials | Scan `/ready` bodies | PASS | Only `ok`/`unavailable` |

## Correlation IDs

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Generated UUID when absent | `GET /health` without header | PASS | `X-Correlation-ID` parses as UUID |
| Exact custom preservation | `GET /health` with `phase11-final-test-001` | PASS | Exact echo in response header |
| Async preservation | Transfer with `phase11-final-test-398435e3` | PASS | Same value in transfer response, Kafka headers, fraud row, and `risk.assessed` |

## Kafka Propagation

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Separate transfer headers | Consume event `3472b69f...` | PASS | `correlation_id` and `traceparent` as separate UTF-8 headers |
| Separate risk headers | Consume event `d1d7e6b4...` | PASS | Same two-header shape with preserved correlation id |
| Schema v1 consumable | Inspect envelope | PASS | `schema_version 1`; older uncorrelated rows remain consumable |
| Shared topic | `pybank.events` | PASS | Both event types observed on one topic |

## End-to-End Banking to Fraud

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Authenticated transfer | `artifacts/phase11/tools/verify_e2e.py` | PASS: `E2E_OK` | `transaction b327c6e1-...`, assessment `3472b69f-...`, `risk_level LOW` |
| Fraud DB row | `psql pybank_fraud fraud_assessments` | PASS | Row contains event, transaction, `LOW`, and correlation id |
| Fraud outbox published | `psql pybank_fraud outbox_events` | PASS | `d1d7e6b4... risk.assessed published` |

## Idempotency

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Replay same event | Republish `3472b69f...` | PASS | `fraud_duplicate_event` logged with same correlation id |
| Exactly one assessment/processed row | Count by `event_id` | PASS | `1` assessment and `1` processed row |
| Duplicate metric | `fraud_duplicate_events_total` | PASS | Advanced `2.0 -> 3.0` |

## Failure Recovery

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Fraud down | Stop fraud, then transfer | PASS | Banking transfer `bafb6e3d-...` succeeded; event retained |
| Fraud restart | Start fraud | PASS | Assessment `LOW` created; `FRAUD_RECOVERY_OK` |
| Kafka down | Stop kafka, then transfer | PASS | DB committed (`balance 490.00`), pending outbox `2 -> 3` |
| Kafka restored | Start kafka | PASS | Pending drained `3 -> 2`; `KAFKA_RECOVERY_OK` |

## Prometheus

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Banking `/metrics` | `GET :8000/metrics` | PASS | `transfers_total 1.0`, `outbox_pending_events 0.0`, `outbox_publish_failures_total 0.0` |
| Fraud `/metrics` | `GET :8001/metrics` | PASS | `fraud_events_consumed_total 11.0`, `fraud_assessments_total LOW 8.0`, `fraud_duplicate_events_total 3.0` |
| Metrics move with events | E2E plus replay plus recovery | PASS | Assessment and duplicate counters advanced during verification |
| Bounded labels | Scan `/metrics` | PASS | No `customer_id/account_id/transaction_id/event_id/correlation_id` labels |
| Targets | `GET :9090/api/v1/targets` | PASS | `banking -> up`, `fraud -> up`, `prometheus -> up` |

## Grafana

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Reachable | `GET :3000/api/health` | PASS | `database ok`, version `11.5.1` |
| Datasource provisioned | `GET /api/datasources` | PASS | `uid pybank-prometheus`, `url http://prometheus:9090` |
| Dashboard provisioned | `GET /api/dashboards/uid/pybank-phase11` | PASS | Title `PyBank - Platform Observability`, 10 panels |
| Panels query real metrics | Dashboard JSON targets | PASS | Transfer, fraud, and outbox metric queries present |

## OpenTelemetry and Jaeger

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Real banking trace | `GET :16686/api/traces?service=banking` | PASS | HTTP spans such as `GET /api/v1/health`, `GET /metrics`, `GET /ready` |
| Real fraud spans | `GET :16686/api/traces?service=fraud` | PASS | `fraud.risk_evaluation` spans |
| traceparent through Kafka | Inspect Kafka headers | PASS | W3C `traceparent` present separately on both event types |

Async-trace limitation: the Kafka hand-off is proven by headers and DB rows;
retained Jaeger traces emphasize HTTP and Fraud evaluation spans rather than
one continuous transfer trace.

## Structured Logging

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Pure JSON app logs | `docker logs backend/fraud --tail` | PASS | Structlog lines parse as JSON with `timestamp/level/service/logger/event` and correlation fields where applicable |
| Secret scan | Search for `password/Authorization/Bearer/JWT/secret` | PASS | No sensitive authentication material found |

Alembic migration startup lines are outside structlog by design and are not
counted as application log lines.

## Security

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Readiness has no secrets | `/ready` bodies | PASS | Only status strings |
| Logs and evidence have no secrets | Container logs plus evidence JSON | PASS | IDs and statuses only |

## Repository Cleanliness

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| `git status` | Working tree review | PASS with note | Implementation is present in the working tree as required; raw runtime evidence is gitignored under `artifacts/phase11/` |
| Runtime evidence location | `artifacts/phase11/` | PASS | Evidence and tools under `artifacts/phase11/runtime` and `artifacts/phase11/tools`; `artifacts/` is gitignored |
| Root pollution | Repository root scan | PASS | Old root logs and temp DBs are staged as deletions; no new root logs added |

## Phase 0 to 10 Regression

| Requirement | Command/Test | Result | Evidence |
|---|---|---|---|
| Backend plus fraud plus frontend | Quality gates above | PASS | 61 backend tests, 3 fraud tests, 12 frontend tests; clean lint, types, and builds |

## Known Limitations

- Jaeger retention emphasizes HTTP and Fraud evaluation spans over one full
  async transfer trace.
- Kafka recovery drained pending rows from 3 to 2 because older verification
  rows remain queued.
- Supported fraud typecheck is `mypy --config-file services/fraud/mypy.ini
  services/fraud/app`, not `mypy services/fraud`.

## Final Verdict

🟢 COMPLETE

All required runtime and quality gates passed on the current working tree.
No new architecture was added and Phase 12 was not started.

