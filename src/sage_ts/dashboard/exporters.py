"""Dashboard data exporters for ToolSandbox SAGE protocol runs."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from sage_ts.campaign.artifacts import ARTIFACT_ROOT, read_jsonl
from sage_ts.dashboard.server import (
    DASHBOARD_SERVER_IDENTITY_PATH,
    DASHBOARD_SERVER_PROTOCOL,
)
from sage_ts.dashboard.task_compare_template import TASK_COMPARE_HTML
from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return default or {}
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError:
        return default or {}


def _read_json_value(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return default
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
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
            # Live result streams are append-only. A dashboard read may catch
            # the final append before its newline, but must never hide a corrupt
            # completed record in the middle of the evidence file.
            if index == len(lines) - 1 and not text.endswith("\n"):
                break
            raise
    return rows


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _campaign_payload(root: Path) -> dict[str, Any]:
    return {
        "status": _read_json(root / "campaign_status.json"),
        "task_plan": _read_json(root / "task_plan.json"),
        "run_index": _read_json(root / "run_index.json", {"runs": []}),
        "events": read_jsonl(root / "events" / "latest.jsonl")[-80:],
        "registry_snapshots": [
            str(path) for path in sorted((root / "registries").glob("*.json"))
        ]
        if (root / "registries").exists()
        else [],
    }


def _looks_like_run_dir(path: Path) -> bool:
    return any(
        candidate.exists()
        for candidate in (
            path / "result_summary.json",
            path / "live_result_summary.json",
            path / "trajectories",
        )
    )


def _resolve_run_dir(run_dir: Path | None) -> Path | None:
    if run_dir is None or not run_dir.exists():
        return None
    if run_dir.is_file():
        if run_dir.name in {
            "result_summary.json",
            "live_result_summary.json",
            "sage_ts_run_manifest.json",
        }:
            run_dir = run_dir.parent
        else:
            return None
    if _looks_like_run_dir(run_dir):
        return run_dir
    candidates = [
        path
        for path in run_dir.iterdir()
        if path.is_dir() and _looks_like_run_dir(path)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _scenario_rows(run_dir: Path | None) -> list[dict[str, Any]]:
    run_dir = _resolve_run_dir(run_dir)
    if run_dir is None:
        return []
    summary = run_dir / "result_summary.json"
    live = run_dir / "live_result_summary.json"
    data = _read_json(summary if summary.exists() else live)
    return list(data.get("per_scenario_results", []))


def _trace_url(dashboard_dir: Path, run_dir: Path | None, scenario: str) -> str | None:
    run_dir = _resolve_run_dir(run_dir)
    if run_dir is None:
        return None
    pretty = run_dir / "trajectories" / scenario / "pretty_print.txt"
    if not pretty.exists():
        return None
    return os.path.relpath(pretty, dashboard_dir)


def _manifest_order(run_dir: Path) -> dict[str, int]:
    run_dir = _resolve_run_dir(run_dir) or run_dir
    manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    names = manifest.get("scenario_names") or []
    return {str(name): index for index, name in enumerate(names)}


def _generated_tool_usage(run_dir: Path) -> dict[str, list[str]]:
    run_dir = _resolve_run_dir(run_dir) or run_dir
    usage: dict[str, list[str]] = {}
    for event in _read_jsonl(run_dir / "reuse_events.jsonl"):
        scenario = event.get("scenario")
        tool = event.get("tool_name")
        if not scenario or not tool:
            continue
        tools = usage.setdefault(str(scenario), [])
        if str(tool) not in tools:
            tools.append(str(tool))
    return usage


def _add_tool_event(
    events: dict[str, list[dict[str, str]]],
    scenario: Any,
    tool: Any,
    kind: str,
) -> None:
    if not scenario or not tool:
        return
    scenario_key = str(scenario)
    tool_name = str(tool)
    row = {"kind": kind, "tool": tool_name}
    rows = events.setdefault(scenario_key, [])
    if row not in rows:
        rows.append(row)


def _generated_tool_events(
    run_root: Path,
    run_dir: Path,
) -> dict[str, list[dict[str, str]]]:
    run_dir = _resolve_run_dir(run_dir) or run_dir
    events: dict[str, list[dict[str, str]]] = {}
    for event in _read_jsonl(run_dir / "reuse_events.jsonl"):
        _add_tool_event(events, event.get("scenario"), event.get("tool_name"), "called")
    for event in _read_jsonl(run_dir / "sage_run_events.jsonl"):
        event_name = str(event.get("event") or "")
        if event_name == "registry_save":
            _add_tool_event(
                events,
                event.get("birth_scenario"),
                event.get("tool_name"),
                "born",
            )
        elif event_name == "tool_birth_heuristic_unverified":
            _add_tool_event(
                events,
                event.get("scenario"),
                event.get("canonical_key"),
                "observed",
            )

    contribution = _read_json(run_root / "helper_contribution_summary.json")
    helpers = contribution.get("helpers") if isinstance(contribution, dict) else {}
    if isinstance(helpers, dict):
        for name, raw in helpers.items():
            if not isinstance(raw, dict):
                continue
            for scenario in raw.get("visible_scenarios") or []:
                _add_tool_event(events, scenario, name, "visible")
            for scenario in raw.get("called_scenarios") or []:
                _add_tool_event(events, scenario, name, "called")

    priority = {"born": 0, "called": 1, "visible": 2, "observed": 3}
    return {
        scenario: sorted(
            rows,
            key=lambda row: (priority.get(row.get("kind", ""), 9), row.get("tool", "")),
        )
        for scenario, rows in events.items()
    }


def _dashboard_load_task_messages() -> bool:
    return os.environ.get(
        "SAGE_DASHBOARD_LOAD_TASK_MESSAGES", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}


def _compact_content(value: Any, *, limit: int = 10000) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


def _message_label(message: dict[str, Any]) -> str:
    role = str(message.get("role", "message"))
    if role == "tool":
        return f"tool: {message.get('name', 'unknown')}"
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        names = [
            call.get("function", {}).get("name", "tool")
            for call in tool_calls
            if isinstance(call, dict)
        ]
        return f"assistant tool call: {', '.join(names)}"
    return role


def _serialize_message(
    index: int,
    message: dict[str, Any],
    generated_tools: set[str],
) -> dict[str, Any]:
    tool_calls = message.get("tool_calls") or []
    call_text = "\n\n".join(
        (
            f"{call.get('function', {}).get('name', 'tool')}("
            f"{call.get('function', {}).get('arguments', '')})"
        )
        for call in tool_calls
        if isinstance(call, dict)
    )
    content = _compact_content(message.get("content"))
    if call_text:
        content = call_text if not content else f"{content}\n\n{call_text}"
    haystack = " ".join(
        [str(message.get("name", "")), _message_label(message), content, call_text]
    )
    used = sorted(tool for tool in generated_tools if tool and tool in haystack)
    return {
        "index": index,
        "role": message.get("role", "message"),
        "name": message.get("name"),
        "label": _message_label(message),
        "content": content,
        "generated_tools": used,
        "uses_generated_tool": bool(used),
    }


def _task_compare_rows(
    run_root: Path,
    run_dir: Path | None,
    *,
    phase: Literal["control", "candidate"],
) -> list[dict[str, Any]]:
    run_dir = _resolve_run_dir(run_dir)
    if run_dir is None:
        return []
    rows = {
        str(row.get("name")): row
        for row in _scenario_rows(run_dir)
        if isinstance(row, dict) and row.get("name")
    }
    order = _manifest_order(run_dir)
    usage = _generated_tool_usage(run_dir)
    tool_events = _generated_tool_events(run_root, run_dir)
    trajectory_dir = run_dir / "trajectories"
    trajectory_names = (
        {path.name for path in trajectory_dir.iterdir() if path.is_dir()}
        if trajectory_dir.exists()
        else set()
    )
    currently_running_data = _read_json(run_dir / "currently_running.json")
    active_scenario_name = (
        currently_running_data.get("scenario") if currently_running_data else None
    )
    load_messages = _dashboard_load_task_messages()
    phantom: set[str] = (
        {active_scenario_name}
        if active_scenario_name
        and active_scenario_name not in set(rows) | trajectory_names
        else set()
    )
    tasks: list[dict[str, Any]] = []
    for scenario in sorted(
        set(rows) | trajectory_names | phantom,
        key=lambda name: (order.get(name, 10_000), name),
    ):
        result = rows.get(scenario)
        conversation = (
            _read_json_value(
                run_dir / "trajectories" / scenario / "conversation.json", []
            )
            if load_messages
            else []
        )
        raw_messages = [m for m in conversation if isinstance(m, dict)]
        generated_tools = usage.get(scenario, [])
        generated_events = tool_events.get(scenario, [])
        generated_set = set(generated_tools) | {
            str(event.get("tool"))
            for event in generated_events
            if event.get("kind") == "called" and event.get("tool")
        }
        tasks.append(
            {
                "id": f"{phase}:{run_dir.name}:{scenario}",
                "phase": phase,
                "run_type": run_dir.name,
                "scenario": scenario,
                "short_name": scenario.replace("_", " "),
                "status": "complete"
                if result
                else "running"
                if (scenario in trajectory_names or scenario == active_scenario_name)
                else "pending",
                "order_index": order.get(scenario),
                "display_index": None
                if order.get(scenario) is None
                else int(order[scenario]) + 1,
                "generated_tools": generated_tools,
                "generated_tool_events": generated_events,
                "outcome_similarity": None
                if result is None
                else result.get("outcome_similarity"),
                "outcome_milestone_similarity": None
                if result is None
                else result.get("outcome_milestone_similarity"),
                "outcome_check_count": None
                if result is None
                else result.get("outcome_check_count"),
                "outcome_checks": []
                if result is None
                else result.get("outcome_checks", []),
                "turn_count": None if result is None else result.get("turn_count"),
                "llm_usage_recorded": False
                if result is None
                else bool(result.get("llm_usage_recorded")),
                "llm_call_count": None
                if result is None
                else result.get("llm_call_count"),
                "llm_live_call_count": None
                if result is None
                else result.get("llm_live_call_count"),
                "llm_cached_call_count": None
                if result is None
                else result.get("llm_cached_call_count"),
                "llm_prompt_tokens": None
                if result is None
                else result.get("llm_prompt_tokens"),
                "llm_provider_cached_prompt_tokens": None
                if result is None
                else result.get("llm_provider_cached_prompt_tokens"),
                "llm_provider_cached_prompt_call_count": None
                if result is None
                else result.get("llm_provider_cached_prompt_call_count"),
                "llm_provider_cached_prompt_tokens_available_count": None
                if result is None
                else result.get("llm_provider_cached_prompt_tokens_available_count"),
                "llm_completion_tokens": None
                if result is None
                else result.get("llm_completion_tokens"),
                "llm_total_tokens": None
                if result is None
                else result.get("llm_total_tokens"),
                "llm_usage_available_count": None
                if result is None
                else result.get("llm_usage_available_count"),
                "llm_usage_by_source": {}
                if result is None
                else result.get("llm_usage_by_source", {}),
                "exception_type": None
                if result is None
                else result.get("exception_type"),
                "categories": [] if result is None else result.get("categories", []),
                "message_count": len(raw_messages),
                "messages": [
                    _serialize_message(index, message, generated_set)
                    for index, message in enumerate(raw_messages)
                ],
            }
        )
    return tasks


def _arm_progress_status(
    run_root: Path,
    arm: str,
    summary: dict[str, Any],
    scenario_count: Any,
) -> dict[str, Any]:
    """Return explicit arm progress for live paired dashboards.

    Task Compare shows baseline and SAGE progress separately. During active
    runs, the runner writes arm status files before a
    final result summary exists; after completion, the summary is the fallback.
    """
    status_path = run_root / f"{arm}_arm_status.json"
    status = _read_json(status_path)
    planned = status.get("scenario_count")
    if planned is None:
        planned = scenario_count
    if planned is None:
        planned = summary.get("planned_scenario_count")
    completed = status.get("completed_count")
    if completed is None:
        completed = summary.get("scenario_count")
    return {
        "arm": arm,
        "status": status.get("status")
        or summary.get("run_status")
        or ("complete" if summary.get("scenario_count") else "pending"),
        "completed_count": int(completed or 0),
        "scenario_count": int(planned or 0),
        "run_dir": status.get("run_dir") or summary.get("run_dir"),
        "updated_at": status.get("updated_at"),
        "error": status.get("error"),
    }


def _balanced_pair_summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    complete_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for pair in pairs:
        control = pair.get("control")
        candidate = pair.get("candidate")
        if not isinstance(control, dict) or not isinstance(candidate, dict):
            continue
        if control.get("status") != "complete" or candidate.get("status") != "complete":
            continue
        complete_pairs.append((control, candidate))

    def mean_value(
        side: int,
        key: str,
    ) -> float | None:
        values: list[float] = []
        for pair in complete_pairs:
            value = pair[side].get(key)
            if value is not None:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
        return sum(values) / len(values) if values else None

    control_outcome_mean = mean_value(0, "outcome_similarity")
    candidate_outcome_mean = mean_value(1, "outcome_similarity")
    outcome_delta = (
        candidate_outcome_mean - control_outcome_mean
        if control_outcome_mean is not None and candidate_outcome_mean is not None
        else None
    )
    return {
        "balanced_completed": len(complete_pairs),
        "balanced_control_mean_outcome_similarity": control_outcome_mean,
        "balanced_candidate_mean_outcome_similarity": candidate_outcome_mean,
        "balanced_outcome_delta": outcome_delta,
    }


def _task_compare_payload(
    dashboard_dir: Path,
    run_root: Path,
    data: dict[str, Any],
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> dict[str, Any]:
    control_tasks = _task_compare_rows(
        run_root,
        control_dir,
        phase="control",
    )
    candidate_tasks = _task_compare_rows(
        run_root,
        candidate_dir,
        phase="candidate",
    )
    tasks = [*control_tasks, *candidate_tasks]
    pair_lookup: dict[str, dict[str, Any]] = {}
    for task in tasks:
        scenario = str(task.get("scenario") or "")
        if not scenario:
            continue
        pair = pair_lookup.setdefault(
            scenario,
            {
                "id": f"pair:{scenario}",
                "scenario": scenario,
                "short_name": str(task.get("short_name") or scenario),
                "order_index": task.get("order_index"),
                "display_index": task.get("display_index"),
                "control": None,
                "candidate": None,
            },
        )
        phase = str(task.get("phase") or "")
        if phase in {"control", "candidate"}:
            pair[phase] = task
        if pair.get("order_index") is None and task.get("order_index") is not None:
            pair["order_index"] = task.get("order_index")
            pair["display_index"] = task.get("display_index")
    pairs = sorted(
        pair_lookup.values(),
        key=lambda pair: (
            10_000 if pair.get("order_index") is None else pair["order_index"],
            str(pair.get("scenario") or ""),
        ),
    )
    active = next(
        (task for task in reversed(tasks) if task["status"] != "complete"), None
    )
    if active is None and tasks:
        active = tasks[-1]
    current = data.get("candidate") or data.get("control") or {}
    control_summary = data.get("control", {})
    candidate_summary = data.get("candidate", {})
    balanced_summary = _balanced_pair_summary(pairs)
    control_arm_status = _arm_progress_status(
        run_root,
        "control",
        control_summary,
        data.get("scenario_count"),
    )
    candidate_arm_status = _arm_progress_status(
        run_root,
        "candidate",
        candidate_summary,
        data.get("scenario_count"),
    )
    payload = {
        "started_at": data.get("started_at"),
        "updated_at": data.get("updated_at"),
        "run_root": str(run_root),
        "mode": data.get("mode"),
        "phase": data.get("phase"),
        "status": data.get("status"),
        "agent": data.get("agent"),
        "base_tool_policy": data.get("base_tool_policy"),
        "arm_labels": data.get("arm_labels"),
        "scenario_count": data.get("scenario_count"),
        "cohort_preflight": data.get("cohort_preflight"),
        "summary": {
            "scenario_count": data.get("scenario_count"),
            "control_completed": data.get("control", {}).get("scenario_count"),
            "control_mean_outcome_similarity": data.get("control", {}).get(
                "mean_outcome_similarity"
            ),
            "control_llm_usage_recorded": data.get("control", {}).get(
                "llm_usage_recorded"
            ),
            "control_llm_call_count": data.get("control", {}).get("llm_call_count"),
            "control_llm_live_call_count": data.get("control", {}).get(
                "llm_live_call_count"
            ),
            "control_llm_cached_call_count": data.get("control", {}).get(
                "llm_cached_call_count"
            ),
            "control_llm_prompt_tokens": data.get("control", {}).get(
                "llm_prompt_tokens"
            ),
            "control_llm_provider_cached_prompt_tokens": data.get("control", {}).get(
                "llm_provider_cached_prompt_tokens"
            ),
            "control_llm_provider_cached_prompt_call_count": data.get(
                "control", {}
            ).get("llm_provider_cached_prompt_call_count"),
            "control_llm_provider_cached_prompt_tokens_available_count": data.get(
                "control", {}
            ).get("llm_provider_cached_prompt_tokens_available_count"),
            "control_llm_completion_tokens": data.get("control", {}).get(
                "llm_completion_tokens"
            ),
            "control_llm_total_tokens": data.get("control", {}).get("llm_total_tokens"),
            "control_llm_usage_available_count": data.get("control", {}).get(
                "llm_usage_available_count"
            ),
            "control_wall_time_seconds": data.get("control", {}).get(
                "wall_time_seconds"
            ),
            "control_wall_time_resume_offset_seconds": data.get("control", {}).get(
                "wall_time_resume_offset_seconds"
            ),
            "candidate_completed": data.get("candidate", {}).get("scenario_count"),
            "candidate_mean_outcome_similarity": data.get("candidate", {}).get(
                "mean_outcome_similarity"
            ),
            "candidate_llm_usage_recorded": data.get("candidate", {}).get(
                "llm_usage_recorded"
            ),
            "candidate_llm_call_count": data.get("candidate", {}).get("llm_call_count"),
            "candidate_llm_live_call_count": data.get("candidate", {}).get(
                "llm_live_call_count"
            ),
            "candidate_llm_cached_call_count": data.get("candidate", {}).get(
                "llm_cached_call_count"
            ),
            "candidate_llm_prompt_tokens": data.get("candidate", {}).get(
                "llm_prompt_tokens"
            ),
            "candidate_llm_provider_cached_prompt_tokens": data.get(
                "candidate", {}
            ).get("llm_provider_cached_prompt_tokens"),
            "candidate_llm_provider_cached_prompt_call_count": data.get(
                "candidate", {}
            ).get("llm_provider_cached_prompt_call_count"),
            "candidate_llm_provider_cached_prompt_tokens_available_count": data.get(
                "candidate", {}
            ).get("llm_provider_cached_prompt_tokens_available_count"),
            "candidate_llm_completion_tokens": data.get("candidate", {}).get(
                "llm_completion_tokens"
            ),
            "candidate_llm_total_tokens": data.get("candidate", {}).get(
                "llm_total_tokens"
            ),
            "candidate_llm_usage_available_count": data.get("candidate", {}).get(
                "llm_usage_available_count"
            ),
            "candidate_wall_time_seconds": data.get("candidate", {}).get(
                "wall_time_seconds"
            ),
            "candidate_wall_time_resume_offset_seconds": data.get("candidate", {}).get(
                "wall_time_resume_offset_seconds"
            ),
            "accepted_tools": current.get("accepted_tool_count", 0),
            "reuse_count": current.get("reuse_count", 0),
            "generated_tool_attempted_scenarios": current.get(
                "generated_tool_attempted_scenarios", 0
            ),
            "generated_tool_called_scenarios": current.get(
                "generated_tool_called_scenarios", 0
            ),
            "generated_tool_failed_scenarios": current.get(
                "generated_tool_failed_scenarios", 0
            ),
            "current_completed": current.get("scenario_count"),
            "current_turns": current.get("total_turns"),
            "current_exceptions": current.get("exception_count"),
            **balanced_summary,
        },
        "arm_progress": {
            "control": control_arm_status,
            "candidate": candidate_arm_status,
        },
        "active_task_id": None if active is None else active["id"],
        "tasks": tasks,
        "pairs": pairs,
    }
    return payload


def _count_incidents(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return value
    return 0


def _tool_count(row: dict[str, Any], count_key: str, list_key: str) -> int:
    count = row.get(count_key)
    if isinstance(count, int):
        return count
    values = row.get(list_key)
    if isinstance(values, list):
        return len(values)
    return 0


def _named_entry_count(value: Any) -> int:
    if isinstance(value, dict):
        return len([name for name in value if name])
    if isinstance(value, list):
        return len({str(name) for name in value if name})
    return 0


def _mean_float(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _candidate_run_dir_from_data(data: dict[str, Any]) -> Path | None:
    candidate = data.get("candidate")
    if not isinstance(candidate, dict):
        return None
    raw = candidate.get("run_dir")
    if not raw:
        return None
    return _resolve_run_dir(Path(str(raw)))


def _add_tool_scenario(
    mapping: dict[str, set[str]],
    tool: Any,
    scenario: str,
) -> None:
    if not scenario or not tool:
        return
    mapping.setdefault(str(tool), set()).add(scenario)


def _live_tool_selection_counts(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    run_dir = _candidate_run_dir_from_data(data)
    if run_dir is None:
        return {}
    visible_by_tool: dict[str, set[str]] = {}
    called_by_tool: dict[str, set[str]] = {}
    failed_by_tool: dict[str, set[str]] = {}
    attempted_by_tool: dict[str, set[str]] = {}

    visibility_rows = _read_jsonl(run_dir / "scenario_tool_visibility.jsonl")
    for row in visibility_rows:
        scenario = str(row.get("scenario") or "")
        for tool in row.get("generated_tools", []) or []:
            _add_tool_scenario(visible_by_tool, tool, scenario)

    selection_rows = _read_jsonl(run_dir / "scenario_tool_selection.jsonl")
    for row in selection_rows:
        scenario = str(row.get("scenario") or "")
        for tool in row.get("generated_tools_visible", []) or []:
            _add_tool_scenario(visible_by_tool, tool, scenario)
        for tool in row.get("generated_tools_called", []) or []:
            _add_tool_scenario(called_by_tool, tool, scenario)
        for tool in row.get("generated_tools_failed", []) or []:
            _add_tool_scenario(failed_by_tool, tool, scenario)
        for tool in row.get("generated_tools_attempted", []) or []:
            _add_tool_scenario(attempted_by_tool, tool, scenario)

    for event in data.get("reuse_events", []) or []:
        scenario = str(event.get("scenario") or "")
        tool = event.get("tool_name") or event.get("tool")
        _add_tool_scenario(called_by_tool, tool, scenario)

    tool_names = (
        set(visible_by_tool)
        | set(called_by_tool)
        | set(failed_by_tool)
        | set(attempted_by_tool)
    )
    counts: dict[str, dict[str, Any]] = {}
    for tool in sorted(tool_names):
        visible = visible_by_tool.get(tool, set())
        called = called_by_tool.get(tool, set())
        failed = failed_by_tool.get(tool, set())
        attempted = attempted_by_tool.get(tool, set())
        counts[tool] = {
            "visible_count": len(visible),
            "called_scenario_count": len(called),
            "visible_not_called_count": len(visible - called),
            "failed_attempt_count": len(failed),
            "attempted_scenario_count": len(attempted),
        }
    return counts


def _live_called_tool_delta_stats(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for row in data.get("scenarios", []) or []:
        if not isinstance(row, dict):
            continue
        tools = row.get("reused_tools") or []
        if not isinstance(tools, list) or not tools:
            continue
        scenario = str(row.get("scenario") or "")
        outcome_delta = _optional_float(row.get("outcome_delta"))
        if outcome_delta is None:
            continue
        for tool in tools:
            tool_name = str(tool)
            entry = stats.setdefault(
                tool_name,
                {
                    "scenarios": set(),
                    "outcome_deltas": [],
                },
            )
            entry["scenarios"].add(scenario)
            entry["outcome_deltas"].append(outcome_delta)

    result: dict[str, dict[str, Any]] = {}
    for tool, raw in stats.items():
        outcome = list(raw["outcome_deltas"])
        result[tool] = {
            "scenario_count": len(raw["scenarios"]),
            "mean_outcome_delta": _mean_float(outcome),
            "outcome_gains": sum(1 for value in outcome if value > 0),
            "outcome_regressions": sum(1 for value in outcome if value < 0),
            "outcome_preserved": sum(1 for value in outcome if value == 0),
        }
    return result


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _sentence_list(values: list[str], *, limit: int = 5) -> str:
    shown = values[:limit]
    if not shown:
        return ""
    if len(values) > limit:
        shown.append(f"{len(values) - limit} more")
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + f", and {shown[-1]}"


def _plain_language_tool_explanation(
    name: str,
    raw: dict[str, Any],
    spec: dict[str, Any],
) -> str:
    description = str(spec.get("description") or "").strip()
    family = str(spec.get("family") or "generated helper").replace("_", " ")
    birth_scenario = str(raw.get("birth_scenario") or "").strip()
    rationale = str(spec.get("generalization_rationale") or "").strip()
    abstain = str(spec.get("abstain_behavior") or "").strip()
    positives = _sentence_list(_string_list(spec.get("positive_triggers")))
    negatives = _sentence_list(_string_list(spec.get("negative_triggers")))
    original_tools = _sentence_list(
        _string_list(spec.get("required_original_tool_calls"))
        or _string_list(spec.get("preserves_side_effect_tools"))
    )
    failure_modes = _sentence_list(
        _string_list(spec.get("known_failure_mechanisms_addressed"))
    )

    paragraphs = [
        (f"{name} is a {family}." + (f" {description}" if description else ""))
    ]
    if birth_scenario:
        paragraphs.append(
            "It was created after SAGE saw a reusable pattern in this task context: "
            f"{birth_scenario}"
        )
    if rationale:
        paragraphs.append(f"Why it exists: {rationale}")
    elif failure_modes:
        paragraphs.append(
            "Why it exists: it addresses recurring failure modes such as "
            f"{failure_modes}."
        )
    if positives:
        paragraphs.append(
            f"It is intended to be used when the task matches: {positives}."
        )
    if negatives:
        paragraphs.append(f"It should avoid tasks matching: {negatives}.")
    if original_tools:
        paragraphs.append(
            "It does not replace the original ToolSandbox action. It prepares or "
            f"normalizes inputs before the agent calls: {original_tools}."
        )
    if abstain:
        paragraphs.append(
            f"When inputs are unsafe or incomplete, it should abstain: {abstain}"
        )
    return "\n\n".join(paragraphs)


def _registry_tool_details(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest = data.get("registry_manifest")
    if not isinstance(manifest, dict):
        return {}
    tools = manifest.get("tools")
    if not isinstance(tools, dict):
        return {}
    details: dict[str, dict[str, Any]] = {}
    for name, raw in tools.items():
        if not isinstance(raw, dict):
            continue
        tool_payload = raw.get("tool")
        if not isinstance(tool_payload, dict):
            continue
        spec = tool_payload.get("spec")
        if not isinstance(spec, dict):
            spec = {}
        details[str(name)] = {
            "code": tool_payload.get("code"),
            "description": spec.get("description"),
            "family": spec.get("family"),
            "plain_language_explanation": _plain_language_tool_explanation(
                str(name), raw, spec
            ),
            "code_hash": raw.get("code_hash"),
        }
    return details


def _task_compare_tool_summary(
    run_root: Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    contribution = _read_json(run_root / "helper_contribution_summary.json")
    helpers = contribution.get("helpers") if isinstance(contribution, dict) else {}
    tools: list[dict[str, Any]] = []
    registry_details = _registry_tool_details(data)
    born = {
        str(event.get("tool_name") or event.get("tool") or "")
        for event in data.get("birth_events", []) or []
        if event.get("accepted") and (event.get("tool_name") or event.get("tool"))
    }
    if isinstance(helpers, dict):
        for name, raw in helpers.items():
            if not isinstance(raw, dict):
                continue
            called_subset = raw.get("called_subset")
            if not isinstance(called_subset, dict):
                called_subset = {}
            tool = {
                "name": str(name),
                "origin": raw.get("origin"),
                **registry_details.get(str(name), {}),
                "visible_count": _tool_count(raw, "visible_count", "visible_scenarios"),
                "called_count": _tool_count(raw, "called_count", "called_scenarios"),
                "visible_not_called_count": _tool_count(
                    raw, "visible_not_called_count", "visible_not_called_scenarios"
                ),
                "failed_attempt_count": _tool_count(
                    raw, "failed_attempt_count", "failed_attempt_scenarios"
                ),
                "called_subset_scenario_count": called_subset.get("scenario_count"),
                "called_subset_mean_outcome_delta": called_subset.get(
                    "mean_outcome_delta"
                ),
                "outcome_gains": called_subset.get("outcome_gains"),
                "outcome_regressions": called_subset.get("outcome_regressions"),
                "outcome_preserved": called_subset.get("outcome_preserved"),
                "side_effect_incident_count": _count_incidents(
                    raw.get("side_effect_incidents")
                ),
                "runtime_incident_count": _count_incidents(
                    raw.get("runtime_incidents")
                ),
                "contribution_source": "helper_contribution_summary",
                "contribution_pending": False,
            }
            if tool["side_effect_incident_count"] or tool["runtime_incident_count"]:
                tool["decision"] = "inspect"
            elif (
                tool["called_count"]
                and (_optional_float(tool["called_subset_mean_outcome_delta"]) or 0.0)
                > 0
            ):
                tool["decision"] = "positive called subset"
            elif tool["called_count"]:
                tool["decision"] = "called; mixed or negative subset"
            else:
                tool["decision"] = "visible or retained; no natural call"
            tools.append(tool)

    existing_names = {str(tool.get("name") or "") for tool in tools}
    missing_live_names = born - existing_names
    if not tools or missing_live_names:
        live_counts = _live_tool_selection_counts(data)
        live_stats = _live_called_tool_delta_stats(data)
        reuse_counts: dict[str, int] = {}
        for event in data.get("reuse_events", []) or []:
            tool_name = str(event.get("tool_name") or event.get("tool") or "")
            if tool_name:
                reuse_counts[tool_name] = reuse_counts.get(tool_name, 0) + 1
        fallback_names = set(reuse_counts) | born | set(live_counts) | set(live_stats)
        for name in sorted(fallback_names - existing_names):
            counts = live_counts.get(name, {})
            stats = live_stats.get(name, {})
            called_count = reuse_counts.get(name, 0) or int(
                counts.get("called_scenario_count") or 0
            )
            outcome_known = stats.get("mean_outcome_delta") is not None
            contribution_pending = bool(called_count and not outcome_known)
            if outcome_known:
                decision = "provisional live paired subset"
            elif contribution_pending:
                decision = "live contribution pending"
            elif name in born:
                decision = "accepted; no natural call yet"
            else:
                decision = "live reuse event fallback"
            tools.append(
                {
                    "name": name,
                    "origin": "generated" if name in born else "retained",
                    **registry_details.get(name, {}),
                    "visible_count": counts.get("visible_count"),
                    "called_count": called_count,
                    "called_scenario_count": counts.get("called_scenario_count"),
                    "visible_not_called_count": counts.get("visible_not_called_count"),
                    "failed_attempt_count": counts.get("failed_attempt_count", 0),
                    "called_subset_scenario_count": stats.get("scenario_count", 0),
                    "called_subset_mean_outcome_delta": stats.get("mean_outcome_delta"),
                    "outcome_gains": stats.get("outcome_gains")
                    if outcome_known
                    else None,
                    "outcome_regressions": stats.get("outcome_regressions")
                    if outcome_known
                    else None,
                    "outcome_preserved": stats.get("outcome_preserved")
                    if outcome_known
                    else None,
                    "side_effect_incident_count": 0,
                    "runtime_incident_count": 0,
                    "contribution_source": "live_reuse_event_fallback",
                    "contribution_pending": contribution_pending,
                    "decision": decision,
                }
            )

    tools = sorted(
        tools,
        key=lambda item: (
            -int(item.get("called_count") or 0),
            str(item.get("name") or ""),
        ),
    )
    birth_event_count = sum(
        1 for event in data.get("birth_events", []) or [] if event.get("accepted")
    )
    helper_tool_count = len(helpers) if isinstance(helpers, dict) else 0
    accepted_tool_count = (
        _named_entry_count(contribution.get("accepted_tools"))
        if isinstance(contribution, dict)
        else 0
    )
    contribution_tool_count = max(helper_tool_count, accepted_tool_count, len(tools))
    contribution_registry_size = (
        contribution.get("registry_size") if isinstance(contribution, dict) else None
    )
    registry_tool_count = max(
        [
            count
            for count in (
                contribution_registry_size
                if isinstance(contribution_registry_size, int)
                else None,
                len(registry_details),
                len(tools),
            )
            if isinstance(count, int)
        ],
        default=0,
    )
    birth_count = max(birth_event_count, accepted_tool_count, registry_tool_count)
    called_tool_count = sum(
        1 for tool in tools if int(tool.get("called_count") or 0) > 0
    )
    visibility_known = any(tool.get("visible_count") is not None for tool in tools)
    outcome_counts_known = any(tool.get("outcome_gains") is not None for tool in tools)
    contribution_known = any(
        tool.get("called_subset_mean_outcome_delta") is not None for tool in tools
    )
    return {
        "registry_tool_count": registry_tool_count,
        "runtime_bundle_size": contribution.get("runtime_bundle_size")
        if isinstance(contribution, dict)
        else None,
        "tool_count": len(tools),
        "generated_tool_birth_count": birth_count,
        "generated_tool_birth_event_count": birth_event_count,
        "contribution_tool_count": contribution_tool_count or len(tools),
        "called_tool_count": called_tool_count,
        "visible_tool_count": (
            sum(1 for tool in tools if (tool.get("visible_count") or 0) > 0)
            if visibility_known
            else None
        ),
        "visibility_known": visibility_known,
        "contribution_known": contribution_known,
        "outcome_gains": (
            sum(int(tool.get("outcome_gains") or 0) for tool in tools)
            if outcome_counts_known
            else None
        ),
        "outcome_regressions": (
            sum(int(tool.get("outcome_regressions") or 0) for tool in tools)
            if outcome_counts_known
            else None
        ),
        "side_effect_incident_count": sum(
            int(tool.get("side_effect_incident_count") or 0) for tool in tools
        ),
        "runtime_incident_count": sum(
            int(tool.get("runtime_incident_count") or 0) for tool in tools
        ),
        "source": "helper_contribution_summary"
        if tools and helpers
        else "live_fallback",
        "accepted_tools": contribution.get("accepted_tools", [])
        if isinstance(contribution, dict)
        else [],
        "accepted_but_uncalled_tools": contribution.get(
            "accepted_but_uncalled_tools", []
        )
        if isinstance(contribution, dict)
        else [],
        "selection_attribution_buckets": contribution.get(
            "selection_attribution_buckets", {}
        )
        if isinstance(contribution, dict)
        else {},
        "selection_attribution_claim_guidance": contribution.get(
            "selection_attribution_claim_guidance", {}
        )
        if isinstance(contribution, dict)
        else {},
        "tools": tools,
    }


_TASK_COMPARE_DROPPED_PERFORMANCE_SECTIONS = frozenset(
    {
        "evaluation",
        "outcome",
        "baseline_count_and_variance_per_cached_task",
        "task_level_fields",
    }
)
_TASK_COMPARE_DROPPED_PERFORMANCE_FIELDS = frozenset(
    {
        "balanced_delta",
        "balanced_lift_percent",
        "correctness_label",
        "exact_correct",
        "exact_success_rate",
    }
)
_TASK_COMPARE_PERFORMANCE_LABEL_KEYS = frozenset(
    {"kind", "label", "metric", "metric_label", "title"}
)
_TASK_COMPARE_FORBIDDEN_PERFORMANCE_LABEL = re.compile(
    r"\b(?:canonical(?: audit| similarity| score)?|reference similarity|score|"
    r"milestone|minefield)\b",
    flags=re.IGNORECASE,
)


def _is_task_compare_performance_field(key: str) -> bool:
    """Return whether a JSON field belongs to a non-outcome evaluator."""
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _TASK_COMPARE_DROPPED_PERFORMANCE_SECTIONS:
        return True
    if normalized in _TASK_COMPARE_DROPPED_PERFORMANCE_FIELDS:
        return True
    if "canonical" in normalized or "milestone" in normalized:
        return True
    if "minefield" in normalized:
        return True
    if "reference" in normalized and "similarity" in normalized:
        return True
    key_parts = normalized.split("_")
    if any(part.startswith("score") for part in key_parts):
        return True
    return normalized.endswith("similarity") and "outcome" not in key_parts


def _sanitize_task_compare_payload(value: Any) -> Any:
    """Remove non-outcome performance data from the Task Compare export.

    Underlying run artifacts retain legacy evaluator diagnostics. Task Compare
    is publication-facing and exposes only outcome performance alongside its
    routing and transcript evidence.
    """
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if _is_task_compare_performance_field(key):
                continue
            normalized = key.strip().lower().replace("-", "_")
            if (
                normalized in _TASK_COMPARE_PERFORMANCE_LABEL_KEYS
                and isinstance(item, str)
                and _TASK_COMPARE_FORBIDDEN_PERFORMANCE_LABEL.search(item)
            ):
                continue
            sanitized[key] = _sanitize_task_compare_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_task_compare_payload(item) for item in value]
    return value


def _write_task_compare_dashboard(
    dashboard_dir: Path,
    run_root: Path,
    data: dict[str, Any],
    task_payload: dict[str, Any],
) -> None:
    payload = _sanitize_task_compare_payload(
        {
            **task_payload,
            "tool_summary": _task_compare_tool_summary(run_root, data),
        }
    )
    (dashboard_dir / "task_compare_data.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "task_compare.html").write_text(
        TASK_COMPARE_HTML, encoding="utf-8"
    )


def _scenario_table(
    dashboard_dir: Path,
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> list[dict[str, Any]]:
    control = {str(row.get("name")): row for row in _scenario_rows(control_dir)}
    candidate = {str(row.get("name")): row for row in _scenario_rows(candidate_dir)}
    reuse_by_scenario: dict[str, set[str]] = {}
    if candidate_dir is not None:
        for event in _read_jsonl(candidate_dir / "reuse_events.jsonl"):
            scenario = str(event.get("scenario", ""))
            tool = str(event.get("tool_name", ""))
            if scenario and tool:
                reuse_by_scenario.setdefault(scenario, set()).add(tool)
    names = list(dict.fromkeys([*control.keys(), *candidate.keys()]))
    rows: list[dict[str, Any]] = []
    for name in names:
        c_row = control.get(name, {})
        s_row = candidate.get(name, {})
        c_outcome = _optional_float(c_row.get("outcome_similarity")) if c_row else None
        s_outcome = _optional_float(s_row.get("outcome_similarity")) if s_row else None
        outcome_delta = (
            s_outcome - c_outcome
            if c_outcome is not None and s_outcome is not None
            else None
        )
        rows.append(
            {
                "scenario": name,
                "categories": c_row.get("categories") or s_row.get("categories") or [],
                "control_outcome_similarity": c_outcome,
                "candidate_outcome_similarity": s_outcome,
                "outcome_delta": outcome_delta,
                "status": (
                    "gain"
                    if outcome_delta is not None and outcome_delta > 0
                    else "regression"
                    if outcome_delta is not None and outcome_delta < 0
                    else "preserved"
                ),
                "control_turns": c_row.get("turn_count"),
                "candidate_turns": s_row.get("turn_count"),
                "control_llm_call_count": c_row.get("llm_call_count"),
                "candidate_llm_call_count": s_row.get("llm_call_count"),
                "control_llm_total_tokens": c_row.get("llm_total_tokens"),
                "candidate_llm_total_tokens": s_row.get("llm_total_tokens"),
                "control_exception": c_row.get("exception_type"),
                "candidate_exception": s_row.get("exception_type"),
                "reused_tools": sorted(reuse_by_scenario.get(name, set())),
                "control_trace_url": _trace_url(dashboard_dir, control_dir, name),
                "candidate_trace_url": _trace_url(dashboard_dir, candidate_dir, name),
            }
        )
    return rows


def _partial_comparison(
    control_dir: Path | None,
    candidate_dir: Path | None,
    registry_dir: Path | None,
) -> dict[str, Any]:
    if control_dir is not None and candidate_dir is not None:
        return compare_runs(
            control_dir,
            candidate_dir,
            registry_dir=registry_dir,
            require_complete_match=False,
        )
    return {
        "control": summarize_run(control_dir) if control_dir is not None else {},
        "candidate": summarize_run(candidate_dir, registry_dir=registry_dir)
        if candidate_dir is not None
        else {},
        "scenario_count": 0,
        "outcome_scenario_count": 0,
        "mean_outcome_similarity_delta": None,
        "outcome_gain_count": 0,
        "outcome_regression_count": 0,
        "outcome_preserved_count": 0,
        "outcome_gains": [],
        "outcome_regressions": [],
        "deltas": [],
        "comparison_type": "intersection_only",
        "claim_grade": False,
    }


def write_protocol_dashboard(
    run_root: Path,
    *,
    mode: str,
    status: str,
    phase: str,
    agent: str,
    user: str,
    generation_enabled: bool,
    base_tool_policy: str,
    scenario_count: int,
    control_dir: Path | None = None,
    candidate_dir: Path | None = None,
    registry_dir: Path | None = None,
    model_metadata: dict[str, Any] | None = None,
    artifact_root: Path = ARTIFACT_ROOT,
    control_label: str = "Non-learning",
    candidate_label: str = "SAGE",
) -> Path:
    """Write dashboard HTML and data for a paired protocol run."""
    control_dir = _resolve_run_dir(control_dir)
    candidate_dir = _resolve_run_dir(candidate_dir)
    dashboard_dir = run_root / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    started_at_path = run_root / "dashboard_started_at.txt"
    if started_at_path.exists():
        started_at = started_at_path.read_text(encoding="utf-8").strip()
    else:
        started_at = datetime.now(timezone.utc).isoformat()
        started_at_path.write_text(started_at + "\n", encoding="utf-8")
    comparison = _partial_comparison(control_dir, candidate_dir, registry_dir)
    data = {
        "mode": mode,
        "status": status,
        "phase": phase,
        "agent": agent,
        "user": user,
        "model_metadata": model_metadata or {},
        "comparison_model_key": (model_metadata or {}).get("comparison_key"),
        "generation_enabled": generation_enabled,
        "base_tool_policy": base_tool_policy,
        "arm_labels": {
            "control": control_label,
            "candidate": candidate_label,
        },
        "scenario_count": scenario_count,
        "cohort_preflight": _read_json(run_root / "cohort_preflight_report.json"),
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "control": comparison.get("control", {}),
        "candidate": comparison.get("candidate", {}),
        "comparison": {
            key: comparison.get(key)
            for key in (
                "outcome_gain_count",
                "outcome_regression_count",
                "outcome_preserved_count",
            )
        },
        "mean_outcome_similarity_delta": comparison.get(
            "mean_outcome_similarity_delta"
        ),
        "scenarios": _scenario_table(dashboard_dir, control_dir, candidate_dir),
        "birth_events": _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
        if candidate_dir
        else [],
        "reuse_events": _read_jsonl(candidate_dir / "reuse_events.jsonl")
        if candidate_dir
        else [],
        "run_events": _read_jsonl(candidate_dir / "sage_run_events.jsonl")
        if candidate_dir
        else [],
        "campaign": _campaign_payload(artifact_root),
        "registry_manifest": _read_json(registry_dir / "registry_manifest.json")
        if registry_dir
        else {},
    }
    task_payload = _task_compare_payload(
        dashboard_dir,
        run_root,
        data,
        control_dir,
        candidate_dir,
    )
    _write_task_compare_dashboard(dashboard_dir, run_root, data, task_payload)
    _write_latest_pointer(
        dashboard_dir / "task_compare.html",
        name="latest_sage_ts.html",
    )
    _write_latest_pointer(
        dashboard_dir / "task_compare.html",
        name="latest_sage_ts_task_compare.html",
    )
    return dashboard_dir / "task_compare.html"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dashboard_url(
    index_path: Path,
    *,
    port: int = 5520,
    server_root: Path | None = None,
) -> str:
    resolved_index = index_path.resolve()
    if server_root is None:
        repo_root = _repo_root().resolve()
        try:
            resolved_index.relative_to(repo_root)
            root = repo_root
        except ValueError:
            root = resolved_index.parent
    else:
        root = server_root.resolve()
    rel = resolved_index.relative_to(root)
    return f"http://127.0.0.1:{port}/{quote(str(rel))}"


def _dashboard_port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _dashboard_server_identity(port: int) -> dict[str, Any] | None:
    url = f"http://127.0.0.1:{port}{DASHBOARD_SERVER_IDENTITY_PATH}"
    try:
        with urlopen(url, timeout=1.0) as response:  # noqa: S310
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, ValueError, URLError):
        return None
    return payload if isinstance(payload, dict) else None


def _assert_dashboard_server_identity(port: int, server_root: Path) -> None:
    expected_root = str(server_root.resolve())
    identity = _dashboard_server_identity(port)
    if identity is None:
        raise RuntimeError(
            f"Port {port} is occupied by a server that does not expose the "
            "SAGE dashboard identity endpoint."
        )
    if (
        identity.get("protocol") != DASHBOARD_SERVER_PROTOCOL
        or identity.get("root") != expected_root
    ):
        raise RuntimeError(
            f"Port {port} is serving a different dashboard root: "
            f"expected {expected_root!r}, observed {identity.get('root')!r}."
        )


def ensure_dashboard_server(
    *,
    port: int = 5520,
    server_root: Path | None = None,
) -> None:
    """Start a static file server for the dashboard output root."""
    repo_root = _repo_root().resolve()
    root = (server_root or repo_root).resolve()
    if _dashboard_port_is_open(port):
        _assert_dashboard_server_identity(port, root)
        return
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(repo_root / "src"),
            str(repo_root),
            environment.get("PYTHONPATH", ""),
        ]
    ).rstrip(os.pathsep)
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "sage_ts.dashboard.server",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
            "--root",
            str(root),
        ],
        cwd=repo_root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        identity = _dashboard_server_identity(port)
        if identity is not None:
            _assert_dashboard_server_identity(port, root)
            return
        time.sleep(0.1)
    raise RuntimeError(
        f"Dashboard server on port {port} did not publish its root identity."
    )


def open_dashboard(
    index_path: Path,
    *,
    port: int = 5520,
    server_root: Path | None = None,
) -> str:
    resolved_index = index_path.resolve()
    if not resolved_index.is_file():
        raise FileNotFoundError(f"Dashboard file does not exist: {resolved_index}")
    if server_root is None:
        repo_root = _repo_root().resolve()
        try:
            resolved_index.relative_to(repo_root)
            resolved_server_root = repo_root
        except ValueError:
            resolved_server_root = resolved_index.parent
    else:
        resolved_server_root = server_root.resolve()
        try:
            resolved_index.relative_to(resolved_server_root)
        except ValueError as exc:
            raise ValueError(
                f"Dashboard file {resolved_index} is outside server root "
                f"{resolved_server_root}."
            ) from exc
    ensure_dashboard_server(port=port, server_root=resolved_server_root)
    url = dashboard_url(index_path, port=port, server_root=resolved_server_root)

    deadline = time.monotonic() + 10.0
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            expected_body = resolved_index.read_bytes()
            with urlopen(url, timeout=1.0) as response:  # noqa: S310
                response_body = response.read()
                if response.status == 200 and response_body == expected_body:
                    break
                if response.status == 200:
                    raise RuntimeError(
                        f"Dashboard URL served bytes from a different file/root: {url}"
                    )
                last_error = RuntimeError(
                    f"dashboard server returned HTTP {response.status}"
                )
        except (OSError, URLError) as exc:
            last_error = exc
        time.sleep(0.1)
    else:
        raise RuntimeError(
            f"Dashboard URL was not reachable before browser open: {url}"
        ) from last_error

    # Publication runs execute on macOS. Use the checked OS opener as the sole
    # launch path there so one external browser tab is opened and failures are
    # observable before model execution begins.
    if sys.platform == "darwin":
        subprocess.run(
            ["open", url],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    elif not webbrowser.open_new_tab(url):
        raise RuntimeError(f"The default browser refused the dashboard URL: {url}")
    return url


def _write_latest_pointer(index_path: Path, *, name: str) -> None:
    latest_dir = _repo_root() / "outputs" / "dashboard"
    latest_dir.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(index_path, latest_dir)
    label = "Open latest ToolSandbox SAGE Task Compare dashboard"
    (latest_dir / name).write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={rel}">
<a href="{rel}">{label}</a>
""",
        encoding="utf-8",
    )
