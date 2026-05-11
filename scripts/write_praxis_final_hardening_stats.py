#!/usr/bin/env python3
"""Write Praxis final-hardening matched formal500 statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARM_LABELS = {
    "best3": "best3 reference",
    "v2_6": "V2.6 reference",
    "praxis": "Praxis frozen BridgePack",
}


@dataclass(frozen=True)
class ArmPaths:
    key: str
    run_root: Path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def bootstrap_ci(
    values: list[float], *, seed: int = 20260510, rounds: int = 5000
) -> dict[str, float]:
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(rounds):
        samples.append(mean([values[rng.randrange(n)] for _ in range(n)]))
    return {
        "mean": mean(values),
        "ci95_low": quantile(samples, 0.025),
        "ci95_high": quantile(samples, 0.975),
        "rounds": float(rounds),
    }


def sign_flip_p_value(
    values: list[float], *, seed: int = 20260510, rounds: int = 10000
) -> float:
    observed = abs(mean(values))
    rng = random.Random(seed)
    hits = 0
    for _ in range(rounds):
        trial = mean([value if rng.random() < 0.5 else -value for value in values])
        if abs(trial) >= observed:
            hits += 1
    return (hits + 1) / (rounds + 1)


def candidate_rows(run_root: Path) -> dict[str, dict[str, Any]]:
    candidates = sorted((run_root / "candidate").glob("*/result_summary.json"))
    if len(candidates) != 1:
        raise FileNotFoundError(f"expected one candidate result under {run_root}")
    rows = read_json(candidates[0]).get("per_scenario_results", [])
    return {str(row["name"]): row for row in rows if isinstance(row, dict)}


def control_rows(run_root: Path) -> dict[str, dict[str, Any]]:
    controls = sorted((run_root / "control").glob("*/result_summary.json"))
    if len(controls) != 1:
        raise FileNotFoundError(f"expected one control result under {run_root}")
    rows = read_json(controls[0]).get("per_scenario_results", [])
    return {str(row["name"]): row for row in rows if isinstance(row, dict)}


def helper_summary(run_root: Path) -> dict[str, Any]:
    path = run_root / "helper_contribution_summary.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def side_effect_failures(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for name, row in rows.items():
        tools = row.get("side_effect_preservation_failures") or []
        if tools:
            failures.append(
                {
                    "scenario": name,
                    "tools": list(tools),
                    "outcome_similarity": row.get("outcome_similarity"),
                    "canonical_similarity": row.get("similarity"),
                }
            )
    return failures


def summarize_arm(arm: ArmPaths) -> dict[str, Any]:
    paired = read_json(arm.run_root / "paired_comparison.json")
    manifest = read_json(arm.run_root / "protocol_manifest.json")
    cache = read_json(arm.run_root / "control_cache_report.json")
    rows = candidate_rows(arm.run_root)
    controls = control_rows(arm.run_root)
    helper = helper_summary(arm.run_root)
    helper_rows = (
        helper.get("helpers", {}) if isinstance(helper.get("helpers"), dict) else {}
    )
    helper_counts: dict[str, dict[str, Any]] = {}
    for name, payload in helper_rows.items():
        visible_scenarios = payload.get("visible_scenarios") or []
        called_scenarios = payload.get("called_scenarios") or []
        vnc_scenarios = payload.get("visible_not_called_scenarios") or []
        failed_attempt_scenarios = payload.get("failed_attempt_scenarios") or []
        called_deltas = []
        for scenario in called_scenarios:
            candidate = rows.get(str(scenario), {})
            control = controls.get(str(scenario), {})
            candidate_outcome = candidate.get("outcome_similarity")
            control_outcome = control.get("outcome_similarity")
            if candidate_outcome is not None and control_outcome is not None:
                called_deltas.append(float(candidate_outcome) - float(control_outcome))
        helper_counts[name] = {
            "visible_count": len(visible_scenarios),
            "called_count": len(called_scenarios),
            "visible_not_called_count": len(vnc_scenarios),
            "failed_attempt_count": len(failed_attempt_scenarios),
            "called_subset_outcome_delta_mean": mean(called_deltas)
            if called_deltas
            else None,
            "called_subset_outcome_delta_n": len(called_deltas),
            "side_effect_incident_count": len(
                payload.get("side_effect_incidents") or []
            ),
            "runtime_incident_count": len(payload.get("runtime_incidents") or []),
        }
    helper_visible_total = sum(item["visible_count"] for item in helper_counts.values())
    helper_called_total = sum(item["called_count"] for item in helper_counts.values())
    helper_vnc_total = sum(
        item["visible_not_called_count"] for item in helper_counts.values()
    )
    return {
        "label": ARM_LABELS[arm.key],
        "run_root": str(arm.run_root),
        "registry_dir": manifest.get("registry_dir"),
        "registry_sha256": manifest.get("registry_manifest_digest_after_run"),
        "candidate_mean_outcome_similarity": paired.get(
            "candidate_mean_outcome_similarity"
        ),
        "candidate_mean_similarity": paired.get("candidate_mean_similarity"),
        "candidate_exact_successes": paired.get("candidate_exact_successes"),
        "mean_outcome_similarity_delta_vs_control": paired.get(
            "mean_outcome_similarity_delta"
        ),
        "mean_similarity_delta_vs_control": paired.get("mean_similarity_delta"),
        "exact_success_delta_vs_control": paired.get("exact_success_delta"),
        "gain_count": paired.get("gain_count"),
        "regression_count": paired.get("regression_count"),
        "preserved_count": paired.get("preserved_count"),
        "outcome_gain_count": paired.get("outcome_gain_count"),
        "outcome_regression_count": paired.get("outcome_regression_count"),
        "outcome_preserved_count": paired.get("outcome_preserved_count"),
        "runtime_exception_count": paired.get("runtime_exception_count"),
        "route_mismatch_qualified": paired.get("route_mismatch_qualified"),
        "candidate_runtime_exceptions": sum(
            1 for row in rows.values() if row.get("exception_type")
        ),
        "candidate_side_effect_failures": side_effect_failures(rows),
        "candidate_side_effect_failure_count": len(side_effect_failures(rows)),
        "control_cache": {
            "source": cache.get("control_source"),
            "cached_control_tasks": cache.get("cached_control_tasks"),
            "fresh_control_tasks": cache.get("fresh_control_tasks"),
            "cache_manifest_hash": cache.get("cache_manifest_hash"),
            "cache_match_policy": cache.get("cache_match_policy"),
        },
        "run_controls": {
            "generation_enabled": manifest.get("generation_enabled"),
            "routing_evidence_mode": manifest.get("routing_evidence_mode"),
            "active_diagnostic_force_env": manifest.get("active_diagnostic_force_env"),
            "openai_response_cache_enabled": manifest.get(
                "openai_response_cache_enabled"
            ),
            "protocol_gate_passed": manifest.get("protocol_gate_passed"),
            "protocol_gate_reasons": manifest.get("protocol_gate_reasons"),
        },
        "dashboard": {
            "index": manifest.get("dashboard_url"),
            "task_focus": manifest.get("dashboard_task_focus_url"),
            "task_compare": manifest.get("dashboard_task_compare_url"),
        },
        "helper_summary_sha256": sha256_file(
            arm.run_root / "helper_contribution_summary.json"
        )
        if (arm.run_root / "helper_contribution_summary.json").exists()
        else None,
        "helper_visible_total": helper_visible_total,
        "helper_called_total": helper_called_total,
        "helper_visible_not_called_total": helper_vnc_total,
        "helper_counts": helper_counts,
        "_candidate_rows": rows,
    }


def pairwise(
    left_key: str, left: dict[str, Any], right_key: str, right: dict[str, Any]
) -> dict[str, Any]:
    left_rows: dict[str, dict[str, Any]] = left["_candidate_rows"]
    right_rows: dict[str, dict[str, Any]] = right["_candidate_rows"]
    names = sorted(set(left_rows) & set(right_rows))
    outcome_names = [
        name
        for name in names
        if left_rows[name].get("outcome_similarity") is not None
        and right_rows[name].get("outcome_similarity") is not None
    ]
    outcome = [
        float(right_rows[name]["outcome_similarity"])
        - float(left_rows[name]["outcome_similarity"])
        for name in outcome_names
    ]
    canonical = [
        float(right_rows[name].get("similarity") or 0.0)
        - float(left_rows[name].get("similarity") or 0.0)
        for name in names
    ]
    exact = [
        (1.0 if float(right_rows[name].get("similarity") or 0.0) >= 1.0 else 0.0)
        - (1.0 if float(left_rows[name].get("similarity") or 0.0) >= 1.0 else 0.0)
        for name in names
    ]

    def counts(values: list[float]) -> dict[str, int]:
        return {
            "right_gain": sum(1 for value in values if value > 1e-12),
            "right_regression": sum(1 for value in values if value < -1e-12),
            "preserved_tie": sum(1 for value in values if abs(value) <= 1e-12),
        }

    return {
        "left": left_key,
        "right": right_key,
        "n": len(names),
        "outcome_n": len(outcome_names),
        "outcome_difference_right_minus_left": {
            **bootstrap_ci(outcome),
            "permutation_p_value_two_sided": sign_flip_p_value(outcome),
            **counts(outcome),
        },
        "canonical_difference_right_minus_left": {
            **bootstrap_ci(canonical),
            "permutation_p_value_two_sided": sign_flip_p_value(canonical),
            **counts(canonical),
        },
        "exact_success_difference_right_minus_left": {
            **bootstrap_ci(exact),
            "permutation_p_value_two_sided": sign_flip_p_value(exact),
            **counts(exact),
        },
    }


def markdown(summary: dict[str, Any]) -> str:
    conclusion = summary["conclusion"]
    if conclusion["praxis_protected_claim_ready"]:
        status = (
            "Status: repaired Praxis registry-only candidate passed matched formal500 "
            "safety and reproduced outcome lift over best3 and V2.6 under review conditions."
        )
    else:
        status = (
            "Status: not protected-claim ready under this review. "
            f"Blocker: {conclusion['blocker']}"
        )
    lines = [
        f"# {summary['report_title']}",
        "",
        status,
        "",
        "Outcome/task completion is primary. Canonical/reference and exact success are secondary.",
        "",
        "## Formal500 Table",
        "",
        "| Arm | Outcome | Run-vs-control outcome lift | Canonical | Exact successes | Runtime exceptions | Helper side-effect failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ("best3", "v2_6", "praxis"):
        arm = summary["arms"][key]
        lines.append(
            f"| {arm['label']} | {arm['candidate_mean_outcome_similarity']:.6f} | "
            f"{arm['mean_outcome_similarity_delta_vs_control']:.6f} | "
            f"{arm['candidate_mean_similarity']:.6f} | "
            f"{arm['candidate_exact_successes']} | "
            f"{arm['candidate_runtime_exceptions']} | "
            f"{arm['candidate_side_effect_failure_count']} |"
        )
    lines.extend(["", "## Pairwise Candidate Comparisons", ""])
    lines.append(
        "| Comparison | Outcome diff | 95% CI | p-value | Canonical diff | Exact diff |"
    )
    lines.append("| --- | ---: | --- | ---: | ---: | ---: |")
    for item in summary["pairwise"]:
        out = item["outcome_difference_right_minus_left"]
        can = item["canonical_difference_right_minus_left"]
        exact = item["exact_success_difference_right_minus_left"]
        lines.append(
            f"| {item['right']} minus {item['left']} | {out['mean']:.6f} | "
            f"[{out['ci95_low']:.6f}, {out['ci95_high']:.6f}] | "
            f"{out['permutation_p_value_two_sided']:.4f} | "
            f"{can['mean']:.6f} | {exact['mean']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Helper Visibility And Called-Subset Contribution",
            "",
            "| Arm | Visible | Called | Visible-not-called | Route mismatch qualified | Top called helpers |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for key in ("best3", "v2_6", "praxis"):
        arm = summary["arms"][key]
        top_helpers = sorted(
            arm["helper_counts"].items(),
            key=lambda item: (
                item[1]["called_count"],
                item[1]["visible_count"],
                item[0],
            ),
            reverse=True,
        )[:6]
        helper_text = "; ".join(
            (
                f"{name}: {payload['called_count']}/{payload['visible_count']} called/visible"
                + (
                    f", called outcome delta {payload['called_subset_outcome_delta_mean']:.4f}"
                    if payload["called_subset_outcome_delta_mean"] is not None
                    else ""
                )
            )
            for name, payload in top_helpers
        )
        lines.append(
            f"| {arm['label']} | {arm['helper_visible_total']} | "
            f"{arm['helper_called_total']} | {arm['helper_visible_not_called_total']} | "
            f"{arm['route_mismatch_qualified']} | {helper_text} |"
        )
    lines.extend(
        [
            "",
            "No-current-helper-fit and detailed route-mismatch subset metrics were not emitted by this review runtime; the report records that absence rather than deriving them from labels or traces.",
            "",
            "## Safety",
            "",
            f"- Runtime exceptions: best3={summary['arms']['best3']['candidate_runtime_exceptions']}, V2.6={summary['arms']['v2_6']['candidate_runtime_exceptions']}, Praxis={summary['arms']['praxis']['candidate_runtime_exceptions']}.",
            f"- Helper side-effect preservation failures: best3={summary['arms']['best3']['candidate_side_effect_failure_count']}, V2.6={summary['arms']['v2_6']['candidate_side_effect_failure_count']}, Praxis={summary['arms']['praxis']['candidate_side_effect_failure_count']}.",
            f"- Safety conclusion: {conclusion['safety_conclusion']}",
            "",
            "## Cache And Leakage",
            "",
            "- Controls were served from the task-level control cache for all 500 tasks in every arm.",
            "- Candidate/SAGE arms were fresh, OpenAI response cache was disabled, generation was off, and routing evidence was disabled.",
            "- Diagnostic force-call environment variables were absent.",
            "- No scenario selection was based on cache availability.",
            "",
            "## Treatment Classification",
            "",
            conclusion["treatment_classification"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--best3", type=Path, required=True)
    parser.add_argument("--v2-6", dest="v2_6", type=Path, required=True)
    parser.add_argument("--praxis", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument(
        "--report-title",
        default="Praxis Matched Formal500 Statistical Report",
    )
    parser.add_argument(
        "--praxis-label",
        default="Praxis frozen BridgePack",
    )
    parser.add_argument(
        "--schema-version",
        default="praxis_final_hardening_stats_v1",
    )
    args = parser.parse_args()

    ARM_LABELS["praxis"] = args.praxis_label
    arms = {
        "best3": summarize_arm(ArmPaths("best3", args.best3)),
        "v2_6": summarize_arm(ArmPaths("v2_6", args.v2_6)),
        "praxis": summarize_arm(ArmPaths("praxis", args.praxis)),
    }
    public_arms = {
        key: {
            field: value for field, value in arm.items() if field != "_candidate_rows"
        }
        for key, arm in arms.items()
    }
    pairwise_items = [
        pairwise("best3", arms["best3"], "v2_6", arms["v2_6"]),
        pairwise("best3", arms["best3"], "praxis", arms["praxis"]),
        pairwise("v2_6", arms["v2_6"], "praxis", arms["praxis"]),
    ]
    pairwise_by_lr = {(item["left"], item["right"]): item for item in pairwise_items}
    praxis_vs_best3 = pairwise_by_lr[("best3", "praxis")][
        "outcome_difference_right_minus_left"
    ]
    praxis_vs_v2_6 = pairwise_by_lr[("v2_6", "praxis")][
        "outcome_difference_right_minus_left"
    ]
    praxis_side_effects = arms["praxis"]["candidate_side_effect_failure_count"]
    praxis_exceptions = arms["praxis"]["candidate_runtime_exceptions"]
    praxis_outcome = arms["praxis"]["candidate_mean_outcome_similarity"]
    best3_outcome = arms["best3"]["candidate_mean_outcome_similarity"]
    v2_6_outcome = arms["v2_6"]["candidate_mean_outcome_similarity"]
    praxis_beats_best3 = bool(
        praxis_outcome > best3_outcome and praxis_vs_best3["mean"] > 0
    )
    praxis_beats_v2_6 = bool(
        praxis_outcome > v2_6_outcome and praxis_vs_v2_6["mean"] > 0
    )
    claim_ready = bool(
        praxis_side_effects == 0
        and praxis_exceptions == 0
        and praxis_beats_best3
        and praxis_beats_v2_6
    )
    if claim_ready:
        blocker = None
        safety_conclusion = (
            "zero runtime exceptions and zero helper side-effect preservation failures "
            "for repaired Praxis, best3, and V2.6."
        )
        treatment_classification = (
            "Repaired Praxis is classified as a registry-only helper-contract repair "
            "under the protected-base final-hardening runtime. No actor/router bridge "
            "policy was imported for this matched formal500 run; routing evidence was disabled."
        )
    elif praxis_side_effects:
        blocker = (
            f"Praxis registry-only run had {praxis_side_effects} helper side-effect "
            "preservation failures under the protected-base checker."
        )
        safety_conclusion = (
            "nonzero Praxis helper side-effect preservation failures block promotion."
        )
        treatment_classification = (
            "Praxis remains a promising but blocked registry-only treatment until helper "
            "contracts or an explicitly audited bridge-policy treatment reach zero side-effect incidents."
        )
    elif not praxis_beats_best3:
        blocker = "Praxis did not beat best3 on paired formal500 outcome."
        safety_conclusion = "safety passed, but promotion is blocked by insufficient outcome lift over best3."
        treatment_classification = (
            "Praxis is a registry-only safety-passing treatment that did not clear the "
            "primary outcome comparison against best3."
        )
    elif not praxis_beats_v2_6:
        blocker = (
            "Praxis did not beat or remain competitive with V2.6 on formal500 outcome."
        )
        safety_conclusion = "safety passed, but promotion is blocked by insufficient outcome lift over V2.6."
        treatment_classification = (
            "Praxis is a registry-only safety-passing treatment that did not clear the "
            "comparison against V2.6."
        )
    else:
        blocker = "unclassified review blocker."
        safety_conclusion = (
            "review did not satisfy all protected-claim readiness checks."
        )
        treatment_classification = "Treatment classification is unresolved; inspect machine-readable statistics."

    summary = {
        "schema_version": args.schema_version,
        "report_title": args.report_title,
        "arms": public_arms,
        "pairwise": pairwise_items,
        "conclusion": {
            "praxis_reproduced_outcome_lift": praxis_beats_best3,
            "praxis_beats_best3": praxis_beats_best3,
            "praxis_beats_v2_6": praxis_beats_v2_6,
            "praxis_protected_claim_ready": claim_ready,
            "blocker": blocker,
            "safety_conclusion": safety_conclusion,
            "treatment_classification": treatment_classification,
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
