import json
from typing import Any

import pytest

from sage_ts.adapters.openai_toolsandbox_roles import (
    ANSWER_RETENTION_ACTOR_POLICY_SENTINEL,
    LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL,
    RELATIVE_TIME_ACTOR_POLICY_SENTINEL,
    SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL,
    SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL,
    STATE_ACTION_ACTOR_POLICY_SENTINEL,
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
    _answer_completion_bridge_completion,
    _answer_retention_actor_policy_message,
    _answer_retention_response_text,
    _contact_lookup_bridge_completion,
    _contact_relationship_batch_bridge_completion,
    _contact_remove_by_phone_insufficient_response_text,
    _contact_update_by_id_bridge_completion,
    _contact_update_phone_bridge_completion,
    _crud_success_response_text,
    _lookup_planner_actor_policy_message,
    _relative_time_actor_policy_message,
    _reminder_recency_bridge_completion,
    _safe_action_or_abstain_bridge_completion,
    _safe_argument_actor_policy_message,
    _scheduling_timestamp_actor_policy_message,
    _state_action_actor_policy_message,
    _state_action_planner_bridge_completion,
    _state_action_sequence_bridge_completion,
)
from sage_ts.adapters.role_factory import make_agent, make_user
from tool_sandbox.roles.unhelpful_agent import UnhelpfulAgent


def _first_tool_call(completion: Any) -> Any:
    tool_calls = completion.choices[0].message.tool_calls
    assert tool_calls is not None
    assert tool_calls
    return tool_calls[0]


def test_role_factory_preserves_upstream_agent() -> None:
    assert isinstance(make_agent("Unhelpful"), UnhelpfulAgent)


def test_role_factory_supports_current_openai_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    agent = make_agent("gpt-4o-mini")
    user = make_user("gpt-4o-mini")

    assert isinstance(agent, ConfigurableOpenAIAgent)
    assert isinstance(user, ConfigurableOpenAIUser)
    assert agent.model_name == "gpt-4o-mini"
    assert user.model_name == "gpt-4o-mini"


def test_role_factory_keeps_gpt_5_mini_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    agent = make_agent("gpt-5-mini")

    assert isinstance(agent, ConfigurableOpenAIAgent)
    assert agent.model_name == "gpt-5-mini"


def test_lookup_planner_actor_policy_shows_before_search() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_contact_lookup_query",
                "description": (
                    "Prepare search_contacts_kwargs for a contact lookup query "
                    "planner before the original search."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_name": {"type": "string"},
                        "relationship": {"type": "string"},
                        "requested_field": {"type": "string"},
                    },
                },
            },
        }
    ]

    policy = _lookup_planner_actor_policy_message(
        [{"role": "user", "content": "What is the name of my boss?"}],
        tools,
    )

    assert policy is not None
    assert LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "call the original ToolSandbox search tool next" in policy["content"]


def test_lookup_planner_actor_policy_waits_when_records_are_visible() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_contact_lookup_query",
                "description": "lookup query planner with search_contacts_kwargs",
                "parameters": {"type": "object", "properties": {"relationship": {}}},
            },
        }
    ]
    messages = [
        {"role": "user", "content": "What is the name of my boss?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': '1', 'name': 'Homer S', 'relationship': 'boss'}]",
        },
    ]

    assert _lookup_planner_actor_policy_message(messages, tools) is None


def test_answer_retention_policy_recaps_after_tool_backed_ack() -> None:
    messages = [
        {"role": "user", "content": "What is Homer S's phone number?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'phone_number': '+10000000000'}]",
        },
        {"role": "assistant", "content": "Homer S's phone number is +10000000000."},
        {"role": "user", "content": "Thanks, you found it."},
    ]

    policy = _answer_retention_actor_policy_message(messages)

    assert policy is not None
    assert ANSWER_RETENTION_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "must include the retrieved value again" in policy["content"]
    assert "generic acknowledgement" in policy["content"]


def test_answer_retention_policy_does_not_interrupt_followup_request() -> None:
    messages = [
        {"role": "user", "content": "What is Homer S's phone number?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'phone_number': '+10000000000'}]",
        },
        {"role": "assistant", "content": "Homer S's phone number is +10000000000."},
        {"role": "user", "content": "Can you modify that contact now?"},
    ]

    assert _answer_retention_actor_policy_message(messages) is None


