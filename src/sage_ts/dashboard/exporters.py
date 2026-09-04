"""Dashboard data exporters for ToolSandbox SAGE protocol runs."""

from __future__ import annotations

import difflib
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
from typing import Any, cast
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from sage_ts.campaign.artifacts import ARTIFACT_ROOT, read_jsonl
from sage_ts.dashboard.server import (
    DASHBOARD_SERVER_IDENTITY_PATH,
    DASHBOARD_SERVER_PROTOCOL,
)
from sage_ts.dashboard.task_compare_template import TASK_COMPARE_HTML
from sage_ts.dashboard.task_focus_template import TASK_FOCUS_HTML
from sage_ts.dashboard.template import DASHBOARD_HTML
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


def _cached_control_transcript(
    control_cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    load_transcripts = os.environ.get(
        "SAGE_DASHBOARD_LOAD_CACHED_CONTROL_TRANSCRIPTS", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    record_ids = control_cache.get("record_ids")
    if not isinstance(record_ids, list):
        return [], None
    records_dir = (
        _repo_root() / "artifacts" / "baselines" / "control_task_baselines" / "records"
    )
    for record_id in record_ids:
        if not isinstance(record_id, str) or not re.fullmatch(
            r"[0-9a-f]{64}", record_id
        ):
            continue
        record_path = records_dir / f"{record_id}.json"
        if not load_transcripts:
            return [], {
                "source": "control_task_baseline_cache",
                "record_id": record_id,
                "record_path": str(record_path),
                "transcript_loaded": False,
                "transcript_load_policy": "disabled_for_live_dashboard",
            }
        record = _read_json(record_path)
        transcript_path = record.get("transcript_path")
        if not isinstance(transcript_path, str) or not transcript_path:
            continue
        transcript = Path(transcript_path)
        if not transcript.is_absolute():
            transcript = _repo_root() / transcript
        source = {
            "source": "control_task_baseline_cache",
            "record_id": record_id,
            "record_path": str(record_path),
            "transcript_path": transcript_path,
            "transcript_hash": record.get("transcript_hash"),
            "transcript_loaded": False,
        }
        conversation = _read_json_value(transcript, [])
        raw_messages = [m for m in conversation if isinstance(m, dict)]
        if raw_messages:
            source["transcript_loaded"] = True
            return raw_messages, source
    return [], None


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
        "name": message.get("name"),
        "label": _message_label(message),
        "content": content,
        "generated_tools": used,
        "uses_generated_tool": bool(used),
    }


def _message_observation_content(message: dict[str, Any], *, limit: int = 10000) -> str:
    tool_calls = message.get("tool_calls") or []
    call_text = "\n\n".join(
        (
            f"{call.get('function', {}).get('name', 'tool')}("
            f"{call.get('function', {}).get('arguments', '')})"
        )
        for call in tool_calls
        if isinstance(call, dict)
    )
    content = _compact_content(message.get("content"), limit=limit)
    if call_text:
        if not content:
            return call_text
        if content.strip() == call_text.strip():
            return content
        return f"{content}\n\n{call_text}"
    return content


def _value_preview(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True, default=str)


def _compact_row(
    namespace: str,
    row: dict[str, Any],
    *,
    preferred_keys: list[str] | None = None,
) -> str:
    hidden_keys = {"sandbox_message_index", "reminder_id", "person_id", "message_id"}
    keys = (
        preferred_keys
        if preferred_keys is not None
        else [
            key
            for key, value in row.items()
            if key not in hidden_keys and value not in (None, "", [])
        ]
    )
    parts = []
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value in ("", []):
            continue
        if preferred_keys is None and value is None:
            continue
        parts.append(f"{key}={_value_preview(value)}")
    if namespace == "SANDBOX":
        sender = row.get("sender")
        recipient = row.get("recipient")
        content = row.get("content")
        if content and sender and recipient:
            return f"{sender} -> {recipient}: {_value_preview(content)}"
    if len(parts) == 1 and keys == ["content"]:
        return parts[0][len("content=") :]
    prefix = f"{namespace}: " if namespace and namespace != "SANDBOX" else ""
    return prefix + ", ".join(parts)


def _tool_trace_lines(trace: Any) -> list[str]:
    try:
        parsed = json.loads(trace) if isinstance(trace, str) else trace
    except Exception:
        return []
    calls = (
        parsed
        if isinstance(parsed, list)
        else [parsed]
        if isinstance(parsed, dict)
        else []
    )
    lines: list[str] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = str(call.get("tool_name") or "tool")
        arguments = call.get("arguments") or {}
        if isinstance(arguments, dict) and arguments:
            arg_text = ", ".join(
                f"{key}={json.dumps(value, ensure_ascii=True, default=str)}"
                for key, value in arguments.items()
            )
            lines.append(f"{name}({arg_text})")
        else:
            lines.append(f"{name}()")
    return lines


def _milestone_desc(constraints: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for c in constraints:
        ns = str(c.get("database_namespace", ""))
        rows = c.get("target_dataframe") or []
        if not rows:
            continue
        if ns == "SANDBOX":
            tool_lines = _tool_trace_lines(
                (rows[0] if rows else {}).get("tool_trace", "")
            )
            if tool_lines:
                parts.append(
                    _one_line(f"Tool trace: {'; '.join(tool_lines)}", limit=120)
                )
                continue
            row = rows[0] if isinstance(rows[0], dict) else {}
            content = _compact_content(row.get("content"), limit=240)
            sender = row.get("sender")
            recipient = row.get("recipient")
            if content and sender and recipient:
                parts.append(
                    _one_line(f"{sender} -> {recipient}: {content}", limit=120)
                )
        else:
            row = rows[0] if isinstance(rows[0], dict) else {}
            fields = [k for k in row if k not in ("sender", "recipient", "tool_trace")]
            if fields:
                parts.append(f"{ns}: {', '.join(fields)}")
    return " · ".join(parts) if parts else "Milestone check"


def _milestone_target_lines(constraints: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for c in constraints:
        ns = str(c.get("database_namespace", ""))
        rows = c.get("target_dataframe") or []
        if not rows:
            continue
        if ns == "SANDBOX":
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tool_lines = _tool_trace_lines(row.get("tool_trace", ""))
                if tool_lines:
                    lines.extend(tool_lines)
                    continue
                content = _compact_content(row.get("content"), limit=3000)
                sender = row.get("sender")
                recipient = row.get("recipient")
                if content and sender and recipient:
                    lines.append(_compact_row(ns, row, preferred_keys=["content"]))
        else:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                preferred = [
                    key
                    for key, _value in row.items()
                    if key not in ("sender", "recipient", "tool_trace")
                    and row[key] != ""
                    and row[key] != []
                ]
                if preferred:
                    lines.append(_compact_row(ns, row, preferred_keys=preferred[:4]))
    return lines


def _row_match_score(
    candidate: dict[str, Any], target: dict[str, Any]
) -> tuple[int, int]:
    exact = 0
    partial = 0
    for key, value in target.items():
        if key not in candidate:
            continue
        current = candidate.get(key)
        if current == value:
            exact += 1
            continue
        if isinstance(current, str) and isinstance(value, str):
            current_norm = current.lower()
            value_norm = value.lower()
            if current_norm in value_norm or value_norm in current_norm:
                partial += 1
    return exact, partial


def _database_update_observed_lines(
    message: dict[str, Any],
    *,
    constraints: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    details = [
        message.get("assistant_details") or {},
        message.get("tool_details") or {},
    ]
    for constraint in constraints:
        namespace = str(constraint.get("database_namespace", ""))
        if namespace in {"", "SANDBOX"}:
            continue
        target_rows = [
            row
            for row in (constraint.get("target_dataframe") or [])
            if isinstance(row, dict)
        ]
        if not target_rows:
            continue
        for detail in details:
            database_update = detail.get("database_update", {}).get(namespace)
            if not isinstance(database_update, list) or not database_update:
                continue
            candidate_rows = [row for row in database_update if isinstance(row, dict)]
            for target_row in target_rows:
                preferred = [
                    key
                    for key, value in target_row.items()
                    if value is not None and value != "" and value != []
                ]
                if not preferred:
                    continue
                ranked = sorted(
                    candidate_rows,
                    key=lambda row: _row_match_score(row, target_row),
                    reverse=True,
                )
                if ranked:
                    line = _compact_row(
                        namespace, ranked[0], preferred_keys=preferred[:4]
                    )
                    if line not in lines:
                        lines.append(line)
    return lines


def _database_update_observed_lines_across_messages(
    messages: list[dict[str, Any]],
    *,
    constraints: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    details_with_order: list[tuple[int, dict[str, Any]]] = []
    for message_index, message in enumerate(messages):
        for detail in (
            message.get("assistant_details") or {},
            message.get("tool_details") or {},
        ):
            details_with_order.append((message_index, detail))

    for constraint in constraints:
        namespace = str(constraint.get("database_namespace", ""))
        if namespace in {"", "SANDBOX"}:
            continue
        target_rows = [
            row
            for row in (constraint.get("target_dataframe") or [])
            if isinstance(row, dict)
        ]
        if not target_rows:
            continue
        for target_row in target_rows:
            preferred = [
                key for key, value in target_row.items() if value != "" and value != []
            ]
            if not preferred:
                continue
            ranked_rows: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
            for message_index, detail in details_with_order:
                database_update = detail.get("database_update", {}).get(namespace)
                if not isinstance(database_update, list):
                    continue
                for row in database_update:
                    if not isinstance(row, dict):
                        continue
                    exact, partial = _row_match_score(row, target_row)
                    ranked_rows.append(((exact, partial, message_index), row))
            if not ranked_rows:
                continue
            _score, best_row = max(ranked_rows, key=lambda item: item[0])
            line = _compact_row(namespace, best_row, preferred_keys=preferred[:4])
            if line not in lines:
                lines.append(line)
    return lines


def _observed_lines_for_message(
    messages: list[dict[str, Any]],
    index: int,
    *,
    constraints: list[dict[str, Any]] | None = None,
) -> list[str]:
    if index < 0 or index >= len(messages):
        return []
    lines: list[str] = []
    message = messages[index]
    constraint_namespaces = {
        str(constraint.get("database_namespace", ""))
        for constraint in (constraints or [])
        if isinstance(constraint, dict)
    }
    if constraints:
        for line in _database_update_observed_lines(message, constraints=constraints):
            if line not in lines:
                lines.append(line)
    if lines and constraint_namespaces - {"", "SANDBOX"}:
        return lines
    if message.get("role") == "tool" and index > 0:
        previous = messages[index - 1]
        prev_content = _message_observation_content(previous, limit=1200)
        if prev_content:
            lines.append(prev_content)
    content = _message_observation_content(message, limit=1200)
    if content:
        if message.get("role") == "tool":
            name = str(message.get("name") or "tool")
            lines.append(f"{name}: {content}")
        else:
            lines.append(content)
    deduped: list[str] = []
    for line in lines:
        if line and line not in deduped:
            deduped.append(line)
    return deduped


def _expected_check_fallback_lines(
    expected_lines: list[Any],
    messages: list[dict[str, Any]],
    *,
    limit: int = 2,
) -> list[str]:
    fragments: list[str] = []
    for expected in expected_lines:
        text = str(expected)
        if not text:
            continue
        lowered = text.lower()
        fragments.append(lowered)
        if ":" in text:
            after_colon = text.split(":", 1)[1].strip().lower()
            if after_colon:
                fragments.append(after_colon)
        for quoted_text in re.findall(r"'([^']+)'", text):
            if quoted_text.strip():
                fragments.append(quoted_text.strip().lower())
        match = re.match(r"([a-z_][a-z0-9_]*)\(", lowered)
        if match:
            fragments.append(f"{match.group(1)}(")
    fragments = [
        fragment
        for i, fragment in enumerate(fragments)
        if len(fragment) >= 4 and fragment not in fragments[:i]
    ]
    if not fragments:
        return []

    deduped: list[str] = []
    for msg_index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        content = _message_observation_content(message, limit=1200)
        if not content:
            continue
        lowered = content.lower()
        attempt: list[str] = []
        if any(fragment in lowered for fragment in fragments):
            attempt.append(content)
        else:
            for fragment in fragments:
                ratio = difflib.SequenceMatcher(
                    None,
                    fragment,
                    lowered,
                ).quick_ratio()
                if ratio >= 0.55:
                    attempt.append(content)
                    break
        if not attempt:
            continue
        if msg_index + 1 < len(messages):
            tool_message = messages[msg_index + 1]
            if tool_message.get("role") == "tool":
                tool_content = _message_observation_content(tool_message, limit=1200)
                if tool_content:
                    attempt.append(
                        f"{tool_message.get('name', 'tool')}: {tool_content}"
                    )
        for line in attempt:
            if line and line not in deduped:
                deduped.append(line)
        if len(deduped) >= limit:
            break
    return deduped[:limit]


def _matched_check_details(
    messages: list[dict[str, Any]],
    *,
    match_key: str,
    index_key: str,
    payload_key: str,
    score_key: str,
) -> dict[int, dict[str, Any]]:
    details_by_idx: dict[int, dict[str, Any]] = {}
    for message_index, message in enumerate(messages):
        for detail_key in ("tool_details", "assistant_details"):
            detail = message.get(detail_key) or {}
            for match in detail.get(match_key, []) or []:
                if not isinstance(match, dict):
                    continue
                idx = match.get(index_key)
                if idx is None:
                    continue
                idx_int = int(idx)
                payload = match.get(payload_key) or {}
                constraints = payload.get("snapshot_constraints", [])
                entry = details_by_idx.setdefault(
                    idx_int,
                    {
                        "description": _milestone_desc(constraints),
                        "target_lines": _milestone_target_lines(constraints),
                        "observed_lines": [],
                        "constraints": constraints,
                        "score": None,
                    },
                )
                if not entry.get("description"):
                    entry["description"] = _milestone_desc(constraints)
                if not entry.get("target_lines"):
                    entry["target_lines"] = _milestone_target_lines(constraints)
                if not entry.get("constraints"):
                    entry["constraints"] = constraints
                for line in _observed_lines_for_message(
                    messages, message_index, constraints=constraints
                ):
                    if line not in entry["observed_lines"]:
                        entry["observed_lines"].append(line)
                sim = match.get(score_key)
                if sim is not None:
                    entry["score"] = float(sim)
    return details_by_idx


def _milestones_from_result(
    result: dict[str, Any],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets_by_idx = _matched_check_details(
        messages,
        match_key="milestone_matches",
        index_key="milestone_index",
        payload_key="milestone",
        score_key="milestone_similarity",
    )
    mapping = result.get("milestone_mapping") or {}
    if mapping:
        milestones: list[dict[str, Any]] = []
        for idx_str in sorted(mapping.keys(), key=int):
            idx = int(idx_str)
            entry = mapping[idx_str]
            score = (
                float(entry[1])
                if isinstance(entry, (list, tuple)) and len(entry) >= 2
                else 0.0
            )
            info = targets_by_idx.get(idx, {})
            observed_lines = list(info.get("observed_lines", []))
            state_lines = _database_update_observed_lines_across_messages(
                messages,
                constraints=info.get("constraints", []),
            )
            if state_lines:
                observed_lines = state_lines
            milestones.append(
                {
                    "passed": score >= 0.999,
                    "score": score,
                    "description": info.get("description", f"Milestone {idx + 1}"),
                    "target_lines": info.get("target_lines", []),
                    "observed_lines": observed_lines,
                }
            )
        return milestones
    seen: dict[int, dict[str, Any]] = {}
    for idx, info in targets_by_idx.items():
        sim = info.get("score")
        observed_lines = list(info.get("observed_lines", []))
        state_lines = _database_update_observed_lines_across_messages(
            messages,
            constraints=info.get("constraints", []),
        )
        if state_lines:
            observed_lines = state_lines
        seen[idx] = {
            "passed": bool(float(sim) >= 0.999) if sim is not None else None,
            "score": float(sim) if sim is not None else None,
            "description": info.get("description", f"Milestone {idx + 1}"),
            "target_lines": info.get("target_lines", []),
            "observed_lines": observed_lines,
        }
    return [seen[k] for k in sorted(seen.keys())]


def _minefields_from_result(
    result: dict[str, Any],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    details_by_idx = _matched_check_details(
        messages,
        match_key="minefield_matches",
        index_key="minefield_index",
        payload_key="minefield",
        score_key="minefield_similarity",
    )
    mapping = result.get("minefield_mapping") or {}
    if mapping:
        minefields: list[dict[str, Any]] = []
        for idx_str in sorted(mapping.keys(), key=int):
            idx = int(idx_str)
            entry = mapping[idx_str]
            score = (
                float(entry[1])
                if isinstance(entry, (list, tuple)) and len(entry) >= 2
                else 0.0
            )
            info = details_by_idx.get(idx, {})
            minefields.append(
                {
                    "triggered": score > 0,
                    "score": score,
                    "description": info.get("description", f"Guardrail {idx + 1}"),
                    "target_lines": info.get("target_lines", []),
                    "observed_lines": info.get("observed_lines", []),
                }
            )
        return minefields
    minefields = []
    for idx, info in sorted(details_by_idx.items()):
        score = float(info["score"]) if info.get("score") is not None else 0.0
        minefields.append(
            {
                "triggered": score > 0,
                "score": score if info.get("score") is not None else None,
                "description": info.get("description", f"Guardrail {idx + 1}"),
                "target_lines": info.get("target_lines", []),
                "observed_lines": info.get("observed_lines", []),
            }
        )
    return minefields


def _agent_action_summary(messages: list[dict[str, Any]]) -> str:
    prefixes = (
        "modify_",
        "set_",
        "add_",
        "update_",
        "delete_",
        "remove_",
        "create_",
        "send_",
    )
    skip_keys = {"reminder_id", "contact_id", "message_id", "event_id"}
    actions: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function", {})
            name = str(fn.get("name", ""))
            if not any(name.startswith(p) for p in prefixes):
                continue
            try:
                args = json.loads(fn.get("arguments", "{}"))
                key_args = {
                    k: v
                    for k, v in args.items()
                    if k not in skip_keys and v is not None
                }
                kv = ", ".join(f"{k}={v}" for k, v in list(key_args.items())[:4])
                actions.append(f"{name}({kv})" if kv else name)
            except Exception:
                actions.append(name)
    if actions:
        return "\n".join(actions[-3:])
    for message in reversed(messages):
        if message.get("role") == "assistant":
            content = _compact_content(message.get("content"), limit=400)
            if content:
                return content
    return "—"


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
    milestones: list[dict[str, Any]],
    minefields: list[dict[str, Any]],
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
    observed_lines: list[str] = []
    expected_lines: list[str] = []
    for index, milestone in enumerate(milestones, start=1):
        for line in milestone.get("observed_lines", [])[:2]:
            observed_lines.append(f"Milestone {index} observed: {line}")
        targets = milestone.get("target_lines", [])
        expected_lines.append(
            f"Milestone {index}: {'; '.join(targets) if targets else milestone.get('description', 'Milestone check')}"
        )
    for index, minefield in enumerate(minefields, start=1):
        for line in minefield.get("observed_lines", [])[:2]:
            observed_lines.append(f"Guardrail {index} triggered: {line}")
        targets = minefield.get("target_lines", [])
        expected_lines.append(
            f"Guardrail {index}: avoid {'; '.join(targets) if targets else minefield.get('description', 'Guardrail violation')}"
        )
    deduped_observed: list[str] = []
    for line in observed_lines:
        if line not in deduped_observed:
            deduped_observed.append(line)
    deduped_expected: list[str] = []
    for line in expected_lines:
        if line not in deduped_expected:
            deduped_expected.append(line)
    return {
        "agent_final_answer": final_answer,
        "agent_actions": _agent_action_summary(messages),
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
        "observed_evidence": (
            "\n".join(deduped_observed)
            or "\n".join(result_parts)
            or final_answer
            or "—"
        ),
        "expected_truth": (
            "\n".join(deduped_expected)
            or "\n".join(_expected_answers_from_messages(messages))
            or "State/tool milestone-scored target; inspect messages and tool evidence."
        ),
        "scenario": scenario,
    }


def _build_evaluation_payload(
    result: dict[str, Any] | None,
    milestones: list[dict[str, Any]],
    minefields: list[dict[str, Any]],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    required_score = None if result is None else result.get("milestone_similarity")
    forbidden_score = None if result is None else result.get("minefield_similarity")
    final_score = None if result is None else result.get("similarity")
    checks: list[dict[str, Any]] = []
    for index, milestone in enumerate(milestones, start=1):
        score = milestone.get("score")
        if score is None:
            status = "pending"
        elif float(score) >= 0.999:
            status = "matched"
        elif float(score) > 0:
            status = "partial"
        else:
            status = "missed"
        checks.append(
            {
                "kind": "required",
                "index": index,
                "status": status,
                "score": score,
                "label": milestone.get("description") or f"Required {index}",
                "observed": milestone.get("observed_lines") or ["No matching evidence"],
                "expected": milestone.get("target_lines")
                or [milestone.get("description") or f"Required {index}"],
            }
        )
    for index, minefield in enumerate(minefields, start=1):
        triggered = bool(minefield.get("triggered"))
        checks.append(
            {
                "kind": "forbidden",
                "index": index,
                "status": "triggered" if triggered else "clear",
                "score": minefield.get("score"),
                "label": minefield.get("description") or f"Forbidden {index}",
                "observed": minefield.get("observed_lines")
                or (
                    ["No forbidden state observed"]
                    if not triggered
                    else ["Forbidden match observed"]
                ),
                "expected": minefield.get("target_lines")
                or [minefield.get("description") or f"Forbidden {index}"],
            }
        )
    for check in checks:
        if check["kind"] != "required":
            continue
        expected_tool_names: list[str] = []
        for line in check["expected"]:
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\(", str(line))
            if match:
                expected_tool_names.append(match.group(1))
        # Try to preserve existing tool-attempt evidence for tool-expected milestones.
        if check["status"] == "missed" and expected_tool_names:
            fallback_observed: list[str] = []
            for msg_index, message in enumerate(messages):
                content = str(message.get("content") or "")
                if message.get("role") == "assistant" and any(
                    f"{tool_name}(" in content for tool_name in expected_tool_names
                ):
                    current_attempt: list[str] = []
                    if "\n\n" in content:
                        first, second = content.split("\n\n", 1)
                        if first.strip() == second.strip():
                            content = first
                    current_attempt.append(content)
                    if msg_index + 1 < len(messages):
                        tool_message = messages[msg_index + 1]
                        if (
                            tool_message.get("role") == "tool"
                            and tool_message.get("name") in expected_tool_names
                        ):
                            current_attempt.append(
                                f"{tool_message['name']}: {tool_message.get('content') or '[empty]'}"
                            )
                    fallback_observed = current_attempt
            if fallback_observed:
                check["observed"] = fallback_observed
                continue
        # If the scorer gave a non-zero score but no line evidence was captured,
        # try recovering assistant/tool traces that match the expected payload
        # text closely.
        if (
            check["status"] in {"partial", "matched"}
            and check["score"] is not None
            and float(check["score"]) > 0
            and check["observed"] == ["No matching evidence"]
        ):
            fallback_observed = _expected_check_fallback_lines(
                check["expected"], messages
            )
            check["observed"] = fallback_observed or ["No matching evidence"]
    return {
        "final_score": final_score,
        "required_score": required_score,
        "forbidden_score": forbidden_score,
        "required_passed": sum(
            1 for milestone in milestones if milestone.get("passed") is True
        ),
        "required_total": len(milestones),
        "forbidden_triggered": sum(
            1 for minefield in minefields if minefield.get("triggered")
        ),
        "forbidden_total": len(minefields),
        "blocked_by_guardrail": bool(
            forbidden_score is not None and float(forbidden_score) > 0
        ),
        "checks": checks,
    }


def _task_focus_rows(
    run_root: Path,
    run_dir: Path | None,
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
        try:
            relative_parts = run_dir.relative_to(run_root).parts
        except ValueError:
            relative_parts = ()
        if relative_parts:
            phase = relative_parts[0]
        else:
            path_hint = "/".join(run_dir.parts[-3:]).lower()
            phase = "control" if "control" in path_hint else "candidate"
        milestones = _milestones_from_result(result or {}, raw_messages)
        minefields = _minefields_from_result(result or {}, raw_messages)
        control_cache = (
            result.get("control_cache", {}) if isinstance(result, dict) else {}
        )
        control_cache_source = (
            result.get("control_cache_source") if isinstance(result, dict) else None
        ) or (control_cache.get("source") if isinstance(control_cache, dict) else None)
        transcript_source = None
        if not raw_messages and control_cache_source == "cached":
            raw_messages, transcript_source = _cached_control_transcript(control_cache)
            if raw_messages:
                milestones = _milestones_from_result(result or {}, raw_messages)
                minefields = _minefields_from_result(result or {}, raw_messages)
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
                "control_cache_source": control_cache_source,
                "control_cache": control_cache,
                "transcript_source": transcript_source,
                "similarity": None if result is None else result.get("similarity"),
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
                "score": None if result is None else result.get("similarity"),
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
                "milestones": milestones,
                "minefields": minefields,
                "evaluation": _build_evaluation_payload(
                    result,
                    milestones,
                    minefields,
                    [
                        _serialize_message(index, message, generated_set)
                        for index, message in enumerate(raw_messages)
                    ],
                ),
                "outcome": _task_outcome(
                    raw_messages,
                    result,
                    scenario,
                    milestones,
                    minefields,
                ),
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

    The Task Focus dashboard needs to show baseline and SAGE progress
    separately. During active runs, the runner writes arm status files before a
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

    control_mean = mean_value(0, "similarity")
    candidate_mean = mean_value(1, "similarity")
    control_outcome_mean = mean_value(0, "outcome_similarity")
    candidate_outcome_mean = mean_value(1, "outcome_similarity")
    delta = (
        candidate_mean - control_mean
        if control_mean is not None and candidate_mean is not None
        else None
    )
    outcome_delta = (
        candidate_outcome_mean - control_outcome_mean
        if control_outcome_mean is not None and candidate_outcome_mean is not None
        else None
    )
    lift_percent = None
    if delta is not None and control_mean is not None and control_mean != 0:
        lift_percent = (delta / control_mean) * 100
    return {
        "balanced_completed": len(complete_pairs),
        "balanced_control_mean_similarity": control_mean,
        "balanced_candidate_mean_similarity": candidate_mean,
        "balanced_delta": delta,
        "balanced_lift_percent": lift_percent,
        "balanced_control_mean_outcome_similarity": control_outcome_mean,
        "balanced_candidate_mean_outcome_similarity": candidate_outcome_mean,
        "balanced_outcome_delta": outcome_delta,
    }


def _write_task_focus_dashboard(
    dashboard_dir: Path,
    run_root: Path,
    data: dict[str, Any],
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> dict[str, Any]:
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
        "control_cache": data.get("control_cache"),
        "cohort_preflight": data.get("cohort_preflight"),
        "summary": {
            "scenario_count": data.get("scenario_count"),
            "control_completed": data.get("control", {}).get("scenario_count"),
            "control_mean_similarity": data.get("control", {}).get("mean_similarity"),
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
            "candidate_mean_similarity": data.get("candidate", {}).get(
                "mean_similarity"
            ),
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
            "current_mean_similarity": current.get("mean_similarity"),
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
    (dashboard_dir / "task_focus_data.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "task_focus.html").write_text(TASK_FOCUS_HTML, encoding="utf-8")
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
        canonical_delta = _optional_float(row.get("delta"))
        outcome_delta = _optional_float(row.get("outcome_delta"))
        if canonical_delta is None and outcome_delta is None:
            continue
        for tool in tools:
            tool_name = str(tool)
            entry = stats.setdefault(
                tool_name,
                {
                    "scenarios": set(),
                    "canonical_deltas": [],
                    "outcome_deltas": [],
                },
            )
            entry["scenarios"].add(scenario)
            if canonical_delta is not None:
                entry["canonical_deltas"].append(canonical_delta)
            if outcome_delta is not None:
                entry["outcome_deltas"].append(outcome_delta)

    result: dict[str, dict[str, Any]] = {}
    for tool, raw in stats.items():
        canonical = list(raw["canonical_deltas"])
        outcome = list(raw["outcome_deltas"])
        result[tool] = {
            "scenario_count": len(raw["scenarios"]),
            "mean_canonical_delta": _mean_float(canonical),
            "mean_outcome_delta": _mean_float(outcome),
            "canonical_gains": sum(1 for value in canonical if value > 0),
            "canonical_regressions": sum(1 for value in canonical if value < 0),
            "canonical_preserved": sum(1 for value in canonical if value == 0),
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
                "called_subset_mean_canonical_delta": called_subset.get(
                    "mean_canonical_delta"
                ),
                "called_subset_mean_outcome_delta": called_subset.get(
                    "mean_outcome_delta"
                ),
                "canonical_gains": called_subset.get("canonical_gains"),
                "canonical_regressions": called_subset.get("canonical_regressions"),
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
                    "called_subset_mean_canonical_delta": stats.get(
                        "mean_canonical_delta"
                    ),
                    "called_subset_mean_outcome_delta": stats.get("mean_outcome_delta"),
                    "canonical_gains": stats.get("canonical_gains"),
                    "canonical_regressions": stats.get("canonical_regressions"),
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

    Task Focus and the underlying run artifacts intentionally retain the legacy
    evaluator diagnostics. Task Compare is publication-facing and must expose
    only outcome performance, alongside its routing and transcript evidence.
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
    focus_payload: dict[str, Any],
) -> None:
    payload = _sanitize_task_compare_payload(
        {
            **focus_payload,
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
        c_score = float(c_row.get("similarity", 0.0)) if c_row else None
        s_score = float(s_row.get("similarity", 0.0)) if s_row else None
        c_outcome = _optional_float(c_row.get("outcome_similarity")) if c_row else None
        s_outcome = _optional_float(s_row.get("outcome_similarity")) if s_row else None
        c_cache = c_row.get("control_cache") if isinstance(c_row, dict) else {}
        c_cache_source = c_row.get("control_cache_source") or (
            c_cache.get("source") if isinstance(c_cache, dict) else None
        )
        delta = (
            (s_score - c_score) if c_score is not None and s_score is not None else None
        )
        outcome_delta = (
            s_outcome - c_outcome
            if c_outcome is not None and s_outcome is not None
            else None
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
                "control_outcome_similarity": c_outcome,
                "candidate_outcome_similarity": s_outcome,
                "outcome_delta": outcome_delta,
                "status": status,
                "control_turns": c_row.get("turn_count"),
                "candidate_turns": s_row.get("turn_count"),
                "control_llm_call_count": c_row.get("llm_call_count"),
                "candidate_llm_call_count": s_row.get("llm_call_count"),
                "control_llm_total_tokens": c_row.get("llm_total_tokens"),
                "candidate_llm_total_tokens": s_row.get("llm_total_tokens"),
                "control_exception": c_row.get("exception_type"),
                "candidate_exception": s_row.get("exception_type"),
                "control_cache_source": c_cache_source,
                "control_cache": c_cache,
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
        "mean_similarity_delta": 0.0,
        "outcome_scenario_count": 0,
        "mean_outcome_similarity_delta": None,
        "gain_count": 0,
        "regression_count": 0,
        "preserved_count": 0,
        "outcome_gain_count": 0,
        "outcome_regression_count": 0,
        "outcome_preserved_count": 0,
        "gains": [],
        "regressions": [],
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
        "control_cache": _read_json(run_root / "control_cache_report.json"),
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "control": comparison.get("control", {}),
        "candidate": comparison.get("candidate", {}),
        "comparison": {
            key: comparison.get(key)
            for key in (
                "gain_count",
                "regression_count",
                "preserved_count",
                "outcome_gain_count",
                "outcome_regression_count",
                "outcome_preserved_count",
            )
        },
        "mean_similarity_delta": comparison.get("mean_similarity_delta", 0.0),
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
    (dashboard_dir / "data.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "index.html").write_text(DASHBOARD_HTML, encoding="utf-8")
    task_focus_payload = _write_task_focus_dashboard(
        dashboard_dir,
        run_root,
        data,
        control_dir,
        candidate_dir,
    )
    _write_task_compare_dashboard(dashboard_dir, run_root, data, task_focus_payload)
    _write_latest_pointer(
        dashboard_dir / "task_compare.html",
        name="latest_sage_ts.html",
    )
    _write_latest_pointer(
        dashboard_dir / "task_focus.html",
        name="latest_sage_ts_task_focus.html",
    )
    _write_latest_pointer(
        dashboard_dir / "index.html",
        name="latest_sage_ts_standard.html",
    )
    _write_latest_pointer(
        dashboard_dir / "task_compare.html",
        name="latest_sage_ts_task_compare.html",
    )
    return dashboard_dir / "index.html"


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
    label = (
        "Open latest ToolSandbox SAGE dashboard"
        if "task_focus" not in name
        else "Open latest ToolSandbox SAGE task-focus dashboard"
    )
    (latest_dir / name).write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={rel}">
<a href="{rel}">{label}</a>
""",
        encoding="utf-8",
    )
