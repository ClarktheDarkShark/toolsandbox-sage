import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerationRequest, ToolGenerator
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


@dataclass
class FakeCompleter:
    model: str = "fake-model"
    calls: int = 0

    def complete(self, request: ChatRequest) -> str:
        self.calls += 1
        return json.dumps(
            {
                "spec": {
                    "tool_name": "normalize_label",
                    "family": "canonicalizer",
                    "description": "Normalize labels.",
                    "inputs": [
                        {
                            "name": "label",
                            "annotation": "str",
                            "description": "Raw label.",
                        }
                    ],
                    "output_annotation": "str",
                    "generalization_rationale": "Labels recur with superficial variants.",
                    "estimated_step_compression": 3,
                    "cross_task_applicability_count": 2,
                    "applicable_task_families": ["labels", "messages"],
                    "reason_tool_is_decisive": "It compresses normalization, comparison, and downstream argument preparation.",
                    "diagnostic_only": False,
                    "shortfall_cluster_evidence": ["label_normalization_failures"],
                    "known_failure_mechanisms_addressed": ["surface_form_mismatch"],
                    "canonical_route_substitution_risk": "low",
                    "expected_milestone_calls_replaced": ["manual_label_comparison"],
                    "final_state_preservation_plan": "The helper returns a normalized label only; the caller still completes the final answer or side effect.",
                    "grading_accounting_note": "Canonical intermediate route may differ, so report substitution separately from task outcome.",
                    "inadequacy_evidence": "Existing tools do not expose label normalization.",
                },
                "code": "def normalize_label(label: str) -> str:\n    return label.strip().lower()\n",
            }
        )


def test_tool_generator_uses_prompt_cache(tmp_path: Path) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="toy",
        observation="Need deterministic label normalization.",
        allowed_families=("canonicalizer",),
    )

    first = generator.generate(request)
    second = generator.generate(request)

    assert first.spec.tool_name == "normalize_label"
    assert first.spec.estimated_step_compression == 3
    assert first.spec.shortfall_cluster_evidence == ("label_normalization_failures",)
    assert first.spec.canonical_route_substitution_risk == "low"
    assert first.spec.expected_milestone_calls_replaced == ("manual_label_comparison",)
    assert second.spec.tool_name == "normalize_label"
    assert completer.calls == 1


def test_generation_request_includes_reusable_name_hint() -> None:
    request = ToolGenerationRequest(
        scenario_name="find_temperature_f_with_location_alt",
        observation="Repeated Celsius to Fahrenheit conversion is needed.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="celsius_to_fahrenheit",
    )

    assert 'tool_name must be exactly "celsius_to_fahrenheit"' in request.prompt()


def test_generation_request_preserves_negative_applicability_metadata() -> None:
    request = ToolGenerationRequest(
        scenario_name="find_stock_symbol_with_company_name",
        observation="Extract a stock symbol only when the payload contains one.",
        allowed_families=("derived_value_calculator",),
        validation_examples=(
            {
                "inputs": {"stock_payload": {"symbol": "NASDAQ:AAPL"}},
                "expected": "AAPL",
                "held_out": False,
                "negative_applicability": False,
            },
            {
                "inputs": {"stock_payload": {"name": "Apple"}},
                "expected": "",
                "held_out": False,
                "negative_applicability": True,
            },
        ),
    )

    prompt = request.prompt()

    assert '"negative_applicability": true' in prompt


def test_generation_request_includes_family_contract_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "dependency_logic")
    request = ToolGenerationRequest(
        scenario_name="search_phone_number_with_name",
        observation="Repeated contact selection failures.",
        allowed_families=("search_filter_ranking_helper", "state_precondition_helper"),
    )
    prompt = request.prompt()

    assert "If family is search_filter_ranking_helper" in prompt
    assert "selected_record" in prompt
    assert "Normalize BOTH sides before comparing" in prompt
    assert "raw formatted phone strings" in prompt
    assert "selected_index=-1" in prompt
    assert "tie_candidates containing ALL matching records" in prompt
    assert "downstream_tool_kwargs, should_call_tool" in prompt
    assert "do not use message_id as a contact id" in prompt
    assert "prefer low-friction call patterns" in prompt
    assert "autofill selected_record from the latest original search_*" in prompt
    assert "Normalize common action aliases" in prompt
    assert "If family is state_precondition_helper" in prompt
    assert "tool_name must have an enum" in prompt
    assert "must not require an opaque dict input" in prompt
    assert "tool_generation_v5" not in prompt


