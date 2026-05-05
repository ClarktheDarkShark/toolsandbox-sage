"""Lightweight live validation for generated candidates before registry acceptance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.adequacy.candidate_gate import grading_accounting_classification
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.sandbox_validator import ToolExample
from sage_ts.validation.schema_check import compile_generated_tool


@dataclass(frozen=True)
class LiveCandidateCheck:
    accepted: bool
    errors: tuple[str, ...]
    grading_classification: str
    canonical_route_substitution_risk: str
    negative_abstain_count: int
    positive_usable_count: int
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "errors": list(self.errors),
            "grading_classification": self.grading_classification,
            "canonical_route_substitution_risk": self.canonical_route_substitution_risk,
            "negative_abstain_count": self.negative_abstain_count,
            "positive_usable_count": self.positive_usable_count,
            "warnings": list(self.warnings),
        }


def _usable_output(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return bool(value)
    return True


def _abstained(value: Any) -> bool:
    if value in (None, "", {}, []):
        return True
    if isinstance(value, dict):
        if value.get("abstain_reason"):
            return True
        if (
            value.get("should_call") is False
            or value.get("should_call_search") is False
        ):
            return True
        if value.get("should_call_add_reminder") is False:
            return True
        if (
            value.get("should_call_tool") is False
            and not value.get("selected_record")
            and not value.get("selected_id")
            and not value.get("value")
            and not value.get("downstream_tool_name")
        ):
            return True
    return False


def run_lightweight_live_candidate_check(
    tool: GeneratedTool,
    examples: tuple[ToolExample, ...],
) -> LiveCandidateCheck:
    """Execute candidate examples and enforce minimal route-accounting evidence."""
    classification = grading_accounting_classification(tool.spec)
    errors: list[str] = []
    warnings: list[str] = []
    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return LiveCandidateCheck(
            False,
            tuple(schema.errors or ("live_schema_invalid",)),
            classification,
            tool.spec.canonical_route_substitution_risk,
            0,
            0,
        )

    positive_usable = 0
    negative_abstain = 0
    for index, example in enumerate(examples):
        try:
            result = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
        except Exception as exc:
            errors.append(
                f"live_example_{index}_runtime_error:{type(exc).__name__}:{exc}"
            )
            continue
        if example.negative_applicability:
            if _abstained(result):
                negative_abstain += 1
            else:
                errors.append(f"live_example_{index}_negative_not_abstained")
        elif _usable_output(result) and not _abstained(result):
            positive_usable += 1
        else:
            errors.append(f"live_example_{index}_positive_unusable_output")

    risk = tool.spec.canonical_route_substitution_risk.strip().lower()
    if risk != "none":
        if not tool.spec.expected_milestone_calls_replaced:
            if (
                len(tool.spec.final_state_preservation_plan.strip()) >= 20
                and len(tool.spec.grading_accounting_note.strip()) >= 20
                and positive_usable > 0
            ):
                warnings.append("live_missing_expected_milestone_calls_replaced")
            else:
                errors.append("live_missing_expected_milestone_calls_replaced")
        if len(tool.spec.final_state_preservation_plan.strip()) < 20:
            errors.append("live_missing_final_state_preservation_plan")
        if len(tool.spec.grading_accounting_note.strip()) < 20:
            errors.append("live_missing_grading_accounting_note")

    return LiveCandidateCheck(
        not errors,
        tuple(errors),
        classification,
        tool.spec.canonical_route_substitution_risk,
        negative_abstain,
        positive_usable,
        tuple(warnings),
    )
