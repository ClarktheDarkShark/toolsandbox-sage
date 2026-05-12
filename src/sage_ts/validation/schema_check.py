"""Compile and schema-check generated helper tools after AST safety passes."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from types import FunctionType
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
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


def _annotation_text(annotation: object) -> str:
    return str(getattr(annotation, "__name__", "") or str(annotation))


def _annotation_tokens(annotation: str) -> set[str]:
    text = annotation.strip().lower()
    text = text.replace("typing.", "")
    text = text.replace("nonetype", "none")
    text = text.replace("null", "none")
    text = re.sub(r"\s+", "", text)
    if text.startswith("optional[") and text.endswith("]"):
        inner = text[len("optional[") : -1]
        return _annotation_tokens(inner) | {"none"}
    if text.startswith("union[") and text.endswith("]"):
        inner = text[len("union[") : -1]
        return {
            token
            for part in inner.split(",")
            for token in _annotation_tokens(part)
            if token
        }
    return {part for part in re.split(r"\|", text) if part}


def _annotation_compatible(actual: object, expected: str) -> bool:
    actual_name = _annotation_text(actual)
    if actual_name == expected:
        return True
    actual_tokens = _annotation_tokens(actual_name)
    expected_tokens = _annotation_tokens(expected)
    if actual_tokens == expected_tokens:
        return True
    if "none" in expected_tokens and actual_tokens <= (expected_tokens - {"none"}):
        return True
    return False


def compile_generated_tool(tool: GeneratedTool) -> SchemaResult:
    try:
        parsed = ast.parse(tool.code, filename=f"<generated:{tool.spec.tool_name}>")
    except SyntaxError as exc:
        return SchemaResult(
            False,
            (f"compile_error:SyntaxError:{exc.msg}",),
            None,
        )
    function_defs = [
        node
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(function_defs) != 1:
        return SchemaResult(
            False,
            (f"function_count_mismatch:{len(function_defs)}",),
            None,
        )
    defined_name = function_defs[0].name
    if defined_name != tool.spec.tool_name:
        return SchemaResult(
            False,
            (f"function_name_mismatch:{defined_name}!={tool.spec.tool_name}",),
            None,
        )

    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    errors: list[str] = []
    try:
        exec(
            compile(tool.code, f"<generated:{tool.spec.tool_name}>", "exec"), namespace
        )
    except Exception as exc:
        return SchemaResult(False, (f"compile_error:{type(exc).__name__}:{exc}",), None)

    compiled_functions = [
        value for value in namespace.values() if isinstance(value, FunctionType)
    ]
    if len(compiled_functions) != 1:
        return SchemaResult(
            False,
            (f"compiled_function_count_mismatch:{len(compiled_functions)}",),
            None,
        )
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
        actual_name = _annotation_text(actual)
        if not _annotation_compatible(actual, annotation):
            errors.append(
                f"input_annotation_mismatch:{name}:{actual_name}!={annotation}"
            )
    ret = annotations.get("return")
    if ret is not None:
        ret_name = _annotation_text(ret)
        if not _annotation_compatible(ret, tool.spec.output_annotation):
            errors.append(
                f"return_annotation_mismatch:{ret_name}!={tool.spec.output_annotation}"
            )
    return SchemaResult(not errors, tuple(errors), fn if not errors else None)
