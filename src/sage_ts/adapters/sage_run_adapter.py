"""ToolSandbox runner with accepted SAGE registry tools injected."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sage_ts.adapters.toolsandbox_adapter import (
    EventHook,
    ProgressHook,
    ToolSandboxRunConfig,
    git_sha,
    run_scenario_sequence,
)
from sage_ts.adequacy.inadequacy_classifier import (
    classify_visible_task_observations,
    classify_visible_trace_observations,
    visible_task_context_from_scenario,
)
from sage_ts.generation.complete_tools import native_action_tool_enabled
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.orchestration.online_birth import (
    GeneratedToolFactory,
    OnlineBirthController,
)
from sage_ts.orchestration.self_evolution_reflection import (
    SelfEvolutionReflectionController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from sage_ts.runtime.toolsandbox_integration import (
    load_tool_lifecycle_routing_state,
    route_registry_entries,
    with_registry_tools,
)
from tool_sandbox.common.scenario import Scenario

INVENTORY_AUTHORITY_SCHEMA_VERSION = 2
INVENTORY_AUTHORITY_ARTIFACT = "sage_matched_inventory_authority"
INVENTORY_AUTHORITY_SHARED_ENV_NAMES = (
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT",
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DISABLE_SCENARIO_NAME_BIRTH",
    "SAGE_DISABLE_SCENARIO_NAME_ROUTING",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS",
    "SAGE_GPT5_REASONING_EFFORT",
    "SAGE_GPT5_USER_SIM_REASONING_EFFORT",
    "SAGE_OPENAI_MAX_RETRIES",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS",
    "SAGE_POLICY_PRESET",
    "SAGE_PRAXIS_BRIDGE_POLICY",
    "SAGE_PUBLICATION_GIT_COMMIT",
    "SAGE_PUBLICATION_GIT_TREE",
    "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
    "SAGE_TS_FREEZE_TOOLSANDBOX_CLOCK",
    "SAGE_TS_GENERATION_SETTINGS_DIGEST",
    "SAGE_TS_MODEL",
    "SAGE_TS_PROMPT_POLICY_DIGEST",
    "SAGE_TS_RUNTIME_DIGEST",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS",
    "TOOLSANDBOX_RAPID_CACHE_MODE",
    "TZ",
)


class InventoryAuthorityError(RuntimeError):
    """Abort before inference when a matched-inventory assertion fails.

    ``run_scenario_sequence`` intentionally catches ordinary transform exceptions and
    falls back to the untransformed scenario. That behavior is useful for exploratory
    adapters but unsafe for a causal inventory replay: silently falling back would send
    a different tool set to the actor. The transform boundary explicitly re-raises
    exceptions carrying this marker instead of entering that fallback path.
    """

    fail_closed_scenario_transform = True


def _reuse_log_tools(output_directory: Path, scenario_name: str) -> list[str]:
    path = output_directory / "reuse_events.jsonl"
    if not path.exists():
        return []
    tools: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("scenario") != scenario_name:
            continue
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in tools:
            tools.append(tool_name)
    return tools


def _selection_log_rows(output_directory: Path) -> list[dict[str, object]]:
    path = output_directory / "scenario_tool_selection.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _conversation_generated_tool_attempts(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
) -> tuple[list[str], list[str]]:
    """Return generated tools attempted in the transcript, including failures."""
    generated_tool_set = set(generated_tools)
    if not generated_tool_set:
        return [], []
    path = output_directory / "trajectories" / scenario_name / "conversation.json"
    if not path.exists():
        return [], []
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], []
    if not isinstance(messages, list):
        return [], []

    attempted: list[str] = []
    failed: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue
                tool_name = function.get("name")
                if isinstance(tool_name, str) and tool_name in generated_tool_set:
                    if tool_name not in attempted:
                        attempted.append(tool_name)
        if message.get("role") == "tool":
            tool_name = message.get("name")
            if not isinstance(tool_name, str) or tool_name not in generated_tool_set:
                continue
            if tool_name not in attempted:
                attempted.append(tool_name)
            content = str(message.get("content", ""))
            if (
                "Error:" in content
                or content.startswith(("TypeError", "ValueError", "ValidationError"))
                or "Traceback" in content
            ) and tool_name not in failed:
                failed.append(tool_name)
    return attempted, failed


def _visible_conversation_messages_for_observation(
    output_directory: Path,
    scenario_name: str,
) -> list[dict[str, object]]:
    """Load only visible trajectory text for capability observation.

    Saved ToolSandbox trajectories can contain scorer metadata under fields such
    as tool_details. Tool birth must not see scorer internals, so keep only the
    transcript fields that were visible in the interaction: roles, text, tool
    names, and tool-call arguments.
    """

    path = output_directory / "trajectories" / scenario_name / "conversation.json"
    if not path.exists():
        return []
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(messages, list):
        return []

    visible: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        sanitized: dict[str, object] = {}
        for key in ("role", "content", "name", "tool_call_id"):
            value = message.get(key)
            if isinstance(value, str):
                sanitized[key] = value
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            sanitized_tool_calls: list[dict[str, object]] = []
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue
                sanitized_function: dict[str, object] = {}
                for key in ("name", "arguments"):
                    value = function.get(key)
                    if isinstance(value, str):
                        sanitized_function[key] = value
                if not sanitized_function:
                    continue
                sanitized_call: dict[str, object] = {
                    "function": sanitized_function,
                    "type": str(tool_call.get("type") or "function"),
                }
                call_id = tool_call.get("id")
                if isinstance(call_id, str):
                    sanitized_call["id"] = call_id
                sanitized_tool_calls.append(sanitized_call)
            if sanitized_tool_calls:
                sanitized["tool_calls"] = sanitized_tool_calls
        if sanitized:
            visible.append(sanitized)
    return visible


def _safe_checkpoint_name(scenario_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_name).strip("_")
    return slug[:120] or "scenario"


def _snapshot_registry_checkpoint(
    *,
    output_directory: Path,
    registry_dir: Path,
    scenario_name: str,
) -> Path | None:
    """Persist registry state after a scenario so resumed runs can restore it."""
    try:
        order_index = int(os.environ.get("SAGE_TS_SCENARIO_ORDER_INDEX") or "-1")
    except ValueError:
        order_index = -1
    completed_count = max(order_index + 1, 0)
    checkpoint_dir = (
        output_directory
        / "registry_checkpoints"
        / f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}"
    )
    copied: list[str] = []
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("registry_manifest.json", "tool_lifecycle.json"):
        source = registry_dir / filename
        if source.exists():
            shutil.copy2(source, checkpoint_dir / filename)
            copied.append(filename)
    if not copied:
        return None
    metadata = {
        "scenario": scenario_name,
        "completed_count": completed_count,
        "registry_dir": str(registry_dir),
        "copied_files": copied,
    }
    (checkpoint_dir / "checkpoint.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return checkpoint_dir


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str | None:
    return _sha256_bytes(path.read_bytes()) if path.is_file() else None


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _scenario_order_sha256(scenario_names: tuple[str, ...]) -> str:
    return _sha256_bytes(("\n".join(scenario_names) + "\n").encode("utf-8"))


def _tracked_source_state(repository_root: Path) -> dict[str, object]:
    """Hash every tracked worktree/index change relative to the bound commit."""

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "diff",
                "--binary",
                "--no-ext-diff",
                "HEAD",
                "--",
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            "Cannot inspect matched-inventory tracked source state."
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            "Cannot inspect matched-inventory tracked source state: "
            f"{detail or completed.returncode}."
        )
    return {
        "tracked_changes_present": bool(completed.stdout),
        "tracked_diff_sha256": _sha256_bytes(completed.stdout),
    }


def _inventory_authority_shared_context(config: "SageRunConfig") -> dict[str, object]:
    """Return non-treatment execution context that must match across arms."""

    fixed_toolsandbox_timestamp = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")
    if not fixed_toolsandbox_timestamp:
        raise ValueError(
            "Matched-inventory capture/replay requires a fixed ToolSandbox timestamp."
        )
    source_git_commit = git_sha()
    if not source_git_commit:
        raise ValueError(
            "Matched-inventory capture/replay requires a resolvable source Git commit."
        )
    benchmark_manifest = Path(config.manifest_path)
    benchmark_manifest_present = benchmark_manifest.is_file()
    repository_root = Path(__file__).resolve().parents[3]
    configured_environment_lock = os.environ.get("SAGE_PUBLICATION_ENVIRONMENT_LOCK")
    environment_lock = (
        Path(configured_environment_lock)
        if configured_environment_lock
        else repository_root / "requirements-publication-lock.txt"
    )
    configured_rapid_fixture = os.environ.get("TOOLSANDBOX_RAPID_CACHE_PATH")
    rapid_fixture = Path(configured_rapid_fixture) if configured_rapid_fixture else None
    behavior_environment = {
        name: os.environ.get(name) for name in INVENTORY_AUTHORITY_SHARED_ENV_NAMES
    }
    return {
        "agent": config.agent,
        "user": config.user,
        "generation_model": config.generation_model,
        "benchmark_manifest_present": benchmark_manifest_present,
        "benchmark_manifest_sha256": (
            _sha256_file(benchmark_manifest) if benchmark_manifest_present else None
        ),
        "base_tool_policy": config.base_tool_policy,
        "recurrence_threshold": config.recurrence_threshold,
        "fixed_toolsandbox_timestamp": fixed_toolsandbox_timestamp,
        "source_git_commit": source_git_commit,
        "tracked_source_state": _tracked_source_state(repository_root),
        "runtime_environment": {
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "environment_lock_present": environment_lock.is_file(),
            "environment_lock_sha256": _sha256_file(environment_lock),
        },
        "behavior_environment": behavior_environment,
        "rapidapi_fixture": {
            "configured": rapid_fixture is not None,
            "present": rapid_fixture.is_file() if rapid_fixture is not None else False,
            "sha256": _sha256_file(rapid_fixture)
            if rapid_fixture is not None
            else None,
        },
    }


def _shared_context_mismatch_fields(
    expected: dict[str, object],
    observed: dict[str, object],
) -> list[str]:
    return sorted(
        key
        for key in set(expected) | set(observed)
        if expected.get(key) != observed.get(key)
    )


def _authority_task_directory_name(order_index: int, scenario_name: str) -> str:
    return f"{order_index + 1:04d}_{_safe_checkpoint_name(scenario_name)}"


def _active_authority_order_index(
    scenario_name: str,
    scenario_names: tuple[str, ...],
) -> int:
    raw_index = os.environ.get("SAGE_TS_SCENARIO_ORDER_INDEX")
    try:
        order_index = int(raw_index) if raw_index is not None else -1
    except ValueError as exc:
        raise InventoryAuthorityError(
            f"Invalid SAGE_TS_SCENARIO_ORDER_INDEX: {raw_index!r}."
        ) from exc
    if not 0 <= order_index < len(scenario_names):
        raise InventoryAuthorityError(
            "Matched-inventory execution requires a valid scenario-order index; "
            f"observed {order_index}."
        )
    if scenario_names[order_index] != scenario_name:
        raise InventoryAuthorityError(
            "Matched-inventory scenario order diverged: expected "
            f"{scenario_names[order_index]!r}, observed {scenario_name!r}."
        )
    return order_index


def _assert_separate_authority_and_registry_roots(
    authority_root: Path,
    registry_root: Path,
) -> None:
    authority = authority_root.resolve()
    registry = registry_root.resolve()
    if (
        authority == registry
        or authority.is_relative_to(registry)
        or registry.is_relative_to(authority)
    ):
        raise ValueError(
            "Inventory authority and mutable registry roots must be separate: "
            f"authority={authority}, registry={registry}."
        )


def _prepare_inventory_authority_capture(
    authority_root: Path,
    *,
    registry_root: Path,
) -> None:
    _assert_separate_authority_and_registry_roots(authority_root, registry_root)
    if authority_root.exists() and any(authority_root.iterdir()):
        raise ValueError(
            "Inventory authority capture refuses to overwrite a non-empty root: "
            f"{authority_root}"
        )
    (authority_root / "tasks").mkdir(parents=True, exist_ok=True)


def _authority_state_record(
    *,
    authority_root: Path,
    registry_root: Path,
    order_index: int,
    scenario_name: str,
) -> dict[str, object]:
    """Copy the exact actor-ready registry/lifecycle bytes for one donor task."""

    relative_state_dir = Path("tasks") / _authority_task_directory_name(
        order_index, scenario_name
    )
    state_dir = authority_root / relative_state_dir
    if state_dir.exists():
        raise InventoryAuthorityError(
            f"Inventory authority task state already exists: {state_dir}"
        )
    state_dir.mkdir(parents=True)
    state: dict[str, object] = {
        "state_dir": relative_state_dir.as_posix(),
    }
    for filename, prefix in (
        ("registry_manifest.json", "registry_manifest"),
        ("tool_lifecycle.json", "tool_lifecycle"),
    ):
        source = registry_root / filename
        present = source.is_file()
        state[f"{prefix}_present"] = present
        state[f"{prefix}_sha256"] = _sha256_file(source) if present else None
        if present:
            shutil.copy2(source, state_dir / filename)
    return state


def _authority_manifest_payload(
    *,
    scenario_names: tuple[str, ...],
    shared_context: dict[str, object],
    source_actor_selection_mode: str,
    source_generation_enabled: bool,
    tasks: list[dict[str, object]],
    complete: bool,
) -> dict[str, object]:
    common: dict[str, object] = {
        "artifact_type": INVENTORY_AUTHORITY_ARTIFACT,
        "schema_version": INVENTORY_AUTHORITY_SCHEMA_VERSION,
        "complete": complete,
        "shared_context": shared_context,
        "shared_context_sha256": _canonical_json_sha256(shared_context),
        "source_actor_selection_mode": source_actor_selection_mode,
        "source_generation_enabled": source_generation_enabled,
        "scenario_order_sha256": _scenario_order_sha256(scenario_names),
        "expected_task_count": len(scenario_names),
        "task_count": len(tasks),
    }
    if complete:
        return {
            **common,
            "scenario_names": list(scenario_names),
            "tasks_sha256": _canonical_json_sha256(tasks),
            "tasks": tasks,
        }
    last_task = tasks[-1] if tasks else None
    return {
        **common,
        "last_task": (
            {
                key: last_task.get(key)
                for key in (
                    "order_index",
                    "scenario",
                    "state_dir",
                    "registry_manifest_sha256",
                    "tool_lifecycle_sha256",
                    "routed_generated_tool_names",
                    "routed_inventory_sha256",
                )
            }
            if last_task is not None
            else None
        ),
        "crash_recovery_note": (
            "Exact completed task records and registry states are stored under tasks/."
        ),
    }


def _write_inventory_authority_manifest(
    authority_root: Path,
    *,
    scenario_names: tuple[str, ...],
    shared_context: dict[str, object],
    source_actor_selection_mode: str,
    source_generation_enabled: bool,
    tasks: list[dict[str, object]],
    complete: bool,
) -> Path:
    filename = (
        "inventory_authority.json" if complete else "inventory_authority.partial.json"
    )
    path = authority_root / filename
    payload = _authority_manifest_payload(
        scenario_names=scenario_names,
        shared_context=shared_context,
        source_actor_selection_mode=source_actor_selection_mode,
        source_generation_enabled=source_generation_enabled,
        tasks=tasks,
        complete=complete,
    )
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if complete:
        partial = authority_root / "inventory_authority.partial.json"
        if partial.exists():
            partial.unlink()
    return path


def _authority_state_dir(authority_root: Path, task: dict[str, object]) -> Path:
    relative = task.get("state_dir")
    if not isinstance(relative, str) or not relative:
        raise ValueError("Inventory authority task has no state_dir.")
    root = authority_root.resolve()
    state_dir = (authority_root / relative).resolve()
    if not state_dir.is_relative_to(root):
        raise ValueError(
            f"Inventory authority task state escapes the authority root: {relative!r}."
        )
    return state_dir


def _validate_authority_state_files(
    authority_root: Path,
    task: dict[str, object],
) -> None:
    state_dir = _authority_state_dir(authority_root, task)
    if not state_dir.is_dir():
        raise ValueError(f"Inventory authority state directory is missing: {state_dir}")
    for filename, prefix in (
        ("registry_manifest.json", "registry_manifest"),
        ("tool_lifecycle.json", "tool_lifecycle"),
    ):
        path = state_dir / filename
        expected_present = task.get(f"{prefix}_present")
        if not isinstance(expected_present, bool):
            raise ValueError(
                f"Inventory authority task has invalid {prefix}_present metadata."
            )
        if path.is_file() != expected_present:
            raise ValueError(
                f"Inventory authority {filename} presence mismatch in {state_dir}."
            )
        expected_digest = task.get(f"{prefix}_sha256")
        observed_digest = _sha256_file(path)
        if observed_digest != expected_digest:
            raise ValueError(
                f"Inventory authority {filename} hash mismatch in {state_dir}: "
                f"expected {expected_digest!r}, observed {observed_digest!r}."
            )


def _load_inventory_authority(
    authority_root: Path,
    *,
    registry_root: Path,
    scenario_names: tuple[str, ...],
    shared_context: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Load and fully validate a complete donor authority before any actor call."""

    _assert_separate_authority_and_registry_roots(authority_root, registry_root)
    manifest_path = authority_root / "inventory_authority.json"
    if not manifest_path.is_file():
        raise ValueError(f"Complete inventory authority is missing: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read inventory authority: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Inventory authority root must be a JSON object.")
    if payload.get("artifact_type") != INVENTORY_AUTHORITY_ARTIFACT:
        raise ValueError("Inventory authority artifact_type is invalid.")
    if payload.get("schema_version") != INVENTORY_AUTHORITY_SCHEMA_VERSION:
        raise ValueError("Inventory authority schema_version is unsupported.")
    if payload.get("complete") is not True:
        raise ValueError("Inventory authority is incomplete.")
    stored_shared_context = payload.get("shared_context")
    if not isinstance(stored_shared_context, dict):
        raise ValueError("Inventory authority shared_context must be a JSON object.")
    if payload.get("shared_context_sha256") != _canonical_json_sha256(
        stored_shared_context
    ):
        raise ValueError("Inventory authority shared-context hash is invalid.")
    if stored_shared_context != shared_context:
        mismatches = _shared_context_mismatch_fields(
            stored_shared_context,
            shared_context,
        )
        raise ValueError(
            "Inventory authority shared execution context mismatch: "
            + ", ".join(mismatches)
        )
    if payload.get("source_actor_selection_mode") != "policy":
        raise ValueError(
            "Inventory authority replay requires a policy-selection source arm."
        )
    if not isinstance(payload.get("source_generation_enabled"), bool):
        raise ValueError(
            "Inventory authority source_generation_enabled must be a boolean."
        )
    expected_names = list(scenario_names)
    if payload.get("scenario_names") != expected_names:
        raise ValueError("Inventory authority scenario order does not match the run.")
    if payload.get("scenario_order_sha256") != _scenario_order_sha256(scenario_names):
        raise ValueError("Inventory authority scenario-order hash is invalid.")
    if payload.get("expected_task_count") != len(scenario_names):
        raise ValueError("Inventory authority expected task count is invalid.")
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not all(
        isinstance(task, dict) for task in raw_tasks
    ):
        raise ValueError("Inventory authority tasks must be a list of objects.")
    tasks = [dict(task) for task in raw_tasks]
    if payload.get("task_count") != len(scenario_names) or len(tasks) != len(
        scenario_names
    ):
        raise ValueError("Inventory authority task count is incomplete.")
    if payload.get("tasks_sha256") != _canonical_json_sha256(tasks):
        raise ValueError("Inventory authority task-record hash is invalid.")
    for index, (scenario_name, task) in enumerate(zip(scenario_names, tasks)):
        if task.get("order_index") != index or task.get("scenario") != scenario_name:
            raise ValueError(
                "Inventory authority task identity mismatch at index "
                f"{index}: expected {scenario_name!r}."
            )
        _validate_authority_state_files(authority_root, task)
    return payload, tasks


