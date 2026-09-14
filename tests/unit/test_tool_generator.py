import ast
import json
from dataclasses import dataclass

import pytest

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.adequacy.inadequacy_classifier import (
    CapabilityObservation,
    _add_contact_argument_observation,
    _address_answer_extraction_observation,
    _broad_location_search_argument_observation,
    _contact_lookup_query_planner_observation,
    _device_status_lookup_observation,
    _distance_answer_extraction_observation,
    _external_service_answer_extraction_observation,
    _holiday_search_args_observation,
    _latest_record_selection_observation,
    _location_search_argument_observation,
    _message_counterparty_search_plan_observation,
    _plan_device_state_action_sequence_observation,
    _reminder_creation_finalizer_observation,
    _resolve_search_window_or_bounds_observation,
    _safe_action_or_abstain_observation,
    _stock_symbol_extraction_observation,
    _temperature_answer_extraction_observation,
)
from sage_ts.generation.tool_generator import (
    MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL,
    ToolGenerationRequest,
    ToolGenerator,
    _inputs_from_public_contract,
    _model_authored_contract_rules,
    _model_authored_final_repair_directive,
    _model_authored_generation_prompt,
    _model_authored_repair_prompt,
    _model_authored_validation_helper_repair_analysis_prompt,
    _normalize_model_authored_tool,
    _validated_validation_helper_contract_analysis,
    _validated_validation_helper_repair_analysis,
    public_input_contract_from_example_inputs,
    public_output_contract_from_example_outputs,
)
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.online_birth import _model_visible_generation_examples
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


def _serialized_model_visible_contract(
    observation: CapabilityObservation,
    *,
    suggested_tool_name: str,
) -> str:
    visible_examples = _model_visible_generation_examples(
        observation.validation_examples
    )
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_task_context",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": False,
                "negative_applicability": example.negative_applicability,
            }
            for example in visible_examples
        ),
        public_input_contract=public_input_contract_from_example_inputs(
            tuple(example.inputs for example in observation.validation_examples)
        ),
        suggested_tool_name=suggested_tool_name,
    )
    return _model_authored_generation_prompt(request)


def test_model_visible_contracts_do_not_serialize_benchmark_literals() -> None:
    observations = (
        (_device_status_lookup_observation("synthetic"), "plan_device_status_lookup"),
        (
            _plan_device_state_action_sequence_observation("synthetic"),
            "plan_device_state_action_sequence_v3",
        ),
        (
            _reminder_creation_finalizer_observation("synthetic"),
            "prepare_reminder_creation_args",
        ),
        (
            _location_search_argument_observation("synthetic"),
            "prepare_specific_location_search_args",
        ),
        (
            _broad_location_search_argument_observation("synthetic"),
            "prepare_broad_location_search_args",
        ),
        (
            _add_contact_argument_observation("synthetic"),
            "prepare_add_contact_args",
        ),
        (
            _resolve_search_window_or_bounds_observation("synthetic"),
            "resolve_search_window_or_bounds",
        ),
        (
            _holiday_search_args_observation("synthetic"),
            "prepare_holiday_search_args",
        ),
        (
            _message_counterparty_search_plan_observation("synthetic"),
            "plan_message_counterparty_search",
        ),
        (_stock_symbol_extraction_observation("synthetic"), "extract_stock_symbol"),
        (
            _address_answer_extraction_observation("synthetic"),
            "extract_address_result",
        ),
        (
            _external_service_answer_extraction_observation("synthetic"),
            "extract_service_answer_field",
        ),
        (
            _distance_answer_extraction_observation("synthetic"),
            "extract_distance_result",
        ),
        (
            _temperature_answer_extraction_observation("synthetic"),
            "extract_temperature_result",
        ),
    )
    serialized = "\n".join(
        _serialized_model_visible_contract(
            observation,
            suggested_tool_name=suggested_tool_name,
        )
        for observation, suggested_tool_name in observations
    )
    prohibited = (
        "whole foods",
        "stevens creek",
        "golden gate bridge",
        "stephen sondheim",
        "+19876543210",
        "one apple park way",
        "67.96238310230461",
        "grand canyon",
        "wifi is on.",
        "wifi has been turned on.",
        "location service has been turned on.",
        "buy tickets",
        "buy chocolate milk",
        "1777380998",
        "todo item i made yesterday",
        "thanksgiving",
        "christmas day",
        "homer s",
        "+10000000000",
        "nasdaq:aapl",
        "you want",
        "how many days is it till",
        "what is the timestamp for",
        "how far am i from the",
        "creek",
        "update_contact_with_id_and_phone_number",
        "your most recent message says",
        "your oldest message says",
        "the phone number for",
        "you are approximately",
    )

    lowered = serialized.lower()
    assert [literal for literal in prohibited if literal in lowered] == []


