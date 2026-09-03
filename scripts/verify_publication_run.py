#!/usr/bin/env python3
"""Fail closed unless a completed publication run is entirely fresh and paired."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PINNED_RAPID_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)
PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256 = (
    "5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f"
)
PUBLICATION_ENVIRONMENT_LOCK = "requirements-publication-lock.txt"
PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP = 1784832588
PUBLICATION_MODEL = "gpt-4o-mini"
PUBLICATION_EXECUTION_ENV = {
    "SAGE_OPENAI_MAX_RETRIES": "5",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}
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
_PUBLICATION_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _uncached_rows(
    run_dir: Path,
    *,
    expected_tasks: int,
    arm: str,
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, int]]:
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
        if row.get("control_score") != control.get("similarity"):
            raise ValueError(f"Reflection control score mismatch for {name!r}.")
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
        "parallel_arms": False,
    }
    for field, expected in required_protocol.items():
        if protocol.get(field) != expected:
            raise ValueError(
                f"Protocol field {field!r} is {protocol.get(field)!r}; "
                f"expected {expected!r}."
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
        "publication_provenance": publication_provenance,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--expected-tasks", type=int, default=1032)
    parser.add_argument(
        "--expect-reflection",
        choices=("same-run-fresh", "not-applicable"),
        required=True,
    )
    args = parser.parse_args()
    try:
        result = verify_run(
            args.search_root,
            expected_tasks=args.expected_tasks,
            expect_reflection=args.expect_reflection,
        )
    except ValueError as exc:
        raise SystemExit(f"publication_run_verification=failed\n{exc}") from exc
    print("publication_run_verification=pass")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
