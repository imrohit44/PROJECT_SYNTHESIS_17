#!/usr/bin/env bash
# PyBank production rollback (Phase 16).
#
# Re-deploys a previously released commit SHA. Because deployment identity is
# the immutable SHA, a rollback is the exact same operation as a forward deploy
# -- there is no separate rollback mechanism to get wrong.
#
# Usage:
#   ./deploy/rollback.sh                 # roll back to the previous release
#   ./deploy/rollback.sh <commit-sha>    # roll back to a specific release
set -euo pipefail

cd "$(dirname "$0")/.."

HISTORY_FILE="deploy/RELEASE_HISTORY"
CURRENT_FILE="deploy/CURRENT_RELEASE"

if [[ ! -f "${HISTORY_FILE}" ]]; then
  echo "ERROR: ${HISTORY_FILE} not found; cannot determine a previous release" >&2
  exit 1
fi

CURRENT="$(cat "${CURRENT_FILE}" 2>/dev/null || true)"

if [[ -n "${1:-}" ]]; then
  TARGET="$1"
else
  # History is append-only and most-recent-last; the previous release is the
  # entry immediately before the current one.
  TARGET="$(grep -v "^${CURRENT}$" "${HISTORY_FILE}" | tail -n 1)"
fi

if [[ -z "${TARGET}" ]]; then
  echo "ERROR: no previous release to roll back to" >&2
  exit 1
fi

echo "==> Rolling back ${CURRENT:-unknown} -> ${TARGET}"

# Record the rollback as a new history entry so the sequence stays auditable.
echo "${TARGET}" >> "${HISTORY_FILE}"

exec ./deploy/deploy.sh "${TARGET}" "${2:-}"
