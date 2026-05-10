import json

from openai import NOT_GIVEN

from sage_ts.adapters.openai_toolsandbox_roles import (
    _derived_actor_policy_message,
    _derived_value_tool_names,
    _message_already_called_tool,
    _messages_show_prior_structured_payload,
    _messages_show_prior_tool_call,
    _messages_show_tool_error,
    _state_action_sequence_bridge_completion,
    _tool_names,
)
from tool_sandbox.common.execution_context import (
    ExecutionContext,
    ScenarioCategories,
    new_context,
)


def test_tool_names_extracts_openai_function_names() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "next_dependency_precondition_call"},
        }
    ]

    assert _tool_names(tools) == {"next_dependency_precondition_call"}
    assert _tool_names(NOT_GIVEN) == set()


def test_message_helpers_detect_prior_tool_call_and_tool_error() -> None:
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "next_dependency_precondition_call",
                        "arguments": "{}",
                    }
                }
            ],
        },
        {
            "role": "tool",
            "content": "PermissionError: Low battery mode blocks this service.",
        },
    ]

    assert _message_already_called_tool(messages, "next_dependency_precondition_call")
    assert _messages_show_tool_error(messages)
    assert _messages_show_prior_tool_call(
        messages, {"next_dependency_precondition_call"}
    )
    assert not _messages_show_prior_tool_call(messages, {"search_contacts"})
    assert _messages_show_prior_tool_call(messages, set())


def test_derived_policy_supports_payload_plus_scalar_selector_inputs() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "resolve_location_lookup_field",
                "description": "Extract a deterministic address or phone field.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_payload": {"type": "object"},
                        "requested_field": {"type": "string"},
                    },
                },
            },
        }
    ]
    messages = [
        {
            "role": "tool",
            "name": "search_lat_lon",
            "content": "Apple Park 1 Apple Park Way Cupertino, CA 95014 United States",
        }
    ]

    assert _derived_value_tool_names(tools) == {"resolve_location_lookup_field"}
    assert _messages_show_prior_structured_payload(messages)
    policy = _derived_actor_policy_message(messages, tools)
    assert policy is not None
    assert "autofill" in policy["content"]
    assert "requested_field" in policy["content"]


def _state_sequence_tool(
    name: str = "plan_device_state_action_sequence_v3",
) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "State action sequence v3 helper.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {"type": "string"},
                    "visible_state_or_error": {"type": "string"},
                },
            },
        },
    }


def _tool_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": f"call_{name}",
                "function": {"name": name, "arguments": json.dumps(arguments)},
                "type": "function",
            }
        ],
    }


def test_state_action_sequence_bridge_advances_ordered_setters() -> None:
    plan_payload = {
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
    }
    messages = [
        {"role": "user", "content": "Turn on cellular service."},
        _tool_call(
            "plan_device_state_action_sequence_v3",
            {"user_request": "Turn on cellular service."},
        ),
        {
            "role": "tool",
            "name": "plan_device_state_action_sequence_v3",
            "content": json.dumps(plan_payload),
        },
    ]

    first = _state_action_sequence_bridge_completion(
        messages,
        [_state_sequence_tool()],
        model_name="gpt-4o-mini",
    )

    assert first is not None
    first_tool_calls = first.choices[0].message.tool_calls
    assert first_tool_calls is not None
    call = first_tool_calls[0]
    assert call.function.name == "set_low_battery_mode_status"

    messages.extend(
        [
            _tool_call("set_low_battery_mode_status", {"on": False}),
            {
                "role": "tool",
                "tool_call_id": "call_set_low_battery_mode_status",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
        ]
    )
    second = _state_action_sequence_bridge_completion(
        messages,
        [_state_sequence_tool()],
        model_name="gpt-4o-mini",
    )

    assert second is not None
    second_tool_calls = second.choices[0].message.tool_calls
    assert second_tool_calls is not None
    call = second_tool_calls[0]
    assert call.function.name == "set_cellular_service_status"

    messages.extend(
        [
            _tool_call("set_cellular_service_status", {"on": True}),
            {
                "role": "tool",
                "tool_call_id": "call_set_cellular_service_status",
                "name": "set_cellular_service_status",
                "content": "None",
            },
        ]
    )
    assert (
        _state_action_sequence_bridge_completion(
            messages,
            [_state_sequence_tool()],
            model_name="gpt-4o-mini",
        )
        is None
    )


def test_state_action_sequence_bridge_uses_agent_facing_names_when_scrambled() -> None:
    context = ExecutionContext(
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED]
    )
    context._actual_to_scrambled_tool_name["plan_device_state_action_sequence_v3"] = (
        "generated_tools_5"
    )
    context._scrambled_to_actual_tool_name["generated_tools_5"] = (
        "plan_device_state_action_sequence_v3"
    )
    plan_payload = {
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
    }
    messages = [
        {"role": "user", "content": "Turn on cellular service."},
        _tool_call("generated_tools_5", {"user_request": "Turn on cellular service."}),
        {
            "role": "tool",
            "name": "generated_tools_5",
            "content": json.dumps(plan_payload),
        },
    ]
    tools = [_state_sequence_tool("generated_tools_5")]

    with new_context(context):
        first = _state_action_sequence_bridge_completion(
            messages,
            tools,
            model_name="gpt-4o-mini",
        )

        assert first is not None
        first_tool_calls = first.choices[0].message.tool_calls
        assert first_tool_calls is not None
        first_call = first_tool_calls[0]
        assert first_call.function.name == "setting_7"

        messages.extend(
            [
                _tool_call("setting_7", {"on": False}),
                {
                    "role": "tool",
                    "tool_call_id": "call_setting_7",
                    "name": "setting_7",
                    "content": "None",
                },
            ]
        )
        second = _state_action_sequence_bridge_completion(
            messages,
            tools,
            model_name="gpt-4o-mini",
        )

        assert second is not None
        second_tool_calls = second.choices[0].message.tool_calls
        assert second_tool_calls is not None
        second_call = second_tool_calls[0]
        assert second_call.function.name == "setting_5"
