"""Build post-scale remaining fresh splits for gap-closure experiments.

The selection policy uses only scenario names, categories, and allowed tool
lists. It excludes scenarios already present in local paired-comparison outputs
and external-service families, then reserves a small pilot for repair selection
and a 100-task confirm split for one final unseen experimental comparison.
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
    "postscale_remaining_splits.json"
)

PILOT_LIMIT = 18
QUALITY_EXPANDED_LIMIT = 60
QUALITY_EXPANDED_FAMILY_CAP = 8
CONFIRM_LIMIT = 100


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


def _is_external_service(record: ScenarioRecord) -> bool:
    lower = record.name.lower()
    return any(token in lower for token in EXTERNAL_SERVICE_TOKENS)


def _round_robin(records: list[ScenarioRecord], *, limit: int) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)

    selected: list[ScenarioRecord] = []
    families = sorted(buckets)
    while len(selected) < limit and any(buckets.values()):
        for family in families:
            if len(selected) >= limit:
                break
            if buckets[family]:
                selected.append(buckets[family].popleft())
    if len(selected) < limit:
        raise RuntimeError(f"Needed {limit} records, selected {len(selected)}")
    return selected


def _capped_round_robin(
    records: list[ScenarioRecord], *, limit: int, family_cap: int
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
            if selected_by_family[family] >= family_cap:
                continue
            if buckets[family]:
                selected.append(buckets[family].popleft())
                selected_by_family[family] += 1
                made_progress = True
        if not made_progress:
            break
    if len(selected) < limit:
        raise RuntimeError(f"Needed {limit} capped records, selected {len(selected)}")
    return selected


def _row(
    record: ScenarioRecord,
    *,
    split_name: str,
    used_for_repair: bool,
    final_evaluation: bool,
) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": used_for_repair,
        "used_for_routing": used_for_repair,
        "used_for_validation": True,
        "final_evaluation": final_evaluation,
        "split": split_name,
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    labels = Counter(
        label for row in rows for label in row.get("task_labels", []) if label
    )
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "top_task_labels": dict(labels.most_common(20)),
        "near_duplicate_dominated": bool(
            rows and max(families.values()) / len(rows) > 0.35
        ),
        "diversity_reason": (
            "Remaining fresh split selected by deterministic base-family round "
            "robin from scenario names/categories/allowed tools only. It excludes "
            "all scenarios already present in local paired-comparison outputs and "
            "all external-service families; it does not use labels, expected "
            "answers, run outcomes, or cache availability."
        ),
    }


def main() -> None:
    records_by_name = {record.name: record for record in scenario_records()}
    existing_payload: dict[str, Any] = {}
    existing_pilot_names: list[str] = []
    if OUT.exists():
        try:
            existing_payload = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = {}
        existing_pilot = existing_payload.get("splits", {}).get(
            "postscale_remaining_pilot18", []
        )
        if isinstance(existing_pilot, list):
            existing_pilot_names = [
                str(row.get("scenario_id"))
                for row in existing_pilot
                if isinstance(row, dict) and row.get("scenario_id")
            ]

    prior = _prior_evaluated_scenarios()
    fresh = [
        record
        for record in records_by_name.values()
        if record.name not in prior and not _is_external_service(record)
    ]
    if len(existing_pilot_names) == PILOT_LIMIT:
        pilot = [
            records_by_name[name]
            for name in existing_pilot_names
            if name in records_by_name
            and not _is_external_service(records_by_name[name])
        ]
        if len(pilot) != PILOT_LIMIT:
            raise RuntimeError("Existing pilot split could not be reconstructed")
        confirm = _round_robin(fresh, limit=CONFIRM_LIMIT)
    else:
        ordered = _round_robin(fresh, limit=PILOT_LIMIT + CONFIRM_LIMIT)
        pilot = ordered[:PILOT_LIMIT]
        confirm = ordered[PILOT_LIMIT : PILOT_LIMIT + CONFIRM_LIMIT]
    expanded = _capped_round_robin(
        confirm,
        limit=QUALITY_EXPANDED_LIMIT,
        family_cap=QUALITY_EXPANDED_FAMILY_CAP,
    )

    splits = {
        "postscale_remaining_pilot18": [
            _row(
                record,
                split_name="postscale_remaining_pilot18",
                used_for_repair=True,
                final_evaluation=False,
            )
            for record in pilot
        ],
        "postscale_remaining_confirm100": [
            _row(
                record,
                split_name="postscale_remaining_confirm100",
                used_for_repair=False,
                final_evaluation=True,
            )
            for record in confirm
        ],
        "postscale_quality_expanded60": [
            _row(
                record,
                split_name="postscale_quality_expanded60",
                used_for_repair=False,
                final_evaluation=False,
            )
            for record in expanded
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_postscale_remaining_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "truth_labels_inspected": False,
        "prior_evaluated_scenario_count": len(prior),
        "fresh_candidate_scenario_count": len(fresh) + len(pilot),
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "excluded_if_seen_in_local_paired_outputs": True,
            "excluded_external_service_scenarios": True,
            "pilot_limit": PILOT_LIMIT,
            "quality_expanded_limit": QUALITY_EXPANDED_LIMIT,
            "quality_expanded_family_cap": QUALITY_EXPANDED_FAMILY_CAP,
            "confirm_limit": CONFIRM_LIMIT,
            "selection_order": (
                "deterministic base-family round-robin; expanded_60 uses the "
                "remaining unseen confirm pool with an 8-variant family cap"
            ),
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_run_outcomes": False,
            "used_cache_availability": False,
        },
        "split_aliases": {
            "pilot_20": "postscale_remaining_pilot18",
            "expanded_60": "postscale_quality_expanded60",
            "confirm_100": "postscale_remaining_confirm100",
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
