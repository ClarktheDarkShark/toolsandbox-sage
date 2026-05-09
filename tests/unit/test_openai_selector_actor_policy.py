from typing import Any

from openai import NOT_GIVEN

from sage_ts.adapters.openai_toolsandbox_roles import (
    DERIVED_ACTOR_POLICY_SENTINEL,
    SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL,
    SEARCH_WINDOW_ACTOR_POLICY_SENTINEL,
    SELECTOR_ACTOR_POLICY_SENTINEL,
    _derived_actor_policy_message,
    _safe_argument_actor_policy_message,
    _search_window_actor_policy_message,
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


def _search_window_tool(
    name: str = "resolve_search_window_or_bounds",
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                "Use this before an original search when the user gives a "
                "time-window or recency phrase. It returns search kwargs."
            ),
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


def _insufficient_info_tool(
    name: str = "detect_insufficient_visible_records",
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Detect insufficient information before unsafe actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "records": {"type": "array"},
                    "task_intent": {"type": "string"},
                },
            },
        },
    }


def _medium_grain_tool(name: str = "constraint_to_action_planner") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (
                "Medium-grain workflow usage: select a visible record and prepare "
                "safe downstream kwargs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "records": {"type": "array"},
                    "match_field": {"type": "string"},
                    "match_value": {"type": "string"},
                    "action_type": {"type": "string"},
                    "update_fields": {"type": "object"},
                    "return_field": {"type": "string"},
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
    assert "call the helper before manually choosing" in policy["content"]
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


def test_medium_grain_workflow_receives_selector_actor_policy() -> None:
    messages = [
        {
            "role": "tool",
            "name": "search_contacts",
            "content": "[{'person_id': 'p1', 'phone_number': '15550100'}]",
        }
    ]

    policy = _selector_actor_policy_message(messages, [_medium_grain_tool()])

    assert policy is not None
    assert "constraint_to_action_planner" in policy["content"]
    assert "call the helper before manually choosing" in policy["content"]


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


def test_search_window_actor_policy_appears_for_visible_window_helper() -> None:
    messages = [
        {
            "role": "user",
            "content": "Update the phone number of the last person I messaged.",
        }
    ]

    policy = _search_window_actor_policy_message(messages, [_search_window_tool()])

    assert policy is not None
    assert SEARCH_WINDOW_ACTOR_POLICY_SENTINEL in policy["content"]
    assert (
        "Never call search_messages or search_reminder with blank strings"
        in (policy["content"])
    )
    assert "call the selector before answering" in policy["content"]


def test_safe_argument_actor_policy_blocks_null_original_tool_args() -> None:
    policy = _safe_argument_actor_policy_message(
        [{"role": "user", "content": "Update whoever I contacted last."}],
        [_search_window_tool()],
    )

    assert policy is not None
    assert SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL in policy["content"]
    assert "person_id=None" in policy["content"]
    assert "Do not probe search_contacts" in policy["content"]
    assert "search_contacts(is_self=true)" in policy["content"]


def test_safe_argument_actor_policy_appears_for_guard_only_helper() -> None:
    policy = _safe_argument_actor_policy_message(
        [{"role": "user", "content": "Find whoever I contacted last."}],
        [_insufficient_info_tool()],
    )

    assert policy is not None
    assert "dedicated helper unambiguously identifies" in policy["content"]


def test_safe_argument_actor_policy_stays_hidden_without_helpers() -> None:
    policy = _safe_argument_actor_policy_message(
        [{"role": "user", "content": "Update whoever I contacted last."}],
        NOT_GIVEN,
    )

    assert policy is None


def test_search_window_actor_policy_stays_hidden_after_helper_call() -> None:
    messages = [
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
        }
    ]

    assert (
        _search_window_actor_policy_message(messages, [_search_window_tool()]) is None
    )
    assert _search_window_actor_policy_message(messages, NOT_GIVEN) is None


def test_selector_actor_policy_preserves_answer_recommendation_text() -> None:
    messages = [
        {
            "role": "tool",
            "name": "search_messages",
            "content": "[{'content': 'Good, keep me posted', 'creation_timestamp': 1}]",
        }
    ]

    policy = _selector_actor_policy_message(messages, [_selector_tool()])

    assert policy is not None
    assert "exact_final_answer" in policy["content"]
    assert "must be exactly that value without markdown" in policy["content"]
