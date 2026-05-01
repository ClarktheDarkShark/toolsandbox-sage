"""Runtime invocation for accepted generated helpers."""

from __future__ import annotations

from typing import Any

from sage_ts.registry.manifest import has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.schema_check import compile_generated_tool


def invoke_registered_tool(
    store: RegistryStore,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    success_flip: bool = False,
) -> Any:
    entry = store.get(tool_name)
    if entry is None or entry.retired:
        raise KeyError(f"registered tool not available: {tool_name}")
    if not has_current_validation_proof(entry):
        raise ValueError(f"registered tool lacks current validation proof: {tool_name}")
    compiled = compile_generated_tool(entry.tool)
    if compiled.function is None:
        raise ValueError(f"registered tool failed to compile: {tool_name}")
    result = compiled.function(**arguments)
    store.record_reuse(tool_name, success_flip=success_flip)
    return result
