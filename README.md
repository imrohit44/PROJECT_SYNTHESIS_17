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

**Phase 1 - Banking Domain & OOP**

Phase 0 is complete. The current implementation adds a framework-independent banking domain with customers, accounts, transactions, account states, transfers, domain exceptions, Decimal-based money, unit tests, and documentation. FastAPI remains only the Phase 0 application foundation; no banking HTTP endpoints have been added.

## Technology stack currently implemented

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic Settings
- pytest, pytest-asyncio, and HTTPX
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

Edit `.env` only for local values. It is ignored by Git and must never contain credentials that are committed.

### 4. Start the application

```powershell
python -m uvicorn backend.app.main:app --reload
```

Open the generated OpenAPI UI at <http://127.0.0.1:8000/docs>. The liveness endpoint is <http://127.0.0.1:8000/api/v1/health>.

### 5. Run tests and quality checks

```powershell
python -m pytest
ruff check .
ruff format --check .
python -m mypy backend
```

## Project structure

```text
PyBank/
├── backend/
│   ├── app/
│   │   ├── api/v1/health.py  # Versioned HTTP health route
│   │   ├── core/config.py     # Typed environment configuration
│   │   ├── core/logging.py    # Standard logging setup
│   │   ├── domain/             # Framework-independent banking rules
│   │   └── main.py             # FastAPI application entrypoint
│   └── tests/                  # API and domain behavior tests
├── docs/
│   ├── architecture/         # System boundaries and evolution
│   └── learning/              # Beginner-friendly explanations
├── infrastructure/            # Reserved for later deployment work
├── .env.example               # Safe configuration template
├── pyproject.toml              # Dependencies and tool configuration
└── README.md
```

The existing root `main.py` is legacy standalone OOP learning code. It remains intentionally separate and untouched. The current PyBank architecture lives under `backend/`, with Phase 1 banking rules under `backend/app/domain/`.

## Security principles

- Never commit secrets or hardcode credentials.
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
| 11 | Observability |
| 12 | ML Fraud Detection |
| 13 | Neo4j + Fraud Graph |
| 14 | LLM Banking Agents |
| 15 | Real-Time + WhatsApp |
| 16 | CI/CD + Cloud |
| 17 | Production Hardening |

Recommended initial commit after review: `chore: initialize PyBank project foundation`.
