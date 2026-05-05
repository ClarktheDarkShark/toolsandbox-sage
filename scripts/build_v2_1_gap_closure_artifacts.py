#!/usr/bin/env python3
"""Build V2.1 gap-atlas and a quality-gated gap-closure discovery manifest."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    cohort_policy_report,
    expected_birth_opportunities,
    expected_helper_fit,
)

FORMAL250 = Path(
    "outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/"
    "validate_250_20260504_052222/paired_comparison.json"
)
ROBUST60 = Path(
    "outputs/v2_best3_robustness60_clean_20260504_070424/"
    "mechanism_40_20260504_070441/paired_comparison.json"
)
SELECT_ACTION_CONFIRM60 = Path(
    "outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/"
    "mechanism_60_20260504_213336/paired_comparison.json"
)
FROZEN_BEST3 = Path("artifacts/registry_frozen_best3_claim")

BEST3 = {
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_record_by_timestamp_extreme",
}

CONSTRAINT_PREFIXES = (
    "remove_contact_by_phone",
    "search_phone_number_with_name",
    "search_relationship_with_phone_number",
    "search_sender_phone_number_with_content",
    "update_contact_relationship_with_relationship",
    "search_name_with_relationship",
)
SIDE_EFFECT_PREFIXES = (
    "remove_contact_by_phone",
    "update_contact_relationship_with_relationship",
)
RECENCY_ACTION_PREFIXES = (
    "modify_contact_with_message_recency",
    "modify_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest",
)
SEARCH_RESIDUAL_PREFIXES = (
    "search_message_with_recency",
    "search_reminder_with",
)
SERVICE_PREFIXES = (
    "cellular_off",
    "get_wifi",
    "get_cellular",
    "turn_on",
    "send_message_with_contact_content_cellular_off",
    "find_days_till_holiday_wifi_off",
    "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _cluster_id(scenario: str) -> str:
    if scenario.startswith(CONSTRAINT_PREFIXES):
        return "constraint_visible_record_selector"
    if scenario.startswith(SIDE_EFFECT_PREFIXES):
        return "side_effect_argument_preparer_after_selection"
    if scenario.startswith(RECENCY_ACTION_PREFIXES):
        return "recency_action_target_selector_parked"
    if scenario.startswith(SEARCH_RESIDUAL_PREFIXES):
        return "search_plus_selection_or_window_residual"
    if scenario.startswith(("find_days_till_holiday", "find_thanksgiving_timestamp")):
        return "holiday_calendar_distance"
    if scenario.startswith(SERVICE_PREFIXES):
        return "service_precondition_or_state_parked"
    if "insufficient_information" in scenario:
        return "insufficient_information_negative"
    return "other_no_helper_or_direct"


def build_gap_atlas() -> dict[str, Any]:
    sources = {
        "formal250": FORMAL250,
        "robustness60": ROBUST60,
        "select_action_confirmation60": SELECT_ACTION_CONFIRM60,
    }
    records: list[dict[str, Any]] = []
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_name, path in sources.items():
        if not path.exists():
            continue
        comparison = _load_json(path)
        for row in comparison.get("deltas", []):
            scenario = str(row["scenario"])
            helper_fit = expected_helper_fit(scenario)
            best3_fit = [helper for helper in helper_fit if helper in BEST3]
            record = {
                "source": source_name,
                "scenario": scenario,
                "base_family": base_task_family(scenario),
                "cluster_id": _cluster_id(scenario),
                "canonical_delta": row.get("delta"),
                "outcome_delta": row.get("outcome_delta"),
                "control_outcome_similarity": row.get("control_outcome_similarity"),
                "candidate_outcome_similarity": row.get("candidate_outcome_similarity"),
                "expected_helper_fit": helper_fit,
                "best3_helper_fit": best3_fit,
                "expected_birth_opportunities": expected_birth_opportunities(scenario),
            }
            records.append(record)
            clusters[record["cluster_id"]].append(record)

    ranked_clusters: list[dict[str, Any]] = []
    for cluster_id, items in clusters.items():
        outcome_values = [
            float(item["outcome_delta"])
            for item in items
            if isinstance(item.get("outcome_delta"), (int, float))
        ]
        regressions = [item for item in items if (item.get("outcome_delta") or 0.0) < 0]
        gains = [item for item in items if (item.get("outcome_delta") or 0.0) > 0]
        no_best3 = [item for item in items if not item["best3_helper_fit"]]
        families = Counter(item["base_family"] for item in items)
        birth_opportunities = Counter(
            opportunity
            for item in items
            for opportunity in item["expected_birth_opportunities"]
        )
        deterministic_potential = {
            "constraint_visible_record_selector": 5,
            "side_effect_argument_preparer_after_selection": 4,
            "search_plus_selection_or_window_residual": 3,
            "holiday_calendar_distance": 3,
            "other_no_helper_or_direct": 2,
            "recency_action_target_selector_parked": 1,
            "service_precondition_or_state_parked": 1,
            "insufficient_information_negative": 1,
        }.get(cluster_id, 2)
        score = (
            len(regressions) * 3
            + len(no_best3)
            + len(families) * 2
            + deterministic_potential * 4
        )
        if "parked" in cluster_id:
            score -= 20
        ranked_clusters.append(
            {
                "cluster_id": cluster_id,
                "scenario_count": len(items),
                "base_family_count": len(families),
                "base_families": dict(families.most_common()),
                "mean_outcome_delta": (
                    sum(outcome_values) / len(outcome_values)
                    if outcome_values
                    else None
                ),
                "outcome_regressions": len(regressions),
                "outcome_gains": len(gains),
                "no_best3_fit_count": len(no_best3),
                "birth_opportunity_counts": dict(birth_opportunities.most_common()),
                "deterministic_helper_potential": deterministic_potential,
                "rank_score": score,
                "worst_examples": sorted(
                    (
                        {
                            "source": item["source"],
                            "scenario": item["scenario"],
                            "outcome_delta": item["outcome_delta"],
                            "canonical_delta": item["canonical_delta"],
                            "best3_helper_fit": item["best3_helper_fit"],
                            "expected_birth_opportunities": item[
                                "expected_birth_opportunities"
                            ],
                        }
                        for item in items
                    ),
                    key=lambda item: (
                        item["outcome_delta"]
                        if isinstance(item["outcome_delta"], (int, float))
                        else 0.0
                    ),
                )[:10],
            }
        )
    ranked_clusters.sort(
        key=lambda item: float(item.get("rank_score", 0.0)),
        reverse=True,
    )
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {key: str(path) for key, path in sources.items()},
        "protected_frozen_best3_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "record_count": len(records),
        "ranked_clusters": ranked_clusters,
        "shortfall_records": records,
        "recommendation": (
            "Prioritize constraint_visible_record_selector plus "
            "side_effect_argument_preparer_after_selection. The prior "
            "recency-action and dependency/precondition concepts are parked because "
            "fair-call diagnostics or confirmation showed negative called-subset "
            "value."
        ),
    }


def _select(
    prefixes: tuple[str, ...],
    *,
    size: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int,
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
    return selected


def build_manifest() -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    max_per_family = 8

    early: list[ScenarioRecord] = []
    for prefixes, count in (
        (("search_phone_number_with_name",), 4),
        (("search_relationship_with_phone_number",), 4),
        (("search_sender_phone_number_with_content",), 4),
        (("update_contact_relationship_with_relationship",), 4),
        (("remove_contact_by_phone",), 4),
    ):
        early.extend(
            _select(
                prefixes,
                size=count,
                already=already,
                family_counts=family_counts,
                max_per_family=max_per_family,
            )
        )

    held_out: list[ScenarioRecord] = []
    for prefixes, count in (
        (("search_name_with_relationship",), 3),
        (("search_phone_number_with_name",), 3),
        (("search_relationship_with_phone_number",), 3),
        (("search_sender_phone_number_with_content",), 3),
        (("update_contact_relationship_with_relationship",), 2),
        (("remove_contact_by_phone",), 2),
    ):
        held_out.extend(
            _select(
                prefixes,
                size=count,
                already=already,
                family_counts=family_counts,
                max_per_family=max_per_family,
            )
        )

    negative: list[ScenarioRecord] = []
    negative_plan: tuple[tuple[tuple[str, ...], int, bool, bool], ...] = (
        (("remove_contact_by_phone",), 2, False, True),
        (("update_contact_relationship_with_relationship",), 2, False, True),
        (
            ("remove_contact_by_phone_no_remove_contact_insufficient_information",),
            2,
            True,
            False,
        ),
        (
            ("remove_contact_by_phone_no_search_contacts_insufficient_information",),
            2,
            True,
            False,
        ),
        (("remove_contact_with_id",), 3, False, False),
        (("add_contact_with_name_and_phone_number",), 2, False, False),
        (("get_wifi", "get_cellular"), 2, False, False),
    )
    for neg_prefixes, count, include_insufficient, include_ambiguous in negative_plan:
        negative.extend(
            _select(
                neg_prefixes,
                size=count,
                already=already,
                family_counts=family_counts,
                max_per_family=max_per_family,
                include_insufficient=include_insufficient,
                include_ambiguous=include_ambiguous,
            )
        )

    if len(early) + len(held_out) + len(negative) < 60:
        # Fill only with direct/no-helper negatives so cached availability or a
        # known winning helper lane cannot dominate the discovery decision.
        remaining = 60 - (len(early) + len(held_out) + len(negative))
        negative.extend(
            _select(
                (
                    "send_message_with_phone_number_and_content",
                    "update_contact_with_id_and_phone_number",
                    "add_contact_with_name_and_phone_number",
                    "remove_contact_with_id",
                ),
                size=remaining,
                already=already,
                family_counts=family_counts,
                max_per_family=max_per_family,
            )
        )

    selected = early + held_out + negative
    if len(selected) != 60:
        raise RuntimeError(f"Expected 60 scenarios, selected {len(selected)}")

    categories_by_name: dict[str, Iterable[str]] = {
        record.name: record.categories for record in selected
    }
    diversity = cohort_policy_report(
        [record.name for record in selected],
        categories_by_name=categories_by_name,
        generation_enabled=True,
        registry_tool_count=3,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"Cohort quality failed: {diversity['quality_gate_failures']}"
        )

    return {
        "manifest_type": "sage_v2_1_gap_closure_discovery60",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": (
            "20 early constraint/side-effect-positive examples, 25 held-out "
            "reuse examples, and 15 ambiguity/direct/no-helper negatives. "
            "Recency-action and dependency/precondition lanes are intentionally "
            "not emphasized because they were parked by prior diagnostics."
        ),
        "protected_baseline_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "splits": {"mechanism_60": [record.to_json() for record in selected]},
        "split_sizes": {"mechanism_60": len(selected)},
        "role_counts": {
            "early_cluster_positive": len(early),
            "held_out_reuse": len(held_out),
            "negative_or_ambiguity": len(negative),
        },
        "cohort_diversity_report": diversity,
    }


def write_markdown_report(
    atlas: dict[str, Any], manifest: dict[str, Any], path: Path
) -> None:
    rows = []
    for cluster in atlas["ranked_clusters"]:
        mean_outcome_delta = cluster["mean_outcome_delta"] or 0.0
        rows.append(
            f"| {cluster['cluster_id']} | {cluster['scenario_count']} | "
            f"{cluster['base_family_count']} | {cluster['outcome_regressions']} | "
            f"{cluster['no_best3_fit_count']} | {mean_outcome_delta:.4f} | "
            f"{cluster['rank_score']} |"
        )
    md = f"""# V2.1 Gap Atlas Report

