#!/usr/bin/env python3
"""Aggregate Chapter 4 full-run artifacts into analysis-ready CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent_delta(candidate: Any, control: Any) -> float | None:
    candidate_f = _safe_float(candidate)
    control_f = _safe_float(control)
    if candidate_f is None or control_f in (None, 0.0):
        return None
    return (candidate_f - control_f) / control_f * 100.0


def _find_run_roots(search_roots: list[Path]) -> list[Path]:
    roots: set[Path] = set()
    for search_root in search_roots:
        if not search_root.exists():
            continue
        if (search_root / "paired_comparison.json").exists():
            roots.add(search_root)
            continue
        for comparison in search_root.rglob("paired_comparison.json"):
            roots.add(comparison.parent)
    return sorted(roots)


def _dashboard_url(run_root: Path) -> str:
    urls_path = run_root / "dashboard_urls.json"
    if urls_path.exists():
        urls = _load_json(urls_path)
        return str(
            urls.get("dashboard_task_compare_url") or urls.get("dashboard_url") or ""
        )
    manifest_path = run_root / "protocol_manifest.json"
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
        return str(
            manifest.get("dashboard_task_compare_url")
            or manifest.get("dashboard_url")
            or ""
        )
    return ""


def _run_id(run_root: Path) -> str:
    parent = run_root.parent.name
    name = run_root.name
    if name.startswith("online_build_full_"):
        return f"{parent}/{name}"
    return str(run_root)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def aggregate_run(
    run_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    paired = _load_json(run_root / "paired_comparison.json")
    dashboard_path = run_root / "dashboard" / "task_compare_data.json"
    dashboard_summary: dict[str, Any] = {}
    if dashboard_path.exists():
        dashboard_summary = _load_json(dashboard_path).get("summary", {})
    manifest: dict[str, Any] = {}
    manifest_path = run_root / "protocol_manifest.json"
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
    helper: dict[str, Any] = {}
    helper_path = run_root / "helper_contribution_summary.json"
    if helper_path.exists():
        helper = _load_json(helper_path)

    control_score = dashboard_summary.get(
        "balanced_control_mean_similarity",
        paired.get("control_mean_similarity"),
    )
    candidate_score = dashboard_summary.get(
        "balanced_candidate_mean_similarity",
        paired.get("candidate_mean_similarity"),
    )
    control_outcome = dashboard_summary.get(
        "balanced_control_mean_outcome_similarity",
        paired.get("control_mean_outcome_similarity"),
    )
    candidate_outcome = dashboard_summary.get(
        "balanced_candidate_mean_outcome_similarity",
        paired.get("candidate_mean_outcome_similarity"),
    )
    env = manifest.get("run_affecting_sage_env") or {}
    run_id = _run_id(run_root)

    run_row = {
        "run_id": run_id,
        "run_root": str(run_root),
        "dashboard_url": _dashboard_url(run_root),
        "agent": manifest.get("agent"),
        "user": manifest.get("user"),
        "generation_model": manifest.get("generation_model"),
        "scenario_count": manifest.get("scenario_count", paired.get("scenario_count")),
        "balanced_completed": dashboard_summary.get("balanced_completed"),
        "control_score": control_score,
        "candidate_score": candidate_score,
        "score_delta": (
            None
            if _safe_float(candidate_score) is None
            or _safe_float(control_score) is None
            else _safe_float(candidate_score) - _safe_float(control_score)
        ),
        "score_lift_percent": _percent_delta(candidate_score, control_score),
        "control_outcome": control_outcome,
        "candidate_outcome": candidate_outcome,
        "outcome_delta": (
            None
            if _safe_float(candidate_outcome) is None
            or _safe_float(control_outcome) is None
            else _safe_float(candidate_outcome) - _safe_float(control_outcome)
        ),
        "outcome_lift_percent": _percent_delta(candidate_outcome, control_outcome),
        "score_gain_count": paired.get("gain_count"),
        "score_regression_count": paired.get("regression_count"),
        "score_preserved_count": paired.get("preserved_count"),
        "outcome_gain_count": paired.get("outcome_gain_count"),
        "outcome_regression_count": paired.get("outcome_regression_count"),
        "outcome_preserved_count": paired.get("outcome_preserved_count"),
        "accepted_tools": dashboard_summary.get("accepted_tools"),
        "registry_size": helper.get("registry_size"),
        "tool_reuse_events": dashboard_summary.get("reuse_count"),
        "generated_tool_called_scenarios": dashboard_summary.get(
            "generated_tool_called_scenarios"
        ),
        "generated_tool_failed_scenarios": dashboard_summary.get(
            "generated_tool_failed_scenarios"
        ),
        "runtime_exceptions": dashboard_summary.get("current_exceptions"),
        "control_llm_calls": dashboard_summary.get("control_llm_call_count"),
        "candidate_llm_calls": dashboard_summary.get("candidate_llm_call_count"),
        "control_llm_tokens": dashboard_summary.get("control_llm_total_tokens"),
        "candidate_llm_tokens": dashboard_summary.get("candidate_llm_total_tokens"),
        "control_repository_whole_response_replay_calls": dashboard_summary.get(
            "control_llm_cached_call_count"
        ),
        "candidate_repository_whole_response_replay_calls": dashboard_summary.get(
            "candidate_llm_cached_call_count"
        ),
        "control_provider_cached_prompt_tokens": dashboard_summary.get(
            "control_llm_provider_cached_prompt_tokens"
        ),
        "candidate_provider_cached_prompt_tokens": dashboard_summary.get(
            "candidate_llm_provider_cached_prompt_tokens"
        ),
        "control_provider_cached_prompt_calls": dashboard_summary.get(
            "control_llm_provider_cached_prompt_call_count"
        ),
        "candidate_provider_cached_prompt_calls": dashboard_summary.get(
            "candidate_llm_provider_cached_prompt_call_count"
        ),
        "control_provider_cached_prompt_metadata_calls": dashboard_summary.get(
            "control_llm_provider_cached_prompt_tokens_available_count"
        ),
        "candidate_provider_cached_prompt_metadata_calls": dashboard_summary.get(
            "candidate_llm_provider_cached_prompt_tokens_available_count"
        ),
        "control_cache_mode": manifest.get("control_cache_mode"),
        "cached_control_tasks": manifest.get("cached_control_tasks"),
        "fresh_control_tasks": manifest.get("fresh_control_tasks"),
        "parallel_arms": manifest.get("parallel_arms"),
        "openai_response_cache_enabled": manifest.get("openai_response_cache_enabled"),
        "bridge_policy": env.get("SAGE_PRAXIS_BRIDGE_POLICY"),
        "tool_codegen_mode": env.get("SAGE_TOOL_CODEGEN_MODE"),
        "deterministic_codegen_disabled": env.get(
            "SAGE_DISABLE_DETERMINISTIC_TOOL_CODEGEN"
        ),
        "scenario_name_birth_disabled": env.get("SAGE_DISABLE_SCENARIO_NAME_BIRTH"),
        "scenario_name_routing_disabled": env.get("SAGE_DISABLE_SCENARIO_NAME_ROUTING"),
        "dynamic_generated_schema": env.get("SAGE_DYNAMIC_GENERATED_TOOL_SCHEMA"),
        "dynamic_generated_schema_max": env.get(
            "SAGE_DYNAMIC_GENERATED_TOOL_SCHEMA_MAX"
        ),
        "protocol_gate_passed": manifest.get("protocol_gate_passed"),
        "protocol_gate_reasons": ";".join(manifest.get("protocol_gate_reasons") or []),
    }

    task_rows: list[dict[str, Any]] = []
    for row in paired.get("deltas", []):
        task_rows.append(
            {
                "run_id": run_id,
                "run_root": str(run_root),
                "scenario": row.get("scenario"),
                "control_score": row.get("control_similarity"),
                "candidate_score": row.get("candidate_similarity"),
                "score_delta": row.get("delta"),
                "control_outcome": row.get("control_outcome_similarity"),
                "candidate_outcome": row.get("candidate_outcome_similarity"),
                "outcome_delta": row.get("outcome_delta"),
                "control_turns": row.get("control_turns"),
                "candidate_turns": row.get("candidate_turns"),
                "control_llm_calls": row.get("control_llm_call_count"),
                "candidate_llm_calls": row.get("candidate_llm_call_count"),
                "control_llm_tokens": row.get("control_llm_total_tokens"),
                "candidate_llm_tokens": row.get("candidate_llm_total_tokens"),
            }
        )

    tool_rows: list[dict[str, Any]] = []
    helpers = helper.get("helpers") or {}
    if isinstance(helpers, dict):
        for tool_name, payload in sorted(helpers.items()):
            if not isinstance(payload, dict):
                continue
            tool_rows.append(
                {
                    "run_id": run_id,
                    "run_root": str(run_root),
                    "tool_name": tool_name,
                    "visible_count": payload.get("visible_count"),
                    "called_count": payload.get("called_count"),
                    "attempted_count": payload.get("attempted_count"),
                    "failed_count": payload.get("failed_count"),
                    "visible_not_called_count": payload.get("visible_not_called_count"),
                    "side_effect_incident_count": payload.get(
                        "side_effect_incident_count"
                    ),
                    "called_score_delta_mean": payload.get("called_score_delta_mean"),
                    "called_outcome_delta_mean": payload.get(
                        "called_outcome_delta_mean"
                    ),
                    "visible_score_delta_mean": payload.get("visible_score_delta_mean"),
                    "visible_outcome_delta_mean": payload.get(
                        "visible_outcome_delta_mean"
                    ),
                    "harmful_called_count": payload.get("harmful_called_count"),
                    "helpful_called_count": payload.get("helpful_called_count"),
                    "decision": payload.get("decision"),
                    "decision_reason": payload.get("decision_reason"),
                }
            )

    return run_row, task_rows, tool_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        action="append",
        type=Path,
        default=[],
        help="Completed paired protocol run root containing paired_comparison.json.",
    )
    parser.add_argument(
        "--search-root",
        action="append",
        type=Path,
        default=[],
        help="Directory to search recursively for paired_comparison.json files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for CSV/JSON exports.",
    )
    args = parser.parse_args()

    search_roots = args.search_root or [Path("outputs/chapter4_4omini_full_runs")]
    run_roots = set(args.run_root) | set(_find_run_roots(search_roots))
    if not run_roots:
        raise SystemExit("No completed run roots found.")

    output_dir = (
        args.output_dir
        or Path("artifacts/chapter4_data_collection")
        / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    run_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    tool_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for run_root in sorted(run_roots):
        try:
            run_row, run_tasks, run_tools = aggregate_run(run_root)
        except Exception as exc:  # noqa: BLE001 - preserve batch progress.
            errors.append({"run_root": str(run_root), "error": repr(exc)})
            continue
        run_rows.append(run_row)
        task_rows.extend(run_tasks)
        tool_rows.extend(run_tools)

    run_fields = [
        "run_id",
        "run_root",
        "dashboard_url",
        "agent",
        "user",
        "generation_model",
        "scenario_count",
        "balanced_completed",
        "control_score",
        "candidate_score",
        "score_delta",
        "score_lift_percent",
        "control_outcome",
        "candidate_outcome",
        "outcome_delta",
        "outcome_lift_percent",
        "score_gain_count",
        "score_regression_count",
        "score_preserved_count",
        "outcome_gain_count",
        "outcome_regression_count",
        "outcome_preserved_count",
        "accepted_tools",
        "registry_size",
        "tool_reuse_events",
        "generated_tool_called_scenarios",
        "generated_tool_failed_scenarios",
        "runtime_exceptions",
        "control_llm_calls",
        "candidate_llm_calls",
        "control_llm_tokens",
        "candidate_llm_tokens",
        "control_repository_whole_response_replay_calls",
        "candidate_repository_whole_response_replay_calls",
        "control_provider_cached_prompt_tokens",
        "candidate_provider_cached_prompt_tokens",
        "control_provider_cached_prompt_calls",
        "candidate_provider_cached_prompt_calls",
        "control_provider_cached_prompt_metadata_calls",
        "candidate_provider_cached_prompt_metadata_calls",
        "control_cache_mode",
        "cached_control_tasks",
        "fresh_control_tasks",
        "parallel_arms",
        "openai_response_cache_enabled",
        "bridge_policy",
        "tool_codegen_mode",
        "deterministic_codegen_disabled",
        "scenario_name_birth_disabled",
        "scenario_name_routing_disabled",
        "dynamic_generated_schema",
        "dynamic_generated_schema_max",
        "protocol_gate_passed",
        "protocol_gate_reasons",
    ]
    task_fields = [
        "run_id",
        "run_root",
        "scenario",
        "control_score",
        "candidate_score",
        "score_delta",
        "control_outcome",
        "candidate_outcome",
        "outcome_delta",
        "control_turns",
        "candidate_turns",
        "control_llm_calls",
        "candidate_llm_calls",
        "control_llm_tokens",
        "candidate_llm_tokens",
    ]
    tool_fields = [
        "run_id",
        "run_root",
        "tool_name",
        "visible_count",
        "called_count",
        "attempted_count",
        "failed_count",
        "visible_not_called_count",
        "side_effect_incident_count",
        "called_score_delta_mean",
        "called_outcome_delta_mean",
        "visible_score_delta_mean",
        "visible_outcome_delta_mean",
        "harmful_called_count",
        "helpful_called_count",
        "decision",
        "decision_reason",
    ]

    _write_csv(output_dir / "run_summary.csv", run_rows, run_fields)
    _write_csv(output_dir / "task_deltas.csv", task_rows, task_fields)
    _write_csv(output_dir / "tool_contribution.csv", tool_rows, tool_fields)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_count": len(run_rows),
                "task_row_count": len(task_rows),
                "tool_row_count": len(tool_rows),
                "errors": errors,
                "run_roots": [str(path) for path in sorted(run_roots)],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(output_dir)
    print(f"runs={len(run_rows)} tasks={len(task_rows)} tools={len(tool_rows)}")
    if errors:
        print(f"errors={len(errors)}; see {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