def test_answer_retention_does_not_treat_look_as_ok() -> None:
    messages = [
        {"role": "user", "content": "What reminders did I have yesterday?"},
        {"role": "tool", "name": "search_reminder", "content": "[]"},
        {"role": "assistant", "content": "No matching reminders were found."},
        {
            "role": "user",
            "content": "I see. You can look for anything in the past week then.",
        },
    ]

    assert _answer_retention_actor_policy_message(messages) is None


def test_answer_retention_response_recaps_without_tool_call() -> None:
    messages = [
        {"role": "user", "content": "What's my relationship with +10000000000?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'relationship': 'boss'}]",
        },
        {
            "role": "assistant",
            "content": "Your relationship with +10000000000 is boss.",
        },
        {"role": "user", "content": "Thanks"},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Your relationship with +10000000000 is boss."
    )


def test_answer_retention_uses_immediate_tool_backed_answer() -> None:
    messages = [
        {"role": "user", "content": "What is Homer S's phone number?"},
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'name': 'Homer S', 'phone_number': '+10000000000'}]",
        },
        {"role": "assistant", "content": "Homer S's phone number is +10000000000."},
        {
            "role": "user",
            "content": "I can't seem to find any other information about Homer S.",
        },
        {
            "role": "assistant",
            "content": "I do not have more details unless you ask for a specific field.",
        },
        {"role": "user", "content": "Got it, thanks!"},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Homer S's phone number is +10000000000."
    )


def test_answer_retention_recaps_successful_setter_result() -> None:
    messages = [
        {"role": "user", "content": "Turn on cellular service."},
        {"role": "tool", "name": "set_low_battery_mode_status", "content": "None"},
        {"role": "tool", "name": "set_cellular_service_status", "content": "None"},
        {
            "role": "assistant",
            "content": "Low battery mode is off and cellular service is now on.",
        },
        {"role": "user", "content": "Awesome, thanks!"},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Low battery mode is off and cellular service is now on."
    )


def test_answer_retention_recaps_setting_status_after_checking_ack() -> None:
    messages = [
        {"role": "user", "content": "Is wifi on?"},
        {
            "role": "tool",
            "name": "get_wifi_status",
            "content": "True",
        },
        {"role": "assistant", "content": "Your Wi-Fi is still on."},
        {"role": "user", "content": "Thanks for checking! That's good to know."},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Your Wi-Fi is still on."
    )


def test_answer_retention_recaps_after_appreciation_ack() -> None:
    messages = [
        {"role": "user", "content": "Is wifi on?"},
        {
            "role": "tool",
            "name": "get_wifi_status",
            "content": "True",
        },
        {"role": "assistant", "content": "Your Wi-Fi is still on."},
        {"role": "user", "content": "I appreciate the confirmation!"},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Your Wi-Fi is still on."
    )


def test_answer_completion_bridge_ends_after_recap_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {"name": "end_conversation", "parameters": {"type": "object"}},
        }
    ]
    messages = [
        {"role": "user", "content": "Is wifi on?"},
        {"role": "tool", "name": "get_wifi_status", "content": "True"},
        {"role": "assistant", "content": "Your Wi-Fi is still on."},
        {"role": "user", "content": "Thanks!"},
        {
            "role": "assistant",
            "content": "You're welcome. To recap: Your Wi-Fi is still on.",
        },
        {"role": "user", "content": "Got it!"},
    ]

    completion = _answer_completion_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    assert _first_tool_call(completion).function.name == "end_conversation"


def test_answer_completion_bridge_waits_until_value_was_recapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {"name": "end_conversation", "parameters": {"type": "object"}},
        }
    ]
    messages = [
        {"role": "user", "content": "Is wifi on?"},
        {"role": "tool", "name": "get_wifi_status", "content": "True"},
        {"role": "assistant", "content": "Your Wi-Fi is still on."},
        {"role": "user", "content": "Thanks!"},
    ]

    assert (
        _answer_completion_bridge_completion(
            messages,
            tools,
            model_name="gpt-4o-mini",
        )
        is None
    )


