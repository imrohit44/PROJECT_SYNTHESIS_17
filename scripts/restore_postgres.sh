#!/usr/bin/env bash
# PyBank PostgreSQL restore (Phase 17).
#
# Restores a pg_dump archive produced by scripts/backup_postgres.sh INTO A NEW,
# PREVIOUSLY NON-EXISTENT DATABASE inside the postgres container. This is a
# verification/inspection tool by design: it proves backups are restorable and
# lets you query the restored data, without any chance of clobbering the live
# databases.
#
# SAFETY RULES
#   * The target database must NOT already exist. If it does, the script
#     refuses and exits; it never DROPs, overwrites, or disconnects anything.
#   * No 'docker compose down', no volume removal, no destructive reset of
#     any kind. The live pybank/pybank_fraud databases are not touched.
#   * Promotion of a restored database into service is a deliberate,
#     separate, human decision -- there is intentionally no --force flag here.
#
# Usage:
#   ./scripts/restore_postgres.sh <file.dump> --into <new-database-name>
#
# Environment (defaults match compose.yaml):
#   POSTGRES_USER  role used to create the database (default: pybank)
set -euo pipefail

cd "$(dirname "$0")/.."

PGUSER="${POSTGRES_USER:-pybank}"

DUMP="${1:-}"
INTO="${2:-}"
if [[ "${INTO}" == "--into" ]]; then
  INTO="${3:-}"
fi

if [[ -z "${DUMP}" || -z "${INTO}" || "${INTO}" == "--into" ]]; then
  echo "usage: $0 <file.dump> --into <new-database-name>" >&2
  exit 2
fi
if [[ ! -f "${DUMP}" ]]; then
  echo "ERROR: dump file '${DUMP}' not found" >&2
  exit 2
fi
# Database names are interpolated into SQL; restrict them to a safe charset.
if [[ ! "${INTO}" =~ ^[a-z_][a-z0-9_]{0,62}$ ]]; then
  echo "ERROR: target name '${INTO}' must be [a-z_][a-z0-9_]* (max 63 chars)" >&2
  exit 2
fi
# The archive must at least be readable by pg_restore before touching Postgres.
if ! docker compose exec -T postgres pg_restore --list < "${DUMP}" > /dev/null; then
  echo "ERROR: ${DUMP} is not a readable pg_dump archive" >&2
  exit 1
fi

exists() {
  docker compose exec -T postgres \
    psql -tAq -U "${PGUSER}" -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname = '${INTO}'" | tr -d '[:space:]'
}

if [[ "$(exists)" == "1" ]]; then
  echo "ERROR: database '${INTO}' already exists; refusing to overwrite it." >&2
  echo "       Choose a fresh name (e.g. ${INTO}_check). This script never" >&2
  echo "       drops or replaces databases." >&2
  exit 1
fi

echo "==> Creating isolated database '${INTO}' and restoring ${DUMP}"
docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "${PGUSER}" -d postgres \
  -c "CREATE DATABASE ${INTO} OWNER ${PGUSER}"

docker compose exec -T postgres \
  pg_restore -v -e --no-owner --no-privileges \
  -U "${PGUSER}" -d "${INTO}" < "${DUMP}"

# Post-restore sanity: the restored schema must actually contain tables.
TABLES="$(docker compose exec -T postgres psql -tAq -U "${PGUSER}" -d "${INTO}" \
  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'" \
  | tr -d '[:space:]')"
if [[ -z "${TABLES}" || "${TABLES}" == "0" ]]; then
  echo "ERROR: restored database '${INTO}' contains no public tables" >&2
  exit 1
fi

echo
echo "RESTORE_OK: '${INTO}' restored with ${TABLES} tables."
echo "Inspect it without touching production data, e.g.:"
echo "  docker compose exec -T postgres psql -U ${PGUSER} -d ${INTO} -c '\\dt'"