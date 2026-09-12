# Phase 2 Architecture

## API boundary

```text
Client
  |
  v
FastAPI application
  |
  v
Versioned router (/api/v1)
  |
  v
Pydantic request/response schemas
  |
  v
API adapter and serializers
  |
  v
Domain
  |
  +--> Bank
  +--> Account
  +--> Transaction
  `--> TransferService
```

## Responsibility boundary

```text
HTTP layer
-----------
FastAPI
Pydantic schemas
HTTP status codes
API error responses
Dependency resolution

Domain layer
------------
Customer
Account
SavingsAccount
CurrentAccount
Transaction
Bank
TransferService
Business invariants
```

Routes translate HTTP into domain calls. They do not modify balances, implement overdraft rules, or decide whether a transfer is valid. Domain exceptions remain unaware of HTTP; the API error handlers map them to stable error codes and status codes.

## API components

- `schemas.py` defines external request and response contracts. These are deliberately separate from domain entities so the HTTP format can evolve independently.
- `serializers.py` converts domain objects into response models and formats money as two-decimal strings.
- `dependencies.py` exposes one cached `Bank` instance for the process. This is intentionally simple and can later be replaced by a persistence-backed dependency.
- `errors.py` translates domain failures and validation failures into a consistent error envelope.
- The routers group customers, accounts, and transfers without creating a large route module.

## In-memory state

The application currently stores all customers, accounts, and transactions in one process-local `Bank` instance. Restarting Uvicorn erases this state. This is expected in Phase 2. Phase 3 will introduce PostgreSQL and durable transactions; it should preserve the API/domain boundary rather than make the domain depend on SQLAlchemy.

## Testing boundary

Domain tests prove business rules directly and quickly. API tests prove HTTP paths, schemas, status codes, error envelopes, and serialization. API tests intentionally cover representative flows instead of duplicating every domain invariant.
