"""Metrics and paired comparisons for ToolSandbox SAGE runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _file_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _run_segment_wall_time_seconds(run_dir: Path) -> float | None:
    manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    started_at = _parse_datetime(manifest.get("started_at"))
    if started_at is None:
        return None

    live_summary_path = run_dir / "live_result_summary.json"
    live_summary = _read_json(live_summary_path)
    ended_at = (
        _parse_datetime(live_summary.get("updated_at"))
        or _file_mtime(run_dir / "result_summary.json")
        or _file_mtime(live_summary_path)
    )
    if ended_at is None:
        return None
    return max(0.0, (ended_at - started_at).total_seconds())


def _resume_checkpoint_wall_time_seconds(
    resume_dir: Path,
    completed_limit: int,
) -> float | None:
    if completed_limit <= 0:
        return 0.0
    manifest = _read_json(resume_dir.parent / "sage_ts_run_manifest.json")
    started_at = _parse_datetime(manifest.get("started_at"))
    if started_at is None:
        return None
    checkpoint_root = resume_dir / "registry_checkpoints"
    prefix = f"after_{completed_limit:04d}_"
    for checkpoint in sorted(checkpoint_root.glob(f"{prefix}*/checkpoint.json")):
        payload = _read_json(checkpoint)
        if _optional_int(payload.get("completed_count")) != completed_limit:
            continue
        checkpoint_at = _file_mtime(checkpoint)
        if checkpoint_at is None:
            continue
        offset = _resume_wall_time_offset_seconds(manifest)
        return offset + max(0.0, (checkpoint_at - started_at).total_seconds())
    return None


def _resume_wall_time_offset_seconds(manifest: dict[str, Any]) -> float:
    resume_from_dir = manifest.get("resume_from_dir")
    completed_limit = _optional_int(manifest.get("resume_completed_limit"))
    if not resume_from_dir or completed_limit is None:
        return 0.0
    resume_dir = Path(str(resume_from_dir))
    checkpoint_seconds = _resume_checkpoint_wall_time_seconds(
        resume_dir,
        completed_limit,
    )
    if checkpoint_seconds is not None:
        return checkpoint_seconds
    previous_seconds = _run_wall_time_seconds(resume_dir)
    return previous_seconds or 0.0


def _run_wall_time_seconds(run_dir: Path) -> float | None:
    segment_seconds = _run_segment_wall_time_seconds(run_dir)
    if segment_seconds is None:
        return None
    manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    return segment_seconds + _resume_wall_time_offset_seconds(manifest)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [_optional_int(row.get(key)) for row in rows if row.get(key) is not None]
    clean = [value for value in values if value is not None]
    return sum(clean) if clean else None


def _llm_usage_summary(rows: list[dict[str, Any]], run_dir: Path) -> dict[str, Any]:
    recorded_rows = [row for row in rows if row.get("llm_usage_recorded")]
    artifact_summary = _read_json(run_dir / "llm_usage_summary.json")
    if not recorded_rows and artifact_summary:
        return {
            "llm_usage_recorded": bool(artifact_summary.get("llm_usage_recorded")),
            "llm_call_count": artifact_summary.get("llm_call_count"),
            "llm_live_call_count": artifact_summary.get("llm_live_call_count"),
            "llm_cached_call_count": artifact_summary.get("llm_cached_call_count"),
            "llm_prompt_tokens": artifact_summary.get("llm_prompt_tokens"),
            "llm_completion_tokens": artifact_summary.get("llm_completion_tokens"),
            "llm_total_tokens": artifact_summary.get("llm_total_tokens"),
            "llm_usage_available_count": artifact_summary.get(
                "llm_usage_available_count"
            ),
            "llm_usage_by_source": artifact_summary.get("llm_usage_by_source", {}),
        }
    return {
        "llm_usage_recorded": bool(recorded_rows),
        "llm_call_count": _sum_optional_int(recorded_rows, "llm_call_count"),
        "llm_live_call_count": _sum_optional_int(recorded_rows, "llm_live_call_count"),
        "llm_cached_call_count": _sum_optional_int(
            recorded_rows, "llm_cached_call_count"
        ),
        "llm_prompt_tokens": _sum_optional_int(recorded_rows, "llm_prompt_tokens"),
        "llm_completion_tokens": _sum_optional_int(
            recorded_rows, "llm_completion_tokens"
        ),
        "llm_total_tokens": _sum_optional_int(recorded_rows, "llm_total_tokens"),
        "llm_usage_available_count": _sum_optional_int(
            recorded_rows, "llm_usage_available_count"
        ),
        "llm_usage_by_source": {},
    }


def summarize_run(run_dir: Path, registry_dir: Path | None = None) -> dict[str, Any]:
    """Summarize one run using JSON artifacts only."""
    rows = _scenario_rows(run_dir)
    manifest = _read_json(run_dir.parent / "sage_ts_run_manifest.json")
    wall_time_resume_offset_seconds = _resume_wall_time_offset_seconds(manifest)
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
    llm_usage = _llm_usage_summary(rows, run_dir)
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
        "wall_time_seconds": _run_wall_time_seconds(run_dir),
        "wall_time_resume_offset_seconds": wall_time_resume_offset_seconds,
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
        **llm_usage,
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
                "control_llm_call_count": control_rows[name].get("llm_call_count"),
                "candidate_llm_call_count": candidate_rows[name].get("llm_call_count"),
                "control_llm_total_tokens": control_rows[name].get("llm_total_tokens"),
                "candidate_llm_total_tokens": candidate_rows[name].get(
                    "llm_total_tokens"
                ),
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
