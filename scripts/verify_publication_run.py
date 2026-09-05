#!/usr/bin/env python3
"""Fail closed unless a completed publication run is entirely fresh and paired."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from sage_ts.evaluation.retry_provenance import (
    validate_successful_retry_provenance,
)
from sage_ts.registry.content_identity import (
    registry_content_identity,
    validate_registry_content_identity,
)

PINNED_RAPID_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)
PINNED_PILOT_BENCHMARK_SHA256 = (
    "378b681dbe86e0f27c911c485c6257075c9fe377f7c993f8083cba35a2fdda90"
)
PINNED_PILOT_SCENARIO_ORDER_SHA256 = (
    "ce19bea3a0ff404487c195dd68a9f07f3e8705a9ed59364a534b13385da09d5e"
)
PUBLICATION_COHORT_PINS: dict[str, tuple[int, str, str]] = {
    "full": (1032, PINNED_BENCHMARK_SHA256, PINNED_SCENARIO_ORDER_SHA256),
    "pilot": (
        30,
        PINNED_PILOT_BENCHMARK_SHA256,
        PINNED_PILOT_SCENARIO_ORDER_SHA256,
    ),
}
PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256 = (
    "5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f"
)
PUBLICATION_ENVIRONMENT_LOCK = "requirements-publication-lock.txt"
PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP = 1784832588
PUBLICATION_MODEL = "gpt-4o-mini"
PUBLICATION_EXECUTION_ENV = {
    "TZ": "America/New_York",
    "SAGE_OPENAI_MAX_RETRIES": "5",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}
PUBLICATION_TIMEZONE = PUBLICATION_EXECUTION_ENV["TZ"]
LLM_USAGE_INTEGER_FIELDS = (
    "llm_call_count",
    "llm_live_call_count",
    "llm_cached_call_count",
    "llm_prompt_tokens",
    "llm_provider_cached_prompt_tokens",
    "llm_provider_cached_prompt_call_count",
    "llm_provider_cached_prompt_tokens_available_count",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_usage_available_count",
)
LLM_USAGE_SOURCE_INTEGER_FIELDS = tuple(
    field for field in LLM_USAGE_INTEGER_FIELDS if field != "llm_usage_available_count"
)
OUTCOME_EVALUATOR_ROW_FIELDS = {
    "outcome_evaluator_version": "version",
    "outcome_evaluator_contract_sha256": "contract_sha256",
    "outcome_evaluator_source_sha256": "source_sha256",
}
_PUBLICATION_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")
REPO_ROOT = Path(__file__).resolve().parents[1]


def publication_cohort_pins(cohort: str) -> tuple[int, str, str]:
    """Return immutable task-count, benchmark, and order pins for one cohort."""

    try:
        return PUBLICATION_COHORT_PINS[cohort]
    except KeyError as exc:
        choices = ", ".join(sorted(PUBLICATION_COHORT_PINS))
        raise ValueError(
            f"Unknown publication cohort {cohort!r}; expected one of: {choices}."
        ) from exc


def _external_distribution_lock_identity(lock_path: Path) -> tuple[int, str]:
    """Independently derive the lock's canonical external package identity."""

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
        raise ValueError(f"Cannot inspect current publication source: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(
            "Cannot inspect current publication source: "
            f"git {' '.join(arguments)} failed ({detail or completed.returncode})."
        )
    return completed.stdout.strip()


