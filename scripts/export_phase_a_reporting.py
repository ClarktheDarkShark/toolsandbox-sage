# mypy: ignore-errors
#!/usr/bin/env python3
"""Emit Phase A reporting artifacts for a protocol run."""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _scenario_rows(run_dir: Path | None) -> list[dict[str, Any]]:
    if run_dir is None:
        return []
    source = run_dir / "result_summary.json"
    if not source.exists():
        source = run_dir / "live_result_summary.json"
    if not source.exists():
        return []
    return list((_read_json(source, {}) or {}).get("per_scenario_results", []))


def _scenario_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("name")): row for row in rows if row.get("name")}


def _row_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    return None if value is None else float(value)


def _scenario_final_answer(run_dir: Path | None, scenario: str) -> str | None:
    if run_dir is None:
        return None
    path = run_dir / "trajectories" / scenario / "conversation.json"
    if not path.exists():
        return None
    conversation = _read_json(path, [])
    final_answer = None
    for message in conversation:
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").lower() != "assistant":
            continue
        content = str(message.get("content") or "")
        if content.strip():
            final_answer = content.strip()
    return final_answer


def _bootstrap_ci(values: list[float], *, rounds: int = 2000) -> dict[str, float]:
    if not values:
        return {
            "estimate": 0.0,
            "lower": 0.0,
            "upper": 0.0,
            "n": 0,
            "bootstrap_rounds": 0,
        }
    estimate = statistics.mean(values)
    if len(values) < 2:
        return {
            "estimate": estimate,
            "lower": estimate,
            "upper": estimate,
            "n": len(values),
            "bootstrap_rounds": 0,
        }
    rng = random.Random(1337)
    means: list[float] = []
    for _ in range(rounds):
        sample = [rng.choice(values) for _ in values]
        means.append(statistics.mean(sample))
    means.sort()
    low_idx = max(0, int(0.025 * rounds) - 1)
    high_idx = min(rounds - 1, int(0.975 * rounds) - 1)
    return {
        "estimate": estimate,
        "lower": means[low_idx],
        "upper": means[high_idx],
        "n": len(values),
        "bootstrap_rounds": rounds,
    }


