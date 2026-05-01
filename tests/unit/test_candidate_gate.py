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
        required_original_tool_calls=("set_wifi_status",),
        abstain_behavior="Return should_call false for insufficient information or already-enabled states.",
        generalization_rationale=(
            "State dependency scenarios repeatedly need deterministic handling of "
            "service readiness before the benchmark action can succeed."
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
