# Phase 13 — Neo4j + Graph-Based Fraud Relationship Analysis

## Overview

Phase 13 adds a **relationship-analysis read model** to the Fraud service using
Neo4j. The deterministic rules (Phase 10) and the ML model (Phase 12) remain the
foundation; the graph contributes one additional, deterministic risk signal.

Nothing about the event contracts changed: `pybank.events`, `transfer.completed`
and `risk.assessed` keep the same schema, the outbox pattern and the idempotency
design are untouched, and the Banking service still never imports or calls Neo4j.

## Architectural principle: PostgreSQL vs Neo4j

| Store | Role | Authority |
|---|---|---|
| PostgreSQL (banking) | Customers, accounts, balances, transfers, outbox | **Source of truth** |
| PostgreSQL (fraud) | `fraud_assessments`, `processed_events`, outbox | **Source of truth** |
| Kafka | Event transport (`pybank.events`) | Transport only |
| **Neo4j** | Relationship projection of accounts/transactions | **Derived read model** |

Neo4j is **never** the ledger. It is a projection rebuilt from Kafka events. If
Neo4j is lost, the banking ledger and every fraud assessment remain correct; only
the graph enrichment is temporarily unavailable.

## Runtime architecture

```
                    ┌────────────────┐
                    │ Banking Service│
                    └───────┬────────┘
                            │ transfer.completed
                            ▼
                         Kafka
                      (pybank.events)
                            │
                            ▼
                   ┌─────────────────┐
                   │ Fraud Service   │
                   └────────┬────────┘
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
  PostgreSQL            ML model             Neo4j
  (authority)       (fraud-model-v1)     (read model)
        │                   │                    │
        └───────────────────┼────────────────────┘
                            ▼
               rule_score + ml_probability  → combined_score
                            +
                    graph_score → graph_adjustment
                            ▼
                       final_score
                     LOW / MEDIUM / HIGH
                            ▼
                    fraud_assessments
                            ▼
              outbox → risk.assessed (Kafka)
```

## Graph data model

Deliberately small — only entities that existing event payloads can provide.

Nodes:

| Label | Key property | Source |
|---|---|---|
| `Customer` | `customer_id` | `transfer.completed` payload |
| `Account` | `account_id` | `transfer.completed` payload |
| `Transaction` | `transaction_id` | `transfer.completed` payload |

Relationships:

| Relationship | Direction | Meaning |
|---|---|---|
| `OWNS` | `(:Customer)-[:OWNS]->(:Account)` | account ownership |
| `SENT` | `(:Account)-[:SENT]->(:Transaction)` | source side of a transfer |
| `RECEIVED_BY` | `(:Transaction)-[:RECEIVED_BY]->(:Account)` | destination side |

```
Customer A ──OWNS──▶ Account A ──SENT──▶ Transaction T1 ──RECEIVED_BY──▶ Account B
                                                                             ▲
Customer C ──OWNS──▶ Account C ──SENT──▶ Transaction T2 ──RECEIVED_BY────────┘
```

Account B is the shared destination of two different sources — the pattern the
`SHARED_BENEFICIARY` signal detects.

No `Device`, `IP`, `Location` or `Merchant` nodes were added: no existing event
payload carries reliable data for them. This is a documented limitation.

## Kafka → Fraud → Neo4j flow

For each `transfer.completed`:

1. Idempotency check against `processed_events` (Phase 10 behaviour, unchanged).
2. Deterministic rules + ML prediction → `combined_score` (Phase 12, unchanged).
3. **Project** the transfer into Neo4j with `MERGE` on business identifiers.
4. **Analyse** the bounded relationship queries (lookback window).
5. `graph_score` → `graph_adjustment` → `final_score` → risk level.
6. Persist the assessment (+ graph columns) and enqueue `risk.assessed`.
7. Commit the Kafka offset using the existing commit semantics.

There is **no distributed transaction** across Kafka, PostgreSQL and Neo4j. The
design stays at-least-once + idempotency; Neo4j writes are idempotent `MERGE`s.

## Graph projection idempotency

Every write merges on stable business ids:

- `Customer.customer_id`, `Account.account_id`, `Transaction.transaction_id`
  have uniqueness constraints.
- `MERGE` is used for nodes, `OWNS`, `SENT` and `RECEIVED_BY` relationships.
- `Transaction` properties are set with `ON CREATE SET`, so a replay cannot
  rewrite history or create a second node/relationship.

Replaying the same `transfer.completed` event therefore leaves exactly one
`Transaction` node and one `SENT` relationship (verified in the E2E run).

## Graph fraud signals

Three bounded, deterministic Cypher queries (parameterised, no interpolation):

| Query | Question | Returns |
|---|---|---|
| `SHARED_BENEFICIARY` | How many distinct sources recently sent to this destination? | one integer |
| `TWO_HOP` | Does the destination send money onward recently? | one integer |
| `RELATIONSHIP_COUNT` | How many distinct accounts did the source interact with? | one integer |

All queries filter on `Transaction.created_ts` using an epoch-seconds lookback
(`GRAPH_LOOKBACK_HOURS`, default 24) and match on a specific account id, so they
never scan the whole graph. None uses unbounded variable-length traversal.

Transparent deterministic scoring (`fraud-graph-v1`):

| Evidence | Contribution |
|---|---|
| `SHARED_BENEFICIARY` (≥ 2 sources) | 0.4 (+0.1 per extra source, capped 0.6) |
| `MULTI_HOP_CONNECTION` (onward transfer) | 0.3 |
| `HIGH_RELATIONSHIP_COUNT` (≥ 5 counterparties) | 0.2 |
| No suspicious relationship | 0.0 |

