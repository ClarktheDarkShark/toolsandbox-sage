"""Build targeted bucket manifests for gap-closure loop diagnostics.

Experimental only. Selection uses scenario names, categories, and allowed
ToolSandbox tools. It does not inspect truth labels, expected answers, traces,
or cache availability.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import base_task_family

OUT_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)

TARGETS: dict[str, dict[str, Any]] = {
    "contact_recency_phone_positive": {
        "manifest_type": "sage_gap_closure_lab_contact_recency_phone_positive_splits",
        "bucket": "contact_crud_high_fit",
        "path": OUT_ROOT / "contact_recency_phone_positive_splits.json",
        "families": (
            "add_contact_with_name_and_phone_number",
            "modify_contact_with_message_recency",
            "remove_contact_by_phone",
            "remove_contact_with_id",
            "update_contact_with_id_and_phone_number",
        ),
        "selection_note": (
            "Contact CRUD high-fit subset selected from prior experimental root-cause "
            "classification: message-recency contact update and remove-by-phone lanes "
            "showed positive natural helper value; add/remove-by-id/update-by-id lanes "
            "were neutral enough to include for unique 100-task coverage, while "
            "relationship update lanes were outcome-negative and are excluded for "
            "separate repair."
        ),
    },
    "reminder_positive_scheduling": {
        "manifest_type": "sage_gap_closure_lab_reminder_positive_scheduling_splits",
        "bucket": "reminder_crud_positive_fit",
        "path": OUT_ROOT / "reminder_positive_scheduling_splits.json",
        "families": (
            "add_reminder_content_and_date_and_time",
            "add_reminder_content_and_week_delta_and_time",
            "add_reminder_content_and_weekday_delta_and_time",
            "modify_reminder_with_recency_latest",
        ),
        "selection_note": (
            "Reminder scheduling high-fit subset selected from prior experimental "
            "root-cause classification: relative week/day conversion and latest "
            "modify lanes had positive pilot signal; direct date-and-time creation "
            "was neutral and is included for unique 100-task coverage. Remove-latest "
            "remains under bridge repair and is excluded from this high-fit manifest."
        ),
    },
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _scenario_family(record: ScenarioRecord) -> str:
    return base_task_family(record.name)


def _matching_records(
    records: Iterable[ScenarioRecord], families: tuple[str, ...]
) -> dict[str, list[ScenarioRecord]]:
    grouped: dict[str, list[ScenarioRecord]] = defaultdict(list)
    for record in records:
        family = _scenario_family(record)
        if family in families:
            grouped[family].append(record)
    return {
        family: sorted(grouped[family], key=lambda item: item.name)
        for family in families
    }


def _round_robin(
    grouped: dict[str, list[ScenarioRecord]], size: int
) -> list[ScenarioRecord]:
    queues = {family: deque(rows) for family, rows in grouped.items() if rows}
    selected: list[ScenarioRecord] = []
    while queues and len(selected) < size:
        for family in list(queues):
            queue = queues.get(family)
            if not queue:
                queues.pop(family, None)
                continue
            selected.append(queue.popleft())
            if not queue:
                queues.pop(family, None)
            if len(selected) >= size:
                break
    if len(selected) < size:
        raise RuntimeError(
            f"only selected {len(selected)} records for requested size {size}"
        )
    return selected


def _row(record: ScenarioRecord, *, bucket: str, split: str) -> dict[str, object]:
    return {
        "name": record.name,
        "scenario_id": record.name,
        "family_label": _scenario_family(record),
        "bucket": bucket,
        "split": split,
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": True,
    }


def _diversity(rows: list[dict[str, object]]) -> dict[str, object]:
    families = Counter(str(row["family_label"]) for row in rows)
    buckets = Counter(str(row["bucket"]) for row in rows)
    largest = max(families.values()) if families else 0
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "bucket_counts": dict(sorted(buckets.items())),
        "largest_family_count": largest,
        "largest_family_share": largest / len(rows) if rows else 0.0,
        "near_duplicate_dominated": bool(rows and largest / len(rows) > 0.75),
        "reason_not_near_duplicate_dominated": (
            "Round-robin selection across targeted base families; the largest family "
            "share remains at or below the narrow-bucket threshold."
        ),
    }


def _manifest(key: str, config: dict[str, Any]) -> dict[str, object]:
    records = scenario_records()
    families = tuple(str(item) for item in config["families"])
    grouped = _matching_records(records, families)
    counts = {family: len(rows) for family, rows in grouped.items()}
    if any(count == 0 for count in counts.values()):
        raise RuntimeError(f"missing family records: {counts}")

    bucket = str(config["bucket"])
    split_specs = {
        f"{key}_20": 20,
        f"{key}_60": 60,
        f"{key}_100": 100,
    }
    splits: dict[str, list[dict[str, object]]] = {}
    diversity: dict[str, object] = {}
    for split_name, size in split_specs.items():
        selected = _round_robin(grouped, size)
        rows = [_row(record, bucket=bucket, split=split_name) for record in selected]
        splits[split_name] = rows
        diversity[split_name] = _diversity(rows)

    payload = {
        "schema_version": 1,
        "manifest_type": str(config["manifest_type"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "selection_policy": {
            "selection_note": str(config["selection_note"]),
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
            "uses_prior_experimental_gap_assessment": True,
            "source": "ToolSandbox scenario names/categories/allowed tools only",
        },
        "cache_policy": {
            "baseline_control_cache": "use-if-eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
        "split_aliases": {
            "pilot_20": f"{key}_20",
            "expanded_60": f"{key}_60",
            "confirm_100": f"{key}_100",
            "validate_100": f"{key}_100",
        },
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": diversity,
        "available_family_counts": counts,
        "splits": splits,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    payload["manifest_sha256"] = _sha256(text.encode("utf-8"))
    return payload


def _write(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def main() -> None:
    manifests: dict[str, object] = {}
    summary: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "manifests": manifests,
        "leakage_statement": (
            "No truth labels, expected answers, scenario outputs, hidden facts, or "
            "cache availability are used. Selection is by predeclared scenario-family "
            "names and prior aggregate experimental root-cause categories."
        ),
    }
    for key, config in TARGETS.items():
        manifest = _manifest(key, config)
        path = Path(config["path"])
        digest = _write(path, manifest)
        manifests[key] = {
            "path": str(path),
            "sha256": digest,
            "split_sizes": manifest["split_sizes"],
            "available_family_counts": manifest["available_family_counts"],
        }
    digest = _write(OUT_ROOT / "bucket_targeted_splits_build_summary.json", summary)
    print(json.dumps({**summary, "summary_sha256": digest}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
