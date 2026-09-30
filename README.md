# Project Synthesis 17

[![CI](https://github.com/imrohit44/PyBank/actions/workflows/ci.yml/badge.svg)](https://github.com/imrohit44/PyBank/actions/workflows/ci.yml)

A learning-driven banking platform that evolves from a simple object-oriented core into a distributed system through 17 engineering stages.

Project Synthesis 17 began as a simple banking system and grew incrementally: a new engineering layer was introduced only when the previous stage created a concrete problem or requirement. The banking domain is the vehicle; the engineering evolution is the subject. The repository contains 17 stages, Phase 0 through Phase 16.

## What is Project Synthesis 17?

Project Synthesis 17 is a banking platform built as an engineering exercise. Customers, savings and current accounts, deposits, withdrawals, transfers, and transaction history sit on top of a modular backend, a React frontend, and -- once the architecture demands it -- event transport, an independent fraud service, and production deployment.

It was built to study how real systems grow. Most sample projects present a finished architecture; this one records the path to it. Each stage is a small, runnable system, and each new technology arrives with the problem that justifies it: PostgreSQL when in-memory state stops being honest, Redis when reads need a cache, Kafka when services must react without calling each other.

That discipline is the development approach. The recurring loop is: simple system, real engineering problem, architectural decision, new capability, new trade-off, next stage. Complexity is earned, and every stage stays understandable on its own.

The 17-stage structure exists so the evolution can be followed end to end -- from an object-oriented core to a containerized, observable, event-driven platform -- with documentation at each step and verification where it matters.

## What You Can Explore

- Model a banking domain with object-oriented design and financial invariants.
- Build a versioned REST API with FastAPI, Pydantic schemas, and OpenAPI docs.
- Persist financial data with PostgreSQL, SQLAlchemy 2, and Alembic migrations.
- Implement JWT authentication, refresh tokens, and role-based authorization.
- Build a React 19 + TypeScript banking interface with routing and data fetching.
- Set up pytest markers, coverage, Ruff, MyPy, ESLint, and TypeScript checks.
- Containerize the system with Docker Compose across ten services.
- Add Redis caching and a shared login rate-limit store.
- Implement event-driven workflows with Kafka and a transactional outbox.
- Extract an independent fraud and risk service with its own database.
- Add structured logging, Prometheus metrics, OpenTelemetry traces, and Grafana dashboards.
- Combine rule-based, ML, and graph-based fraud scoring into one assessment.
- Project transfer history into a Neo4j relationship graph.
- Integrate a read-only LLM banking assistant behind four allowlisted tools.
- Deliver authenticated realtime updates over WebSockets with ticket-based auth.
- Send outbound-only WhatsApp notifications driven by Kafka events.
- Ship immutable container releases through CI to a cloud host.

## Key Capabilities

### Banking

- Customer management, savings and current accounts
- Deposits, withdrawals, and transfers with deterministic locking order
- Transaction history and per-account statements
- Versioned API (`/api/v1`) serving customers, accounts, transfers, users, auth, health, assistant, and realtime tickets

### Security

- Argon2 password hashing; JWT access tokens (15 minutes) and refresh tokens (7 days)
- HS256-only token validation; secrets under 32 characters refused at startup
- RBAC with an admin role; server-side account ownership enforcement
- Redis-backed login rate limiting with local fallback; assistant rate limiting
- Security headers, CORS allow-list, input validation via Pydantic
- Structured audit logging of security events without sensitive values
- Configuration validated at startup; secrets only through environment variables

### Distributed Systems

- Apache Kafka event transport with correlation ID and trace headers
- Transactional outbox: events committed with the business write, relayed by a publisher thread
- At-least-once delivery with idempotent, deduplicating consumers
- Independent fraud service with its own database, migrations, and Kafka consumer groups
- Bounded timeouts on every outbound HTTP call and readiness probe

### Fraud and Intelligence

- Deterministic rule scoring combined with trained ML scoring (scikit-learn) under configurable weights
- Neo4j relationship projection producing a bounded graph adjustment; fraud degrades to rules plus ML when the graph is unavailable
- Single risk assessment combining rules, model, and graph signals
- Read-only LLM assistant: four allowlisted tools, no direct database or model-driven identity access, mutations impossible, explicit 503 when unconfigured

### Realtime

- Authenticated WebSockets via short-lived, single-use tickets (`POST /api/v1/ws/ticket` with the WebSocket at `/api/v1/ws`); raw JWTs are never accepted in query strings
- Kafka-driven notification service mapping transfers and risk assessments to channel-neutral messages
- WebSocket and outbound-only WhatsApp adapters; banking is unaffected when channels fail
- React `useRealtime` hook with status, typed messages, and bounded reconnect backoff

### Operations

- Docker Compose development stack plus an additive production overlay
- Liveness (`/health`), readiness (`/ready`), and Prometheus (`/metrics`) endpoints on both Python services
- Prometheus, Grafana with provisioned dashboards, Jaeger all-in-one for OpenTelemetry traces, structured JSON logging
- CI pipeline, immutable GHCR releases, SSH-based EC2 deployment with health verification and SHA rollback
- Verified `pg_dump` backup and restore tooling with overwrite protection

## Architecture Evolution

The repository contains 17 engineering stages, from Phase 0 through Phase 16. Each phase is documented under `docs/architecture/` and `docs/learning/`, with runtime verification for Phases 11 through 16 under `docs/verification/`.

| Phase | Focus | Main Addition |
| --- | --- | --- |
| 0 | Foundation | Python project layout, tooling, and conventions |
| 1 | Domain | Banking domain model and financial invariants |
| 2 | API | FastAPI application layer with versioned routes |
| 3 | Persistence | PostgreSQL, SQLAlchemy 2, and Alembic migrations |
| 4 | Security | JWT authentication, RBAC, and ownership enforcement |
| 5 | Frontend | React + TypeScript client with auth and banking pages |
| 6 | Quality | Pytest suites, coverage, Ruff, and MyPy |
| 7 | Containers | Docker images and a ten-service Compose stack |
| 8 | Performance | Redis cache and shared rate-limit store |
| 9 | Events | Kafka with a transactional outbox |
| 10 | Services | Independent fraud and risk service |
| 11 | Observability | Structured logs, metrics, traces, and dashboards |
| 12 | ML | Trained fraud model combined with rule scoring |
| 13 | Graph | Neo4j relationship projection and graph adjustment |
| 14 | AI | Read-only LLM banking assistant |
| 15 | Realtime | Ticket-authenticated WebSockets and notification adapters |
| 16 | Production | CI pipeline, immutable releases, and cloud deployment |

## Technology Stack

### Backend

| Technology | Version |
| --- | --- |
| Python | >= 3.12 (CI and images use 3.12) |
| FastAPI | >= 0.115, < 1.0 |
| Uvicorn (standard) | >= 0.34, < 1.0 |
| SQLAlchemy | >= 2.0, < 3.0 |
| Alembic | >= 1.14, < 2.0 |
| psycopg (binary) | >= 3.2, < 4.0 |
| Pydantic Settings | >= 2.6, < 3.0 |
| PyJWT | >= 2.9, < 3.0 |
| argon2-cffi | >= 23.1, < 26.0 |
| httpx | >= 0.28, < 1.0 |
| email-validator | >= 2.2, < 3.0 |

### Frontend

| Technology | Version |
| --- | --- |
| React / React DOM | ^19.1.1 |
| TypeScript | ~5.9.2 |
| Vite | ^7.1.3 |
| Tailwind CSS | ^4.1.12 |
| React Router | ^7.8.2 |
| TanStack React Query | ^5.87.0 |
| Axios | ^1.11.0 |
| lucide-react | ^0.468.0 |

### Data and Messaging

| Technology | Version |
| --- | --- |
| PostgreSQL | 18 (Compose image) |
| Redis | 7.4-alpine (Compose image) |
| Neo4j Community | 5.26-community (Compose image) |
| Apache Kafka (KRaft) | 3.9.1 (Compose image) |
| confluent-kafka (Python client) | >= 2.6, < 3.0 |

### AI and ML

| Technology | Version |
| --- | --- |
| scikit-learn | >= 1.5, < 2.0 |
| numpy | >= 2.0, < 3.0 |
| joblib | >= 1.4, < 2.0 |
| neo4j (Python driver) | >= 5.25, < 6.0 |
| pandas (ML training and dev) | >= 2.2, < 4.0 |
| LLM provider client | HTTP-based, configured via `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |

### Observability

| Technology | Version |
| --- | --- |
| structlog | >= 24.1, < 25.0 |
| prometheus-client | >= 0.20, < 1.0 |
| OpenTelemetry API / SDK / OTLP exporter | >= 1.29, < 2.0 |
| FastAPI OpenTelemetry instrumentation | >= 0.50b0 |
| Jaeger all-in-one | 1.62.0 (Compose image) |
| Prometheus | v3.1.0 (Compose image) |
| Grafana | 11.5.1 (Compose image) |

### Infrastructure

| Technology | Notes |
| --- | --- |
| Docker / Docker Compose | Backend, fraud, and frontend images; ten-service dev stack |
| Nginx | Serves the production SPA build; TLS reverse proxy config in `deploy/nginx/` |
| GitHub Actions | CI, image publishing, and EC2 deployment workflows |
| GHCR | Immutable per-commit backend, fraud, and frontend images |
| AWS EC2 | Single-host Docker Compose deployment target |

## Architecture

The browser loads the React SPA from Nginx and talks to the banking API over `/api/v1`, with realtime updates arriving over authenticated WebSockets. The backend persists to PostgreSQL, caches in Redis, and emits domain events through a transactional outbox to Kafka. The fraud service consumes transfer events, scores them with rules, a trained model, and the Neo4j graph projection, and returns assessments to the API and event stream. Metrics flow to Prometheus and Grafana; traces flow to Jaeger.

```text
Browser (React SPA)
  |
Nginx (static SPA + TLS reverse proxy in production)
  |
Banking API (FastAPI :8000) ---- HTTP ---- Fraud service (FastAPI :8001)
  |        |        |                               |
PostgreSQL Redis   Kafka topics               PostgreSQL (fraud DB)
(Banking) (cache,  (transfer events,               |
 rate limit) risk assessments)              Rules + ML model + Neo4j graph
  |        |        |
  |        |     Consumers: audit, notifications (WebSocket, WhatsApp)
  |
/health /ready /metrics --> Prometheus --> Grafana
Traces (OTLP) --> Jaeger
```

## Repository Structure

```text
.
├── .github/workflows/      # CI, GHCR publishing, EC2 deployment
├── alembic/                # Banking-service database migrations
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Routers: auth, customers, accounts, transfers, users, assistant, ws
│   │   ├── application/    # Use cases coordinating domain and persistence
│   │   ├── assistant/      # Read-only LLM tools executed against the JWT principal
│   │   ├── core/           # Typed settings, logging, readiness dependencies
│   │   ├── domain/         # Framework-independent banking rules
│   │   ├── infrastructure/ # SQLAlchemy models, sessions, Kafka, outbox, cache
│   │   ├── llm/            # Provider client abstraction
│   │   ├── notifications/  # Kafka consumer plus WebSocket and WhatsApp adapters
│   │   ├── realtime/       # Ticket store, WebSocket manager, message contract
│   │   └── security/       # JWT tokens, passwords, RBAC, rate limiting, audit
│   └── tests/              # unit, integration, security, persistence, realtime, assistant suites
├── services/
│   ├── fraud/              # Independent service: API, Kafka, rules, ML, graph, own migrations
│   └── common/             # Shared observability helpers
├── frontend/               # React + TypeScript client (Vite, Tailwind, Router, Query)
├── docs/
│   ├── architecture/       # Phase 0-16 design records
│   ├── learning/           # Beginner-friendly phase explanations
│   └── verification/       # Runtime verification for Phases 11-16 plus hardening audits
├── infrastructure/         # Prometheus config, Grafana provisioning, Postgres init
├── docker/                 # Entrypoints and Compose verification scripts
├── deploy/                 # Production overlay scripts plus Nginx config
├── scripts/                # PostgreSQL backup and restore tooling
├── showcase/               # Synthesis Explorer: visual tour of the 17-stage evolution
├── compose.yaml            # Ten-service development stack
├── docker-compose.prod.yml # Production overlay (private services, required secrets)
├── Dockerfile              # Banking API image
├── pyproject.toml          # Backend dependencies, pytest, coverage, Ruff, MyPy
├── alembic.ini             # Migration configuration
├── .env.example            # Development configuration template
└── .env.production.example # Production configuration template
```

Only the directories above are part of the documented layout. Generated output such as `backups/`, `artifacts/`, and build folders is gitignored and intentionally omitted.

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker Desktop with Docker Compose (for the full stack)
- A local PostgreSQL instance (only for running the backend outside Docker)

### Clone

```bash
git clone https://github.com/imrohit44/PyBank.git
cd PyBank
```

The checked-out directory is `PyBank`; the project itself is titled Project Synthesis 17. Several runtime identifiers predate that title and still use the historical name, including environment variables (`PYBANK_*`), the Compose volume prefix, and the container image names.

### Environment

```powershell
Copy-Item .env.example .env
```

`.env` is gitignored. The development defaults run the stack without real credentials; production uses `.env.production.example`, where required secrets fail fast if unset.

### Run with Docker

```powershell
docker compose up -d
```

This starts PostgreSQL, Redis, Kafka, the banking API, the frontend, the fraud service, Neo4j, Jaeger, Prometheus, and Grafana. Open the frontend at <http://localhost:8080> and check the API at <http://localhost:8000/health>.

### Run locally

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open the OpenAPI UI at <http://127.0.0.1:8000/docs>. Persistence tests use a dedicated database configured through `PYBANK_TEST_DATABASE_URL`; never point it at a development or production database.

## Testing

Backend (repository root):

```powershell
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m security
python -m pytest --cov=backend --cov-report=term-missing
```

Fraud service:

```powershell
cd services/fraud
python -m pytest
ruff check app tests
ruff format --check app tests
mypy app
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

Quality gates (repository root):

```powershell
ruff check backend/app backend/tests
ruff format --check backend/app backend/tests
mypy backend/app
```

Coverage enforces a 60 percent floor for the backend. Kafka-dependent tests run against the Compose stack; Redis tests use a fake client or a local instance. The full matrix also runs in CI on every push and pull request.

## Security

Implemented mechanisms, without implying absolute security:

- Argon2 password hashing; no plaintext credentials stored
- Short-lived JWT access tokens with refresh rotation; HS256-only validation
- Minimum 32-character JWT secrets enforced at startup
- Admin/user roles with server-side account ownership checks
- Redis-backed login rate limiting with per-endpoint assistant limits
- Hardening headers, restrictive CORS origin, Pydantic input validation
- Audit log entries for auth and security events, excluding sensitive values
- Ticket-based WebSocket auth so bearer tokens never appear in URLs or logs
- Idempotent event processing so retried deliveries cannot double-apply effects
- Assistants and adapters cannot mutate banking state
- Secrets supplied only through environment files that are never committed
- Backups restore into new databases only; deployment scripts ban destructive volume removal

The frontend stores tokens in `sessionStorage` for this learning client. That storage is readable by page JavaScript, so it is not presented as a hardened production token strategy.

## Engineering Characteristics

- Domain logic isolated from frameworks, persistence, and transport
- Application services coordinate use cases across the domain boundary
- Money movement guarded by deterministic database locking order
- State changes and outbound events committed atomically via the outbox
- Consumers process at-least-once deliveries idempotently
- Fraud runs as an independently deployable service with its own schema
- Analytical systems (graph, ML, assistant) degrade gracefully instead of blocking banking
- Health, readiness, and metrics endpoints on every Python service
- One Compose definition for development; a strictly additive overlay for production
- Every stage reproducible from versioned images, migrations, and checked-in configuration

## Status

The repository is a completed learning and engineering project covering Phase 0 through Phase 16. The implementation, documentation, and verification tooling described above are present in the tree.

Verification was executed in an environment with the Compose stack running; external integrations and the cloud deployment path additionally require environment-specific credentials and infrastructure. `docs/verification/` marks anything that could not be executed as pending rather than passing. `phase-17.md` and `phase-17-cleanup.md` record a later hardening audit (token validation, reliability checks, dependency review, backups), not a new implementation stage.

## Documentation

- `docs/architecture/phase-0.md` through `phase-16.md` — design record for each stage
- `docs/learning/phase-0.md` through `phase-16.md` — approachable explanation of each stage
- `docs/verification/phase-11.md` through `phase-16.md` — runtime verification evidence
- `docs/verification/phase-17.md`, `phase-17-cleanup.md` — hardening audit records
- `showcase/` — Synthesis Explorer, the visual tour of the 17-stage evolution
- `deploy/` and `docker-compose.prod.yml` — production deployment procedure
- `scripts/` — database backup and restore procedure
- `services/fraud/README.md` — fraud service notes
- `infrastructure/README.md` — observability and database initialization notes
