from typing import Any

from openai import NOT_GIVEN

from sage_ts.adapters.openai_toolsandbox_roles import (
    DERIVED_ACTOR_POLICY_SENTINEL,
    SELECTOR_ACTOR_POLICY_SENTINEL,
    _derived_actor_policy_message,
    _selector_actor_policy_message,
)


def _selector_tool(
    name: str = "select_visible_record_by_constraints",
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                "Visible-record constraint selection usage: use this helper after "
                "search returns visible records."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "records": {"type": "array"},
                    "field_name": {"type": "string"},
                    "expected_value": {"type": "string"},
                    "return_field": {"type": "string"},
                },
            },
        },
    }


def _derived_tool(name: str = "extract_stock_symbol") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                "Deterministic extraction usage: extract and normalize a stock "
                "symbol from a visible search_stock payload."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_payload": {"type": "object"},
                },
            },
        },
    }


def test_selector_actor_policy_appears_after_candidate_records() -> None:
    messages = [
        {"role": "user", "content": "What is Taylor's phone number?"},
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "search_contacts", "arguments": "{}"}}
            ],
        },
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': '1', 'name': 'Taylor', 'phone_number': '555'}]",
        },
    ]

    policy = _selector_actor_policy_message(messages, [_selector_tool()])

    assert policy is not None
    assert policy["role"] == "system"
    assert SELECTOR_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "call the selector before manually choosing" in policy["content"]
    assert "Do not call it without visible candidates" in policy["content"]


def test_selector_actor_policy_stays_hidden_without_records() -> None:
    messages = [{"role": "user", "content": "What is Taylor's phone number?"}]

    assert _selector_actor_policy_message(messages, [_selector_tool()]) is None
    assert _selector_actor_policy_message(messages, NOT_GIVEN) is None


def test_selector_actor_policy_stays_hidden_after_selector_call() -> None:
    messages = [
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': '1'}]",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "select_visible_record_by_constraints",
                        "arguments": "{}",
                    }
                }
            ],
        },
    ]

    assert _selector_actor_policy_message(messages, [_selector_tool()]) is None


def test_selector_actor_policy_ignores_empty_search_results() -> None:
    messages = [{"role": "tool", "name": "search_contacts", "content": "[]"}]

    assert _selector_actor_policy_message(messages, [_selector_tool()]) is None


def test_derived_actor_policy_appears_after_structured_payload() -> None:
    messages = [
        {"role": "user", "content": "What's the stock symbol for Apple?"},
        {
            "role": "tool",
            "name": "search_stock",
            "content": "{'name': 'Apple Inc', 'symbol': 'NASDAQ:AAPL'}",
        },
    ]

    policy = _derived_actor_policy_message(messages, [_derived_tool()])

    assert policy is not None
    assert DERIVED_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "Pass the full prior tool payload" in policy["content"]


def test_derived_actor_policy_stays_hidden_without_payload() -> None:
    messages = [{"role": "user", "content": "What's the stock symbol for Apple?"}]

    assert _derived_actor_policy_message(messages, [_derived_tool()]) is None
    assert _derived_actor_policy_message(messages, NOT_GIVEN) is None
