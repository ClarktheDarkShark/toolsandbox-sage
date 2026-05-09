"""Build a clean external-service holdout split for gap-closure follow-up.

This is the only remaining locally uninspected pool after the postscale
recency/time/day campaign. The split is experimental: external-service tasks
are intentionally marked contaminated for final-claim purposes.
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
    "external_holdout_splits.json"
)

CONFIRM_LIMIT = 100
CONFIRM_FAMILY_CAP = 10


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


def _scenario_ids_from_payload(payload: object) -> set[str]:
    found: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            raw = value.get("scenario_id")
            if isinstance(raw, str) and raw:
                found.add(raw)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
    return found


def _prior_seen_scenarios() -> set[str]:
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

    manifest_root = Path("artifacts/experiment_manifests/gap_closure_lab")
    for path in manifest_root.rglob("*.json"):
        if path == OUT:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prior.update(_scenario_ids_from_payload(payload))
    return prior


def _is_external_service(record: ScenarioRecord) -> bool:
    lower = record.name.lower()
    return any(token in lower for token in EXTERNAL_SERVICE_TOKENS)


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
        raise RuntimeError(f"Needed {limit} records, selected {len(selected)}")
    return selected


def _row(
    record: ScenarioRecord,
    *,
    split_name: str,
    final_evaluation: bool,
) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": final_evaluation,
        "external_service_contaminated_for_final_claim": True,
        "split": split_name,
    }


def _diversity(rows: list[dict[str, Any]], *, reason: str) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    labels = Counter(
        label for row in rows for label in row.get("task_labels", []) if label
    )
    largest = max(families.values()) if families else 0
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "largest_family_count": largest,
        "largest_family_share": largest / len(rows) if rows else 0.0,
        "top_task_labels": dict(labels.most_common(20)),
        "near_duplicate_dominated": bool(rows and largest / len(rows) > 0.35),
        "diversity_reason": reason,
    }


def main() -> None:
    prior = _prior_seen_scenarios()
    fresh_external = [
        record
        for record in scenario_records()
        if record.name not in prior and _is_external_service(record)
    ]
    confirm = _capped_round_robin(
        fresh_external,
        limit=CONFIRM_LIMIT,
        family_cap=CONFIRM_FAMILY_CAP,
    )
    confirm_names = {record.name for record in confirm}
    residual = [
        record
        for record in sorted(fresh_external, key=lambda item: item.name)
        if record.name not in confirm_names
    ]
    splits = {
        "external_holdout_confirm100": [
            _row(
                record,
                split_name="external_holdout_confirm100",
                final_evaluation=True,
            )
            for record in confirm
        ],
        "external_holdout_residual18": [
            _row(
                record,
                split_name="external_holdout_residual18",
                final_evaluation=False,
            )
            for record in residual
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_external_holdout_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "prior_seen_scenario_count": len(prior),
        "fresh_external_candidate_count": len(fresh_external),
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "excluded_if_seen_in_local_paired_outputs": True,
            "excluded_if_listed_in_prior_experiment_manifests": True,
            "included_only_external_service_families": True,
            "confirm_limit": CONFIRM_LIMIT,
            "confirm_family_cap": CONFIRM_FAMILY_CAP,
            "selection_order": "deterministic capped base-family round-robin",
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_run_outcomes": False,
            "used_cache_availability": False,
        },
        "split_aliases": {
            "confirm_100": "external_holdout_confirm100",
            "validate_100": "external_holdout_residual18",
        },
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {
            "external_holdout_confirm100": _diversity(
                splits["external_holdout_confirm100"],
                reason=(
                    "Fresh external-service scenarios selected by family-capped "
                    "round robin after excluding any scenario already evaluated "
                    "or listed in prior experiment manifests. This is diverse "
                    "within the remaining pool but external-service contaminated "
                    "for final-claim purposes."
                ),
            ),
            "external_holdout_residual18": _diversity(
                splits["external_holdout_residual18"],
                reason=(
                    "Residual fresh external-service scenarios after reserving "
                    "confirmation100. Use only as diagnostic follow-up; too "
                    "small for scale claims."
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
