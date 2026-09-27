# Phase 16 Verification Report — CI/CD and Cloud

Every result below was produced by actually running the command shown. Where a
check could not be performed because AWS credentials, a domain or a certificate
do not exist in this environment, it is marked **EXTERNAL VERIFICATION PENDING**
rather than being reported as a pass.

## 1. Scope of what was verified

Two different things are reported separately throughout, because they are not
the same claim:

- **VERIFIED LOCALLY** — executed against the real Compose stack on this
  machine. Real requests, real responses, real containers.
- **EXTERNAL VERIFICATION PENDING** — needs an AWS account, a public domain or
  a GitHub Actions runtime that does not exist in this environment.

## 2. Test suites (VERIFIED LOCALLY)

| Suite | Command | Result |
|---|---|---|
| Backend | `pytest backend/tests -q` | **124 passed, 3 skipped, 0 failed** |
| Fraud | `pytest tests -q` (in `services/fraud`) | **40 passed, 0 failed** |
| Frontend | `npm run test` | **23 passed (8 files), 0 failed** |

### Static analysis

| Tool | Scope | Result |
|---|---|---|
| Ruff lint | repository | **All checks passed** |
| Ruff format | repository | **183 files already formatted** |
| MyPy | `backend/app` | **no issues in 74 source files** |
| Ruff lint | `services/fraud` | **All checks passed** |
| Ruff format | `services/fraud` | **20 files already formatted** |
| MyPy | `services/fraud/app` | **no issues in 13 source files** |
| ESLint | `frontend` | **0 errors, exit 0** |
| TypeScript | `npm run typecheck` (`tsc -b`) | **exit 0** |
| Production build | `npm run build` | **exit 0**, 1715 modules, `/api/v1` inlined |

The ESLint fix in `frontend/src/lib/useRealtime.test.tsx` removed an unused
rest parameter from a `vi.fn` mock. The project's lint configuration was not
weakened and no rule was disabled.

## 3. Docker (VERIFIED LOCALLY)

| Image | Build | Result |
|---|---|---|
| `pybank-backend` | `docker build -f Dockerfile .` | **exit 0**, `sha256:e3ed262e1ed4...` |
| `pybank-fraud` | `docker build -f services/fraud/Dockerfile .` | **exit 0**, `sha256:6d5cde7da923...` |
| `pybank-frontend` | `docker build --build-arg VITE_API_BASE_URL=/api/v1 ./frontend` | **exit 0**, `sha256:c80168343a1e...` |

Compose validation:

| Check | Result |
|---|---|
| `docker compose config --quiet` | **exit 0** |
| `docker compose -f compose.yaml -f docker-compose.prod.yml config --quiet` | **exit 0** |

Non-root execution: the backend image sets `USER pybank`. The fraud and
frontend images declare no `USER` and therefore run as root. This is
**pre-existing from Phase 9/7** and was not introduced by Phase 16; it is
recorded as a known limitation for Phase 17 rather than redesigned here.

## 4. Nginx (VERIFIED LOCALLY)

The production reverse-proxy configuration was validated with a real Nginx
container, not a syntax approximation:

```
docker run --rm -v ./deploy/nginx/pybank.conf:/etc/nginx/conf.d/default.conf:ro \
  nginx:1.27-alpine nginx -t
```

Result: **exit 0** — `nginx/1.27.5`,
`nginx: configuration file /etc/nginx/nginx.conf test is successful`.

22 directives were asserted individually, covering: HTTPS listener, TLS
certificate and key paths, HTTP to HTTPS redirect, ACME challenge location,
TLS 1.2/1.3 only, WebSocket `Upgrade`/`Connection` passthrough, `Host`,
`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, the correlation-ID map,
`client_max_body_size`, the WebSocket read timeout, and both upstreams.
HSTS is intentionally left commented out and its disabled state is asserted,
because enabling it before HTTPS is confirmed would lock users out.

Evidence: `artifacts/phase16/nginx_config_evidence.txt`.

## 5. Network exposure (VERIFIED LOCALLY)

`artifacts/phase16/audit_prod_exposure.py` merges the base and production
Compose files, inspects the resolved model, and asserts which services publish
a port. Result: **PROD_EXPOSURE_AUDIT_OK: True**.

```
services_total: 10
published_ports:
  backend:  ["127.0.0.1:8000->8000/tcp"]   # loopback only
  frontend: ["127.0.0.1:8080->80/tcp"]     # loopback only
