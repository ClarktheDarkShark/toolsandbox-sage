import json

from openai import NOT_GIVEN

from sage_ts.adapters.openai_toolsandbox_roles import (
    _absolute_reminder_creation_bridge_completion,
    _ambiguous_holiday_distance_bridge_completion,
    _answer_completion_bridge_completion,
    _answer_retention_response_text,
    _completed_device_setting_retention_response_text,
    _contact_lookup_answer_actor_policy_message,
    _contact_relationship_batch_bridge_completion,
    _crud_success_response_text,
    _current_city_recovery_bridge_completion,
    _current_location_distance_bridge_completion,
    _current_location_without_location_tool_response_text,
    _derived_actor_policy_message,
    _derived_value_tool_names,
    _device_status_answer_retention_actor_policy_message,
    _distance_answer_recovery_response_text,
    _generated_tool_contract_retry_policy_message,
    _helper_answer_retention_actor_policy_message,
    _helper_output_handoff_actor_policy_message,
    _holiday_day_count_bridge_completion,
    _location_phone_answer_bridge_completion,
    _location_search_retry_after_coordinates_actor_policy_message,
    _message_already_called_tool,
    _messages_show_prior_structured_payload,
    _messages_show_prior_tool_call,
    _messages_show_tool_error,
    _relationship_batch_request,
    _relative_reminder_creation_bridge_completion,
    _relative_timestamp_for_day_time,
    _reminder_created_yesterday_answer,
    _reminder_creation_location_bridge_completion,
    _reminder_recency_bridge_completion,
    _safe_action_or_abstain_bridge_completion,
    _search_window_result_handoff_actor_policy_message,
    _send_message_cellular_retry_bridge_completion,
    _send_message_missing_phone_response_text,
    _service_answer_extraction_bridge_completion,
    _setting_lookup_retention_response_text,
    _setting_lookup_unavailable_message_history_response_text,
    _setting_permission_followup_bridge_completion,
    _setting_success_response_text,
    _state_action_sequence_bridge_completion,
    _state_action_sequence_completion_policy_message,
    _stock_lookup_bridge_completion,
    _synthetic_tool_call_completion,
    _tool_name_for_call,
    _tool_names,
    _tool_names_execution_facing,
    _upcoming_reminder_answer_text,
    _visible_location_phrase_from_user_request,
    _weather_location_bridge_completion,
    _weekday_reminder_creation_bridge_completion,
)


def _first_tool_call(completion):
    tool_calls = completion.choices[0].message.tool_calls
    assert tool_calls
    return tool_calls[0]


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


def test_contact_relationship_bridge_updates_prior_lookup_contacts_without_planner(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]
    messages = [
        {"role": "user", "content": "Who are my friends?"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_lookup",
                    "function": {
                        "name": "plan_contact_lookup_query",
                        "arguments": '{"relationship":"friend"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "plan_contact_lookup_query",
            "tool_call_id": "call_lookup",
            "content": "{'should_call_search_contacts': True, 'search_contacts_kwargs': {'relationship': 'friend'}}",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_search",
                    "function": {
                        "name": "search_contacts",
                        "arguments": '{"relationship":"friend"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "search_contacts",
            "tool_call_id": "call_search",
            "content": (
                "[{'person_id': 'p1', 'name': 'Fredrik Thordendal', "
                "'relationship': 'friend', 'is_self': False}, "
                "{'person_id': 'p2', 'name': 'John Petrucci', "
                "'relationship': 'friend', 'is_self': False}]"
            ),
        },
        {
            "role": "assistant",
            "content": "Your friend is Fredrik Thordendal and John Petrucci.",
        },
        {"role": "user", "content": "Can you update all of them to enemies?"},
    ]

    completion = _contact_relationship_batch_bridge_completion(
        messages, tools, model_name="gpt-4o-mini"
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "modify_contact"
    assert json.loads(call.function.arguments) == {
        "person_id": "p1",
        "relationship": "enemy",
    }


def test_contact_relationship_bridge_finishes_prior_lookup_contact_updates_without_planner(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]
    messages = [
        {"role": "user", "content": "Who are my friends?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": (
                "[{'person_id': 'p1', 'name': 'Fredrik Thordendal', "
                "'relationship': 'friend', 'is_self': False}, "
                "{'person_id': 'p2', 'name': 'John Petrucci', "
                "'relationship': 'friend', 'is_self': False}]"
            ),
        },
        {"role": "user", "content": "Can you update all of them to enemies?"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_p1",
                    "function": {
                        "name": "modify_contact",
                        "arguments": '{"person_id":"p1","relationship":"enemy"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "modify_contact",
            "tool_call_id": "call_p1",
            "content": "Done",
        },
    ]

    completion = _contact_relationship_batch_bridge_completion(
        messages, tools, model_name="gpt-4o-mini"
    )
    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "modify_contact"
    assert json.loads(call.function.arguments) == {
        "person_id": "p2",
        "relationship": "enemy",
    }

    messages.extend(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_p2",
                        "function": {
                            "name": "modify_contact",
                            "arguments": '{"person_id":"p2","relationship":"enemy"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "name": "modify_contact",
                "tool_call_id": "call_p2",
                "content": "Done",
            },
        ]
    )

    completion = _contact_relationship_batch_bridge_completion(
        messages, tools, model_name="gpt-4o-mini"
    )
    assert completion is not None
    assert (
        completion.choices[0].message.content
        == "Fredrik Thordendal and John Petrucci are now your enemies"
    )


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


def test_safe_action_abstain_bridge_handles_current_location_missing_tool(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "prepare_safe_action_or_abstain"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    completion = _safe_action_or_abstain_bridge_completion(
        [{"role": "user", "content": "What is my current location?"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "prepare_safe_action_or_abstain"
    assert '"requested_action": "location_lookup"' in call.function.arguments
    assert '"get_current_location"' in call.function.arguments


def test_current_city_without_location_tool_returns_insufficient_information(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    answer = _current_location_without_location_tool_response_text(
        [{"role": "user", "content": "What city am I in?"}],
        tools,
    )

    assert (
        answer
        == "I do not have enough information to determine your current city because "
        "current location is unavailable and you did not provide coordinates."
    )


def test_current_city_location_service_followup_still_abstains_when_location_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "set_location_service_status"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    answer = _current_location_without_location_tool_response_text(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "assistant",
                "content": "Please provide your coordinates or enable location services.",
            },
            {
                "role": "user",
                "content": (
                    "I can't give you my coordinates. You'll have to enable "
                    "location services."
                ),
            },
        ],
        tools,
    )

    assert answer is not None
    assert "did not provide coordinates" in answer


def test_current_distance_still_abstains_when_location_tool_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "set_location_service_status"}},
    ]

    answer = _current_location_without_location_tool_response_text(
        [
            {"role": "user", "content": "How far am I from the museum?"},
            {
                "role": "assistant",
                "content": "Please enable location services. Would you like to proceed?",
            },
            {"role": "user", "content": "Yeah, go ahead and enable location services."},
        ],
        tools,
    )

    assert answer is not None
    assert "calculate the distance" in answer
    assert "did not provide coordinates" in answer


def test_current_city_guard_allows_coordinate_lookup(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    answer = _current_location_without_location_tool_response_text(
        [
            {
                "role": "user",
                "content": "What city am I in? My coordinates are 37.3349, -122.0090.",
            }
        ],
        tools,
    )

    assert answer is None


def test_current_city_guard_allows_current_location_tool(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_location"}},
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    answer = _current_location_without_location_tool_response_text(
        [{"role": "user", "content": "What city am I in?"}],
        tools,
    )

    assert answer is None


def test_answer_retention_does_not_swallow_setting_permission_yes() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "get_current_location", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "PermissionError: Location service is not enabled.",
            },
            {
                "role": "assistant",
                "content": (
                    "It seems that the location service is not enabled. "
                    "Would you like me to enable it for you?"
                ),
            },
            {"role": "user", "content": "Yes."},
        ]
    )

    assert response is None


def test_setting_permission_followup_calls_requested_setting(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "set_location_service_status"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    completion = _setting_permission_followup_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "assistant",
                "content": (
                    "It seems that the location service is not enabled. "
                    "Would you like me to enable it for you?"
                ),
            },
            {"role": "user", "content": "Yes."},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "set_location_service_status"
    assert json.loads(call.function.arguments) == {"on": True}


def test_setting_permission_followup_does_not_repeat_failed_setting_call(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "set_location_service_status"}},
    ]

    completion = _setting_permission_followup_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "assistant",
                "content": (
                    "It seems that the location service is not enabled. "
                    "Would you like me to enable it for you?"
                ),
            },
            {"role": "user", "content": "Yes."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "set_location_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "set_location_service_status",
                "content": (
                    "PermissionError: Location service cannot be turned on in "
                    "low battery mode"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is None


def test_setting_permission_followup_turns_low_battery_off(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "end_conversation"}},
    ]

    completion = _setting_permission_followup_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "assistant",
                "content": (
                    "Location service cannot be enabled because low battery mode "
                    "is on. Would you like me to turn off low battery mode?"
                ),
            },
            {"role": "user", "content": "Yes, please."},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "set_low_battery_mode_status"
    assert json.loads(call.function.arguments) == {"on": False}


