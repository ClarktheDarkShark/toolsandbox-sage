"""Readable, source-counted actor replay fixtures.

The historical-test cases below are adapted from the 72 passing cases in
``tests/unit/test_openai_toolsandbox_roles.py`` at the frozen test-oracle
commit.  They are deterministic characterization inputs, not archived model
requests and not reconstructed evidence-run payloads.  The remaining cases
exercise reference branches that the historical tests did not reach through
the top-level policy composer.
"""

from __future__ import annotations

import json
from typing import Any


STRING = {"type": "string"}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
OBJECT = {"type": "object"}
RECORDS = {"type": "array", "items": {"type": "object"}}


def tool(
    name: str,
    properties: dict[str, Any] | None = None,
    *,
    description: str = "Deterministic actor replay fixture tool.",
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
    }
    if required:
        parameters["required"] = list(required)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def assistant_call(
    name: str, arguments: dict[str, Any], call_id: str = "fixture-call"
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, separators=(",", ":")),
                },
            }
        ],
    }


def tool_result(
    name: str, payload: Any, call_id: str = "fixture-call"
) -> dict[str, Any]:
    return {
        "role": "tool",
        "name": name,
        "tool_call_id": call_id,
        "content": repr(payload),
    }


def _case(
    case_id: str,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | str,
    direct_positive: tuple[str, ...] = (),
    direct_absent: tuple[str, ...] = (),
    provenance: str,
    source_test: str = "",
    runtime_tools: dict[str, dict[str, Any]] | None = None,
    response_mode: str = "assistant_text",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "provenance": provenance,
        "source_test": source_test,
        "messages": messages,
        "tools": tools,
        "runtime_tools": runtime_tools or {},
        "direct_positive": list(direct_positive),
        "direct_absent": list(direct_absent),
        "response_mode": response_mode,
    }


REMINDER_PREPARE = tool(
    "prepare_reminder_creation_args",
    {
        "content": STRING,
        "resolved_reminder_timestamp": NUMBER,
        "current_timestamp": NUMBER,
        "day_offset": INTEGER,
        "hour": INTEGER,
        "minute": INTEGER,
        "current_datetime_info": OBJECT,
        "location_available": BOOLEAN,
        "location_lookup_failed": BOOLEAN,
        "latitude": NUMBER,
        "longitude": NUMBER,
    },
    description=(
        "Prepare the arguments for original add_reminder and return "
        "should_call_add_reminder with downstream_tool_kwargs."
    ),
)
LOCATION_PREPARE = tool(
    "prepare_location_search_args",
    {
        "user_request": STRING,
        "location_phrase": STRING,
        "latitude": NUMBER,
        "longitude": NUMBER,
    },
)
STATE_HELPER = tool(
    "plan_device_state_action_sequence_v3",
    {
        "user_request": STRING,
        "visible_state_or_error": STRING,
        "target_service": STRING,
        "desired_on": BOOLEAN,
    },
    description="Plan a deterministic device-state setter sequence.",
)


