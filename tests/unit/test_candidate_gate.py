from dataclasses import replace

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
