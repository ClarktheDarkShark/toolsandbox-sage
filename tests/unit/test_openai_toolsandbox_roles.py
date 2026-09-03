import json
from types import SimpleNamespace

from openai import NOT_GIVEN

import sage_ts.adapters.openai_toolsandbox_roles as toolsandbox_roles
from sage_ts.adapters.openai_toolsandbox_roles import (
    _contact_lookup_answer_actor_policy_message,
    _declared_service_answer_producers,
    _derived_actor_policy_message,
    _derived_value_tool_names,
    _device_status_answer_retention_actor_policy_message,
    _dynamic_generated_tool_schema_filter,
    _generated_downstream_original_tool_choice,
    _generated_tool_abstain_continuation_actor_policy_message,
    _generated_tool_choice_priority,
    _generated_tool_inputs_ready_for_current_turn,
    _generated_tool_new_information_since_call,
    _generated_tool_prerequisite_choice,
    _generated_tool_uses_native_action,
    _helper_answer_completion_actor_policy_message,
    _helper_answer_completion_tool_free_turn,
    _helper_answer_retention_actor_policy_message,
    _helper_output_handoff_actor_policy_message,
    _hide_wrapped_native_action_schemas,
    _location_search_retry_after_coordinates_actor_policy_message,
    _message_counterparty_selector_setup_actor_policy_message,
    _messages_show_prior_structured_payload,
    _native_action_tool_actor_policy_message,
    _relationship_batch_request,
    _relative_time_actor_policy_message,
    _reminder_recency_search_result_actor_policy_message,
    _reminder_recency_workflow_tool_choice,
    _scheduling_timestamp_actor_policy_message,
    _search_window_result_handoff_actor_policy_message,
    _state_action_planner_tool_choice,
    _state_action_sequence_completion_policy_message,
    _tool_name_for_call,
    _tool_names,
    _tool_names_execution_facing,
    _visible_location_phrase_from_user_request,
)


def _first_tool_call(completion):
    tool_calls = completion.choices[0].message.tool_calls
    assert tool_calls
    return tool_calls[0]


def test_selector_actor_policy_supports_non_native_tool_bundle() -> None:
    messages = [
        {"role": "system", "content": "You are a tool-use agent."},
        {"role": "user", "content": "Add a reminder for tomorrow."},
    ]

    prompted = toolsandbox_roles._with_selector_actor_policy(messages, [])

    assert prompted[-1] == messages[-1]
    assert any(
        message.get("role") == "system"
        and "Complete exactly the user's current ToolSandbox task"
        in message.get("content", "")
        for message in prompted
    )


def test_visible_record_continuation_precedes_generic_generated_tool_choice(
    monkeypatch,
) -> None:
    """A matching record consumer should run before a generic ready tool."""

    monkeypatch.setattr(
        toolsandbox_roles,
        "_with_selector_actor_policy",
        lambda messages, _tools: messages,
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_helper_answer_completion_tool_free_turn",
        lambda _messages, _tools: False,
    )
    for selector_name in (
        "_helper_answer_completion_tool_choice",
        "_device_status_completion_tool_choice",
        "_shared_task_closure_tool_choice",
        "_generated_downstream_original_tool_choice",
        "_state_action_planner_tool_choice",
        "_reminder_recency_workflow_tool_choice",
        "_relationship_batch_generated_tool_choice",
        "_reminder_location_batch_tool_choice",
    ):
        monkeypatch.setattr(
            toolsandbox_roles,
            selector_name,
            lambda _messages, _tools: None,
        )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_generated_tool_continuation_choice",
        lambda _messages, _tools: "record_consumer",
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_new_user_turn_generated_tool_choice",
        lambda _messages, _tools: "generic_ready_tool",
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_first_attempt_generated_tool_choice",
        lambda _messages, _tools: "generic_ready_tool",
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_dynamic_generated_tool_schema_filter",
        lambda _messages, tools, **_kwargs: tools,
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "_hide_wrapped_native_action_schemas",
        lambda tools, **_kwargs: tools,
    )

    agent = object.__new__(toolsandbox_roles.ConfigurableOpenAIAgent)
    agent.model_name = "gpt-4o-mini"
    selected: list[str] = []

    def capture_choice(_messages, _tools, tool_name):
        selected.append(tool_name)
        return SimpleNamespace()

    monkeypatch.setattr(agent, "_model_inference_with_tool_choice", capture_choice)
    tools = [
        {"type": "function", "function": {"name": "record_consumer"}},
        {"type": "function", "function": {"name": "generic_ready_tool"}},
    ]

    agent.model_inference([{"role": "user", "content": "Use the records."}], tools)

    assert selected == ["record_consumer"]


def test_native_device_action_requires_visible_device_state_need(monkeypatch) -> None:
    runtime_tool = SimpleNamespace(
        sage_native_action_delegation=True,
        sage_native_action_names=("set_wifi_status",),
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_device_action": runtime_tool}),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_device_action",
                "description": "Apply one validated device state action.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        [{"role": "user", "content": "Find my most recent message."}],
        tools,
        "generated_device_action",
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        [{"role": "user", "content": "Turn on wifi."}],
        tools,
        "generated_device_action",
    )


def test_native_device_action_is_ready_after_visible_repair_status(
    monkeypatch,
) -> None:
    runtime_tool = SimpleNamespace(
        sage_native_action_delegation=True,
        sage_native_action_names=("set_location_service_status",),
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_device_action": runtime_tool}),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_device_action",
                "description": "Apply one validated device state action.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        }
    ]
    messages = [
        {
            "role": "user",
            "content": "I cannot access my current location. Help me fix it.",
        },
        {"role": "tool", "name": "get_location_service_status", "content": "False"},
    ]

    assert _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "generated_device_action",
    )


def _generated_update_tool_schema():
    return [
        {
            "type": "function",
            "function": {
                "name": "generated_update_tool",
                "description": "Apply a validated visible update.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "records": {"type": "array"},
                        "updates": {"type": "object"},
                    },
                    "required": ["records", "updates"],
                },
            },
        }
    ]


def test_generated_tool_abstention_routes_user_supplied_followup() -> None:
    messages = [
        {"role": "user", "content": "Find the visible record first."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "generated_update_tool",
                        "arguments": json.dumps(
                            {"records": [{"id": "visible-1"}], "updates": {}}
                        ),
                    }
                }
            ],
        },
        {
            "role": "tool",
            "name": "generated_update_tool",
            "content": repr(
                {
                    "status": "abstain",
                    "confirmation": "",
                    "abstain_reason": "missing update fields",
                    "native_action": "",
                }
            ),
        },
        {"role": "assistant", "content": "I still need the update value."},
        {"role": "user", "content": "Use the new value I just provided."},
    ]
    tools = _generated_update_tool_schema()

    policy = _generated_tool_abstain_continuation_actor_policy_message(messages, tools)

    assert policy is not None
    assert "did not complete the task" in policy["content"]
    assert "records, updates" in policy["content"]
    assert _helper_answer_completion_actor_policy_message(messages, tools) is None


def test_tool_names_extracts_openai_function_names() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "next_dependency_precondition_call"},
        }
    ]

    assert _tool_names(tools) == {"next_dependency_precondition_call"}
    assert _tool_names(NOT_GIVEN) == set()


