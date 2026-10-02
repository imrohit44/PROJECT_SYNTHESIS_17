#!/usr/bin/env bash
# Project Synthesis 17 production health check (Phase 16).
#
# Read-only. Safe to run at any time; starts nothing, changes nothing.
# Checks liveness (/health) and readiness (/ready) separately, because they
# mean different things and a green liveness with a red readiness is a real
# state that should be reported as such.
#
# Usage: ./deploy/health.sh
set -uo pipefail

cd "$(dirname "$0")/.."

BACKEND="http://127.0.0.1:${BACKEND_BIND_PORT:-8000}"
FAILURES=0

# The fraud service publishes no host port in production (it is private), and
# the name `fraud` only resolves inside the Compose network, so it is reached
# with `docker compose exec` rather than by publishing a port just to make a
# script work. Exposing it to make monitoring easier would defeat the point of
# keeping it private.
fraud_probe() {
  local path="$1"
  local code
  code="$(docker compose exec -T fraud \
    python -c "
import sys, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8001${path}', timeout=10) as r:
        print(r.status)
except Exception:
    print(000)
" 2>/dev/null | tr -d '\r' | tail -n 1)"
  [[ -z "${code}" ]] && code=000
  echo "${code}"
}

check_code() {
  local name="$1" url="$2" code="$3"
  if [[ "${code}" == "200" ]]; then
    printf '  OK    %-22s %s -> %s\n' "${name}" "${url}" "${code}"
  else
    printf '  FAIL  %-22s %s -> %s\n' "${name}" "${url}" "${code}"
    FAILURES=$((FAILURES + 1))
  fi
}

check() {
  local name="$1" url="$2"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${url}" 2>/dev/null || echo 000)"
  if [[ "${code}" == "200" ]]; then
    printf '  OK    %-22s %s -> %s\n' "${name}" "${url}" "${code}"
  else
    printf '  FAIL  %-22s %s -> %s\n' "${name}" "${url}" "${code}"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "Project Synthesis 17 deployment health"
echo
echo "Application (loopback only):"
check "banking /health"  "${BACKEND}/health"
check "banking /ready"   "${BACKEND}/ready"
check_code "fraud /health" "fraud:8001/health" "$(fraud_probe /health)"
check_code "fraud /ready"  "fraud:8001/ready"  "$(fraud_probe /ready)"

echo
echo "Public surface (through the reverse proxy):"
# The certificate is issued for the real domain, so probing https://localhost/
# would fail on hostname verification for a reason that has nothing to do with
# the application's health. Verify the real origin when the operator supplies
# it, and say so plainly when it is not configured.
if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
  check "https root"            "https://${PUBLIC_DOMAIN}/"
  check "https /api/v1/health"  "https://${PUBLIC_DOMAIN}/api/v1/health"
else
  printf '  SKIP  public HTTPS checks (set PUBLIC_DOMAIN to verify)\n'
fi

echo
echo "Internal services must NOT be reachable from the public internet."
for port in 5432 6379 9092 7687 7474 9090 3000 16686; do
  if timeout 3 bash -c "</dev/tcp/127.0.0.1/${port}" 2>/dev/null; then
    printf '  FAIL  port %s is open on the host\n' "${port}"
    FAILURES=$((FAILURES + 1))
  else
    printf '  OK    port %s is closed\n' "${port}"
  fi
done

echo
if [[ "${FAILURES}" -eq 0 ]]; then
  echo "DEPLOY_HEALTH_OK: true"
  exit 0
fi
echo "DEPLOY_HEALTH_OK: false (${FAILURES} failed check(s))"
exit 1
