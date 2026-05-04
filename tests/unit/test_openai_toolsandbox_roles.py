from openai import NOT_GIVEN

from sage_ts.adapters.openai_toolsandbox_roles import (
    _message_already_called_tool,
    _messages_show_prior_tool_call,
    _messages_show_tool_error,
    _tool_names,
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
