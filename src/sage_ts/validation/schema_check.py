"""Compile and schema-check generated helper tools after AST safety passes."""

from __future__ import annotations

from dataclasses import dataclass
from types import FunctionType
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
}


@dataclass(frozen=True)
class SchemaResult:
    valid: bool
    errors: tuple[str, ...]
    function: FunctionType | None = None


def compile_generated_tool(tool: GeneratedTool) -> SchemaResult:
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    errors: list[str] = []
    try:
        exec(
            compile(tool.code, f"<generated:{tool.spec.tool_name}>", "exec"), namespace
        )
    except Exception as exc:
        return SchemaResult(False, (f"compile_error:{type(exc).__name__}:{exc}",), None)

    fn = namespace.get(tool.spec.tool_name)
    if not isinstance(fn, FunctionType):
        return SchemaResult(False, ("missing_expected_function",), None)
    if fn.__name__ != tool.spec.tool_name:
        return SchemaResult(
            False,
            (f"function_name_mismatch:{fn.__name__}!={tool.spec.tool_name}",),
            None,
        )

    annotations = getattr(fn, "__annotations__", {})
    expected_inputs = {item.name: item.annotation for item in tool.spec.inputs}
    for name, annotation in expected_inputs.items():
        actual = annotations.get(name)
        if actual is None:
            continue  # unannotated is allowed; wrong annotation is not
        actual_name = getattr(actual, "__name__", str(actual))
        if actual_name != annotation:
            errors.append(
                f"input_annotation_mismatch:{name}:{actual_name}!={annotation}"
            )
    ret = annotations.get("return")
    if ret is not None:
        ret_name = getattr(ret, "__name__", str(ret))
        if ret_name != tool.spec.output_annotation:
            errors.append(
                f"return_annotation_mismatch:{ret_name}!={tool.spec.output_annotation}"
            )
    return SchemaResult(not errors, tuple(errors), fn if not errors else None)
