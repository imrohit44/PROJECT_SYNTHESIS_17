# Phase 7 Architecture - Docker + Docker Compose

Phase 7 adds a reproducible local container environment. It does not replace the
normal Python, PostgreSQL, or frontend development workflows.

```text
Host browser
  |
  | http://localhost:8080
  v
frontend container (Nginx static files)
  |
  | browser calls http://localhost:8000/api/v1
  v
backend container (FastAPI/Uvicorn)
  |
  | postgresql+psycopg://...@postgres:5432/pybank_docker
  v
postgres container (PostgreSQL 18)
```

## Services

- `postgres`: PostgreSQL 18 with a named persistent volume.
- `backend`: Python 3.12 slim image running FastAPI with Uvicorn.
- `frontend`: Vite build served by Nginx.

All services join the private `pybank` bridge network.

## Ports

- Frontend: host `8080` -> container `80`.
- Backend: host `8000` -> container `8000`.
- PostgreSQL: host `5433` -> container `5432` for local debugging.

The backend uses `postgres:5432` inside Docker. It must not use `localhost`
for PostgreSQL because `localhost` inside a container means that same container.

The browser runs on the host, outside the Docker network. It cannot rely on the
Compose hostname `backend`, so the frontend is built with
`VITE_API_BASE_URL=http://localhost:8000/api/v1` by default.

## Environment

Host development can use:

```text
DATABASE_URL=postgresql+psycopg://pybank:pybank@localhost:5432/pybank
```

Docker Compose development uses:

```text
DATABASE_URL=postgresql+psycopg://pybank:pybank_docker_password@postgres:5432/pybank_docker
```

Values come from `.env` or Compose defaults. Real secrets must not be committed.

## Migrations

Alembic remains the schema authority. The backend entrypoint runs:

```text
alembic upgrade head
```

when `RUN_MIGRATIONS=true`, then starts Uvicorn. This keeps the learning flow
simple for a single backend container. For manual migration practice, set
`RUN_MIGRATIONS=false` and run:

```powershell
docker compose exec backend alembic upgrade head
```

## Health Checks

- PostgreSQL uses `pg_isready`.
- Backend calls `/api/v1/health`.
- Frontend checks that Nginx can serve HTTP.

`depends_on` waits for configured health checks before starting dependent
services. It helps startup ordering, but it is not a general guarantee that a
service will remain healthy forever.

## Persistence

PostgreSQL data lives in the named volume `pybank_postgres_data`. `docker compose
down` stops containers but keeps named volumes. To intentionally reset the Docker
database:

```powershell
docker compose down -v
docker compose up -d
```

The next backend startup reruns Alembic against the fresh database.

## Verification

After `docker compose up -d`, run the host-side smoke check:

```powershell
.\docker\smoke-test.ps1
```

It verifies frontend reachability, backend health, registration, login,
`/auth/me`, account creation, deposit, withdrawal, transfer, and transaction
history through the published host ports.
