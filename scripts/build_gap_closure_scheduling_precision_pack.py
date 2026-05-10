# mypy: ignore-errors
"""Build experimental reminder scheduling precision packs.

Experimental only. These packs target the remaining reminder scheduling
regressions observed in the confirmed-bucket broad run, especially week-delta
and weekday-delta timestamp construction. They do not modify protected
registries or final evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
CORE_REGISTRY = REGISTRY_ROOT / "confirmed_bucket_core_pack" / "registry_manifest.json"
SUMMARY_OUT = MANIFEST_ROOT / "scheduling_precision_pack_summary.json"

WEEK_DELTA_CODE = '''
def week_delta_time_to_timestamp(current_timestamp: float, week_delta: int, hour: int, minute: int, local_utc_offset_hours: float) -> dict:
    """Convert an exact week offset plus local time into a UTC Unix timestamp."""
    week_delta = int(week_delta)
    hour = int(hour)
    minute = int(minute)
    if week_delta < 0 or hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return {
            "ok": False,
            "timestamp": 0.0,
            "reminder_timestamp": 0.0,
            "day_offset": 0,
            "add_reminder_kwargs": {},
            "reason": "invalid_week_delta_or_time",
            "final_answer_recommendation": "abstain:invalid_reminder_time",
        }
    seconds_per_day = 86400.0
    offset_seconds = float(local_utc_offset_hours) * 3600.0
    current_local_day = int((float(current_timestamp) + offset_seconds) // seconds_per_day)
    day_offset = week_delta * 7
    target_local_day = current_local_day + day_offset
    timestamp = (target_local_day * seconds_per_day) - offset_seconds + (hour * 3600.0) + (minute * 60.0)
    return {
        "ok": True,
        "timestamp": float(timestamp),
        "reminder_timestamp": float(timestamp),
        "day_offset": int(day_offset),
        "add_reminder_kwargs": {"reminder_timestamp": float(timestamp)},
        "reason": "week_delta_time_resolved",
        "final_answer_recommendation": "use reminder_timestamp for add_reminder or modify_reminder",
    }
'''

WEEKDAY_DELTA_CODE = '''
def weekday_delta_time_to_timestamp(current_timestamp: float, target_weekday: str, week_delta: int, hour: int, minute: int, local_utc_offset_hours: float, include_today: bool) -> dict:
    """Convert a target weekday plus week offset and local time into a UTC timestamp."""
    names = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    key = str(target_weekday or "").strip().lower()
    target = names.get(key)
    week_delta = int(week_delta)
    hour = int(hour)
    minute = int(minute)
    if target is None or week_delta < 0 or hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return {
            "ok": False,
            "timestamp": 0.0,
            "reminder_timestamp": 0.0,
            "day_offset": 0,
            "add_reminder_kwargs": {},
            "reason": "invalid_weekday_or_time",
            "final_answer_recommendation": "abstain:invalid_reminder_time",
        }
    seconds_per_day = 86400.0
    offset_seconds = float(local_utc_offset_hours) * 3600.0
    current_local_day = int((float(current_timestamp) + offset_seconds) // seconds_per_day)
    # Unix day 0 was Thursday. With Monday=0, current weekday is day + 3 modulo 7.
    current_weekday = (current_local_day + 3) % 7
    days_until = (target - current_weekday) % 7
    if days_until == 0 and not bool(include_today):
        days_until = 7
    day_offset = days_until + (week_delta * 7)
    target_local_day = current_local_day + day_offset
    timestamp = (target_local_day * seconds_per_day) - offset_seconds + (hour * 3600.0) + (minute * 60.0)
    return {
        "ok": True,
        "timestamp": float(timestamp),
        "reminder_timestamp": float(timestamp),
        "day_offset": int(day_offset),
        "weekday_index": int(target),
        "add_reminder_kwargs": {"reminder_timestamp": float(timestamp)},
        "reason": "weekday_delta_time_resolved",
        "final_answer_recommendation": "use reminder_timestamp for add_reminder or modify_reminder",
    }
'''


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


def _entry(
    tool: GeneratedTool, examples: tuple[ToolExample, ...], birth: str
) -> dict[str, Any]:
    validation = validate_generated_tool(tool, examples)
    if not validation.accepted:
        raise RuntimeError(
            f"{tool.spec.tool_name} validation failed: {validation.errors}"
        )
    return RegistryEntry.accepted(
        tool=tool, validation=validation, birth_scenario=birth
    ).to_json()


def _week_delta_expected(
    current_timestamp: float,
    week_delta: int,
    hour: int,
    minute: int,
    local_utc_offset_hours: float,
) -> dict[str, Any]:
    offset_seconds = local_utc_offset_hours * 3600.0
    current_local_day = int((current_timestamp + offset_seconds) // 86400.0)
    day_offset = week_delta * 7
    timestamp = (
        ((current_local_day + day_offset) * 86400.0)
        - offset_seconds
        + (hour * 3600.0)
        + (minute * 60.0)
    )
    return {
        "ok": True,
        "timestamp": float(timestamp),
        "reminder_timestamp": float(timestamp),
        "day_offset": int(day_offset),
        "add_reminder_kwargs": {"reminder_timestamp": float(timestamp)},
        "reason": "week_delta_time_resolved",
        "final_answer_recommendation": "use reminder_timestamp for add_reminder or modify_reminder",
    }


def _weekday_delta_expected(
    current_timestamp: float,
    weekday_index: int,
    week_delta: int,
    hour: int,
    minute: int,
    local_utc_offset_hours: float,
    include_today: bool,
) -> dict[str, Any]:
    offset_seconds = local_utc_offset_hours * 3600.0
    current_local_day = int((current_timestamp + offset_seconds) // 86400.0)
    current_weekday = (current_local_day + 3) % 7
    days_until = (weekday_index - current_weekday) % 7
    if days_until == 0 and not include_today:
        days_until = 7
    day_offset = days_until + (week_delta * 7)
    timestamp = (
        ((current_local_day + day_offset) * 86400.0)
        - offset_seconds
        + (hour * 3600.0)
        + (minute * 60.0)
    )
    return {
        "ok": True,
        "timestamp": float(timestamp),
        "reminder_timestamp": float(timestamp),
        "day_offset": int(day_offset),
        "weekday_index": int(weekday_index),
        "add_reminder_kwargs": {"reminder_timestamp": float(timestamp)},
        "reason": "weekday_delta_time_resolved",
        "final_answer_recommendation": "use reminder_timestamp for add_reminder or modify_reminder",
    }


def _week_delta_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="week_delta_time_to_timestamp",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description=(
            "Reminder scheduling helper for requests like 'in two weeks at 9 AM'. "
            "After get_current_timestamp returns the current time, call this "
            "instead of manually converting weeks to days. It returns a "
            "reminder_timestamp and add_reminder_kwargs. Pure helper; no side effects."
        ),
        inputs=(
            ToolInput(
                "current_timestamp",
                "float",
                "Current Unix timestamp from get_current_timestamp.",
            ),
            ToolInput(
                "week_delta",
                "int",
                "Number of whole weeks from the current local date. Use 1 for next week, 2 for two weeks, etc.",
            ),
            ToolInput("hour", "int", "Target local hour in 24-hour time."),
            ToolInput("minute", "int", "Target local minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local UTC offset; use -4 for ToolSandbox unless another offset is known.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "timestamp": {"type": "number"},
                "reminder_timestamp": {"type": "number"},
                "day_offset": {"type": "integer"},
                "add_reminder_kwargs": {"type": "object"},
                "reason": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
            "required": [
                "ok",
                "timestamp",
                "reminder_timestamp",
                "day_offset",
                "reason",
            ],
        },
        positive_triggers=(
            "add_reminder_content_and_week_delta_and_time",
            "add_reminder_content_and_week_delta_and_time_and_location",
            "week_delta",
            "in two weeks",
            "next week",
        ),
        negative_triggers=(
            "recency_latest",
            "search_reminder_with_recency",
            "insufficient_information",
            "weekday_delta",
        ),
        preserves_side_effect_tools=("add_reminder", "modify_reminder"),
        required_original_tool_calls=("get_current_timestamp", "add_reminder"),
        abstain_behavior="Return ok false and no add_reminder_kwargs for invalid week/time inputs.",
        generalization_rationale=(
            "Week-delta reminder creation appears across no-distraction and "
            "distraction variants; a deterministic timestamp tool removes a "
            "repeated arithmetic/planning burden without performing side effects."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=(
            "add_reminder_content_and_week_delta_and_time",
            "add_reminder_content_and_week_delta_and_time_and_location",
        ),
        reason_tool_is_decisive=(
            "It converts weeks and local time directly into the exact "
            "reminder_timestamp required by add_reminder."
        ),
        known_failure_mechanisms_addressed=(
            "week_delta_to_day_offset_arithmetic",
            "timestamp_not_final_answer_ready",
        ),
        shortfall_cluster_evidence=(
            "Broad60 confirmed-bucket core showed regressions on add_reminder_content_and_week_delta variants.",
            "Reminder CRUD confirm100 showed timestamp helpers are naturally adopted and outcome-positive downstream.",
        ),
        final_state_preservation_plan=(
            "The helper is pure and returns kwargs; the actor still must call "
            "the original add_reminder or modify_reminder side-effect tool."
        ),
        grading_accounting_note="Original side-effect route remains visible through add_reminder/modify_reminder.",
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Broad60 retained-core run regressed on week-delta reminder scheduling variants.",
            signals=("broad_family_regression", "timestamp_arithmetic_gap"),
            planner_failures=("manual_week_delta_timestamp_conversion",),
        ),
    )
    examples = (
        ToolExample(
            {
                "current_timestamp": 86400.0,
                "week_delta": 1,
                "hour": 9,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
            },
            _week_delta_expected(86400.0, 1, 9, 30, 0.0),
        ),
        ToolExample(
            {
                "current_timestamp": 1777687768.0,
                "week_delta": 2,
                "hour": 17,
                "minute": 0,
                "local_utc_offset_hours": -4.0,
            },
            _week_delta_expected(1777687768.0, 2, 17, 0, -4.0),
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 86400.0,
                "week_delta": -1,
                "hour": 9,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
            },
            {
                "ok": False,
                "timestamp": 0.0,
                "reminder_timestamp": 0.0,
                "day_offset": 0,
                "add_reminder_kwargs": {},
                "reason": "invalid_week_delta_or_time",
                "final_answer_recommendation": "abstain:invalid_reminder_time",
            },
            negative_applicability=True,
        ),
    )
    return _entry(
        GeneratedTool(spec=spec, code=WEEK_DELTA_CODE),
        examples,
        "add_reminder_content_and_week_delta_and_time",
    )


def _weekday_delta_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="weekday_delta_time_to_timestamp",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description=(
            "Reminder scheduling helper for requests like 'next Tuesday at 8 AM' "
            "or 'two Fridays from now'. After get_current_timestamp returns the "
            "current time, call this to resolve the weekday and local time into "
            "a reminder_timestamp. Pure helper; no side effects."
        ),
        inputs=(
            ToolInput(
                "current_timestamp",
                "float",
                "Current Unix timestamp from get_current_timestamp.",
            ),
            ToolInput(
                "target_weekday",
                "str",
                "Target weekday name, e.g. monday, tue, friday.",
            ),
            ToolInput(
                "week_delta",
                "int",
                "Whole weeks after the upcoming occurrence. Use 0 for the next occurrence, 1 for the following week.",
            ),
            ToolInput("hour", "int", "Target local hour in 24-hour time."),
            ToolInput("minute", "int", "Target local minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local UTC offset; use -4 for ToolSandbox unless another offset is known.",
            ),
            ToolInput(
                "include_today",
                "bool",
                "Whether a same-day weekday match is allowed. Use false for 'next <weekday>'.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "timestamp": {"type": "number"},
                "reminder_timestamp": {"type": "number"},
                "day_offset": {"type": "integer"},
                "weekday_index": {"type": "integer"},
                "add_reminder_kwargs": {"type": "object"},
                "reason": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
            "required": [
                "ok",
                "timestamp",
                "reminder_timestamp",
                "day_offset",
                "weekday_index",
                "reason",
            ],
        },
        positive_triggers=(
            "add_reminder_content_and_weekday_delta_and_time",
            "weekday_delta",
            "next monday",
            "next tuesday",
            "next friday",
        ),
        negative_triggers=(
            "recency_latest",
            "search_reminder_with_recency",
            "insufficient_information",
            "week_delta_and_time",
        ),
        preserves_side_effect_tools=("add_reminder", "modify_reminder"),
        required_original_tool_calls=("get_current_timestamp", "add_reminder"),
        abstain_behavior="Return ok false and no add_reminder_kwargs for unknown weekday/time inputs.",
        generalization_rationale=(
            "Weekday reminder creation recurs across base and distraction "
            "variants; resolving the next matching local weekday is a narrow "
            "deterministic arithmetic step."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=(
            "add_reminder_content_and_weekday_delta_and_time",
            "add_reminder_content_and_weekday_delta_and_time_10_distraction_tools",
        ),
        reason_tool_is_decisive=(
            "It removes ambiguous weekday arithmetic and returns the exact "
            "reminder_timestamp required by add_reminder."
        ),
        known_failure_mechanisms_addressed=(
            "weekday_to_day_offset_arithmetic",
            "timestamp_not_final_answer_ready",
        ),
        shortfall_cluster_evidence=(
            "Broad60 confirmed-bucket core showed regressions on add_reminder_content_and_weekday_delta variants.",
            "Reminder CRUD confirm100 showed timestamp helpers are naturally adopted and outcome-positive downstream.",
        ),
        final_state_preservation_plan=(
            "The helper is pure and returns kwargs; the actor still must call "
            "the original add_reminder or modify_reminder side-effect tool."
        ),
        grading_accounting_note="Original side-effect route remains visible through add_reminder/modify_reminder.",
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Broad60 retained-core run regressed on weekday-delta reminder scheduling variants.",
            signals=("broad_family_regression", "timestamp_arithmetic_gap"),
            planner_failures=("manual_weekday_timestamp_conversion",),
        ),
    )
    examples = (
        ToolExample(
            {
                "current_timestamp": 86400.0,
                "target_weekday": "monday",
                "week_delta": 0,
                "hour": 9,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
                "include_today": False,
            },
            _weekday_delta_expected(86400.0, 0, 0, 9, 30, 0.0, False),
        ),
        ToolExample(
            {
                "current_timestamp": 1777687768.0,
                "target_weekday": "friday",
                "week_delta": 1,
                "hour": 17,
                "minute": 0,
                "local_utc_offset_hours": -4.0,
                "include_today": False,
            },
            _weekday_delta_expected(1777687768.0, 4, 1, 17, 0, -4.0, False),
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 86400.0,
                "target_weekday": "nonday",
                "week_delta": 0,
                "hour": 9,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
                "include_today": False,
            },
            {
                "ok": False,
                "timestamp": 0.0,
                "reminder_timestamp": 0.0,
                "day_offset": 0,
                "add_reminder_kwargs": {},
                "reason": "invalid_weekday_or_time",
                "final_answer_recommendation": "abstain:invalid_reminder_time",
            },
            negative_applicability=True,
        ),
    )
    return _entry(
        GeneratedTool(spec=spec, code=WEEKDAY_DELTA_CODE),
        examples,
        "add_reminder_content_and_weekday_delta_and_time",
    )


def _mark_variant(entry: dict[str, Any], note: str) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    existing = str(spec.get("adoption_experiment_note", "")).strip()
    spec["adoption_experiment_note"] = f"{existing}; {note}" if existing else note
    return updated


def main() -> None:
    core_tools = _load_tools(CORE_REGISTRY)
    schedule_tools = {
        "week_delta_time_to_timestamp": _week_delta_tool(),
        "weekday_delta_time_to_timestamp": _weekday_delta_tool(),
    }
    variants = {
        "scheduling_precision_only_pack": schedule_tools,
        "confirmed_bucket_core_plus_schedule_precision_pack": {
            **{
                name: _mark_variant(entry, "scheduling_precision_broad_candidate")
                for name, entry in core_tools.items()
            },
            **schedule_tools,
        },
    }

    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "source_registry": str(CORE_REGISTRY),
        "source_registry_sha256": _sha256(CORE_REGISTRY.read_bytes()),
        "objective": (
            "Repair broad reminder scheduling regressions with two narrow "
            "deterministic timestamp helpers for week and weekday deltas."
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
