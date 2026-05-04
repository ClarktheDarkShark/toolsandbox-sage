"""Strict gate for deciding whether a generated helper is even eligible."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sage_ts.adequacy.failure_memory import gate_failure_memory_reasons
from sage_ts.experiments.v2_flags import GRADING_ACCOUNTING, feature_enabled
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
CANONICAL_SUBSTITUTION_RISK_LEVELS = frozenset({"none", "low", "medium", "high"})
SINGLE_BASE_TOOL_REPLACEMENT_PHRASES = (
    "replace a single existing base tool",
    "replace one existing base tool",
    "single existing base tool",
    "single base tool",
    "thin helper",
)
GENERIC_TASK_FAMILY_LABELS = frozenset(
    {
        "canonicalizer",
        "derived_value_calculator",
        "state_precondition_helper",
        "search_filter_ranking_helper",
        "composite_workflow_helper",
        "validation_abstention_helper",
        "helper",
        "search_filter",
        "state_precondition",
        "timestamp_conversion",
    }
)
DOWNSTREAM_TOOL_PREFIXES = (
    "add_",
    "modify_",
    "search_",
    "send_",
    "set_",
)
BOUNDS_ONLY_OUTPUT_KEYS = frozenset(
    {
        "timestamp",
        "lower_bound",
        "upper_bound",
        "timestamp_lowerbound",
        "timestamp_upperbound",
        "creation_timestamp_lowerbound",
        "creation_timestamp_upperbound",
        "creation_timestamp_lower_bound",
        "creation_timestamp_upper_bound",
        "reminder_timestamp_lowerbound",
        "reminder_timestamp_upperbound",
        "reminder_timestamp_lower_bound",
        "reminder_timestamp_upper_bound",
    }
)


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    grading_classification: str = "unknown"


def grading_accounting_classification(spec: ToolSpec) -> str:
    """Classify whether a helper preserves or substitutes canonical route evidence."""
    if not feature_enabled(GRADING_ACCOUNTING):
        if (
            spec.family
            in {
                ToolFamily.STATE_PRECONDITION_HELPER,
                ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            }
            and not spec.preserves_side_effect_tools
        ):
            return "side_effect_unsafe"
        return "canonical_preserving"
    risk = spec.canonical_route_substitution_risk.strip().lower()
    replaces = bool(spec.expected_milestone_calls_replaced)
    has_final_state_plan = len(spec.final_state_preservation_plan.strip()) >= 20
    side_effect_family = spec.family in {
        ToolFamily.STATE_PRECONDITION_HELPER,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    }
    if side_effect_family and not spec.preserves_side_effect_tools:
        return "side_effect_unsafe"
    if (risk and risk != "none") or replaces:
        if has_final_state_plan:
            return "outcome_preserving_but_canonical_substituting"
        return "true_task_risky"
    return "canonical_preserving"


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


def _has_decisive_metadata(spec: ToolSpec) -> bool:
    return (
        spec.estimated_step_compression is not None
        or spec.cross_task_applicability_count is not None
        or bool(spec.applicable_task_families)
        or bool(spec.reason_tool_is_decisive.strip())
    )


def _has_downstream_original_tool_call(spec: ToolSpec) -> bool:
    return any(
        tool_name.startswith(DOWNSTREAM_TOOL_PREFIXES)
        for tool_name in spec.required_original_tool_calls
    )


def _is_bounds_only_derived_helper(spec: ToolSpec) -> bool:
    if spec.family != ToolFamily.DERIVED_VALUE_CALCULATOR:
        return False
    props = set(_output_schema_properties(spec))
    if not props:
        return False
    if {
        "search_kwargs",
        "target_tool_name",
        "selected_record",
        "add_reminder_kwargs",
    } & props:
        return False
    normalized = {key.lower() for key in props}
    return normalized.issubset(BOUNDS_ONLY_OUTPUT_KEYS)


def evaluate_candidate_gate(
    spec: ToolSpec,
    *,
    failure_memory_path: Path | None = None,
) -> GateDecision:
    grading_classification = grading_accounting_classification(spec)
    if spec.family not in ALLOWED_FAMILIES:
        return GateDecision(
            False, f"unsupported_family:{spec.family}", grading_classification
        )
    risk = spec.canonical_route_substitution_risk.strip().lower()
    if feature_enabled(GRADING_ACCOUNTING):
        if risk not in CANONICAL_SUBSTITUTION_RISK_LEVELS:
            return GateDecision(
                False,
                "invalid_canonical_route_substitution_risk",
                grading_classification,
            )
        if risk != "none" and not spec.grading_accounting_note.strip():
            return GateDecision(
                False,
                "missing_grading_accounting_note",
                grading_classification,
            )
        if (
            spec.expected_milestone_calls_replaced
            and not spec.final_state_preservation_plan.strip()
        ):
            return GateDecision(
                False,
                "missing_final_state_preservation_plan",
                grading_classification,
            )
    if not spec.inputs:
        return GateDecision(False, "missing_inputs", grading_classification)
    if len(spec.generalization_rationale.strip()) < 20:
        return GateDecision(
            False, "weak_generalization_rationale", grading_classification
        )
    evidence = coerce_inadequacy_evidence(spec.inadequacy_evidence)
    if len(evidence.summary.strip()) < 20:
        return GateDecision(False, "weak_inadequacy_evidence", grading_classification)
    if not evidence.signals:
        return GateDecision(
            False, "missing_structured_inadequacy_signals", grading_classification
        )
    if (
        spec.output_annotation == "dict"
        and _requires_output_schema(spec)
        and spec.output_schema is None
    ):
        return GateDecision(False, "missing_output_schema", grading_classification)
    if (
        _requires_negative_applicability(spec)
        and not spec.negative_triggers
        and "insufficient_information" not in spec.abstain_behavior.lower()
    ):
        return GateDecision(False, "missing_negative_triggers", grading_classification)
    if _has_decisive_metadata(spec):
        if spec.estimated_step_compression is None:
            return GateDecision(
                False, "missing_estimated_step_compression", grading_classification
            )
        if spec.estimated_step_compression < 3:
            return GateDecision(
                False, "step_compression_below_3", grading_classification
            )
        if spec.cross_task_applicability_count is None:
            return GateDecision(
                False, "missing_cross_task_applicability_count", grading_classification
            )
        if spec.cross_task_applicability_count < 2:
            return GateDecision(
                False, "cross_task_applicability_below_2", grading_classification
            )
        if len(spec.applicable_task_families) < 2:
            return GateDecision(
                False, "insufficient_applicable_task_families", grading_classification
            )
        if any(
            family.strip().lower() in GENERIC_TASK_FAMILY_LABELS
            for family in spec.applicable_task_families
        ):
            return GateDecision(
                False, "generic_applicable_task_family", grading_classification
            )
        if not spec.positive_triggers:
            return GateDecision(
                False, "missing_decisive_positive_triggers", grading_classification
            )
        if not spec.negative_triggers:
            return GateDecision(
                False, "missing_decisive_negative_triggers", grading_classification
            )
        if spec.output_annotation == "dict" and spec.output_schema is None:
            return GateDecision(
                False, "missing_decisive_output_schema", grading_classification
            )
        if len(spec.reason_tool_is_decisive.strip()) < 20:
            return GateDecision(
                False, "weak_decisive_rationale", grading_classification
            )
        if not spec.diagnostic_only and not spec.shortfall_cluster_evidence:
            return GateDecision(
                False, "missing_shortfall_cluster_evidence", grading_classification
            )
        if not spec.known_failure_mechanisms_addressed:
            return GateDecision(
                False, "missing_known_failure_mechanisms", grading_classification
            )
        memory_reasons = gate_failure_memory_reasons(
            failure_memory_path,
            tool_name=spec.tool_name,
            mechanisms=spec.known_failure_mechanisms_addressed,
            diagnostic_only=spec.diagnostic_only,
            repair_rationale=" ".join(
                [
                    spec.description,
                    spec.abstain_behavior,
                    spec.reason_tool_is_decisive,
                    spec.generalization_rationale,
                    *spec.positive_triggers,
                    *spec.negative_triggers,
                    *spec.shortfall_cluster_evidence,
                    *spec.known_failure_mechanisms_addressed,
                ]
            ),
        )
        if memory_reasons:
            return GateDecision(False, memory_reasons[0], grading_classification)
        decisive_text = " ".join(
            [
                spec.description,
                spec.generalization_rationale,
                spec.reason_tool_is_decisive,
            ]
        ).lower()
        if any(
            phrase in decisive_text for phrase in SINGLE_BASE_TOOL_REPLACEMENT_PHRASES
        ):
            return GateDecision(
                False, "single_base_tool_replacement", grading_classification
            )
        if not (spec.preserves_side_effect_tools or spec.required_original_tool_calls):
            if (
                grading_classification
                != "outcome_preserving_but_canonical_substituting"
            ):
                return GateDecision(
                    False,
                    "missing_downstream_tool_preservation",
                    grading_classification,
                )
        if spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR and not (
            spec.preserves_side_effect_tools or _has_downstream_original_tool_call(spec)
        ):
            if (
                grading_classification
                != "outcome_preserving_but_canonical_substituting"
            ):
                return GateDecision(
                    False,
                    "missing_downstream_original_tool_call",
                    grading_classification,
                )
        if _is_bounds_only_derived_helper(spec):
            return GateDecision(
                False,
                "bounds_only_derived_helper_low_value",
                grading_classification,
            )
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        if any(item.annotation == "dict" for item in spec.inputs):
            return GateDecision(
                False,
                "state_helper_opaque_dict_input_contract",
                grading_classification,
            )
        text = " ".join(
            [
                spec.tool_name,
                spec.description,
                spec.output_annotation,
                *(item.name for item in spec.inputs),
            ]
        ).lower()
        if not any(token in text for token in STATE_ACTIONABLE_TOKENS):
            return GateDecision(
                False, "state_helper_not_runtime_actionable", grading_classification
            )
        props = _output_schema_properties(spec)
        required = {"tool_name", "arguments", "should_call", "reason"}
        if not required.issubset(props):
            return GateDecision(
                False, "state_helper_missing_output_contract", grading_classification
            )
        tool_name_schema = props.get("tool_name")
        if not isinstance(tool_name_schema, dict):
            return GateDecision(
                False, "state_helper_tool_name_enum_invalid", grading_classification
            )
        enum_values = {str(item) for item in tool_name_schema.get("enum", ())}
        if "" not in enum_values or not all(
            item == "" or item.startswith(("set_", "enable_", "disable_"))
            for item in enum_values
        ):
            return GateDecision(
                False, "state_helper_tool_name_enum_invalid", grading_classification
            )
        emitted_tool_names = set(tool_name_schema.get("enum", ())) - {""}
        if not spec.preserves_side_effect_tools:
            return GateDecision(
                False,
                "state_helper_missing_preserved_tool_contract",
                grading_classification,
            )
        if not set(spec.required_original_tool_calls).issubset(
            set(spec.preserves_side_effect_tools)
        ):
            return GateDecision(
                False,
                "state_helper_required_calls_not_preserved",
                grading_classification,
            )
        if not emitted_tool_names.issubset(set(spec.preserves_side_effect_tools)):
            return GateDecision(
                False,
                "state_helper_emitted_tools_not_preserved",
                grading_classification,
            )
        if not emitted_tool_names.issubset(set(spec.required_original_tool_calls)):
            return GateDecision(
                False, "state_helper_emitted_tools_not_required", grading_classification
            )
    if spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        text = " ".join([spec.tool_name, spec.description]).lower()
        if not any(token in text for token in SEARCH_FILTER_ACTIONABLE_TOKENS):
            return GateDecision(
                False, "search_filter_not_runtime_actionable", grading_classification
            )
        input_names = _input_names(spec)
        if not (
            {"records", "candidates"} & input_names
            or "records_payload" in input_names
            or "candidates_payload" in input_names
        ):
            return GateDecision(
                False, "search_filter_missing_candidate_inputs", grading_classification
            )
        props = _output_schema_properties(spec)
        if not (
            {"selected_record", "selected_id"} & set(props) or spec.abstain_behavior
        ):
            return GateDecision(
                False, "search_filter_missing_output_contract", grading_classification
            )
        ambiguity_text = " ".join(
            [
                spec.description,
                spec.abstain_behavior,
                *spec.negative_triggers,
            ]
        ).lower()
        if not any(
            token in ambiguity_text
            for token in ("tie", "ambigu", "multiple match", "multiple-match")
        ):
            return GateDecision(
                False, "search_filter_missing_tie_behavior", grading_classification
            )
    if spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        if not spec.preserves_side_effect_tools:
            return GateDecision(
                False,
                "composite_helper_missing_preserved_side_effects",
                grading_classification,
            )
        if not spec.required_original_tool_calls:
            return GateDecision(
                False,
                "composite_helper_missing_required_original_calls",
                grading_classification,
            )
        props = _output_schema_properties(spec)
        if not any(str(key).endswith("_kwargs") for key in props):
            return GateDecision(
                False,
                "composite_helper_missing_prepared_kwargs_output",
                grading_classification,
            )
    return GateDecision(True, "allowed", grading_classification)
