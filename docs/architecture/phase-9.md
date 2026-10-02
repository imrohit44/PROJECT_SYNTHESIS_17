# Phase 9 Architecture - Kafka and Transactional Outbox

Kafka is introduced as event transport. PostgreSQL remains authoritative for
balances, accounts, customers, transactions, transfers, and the outbox.

```text
HTTP request
  |
  v
Banking application service
  |
  | one PostgreSQL transaction
  v
balances/transactions + outbox_events
  |
  v
background outbox publisher
  |
  v
Kafka topic: pybank.events
  |
  v
audit consumer group: pybank-audit-consumer
  |
  v
processed_events
```

## Deployment

Compose runs one local Kafka broker in KRaft mode using `apache/kafka:3.9.1`.
ZooKeeper is not used. The backend connects to `kafka:9092` on the private
Compose network.

## Event Topic

Project Synthesis 17 uses one topic:

```text
pybank.events
```

The event type is inside the envelope. This keeps Phase 9 small and makes topic
inspection easier.

## Envelope

Each event contains:

- `event_id`
- `event_type`
- `schema_version`
- `occurred_at`
- `aggregate_type`
- `aggregate_id`
- `payload`

Events are JSON. They do not include passwords, password hashes, tokens, or
secrets.

## Outbox

`outbox_events` stores pending and published events. Pending means
`published_at IS NULL`. Published means `published_at IS NOT NULL`.

The banking mutation and outbox insert share one database transaction. If Kafka
is down, the API can still succeed and the durable outbox row remains pending.

## Publisher

The backend starts a single background publisher when `KAFKA_ENABLED=true`. It:

1. Reads unpublished outbox rows.
2. Publishes JSON events to Kafka.
3. Marks rows as published after broker acknowledgement.
4. Records attempt count and last error on failure.

This is at-least-once delivery. If publishing succeeds but the app crashes before
marking the row published, the event may be sent again.

## Consumer

The audit consumer uses consumer group `pybank-audit-consumer`. It records
processed event IDs in `processed_events`, so duplicate deliveries are ignored.

Kafka offsets record where the consumer group is in the topic. Offsets are
committed only after processing.

## Ordering

The publisher uses `aggregate_id` as the Kafka message key. Kafka preserves order
within a partition, not globally across all partitions.

## Verification

Run:

```powershell
.\docker\event-flow-check.ps1
.\docker\kafka-failure-recovery-check.ps1
.\docker\duplicate-event-check.ps1
```

It creates accounts, performs a transfer, verifies balances, checks the transfer
outbox row is published, and checks the audit consumer recorded the event ID.