internal_services_with_no_published_port:
  fraud, grafana, jaeger, kafka, neo4j, postgres, prometheus, redis
named_volumes_preserved: [pybank_neo4j_data, pybank_postgres_data]
```

Ports 5432, 6379, 9092, 7474, 7687, 9090, 3000 and 16686 publish **nothing**.
Both application ports bind `127.0.0.1`, so the public entry point is only
80/443 via host Nginx. No internal port is reachable from the internet.

Evidence: `artifacts/phase16/prod_exposure_audit.txt`.

## 6. CI -> publish -> deploy dependency (VERIFIED LOCALLY)

`artifacts/phase16/verify_ci_dependency.py` parses the three workflow files and
asserts the chain is real executable logic rather than a comment. Result:
**WORKFLOW_DEPENDENCY_OK: True**.

```
CI triggers:       ['pull_request', 'push']
Publish triggers:  ['workflow_dispatch', 'workflow_run']
Deploy triggers:   ['workflow_dispatch', 'workflow_run']

  push main -> CI -> [conclusion==success] -> Publish
            -> [conclusion==success] -> Deploy
  published SHA == CI-validated head_sha (no github.sha drift)
  publish limited to main, so a pull request cannot deploy
```

Enforced by:
- `docker-publish.yml` no longer triggers on `push`; it triggers on
  `workflow_run` for the `CI` workflow, filtered to `branches: [main]`.
- Its `publish` job carries
  `if: github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success'`.
- It resolves the release from `workflow_run.head_sha` and checks out that
  exact commit, so the image is built from what CI validated.
- `deploy-ec2.yml` triggers on `workflow_run` for `Publish images` with the
  same conclusion guard.

Permissions remain least-privilege: CI `contents: read`, publish
`contents: read` + `packages: write`, deploy `contents: read`.

Evidence: `artifacts/phase16/ci_dependency_evidence.txt`.

## 7. Deployment smoke test (VERIFIED LOCALLY)

`artifacts/phase16/verify_deployment.py` runs 14 real checks against the live
stack. Result: **DEPLOYMENT_SMOKE_OK: True**, `failures: []`.

| Check | Result | Evidence |
|---|---|---|
| Public endpoint responds | PASS | `HTTP 200` |
| Frontend loads | PASS | `HTTP 200 html=True`, `Content-Type: text/html` |
| Backend liveness | PASS | `{"status": "ok", "service": "banking"}` |
| Backend readiness | PASS | `{"status": "ready", "dependencies": {postgres, redis, kafka: ok}}` |
| Authentication | PASS | register + login, JWT issued |
| Authenticated account access | PASS | `HTTP 200` |
| Transfer flow | PASS | `HTTP 200`, transaction committed |
| Kafka event flow | PASS | event consumed by the fraud service |
| Fraud liveness | PASS | `HTTP 200` |
| Fraud readiness | PASS | `{"status": "ready", "dependencies": {postgres, kafka, neo4j: ok}}` |
| Fraud assessment (ML + graph) | PASS | `final_score 0.0229`, `risk_level LOW`, `ml_probability 0.0574`, `graph_score 0.0`, `fraud-model-v1`, `fraud-graph-v1` |
| Realtime WebSocket | PASS | ticket `HTTP 200`, socket received `connection.established` |
| LLM assistant protected | PASS | unauthenticated call returned `HTTP 401` |
| Correlation ID propagation | PASS | `phase16-smoke-274cad49` present on the fraud assessment |

Evidence: `artifacts/phase16/deployment_smoke_evidence.txt`.

### Two environment notes, recorded honestly