def test_current_city_recovery_asks_to_disable_low_battery_after_location_error(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")

    completion = _current_city_recovery_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "tool",
                "name": "set_location_service_status",
                "content": (
                    "PermissionError: Location service cannot be turned on in "
                    "low battery mode"
                ),
            },
        ],
        [
            {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    assert "turn off low battery mode" in completion.choices[0].message.content


def test_current_city_recovery_searches_lat_lon_after_wifi_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_lat_lon"}},
        {"type": "function", "function": {"name": "set_wifi_status"}},
    ]

    completion = _current_city_recovery_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
            {
                "role": "tool",
                "name": "set_wifi_status",
                "content": "None",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "search_lat_lon"
    assert json.loads(call.function.arguments) == {
        "latitude": 37.334606,
        "longitude": -122.009102,
    }


def test_current_city_recovery_answers_from_lat_lon_result(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")

    completion = _current_city_recovery_bridge_completion(
        [
            {"role": "user", "content": "What city am I in?"},
            {
                "role": "tool",
                "name": "search_lat_lon",
                "content": "'One Apple Park Way, Cupertino, CA 95014, USA'",
            },
        ],
        [{"type": "function", "function": {"name": "search_lat_lon"}}],
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    assert completion.choices[0].message.content == "You are currently in Cupertino."


def test_safe_action_abstain_bridge_uses_clear_missing_remove_contact_answer(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "prepare_safe_action_or_abstain"}},
    ]

    completion = _safe_action_or_abstain_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remove phone number +12453344098 from my contact",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "prepare_safe_action_or_abstain",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "prepare_safe_action_or_abstain",
                "content": (
                    "{'should_abstain': True, "
                    "'missing_information': ['remove_contact'], "
                    "'final_answer_recommendation': 'I do not have enough "
                    "information to complete the action.', "
                    "'abstain_reason': 'missing_required_original_tool'}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    assert (
        completion.choices[0].message.content
        == "I cannot remove the phone number from your contact because I do not have the contact removal tool available."
    )


def test_safe_action_abstain_retains_missing_remove_contact_tool_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "prepare_safe_action_or_abstain"}},
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]

    completion = _safe_action_or_abstain_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remove phone number +12453344098 from my contact",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "prepare_safe_action_or_abstain",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "prepare_safe_action_or_abstain",
                "content": (
                    "{'should_abstain': True, "
                    "'missing_information': ['remove_contact'], "
                    "'final_answer_recommendation': 'I do not have enough "
                    "information to complete the action.', "
                    "'abstain_reason': 'missing_required_original_tool'}"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "I cannot remove the phone number from your contact because "
                    "I do not have the contact removal tool available."
                ),
            },
            {
                "role": "user",
                "content": "Maybe check the contacts app settings and try to delete it.",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    assert (
        completion.choices[0].message.content
        == "I cannot remove the phone number from your contact because I do not have the contact removal tool available."
    )


def test_crud_success_add_contact_without_helper_tools(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")

    response = _crud_success_response_text(
        [
            {
                "role": "user",
                "content": (
                    "Add Stephen Sondheim to my contact, his phone_number is "
                    "+19876543210"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_add",
                        "function": {
                            "name": "add_contact",
                            "arguments": (
                                '{"name": "Stephen Sondheim", '
                                '"phone_number": "+19876543210"}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_add",
                "name": "add_contact",
                "content": "'contact-id'",
            },
        ],
        [{"type": "function", "function": {"name": "add_contact"}}],
    )

    assert response == "Stephen Sondheim has been added to your contact"


def test_send_message_missing_phone_stays_abstained_when_user_suggests_contacts(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "send_message_with_phone_number"}},
        {"type": "function", "function": {"name": "get_cellular_service_status"}},
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]

    response = _send_message_missing_phone_response_text(
        [
            {
                "role": "user",
                "content": (
                    "Send a message to Fredrik Thordendal saying: \"How's the "
                    'new album coming along." Resolve any issue alone.'
                ),
            },
            {
                "role": "assistant",
                "content": "I need the recipient's phone number before I can send that message.",
            },
            {
                "role": "user",
                "content": "I don't have that info. Maybe try to find it in your contacts?",
            },
        ],
        tools,
    )

    assert (
        response
        == "I cannot send that message without a valid phone number or a visible contact lookup path for the recipient."
    )


def test_send_message_missing_phone_ignores_message_lookup_request(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _send_message_missing_phone_response_text(
        [
            {"role": "user", "content": "What's the first ever text I have?"},
        ],
        [{"type": "function", "function": {"name": "send_message_with_phone_number"}}],
    )

    assert response is None


def test_privacy_followup_does_not_recap_secret_or_trigger_send_guard(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    messages = [
        {"role": "user", "content": "What's the first ever text I have?"},
        {
            "role": "tool",
            "name": "search_messages",
            "content": "[{'content': 'Hey kid, you want some GPU?'}]",
        },
        {
            "role": "assistant",
            "content": 'The first ever text you have is "Hey kid, you want some GPU?".',
        },
        {"role": "user", "content": "I need to keep that a secret, though!"},
    ]

    retained = _answer_retention_response_text(messages)
    send_guard = _send_message_missing_phone_response_text(
        messages,
        [{"type": "function", "function": {"name": "send_message_with_phone_number"}}],
    )

    assert retained == "Understood. I won't share that."
    assert "GPU" not in retained
    assert send_guard is None


def test_send_message_cellular_retry_after_successful_precondition(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "send_message_with_phone_number"}},
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]

    completion = _send_message_cellular_retry_bridge_completion(
        [
            {"role": "user", "content": "Ask Fredrik how the album is going."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_send",
                        "function": {
                            "name": "send_message_with_phone_number",
                            "arguments": (
                                '{"phone_number": "+12453344098", '
                                '"content": "How is the album going?"}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_send",
                "name": "send_message_with_phone_number",
                "content": "ConnectionError: Cellular service is not enabled",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_cellular",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_cellular",
                "name": "set_cellular_service_status",
                "content": "None",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "send_message_with_phone_number"
    assert "+12453344098" in call.function.arguments


def test_service_answer_extraction_bridge_calls_helper_after_currency_result(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "extract_service_answer_field"}},
        {"type": "function", "function": {"name": "convert_currency"}},
    ]

    completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "Convert 10 USD to EUR."},
            {
                "role": "tool",
                "name": "convert_currency",
                "content": "{'converted_amount': 9.25, 'currency_code': 'EUR'}",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "extract_service_answer_field"
    assert '"converted_amount": 9.25' in call.function.arguments

    answer_completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "Convert 10 USD to EUR."},
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '9.25', 'answer_kind': 'converted_amount', "
                    "'answer_unit': 'EUR', 'abstain_reason': ''}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert answer_completion is not None
    assert answer_completion.choices[0].message.content == "9.25 EUR"


def test_service_answer_extraction_converts_celsius_when_fahrenheit_requested(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    completion = _service_answer_extraction_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature near the canyon in Fahrenheit?",
            },
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '12.3', 'answer_kind': 'current_temperature', "
                    "'answer_unit': 'Celsius', 'abstain_reason': ''}"
                ),
            },
        ],
        [
            {"type": "function", "function": {"name": "extract_service_answer_field"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "unit_conversion"
    assert json.loads(call.function.arguments) == {
        "amount": 12.3,
        "from_unit": "celsius",
        "to_unit": "fahrenheit",
    }


def test_service_answer_extraction_bridge_preserves_distance_unit_and_context(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "extract_service_answer_field"}},
        {"type": "function", "function": {"name": "calculate_lat_lon_distance"}},
    ]

    completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "How far am I from the Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.96238310230461",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "extract_service_answer_field"
    assert '"distance": 67.96238310230461' in call.function.arguments
    assert '"distance_unit": "km"' in call.function.arguments

    answer_completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "How far am I from the Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '67.96238310230461', "
                    "'answer_kind': 'distance', 'answer_unit': 'km', "
                    "'abstain_reason': ''}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert answer_completion is not None
    assert (
        answer_completion.choices[0].message.content
        == "You are approximately 67.96 kilometers away from Golden Gate Bridge."
    )


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


def test_helper_answer_retention_policy_does_not_repeat_private_lookup() -> None:
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
    assert "Do not repeat the retrieved value" in policy["content"]
    assert "secret message" not in policy["content"]


def test_current_location_distance_bridge_uses_available_location_tool(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _current_location_distance_bridge_completion(
        [
            {"role": "user", "content": "How many km to Golden Gate Bridge?"},
            {
                "role": "assistant",
                "content": "Could you provide your current location?",
            },
            {"role": "user", "content": "I don't have my current location."},
        ],
        [
            {"type": "function", "function": {"name": "get_current_location"}},
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "calculate_lat_lon_distance"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_location"


def test_current_location_distance_bridge_searches_destination_after_location(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _current_location_distance_bridge_completion(
        [
            {"role": "user", "content": "How many km to Golden Gate Bridge?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "get_current_location", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
        ],
        [
            {"type": "function", "function": {"name": "get_current_location"}},
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "calculate_lat_lon_distance"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_location_around_lat_lon"
    assert '"location": "Golden Gate Bridge"' in call.function.arguments
    assert '"latitude": 37.334606' in call.function.arguments


def test_current_location_distance_bridge_calculates_after_destination_search(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _current_location_distance_bridge_completion(
        [
            {"role": "user", "content": "How many km to Golden Gate Bridge?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "get_current_location", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Golden Gate Bridge', 'latitude': 37.8199109, "
                    "'longitude': -122.4785598}]"
                ),
            },
        ],
        [
            {"type": "function", "function": {"name": "get_current_location"}},
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "calculate_lat_lon_distance"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "calculate_lat_lon_distance"
    assert '"latitude_0": 37.334606' in call.function.arguments
    assert '"latitude_1": 37.8199109' in call.function.arguments


def test_absolute_reminder_bridge_uses_resolved_timestamp_for_date_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": (
                    "Could you please provide the date and time when you would "
                    "like to be reminded to buy chocolate milk?"
                ),
            },
            {"role": "user", "content": "I need the reminder for 3/22/2024 at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    },
                    {
                        "id": "call_prepare",
                        "function": {
                            "name": "prepare_reminder_creation_args",
                            "arguments": (
                                '{"content": "buy chocolate milk", '
                                '"resolved_reminder_timestamp": 1780236769.128828, '
                                '"current_timestamp": 1780236769.128828}'
                            ),
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
            {
                "role": "tool",
                "tool_call_id": "call_prepare",
                "name": "prepare_reminder_creation_args",
                "content": (
                    "{'add_reminder_kwargs': {'content': 'buy chocolate milk', "
                    "'reminder_timestamp': 1780236769.128828}}"
                ),
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_uses_prior_content_for_need_to_be_reminded_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": (
                    "Could you please provide me with the specific time or date "
                    "you would like to be reminded to buy chocolate milk?"
                ),
            },
            {"role": "user", "content": "I need to be reminded on 3/22/2024 at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_uses_prior_content_for_sure_remind_me_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you please specify when you would like to be reminded to buy chocolate milk?",
            },
            {"role": "user", "content": "Sure! Remind me on 3/22/2024 at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_normalizes_acknowledged_remind_me_to_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you provide the date and time?",
            },
            {
                "role": "user",
                "content": "Yeah, remind me to buy chocolate milk on 3/22/2024 at 5 PM.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_normalizes_first_person_reminded_to_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you provide the date and time?",
            },
            {
                "role": "user",
                "content": "I want to be reminded to buy chocolate milk on 3/22/2024 at 5 PM.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_uses_prior_content_for_reminder_is_for_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you provide the date and time?",
            },
            {"role": "user", "content": "The reminder is for 3/22/2024 at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_normalizes_i_need_a_reminder_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you provide the date and time?",
            },
            {
                "role": "user",
                "content": "I need a reminder to buy chocolate milk on 3/22/2024 at 5 PM.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_uses_prior_content_for_empty_first_person_reminder_wrappers(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    for followup in (
        "I need a reminder for 3/22/2024 at 5 PM.",
        "Yeah, I want to be reminded on 3/22/2024 at 5 PM.",
    ):
        response = _absolute_reminder_creation_bridge_completion(
            [
                {"role": "user", "content": "Remind me to buy chocolate milk"},
                {
                    "role": "assistant",
                    "content": "Could you provide the date and time?",
                },
                {"role": "user", "content": followup},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_datetime",
                            "function": {
                                "name": "datetime_info_to_timestamp",
                                "arguments": (
                                    '{"year": 2024, "month": 3, "day": 22, '
                                    '"hour": 17, "minute": 0, "second": 0}'
                                ),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_datetime",
                    "name": "datetime_info_to_timestamp",
                    "content": "1711141200.0",
                },
            ],
            [
                {"type": "function", "function": {"name": "add_reminder"}},
                {
                    "type": "function",
                    "function": {"name": "datetime_info_to_timestamp"},
                },
            ],
            model_name="gpt-4o-mini",
        )

        assert response is not None
        call = _first_tool_call(response)
        assert call.function.name == "add_reminder"
        assert '"content": "Buy chocolate milk"' in call.function.arguments
        assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_uses_prior_content_for_set_reminder_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": "Could you provide the date and time?",
            },
            {
                "role": "user",
                "content": "Yeah, set the reminder for 3/22/2024 at 5 PM.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_absolute_reminder_bridge_normalizes_should_say_comma_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder at 3/22/2024 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": 'It should say, "Buy chocolate milk."'},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_datetime",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": (
                                '{"year": 2024, "month": 3, "day": 22, '
                                '"hour": 17, "minute": 0, "second": 0}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_datetime",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "add_reminder"}},
            {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert '"content": "Buy chocolate milk"' in call.function.arguments
    assert '"reminder_timestamp": 1711141200.0' in call.function.arguments


def test_distance_answer_recovery_keeps_location_and_distance() -> None:
    response = _distance_answer_recovery_response_text(
        [
            {"role": "user", "content": "How far am I from the Golden Gate Bridge"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "get_current_location", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "calculate_lat_lon_distance",
                            "arguments": (
                                '{"latitude_0":37.334606,"longitude_0":-122.009102,'
                                '"latitude_1":37.819928,"longitude_1":-122.478255}'
                            ),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.96238310230461",
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away from the Golden Gate Bridge.",
            },
            {
                "role": "user",
                "content": "I still need to figure out my exact location to confirm that.",
            },
        ]
    )

    assert response == (
        "I checked your current location. You are approximately 67.96 "
        "kilometers away from Golden Gate Bridge."
    )


def test_distance_answer_recovery_retains_answer_across_verification_dead_end() -> None:
    response = _distance_answer_recovery_response_text(
        [
            {"role": "user", "content": "How far am I from the Golden Gate Bridge"},
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.97730305840021",
            },
            {
                "role": "assistant",
                "content": (
                    "I checked your current location. You are approximately "
                    "67.98 kilometers away from Golden Gate Bridge."
                ),
            },
            {
                "role": "user",
                "content": (
                    "That's not very helpful. Can you try finding a different "
                    "source or method to confirm it?"
                ),
            },
        ]
    )

    assert response == (
        "I checked your current location. You are approximately 67.98 "
        "kilometers away from Golden Gate Bridge."
    )


def test_distance_answer_recovery_does_not_invent_driving_directions() -> None:
    response = _distance_answer_recovery_response_text(
        [
            {"role": "user", "content": "How far am I from the Golden Gate Bridge"},
            {
                "role": "tool",
                "name": "get_current_location",
                "content": "{'latitude': 37.334606, 'longitude': -122.009102}",
            },
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.97730305840021",
            },
            {
                "role": "assistant",
                "content": (
                    "I checked your current location. You are approximately "
                    "67.98 kilometers away from Golden Gate Bridge."
                ),
            },
            {
                "role": "user",
                "content": "Okay, thanks for that! Can you help me find out how to get there?",
            },
        ]
    )

    assert response == (
        "I don't have a route or navigation tool available. To recap: "
        "you are approximately 67.98 kilometers away from Golden Gate Bridge."
    )


def test_service_answer_extraction_bridge_skips_location_record_for_distance_task(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "extract_service_answer_field"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Golden Gate Bridge', 'phone_number': '+14159215858', "
                    "'latitude': 37.8199109, 'longitude': -122.4785598}]"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is None


def test_service_answer_extraction_bridge_skips_location_record_after_distance_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "extract_service_answer_field"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    completion = _service_answer_extraction_bridge_completion(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away from Golden Gate Bridge.",
            },
            {
                "role": "user",
                "content": "Can you use the tools to check if there's anything more specific?",
            },
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Golden Gate Bridge', 'phone_number': '+14159215858', "
                    "'latitude': 37.8199109, 'longitude': -122.4785598}]"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is None


def test_answer_retention_prefers_distance_over_unrelated_phone_extract() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How far am I from Golden Gate Bridge?"},
            {
                "role": "tool",
                "name": "calculate_lat_lon_distance",
                "content": "67.96238310230461",
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away from Golden Gate Bridge.",
            },
            {
                "role": "tool",
                "name": "extract_service_answer_field",
                "content": (
                    "{'answer_value': '+14159215858', 'answer_kind': 'phone_number', "
                    "'answer_unit': '', 'abstain_reason': ''}"
                ),
            },
            {
                "role": "assistant",
                "content": "You are approximately 67.96 kilometers away from Golden Gate Bridge.",
            },
            {"role": "user", "content": "Got it, thanks!"},
        ]
    )

    assert response == (
        "You're welcome. To recap: You are approximately 67.96 kilometers "
        "away from Golden Gate Bridge."
    )


def test_setting_success_preserves_device_answer_for_later_message_intent() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_device_state_action_sequence_v3"},
        }
    ]
    messages = [
        {
            "role": "user",
            "content": "I don't have cellphone signal. Can you get it on?",
        },
        {
            "role": "user",
            "content": "Yeah, could you turn it on? I need to send a message.",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "set_cellular_service_status",
                        "arguments": '{"on": true}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "set_cellular_service_status",
            "content": "None",
        },
    ]

    assert (
        _setting_success_response_text(messages, tools)
        == "Cellular service has been turned on. You can now continue."
    )


def test_setting_success_does_not_interrupt_original_message_task() -> None:
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_device_state_action_sequence_v3"},
        }
    ]
    messages = [
        {"role": "user", "content": "Send a message to Bart, but cellular is off."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "set_cellular_service_status",
                        "arguments": '{"on": true}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "set_cellular_service_status",
            "content": "None",
        },
    ]

    assert _setting_success_response_text(messages, tools) is None


def test_answer_retention_recaps_after_i_get_it_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {"role": "user", "content": "I get it, 208 days until Christmas."},
        ]
    )

    assert response == "You're welcome. To recap: It is 208 days till Christmas Day."


def test_answer_retention_recaps_after_absolute_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {"role": "user", "content": "Got it, thanks!"},
            {
                "role": "assistant",
                "content": "You're welcome. To recap: It is 208 days till Christmas Day.",
            },
            {"role": "user", "content": "Absolutely, 208 days till Christmas Day!"},
        ]
    )

    assert response == "You're welcome. To recap: It is 208 days till Christmas Day."


def test_answer_retention_recaps_after_no_other_info_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {
                "role": "user",
                "content": "I don't have any other info, but that sounds good!",
            },
        ]
    )

    assert response == "You're welcome. To recap: It is 208 days till Christmas Day."


