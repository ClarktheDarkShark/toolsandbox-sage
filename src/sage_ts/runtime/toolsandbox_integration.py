"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Iterable
from typing import Any, Callable, cast

from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common.execution_context import ExecutionContext, RoleType
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend, get_scrambled_tool_names

PYTHON_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
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

    raw_fn = compiled.function

    # Wrap with reuse callback if provided, using a plain closure (pickle-safe).
    if on_reuse is not None:
        _tool_name = entry.tool.spec.tool_name
        _inner = raw_fn

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            result = _inner(*args, **kwargs)
            on_reuse(_tool_name)
            return result

        _wrapped.__name__ = raw_fn.__name__
        _wrapped.__doc__ = raw_fn.__doc__
        fn: Callable[..., Any] = _wrapped
    else:
        fn = cast(Callable[..., Any], raw_fn)

    # Build annotations using Python type objects.
    annotations: dict[str, Any] = {}
    for item in entry.tool.spec.inputs:
        if item.annotation in PYTHON_TYPES:
            annotations[item.name] = PYTHON_TYPES[item.annotation]
    if entry.tool.spec.output_annotation in PYTHON_TYPES:
        annotations["return"] = PYTHON_TYPES[entry.tool.spec.output_annotation]
    fn.__annotations__ = annotations
    fn.__doc__ = _google_docstring(entry)
    fn.__module__ = "sage_ts.generated_tools"

    # Set ToolSandbox tool metadata directly — avoids the register_as_tool
    # decorator which wraps the function with new_context_with_attribute, a
    # contextvars-backed context manager whose internals are not picklable by dill.
    fn.is_tool = True  # type: ignore[attr-defined]
    fn.visible_to = (RoleType.AGENT,)  # type: ignore[attr-defined]
    fn.backend = ToolBackend.DEFAULT  # type: ignore[attr-defined]

    # Rebuild the inspect.Signature so the agent role can introspect parameters.
    sig = inspect.signature(raw_fn)
    fn.__signature__ = sig.replace(  # type: ignore[attr-defined]
        parameters=[
            p.replace(annotation=annotations.get(p.name, p.annotation))
            for p in sig.parameters.values()
        ],
        return_annotation=annotations.get("return", inspect.Parameter.empty),
    )
    return fn


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
