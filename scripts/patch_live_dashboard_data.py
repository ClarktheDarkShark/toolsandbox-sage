#!/usr/bin/env python
"""Enrich live task-compare dashboard data for an active SAGE run.

The protocol runner may not emit final helper contribution summaries until the
candidate arm finishes. This script derives a conservative live tool summary
from selection, reuse, birth, and side-effect preservation traces, then patches
``dashboard/task_compare_data.json`` atomically. It does not affect experiment
execution or scoring artifacts.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _latest_arm_dir(run_root: Path, arm: str) -> Path | None:
    base = run_root / arm
    if not base.is_dir():
        return None
    dirs = sorted(path for path in base.iterdir() if path.is_dir())
    return dirs[-1] if dirs else None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _gain_count(values: list[float]) -> int:
    return sum(1 for value in values if value > 1e-9)


def _regression_count(values: list[float]) -> int:
    return sum(1 for value in values if value < -1e-9)


def _preserved_count(values: list[float]) -> int:
    return sum(1 for value in values if abs(value) <= 1e-9)


def _pair_maps(
    payload: dict[str, Any],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    pairs: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        scenario = str(pair.get("scenario") or "")
        control = pair.get("control") if isinstance(pair.get("control"), dict) else {}
        candidate = (
            pair.get("candidate") if isinstance(pair.get("candidate"), dict) else {}
        )
        if scenario and control and candidate:
            pairs[scenario] = (control, candidate)
    return pairs


def build_live_tool_summary(run_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    candidate_dir = _latest_arm_dir(run_root, "candidate")
    if candidate_dir is None:
        return (
            payload.get("tool_summary")
            if isinstance(payload.get("tool_summary"), dict)
            else {}
        )

    selection_rows = _read_jsonl(candidate_dir / "scenario_tool_selection.jsonl")
    birth_rows = _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
    side_effect_rows = _read_jsonl(
        candidate_dir / "side_effect_preservation_report.jsonl"
    )
    existing = (
        payload.get("tool_summary")
        if isinstance(payload.get("tool_summary"), dict)
        else {}
    )
    existing_tools = {
        str(tool.get("name")): dict(tool)
        for tool in existing.get("tools", []) or []
        if isinstance(tool, dict) and tool.get("name")
    }

    accepted = {
        str(row.get("tool_name") or row.get("tool") or "")
        for row in birth_rows
        if row.get("accepted") and (row.get("tool_name") or row.get("tool"))
    }

    visible_by_tool: dict[str, set[str]] = defaultdict(set)
    called_by_tool: dict[str, set[str]] = defaultdict(set)
    failed_by_tool: dict[str, set[str]] = defaultdict(set)
    runtime_by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in selection_rows:
        scenario = str(row.get("scenario") or "")
        if not scenario:
            continue
        for tool in row.get("generated_tools_visible") or []:
            visible_by_tool[str(tool)].add(scenario)
        for tool in row.get("generated_tools_called") or []:
            called_by_tool[str(tool)].add(scenario)
        for tool in row.get("generated_tools_failed") or []:
            name = str(tool)
            failed_by_tool[name].add(scenario)
            runtime_by_tool[name].append({"scenario": scenario, "row": row})

    side_effect_by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in side_effect_rows:
        scenario = str(row.get("scenario") or "")
        for tool in row.get("side_effect_preservation_failures") or []:
            side_effect_by_tool[str(tool)].append({"scenario": scenario, "row": row})

    pair_maps = _pair_maps(payload)
    tool_names = sorted(
        set(existing_tools)
        | accepted
        | set(visible_by_tool)
        | set(called_by_tool)
        | set(side_effect_by_tool)
    )
    tools: list[dict[str, Any]] = []
    for name in tool_names:
        base = existing_tools.get(name, {})
        called_scenarios = sorted(called_by_tool.get(name, set()))
        visible_scenarios = sorted(visible_by_tool.get(name, set()))
        visible_not_called = sorted(set(visible_scenarios) - set(called_scenarios))
        canonical_deltas: list[float] = []
        outcome_deltas: list[float] = []
        for scenario in called_scenarios:
            pair = pair_maps.get(scenario)
            if not pair:
                continue
            control, candidate = pair
            control_score = _numeric(control.get("similarity"))
            candidate_score = _numeric(candidate.get("similarity"))
            if control_score is not None and candidate_score is not None:
                canonical_deltas.append(candidate_score - control_score)
            control_outcome = _numeric(control.get("outcome_similarity"))
            candidate_outcome = _numeric(candidate.get("outcome_similarity"))
            if control_outcome is not None and candidate_outcome is not None:
                outcome_deltas.append(candidate_outcome - control_outcome)

        side_effect_count = len(side_effect_by_tool.get(name, []))
        runtime_count = len(runtime_by_tool.get(name, []))
        mean_outcome = _mean(outcome_deltas)
        if side_effect_count or runtime_count:
            decision = "inspect"
        elif called_scenarios and (mean_outcome or 0.0) > 0.0:
            decision = "positive called subset"
        elif called_scenarios:
            decision = "called; mixed or negative subset"
        elif visible_scenarios:
            decision = "visible; no natural call yet"
        else:
            decision = base.get("decision") or "accepted; not yet visible"

        tools.append(
            {
                **base,
                "name": name,
                "origin": base.get("origin")
                or ("generated" if name in accepted else "retained"),
                "visible_count": len(visible_scenarios),
                "called_count": len(called_scenarios),
                "visible_not_called_count": len(visible_not_called),
                "failed_attempt_count": len(failed_by_tool.get(name, set())),
                "called_subset_scenario_count": len(called_scenarios),
                "called_subset_mean_canonical_delta": _mean(canonical_deltas),
                "called_subset_mean_outcome_delta": mean_outcome,
                "canonical_gains": _gain_count(canonical_deltas),
                "canonical_regressions": _regression_count(canonical_deltas),
                "outcome_gains": _gain_count(outcome_deltas),
                "outcome_regressions": _regression_count(outcome_deltas),
                "outcome_preserved": _preserved_count(outcome_deltas),
                "side_effect_incident_count": side_effect_count,
                "runtime_incident_count": runtime_count,
                "decision": decision,
            }
        )

    tools.sort(
        key=lambda item: (
            -int(item.get("called_count") or 0),
            str(item.get("name") or ""),
        )
    )
    return {
        **existing,
        "tool_count": len(tools),
        "generated_tool_birth_count": len(accepted),
        "called_tool_count": sum(
            1 for tool in tools if int(tool.get("called_count") or 0) > 0
        ),
        "visible_tool_count": sum(
            1 for tool in tools if int(tool.get("visible_count") or 0) > 0
        ),
        "outcome_gains": sum(int(tool.get("outcome_gains") or 0) for tool in tools),
        "outcome_regressions": sum(
            int(tool.get("outcome_regressions") or 0) for tool in tools
        ),
        "side_effect_incident_count": sum(
            int(tool.get("side_effect_incident_count") or 0) for tool in tools
        ),
        "runtime_incident_count": sum(
            int(tool.get("runtime_incident_count") or 0) for tool in tools
        ),
        "accepted_tools": sorted(accepted),
        "accepted_but_uncalled_tools": sorted(
            name for name in accepted if not called_by_tool.get(name)
        ),
        "tools": tools,
        "live_enriched": True,
        "live_enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def patch_once(run_root: Path) -> bool:
    data_path = run_root / "dashboard" / "task_compare_data.json"
    payload = _read_json(data_path)
    if not payload:
        return False
    tool_summary = build_live_tool_summary(run_root, payload)
    if not tool_summary:
        return False
    old_marker = (
        payload.get("tool_summary", {}).get("live_enriched_at")
        if isinstance(payload.get("tool_summary"), dict)
        else None
    )
    payload["tool_summary"] = tool_summary
    payload["live_dashboard_data_patch"] = {
        "patched_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "live helper visibility/contribution/safety summary enrichment",
    }
    if tool_summary.get("live_enriched_at") == old_marker:
        return False
    _atomic_write_json(data_path, payload)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    args = parser.parse_args()

    while True:
        changed = patch_once(args.run_root)
        if changed:
            print(
                f"{datetime.now(timezone.utc).isoformat()} patched task_compare_data.json",
                flush=True,
            )
        if not args.watch:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
