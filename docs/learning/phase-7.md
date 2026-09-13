# Phase 7 Learning - Docker + Docker Compose

Docker packages an application with the operating-system pieces it needs to run.
For PyBank, that means a repeatable backend, frontend, and PostgreSQL setup.

## Core Ideas

- An image is a build artifact. It is the recipe plus filesystem used to start containers.
- A container is a running instance of an image.
- Docker Compose starts several containers together from one `compose.yaml`.
- PyBank uses Compose because the app has three local parts: frontend, backend, and database.

## Why Containers Help

Containers reduce "works on my machine" problems. A new learner can build the
same Python backend image, the same frontend static image, and the same
PostgreSQL 18 service with a few commands.

Docker does not make code correct, secure, scalable, or production-ready by
itself. Tests, migrations, configuration, and security rules still matter.

## PostgreSQL and Volumes

The PostgreSQL container is useful because every developer can run the same
database version locally. Its data is stored in a named volume:

```text
pybank_postgres_data
```

A volume survives container deletion. That is why `docker compose down` does not
delete your Docker database. Use `docker compose down -v` only when you want a
fresh database.

## Docker Networks

Compose creates private DNS for services. Inside Docker, the backend can use:

```text
postgres:5432
```

because `postgres` is the Compose service name.

`localhost` is different inside containers. From the backend container,
`localhost` means the backend container itself, not PostgreSQL and not your host
machine.

## Browser Networking

The browser is not inside the Compose network. It opens the frontend through:

```text
http://localhost:8080
```

The frontend JavaScript calls the backend through:

```text
http://localhost:8000/api/v1
```

Do not configure browser code to call `http://backend:8000`; normal host
browsers cannot resolve that Docker-only service name.

## Health Checks

A running container is not always a healthy application. Health checks ask a
small question:

- Is PostgreSQL accepting connections?
- Is FastAPI returning `/api/v1/health`?
- Is Nginx serving the frontend?

Compose can use these checks to start services in a better order.

## Alembic

Alembic remains the migration authority. PyBank does not use SQLAlchemy
`create_all` to silently change schemas. In the Docker development stack, the
backend entrypoint runs `alembic upgrade head` before starting the API.

## Development vs Production

This Docker setup is for local learning and reproducibility. Production would
need different secrets, deployment policy, monitoring, backup strategy, TLS, and
hardening. Those are intentionally deferred to later phases.
