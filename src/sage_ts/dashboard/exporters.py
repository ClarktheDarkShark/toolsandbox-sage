"""Dashboard data exporters for ToolSandbox SAGE protocol runs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from sage_ts.campaign.artifacts import ARTIFACT_ROOT, read_jsonl
from sage_ts.dashboard.task_focus_template import TASK_FOCUS_HTML
from sage_ts.dashboard.template import DASHBOARD_HTML
from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _read_json_value(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _scenario_rows(run_dir: Path | None) -> list[dict[str, Any]]:
    if run_dir is None:
        return []
    summary = run_dir / "result_summary.json"
    live = run_dir / "live_result_summary.json"
    data = _read_json(summary if summary.exists() else live)
    return list(data.get("per_scenario_results", []))


def _trace_url(dashboard_dir: Path, run_dir: Path | None, scenario: str) -> str | None:
    if run_dir is None:
        return None
    pretty = run_dir / "trajectories" / scenario / "pretty_print.txt"
    if not pretty.exists():
        return None
    return os.path.relpath(pretty, dashboard_dir)


def _manifest_order(run_dir: Path) -> dict[str, int]:
    manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    names = manifest.get("scenario_names") or []
    return {str(name): index for index, name in enumerate(names)}


def _generated_tool_usage(run_dir: Path) -> dict[str, list[str]]:
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


def _compact_content(value: Any, *, limit: int = 10000) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


def _one_line(value: Any, *, limit: int = 180) -> str:
    text = " ".join(_compact_content(value, limit=max(limit * 4, 1000)).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


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
        "label": _message_label(message),
        "content": content,
        "generated_tools": used,
        "uses_generated_tool": bool(used),
    }


def _expected_answers_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    answers: list[str] = []
    for message in messages:
        details = [
            message.get("assistant_details") or {},
            message.get("tool_details") or {},
        ]
        for detail in details:
            for match in detail.get("milestone_matches", []):
                milestone = (
                    match.get("milestone", {}) if isinstance(match, dict) else {}
                )
                for constraint in milestone.get("snapshot_constraints", []):
                    rows = constraint.get("target_dataframe") or []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if (
                            row.get("sender") == "AGENT"
                            and row.get("recipient") == "USER"
                        ):
                            content = _compact_content(row.get("content"), limit=3000)
                            if content and content not in answers:
                                answers.append(content)
    return answers


def _summarize_tool_messages(messages: list[dict[str, Any]]) -> str:
    tool_bits: list[str] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        name = str(message.get("name") or "tool")
        content = _compact_content(message.get("content"), limit=900)
        if content.lower() in {"", "none", "null"}:
            content = "no visible state change"
        tool_bits.append(f"{name}: {_one_line(content, limit=80)}")
    return _one_line("; ".join(tool_bits[-3:]), limit=220)


def _task_outcome(
    messages: list[dict[str, Any]],
    result: dict[str, Any] | None,
    scenario: str,
) -> dict[str, Any]:
    final_index: int | None = None
    for index, message in enumerate(messages):
        if message.get("role") == "assistant" and message.get("assistant_details"):
            final_index = index
    if final_index is None:
        for index, message in enumerate(messages):
            if message.get("role") == "assistant" and _compact_content(
                message.get("content")
            ):
                final_index = index
    final_answer = (
        ""
        if final_index is None
        else _compact_content(messages[final_index].get("content"), limit=4000)
    )
    similarity = None if result is None else result.get("similarity")
    exact = bool(similarity is not None and float(similarity) >= 0.999)
    tool_summary = _summarize_tool_messages(messages)
    result_parts = []
    if final_answer:
        result_parts.append(f"Answer: {_one_line(final_answer, limit=130)}")
    if tool_summary:
        result_parts.append(f"Tools: {tool_summary}")
    if similarity is not None and float(similarity) < 0.999:
        result_parts.append(f"Score: {float(similarity):.3f}")
    return {
        "agent_final_answer": final_answer,
        "agent_result_summary": "\n".join(result_parts),
        "expected_answers": _expected_answers_from_messages(messages),
        "expected_note": (
            "State/tool milestone-scored target; inspect messages and tool evidence."
        ),
        "similarity": similarity,
        "exact_correct": exact,
        "correctness_label": (
            "pending" if result is None else "correct" if exact else "not exact"
        ),
        "scenario": scenario,
    }


def _task_focus_rows(
    run_root: Path,
    run_dir: Path | None,
) -> list[dict[str, Any]]:
    if run_dir is None:
        return []
    rows = {
        str(row.get("name")): row
        for row in _scenario_rows(run_dir)
        if isinstance(row, dict) and row.get("name")
    }
    order = _manifest_order(run_dir)
    usage = _generated_tool_usage(run_dir)
    trajectory_dir = run_dir / "trajectories"
    trajectory_names = (
        {path.name for path in trajectory_dir.iterdir() if path.is_dir()}
        if trajectory_dir.exists()
        else set()
    )
    tasks: list[dict[str, Any]] = []
    for scenario in sorted(
        set(rows) | trajectory_names,
        key=lambda name: (order.get(name, 10_000), name),
    ):
        result = rows.get(scenario)
        conversation = _read_json_value(
            run_dir / "trajectories" / scenario / "conversation.json", []
        )
        raw_messages = [m for m in conversation if isinstance(m, dict)]
        generated_tools = usage.get(scenario, [])
        generated_set = set(generated_tools)
        phase = run_dir.relative_to(run_root).parts[0]
        tasks.append(
            {
                "id": f"{phase}:{run_dir.name}:{scenario}",
                "phase": phase,
                "run_type": run_dir.name,
                "scenario": scenario,
                "short_name": scenario.replace("_", " "),
                "status": "complete" if result else "running",
                "order_index": order.get(scenario),
                "display_index": None
                if order.get(scenario) is None
                else int(order[scenario]) + 1,
                "generated_tools": generated_tools,
                "similarity": None if result is None else result.get("similarity"),
                "score": None if result is None else result.get("similarity"),
                "turn_count": None if result is None else result.get("turn_count"),
                "exception_type": None
                if result is None
                else result.get("exception_type"),
                "categories": [] if result is None else result.get("categories", []),
                "message_count": len(raw_messages),
                "messages": [
                    _serialize_message(index, message, generated_set)
                    for index, message in enumerate(raw_messages)
                ],
                "outcome": _task_outcome(raw_messages, result, scenario),
            }
        )
    return tasks


def _write_task_focus_dashboard(
    dashboard_dir: Path,
    run_root: Path,
    data: dict[str, Any],
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> None:
    control_tasks = _task_focus_rows(run_root, control_dir)
    candidate_tasks = _task_focus_rows(run_root, candidate_dir)
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
    payload = {
        "updated_at": data.get("updated_at"),
        "run_root": str(run_root),
        "mode": data.get("mode"),
        "phase": data.get("phase"),
        "status": data.get("status"),
        "agent": data.get("agent"),
        "base_tool_policy": data.get("base_tool_policy"),
        "summary": {
            "scenario_count": data.get("scenario_count"),
            "control_completed": data.get("control", {}).get("scenario_count"),
            "control_mean_similarity": data.get("control", {}).get("mean_similarity"),
            "candidate_completed": data.get("candidate", {}).get("scenario_count"),
            "candidate_mean_similarity": data.get("candidate", {}).get(
                "mean_similarity"
            ),
            "accepted_tools": current.get("accepted_tool_count", 0),
            "reuse_count": current.get("reuse_count", 0),
            "current_completed": current.get("scenario_count"),
            "current_mean_similarity": current.get("mean_similarity"),
            "current_turns": current.get("total_turns"),
            "current_exceptions": current.get("exception_count"),
        },
        "active_task_id": None if active is None else active["id"],
        "tasks": tasks,
        "pairs": pairs,
    }
    (dashboard_dir / "task_focus_data.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "task_focus.html").write_text(TASK_FOCUS_HTML, encoding="utf-8")


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
        c_score = float(c_row.get("similarity", 0.0)) if c_row else None
        s_score = float(s_row.get("similarity", 0.0)) if s_row else None
        delta = (
            (s_score - c_score) if c_score is not None and s_score is not None else None
        )
        status = (
            "gain"
            if delta is not None and delta > 0
            else "regression"
            if delta is not None and delta < 0
            else "preserved"
        )
        rows.append(
            {
                "scenario": name,
                "categories": c_row.get("categories") or s_row.get("categories") or [],
                "control_similarity": c_score,
                "candidate_similarity": s_score,
                "delta": delta,
                "status": status,
                "control_turns": c_row.get("turn_count"),
                "candidate_turns": s_row.get("turn_count"),
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
        return compare_runs(control_dir, candidate_dir, registry_dir=registry_dir)
    return {
        "control": summarize_run(control_dir) if control_dir is not None else {},
        "candidate": summarize_run(candidate_dir, registry_dir=registry_dir)
        if candidate_dir is not None
        else {},
        "scenario_count": 0,
        "mean_similarity_delta": 0.0,
        "gain_count": 0,
        "regression_count": 0,
        "preserved_count": 0,
        "gains": [],
        "regressions": [],
        "deltas": [],
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
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    """Write dashboard HTML and data for a paired protocol run."""
    dashboard_dir = run_root / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    comparison = _partial_comparison(control_dir, candidate_dir, registry_dir)
    data = {
        "mode": mode,
        "status": status,
        "phase": phase,
        "agent": agent,
        "user": user,
        "generation_enabled": generation_enabled,
        "base_tool_policy": base_tool_policy,
        "scenario_count": scenario_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "control": comparison.get("control", {}),
        "candidate": comparison.get("candidate", {}),
        "comparison": {
            key: comparison.get(key)
            for key in ("gain_count", "regression_count", "preserved_count")
        },
        "mean_similarity_delta": comparison.get("mean_similarity_delta", 0.0),
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
    (dashboard_dir / "data.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "index.html").write_text(DASHBOARD_HTML, encoding="utf-8")
    _write_task_focus_dashboard(
        dashboard_dir,
        run_root,
        data,
        control_dir,
        candidate_dir,
    )
    _write_latest_pointer(dashboard_dir / "index.html")
    return dashboard_dir / "index.html"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dashboard_url(index_path: Path, *, port: int = 5520) -> str:
    rel = index_path.resolve().relative_to(_repo_root())
    return f"http://127.0.0.1:{port}/{quote(str(rel))}"


def ensure_dashboard_server(*, port: int = 5520) -> None:
    """Start a repo-root static file server if the dashboard port is unused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            return
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
        ],
        cwd=_repo_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_dashboard(index_path: Path, *, port: int = 5520) -> str:
    ensure_dashboard_server(port=port)
    url = dashboard_url(index_path, port=port)
    webbrowser.open(url)
    return url


def _write_latest_pointer(index_path: Path) -> None:
    latest_dir = _repo_root() / "outputs" / "dashboard"
    latest_dir.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(index_path, latest_dir)
    (latest_dir / "latest_sage_ts.html").write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={rel}">
<a href="{rel}">Open latest ToolSandbox SAGE dashboard</a>
""",
        encoding="utf-8",
    )
