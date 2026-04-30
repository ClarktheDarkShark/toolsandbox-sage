"""Strict gate for deciding whether a generated helper is even eligible."""

from __future__ import annotations

from dataclasses import dataclass

from sage_ts.generation.tool_spec import ToolFamily, ToolSpec

ALLOWED_FAMILIES = frozenset(ToolFamily)
STATE_ACTIONABLE_TOKENS = (
    "next_action",
    "next action",
    "single next action",
    "readiness",
    "ready",
    "precondition_met",
    "predicate",
)


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def evaluate_candidate_gate(spec: ToolSpec) -> GateDecision:
    if spec.family not in ALLOWED_FAMILIES:
        return GateDecision(False, f"unsupported_family:{spec.family}")
    if not spec.inputs:
        return GateDecision(False, "missing_inputs")
    if len(spec.generalization_rationale.strip()) < 20:
        return GateDecision(False, "weak_generalization_rationale")
    if len(spec.inadequacy_evidence.strip()) < 20:
        return GateDecision(False, "weak_inadequacy_evidence")
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        text = " ".join([spec.tool_name, spec.description]).lower()
        if not any(token in text for token in STATE_ACTIONABLE_TOKENS):
            return GateDecision(False, "state_helper_not_runtime_actionable")
    return GateDecision(True, "allowed")
