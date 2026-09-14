# Phase 9 Learning - Kafka and Events

Event-driven architecture means parts of the system communicate by recording and
reacting to facts that already happened.

Kafka is a broker. Producers write messages to topics. Consumers read messages
from topics. A topic can have partitions, and each consumer group tracks offsets
showing what it has processed.

## Why Kafka

PyBank uses Kafka to teach decoupling. A transfer can complete immediately in
PostgreSQL while audit processing happens later.

Kafka is not the banking ledger. PostgreSQL remains the source of truth.

## Dual-Write Problem

This is unsafe:

```text
commit database
publish Kafka event
```

If the app crashes between those steps, the database changed but the event is
lost. PyBank uses the transactional outbox pattern instead.

## Transactional Outbox

```text
begin transaction
  update balances
  insert transactions
  insert outbox event
commit
```

A background publisher later sends outbox events to Kafka.

## Delivery and Duplicates

PyBank treats Kafka delivery as at least once. Events may be delivered more than
once. Consumers must be idempotent.

The audit consumer stores processed `event_id` values in PostgreSQL. If the same
event arrives again, it is ignored.

## Eventual Consistency

Financial state is correct immediately after the PostgreSQL transaction commits.
Kafka consumers may process events seconds later. That delay is eventual
consistency.

## What Kafka Does Not Solve

Kafka does not replace PostgreSQL transactions, migrations, authorization,
security, or data modeling. It is not used for deposits, withdrawals, transfers,
or balances as source-of-truth state.
