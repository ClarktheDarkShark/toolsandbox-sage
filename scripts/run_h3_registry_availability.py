#!/usr/bin/env python3
"""Run the frozen-registry randomized-availability H3 pilot exactly once.

This command consumes a precomputed assignment.  It never creates or modifies
the randomization.  The frozen registry is copied into the run directory,
hashed before and after execution, and passed to ``run_sage_with_registry`` with
generation disabled.  Every randomized task is analyzed by assigned condition
regardless of whether a generated tool is selected or called (intention to
treat).
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
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, cast

import numpy as np

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
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY, apply_base_tool_policy
from scripts.manage_hypothesis_pilot import seal_phase_inputs
from scripts.research.h3_registry_ablation import (
    DEFAULT_ASSIGNMENT_SEED,
    DEFAULT_BOOTSTRAP_ITERATIONS,
    DEFAULT_RANDOMIZATION_ITERATIONS,
    EXPECTED_SCENARIO_COUNT,
    analyze_registry_availability,
    assignment_by_scenario,
    validate_registry_assignment,
)
from scripts.verify_publication_environment import verify_environment
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.scenario import Scenario

RESULT_SCHEMA_VERSION = 1
RESULT_FILENAME = "h3_registry_availability_result.json"
ANALYSIS_FILENAME = "h3_registry_availability_analysis.json"
INVENTORY_FILENAME = "native_inventory_snapshot.json"
PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS = 4
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)
PINNED_FIXED_NOW_TIMESTAMP = "1784832588"
PINNED_RAPID_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_OUTCOME_EVALUATOR = {
    "version": "sage_outcome_contracts_v9",
    "contract_sha256": (
        "d6a7598e708b24e40823278c228c895c387ef1a4d116e3b92173885967ad1955"
    ),
    "source_sha256": (
        "8ed1595b3eb050004ba2cc161836fb78906e58d3c0127b2c421df03400f14c63"
    ),
}
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAPID_FIXTURE = (
    REPO_ROOT
    / "artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
)
PILOT_RANDOMIZATION_ALPHA = 0.05
PRACTICAL_EFFECT_THRESHOLD = 0.05

_DIAGNOSTIC_FORCE_ENV = (
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)
_FORBIDDEN_LIFECYCLE_EVENT_TOKENS = (
    "birth",
    "canary",
    "lifecycle",
    "promot",
    "repair",
    "reflection",
    "retir",
    "successor",
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
            "H3 requires OPENAI_API_KEY before any run artifact is written."
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
            raise ValueError(f"H3 requires {key}={required!r}; found {configured!r}.")
        os.environ[key] = required
    fixture_value = os.environ.get("TOOLSANDBOX_RAPID_CACHE_PATH")
    fixture = (
        Path(fixture_value).expanduser().resolve()
        if fixture_value
        else DEFAULT_RAPID_FIXTURE.resolve()
    )
    if not fixture.is_file():
        raise ValueError(f"H3 read-only RapidAPI fixture is missing: {fixture}")
    fixture_sha256 = _file_sha256(fixture)
    if fixture_sha256 != PINNED_RAPID_FIXTURE_SHA256:
        raise ValueError(
            "H3 RapidAPI fixture hash mismatch: expected "
            f"{PINNED_RAPID_FIXTURE_SHA256}, observed {fixture_sha256}."
        )
    os.environ["TOOLSANDBOX_RAPID_CACHE_PATH"] = str(fixture)
    evaluator = outcome_evaluator_manifest()
    if any(
        evaluator.get(key) != value for key, value in PINNED_OUTCOME_EVALUATOR.items()
    ):
        raise ValueError("H3 requires the exact pinned v9 outcome evaluator identity.")
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    )
    if status.strip():
        raise ValueError("H3 requires a clean Git worktree.")
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


def _ordered_names_sha256(names: Iterable[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer.")
    return int(value)


def _nonnegative_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _tree_hash(path: Path) -> dict[str, Any]:
    """Return a content-addressed regular-file inventory for a registry tree."""

    if not path.is_dir():
        raise ValueError(f"Registry directory does not exist: {path}")
    rows: list[dict[str, Any]] = []
    content_files: dict[str, dict[str, Any]] = {}
    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        if item.is_symlink():
            raise ValueError(f"Registry trees may not contain symlinks: {item}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"Registry tree contains a non-regular file: {item}")
        relative = item.relative_to(path).as_posix()
        rows.append(
            {
                "path": relative,
                "size": item.stat().st_size,
                "sha256": _file_sha256(item),
            }
        )
        content_files[relative] = {
            "sha256": rows[-1]["sha256"],
            "size_bytes": rows[-1]["size"],
        }
    if not rows:
        raise ValueError(f"Registry directory contains no files: {path}")
    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "content_sha256": hashlib.sha256(
            json.dumps(
                content_files,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest(),
        "file_count": len(rows),
        "files": rows,
    }


def _registry_tool_roster(registry_dir: Path) -> dict[str, list[str]]:
    manifest_path = registry_dir / "registry_manifest.json"
    payload = _load_json_object(manifest_path, "Registry manifest")
    tools = payload.get("tools")
    if not isinstance(tools, dict):
        raise ValueError("Registry manifest has no tools object.")
    active: list[str] = []
    all_tools: list[str] = []
    for name, raw_entry in tools.items():
        if not isinstance(name, str) or not isinstance(raw_entry, dict):
            raise ValueError("Registry manifest contains a malformed tool entry.")
        all_tools.append(name)
        validation = raw_entry.get("validation")
        accepted = isinstance(validation, dict) and validation.get("accepted") is True
        if not raw_entry.get("retired", False) and accepted:
            active.append(name)
    if not active:
        raise ValueError("Frozen H3 registry contains no active accepted tools.")
    return {"all": sorted(all_tools), "active": sorted(active)}


def _load_control_rows(path: Path) -> list[dict[str, Any]]:
    """Load H2 controls from a paired comparison or ToolSandbox summary."""

    payload = _load_json(path)
    rows: Any
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("deltas"), list):
        rows = payload["deltas"]
    elif isinstance(payload, dict) and isinstance(
        payload.get("per_scenario_results"), list
    ):
        rows = payload["per_scenario_results"]
    else:
        raise ValueError(
            "H2 control input must be a row list, paired comparison, or "
            "ToolSandbox result summary."
        )
    parsed = [dict(row) for row in rows if isinstance(row, dict)]
    if len(parsed) != len(rows):
        raise ValueError("H2 control input contains a non-object row.")
    # A standalone control result calls its score ``outcome_similarity``.  The
    # analysis module accepts that key directly, so no score transformation is
    # performed here.
    return parsed


def _load_result_rows(run_dir: Path) -> list[dict[str, Any]]:
    summary_path = run_dir / "result_summary.json"
    payload = _load_json_object(summary_path, "H3 result summary")
    rows = payload.get("per_scenario_results")
    if not isinstance(rows, list):
        raise ValueError(f"H3 result summary has no per-scenario rows: {summary_path}")
    parsed = [dict(row) for row in rows if isinstance(row, dict)]
    if len(parsed) != len(rows):
        raise ValueError("H3 result summary contains a non-object row.")
    return parsed


def _load_jsonl(path: Path, *, required: bool = True) -> list[dict[str, Any]]:
    if not path.is_file():
        if required:
            raise ValueError(f"Required H3 runtime journal is missing: {path}")
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


def _rows_by_scenario(
    rows: Iterable[Mapping[str, Any]],
    *,
    expected: tuple[str, ...],
    label: str,
    name_key: str = "scenario",
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    expected_set = set(expected)
    for row in rows:
        name = row.get(name_key)
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} contains a row without {name_key!r}.")
        if name in result:
            raise ValueError(f"{label} contains duplicate scenario {name!r}.")
        if name not in expected_set:
            raise ValueError(f"{label} contains unexpected scenario {name!r}.")
        result[name] = dict(row)
    if set(result) != expected_set:
        missing = sorted(expected_set - set(result))
        raise ValueError(
            f"{label} does not cover the complete ITT roster; missing={missing[:5]!r}."
        )
    return result


def _native_inventory_snapshot(
    scenarios: Mapping[str, Scenario],
    scenario_names: tuple[str, ...],
) -> dict[str, dict[str, list[str]]]:
    snapshot: dict[str, dict[str, list[str]]] = {}
    for name in scenario_names:
        scenario = scenarios.get(name)
        if scenario is None:
            raise ValueError(f"Resolved ToolSandbox scenarios omit {name!r}.")
        baseline = apply_base_tool_policy(scenario, UPSTREAM_POLICY)
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


def _validate_runtime_manifest(
    executed_run_dir: Path,
    *,
    scenario_names: tuple[str, ...],
    agent: str,
    user: str,
) -> dict[str, Any]:
    manifest_path = executed_run_dir / "sage_ts_run_manifest.json"
    if not manifest_path.is_file():
        # ToolSandbox currently writes the immutable configuration manifest at
        # the parent output root before creating the timestamped run directory.
        # Resolve it relative to the returned run, never from an assumed CLI path.
        manifest_path = executed_run_dir.parent / "sage_ts_run_manifest.json"
    payload = _load_json_object(manifest_path, "ToolSandbox run manifest")
    expected = {
        "agent": agent,
        "user": user,
        "agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
        "base_tool_policy": UPSTREAM_POLICY,
        "run_type": "h3_registry_availability_candidate",
        "processes": 1,
        "fail_on_scenario_transform_error": True,
        "actor_selection_mode": "policy",
        "timezone": "America/New_York",
        "resume_from_dir": None,
        "resume_completed_limit": None,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(
                f"H3 runtime manifest field {key!r} is {payload.get(key)!r}; "
                f"expected {value!r}."
            )
    if payload.get("scenario_names") != list(scenario_names):
        raise ValueError(
            "H3 runtime manifest scenario order differs from the benchmark."
        )
    evaluator = payload.get("outcome_evaluator")
    if not isinstance(evaluator, dict) or any(
        evaluator.get(key) != value for key, value in PINNED_OUTCOME_EVALUATOR.items()
    ):
        raise ValueError("H3 runtime did not record the exact pinned v9 evaluator.")
    return payload


def _validate_result_roster(
    rows: Iterable[Mapping[str, Any]],
    *,
    scenario_names: tuple[str, ...],
    assignment: Mapping[str, str],
    assignment_id: str,
) -> dict[str, dict[str, Any]]:
    by_name = _rows_by_scenario(
        rows,
        expected=scenario_names,
        label="H3 result summary",
        name_key="name",
    )
    for name, row in by_name.items():
        expected_condition = (
            "masked" if assignment[name] == "registry_masked" else "available"
        )
        if row.get("experimental_registry_condition") != expected_condition:
            raise ValueError(
                f"H3 result condition disagrees with assignment for {name!r}."
            )
        if row.get("registry_assignment_id") != assignment_id:
            raise ValueError(f"H3 result assignment ID is wrong for {name!r}.")
        retries = row.get("transient_retry_count", 0)
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"H3 scenario {name!r} has an invalid retry count.")
        archives = row.get("transient_retry_archives", [])
        if not isinstance(archives, list) or any(
            not isinstance(item, str) for item in archives
        ):
            raise ValueError(f"H3 scenario {name!r} has malformed retry archives.")
        if row.get("exception_type") not in (None, "") or row.get("traceback") not in (
            None,
            "",
        ):
            raise ValueError(f"H3 scenario {name!r} ended with an exception.")
        for field, expected in PINNED_OUTCOME_EVALUATOR.items():
            row_field = (
                "outcome_evaluator_version"
                if field == "version"
                else f"outcome_evaluator_{field}"
            )
            if row.get(row_field) != expected:
                raise ValueError(f"H3 scenario {name!r} has the wrong {row_field}.")
    return by_name


def _transient_retry_report(
    rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    retried: list[dict[str, Any]] = []
    total_retries = 0
    archive_count = 0
    for name, row in sorted(rows.items()):
        count = int(row.get("transient_retry_count") or 0)
        archives = [str(item) for item in (row.get("transient_retry_archives") or [])]
        total_retries += count
        archive_count += len(archives)
        if count or archives:
            retried.append(
                {"scenario": name, "retry_count": count, "archives": archives}
            )
    return {
        "policy_attempt_limit": PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS,
        "retried_scenario_count": len(retried),
        "total_retry_count": total_retries,
        "retry_archive_count": archive_count,
        "retried_scenarios": retried,
    }


def _canonical_similarity_by_condition(
    rows: Iterable[Mapping[str, Any]], assignment: Mapping[str, str]
) -> dict[str, Any]:
    values: dict[str, list[float]] = {
        "registry_available": [],
        "registry_masked": [],
    }
    for row in rows:
        name = str(row.get("name") or "")
        condition = assignment.get(name)
        raw = row.get("similarity")
        if (
            condition not in values
            or isinstance(raw, bool)
            or not isinstance(raw, (int, float))
        ):
            raise ValueError(f"H3 canonical similarity is missing for {name!r}.")
        score = float(raw)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"H3 canonical similarity is invalid for {name!r}.")
        values[condition].append(score)
    return {
        "role": "descriptive_not_primary",
        "registry_available_mean": float(np.mean(values["registry_available"])),
        "registry_masked_mean": float(np.mean(values["registry_masked"])),
        "available_tasks": len(values["registry_available"]),
        "masked_tasks": len(values["registry_masked"]),
    }


def _dashboard_result_fields(
    analysis: Mapping[str, Any] | None,
    *,
    integrity_passed: bool,
    assignment_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project the locked pilot gate into stable dashboard-facing root fields."""

    empty: dict[str, Any] = {
        "registry_available_mean": None,
        "registry_masked_mean": None,
        "itt_difference": None,
        "itt_mean_difference": None,
        "itt_cluster_bootstrap_95_ci": [None, None],
        "cluster_ci_95": [None, None],
        "one_sided_randomization_p_value": None,
        "p_value": None,
        "p_value_note": "one-sided restricted randomization test",
        "allocation_counts": None,
        "available_tasks": None,
        "masked_tasks": None,
        "stem_clusters": None,
        "allocation": None,
        "pilot_gate_outcome": "integrity_failure",
        "pilot_gate_passed": False,
        "pilot_gate_label": "INTEGRITY_FAILURE",
        "pilot_gate_rule": {
            "integrity_required": True,
            "estimate_greater_than": 0.0,
            "one_sided_p_less_than": PILOT_RANDOMIZATION_ALPHA,
            "ci_lower_greater_than": 0.0,
        },
        "practical_effect_threshold": PRACTICAL_EFFECT_THRESHOLD,
        "practical_effect_ge_0_05": False,
        "method_note": (
            "Intention-to-treat by frozen registry-availability assignment; "
            "all eight robustness variants remain clustered by task stem."
        ),
    }
    if not integrity_passed or analysis is None:
        return empty
    outcomes = analysis.get("outcomes")
    uncertainty = analysis.get("uncertainty")
    counts = analysis.get("counts")
    if not isinstance(outcomes, Mapping) or not isinstance(uncertainty, Mapping):
        raise ValueError("H3 analysis is missing dashboard outcome fields.")
    available = outcomes.get("registry_available_mean")
    masked = outcomes.get("registry_masked_mean")
    estimate = outcomes.get("absolute_difference")
    p_value = uncertainty.get("restricted_randomization_one_sided_p_value")
    interval = uncertainty.get("stem_cluster_percentile_bootstrap_95_ci")

    def finite_value(value: Any, label: str) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"H3 analysis has an invalid dashboard {label}.")
        return float(value)

    available_value = finite_value(available, "available mean")
    masked_value = finite_value(masked, "masked mean")
    estimate_value = finite_value(estimate, "ITT estimate")
    p_value_float = finite_value(p_value, "randomization p-value")
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("H3 analysis has an invalid dashboard confidence interval.")
    interval_values = [
        finite_value(interval[0], "confidence-interval lower bound"),
        finite_value(interval[1], "confidence-interval upper bound"),
    ]
    gate_cleared = (
        estimate_value > 0.0
        and p_value_float < PILOT_RANDOMIZATION_ALPHA
        and interval_values[0] > 0.0
    )
    count_values = dict(counts) if isinstance(counts, Mapping) else {}
    allocation = (
        {
            "seed": assignment_manifest.get("seed"),
            "sha256": str(assignment_manifest.get("assignment_sha256") or ""),
            "stratification": (
                "129 task stems; 63 matched pairs plus one triplet; all eight "
                "robustness variants inherit the stem assignment"
            ),
        }
        if isinstance(assignment_manifest, Mapping)
        else None
    )
    gate_label = (
        "PILOT_THRESHOLD_CLEARED" if gate_cleared else "PILOT_THRESHOLD_NOT_CLEARED"
    )
    gate_outcome = "cleared" if gate_cleared else "not_cleared"
    empty.update(
        {
            "registry_available_mean": available_value,
            "registry_masked_mean": masked_value,
            "itt_difference": estimate_value,
            "itt_mean_difference": estimate_value,
            "itt_cluster_bootstrap_95_ci": interval_values,
            "cluster_ci_95": interval_values,
            "one_sided_randomization_p_value": p_value_float,
            "p_value": p_value_float,
            "allocation_counts": count_values,
            "available_tasks": count_values.get("registry_available_scenarios"),
            "masked_tasks": count_values.get("registry_masked_scenarios"),
            "stem_clusters": count_values.get("stems"),
            "allocation": allocation,
            "pilot_gate_outcome": gate_outcome,
            "pilot_gate_passed": gate_cleared,
            "pilot_gate_label": gate_label,
            "pilot_gate": {
                "outcome": gate_outcome,
                "passed": gate_cleared,
                "label": gate_label,
                "rule": empty["pilot_gate_rule"],
            },
            "practical_effect_ge_0_05": (estimate_value >= PRACTICAL_EFFECT_THRESHOLD),
        }
    )
    return empty


