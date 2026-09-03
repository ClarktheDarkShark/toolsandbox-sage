#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SIZE="${1:-full}"
DASHBOARD_PORT="${2:-63105}"
EXECUTION_MODE="${3:-native-only}"
if [[ "$SIZE" != "full" ]]; then
  echo "Only the complete 1,032-task publication cohort is supported." >&2
  exit 2
fi
if [[ "$EXECUTION_MODE" != "native-only" && "$EXECUTION_MODE" != "frozen-only" ]]; then
  echo "Execution mode must be native-only or frozen-only." >&2
  exit 2
fi
if [[ -n "${RESUME_RUN_ROOT:-}" || -n "${RESUME_COMPLETED_LIMIT:-}" ]]; then
  echo "Publication runs must start all task rows fresh; partial-row resume is forbidden." >&2
  exit 2
fi
if [[ "$EXECUTION_MODE" == "native-only" && -n "${RESUME_REGISTRY_CHECKPOINT:-}" ]]; then
  echo "Online publication runs must start with an empty registry; a registry checkpoint is forbidden." >&2
  exit 2
fi

# Verify the exact environment under the same import path used by the run.
# This makes stale repository-local package metadata fail before any output or
# model request is created.
export PYTHONPATH="src:."
PYTHON_ON_PATH="$(command -v python || true)"
if [[ -z "$PYTHON_ON_PATH" ]]; then
  echo "python was not found on PATH; activate the exact publication environment." >&2
  exit 1
fi
PYTHON_EXECUTABLE="$("$PYTHON_ON_PATH" -c 'import sys; print(sys.executable)')"
PUBLICATION_ENVIRONMENT_LOCK="$ROOT_DIR/requirements-publication-lock.txt"
PUBLICATION_ENVIRONMENT_REPORT="$("$PYTHON_EXECUTABLE" scripts/verify_publication_environment.py \
  --lock "$PUBLICATION_ENVIRONMENT_LOCK" --json)"
PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256="$("$PYTHON_EXECUTABLE" -c 'import json, sys; print(json.load(sys.stdin)["external_distribution_sha256"])' <<< "$PUBLICATION_ENVIRONMENT_REPORT")"
PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT="$("$PYTHON_EXECUTABLE" -c 'import json, sys; print(json.load(sys.stdin)["external_distribution_count"])' <<< "$PUBLICATION_ENVIRONMENT_REPORT")"
echo "publication_environment_verification=pass"
echo "external_distribution_count=$PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT"
echo "external_distribution_sha256=$PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256"
PUBLICATION_PYTHON_VERSION="$("$PYTHON_EXECUTABLE" -c 'import platform; print(platform.python_version())')"
PUBLICATION_PYTHON_PREFIX="$("$PYTHON_EXECUTABLE" -c 'import sys; print(sys.prefix)')"
PUBLICATION_PYTHON_BASE_PREFIX="$("$PYTHON_EXECUTABLE" -c 'import sys; print(sys.base_prefix)')"
PUBLICATION_PYTHON_IMPLEMENTATION="$("$PYTHON_EXECUTABLE" -c 'import platform; print(platform.python_implementation())')"
PUBLICATION_PLATFORM_SYSTEM="$("$PYTHON_EXECUTABLE" -c 'import platform; print(platform.system())')"
PUBLICATION_PLATFORM_MACHINE="$("$PYTHON_EXECUTABLE" -c 'import platform; print(platform.machine())')"
PUBLICATION_ENVIRONMENT_LOCK_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$PUBLICATION_ENVIRONMENT_LOCK")"
readonly PYTHON_EXECUTABLE
readonly PUBLICATION_PYTHON_VERSION
readonly PUBLICATION_PYTHON_PREFIX
readonly PUBLICATION_PYTHON_BASE_PREFIX
readonly PUBLICATION_PYTHON_IMPLEMENTATION
readonly PUBLICATION_PLATFORM_SYSTEM
readonly PUBLICATION_PLATFORM_MACHINE
readonly PUBLICATION_ENVIRONMENT_LOCK
readonly PUBLICATION_ENVIRONMENT_LOCK_SHA256
readonly PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256
readonly PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT

if ! command -v git >/dev/null 2>&1 || ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Publication runs require a Git checkout with a resolvable HEAD." >&2
  exit 1