def test_execution_tool_names_normalize_openai_function_namespace() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "functions.set_location_service_status"},
        }
    ]

    assert _tool_names_execution_facing(tools) == {"set_location_service_status"}
    assert _tool_name_for_call(tools, "set_location_service_status") == (
        "functions.set_location_service_status"
    )


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


def test_temperature_extractor_waits_for_its_declared_producer() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_temperature_result",
                "description": (
                    "Deterministic extraction. First call one declared original "
                    "producer: search_weather_around_lat_lon."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_payload": {"type": "object"},
                        "requested_unit": {"type": "string"},
                        "answer_subject": {"type": "string"},
                        "requested_metric": {"type": "string"},
                    },
                },
            },
        }
    ]
    messages = [
        {"role": "user", "content": "Temperature in Grand Canyon in Fahrenheit"},
        {
            "role": "tool",
            "name": "search_location_around_lat_lon",
            "content": "[{'latitude': 36.2, 'longitude': -112.1}]",
        },
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "extract_temperature_result"
    )
    assert _derived_actor_policy_message(messages, tools) is None

    messages.append(
        {
            "role": "tool",
            "name": "search_weather_around_lat_lon",
            "content": (
                "{'current_temperature': 15.1, 'min_temperature': 8.9, "
                "'temperature_unit': 'Celsius'}"
            ),
        }
    )

    assert _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "extract_temperature_result"
    )
    policy = _derived_actor_policy_message(messages, tools)
    assert policy is not None
    assert "requested_metric" in policy["content"]
    assert "canonical selector value" in policy["content"]


def test_declared_producer_survives_function_or_argument_description_scrambling() -> (
    None
):
    function_description_only = [
        {
            "type": "function",
            "function": {
                "name": "extract_temperature_result",
                "description": (
                    "Call only after one declared original producer returns: "
                    "search_weather_around_lat_lon."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"service_payload": {"type": "object"}},
                },
            },
        }
    ]
    argument_description_only = [
        {
            "type": "function",
            "function": {
                "name": "extract_temperature_result",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_payload": {
                            "type": "object",
                            "description": (
                                "Full visible result from "
                                "search_weather_around_lat_lon."
                            ),
                        }
                    },
                },
            },
        }
    ]

    assert _declared_service_answer_producers(
        function_description_only, "extract_temperature_result"
    ) == ("search_weather_around_lat_lon",)
    assert _declared_service_answer_producers(
        argument_description_only, "extract_temperature_result"
    ) == ("search_weather_around_lat_lon",)


def test_selected_generated_extractor_cannot_bypass_input_readiness(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_DYNAMIC_GENERATED_TOOL_SCHEMA", "1")
    generated = {
        "type": "function",
        "function": {
            "name": "extract_temperature_result",
            "description": (
                "Deterministic extraction. First call one declared original "
                "producer: search_weather_around_lat_lon."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_payload": {"type": "object"},
                    "requested_metric": {"type": "string"},
                },
            },
        },
    }
    tools = [
        {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
        generated,
    ]
    messages = [
        {"role": "user", "content": "Temperature in Grand Canyon"},
        {
            "role": "tool",
            "name": "search_location_around_lat_lon",
            "content": "[{'latitude': 36.2, 'longitude': -112.1}]",
        },
    ]

    filtered = _dynamic_generated_tool_schema_filter(
        messages,
        tools,
        selected_tool_name="extract_temperature_result",
    )
    assert _tool_names_execution_facing(filtered) == {"search_weather_around_lat_lon"}

    messages.append(
        {
            "role": "tool",
            "name": "search_weather_around_lat_lon",
            "content": "{'current_temperature': 15.1, 'temperature_unit': 'Celsius'}",
        }
    )
    filtered = _dynamic_generated_tool_schema_filter(
        messages,
        tools,
        selected_tool_name="extract_temperature_result",
    )
    assert "extract_temperature_result" in _tool_names_execution_facing(filtered)


def test_relationship_batch_request_parses_switch_back_to_being_followup() -> None:
    request = _relationship_batch_request(
        [
            {"role": "user", "content": "Who are my friends?"},
            {
                "role": "user",
                "content": (
                    "I want you to update all my friends, Fredrik and John, "
                    "as my enemy."
                ),
            },
            {
                "role": "user",
                "content": "Now switch them back to being my friends.",
            },
        ]
    )

    assert request == {
        "user_request": (
            "Who are my friends? I want you to update all my friends, "
            "Fredrik and John, as my enemy. Now switch them back to being my friends."
        ),
        "source_relationship": "enemy",
        "target_relationship": "friend",
    }


def test_derived_policy_does_not_force_distance_scalar_into_service_helper() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_service_answer_field",
                "description": "Extract deterministic answer fields.",
                "parameters": {
                    "type": "object",
                    "properties": {"service_payload": {"type": "object"}},
                },
            },
        }
    ]

    policy = _derived_actor_policy_message(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.96238310230461",
            },
        ],
        tools,
    )

    assert policy is not None
    assert "distance_km" not in policy["content"]
    assert "bare scalar" in policy["content"]


def test_helper_answer_retention_policy_preserves_service_distance() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '67.96238310230461', "
                    "'answer_kind': 'distance', 'answer_unit': 'km', "
                    "'abstain_reason': ''}"
                ),
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away.",
            },
            {
                "role": "user",
                "content": "Alright, thanks. You can end the conversation now.",
            },
        ]
    )

    assert policy is not None
    assert "67.96 kilometers" in policy["content"]
    assert "generic acknowledgement" in policy["content"]


def test_helper_answer_retention_policy_does_not_reuse_on_repeat_request() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '67.96238310230461', "
                    "'answer_kind': 'distance', 'answer_unit': 'km', "
                    "'abstain_reason': ''}"
                ),
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away.",
            },
            {
                "role": "user",
                "content": "Cool, can you check the distance to the Golden Gate Bridge again?",
            },
        ]
    )

    assert policy is None


def test_helper_answer_retention_policy_recognizes_scrambled_generated_name() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "generated_tools_0",
                "content": (
                    "{'answer_value': '67.96238310230461', "
                    "'answer_kind': 'distance', 'answer_unit': 'km', "
                    "'abstain_reason': ''}"
                ),
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away.",
            },
            {"role": "user", "content": "Okay, I have got the distance now. Thanks!"},
        ]
    )

    assert policy is not None
    assert "67.96 kilometers" in policy["content"]


def test_helper_answer_retention_policy_recaps_generated_lookup_answer() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "What is my relationship with +10000000000?"},
            {
                "role": "tool",
                "name": "plan_contact_lookup_query",
                "content": (
                    "{'should_call_search_contacts': True, "
                    "'search_contacts_kwargs': {'phone_number': '+10000000000'}, "
                    "'answer_field': 'relationship'}"
                ),
            },
            {
                "role": "tool",
                "name": "search_contacts",
                "content": (
                    "[{'person_id': 'p1', 'name': 'Homer S', "
                    "'phone_number': '+10000000000', 'relationship': 'boss'}]"
                ),
            },
            {
                "role": "assistant",
                "content": "Your relationship with +10000000000 is boss.",
            },
            {"role": "user", "content": "Okay, great!"},
        ]
    )

    assert policy is not None
    assert "Your relationship with +10000000000 is boss." in policy["content"]
    assert "generic acknowledgement" in policy["content"]


