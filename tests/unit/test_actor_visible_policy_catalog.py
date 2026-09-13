import json
import re

import sage_ts.adapters.openai_toolsandbox_roles as roles
from sage_ts.adapters.actor_visible_policy_catalog import (
    actor_visible_policy_catalog_scope,
    build_actor_visible_policy_catalog,
)
from tool_sandbox.common.execution_context import (
    ExecutionContext,
    RoleType,
    ScenarioCategories,
    new_context,
)
from tool_sandbox.common.tool_conversion import convert_to_openai_tools


def _scrambled_policy_tools() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "generated_tools_0",
                "description": (
                    "Determine whether the actor can safely proceed or abstain. "
                    "Generated SAGE tool usage."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_request": {"type": "string"},
                        "requested_action": {"type": "string"},
                        "required_original_tools": {"type": "array"},
                        "available_original_tools": {"type": "array"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reminder_3",
                "description": "Search for reminders using the supplied criteria.",
                "parameters": {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "utility_9",
                "description": "Unrelated opaque utility.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def _completion_for_tool(tool_name: str):
    return roles.ChatCompletion.model_validate(
        {
            "id": "actor-visible-policy-test",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps({}),
                                },
                            }
                        ],
                    },
                }
            ],
            "created": 0,
            "model": "gpt-4o-mini",
            "object": "chat.completion",
        }
    )


def test_real_scrambled_native_aliases_resolve_from_public_schemas() -> None:
    context = ExecutionContext(
        tool_allow_list=["search_contacts", "send_message_with_phone_number"],
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED],
    )
    with new_context(context):
        available = {
            name: tool
            for name, tool in context.get_available_tools(
                scrambling_allowed=True
            ).items()
            if RoleType.AGENT in getattr(tool, "visible_to", (RoleType.AGENT,))
        }
        schemas = convert_to_openai_tools(available)

    catalog = build_actor_visible_policy_catalog(
        schemas,
        known_semantic_capabilities=roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES,
    )

    contact_alias = catalog.visible_name("search_contacts")
    message_alias = catalog.visible_name("send_message_with_phone_number")
    assert contact_alias in available and contact_alias != "search_contacts"
    assert (
        message_alias in available and message_alias != "send_message_with_phone_number"
    )
    assert catalog.semantic_name(contact_alias) == "search_contacts"
    assert catalog.semantic_name(message_alias) == "send_message_with_phone_number"


def test_unknown_opaque_schema_stays_opaque_and_is_not_generated() -> None:
    tools = _scrambled_policy_tools()
    catalog = build_actor_visible_policy_catalog(
        tools,
        known_semantic_capabilities=roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES,
    )

    assert catalog.semantic_name("utility_9") == "utility_9"
    assert not catalog.is_generated("utility_9")
    assert catalog.is_generated("generated_tools_0")


def test_generated_policy_order_matches_the_sent_schema_order() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generated_second",
                "description": "Second public SAGE helper.",
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generated_first",
                "description": "First public SAGE helper.",
            },
        },
    ]
    catalog = build_actor_visible_policy_catalog(
        tools,
        known_semantic_capabilities=roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES,
    )

    with actor_visible_policy_catalog_scope(catalog):
        assert roles._generated_tool_names_execution_facing(tools) == [
            "generated_second",
            "generated_first",
        ]


def test_ambiguous_public_capability_is_never_named_as_a_tool_choice() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": alias,
                "description": "Search for reminders using supplied criteria.",
                "parameters": {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                },
            },
        }
        for alias in ("reminder_3", "reminder_4")
    ]
    catalog = build_actor_visible_policy_catalog(
        tools,
        known_semantic_capabilities=roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES,
    )

    with actor_visible_policy_catalog_scope(catalog):
        assert roles._tool_name_for_call(tools, "search_reminder") == ""


def test_scrambled_filter_and_history_use_only_visible_schema_names() -> None:
    tools = _scrambled_policy_tools()
    catalog = build_actor_visible_policy_catalog(
        tools,
        known_semantic_capabilities=roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES,
    )
    messages = [
        {"role": "user", "content": "Which reminder was due yesterday?"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "generated_tools_0", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "name": "generated_tools_0",
            "tool_call_id": "call_1",
            "content": "{'should_abstain': True}",
        },
        {
            "role": "tool",
            "name": "reminder_3",
            "tool_call_id": "call_2",
            "content": "[]",
        },
    ]

    with actor_visible_policy_catalog_scope(catalog):
        assert roles._message_already_called_any_generated_tool(messages, tools)
        assert roles._latest_tool_message(messages, "search_reminder") is messages[-1]
        filtered = roles._dynamic_generated_tool_schema_filter(
            [{"role": "user", "content": "Which reminder was due yesterday?"}],
            tools,
            selected_tool_name="generated_tools_0",
        )

    # The selected public SAGE alias is retained, and unknown native/distraction
    # aliases are never removed merely because their private identity is unknown.
    assert roles._tool_names(filtered) == {
        "generated_tools_0",
        "reminder_3",
        "utility_9",
    }


def test_model_inference_fails_if_policy_attempts_private_alias_reversal(
    monkeypatch,
) -> None:
    tools = _scrambled_policy_tools()
    messages = [{"role": "user", "content": "Which reminder was due yesterday?"}]

    class PrivateAliasReversalUsed(BaseException):
        pass

    def reject_private_alias_reversal(_self, _name: str) -> str:
        # BaseException is intentional: the former implementation swallowed
        # ordinary Exceptions and would make a weaker guard produce a false pass.
        raise PrivateAliasReversalUsed

    monkeypatch.setattr(
        ExecutionContext,
        "get_execution_facing_tool_name",
        reject_private_alias_reversal,
    )
    agent = object.__new__(roles.ConfigurableOpenAIAgent)
    agent.model_name = "gpt-4o-mini"
    captured: dict[str, object] = {}

    def capture_choice(prompted_messages, prompted_tools, tool_name):
        captured["messages"] = prompted_messages
        captured["tools"] = prompted_tools
        captured["choice"] = tool_name
        return _completion_for_tool(tool_name)

    monkeypatch.setattr(agent, "_model_inference_with_tool_choice", capture_choice)
    context = ExecutionContext()
    with new_context(context):
        completion = agent.model_inference(messages, tools)

    sent_names = roles._tool_names(tools)
    prompted_names = roles._tool_names(captured["tools"])
    assert captured["choice"] == "generated_tools_0"
    assert captured["choice"] in prompted_names <= sent_names
    assert completion.choices[0].message.tool_calls[0].function.name in sent_names

    policy_text = " ".join(
        str(message.get("content") or "")
        for message in captured["messages"]
        if message.get("role") == "system"
    )
    for hidden_name in roles.ORIGINAL_TOOLSANDBOX_TOOL_NAMES - sent_names:
        assert (
            re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(hidden_name)}(?![A-Za-z0-9_])",
                policy_text,
            )
            is None
        )
