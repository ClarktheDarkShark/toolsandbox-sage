# mypy: ignore-errors
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.validation.live_candidate_check import run_lightweight_live_candidate_check
from sage_ts.validation.sandbox_validator import ToolExample


def _tool(
    *, missing_grading_note: bool = False, missing_expected_milestones: bool = False
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="pick_value",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Pick a deterministic visible value and abstain when missing.",
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
        positive_triggers=("visible_value",),
        negative_triggers=("missing_value",),
        generalization_rationale="Visible value picking recurs across lookup tasks.",
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("message_lookup", "contact_lookup"),
        reason_tool_is_decisive=(
            "It compresses visible record inspection, value extraction, and "
            "answer preparation."
        ),
        shortfall_cluster_evidence=("visible_value_failures",),
        known_failure_mechanisms_addressed=("wrong_visible_value",),
        canonical_route_substitution_risk="medium",
        expected_milestone_calls_replaced=()
        if missing_expected_milestones
        else ("manual_value_extraction",),
        final_state_preservation_plan=(
            "The helper only returns a deterministic visible value; final answer "
            "or side-effect completion remains with the caller."
        ),
        grading_accounting_note=""
        if missing_grading_note
        else "Canonical route evidence may differ and must be reported separately.",
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly extract the wrong visible value.",
            signals=("wrong_visible_value",),
        ),
    )
    code = (
        "def pick_value(value: str) -> dict:\n"
        "    if not value:\n"
        "        return {}\n"
        "    return {'value': value.strip()}\n"
    )
    return GeneratedTool(spec=spec, code=code)


def test_live_candidate_check_accepts_positive_and_negative_examples(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "grading_accounting")
    result = run_lightweight_live_candidate_check(
        _tool(),
        (
            ToolExample({"value": " Ada "}, {"value": "Ada"}),
            ToolExample({"value": ""}, {}, negative_applicability=True),
        ),
    )

    assert result.accepted
    assert result.positive_usable_count == 1
    assert result.negative_abstain_count == 1
    assert (
        result.grading_classification == "outcome_preserving_but_canonical_substituting"
    )


def test_live_candidate_check_requires_substitution_accounting() -> None:
    result = run_lightweight_live_candidate_check(
        _tool(missing_grading_note=True),
        (ToolExample({"value": "Ada"}, {"value": "Ada"}),),
    )

    assert not result.accepted
    assert "live_missing_grading_accounting_note" in result.errors


def test_live_candidate_check_warns_when_milestone_list_missing_but_accounted(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "grading_accounting")
    result = run_lightweight_live_candidate_check(
        _tool(missing_expected_milestones=True),
        (ToolExample({"value": "Ada"}, {"value": "Ada"}),),
    )

    assert result.accepted
    assert "live_missing_expected_milestone_calls_replaced" in result.warnings
    assert "live_missing_expected_milestone_calls_replaced" not in result.errors


def test_live_candidate_check_rejects_positive_composite_abstention() -> None:
    spec = ToolSpec(
        tool_name="constraint_to_action_planner",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description="Select a visible record and prepare safe downstream kwargs.",
        inputs=(
            ToolInput("records", "list", "Visible records."),
            ToolInput("match_field", "str", "Field to match."),
            ToolInput("match_value", "str", "Value to match."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "selected_id": {"type": "string"},
                "selected_index": {"type": "integer"},
                "value": {"type": "string"},
                "downstream_tool_name": {"type": "string"},
                "downstream_tool_kwargs": {"type": "object"},
                "should_call_tool": {"type": "boolean"},
                "tie_candidates": {"type": "array"},
                "abstain_reason": {"type": "string"},
                "safety_notes": {"type": "string"},
            },
        },
        positive_triggers=("visible records need safe constraint-to-action planning",),
        negative_triggers=("no match", "ambiguous match"),
        preserves_side_effect_tools=("remove_contact",),
        required_original_tool_calls=("remove_contact",),
        abstain_behavior="Abstain on no match or ambiguity.",
        generalization_rationale="Visible record action planning recurs across tasks.",
        estimated_step_compression=4,
        cross_task_applicability_count=2,
        applicable_task_families=("remove_contact_by_phone", "modify_contact_by_name"),
        reason_tool_is_decisive=(
            "It combines selection, ambiguity handling, and downstream argument prep."
        ),
        shortfall_cluster_evidence=("composite:constraint_to_action_planner",),
        known_failure_mechanisms_addressed=("visible_info_unused",),
        final_state_preservation_plan="Caller still executes original side-effect tools.",
        grading_accounting_note="Route changes are reported separately.",
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents fail to use visible records for safe actions.",
            signals=("visible_info_unused",),
        ),
    )
    tool = GeneratedTool(
        spec=spec,
        code=(
            "def constraint_to_action_planner(records: list, match_field: str, "
            "match_value: str) -> dict:\n"
            "    return {'selected_record': {}, 'selected_id': '', "
            "'selected_index': -1, 'value': '', 'downstream_tool_name': '', "
            "'downstream_tool_kwargs': {}, 'should_call_tool': False, "
            "'tie_candidates': [], 'abstain_reason': 'no match found', "
            "'safety_notes': ''}\n"
        ),
    )

    result = run_lightweight_live_candidate_check(
        tool,
        (
            ToolExample(
                {
                    "records": [{"person_id": "p1", "phone_number": "+1 555 0100"}],
                    "match_field": "phone_number",
                    "match_value": "15550100",
                },
                {},
            ),
        ),
    )

    assert not result.accepted
    assert "live_example_0_positive_unusable_output" in result.errors
