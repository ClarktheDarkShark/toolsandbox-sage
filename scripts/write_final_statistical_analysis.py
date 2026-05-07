#!/usr/bin/env python3
"""Write dissertation-facing statistical summaries from locked SAGE artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, cast

DEFAULT_OUTPUT_JSON = Path(
    "artifacts/summaries/final_statistical_analysis/analysis.json"
)
DEFAULT_OUTPUT_MD = Path("docs/sage_protocol/final_statistical_analysis_report.md")
BOOTSTRAP_ITERATIONS = 5000
PERMUTATION_ITERATIONS = 10000
RANDOM_SEED = 20260507


@dataclass(frozen=True)
class RunSpec:
    label: str
    run_root: Path
    comparison_kind: str


BEST3_RUNS = (
    RunSpec(
        "best3_formal100_vs_control",
        Path(
            "outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428"
        ),
        "candidate_vs_control",
    ),
    RunSpec(
        "best3_formal250_vs_control",
        Path(
            "outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222"
        ),
        "candidate_vs_control",
    ),
    RunSpec(
        "best3_formal500_vs_control",
        Path(
            "outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130"
        ),
        "candidate_vs_control",
    ),
    RunSpec(
        "best3_formal1032_vs_control",
        Path(
            "outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905"
        ),
        "candidate_vs_control",
    ),
)

DIRECT_COMPARISONS = (
    (
        "v2_6_current_code_original250_expanded_vs_best3",
        Path(
            "outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235"
        ),
        Path(
            "outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441"
        ),
        Path(
            "artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_original250_best3/feedback_summary.json"
        ),
        Path(
            "artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_original250_expanded/feedback_summary.json"
        ),
    ),
    (
        "v2_6_current_code_500_expanded_vs_best3",
        Path("outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553"),
        Path("outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427"),
        Path(
            "artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_500_best3/feedback_summary.json"
        ),
        Path(
            "artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_500_expanded/feedback_summary.json"
        ),
    ),
)


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - idx) + ordered[hi] * (idx - lo)


def bootstrap_ci(
    values: list[float], *, iterations: int = BOOTSTRAP_ITERATIONS
) -> dict[str, float]:
    if not values:
        return {"mean": math.nan, "ci_low": math.nan, "ci_high": math.nan}
    rng = random.Random(RANDOM_SEED + len(values))
    n = len(values)
    samples = [
        mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(iterations)
    ]
    return {
        "mean": mean(values),
        "ci_low": quantile(samples, 0.025),
        "ci_high": quantile(samples, 0.975),
    }


def permutation_p_value(
    values: list[float], *, iterations: int = PERMUTATION_ITERATIONS
) -> float:
    if not values:
        return math.nan
    observed = abs(mean(values))
    rng = random.Random(RANDOM_SEED + 17 + len(values))
    extreme = 0
    for _ in range(iterations):
        signed = [value if rng.random() < 0.5 else -value for value in values]
        if abs(mean(signed)) >= observed:
            extreme += 1
    return (extreme + 1) / (iterations + 1)


def maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def paired_exact_deltas(
    rows: list[dict[str, Any]], *, candidate_key: str, control_key: str
) -> list[float]:
    return [
        float(float(row.get(candidate_key, 0.0) or 0.0) >= 1.0)
        - float(float(row.get(control_key, 0.0) or 0.0) >= 1.0)
        for row in rows
    ]


def cache_summary(run_root: Path) -> dict[str, Any]:
    path = run_root / "control_cache_report.json"
    if not path.exists():
        return {"path": str(path), "exists": False}
    data = read_json(path)
    variances = data.get("baseline_count_and_variance_per_cached_task", {})
    outcome_variances = []
    if isinstance(variances, dict):
        for row in variances.values():
            if isinstance(row, dict) and row.get("outcome_variance") is not None:
                outcome_variances.append(float(row["outcome_variance"]))
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "exists": True,
        "control_source": data.get("control_source"),
        "cached_control_tasks": data.get("cached_control_tasks"),
        "fresh_control_tasks": data.get("fresh_control_tasks"),
        "confidence_intervals_account_for_cached_control_variance": data.get(
            "confidence_intervals_account_for_cached_control_variance"
        ),
        "cached_task_outcome_variance_mean": mean(outcome_variances)
        if outcome_variances
        else None,
        "cached_task_outcome_variance_max": max(outcome_variances)
        if outcome_variances
        else None,
    }


def helper_summary(run_root: Path) -> dict[str, Any]:
    path = run_root / "helper_contribution_summary.json"
    if not path.exists():
        return {"path": str(path), "exists": False}
    data = read_json(path)
    helpers = {}
    for name, row in (data.get("helpers", {}) or {}).items():
        if not isinstance(row, dict):
            continue
        helpers[name] = {
            "visible_count": row.get("visible_count"),
            "called_count": row.get("called_count"),
            "visible_not_called_count": row.get("visible_not_called_count"),
            "called_subset": row.get("called_subset"),
        }
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "exists": True,
        "helpers": helpers,
    }


def analyze_candidate_vs_control(spec: RunSpec) -> dict[str, Any]:
    path = spec.run_root / "paired_comparison.json"
    data = read_json(path)
    rows = data.get("deltas", []) or []
    outcome = [float(row.get("outcome_delta", 0.0) or 0.0) for row in rows]
    canonical = [float(row.get("delta", 0.0) or 0.0) for row in rows]
    exact = paired_exact_deltas(
        rows, candidate_key="candidate_similarity", control_key="control_similarity"
    )
    return {
        "label": spec.label,
        "comparison_kind": spec.comparison_kind,
        "run_root": str(spec.run_root),
        "paired_comparison_path": str(path),
        "paired_comparison_sha256": sha256_file(path),
        "scenario_count": len(rows),
        "outcome": {
            "control_mean": data.get("control_mean_outcome_similarity"),
            "candidate_mean": data.get("candidate_mean_outcome_similarity"),
            "mean_delta": mean(outcome) if outcome else None,
            "bootstrap_ci": bootstrap_ci(outcome),
            "permutation_p_two_sided": permutation_p_value(outcome),
        },
        "canonical": {
            "control_mean": data.get("control_mean_similarity"),
            "candidate_mean": data.get("candidate_mean_similarity"),
            "mean_delta": mean(canonical) if canonical else None,
            "bootstrap_ci": bootstrap_ci(canonical),
            "permutation_p_two_sided": permutation_p_value(canonical),
        },
        "exact_success": {
            "control_exact_successes": data.get("control_exact_successes"),
            "candidate_exact_successes": data.get("candidate_exact_successes"),
            "mean_paired_delta": mean(exact) if exact else None,
            "bootstrap_ci": bootstrap_ci(exact),
            "permutation_p_two_sided": permutation_p_value(exact),
        },
        "counts": {
            "outcome_gains": data.get("outcome_gain_count"),
            "outcome_regressions": data.get("outcome_regression_count"),
            "outcome_preserved": data.get("outcome_preserved_count"),
            "runtime_exception_count": data.get("runtime_exception_count"),
            "protocol_gate_passed": data.get("protocol_gate_passed"),
            "route_mismatch_qualified": data.get("route_mismatch_qualified"),
        },
        "control_cache": cache_summary(spec.run_root),
        "helper_contribution": helper_summary(spec.run_root),
    }


def candidate_rows_by_scenario(run_root: Path) -> dict[str, dict[str, Any]]:
    rows = read_json(run_root / "paired_comparison.json").get("deltas", []) or []
    return {str(row.get("scenario")): row for row in rows}


def analyze_direct_pair(
    label: str,
    best3_root: Path,
    expanded_root: Path,
    best3_feedback: Path,
    expanded_feedback: Path,
) -> dict[str, Any]:
    best3_rows = candidate_rows_by_scenario(best3_root)
    expanded_rows = candidate_rows_by_scenario(expanded_root)
    common = sorted(set(best3_rows) & set(expanded_rows))
    outcome: list[float] = []
    canonical: list[float] = []
    exact: list[float] = []
    for scenario in common:
        b = best3_rows[scenario]
        e = expanded_rows[scenario]
        outcome.append(
            float(e.get("candidate_outcome_similarity", 0.0) or 0.0)
            - float(b.get("candidate_outcome_similarity", 0.0) or 0.0)
        )
        canonical.append(
            float(e.get("candidate_similarity", 0.0) or 0.0)
            - float(b.get("candidate_similarity", 0.0) or 0.0)
        )
        exact.append(
            float(float(e.get("candidate_similarity", 0.0) or 0.0) >= 1.0)
            - float(float(b.get("candidate_similarity", 0.0) or 0.0) >= 1.0)
        )
    best3_feedback_data = read_json(best3_feedback) if best3_feedback.exists() else {}
    expanded_feedback_data = (
        read_json(expanded_feedback) if expanded_feedback.exists() else {}
    )
    best3_no_fit = maybe_float(best3_feedback_data.get("no_current_helper_fit_share"))
    expanded_no_fit = maybe_float(
        expanded_feedback_data.get("no_current_helper_fit_share")
    )
    gap_reduction = None
    if best3_no_fit is not None and best3_no_fit != 0.0 and expanded_no_fit is not None:
        gap_reduction = (best3_no_fit - expanded_no_fit) / best3_no_fit
    return {
        "label": label,
        "comparison_kind": "expanded_candidate_vs_best3_candidate_same_manifest",
        "best3_run_root": str(best3_root),
        "expanded_run_root": str(expanded_root),
        "scenario_count": len(common),
        "outcome": {
            "mean_delta": mean(outcome) if outcome else None,
            "bootstrap_ci": bootstrap_ci(outcome),
            "permutation_p_two_sided": permutation_p_value(outcome),
        },
        "canonical": {
            "mean_delta": mean(canonical) if canonical else None,
            "bootstrap_ci": bootstrap_ci(canonical),
            "permutation_p_two_sided": permutation_p_value(canonical),
        },
        "exact_success": {
            "mean_paired_delta": mean(exact) if exact else None,
            "bootstrap_ci": bootstrap_ci(exact),
            "permutation_p_two_sided": permutation_p_value(exact),
        },
        "no_current_helper_fit": {
            "best3_share": best3_no_fit,
            "expanded_share": expanded_no_fit,
            "relative_reduction": gap_reduction,
            "best3_feedback_summary": str(best3_feedback),
            "expanded_feedback_summary": str(expanded_feedback),
        },
        "best3_helper_contribution": helper_summary(best3_root),
        "expanded_helper_contribution": helper_summary(expanded_root),
        "best3_control_cache": cache_summary(best3_root),
        "expanded_control_cache": cache_summary(expanded_root),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Statistical Analysis Report",
        "",
        "## Scope",
        "",
        "This report is generated from existing paired comparison, helper-contribution, feedback-summary, and control-cache artifacts. It does not run new benchmarks and does not modify registries.",
        "",
        "Outcome/task-completion is primary. Canonical/reference similarity is secondary. Best3 broad evidence and V2.6 expanded contact-scalar evidence are reported separately.",
        "",
        "## Best3 Broad Evidence Versus Control",
        "",
        "| Evidence | N | Outcome Delta | Outcome 95% Bootstrap CI | Outcome Permutation p | Canonical Delta | Exact Paired Delta | Runtime | Protocol Gate |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in report["best3_vs_control"]:
        lines.append(
            "| {label} | {n} | {od:.4f} | [{ol:.4f}, {oh:.4f}] | {op:.4f} | {cd:.4f} | {ed:.4f} | {rt} | {gate} |".format(
                label=row["label"],
                n=row["scenario_count"],
                od=row["outcome"]["mean_delta"],
                ol=row["outcome"]["bootstrap_ci"]["ci_low"],
                oh=row["outcome"]["bootstrap_ci"]["ci_high"],
                op=row["outcome"]["permutation_p_two_sided"],
                cd=row["canonical"]["mean_delta"],
                ed=row["exact_success"]["mean_paired_delta"],
                rt=row["counts"].get("runtime_exception_count"),
                gate=row["counts"].get("protocol_gate_passed"),
            )
        )
    lines.extend(
        [
            "",
            "## V2.6 Expanded Versus Current-Code Best3",
            "",
            "| Evidence | N | Outcome Delta | Outcome 95% Bootstrap CI | Outcome Permutation p | Canonical Delta | Exact Paired Delta | Best3 No-Fit | Expanded No-Fit | Gap Reduction |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["v2_6_expanded_vs_best3"]:
        gap = row["no_current_helper_fit"].get("relative_reduction")
        lines.append(
            "| {label} | {n} | {od:.4f} | [{ol:.4f}, {oh:.4f}] | {op:.4f} | {cd:.4f} | {ed:.4f} | {bnf:.3f} | {enf:.3f} | {gap:.2%} |".format(
                label=row["label"],
                n=row["scenario_count"],
                od=row["outcome"]["mean_delta"],
                ol=row["outcome"]["bootstrap_ci"]["ci_low"],
                oh=row["outcome"]["bootstrap_ci"]["ci_high"],
                op=row["outcome"]["permutation_p_two_sided"],
                cd=row["canonical"]["mean_delta"],
                ed=row["exact_success"]["mean_paired_delta"],
                bnf=row["no_current_helper_fit"].get("best3_share") or 0.0,
                enf=row["no_current_helper_fit"].get("expanded_share") or 0.0,
                gap=gap or 0.0,
            )
        )
    lines.extend(
        [
            "",
            "## Cache Variance Treatment",
            "",
            "Primary bootstrap and permutation analyses are paired over scenario-level realized scores in the stored artifacts. Task-level cached controls are treated as fixed score-complete baseline estimates for these intervals. Control-cache reports are included in the JSON output with cached/fresh counts and cached-task variance summaries, but cache variance is not folded into the primary bootstrap interval. Interpret intervals as conditional on the stored baseline artifacts, not as a full model-stochastic uncertainty decomposition.",
            "",
            "Cached-control feedback packets may be score-complete but trace-incomplete when the synthetic cached row has no historical conversation trajectory. This affects trace-level feedback interpretation, not score arithmetic.",
            "",
            "## Evidence Separation",
            "",
            "- Best3 broad evidence remains the protected primary portfolio claim.",
            "- V2.6 expanded contact-scalar evidence is secondary: matched gap closure is strong, current-code original250/500 is non-harmful and modestly positive, and broad 500 helper-fit reduction remains below the 10% target.",
            "- Generated-but-uncalled tools remain adoption/routing/callability diagnoses, not no-value conclusions.",
            "",
            "## Output Artifacts",
            "",
            f"- JSON: `{report['output_json']}`",
            f"- Report generated with bootstrap iterations: `{BOOTSTRAP_ITERATIONS}` and permutation iterations: `{PERMUTATION_ITERATIONS}`.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    best3 = [analyze_candidate_vs_control(spec) for spec in BEST3_RUNS]
    expanded = [analyze_direct_pair(*item) for item in DIRECT_COMPARISONS]
    report = {
        "schema_version": "sage_final_statistical_analysis_v1",
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "permutation_iterations": PERMUTATION_ITERATIONS,
        "random_seed": RANDOM_SEED,
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "best3_vs_control": best3,
        "v2_6_expanded_vs_best3": expanded,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_markdown(report, args.output_md)
    print(
        json.dumps(
            {"output_json": str(args.output_json), "output_md": str(args.output_md)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