1. **Host port 8080 conflict.** On this machine port 8080 is already bound by
   a native `httpd` process (PID 4924) that ships with a local EnterpriseDB
   PostgreSQL installation, so `127.0.0.1:8080` resolves to that process
   instead of the container. The frontend container itself was confirmed
   healthy and serving the correct SPA. The smoke test was therefore pointed
   at the same container republished on a free port via a temporary override
   kept outside the repository. No project file was changed to achieve this.
2. **Stalled Kafka consumers.** The backend and fraud containers had been
   running ~25 hours and their Kafka consumers had stopped polling, so no
   realtime or fraud assessment was produced. Both were restarted (a
   non-destructive operation that touches no volumes) and every check then
   passed. This is a long-running local environment condition, not a defect
   introduced by Phase 16.

## 8. Phase 0-15 regression (VERIFIED LOCALLY)

No Phase 15 behaviour was changed. Re-verified after all Phase 16 edits:

| Script | Result |
|---|---|
| `verify_realtime.py` | **REALTIME_LIVE_OK: True** (user isolation, correlation, metrics) |
| `verify_failure_modes.py` | **FAILURE_MODES_OK: True** |
| `verify_risk_notification.py` | **RISK_NOTIFICATION_OK: True** (bystander silent) |
| `verify_whatsapp_smoke.py` | **Skipped — credentials not configured** (unchanged) |
| Backend / Fraud / Frontend suites | 124 / 40 / 23 passing |

## 9. Secrets and data safety (VERIFIED LOCALLY)

| Check | Result |
|---|---|
| `.env` tracked by git | No — gitignored (`.gitignore:2`) |
| Secret patterns in tracked files (AKIA, private key, `ghp_`) | None found |
| Certificates or keys in `deploy/` | None — only `.conf` and `.sh` |
| `docker compose down -v` as an action | Absent; `deploy.sh` greps for it and aborts if found |
| `DROP`/`TRUNCATE`/volume deletion in deploy path | None |

Required production secrets use Compose's fail-fast syntax
(`${JWT_SECRET:?...}`), so the production stack refuses to start rather than
falling back to a development default. Production sets `PYBANK_DEBUG: "false"`
and leaves `CORS_ALLOW_ORIGINS` empty (single origin, no wildcard).

All five required variables are now documented in `.env.production.example`.

## 10. EXTERNAL VERIFICATION PENDING

These were **not** performed, and no result is claimed for them. They require
resources that do not exist in this environment.

| Item | Status | Reason |
|---|---|---|
| AWS EC2 instance | **EXTERNAL VERIFICATION PENDING** | No AWS credentials or account available |
| Security group / firewall rules | **EXTERNAL VERIFICATION PENDING** | Requires the instance |
| Public deployment execution | **EXTERNAL VERIFICATION PENDING** | Requires the instance |
| Images published to GHCR | **EXTERNAL VERIFICATION PENDING** | Registry push needs a CI runner with `packages: write`; images were built locally and digests recorded, but not pushed |
| GitHub Actions runtime history | **EXTERNAL VERIFICATION PENDING** | GitHub API returned HTTP 404 for the runs endpoint; the workflows have not yet executed on a runner |
| Real domain and DNS | **EXTERNAL VERIFICATION PENDING** | No domain available |
| Let's Encrypt certificate | **EXTERNAL VERIFICATION PENDING** | Requires public DNS and a reachable port 80 |
| Public HTTPS / WSS | **EXTERNAL VERIFICATION PENDING** | Requires the certificate above |
| Runtime rollback A -> B -> A | **NOT EXECUTED** | Script implemented and reviewed; requires a deployed host. Documented procedure only |

The Nginx configuration is verified to be syntactically correct and
functionally complete, but "the config validates" is not the same claim as
"HTTPS works publicly", and the second claim is not made.

## 11. Rollback status

`deploy/rollback.sh` is implemented and reviewed. Because releases are
immutable commit SHAs, a rollback re-invokes `deploy/deploy.sh` with the
previous SHA, so there is no separate code path that could be wrong.
`deploy/RELEASE_HISTORY` is append-only and `deploy/CURRENT_RELEASE` records the
active release.

Status: **ROLLBACK PROCEDURE IMPLEMENTED AND DOCUMENTED — NOT RUNTIME VERIFIED.**
Executing it requires a real deployment host.
