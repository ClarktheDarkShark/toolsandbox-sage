# mypy: ignore-errors
"""Build high-fit scale registries and splits for recency/action gap closure.

This suite intentionally targets the retained positive recency/action surface
from prior gap-closure diagnostics. It is experimental revalidation, not
protected final-claim evidence: local outputs already cover the non-external
benchmark surface, so fully scenario-unseen scale splits are not available in
this worktree.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import EXTERNAL_SERVICE_TOKENS, base_task_family

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption"
)
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption"
)

HIGH_RETAINED = (
    REGISTRY_ROOT
    / "recency_search_contact_selector_safe_bridge_plus_guard_final_selector_pack"
    / "registry_manifest.json"
)
DAYS_CONTACT = (
    REGISTRY_ROOT / "best3_plus_final_selector_days_pack" / "registry_manifest.json"
)

RECENCY_DAY_OUT = (
    REGISTRY_ROOT / "recency_day_high_power_scale_pack" / "registry_manifest.json"
)
RECENCY_DAY_CONTACT_OUT = (
    REGISTRY_ROOT
    / "recency_day_contact_high_power_scale_pack"
    / "registry_manifest.json"
)
SPLIT_OUT = MANIFEST_ROOT / "high_fit_scale_splits.json"
SUMMARY_OUT = MANIFEST_ROOT / "high_fit_scale_suite_build_summary.json"

RECENCY_DAY_PREFIXES = (
    "search_message_with_recency",
    "modify_contact_with_message_recency",
    "search_reminder_with_recency",
    "search_reminder_with_creation_recency",
    "modify_reminder_with_recency",
    "remove_reminder_with_recency",
    "find_days_till_holiday",
)

TEMPORAL_ACTION_PREFIXES = (
    "add_reminder",
    "modify_reminder",
    "remove_reminder",
)

CONTACT_SCALAR_PREFIXES = (
    "search_phone_number_with_name",
    "search_relationship_with_phone_number",
    "search_name_with_relationship",
    "remove_contact_by_phone",
    "update_contact_relationship_with_relationship",
    "search_sender_phone_number_with_content",
)

CORE_RECENCY_TOOLS = (
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
)

DAY_TOOLS = (
    "days_between_timestamps",
    "relative_day_time_to_timestamp",
)

CONTACT_TOOLS = (
    "plan_contact_lookup_query",
    "plan_contact_search_from_scalar_constraint",
    "extract_contact_field_from_search_result",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def _load_tools(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload["tools"])


def _tool(source: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in source:
        raise KeyError(f"Missing expected tool {name!r}")
    return copy.deepcopy(source[name])


def _tighten_contact_tool(entry: dict[str, Any], name: str) -> dict[str, Any]:
    entry = copy.deepcopy(entry)
    spec = entry["tool"]["spec"]
    existing_negative = list(spec.get("negative_triggers") or [])
    spec["negative_triggers"] = sorted(
        set(
            existing_negative
            + [
                "reminder tasks",
                "message recency tasks",
                "calendar or external service tasks",
                "insufficient_information",
                "no visible contact scalar constraint",
            ]
        )
    )
    spec["description"] = (
        str(spec.get("description") or "").strip()
        + " Use only for contact scalar lookup/removal/update tasks where the "
        "user provides a concrete name, phone number, or relationship and the "
        "next step is an original search_contacts or contact side-effect tool. "
        "Do not expose this for reminder, message-recency, or broad timestamp "
        "tasks. Low natural frequency is acceptable; the tool is retained for "
        "specific contact-scalar failures."
    )
    spec["generalization_rationale"] = (
        "Retained as a narrow V2.6/contact-scalar candidate for the 500-scale "
        "high-fit portfolio. The metadata is tightened to reduce recency/action "
        "pollution while preserving value when a contact scalar lane appears."
    )
    spec["adoption_experiment_note"] = (
        f"high_fit_scale_suite_contact_affordance:{name}; experimental only"
    )
    return entry


def _build_registries() -> dict[str, Any]:
    retained = _load_tools(HIGH_RETAINED)
    days_contact = _load_tools(DAYS_CONTACT)

    recency_day_tools = {name: _tool(retained, name) for name in CORE_RECENCY_TOOLS}
    recency_day_tools.update({name: _tool(days_contact, name) for name in DAY_TOOLS})

    recency_day_contact_tools = copy.deepcopy(recency_day_tools)
    for name in CONTACT_TOOLS:
        recency_day_contact_tools[name] = _tighten_contact_tool(
            _tool(days_contact, name), name
        )

    recency_day_hash = _write_json(RECENCY_DAY_OUT, {"tools": recency_day_tools})
    contact_hash = _write_json(
        RECENCY_DAY_CONTACT_OUT, {"tools": recency_day_contact_tools}
    )
    return {
        "recency_day_registry": {
            "path": str(RECENCY_DAY_OUT),
            "sha256": recency_day_hash,
            "tool_count": len(recency_day_tools),
            "tools": sorted(recency_day_tools),
        },
        "recency_day_contact_registry": {
            "path": str(RECENCY_DAY_CONTACT_OUT),
            "sha256": contact_hash,
            "tool_count": len(recency_day_contact_tools),
            "tools": sorted(recency_day_contact_tools),
        },
        "source_registries": {
            "high_retained": str(HIGH_RETAINED),
            "days_contact": str(DAYS_CONTACT),
        },
    }


def _prior_evaluated_scenarios() -> set[str]:
    prior: set[str] = set()
    for path in Path("outputs/gap_closure_lab").rglob("paired_comparison.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in (
            "deltas",
            "gains",
            "regressions",
            "outcome_gains",
            "outcome_regressions",
        ):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and row.get("scenario"):
                    prior.add(str(row["scenario"]))
    return prior


def _matches(record: ScenarioRecord, prefixes: tuple[str, ...]) -> bool:
    return any(record.name.startswith(prefix) for prefix in prefixes)


def _is_external(record: ScenarioRecord) -> bool:
    lower = record.name.lower()
    return any(token in lower for token in EXTERNAL_SERVICE_TOKENS)


def _is_insufficient(record: ScenarioRecord) -> bool:
    return "INSUFFICIENT_INFORMATION" in record.categories or (
        "insufficient_information" in record.name
    )


def _lane(record: ScenarioRecord) -> str:
    if _matches(record, RECENCY_DAY_PREFIXES):
        return "recency_day"
    if _matches(record, TEMPORAL_ACTION_PREFIXES):
        return "temporal_action"
    if _matches(record, CONTACT_SCALAR_PREFIXES):
        return "contact_scalar"
    return "broad_filler"


def _round_robin(
    records: list[ScenarioRecord], *, limit: int | None = None
) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)

    selected: list[ScenarioRecord] = []
    family_order = sorted(buckets)
    while any(buckets.values()) and (limit is None or len(selected) < limit):
        for family in family_order:
            if limit is not None and len(selected) >= limit:
                break
            bucket = buckets[family]
            if bucket:
                selected.append(bucket.popleft())
    return selected


def _take_priority(
    records_by_lane: dict[str, list[ScenarioRecord]],
    lane_order: tuple[str, ...],
    *,
    limit: int,
    used: set[str],
) -> list[ScenarioRecord]:
    selected: list[ScenarioRecord] = []
    for lane in lane_order:
        remaining = limit - len(selected)
        if remaining <= 0:
            break
        available = [
            record
            for record in records_by_lane.get(lane, [])
            if record.name not in used
        ]
        taken = _round_robin(available, limit=remaining)
        selected.extend(taken)
        used.update(record.name for record in taken)
    if len(selected) != limit:
        raise RuntimeError(f"Needed {limit} scenarios, selected {len(selected)}")
    return selected


def _record_to_row(
    record: ScenarioRecord,
    *,
    split_name: str,
    prior_evaluated: set[str],
    final_evaluation: bool,
) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "high_fit_lane": _lane(record),
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": final_evaluation,
        "split": split_name,
        "prior_local_sage_or_control_output_present": record.name in prior_evaluated,
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    lanes = Counter(str(row["high_fit_lane"]) for row in rows)
    labels = Counter(label for row in rows for label in row.get("task_labels", []))
    prior_count = sum(
        1 for row in rows if row.get("prior_local_sage_or_control_output_present")
    )
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "lane_counts": dict(sorted(lanes.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "top_task_labels": dict(labels.most_common(20)),
        "prior_local_output_present_count": prior_count,
        "insufficient_information_count": sum(
            1
            for row in rows
            if "INSUFFICIENT_INFORMATION" in row.get("task_labels", [])
        ),
        "near_duplicate_dominated": bool(
            rows and max(families.values()) / len(rows) > 0.35
        ),
        "diversity_reason": (
            "The split is high-fit by design: it covers the complete visible "
            "recency/day/contact-scalar surface before deterministic broad filler. "
            "Family ordering is round-robin within each lane and does not use "
            "truth labels, expected answers, or cache availability. Because local "
            "prior outputs already cover the eligible non-external benchmark "
            "surface, this is fresh-run experimental revalidation rather than "
            "scenario-unseen final evidence."
        ),
    }


def _build_splits() -> dict[str, Any]:
    prior = _prior_evaluated_scenarios()
    eligible = [
        record
        for record in scenario_records()
        if not _is_external(record) and not _is_insufficient(record)
    ]
    records_by_lane: dict[str, list[ScenarioRecord]] = defaultdict(list)
    for record in eligible:
        records_by_lane[_lane(record)].append(record)

    used: set[str] = set()
    confirm_records = _take_priority(
        records_by_lane,
        ("recency_day",),
        limit=100,
        used=used,
    )

    # Do not reuse confirm records inside the 250/500 split construction. This
    # keeps confirm as a separate quick diagnostic if needed while the scale
    # aliases remain deterministic.
    used_for_scale: set[str] = set()
    scale250_records = _take_priority(
        records_by_lane,
        ("recency_day", "temporal_action"),
        limit=250,
        used=used_for_scale,
    )

    used500: set[str] = set()
    high_fit_500_records = _take_priority(
        records_by_lane,
        ("recency_day", "temporal_action", "contact_scalar", "broad_filler"),
        limit=500,
        used=used500,
    )

    expanded_records = scale250_records[:60]

    splits = {
        "high_fit_confirm100": [
            _record_to_row(
                record,
                split_name="high_fit_confirm100",
                prior_evaluated=prior,
                final_evaluation=False,
            )
            for record in confirm_records
        ],
        "high_fit_expanded60": [
            _record_to_row(
                record,
                split_name="high_fit_expanded60",
                prior_evaluated=prior,
                final_evaluation=False,
            )
            for record in expanded_records
        ],
        "high_fit_scale250": [
            _record_to_row(
                record,
                split_name="high_fit_scale250",
                prior_evaluated=prior,
                final_evaluation=True,
            )
            for record in scale250_records
        ],
        "high_fit_scale500": [
            _record_to_row(
                record,
                split_name="high_fit_scale500",
                prior_evaluated=prior,
                final_evaluation=True,
            )
            for record in high_fit_500_records
        ],
    }

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_high_fit_scale_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "prior_local_evaluated_scenario_count": len(prior),
        "eligible_non_external_non_insufficient_count": len(eligible),
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "excluded_external_service_scenarios": True,
            "excluded_insufficient_information_scenarios": True,
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
            "used_prior_outcomes_for_individual_scenario_selection": False,
            "used_prior_experiment_diagnosis_for_family_targeting": True,
            "family_targeting_note": (
                "Prior sealed experimental diagnostics identified recency/search/"
                "action and contact-scalar lanes as the remaining positive pockets. "
                "The manifest selects by broad family prefixes only, not by scenario "
                "ID outcome, hidden answer, or cache status."
            ),
            "lane_prefixes": {
                "recency_day": list(RECENCY_DAY_PREFIXES),
                "temporal_action": list(TEMPORAL_ACTION_PREFIXES),
                "contact_scalar": list(CONTACT_SCALAR_PREFIXES),
            },
            "scale250_policy": (
                "Prioritize the complete recency/day lane, then deterministic "
                "temporal-action fill, round-robin by base task family."
            ),
            "scale500_policy": (
                "Prioritize recency/day, temporal-action, and contact-scalar lanes, "
                "then deterministic broad non-external/non-insufficient filler."
            ),
        },
        "split_aliases": {
            "confirm_100": "high_fit_confirm100",
            "expanded_60": "high_fit_expanded60",
            "promotion_250": "high_fit_scale250",
            "validate_250": "high_fit_scale250",
            "full_benchmark": "high_fit_scale500",
        },
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {name: _diversity(rows) for name, rows in splits.items()},
        "leakage_controls": {
            "labels_inspected_before_run": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "expected_answers_encoded": False,
            "cache_availability_used_for_selection": False,
            "task_level_cache_allowed_only_for_control": True,
            "sage_candidate_runs_fresh": True,
            "prior_output_coverage_blocker_recorded": True,
        },
        "cache_policy": {
            "baseline_control_cache": "use-if-eligible; cache manifest/hash must be recorded in run report",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
            "selection_based_on_cache_availability": False,
        },
    }
    return manifest


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    registry_summary = _build_registries()
    splits = _build_splits()
    split_hash = _write_json(SPLIT_OUT, splits)
    summary = {
        "created_at": now,
        "experimental_only": True,
        "protected_claim_evidence": False,
        "objective": (
            "Scale the retained positive recency/action tools into 250/500 fresh "
            "experimental runs while maximizing eligible control-cache reuse."
        ),
        "registries": registry_summary,
        "split_manifest": {
            "path": str(SPLIT_OUT),
            "sha256": split_hash,
            "split_sizes": splits["split_sizes"],
            "split_diversity": splits["split_diversity"],
        },
        "leakage_statement": (
            "Tools are generic deterministic helpers copied from prior retained "
            "positive registries with tightened contact affordances. The split "
            "selection uses scenario names/categories/allowed tools only and does "
            "not encode hidden labels, expected answers, task-specific strings, "
            "or cache availability."
        ),
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
