#!/usr/bin/env python3
"""Build V2.2 masked-best3 loop-2 atlas and manifests."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, cast

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    cohort_policy_report,
    expected_birth_opportunities,
    expected_helper_fit,
)
from scripts.build_v2_1_gap_closure_artifacts import (
    BEST3,
    CONSTRAINT_PREFIXES,
    FROZEN_BEST3,
    RECENCY_ACTION_PREFIXES,
    SEARCH_RESIDUAL_PREFIXES,
    SERVICE_PREFIXES,
    SIDE_EFFECT_PREFIXES,
    _load_json,
)

SOURCES: dict[str, Path] = {
    "formal250": Path(
        "outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/"
        "validate_250_20260504_052222/paired_comparison.json"
    ),
    "robustness60": Path(
        "outputs/v2_best3_robustness60_clean_20260504_070424/"
        "mechanism_40_20260504_070441/paired_comparison.json"
    ),
    "formal500": Path(
        "outputs/v2_1_formal500_best3_parallel_20260504_232126/"
        "full_benchmark_20260504_232130/paired_comparison.json"
    ),
    "formal1032": Path(
        "outputs/v2_1_formal1000_best3_full_20260505_004901/"
        "full_benchmark_20260505_004905/paired_comparison.json"
    ),
    "v2_2_masked_discovery60": Path(
        "outputs/v2_2_masked_best3_discovery60_20260505_064113/"
        "mechanism_60_20260505_064202/paired_comparison.json"
    ),
    "v2_2_days_confirmation60": Path(
        "outputs/v2_2_days_between_confirmation60_resume_20260505_081500/"
        "mechanism_60_20260505_081108/paired_comparison.json"
    ),
}

PREVIOUS_V2_2_REGISTRY = Path(
    "artifacts/registry_candidates/v2_2_masked_best3_discovery60_20260505_064113/"
    "registry_manifest.json"
)

CONFIRMED_V2_2 = {"days_between_timestamps"}
PARKED_LANES = {
    "dependency_precondition",
    "side_effect_argument_preparer_after_selection",
    "recency_action_target_selector",
}

_SCENARIO_CACHE: list[ScenarioRecord] | None = None


def _all_scenario_records() -> list[ScenarioRecord]:
    global _SCENARIO_CACHE
    if _SCENARIO_CACHE is None:
        _SCENARIO_CACHE = list(scenario_records())
    return _SCENARIO_CACHE


def _select_records(
    prefixes: tuple[str, ...],
    *,
    size: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int,
    include_insufficient: bool = False,
    include_ambiguous: bool = False,
) -> list[ScenarioRecord]:
    allow_low_battery = any("low_battery_mode" in prefix for prefix in prefixes)
    candidates = [
        record
        for record in _all_scenario_records()
        if record.name.startswith(prefixes)
        and record.name not in already
        and (allow_low_battery or "low_battery_mode" not in record.name)
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


def _loop2_cluster_id(scenario: str) -> str:
    name = scenario.lower()
    if name.startswith(("find_days_till_holiday", "find_thanksgiving_timestamp")):
        return "confirmed_days_between_timestamps_covered"
    if expected_helper_fit(scenario) and set(expected_helper_fit(scenario)) & BEST3:
        return "best3_adjacent_or_covered"
    if name.startswith(SERVICE_PREFIXES):
        return "parked_dependency_precondition"
    if name.startswith(SIDE_EFFECT_PREFIXES):
        return "parked_side_effect_argument_preparer_after_selection"
    if name.startswith(RECENCY_ACTION_PREFIXES):
        return "parked_recency_action_target_selector"
    if name.startswith(SEARCH_RESIDUAL_PREFIXES):
        return "best3_adjacent_or_covered"
    if "insufficient_information" not in name and name.startswith(
        "find_stock_symbol_with_company_name"
    ):
        return "stock_symbol_extraction"
    if "insufficient_information" not in name and name.startswith(CONSTRAINT_PREFIXES):
        return "selector_actor_policy_diagnostic_lane"
    if "insufficient_information" in name:
        return "insufficient_information_or_negative"
    if name.startswith(
        ("find_distance_with_location_name", "find_temperature_f_with_location")
    ):
        return "location_lookup_answer_extraction"
    return "other_no_current_helper_fit"


def build_loop2_gap_atlas() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_name, path in SOURCES.items():
        if not path.exists():
            continue
        comparison = _load_json(path)
        for row in comparison.get("deltas", []):
            scenario = str(row["scenario"])
            helper_fit = expected_helper_fit(scenario)
            cluster_id = _loop2_cluster_id(scenario)
            record = {
                "source": source_name,
                "scenario": scenario,
                "base_family": base_task_family(scenario),
                "cluster_id": cluster_id,
                "canonical_delta": row.get("delta"),
                "outcome_delta": row.get("outcome_delta"),
                "control_outcome_similarity": row.get("control_outcome_similarity"),
                "candidate_outcome_similarity": row.get("candidate_outcome_similarity"),
                "expected_helper_fit": helper_fit,
                "expected_birth_opportunities": expected_birth_opportunities(scenario),
            }
            records.append(record)
            clusters[cluster_id].append(record)

    status_by_cluster = {
        "confirmed_days_between_timestamps_covered": "excluded_confirmed",
        "best3_adjacent_or_covered": "excluded_best3_adjacent",
        "parked_dependency_precondition": "excluded_parked",
        "parked_side_effect_argument_preparer_after_selection": "excluded_parked",
        "parked_recency_action_target_selector": "excluded_parked",
        "selector_actor_policy_diagnostic_lane": "diagnostic_pending_actor_policy",
        "stock_symbol_extraction": "candidate_discovery_ready",
        "location_lookup_answer_extraction": "candidate_discovery_ready",
        "insufficient_information_or_negative": "negative_or_abstention_support",
        "other_no_current_helper_fit": "candidate_discovery_ready",
    }
    potential = {
        "stock_symbol_extraction": 5,
        "selector_actor_policy_diagnostic_lane": 4,
        "location_lookup_answer_extraction": 3,
        "other_no_current_helper_fit": 2,
        "insufficient_information_or_negative": 1,
    }
    ranked: list[dict[str, Any]] = []
    for cluster_id, items in clusters.items():
        outcome_values = [
            float(item["outcome_delta"])
            for item in items
            if isinstance(item.get("outcome_delta"), (int, float))
        ]
        regressions = [
            item for item in items if float(item.get("outcome_delta") or 0) < 0
        ]
        families = Counter(item["base_family"] for item in items)
        birth_opportunities = Counter(
            opportunity
            for item in items
            for opportunity in item["expected_birth_opportunities"]
        )
        no_current_fit = [
            item
            for item in items
            if not item["expected_helper_fit"]
            or not set(item["expected_helper_fit"]) & (BEST3 | CONFIRMED_V2_2)
        ]
        cluster_potential = potential.get(cluster_id, 1)
        rank_score = (
            len(regressions) * 3
            + len(no_current_fit)
            + len(families) * 2
            + cluster_potential * 4
        )
        status = status_by_cluster.get(cluster_id, "candidate_discovery_ready")
        if status.startswith("excluded"):
            rank_score -= 100
        if status == "diagnostic_pending_actor_policy":
            rank_score -= 10
        ranked.append(
            {
                "cluster_id": cluster_id,
                "status": status,
                "scenario_count": len(items),
                "base_family_count": len(families),
                "base_families": dict(families.most_common()),
                "mean_outcome_delta": (
                    sum(outcome_values) / len(outcome_values)
                    if outcome_values
                    else None
                ),
                "outcome_regressions": len(regressions),
                "no_current_or_unconfirmed_helper_fit_count": len(no_current_fit),
                "birth_opportunity_counts": dict(birth_opportunities.most_common()),
                "deterministic_helper_potential": cluster_potential,
                "rank_score": rank_score,
                "worst_examples": sorted(
                    (
                        {
                            "source": item["source"],
                            "scenario": item["scenario"],
                            "outcome_delta": item["outcome_delta"],
                            "canonical_delta": item["canonical_delta"],
                            "expected_helper_fit": item["expected_helper_fit"],
                            "expected_birth_opportunities": item[
                                "expected_birth_opportunities"
                            ],
                        }
                        for item in items
                    ),
                    key=lambda item: float(item["outcome_delta"] or 0),
                )[:8],
            }
        )
    ranked.sort(key=lambda item: float(item.get("rank_score", 0.0)), reverse=True)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {name: str(path) for name, path in SOURCES.items()},
        "protected_frozen_best3_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "masked_best3_tools": sorted(BEST3),
        "confirmed_v2_2_tools": sorted(CONFIRMED_V2_2),
        "parked_lanes": sorted(PARKED_LANES),
        "record_count": len(records),
        "ranked_clusters": ranked,
        "shortfall_records": records,
        "recommendation": (
            "Run the bounded selector actor-policy diagnostic first. If selector "
            "natural adoption remains zero, keep it parked and run loop-2 discovery "
            "on stock-symbol extraction plus location/answer-extraction and negative "
            "support lanes; do not repeat dependency/precondition or selected-record "
            "side-effect-prep lanes."
        ),
    }


def _manifest_from_records(
    *,
    manifest_type: str,
    selected: list[ScenarioRecord],
    generation_enabled: bool,
    registry_tool_count: int,
    role_counts: dict[str, int],
    strategy: str,
) -> dict[str, Any]:
    categories_by_name: dict[str, Iterable[str]] = {
        record.name: record.categories for record in selected
    }
    diversity = cohort_policy_report(
        [record.name for record in selected],
        categories_by_name=categories_by_name,
        generation_enabled=generation_enabled,
        registry_tool_count=registry_tool_count,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"Cohort quality failed for {manifest_type}: "
            f"{diversity['quality_gate_failures']}"
        )
    split_key = "mechanism_60" if len(selected) == 60 else "mechanism_40"
    return {
        "manifest_type": manifest_type,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": strategy,
        "masked_tools": sorted(BEST3),
        "confirmed_v2_2_tools": sorted(CONFIRMED_V2_2),
        "protected_baseline_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "splits": {split_key: [record.to_json() for record in selected]},
        "split_sizes": {split_key: len(selected)},
        "role_counts": role_counts,
        "cohort_diversity_report": diversity,
    }


def build_selector20_manifest() -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    selected: list[ScenarioRecord] = []
    for prefix in (
        "search_phone_number_with_name",
        "search_relationship_with_phone_number",
        "search_sender_phone_number_with_content",
        "search_name_with_relationship",
        "update_contact_relationship_with_relationship",
        "remove_contact_by_phone",
        "remove_contact_by_phone_no_remove_contact_insufficient_information",
        "remove_contact_by_phone_no_search_contacts_insufficient_information",
        "add_contact_with_name_and_phone_number",
        "send_message_with_phone_number_and_content",
    ):
        selected.extend(
            _select_records(
                (prefix,),
                size=2,
                already=already,
                family_counts=family_counts,
                max_per_family=2,
                include_insufficient="insufficient_information" in prefix,
            )
        )
    if len(selected) != 20:
        raise RuntimeError(f"Expected selector diagnostic 20, selected {len(selected)}")
    return _manifest_from_records(
        manifest_type="sage_v2_2_selector_actor_policy_diagnostic20",
        selected=selected,
        generation_enabled=False,
        registry_tool_count=1,
        role_counts={
            "selector_positive": 12,
            "negative_or_no_helper": 8,
        },
        strategy=(
            "Focused selector adoption diagnostic: expose one valid selector after "
            "the bounded actor-policy repair across 12 selector-positive and 8 "
            "negative/no-helper cases."
        ),
    )


def build_discovery60_manifest(*, selector_lane_revived: bool) -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    early: list[ScenarioRecord] = []
    held_out: list[ScenarioRecord] = []
    negative: list[ScenarioRecord] = []

    early_plan = (
        [
            ("find_stock_symbol_with_company_name", 4),
            ("find_distance_with_location_name", 3),
            ("find_temperature_f_with_location", 3),
            ("convert_currency", 2),
            ("convert_currency_canonicalize", 2),
            ("find_address_with_lat_lon", 2),
            ("search_phone_number_with_name", 2),
            ("search_relationship_with_phone_number", 2),
        ]
        if selector_lane_revived
        else [
            ("find_stock_symbol_with_company_name", 2),
            ("find_stock_symbol_with_company_name_low_battery_mode", 2),
            ("find_distance_with_location_name", 4),
            ("find_temperature_f_with_location", 4),
            ("convert_currency", 2),
            ("convert_currency_canonicalize", 2),
            ("find_address_with_lat_lon", 2),
            ("find_phone_number_with_location_name", 2),
        ]
    )
    for prefix, count in early_plan:
        if count:
            early.extend(
                _select_records(
                    (prefix,),
                    size=count,
                    already=already,
                    family_counts=family_counts,
                    max_per_family=8,
                )
            )
    held_out_plan = (
        [
            ("find_stock_symbol_with_company_name", 4),
            ("find_distance_with_location_name", 3),
            ("find_temperature_f_with_location", 4),
            ("convert_currency", 2),
            ("convert_currency_canonicalize", 2),
            ("find_address_with_lat_lon", 2),
            ("find_phone_number_with_location_name", 2),
            ("find_temperature", 3),
            ("search_sender_phone_number_with_content", 3),
            ("search_name_with_relationship", 3),
            ("update_contact_relationship_with_relationship", 2),
        ]
        if selector_lane_revived
        else [
            ("find_stock_symbol_with_company_name", 4),
            ("find_stock_symbol_with_company_name_low_battery_mode", 4),
            ("find_distance_with_location_name", 3),
            ("find_temperature_f_with_location", 3),
            ("convert_currency", 2),
            ("convert_currency_canonicalize", 2),
            ("find_address_with_lat_lon", 2),
            ("find_phone_number_with_location_name", 2),
            ("find_temperature", 1),
            ("find_temperature_f_with_location_and_time_diff", 2),
        ]
    )
    for prefix, count in held_out_plan:
        if count:
            held_out.extend(
                _select_records(
                    (prefix,),
                    size=count,
                    already=already,
                    family_counts=family_counts,
                    max_per_family=8,
                )
            )
    for prefix, count in (
        ("find_distance_with_location_name_insufficient_information", 2),
        ("find_temperature_f_with_location_insufficient_information", 2),
        ("find_current_city_insufficient_information", 2),
        ("find_current_location_insufficient_information", 2),
        ("remove_contact_by_phone_no_remove_contact_insufficient_information", 2),
        ("remove_contact_by_phone_no_search_contacts_insufficient_information", 2),
        ("add_contact_with_name_and_phone_number", 2),
        ("remove_contact_with_id", 1),
    ):
        negative.extend(
            _select_records(
                (prefix,),
                size=count,
                already=already,
                family_counts=family_counts,
                max_per_family=8,
                include_insufficient="insufficient_information" in prefix,
            )
        )
    selected = early + held_out + negative
    if (len(early), len(held_out), len(negative), len(selected)) != (20, 25, 15, 60):
        raise RuntimeError(
            f"Expected 20/25/15/60, got {len(early)}/{len(held_out)}/{len(negative)}/{len(selected)}"
        )
    return _manifest_from_records(
        manifest_type="sage_v2_2_masked_best3_discovery60_loop2",
        selected=selected,
        generation_enabled=True,
        registry_tool_count=0,
        role_counts={
            "early_cluster_positive": len(early),
            "held_out_reuse": len(held_out),
            "negative_or_ambiguity": len(negative),
        },
        strategy=(
            "Masked-best3 loop-2 discovery excluding confirmed days and parked "
            "dependency/side-effect/recency-action lanes. Selector lane included "
            f"only if revived: {selector_lane_revived}."
        ),
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_gap_report(atlas: dict[str, Any], path: Path) -> None:
    rows = []
    for item in atlas["ranked_clusters"][:12]:
        rows.append(
            "| {cluster_id} | {status} | {scenario_count} | {base_family_count} | "
            "{outcome_regressions} | {rank_score} |".format(**item)
        )
    path.write_text(
        f"""# V2.2 Gap Atlas Loop 2

