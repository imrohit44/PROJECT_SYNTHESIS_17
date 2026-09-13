# Learning Guide: Phase 6

## What

Unit tests check small pieces in isolation, such as domain entities, money rules, password hashing, and token validation.

Integration tests check layers working together, such as FastAPI, application services, SQLAlchemy, and the database.

E2E tests check the full path from browser to React to FastAPI to PostgreSQL.

Coverage measures which code ran during tests. Linting catches style and common bug patterns. Formatting keeps code consistent. Type checking catches contract mistakes before runtime.

## Why

Future phases will add Docker, Redis, Kafka, microservices, ML, graphs, agents, and cloud infrastructure. Each addition increases the number of ways PyBank can break. Phase 6 creates fast feedback before that complexity arrives.

## Problem prevented

- Domain tests catch broken banking rules.
- Application tests catch orchestration mistakes.
- API tests catch contract regressions.
- Persistence tests catch constraint, transaction, and money storage issues.
- Security tests catch authentication, authorization, ownership, and leakage bugs.
- Frontend tests catch unsafe error display, broken auth flow, and stale server state.
- Static checks catch mistakes tests may not execute.

## Alternatives

One option is mostly unit tests. This is fast, but can miss database and API contract failures.

Another option is mostly E2E tests. This is realistic, but slow and brittle.

A third option is the pyramid used here: many fast unit tests, moderate integration tests, and a few high-value E2E tests.

## Trade-offs

Speed vs realism: unit tests are fast but less realistic; PostgreSQL and browser tests are slower but prove real integration.

Mocks vs real infrastructure: mocks are useful for external services and time/token boundaries. They should not replace the banking domain or PostgreSQL integration tests.

Coverage vs meaningful tests: 100 percent line coverage can still miss important bugs. Meaningful tests cover failure paths, security boundaries, ownership, rollback, and edge cases.

## Current strategy

Backend tests use pytest markers:

```powershell
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m security
```

Coverage:

```powershell
python -m pytest --cov=backend --cov-report=term-missing
```

Frontend tests:

```powershell
cd frontend
npm test
npm run test:coverage
```

Quality checks:

```powershell
ruff check .
ruff format --check .
python -m mypy backend
cd frontend
npm run lint
npm run typecheck
npm run build
```

## PostgreSQL tests

Set `PYBANK_TEST_DATABASE_URL` to a dedicated test database. Never point it at a personal or production database. The PostgreSQL fixture recreates the public schema for isolation and refuses URLs that are not clearly test-named.

## Future

Later phases can add:

- Dockerized test databases
- automated Playwright smoke tests
- CI/CD in Phase 16
- parallel tests
- API contract testing
- mutation testing
- performance checks for Redis and Kafka workflows

The lesson of Phase 6 is simple: tests should make change less scary.
