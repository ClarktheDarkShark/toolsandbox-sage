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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_run(run_dir: Path, registry_dir: Path | None = None) -> dict[str, Any]:
    """Summarize one run using JSON artifacts only."""
    rows = _scenario_rows(run_dir)
    birth_events = _read_jsonl(run_dir / "tool_birth_events.jsonl")
    reuse_events = _read_jsonl(run_dir / "reuse_events.jsonl")
    run_events = _read_jsonl(run_dir / "sage_run_events.jsonl")
    visibility = _read_jsonl(run_dir / "scenario_tool_visibility.jsonl")
    selection = _read_jsonl(run_dir / "scenario_tool_selection.jsonl")
    prompt_cache_metrics = _read_json(run_dir / "prompt_cache_metrics.json")
    openai_response_cache_metrics = _read_json(
        run_dir / "openai_response_cache_metrics.json"
    )
    live_summary = _read_json(run_dir / "live_result_summary.json")
    registry_manifest = (
        _read_json(registry_dir / "registry_manifest.json") if registry_dir else {}
    )
    similarities = [float(row.get("similarity", 0.0)) for row in rows]
    outcome_similarities = [
        score
        for row in rows
        if (score := _optional_float(row.get("outcome_similarity"))) is not None
    ]
    successful = [row for row in rows if float(row.get("similarity", 0.0)) >= 1.0]
    outcome_successful = [score for score in outcome_similarities if score >= 1.0]
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
    attempted_selection = [
        event for event in selection if event.get("generated_tools_attempted")
    ]
    failed_attempt_selection = [
        event for event in selection if event.get("generated_tools_failed")
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
        "outcome_score_available_count": len(outcome_similarities),
        "outcome_success_count": len(outcome_successful),
        "mean_outcome_similarity": (
            sum(outcome_similarities) / len(outcome_similarities)
            if outcome_similarities
            else None
        ),
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
        "generated_tool_attempted_scenarios": len(attempted_selection),
        "generated_tool_failed_scenarios": len(failed_attempt_selection),
        "generated_tool_called_scenarios": len(called_selection),
        "generated_tool_visible_not_called_scenarios": len(ignored_selection),
        "generated_tool_selection_failures": [
            {
                "scenario": event.get("scenario"),
                "selection_status": event.get("selection_status"),
                "generated_tools_visible": event.get("generated_tools_visible", []),
                "generated_tools_attempted": event.get("generated_tools_attempted", []),
                "generated_tools_failed": event.get("generated_tools_failed", []),
                "generated_tools_called": event.get("generated_tools_called", []),
                "similarity": event.get("similarity"),
                "outcome_similarity": event.get("outcome_similarity"),
                "exception_type": event.get("exception_type"),
            }
            for event in selection
            if event.get("failure_after_selection")
            and event.get("selection_status") != "no_visible_generated_tools"
        ],
        "generated_tool_outcome_selection_failures": [
            {
                "scenario": event.get("scenario"),
                "selection_status": event.get("selection_status"),
                "generated_tools_visible": event.get("generated_tools_visible", []),
                "generated_tools_attempted": event.get("generated_tools_attempted", []),
                "generated_tools_failed": event.get("generated_tools_failed", []),
                "generated_tools_called": event.get("generated_tools_called", []),
                "similarity": event.get("similarity"),
                "outcome_similarity": event.get("outcome_similarity"),
                "exception_type": event.get("exception_type"),
            }
            for event in selection
            if event.get("failure_after_outcome_selection")
            and event.get("selection_status") != "no_visible_generated_tools"
        ],
        "cache_metrics": {
            "prompt_cache": prompt_cache_metrics,
            "openai_response_cache": openai_response_cache_metrics,
        },
        "failures": [
            {
                "scenario": row.get("name"),
                "similarity": row.get("similarity"),
                "outcome_similarity": row.get("outcome_similarity"),
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
    require_complete_match: bool = True,
) -> dict[str, Any]:
    """Compare matched control/candidate result summaries by scenario name."""
    control_list = _scenario_rows(control_dir)
    candidate_list = _scenario_rows(candidate_dir)
    control_names = [str(row["name"]) for row in control_list]
    candidate_names = [str(row["name"]) for row in candidate_list]
    if control_names != candidate_names:
        if not require_complete_match:
            candidate_name_set = set(candidate_names)
            shared_names = [
                name for name in control_names if name in candidate_name_set
            ]
            control_list = [
                row for row in control_list if str(row["name"]) in set(shared_names)
            ]
            candidate_by_name = {str(row["name"]): row for row in candidate_list}
            candidate_list = [candidate_by_name[name] for name in shared_names]
            control_names = shared_names
            candidate_names = shared_names
        else:
            raise ValueError(
                "paired_run_mismatch:"
                f"control_count={len(control_names)};"
                f"candidate_count={len(candidate_names)};"
                f"control_only={sorted(set(control_names) - set(candidate_names))[:10]};"
                f"candidate_only={sorted(set(candidate_names) - set(control_names))[:10]}"
            )
    control_rows = {str(row["name"]): row for row in control_list}
    candidate_rows = {str(row["name"]): row for row in candidate_list}
    shared = control_names
    deltas: list[dict[str, Any]] = []
    for name in shared:
        control_similarity = float(control_rows[name].get("similarity", 0.0))
        candidate_similarity = float(candidate_rows[name].get("similarity", 0.0))
        control_outcome_similarity = _optional_float(
            control_rows[name].get("outcome_similarity")
        )
        candidate_outcome_similarity = _optional_float(
            candidate_rows[name].get("outcome_similarity")
        )
        outcome_delta = (
            candidate_outcome_similarity - control_outcome_similarity
            if control_outcome_similarity is not None
            and candidate_outcome_similarity is not None
            else None
        )
        deltas.append(
            {
                "scenario": name,
                "control_similarity": control_similarity,
                "candidate_similarity": candidate_similarity,
                "delta": candidate_similarity - control_similarity,
                "control_outcome_similarity": control_outcome_similarity,
                "candidate_outcome_similarity": candidate_outcome_similarity,
                "outcome_delta": outcome_delta,
                "control_turns": control_rows[name].get("turn_count"),
                "candidate_turns": candidate_rows[name].get("turn_count"),
            }
        )
    gains = [row for row in deltas if row["delta"] > 0]
    regressions = [row for row in deltas if row["delta"] < 0]
    preserved = [row for row in deltas if row["delta"] == 0]
    outcome_deltas = [row for row in deltas if row["outcome_delta"] is not None]
    outcome_gains = [row for row in outcome_deltas if row["outcome_delta"] > 0]
    outcome_regressions = [row for row in outcome_deltas if row["outcome_delta"] < 0]
    outcome_preserved = [row for row in outcome_deltas if row["outcome_delta"] == 0]
    control_summary = summarize_run(control_dir)
    candidate_summary = summarize_run(candidate_dir, registry_dir=registry_dir)
    control_exact_successes = sum(
        1 for row in deltas if row["control_similarity"] >= 1.0
    )
    candidate_exact_successes = sum(
        1 for row in deltas if row["candidate_similarity"] >= 1.0
    )
    return {
        "control": control_summary,
        "candidate": candidate_summary,
        "scenario_count": len(shared),
        "control_mean_similarity": (
            sum(row["control_similarity"] for row in deltas) / len(deltas)
            if deltas
            else 0.0
        ),
        "candidate_mean_similarity": (
            sum(row["candidate_similarity"] for row in deltas) / len(deltas)
            if deltas
            else 0.0
        ),
        "mean_similarity_delta": (
            sum(row["delta"] for row in deltas) / len(deltas) if deltas else 0.0
        ),
        "control_exact_successes": control_exact_successes,
        "candidate_exact_successes": candidate_exact_successes,
        "exact_success_delta": candidate_exact_successes - control_exact_successes,
        "runtime_exception_count": control_summary["exception_count"]
        + candidate_summary["exception_count"],
        "outcome_scenario_count": len(outcome_deltas),
        "control_mean_outcome_similarity": (
            sum(
                float(row["control_outcome_similarity"])
                for row in outcome_deltas
                if row["control_outcome_similarity"] is not None
            )
            / len(outcome_deltas)
            if outcome_deltas
            else None
        ),
        "candidate_mean_outcome_similarity": (
            sum(
                float(row["candidate_outcome_similarity"])
                for row in outcome_deltas
                if row["candidate_outcome_similarity"] is not None
            )
            / len(outcome_deltas)
            if outcome_deltas
            else None
        ),
        "mean_outcome_similarity_delta": (
            sum(float(row["outcome_delta"]) for row in outcome_deltas)
            / len(outcome_deltas)
            if outcome_deltas
            else None
        ),
        "gain_count": len(gains),
        "regression_count": len(regressions),
        "preserved_count": len(preserved),
        "outcome_gain_count": len(outcome_gains),
        "outcome_regression_count": len(outcome_regressions),
        "outcome_preserved_count": len(outcome_preserved),
        "gains": gains,
        "regressions": regressions,
        "outcome_gains": outcome_gains,
        "outcome_regressions": outcome_regressions,
        "deltas": deltas,
    }