def test_helper_answer_retention_policy_recaps_search_window_answer_with_end_tool() -> (
    None
):
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "What's the todo item I made yesterday?"},
            {"role": "tool", "name": "get_current_timestamp", "content": "1780650312"},
            {
                "role": "tool",
                "name": "resolve_search_window_or_bounds",
                "content": (
                    "{'target_tool_name': 'search_reminder', "
                    "'search_kwargs': {'creation_timestamp_lowerbound': 1780563792, "
                    "'creation_timestamp_upperbound': 1780564032}, "
                    "'should_call_search': True, 'abstain_reason': ''}"
                ),
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": (
                    "[{'reminder_id': 'r1', "
                    "'content': 'Buy tickets for Merrily next week', "
                    "'creation_timestamp': 1780563912.356671}]"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The todo item you made yesterday is: "
                    "Buy tickets for Merrily next week."
                ),
            },
            {"role": "user", "content": "Got it, I need that info!"},
        ],
        [{"type": "function", "function": {"name": "end_conversation"}}],
    )

    assert policy is not None
    assert "Buy tickets for Merrily next week" in policy["content"]
    assert "generic acknowledgement" in policy["content"]


def test_search_window_result_handoff_answers_after_visible_reminder_result() -> None:
    policy = _search_window_result_handoff_actor_policy_message(
        [
            {"role": "user", "content": "What's my todo yesterday?"},
            {"role": "tool", "name": "get_current_timestamp", "content": "1780650312"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "resolve_search_window_or_bounds",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "resolve_search_window_or_bounds",
                "content": (
                    "{'target_tool_name': 'search_reminder', "
                    "'search_kwargs': {'creation_timestamp_lowerbound': 1780563792, "
                    "'creation_timestamp_upperbound': 1780564032}, "
                    "'should_call_search': True, 'abstain_reason': ''}"
                ),
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": (
                    "[{'reminder_id': 'r1', "
                    "'content': 'Buy tickets for Merrily next week'}]"
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "resolve_search_window_or_bounds"},
            },
            {"type": "function", "function": {"name": "search_reminder"}},
        ],
    )

    assert policy is not None
    assert "exactly one visible reminder record" in policy["content"]
    assert "must answer from that record" in policy["content"]
    assert "visible ToolSandbox search result" in policy["content"]


def test_recency_window_does_not_hide_datetime_producer_prerequisite() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "resolve_search_window_or_bounds",
                "parameters": {
                    "type": "object",
                    "properties": {"current_timestamp": {"type": "number"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "relative_day_time_to_timestamp",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_timestamp": {"type": "number"},
                        "current_datetime_info": {"type": "object"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_timestamp",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "timestamp_to_datetime_info",
                "parameters": {
                    "type": "object",
                    "properties": {"timestamp": {"type": "number"}},
                },
            },
        },
    ]
    choice = _generated_tool_prerequisite_choice(
        [
            {
                "role": "user",
                "content": "Postpone my most recent reminder to tomorrow 5 PM.",
            },
            {
                "role": "tool",
                "name": "get_current_timestamp",
                "content": "1784539373.0",
            },
        ],
        tools,
    )

    assert choice == "timestamp_to_datetime_info"


def test_native_reminder_action_receives_generated_timestamp_update() -> None:
    policy = _reminder_recency_search_result_actor_policy_message(
        [
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
        [
            {
                "type": "function",
                "function": {
                    "name": "select_action_target_by_recency",
                    "description": (
                        "This generated composite completes one final action by "
                        "delegating to an approved native ToolSandbox tool. The "
                        "native tool remains the state-changing implementation."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {"type": "function", "function": {"name": "modify_reminder"}},
            {
                "type": "function",
                "function": {"name": "relative_day_time_to_timestamp"},
            },
        ],
    )

    assert policy is not None
    assert 'updates={"reminder_timestamp": 90000.0}' in policy["content"]
    assert "do not call modify_reminder again" in policy["content"]


def test_record_native_tool_waits_for_matching_original_record_source() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_message_counterparty_for_contact_update",
                "description": (
                    "Consumes visible search_messages records and delegates one "
                    "validated native modify_contact action."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "records": {"type": "array"},
                        "updates": {"type": "object"},
                        "self_person_id": {"type": "string"},
                    },
                },
            },
        }
    ]
    messages = [
        {"role": "user", "content": "Update the last person I messaged."},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': 'self', 'is_self': True}]",
        },
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "select_message_counterparty_for_contact_update",
    )

    messages.append(
        {
            "role": "tool",
            "name": "search_messages",
            "content": (
                "[{'sender_person_id': 'self', 'recipient_person_id': 'p2', "
                "'creation_timestamp': 100.0}]"
            ),
        }
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "select_message_counterparty_for_contact_update",
    )

    messages.append(
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': 'p2', 'name': 'Visible contact'}]",
        }
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "select_message_counterparty_for_contact_update",
    )


def test_message_record_tool_requires_visible_self_lookup_before_search() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_message_counterparty_for_contact_update",
                "description": "Select a counterparty from search_messages records.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "records": {"type": "array"},
                        "self_person_id": {"type": "string"},
                        "updates": {"type": "object"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "search_messages"}},
    ]
    messages = [
        {
            "role": "user",
            "content": "Update the contact from my most recent incoming message.",
        }
    ]

    assert _generated_tool_prerequisite_choice(messages, tools) == "search_contacts"

    messages.append(
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': 'self-1', 'is_self': True}]",
        }
    )

    assert _generated_tool_prerequisite_choice(messages, tools) == "search_messages"


def test_record_update_tool_waits_for_visible_update_turn() -> None:
    tools = _generated_update_tool_schema()
    messages = [
        {"role": "user", "content": "Who was the last person I messaged?"},
        {
            "role": "tool",
            "name": "search_messages",
            "content": "[{'id': 'visible-1', 'creation_timestamp': 100.0}]",
        },
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "generated_update_tool",
    )

    messages.extend(
        [
            {"role": "assistant", "content": "That was Jamie."},
            {"role": "user", "content": "Update their phone number to +15550100."},
        ]
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages,
        tools,
        "generated_update_tool",
    )


def test_relative_time_tool_waits_for_required_reminder_content() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "relative_day_time_to_timestamp",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    messages = [{"role": "user", "content": "Add a reminder for tomorrow 5 PM"}]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "relative_day_time_to_timestamp"
    )

    messages.extend(
        [
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk."},
        ]
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "relative_day_time_to_timestamp"
    )


def test_weekday_time_tool_waits_for_required_reminder_content() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "next_weekday_time_to_timestamp",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    messages = [{"role": "user", "content": "Add a reminder next Friday 5 PM"}]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "next_weekday_time_to_timestamp"
    )

    messages.extend(
        [
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk."},
        ]
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "next_weekday_time_to_timestamp"
    )


