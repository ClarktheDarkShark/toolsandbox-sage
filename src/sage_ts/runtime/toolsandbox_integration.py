"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Iterable
from typing import Any, Callable, cast

from decorator import decorate

from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common.execution_context import ExecutionContext, RoleType
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend, get_scrambled_tool_names
from tool_sandbox.common.utils import register_as_tool

PYTHON_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


def _google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    lines = [spec.description, "", "Args:"]
    for item in spec.inputs:
        lines.append(f"    {item.name}: {item.description}")
    lines.extend(["", "Returns:", f"    {spec.output_annotation}"])
    return "\n".join(lines)


def compile_toolsandbox_tool(entry: RegistryEntry) -> Callable[..., Any]:
    """Compile an accepted registry entry into a ToolSandbox-visible callable."""
    return _compile_toolsandbox_tool(entry, on_reuse=None)


def _compile_toolsandbox_tool(
    entry: RegistryEntry,
    on_reuse: Callable[[str], None] | None,
) -> Callable[..., Any]:
    if entry.retired or not entry.validation.accepted:
        raise ValueError(f"registry entry is not active: {entry.tool.spec.tool_name}")

    compiled = compile_generated_tool(entry.tool)
    if compiled.function is None:
        raise ValueError(
            f"registry entry failed schema compilation: {entry.tool.spec.tool_name}"
        )

    function = compiled.function
    if on_reuse is not None:

        def _record_reuse(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            on_reuse(entry.tool.spec.tool_name)
            return result

        function = decorate(function, _record_reuse)

    annotations = dict(function.__annotations__)
    for item in entry.tool.spec.inputs:
        annotations[item.name] = PYTHON_TYPES[item.annotation]
    annotations["return"] = PYTHON_TYPES[entry.tool.spec.output_annotation]
    function.__annotations__ = annotations
    function.__doc__ = _google_docstring(entry)
    function.__module__ = "sage_ts.generated_tools"

    registered = register_as_tool(
        visible_to=(RoleType.AGENT,),
        backend=ToolBackend.DEFAULT,
    )(function)
    registered.__annotations__ = annotations
    registered.__doc__ = function.__doc__
    registered.__module__ = "sage_ts.generated_tools"
    signature = inspect.signature(registered)
    registered.__signature__ = signature.replace(
        parameters=[
            parameter.replace(
                annotation=annotations.get(parameter.name, parameter.annotation)
            )
            for parameter in signature.parameters.values()
        ],
        return_annotation=annotations["return"],
    )
    return cast(Callable[..., Any], registered)


def inject_registry_tools_into_context(
    context: ExecutionContext,
    entries: Iterable[RegistryEntry],
    *,
    on_reuse: Callable[[str], None] | None = None,
) -> list[str]:
    """Inject accepted generated helpers into a ToolSandbox execution context."""
    injected: list[str] = []
    for entry in entries:
        tool_name = entry.tool.spec.tool_name
        if tool_name in context.name_to_tool:
            raise ValueError(f"tool name already exists in ToolSandbox: {tool_name}")
        context.name_to_tool[tool_name] = _compile_toolsandbox_tool(entry, on_reuse)
        if (
            context.tool_allow_list is not None
            and tool_name not in context.tool_allow_list
        ):
            context.tool_allow_list.append(tool_name)
        injected.append(tool_name)

    if injected:
        context._actual_to_scrambled_tool_name = get_scrambled_tool_names(
            context.name_to_tool.values()
        )
        context._scrambled_to_actual_tool_name = {
            value: key for key, value in context._actual_to_scrambled_tool_name.items()
        }
    return injected


def with_registry_tools(
    scenario: Scenario,
    store: RegistryStore,
    *,
    on_reuse: Callable[[str], None] | None = None,
) -> Scenario:
    """Return a scenario copy whose starting context includes registry tools."""
    scenario_copy = copy.deepcopy(scenario)
    inject_registry_tools_into_context(
        scenario_copy.starting_context,
        store.load_entries().values(),
        on_reuse=on_reuse,
    )
    return scenario_copy
