#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SIZE="${1:-full}"
DASHBOARD_PORT="${2:-63105}"
EXECUTION_MODE="${3:-native-only}"
PUBLICATION_GATE_PURPOSE="${4:-release-sample}"
ONLINE_FEEDBACK_MODE="${SAGE_ONLINE_FEEDBACK_MODE:-audited}"
if [[ "$SIZE" != "full" && "$SIZE" != "dev10" && "$SIZE" != "dev30" ]]; then
  echo "Run size must be full, dev10, or dev30." >&2
  exit 2
fi
case "$SIZE" in
  full) EXPECTED_TASKS=1032 ;;
  dev10) EXPECTED_TASKS=10 ;;
  dev30) EXPECTED_TASKS=30 ;;
esac
readonly EXPECTED_TASKS
if [[ "$EXECUTION_MODE" != "native-only" && "$EXECUTION_MODE" != "frozen-only" && "$EXECUTION_MODE" != "development-only" && "$EXECUTION_MODE" != "development-transfer" ]]; then
  echo "Execution mode must be native-only, frozen-only, development-only, or development-transfer." >&2
  exit 2
fi
if [[ "$SIZE" != "full" && "$EXECUTION_MODE" != "development-only" && "$EXECUTION_MODE" != "development-transfer" ]]; then
  echo "Development cohorts require execution mode development-only." >&2
  exit 2
fi
if [[ ( "$EXECUTION_MODE" == "development-only" || "$EXECUTION_MODE" == "development-transfer" ) && "$SIZE" == "full" ]]; then
  echo "Development execution modes cannot run the publication cohort." >&2
  exit 2
fi
if [[ "$EXECUTION_MODE" == "development-transfer" && "$SIZE" != "dev30" ]]; then
  echo "development-transfer is defined only for the disjoint dev30 cohort." >&2
  exit 2
fi
if [[ "$PUBLICATION_GATE_PURPOSE" != "release-sample" && "$PUBLICATION_GATE_PURPOSE" != "campaign-inclusion" && "$PUBLICATION_GATE_PURPOSE" != "development-diagnostic" ]]; then
  echo "Gate purpose must be release-sample, campaign-inclusion, or development-diagnostic." >&2
  exit 2
fi
if [[ "$ONLINE_FEEDBACK_MODE" != "audited" && "$ONLINE_FEEDBACK_MODE" != "actor-visible-only" ]]; then
  echo "SAGE_ONLINE_FEEDBACK_MODE must be audited or actor-visible-only." >&2
  exit 2
fi
if [[ "$ONLINE_FEEDBACK_MODE" == "actor-visible-only" && "$EXECUTION_MODE" != "native-only" ]]; then
  echo "actor-visible-only feedback is valid only for generation-enabled native-only runs." >&2
  exit 2
fi
if [[ -n "${SAGE_HYPOTHESIS_PILOT_MANIFEST:-}" ]]; then
  if [[ "$SIZE" != "full" || "$EXECUTION_MODE" != "native-only" || "$PUBLICATION_GATE_PURPOSE" != "campaign-inclusion" ]]; then
    echo "Hypothesis-pilot H2 requires: full, native-only, and campaign-inclusion." >&2
    exit 2
  fi
fi
if [[ "$SIZE" == "full" && "$EXECUTION_MODE" == "native-only" && "$PUBLICATION_GATE_PURPOSE" == "campaign-inclusion" && "$ONLINE_FEEDBACK_MODE" == "actor-visible-only" ]]; then
  if [[ -z "${SAGE_HYPOTHESIS_PILOT_MANIFEST:-}" || ! -f "$SAGE_HYPOTHESIS_PILOT_MANIFEST" ]]; then
    echo "Actor-visible H2 campaign inclusion requires SAGE_HYPOTHESIS_PILOT_MANIFEST." >&2
    exit 2
  fi
fi
if [[ ( "$EXECUTION_MODE" == "development-only" || "$EXECUTION_MODE" == "development-transfer" ) && "$PUBLICATION_GATE_PURPOSE" != "development-diagnostic" ]]; then
  echo "Development cohorts require gate purpose development-diagnostic." >&2
  exit 2
fi
if [[ "$EXECUTION_MODE" != "development-only" && "$EXECUTION_MODE" != "development-transfer" && "$PUBLICATION_GATE_PURPOSE" == "development-diagnostic" ]]; then
  echo "Gate purpose development-diagnostic requires a development execution mode." >&2
  exit 2
