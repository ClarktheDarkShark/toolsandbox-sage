"""Typed specifications for deterministic generated helper tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

TOOL_SPEC_SCHEMA_VERSION = 2


class ToolFamily(str, Enum):
    CANONICALIZER = "canonicalizer"
    DERIVED_VALUE_CALCULATOR = "derived_value_calculator"
    STATE_PRECONDITION_HELPER = "state_precondition_helper"
    SEARCH_FILTER_RANKING_HELPER = "search_filter_ranking_helper"
    COMPOSITE_WORKFLOW_HELPER = "composite_workflow_helper"
    VALIDATION_ABSTENTION_HELPER = "validation_abstention_helper"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ToolInput:
    name: str
    annotation: str
    description: str

    def to_json(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredInadequacyEvidence:
    summary: str
    signals: tuple[str, ...]
    failed_tool_calls: tuple[str, ...] = ()
    repeated_failed_tool_calls: tuple[str, ...] = ()
    visible_data_gaps: tuple[str, ...] = ()
    planner_failures: tuple[str, ...] = ()
    final_answer_route_mismatch: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "signals": list(self.signals),
            "failed_tool_calls": list(self.failed_tool_calls),
            "repeated_failed_tool_calls": list(self.repeated_failed_tool_calls),
            "visible_data_gaps": list(self.visible_data_gaps),
            "planner_failures": list(self.planner_failures),
            "final_answer_route_mismatch": self.final_answer_route_mismatch,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "StructuredInadequacyEvidence":
        return cls(
            summary=str(payload.get("summary", "")),
            signals=_coerce_str_tuple(payload.get("signals", ())),
            failed_tool_calls=_coerce_str_tuple(payload.get("failed_tool_calls", ())),
            repeated_failed_tool_calls=_coerce_str_tuple(
                payload.get("repeated_failed_tool_calls", ())
            ),
            visible_data_gaps=_coerce_str_tuple(payload.get("visible_data_gaps", ())),
            planner_failures=_coerce_str_tuple(payload.get("planner_failures", ())),
            final_answer_route_mismatch=bool(
                payload.get("final_answer_route_mismatch", False)
            ),
        )


def coerce_inadequacy_evidence(
    payload: StructuredInadequacyEvidence | dict[str, Any] | str,
) -> StructuredInadequacyEvidence:
    if isinstance(payload, StructuredInadequacyEvidence):
        return payload
    if isinstance(payload, dict):
        return StructuredInadequacyEvidence.from_json(payload)
    return StructuredInadequacyEvidence(
        summary=str(payload),
        signals=("legacy_unstructured_evidence",),
    )


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, dict):
        return tuple(str(item) for item in value.values() if str(item).strip())
    try:
        return tuple(str(item) for item in value if str(item).strip())
    except TypeError:
        text = str(value)
        return (text,) if text.strip() else ()


@dataclass(frozen=True)
class ToolSpec:
    tool_name: str
    family: ToolFamily
    description: str
    inputs: tuple[ToolInput, ...]
    output_annotation: str
    output_schema: dict[str, Any] | None = None
    positive_triggers: tuple[str, ...] = ()
    negative_triggers: tuple[str, ...] = ()
    preserves_side_effect_tools: tuple[str, ...] = ()
    required_original_tool_calls: tuple[str, ...] = ()
    abstain_behavior: str = ""
    generalization_rationale: str = ""
    estimated_step_compression: int | None = None
    cross_task_applicability_count: int | None = None
    applicable_task_families: tuple[str, ...] = ()
    reason_tool_is_decisive: str = ""
    diagnostic_only: bool = False
    shortfall_cluster_evidence: tuple[str, ...] = ()
    known_failure_mechanisms_addressed: tuple[str, ...] = ()
    canonical_route_substitution_risk: str = "none"
    expected_milestone_calls_replaced: tuple[str, ...] = ()
    final_state_preservation_plan: str = ""
    grading_accounting_note: str = ""
    native_action_delegation: bool = False
    inadequacy_evidence: StructuredInadequacyEvidence = StructuredInadequacyEvidence(
        summary="",
        signals=(),
    )
    schema_version: int = TOOL_SPEC_SCHEMA_VERSION

    def to_json(self) -> dict[str, Any]:
        evidence = coerce_inadequacy_evidence(self.inadequacy_evidence)
        return {
            "schema_version": self.schema_version,
            "tool_name": self.tool_name,
            "family": self.family.value,
            "description": self.description,
            "inputs": [item.to_json() for item in self.inputs],
            "output_annotation": self.output_annotation,
            "output_schema": self.output_schema,
            "positive_triggers": list(self.positive_triggers),
            "negative_triggers": list(self.negative_triggers),
            "preserves_side_effect_tools": list(self.preserves_side_effect_tools),
            "required_original_tool_calls": list(self.required_original_tool_calls),
            "abstain_behavior": self.abstain_behavior,
            "generalization_rationale": self.generalization_rationale,
            "estimated_step_compression": self.estimated_step_compression,
            "cross_task_applicability_count": self.cross_task_applicability_count,
            "applicable_task_families": list(self.applicable_task_families),
            "reason_tool_is_decisive": self.reason_tool_is_decisive,
            "diagnostic_only": self.diagnostic_only,
            "shortfall_cluster_evidence": list(self.shortfall_cluster_evidence),
            "known_failure_mechanisms_addressed": list(
                self.known_failure_mechanisms_addressed
            ),
            "canonical_route_substitution_risk": self.canonical_route_substitution_risk,
            "expected_milestone_calls_replaced": list(
                self.expected_milestone_calls_replaced
            ),
            "final_state_preservation_plan": self.final_state_preservation_plan,
            "grading_accounting_note": self.grading_accounting_note,
            "native_action_delegation": self.native_action_delegation,
            "inadequacy_evidence": evidence.to_json(),
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "ToolSpec":
        raw_output_schema = payload.get("output_schema")
        return cls(
            schema_version=int(payload.get("schema_version", TOOL_SPEC_SCHEMA_VERSION)),
            tool_name=str(payload["tool_name"]),
            family=ToolFamily(str(payload["family"])),
            description=str(payload["description"]),
            inputs=tuple(ToolInput(**item) for item in payload["inputs"]),
            output_annotation=str(payload["output_annotation"]),
            output_schema=raw_output_schema
            if isinstance(raw_output_schema, dict)
            else None,
            positive_triggers=tuple(
                str(item) for item in payload.get("positive_triggers", ())
            ),
            negative_triggers=tuple(
                str(item) for item in payload.get("negative_triggers", ())
            ),
            preserves_side_effect_tools=tuple(
                str(item) for item in payload.get("preserves_side_effect_tools", ())
            ),
            required_original_tool_calls=tuple(
                str(item) for item in payload.get("required_original_tool_calls", ())
            ),
            abstain_behavior=str(payload.get("abstain_behavior", "")),
            generalization_rationale=str(payload["generalization_rationale"]),
            estimated_step_compression=(
                int(payload["estimated_step_compression"])
                if payload.get("estimated_step_compression") is not None
                else None
            ),
            cross_task_applicability_count=(
                int(payload["cross_task_applicability_count"])
                if payload.get("cross_task_applicability_count") is not None
                else None
            ),
            applicable_task_families=tuple(
                str(item) for item in payload.get("applicable_task_families", ())
            ),
            reason_tool_is_decisive=str(payload.get("reason_tool_is_decisive", "")),
            diagnostic_only=bool(payload.get("diagnostic_only", False)),
            shortfall_cluster_evidence=tuple(
                str(item) for item in payload.get("shortfall_cluster_evidence", ())
            ),
            known_failure_mechanisms_addressed=tuple(
                str(item)
                for item in payload.get("known_failure_mechanisms_addressed", ())
            ),
            canonical_route_substitution_risk=str(
                payload.get("canonical_route_substitution_risk", "none")
            ),
            expected_milestone_calls_replaced=tuple(
                str(item)
                for item in payload.get("expected_milestone_calls_replaced", ())
            ),
            final_state_preservation_plan=str(
                payload.get("final_state_preservation_plan", "")
            ),
            grading_accounting_note=str(payload.get("grading_accounting_note", "")),
            native_action_delegation=bool(
                payload.get("native_action_delegation", False)
            ),
            inadequacy_evidence=coerce_inadequacy_evidence(
                payload.get("inadequacy_evidence", "")
            ),
        )


@dataclass(frozen=True)
class GeneratedTool:
    spec: ToolSpec
    code: str

    def to_json(self) -> dict[str, Any]:
        return {"spec": self.spec.to_json(), "code": self.code}

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "GeneratedTool":
        return cls(spec=ToolSpec.from_json(payload["spec"]), code=str(payload["code"]))
