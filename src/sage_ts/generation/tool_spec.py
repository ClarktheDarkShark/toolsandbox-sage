"""Typed specifications for deterministic generated helper tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from strenum import StrEnum


class ToolFamily(StrEnum):
    CANONICALIZER = "canonicalizer"
    DERIVED_VALUE_CALCULATOR = "derived_value_calculator"
    STATE_PRECONDITION_HELPER = "state_precondition_helper"
    COMPOSITE_WORKFLOW_HELPER = "composite_workflow_helper"
    VALIDATION_ABSTENTION_HELPER = "validation_abstention_helper"


@dataclass(frozen=True)
class ToolInput:
    name: str
    annotation: str
    description: str

    def to_json(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ToolSpec:
    tool_name: str
    family: ToolFamily
    description: str
    inputs: tuple[ToolInput, ...]
    output_annotation: str
    generalization_rationale: str
    inadequacy_evidence: str

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "family": self.family.value,
            "description": self.description,
            "inputs": [item.to_json() for item in self.inputs],
            "output_annotation": self.output_annotation,
            "generalization_rationale": self.generalization_rationale,
            "inadequacy_evidence": self.inadequacy_evidence,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "ToolSpec":
        return cls(
            tool_name=str(payload["tool_name"]),
            family=ToolFamily(str(payload["family"])),
            description=str(payload["description"]),
            inputs=tuple(ToolInput(**item) for item in payload["inputs"]),
            output_annotation=str(payload["output_annotation"]),
            generalization_rationale=str(payload["generalization_rationale"]),
            inadequacy_evidence=str(payload["inadequacy_evidence"]),
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
