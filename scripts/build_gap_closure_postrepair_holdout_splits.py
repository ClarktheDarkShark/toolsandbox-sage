"""Build leak-clean post-repair holdout splits for gap-closure validation.

The split policy is deterministic and uses only scenario names, categories, and
allowed tool lists. It excludes scenarios already observed in local
paired-comparison outputs, so a tool repaired from a previous task is evaluated
on fresh scenarios when enough benchmark surface remains.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import EXTERNAL_SERVICE_TOKENS, base_task_family

OUT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "postrepair_holdout_splits.json"
)

TARGET_FAMILY_PREFIXES = (
    "modify_contact_with_message_recency",
    "modify_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest",
    "search_message_with_recency",
    "search_reminder_with_creation_recency_yesterday",
    "search_reminder_with_recency_yesterday",
    "search_reminder_with_recency_upcoming",
)

CONFIRM_TARGET_LIMIT = 24
MAX_CONFIRM_TARGETS_PER_BASE_FAMILY = 8

VARIANT_MARKERS = (
    "_insufficient_information",
    "_multiple_user_turn",
    "_3_distraction_tools",
    "_10_distraction_tools",
    "_all_tools",
    "_arg_description_scrambled",
    "_arg_type_scrambled",
    "_tool_description_scrambled",
    "_tool_name_scrambled",
    "_wifi_off",
    "_low_battery_mode",
    "_no_wifi",
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


def _target_family(name: str) -> str | None:
    for prefix in TARGET_FAMILY_PREFIXES:
        if name.startswith(prefix):
            return prefix
    return None


def _is_external_service(record: ScenarioRecord) -> bool:
    lower = record.name.lower()
    return any(token in lower for token in EXTERNAL_SERVICE_TOKENS)


def _family_label(name: str) -> str:
    target = _target_family(name)
    if target is not None:
        return target
    split_at = len(name)
    for marker in VARIANT_MARKERS:
        position = name.find(marker)
        if position > 0:
            split_at = min(split_at, position)
    return name[:split_at]


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


def _record_to_row(record: ScenarioRecord, *, split_name: str) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": _family_label(record.name),
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


def _round_robin(records: list[ScenarioRecord], *, limit: int) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[_family_label(record.name)].append(record)

    selected: list[ScenarioRecord] = []
    families = sorted(buckets)
    while len(selected) < limit and any(buckets.values()):
        for family in families:
            if len(selected) >= limit:
                break
            bucket = buckets[family]
            if bucket:
                selected.append(bucket.popleft())
    if len(selected) < limit:
        raise RuntimeError(f"Needed {limit} scenarios, selected {len(selected)}")
    return selected


def _round_robin_capped_by_base_family(
    records: list[ScenarioRecord],
    *,
    limit: int,
    max_per_base_family: int,
) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)

    selected: list[ScenarioRecord] = []
    selected_by_family: Counter[str] = Counter()
    families = sorted(buckets)
    while len(selected) < limit and any(buckets.values()):
        made_progress = False
        for family in families:
            if len(selected) >= limit:
                break
            if selected_by_family[family] >= max_per_base_family:
                continue
            bucket = buckets[family]
            if not bucket:
                continue
            selected.append(bucket.popleft())
            selected_by_family[family] += 1
            made_progress = True
        if not made_progress:
            break
    return selected


def _take_broad(
    records: list[ScenarioRecord],
    *,
    limit: int,
    used: set[str],
) -> list[ScenarioRecord]:
    available = [record for record in records if record.name not in used]
    selected = _round_robin(available, limit=limit)
    used.update(record.name for record in selected)
    return selected


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    labels = Counter(
        label for row in rows for label in row.get("task_labels", []) if label
    )
    target_count = sum(
        1 for row in rows if _target_family(str(row["scenario_id"])) is not None
    )
    insufficient_count = sum(
        1 for row in rows if "INSUFFICIENT_INFORMATION" in row.get("task_labels", [])
    )
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "top_task_labels": dict(labels.most_common(20)),
        "target_recency_action_count": target_count,
        "insufficient_information_count": insufficient_count,
        "near_duplicate_dominated": bool(
            rows and max(families.values()) / len(rows) > 0.35
        ),
        "diversity_reason": (
            "Post-repair holdout selected from scenarios not present in local "
            "paired-comparison outputs. Selection uses deterministic family "
            "round-robin over scenario names/categories/allowed tools only; it "
            "does not use truth labels, expected answers, run outcomes, or cache "
            "availability."
        ),
    }


def main() -> None:
    prior = _prior_evaluated_scenarios()
    fresh_records = [
        record
        for record in scenario_records()
        if record.name not in prior and not _is_external_service(record)
    ]
    target_records = [
        record for record in fresh_records if _target_family(record.name) is not None
    ]
    non_target_records = [
        record for record in fresh_records if _target_family(record.name) is None
    ]
    used: set[str] = set()

    targeted_rows = [
        _record_to_row(record, split_name="postrepair_targeted_holdout")
        for record in sorted(target_records, key=lambda item: item.name)
    ]

    mixed_confirm_records = _round_robin_capped_by_base_family(
        target_records,
        limit=min(CONFIRM_TARGET_LIMIT, len(target_records)),
        max_per_base_family=MAX_CONFIRM_TARGETS_PER_BASE_FAMILY,
    )
    used.update(record.name for record in mixed_confirm_records)
    needed_for_confirm = max(0, 100 - len(mixed_confirm_records))
    if needed_for_confirm:
        mixed_confirm_records.extend(
            _take_broad(non_target_records, limit=needed_for_confirm, used=used)
        )

    broad_expanded_records = _take_broad(fresh_records, limit=60, used=used)
    broad_scale_records = _take_broad(fresh_records, limit=250, used=used)

    splits = {
        "postrepair_targeted_holdout": targeted_rows,
        "postrepair_mixed_confirm100": [
            _record_to_row(record, split_name="postrepair_mixed_confirm100")
            for record in _round_robin(mixed_confirm_records, limit=100)
        ],
        "postrepair_broad_expanded60": [
            _record_to_row(record, split_name="postrepair_broad_expanded60")
            for record in broad_expanded_records
        ],
        "postrepair_broad_scale250": [
            _record_to_row(record, split_name="postrepair_broad_scale250")
            for record in broad_scale_records
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_postrepair_holdout_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "truth_labels_inspected": False,
        "prior_evaluated_scenario_count": len(prior),
        "fresh_candidate_scenario_count": len(fresh_records),
        "targeted_holdout_scenario_count": len(target_records),
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "excluded_if_seen_in_local_paired_outputs": True,
            "excluded_external_service_scenarios": True,
            "included_target_family_prefixes": list(TARGET_FAMILY_PREFIXES),
            "mixed_confirm_policy": (
                "Include a base-family-capped fresh recency/action target block, "
                "then fill to 100 with deterministic broad holdout records."
            ),
            "confirm_target_limit": CONFIRM_TARGET_LIMIT,
            "max_confirm_targets_per_base_family": MAX_CONFIRM_TARGETS_PER_BASE_FAMILY,
            "broad_selection_policy": "deterministic family round-robin",
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_run_outcomes": False,
            "used_cache_availability": False,
        },
        "split_aliases": {
            "mechanism_40": "postrepair_targeted_holdout",
            "expanded_60": "postrepair_broad_expanded60",
            "confirm_100": "postrepair_mixed_confirm100",
            "validate_250": "postrepair_broad_scale250",
            "promotion_250": "postrepair_broad_scale250",
        },
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {name: _diversity(rows) for name, rows in splits.items()},
        "leakage_controls": {
            "labels_inspected_before_run": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "expected_answers_encoded": False,
            "cache_availability_used_for_selection": False,
            "unseen_truth_labels_may_be_read_only_after_sealed_run": True,
            "repair_trigger_tasks_excluded_if_present_in_outputs": True,
        },
        "cache_policy": {
            "baseline_control_cache": "eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }
    digest = _write_json(OUT, payload)
    print(
        json.dumps(
            {
                "output_manifest": str(OUT),
                "sha256": digest,
                "split_sizes": payload["split_sizes"],
                "split_diversity": payload["split_diversity"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