fi
if [[ -n "${RESUME_RUN_ROOT:-}" || -n "${RESUME_COMPLETED_LIMIT:-}" ]]; then
  echo "Publication runs must start all task rows fresh; partial-row resume is forbidden." >&2
  exit 2
fi
if [[ "$EXECUTION_MODE" != "frozen-only" && -n "${RESUME_REGISTRY_CHECKPOINT:-}" ]]; then
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

if [[ -n "${SAGE_HYPOTHESIS_PILOT_MANIFEST:-}" ]]; then
  "$PYTHON_EXECUTABLE" - "$SAGE_HYPOTHESIS_PILOT_MANIFEST" \
    "$PUBLICATION_GIT_COMMIT" "$PUBLICATION_GIT_TREE" <<'PY'
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1]).resolve()
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
provenance = payload.get("provenance")
h2 = payload.get("h2")
if not isinstance(provenance, dict) or not isinstance(h2, dict):
    raise SystemExit("Hypothesis-pilot manifest provenance/state is malformed.")
if provenance.get("git_commit") != sys.argv[2] or provenance.get("git_tree") != sys.argv[3]:
    raise SystemExit("Hypothesis-pilot Git identity differs from the H2 source checkout.")
if provenance.get("git_status") != "clean":
    raise SystemExit("Hypothesis-pilot manifest does not lock a clean Git source.")
if payload.get("status") != "running" or h2.get("status") != "running":
    raise SystemExit("Hypothesis-pilot H2 must be marked running before launch.")
for hypothesis in ("h1", "h3", "h4"):
    state = payload.get(hypothesis)
    if not isinstance(state, dict) or state.get("status") != "pending":
        raise SystemExit(
            "Hypothesis-pilot H2 requires all later phases to remain pending."
        )
if not str(payload.get("pilot_id") or "").strip():
    raise SystemExit("Hypothesis-pilot manifest has no pilot ID.")
PY
  echo "hypothesis_pilot_git_binding=pass"
fi

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
pin_publication_env TZ "America/New_York"
export TOOLSANDBOX_RAPID_CACHE_MODE="read_only"
export TOOLSANDBOX_RAPID_CACHE_PATH="${TOOLSANDBOX_RAPID_CACHE_PATH:-artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json}"
PINNED_RAPID_FIXTURE_SHA256="eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
PINNED_BENCHMARK_SHA256="21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
VALIDATION_THRESHOLDS="docs/sage_protocol/publication_validation_thresholds_v4.json"
LIFECYCLE_FAULT_FIXTURE="docs/sage_protocol/fixtures/historical_faulty_safe_action_registry.json"
PINNED_LIFECYCLE_FAULT_FIXTURE_SHA256="7677756340ccde07c5edb7b43003f68b5f363611d2cd935afdc7363e3bc33e8a"
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

if [[ "$EXECUTION_MODE" == "development-only" || "$EXECUTION_MODE" == "development-transfer" ]]; then
  DEFAULT_RUN_STAMP="lifecycle_repair_${SIZE}_$(date +%Y%m%d_%H%M%S)"
  DEFAULT_OUTPUT_ROOT="outputs/lifecycle_repair"
  DEFAULT_ARTIFACT_ROOT="artifacts/lifecycle_repair"
else
  DEFAULT_RUN_STAMP="publication_fresh_$(date +%Y%m%d_%H%M%S)"
  DEFAULT_OUTPUT_ROOT="outputs/publication_validation"
  DEFAULT_ARTIFACT_ROOT="artifacts/publication_validation"
fi
RUN_STAMP="${SAGE_RUN_STAMP:-$DEFAULT_RUN_STAMP}"
OUTPUT_ROOT="${SAGE_OUTPUT_ROOT:-$DEFAULT_OUTPUT_ROOT/$RUN_STAMP}"
ARTIFACT_ROOT="${SAGE_ARTIFACT_ROOT:-$DEFAULT_ARTIFACT_ROOT/$RUN_STAMP}"
if [[ "$EXECUTION_MODE" == "development-only" ]]; then
  DEFAULT_MANIFEST="docs/sage_protocol/manifests/lifecycle_repair_${SIZE}.json"
elif [[ "$EXECUTION_MODE" == "development-transfer" ]]; then
  DEFAULT_MANIFEST="docs/sage_protocol/manifests/lifecycle_repair_transfer_dev30.json"
else
  DEFAULT_MANIFEST="docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
