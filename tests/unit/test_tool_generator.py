import json
from dataclasses import dataclass

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.adequacy.inadequacy_classifier import (
    _temperature_answer_extraction_observation,
)
from sage_ts.generation.tool_generator import (
    MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL,
    ToolGenerationRequest,
    ToolGenerator,
    _model_authored_contract_rules,
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


def test_tool_generator_authors_each_tool_fresh() -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer)
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
    assert completer.calls == 2


def test_contract_analysis_is_memoized_only_within_generator_instance(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sage_ts.generation.tool_generator._request_complete_tools_enabled",
        lambda _request: True,
    )
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer)
    request = ToolGenerationRequest(
        scenario_name="visible_contract",
        observation="Map visible values to one validated action.",
        allowed_families=("composite_workflow_helper",),
    )

    generator._contract_analysis_suffix(request)
    generator._contract_analysis_suffix(request)

    assert completer.calls == 1

    second_generator = ToolGenerator(completer=completer)
    second_generator._contract_analysis_suffix(request)

    assert completer.calls == 2


def test_repair_analysis_is_memoized_only_within_generator_instance(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sage_ts.generation.tool_generator._request_complete_tools_enabled",
        lambda _request: True,
    )
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer)
    request = ToolGenerationRequest(
        scenario_name="visible_repair_contract",
        observation="Repair a rejected deterministic normalization helper.",
        allowed_families=("canonicalizer",),
    )
    rejected_tool = generator.generate(request)
    calls_before_repair_analysis = completer.calls
    errors = ("validation example 1 did not match",)

    generator._repair_analysis_suffix(request, rejected_tool, errors)
    generator._repair_analysis_suffix(request, rejected_tool, errors)

    assert completer.calls == calls_before_repair_analysis + 1

    second_generator = ToolGenerator(completer=completer)
    second_generator._repair_analysis_suffix(request, rejected_tool, errors)

    assert completer.calls == calls_before_repair_analysis + 2


def test_generation_request_includes_reusable_name_hint() -> None:
    request = ToolGenerationRequest(
        scenario_name="find_temperature_f_with_location_alt",
        observation="Repeated Celsius to Fahrenheit conversion is needed.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="celsius_to_fahrenheit",
    )

    assert 'tool_name must be exactly "celsius_to_fahrenheit"' in request.prompt()


def test_temperature_generation_contract_finishes_visible_conversion() -> None:
    observation = _temperature_answer_extraction_observation("visible_task_context")
    first = observation.validation_examples[0]

    assert observation.failed_tool_calls == ("search_weather_around_lat_lon",)
    assert first.inputs["requested_metric"] == "current"
    assert first.expected["answer_value"] == "70.7"
    assert first.expected["answer_unit"] == "Fahrenheit"
    assert first.expected["should_call_downstream_tool"] is False
    assert first.expected["downstream_tool_name"] == ""
    assert first.expected["copy_exactly"] is True
    low_case = next(
        example
        for example in observation.validation_examples
        if example.inputs.get("requested_metric") == "min"
    )
    assert low_case.inputs["service_payload"]["result"] == 15.1
    assert low_case.inputs["service_payload"]["current_temperature"] == 15.1
    assert low_case.inputs["service_payload"]["min_temperature"] == 8.9
    assert low_case.expected["answer_value"] == "48.02"
    assert low_case.expected["exact_final_answer"].startswith("The min temperature")


def test_temperature_model_guidance_rejects_nonterminal_conversion_handoff() -> None:
    request = ToolGenerationRequest(
        scenario_name="visible_task_context",
        observation="Extract the requested visible weather value.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="extract_temperature_result",
    )

    guidance = " ".join(_model_authored_contract_rules(request))

    assert MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL[
        "extract_temperature_result"
    ] == ("search_weather_around_lat_lon",)
    assert "Do not return a downstream handoff to unit_conversion" in guidance
    assert "Never silently use current_temperature" in guidance
    assert "public validation examples as the canonical interface values" in guidance
    assert "without discarding richer named fields" in guidance


def test_device_sequence_guidance_uses_visible_contract_not_scenario_name() -> None:
    direct = ToolGenerationRequest(
        scenario_name="direct_device_state_action_hidden_label",
        observation="Plan native setter calls from visible inputs.",
        allowed_families=("state_precondition_helper",),
        suggested_tool_name="plan_device_state_action_sequence_v3",
    )
    downstream = ToolGenerationRequest(
        scenario_name="unrelated_hidden_label",
        observation="Plan native setter calls from visible inputs.",
        allowed_families=("state_precondition_helper",),
        suggested_tool_name="plan_device_state_action_sequence_v3",
    )

    direct_rules = _model_authored_contract_rules(direct)
    downstream_rules = _model_authored_contract_rules(downstream)
    guidance = " ".join(direct_rules)

    assert direct_rules == downstream_rules
    assert "scenario names" in guidance
    assert "public validation examples as binding" in guidance
    assert "complete minimal action_sequence" in guidance
    assert "target_service" in guidance
    assert "one recovery action" not in guidance


def test_add_contact_contract_parses_to_my_contact_phone_phrase() -> None:
    generator = ToolGenerator(completer=FakeCompleter())
    request = ToolGenerationRequest(
        scenario_name="add_contact_with_name_and_phone_number_10_distraction_tools",
        observation="Prepare add_contact arguments from visible name and phone.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_add_contact_args",
    )

    tool = generator.generate(request)

    validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": (
                        "Add Stephen Sondheim to my contact, his phone_number is "
                        "+19876543210"
                    )
                },
                {
                    "add_contact_kwargs": {
                        "name": "Stephen Sondheim",
                        "phone_number": "+19876543210",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Stephen Sondheim",
                        "phone_number": "+19876543210",
                    },
                    "normalized_phone_number": "+19876543210",
                    "abstain_reason": "",
                },
            ),
        ),
    )


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


def test_generation_request_includes_family_contract_guidance() -> None:
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


def test_generation_request_requires_contract_fields() -> None:
    request = ToolGenerationRequest(
        scenario_name="search_message_with_recency_latest",
        observation="Repeated shortfalls cluster around latest-record selection.",
        allowed_families=("search_filter_ranking_helper",),
    )
    prompt = request.prompt()

    assert "diagnostic_only" in prompt
    assert "shortfall_cluster_evidence" in prompt
    assert "known_failure_mechanisms_addressed" in prompt
    assert "canonical_route_substitution_risk" not in prompt
    assert "final_state_preservation_plan" not in prompt


def test_generation_request_includes_medium_grain_guidance() -> None:
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
