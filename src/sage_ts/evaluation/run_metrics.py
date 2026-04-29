"""Metrics and paired comparisons for ToolSandbox SAGE runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _scenario_rows(run_dir: Path) -> list[dict[str, Any]]:
    final_summary = run_dir / "result_summary.json"
    live_summary = run_dir / "live_result_summary.json"
    source = final_summary if final_summary.exists() else live_summary
    return list(_read_json(source).get("per_scenario_results", []))


def summarize_run(run_dir: Path, registry_dir: Path | None = None) -> dict[str, Any]:
    """Summarize one run using JSON artifacts only."""
    rows = _scenario_rows(run_dir)
    birth_events = _read_jsonl(run_dir / "tool_birth_events.jsonl")
    reuse_events = _read_jsonl(run_dir / "reuse_events.jsonl")
    run_events = _read_jsonl(run_dir / "sage_run_events.jsonl")
    visibility = _read_jsonl(run_dir / "scenario_tool_visibility.jsonl")
    selection = _read_jsonl(run_dir / "scenario_tool_selection.jsonl")
    cache_metrics = _read_json(run_dir / "prompt_cache_metrics.json")
    live_summary = _read_json(run_dir / "live_result_summary.json")
    registry_manifest = (
        _read_json(registry_dir / "registry_manifest.json") if registry_dir else {}
    )
    similarities = [float(row.get("similarity", 0.0)) for row in rows]
    successful = [row for row in rows if float(row.get("similarity", 0.0)) >= 1.0]
    exceptions = [row for row in rows if row.get("exception_type")]
    accepted_births = [event for event in birth_events if event.get("accepted") is True]
    registry_loads = [
        event for event in run_events if event.get("event") == "registry_load"
    ]
    registry_finish = [
        event for event in run_events if event.get("event") == "run_finished"
    ]
    visible_generated = {
        tool
        for event in visibility
        for tool in event.get("generated_tools", [])
        if isinstance(tool, str)
    }
    called_selection = [
        event
        for event in selection
        if event.get("selection_status") == "generated_tool_called"
    ]
    ignored_selection = [
        event
        for event in selection
        if event.get("selection_status") == "generated_tool_visible_not_called"
    ]
    visible_selection = [
        event
        for event in selection
        if event.get("selection_status")
        in {"generated_tool_called", "generated_tool_visible_not_called"}
    ]
    return {
        "run_dir": str(run_dir),
        "scenario_count": len(rows),
        "planned_scenario_count": int(
            live_summary.get("scenario_count", len(rows)) or len(rows)
        ),
        "run_status": live_summary.get(
            "status",
            "complete" if (run_dir / "result_summary.json").exists() else "unknown",
        ),
        "success_count": len(successful),
        "mean_similarity": sum(similarities) / len(similarities)
        if similarities
        else 0.0,
        "total_turns": sum(int(row.get("turn_count", 0)) for row in rows),
        "exception_count": len(exceptions),
        "tool_generation_count": len(birth_events),
        "accepted_tool_count": len(accepted_births),
        "accepted_tools": [event.get("tool_name") for event in accepted_births],
        "reuse_count": len(reuse_events),
        "reuse_scenarios": [event.get("scenario") for event in reuse_events],
        "reused_tools": sorted({str(event.get("tool_name")) for event in reuse_events}),
        "registry_size_at_start": (
            int(registry_loads[0].get("registry_size", 0)) if registry_loads else 0
        ),
        "registry_size_at_end": (
            int(registry_finish[-1].get("final_registry_size", 0))
            if registry_finish
            else len(registry_manifest.get("tools", {}))
        ),
        "visible_generated_tools": sorted(visible_generated),
        "generated_tool_visible_scenarios": len(visible_selection),
        "generated_tool_called_scenarios": len(called_selection),
        "generated_tool_visible_not_called_scenarios": len(ignored_selection),
        "generated_tool_selection_failures": [
            {
                "scenario": event.get("scenario"),
                "selection_status": event.get("selection_status"),
                "generated_tools_visible": event.get("generated_tools_visible", []),
                "generated_tools_called": event.get("generated_tools_called", []),
                "similarity": event.get("similarity"),
                "exception_type": event.get("exception_type"),
            }
            for event in selection
            if event.get("failure_after_selection")
            and event.get("selection_status") != "no_visible_generated_tools"
        ],
        "cache_metrics": cache_metrics,
        "failures": [
            {
                "scenario": row.get("name"),
                "similarity": row.get("similarity"),
                "exception_type": row.get("exception_type"),
                "categories": row.get("categories", []),
            }
            for row in rows
            if float(row.get("similarity", 0.0)) < 1.0 or row.get("exception_type")
        ],
    }


def compare_runs(
    control_dir: Path,
    candidate_dir: Path,
    *,
    registry_dir: Path | None = None,
) -> dict[str, Any]:
    """Compare matched control/candidate result summaries by scenario name."""
    control_rows = {str(row["name"]): row for row in _scenario_rows(control_dir)}
    candidate_rows = {str(row["name"]): row for row in _scenario_rows(candidate_dir)}
    shared = [name for name in control_rows if name in candidate_rows]
    deltas: list[dict[str, Any]] = []
    for name in shared:
        control_similarity = float(control_rows[name].get("similarity", 0.0))
        candidate_similarity = float(candidate_rows[name].get("similarity", 0.0))
        deltas.append(
            {
                "scenario": name,
                "control_similarity": control_similarity,
                "candidate_similarity": candidate_similarity,
                "delta": candidate_similarity - control_similarity,
                "control_turns": control_rows[name].get("turn_count"),
                "candidate_turns": candidate_rows[name].get("turn_count"),
            }
        )
    gains = [row for row in deltas if row["delta"] > 0]
    regressions = [row for row in deltas if row["delta"] < 0]
    preserved = [row for row in deltas if row["delta"] == 0]
    return {
        "control": summarize_run(control_dir),
        "candidate": summarize_run(candidate_dir, registry_dir=registry_dir),
        "scenario_count": len(shared),
        "mean_similarity_delta": (
            sum(row["delta"] for row in deltas) / len(deltas) if deltas else 0.0
        ),
        "gain_count": len(gains),
        "regression_count": len(regressions),
        "preserved_count": len(preserved),
        "gains": gains,
        "regressions": regressions,
        "deltas": deltas,
    }