def test_search_window_tool_requires_visible_recency_search_intent() -> None:
    window_tool = {
        "type": "function",
        "function": {
            "name": "resolve_search_window_or_bounds",
            "description": "Prepare bounded search kwargs from a recency phrase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_timestamp": {"type": "number"},
                    "phrase": {"type": "string"},
                    "target_domain": {"type": "string"},
                    "timestamp_intent": {"type": "string"},
                    "direction": {"type": "string"},
                },
            },
        },
    }
    tools = [
        window_tool,
        {"type": "function", "function": {"name": "get_current_timestamp"}},
    ]

    vague = [{"role": "user", "content": "I wanna find a message."}]
    assert not _generated_tool_inputs_ready_for_current_turn(
        vague, tools, "resolve_search_window_or_bounds"
    )
    assert _generated_tool_prerequisite_choice(vague, tools) is None

    creation = [
        {
            "role": "user",
            "content": "Add a reminder next Friday at 5 PM to buy milk.",
        }
    ]
    assert not _generated_tool_inputs_ready_for_current_turn(
        creation, tools, "resolve_search_window_or_bounds"
    )
    assert _generated_tool_prerequisite_choice(creation, tools) is None

    recency_search = [{"role": "user", "content": "Find my most recent message."}]
    assert not _generated_tool_inputs_ready_for_current_turn(
        recency_search, tools, "resolve_search_window_or_bounds"
    )
    assert (
        _generated_tool_prerequisite_choice(recency_search, tools)
        == "get_current_timestamp"
    )


def test_device_repair_status_routes_generated_sequence_before_single_action() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "apply_single_device_state_action",
                "description": (
                    "A generated device-state tool that delegates to validated native "
                    "actions set_wifi_status and set_location_service_status."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plan a generated device-state setter sequence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "get_location_service_status"}},
    ]
    messages = [
        {
            "role": "user",
            "content": "I cannot access my current location. Help me fix it in settings.",
        },
        {
            "role": "tool",
            "name": "get_location_service_status",
            "content": "False",
        },
    ]

    assert (
        _state_action_planner_tool_choice(messages, tools)
        == "plan_device_state_action_sequence_v3"
    )


def test_implicit_device_mutation_routes_generated_action_on_existing_turn() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "apply_single_device_state_action",
                "description": "Applies a single device state action.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plans a sequence of actions to change device state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        },
    ]
    messages = [
        {
            "role": "user",
            "content": "I don't have cellphone signal. Can you get it on?",
        }
    ]

    assert (
        _state_action_planner_tool_choice(messages, tools)
        == "plan_device_state_action_sequence_v3"
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "apply_single_device_state_action"
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "plan_device_state_action_sequence_v3"
    )


def test_state_precondition_policy_uses_current_structured_contract() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plans a sequence of actions to change device state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                        "low_battery_blocks_enable": {"type": "boolean"},
                        "resume_original_task": {"type": "boolean"},
                        "additional_services_to_enable": {"type": "array"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]
    messages = [
        {"role": "user", "content": "Turn on cellular"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "set_cellular_service_status",
                        "arguments": '{"on": true}',
                    }
                }
            ],
        },
        {
            "role": "tool",
            "name": "set_cellular_service_status",
            "content": (
                "PermissionError: Cellular service cannot be turned on in "
                "low battery mode"
            ),
        },
    ]

    policy = toolsandbox_roles._state_action_actor_policy_message(messages, tools)

    assert policy is not None
    assert "low_battery_blocks_enable=true" in policy["content"]
    assert "retired fields" in policy["content"]


def test_state_action_policy_exposes_generated_tool_canonical_service_keys() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plans a sequence of actions to change device state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                        "low_battery_blocks_enable": {"type": "boolean"},
                        "resume_original_task": {"type": "boolean"},
                        "additional_services_to_enable": {"type": "array"},
                    },
                },
            },
        }
    ]
    messages = [{"role": "user", "content": "Turn on location service"}]

    policy = toolsandbox_roles._state_action_actor_policy_message(messages, tools)

    assert policy is not None
    assert "wifi, cellular, location, or low_battery" in policy["content"]
    assert "rather than passing location_service" in policy["content"]


def test_native_reminder_finalizer_and_guidance_wait_for_required_content() -> None:
    finalizer = {
        "type": "function",
        "function": {
            "name": "prepare_reminder_creation_args",
            "description": (
                "This generated composite completes one final action by delegating "
                "to an approved native ToolSandbox tool. Validated native action: "
                "add_reminder. The native tool remains the state-changing "
                "implementation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "reminder_timestamp": {"type": "number"},
                },
            },
        },
    }
    relative_tool = {
        "type": "function",
        "function": {
            "name": "relative_day_time_to_timestamp",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    messages = [
        {"role": "user", "content": "Add a reminder for tomorrow 5 PM"},
        {
            "role": "tool",
            "name": "relative_day_time_to_timestamp",
            "content": "1784678400.0",
        },
    ]
    tools = [finalizer, relative_tool]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages, tools, "prepare_reminder_creation_args"
    )
    policy = _relative_time_actor_policy_message(messages[:1], tools)
    assert policy is not None
    assert "Ask the user what the reminder should say" in policy["content"]

    weekday_tool = {
        "type": "function",
        "function": {
            "name": "next_weekday_time_to_timestamp",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    weekday_policy = _scheduling_timestamp_actor_policy_message(
        [{"role": "user", "content": "Add a reminder next Friday 5 PM"}],
        [finalizer, weekday_tool],
    )
    assert weekday_policy is not None
    assert "Ask the user what the reminder should say" in weekday_policy["content"]


def test_generated_tool_own_result_does_not_trigger_duplicate_call() -> None:
    messages = [
        {"role": "user", "content": "Create the reminder."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-finalizer",
                    "function": {
                        "name": "prepare_reminder_creation_args",
                        "arguments": '{"content": "Buy milk"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "prepare_reminder_creation_args",
            "tool_call_id": "call-finalizer",
            "content": "{'status': 'success', 'native_action': 'add_reminder'}",
        },
        {"role": "assistant", "content": "The reminder was created."},
        {"role": "user", "content": "Awesome!"},
    ]

    assert not _generated_tool_new_information_since_call(
        messages, "prepare_reminder_creation_args"
    )

    messages.extend(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call-search",
                        "function": {"name": "search_reminder", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "tool_call_id": "call-search",
                "content": "[{'reminder_id': 'r1'}]",
            },
        ]
    )
    assert _generated_tool_new_information_since_call(
        messages, "prepare_reminder_creation_args"
    )


def _native_reminder_action_schema() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "generated_reminder_action",
            "description": (
                "This generated composite completes one final action by delegating "
                "to an approved native ToolSandbox tool. The native tool remains "
                "the state-changing implementation. Validated native action: "
                "modify_reminder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "records": {"type": "array"},
                    "updates": {"type": "object"},
                },
            },
        },
    }


def _native_reminder_remove_action_schema(
    name: str = "generated_reminder_remove_action",
) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                "This generated composite completes one final action by delegating "
                "to an approved native ToolSandbox tool. The native tool remains "
                "the state-changing implementation. Validated native action: "
                "remove_reminder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "records": {"type": "array"},
                    "timestamp_key": {"type": "string"},
                    "selection_mode": {"type": "string"},
                    "action_type": {"type": "string"},
                    "constraints": {"type": "object"},
                    "updates": {"type": "object"},
                },
            },
        },
    }


def test_native_action_tool_has_priority_over_preparatory_selector() -> None:
    tools = [
        _native_reminder_action_schema(),
        {
            "type": "function",
            "function": {
                "name": "select_record_by_timestamp_extreme",
                "parameters": {
                    "type": "object",
                    "properties": {"records": {"type": "array"}},
                },
            },
        },
    ]

    assert _generated_tool_choice_priority(tools, "generated_reminder_action") == -1
    assert (
        _generated_tool_choice_priority(tools, "select_record_by_timestamp_extreme")
        > -1
    )


