# Phase 11 Architecture - Observability

Phase 11 keeps the Phase 9/10 runtime topology and adds production-style
observability without changing service boundaries.

```text
Browser -> Frontend -> Banking API -> PostgreSQL (source of truth)
                          |  \
                          |   -> Redis (cache / rate limits)
                          |  \
                          |   -> Kafka pybank.events (async transport only)
                          |        -> Fraud consumer -> fraud_assessments
                          |        -> Fraud outbox -> risk.assessed -> pybank.events
                          |
                          +-> Prometheus /metrics (banking + fraud)
                          +-> Grafana dashboard (provisioned)
                          +-> Jaeger traces over OTLP/HTTP
```

## Single shared topic

Both `transfer.completed` and `risk.assessed` travel on `pybank.events`.
The event type lives in the envelope (`event_type`), not in the topic name.
The Fraud service consumes `transfer.completed` and publishes `risk.assessed`
on the same topic through its own transactional outbox.

## Correlation and tracing

- HTTP uses `X-Correlation-ID`. Missing values generate a UUID4.
- Banking persists `correlation_id` and `traceparent` on each outbox row.
- Kafka records carry them as two separate UTF-8 headers:
  `correlation_id` and `traceparent`.
- Fraud binds the incoming `correlation_id` to its logging context, stores it
  on `fraud_assessments`, and forwards both headers on `risk.assessed`.
- OpenTelemetry exports HTTP and application spans to Jaeger over OTLP/HTTP.
  The async Kafka hand-off continues trace context but is not one continuous
  HTTP request span.

## Health model

- `/health` is liveness only and stays 200 when dependencies are down.
- `/ready` checks real dependencies with bounded timeouts:
  Banking checks PostgreSQL, Redis, and Kafka; Fraud checks PostgreSQL and
  Kafka. Responses contain only `ok`/`unavailable`, never credentials.
- `/metrics` exposes Prometheus counters/gauges with bounded labels only.

## Verification

See `docs/verification/phase-11.md` for runtime evidence.