def test_relative_time_actor_policy_shows_for_timestamp_helper() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "relative_day_time_to_timestamp",
                "description": "Convert a relative local day and time into a timestamp.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_timestamp": {"type": "number"},
                        "day_offset": {"type": "integer"},
                        "hour": {"type": "integer"},
                        "minute": {"type": "integer"},
                        "local_utc_offset_hours": {"type": "number"},
                    },
                },
            },
        }
    ]

    policy = _relative_time_actor_policy_message(
        [{"role": "user", "content": "Push my reminder to tomorrow at 5 PM."}],
        tools,
    )

    assert policy is not None
    assert RELATIVE_TIME_ACTOR_POLICY_SENTINEL in policy["content"]
    assert (
        "does not replace the original reminder side-effect tool" in policy["content"]
    )


def test_state_action_policy_shows_for_device_state_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": (
                    "Plan the exact original ToolSandbox device-state setter "
                    "sequence for wifi, cellular, location, or low-battery blockers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        }
    ]

    policy = _state_action_actor_policy_message(
        [{"role": "user", "content": "Turn on wifi while low battery mode is on."}],
        tools,
    )

    assert policy is not None
    assert STATE_ACTION_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "Prefer plan_device_state_action_sequence_v3" in policy["content"]
    assert "setter calls from action_sequence in order" in policy["content"]


def test_state_action_planner_bridge_calls_planner_for_explicit_low_battery_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": (
                    "Plan the exact original ToolSandbox device-state setter "
                    "sequence for wifi, cellular, location, or low-battery blockers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        }
    ]

    completion = _state_action_planner_bridge_completion(
        [{"role": "user", "content": "Turn on wifi while low battery mode is on."}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "plan_device_state_action_sequence_v3"
    assert "Turn on wifi" in call.function.arguments


def test_state_action_planner_bridge_calls_planner_after_blocked_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": (
                    "Plan the exact original ToolSandbox device-state setter "
                    "sequence for wifi, cellular, location, or low-battery blockers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        }
    ]

    completion = _state_action_planner_bridge_completion(
        [
            {"role": "user", "content": "Please send Taylor the address."},
            {
                "role": "tool",
                "name": "send_message_with_phone_number",
                "content": "ValueError: Cellular service is not enabled.",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "plan_device_state_action_sequence_v3"
    assert "Cellular service is not enabled" in call.function.arguments


def test_state_action_planner_bridge_ignores_plain_direct_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": (
                    "Plan the exact original ToolSandbox device-state setter "
                    "sequence for wifi, cellular, location, or low-battery blockers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        }
    ]

    assert (
        _state_action_planner_bridge_completion(
            [{"role": "user", "content": "Turn off cellular service."}],
            tools,
            model_name="gpt-4o-mini",
        )
        is None
    )


def test_state_action_planner_bridge_ignores_status_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": (
                    "Plan the exact original ToolSandbox device-state setter "
                    "sequence for wifi, cellular, location, or low-battery blockers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        }
    ]

    assert (
        _state_action_planner_bridge_completion(
            [{"role": "user", "content": "Can you check whether wifi is on?"}],
            tools,
            model_name="gpt-4o-mini",
        )
        is None
    )


def test_scheduling_timestamp_policy_shows_for_week_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "relative_weeks_time_to_timestamp",
                "description": "Convert week scheduling into a reminder_timestamp.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_timestamp": {"type": "number"},
                        "weeks_from_now": {"type": "integer"},
                        "hour": {"type": "integer"},
                        "minute": {"type": "integer"},
                        "local_utc_offset_hours": {"type": "number"},
                    },
                },
            },
        }
    ]

    policy = _scheduling_timestamp_actor_policy_message(
        [{"role": "user", "content": "Add a reminder for next week at 5 PM."}],
        tools,
    )

    assert policy is not None
    assert SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "whole-week helper" in policy["content"]


def test_state_action_bridge_calls_next_setter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_device_state_action_sequence_v3",
                "description": "Plan a state action sequence for device settings.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "visible_state_or_error": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {"name": "set_low_battery_mode_status"},
        },
    ]
    messages = [
        {
            "role": "tool",
            "name": "plan_device_state_action_sequence_v3",
            "content": (
                "{'should_call': True, 'action_sequence': "
                "[{'tool_name': 'set_low_battery_mode_status', "
                "'arguments': {'on': False}}]}"
            ),
        }
    ]

    completion = _state_action_sequence_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "set_low_battery_mode_status"
    assert '"on": false' in call.function.arguments


