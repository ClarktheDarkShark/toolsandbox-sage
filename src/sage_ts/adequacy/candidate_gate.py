"""Strict gate for deciding whether a generated helper is even eligible."""

from __future__ import annotations

from dataclasses import dataclass

from sage_ts.generation.tool_spec import (
    ToolFamily,
    ToolSpec,
    coerce_inadequacy_evidence,
)

ALLOWED_FAMILIES = frozenset(ToolFamily)
STATE_ACTIONABLE_TOKENS = (
    "next_action",
    "next action",
    "single next action",
    "readiness",
    "ready",
    "precondition_met",
    "predicate",
    "tool_call",
    "tool call",
    "tool_name",
    "arguments",
    "setter",
)
SEARCH_FILTER_ACTIONABLE_TOKENS = (
    "select",
    "filter",
    "rank",
    "record",
    "candidate",
    "timestamp",
    "constraint",
)
STATE_ALLOWED_TOOL_NAMES = frozenset(
    {
        "",
        "set_wifi_status",
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
    }
)


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def _input_names(spec: ToolSpec) -> set[str]:
    return {item.name for item in spec.inputs}


def _output_schema_properties(spec: ToolSpec) -> dict[str, object]:
    schema = spec.output_schema
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def _requires_negative_applicability(spec: ToolSpec) -> bool:
    return spec.family in {
        ToolFamily.STATE_PRECONDITION_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    }


def _requires_output_schema(spec: ToolSpec) -> bool:
    return spec.family in {
        ToolFamily.STATE_PRECONDITION_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    }


def evaluate_candidate_gate(spec: ToolSpec) -> GateDecision:
    if spec.family not in ALLOWED_FAMILIES:
        return GateDecision(False, f"unsupported_family:{spec.family}")
    if not spec.inputs:
        return GateDecision(False, "missing_inputs")
    if len(spec.generalization_rationale.strip()) < 20:
        return GateDecision(False, "weak_generalization_rationale")
    evidence = coerce_inadequacy_evidence(spec.inadequacy_evidence)
    if len(evidence.summary.strip()) < 20:
        return GateDecision(False, "weak_inadequacy_evidence")
    if not evidence.signals:
        return GateDecision(False, "missing_structured_inadequacy_signals")
    if (
        spec.output_annotation == "dict"
        and _requires_output_schema(spec)
        and spec.output_schema is None
    ):
        return GateDecision(False, "missing_output_schema")
    if (
        _requires_negative_applicability(spec)
        and not spec.negative_triggers
        and "insufficient_information" not in spec.abstain_behavior.lower()
    ):
        return GateDecision(False, "missing_negative_triggers")
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        text = " ".join(
            [
                spec.tool_name,
                spec.description,
                spec.output_annotation,
                *(item.name for item in spec.inputs),
            ]
        ).lower()
        if not any(token in text for token in STATE_ACTIONABLE_TOKENS):
            return GateDecision(False, "state_helper_not_runtime_actionable")
        props = _output_schema_properties(spec)
        required = {"tool_name", "arguments", "should_call", "reason"}
        if not required.issubset(props):
            return GateDecision(False, "state_helper_missing_output_contract")
        tool_name_schema = props.get("tool_name")
        if not isinstance(tool_name_schema, dict) or set(
            tool_name_schema.get("enum", ())
        ) != set(STATE_ALLOWED_TOOL_NAMES):
            return GateDecision(False, "state_helper_tool_name_enum_invalid")
        if not spec.preserves_side_effect_tools:
            return GateDecision(False, "state_helper_missing_preserved_tool_contract")
        if not set(spec.required_original_tool_calls).issubset(
            set(spec.preserves_side_effect_tools)
        ):
            return GateDecision(False, "state_helper_required_calls_not_preserved")
    if spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        text = " ".join([spec.tool_name, spec.description]).lower()
        if not any(token in text for token in SEARCH_FILTER_ACTIONABLE_TOKENS):
            return GateDecision(False, "search_filter_not_runtime_actionable")
        input_names = _input_names(spec)
        if not (
            {"records", "candidates"} & input_names
            or "records_payload" in input_names
            or "candidates_payload" in input_names
        ):
            return GateDecision(False, "search_filter_missing_candidate_inputs")
        props = _output_schema_properties(spec)
        if not (
            {"selected_record", "selected_id"} & set(props) or spec.abstain_behavior
        ):
            return GateDecision(False, "search_filter_missing_output_contract")
        if (
            "tie" not in spec.description.lower()
            and "tie" not in spec.abstain_behavior.lower()
        ):
            return GateDecision(False, "search_filter_missing_tie_behavior")
    if spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        if not spec.preserves_side_effect_tools:
            return GateDecision(
                False, "composite_helper_missing_preserved_side_effects"
            )
        if not spec.required_original_tool_calls:
            return GateDecision(
                False, "composite_helper_missing_required_original_calls"
            )
        props = _output_schema_properties(spec)
        if not any(str(key).endswith("_kwargs") for key in props):
            return GateDecision(
                False, "composite_helper_missing_prepared_kwargs_output"
            )
    return GateDecision(True, "allowed")
