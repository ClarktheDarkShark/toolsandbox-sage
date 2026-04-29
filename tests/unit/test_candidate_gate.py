from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import ToolFamily, ToolInput, ToolSpec


def _state_spec(description: str) -> ToolSpec:
    return ToolSpec(
        tool_name="state_helper",
        family=ToolFamily(str(ToolFamily.STATE_PRECONDITION_HELPER)),
        description=description,
        inputs=(ToolInput("target_service", "str", "Requested service."),),
        output_annotation="dict",
        generalization_rationale=(
            "State dependency scenarios repeatedly need deterministic handling of "
            "service readiness before the benchmark action can succeed."
        ),
        inadequacy_evidence=(
            "Base tools expose raw setters/getters but not a reusable intermediate "
            "readiness decision for repeated service precondition failures."
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
