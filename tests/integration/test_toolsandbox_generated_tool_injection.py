import json
from pathlib import Path

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
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


def _registry_with_state_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="next_service_enablement_action",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description="Return a concrete next_action and readiness predicate.",
        inputs=(
            ToolInput("target_service", "str", "Requested service."),
            ToolInput("wifi_enabled", "bool", "Whether Wi-Fi is already enabled."),
        ),
        output_annotation="dict",
        generalization_rationale=(
            "Direct service-state scenarios repeatedly need a deterministic readiness "
            "predicate and a single next action before finalizing."
        ),
        inadequacy_evidence=(
            "Base tools expose raw service setters/getters but not a reusable "
            "state-precondition decision helper."
        ),
    )
    code = """
def next_service_enablement_action(target_service: str, wifi_enabled: bool) -> dict:
    if target_service.lower() == "wifi" and not wifi_enabled:
        return {"ready": False, "next_action": "set_wifi_status_true"}
    return {"ready": True, "next_action": "none"}
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {"target_service": "wifi", "wifi_enabled": False},
                {"ready": False, "next_action": "set_wifi_status_true"},
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_latest_selector(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="select_latest_record_by_timestamp",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select the visible candidate record with the largest timestamp.",
        inputs=(
            ToolInput("records_payload", "dict", "Dict containing records list."),
            ToolInput("timestamp_key", "str", "Timestamp field to compare."),
        ),
        output_annotation="dict",
        generalization_rationale=(
            "Latest-record tasks repeatedly require selecting the newest visible "
            "search result before using original ToolSandbox tools."
        ),
        inadequacy_evidence=(
            "Base search tools return records but do not provide a reusable "
            "timestamp-ranking helper."
        ),
    )
    code = """
def select_latest_record_by_timestamp(records_payload: dict, timestamp_key: str) -> dict:
    records = records_payload.get("records", [])
    best = {}
    best_value = None
    for record in records:
        if not isinstance(record, dict):
            continue
        value = record.get(timestamp_key)
        if not isinstance(value, (int, float)):
            continue
        if best_value is None or float(value) > best_value:
            best_value = float(value)
            best = dict(record)
    return best
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"content": "old", "creation_timestamp": 10.0},
                            {"content": "new", "creation_timestamp": 20.0},
                        ]
                    },
                    "timestamp_key": "creation_timestamp",
                },
                {"content": "new", "creation_timestamp": 20.0},
            ),
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
    assert next(iter(enhanced.starting_context.name_to_tool)) == tool_name
    assert enhanced.starting_context.tool_allow_list is not None
    assert enhanced.starting_context.tool_allow_list[0] == tool_name

    available_tools = enhanced.starting_context.get_available_tools(
        scrambling_allowed=False
    )
    assert next(iter(available_tools)) == tool_name
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


def test_state_helpers_are_only_exposed_on_relevant_state_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_state_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest",
    )
    direct_state = with_registry_tools(
        scenario,
        store,
        scenario_name="turn_on_wifi_low_battery_mode",
    )

    assert (
        "next_service_enablement_action" not in unrelated.starting_context.name_to_tool
    )
    assert (
        "next_service_enablement_action" in direct_state.starting_context.name_to_tool
    )


def test_latest_selector_only_exposed_on_latest_record_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_latest_selector(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_sender_phone_number_with_content",
    )
    latest = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_latest_10_distraction_tools",
    )

    tool_name = "select_latest_record_by_timestamp"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in latest.starting_context.name_to_tool


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
