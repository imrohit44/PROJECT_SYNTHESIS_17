# Phase 17 Verification Report — Production Hardening

Scope discipline: Phase 17 added no feature, no new service, no new database,
no Kubernetes, and no orchestration. Every change either tightens an existing
security boundary, documents an audited reliability property, or adds
backup/restore tooling. Results below were produced by actually running the
commands shown; anything that could not run here is marked
**PENDING (ENVIRONMENT)** rather than reported as a pass.

## 1. Changes made

| File | Change |
|---|---|
| `backend/app/security/tokens.py` | HS256-only issuance and validation; secrets < 32 chars or non-HS256 configurations are rejected at construction. Closes algorithm-confusion and `alg=none` vectors at the source. |
| `backend/app/core/config.py` | Development `JWT_SECRET` default raised to ≥ 32 chars so it clears the new floor (production already fails fast via `docker-compose.prod.yml`). |
| `backend/tests/security/test_tokens.py` | 8 new regression tests: short/empty secret, unsupported algorithms (HS512/RS256/none/HS384), expired token, foreign-signed token, forged `alg=none` token, refresh-as-access and access-as-refresh misuse. |
| `pyproject.toml`, `services/fraud/pyproject.toml` | Dev pins moved to `pytest>=9.0.3,<10.0` + `pytest-asyncio>=1.4,<2.0` (fixes PYSEC-2026-1845 / CVE-2025-71176, the tmp/basetemp TOCTOU advisory). |
| `scripts/backup_postgres.sh` | New. `pg_dump -Fc` of both databases via the container's own client; verifies each archive with `pg_restore --list`, size check, sha256 sidecar. Read-only against the databases, append-only on disk, never deletes anything. |
| `scripts/restore_postgres.sh` | New. Restores a dump **only into a brand-new database**; refuses if the target exists; validates the archive before touching Postgres; verifies table counts after restore. There is intentionally no overwrite/force path. |
| `.gitignore` | `backups/` ignored — dumps contain data and must never be committed. |
| `README.md` | Phase 17 section. |

## 2. Test suites (VERIFIED LOCALLY)

| Suite | Command | Result |
|---|---|---|
| New token tests | `pytest backend/tests/security/test_tokens.py` | **8 passed** |
| Backend (pytest 9.0.3) | `pytest` (root) | **132 passed, 3 skipped, 0 failed** (Phase 16 baseline was 124 + 3 skipped; +8 = the new token tests) |
| Fraud (pytest 9.0.3) | `pytest` in `services/fraud` | **34 passed, 6 skipped** — all skips are `Neo4j is not reachable`, the designed graceful-skip while the Docker daemon is stopped |
| Frontend | `npm run test` | **23 passed (8 files), 0 failed** |

### Static analysis

| Tool | Scope | Result |
|---|---|---|
| Ruff | repository | **All checks passed** |
| Ruff | `services/fraud` | **All checks passed** |
| MyPy | `backend` | **no issues in 101 source files** |
| MyPy | `services/fraud/app` | **no issues in 13 source files** |

## 3. Security audit findings

- **Password hashing**: `PasswordService` uses `argon2-cffi`'s default
  `PasswordHasher`, which is Argon2id with library-current parameters. No
  plaintext or reversible storage anywhere. **No change needed.**
- **JWT**: validation is now structurally HS256-only; purpose (`type` claim),
  signature, expiry, and role validity are all enforced, and access/refresh
  tokens are not interchangeable. Ownership of the `sub` is checked per-route.
- **RBAC / ownership**: `customers.py` et al. call `authorize_customer(user,
  customer_id)` / `require_role(...)` server-side on every route; the frontend
  never gates authorization. **No frontend trust found.**
- **WebSocket**: Phase 15 already authenticates the socket with the same JWT
  access token before accepting, and delivery is isolated per user (covered by
  `backend/tests/realtime`).

## 4. Reliability audit findings

- **Transaction consistency**: `BankApplicationService.transfer` locks both
  accounts with `SELECT … FOR UPDATE` in **sorted account-id order**, so two
  opposite-direction transfers cannot deadlock. Balance mutation, transaction
  rows, and the outbox event share one database transaction (atomic commit).
