#!/usr/bin/env python3
# mypy: ignore-errors
"""Build task-stratum coverage artifacts for ToolSandbox SAGE runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sage_ts.evaluation.task_strata import (
    HELPER_TRIGGERS,
    STRATA,
    classify_task_strata,
    expected_helper_fit,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _result_categories(run_dir: Path | None) -> dict[str, list[str]]:
    if run_dir is None:
        return {}
    path = run_dir / "result_summary.json"
    if not path.exists():
        return {}
    payload = _read_json(path)
    rows = payload.get("per_scenario_results", [])
    return {
        str(row.get("name")): list(row.get("categories") or [])
        for row in rows
        if row.get("name")
    }


def _candidate_dir(run_root: Path, comparison: dict[str, Any]) -> Path | None:
    raw = comparison.get("candidate", {}).get("run_dir")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.exists():
            return path
    candidate_root = run_root / "candidate"
    if not candidate_root.exists():
        return None
    dirs = [path for path in candidate_root.iterdir() if path.is_dir()]
    return max(dirs, key=lambda path: path.stat().st_mtime) if dirs else None


def _selection_by_scenario(candidate_dir: Path | None) -> dict[str, dict[str, Any]]:
    if candidate_dir is None:
        return {}
    rows = _read_jsonl(candidate_dir / "selection_trace.jsonl")
    return {str(row.get("scenario")): row for row in rows if row.get("scenario")}


def _empty_stats() -> dict[str, Any]:
    return {
        "scenario_count": 0,
        "total_delta": 0.0,
        "mean_delta": 0.0,
        "gains": 0,
        "regressions": 0,
        "preserved": 0,
        "exact_success_gap_count": 0,
        "visible_tool_scenarios": 0,
        "called_tool_scenarios": 0,
        "visible_not_called_scenarios": 0,
        "no_visible_tool_regressions": 0,
        "expected_current_helper_fit": Counter(),
        "visible_helpers": Counter(),
        "called_helpers": Counter(),
        "example_regressions": [],
        "example_no_visible_regressions": [],
    }


def _finalize_stats(stats: dict[str, Any]) -> dict[str, Any]:
    count = int(stats["scenario_count"])
    stats["mean_delta"] = float(stats["total_delta"]) / count if count else 0.0
    for key in ("expected_current_helper_fit", "visible_helpers", "called_helpers"):
        stats[key] = dict(stats[key].most_common())
    return stats


def build_coverage(run_roots: list[Path]) -> dict[str, Any]:
    aggregate = {stratum: _empty_stats() for stratum in STRATA}
    runs: dict[str, Any] = {}
    model_keys: dict[str, list[str]] = defaultdict(list)
    no_visible_regressions: list[dict[str, Any]] = []
    matrix: dict[str, dict[str, Any]] = {
        helper: {
            "trigger_strata": list(trigger_strata),
            "visible": Counter(),
            "called": Counter(),
            "called_gains": Counter(),
            "called_regressions": Counter(),
            "called_total_delta": defaultdict(float),
        }
        for helper, trigger_strata in HELPER_TRIGGERS.items()
    }

    for run_root in run_roots:
        comparison_path = run_root / "paired_comparison.json"
        if not comparison_path.exists():
            continue
        comparison = _read_json(comparison_path)
        manifest_path = run_root / "protocol_manifest.json"
        manifest = _read_json(manifest_path) if manifest_path.exists() else {}
        model_metadata = (
            comparison.get("model_metadata") or manifest.get("model_metadata") or {}
        )
        comparison_model_key = (
            comparison.get("comparison_model_key")
            or manifest.get("comparison_model_key")
            or model_metadata.get("comparison_key")
            or f"legacy-agent={manifest.get('agent', 'unknown')}"
        )
        model_keys[str(comparison_model_key)].append(str(run_root))
        candidate_dir = _candidate_dir(run_root, comparison)
        categories_by_scenario = _result_categories(candidate_dir)
        selection = _selection_by_scenario(candidate_dir)
        run_stats = {stratum: _empty_stats() for stratum in STRATA}

        for row in comparison.get("deltas", []):
            scenario = str(row.get("scenario"))
            delta = float(row.get("delta") or 0.0)
            categories = categories_by_scenario.get(scenario, [])
            strata = classify_task_strata(scenario, categories)
            helper_fit = expected_helper_fit(scenario, categories)
            sel = selection.get(scenario, {})
            visible = list(sel.get("generated_tools_visible") or [])
            called = list(sel.get("generated_tools_called") or [])
            is_gain = delta > 1e-9
            is_regression = delta < -1e-9

            for stratum in strata:
                for stats in (aggregate[stratum], run_stats[stratum]):
                    stats["scenario_count"] += 1
                    stats["total_delta"] += delta
                    stats["gains"] += int(is_gain)
                    stats["regressions"] += int(is_regression)
                    stats["preserved"] += int(not is_gain and not is_regression)
                    stats["visible_tool_scenarios"] += int(bool(visible))
                    stats["called_tool_scenarios"] += int(bool(called))
                    stats["visible_not_called_scenarios"] += int(
                        bool(visible) and not called
                    )
                    if helper_fit:
                        stats["expected_current_helper_fit"].update(helper_fit)
                    else:
                        stats["expected_current_helper_fit"].update(
                            ["no_current_helper_fit"]
                        )
                    stats["visible_helpers"].update(visible)
                    stats["called_helpers"].update(called)
                    if is_regression and len(stats["example_regressions"]) < 10:
                        stats["example_regressions"].append(
                            {"scenario": scenario, "delta": delta}
                        )
                    if is_regression and not visible:
                        stats["no_visible_tool_regressions"] += 1
                        if len(stats["example_no_visible_regressions"]) < 10:
                            stats["example_no_visible_regressions"].append(
                                {"scenario": scenario, "delta": delta}
                            )

                if is_regression and not visible:
                    no_visible_regressions.append(
                        {
                            "run_root": str(run_root),
                            "scenario": scenario,
                            "stratum": stratum,
                            "delta": delta,
                            "categories": categories,
                        }
                    )

                for helper in visible:
                    if helper in matrix:
                        matrix[helper]["visible"].update([stratum])
                for helper in called:
                    if helper in matrix:
                        matrix[helper]["called"].update([stratum])
                        matrix[helper]["called_total_delta"][stratum] += delta
                        if is_gain:
                            matrix[helper]["called_gains"].update([stratum])
                        elif is_regression:
                            matrix[helper]["called_regressions"].update([stratum])

        runs[str(run_root)] = {
            "comparison_path": str(comparison_path),
            "model_metadata": model_metadata,
            "comparison_model_key": comparison_model_key,
            "candidate_dir": str(candidate_dir) if candidate_dir else None,
            "overall": {
                "scenario_count": comparison.get("scenario_count"),
                "control_mean": comparison.get("control", {}).get("mean_similarity"),
                "sage_mean": comparison.get("candidate", {}).get("mean_similarity"),
                "mean_delta": comparison.get("mean_similarity_delta"),
                "control_outcome_mean": comparison.get("control", {}).get(
                    "mean_outcome_similarity"
                ),
                "sage_outcome_mean": comparison.get("candidate", {}).get(
                    "mean_outcome_similarity"
                ),
                "mean_outcome_delta": comparison.get("mean_outcome_similarity_delta"),
                "gains": comparison.get("gain_count"),
                "regressions": comparison.get("regression_count"),
                "preserved": comparison.get("preserved_count"),
                "outcome_gains": comparison.get("outcome_gain_count"),
                "outcome_regressions": comparison.get("outcome_regression_count"),
                "outcome_preserved": comparison.get("outcome_preserved_count"),
                "control_exact_success": comparison.get("control", {}).get(
                    "success_count"
                ),
                "sage_exact_success": comparison.get("candidate", {}).get(
                    "success_count"
                ),
                "retained_reuse_count": comparison.get("candidate", {}).get(
                    "reuse_count"
                ),
            },
            "strata": {
                key: _finalize_stats(value)
                for key, value in run_stats.items()
                if value["scenario_count"]
            },
        }

    matrix_out: dict[str, Any] = {}
    for helper, stats in matrix.items():
        called = dict(stats["called"].most_common())
        total_delta = dict(stats["called_total_delta"])
        matrix_out[helper] = {
            "trigger_strata": stats["trigger_strata"],
            "visible_by_stratum": dict(stats["visible"].most_common()),
            "called_by_stratum": called,
            "called_gain_by_stratum": dict(stats["called_gains"].most_common()),
            "called_regression_by_stratum": dict(
                stats["called_regressions"].most_common()
            ),
            "mean_delta_when_called_by_stratum": {
                stratum: total_delta[stratum] / count
                for stratum, count in called.items()
                if count
            },
        }

    return {
        "runs": runs,
        "model_comparison": {
            "comparison_keys": dict(model_keys),
            "mixed_model_warning": len(model_keys) > 1,
            "warning": (
                "Runs use different model comparison keys. Treat cross-run deltas as "
                "model-specific, not directly interchangeable."
                if len(model_keys) > 1
                else None
            ),
        },
        "aggregate_strata": {
            key: _finalize_stats(value)
            for key, value in aggregate.items()
            if value["scenario_count"]
        },
        "tool_coverage_matrix": matrix_out,
        "no_visible_tool_regressions": no_visible_regressions,
    }


def write_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "task_stratum_map.json").write_text(
        json.dumps(
            {
                "runs": payload["runs"],
                "model_comparison": payload["model_comparison"],
                "aggregate_strata": payload["aggregate_strata"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "tool_coverage_matrix.json").write_text(
        json.dumps(payload["tool_coverage_matrix"], indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "no_visible_tool_regressions.json").write_text(
        json.dumps(payload["no_visible_tool_regressions"], indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Coverage Gap Report",
        "",
        "This report maps current retained helper coverage against prior 100/250 scenario mixes.",
        "",
        "## Model Comparison Guard",
        "",
        f"- Mixed model warning: {payload['model_comparison']['mixed_model_warning']}",
        f"- Comparison keys: {list(payload['model_comparison']['comparison_keys'].keys())}",
        "",
        "## Stratum Summary",
        "",
    ]
    for stratum, stats in sorted(
        payload["aggregate_strata"].items(),
        key=lambda item: item[1]["scenario_count"],
        reverse=True,
    ):
        lines.extend(
            [
                f"### {stratum}",
                f"- Scenarios: {stats['scenario_count']}",
                f"- Mean delta: {stats['mean_delta']:.4f}",
                f"- Gains / regressions / preserved: {stats['gains']} / {stats['regressions']} / {stats['preserved']}",
                f"- Visible-tool scenarios: {stats['visible_tool_scenarios']}",
                f"- Called-tool scenarios: {stats['called_tool_scenarios']}",
                f"- No-visible-tool regressions: {stats['no_visible_tool_regressions']}",
                f"- Expected helper fit: {stats['expected_current_helper_fit']}",
                "",
            ]
        )
    lines.extend(["## Helper Coverage Matrix", ""])
    for helper, stats in payload["tool_coverage_matrix"].items():
        lines.extend(
            [
                f"### {helper}",
                f"- Trigger strata: {stats['trigger_strata']}",
                f"- Visible by stratum: {stats['visible_by_stratum']}",
                f"- Called by stratum: {stats['called_by_stratum']}",
                f"- Mean delta when called by stratum: {stats['mean_delta_when_called_by_stratum']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Campaign Implication",
            "",
            "- Do not run another broad 100/250 gate until uncovered high-frequency strata have discovery runs.",
            "- Prioritize contact/message disambiguation and record filtering/ranking because they recur often and current helper coverage is thin.",
            "- Treat broad validation as a regression/generalization test after registry coverage expands, not as the primary proof for the current four tools.",
            "",
        ]
    )
    (output_dir / "coverage_gap_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        type=Path,
        action="append",
        required=True,
        help="Protocol run root containing paired_comparison.json.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args()

    payload = build_coverage(args.run_root)
    write_report(payload, args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