def test_native_reminder_action_waits_for_generated_timestamp() -> None:
    base_messages = [
        {
            "role": "user",
            "content": "Postpone my most recent reminder to tomorrow 5 PM.",
        },
        {"role": "tool", "name": "get_current_timestamp", "content": "1000"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-datetime-info",
                    "function": {
                        "name": "timestamp_to_datetime_info",
                        "arguments": '{"timestamp": 1000}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "timestamp_to_datetime_info",
            "tool_call_id": "call-datetime-info",
            "content": "{'hour': 8, 'minute': 0, 'second': 0}",
        },
        {
            "role": "tool",
            "name": "search_reminder",
            "content": (
                "[{'reminder_id': 'r1', 'creation_timestamp': 900.0, "
                "'reminder_timestamp': 1200.0}]"
            ),
        },
    ]
    tools = [
        _native_reminder_action_schema(),
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {
            "type": "function",
            "function": {"name": "timestamp_to_datetime_info"},
        },
        {
            "type": "function",
            "function": {"name": "relative_day_time_to_timestamp"},
        },
        {"type": "function", "function": {"name": "modify_reminder"}},
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        base_messages,
        tools,
        "generated_reminder_action",
    )
    assert (
        _reminder_recency_workflow_tool_choice(base_messages, tools)
        == "relative_day_time_to_timestamp"
    )
    completed_messages = [
        *base_messages,
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-relative-time",
                    "function": {
                        "name": "relative_day_time_to_timestamp",
                        "arguments": (
                            '{"current_timestamp": 1000, "day_offset": 1, '
                            '"hour": 17, "minute": 0}'
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "relative_day_time_to_timestamp",
            "tool_call_id": "call-relative-time",
            "content": "90000.0",
        },
    ]
    assert _generated_tool_inputs_ready_for_current_turn(
        completed_messages,
        tools,
        "generated_reminder_action",
    )
    assert (
        _reminder_recency_workflow_tool_choice(completed_messages, tools)
        == "generated_reminder_action"
    )


def test_native_reminder_workflow_runs_generated_search_planner_before_search() -> None:
    messages = [
        {
            "role": "user",
            "content": "Postpone my most recent reminder to tomorrow 5 PM.",
        },
        {"role": "tool", "name": "get_current_timestamp", "content": "1000"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-relative-time",
                    "function": {
                        "name": "relative_day_time_to_timestamp",
                        "arguments": (
                            '{"current_timestamp": 1000, "day_offset": 1, '
                            '"hour": 17, "minute": 0}'
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "relative_day_time_to_timestamp",
            "tool_call_id": "call-relative-time",
            "content": "90000.0",
        },
    ]
    tools = [
        _native_reminder_action_schema(),
        {
            "type": "function",
            "function": {
                "name": "prepare_past_reminder_recency_search_args",
                "description": "Prepare search kwargs for past reminder recency.",
                "parameters": {
                    "type": "object",
                    "properties": {"current_timestamp": {"type": "number"}},
                },
            },
        },
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "modify_reminder"}},
    ]

    assert (
        _reminder_recency_workflow_tool_choice(messages, tools)
        == "prepare_past_reminder_recency_search_args"
    )


def test_native_reminder_remove_workflow_routes_action_tool_after_search() -> None:
    messages = [
        {"role": "user", "content": "Delete my most recent reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": (
                "[{'reminder_id': 'old', 'creation_timestamp': 100.0}, "
                "{'reminder_id': 'new', 'creation_timestamp': 200.0}]"
            ),
        },
    ]
    tools = [
        _native_reminder_remove_action_schema(),
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    assert (
        _reminder_recency_workflow_tool_choice(messages, tools)
        == "generated_reminder_remove_action"
    )


def test_native_upcoming_reminder_remove_routes_search_planner() -> None:
    messages = [
        {"role": "user", "content": "Remove my next upcoming reminder."},
        {"role": "tool", "name": "get_current_timestamp", "content": "1000"},
    ]
    tools = [
        _native_reminder_remove_action_schema(),
        {
            "type": "function",
            "function": {
                "name": "prepare_upcoming_reminder_search_args",
                "parameters": {
                    "type": "object",
                    "properties": {"current_timestamp": {"type": "number"}},
                },
            },
        },
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    assert (
        _reminder_recency_workflow_tool_choice(messages, tools)
        == "prepare_upcoming_reminder_search_args"
    )


def test_native_upcoming_reminder_remove_recognizes_generic_disposal_phrase() -> None:
    messages = [
        {"role": "user", "content": "Get rid of my next reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": ("[{'reminder_id': 'next', 'reminder_timestamp': 1200.0}]"),
        },
    ]
    tools = [
        _native_reminder_remove_action_schema("select_action_target_by_recency"),
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    assert (
        _reminder_recency_workflow_tool_choice(messages, tools)
        == "select_action_target_by_recency"
    )


def test_native_reminder_remove_policy_uses_generated_action_contract() -> None:
    messages = [
        {"role": "user", "content": "Remove my latest reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": (
                "[{'reminder_id': 'old', 'creation_timestamp': 100.0}, "
                "{'reminder_id': 'new', 'creation_timestamp': 200.0}]"
            ),
        },
    ]
    tools = [
        _native_reminder_remove_action_schema("select_action_target_by_recency"),
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    policy = _reminder_recency_search_result_actor_policy_message(messages, tools)

    assert policy is not None
    assert "Call select_action_target_by_recency now" in policy["content"]
    assert "timestamp_key='creation_timestamp'" in policy["content"]
    assert "selection_mode='latest'" in policy["content"]
    assert "action_type='remove_reminder'" in policy["content"]
    assert "updates={}" in policy["content"]


def test_reminder_remove_workflow_forces_validated_selector_fallback() -> None:
    messages = [
        {"role": "user", "content": "Remove my latest reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": (
                "[{'reminder_id': 'old', 'creation_timestamp': 100.0}, "
                "{'reminder_id': 'new', 'creation_timestamp': 200.0}]"
            ),
        },
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_record_by_timestamp_extreme",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "records": {"type": "array"},
                        "timestamp_key": {"type": "string"},
                        "selection_mode": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    assert (
        _reminder_recency_workflow_tool_choice(messages, tools)
        == "select_record_by_timestamp_extreme"
    )


def test_reminder_remove_workflow_calls_original_action_after_selector() -> None:
    messages = [
        {"role": "user", "content": "Remove my latest reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": (
                "[{'reminder_id': 'old', 'creation_timestamp': 100.0}, "
                "{'reminder_id': 'new', 'creation_timestamp': 200.0}]"
            ),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-selector",
                    "function": {
                        "name": "select_record_by_timestamp_extreme",
                        "arguments": (
                            '{"records": [], "timestamp_key": '
                            '"creation_timestamp", "selection_mode": "latest"}'
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "select_record_by_timestamp_extreme",
            "tool_call_id": "call-selector",
            "content": (
                "{'selected_record': {'reminder_id': 'new', "
                "'creation_timestamp': 200.0}, 'abstain_reason': ''}"
            ),
        },
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_record_by_timestamp_extreme",
                "parameters": {
                    "type": "object",
                    "properties": {"records": {"type": "array"}},
                },
            },
        },
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]

    assert _reminder_recency_workflow_tool_choice(messages, tools) == "remove_reminder"


def test_native_reminder_finalizer_waits_for_normalized_timestamp() -> None:
    finalizer = {
        "type": "function",
        "function": {
            "name": "prepare_reminder_creation_args",
            "description": (
                "This generated composite completes one final action by delegating "
                "to an approved native ToolSandbox tool. The native tool remains "
                "the state-changing implementation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "reminder_timestamp": {"type": "number"},
                    "location_requested": {"type": "boolean"},
                    "location_required": {"type": "boolean"},
                    "location_available": {"type": "boolean"},
                    "latitude": {"type": ["number", "null"]},
                    "longitude": {"type": ["number", "null"]},
                    "location_lookup_failed": {"type": "boolean"},
                },
            },
        },
    }
    messages = [
        {"role": "user", "content": "Remind me to call Alex tomorrow at 5 PM."},
        {"role": "tool", "name": "get_current_timestamp", "content": "1000"},
    ]

    assert not _generated_tool_inputs_ready_for_current_turn(
        messages,
        [finalizer],
        "prepare_reminder_creation_args",
    )
    messages.append(
        {
            "role": "tool",
            "name": "relative_day_time_to_timestamp",
            "content": "90000.0",
        }
    )
    assert _generated_tool_inputs_ready_for_current_turn(
        messages,
        [finalizer],
        "prepare_reminder_creation_args",
    )


def test_counterparty_setup_uses_unfiltered_records_when_direction_is_unknown() -> None:
    policy = _message_counterparty_selector_setup_actor_policy_message(
        [
            {
                "role": "user",
                "content": "Update the contact selected from the latest record.",
            },
            {
                "role": "tool",
                "name": "search_contacts",
                "content": (
                    "[{'person_id': 'self-1', 'is_self': True, 'relationship': 'self'}]"
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {
                    "name": "select_message_counterparty_for_contact_update",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {"type": "function", "function": {"name": "search_messages"}},
        ],
    )

    assert policy is not None
    assert "without sender or recipient filters" in policy["content"]


def test_native_action_policy_explains_visible_validated_action_contract() -> None:
    policy = _native_action_tool_actor_policy_message(
        [{"role": "user", "content": "Remove the selected reminder."}],
        [
            {
                "type": "function",
                "function": {
                    "name": "generated_action_tool",
                    "description": (
                        "This generated composite completes one final action by "
                        "delegating to an approved native ToolSandbox tool. The "
                        "native tool remains the state-changing implementation."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "records": {"type": "array"},
                            "selection_mode": {"type": "string"},
                            "updates": {"type": "object"},
                            "self_person_id": {"type": "string"},
                        },
                    },
                },
            },
            {"type": "function", "function": {"name": "remove_reminder"}},
        ],
    )

    assert policy is not None
    assert "generated_action_tool" in policy["content"]
    assert "state change is complete" in policy["content"]
    assert "every visible changed field value" in policy["content"]
    assert "do not invent" in policy["content"]
    assert (
        "generated_action_tool inputs: records, selection_mode, self_person_id, updates"
        in policy["content"]
    )
    assert "pass those changes together in the updates mapping" in policy["content"]
    assert (
        "Every updates key must exactly match a writable parameter" in policy["content"]
    )
    assert (
        "do not bypass it with the original state-changing action" in policy["content"]
    )
    assert "describe the target by that visible relationship" in policy["content"]
    assert "Do not perform another lookup solely" in policy["content"]
    assert "copy the matching original tool result intact" in policy["content"]
    assert "whose is_self field is true" in policy["content"]


def test_native_action_policy_is_absent_for_preparatory_generated_tool() -> None:
    policy = _native_action_tool_actor_policy_message(
        [{"role": "user", "content": "Find the latest reminder."}],
        [
            {
                "type": "function",
                "function": {
                    "name": "generated_selector",
                    "description": "Select one visible record.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    assert policy is None


def test_native_action_metadata_survives_description_scrambling(monkeypatch) -> None:
    runtime_tool = SimpleNamespace(sage_native_action_delegation=True)
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_action": runtime_tool}),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_action",
                "description": "unrelated scrambled description",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    assert _generated_tool_uses_native_action(tools, "generated_action")


def test_native_action_tool_hides_its_wrapped_original_from_actor(monkeypatch) -> None:
    runtime_tool = SimpleNamespace(
        sage_native_action_delegation=True,
        sage_native_action_names=("add_reminder",),
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_action": runtime_tool}),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_action",
                "description": "unrelated scrambled description",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    filtered = _hide_wrapped_native_action_schemas(
        tools,
        routed_openai_tools=tools,
    )

    assert _tool_names_execution_facing(filtered) == {
        "generated_action",
        "search_location_around_lat_lon",
    }


def test_generated_contract_continuation_keeps_selected_wrapped_action(
    monkeypatch,
) -> None:
    runtime_tool = SimpleNamespace(
        sage_native_action_delegation=True,
        sage_native_action_names=("set_location_service_status",),
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_action": runtime_tool}),
    )
    tools = [
        {"type": "function", "function": {"name": "generated_action"}},
        {
            "type": "function",
            "function": {"name": "set_location_service_status"},
        },
        {"type": "function", "function": {"name": "get_current_location"}},
    ]

    filtered = _hide_wrapped_native_action_schemas(
        tools,
        routed_openai_tools=tools,
        selected_tool_name="set_location_service_status",
    )

    assert _tool_names_execution_facing(filtered) == {
        "generated_action",
        "set_location_service_status",
        "get_current_location",
    }


def test_generated_downstream_choice_executes_next_state_sequence_action() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plans a sequence of actions to change device state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]
    messages = [
        {"role": "user", "content": "Turn on cellular"},
        {
            "role": "tool",
            "name": "plan_device_state_action_sequence_v3",
            "content": (
                "{'tool_name': 'set_low_battery_mode_status', "
                "'arguments': {'on': False}, 'should_call': True, "
                "'action_sequence': ["
                "{'tool_name': 'set_low_battery_mode_status', "
                "'arguments': {'on': False}}, "
                "{'tool_name': 'set_cellular_service_status', "
                "'arguments': {'on': True}}]}"
            ),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-low-battery",
                    "function": {
                        "name": "set_low_battery_mode_status",
                        "arguments": '{"on": false}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-low-battery",
            "name": "set_low_battery_mode_status",
            "content": "None",
        },
    ]

    assert (
        _generated_downstream_original_tool_choice(messages, tools)
        == "set_cellular_service_status"
    )


def test_generated_state_sequence_skips_unavailable_ungrounded_prerequisite() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plans a sequence of actions to change device state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_service": {"type": "string"},
                        "desired_on": {"type": "boolean"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]
    messages = [
        {
            "role": "user",
            "content": "Send a message after resolving a cellular error.",
        },
        {
            "role": "tool",
            "name": "plan_device_state_action_sequence_v3",
            "content": repr(
                {
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
                    "continue_original_task_after_sequence": True,
                    "final_response_recommendation": "continue_original_task",
                }
            ),
        },
    ]

    assert (
        _generated_downstream_original_tool_choice(messages, tools)
        == "set_cellular_service_status"
    )


def test_projected_state_sequence_completes_after_available_action() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_device_state_action_sequence_v3"},
        },
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
        {"type": "function", "function": {"name": "send_message_with_phone_number"}},
    ]
    messages = [
        {
            "role": "user",
            "content": "Send the message after restoring cellular service.",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-plan",
                    "function": {
                        "name": "plan_device_state_action_sequence_v3",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-plan",
            "name": "plan_device_state_action_sequence_v3",
            "content": repr(
                {
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
                    "continue_original_task_after_sequence": True,
                    "final_response_recommendation": "continue_original_task",
                }
            ),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-cellular",
                    "function": {
                        "name": "set_cellular_service_status",
                        "arguments": '{"on": true}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-cellular",
            "name": "set_cellular_service_status",
            "content": "None",
        },
    ]

    assert _generated_downstream_original_tool_choice(messages, tools) is None
    policy = _state_action_sequence_completion_policy_message(messages, tools)
    assert policy is not None
    assert "continue the user's original task" in policy["content"].lower()


def test_preparatory_tool_does_not_hide_original_action(monkeypatch) -> None:
    runtime_tool = SimpleNamespace(
        sage_native_action_delegation=False,
        sage_native_action_names=("add_reminder",),
    )
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_prep": runtime_tool}),
    )
    tools = [
        {"type": "function", "function": {"name": "generated_prep"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    filtered = _hide_wrapped_native_action_schemas(
        tools,
        routed_openai_tools=tools,
    )

    assert _tool_names_execution_facing(filtered) == {
        "generated_prep",
        "add_reminder",
    }


def test_pruned_generated_search_tool_hands_off_to_original_search() -> None:
    tools = [
        {"type": "function", "function": {"name": "search_reminder"}},
        {
            "type": "function",
            "function": {"name": "select_action_target_by_recency"},
        },
    ]
    messages = [
        {"role": "user", "content": "Get rid of my next reminder."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "prepare_upcoming_reminder_search_args",
                        "arguments": '{"current_timestamp": 1784612251}',
                    }
                }
            ],
        },
        {
            "role": "tool",
            "name": "prepare_upcoming_reminder_search_args",
            "content": repr(
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {"reminder_timestamp_lowerbound": 1784612251},
                    "should_call_search": True,
                    "abstain_reason": "",
                }
            ),
        },
    ]

    assert (
        _generated_downstream_original_tool_choice(messages, tools) == "search_reminder"
    )


def test_dynamic_schema_keeps_multi_action_selector_for_removal() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "select_action_target_by_recency",
                "description": "Select and execute a validated reminder action.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "records": {"type": "array"},
                        "updates": {"type": "object"},
                        "action_type": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "search_reminder"}},
    ]
    messages = [
        {"role": "user", "content": "Get rid of my next reminder."},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": repr(
                [
                    {
                        "reminder_id": "r1",
                        "reminder_timestamp": 1784615851,
                    }
                ]
            ),
        },
    ]

    filtered = _dynamic_generated_tool_schema_filter(
        messages,
        tools,
        selected_tool_name="select_action_target_by_recency",
    )

    assert "select_action_target_by_recency" in _tool_names_execution_facing(filtered)


def test_successful_native_action_gets_tool_free_confirmation_turn(
    monkeypatch,
) -> None:
    runtime_tool = SimpleNamespace(sage_native_action_delegation=True)
    monkeypatch.setattr(
        toolsandbox_roles,
        "get_current_context",
        lambda: SimpleNamespace(name_to_tool={"generated_action": runtime_tool}),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_action",
                "description": "unrelated scrambled description",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]
    messages = [
        {"role": "user", "content": "Create the reminder."},
        {
            "role": "tool",
            "name": "generated_action",
            "content": repr(
                {
                    "status": "success",
                    "native_action": "add_reminder",
                    "native_result": "reminder-1",
                }
            ),
        },
    ]

    assert _helper_answer_completion_tool_free_turn(messages, tools)


def test_contact_lookup_answer_policy_reuses_helper_after_visible_record() -> None:
    policy = _contact_lookup_answer_actor_policy_message(
        [
            {"role": "user", "content": "What is my relationship with +10000000000?"},
            {
                "role": "tool",
                "name": "plan_contact_lookup_query",
                "content": (
                    "{'should_call_search_contacts': True, "
                    "'search_contacts_kwargs': {'phone_number': '+10000000000'}, "
                    "'answer_field': 'relationship', 'abstain_reason': ''}"
                ),
            },
            {
                "role": "tool",
                "name": "search_contacts",
                "content": (
                    "[{'person_id': 'p1', 'name': 'Homer S', "
                    "'phone_number': '+10000000000', 'relationship': 'boss'}]"
                ),
            },
        ],
        [{"type": "function", "function": {"name": "plan_contact_lookup_query"}}],
    )

    assert policy is not None
    assert "call plan_contact_lookup_query again" in policy["content"]
    assert "selected_record" in policy["content"]
    assert "requested_field='relationship'" in policy["content"]
    assert "final_answer_recommendation" in policy["content"]


def test_contact_lookup_answer_policy_skips_side_effect_id_lookup() -> None:
    policy = _contact_lookup_answer_actor_policy_message(
        [
            {"role": "user", "content": "Remove phone number +12453344098."},
            {
                "role": "tool",
                "name": "plan_contact_lookup_query",
                "content": (
                    "{'should_call_search_contacts': True, "
                    "'search_contacts_kwargs': {'phone_number': '+12453344098'}, "
                    "'answer_field': 'person_id', 'abstain_reason': ''}"
                ),
            },
            {
                "role": "tool",
                "name": "search_contacts",
                "content": (
                    "[{'person_id': 'p1', 'name': 'Fredrik', "
                    "'phone_number': '+12453344098'}]"
                ),
            },
        ],
        [{"type": "function", "function": {"name": "plan_contact_lookup_query"}}],
    )

    assert policy is None


def test_helper_answer_retention_policy_ignores_plain_base_tool_lookup() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "What is my relationship with +10000000000?"},
            {
                "role": "tool",
                "name": "search_contacts",
                "content": (
                    "[{'person_id': 'p1', 'name': 'Homer S', "
                    "'phone_number': '+10000000000', 'relationship': 'boss'}]"
                ),
            },
            {
                "role": "assistant",
                "content": "Your relationship with +10000000000 is boss.",
            },
            {"role": "user", "content": "Okay, great!"},
        ]
    )

    assert policy is None


def test_helper_answer_retention_policy_recaps_generated_status_lookup() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "Is the wifi connected to the internet?"},
            {
                "role": "tool",
                "name": "plan_device_status_lookup",
                "content": (
                    "{'tool_name': 'get_wifi_status', 'arguments': {}, "
                    "'should_call': True, 'target_service': 'wifi'}"
                ),
            },
            {"role": "tool", "name": "get_wifi_status", "content": "True"},
            {"role": "assistant", "content": "Your wifi is connected to the internet."},
            {"role": "user", "content": "Sweet! Thanks for the info."},
        ],
        openai_tools=[],
    )

    assert policy is not None
    assert "Your wifi is connected to the internet." in policy["content"]


