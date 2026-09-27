"""Exact actor transcript-scanning contracts for structural refactors.

This validation-only probe exercises the private compatibility wrappers that
read OpenAI-format messages. It deliberately includes malformed values and a
recording name normalizer because call order and short-circuit behavior are
part of the frozen implementation contract.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from typing import Any


def _wire(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    if isinstance(value, set):
        return sorted((_wire(item) for item in value), key=repr)
    return str(value)


def _tool(name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Replay tool {name}.",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _tool_call(
    name: str,
    arguments: Mapping[str, Any] | str | None = None,
    *,
    call_id: str = "call-1",
) -> dict[str, Any]:
    raw_arguments = (
        arguments
        if isinstance(arguments, str)
        else json.dumps(dict(arguments or {}), separators=(",", ":"))
    )
    return {
        "id": call_id,
        "function": {"name": name, "arguments": raw_arguments},
    }


def _standard_messages() -> list[Any]:
    return [
        {"role": "system", "content": "system", "name": "system_noise"},
        {"role": "user", "content": "First request"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-contact",
                    "function": {
                        "name": "functions.search_contacts",
                        "arguments": '{"query":"Ada"}',
                    },
                },
                {
                    "id": "call-generated",
                    "function": {
                        "name": "generated_helper",
                        "arguments": '{"records":[1]}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "name": "functions.search_contacts",
            "tool_call_id": "call-contact",
            "content": "{'person_id': 'person-1', 'name': 'Ada'}",
        },
        {"role": "assistant", "content": "Intermediate answer."},
        {"role": "user", "content": ""},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-send",
                    "function": {
                        "name": "send_message_with_phone_number",
                        "arguments": '{"phone_number":"+15550100","content":"Hi"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "send_message_with_phone_number",
            "tool_call_id": "call-send",
            "content": "success",
        },
        {
            "role": "tool",
            "name": "calculate_lat_lon_distance",
            "content": "12.5",
        },
        {"role": "tool", "name": "get_current_timestamp", "content": "123.5"},
        {"role": "assistant", "content": "tail", "name": "assistant_noise"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": '{"person_id":"person-final"}',
        },
    ]


def _message_vectors() -> dict[str, list[Any]]:
    standard = _standard_messages()
    tuple_calls = copy.deepcopy(standard)
    tuple_calls[2]["tool_calls"] = tuple(tuple_calls[2]["tool_calls"])
    tuple_calls[6]["tool_calls"] = tuple(tuple_calls[6]["tool_calls"])
    malformed = [
        {"role": "user", "content": None},
        {"role": "assistant", "tool_calls": "not-a-list"},
        {
            "role": "assistant",
            "tool_calls": [None, {"function": []}, {"function": {"name": 7}}],
        },
        {"role": "tool", "name": None, "content": "not literal or json"},
        {"role": "tool", "name": "get_current_timestamp", "content": "none"},
    ]
    normalizer_failure = [
        {"role": "user", "content": "request"},
        {"role": "assistant", "name": "explode", "content": "noise"},
        {"role": "tool", "name": "search_contacts", "content": "{}"},
    ]
    non_mapping_message = [
        {"role": "user", "content": "request"},
        "not-a-message-mapping",
    ]
    return {
        "empty": [],
        "standard": standard,
        "policy_augmented": [
            *copy.deepcopy(standard),
            {"role": "system", "content": "[policy] continue exactly"},
        ],
        "tuple_tool_calls": tuple_calls,
        "malformed_nested_values": malformed,
        "normalizer_failure": normalizer_failure,
        "non_mapping_message": non_mapping_message,
    }


def _recorded_call(
    actor: Any,
    messages: list[Any],
    operation: Callable[[], Any],
) -> dict[str, Any]:
    original_normalizer = actor._execution_facing_tool_name
    normalizer_calls: list[str] = []
    before = copy.deepcopy(messages)

    def normalize(value: str) -> str:
        text = str(value)
        normalizer_calls.append(text)
        if text == "explode":
            raise LookupError("recorded normalizer failure")
        aliases = {
            "functions.search_contacts": "search_contacts",
            "agent_search_contacts": "search_contacts",
        }
        return aliases.get(text, text.removeprefix("functions."))

    actor._execution_facing_tool_name = normalize
    try:
        try:
            value = operation()
        except Exception as error:  # noqa: BLE001 - exception behavior is frozen.
            outcome = {
                "status": "raised",
                "exception_type": type(error).__name__,
                "message": str(error),
            }
        else:
            outcome = {
                "status": "returned",
                "python_type": type(value).__name__,
                "value": _wire(value),
            }
    finally:
        actor._execution_facing_tool_name = original_normalizer
    return {
        "outcome": outcome,
        "normalizer_calls": normalizer_calls,
        "messages_unchanged": messages == before,
        "messages_after": _wire(messages),
    }


def _recorded_structural_call(
    actor: Any,
    inputs: dict[str, Any],
    operation: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Record exact helper behavior without mutating the supplied fixtures."""

    original_normalizer = actor._execution_facing_tool_name
    normalizer_calls: list[str] = []
    before = copy.deepcopy(inputs)

    def normalize(value: str) -> str:
        text = str(value)
        normalizer_calls.append(text)
        if text == "explode":
            raise LookupError("recorded normalizer failure")
        aliases = {
            "functions.search_contacts": "search_contacts",
            "agent_search_contacts": "search_contacts",
        }
        return aliases.get(text, text.removeprefix("functions."))

    actor._execution_facing_tool_name = normalize
    try:
        try:
            value = operation(inputs)
        except Exception as error:  # noqa: BLE001 - exception behavior is frozen.
            outcome = {
                "status": "raised",
                "exception_type": type(error).__name__,
                "message": str(error),
            }
        else:
            outcome = {
                "status": "returned",
                "python_type": type(value).__name__,
                "value": _wire(value),
            }
    finally:
        actor._execution_facing_tool_name = original_normalizer
    return {
        "outcome": outcome,
        "normalizer_calls": normalizer_calls,
        "inputs_unchanged": inputs == before,
        "inputs_after": _wire(inputs),
    }


