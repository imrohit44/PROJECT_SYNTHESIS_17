# Phase 17 — Final Repository Forensic Cleanup

Release-readiness audit of every tracked file (284 files at `d12b614`).
Objective: remove only files that are demonstrably generated, temporary,
debug-only, duplicated, or obsolete. Conservative rule applied throughout:
if a file's necessity could not be proven unnecessary, it was kept.

## Verdict

**No tracked file was deleted.** Every tracked file was traced to a concrete
purpose: runtime, development, testing, deployment, CI, migration history,
or documented verification/learning material. The tracked tree contains no
secrets, caches, dumps, build output, IDE metadata, or scratch files
(`git ls-files` grep for `.env`, `*.log`, `*.dump`, `*.pyc`, `node_modules`,
`dist/`, `build/`, `egg-info`, IDE/OS metadata: zero hits).

## Candidates examined and why each was KEPT

| Candidate | Suspicion | Evidence found | Action |
|---|---|---|---|
| `docker/smoke-test.ps1`, `cache-benchmark.ps1`, `event-flow-check.ps1`, `kafka-failure-recovery-check.ps1`, `duplicate-event-check.ps1` | One-off scripts | Explicitly invoked in `docs/architecture/phase-7.md`, `phase-8.md`, `phase-9.md` as the documented verification procedures | KEEP |
| `docker/cache-invalidation-check.ps1` | No doc citation found | Same class of Phase-8 runtime verification tooling as the five above; docs cover cache invalidation (`phase-8.md` "Invalidation"); script is intentional educational evidence | KEEP (uncertain → conservative) |
| `backend/tests/test_health.py` | Overlaps `test_api.py` health assertion | Step 17 mandate: tests are not deletable; both pass and are cheap | KEEP |
| `backend/tests/observability/test_metrics.py` vs `test_observability.py` | Suspected duplicates | Disjoint scope: counters/gauge vs correlation/JSON logs/readiness | KEEP |
| `services/fraud/models/fraud_model.joblib` | Binary artifact | Runtime dependency loaded by the fraud service; paired metadata JSON | KEEP |
| `services/fraud/ml/dataset.py` | Possibly unused | Imported by `ml/evaluate.py`; re-exports `FEATURE_COLUMNS` contract used at runtime via `ml/features.py` | KEEP |
| All 8 Alembic migrations (4 backend + 4 fraud) | Schema already applied elsewhere | Migration history is immutable project history | KEEP |
| `deploy/deploy.sh`, `health.sh`, `rollback.sh`, `deploy/nginx/pybank.conf` | Rarely executed | Wired into `.github/workflows/deploy-ec2.yml`, `deploy.sh`, README, Phase-16 docs | KEEP |
| `scripts/backup_postgres.sh`, `scripts/restore_postgres.sh` | Rarely executed | Documented in README and this verification trail; restore refuses overwrite by design | KEEP |
| Root `Dockerfile`, `docker/backend-entrypoint.sh`, `docker/fraud-entrypoint.sh`, `frontend/Dockerfile`, `services/fraud/Dockerfile` | Possibly redundant | Built by `compose.yaml`, `ci.yml` image job, and `docker-publish.yml`; entrypoints COPY'd as image ENTRYPOINTs | KEEP |
| `docs/architecture/*`, `docs/learning/*`, `docs/verification/*` | Not required to run | Intentional learning/architecture/verification record — the project's stated purpose | KEEP |
| Frontend pages/components | Unused exports? | All 12 pages imported and routed in `App.tsx`; no orphaned modules | KEEP |

## Debug-leftover sweep

Tracked-source searches: `pdb`, `breakpoint(`, `console.log(` → zero hits.
`TODO/FIXME/HACK/XXX` → zero hits (one base64 false positive in
`package-lock.json` integrity hash). `print(` (`ruff T201`, not part of the
project rule set) → two hits in `services/fraud/ml/train.py` / `evaluate.py`
CLI `main()` entry points, which intentionally emit JSON to stdout → kept.

## Local (git-ignored) items

Removed from disk: `.pytest-tmp-phase14/`, `.pytest-tmp-phase14-final/`
(one-off Phase-14 basetemp scratch; proven unreferenced except in
historical verification text). Preserved per audit policy: `artifacts/`
(phase evidence referenced by docs), `backups/` (ignored, local only),
`.pytest-tmp/` (configured pytest basetemp; Windows pending-delete zombie,
documented above in `phase-17.md`, auto-purged by pytest).
`git check-ignore` confirms all of `.venv`, caches, `artifacts/`,
`backups/`, `pybank.egg-info/`, `.coverage`, `.pytest-tmp*/` are ignored.

## Post-cleanup validation (all re-run after removals)

| Check | Command | Result |
|---|---|---|
| Backend tests | `pytest --junitxml` | 135 tests: 132 passed, 3 skipped, 0 failures |
| Fraud tests | `pytest --junitxml` (in `services/fraud`) | 40 tests: 34 passed, 6 skipped (Neo4j down), 0 failures |
| Frontend tests | `npm test -- --run` | 8 files / 23 tests passed |
| Frontend lint | `npm run lint` | exit 0 |
| TypeScript | `npx tsc -b` | exit 0 |
| Build | `npm run build` | exit 0 |
| Ruff | `ruff check .` / `ruff format --check .` | all checks passed; 186 files formatted |
| Ruff (fraud cwd) | `ruff check .` / `format --check` in `services/fraud` | passed; 33 files formatted |
| MyPy backend | `mypy backend/app` | Success, 74 files |
| MyPy fraud | `mypy app` (in `services/fraud`, per CI) | Success, 13 files |
| Compose (dev) | `docker compose config --quiet` | exit 0 |
| Compose (prod) | `docker compose -f compose.yaml -f docker-compose.prod.yml config --quiet` (dummy secrets) | exit 0 |
| Hygiene | `git status --short`, `git diff --check` | clean / exit 0 |

Note: the prod stack is validated as the documented two-file overlay
(`compose.yaml` + `docker-compose.prod.yml`), which is how CI
(`ci.yml` line 183) and `deploy/deploy.sh` invoke it. `docker-compose.prod.yml`
is a merge overlay (`!reset` tags) and is not valid standalone by design.