def test_public_input_contract_exposes_shape_without_held_out_values() -> None:
    hidden_input = "HELD_OUT_INPUT_VALUE_MUST_STAY_PRIVATE"
    hidden_expected = "HELD_OUT_EXPECTED_VALUE_MUST_STAY_PRIVATE"
    examples = (
        ToolExample(
            inputs={"query": "visible example"},
            expected={"value": ""},
        ),
        ToolExample(
            inputs={
                "query": hidden_input,
                "selected_record": {"private_field": hidden_input},
            },
            expected={"value": hidden_expected, "confidence": 0.75},
            held_out=True,
        ),
    )
    visible_examples = _model_visible_generation_examples(examples)
    contract = public_input_contract_from_example_inputs(
        tuple(item.inputs for item in examples)
    )
    output_contract = public_output_contract_from_example_outputs(
        tuple(item.expected for item in examples)
    )
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_task_context",
        observation="Use a visible record when one is available.",
        allowed_families=("composite_workflow_helper",),
        validation_examples=tuple(
            {
                "inputs": item.inputs,
                "expected": item.expected,
                "held_out": False,
                "negative_applicability": item.negative_applicability,
            }
            for item in visible_examples
        ),
        public_input_contract=contract,
        public_output_contract=output_contract,
        suggested_tool_name="select_visible_record",
    )

    prompt = _model_authored_generation_prompt(request)

    assert [item.to_json() for item in contract] == [
        {"name": "query", "annotation": "str", "optional": False},
        {"name": "selected_record", "annotation": "dict", "optional": True},
    ]
    assert '"name": "selected_record"' in prompt
    assert '"annotation": "dict"' in prompt
    assert '"optional": true' in prompt
    assert [item.to_json() for item in output_contract] == [
        {"name": "value", "types": ["string"], "optional": False},
        {"name": "confidence", "types": ["number"], "optional": True},
    ]
    assert '"name": "confidence"' in prompt
    assert '"types": ["number"]' in prompt
    assert "private_field" not in prompt
    assert hidden_input not in prompt
    assert hidden_expected not in prompt


