# Phase 6 Architecture

Phase 6 makes PyBank safer to change. The goal is a deliberate feedback system, not a high test count.

## Testing pyramid

```text
                E2E
             few smoke tests
                ^
                |
          integration tests
          API + persistence
                ^
                |
            unit tests
        fast isolated logic
```

Most coverage stays in unit tests because they are fast and deterministic. Integration tests prove layer contracts. E2E tests stay small because browser tests are slower and more fragile.

## Backend tests

- `backend/tests/domain`: unit tests for framework-independent banking invariants.
- `backend/tests/security`: authentication, authorization, ownership, token, and rate-limit regressions.
- `backend/tests/api`: FastAPI contract tests through the application layer.
- `backend/tests/persistence`: persistence behavior using an isolated local test database file for fast feedback.
- `backend/tests/integration/persistence`: PostgreSQL-specific tests, skipped unless `PYBANK_TEST_DATABASE_URL` is set.

Pytest markers classify tests as `unit`, `integration`, `security`, and `e2e`.

## Database isolation

Fast local integration tests create a fresh database under pytest `tmp_path`, build schema metadata, and discard the file after the test. Tests do not depend on records created by earlier tests.

PostgreSQL tests require `PYBANK_TEST_DATABASE_URL`. The fixture refuses to run unless the URL contains both `pybank` and `test`, then recreates the `public` schema before and after the suite. This prevents accidental mutation of a normal developer database.

## PostgreSQL strategy

SQLite is not treated as equivalent to PostgreSQL. It is used for fast API feedback only. PostgreSQL-specific tests cover numeric behavior, foreign keys, transactions, and row locking with real PostgreSQL when the test database is available.

## Fixtures and factories

Shared fixtures create:

- application services
- isolated test clients
- registered users
- issued access/refresh tokens
- authenticated request headers

Factories are intentionally small functions with overridable defaults. Business logic stays in the application and domain layers.

## Frontend tests

Vitest uses jsdom, React Testing Library, and V8 coverage. Tests focus on visible behavior and boundaries:

- login success and safe failures
- logout and expired session handling
- protected route redirect
- API error envelope handling
- React Query loading, error, and mutation invalidation

## E2E strategy

Playwright is not added in this phase because it would require browser binaries and orchestration that are better introduced with the Docker phase. The target smoke suite for Phase 7+ is:

- register, login, dashboard
- login, account, deposit, verify balance
- login, transfer, verify account and transaction state
- customer blocked from admin page

Until then, E2E is documented as a manual quality-gate step, not faked.

## Coverage

Backend coverage uses `pytest-cov` with branch coverage and excludes tests. The initial backend threshold is 60 percent.

Frontend coverage uses Vitest V8 coverage. Initial thresholds are deliberately modest: lines/functions/statements 20 percent, branches 15 percent.

Coverage is a signal, not proof. PyBank prioritizes failure paths, security paths, ownership, rollback, and money movement over artificial 100 percent coverage.

## Static quality

Backend gate:

```powershell
python -m pytest
python -m pytest --cov=backend --cov-report=term-missing
ruff check .
ruff format --check .
python -m mypy backend
```

Frontend gate:

```powershell
cd frontend
npm test
npm run test:coverage
npm run lint
npm run typecheck
npm run build
```

E2E gate is `NOT VERIFIED` until Playwright is introduced.

## Phase 16 readiness

Phase 16 CI/CD can invoke these same commands directly. No GitHub Actions, Docker CI, cloud runners, or deployment automation are introduced in Phase 6.
