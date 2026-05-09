"""Build targeted recency/action splits for gap-closure adoption testing.

The selection policy uses only scenario names, categories, and allowed tool
lists. It excludes scenarios already evaluated in local experimental outputs so
the targeted expanded/confirmation cohorts are fresh with respect to observed
run outcomes.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records

OUT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_action_targeted_splits.json"
)

FAMILY_PREFIXES = (
    "modify_contact_with_message_recency",
    "modify_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest",
    "search_message_with_recency",
    "search_reminder_with_creation_recency_yesterday",
    "search_reminder_with_recency_yesterday",
    "search_reminder_with_recency_upcoming",
)

TARGETED_EXPANDED_SUFFICIENT_COUNTS = {
    "search_message_with_recency": 8,
    "modify_contact_with_message_recency": 7,
    "modify_reminder_with_recency_latest": 7,
    "remove_reminder_with_recency_latest": 7,
    "search_reminder_with_creation_recency_yesterday": 7,
    "search_reminder_with_recency_yesterday": 6,
    "search_reminder_with_recency_upcoming": 6,
}

TARGETED_EXPANDED_INSUFFICIENT_COUNTS = {
    "modify_contact_with_message_recency": 2,
    "modify_reminder_with_recency_latest": 2,
    "remove_reminder_with_recency_latest": 2,
    "search_reminder_with_creation_recency_yesterday": 2,
    "search_reminder_with_recency_yesterday": 2,
    "search_reminder_with_recency_upcoming": 2,
}

TARGETED_CONFIRM_SUFFICIENT_COUNTS = {
    "search_message_with_recency": 20,
    "modify_contact_with_message_recency": 10,
    "modify_reminder_with_recency_latest": 3,
    "remove_reminder_with_recency_latest": 4,
    "search_reminder_with_creation_recency_yesterday": 3,
    "search_reminder_with_recency_yesterday": 4,
    "search_reminder_with_recency_upcoming": 6,
}

TARGETED_CONFIRM_INSUFFICIENT_COUNTS = {
    "modify_contact_with_message_recency": 12,
    "modify_reminder_with_recency_latest": 4,
    "remove_reminder_with_recency_latest": 4,
    "search_reminder_with_creation_recency_yesterday": 10,
    "search_reminder_with_recency_yesterday": 10,
    "search_reminder_with_recency_upcoming": 10,
}


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


def _family(name: str) -> str | None:
    for prefix in FAMILY_PREFIXES:
        if name.startswith(prefix):
            return prefix
    return None


def _prior_evaluated_scenarios() -> set[str]:
    """Return scenario ids already present in local paired-comparison outputs."""

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


def _bucket_records(
    records: list[ScenarioRecord],
    *,
    prior_evaluated: set[str],
) -> dict[tuple[str, bool], deque[ScenarioRecord]]:
    buckets: dict[tuple[str, bool], list[ScenarioRecord]] = defaultdict(list)
    for record in records:
        family = _family(record.name)
        if family is None or record.name in prior_evaluated:
            continue
        insufficient = "insufficient_information" in record.name
        buckets[(family, insufficient)].append(record)

    ordered: dict[tuple[str, bool], deque[ScenarioRecord]] = {}
    for key, rows in buckets.items():
        # Prefer simpler variants before all-tools variants while staying
        # deterministic and independent of labels or outcomes.
        rows.sort(
            key=lambda record: (
                "all_tools" in record.name,
                "10_distraction_tools" in record.name,
                "3_distraction_tools" in record.name,
                record.name,
            )
        )
        ordered[key] = deque(rows)
    return ordered


def _take_counts(
    buckets: dict[tuple[str, bool], deque[ScenarioRecord]],
    counts: dict[str, int],
    *,
    insufficient: bool,
    used: set[str],
) -> list[ScenarioRecord]:
    selected: list[ScenarioRecord] = []
    for family, count in counts.items():
        bucket = buckets[(family, insufficient)]
        taken = 0
        while bucket and taken < count:
            record = bucket.popleft()
            if record.name in used:
                continue
            selected.append(record)
            used.add(record.name)
            taken += 1
        if taken != count:
            raise RuntimeError(
                f"Not enough {'insufficient' if insufficient else 'sufficient'} "
                f"records for {family}: needed {count}, took {taken}"
            )
    return selected


def _interleave(records: list[ScenarioRecord]) -> list[ScenarioRecord]:
    by_family: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in records:
        family = _family(record.name)
        if family is None:
            raise RuntimeError(f"Unexpected non-target record: {record.name}")
        by_family[family].append(record)

    ordered: list[ScenarioRecord] = []
    family_order = list(FAMILY_PREFIXES)
    while any(by_family.values()):
        for family in family_order:
            bucket = by_family[family]
            if bucket:
                ordered.append(bucket.popleft())
    return ordered


def _record_to_manifest_row(
    record: ScenarioRecord,
    *,
    split_name: str,
) -> dict[str, Any]:
    family = _family(record.name)
    if family is None:
        raise RuntimeError(f"Unexpected non-target record: {record.name}")
    return {
        "scenario_id": record.name,
        "family_label": family,
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": False,
        "split": split_name,
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    insufficient_count = sum(
        1 for row in rows if "insufficient_information" in str(row["scenario_id"])
    )
    action_count = sum(
        1 for row in rows if str(row["family_label"]).startswith(("modify_", "remove_"))
    )
    search_count = len(rows) - action_count
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "insufficient_information_count": insufficient_count,
        "sufficient_information_count": len(rows) - insufficient_count,
        "action_task_count": action_count,
        "search_task_count": search_count,
        "near_duplicate_dominated": False,
        "diversity_reason": (
            "Targeted recency/action cohort selected by deterministic family quotas "
            "from uninspected scenario names and allowed tools, with action/search "
            "and insufficient-information minefield coverage. Selection excludes "
            "locally observed experimental outputs and never uses truth labels, "
            "expected answers, or cache availability."
        ),
    }


def main() -> None:
    records = scenario_records()
    prior = _prior_evaluated_scenarios()
    buckets = _bucket_records(records, prior_evaluated=prior)
    used: set[str] = set()

    expanded_records = []
    expanded_records.extend(
        _take_counts(
            buckets,
            TARGETED_EXPANDED_SUFFICIENT_COUNTS,
            insufficient=False,
            used=used,
        )
    )
    expanded_records.extend(
        _take_counts(
            buckets,
            TARGETED_EXPANDED_INSUFFICIENT_COUNTS,
            insufficient=True,
            used=used,
        )
    )

    confirm_records = []
    confirm_records.extend(
        _take_counts(
            buckets,
            TARGETED_CONFIRM_SUFFICIENT_COUNTS,
            insufficient=False,
            used=used,
        )
    )
    confirm_records.extend(
        _take_counts(
            buckets,
            TARGETED_CONFIRM_INSUFFICIENT_COUNTS,
            insufficient=True,
            used=used,
        )
    )

    expanded_rows = [
        _record_to_manifest_row(record, split_name="targeted_expanded60")
        for record in _interleave(expanded_records)
    ]
    confirm_rows = [
        _record_to_manifest_row(record, split_name="targeted_confirm100")
        for record in _interleave(confirm_records)
    ]
    pilot_rows = expanded_rows[:20]

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_targeted_recency_action_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "truth_labels_inspected": False,
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "included_surface_families": list(FAMILY_PREFIXES),
            "excluded_if_seen_in_local_paired_outputs": True,
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
            "expanded_sufficient_counts": TARGETED_EXPANDED_SUFFICIENT_COUNTS,
            "expanded_insufficient_counts": TARGETED_EXPANDED_INSUFFICIENT_COUNTS,
            "confirm_sufficient_counts": TARGETED_CONFIRM_SUFFICIENT_COUNTS,
            "confirm_insufficient_counts": TARGETED_CONFIRM_INSUFFICIENT_COUNTS,
        },
        "split_aliases": {
            "pilot_20": "targeted_pilot20",
            "expanded_60": "targeted_expanded60",
            "confirm_100": "targeted_confirm100",
        },
        "splits": {
            "targeted_pilot20": pilot_rows,
            "targeted_expanded60": expanded_rows,
            "targeted_confirm100": confirm_rows,
        },
        "split_sizes": {
            "targeted_pilot20": len(pilot_rows),
            "targeted_expanded60": len(expanded_rows),
            "targeted_confirm100": len(confirm_rows),
        },
        "split_diversity": {
            "targeted_pilot20": _diversity(pilot_rows),
            "targeted_expanded60": _diversity(expanded_rows),
            "targeted_confirm100": _diversity(confirm_rows),
        },
        "leakage_controls": {
            "labels_inspected_before_run": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "expected_answers_encoded": False,
            "cache_availability_used_for_selection": False,
            "unseen_truth_labels_may_be_read_only_after_sealed_run": True,
        },
        "cache_policy": {
            "baseline_control_cache": "eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }
    digest = _write_json(OUT, manifest)
    print(
        json.dumps(
            {
                "output_manifest": str(OUT),
                "sha256": digest,
                "split_sizes": manifest["split_sizes"],
                "split_diversity": manifest["split_diversity"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