def _restore_authority_state(
    *,
    authority_root: Path,
    registry_root: Path,
    task: dict[str, object],
) -> None:
    """Force the mutable exposure registry to the donor's exact pre-task bytes."""

    state_dir = _authority_state_dir(authority_root, task)
    for filename, prefix in (
        ("registry_manifest.json", "registry_manifest"),
        ("tool_lifecycle.json", "tool_lifecycle"),
    ):
        target = registry_root / filename
        if task[f"{prefix}_present"]:
            shutil.copy2(state_dir / filename, target)
        elif target.exists():
            target.unlink()
        observed_digest = _sha256_file(target)
        expected_digest = task[f"{prefix}_sha256"]
        if observed_digest != expected_digest:
            raise InventoryAuthorityError(
                f"Restored inventory authority {filename} hash mismatch: "
                f"expected {expected_digest!r}, observed {observed_digest!r}."
            )


def _routed_inventory_record(
    *,
    order_index: int,
    scenario_name: str,
    state: dict[str, object],
    original_tool_order: list[str],
    original_tool_allow_list: list[str] | None,
    routed_entries: list[Any],
    routing_decisions: dict[str, Any],
    enhanced_tool_order: list[str],
    enhanced_tool_allow_list: list[str] | None,
) -> dict[str, object]:
    routed_entry_payloads = [entry.to_json() for entry in routed_entries]
    routed_names = [entry.tool.spec.tool_name for entry in routed_entries]
    decision_payload = {
        tool_name: decision.to_json()
        for tool_name, decision in sorted(routing_decisions.items())
    }
    inventory_material = {
        "registry_manifest_sha256": state["registry_manifest_sha256"],
        "tool_lifecycle_sha256": state["tool_lifecycle_sha256"],
        "original_tool_order": original_tool_order,
        "original_tool_allow_list": original_tool_allow_list,
        "routed_generated_entries": routed_entry_payloads,
        "routing_decisions": decision_payload,
        "enhanced_tool_order": enhanced_tool_order,
        "enhanced_tool_allow_list": enhanced_tool_allow_list,
    }
    return {
        "order_index": order_index,
        "scenario": scenario_name,
        **state,
        "original_tool_order": original_tool_order,
        "original_tool_allow_list": original_tool_allow_list,
        "routed_generated_tool_names": routed_names,
        "routed_generated_entries_sha256": _canonical_json_sha256(
            routed_entry_payloads
        ),
        "routing_decisions": decision_payload,
        "enhanced_tool_order": enhanced_tool_order,
        "enhanced_tool_allow_list": enhanced_tool_allow_list,
        "routed_inventory_sha256": _canonical_json_sha256(inventory_material),
    }


