# mypy: ignore-errors
"""Build schedule-v3 adoption variants for gap-closure testing.

Experimental only. The schedule-v2 broad runs showed strong natural value, but
the exact whole-week helper was repeatedly visible-not-called. These variants
test a clearer helper name and metadata while keeping the rest of the retained
schedule/recency portfolio fixed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
SUMMARY_OUT = (
    Path("artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop")
    / "schedule_v3_adoption_variants_summary.json"
)

BASE = (
    REGISTRY_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
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
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["tools"])


def _renamed_week_helper(entry: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    tool = updated["tool"]
    spec = tool["spec"]
    spec["tool_name"] = "weeks_from_now_time_to_timestamp"
    spec["description"] = (
        "Reminder scheduling helper for whole-week offsets. Call this after "
        "get_current_timestamp and before add_reminder/modify_reminder when the "
        "user says next week, in one week, in two weeks, in three weeks, or an "
        "equivalent whole-week delay at a local time. It directly returns "
        "reminder_timestamp and add_reminder_kwargs. Do not use it for named "
        "weekdays like next Friday, tomorrow, yesterday, reminder recency search, "
        "or insufficient-information tasks. Pure helper; no side effects."
    )
    spec["inputs"][1]["description"] = (
        "Whole weeks from the current local date. Use 1 for next week or in one "
        "week, 2 for in two weeks, 3 for in three weeks."
    )
    spec["positive_triggers"] = [
        "next week at a time",
        "in one week at a time",
        "in two weeks at a time",
        "in three weeks at a time",
        "week_delta reminder scheduling",
        "add_reminder_content_and_week_delta_and_time",
        "add_reminder_content_and_week_delta_and_time_and_location",
    ]
    spec["negative_triggers"] = [
        "tomorrow",
        "yesterday",
        "next monday",
        "next tuesday",
        "next friday",
        "weekday_delta",
        "recency_latest",
        "search_reminder_with_recency",
        "insufficient_information",
    ]
    spec["reason_tool_is_decisive"] = (
        "It makes the whole-week offset explicit in the function name and returns "
        "the exact reminder_timestamp needed by the original reminder side-effect "
        "tool, avoiding manual seven-day arithmetic."
    )
    spec["known_failure_mechanisms_addressed"] = [
        "visible_not_called_whole_week_helper",
        "week_delta_to_day_offset_arithmetic",
        "timestamp_not_final_answer_ready",
    ]
    spec["adoption_experiment_note"] = (
        "schedule_v3_week_renamed: repair relative_weeks_time_to_timestamp "
        "visible-not-called by using a trigger-focused name and metadata."
    )
    code = str(tool["code"])
    tool["code"] = code.replace(
        "def relative_weeks_time_to_timestamp(",
        "def weeks_from_now_time_to_timestamp(",
        1,
    )
    updated["code_hash"] = _sha256(str(tool["code"]).encode("utf-8"))
    validation = updated.get("validation")
    if isinstance(validation, dict):
        validation["diagnostic_notes"] = [
            *validation.get("diagnostic_notes", []),
            "Experimental metadata/name-only adoption repair; implementation body unchanged from relative_weeks_time_to_timestamp.",
        ]
    return updated


def _selector_hint(entry: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    spec["description"] = (
        "Visible-record selector for recency tasks. After an original search "
        "returns records, call this when the user asks for the latest, last, most "
        "recent, oldest, earliest, first, or newest message/reminder/contact "
        "record. Pass the records list, the timestamp field, and mode='latest' or "
        "mode='oldest'. It returns selected_record and selected_id for the final "
        "answer or the next original side-effect tool. Do not manually pick the "
        "first record when a recency extreme is requested. Ties in timestamp are "
        "broken deterministically by original list order, with the first matching "
        "record in the input list selected."
    )
    spec["positive_triggers"] = [
        "latest record after search",
        "oldest record after search",
        "last message after search_messages",
        "most recent reminder after search_reminder",
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
    ]
    spec["adoption_experiment_note"] = (
        "schedule_v3_selector_hint: compress selector metadata to improve natural "
        "post-search adoption without changing implementation."
    )
    return updated


def _mark(entry: dict[str, Any], note: str) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    existing = str(spec.get("adoption_experiment_note", "")).strip()
    spec["adoption_experiment_note"] = f"{existing}; {note}" if existing else note
    return updated


def _base_without(base_tools: dict[str, Any], *names: str) -> dict[str, Any]:
    removed = set(names)
    return {
        name: _mark(entry, "schedule_v3_base_retained")
        for name, entry in base_tools.items()
        if name not in removed
    }


def main() -> None:
    base_tools = _load_tools(BASE)
    week_helper = _renamed_week_helper(base_tools["relative_weeks_time_to_timestamp"])

    week_renamed = {
        **_base_without(base_tools, "relative_weeks_time_to_timestamp"),
        "weeks_from_now_time_to_timestamp": week_helper,
    }

    week_renamed_selector_hint = copy.deepcopy(week_renamed)
    week_renamed_selector_hint["select_record_by_timestamp_extreme"] = _selector_hint(
        week_renamed_selector_hint["select_record_by_timestamp_extreme"]
    )

    variants = {
        "full_timestamp_schedule_v3_week_renamed_pack": week_renamed,
        "full_timestamp_schedule_v3_week_renamed_selector_hint_pack": week_renamed_selector_hint,
    }

    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "base_registry": str(BASE),
        "base_registry_sha256": _sha256(BASE.read_bytes()),
        "objective": (
            "Repair the whole-week scheduling visible-not-called lane and test "
            "whether shorter selector metadata improves post-search adoption."
        ),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "candidate_arms_fresh_only": True,
            "baseline_cache_policy": "use-if-eligible",
        },
        "variants": {},
    }
    for label, tools in variants.items():
        path = REGISTRY_ROOT / label / "registry_manifest.json"
        digest = _write_json(path, {"tools": tools})
        summary["variants"][label] = {
            "path": str(path),
            "sha256": digest,
            "tools": sorted(tools),
        }

    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