fi
MANIFEST="${SAGE_BENCHMARK_MANIFEST:-$DEFAULT_MANIFEST}"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Required publication benchmark is missing: $MANIFEST" >&2
  exit 1
fi
MANIFEST_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$MANIFEST")"
if [[ "$EXECUTION_MODE" != "development-only" && "$EXECUTION_MODE" != "development-transfer" && "$MANIFEST_SHA256" != "$PINNED_BENCHMARK_SHA256" ]]; then
  echo "Publication benchmark hash mismatch: expected $PINNED_BENCHMARK_SHA256, observed $MANIFEST_SHA256" >&2
  exit 1
fi

if [[ "$EXECUTION_MODE" == "native-only" ]]; then
  ARM="native_action"
  RUN_MODE="online_build_full"
  GENERATION="on"
  SAGE_POLICY="self-evolving-praxis"
  if [[ "$ONLINE_FEEDBACK_MODE" == "actor-visible-only" ]]; then
    REFLECTION_EXPECTATION="actor-visible-only"
  else
    REFLECTION_EXPECTATION="same-run-fresh"
  fi
elif [[ "$EXECUTION_MODE" == "frozen-only" ]]; then
  ARM="frozen_registry"
  RUN_MODE="full_benchmark"
  GENERATION="off"
  SAGE_POLICY="none"
  REFLECTION_EXPECTATION="not-applicable"
elif [[ "$EXECUTION_MODE" == "development-transfer" ]]; then
  ARM="lifecycle_repair_transfer_diagnostic"
  RUN_MODE="transfer_30"
  GENERATION="off"
  SAGE_POLICY="none"
  REFLECTION_EXPECTATION="not-applicable"
else
  ARM="lifecycle_repair_diagnostic"
  RUN_MODE="online_build_full"
  GENERATION="on"
  SAGE_POLICY="self-evolving-praxis"
  REFLECTION_EXPECTATION="same-run-fresh"
fi

ARM_OUTPUT="$OUTPUT_ROOT/$ARM"
ARM_ARTIFACTS="$ARTIFACT_ROOT/${ARM}_artifacts"
REGISTRY_DIR="$ARTIFACT_ROOT/${ARM}_registry"
COMMAND_FILE="$ARTIFACT_ROOT/${ARM}_command.txt"
LOG_FILE="$ARTIFACT_ROOT/${ARM}.log"
STUDY_FILE="$ARTIFACT_ROOT/study_manifest.txt"
mkdir -p "$ARM_ARTIFACTS" "$(dirname "$COMMAND_FILE")" "$ARM_OUTPUT"

LIFECYCLE_FAULT_FIXTURE_SHA256=""
LIFECYCLE_CONTRACT_RECEIPT=""
LIFECYCLE_CONTRACT_RECEIPT_SHA256=""
DEVELOPMENT_FAULT_INJECTION="false"
REGISTRY_TRANSFER_SOURCE_RUN=""
if [[ "$EXECUTION_MODE" == "frozen-only" ]]; then
  SOURCE_REGISTRY="${RESUME_REGISTRY_CHECKPOINT:-}"
  if [[ -z "$SOURCE_REGISTRY" || ! -f "$SOURCE_REGISTRY/registry_manifest.json" ]]; then
    echo "frozen-only requires RESUME_REGISTRY_CHECKPOINT with a registry manifest." >&2
    exit 1
  fi
  if [[ -e "$REGISTRY_DIR" || -L "$REGISTRY_DIR" ]]; then
    echo "Frozen publication registry target must not exist before its checkpoint is installed: $REGISTRY_DIR" >&2
    exit 1
  fi
  mkdir -p "$REGISTRY_DIR"
  cp -R "$SOURCE_REGISTRY"/. "$REGISTRY_DIR"/
