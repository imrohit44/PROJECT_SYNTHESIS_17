# Phase 11 Learning - Observability

Observability is the ability to answer questions about a running system without
adding new code to answer them. Three signals are usually enough: logs, metrics,
and traces.

## Why it matters for a bank

A transfer that silently fails, an outbox row that never publishes, or a login
endpoint that gets hammered are all invisible until someone measures them.
Observability turns "it feels slow" into "p99 transfer latency is 1.2 seconds and
the outbox has 400 pending rows".

## Structured logs

Plain text logs are written for humans. Structured logs are written for machines:
each line is JSON with fields such as `event`, `level`, `service`, `timestamp`
and `correlation_id`. A log pipeline can then filter and aggregate without
guessing with regular expressions.

structlog lets Project Synthesis 17 build that line from a processor chain instead of
hand-formatting strings.

Phase 11 runtime result: Banking and Fraud container application logs are pure
JSON objects; readiness responses contain only `ok`/`unavailable`.

## Correlation IDs

A correlation ID is one identifier attached to everything that belongs to the
same unit of work, such as one HTTP request. Project Synthesis 17 reads `X-Correlation-ID`,
generates a UUID when the client did not send one, puts it on the response, and
binds it to a context variable so background threads can log the same value.

The ID is not authorization and not identity. It is only a label that makes
searching logs possible. Anything a client supplies must still be validated.

Phase 11 runtime result: `phase11-final-test-398435e3` was preserved from the
Banking transfer response through `transfer.completed` Kafka headers into the
Fraud `fraud_assessments` row and onward in `risk.assessed` headers.

## Metrics

Prometheus-style metrics come in a few shapes:

- **Counter**: only goes up. Total requests, total failures.
- **Gauge**: goes up and down. Pending outbox rows, open connections.
- **Histogram**: buckets observations so you can compute latency percentiles.

Labels add dimensions (`method`, `route`, `status`). Every unique label
combination is a separate time series, which is why high-cardinality labels such
as raw URL paths with IDs inside them are dangerous.

Phase 11 runtime result: `transfers_total`, `fraud_events_consumed_total`,
`fraud_assessments_total`, `fraud_duplicate_events_total`,
`outbox_pending_events`, and `outbox_publish_failures_total` were scraped live,
and Prometheus reported `banking -> UP` and `fraud -> UP`.

## Pull, not push

Prometheus scrapes an HTTP endpoint (`/metrics`) instead of the app pushing
numbers somewhere. That means the application only has to expose state; the
monitoring system decides how often to look.

## Liveness and readiness

Liveness asks "is this process broken and should be restarted". Readiness asks
"should this instance receive traffic right now". A readiness probe that always
returns `ready` will not prevent traffic from reaching an instance whose
database is unreachable.

Phase 11 runtime result: stopping Redis made Banking `/health -> 200` and
`/ready -> 503`; restoring Redis returned `/ready -> 200`.

## Logs versus traces

A metric tells you something changed. Logs tell you what happened in one place. A
trace shows one request crossing service boundaries and where the time went, which
is why trace context usually travels in message headers - including Kafka record
headers.

Phase 11 runtime result: Jaeger contains Banking HTTP spans and Fraud
`fraud.risk_evaluation` spans, with separate W3C `traceparent` Kafka headers.

## Hygiene

Do not log secrets, tokens, passwords, or full request bodies. Project Synthesis 17's runtime
check verifies that synthetic credentials never appear in the container logs.
Correlation IDs supplied by a client should be length-limited and validated so
they cannot inject content into logs or response headers.

## What observability does not solve

Instrumentation does not fix bugs, does not create correctness, and does not
replace tests. Metrics that are declared but never updated are worse than no
metrics, because a dashboard that always shows zero looks healthy. Observability
only works when each signal is wired to the real code path and verified against
live traffic.