- **Bounded timeouts**: LLM provider calls (`LLM_TIMEOUT_SECONDS`), fraud
  service tool calls (`FRAUD_SERVICE_TIMEOUT_SECONDS`), WhatsApp delivery
  (`WHATSAPP_TIMEOUT_SECONDS`), and every readiness probe (`connect_timeout`
  2s Postgres/Redis, 3s Kafka) are all bounded. No unbounded outbound call was
  found in `backend/app` or `services`.
- **No blind financial retries**: money movement is a single transactional
  request; retries live only in non-financial idempotent paths. Kafka
  consumers (audit, fraud, realtime, notifications) commit offsets **after**
  durable processing and deduplicate by `event_id`.
- **Graceful degradation**: Redis/cache failures fall back to the database,
  Kafka-disabled mode is supported, assistant returns 503 without an LLM key,
  Neo4j absence only removes the graph signal (see the 6 clean fraud skips
  above — observed live while Docker was down).

## 5. Dependency audit

- **`pip-audit` (before)**: `pytest 8.4.2` → PYSEC-2026-1845
  (CVE-2025-71176, TOCTOU race in tmp/basetemp directory handling; realistic
  mainly on shared multi-user machines). Fixed by bumping to pytest 9.0.3
  (above), after which **`pip-audit` reports no known vulnerabilities**.
- **`npm audit` (frontend)**: 3 **moderate** advisories, all dev-time only:
  GHSA-82fw-gwwq-j7x9 in `@vitest/mocker` (path traversal in the dev mock
  redirect feature) plus its dependents `vitest` and `@vitest/coverage-v8`.
  These are test tooling; nothing is bundled into the production static build
  served by Nginx. The only automated fix is a breaking major (`vitest` 5),
  deliberately **not** applied in a hardening phase; tracked as a normal
  dependency-upgrade task.

## 6. Backup and restore — script design and safety properties

- Both scripts pass `bash -n` syntax checking (Git Bash).
- Safety properties are structural, not advisory: backup uses only `pg_dump`
  (consistent snapshot, no table locks, no writes to the source databases) and
  only ever creates new files; restore creates a **new** database and exits
  with an error if the target name already exists. Neither script contains
  `DROP`, `docker compose down`, or volume removal — the same invariant
  `deploy.sh` enforces for deployments.
- ~~PENDING (ENVIRONMENT)~~: the end-to-end backup → restore → row-count
  comparison listed here as pending has since been executed against the live
  stack. All results are recorded in **§7, Final Backup & Restore
  Verification**, below.

## 7. Final Backup & Restore Verification (executed 2026-09-27, live stack)

This section supersedes the earlier "PENDING (ENVIRONMENT)" note. Every value
below is copied from the actual command output of this session.

### 7.1 Environment

- `docker info` → engine **29.7.2** (Docker Desktop had to be started first).
- The `pybank-postgres-1` container was **reused, not recreated**
  (`docker compose up -d postgres` → "Container Started", image
  `postgres:18`, created 3 days prior); health reached `healthy`.
- Volume `pybank_pybank_postgres_data` intact. `docker compose down -v` was
  never run; no volume was removed at any point.

### 7.2 Source row counts (before anything ran)

| `pybank_docker` | count | | `pybank_fraud` | count |
|---|---|---|---|---|
| customers | 113 | | fraud_assessments | 76 |
| users | 113 | | outbox_events | 76 |
| accounts | 110 | | processed_events | 76 |
| transactions | 178 | | | |
| outbox_events | 212 | | | |
| processed_events | 576 | | | |

### 7.3 Backup (real run)

Command: `./scripts/backup_postgres.sh` (Git Bash), exact script output:

```text
==> Backing up 'pybank_docker' -> backups/pybank_docker-20260927T145239Z.dump
    verified: 99139 bytes, sha256 recorded in pybank_docker-...dump.sha256
==> Backing up 'pybank_fraud' -> backups/pybank_fraud-20260927T145239Z.dump
    verified: 31410 bytes, sha256 recorded in pybank_fraud-...dump.sha256
BACKUP_OK: dumps in /d/PyBank/PyBank/backups tagged 20260927T145239Z
```