`graph_score = min(1.0, sum of contributions)`. These are **educational
heuristics**, not proven fraud indicators.

## Score composition (Phase 12 baseline preserved)

```
combined_score   = 0.6 * rule_score + 0.4 * ml_probability   # unchanged Phase 12
graph_adjustment = min(GRAPH_MAX_ADJUSTMENT, GRAPH_WEIGHT * graph_score)
final_score      = min(1.0, combined_score + graph_adjustment)
risk_level       = LOW (<0.30) / MEDIUM (0.30–<0.70) / HIGH (>=0.70) on final_score
```

Defaults: `GRAPH_WEIGHT=0.25`, `GRAPH_MAX_ADJUSTMENT=0.15`. Both configurable.
`combined_score` keeps meaning *only* the rule + ML baseline, and `risk_score`
still stores that baseline; `final_score` is the new authoritative number, so the
graph contribution is always separately observable.

## Failure behavior

Neo4j is an **advisory** dependency:

| Situation | Behavior |
|---|---|
| Neo4j reachable | projection + analysis run, `graph_score` contributes |
| Neo4j unreachable | `graph_score = 0.0`, `graph_adjustment = 0.0`, assessment completes on rule + ML |
| Projection invalid (bad Cypher, schema) | same neutral fallback; logged + counted |
| Model artifact missing/invalid | Fraud service **fails fast at startup** (Phase 12 behaviour) |

Failures are never swallowed: each emits a structured log
(`fraud_graph_unavailable`, `fraud_graph_projection_failed`) and increments
`fraud_graph_failures_total{operation=...}` plus
`fraud_graph_projection_total{result="failure"}`.

Banking is asynchronous and unaffected: a Fraud or graph failure can never roll
back a completed transfer.

## Readiness decision

| Probe | Banking | Fraud |
|---|---|---|
| `/health` (liveness) | 200 always | 200 always |
| `/ready` (baseline) | postgres, redis, kafka | postgres, kafka |
| Neo4j | not checked | reported as `neo4j: ok/unavailable`, **never gates** |

Neo4j is reported in `/ready` for visibility but deliberately excluded from
`REQUIRED_DEPENDENCIES`, because Phase 13 requires graceful degradation. Making
it mandatory would turn a graph outage into a fraud outage, which is the opposite
of the intended design.

## Observability

Reuses the Phase 11 stack — no second logging/metrics/tracing system.

- Logs: `graph_score`, `graph_adjustment`, `final_score`, `graph_version`,
  `graph_available`, plus the existing `correlation_id`, `event_id`,
  `transaction_id`.
- Metrics (bounded, no id labels):
  `fraud_graph_queries_total{operation,result}`,
  `fraud_graph_failures_total{operation}`,
  `fraud_graph_projection_total{result}`,
  `fraud_graph_risk_signals_total{signal_type}`.
  Labels are `operation`, `result`, `signal_type` only — never `transaction_id`,
  `account_id`, `customer_id` or `event_id`.

## Neo4j infrastructure

| Setting | Value |
|---|---|
| Image | `neo4j:5.26-community` (pinned; no Enterprise-only features) |
| Auth | `NEO4J_AUTH` from `NEO4J_PASSWORD` (env-backed, never hardcoded) |
| Driver dependency | `neo4j>=5.25,<6.0` (installed 5.28.6) |
| Volume | named `pybank_neo4j_data` (persistent) |
| Ports | `7474` (Browser), `7687` (Bolt) — local learning only |
| Healthcheck | `cypher-shell ... 'RETURN 1'`, credentials parsed from `NEO4J_AUTH` |
| Memory | `NEO4J_server_memory_heap_max__size=512M`, pagecache `256M` |
| Compose dependency | `neo4j: condition: service_healthy, required: false` |

`required: false` is what makes graceful degradation real: Compose never refuses
to start Fraud when Neo4j is absent or unhealthy.

## Constraints and indexes

```cypher
CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
  FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE;
CREATE CONSTRAINT account_id_unique IF NOT EXISTS
  FOR (a:Account) REQUIRE a.account_id IS UNIQUE;
CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS
  FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE;
```

Created once per driver lifetime by `GraphClient.ensure_schema()`, which runs
before the first projection. There is no endpoint that accepts arbitrary Cypher —
queries live only in `graph/queries.py`.

## Database migration

`d5e6f7a8b9c0_add_graph_scoring_columns.py` additively adds nullable columns:
`graph_score`, `graph_adjustment`, `final_score`, `graph_signals` (JSON),
`graph_version`. Existing rows stay readable with `NULL` graph fields.

## Component map

| Component | Location |
|---|---|
| Cypher queries | `services/fraud/graph/queries.py` |
| Driver lifecycle | `services/fraud/graph/client.py` |
| Projection + bounded reads | `services/fraud/graph/repository.py` |
| Deterministic scoring | `services/fraud/graph/risk.py` |
| Consumer integration | `services/fraud/app/infrastructure/kafka_consumer.py` |
| Startup driver wiring | `services/fraud/app/main.py` |
| Neo4j service | `compose.yaml` (`neo4j`) |

## Future improvements (out of Phase 13 scope)

Neo4j Graph Data Science, graph embeddings, GNNs, PageRank / community detection,
Kafka Connect / Debezium graph ETL, a separate graph microservice, frontend graph
visualisation, and online model retraining were all intentionally excluded. They
belong to later phases, not to this one.
