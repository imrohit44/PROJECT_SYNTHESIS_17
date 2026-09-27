# PyBank

## Overview

PyBank is a progressive software engineering learning project for building a production-inspired banking platform. The repository intentionally grows in stages so each technology is introduced when its problem is clear.

## Aim

The aim is to learn how a system evolves from a small, well-structured application into a secure, observable, distributed platform without skipping the engineering fundamentals.

## Objectives

- Build clear Python modules and boundaries.
- Learn API design, testing, configuration, and operational practices.
- Introduce infrastructure only when the application needs it.
- Document the reasoning behind important decisions.

## Learning philosophy

PyBank evolves through:

```text
Modular Monolith -> Production Backend -> Event-Driven Architecture
                 -> Microservices -> AI-Enabled Distributed System
```

Each phase should leave the previous phase understandable and runnable. Complexity is earned by a concrete requirement, not added for appearance.

## Current phase

**Phase 16 — CI/CD and Cloud (current)**

Phase 16 makes PyBank automatically tested, versioned, and deployable, and
deliberately adds no new runtime component, database, or Kafka cluster:

1. **CI pipeline** — `.github/workflows/ci.yml` runs on every push and pull
   request: backend pytest/Ruff/MyPy, fraud pytest/Ruff/MyPy, frontend
   ESLint/TypeScript/Vitest/production build, plus Compose validation and all
   three image builds.
2. **Immutable container release** — `docker-publish.yml` runs *only* after CI
   succeeds, builds the exact commit CI validated, and pushes
   `ghcr.io/imrohit44/pybank-{backend,fraud,frontend}:<commit-sha>`. `main` is
   also tagged for humans, but deployment never uses it.
3. **Cloud deployment** — `deploy-ec2.yml` deploys a published SHA over SSH to
   a single AWS EC2 host running Docker Compose, waits for `/health` and
   `/ready`, then smoke tests. `deploy/rollback.sh` restores a previous SHA
   using the same command, since releases are immutable.

The chain is enforced in executable workflow logic, not in comments:

```
push main → CI → [conclusion == success] → Publish → [conclusion == success] → Deploy
```

**Security properties.** In production (`docker-compose.prod.yml` layered over
`compose.yaml`) only Nginx on 80/443 is public. The two application services
bind `127.0.0.1`, and PostgreSQL, Redis, Kafka, Neo4j, Prometheus, Grafana,
Jaeger and the Fraud service publish **no** host port at all. Required
secrets use Compose's fail-fast syntax, so the stack refuses to start rather
than falling back to a development default. `docker compose down -v` appears
nowhere as an action, and `deploy.sh` aborts the deployment if it ever does.

**Local development is unaffected.** `docker compose up` still works exactly as
before; the production file is an overlay, not a replacement.

See `docs/architecture/phase-16.md`, `docs/learning/phase-16.md` and
`docs/verification/phase-16.md`.

**Phase 15 — Real-Time Communication**

Phase 15 adds three things and deliberately no new service, database, or
Kafka cluster:

1. **WebSocket real-time delivery** — `GET /api/v1/realtime/ticket` mints a
   single-use, short-lived ticket, and `WS /api/v1/ws` exchanges it for an
   authenticated connection. This keeps the JWT out of the URL, so credentials
   never land in proxy or browser history logs. A process-local connection
   manager fans messages out per user.
2. **Event-driven notifications** — a Kafka consumer inside the existing
   Banking service maps `transfer.completed` and `risk.assessed` onto
   channel-neutral notifications and dispatches them to WebSocket and WhatsApp
   adapters. Banking never pushes to a socket directly.
3. **Outbound WhatsApp adapter** — provider-agnostic, configuration-driven, and
   strictly outbound. Replies are never interpreted, so no WhatsApp message can
   move money. If it is unconfigured or failing, banking is unaffected and the
   failure is logged and counted.

The frontend gained `useRealtime()`: connection status, typed messages, bounded
reconnect backoff, and duplicate-connection prevention across re-renders. See
`docs/architecture/phase-15.md`, `docs/learning/phase-15.md` and
`docs/verification/phase-15.md`.

**Phase 11 - Observability (verified 2026-09-19)**

