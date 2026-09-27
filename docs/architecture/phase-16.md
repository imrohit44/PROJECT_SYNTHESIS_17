# Phase 16 — CI/CD and Cloud Architecture

## 1. What Phase 16 actually changed

Phases 0–15 produced an application that was *correct* and *containerised*.
Nothing had ever taken it from a laptop to a public URL.

Phase 16 adds exactly three things and changes no application behaviour:

1. **CI** — every push and pull request is validated automatically.
2. **A container release** — the three deployable images are built once and
   published under an immutable commit-SHA tag.
3. **A cloud deployment** — a single AWS EC2 host runs the same Compose stack
   behind Nginx over HTTPS, plus a documented rollback.

The eleven running components from Phase 15 are unchanged. Same services, same
migrations, same health checks, same event flow.

## 2. The release chain

```
      git push (main)
            │
            ▼
   ┌──────────────────────┐
   │  GitHub Actions: CI  │   backend pytest/ruff/mypy
   │  (.github/workflows/ │   fraud  pytest/ruff/mypy
   │        ci.yml)       │   frontend eslint/tsc/vitest/build
   │                      │   docker compose config + 3 image builds
   └──────────┬───────────┘
              │  workflow_run, conclusion == 'success'   ← hard gate
              ▼
   ┌──────────────────────┐
   │ Publish images       │   builds the exact commit CI validated
   │ (docker-publish.yml) │   tags <sha> AND main, pushes to GHCR
   └──────────┬───────────┘
              │  workflow_run, conclusion == 'success'   ← hard gate
              ▼
   ┌──────────────────────┐
   │ Deploy to EC2        │   SSH → pull <sha> → compose up
   │ (deploy-ec2.yml)     │   wait /health + /ready → smoke test
   └──────────┬───────────┘
              ▼
      AWS EC2 host (Docker Compose)
```

### Why the gates are real, not aspirational

`docker-publish.yml` no longer listens to `push`. It listens to
`workflow_run` for the `CI` workflow and carries a job-level guard:

```yaml
if: >-
  github.event_name == 'workflow_dispatch' ||
  github.event.workflow_run.conclusion == 'success'
```

A failed CI run therefore produces **no image at all**, and because
`deploy-ec2.yml` triggers off `Publish images`, a failed publish produces
**no deployment**. There is no path from a red build to a running container.

The publish workflow also checks out `workflow_run.head_sha` rather than
`github.sha`. On a `workflow_run` event `github.sha` refers to the default
branch HEAD, which may already have moved on — publishing from it would ship
code that was never tested. Using `head_sha` guarantees the image is built
from precisely the commit CI validated.

## 3. Network topology — public vs private

```
                        INTERNET
                            |
                    HTTPS :443  /  HTTP :80 (redirect only)
                            |
                            v
                  +-------------------+
                  |  Nginx (host)     |  deploy/nginx/pybank.conf
                  |  TLS termination  |  only component facing the internet
                  +---------+---------+
                            |  loopback only (127.0.0.1)
            +---------------+----------------+
            v                                v
   +---------------------+         +----------------------+
   | Frontend :8080      |         | Backend  :8000       |
   | React SPA, static   |         | FastAPI, REST, WS    |
   +---------------------+         +----------+-----------+
                                              | private compose network
   +------------------------------------------+-----------------------------+
   |  postgres (5432)  redis (6379)  kafka (9092)  neo4j (7474/7687)        |
   |  prometheus (9090)  grafana (3000)  jaeger (16686)  fraud (8000)        |
   +-----------------------------------------------------------------------+
```

### PUBLIC

| Port | Service | Purpose |
|------|---------|---------|
| 80 | Nginx | ACME challenge + 301 to HTTPS |
| 443 | Nginx | The only application entry point |
| 22 | sshd | Deployment and administration (restrict source IP) |

### PRIVATE — no published port, unreachable from the internet

`postgres` (5432), `redis` (6379), `kafka` (9092), `neo4j` (7474, 7687),
`prometheus` (9090), `grafana` (3000), `jaeger` (16686), `fraud` (8000).

### How "private" is enforced

`docker-compose.prod.yml` layers over `compose.yaml` and removes the host
port for every internal service using Compose's `!reset` tag:

```yaml
  postgres:
    ports: !reset []      # base file's 5433 mapping is discarded
  neo4j:
    ports: !reset []
```

The two application services keep a port but bind it to loopback, so Nginx can
reach them and the internet cannot:

