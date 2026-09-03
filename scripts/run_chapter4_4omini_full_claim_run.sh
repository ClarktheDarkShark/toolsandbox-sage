#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_LABEL="${1:-chapter4_4omini_full}"
DASHBOARD_PORT="${2:-63105}"
SAFE_LABEL="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9_-' '_' | sed 's/^_//; s/_$//')"
export SAGE_RUN_STAMP="${SAFE_LABEL}_$(date +%Y%m%d_%H%M%S)"
export SAGE_OUTPUT_ROOT="${SAGE_OUTPUT_ROOT:-outputs/chapter4_4omini_full_runs/$SAGE_RUN_STAMP}"
export SAGE_ARTIFACT_ROOT="${SAGE_ARTIFACT_ROOT:-artifacts/chapter4_4omini_full_runs/$SAGE_RUN_STAMP}"

exec bash scripts/run_native_action_4omini_ab.sh \
  full \
  "$DASHBOARD_PORT" \
  native-only
