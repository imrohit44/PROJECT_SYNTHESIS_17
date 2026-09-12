# Learning Guide: Phase 3

## 1. Relational databases

A relational database stores structured records in tables and connects them with keys. PostgreSQL provides durable storage, constraints, transactions, concurrency control, and query capabilities that an in-memory dictionary cannot provide.

## 2. SQLAlchemy and the ORM

SQLAlchemy is a Python toolkit for SQL and object-relational mapping. Its ORM maps Python persistence models to tables while still allowing explicit transaction and query control. It is not the domain model.

## 3. Domain model versus persistence model

Domain entities express behavior and business invariants. Persistence models express columns, foreign keys, indexes, and database constraints. Separating them prevents SQLAlchemy details from contaminating the framework-independent domain.

## 4. Repository and application boundary

Phase 3 uses `BankApplicationService` as the application boundary because the current API needs coordinated persistence operations. It opens sessions, maps rows, invokes domain behavior, and persists results. A larger repository interface hierarchy was deliberately not added yet; repositories become valuable when multiple persistence implementations or independently testable aggregate stores are needed.

## 5. Database transactions and ACID

A database transaction groups operations into one unit. ACID means atomicity, consistency, isolation, and durability. A transfer either debits, credits, and records both sides, or none of those changes commit.

## 6. Atomicity

Atomicity prevents partial transfers. The SQLAlchemy context manager commits on success and rolls back when an exception escapes. This is stronger than simply calling two domain methods one after another.

## 7. Isolation and concurrency

Two withdrawals must not both spend the same balance. PostgreSQL row locks acquired with `SELECT FOR UPDATE` serialize writes to the affected account rows. Transfers lock both rows in deterministic order to reduce deadlocks.

## 8. Connection pooling

An engine manages a pool of database connections. Reusing connections is faster than opening a new network connection for every request. `pool_pre_ping` discards stale connections before use.

## 9. Constraints

Constraints are database-enforced rules such as foreign keys, unique email, positive transaction amounts, and allowed status values. Application validation gives friendly errors, while constraints protect data when code paths change or another writer appears.

## 10. Indexes

An index is an additional lookup structure. It makes common reads faster, such as finding an account's transactions, but increases storage and write cost. PyBank adds only indexes justified by current queries.

## 11. Alembic migrations

Alembic records schema changes as versioned Python migrations. `alembic upgrade head` applies all migrations; `alembic downgrade base` reverses them. This makes a database reproducible instead of relying on a developer manually creating tables.

## 12. Object-relational impedance mismatch

Objects support inheritance, identity, and behavior; relational tables support rows, columns, and relationships. PyBank uses one accounts table with an `account_type` discriminator rather than forcing the Python inheritance tree into multiple tables. Mappers handle the translation.

## 13. Failure boundaries

A domain exception is a business failure. `IntegrityError` is a persistence failure. The API maps both to stable responses without exposing SQL, connection strings, or stack traces. The session rollback is what prevents a failed operation from leaving partial state.

## 14. Current limitation

The implementation is PostgreSQL-first, but local automated tests use isolated SQLite files because this machine does not have a PostgreSQL server configured. SQLite proves mapping and transaction behavior, not PostgreSQL-specific locking. A real Phase 3 environment must run the Alembic migration against PostgreSQL and exercise concurrency there.
