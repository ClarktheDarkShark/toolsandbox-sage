import json
from pathlib import Path

from sage_ts.orchestration.toy_mechanism import canonicalizer_tool
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.toolsandbox_integration import with_registry_tools
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    ScenarioCategories,
    new_context,
)
from tool_sandbox.common.message_conversion import Message
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_conversion import convert_to_openai_tool
from tool_sandbox.roles.execution_environment import respond_to_single_message


def _registry_with_canonicalizer(tmp_path: Path) -> RegistryStore:
    tool = canonicalizer_tool()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular"),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def test_registry_tools_are_available_to_toolsandbox_context(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    scenario = Scenario(starting_context=context)

    reused_tools: list[str] = []
    enhanced = with_registry_tools(scenario, store, on_reuse=reused_tools.append)

    tool_name = "canonicalize_connectivity_label"
    assert tool_name not in scenario.starting_context.name_to_tool
    assert tool_name in enhanced.starting_context.name_to_tool
    assert enhanced.starting_context.tool_allow_list is not None
    assert tool_name in enhanced.starting_context.tool_allow_list

    available_tools = enhanced.starting_context.get_available_tools(
        scrambling_allowed=False
    )
    assert available_tools[tool_name]("Wi-Fi") == "wifi"
    assert reused_tools == [tool_name]

    openai_tool = convert_to_openai_tool(available_tools[tool_name], tool_name)
    parameters = openai_tool["function"]["parameters"]
    assert openai_tool["function"]["description"].startswith(
        "Normalize connectivity labels"
    )
    assert parameters["properties"]["label"]["type"] == "string"
    assert parameters["properties"]["label"]["description"] == (
        "Raw connectivity label."
    )
    assert parameters["required"] == ["label"]


def test_registry_tools_execute_through_toolsandbox_console(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    reused_tools: list[str] = []
    enhanced = with_registry_tools(
        Scenario(starting_context=context),
        store,
        on_reuse=reused_tools.append,
    )

    message = Message(
        sender=RoleType.AGENT,
        recipient=RoleType.EXECUTION_ENVIRONMENT,
        content=(
            "call_1_parameters = {'label': 'Wi-Fi'}\n"
            "call_1_response = canonicalize_connectivity_label(**call_1_parameters)\n"
            "print(repr(call_1_response))"
        ),
        openai_tool_call_id="call_1",
        openai_function_name="canonicalize_connectivity_label",
    )
    response = respond_to_single_message(
        enhanced.starting_context.interactive_console,
        message,
        RoleType.EXECUTION_ENVIRONMENT,
    )

    assert response is not None
    assert response.tool_call_exception is None
    assert response.content == "'wifi'"
    assert reused_tools == ["canonicalize_connectivity_label"]


def test_registry_tools_emit_toolsandbox_trace(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    enhanced = with_registry_tools(Scenario(starting_context=context), store)
    tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
        "canonicalize_connectivity_label"
    ]
    enhanced.starting_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "canonicalize_connectivity_label(label='Wi-Fi')",
                "openai_tool_call_id": "call_1",
                "openai_function_name": "canonicalize_connectivity_label",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": None,
            }
        ],
    )

    with new_context(enhanced.starting_context):
        enhanced.starting_context.trace_tool = True
        assert tool("Wi-Fi") == "wifi"
        trace_series = enhanced.starting_context.get_database(
            DatabaseNamespace.SANDBOX
        )["tool_trace"][0]

    traces = trace_series.to_list()
    assert len(traces) == 1
    payload = json.loads(traces[0])
    assert payload["tool_name"] == "canonicalize_connectivity_label"
    assert payload["arguments"] == {"label": "Wi-Fi"}
    assert payload["result"] == "wifi"


def test_generated_tools_support_toolsandbox_name_scrambling(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(
        tool_allow_list=["end_conversation"],
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED],
    )
    enhanced = with_registry_tools(Scenario(starting_context=context), store)

    available_tools = enhanced.starting_context.get_available_tools(
        scrambling_allowed=True
    )

    execution_names = {tool.__name__ for tool in available_tools.values()}
    assert "canonicalize_connectivity_label" in execution_names