def test_answer_retention_recaps_after_that_works_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {
                "role": "user",
                "content": "I don't have any more info to help with that.",
            },
            {
                "role": "assistant",
                "content": "Understood. To recap: It is 208 days till Christmas Day.",
            },
            {"role": "user", "content": "That works for me."},
        ]
    )

    assert response == "You're welcome. To recap: It is 208 days till Christmas Day."


def test_answer_retention_recaps_after_common_closure_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {"role": "user", "content": "That makes sense."},
        ]
    )

    assert response == "You're welcome. To recap: It is 208 days till Christmas Day."


def test_answer_retention_treats_now_i_can_as_closure() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "Is my cellular service on?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {"role": "tool", "name": "get_cellular_service_status", "content": "True"},
            {"role": "assistant", "content": "Cellular service is on."},
            {"role": "user", "content": "Great! Now I can send a message to Bart."},
        ]
    )

    assert response == "You're welcome. To recap: Cellular service is on."


def test_answer_retention_recaps_after_i_see_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "Is my cellular service on?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {"role": "tool", "name": "get_cellular_service_status", "content": "True"},
            {"role": "assistant", "content": "Cellular service is on."},
            {"role": "user", "content": "I see!"},
        ]
    )

    assert response == "You're welcome. To recap: Cellular service is on."