## Objective

Rebuild the masked-best3 V2.2 gap atlas after confirming `days_between_timestamps`, excluding parked lanes and best3-adjacent mechanisms.

## Protected Assets

- Frozen best3 registry: `{atlas["protected_frozen_best3_registry"]}`
- Masked best3 tools: `{", ".join(atlas["masked_best3_tools"])}`
- Confirmed V2.2 tools: `{", ".join(atlas["confirmed_v2_2_tools"])}`
- Parked lanes: `{", ".join(atlas["parked_lanes"])}`

## Sources

{chr(10).join(f"- `{name}`: `{path}`" for name, path in atlas["sources"].items())}

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Regressions | Score |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Recommendation

{atlas["recommendation"]}

## Decision Label

`discovery loop2 ready`
""",
        encoding="utf-8",
    )


def write_selector20_report(manifest: dict[str, Any], path: Path) -> None:
    diversity = manifest["cohort_diversity_report"]
    path.write_text(
        f"""# V2.2 Selector Actor-Policy Diagnostic Setup

## Objective

Create the focused selector-adoption diagnostic cohort after the bounded actor-policy repair.

## Cohort

- Manifest type: `{manifest["manifest_type"]}`
- Scenarios: `{next(iter(manifest["split_sizes"].values()))}`
- Role counts: `{manifest["role_counts"]}`
- Quality gate: `{diversity["quality_gate_status"]}`
- Distinct families: `{diversity["distinct_base_task_families"]}`
- Largest family variants: `{diversity["largest_family_variant_count"]}`
- No-current-helper-fit share: `{diversity["no_current_helper_fit_share"]:.3f}`

