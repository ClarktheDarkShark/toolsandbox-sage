"""Build residual fresh splits after the postscale expanded60 run.

Only a small, family-skewed residual pool remains. These splits are for
diagnostic gap-closure testing, not broad claim evidence.
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
    "postexpanded_residual_splits.json"
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


def _round_robin(records: list[ScenarioRecord]) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)
    selected: list[ScenarioRecord] = []
    families = sorted(buckets)
    while any(buckets.values()):
        for family in families:
            if buckets[family]:
                selected.append(buckets[family].popleft())
    return selected


def _row(record: ScenarioRecord, *, split_name: str) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": True,
        "used_for_routing": True,
        "used_for_validation": True,
        "final_evaluation": False,
        "split": split_name,
    }


def _diversity(rows: list[dict[str, Any]], *, reason: str) -> dict[str, Any]:
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
        "diversity_reason": reason,
    }


def main() -> None:
    prior = _prior_evaluated_scenarios()
    remaining = [
        record
        for record in scenario_records()
        if record.name not in prior and not _is_external_service(record)
    ]
    all40 = _round_robin(remaining)
    holiday = [
        record
        for record in sorted(remaining, key=lambda item: item.name)
        if record.name.startswith("find_days_till_holiday")
    ]
    splits = {
        "postexpanded_residual_all40": [
            _row(record, split_name="postexpanded_residual_all40") for record in all40
        ],
        "postexpanded_residual_holiday19": [
            _row(record, split_name="postexpanded_residual_holiday19")
            for record in holiday
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_postexpanded_residual_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "diagnostic_only": True,
        "truth_labels_inspected": False,
        "prior_evaluated_scenario_count": len(prior),
        "fresh_candidate_scenario_count": len(remaining),
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "excluded_if_seen_in_local_paired_outputs": True,
            "excluded_external_service_scenarios": True,
            "selection_order": "deterministic base-family round-robin",
            "holiday_split_selection": "name prefix only; no labels or expected answers",
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_run_outcomes": False,
            "used_cache_availability": False,
        },
        "split_aliases": {
            "pilot_20": "postexpanded_residual_holiday19",
            "expanded_60": "postexpanded_residual_all40",
            "confirm_100": "postexpanded_residual_all40",
        },
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {
            "postexpanded_residual_all40": _diversity(
                splits["postexpanded_residual_all40"],
                reason=(
                    "All remaining fresh, non-external scenarios after the "
                    "expanded60 quality run. The pool is family-skewed, so use "
                    "only as diagnostic evidence."
                ),
            ),
            "postexpanded_residual_holiday19": _diversity(
                splits["postexpanded_residual_holiday19"],
                reason=(
                    "Fresh remaining holiday/day-distance tasks selected by "
                    "scenario-name prefix only to diagnose the generic "
                    "days_between_timestamps helper."
                ),
            ),
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