def actor_cases() -> list[dict[str, Any]]:
    """Return fresh mutable copies of every actor-boundary fixture."""

    cases = [
        _case(
            "historical_message_record_handoff",
            provenance="historical_test_seed",
            source_test="test_record_native_tool_waits_for_matching_original_record_source",
            messages=[
                {"role": "user", "content": "Update the last person I messaged."},
                {
                    "role": "tool",
                    "name": "search_contacts",
                    "content": "[{'person_id': 'self', 'is_self': True}]",
                },
                {
                    "role": "tool",
                    "name": "search_messages",
                    "content": (
                        "[{'sender_person_id': 'self', 'recipient_person_id': "
                        "'p2', 'creation_timestamp': 100.0}]"
                    ),
                },
            ],
            tools=[
                tool(
                    "select_message_counterparty_for_contact_update",
                    {
                        "records": {"type": "array"},
                        "updates": OBJECT,
                        "self_person_id": STRING,
                    },
                    description=(
                        "Consumes visible search_messages records and delegates one "
                        "validated native modify_contact action."
                    ),
                )
            ],
            direct_positive=(
                "_generated_record_handoff_actor_policy_message",
                "_message_counterparty_selector_setup_actor_policy_message",
                "_post_selection_helper_actor_policy_message",
                "_selector_actor_policy_message",
            ),
        ),
        _case(
            "historical_reminder_recency_native_handoff",
            provenance="historical_test_seed",
            source_test="test_native_reminder_action_receives_generated_timestamp_update",
            messages=[
                {
                    "role": "user",
                    "content": "Postpone my most recent reminder to tomorrow 5 PM.",
                },
                {"role": "tool", "name": "get_current_timestamp", "content": "1000"},
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "content": "{'hour': 8, 'minute': 0, 'second': 0}",
                },
                {
                    "role": "tool",
                    "name": "relative_day_time_to_timestamp",
                    "content": "90000.0",
                },
                {
                    "role": "tool",
                    "name": "search_reminder",
                    "content": (
                        "[{'reminder_id': 'r1', 'creation_timestamp': 900.0, "
                        "'reminder_timestamp': 1200.0}]"
                    ),
                },
            ],
            tools=[
                tool(
                    "select_action_target_by_recency",
                    description=(
                        "This generated composite completes one final action by "
                        "delegating to an approved native ToolSandbox tool. The "
                        "native tool remains the state-changing implementation."
                    ),
                ),
                tool("modify_reminder"),
                tool("relative_day_time_to_timestamp"),
            ],
            direct_positive=(
                "_native_action_tool_actor_policy_message",
                "_relative_time_actor_policy_message",
                "_reminder_recency_search_result_actor_policy_message",
            ),
        ),
        _case(
            "historical_relative_search_without_clock",
            provenance="historical_test_seed",
            source_test="test_relative_time_search_routes_to_abstention_without_clock",
            messages=[{"role": "user", "content": "Which reminder was due yesterday?"}],
            tools=[
                tool(
                    "prepare_safe_action_or_abstain",
                    {
                        "user_request": STRING,
                        "requested_action": STRING,
                        "target_identifier": STRING,
                        "required_original_tools": {"type": "array"},
                        "available_original_tools": {"type": "array"},
                        "visible_records_count": INTEGER,
                    },
                    description="Prepare a safe action or abstain decision.",
                ),
                tool(
                    "resolve_search_window_or_bounds",
                    {
                        "current_timestamp": NUMBER,
                        "phrase": STRING,
                        "target_domain": STRING,
                        "timestamp_intent": STRING,
                        "direction": STRING,
                    },
                    description="Prepare bounded search kwargs from a recency phrase.",
                ),
                tool("search_reminder"),
            ],
            direct_positive=(
                "_lookup_planner_actor_policy_message",
                "_safe_abstention_helper_actor_policy_message",
                "_search_window_actor_policy_message",
            ),
        ),
        _case(
            "historical_location_retry_after_coordinates",
            provenance="historical_test_seed",
            source_test="test_location_search_retries_generated_prepare_after_coordinates",
            messages=[
                {
                    "role": "user",
                    "content": "Add a reminder to buy milk at Whole Foods.",
                },
                assistant_call(
                    "prepare_location_search_args",
                    {
                        "user_request": "Add a reminder to buy milk at Whole Foods.",
                        "location_phrase": "Whole Foods",
                    },
                    "prepare",
                ),
                tool_result(
                    "prepare_location_search_args",
                    {
                        "search_location_kwargs": {},
                        "should_call_downstream_tool": False,
                        "downstream_tool_name": "",
                        "downstream_tool_kwargs": {},
                        "location_query": "",
                        "abstain_reason": (
                            "missing_current_coordinates_for_broad_location_query"
                        ),
                    },
                    "prepare",
                ),
                {"role": "user", "content": "It's on McKinley Ave."},
                assistant_call("get_current_location", {}, "location"),
                tool_result(
                    "get_current_location",
                    {"latitude": 37.334606, "longitude": -122.009102},
                    "location",
                ),
            ],
            tools=[
                LOCATION_PREPARE,
                tool("search_location_around_lat_lon"),
                tool("prepare_reminder_creation_args"),
                tool("add_reminder"),
            ],
            direct_positive=(
                "_generated_tool_abstain_continuation_actor_policy_message",
                "_location_search_retry_after_coordinates_actor_policy_message",
                "_reminder_missing_time_actor_policy_message",
            ),
        ),
        _case(
            "historical_distance_scalar_extractor",
            provenance="historical_test_seed",
            source_test="test_derived_policy_does_not_force_distance_scalar_into_service_helper",
            messages=[
                {
                    "role": "user",
                    "content": "How far am I from Golden Gate Bridge?",
                },
                {
                    "role": "tool",
                    "name": "calculate_lat_lon_distance",
                    "content": "67.96238310230461",
                },
            ],
            tools=[
                tool(
                    "extract_service_answer_field",
                    {"service_payload": OBJECT},
                    description="Extract deterministic answer fields.",
                )
            ],
            direct_positive=(
                "_derived_actor_policy_message",
                "_service_extractor_scalar_actor_policy_message",
            ),
        ),
        _case(
            "historical_state_sequence_continuation",
            provenance="historical_test_seed",
            source_test="test_generated_downstream_choice_executes_next_state_sequence_action",
            messages=[
                {"role": "user", "content": "Turn on cellular"},
                tool_result(
                    "plan_device_state_action_sequence_v3",
                    {
                        "tool_name": "set_low_battery_mode_status",
                        "arguments": {"on": False},
                        "should_call": True,
                        "action_sequence": [
                            {
                                "tool_name": "set_low_battery_mode_status",
                                "arguments": {"on": False},
                            },
                            {
                                "tool_name": "set_cellular_service_status",
                                "arguments": {"on": True},
                            },
                        ],
                    },
                    "plan",
                ),
                assistant_call(
                    "set_low_battery_mode_status", {"on": False}, "low-battery"
                ),
                tool_result("set_low_battery_mode_status", None, "low-battery"),
            ],
            tools=[
                tool(
                    "plan_device_state_action_sequence_v3",
                    {"target_service": STRING, "desired_on": BOOLEAN},
                    description="Plans a sequence of actions to change device state.",
                ),
                tool("set_low_battery_mode_status"),
                tool("set_cellular_service_status"),
            ],
            direct_positive=(
                "_state_action_actor_policy_message",
                "_state_action_sequence_completion_policy_message",
            ),
        ),
        _case(
            "historical_helper_answer_completion",
            provenance="historical_test_seed",
            source_test="test_helper_answer_retention_policy_recaps_search_window_answer_with_end_tool",
            messages=[
                {"role": "user", "content": "What's the todo item I made yesterday?"},
                {
                    "role": "tool",
                    "name": "get_current_timestamp",
                    "content": "1780650312",
                },
                tool_result(
                    "resolve_search_window_or_bounds",
                    {
                        "target_tool_name": "search_reminder",
                        "search_kwargs": {
                            "creation_timestamp_lowerbound": 1780563792,
                            "creation_timestamp_upperbound": 1780564032,
                        },
                        "should_call_search": True,
                        "abstain_reason": "",
                    },
                ),
                tool_result(
                    "search_reminder",
                    [
                        {
                            "reminder_id": "r1",
                            "content": "Buy tickets for Merrily next week",
                            "creation_timestamp": 1780563912.356671,
                        }
                    ],
                ),
                {
                    "role": "assistant",
                    "content": (
                        "The todo item you made yesterday is: Buy tickets for "
                        "Merrily next week."
                    ),
                },
                {"role": "user", "content": "Got it, I need that info!"},
            ],
            tools=[tool("end_conversation")],
            direct_positive=("_helper_answer_completion_actor_policy_message",),
        ),
        _case(
            "historical_search_window_result",
            provenance="historical_test_seed",
            source_test="test_search_window_result_handoff_answers_after_visible_reminder_result",
            messages=[
                {"role": "user", "content": "What's my todo yesterday?"},
                {
                    "role": "tool",
                    "name": "get_current_timestamp",
                    "content": "1780650312",
                },
                assistant_call("resolve_search_window_or_bounds", {}),
                tool_result(
                    "resolve_search_window_or_bounds",
                    {
                        "target_tool_name": "search_reminder",
                        "search_kwargs": {
                            "creation_timestamp_lowerbound": 1780563792,
                            "creation_timestamp_upperbound": 1780564032,
                        },
                        "should_call_search": True,
                        "abstain_reason": "",
                    },
                ),
                tool_result(
                    "search_reminder",
                    [{"reminder_id": "r1", "content": "Buy tickets for Merrily"}],
                ),
            ],
            tools=[tool("resolve_search_window_or_bounds"), tool("search_reminder")],
            direct_positive=("_search_window_result_handoff_actor_policy_message",),
        ),
        _case(
            "historical_weekday_missing_content",
            provenance="historical_test_seed",
            source_test="test_weekday_time_tool_waits_for_required_reminder_content",
            messages=[{"role": "user", "content": "Add a reminder next Friday 5 PM"}],
            tools=[tool("next_weekday_time_to_timestamp")],
            direct_positive=("_scheduling_timestamp_actor_policy_message",),
        ),
        _case(
            "historical_reminder_remove_after_selector",
            provenance="historical_test_seed",
            source_test="test_reminder_remove_workflow_calls_original_action_after_selector",
            messages=[
                {"role": "user", "content": "Remove my latest reminder."},
                tool_result(
                    "search_reminder",
                    [
                        {"reminder_id": "old", "creation_timestamp": 100.0},
                        {"reminder_id": "new", "creation_timestamp": 200.0},
                    ],
                ),
                assistant_call(
                    "select_record_by_timestamp_extreme",
                    {
                        "records": [],
                        "timestamp_key": "creation_timestamp",
                        "selection_mode": "latest",
                    },
                    "selector",
                ),
                tool_result(
                    "select_record_by_timestamp_extreme",
                    {
                        "selected_record": {
                            "reminder_id": "new",
                            "creation_timestamp": 200.0,
                        },
                        "abstain_reason": "",
                    },
                    "selector",
                ),
            ],
            tools=[
                tool(
                    "select_record_by_timestamp_extreme", {"records": {"type": "array"}}
                ),
                tool("search_reminder"),
                tool("remove_reminder"),
            ],
            direct_positive=("_helper_output_handoff_actor_policy_message",),
        ),
        _case(
            "historical_contact_lookup_answer",
            provenance="historical_test_seed",
            source_test="test_contact_lookup_answer_policy_reuses_helper_after_visible_record",
            messages=[
                {
                    "role": "user",
                    "content": "What is my relationship with +10000000000?",
                },
                tool_result(
                    "plan_contact_lookup_query",
                    {
                        "should_call_search_contacts": True,
                        "search_contacts_kwargs": {"phone_number": "+10000000000"},
                        "answer_field": "relationship",
                        "abstain_reason": "",
                    },
                ),
                tool_result(
                    "search_contacts",
                    [
                        {
                            "person_id": "p1",
                            "name": "Homer S",
                            "phone_number": "+10000000000",
                            "relationship": "boss",
                        }
                    ],
                ),
            ],
            tools=[tool("plan_contact_lookup_query")],
            direct_positive=("_contact_lookup_answer_actor_policy_message",),
        ),
    ]

    # Deterministic branch characterizations fill the policy branches that the
    # historical actor tests did not exercise through the top-level composer.
    cases.extend(_characterization_cases())
    cases.extend(_envelope_edge_cases())
    return cases


