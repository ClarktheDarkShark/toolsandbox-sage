#!/usr/bin/env python3
"""Run the exploratory randomized-discovery / held-out frozen-registry H4 pilot.

The command seals the split and both execution orders before the first model
call.  Discovery starts from an empty registry and permits actor-visible-only
tool generation on 64 randomized task stems.  It then freezes two identical
registry copies and executes the same 65 held-out stems twice, in the same
order: registry available versus registry fully masked.

This is a one-replication pilot.  Its only terminal labels are
``PILOT_THRESHOLD_CLEARED``, ``PILOT_THRESHOLD_NOT_CLEARED``, and
``INTEGRITY_FAILURE``; it does not make a confirmatory support/rejection claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from typing import Any, Iterator, cast

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.role_factory import SAGE_WRAPPED_AGENT_RUNTIME
from sage_ts.adapters.sage_run_adapter import (
    ONLINE_FEEDBACK_ACTOR_VISIBLE,
    SageRunConfig,
    run_sage_with_registry,
)
from sage_ts.adapters.toolsandbox_adapter import DEFAULT_TOOL_BACKEND
from sage_ts.config.models import DEFAULT_MODEL
from sage_ts.config.splits import load_split_names
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from sage_ts.generation.tool_generator import ToolGenerator
from sage_ts.orchestration.online_birth import (
    POST_DEPLOYMENT_REPAIR_STATE_FILENAME,
)
from sage_ts.registry.manifest import has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY, apply_base_tool_policy
from scripts.manage_hypothesis_pilot import bind_h4_frozen_registry, seal_phase_inputs
from scripts.research.h4_split_registry import (
    DEFAULT_BOOTSTRAP_ITERATIONS,
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_SPLIT_SEED,
    DISCOVERY_SCENARIO_COUNT,
    HELD_OUT_SCENARIO_COUNT,
    HYPOTHESIS,
    INTEGRITY_FAILURE,
    analyze_paired_held_out,
    build_split_design,
    validate_split_design,
)
from scripts.verify_publication_environment import verify_environment
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.scenario import Scenario

RESULT_SCHEMA_VERSION = 1
RESULT_FILENAME = "h4_split_registry_result.json"
DESIGN_FILENAME = "h4_split_design.json"
ANALYSIS_FILENAME = "h4_split_registry_analysis.json"
NATIVE_INVENTORY_FILENAME = "held_out_native_inventory.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
PINNED_FIXED_NOW_TIMESTAMP = "1784832588"
PINNED_RAPID_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS = 4
PINNED_RECURRENCE_THRESHOLD = 2
PINNED_OUTCOME_EVALUATOR = {
    "version": "sage_outcome_contracts_v9",
    "contract_sha256": (
        "d6a7598e708b24e40823278c228c895c387ef1a4d116e3b92173885967ad1955"
    ),
    "source_sha256": (
        "8ed1595b3eb050004ba2cc161836fb78906e58d3c0127b2c421df03400f14c63"
    ),
}
DEFAULT_RAPID_FIXTURE = (
    REPO_ROOT
    / "artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
)

_DIAGNOSTIC_FORCE_ENV = (
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)
_FROZEN_FORBIDDEN_EVENT_TOKENS = (
    "birth",
    "canary",
    "lifecycle",
    "promot",
    "repair",
    "reflection",
    "retir",
    "successor",
)
_DISCOVERY_FORBIDDEN_EVENT_TOKENS = tuple(
    token for token in _FROZEN_FORBIDDEN_EVENT_TOKENS if token != "birth"
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return cast(dict[str, Any], payload)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _publication_environment_preflight() -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError(
            "H4 requires OPENAI_API_KEY before any run artifact is written."
        )
    exact_environment = verify_environment(
        REPO_ROOT / "requirements-publication-lock.txt", repo_root=REPO_ROOT
    )
    expected = {
        "TZ": "America/New_York",
        "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP": PINNED_FIXED_NOW_TIMESTAMP,
        "TOOLSANDBOX_RAPID_CACHE_MODE": "read_only",
        "SAGE_OPENAI_MAX_RETRIES": "5",
        "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
        "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
    }
    for key, required in expected.items():
        configured = os.environ.get(key)
        if configured is not None and configured != required:
            raise ValueError(f"H4 requires {key}={required!r}; found {configured!r}.")
        os.environ[key] = required
    raw_fixture = os.environ.get("TOOLSANDBOX_RAPID_CACHE_PATH")
    fixture = (
        Path(raw_fixture).expanduser().resolve()
        if raw_fixture
        else DEFAULT_RAPID_FIXTURE.resolve()
    )
    if not fixture.is_file():
        raise ValueError(f"H4 read-only RapidAPI fixture is missing: {fixture}")
    fixture_sha256 = _file_sha256(fixture)
    if fixture_sha256 != PINNED_RAPID_FIXTURE_SHA256:
        raise ValueError(
            "H4 RapidAPI fixture hash mismatch: expected "
            f"{PINNED_RAPID_FIXTURE_SHA256}, observed {fixture_sha256}."
        )
    os.environ["TOOLSANDBOX_RAPID_CACHE_PATH"] = str(fixture)
    evaluator = outcome_evaluator_manifest()
    if any(
        evaluator.get(key) != value for key, value in PINNED_OUTCOME_EVALUATOR.items()
    ):
        raise ValueError("H4 requires the exact pinned v9 outcome evaluator identity.")
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    )
    if status.strip():
        raise ValueError("H4 requires a clean Git worktree.")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=REPO_ROOT, text=True
    ).strip()
    return {
        **expected,
        "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": str(
            PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS
        ),
        "TOOLSANDBOX_RAPID_CACHE_PATH": str(fixture),
        "rapid_fixture_sha256": fixture_sha256,
        "outcome_evaluator": evaluator,
        "git_commit": commit,
        "git_tree": tree,
        "git_status": "clean",
        "exact_publication_environment": exact_environment,
    }


def _tree_hash(path: Path, *, allow_empty: bool = False) -> dict[str, Any]:
    if not path.is_dir():
        raise ValueError(f"Registry directory does not exist: {path}")
    files: list[dict[str, Any]] = []
    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        if item.is_symlink():
            raise ValueError(f"Registry trees may not contain symlinks: {item}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"Registry tree contains a non-regular file: {item}")
        files.append(
            {
                "path": item.relative_to(path).as_posix(),
                "size": item.stat().st_size,
                "sha256": _file_sha256(item),
            }
        )
    if not files and not allow_empty:
        raise ValueError(f"Registry directory contains no files: {path}")
    canonical = json.dumps(
        files, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "file_count": len(files),
        "files": files,
    }


def _load_jsonl(path: Path, *, required: bool = True) -> list[dict[str, Any]]:
    if not path.is_file():
        if required:
            raise ValueError(f"Required H4 runtime journal is missing: {path}")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSONL row at {path}:{line_number}.") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Non-object JSONL row at {path}:{line_number}.")
        rows.append(cast(dict[str, Any], payload))
    return rows


def _load_result_rows(run_dir: Path, label: str) -> list[dict[str, Any]]:
    payload = _load_json_object(run_dir / "result_summary.json", label)
    rows = payload.get("per_scenario_results")
    if not isinstance(rows, list):
        raise ValueError(f"{label} has no per-scenario result rows.")
    parsed = [dict(row) for row in rows if isinstance(row, dict)]
    if len(parsed) != len(rows):
        raise ValueError(f"{label} contains a non-object result row.")
    return parsed


def _mean_required_score(
    rows: Iterable[Mapping[str, Any]], *, field: str, label: str
) -> float:
    values: list[float] = []
    for row in rows:
        raw = row.get(field)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{label} has a missing/non-numeric {field} value.")
        value = float(raw)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{label} has an out-of-range {field} value.")
        values.append(value)
    if not values:
        raise ValueError(f"{label} has no rows for {field} aggregation.")
    return float(sum(values) / len(values))


def _rows_by_scenario(
    rows: Iterable[Mapping[str, Any]],
    *,
    expected_order: tuple[str, ...],
    label: str,
    name_key: str,
) -> dict[str, dict[str, Any]]:
    rows = tuple(rows)
    observed_order: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row.get(name_key)
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} contains a row without {name_key!r}.")
        if name in indexed:
            raise ValueError(f"{label} contains duplicate scenario {name!r}.")
        observed_order.append(name)
        indexed[name] = dict(row)
    if tuple(observed_order) != expected_order:
        raise ValueError(f"{label} does not preserve the locked execution order.")
    return indexed


def _native_inventory_snapshot(
    scenarios: Mapping[str, Scenario],
    scenario_names: tuple[str, ...],
) -> dict[str, dict[str, list[str]]]:
    snapshot: dict[str, dict[str, list[str]]] = {}
    for name in scenario_names:
        baseline = apply_base_tool_policy(scenarios[name], UPSTREAM_POLICY)
        snapshot[name] = {
            "available_tools": sorted(
                str(tool)
                for tool in baseline.starting_context.get_available_tools(
                    scrambling_allowed=True
                )
            ),
            "tool_allow_list": [
                str(tool) for tool in (baseline.starting_context.tool_allow_list or [])
            ],
        }
    return snapshot


def _runtime_manifest_validation(
    output_dir: Path,
    *,
    expected_order: tuple[str, ...],
    expected_run_type: str,
    agent: str,
    user: str,
) -> dict[str, Any]:
    payload = _load_json_object(
        output_dir / "sage_ts_run_manifest.json", "H4 runtime manifest"
    )
    expected: dict[str, Any] = {
        "agent": agent,
        "user": user,
        "agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
        "base_tool_policy": UPSTREAM_POLICY,
        "processes": 1,
        "run_type": expected_run_type,
        "scenario_names": list(expected_order),
        "resume_from_dir": None,
        "resume_completed_limit": None,
        "fail_on_scenario_transform_error": True,
        "actor_selection_mode": "policy",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(
                f"H4 runtime manifest field {key!r} is {payload.get(key)!r}; "
                f"expected {value!r}."
            )
    evaluator = payload.get("outcome_evaluator")
    if not isinstance(evaluator, dict) or any(
        evaluator.get(key) != value for key, value in PINNED_OUTCOME_EVALUATOR.items()
    ):
        raise ValueError("H4 runtime did not record the exact pinned v9 evaluator.")
    comparison_contract = {
        key: payload.get(key)
        for key in (
            "agent",
            "user",
            "agent_runtime",
            "base_tool_policy",
            "processes",
            "scenario_names",
            "resume_from_dir",
            "resume_completed_limit",
            "fail_on_scenario_transform_error",
            "actor_selection_mode",
            "outcome_evaluator",
            "online_feedback_evaluator_version",
            "timezone",
            "git_sha",
        )
    }
    canonical = json.dumps(
        comparison_contract,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "valid": True,
        "comparison_contract_sha256": hashlib.sha256(canonical).hexdigest(),
        "comparison_contract": comparison_contract,
    }


def _active_registry_roster(registry_dir: Path) -> dict[str, Any]:
    entries = RegistryStore(registry_dir).load_entries()
    active = sorted(
        name
        for name, entry in entries.items()
        if entry.validation.accepted and not entry.retired
    )
    invalid_claim_grade = sorted(
        name for name in active if not has_current_validation_proof(entries[name])
    )
    if not active:
        raise ValueError(
            "H4 discovery produced no active accepted tools; a registry-availability "
            "contrast would be undefined."
        )
    if invalid_claim_grade:
        raise ValueError(
            "H4 discovery registry contains active tools without current validation "
            f"proof: {invalid_claim_grade!r}."
        )
    return {
        "all": sorted(entries),
        "active": active,
        "active_count": len(active),
        "all_count": len(entries),
        "all_active_claim_grade": True,
    }


def _result_roster_validation(
    rows: Iterable[Mapping[str, Any]],
    *,
    expected_order: tuple[str, ...],
    condition: str,
    assignment_id: str,
    label: str,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    indexed = _rows_by_scenario(
        rows,
        expected_order=expected_order,
        label=label,
        name_key="name",
    )
    exception_count = 0
    retry_count = 0
    for name, row in indexed.items():
        if row.get("experimental_registry_condition") != condition:
            raise ValueError(f"{label} condition is wrong for {name!r}.")
        if row.get("registry_assignment_id") != assignment_id:
            raise ValueError(f"{label} assignment ID is wrong for {name!r}.")
        retries = row.get("transient_retry_count", 0)
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"{label} scenario {name!r} has an invalid retry count.")
        retry_count += retries
        archives = row.get("transient_retry_archives", [])
        if not isinstance(archives, list) or any(
            not isinstance(item, str) for item in archives
        ):
            raise ValueError(f"{label} scenario {name!r} has malformed retry archives.")
        if row.get("exception_type") not in (None, "") or row.get("traceback") not in (
            None,
            "",
        ):
            exception_count += 1
        for field, expected in PINNED_OUTCOME_EVALUATOR.items():
            row_field = (
                "outcome_evaluator_version"
                if field == "version"
                else f"outcome_evaluator_{field}"
            )
            if row.get(row_field) != expected:
                raise ValueError(
                    f"{label} scenario {name!r} has the wrong {row_field}."
                )
    return indexed, exception_count, retry_count


def _discovery_validation(
    run_dir: Path,
    *,
    expected_order: tuple[str, ...],
) -> dict[str, Any]:
    rows = _load_result_rows(run_dir, "H4 discovery result summary")
    indexed = _rows_by_scenario(
        rows,
        expected_order=expected_order,
        label="H4 discovery result summary",
        name_key="name",
    )
    exception_count = sum(
        row.get("exception_type") not in (None, "")
        or row.get("traceback") not in (None, "")
        for row in indexed.values()
    )
    retry_count = 0
    for name, row in indexed.items():
        retries = row.get("transient_retry_count", 0)
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(
                f"H4 discovery scenario {name!r} has an invalid retry count."
            )
        retry_count += retries
        archives = row.get("transient_retry_archives", [])
        if not isinstance(archives, list) or any(
            not isinstance(item, str) for item in archives
        ):
            raise ValueError(
                f"H4 discovery scenario {name!r} has malformed retry archives."
            )
    events = _load_jsonl(run_dir / "sage_run_events.jsonl")
    finished = [row for row in events if row.get("event") == "run_finished"]
    if len(finished) != 1:
        raise ValueError("H4 discovery must emit exactly one run_finished event.")
    if finished[0].get("online_feedback_mode") != ONLINE_FEEDBACK_ACTOR_VISIBLE:
        raise ValueError("H4 discovery did not use actor-visible-only feedback.")
    feedback_receipt_path = run_dir / "online_birth_feedback_receipts.jsonl"
    feedback_receipts = _rows_by_scenario(
        _load_jsonl(feedback_receipt_path),
        expected_order=expected_order,
        label="H4 discovery score-free feedback receipts",
        name_key="scenario",
    )
    for name, receipt in feedback_receipts.items():
        if (
            receipt.get("online_feedback_mode") != ONLINE_FEEDBACK_ACTOR_VISIBLE
            or receipt.get("online_birth_outcome_source")
            != "withheld_actor_visible_only"
            or receipt.get("score_fields_with_values") != []
            or receipt.get("evaluator_private_fields_present") != []
            or isinstance(receipt.get("visible_message_count"), bool)
            or not isinstance(receipt.get("visible_message_count"), int)
            or int(receipt["visible_message_count"]) < 0
        ):
            raise ValueError(
                f"H4 discovery feedback receipt leaks evaluator data for {name!r}."
            )
    forbidden_events = sorted(
        {
            str(row.get("event") or "")
            for row in events
            if any(
                token in str(row.get("event") or "").lower()
                for token in _DISCOVERY_FORBIDDEN_EVENT_TOKENS
            )
        }
    )
    if forbidden_events:
        raise ValueError(
            "H4 discovery emitted evaluator-driven repair/lifecycle events: "
            f"{forbidden_events!r}."
        )
    prohibited = sorted(
        {
            path.name
            for pattern in ("self_evolution*", "post_deployment*")
            for path in run_dir.glob(pattern)
            if path.name != POST_DEPLOYMENT_REPAIR_STATE_FILENAME
        }
    )
    if prohibited:
        raise ValueError(
            "H4 discovery emitted evaluator/reflection artifacts despite the "
            f"actor-visible-only policy: {prohibited!r}."
        )
    repair_state_path = run_dir / POST_DEPLOYMENT_REPAIR_STATE_FILENAME
    repair_state_status = "absent"
    if repair_state_path.exists():
        repair_state = _load_json_object(
            repair_state_path, "H4 disabled repair-state receipt"
        )
        expected_repair_state = {
            "schema_version": 1,
            "pending_repair_requests": [],
            "handled_repair_request_ids": [],
            "canary_state_by_tool": {},
            "repair_transactions_by_tool": {},
            "last_completed_count": 0,
        }
        if repair_state != expected_repair_state:
            raise ValueError(
                "H4 actor-visible-only discovery has nonempty repair state."
            )
        repair_state_status = "present_empty_disabled_receipt"
    return {
        "scenario_count": len(indexed),
        "runtime_exception_count": exception_count,
        "transient_retry_count": retry_count,
        "actor_visible_only_feedback": True,
        "online_evaluator_or_control_feedback_consumed": False,
        "score_free_feedback_receipt_count": len(feedback_receipts),
        "score_free_feedback_receipt_sha256": _file_sha256(feedback_receipt_path),
        "reflection_artifact_count": 0,
        "repair_state_status": repair_state_status,
        "forbidden_repair_lifecycle_event_count": 0,
    }


def _frozen_arm_validation(
    run_dir: Path,
    *,
    expected_order: tuple[str, ...],
    expected_condition: str,
    assignment_id: str,
    native_inventory: Mapping[str, Mapping[str, list[str]]],
    registry_tools: list[str],
) -> dict[str, Any]:
    label = f"H4 {expected_condition} arm"
    result_rows = _load_result_rows(run_dir, f"{label} result summary")
    _, exception_count, retry_count = _result_roster_validation(
        result_rows,
        expected_order=expected_order,
        condition=expected_condition,
        assignment_id=assignment_id,
        label=f"{label} result summary",
    )
    visibility = _rows_by_scenario(
        _load_jsonl(run_dir / "scenario_tool_visibility.jsonl"),
        expected_order=expected_order,
        label=f"{label} visibility journal",
        name_key="scenario",
    )
    selection = _rows_by_scenario(
        _load_jsonl(run_dir / "scenario_tool_selection.jsonl"),
        expected_order=expected_order,
        label=f"{label} selection journal",
        name_key="scenario",
    )

    generated_exposure_count = 0
    generated_call_count = 0
    for name in expected_order:
        visible_row = visibility[name]
        selection_row = selection[name]
        for record_label, row in (
            ("visibility", visible_row),
            ("selection", selection_row),
        ):
            if row.get("experimental_registry_condition") != expected_condition:
                raise ValueError(
                    f"{label} {record_label} condition is wrong for {name!r}."
                )
            if row.get("registry_assignment_id") != assignment_id:
                raise ValueError(
                    f"{label} {record_label} assignment ID is wrong for {name!r}."
                )
            if row.get("base_tool_policy") != UPSTREAM_POLICY:
                raise ValueError(
                    f"{label} {record_label} base-tool policy changed for {name!r}."
                )

        generated = visible_row.get("generated_tools")
        available_tools = visible_row.get("available_tools")
        allow_list = visible_row.get("tool_allow_list")
        if not isinstance(generated, list) or not isinstance(available_tools, list):
            raise ValueError(f"{label} visibility inventory is malformed for {name!r}.")
        if not isinstance(allow_list, list):
            raise ValueError(f"{label} allow list is malformed for {name!r}.")
        generated_names = {str(tool) for tool in generated}
        retained = visible_row.get("retained_tools_loaded")
        filtered = visible_row.get("filtered_out_generated_tools")
        shortlisted = visible_row.get("shortlisted_generated_tools")
        if not isinstance(retained, list) or set(retained) != set(registry_tools):
            raise ValueError(
                f"{label} did not load the exact frozen registry for {name!r}."
            )
        if not isinstance(filtered, list) or not isinstance(shortlisted, list):
            raise ValueError(f"{label} routing partition is malformed for {name!r}.")
        if set(filtered) & set(shortlisted) or set(filtered) | set(shortlisted) != set(
            retained
        ):
            raise ValueError(f"{label} routing partition is incomplete for {name!r}.")
        native_available = sorted(
            str(tool) for tool in available_tools if str(tool) not in generated_names
        )
        native_allow = [
            str(tool) for tool in allow_list if str(tool) not in generated_names
        ]
        if native_available != list(native_inventory[name]["available_tools"]):
            raise ValueError(f"{label} native available tools changed for {name!r}.")
        if native_allow != list(native_inventory[name]["tool_allow_list"]):
            raise ValueError(f"{label} native allow list changed for {name!r}.")

        called = selection_row.get("generated_tools_called")
        if not isinstance(called, list):
            raise ValueError(f"{label} call record is malformed for {name!r}.")
        generated_exposure_count += int(bool(generated))
        generated_call_count += len(called)
        if expected_condition == "masked":
            if generated:
                raise ValueError(f"Masked H4 task exposed a generated tool: {name!r}.")
            if visible_row.get("shortlisted_generated_tools") not in ([], None):
                raise ValueError(
                    f"Masked H4 task retained a generated shortlist: {name!r}."
                )
            if set(filtered) != set(retained):
                raise ValueError(
                    f"Masked H4 task did not filter the full frozen registry: {name!r}."
                )
            for field in (
                "generated_tools_visible",
                "generated_tools_attempted",
                "generated_tools_failed",
                "generated_tools_called",
            ):
                if selection_row.get(field) not in ([], None):
                    raise ValueError(f"Masked H4 task has nonempty {field}: {name!r}.")
            if selection_row.get("selection_status") != (
                "registry_masked_by_random_assignment"
            ):
                raise ValueError(f"Masked H4 selection status is wrong for {name!r}.")
        else:
            if set(generated) != set(shortlisted):
                raise ValueError(
                    f"Available H4 task did not expose its exact routed shortlist: "
                    f"{name!r}."
                )
            if selection_row.get("retained_tools_loaded") != retained:
                raise ValueError(
                    f"Available H4 selection record changed the loaded roster: {name!r}."
                )
            if selection_row.get("filtered_out_generated_tools") != filtered:
                raise ValueError(
                    f"Available H4 selection record changed the filter: {name!r}."
                )
            if selection_row.get("shortlisted_generated_tools") != shortlisted:
                raise ValueError(
                    f"Available H4 selection record changed the shortlist: {name!r}."
                )
            if set(selection_row.get("generated_tools_visible") or ()) != set(
                generated
            ):
                raise ValueError(
                    f"Available H4 selection visibility differs from injection: {name!r}."
                )

    reuse_events = _load_jsonl(run_dir / "reuse_events.jsonl", required=False)
    if expected_condition == "masked" and reuse_events:
        raise ValueError("Masked H4 arm emitted generated-tool reuse events.")

    forbidden_events: list[str] = []
    run_finished = 0
    for row in _load_jsonl(run_dir / "sage_run_events.jsonl"):
        event = str(row.get("event") or "")
        if any(token in event.lower() for token in _FROZEN_FORBIDDEN_EVENT_TOKENS):
            forbidden_events.append(event)
        if event == "run_finished":
            run_finished += 1
            if int(row.get("lifecycle_finalization_count") or 0) != 0:
                raise ValueError(f"{label} performed lifecycle finalization.")
            if row.get("registry_assignment_id") != assignment_id:
                raise ValueError(f"{label} run_finished assignment ID is wrong.")
    if forbidden_events:
        raise ValueError(
            f"{label} emitted frozen-forbidden events: {forbidden_events!r}."
        )
    if run_finished != 1:
        raise ValueError(f"{label} must emit exactly one run_finished event.")
    prohibited_artifacts = sorted(
        {
            path.name
            for pattern in ("self_evolution*", "post_deployment*", "*repair_state*")
            for path in run_dir.glob(pattern)
        }
    )
    if prohibited_artifacts:
        raise ValueError(
            f"{label} emitted frozen-forbidden artifacts: {prohibited_artifacts!r}."
        )
    return {
        "scenario_count": len(result_rows),
        "runtime_exception_count": exception_count,
        "transient_retry_count": retry_count,
        "generated_exposure_scenario_count": generated_exposure_count,
        "generated_call_count": generated_call_count,
        "native_inventory_preserved": True,
        "generation_enabled": False,
        "reflection_repair_lifecycle_enabled": False,
        "forbidden_lifecycle_event_count": 0,
    }


@contextmanager
def _pinned_retry_environment() -> Iterator[None]:
    key = "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS"
    prior = os.environ.get(key)
    os.environ[key] = str(PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS)
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prior


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _run_discovery(
    *,
    config: SageRunConfig,
    scenarios: dict[str, Scenario],
    generator: ToolGenerator,
) -> Path:
    with _pinned_retry_environment():
        return cast(
            Path,
            run_sage_with_registry(config, generator=generator, scenarios=scenarios),
        )


def _run_frozen_arm(
    *,
    scenario_names: tuple[str, ...],
    scenarios: dict[str, Scenario],
    output_dir: Path,
    registry_dir: Path,
    benchmark_manifest_path: Path,
    assignment_id: str,
    masked: bool,
    agent: str,
    user: str,
) -> Path:
    config = SageRunConfig(
        agent=agent,
        user=user,
        scenario_names=scenario_names,
        output_dir=output_dir,
        registry_dir=registry_dir,
        run_type=(
            "h4_held_out_registry_masked"
            if masked
            else "h4_held_out_registry_available"
        ),
        base_tool_policy=UPSTREAM_POLICY,
        agent_runtime=SAGE_WRAPPED_AGENT_RUNTIME,
        manifest_path=benchmark_manifest_path,
        reflection_control_rows=None,
        require_fresh_reflection_control=False,
        failure_memory_path=None,
        fail_on_scenario_transform_error=True,
        online_feedback_mode=ONLINE_FEEDBACK_ACTOR_VISIBLE,
        registry_masked_scenarios=(
            frozenset(scenario_names) if masked else frozenset()
        ),
        registry_assignment_id=assignment_id,
    )
    with _pinned_retry_environment():
        return cast(
            Path,
            run_sage_with_registry(config, generator=None, scenarios=scenarios),
        )


def _frozen_arm_worker(params: dict[str, Any], result_queue: Any) -> None:
    condition = str(params["condition"])
    started = time.monotonic_ns()
    try:
        scenario_names = tuple(str(name) for name in params["scenario_names"])
        scenarios = resolve_scenarios(
            desired_scenario_names=list(scenario_names),
            preferred_tool_backend=DEFAULT_TOOL_BACKEND,
        )
        run_dir = _run_frozen_arm(
            scenario_names=scenario_names,
            scenarios=scenarios,
            output_dir=Path(params["output_dir"]),
            registry_dir=Path(params["registry_dir"]),
            benchmark_manifest_path=Path(params["benchmark_manifest_path"]),
            assignment_id=str(params["assignment_id"]),
            masked=bool(params["masked"]),
            agent=str(params["agent"]),
            user=str(params["user"]),
        )
    except BaseException as exc:
        result_queue.put(
            {
                "condition": condition,
                "status": "failed",
                "process_pid": os.getpid(),
                "started_monotonic_ns": started,
                "completed_monotonic_ns": time.monotonic_ns(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        raise
    result_queue.put(
        {
            "condition": condition,
            "status": "complete",
            "process_pid": os.getpid(),
            "started_monotonic_ns": started,
            "completed_monotonic_ns": time.monotonic_ns(),
            "run_dir": str(run_dir),
        }
    )


def _stop_process(process: Any) -> None:
    if not process.is_alive():
        return
    process.terminate()
    process.join(timeout=10)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=10)


def _run_paired_frozen_arms(
    *,
    scenario_names: tuple[str, ...],
    run_root: Path,
    available_registry: Path,
    masked_registry: Path,
    benchmark_manifest_path: Path,
    assignment_id: str,
    agent: str,
    user: str,
) -> tuple[Path, Path, dict[str, Any]]:
    """Execute the held-out treatment and control concurrently."""

    ctx = get_context("spawn")
    result_queue = ctx.Queue()
    common: dict[str, Any] = {
        "scenario_names": list(scenario_names),
        "benchmark_manifest_path": str(benchmark_manifest_path),
        "assignment_id": assignment_id,
        "agent": agent,
        "user": user,
    }
    parameters = {
        "available": {
            **common,
            "condition": "available",
            "masked": False,
            "output_dir": str(run_root / "held_out_available"),
            "registry_dir": str(available_registry),
        },
        "masked": {
            **common,
            "condition": "masked",
            "masked": True,
            "output_dir": str(run_root / "held_out_masked"),
            "registry_dir": str(masked_registry),
        },
    }
    processes = {
        condition: ctx.Process(
            target=_frozen_arm_worker,
            args=(params, result_queue),
            name=f"sage_h4_{condition}_arm",
        )
        for condition, params in parameters.items()
    }
    started: list[str] = []
    try:
        for condition in ("available", "masked"):
            processes[condition].start()
            started.append(condition)
        while any(process.is_alive() for process in processes.values()):
            failed = next(
                (
                    condition
                    for condition, process in processes.items()
                    if process.exitcode not in (None, 0)
                ),
                None,
            )
            if failed is not None:
                for condition, process in processes.items():
                    if condition != failed:
                        _stop_process(process)
                raise RuntimeError(
                    f"H4 {failed} arm exited with code {processes[failed].exitcode}."
                )
            time.sleep(0.5)
        for process in processes.values():
            process.join()
        if any(process.exitcode != 0 for process in processes.values()):
            raise RuntimeError("One or more H4 held-out arm processes failed.")
        records: dict[str, dict[str, Any]] = {}
        for _ in processes:
            try:
                record = result_queue.get(timeout=30)
            except Empty as exc:
                raise RuntimeError("H4 held-out worker returned no receipt.") from exc
            if not isinstance(record, dict):
                raise RuntimeError("H4 held-out worker receipt is malformed.")
            records[str(record.get("condition"))] = record
        if set(records) != set(processes) or any(
            record.get("status") != "complete" for record in records.values()
        ):
            raise RuntimeError(f"H4 held-out worker failure: {records!r}.")
        overlap_ns = min(
            int(record["completed_monotonic_ns"]) for record in records.values()
        ) - max(int(record["started_monotonic_ns"]) for record in records.values())
        if overlap_ns <= 0:
            raise RuntimeError("H4 held-out process intervals do not overlap.")
        if len({int(record["process_pid"]) for record in records.values()}) != 2:
            raise RuntimeError("H4 held-out arms did not run in distinct processes.")
        evidence = {
            "mode": "concurrent_spawned_processes",
            "arms": records,
            "overlap_monotonic_ns": overlap_ns,
            "overlap_seconds": overlap_ns / 1_000_000_000,
        }
        return (
            Path(str(records["available"]["run_dir"])),
            Path(str(records["masked"]["run_dir"])),
            evidence,
        )
    finally:
        for condition in started:
            _stop_process(processes[condition])
        result_queue.close()
        result_queue.join_thread()


def run_h4_split_registry(
    *,
    benchmark_manifest_path: Path,
    pilot_manifest_path: Path,
    run_root: Path,
    agent: str = DEFAULT_MODEL,
    user: str = DEFAULT_MODEL,
    generation_model: str = DEFAULT_MODEL,
    recurrence_threshold: int = 2,
    split_seed: int = DEFAULT_SPLIT_SEED,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Execute, verify, and analyze one complete exploratory H4 pilot."""

    benchmark_manifest_path = benchmark_manifest_path.resolve()
    pilot_manifest_path = pilot_manifest_path.resolve()
    run_root = run_root.resolve()
    if run_root.exists():
        raise ValueError(
            f"H4 run root already exists; refusing to overwrite: {run_root}"
        )
    if not pilot_manifest_path.is_file():
        raise ValueError(f"H4 central pilot manifest is missing: {pilot_manifest_path}")
    locked_parameters = {
        "agent": DEFAULT_MODEL,
        "user": DEFAULT_MODEL,
        "generation_model": DEFAULT_MODEL,
        "recurrence_threshold": PINNED_RECURRENCE_THRESHOLD,
        "split_seed": DEFAULT_SPLIT_SEED,
        "bootstrap_iterations": DEFAULT_BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": DEFAULT_BOOTSTRAP_SEED,
    }
    observed_parameters = {
        "agent": agent,
        "user": user,
        "generation_model": generation_model,
        "recurrence_threshold": recurrence_threshold,
        "split_seed": split_seed,
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_seed": bootstrap_seed,
    }
    if observed_parameters != locked_parameters:
        raise ValueError(
            "H4 execution/analysis parameters differ from the locked protocol: "
            f"{observed_parameters!r}."
        )
    publication_environment = _publication_environment_preflight()
    run_root.mkdir(parents=True)
    result_path = run_root / RESULT_FILENAME
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "hypothesis": HYPOTHESIS,
        "pilot_not_confirmatory": True,
        "status": "running",
        "status_label": None,
        "execution_stage": "preflight",
        "started_at": _utc_now(),
        "completed_at": None,
        "run_root": str(run_root),
        "git_head": _git_head(),
        "inputs": {
            "benchmark_manifest_path": str(benchmark_manifest_path),
            "pilot_manifest_path": str(pilot_manifest_path),
        },
        "integrity": {"passed": False},
    }
    _atomic_write_json(result_path, result)

    design: dict[str, Any] | None = None
    discovery_run_dir: Path | None = None
    available_run_dir: Path | None = None
    masked_run_dir: Path | None = None
    discovery_registry = run_root / "discovery_registry"
    available_registry = run_root / "held_out_available_registry"
    masked_registry = run_root / "held_out_masked_registry"
    try:
        if not benchmark_manifest_path.is_file():
            raise ValueError(
                f"H4 benchmark manifest does not exist: {benchmark_manifest_path}"
            )
        benchmark_sha256 = _file_sha256(benchmark_manifest_path)
        if benchmark_sha256 != PINNED_BENCHMARK_SHA256:
            raise ValueError(
                "H4 benchmark hash mismatch: expected "
                f"{PINNED_BENCHMARK_SHA256}, observed {benchmark_sha256}."
            )
        active_force = [key for key in _DIAGNOSTIC_FORCE_ENV if os.environ.get(key)]
        if active_force:
            raise ValueError(
                f"H4 forbids diagnostic force-call settings: {active_force!r}."
            )
        scenario_names = tuple(
            load_split_names(benchmark_manifest_path, "full_benchmark")
        )
        design = build_split_design(scenario_names, seed=split_seed)
        design_validation = validate_split_design(design, scenario_names=scenario_names)
        design_path = run_root / DESIGN_FILENAME
        # The design file is durable before any actor/generator model call. The
        # central write-once seal is added after all deterministic preflights.
        _atomic_write_json(design_path, design)
        archived_manifest = run_root / "benchmark_manifest.json"
        shutil.copy2(benchmark_manifest_path, archived_manifest)
        discovery_registry.mkdir()
        empty_registry_hash = _tree_hash(discovery_registry, allow_empty=True)
        result.update(
            {
                "design_path": str(design_path),
                "design_sha256": design["design_sha256"],
                "design_file_sha256": _file_sha256(design_path),
                "design_sealed_before_model_execution": True,
                "design_validation": design_validation,
                "orders": design["hashes"],
                "publication_environment": publication_environment,
            }
        )
        _atomic_write_json(result_path, result)

        discovery_order = tuple(
            str(name) for name in design["discovery_execution_order"]
        )
        held_out_order = tuple(str(name) for name in design["held_out_execution_order"])
        discovery_scenarios = resolve_scenarios(
            desired_scenario_names=list(discovery_order),
            preferred_tool_backend=DEFAULT_TOOL_BACKEND,
        )
        held_out_scenarios = resolve_scenarios(
            desired_scenario_names=list(held_out_order),
            preferred_tool_backend=DEFAULT_TOOL_BACKEND,
        )
        native_inventory = _native_inventory_snapshot(
            held_out_scenarios, held_out_order
        )
        native_inventory_path = run_root / NATIVE_INVENTORY_FILENAME
        _atomic_write_json(native_inventory_path, native_inventory)
        discovery_config = SageRunConfig(
            agent=agent,
            user=user,
            scenario_names=discovery_order,
            output_dir=run_root / "discovery",
            registry_dir=discovery_registry,
            run_type="h4_randomized_discovery",
            recurrence_threshold=recurrence_threshold,
            base_tool_policy=UPSTREAM_POLICY,
            agent_runtime=SAGE_WRAPPED_AGENT_RUNTIME,
            manifest_path=benchmark_manifest_path,
            reflection_control_rows=None,
            require_fresh_reflection_control=False,
            failure_memory_path=None,
            fail_on_scenario_transform_error=True,
            online_feedback_mode=ONLINE_FEEDBACK_ACTOR_VISIBLE,
        )
        discovery_generator = ToolGenerator(
            completer=OpenAIChatAdapter(model=generation_model)
        )
        result["provenance"] = {
            "benchmark_manifest_sha256": _file_sha256(benchmark_manifest_path),
            "archived_benchmark_manifest_sha256": _file_sha256(archived_manifest),
            "design_file_sha256": _file_sha256(design_path),
            "native_inventory_sha256": _file_sha256(native_inventory_path),
            "empty_registry": empty_registry_hash,
        }
        _atomic_write_json(result_path, result)
        seal_phase_inputs(
            manifest_path=pilot_manifest_path,
            phase="h4_split",
            files={
                "design": design_path,
                "benchmark": benchmark_manifest_path,
                "held_out_native_inventory": native_inventory_path,
            },
            declarations={
                "run_root": str(run_root),
                "design_sha256": design["design_sha256"],
                "empty_registry_sha256": empty_registry_hash["sha256"],
                "model": agent,
                "generation_model": generation_model,
                "preflight_complete": True,
            },
        )
        result["phase_inputs_sealed_before_model_execution"] = True
        result["execution_stage"] = "discovery"
        _atomic_write_json(result_path, result)

        discovery_run_dir = _run_discovery(
            config=discovery_config,
            scenarios=discovery_scenarios,
            generator=discovery_generator,
        )
        discovery_validation = _discovery_validation(
            discovery_run_dir, expected_order=discovery_order
        )
        discovery_runtime = _runtime_manifest_validation(
            run_root / "discovery",
            expected_order=discovery_order,
            expected_run_type="h4_randomized_discovery",
            agent=agent,
            user=user,
        )
        frozen_registry_hash = _tree_hash(discovery_registry)
        registry_roster = _active_registry_roster(discovery_registry)
        bound_manifest = bind_h4_frozen_registry(
            manifest_path=pilot_manifest_path,
            registry_dir=discovery_registry,
            design_sha256=str(design["design_sha256"]),
            discovery_run_dir=discovery_run_dir,
        )
        frozen_binding = dict(bound_manifest["h4_frozen_registry"])
        result["h4_frozen_registry_binding"] = frozen_binding
        result["execution_stage"] = "held_out"
        result["provenance"]["frozen_registry_content_sha256"] = frozen_binding[
            "content_sha256"
        ]
        _atomic_write_json(result_path, result)

        shutil.copytree(discovery_registry, available_registry)
        shutil.copytree(discovery_registry, masked_registry)
        available_registry_before = _tree_hash(available_registry)
        masked_registry_before = _tree_hash(masked_registry)
        if not (
            frozen_registry_hash == available_registry_before == masked_registry_before
        ):
            raise ValueError("H4 frozen registry copies are not byte-identical.")

        assignment_id = str(design["design_sha256"])

        available_run_dir, masked_run_dir, parallel_arm_execution = (
            _run_paired_frozen_arms(
                scenario_names=held_out_order,
                run_root=run_root,
                available_registry=available_registry,
                masked_registry=masked_registry,
                benchmark_manifest_path=benchmark_manifest_path,
                assignment_id=assignment_id,
                agent=agent,
                user=user,
            )
        )

        available_validation = _frozen_arm_validation(
            available_run_dir,
            expected_order=held_out_order,
            expected_condition="available",
            assignment_id=assignment_id,
            native_inventory=native_inventory,
            registry_tools=registry_roster["all"],
        )
        masked_validation = _frozen_arm_validation(
            masked_run_dir,
            expected_order=held_out_order,
            expected_condition="masked",
            assignment_id=assignment_id,
            native_inventory=native_inventory,
            registry_tools=registry_roster["all"],
        )
        available_runtime = _runtime_manifest_validation(
            run_root / "held_out_available",
            expected_order=held_out_order,
            expected_run_type="h4_held_out_registry_available",
            agent=agent,
            user=user,
        )
        masked_runtime = _runtime_manifest_validation(
            run_root / "held_out_masked",
            expected_order=held_out_order,
            expected_run_type="h4_held_out_registry_masked",
            agent=agent,
            user=user,
        )
        identical_runtime_contract = (
            available_runtime["comparison_contract_sha256"]
            == masked_runtime["comparison_contract_sha256"]
        )
        if not identical_runtime_contract:
            raise ValueError(
                "H4 held-out arms differ in model, wrapper, evaluator, or runtime."
            )

        discovery_registry_after = _tree_hash(discovery_registry)
        available_registry_after = _tree_hash(available_registry)
        masked_registry_after = _tree_hash(masked_registry)
        immutable_equal = (
            frozen_registry_hash
            == discovery_registry_after
            == available_registry_before
            == available_registry_after
            == masked_registry_before
            == masked_registry_after
        )
        if not immutable_equal:
            raise ValueError("H4 frozen registry source or a paired copy mutated.")

        runtime_exception_count = (
            int(discovery_validation["runtime_exception_count"])
            + int(available_validation["runtime_exception_count"])
            + int(masked_validation["runtime_exception_count"])
        )
        integrity_checks = {
            "complete_rosters": (
                int(discovery_validation["scenario_count"]) == DISCOVERY_SCENARIO_COUNT
                and int(available_validation["scenario_count"])
                == HELD_OUT_SCENARIO_COUNT
                and int(masked_validation["scenario_count"]) == HELD_OUT_SCENARIO_COUNT
            ),
            "source_disjoint_stems": bool(design_validation["source_disjoint_stems"]),
            "design_hash_verified": True,
            "execution_order_hashes_verified": bool(
                design_validation["execution_order_hashes_verified"]
            ),
            "immutable_equal_registry_copies": immutable_equal,
            "identical_runtime_and_native_inventory": bool(
                identical_runtime_contract
                and available_validation["native_inventory_preserved"]
                and masked_validation["native_inventory_preserved"]
            ),
            "masked_zero_generated_exposure": (
                int(masked_validation["generated_exposure_scenario_count"]) == 0
            ),
            "masked_zero_generated_calls": (
                int(masked_validation["generated_call_count"]) == 0
            ),
            "available_generated_exposure_positive": (
                int(available_validation["generated_exposure_scenario_count"]) > 0
            ),
            "held_out_arms_concurrent": bool(
                int(parallel_arm_execution["overlap_monotonic_ns"]) > 0
            ),
            "zero_runtime_exceptions": runtime_exception_count == 0,
            "frozen_phase_generation_repair_reflection_lifecycle_disabled": bool(
                not available_validation["generation_enabled"]
                and not masked_validation["generation_enabled"]
                and not available_validation["reflection_repair_lifecycle_enabled"]
                and not masked_validation["reflection_repair_lifecycle_enabled"]
            ),
        }
        available_rows = _load_result_rows(
            available_run_dir, "H4 registry-available result summary"
        )
        masked_rows = _load_result_rows(
            masked_run_dir, "H4 registry-masked result summary"
        )
        analysis = analyze_paired_held_out(
            available_rows,
            masked_rows,
            design,
            integrity_checks=integrity_checks,
            bootstrap_iterations=bootstrap_iterations,
            bootstrap_seed=bootstrap_seed,
        )
        analysis_path = run_root / ANALYSIS_FILENAME
        _atomic_write_json(analysis_path, analysis)
        final_integrity_passed = bool(analysis["integrity"]["passed"])

        result.update(
            {
                "status": (
                    "complete" if final_integrity_passed else "failed_integrity"
                ),
                "status_label": analysis["status_label"],
                "execution_stage": "complete",
                "completed_at": _utc_now(),
                "analysis_path": str(analysis_path),
                "analysis": analysis,
                "descriptive_canonical_similarity": {
                    "role": "descriptive_not_primary",
                    "registry_available_mean": _mean_required_score(
                        available_rows,
                        field="similarity",
                        label="H4 registry-available rows",
                    ),
                    "registry_masked_mean": _mean_required_score(
                        masked_rows,
                        field="similarity",
                        label="H4 registry-masked rows",
                    ),
                },
                "execution": {
                    "agent": agent,
                    "user": user,
                    "generation_model": generation_model,
                    "agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
                    "base_tool_policy": UPSTREAM_POLICY,
                    "discovery_feedback_mode": ONLINE_FEEDBACK_ACTOR_VISIBLE,
                    "discovery_generation_enabled": True,
                    "held_out_generation_enabled": False,
                    "held_out_reflection_repair_lifecycle_enabled": False,
                    "held_out_arms_concurrent": True,
                    "parallel_arm_execution": parallel_arm_execution,
                    "scenario_retry_attempts": (
                        PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS
                    ),
                    "transient_retry_count": (
                        int(discovery_validation["transient_retry_count"])
                        + int(available_validation["transient_retry_count"])
                        + int(masked_validation["transient_retry_count"])
                    ),
                    "discovery_run_dir": str(discovery_run_dir),
                    "available_run_dir": str(available_run_dir),
                    "masked_run_dir": str(masked_run_dir),
                },
                "registry": {
                    "started_empty": empty_registry_hash["file_count"] == 0,
                    "roster": registry_roster,
                    "discovery_source": str(discovery_registry),
                    "available_copy": str(available_registry),
                    "masked_copy": str(masked_registry),
                },
                "provenance": {
                    "benchmark_manifest_sha256": _file_sha256(benchmark_manifest_path),
                    "archived_benchmark_manifest_sha256": _file_sha256(
                        archived_manifest
                    ),
                    "design_file_sha256": _file_sha256(design_path),
                    "native_inventory_sha256": _file_sha256(native_inventory_path),
                    "empty_registry": empty_registry_hash,
                    "frozen_registry": frozen_registry_hash,
                    "frozen_registry_content_sha256": frozen_binding["content_sha256"],
                    "discovery_registry_after": discovery_registry_after,
                    "available_registry_before": available_registry_before,
                    "available_registry_after": available_registry_after,
                    "masked_registry_before": masked_registry_before,
                    "masked_registry_after": masked_registry_after,
                },
                "integrity": {
                    **integrity_checks,
                    "passed": final_integrity_passed,
                    "runtime_exception_count": runtime_exception_count,
                    "discovery_validation": discovery_validation,
                    "discovery_runtime": discovery_runtime,
                    "available_validation": available_validation,
                    "masked_validation": masked_validation,
                    "available_runtime": available_runtime,
                    "masked_runtime": masked_runtime,
                },
            }
        )
        _atomic_write_json(result_path, result)
        return result
    except Exception as exc:
        result.update(
            {
                "status": "failed_integrity",
                "status_label": INTEGRITY_FAILURE,
                "completed_at": _utc_now(),
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "runs": {
                    "discovery_run_dir": (
                        str(discovery_run_dir) if discovery_run_dir else None
                    ),
                    "available_run_dir": (
                        str(available_run_dir) if available_run_dir else None
                    ),
                    "masked_run_dir": str(masked_run_dir) if masked_run_dir else None,
                },
                "integrity": {"passed": False, "failure": str(exc)},
            }
        )
        if design is not None:
            result["design_sha256"] = design.get("design_sha256")
        _atomic_write_json(result_path, result)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--agent", default=DEFAULT_MODEL)
    parser.add_argument("--user", default=DEFAULT_MODEL)
    parser.add_argument("--generation-model", default=DEFAULT_MODEL)
    parser.add_argument("--recurrence-threshold", type=int, default=2)
    parser.add_argument("--split-seed", type=int, default=DEFAULT_SPLIT_SEED)
    parser.add_argument(
        "--bootstrap-iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS
    )
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run_h4_split_registry(
            benchmark_manifest_path=args.manifest,
            pilot_manifest_path=args.pilot_manifest,
            run_root=args.run_root,
            agent=args.agent,
            user=args.user,
            generation_model=args.generation_model,
            recurrence_threshold=args.recurrence_threshold,
            split_seed=args.split_seed,
            bootstrap_iterations=args.bootstrap_iterations,
            bootstrap_seed=args.bootstrap_seed,
        )
    except Exception as exc:
        print(f"H4 split-registry pilot failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "status_label": result["status_label"],
                "design_sha256": result["design_sha256"],
                "result": str(Path(result["run_root"]) / RESULT_FILENAME),
            },
            indent=2,
        )
    )
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