@pytest.mark.parametrize(
    "signature",
    (
        (
            "def prepare_safe_action_or_abstain(user_request: str, "
            "requested_action: str, target_identifier: str, "
            "required_original_tools: list, available_original_tools: list, "
            "visible_records_count: int) -> dict:"
        ),
        (
            "def prepare_safe_action_or_abstain(user_request: str = 'fixed', "
            "requested_action: str = 'fixed', target_identifier: str = 'fixed', "
            "required_original_tools: list = [], "
            "available_original_tools: list = [], "
            "visible_records_count: int = 99) -> dict:"
        ),
        (
            "def prepare_safe_action_or_abstain(user_request: str, /, "
            "requested_action: str, *extra, target_identifier: str = 'fixed', "
            "required_original_tools: list = [], available_original_tools: list = [], "
            "visible_records_count: int = 99, **kwargs) -> dict:"
        ),
    ),
)
def test_public_contract_required_inputs_never_receive_defaults(signature: str) -> None:
    example_inputs = {
        "user_request": "Visible request",
        "requested_action": "modify_record",
        "target_identifier": "visible-id",
        "required_original_tools": ["record_update"],
        "available_original_tools": ["record_update"],
        "visible_records_count": 1,
    }
    contract = public_input_contract_from_example_inputs(
        (example_inputs, dict(example_inputs))
    )
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_task_context",
        observation="Decide whether visible prerequisites permit an action.",
        allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
        public_input_contract=contract,
        suggested_tool_name="prepare_safe_action_or_abstain",
    )
    spec = ToolSpec(
        tool_name="prepare_safe_action_or_abstain",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description="Decide whether visible prerequisites permit an action.",
        inputs=tuple(
            ToolInput(item.name, item.annotation, f"Visible {item.name}.")
            for item in contract
        ),
        output_annotation="dict",
    )
    normalized = _normalize_model_authored_tool(
        request,
        GeneratedTool(spec=spec, code=signature + "\n    return {}\n"),
    )

    function = next(
        node
        for node in ast.parse(normalized.code).body
        if isinstance(node, ast.FunctionDef)
    )
    assert all(not item.optional for item in contract)
    assert function.args.defaults == []
    assert function.args.posonlyargs == []
    assert function.args.vararg is None
    assert function.args.kwonlyargs == []
    assert function.args.kwarg is None
    assert [item.arg for item in function.args.args] == [item.name for item in contract]


def test_public_input_contract_preserves_model_visible_record_description() -> None:
    observation = _latest_record_selection_observation("synthetic")
    visible_examples = _model_visible_generation_examples(
        observation.validation_examples
    )
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_task_context",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        validation_examples=tuple(
            {"inputs": item.inputs, "expected": item.expected}
            for item in visible_examples
        ),
        public_input_contract=public_input_contract_from_example_inputs(
            tuple(item.inputs for item in observation.validation_examples)
        ),
    )

    inputs = {item.name: item for item in _inputs_from_public_contract(request)}

    assert inputs["records"].description.startswith("Complete visible records")
    assert "preserve every record, field, and value" in inputs["records"].description
    assert inputs["selection_mode"].description == (
        "Visible semantic selection mode requested by the user."
    )


