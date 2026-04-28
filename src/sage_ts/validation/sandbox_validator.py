"""Validation pipeline for generated deterministic helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.schema_check import compile_generated_tool


@dataclass(frozen=True)
class ToolExample:
    inputs: dict[str, Any]
    expected: Any


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    errors: tuple[str, ...]


def validate_generated_tool(
    tool: GeneratedTool,
    examples: tuple[ToolExample, ...],
) -> ValidationResult:
    gate = evaluate_candidate_gate(tool.spec)
    if not gate.allowed:
        return ValidationResult(False, (gate.reason,))

    safety = check_ast_safety(tool.code)
    if not safety.safe:
        return ValidationResult(False, safety.errors)

    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return ValidationResult(False, schema.errors)

    errors: list[str] = []
    for index, example in enumerate(examples):
        try:
            actual = schema.function(**example.inputs)
        except Exception as exc:
            errors.append(f"example_{index}_error:{type(exc).__name__}:{exc}")
            continue
        if actual != example.expected:
            errors.append(f"example_{index}_mismatch:{actual!r}!={example.expected!r}")
    return ValidationResult(not errors, tuple(errors))