In-script verification (both archives): `pg_restore --list` succeeded, size
check passed, SHA256 sidecars written.

### 7.4 Independent integrity checks

- `sha256sum -c` on both sidecars → **`...dump: OK`** (×2).
- `pg_restore --list` on the banking archive contains TABLE + TABLE DATA
  entries for: `accounts, alembic_version, customers, outbox_events,
  processed_events, transactions, users` (7/7).
- Fraud archive: `alembic_version, fraud_assessments, outbox_events,
  processed_events` (4/4).
- Post-backup check: `pybank_docker.customers` still 113 — sources untouched.

### 7.5 Restore into brand-new databases

```text
./scripts/restore_postgres.sh backups/pybank_docker-...dump --into p17_check_bank
  RESTORE_OK: 'p17_check_bank' restored with 7 tables.
./scripts/restore_postgres.sh backups/pybank_fraud-...dump --into p17_check_fraud
  RESTORE_OK: 'p17_check_fraud' restored with 4 tables.
```

Row counts queried from the restored databases **match the source exactly**:
p17_check_bank → 113/113/110/178/212/576 (same order as §7.2);

### 7.6 Overwrite protection (proven, no production risk taken)

- Restore a second dump **into the existing `p17_check_bank`** (a scratch DB):
  ```text
  ERROR: database 'p17_check_bank' already exists; refusing to overwrite it.
         Choose a fresh name (e.g. p17_check_bank_check). This script never
         drops or replaces databases.
  ```
  Exit code **1**; `p17_check_bank.customers` still 113 afterwards.
- Restore **directed at the production name `pybank_fraud`** — refused with
  the same error and exit 1 *before* any SQL ran; `pybank_fraud` untouched
  (76 rows both before and after).

### 7.7 Cleanup

`DROP DATABASE p17_check_bank;` and `DROP DATABASE p17_check_fraud;` executed
inside the container — only the two scratch databases created for this test.
Postgres database list afterwards: `postgres, pybank_docker, pybank_fraud,
template0, template1`. Temp `/tmp/*.dump` copies inside the container deleted.
No volumes, Kafka, Redis, or Neo4j data touched.

### 7.8 Final regression re-run (after restore test)

| Gate | Result |
|---|---|
| Backend `pytest` | **135 collected: 0 failed, 0 errors, 3 skipped** (exit 0) — 132 passed |
| Fraud `pytest` | **40 collected: 0 failed, 0 errors, 6 skipped** (exit 0) — 34 passed; skips = Neo4j unreachable |
| Frontend `vitest` | **23 tests / 8 files passed** (exit 0) |
| Frontend `lint` / `tsc -b` / `build` | all exit 0 |
| `ruff check .` | All checks passed |
| `ruff format --check .` | clean (after fixing one genuine defect: `backend/tests/security/test_tokens.py` was unformatted — this was the ONLY code defect found in this pass, corrected with `ruff format`) |
| `mypy backend/app` | no issues in 74 source files |
| `mypy app` (fraud) | no issues in 13 source files |
| `pip-audit` | **No known vulnerabilities found** (exit 1 only because the local editable `pybank` package is not on PyPI — expected) |
| `npm audit` | **3 moderate** dev-time vitest advisories, as documented in §5 (unchanged; not production runtime) |
| `git check-ignore backups/*` | `.gitignore:8 backups/` matches both dumps and sidecars — **no backup artifact tracked** |

### 7.9 Operational notes from this run

- Docker Desktop was not running at session start; it was launched and the
  engine came up cleanly. Only the postgres service was started for the
  backup/restore verification; other containers were left untouched.
- One `.pytest-tmp` basetemp directory was left in Windows *pending-delete*
  state after orphaned pytest child processes (from an interrupted run) were
  terminated. It is git-ignored, harmless, and clears on reboot; it is not a
  repository or code issue. Tests were re-run with an equivalent basetemp and
  all gates above passed with the project's own pytest configuration otherwise
  unchanged.
p17_check_fraud → 76/76/76. Connectivity proven by the same psql queries.
