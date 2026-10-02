#!/usr/bin/env bash
# Project Synthesis 17 production deployment (Phase 16).
#
# Pulls a specific immutable image release onto this host and starts it.
# The deployment identity is the commit SHA passed in as $1, never `latest`
# and never `main`.
#
# SAFETY RULES ENFORCED HERE
#   * `docker compose down -v` is never used. Volumes are never removed.
#   * Databases are never recreated, reset, or seeded.
#   * Migrations run through the existing application entrypoint (additive).
#   * Secrets are read from the host's .env file, which is never in git.
#
# Usage: ./deploy/deploy.sh <commit-sha> [--skip-smoke]
set -euo pipefail

cd "$(dirname "$0")/.."

SHA="${1:-}"
SKIP_SMOKE="${2:-}"

if [[ -z "${SHA}" ]]; then
  echo "usage: $0 <commit-sha> [--skip-smoke]" >&2
  exit 2
fi
if [[ ! "${SHA}" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "refusing to deploy '${SHA}': not a commit SHA" >&2
  exit 2
fi

# `docker compose down -v` would destroy the PostgreSQL and Neo4j volumes.
# This is a guard, not a comment: the string is banned in every deploy script.
if grep -rn -- "compose down -v" deploy/ .github/workflows/ 2>/dev/null; then
  echo "FATAL: a destructive 'compose down -v' was found in the deploy path" >&2
  exit 1
fi

COMPOSE_FILES=(-f compose.yaml -f docker-compose.prod.yml)
compose() { docker compose "${COMPOSE_FILES[@]}" "$@"; }

echo "==> Deploying release ${SHA}"

# 1. Record the exact release for auditability and for rollback.
#    HISTORY is append-only, most-recent-last, which is what rollback.sh reads.
mkdir -p deploy
echo "${SHA}" > deploy/CURRENT_RELEASE
if [[ -f deploy/RELEASE_HISTORY ]]; then
  grep -qxF "${SHA}" deploy/RELEASE_HISTORY || echo "${SHA}" >> deploy/RELEASE_HISTORY
else
  echo "${SHA}" > deploy/RELEASE_HISTORY
fi

# 2. Point the application services at the immutable SHA tags.
#    docker-compose.prod.yml reads these three variables.
export PYBANK_BACKEND_IMAGE="${PYBANK_IMAGE_OWNER:-imrohit44}/pybank-backend:${SHA}"
export PYBANK_FRAUD_IMAGE="${PYBANK_IMAGE_OWNER:-imrohit44}/pybank-fraud:${SHA}"
export PYBANK_FRONTEND_IMAGE="${PYBANK_IMAGE_OWNER:-imrohit44}/pybank-frontend:${SHA}"
export APP_VERSION="${SHA}"

# Persist them so `compose up` in a later shell (and the rollback script) use
# the same release.
if [[ -f .env ]]; then
  for var in PYBANK_BACKEND_IMAGE PYBANK_FRAUD_IMAGE PYBANK_FRONTEND_IMAGE APP_VERSION; do
    grep -v "^${var}=" .env > .env.tmp || true
    mv .env.tmp .env
  done
  cat >> .env <<EOF
PYBANK_BACKEND_IMAGE=${PYBANK_BACKEND_IMAGE}
PYBANK_FRAUD_IMAGE=${PYBANK_FRAUD_IMAGE}
PYBANK_FRONTEND_IMAGE=${PYBANK_FRONTEND_IMAGE}
APP_VERSION=${APP_VERSION}
EOF
fi

# 3. GHCR auth. A read-only PAT is stored on the host, never in git.
if [[ -f "$HOME/.docker/config.json" ]] || docker pull --quiet "${PYBANK_BACKEND_IMAGE}" >/dev/null 2>&1; then
  echo "==> Already authenticated to GHCR"
else
  echo "==> ERROR: not authenticated to ${PYBANK_IMAGE_OWNER:-imrohit44}" >&2
  echo "    Run: echo \$GHCR_PAT | docker login ghcr.io -u <github-user> --password-stdin" >&2
  exit 1
fi

# 4. Pull the exact release images. Infrastructure images (postgres, kafka,
#    neo4j, ...) are deliberately NOT re-pulled: compose.yaml pins them by
#    version tag (postgres:18, apache/kafka:3.9.1, neo4j:5.26-community) rather
#    than by digest, so they are reused as-is instead of being upgraded as a
#    side effect of an application deploy. Pinning by digest is a Phase 17
#    supply-chain hardening item, not something Phase 16 changes silently.
echo "==> Pulling release images"
docker compose "${COMPOSE_FILES[@]}" pull --quiet backend fraud frontend

# 5. Apply. `up -d` recreates only services whose image changed. Volumes and
#    databases are untouched.
echo "==> Applying deployment"
compose up -d --remove-orphans

# 6. Wait for health. A deployment is not successful until the app is healthy.
echo "==> Waiting for health checks"
deadline=$(( $(date +%s) + 300 ))
until curl -fsS "http://127.0.0.1:${BACKEND_BIND_PORT:-8000}/health" >/dev/null 2>&1; do
  if (( $(date +%s) > deadline )); then
    echo "ERROR: backend did not become healthy within 300s" >&2
    compose ps
    compose logs --tail 80 backend
    exit 1
  fi
  sleep 5
done

until curl -fsS "http://127.0.0.1:${BACKEND_BIND_PORT:-8000}/ready" >/dev/null 2>&1; do
  if (( $(date +%s) > deadline )); then
    echo "ERROR: backend not ready within 300s" >&2
    compose logs --tail 80 backend
    exit 1
  fi
  sleep 5
done
echo "==> Backend /health and /ready are green"

# 7. Smoke test the real public path (through the proxy, as a user sees it).
if [[ "${SKIP_SMOKE}" != "--skip-smoke" ]]; then
  echo "==> Running deployment smoke test"
  python3 artifacts/phase16/verify_deployment.py
fi

echo "==> Release ${SHA} deployed successfully"
compose ps
