#!/usr/bin/env python3
"""Compare standard and native-action SAGE arms from one matched study."""

from __future__ import annotations

import argparse
import ast
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


def _single(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"Expected one {pattern!r} under {root}, found {len(matches)}")
    return matches[0]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _called_function_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _paired_statistics(differences: list[float]) -> dict[str, Any]:
    if not differences:
        return {
            "mean_difference": None,
            "bootstrap_95_ci": [None, None],
            "randomization_p_value": None,
            "exact_sign_test_p_value": None,
        }

    iterations = 50_000
    observed = statistics.fmean(differences)
    bootstrap_rng = random.Random(20260719)
    bootstrap = [
        statistics.fmean(bootstrap_rng.choices(differences, k=len(differences)))
        for _ in range(iterations)
    ]

    randomization_rng = random.Random(20260720)
    extreme = 0
    for _ in range(iterations):
        randomized = statistics.fmean(
            delta if randomization_rng.getrandbits(1) else -delta
            for delta in differences
        )
        extreme += abs(randomized) >= abs(observed)

    non_ties = [delta for delta in differences if abs(delta) > 1e-12]
    positive = sum(delta > 0 for delta in non_ties)
    negative = len(non_ties) - positive
    tail = sum(
        math.comb(len(non_ties), count) for count in range(min(positive, negative) + 1)
    )
    sign_p_value = min(1.0, 2.0 * tail / (2 ** len(non_ties)))

    return {
        "mean_difference": observed,
        "bootstrap_95_ci": [
            _percentile(bootstrap, 0.025),
            _percentile(bootstrap, 0.975),
        ],
        "randomization_p_value": (extreme + 1) / (iterations + 1),
        "exact_sign_test_p_value": sign_p_value,
        "iterations": iterations,
        "random_seed": 20260719,
    }


def _delegated_native_action_scenarios(
    arm_root: Path,
    generated_tool_name: str,
    native_action_names: set[str],
) -> list[str]:
    """Find native traces emitted inside one generated-tool invocation."""

    executed: list[str] = []
    for path in arm_root.glob("*/candidate/*/trajectories/*/execution_context.json"):
        payload = _load(path)
        rows = payload.get("_dbs", {}).get("SANDBOX", [])
        if not isinstance(rows, list):
            continue
        found = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("openai_function_name") or "") != generated_tool_name:
                continue
            traces = row.get("tool_trace")
            if not isinstance(traces, list):
                continue
            for trace in traces:
                try:
                    trace_payload = json.loads(str(trace))
                except (TypeError, ValueError):
                    continue
                if str(trace_payload.get("tool_name") or "") in native_action_names:
                    found = True
                    break
            if found:
                break
        if found:
            executed.append(path.parent.name)
    return sorted(set(executed))


