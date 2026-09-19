#!/bin/sh
set -e

# Fraud owns its own schema. Migrations run from /app/services/fraud so that
# alembic.ini and the alembic/ directory are found by the alembic CLI.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  cd /app/services/fraud
  alembic upgrade head
  cd /app
fi

exec "$@"