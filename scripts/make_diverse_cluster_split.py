#!/usr/bin/env python3
# mypy: ignore-errors
"""Create diverse cluster cohorts with family caps and diversity reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    classify_task_strata,
    expected_birth_opportunities,
    expected_helper_fit,
)

EXTERNAL_TOKENS = (
    "weather",
    "temperature",
    "current_city",
    "distance",
    "lat_lon",
    "current_location",
    "location_name",
    "location_around",
    "address",
    "stock",
    "market",
    "price",
)

CLUSTER_STRATA = {
    "contact_message": "contact_message_search_disambiguation",
    "generic_multi_tool": "generic_multi_tool_composition",
    "record_ranking": "record_filtering_ranking_latest_selection",
    "holiday_calendar": "holiday_calendar_business_day_logic",
    "state_precondition": "direct_state_precondition_service_enablement",
    "stock_numeric": "stock_market_numeric_normalization",
}


def _is_contaminated(record: ScenarioRecord) -> bool:
    name = record.name.lower()
    return any(token in name for token in EXTERNAL_TOKENS)


def _matches_cluster(record: ScenarioRecord, cluster: str) -> bool:
    stratum = CLUSTER_STRATA[cluster]
    return stratum in classify_task_strata(record.name, record.categories)


def _variant_priority(name: str) -> tuple[int, str]:
    lowered = name.lower()
    if "insufficient_information" in lowered:
        return (50, name)
    if "arg_type_scrambled" in lowered or "arg_description_scrambled" in lowered:
        return (20, name)
    if "tool_name_scrambled" in lowered or "tool_description_scrambled" in lowered:
        return (25, name)
    if "all_tools" in lowered:
        return (30, name)
    if "10_distraction_tools" in lowered:
        return (10, name)
    if "3_distraction_tools" in lowered:
        return (5, name)
    return (0, name)


def _select_diverse(
    records: Iterable[ScenarioRecord],
    *,
    size: int,
    max_per_family: int,
    family_counts: Counter[str] | None = None,
    already_selected: set[str] | None = None,
) -> list[ScenarioRecord]:
    by_family: dict[str, list[ScenarioRecord]] = defaultdict(list)
    family_counts = family_counts or Counter()
    already_selected = already_selected or set()
    for record in records:
        if record.name in already_selected:
            continue
        by_family[base_task_family(record.name)].append(record)
    for family_records in by_family.values():
        family_records.sort(key=lambda item: _variant_priority(item.name))

    selected: list[ScenarioRecord] = []
    round_index = 0
    families = sorted(by_family, key=lambda family: (-len(by_family[family]), family))
    while len(selected) < size:
        changed = False
        for family in families:
            if len(selected) >= size:
                break
            if family_counts[family] >= max_per_family:
                continue
            family_records = by_family[family]
            if round_index >= len(family_records):
                continue
            selected.append(family_records[round_index])
            family_counts[family] += 1
            changed = True
        if not changed:
            break
        round_index += 1
    return selected


def _select_with_minimum_positive_cases(
    records: Iterable[ScenarioRecord],
    *,
    size: int,
    max_per_family: int,
    min_helper_fit: int,
    min_birth_opportunity: int,
    required_helper_fit: str,
) -> list[ScenarioRecord]:
    """Select a diverse cohort while forcing enough positive tool-evolution cases."""

    all_records = list(records)
    selected: list[ScenarioRecord] = []
    selected_names: set[str] = set()
    family_counts: Counter[str] = Counter()

    def add(records_to_add: list[ScenarioRecord]) -> None:
        for record in records_to_add:
            if record.name in selected_names:
                continue
            selected.append(record)
            selected_names.add(record.name)
            family_counts[base_task_family(record.name)] += 1

    def has_helper_fit(record: ScenarioRecord) -> bool:
        helper_fit = expected_helper_fit(record.name, record.categories)
        return (
            required_helper_fit in helper_fit
            if required_helper_fit
            else bool(helper_fit)
        )

    if min_helper_fit:
        fit_records = [record for record in all_records if has_helper_fit(record)]
        add(
            _select_diverse(
                fit_records,
                size=min_helper_fit,
                max_per_family=max_per_family,
                family_counts=family_counts,
                already_selected=selected_names,
            )
        )
        fit_count = sum(1 for record in selected if has_helper_fit(record))
        if fit_count < min_helper_fit:
            helper_label = required_helper_fit or "any helper"
            raise ValueError(
                f"Only selected {fit_count} {helper_label} fit scenarios; "
                f"requested at least {min_helper_fit}"
            )

    if min_birth_opportunity:
        birth_records = [
            record
            for record in all_records
            if expected_birth_opportunities(record.name, record.categories)
        ]
        current_birth_count = sum(
            1
            for record in selected
            if expected_birth_opportunities(record.name, record.categories)
        )
        add(
            _select_diverse(
                birth_records,
                size=max(0, min_birth_opportunity - current_birth_count),
                max_per_family=max_per_family,
                family_counts=family_counts,
                already_selected=selected_names,
            )
        )
        birth_count = sum(
            1
            for record in selected
            if expected_birth_opportunities(record.name, record.categories)
        )
        if birth_count < min_birth_opportunity:
            raise ValueError(
                f"Only selected {birth_count} birth-opportunity scenarios; "
                f"requested at least {min_birth_opportunity}"
            )

    add(
        _select_diverse(
            all_records,
            size=size - len(selected),
            max_per_family=max_per_family,
            family_counts=family_counts,
            already_selected=selected_names,
        )
    )
    return selected


def _label_for_size(size: int) -> str:
    if size <= 6:
        return "smoke"
    if size <= 20:
        return "focused discovery"
    if size <= 50:
        return "stratum confirmation"
    return "broad validation"


def _diversity_report(
    *,
    cluster: str,
    split_name: str,
    selected: list[ScenarioRecord],
    max_per_family: int,
    include_contaminated: bool,
) -> dict[str, object]:
    family_counts = Counter(base_task_family(record.name) for record in selected)
    strata_counts: Counter[str] = Counter()
    helper_fit_counts: Counter[str] = Counter()
    birth_opportunity_counts: Counter[str] = Counter()
    contaminated = []
    insufficient = []
    for record in selected:
        strata_counts.update(classify_task_strata(record.name, record.categories))
        helper_fit_counts.update(
            expected_helper_fit(record.name, record.categories)
            or ["no_current_helper_fit"]
        )
        birth_opportunity_counts.update(
            expected_birth_opportunities(record.name, record.categories)
            or ["no_current_birth_opportunity"]
        )
        if _is_contaminated(record):
            contaminated.append(record.name)
        if "INSUFFICIENT_INFORMATION" in set(record.categories):
            insufficient.append(record.name)
    largest_family = max(family_counts.values(), default=0)
    size = len(selected)
    max_share = (largest_family / size) if size else 0.0
    if size >= 60:
        required_families = 8
    elif size >= 30:
        required_families = 5
    else:
        required_families = min(size, 4)
    return {
        "cluster": cluster,
        "split_name": split_name,
        "label": _label_for_size(size),
        "scenario_count": size,
        "distinct_base_task_families": len(family_counts),
        "required_distinct_base_task_families": required_families,
        "max_per_family": max_per_family,
        "largest_family_share": max_share,
        "family_counts": dict(family_counts.most_common()),
        "strata_counts": dict(strata_counts.most_common()),
        "expected_helper_fit_counts": dict(helper_fit_counts.most_common()),
        "expected_birth_opportunity_counts": dict(
            birth_opportunity_counts.most_common()
        ),
        "contaminated_external_service_scenarios": contaminated,
        "insufficient_information_scenarios": insufficient,
        "include_contaminated": include_contaminated,
        "decision_use": (
            "suitable_for_broad_value_decision"
            if size >= 30
            and len(family_counts) >= required_families
            and max_share <= 0.2
            else "suitable_for_early_value_only"
        ),
        "warnings": [
            warning
            for warning in (
                "external_service_cases_present" if contaminated else "",
                "too_few_base_families"
                if len(family_counts) < required_families
                else "",
                "family_share_above_20_percent"
                if size >= 30 and max_share > 0.2
                else "",
            )
            if warning
        ],
    }


def build_manifest(
    *,
    cluster: str,
    size: int,
    max_per_family: int,
    split_name: str,
    include_contaminated: bool,
    require_helper_fit: bool,
    require_birth_opportunity: bool,
    min_helper_fit: int,
    min_birth_opportunity: int,
    required_helper_fit: str,
) -> tuple[dict[str, object], dict[str, object]]:
    records = [
        record
        for record in scenario_records()
        if _matches_cluster(record, cluster)
        and (include_contaminated or not _is_contaminated(record))
    ]
    if require_helper_fit:
        records = [
            record
            for record in records
            if (
                required_helper_fit
                in expected_helper_fit(record.name, record.categories)
                if required_helper_fit
                else expected_helper_fit(record.name, record.categories)
            )
        ]
    if require_birth_opportunity:
        records = [
            record
            for record in records
            if expected_birth_opportunities(record.name, record.categories)
        ]
    selected = _select_with_minimum_positive_cases(
        records,
        size=size,
        max_per_family=max_per_family,
        min_helper_fit=min_helper_fit,
        min_birth_opportunity=min_birth_opportunity,
        required_helper_fit=required_helper_fit,
    )
    if len(selected) < size:
        raise ValueError(
            f"Only selected {len(selected)} scenarios for {cluster}; requested {size}"
        )
    report = _diversity_report(
        cluster=cluster,
        split_name=split_name,
        selected=selected,
        max_per_family=max_per_family,
        include_contaminated=include_contaminated,
    )
    manifest = {
        "manifest_type": "sage_diverse_cluster_discovery",
        "cluster": cluster,
        "strategy": (
            "Diverse early-value cohort with capped ToolSandbox robustness variants. "
            "Use this for discovery, not broad final claims."
        ),
        "splits": {split_name: [record.to_json() for record in selected]},
        "split_sizes": {split_name: len(selected)},
        "cohort_diversity_report": report,
    }
    return manifest, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", choices=sorted(CLUSTER_STRATA), required=True)
    parser.add_argument("--size", type=int, default=18)
    parser.add_argument("--max-per-family", type=int, default=2)
    parser.add_argument("--split-name", default="transfer_40")
    parser.add_argument("--include-contaminated", action="store_true")
    parser.add_argument(
        "--require-helper-fit",
        action="store_true",
        help="Select only scenarios with an expected retained-helper fit.",
    )
    parser.add_argument(
        "--require-birth-opportunity",
        action="store_true",
        help="Select only scenarios with an expected adequacy-gate birth path.",
    )
    parser.add_argument(
        "--min-helper-fit",
        type=int,
        default=0,
        help="Require at least this many selected scenarios to fit retained helpers.",
    )
    parser.add_argument(
        "--required-helper-fit",
        default="",
        help=(
            "When set, --require-helper-fit and --min-helper-fit only count "
            "scenarios expected to fit this specific retained helper."
        ),
    )
    parser.add_argument(
        "--min-birth-opportunity",
        type=int,
        default=0,
        help="Require at least this many selected scenarios to have birth opportunities.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    manifest, report = build_manifest(
        cluster=args.cluster,
        size=args.size,
        max_per_family=args.max_per_family,
        split_name=args.split_name,
        include_contaminated=args.include_contaminated,
        require_helper_fit=args.require_helper_fit,
        require_birth_opportunity=args.require_birth_opportunity,
        min_helper_fit=args.min_helper_fit,
        min_birth_opportunity=args.min_birth_opportunity,
        required_helper_fit=args.required_helper_fit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    args.report_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(args.output),
                "cohort_diversity_report": str(args.report_output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