def _arm_summary(arm_root: Path, artifact_root: Path) -> dict[str, Any]:
    comparison = _load(_single(arm_root, "*/paired_comparison.json"))
    contribution = _load(_single(arm_root, "*/helper_contribution_summary.json"))
    registry_path = artifact_root.joinpath("registry_manifest.json")
    if not registry_path.exists():
        # Final registry gating may restore the starting registry while preserving
        # the evaluated candidate registry beside the run outputs.
        registry_path = _single(
            arm_root, "*/registry_gate/registry_manifest_failed_gate.json"
        )
    registry = _load(registry_path)

    native_action_tools: list[dict[str, Any]] = []
    for name, entry in registry.get("tools", {}).items():
        tool = entry.get("tool", {})
        spec = tool.get("spec", {})
        required = set(spec.get("required_original_tool_calls", []))
        direct_calls = sorted(
            required & _called_function_names(str(tool.get("code", "")))
        )
        if direct_calls:
            validation = entry.get("validation", {})
            contribution_record = contribution.get("helpers", {}).get(name, {})
            executed_scenarios = _delegated_native_action_scenarios(
                arm_root, name, set(direct_calls)
            )
            native_action_tools.append(
                {
                    "tool": name,
                    "native_actions": direct_calls,
                    "source_examples": validation.get("source_example_count"),
                    "held_out_checks": validation.get("held_out_check_count"),
                    "negative_checks": validation.get("negative_applicability_count"),
                    "visible_count": contribution_record.get("visible_count", 0),
                    "called_count": contribution_record.get("called_count", 0),
                    "failed_attempt_count": contribution_record.get(
                        "failed_attempt_count", 0
                    ),
                    "native_action_executed_count": len(executed_scenarios),
                    "native_action_executed_scenarios": executed_scenarios,
                    "visible_scenarios": contribution_record.get(
                        "visible_scenarios", []
                    ),
                    "called_scenarios": contribution_record.get("called_scenarios", []),
                }
            )

    side_effect_preservation_flags = 0
    runtime_incidents = 0
    for item in contribution.get("helpers", {}).values():
        side_effect_preservation_flags += len(item.get("side_effect_incidents", []))
        runtime_incidents += len(item.get("runtime_incidents", []))

    candidate = comparison["candidate"]
    outcome_by_scenario = {
        row["scenario"]: row.get("candidate_outcome_similarity")
        for row in comparison.get("deltas", [])
    }
    return {
        "outcome": comparison.get("candidate_mean_outcome_similarity"),
        "outcome_vs_control_delta": comparison.get("mean_outcome_similarity_delta"),
        "score": comparison.get("candidate_mean_similarity"),
        "score_vs_control_delta": comparison.get("mean_similarity_delta"),
        "outcome_successes": candidate.get("outcome_success_count"),
        "outcome_scored_tasks": candidate.get("outcome_score_available_count"),
        "accepted_tools": candidate.get("accepted_tool_count"),
        "tool_births": candidate.get("tool_generation_count"),
        "tool_reuse_events": candidate.get("reuse_count"),
        "runtime_exceptions": candidate.get("exception_count"),
        "generated_tool_called_scenarios": len(
            {
                scenario
                for item in contribution.get("helpers", {}).values()
                for scenario in item.get("called_scenarios", [])
            }
        ),
        "side_effect_preservation_flags": side_effect_preservation_flags,
        "tool_runtime_incidents": runtime_incidents,
        "native_action_tools": native_action_tools,
        "outcome_by_scenario": outcome_by_scenario,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("study_output_root", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args()

    output_root = args.study_output_root
    artifact_root = args.artifact_root or Path(
        str(output_root).replace("outputs/", "artifacts/", 1)
    )
    standard = _arm_summary(
        output_root / "standard", artifact_root / "standard_registry"
    )
    native = _arm_summary(
        output_root / "native_action", artifact_root / "native_action_registry"
    )

    standard_rows = standard.pop("outcome_by_scenario")
    native_rows = native.pop("outcome_by_scenario")
    common = sorted(set(standard_rows) & set(native_rows))
    paired = [
        (name, standard_rows[name], native_rows[name])
        for name in common
        if standard_rows[name] is not None and native_rows[name] is not None
    ]
    differences = [
        (name, native_value - standard_value)
        for name, standard_value, native_value in paired
    ]
    paired_statistics = _paired_statistics([delta for _, delta in differences])
    tolerance = 1e-12
    report = {
        "study_output_root": str(output_root),
        "primary_metric": "outcome/task-completion score",
        "standard": standard,
        "native_action": native,
        "direct_comparison": {
            "native_minus_standard_outcome": native["outcome"] - standard["outcome"],
            "paired_outcome_task_count": len(paired),
            "native_wins": sum(delta > tolerance for _, delta in differences),
            "standard_wins": sum(delta < -tolerance for _, delta in differences),
            "ties": sum(abs(delta) <= tolerance for _, delta in differences),
            "paired_statistics": paired_statistics,
            "largest_native_gains": sorted(
                (
                    {"scenario": name, "outcome_delta": delta}
                    for name, delta in differences
                ),
                key=lambda row: row["outcome_delta"],
                reverse=True,
            )[:10],
            "largest_native_regressions": sorted(
                (
                    {"scenario": name, "outcome_delta": delta}
                    for name, delta in differences
                ),
                key=lambda row: row["outcome_delta"],
            )[:10],
        },
    }
    destination = artifact_root / "comparison_summary.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