def _operations(
    actor: Any,
    messages: list[Any],
    tools: list[dict[str, Any]],
) -> dict[str, Callable[[], Any]]:
    return {
        "latest_user_request_text": lambda: actor._latest_user_request_text(messages),
        "first_user_request_text": lambda: actor._first_user_request_text(messages),
        "all_user_texts": lambda: actor._all_user_texts(messages),
        "latest_user_index": lambda: actor._latest_user_index(messages),
        "latest_any_tool_message_index": lambda: actor._latest_any_tool_message_index(
            messages
        ),
        "last_tool_result_index": lambda: actor._last_tool_result_index(
            messages, "search_contacts"
        ),
        "latest_tool_success_content": lambda: actor._latest_tool_success_content(
            messages
        ),
        "latest_tool_payload_excluding_latest": lambda: (
            actor._latest_tool_payload_by_name(messages, "search_contacts")
        ),
        "latest_tool_message": lambda: actor._latest_tool_message(
            messages, "search_contacts"
        ),
        "latest_tool_payload_including_latest": lambda: (
            actor._latest_tool_payload_by_name_including_latest(
                messages, "search_contacts"
            )
        ),
        "latest_tool_float": lambda: actor._latest_tool_float_by_name_including_latest(
            messages, "get_current_timestamp"
        ),
        "latest_tool_message_index": lambda: actor._latest_tool_message_index(
            messages, {"search_contacts"}
        ),
        "latest_tool_is": lambda: actor._latest_tool_is(messages, "search_contacts"),
        "latest_tool_content": lambda: actor._latest_tool_content(
            messages, "search_contacts"
        ),
        "latest_service_answer_payload": lambda: actor._latest_service_answer_payload(
            messages
        ),
        "message_already_called_tool": lambda: actor._message_already_called_tool(
            messages, "search_contacts"
        ),
        "last_tool_call_index": lambda: actor._last_tool_call_index(
            messages, "search_contacts"
        ),
        "latest_prior_tool_call_arguments": lambda: (
            actor._latest_prior_tool_call_arguments(messages, "search_contacts")
        ),
        "called_tool_after_latest_user": lambda: actor._called_tool_after_latest_user(
            messages, "send_message_with_phone_number"
        ),
        "assistant_called_tool_after_index": lambda: (
            actor._assistant_called_tool_after_index(
                messages, "send_message_with_phone_number", 1
            )
        ),
        "message_called_generated_after_index": lambda: (
            actor._message_called_generated_tool_after_index(messages, tools, 0)
        ),
        "message_called_execution_after_tool": lambda: (
            actor._message_called_execution_tool_after_tool(
                messages,
                "send_message_with_phone_number",
                {"search_contacts"},
            )
        ),
        "latest_successful_crud_tool_call": lambda: (
            actor._latest_successful_crud_tool_call(messages)
        ),
        "latest_successful_send_message_tool_call": lambda: (
            actor._latest_successful_send_message_tool_call(messages)
        ),
    }


