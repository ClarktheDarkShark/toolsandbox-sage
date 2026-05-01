"""Dashboard data exporters for ToolSandbox SAGE protocol runs."""

from __future__ import annotations

import json
import os
import re
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
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _extract_tool_names_from_trace(trace: Any) -> list[str]:
    try:
        parsed = json.loads(trace) if isinstance(trace, str) else trace
        if isinstance(parsed, list):
            return [
                c["tool_name"]
                for c in parsed
                if isinstance(c, dict) and c.get("tool_name")
            ]
        if isinstance(parsed, dict) and parsed.get("tool_name"):
            return [parsed["tool_name"]]
    except Exception:
        pass
    return []


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
        if check["kind"] != "required" or check["status"] != "missed":
            continue
        expected_tool_names: list[str] = []
        for line in check["expected"]:
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\(", str(line))
            if match:
                expected_tool_names.append(match.group(1))
        if not expected_tool_names:
            if not check["observed"]:
                check["observed"] = ["No matching evidence"]
            continue
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
        conversation = _read_json_value(
            run_dir / "trajectories" / scenario / "conversation.json", []
        )
        raw_messages = [m for m in conversation if isinstance(m, dict)]
        generated_tools = usage.get(scenario, [])
        generated_set = set(generated_tools)
        phase = run_dir.relative_to(run_root).parts[0]
        milestones = _milestones_from_result(result or {}, raw_messages)
        minefields = _minefields_from_result(result or {}, raw_messages)
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
            "control_mean_outcome_similarity": data.get("control", {}).get(
                "mean_outcome_similarity"
            ),
            "candidate_completed": data.get("candidate", {}).get("scenario_count"),
            "candidate_mean_similarity": data.get("candidate", {}).get(
                "mean_similarity"
            ),
            "candidate_mean_outcome_similarity": data.get("candidate", {}).get(
                "mean_outcome_similarity"
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
        c_outcome = _optional_float(c_row.get("outcome_similarity")) if c_row else None
        s_outcome = _optional_float(s_row.get("outcome_similarity")) if s_row else None
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
) -> Path:
    """Write dashboard HTML and data for a paired protocol run."""
    control_dir = _resolve_run_dir(control_dir)
    candidate_dir = _resolve_run_dir(candidate_dir)
    dashboard_dir = run_root / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
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
        "scenario_count": scenario_count,
        "cohort_preflight": _read_json(run_root / "cohort_preflight_report.json"),
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
    _write_task_focus_dashboard(
        dashboard_dir,
        run_root,
        data,
        control_dir,
        candidate_dir,
    )
    _write_latest_pointer(dashboard_dir / "index.html", name="latest_sage_ts.html")
    _write_latest_pointer(
        dashboard_dir / "task_focus.html",
        name="latest_sage_ts_task_focus.html",
    )
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
    opened = webbrowser.open_new_tab(url)
    # In non-interactive benchmark shells, webbrowser can return True even when
    # no visible browser tab is surfaced. On macOS, also hand the URL to the OS
    # opener so run dashboards reliably appear during campaign runs.
    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
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