def test_helper_answer_retention_policy_preserves_status_recommendation_on_followup() -> (
    None
):
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "Is my wifi on?"},
            {
                "role": "tool",
                "name": "plan_device_status_lookup",
                "content": (
                    "{'tool_name': '', 'arguments': {}, 'should_call': False, "
                    "'target_service': 'wifi', 'status_value': True, "
                    "'final_answer_recommendation': 'Wifi is on.'}"
                ),
            },
            {"role": "assistant", "content": "Wifi is on."},
            {
                "role": "user",
                "content": "Just check if it's connected to the internet.",
            },
        ],
        openai_tools=[],
    )

    assert policy is not None
    assert "Wifi is on." in policy["content"]
    assert "same-thread device-status follow-up" in policy["content"]


def test_device_status_retention_policy_requires_exact_helper_recommendation() -> None:
    policy = _device_status_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "Is my wifi on?"},
            {
                "role": "tool",
                "name": "plan_device_status_lookup",
                "content": (
                    "{'tool_name': '', 'arguments': {}, 'should_call': False, "
                    "'target_service': 'wifi', 'status_value': True, "
                    "'final_answer_recommendation': 'Wifi is on.'}"
                ),
            },
            {"role": "assistant", "content": "Wifi is on."},
            {"role": "user", "content": "I'm all set for now. Thanks!"},
        ],
        openai_tools=[],
    )

    assert policy is not None
    assert "begin exactly with: Wifi is on." in policy["content"]
    assert "do not invent unsupported diagnostics" in policy["content"]