def _validate_condition_exposure(
    run_dir: Path,
    *,
    scenario_names: tuple[str, ...],
    assignment: Mapping[str, str],
    assignment_id: str,
    native_inventory: Mapping[str, Mapping[str, list[str]]],
    registry_tools: list[str],
) -> dict[str, Any]:
    visibility = _rows_by_scenario(
        _load_jsonl(run_dir / "scenario_tool_visibility.jsonl"),
        expected=scenario_names,
        label="H3 visibility journal",
    )
    selection = _rows_by_scenario(
        _load_jsonl(run_dir / "scenario_tool_selection.jsonl"),
        expected=scenario_names,
        label="H3 selection journal",
    )
    condition_counts = {"available": 0, "masked": 0}
    native_inventory_mismatches: list[str] = []
    for name in scenario_names:
        expected_condition = (
            "masked" if assignment[name] == "registry_masked" else "available"
        )
        condition_counts[expected_condition] += 1
        visible_row = visibility[name]
        selection_row = selection[name]
        for label, row in (("visibility", visible_row), ("selection", selection_row)):
            if row.get("experimental_registry_condition") != expected_condition:
                raise ValueError(
                    f"H3 {label} condition disagrees with assignment for {name!r}."
                )
            if row.get("registry_assignment_id") != assignment_id:
                raise ValueError(f"H3 {label} assignment ID is wrong for {name!r}.")
            if row.get("base_tool_policy") != UPSTREAM_POLICY:
                raise ValueError(f"H3 {label} base-tool policy changed for {name!r}.")

        generated = visible_row.get("generated_tools")
        available_tools = visible_row.get("available_tools")
        allow_list = visible_row.get("tool_allow_list")
        if not isinstance(generated, list) or not isinstance(available_tools, list):
            raise ValueError(f"H3 visibility inventory is malformed for {name!r}.")
        if not isinstance(allow_list, list):
            raise ValueError(f"H3 allow list is malformed for {name!r}.")
        generated_names = {str(tool) for tool in generated}
        retained = visible_row.get("retained_tools_loaded")
        filtered = visible_row.get("filtered_out_generated_tools")
        shortlisted = visible_row.get("shortlisted_generated_tools")
        if not isinstance(retained, list) or set(retained) != set(registry_tools):
            raise ValueError(
                f"H3 task did not load the exact frozen registry: {name!r}."
            )
        if not isinstance(filtered, list) or not isinstance(shortlisted, list):
            raise ValueError(f"H3 routing partition is malformed for {name!r}.")
        if set(filtered) & set(shortlisted) or set(filtered) | set(shortlisted) != set(
            retained
        ):
            raise ValueError(f"H3 routing partition is incomplete for {name!r}.")
        native_available = sorted(
            str(tool) for tool in available_tools if str(tool) not in generated_names
        )
        native_allow = [
            str(tool) for tool in allow_list if str(tool) not in generated_names
        ]
        expected_native = native_inventory[name]
        if native_available != list(
            expected_native["available_tools"]
        ) or native_allow != list(expected_native["tool_allow_list"]):
            native_inventory_mismatches.append(name)

        if expected_condition == "masked":
            if generated:
                raise ValueError(f"Masked H3 task exposed a generated tool: {name!r}.")
            if visible_row.get("shortlisted_generated_tools") not in ([], None):
                raise ValueError(
                    f"Masked H3 task retained a generated shortlist: {name!r}."
                )
            if set(filtered) != set(retained):
                raise ValueError(
                    f"Masked H3 task did not filter the full registry: {name!r}."
                )
            for field in (
                "generated_tools_visible",
                "generated_tools_attempted",
                "generated_tools_failed",
                "generated_tools_called",
            ):
                if selection_row.get(field) not in ([], None):
                    raise ValueError(f"Masked H3 task has nonempty {field}: {name!r}.")
            if selection_row.get("selection_status") != (
                "registry_masked_by_random_assignment"
            ):
                raise ValueError(f"Masked H3 selection status is wrong for {name!r}.")
        else:
            if set(generated) != set(shortlisted):
                raise ValueError(
                    f"Available H3 task did not expose its exact routed shortlist: "
                    f"{name!r}."
                )
            if selection_row.get("retained_tools_loaded") != retained:
                raise ValueError(
                    f"Available H3 selection record changed the loaded roster: {name!r}."
                )
            if selection_row.get("filtered_out_generated_tools") != filtered:
                raise ValueError(
                    f"Available H3 selection record changed the filter: {name!r}."
                )
            if selection_row.get("shortlisted_generated_tools") != shortlisted:
                raise ValueError(
                    f"Available H3 selection record changed the shortlist: {name!r}."
                )
            if set(selection_row.get("generated_tools_visible") or ()) != set(
                generated
            ):
                raise ValueError(
                    f"Available H3 selection visibility differs from injection: {name!r}."
                )

    if native_inventory_mismatches:
        raise ValueError(
            "H3 wrapper/native inventory changed outside the randomized registry "
            f"exposure; scenarios={native_inventory_mismatches[:5]!r}."
        )
    if condition_counts != {"available": 520, "masked": 512}:
        raise ValueError(
            f"H3 runtime condition counts are wrong: {condition_counts!r}."
        )

    for row in _load_jsonl(run_dir / "reuse_events.jsonl", required=False):
        scenario = row.get("scenario")
        if isinstance(scenario, str) and assignment.get(scenario) == "registry_masked":
            raise ValueError(
                f"Masked H3 task emitted a generated-tool reuse: {scenario!r}."
            )

    forbidden_events: list[str] = []
    run_finished_rows = 0
    for row in _load_jsonl(run_dir / "sage_run_events.jsonl"):
        event = str(row.get("event") or "")
        lowered = event.lower()
        if any(token in lowered for token in _FORBIDDEN_LIFECYCLE_EVENT_TOKENS):
            forbidden_events.append(event)
        if event == "run_finished":
            run_finished_rows += 1
            if int(row.get("lifecycle_finalization_count") or 0) != 0:
                raise ValueError("Frozen H3 run performed lifecycle finalization.")
            if row.get("registry_assignment_id") != assignment_id:
                raise ValueError(
                    "Frozen H3 run-finished event has the wrong assignment ID."
                )
    if forbidden_events:
        raise ValueError(
            f"Frozen H3 run emitted lifecycle events: {forbidden_events!r}."
        )
    if run_finished_rows != 1:
        raise ValueError("Frozen H3 run must emit exactly one run_finished event.")

    prohibited_artifacts = sorted(
        {
            path.name
            for pattern in ("self_evolution*", "post_deployment*", "*repair_state*")
            for path in run_dir.glob(pattern)
        }
    )
    if prohibited_artifacts:
        raise ValueError(
            f"Frozen H3 run emitted lifecycle artifacts: {prohibited_artifacts!r}."
        )
    return {
        "condition_counts": condition_counts,
        "visibility_row_count": len(visibility),
        "selection_row_count": len(selection),
        "native_inventory_preserved": True,
        "masked_generated_exposure_count": 0,
        "masked_generated_call_count": 0,
        "available_generated_exposure_count": sum(
            bool(visibility[name].get("generated_tools"))
            for name in scenario_names
            if assignment[name] == "registry_available"
        ),
        "forbidden_lifecycle_event_count": 0,
        "prohibited_lifecycle_artifact_count": 0,
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


def run_h3_registry_availability(
    *,
    benchmark_manifest_path: Path,
    assignment_path: Path,
    h2_control_path: Path,
    registry_source: Path,
    pilot_manifest_path: Path,
    run_root: Path,
    agent: str = DEFAULT_MODEL,
    user: str = DEFAULT_MODEL,
    randomization_iterations: int = DEFAULT_RANDOMIZATION_ITERATIONS,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    randomization_seed: int = DEFAULT_ASSIGNMENT_SEED + 1,
    bootstrap_seed: int = DEFAULT_ASSIGNMENT_SEED + 2,
) -> dict[str, Any]:
    """Execute and verify one complete mixed-arm H3 ToolSandbox run."""

    benchmark_manifest_path = benchmark_manifest_path.resolve()
    assignment_path = assignment_path.resolve()
    h2_control_path = h2_control_path.resolve()
    registry_source = registry_source.resolve()
    pilot_manifest_path = pilot_manifest_path.resolve()
    run_root = run_root.resolve()
    if run_root == registry_source or run_root.is_relative_to(registry_source):
        raise ValueError("H3 run root may not be inside the frozen registry source.")
    if run_root.exists():
        raise ValueError(
            f"H3 run root already exists; refusing to overwrite: {run_root}"
        )
    randomization_iterations = _positive_integer(
        randomization_iterations, "randomization iterations"
    )
    bootstrap_iterations = _positive_integer(
        bootstrap_iterations, "bootstrap iterations"
    )
    randomization_seed = _nonnegative_integer(randomization_seed, "randomization seed")
    bootstrap_seed = _nonnegative_integer(bootstrap_seed, "bootstrap seed")
    locked_parameters = {
        "agent": DEFAULT_MODEL,
        "user": DEFAULT_MODEL,
        "randomization_iterations": DEFAULT_RANDOMIZATION_ITERATIONS,
        "bootstrap_iterations": DEFAULT_BOOTSTRAP_ITERATIONS,
        "randomization_seed": DEFAULT_ASSIGNMENT_SEED + 1,
        "bootstrap_seed": DEFAULT_ASSIGNMENT_SEED + 2,
    }
    observed_parameters = {
        "agent": agent,
        "user": user,
        "randomization_iterations": randomization_iterations,
        "bootstrap_iterations": bootstrap_iterations,
        "randomization_seed": randomization_seed,
        "bootstrap_seed": bootstrap_seed,
    }
    if observed_parameters != locked_parameters:
        raise ValueError(
            "H3 execution/analysis parameters differ from the locked protocol: "
            f"{observed_parameters!r}."
        )
    publication_environment = _publication_environment_preflight()
    run_root.mkdir(parents=True)
    result_path = run_root / RESULT_FILENAME
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "running",
        "started_at": _utc_now(),
        "completed_at": None,
        "run_root": str(run_root),
        "git_head": _git_head(),
        "publication_environment": publication_environment,
        "inputs": {
            "benchmark_manifest_path": str(benchmark_manifest_path),
            "assignment_path": str(assignment_path),
            "h2_control_path": str(h2_control_path),
            "registry_source": str(registry_source),
            "pilot_manifest_path": str(pilot_manifest_path),
        },
        "execution": {
            "agent": agent,
            "user": user,
            "agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
            "base_tool_policy": UPSTREAM_POLICY,
            "generator_enabled": False,
            "online_evaluator_feedback_consumed": False,
            "repair_enabled": False,
            "lifecycle_mutation_enabled": False,
            "resume_enabled": False,
            "scenario_retry_attempts": PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS,
            "analysis_parameters": {
                "randomization_iterations": randomization_iterations,
                "bootstrap_iterations": bootstrap_iterations,
                "randomization_seed": randomization_seed,
                "bootstrap_seed": bootstrap_seed,
            },
        },
        "integrity": {"status": "pending", "passed": False},
    }
    _atomic_write_json(result_path, result)

    registry_copy = run_root / "frozen_registry"
    candidate_root = run_root / "candidate"
    source_registry_before: dict[str, Any] | None = None
    copied_registry_before: dict[str, Any] | None = None
    run_dir: Path | None = None
    try:
        for path, label in (
            (benchmark_manifest_path, "benchmark manifest"),
            (assignment_path, "H3 assignment"),
            (h2_control_path, "H2 control input"),
            (pilot_manifest_path, "central pilot manifest"),
        ):
            if not path.is_file():
                raise ValueError(f"Required {label} does not exist: {path}")
        active_force = [key for key in _DIAGNOSTIC_FORCE_ENV if os.environ.get(key)]
        if active_force:
            raise ValueError(
                "H3 randomized availability forbids diagnostic force-call settings: "
                f"{active_force!r}."
            )
        assignment_manifest = _load_json_object(assignment_path, "H3 assignment")
        if assignment_manifest.get("seed") != DEFAULT_ASSIGNMENT_SEED:
            raise ValueError("H3 assignment seed differs from the locked protocol.")
        control_rows = _load_control_rows(h2_control_path)
        assignment_validation = validate_registry_assignment(
            assignment_manifest,
            control_rows=control_rows,
        )
        assignment = assignment_by_scenario(assignment_manifest)
        assignment_id = str(assignment_manifest["assignment_sha256"])

        scenario_names = tuple(
            load_split_names(benchmark_manifest_path, "full_benchmark")
        )
        benchmark_sha256 = _file_sha256(benchmark_manifest_path)
        if benchmark_sha256 != PINNED_BENCHMARK_SHA256:
            raise ValueError("H3 benchmark bytes differ from the publication pin.")
        if (
            len(scenario_names) != EXPECTED_SCENARIO_COUNT
            or len(set(scenario_names)) != EXPECTED_SCENARIO_COUNT
        ):
            raise ValueError(
                "H3 benchmark must contain exactly 1,032 unique full-benchmark tasks."
            )
        if set(scenario_names) != set(assignment):
            raise ValueError("H3 assignment and benchmark scenario rosters differ.")
        if _ordered_names_sha256(scenario_names) != PINNED_SCENARIO_ORDER_SHA256:
            raise ValueError(
                "H3 benchmark scenario order differs from the publication pin."
            )
        control_names = tuple(
            str(row.get("name") or row.get("scenario") or "") for row in control_rows
        )
        if control_names != scenario_names:
            raise ValueError(
                "H3 benchmark order differs from the completed H2 control."
            )

        source_registry_before = _tree_hash(registry_source)
        pilot_manifest = _load_json_object(
            pilot_manifest_path, "Central hypothesis-pilot manifest"
        )
        h2_state = pilot_manifest.get("h2")
        if not isinstance(h2_state, dict):
            raise ValueError("H3 central manifest has no recorded H2 state.")
        h2_report_path = Path(str(h2_state.get("source_report_path") or "")).resolve()
        if not h2_report_path.is_file() or _file_sha256(h2_report_path) != h2_state.get(
            "source_report_sha256"
        ):
            raise ValueError("H3 recorded H2 report is missing or changed.")
        h2_report = _load_json_object(h2_report_path, "Recorded H2 report")
        h2_inputs = h2_report.get("inputs")
        h2_control = h2_inputs.get("control") if isinstance(h2_inputs, dict) else None
        if not isinstance(h2_control, dict):
            raise ValueError("Recorded H2 report has no locked control input.")
        if Path(
            str(h2_control.get("path") or "")
        ).resolve() != h2_control_path or h2_control.get("sha256") != _file_sha256(
            h2_control_path
        ):
            raise ValueError(
                "H3 control covariate file differs from recorded H2 control."
            )
        binding = pilot_manifest.get("frozen_h123_registry")
        if not isinstance(binding, dict):
            raise ValueError("H3 central manifest has no frozen H2 registry binding.")
        if Path(str(binding.get("path") or "")).resolve() != registry_source:
            raise ValueError("H3 registry source differs from the H2 registry binding.")
        if binding.get("content_sha256") != source_registry_before["content_sha256"]:
            raise ValueError("H3 registry bytes differ from the H2 registry binding.")
        source_registry_tools = _registry_tool_roster(registry_source)
        shutil.copytree(registry_source, registry_copy)
        copied_registry_before = _tree_hash(registry_copy)
        if copied_registry_before != source_registry_before:
            raise ValueError("Frozen registry copy does not match its source tree.")
        if _registry_tool_roster(registry_copy) != source_registry_tools:
            raise ValueError("Frozen registry copy changed the active-tool roster.")

        inputs_dir = run_root / "inputs"
        inputs_dir.mkdir()
        shutil.copy2(benchmark_manifest_path, inputs_dir / "benchmark_manifest.json")
        shutil.copy2(assignment_path, inputs_dir / "h3_assignment.json")
        shutil.copy2(h2_control_path, inputs_dir / "h2_control_rows.json")

        resolved_scenarios = resolve_scenarios(
            desired_scenario_names=list(scenario_names),
            preferred_tool_backend=DEFAULT_TOOL_BACKEND,
        )
        native_inventory = _native_inventory_snapshot(
            resolved_scenarios, scenario_names
        )
        inventory_path = run_root / INVENTORY_FILENAME
        _atomic_write_json(inventory_path, native_inventory)

        masked_scenarios = frozenset(
            name for name, arm in assignment.items() if arm == "registry_masked"
        )
        if len(masked_scenarios) != 512:
            raise ValueError("H3 assignment must mask exactly 512 scenarios.")
        config = SageRunConfig(
            agent=agent,
            user=user,
            scenario_names=scenario_names,
            output_dir=candidate_root,
            registry_dir=registry_copy,
            run_type="h3_registry_availability_candidate",
            base_tool_policy=UPSTREAM_POLICY,
            agent_runtime=SAGE_WRAPPED_AGENT_RUNTIME,
            manifest_path=benchmark_manifest_path,
            reflection_control_rows=None,
            require_fresh_reflection_control=False,
            failure_memory_path=None,
            fail_on_scenario_transform_error=True,
            online_feedback_mode=ONLINE_FEEDBACK_ACTOR_VISIBLE,
            registry_masked_scenarios=masked_scenarios,
            registry_assignment_id=assignment_id,
        )
        result["provenance"] = {
            "benchmark_manifest_sha256": _file_sha256(benchmark_manifest_path),
            "assignment_file_sha256": _file_sha256(assignment_path),
            "h2_control_file_sha256": _file_sha256(h2_control_path),
            "native_inventory_sha256": _file_sha256(inventory_path),
            "registry_source_before": source_registry_before,
            "registry_copy_before": copied_registry_before,
            "registry_tools": source_registry_tools,
        }
        _atomic_write_json(result_path, result)
        seal_phase_inputs(
            manifest_path=pilot_manifest_path,
            phase="h3_randomized_availability",
            files={
                "assignment": assignment_path,
                "benchmark": benchmark_manifest_path,
                "h2_control": h2_control_path,
            },
            declarations={
                "run_root": str(run_root),
                "registry_path": str(registry_source),
                "registry_content_sha256": source_registry_before["content_sha256"],
                "assignment_sha256": assignment_id,
                "scenario_order_sha256": _ordered_names_sha256(scenario_names),
                "model": agent,
                "preflight_complete": True,
            },
        )
        result["phase_inputs_sealed_before_model_execution"] = True
        _atomic_write_json(result_path, result)
        with _pinned_retry_environment():
            executed_run_dir = run_sage_with_registry(
                config,
                generator=None,
                scenarios=resolved_scenarios,
            )
        run_dir = executed_run_dir

        runtime_manifest = _validate_runtime_manifest(
            executed_run_dir,
            scenario_names=scenario_names,
            agent=agent,
            user=user,
        )
        candidate_rows = _load_result_rows(executed_run_dir)
        candidate_by_name = _validate_result_roster(
            candidate_rows,
            scenario_names=scenario_names,
            assignment=assignment,
            assignment_id=assignment_id,
        )
        retry_report = _transient_retry_report(candidate_by_name)
        exposure_validation = _validate_condition_exposure(
            executed_run_dir,
            scenario_names=scenario_names,
            assignment=assignment,
            assignment_id=assignment_id,
            native_inventory=native_inventory,
            registry_tools=source_registry_tools["all"],
        )
        if int(exposure_validation["available_generated_exposure_count"]) == 0:
            raise ValueError(
                "H3 available condition delivered no generated-tool exposure."
            )

        copied_registry_after = _tree_hash(registry_copy)
        source_registry_after = _tree_hash(registry_source)
        if copied_registry_after != copied_registry_before:
            raise ValueError("Frozen registry copy mutated during the H3 run.")
        if source_registry_after != source_registry_before:
            raise ValueError("Source frozen registry mutated during the H3 run.")

        analysis = analyze_registry_availability(
            candidate_rows,
            control_rows,
            assignment_manifest,
            randomization_iterations=randomization_iterations,
            bootstrap_iterations=bootstrap_iterations,
            randomization_seed=randomization_seed,
            bootstrap_seed=bootstrap_seed,
        )
        analysis_path = run_root / ANALYSIS_FILENAME
        _atomic_write_json(analysis_path, analysis)
        result.update(
            {
                "status": "complete",
                "completed_at": _utc_now(),
                "assignment_id": assignment_id,
                "assignment_design_sha256": assignment_manifest["design_sha256"],
                "scenario_count": len(scenario_names),
                "scenario_order_sha256": _ordered_names_sha256(scenario_names),
                "candidate_run_dir": str(run_dir),
                "analysis_path": str(analysis_path),
                "analysis": analysis,
                "descriptive_canonical_similarity": (
                    _canonical_similarity_by_condition(candidate_rows, assignment)
                ),
                "provenance": {
                    "benchmark_manifest_sha256": _file_sha256(benchmark_manifest_path),
                    "assignment_file_sha256": _file_sha256(assignment_path),
                    "h2_control_file_sha256": _file_sha256(h2_control_path),
                    "native_inventory_sha256": _file_sha256(inventory_path),
                    "registry_source_before": source_registry_before,
                    "registry_source_after": source_registry_after,
                    "registry_copy_before": copied_registry_before,
                    "registry_copy_after": copied_registry_after,
                    "registry_tools": source_registry_tools,
                    "runtime_manifest": runtime_manifest,
                },
                "integrity": {
                    "status": "pass",
                    "passed": True,
                    "complete_itt_roster": True,
                    "one_result_per_randomized_scenario": True,
                    "transient_retry_report": retry_report,
                    "assignment_validation": assignment_validation,
                    "assignment_id_recorded_per_scenario": True,
                    "condition_exposure_validation": exposure_validation,
                    "identical_wrapper_and_native_inventory": True,
                    "registry_source_unchanged": True,
                    "registry_copy_unchanged": True,
                    "generator_disabled": True,
                    "online_evaluator_feedback_consumed": False,
                    "reflection_repair_lifecycle_disabled": True,
                },
            }
        )
        result.update(
            _dashboard_result_fields(
                analysis,
                integrity_passed=True,
                assignment_manifest=assignment_manifest,
            )
        )
        _atomic_write_json(result_path, result)
        return result
    except Exception as exc:
        result.update(
            {
                "status": "failed_integrity",
                "completed_at": _utc_now(),
                "candidate_run_dir": str(run_dir) if run_dir is not None else None,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        existing_provenance = result.get("provenance")
        registry_provenance: dict[str, Any] = (
            dict(existing_provenance)
            if isinstance(existing_provenance, Mapping)
            else {
                "registry_source_before": source_registry_before,
                "registry_copy_before": copied_registry_before,
            }
        )
        try:
            if registry_source.is_dir():
                registry_provenance["registry_source_at_failure"] = _tree_hash(
                    registry_source
                )
            if registry_copy.is_dir():
                registry_provenance["registry_copy_at_failure"] = _tree_hash(
                    registry_copy
                )
        except Exception as hash_exc:  # Preserve the original failure.
            registry_provenance["failure_hash_error"] = {
                "type": type(hash_exc).__name__,
                "message": str(hash_exc),
            }
        result["provenance"] = registry_provenance
        result["integrity"] = {
            "status": "fail",
            "passed": False,
            "failure": str(exc),
        }
        result.update(_dashboard_result_fields(None, integrity_passed=False))
        _atomic_write_json(result_path, result)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--h2-control", type=Path, required=True)
    parser.add_argument("--registry-source", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--agent", default=DEFAULT_MODEL)
    parser.add_argument("--user", default=DEFAULT_MODEL)
    parser.add_argument(
        "--randomization-iterations",
        type=int,
        default=DEFAULT_RANDOMIZATION_ITERATIONS,
    )
    parser.add_argument(
        "--bootstrap-iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS
    )
    parser.add_argument(
        "--randomization-seed", type=int, default=DEFAULT_ASSIGNMENT_SEED + 1
    )
    parser.add_argument(
        "--bootstrap-seed", type=int, default=DEFAULT_ASSIGNMENT_SEED + 2
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run_h3_registry_availability(
            benchmark_manifest_path=args.manifest,
            assignment_path=args.assignment,
            h2_control_path=args.h2_control,
            registry_source=args.registry_source,
            pilot_manifest_path=args.pilot_manifest,
            run_root=args.run_root,
            agent=args.agent,
            user=args.user,
            randomization_iterations=args.randomization_iterations,
            bootstrap_iterations=args.bootstrap_iterations,
            randomization_seed=args.randomization_seed,
            bootstrap_seed=args.bootstrap_seed,
        )
    except Exception as exc:
        print(f"H3 registry-availability run failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "assignment_id": result["assignment_id"],
                "scenario_count": result["scenario_count"],
                "candidate_run_dir": result["candidate_run_dir"],
                "result": str(Path(result["run_root"]) / RESULT_FILENAME),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
