# Phase 13 Learning Notes — Graph-Based Fraud Relationship Analysis

Neo4j is the fourth lens on the same fraud problem. Phase 10 asks "does this
transfer look suspicious on its own?", Phase 12 asks "does it resemble past
fraud?", and Phase 13 asks "does it connect to other suspicious transfers?".

## 1. What is a graph database?

A database that stores **nodes** (things) and **relationships** (connections
between things) as first-class structures. Traversing a relationship is a
pointer hop, not a join — the database is organised around connectivity
rather than around tables.

## 2. Why PostgreSQL is good for banking records

Balances, transfers and assessments need ACID guarantees, exact aggregates
and auditability. A relational row is the natural unit: one transfer is one
row, one balance update is one atomic commit. Nothing in Phase 13 changes
that — the ledger stays in PostgreSQL.

## 3. Why relationship analysis can be easier in Neo4j

"Which accounts feed the same destination, and where does the money go
next?" is a multi-hop traversal. In SQL each hop is another self-join over
the transfers table and the query grows with the number of hops. In Cypher
the same question reads almost like the sentence itself:
`(src:Account)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(dst)`. We do **not**
claim Neo4j is universally faster or better — it is a specialised tool that
makes connected-data queries more natural to express.

## 4. What nodes are

Our graph has three labels, all derived from existing `transfer.completed`
payloads: `Customer` (keyed by `customer_id`), `Account` (keyed by
`account_id`) and `Transaction` (keyed by `transaction_id`). No Device, IP or
Merchant nodes — the event contracts do not carry that data, and inventing
it would be dishonest.

## 5. What relationships are

Three typed edges mirror the money flow:
`(:Customer)-[:OWNS]->(:Account)`, `(:Account)-[:SENT]->(:Transaction)` and
`(:Transaction)-[:RECEIVED_BY]->(:Account)`. The edge types are part of the
schema: every query names them explicitly, so traversals can never wander
into unrelated data.

## 6. What Cypher is

Neo4j's declarative query language. You draw the pattern you want with ASCII
art — `(a:Account)-[:SENT]->(t:Transaction)` — and add `WHERE`, `WITH` and
`RETURN` clauses. All of our queries live in `services/fraud/graph/queries.py`
and use parameters only; there is deliberately no endpoint that accepts
arbitrary Cypher from users.

## 7. Why MERGE is important

`MERGE` means "match this pattern or create it". Kafka is at-least-once, so
the same event can be delivered twice; because every write is keyed on the
stable business id (`transaction_id`, `account_id`), a replayed event
matches the existing nodes and relationships instead of duplicating them.
Idempotency in the graph comes from the data model, not from extra code.

## 8. What graph projection means

Projection is copying facts that already exist (in Kafka events) into a
different *shape* — rows become nodes and edges. Neo4j holds no original
data; if it were wiped, every relationship could be rebuilt by replaying
`transfer.completed`. That is why it is a read model, not a ledger.

## 9. What fraud patterns graphs can reveal

Single transfers look innocent; networks look suspicious. Our three
deterministic queries target exactly that: **shared beneficiary** (several
unrelated sources feeding one destination — classic money-mule shape),
**two-hop chains** (money arriving and immediately leaving — pass-through
behaviour) and **relationship count** (an account suddenly touching many
counterparties). These are educational heuristics, not proven indicators.

## 10. Why graph analysis complements ML rather than replacing it

Rules see one transfer, ML sees resemblance to past fraud, the graph sees
connections between transfers. Each lens misses what the others catch: a
small, ML-clean transfer into a shared mule account is invisible to Phases
10–12 but visible to Phase 13. The pipeline therefore *adds* signals
(`combined_score` stays the rule+ML baseline; the graph only contributes a
bounded `graph_adjustment`) instead of letting any one signal overrule the
rest.

## 11. Why Neo4j is not the financial source of truth

The graph has no balances, no constraints on money movement, and no
participation in the banking transaction. Treating it as authoritative
would mean two ledgers that can disagree. One ledger (PostgreSQL), one
lens (Neo4j) — that separation is the whole design.

## 12. Why graph failure must degrade gracefully

The graph is an enrichment, not a prerequisite. If Neo4j is down, blocking
assessments would turn an analytical outage into a fraud-processing outage
and, through backpressure, a banking outage. So the consumer catches the
failure, records `graph_available=false` with `graph_score=0.0`, emits a
metric, and completes the rule+ML assessment. A missing lens dims the
picture; it must never stop the camera.

## Real-world example

```
Customer A ──OWNS──▶ Account A ──SENT──▶ Transaction T1 ──RECEIVED_BY──▶┐
                                                                       │
                                                              Account X │
                                                                       │
Customer B ──OWNS──▶ Account B ──SENT──▶ Transaction T2 ──RECEIVED_BY──▶┘
```

Viewed as rows, T1 and T2 are two ordinary transfers. Viewed as a graph,
Account X has **two distinct source accounts** — the `SHARED_BENEFICIARY`
signal. One shared destination might be a landlord collecting rent; three
unrelated sources at 2 a.m. deserve a closer look. The graph does not decide
which it is — it contributes up to `GRAPH_MAX_ADJUSTMENT` (0.15) to the
final score and leaves the verdict to the thresholds.
