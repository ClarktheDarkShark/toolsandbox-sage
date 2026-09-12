#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="src:."
PYTHON_EXECUTABLE="$ROOT_DIR/.venv-publication/bin/python"
if [[ ! -x "$PYTHON_EXECUTABLE" ]]; then
  echo "Publication Python is missing: $PYTHON_EXECUTABLE" >&2
  exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" && -f ".secrets/env.sh" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".secrets/env.sh"
  set +a
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required." >&2
  exit 1
fi

for diagnostic_name in \
  SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME \
  SAGE_DIAGNOSTIC_FORCE_TOOL_NAME \
  SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR \
  SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL; do
  if [[ -n "${!diagnostic_name:-}" ]]; then
    echo "Diagnostic tool forcing is forbidden: $diagnostic_name" >&2
    exit 1
  fi
done

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  echo "The native baseline requires a clean, committed tree." >&2
  git status --short >&2
  exit 1
fi

export TOOL_SANDBOX_FIXED_NOW_TIMESTAMP="1784832588"
export TOOLSANDBOX_RAPID_CACHE_MODE="read_only"
export TOOLSANDBOX_RAPID_CACHE_PATH="$ROOT_DIR/artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
export CONTROL_CACHE="off"
unset CONTROL_CACHE_ROOT
unset SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT
unset SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY
export SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS="4"
export TZ="America/New_York"
export PYTHONUNBUFFERED="1"

RUN_STAMP="${PURE_BASELINE_RUN_STAMP:-pure_toolsandbox_baseline_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_ROOT="${PURE_BASELINE_OUTPUT_ROOT:-$ROOT_DIR/outputs/pure_toolsandbox_baseline/$RUN_STAMP}"
MANIFEST="$ROOT_DIR/docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
COMPARISON_RUN="${PURE_BASELINE_COMPARISON_RUN:-$ROOT_DIR/outputs/chapter4_evidence/chapter4_final_policy_online_frozen_20260911_4ce1c6d/technical_replacement/frozen/rep01/frozen_registry/full_benchmark_20260912_083006/control/full_benchmark_control_agent_gpt-4o-mini_user_gpt-4o-mini_09_12_2026_08_30_18}"
DASHBOARD_PORT="${1:-64620}"

if [[ ! -f "$COMPARISON_RUN/result_summary.json" ]]; then
  echo "SAGE-wrapped comparison run is missing: $COMPARISON_RUN" >&2
  exit 1
fi

echo "Starting pure ToolSandbox baseline: $RUN_STAMP"
echo "Output: $OUTPUT_ROOT"
echo "Dashboard: http://127.0.0.1:$DASHBOARD_PORT/dashboard/task_compare.html"
exec "$PYTHON_EXECUTABLE" scripts/run_pure_toolsandbox_baseline.py \
  --manifest "$MANIFEST" \
  --fixture "$TOOLSANDBOX_RAPID_CACHE_PATH" \
  --output-root "$OUTPUT_ROOT" \
  --comparison-run "$COMPARISON_RUN" \
  --dashboard-port "$DASHBOARD_PORT" \
  --agent gpt-4o-mini \
  --user gpt-4o-mini