Phases 0 through 10 are complete. Phase 11 adds structlog JSON logging,
correlation IDs, Kafka `correlation_id` + `traceparent` headers,
OpenTelemetry/Jaeger tracing, Prometheus metrics, provisioned Grafana,
and real readiness checks. Runtime verification is documented in
`docs/verification/phase-11.md`.

**Phase 14 — LLM Banking Assistant**

Phase 14 adds an authenticated, read-only assistant (`POST
/api/v1/assistant/chat`): an LLM chooses among exactly four allowlisted tools
(`get_account_summary`, `get_recent_transactions`, `get_transaction_details`,
`get_fraud_assessment`), and the backend executes them against the JWT
principal through the existing service layer. The model never supplies
identity, never reaches a database directly, and cannot perform mutations.
Provider configuration is optional (`LLM_PROVIDER`/`LLM_API_KEY`); without it
the endpoint returns an explicit 503 while the rest of the API is unaffected.
See `docs/architecture/phase-14.md`, `docs/learning/phase-14.md` and
`docs/verification/phase-14.md`.

**Phase 13 - Neo4j + Graph Fraud Analysis**

Phase 13 projects `transfer.completed` events into a Neo4j Community 5.26
relationship graph (`Customer`/`Account`/`Transaction` nodes) and adds a
deterministic graph signal (`graph_score`, `graph_adjustment`, `final_score`,
`fraud-graph-v1`) alongside the Phase 12 rule + ML baseline. Neo4j is an
optional analytical projection: the Fraud assessment still completes with the
rule + ML result when the graph is unavailable. See
`docs/architecture/phase-13.md`, `docs/learning/phase-13.md` and
`docs/verification/phase-13.md`.

## Technology stack currently implemented

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic Settings
- Pydantic request/response schemas
- Versioned REST API
- SQLAlchemy 2
- PostgreSQL via psycopg
- Alembic migrations
- Argon2id password hashing
- JWT authentication
- Role-based authorization
- React + TypeScript
- Vite + Tailwind CSS
- React Router
- Axios
- TanStack React Query
- pytest, pytest-asyncio, and HTTPX
- pytest-cov
- Ruff
- MyPy configuration
- structlog JSON logging
- OpenTelemetry OTLP tracing
- Prometheus metrics
- Apache Kafka event transport
- Independent Fraud microservice
- WebSockets with single-use ticket authentication
- Event-driven notification channels (WebSocket, WhatsApp)
- Jaeger, Prometheus, and Grafana observability stack

Future technologies are roadmap items, not current dependencies.

## Getting started

### 1. Create a virtual environment

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
```

On macOS or Linux, activate with `source .venv/bin/activate`.

### 2. Install dependencies

```powershell
python -m pip install -e ".[dev]"
```

### 3. Configure local settings

```powershell
Copy-Item .env.example .env
```

Edit `.env` with a local PostgreSQL `DATABASE_URL`. It is ignored by Git and must never contain credentials that are committed.

### 4. Prepare the database

Create a local PostgreSQL database, then run:

```powershell
alembic upgrade head
```

To reverse the schema during development:

```powershell
alembic downgrade base
```

### 5. Start the application

```powershell
python -m uvicorn backend.app.main:app --reload
```

Open the generated OpenAPI UI at <http://127.0.0.1:8000/docs>. The liveness endpoint is <http://127.0.0.1:8000/api/v1/health>.

### 6. Run tests and quality checks

```powershell
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m security
python -m pytest --cov=backend --cov-report=term-missing
ruff check .
ruff format --check .
python -m mypy backend
```

Frontend:

```powershell
cd frontend
npm test
npm run test:coverage
npm run lint
npm run typecheck
npm run build
```

PostgreSQL-specific tests require a dedicated test database:

```powershell
$env:PYBANK_TEST_DATABASE_URL="postgresql+psycopg://pybank_test:pybank_test@localhost:5432/pybank_test"
python -m pytest backend/tests/integration/persistence
```

Do not point `PYBANK_TEST_DATABASE_URL` at a normal development or production database.

## Docker quick start

Prerequisites:

- Docker
- Docker Compose

Create local configuration if needed:

```powershell
Copy-Item .env.example .env
```

Build and start the stack:

```powershell
docker compose build
docker compose up
```

Or start detached:

```powershell
docker compose up -d
```

Open the frontend at <http://localhost:8080>. Verify the backend at
<http://localhost:8000/api/v1/health>.

Useful commands:

```powershell
docker compose ps
docker compose logs
docker compose logs backend
docker compose down
```

The Docker database is stored in the named volume `pybank_postgres_data`.
`docker compose down` keeps that data. To intentionally reset the Docker
database:

```powershell
docker compose down -v
docker compose up -d
```

Detailed Docker notes are in `docs/architecture/phase-7.md` and
`docs/learning/phase-7.md`.

Phase 8 adds Redis to the Docker stack as a cache and shared login rate-limit
store. Redis is reached by the backend as `redis://redis:6379/0` inside Compose.
Host development can use `REDIS_URL=redis://localhost:6379/0`. See
`docs/architecture/phase-8.md` and `docs/learning/phase-8.md`.

