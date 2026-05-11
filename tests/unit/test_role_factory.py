import pytest

from sage_ts.adapters.openai_toolsandbox_roles import (
    ANSWER_RETENTION_ACTOR_POLICY_SENTINEL,
    LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL,
    RELATIVE_TIME_ACTOR_POLICY_SENTINEL,
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
    _answer_retention_actor_policy_message,
    _answer_retention_response_text,
    _lookup_planner_actor_policy_message,
    _relative_time_actor_policy_message,
)
from sage_ts.adapters.role_factory import make_agent, make_user
from tool_sandbox.roles.unhelpful_agent import UnhelpfulAgent


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
