"""Validation pipeline for generated deterministic helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    new_context,
)
from tool_sandbox.common.tool_conversion import convert_to_openai_tool
from tool_sandbox.common.utils import add_tool_trace


@dataclass(frozen=True)
class ToolExample:
    inputs: dict[str, Any]
    expected: Any
    held_out: bool = False


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    errors: tuple[str, ...]
    source_example_count: int = 0
    held_out_check_count: int = 0
    runtime_smoke_passed: bool = False


def _json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


def _partition_examples(
    examples: tuple[ToolExample, ...],
) -> tuple[tuple[ToolExample, ...], tuple[ToolExample, ...]]:
    """Split examples into source and semantic held-out cases.

    Existing observations predate the ``held_out`` flag and usually include
    multiple semantic expected-output examples. For those, keep all but the
    final case as source and reserve the final case as held-out. A single
    example is no longer sufficient for claim-grade acceptance.
    """
    marked_held_out = tuple(example for example in examples if example.held_out)
    if marked_held_out:
        source = tuple(example for example in examples if not example.held_out)
        return source, marked_held_out
    if len(examples) >= 2:
        return examples[:-1], examples[-1:]
    return examples, ()


def _runtime_smoke(
    tool: GeneratedTool,
    example: ToolExample | None,
) -> tuple[bool, str | None]:
    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return False, "runtime_smoke_schema_invalid"
    try:
        convert_to_openai_tool(schema.function, name=tool.spec.tool_name)
    except Exception as exc:
        return False, f"runtime_smoke_tool_schema_error:{type(exc).__name__}:{exc}"
    if example is None:
        return False, "runtime_smoke_missing_example"
    try:
        context = ExecutionContext()
        context.trace_tool = True
        sandbox_namespace = cast(DatabaseNamespace, DatabaseNamespace.SANDBOX)
        context.add_to_database(
            sandbox_namespace,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": f"runtime smoke for {tool.spec.tool_name}",
                    "openai_tool_call_id": "sage-runtime-smoke",
                    "openai_function_name": tool.spec.tool_name,
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        with new_context(context):
            result = schema.function(**example.inputs)
            add_tool_trace(schema.function, result, **example.inputs)
            sandbox = context.get_database(sandbox_namespace)
            traces = sandbox["tool_trace"][0]
            if traces is None or len(traces) == 0:
                return False, "runtime_smoke_missing_tool_trace"
    except Exception as exc:
        return False, f"runtime_smoke_toolsandbox_error:{type(exc).__name__}:{exc}"
    return True, None


def validate_generated_tool(
    tool: GeneratedTool,
    examples: tuple[ToolExample, ...],
) -> ValidationResult:
    if not examples:
        return ValidationResult(False, ("missing_source_examples",))
    source_examples, held_out_examples = _partition_examples(examples)
    if not source_examples:
        return ValidationResult(False, ("missing_source_examples",))
    if not held_out_examples:
        return ValidationResult(
            False,
            ("missing_semantic_held_out_examples",),
            source_example_count=len(source_examples),
        )

    gate = evaluate_candidate_gate(tool.spec)
    if not gate.allowed:
        return ValidationResult(
            False, (gate.reason,), source_example_count=len(source_examples)
        )

    safety = check_ast_safety(tool.code)
    if not safety.safe:
        return ValidationResult(
            False, safety.errors, source_example_count=len(source_examples)
        )

    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return ValidationResult(
            False, schema.errors, source_example_count=len(source_examples)
        )

    errors: list[str] = []
    all_examples = (
        *(
            (f"source_{index}", example)
            for index, example in enumerate(source_examples)
        ),
        *(
            (f"held_out_{index}", example)
            for index, example in enumerate(held_out_examples)
        ),
    )
    for label, example in all_examples:
        try:
            actual = schema.function(**example.inputs)
            replay = schema.function(**example.inputs)
        except Exception as exc:
            errors.append(f"{label}_error:{type(exc).__name__}:{exc}")
            continue
        if actual != replay:
            errors.append(f"{label}_nondeterministic:{actual!r}!={replay!r}")
        if actual != example.expected:
            errors.append(f"{label}_mismatch:{actual!r}!={example.expected!r}")
        if not _json_serializable(actual):
            errors.append(f"{label}_non_json_serializable_output")

    runtime_smoke_passed, runtime_error = _runtime_smoke(
        tool,
        source_examples[0] if source_examples else None,
    )
    if runtime_error is not None:
        errors.append(runtime_error)

    return ValidationResult(
        not errors,
        tuple(errors),
        source_example_count=len(source_examples),
        held_out_check_count=len(held_out_examples),
        runtime_smoke_passed=runtime_smoke_passed,
    )
