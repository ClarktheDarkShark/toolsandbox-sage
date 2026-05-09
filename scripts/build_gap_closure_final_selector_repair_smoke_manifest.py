"""Build a small diagnostic manifest for post-search message recency repair."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.config.splits import scenario_records

OUT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "final_selector_repair_smoke6_manifest.json"
)

SCENARIOS = [
    "search_message_with_recency_latest_multiple_user_turn_alt_3_distraction_tools_arg_description_scrambled",
    "search_message_with_recency_latest_multiple_user_turn_alt_3_distraction_tools_arg_type_scrambled",
    "search_message_with_recency_latest_multiple_user_turn_alt_3_distraction_tools_tool_name_scrambled",
    "search_message_with_recency_latest_multiple_user_turn_3_distraction_tools_arg_description_scrambled",
    "search_message_with_recency_oldest_3_distraction_tools",
    "search_message_with_recency_oldest_3_distraction_tools_arg_type_scrambled",
]


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


def main() -> None:
    records = {record.name: record for record in scenario_records()}
    missing = [name for name in SCENARIOS if name not in records]
    if missing:
        raise RuntimeError(f"Unknown scenarios: {missing}")
    rows = []
    for name in SCENARIOS:
        record = records[name]
        rows.append(
            {
                "scenario_id": record.name,
                "family_label": (
                    "search_message_with_recency_oldest"
                    if "oldest" in record.name
                    else "search_message_with_recency_latest"
                ),
                "task_labels": list(record.categories),
                "allowed_tools": list(record.allowed_tools),
                "truth_labels_inspected": False,
                "used_for_generation": False,
                "used_for_repair": True,
                "used_for_routing": False,
                "used_for_validation": True,
                "final_evaluation": False,
                "split": "final_selector_repair_smoke6",
            }
        )
    families = Counter(row["family_label"] for row in rows)
    manifest = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_final_selector_repair_smoke6",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "truth_labels_inspected": False,
        "selection_policy": {
            "source": "tool_sandbox.scenarios named_scenarios via scenario_records",
            "purpose": (
                "Diagnostic-only repair replay for post-search message recency "
                "selection. Includes a sealed-run recency selection failure "
                "mechanism and near variants; not promotion evidence."
            ),
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
        },
        "split_aliases": {"smoke_6": "final_selector_repair_smoke6"},
        "splits": {"final_selector_repair_smoke6": rows},
        "split_sizes": {"final_selector_repair_smoke6": len(rows)},
        "split_diversity": {
            "final_selector_repair_smoke6": {
                "scenario_count": len(rows),
                "distinct_family_count": len(families),
                "family_counts": dict(sorted(families.items())),
                "near_duplicate_dominated": True,
                "diversity_reason": (
                    "Intentional diagnostic near-variant set for one repaired "
                    "failure mode. It is unsuitable for final evidence."
                ),
            }
        },
        "leakage_controls": {
            "labels_inspected_before_run": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "expected_answers_encoded": False,
            "cache_availability_used_for_selection": False,
            "repair_contaminated": True,
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
