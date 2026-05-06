"""Artifact-backed capability observations for online tool birth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.experiments.v2_flags import (
    DEPENDENCY_LOGIC,
    MEDIUM_GRAIN_SKILLS,
    feature_enabled,
)
from sage_ts.generation.tool_spec import StructuredInadequacyEvidence, ToolFamily
from sage_ts.validation.sandbox_validator import ToolExample
from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario


def _similarity(result: dict[str, Any]) -> float:
    value = result.get("similarity", 0.0)
    try:
        return float(value) if isinstance(value, (int, float, str)) else 0.0
    except ValueError:
        return 0.0


def _is_latest_record_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith(("modify_contact_with_message_recency",))


def _is_message_search_window_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith("modify_contact_with_message_recency")


def _is_message_recency_extreme_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith(
        (
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
        )
    )


def _is_contact_constraint_scenario(scenario_name: str) -> bool:
    return "ambiguous" not in scenario_name and scenario_name.startswith(
        ("update_contact_relationship_with_relationship",)
    )


def _is_visible_record_constraint_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "remove_contact_by_phone",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
            "update_contact_relationship_with_relationship",
        )
    )


def _is_recency_action_target_scenario(scenario_name: str) -> bool:
    if "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "modify_contact_with_message_recency",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
        )
    )


def _is_post_selection_side_effect_prep_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "remove_contact_by_phone",
            "update_contact_relationship_with_relationship",
            "modify_contact_with_message_recency",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
        )
    )


def _is_medium_grain_constraint_action_scenario(scenario_name: str) -> bool:
    if (
        "ambiguous" in scenario_name
        or "insufficient_information" in scenario_name
        or not feature_enabled(MEDIUM_GRAIN_SKILLS)
    ):
        return False
    return scenario_name.startswith(
        (
            "remove_contact_by_phone",
            "update_contact_relationship_with_relationship",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
            "search_name_with_relationship",
        )
    )


def _is_direct_service_precondition_scenario(scenario_name: str) -> bool:
    return "insufficient_information" not in scenario_name and scenario_name.startswith(
        (
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "wifi_off",
            "cellular_off",
            "send_message_with_contact_content_cellular_off",
        )
    )


def _is_reminder_optional_location_argument_scenario(scenario_name: str) -> bool:
    return (
        "insufficient_information" not in scenario_name
        and scenario_name.startswith("add_reminder_content_and_")
        and "_time" in scenario_name
    )


def _reminder_optional_location_argument_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_reminder_creation_args",
        observation=(
            "Reminder creation tasks with relative date/time and optional location "
            "repeatedly fail after the agent has enough visible information to call "
            "the original add_reminder ToolSandbox side-effect tool. The missing "
            "capability is not another side effect; it is deterministic argument "
            "preparation. Generate a small trace-compatible helper named "
            "prepare_reminder_creation_args and use it immediately before "
            "add_reminder as the normal final step once reminder content and time "
            "are known. Inputs: content, "
            "resolved_reminder_timestamp, current_timestamp, day_offset, hour, "
            "minute, local_utc_offset_hours, location_requested, location_required, "
            "location_available, latitude, longitude, and location_lookup_failed. "
            "Return a dict with add_reminder_kwargs, should_call_add_reminder, "
            "abstain_reason, location_status, and timestamp_source. "
            "add_reminder_kwargs must be directly splattable into the original "
            "ToolSandbox add_reminder(content, reminder_timestamp, latitude, "
            "longitude) side-effect tool. If resolved_reminder_timestamp is "
            "present, use it directly. Otherwise use local-day timestamp "
            "arithmetic, not current_timestamp plus raw hours. Formula: "
            "offset_seconds = local_utc_offset_hours * 3600; local_seconds = "
            "current_timestamp + offset_seconds; local_midnight = floor("
            "local_seconds / 86400) * 86400; reminder_timestamp = local_midnight "
            "+ day_offset * 86400 - offset_seconds + hour * 3600 + minute * 60. "
            "Prefer resolved_reminder_timestamp whenever current benchmark "
            "timestamp context already makes the reminder time clear. In "
            "ToolSandbox reminder creation, plain relative times like 'tomorrow "
            "at 5 PM' mean local device time by default, so do not ask the user "
            "for timezone or UTC offset again unless the request is truly "
            "ambiguous. "
            "Set location_requested to true when the user mentioned a location "
            "that you would like to attach if resolution succeeds. Set "
            "location_required to true only when the user explicitly requires "
            "the created reminder to include a location. "
            "If optional location is unavailable or a lookup already failed, do "
            "not invent coordinates: include latitude None and longitude None in "
            "add_reminder_kwargs, set location_status to omitted_optional, and "
            "still allow the original add_reminder call. If an optional location "
            "is still being chosen or refined and lookup has not failed yet, "
            "abstain with location_status lookup_pending and do not call "
            "add_reminder yet instead of creating the reminder prematurely. "
            "After that optional location is resolved or explicitly skipped, "
            "call this helper again before add_reminder. If location is "
            "explicitly required but "
            "unresolved, abstain instead of retrying blindly. This "
            "helper must preserve the original ToolSandbox add_reminder call by "
            "preparing arguments only; it must not create or modify reminders "
            "itself."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "content": "Buy tickets",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Buy tickets",
                        "reminder_timestamp": 147600.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Team meeting",
                    "resolved_reminder_timestamp": 1777500000.0,
                    "current_timestamp": 1777428906.0,
                    "day_offset": 0,
                    "hour": 0,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Team meeting",
                        "reminder_timestamp": 1777500000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "resolved",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "content": "Meet at park",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 14,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": True,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "required_location_unresolved",
                    "location_status": "required_missing",
                    "timestamp_source": "relative_fields",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 1777687768.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": (
                        "optional_location_lookup_pending_do_not_call_add_reminder"
                    ),
                    "location_status": "lookup_pending",
                    "timestamp_source": "resolved",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="reminder_creation_argument_preparation_failure",
        inadequacy_signals=(
            "optional_info_treated_as_required",
            "visible_raw_data_lacking_deterministic_transform",
        ),
        visible_data_gaps=(
            "relative day/time and optional location must be converted into add_reminder kwargs",
        ),
    )


def _message_search_window_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:message_search_time_window",
        observation=(
            "Contact/message recency tasks sometimes fail before ranking because "
            "search_messages requires a concrete criterion. Prior experiments showed "
            "that a bounds-only message_search_time_window helper is too thin: it "
            "can be accepted and called but does not reliably improve final task "
            "completion. Treat this as diagnostic shortfall evidence only. "
            "Claim-grade generation for these tasks should prefer a composite "
            "search/filter or record-selection candidate that preserves the original "
            "search_messages call and then deterministically selects or prepares the "
            "downstream action from visible records."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {
                    "anchor_timestamp": 864000.0,
                    "lookback_days": 2,
                },
                {
                    "creation_timestamp_lowerbound": 691200.0,
                    "creation_timestamp_upperbound": 864000.0,
                },
            ),
            ToolExample(
                {
                    "anchor_timestamp": 1000.0,
                    "lookback_days": 0,
                },
                {
                    "creation_timestamp_lowerbound": 1000.0,
                    "creation_timestamp_upperbound": 1000.0,
                },
            ),
            ToolExample(
                {
                    "anchor_timestamp": 1000.0,
                    "lookback_days": -5,
                },
                {
                    "creation_timestamp_lowerbound": 1000.0,
                    "creation_timestamp_upperbound": 1000.0,
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=False,
        reason="diagnostic_only_bounds_helper_low_value",
        inadequacy_signals=(
            "repeated_failed_tool_call",
            "visible_raw_data_lacking_deterministic_transform",
        ),
        failed_tool_calls=("search_messages",),
        visible_data_gaps=("missing benchmark-compatible timestamp window",),
    )


def _latest_record_selection_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_record_by_timestamp_extreme",
        observation=(
            "Repeated latest-result scenarios require choosing the timestamp "
            "extreme from a visible list returned by search tools. Agents can "
            "compute valid search bounds but still select or report the wrong "
            "candidate. Generate the shared deterministic search/filter/ranking "
            "helper named select_record_by_timestamp_extreme rather than a "
            "latest-only variant. Inputs: records as a list of record "
            "dictionaries copied directly from the visible search-tool result, "
            "timestamp_key as the timestamp field to compare, and selection_mode as "
            "either 'latest' or 'oldest'. Ignore records missing a numeric "
            "timestamp. The spec.output_schema must be a JSON Schema object with "
            "properties selected_record, selected_index, selected_timestamp, and "
            "abstain_reason. Return a dict with those keys; selected_record must be "
            "the full visible record. Return selected_record {} plus a non-empty "
            "abstain_reason when no record has a numeric timestamp, selection_mode "
            "is invalid, or timestamp ties make the requested extreme ambiguous. "
            "The spec.required_original_tool_calls must include search_messages "
            "for message recency tasks and search_reminder for reminder recency "
            "tasks when applicable. The spec.preserves_side_effect_tools must "
            "include those original search tools and any downstream original "
            "ToolSandbox side-effect tools that will consume the selected record, "
            "such as modify_contact or modify_reminder. This helper must only "
            "select from visible records passed as inputs; it must never search, "
            "modify, send, or create records itself."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {"content": "older", "creation_timestamp": 10.0},
                        {"content": "newer", "creation_timestamp": 20.0},
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {"content": "newer", "creation_timestamp": 20.0},
                    "selected_index": 1,
                    "selected_timestamp": 20.0,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {"content": "missing"},
                        {"content": "old", "reminder_timestamp": 5.0},
                        {"content": "new", "reminder_timestamp": 15.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {"content": "new", "reminder_timestamp": 15.0},
                    "selected_index": 2,
                    "selected_timestamp": 15.0,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "records": [{"content": "none"}],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_timestamp": 0.0,
                    "abstain_reason": "no_numeric_timestamp",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"content": "a", "creation_timestamp": 20.0},
                        {"content": "b", "creation_timestamp": 20.0},
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_timestamp": 20.0,
                    "abstain_reason": "ambiguous_tie",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="repeated_latest_record_selection_failure",
        inadequacy_signals=("wrong_selected_record",),
        visible_data_gaps=(
            "visible candidate list requires deterministic extreme selection",
        ),
    )


def _days_between_timestamps_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:days_between_timestamps",
        observation=(
            "Holiday/calendar tasks repeatedly require computing the same "
            "deterministic timestamp difference that the reduced base toolset no "
            "longer exposes through timestamp_diff. The agent can still call "
            "get_current_timestamp and search_holiday, but it needs a small "
            "value-producing helper named days_between_timestamps that accepts "
            "timestamp_0 and timestamp_1 floats and returns a dict with integer "
            "days and seconds matching Python datetime timedelta semantics for "
            "timestamp_1 - timestamp_0. This is reusable for future calendar and "
            "deadline-distance tasks and does not require hidden answers."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {"timestamp_0": 0.0, "timestamp_1": 86400.0},
                {"days": 1, "seconds": 0},
            ),
            ToolExample(
                {"timestamp_0": 0.0, "timestamp_1": 90061.0},
                {"days": 1, "seconds": 3661},
            ),
            ToolExample(
                {"timestamp_0": 1000.0, "timestamp_1": 1000.0},
                {"days": 0, "seconds": 0},
            ),
        ),
        generation_allowed=True,
        reason="reduced_base_missing_timestamp_diff_for_calendar_distance",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "holiday timestamp and current timestamp need day-distance computation",
        ),
    )


def _contact_constraint_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_visible_record_by_constraints",
        observation=(
            "Repeated visible-record constraint tasks require selecting exactly one "
            "contact, message, reminder, or generic record from candidates already "
            "returned by original ToolSandbox search/read tools. Generate a "
            "deterministic search/filter helper named "
            "select_visible_record_by_constraints. Inputs: records as a list of "
            "visible record dictionaries, field_name as the explicit visible field "
            "to match, expected_value as the user-provided constraint value, and "
            "return_field as the optional field to extract. Use top-level scalar "
            "inputs instead of an opaque constraints dict so the acting model can "
            "call the helper directly after a search result. Match only visible "
            "candidate data. Normalize phone-like values to digits and compare "
            "strings case-insensitively. Return selected_record, selected_index, "
            "selected_id, value, matched_constraints, tie_candidates, and "
            "abstain_reason. Return an empty selected_record and non-empty "
            "abstain_reason when there are no records, no match, multiple equal "
            "matches, missing required fields, or insufficient constraints. On a "
            "tie, tie_candidates must include every tied visible record, including "
            "the first matching record; selected_record must remain empty. The "
            "spec.required_original_tool_calls must include the original search "
            "tools that produce records such as search_contacts, search_messages, "
            "or search_reminder. The spec.preserves_side_effect_tools must include "
            "those search tools and any downstream original ToolSandbox action "
            "that consumes the selected record, such as modify_contact, "
            "remove_contact, send_message, modify_reminder, or remove_reminder. "
            "This helper only selects from visible records; it must never search, "
            "modify, remove, send, create, or guess before a side-effect action."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "name": "Ada Lovelace",
                            "person_id": "a",
                            "phone_number": "+1 (555) 0100",
                            "relationship": "friend",
                        },
                        {
                            "name": "Grace Hopper",
                            "person_id": "b",
                            "phone_number": "+1 (555) 0200",
                            "relationship": "coworker",
                        },
                    ],
                    "field_name": "phone_number",
                    "expected_value": "15550200",
                    "return_field": "person_id",
                },
                {
                    "selected_record": {
                        "name": "Grace Hopper",
                        "person_id": "b",
                        "phone_number": "+1 (555) 0200",
                        "relationship": "coworker",
                    },
                    "selected_index": 1,
                    "selected_id": "b",
                    "value": "b",
                    "matched_constraints": ["phone_number"],
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "name": "Ada Lovelace",
                            "person_id": "a",
                            "phone_number": "+1 (555) 0100",
                        }
                    ],
                    "field_name": "name",
                    "expected_value": " ada lovelace ",
                    "return_field": "phone_number",
                },
                {
                    "selected_record": {
                        "name": "Ada Lovelace",
                        "person_id": "a",
                        "phone_number": "+1 (555) 0100",
                    },
                    "selected_index": 0,
                    "selected_id": "a",
                    "value": "+1 (555) 0100",
                    "matched_constraints": ["name"],
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "a", "relationship": "friend"},
                        {"person_id": "b", "relationship": "friend"},
                    ],
                    "field_name": "relationship",
                    "expected_value": "friend",
                    "return_field": "person_id",
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "value": "",
                    "matched_constraints": ["relationship"],
                    "tie_candidates": [
                        {"person_id": "a", "relationship": "friend"},
                        {"person_id": "b", "relationship": "friend"},
                    ],
                    "abstain_reason": "ambiguous_multiple_matches",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="repeated_visible_record_constraint_selection_failure",
        inadequacy_signals=("wrong_selected_record", "visible_info_unused"),
        visible_data_gaps=(
            "visible candidates need deterministic constraint matching and ambiguity abstention",
        ),
    )


def _recency_action_target_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_action_target_by_recency",
        observation=(
            "Repeated modify/remove/reply workflows fail after search because the "
            "agent must choose the one visible target record that satisfies recency, "
            "timestamp, and user constraints before calling an original ToolSandbox "
            "side-effect tool. Generate a deterministic search/filter helper named "
            "select_action_target_by_recency. Inputs: records as visible candidate "
            "dictionaries, timestamp_key, selection_mode latest or oldest, "
            "action_type such as modify_contact, modify_reminder, remove_reminder, "
            "or remove_contact, and constraints as an optional dict. The generated "
            "function must treat omitted constraints as {} and {} as no additional "
            "filter. Return "
            "selected_record, selected_index, selected_id, selected_timestamp, "
            "action_type, downstream_tool_name, tie_candidates, and abstain_reason. "
            "Abstain on no records, no numeric timestamp, invalid mode, ties, "
            "constraints not met, or missing target id. The helper must preserve "
            "the original search tool and downstream side-effect tool; it only "
            "selects the target and labels the next action. When exactly one best "
            "record exists, tie_candidates must be empty. selected_id must use the "
            "first available stable id among reminder_id, message_id, person_id, "
            "sender_person_id, recipient_person_id, or id. It must never execute "
            "modify/remove/send/add itself. On a timestamp tie, tie_candidates "
            "must include every record sharing the selected timestamp, including "
            "the first best record; selected_record must remain empty."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "old",
                            "content": "call Sam",
                            "reminder_timestamp": 10.0,
                        },
                        {
                            "reminder_id": "new",
                            "content": "call Sam",
                            "reminder_timestamp": 20.0,
                        },
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "remove_reminder",
                    "constraints": {"content": "call Sam"},
                },
                {
                    "selected_record": {
                        "reminder_id": "new",
                        "content": "call Sam",
                        "reminder_timestamp": 20.0,
                    },
                    "selected_index": 1,
                    "selected_id": "new",
                    "selected_timestamp": 20.0,
                    "action_type": "remove_reminder",
                    "downstream_tool_name": "remove_reminder",
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "p1",
                            "creation_timestamp": 30.0,
                        },
                        {
                            "message_id": "m2",
                            "sender_person_id": "p2",
                            "creation_timestamp": 50.0,
                        },
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_contact",
                    "constraints": {},
                },
                {
                    "selected_record": {
                        "message_id": "m2",
                        "sender_person_id": "p2",
                        "creation_timestamp": 50.0,
                    },
                    "selected_index": 1,
                    "selected_id": "m2",
                    "selected_timestamp": 50.0,
                    "action_type": "modify_contact",
                    "downstream_tool_name": "modify_contact",
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"reminder_id": "a", "reminder_timestamp": 20.0},
                        {"reminder_id": "b", "reminder_timestamp": 20.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_reminder",
                    "constraints": {},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 20.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "modify_reminder",
                    "tie_candidates": [
                        {"reminder_id": "a", "reminder_timestamp": 20.0},
                        {"reminder_id": "b", "reminder_timestamp": 20.0},
                    ],
                    "abstain_reason": "ambiguous_timestamp_tie",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="repeated_recency_action_target_selection_failure",
        inadequacy_signals=("wrong_selected_record", "side_effect_target_selection"),
        visible_data_gaps=(
            "visible records need deterministic target selection before side effect",
        ),
        planner_failures=("select target before modify/remove side-effect call",),
    )


def _post_selection_side_effect_args_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_side_effect_args_from_selected_record",
        observation=(
            "Several workflows reach or can deterministically identify the correct "
            "visible target record, but then fail to prepare the exact kwargs for "
            "the original ToolSandbox side-effect call. Generate a compact "
            "composite helper named prepare_side_effect_args_from_selected_record. "
            "Inputs: selected_record, action_type, updates, and user_intent. Return "
            "downstream_tool_name, downstream_tool_kwargs, should_call_tool, and "
            "abstain_reason. For supported actions, copy stable ids from the "
            "selected record into kwargs and merge explicit updates only when the "
            "required fields are present. Preserve the original side-effect tools "
            "modify_contact, remove_contact, modify_reminder, remove_reminder, "
            "send_message, or add_reminder as applicable. Abstain if selected_record "
            "is empty, action_type is unsupported, required ids are missing, updates "
            "are ambiguous, or the user did not provide enough information. This "
            "helper prepares arguments only; it must not perform the side effect. "
            "The generated function should be safe when the acting model omits "
            "optional chaining inputs: use default empty dicts for selected_record "
            "and updates, then abstain unless a previous selector or explicit input "
            "provides the selected record. Remove/delete actions may use updates {}. "
            "Modify/update actions must abstain unless updates contains at least one "
            "actual field to change."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "selected_record": {"person_id": "p1", "name": "Ada"},
                    "action_type": "modify_contact",
                    "updates": {"relationship": "friend"},
                    "user_intent": "update relationship",
                },
                {
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p1",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "selected_record": {"reminder_id": "r1", "content": "old"},
                    "action_type": "remove_reminder",
                    "updates": {},
                    "user_intent": "remove selected reminder",
                },
                {
                    "downstream_tool_name": "remove_reminder",
                    "downstream_tool_kwargs": {"reminder_id": "r1"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "selected_record": {},
                    "action_type": "modify_reminder",
                    "updates": {"content": "new"},
                    "user_intent": "modify selected reminder",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "missing_selected_record",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="post_selection_side_effect_argument_preparation_failure",
        inadequacy_signals=("side_effect_argument_preparation_failure",),
        visible_data_gaps=(
            "selected record id and explicit updates must become downstream kwargs",
        ),
        planner_failures=("prepare kwargs before original side-effect tool call",),
    )


def _constraint_to_action_planner_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:constraint_to_action_planner",
        observation=(
            "A medium-grain shortfall cluster spans contact/message constraint "
            "selection, visible-record resolution, and safe downstream action "
            "planning. Small selectors were valid but naturally uncalled, and "
            "side-effect-only preparers were too brittle because they required a "
            "separately selected record. Generate a deterministic medium-grain "
            "composite helper named constraint_to_action_planner that accepts "
            "simple callable inputs: records list copied directly from a visible "
            "search/get result, match_field string, match_value string, action_type "
            "string, update_fields dict, and return_field string. It must normalize "
            "record values and constraints internally, select exactly one visible "
            "record when unambiguous, detect ties, and prepare the downstream "
            "ToolSandbox kwargs when safe. It must not execute final side-effect "
            "tools. Return selected_record, selected_id, selected_index, value, "
            "downstream_tool_name, downstream_tool_kwargs, should_call_tool, "
            "tie_candidates, abstain_reason, and safety_notes. Supported action "
            "types include answer_field, remove_contact, modify_contact, and "
            "send_message. remove_contact requires person_id; modify_contact "
            "requires person_id plus non-empty update_fields; send_message requires "
            "phone_number and content in update_fields. answer_field should return "
            "the requested return_field value with should_call_tool false. Abstain "
            "on no records, missing match_field/match_value, no match, multiple "
            "equal matches, missing ids, missing update fields, unsupported action, "
            "or insufficient information. This skill compresses search-result "
            "inspection, constraint normalization, target selection, ambiguity "
            "handling, and downstream-kwargs preparation while preserving original "
            "ToolSandbox search and side-effect calls."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "person_id": "p1",
                            "name": "Ada Lovelace",
                            "phone_number": "+1 (555) 0100",
                            "relationship": "friend",
                        },
                        {
                            "person_id": "p2",
                            "name": "Grace Hopper",
                            "phone_number": "+1 (555) 0200",
                            "relationship": "coworker",
                        },
                    ],
                    "match_field": "phone_number",
                    "match_value": "15550200",
                    "action_type": "remove_contact",
                    "update_fields": {},
                    "return_field": "person_id",
                },
                {
                    "selected_record": {
                        "person_id": "p2",
                        "name": "Grace Hopper",
                        "phone_number": "+1 (555) 0200",
                        "relationship": "coworker",
                    },
                    "selected_id": "p2",
                    "selected_index": 1,
                    "value": "p2",
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "p2"},
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call downstream ToolSandbox side-effect next",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "person_id": "p1",
                            "name": "Ada Lovelace",
                            "phone_number": "+1 (555) 0100",
                            "relationship": "coworker",
                        }
                    ],
                    "match_field": "name",
                    "match_value": "ada lovelace",
                    "action_type": "modify_contact",
                    "update_fields": {"relationship": "friend"},
                    "return_field": "person_id",
                },
                {
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Ada Lovelace",
                        "phone_number": "+1 (555) 0100",
                        "relationship": "coworker",
                    },
                    "selected_id": "p1",
                    "selected_index": 0,
                    "value": "p1",
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p1",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call downstream ToolSandbox side-effect next",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "person_id": "p1",
                            "name": "Ada Lovelace",
                            "phone_number": "+1 (555) 0100",
                        }
                    ],
                    "match_field": "name",
                    "match_value": "ada lovelace",
                    "action_type": "answer_field",
                    "update_fields": {},
                    "return_field": "phone_number",
                },
                {
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Ada Lovelace",
                        "phone_number": "+1 (555) 0100",
                    },
                    "selected_id": "p1",
                    "selected_index": 0,
                    "value": "+1 (555) 0100",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "answer from value; no side effect needed",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "p1", "relationship": "friend"},
                        {"person_id": "p2", "relationship": "friend"},
                    ],
                    "match_field": "relationship",
                    "match_value": "friend",
                    "action_type": "modify_contact",
                    "update_fields": {"relationship": "coworker"},
                    "return_field": "person_id",
                },
                {
                    "selected_record": {},
                    "selected_id": "",
                    "selected_index": -1,
                    "value": "",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [
                        {"person_id": "p1", "relationship": "friend"},
                        {"person_id": "p2", "relationship": "friend"},
                    ],
                    "abstain_reason": "ambiguous_multiple_matches",
                    "safety_notes": "do not guess before side-effect action",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="medium_grain_constraint_to_action_workflow_failure",
        inadequacy_signals=(
            "visible_info_unused",
            "wrong_selected_record",
            "side_effect_argument_preparation_failure",
        ),
        visible_data_gaps=(
            "visible records plus scalar constraints must become a safe target and downstream kwargs",
        ),
        planner_failures=(
            "chain search result inspection, constraint matching, ambiguity handling, and action prep",
        ),
    )


def _stock_symbol_extraction_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:extract_stock_symbol",
        observation=(
            "Stock lookup scenarios repeatedly require extracting the benchmark "
            "answer field from a visible search_stock result. The base tool can "
            "return a dictionary with symbol values such as 'NASDAQ:AAPL' or "
            "'AAPL', but agents sometimes fail to normalize and report the symbol "
            "only. Generate a small deterministic helper named extract_stock_symbol. "
            "Input: stock_payload dict returned by search_stock. Return the symbol "
            "string with any exchange prefix removed. Abstain with an empty string "
            "if the payload does not contain a usable string symbol."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample({"stock_payload": {"symbol": "NASDAQ:AAPL"}}, "AAPL"),
            ToolExample({"stock_payload": {"symbol": "AAPL"}}, "AAPL"),
            ToolExample(
                {"stock_payload": {"name": "Apple"}},
                "",
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="stock_symbol_field_extraction_failure",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "visible stock payload requires deterministic symbol extraction",
        ),
    )


def _is_external_answer_extraction_scenario(scenario_name: str) -> bool:
    if "insufficient_information" in scenario_name:
        return False
    if "stock_symbol" in scenario_name or "low_battery" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "find_distance_with_location_name",
            "find_address_with_lat_lon",
            "find_phone_number_with_location_name",
            "find_temperature",
            "find_temperature_f_with_location",
            "convert_currency",
            "convert_currency_canonicalize",
        )
    )


def _external_service_answer_extraction_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:extract_service_answer_field",
        observation=(
            "External lookup and conversion tasks repeatedly expose a visible "
            "ToolSandbox result payload, but the agent can still lose task "
            "completion by manually copying, normalizing, or selecting the wrong "
            "answer field from that payload. Generate a deterministic answer-only "
            "helper named extract_service_answer_field. Input: service_payload dict "
            "copied from a visible result row or dictionary returned by an original "
            "ToolSandbox lookup/conversion tool. Return a dict with answer_value, "
            "answer_kind, answer_unit, and abstain_reason. Recognize common visible "
            "fields such as phone_number, address, current_temperature, "
            "temperature, distance, converted_amount, convertedAmount, amount, and "
            "value. Return answer_value as a string and preserve any visible unit "
            "field as answer_unit when present. Abstain with an empty answer_value "
            "when no supported scalar answer field is present. This helper must "
            "not call external services itself, must not perform side effects, and "
            "must not replace the original ToolSandbox lookup or conversion call; "
            "it only extracts the final answer from visible output after that "
            "original call returns. Its required_original_tool_calls and "
            "preserves_side_effect_tools must use concrete ToolSandbox producer "
            "names from this list only: search_location_around_lat_lon, "
            "search_weather_around_lat_lon, search_lat_lon, "
            "calculate_lat_lon_distance, convert_currency, and unit_conversion. "
            "Do not invent placeholder producer names such as search_service_payload."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {
                    "service_payload": {
                        "name": "Main Branch",
                        "phone_number": "+1 (555) 0100",
                    }
                },
                {
                    "answer_value": "+1 (555) 0100",
                    "answer_kind": "phone_number",
                    "answer_unit": "",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "service_payload": {
                        "current_temperature": 21.5,
                        "temperature_unit": "Celsius",
                    }
                },
                {
                    "answer_value": "21.5",
                    "answer_kind": "current_temperature",
                    "answer_unit": "Celsius",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"service_payload": {"address": "1 Main St, Springfield"}},
                {
                    "answer_value": "1 Main St, Springfield",
                    "answer_kind": "address",
                    "answer_unit": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {"service_payload": {"name": "Main Branch", "category": "library"}},
                {
                    "answer_value": "",
                    "answer_kind": "",
                    "answer_unit": "",
                    "abstain_reason": "no_supported_answer_field",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="visible_external_payload_answer_field_extraction_failure",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "visible service result payload contains answer fields requiring deterministic extraction",
        ),
        failed_tool_calls=(
            "search_location_around_lat_lon",
            "search_weather_around_lat_lon",
            "search_lat_lon",
            "calculate_lat_lon_distance",
            "convert_currency",
            "unit_conversion",
        ),
        final_answer_route_mismatch=True,
    )


def _next_service_tool_call_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="state_precondition:next_service_tool_call",
        observation=(
            "Direct service-precondition tasks repeatedly require deciding the "
            "single next original ToolSandbox tool call needed to enable wifi, "
            "cellular, or location service. Existing advisory state helpers are "
            "trace-misaligned because they return informal action strings instead "
            "of benchmark tool names and arguments. Generate a deterministic "
            "state-precondition helper named next_service_tool_call. Inputs: "
            "target_service string ('wifi', 'cellular', or 'location'), "
            "wifi_enabled bool, cellular_enabled bool, location_service_enabled "
            "bool, and low_battery_mode bool. The spec.output_schema must be a "
            "JSON Schema object with properties tool_name, arguments, should_call, "
            "and reason. tool_name must have exactly this enum: '', "
            "'set_wifi_status', 'set_cellular_service_status', "
            "'set_location_service_status', and 'set_low_battery_mode_status'. "
            "Do not omit should_call. Return a dict with ready bool, tool_name "
            "string, arguments dict, should_call bool, and reason string. If the "
            "target service is already enabled, return ready True, empty "
            "tool_name, empty arguments, should_call False, and a reason. If "
            "low_battery_mode is true and the "
            "target is not enabled, return tool_name 'set_low_battery_mode_status' "
            "with arguments {'on': False} and should_call True. Otherwise return the exact original "
            "ToolSandbox setter: wifi -> set_wifi_status, cellular -> "
            "set_cellular_service_status, location -> set_location_service_status, "
            "always with arguments {'on': True} and should_call True. This helper is for one chosen "
            "target service at a time; it must not encourage calling parallel or "
            "alternative service flows for unrelated targets. After the caller "
            "uses the returned ToolSandbox tool call, it should report only the "
            "final state of that chosen target service unless the user explicitly "
            "asks to broaden scope. For unknown target services, return ready "
            "False, empty tool_name, empty arguments, should_call False, and a "
            "brief reason. negative_triggers must include already_ready, "
            "unknown_target_service, and insufficient_state. "
            "spec.required_original_tool_calls and spec.preserves_side_effect_tools "
            "must include the relevant original setter tools."
        ),
        allowed_families=(str(ToolFamily.STATE_PRECONDITION_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "target_service": "wifi",
                    "wifi_enabled": False,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": True,
                },
                {
                    "ready": False,
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "wifi cannot be enabled while low battery mode is on",
                },
            ),
            ToolExample(
                {
                    "target_service": "cellular",
                    "wifi_enabled": True,
                    "cellular_enabled": False,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": False,
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "cellular is disabled and must be enabled first",
                },
            ),
            ToolExample(
                {
                    "target_service": "location",
                    "wifi_enabled": True,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": True,
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "location is already enabled",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="trace_compatible_service_precondition_next_tool_call",
        inadequacy_signals=("failed_base_tool_with_deterministic_fallback",),
        failed_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
        ),
    )


def _tool_allow_list(scenario: Scenario) -> tuple[str, ...]:
    tools = getattr(scenario.starting_context, "tool_allow_list", None) or ()
    return tuple(str(tool) for tool in tools)


def _generic_precondition_tools(scenario: Scenario) -> tuple[str, ...]:
    return tuple(
        tool
        for tool in _tool_allow_list(scenario)
        if tool.startswith("set_")
        or tool.startswith("enable_")
        or tool.startswith("disable_")
    )


def _generic_downstream_action_tools(scenario: Scenario) -> tuple[str, ...]:
    return tuple(
        tool
        for tool in _tool_allow_list(scenario)
        if tool.startswith(("send_", "search_", "modify_", "add_"))
    )


def _dependency_precondition_observation(
    scenario_name: str,
    scenario: Scenario,
) -> CapabilityObservation:
    precondition_tools = _generic_precondition_tools(scenario)
    downstream_tools = _generic_downstream_action_tools(scenario)
    tool_enum = ("", *precondition_tools[:6])
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="state_precondition:dependency_precondition_tool_call",
        observation=(
            "A repeated dependency-bundle shortfall is present: the task exposes "
            "original ToolSandbox precondition setters plus downstream action tools, "
            "but the agent must infer which concrete precondition action is needed "
            "before the downstream action can succeed. Generate a deterministic "
            "state dependency planner that accepts concrete top-level visible "
            "state fields such as service_ready, blocker_active, blocker_kind, "
            "target_action, and blocked_reason. Do not require an opaque "
            "dependency_state dict. Return one original "
            "ToolSandbox precondition tool_name plus arguments, or abstains when "
            "the state is already ready, unknown, or ambiguous. It must preserve "
            "the returned original precondition tool call and must not perform the "
            "downstream task itself."
        ),
        allowed_families=(str(ToolFamily.STATE_PRECONDITION_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "service_ready": False,
                    "blocker_active": True,
                    "blocker_kind": "low_battery_mode",
                    "target_action": "downstream_action",
                    "blocked_reason": "blocked by active precondition",
                },
                {
                    "tool_name": tool_enum[1] if len(tool_enum) > 1 else "",
                    "arguments": {"on": False},
                    "should_call": bool(len(tool_enum) > 1),
                    "reason": "disable active blocker before downstream action",
                },
            ),
            ToolExample(
                {
                    "service_ready": False,
                    "blocker_active": False,
                    "blocker_kind": "",
                    "target_action": "downstream_action",
                    "blocked_reason": "service disabled",
                },
                {
                    "tool_name": (
                        tool_enum[2]
                        if len(tool_enum) > 2
                        else tool_enum[1]
                        if len(tool_enum) > 1
                        else ""
                    ),
                    "arguments": {"on": True},
                    "should_call": bool(len(tool_enum) > 1),
                    "reason": "enable missing dependency before downstream action",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "service_ready": True,
                    "blocker_active": False,
                    "blocker_kind": "",
                    "target_action": "downstream_action",
                    "blocked_reason": "",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "dependency already ready",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=bool(precondition_tools),
        reason="generic_dependency_precondition_bundle",
        inadequacy_signals=(
            "failed_base_tool_with_deterministic_fallback",
            "precondition_bundle_before_downstream_action",
        ),
        failed_tool_calls=precondition_tools,
        planner_failures=("choose one precondition setter before downstream action",),
    )


@dataclass(frozen=True)
class CapabilityObservation:
    scenario_name: str
    canonical_key: str
    observation: str
    allowed_families: tuple[str, ...]
    validation_examples: tuple[ToolExample, ...]
    generation_allowed: bool
    reason: str
    inadequacy_signals: tuple[str, ...] = ()
    failed_tool_calls: tuple[str, ...] = ()
    repeated_failed_tool_calls: tuple[str, ...] = ()
    visible_data_gaps: tuple[str, ...] = ()
    planner_failures: tuple[str, ...] = ()
    final_answer_route_mismatch: bool = False
    # "heuristic" = scenario-name prefix only; "transcript_verified" = signal confirmed in transcript
    evidence_source: str = "heuristic"

    def to_inadequacy_evidence(self) -> StructuredInadequacyEvidence:
        return StructuredInadequacyEvidence(
            summary=self.observation,
            signals=self.inadequacy_signals,
            failed_tool_calls=self.failed_tool_calls,
            repeated_failed_tool_calls=self.repeated_failed_tool_calls,
            visible_data_gaps=self.visible_data_gaps,
            planner_failures=self.planner_failures,
            final_answer_route_mismatch=self.final_answer_route_mismatch,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "canonical_key": self.canonical_key,
            "observation": self.observation,
            "allowed_families": list(self.allowed_families),
            "validation_examples": [
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in self.validation_examples
            ],
            "generation_allowed": self.generation_allowed,
            "reason": self.reason,
            "evidence_source": self.evidence_source,
            "inadequacy_evidence": self.to_inadequacy_evidence().to_json(),
        }


def classify_scenario_observations(
    scenario_name: str,
    scenario: Scenario,
    result: dict[str, Any],
) -> tuple[CapabilityObservation, ...]:
    """Classify only narrow, repeated ToolSandbox hard-mode observations."""
    categories = {str(category) for category in scenario.categories}
    similarity = _similarity(result)
    raw_outcome_similarity = result.get("outcome_similarity")
    try:
        outcome_similarity = (
            float(raw_outcome_similarity)
            if isinstance(raw_outcome_similarity, (int, float, str))
            else None
        )
    except ValueError:
        outcome_similarity = None
    route_mismatch = bool(
        outcome_similarity is not None and outcome_similarity > similarity
    )
    if ScenarioCategories.INSUFFICIENT_INFORMATION in scenario.categories:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="insufficient_information",
                observation=(
                    "Scenario is marked insufficient-information; this should be "
                    "stored as abstention/guard evidence, not immediate tool birth."
                ),
                allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
                validation_examples=(),
                generation_allowed=False,
                reason="insufficient_information_observation_only",
                inadequacy_signals=("missing_user_information",),
                planner_failures=("abstain_or_clarify_instead_of_birth",),
            ),
        )

    if similarity < 1.0 and (
        "recency" in scenario_name
        and ScenarioCategories.CANONICALIZATION in scenario.categories
    ):
        # Validation constants: day 10 boundary (all values are exact float arithmetic)
        _ts = float(10 * 86400)  # 864000.0
        _yesterday_start = float(9 * 86400)  # 777600.0
        _today_ts = float(10 * 86400 + 3600)  # 867600.0
        _today_start = float(10 * 86400)  # 864000.0
        observations = [
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="derived_value:recency_timestamp_bounds",
                observation=(
                    "ToolSandbox scenarios repeatedly require converting user-facing "
                    "bounded recency words (yesterday, today, upcoming) into "
                    "Unix timestamp lower/upper bounds to pass to search tools "
                    "(search_reminder, search_messages). The base toolset provides "
                    "get_current_timestamp, timestamp_to_datetime_info, and "
                    "datetime_info_to_timestamp as building blocks but not a single "
                    "recency-to-bounds helper. Agents must make 3+ extra calls and "
                    "are error-prone on day boundary arithmetic."
                ),
                allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
                validation_examples=(
                    ToolExample(
                        {"recency_label": "yesterday", "current_timestamp": _ts},
                        {"lower_bound": _yesterday_start, "upper_bound": _ts},
                    ),
                    ToolExample(
                        {"recency_label": "today", "current_timestamp": _today_ts},
                        {"lower_bound": _today_start, "upper_bound": _today_ts},
                    ),
                ),
                generation_allowed=True,
                reason=f"categories:{','.join(sorted(categories))}",
                inadequacy_signals=(
                    "visible_raw_data_lacking_deterministic_transform",
                ),
                visible_data_gaps=(
                    "bounded recency label must become timestamp lower/upper bounds",
                ),
                final_answer_route_mismatch=route_mismatch,
            )
        ]
        if scenario_name.startswith("modify_reminder_with_recency_latest"):
            observations.append(
                CapabilityObservation(
                    scenario_name=scenario_name,
                    canonical_key="canonicalizer:relative_day_time_timestamp",
                    observation=(
                        "Repeated modify_reminder recency scenarios require turning "
                        "a user-facing relative date/time such as 'tomorrow 5PM' "
                        "into the exact local Unix timestamp passed to "
                        "modify_reminder. In the reduced base toolset the date/time "
                        "decomposition helpers are absent, so agents find the right "
                        "reminder but often write the wrong timestamp. Generate a "
                        "small deterministic canonicalizer named "
                        "relative_day_time_to_timestamp that accepts current_timestamp, "
                        "day_offset, hour, minute, and local_utc_offset_hours. Use "
                        "local_utc_offset_hours=-4 for the current ToolSandbox local "
                        "environment unless another offset is explicitly known."
                    ),
                    allowed_families=(str(ToolFamily.CANONICALIZER),),
                    validation_examples=(
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 1,
                                "hour": 17,
                                "minute": 0,
                                "local_utc_offset_hours": -4,
                            },
                            1777496400.0,
                        ),
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 2,
                                "hour": 8,
                                "minute": 30,
                                "local_utc_offset_hours": -4,
                            },
                            1777552200.0,
                        ),
                    ),
                    generation_allowed=True,
                    reason="repeated_modify_reminder_relative_datetime_failure",
                    inadequacy_signals=(
                        "visible_raw_data_lacking_deterministic_transform",
                    ),
                    visible_data_gaps=(
                        "relative day/time must become exact benchmark timestamp",
                    ),
                    final_answer_route_mismatch=route_mismatch,
                )
            )
        if _is_latest_record_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_recency_action_target_scenario(scenario_name):
            observations.append(_recency_action_target_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        if _is_message_search_window_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_search_window_observation(scenario_name))
        return tuple(observations)

    if similarity < 1.0 and _is_reminder_optional_location_argument_scenario(
        scenario_name
    ):
        return (_reminder_optional_location_argument_observation(scenario_name),)

    if similarity < 1.0 and _is_medium_grain_constraint_action_scenario(scenario_name):
        return (_constraint_to_action_planner_observation(scenario_name),)

    if similarity < 1.0 and (
        _is_latest_record_scenario(scenario_name)
        or _is_message_search_window_scenario(scenario_name)
        or _is_message_recency_extreme_scenario(scenario_name)
    ):
        observations = []
        if _is_latest_record_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_recency_action_target_scenario(scenario_name):
            observations.append(_recency_action_target_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        if _is_message_search_window_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_search_window_observation(scenario_name))
        return tuple(observations)

    if similarity < 1.0 and (
        (
            _is_recency_action_target_scenario(scenario_name)
            or _is_post_selection_side_effect_prep_scenario(scenario_name)
        )
        and not _is_visible_record_constraint_scenario(scenario_name)
    ):
        observations = []
        if _is_recency_action_target_scenario(scenario_name):
            observations.append(_recency_action_target_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and _is_visible_record_constraint_scenario(scenario_name):
        observations = [_contact_constraint_observation(scenario_name)]
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and scenario_name.startswith("find_days_till_holiday"):
        return (_days_between_timestamps_observation(scenario_name),)

    if similarity < 1.0 and scenario_name.startswith(
        "find_stock_symbol_with_company_name"
    ):
        return (_stock_symbol_extraction_observation(scenario_name),)

    if similarity < 1.0 and _is_external_answer_extraction_scenario(scenario_name):
        return (_external_service_answer_extraction_observation(scenario_name),)

    if similarity < 1.0 and _is_direct_service_precondition_scenario(scenario_name):
        observations = [_next_service_tool_call_observation(scenario_name)]
        if feature_enabled(DEPENDENCY_LOGIC) and _generic_precondition_tools(scenario):
            observations.append(
                _dependency_precondition_observation(
                    scenario_name,
                    scenario,
                )
            )
        return tuple(observations)

    if (
        similarity < 1.0
        and feature_enabled(DEPENDENCY_LOGIC)
        and _generic_precondition_tools(scenario)
        and _generic_downstream_action_tools(scenario)
    ):
        return (_dependency_precondition_observation(scenario_name, scenario),)

    if result.get("similarity") == 0:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="failed:unclassified",
                observation=(
                    "Scenario failed, but no narrow repeated SAGE helper class is "
                    "eligible yet."
                ),
                allowed_families=(),
                validation_examples=(),
                generation_allowed=False,
                reason="no_repeated_supported_pattern",
                inadequacy_signals=("no_valid_deterministic_helper_opportunity",),
            ),
        )
    return ()
