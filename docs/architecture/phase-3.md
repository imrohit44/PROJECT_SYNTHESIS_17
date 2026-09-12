# Phase 3 Architecture

## Persistence architecture

```text
Client
  |
  v
FastAPI API adapter
  |
  v
BankApplicationService
  |
  +--> Domain entities and TransferService
  |
  `--> SQLAlchemy session
          |
          v
      Persistence models and mappers
          |
          v
      PostgreSQL
```

## Domain versus persistence

The domain remains under `backend/app/domain` and imports no SQLAlchemy, PostgreSQL driver, FastAPI, or Alembic code. `Customer`, `Account`, and `Transaction` remain behavior-focused entities.

The persistence layer under `backend/app/infrastructure/persistence` contains `CustomerModel`, `AccountModel`, and `TransactionModel`. Mappers convert rows to domain entities and never return ORM objects to the API or domain.

This separation protects the domain from schema changes and prevents database sessions from leaking into business objects. The alternative would be active-record-style entities, which is shorter initially but couples business behavior to one ORM and makes domain tests slower and less portable.

## Relational schema

```text
customers
---------
id PK
name NOT NULL
email NOT NULL UNIQUE
phone
created_at
updated_at
        |
        | 1-to-many
        v
accounts
--------
id PK
customer_id FK -> customers.id
account_type: savings | current
balance NUMERIC(18,2)
status: active | frozen | closed
interest_rate
minimum_balance
overdraft_limit
created_at
updated_at
        |
        | 1-to-many
        v
transactions
------------
id PK
account_id FK -> accounts.id
transaction_type
status
amount NUMERIC(18,2)
source_account_id FK -> accounts.id
destination_account_id FK -> accounts.id
timestamp
```

A single accounts table represents both account types. `account_type` selects the domain subtype and specialized columns remain nullable when irrelevant. This is simpler than joined-table inheritance for the current small model and demonstrates that object inheritance does not need to become relational inheritance.

`accounts.balance` is current state. `transactions` are historical records. This is not event sourcing; a future ledger design would need stronger accounting semantics.

## Transactions and concurrency

Deposits and withdrawals use one SQLAlchemy transaction, lock the account row with `SELECT ... FOR UPDATE`, apply domain rules, update the balance, and insert the transaction record. Transfers lock both account rows in sorted identifier order, validate both domain objects, update both balances, insert both transaction records, and commit as one unit.

If validation or persistence fails, the session context rolls back all changes. PostgreSQL row locks prevent two concurrent writes to the same account from both using the same stale balance. Deterministic lock ordering reduces deadlock risk when two transfers involve the same pair in opposite directions.

SQLite integration tests validate behavior, but SQLite does not provide PostgreSQL's row-lock semantics. Live PostgreSQL concurrency verification requires a configured PostgreSQL server.

## Sessions and migrations

`create_session_factory` creates a pooled SQLAlchemy engine with `pool_pre_ping=True`. Each application operation opens a short-lived session and closes it through the context manager. No global session is shared between requests.

Alembic owns schema history. `alembic upgrade head` creates the schema, and `alembic downgrade base` removes it. The initial migration is the reproducible source of the database structure.

## Constraints and indexes

Application/domain validation provides useful user-facing errors. Database constraints provide a second line of defense against bugs or alternate writers. The schema constrains foreign keys, allowed account types/statuses, non-negative savings balances, and positive transaction amounts.

Indexes exist for customer lookup, transaction account lookup, source/destination account lookup, and transaction time queries. They improve reads but consume storage and make writes more expensive, so unrelated columns are not indexed.