def test_contact_lookup_bridge_calls_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "plan_contact_lookup_query"}},
        {"type": "function", "function": {"name": "search_contacts"}},
    ]

    completion = _contact_lookup_bridge_completion(
        [{"role": "user", "content": "What is the name of my boss?"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "plan_contact_lookup_query"
    assert '"relationship": "boss"' in call.function.arguments


def test_contact_lookup_bridge_calls_search_after_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "plan_contact_lookup_query"}},
        {"type": "function", "function": {"name": "search_contacts"}},
    ]
    messages = [
        {"role": "user", "content": "What is the name of my boss?"},
        {
            "role": "tool",
            "name": "plan_contact_lookup_query",
            "content": (
                "{'should_call_search_contacts': True, "
                "'search_contacts_kwargs': {'relationship': 'boss'}}"
            ),
        },
    ]

    completion = _contact_lookup_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "search_contacts"
    assert '"relationship": "boss"' in call.function.arguments


def test_contact_update_bridge_preserves_required_modify_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [{"type": "function", "function": {"name": "modify_contact"}}]
    messages = [
        {
            "role": "user",
            "content": (
                "Update the phone number of the last person I sent a message to "
                "to +10293847563"
            ),
        },
        {
            "role": "tool",
            "name": "select_message_counterparty_for_contact_update",
            "content": (
                "{'selected_person_id': 'person-1', 'abstain_reason': '', "
                "'downstream_tool_name': 'modify_contact'}"
            ),
        },
    ]

    completion = _contact_update_phone_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "modify_contact"
    assert '"person_id": "person-1"' in call.function.arguments
    assert '"phone_number": "+10293847563"' in call.function.arguments


def test_contact_update_bridge_calls_counterparty_selector_with_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {"name": "select_message_counterparty_for_contact_update"},
        },
        {"type": "function", "function": {"name": "modify_contact"}},
    ]
    messages = [
        {
            "role": "user",
            "content": (
                "Update the phone number of the last person I sent a message to "
                "to +10293847563"
            ),
        },
        {
            "role": "tool",
            "name": "search_messages",
            "content": (
                "[{'message_id': 'old', 'sender_person_id': 'self-id', "
                "'recipient_person_id': 'old-person', 'creation_timestamp': 10.0}, "
                "{'message_id': 'new', 'sender_person_id': 'self-id', "
                "'recipient_person_id': 'new-person', 'creation_timestamp': 30.0}]"
            ),
        },
    ]

    completion = _contact_update_phone_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "select_message_counterparty_for_contact_update"
    assert '"selection_mode": "latest"' in call.function.arguments
    assert '"phone_number": "+10293847563"' in call.function.arguments
    assert '"self_person_id": "self-id"' in call.function.arguments