def _characterization_cases() -> list[dict[str, Any]]:
    return [
        _case(
            "absolute_reminder_timestamp",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Remind me on October 15, 2026 at 3 PM to call Dana.",
                }
            ],
            tools=[
                tool("datetime_info_to_timestamp"),
                REMINDER_PREPARE,
                tool("add_reminder"),
            ],
            direct_positive=("_absolute_reminder_timestamp_actor_policy_message",),
        ),
        _case(
            "action_argument_helper",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Remind me tomorrow at 3 PM to call Dana."}
            ],
            tools=[
                REMINDER_PREPARE,
                tool("get_current_timestamp"),
                tool("timestamp_to_datetime_info"),
                tool("add_reminder"),
            ],
            direct_positive=("_action_argument_helper_actor_policy_message",),
        ),
        _case(
            "add_contact_arguments",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Add Dana as a contact with phone number +15551234567.",
                }
            ],
            tools=[
                tool(
                    "prepare_add_contact_args",
                    {
                        "user_request": STRING,
                        "relationship": STRING,
                        "is_self": BOOLEAN,
                    },
                ),
                tool("add_contact"),
            ],
            direct_positive=("_add_contact_argument_actor_policy_message",),
        ),
        _case(
            "contact_relationship_batch",
            provenance="deterministic_characterization",
            messages=[{"role": "user", "content": "Update all my friends as enemies."}],
            tools=[
                tool(
                    "plan_contact_relationship_batch_update",
                    {
                        "source_relationship": STRING,
                        "target_relationship": STRING,
                        "contacts": RECORDS,
                    },
                ),
                tool("search_contacts"),
                tool("modify_contact"),
            ],
            direct_positive=("_contact_relationship_batch_actor_policy_message",),
        ),
        _case(
            "contact_relationship_batch_result",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Update all my friends as enemies."},
                assistant_call(
                    "plan_contact_relationship_batch_update",
                    {
                        "source_relationship": "friend",
                        "target_relationship": "enemy",
                        "contacts": [],
                    },
                ),
                tool_result(
                    "plan_contact_relationship_batch_update",
                    {
                        "should_call_search_contacts": True,
                        "search_contacts_kwargs": {"relationship": "friend"},
                        "downstream_tool_kwargs_list": [],
                    },
                ),
            ],
            tools=[
                tool(
                    "plan_contact_relationship_batch_update",
                    {
                        "source_relationship": STRING,
                        "target_relationship": STRING,
                        "contacts": RECORDS,
                    },
                ),
                tool("search_contacts"),
                tool("modify_contact"),
            ],
            direct_positive=(
                "_contact_relationship_batch_result_actor_policy_message",
            ),
        ),
        _case(
            "contact_remove_lookup_handoff",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Remove my contact with phone number +15551234567.",
                },
                tool_result(
                    "plan_contact_lookup_query",
                    {
                        "search_contacts_kwargs": {"phone_number": "+15551234567"},
                        "answer_field": "person_id",
                    },
                ),
                tool_result(
                    "search_contacts",
                    [
                        {
                            "person_id": "p1",
                            "name": "Dana",
                            "phone_number": "+15551234567",
                            "is_self": False,
                        }
                    ],
                ),
            ],
            tools=[
                tool("plan_contact_lookup_query"),
                tool("search_contacts"),
                tool("remove_contact"),
            ],
            direct_positive=("_contact_remove_lookup_handoff_actor_policy_message",),
        ),
        _case(
            "contact_remove_success",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Remove my contact with phone number +15551234567.",
                },
                assistant_call(
                    "plan_contact_lookup_query",
                    {"phone_number": "+15551234567"},
                    "plan",
                ),
                tool_result(
                    "plan_contact_lookup_query",
                    {
                        "search_contacts_kwargs": {"phone_number": "+15551234567"},
                        "answer_field": "person_id",
                    },
                    "plan",
                ),
                assistant_call(
                    "search_contacts", {"phone_number": "+15551234567"}, "search"
                ),
                tool_result(
                    "search_contacts",
                    [{"person_id": "p1", "phone_number": "+15551234567"}],
                    "search",
                ),
                assistant_call("remove_contact", {"person_id": "p1"}, "remove"),
                tool_result("remove_contact", None, "remove"),
            ],
            tools=[
                tool("plan_contact_lookup_query"),
                tool("search_contacts"),
                tool("remove_contact"),
            ],
            direct_positive=("_contact_remove_success_actor_policy_message",),
        ),
        _case(
            "device_status_lookup",
            provenance="deterministic_characterization",
            messages=[{"role": "user", "content": "Is wifi on?"}],
            tools=[
                tool(
                    "plan_device_status_lookup",
                    {"user_request": STRING, "visible_state_result": STRING},
                ),
                tool("get_wifi_status"),
                tool("end_conversation"),
            ],
            direct_positive=("_device_status_lookup_actor_policy_message",),
        ),
        _case(
            "location_search_arguments",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Remind me tomorrow at 5 PM to buy milk at Whole Foods."
                    ),
                }
            ],
            tools=[
                LOCATION_PREPARE,
                tool("search_location_around_lat_lon"),
                REMINDER_PREPARE,
                tool("add_reminder"),
            ],
            direct_positive=("_location_search_argument_actor_policy_message",),
        ),
        _case(
            "location_retry_after_state",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Remind me tomorrow at 5 PM to buy milk at Whole Foods."
                    ),
                },
                assistant_call(
                    "prepare_location_search_args",
                    {
                        "user_request": (
                            "Remind me tomorrow at 5 PM to buy milk at Whole Foods."
                        ),
                        "location_phrase": "Whole Foods",
                    },
                    "prepare",
                ),
                tool_result(
                    "prepare_location_search_args",
                    {
                        "should_call_downstream_tool": True,
                        "downstream_tool_name": "search_location_around_lat_lon",
                        "downstream_tool_kwargs": {
                            "location": "Whole Foods",
                            "latitude": 40.0,
                            "longitude": -73.0,
                        },
                    },
                    "prepare",
                ),
                assistant_call(
                    "search_location_around_lat_lon",
                    {"location": "Whole Foods", "latitude": 40.0, "longitude": -73.0},
                    "search",
                ),
                tool_result(
                    "search_location_around_lat_lon",
                    "PermissionError: Location service is not enabled",
                    "search",
                ),
                assistant_call("set_location_service_status", {"on": True}, "set"),
                tool_result("set_location_service_status", None, "set"),
            ],
            tools=[
                LOCATION_PREPARE,
                tool("search_location_around_lat_lon"),
                tool("set_location_service_status"),
            ],
            direct_positive=(
                "_location_search_retry_after_state_actor_policy_message",
            ),
        ),
        _case(
            "message_counterparty_search",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Update the phone number of the last person I sent a message to."
                    ),
                }
            ],
            tools=[
                tool(
                    "plan_message_counterparty_search",
                    {
                        "user_request": STRING,
                        "message_direction": STRING,
                        "selection_mode": STRING,
                        "self_person_id": STRING,
                    },
                ),
                tool("search_contacts"),
                tool("search_messages"),
            ],
            direct_positive=("_message_counterparty_search_actor_policy_message",),
        ),
        _case(
            "message_counterparty_self_handoff",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Update the phone number of the last person I sent a message to."
                    ),
                },
                assistant_call(
                    "plan_message_counterparty_search",
                    {
                        "user_request": "Update the last person I messaged.",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "self_person_id": "",
                    },
                    "plan",
                ),
                tool_result(
                    "plan_message_counterparty_search",
                    {
                        "should_call_search_contacts": True,
                        "search_contacts_kwargs": {"is_self": True},
                    },
                    "plan",
                ),
                assistant_call("search_contacts", {"is_self": True}, "search"),
                tool_result(
                    "search_contacts",
                    [{"person_id": "self-1", "is_self": True}],
                    "search",
                ),
            ],
            tools=[
                tool("plan_message_counterparty_search"),
                tool("search_contacts"),
                tool("search_messages"),
            ],
            direct_positive=(
                "_message_counterparty_self_lookup_handoff_actor_policy_message",
            ),
        ),
        _case(
            "message_counterparty_update_completion",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Change the phone number of the last person I sent a "
                        "message to to +15550001111."
                    ),
                },
                assistant_call(
                    "select_message_counterparty_for_contact_update",
                    {
                        "records": [],
                        "updates": {"phone_number": "+15550001111"},
                        "self_person_id": "self",
                    },
                    "select",
                ),
                tool_result(
                    "select_message_counterparty_for_contact_update",
                    {
                        "downstream_tool_name": "modify_contact",
                        "downstream_tool_kwargs": {
                            "person_id": "p2",
                            "phone_number": "+15550001111",
                        },
                    },
                    "select",
                ),
                assistant_call(
                    "modify_contact",
                    {"person_id": "p2", "phone_number": "+15550001111"},
                    "modify",
                ),
                tool_result("modify_contact", None, "modify"),
            ],
            tools=[
                tool("select_message_counterparty_for_contact_update"),
                tool("modify_contact"),
            ],
            direct_positive=(
                "_message_counterparty_update_completion_actor_policy_message",
            ),
        ),
        _case(
            "reminder_recency_relative_modify",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Move my latest reminder to tomorrow at 5 PM.",
                },
                tool_result(
                    "select_record_by_timestamp_extreme",
                    {
                        "selected_record": {
                            "reminder_id": "r1",
                            "content": "Call Dana",
                            "creation_timestamp": 100.0,
                        }
                    },
                ),
            ],
            tools=[
                tool("select_record_by_timestamp_extreme"),
                tool("get_current_timestamp"),
                tool("timestamp_to_datetime_info"),
                tool("relative_day_time_to_timestamp"),
                tool("modify_reminder"),
            ],
            direct_positive=("_reminder_recency_relative_modify_actor_policy_message",),
        ),
        _case(
            "state_downstream_completion",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Turn on wifi then send hello to +15551234567.",
                },
                tool_result(
                    "plan_device_state_action_sequence_v3",
                    {
                        "continue_original_task_after_sequence": True,
                        "final_response_recommendation": "continue_original_task",
                    },
                    "plan",
                ),
                assistant_call(
                    "send_message_with_phone_number",
                    {"phone_number": "+15551234567", "content": "hello"},
                    "send",
                ),
                tool_result("send_message_with_phone_number", None, "send"),
            ],
            tools=[STATE_HELPER, tool("send_message_with_phone_number")],
            direct_positive=("_state_downstream_completion_actor_policy_message",),
        ),
        _case(
            "reminder_current_datetime",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Remind me to call Dana tomorrow at 5 PM.",
                },
                assistant_call("get_current_timestamp", {}, "timestamp"),
                tool_result("get_current_timestamp", 1000.0, "timestamp"),
            ],
            tools=[
                REMINDER_PREPARE,
                tool("get_current_timestamp"),
                tool("timestamp_to_datetime_info"),
                tool("add_reminder"),
            ],
            direct_positive=("_reminder_current_datetime_actor_policy_message",),
        ),
        _case(
            "reminder_datetime_continuation",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": "Remind me tomorrow at 5 PM to call Dana.",
                },
                assistant_call(
                    "prepare_reminder_creation_args",
                    {
                        "content": "call Dana",
                        "resolved_reminder_timestamp": None,
                        "current_timestamp": 1000.0,
                        "day_offset": 1,
                        "hour": 17,
                        "minute": 0,
                    },
                    "prepare",
                ),
                tool_result(
                    "prepare_reminder_creation_args",
                    {
                        "abstain_reason": (
                            "missing_current_datetime_info_call_timestamp_to_datetime_info"
                        )
                    },
                    "prepare",
                ),
                assistant_call(
                    "timestamp_to_datetime_info", {"timestamp": 1000.0}, "datetime"
                ),
                tool_result(
                    "timestamp_to_datetime_info",
                    {"year": 2026, "month": 1, "day": 1, "hour": 8, "minute": 0},
                    "datetime",
                ),
            ],
            tools=[
                REMINDER_PREPARE,
                tool("timestamp_to_datetime_info"),
                tool("add_reminder"),
            ],
            direct_positive=("_reminder_datetime_continuation_actor_policy_message",),
        ),
        _case(
            "reminder_location_completion",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Remind me tomorrow at 5 PM to buy milk at Whole Foods."
                    ),
                },
                assistant_call(
                    "prepare_reminder_creation_args",
                    {"content": "buy milk", "resolved_reminder_timestamp": 90000.0},
                    "prepare",
                ),
                tool_result(
                    "prepare_reminder_creation_args",
                    {
                        "location_status": "lookup_pending",
                        "abstain_reason": "location_lookup_pending",
                    },
                    "prepare",
                ),
                assistant_call(
                    "search_location_around_lat_lon",
                    {"location": "Whole Foods", "latitude": 40.0, "longitude": -73.0},
                    "search",
                ),
                tool_result(
                    "search_location_around_lat_lon",
                    [{"name": "Whole Foods", "latitude": 40.1, "longitude": -73.1}],
                    "search",
                ),
            ],
            tools=[
                REMINDER_PREPARE,
                tool("search_location_around_lat_lon"),
                tool("add_reminder"),
            ],
            direct_positive=("_reminder_location_completion_actor_policy_message",),
        ),
        _case(
            "reminder_location_batch",
            provenance="deterministic_characterization",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Remind me tomorrow at 5 PM to buy milk at Whole Foods."
                    ),
                }
            ],
            tools=[
                LOCATION_PREPARE,
                tool("search_location_around_lat_lon"),
                tool("get_current_timestamp"),
                tool("timestamp_to_datetime_info"),
                tool("relative_day_time_to_timestamp"),
                REMINDER_PREPARE,
                tool("add_reminder"),
            ],
            direct_positive=("_reminder_location_batch_actor_policy_message",),
        ),
        _case(
            "contact_creation_completion",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Add Dana as a contact."},
                assistant_call(
                    "prepare_add_contact_args",
                    {"user_request": "Add Dana +15551234567"},
                    "prepare",
                ),
                tool_result(
                    "prepare_add_contact_args",
                    {
                        "downstream_tool_kwargs": {
                            "name": "Dana",
                            "phone_number": "+15551234567",
                        }
                    },
                    "prepare",
                ),
                assistant_call(
                    "add_contact",
                    {"name": "Dana", "phone_number": "+15551234567"},
                    "add",
                ),
                tool_result("add_contact", None, "add"),
            ],
            tools=[
                tool("prepare_add_contact_args", {"user_request": STRING}),
                tool("add_contact"),
            ],
            direct_positive=("_contact_creation_completion_actor_policy_message",),
        ),
        _case(
            "direct_contact_completion",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Remove contact p1."},
                assistant_call(
                    "prepare_direct_contact_action_args",
                    {"user_request": "Remove contact p1"},
                    "prepare",
                ),
                tool_result(
                    "prepare_direct_contact_action_args",
                    {
                        "downstream_tool_name": "remove_contact",
                        "downstream_tool_kwargs": {"person_id": "p1"},
                    },
                    "prepare",
                ),
                assistant_call("remove_contact", {"person_id": "p1"}, "remove"),
                tool_result("remove_contact", None, "remove"),
            ],
            tools=[
                tool("prepare_direct_contact_action_args", {"user_request": STRING}),
                tool("remove_contact"),
            ],
            direct_positive=("_direct_contact_action_completion_actor_policy_message",),
        ),
        _case(
            "message_contact_completion",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Send Dana the message hello."},
                assistant_call(
                    "plan_send_message_contact_lookup",
                    {"recipient_name": "Dana", "message_content": "hello"},
                    "plan",
                ),
                tool_result(
                    "plan_send_message_contact_lookup",
                    {
                        "downstream_tool_name": "search_contacts",
                        "downstream_tool_kwargs": {"name": "Dana"},
                    },
                    "plan",
                ),
                assistant_call(
                    "send_message_with_phone_number",
                    {"phone_number": "+15551234567", "content": "hello"},
                    "send",
                ),
                tool_result("send_message_with_phone_number", None, "send"),
            ],
            tools=[
                tool(
                    "plan_send_message_contact_lookup",
                    {"recipient_name": STRING, "message_content": STRING},
                ),
                tool("send_message_with_phone_number"),
            ],
            direct_positive=(
                "_message_contact_lookup_completion_actor_policy_message",
            ),
        ),
        _case(
            "next_service_direct_completion",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Turn on wifi."},
                assistant_call(
                    "next_service_tool_call",
                    {"user_request": "Turn on wifi.", "target_service": "wifi"},
                    "plan",
                ),
                tool_result(
                    "next_service_tool_call",
                    {
                        "target_service": "wifi",
                        "tool_name": "set_wifi_status",
                        "should_call": True,
                        "arguments": {"on": True},
                    },
                    "plan",
                ),
                assistant_call("set_wifi_status", {"on": True}, "set"),
                tool_result("set_wifi_status", None, "set"),
            ],
            tools=[
                tool(
                    "next_service_tool_call",
                    {
                        "user_request": STRING,
                        "target_service": STRING,
                        "tool_name": STRING,
                        "should_call": BOOLEAN,
                    },
                ),
                tool("set_wifi_status"),
            ],
            direct_positive=("_next_service_direct_completion_policy_message",),
        ),
        _case(
            "state_completion_clarification",
            provenance="deterministic_characterization",
            messages=[
                {"role": "user", "content": "Turn on wifi."},
                assistant_call(
                    "plan_device_state_action_sequence_v3",
                    {"user_request": "Turn on wifi.", "visible_state_or_error": ""},
                    "plan",
                ),
                tool_result(
                    "plan_device_state_action_sequence_v3",
                    {
                        "action_sequence": [
                            {"tool_name": "set_wifi_status", "arguments": {"on": True}}
                        ],
                        "final_response_recommendation": "Wifi has been turned on.",
                        "continue_original_task_after_sequence": False,
                    },
                    "plan",
                ),
                assistant_call("set_wifi_status", {"on": True}, "set"),
                tool_result("set_wifi_status", None, "set"),
                {"role": "user", "content": "I meant wifi should be on."},
            ],
            tools=[STATE_HELPER, tool("set_wifi_status")],
            direct_positive=("_state_action_completion_clarification_policy_message",),
        ),
        _case(
            "helper_answer_retention",
            provenance="historical_test_seed",
            source_test="test_helper_answer_retention_policy_preserves_service_distance",
            messages=[
                {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
                tool_result(
                    "extract_service_answer_field",
                    {
                        "answer_value": "67.96",
                        "answer_kind": "distance",
                        "answer_unit": "km",
                        "abstain_reason": "",
                    },
                ),
                {
                    "role": "assistant",
                    "content": "You are approximately 67.96 kilometers away.",
                },
                {
                    "role": "user",
                    "content": "Alright, thanks. You can end the conversation now.",
                },
            ],
            tools=[],
            direct_positive=("_helper_answer_retention_actor_policy_message",),
        ),
        _case(
            "device_status_answer_retention",
            provenance="historical_test_seed",
            source_test="test_device_status_retention_policy_requires_exact_helper_recommendation",
            messages=[
                {"role": "user", "content": "Is my wifi on?"},
                tool_result(
                    "plan_device_status_lookup",
                    {
                        "tool_name": "",
                        "arguments": {},
                        "should_call": False,
                        "target_service": "wifi",
                        "status_value": True,
                        "final_answer_recommendation": "Wifi is on.",
                    },
                ),
                {"role": "assistant", "content": "Wifi is on."},
                {"role": "user", "content": "I'm all set for now. Thanks!"},
            ],
            tools=[],
            direct_positive=("_device_status_answer_retention_actor_policy_message",),
        ),
    ]


