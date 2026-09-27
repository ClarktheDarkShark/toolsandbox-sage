"""Exact actor transcript-scanning contracts for structural refactors.

This validation-only probe exercises the private compatibility wrappers that
read OpenAI-format messages. It deliberately includes malformed values and a
recording name normalizer because call order and short-circuit behavior are
part of the frozen implementation contract.
"""

from __future__ import annotations

import copy
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
        "schema_version": 1,
        "message_cases": cases,
        "payload_parsers": parsed_payloads,
    }
