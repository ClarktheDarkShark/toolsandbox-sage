#!/usr/bin/env python3
"""Render dissertation tables for the revised Chapter 4 hypotheses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.render_chapter4_evidence_tables import (
    _number,
    _number_interval,
    _percent,
    _percent_interval,
    metric_value,
    render_table,
    write_contact_sheet,
    write_gallery,
)
from scripts.research.chapter4_evidence import _p_label


def _hypotheses(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    hypotheses = {item["id"]: item for item in data["hypotheses"]}
    expected = {"Hypothesis 1", "Hypothesis 2", "Hypothesis 3"}
    if set(hypotheses) != expected:
        raise ValueError(f"Expected revised H1-H3 data, found {sorted(hypotheses)}")
    return hypotheses


def build_tables(data: dict[str, Any]) -> list[dict[str, Any]]:
    campaign = data["campaign"]
    hypotheses = _hypotheses(data)
    h1 = hypotheses["Hypothesis 1"]
    h2 = hypotheses["Hypothesis 2"]
    h3 = hypotheses["Hypothesis 3"]
    stats = data["statistics"]
    evolution = data["evolution_metrics"]
    totals = evolution["totals"]
    metrics = data["tool_metrics"]
    supporting_reuse = data["supporting_reuse"]
    failure_summary = data["tool_failure_summary"]
    integrity_counts = data["integrity"]["counts"]

    runs = [
        run
        for run in data["runs"]
        if run.get("online_inference_eligible") is True
        and run.get("frozen_inference_eligible") is True
    ]
    if len(runs) != 10:
        raise ValueError("Chapter 4 tables require ten eligible paired runs.")

    evolution_runs = evolution["runs"]
    if len(evolution_runs) != 10:
        raise ValueError("Chapter 4 evolution tables require ten online-build runs.")

    baseline_mean = sum(float(run["baseline_outcome"]) for run in runs) / len(runs)
    sage_mean = sum(float(run["online_sage_outcome"]) for run in runs) / len(runs)
    lift = (sage_mean - baseline_mean) / baseline_mean * 100.0
    frozen_mean = sum(float(run["frozen_sage_outcome"]) for run in runs) / len(runs)
    frozen_retention = float(supporting_reuse["frozen_gain_retention_percent"])
    frozen_retention_ci = supporting_reuse["frozen_gain_retention_confidence_interval"]
    frozen_retention_ci_label = (
        f"[{_percent(frozen_retention_ci['lower'])}, "
        f"{_percent(frozen_retention_ci['upper'])}]"
    )
    repair_p = evolution["repair_threshold_sign_flip_p"]
    cross_family_p = evolution["cross_family_threshold_sign_flip_p"]
    cross_family_rates = [float(run["cross_family_percent"]) for run in evolution_runs]
    failed_tools = failure_summary["tools"]
    dominant_failure = max(failed_tools, key=lambda item: item["failed_scenarios"])
    other_failure_count = int(failure_summary["failed_scenarios"]) - int(
        dominant_failure["failed_scenarios"]
    )

    return [
        {
            "filename": "table_4_1_evidence_campaign.png",
            "title": "Table 4.1 - Evidence Campaign",
            "subtitle": "Final benchmark and analysis settings.",
            "columns": ["Configuration item", "Final setting", "Purpose"],
            "widths": [0.26, 0.29, 0.45],
            "rows": [
                [
                    "Benchmark",
                    f"ToolSandbox, {campaign['tasks_per_run']:,} tasks",
                    "Same ordered tasks for each matched control and SAGE arm.",
                ],
                [
                    "Model",
                    campaign["model"],
                    "Same model for the actor, simulated user, and tool generator.",
                ],
                [
                    "Online-build evidence",
                    "10 independent runs",
                    "Each SAGE run began with an empty run-local registry.",
                ],
                [
                    "Frozen-registry evidence",
                    "10 paired runs",
                    "Supporting reuse evidence with generation and repair disabled.",
                ],
                [
                    "Primary performance endpoint",
                    "Mean route-independent outcome score",
                    (
                        "Continuous score from 0 to 1 across all "
                        f"{campaign['tasks_per_run']:,} tasks per run."
                    ),
                ],
                [
                    "Application replay caches",
                    "Disabled",
                    "Every matched-control task was executed live.",
                ],
            ],
            "caption": "Final Chapter 4 evidence campaign configuration.",
            "compact": True,
        },
        {
            "filename": "table_4_2_replication_results.png",
            "title": "Table 4.2 - Replication Results",
            "subtitle": "Online-build performance and supporting frozen-registry reuse.",
            "columns": [
                "Run",
                "Control",
                "Online SAGE",
                "Online lift",
                "Frozen SAGE",
                "Gain retained",
            ],
            "widths": [0.10, 0.17, 0.20, 0.17, 0.19, 0.17],
            "rows": [
                [
                    run["short_label"],
                    _number(run["baseline_outcome"], digits=3),
                    _number(run["online_sage_outcome"], digits=3),
                    _percent(run["online_outcome_lift_percent"], signed=True),
                    _number(run["frozen_sage_outcome"], digits=3),
                    _percent(run["frozen_gain_retention_percent"]),
                ]
                for run in runs
            ]
            + [
                [
                    "Mean",
                    _number(baseline_mean),
                    _number(sage_mean),
                    _percent(lift, signed=True),
                    _number(frozen_mean),
                    _percent(frozen_retention),
                ]
            ],
            "caption": "Complete results for the ten independent registry runs.",
            "compact": True,
        },
        {
            "filename": "table_4_3_h1_task_completion.png",
            "title": "Table 4.3 - Hypothesis 1",
            "subtitle": "Improved task completion.",
            "columns": [
                "Measure",
                "Control",
                "SAGE",
                "Observed result",
                "Decision rule",
            ],
            "widths": [0.24, 0.15, 0.15, 0.24, 0.22],
            "rows": [
                [
                    "Mean outcome score",
                    _number(baseline_mean),
                    _number(sage_mean),
                    _percent(lift, signed=True),
                    ">= 10% relative lift",
                ],
                [
                    "Relative-lift 95% CI",
                    "",
                    "",
                    _percent_interval(stats["two_way_run_task_bootstrap_lift_ci"]),
                    "Lower bound > 10%",
                ],
                [
                    "10% target contrast",
                    "",
                    "",
                    _number(stats["h1_threshold_contrast"], digits=4),
                    "SAGE - 1.10 x control > 0",
                ],
                [
                    "Two-way contrast 95% CI",
                    "",
                    "",
                    _number_interval(
                        stats["two_way_run_task_bootstrap_threshold_contrast_ci"]
                    ),
                    "Lower bound > 0",
                ],
                [
                    "Run-cluster contrast 95% CI",
                    "",
                    "",
                    _number_interval(stats["run_cluster_threshold_contrast_ci"]),
                    "Lower bound > 0",
                ],
                [
                    "Run-level sign-flip test",
                    "",
                    "",
                    stats["p_label"],
                    "p < .05",
                ],
            ],
            "caption": "Hypothesis 1 evidence from the ten online-build runs.",
        },
        {
            "filename": "table_4_4_h2_repair_and_reuse.png",
            "title": "Table 4.4 - Hypothesis 2",
            "subtitle": "Repair and later reuse.",
            "columns": [
                "Measure",
                "Observed count",
                "Observed rate",
                "95% run-cluster CI",
                "Decision rule",
            ],
            "widths": [0.28, 0.18, 0.16, 0.20, 0.18],
            "rows": [
                [
                    "Failed candidates repaired and admitted",
                    f"{totals['repaired_accepted']} / {totals['repair_entrants']}",
                    _percent(h2["estimate_percent"]),
                    _percent_interval(h2["confidence_interval"]),
                    "> 50%",
                ],
                [
                    "Admitted repaired tools invoked later",
                    (
                        f"{totals['repaired_reused_later']} / "
                        f"{totals['repaired_accepted']}"
                    ),
                    _percent(h2["secondary_estimate_percent"]),
                    _percent_interval(h2["secondary_confidence_interval"]),
                    ">= 90%",
                ],
                [
                    "Repair threshold sign-flip test",
                    "10 runs",
                    _p_label(repair_p),
                    "",
                    "p < .05",
                ],
                [
                    "Maximum recorded repair attempts",
                    str(totals["max_repair_attempts_observed"]),
                    "",
                    "",
                    "Reported from run ledgers",
                ],
            ],
            "caption": "Hypothesis 2 evidence from validation, repair, birth, and later-invocation records.",
        },
        {
            "filename": "table_4_5_h3_cross_family_use.png",
            "title": "Table 4.5 - Hypothesis 3",
            "subtitle": "Use across semantic task families.",
            "columns": [
                "Measure",
                "Observed count",
                "Observed rate",
                "95% run-cluster CI",
                "Decision rule",
            ],
            "widths": [0.29, 0.18, 0.16, 0.20, 0.17],
            "rows": [
                [
                    "Accepted tools used in another family",
                    f"{totals['cross_family_tools']} / {totals['accepted_tools']}",
                    _percent(h3["estimate_percent"]),
                    _percent_interval(h3["confidence_interval"]),
                    "> 50%",
                ],
                [
                    "Run-level range",
                    "10 runs",
                    (
                        f"{min(cross_family_rates):.1f}% to "
                        f"{max(cross_family_rates):.1f}%"
                    ),
                    "",
                    "Every run > 50%",
                ],
                [
                    "Threshold sign-flip test",
                    "10 runs",
                    _p_label(cross_family_p),
                    "",
                    "p < .05",
                ],
            ],
            "caption": "Hypothesis 3 evidence from actual tool-birth and later-invocation task families.",
        },
        {
            "filename": "table_4_6_hypothesis_summary.png",
            "title": "Table 4.6 - Hypothesis Summary",
            "subtitle": "Chapter 4 decisions.",
            "columns": [
                "Hypothesis",
                "Claim tested",
                "Threshold",
                "Observed result",
                "Decision",
            ],
            "widths": [0.10, 0.35, 0.18, 0.25, 0.12],
            "rows": [
                [
                    "H1",
                    "SAGE improves task completion over matched control.",
                    ">= 10% lift",
                    f"{_percent(lift)} lift",
                    h1["decision_label"],
                ],
                [
                    "H2",
                    "Failed candidates are repaired, admitted, and reused later.",
                    "> 50%; >= 90%",
                    (
                        f"{_percent(h2['estimate_percent'])}; "
                        f"{_percent(h2['secondary_estimate_percent'])}"
                    ),
                    h2["decision_label"],
                ],
                [
                    "H3",
                    "Accepted tools are used in another semantic task family.",
                    "> 50%",
                    _percent(h3["estimate_percent"]),
                    h3["decision_label"],
                ],
            ],
            "caption": "Summary of the three revised hypothesis decisions.",
            "compact": True,
        },
        {
            "filename": "table_4_7_reuse_evidence.png",
            "title": "Table 4.7 - Supporting Reuse Evidence",
            "subtitle": "Later use and frozen-registry performance.",
            "columns": ["Reuse measure", "Observed value", "Interpretation"],
            "widths": [0.32, 0.20, 0.48],
            "rows": [
                [
                    "Accepted generated-tool instances",
                    metric_value(metrics, "Accepted tools"),
                    "Tools that passed validation and entered a run-local registry.",
                ],
                [
                    "Accepted tools invoked on a later task",
                    metric_value(metrics, "Reused on later tasks"),
                    "Later-task use across the ten online-build runs.",
                ],
                [
                    "Accepted-tool later-reuse rate",
                    metric_value(metrics, "Tool reuse rate"),
                    "Most accepted tool instances were not one-task artifacts.",
                ],
                [
                    "Frozen-registry gain retained",
                    f"{_percent(frozen_retention)} {frozen_retention_ci_label}",
                    "Supporting result after generation and repair were disabled.",
                ],
            ],
            "caption": "Supporting evidence for later tool reuse and retained registry value.",
        },
        {
            "filename": "table_4_8_generated_tool_failures.png",
            "title": "Table 4.8 - Generated-Tool Failures",
            "subtitle": "Operational failures remain visible in the evidence record.",
            "columns": ["Operational measure", "Observed value", "Interpretation"],
            "widths": [0.34, 0.20, 0.46],
            "rows": [
                [
                    "Tasks with a failed generated-tool call",
                    str(failure_summary["failed_scenarios"]),
                    "Task scenarios, not 289 distinct failed tools.",
                ],
                [
                    "Device-setting action failures",
                    str(dominant_failure["failed_scenarios"]),
                    "Most failures came from one generated action tool.",
                ],
                [
                    "Other generated-tool failures",
                    str(other_failure_count),
                    f"Distributed across {len(failed_tools) - 1} generated tools.",
                ],
                [
                    "Side-effect audit flags",
                    str(integrity_counts["side_effect_flags"]),
                    "Retained in the evidence record for review.",
                ],
                [
                    "Runtime exceptions in selected runs",
                    str(integrity_counts["runtime_exceptions"]),
                    "All selected runs passed the runtime integrity gate.",
                ],
            ],
            "caption": "Generated-tool failure and integrity results.",
            "compact": True,
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    for spec in build_tables(data):
        path = output_dir / spec.pop("filename")
        render_table(path=path, **spec)
        image_paths.append(path)
        print(path)
    write_gallery(image_paths, output_dir)
    write_contact_sheet(image_paths, output_dir)
    print(output_dir / "index.html")


if __name__ == "__main__":
    main()
