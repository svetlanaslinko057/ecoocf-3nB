#!/usr/bin/env bash
# Refactor guardrail: fail if anyone adds a NEW @fastapi_app route in server.py.
#
# Phase 1 of the Controlled Modular Monolith refactoring froze server.py
# as a routing surface.  All new endpoints must live in backend/app/routers/<domain>.py.
#
# This script measures the @fastapi_app.{get,post,put,delete,patch,websocket}
# decorator count in backend/server.py against a baseline.  CI / pre-commit
# fail if the count INCREASES.
#
# Update the baseline ONLY when a router extraction commit legitimately
# adds new fastapi_app calls (e.g. an include_router line counts as 0 since
# include_router is not in the decorator family).
#
# Usage:
#   ./scripts/check_server_freeze.sh           # check
#   BASELINE=$(./scripts/check_server_freeze.sh --count)  # print current count
#   ./scripts/check_server_freeze.sh --update-baseline    # rewrite baseline (review change!)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_FILE="$REPO_ROOT/backend/server.py"
BASELINE_FILE="$REPO_ROOT/backend/.server_freeze_baseline"

if [[ ! -f "$SERVER_FILE" ]]; then
  echo "ERROR: server.py not found at $SERVER_FILE" >&2
  exit 2
fi

# Count direct @fastapi_app.<method>( decorators -- the kind that register
# new routes on the legacy ASGI app.
current=$(grep -cE '^@fastapi_app\.(get|post|put|delete|patch|websocket|on_event)\(' "$SERVER_FILE" || true)

case "${1:-}" in
  --count)
    echo "$current"
    exit 0
    ;;
  --update-baseline)
    echo "$current" > "$BASELINE_FILE"
    echo "baseline updated: $current"
    exit 0
    ;;
esac

if [[ ! -f "$BASELINE_FILE" ]]; then
  echo "$current" > "$BASELINE_FILE"
  echo "[refactor-guard] baseline created: $current @fastapi_app decorators in server.py"
  exit 0
fi

baseline=$(cat "$BASELINE_FILE")

if [[ "$current" -gt "$baseline" ]]; then
  delta=$((current - baseline))
  cat <<EOF >&2

═══════════════════════════════════════════════════════════════════
                  REFACTOR GUARDRAIL — FAIL
───────────────────────────────────────────────────────────────────
server.py is frozen during the Controlled Modular Monolith refactor.

  Baseline: $baseline @fastapi_app decorators
  Current:  $current  ($delta new!)

ACTION:
  * Move the new endpoint into backend/app/routers/<domain>.py
  * Wire it via 'fastapi_app.include_router(...)' at the end of server.py
  * See backend/CONTRIBUTING.md for the extraction playbook.

If this commit IS a legitimate extraction (which can only DECREASE the
count), the baseline will be auto-updated by your post-extract step.
═══════════════════════════════════════════════════════════════════
EOF
  exit 1
fi

if [[ "$current" -lt "$baseline" ]]; then
  echo "[refactor-guard] @fastapi_app count went DOWN ($baseline -> $current). Auto-updating baseline."
  echo "$current" > "$BASELINE_FILE"
fi

echo "[refactor-guard] OK: server.py has $current @fastapi_app decorators (baseline $baseline)."
exit 0