def test_helper_answer_retention_policy_preserves_prior_tool_answer() -> None:
    policy = _helper_answer_retention_actor_policy_message(
        [
            {"role": "user", "content": "What does my oldest message say?"},
            {
                "role": "tool",
                "name": "select_record_by_timestamp_extreme",
                "content": (
                    "{'selected_record': {'content': 'secret message'}, "
                    "'abstain_reason': ''}"
                ),
            },
            {
                "role": "assistant",
                "content": "Your oldest message says: secret message",
            },
            {"role": "user", "content": "Got it, but please don't leak that info."},
        ],
        openai_tools=[],
    )

    assert policy is not None
    assert "Answer exactly with" in policy["content"]
    assert "Your oldest message says: secret message" in policy["content"]


def test_state_sequence_completion_retries_blocked_original_call_without_bridge() -> (
    None
):
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_device_state_action_sequence_v3"},
        },
        {"type": "function", "function": {"name": "set_wifi_status"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]
    policy = _state_action_sequence_completion_policy_message(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk at Whole Foods.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_search",
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": '{"location": "Whole Foods on McKinley Ave"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_search",
                "name": "search_location_around_lat_lon",
                "content": "ConnectionError: Wifi is not enabled",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_plan",
                        "function": {
                            "name": "plan_device_state_action_sequence_v3",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_plan",
                "name": "plan_device_state_action_sequence_v3",
                "content": (
                    "{'tool_name': 'set_wifi_status', "
                    "'arguments': {'on': True}, 'should_call': True, "
                    "'action_sequence': ["
                    "{'tool_name': 'set_wifi_status', "
                    "'arguments': {'on': True}}], "
                    "'final_response_recommendation': 'continue_original_task', "
                    "'continue_original_task_after_sequence': True}"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_wifi",
                        "function": {
                            "name": "set_wifi_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_wifi",
                "name": "set_wifi_status",
                "content": "None",
            },
        ],
        tools,
    )

    assert policy is not None
    assert "search_location_around_lat_lon" in policy["content"]
    assert '"location": "Whole Foods on McKinley Ave"' in policy["content"]
    assert "Do not ask the user again" in policy["content"]


def test_visible_location_phrase_extracts_on_street_qualifier() -> None:
    assert (
        _visible_location_phrase_from_user_request(
            [
                {"role": "user", "content": "Add a reminder at Whole Foods."},
                {"role": "user", "content": "It's on McKinley Ave."},
            ]
        )
        == "McKinley Ave"
    )
    assert (
        _visible_location_phrase_from_user_request(
            [{"role": "user", "content": "Remind me on Friday at 5 PM."}]
        )
        == ""
    )


def test_location_search_retries_generated_prepare_after_coordinates() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "prepare_location_search_args",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "location_phrase": {"type": "string"},
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
        {"type": "function", "function": {"name": "prepare_reminder_creation_args"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]
    messages = [
        {"role": "user", "content": "Add a reminder to buy milk at Whole Foods."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_location_prepare",
                    "function": {
                        "name": "prepare_location_search_args",
                        "arguments": json.dumps(
                            {
                                "user_request": "Add a reminder to buy milk at Whole Foods.",
                                "location_phrase": "Whole Foods",
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_location_prepare",
            "name": "prepare_location_search_args",
            "content": (
                "{'search_location_kwargs': {}, "
                "'should_call_downstream_tool': False, "
                "'downstream_tool_name': '', "
                "'downstream_tool_kwargs': {}, "
                "'location_query': '', "
                "'abstain_reason': "
                "'missing_current_coordinates_for_broad_location_query'}"
            ),
        },
        {"role": "user", "content": "It's on McKinley Ave."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_current_location",
                    "function": {
                        "name": "get_current_location",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_current_location",
            "name": "get_current_location",
            "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
        },
    ]

    policy = _location_search_retry_after_coordinates_actor_policy_message(
        messages, tools
    )

    assert policy is not None
    assert "prepare_location_search_args" in policy["content"]
    assert "McKinley Ave" in policy["content"]
    assert "37.334606" in policy["content"]
    assert "search_location_around_lat_lon" in policy["content"]
    assert (
        "Do not call prepare_reminder_creation_args or add_reminder"
        in policy["content"]
    )


def test_generated_reminder_missing_required_inputs_reuses_visible_timestamp() -> None:
    tools = [
        {"type": "function", "function": {"name": "relative_day_time_to_timestamp"}},
        {"type": "function", "function": {"name": "prepare_reminder_creation_args"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]
    policy = _helper_output_handoff_actor_policy_message(
        [
            {"role": "user", "content": "Tomorrow at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_relative",
                        "function": {
                            "name": "relative_day_time_to_timestamp",
                            "arguments": (
                                '{"current_timestamp": 1780757525.0, '
                                '"day_offset": 1, "hour": 17, "minute": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_relative",
                "name": "relative_day_time_to_timestamp",
                "content": "1780876800.0",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_prepare",
                        "function": {
                            "name": "prepare_reminder_creation_args",
                            "arguments": (
                                '{"content": "buy chocolate milk", '
                                '"current_timestamp": 1780757525, '
                                '"day_offset": 1, "hour": 17, "minute": 0, '
                                '"local_utc_offset_hours": 0, '
                                '"location_requested": false, '
                                '"location_required": false, '
                                '"location_available": false, '
                                '"latitude": 0, "longitude": 0, '
                                '"location_lookup_failed": false, '
                                '"current_datetime_info": {"year": 2026, '
                                '"month": 6, "day": 6, "hour": 7, '
                                '"minute": 52, "second": 5}}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_prepare",
                "name": "prepare_reminder_creation_args",
                "content": (
                    "{'add_reminder_kwargs': {}, "
                    "'should_call_add_reminder': False, "
                    "'abstain_reason': 'missing_required_helper_inputs'}"
                ),
            },
        ],
        tools,
    )

    assert policy is not None
    assert "resolved_reminder_timestamp" in policy["content"]
    assert "1780876800.0" in policy["content"]
    assert "Retry generated prepare_reminder_creation_args" in policy["content"]