## Objective

Rank the remaining post-best3 shortfall clusters and build the next quality-gated discovery60 manifest without modifying frozen best3 evidence.

## Sources

- Formal 250: `{FORMAL250}`
- Robustness 60: `{ROBUST60}`
- Select-action confirmation60: `{SELECT_ACTION_CONFIRM60}`
- Protected registry: `{FROZEN_BEST3 / "registry_manifest.json"}`

## Ranked Clusters

| Cluster | Scenarios | Families | Outcome regressions | No best3 fit | Mean outcome delta | Rank score |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Decision

The next run should test `constraint_visible_record_selector` and `side_effect_argument_preparer_after_selection`. These are higher value than another recency-action test because the recency-action selector was callable but negative in confirmation60. Dependency/precondition remains parked because force-call diagnostics were non-positive and had one side-effect preservation failure.

## Discovery60 Manifest

- Manifest type: `{manifest["manifest_type"]}`
- Scenario count: `{manifest["split_sizes"]["mechanism_60"]}`
- Role counts: `{manifest["role_counts"]}`
- Quality gate: `{manifest["cohort_diversity_report"]["quality_gate_status"]}`
- Distinct base families: `{manifest["cohort_diversity_report"]["distinct_base_task_families"]}`
- Largest family share: `{manifest["cohort_diversity_report"]["largest_family_share"]:.3f}`
- No-current-helper-fit share: `{manifest["cohort_diversity_report"]["no_current_helper_fit_share"]:.3f}`

## Decision Label

`candidate discovery ready`
"""
    path.write_text(md, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/summaries/v2_1_gap_closure"),
    )
    parser.add_argument(
        "--candidate-registry-dir",
        type=Path,
        default=Path("artifacts/registry_candidates/v2_1_gap_closure_discovery60"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.candidate_registry_dir.mkdir(parents=True, exist_ok=True)

    atlas = build_gap_atlas()
    manifest = build_manifest()
    (args.output_dir / "gap_atlas.json").write_text(
        json.dumps(atlas, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "cohort_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "cohort_diversity_report.json").write_text(
        json.dumps(manifest["cohort_diversity_report"], indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown_report(
        atlas, manifest, Path("docs/sage_protocol/v2_1_gap_atlas_report.md")
    )

    for item in FROZEN_BEST3.iterdir():
        target = args.candidate_registry_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    print(args.output_dir / "cohort_manifest.json")
    print(args.candidate_registry_dir / "registry_manifest.json")


if __name__ == "__main__":
    main()