def _clean_source_identity(repo_root: Path) -> dict[str, Any]:
    """Return current Git identity only for the exact, clean repository root."""

    repo_root = repo_root.resolve()
    git_root = Path(_git_output(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if git_root != repo_root:
        raise ValueError(
            f"Current publication source root is {git_root}; expected {repo_root}."
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
            "Current publication source worktree is not clean"
            + (f": {first_entries}" if first_entries else ".")
        )
    commit = _git_output(repo_root, "rev-parse", "--verify", "HEAD")
    tree = _git_output(repo_root, "rev-parse", "--verify", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not re.fullmatch(
        r"[0-9a-f]{40,64}", tree
    ):
        raise ValueError("Current publication Git commit or tree is malformed.")
    return {"git_commit": commit, "git_tree": tree, "git_clean": True}


def _active_publication_environment(
    lock_path: Path,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        environment_verifier = importlib.import_module(
            "scripts.verify_publication_environment"
        )
    except ModuleNotFoundError:
        environment_verifier = importlib.import_module("verify_publication_environment")

    try:
        report = environment_verifier.verify_environment(
            lock_path,
            repo_root=repo_root,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Active publication environment is invalid: {exc}") from exc
    if not isinstance(report, dict) or report.get("status") != "pass":
        raise ValueError("Active publication environment verifier did not pass.")
    return report


def _verify_publication_provenance(protocol: dict[str, Any]) -> dict[str, Any]:
    provenance = protocol.get("publication_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Protocol does not record publication provenance.")
    if provenance.get("schema_version") != 2:
        raise ValueError("Publication provenance schema version is not 2.")
    if protocol.get("toolsandbox_clock_policy") != "frozen":
        raise ValueError("Publication protocol did not freeze the ToolSandbox clock.")
    required_timestamp = str(PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP)
    if protocol.get("toolsandbox_fixed_now_timestamp") != required_timestamp:
        raise ValueError(
            "Protocol ToolSandbox timestamp is not the exact publication pin."
        )
    if (
        provenance.get("fixed_toolsandbox_timestamp")
        != PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
    ):
        raise ValueError(
            "Publication provenance ToolSandbox timestamp is not the exact pin."
        )

    recorded_commit = provenance.get("git_commit")
    recorded_tree = provenance.get("git_tree")
    if not isinstance(recorded_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40,64}", recorded_commit
    ):
        raise ValueError("Publication provenance Git commit is missing or malformed.")
    if not isinstance(recorded_tree, str) or not re.fullmatch(
        r"[0-9a-f]{40,64}", recorded_tree
    ):
        raise ValueError("Publication provenance Git tree is missing or malformed.")
    if provenance.get("git_clean") is not True:
        raise ValueError("Publication provenance does not attest a clean Git worktree.")
    current_source = _clean_source_identity(REPO_ROOT)
    for field in ("git_commit", "git_tree", "git_clean"):
        if provenance.get(field) != current_source.get(field):
            raise ValueError(
                f"Current clean source identity does not match recorded {field}."
            )

    if provenance.get("environment_lock_path") != PUBLICATION_ENVIRONMENT_LOCK:
        raise ValueError(
            "Publication provenance does not name the canonical environment lock."
        )
    lock_path = (REPO_ROOT / PUBLICATION_ENVIRONMENT_LOCK).resolve()
    observed_lock_sha256 = (
        hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if lock_path.is_file()
        else "missing"
    )
    if observed_lock_sha256 != PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256:
        raise ValueError(
            "Current publication environment lock does not match its exact pin."
        )
    if provenance.get("environment_lock_sha256") != observed_lock_sha256:
        raise ValueError(
            "Recorded publication environment lock hash does not match current bytes."
        )
    distribution_count, distribution_sha256 = _external_distribution_lock_identity(
        lock_path
    )
    if provenance.get("external_distribution_count") != distribution_count:
        raise ValueError(
            "Recorded external distribution count does not match the exact lock."
        )
    if provenance.get("external_distribution_sha256") != distribution_sha256:
        raise ValueError(
            "Recorded external distribution identity does not match the exact lock."
        )

    exact_environment: dict[str, Any] = {
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "isolated_environment": True,
        "platform_system": "Darwin",
        "platform_machine": "arm64",
    }
    for field, expected in exact_environment.items():
        if provenance.get(field) != expected:
            raise ValueError(
                f"Publication provenance field {field!r} is "
                f"{provenance.get(field)!r}; expected {expected!r}."
            )
    for field in ("python_executable", "python_prefix", "python_base_prefix"):
        value = provenance.get(field)
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise ValueError(
                f"Publication provenance field {field!r} is not an absolute path."
            )
    if provenance.get("execution_environment") != PUBLICATION_EXECUTION_ENV:
        raise ValueError(
            "Publication provenance does not pin the complete execution policy."
        )

    active_environment = _active_publication_environment(
        lock_path,
        repo_root=REPO_ROOT,
    )
    required_active: dict[str, Any] = {
        **exact_environment,
        "environment_lock_path": str(lock_path),
        "environment_lock_sha256": observed_lock_sha256,
        "external_distribution_count": distribution_count,
        "external_distribution_sha256": distribution_sha256,
    }
    for field, expected in required_active.items():
        if active_environment.get(field) != expected:
            raise ValueError(
                f"Active publication environment field {field!r} is "
                f"{active_environment.get(field)!r}; expected {expected!r}."
            )
    for field in (
        "python_executable",
        "python_version",
        "python_implementation",
        "python_prefix",
        "python_base_prefix",
        "isolated_environment",
        "platform_system",
        "platform_machine",
    ):
        if active_environment.get(field) != provenance.get(field):
            raise ValueError(
                f"Active publication environment does not match recorded {field}."
            )
    return dict(provenance)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read required JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _verify_parallel_arm_execution(
    run_root: Path,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    record = protocol.get("parallel_arm_execution")
    if not isinstance(record, dict):
        raise ValueError("Protocol has no parallel child-process execution evidence.")
    if (
        record.get("unit") != "isolated_child_process"
        or record.get("positive_overlap_asserted") is not True
    ):
        raise ValueError("Parallel execution evidence has invalid process metadata.")
    recorded_arms = record.get("arms")
    if not isinstance(recorded_arms, dict):
        raise ValueError("Parallel execution evidence has no arm records.")
    intervals: dict[str, tuple[int, int]] = {}
    pids: set[int] = set()
    fields = (
        "status",
        "process_pid",
        "started_at",
        "completed_at",
        "started_monotonic_ns",
        "completed_monotonic_ns",
    )
    for arm in ("control", "candidate"):
        arm_record = recorded_arms.get(arm)
        if not isinstance(arm_record, dict):
            raise ValueError(f"Parallel execution evidence is missing {arm!r}.")
        status = _read_json(run_root / f"{arm}_arm_status.json")
        if any(arm_record.get(field) != status.get(field) for field in fields):
            raise ValueError(
                f"Parallel {arm} execution evidence differs from its arm status."
            )
        pid = arm_record.get("process_pid")
        started = arm_record.get("started_monotonic_ns")
        completed = arm_record.get("completed_monotonic_ns")
        if (
            arm_record.get("status") != "complete"
            or isinstance(pid, bool)
            or not isinstance(pid, int)
            or pid <= 0
            or pid in pids
            or isinstance(started, bool)
            or not isinstance(started, int)
            or isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed <= started
        ):
            raise ValueError(f"Parallel {arm} process timing/PID evidence is invalid.")
        pids.add(pid)
        intervals[arm] = (started, completed)
    overlap_ns = min(interval[1] for interval in intervals.values()) - max(
        interval[0] for interval in intervals.values()
    )
    if (
        overlap_ns <= 0
        or record.get("overlap_monotonic_ns") != overlap_ns
        or record.get("overlap_seconds") != overlap_ns / 1_000_000_000
    ):
        raise ValueError("Control and SAGE process intervals do not prove overlap.")
    return record


def _resolve_declared_path(
    run_root: Path,
    value: Any,
    label: str,
    *,
    required_parent: Path | None = None,
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Protocol manifest does not declare {label}.")
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        candidates = [REPO_ROOT / path, Path.cwd() / path, run_root / path]
        existing: list[Path] = []
        for candidate in candidates:
            candidate_resolved = candidate.resolve()
            if candidate_resolved.exists() and candidate_resolved not in existing:
                existing.append(candidate_resolved)
        if len(existing) == 1:
            resolved = existing[0]
        elif len(existing) > 1:
            raise ValueError(f"Protocol {label} path is ambiguous: {value!r}.")
        else:
            resolved = (REPO_ROOT / path).resolve()
    if required_parent is not None and not resolved.is_relative_to(
        required_parent.resolve()
    ):
        raise ValueError(
            f"Protocol {label} escapes its same-run directory: {resolved}."
        )
    return resolved


def _completed_run_roots(search_root: Path) -> list[Path]:
    return sorted(
        {
            path.parent
            for path in search_root.rglob("protocol_manifest.json")
            if (path.parent / "paired_comparison.json").is_file()
            and (path.parent / "control_cache_report.json").is_file()
        },
        key=lambda path: path.stat().st_mtime,
    )


def _verify_registry_content_lineage(
    run_root: Path,
    protocol: dict[str, Any],
    *,
    expected_generation: bool,
) -> dict[str, Any]:
    """Verify exact registry bytes before, after, and at verification time."""

    try:
        before = validate_registry_content_identity(
            protocol.get("registry_content_identity_before_run")
        )
        after = validate_registry_content_identity(
            protocol.get("registry_content_identity_after_run")
        )
    except ValueError as exc:
        raise ValueError(
            f"Protocol registry content identity is invalid: {exc}"
        ) from exc
    registry_dir = _resolve_declared_path(
        run_root,
        protocol.get("registry_dir"),
        "registry_dir",
    )
    try:
        current = registry_content_identity(registry_dir, require_complete=True)
    except ValueError as exc:
        raise ValueError(f"Current publication registry is invalid: {exc}") from exc
    if current != after:
        raise ValueError(
            "Current publication registry bytes do not match the protocol's "
            "post-run identity."
        )
    if (
        after.get("complete") is not True
        or protocol.get("registry_manifest_digest_after_run")
        != after.get("registry_manifest_sha256")
        or protocol.get("frozen_registry_content_immutable") is not True
    ):
        raise ValueError(
            "Protocol post-run registry identity is incomplete or invalid."
        )
    if expected_generation:
        if (
            before.get("complete") is not False
            or before.get("file_count") != 0
            or before.get("files") != []
            or before.get("helper_entry_count") is not None
            or before.get("registry_manifest_sha256") is not None
            or before.get("tool_lifecycle_sha256") is not None
        ):
            raise ValueError(
                "Online publication registry was not exactly empty before execution."
            )
    elif before != after:
        raise ValueError(
            "Frozen publication registry bytes changed between pre-run and post-run."
        )
    return {
        "registry_dir": str(registry_dir),
        "before_run": before,
        "after_run": after,
        "current": current,
    }


def _verify_run_manifest_timezone(run_dir: Path, *, arm: str) -> dict[str, Any]:
    """Require the arm-local manifest to record the publication timezone."""

    run_manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    observed = run_manifest.get("timezone")
    if observed != PUBLICATION_TIMEZONE:
        raise ValueError(
            f"{arm} run manifest timezone is {observed!r}; "
            f"expected {PUBLICATION_TIMEZONE!r}."
        )
    return run_manifest


def _uncached_rows(
    run_dir: Path,
    *,
    expected_tasks: int,
    arm: str,
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, int]]:
    expected_outcome_evaluator = outcome_evaluator_manifest()
    run_manifest = _verify_run_manifest_timezone(run_dir, arm=arm)
    if run_manifest.get("outcome_evaluator") != expected_outcome_evaluator:
        raise ValueError(f"{arm} run manifest has the wrong outcome evaluator.")
    summary_path = run_dir / "result_summary.json"
    payload = _read_json(summary_path)
    rows = payload.get("per_scenario_results")
    if not isinstance(rows, list):
        raise ValueError(f"{arm} result summary has no per-scenario rows.")
    by_name: dict[str, dict[str, Any]] = {}
    totals = {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError(f"{arm} result summary contains a non-object row.")
        name = str(item.get("name") or "")
        if not name:
            raise ValueError(f"{arm} result summary contains an unnamed task.")
        if name in by_name:
            raise ValueError(f"{arm} result summary duplicates task {name!r}.")
        for exception_field in ("exception_type", "traceback"):
            if exception_field not in item:
                raise ValueError(
                    f"{arm} task {name!r} does not report runtime exception "
                    f"field {exception_field!r}."
                )
        if item["exception_type"] is not None:
            raise ValueError(
                f"{arm} task {name!r} contains runtime exception "
                f"{item['exception_type']!r}."
            )
        if item["traceback"] is not None:
            raise ValueError(
                f"{arm} task {name!r} contains a runtime exception traceback."
            )
        raw_outcome = item.get("outcome_similarity")
        if (
            isinstance(raw_outcome, bool)
            or not isinstance(raw_outcome, (int, float))
            or not math.isfinite(float(raw_outcome))
            or not 0.0 <= float(raw_outcome) <= 1.0
        ):
            raise ValueError(
                f"{arm} task {name!r} has no valid outcome-evaluator value."
            )
        for row_field, identity_field in OUTCOME_EVALUATOR_ROW_FIELDS.items():
            if item.get(row_field) != expected_outcome_evaluator[identity_field]:
                raise ValueError(f"{arm} task {name!r} has mismatched {row_field}.")
        validate_successful_retry_provenance(
            item,
            run_dir=run_dir,
            repo_root=REPO_ROOT,
            arm=arm,
            scenario=name,
        )
        cache_source = str(item.get("control_cache_source") or "").lower()
        cache_detail = item.get("control_cache")
        if cache_source and cache_source != "fresh":
            raise ValueError(f"{arm} task {name!r} is cache sourced.")
        if isinstance(cache_detail, dict) and (
            str(cache_detail.get("source") or "").lower() == "cached"
            or cache_detail.get("record_ids")
        ):
            raise ValueError(f"{arm} task {name!r} contains cached baseline data.")
        if "llm_cached_call_count" not in item:
            raise ValueError(
                f"{arm} task {name!r} does not report repository whole-response "
                "replay provenance."
            )
        repository_response_replays = item["llm_cached_call_count"]
        if isinstance(repository_response_replays, bool) or not isinstance(
            repository_response_replays, int
        ):
            raise ValueError(
                f"{arm} task {name!r} has invalid repository whole-response "
                "replay provenance."
            )
        if repository_response_replays:
            raise ValueError(
                f"{arm} task {name!r} contains repository whole-response replay calls."
            )
        usage_counts: dict[str, int] = {}
        for field in LLM_USAGE_INTEGER_FIELDS:
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{arm} task {name!r} has invalid or missing {field}.")
            usage_counts[field] = value
        if item.get("llm_usage_recorded") is not bool(usage_counts["llm_call_count"]):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent llm_usage_recorded status."
            )
        if (
            usage_counts["llm_live_call_count"] + usage_counts["llm_cached_call_count"]
            != usage_counts["llm_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent live/replayed LLM call counts."
            )
        if (
            usage_counts["llm_provider_cached_prompt_tokens_available_count"]
            != usage_counts["llm_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} is missing provider-prefix cache metadata "
                "for one or more LLM calls."
            )
        if usage_counts["llm_usage_available_count"] != usage_counts["llm_call_count"]:
            raise ValueError(
                f"{arm} task {name!r} is missing token usage for one or more LLM calls."
            )
        if (
            usage_counts["llm_provider_cached_prompt_call_count"]
            > usage_counts["llm_provider_cached_prompt_tokens_available_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} reports more provider-prefix cache calls "
                "than LLM calls."
            )
        if (
            usage_counts["llm_provider_cached_prompt_tokens"]
            > usage_counts["llm_prompt_tokens"]
        ):
            raise ValueError(
                f"{arm} task {name!r} reports more provider-prefix cached tokens "
                "than prompt tokens."
            )
        if bool(usage_counts["llm_provider_cached_prompt_tokens"]) != bool(
            usage_counts["llm_provider_cached_prompt_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent provider-prefix cache "
                "token and call counts."
            )
        if usage_counts["llm_total_tokens"] != (
            usage_counts["llm_prompt_tokens"] + usage_counts["llm_completion_tokens"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent total token accounting."
            )
        for field, value in usage_counts.items():
            totals[field] += value
        by_name[name] = item
    if len(by_name) != expected_tasks:
        raise ValueError(
            f"{arm} has {len(by_name)} unique task rows; expected {expected_tasks}."
        )
    for forbidden in (
        run_dir / "openai_response_cache_metrics.json",
        run_dir / "prompt_cache_metrics.json",
    ):
        if forbidden.exists():
            raise ValueError(f"{arm} emitted forbidden cache artifact {forbidden}.")
    return by_name, list(by_name), totals


def _required_usage_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _verify_llm_usage_artifacts(
    run_dir: Path,
    *,
    rows: dict[str, dict[str, Any]],
    row_totals: dict[str, int],
    arm: str,
    expected_event_arm: str,
    allow_generation_source: bool,
) -> None:
    """Reconcile row, arm-summary, and raw-event LLM usage evidence."""

    summary_path = run_dir / "llm_usage_summary.json"
    summary = _read_json(summary_path)
    if summary.get("schema_version") != 2:
        raise ValueError(f"{arm} LLM usage summary schema version is not 2.")
    if summary.get("token_source") != "openai_chat_completion_usage":
        raise ValueError(f"{arm} LLM usage summary has an invalid token source.")
    if summary.get("llm_usage_recorded") is not bool(row_totals["llm_call_count"]):
        raise ValueError(f"{arm} LLM usage summary has inconsistent recorded status.")
    for field in LLM_USAGE_INTEGER_FIELDS:
        observed = _required_usage_integer(
            summary.get(field),
            label=f"{arm} LLM usage summary field {field!r}",
        )
        if observed != row_totals[field]:
            raise ValueError(
                f"{arm} LLM usage summary field {field!r} does not match "
                "the result rows."
            )
    expected_scenario_count = sum(
        1 for row in rows.values() if row["llm_call_count"] > 0
    )
    if summary.get("scenario_count_with_usage") != expected_scenario_count:
        raise ValueError(
            f"{arm} LLM usage summary scenario count does not match result rows."
        )

    events_path = run_dir / "llm_usage_events.jsonl"
    if not events_path.is_file():
        raise ValueError(f"Missing {arm} LLM usage event artifact: {events_path}")
    event_totals = {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
    scenario_totals = {
        name: {field: 0 for field in LLM_USAGE_INTEGER_FIELDS} for name in rows
    }
    source_totals: dict[str, dict[str, int]] = {}
    event_count = 0
    allowed_sources = {"toolsandbox_agent", "toolsandbox_user"}
    if allow_generation_source:
        allowed_sources.add("sage_generation")
    try:
        event_lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(
            f"Cannot read required LLM usage artifact {events_path}: {exc}"
        ) from exc
    for line_number, line in enumerate(event_lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is invalid JSON: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is not an object."
            )
        scenario = event.get("scenario")
        if not isinstance(scenario, str) or scenario not in rows:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an unknown scenario."
            )
        if event.get("model") != PUBLICATION_MODEL:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} does not use "
                f"{PUBLICATION_MODEL}."
            )
        if event.get("source") not in allowed_sources:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an invalid source."
            )
        if event.get("arm") != expected_event_arm:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an invalid arm."
            )
        if event.get("response_cache_status") != "live":
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is not a live response."
            )
        if event.get("usage_available") is not True:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no token usage."
            )
        prompt_tokens = _required_usage_integer(
            event.get("prompt_tokens"),
            label=f"{arm} LLM usage event line {line_number} prompt_tokens",
        )
        cached_prompt_tokens = _required_usage_integer(
            event.get("provider_cached_prompt_tokens"),
            label=(
                f"{arm} LLM usage event line {line_number} "
                "provider_cached_prompt_tokens"
            ),
        )
        completion_tokens = _required_usage_integer(
            event.get("completion_tokens"),
            label=f"{arm} LLM usage event line {line_number} completion_tokens",
        )
        total_tokens = _required_usage_integer(
            event.get("total_tokens"),
            label=f"{arm} LLM usage event line {line_number} total_tokens",
        )
        if cached_prompt_tokens > prompt_tokens:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} reports more "
                "provider-prefix cached tokens than prompt tokens."
            )
        if total_tokens != prompt_tokens + completion_tokens:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has inconsistent "
                "total token accounting."
            )
        raw_usage = event.get("raw_usage")
        if not isinstance(raw_usage, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no raw API usage."
            )
        raw_prompt_tokens = _required_usage_integer(
            raw_usage.get("prompt_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw prompt_tokens",
        )
        raw_completion_tokens = _required_usage_integer(
            raw_usage.get("completion_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw completion_tokens",
        )
        raw_total_tokens = _required_usage_integer(
            raw_usage.get("total_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw total_tokens",
        )
        raw_prompt_details = raw_usage.get("prompt_tokens_details")
        if not isinstance(raw_prompt_details, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no raw "
                "prompt-token details."
            )
        raw_cached_prompt_tokens = _required_usage_integer(
            raw_prompt_details.get("cached_tokens"),
            label=(f"{arm} LLM usage event line {line_number} raw cached_tokens"),
        )
        if (
            raw_prompt_tokens != prompt_tokens
            or raw_completion_tokens != completion_tokens
            or raw_total_tokens != total_tokens
            or raw_cached_prompt_tokens != cached_prompt_tokens
        ):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} disagrees with "
                "its raw API usage."
            )
        increments = {
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": prompt_tokens,
            "llm_provider_cached_prompt_tokens": cached_prompt_tokens,
            "llm_provider_cached_prompt_call_count": int(cached_prompt_tokens > 0),
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": completion_tokens,
            "llm_total_tokens": total_tokens,
            "llm_usage_available_count": 1,
        }
        for field, value in increments.items():
            event_totals[field] += value
            scenario_totals[scenario][field] += value
        source = str(event["source"])
        if source not in source_totals:
            source_totals[source] = {
                field: 0 for field in LLM_USAGE_SOURCE_INTEGER_FIELDS
            }
        for field in LLM_USAGE_SOURCE_INTEGER_FIELDS:
            source_totals[source][field] += increments[field]
        event_count += 1

    if event_count != row_totals["llm_call_count"]:
        raise ValueError(f"{arm} LLM usage event count does not match result rows.")
    for field in LLM_USAGE_INTEGER_FIELDS:
        if event_totals[field] != row_totals[field]:
            raise ValueError(
                f"{arm} raw LLM usage events field {field!r} does not match "
                "the result rows."
            )
    for scenario, expected in scenario_totals.items():
        row = rows[scenario]
        for field in LLM_USAGE_INTEGER_FIELDS:
            if expected[field] != row[field]:
                raise ValueError(
                    f"{arm} raw LLM usage events for task {scenario!r} field "
                    f"{field!r} do not match the result row."
                )
    if summary.get("llm_usage_by_source") != dict(sorted(source_totals.items())):
        raise ValueError(f"{arm} LLM usage source summary does not match raw events.")


def _verify_reflection(
    candidate_dir: Path,
    *,
    control_rows: dict[str, dict[str, Any]],
) -> None:
    feedback_path = candidate_dir / "self_evolution_task_feedback.jsonl"
    if not feedback_path.is_file():
        raise ValueError(f"Missing same-run reflection feedback: {feedback_path}")
    feedback: dict[str, dict[str, Any]] = {}
    for line in feedback_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("event") != "self_evolution_task_assessed":
            continue
        name = str(row.get("scenario") or "")
        if not name or name in feedback:
            raise ValueError(f"Duplicate or unnamed reflection task {name!r}.")
        if row.get("control_source") != "same_run_fresh":
            raise ValueError(f"Reflection task {name!r} is not same-run fresh.")
        control = control_rows.get(name)
        if control is None:
            raise ValueError(f"Reflection task {name!r} has no matched live control.")
        if row.get("control_outcome") != control.get("outcome_similarity"):
            raise ValueError(f"Reflection control outcome mismatch for {name!r}.")
        feedback[name] = row
    if set(feedback) != set(control_rows):
        raise ValueError(
            "Reflection/control task sets differ "
            f"(missing={sorted(set(control_rows) - set(feedback))!r}, "
            f"extra={sorted(set(feedback) - set(control_rows))!r})."
        )


def verify_run(
    search_root: Path,
    *,
    expected_tasks: int,
    expect_reflection: str,
    expected_fixture_sha256: str = PINNED_RAPID_FIXTURE_SHA256,
    expected_benchmark_sha256: str = PINNED_BENCHMARK_SHA256,
    expected_scenario_order_sha256: str = PINNED_SCENARIO_ORDER_SHA256,
) -> dict[str, Any]:
    runs = _completed_run_roots(search_root)
    if not runs:
        raise ValueError(f"No completed paired run found under {search_root}.")
    run_root = runs[-1]
    protocol = _read_json(run_root / "protocol_manifest.json")
    current_outcome_evaluator = outcome_evaluator_manifest()
    if protocol.get("outcome_evaluator") != current_outcome_evaluator:
        raise ValueError("Protocol manifest has the wrong outcome evaluator identity.")
    paired_comparison = _read_json(run_root / "paired_comparison.json")
    if paired_comparison.get("outcome_evaluator") != current_outcome_evaluator:
        raise ValueError("Paired comparison has the wrong outcome evaluator identity.")
    cache_report = _read_json(run_root / "control_cache_report.json")
    publication_provenance = _verify_publication_provenance(protocol)
    for model_field in ("agent", "user", "generation_model"):
        if protocol.get(model_field) != PUBLICATION_MODEL:
            raise ValueError(
                f"Protocol field {model_field!r} is not {PUBLICATION_MODEL}."
            )
    expected_mode = (
        "online_build_full"
        if expect_reflection == "same-run-fresh"
        else "full_benchmark"
    )
    if protocol.get("mode") != expected_mode:
        raise ValueError(f"Protocol mode is not {expected_mode!r}.")
    expected_generation = expect_reflection == "same-run-fresh"
    if protocol.get("generation_enabled") is not expected_generation:
        raise ValueError(
            "Protocol generation_enabled does not match the publication arm."
        )
    expected_sage_policy = "self-evolving-praxis" if expected_generation else "none"
    if protocol.get("sage_policy") != expected_sage_policy:
        raise ValueError(f"Protocol sage_policy is not {expected_sage_policy!r}.")
    registry_content_lineage = _verify_registry_content_lineage(
        run_root,
        protocol,
        expected_generation=expected_generation,
    )
    if int(protocol.get("scenario_count") or 0) != expected_tasks:
        raise ValueError(
            "Protocol scenario count does not match the publication cohort."
        )
    if protocol.get("benchmark_manifest_sha256") != expected_benchmark_sha256:
        raise ValueError(
            "Protocol benchmark manifest does not match the publication pin."
        )
    benchmark_path = _resolve_declared_path(
        run_root,
        protocol.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    if not benchmark_path.is_file():
        raise ValueError(f"Recorded benchmark manifest is missing: {benchmark_path}")
    if (
        hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
        != expected_benchmark_sha256
    ):
        raise ValueError("Recorded benchmark manifest bytes no longer match the pin.")
    if protocol.get("scenario_order_sha256") != expected_scenario_order_sha256:
        raise ValueError(
            "Protocol ordered scenario names do not match the publication pin."
        )
    required_protocol = {
        "fresh_control_required": True,
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "timezone": PUBLICATION_TIMEZONE,
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "openai_response_cache_scope": "persistent_repository_whole_response_replay",
        "prompt_cache_enabled": False,
        "prompt_cache_scope": "persistent_generation_output_replay",
        "generator_contract_and_repair_analysis_memoization": "within_run_only",
        "openai_provider_prompt_prefix_cache_policy": "automatic_implicit",
        "openai_provider_prompt_prefix_cache_reuses_responses": False,
        "sage_task_cache_enabled": False,
        "cross_run_failure_memory_enabled": False,
        "cross_run_failure_memory_path": None,
        "diagnostic_force_allowed": False,
        "active_diagnostic_force_env": [],
        "parallel_arms": True,
        "reflection_control_delivery": (
            "task_synchronous_stream"
            if expected_generation
            else "not_applicable_generation_disabled"
        ),
        "dashboard_open_required": True,
    }
    for field, expected in required_protocol.items():
        if protocol.get(field) != expected:
            raise ValueError(
                f"Protocol field {field!r} is {protocol.get(field)!r}; "
                f"expected {expected!r}."
            )
    parallel_execution = _verify_parallel_arm_execution(run_root, protocol)
    dashboard_receipt_path = _resolve_declared_path(
        run_root,
        protocol.get("dashboard_open_receipt_path"),
        "dashboard_open_receipt_path",
        required_parent=run_root,
    )
    dashboard_receipt = _read_json(dashboard_receipt_path)
    expected_task_dashboard = (run_root / "dashboard" / "task_compare.html").resolve()
    expected_actor_selection_mode = str(
        protocol.get("candidate_actor_selection_mode") or ""
    )
    expected_comparison = (
        f"fresh_control_vs_sage_{expected_actor_selection_mode}_selection"
    )
    opened_monotonic_ns = dashboard_receipt.get("opened_monotonic_ns")
    first_model_process_start = min(
        int(parallel_execution["arms"][arm]["started_monotonic_ns"])
        for arm in ("control", "candidate")
    )
    if (
        dashboard_receipt.get("dashboard") != "task_compare"
        or dashboard_receipt.get("comparison") != expected_comparison
        or Path(str(dashboard_receipt.get("path") or "")).resolve()
        != expected_task_dashboard
        or dashboard_receipt.get("url") != protocol.get("dashboard_task_compare_url")
        or dashboard_receipt.get("external_browser_opened") is not True
        or dashboard_receipt.get("http_verified_before_open") is not True
        or dashboard_receipt.get("dashboard_server_protocol")
        != DASHBOARD_SERVER_PROTOCOL
        or Path(str(dashboard_receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or dashboard_receipt.get("opened_before_model_processes") is not True
        or isinstance(opened_monotonic_ns, bool)
        or not isinstance(opened_monotonic_ns, int)
        or opened_monotonic_ns <= 0
        or opened_monotonic_ns >= first_model_process_start
    ):
        raise ValueError(
            "Task Compare dashboard external-open receipt is invalid or does not "
            "prove a pre-model open."
        )
    dashboard_data = _read_json(
        expected_task_dashboard.with_name("task_compare_data.json")
    )
    dashboard_summary = dashboard_data.get("summary")
    dashboard_summary_count = (
        dashboard_summary.get("scenario_count")
        if isinstance(dashboard_summary, dict)
        else None
    )
    dashboard_top_level_count = dashboard_data.get("scenario_count")
    dashboard_scenario_count = (
        dashboard_top_level_count
        if dashboard_top_level_count is not None
        else dashboard_summary_count
    )
    dashboard_counts_agree = (
        dashboard_top_level_count is None
        or dashboard_summary_count is None
        or dashboard_top_level_count == dashboard_summary_count
    )
    if (
        dashboard_data.get("arm_labels")
        != {
            "control": "Fresh non-learning control",
            "candidate": f"SAGE {expected_actor_selection_mode} selection",
        }
        or dashboard_scenario_count != expected_tasks
        or not dashboard_counts_agree
    ):
        raise ValueError(
            "Task Compare dashboard does not unambiguously identify both "
            "concurrent publication arms."
        )
    run_env = protocol.get("run_affecting_sage_env")
    if not isinstance(run_env, dict):
        raise ValueError("Publication run did not record its execution environment.")
    for env_name, expected in PUBLICATION_EXECUTION_ENV.items():
        if run_env.get(env_name) != expected:
            raise ValueError(f"Publication run did not record {env_name}={expected!r}.")
    fixture = protocol.get("external_fixture")
    if not isinstance(fixture, dict):
        raise ValueError("Protocol does not record a validated external fixture.")
    if fixture.get("policy") != "validated_read_only_fixture":
        raise ValueError("External fixture policy is not validated read-only.")
    if fixture.get("mode") != "read_only":
        raise ValueError("External fixture was not used read-only.")
    if fixture.get("sha256") != expected_fixture_sha256:
        raise ValueError("External fixture does not match the pinned SHA-256.")
    fixture_path = _resolve_declared_path(
        run_root,
        fixture.get("path"),
        "external_fixture.path",
    )
    if not fixture_path.is_file():
        raise ValueError(f"Recorded external fixture is missing: {fixture_path}")
    observed_fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    if observed_fixture_sha256 != expected_fixture_sha256:
        raise ValueError("Recorded external fixture bytes no longer match the pin.")
    if expect_reflection == "same-run-fresh":
        if protocol.get("reflection_control_source") != "same_run_fresh":
            raise ValueError(
                "Online reflection did not declare same-run fresh control."
            )
    elif protocol.get("reflection_control_source") != "not_applicable":
        raise ValueError(
            "Frozen run unexpectedly declared a reflection control source."
        )
    for field in (
        "resume_run_root",
        "resume_completed_limit",
        "control_resume_dir",
        "candidate_resume_dir",
    ):
        if protocol.get(field) is not None:
            raise ValueError(
                f"Publication run used forbidden partial-row resume field {field!r}."
            )
    required_report = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "cache_accessed": False,
        "fresh_control_enforced": True,
    }
    for field, expected in required_report.items():
        if cache_report.get(field) != expected:
            raise ValueError(
                f"Control report field {field!r} is {cache_report.get(field)!r}; "
                f"expected {expected!r}."
            )
    control_dir = _resolve_declared_path(
        run_root,
        protocol.get("control_dir"),
        "control_dir",
        required_parent=run_root / "control",
    )
    candidate_dir = _resolve_declared_path(
        run_root,
        protocol.get("candidate_dir"),
        "candidate_dir",
        required_parent=run_root / "candidate",
    )
    control_rows, control_order, control_llm_usage = _uncached_rows(
        control_dir,
        expected_tasks=expected_tasks,
        arm="control",
    )
    candidate_rows, candidate_order, candidate_llm_usage = _uncached_rows(
        candidate_dir,
        expected_tasks=expected_tasks,
        arm="candidate",
    )
    _verify_llm_usage_artifacts(
        control_dir,
        rows=control_rows,
        row_totals=control_llm_usage,
        arm="control",
        expected_event_arm=f"{expected_mode}_control",
        allow_generation_source=False,
    )
    _verify_llm_usage_artifacts(
        candidate_dir,
        rows=candidate_rows,
        row_totals=candidate_llm_usage,
        arm="candidate",
        expected_event_arm=f"{expected_mode}_candidate",
        allow_generation_source=expected_generation,
    )
    if control_order != candidate_order:
        raise ValueError("Control and candidate task order is not identical.")
    observed_order_sha256 = hashlib.sha256(
        ("\n".join(control_order) + "\n").encode("utf-8")
    ).hexdigest()
    if observed_order_sha256 != expected_scenario_order_sha256:
        raise ValueError(
            "Result rows do not preserve the pinned publication task order."
        )
    if expect_reflection == "same-run-fresh":
        _verify_reflection(candidate_dir, control_rows=control_rows)
    return {
        "status": "pass",
        "run_root": str(run_root),
        "scenario_count": expected_tasks,
        "cached_control_tasks": 0,
        # Backward-compatible name: this counts repository response replays,
        # not provider prompt-prefix cached input tokens.
        "cached_llm_calls": 0,
        "repository_whole_response_replay_hits": 0,
        "openai_provider_prompt_prefix_cache_policy": protocol[
            "openai_provider_prompt_prefix_cache_policy"
        ],
        "publication_model": PUBLICATION_MODEL,
        "openai_provider_cached_prompt_tokens": {
            "control": control_llm_usage["llm_provider_cached_prompt_tokens"],
            "candidate": candidate_llm_usage["llm_provider_cached_prompt_tokens"],
        },
        "openai_provider_cached_prompt_call_count": {
            "control": control_llm_usage["llm_provider_cached_prompt_call_count"],
            "candidate": candidate_llm_usage["llm_provider_cached_prompt_call_count"],
        },
        "openai_provider_cached_prompt_tokens_available_count": {
            "control": control_llm_usage[
                "llm_provider_cached_prompt_tokens_available_count"
            ],
            "candidate": candidate_llm_usage[
                "llm_provider_cached_prompt_tokens_available_count"
            ],
        },
        "reflection_control_source": protocol.get("reflection_control_source"),
        "timezone": PUBLICATION_TIMEZONE,
        "outcome_evaluator": current_outcome_evaluator,
        "parallel_arm_execution": parallel_execution,
        "external_fixture_sha256": observed_fixture_sha256,
        "git_commit": publication_provenance["git_commit"],
        "git_tree": publication_provenance["git_tree"],
        "python_version": publication_provenance["python_version"],
        "python_implementation": publication_provenance["python_implementation"],
        "platform_system": publication_provenance["platform_system"],
        "platform_machine": publication_provenance["platform_machine"],
        "environment_lock_sha256": publication_provenance["environment_lock_sha256"],
        "external_distribution_count": publication_provenance[
            "external_distribution_count"
        ],
        "external_distribution_sha256": publication_provenance[
            "external_distribution_sha256"
        ],
        "fixed_toolsandbox_timestamp": publication_provenance[
            "fixed_toolsandbox_timestamp"
        ],
        "registry_dir": registry_content_lineage["registry_dir"],
        "registry_content_identity_before_run": registry_content_lineage["before_run"],
        "registry_content_identity_after_run": registry_content_lineage["after_run"],
        "publication_provenance": publication_provenance,
    }


def verify_pinned_run(
    search_root: Path,
    *,
    cohort: str = "full",
    expect_reflection: str,
) -> dict[str, Any]:
    """Verify one internally pinned publication cohort without caller-supplied pins."""

    if expect_reflection not in {"same-run-fresh", "not-applicable"}:
        raise ValueError(
            "expect_reflection must be 'same-run-fresh' or 'not-applicable'."
        )
    expected_tasks, expected_benchmark, expected_order = publication_cohort_pins(cohort)
    result = verify_run(
        search_root,
        expected_tasks=expected_tasks,
        expect_reflection=expect_reflection,
        expected_benchmark_sha256=expected_benchmark,
        expected_scenario_order_sha256=expected_order,
    )
    result["publication_cohort"] = cohort
    return result


def _outcome_only_pair_summary(
    control_rows: dict[str, dict[str, Any]],
    auto_rows: dict[str, dict[str, Any]],
    scenario_order: list[str],
) -> dict[str, object]:
    if not scenario_order:
        raise ValueError("Auto-selection outcome comparison has an empty cohort.")
    control_values = [
        float(control_rows[name]["outcome_similarity"]) for name in scenario_order
    ]
    auto_values = [
        float(auto_rows[name]["outcome_similarity"]) for name in scenario_order
    ]
    count = len(scenario_order)
    return {
        "schema_version": 1,
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "scenario_count": count,
        "outcome_evaluated_count": count,
        "control_exact_outcome_successes": sum(
            value == 1.0 for value in control_values
        ),
        "auto_exact_outcome_successes": sum(value == 1.0 for value in auto_values),
        "control_mean_outcome_similarity": sum(control_values) / count,
        "auto_mean_outcome_similarity": sum(auto_values) / count,
        "mean_outcome_similarity_delta": (
            sum(auto_values) / count - sum(control_values) / count
        ),
        "auto_outcome_gain_count": sum(
            auto > control for control, auto in zip(control_values, auto_values)
        ),
        "auto_outcome_regression_count": sum(
            auto < control for control, auto in zip(control_values, auto_values)
        ),
        "outcome_tie_count": sum(
            auto == control for control, auto in zip(control_values, auto_values)
        ),
    }


def _verify_complete_outcome_dashboard(
    dashboard_data: dict[str, Any],
    *,
    expected_tasks: int,
) -> dict[str, float | int]:
    """Fail closed unless every displayed task has both finite outcome arms."""

    pairs = dashboard_data.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != expected_tasks:
        raise ValueError(
            "Task Compare does not contain the expected number of outcome pairs."
        )
    scenarios: set[str] = set()
    control_values: list[float] = []
    candidate_values: list[float] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("Task Compare contains a non-object outcome pair.")
        scenario = pair.get("scenario")
        if not isinstance(scenario, str) or not scenario or scenario in scenarios:
            raise ValueError(
                "Task Compare contains a missing or duplicate outcome-pair scenario."
            )
        scenarios.add(scenario)
        for phase, values in (
            ("control", control_values),
            ("candidate", candidate_values),
        ):
            row = pair.get(phase)
            if (
                not isinstance(row, dict)
                or row.get("scenario") != scenario
                or row.get("phase") != phase
                or row.get("status") != "complete"
            ):
                raise ValueError(
                    f"Task Compare outcome pair {scenario!r} has no complete "
                    f"{phase} arm."
                )
            raw_outcome = row.get("outcome_similarity")
            if (
                isinstance(raw_outcome, bool)
                or not isinstance(raw_outcome, (int, float))
                or not math.isfinite(float(raw_outcome))
                or not 0.0 <= float(raw_outcome) <= 1.0
            ):
                raise ValueError(
                    f"Task Compare outcome pair {scenario!r} has no valid "
                    f"{phase} outcome."
                )
            values.append(float(raw_outcome))

    control_mean = sum(control_values) / expected_tasks
    candidate_mean = sum(candidate_values) / expected_tasks
    outcome_delta = candidate_mean - control_mean
    summary = dashboard_data.get("summary")
    expected_summary = {
        "balanced_completed": expected_tasks,
        "balanced_control_mean_outcome_similarity": control_mean,
        "balanced_candidate_mean_outcome_similarity": candidate_mean,
        "balanced_outcome_delta": outcome_delta,
    }
    if not isinstance(summary, dict):
        raise ValueError("Task Compare has no balanced outcome summary.")
    for field, expected in expected_summary.items():
        observed = summary.get(field)
        if field == "balanced_completed":
            if observed != expected:
                raise ValueError("Task Compare balanced outcome count is incomplete.")
        elif (
            isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not math.isfinite(float(observed))
            or not math.isclose(
                float(observed), float(expected), rel_tol=0.0, abs_tol=1e-12
            )
        ):
            raise ValueError(
                f"Task Compare balanced outcome field {field!r} is inconsistent."
            )
    return {
        "control_mean": control_mean,
        "candidate_mean": candidate_mean,
        "outcome_delta": outcome_delta,
        "control_exact_successes": sum(value == 1.0 for value in control_values),
        "candidate_exact_successes": sum(value == 1.0 for value in candidate_values),
    }


def verify_auto_selection_parallel_pair(
    pair_manifest_path: Path,
    *,
    run_root: Path,
    expected_tasks: int,
    expected_scenario_order_sha256: str,
    expected_auto_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify that auto-selection ran beside an isolated fresh control."""

    run_root = run_root.resolve()
    pair_manifest_path = pair_manifest_path.resolve()
    pair_root = pair_manifest_path.parent
    if (
        pair_root != run_root / "sage_auto_selection_parallel_pair"
        or pair_manifest_path != pair_root / "parallel_pair_manifest.json"
    ):
        raise ValueError("Auto-selection parallel-pair manifest is outside its run.")
    pair = _read_json(pair_manifest_path)
    expected_evaluator = outcome_evaluator_manifest()
    required = {
        "schema_version": 1,
        "experiment": "sage_auto_selection_parallel_control_pair",
        "status": "complete",
        "mode": "online_build_full",
        "scenario_count": expected_tasks,
        "scenario_order_sha256": expected_scenario_order_sha256,
        "control_role": "fresh_non_learning_control",
        "candidate_role": "sage_auto_selection",
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "cache_accessed": False,
        "openai_response_cache_enabled": False,
        "sage_task_cache_enabled": False,
        "persistent_response_cache_reuse": False,
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "legacy_score_is_performance_gate": False,
        "parallel_arms": True,
        "auto_control_delivery": "not_connected",
        "auto_control_output_influences_inventory": False,
        "auto_control_output_influences_execution": False,
        "auto_inventory_source": "matched_policy_inventory_authority",
        "outcome_evaluator": expected_evaluator,
        "timezone": PUBLICATION_TIMEZONE,
    }
    for field, expected in required.items():
        if pair.get(field) != expected:
            raise ValueError(
                f"Auto-selection parallel-pair field {field!r} is "
                f"{pair.get(field)!r}; expected {expected!r}."
            )

    control_dir = _resolve_declared_path(
        run_root,
        pair.get("control_run_dir"),
        "auto_parallel_control_run_dir",
        required_parent=pair_root / "control",
    )
    auto_dir = _resolve_declared_path(
        run_root,
        pair.get("auto_run_dir"),
        "auto_parallel_sage_run_dir",
        required_parent=run_root / "sage_auto_selection",
    )
    if expected_auto_dir is not None and auto_dir != expected_auto_dir.resolve():
        raise ValueError("Auto-selection pair links a different SAGE run directory.")

    parallel_execution = _verify_parallel_arm_execution(pair_root, pair)
    control_rows, control_order, control_usage = _uncached_rows(
        control_dir,
        expected_tasks=expected_tasks,
        arm="auto-selection fresh control",
    )
    auto_rows, auto_order, auto_usage = _uncached_rows(
        auto_dir,
        expected_tasks=expected_tasks,
        arm="sage_auto_selection",
    )
    if control_order != auto_order:
        raise ValueError(
            "Auto-selection SAGE and its fresh control do not have identical task order."
        )
    observed_order_sha256 = hashlib.sha256(
        ("\n".join(control_order) + "\n").encode("utf-8")
    ).hexdigest()
    if observed_order_sha256 != expected_scenario_order_sha256:
        raise ValueError("Auto-selection parallel pair changed the pinned task order.")
    _verify_llm_usage_artifacts(
        control_dir,
        rows=control_rows,
        row_totals=control_usage,
        arm="auto-selection fresh control",
        expected_event_arm="online_build_full_control",
        allow_generation_source=False,
    )
    outcome_comparison_path = _resolve_declared_path(
        run_root,
        pair.get("outcome_comparison_path"),
        "auto_parallel_outcome_comparison_path",
        required_parent=pair_root,
    )
    if (
        outcome_comparison_path != pair_root / "auto_control_outcome_comparison.json"
        or not outcome_comparison_path.is_file()
        or pair.get("outcome_comparison_sha256")
        != hashlib.sha256(outcome_comparison_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Auto-selection control outcome comparison has drifted.")
    outcome_comparison = _read_json(outcome_comparison_path)
    recomputed_outcomes = _outcome_only_pair_summary(
        control_rows,
        auto_rows,
        control_order,
    )
    if outcome_comparison != recomputed_outcomes:
        raise ValueError(
            "Auto-selection control outcome comparison does not match result rows."
        )
    _verify_llm_usage_artifacts(
        auto_dir,
        rows=auto_rows,
        row_totals=auto_usage,
        arm="sage_auto_selection",
        expected_event_arm="online_build_full_sage_auto_selection",
        allow_generation_source=False,
    )

    control_config = _read_json(control_dir.parent / "sage_ts_run_manifest.json")
    auto_config = _read_json(auto_dir.parent / "sage_ts_run_manifest.json")
    common_fields = ("agent", "user", "scenario_names", "processes", "base_tool_policy")
    if any(
        control_config.get(field) != auto_config.get(field) for field in common_fields
    ):
        raise ValueError(
            "Auto-selection SAGE and its fresh control have mismatched run settings."
        )
    if (
        control_config.get("actor_selection_mode") != "policy"
        or auto_config.get("actor_selection_mode") != "auto"
        or control_config.get("processes") != 1
        or auto_config.get("processes") != 1
        or control_config.get("resume_from_dir") is not None
        or auto_config.get("resume_from_dir") is not None
        or control_config.get("resume_completed_limit") is not None
        or auto_config.get("resume_completed_limit") is not None
    ):
        raise ValueError("Auto-selection parallel-pair arm configuration is invalid.")
    if (
        pair.get("agent") != auto_config.get("agent")
        or pair.get("user") != auto_config.get("user")
        or pair.get("base_tool_policy") != auto_config.get("base_tool_policy")
    ):
        raise ValueError("Auto-selection pair manifest disagrees with arm settings.")

    selection_summary = _read_json(auto_dir / "selection_summary.json")
    authority_path = _resolve_declared_path(
        run_root,
        pair.get("inventory_authority_path"),
        "auto_parallel_inventory_authority_path",
    )
    if (
        not authority_path.is_file()
        or pair.get("inventory_authority_sha256")
        != hashlib.sha256(authority_path.read_bytes()).hexdigest()
        or selection_summary.get("generation_enabled") is not False
        or selection_summary.get("actor_selection_mode") != "auto"
        or selection_summary.get("inventory_authority_mode") != "replay"
        or selection_summary.get("inventory_authority_task_count") != expected_tasks
        or selection_summary.get("inventory_authority_controls_later_exposure")
        is not True
        or selection_summary.get("inventory_authority_source_actor_selection_mode")
        != "policy"
    ):
        raise ValueError(
            "Auto-selection arm did not use the complete policy inventory authority."
        )
    if (auto_dir / "self_evolution_task_feedback.jsonl").exists():
        raise ValueError(
            "Auto-selection arm consumed control feedback despite disconnected control."
        )

    dashboard_receipt_path = _resolve_declared_path(
        run_root,
        pair.get("dashboard_open_receipt_path"),
        "auto_parallel_dashboard_open_receipt_path",
        required_parent=pair_root,
    )
    dashboard_receipt = _read_json(dashboard_receipt_path)
    dashboard_path = _resolve_declared_path(
        run_root,
        pair.get("dashboard_task_compare_path"),
        "auto_parallel_dashboard_task_compare_path",
        required_parent=pair_root,
    )
    opened_monotonic_ns = dashboard_receipt.get("opened_monotonic_ns")
    first_process_start = min(
        int(parallel_execution["arms"][arm]["started_monotonic_ns"])
        for arm in ("control", "candidate")
    )
    if (
        dashboard_path != pair_root / "dashboard" / "task_compare.html"
        or not dashboard_path.is_file()
        or dashboard_receipt.get("dashboard") != "task_compare"
        or dashboard_receipt.get("comparison") != "fresh_control_vs_sage_auto_selection"
        or Path(str(dashboard_receipt.get("path") or "")).resolve() != dashboard_path
        or dashboard_receipt.get("url") != pair.get("dashboard_task_compare_url")
        or dashboard_receipt.get("external_browser_opened") is not True
        or dashboard_receipt.get("http_verified_before_open") is not True
        or dashboard_receipt.get("opened_before_model_processes") is not True
        or dashboard_receipt.get("dashboard_server_protocol")
        != DASHBOARD_SERVER_PROTOCOL
        or Path(str(dashboard_receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or isinstance(opened_monotonic_ns, bool)
        or not isinstance(opened_monotonic_ns, int)
        or opened_monotonic_ns <= 0
        or opened_monotonic_ns >= first_process_start
    ):
        raise ValueError(
            "Auto-selection live Task Compare receipt does not prove external "
            "pre-model opening of the paired dashboard."
        )
    dashboard_data = _read_json(dashboard_path.with_name("task_compare_data.json"))
    if (
        dashboard_data.get("arm_labels")
        != {
            "control": "Fresh non-learning control",
            "candidate": "SAGE auto selection",
        }
        or dashboard_data.get("scenario_count") != expected_tasks
    ):
        raise ValueError(
            "Auto-selection live Task Compare does not identify both concurrent arms."
        )
    return {
        "status": "pass",
        "control_run_dir": str(control_dir),
        "auto_run_dir": str(auto_dir),
        "scenario_count": expected_tasks,
        "scenario_order_sha256": observed_order_sha256,
        "parallel_arm_execution": parallel_execution,
        "outcomes": recomputed_outcomes,
        "outcome_comparison_path": str(outcome_comparison_path),
        "dashboard_open_receipt_path": str(dashboard_receipt_path),
    }


def verify_selector_pilot_evidence(evidence_path: Path) -> dict[str, Any]:
    """Revalidate a complete, same-source 30-task selector pilot artifact."""

    evidence_path = evidence_path.resolve()
    if evidence_path.name != "actor_selection_experiment_manifest.json":
        raise ValueError(
            "Selector pilot evidence must be actor_selection_experiment_manifest.json."
        )
    evidence = _read_json(evidence_path)
    current_outcome_evaluator = outcome_evaluator_manifest()
    expected_tasks, expected_benchmark_sha256, expected_order_sha256 = (
        publication_cohort_pins("pilot")
    )
    required_evidence = {
        "schema_version": 2,
        "experiment": "sage_auto_selection",
        "stage": "pilot",
        "status": "complete",
        "scenario_count": expected_tasks,
        "policy_generation_enabled": True,
        "auto_generation_enabled": False,
        "auto_evolution_source": "matched_policy_inventory_authority",
        "auto_parallel_arms": True,
        "auto_control_cache_mode": "off",
        "auto_control_source": "fresh",
        "auto_cached_control_tasks": 0,
        "auto_fresh_control_tasks": expected_tasks,
        "auto_control_cache_accessed": False,
        "auto_control_delivery": "not_connected",
        "auto_control_output_influences_inventory": False,
        "auto_control_output_influences_execution": False,
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "legacy_score_is_performance_gate": False,
        "mechanism_counts_are_performance_gates": False,
        "persistent_response_cache_reuse": False,
        "outcome_evidence_complete": True,
        "performance_gate_applied": False,
        "performance_gate_reason": "no_predeclared_selector_performance_threshold",
        "integrity_gate_passed": True,
        "integrity_gate_reasons": [],
        "experiment_passed": True,
        "stability_gate_passed": True,
        "stability_gate_reasons": [],
        "benchmark_manifest_sha256": expected_benchmark_sha256,
        "scenario_order_sha256": expected_order_sha256,
        "outcome_evaluator": current_outcome_evaluator,
    }
    for field, expected in required_evidence.items():
        if evidence.get(field) != expected:
            raise ValueError(
                f"Selector pilot evidence field {field!r} is "
                f"{evidence.get(field)!r}; expected {expected!r}."
            )

    run_root = evidence_path.parent.resolve()
    protocol_path = _resolve_declared_path(
        run_root,
        evidence.get("policy_protocol_manifest_path"),
        "policy_protocol_manifest_path",
        required_parent=run_root,
    )
    if (
        protocol_path != run_root / "protocol_manifest.json"
        or not protocol_path.is_file()
    ):
        raise ValueError(
            "Selector pilot evidence does not link its same-run protocol manifest."
        )
    protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if evidence.get("policy_protocol_manifest_sha256") != protocol_sha256:
        raise ValueError("Selector pilot policy protocol digest has drifted.")
    protocol = _read_json(protocol_path)
    if (
        protocol.get("candidate_actor_selection_mode") != "policy"
        or protocol.get("inventory_authority_mode") != "capture"
        or protocol.get("scenario_count") != expected_tasks
        or protocol.get("benchmark_manifest_sha256") != expected_benchmark_sha256
        or protocol.get("scenario_order_sha256") != expected_order_sha256
        or protocol.get("outcome_evaluator") != current_outcome_evaluator
        or protocol.get("timezone") != PUBLICATION_TIMEZONE
    ):
        raise ValueError(
            "Selector pilot policy protocol is not the pinned policy-authority donor."
        )

    current_source = _clean_source_identity(REPO_ROOT)
    source_identity = evidence.get("source_identity")
    if not isinstance(source_identity, dict) or any(
        source_identity.get(field) != current_source[field]
        for field in ("git_commit", "git_tree")
    ):
        raise ValueError(
            "Selector pilot evidence source does not match the current clean source."
        )

    policy_dir = _resolve_declared_path(
        run_root,
        evidence.get("policy_run_dir"),
        "policy_run_dir",
        required_parent=run_root / "candidate",
    )
    protocol_policy_dir = _resolve_declared_path(
        run_root,
        protocol.get("candidate_dir"),
        "candidate_dir",
        required_parent=run_root / "candidate",
    )
    if policy_dir != protocol_policy_dir or not policy_dir.is_dir():
        raise ValueError("Selector pilot policy run link does not match its protocol.")
    auto_dir = _resolve_declared_path(
        run_root,
        evidence.get("auto_run_dir"),
        "auto_run_dir",
        required_parent=run_root / "sage_auto_selection",
    )
    if not auto_dir.is_dir():
        raise ValueError("Selector pilot auto-selection run is missing.")
    _verify_run_manifest_timezone(policy_dir, arm="policy")
    _verify_run_manifest_timezone(auto_dir, arm="sage_auto_selection")
    pair_manifest_path = _resolve_declared_path(
        run_root,
        evidence.get("auto_parallel_pair_manifest_path"),
        "auto_parallel_pair_manifest_path",
        required_parent=run_root / "sage_auto_selection_parallel_pair",
    )
    if (
        not pair_manifest_path.is_file()
        or evidence.get("auto_parallel_pair_manifest_sha256")
        != hashlib.sha256(pair_manifest_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Selector pilot auto-selection pair manifest has drifted.")
    auto_parallel_verification = verify_auto_selection_parallel_pair(
        pair_manifest_path,
        run_root=run_root,
        expected_tasks=expected_tasks,
        expected_scenario_order_sha256=expected_order_sha256,
        expected_auto_dir=auto_dir,
    )
    auto_control_dir = _resolve_declared_path(
        run_root,
        evidence.get("auto_control_run_dir"),
        "auto_control_run_dir",
        required_parent=run_root / "sage_auto_selection_parallel_pair" / "control",
    )
    if (
        auto_control_dir
        != Path(str(auto_parallel_verification["control_run_dir"])).resolve()
        or evidence.get("auto_parallel_arm_execution")
        != auto_parallel_verification["parallel_arm_execution"]
    ):
        raise ValueError(
            "Selector pilot auto-selection concurrency evidence is inconsistent."
        )
    auto_control_outcome_path = _resolve_declared_path(
        run_root,
        evidence.get("auto_control_outcome_comparison_path"),
        "auto_control_outcome_comparison_path",
        required_parent=run_root / "sage_auto_selection_parallel_pair",
    )
    if (
        auto_control_outcome_path
        != Path(str(auto_parallel_verification["outcome_comparison_path"])).resolve()
        or evidence.get("auto_control_outcomes")
        != auto_parallel_verification["outcomes"]
    ):
        raise ValueError(
            "Selector pilot auto/control outcome evidence is inconsistent."
        )
    authority_path = _resolve_declared_path(
        run_root,
        evidence.get("inventory_authority_path"),
        "inventory_authority_path",
    )
    if not authority_path.is_file():
        raise ValueError("Selector pilot inventory authority is missing.")
    authority_sha256 = hashlib.sha256(authority_path.read_bytes()).hexdigest()
    if (
        evidence.get("inventory_authority_sha256") != authority_sha256
        or protocol.get("inventory_authority_manifest_sha256") != authority_sha256
        or evidence.get("inventory_authority_tasks_sha256")
        != protocol.get("inventory_authority_tasks_sha256")
    ):
        raise ValueError("Selector pilot inventory authority digest has drifted.")

    benchmark_path = _resolve_declared_path(
        run_root,
        evidence.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    protocol_benchmark_path = _resolve_declared_path(
        run_root,
        protocol.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    if (
        benchmark_path != protocol_benchmark_path
        or not benchmark_path.is_file()
        or hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
        != expected_benchmark_sha256
    ):
        raise ValueError("Selector pilot benchmark link or bytes have drifted.")

    comparison_path = _resolve_declared_path(
        run_root,
        evidence.get("outcome_comparison_path"),
        "outcome_comparison_path",
        required_parent=run_root,
    )
    if (
        comparison_path != run_root / "actor_selection_outcome_comparison.json"
        or not comparison_path.is_file()
    ):
        raise ValueError("Selector pilot outcome-comparison artifact is missing.")
    live_dashboard_receipt = _resolve_declared_path(
        run_root,
        evidence.get("live_auto_control_dashboard_open_receipt_path"),
        "live_auto_control_dashboard_open_receipt_path",
        required_parent=run_root / "sage_auto_selection_parallel_pair",
    )
    if (
        live_dashboard_receipt
        != Path(
            str(auto_parallel_verification["dashboard_open_receipt_path"])
        ).resolve()
    ):
        raise ValueError(
            "Selector pilot links a different live auto/control dashboard receipt."
        )
    policy_auto_dashboard_path = _resolve_declared_path(
        run_root,
        evidence.get("dashboard_task_compare_path"),
        "dashboard_task_compare_path",
        required_parent=run_root / "actor_selection_dashboard",
    )
    policy_auto_receipt_path = _resolve_declared_path(
        run_root,
        evidence.get("policy_auto_dashboard_open_receipt_path"),
        "policy_auto_dashboard_open_receipt_path",
        required_parent=run_root / "actor_selection_dashboard",
    )
    if (
        _resolve_declared_path(
            run_root,
            evidence.get("dashboard_open_receipt_path"),
            "dashboard_open_receipt_path",
            required_parent=run_root / "actor_selection_dashboard",
        )
        != policy_auto_receipt_path
    ):
        raise ValueError("Selector pilot policy/auto dashboard receipt is ambiguous.")
    policy_auto_receipt = _read_json(policy_auto_receipt_path)
    if (
        policy_auto_dashboard_path
        != run_root / "actor_selection_dashboard" / "dashboard" / "task_compare.html"
        or not policy_auto_dashboard_path.is_file()
        or policy_auto_receipt.get("dashboard") != "task_compare"
        or policy_auto_receipt.get("comparison") != "policy_vs_sage_auto_selection"
        or Path(str(policy_auto_receipt.get("path") or "")).resolve()
        != policy_auto_dashboard_path
        or policy_auto_receipt.get("url") != evidence.get("dashboard_task_compare_url")
        or policy_auto_receipt.get("external_browser_opened") is not True
        or policy_auto_receipt.get("http_verified_before_open") is not True
        or policy_auto_receipt.get("dashboard_server_protocol")
        != DASHBOARD_SERVER_PROTOCOL
        or Path(str(policy_auto_receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or policy_auto_receipt.get("opened_phase") != "post_run_causal_comparison"
    ):
        raise ValueError("Selector pilot policy/auto Task Compare receipt is invalid.")
    policy_auto_data = _read_json(
        policy_auto_dashboard_path.with_name("task_compare_data.json")
    )
    if (
        policy_auto_data.get("arm_labels")
        != {
            "control": "SAGE policy selection",
            "candidate": "SAGE auto selection",
        }
        or policy_auto_data.get("scenario_count") != expected_tasks
    ):
        raise ValueError(
            "Selector pilot policy/auto Task Compare does not identify both arms."
        )
    policy_auto_dashboard_outcomes = _verify_complete_outcome_dashboard(
        policy_auto_data,
        expected_tasks=expected_tasks,
    )
    status_path = run_root / "sage_auto_selection_arm_status.json"
    status = _read_json(status_path)
    status_run_dir = _resolve_declared_path(
        run_root,
        status.get("run_dir"),
        "sage_auto_selection_arm_status.run_dir",
        required_parent=run_root / "sage_auto_selection",
    )
    if (
        status.get("arm") != "sage_auto_selection"
        or status.get("status") != "complete"
        or status_run_dir != auto_dir
    ):
        raise ValueError("Selector pilot auto-selection completion status is invalid.")

    integrity = verify_pinned_run(
        run_root,
        cohort="pilot",
        expect_reflection="same-run-fresh",
    )
    if Path(str(integrity.get("run_root") or "")).resolve() != run_root:
        raise ValueError("Selector pilot publication verifier selected another run.")
    if integrity.get("outcome_evaluator") != current_outcome_evaluator:
        raise ValueError(
            "Selector pilot publication verification used another outcome evaluator."
        )

    from scripts.research.actor_selection_comparison import (
        verify_matched_actor_selection_experiment,
    )

    recomputed_comparison = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )
    stored_comparison = _read_json(comparison_path)
    if stored_comparison != recomputed_comparison:
        raise ValueError(
            "Selector pilot comparison does not match recomputed evidence."
        )
    if (
        recomputed_comparison.get("mechanism_counts_are_performance_gates") is not False
        or recomputed_comparison.get("outcome_evidence_complete") is not True
        or recomputed_comparison.get("performance_gate_applied") is not False
        or recomputed_comparison.get("performance_gate_reason")
        != "no_predeclared_selector_performance_threshold"
        or recomputed_comparison.get("integrity_gate_passed") is not True
        or recomputed_comparison.get("integrity_gate_reasons") != []
        or recomputed_comparison.get("experiment_passed") is not True
        or recomputed_comparison.get("stability_gate_passed") is not True
        or recomputed_comparison.get("stability_gate_reasons") != []
        or recomputed_comparison.get("scenario_count") != expected_tasks
        or recomputed_comparison.get("outcome_evaluator") != current_outcome_evaluator
    ):
        raise ValueError(
            "Selector pilot integrity or complete outcome evidence did not pass "
            "revalidation."
        )
    recomputed_outcomes = recomputed_comparison.get("outcomes")
    if not isinstance(recomputed_outcomes, dict):
        raise ValueError("Selector pilot comparison has no outcome summary.")
    expected_dashboard_outcomes = {
        "control_mean": recomputed_outcomes.get("policy_mean_outcome_similarity"),
        "candidate_mean": recomputed_outcomes.get("auto_mean_outcome_similarity"),
        "outcome_delta": recomputed_outcomes.get(
            "auto_minus_policy_mean_outcome_delta"
        ),
        "control_exact_successes": recomputed_outcomes.get(
            "policy_exact_outcome_successes"
        ),
        "candidate_exact_successes": recomputed_outcomes.get(
            "auto_exact_outcome_successes"
        ),
    }
    for field, expected in expected_dashboard_outcomes.items():
        observed = policy_auto_dashboard_outcomes[field]
        if isinstance(observed, float):
            if (
                isinstance(expected, bool)
                or not isinstance(expected, (int, float))
                or not math.isfinite(float(expected))
                or not math.isclose(
                    observed, float(expected), rel_tol=0.0, abs_tol=1e-12
                )
            ):
                raise ValueError(
                    "Selector pilot dashboard outcomes do not match the "
                    "recomputed comparison."
                )
        elif observed != expected:
            raise ValueError(
                "Selector pilot dashboard outcomes do not match the recomputed "
                "comparison."
            )

    return {
        "status": "pass",
        "stage": "pilot",
        "scenario_count": expected_tasks,
        "evidence_path": str(evidence_path),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "policy_protocol_manifest_sha256": protocol_sha256,
        "inventory_authority_sha256": authority_sha256,
        "inventory_authority_tasks_sha256": evidence.get(
            "inventory_authority_tasks_sha256"
        ),
        "benchmark_manifest_sha256": expected_benchmark_sha256,
        "scenario_order_sha256": expected_order_sha256,
        "outcome_evaluator": current_outcome_evaluator,
        "timezone": PUBLICATION_TIMEZONE,
        "git_commit": current_source["git_commit"],
        "git_tree": current_source["git_tree"],
        "outcome_evidence_complete": True,
        "performance_gate_applied": False,
        "integrity_gate_passed": True,
        "experiment_passed": True,
        "stability_gate_passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path)
    parser.add_argument(
        "--cohort",
        choices=tuple(sorted(PUBLICATION_COHORT_PINS)),
        default="full",
        help="Internally pinned publication cohort (default: full).",
    )
    parser.add_argument(
        "--selector-pilot-evidence",
        type=Path,
        help=(
            "Revalidate a completed pinned selector pilot manifest instead of a "
            "new publication run."
        ),
    )
    parser.add_argument(
        "--expect-reflection",
        choices=("same-run-fresh", "not-applicable"),
    )
    args = parser.parse_args()
    verification_label = (
        "selector_pilot_evidence_verification"
        if args.selector_pilot_evidence is not None
        else "publication_run_verification"
    )
    try:
        if args.selector_pilot_evidence is not None:
            if args.search_root is not None or args.expect_reflection is not None:
                parser.error(
                    "--selector-pilot-evidence cannot be combined with "
                    "--search-root or --expect-reflection"
                )
            result = verify_selector_pilot_evidence(args.selector_pilot_evidence)
        else:
            if args.search_root is None or args.expect_reflection is None:
                parser.error(
                    "--search-root and --expect-reflection are required for run "
                    "verification"
                )
            result = verify_pinned_run(
                args.search_root,
                cohort=args.cohort,
                expect_reflection=args.expect_reflection,
            )
    except ValueError as exc:
        raise SystemExit(f"{verification_label}=failed\n{exc}") from exc
    print(f"{verification_label}=pass")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
