import pytest

from sage_ts.adapters.openai_toolsandbox_roles import (
    ANSWER_RETENTION_ACTOR_POLICY_SENTINEL,
    LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL,
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
    _answer_retention_actor_policy_message,
    _answer_retention_response_text,
    _lookup_planner_actor_policy_message,
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


def test_answer_retention_response_recaps_message_answer_after_ack() -> None:
    messages = [
        {"role": "user", "content": "Find my most recent text."},
        {
            "role": "tool",
            "name": "select_message_content_by_recency",
            "content": "{'exact_final_answer': \"Your most recent message says 'Good, keep me posted'.\"}",
        },
        {
            "role": "assistant",
            "content": "Your most recent message says 'Good, keep me posted'.",
        },
        {"role": "user", "content": "Thanks!"},
    ]

    assert (
        _answer_retention_response_text(messages)
        == "You're welcome. To recap: Your most recent message says 'Good, keep me posted'."
    )
