#!/usr/bin/env python3
# mypy: ignore-errors
"""Build V2.4 additive-over-best3 gap atlas and discovery manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
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

BEST3_REGISTRY = Path("artifacts/registry_frozen_best3_claim/registry_manifest.json")
BEST3 = {
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_record_by_timestamp_extreme",
}

SOURCES: dict[str, Path] = {
    "formal100_best3": Path(
        "outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/"
        "validate_100_20260504_050428/paired_comparison.json"
    ),
    "formal250_best3": Path(
        "outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/"
        "validate_250_20260504_052222/paired_comparison.json"
    ),
    "formal500_best3": Path(
        "outputs/v2_1_formal500_best3_parallel_20260504_232126/"
        "full_benchmark_20260504_232130/paired_comparison.json"
    ),
    "formal1032_best3": Path(
        "outputs/v2_1_formal1000_best3_full_20260505_004901/"
        "full_benchmark_20260505_004905/paired_comparison.json"
    ),
    "robustness60_best3": Path(
        "outputs/v2_best3_robustness60_clean_20260504_070424/"
        "mechanism_40_20260504_070441/paired_comparison.json"
    ),
    "best4_ablation_best3": Path(
        "outputs/v2_2_best4_ablation60_best3_20260506_075831/"
        "mechanism_60_20260506_075938/paired_comparison.json"
    ),
    "best4_ablation_best4": Path(
        "outputs/v2_2_best4_ablation60_best4_20260506_075831/"
        "mechanism_60_20260506_082133/paired_comparison.json"
    ),
    "best4_frozen100": Path(
        "outputs/v2_2_best4_frozen100_20260506_075831/"
        "validate_100_20260506_084140/paired_comparison.json"
    ),
}

PARKED_CLUSTER_IDS = {
    "best3_covered",
    "days_between_calendar_distance",
    "dependency_precondition",
    "visible_record_selector",
    "selected_record_side_effect_prep",
    "recency_action_selector",
    "stock_symbol_extraction",
    "broad_constraint_action_planner",
}

_SCENARIOS: list[ScenarioRecord] | None = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records() -> list[ScenarioRecord]:
    global _SCENARIOS
    if _SCENARIOS is None:
        _SCENARIOS = list(scenario_records())
    return _SCENARIOS


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cluster_id(scenario: str) -> str:
    name = scenario.lower()
    helper_fit = set(expected_helper_fit(scenario))
    if helper_fit & BEST3:
        return "best3_covered"
    if name.startswith(("find_days_till_holiday", "find_thanksgiving_timestamp")):
        return "days_between_calendar_distance"
    if name.startswith("find_stock_symbol_with_company_name"):
        return "stock_symbol_extraction"
    if any(token in name for token in ("low_battery", "wifi_off", "cellular_off")):
        return "dependency_precondition"
    if name.startswith(
        (
            "remove_contact_by_phone",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
            "search_name_with_relationship",
            "update_contact_relationship_with_relationship",
        )
    ):
        return "visible_record_selector"
    if name.startswith(
        (
            "modify_contact_with_message_recency",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
        )
    ):
        return "recency_action_selector"
    if "insufficient_information" in name:
        return "insufficient_information_or_clarification"
    if name.startswith(
        (
            "find_distance_with_location_name",
            "find_address_with_lat_lon",
            "find_phone_number_with_location_name",
            "find_temperature",
            "find_temperature_f_with_location",
            "convert_currency",
            "convert_currency_canonicalize",
        )
    ):
        return "external_service_answer_extraction"
    if name.startswith(
        (
            "find_temperature",
            "find_temperature_f_with_location",
            "find_min_temperature_weekday",
        )
    ):
        return "weather_answer_extraction"
    if name.startswith(("convert_currency", "convert_currency_canonicalize")):
        return "currency_value_extraction"
    if name.startswith(("find_current_city", "find_current_location")):
        return "current_location_answer_extraction"
    if name.startswith(("add_contact", "send_message", "remove_contact_with_id")):
        return "direct_side_effect_no_helper"
    return "other_no_current_helper_fit"


def build_gap_atlas() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source, path in SOURCES.items():
        if not path.exists():
            continue
        for row in _load_json(path).get("deltas", []):
            scenario = str(row["scenario"])
            outcome_delta = row.get("outcome_delta")
            candidate_outcome = row.get("candidate_outcome_similarity")
            control_outcome = row.get("control_outcome_similarity")
            helper_fit = expected_helper_fit(scenario)
            cluster = _cluster_id(scenario)
            item = {
                "source": source,
                "scenario": scenario,
                "base_family": base_task_family(scenario),
                "cluster_id": cluster,
                "canonical_delta": row.get("delta"),
                "outcome_delta": outcome_delta,
                "candidate_outcome_similarity": candidate_outcome,
                "control_outcome_similarity": control_outcome,
                "candidate_failed": (
                    isinstance(candidate_outcome, (int, float))
                    and float(candidate_outcome) < 0.75
                ),
                "outcome_regression": (
                    isinstance(outcome_delta, (int, float))
                    and float(outcome_delta) < -1e-9
                ),
                "expected_helper_fit": helper_fit,
                "expected_birth_opportunities": expected_birth_opportunities(scenario),
            }
            records.append(item)
            clusters[cluster].append(item)

    helper_potential = {
        "external_service_answer_extraction": 3,
        "location_answer_extraction": 3,
        "weather_answer_extraction": 3,
        "currency_value_extraction": 3,
        "current_location_answer_extraction": 2,
        "insufficient_information_or_clarification": 1,
        "direct_side_effect_no_helper": 0,
        "other_no_current_helper_fit": 1,
    }
    callability = {
        "external_service_answer_extraction": 3,
        "location_answer_extraction": 4,
        "weather_answer_extraction": 3,
        "currency_value_extraction": 4,
        "current_location_answer_extraction": 2,
        "insufficient_information_or_clarification": 2,
        "direct_side_effect_no_helper": 1,
        "other_no_current_helper_fit": 1,
    }
    side_effect_risk = {
        "direct_side_effect_no_helper": 5,
        "insufficient_information_or_clarification": 2,
        "current_location_answer_extraction": 1,
        "external_service_answer_extraction": 0,
        "location_answer_extraction": 0,
        "weather_answer_extraction": 0,
        "currency_value_extraction": 0,
        "other_no_current_helper_fit": 2,
    }

    ranked: list[dict[str, Any]] = []
    for cluster, items in clusters.items():
        families = Counter(str(item["base_family"]) for item in items)
        regressions = [item for item in items if item["outcome_regression"]]
        failures = [item for item in items if item["candidate_failed"]]
        no_fit = [
            item
            for item in items
            if not set(item["expected_helper_fit"]) & BEST3
            and not item["expected_helper_fit"]
        ]
        values = [
            float(item["outcome_delta"])
            for item in items
            if isinstance(item.get("outcome_delta"), (int, float))
        ]
        status = (
            "excluded_or_parked"
            if cluster in PARKED_CLUSTER_IDS
            else "candidate_ranked"
        )
        if cluster in {
            "direct_side_effect_no_helper",
            "insufficient_information_or_clarification",
            "other_no_current_helper_fit",
        }:
            status = "support_or_negative_not_primary"
        potential = helper_potential.get(cluster, 1)
        adoption = callability.get(cluster, 1)
        risk = side_effect_risk.get(cluster, 1)
        score = (
            len(failures) * 3
            + len(regressions) * 4
            + len(no_fit) * 2
            + len(families) * 2
            + potential * 5
            + adoption * 3
            - risk * 5
        )
        if status != "candidate_ranked":
            score -= 100
        ranked.append(
            {
                "cluster_id": cluster,
                "status": status,
                "scenario_count": len(items),
                "base_family_count": len(families),
                "base_families": dict(families.most_common()),
                "best3_failure_frequency": len(failures),
                "best3_regression_frequency": len(regressions),
                "no_current_helper_fit_count": len(no_fit),
                "mean_outcome_delta": sum(values) / len(values) if values else None,
                "deterministic_helper_potential": potential,
                "callability_simplicity": adoption,
                "side_effect_risk": risk,
                "additive_over_best3_potential": score,
                "birth_opportunity_counts": dict(
                    Counter(
                        opportunity
                        for item in items
                        for opportunity in item["expected_birth_opportunities"]
                    ).most_common()
                ),
                "worst_examples": sorted(
                    (
                        {
                            "source": item["source"],
                            "scenario": item["scenario"],
                            "outcome_delta": item["outcome_delta"],
                            "candidate_outcome_similarity": item[
                                "candidate_outcome_similarity"
                            ],
                            "expected_helper_fit": item["expected_helper_fit"],
                        }
                        for item in items
                    ),
                    key=lambda item: float(item["candidate_outcome_similarity"] or 0),
                )[:12],
            }
        )
    ranked.sort(
        key=lambda item: float(item["additive_over_best3_potential"]),
        reverse=True,
    )
    candidate_clusters = [
        item for item in ranked if item["status"] == "candidate_ranked"
    ]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "objective": "rank only non-parked clusters with plausible additive value over frozen best3",
        "sources": {key: str(path) for key, path in SOURCES.items()},
        "protected_best3_registry": str(BEST3_REGISTRY),
        "excluded_or_downranked": sorted(PARKED_CLUSTER_IDS),
        "record_count": len(records),
        "ranked_clusters": ranked,
        "candidate_clusters": candidate_clusters,
        "selected_cluster": candidate_clusters[0]["cluster_id"]
        if candidate_clusters
        else None,
        "decision_label": (
            "additive discovery ready"
            if candidate_clusters
            and candidate_clusters[0]["additive_over_best3_potential"] > 0
            else "no additive tool-suitable cluster found"
        ),
        "shortfall_records": records,
    }


def _select(
    prefixes: tuple[str, ...],
    *,
    size: int,
    already: set[str],
    family_counts: Counter[str],
    include_insufficient: bool = False,
    max_per_family: int = 8,
) -> list[ScenarioRecord]:
    candidates = [
        record
        for record in _records()
        if record.name.startswith(prefixes)
        and record.name not in already
        and (
            include_insufficient or "INSUFFICIENT_INFORMATION" not in record.categories
        )
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
        raise RuntimeError(f"Could only select {len(selected)} of {size}: {prefixes}")
    return selected


def _add(
    dest: list[ScenarioRecord],
    role_counts: dict[str, int],
    role: str,
    prefixes: tuple[str, ...],
    count: int,
    already: set[str],
    family_counts: Counter[str],
    *,
    include_insufficient: bool = False,
) -> None:
    chosen = _select(
        prefixes,
        size=count,
        already=already,
        family_counts=family_counts,
        include_insufficient=include_insufficient,
    )
    dest.extend(chosen)
    role_counts[role] = role_counts.get(role, 0) + len(chosen)


def build_discovery_manifest(selected_cluster: str) -> dict[str, Any]:
    if selected_cluster != "external_service_answer_extraction":
        raise RuntimeError(
            "Only external_service_answer_extraction currently has a non-parked additive "
            "discovery manifest template."
        )
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    early: list[ScenarioRecord] = []
    held_out: list[ScenarioRecord] = []
    negative: list[ScenarioRecord] = []
    role_counts: dict[str, int] = {}

    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("find_distance_with_location_name",),
        4,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("find_address_with_lat_lon",),
        4,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("find_phone_number_with_location_name",),
        3,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("find_temperature",),
        3,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("find_temperature_f_with_location",),
        3,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("convert_currency",),
        2,
        already,
        family_counts,
    )
    _add(
        early,
        role_counts,
        "early_cluster_positive",
        ("convert_currency_canonicalize",),
        1,
        already,
        family_counts,
    )

    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("find_distance_with_location_name",),
        4,
        already,
        family_counts,
    )
    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("find_address_with_lat_lon",),
        4,
        already,
        family_counts,
    )
    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("find_phone_number_with_location_name",),
        5,
        already,
        family_counts,
    )
    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("find_temperature",),
        5,
        already,
        family_counts,
    )
    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("find_temperature_f_with_location",),
        5,
        already,
        family_counts,
    )
    _add(
        held_out,
        role_counts,
        "held_out_reuse",
        ("convert_currency",),
        2,
        already,
        family_counts,
    )

    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("find_distance_with_location_name_insufficient_information",),
        3,
        already,
        family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("find_temperature_f_with_location_insufficient_information",),
        3,
        already,
        family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("find_current_city_insufficient_information",),
        3,
        already,
        family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("find_current_location_insufficient_information",),
        2,
        already,
        family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("get_wifi", "get_cellular"),
        2,
        already,
        family_counts,
    )
    _add(
        negative,
        role_counts,
        "negative_or_no_helper",
        ("add_contact_with_name_and_phone_number",),
        2,
        already,
        family_counts,
    )

    selected = early + held_out + negative
    if (len(early), len(held_out), len(negative), len(selected)) != (20, 25, 15, 60):
        raise RuntimeError(
            f"Expected 20/25/15/60, got {len(early)}/{len(held_out)}/{len(negative)}/{len(selected)}"
        )
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
        "manifest_type": "sage_v2_4_additive_discovery60",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": (
            "Best3-active additive discovery focused on visible external-service "
            "answer extraction. Best3 is active, not masked; new tools must add value "
            "beside the validated portfolio."
        ),
        "selected_cluster": selected_cluster,
        "protected_best3_registry": str(BEST3_REGISTRY),
        "splits": {"mechanism_60": [record.to_json() for record in selected]},
        "split_sizes": {"mechanism_60": len(selected)},
        "role_counts": role_counts,
        "cohort_diversity_report": diversity,
    }


def write_gap_report(atlas: dict[str, Any], path: Path) -> None:
    rows = []
    for item in atlas["ranked_clusters"][:14]:
        rows.append(
            "| {cluster_id} | {status} | {scenario_count} | {base_family_count} | "
            "{best3_failure_frequency} | {best3_regression_frequency} | "
            "{no_current_helper_fit_count} | {additive_over_best3_potential} |".format(
                **item
            )
        )
    selected = atlas.get("selected_cluster") or "none"
    path.write_text(
        f"""# V2.4 Additive Gap Atlas Report