def _build_visibility_and_call_report(
    selection_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    tool_aggregate: dict[str, dict[str, int]] = defaultdict(
        lambda: {"visible": 0, "called": 0, "attempted": 0, "not_called": 0}
    )
    scenarios = []
    for row in selection_rows:
        scenario = str(row.get("scenario") or "")
        visible = list(row.get("generated_tools_visible") or [])
        called = list(row.get("generated_tools_called") or [])
        attempted = list(row.get("generated_tools_attempted") or [])
        not_called = list(row.get("generated_tools_not_called") or [])
        status = str(row.get("selection_status") or "")
        scenarios.append(
            {
                "scenario": scenario,
                "selection_status": status,
                "visible": visible,
                "called": called,
                "attempted": attempted,
                "not_called": not_called,
                "similarity": _row_value(row, "similarity"),
            }
        )
        for tool_name in visible:
            tool_aggregate[tool_name]["visible"] += 1
        for tool_name in called:
            tool_aggregate[tool_name]["called"] += 1
        for tool_name in attempted:
            tool_aggregate[tool_name]["attempted"] += 1
        for tool_name in not_called:
            tool_aggregate[tool_name]["not_called"] += 1
    return {
        "scenario_rows": scenarios,
        "tool_summary": dict(tool_aggregate),
        "summary": {
            "scenario_count": len(scenarios),
            "visible_scenarios": len([row for row in scenarios if row["visible"]]),
            "called_scenarios": len([row for row in scenarios if row["called"]]),
        },
    }


def _build_subset_reports(
    selection_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    applicable: list[dict[str, Any]] = []
    non_applicable: list[dict[str, Any]] = []
    for row in selection_rows:
        scenario = str(row.get("scenario") or "")
        status = str(row.get("selection_status") or "")
        bucket = (
            applicable if status != "no_visible_generated_tools" else non_applicable
        )
        bucket.append(
            {
                "scenario": scenario,
                "selection_status": status,
                "visible": row.get("generated_tools_visible", []),
                "attempted": row.get("generated_tools_attempted", []),
                "called": row.get("generated_tools_called", []),
                "filtered_out": row.get("filtered_out_generated_tools", []),
            }
        )
    return (
        {
            "subset_type": "tool_applicable",
            "count": len(applicable),
            "scenarios": applicable,
        },
        {
            "subset_type": "tool_non_applicable",
            "count": len(non_applicable),
            "scenarios": non_applicable,
        },
    )


def _scenario_label(
    delta: float | None,
    outcome_delta: float | None,
    candidate_similarity: float | None,
    control_similarity: float | None,
) -> str:
    if delta is None:
        return "baseline_only"
    if delta > 0.0005:
        return "gain"
    if delta < -0.0005:
        return "regression"
    if (
        outcome_delta is not None
        and outcome_delta >= 0.0005
        and candidate_similarity is not None
        and control_similarity is not None
        and candidate_similarity < 0.999
        and control_similarity < 0.999
    ):
        return "trace_mismatch"
    return "preserved"


def _build_adjudication_packet(
    control_rows: dict[str, dict[str, Any]],
    candidate_rows: dict[str, dict[str, Any]],
    control_dir: Path | None,
    candidate_dir: Path | None,
    deltas: list[dict[str, Any]],
    reuse_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reuse_by_scenario: dict[str, list[str]] = defaultdict(list)
    for row in reuse_rows:
        scenario = str(row.get("scenario") or "")
        name = row.get("tool_name")
        if scenario and name:
            reuse_by_scenario[scenario].append(str(name))
    by_scenario = {}
    for row in deltas:
        scenario = str(row.get("scenario") or "")
        by_scenario[scenario] = row
    packet: list[dict[str, Any]] = []
    for scenario in sorted(set(control_rows) | set(candidate_rows)):
        control = control_rows.get(scenario, {})
        candidate = candidate_rows.get(scenario, {})
        delta = by_scenario.get(scenario, {})
        control_similarity = _row_value(control, "similarity")
        candidate_similarity = _row_value(candidate, "similarity")
        control_outcome = _row_value(control, "outcome_similarity")
        candidate_outcome = _row_value(candidate, "outcome_similarity")
        outcome_delta = None
        if control_outcome is not None and candidate_outcome is not None:
            outcome_delta = candidate_outcome - control_outcome
        packet.append(
            {
                "task_id": scenario,
                "scenario": scenario,
                "control_final_answer": _scenario_final_answer(control_dir, scenario),
                "candidate_final_answer": _scenario_final_answer(
                    candidate_dir, scenario
                ),
                "control_final_state": {
                    "similarity": control_similarity,
                    "outcome_similarity": control_outcome,
                    "exception_type": control.get("exception_type"),
                    "turn_count": control.get("turn_count"),
                },
                "candidate_final_state": {
                    "similarity": candidate_similarity,
                    "outcome_similarity": candidate_outcome,
                    "exception_type": candidate.get("exception_type"),
                    "turn_count": candidate.get("turn_count"),
                },
                "tool_trace_summary": {
                    "reuse_tools": sorted(set(reuse_by_scenario.get(scenario, []))),
                    "control_similarity": control_similarity,
                    "candidate_similarity": candidate_similarity,
                    "outcome_delta": outcome_delta,
                },
                "label": _scenario_label(
                    delta.get("delta"),
                    delta.get("outcome_delta"),
                    candidate_similarity,
                    control_similarity,
                ),
            }
        )
    return packet


def emit_phase_a_reports(protocol_root: Path, output_dir: Path) -> dict[str, Any]:
    manifest = _read_json(protocol_root / "protocol_manifest.json", {})
    control_dir = (
        Path(str(manifest.get("control_dir"))) if manifest.get("control_dir") else None
    )
    candidate_dir = (
        Path(str(manifest.get("candidate_dir")))
        if manifest.get("candidate_dir")
        else None
    )
    registry_dir = (
        Path(str(manifest.get("registry_dir")))
        if manifest.get("registry_dir")
        else None
    )
    if control_dir is not None and not control_dir.exists():
        control_dir = None
    if candidate_dir is not None and not candidate_dir.exists():
        candidate_dir = None

    output_dir.mkdir(parents=True, exist_ok=True)
    if manifest:
        (output_dir / "protocol_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    control_summary = (
        summarize_run(control_dir, registry_dir=registry_dir)
        if control_dir is not None
        else {"scenario_count": 0}
    )
    if candidate_dir is not None:
        candidate_summary = summarize_run(candidate_dir)
    elif control_dir is not None:
        candidate_summary = summarize_run(control_dir)
    else:
        candidate_summary = {}

    if control_dir is not None and candidate_dir is not None:
        comparison = compare_runs(
            control_dir,
            candidate_dir,
            registry_dir=registry_dir,
            require_complete_match=False,
        )
    else:
        comparison = {}

    control_rows = _scenario_map(_scenario_rows(control_dir))
    candidate_rows = _scenario_map(_scenario_rows(candidate_dir))
    deltas = list(comparison.get("deltas", []))
    delta_map = {row["scenario"]: row for row in deltas if isinstance(row, dict)}
    selection_rows = _read_jsonl(
        candidate_dir / "scenario_tool_selection.jsonl"
        if candidate_dir is not None
        else Path("missing")
    )
    tool_visibility = _build_visibility_and_call_report(selection_rows)
    applicable, non_applicable = _build_subset_reports(selection_rows)
    route_mismatch = []
    for row in deltas:
        if (
            _row_value(row, "outcome_delta") is not None
            and _row_value(row, "candidate_similarity") is not None
            and _row_value(row, "control_similarity") is not None
            and _row_value(row, "candidate_similarity") is not None
        ):
            candidate_similarity = _row_value(row, "candidate_similarity")
            outcome_similarity = _row_value(row, "candidate_outcome_similarity")
            if candidate_similarity is not None and outcome_similarity is not None:
                if outcome_similarity >= 1.0 and candidate_similarity < 0.999:
                    route_mismatch.append(row)
    gains = [
        row
        for row in deltas
        if isinstance(row.get("delta"), (int, float)) and row["delta"] > 0
    ]
    regressions = [
        row
        for row in deltas
        if isinstance(row.get("delta"), (int, float)) and row["delta"] < 0
    ]
    preserved = [
        row
        for row in deltas
        if isinstance(row.get("delta"), (int, float)) and row["delta"] == 0
    ]

    canonical_score = {
        "control": {
            "mean_similarity": control_summary.get("mean_similarity"),
            "success_count": control_summary.get("success_count"),
            "exact_success_count": control_summary.get("success_count"),
            "scenario_count": control_summary.get("scenario_count"),
        }
        if control_summary
        else {},
        "candidate": {
            "mean_similarity": candidate_summary.get("mean_similarity"),
            "success_count": candidate_summary.get("success_count"),
            "exact_success_count": candidate_summary.get("success_count"),
            "scenario_count": candidate_summary.get("scenario_count"),
        }
        if candidate_summary
        else {},
    }
    if (
        control_summary
        and candidate_summary
        and control_summary.get("mean_similarity") is not None
        and candidate_summary.get("mean_similarity") is not None
    ):
        canonical_score["delta"] = float(candidate_summary["mean_similarity"]) - float(
            control_summary["mean_similarity"]
        )

    final_task_score = {
        "control": {
            "mean_outcome_similarity": control_summary.get("mean_outcome_similarity"),
            "outcome_success_count": control_summary.get("outcome_success_count"),
            "scenario_count": control_summary.get("scenario_count"),
        }
        if control_summary
        else {},
        "candidate": {
            "mean_outcome_similarity": candidate_summary.get("mean_outcome_similarity"),
            "outcome_success_count": candidate_summary.get("outcome_success_count"),
            "scenario_count": candidate_summary.get("scenario_count"),
        }
        if candidate_summary
        else {},
    }
    if (
        control_summary
        and candidate_summary
        and control_summary.get("mean_outcome_similarity") is not None
        and candidate_summary.get("mean_outcome_similarity") is not None
    ):
        final_task_score["delta"] = float(
            candidate_summary["mean_outcome_similarity"]
        ) - float(control_summary["mean_outcome_similarity"])

    exact_success = {
        "control_exact_success": control_summary.get("success_count"),
        "candidate_exact_success": candidate_summary.get("success_count"),
        "exact_success_delta": None,
    }
    if (
        control_summary.get("success_count") is not None
        and candidate_summary.get("success_count") is not None
    ):
        exact_success["exact_success_delta"] = int(
            candidate_summary["success_count"]
        ) - int(control_summary["success_count"])

    canonical_ci = _bootstrap_ci(
        [
            float(row["delta"])
            for row in deltas
            if isinstance(row.get("delta"), (int, float))
        ]
    )
    outcome_ci = _bootstrap_ci(
        [
            float(row["outcome_delta"])
            for row in deltas
            if isinstance(row.get("outcome_delta"), (int, float))
        ]
    )

    side_effect_source = (
        candidate_dir / "side_effect_preservation_report.jsonl"
        if candidate_dir is not None
        else None
    )
    side_effect_rows = _read_jsonl(side_effect_source or Path("missing"))
    runtime_exceptions = [
        {
            "arm": "control",
            "scenario": row.get("name"),
            "exception_type": row.get("exception_type"),
            "similarity": row.get("similarity"),
        }
        for row in _scenario_rows(control_dir)
        if row.get("exception_type")
    ] + [
        {
            "arm": "candidate",
            "scenario": row.get("name"),
            "exception_type": row.get("exception_type"),
            "similarity": row.get("similarity"),
        }
        for row in _scenario_rows(candidate_dir)
        if row.get("exception_type")
    ]

    candidate_reuse_rows = _read_jsonl(
        candidate_dir / "reuse_events.jsonl"
        if candidate_dir is not None
        else Path("missing")
    )
    adjudication_rows = _build_adjudication_packet(
        control_rows,
        candidate_rows,
        control_dir,
        candidate_dir,
        deltas,
        candidate_reuse_rows,
    )

    artifacts: dict[str, Any] = {
        "protocol_manifest.json": manifest,
        "canonical_score.json": canonical_score,
        "final_task_success_score.json": final_task_score,
        "exact_success.json": exact_success,
        "gains_regressions_preserved.json": {
            "scenario_count": len(deltas),
            "gain_count": len(gains),
            "regression_count": len(regressions),
            "preserved_count": len(preserved),
            "gains": gains,
            "regressions": regressions,
            "preserved": preserved,
        },
        "tool_visibility_and_call_report.json": tool_visibility,
        "tool_applicable_subset_report.json": applicable,
        "non_applicable_subset_report.json": non_applicable,
        "route_mismatch_report.json": {
            "count": len(route_mismatch),
            "rows": route_mismatch,
        },
        "runtime_exceptions.json": {
            "count": len(runtime_exceptions),
            "exceptions": runtime_exceptions,
        },
        "side_effect_preservation_report.jsonl": side_effect_rows,
        "confidence_intervals.json": {
            "canonical": canonical_ci,
            "final_task": outcome_ci,
        },
    }

    for filename, payload in artifacts.items():
        path = output_dir / filename
        if filename.endswith(".jsonl"):
            lines = [json.dumps(row) for row in payload]
            path.write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
        else:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    adjudication_path = output_dir / "adjudication_packet.jsonl"
    adjudication_path.write_text(
        "\n".join(json.dumps(row) for row in adjudication_rows)
        + ("\n" if adjudication_rows else ""),
        encoding="utf-8",
    )
    artifact_paths = [str((output_dir / key)) for key in artifacts]
    artifact_paths.append(str(adjudication_path))
    return {
        "output_dir": str(output_dir),
        "artifact_paths": artifact_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-run-root", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write reporting artifacts. Defaults to <protocol-run-root>/phase_A_reports.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir or (args.protocol_run_root / "phase_A_reports")
    payload = emit_phase_a_reports(args.protocol_run_root, output_dir)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
