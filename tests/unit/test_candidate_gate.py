import json
from dataclasses import replace
from pathlib import Path

import pytest

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import (
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)


def _state_spec(description: str) -> ToolSpec:
    return ToolSpec(
        tool_name="state_helper",
        family=ToolFamily(str(ToolFamily.STATE_PRECONDITION_HELPER)),
        description=description,
        inputs=(ToolInput("target_service", "str", "Requested service."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": [
                        "",
                        "set_wifi_status",
                        "set_cellular_service_status",
                        "set_location_service_status",
                        "set_low_battery_mode_status",
                    ],
                },
                "arguments": {"type": "object"},
                "should_call": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
        positive_triggers=("service_precondition_failure",),
        negative_triggers=("insufficient_information",),
        preserves_side_effect_tools=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        required_original_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        abstain_behavior="Return should_call false for insufficient information or already-enabled states.",
        generalization_rationale=(
            "State dependency scenarios repeatedly need deterministic handling of "
            "service readiness before the benchmark action can succeed."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("service_preconditions", "location_preconditions"),
        reason_tool_is_decisive=(
            "It compresses device-state inspection, tool choice, and argument "
            "preparation while preserving the original setter call."
        ),
        shortfall_cluster_evidence=("service_precondition_failures",),
        known_failure_mechanisms_addressed=(
            "advisory_text_instead_of_tool_call",
            "wrong_service_order",
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Base tools expose raw setters/getters but not a reusable intermediate "
                "readiness decision for repeated service precondition failures."
            ),
            signals=("failed_base_tool_with_deterministic_fallback",),
        ),
    )


def test_state_precondition_helper_must_be_runtime_actionable() -> None:
    decision = evaluate_candidate_gate(
        _state_spec("Return a descriptive ordered plan with steps.")
    )

    assert not decision.allowed
    assert decision.reason == "state_helper_not_runtime_actionable"


def test_state_precondition_helper_allows_next_action_micro_helper() -> None:
    decision = evaluate_candidate_gate(
        _state_spec("Return a concrete next_action and readiness predicate.")
    )

    assert decision.allowed


def test_state_precondition_helper_allows_trace_compatible_tool_call() -> None:
    spec = replace(
        _state_spec("Return the exact ToolSandbox setter name and arguments."),
        tool_name="next_service_tool_call",
    )

    decision = evaluate_candidate_gate(spec)

    assert decision.allowed


