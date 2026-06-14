"""Artifact-backed capability observations for online tool birth."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from typing import Any

from sage_ts.experiments.v2_flags import (
    DEPENDENCY_LOGIC,
    MEDIUM_GRAIN_SKILLS,
    feature_enabled,
)
from sage_ts.generation.tool_spec import StructuredInadequacyEvidence, ToolFamily
from sage_ts.validation.sandbox_validator import ToolExample
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    RoleType,
    ScenarioCategories,
)
from tool_sandbox.common.scenario import Scenario

SAFE_ABSTAIN_BIRTH_ENV = "SAGE_ENABLE_SAFE_ABSTAIN_BIRTH"
DIRECT_STATUS_LOOKUP_ENV = "SAGE_ENABLE_DIRECT_STATUS_LOOKUP_TOOL"
DISABLE_SCENARIO_NAME_BIRTH_ENV = "SAGE_DISABLE_SCENARIO_NAME_BIRTH"
SCENARIO_METADATA_POLICY_ENV = "SAGE_SCENARIO_METADATA_POLICY"


@dataclass(frozen=True)
class VisibleTaskContext:
    """Observable task context available before a ToolSandbox run starts."""

    user_request: str
    available_tools: tuple[str, ...]
    signals: tuple[str, ...]
    primary_family_key: str

    def routing_text(self) -> str:
        return " ".join(
            [
                f"request={self.user_request}",
                f"tools={' '.join(self.available_tools)}",
                f"signals={' '.join(self.signals)}",
                f"family={self.primary_family_key}",
            ]
        ).strip()

    def generation_label(self) -> str:
        request = " ".join(self.user_request.split())
        if len(request) > 220:
            request = f"{request[:217]}..."
        return (
            "visible_task_context("
            f"family={self.primary_family_key}; "
            f"signals={','.join(self.signals)}; "
            f"request={request!r})"
        )


def _direct_status_lookup_enabled() -> bool:
    raw = os.environ.get(DIRECT_STATUS_LOOKUP_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off", "disabled"}


def _scenario_name_birth_disabled() -> bool:
    raw = os.environ.get(DISABLE_SCENARIO_NAME_BIRTH_ENV, "").strip().lower()
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    policy = os.environ.get(SCENARIO_METADATA_POLICY_ENV, "").strip().lower()
    return policy in {
        "visible_context",
        "visible-context",
        "visible",
        "no_scenario_names",
        "no-scenario-names",
    }


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


def _is_search_window_or_bounds_scenario(scenario_name: str) -> bool:
    if "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "search_reminder_with_creation_recency_",
            "search_reminder_with_recency_",
            "search_message_with_recency_",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
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


def _is_contact_lookup_query_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "remove_contact_by_phone",
            "search_name_with_relationship",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
        )
    )


def _is_contact_relationship_batch_update_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith("update_contact_relationship_with_relationship")


def _is_contact_update_by_id_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith("update_contact_with_id_and_phone_number")


def _is_add_contact_action_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith("add_contact_with_name_and_phone_number")


def _is_send_message_contact_lookup_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith("send_message_with_contact_content")


def _is_message_counterparty_contact_update_scenario(scenario_name: str) -> bool:
    if "ambiguous" in scenario_name or "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith("modify_contact_with_message_recency")


def _safe_abstain_birth_enabled() -> bool:
    return os.environ.get(SAFE_ABSTAIN_BIRTH_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_action_or_abstain_observation(scenario_name: str) -> CapabilityObservation:
    enabled = _safe_abstain_birth_enabled()
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="validation:prepare_safe_action_or_abstain",
        observation=(
            "Repeated insufficient-information and missing-precondition failures "
            "need a side-effect-free helper that decides whether the actor has "
            "enough visible information and original ToolSandbox affordances to "
            "continue, or must abstain instead of guessing. Generate a deterministic "
            "validation helper named prepare_safe_action_or_abstain. Inputs must be "
            "user_request: str, requested_action: str, target_identifier: str, "
            "required_original_tools: list, available_original_tools: list, and "
            "visible_records_count: int. Return exactly should_abstain, "
            "missing_information, required_original_tools, safe_next_action, "
            "final_answer_recommendation, and abstain_reason. If any required "
            "original ToolSandbox tool is absent from available_original_tools, "
            "set should_abstain true, missing_information to those missing tool "
            "names, safe_next_action to ask_user_or_abstain, and a final answer "
            "recommendation that says the action cannot be completed with the "
            "currently available information/tools. For contact modify/remove "
            "requests, a raw phone number or name is not a safe record id unless "
            "a visible search/helper result resolved it to a stable contact "
            "record. If contact lookup is unavailable, abstain with a precise "
            "missing contact lookup/tool reason instead of a generic answer. If "
            "requested_action is a contact or reminder side-effect and "
            "target_identifier is blank, abstain with missing_target_identifier. "
            "If visible_records_count is greater than 1 and the target is not "
            "unique, abstain for ambiguity. "
            "If required tools are available and a unique target identifier is "
            "present, set should_abstain false, missing_information empty, "
            "safe_next_action continue_with_original_tool, and blank final answer "
            "recommendation. The helper must never call, select, modify, remove, "
            "send, create, or guess records; it only prepares a final abstention "
            "or safe-continue recommendation. The spec must list the original "
            "ToolSandbox calls it protects in both required_original_tool_calls "
            "and preserves_side_effect_tools, including search_contacts, "
            "remove_contact, modify_contact, search_messages, search_reminder, "
            "remove_reminder, modify_reminder, add_reminder, and "
            "send_message_with_phone_number when those actions are supported. "
            "Include positive triggers for "
            "insufficient_information, missing original tool, missing precondition, "
            "missing target, unavailable search tool, and ambiguous target. "
            "Include negative triggers for complete safe requests, known unique "
            "records, and tasks where the original side-effect tool is visible and "
            "all required user information is present."
        ),
        allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": "Remove the contact with phone +15550100",
                    "requested_action": "remove_contact",
                    "target_identifier": "+15550100",
                    "required_original_tools": ["search_contacts"],
                    "available_original_tools": ["remove_contact"],
                    "visible_records_count": 0,
                },
                {
                    "should_abstain": True,
                    "missing_information": ["search_contacts"],
                    "required_original_tools": ["search_contacts"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "I do not have enough information to safely remove the "
                        "contact with phone number +15550100. I would need a "
                        "contact name or person_id, or access to search contacts, "
                        "before I can remove it."
                    ),
                    "abstain_reason": "missing_required_original_tool",
                },
            ),
            ToolExample(
                {
                    "user_request": "Remove the contact with phone +15550100",
                    "requested_action": "remove_contact",
                    "target_identifier": "+15550100",
                    "required_original_tools": ["search_contacts", "remove_contact"],
                    "available_original_tools": ["search_contacts", "remove_contact"],
                    "visible_records_count": 1,
                },
                {
                    "should_abstain": False,
                    "missing_information": [],
                    "required_original_tools": ["search_contacts", "remove_contact"],
                    "safe_next_action": "continue_with_original_tool",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Update that contact",
                    "requested_action": "modify_contact",
                    "target_identifier": "",
                    "required_original_tools": ["modify_contact"],
                    "available_original_tools": ["modify_contact"],
                    "visible_records_count": 0,
                },
                {
                    "should_abstain": True,
                    "missing_information": ["target_identifier"],
                    "required_original_tools": ["modify_contact"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "I do not have enough information to complete the action."
                    ),
                    "abstain_reason": "missing_target_identifier",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=enabled,
        reason=(
            "insufficient_information_safe_abstain_birth_enabled"
            if enabled
            else "insufficient_information_safe_abstain_birth_parked_pending_benchmark_phrasing"
        ),
        inadequacy_signals=(
            "missing_user_information",
            "missing_original_tool_precondition",
            "unsafe_guess_before_side_effect",
        ),
        planner_failures=("abstain_or_clarify_instead_of_guessing",),
        visible_data_gaps=(
            "visible request and available tool list must be converted into a safe abstention decision",
        ),
    )


def _is_direct_service_precondition_scenario(scenario_name: str) -> bool:
    if "insufficient_information" in scenario_name:
        return False
    if scenario_name.startswith(
        (
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "wifi_off",
            "cellular_off",
            "send_message_with_contact_content_cellular_off",
        )
    ):
        return True
    return (
        scenario_name.startswith("add_reminder_content_and_")
        and "location" in scenario_name
        and (
            "low_battery" in scenario_name
            or "wifi_off" in scenario_name
            or "location_service_off" in scenario_name
        )
    )


def _is_device_status_lookup_scenario(scenario_name: str) -> bool:
    if not _direct_status_lookup_enabled():
        return False
    if "insufficient_information" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "get_wifi",
            "get_cellular",
            "get_location",
            "get_low_battery",
        )
    )


def _is_direct_scalar_contact_action_scenario(scenario_name: str) -> bool:
    if "insufficient_information" in scenario_name:
        return False
    if "ambiguous" in scenario_name:
        return False
    return scenario_name.startswith(
        (
            "remove_contact_with_id",
            "send_message_with_phone_number_and_content",
        )
    )


def _device_status_lookup_observation(
    scenario_name: str,
) -> CapabilityObservation:
    getter_tools = (
        "get_wifi_status",
        "get_cellular_service_status",
        "get_location_service_status",
        "get_low_battery_mode_status",
    )
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:plan_device_status_lookup",
        observation=(
            "Read-only device-status tasks need a helper that selects the exact "
            "original ToolSandbox getter for wifi, cellular, location service, "
            "or low-battery mode, then normalizes the visible boolean getter "
            "result into a concise final answer. Generate a deterministic helper "
            "named plan_device_status_lookup. Inputs: user_request and "
            "visible_state_result. Before the getter result is visible, return "
            "should_call true, the matching getter tool_name, and empty arguments. "
            "After a getter result such as True/False is visible, return "
            "should_call false and final_answer_recommendation. The helper must "
            "never call setters or infer hidden state."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": "Can you check whether wifi is on?",
                    "visible_state_result": "",
                },
                {
                    "tool_name": "get_wifi_status",
                    "arguments": {},
                    "should_call": True,
                    "target_service": "wifi",
                    "status_value": False,
                    "status_label": "Wifi",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Is my cellular service on?",
                    "visible_state_result": "True",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "target_service": "cellular",
                    "status_value": True,
                    "status_label": "Cellular service",
                    "final_answer_recommendation": "Cellular service is on.",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Turn on wifi",
                    "visible_state_result": "",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "target_service": "",
                    "status_value": False,
                    "status_label": "",
                    "final_answer_recommendation": "",
                    "abstain_reason": "not_read_only_status_lookup",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="read_only_device_status_lookup_gap",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        failed_tool_calls=getter_tools,
        visible_data_gaps=(
            "read-only device-status request must route through the matching original getter",
        ),
        planner_failures=("status lookup answered without original getter",),
    )


def _is_reminder_optional_location_argument_scenario(scenario_name: str) -> bool:
    return (
        "insufficient_information" not in scenario_name
        and scenario_name.startswith("add_reminder_content_and_")
        and "_time" in scenario_name
        and "weekday_delta" not in scenario_name
        and (
            "week_delta" in scenario_name
            or "_location" in scenario_name
            or "low_battery_mode" in scenario_name
            or "wifi_off" in scenario_name
            or "location_off" in scenario_name
        )
    )


def _is_reminder_location_search_argument_scenario(scenario_name: str) -> bool:
    return (
        "insufficient_information" not in scenario_name
        and scenario_name.startswith("add_reminder_content_and_")
        and "_time" in scenario_name
        and "_location" in scenario_name
    )


def _is_next_weekday_reminder_scenario(scenario_name: str) -> bool:
    return "insufficient_information" not in scenario_name and scenario_name.startswith(
        "add_reminder_content_and_weekday_delta_and_time"
    )


def _plan_device_state_action_sequence_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="state_precondition:plan_device_state_action_sequence",
        observation=(
            "Device-state and downstream blocked-service tasks need a helper that "
            "plans the exact original ToolSandbox setter sequence, not just a "
            "single informal next action. Generate a deterministic helper named "
            "plan_device_state_action_sequence_v3. Inputs: user_request and "
            "visible_state_or_error. Return the first tool_name/arguments to call, "
            "the full action_sequence, a final_response_recommendation, and "
            "continue_original_task_after_sequence so the actor can resume the "
            "original task after clearing wifi/cellular/location/low-battery "
            "preconditions. The helper must never change device state itself; it "
            "only prepares original setter calls."
        ),
        allowed_families=(str(ToolFamily.STATE_PRECONDITION_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": "Turn on wifi",
                    "visible_state_or_error": "wifi is off and low battery mode is on",
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": "set_wifi_on",
                        },
                    ],
                    "final_response_recommendation": "Wifi has been turned on.",
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": (
                        "Add a reminder to buy chocolate milk at Whole Foods."
                    ),
                    "visible_state_or_error": (
                        "PermissionError: Location service is not enabled."
                    ),
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_location_service_status",
                            "arguments": {"on": True},
                            "reason": "set_location_on",
                        },
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": ("enable_wifi_for_downstream_location_search"),
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Send Sam the message hello",
                    "visible_state_or_error": (
                        "cellular service is disabled and low battery mode is on"
                    ),
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_cellular_service_status",
                            "arguments": {"on": True},
                            "reason": "set_cellular_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Send Sam the message hello",
                    "visible_state_or_error": (
                        "cellular service is disabled and low battery mode is off"
                    ),
                },
                {
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "set_cellular_on",
                    "action_sequence": [
                        {
                            "tool_name": "set_cellular_service_status",
                            "arguments": {"on": True},
                            "reason": "set_cellular_on",
                        }
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "What is my contact's phone number?",
                    "visible_state_or_error": "contacts are available",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "no_device_state_target",
                    "action_sequence": [],
                    "final_response_recommendation": "",
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "no_device_state_target",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="device_state_sequence_planning_gap",
        inadequacy_signals=("failed_base_tool_with_deterministic_fallback",),
        failed_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        visible_data_gaps=(
            "visible state/error text must become an original setter sequence",
        ),
        planner_failures=("continue downstream task after state precondition repair",),
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
            "location_available, latitude, longitude, location_lookup_failed, and "
            "optional current_datetime_info from timestamp_to_datetime_info. "
            "Return a dict with add_reminder_kwargs, should_call_add_reminder, "
            "abstain_reason, location_status, and timestamp_source. "
            "add_reminder_kwargs must be directly splattable into the original "
            "ToolSandbox add_reminder(content, reminder_timestamp, latitude, "
            "longitude) side-effect tool. If resolved_reminder_timestamp is "
            "present for an absolute date/time request, use it directly. For "
            "relative local dates such as tomorrow at 5 PM, derive the sandbox "
            "local offset from current_timestamp plus current_datetime_info; do "
            "not trust a guessed UTC offset or add raw hours to the current "
            "timestamp. If an explicit hour is supplied but minute is omitted, "
            "treat minute as 0 for a top-of-hour request. If "
            "current_datetime_info is missing for a relative local "
            "date, abstain and ask the actor to call timestamp_to_datetime_info "
            "on the current timestamp before retrying the generated tool. "
            "If an explicit date/time request has already been resolved to a "
            "timestamp, use that timestamp directly. If no explicit timestamp is "
            "available and the task depends on relative time, require current-time "
            "context instead of treating current_timestamp as the reminder time. "
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
                    "current_datetime_info": {
                        "year": 1970,
                        "month": 1,
                        "day": 1,
                        "hour": 0,
                        "minute": 0,
                        "second": 0,
                    },
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": None,
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
                    "timestamp_source": "current_datetime_info",
                },
            ),
            ToolExample(
                {
                    "content": "Team meeting",
                    "resolved_reminder_timestamp": 1777500000.0,
                    "current_timestamp": 1777428906.0,
                    "current_datetime_info": {},
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
                    "current_datetime_info": {
                        "year": 1970,
                        "month": 1,
                        "day": 1,
                        "hour": 0,
                        "minute": 0,
                        "second": 0,
                    },
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
                    "timestamp_source": "current_datetime_info",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 1777687768.0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 1,
                        "hour": 16,
                        "minute": 49,
                        "second": 28,
                    },
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
                    "timestamp_source": "current_datetime_info",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "buy chocolate milk",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": None,
                    "current_datetime_info": {},
                    "day_offset": None,
                    "hour": None,
                    "minute": None,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": True,
                    "location_available": True,
                    "latitude": 37.3738083,
                    "longitude": -122.0314225,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "missing_time_info",
                    "location_status": "provided",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "buy chocolate milk",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 1780598838.0,
                    "current_datetime_info": {},
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": None,
                    "location_requested": False,
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
                        "missing_current_datetime_info_call_timestamp_to_datetime_info"
                    ),
                    "location_status": "omitted_optional",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1780633200.0,
                    "current_timestamp": 1780612184.0,
                    "current_datetime_info": {},
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -7.0,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": True,
                    "latitude": 37.3738083,
                    "longitude": -122.0314225,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "buy chocolate milk",
                        "reminder_timestamp": 1780633200.0,
                        "latitude": 37.3738083,
                        "longitude": -122.0314225,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "provided",
                    "timestamp_source": "resolved",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 0.0,
                    "current_datetime_info": {
                        "year": 1970,
                        "month": 1,
                        "day": 1,
                        "hour": 0,
                        "minute": 0,
                        "second": 0,
                    },
                    "day_offset": 1,
                    "hour": 17,
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
                        "content": "Buy chocolate milk at Whole Foods",
                        "reminder_timestamp": 1777776000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "resolved",
                },
            ),
            ToolExample(
                {
                    "content": "buy chocolate milk",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 1780597924.689969,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 4,
                        "hour": 11,
                        "minute": 32,
                        "second": 4,
                    },
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "buy chocolate milk",
                        "reminder_timestamp": 1780704000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "current_datetime_info",
                },
                held_out=True,
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


def _location_search_argument_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_location_search_args",
        observation=(
            "Reminder-location tasks repeatedly fail when the user provided a "
            "visible place phrase but the actor drops qualifiers such as street "
            "names or passes placeholder coordinates into the original "
            "search_location_around_lat_lon ToolSandbox lookup. Generate a "
            "deterministic argument-preparation tool named "
            "prepare_location_search_args. Inputs: user_request, optional "
            "location_phrase, latitude, and longitude. Return "
            "search_location_kwargs, should_call_downstream_tool, "
            "downstream_tool_name, downstream_tool_kwargs, location_query, and "
            "abstain_reason. The tool must preserve the full visible place phrase "
            "such as 'Whole Foods on Stevens Creek' and must omit latitude and "
            "longitude when the only values are missing or placeholder 0.0. It "
            "must abstain before location lookup when a reminder request has a "
            "visible place phrase but no visible reminder date/time, because the "
            "actor should ask for the required reminder time before spending "
            "turns on location or device-state prerequisites. It must abstain "
            "when a broad place name has no visible current coordinates, because "
            "the actor should first obtain current coordinates before searching "
            "an unqualified venue name. It "
            "must not search for locations, invent coordinates, or complete the "
            "reminder; the actor must still call the original ToolSandbox "
            "search_location_around_lat_lon and then use only visible returned "
            "coordinates."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": (
                        "Remind me to buy chocolate milk tomorrow 5PM at Whole "
                        "Foods on Stevens Creek."
                    ),
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek",
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": (
                        "Please create a reminder to pick up pasta tomorrow at "
                        "5 PM near Trader Joe's on Market Street."
                    ),
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Trader Joe's on Market Street",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Trader Joe's on Market Street",
                    },
                    "location_query": "Trader Joe's on Market Street",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Whole Foods on Stevens Creek",
                    "location_phrase": "Whole Foods",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek",
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Remind me to buy milk tomorrow at 5 PM.",
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {},
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "location_query": "",
                    "abstain_reason": "missing_location_phrase",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "user_request": "",
                    "location_phrase": "Whole Foods",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {},
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "get_current_location",
                    "downstream_tool_kwargs": {},
                    "location_query": "Whole Foods",
                    "abstain_reason": (
                        "need_current_coordinates_for_broad_location_query"
                    ),
                },
            ),
            ToolExample(
                {
                    "user_request": ("Remind me to buy chocolate milk at Whole Foods."),
                    "location_phrase": "Whole Foods",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {},
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "location_query": "Whole Foods",
                    "abstain_reason": ("missing_reminder_time_before_location_lookup"),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "",
                    "location_phrase": "Whole Foods",
                    "latitude": 37.323,
                    "longitude": -122.039,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods",
                        "latitude": 37.323,
                        "longitude": -122.039,
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods",
                        "latitude": 37.323,
                        "longitude": -122.039,
                    },
                    "location_query": "Whole Foods",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
        ),
        generation_allowed=True,
        reason="location_search_argument_preparation_gap",
        inadequacy_signals=("final_action_argument_preparation",),
        failed_tool_calls=("search_location_around_lat_lon",),
        repeated_failed_tool_calls=("search_location_around_lat_lon",),
        visible_data_gaps=(
            "visible location phrase must become original location-search kwargs",
        ),
        planner_failures=(
            "actor dropped place qualifiers or used placeholder coordinates",
        ),
    )


def _add_contact_argument_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_add_contact_args",
        observation=(
            "Add-contact tasks repeatedly contain the name and phone number in "
            "visible user text, but the actor may search or modify an existing "
            "record instead of preparing the original add_contact side-effect "
            "call. Generate a deterministic action-argument tool named "
            "prepare_add_contact_args. It must accept user_request, optional "
            "name, optional phone_number, and optional relationship; normalize "
            "only the visible phone formatting; and return downstream_tool_name "
            "add_contact plus downstream_tool_kwargs/add_contact_kwargs. The "
            "tool prepares arguments only and must not search, modify, or create "
            "contacts itself."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": (
                        "Please add a contact for Stephen Sondheim with phone "
                        "number +1 (987) 654-3210."
                    ),
                    "name": "",
                    "phone_number": "",
                    "relationship": "",
                },
                {
                    "add_contact_kwargs": {
                        "name": "Stephen Sondheim",
                        "phone_number": "+19876543210",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Stephen Sondheim",
                        "phone_number": "+19876543210",
                    },
                    "normalized_phone_number": "+19876543210",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "",
                    "name": "Avery Stone",
                    "phone_number": "+1 555 0100",
                    "relationship": "friend",
                },
                {
                    "add_contact_kwargs": {
                        "name": "Avery Stone",
                        "phone_number": "+15550100",
                        "relationship": "friend",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Avery Stone",
                        "phone_number": "+15550100",
                        "relationship": "friend",
                    },
                    "normalized_phone_number": "+15550100",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Add a contact for Morgan.",
                    "name": "",
                    "phone_number": "",
                    "relationship": "",
                },
                {
                    "add_contact_kwargs": {},
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "normalized_phone_number": "",
                    "abstain_reason": "missing_name_or_phone_number",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="add_contact_argument_preparation_gap",
        inadequacy_signals=("final_action_argument_preparation",),
        failed_tool_calls=("add_contact",),
        repeated_failed_tool_calls=("add_contact",),
        visible_data_gaps=(
            "visible name and phone number must become original add_contact kwargs",
        ),
        planner_failures=(
            "actor searched or modified contacts instead of add_contact",
        ),
    )


def _next_weekday_timestamp_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="canonicalizer:next_weekday_time_to_timestamp",
        observation=(
            "Reminder creation tasks with phrases like 'next Friday at 5 PM' "
            "require converting the current timestamp plus a target ISO weekday "
            "and local time into the next matching local Unix timestamp before "
            "calling add_reminder. Generate a deterministic canonicalizer named "
            "next_weekday_time_to_timestamp. Inputs: current_timestamp, "
            "target_isoweekday where Monday=1 and Sunday=7, hour, minute, and "
            "current_datetime_info from timestamp_to_datetime_info(current_timestamp). "
            "Keep local_utc_offset_hours only as a deprecated compatibility input; "
            "do not trust a guessed offset. Return a float Unix timestamp for the next "
            "occurrence of that weekday/time strictly after the current local "
            "timestamp; if the target weekday is today and the target time is "
            "still in the future, use today, otherwise use seven days later. "
            "Derive the sandbox local offset from current_timestamp and current_datetime_info, and "
            "return 0.0 if that visible local datetime context is missing or "
            "inconsistent. The helper "
            "must not call add_reminder; the actor must still call the original "
            "ToolSandbox add_reminder with the returned reminder_timestamp."
        ),
        allowed_families=(str(ToolFamily.CANONICALIZER),),
        validation_examples=(
            ToolExample(
                {
                    "current_timestamp": 1778595707.0,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 12,
                        "hour": 10,
                        "minute": 21,
                        "second": 47,
                        "isoweekday": 2,
                    },
                },
                1778878800.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1778860800.0,
                    "target_isoweekday": 5,
                    "hour": 8,
                    "minute": 30,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 15,
                        "hour": 12,
                        "minute": 0,
                        "second": 0,
                        "isoweekday": 5,
                    },
                },
                1779453000.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1778595707.0,
                    "target_isoweekday": 8,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 12,
                        "hour": 10,
                        "minute": 21,
                        "second": 47,
                        "isoweekday": 2,
                    },
                },
                0.0,
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780609395.536667,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 4,
                        "hour": 14,
                        "minute": 43,
                        "second": 15,
                        "isoweekday": 4,
                    },
                },
                1780704000.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780644041.436888,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 5,
                        "hour": 0,
                        "minute": 20,
                        "second": 41,
                        "isoweekday": 5,
                    },
                },
                1780704000.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780609395.536667,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {},
                },
                0.0,
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="next_weekday_reminder_timestamp_failure",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "next weekday phrase must become exact local reminder timestamp",
        ),
        planner_failures=(
            "actor invented day offset or reused current timestamp as reminder time",
        ),
        final_answer_route_mismatch=False,
    )


def _relative_day_time_timestamp_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="canonicalizer:relative_day_time_timestamp",
        observation=(
            "Reminder creation/modification tasks require turning a visible "
            "relative date/time such as 'tomorrow 5 PM' into the exact local Unix "
            "timestamp passed to the original add_reminder or modify_reminder "
            "ToolSandbox call. Generate a deterministic canonicalizer named "
            "relative_day_time_to_timestamp with inputs current_timestamp, "
            "day_offset, hour, minute, current_datetime_info, and optional "
            "local_utc_offset_hours. current_datetime_info must be the visible "
            "dict returned by timestamp_to_datetime_info(current_timestamp), so "
            "the helper preserves ToolSandbox local time without hard-coding a "
            "timezone. Return only the timestamp; never create or modify the "
            "reminder inside the helper."
        ),
        allowed_families=(str(ToolFamily.CANONICALIZER),),
        validation_examples=(
            ToolExample(
                {
                    "current_timestamp": 1777428906.194959,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 4,
                        "day": 28,
                        "hour": 22,
                        "minute": 15,
                        "second": 6,
                        "isoweekday": 2,
                    },
                },
                1777496400.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1777428906.194959,
                    "day_offset": 2,
                    "hour": 8,
                    "minute": 30,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 4,
                        "day": 28,
                        "hour": 22,
                        "minute": 15,
                        "second": 6,
                        "isoweekday": 2,
                    },
                },
                1777552200.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1777428906.194959,
                    "day_offset": 1,
                    "hour": 25,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 4,
                        "day": 28,
                        "hour": 22,
                        "minute": 15,
                        "second": 6,
                        "isoweekday": 2,
                    },
                },
                0.0,
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="relative_reminder_datetime_canonicalization_failure",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        failed_tool_calls=("add_reminder", "modify_reminder"),
        visible_data_gaps=(
            "relative local day/time must become exact benchmark timestamp",
        ),
        planner_failures=("compute relative timestamp before reminder side effect",),
        final_answer_route_mismatch=False,
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


def _resolve_search_window_or_bounds_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:resolve_search_window_or_bounds",
        observation=(
            "Repeated reminder/message recency tasks need a final-action-ready "
            "helper named resolve_search_window_or_bounds, not a thin bounds-only "
            "calculator. The helper must take the current timestamp plus a natural "
            "recency phrase/domain/intent, return the exact original search tool "
            "name and search kwargs, and then preserve the original search call. "
            "This is the broad Praxis-style search-window lane: call "
            "get_current_timestamp first, call this helper second, then call "
            "search_reminder or search_messages with the returned kwargs."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {
                    "current_timestamp": 1777380998.0,
                    "phrase": "todo item I made yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 0,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1777294478.0,
                        "creation_timestamp_upperbound": 1777294718.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
            ),
            ToolExample(
                {
                    "current_timestamp": 1777380998.0,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 0,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1777294478.0,
                        "reminder_timestamp_upperbound": 1777294718.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1777380998.0,
                    "phrase": "today",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "today",
                    "content_keyword": "",
                    "lookback_days": 0,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1777334400.0,
                        "reminder_timestamp_upperbound": 1777420799.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "today",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1777380998.0,
                    "phrase": "upcoming",
                    "target_domain": "reminder",
                    "timestamp_intent": "upcoming",
                    "direction": "upcoming",
                    "content_keyword": "",
                    "lookback_days": 0,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1777380998.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "upcoming",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 0.0,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 0,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "",
                    "search_kwargs": {},
                    "should_call_search": False,
                    "abstain_reason": "missing_current_timestamp",
                    "interpretation": "",
                    "bounds_source": "abstain",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="search_window_final_action_ready_gap",
        inadequacy_signals=(
            "repeated_failed_tool_call",
            "visible_raw_data_lacking_deterministic_transform",
            "thin_bounds_helper_rejected",
        ),
        failed_tool_calls=("search_reminder", "search_messages"),
        repeated_failed_tool_calls=("search_reminder", "search_messages"),
        visible_data_gaps=("missing benchmark-compatible search kwargs",),
        planner_failures=("no_criteria_search_call",),
        final_answer_route_mismatch=False,
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


def _message_content_by_recency_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_message_content_by_recency",
        observation=(
            "Latest/oldest message answer tasks can still fail after "
            "search_messages returns visible records because the actor selects "
            "the wrong message or copies the content poorly. Generate a "
            "side-effect-free helper named select_message_content_by_recency. "
            "Inputs: records and selection_mode ('latest' or 'oldest'). Select "
            "the unique visible message by numeric creation_timestamp and return "
            "selected_content plus an exact final answer recommendation. Abstain "
            "on missing records, missing timestamps, invalid selection mode, "
            "timestamp ties, or missing content. The helper must not search or "
            "send messages."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "old",
                            "content": "bring milk",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "new",
                            "content": "call me",
                            "creation_timestamp": 20.0,
                        },
                    ],
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {
                        "message_id": "new",
                        "content": "call me",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message": {
                        "message_id": "new",
                        "content": "call me",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message_id": "new",
                    "selected_content": "call me",
                    "selected_timestamp": 20.0,
                    "should_answer": True,
                    "abstain_reason": "",
                    "tie_candidates": [],
                    "selection_reason": "selected_latest_message_by_creation_timestamp_at_index_1",
                    "exact_final_answer": "Your most recent message says 'call me'.",
                    "final_answer_recommendation": "Your most recent message says 'call me'.",
                    "copy_exactly": True,
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "old",
                            "content": "first",
                            "creation_timestamp": 5.0,
                        },
                        {
                            "message_id": "new",
                            "content": "second",
                            "creation_timestamp": 15.0,
                        },
                    ],
                    "selection_mode": "oldest",
                },
                {
                    "selected_record": {
                        "message_id": "old",
                        "content": "first",
                        "creation_timestamp": 5.0,
                    },
                    "selected_message": {
                        "message_id": "old",
                        "content": "first",
                        "creation_timestamp": 5.0,
                    },
                    "selected_message_id": "old",
                    "selected_content": "first",
                    "selected_timestamp": 5.0,
                    "should_answer": True,
                    "abstain_reason": "",
                    "tie_candidates": [],
                    "selection_reason": "selected_oldest_message_by_creation_timestamp_at_index_0",
                    "exact_final_answer": "Your oldest message says 'first'.",
                    "final_answer_recommendation": "Your oldest message says 'first'.",
                    "copy_exactly": True,
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "a",
                            "content": "same",
                            "creation_timestamp": 5.0,
                        },
                        {
                            "message_id": "b",
                            "content": "same",
                            "creation_timestamp": 5.0,
                        },
                    ],
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {},
                    "selected_message": {},
                    "selected_message_id": "",
                    "selected_content": "",
                    "selected_timestamp": 5.0,
                    "should_answer": False,
                    "abstain_reason": "ambiguous_timestamp_tie",
                    "tie_candidates": [
                        {
                            "message_id": "a",
                            "content": "same",
                            "creation_timestamp": 5.0,
                        },
                        {
                            "message_id": "b",
                            "content": "same",
                            "creation_timestamp": 5.0,
                        },
                    ],
                    "selection_reason": "",
                    "exact_final_answer": "",
                    "final_answer_recommendation": "abstain:ambiguous_timestamp_tie",
                    "copy_exactly": False,
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="message_recency_final_answer_selection_failure",
        inadequacy_signals=("wrong_selected_record", "final_response_phrasing_failure"),
        failed_tool_calls=("search_messages",),
        visible_data_gaps=(
            "visible message records must become selected content and final answer",
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


def _holiday_search_args_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_holiday_search_args",
        observation=(
            "Holiday timestamp lookup tasks require stable original search_holiday "
            "arguments from the visible user request. The actor has previously "
            "invented stale numeric years for 'this year' requests. Generate a "
            "deterministic helper named prepare_holiday_search_args that accepts "
            "user_request: str and visible_current_year: int, extracts the visible "
            "holiday name, and returns should_call_search_holiday plus "
            "search_holiday_kwargs. It must omit the year unless the user supplied "
            "an explicit numeric year, so the original environment resolves the "
            "current year. It must not compute or encode holiday timestamps."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": "What is the timestamp for Thanksgiving?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": True,
                    "search_holiday_kwargs": {"holiday_name": "Thanksgiving"},
                    "holiday_name": "Thanksgiving",
                    "year_policy": "environment_resolves_year",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "What is the timestamp for Thanksgiving in 2027?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": True,
                    "search_holiday_kwargs": {
                        "holiday_name": "Thanksgiving",
                        "year": 2027,
                    },
                    "holiday_name": "Thanksgiving",
                    "year_policy": "explicit_year",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "What is the holiday timestamp?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": False,
                    "search_holiday_kwargs": {},
                    "holiday_name": "",
                    "year_policy": "missing_holiday_name",
                    "final_answer_recommendation": (
                        "I need the holiday name before I can look up its timestamp."
                    ),
                    "abstain_reason": "missing_holiday_name",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="holiday_timestamp_search_args_need_visible_year_policy",
        inadequacy_signals=(
            "wrong_original_tool_arguments",
            "invented_temporal_context",
        ),
        failed_tool_calls=("search_holiday",),
        visible_data_gaps=(
            "visible holiday label must become original search_holiday kwargs",
        ),
    )


def _is_holiday_timestamp_scenario(scenario_name: str) -> bool:
    lower = scenario_name.lower()
    return "timestamp" in lower and any(
        token in lower
        for token in (
            "holiday",
            "thanksgiving",
            "christmas",
            "easter",
            "halloween",
            "memorial_day",
            "labor_day",
            "independence_day",
            "veterans_day",
        )
    )


def _contact_lookup_query_planner_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:plan_contact_lookup_query",
        observation=(
            "Repeated contact lookup failures happen before any side effect: the "
            "agent has a visible scalar contact constraint from the user request "
            "but fails to turn it into the original search_contacts kwargs and "
            "the answer or target field to extract afterward. Generate a "
            "deterministic pre-search lookup planner named "
            "plan_contact_lookup_query. Inputs are visible scalar constraints "
            "contact_name, phone_number, relationship, and requested_field, plus "
            "optional selected_record after search_contacts returns one visible "
            "contact record. "
            "Return exactly "
            "should_call_search_contacts, search_contacts_kwargs, answer_field, "
            "selected_record, answer_value, final_answer_recommendation, "
            "copy_exactly, and abstain_reason. When one or more safe visible constraints are "
            "present, set should_call_search_contacts true and include only "
            "nonblank original search_contacts kwargs: name from contact_name, "
            "phone_number from phone_number, and relationship from relationship. "
            "Do not add optional filters such as is_self unless they were "
            "explicitly provided as helper inputs. Preserve requested_field as "
            "answer_field so the actor can answer or select a side-effect target "
            "after the original search_contacts result is visible. When "
            "selected_record is supplied for an answer-only lookup, extract the "
            "requested field into answer_value and, when safe, "
            "final_answer_recommendation without adding unrelated fields. Abstain when "
            "requested_field is blank, when no lookup constraint is supplied, "
            "when requested_field is unsupported, or when the task asks to add, "
            "or handle insufficient information instead of answering a scalar "
            "lookup or locating a target for a preserved original side-effect "
            "tool. The helper must never call "
            "search_contacts and must never modify contacts; it only prepares "
            "the next original ToolSandbox search call. Include positive "
            "triggers for search_name_with_relationship, "
            "search_phone_number_with_name, and "
            "search_relationship_with_phone_number, and remove_contact_by_phone. "
            "Include negative triggers for add_contact, insufficient_information, "
            "ambiguous contacts, and non-contact tasks. List search_contacts in "
            "required_original_tool_calls and preserves_side_effect_tools."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "contact_name": "Homer S",
                    "phone_number": "",
                    "relationship": "",
                    "requested_field": "phone_number",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"name": "Homer S"},
                    "answer_field": "phone_number",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "boss",
                    "requested_field": "name",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"relationship": "boss"},
                    "answer_field": "name",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "+10000000000",
                    "relationship": "",
                    "requested_field": "relationship",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"phone_number": "+10000000000"},
                    "answer_field": "relationship",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "+10000000000",
                    "relationship": "",
                    "requested_field": "relationship",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {"phone_number": "+10000000000"},
                    "answer_field": "relationship",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                    "answer_value": "boss",
                    "final_answer_recommendation": "+10000000000 is your boss",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "Homer S",
                    "phone_number": "",
                    "relationship": "",
                    "requested_field": "phone_number",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {"name": "Homer S"},
                    "answer_field": "phone_number",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                    "answer_value": "+10000000000",
                    "final_answer_recommendation": (
                        "Homer S's phone number is +10000000000"
                    ),
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "+12453344098",
                    "relationship": "",
                    "requested_field": "person_id",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"phone_number": "+12453344098"},
                    "answer_field": "person_id",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "",
                    "requested_field": "phone_number",
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "answer_field": "phone_number",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "missing_lookup_constraint",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="contact_scalar_lookup_needs_pre_search_planner",
        inadequacy_signals=(
            "planner_failed_to_issue_available_search",
            "visible_contact_scalar_constraint_unused",
        ),
        failed_tool_calls=("search_contacts",),
        visible_data_gaps=(
            "visible scalar contact constraint must become original search_contacts kwargs",
            "requested answer field must be preserved after search",
        ),
        planner_failures=(
            "prepare contact lookup before original search_contacts call",
        ),
    )


def _send_message_contact_lookup_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:plan_send_message_contact_lookup",
        observation=(
            "Send-message tasks with a named recipient repeatedly fail because "
            "the agent asks for a phone number or tries the send before using "
            "the visible original search_contacts tool. Generate a deterministic "
            "side-effect-free lookup planner named "
            "plan_send_message_contact_lookup. Inputs must be scalar strings: "
            "recipient_name and message_content. Return exactly "
            "should_call_search_contacts, search_contacts_kwargs, "
            "downstream_tool_name, message_content, abstain_reason, next_step, "
            "and final_answer_recommendation. If recipient_name and "
            "message_content are both present, set should_call_search_contacts "
            "true, search_contacts_kwargs to {'name': recipient_name}, "
            "downstream_tool_name to send_message_with_phone_number, and carry "
            "message_content forward unchanged except for trimming outer "
            "whitespace. The helper must not send a message or enable cellular; "
            "after search_contacts returns a unique visible phone number, the "
            "actor must call the original send_message_with_phone_number tool "
            "with that phone number and the returned message_content. If the send "
            "fails because cellular is disabled and the original cellular setter "
            "is visible, the actor may turn cellular on and retry the same send "
            "once. Abstain when recipient_name or message_content is blank, when "
            "the task is insufficient-information, when the recipient is already "
            "a phone number, or when search_contacts is unavailable. Include "
            "search_contacts and send_message_with_phone_number in "
            "required_original_tool_calls and preserves_side_effect_tools."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "recipient_name": "Ada Lovelace",
                    "message_content": "Please call me.",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"name": "Ada Lovelace"},
                    "downstream_tool_name": "send_message_with_phone_number",
                    "message_content": "Please call me.",
                    "abstain_reason": "",
                    "next_step": (
                        "call search_contacts, then send_message_with_phone_number"
                    ),
                    "final_answer_recommendation": (
                        "search_contacts first; if cellular is disabled during "
                        "send, enable cellular and retry once"
                    ),
                },
            ),
            ToolExample(
                {
                    "recipient_name": " Grace Hopper ",
                    "message_content": "  ETA is 5.  ",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"name": "Grace Hopper"},
                    "downstream_tool_name": "send_message_with_phone_number",
                    "message_content": "ETA is 5.",
                    "abstain_reason": "",
                    "next_step": (
                        "call search_contacts, then send_message_with_phone_number"
                    ),
                    "final_answer_recommendation": (
                        "search_contacts first; if cellular is disabled during "
                        "send, enable cellular and retry once"
                    ),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "recipient_name": "",
                    "message_content": "Please call me.",
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "downstream_tool_name": "",
                    "message_content": "Please call me.",
                    "abstain_reason": "missing_recipient_name",
                    "next_step": "ask_for_recipient_or_phone_number",
                    "final_answer_recommendation": (
                        "I need the recipient name or phone number before I can "
                        "send that message."
                    ),
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "recipient_name": "Fredrik Thordendal",
                    "message_content": "",
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "downstream_tool_name": "",
                    "message_content": "",
                    "abstain_reason": "missing_message_content",
                    "next_step": "ask_for_message_content",
                    "final_answer_recommendation": (
                        "What message would you like to send to Fredrik Thordendal?"
                    ),
                },
                negative_applicability=True,
                held_out=True,
            ),
        ),
        generation_allowed=True,
        reason="send_message_named_recipient_needs_contact_lookup_planner",
        inadequacy_signals=(
            "planner_failed_to_issue_available_search",
            "visible_recipient_name_unused",
            "side_effect_precondition_requires_lookup",
        ),
        failed_tool_calls=("search_contacts", "send_message_with_phone_number"),
        visible_data_gaps=(
            "named recipient and message content must become search_contacts kwargs before original send",
        ),
        planner_failures=(
            "prepare contact lookup before original send_message_with_phone_number",
        ),
    )


def _contact_relationship_batch_update_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:plan_contact_relationship_batch_update",
        observation=(
            "Relationship-group contact update scenarios repeatedly fail because "
            "the agent asks for identifiers or updates only one contact even "
            "though the user supplied a visible source relationship and target "
            "relationship. Generate a deterministic side-effect-free planner "
            "named plan_contact_relationship_batch_update. Inputs should be "
            "user_request, source_relationship, target_relationship, and "
            "contacts as an optional visible list from search_contacts. The first "
            "call may happen before search_contacts; when source and target "
            "relationships are known but contacts is empty, return "
            "should_call_search_contacts true with search_contacts_kwargs using "
            "the source relationship. When source_relationship is "
            "'__all_contacts__', this means all non-self contacts and the helper "
            "must return search_contacts_kwargs {'is_self': False} rather than "
            "sending the sentinel as a real relationship filter. After contacts "
            "are visible, return "
            "selected_contacts and downstream_tool_kwargs_list containing one "
            "modify_contact kwargs object per selected non-self contact, plus "
            "downstream_tool_name='modify_contact' and should_call_tools true. "
            "This helper must not call search_contacts or modify_contact itself; "
            "it only prepares the original calls the actor must make next. "
            "Abstain when source_relationship or target_relationship is missing, "
            "when they are equal, when the requested update is self-only, when "
            "contacts are ambiguous or missing required person_id values, or "
            "when the task is add/remove/send/reminder/search-only. Include "
            "positive triggers for relationship group update wording such as "
            "'all friends to enemies' and scenario families beginning "
            "update_contact_relationship_with_relationship. Include "
            "search_contacts and modify_contact in required_original_tool_calls "
            "and preserves_side_effect_tools so side-effect preservation remains "
            "checker-visible."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "user_request": "Make all my friends enemies",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "contacts": [],
                },
                {
                    "phase": "search_required",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"relationship": "friend"},
                    "selected_contacts": [],
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                    "should_call_tools": False,
                    "abstain_reason": "",
                    "final_answer_recommendation": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Make all my friends enemies",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                        },
                        {
                            "person_id": "p2",
                            "name": "Grace",
                            "relationship": "friend",
                        },
                    ],
                },
                {
                    "phase": "modify_required",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                        },
                        {
                            "person_id": "p2",
                            "name": "Grace",
                            "relationship": "friend",
                        },
                    ],
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p1", "relationship": "enemy"},
                        {"person_id": "p2", "relationship": "enemy"},
                    ],
                    "should_call_tools": True,
                    "abstain_reason": "",
                    "final_answer_recommendation": "Ada and Grace are now your enemies.",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Update all contacts as enemies",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "contacts": [],
                },
                {
                    "phase": "search_required",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"is_self": False},
                    "selected_contacts": [],
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                    "should_call_tools": False,
                    "abstain_reason": "",
                    "final_answer_recommendation": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Update all contacts as enemies",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "contacts": [
                        {
                            "person_id": "self",
                            "name": "Me",
                            "relationship": "self",
                            "is_self": True,
                        },
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                },
                {
                    "phase": "modify_required",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p1", "relationship": "enemy"},
                    ],
                    "should_call_tools": True,
                    "abstain_reason": "",
                    "final_answer_recommendation": "Ada is now your enemy.",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Make all my friends friends",
                    "source_relationship": "friend",
                    "target_relationship": "friend",
                    "contacts": [],
                },
                {
                    "phase": "abstain",
                    "source_relationship": "friend",
                    "target_relationship": "friend",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [],
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                    "should_call_tools": False,
                    "abstain_reason": "source equals target",
                    "final_answer_recommendation": "No relationship change is needed.",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="contact_relationship_group_update_needs_batch_planner",
        inadequacy_signals=(
            "planner_failed_to_issue_available_search",
            "side_effect_argument_preparation_failure",
            "batch_update_incomplete",
        ),
        failed_tool_calls=("search_contacts", "modify_contact"),
        visible_data_gaps=(
            "relationship labels must become search_contacts kwargs and batched modify_contact kwargs",
        ),
        planner_failures=(
            "plan relationship-group search then original modify_contact calls",
        ),
    )


def _message_counterparty_contact_update_observation(
    scenario_name: str,
) -> CapabilityObservation:
    latest_person_id = "11111111-1111-1111-1111-111111111111"
    oldest_person_id = "22222222-2222-2222-2222-222222222222"
    latest_record = {
        "message_id": "m2",
        "sender_person_id": "self",
        "recipient_person_id": latest_person_id,
        "recipient_phone_number": "+15550100",
        "creation_timestamp": 20.0,
    }
    oldest_record = {
        "message_id": "m0",
        "sender_person_id": "self",
        "recipient_person_id": oldest_person_id,
        "recipient_phone_number": "+15550001",
        "creation_timestamp": 5.0,
    }
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:select_message_counterparty_for_contact_update",
        observation=(
            "Contact updates based on the latest or oldest message counterparty "
            "repeatedly fail after search_messages returns visible records: the "
            "agent updates the self contact, asks for an id, or guesses an id "
            "instead of selecting the non-self counterparty. Generate a "
            "deterministic side-effect-free helper named "
            "select_message_counterparty_for_contact_update. Inputs must be "
            "records, selection_mode, updates, and self_person_id. It must choose "
            "the latest or oldest visible message by numeric creation_timestamp, "
            "identify the non-self counterparty person id and phone number from "
            "visible sender/recipient fields, and return a final-action-ready "
            "modify_contact plan. Return exactly selected_record, "
            "selected_message, selected_message_id, selected_person_id, "
            "selected_phone_number, selected_timestamp, downstream_tool_name, "
            "downstream_tool_kwargs, should_call_tool, tie_candidates, "
            "abstain_reason, safety_notes, and final_answer_recommendation. "
            "When a unique non-self person_id and at least one update field are "
            "present, downstream_tool_name must be modify_contact and "
            "downstream_tool_kwargs must contain person_id plus the update fields. "
            "The helper must never call search_messages or modify_contact; it "
            "only prepares the original modify_contact call. Abstain on no "
            "records, invalid selection_mode, timestamp ties, missing non-self "
            "counterparty id, missing updates, or insufficient-information tasks. "
            "Include modify_contact in required_original_tool_calls and "
            "preserves_side_effect_tools."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "self",
                            "recipient_person_id": oldest_person_id,
                            "recipient_phone_number": "+15550000",
                            "creation_timestamp": 10.0,
                        },
                        latest_record,
                    ],
                    "selection_mode": "latest",
                    "updates": {"phone_number": "+15550999"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": latest_record,
                    "selected_message": latest_record,
                    "selected_message_id": "m2",
                    "selected_person_id": latest_person_id,
                    "selected_phone_number": "+15550100",
                    "selected_timestamp": 20.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": latest_person_id,
                        "phone_number": "+15550999",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": ("call modify_contact with downstream_tool_kwargs"),
                    "final_answer_recommendation": (
                        "call modify_contact with downstream_tool_kwargs"
                    ),
                },
            ),
            ToolExample(
                {
                    "records": [
                        oldest_record,
                        {
                            "message_id": "m3",
                            "sender_person_id": "self",
                            "recipient_person_id": latest_person_id,
                            "recipient_phone_number": "+15550100",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "oldest",
                    "updates": {"relationship": "friend"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": oldest_record,
                    "selected_message": oldest_record,
                    "selected_message_id": "m0",
                    "selected_person_id": oldest_person_id,
                    "selected_phone_number": "+15550001",
                    "selected_timestamp": 5.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": oldest_person_id,
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": ("call modify_contact with downstream_tool_kwargs"),
                    "final_answer_recommendation": (
                        "call modify_contact with downstream_tool_kwargs"
                    ),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [latest_record],
                    "selection_mode": "latest",
                    "updates": {},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {},
                    "selected_message": {},
                    "selected_message_id": "",
                    "selected_person_id": "",
                    "selected_phone_number": "",
                    "selected_timestamp": 0.0,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "missing_updates",
                    "safety_notes": "abstain; no safe contact update target",
                    "final_answer_recommendation": "abstain:missing_updates",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="message_recency_contact_update_needs_counterparty_selector",
        inadequacy_signals=(
            "wrong_selected_record",
            "unsafe_guess_before_side_effect",
            "side_effect_argument_preparation_failure",
        ),
        failed_tool_calls=("modify_contact",),
        visible_data_gaps=(
            "visible message records must identify the non-self contact update target",
        ),
        planner_failures=(
            "select message counterparty then prepare original modify_contact kwargs",
        ),
    )


def _message_counterparty_search_plan_observation(
    scenario_name: str,
) -> CapabilityObservation:
    def counterparty_expected(payload: dict) -> dict:
        expected = {
            "selected_message": {},
            "counterparty_phone_number": "",
            "answer_value": "",
            "exact_final_answer": "",
            "final_answer_recommendation": "",
            "copy_exactly": False,
        }
        expected.update(payload)
        return expected

    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:plan_message_counterparty_search",
        observation=(
            "Message-counterparty contact updates can fail before the selector "
            "helper has useful records because the actor must first retrieve the "
            "current user's stable person id and then issue the original "
            "search_messages call with a concrete sender or recipient id. Generate "
            "a deterministic side-effect-free helper named "
            "plan_message_counterparty_search. Inputs must be message_direction, "
            "selection_mode, self_person_id, content_keyword, and optional visible "
            "messages from search_messages. On the first "
            "call, when self_person_id is blank, return phase "
            "self_lookup_required, should_call_search_contacts true, "
            "search_contacts_kwargs {'is_self': True}, should_call_search_messages "
            "false, and empty search_messages_kwargs. After the actor obtains "
            "self_person_id from the original search_contacts result, a second "
            "call must return phase message_search_required, "
            "should_call_search_messages true, and search_messages_kwargs using "
            "sender_person_id for sent/outgoing/from-me directions or "
            "recipient_person_id for received/incoming/to-me directions. Preserve "
            "selection_mode so a later visible-record selector can choose latest "
            "or oldest. When visible search_messages records are provided, return "
            "the requested sender or recipient phone number as a final-answer-ready "
            "value. The helper must never call search_contacts, "
            "search_messages, or modify_contact; it only prepares the original "
            "lookup calls that make the later generated selector/action helper "
            "callable. Abstain on missing or invalid message_direction, invalid "
            "selection_mode, or ambiguous either-direction requests."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "message_direction": "sent",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "self_lookup_required",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": True,
                        "search_contacts_kwargs": {"is_self": True},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_contacts, then call this helper again with self_person_id",
                    }
                ),
            ),
            ToolExample(
                {
                    "message_direction": "sent",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "message_search_required",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": True,
                        "search_messages_kwargs": {"sender_person_id": "self-id"},
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_messages with search_messages_kwargs",
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "oldest",
                    "self_person_id": "self-id",
                    "content_keyword": "invoice",
                },
                counterparty_expected(
                    {
                        "phase": "message_search_required",
                        "message_direction": "received",
                        "selection_mode": "oldest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": True,
                        "search_messages_kwargs": {
                            "recipient_person_id": "self-id",
                            "content": "invoice",
                        },
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_messages with search_messages_kwargs",
                    }
                ),
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "GPU",
                    "messages": [
                        {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        }
                    ],
                },
                counterparty_expected(
                    {
                        "phase": "answer_ready",
                        "message_direction": "received",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "",
                        "next_step": "answer with final_answer_recommendation",
                        "selected_message": {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        },
                        "counterparty_phone_number": "+18307976530",
                        "answer_value": "+18307976530",
                        "exact_final_answer": "+18307976530 asked you if you want some GPU",
                        "final_answer_recommendation": "+18307976530 asked you if you want some GPU",
                        "copy_exactly": True,
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "outgoing",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                    "messages": [
                        {
                            "sender_person_id": "other-id",
                            "sender_phone_number": "+10000000000",
                            "recipient_person_id": "self-id",
                            "recipient_phone_number": "+11233344455",
                            "content": "Good, keep me posted",
                            "creation_timestamp": 1781283797.0,
                        }
                    ],
                },
                counterparty_expected(
                    {
                        "phase": "answer_ready",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "",
                        "next_step": "answer with final_answer_recommendation",
                        "selected_message": {
                            "sender_person_id": "other-id",
                            "sender_phone_number": "+10000000000",
                            "recipient_person_id": "self-id",
                            "recipient_phone_number": "+11233344455",
                            "content": "Good, keep me posted",
                            "creation_timestamp": 1781283797.0,
                        },
                        "counterparty_phone_number": "+10000000000",
                        "answer_value": "+10000000000",
                        "exact_final_answer": "+10000000000",
                        "final_answer_recommendation": "+10000000000",
                        "copy_exactly": True,
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "either",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "abstain",
                        "message_direction": "either",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "ambiguous_message_direction",
                        "next_step": "ask_for_sent_or_received_direction",
                    }
                ),
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="message_counterparty_search_needs_self_id_planner",
        inadequacy_signals=(
            "planner_failed_to_issue_available_search",
            "visible_records_missing_before_selector",
            "side_effect_argument_preparation_failure",
        ),
        failed_tool_calls=("search_contacts", "search_messages"),
        visible_data_gaps=(
            "message counterparty selectors need self_person_id and visible message records",
        ),
        planner_failures=(
            "prepare self lookup then original message search before counterparty selector",
        ),
    )


def _contact_update_by_id_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:plan_contact_update_from_id",
        observation=(
            "Direct contact-id update tasks repeatedly fail even though the user "
            "has supplied the stable contact/person id and a new visible phone "
            "number. Generate a deterministic side-effect-free planner named "
            "plan_contact_update_from_id. Inputs must be scalar strings: "
            "person_id, phone_number, name, relationship, and user_request. "
            "Treat name and relationship as optional update fields; if the actor "
            "omits either field, the helper must behave as though an empty string "
            "was supplied rather than abstaining. "
            "Return downstream_tool_name, downstream_tool_kwargs, "
            "should_call_tool, and abstain_reason. "
            "When person_id is present and at least one update field is present, "
            "return should_call_tool true, downstream_tool_name='modify_contact', "
            "and downstream_tool_kwargs containing person_id plus only nonblank "
            "update fields among phone_number, name, and relationship. The "
            "phone_number should be normalized only by removing spaces, dashes, "
            "and parentheses while preserving a leading plus. This helper must "
            "never call modify_contact itself and must never search or guess a "
            "missing id. It prepares the original ToolSandbox modify_contact "
            "call and then the actor must call modify_contact with exactly the "
            "returned kwargs. Abstain when person_id is missing, no update field "
            "is present, the task is add/remove/search/send/reminder, or the "
            "request is insufficient information. Include positive triggers for "
            "update_contact_with_id_and_phone_number and update contact id phone "
            "number. Include modify_contact in required_original_tool_calls and "
            "preserves_side_effect_tools."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "person_id": "11111111-1111-1111-1111-111111111111",
                    "phone_number": "+1 (555) 0100",
                    "name": "",
                    "relationship": "",
                    "user_request": "Update this contact phone number",
                },
                {
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "11111111-1111-1111-1111-111111111111",
                        "phone_number": "+15550100",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "person_id": "22222222-2222-2222-2222-222222222222",
                    "phone_number": "",
                    "name": "Ada Lovelace",
                    "relationship": "",
                    "user_request": "Update contact name",
                },
                {
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "22222222-2222-2222-2222-222222222222",
                        "name": "Ada Lovelace",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "person_id": "",
                    "phone_number": "+15550100",
                    "name": "",
                    "relationship": "",
                    "user_request": "Update contact phone number",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "missing_person_id",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="contact_id_update_needs_modify_contact_argument_planner",
        inadequacy_signals=("side_effect_argument_preparation_failure",),
        failed_tool_calls=("modify_contact",),
        visible_data_gaps=(
            "visible person_id and update fields must become original modify_contact kwargs",
        ),
        planner_failures=(
            "prepare modify_contact kwargs from visible scalar id update",
        ),
    )


def _direct_scalar_contact_action_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_direct_contact_action_args",
        observation=(
            "Direct scalar contact/message action tasks need a generated tool "
            "that prepares exact kwargs for the original ToolSandbox side-effect "
            "tool from user-visible scalar inputs. Generate a deterministic "
            "side-effect-free planner named prepare_direct_contact_action_args. "
            "Inputs: action_type, contact_name, phone_number, relationship, "
            "record_id, target_field, new_value, message_text, and user_request. "
            "The helper must support add_contact, modify_contact, remove_contact, "
            "and send_message actions, but it must never call those original "
            "tools itself. It should return downstream_tool_name, "
            "downstream_tool_kwargs, should_call_tool, and abstain_reason. "
            "For remove_contact, require record_id/person_id. For send_message, "
            "require phone_number and message_text. For modify_contact, require "
            "record_id/person_id plus at least one update field. For add_contact, "
            "require contact_name and phone_number. The helper must abstain for "
            "search, recency, relationship-batch, reminder, or insufficient "
            "information tasks."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "action_type": "remove_contact",
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "",
                    "record_id": "person-123",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "",
                    "user_request": "Remove contact id person-123",
                },
                {
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "person-123"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "action_type": "send_message",
                    "contact_name": "",
                    "phone_number": "+1 (555) 0100",
                    "relationship": "",
                    "record_id": "",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "Running late",
                    "user_request": "Send +1 (555) 0100 Running late",
                },
                {
                    "downstream_tool_name": "send_message_with_phone_number",
                    "downstream_tool_kwargs": {
                        "phone_number": "+15550100",
                        "content": "Running late",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "action_type": "send_message",
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "",
                    "record_id": "",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "Hello",
                    "user_request": "Search messages with content Hello",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "not_direct_scalar_contact_action",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="direct_scalar_contact_action_argument_gap",
        inadequacy_signals=("side_effect_argument_preparation_failure",),
        failed_tool_calls=(
            "add_contact",
            "modify_contact",
            "remove_contact",
            "send_message_with_phone_number",
        ),
        visible_data_gaps=(
            "visible scalar action inputs must be converted into exact original ToolSandbox kwargs",
        ),
        planner_failures=(
            "direct scalar side-effect action executed with incomplete or drifted kwargs",
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
            "or remove_contact, constraints as an optional dict, and updates as an "
            "optional dict for modify actions. The generated "
            "function must treat omitted constraints as {} and {} as no additional "
            "filter, and omitted updates as {}. Return "
            "selected_record, selected_index, selected_id, selected_timestamp, "
            "action_type, downstream_tool_name, downstream_tool_kwargs, "
            "should_call_tool, tie_candidates, abstain_reason, and safety_notes. "
            "Abstain on no records, no numeric timestamp, invalid mode, ties, "
            "constraints not met, or missing target id. The helper must preserve "
            "the original search tool and downstream side-effect tool; it only "
            "selects the target and prepares the next call arguments. When exactly "
            "one best record exists, tie_candidates must be empty. For reminder "
            "actions, selected_id and downstream_tool_kwargs must use reminder_id. "
            "For contact actions, selected_id and downstream_tool_kwargs must use "
            "person_id; do not use message_id as a contact id. If only one of "
            "sender_person_id or recipient_person_id is present, that can be used "
            "as the contact id, but if both are present and differ the helper must "
            "abstain unless the selected record already has person_id. Remove "
            "actions may set should_call_tool true with only the selected id. "
            "Modify actions must merge explicit updates and abstain when updates "
            "is empty. It must never execute modify/remove/send/add itself. On a "
            "timestamp tie, tie_candidates "
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
                    "updates": {},
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
                    "downstream_tool_kwargs": {"reminder_id": "new"},
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call remove_reminder with downstream_tool_kwargs",
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
                    "updates": {"relationship": "friend"},
                },
                {
                    "selected_record": {
                        "message_id": "m2",
                        "sender_person_id": "p2",
                        "creation_timestamp": 50.0,
                    },
                    "selected_index": 1,
                    "selected_id": "p2",
                    "selected_timestamp": 50.0,
                    "action_type": "modify_contact",
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p2",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
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
                    "updates": {"content": "new"},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 20.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [
                        {"reminder_id": "a", "reminder_timestamp": 20.0},
                        {"reminder_id": "b", "reminder_timestamp": 20.0},
                    ],
                    "abstain_reason": "ambiguous_timestamp_tie",
                    "safety_notes": "do not guess before side-effect action",
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
            "only. Generate a small deterministic tool named extract_stock_symbol. "
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
    if scenario_name.startswith(
        ("find_temperature", "find_temperature_f_with_location")
    ):
        return False
    return scenario_name.startswith(
        (
            "find_phone_number_with_location_name",
            "find_distance_with_location_name",
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
            "answer_kind, answer_unit, should_call_downstream_tool, "
            "downstream_tool_name, downstream_tool_kwargs, exact_final_answer, "
            "final_answer_recommendation, copy_exactly, and abstain_reason. "
            "Recognize common visible fields such as phone_number, address, "
            "distance_km, distance, converted_amount, convertedAmount, amount, "
            "value, and scalar conversion results. Return answer_value as a "
            "string and preserve visible unit fields such as currency_code, "
            "unit, and distance_unit as answer_unit when present. Abstain with "
            "an empty answer_value when no supported scalar answer field is "
            "present. This helper must "
            "not call external services itself, must not perform side effects, and "
            "must not replace the original ToolSandbox lookup or conversion call; "
            "it only extracts the final answer from visible output after that "
            "original call returns. Its required_original_tool_calls and "
            "preserves_side_effect_tools must use concrete ToolSandbox producer "
            "names from this list only: search_location_around_lat_lon, "
            "search_lat_lon, calculate_lat_lon_distance, and convert_currency. "
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
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "+1 (555) 0100",
                    "final_answer_recommendation": "+1 (555) 0100",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"service_payload": {"address": "1 Main St, Springfield"}},
                {
                    "answer_value": "1 Main St, Springfield",
                    "answer_kind": "address",
                    "answer_unit": "",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "1 Main St, Springfield",
                    "final_answer_recommendation": "1 Main St, Springfield",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "service_payload": {
                        "converted_amount": 123.45,
                        "currency_code": "EUR",
                    }
                },
                {
                    "answer_value": "123.45",
                    "answer_kind": "converted_amount",
                    "answer_unit": "EUR",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "123.45 EUR",
                    "final_answer_recommendation": "123.45 EUR",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "service_payload": {"distance_km": 67.96238310230461},
                    "requested_unit": "kilometers",
                    "answer_subject": "Golden Gate Bridge",
                },
                {
                    "answer_value": "67.96238310230461",
                    "answer_kind": "distance",
                    "answer_unit": "km",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": (
                        "You are approximately 67.96 kilometers away from Golden Gate Bridge."
                    ),
                    "final_answer_recommendation": (
                        "You are approximately 67.96 kilometers away from Golden Gate Bridge."
                    ),
                    "copy_exactly": True,
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
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
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
            "search_lat_lon",
            "calculate_lat_lon_distance",
            "convert_currency",
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
    # For clean methodology runs, generation and routing use visible task
    # context rather than ToolSandbox scenario names.
    task_context_label: str = ""
    task_family_key: str = ""

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
        source_task_id_redacted = (
            self.evidence_source == "visible_task_context"
            and bool(self.task_context_label)
        )
        scenario_label = (
            self.task_context_label if source_task_id_redacted else self.scenario_name
        )
        return {
            "scenario_name": scenario_label,
            "source_task_id_redacted": source_task_id_redacted,
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
            "task_context_label": self.task_context_label,
            "task_family_key": self.task_family_key,
            "inadequacy_evidence": self.to_inadequacy_evidence().to_json(),
        }


def visible_task_context_from_scenario(scenario: Scenario) -> VisibleTaskContext:
    """Extract only user-visible task text and available tool names."""

    request = ""
    try:
        sandbox_db = scenario.starting_context.get_database(
            DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
            drop_sandbox_message_index=False,
        )
        for row in sandbox_db.iter_rows(named=True):
            if (
                row.get("sender") == RoleType.USER
                and row.get("recipient") == RoleType.AGENT
            ):
                content = str(row.get("content") or "").strip()
                if content:
                    request = content
    except Exception:
        request = ""
    try:
        available = scenario.starting_context.get_available_tools(
            scrambling_allowed=False
        )
        tools = tuple(sorted(str(name) for name in available))
    except Exception:
        tools = ()
    signals = _visible_task_signals(request, tools)
    return VisibleTaskContext(
        user_request=request,
        available_tools=tools,
        signals=signals,
        primary_family_key=_visible_primary_family(signals),
    )


_UUID_LIKE_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def _has_phone_like_value(text: str) -> bool:
    scrubbed = _UUID_LIKE_RE.sub(" ", text)
    for match in re.finditer(
        r"(?<![A-Za-z0-9])\+?\d[\d\s().-]{6,}\d(?![A-Za-z0-9])",
        scrubbed,
    ):
        digit_count = len(re.sub(r"\D", "", match.group(0)))
        if 7 <= digit_count <= 15:
            return True
    return False


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _visible_task_signals(
    user_request: str,
    available_tools: tuple[str, ...],
) -> tuple[str, ...]:
    text = user_request.lower()
    tools = set(available_tools)
    signals: list[str] = []
    has_visible_identifier = bool(
        re.search(r"\b(?:id|person id|contact id)\s+[a-z0-9-]{6,}", text)
    )
    contacted_recency_target = _has_any(
        text,
        (
            "whoever i contacted",
            "whoever contacted me",
            "contacted last",
            "last contacted",
            "i contacted last",
            "contacted most recently",
            "most recently contacted",
            "who did i talk to",
            "who did i speak to",
            "talk to last",
            "talked to last",
            "speak to last",
            "spoke to last",
            "last talked",
            "last spoke",
            "most recently talked",
            "most recently spoke",
        ),
    )
    message_counterparty_target = (
        "search_messages" in tools
        and (
            contacted_recency_target
            or _has_any(
                text,
                (
                    "latest",
                    "oldest",
                    "recent",
                    "last message",
                    "last person",
                    "last contact",
                    "most recent message",
                    "last conversation",
                    "last chat",
                ),
            )
        )
        and _has_any(
            text,
            (
                "contacted",
                "message",
                "messages",
                "text",
                "sent",
                "asked me",
                "talk",
                "talked",
                "speak",
                "spoke",
                "chat",
                "conversation",
            ),
        )
    )
    recency_or_indirect_target = message_counterparty_target or _has_any(
        text,
        (
            "latest",
            "oldest",
            "recent",
            "last message",
            "last person",
            "last contact",
            "first text",
            "first ever",
            "first message",
            "earliest",
            "most recent",
            "who sent",
            "whoever i contacted",
            "contacted last",
            "last contacted",
            "asked me",
            "sent me",
            "which contact",
            "who did i talk to",
            "who did i speak to",
            "talk to last",
            "talked to last",
            "spoke to last",
            "last conversation",
            "last chat",
        ),
    )

    def add(signal: str, condition: bool) -> None:
        if condition and signal not in signals:
            signals.append(signal)

    add("insufficient_information", "insufficient information" in text)
    add("has_phone_number", _has_phone_like_value(text))
    add(
        "contact",
        bool(
            tools
            & {"search_contacts", "add_contact", "modify_contact", "remove_contact"}
        )
        and (
            "has_phone_number" in signals
            or has_visible_identifier
            or _has_any(
                text,
                (
                    "contact",
                    "phone",
                    "relationship",
                    "person",
                    "friend",
                    "enemy",
                    "enemies",
                    "coworker",
                    "coworkers",
                    "boss",
                    "bosses",
                ),
            )
        ),
    )
    add(
        "add_contact",
        "add_contact" in tools
        and _has_any(text, ("add ", "create ", "save "))
        and "contact" in text,
    )
    remove_contact_intent = _has_any(
        text,
        (
            "remove",
            "delete",
            "get rid",
            "get him out",
            "get her out",
            "get them out",
            "get this person out",
            "out of my contact",
            "out of my contacts",
        ),
    )
    add(
        "requested_remove_contact",
        remove_contact_intent and ("contact" in text or "has_phone_number" in signals),
    )
    add(
        "remove_contact",
        "remove_contact" in tools and "requested_remove_contact" in signals,
    )
    add(
        "modify_contact",
        "modify_contact" in tools
        and _has_any(text, ("update", "modify", "change"))
        and "contact" in text,
    )
    phone_contact_target_lookup = "has_phone_number" in signals and (
        "requested_remove_contact" in signals or "modify_contact" in signals
    )
    underspecified_contact_action_lookup = (
        "requested_remove_contact" in signals
        and "search_contacts" in tools
        and not has_visible_identifier
    )
    add(
        "contact_lookup",
        "search_contacts" in tools
        and (
            _has_any(
                text,
                ("phone number", "relationship", "who is", "what is", "who are"),
            )
            or phone_contact_target_lookup
            or underspecified_contact_action_lookup
        )
        and (
            _has_any(
                text,
                ("contact", "friend", "enemy", "boss", "coworker", "phone", "number"),
            )
            or "has_phone_number" in signals
        ),
    )
    relationship_update_request = _has_any(
        text,
        ("update", "modify", "change", "make", "turn", "set "),
    )
    relationship_group_request = _has_any(
        text,
        (
            "all ",
            "all of",
            "everyone",
            "them",
            "friends",
            "enemies",
            "coworkers",
            "bosses",
        ),
    )
    relationship_target_request = _has_any(
        text,
        (
            "friend",
            "friends",
            "enemy",
            "enemies",
            "coworker",
            "coworkers",
            "boss",
            "bosses",
            "relationship",
        ),
    )
    relationship_group_lookup_for_possible_followup = (
        "search_contacts" in tools
        and "modify_contact" in tools
        and not relationship_update_request
        and relationship_group_request
        and relationship_target_request
        and _has_any(text, ("who are", "which", "list", "show", "find", "search"))
    )
    add(
        "relationship_batch_update",
        "modify_contact" in tools
        and "search_contacts" in tools
        and relationship_group_request
        and relationship_target_request
        and (
            relationship_update_request
            or relationship_group_lookup_for_possible_followup
        ),
    )
    direct_scalar_action = (
        not recency_or_indirect_target
        and "relationship_batch_update" not in signals
        and bool(
            tools
            & {
                "add_contact",
                "modify_contact",
                "remove_contact",
                "send_message_with_phone_number",
            }
        )
        and (
            (
                "send_message_with_phone_number" in tools
                and "has_phone_number" in signals
                and _has_any(text, ("send", "text", "message"))
            )
            or (
                "add_contact" in tools
                and "add_contact" in signals
                and "has_phone_number" in signals
            )
            or (
                bool(tools & {"modify_contact", "remove_contact"})
                and has_visible_identifier
                and _has_any(text, ("remove", "delete", "update", "modify"))
            )
        )
    )
    add("direct_contact_action", direct_scalar_action)
    add(
        "safe_abstain_needed",
        "requested_remove_contact" in signals
        and (
            "remove_contact" not in tools
            or ("search_contacts" not in tools and _has_phone_like_value(text))
        ),
    )
    add(
        "safe_abstain_needed",
        "modify_contact" in signals
        and (
            "modify_contact" not in tools
            or (
                "search_contacts" not in tools
                and not ("id " in text or "person" in text)
            )
        ),
    )

    add(
        "message",
        bool(tools & {"search_messages", "send_message_with_phone_number"})
        and _has_any(
            text,
            (
                "message",
                "messages",
                "text",
                "contacted",
                "send",
                "sent me",
                "asked me",
            ),
        ),
    )
    message_lookup_intent = _has_any(
        text,
        (
            "find",
            "look for",
            "search",
            "what does",
            "what's",
            "which message",
            "which text",
            "oldest",
            "latest",
            "earliest",
            "first message",
            "first text",
            "first ever",
            "last message",
            "last text",
            "most recent",
            "sent me",
            "asked me",
        ),
    )
    explicit_send_message_intent = (
        "send_message_with_phone_number" in tools
        and not message_lookup_intent
        and (
            _has_any(text, ("send", "message to", "text to", "tell ", "ask "))
            or bool(re.search(r"\btext\s+(?:\+?\d|[a-z][a-z0-9_'-]+)\b", text))
        )
    )
    add("send_message", explicit_send_message_intent)
    add(
        "named_message_recipient",
        "search_contacts" in tools
        and "send_message" in signals
        and not _has_phone_like_value(text),
    )
    add(
        "safe_abstain_needed",
        "send_message" in signals
        and "search_contacts" not in tools
        and not _has_phone_like_value(text),
    )
    message_search_followup_possible = (
        "search_messages" in tools
        and _has_any(text, ("find", "look for", "search"))
        and _has_any(text, ("message", "messages", "text"))
        and not _has_any(text, ("send", "sent me", "asked me", "which phone number"))
    )
    add(
        "message_recency",
        "search_messages" in tools
        and _has_any(
            text,
            (
                "latest",
                "oldest",
                "earliest",
                "recent",
                "last message",
                "last text",
                "first message",
                "first text",
                "first ever",
                "most recent",
            ),
        ),
    )
    add("message_search_followup_possible", message_search_followup_possible)
    add(
        "message_counterparty_lookup",
        "search_messages" in tools
        and _has_any(
            text,
            (
                "which phone number",
                "who asked",
                "who sent",
                "asked me",
                "sent me",
                "which contact",
                "whoever i contacted",
                "contacted last",
                "last contacted",
                "who did i talk to",
                "who did i speak to",
                "talk to last",
                "talked to last",
                "spoke to last",
                "last conversation",
                "last chat",
            ),
        ),
    )
    add(
        "message_counterparty_update",
        "modify_contact" in tools
        and "search_messages" in tools
        and message_counterparty_target
        and _has_any(text, ("update", "modify", "change")),
    )

    request_mentions_reminder = _has_any(text, ("reminder", "remind", "todo", "to-do"))
    add(
        "reminder",
        bool(
            tools
            & {"add_reminder", "modify_reminder", "remove_reminder", "search_reminder"}
        )
        and request_mentions_reminder,
    )
    add(
        "reminder_create",
        "add_reminder" in tools and _has_any(text, ("remind", "reminder", "todo")),
    )
    add(
        "reminder_modify",
        "modify_reminder" in tools
        and _has_any(text, ("modify", "update", "change"))
        and "reminder" in text,
    )
    add(
        "reminder_remove",
        "remove_reminder" in tools
        and _has_any(text, ("remove", "delete", "get rid", "cancel", "clear"))
        and "reminder" in text,
    )
    add(
        "relative_time",
        _has_any(
            text,
            (
                "tomorrow",
                "tonight",
                "next ",
                "in a week",
                "in two",
                "days from",
                "weeks from",
                "today",
                "yesterday",
                "upcoming",
                "later",
            ),
        ),
    )
    add(
        "weekday_time",
        _has_any(
            text,
            (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ),
        ),
    )
    add("explicit_time", bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", text)))
    add(
        "location_phrase",
        bool(tools & {"search_location_around_lat_lon", "search_lat_lon"})
        and _has_any(
            text,
            (
                " at ",
                " near ",
                " around ",
                "location",
                "address",
                "distance",
                "how far",
                "how many km",
                "how many miles",
                "km to",
                "miles to",
                "phone number of",
            ),
        ),
    )
    recency_search_domain = bool(
        {
            "message",
            "message_recency",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "reminder",
            "reminder_create",
            "reminder_modify",
            "reminder_remove",
        }
        & set(signals)
    )
    add(
        "recency_search",
        recency_search_domain
        and bool(tools & {"search_reminder", "search_messages"})
        and _has_any(
            text,
            (
                "latest",
                "oldest",
                "earliest",
                "first ",
                "first ever",
                "recent",
                "yesterday",
                "today",
                "upcoming",
                "next",
                "later",
                "made",
                "created",
                "last ",
            ),
        ),
    )
    add(
        "recency_action",
        "recency_search" in signals
        and "reminder" in signals
        and bool(tools & {"modify_reminder", "remove_reminder"}),
    )

    add(
        "device_status_read",
        bool(
            tools
            & {
                "get_wifi_status",
                "get_cellular_service_status",
                "get_location_service_status",
                "get_low_battery_mode_status",
            }
        )
        and _has_any(text, ("is my", "whether", "status", "check"))
        and _has_any(text, ("wifi", "cellular", "location", "low battery")),
    )
    direct_device_state_request = bool(
        tools
        & {
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        }
    ) and (
        _has_any(text, ("turn on", "turn off", "enable", "disable"))
        and _has_any(text, ("wifi", "cellular", "location", "low battery"))
    )
    dependent_state_need = _has_any(
        text,
        (
            "resolve any issue",
            "issue alone",
            "whatever you need",
            "if needed",
            "can't send",
            "cannot send",
            "can't access",
            "cannot access",
            "can't connect",
            "cannot connect",
            "cellphone signal",
            "current location",
            "connected to the internet",
            "access my current location",
            "so you can",
            "in order to",
            "to search",
            "to send",
            "to find",
        ),
    )
    add("direct_device_state_action", direct_device_state_request)
    add(
        "device_state_action",
        direct_device_state_request or dependent_state_need,
    )
    add(
        "state_precondition_possible",
        "safe_abstain_needed" not in signals
        and bool(
            tools
            & {
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
                "set_low_battery_mode_status",
            }
        )
        and bool(
            tools
            & {
                "send_message_with_phone_number",
                "search_location_around_lat_lon",
                "search_lat_lon",
                "calculate_lat_lon_distance",
                "search_holiday",
            }
        )
        and (
            dependent_state_need
            or _has_any(
                text, ("cellular off", "wifi off", "location off", "low battery")
            )
        ),
    )

    add(
        "holiday",
        "search_holiday" in tools
        and _has_any(
            text,
            (
                "holiday",
                "christmas",
                "thanksgiving",
                "easter",
                "halloween",
                "memorial day",
                "labor day",
                "independence day",
                "veterans day",
            ),
        ),
    )
    add(
        "calendar_distance",
        "holiday" in signals
        and _has_any(text, ("how many days", "days until", "days till", "when is")),
    )
    add(
        "currency_lookup",
        "convert_currency" in tools
        and (
            _has_any(
                text, ("currency", "convert", "usd", "cny", "eur", "gbp", "jpy", "$")
            )
            or "how much is" in text
        ),
    )
    contact_workflow = bool(
        {
            "contact",
            "add_contact",
            "requested_remove_contact",
            "remove_contact",
            "modify_contact",
            "direct_contact_action",
            "relationship_batch_update",
        }
        & set(signals)
    )
    external_query_text = _has_any(
        text,
        (
            "temperature",
            "temp",
            "weather",
            "celsius",
            "fahrenheit",
            "distance",
            "how far",
            "how many km",
            "how many miles",
            "km to",
            "miles to",
            "currency",
            "convert",
            "stock",
            "address",
            "business",
            "restaurant",
            "store",
            "venue",
        ),
    ) or (
        "phone number" in text
        and not contact_workflow
        and _has_any(
            text,
            (
                "find",
                "what is",
                "what's",
                "lookup",
                "look up",
                "business",
                "restaurant",
                "store",
                "venue",
            ),
        )
    )
    add(
        "external_lookup",
        bool(
            tools
            & {
                "search_lat_lon",
                "search_location_around_lat_lon",
                "search_weather_around_lat_lon",
                "calculate_lat_lon_distance",
                "convert_currency",
                "search_stock",
            }
        )
        and (external_query_text or "currency_lookup" in signals),
    )
    add(
        "stock_lookup",
        "search_stock" in tools and _has_any(text, ("stock", "ticker", "symbol")),
    )
    add(
        "service_answer_extraction",
        "external_lookup" in signals
        and "stock_lookup" not in signals
        and bool(
            tools
            & {
                "search_lat_lon",
                "search_location_around_lat_lon",
                "search_weather_around_lat_lon",
                "calculate_lat_lon_distance",
                "convert_currency",
            }
        )
        and (
            _has_any(
                text,
                (
                    "what is",
                    "what's",
                    "find",
                    "how far",
                    "how many km",
                    "how many miles",
                    "km to",
                    "miles to",
                    "convert",
                    "phone number",
                    "address",
                    "distance",
                    "temperature",
                    "temp",
                    "weather",
                    "forecast",
                    "celsius",
                    "fahrenheit",
                ),
            )
            or "currency_lookup" in signals
        ),
    )
    return tuple(signals)


def _visible_primary_family(signals: tuple[str, ...]) -> str:
    priority = (
        "relationship_batch_update",
        "named_message_recipient",
        "message_counterparty_lookup",
        "message_counterparty_update",
        "recency_action",
        "recency_search",
        "reminder_create",
        "add_contact",
        "direct_contact_action",
        "contact_lookup",
        "device_state_action",
        "device_status_read",
        "stock_lookup",
        "holiday",
        "service_answer_extraction",
        "external_lookup",
        "message",
        "contact",
        "reminder",
    )
    for signal in priority:
        if signal in signals:
            return signal
    return "general_visible_task"


def _visible_observation(
    observation: CapabilityObservation,
    context: VisibleTaskContext,
    task_family_key: str,
    reason: str,
) -> CapabilityObservation:
    sanitized_observation = _sanitize_visible_observation_text(observation.observation)
    return replace(
        observation,
        observation=sanitized_observation,
        task_context_label=context.generation_label(),
        task_family_key=task_family_key,
        evidence_source="visible_task_context",
        reason=f"visible_task_context:{reason}",
    )


def _sanitize_visible_observation_text(text: str) -> str:
    sanitized = text
    sanitized = re.sub(
        r"Include positive triggers for search_name_with_relationship, "
        r"search_phone_number_with_name, and search_relationship_with_phone_number, "
        r"and remove_contact_by_phone\.",
        "Include positive triggers for visible contact lookup, contact field answer, "
        "and contact side-effect target-resolution requests.",
        sanitized,
    )
    sanitized = re.sub(
        r"and scenario families beginning update_contact_relationship_with_relationship\.",
        "and visible relationship-group update wording.",
        sanitized,
    )
    sanitized = re.sub(
        r"scenario families beginning [A-Za-z0-9_]+",
        "visible task families for the same capability",
        sanitized,
    )
    return sanitized


def classify_visible_task_observations(
    scenario_name: str,
    scenario: Scenario,
) -> tuple[CapabilityObservation, ...]:
    """Classify tool-birth opportunities from visible task text and tool schemas."""

    context = visible_task_context_from_scenario(scenario)
    signals = set(context.signals)
    observations: list[CapabilityObservation] = []

    def add(
        observation: CapabilityObservation,
        task_family_key: str,
        reason: str,
    ) -> None:
        observations.append(
            _visible_observation(observation, context, task_family_key, reason)
        )

    if "insufficient_information" in signals or "safe_abstain_needed" in signals:
        add(
            _safe_action_or_abstain_observation(scenario_name),
            "safe_abstain",
            "insufficient_information_guard",
        )
    if "device_status_read" in signals and _direct_status_lookup_enabled():
        add(
            _device_status_lookup_observation(scenario_name),
            "device_status_read",
            "read_only_device_status",
        )
    if "device_state_action" in signals or "state_precondition_possible" in signals:
        add(
            _plan_device_state_action_sequence_observation(scenario_name),
            "device_state_action",
            "visible_device_or_precondition_action",
        )
    reminder_argument_gap = bool(
        "relative_time" in signals
        or "location_phrase" in signals
        or "state_precondition_possible" in signals
        or "device_state_action" in signals
    )
    if "reminder_create" in signals and reminder_argument_gap:
        add(
            _reminder_optional_location_argument_observation(scenario_name),
            "reminder_create",
            "visible_reminder_creation",
        )
    if "reminder_create" in signals:
        if "relative_time" in signals and "weekday_time" not in signals:
            add(
                _relative_day_time_timestamp_observation(scenario_name),
                "relative_time",
                "visible_relative_time",
            )
        if "weekday_time" in signals:
            add(
                _next_weekday_timestamp_observation(scenario_name),
                "weekday_time",
                "visible_weekday_time",
            )
        if "location_phrase" in signals:
            add(
                _location_search_argument_observation(scenario_name),
                "location_phrase",
                "visible_location_phrase",
            )
    if "add_contact" in signals:
        add(
            _add_contact_argument_observation(scenario_name),
            "add_contact",
            "visible_add_contact_request",
        )
    if "direct_contact_action" in signals:
        add(
            _direct_scalar_contact_action_observation(scenario_name),
            "direct_contact_action",
            "visible_scalar_contact_or_message_action",
        )
    if "contact_lookup" in signals:
        add(
            _contact_lookup_query_planner_observation(scenario_name),
            "contact_lookup",
            "visible_contact_lookup_constraint",
        )
    if "named_message_recipient" in signals:
        add(
            _send_message_contact_lookup_observation(scenario_name),
            "named_message_recipient",
            "visible_named_message_recipient",
        )
    if "relationship_batch_update" in signals:
        add(
            _contact_relationship_batch_update_observation(scenario_name),
            "relationship_batch_update",
            "visible_relationship_batch_update",
        )
    if "message_counterparty_update" in signals:
        add(
            _message_counterparty_search_plan_observation(scenario_name),
            "message_counterparty_update",
            "visible_message_counterparty_update_search_plan",
        )
        add(
            _message_counterparty_contact_update_observation(scenario_name),
            "message_counterparty_update",
            "visible_message_counterparty_update",
        )
    if "message_counterparty_lookup" in signals:
        add(
            _message_counterparty_search_plan_observation(scenario_name),
            "message_counterparty_lookup",
            "visible_message_counterparty_lookup",
        )
    if "recency_search" in signals:
        add(
            _resolve_search_window_or_bounds_observation(scenario_name),
            "recency_search",
            "visible_recency_search",
        )
        add(
            _latest_record_selection_observation(scenario_name),
            "recency_search",
            "visible_recency_selection",
        )
        if "message_recency" in signals:
            add(
                _message_content_by_recency_observation(scenario_name),
                "message_recency",
                "visible_message_recency_answer",
            )
    message_recency_visible = (
        "message_recency" in signals or "message_search_followup_possible" in signals
    )
    if message_recency_visible and "recency_search" not in signals:
        add(
            _message_content_by_recency_observation(scenario_name),
            "message_recency",
            "visible_message_recency_answer",
        )
    if "recency_action" in signals:
        add(
            _recency_action_target_observation(scenario_name),
            "recency_action",
            "visible_recency_side_effect_target",
        )
    if "location_phrase" in signals and "external_lookup" in signals:
        add(
            _location_search_argument_observation(scenario_name),
            "location_phrase",
            "visible_external_location_phrase",
        )
    if "holiday" in signals:
        add(
            _holiday_search_args_observation(scenario_name),
            "holiday_lookup",
            "visible_holiday_lookup",
        )
        if "calendar_distance" in signals:
            add(
                _days_between_timestamps_observation(scenario_name),
                "calendar_distance",
                "visible_calendar_distance",
            )
    if "stock_lookup" in signals:
        add(
            _stock_symbol_extraction_observation(scenario_name),
            "stock_lookup",
            "visible_stock_lookup",
        )
    if "service_answer_extraction" in signals:
        add(
            _external_service_answer_extraction_observation(scenario_name),
            "service_answer_extraction",
            "visible_service_answer",
        )

    return tuple(observations)


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
        return (_safe_action_or_abstain_observation(scenario_name),)

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
        if _is_search_window_or_bounds_scenario(scenario_name):
            observations.append(
                _resolve_search_window_or_bounds_observation(scenario_name)
            )
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
                        "day_offset, hour, minute, current_datetime_info, and optional "
                        "local_utc_offset_hours. current_datetime_info must be the "
                        "visible dict returned by timestamp_to_datetime_info("
                        "current_timestamp), so the helper preserves ToolSandbox "
                        "local time without hard-coding a timezone."
                    ),
                    allowed_families=(str(ToolFamily.CANONICALIZER),),
                    validation_examples=(
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 1,
                                "hour": 17,
                                "minute": 0,
                                "local_utc_offset_hours": 0,
                                "current_datetime_info": {
                                    "year": 2026,
                                    "month": 4,
                                    "day": 28,
                                    "hour": 22,
                                    "minute": 15,
                                    "second": 6,
                                    "isoweekday": 2,
                                },
                            },
                            1777496400.0,
                        ),
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 2,
                                "hour": 8,
                                "minute": 30,
                                "local_utc_offset_hours": 0,
                                "current_datetime_info": {
                                    "year": 2026,
                                    "month": 4,
                                    "day": 28,
                                    "hour": 22,
                                    "minute": 15,
                                    "second": 6,
                                    "isoweekday": 2,
                                },
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
        if _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_content_by_recency_observation(scenario_name))
        elif _is_latest_record_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_message_counterparty_contact_update_scenario(scenario_name):
            observations.append(
                _message_counterparty_search_plan_observation(scenario_name)
            )
            observations.append(
                _message_counterparty_contact_update_observation(scenario_name)
            )
        if _is_recency_action_target_scenario(scenario_name):
            observations.append(_recency_action_target_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_medium_grain_constraint_action_scenario(
            scenario_name
        ) and not _is_contact_relationship_batch_update_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        if _is_message_search_window_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_search_window_observation(scenario_name))
        if _is_search_window_or_bounds_scenario(scenario_name):
            observations.append(
                _resolve_search_window_or_bounds_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and _is_next_weekday_reminder_scenario(scenario_name):
        return (_next_weekday_timestamp_observation(scenario_name),)

    if similarity < 1.0 and _is_reminder_optional_location_argument_scenario(
        scenario_name
    ):
        observations = [_reminder_optional_location_argument_observation(scenario_name)]
        if _is_reminder_location_search_argument_scenario(scenario_name):
            observations.append(_location_search_argument_observation(scenario_name))
        if _is_direct_service_precondition_scenario(scenario_name):
            observations.append(
                _plan_device_state_action_sequence_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and _is_contact_update_by_id_scenario(scenario_name):
        return (_contact_update_by_id_observation(scenario_name),)

    if similarity < 1.0 and _is_direct_scalar_contact_action_scenario(scenario_name):
        return (_direct_scalar_contact_action_observation(scenario_name),)

    if similarity < 1.0 and _is_contact_relationship_batch_update_scenario(
        scenario_name
    ):
        return (_contact_relationship_batch_update_observation(scenario_name),)

    if similarity < 1.0 and _is_medium_grain_constraint_action_scenario(scenario_name):
        return (_constraint_to_action_planner_observation(scenario_name),)

    if similarity < 1.0 and (
        _is_latest_record_scenario(scenario_name)
        or _is_message_search_window_scenario(scenario_name)
        or _is_message_recency_extreme_scenario(scenario_name)
    ):
        observations = []
        if _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_content_by_recency_observation(scenario_name))
        elif _is_latest_record_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_message_counterparty_contact_update_scenario(scenario_name):
            observations.append(
                _message_counterparty_search_plan_observation(scenario_name)
            )
            observations.append(
                _message_counterparty_contact_update_observation(scenario_name)
            )
        if _is_recency_action_target_scenario(scenario_name):
            observations.append(_recency_action_target_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_contact_relationship_batch_update_scenario(scenario_name):
            observations.append(
                _contact_relationship_batch_update_observation(scenario_name)
            )
        elif _is_medium_grain_constraint_action_scenario(scenario_name):
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
        if _is_contact_relationship_batch_update_scenario(scenario_name):
            observations.append(
                _contact_relationship_batch_update_observation(scenario_name)
            )
        elif _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and _is_add_contact_action_scenario(scenario_name):
        return (_add_contact_argument_observation(scenario_name),)

    if similarity < 1.0 and _is_visible_record_constraint_scenario(scenario_name):
        observations = []
        if _is_contact_lookup_query_scenario(scenario_name):
            observations.append(
                _contact_lookup_query_planner_observation(scenario_name)
            )
        if _is_contact_relationship_batch_update_scenario(scenario_name):
            observations.append(
                _contact_relationship_batch_update_observation(scenario_name)
            )
        if not observations:
            observations.append(_contact_constraint_observation(scenario_name))
        if _is_post_selection_side_effect_prep_scenario(scenario_name):
            observations.append(
                _post_selection_side_effect_args_observation(scenario_name)
            )
        if _is_contact_relationship_batch_update_scenario(scenario_name):
            observations.append(
                _contact_relationship_batch_update_observation(scenario_name)
            )
        elif _is_medium_grain_constraint_action_scenario(scenario_name):
            observations.append(
                _constraint_to_action_planner_observation(scenario_name)
            )
        return tuple(observations)

    if similarity < 1.0 and scenario_name.startswith("find_days_till_holiday"):
        return (_days_between_timestamps_observation(scenario_name),)

    if similarity < 1.0 and _is_holiday_timestamp_scenario(scenario_name):
        return (_holiday_search_args_observation(scenario_name),)

    if similarity < 1.0 and scenario_name.startswith(
        "find_stock_symbol_with_company_name"
    ):
        return (_stock_symbol_extraction_observation(scenario_name),)

    if similarity < 1.0 and _is_external_answer_extraction_scenario(scenario_name):
        return (_external_service_answer_extraction_observation(scenario_name),)

    if similarity < 1.0 and _is_device_status_lookup_scenario(scenario_name):
        return (_device_status_lookup_observation(scenario_name),)

    if similarity < 1.0 and _is_direct_service_precondition_scenario(scenario_name):
        observations = [_next_service_tool_call_observation(scenario_name)]
        if _is_send_message_contact_lookup_scenario(scenario_name):
            observations.append(_send_message_contact_lookup_observation(scenario_name))
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


def classify_planned_scenario_observations(
    scenario_name: str,
) -> tuple[CapabilityObservation, ...]:
    """Classify unlabeled task-family text into proactive birth observations.

    This is intentionally weaker than result-backed classification: it uses only
    visible manifest task names/family text, never labels, answers, scenario
    state, or prior SAGE traces.  It exists to let self-evolving discovery birth
    a coherent helper portfolio early enough for natural adoption instead of
    paying one failure per helper family before the registry can improve.
    """

    if _scenario_name_birth_disabled():
        return ()

    observations: list[CapabilityObservation] = []

    if "insufficient_information" in scenario_name:
        observations.append(_safe_action_or_abstain_observation(scenario_name))
    if _is_medium_grain_constraint_action_scenario(scenario_name):
        observations.append(_constraint_to_action_planner_observation(scenario_name))
    if _is_next_weekday_reminder_scenario(scenario_name):
        observations.append(_next_weekday_timestamp_observation(scenario_name))
    if _is_reminder_optional_location_argument_scenario(scenario_name):
        observations.append(
            _reminder_optional_location_argument_observation(scenario_name)
        )
    if _is_reminder_location_search_argument_scenario(scenario_name):
        observations.append(_location_search_argument_observation(scenario_name))
    if _is_contact_update_by_id_scenario(scenario_name):
        observations.append(_contact_update_by_id_observation(scenario_name))
    if _is_contact_lookup_query_scenario(scenario_name):
        observations.append(_contact_lookup_query_planner_observation(scenario_name))
    if _is_contact_relationship_batch_update_scenario(scenario_name):
        observations.append(
            _contact_relationship_batch_update_observation(scenario_name)
        )
    if _is_send_message_contact_lookup_scenario(scenario_name):
        observations.append(_send_message_contact_lookup_observation(scenario_name))
    if _is_message_counterparty_contact_update_scenario(scenario_name):
        observations.append(
            _message_counterparty_search_plan_observation(scenario_name)
        )
        observations.append(
            _message_counterparty_contact_update_observation(scenario_name)
        )
    if _is_message_recency_extreme_scenario(scenario_name):
        observations.append(_message_content_by_recency_observation(scenario_name))
    if _is_recency_action_target_scenario(scenario_name):
        observations.append(_recency_action_target_observation(scenario_name))
    if _is_post_selection_side_effect_prep_scenario(scenario_name):
        observations.append(_post_selection_side_effect_args_observation(scenario_name))
    if scenario_name.startswith(
        (
            "modify_reminder_with_recency_latest",
            "add_reminder_content_and_week_delta_and_time",
        )
    ):
        observations.append(_relative_day_time_timestamp_observation(scenario_name))
    if _is_search_window_or_bounds_scenario(scenario_name):
        observations.append(_resolve_search_window_or_bounds_observation(scenario_name))
    if scenario_name.startswith("find_days_till_holiday"):
        observations.append(_days_between_timestamps_observation(scenario_name))
    if _is_holiday_timestamp_scenario(scenario_name):
        observations.append(_holiday_search_args_observation(scenario_name))
    if _is_external_answer_extraction_scenario(scenario_name):
        observations.append(
            _external_service_answer_extraction_observation(scenario_name)
        )
    if _is_direct_scalar_contact_action_scenario(scenario_name):
        observations.append(_direct_scalar_contact_action_observation(scenario_name))
    if _is_add_contact_action_scenario(scenario_name):
        observations.append(_add_contact_argument_observation(scenario_name))
    if _is_direct_service_precondition_scenario(scenario_name):
        observations.append(
            _plan_device_state_action_sequence_observation(scenario_name)
        )
        observations.append(_next_service_tool_call_observation(scenario_name))
    if _is_device_status_lookup_scenario(scenario_name):
        observations.append(_device_status_lookup_observation(scenario_name))

    planned: list[CapabilityObservation] = []
    for observation in observations:
        planned.append(
            replace(
                observation,
                reason=f"unlabeled_manifest_gap_plan:{observation.reason}",
                evidence_source="unlabeled_manifest_task_text",
            )
        )
    return tuple(planned)
