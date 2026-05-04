"""Claim-grade helper contribution summaries for paired SAGE runs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sage_ts.evaluation.run_metrics import _read_json, _read_jsonl, _scenario_rows


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def _registry_tool_names(registry_dir: Path | None) -> list[str]:
    if registry_dir is None:
        return []
    manifest = _read_json(registry_dir / "registry_manifest.json")
    tools = manifest.get("tools", {})
    return sorted(str(name) for name in tools) if isinstance(tools, dict) else []


def _runtime_bundle_sizes(candidate_dir: Path) -> dict[str, Any]:
    rows = _read_jsonl(candidate_dir / "scenario_tool_visibility.jsonl")
    sizes = [len(row.get("generated_tools", []) or []) for row in rows]
    available_sizes = [len(row.get("available_tools", []) or []) for row in rows]
    return {
        "scenario_count": len(rows),
        "mean_generated_tool_bundle_size": _mean(float(size) for size in sizes),
        "max_generated_tool_bundle_size": max(sizes, default=0),
        "mean_available_tool_count": _mean(float(size) for size in available_sizes),
        "max_available_tool_count": max(available_sizes, default=0),
    }


def _scenario_deltas(
    control_dir: Path, candidate_dir: Path
) -> dict[str, dict[str, Any]]:
    control_rows = {str(row["name"]): row for row in _scenario_rows(control_dir)}
    candidate_rows = {str(row["name"]): row for row in _scenario_rows(candidate_dir)}
    shared = [name for name in control_rows if name in candidate_rows]
    deltas: dict[str, dict[str, Any]] = {}
    for name in shared:
        control_similarity = float(control_rows[name].get("similarity", 0.0) or 0.0)
        candidate_similarity = float(candidate_rows[name].get("similarity", 0.0) or 0.0)
        control_outcome = _optional_float(control_rows[name].get("outcome_similarity"))
        candidate_outcome = _optional_float(
            candidate_rows[name].get("outcome_similarity")
        )
        deltas[name] = {
            "canonical_delta": candidate_similarity - control_similarity,
            "outcome_delta": (
                candidate_outcome - control_outcome
                if control_outcome is not None and candidate_outcome is not None
                else None
            ),
            "candidate_exception_type": candidate_rows[name].get("exception_type"),
            "control_exception_type": control_rows[name].get("exception_type"),
        }
    return deltas


def _subset_stats(
    scenarios: set[str], deltas_by_scenario: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows = [
        deltas_by_scenario[name]
        for name in sorted(scenarios)
        if name in deltas_by_scenario
    ]
    canonical = [float(row["canonical_delta"]) for row in rows]
    outcome = [
        row["outcome_delta"] for row in rows if row.get("outcome_delta") is not None
    ]
    outcome_values = [float(value) for value in outcome]
    return {
        "scenario_count": len(rows),
        "scenarios": sorted(name for name in scenarios if name in deltas_by_scenario),
        "mean_canonical_delta": _mean(canonical),
        "mean_outcome_delta": _mean(outcome_values),
        "canonical_gains": sum(1 for value in canonical if value > 0),
        "canonical_regressions": sum(1 for value in canonical if value < 0),
        "canonical_preserved": sum(1 for value in canonical if value == 0),
        "outcome_gains": sum(1 for value in outcome_values if value > 0),
        "outcome_regressions": sum(1 for value in outcome_values if value < 0),
        "outcome_preserved": sum(1 for value in outcome_values if value == 0),
    }


def build_helper_contribution_summary(
    control_dir: Path,
    candidate_dir: Path,
    *,
    registry_dir: Path | None = None,
) -> dict[str, Any]:
    """Build per-helper contribution evidence from paired run artifacts."""

    deltas_by_scenario = _scenario_deltas(control_dir, candidate_dir)
    all_scenarios = set(deltas_by_scenario)
    selection = _read_jsonl(candidate_dir / "scenario_tool_selection.jsonl")
    visibility = _read_jsonl(candidate_dir / "scenario_tool_visibility.jsonl")
    births = _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
    side_effect_rows = _read_jsonl(
        candidate_dir / "side_effect_preservation_report.jsonl"
    )
    candidate_metrics = _read_json(candidate_dir / "openai_response_cache_metrics.json")
    prompt_metrics = _read_json(candidate_dir / "prompt_cache_metrics.json")
    registry_tools = set(_registry_tool_names(registry_dir))
    accepted_tools = {
        str(event.get("tool_name"))
        for event in births
        if event.get("accepted") is True and event.get("tool_name")
    }
    helper_names = set(registry_tools) | accepted_tools
    helper_names.update(
        str(tool)
        for row in selection
        for key in (
            "generated_tools_visible",
            "generated_tools_called",
            "generated_tools_failed",
            "generated_tools_attempted",
        )
        for tool in (row.get(key, []) or [])
    )
    visible_by_helper: dict[str, set[str]] = defaultdict(set)
    called_by_helper: dict[str, set[str]] = defaultdict(set)
    failed_by_helper: dict[str, set[str]] = defaultdict(set)
    attempted_by_helper: dict[str, set[str]] = defaultdict(set)
    for row in selection:
        scenario = str(row.get("scenario", ""))
        if not scenario:
            continue
        for tool in row.get("generated_tools_visible", []) or []:
            visible_by_helper[str(tool)].add(scenario)
        for tool in row.get("generated_tools_called", []) or []:
            called_by_helper[str(tool)].add(scenario)
        for tool in row.get("generated_tools_failed", []) or []:
            failed_by_helper[str(tool)].add(scenario)
        for tool in row.get("generated_tools_attempted", []) or []:
            attempted_by_helper[str(tool)].add(scenario)
    side_effect_incidents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in side_effect_rows:
        scenario = str(row.get("scenario", ""))
        for tool in row.get("side_effect_preservation_failures", []) or []:
            side_effect_incidents[str(tool)].append({"scenario": scenario, "row": row})
    per_helper: dict[str, Any] = {}
    for helper in sorted(helper_names):
        visible = visible_by_helper.get(helper, set())
        called = called_by_helper.get(helper, set())
        failed = failed_by_helper.get(helper, set())
        attempted = attempted_by_helper.get(helper, set())
        visible_not_called = visible - called
        hidden = all_scenarios - visible
        runtime_incidents = [
            {
                "scenario": scenario,
                "exception_type": deltas_by_scenario[scenario].get(
                    "candidate_exception_type"
                ),
            }
            for scenario in sorted(visible | called | attempted | failed)
            if deltas_by_scenario.get(scenario, {}).get("candidate_exception_type")
        ]
        origin = "newly_generated" if helper in accepted_tools else "retained"
        per_helper[helper] = {
            "origin": origin,
            "visible_scenarios": sorted(visible),
            "called_scenarios": sorted(called),
            "visible_not_called_scenarios": sorted(visible_not_called),
            "failed_attempt_scenarios": sorted(failed),
            "attempted_scenarios": sorted(attempted),
            "hidden_no_call_scenarios": sorted(hidden),
            "visible_count": len(visible),
            "called_count": len(called),
            "visible_not_called_count": len(visible_not_called),
            "failed_attempt_count": len(failed),
            "hidden_no_call_count": len(hidden),
            "called_subset": _subset_stats(called, deltas_by_scenario),
            "visible_not_called_subset": _subset_stats(
                visible_not_called, deltas_by_scenario
            ),
            "hidden_no_call_subset": _subset_stats(hidden, deltas_by_scenario),
            "failed_attempt_subset": _subset_stats(failed, deltas_by_scenario),
            "side_effect_incidents": side_effect_incidents.get(helper, []),
            "runtime_incidents": runtime_incidents,
        }
    accepted_but_uncalled = sorted(
        tool for tool in accepted_tools if not called_by_helper.get(tool)
    )
    retained_called = sorted(
        helper
        for helper, data in per_helper.items()
        if data["origin"] == "retained" and data["called_count"] > 0
    )
    newly_generated_called = sorted(
        helper
        for helper, data in per_helper.items()
        if data["origin"] == "newly_generated" and data["called_count"] > 0
    )
    return {
        "control_dir": str(control_dir),
        "candidate_dir": str(candidate_dir),
        "registry_dir": str(registry_dir) if registry_dir else None,
        "scenario_count": len(all_scenarios),
        "helpers": per_helper,
        "accepted_tools": sorted(accepted_tools),
        "accepted_but_uncalled_tools": accepted_but_uncalled,
        "retained_helper_called_tools": retained_called,
        "newly_generated_helper_called_tools": newly_generated_called,
        "registry_size": len(registry_tools),
        "runtime_bundle_size": _runtime_bundle_sizes(candidate_dir),
        "compute_cache_token_metrics": {
            "candidate_openai_response_cache": candidate_metrics,
            "candidate_prompt_cache": prompt_metrics,
        },
        "selection_event_count": len(selection),
        "visibility_event_count": len(visibility),
    }


def write_helper_contribution_summary(
    control_dir: Path,
    candidate_dir: Path,
    output_path: Path,
    *,
    registry_dir: Path | None = None,
) -> dict[str, Any]:
    summary = build_helper_contribution_summary(
        control_dir,
        candidate_dir,
        registry_dir=registry_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