def test_generation_request_includes_exact_contact_phone_normalization() -> None:
    request = ToolGenerationRequest(
        scenario_name="remove_contact_by_phone",
        observation="Normalize a scalar contact phone constraint.",
        allowed_families=("composite_workflow_helper",),
    )
    prompt = request.prompt()

    assert "if there are 11 digits and the first digit is '1'" in prompt
    assert "Never prepend '+1' to an 11-digit US number" in prompt
    assert "preserve the original case and spacing" in prompt
    assert "should_call_search is false" in prompt


def test_generation_request_requires_v2_contract_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "grading_accounting")
    request = ToolGenerationRequest(
        scenario_name="search_message_with_recency_latest",
        observation="Repeated shortfalls cluster around latest-record selection.",
        allowed_families=("search_filter_ranking_helper",),
    )
    prompt = request.prompt()

    assert "diagnostic_only" in prompt
    assert "shortfall_cluster_evidence" in prompt
    assert "known_failure_mechanisms_addressed" in prompt
    assert "canonical_route_substitution_risk" in prompt
    assert "final_state_preservation_plan" in prompt


def test_generation_request_includes_medium_grain_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SAGE_V2_EXPERIMENT_FEATURES",
        "contract_synthesis,medium_grain_skills",
    )
    request = ToolGenerationRequest(
        scenario_name="remove_contact_by_phone",
        observation="Generate a constraint-to-action planner.",
        allowed_families=("composite_workflow_helper",),
    )
    prompt = request.prompt()

    assert "Medium-grain skill experiment guidance" in prompt
    assert "records: list, match_field: str" in prompt
    assert "Do not split this into a thin selector" in prompt


def test_generation_request_includes_failure_memory_and_cluster_context() -> None:
    request = ToolGenerationRequest(
        scenario_name="search_message_with_recency_latest",
        observation="Repeated shortfalls cluster around latest-record selection.",
        allowed_families=("search_filter_ranking_helper",),
        failure_memory_context={
            "unresolved_relevant_failures": [{"mechanism_id": "wrong_record_selected"}]
        },
        shortfall_cluster_context={
            "cluster_id": "search_filter:select_record_by_timestamp_extreme",
            "non_diagnostic_birth_allowed": True,
        },
    )
    prompt = request.prompt()

    assert "Relevant unresolved failure memory" in prompt
    assert "wrong_record_selected" in prompt
    assert "Shortfall cluster context" in prompt
    assert "non_diagnostic_birth_allowed" in prompt


def test_repair_prompt_includes_selector_and_action_alias_contract(
    tmp_path: Path,
) -> None:
    seen: list[str] = []

    class RepairCompleter(FakeCompleter):
        def complete(self, request: ChatRequest) -> str:
            seen.append(request.user)
            return super().complete(request)

    generator = ToolGenerator(
        completer=RepairCompleter(),
        cache=PromptCache(tmp_path),
    )
    request = ToolGenerationRequest(
        scenario_name="search_phone_number_with_name",
        observation="Ambiguous selector failed tie abstention.",
        allowed_families=("search_filter_ranking_helper",),
    )
    rejected = generator.generate(request)

    generator.repair(request, rejected, ("negative_0_mismatch",))

    assert any("selected_index=-1" in prompt for prompt in seen)
    assert any("remove/delete" in prompt for prompt in seen)
    assert any("Exact E.164 repair rule" in prompt for prompt in seen)
    assert any("search_kwargs must be {}" in prompt for prompt in seen)
    assert any(
        "prepare_reminder_creation_args failed validation" in prompt for prompt in seen
    )
    assert any(
        "optional_location_lookup_pending_do_not_call_add_reminder" in prompt
        for prompt in seen
    )