def test_contact_planner_normalization_preserves_hidden_case_interface() -> None:
    observation = _contact_lookup_query_planner_observation("synthetic")
    visible_examples = _model_visible_generation_examples(
        observation.validation_examples
    )
    contract = public_input_contract_from_example_inputs(
        tuple(item.inputs for item in observation.validation_examples)
    )
    output_contract = public_output_contract_from_example_outputs(
        tuple(item.expected for item in observation.validation_examples)
    )
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_task_context",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        validation_examples=tuple(
            {
                "inputs": item.inputs,
                "expected": item.expected,
                "held_out": False,
                "negative_applicability": item.negative_applicability,
            }
            for item in visible_examples
        ),
        public_input_contract=contract,
        public_output_contract=output_contract,
        suggested_tool_name="plan_contact_lookup_query",
        inadequacy_evidence=observation.to_inadequacy_evidence().to_json(),
    )
    spec = ToolSpec(
        tool_name="plan_contact_lookup_query",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description="Prepare a contact lookup and extract a visible result field.",
        inputs=(
            ToolInput("contact_name", "str", "Visible contact name."),
            ToolInput("phone_number", "str", "Visible phone number."),
            ToolInput("relationship", "str", "Visible relationship."),
            ToolInput("requested_field", "str", "Requested result field."),
            ToolInput("selected_record", "dict", "Optional visible contact record."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_call_search_contacts": {"type": "boolean"},
                "search_contacts_kwargs": {"type": "object"},
                "answer_field": {"type": "string"},
                "selected_record": {"type": "object"},
                "answer_value": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "copy_exactly": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
                "legacy_undeclared_field": {"type": "string"},
            },
        },
        positive_triggers=("contact_lookup", "contact_target_lookup"),
        negative_triggers=("missing_lookup_constraint", "ambiguous_contact"),
        preserves_side_effect_tools=("search_contacts",),
        required_original_tool_calls=("search_contacts",),
        abstain_behavior="Abstain when no visible lookup constraint is available.",
        generalization_rationale=(
            "The same two-phase lookup contract supports contact answers and actions."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup", "contact_side_effect_target"),
        reason_tool_is_decisive=(
            "It preserves visible lookup evidence across search and extraction."
        ),
        shortfall_cluster_evidence=("contact_lookup_argument_planning",),
        known_failure_mechanisms_addressed=("missing_contact_lookup_plan",),
        inadequacy_evidence=observation.to_inadequacy_evidence(),
    )
    code = """
def plan_contact_lookup_query(contact_name: str, phone_number: str, relationship: str, requested_field: str, selected_record: dict = {}) -> dict:
    kwargs = {}
    if str(contact_name or "").strip():
        kwargs["name"] = str(contact_name).strip()
    if str(phone_number or "").strip():
        kwargs["phone_number"] = str(phone_number).strip()
    if str(relationship or "").strip():
        kwargs["relationship"] = str(relationship).strip()
    requested = str(requested_field or "").strip()
    selected = selected_record if isinstance(selected_record, dict) else {}
    if selected:
        value = selected.get(requested, "")
        subject = str(phone_number or contact_name or relationship).strip()
        recommendation = "" if requested == "person_id" else requested + " for " + subject + ": " + str(value)
        return {"should_call_search_contacts": False, "search_contacts_kwargs": kwargs, "answer_field": requested, "selected_record": selected, "answer_value": value, "final_answer_recommendation": recommendation, "copy_exactly": True, "abstain_reason": ""}
    if not kwargs:
        return {"should_call_search_contacts": False, "search_contacts_kwargs": {}, "answer_field": requested, "selected_record": {}, "answer_value": "", "final_answer_recommendation": "", "copy_exactly": False, "abstain_reason": "missing_lookup_constraint"}
    return {"should_call_search_contacts": True, "search_contacts_kwargs": kwargs, "answer_field": requested, "selected_record": {}, "answer_value": "", "final_answer_recommendation": "", "copy_exactly": False, "abstain_reason": ""}
""".strip()

    normalized = _normalize_model_authored_tool(
        request,
        GeneratedTool(spec=spec, code=code),
    )
    validation = validate_generated_tool(
        normalized,
        observation.validation_examples,
    )

    assert [item.name for item in normalized.spec.inputs] == [
        "contact_name",
        "phone_number",
        "relationship",
        "requested_field",
        "selected_record",
    ]
    assert "selected_record:dict={}" in normalized.code.replace(" ", "")
    assert normalized.spec.output_schema == {
        "type": "object",
        "properties": {
            item.name: {
                "type": item.schema_types[0]
                if len(item.schema_types) == 1
                else list(item.schema_types)
            }
            for item in output_contract
        },
        "required": [item.name for item in output_contract if not item.optional],
        "additionalProperties": False,
    }
    assert validation.accepted, validation.errors


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


def test_validation_abstention_repair_uses_compact_code_specific_cegis() -> None:
    hidden_task = "private_held_out_task_DO_NOT_DISCLOSE_9107"
    hidden_answer = "private_held_out_answer_DO_NOT_DISCLOSE_2841"
    examples = (
        ToolExample(
            inputs={
                "user_request": "Update a record",
                "requested_action": "modify_record",
                "target_identifier": "",
                "required_original_tools": ["record_update"],
                "available_original_tools": ["record_update"],
                "visible_records_count": 0,
            },
            expected={
                "should_abstain": True,
                "missing_information": ["target_identifier"],
                "required_original_tools": ["record_update"],
                "safe_next_action": "ask_user_or_abstain",
                "final_answer_recommendation": (
                    "Cannot continue without a target identifier."
                ),
                "abstain_reason": "missing_target_identifier",
            },
        ),
        ToolExample(
            inputs={
                "user_request": hidden_task,
                "requested_action": "lookup_record",
                "target_identifier": hidden_answer,
                "required_original_tools": [hidden_answer],
                "available_original_tools": [hidden_answer],
                "visible_records_count": 1,
            },
            expected={
                "should_abstain": False,
                "missing_information": [],
                "required_original_tools": [hidden_answer],
                "safe_next_action": "continue_with_original_tool",
                "final_answer_recommendation": "",
                "abstain_reason": "",
            },
            held_out=True,
        ),
    )
    model_visible_examples = _model_visible_generation_examples(examples)
    request = ToolGenerationRequest(
        scenario_name=(
            "post_deployment_repair(kind=implementation;family=record_safety)"
        ),
        observation=(
            "Use public capability, target, and ambiguity rules to decide whether "
            "an action may continue."
        ),
        allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
        validation_examples=tuple(
            {
                "inputs": item.inputs,
                "expected": item.expected,
                "held_out": False,
                "negative_applicability": item.negative_applicability,
            }
            for item in model_visible_examples
        ),
        public_input_contract=public_input_contract_from_example_inputs(
            tuple(item.inputs for item in examples)
        ),
        public_output_contract=public_output_contract_from_example_outputs(
            tuple(item.expected for item in examples)
        ),
        suggested_tool_name="decide_safe_action",
    )
    spec = ToolSpec(
        tool_name="decide_safe_action",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description="Decide whether visible public prerequisites permit an action.",
        inputs=(
            ToolInput("user_request", "str", "Visible user request."),
            ToolInput("requested_action", "str", "Visible requested action."),
            ToolInput("target_identifier", "str", "Visible target."),
            ToolInput("required_original_tools", "list", "Required capabilities."),
            ToolInput("available_original_tools", "list", "Available capabilities."),
            ToolInput("visible_records_count", "int", "Visible matching records."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_abstain": {"type": "boolean"},
                "missing_information": {"type": "array"},
                "required_original_tools": {"type": "array"},
                "safe_next_action": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
            },
        },
        generalization_rationale="The same ordered checks apply across action families.",
        estimated_step_compression=3,
        cross_task_applicability_count=2,
    )
    rejected = GeneratedTool(
        spec=spec,
        code=(
            "def decide_safe_action(user_request: str, requested_action: str, "
            "target_identifier: str, required_original_tools: list, "
            "available_original_tools: list, visible_records_count: int) -> dict:\n"
            "    return {}\n"
        ),
    )

    class CapturingCompleter:
        model = "fake-model"

        def __init__(self) -> None:
            self.requests: list[ChatRequest] = []

        def complete(self, chat_request: ChatRequest) -> str:
            self.requests.append(chat_request)
            if "trace rejected deterministic validation helpers" in (
                chat_request.system.lower()
            ):
                return json.dumps(
                    {
                        "algorithm_steps": [
                            "normalize capabilities",
                            "infer public prerequisites",
                            "check missing capabilities",
                            "classify the action",
                            "apply target and ambiguity gates",
                        ],
                        "capability_aliases": {},
                        "inferred_prerequisites": [],
                        "read_only_actions": ["lookup"],
                        "mutating_actions": ["update"],
                        "target_exceptions": ["read-only lookup"],
                        "case_coverage": {},
                        "invariants": ["return exactly six keys"],
                        "first_incorrect_branches": {
                            "source_0": "fixed result ignores public input"
                        },
                        "regression_guards": ["preserve public passing cases"],
                    }
                )
            return json.dumps(rejected.to_json())

    completer = CapturingCompleter()
    generator = ToolGenerator(completer=completer)
    errors = (
        f"held_out_0_raw_should_abstain:{hidden_task}",
        (
            "blind_property_0_missing_capability_0_final_recommendation_fact:"
            + hidden_answer
        ),
        "source_0_raw_should_abstain:False!=True",
    )

    repaired = generator.repair_candidates(request, rejected, errors)

    assert len(repaired) == 1
    assert len(completer.requests) == 2
    analysis_prompt = completer.requests[0].user
    prompt = completer.requests[1].user
    assert prompt.startswith("Repair one rejected pure deterministic validation helper")
    assert "top-level keys spec and code_lines" in prompt
    assert "Synthesize one reusable deterministic Python tool" not in prompt
    assert "FINAL BINDING VALIDATION-ABSTENTION" in prompt
    assert "Return exactly one complete repair JSON object" in prompt
    assert "REPAIR STRATEGY 1" in prompt
    assert "generic required-minus-available capability computation" not in prompt
    assert '"current_candidate"' in prompt
    assert '"case_label": "source_0"' in prompt
    assert '"validator_feedback"' in prompt
    assert "source_0_raw_should_abstain:False!=True" in prompt
    assert "held_out_0_raw_should_abstain" in prompt
    assert "blind_property_0_missing_capability_0_final_recommendation_fact" in prompt
    assert "Trace the current pure validation helper" in analysis_prompt
    assert "case_coverage, and invariants may be arrays or descriptive objects" in (
        analysis_prompt
    )
    assert "same types as declared by the public contract-analysis protocol" not in (
        analysis_prompt
    )
    assert rejected.code.splitlines()[0] in analysis_prompt
    assert "CODE-SPECIFIC DECISION PLAN" in prompt
    assert len(prompt) < 20_000
    assert len(request.validation_examples) == 1
    assert hidden_task not in analysis_prompt + prompt
    assert hidden_answer not in analysis_prompt + prompt


@pytest.mark.parametrize(
    ("code_suffix", "errors", "prohibited_token"),
    [
        (
            "\n# expected_answer=PRIVATE_SENTINEL",
            ("public_validation_failed",),
            "expected_answer",
        ),
        ("", ("task_id=PRIVATE_SENTINEL",), "task_id"),
    ],
)
def test_post_deployment_repair_audits_exact_prompt_before_inference(
    code_suffix: str,
    errors: tuple[str, ...],
    prohibited_token: str,
) -> None:
    class RecordingCompleter(FakeCompleter):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[ChatRequest] = []

        def complete(self, request: ChatRequest) -> str:
            self.requests.append(request)
            return super().complete(request)

    completer = RecordingCompleter()
    generator = ToolGenerator(completer=completer)
    ordinary_request = ToolGenerationRequest(
        scenario_name="ordinary_visible_context",
        observation="Normalize a visible public label.",
        allowed_families=("canonicalizer",),
        suggested_tool_name="normalize_label",
    )
    rejected = generator.generate(ordinary_request)
    rejected = GeneratedTool(spec=rejected.spec, code=rejected.code + code_suffix)
    repair_request = ToolGenerationRequest(
        scenario_name="post_deployment_repair(kind=implementation;family=labels)",
        observation="Repair visible public label normalization.",
        allowed_families=("canonicalizer",),
        suggested_tool_name="normalize_label",
    )

    with pytest.raises(ValueError, match=prohibited_token):
        generator.repair_candidates(repair_request, rejected, errors)

    assert all("PRIVATE_SENTINEL" not in request.user for request in completer.requests)


def test_validation_helper_repair_restates_public_semantic_exceptions_last() -> None:
    observation = _safe_action_or_abstain_observation("public_contract_probe")
    model_visible_examples = _model_visible_generation_examples(
        observation.validation_examples
    )
    request = ToolGenerationRequest(
        scenario_name="post_deployment_repair(kind=implementation;family=safety)",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        validation_examples=tuple(
            {
                "inputs": item.inputs,
                "expected": item.expected,
                "held_out": False,
                "negative_applicability": item.negative_applicability,
            }
            for item in model_visible_examples
        )
        + (
            {
                "inputs": {"user_request": "PRIVATE_HELD_OUT_SENTINEL"},
                "expected": {"missing_information": ["private_capability"]},
                "held_out": True,
                "negative_applicability": False,
            },
        ),
        suggested_tool_name="prepare_safe_action_or_abstain",
    )

    directive = _model_authored_final_repair_directive(
        request,
        ("public_contract_failure",),
    )

    assert "PUBLIC NAMED-RECIPIENT RULE" in directive
    assert "PUBLIC RELATIVE-TIME RULE" in directive
    assert "Return exactly one complete repair JSON object" in directive
    assert "REPAIR STRATEGY 1" in directive
    assert "PRIVATE_HELD_OUT_SENTINEL" not in directive
    assert "private_capability" not in directive
    assert directive.endswith(
        "every read-only exception must be tested before any generic "
        "blank-target guard."
    )


def test_safe_action_repair_prompt_is_compact_labeled_and_values_safe() -> None:
    observation = _safe_action_or_abstain_observation("public_contract_probe")
    visible_examples = _model_visible_generation_examples(
        observation.validation_examples
    )
    input_contract = public_input_contract_from_example_inputs(
        tuple(item.inputs for item in observation.validation_examples)
    )
    output_contract = public_output_contract_from_example_outputs(
        tuple(item.expected for item in observation.validation_examples)
    )
    request = ToolGenerationRequest(
        scenario_name="post_deployment_repair(kind=implementation;family=safety)",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        validation_examples=tuple(
            {
                "inputs": item.inputs,
                "expected": item.expected,
                "held_out": False,
                "negative_applicability": item.negative_applicability,
            }
            for item in visible_examples
        ),
        public_input_contract=input_contract,
        public_output_contract=output_contract,
        suggested_tool_name="prepare_safe_action_or_abstain",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            description="Decide whether visible prerequisites permit safe action.",
            inputs=tuple(
                ToolInput(item.name, item.annotation, f"Visible {item.name}.")
                for item in input_contract
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    item.name: {"type": list(item.schema_types)[0]}
                    for item in output_contract
                },
            },
        ),
        code=(
            "def prepare_safe_action_or_abstain(user_request: str, "
            "requested_action: str, target_identifier: str, "
            "required_original_tools: list, available_original_tools: list, "
            "visible_records_count: int) -> dict:\n"
            "    return {}\n"
        ),
    )
    hidden_value = "PRIVATE_VALIDATOR_VALUE_DO_NOT_DISCLOSE"
    errors = (
        "source_0_raw_final_recommendation_missing_facts:contact_lookup",
        f"held_out_1_mismatch:{hidden_value}",
        f"blind_property_4_missing_capability_0:{hidden_value}",
        "repair_strategy:4",
    )

    prompt = _model_authored_repair_prompt(request, rejected, errors)
    analysis_prompt = _model_authored_validation_helper_repair_analysis_prompt(
        request,
        rejected,
        errors,
    )

    for case_label in ("source_0", "negative_0", "source_1", "negative_1"):
        assert f'"case_label": "{case_label}"' in prompt
    assert '"case_label": "held_out_' not in prompt
    assert hidden_value not in prompt + analysis_prompt
    assert "held_out_1_mismatch" in prompt
    assert "blind_property_4_missing_capability_0" in prompt
    assert '"repair_strategy": 4' in prompt
    assert "requires both message_send and contact_lookup" in prompt
    assert "blank target_identifier is valid" in prompt
    assert "Synthesize one reusable deterministic Python tool" not in prompt
    assert "Previous candidate JSON" not in prompt
    assert len(prompt) < 16_000

    final_directive = _model_authored_final_repair_directive(request, errors)
    assert "REPAIR STRATEGY 4" in final_directive
    assert "smallest clean implementation" in final_directive


