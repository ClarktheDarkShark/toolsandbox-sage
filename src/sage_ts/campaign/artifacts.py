"""Structured campaign artifacts for live dashboards and handoff."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sage_ts.config.models import DEFAULT_MODEL

ARTIFACT_ROOT = Path("artifacts")
EVENT_TYPES = {
    "campaign_started",
    "phase_started",
    "phase_completed",
    "subtask_started",
    "subtask_completed",
    "run_started",
    "run_stopped_early",
    "scenario_started",
    "scenario_finished",
    "scenario_transform_failed",
    "inadequacy_detected",
    "proactive_inadequacy_detected",
    "proactive_manifest_reflection_completed",
    "proactive_manifest_reflection_skipped",
    "jit_proactive_inadequacy_detected",
    "jit_proactive_scenario_reflection_completed",
    "jit_proactive_action_tool_ready",
    "jit_proactive_birth_stopped_after_action_tool",
    "jit_birth_tools_available_for_same_task",
    "tool_birth_started",
    "tool_generation_completed",
    "tool_generation_failed",
    "tool_birth_succeeded",
    "tool_birth_rejected",
    "tool_repair_started",
    "tool_repair_attempted",
    "tool_repair_failed",
    "tool_birth_skipped_existing",
    "tool_birth_skipped_existing_broader_helper",
    "tool_birth_skipped_decomposed_complex_contract",
    "validation_started",
    "validation_passed",
    "validation_failed",
    "registry_loaded",
    "registry_saved",
    "tool_reused",
    "tool_runtime_suppressed",
    "self_evolution_stop_recommended",
    "consolidation_started",
    "consolidation_completed",
    "gate_passed",
    "gate_failed",
    "branch_kept",
    "branch_reverted",
    "blocker_detected",
}

DEFAULT_TASKS = [
    ("freeze_current_proof", "completed"),
    ("build_command_surface", "in_progress"),
    ("expand_live_dashboard", "in_progress"),
    ("reproduce_clean_recency_birth", "pending"),
    ("frozen_registry_transfer", "pending"),
    ("second_tool_class_state_precondition", "pending"),
    ("third_tool_class_search_filter", "pending"),
    ("registry_consolidation", "pending"),
    ("broad_validation", "pending"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except subprocess.CalledProcessError:
        return None


def artifact_root(root: Path | None = None) -> Path:
    return root or ARTIFACT_ROOT


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A live dashboard can read between an append opening and its final
            # newline. Ignore only that incomplete tail; a malformed committed
            # line remains an error so preserved evidence cannot be hidden.
            if index == len(lines) - 1 and not text.endswith("\n"):
                break
            raise
    return rows


def _append_bytes(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o666,
    )
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError(f"Could not append campaign event to {path}")
            remaining = remaining[written:]
    finally:
        os.close(descriptor)


def append_event(
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    if event not in EVENT_TYPES:
        raise ValueError(f"Unknown campaign event type: {event}")
    base = artifact_root(root)
    event_dir = base / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "event": event,
        "timestamp": utc_now(),
        "git_sha": git_value("rev-parse", "HEAD"),
        "branch": git_value("branch", "--show-current"),
        **(payload or {}),
    }
    line = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
    date_path = event_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    latest_path = event_dir / "latest.jsonl"
    # Both model-arm processes append to this shared event stream. One advisory
    # lock plus unbuffered O_APPEND writes prevents record interleaving and keeps
    # the dated and latest streams in the same order, even after a short write.
    lock_path = event_dir / ".append.lock"
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            _append_bytes(date_path, line)
            _append_bytes(latest_path, line)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return row


def initialize_campaign(
    *,
    root: Path | None = None,
    phase: str = "harness",
    status: str = "active",
    dashboard_path: str | None = None,
) -> Path:
    base = artifact_root(root)
    for child in ("events", "registries", "summaries"):
        (base / child).mkdir(parents=True, exist_ok=True)
    status_path = base / "campaign_status.json"
    prior = read_json(status_path)
    payload = {
        "campaign": "toolsandbox_sage_tool_evolution",
        "status": status,
        "phase": phase,
        "branch": git_value("branch", "--show-current"),
        "git_sha": git_value("rev-parse", "HEAD"),
        "model": DEFAULT_MODEL,
        "benchmark": "ToolSandbox",
        "base_toolset": "unmodified upstream ToolSandbox visibility",
        "generation_settings": {
            "enabled_for": ["mechanism_40", "extended_reuse_100"],
            "recurrence_threshold": 2,
            "allowed_tool_classes": [
                "derived_value_calculator",
                "state_precondition_helper",
                "search_filter_ranking_helper",
                "canonicalizer",
                "validation_abstention_helper",
            ],
        },
        "registry_path": prior.get("registry_path"),
        "validation_settings": {
            "requires_schema_validation": True,
            "requires_deterministic_tests": True,
            "requires_toolsandbox_runtime_smoke": True,
        },
        "dashboard_path": dashboard_path or prior.get("dashboard_path"),
        "ladder": {
            "mechanism": "current proof exists; clean reproduction pending",
            "frozen_transfer": "pending",
            "category_confirmation": "pending",
            "broad_validation": "pending",
        },
        "milestones": {
            "accepted_tool_classes": 1,
            "target_tool_classes": 3,
            "challenge_categories": ["CANONICALIZATION"],
            "target_challenge_category_count": 2,
            "dashboard_live": True,
        },
        "current_blocker": "Need reproducible clean-start proof, frozen transfer proof, then second/third retained tool classes.",
        "next_action": "Run clean mechanism40 reproduction with dashboard and campaign artifacts.",
        "updated_at": utc_now(),
    }
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_task_plan(root=base)
    append_event("campaign_started", {"phase": phase}, root=base)
    return status_path


def write_task_plan(*, root: Path | None = None) -> Path:
    base = artifact_root(root)
    path = base / "task_plan.json"
    prior = read_json(path)
    tasks = prior.get("tasks") or [
        {"task": task, "status": status} for task, status in DEFAULT_TASKS
    ]
    payload = {"updated_at": utc_now(), "tasks": tasks}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def update_task(task: str, status: str, *, root: Path | None = None) -> None:
    base = artifact_root(root)
    path = write_task_plan(root=base)
    payload = read_json(path)
    tasks = list(payload.get("tasks", []))
    found = False
    for row in tasks:
        if row.get("task") == task:
            row["status"] = status
            found = True
    if not found:
        tasks.append({"task": task, "status": status})
    payload["tasks"] = tasks
    payload["updated_at"] = utc_now()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def record_run(run: dict[str, Any], *, root: Path | None = None) -> Path:
    base = artifact_root(root)
    path = base / "run_index.json"
    payload = read_json(path, {"runs": []})
    runs = [
        row
        for row in payload.get("runs", [])
        if row.get("run_root") != run.get("run_root")
    ]
    runs.append({"updated_at": utc_now(), **run})
    payload["runs"] = runs[-100:]
    payload["updated_at"] = utc_now()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def snapshot_registry(
    registry_dir: Path, *, name: str, root: Path | None = None
) -> Path | None:
    source = registry_dir / "registry_manifest.json"
    if not source.exists():
        return None
    base = artifact_root(root)
    out = base / "registries" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return out
