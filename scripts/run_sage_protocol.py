#!/usr/bin/env python3
# mypy: ignore-errors
"""Run paired ToolSandbox SAGE mechanism/transfer/extended-reuse gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import traceback
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Callable, cast

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import (
    InventoryAuthorityError,
    SageRunConfig,
    run_sage_with_registry,
)
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.campaign.artifacts import (
    append_event,
    initialize_campaign,
    record_run,
    snapshot_registry,
    update_task,
)
from sage_ts.config.models import DEFAULT_MODEL, paired_model_metadata
from sage_ts.config.splits import load_split_names, scenario_records
from sage_ts.dashboard.exporters import (
    open_dashboard,
    write_protocol_dashboard,
)
from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.helper_contribution import write_helper_contribution_summary
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from sage_ts.evaluation.run_metrics import compare_runs
from sage_ts.evaluation.task_strata import cohort_policy_report
from sage_ts.generation.tool_generator import ToolGenerator
from sage_ts.orchestration.self_evolution_reflection import (
    FRESH_CONTROL_COMPLETE_EVENT,
    FRESH_CONTROL_ERROR_EVENT,
    FRESH_CONTROL_ROW_EVENT,
)
from sage_ts.registry.content_identity import registry_content_identity
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY

# Run modes are also split names. Keep these explicit so bad campaign labels
# fail early, but support campaign-sized protocol runs directly.
MODES = (
    # Smoke / wiring checks
    "smoke_6",
    "smoke_12",
    # Mechanism / tool-birth checks
    "viability_12",
    "mechanism_12",
    "mechanism_40",
    "mechanism_60",
    "online_build_100",
    "online_build_250",
    "online_build_500",
    "online_build_full",
    # Frozen transfer checks
    "transfer_40",
    "transfer_60",
    "transfer_100",
    # Confirmation / validation
    "extended_reuse_100",
    "confirm_100",
    "validate_100",
    "promotion_250",
    "validate_250",
    "full_benchmark",
)

SAGE_POLICY_NONE = "none"
SAGE_POLICY_AUTO = "auto"
SAGE_POLICY_SELF_EVOLVING_PRAXIS = "self-evolving-praxis"
SAGE_POLICIES = (
    SAGE_POLICY_AUTO,
    SAGE_POLICY_NONE,
    SAGE_POLICY_SELF_EVOLVING_PRAXIS,
)
ACTOR_SELECTION_MODES = ("policy", "auto")
SELF_EVOLVING_PRAXIS_ENV_DEFAULTS = {
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP = 1784832588
PUBLICATION_ENVIRONMENT_LOCK = "requirements-publication-lock.txt"
PUBLICATION_EXECUTION_ENV = {
    "TZ": "America/New_York",
    "SAGE_OPENAI_MAX_RETRIES": "5",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}
PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256 = (
    "5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f"
)
_PUBLICATION_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")


def _candidate_arm_name(actor_selection_mode: str) -> str:
    return "sage_auto_selection" if actor_selection_mode == "auto" else "candidate"


def _candidate_arm_root(run_root: Path, actor_selection_mode: str) -> Path:
    return run_root / _candidate_arm_name(actor_selection_mode)


def _candidate_generation_enabled(
    generation_enabled: bool,
    inventory_authority_replay_dir: Path | str | None,
) -> bool:
    return generation_enabled and inventory_authority_replay_dir is None


def _apply_sage_policy_preset(policy: str) -> dict[str, dict[str, str]]:
    """Apply a named SAGE runtime policy without overriding explicit env values."""

    if policy == SAGE_POLICY_NONE:
        return {}
    if policy == SAGE_POLICY_SELF_EVOLVING_PRAXIS:
        defaults = SELF_EVOLVING_PRAXIS_ENV_DEFAULTS
    else:
        raise ValueError(f"Unknown SAGE policy preset: {policy}")
    applied: dict[str, dict[str, str]] = {}
    for key, desired_value in defaults.items():
        existing = os.environ.get(key)
        if existing is None:
            os.environ[key] = desired_value
            applied[key] = {
                "value": desired_value,
                "source": "preset_default",
            }
        else:
            applied[key] = {
                "value": existing,
                "source": "preexisting_environment",
            }
    return applied


def _resolve_sage_policy_preset(
    requested_policy: str,
    *,
    generation_enabled: bool,
) -> str:
    """Resolve auto policy without changing frozen validation behavior."""

    if requested_policy != SAGE_POLICY_AUTO:
        return requested_policy
    if generation_enabled:
        return SAGE_POLICY_SELF_EVOLVING_PRAXIS
    return SAGE_POLICY_NONE


def _manifest_type(manifest: Path) -> str:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("manifest_type", ""))


def _generation_enabled_by_default(mode: str, manifest_type: str) -> bool:
    """Default live generation for build/discovery lanes, not frozen validation."""

    generation_modes = {
        "smoke_6",
        "smoke_12",
        "viability_12",
        "mechanism_12",
        "mechanism_40",
        "mechanism_60",
        "online_build_100",
        "online_build_250",
        "online_build_500",
        "online_build_full",
        "extended_reuse_100",
    }
    if mode in generation_modes:
        return True
    return "discovery" in manifest_type.lower()


def _is_frozen_transfer_mode(mode: str) -> bool:
    """Modes that should default to generation disabled."""

    frozen_modes = {
        "transfer_40",
        "transfer_60",
        "transfer_100",
        "confirm_100",
        "validate_100",
        "promotion_250",
        "validate_250",
        "full_benchmark",
    }
    return mode in frozen_modes


def _manifest_split_for_mode(mode: str) -> str:
    """Map run modes to manifest split names.

    ``full_benchmark`` remains a frozen validation mode, so the generation-enabled
    whole-dataset build lane uses its own mode name while reading the same sealed
    manifest split.
    """

    if mode in {
        "online_build_100",
        "online_build_250",
        "online_build_500",
        "online_build_full",
    }:
        return "full_benchmark"
    return mode


def _scenario_limit_for_mode(mode: str) -> int | None:
    if mode == "online_build_100":
        return 100
    if mode == "online_build_250":
        return 250
    if mode == "online_build_500":
        return 500
    return None


DIAGNOSTIC_FORCE_ENV_VARS = (
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)


def _active_diagnostic_force_env(env: dict[str, str] | None = None) -> dict[str, str]:
    env = env or os.environ
    return {
        name: value
        for name in DIAGNOSTIC_FORCE_ENV_VARS
        if (value := str(env.get(name, "")).strip())
    }


def _redacted_run_affecting_sage_env() -> dict[str, str]:
    blocked_tokens = ("API", "KEY", "TOKEN", "SECRET")
    values: dict[str, str] = {}
    for name, value in sorted(os.environ.items()):
        if not name.startswith("SAGE_") and name != "TZ":
            continue
        if any(token in name.upper() for token in blocked_tokens):
            values[name] = "<redacted>"
        else:
            values[name] = value
    return values


def _looks_like_openai_model(model: str) -> bool:
    name = model.strip().lower()
    return name.startswith(("gpt-", "o1", "o3", "o4"))


def _preflight_openai_api_key(
    *,
    agent_model: str,
    user_model: str,
    generation_model: str,
    generation_enabled: bool,
) -> None:
    """Fail before task execution if an OpenAI-backed run has no API key."""

    requires_openai = (
        _looks_like_openai_model(agent_model)
        or _looks_like_openai_model(user_model)
        or (generation_enabled and _looks_like_openai_model(generation_model))
    )
    if not requires_openai:
        return
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key.strip():
        raise SystemExit(
            "OPENAI_API_KEY is required for this OpenAI-backed run but is "
            "missing or blank. Aborting before task execution."
        )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _arm_status_path(run_root: Path, arm: str) -> Path:
    return run_root / f"{arm}_arm_status.json"


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_arm_status(
    run_root: Path,
    arm: str,
    *,
    status: str,
    run_dir: Path | None = None,
    completed_count: int | None = None,
    scenario_count: int | None = None,
    error: str | None = None,
    process_pid: int | None = None,
) -> None:
    path = _arm_status_path(run_root, arm)
    prior = _read_arm_status(run_root, arm)
    now = datetime.now().astimezone().isoformat()
    now_monotonic_ns = time.monotonic_ns()
    payload: dict[str, object] = {
        "arm": arm,
        "status": status,
        "process_pid": prior.get("process_pid") or process_pid or os.getpid(),
        "started_at": prior.get("started_at") or now,
        "started_monotonic_ns": prior.get("started_monotonic_ns") or now_monotonic_ns,
        "updated_at": now,
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir)
    if completed_count is not None:
        payload["completed_count"] = completed_count
    if scenario_count is not None:
        payload["scenario_count"] = scenario_count
    if error is not None:
        payload["error"] = error
    if status not in {"starting", "running"}:
        payload["completed_at"] = now
        payload["completed_monotonic_ns"] = now_monotonic_ns
    _atomic_write_json(path, payload)


def _read_arm_status(run_root: Path, arm: str) -> dict[str, Any]:
    path = _arm_status_path(run_root, arm)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return cast(dict[str, Any], payload) if isinstance(payload, dict) else {}


def _parallel_arm_execution_record(run_root: Path) -> dict[str, Any]:
    statuses = {
        arm: _read_arm_status(run_root, arm) for arm in ("control", "candidate")
    }
    intervals: dict[str, tuple[int, int]] = {}
    arms: dict[str, dict[str, Any]] = {}
    for arm, status in statuses.items():
        if status.get("status") != "complete":
            raise ValueError(
                f"Parallel {arm} arm did not preserve complete terminal status."
            )
        pid = status.get("process_pid")
        started = status.get("started_monotonic_ns")
        completed = status.get("completed_monotonic_ns")
        if (
            isinstance(pid, bool)
            or not isinstance(pid, int)
            or pid <= 0
            or isinstance(started, bool)
            or not isinstance(started, int)
            or isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed <= started
        ):
            raise ValueError(f"Parallel {arm} arm timing/PID evidence is invalid.")
        intervals[arm] = (started, completed)
        arms[arm] = {
            key: status.get(key)
            for key in (
                "status",
                "process_pid",
                "started_at",
                "completed_at",
                "started_monotonic_ns",
                "completed_monotonic_ns",
            )
        }
    if arms["control"]["process_pid"] == arms["candidate"]["process_pid"]:
        raise ValueError("Parallel arms recorded the same process PID.")
    overlap_ns = min(interval[1] for interval in intervals.values()) - max(
        interval[0] for interval in intervals.values()
    )
    if overlap_ns <= 0:
        raise ValueError("Control and SAGE process intervals did not overlap.")
    return {
        "unit": "isolated_child_process",
        "arms": arms,
        "positive_overlap_asserted": True,
        "overlap_monotonic_ns": overlap_ns,
        "overlap_seconds": overlap_ns / 1_000_000_000,
    }


def _stop_parallel_process(process: Any, *, timeout_seconds: float = 10.0) -> None:
    if process.is_alive():
        process.terminate()
    process.join(timeout=timeout_seconds)
    if process.is_alive():
        kill = getattr(process, "kill", None)
        if callable(kill):
            kill()
            process.join(timeout=timeout_seconds)


def _latest_run_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _status_run_dir(run_root: Path, arm: str, root: Path) -> Path | None:
    status = _read_arm_status(run_root, arm)
    raw = status.get("run_dir")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.exists():
            return path
    return _latest_run_dir(root)


def _registry_tool_count(registry_dir: Path) -> int:
    manifest_path = registry_dir / "registry_manifest.json"
    if not manifest_path.exists():
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    tools = manifest.get("tools")
    return len(tools) if isinstance(tools, dict) else 0


def _digest_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external_distribution_lock_identity(lock_path: Path) -> tuple[int, str]:
    """Independently derive the canonical external-distribution identity."""

    if not lock_path.is_file():
        raise ValueError(f"Publication environment lock is missing: {lock_path}")
    locked: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PUBLICATION_LOCK_LINE.fullmatch(line)
        if match is None:
            raise ValueError(
                "Publication environment lock must contain exact name==version "
                f"entries; line {line_number} is invalid: {line!r}."
            )
        display_name, version = match.groups()
        canonical_name = re.sub(r"[-_.]+", "-", display_name).lower()
        if canonical_name in locked:
            raise ValueError(
                "Publication environment lock contains duplicate distribution "
                f"{canonical_name!r}."
            )
        locked[canonical_name] = version
    if not locked:
        raise ValueError("Publication environment lock is empty.")
    canonical_entries = sorted(
        f"{name}=={version}\n" for name, version in locked.items()
    )
    canonical_bytes = "".join(canonical_entries).encode("utf-8")
    return len(locked), hashlib.sha256(canonical_bytes).hexdigest()


def _git_output(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Cannot inspect publication Git identity: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(
            "Cannot inspect publication Git identity: "
            f"git {' '.join(arguments)} failed ({detail or completed.returncode})."
        )
    return completed.stdout.strip()


def _clean_source_identity(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Return HEAD identity only when the exact repository worktree is clean."""

    repo_root = repo_root.resolve()
    git_root = Path(_git_output(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if git_root != repo_root:
        raise ValueError(
            f"Publication source root mismatch: expected {repo_root}, observed {git_root}."
        )
    status = _git_output(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        first_entries = ", ".join(status.splitlines()[:5])
        raise ValueError(
            "Publication source worktree is not clean"
            + (f": {first_entries}" if first_entries else ".")
        )
    commit = _git_output(repo_root, "rev-parse", "--verify", "HEAD")
    tree = _git_output(repo_root, "rev-parse", "--verify", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not re.fullmatch(
        r"[0-9a-f]{40,64}", tree
    ):
        raise ValueError("Publication Git commit or tree identity is malformed.")
    return {"git_commit": commit, "git_tree": tree, "git_clean": True}


def _active_publication_environment(
    lock_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    try:
        from scripts.verify_publication_environment import verify_environment
    except ModuleNotFoundError:
        from verify_publication_environment import verify_environment

    try:
        report = verify_environment(lock_path, repo_root=repo_root)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Publication environment verification failed: {exc}") from exc
    if not isinstance(report, dict) or report.get("status") != "pass":
        raise ValueError("Publication environment verifier did not return pass status.")
    return cast(dict[str, Any], report)


def _publication_provenance(
    *,
    fixed_toolsandbox_timestamp: str | None,
    freeze_toolsandbox_clock: bool,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Fail closed and capture the exact runtime/source publication identity."""

    if not freeze_toolsandbox_clock:
        raise ValueError("Publication runs require --freeze-toolsandbox-clock.")
    required_timestamp = str(PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP)
    if fixed_toolsandbox_timestamp != required_timestamp:
        raise ValueError(
            "Publication ToolSandbox timestamp must be exactly "
            f"{required_timestamp}; observed {fixed_toolsandbox_timestamp!r}."
        )

    repo_root = repo_root.resolve()
    source = _clean_source_identity(repo_root)
    exported_commit = os.environ.get("SAGE_PUBLICATION_GIT_COMMIT")
    exported_tree = os.environ.get("SAGE_PUBLICATION_GIT_TREE")
    if exported_commit != source["git_commit"]:
        raise ValueError(
            "SAGE_PUBLICATION_GIT_COMMIT is missing or does not match clean HEAD."
        )
    if exported_tree != source["git_tree"]:
        raise ValueError(
            "SAGE_PUBLICATION_GIT_TREE is missing or does not match the clean HEAD tree."
        )

    lock_path = (repo_root / PUBLICATION_ENVIRONMENT_LOCK).resolve()
    observed_lock_sha256 = _digest_file(lock_path)
    if observed_lock_sha256 != PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256:
        raise ValueError(
            "Publication environment lock hash mismatch: expected "
            f"{PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256}, observed "
            f"{observed_lock_sha256 or 'missing'}."
        )
    distribution_count, distribution_sha256 = _external_distribution_lock_identity(
        lock_path
    )
    environment = _active_publication_environment(lock_path, repo_root=repo_root)
    required_environment: dict[str, Any] = {
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "isolated_environment": True,
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "environment_lock_path": str(lock_path),
        "environment_lock_sha256": observed_lock_sha256,
        "external_distribution_count": distribution_count,
        "external_distribution_sha256": distribution_sha256,
    }
    for field, expected in required_environment.items():
        if environment.get(field) != expected:
            raise ValueError(
                f"Publication environment field {field!r} is "
                f"{environment.get(field)!r}; expected {expected!r}."
            )

    exported_fields = {
        "python_executable": "SAGE_PUBLICATION_PYTHON_EXECUTABLE",
        "python_version": "SAGE_PUBLICATION_PYTHON_VERSION",
        "python_prefix": "SAGE_PUBLICATION_PYTHON_PREFIX",
        "python_base_prefix": "SAGE_PUBLICATION_PYTHON_BASE_PREFIX",
        "python_implementation": "SAGE_PUBLICATION_PYTHON_IMPLEMENTATION",
        "platform_system": "SAGE_PUBLICATION_PLATFORM_SYSTEM",
        "platform_machine": "SAGE_PUBLICATION_PLATFORM_MACHINE",
        "environment_lock_path": "SAGE_PUBLICATION_ENVIRONMENT_LOCK",
        "environment_lock_sha256": "SAGE_PUBLICATION_ENVIRONMENT_LOCK_SHA256",
        "external_distribution_count": ("SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT"),
        "external_distribution_sha256": (
            "SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256"
        ),
    }
    for field, env_name in exported_fields.items():
        exported = os.environ.get(env_name)
        observed = environment.get(field)
        if exported is None or exported != str(observed):
            raise ValueError(
                f"{env_name} is missing or does not match the verified "
                f"publication environment field {field!r}."
            )
    for env_name, expected in PUBLICATION_EXECUTION_ENV.items():
        if os.environ.get(env_name) != expected:
            raise ValueError(
                f"{env_name} must be pinned to {expected!r} for publication runs."
            )

    return {
        "schema_version": 2,
        **source,
        "fixed_toolsandbox_timestamp": PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP,
        "python_executable": environment["python_executable"],
        "python_version": environment["python_version"],
        "python_implementation": environment["python_implementation"],
        "python_prefix": environment["python_prefix"],
        "python_base_prefix": environment["python_base_prefix"],
        "isolated_environment": environment["isolated_environment"],
        "platform_system": environment["platform_system"],
        "platform_machine": environment["platform_machine"],
        "environment_lock_path": PUBLICATION_ENVIRONMENT_LOCK,
        "environment_lock_sha256": observed_lock_sha256,
        "external_distribution_count": distribution_count,
        "external_distribution_sha256": distribution_sha256,
        "execution_environment": dict(PUBLICATION_EXECUTION_ENV),
    }


def _assert_publication_source_unchanged(
    provenance: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> None:
    current = _clean_source_identity(repo_root)
    for field in ("git_commit", "git_tree", "git_clean"):
        if current.get(field) != provenance.get(field):
            raise ValueError(
                f"Publication source identity changed during execution ({field})."
            )
    lock_path = (repo_root.resolve() / PUBLICATION_ENVIRONMENT_LOCK).resolve()
    if _digest_file(lock_path) != provenance.get("environment_lock_sha256"):
        raise ValueError("Publication environment lock changed during execution.")
    count, digest = _external_distribution_lock_identity(lock_path)
    if count != provenance.get(
        "external_distribution_count"
    ) or digest != provenance.get("external_distribution_sha256"):
        raise ValueError(
            "Publication external-distribution identity changed during execution."
        )
    active_environment = _active_publication_environment(
        lock_path,
        repo_root=repo_root.resolve(),
    )
    end_of_run_fields = (
        "python_executable",
        "python_version",
        "python_implementation",
        "python_prefix",
        "python_base_prefix",
        "isolated_environment",
        "platform_system",
        "platform_machine",
        "environment_lock_sha256",
        "external_distribution_count",
        "external_distribution_sha256",
    )
    for field in end_of_run_fields:
        if active_environment.get(field) != provenance.get(field):
            raise ValueError(
                f"Publication environment identity changed during execution ({field})."
            )
    if active_environment.get("environment_lock_path") != str(lock_path):
        raise ValueError("Publication environment lock path changed during execution.")
    if provenance.get("execution_environment") != PUBLICATION_EXECUTION_ENV:
        raise ValueError("Publication execution policy provenance is malformed.")
    for env_name, expected in PUBLICATION_EXECUTION_ENV.items():
        if os.environ.get(env_name) != expected:
            raise ValueError(
                f"Publication execution policy changed during execution ({env_name})."
            )


def _validated_external_fixture(
    path: Path | None,
    expected_sha256: str | None,
) -> dict[str, Any] | None:
    if path is None and expected_sha256 is None:
        return None
    if path is None or not expected_sha256:
        raise ValueError(
            "Validated external fixture requires both a path and pinned SHA-256."
        )
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"Validated external fixture is missing: {resolved}")
    expected = expected_sha256.strip().lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ValueError("Validated external fixture SHA-256 is malformed.")
    actual = _digest_file(resolved)
    if actual != expected:
        raise ValueError(
            "Validated external fixture hash mismatch: "
            f"expected {expected}, observed {actual}."
        )
    mode = os.environ.get("TOOLSANDBOX_RAPID_CACHE_MODE", "")
    if mode != "read_only":
        raise ValueError(
            "Validated external fixture requires "
            "TOOLSANDBOX_RAPID_CACHE_MODE=read_only."
        )
    env_path_raw = os.environ.get("TOOLSANDBOX_RAPID_CACHE_PATH", "")
    if not env_path_raw or Path(env_path_raw).resolve() != resolved:
        raise ValueError(
            "TOOLSANDBOX_RAPID_CACHE_PATH does not match the validated fixture."
        )
    return {
        "policy": "validated_read_only_fixture",
        "path": str(resolved),
        "sha256": actual,
        "mode": mode,
    }


def _snapshot_registry_for_gate(run_root: Path, registry_dir: Path) -> dict[str, Any]:
    """Snapshot registry state so failed gated runs cannot contaminate follow-ups."""
    gate_dir = run_root / "registry_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    for filename in ("registry_manifest.json", "tool_lifecycle.json"):
        source_path = registry_dir / filename
        snapshot_path = gate_dir / f"{Path(filename).stem}_before_run.json"
        existed = source_path.is_file()
        if existed:
            shutil.copy2(source_path, snapshot_path)
        files[filename] = {
            "existed_before_run": existed,
            "snapshot_path": str(snapshot_path) if existed else None,
            "digest_before_run": _digest_file(source_path) if existed else None,
        }
    manifest = files["registry_manifest.json"]
    metadata = {
        "registry_dir": str(registry_dir),
        "files": files,
        # Compatibility aliases for historical consumers.
        "manifest_existed_before_run": manifest["existed_before_run"],
        "snapshot_path": manifest["snapshot_path"],
        "manifest_digest_before_run": manifest["digest_before_run"],
    }
    (gate_dir / "registry_gate_snapshot.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def _restore_registry_after_failed_gate(
    *,
    run_root: Path,
    registry_dir: Path,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Preserve failed registry state, then restore all pre-run state files."""
    gate_dir = run_root / "registry_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    raw_files = snapshot.get("files")
    if not isinstance(raw_files, dict):
        raw_files = {
            "registry_manifest.json": {
                "existed_before_run": snapshot.get("manifest_existed_before_run"),
                "snapshot_path": snapshot.get("snapshot_path"),
            }
        }
    restored_files: dict[str, dict[str, Any]] = {}
    for filename in ("registry_manifest.json", "tool_lifecycle.json"):
        current_path = registry_dir / filename
        failed_snapshot_path = gate_dir / f"{Path(filename).stem}_failed_gate.json"
        if current_path.is_file():
            shutil.copy2(current_path, failed_snapshot_path)
        file_snapshot = raw_files.get(filename, {})
        if not isinstance(file_snapshot, dict):
            file_snapshot = {}
        prior_snapshot = file_snapshot.get("snapshot_path")
        prior_exists = bool(file_snapshot.get("existed_before_run"))
        if prior_exists and isinstance(prior_snapshot, str):
            registry_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(prior_snapshot), current_path)
        elif current_path.is_file():
            current_path.unlink()
        restored_files[filename] = {
            "existed_before_run": prior_exists,
            "failed_snapshot_path": (
                str(failed_snapshot_path) if failed_snapshot_path.is_file() else None
            ),
            "restored_snapshot_path": prior_snapshot if prior_exists else None,
        }

    manifest = restored_files["registry_manifest.json"]
    result = {
        "registry_dir": str(registry_dir),
        "restored": True,
        "files": restored_files,
        # Compatibility aliases for historical consumers.
        "manifest_existed_before_run": manifest["existed_before_run"],
        "failed_snapshot_path": manifest["failed_snapshot_path"],
        "restored_snapshot_path": manifest["restored_snapshot_path"],
    }
    (gate_dir / "registry_gate_restore.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def _write_cohort_preflight(
    run_root: Path,
    *,
    scenario_names: tuple[str, ...],
    generation_enabled: bool,
    registry_dir: Path,
) -> dict[str, object]:
    categories_by_name = {
        record.name: record.categories for record in scenario_records()
    }
    report = cohort_policy_report(
        scenario_names,
        categories_by_name=categories_by_name,
        generation_enabled=generation_enabled,
        registry_tool_count=_registry_tool_count(registry_dir),
    )
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "cohort_preflight_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    diversity_report = {
        "scenario_count": report.get("scenario_count"),
        "distinct_base_task_families": report.get("distinct_base_task_families"),
        "required_distinct_base_task_families": report.get(
            "required_distinct_base_task_families"
        ),
        "largest_family_share": report.get("largest_family_share"),
        "family_counts": report.get("family_counts", {}),
        "strata_counts": report.get("strata_counts", {}),
        "warnings": report.get("warnings", []),
        "decision_use": report.get("decision_use"),
    }
    (run_root / "cohort_diversity_report.json").write_text(
        json.dumps(diversity_report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _protocol_gate_decision(
    comparison: dict[str, Any],
    *,
    scenario_count: int,
) -> tuple[bool, list[str]]:
    """Apply the outcome-only viability gate used by ordinary protocol runs."""
    _, reasons = _protocol_integrity_gate_decision(
        comparison,
        scenario_count=scenario_count,
    )
    outcome_delta = _optional_float(comparison.get("mean_outcome_similarity_delta"))
    outcome_gains = int(comparison.get("outcome_gain_count", 0) or 0)
    outcome_regressions = int(comparison.get("outcome_regression_count", 0) or 0)
    if outcome_delta is not None:
        if outcome_delta <= 0:
            reasons.append("non_positive_outcome_delta")
        if outcome_gains <= outcome_regressions:
            reasons.append("outcome_gains_do_not_exceed_regressions")

    if scenario_count >= 30:
        primary_delta = outcome_delta if outcome_delta is not None else 0.0
        primary_gains = outcome_gains
        primary_regressions = outcome_regressions
        ratio = primary_gains / max(primary_regressions, 1)
        if primary_delta < 0.08:
            reasons.append("confirmation_outcome_delta_below_0_08")
        if ratio < 1.4:
            reasons.append("gain_regression_ratio_below_1_4")

    return not reasons, reasons


def _protocol_integrity_gate_decision(
    comparison: dict[str, Any],
    *,
    scenario_count: int,
) -> tuple[bool, list[str]]:
    """Reject incomplete or malformed comparisons without judging performance."""
    reasons: list[str] = []
    outcome_delta = _optional_float(comparison.get("mean_outcome_similarity_delta"))
    outcome_scenario_count = int(comparison.get("outcome_scenario_count", 0) or 0)
    runtime_exceptions = int(comparison.get("runtime_exception_count", 0) or 0)
    if runtime_exceptions:
        reasons.append("runtime_exceptions_present")
    if outcome_scenario_count != scenario_count:
        reasons.append("outcome_score_coverage_incomplete")
    if outcome_delta is None:
        reasons.append("outcome_score_unavailable")
    return not reasons, reasons


def _select_protocol_gate_decision(
    comparison: dict[str, Any],
    *,
    scenario_count: int,
    actor_selection_donor_capture: bool,
) -> tuple[bool, list[str], str, bool, bool, list[str]]:
    """Select the explicit gate policy for an ordinary or selector-donor run."""
    performance_passed, performance_reasons = _protocol_gate_decision(
        comparison,
        scenario_count=scenario_count,
    )
    if actor_selection_donor_capture:
        passed, reasons = _protocol_integrity_gate_decision(
            comparison,
            scenario_count=scenario_count,
        )
        return (
            passed,
            reasons,
            "actor_selection_donor_integrity_only",
            False,
            performance_passed,
            performance_reasons,
        )
    return (
        performance_passed,
        performance_reasons,
        "ordinary_outcome_viability",
        True,
        performance_passed,
        performance_reasons,
    )


def _protocol_event(
    *,
    event: str,
    mode: str,
    run_root: Path,
    run_dir: Path,
    payload: dict[str, object],
    artifact_root: Path,
) -> None:
    append_event(
        event,
        {
            "mode": mode,
            "run_root": str(run_root),
            "run_dir": str(run_dir),
            **payload,
        },
        root=artifact_root,
    )


def _candidate_protocol_event_hook(
    params: dict[str, Any],
) -> Callable[[str, Path, dict[str, object]], None]:
    """Build a candidate hook without retaining queue-bearing worker params."""

    mode = str(params["mode"])
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])

    def event_hook(
        event: str,
        run_dir: Path,
        payload: dict[str, object],
    ) -> None:
        _protocol_event(
            event=event,
            mode=mode,
            run_root=run_root,
            run_dir=run_dir,
            payload=payload,
            artifact_root=artifact_root,
        )

    return event_hook


def _run_control_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    control_root = Path(params["control_root"])
    scenario_names = tuple(params["scenario_names"])
    reflection_control_channel = params.get("reflection_control_channel")
    published_count = 0
    _write_arm_status(
        run_root,
        "control",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            nonlocal published_count
            if len(rows) < published_count:
                raise ValueError("Live control progress rows moved backwards.")
            for index in range(published_count, len(rows)):
                row = rows[index]
                expected_scenario = scenario_names[index]
                observed_scenario = str(row.get("name") or "")
                if observed_scenario != expected_scenario:
                    raise ValueError(
                        "Live control stream is out of order: expected "
                        f"{expected_scenario!r}, observed {observed_scenario!r}."
                    )
                if reflection_control_channel is not None:
                    reflection_control_channel.put(
                        {
                            "event": FRESH_CONTROL_ROW_EVENT,
                            "scenario": expected_scenario,
                            "row": dict(row),
                        }
                    )
            published_count = len(rows)
            _write_arm_status(
                run_root,
                "control",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        def event_hook(event: str, run_dir: Path, payload: dict[str, object]) -> None:
            _protocol_event(
                event=event,
                mode=str(params["mode"]),
                run_root=run_root,
                run_dir=run_dir,
                payload=payload,
                artifact_root=artifact_root,
            )

        run_dir = run_toolsandbox(
            ToolSandboxRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=control_root,
                processes=1,
                run_type=f"{params['mode']}_control",
                base_tool_policy=str(params["base_tool_policy"]),
                actor_selection_mode="policy",
            ),
            progress_hook=progress,
            event_hook=event_hook,
        )
        if published_count != len(scenario_names):
            raise ValueError(
                "Live control stream ended before every task row was published: "
                f"{published_count}/{len(scenario_names)}."
            )
        if reflection_control_channel is not None:
            reflection_control_channel.put(
                {
                    "event": FRESH_CONTROL_COMPLETE_EVENT,
                    "scenario_count": len(scenario_names),
                }
            )
        append_event(
            "phase_completed",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_dir": str(run_dir),
                "parallel_arms": True,
            },
            root=artifact_root,
        )
        _write_arm_status(
            run_root,
            "control",
            status="complete",
            run_dir=run_dir,
            completed_count=len(scenario_names),
            scenario_count=len(scenario_names),
        )
    except Exception:
        error = traceback.format_exc()
        if reflection_control_channel is not None:
            reflection_control_channel.put(
                {"event": FRESH_CONTROL_ERROR_EVENT, "error": error}
            )
        _write_arm_status(run_root, "control", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _run_candidate_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    candidate_root = Path(params["candidate_root"])
    registry_dir = Path(params["registry_dir"])
    scenario_names = tuple(params["scenario_names"])
    generation_enabled = bool(params["generation_enabled"])
    candidate_generation_enabled = _candidate_generation_enabled(
        generation_enabled,
        params.get("inventory_authority_replay_dir"),
    )
    require_fresh_control = bool(params.get("require_fresh_control"))
    _write_arm_status(
        run_root,
        "candidate",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:
        generator = (
            ToolGenerator(
                completer=OpenAIChatAdapter(model=str(params["generation_model"]))
            )
            if candidate_generation_enabled
            else None
        )

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            _write_arm_status(
                run_root,
                "candidate",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        event_hook = _candidate_protocol_event_hook(params)

        run_dir = run_sage_with_registry(
            SageRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=candidate_root,
                registry_dir=registry_dir,
                generation_model=str(params["generation_model"]),
                run_type=f"{params['mode']}_{params['candidate_arm_name']}",
                recurrence_threshold=int(params["recurrence_threshold"]),
                base_tool_policy=str(params["base_tool_policy"]),
                actor_selection_mode=str(params["actor_selection_mode"]),
                inventory_authority_capture_dir=(
                    Path(params["inventory_authority_capture_dir"])
                    if params.get("inventory_authority_capture_dir")
                    else None
                ),
                inventory_authority_replay_dir=(
                    Path(params["inventory_authority_replay_dir"])
                    if params.get("inventory_authority_replay_dir")
                    else None
                ),
                manifest_path=Path(params["manifest"]),
                reflection_control_channel=params.get("reflection_control_channel"),
                require_fresh_reflection_control=(
                    require_fresh_control and candidate_generation_enabled
                ),
                failure_memory_path=None,
            ),
            generator=generator,
            progress_hook=progress,
            event_hook=event_hook,
        )
        live_summary = _read_metrics(run_dir / "live_result_summary.json")
        completed_count = int(
            live_summary.get("completed_count", len(scenario_names))
            or len(scenario_names)
        )
        final_status = str(live_summary.get("status", "complete") or "complete")
        _write_arm_status(
            run_root,
            "candidate",
            status=final_status,
            run_dir=run_dir,
            completed_count=completed_count,
            scenario_count=len(scenario_names),
        )
    except (Exception, InventoryAuthorityError):
        error = traceback.format_exc()
        _write_arm_status(run_root, "candidate", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "candidate",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _read_metrics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _run_result_rows(run_dir: Path, *, require_complete: bool) -> list[dict[str, Any]]:
    final_path = run_dir / "result_summary.json"
    live_path = run_dir / "live_result_summary.json"
    if require_complete and not final_path.is_file():
        raise ValueError(f"Completed result summary is missing: {final_path}")
    source = final_path if final_path.is_file() else live_path
    payload = _read_metrics(source)
    rows = payload.get("per_scenario_results")
    if not isinstance(rows, list):
        raise ValueError(f"Scenario result rows are missing: {source}")
    return [cast(dict[str, Any], row) for row in rows if isinstance(row, dict)]


def _validate_uncached_result_rows(
    run_dir: Path,
    *,
    expected_scenarios: tuple[str, ...],
    arm: str,
    require_complete: bool,
) -> dict[str, dict[str, Any]]:
    """Validate a one-row-per-task live run and return rows keyed by task name."""
    if len(set(expected_scenarios)) != len(expected_scenarios):
        raise ValueError("Protocol cohort contains duplicate scenario names.")
    rows = _run_result_rows(run_dir, require_complete=require_complete)
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("name") or "")
        if not name:
            raise ValueError(f"{arm} result contains a row without a task name.")
        if name in by_name:
            raise ValueError(f"Duplicate {arm} result for task {name!r}.")
        if name not in expected_scenarios:
            raise ValueError(f"Unexpected {arm} result for task {name!r}.")
        cache_source = str(row.get("control_cache_source") or "").strip().lower()
        cache_detail = row.get("control_cache")
        if cache_source and cache_source != "fresh":
            raise ValueError(
                f"{arm} task {name!r} was marked as cache sourced: {cache_source!r}."
            )
        if isinstance(cache_detail, dict) and (
            str(cache_detail.get("source") or "").strip().lower() == "cached"
            or bool(cache_detail.get("record_ids"))
        ):
            raise ValueError(f"{arm} task {name!r} contains cached baseline data.")
        if "llm_cached_call_count" not in row:
            raise ValueError(
                f"{arm} task {name!r} does not report repository whole-response "
                "replay provenance."
            )
        repository_response_replays = int(row["llm_cached_call_count"])
        if repository_response_replays:
            raise ValueError(
                f"{arm} task {name!r} reports {repository_response_replays} "
                "repository whole-response replay calls."
            )
        by_name[name] = dict(row)

    expected = set(expected_scenarios)
    actual = set(by_name)
    if require_complete and actual != expected:
        raise ValueError(
            f"{arm} task coverage mismatch (missing={sorted(expected - actual)!r}, "
            f"extra={sorted(actual - expected)!r})."
        )
    for cache_artifact in (
        run_dir / "openai_response_cache_metrics.json",
        run_dir / "prompt_cache_metrics.json",
    ):
        if cache_artifact.exists():
            raise ValueError(
                f"Strict uncached {arm} run emitted a cache artifact: {cache_artifact}"
            )
    return by_name


def _assert_strict_fresh_report(
    report: dict[str, Any],
    *,
    scenario_count: int,
) -> None:
    if report.get("mode") != "off":
        raise ValueError("Strict fresh-control run did not use control-cache mode off.")
    if str(report.get("control_source") or "") != "fresh":
        raise ValueError("Strict fresh-control run did not report a fresh control arm.")
    if int(report.get("cached_control_tasks") or 0) != 0:
        raise ValueError("Strict fresh-control run contains cached control tasks.")
    if int(report.get("fresh_control_tasks") or 0) != scenario_count:
        raise ValueError("Strict fresh-control run has incomplete fresh controls.")
    if report.get("cache_accessed") is not False:
        raise ValueError("Strict fresh-control run accessed ControlBaselineCache.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--agent", default=DEFAULT_MODEL)
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument("--generation-model", default=DEFAULT_MODEL)
    parser.add_argument("--recurrence-threshold", type=int, default=2)
    parser.add_argument(
        "--actor-selection-mode",
        choices=ACTOR_SELECTION_MODES,
        default="policy",
        help=(
            "Candidate actor-selection behavior. 'policy' preserves the SAGE "
            "selector cascade; 'auto' delegates selection directly to the "
            "upstream model over the SAGE-routed tool inventory."
        ),
    )
    authority_group = parser.add_mutually_exclusive_group()
    authority_group.add_argument(
        "--inventory-authority-capture-dir",
        type=Path,
        help=(
            "Write the policy arm's exact pre-actor registry, lifecycle, and "
            "routed-inventory state for matched replay."
        ),
    )
    authority_group.add_argument(
        "--inventory-authority-replay-dir",
        type=Path,
        help=(
            "Replay and assert an exact policy-arm inventory authority before "
            "each auto-selection task."
        ),
    )
    parser.add_argument(
        "--sage-policy",
        choices=SAGE_POLICIES,
        default=os.environ.get("SAGE_POLICY_PRESET", SAGE_POLICY_AUTO),
        help=(
            "Optional SAGE runtime policy preset. The default 'auto' resolves "
            "to self-evolving-praxis for generation-enabled build/mechanism "
            "runs and to none for frozen validation. 'self-evolving-praxis' "
            "enables the audited online tool-birth, validation, registry, "
            "routing, reflection, and contribution-accounting lifecycle."
        ),
    )
    parser.add_argument("--registry-dir", type=Path)
    parser.add_argument(
        "-o",
        "--output-root",
        type=Path,
        default=Path("outputs/sage_protocol"),
    )
    parser.add_argument("--dashboard-port", type=int, default=5520)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--parallel-arms",
        action="store_true",
        help=(
            "Required compatibility flag: run the matched control and SAGE arms "
            "concurrently in isolated processes."
        ),
    )
    parser.add_argument(
        "--control-cache",
        choices=("off",),
        default="off",
        help="Compatibility flag; SAGE always executes a fresh control arm.",
    )
    parser.add_argument(
        "--require-fresh-control",
        action="store_true",
        help=(
            "Required compatibility flag: require exactly one live uncached "
            "control row per task and supply those same-run rows to online "
            "reflection. Requires --parallel-arms so rows are streamed to SAGE at "
            "each matched task boundary."
        ),
    )
    parser.add_argument(
        "--freeze-toolsandbox-clock",
        action="store_true",
        default=os.environ.get("SAGE_TS_FREEZE_TOOLSANDBOX_CLOCK") == "1",
        help=(
            "Freeze ToolSandbox's current timestamp for the whole run. This keeps "
            "scenario setup and timestamp tools on a single benchmark clock during "
            "long runs."
        ),
    )
    parser.add_argument(
        "--generation",
        choices=("auto", "on", "off"),
        default="auto",
        help="Override candidate-side helper generation. Use off for frozen-registry validation.",
    )
    parser.add_argument(
        "--diagnostic-force-allowed",
        action="store_true",
        help="Allow SAGE_DIAGNOSTIC_FORCE_* env vars for explicit diagnostic runs only.",
    )
    parser.add_argument(
        "--allow-empty-birth-preflight",
        action="store_true",
        help=(
            "Allow a generation-enabled run to proceed even when the cohort has "
            "no current expected birth path and no retained-helper fit."
        ),
    )
    parser.add_argument(
        "--allow-contaminated-preflight",
        action="store_true",
        help="Allow stock/location/weather/API-contaminated cohorts for explicit diagnostics.",
    )
    parser.add_argument(
        "--validated-external-fixture",
        type=Path,
        help=(
            "Read-only external-service fixture approved for a publication run. "
            "Requires --validated-external-fixture-sha256 and matching "
            "TOOLSANDBOX_RAPID_CACHE_* environment."
        ),
    )
    parser.add_argument(
        "--validated-external-fixture-sha256",
        help="Pinned SHA-256 for --validated-external-fixture.",
    )
    parser.add_argument(
        "--allow-low-quality-cohort",
        action="store_true",
        help=(
            "Allow a cohort that fails mechanical diversity/near-duplicate checks. "
            "Use only for explicit diagnostics, not broad claim runs."
        ),
    )
    args = parser.parse_args()

    if (
        args.inventory_authority_capture_dir is not None
        and args.actor_selection_mode != "policy"
    ):
        raise SystemExit(
            "--inventory-authority-capture-dir requires --actor-selection-mode policy."
        )
    if (
        args.inventory_authority_replay_dir is not None
        and args.actor_selection_mode != "auto"
    ):
        raise SystemExit(
            "--inventory-authority-replay-dir requires --actor-selection-mode auto."
        )
    matched_inventory_requested = (
        args.inventory_authority_capture_dir is not None
        or args.inventory_authority_replay_dir is not None
    )
    if matched_inventory_requested and not args.freeze_toolsandbox_clock:
        raise SystemExit(
            "Matched-inventory capture/replay requires --freeze-toolsandbox-clock."
        )
    if not args.require_fresh_control:
        raise SystemExit(
            "--require-fresh-control is mandatory; cached or cross-run controls "
            "are not supported."
        )
    if not args.parallel_arms:
        raise SystemExit(
            "--require-fresh-control requires --parallel-arms; every strict "
            "publication control/SAGE pair must run concurrently."
        )
    if args.no_dashboard_open:
        raise SystemExit(
            "Strict publication runs require the Task Compare dashboard to open "
            "in the external browser; --no-dashboard-open is forbidden."
        )
    active_force_env = _active_diagnostic_force_env()
    if active_force_env:
        raise SystemExit(
            "Diagnostic force-call environment is forbidden during a strict "
            "publication run: "
            f"{', '.join(sorted(active_force_env))}. Unset these variables; "
            "--diagnostic-force-allowed cannot override publication mode."
        )
    if args.require_fresh_control and os.environ.get("SAGE_APPROVE_LIVE_RUN") != "YES":
        raise SystemExit(
            "Strict publication execution requires explicit approval: set "
            "SAGE_APPROVE_LIVE_RUN=YES through the canonical launcher."
        )
    try:
        external_fixture = _validated_external_fixture(
            args.validated_external_fixture,
            args.validated_external_fixture_sha256,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.freeze_toolsandbox_clock and not os.environ.get(
        "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"
    ):
        os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = str(
            PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
            if matched_inventory_requested
            else time.time()
        )
    toolsandbox_fixed_now = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")
    publication_provenance: dict[str, Any] | None = None
    if args.require_fresh_control:
        try:
            publication_provenance = _publication_provenance(
                fixed_toolsandbox_timestamp=toolsandbox_fixed_now,
                freeze_toolsandbox_clock=args.freeze_toolsandbox_clock,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    split_name = _manifest_split_for_mode(args.mode)
    scenario_names = tuple(load_split_names(args.manifest, split_name))
    scenario_limit = _scenario_limit_for_mode(args.mode)
    if scenario_limit is not None:
        scenario_names = scenario_names[:scenario_limit]
    benchmark_manifest_path = args.manifest.resolve()
    benchmark_manifest_sha256 = _digest_file(benchmark_manifest_path)
    scenario_order_sha256 = hashlib.sha256(
        ("\n".join(scenario_names) + "\n").encode("utf-8")
    ).hexdigest()
    manifest_type = _manifest_type(args.manifest)
    model_metadata = paired_model_metadata(
        agent_model=args.agent,
        generation_model=args.generation_model,
        user_model=args.user,
    )
    outcome_evaluator = outcome_evaluator_manifest()
    run_timezone = os.environ.get("TZ")
    candidate_arm_name = _candidate_arm_name(args.actor_selection_mode)
    inventory_authority_capture_dir = (
        args.inventory_authority_capture_dir.resolve()
        if args.inventory_authority_capture_dir is not None
        else None
    )
    inventory_authority_replay_dir = (
        args.inventory_authority_replay_dir.resolve()
        if args.inventory_authority_replay_dir is not None
        else None
    )
    inventory_authority_mode = (
        "capture"
        if inventory_authority_capture_dir is not None
        else "replay"
        if inventory_authority_replay_dir is not None
        else "off"
    )
    os.environ["SAGE_TS_MODEL"] = args.agent
    run_root = args.output_root / f"{args.mode}_{_timestamp()}"
    control_root = run_root / "control"
    candidate_root = _candidate_arm_root(run_root, args.actor_selection_mode)
    registry_dir = args.registry_dir or (run_root / "registry")
    registry_gate_snapshot = _snapshot_registry_for_gate(run_root, registry_dir)
    control_dir: Path | None = None
    candidate_dir: Path | None = None
    generation_enabled = _generation_enabled_by_default(args.mode, manifest_type)
    if args.generation == "on":
        generation_enabled = True
    elif args.generation == "off":
        generation_enabled = False
    elif _is_frozen_transfer_mode(args.mode):
        generation_enabled = False
    candidate_generation_enabled = _candidate_generation_enabled(
        generation_enabled,
        inventory_authority_replay_dir,
    )
    generation_requested = generation_enabled
    frozen_final_run = _is_frozen_transfer_mode(args.mode) and not generation_enabled
    try:
        registry_content_identity_before_run = registry_content_identity(
            registry_dir,
            require_complete=args.require_fresh_control and frozen_final_run,
        )
    except ValueError as exc:
        raise SystemExit(
            f"Invalid publication registry before execution: {exc}"
        ) from exc
    if (
        args.require_fresh_control
        and candidate_generation_enabled
        and registry_content_identity_before_run["file_count"] != 0
    ):
        raise SystemExit(
            "Strict online publication execution requires a completely empty "
            "registry root before the first model request."
        )
    effective_sage_policy = _resolve_sage_policy_preset(
        args.sage_policy,
        generation_enabled=candidate_generation_enabled,
    )
    sage_policy_env: dict[str, dict[str, str]] = {}
    if effective_sage_policy != SAGE_POLICY_NONE:
        if not candidate_generation_enabled:
            raise SystemExit(
                "--sage-policy self-evolving-praxis requires generation-enabled "
                "mechanism/online-build execution. Do not use it for frozen "
                "registry validation or matched-inventory replay arms."
            )
        sage_policy_env = _apply_sage_policy_preset(effective_sage_policy)
    _preflight_openai_api_key(
        agent_model=args.agent,
        user_model=args.user,
        generation_model=args.generation_model,
        generation_enabled=candidate_generation_enabled,
    )
    if _is_frozen_transfer_mode(args.mode) and args.generation == "on":
        raise SystemExit(
            "Final/frozen protocol modes must not run with --generation on. "
            "Use a mechanism/discovery mode for tool birth diagnostics."
        )
    if frozen_final_run and active_force_env and not args.diagnostic_force_allowed:
        raise SystemExit(
            "Diagnostic force-call environment is set during a frozen final run: "
            f"{', '.join(sorted(active_force_env))}. Unset these variables or pass "
            "--diagnostic-force-allowed only for explicit diagnostics."
        )
    control_cache_report: dict[str, Any] = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": len(scenario_names),
        "cached_scenarios": [],
        "fresh_scenarios": list(scenario_names),
        "cache_misses": {},
        "cache_manifest_hash": None,
        "cache_accessed": False,
        "fresh_control_enforced": True,
        "baseline_count_and_variance_per_cached_task": {},
        "estimated_token_time_savings": {
            "cached_tasks_skipped": 0,
            "cached_control_turns_avoided": 0,
            "token_savings": None,
            "wall_time_seconds_savings": None,
        },
        "confidence_intervals_account_for_cached_control_variance": False,
        "cohort_selection_influenced_by_cache": False,
    }
    effective_parallel_arms = True
    reflection_control_delivery = (
        "task_synchronous_stream"
        if candidate_generation_enabled
        else "not_applicable_generation_disabled"
    )
    cohort_preflight = _write_cohort_preflight(
        run_root,
        scenario_names=scenario_names,
        generation_enabled=candidate_generation_enabled,
        registry_dir=registry_dir,
    )
    initialize_campaign(root=args.artifact_root, phase=args.mode)
    append_event(
        "phase_started",
        {
            "mode": args.mode,
            "manifest_split": split_name,
            "manifest_type": manifest_type,
            "run_root": str(run_root),
            "scenario_count": len(scenario_names),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "control_cache_mode": args.control_cache,
            "control_cache_source": control_cache_report.get("control_source"),
            "control_cache_manifest_hash": control_cache_report.get(
                "cache_manifest_hash"
            ),
            "sage_policy": effective_sage_policy,
            "sage_policy_requested": args.sage_policy,
            "sage_policy_env": sage_policy_env,
            "actor_selection_mode": args.actor_selection_mode,
            "candidate_arm_name": candidate_arm_name,
            "generation_enabled": candidate_generation_enabled,
            "generation_requested": generation_requested,
            "candidate_generation_enabled": candidate_generation_enabled,
            "parallel_arms": effective_parallel_arms,
            "reflection_control_delivery": reflection_control_delivery,
            "inventory_authority_mode": inventory_authority_mode,
            "inventory_authority_capture_dir": str(inventory_authority_capture_dir)
            if inventory_authority_capture_dir
            else None,
            "inventory_authority_replay_dir": str(inventory_authority_replay_dir)
            if inventory_authority_replay_dir
            else None,
            "toolsandbox_clock_policy": "frozen"
            if args.freeze_toolsandbox_clock
            else "wall_clock",
            "toolsandbox_fixed_now_timestamp": toolsandbox_fixed_now,
            "outcome_evaluator": outcome_evaluator,
            "timezone": run_timezone,
        },
        root=args.artifact_root,
    )
    if cohort_preflight.get("should_block") and not args.allow_empty_birth_preflight:
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_preflight",
                "run_root": str(run_root),
                "reason": "generation_enabled_without_birth_path_or_registry_fit",
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort preflight blocked this generation-enabled run: no expected "
            "birth path, no retained-helper fit, and empty registry. See "
            f"{run_root / 'cohort_preflight_report.json'}"
        )
    contaminated = cohort_preflight.get("contaminated_external_service_scenarios", [])
    if contaminated and not (args.allow_contaminated_preflight or external_fixture):
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_preflight",
                "run_root": str(run_root),
                "reason": "external_service_contamination",
                "contaminated_external_service_scenarios": contaminated,
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort preflight blocked this run because it contains external-service "
            "contamination. Pass --allow-contaminated-preflight only for explicit "
            "diagnostics, or provide a hash-pinned read-only external fixture for "
            f"publication. See {run_root / 'cohort_preflight_report.json'}"
        )
    if (
        cohort_preflight.get("should_block_quality")
        and not args.allow_low_quality_cohort
    ):
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_quality",
                "run_root": str(run_root),
                "reason": "low_quality_cohort",
                "quality_gate_failures": cohort_preflight.get(
                    "quality_gate_failures", []
                ),
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort quality gate blocked this run. Use "
            "--allow-low-quality-cohort only for explicit diagnostics, not broad "
            f"claim runs. See {run_root / 'cohort_preflight_report.json'}"
        )
    append_event(
        "gate_passed",
        {
            "mode": args.mode,
            "gate": "cohort_preflight",
            "run_root": str(run_root),
            "warnings": cohort_preflight.get("warnings", []),
        },
        root=args.artifact_root,
    )
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "manifest_split": split_name,
            "manifest_type": manifest_type,
            "status": "running",
            "agent": args.agent,
            "model_metadata": model_metadata,
            "generation_enabled": candidate_generation_enabled,
            "generation_requested": generation_requested,
            "base_tool_policy": UPSTREAM_POLICY,
            "scenario_count": len(scenario_names),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "external_fixture": external_fixture,
            "sage_policy": effective_sage_policy,
            "sage_policy_requested": args.sage_policy,
            "actor_selection_mode": args.actor_selection_mode,
            "candidate_arm_name": candidate_arm_name,
            "candidate_generation_enabled": candidate_generation_enabled,
            "parallel_arms": effective_parallel_arms,
            "reflection_control_delivery": reflection_control_delivery,
            "outcome_evaluator": outcome_evaluator,
            "timezone": run_timezone,
            "inventory_authority_mode": inventory_authority_mode,
            "inventory_authority_capture_dir": str(inventory_authority_capture_dir)
            if inventory_authority_capture_dir
            else None,
            "inventory_authority_replay_dir": str(inventory_authority_replay_dir)
            if inventory_authority_replay_dir
            else None,
        },
        root=args.artifact_root,
    )
    dashboard_index = write_protocol_dashboard(
        run_root,
        mode=args.mode,
        status="running",
        phase="control",
        agent=args.agent,
        user=args.user,
        model_metadata=model_metadata,
        generation_enabled=candidate_generation_enabled,
        base_tool_policy=UPSTREAM_POLICY,
        scenario_count=len(scenario_names),
        registry_dir=registry_dir,
        artifact_root=args.artifact_root,
        control_label="Fresh non-learning control",
        candidate_label=f"SAGE {args.actor_selection_mode} selection",
    )
    # Dashboard visibility is part of the experiment surface. Keep it on by
    # default for every run; only the explicit CLI flag should suppress it.
    should_open_dashboard = not args.no_dashboard_open
    dashboard_url = dashboard_task_compare_url = None
    dashboard_open_receipt_path: Path | None = None
    if should_open_dashboard:
        dashboard_task_compare_url = open_dashboard(
            dashboard_index,
            port=args.dashboard_port,
            server_root=run_root,
        )
        dashboard_opened_monotonic_ns = time.monotonic_ns()
        dashboard_url = dashboard_task_compare_url
        (run_root / "dashboard_urls.json").write_text(
            json.dumps(
                {
                    "dashboard_url": dashboard_task_compare_url,
                    "dashboard_task_compare_url": dashboard_task_compare_url,
                    "default_dashboard": "task_compare",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        dashboard_open_receipt_path = run_root / "dashboard_open_receipt.json"
        dashboard_open_receipt_path.write_text(
            json.dumps(
                {
                    "dashboard": "task_compare",
                    "comparison": (
                        f"fresh_control_vs_sage_{args.actor_selection_mode}_selection"
                    ),
                    "path": str(dashboard_index.resolve()),
                    "url": dashboard_task_compare_url,
                    "external_browser_opened": True,
                    "http_verified_before_open": True,
                    "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
                    "dashboard_server_root": str(run_root.resolve()),
                    "opened_at": datetime.now().astimezone().isoformat(),
                    "opened_monotonic_ns": dashboard_opened_monotonic_ns,
                    "opened_before_model_processes": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def refresh_dashboard(phase: str, status: str) -> None:
        write_protocol_dashboard(
            run_root,
            mode=args.mode,
            status=status,
            phase=phase,
            agent=args.agent,
            user=args.user,
            model_metadata=model_metadata,
            generation_enabled=candidate_generation_enabled,
            base_tool_policy=UPSTREAM_POLICY,
            scenario_count=len(scenario_names),
            control_dir=control_dir,
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            artifact_root=args.artifact_root,
            control_label="Fresh non-learning control",
            candidate_label=f"SAGE {args.actor_selection_mode} selection",
        )

    def campaign_event(
        event: str,
        run_dir: Path,
        payload: dict[str, object],
    ) -> None:
        append_event(
            event,
            {
                "mode": args.mode,
                "run_root": str(run_root),
                "run_dir": str(run_dir),
                **payload,
            },
            root=args.artifact_root,
        )

    parallel_arm_execution: dict[str, Any] | None = None
    if effective_parallel_arms:
        append_event(
            "subtask_started",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "parallel_cache_policy": "per_arm",
            },
            root=args.artifact_root,
        )
        ctx = get_context("spawn")
        reflection_control_channel = (
            ctx.Queue() if candidate_generation_enabled else None
        )
        base_params: dict[str, Any] = {
            "mode": args.mode,
            "run_root": str(run_root),
            "artifact_root": str(args.artifact_root),
            "agent": args.agent,
            "user": args.user,
            "generation_model": args.generation_model,
            "recurrence_threshold": args.recurrence_threshold,
            "base_tool_policy": UPSTREAM_POLICY,
            "registry_dir": str(registry_dir),
            "scenario_names": list(scenario_names),
            "manifest": str(args.manifest),
            "actor_selection_mode": args.actor_selection_mode,
            "candidate_arm_name": candidate_arm_name,
            "inventory_authority_capture_dir": str(inventory_authority_capture_dir)
            if inventory_authority_capture_dir
            else None,
            "inventory_authority_replay_dir": str(inventory_authority_replay_dir)
            if inventory_authority_replay_dir
            else None,
            "require_fresh_control": True,
            "reflection_control_channel": reflection_control_channel,
        }
        control_process = ctx.Process(
            target=_run_control_arm_worker,
            args=(
                {
                    **base_params,
                    "control_root": str(control_root),
                },
            ),
            name="sage_ts_control_arm",
        )
        candidate_process = ctx.Process(
            target=_run_candidate_arm_worker,
            args=(
                {
                    **base_params,
                    "candidate_root": str(candidate_root),
                    "generation_enabled": generation_requested,
                },
            ),
            name="sage_ts_candidate_arm",
        )
        started = {"control": False, "candidate": False}
        detected_failed_arm: str | None = None
        processes = {
            "control": control_process,
            "candidate": candidate_process,
        }
        try:
            control_process.start()
            started["control"] = True
            candidate_process.start()
            started["candidate"] = True
            while control_process.is_alive() or candidate_process.is_alive():
                if control_process.exitcode not in (None, 0):
                    detected_failed_arm = "control"
                    break
                if candidate_process.exitcode not in (None, 0):
                    detected_failed_arm = "candidate"
                    break
                control_dir = _status_run_dir(run_root, "control", control_root)
                candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
                refresh_dashboard("parallel", "running")
                time.sleep(5)
            if detected_failed_arm is not None:
                peer = "candidate" if detected_failed_arm == "control" else "control"
                _stop_parallel_process(processes[peer])
                raise RuntimeError(
                    f"{detected_failed_arm} arm exited with code "
                    f"{processes[detected_failed_arm].exitcode}."
                )
            control_process.join()
            candidate_process.join()
            if control_process.exitcode != 0 or candidate_process.exitcode != 0:
                raise RuntimeError("One or more parallel arms exited unsuccessfully.")
            control_dir = _status_run_dir(run_root, "control", control_root)
            candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
            if control_dir is None or candidate_dir is None:
                raise RuntimeError(
                    "Parallel arms finished but run directories were not found."
                )
            parallel_arm_execution = _parallel_arm_execution_record(run_root)
            refresh_dashboard("parallel", "running")
        except BaseException as exc:
            for arm, process in processes.items():
                if not started[arm]:
                    continue
                _stop_parallel_process(process)
                status = _read_arm_status(run_root, arm)
                if status.get("status") in {"complete", "failed"}:
                    continue
                failure_status = (
                    "failed"
                    if arm == detected_failed_arm
                    else "aborted_peer_failure"
                    if detected_failed_arm is not None
                    else "aborted_orchestrator_failure"
                )
                _write_arm_status(
                    run_root,
                    arm,
                    status=failure_status,
                    error=str(exc),
                    process_pid=process.pid,
                )
            failed = {arm: process.exitcode for arm, process in processes.items()}
            try:
                refresh_dashboard("parallel", "failed")
            except Exception:
                pass
            try:
                append_event(
                    "blocker_detected",
                    {
                        "mode": args.mode,
                        "run_root": str(run_root),
                        "parallel_arms": True,
                        "exitcodes": failed,
                        "control_status": _read_arm_status(run_root, "control"),
                        "candidate_status": _read_arm_status(run_root, "candidate"),
                        "orchestrator_error": repr(exc),
                    },
                    root=args.artifact_root,
                )
            except Exception:
                pass
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise SystemExit(f"Parallel arm failure: {failed}; {exc}") from exc
        finally:
            if reflection_control_channel is not None:
                try:
                    reflection_control_channel.cancel_join_thread()
                    reflection_control_channel.close()
                except (OSError, ValueError):
                    pass
        append_event(
            "subtask_completed",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "control_dir": str(control_dir),
                "candidate_dir": str(candidate_dir),
                "parallel_arm_execution": parallel_arm_execution,
                "control_cache_mode": args.control_cache,
                "control_cache_source": control_cache_report.get("control_source"),
            },
            root=args.artifact_root,
        )
    if control_dir is None:
        raise SystemExit("Strict fresh-control run did not produce a control arm.")
    if candidate_dir is None:
        raise SystemExit("Strict fresh-control run did not produce a SAGE arm.")
    try:
        _validate_uncached_result_rows(
            control_dir,
            expected_scenarios=scenario_names,
            arm="control",
            require_complete=True,
        )
        _validate_uncached_result_rows(
            candidate_dir,
            expected_scenarios=scenario_names,
            arm="candidate",
            require_complete=True,
        )
        _assert_strict_fresh_report(
            control_cache_report,
            scenario_count=len(scenario_names),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    control_cache_report_path = run_root / "control_cache_report.json"
    control_cache_report_path.write_text(
        json.dumps(control_cache_report, indent=2) + "\n", encoding="utf-8"
    )
    if control_dir is not None:
        (control_dir / "control_cache_report.json").write_text(
            json.dumps(control_cache_report, indent=2) + "\n", encoding="utf-8"
        )
    candidate_live_summary = _read_metrics(candidate_dir / "live_result_summary.json")
    candidate_stopped_early = (
        str(candidate_live_summary.get("status", "")).strip().lower() == "stopped_early"
    )
    comparison = compare_runs(
        control_dir,
        candidate_dir,
        registry_dir=registry_dir,
        require_complete_match=not candidate_stopped_early,
    )
    comparison["candidate_stopped_early"] = candidate_stopped_early
    comparison["control_cache"] = control_cache_report
    comparison["model_metadata"] = model_metadata
    comparison["comparison_model_key"] = model_metadata["comparison_key"]
    comparison["outcome_evaluator"] = outcome_evaluator
    (
        protocol_gate_passed,
        protocol_gate_reasons,
        protocol_gate_policy,
        protocol_performance_thresholds_applied,
        protocol_performance_diagnostic_passed,
        protocol_performance_diagnostic_reasons,
    ) = _select_protocol_gate_decision(
        comparison,
        scenario_count=len(scenario_names),
        actor_selection_donor_capture=inventory_authority_capture_dir is not None,
    )
    comparison["protocol_gate_passed"] = protocol_gate_passed
    comparison["protocol_gate_reasons"] = protocol_gate_reasons
    comparison["protocol_gate_policy"] = protocol_gate_policy
    comparison["protocol_performance_thresholds_applied"] = (
        protocol_performance_thresholds_applied
    )
    comparison["protocol_performance_diagnostic_passed"] = (
        protocol_performance_diagnostic_passed
    )
    comparison["protocol_performance_diagnostic_reasons"] = (
        protocol_performance_diagnostic_reasons
    )
    comparison_path = run_root / "paired_comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    helper_contribution_path = run_root / "helper_contribution_summary.json"
    helper_contribution = write_helper_contribution_summary(
        control_dir,
        candidate_dir,
        helper_contribution_path,
        registry_dir=registry_dir,
    )
    helper_artifact_dir = args.artifact_root / "summaries" / run_root.name
    helper_artifact_dir.mkdir(parents=True, exist_ok=True)
    helper_contribution_artifact_path = (
        helper_artifact_dir / "helper_contribution_summary.json"
    )
    shutil.copy2(helper_contribution_path, helper_contribution_artifact_path)
    registry_gate_restore: dict[str, Any] | None = None
    if not protocol_gate_passed:
        registry_gate_restore = _restore_registry_after_failed_gate(
            run_root=run_root,
            registry_dir=registry_dir,
            snapshot=registry_gate_snapshot,
        )
    gate_event = "gate_passed" if protocol_gate_passed else "gate_failed"
    append_event(
        gate_event,
        {
            "mode": args.mode,
            "run_root": str(run_root),
            "mean_outcome_similarity_delta": comparison.get(
                "mean_outcome_similarity_delta"
            ),
            "outcome_gain_count": comparison.get("outcome_gain_count"),
            "outcome_regression_count": comparison.get("outcome_regression_count"),
            "protocol_gate_reasons": protocol_gate_reasons,
            "protocol_gate_policy": protocol_gate_policy,
            "protocol_performance_thresholds_applied": (
                protocol_performance_thresholds_applied
            ),
            "protocol_performance_diagnostic_passed": (
                protocol_performance_diagnostic_passed
            ),
            "protocol_performance_diagnostic_reasons": (
                protocol_performance_diagnostic_reasons
            ),
            "registry_gate_restore": registry_gate_restore,
        },
        root=args.artifact_root,
    )
    append_event(
        "phase_completed",
        {"mode": args.mode, "phase": "comparison", "run_root": str(run_root)},
        root=args.artifact_root,
    )
    snapshot_registry(
        registry_dir, name=f"{args.mode}_{run_root.name}", root=args.artifact_root
    )
    if args.mode in {"viability_12", "mechanism_12", "mechanism_40", "mechanism_60"}:
        update_task(
            "reproduce_clean_recency_birth", "completed", root=args.artifact_root
        )
    elif args.mode in {"transfer_40", "transfer_60", "transfer_100"}:
        update_task("frozen_registry_transfer", "completed", root=args.artifact_root)
    refresh_dashboard("comparison", "complete")
    if publication_provenance is not None:
        try:
            _assert_publication_source_unchanged(publication_provenance)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    try:
        registry_content_identity_after_run = registry_content_identity(
            registry_dir,
            require_complete=args.require_fresh_control,
        )
    except ValueError as exc:
        raise SystemExit(
            f"Invalid publication registry after execution: {exc}"
        ) from exc
    frozen_registry_content_immutable = (
        not frozen_final_run
        or registry_content_identity_before_run == registry_content_identity_after_run
    )
    if args.require_fresh_control and not frozen_registry_content_immutable:
        raise SystemExit(
            "Frozen publication execution mutated the exact registry bytes."
        )
    inventory_authority_dir = (
        inventory_authority_capture_dir or inventory_authority_replay_dir
    )
    inventory_authority_manifest_path = (
        inventory_authority_dir / "inventory_authority.json"
        if inventory_authority_dir is not None
        else None
    )
    inventory_authority_manifest_sha256 = (
        _digest_file(inventory_authority_manifest_path)
        if inventory_authority_manifest_path is not None
        else None
    )
    if (
        inventory_authority_manifest_path is not None
        and inventory_authority_manifest_sha256 is None
    ):
        raise SystemExit(
            "Matched-inventory run did not produce or preserve a complete "
            f"authority manifest: {inventory_authority_manifest_path}"
        )
    inventory_authority_manifest = (
        _read_metrics(inventory_authority_manifest_path)
        if inventory_authority_manifest_path is not None
        else {}
    )
    manifest = {
        "mode": args.mode,
        "manifest_split": split_name,
        "manifest_type": manifest_type,
        "agent": args.agent,
        "user": args.user,
        "generation_model": args.generation_model,
        "model_metadata": model_metadata,
        "comparison_model_key": model_metadata["comparison_key"],
        "generation_enabled": candidate_generation_enabled,
        "generation_requested": generation_requested,
        "base_tool_policy": UPSTREAM_POLICY,
        "sage_policy": effective_sage_policy,
        "sage_policy_requested": args.sage_policy,
        "sage_policy_env": sage_policy_env,
        "actor_selection_mode": args.actor_selection_mode,
        "control_actor_selection_mode": "policy",
        "candidate_actor_selection_mode": args.actor_selection_mode,
        "candidate_arm_name": candidate_arm_name,
        "candidate_generation_enabled": candidate_generation_enabled,
        "candidate_evolution_source": (
            "matched_inventory_authority"
            if inventory_authority_replay_dir is not None
            else "live_candidate"
        ),
        "inventory_authority_mode": inventory_authority_mode,
        "inventory_authority_capture_dir": str(inventory_authority_capture_dir)
        if inventory_authority_capture_dir
        else None,
        "inventory_authority_replay_dir": str(inventory_authority_replay_dir)
        if inventory_authority_replay_dir
        else None,
        "inventory_authority_manifest_path": str(inventory_authority_manifest_path)
        if inventory_authority_manifest_path
        else None,
        "inventory_authority_manifest_sha256": (inventory_authority_manifest_sha256),
        "inventory_authority_source_actor_selection_mode": (
            inventory_authority_manifest.get("source_actor_selection_mode")
        ),
        "inventory_authority_source_generation_enabled": (
            inventory_authority_manifest.get("source_generation_enabled")
        ),
        "inventory_authority_task_count": inventory_authority_manifest.get(
            "task_count"
        ),
        "inventory_authority_tasks_sha256": inventory_authority_manifest.get(
            "tasks_sha256"
        ),
        "scenario_count": len(scenario_names),
        "benchmark_manifest_path": str(benchmark_manifest_path),
        "benchmark_manifest_sha256": benchmark_manifest_sha256,
        "scenario_order_sha256": scenario_order_sha256,
        "control_dir": str(control_dir),
        "candidate_dir": str(candidate_dir),
        "registry_dir": str(registry_dir),
        "registry_gate_snapshot": registry_gate_snapshot,
        "registry_gate_restore": registry_gate_restore,
        "registry_content_identity_before_run": registry_content_identity_before_run,
        "registry_content_identity_after_run": registry_content_identity_after_run,
        "frozen_registry_content_immutable": frozen_registry_content_immutable,
        "registry_manifest_digest_after_run": _digest_file(
            registry_dir / "registry_manifest.json"
        ),
        "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
        "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
        "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
        "cohort_quality_gate_failures": cohort_preflight.get(
            "quality_gate_failures", []
        ),
        "external_fixture": external_fixture,
        "resume_run_root": None,
        "resume_completed_limit": None,
        "control_resume_dir": None,
        "candidate_resume_dir": None,
        "comparison_path": str(comparison_path),
        "control_cache_mode": args.control_cache,
        "control_source": control_cache_report.get("control_source"),
        "cached_control_tasks": control_cache_report.get("cached_control_tasks"),
        "fresh_control_tasks": control_cache_report.get("fresh_control_tasks"),
        "control_cache_report_path": str(control_cache_report_path),
        "control_cache_manifest_hash": control_cache_report.get("cache_manifest_hash"),
        "fresh_control_required": True,
        "cross_run_failure_memory_enabled": False,
        "cross_run_failure_memory_path": None,
        "reflection_control_source": (
            "inventory_authority_replay"
            if inventory_authority_replay_dir is not None
            else "same_run_fresh"
            if candidate_generation_enabled
            else "not_applicable"
        ),
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "outcome_evaluator": outcome_evaluator,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "openai_response_cache_scope": "persistent_repository_whole_response_replay",
        # Legacy field retained for the predeclared sample gate. It refers to
        # the retired persistent generated-output cache, not OpenAI's
        # provider-managed prompt-prefix/KV cache.
        "prompt_cache_enabled": False,
        "prompt_cache_scope": "persistent_generation_output_replay",
        "generator_contract_and_repair_analysis_memoization": (
            "disabled_every_analysis_request_live"
        ),
        "openai_provider_prompt_prefix_cache_policy": "automatic_implicit",
        "openai_provider_prompt_prefix_cache_reuses_responses": False,
        "sage_task_cache_enabled": False,
        "helper_contribution_summary_path": str(helper_contribution_path),
        "helper_contribution_artifact_path": str(helper_contribution_artifact_path),
        "diagnostic_force_allowed": args.diagnostic_force_allowed,
        "active_diagnostic_force_env": sorted(active_force_env),
        "toolsandbox_clock_policy": "frozen"
        if args.freeze_toolsandbox_clock
        else "wall_clock",
        "toolsandbox_fixed_now_timestamp": toolsandbox_fixed_now,
        "publication_provenance": publication_provenance,
        "timezone": run_timezone,
        "run_affecting_sage_env": _redacted_run_affecting_sage_env(),
        "accepted_but_uncalled_tools": helper_contribution.get(
            "accepted_but_uncalled_tools", []
        ),
        "dashboard_path": str(dashboard_index),
        "dashboard_url": dashboard_url,
        "dashboard_task_compare_url": dashboard_task_compare_url,
        "dashboard_open_required": True,
        "dashboard_open_receipt_path": str(dashboard_open_receipt_path)
        if dashboard_open_receipt_path
        else None,
        "parallel_arms": effective_parallel_arms,
        "parallel_arm_execution": parallel_arm_execution,
        "reflection_control_delivery": reflection_control_delivery,
        "model_authored_generation_enabled": candidate_generation_enabled,
        "native_action_tools_enabled": True,
        "scenario_name_birth_enabled": False,
        "scenario_name_routing_enabled": False,
        "synthetic_bridge_completions_enabled": False,
        "mean_outcome_similarity_delta": comparison.get(
            "mean_outcome_similarity_delta"
        ),
        "protocol_gate_passed": protocol_gate_passed,
        "protocol_gate_reasons": protocol_gate_reasons,
        "protocol_gate_policy": protocol_gate_policy,
        "protocol_performance_thresholds_applied": (
            protocol_performance_thresholds_applied
        ),
        "protocol_performance_diagnostic_passed": (
            protocol_performance_diagnostic_passed
        ),
        "protocol_performance_diagnostic_reasons": (
            protocol_performance_diagnostic_reasons
        ),
    }
    manifest_path = run_root / "protocol_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "manifest_split": split_name,
            "manifest_type": manifest_type,
            "status": "complete",
            "agent": args.agent,
            "model_metadata": model_metadata,
            "comparison_model_key": model_metadata["comparison_key"],
            "generation_enabled": candidate_generation_enabled,
            "generation_requested": generation_requested,
            "base_tool_policy": UPSTREAM_POLICY,
            "actor_selection_mode": args.actor_selection_mode,
            "control_actor_selection_mode": "policy",
            "candidate_actor_selection_mode": args.actor_selection_mode,
            "candidate_arm_name": candidate_arm_name,
            "candidate_generation_enabled": candidate_generation_enabled,
            "candidate_evolution_source": (
                "matched_inventory_authority"
                if inventory_authority_replay_dir is not None
                else "live_candidate"
            ),
            "inventory_authority_mode": inventory_authority_mode,
            "inventory_authority_capture_dir": str(inventory_authority_capture_dir)
            if inventory_authority_capture_dir
            else None,
            "inventory_authority_replay_dir": str(inventory_authority_replay_dir)
            if inventory_authority_replay_dir
            else None,
            "inventory_authority_manifest_path": str(inventory_authority_manifest_path)
            if inventory_authority_manifest_path
            else None,
            "inventory_authority_manifest_sha256": (
                inventory_authority_manifest_sha256
            ),
            "inventory_authority_source_actor_selection_mode": (
                inventory_authority_manifest.get("source_actor_selection_mode")
            ),
            "inventory_authority_source_generation_enabled": (
                inventory_authority_manifest.get("source_generation_enabled")
            ),
            "inventory_authority_task_count": inventory_authority_manifest.get(
                "task_count"
            ),
            "inventory_authority_tasks_sha256": inventory_authority_manifest.get(
                "tasks_sha256"
            ),
            "scenario_count": len(scenario_names),
            "control_dir": str(control_dir),
            "candidate_dir": str(candidate_dir),
            "registry_dir": str(registry_dir),
            "registry_gate_snapshot": registry_gate_snapshot,
            "registry_gate_restore": registry_gate_restore,
            "registry_content_identity_before_run": (
                registry_content_identity_before_run
            ),
            "registry_content_identity_after_run": registry_content_identity_after_run,
            "frozen_registry_content_immutable": frozen_registry_content_immutable,
            "registry_manifest_digest_after_run": _digest_file(
                registry_dir / "registry_manifest.json"
            ),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "cohort_quality_gate_failures": cohort_preflight.get(
                "quality_gate_failures", []
            ),
            "external_fixture": external_fixture,
            "comparison_path": str(comparison_path),
            "control_cache_mode": args.control_cache,
            "control_source": control_cache_report.get("control_source"),
            "cached_control_tasks": control_cache_report.get("cached_control_tasks"),
            "fresh_control_tasks": control_cache_report.get("fresh_control_tasks"),
            "control_cache_report_path": str(control_cache_report_path),
            "control_cache_manifest_hash": control_cache_report.get(
                "cache_manifest_hash"
            ),
            "fresh_control_required": True,
            "outcome_evaluator": outcome_evaluator,
            "timezone": run_timezone,
            "helper_contribution_summary_path": str(helper_contribution_path),
            "helper_contribution_artifact_path": str(helper_contribution_artifact_path),
            "accepted_but_uncalled_tools": helper_contribution.get(
                "accepted_but_uncalled_tools", []
            ),
            "dashboard_path": str(dashboard_index),
            "dashboard_url": dashboard_url,
            "dashboard_task_compare_url": dashboard_task_compare_url,
            "dashboard_open_required": True,
            "dashboard_open_receipt_path": str(dashboard_open_receipt_path)
            if dashboard_open_receipt_path
            else None,
            "parallel_arms": effective_parallel_arms,
            "parallel_arm_execution": parallel_arm_execution,
            "reflection_control_delivery": reflection_control_delivery,
            "mean_outcome_similarity_delta": comparison.get(
                "mean_outcome_similarity_delta"
            ),
            "protocol_gate_passed": protocol_gate_passed,
            "protocol_gate_reasons": protocol_gate_reasons,
            "protocol_gate_policy": protocol_gate_policy,
            "protocol_performance_thresholds_applied": (
                protocol_performance_thresholds_applied
            ),
            "protocol_performance_diagnostic_passed": (
                protocol_performance_diagnostic_passed
            ),
            "protocol_performance_diagnostic_reasons": (
                protocol_performance_diagnostic_reasons
            ),
        },
        root=args.artifact_root,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