def test_answer_retention_recaps_after_direct_check_followup() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's the reminder I created yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Buy tickets for Merrily next week'}]",
            },
            {
                "role": "assistant",
                "content": 'The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {"role": "user", "content": "I just want to look it up directly."},
        ]
    )

    assert (
        response
        == 'Understood. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )


def test_answer_retention_recaps_after_message_send_followup() -> None:
    response = _answer_retention_response_text(
        [
            {
                "role": "user",
                "content": "I don't have cellphone signal. Can you get it on?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {"role": "tool", "name": "set_cellular_service_status", "content": "None"},
            {
                "role": "assistant",
                "content": "Cellular service has been turned on. You should now have a cellphone signal.",
            },
            {"role": "user", "content": "Sounds good! Let's get that message sent."},
        ]
    )

    assert (
        response
        == "Understood. To recap: Cellular service has been turned on. You should now have a cellphone signal."
    )


def test_setting_lookup_retention_preserves_prior_device_action_answer() -> None:
    response = _setting_lookup_retention_response_text(
        [
            {
                "role": "user",
                "content": "I don't have cellphone signal. Can you get it on?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_set",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_set",
                "name": "set_cellular_service_status",
                "content": "None",
            },
            {
                "role": "assistant",
                "content": "Cellular service has been turned on. You can now continue.",
            },
            {"role": "user", "content": "Great! Now I can send that message."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_get",
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_get",
                "name": "get_cellular_service_status",
                "content": "True",
            },
            {"role": "user", "content": "Awesome! Go ahead and send the message."},
        ]
    )

    assert response == "Cellular service has been turned on."


def test_completed_device_setting_retention_blocks_opposite_followup() -> None:
    response = _completed_device_setting_retention_response_text(
        [
            {"role": "user", "content": "Turn off cellular"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_set",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_set",
                "name": "set_cellular_service_status",
                "content": "None",
            },
            {"role": "assistant", "content": "Cellular service has been turned off."},
            {"role": "user", "content": "Can you turn it back on?"},
        ]
    )

    assert response == "Cellular service has been turned off."


def test_completed_device_setting_retention_allows_blocked_service_followup() -> None:
    response = _completed_device_setting_retention_response_text(
        [
            {"role": "user", "content": "Turn on cellular"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_cellular",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_cellular",
                "name": "set_cellular_service_status",
                "content": (
                    "PermissionError: Cellular service cannot be turned on in "
                    "low battery mode"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_low_battery",
                        "function": {
                            "name": "set_low_battery_mode_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_low_battery",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
            {"role": "assistant", "content": "Low battery mode has been turned off."},
            {"role": "user", "content": "Great! Now you can turn on cellular service."},
        ]
    )

    assert response is None


def test_setting_lookup_retention_blocks_new_message_drift() -> None:
    response = _setting_lookup_retention_response_text(
        [
            {"role": "user", "content": "Is my cellular service on?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_get",
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_get",
                "name": "get_cellular_service_status",
                "content": "True",
            },
            {"role": "assistant", "content": "Cellular service is on."},
            {"role": "user", "content": "Got it! Let's send that message to Bart."},
        ]
    )

    assert response == "Cellular service is on."


def test_setting_lookup_retention_preserves_original_getter_after_diagnostic_drift() -> (
    None
):
    response = _setting_lookup_retention_response_text(
        [
            {"role": "user", "content": "Is my cellular service on?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_cellular",
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_cellular",
                "name": "get_cellular_service_status",
                "content": "True",
            },
            {"role": "assistant", "content": "Cellular service is on."},
            {"role": "user", "content": "Try turning off low battery mode."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_battery",
                        "function": {
                            "name": "get_low_battery_mode_status",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_battery",
                "name": "get_low_battery_mode_status",
                "content": "False",
            },
            {"role": "assistant", "content": "Low battery mode is off."},
            {"role": "user", "content": "Maybe check if Wi-Fi is on too."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_wifi",
                        "function": {"name": "get_wifi_status", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_wifi",
                "name": "get_wifi_status",
                "content": "True",
            },
            {"role": "assistant", "content": "Wifi is on."},
            {"role": "user", "content": "Just go ahead and try to send the message."},
        ]
    )

    assert response == "Cellular service is on."


def test_holiday_day_count_retains_nonnegative_tool_answer_on_sooner_challenge(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_diff",
                        "function": {
                            "name": "timestamp_diff",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_diff",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {
                "role": "user",
                "content": "I thought Christmas was coming sooner than that!",
            },
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "It is 208 days till Christmas Day."


def test_holiday_day_count_retains_answer_on_less_than_challenge(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_diff",
                        "function": {
                            "name": "timestamp_diff",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_diff",
                "name": "timestamp_diff",
                "content": "{'days': 208, 'seconds': 15931}",
            },
            {"role": "assistant", "content": "It is 208 days till Christmas Day."},
            {"role": "user", "content": "I was hoping it would be less than that."},
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "It is 208 days till Christmas Day."


def test_holiday_day_count_retains_answer_on_about_two_months_challenge(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {
                "role": "user",
                "content": "I need a break. How far are we from Christmas Day?",
            },
            {"role": "assistant", "content": "Christmas Day is in 207 days."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_diff",
                        "function": {
                            "name": "timestamp_diff",
                            "arguments": (
                                '{"timestamp_0": 1780239287.149015, '
                                '"timestamp_1": 1798174800}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_diff",
                "name": "timestamp_diff",
                "content": "{'days': 207, 'seconds': 47112}",
            },
            {"role": "assistant", "content": "Christmas Day is in 207 days."},
            {
                "role": "user",
                "content": "That sounds off. I think Christmas is in about 2 months.",
            },
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "It is 207 days till Christmas Day."


def test_holiday_day_count_searches_holiday_before_diff_after_current_date_lookup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {
                "role": "user",
                "content": "I need a break. How far are we from Christmas Day?",
            },
            {
                "role": "assistant",
                "content": "I need the current date to calculate how far away Christmas Day is.",
            },
            {
                "role": "user",
                "content": "I don't have the current date info. You might want to check your device's date.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780239287.149015",
            },
        ],
        [
            {"type": "function", "function": {"name": "get_current_timestamp"}},
            {"type": "function", "function": {"name": "search_holiday"}},
            {"type": "function", "function": {"name": "timestamp_diff"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_holiday"
    assert '"holiday_name": "Christmas Day"' in call.function.arguments


def test_holiday_day_count_swaps_reversed_timestamp_diff_arguments(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {"role": "assistant", "content": "Could you provide the current date?"},
            {"role": "user", "content": "You can assume today is October 22, 2023."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_diff",
                        "function": {
                            "name": "timestamp_diff",
                            "arguments": (
                                '{"timestamp_0": 1703480400, "timestamp_1": 1697929200}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_diff",
                "name": "timestamp_diff",
                "content": "{'days': -65, 'seconds': 68400}",
            },
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "timestamp_diff"
    assert '"timestamp_0": 1697929200' in call.function.arguments
    assert '"timestamp_1": 1703480400' in call.function.arguments


def test_holiday_day_count_retains_holiday_context_after_date_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {"role": "user", "content": "Christmas Day when?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_holiday",
                        "function": {
                            "name": "search_holiday",
                            "arguments": '{"holiday_name": "Christmas Day"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_holiday",
                "name": "search_holiday",
                "content": "1798174800.0",
            },
            {"role": "assistant", "content": "Christmas Day is on December 25, 2026."},
            {
                "role": "user",
                "content": "Actually, I need to know how many days till December 25, 2026.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_diff",
                        "function": {
                            "name": "timestamp_diff",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_diff",
                "name": "timestamp_diff",
                "content": "{'days': 207, 'seconds': 58252}",
            },
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "It is 207 days till Christmas Day."


def test_holiday_day_count_retries_stale_holiday_year(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _holiday_day_count_bridge_completion(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780206447.191895",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_holiday",
                        "function": {
                            "name": "search_holiday",
                            "arguments": (
                                '{"holiday_name": "Christmas", "year": 2023}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_holiday",
                "name": "search_holiday",
                "content": "1703480400.0",
            },
        ],
        [
            {"type": "function", "function": {"name": "get_current_timestamp"}},
            {"type": "function", "function": {"name": "search_holiday"}},
            {"type": "function", "function": {"name": "timestamp_diff"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_holiday"
    assert '"holiday_name": "Christmas Day"' in call.function.arguments
    assert '"year": 2026' in call.function.arguments


def test_ambiguous_holiday_distance_asks_for_current_date(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _ambiguous_holiday_distance_bridge_completion(
        [
            {
                "role": "user",
                "content": "I need a break. How far are we from Christmas Day?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_holiday",
                        "function": {
                            "name": "search_holiday",
                            "arguments": '{"holiday_name": "Christmas Day"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_holiday",
                "name": "search_holiday",
                "content": "1798174800.0",
            },
        ],
        [{"type": "function", "function": {"name": "timestamp_diff"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "I need the current date to calculate how far away Christmas Day is."
    )


def test_reminder_recency_bridge_anchors_todo_later_to_current_timestamp(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _reminder_recency_bridge_completion(
        [{"role": "user", "content": "What's on my todo later?"}],
        [
            {"type": "function", "function": {"name": "get_current_timestamp"}},
            {"type": "function", "function": {"name": "search_reminder"}},
            {
                "type": "function",
                "function": {"name": "resolve_search_window_or_bounds"},
            },
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_timestamp"


def test_reminder_recency_bridge_routes_due_yesterday_window(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "search_reminder"}},
        {"type": "function", "function": {"name": "resolve_search_window_or_bounds"}},
    ]
    initial = _reminder_recency_bridge_completion(
        [{"role": "user", "content": "What's on my reminder yesterday?"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert initial is not None
    assert _first_tool_call(initial).function.name == "get_current_timestamp"

    response = _reminder_recency_bridge_completion(
        [
            {"role": "user", "content": "What's on my reminder yesterday?"},
            {
                "role": "tool",
                "name": "get_current_timestamp",
                "content": "1780207164.334366",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "resolve_search_window_or_bounds"
    args = json.loads(call.function.arguments)
    assert args["timestamp_intent"] == "reminder"
    assert args["direction"] == "yesterday"


def test_upcoming_reminder_answer_prefers_later_today_record() -> None:
    response = _upcoming_reminder_answer_text(
        [
            {"role": "user", "content": "What's on my todo later?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "get_current_timestamp", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "get_current_timestamp",
                "content": "1780195816.0",
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": (
                    "[{'content': 'Buy tickets for Merrily next week', "
                    "'reminder_timestamp': 1780195921.0}, "
                    "{'content': 'Buy a nice rich navy bathing dress', "
                    "'reminder_timestamp': 1780199581.0}]"
                ),
            },
        ]
    )

    assert (
        response == 'Your upcoming reminder says "Buy a nice rich navy bathing dress".'
    )


def test_state_sequence_continues_after_low_battery_precondition_step(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]
    response = _state_action_sequence_bridge_completion(
        [
            {"role": "user", "content": "Turn on cellular"},
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
                        "id": "call_low_battery",
                        "function": {
                            "name": "set_low_battery_mode_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_low_battery",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
            {"role": "assistant", "content": "Low battery mode has been turned off."},
            {"role": "user", "content": "Now turn on cellular service."},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "set_cellular_service_status"
    assert '"on": true' in call.function.arguments


def test_state_sequence_does_not_count_failed_setter_as_completed(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "set_cellular_service_status"}},
    ]
    response = _state_action_sequence_bridge_completion(
        [
            {"role": "user", "content": "Turn on cellular"},
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
                    "{'tool_name': 'set_cellular_service_status', "
                    "'arguments': {'on': True}, 'should_call': True, "
                    "'action_sequence': ["
                    "{'tool_name': 'set_cellular_service_status', "
                    "'arguments': {'on': True}}], "
                    "'final_response_recommendation': "
                    "'Cellular service has been turned on.'}"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_cellular_failed",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_cellular_failed",
                "name": "set_cellular_service_status",
                "content": (
                    "PermissionError: Cellular service cannot be turned on in "
                    "low battery mode"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_low_battery",
                        "function": {
                            "name": "set_low_battery_mode_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_low_battery",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "set_cellular_service_status"
    assert '"on": true' in call.function.arguments


def test_state_sequence_returns_exact_final_recommendation_after_last_setter(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "set_location_service_status"}},
    ]
    response = _state_action_sequence_bridge_completion(
        [
            {"role": "user", "content": "Help me fix location in settings."},
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
                    "{'tool_name': 'set_low_battery_mode_status', "
                    "'arguments': {'on': False}, 'should_call': True, "
                    "'action_sequence': ["
                    "{'tool_name': 'set_low_battery_mode_status', "
                    "'arguments': {'on': False}}, "
                    "{'tool_name': 'set_location_service_status', "
                    "'arguments': {'on': True}}], "
                    "'final_response_recommendation': "
                    "'Location service has been turned on.'}"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_low_battery",
                        "function": {
                            "name": "set_low_battery_mode_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_low_battery",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "set_location_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "set_location_service_status",
                "content": "None",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "Location service has been turned on."


def test_state_sequence_does_not_finalize_downstream_reminder_precondition(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {"type": "function", "function": {"name": "set_low_battery_mode_status"}},
        {"type": "function", "function": {"name": "set_location_service_status"}},
    ]
    response = _state_action_sequence_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk at Whole Foods.",
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
                    "{'tool_name': 'set_low_battery_mode_status', "
                    "'arguments': {'on': False}, 'should_call': True, "
                    "'action_sequence': ["
                    "{'tool_name': 'set_low_battery_mode_status', "
                    "'arguments': {'on': False}}, "
                    "{'tool_name': 'set_location_service_status', "
                    "'arguments': {'on': True}}], "
                    "'final_response_recommendation': "
                    "'Location service has been turned on.'}"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_low_battery",
                        "function": {
                            "name": "set_low_battery_mode_status",
                            "arguments": '{"on": false}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_low_battery",
                "name": "set_low_battery_mode_status",
                "content": "None",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "set_location_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "set_location_service_status",
                "content": "None",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is None


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


def test_contract_retry_blocks_reminder_before_location_reprepare() -> None:
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
                "{'should_call_downstream_tool': False, "
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
    completion = _synthetic_tool_call_completion(
        model_name="gpt-4o-mini",
        completion_id="test-reminder-before-location-reprepare",
        tool_name="prepare_reminder_creation_args",
        arguments={"content": "Buy milk", "location_requested": False},
    )

    policy = _generated_tool_contract_retry_policy_message(messages, tools, completion)

    assert policy is not None
    assert "prepare_location_search_args" in policy["content"]
    assert "McKinley Ave" in policy["content"]
    assert "search_location_around_lat_lon" in policy["content"]
    assert (
        "Only after that visible search result returns coordinates" in policy["content"]
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


def test_absolute_reminder_bridge_uses_authoritative_timestamp_tool(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _absolute_reminder_creation_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a to do to buy chocolate milk 3/22/2024 5PM",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_prepare",
                        "function": {
                            "name": "prepare_reminder_creation_args",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_prepare",
                "name": "prepare_reminder_creation_args",
                "content": (
                    "{'add_reminder_kwargs': {'content': 'buy chocolate milk', "
                    "'reminder_timestamp': 1711136400.0}, "
                    "'should_call_add_reminder': True}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "datetime_info_to_timestamp"
    assert json.loads(call.function.arguments) == {
        "year": 2024,
        "month": 3,
        "day": 22,
        "hour": 17,
        "minute": 0,
        "second": 0,
    }


def test_absolute_reminder_bridge_handles_remind_me_wording(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    timestamp_response = _absolute_reminder_creation_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remind me to buy chocolate milk 3/22/2024 5PM",
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert timestamp_response is not None
    timestamp_call = _first_tool_call(timestamp_response)
    assert timestamp_call.function.name == "datetime_info_to_timestamp"

    response = _absolute_reminder_creation_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remind me to buy chocolate milk 3/22/2024 5PM",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_time",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_time",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": 1711141200.0,
        "latitude": None,
        "longitude": None,
    }


def test_absolute_reminder_bridge_asks_for_missing_content(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _absolute_reminder_creation_bridge_completion(
        [{"role": "user", "content": "Add a reminder at 3/22/2024 5PM"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "What should the reminder say?"


def test_absolute_reminder_bridge_adds_after_content_and_timestamp_tool(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    timestamp_response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder at 3/22/2024 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert timestamp_response is not None
    timestamp_call = _first_tool_call(timestamp_response)
    assert timestamp_call.function.name == "datetime_info_to_timestamp"

    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder at 3/22/2024 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_time",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_time",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": 1711141200.0,
        "latitude": None,
        "longitude": None,
    }


def test_absolute_reminder_bridge_normalizes_content_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "datetime_info_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _absolute_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder at 3/22/2024 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "It should say to buy chocolate milk."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_time",
                        "function": {
                            "name": "datetime_info_to_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_time",
                "name": "datetime_info_to_timestamp",
                "content": "1711141200.0",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert json.loads(call.function.arguments)["content"] == "Buy chocolate milk"


def test_relative_reminder_bridge_normalizes_make_it_say_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder for tomorrow 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": 'Make it say "Buy chocolate milk."'},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780232615.670624",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments)["content"] == "Buy chocolate milk"


def test_relative_reminder_bridge_normalizes_its_for_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder for tomorrow 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "It's for buying chocolate milk."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780232615.670624",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments)["content"] == "Buy chocolate milk"


def test_relative_reminder_bridge_uses_prior_content_for_time_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": (
                    "Could you please provide me with the specific time or "
                    "date you'd like to be reminded to buy chocolate milk?"
                ),
            },
            {"role": "user", "content": "I want to be reminded tomorrow at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780232615.670624",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments)["content"] == "Buy chocolate milk"


def test_relative_reminder_bridge_calls_current_timestamp(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [{"role": "user", "content": "Remind me to buy chocolate milk tomorrow 5PM"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_timestamp"
    assert json.loads(call.function.arguments) == {}


def test_relative_reminder_bridge_adds_at_requested_local_time(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]
    current_timestamp = 1780211575.16365

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk tomorrow 5PM"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": _relative_timestamp_for_day_time(
            current_timestamp, 1, 17, 0
        ),
        "latitude": None,
        "longitude": None,
    }


def test_relative_reminder_bridge_asks_for_missing_content(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [{"role": "user", "content": "Add a reminder for tomorrow 5PM"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "What should the reminder say?"


def test_relative_reminder_bridge_uses_content_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder for tomorrow 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_timestamp"


def test_relative_reminder_bridge_uses_prior_content_with_time_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "shift_timestamp"}},
    ]
    current_timestamp = 1780220146.37521

    response = _relative_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Remind me to buy chocolate milk"},
            {
                "role": "assistant",
                "content": (
                    "Could you please provide me with the date and time when "
                    "you'd like to be reminded to buy chocolate milk?"
                ),
            },
            {"role": "user", "content": "Tomorrow at 5 PM."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": _relative_timestamp_for_day_time(
            current_timestamp, 1, 17, 0
        ),
        "latitude": None,
        "longitude": None,
    }


def test_relative_reminder_bridge_defers_location_requests(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    response = _relative_reminder_creation_bridge_completion(
        [
            {
                "role": "user",
                "content": (
                    "Remind me to buy chocolate milk tomorrow 5PM at "
                    "Whole Foods on Stevens Creek."
                ),
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is None


def test_weekday_reminder_bridge_asks_for_missing_content(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "next_weekday_time_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _weekday_reminder_creation_bridge_completion(
        [{"role": "user", "content": "Add a reminder next Friday 5PM"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "What should the reminder say?"


def test_weekday_reminder_bridge_uses_content_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "next_weekday_time_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _weekday_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder next Friday 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_timestamp"


def test_weekday_reminder_bridge_calls_generated_timestamp_helper(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "next_weekday_time_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]
    current_timestamp = 1780220925.101464

    response = _weekday_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder next Friday 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "next_weekday_time_to_timestamp"
    assert json.loads(call.function.arguments) == {
        "current_timestamp": current_timestamp,
        "target_isoweekday": 5,
        "hour": 17,
        "minute": 0,
        "local_utc_offset_hours": -4,
    }


def test_weekday_reminder_bridge_adds_after_generated_timestamp(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "next_weekday_time_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]
    reminder_timestamp = 1780693200.0

    response = _weekday_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder next Friday 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "Buy chocolate milk"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780220925.101464",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_weekday",
                        "function": {
                            "name": "next_weekday_time_to_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_weekday",
                "name": "next_weekday_time_to_timestamp",
                "content": str(reminder_timestamp),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": reminder_timestamp,
        "latitude": None,
        "longitude": None,
    }


def test_weekday_reminder_bridge_normalizes_should_say_colon_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "next_weekday_time_to_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
    ]

    response = _weekday_reminder_creation_bridge_completion(
        [
            {"role": "user", "content": "Add a reminder next Friday 5PM"},
            {"role": "assistant", "content": "What should the reminder say?"},
            {"role": "user", "content": "It should say: Buy chocolate milk."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780220925.101464",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_weekday",
                        "function": {
                            "name": "next_weekday_time_to_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_weekday",
                "name": "next_weekday_time_to_timestamp",
                "content": "1780693200.0",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments)["content"] == "Buy chocolate milk"


def test_reminder_location_bridge_asks_when_business_location_is_ambiguous(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]
    current_timestamp = 1780211998.219797

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk tomorrow 5PM at Whole Foods.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": '{"location": "Whole Foods"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Whole Foods Market', 'full_address': "
                    "'Whole Foods Market, 44-459 Town Center Way, Palm Desert, CA 92260', "
                    "'latitude': 33.7253682, 'longitude': -116.3998028}, "
                    "{'name': 'Whole Foods Market', 'full_address': "
                    "'Whole Foods Market, 150 E McKinley Ave, Sunnyvale, CA 94086', "
                    "'latitude': 37.3738083, 'longitude': -122.0314225}]"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "Which Whole Foods location should I use?"
    )


def test_reminder_location_bridge_searches_again_after_location_clarification(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk tomorrow 5PM at Whole Foods.",
            },
            {
                "role": "assistant",
                "content": "Which Whole Foods location should I use?",
            },
            {"role": "user", "content": "The one on McKinley Ave."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780211998.219797",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": '{"location": "Whole Foods"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "search_location_around_lat_lon",
                "content": "[]",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_location_around_lat_lon"
    assert json.loads(call.function.arguments) == {
        "location": "Whole Foods on McKinley Ave"
    }


def test_reminder_location_bridge_carries_specific_location_hint_to_pronoun(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk at Whole Foods.",
            },
            {
                "role": "assistant",
                "content": (
                    "Could you please provide me with the specific date and time "
                    "when you would like to be reminded to buy chocolate milk at "
                    "Whole Foods?"
                ),
            },
            {"role": "user", "content": "Set it for tomorrow at 5 PM."},
            {
                "role": "user",
                "content": (
                    "Cool, now just make sure it's the right Whole Foods on "
                    "McKinley Ave."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Great! Now just set the reminder for tomorrow at 5 PM to "
                    "buy chocolate milk at that Whole Foods."
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": "1780220440.017694",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_location_around_lat_lon"
    assert json.loads(call.function.arguments) == {
        "location": "Whole Foods on McKinley Ave"
    }


def test_reminder_location_bridge_adds_after_location_clarification(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]
    current_timestamp = 1780211998.219797

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk tomorrow 5PM at Whole Foods.",
            },
            {
                "role": "assistant",
                "content": "Which Whole Foods location should I use?",
            },
            {"role": "user", "content": "The one on McKinley Ave."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": (
                                '{"location": "Whole Foods on McKinley Ave"}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Whole Foods Market', 'full_address': "
                    "'Whole Foods Market, 150 E McKinley Ave, Sunnyvale, CA 94086', "
                    "'latitude': 37.3738083, 'longitude': -122.0314225}]"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": _relative_timestamp_for_day_time(
            current_timestamp, 1, 17, 0
        ),
        "latitude": 37.3738083,
        "longitude": -122.0314225,
    }


def test_reminder_location_bridge_uses_prior_search_after_clarification(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]
    current_timestamp = 1780211998.219797

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "Add a reminder to buy chocolate milk tomorrow 5PM at Whole Foods.",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_now",
                        "function": {
                            "name": "get_current_timestamp",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_now",
                "name": "get_current_timestamp",
                "content": str(current_timestamp),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_location",
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": '{"location": "Whole Foods"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_location",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Whole Foods Market', 'full_address': "
                    "'Whole Foods Market, 44-459 Town Center Way, Palm Desert, CA 92260', "
                    "'latitude': 33.7253682, 'longitude': -116.3998028}, "
                    "{'name': 'Whole Foods Market', 'full_address': "
                    "'Whole Foods Market, 150 E McKinley Ave, Sunnyvale, CA 94086', "
                    "'latitude': 37.3738083, 'longitude': -122.0314225}]"
                ),
            },
            {
                "role": "assistant",
                "content": "Which Whole Foods location should I use?",
            },
            {"role": "user", "content": "It should be the one on McKinley Ave."},
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": _relative_timestamp_for_day_time(
            current_timestamp, 1, 17, 0
        ),
        "latitude": 37.3738083,
        "longitude": -122.0314225,
    }


def test_reminder_location_bridge_gets_current_timestamp_for_relative_time(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]

    response = _reminder_creation_location_bridge_completion(
        [
            {
                "role": "user",
                "content": (
                    "Remind me to buy chocolate milk tomorrow 5PM at "
                    "Whole Foods on Stevens Creek."
                ),
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "get_current_timestamp"
    assert json.loads(call.function.arguments) == {}


def test_reminder_location_bridge_adds_relative_time_with_coordinates(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "add_reminder"}},
        {"type": "function", "function": {"name": "search_location_around_lat_lon"}},
    ]
    current_timestamp = 1780211998.219797
    messages = [
        {
            "role": "user",
            "content": (
                "Remind me to buy chocolate milk tomorrow 5PM at "
                "Whole Foods on Stevens Creek."
            ),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_now",
                    "function": {
                        "name": "get_current_timestamp",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_now",
            "name": "get_current_timestamp",
            "content": str(current_timestamp),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_location",
                    "function": {
                        "name": "search_location_around_lat_lon",
                        "arguments": ('{"location": "Whole Foods on Stevens Creek"}'),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_location",
            "name": "search_location_around_lat_lon",
            "content": (
                "[{'name': 'Whole Foods Market', 'latitude': 37.3235879, "
                "'longitude': -122.0396177}]"
            ),
        },
    ]

    response = _reminder_creation_location_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "add_reminder"
    assert json.loads(call.function.arguments) == {
        "content": "Buy chocolate milk",
        "reminder_timestamp": _relative_timestamp_for_day_time(
            current_timestamp, 1, 17, 0
        ),
        "latitude": 37.3235879,
        "longitude": -122.0396177,
    }


def test_completed_device_setting_retention_ignores_original_message_task() -> None:
    response = _completed_device_setting_retention_response_text(
        [
            {"role": "user", "content": "Send a message to Bart, but cellular is off."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_set",
                        "function": {
                            "name": "set_cellular_service_status",
                            "arguments": '{"on": true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_set",
                "name": "set_cellular_service_status",
                "content": "None",
            },
            {"role": "assistant", "content": "Cellular service has been turned on."},
            {"role": "user", "content": "Can you turn it back off?"},
        ]
    )

    assert response is None


def test_answer_retention_recaps_after_vague_help_followup() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's the todo item I made yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Buy tickets for Merrily next week'}]",
            },
            {
                "role": "assistant",
                "content": 'The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {"role": "user", "content": "Great! Can you help me with that?"},
        ]
    )

    assert (
        response
        == 'Understood. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )


def test_answer_retention_recaps_after_get_tickets_followup() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's the todo item I made yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Buy tickets for Merrily next week'}]",
            },
            {
                "role": "assistant",
                "content": 'The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {
                "role": "assistant",
                "content": 'Understood. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {"role": "user", "content": "I just need to get the tickets for that."},
        ]
    )

    assert (
        response
        == 'Understood. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )


def test_answer_retention_handles_ack_that_quotes_look_for_reminder() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's on my reminder yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Look for Company SF tickets'}]",
            },
            {
                "role": "assistant",
                "content": 'The reminder is "Look for Company SF tickets".',
            },
            {"role": "user", "content": 'Yep, "Look for Company SF tickets."'},
        ]
    )

    assert (
        response
        == 'You\'re welcome. To recap: The reminder is "Look for Company SF tickets".'
    )


def test_answer_retention_handles_already_have_that_noted() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's on my reminder yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Look for Company SF tickets'}]",
            },
            {
                "role": "assistant",
                "content": 'The reminder is "Look for Company SF tickets".',
            },
            {"role": "user", "content": "I already have that noted!"},
        ]
    )

    assert (
        response
        == 'You\'re welcome. To recap: The reminder is "Look for Company SF tickets".'
    )


def test_answer_retention_handles_no_repeat_and_cannot_share_more() -> None:
    response = _answer_retention_response_text(
        [
            {
                "role": "user",
                "content": "Which phone number asked me if I want some GPUs?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_messages", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_messages",
                "content": "[{'sender_phone_number': '+18307976530', 'content': 'Hey kid, you want some GPU?'}]",
            },
            {
                "role": "assistant",
                "content": "The phone number that asked you if I want some GPUs is +18307976530.",
            },
            {
                "role": "user",
                "content": "I already know the number. No need to repeat it.",
            },
            {
                "role": "assistant",
                "content": "The phone number that asked you if I want some GPUs is +18307976530.",
            },
            {"role": "user", "content": "I really can’t share anything more."},
        ]
    )

    assert (
        response
        == "Understood. To recap: The phone number that asked you if I want some GPUs is +18307976530."
    )


def test_answer_retention_blocks_phone_answer_contact_and_message_drift() -> None:
    response = _answer_retention_response_text(
        [
            {
                "role": "user",
                "content": "Which phone number asked me if I want some GPUs?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_messages", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_messages",
                "content": "[{'sender_phone_number': '+18307976530', 'content': 'Hey kid, you want some GPU?'}]",
            },
            {
                "role": "assistant",
                "content": "The phone number that asked you if I want some GPUs is +18307976530.",
            },
            {"role": "user", "content": "Maybe check if your cellular service is on?"},
        ]
    )

    assert (
        response
        == "Understood. To recap: The phone number that asked you if I want some GPUs is +18307976530."
    )

    contact_response = _answer_retention_response_text(
        [
            {
                "role": "user",
                "content": "Which phone number asked me if I want some GPUs?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_messages", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_messages",
                "content": "[{'sender_phone_number': '+18307976530', 'content': 'Hey kid, you want some GPU?'}]",
            },
            {
                "role": "assistant",
                "content": "The phone number that asked you if I want some GPUs is +18307976530.",
            },
            {"role": "user", "content": "I still need you to find the contact."},
        ]
    )

    assert (
        contact_response
        == "Understood. To recap: The phone number that asked you if I want some GPUs is +18307976530."
    )


def test_answer_retention_handles_good_to_go_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {
                "role": "user",
                "content": "I don't have cellphone signal. Can you get it on?",
            },
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
            {"role": "tool", "name": "set_cellular_service_status", "content": "None"},
            {"role": "assistant", "content": "Cellular service has been turned on."},
            {"role": "user", "content": "Awesome! Now we should be good to go."},
        ]
    )

    assert response == "You're welcome. To recap: Cellular service has been turned on."


def test_answer_retention_handles_need_to_remember_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's the todo item I made yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Buy tickets for Merrily next week'}]",
            },
            {
                "role": "assistant",
                "content": 'The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {"role": "user", "content": "Yeah, that's what I need to remember."},
        ]
    )

    assert (
        response
        == 'Understood. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )


def test_answer_completion_ends_after_understood_followup_to_recapped_answer(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _answer_completion_bridge_completion(
        [
            {"role": "user", "content": "What's on my reminder yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Look for Company SF tickets'}]",
            },
            {
                "role": "assistant",
                "content": 'The reminder is "Look for Company SF tickets".',
            },
            {"role": "user", "content": "Got it!"},
            {
                "role": "assistant",
                "content": 'You\'re welcome. To recap: The reminder is "Look for Company SF tickets".',
            },
            {"role": "user", "content": "Understood!"},
        ],
        [{"type": "function", "function": {"name": "end_conversation"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert _first_tool_call(response).function.name == "end_conversation"


def test_answer_completion_ends_on_first_clear_closing_acknowledgement(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _answer_completion_bridge_completion(
        [
            {"role": "user", "content": "What's the phone number of Apple Park?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_location_around_lat_lon",
                            "arguments": '{"location":"Apple Park"}',
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": "[{'name': 'Apple Park', 'phone_number': '+14089961010'}]",
            },
            {
                "role": "assistant",
                "content": "The phone number for Apple Park is +1 408-996-1010.",
            },
            {"role": "user", "content": "I don't need anything else right now."},
        ],
        [{"type": "function", "function": {"name": "end_conversation"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert _first_tool_call(response).function.name == "end_conversation"


def test_stock_lookup_bridge_requires_search_before_symbol_answer(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _stock_lookup_bridge_completion(
        [{"role": "user", "content": "What's the stock symbol for Apple"}],
        [{"type": "function", "function": {"name": "search_stock"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_stock"
    assert json.loads(call.function.arguments) == {"query": "Apple"}


def test_location_phone_bridge_copies_phone_number_exactly(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _location_phone_answer_bridge_completion(
        [
            {"role": "user", "content": "What's the phone number of Apple Park"},
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Apple Park', 'phone_number': '+14089961010'}, "
                    "{'name': 'Apple Park Visitor Center', 'phone_number': '+14089611560'}]"
                ),
            },
        ],
        [{"type": "function", "function": {"name": "search_location_around_lat_lon"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "The phone number for Apple Park is +14089961010."
    )


def test_location_phone_bridge_repeats_exact_number_on_followup(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _location_phone_answer_bridge_completion(
        [
            {"role": "user", "content": "What's the phone number of Apple Park"},
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": "[{'name': 'Apple Park', 'phone_number': '+14089961010'}]",
            },
            {
                "role": "assistant",
                "content": "The phone number for Apple Park is +1 408-996-1010.",
            },
            {"role": "user", "content": "I still need that number."},
        ],
        [{"type": "function", "function": {"name": "search_location_around_lat_lon"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "The phone number for Apple Park is +14089961010."
    )


def test_stock_lookup_bridge_answers_from_search_payload(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _stock_lookup_bridge_completion(
        [
            {"role": "user", "content": "Find the code for Apple stock."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_stock",
                            "arguments": '{"query":"Apple"}',
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "search_stock",
                "content": "{'name': 'Apple Inc', 'symbol': 'AAPL', 'price': 280.92}",
            },
        ],
        [{"type": "function", "function": {"name": "search_stock"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "The stock symbol for Apple is AAPL."


def test_stock_lookup_bridge_ignores_followup_instruction_as_company(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _stock_lookup_bridge_completion(
        [
            {"role": "user", "content": "What's the stock symbol for Apple?"},
            {"role": "assistant", "content": "Wifi is not enabled."},
            {"role": "user", "content": "Now try searching for the stock symbol."},
            {
                "role": "tool",
                "name": "search_stock",
                "content": "{'name': 'Apple Inc', 'symbol': 'AAPL', 'price': 280.92}",
            },
        ],
        [{"type": "function", "function": {"name": "search_stock"}}],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.content == "The stock symbol for Apple is AAPL."


def test_weather_location_bridge_abstains_for_current_temperature_without_location(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {"role": "user", "content": "What's the temperature here right now"},
            {
                "role": "assistant",
                "content": "Could you provide your current location?",
            },
            {"role": "user", "content": "I don't know my exact location."},
            {
                "role": "user",
                "content": "Can you try looking it up using any available settings?",
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.tool_calls is None
    assert "current location is unavailable" in response.choices[0].message.content


def test_weather_location_bridge_rejects_vague_city_instruction_queries(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    followups = [
        "Maybe turn on your location services or search for the weather in a nearby city.",
        "Maybe you could look up the weather in your specific city instead?",
        "Try turning on location services or search for a specific city to find the temperature.",
    ]
    for followup in followups:
        response = _weather_location_bridge_completion(
            [
                {"role": "user", "content": "What's the temperature here right now"},
                {
                    "role": "assistant",
                    "content": (
                        "I do not have enough information to retrieve the current "
                        "temperature because current location is unavailable."
                    ),
                },
                {"role": "user", "content": followup},
            ],
            [
                {
                    "type": "function",
                    "function": {"name": "search_location_around_lat_lon"},
                },
                {
                    "type": "function",
                    "function": {"name": "search_weather_around_lat_lon"},
                },
            ],
            model_name="gpt-4o-mini",
        )

        assert response is not None
        assert response.choices[0].message.tool_calls is None
        assert "current location is unavailable" in response.choices[0].message.content


def test_weather_location_bridge_rejects_vague_your_area_location_query(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {"role": "user", "content": "What's the temperature here right now"},
            {
                "role": "assistant",
                "content": (
                    "I do not have enough information to retrieve the current "
                    "temperature because current location is unavailable."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Maybe check your device's weather app or Google search for "
                    "the temperature in your area."
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert response.choices[0].message.tool_calls is None
    assert "current location is unavailable" in response.choices[0].message.content


def test_weather_location_bridge_resolves_named_place_before_weather(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            }
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_location_around_lat_lon"
    assert json.loads(call.function.arguments) == {"location": "Grand Canyon"}


def test_weather_location_bridge_uses_resolved_coordinates(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            },
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Grand Canyon National Park', "
                    "'latitude': 36.2678855, 'longitude': -112.3535253}]"
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "search_weather_around_lat_lon"
    assert json.loads(call.function.arguments) == {
        "latitude": 36.2678855,
        "longitude": -112.3535253,
    }


def test_weather_location_bridge_converts_celsius_payload(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            },
            {
                "role": "tool",
                "name": "search_weather_around_lat_lon",
                "content": (
                    "{'name': 'Grand Canyon National Park', 'region': 'Arizona', "
                    "'current_temperature': 15.1, 'temperature_unit': 'Celsius'}"
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "unit_conversion"
    assert json.loads(call.function.arguments) == {
        "amount": 15.1,
        "from_unit": "celsius",
        "to_unit": "fahrenheit",
    }


def test_weather_location_bridge_accepts_payload_after_resolved_place_alias(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            },
            {
                "role": "tool",
                "name": "search_location_around_lat_lon",
                "content": (
                    "[{'name': 'Grand Canyon National Park', "
                    "'latitude': 36.2678855, 'longitude': -112.3535253}]"
                ),
            },
            {
                "role": "tool",
                "name": "search_weather_around_lat_lon",
                "content": (
                    "{'name': 'North Rim', 'region': 'Arizona', "
                    "'current_temperature': 12.3, 'temperature_unit': 'Celsius'}"
                ),
            },
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    call = _first_tool_call(response)
    assert call.function.name == "unit_conversion"
    assert json.loads(call.function.arguments) == {
        "amount": 12.3,
        "from_unit": "celsius",
        "to_unit": "fahrenheit",
    }


def test_weather_location_bridge_answers_after_unit_conversion(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            },
            {"role": "tool", "name": "unit_conversion", "content": "59.18"},
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "The current temperature in Grand Canyon is approximately 59.2°F."
    )


def test_weather_location_bridge_keeps_original_place_on_unit_followup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    response = _weather_location_bridge_completion(
        [
            {
                "role": "user",
                "content": "What's the temperature in Grand Canyon in Fahrenheit",
            },
            {"role": "assistant", "content": "12.3 Celsius"},
            {
                "role": "user",
                "content": "I need the temperature in Fahrenheit, not Celsius.",
            },
            {"role": "tool", "name": "unit_conversion", "content": "54.14"},
        ],
        [
            {
                "type": "function",
                "function": {"name": "search_location_around_lat_lon"},
            },
            {"type": "function", "function": {"name": "search_weather_around_lat_lon"}},
            {"type": "function", "function": {"name": "unit_conversion"}},
        ],
        model_name="gpt-4o-mini",
    )

    assert response is not None
    assert (
        response.choices[0].message.content
        == "The current temperature in Grand Canyon is approximately 54.1°F."
    )


def test_answer_retention_handles_check_that_for_me_followup() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's on my reminder yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Look for Company SF tickets'}]",
            },
            {
                "role": "assistant",
                "content": 'The reminder is "Look for Company SF tickets".',
            },
            {"role": "user", "content": "Can you check that for me?"},
        ]
    )

    assert (
        response
        == 'Understood. To recap: The reminder is "Look for Company SF tickets".'
    )


def test_answer_retention_handles_nice_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "How many days is it till Christmas Day"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "timestamp_diff", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "name": "timestamp_diff", "content": "{'days': 207}"},
            {"role": "assistant", "content": "It is 207 days till Christmas Day."},
            {"role": "user", "content": "Nice!"},
        ]
    )

    assert response == "You're welcome. To recap: It is 207 days till Christmas Day."


def test_setting_lookup_does_not_drift_into_unavailable_message_history() -> None:
    response = _setting_lookup_unavailable_message_history_response_text(
        [
            {"role": "user", "content": "Is my cellular service on?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_cellular_service_status",
                            "arguments": "{}",
                        }
                    }
                ],
            },
            {"role": "tool", "name": "get_cellular_service_status", "content": "True"},
            {"role": "assistant", "content": "Cellular service is on."},
            {"role": "user", "content": "Can you help check the message history?"},
        ],
        [{"type": "function", "function": {"name": "get_current_location"}}],
    )

    assert (
        response
        == "I cannot check message history with the available tools. To recap: Cellular service is on."
    )


def test_answer_retention_handles_thanks_for_finding_acknowledgement() -> None:
    response = _answer_retention_response_text(
        [
            {"role": "user", "content": "What's the todo item I made yesterday?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "search_reminder", "arguments": "{}"}}
                ],
            },
            {
                "role": "tool",
                "name": "search_reminder",
                "content": "[{'content': 'Buy tickets for Merrily next week'}]",
            },
            {
                "role": "assistant",
                "content": 'The todo item you made yesterday is "Buy tickets for Merrily next week".',
            },
            {"role": "user", "content": "Nice, thanks for finding that!"},
        ]
    )

    assert (
        response
        == 'You\'re welcome. To recap: The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )


def test_created_yesterday_answer_uses_relative_day_target() -> None:
    now = 1780187304.322408
    response = _reminder_created_yesterday_answer(
        [
            {"role": "tool", "name": "get_current_timestamp", "content": str(now)},
            {
                "role": "tool",
                "name": "search_reminder",
                "content": repr(
                    [
                        {
                            "content": "Buy tickets for Merrily next week",
                            "creation_timestamp": now - 86400.0,
                        },
                        {
                            "content": "Buy a nice rich navy bathing dress",
                            "creation_timestamp": now - 3600.0,
                        },
                    ]
                ),
            },
        ]
    )

    assert (
        response
        == 'The todo item you made yesterday is "Buy tickets for Merrily next week".'
    )