def _specialized_structural_cases(actor: Any) -> dict[str, Any]:
    """Freeze correlation, bounded-scan, and precedence quirks used by policy."""

    generated_tools = [_tool("generated_helper")]
    record_source_inputs = {
        "generated_then_contact_records": {
            "messages": [
                {"role": "user", "content": "Find Ada"},
                {
                    "role": "assistant",
                    "tool_calls": [_tool_call("generated_helper")],
                },
                {
                    "role": "tool",
                    "name": "functions.search_contacts",
                    "content": "[{'person_id': 'person-1'}]",
                },
                {"role": "tool", "name": "search_messages", "content": "[]"},
            ],
            "tools": generated_tools,
            "require_prior_generated_call": True,
        },
        "records_without_prior_generated_call": {
            "messages": [
                {
                    "role": "tool",
                    "name": "search_contacts",
                    "content": '[{"person_id":"person-1"}]',
                }
            ],
            "tools": generated_tools,
            "require_prior_generated_call": True,
        },
        "records_allowed_without_prior_generated_call": {
            "messages": [
                {
                    "role": "tool",
                    "name": "search_contacts",
                    "content": '[{"person_id":"person-1"}]',
                }
            ],
            "tools": generated_tools,
            "require_prior_generated_call": False,
        },
        "generated_then_extraction_source": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [_tool_call("generated_helper")],
                },
                {
                    "role": "tool",
                    "name": "search_stock",
                    "content": '{"ticker":"SAGE","price":42.5}',
                },
            ],
            "tools": generated_tools,
            "require_prior_generated_call": True,
        },
        "malformed_and_empty_records": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [None, {"function": []}, _tool_call("other")],
                },
                {"role": "tool", "name": "search_reminder", "content": "[]"},
                {"role": "tool", "name": "search_contacts", "content": "bad"},
            ],
            "tools": generated_tools,
            "require_prior_generated_call": False,
        },
    }
    record_sources = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._latest_record_source_after_generated_call(
                values["messages"],
                values["tools"],
                require_prior_generated_call=values["require_prior_generated_call"],
            ),
        )
        for case_id, inputs in record_source_inputs.items()
    }

    setting_inputs = {
        "matching_correlated_success": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "functions.set_wifi_status",
                            {"on": True},
                            call_id="wifi-1",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "tool_call_id": "wifi-1",
                    "content": "None",
                },
            ],
            "action": {"tool_name": "set_wifi_status", "arguments": {"on": True}},
        },
        "matching_correlated_failure": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call("set_wifi_status", {"on": True}, call_id="wifi-2")
                    ],
                },
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "tool_call_id": "wifi-2",
                    "content": "Error: failed",
                },
            ],
            "action": {"tool_name": "set_wifi_status", "arguments": {"on": True}},
        },
        "successful_result_but_arguments_differ": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call("set_wifi_status", {"on": False}, call_id="wifi-3")
                    ],
                },
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "tool_call_id": "wifi-3",
                    "content": "null",
                },
            ],
            "action": {"tool_name": "set_wifi_status", "arguments": {"on": True}},
        },
        "uncorrelated_named_success": {
            "messages": [{"role": "tool", "name": "set_wifi_status", "content": ""}],
            "action": {"tool_name": "set_wifi_status", "arguments": {"on": True}},
        },
        "invalid_action": {
            "messages": [],
            "action": {"tool_name": "search_contacts", "arguments": {"query": "Ada"}},
        },
    }
    satisfied_settings = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._setting_action_already_satisfied(
                values["messages"], values["action"]
            ),
        )
        for case_id, inputs in setting_inputs.items()
    }

    precondition_inputs = {
        "correlated_native_retry": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "search_weather_around_lat_lon",
                            {"latitude": 1.0, "longitude": 2.0},
                            call_id="weather-1",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "search_weather_around_lat_lon",
                    "tool_call_id": "weather-1",
                    "content": "Wifi is not enabled",
                },
            ]
        },
        "uncorrelated_native_retry": {
            "messages": [
                {
                    "role": "tool",
                    "name": "search_location_around_lat_lon",
                    "content": "Location service is not enabled",
                }
            ]
        },
        "setting_setter_is_excluded": {
            "messages": [
                {
                    "role": "tool",
                    "name": "set_wifi_status",
                    "content": "blocked by low battery",
                }
            ]
        },
        "error_outside_sixteen_message_window": {
            "messages": [
                {
                    "role": "tool",
                    "name": "search_weather_around_lat_lon",
                    "content": "Wifi is not enabled",
                },
                *[
                    {"role": "system", "content": f"padding-{index}"}
                    for index in range(16)
                ],
            ]
        },
        "non_precondition_error": {
            "messages": [
                {
                    "role": "tool",
                    "name": "search_weather_around_lat_lon",
                    "content": "HTTP 500",
                }
            ]
        },
    }
    precondition_retries = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._latest_non_setting_state_precondition_retry_call(
                values["messages"]
            ),
        )
        for case_id, inputs in precondition_inputs.items()
    }

    timestamp_inputs = {
        "correlated_timestamp_within_tolerance": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "timestamp_to_datetime_info",
                            {"timestamp": 100.25},
                            call_id="time-1",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "tool_call_id": "time-1",
                    "content": "{'year': 2026, 'month': 9, 'day': 27}",
                },
            ],
            "timestamp": 100.9,
        },
        "correlated_timestamp_outside_tolerance": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "timestamp_to_datetime_info",
                            {"timestamp": 100.25},
                            call_id="time-2",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "tool_call_id": "time-2",
                    "content": '{"year":2026}',
                },
            ],
            "timestamp": 102.0,
        },
        "latest_empty_payload_shadows_earlier_payload": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "timestamp_to_datetime_info",
                            {"timestamp": 100.0},
                            call_id="time-old",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "tool_call_id": "time-old",
                    "content": '{"year":2026}',
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "timestamp_to_datetime_info",
                            {"timestamp": 100.0},
                            call_id="time-new",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "tool_call_id": "time-new",
                    "content": "{}",
                },
            ],
            "timestamp": 100.0,
        },
        "invalid_call_arguments": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "timestamp_to_datetime_info", "not-json", call_id="time-3"
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "timestamp_to_datetime_info",
                    "tool_call_id": "time-3",
                    "content": '{"year":2026}',
                },
            ],
            "timestamp": 100.0,
        },
        "non_mapping_message_raises": {
            "messages": ["not-a-message"],
            "timestamp": 100.0,
        },
    }
    timestamp_lookups = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._timestamp_to_datetime_info_for_timestamp(
                values["messages"], values["timestamp"]
            ),
        )
        for case_id, inputs in timestamp_inputs.items()
    }

    reminder_inputs = {
        "matching_reason_returns_correlated_args": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "prepare_reminder_creation_args",
                            {"content": "Call Ada", "reminder_timestamp": 123.0},
                            call_id="reminder-1",
                        )
                    ],
                },
                {
                    "role": "tool",
                    "name": "prepare_reminder_creation_args",
                    "tool_call_id": "reminder-1",
                    "content": '{"abstain_reason":"missing_time"}',
                },
            ],
            "abstain_reason": "missing_time",
        },
        "reason_mismatch": {
            "messages": [
                {
                    "role": "tool",
                    "name": "prepare_reminder_creation_args",
                    "content": '{"abstain_reason":"missing_location"}',
                }
            ],
            "abstain_reason": "missing_time",
        },
        "matching_uncorrelated_result_returns_empty_args": {
            "messages": [
                {
                    "role": "tool",
                    "name": "prepare_reminder_creation_args",
                    "tool_call_id": "unknown",
                    "content": '{"abstain_reason":"missing_time"}',
                }
            ],
            "abstain_reason": "missing_time",
        },
        "tuple_tool_calls_are_scanned": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": (
                        _tool_call(
                            "prepare_reminder_creation_args",
                            {"content": "Call Ada"},
                            call_id="reminder-2",
                        ),
                    ),
                },
                {
                    "role": "tool",
                    "name": "prepare_reminder_creation_args",
                    "tool_call_id": "reminder-2",
                    "content": '{"abstain_reason":"missing_time"}',
                },
            ],
            "abstain_reason": "missing_time",
        },
    }
    reminder_args = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._latest_reminder_creation_args_for_abstain_reason(
                values["messages"], values["abstain_reason"]
            ),
        )
        for case_id, inputs in reminder_inputs.items()
    }

    holiday_inputs = {
        "latest_known_user_holiday_wins": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call("search_holiday", {"holiday_name": "Christmas"})
                    ],
                },
                {"role": "user", "content": "What date is Thanksgiving?"},
            ]
        },
        "holiday_from_search_call_arguments": {
            "messages": [
                {"role": "user", "content": "Find that holiday"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            "functions.search_holiday",
                            {"holiday_name": "Christmas"},
                        )
                    ],
                },
            ]
        },
        "unknown_holiday": {
            "messages": [
                {"role": "user", "content": "Find Founders Day"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call("search_holiday", {"holiday_name": "Founders Day"})
                    ],
                },
            ]
        },
        "tuple_tool_calls_are_ignored": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": (
                        _tool_call("search_holiday", {"holiday_name": "New Years"}),
                    ),
                }
            ]
        },
        "normalizer_failure_is_visible": {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call("explode", {"holiday_name": "Christmas"})
                    ],
                }
            ]
        },
    }
    holiday_labels = {
        case_id: _recorded_structural_call(
            actor,
            inputs,
            lambda values: actor._holiday_context_label(values["messages"]),
        )
        for case_id, inputs in holiday_inputs.items()
    }

    return {
        "latest_record_source_after_generated_call": record_sources,
        "setting_action_already_satisfied": satisfied_settings,
        "latest_non_setting_state_precondition_retry_call": precondition_retries,
        "timestamp_to_datetime_info_for_timestamp": timestamp_lookups,
        "latest_reminder_creation_args_for_abstain_reason": reminder_args,
        "holiday_context_label": holiday_labels,
    }


def run_probe(_root: Any) -> dict[str, Any]:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    tools = [_tool("generated_helper")]
    cases: dict[str, Any] = {}
    for vector_id, messages in _message_vectors().items():
        cases[vector_id] = {
            operation_id: _recorded_call(actor, messages, operation)
            for operation_id, operation in _operations(actor, messages, tools).items()
        }

    payload_cases = {
        "mapping_python_literal": "{'a': 1, 'nested': {'b': 2}}",
        "mapping_json": '{"a":1,"items":[2,3]}',
        "mapping_direct": {"direct": True},
        "sequence_python_literal": "[{'a': 1}, 2]",
        "sequence_json": '[{"a":1},2]',
        "scalar": "12.5",
        "blank": "  ",
        "invalid": "not literal or json",
    }
    parsed_payloads = {
        case_id: {
            "mapping": _wire(actor._parse_mapping_payload(value)),
            "sequence": _wire(actor._parse_sequence_payload(value)),
        }
        for case_id, value in payload_cases.items()
    }
    return {
        "schema_version": 2,
        "message_cases": cases,
        "payload_parsers": parsed_payloads,
        "specialized_structural_cases": _specialized_structural_cases(actor),
    }
