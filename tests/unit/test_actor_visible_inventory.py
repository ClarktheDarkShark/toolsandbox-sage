from sage_ts.runtime.actor_visible_inventory import actor_visible_tool_inventory
from tool_sandbox.common.execution_context import (
    ExecutionContext,
    RoleType,
    ScenarioCategories,
    get_current_context,
)


def _agent_visible_execution_names(context: ExecutionContext) -> set[str]:
    return {
        name
        for name, tool in context.get_available_tools(scrambling_allowed=False).items()
        if RoleType.AGENT in getattr(tool, "visible_to", (RoleType.AGENT,))
    }


def test_scrambled_inventory_contains_only_actor_facing_names_and_schemas() -> None:
    context = ExecutionContext(
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED]
    )

    inventory = actor_visible_tool_inventory(context)
    hidden_execution_names = _agent_visible_execution_names(context)
    public_schema_text = " ".join(inventory.schema_json)

    assert set(inventory.names).isdisjoint(hidden_execution_names)
    assert all(name not in public_schema_text for name in hidden_execution_names)
    assert context.get_agent_facing_tool_name("end_conversation") not in inventory.names


def test_public_schema_semantics_preserve_native_compatibility_tags() -> None:
    context = ExecutionContext(
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED]
    )

    inventory = actor_visible_tool_inventory(context)
    hidden_execution_names = _agent_visible_execution_names(context)
    derived_capabilities = set(inventory.semantic_capabilities) - set(inventory.names)

    # Execution-facing names are used here only as the test oracle.  Production
    # derives this identical compatibility set from public descriptions and
    # parameter names and never reads the hidden mapping.
    assert derived_capabilities == hidden_execution_names


def test_inventory_schema_conversion_restores_process_context() -> None:
    original = get_current_context()
    scenario_context = ExecutionContext(
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED]
    )

    actor_visible_tool_inventory(scenario_context)

    assert get_current_context() is original