## Objective

Rebuild the gap atlas with a stricter additive-over-best3 rule. Masked-best3 evidence is no longer sufficient for candidate advancement.

## Sources

{chr(10).join(f"- `{name}`: `{source}`" for name, source in atlas["sources"].items())}

## Excluded Or Downranked Lanes

{chr(10).join(f"- `{name}`" for name in atlas["excluded_or_downranked"])}

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Best3 failures | Best3 regressions | No-helper-fit | Additive score |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Selected Cluster

`{selected}`

The top non-parked cluster is selected only because it has answer-only deterministic extraction potential, scalar/dict output inputs, no final side-effect execution, and a plausible additive gap beside best3. It is still speculative and must prove actual additivity in best3-active discovery and confirmation.

## Decision Label

`{atlas["decision_label"]}`
""",
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    summary_dir = Path("artifacts/summaries/v2_4_additive_gap_atlas")
    run_dir = (
        Path("artifacts/summaries") / f"v2_4_additive_discovery60_{args.timestamp}"
    )
    registry_dir = (
        Path("artifacts/registry_candidates")
        / f"v2_4_additive_discovery60_{args.timestamp}"
    )

    atlas = build_gap_atlas()
    write_json(summary_dir / "latest_gap_atlas.json", atlas)
    write_gap_report(
        atlas, Path("docs/sage_protocol/v2_4_additive_gap_atlas_report.md")
    )

    selected = atlas.get("selected_cluster")
    if atlas["decision_label"] == "additive discovery ready" and selected:
        manifest = build_discovery_manifest(str(selected))
        write_json(run_dir / "cohort_manifest.json", manifest)
        write_json(
            run_dir / "cohort_diversity_report.json",
            manifest["cohort_diversity_report"],
        )
        registry_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BEST3_REGISTRY, registry_dir / "registry_manifest.json")
        setup = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "atlas": str(summary_dir / "latest_gap_atlas.json"),
            "manifest": str(run_dir / "cohort_manifest.json"),
            "registry_dir": str(registry_dir),
            "registry_manifest": str(registry_dir / "registry_manifest.json"),
            "registry_sha256": _sha256(registry_dir / "registry_manifest.json"),
            "selected_cluster": selected,
            "cohort_quality": manifest["cohort_diversity_report"][
                "quality_gate_status"
            ],
        }
        write_json(run_dir / "setup_summary.json", setup)
        print(json.dumps(setup, indent=2))
    else:
        print(
            json.dumps(
                {
                    "atlas": str(summary_dir / "latest_gap_atlas.json"),
                    "decision": atlas["decision_label"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