def _envelope_edge_cases() -> list[dict[str, Any]]:
    safe_helper = tool(
        "prepare_safe_action_or_abstain",
        {
            "user_request": STRING,
            "requested_action": STRING,
            "target_identifier": STRING,
            "required_original_tools": {"type": "array"},
            "available_original_tools": {"type": "array"},
            "visible_records_count": INTEGER,
        },
        description="Prepare a safe action or abstain on insufficient information.",
    )
    return [
        _case(
            "not_given_tools",
            provenance="deterministic_envelope_edge",
            messages=[{"role": "user", "content": "Answer without tools."}],
            tools="NOT_GIVEN",
            direct_positive=("_shared_task_closure_actor_policy_message",),
        ),
        _case(
            "transient_named_choice_falls_back_naturally",
            provenance="deterministic_envelope_edge",
            messages=[
                {
                    "role": "user",
                    "content": "Add Dana as a contact with phone number +15551234567.",
                }
            ],
            tools=[
                tool("prepare_add_contact_args", {"user_request": STRING}),
                tool("add_contact"),
            ],
            response_mode="transient_named_then_natural",
        ),
        _case(
            "safe_abstention_post_response_grounding",
            provenance="deterministic_envelope_edge",
            messages=[
                {
                    "role": "user",
                    "content": "Remove the contact with phone number +15550100.",
                }
            ],
            tools=[safe_helper, tool("search_contacts"), tool("remove_contact")],
            response_mode="safe_abstention_tool_call",
        ),
        _case(
            "near_miss_absolute_without_content",
            provenance="deterministic_near_miss",
            messages=[
                {
                    "role": "user",
                    "content": "Add a reminder on October 15, 2026 at 3 PM.",
                }
            ],
            tools=[
                tool("datetime_info_to_timestamp"),
                REMINDER_PREPARE,
                tool("add_reminder"),
            ],
            direct_positive=("_absolute_reminder_timestamp_actor_policy_message",),
            direct_absent=("_add_contact_argument_actor_policy_message",),
        ),
        _case(
            "near_miss_location_without_reminder",
            provenance="deterministic_near_miss",
            messages=[{"role": "user", "content": "Find Whole Foods near me."}],
            tools=[LOCATION_PREPARE, tool("search_location_around_lat_lon")],
            direct_absent=("_location_search_argument_actor_policy_message",),
        ),
        _case(
            "near_miss_status_helper_for_mutation",
            provenance="deterministic_near_miss",
            messages=[{"role": "user", "content": "Turn wifi on."}],
            tools=[tool("plan_device_status_lookup"), tool("set_wifi_status")],
            direct_positive=("_device_status_lookup_actor_policy_message",),
            direct_absent=("_device_status_answer_retention_actor_policy_message",),
        ),
    ]
