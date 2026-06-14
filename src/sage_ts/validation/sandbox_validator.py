"""Validation pipeline for generated deterministic helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.output_normalization import normalize_generated_tool_output
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
    negative_applicability: bool = False


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    errors: tuple[str, ...]
    source_example_count: int = 0
    held_out_check_count: int = 0
    negative_applicability_count: int = 0
    runtime_smoke_passed: bool = False


def _json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


def _partition_examples(
    examples: tuple[ToolExample, ...],
) -> tuple[tuple[ToolExample, ...], tuple[ToolExample, ...], tuple[ToolExample, ...]]:
    """Split examples into source and semantic held-out cases.

    Existing observations predate the ``held_out`` flag and usually include
    multiple semantic expected-output examples. For those, keep all but the
    final case as source and reserve the final case as held-out. A single
    example is no longer sufficient for claim-grade acceptance.
    """
    negative_examples = tuple(
        example for example in examples if example.negative_applicability
    )
    non_negative_examples = tuple(
        example for example in examples if not example.negative_applicability
    )
    marked_held_out = tuple(
        example
        for example in examples
        if example.held_out and not example.negative_applicability
    )
    if marked_held_out:
        source = tuple(
            example
            for example in examples
            if not example.held_out and not example.negative_applicability
        )
        return source, marked_held_out, negative_examples
    if len(non_negative_examples) >= 2:
        source = non_negative_examples[:-1]
        held_out = non_negative_examples[-1:]
        return source, held_out, negative_examples
    source = non_negative_examples
    return source, (), negative_examples


def _requires_negative_applicability(tool: GeneratedTool) -> bool:
    return tool.spec.family in {
        ToolFamily.STATE_PRECONDITION_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    }


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
            result = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
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
    source_examples, held_out_examples, negative_examples = _partition_examples(
        examples
    )
    if not source_examples:
        return ValidationResult(False, ("missing_source_examples",))
    if not held_out_examples:
        return ValidationResult(
            False,
            ("missing_semantic_held_out_examples",),
            source_example_count=len(source_examples),
        )
    if _requires_negative_applicability(tool) and not negative_examples:
        return ValidationResult(
            False,
            ("missing_negative_applicability_examples",),
            source_example_count=len(source_examples),
            held_out_check_count=len(held_out_examples),
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
        *(
            (f"negative_{index}", example)
            for index, example in enumerate(negative_examples)
        ),
    )
    for label, example in all_examples:
        try:
            actual = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
            replay = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
            expected = normalize_generated_tool_output(
                tool, example.expected, inputs=example.inputs
            )
        except Exception as exc:
            errors.append(f"{label}_error:{type(exc).__name__}:{exc}")
            continue
        if actual != replay:
            errors.append(f"{label}_nondeterministic:{actual!r}!={replay!r}")
        if actual != expected:
            errors.append(f"{label}_mismatch:{actual!r}!={expected!r}")
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
        negative_applicability_count=len(negative_examples),
        runtime_smoke_passed=runtime_smoke_passed,
    )