def test_reminder_repair_uses_deterministic_contract_fallback(tmp_path: Path) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="add_reminder_content_and_week_delta_and_time_and_location",
        observation="Reminder creation needs final add_reminder kwargs.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_reminder_creation_args",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_reminder_creation_args",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Rejected reminder helper.",
            inputs=(
                ToolInput("content", "str", "content"),
                ToolInput("resolved_reminder_timestamp", "float", "timestamp"),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {"add_reminder_kwargs": {}}},
            positive_triggers=("add_reminder",),
            negative_triggers=("missing_time_info",),
            preserves_side_effect_tools=("add_reminder",),
            required_original_tool_calls=("add_reminder",),
            abstain_behavior="Abstain when information is missing.",
            generalization_rationale="Reminder tasks need reusable argument prep.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "add_reminder_content_and_week_delta_and_time",
                "add_reminder_content_and_week_delta_and_time_and_location",
            ),
            reason_tool_is_decisive="It prepares final add_reminder arguments.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("bad_optional_location_contract",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Reminder helper had a repairable validation mismatch.",
                signals=("reminder_argument_prep",),
            ),
        ),
        code="def prepare_reminder_creation_args(content: str, resolved_reminder_timestamp: float) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(
        request,
        rejected,
        (
            "negative_1_mismatch:{'should_call_add_reminder': True}!={'should_call_add_reminder': False}",
        ),
    )

    assert completer.calls == 0
    assert repaired.spec.tool_name == "prepare_reminder_creation_args"
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "content": "Buy tickets",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Buy tickets",
                        "reminder_timestamp": 147600.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Team meeting",
                    "resolved_reminder_timestamp": 1777500000.0,
                    "current_timestamp": 1777428906.0,
                    "day_offset": 0,
                    "hour": 0,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Team meeting",
                        "reminder_timestamp": 1777500000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "resolved",
                },
            ),
            ToolExample(
                {
                    "content": "Meet at park",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 14,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": True,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "required_location_unresolved",
                    "location_status": "required_missing",
                    "timestamp_source": "relative_fields",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 1777687768.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": (
                        "optional_location_lookup_pending_do_not_call_add_reminder"
                    ),
                    "location_status": "lookup_pending",
                    "timestamp_source": "resolved",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_action_selector_repair_uses_final_action_ready_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="remove_reminder_with_recency_latest",
        observation="Need a recency action target selector.",
        allowed_families=("search_filter_ranking_helper",),
        suggested_tool_name="select_action_target_by_recency",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Rejected action selector.",
            inputs=(ToolInput("records", "list", "records"),),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_id": {"type": "string"},
                    "downstream_tool_name": {"type": "string"},
                },
            },
            positive_triggers=("remove_reminder_with_recency_latest",),
            negative_triggers=("ambiguous_tie",),
            preserves_side_effect_tools=("remove_reminder",),
            required_original_tool_calls=("search_reminder",),
            abstain_behavior="Abstain on ambiguity.",
            generalization_rationale="Recency action targeting recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("remove_reminder_with_recency_latest",),
            reason_tool_is_decisive="It selects the action target.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("visible_not_called_action_selector",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Selector lacked downstream kwargs.",
                signals=("visible_not_called",),
            ),
        ),
        code="def select_action_target_by_recency(records: list) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(
        request,
        rejected,
        ("action_selector_missing_downstream_kwargs_contract",),
    )

    assert completer.calls == 0
    assert repaired.spec.tool_name == "select_action_target_by_recency"
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "records": [
                        {"reminder_id": "old", "reminder_timestamp": 1.0},
                        {"reminder_id": "new", "reminder_timestamp": 2.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "remove_reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {
                        "reminder_id": "new",
                        "reminder_timestamp": 2.0,
                    },
                    "selected_index": 1,
                    "selected_id": "new",
                    "selected_timestamp": 2.0,
                    "action_type": "remove_reminder",
                    "downstream_tool_name": "remove_reminder",
                    "downstream_tool_kwargs": {"reminder_id": "new"},
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": (
                        "call downstream ToolSandbox side-effect with "
                        "downstream_tool_kwargs"
                    ),
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m2",
                            "sender_person_id": "p2",
                            "creation_timestamp": 50.0,
                        }
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_contact",
                    "constraints": {},
                    "updates": {"relationship": "friend"},
                },
                {
                    "selected_record": {
                        "message_id": "m2",
                        "sender_person_id": "p2",
                        "creation_timestamp": 50.0,
                    },
                    "selected_index": 0,
                    "selected_id": "p2",
                    "selected_timestamp": 50.0,
                    "action_type": "modify_contact",
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p2",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": (
                        "call downstream ToolSandbox side-effect with "
                        "downstream_tool_kwargs"
                    ),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"reminder_id": "a", "reminder_timestamp": 3.0},
                        {"reminder_id": "b", "reminder_timestamp": 3.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "remove_reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 3.0,
                    "action_type": "remove_reminder",
                    "downstream_tool_name": "remove_reminder",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [
                        {"reminder_id": "a", "reminder_timestamp": 3.0},
                        {"reminder_id": "b", "reminder_timestamp": 3.0},
                    ],
                    "abstain_reason": "ambiguous_timestamp_tie",
                    "safety_notes": "do not guess before side-effect action",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_constraint_selector_repair_abstains_on_ambiguous_matches(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="search_relationship_with_phone_number",
        observation="Need exact visible record selection.",
        allowed_families=("search_filter_ranking_helper",),
        suggested_tool_name="select_visible_record_by_constraints",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_visible_record_by_constraints",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Rejected constraint selector.",
            inputs=(ToolInput("records", "list", "records"),),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {"selected_record": {}}},
            positive_triggers=("search_relationship_with_phone_number",),
            negative_triggers=("ambiguous_matches",),
            preserves_side_effect_tools=("search_contacts",),
            required_original_tool_calls=("search_contacts",),
            abstain_behavior="Abstain on ambiguity.",
            generalization_rationale="Constraint selection recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("contact_lookup",),
            reason_tool_is_decisive="It avoids ambiguous selected records.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("ambiguous_constraint_match",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Selector retained first ambiguous match.",
                signals=("wrong_selected_record",),
            ),
        ),
        code="def select_visible_record_by_constraints(records: list) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(request, rejected, ("negative_0_mismatch",))

    assert completer.calls == 0
    assert repaired.spec.tool_name == "select_visible_record_by_constraints"
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "records": [
                        {"person_id": "p1", "phone_number": "+1 (555) 0100"},
                    ],
                    "field_name": "phone_number",
                    "expected_value": "15550100",
                    "return_field": "person_id",
                },
                {
                    "selected_record": {
                        "person_id": "p1",
                        "phone_number": "+1 (555) 0100",
                    },
                    "selected_index": 0,
                    "selected_id": "p1",
                    "value": "p1",
                    "matched_constraints": ["phone_number"],
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "p9", "name": "Ada Lovelace"},
                    ],
                    "field_name": "name",
                    "expected_value": "ada lovelace",
                    "return_field": "person_id",
                },
                {
                    "selected_record": {
                        "person_id": "p9",
                        "name": "Ada Lovelace",
                    },
                    "selected_index": 0,
                    "selected_id": "p9",
                    "value": "p9",
                    "matched_constraints": ["name"],
                    "tie_candidates": [],
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "p1", "relationship": "friend"},
                        {"person_id": "p2", "relationship": "friend"},
                    ],
                    "field_name": "relationship",
                    "expected_value": "friend",
                    "return_field": "person_id",
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "value": "",
                    "matched_constraints": ["relationship"],
                    "tie_candidates": [
                        {"person_id": "p1", "relationship": "friend"},
                        {"person_id": "p2", "relationship": "friend"},
                    ],
                    "abstain_reason": "ambiguous_multiple_matches",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors
