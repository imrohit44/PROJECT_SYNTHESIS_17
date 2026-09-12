# Learning Guide: Phase 2

## 1. What is a REST API?

A REST API exposes resources and operations through HTTP methods and URLs. PyBank uses `POST` to create or perform a state-changing operation and `GET` to retrieve customers, accounts, and transaction history.

## 2. What FastAPI does

FastAPI receives HTTP requests, selects route functions, validates input through Pydantic models, and generates OpenAPI documentation. It is the delivery mechanism for the domain, not the owner of banking rules.

## 3. What Pydantic does

Pydantic validates and parses request data into typed Python objects. In PyBank, it rejects arbitrary float money values at the API boundary and keeps request and response contracts explicit.

## 4. Request versus response schemas

A request schema describes what a client may send. A response schema describes what the API promises to return. Keeping them separate prevents internal domain fields and implementation details from accidentally becoming public API contracts.

## 5. API versioning

The `/api/v1` prefix gives the first public API contract a stable identity. A future breaking contract can be introduced as `/api/v2` while clients migrate.

## 6. HTTP status codes

- `201 Created`: a customer or account was created.
- `200 OK`: a resource was retrieved or an operation completed.
- `400 Bad Request`: the request violates a transfer rule such as same-account transfer.
- `404 Not Found`: the requested customer or account does not exist.
- `409 Conflict`: the request conflicts with current domain state, such as insufficient funds or a frozen account.
- `422 Unprocessable Content`: the request shape or amount representation is invalid.

## 7. Domain-to-HTTP exception mapping

A domain exception describes a business failure without knowing its delivery mechanism. The API layer maps `AccountNotFoundError` to a 404 error envelope and `InsufficientFundsError` to a 409 response. This keeps the domain reusable from scripts, jobs, tests, and future transports.

## 8. Why domain objects are not API schemas

Domain entities contain behavior, private state, and relationships. HTTP schemas are serialization contracts. Returning domain objects directly couples the public API to internal refactors and can expose fields that clients should not control.

## 9. Why business logic stays outside routes

A route should receive input, call the domain, map errors, and serialize output. If it checked overdrafts or edited balances directly, another caller could behave differently and the business rules would be duplicated.

## 10. Dependency injection

FastAPI injects the process-local `Bank` through `get_bank`. This is a small application dependency, not a custom dependency framework. Later, the same dependency boundary can provide a persistence-backed application service or repository composition.

## 11. In-memory application state

The cached bank exists only while the Python process runs. Restarting the server loses all data. The limitation is explicit rather than hidden behind a fake repository. PostgreSQL belongs to Phase 3.

## 12. API tests versus domain tests

Domain tests call entities and services directly to prove business rules. API tests call HTTP endpoints to prove routing, validation, serialization, status codes, and error envelopes. Keeping these suites distinct makes failures easier to diagnose and avoids repeating every rule through HTTP.

## 13. OpenAPI

FastAPI derives an OpenAPI document from route declarations and Pydantic models. Swagger UI at `/docs` lets another developer inspect request shapes, response models, and available endpoints without reading the implementation.

## Money representation

Clients send money as decimal strings, for example `{"amount": "1000.00"}`. Responses also use strings such as `"1000.00"`, which avoids JSON number ambiguity and preserves predictable two-decimal formatting. Float JSON values are rejected.
