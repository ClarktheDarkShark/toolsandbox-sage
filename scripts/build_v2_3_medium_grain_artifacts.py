#!/usr/bin/env python3
"""Build V2.3 medium-grain deterministic skill experiment artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    cohort_policy_report,
    expected_birth_opportunities,
    expected_helper_fit,
)
from scripts.build_v2_1_gap_closure_artifacts import BEST3, FROZEN_BEST3

CONFIRMED_V2_2 = {"days_between_timestamps"}
PARKED_LANES = {
    "select_visible_record_by_constraints",
    "prepare_side_effect_args_from_selected_record",
    "select_action_target_by_recency",
    "dependency_precondition_helpers",
    "extract_stock_symbol",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _select(
    prefixes: tuple[str, ...],
    *,
    size: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int = 8,
    include_insufficient: bool = False,
    include_ambiguous: bool = False,
) -> list[ScenarioRecord]:
    candidates = [
        record
        for record in scenario_records()
        if record.name.startswith(prefixes)
        and record.name not in already
        and (
            include_insufficient or "INSUFFICIENT_INFORMATION" not in record.categories
        )
        and (include_ambiguous or "ambiguous" not in record.name)
    ]
    candidates.sort(
        key=lambda record: (
            0 if "_3_distraction_tools_arg_description_scrambled" in record.name else 1,
            0 if "_10_distraction_tools" in record.name else 1,
            base_task_family(record.name),
            record.name,
        )
    )
    selected: list[ScenarioRecord] = []
    for record in candidates:
        if len(selected) >= size:
            break
        family = base_task_family(record.name)
        if family_counts[family] >= max_per_family:
            continue
        selected.append(record)
        already.add(record.name)
        family_counts[family] += 1
    if len(selected) != size:
        raise RuntimeError(
            f"Could only select {len(selected)} of {size} for prefixes {prefixes}"
        )
    return selected


def _extend(
    target: list[ScenarioRecord],
    prefixes: tuple[str, ...],
    *,
    count: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int = 8,
    include_insufficient: bool = False,
    include_ambiguous: bool = False,
) -> None:
    target.extend(
        _select(
            prefixes,
            size=count,
            already=already,
            family_counts=family_counts,
            max_per_family=max_per_family,
            include_insufficient=include_insufficient,
            include_ambiguous=include_ambiguous,
        )
    )


def _records_to_manifest_records(records: list[ScenarioRecord]) -> list[dict[str, Any]]:
    return [record.to_json() for record in records]


def build_manifest() -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()

    early: list[ScenarioRecord] = []
    for prefix, count in (
        ("search_phone_number_with_name", 3),
        ("search_relationship_with_phone_number", 3),
        ("search_sender_phone_number_with_content", 3),
        ("search_name_with_relationship", 3),
        ("update_contact_relationship_with_relationship", 4),
        ("remove_contact_by_phone", 4),
    ):
        _extend(
            early,
            (prefix,),
            count=count,
            already=already,
            family_counts=family_counts,
        )

    held_out: list[ScenarioRecord] = []
    for prefix, count in (
        ("search_phone_number_with_name", 3),
        ("search_relationship_with_phone_number", 3),
        ("search_sender_phone_number_with_content", 3),
        ("search_name_with_relationship", 3),
        ("update_contact_relationship_with_relationship", 4),
        ("remove_contact_by_phone", 4),
        ("update_contact_relationship_with_relationship_twice_multiple_user_turn", 5),
    ):
        _extend(
            held_out,
            (prefix,),
            count=count,
            already=already,
            family_counts=family_counts,
        )

    negative: list[ScenarioRecord] = []
    for prefix, count, include_insufficient in (
        ("add_contact_with_name_and_phone_number", 3, False),
        ("send_message_with_phone_number_and_content", 3, False),
        ("remove_contact_with_id", 3, False),
        ("update_contact_with_id_and_phone_number", 3, False),
        ("remove_contact_by_phone_no_remove_contact_insufficient_information", 2, True),
        (
            "remove_contact_by_phone_no_search_contacts_insufficient_information",
            1,
            True,
        ),
    ):
        _extend(
            negative,
            (prefix,),
            count=count,
            already=already,
            family_counts=family_counts,
            include_insufficient=include_insufficient,
        )

    selected = early + held_out + negative
    if (len(early), len(held_out), len(negative)) != (20, 25, 15):
        raise RuntimeError(
            f"Expected 20/25/15, got {len(early)}/{len(held_out)}/{len(negative)}"
        )
    categories_by_name: dict[str, Iterable[str]] = {
        record.name: record.categories for record in selected
    }
    diversity = cohort_policy_report(
        [record.name for record in selected],
        categories_by_name=categories_by_name,
        generation_enabled=True,
        registry_tool_count=0,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"Cohort quality failed: {diversity['quality_gate_failures']}"
        )
    return {
        "manifest_type": "sage_v2_3_medium_grain_skill_discovery60",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": (
            "Masked-best3 medium-grain skill experiment: early cluster-positive "
            "constraint/action workflows, held-out reuse, and negative/no-helper cases."
        ),
        "masked_tools": sorted(BEST3),
        "confirmed_v2_2_tools_excluded": sorted(CONFIRMED_V2_2),
        "parked_lanes_excluded": sorted(PARKED_LANES),
        "protected_baseline_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "candidate_registry_role": "v2_3_medium_grain_candidate_registry",
        "role_counts": {
            "early_cluster_positive": len(early),
            "held_out_reuse": len(held_out),
            "negative_ambiguity_no_helper": len(negative),
        },
        "splits": {"mechanism_60": _records_to_manifest_records(selected)},
        "split_sizes": {"mechanism_60": len(selected)},
        "cohort_diversity_report": diversity,
        "per_scenario_expectations": [
            {
                "scenario": record.name,
                "role": (
                    "early_cluster_positive"
                    if record in early
                    else "held_out_reuse"
                    if record in held_out
                    else "negative_ambiguity_no_helper"
                ),
                "base_task_family": base_task_family(record.name),
                "expected_helper_fit": expected_helper_fit(
                    record.name, record.categories
                ),
                "expected_birth_opportunities": expected_birth_opportunities(
                    record.name, record.categories
                ),
            }
            for record in selected
        ],
    }


def write_setup_report(manifest: dict[str, Any], path: Path) -> None:
    diversity = manifest["cohort_diversity_report"]
    medium_birth = diversity["expected_birth_opportunity_counts"].get(
        "composite:constraint_to_action_planner", 0
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# V2.3 Medium-Grain Skill Experiment Setup

## Objective

Create a quality-gated masked-best3 discovery60 cohort to test whether a generated medium-grain deterministic workflow helper can outperform prior lightweight selector/prep helpers.

## Protected Assets

- Frozen best3 registry: `{manifest["protected_baseline_registry"]}`
- Masked best3 tools: `{", ".join(manifest["masked_tools"])}`
- Confirmed V2.2 tools excluded from discovery registry: `{", ".join(manifest["confirmed_v2_2_tools_excluded"])}`

## Cohort

- Manifest type: `{manifest["manifest_type"]}`
- Scenarios: `{manifest["split_sizes"]["mechanism_60"]}`
- Role counts: `{manifest["role_counts"]}`
- Cohort quality: `{diversity["quality_gate_status"]}`
- Distinct base task families: `{diversity["distinct_base_task_families"]}`
- Largest family share: `{diversity["largest_family_share"]:.4f}`
- Largest family variants: `{diversity["largest_family_variant_count"]}`
- Medium-grain birth opportunities: `{medium_birth}`
- Warnings: `{diversity["warnings"]}`

## Decision Label

`medium-grain discovery ready`
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/summaries/v2_3_medium_grain")
    )
    parser.add_argument(
        "--candidate-registry-dir",
        type=Path,
        default=Path("artifacts/registry_candidates/v2_3_medium_grain"),
    )
    args = parser.parse_args()

    manifest = build_manifest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.candidate_registry_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "cohort_manifest.json", manifest)
    _write_json(
        args.output_dir / "cohort_diversity_report.json",
        manifest["cohort_diversity_report"],
    )
    _write_json(args.candidate_registry_dir / "registry_manifest.json", {"tools": {}})
    _write_json(
        args.candidate_registry_dir / "registry_lock.json",
        {
            "label": "v2_3_medium_grain_candidate_registry",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "masked_tools": sorted(BEST3),
            "confirmed_v2_2_tools_excluded": sorted(CONFIRMED_V2_2),
            "parked_lanes_excluded": sorted(PARKED_LANES),
        },
    )
    write_setup_report(
        manifest,
        Path("docs/sage_protocol/v2_3_medium_grain_skill_experiment_report.md"),
    )
    print(args.output_dir / "cohort_manifest.json")
    print(args.output_dir / "cohort_diversity_report.json")
    print(args.candidate_registry_dir / "registry_manifest.json")


if __name__ == "__main__":
    main()