fi
GIT_STATUS="$(git status --porcelain --untracked-files=all)"
if [[ -n "$GIT_STATUS" ]]; then
  echo "Publication runs require a clean Git tree. Commit or remove these changes:" >&2
  echo "$GIT_STATUS" >&2
  exit 1
fi
PUBLICATION_GIT_COMMIT="$(git rev-parse --verify HEAD)"
PUBLICATION_GIT_TREE="$(git rev-parse "${PUBLICATION_GIT_COMMIT}^{tree}")"
readonly PUBLICATION_GIT_COMMIT
readonly PUBLICATION_GIT_TREE

# Verify the tracked release chain: immutable P0 inputs, checkpoint policy
# amendment, benchmark, fixture, thresholds, and historical analysis references.
"$PYTHON_EXECUTABLE" scripts/verify_publication_inputs.py

if [[ -z "${OPENAI_API_KEY:-}" && -f ".secrets/env.sh" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".secrets/env.sh"
  set +a
fi

# Diagnostic exposure/force flags change which tools can be surfaced or called.
# They are forbidden, rather than silently ignored, in every publication arm.
DIAGNOSTIC_FORCE_ENV_VARS=(
  SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME
  SAGE_DIAGNOSTIC_FORCE_TOOL_NAME
  SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR
  SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL
)
for diagnostic_name in "${DIAGNOSTIC_FORCE_ENV_VARS[@]}"; do
  diagnostic_value="${!diagnostic_name-}"
  if [[ "$diagnostic_value" =~ [^[:space:]] ]]; then
    echo "Publication runs forbid active diagnostic force variable $diagnostic_name." >&2
    exit 1
  fi
done
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required." >&2
  exit 1
fi

export SAGE_PUBLICATION_PYTHON_EXECUTABLE="$PYTHON_EXECUTABLE"
export SAGE_PUBLICATION_PYTHON_VERSION="$PUBLICATION_PYTHON_VERSION"
export SAGE_PUBLICATION_PYTHON_PREFIX="$PUBLICATION_PYTHON_PREFIX"
export SAGE_PUBLICATION_PYTHON_BASE_PREFIX="$PUBLICATION_PYTHON_BASE_PREFIX"
export SAGE_PUBLICATION_PYTHON_IMPLEMENTATION="$PUBLICATION_PYTHON_IMPLEMENTATION"
export SAGE_PUBLICATION_PLATFORM_SYSTEM="$PUBLICATION_PLATFORM_SYSTEM"
export SAGE_PUBLICATION_PLATFORM_MACHINE="$PUBLICATION_PLATFORM_MACHINE"
export SAGE_PUBLICATION_ENVIRONMENT_LOCK="$PUBLICATION_ENVIRONMENT_LOCK"
export SAGE_PUBLICATION_ENVIRONMENT_LOCK_SHA256="$PUBLICATION_ENVIRONMENT_LOCK_SHA256"
export SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256="$PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256"
export SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT="$PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT"
export SAGE_PUBLICATION_GIT_COMMIT="$PUBLICATION_GIT_COMMIT"
export SAGE_PUBLICATION_GIT_TREE="$PUBLICATION_GIT_TREE"
PINNED_FIXED_NOW_TIMESTAMP="1784832588"
if [[ -n "${TOOL_SANDBOX_FIXED_NOW_TIMESTAMP:-}" && "$TOOL_SANDBOX_FIXED_NOW_TIMESTAMP" != "$PINNED_FIXED_NOW_TIMESTAMP" ]]; then
  echo "Publication runs require TOOL_SANDBOX_FIXED_NOW_TIMESTAMP=$PINNED_FIXED_NOW_TIMESTAMP exactly." >&2
  exit 1
fi
export TOOL_SANDBOX_FIXED_NOW_TIMESTAMP="$PINNED_FIXED_NOW_TIMESTAMP"

pin_publication_env() {
  local name="$1"
  local expected="$2"
  local observed="${!name-}"
  if [[ -n "$observed" && "$observed" != "$expected" ]]; then
    echo "Publication runs require $name=$expected exactly." >&2
    exit 1
  fi
  export "$name=$expected"
}

# Preserve the operational policy used by the historical launcher and make
# every wrapper/SDK retry layer and timeout explicit. No inherited shell value
# may silently alter a publication run.
pin_publication_env SAGE_OPENAI_MAX_RETRIES "5"
pin_publication_env SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS "1,3"
pin_publication_env SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS "1,3"
pin_publication_env SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS "4"
pin_publication_env SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS "120"
pin_publication_env SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS "600"
export TOOLSANDBOX_RAPID_CACHE_MODE="read_only"
export TOOLSANDBOX_RAPID_CACHE_PATH="${TOOLSANDBOX_RAPID_CACHE_PATH:-artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json}"
PINNED_RAPID_FIXTURE_SHA256="eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
PINNED_BENCHMARK_SHA256="21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
export CONTROL_CACHE="off"
unset CONTROL_CACHE_ROOT
unset SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT
unset SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY

if [[ ! -f "$TOOLSANDBOX_RAPID_CACHE_PATH" ]]; then
  echo "Required read-only RapidAPI fixture is missing: $TOOLSANDBOX_RAPID_CACHE_PATH" >&2
  exit 1
fi
RAPID_FIXTURE_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$TOOLSANDBOX_RAPID_CACHE_PATH")"
if [[ "$RAPID_FIXTURE_SHA256" != "$PINNED_RAPID_FIXTURE_SHA256" ]]; then
  echo "RapidAPI fixture hash mismatch: expected $PINNED_RAPID_FIXTURE_SHA256, observed $RAPID_FIXTURE_SHA256" >&2
  exit 1
fi

RUN_STAMP="${SAGE_RUN_STAMP:-publication_fresh_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_ROOT="${SAGE_OUTPUT_ROOT:-outputs/publication_validation/$RUN_STAMP}"
ARTIFACT_ROOT="${SAGE_ARTIFACT_ROOT:-artifacts/publication_validation/$RUN_STAMP}"
MANIFEST="${SAGE_BENCHMARK_MANIFEST:-docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json}"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Required publication benchmark is missing: $MANIFEST" >&2
  exit 1
fi
MANIFEST_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$MANIFEST")"
if [[ "$MANIFEST_SHA256" != "$PINNED_BENCHMARK_SHA256" ]]; then
  echo "Publication benchmark hash mismatch: expected $PINNED_BENCHMARK_SHA256, observed $MANIFEST_SHA256" >&2
  exit 1
fi

if [[ "$EXECUTION_MODE" == "native-only" ]]; then
  ARM="native_action"
  RUN_MODE="online_build_full"
  GENERATION="on"
  SAGE_POLICY="self-evolving-praxis"
  REFLECTION_EXPECTATION="same-run-fresh"
else
  ARM="frozen_registry"
  RUN_MODE="full_benchmark"
  GENERATION="off"
  SAGE_POLICY="none"
  REFLECTION_EXPECTATION="not-applicable"
fi

ARM_OUTPUT="$OUTPUT_ROOT/$ARM"
ARM_ARTIFACTS="$ARTIFACT_ROOT/${ARM}_artifacts"
REGISTRY_DIR="$ARTIFACT_ROOT/${ARM}_registry"
COMMAND_FILE="$ARTIFACT_ROOT/${ARM}_command.txt"
LOG_FILE="$ARTIFACT_ROOT/${ARM}.log"
STUDY_FILE="$ARTIFACT_ROOT/study_manifest.txt"
mkdir -p "$ARM_ARTIFACTS" "$(dirname "$COMMAND_FILE")" "$ARM_OUTPUT"

if [[ "$EXECUTION_MODE" == "frozen-only" ]]; then
  SOURCE_REGISTRY="${RESUME_REGISTRY_CHECKPOINT:-}"
  if [[ -z "$SOURCE_REGISTRY" || ! -f "$SOURCE_REGISTRY/registry_manifest.json" ]]; then
    echo "frozen-only requires RESUME_REGISTRY_CHECKPOINT with a registry manifest." >&2
    exit 1
  fi
  if [[ ! -f "$REGISTRY_DIR/registry_manifest.json" ]]; then
    mkdir -p "$REGISTRY_DIR"
    cp -R "$SOURCE_REGISTRY"/. "$REGISTRY_DIR"/
  fi
elif [[ -f "$REGISTRY_DIR/registry_manifest.json" ]]; then
  echo "Online publication registry must start empty: $REGISTRY_DIR" >&2
  exit 1
fi

CMD=(
  "$PYTHON_EXECUTABLE" scripts/run_sage_protocol.py
  --mode "$RUN_MODE"
  --manifest "$MANIFEST"
  --registry-dir "$REGISTRY_DIR"
  --sage-policy "$SAGE_POLICY"
  --agent gpt-4o-mini
  --user gpt-4o-mini
  --generation-model gpt-4o-mini
  --generation "$GENERATION"
  --control-cache off
  --require-fresh-control
  --validated-external-fixture "$TOOLSANDBOX_RAPID_CACHE_PATH"
  --validated-external-fixture-sha256 "$PINNED_RAPID_FIXTURE_SHA256"
  --freeze-toolsandbox-clock
  --dashboard-port "$DASHBOARD_PORT"
  --output-root "$ARM_OUTPUT"
  --artifact-root "$ARM_ARTIFACTS"
)
if [[ "${SAGE_BATCH_NO_DASHBOARD_OPEN:-0}" == "1" ]]; then
  CMD+=(--no-dashboard-open)
fi
{
  echo "study_id=full_$RUN_STAMP"
  echo "arm=$ARM"
  echo "generation=$GENERATION"
  echo "sage_policy=$SAGE_POLICY"
  echo "run_mode=$RUN_MODE"
  echo "model=gpt-4o-mini"
  echo "python_executable=$PYTHON_EXECUTABLE"
  echo "python_version=$PUBLICATION_PYTHON_VERSION"
  echo "python_prefix=$PUBLICATION_PYTHON_PREFIX"
  echo "python_base_prefix=$PUBLICATION_PYTHON_BASE_PREFIX"
  echo "python_implementation=$PUBLICATION_PYTHON_IMPLEMENTATION"
  echo "platform_system=$PUBLICATION_PLATFORM_SYSTEM"
  echo "platform_machine=$PUBLICATION_PLATFORM_MACHINE"
  echo "environment_lock=$PUBLICATION_ENVIRONMENT_LOCK"
  echo "environment_lock_sha256=$PUBLICATION_ENVIRONMENT_LOCK_SHA256"
  echo "external_distribution_count=$PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT"
  echo "external_distribution_sha256=$PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256"
  echo "git_commit=$PUBLICATION_GIT_COMMIT"
  echo "git_tree=$PUBLICATION_GIT_TREE"
  echo "git_status=clean"
  echo "manifest=$MANIFEST"
  echo "manifest_sha256=$MANIFEST_SHA256"
  echo "fixed_now=$TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"
  echo "control_cache=off"
  echo "fresh_control_required=true"
  echo "reflection_control=$REFLECTION_EXPECTATION"
  echo "openai_response_cache=off"
  echo "openai_response_cache_scope=persistent_repository_whole_response_replay"
  echo "persistent_generation_output_cache=off"
  echo "generator_contract_and_repair_analysis_memoization=within_run_only"
  echo "openai_provider_prompt_prefix_cache=automatic_implicit"
  echo "openai_max_retries=$SAGE_OPENAI_MAX_RETRIES"
  echo "openai_transient_retry_delays_seconds=$SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS"
  echo "generation_transient_retry_delays_seconds=$SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS"
  echo "transient_scenario_retry_attempts=$SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS"
  echo "openai_request_timeout_seconds=$SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS"
  echo "generation_openai_request_timeout_seconds=$SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS"
  echo "sage_task_cache=off"
  echo "cross_run_failure_memory=off"
  echo "diagnostic_force_calls=off"
  echo "rapid_fixture_mode=$TOOLSANDBOX_RAPID_CACHE_MODE"
  echo "rapid_fixture_path=$TOOLSANDBOX_RAPID_CACHE_PATH"
  echo "rapid_fixture_sha256=$RAPID_FIXTURE_SHA256"
  echo "resume_registry_checkpoint=${RESUME_REGISTRY_CHECKPOINT:-}"
  printf 'command='
  printf '%q ' "${CMD[@]}"
  printf '\n'
} > "$COMMAND_FILE"
cp "$COMMAND_FILE" "$STUDY_FILE"

echo "Starting strict fresh-control publication run: full_$RUN_STAMP"
echo "[$ARM] output: $ARM_OUTPUT"
echo "[$ARM] log: $LOG_FILE"
"${CMD[@]}" 2>&1 | tee "$LOG_FILE"

"$PYTHON_EXECUTABLE" scripts/verify_publication_run.py \
  --search-root "$ARM_OUTPUT" \
  --expected-tasks 1032 \
  --expect-reflection "$REFLECTION_EXPECTATION" | tee -a "$LOG_FILE"
echo "Strict fresh-control publication run complete: full_$RUN_STAMP"