## Decision Label

`selector diagnostic ready`
""",
        encoding="utf-8",
    )


def copy_selector_registry(dst: Path) -> None:
    src = _load_json(PREVIOUS_V2_2_REGISTRY)
    tools = cast(dict[str, Any], src.get("tools", {}))
    selector = tools.get("select_visible_record_by_constraints")
    if not isinstance(selector, dict):
        raise RuntimeError(f"Missing selector in {PREVIOUS_V2_2_REGISTRY}")
    dst.mkdir(parents=True, exist_ok=True)
    _write_json(
        dst / "registry_manifest.json",
        {"tools": {"select_visible_record_by_constraints": selector}},
    )
    _write_json(
        dst / "registry_lock.json",
        {
            "label": "v2_2_selector_actor_policy_diagnostic_registry",
            "source_registry": str(PREVIOUS_V2_2_REGISTRY),
            "masked_tools": sorted(BEST3),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/summaries/v2_2_loop2"),
    )
    parser.add_argument(
        "--selector-registry-dir",
        type=Path,
        default=Path("artifacts/registry_candidates/v2_2_selector_actor_policy20"),
    )
    parser.add_argument(
        "--candidate-registry-dir",
        type=Path,
        default=Path("artifacts/registry_candidates/v2_2_masked_best3_discovery_loop2"),
    )
    parser.add_argument(
        "--selector-lane-status",
        choices=("pending", "revived", "parked"),
        default="pending",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    atlas = build_loop2_gap_atlas()
    _write_json(args.output_dir / "latest_gap_atlas.json", atlas)
    write_gap_report(atlas, Path("docs/sage_protocol/v2_2_gap_atlas_loop2_report.md"))

    selector_manifest = build_selector20_manifest()
    _write_json(
        args.output_dir / "selector_actor_policy20_manifest.json", selector_manifest
    )
    _write_json(
        args.output_dir / "selector_actor_policy20_diversity_report.json",
        selector_manifest["cohort_diversity_report"],
    )
    copy_selector_registry(args.selector_registry_dir)
    write_selector20_report(
        selector_manifest,
        Path("docs/sage_protocol/v2_2_selector_actor_policy_diagnostic20_report.md"),
    )

    discovery_manifest = build_discovery60_manifest(
        selector_lane_revived=args.selector_lane_status == "revived"
    )
    _write_json(args.output_dir / "discovery60_loop2_manifest.json", discovery_manifest)
    _write_json(
        args.output_dir / "discovery60_loop2_diversity_report.json",
        discovery_manifest["cohort_diversity_report"],
    )
    args.candidate_registry_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.candidate_registry_dir / "registry_manifest.json", {"tools": {}})
    _write_json(
        args.candidate_registry_dir / "registry_lock.json",
        {
            "label": "v2_2_masked_best3_discovery_loop2_candidate_registry",
            "masked_tools": sorted(BEST3),
            "confirmed_v2_2_tools": sorted(CONFIRMED_V2_2),
            "selector_lane_status": args.selector_lane_status,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    print(args.output_dir / "latest_gap_atlas.json")
    print(args.output_dir / "selector_actor_policy20_manifest.json")
    print(args.selector_registry_dir / "registry_manifest.json")
    print(args.output_dir / "discovery60_loop2_manifest.json")
    print(args.candidate_registry_dir / "registry_manifest.json")


if __name__ == "__main__":
    main()
