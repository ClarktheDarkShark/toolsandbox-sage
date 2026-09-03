"""Runtime routing types shared by the visible-context router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_RUNTIME_BUNDLE_SIZE = 5


@dataclass(frozen=True)
class RuntimeRoutingDecision:
    tool_name: str
    visible: bool
    status: str
    reason: str
    score: int
    matched_positive_triggers: tuple[str, ...] = ()
    matched_negative_triggers: tuple[str, ...] = ()
    matched_task_families: tuple[str, ...] = ()
    fair_chance_candidate: bool = False
    fair_chance_reason: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "visible": self.visible,
            "status": self.status,
            "reason": self.reason,
            "score": self.score,
            "matched_positive_triggers": list(self.matched_positive_triggers),
            "matched_negative_triggers": list(self.matched_negative_triggers),
            "matched_task_families": list(self.matched_task_families),
            "fair_chance_candidate": self.fair_chance_candidate,
            "fair_chance_reason": self.fair_chance_reason,
        }


def _is_insufficient_information_guard(spec: Any) -> bool:
    """Identify tools whose validated contract safely abstains on missing data."""
    output_props = {}
    if isinstance(spec.output_schema, dict):
        raw_props = spec.output_schema.get("properties", {})
        if isinstance(raw_props, dict):
            output_props = raw_props
    evidence_text = " ".join(
        (
            spec.description,
            spec.abstain_behavior,
            spec.generalization_rationale,
            " ".join(spec.positive_triggers),
            " ".join(spec.applicable_task_families),
            " ".join(spec.shortfall_cluster_evidence),
            " ".join(spec.known_failure_mechanisms_addressed),
            " ".join(output_props),
        )
    ).lower()
    has_abstention_contract = (
        "should_abstain" in output_props
        and (
            "clarification_prompt" in output_props
            or "final_answer_recommendation" in output_props
        )
        and (
            "safe_next_action" in output_props or "clarification_prompt" in output_props
        )
        and (
            "missing_information" in output_props
            or "forbidden_downstream_tools" in output_props
        )
    )
    return has_abstention_contract and any(
        token in evidence_text
        for token in (
            "insufficient_information",
            "missing information",
            "missing_information",
            "clarification",
            "minefield",
        )
    )