def test_state_precondition_helper_rejects_opaque_dict_input_contract() -> None:
    spec = replace(
        _state_spec("Return the exact ToolSandbox setter name and arguments."),
        inputs=(
            ToolInput(
                "dependency_state",
                "dict",
                "Opaque service readiness and blocker state.",
            ),
            ToolInput("target_action", "str", "Downstream action."),
            ToolInput("blocked_reason", "str", "Observed blocking reason."),
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "state_helper_opaque_dict_input_contract"


def test_search_helper_can_substitute_canonical_route_with_grading_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "grading_accounting")
    spec = ToolSpec(
        tool_name="select_visible_record",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select a visible candidate record by timestamp; tie cases abstain "
            "instead of manual timestamp comparison."
        ),
        inputs=(ToolInput("records", "list", "Visible records."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {"selected_record": {"type": "object"}},
        },
        positive_triggers=("visible_candidate_selection",),
        negative_triggers=("no_candidates", "ambiguous_tie"),
        abstain_behavior="Return {} when no candidates or a tie/ambiguity exists.",
        generalization_rationale=(
            "Visible record selection recurs across answer and update tasks."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("message_lookup", "reminder_lookup"),
        reason_tool_is_decisive=(
            "It compresses search result inspection, timestamp comparison, and "
            "record choice across families."
        ),
        shortfall_cluster_evidence=("visible_record_selection_failures",),
        known_failure_mechanisms_addressed=("wrong_visible_record_selected",),
        canonical_route_substitution_risk="medium",
        expected_milestone_calls_replaced=("manual_record_ranking_trace",),
        final_state_preservation_plan=(
            "The helper only selects from visible records and leaves any final "
            "answer or downstream side-effect tool to the caller."
        ),
        grading_accounting_note=(
            "Canonical route evidence may differ, so report as outcome-preserving "
            "canonical substitution rather than canonical success."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly select the wrong visible candidate.",
            signals=("wrong_selected_record",),
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert decision.allowed
    assert (
        decision.grading_classification
        == "outcome_preserving_but_canonical_substituting"
    )


def test_search_filter_gate_accepts_ambiguity_abstention_without_literal_tie() -> None:
    spec = ToolSpec(
        tool_name="select_contact_field_by_constraint",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select exactly one visible contact and abstain on ambiguity.",
        inputs=(ToolInput("records", "list", "Visible contact records."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "value": {"type": "string"},
            },
        },
        positive_triggers=("contact_lookup_after_search_contacts",),
        negative_triggers=("no_candidates", "ambiguous_matches"),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts",),
        abstain_behavior="Return {} when no unique safe selection exists.",
        generalization_rationale=(
            "Contact lookup and update tasks repeatedly need deterministic "
            "visible-record field selection after search_contacts."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup", "contact_update"),
        reason_tool_is_decisive=(
            "It compresses candidate inspection, constraint matching, and output "
            "field extraction while preserving original search/update calls."
        ),
        shortfall_cluster_evidence=(
            "search_filter:select_contact_field_by_constraint",
        ),
        known_failure_mechanisms_addressed=("search_filter_missing_tie_behavior",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly choose the wrong visible contact candidate.",
            signals=("wrong_selected_record",),
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert decision.allowed


def test_decisive_gate_rejects_thin_helper() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        estimated_step_compression=1,
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "step_compression_below_3"


def test_legacy_spec_without_decisive_metadata_still_passes_existing_gate() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        estimated_step_compression=None,
        cross_task_applicability_count=None,
        applicable_task_families=(),
        reason_tool_is_decisive="",
    )

    decision = evaluate_candidate_gate(spec)

    assert decision.allowed


def test_decisive_gate_rejects_generic_applicable_family_label() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        applicable_task_families=("state_precondition_helper", "service_tasks"),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "generic_applicable_task_family"


def test_decisive_gate_rejects_missing_negative_triggers() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        negative_triggers=(),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "missing_negative_triggers"


def test_decisive_gate_rejects_missing_positive_triggers() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        positive_triggers=(),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "missing_decisive_positive_triggers"


def test_decisive_gate_rejects_missing_shortfall_cluster_evidence() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        shortfall_cluster_evidence=(),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "missing_shortfall_cluster_evidence"


def test_diagnostic_decisive_spec_can_lack_shortfall_cluster_evidence() -> None:
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        diagnostic_only=True,
        shortfall_cluster_evidence=(),
    )

    decision = evaluate_candidate_gate(spec)

    assert decision.allowed


def test_state_precondition_helper_must_preserve_all_emitted_setters() -> None:
    spec = replace(
        _state_spec("Return the exact ToolSandbox setter name and arguments."),
        preserves_side_effect_tools=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
        ),
        required_original_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "state_helper_emitted_tools_not_preserved"


def test_decisive_gate_rejects_timestamp_only_derived_helper() -> None:
    spec = ToolSpec(
        tool_name="thin_timestamp_bounds",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Convert a date phrase into timestamp bounds.",
        inputs=(ToolInput("phrase", "str", "Date phrase."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {"timestamp": {"type": "number"}},
        },
        positive_triggers=("date_phrase",),
        negative_triggers=("ambiguous_phrase",),
        required_original_tool_calls=("datetime_info_to_timestamp",),
        abstain_behavior="Return {} when the phrase is ambiguous.",
        generalization_rationale=(
            "Date phrases recur across tasks and can be converted deterministically."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("reminder_search", "message_search"),
        reason_tool_is_decisive=(
            "It compresses date parsing, timestamp conversion, and bounded argument setup."
        ),
        shortfall_cluster_evidence=("bounded_search_window_failures",),
        known_failure_mechanisms_addressed=("unsafe_or_empty_search_bounds",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly fail converting natural date phrases into safe bounds.",
            signals=("visible_raw_data_lacking_deterministic_transform",),
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "missing_downstream_original_tool_call"


def test_decisive_gate_rejects_bounds_only_search_helper_even_with_search_call() -> (
    None
):
    spec = ToolSpec(
        tool_name="generic_message_window",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Return timestamp lower and upper bounds before search.",
        inputs=(ToolInput("anchor_timestamp", "float", "Current timestamp."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "creation_timestamp_lowerbound": {"type": "number"},
                "creation_timestamp_upperbound": {"type": "number"},
            },
        },
        positive_triggers=("message_recency_search_needs_bounds",),
        negative_triggers=("ambiguous_recency",),
        preserves_side_effect_tools=("search_messages",),
        required_original_tool_calls=("search_messages",),
        abstain_behavior="Return {} when the recency phrase is ambiguous.",
        generalization_rationale=(
            "Message and contact recency tasks sometimes need bounded searches."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("message_lookup", "contact_update_after_message"),
        reason_tool_is_decisive=(
            "It compresses timestamp-bound setup before the original search call."
        ),
        shortfall_cluster_evidence=("message_recency_bounds_failures",),
        known_failure_mechanisms_addressed=("missing_message_search_bounds",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly issue message searches without criteria.",
            signals=("repeated_failed_tool_call",),
        ),
    )

    decision = evaluate_candidate_gate(spec)

    assert not decision.allowed
    assert decision.reason == "bounds_only_derived_helper_low_value"


def test_failure_memory_allows_tie_mechanism_when_spec_repairs_ambiguity(
    tmp_path: Path,
) -> None:
    memory = tmp_path / "failure_memory.json"
    memory.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "mechanism_id": "search_filter_missing_tie_behavior",
                        "candidate_name": "select_contact_field_by_constraint",
                        "failure_symptoms": ["missing tie behavior"],
                        "suspected_root_cause": "selector omitted tie abstention",
                        "status": "active_failure",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    spec = ToolSpec(
        tool_name="select_contact_field_by_constraint",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select exactly one visible contact; ambiguous matches and ties abstain."
        ),
        inputs=(ToolInput("records", "list", "Visible contact records."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "value": {"type": "string"},
            },
        },
        positive_triggers=("contact_lookup_after_search_contacts",),
        negative_triggers=("no_candidates", "ambiguous_tie", "missing_output_field"),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts",),
        abstain_behavior=(
            "Return {} when no candidates, no unique match, or a tie/ambiguity exists."
        ),
        generalization_rationale=(
            "Contact lookup and contact-update tasks repeatedly need deterministic "
            "visible-record field selection after search_contacts."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup", "contact_update"),
        reason_tool_is_decisive=(
            "It compresses candidate inspection, constraint matching, and output "
            "field extraction while explicitly abstaining on ambiguity."
        ),
        shortfall_cluster_evidence=(
            "search_filter:select_contact_field_by_constraint",
        ),
        known_failure_mechanisms_addressed=("search_filter_missing_tie_behavior",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly choose the wrong visible contact candidate.",
            signals=("wrong_selected_record",),
        ),
    )

    decision = evaluate_candidate_gate(spec, failure_memory_path=memory)

    assert decision.allowed


def test_failure_memory_keeps_visible_not_called_mechanism_blocked_without_adoption_repair(
    tmp_path: Path,
) -> None:
    memory = tmp_path / "failure_memory.json"
    memory.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "mechanism_id": "state_precondition_visible_not_called",
                        "candidate_name": "next_service_tool_call",
                        "failure_symptoms": ["visible but not called"],
                        "suspected_root_cause": "routing/adoption weakness",
                        "status": "active_failure",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    spec = replace(
        _state_spec("Return a concrete next_action and readiness predicate."),
        tool_name="next_service_tool_call",
        known_failure_mechanisms_addressed=("state_precondition_visible_not_called",),
    )

    decision = evaluate_candidate_gate(spec, failure_memory_path=memory)

    assert not decision.allowed
    assert (
        decision.reason
        == "unresolved_failure_memory:state_precondition_visible_not_called"
    )
