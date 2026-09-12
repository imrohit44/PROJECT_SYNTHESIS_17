# Phase 0 Architecture

## Current architecture

```text
Client
  |
  v
FastAPI application
  |
  v
Versioned API router (/api/v1)
  |
  v
Health endpoint (/health)
```

The application is currently a small modular monolith. `backend/app/main.py` creates the FastAPI application, the versioned router owns HTTP route registration, and the health module owns the liveness behavior. Configuration and logging are kept in `core` so the application entrypoint does not become a collection of unrelated concerns.

## Why this boundary exists

- `backend/app`: application code, packaged independently from documentation and tests.
- `api/v1`: the public HTTP contract. New endpoints can be grouped by resource without changing the application entrypoint.
- `core`: cross-cutting concerns used by multiple modules, currently settings and logging.
- `backend/tests`: executable proof that the application contract works.

## Future direction (not implemented)

```text
React frontend (not implemented)
  |
  v
API gateway (not implemented)
  |
  v
Backend services (not implemented)
  |
  +--> PostgreSQL / Redis (not implemented)
  |
  v
Kafka (not implemented)
  |
  v
Supporting services (not implemented)
  |
  +--> ML / Neo4j / AI agents (not implemented)
```

The future architecture will be reached incrementally. Phase 0 intentionally does not add databases, caches, brokers, service boundaries, authentication, frontend code, containers, or cloud resources.

## Liveness and readiness

The current health endpoint is a liveness check: it shows that the process can answer HTTP requests. Readiness is different: a later readiness check will verify that dependencies required to serve traffic are available, such as a database. There are no such dependencies in Phase 0, so readiness is intentionally not implemented.