```yaml
  backend:
    ports: !override
      - "127.0.0.1:${BACKEND_BIND_PORT:-8000}:8000"
```

Verified by merging both files and reading the resolved model: only
`backend` and `frontend` report a published port, and both have
`host_ip: 127.0.0.1`. Nginx references no internal service by name, so there
is no route from a request to a database.

## 4. Why internal services must not be public

PostgreSQL on 5432 speaks no authentication worth relying on, Kafka on 9092
has no transport security, Neo4j's browser and Bolt ports are an
administrative console, and Prometheus/Grafana/Jaeger are operational
dashboards that leak topology, metrics and trace payloads.

Publishing any of them converts an application bug into a data breach. The
cheapest defence is architectural: make the port unreachability a property of
the Compose file rather than a firewall rule somebody has to remember.

This is why `fraud` is reached with `docker compose exec` in
`deploy/health.sh` instead of being given a host port for convenience. A
monitoring script must never be the reason a private service becomes public.

## 5. Request routing

Nginx does three jobs and contains no business logic:

| Path | Upstream | Notes |
|------|----------|-------|
| `/` | `127.0.0.1:8080` | React SPA, static assets |
| `/api/` | `127.0.0.1:8000` | REST + LLM assistant (120s read timeout) |
| `/api/v1/ws` | `127.0.0.1:8000` | WebSocket, Upgrade/Connection passthrough, 3600s timeout |

The SPA is built with `VITE_API_BASE_URL=/api/v1`, a **relative** path, so the
browser calls the same origin that served it. That makes production
single-origin and removes CORS as a production dependency entirely.

Correlation IDs survive the hop: Nginx forwards a client-supplied
`X-Correlation-ID` or mints one via `$request_id`, so a request can be traced
from the edge into the backend, through Kafka, and into the Fraud service. The
Phase 11/12 correlation guarantee is not weakened by the proxy.

## 6. Image versioning

```
ghcr.io/imrohit44/pybank-backend:<commit-sha>
ghcr.io/imrohit44/pybank-fraud:<commit-sha>
ghcr.io/imrohit44/pybank-frontend:<commit-sha>
```

A `main` tag is also published purely for human convenience. **Deployment never
uses it.** `deploy/deploy.sh` rejects any argument that is not a commit SHA
(`^[0-9a-f]{7,40}$`), so a moving tag can never cause an unreviewed redeploy,
and "what is running in production" is always answerable.

`deploy/RELEASE_HISTORY` is append-only and `deploy/CURRENT_RELEASE` records
the active SHA, which is what makes rollback a one-line operation.

## 7. Local vs cloud

Phase 16 is strictly **additive**. `compose.yaml` is untouched, so
`docker compose up` still works exactly as before on a laptop. The production
file is an *overlay*, never a replacement:

```
docker compose up                                                # local
docker compose -f compose.yaml -f docker-compose.prod.yml up -d   # cloud
```

Both run the same services, the same migrations and the same health checks. The
only differences are the image source, the port exposure, and the fail-fast
secrets.

## 8. Data safety

`docker compose down -v` destroys named volumes, which would delete the banking
database, the fraud database and the Neo4j graph. It appears nowhere as an
action in the deploy path. It is not merely avoided -- `deploy.sh` greps the
deploy tree and **aborts the deployment** if it ever appears:

```bash
if grep -rn -- "compose down -v" deploy/ .github/workflows/ 2>/dev/null; then
  echo "FATAL: a destructive 'compose down -v' was found in the deploy path" >&2
  exit 1
fi
```

Migrations run through the existing application entrypoint and are additive.
`docker compose up -d` recreates only services whose image changed; the
PostgreSQL and Neo4j named volumes are untouched, so existing customer, account
and transaction data survives every deployment.

## 9. Component responsibilities

| Component | Role in Phase 16 | Changed? |
|-----------|------------------|----------|
| GitHub Actions CI | Validates every push and PR | new |
| GitHub Container Registry | Stores immutable release images | new |
| AWS EC2 | Single host running the whole stack | new |
| Nginx (host) | TLS termination and public routing | new |
| Banking backend | Unchanged application service | no |
| Fraud service | Unchanged application service | no |
| React frontend | Unchanged app, relative API base at build time | build only |
| PostgreSQL (banking + fraud DBs) | Unchanged; volume preserved | no |
| Redis, Kafka, Neo4j | Unchanged; made unreachable from the internet | exposure only |
| Prometheus, Grafana, Jaeger | Unchanged; made unreachable from the internet | exposure only |