def test_validation_helper_contract_analysis_requires_a_structured_plan() -> None:
    valid = {
        "algorithm_steps": ["normalize", "infer", "validate"],
        "capability_aliases": {},
        "inferred_prerequisites": {"message_send": ["contact_lookup"]},
        "read_only_actions": ["search"],
        "mutating_actions": ["send"],
        "target_exceptions": ["read-only search"],
        "case_coverage": {},
        "invariants": ["do not guess"],
    }

    normalized = _validated_validation_helper_contract_analysis(json.dumps(valid))

    assert json.loads(normalized) == valid
    with pytest.raises(ValueError, match="algorithm_steps"):
        _validated_validation_helper_contract_analysis(
            json.dumps(
                {key: value for key, value in valid.items() if key != "algorithm_steps"}
            )
        )
    with pytest.raises(ValueError, match="not valid JSON"):
        _validated_validation_helper_contract_analysis("not-json")
    malformed = {**valid, "target_exceptions": "read-only search"}
    with pytest.raises(ValueError, match="target_exceptions"):
        _validated_validation_helper_contract_analysis(json.dumps(malformed))

    list_coverage = {
        **valid,
        "case_coverage": [{"case_label": "source_0", "branch": "missing capability"}],
    }
    assert (
        json.loads(
            _validated_validation_helper_contract_analysis(json.dumps(list_coverage))
        )
        == list_coverage
    )

    malformed_coverage = {**valid, "case_coverage": "source_0 is covered"}
    with pytest.raises(ValueError, match="case_coverage"):
        _validated_validation_helper_contract_analysis(json.dumps(malformed_coverage))


