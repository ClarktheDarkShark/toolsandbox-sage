# mypy: ignore-errors
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.promotion_gate import evaluate_promotion_entry
from sage_ts.validation.sandbox_validator import ValidationResult


def _entry(*, diagnostic_only: bool = False) -> RegistryEntry:
    spec = ToolSpec(
        tool_name="select_visible_record",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select a visible candidate record with deterministic tie abstention.",
        inputs=(ToolInput("records", "list", "Visible records."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {"selected_record": {"type": "object"}},
        },
        positive_triggers=("visible_candidate_selection",),
        negative_triggers=("no_candidates", "ambiguous_tie"),
        preserves_side_effect_tools=("modify_contact",),
        required_original_tool_calls=("modify_contact",),
        abstain_behavior="Return {} when candidates are absent or tie/ambiguity is present.",
        generalization_rationale="Visible record selection recurs across contact and message update tasks.",
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_update", "message_lookup"),
        reason_tool_is_decisive="It compresses search result inspection, constraint matching, and downstream side-effect argument selection.",
        diagnostic_only=diagnostic_only,
        shortfall_cluster_evidence=("visible_record_selection_failures",),
        known_failure_mechanisms_addressed=("wrong_visible_record_selected",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly choose the wrong visible candidate record.",
            signals=("wrong_selection",),
        ),
    )
    tool = GeneratedTool(
        spec=spec,
        code="def select_visible_record(records: list) -> dict:\n    return records[0] if records else {}\n",
    )
    return RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="seed",
    )


def _summary(outcome_delta: float = 0.2, called_count: int = 2) -> dict:
    return {
        "helpers": {
            "select_visible_record": {
                "called_count": called_count,
                "visible_count": 3,
                "visible_not_called_count": 1,
                "called_subset": {"mean_outcome_delta": outcome_delta},
                "side_effect_incidents": [],
                "runtime_incidents": [],
            }
        }
    }


def _derived_entry_with_prerequisites() -> RegistryEntry:
    spec = ToolSpec(
        tool_name="days_between_timestamps",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Compute deterministic elapsed days between two visible timestamps.",
        inputs=(
            ToolInput("timestamp_0", "float", "Start timestamp."),
            ToolInput("timestamp_1", "float", "End timestamp."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {"days": {"type": "integer"}},
        },
        positive_triggers=("day distance between known timestamps",),
        negative_triggers=("missing timestamp",),
        preserves_side_effect_tools=(),
        required_original_tool_calls=("get_current_timestamp", "search_holiday"),
        abstain_behavior="Return {} when either timestamp is unavailable.",
        generalization_rationale="Elapsed-day calculation recurs across holiday and deadline tasks.",
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("holiday_distance", "deadline_distance"),
        reason_tool_is_decisive="It compresses repeated timestamp arithmetic after prerequisite lookup tools.",
        shortfall_cluster_evidence=("derived_value:days_between_timestamps",),
        known_failure_mechanisms_addressed=(
            "visible_raw_data_lacking_deterministic_transform",
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly need deterministic day arithmetic after timestamp lookup.",
            signals=("deterministic_transform_missing",),
        ),
    )
    tool = GeneratedTool(
        spec=spec,
        code="def days_between_timestamps(timestamp_0: float, timestamp_1: float) -> dict:\n    return {'days': int((timestamp_1 - timestamp_0) // 86400)}\n",
    )
    return RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="seed",
    )


def _derived_summary() -> dict:
    return {
        "helpers": {
            "days_between_timestamps": {
                "called_count": 2,
                "visible_count": 2,
                "visible_not_called_count": 0,
                "called_subset": {"mean_outcome_delta": 0.1},
                "side_effect_incidents": [],
                "runtime_incidents": [],
            }
        }
    }


def test_promotion_gate_allows_claim_safe_called_positive_tool() -> None:
    decision = evaluate_promotion_entry(_entry(), _summary())

    assert decision.allowed
    assert decision.decision == "promote"


def test_promotion_gate_parks_accepted_but_uncalled_tool() -> None:
    decision = evaluate_promotion_entry(_entry(), _summary(called_count=0))

    assert not decision.allowed
    assert "no_later_task_calls" in decision.reasons


def test_promotion_gate_parks_harmful_called_subset() -> None:
    decision = evaluate_promotion_entry(_entry(), _summary(outcome_delta=-0.1))

    assert not decision.allowed
    assert "negative_called_subset_outcome_delta" in decision.reasons


def test_promotion_gate_parks_diagnostic_only_without_later_evidence() -> None:
    decision = evaluate_promotion_entry(_entry(diagnostic_only=True), _summary())

    assert not decision.allowed
    assert "diagnostic_only_without_later_non_diagnostic_evidence" in decision.reasons


def test_promotion_gate_allows_prerequisite_original_calls_without_side_effect_contract() -> (
    None
):
    decision = evaluate_promotion_entry(
        _derived_entry_with_prerequisites(), _derived_summary()
    )

    assert decision.allowed
    assert "missing_downstream_side_effect_preservation" not in decision.reasons