elif [[ "$EXECUTION_MODE" == "development-transfer" ]]; then
  REGISTRY_TRANSFER_SOURCE_RUN="${LIFECYCLE_TRANSFER_SOURCE_RUN:-}"
  if [[ -z "$REGISTRY_TRANSFER_SOURCE_RUN" ]]; then
    echo "development-transfer requires LIFECYCLE_TRANSFER_SOURCE_RUN." >&2
    exit 1
  fi
  REGISTRY_TRANSFER_SOURCE_RUN="$("$PYTHON_EXECUTABLE" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$REGISTRY_TRANSFER_SOURCE_RUN")"
  if [[ ! -f "$REGISTRY_TRANSFER_SOURCE_RUN/protocol_manifest.json" || ! -f "$REGISTRY_TRANSFER_SOURCE_RUN/lifecycle_repair_validation_report.json" ]]; then
    echo "Transfer source must be the exact completed dev10 run root." >&2
    exit 1
  fi
  "$PYTHON_EXECUTABLE" scripts/verify_lifecycle_repair_run.py \
    --search-root "$REGISTRY_TRANSFER_SOURCE_RUN" --expected-tasks 10
  SOURCE_REGISTRY="$("$PYTHON_EXECUTABLE" -c 'import json, pathlib, sys; p=pathlib.Path(sys.argv[1]); raw=pathlib.Path(json.loads(p.read_text())["registry_dir"]); print((raw if raw.is_absolute() else pathlib.Path.cwd() / raw).resolve())' "$REGISTRY_TRANSFER_SOURCE_RUN/protocol_manifest.json")"
  if [[ ! -f "$SOURCE_REGISTRY/registry_manifest.json" ]]; then
    echo "Passing dev10 source does not contain its declared final registry." >&2
    exit 1
  fi
  if [[ -e "$REGISTRY_DIR" || -L "$REGISTRY_DIR" ]]; then
    echo "Development transfer registry target must not exist: $REGISTRY_DIR" >&2
    exit 1
  fi
  mkdir -p "$REGISTRY_DIR"
  cp -R "$SOURCE_REGISTRY"/. "$REGISTRY_DIR"/
elif [[ "$EXECUTION_MODE" == "development-only" ]]; then
  DEVELOPMENT_FAULT_INJECTION="true"
  if [[ -e "$REGISTRY_DIR" || -L "$REGISTRY_DIR" ]]; then
    echo "Development registry directory must not exist before its pinned fault fixture is installed: $REGISTRY_DIR" >&2
    exit 1
  fi
  if [[ ! -f "$LIFECYCLE_FAULT_FIXTURE" ]]; then
    echo "Required development-only lifecycle fixture is missing: $LIFECYCLE_FAULT_FIXTURE" >&2
    exit 1
  fi
  LIFECYCLE_FAULT_FIXTURE_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$LIFECYCLE_FAULT_FIXTURE")"
  if [[ "$LIFECYCLE_FAULT_FIXTURE_SHA256" != "$PINNED_LIFECYCLE_FAULT_FIXTURE_SHA256" ]]; then
    echo "Lifecycle fault fixture hash mismatch: expected $PINNED_LIFECYCLE_FAULT_FIXTURE_SHA256, observed $LIFECYCLE_FAULT_FIXTURE_SHA256" >&2
    exit 1
  fi
  mkdir -p "$REGISTRY_DIR"
  cp "$LIFECYCLE_FAULT_FIXTURE" "$REGISTRY_DIR/registry_manifest.json"
  LIFECYCLE_CONTRACT_RECEIPT="$ARM_ARTIFACTS/historical_validation_contract_binding.json"
  PYTHONPATH="src:." "$PYTHON_EXECUTABLE" \
    scripts/seed_lifecycle_validation_contract.py \
    --registry-dir "$REGISTRY_DIR" \
    --fixture "$LIFECYCLE_FAULT_FIXTURE" \
    --receipt "$LIFECYCLE_CONTRACT_RECEIPT"
  LIFECYCLE_CONTRACT_RECEIPT_SHA256="$("$PYTHON_EXECUTABLE" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$LIFECYCLE_CONTRACT_RECEIPT")"
elif [[ -e "$REGISTRY_DIR" || -L "$REGISTRY_DIR" ]]; then
  echo "Online publication registry directory must not exist: $REGISTRY_DIR" >&2
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
  --online-feedback-mode "$ONLINE_FEEDBACK_MODE"
  --control-cache off
  --require-fresh-control
  --publication-gate-purpose "$PUBLICATION_GATE_PURPOSE"
  --parallel-arms
  --validated-external-fixture "$TOOLSANDBOX_RAPID_CACHE_PATH"
  --validated-external-fixture-sha256 "$PINNED_RAPID_FIXTURE_SHA256"
  --freeze-toolsandbox-clock
  --dashboard-port "$DASHBOARD_PORT"
  --output-root "$ARM_OUTPUT"
  --artifact-root "$ARM_ARTIFACTS"
)
if [[ -n "${SAGE_HYPOTHESIS_PILOT_MANIFEST:-}" ]]; then
  CMD+=(--hypothesis-pilot-manifest "$SAGE_HYPOTHESIS_PILOT_MANIFEST")
