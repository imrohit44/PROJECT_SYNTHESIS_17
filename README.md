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

**Phase 6 - Testing + Code Quality**

Phases 0 through 5 are complete. The current implementation establishes the testing pyramid, coverage measurement, shared backend fixtures, authentication/security regression tests, React Testing Library coverage, React Query behavior tests, and documented quality gates. The backend remains the authority for security and banking behavior.

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
| 6 | Testing + Code Quality (current) |
| 7 | Docker + Docker Compose |
| 8 | Redis + Performance |
| 9 | Kafka + Event-Driven Architecture |
| 10 | Microservices |
| 11 | Observability |
| 12 | ML Fraud Detection |
| 13 | Neo4j + Fraud Graph |
| 14 | LLM Banking Agents |
| 15 | Real-Time + WhatsApp |
| 16 | CI/CD + Cloud |
| 17 | Production Hardening |

Recommended initial commit after review: `chore: initialize PyBank project foundation`.
