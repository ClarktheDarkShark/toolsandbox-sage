"""Build a repair-only smoke manifest for the safe contact selector."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.config.splits import scenario_records

OUT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "safe_contact_selector_repair_smoke6_manifest.json"
)

SCENARIOS = [
    "modify_contact_with_message_recency_multiple_user_turn_alt_3_distraction_tools",
    "modify_contact_with_message_recency_multiple_user_turn_alt_3_distraction_tools_tool_description_scrambled",
    "modify_contact_with_message_recency_multiple_user_turn_alt_3_distraction_tools_arg_type_scrambled",
    "modify_contact_with_message_recency_insufficient_information_3_distraction_tools",
    "search_message_with_recency_latest_multiple_user_turn_alt_3_distraction_tools",
    "search_reminder_with_recency_upcoming_insufficient_information_implicit_3_distraction_tools_tool_name_scrambled",
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


def _family(name: str) -> str:
    if name.startswith("modify_contact_with_message_recency_insufficient_information"):
        return "modify_contact_with_message_recency_insufficient_information"
    if name.startswith("modify_contact_with_message_recency"):
        return "modify_contact_with_message_recency"
    if name.startswith("search_message_with_recency"):
        return "search_message_with_recency"
    if name.startswith("search_reminder_with_recency_upcoming"):
        return "search_reminder_with_recency_upcoming"
    return name.split("_", 1)[0]


def main() -> None:
    by_name = {record.name: record for record in scenario_records()}
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        record = by_name[scenario]
        rows.append(
            {
                "scenario_id": scenario,
                "family_label": _family(scenario),
                "task_labels": list(record.categories),
                "allowed_tools": list(record.allowed_tools),
                "truth_labels_inspected": False,
                "used_for_generation": False,
                "used_for_repair": True,
                "used_for_routing": False,
                "used_for_validation": True,
                "used_for_final_evaluation": False,
                "final_evaluation": False,
                "split": "safe_contact_selector_repair_smoke6",
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_safe_contact_selector_repair_smoke",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "purpose": (
            "Repair-only smoke test for the safe contact selector. Includes the "
            "post-confirm100 malformed-id failure case and nearby negatives; not "
            "promotion evidence."
        ),
        "source_of_repair_contamination": (
            "A sealed-run malformed visible-ID failure was inspected to repair "
            "generic contact-update argument handling."
        ),
        "split_aliases": {"smoke_6": "safe_contact_selector_repair_smoke6"},
        "splits": {"safe_contact_selector_repair_smoke6": rows},
        "split_sizes": {"safe_contact_selector_repair_smoke6": len(rows)},
        "split_diversity": {
            "safe_contact_selector_repair_smoke6": {
                "scenario_count": len(rows),
                "distinct_family_count": len({row["family_label"] for row in rows}),
                "near_duplicate_dominated": True,
                "near_duplicate_assessment": (
                    "Repair smoke intentionally contains related contact-recency variants "
                    "plus search/reminder negatives; it is diagnostic only."
                ),
            }
        },
        "leakage_controls": {
            "truth_labels_inspected_before_run": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "expected_answers_encoded": False,
            "cache_availability_used_for_selection": False,
            "repair_contaminated_not_final_evidence": True,
        },
        "cache_policy": {
            "baseline_control_cache": "eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }
    digest = _write_json(OUT, manifest)
    print(json.dumps({"output_manifest": str(OUT), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