fi
if [[ "$EXECUTION_MODE" == "development-only" ]]; then
  CMD+=(
    --allow-low-quality-cohort
    --development-validation-contract-receipt "$LIFECYCLE_CONTRACT_RECEIPT"
    --development-validation-contract-receipt-sha256 "$LIFECYCLE_CONTRACT_RECEIPT_SHA256"
  )
elif [[ "$EXECUTION_MODE" == "development-transfer" ]]; then
  CMD+=(
    --allow-low-quality-cohort
    --registry-transfer-source-run "$REGISTRY_TRANSFER_SOURCE_RUN"
  )
fi
{
  echo "study_id=${SIZE}_$RUN_STAMP"
  echo "arm=$ARM"
  echo "generation=$GENERATION"
  echo "sage_policy=$SAGE_POLICY"
  echo "actor_selection_mode=policy"
  echo "control_condition=matched_policy_wrapper_without_generated_tools"
  echo "control_agent_runtime=sage_wrapped"
  echo "control_generated_tools_enabled=false"
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
  echo "publication_gate_purpose=$PUBLICATION_GATE_PURPOSE"
  echo "reflection_control=$REFLECTION_EXPECTATION"
  echo "online_feedback_mode=$ONLINE_FEEDBACK_MODE"
  echo "hypothesis_pilot_manifest=${SAGE_HYPOTHESIS_PILOT_MANIFEST:-}"
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
  echo "timezone=$TZ"
  echo "sage_task_cache=off"
  echo "cross_run_failure_memory=off"
  echo "diagnostic_force_calls=off"
  echo "rapid_fixture_mode=$TOOLSANDBOX_RAPID_CACHE_MODE"
  echo "rapid_fixture_path=$TOOLSANDBOX_RAPID_CACHE_PATH"
  echo "rapid_fixture_sha256=$RAPID_FIXTURE_SHA256"
  echo "resume_registry_checkpoint=${RESUME_REGISTRY_CHECKPOINT:-}"
  echo "development_fault_injection=$DEVELOPMENT_FAULT_INJECTION"
  echo "development_fault_fixture=$([[ "$DEVELOPMENT_FAULT_INJECTION" == "true" ]] && echo "$LIFECYCLE_FAULT_FIXTURE" || true)"
  echo "development_fault_fixture_sha256=$LIFECYCLE_FAULT_FIXTURE_SHA256"
  echo "development_validation_contract_receipt=$LIFECYCLE_CONTRACT_RECEIPT"
  echo "development_validation_contract_receipt_sha256=$LIFECYCLE_CONTRACT_RECEIPT_SHA256"
  echo "registry_transfer_source_run=$REGISTRY_TRANSFER_SOURCE_RUN"
  printf 'command='
  printf '%q ' "${CMD[@]}"
  printf '\n'
} > "$COMMAND_FILE"
cp "$COMMAND_FILE" "$STUDY_FILE"

echo "Starting strict fresh-control run: ${SIZE}_$RUN_STAMP"
echo "[$ARM] output: $ARM_OUTPUT"
echo "[$ARM] log: $LOG_FILE"
"${CMD[@]}" 2>&1 | tee "$LOG_FILE"

if [[ "$EXECUTION_MODE" == "development-only" || "$EXECUTION_MODE" == "development-transfer" ]]; then
  "$PYTHON_EXECUTABLE" scripts/verify_lifecycle_repair_run.py \
    --search-root "$ARM_OUTPUT" \
    --expected-tasks "$EXPECTED_TASKS" | tee -a "$LOG_FILE"
else
  "$PYTHON_EXECUTABLE" scripts/verify_publication_run.py \
    --search-root "$ARM_OUTPUT" \
    --expected-tasks "$EXPECTED_TASKS" \
    --expect-reflection "$REFLECTION_EXPECTATION" \
    --gate-purpose "$PUBLICATION_GATE_PURPOSE" | tee -a "$LOG_FILE"
  if [[ "$EXECUTION_MODE" == "native-only" && "$PUBLICATION_GATE_PURPOSE" == "release-sample" ]]; then
    "$PYTHON_EXECUTABLE" scripts/verify_publication_sample.py \
      --search-root "$ARM_OUTPUT" \
      --thresholds "$VALIDATION_THRESHOLDS" | tee -a "$LOG_FILE"
  fi
fi
echo "Strict fresh-control run complete: ${SIZE}_$RUN_STAMP"