def test_validation_helper_repair_analysis_requires_code_specific_diagnosis() -> None:
    valid = {
        "algorithm_steps": ["normalize", "infer", "validate"],
        "capability_aliases": {},
        "inferred_prerequisites": {"message_send": ["contact_lookup"]},
        "read_only_actions": ["search"],
        "mutating_actions": ["send"],
        "target_exceptions": ["read-only search"],
        "case_coverage": {"source_0": "missing capability branch"},
        "invariants": ["do not guess"],
        "first_incorrect_branches": {"source_0": "fixed return"},
        "regression_guards": ["preserve the read-only exception"],
    }

    assert (
        json.loads(_validated_validation_helper_repair_analysis(json.dumps(valid)))
        == valid
    )
    list_coverage = {
        **valid,
        "case_coverage": [{"case_label": "source_0", "branch": "missing capability"}],
    }
    assert (
        json.loads(
            _validated_validation_helper_repair_analysis(json.dumps(list_coverage))
        )
        == list_coverage
    )
    for missing in ("first_incorrect_branches", "regression_guards"):
        with pytest.raises(ValueError, match=missing):
            _validated_validation_helper_repair_analysis(
                json.dumps(
                    {key: value for key, value in valid.items() if key != missing}
                )
            )


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
    assert first.expected["answer_value"] == "65.12"
    assert first.expected["answer_unit"] == "Fahrenheit"
    assert first.expected["should_call_downstream_tool"] is False
    assert first.expected["downstream_tool_name"] == ""
    assert first.expected["copy_exactly"] is True
    low_case = next(
        example
        for example in observation.validation_examples
        if example.inputs.get("requested_metric") == "min"
    )
    assert low_case.inputs["service_payload"]["result"] == 14.6
    assert low_case.inputs["service_payload"]["current_temperature"] == 14.6
    assert low_case.inputs["service_payload"]["min_temperature"] == 7.3
    assert low_case.expected["answer_value"] == "45.14"
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


def test_add_contact_contract_parses_visible_contact_phone_phrase() -> None:
    generator = ToolGenerator(completer=FakeCompleter())
    request = ToolGenerationRequest(
        scenario_name="synthetic_visible_add_contact_context",
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
                        "Add Casey Example to my contact, their phone_number is "
                        "+12025550147"
                    )
                },
                {
                    "add_contact_kwargs": {
                        "name": "Casey Example",
                        "phone_number": "+12025550147",
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Casey Example",
                        "phone_number": "+12025550147",
                    },
                    "normalized_phone_number": "+12025550147",
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
                "inputs": {"stock_payload": {"symbol": "NASDAQ:EXMP"}},
                "expected": "EXMP",
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