def test_contact_relationship_bridge_uses_generated_batch_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_contact_relationship_batch_update"},
        },
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]

    completion = _contact_relationship_batch_bridge_completion(
        [{"role": "user", "content": "Make all my friends enemies"}],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "plan_contact_relationship_batch_update"
    assert '"source_relationship": "friend"' in call.function.arguments
    assert '"target_relationship": "enemy"' in call.function.arguments

    variant_completion = _contact_relationship_batch_bridge_completion(
        [{"role": "user", "content": "Make all of my friends my enemy"}],
        tools,
        model_name="gpt-4o-mini",
    )
    assert variant_completion is not None
    variant_call = _first_tool_call(variant_completion)
    assert variant_call.function.name == "plan_contact_relationship_batch_update"
    assert '"source_relationship": "friend"' in variant_call.function.arguments
    assert '"target_relationship": "enemy"' in variant_call.function.arguments

    updated_variant_completion = _contact_relationship_batch_bridge_completion(
        [
            {
                "role": "user",
                "content": (
                    "Who are my friends? I just want all my friends in the "
                    "contact book updated as enemies."
                ),
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert updated_variant_completion is not None
    updated_variant_call = _first_tool_call(updated_variant_completion)
    assert (
        updated_variant_call.function.name == "plan_contact_relationship_batch_update"
    )
    assert '"source_relationship": "friend"' in updated_variant_call.function.arguments
    assert '"target_relationship": "enemy"' in updated_variant_call.function.arguments


def test_contact_relationship_bridge_continues_with_search_and_modify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {
            "type": "function",
            "function": {"name": "plan_contact_relationship_batch_update"},
        },
        {"type": "function", "function": {"name": "search_contacts"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]

    search_completion = _contact_relationship_batch_bridge_completion(
        [
            {"role": "user", "content": "Make all my friends enemies"},
            {
                "role": "tool",
                "name": "plan_contact_relationship_batch_update",
                "content": (
                    "{'should_call_search_contacts': True, "
                    "'search_contacts_kwargs': {'relationship': 'friend'}, "
                    "'abstain_reason': ''}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert search_completion is not None
    search_call = _first_tool_call(search_completion)
    assert search_call.function.name == "search_contacts"
    assert '"relationship": "friend"' in search_call.function.arguments

    modify_completion = _contact_relationship_batch_bridge_completion(
        [
            {"role": "user", "content": "Make all my friends enemies"},
            {
                "role": "tool",
                "name": "plan_contact_relationship_batch_update",
                "content": (
                    "{'phase': 'modify_required', 'should_call_tools': True, "
                    "'downstream_tool_kwargs_list': ["
                    "{'person_id': 'p1', 'relationship': 'enemy'}], "
                    "'abstain_reason': ''}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert modify_completion is not None
    modify_call = _first_tool_call(modify_completion)
    assert modify_call.function.name == "modify_contact"
    assert '"person_id": "p1"' in modify_call.function.arguments
    assert '"relationship": "enemy"' in modify_call.function.arguments


def test_contact_update_by_id_bridge_uses_generated_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "plan_contact_update_from_id"}},
        {"type": "function", "function": {"name": "modify_contact"}},
    ]
    person_id = "11111111-1111-1111-1111-111111111111"

    completion = _contact_update_by_id_bridge_completion(
        [
            {
                "role": "user",
                "content": f"Update contact {person_id}'s phone to +1 (555) 0100",
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "plan_contact_update_from_id"
    assert f'"person_id": "{person_id}"' in call.function.arguments
    assert '"phone_number": "+15550100"' in call.function.arguments

    modify_completion = _contact_update_by_id_bridge_completion(
        [
            {
                "role": "user",
                "content": f"Update contact {person_id}'s phone to +1 (555) 0100",
            },
            {
                "role": "tool",
                "name": "plan_contact_update_from_id",
                "content": (
                    "{'should_call_tool': True, "
                    "'downstream_tool_kwargs': {"
                    f"'person_id': '{person_id}', "
                    "'phone_number': '+15550100'}}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert modify_completion is not None
    modify_call = _first_tool_call(modify_completion)
    assert modify_call.function.name == "modify_contact"
    assert f'"person_id": "{person_id}"' in modify_call.function.arguments
    assert '"phone_number": "+15550100"' in modify_call.function.arguments


def test_safe_action_abstain_bridge_uses_generated_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "prepare_safe_action_or_abstain"}},
        {"type": "function", "function": {"name": "remove_contact"}},
    ]

    completion = _safe_action_or_abstain_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remove the contact with phone number +1 (555) 0100",
            }
        ],
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "prepare_safe_action_or_abstain"
    assert '"requested_action": "remove_contact"' in call.function.arguments
    assert '"target_identifier": "+15550100"' in call.function.arguments
    assert '"search_contacts"' in call.function.arguments

    answer_completion = _safe_action_or_abstain_bridge_completion(
        [
            {
                "role": "user",
                "content": "Remove the contact with phone number +1 (555) 0100",
            },
            {
                "role": "tool",
                "name": "prepare_safe_action_or_abstain",
                "content": (
                    "{'should_abstain': True, "
                    "'final_answer_recommendation': 'I do not have enough "
                    "information to remove that contact.', "
                    "'abstain_reason': 'missing_required_original_tool'}"
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert answer_completion is not None
    assert (
        answer_completion.choices[0].message.content
        == "I do not have enough information to remove that contact."
    )


def test_contact_remove_by_phone_without_search_contacts_abstains_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [{"type": "function", "function": {"name": "remove_contact"}}]

    answer = _contact_remove_by_phone_insufficient_response_text(
        [
            {
                "role": "user",
                "content": "Remove phone number +1 (555) 0100 from my contact",
            }
        ],
        tools,
    )

    assert answer is not None
    assert "+15550100" in answer
    assert "name or person_id" in answer
    assert "search contacts" in answer


def test_contact_remove_by_phone_uses_normal_flow_when_search_contacts_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "remove_contact"}},
        {"type": "function", "function": {"name": "search_contacts"}},
    ]

    assert (
        _contact_remove_by_phone_insufficient_response_text(
            [
                {
                    "role": "user",
                    "content": "Remove phone number +1 (555) 0100 from my contact",
                }
            ],
            tools,
        )
        is None
    )


def test_crud_success_retains_reminder_update_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    messages = [
        {"role": "user", "content": "Modify my latest reminder to tomorrow at 5 PM."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_modify",
                    "type": "function",
                    "function": {
                        "name": "modify_reminder",
                        "arguments": '{"reminder_id": "r1", "reminder_timestamp": 1}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_modify",
            "name": "modify_reminder",
            "content": "None",
        },
    ]

    assert (
        _crud_success_response_text(
            messages,
            [
                {
                    "type": "function",
                    "function": {"name": "relative_day_time_to_timestamp"},
                }
            ],
        )
        == "The reminder has been updated."
    )


def test_answer_retention_allows_acknowledgement_with_what_clause() -> None:
    messages = [
        {"role": "user", "content": "What's the todo item I made yesterday?"},
        {
            "role": "tool",
            "name": "search_reminder",
            "content": "[{'content': 'Buy tickets'}]",
        },
        {
            "role": "assistant",
            "content": 'The todo item you made yesterday is "Buy tickets".',
        },
        {"role": "user", "content": "Thanks, that's what I needed!"},
    ]

    assert _answer_retention_response_text(messages) == (
        'You\'re welcome. To recap: The todo item you made yesterday is "Buy tickets".'
    )


def test_reminder_latest_modify_bridge_uses_search_select_timestamp_then_modify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "search_reminder"}},
        {
            "type": "function",
            "function": {"name": "select_record_by_timestamp_extreme"},
        },
        {"type": "function", "function": {"name": "relative_day_time_to_timestamp"}},
        {"type": "function", "function": {"name": "modify_reminder"}},
    ]
    messages = [
        {
            "role": "user",
            "content": "Postpone my most recent reminder to tomorrow 5PM.",
        },
        {"role": "tool", "name": "get_current_timestamp", "content": "1778531841.0"},
    ]

    search_completion = _reminder_recency_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )
    assert search_completion is not None
    search_call = _first_tool_call(search_completion)
    assert search_call.function.name == "search_reminder"
    search_args = json.loads(search_call.function.arguments)
    assert search_args == {"creation_timestamp_upperbound": 1778531841.0}

    records = [
        {"reminder_id": "old", "reminder_timestamp": 1778531000.0},
        {"reminder_id": "latest", "reminder_timestamp": 1778535000.0},
    ]
    select_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "search_reminder", "content": repr(records)},
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert select_completion is not None
    select_call = _first_tool_call(select_completion)
    assert select_call.function.name == "select_record_by_timestamp_extreme"
    select_args = json.loads(select_call.function.arguments)
    assert select_args["timestamp_field"] == "reminder_timestamp"
    assert select_args["mode"] == "latest"

    selected_payload = {
        "selected_record": {
            "reminder_id": "latest",
            "reminder_timestamp": 1778535000.0,
        },
        "abstain_reason": "",
    }
    relative_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "search_reminder", "content": repr(records)},
            {
                "role": "tool",
                "name": "select_record_by_timestamp_extreme",
                "content": repr(selected_payload),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert relative_completion is not None
    relative_call = _first_tool_call(relative_completion)
    assert relative_call.function.name == "relative_day_time_to_timestamp"
    relative_args = json.loads(relative_call.function.arguments)
    assert relative_args["day_offset"] == 1
    assert relative_args["hour"] == 17

    modify_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "search_reminder", "content": repr(records)},
            {
                "role": "tool",
                "name": "select_record_by_timestamp_extreme",
                "content": repr(selected_payload),
            },
            {
                "role": "tool",
                "name": "relative_day_time_to_timestamp",
                "content": "1778619600.0",
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert modify_completion is not None
    modify_call = _first_tool_call(modify_completion)
    assert modify_call.function.name == "modify_reminder"
    modify_args = json.loads(modify_call.function.arguments)
    assert modify_args == {
        "reminder_id": "latest",
        "reminder_timestamp": 1778619600.0,
    }


def test_reminder_recency_bridge_calls_search_after_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "resolve_search_window_or_bounds"}},
        {"type": "function", "function": {"name": "search_reminder"}},
    ]
    messages = [
        {"role": "user", "content": "Which todo was made yesterday?"},
        {
            "role": "tool",
            "name": "resolve_search_window_or_bounds",
            "content": (
                "{'should_call_search': True, 'target_tool_name': 'search_reminder', "
                "'search_kwargs': {'creation_timestamp_lowerbound': 10, "
                "'creation_timestamp_upperbound': 20}}"
            ),
        },
    ]

    completion = _reminder_recency_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )

    assert completion is not None
    call = _first_tool_call(completion)
    assert call.function.name == "search_reminder"
    assert "creation_timestamp_lowerbound" in call.function.arguments


def test_reminder_upcoming_remove_bridge_uses_generated_action_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")
    tools = [
        {"type": "function", "function": {"name": "get_current_timestamp"}},
        {"type": "function", "function": {"name": "search_reminder"}},
        {
            "type": "function",
            "function": {"name": "select_action_target_by_recency"},
        },
        {"type": "function", "function": {"name": "remove_reminder"}},
    ]
    messages = [{"role": "user", "content": "Remove my upcoming reminder."}]

    timestamp_completion = _reminder_recency_bridge_completion(
        messages,
        tools,
        model_name="gpt-4o-mini",
    )
    assert timestamp_completion is not None
    timestamp_call = _first_tool_call(timestamp_completion)
    assert timestamp_call.function.name == "get_current_timestamp"

    search_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "get_current_timestamp", "content": "100.0"},
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert search_completion is not None
    search_call = _first_tool_call(search_completion)
    assert search_call.function.name == "search_reminder"
    assert json.loads(search_call.function.arguments) == {}

    records = [
        {"reminder_id": "later", "reminder_timestamp": 300.0},
        {"reminder_id": "next", "reminder_timestamp": 200.0},
    ]
    select_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "get_current_timestamp", "content": "100.0"},
            {"role": "tool", "name": "search_reminder", "content": repr(records)},
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert select_completion is not None
    select_call = _first_tool_call(select_completion)
    assert select_call.function.name == "select_action_target_by_recency"
    select_args = json.loads(select_call.function.arguments)
    assert select_args["timestamp_key"] == "reminder_timestamp"
    assert select_args["selection_mode"] == "oldest"
    assert select_args["action_type"] == "remove_reminder"
    assert select_args["records"] == records

    remove_completion = _reminder_recency_bridge_completion(
        [
            *messages,
            {"role": "tool", "name": "get_current_timestamp", "content": "100.0"},
            {"role": "tool", "name": "search_reminder", "content": repr(records)},
            {
                "role": "tool",
                "name": "select_action_target_by_recency",
                "content": repr(
                    {
                        "downstream_tool_name": "remove_reminder",
                        "downstream_tool_kwargs": {"reminder_id": "next"},
                        "should_call_tool": True,
                        "abstain_reason": "",
                    }
                ),
            },
        ],
        tools,
        model_name="gpt-4o-mini",
    )
    assert remove_completion is not None
    remove_call = _first_tool_call(remove_completion)
    assert remove_call.function.name == "remove_reminder"
    assert json.loads(remove_call.function.arguments) == {"reminder_id": "next"}


def test_safe_argument_policy_blocks_inferred_self_contact() -> None:
    policy = _safe_argument_actor_policy_message(
        [
            {
                "role": "user",
                "content": (
                    "Add Stephen Sondheim to my contact, his phone_number is "
                    "+19876543210"
                ),
            }
        ],
        [{"type": "function", "function": {"name": "add_contact"}}],
    )

    assert policy is not None
    assert SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "omit is_self" in policy["content"]
