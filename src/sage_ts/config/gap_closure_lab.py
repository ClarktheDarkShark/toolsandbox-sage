"""Split manifest construction for SAGE gap-closure lab experiments."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    classify_task_strata,
    expected_birth_opportunities,
    expected_helper_fit,
)

DEFAULT_GAP_CLOSURE_SEED = 20260507

SPLIT_SPECS: dict[str, dict[str, Any]] = {
    "seed_dev_labeled": {
        "size": 8,
        "max_per_family": 1,
        "truth_labels_inspected": True,
        "allowed_uses": [
            "pain_point_analysis",
            "tool_design",
            "generation_prompt_repair",
            "validation_examples",
        ],
        "disallowed_uses": ["final_evaluation", "promotion_evidence"],
        "final_evaluation": False,
    },
    "pilot_unseen": {
        "size": 20,
        "max_per_family": 2,
        "truth_labels_inspected": False,
        "allowed_uses": [
            "micro20_natural_run",
            "diagnostic_force_exposure",
            "diagnostic_force_call_when_safe",
            "fair_chance_root_cause_analysis",
        ],
        "disallowed_uses": ["generation_with_truth_labels", "final_evaluation"],
        "final_evaluation": False,
    },
    "expanded_pilot_unseen": {
        "size": 60,
        "max_per_family": 3,
        "truth_labels_inspected": False,
        "allowed_uses": [
            "expanded_pilot",
            "natural_adoption_rerun_after_repair",
            "portfolio_interaction_test",
            "family_merit_assessment",
        ],
        "disallowed_uses": ["generation_with_truth_labels", "final_evaluation"],
        "final_evaluation": False,
    },
    "confirm_unseen": {
        "size": 100,
        "max_per_family": 4,
        "truth_labels_inspected": False,
        "allowed_uses": [
            "matched_confirmation",
            "ablation",
            "routing_adoption_measurement",
            "called_subset_outcome_measurement",
        ],
        "disallowed_uses": ["generation_with_truth_labels"],
        "final_evaluation": False,
    },
    "scale_unseen": {
        "size": 250,
        "max_per_family": 6,
        "truth_labels_inspected": False,
        "allowed_uses": [
            "scale_validation_after_confirm_positive",
            "matched_baseline_comparison",
            "candidate_portfolio_evaluation",
        ],
        "disallowed_uses": [
            "generation_with_truth_labels",
            "code_or_registry_change_between_matched_arms",
        ],
        "final_evaluation": True,
    },
}

RUNNER_SPLIT_ALIASES = {
    "pilot_20": "pilot_unseen",
    "expanded_60": "expanded_pilot_unseen",
    "confirm_100": "confirm_unseen",
    "validate_250": "scale_unseen",
    "promotion_250": "scale_unseen",
}

PRIMARY_STRATA_ORDER = (
    "insufficient_information_clarification",
    "contact_message_search_disambiguation",
    "record_filtering_ranking_latest_selection",
    "temporal_reminder_date_canonicalization",
    "direct_state_precondition_service_enablement",
    "holiday_calendar_business_day_logic",
    "stock_market_numeric_normalization",
    "weather_location_current_city_distance",
    "other_uncovered_clusters",
    "generic_multi_tool_composition",
)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _stable_key(seed: int, *parts: str) -> str:
    return hashlib.sha256("::".join((str(seed), *parts)).encode("utf-8")).hexdigest()


def _primary_task_label(strata: Iterable[str]) -> str:
    stratum_set = set(strata)
    for label in PRIMARY_STRATA_ORDER:
        if label in stratum_set:
            return label
    return "other_uncovered_clusters"


def _candidate_groups(
    records: Iterable[ScenarioRecord], *, seed: int, blocked_families: set[str]
) -> dict[str, dict[str, list[ScenarioRecord]]]:
    groups: dict[str, dict[str, list[ScenarioRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        family = base_task_family(record.name)
        if family in blocked_families:
            continue
        strata = classify_task_strata(record.name, record.categories)
        primary = _primary_task_label(strata)
        groups[primary][family].append(record)
    for primary_groups in groups.values():
        for family, family_records in primary_groups.items():
            family_records.sort(
                key=lambda record: _stable_key(seed, family, record.name)
            )
    return groups


def _select_diverse(
    records: list[ScenarioRecord],
    *,
    size: int,
    seed: int,
    used_scenarios: set[str],
    blocked_families: set[str],
    max_per_family: int,
) -> list[ScenarioRecord]:
    groups = _candidate_groups(records, seed=seed, blocked_families=blocked_families)
    strata = sorted(groups, key=lambda label: _stable_key(seed, "stratum", label))
    family_order: dict[str, list[str]] = {}
    for label in strata:
        families = sorted(
            groups[label],
            key=lambda family: _stable_key(seed, label, "family", family),
        )
        family_order[label] = families

    selected: list[ScenarioRecord] = []
    family_counts: Counter[str] = Counter()
    family_offsets: dict[tuple[str, str], int] = defaultdict(int)
    progress = True
    while len(selected) < size and progress:
        progress = False
        for label in strata:
            for family in family_order[label]:
                if len(selected) >= size:
                    break
                if family_counts[family] >= max_per_family:
                    continue
                family_records = groups[label][family]
                offset_key = (label, family)
                offset = family_offsets[offset_key]
                while offset < len(family_records):
                    record = family_records[offset]
                    offset += 1
                    if record.name in used_scenarios:
                        continue
                    selected.append(record)
                    family_counts[family] += 1
                    family_offsets[offset_key] = offset
                    progress = True
                    break
                family_offsets[offset_key] = offset
            if len(selected) >= size:
                break
    if len(selected) < size:
        raise ValueError(f"Only selected {len(selected)} scenarios; requested {size}")
    return selected


def _scenario_row(
    record: ScenarioRecord, *, split_name: str, spec: dict[str, Any]
) -> dict[str, Any]:
    strata = classify_task_strata(record.name, record.categories)
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "primary_task_label": _primary_task_label(strata),
        "task_labels": strata,
        "categories": sorted(record.categories),
        "truth_labels_inspected": bool(spec["truth_labels_inspected"]),
        "used_for_generation": "tool_design" in spec["allowed_uses"],
        "used_for_repair": "generation_prompt_repair" in spec["allowed_uses"],
        "used_for_routing": "routing_adoption_measurement" in spec["allowed_uses"],
        "used_for_validation": any(
            use in spec["allowed_uses"]
            for use in (
                "validation_examples",
                "matched_confirmation",
                "scale_validation_after_confirm_positive",
            )
        ),
        "used_for_final_evaluation": bool(spec["final_evaluation"]),
        "expected_helper_fit": expected_helper_fit(record.name, record.categories),
        "expected_birth_opportunities": expected_birth_opportunities(
            record.name, record.categories
        ),
    }


def _diversity_summary(
    rows: list[dict[str, Any]], *, max_per_family: int
) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    primary_labels = Counter(str(row["primary_task_label"]) for row in rows)
    task_labels: Counter[str] = Counter()
    for row in rows:
        task_labels.update(str(label) for label in row["task_labels"])
    largest_family_count = max(families.values(), default=0)
    scenario_count = len(rows)
    largest_family_share = (
        largest_family_count / scenario_count if scenario_count else 0.0
    )
    return {
        "scenario_count": scenario_count,
        "distinct_family_count": len(families),
        "max_per_family": max_per_family,
        "largest_family_count": largest_family_count,
        "largest_family_share": largest_family_share,
        "family_counts": dict(families.most_common()),
        "primary_task_label_counts": dict(primary_labels.most_common()),
        "task_label_counts": dict(task_labels.most_common()),
        "near_duplicate_dominated": largest_family_count > max_per_family,
        "diversity_reason": (
            "Selected by seeded round-robin over primary task labels and base task "
            f"families, with at most {max_per_family} scenarios from any base "
            "family in this split."
        ),
    }


def _hashable_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    clone = dict(payload)
    clone.pop("manifest_integrity", None)
    return clone


def make_gap_closure_lab_manifest(
    *,
    seed: int = DEFAULT_GAP_CLOSURE_SEED,
    generated_at: str = "2026-05-07",
) -> dict[str, Any]:
    records = scenario_records()
    rng = random.Random(seed)
    shuffled_records = records[:]
    rng.shuffle(shuffled_records)

    used_scenarios: set[str] = set()
    seed_dev_families: set[str] = set()
    splits: dict[str, list[dict[str, Any]]] = {}
    split_summaries: dict[str, dict[str, Any]] = {}

    for split_name, spec in SPLIT_SPECS.items():
        blocked_families = (
            seed_dev_families if not spec["truth_labels_inspected"] else set()
        )
        selected = _select_diverse(
            shuffled_records,
            size=int(spec["size"]),
            seed=seed + len(splits),
            used_scenarios=used_scenarios,
            blocked_families=blocked_families,
            max_per_family=int(spec["max_per_family"]),
        )
        used_scenarios.update(record.name for record in selected)
        if split_name == "seed_dev_labeled":
            seed_dev_families = {base_task_family(record.name) for record in selected}
        rows = [
            _scenario_row(record, split_name=split_name, spec=spec)
            for record in selected
        ]
        splits[split_name] = rows
        split_summaries[split_name] = _diversity_summary(
            rows, max_per_family=int(spec["max_per_family"])
        )

    manifest: dict[str, Any] = {
        "manifest_type": "sage_gap_closure_lab_splits",
        "schema_version": 1,
        "created_at": generated_at,
        "seed": seed,
        "status": "experimental_not_claim_evidence",
        "protected_asset_policy": {
            "do_not_modify": [
                "artifacts/registry_frozen_best3_claim/registry_manifest.json",
                "locked best3 evidence",
                "locked formal evidence",
                "final-package claim artifacts",
            ],
            "experimental_registry_root": (
                "artifacts/registry_experiments/gap_closure_lab/"
            ),
        },
        "cache_policy": {
            "baseline_control": (
                "eligible for control baseline cache when the exact manifest, model, "
                "base tools, and cache hash are recorded"
            ),
            "sage_candidate_arms": (
                "fresh experimental runs only; no prior SAGE traces as outcome evidence"
            ),
            "cross_arm_response_reuse": (
                "disabled unless the cache key is provably arm/tool/registry specific "
                "and recorded in the run report"
            ),
        },
        "split_protocol": {
            name: {
                key: value
                for key, value in spec.items()
                if key
                in (
                    "size",
                    "max_per_family",
                    "truth_labels_inspected",
                    "allowed_uses",
                    "disallowed_uses",
                    "final_evaluation",
                )
            }
            for name, spec in SPLIT_SPECS.items()
        },
        "split_aliases": RUNNER_SPLIT_ALIASES,
        "leakage_controls": [
            "Seed/dev base families are excluded from all unseen splits.",
            "No scenario is assigned to more than one split.",
            "Unseen split truth labels are marked not inspected.",
            "Cache availability is not used as a scenario-selection feature.",
            "Scenario IDs may not be hard-coded into generated tools or routers.",
        ],
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": split_summaries,
    }
    manifest["manifest_integrity"] = {
        "hash_algorithm": "sha256",
        "hash_scope": "canonical JSON payload excluding manifest_integrity",
        "payload_sha256": payload_sha256(_hashable_manifest(manifest)),
    }
    return manifest


def write_gap_closure_lab_manifest(
    output: Path,
    *,
    seed: int = DEFAULT_GAP_CLOSURE_SEED,
    generated_at: str = "2026-05-07",
) -> tuple[Path, str]:
    manifest = make_gap_closure_lab_manifest(seed=seed, generated_at=generated_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    file_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{file_hash}  {output.name}\n", encoding="utf-8"
    )
    return output, file_hash