Phase 9 adds Kafka through a transactional outbox. Kafka is reached as
`kafka:9092` inside Compose and transports events from durable PostgreSQL outbox
rows. See `docs/architecture/phase-9.md` and `docs/learning/phase-9.md`.

## Project structure

```text
PyBank/
├── backend/
│   ├── app/
│   │   ├── api/               # HTTP routers, schemas, serializers, errors
│   │   ├── application/       # Use cases coordinating domain and persistence
│   │   ├── core/config.py     # Typed environment configuration
│   │   ├── core/logging.py    # Standard logging setup
│   │   ├── domain/             # Framework-independent banking rules
│   │   ├── infrastructure/     # SQLAlchemy models, sessions, and mappers
│   │   ├── notifications/      # Channel-neutral notification model and adapters
│   │   ├── realtime/           # WebSocket manager, message contract, tickets
│   │   └── main.py             # FastAPI application entrypoint
│   └── tests/                  # API and domain behavior tests
├── frontend/                   # React + TypeScript client
├── docs/
│   ├── architecture/         # System boundaries and evolution
│   └── learning/              # Beginner-friendly explanations
├── infrastructure/            # Reserved for later deployment work
├── .env.example               # Safe configuration template
├── pyproject.toml              # Dependencies and tool configuration
└── README.md
```

The existing root `main.py` is legacy standalone OOP learning code. It remains intentionally separate and untouched. The current PyBank architecture lives under `backend/`, with Phase 1 banking rules under `backend/app/domain/` and Phase 2 HTTP adapters under `backend/app/api/`.

Phase 4 stores authentication users in PostgreSQL through migration `0002_users`. Phase 5 stores browser tokens in `sessionStorage` for this learning client; this is XSS-readable and is not presented as a hardened production banking strategy. See the Phase 5 security documentation for the production alternative.

Phase 6 keeps browser E2E tests as a documented smoke target rather than adding Playwright before Dockerized orchestration exists. The high-value E2E suite should be automated in Phase 7 or Phase 16 using the Phase 6 quality gate.

## Security principles

- Never commit secrets or hardcode credentials.
- Never store plaintext passwords.
- Keep JWT secrets in environment-backed configuration.
- Enforce account ownership server-side.
- Use role-based authorization for administrative operations.
- Rate-limit authentication attempts.
- Log security events without sensitive values.
- Validate configuration at startup.
- Keep dependencies minimal and reviewed.
- Do not expose unnecessary debugging information in production.
- Do not use `eval()`.
- Treat all client input as untrusted.

## Roadmap

| Phase | Focus |
|---:|---|
| 0 | Project Foundation |
| 1 | Banking Domain + OOP |
| 2 | FastAPI Backend |
| 3 | PostgreSQL + SQLAlchemy + Alembic |
| 4 | Authentication + Security |
| 5 | React + TypeScript Frontend |
| 6 | Testing + Code Quality |
| 7 | Docker + Docker Compose |
| 8 | Redis + Performance |
| 9 | Kafka + Event-Driven Architecture |
| 10 | Microservices |
| 11 | Observability (verified; see `docs/verification/phase-11.md`) |
| 12 | ML Fraud Detection (verified; see `docs/verification/phase-12.md`) |
| 13 | Neo4j + Fraud Graph (verified; see `docs/verification/phase-13.md`) |
| 14 | LLM Banking Agents |
| 15 | Real-Time + WhatsApp |
| 16 | CI/CD + Cloud |
| 17 | Production Hardening |

Recommended initial commit after review: `chore: initialize PyBank project foundation`.
