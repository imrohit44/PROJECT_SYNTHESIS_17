#!/usr/bin/env bash
# Project Synthesis 17 PostgreSQL backup (hardening audit: docs/verification/phase-17.md).
#
# Produces logical pg_dump archives of the banking and fraud databases using
# the pg_dump client already present in the postgres container. Because it
# connects over the Compose network as an existing database user, it needs no
# extra tooling on the host and never touches the data volume directly.
#
# SAFETY RULES
#   * READ-ONLY against the databases: pg_dump takes a consistent snapshot
#     without locking tables; nothing is written back.
#   * APPEND-ONLY on disk: every run writes a NEW timestamped file. Existing
#     dumps are never modified or deleted by this script (prune them yourself
#     once you have verified newer copies).
#   * No 'docker compose down', no volume removal, no server restart. The
#     database stays online the whole time.
#
# Usage:
#   ./scripts/backup_postgres.sh [output-directory]
#
# Environment (defaults match compose.yaml):
#   POSTGRES_USER   database role used for pg_dump        (default: pybank)
#   POSTGRES_DB     primary database name                 (default: pybank_docker)
#   FRAUD_DATABASE  fraud database name                   (default: pybank_fraud)
#   PG_BACKUP_DIR   output directory                      (default: backups)
#
# Restore with: ./scripts/restore_postgres.sh <file.dump> --into <new-db>
set -euo pipefail

cd "$(dirname "$0")/.."

PGUSER="${POSTGRES_USER:-pybank}"
PRIMARY_DB="${POSTGRES_DB:-pybank_docker}"
FRAUD_DB="${FRAUD_DATABASE:-pybank_fraud}"
BACKUP_DIR="${1:-${PG_BACKUP_DIR:-backups}}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_DIR}"

if ! docker compose ps postgres >/dev/null 2>&1; then
  echo "ERROR: 'docker compose ps postgres' failed; is the stack up?" >&2
  exit 1
fi

backup_one() {
  local db="$1"
  local file="${BACKUP_DIR}/${db}-${TS}.dump"

  echo "==> Backing up '${db}' -> ${file}"

  # Custom format (-Fc): compressed, parallel-restorable, and verifiable
  # offline with 'pg_restore --list'. --no-owner/--no-privileges keep the
  # archive portable across the dev/prod role layouts.
  docker compose exec -T postgres \
    pg_dump --format=custom --compress=6 --no-owner --no-privileges \
    --dbname="${db}" --username="${PGUSER}" > "${file}"

  # A dump is only trustworthy if pg_restore can read its table of contents.
  if ! docker compose exec -T postgres \
      pg_restore --list < "${file}" > /dev/null; then
    echo "ERROR: ${file} failed pg_restore --list verification" >&2
    exit 1
  fi

  local size
  size="$(wc -c < "${file}" | tr -d ' ')"
  if [[ "${size}" -lt 100 ]]; then
    echo "ERROR: ${file} is suspiciously small (${size} bytes)" >&2
    exit 1
  fi

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" > "${file}.sha256"
    echo "    verified: ${size} bytes, sha256 recorded in ${file}.sha256"
  else
    echo "    verified: ${size} bytes"
  fi
}

# Back up each distinct database exactly once (the names can coincide when
# banking and fraud share a single database).
DATABASES=("${PRIMARY_DB}")
if [[ "${FRAUD_DB}" != "${PRIMARY_DB}" ]]; then
  DATABASES+=("${FRAUD_DB}")
fi

for db in "${DATABASES[@]}"; do
  backup_one "${db}"
done

echo
echo "BACKUP_OK: dumps in $(cd "${BACKUP_DIR}" && pwd) tagged ${TS}"
echo "Restore into an isolated new database with:"
echo "  ./scripts/restore_postgres.sh ${PRIMARY_DB}-${TS}.dump --into <new-db-name>"