def _assert_replayed_inventory(
    expected: dict[str, object],
    observed: dict[str, object],
) -> None:
    fields = (
        "order_index",
        "scenario",
        "registry_manifest_present",
        "registry_manifest_sha256",
        "tool_lifecycle_present",
        "tool_lifecycle_sha256",
        "original_tool_order",
        "original_tool_allow_list",
        "routed_generated_tool_names",
        "routed_generated_entries_sha256",
        "routing_decisions",
        "enhanced_tool_order",
        "enhanced_tool_allow_list",
        "routed_inventory_sha256",
    )
    mismatches = [
        field for field in fields if expected.get(field) != observed.get(field)
    ]
    if mismatches:
        raise InventoryAuthorityError(
            "Matched-inventory replay diverged before actor inference for "
            f"{observed.get('scenario')!r}: {', '.join(mismatches)}."
        )


def _parse_tool_message_content(raw_content: object) -> object:
    if isinstance(raw_content, (dict, list, int, float, bool)) or raw_content is None:
        return raw_content
    if not isinstance(raw_content, str):
        return None
    text = raw_content.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text


def _tool_trace_events_from_execution_context(path: Path) -> list[dict[str, object]]:
    """Return actual ToolSandbox tool events from a serialized execution context."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    dbs = payload.get("_dbs")
    if not isinstance(dbs, dict):
        return []
    rows = dbs.get("SANDBOX")
    if not isinstance(rows, list):
        return []

    events: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_traces = row.get("tool_trace")
        if raw_traces is not None:
            trace_items = raw_traces if isinstance(raw_traces, list) else [raw_traces]
            for raw_trace in trace_items:
                trace = _parse_tool_message_content(raw_trace)
                if not isinstance(trace, dict):
                    continue
                tool_name = trace.get("tool_name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                event = dict(trace)
                event["_sandbox_message_index"] = row.get("sandbox_message_index")
                event["_openai_function_name"] = row.get("openai_function_name")
                events.append(event)
            continue
        # Scrambled-tool settings may omit tool_trace rows for attempted calls,
        # especially failures. The execution content still contains the
        # canonical ToolSandbox callable, so preserve state-changing attempts
        # for side-effect checks.
        content = row.get("content")
        if not isinstance(content, str):
            continue
        match = re.search(r"_response\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", content)
        if not match:
            continue
        tool_name = match.group(1)
        if not tool_name.startswith(("add_", "modify_", "remove_", "send_", "set_")):
            continue
        events.append(
            {
                "tool_name": tool_name,
                "arguments": {},
                "result": row.get("tool_call_exception"),
                "_sandbox_message_index": row.get("sandbox_message_index"),
                "_openai_function_name": row.get("openai_function_name"),
                "_call_attempt": True,
            }
        )
    return events


def _conversation_generated_tool_results(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
) -> dict[str, list[object]]:
    generated_tool_set = set(generated_tools)
    if not generated_tool_set:
        return {}
    path = output_directory / "trajectories" / scenario_name / "conversation.json"
    if not path.exists():
        return {}
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(messages, list):
        return {}

    results: dict[str, list[object]] = {}
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        tool_name = message.get("name")
        if not isinstance(tool_name, str) or tool_name not in generated_tool_set:
            continue
        results.setdefault(tool_name, []).append(
            _parse_tool_message_content(message.get("content"))
        )
    return results


def _reconcile_generated_tool_calls_from_conversation(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
    generated_called: list[str],
) -> list[str]:
    """Treat executed generated-tool result messages as generated calls.

    The primary reuse callback remains the source of record for registry reuse.
    This transcript reconciliation protects same-task retry and dashboard
    attribution when ToolSandbox serializes a generated tool result but the
    in-memory callback did not update the local scenario accounting.
    """

    if not generated_tools:
        return generated_called
    reconciled = list(generated_called)
    for tool_name in _conversation_generated_tool_results(
        output_directory,
        scenario_name,
        generated_tools,
    ):
        if tool_name not in reconciled:
            reconciled.append(tool_name)
    return reconciled


def _side_effect_tool_name(tool_name: object, required: set[str]) -> str | None:
    if not isinstance(tool_name, str):
        return None
    name = tool_name.strip()
    if name in required and name.startswith(
        ("add_", "modify_", "remove_", "send_", "set_")
    ):
        return name
    return None


def _explicit_side_effect_calls_from_output(
    output: dict[str, object],
    *,
    required_side_effect_calls: tuple[str, ...],
) -> set[str]:
    required = set(required_side_effect_calls)
    explicit: set[str] = set()
    for key in ("downstream_tool_name", "tool_name"):
        tool_name = _side_effect_tool_name(output.get(key), required)
        if tool_name:
            explicit.add(tool_name)
    action_sequence = output.get("action_sequence")
    if isinstance(action_sequence, list):
        for action in action_sequence:
            if not isinstance(action, dict):
                continue
            tool_name = _side_effect_tool_name(action.get("tool_name"), required)
            if tool_name:
                explicit.add(tool_name)
    if "add_reminder" in required and (
        output.get("should_call_add_reminder") is True
        or isinstance(output.get("add_reminder_kwargs"), dict)
    ):
        explicit.add("add_reminder")
    return explicit


def _output_is_preparatory_search_followup(output: dict[str, object]) -> bool:
    """Return True for helper outputs that only prepare original search calls."""

    if (
        output.get("should_call_search_contacts") is True
        or output.get("should_call_search_messages") is True
    ):
        return True
    next_step = str(output.get("next_step") or "").lower()
    return "search_contacts" in next_step or "search_messages" in next_step


def _assistant_tool_names(message: dict[str, object]) -> list[str]:
    names: list[str] = []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return names
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict):
            continue
        tool_name = function.get("name")
        if isinstance(tool_name, str):
            names.append(tool_name)
    return names


def _next_assistant_tool_names(
    messages: list[object],
    *,
    start_index: int,
) -> list[str]:
    for lookahead in messages[start_index + 1 :]:
        if not isinstance(lookahead, dict):
            continue
        if lookahead.get("role") == "user":
            return []
        if lookahead.get("role") == "assistant" and lookahead.get("tool_calls"):
            return _assistant_tool_names(lookahead)
    return []


def _next_trace_tool_names(
    events: list[dict[str, object]],
    *,
    start_index: int,
) -> set[str]:
    for event in events[start_index + 1 :]:
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str):
            return {tool_name}
    return set()


def _later_trace_tool_names(
    events: list[dict[str, object]],
    *,
    start_index: int,
) -> set[str]:
    later_tools: set[str] = set()
    for event in events[start_index + 1 :]:
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str):
            later_tools.add(tool_name)
    return later_tools


def _side_effect_followup_failures_from_trace_events(
    events: list[dict[str, object]],
    *,
    helper_name: str,
    required_side_effect_calls: tuple[str, ...],
) -> bool:
    saw_helper_result = False
    for index, event in enumerate(events):
        if event.get("tool_name") != helper_name:
            continue
        saw_helper_result = True
        output = event.get("result")
        next_tools = _next_trace_tool_names(events, start_index=index)
        required = set(required_side_effect_calls)
        if isinstance(output, dict):
            declares_followup = any(
                key in output
                for key in (
                    "should_call_add_reminder",
                    "should_call",
                    "should_call_tool",
                    "should_call_tools",
                    "downstream_tool_name",
                    "tool_name",
                    "action_sequence",
                    "add_reminder_kwargs",
                    "downstream_tool_kwargs",
                )
            )
            if not declares_followup:
                continue
            explicit_required = _explicit_side_effect_calls_from_output(
                output,
                required_side_effect_calls=required_side_effect_calls,
            )
            if explicit_required:
                required = explicit_required
            elif _output_is_preparatory_search_followup(output):
                continue
            if (
                output.get("should_call_add_reminder") is False
                or output.get("should_call") is False
                or output.get("should_call_tool") is False
                or output.get("should_call_tools") is False
            ):
                if (
                    output.get("should_call_search_contacts") is True
                    and output.get("should_call_tools") is False
                ):
                    if required & next_tools:
                        return True
                    continue
                selection_only_bridge = (
                    isinstance(output.get("selected_record"), dict)
                    and bool(output.get("selected_record"))
                    and str(output.get("downstream_tool_name") or "")
                    in required_side_effect_calls
                    and str(output.get("final_answer_recommendation") or "").startswith(
                        "use_selected_record:"
                    )
                )
                if selection_only_bridge:
                    later_tools = _later_trace_tool_names(events, start_index=index)
                    if not (required & later_tools):
                        return True
                    continue
                if required & next_tools:
                    return True
                continue
            if (
                output.get("should_call_add_reminder") is True
                or output.get("should_call") is True
                or output.get("should_call_tool") is True
                or output.get("should_call_tools") is True
            ):
                if required & next_tools:
                    continue
                later_tools = _later_trace_tool_names(events, start_index=index)
                if required & later_tools:
                    continue
                return True
        else:
            # Scalar/extraction helpers may list downstream tools in their broad
            # preservation contract because their values can be used before a
            # later side effect. The helper output itself does not declare a
            # side-effect call, so absence of that call is not a safety incident.
            continue
        if not (required & _later_trace_tool_names(events, start_index=index)):
            return True
    return not saw_helper_result


def _side_effect_followup_failures(
    messages: list[object],
    *,
    helper_name: str,
    required_original_tool_calls: tuple[str, ...],
    actual_tool_trace_events: list[dict[str, object]] | None = None,
) -> bool:
    """Return True when a helper's declared follow-up contract is violated.

    Abstaining helpers should not trigger their side-effect tool directly, but
    they may resolve missing prerequisites first and call the side-effect later.
    """

    required_side_effect_calls = tuple(
        tool_name
        for tool_name in required_original_tool_calls
        if tool_name.startswith(("add_", "modify_", "remove_", "send_", "set_"))
    )
    if not required_side_effect_calls:
        return False
    if actual_tool_trace_events:
        traced_tools = {
            str(event.get("tool_name") or "")
            for event in actual_tool_trace_events
            if isinstance(event, dict)
        }
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "tool":
                continue
            payload = _parse_tool_message_content(message.get("content"))
            if not isinstance(payload, dict):
                continue
            native_action = str(payload.get("native_action") or "")
            if (
                str(payload.get("status") or "").lower() == "success"
                and native_action in required_side_effect_calls
                and native_action in traced_tools
                and payload.get("native_result") is not None
            ):
                return False
    if actual_tool_trace_events:
        trace_failure = _side_effect_followup_failures_from_trace_events(
            actual_tool_trace_events,
            helper_name=helper_name,
            required_side_effect_calls=required_side_effect_calls,
        )
        if not trace_failure:
            return False
        # ToolSandbox trace rows can omit failed original tool attempts while the
        # conversation still records the assistant tool call and tool error. Use
        # the conversation as a conservative fallback before declaring that a
        # helper failed to preserve a required downstream side-effect call.
    saw_helper_result = False
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool" or message.get("name") != helper_name:
            continue
        saw_helper_result = True
        output = _parse_tool_message_content(message.get("content"))
        next_tools = set(_next_assistant_tool_names(messages, start_index=index))
        required = set(required_side_effect_calls)
        if isinstance(output, dict):
            declares_followup = any(
                key in output
                for key in (
                    "should_call_add_reminder",
                    "should_call",
                    "should_call_tool",
                    "should_call_tools",
                    "downstream_tool_name",
                    "tool_name",
                    "action_sequence",
                    "add_reminder_kwargs",
                    "downstream_tool_kwargs",
                )
            )
            if not declares_followup:
                # Scalar/extraction helpers may preserve one of several original
                # producers without preparing the final side-effect call. Do not
                # mark them unsafe simply because a side-effect tool named in the
                # broad preservation contract was not needed for this scenario.
                continue
            explicit_required = _explicit_side_effect_calls_from_output(
                output,
                required_side_effect_calls=required_side_effect_calls,
            )
            if explicit_required:
                required = explicit_required
            elif _output_is_preparatory_search_followup(output):
                continue
            if (
                output.get("should_call_add_reminder") is False
                or output.get("should_call") is False
                or output.get("should_call_tool") is False
                or output.get("should_call_tools") is False
            ):
                if (
                    output.get("should_call_search_contacts") is True
                    and output.get("should_call_tools") is False
                ):
                    if required & next_tools:
                        return True
                    continue
                selection_only_bridge = (
                    isinstance(output.get("selected_record"), dict)
                    and bool(output.get("selected_record"))
                    and str(output.get("downstream_tool_name") or "")
                    in required_side_effect_calls
                    and str(output.get("final_answer_recommendation") or "").startswith(
                        "use_selected_record:"
                    )
                )
                if selection_only_bridge:
                    bridge_followup_tools: set[str] = set()
                    for later in messages[index + 1 :]:
                        if isinstance(later, dict) and later.get("role") == "assistant":
                            bridge_followup_tools.update(_assistant_tool_names(later))
                    if not (required & bridge_followup_tools):
                        return True
                    continue
                if required & next_tools:
                    return True
                continue
            if (
                output.get("should_call_add_reminder") is True
                or output.get("should_call") is True
                or output.get("should_call_tool") is True
                or output.get("should_call_tools") is True
            ):
                if required & next_tools:
                    continue
                later_followup_tools: set[str] = set()
                for later in messages[index + 1 :]:
                    if isinstance(later, dict) and later.get("role") == "assistant":
                        later_followup_tools.update(_assistant_tool_names(later))
                if required & later_followup_tools:
                    continue
                return True
        else:
            # Non-mapping helper outputs, such as deterministic timestamp values,
            # do not declare a downstream side-effect contract.
            continue
        later_tools: set[str] = set()
        for later in messages[index + 1 :]:
            if isinstance(later, dict) and later.get("role") == "assistant":
                later_tools.update(_assistant_tool_names(later))
        if not (required & later_tools):
            return True
    return not saw_helper_result


@dataclass(frozen=True)
class SageRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    registry_dir: Path
    generation_model: str | None = None
    run_type: str = "sage_online"
    recurrence_threshold: int = 2
    base_tool_policy: str = UPSTREAM_POLICY
    actor_selection_mode: str = "policy"
    inventory_authority_capture_dir: Path | None = None
    inventory_authority_replay_dir: Path | None = None
    resume_from_dir: Path | None = None
    resume_completed_limit: int | None = None
    manifest_path: Path = Path("")
    reflection_control_rows: dict[str, dict[str, Any]] | None = None
    require_fresh_reflection_control: bool = False
    failure_memory_path: Path | None = Path("artifacts/summaries/failure_memory.json")


def run_sage_with_registry(
    config: SageRunConfig,
    *,
    generator: GeneratedToolFactory | None = None,
    scenarios: dict[str, Scenario] | None = None,
    progress_hook: ProgressHook | None = None,
    event_hook: EventHook | None = None,
) -> Path:
    """Run ToolSandbox scenarios with accepted generated tools available."""
    if (
        config.inventory_authority_capture_dir is not None
        and config.inventory_authority_replay_dir is not None
    ):
        raise ValueError(
            "Inventory authority capture and replay are mutually exclusive."
        )
    if (
        config.inventory_authority_capture_dir is not None
        and config.actor_selection_mode != "policy"
    ):
        raise ValueError(
            "Inventory authority capture requires actor_selection_mode='policy'."
        )
    if (
        config.inventory_authority_replay_dir is not None
        and config.actor_selection_mode != "auto"
    ):
        raise ValueError(
            "Inventory authority replay requires actor_selection_mode='auto'."
        )
    if (
        config.inventory_authority_capture_dir is not None
        or config.inventory_authority_replay_dir is not None
    ) and (
        config.resume_from_dir is not None or config.resume_completed_limit is not None
    ):
        raise ValueError(
            "Matched-inventory capture/replay requires a fresh complete task sequence."
        )
    if config.inventory_authority_replay_dir is not None and generator is not None:
        raise ValueError(
            "Inventory authority replay requires generator=None. The replay arm "
            "consumes the donor's validated actor-ready registry state and must not "
            "run arm-specific birth or lifecycle updates."
        )
    store = RegistryStore(config.registry_dir)
    capture_root = config.inventory_authority_capture_dir
    replay_root = config.inventory_authority_replay_dir
    if replay_root is not None:
        existing_registry_paths = sorted(path.name for path in store.root.iterdir())
        if existing_registry_paths:
            raise ValueError(
                "Inventory authority replay requires an empty registry directory; "
                "found pre-existing state: " + ", ".join(existing_registry_paths)
            )
    capture_tasks: list[dict[str, object]] = []
    replay_manifest: dict[str, object] | None = None
    replay_tasks: list[dict[str, object]] = []
    replayed_scenarios: list[str] = []
    authority_shared_context: dict[str, object] | None = None
    if capture_root is not None or replay_root is not None:
        authority_shared_context = _inventory_authority_shared_context(config)
    authority_shared_context_sha256 = (
        _canonical_json_sha256(authority_shared_context)
        if authority_shared_context is not None
        else None
    )
    if capture_root is not None:
        _prepare_inventory_authority_capture(
            capture_root,
            registry_root=store.root,
        )
    if replay_root is not None:
        if authority_shared_context is None:
            raise AssertionError("Inventory replay shared context was not captured.")
        replay_manifest, replay_tasks = _load_inventory_authority(
            replay_root,
            registry_root=store.root,
            scenario_names=config.scenario_names,
            shared_context=authority_shared_context,
        )
    registry_tools = sorted(store.load_entries())
    visible_generated_by_scenario: dict[str, list[str]] = {}
    called_generated_by_scenario: dict[str, list[str]] = {}
    selection_context_by_scenario: dict[str, dict[str, object]] = {}
    baseline_scenario_by_name: dict[str, Scenario] = {}

    birth_controller: OnlineBirthController | None = None
    reflection_controller: SelfEvolutionReflectionController | None = None
    registry_load_logged = False
    mutate_registry_reuse_counts = generator is not None

    def transform(name: str, scenario: Scenario, output_directory: Path) -> Scenario:
        nonlocal birth_controller, registry_load_logged, reflection_controller
        nonlocal registry_tools
        if generator is not None and birth_controller is None:

            def birth_event_hook(event: str, payload: dict[str, object]) -> None:
                if event_hook is not None:
                    event_hook(event, output_directory, payload)

            birth_controller = OnlineBirthController(
                store=store,
                generator=generator,
                output_dir=output_directory,
                recurrence_threshold=config.recurrence_threshold,
                event_hook=birth_event_hook,
                failure_memory_path=config.failure_memory_path,
            )
        if generator is not None and reflection_controller is None:
            reflection_controller = SelfEvolutionReflectionController.from_env(
                store=store,
                output_dir=output_directory,
                agent=config.agent,
                user=config.user,
                base_tool_policy=config.base_tool_policy,
                manifest_path=config.manifest_path,
                fresh_control_rows=config.reflection_control_rows,
                require_fresh_control=config.require_fresh_reflection_control,
            )
        visible_task_context = visible_task_context_from_scenario(scenario)
        routing_context_text = visible_task_context.routing_text()
        routing_context_label = visible_task_context.generation_label()
        routing_family_key = visible_task_context.primary_family_key
        authority_order_index: int | None = None
        authority_state: dict[str, object] | None = None
        expected_authority_task: dict[str, object] | None = None
        if capture_root is not None or replay_root is not None:
            authority_order_index = _active_authority_order_index(
                name,
                config.scenario_names,
            )
            completed_authority_tasks = (
                len(capture_tasks)
                if capture_root is not None
                else len(replayed_scenarios)
            )
            if authority_order_index != completed_authority_tasks:
                raise InventoryAuthorityError(
                    "Matched-inventory tasks must be transformed exactly once in order: "
                    f"expected index {completed_authority_tasks}, observed "
                    f"{authority_order_index}."
                )
        if replay_root is not None:
            if authority_order_index is None:
                raise InventoryAuthorityError(
                    "Inventory replay has no active scenario-order index."
                )
            expected_authority_task = replay_tasks[authority_order_index]
            _restore_authority_state(
                authority_root=replay_root,
                registry_root=store.root,
                task=expected_authority_task,
            )
            if not registry_load_logged:
                # The replay registry may begin empty or contain unrelated state.
                # Report the donor's first actor-ready state, not that disposable
                # bootstrap state, as the replay's loaded inventory.
                registry_tools = sorted(store.load_entries())
            authority_state = {
                key: expected_authority_task[key]
                for key in (
                    "state_dir",
                    "registry_manifest_present",
                    "registry_manifest_sha256",
                    "tool_lifecycle_present",
                    "tool_lifecycle_sha256",
                )
            }
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "inventory_authority_state_restored",
                    "scenario": name,
                    "order_index": authority_order_index,
                    "authority_root": str(replay_root),
                    "routed_inventory_sha256": expected_authority_task.get(
                        "routed_inventory_sha256"
                    ),
                },
            )
        elif birth_controller is not None:
            accepted_tools = birth_controller.prime_before_scenario(name, scenario)
            if accepted_tools:
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "jit_birth_tools_available_for_same_task",
                        "scenario": name,
                        "accepted_tools": accepted_tools,
                        "registry_dir": str(config.registry_dir),
                    },
                )
                if event_hook is not None:
                    event_hook(
                        "jit_birth_tools_available_for_same_task",
                        output_directory,
                        {
                            "scenario": name,
                            "accepted_tools": accepted_tools,
                            "registry_dir": str(config.registry_dir),
                        },
                    )
        if capture_root is not None:
            if authority_order_index is None:
                raise InventoryAuthorityError(
                    "Inventory capture has no active scenario-order index."
                )
            authority_state = _authority_state_record(
                authority_root=capture_root,
                registry_root=store.root,
                order_index=authority_order_index,
                scenario_name=name,
            )
        if not registry_load_logged:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "registry_load",
                    "registry_dir": str(config.registry_dir),
                    "registry_tools": registry_tools,
                    "registry_size": len(registry_tools),
                    "base_tool_policy": config.base_tool_policy,
                    "generation_enabled": generator is not None,
                },
            )
            if event_hook is not None:
                event_hook(
                    "registry_loaded",
                    output_directory,
                    {
                        "registry_dir": str(config.registry_dir),
                        "registry_tools": registry_tools,
                        "registry_size": len(registry_tools),
                        "base_tool_policy": config.base_tool_policy,
                        "generation_enabled": generator is not None,
                    },
                )
            registry_load_logged = True

        baseline_scenario_by_name[name] = scenario

        def record_reuse(tool_name: str) -> None:
            if mutate_registry_reuse_counts:
                store.record_reuse(tool_name)
            called = called_generated_by_scenario.setdefault(name, [])
            if tool_name not in called:
                called.append(tool_name)
            append_jsonl(
                output_directory / "reuse_events.jsonl",
                {
                    "scenario": name,
                    "tool_name": tool_name,
                    "event": "generated_tool_invoked",
                },
            )
            if event_hook is not None:
                event_hook(
                    "tool_reused",
                    output_directory,
                    {
                        "scenario": name,
                        "tool_name": tool_name,
                        "registry_dir": str(config.registry_dir),
                    },
                )

        loaded_entries = store.load_entries()
        retained_tools_loaded = sorted(loaded_entries)
        available_base_tools = set(
            scenario.starting_context.get_available_tools(scrambling_allowed=False)
        )
        lifecycle_state = load_tool_lifecycle_routing_state(store.root)
        _routed_entries, routing_decisions = route_registry_entries(
            loaded_entries,
            name,
            available_base_tools=available_base_tools,
            lifecycle_state=lifecycle_state,
            task_context_text=routing_context_text,
            task_family_key=routing_family_key,
        )
        visibility_by_tool = {
            tool_name: (decision.visible, decision.reason)
            for tool_name, decision in routing_decisions.items()
        }
        shortlisted_generated_tools = [
            tool_name
            for tool_name, (is_visible, _reason) in visibility_by_tool.items()
            if is_visible
        ]
        filtered_out_generated_tools = [
            tool_name
            for tool_name in retained_tools_loaded
            if tool_name not in set(shortlisted_generated_tools)
        ]
        filtered_out_reasons = {
            tool_name: visibility_by_tool.get(
                tool_name, (False, "scenario_relevance_filter")
            )[1]
            for tool_name in filtered_out_generated_tools
        }
        original_tool_order = list(scenario.starting_context.name_to_tool)
        original_tool_allow_list = (
            None
            if scenario.starting_context.tool_allow_list is None
            else list(scenario.starting_context.tool_allow_list)
        )
        enhanced = with_registry_tools(
            scenario,
            store,
            on_reuse=record_reuse,
            scenario_name=name,
            task_context_text=routing_context_text,
            task_family_key=routing_family_key,
        )
        enhanced_tool_order = list(enhanced.starting_context.name_to_tool)
        enhanced_tool_allow_list = (
            None
            if enhanced.starting_context.tool_allow_list is None
            else list(enhanced.starting_context.tool_allow_list)
        )
        if authority_state is not None and authority_order_index is not None:
            observed_authority_task = _routed_inventory_record(
                order_index=authority_order_index,
                scenario_name=name,
                state=authority_state,
                original_tool_order=original_tool_order,
                original_tool_allow_list=original_tool_allow_list,
                routed_entries=_routed_entries,
                routing_decisions=routing_decisions,
                enhanced_tool_order=enhanced_tool_order,
                enhanced_tool_allow_list=enhanced_tool_allow_list,
            )
            if capture_root is not None:
                state_dir = _authority_state_dir(
                    capture_root,
                    observed_authority_task,
                )
                (state_dir / "inventory_task.json").write_text(
                    json.dumps(observed_authority_task, indent=2) + "\n",
                    encoding="utf-8",
                )
                capture_tasks.append(observed_authority_task)
                _write_inventory_authority_manifest(
                    capture_root,
                    scenario_names=config.scenario_names,
                    shared_context=authority_shared_context or {},
                    source_actor_selection_mode=config.actor_selection_mode,
                    source_generation_enabled=generator is not None,
                    tasks=capture_tasks,
                    complete=False,
                )
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "inventory_authority_task_captured",
                        "scenario": name,
                        "order_index": authority_order_index,
                        "authority_root": str(capture_root),
                        "routed_generated_tool_names": observed_authority_task[
                            "routed_generated_tool_names"
                        ],
                        "routed_inventory_sha256": observed_authority_task[
                            "routed_inventory_sha256"
                        ],
                    },
                )
            elif expected_authority_task is not None:
                _assert_replayed_inventory(
                    expected_authority_task,
                    observed_authority_task,
                )
                replayed_scenarios.append(name)
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "inventory_authority_task_matched",
                        "scenario": name,
                        "order_index": authority_order_index,
                        "authority_root": str(replay_root),
                        "routed_generated_tool_names": observed_authority_task[
                            "routed_generated_tool_names"
                        ],
                        "routed_inventory_sha256": observed_authority_task[
                            "routed_inventory_sha256"
                        ],
                    },
                )
        available_tools = set(
            enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        )
        generated_tools = [
            tool_name
            for tool_name in sorted(store.load_entries())
            if tool_name in available_tools
        ]
        visible_generated_by_scenario[name] = generated_tools
        priority_injection_changed_tool_order = bool(
            generated_tools
            and enhanced_tool_order[: len(generated_tools)] == generated_tools
            and enhanced_tool_order != original_tool_order
        )
        selection_context_by_scenario[name] = {
            "retained_tools_loaded": retained_tools_loaded,
            "filtered_out_generated_tools": filtered_out_generated_tools,
            "filtered_out_reasons": filtered_out_reasons,
            "shortlisted_generated_tools": shortlisted_generated_tools,
            "task_context_label": routing_context_label,
            "task_family_key": routing_family_key,
            "priority_injection_changed_tool_order": (
                priority_injection_changed_tool_order
            ),
            "relevance_gating_hid_retained_tool": bool(filtered_out_generated_tools),
        }
        append_jsonl(
            output_directory / "scenario_tool_visibility.jsonl",
            {
                "scenario": name,
                "base_tool_policy": config.base_tool_policy,
                "retained_tools_loaded": retained_tools_loaded,
                "filtered_out_generated_tools": filtered_out_generated_tools,
                "filtered_out_reasons": filtered_out_reasons,
                "shortlisted_generated_tools": shortlisted_generated_tools,
                "priority_injection_changed_tool_order": (
                    priority_injection_changed_tool_order
                ),
                "relevance_gating_hid_retained_tool": bool(
                    filtered_out_generated_tools
                ),
                "routing_decisions": {
                    tool_name: decision.to_json()
                    for tool_name, decision in routing_decisions.items()
                },
                "tool_allow_list": list(
                    enhanced.starting_context.tool_allow_list or []
                ),
                "available_tools": sorted(
                    enhanced.starting_context.get_available_tools(
                        scrambling_allowed=False
                    )
                ),
                "generated_tools": generated_tools,
            },
        )
        return enhanced

    def after_result(
        name: str,
        scenario: Scenario,
        result: dict[str, object],
        output_directory: Path,
    ) -> dict[str, object]:
        generated_visible = visible_generated_by_scenario.get(name, [])
        generated_called = list(called_generated_by_scenario.get(name, []))
        for tool_name in _reuse_log_tools(output_directory, name):
            if tool_name not in generated_called:
                generated_called.append(tool_name)
        generated_attempted, generated_failed = _conversation_generated_tool_attempts(
            output_directory,
            name,
            generated_visible,
        )
        generated_called = _reconcile_generated_tool_calls_from_conversation(
            output_directory,
            name,
            generated_visible,
            generated_called,
        )
        if generated_failed:
            failed_set = set(generated_failed)
            generated_called = [
                tool_name
                for tool_name in generated_called
                if tool_name not in failed_set
            ]
        generated_not_called = [
            tool for tool in generated_visible if tool not in set(generated_called)
        ]
        generated_not_attempted = [
            tool for tool in generated_visible if tool not in set(generated_attempted)
        ]
        raw_similarity = result.get("similarity", 0.0)
        try:
            similarity = (
                float(raw_similarity)
                if isinstance(raw_similarity, (int, float, str))
                else 0.0
            )
        except ValueError:
            similarity = 0.0
        raw_outcome_similarity = result.get("outcome_similarity")
        try:
            outcome_similarity = (
                float(raw_outcome_similarity)
                if isinstance(raw_outcome_similarity, (int, float, str))
                else None
            )
        except ValueError:
            outcome_similarity = None
        generated_not_called = [
            tool for tool in generated_visible if tool not in set(generated_called)
        ]
        generated_not_attempted = [
            tool for tool in generated_visible if tool not in set(generated_attempted)
        ]
        selection_status = (
            "generated_tool_called"
            if generated_called
            else "generated_tool_attempt_failed"
            if generated_failed
            else "generated_tool_attempted_without_success"
            if generated_attempted
            else "generated_tool_visible_not_called"
            if generated_visible
            else "no_visible_generated_tools"
        )
        if generated_called:
            selection_reason = "retained_tool_invoked"
        elif generated_failed:
            selection_reason = "retained_tool_call_failed"
        elif generated_attempted:
            selection_reason = "retained_tool_attempted_without_success_trace"
        elif generated_visible:
            selection_reason = "retained_tool_visible_but_model_did_not_call_it"
        else:
            selection_reason = "no_retained_tool_visible_after_relevance_filter"
        context = selection_context_by_scenario.get(name, {})
        selection_record = {
            "scenario": name,
            "base_tool_policy": config.base_tool_policy,
            "retained_tools_loaded": context.get("retained_tools_loaded", []),
            "filtered_out_generated_tools": context.get(
                "filtered_out_generated_tools", []
            ),
            "filtered_out_reasons": context.get("filtered_out_reasons", {}),
            "shortlisted_generated_tools": context.get(
                "shortlisted_generated_tools", generated_visible
            ),
            "chosen_retained_tool": (
                generated_called[0]
                if generated_called
                else generated_attempted[0]
                if generated_attempted
                else None
            ),
            "priority_injection_changed_tool_order": context.get(
                "priority_injection_changed_tool_order", False
            ),
            "relevance_gating_hid_retained_tool": context.get(
                "relevance_gating_hid_retained_tool", False
            ),
            "generated_tools_visible": generated_visible,
            "generated_tools_attempted": generated_attempted,
            "generated_tools_failed": generated_failed,
            "generated_tools_called": generated_called,
            "generated_tools_not_called": generated_not_called,
            "generated_tools_not_attempted": generated_not_attempted,
            "visible_generated_tool_count": len(generated_visible),
            "attempted_generated_tool_count": len(generated_attempted),
            "failed_generated_tool_count": len(generated_failed),
            "called_generated_tool_count": len(generated_called),
            "selection_status": selection_status,
            "selection_reason": selection_reason,
            "not_called_reason": None
            if generated_called or generated_attempted or not generated_visible
            else "model_did_not_call_retained_tool",
            "similarity": similarity,
            "outcome_similarity": outcome_similarity,
            "exception_type": result.get("exception_type"),
            "failure_after_selection": similarity < 1.0
            or bool(result.get("exception_type")),
            "failure_after_outcome_selection": (
                outcome_similarity is not None and outcome_similarity < 1.0
            )
            or bool(result.get("exception_type")),
        }
        append_jsonl(
            output_directory / "scenario_tool_selection.jsonl",
            selection_record,
        )
        append_jsonl(output_directory / "selection_trace.jsonl", selection_record)
        # Side-effect preservation check: for helpers with required_original_tool_calls,
        # verify those tool names appear in the downstream conversation trajectory.
        side_effect_failures: list[str] = []
        if generated_called:
            loaded_entries_for_check = store.load_entries()
            conv_path = output_directory / "trajectories" / name / "conversation.json"
            conv_messages: list[object] = []
            if conv_path.exists():
                try:
                    conv_messages = json.loads(conv_path.read_text(encoding="utf-8"))
                    if not isinstance(conv_messages, list):
                        conv_messages = []
                except Exception:
                    pass
            actual_tool_trace_events = _tool_trace_events_from_execution_context(
                output_directory / "trajectories" / name / "execution_context.json"
            )
            for helper_name in generated_called:
                entry = loaded_entries_for_check.get(helper_name)
                if entry is None:
                    continue
                if native_action_tool_enabled(entry.tool):
                    continue
                required = tuple(entry.tool.spec.required_original_tool_calls)
                if _side_effect_followup_failures(
                    conv_messages,
                    helper_name=helper_name,
                    required_original_tool_calls=required,
                    actual_tool_trace_events=actual_tool_trace_events,
                ):
                    side_effect_failures.append(helper_name)
        if side_effect_failures:
            result["side_effect_preservation_failures"] = side_effect_failures
            append_jsonl(
                output_directory / "side_effect_preservation_report.jsonl",
                {
                    "scenario": name,
                    "side_effect_preservation_failures": side_effect_failures,
                    "generated_tools_called": generated_called,
                },
            )
        if reflection_controller is not None:
            reflection_controller.assess_scenario(
                scenario_name=name,
                baseline_scenario=baseline_scenario_by_name.get(name, scenario),
                result=result,
                selection_record=selection_record,
                side_effect_failures=side_effect_failures,
                task_context_label=selection_context_by_scenario.get(name, {}).get(
                    "task_context_label"
                ),
                task_family_key=selection_context_by_scenario.get(name, {}).get(
                    "task_family_key"
                ),
            )

        if birth_controller is None:
            checkpoint = _snapshot_registry_checkpoint(
                output_directory=output_directory,
                registry_dir=config.registry_dir,
                scenario_name=name,
            )
            if checkpoint is not None:
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "registry_checkpoint_written",
                        "scenario": name,
                        "checkpoint_dir": str(checkpoint),
                        "registry_dir": str(config.registry_dir),
                    },
                )
            return result
        trace_result = result
        visible_messages = _visible_conversation_messages_for_observation(
            output_directory,
            name,
        )
        if visible_messages:
            trace_result = dict(result)
            trace_result["messages"] = visible_messages
        visible_task_context_processed = (
            name in birth_controller.pre_scenario_visible_observations
        )
        visible_task_observations = (
            ()
            if visible_task_context_processed
            else classify_visible_task_observations(name, scenario)
        )
        observations = (
            *visible_task_observations,
            *classify_visible_trace_observations(name, scenario, trace_result),
        )
        if visible_task_context_processed:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "post_task_duplicate_visible_observation_skipped",
                    "scenario": name,
                    "reason": "visible_task_context_processed_before_task",
                },
            )
        for observation in observations:
            if event_hook is not None:
                event_hook(
                    "inadequacy_detected",
                    output_directory,
                    observation.to_json(),
                )
            birth_controller.observe(observation)
        result["sage_observations"] = [item.to_json() for item in observations]
        checkpoint = _snapshot_registry_checkpoint(
            output_directory=output_directory,
            registry_dir=config.registry_dir,
            scenario_name=name,
        )
        if checkpoint is not None:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "registry_checkpoint_written",
                    "scenario": name,
                    "checkpoint_dir": str(checkpoint),
                    "registry_dir": str(config.registry_dir),
                },
            )
        return result

    if replay_root is not None:
        # Any replay-transform error must abort before actor inference. This also
        # covers unexpected I/O or parse errors after the initial authority
        # preflight, not only explicit inventory-mismatch exceptions.
        setattr(transform, "fail_closed_scenario_transform", True)

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent=config.agent,
            user=config.user,
            scenario_names=config.scenario_names,
            output_dir=config.output_dir,
            processes=1,
            run_type=config.run_type,
            base_tool_policy=config.base_tool_policy,
            actor_selection_mode=config.actor_selection_mode,
            resume_from_dir=config.resume_from_dir,
            resume_completed_limit=config.resume_completed_limit,
        ),
        scenarios=scenarios,
        scenario_transform=transform,
        result_hook=after_result,
        progress_hook=progress_hook,
        event_hook=event_hook,
    )
    if authority_shared_context is not None:
        final_shared_context = _inventory_authority_shared_context(config)
        context_drift = _shared_context_mismatch_fields(
            authority_shared_context,
            final_shared_context,
        )
        if context_drift:
            raise InventoryAuthorityError(
                "Matched-inventory shared execution context changed during the run: "
                + ", ".join(context_drift)
            )
    authority_mode = "off"
    authority_root: Path | None = None
    authority_tasks_sha256: str | None = None
    authority_source_actor_selection_mode: str | None = None
    authority_source_generation_enabled: bool | None = None
    if capture_root is not None:
        authority_mode = "capture"
        authority_root = capture_root
        captured_names = [str(task.get("scenario") or "") for task in capture_tasks]
        if captured_names != list(config.scenario_names):
            raise InventoryAuthorityError(
                "Inventory authority capture did not cover the exact task sequence."
            )
        authority_path = _write_inventory_authority_manifest(
            capture_root,
            scenario_names=config.scenario_names,
            shared_context=authority_shared_context or {},
            source_actor_selection_mode=config.actor_selection_mode,
            source_generation_enabled=generator is not None,
            tasks=capture_tasks,
            complete=True,
        )
        authority_tasks_sha256 = _canonical_json_sha256(capture_tasks)
        authority_source_actor_selection_mode = config.actor_selection_mode
        authority_source_generation_enabled = generator is not None
        append_jsonl(
            output_directory / "sage_run_events.jsonl",
            {
                "event": "inventory_authority_capture_completed",
                "authority_path": str(authority_path),
                "task_count": len(capture_tasks),
                "tasks_sha256": authority_tasks_sha256,
                "shared_context_sha256": authority_shared_context_sha256,
                "source_actor_selection_mode": config.actor_selection_mode,
                "source_generation_enabled": generator is not None,
            },
        )
    elif replay_root is not None:
        authority_mode = "replay"
        authority_root = replay_root
        if replayed_scenarios != list(config.scenario_names):
            raise InventoryAuthorityError(
                "Inventory authority replay did not match the exact task sequence."
            )
        authority_tasks_sha256 = str((replay_manifest or {}).get("tasks_sha256") or "")
        authority_source_actor_selection_mode = str(
            (replay_manifest or {}).get("source_actor_selection_mode") or ""
        )
        authority_source_generation_enabled = bool(
            (replay_manifest or {})["source_generation_enabled"]
        )
        append_jsonl(
            output_directory / "sage_run_events.jsonl",
            {
                "event": "inventory_authority_replay_completed",
                "authority_path": str(replay_root / "inventory_authority.json"),
                "task_count": len(replayed_scenarios),
                "tasks_sha256": authority_tasks_sha256,
                "shared_context_sha256": authority_shared_context_sha256,
                "source_actor_selection_mode": (authority_source_actor_selection_mode),
                "source_generation_enabled": authority_source_generation_enabled,
                "replay_generation_enabled": False,
                "replay_actor_selection_mode": config.actor_selection_mode,
                "later_exposure_control": "donor_state_restored_before_every_task",
            },
        )
    if reflection_controller is not None:
        reflection_controller.assert_fresh_control_complete(config.scenario_names)
    final_registry_tools = sorted(store.load_entries())
    append_jsonl(
        output_directory / "sage_run_events.jsonl",
        {
            "event": "run_finished",
            "registry_dir": str(config.registry_dir),
            "registry_tools": registry_tools,
            "final_registry_tools": final_registry_tools,
            "final_registry_size": len(final_registry_tools),
        },
    )
    selection_rows = _selection_log_rows(output_directory)
    selection_summary = {
        "scenario_count": len(config.scenario_names),
        "registry_dir": str(config.registry_dir),
        "generation_enabled": generator is not None,
        "generation_model": config.generation_model,
        "actor_selection_mode": config.actor_selection_mode,
        "inventory_authority_mode": authority_mode,
        "inventory_authority_root": str(authority_root) if authority_root else None,
        "inventory_authority_task_count": (
            len(capture_tasks) if capture_root is not None else len(replayed_scenarios)
        ),
        "inventory_authority_tasks_sha256": authority_tasks_sha256,
        "inventory_authority_shared_context_sha256": (authority_shared_context_sha256),
        "inventory_authority_source_actor_selection_mode": (
            authority_source_actor_selection_mode
        ),
        "inventory_authority_source_generation_enabled": (
            authority_source_generation_enabled
        ),
        "inventory_authority_controls_later_exposure": replay_root is not None,
        "registry_tools": registry_tools,
        "final_registry_tools": final_registry_tools,
        "generated_tool_visible_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_visible")
        ),
        "generated_tool_called_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_called")
        ),
        "generated_tool_attempted_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_attempted")
        ),
        "generated_tool_failed_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_failed")
        ),
        "relevance_gate_hidden_scenarios": sum(
            1 for row in selection_rows if row.get("relevance_gating_hid_retained_tool")
        ),
    }
    (output_directory / "selection_summary.json").write_text(
        json.dumps(selection_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_directory
