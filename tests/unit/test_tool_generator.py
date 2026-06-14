import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import (
    ToolGenerationRequest,
    ToolGenerator,
    _extract_service_answer_field_contract_tool,
    _plan_send_message_contact_lookup_contract_tool,
    _resolve_search_window_or_bounds_contract_tool,
)
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


def test_service_answer_extractor_contract_supports_visible_weather_payload() -> None:
    request = ToolGenerationRequest(
        scenario_name="visible_task_context",
        observation="Extract scalar fields from visible external service payloads.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="extract_service_answer_field",
    )

    tool = _extract_service_answer_field_contract_tool(request)
    namespace: dict[str, object] = {}
    exec(tool.code, namespace)
    result = namespace["extract_service_answer_field"](
        {"current_temperature": 21.5, "temperature_unit": "Celsius"},
        requested_unit="Fahrenheit",
        answer_subject="Grand Canyon",
    )

    assert "search_weather_around_lat_lon" in tool.spec.required_original_tool_calls
    assert result["answer_value"] == "21.5"
    assert result["answer_kind"] == "current_temperature"
    assert result["answer_unit"] == "Celsius"
    assert result["abstain_reason"] == ""


def test_send_message_contact_lookup_contract_asks_for_missing_content() -> None:
    request = ToolGenerationRequest(
        scenario_name="visible_task_context",
        observation="Named-recipient sends need contact lookup and visible message text.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="plan_send_message_contact_lookup",
    )

    tool = _plan_send_message_contact_lookup_contract_tool(request)
    namespace: dict[str, object] = {}
    exec(tool.code, namespace)
    result = namespace["plan_send_message_contact_lookup"](
        recipient_name="Fredrik Thordendal",
        message_content="",
    )

    assert result["should_call_search_contacts"] is False
    assert result["abstain_reason"] == "missing_message_content"
    assert result["next_step"] == "ask_for_message_content"
    assert "Fredrik Thordendal" in result["final_answer_recommendation"]


def test_add_contact_contract_parses_to_my_contact_phone_phrase(
    tmp_path: Path,
) -> None:
    generator = ToolGenerator(completer=FakeCompleter(), cache=PromptCache(tmp_path))
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


def test_service_answer_extractor_generation_uses_deterministic_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="convert_currency",
        observation="Need deterministic service payload answer extraction.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="extract_service_answer_field",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "service_payload": {
                        "converted_amount": 123.45,
                        "currency_code": "EUR",
                    }
                },
                {
                    "answer_value": "123.45",
                    "answer_kind": "converted_amount",
                    "answer_unit": "EUR",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "123.45 EUR",
                    "final_answer_recommendation": "123.45 EUR",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"service_payload": {"current_temperature": 21.5}},
                {
                    "answer_value": "",
                    "answer_kind": "",
                    "answer_unit": "",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "no_supported_answer_field",
                },
                held_out=True,
                negative_applicability=True,
            ),
            ToolExample(
                {"service_payload": {"distance_km": 67.96238310230461}},
                {
                    "answer_value": "67.96238310230461",
                    "answer_kind": "distance",
                    "answer_unit": "km",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": (
                        "The distance is approximately 67.96 kilometers."
                    ),
                    "final_answer_recommendation": (
                        "The distance is approximately 67.96 kilometers."
                    ),
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "service_payload": [
                        {
                            "name": "Apple Park",
                            "phone_number": "+14089961010",
                        }
                    ]
                },
                {
                    "answer_value": "+14089961010",
                    "answer_kind": "phone_number",
                    "answer_unit": "",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "+14089961010",
                    "final_answer_recommendation": "+14089961010",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"service_payload": "One Apple Park Way, Cupertino, CA 95014, USA"},
                {
                    "answer_value": "One Apple Park Way, Cupertino, CA 95014, USA",
                    "answer_kind": "result",
                    "answer_unit": "",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "One Apple Park Way, Cupertino, CA 95014, USA",
                    "final_answer_recommendation": (
                        "One Apple Park Way, Cupertino, CA 95014, USA"
                    ),
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {"service_payload": {"name": "Main Branch", "category": "library"}},
                {
                    "answer_value": "",
                    "answer_kind": "",
                    "answer_unit": "",
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "exact_final_answer": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "no_supported_answer_field",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert tool.spec.tool_name == "extract_service_answer_field"
    assert result.accepted, result.errors


def test_device_status_lookup_generation_uses_original_getters(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="get_wifi",
        observation="Need deterministic read-only device status lookup.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="plan_device_status_lookup",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "Can you check whether wifi is on?",
                    "visible_state_result": "",
                },
                {
                    "tool_name": "get_wifi_status",
                    "arguments": {},
                    "should_call": True,
                    "target_service": "wifi",
                    "status_value": False,
                    "status_label": "Wifi",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Is my cellular service on?",
                    "visible_state_result": "True",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "target_service": "cellular",
                    "status_value": True,
                    "status_label": "Cellular service",
                    "final_answer_recommendation": "Cellular service is on.",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Turn on wifi",
                    "visible_state_result": "",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "target_service": "",
                    "status_value": False,
                    "status_label": "",
                    "final_answer_recommendation": "",
                    "abstain_reason": "not_read_only_status_lookup",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "user_request": "Can you check whether wifi is on?",
                    "visible_state_result": "",
                    "available_tools": ["get_cellular_service_status"],
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "target_service": "wifi",
                    "status_value": False,
                    "status_label": "Wifi",
                    "final_answer_recommendation": "",
                    "abstain_reason": "status_getter_not_visible",
                },
                held_out=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert tool.spec.tool_name == "plan_device_status_lookup"
    assert "get_wifi_status" in tool.spec.required_original_tool_calls
    assert any(item.name == "available_tools" for item in tool.spec.inputs)
    assert result.accepted, result.errors


def test_contact_lookup_generation_drops_invented_self_relationship(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="remove_contact_by_phone_10_distraction_tools",
        observation="Need deterministic contact lookup planning.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="plan_contact_lookup_query",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "+12453344098",
                    "relationship": "self",
                    "requested_field": "person_id",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"phone_number": "+12453344098"},
                    "answer_field": "person_id",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "boss",
                    "requested_field": "name",
                },
                {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"relationship": "boss"},
                    "answer_field": "name",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "self",
                    "requested_field": "phone_number",
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "answer_field": "phone_number",
                    "selected_record": {},
                    "answer_value": "",
                    "final_answer_recommendation": "",
                    "copy_exactly": False,
                    "abstain_reason": "missing_lookup_constraint",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "phone_number": "+10000000000",
                    "requested_field": "relationship",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {"phone_number": "+10000000000"},
                    "answer_field": "relationship",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                    "answer_value": "boss",
                    "final_answer_recommendation": "+10000000000 is your boss",
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "contact_name": "Homer S",
                    "requested_field": "phone_number",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                },
                {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {"name": "Homer S"},
                    "answer_field": "phone_number",
                    "selected_record": {
                        "person_id": "p1",
                        "name": "Homer S",
                        "phone_number": "+10000000000",
                        "relationship": "boss",
                    },
                    "answer_value": "+10000000000",
                    "final_answer_recommendation": (
                        "Homer S's phone number is +10000000000"
                    ),
                    "copy_exactly": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert tool.spec.tool_name == "plan_contact_lookup_query"
    assert "selected_record" in {item.name for item in tool.spec.inputs}
    assert tool.spec.required_original_tool_calls == ("search_contacts",)
    assert result.accepted, result.errors


def test_relationship_batch_generation_handles_all_contacts_sentinel(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="update_contact_relationship_with_relationship_twice_multiple_user_turn",
        observation="Need deterministic relationship batch planning.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="plan_contact_relationship_batch_update",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "Update all contacts as enemies",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "contacts": [],
                },
                {
                    "phase": "search_required",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"is_self": False},
                    "selected_contacts": [],
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                    "should_call_tools": False,
                    "abstain_reason": "",
                    "final_answer_recommendation": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Update all contacts as enemies",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "contacts": [
                        {
                            "person_id": "self",
                            "name": "Me",
                            "relationship": "self",
                            "is_self": True,
                        },
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                },
                {
                    "phase": "modify_required",
                    "source_relationship": "__all_contacts__",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p1", "relationship": "enemy"}
                    ],
                    "should_call_tools": True,
                    "abstain_reason": "",
                    "final_answer_recommendation": "Ada is now your enemy.",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Make all of my friends my enemy",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                        {
                            "person_id": "p2",
                            "name": "Grace",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                },
                {
                    "phase": "modify_required",
                    "source_relationship": "friend",
                    "target_relationship": "enemy",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [
                        {
                            "person_id": "p1",
                            "name": "Ada",
                            "relationship": "friend",
                            "is_self": False,
                        },
                        {
                            "person_id": "p2",
                            "name": "Grace",
                            "relationship": "friend",
                            "is_self": False,
                        },
                    ],
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p1", "relationship": "enemy"},
                        {"person_id": "p2", "relationship": "enemy"},
                    ],
                    "should_call_tools": True,
                    "abstain_reason": "",
                    "final_answer_recommendation": "Ada and Grace are now your enemies.",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Make all friends friends",
                    "source_relationship": "friend",
                    "target_relationship": "friend",
                    "contacts": [],
                },
                {
                    "phase": "abstain",
                    "source_relationship": "friend",
                    "target_relationship": "friend",
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "selected_contacts": [],
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                    "should_call_tools": False,
                    "abstain_reason": "source equals target",
                    "final_answer_recommendation": "No relationship change is needed.",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert tool.spec.tool_name == "plan_contact_relationship_batch_update"
    assert "modify_contact" in tool.spec.preserves_side_effect_tools
    assert result.accepted, result.errors


def test_safe_abstain_generation_uses_import_free_deterministic_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="modify_contact_with_message_recency_insufficient_information",
        observation="Need deterministic safe abstention before unsafe side effects.",
        allowed_families=("validation_abstention_helper",),
        suggested_tool_name="prepare_safe_action_or_abstain",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "Update that contact",
                    "requested_action": "contact_update",
                    "target_identifier": "",
                    "required_original_tools": ["contact_update"],
                    "available_original_tools": ["contact_update"],
                    "visible_records_count": 0,
                },
                {
                    "should_abstain": True,
                    "missing_information": ["target_identifier"],
                    "required_original_tools": ["contact_update"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "I do not have enough information to complete the action."
                    ),
                    "abstain_reason": "missing_target_identifier",
                },
            ),
            ToolExample(
                {
                    "user_request": "Update contact id phone",
                    "requested_action": "contact_update",
                    "target_identifier": "11111111-1111-1111-1111-111111111111",
                    "required_original_tools": ["contact_update"],
                    "available_original_tools": ["contact_update"],
                    "visible_records_count": 0,
                },
                {
                    "should_abstain": False,
                    "missing_information": [],
                    "required_original_tools": ["contact_update"],
                    "safe_next_action": "continue_with_original_tool",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Update by name only",
                    "requested_action": "contact_update",
                    "target_identifier": "Ada",
                    "required_original_tools": ["contact_update"],
                    "available_original_tools": ["contact_update"],
                    "visible_records_count": 0,
                },
                {
                    "should_abstain": True,
                    "missing_information": ["contact_lookup"],
                    "required_original_tools": ["contact_update"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "I do not have enough information to identify the contact "
                        "because contact search is unavailable."
                    ),
                    "abstain_reason": "missing_contact_lookup_tool",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert "import " not in tool.code
    assert completer.calls == 0
    assert tool.spec.tool_name == "prepare_safe_action_or_abstain"
    assert result.accepted, result.errors


def test_safe_abstain_contract_returns_precise_missing_lookup_answers(
    tmp_path: Path,
) -> None:
    generator = ToolGenerator(completer=FakeCompleter(), cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="remove_contact_by_phone_no_search_contacts_insufficient_information",
        observation="Need precise safe abstention when required lookup tools are absent.",
        allowed_families=("validation_abstention_helper",),
        suggested_tool_name="prepare_safe_action_or_abstain",
    )

    tool = generator.generate(request)
    namespace: dict[str, object] = {}
    exec(tool.code, namespace)
    prepare = namespace["prepare_safe_action_or_abstain"]

    contact_result = prepare(
        "Remove phone number +12453344098 from my contact",
        "contact_removal",
        "+12453344098",
        ["contact_lookup", "contact_removal"],
        ["contact_removal"],
        0,
    )
    assert contact_result["should_abstain"] is True
    assert "contact_lookup" in contact_result["missing_information"]
    assert contact_result["final_answer_recommendation"] == (
        "I do not have enough information to safely remove the contact with "
        "phone number +12453344098. I would need a contact name or person_id, "
        "or access to search contacts, before I can remove it."
    )

    message_result = prepare(
        "Update the phone number of the last person I sent a message to to +10293847563",
        "modify_contact",
        "recency_reference",
        ["search_messages", "modify_contact"],
        ["modify_contact"],
        0,
    )
    assert message_result["should_abstain"] is True
    assert "message_lookup" in message_result["missing_information"]
    assert message_result["final_answer_recommendation"] == (
        "I do not have enough information to identify the last person you sent "
        "a message to because message history is unavailable."
    )

    message_action_text_result = prepare(
        "Update the phone number of the last person I sent a message to to +10293847563",
        "update phone number",
        "recency_reference",
        ["search_messages", "modify_contact"],
        ["modify_contact"],
        0,
    )
    assert message_action_text_result["should_abstain"] is True
    assert "message_lookup" in message_action_text_result["missing_information"]
    assert message_action_text_result["final_answer_recommendation"] == (
        "I do not have enough information to identify the last person you sent "
        "a message to because message history is unavailable."
    )

    send_message_result = prepare(
        "Send a message to Fredrik Thordendal saying: How's the new album coming along.",
        "message_send",
        "Fredrik Thordendal",
        ["contact_lookup", "message_send"],
        ["message_send"],
        0,
    )
    assert send_message_result["should_abstain"] is True
    assert "contact_lookup" in send_message_result["missing_information"]
    assert send_message_result["final_answer_recommendation"] == (
        "I cannot safely send the message because I do not have contact lookup "
        "available to resolve Fredrik Thordendal to a phone number."
    )

    underspecified_send_message_result = prepare(
        "Send a message to Fredrik Thordendal saying: How's the new album coming along.",
        "message_send",
        "Fredrik Thordendal",
        ["message_send"],
        ["message_send"],
        0,
    )
    assert underspecified_send_message_result["should_abstain"] is True
    assert "contact_lookup" in underspecified_send_message_result["missing_information"]
    assert underspecified_send_message_result["final_answer_recommendation"] == (
        "I cannot safely send the message because I do not have contact lookup "
        "available to resolve Fredrik Thordendal to a phone number."
    )

    underspecified_message_recency_update_result = prepare(
        "Update the phone number of the last person I sent a message to to +10293847563",
        "modify_contact",
        "last_sent_message",
        ["contact_update"],
        ["contact_lookup"],
        3,
    )
    assert underspecified_message_recency_update_result["should_abstain"] is True
    assert (
        "message_lookup"
        in underspecified_message_recency_update_result["missing_information"]
    )
    assert underspecified_message_recency_update_result[
        "final_answer_recommendation"
    ] == (
        "I do not have enough information to identify the last person you sent "
        "a message to because message history is unavailable."
    )

    location_result = prepare(
        "What city am I in?",
        "get my current city",
        "current location",
        [],
        ["set_location_service_status"],
        0,
    )
    assert location_result["should_abstain"] is True
    assert "location_lookup" in location_result["missing_information"]
    assert location_result["final_answer_recommendation"] == (
        "I cannot determine what city you are in because I do not have access "
        "to your current location, GPS, or latitude and longitude coordinates."
    )

    coordinate_lookup_result = prepare(
        "What city am I in?",
        "location_lookup",
        "",
        ["location_lookup"],
        ["search_lat_lon", "get_location_service_status"],
        0,
    )
    assert coordinate_lookup_result["should_abstain"] is True
    assert "location_lookup" in coordinate_lookup_result["missing_information"]

    reminder_search_result = prepare(
        "Search my reminders",
        "search_reminder",
        "",
        ["search_reminder"],
        ["search_reminder"],
        0,
    )
    assert reminder_search_result["should_abstain"] is True
    assert reminder_search_result["missing_information"] == ["search_criteria"]
    assert reminder_search_result["abstain_reason"] == "missing_search_criteria"

    recency_only_search_result = prepare(
        "Search my reminder from yesterday",
        "search_reminder",
        "yesterday",
        ["search_reminder"],
        ["search_reminder"],
        0,
    )
    assert recency_only_search_result["should_abstain"] is True
    assert recency_only_search_result["missing_information"] == [
        "specific_search_criteria"
    ]
    assert (
        recency_only_search_result["abstain_reason"] == "recency_only_search_criteria"
    )


def test_prepare_holiday_search_args_contract_tool_validates(tmp_path: Path) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="find_thanksgiving_timestamp",
        observation="Need deterministic search_holiday kwargs for a timestamp request.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_holiday_search_args",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "What is the timestamp for Thanksgiving?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": True,
                    "search_holiday_kwargs": {"holiday_name": "Thanksgiving"},
                    "holiday_name": "Thanksgiving",
                    "year_policy": "environment_resolves_year",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "What is the timestamp for Thanksgiving in 2027?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": True,
                    "search_holiday_kwargs": {
                        "holiday_name": "Thanksgiving",
                        "year": 2027,
                    },
                    "holiday_name": "Thanksgiving",
                    "year_policy": "explicit_year",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "What is the holiday timestamp?",
                    "visible_current_year": 0,
                },
                {
                    "should_call_search_holiday": False,
                    "search_holiday_kwargs": {},
                    "holiday_name": "",
                    "year_policy": "missing_holiday_name",
                    "final_answer_recommendation": (
                        "I need the holiday name before I can look up its timestamp."
                    ),
                    "abstain_reason": "missing_holiday_name",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert tool.spec.tool_name == "prepare_holiday_search_args"
    assert "search_holiday" in tool.spec.required_original_tool_calls
    assert result.accepted, result.errors


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
                    "current_datetime_info": {
                        "year": 1970,
                        "month": 1,
                        "day": 1,
                        "hour": 0,
                        "minute": 0,
                        "second": 0,
                    },
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
                    "timestamp_source": "current_datetime_info",
                },
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk",
                    "resolved_reminder_timestamp": 1778618400.0,
                    "current_timestamp": 1778603855.0,
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
                        "content": "Buy chocolate milk",
                        "reminder_timestamp": 1778618400.0,
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
                    "content": "Call mom at 5 PM",
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
                    "location_lookup_failed": False,
                    "current_datetime_info": {
                        "year": 1970,
                        "month": 1,
                        "day": 1,
                        "hour": 0,
                        "minute": 0,
                        "second": 0,
                    },
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Call mom at 5 PM",
                        "reminder_timestamp": 147600.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "current_datetime_info",
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
                    "content": "Buy milk",
                    "resolved_reminder_timestamp": None,
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
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "missing_time_info",
                    "location_status": "omitted_optional",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy milk",
                    "resolved_reminder_timestamp": 1777428906.0,
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
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "current_timestamp_placeholder_rejected",
                    "location_status": "omitted_optional",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy milk",
                    "resolved_reminder_timestamp": 1777428902.0,
                    "current_timestamp": 1777428906.0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 4,
                        "day": 28,
                        "hour": 19,
                        "minute": 15,
                        "second": 6,
                    },
                    "day_offset": 0,
                    "hour": 19,
                    "minute": 15,
                    "local_utc_offset_hours": -7.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "current_timestamp_placeholder_rejected",
                    "location_status": "omitted_optional",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk",
                    "resolved_reminder_timestamp": 1711152000.0,
                    "current_timestamp": 1711152000.0,
                    "day_offset": 0,
                    "hour": 17,
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
                        "content": "Buy chocolate milk",
                        "reminder_timestamp": 1711152000.0,
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
                    "content": "Buy chocolate milk",
                    "resolved_reminder_timestamp": 1711141200.0,
                    "current_timestamp": 1780186343.0,
                    "day_offset": -1,
                    "hour": 17,
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
                        "content": "Buy chocolate milk",
                        "reminder_timestamp": 1711141200.0,
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
                    "timestamp_source": "none",
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
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 0.0,
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
                        "content": "Buy chocolate milk at Whole Foods",
                        "reminder_timestamp": 1777776000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "resolved",
                },
            ),
        ),
    )
    assert result.accepted, result.errors
    namespace: dict[str, object] = {}
    exec(repaired.code, namespace)
    prepare = namespace["prepare_reminder_creation_args"]
    resolved_only_result = prepare(
        content="Buy chocolate milk.",
        resolved_reminder_timestamp=1711152000.0,
    )
    assert resolved_only_result["should_call_add_reminder"] is True
    assert resolved_only_result["add_reminder_kwargs"] == {
        "content": "Buy chocolate milk.",
        "reminder_timestamp": 1711152000.0,
        "latitude": None,
        "longitude": None,
    }
    assert resolved_only_result["timestamp_source"] == "resolved"
    resolved_with_coordinates = prepare(
        content="Buy chocolate milk.",
        resolved_reminder_timestamp=1711152000.0,
        location_requested=True,
        location_required=True,
        location_available=True,
        latitude=37.3235879,
        longitude=-122.0396177,
    )
    assert resolved_with_coordinates["should_call_add_reminder"] is True
    assert resolved_with_coordinates["add_reminder_kwargs"] == {
        "content": "Buy chocolate milk.",
        "reminder_timestamp": 1711152000.0,
        "latitude": 37.3235879,
        "longitude": -122.0396177,
    }
    assert resolved_with_coordinates["location_status"] == "provided"
    placeholder_result = prepare(
        content="Reminder for 5 PM",
        resolved_reminder_timestamp=1711152000.0,
        current_timestamp=None,
        day_offset=0,
        hour=17,
        minute=0,
        local_utc_offset_hours=0.0,
        location_requested=False,
        location_required=False,
        location_available=False,
        latitude=0.0,
        longitude=0.0,
        location_lookup_failed=False,
    )
    assert placeholder_result["should_call_add_reminder"] is False
    assert placeholder_result["abstain_reason"] == "missing_reminder_content"
    generic_filler_result = prepare(
        content="Don't forget!",
        resolved_reminder_timestamp=1711152000.0,
        current_timestamp=None,
        day_offset=0,
        hour=17,
        minute=0,
        local_utc_offset_hours=0.0,
        location_requested=False,
        location_required=False,
        location_available=False,
        latitude=0.0,
        longitude=0.0,
        location_lookup_failed=False,
    )
    assert generic_filler_result["should_call_add_reminder"] is False
    assert generic_filler_result["abstain_reason"] == "missing_reminder_content"
    relative_resolved_result = prepare(
        content="Buy chocolate milk",
        resolved_reminder_timestamp=1780876800.0,
        current_timestamp=1780808158.150612,
        day_offset=1,
        hour=17,
        minute=0,
        local_utc_offset_hours=-8.0,
        location_requested=True,
        location_required=False,
        location_available=True,
        latitude=37.3235879,
        longitude=-122.0396177,
        location_lookup_failed=False,
    )
    assert relative_resolved_result["should_call_add_reminder"] is True
    assert (
        relative_resolved_result["add_reminder_kwargs"]["reminder_timestamp"]
        == 1780876800.0
    )
    assert relative_resolved_result["timestamp_source"] == "resolved"


def test_location_search_contract_uses_user_request_as_isolated_place_phrase(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="add_reminder_content_and_week_delta_and_time_and_location",
        observation="Location search needs preserved place qualifiers.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_location_search_args",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "Whole Foods on Stevens Creek",
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Central Market on North Lamar",
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Central Market on North Lamar"
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Central Market on North Lamar"
                    },
                    "location_query": "Central Market on North Lamar",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Remind me to buy chocolate milk tomorrow 5PM at Whole Foods on Stevens Creek.",
                    "location_phrase": "Stevens Creek",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Remind me to buy chocolate milk tomorrow 5PM at Whole Foods on Stevens Creek.",
                    "location_phrase": "Whole Foods on Stevens Creek",
                    "latitude": 37.319532,
                    "longitude": -122.046872,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Add a reminder to buy chocolate milk at Whole Foods.",
                    "location_phrase": "Whole Foods",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {},
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "location_query": "Whole Foods",
                    "abstain_reason": "missing_reminder_time_before_location_lookup",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Whole Foods on Stevens Creek",
                    "location_phrase": "Whole Foods",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "search_location_around_lat_lon",
                    "downstream_tool_kwargs": {
                        "location": "Whole Foods on Stevens Creek"
                    },
                    "location_query": "Whole Foods on Stevens Creek",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Remind me tomorrow at 5 PM",
                    "location_phrase": "",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                {
                    "search_location_kwargs": {},
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "location_query": "",
                    "abstain_reason": "missing_location_phrase",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
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
                    "safety_notes": "call remove_reminder with downstream_tool_kwargs",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "p1",
                            "sender_phone_number": "+15550111",
                            "recipient_person_id": "self",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "m2",
                            "sender_person_id": "self",
                            "recipient_person_id": "p2",
                            "recipient_phone_number": "+15550222",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "oldest",
                    "updates": {"relationship": "friend"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message_id": "m1",
                    "selected_person_id": "p1",
                    "selected_phone_number": "+15550111",
                    "selected_timestamp": 10.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p1",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "p1",
                            "sender_phone_number": "+15550111",
                            "recipient_person_id": "self",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "m2",
                            "sender_person_id": "self",
                            "recipient_person_id": "p2",
                            "recipient_phone_number": "+15550222",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "oldest",
                    "updates": {"relationship": "friend"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message_id": "m1",
                    "selected_person_id": "p1",
                    "selected_phone_number": "+15550111",
                    "selected_timestamp": 10.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p1",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m_old",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_old",
                            "recipient_phone_number": "+15550111",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "m_new",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_new",
                            "recipient_phone_number": "+15550222",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_contact",
                    "constraints": {},
                    "updates": {"phone_number": "+15550999"},
                    "self_person_id": "self-typo",
                },
                {
                    "selected_record": {
                        "message_id": "m_new",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_new",
                        "recipient_phone_number": "+15550222",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message": {
                        "message_id": "m_new",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_new",
                        "recipient_phone_number": "+15550222",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message_id": "m_new",
                    "selected_person_id": "p_new",
                    "selected_phone_number": "+15550222",
                    "selected_timestamp": 30.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p_new",
                        "phone_number": "+15550999",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
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
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"reminder_id": "soon", "reminder_timestamp": 25.0},
                        {"reminder_id": "later", "reminder_timestamp": 40.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "upcoming",
                    "action_type": "remove_reminder",
                    "constraints": {},
                    "updates": {},
                    "reference_timestamp": 20.0,
                },
                {
                    "selected_record": {
                        "reminder_id": "soon",
                        "reminder_timestamp": 25.0,
                    },
                    "selected_index": 0,
                    "selected_id": "soon",
                    "selected_timestamp": 25.0,
                    "action_type": "remove_reminder",
                    "downstream_tool_name": "remove_reminder",
                    "downstream_tool_kwargs": {"reminder_id": "soon"},
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call remove_reminder with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "read_only",
                            "content": "Buy tickets",
                            "creation_timestamp": 10.0,
                        }
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "remove",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 0.0,
                    "action_type": "remove",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "unsupported_action_type",
                    "safety_notes": "do not guess before side-effect action",
                },
                negative_applicability=True,
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
                    "downstream_tool_name": "",
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


def test_action_selector_repair_accepts_planned_modify_reminder_contract(
    tmp_path: Path,
) -> None:
    from sage_ts.adequacy.inadequacy_classifier import (
        classify_planned_scenario_observations,
    )

    observation = next(
        item
        for item in classify_planned_scenario_observations(
            "modify_reminder_with_recency_latest"
        )
        if item.canonical_key == "search_filter:select_action_target_by_recency"
    )
    generator = ToolGenerator(completer=FakeCompleter(), cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
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
            positive_triggers=("modify_reminder_with_recency_latest",),
            negative_triggers=("ambiguous_tie",),
            preserves_side_effect_tools=("modify_reminder",),
            required_original_tool_calls=("search_reminder",),
            abstain_behavior="Abstain on ambiguity.",
            generalization_rationale="Recency action targeting recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("modify_reminder_with_recency_latest",),
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

    result = validate_generated_tool(
        repaired,
        examples=(
            *observation.validation_examples,
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "old",
                            "creation_timestamp": 10.0,
                            "reminder_timestamp": 100.0,
                        },
                        {
                            "reminder_id": "new",
                            "creation_timestamp": 20.0,
                            "reminder_timestamp": 200.0,
                        },
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_reminder",
                    "constraints": {},
                    "updates": {"reminder_timestamp": 300.0},
                },
                {
                    "selected_record": {
                        "reminder_id": "new",
                        "creation_timestamp": 20.0,
                        "reminder_timestamp": 200.0,
                    },
                    "selected_index": 1,
                    "selected_id": "new",
                    "selected_timestamp": 20.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "modify_reminder",
                    "downstream_tool_kwargs": {
                        "reminder_id": "new",
                        "reminder_timestamp": 300.0,
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_reminder with downstream_tool_kwargs",
                },
                held_out=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_action_selector_supports_answer_only_recency_selection(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="search_reminder_with_recency_upcoming",
        observation="Need to select the visible reminder by recency for an answer.",
        allowed_families=("search_filter_ranking_helper",),
        suggested_tool_name="select_action_target_by_recency",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Rejected recency selector.",
            inputs=(ToolInput("records", "list", "records"),),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                },
            },
            positive_triggers=("search_reminder_with_recency_upcoming",),
            negative_triggers=("ambiguous_tie",),
            preserves_side_effect_tools=("search_reminder",),
            required_original_tool_calls=("search_reminder",),
            abstain_behavior="Abstain on ambiguity.",
            generalization_rationale="Recency selection recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("search_reminder_with_recency",),
            reason_tool_is_decisive="It selects a visible record by recency.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("answer_record_selection_loss",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Selector lost the visible selected record for answer tasks.",
                signals=("final_response_phrasing_failure",),
            ),
        ),
        code="def select_action_target_by_recency(records: list) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(
        request,
        rejected,
        ("action_selector_missing_downstream_kwargs_contract",),
    )

    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "old",
                            "content": "Buy tickets for Merrily next week",
                            "reminder_timestamp": 1780659225.0,
                        },
                        {
                            "reminder_id": "new",
                            "content": "Buy a nice rich navy bathing dress",
                            "reminder_timestamp": 1780662885.0,
                        },
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {
                        "reminder_id": "new",
                        "content": "Buy a nice rich navy bathing dress",
                        "reminder_timestamp": 1780662885.0,
                    },
                    "selected_index": 1,
                    "selected_id": "new",
                    "selected_timestamp": 1780662885.0,
                    "action_type": "answer_record",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": (
                        "use selected_record for the answer; "
                        "no side-effect tool is needed"
                    ),
                    "final_answer_recommendation": (
                        'Your selected item is "Buy a nice rich navy bathing dress".'
                    ),
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "soon",
                            "content": "Call Sam",
                            "reminder_timestamp": 100.0,
                        },
                        {
                            "reminder_id": "later",
                            "content": "Send invoice",
                            "reminder_timestamp": 300.0,
                        },
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "answer_record",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {
                        "reminder_id": "later",
                        "content": "Send invoice",
                        "reminder_timestamp": 300.0,
                    },
                    "selected_index": 1,
                    "selected_id": "later",
                    "selected_timestamp": 300.0,
                    "action_type": "answer_record",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": (
                        "use selected_record for the answer; "
                        "no side-effect tool is needed"
                    ),
                    "final_answer_recommendation": (
                        'Your selected item is "Send invoice".'
                    ),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "a",
                            "content": "Call Sam",
                            "reminder_timestamp": 300.0,
                        },
                        {
                            "reminder_id": "b",
                            "content": "Send invoice",
                            "reminder_timestamp": 300.0,
                        },
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                    "action_type": "reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 300.0,
                    "action_type": "answer_record",
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [
                        {
                            "reminder_id": "a",
                            "content": "Call Sam",
                            "reminder_timestamp": 300.0,
                        },
                        {
                            "reminder_id": "b",
                            "content": "Send invoice",
                            "reminder_timestamp": 300.0,
                        },
                    ],
                    "abstain_reason": "ambiguous_timestamp_tie",
                    "safety_notes": "do not guess before side-effect action",
                    "final_answer_recommendation": "",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_next_weekday_repair_uses_deterministic_timestamp_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="add_reminder_content_and_weekday_delta_and_time",
        observation="Need a next weekday reminder timestamp canonicalizer.",
        allowed_families=("canonicalizer",),
        suggested_tool_name="next_weekday_time_to_timestamp",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="next_weekday_time_to_timestamp",
            family=ToolFamily.CANONICALIZER,
            description="Rejected weekday timestamp helper.",
            inputs=(ToolInput("current_timestamp", "float", "current"),),
            output_annotation="float",
            positive_triggers=("next Friday reminder",),
            negative_triggers=("invalid weekday",),
            preserves_side_effect_tools=("get_current_timestamp", "add_reminder"),
            required_original_tool_calls=("get_current_timestamp", "add_reminder"),
            abstain_behavior="Return 0 for invalid fields.",
            generalization_rationale="Weekday scheduling recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "add_reminder_content_and_weekday_delta_and_time",
                "modify_reminder_with_weekday_delta_and_time",
            ),
            reason_tool_is_decisive="It computes the timestamp before add_reminder.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("weekday_timestamp_wrong",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Weekday timestamp was wrong.",
                signals=("visible_raw_data_lacking_deterministic_transform",),
            ),
        ),
        code="def next_weekday_time_to_timestamp(current_timestamp: float) -> float:\n    return current_timestamp\n",
    )

    repaired = generator.repair(request, rejected, ("denied_node:Import",))

    assert completer.calls == 0
    assert repaired.spec.tool_name == "next_weekday_time_to_timestamp"
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1778595707.0,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 12,
                        "hour": 10,
                        "minute": 21,
                        "second": 47,
                        "isoweekday": 2,
                    },
                },
                1778878800.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1778603870.0,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 12,
                        "hour": 12,
                        "minute": 37,
                        "second": 50,
                        "isoweekday": 2,
                    },
                },
                1778878800.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1778860800.0,
                    "target_isoweekday": 5,
                    "hour": 8,
                    "minute": 30,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 15,
                        "hour": 12,
                        "minute": 0,
                        "second": 0,
                        "isoweekday": 5,
                    },
                },
                1779453000.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780644041.436888,
                    "target_isoweekday": 5,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 5,
                        "hour": 0,
                        "minute": 20,
                        "second": 41,
                        "isoweekday": 5,
                    },
                },
                1780704000.0,
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1778595707.0,
                    "target_isoweekday": 8,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 5,
                        "day": 12,
                        "hour": 10,
                        "minute": 21,
                        "second": 47,
                        "isoweekday": 2,
                    },
                },
                0.0,
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_relative_day_time_contract_requires_only_timestamp_producer(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="modify_reminder_with_recency_latest",
        observation="Need a timestamp canonicalizer before modifying a reminder.",
        allowed_families=("canonicalizer",),
        suggested_tool_name="relative_day_time_to_timestamp",
    )

    tool = generator.generate(request)

    assert tool.spec.tool_name == "relative_day_time_to_timestamp"
    assert tool.spec.required_original_tool_calls == (
        "get_current_timestamp",
        "timestamp_to_datetime_info",
    )
    assert "add_reminder" in tool.spec.preserves_side_effect_tools
    assert "modify_reminder" in tool.spec.preserves_side_effect_tools
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1780640888.631557,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 6,
                        "day": 4,
                        "hour": 23,
                        "minute": 28,
                        "second": 8,
                        "isoweekday": 4,
                    },
                },
                1780704000.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1777428906.194959,
                    "day_offset": 2,
                    "hour": 8,
                    "minute": 30,
                    "local_utc_offset_hours": 0,
                    "current_datetime_info": {
                        "year": 2026,
                        "month": 4,
                        "day": 28,
                        "hour": 22,
                        "minute": 15,
                        "second": 6,
                        "isoweekday": 2,
                    },
                },
                1777552200.0,
                held_out=True,
            ),
        ),
    )
    assert validation.accepted, validation.errors
    namespace: dict[str, object] = {}
    exec(tool.code, namespace)
    result = namespace["relative_day_time_to_timestamp"](
        current_timestamp=1780640888.631557,
        day_offset=1,
        hour=17,
        minute=0,
        current_datetime_info={
            "year": 2026,
            "month": 6,
            "day": 4,
            "hour": 23,
            "minute": 28,
            "second": 8,
            "isoweekday": 4,
        },
    )
    assert result == 1780704000.0


def test_resolve_search_window_contract_bounds_latest_reminder_at_now() -> None:
    request = ToolGenerationRequest(
        scenario_name="modify_reminder_with_recency_latest",
        observation="Need search kwargs for latest reminder recency.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="resolve_search_window_or_bounds",
    )
    tool = _resolve_search_window_or_bounds_contract_tool(request)

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1700000000.0,
                    "phrase": "latest",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "latest",
                    "content_keyword": "",
                    "lookback_days": 7,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1699395200.0,
                        "creation_timestamp_upperbound": 1700000000.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "latest",
                    "bounds_source": "resolved_direction",
                },
            ),
            ToolExample(
                {
                    "current_timestamp": 1700000000.0,
                    "phrase": "most recent",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder_creation",
                    "direction": "latest",
                    "content_keyword": "",
                    "lookback_days": 7,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1699395200.0,
                        "creation_timestamp_upperbound": 1700000000.0,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "latest",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
        ),
    )

    assert validation.accepted, validation.errors


def test_resolve_search_window_contract_abstains_on_missing_current_timestamp() -> None:
    request = ToolGenerationRequest(
        scenario_name="modify_reminder_with_recency_latest",
        observation="Need search kwargs for latest reminder recency.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="resolve_search_window_or_bounds",
    )
    tool = _resolve_search_window_or_bounds_contract_tool(request)
    namespace: dict[str, object] = {}
    exec(tool.code, namespace)

    result = namespace["resolve_search_window_or_bounds"](
        current_timestamp=None,
        phrase="upcoming",
        target_domain="reminder",
        timestamp_intent="reminder",
        direction="upcoming",
    )

    assert result == {
        "target_tool_name": "",
        "search_kwargs": {},
        "should_call_search": False,
        "abstain_reason": "missing_current_timestamp",
        "interpretation": "",
        "bounds_source": "abstain",
    }


def test_resolve_search_window_contract_todo_made_yesterday_uses_creation_bounds() -> (
    None
):
    request = ToolGenerationRequest(
        scenario_name="search_reminder_with_creation_recency_yesterday",
        observation="Need search kwargs for reminder creation recency.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="resolve_search_window_or_bounds",
    )
    tool = _resolve_search_window_or_bounds_contract_tool(request)

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1780826317.936844,
                    "phrase": "reminder created yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "custom",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1780739797.936844,
                        "creation_timestamp_upperbound": 1780740037.936844,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
            ),
            ToolExample(
                {
                    "current_timestamp": 1780826317.936844,
                    "phrase": "todo item I made yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "search",
                    "direction": "custom",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1780739797.936844,
                        "creation_timestamp_upperbound": 1780740037.936844,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
            ),
        ),
    )

    assert validation.accepted, validation.errors


def test_resolve_search_window_contract_distinguishes_creation_intent_from_bare_phrase() -> (
    None
):
    request = ToolGenerationRequest(
        scenario_name="search_reminder_with_recency_yesterday",
        observation="Need search kwargs for reminder due recency.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="resolve_search_window_or_bounds",
    )
    tool = _resolve_search_window_or_bounds_contract_tool(request)

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "todo item I made yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1780816770.56798,
                        "creation_timestamp_upperbound": 1780817010.56798,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
            ),
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                    "content_keyword": "Company SF",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "creation_timestamp_lowerbound": 1780816770.56798,
                        "creation_timestamp_upperbound": 1780817010.56798,
                        "content": "Company SF",
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "reminder yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1780816770.56798,
                        "reminder_timestamp_upperbound": 1780817010.56798,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "made yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1780816770.56798,
                        "reminder_timestamp_upperbound": 1780817010.56798,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
        ),
    )

    assert validation.accepted, validation.errors


def test_resolve_search_window_contract_reminder_yesterday_message_creation_alias_uses_due_bounds() -> (
    None
):
    request = ToolGenerationRequest(
        scenario_name="search_reminder_with_recency_yesterday",
        observation="Need search kwargs for reminder due recency.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="resolve_search_window_or_bounds",
    )
    tool = _resolve_search_window_or_bounds_contract_tool(request)

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "message_creation",
                    "direction": "oldest",
                    "content_keyword": "Company SF",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1780816770.56798,
                        "reminder_timestamp_upperbound": 1780817010.56798,
                        "content": "Company SF",
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
            ),
            ToolExample(
                {
                    "current_timestamp": 1780903290.56798,
                    "phrase": "todo from yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "message_creation",
                    "direction": "yesterday",
                    "content_keyword": "",
                    "lookback_days": 1,
                    "timezone_offset": 0.0,
                },
                {
                    "target_tool_name": "search_reminder",
                    "search_kwargs": {
                        "reminder_timestamp_lowerbound": 1780816770.56798,
                        "reminder_timestamp_upperbound": 1780817010.56798,
                    },
                    "should_call_search": True,
                    "abstain_reason": "",
                    "interpretation": "yesterday",
                    "bounds_source": "resolved_direction",
                },
                held_out=True,
            ),
        ),
    )

    assert validation.accepted, validation.errors


def test_message_content_selector_dedupes_identical_timestamp_records(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="search_message_with_recency_latest",
        observation="Need deterministic message recency content selection.",
        allowed_families=("search_filter_ranking_helper",),
        suggested_tool_name="select_message_content_by_recency",
    )

    tool = generator.generate(request)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "p1",
                            "recipient_person_id": "self",
                            "content": "Same visible content",
                            "creation_timestamp": 20.0,
                        },
                        {
                            "message_id": "m1",
                            "sender_person_id": "p1",
                            "recipient_person_id": "self",
                            "content": "Same visible content",
                            "creation_timestamp": 20.0,
                        },
                    ],
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "recipient_person_id": "self",
                        "content": "Same visible content",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message": {
                        "message_id": "m1",
                        "sender_person_id": "p1",
                        "recipient_person_id": "self",
                        "content": "Same visible content",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message_id": "m1",
                    "selected_content": "Same visible content",
                    "selected_timestamp": 20.0,
                    "should_answer": True,
                    "abstain_reason": "",
                    "tie_candidates": [],
                    "selection_reason": (
                        "selected_latest_message_by_creation_timestamp_at_index_0"
                    ),
                    "exact_final_answer": (
                        "Your most recent message says 'Same visible content'."
                    ),
                    "final_answer_recommendation": (
                        "Your most recent message says 'Same visible content'."
                    ),
                    "copy_exactly": True,
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "old",
                            "content": "Earlier message",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "new",
                            "content": "Later message",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {
                        "message_id": "new",
                        "content": "Later message",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message": {
                        "message_id": "new",
                        "content": "Later message",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message_id": "new",
                    "selected_content": "Later message",
                    "selected_timestamp": 30.0,
                    "should_answer": True,
                    "abstain_reason": "",
                    "tie_candidates": [],
                    "selection_reason": (
                        "selected_latest_message_by_creation_timestamp_at_index_1"
                    ),
                    "exact_final_answer": (
                        "Your most recent message says 'Later message'."
                    ),
                    "final_answer_recommendation": (
                        "Your most recent message says 'Later message'."
                    ),
                    "copy_exactly": True,
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "a",
                            "content": "First",
                            "creation_timestamp": 20.0,
                        },
                        {
                            "message_id": "b",
                            "content": "Second",
                            "creation_timestamp": 20.0,
                        },
                    ],
                    "selection_mode": "latest",
                },
                {
                    "selected_record": {},
                    "selected_message": {},
                    "selected_message_id": "",
                    "selected_content": "",
                    "selected_timestamp": 20.0,
                    "should_answer": False,
                    "abstain_reason": "ambiguous_timestamp_tie",
                    "tie_candidates": [
                        {
                            "message_id": "a",
                            "content": "First",
                            "creation_timestamp": 20.0,
                        },
                        {
                            "message_id": "b",
                            "content": "Second",
                            "creation_timestamp": 20.0,
                        },
                    ],
                    "selection_reason": "",
                    "exact_final_answer": "",
                    "final_answer_recommendation": ("abstain:ambiguous_timestamp_tie"),
                    "copy_exactly": False,
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert validation.accepted, validation.errors


def test_state_precondition_repair_handles_visible_not_called_memory(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="cellular_off",
        observation="Need an exact next service setter call.",
        allowed_families=("state_precondition_helper",),
        suggested_tool_name="next_service_tool_call",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="next_service_tool_call",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            description="Rejected service helper.",
            inputs=(ToolInput("target_service", "str", "service"),),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "enum": ["", "set_cellular_service_status"],
                    },
                    "arguments": {"type": "object"},
                    "should_call": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
            positive_triggers=("cellular disabled",),
            negative_triggers=("already_ready",),
            preserves_side_effect_tools=("set_cellular_service_status",),
            required_original_tool_calls=("set_cellular_service_status",),
            abstain_behavior="Abstain when already ready.",
            generalization_rationale="Service preconditions recur.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("cellular_off", "wifi_off"),
            reason_tool_is_decisive="It prepares the next setter call.",
            diagnostic_only=False,
            shortfall_cluster_evidence=("state_precondition",),
            known_failure_mechanisms_addressed=("trace_compatible_service_call",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Service helper was visible but not called.",
                signals=("failed_base_tool_with_deterministic_fallback",),
            ),
        ),
        code=(
            "def next_service_tool_call(target_service: str) -> dict:\n    return {}\n"
        ),
    )

    repaired = generator.repair(
        request,
        rejected,
        ("unresolved_failure_memory:state_precondition_visible_not_called",),
    )

    assert completer.calls == 0
    assert repaired.spec.tool_name == "next_service_tool_call"
    assert (
        "state_precondition_visible_not_called"
        in repaired.spec.known_failure_mechanisms_addressed
    )
    input_names = {item.name for item in repaired.spec.inputs}
    assert {"user_request", "visible_state_or_error", "available_tools"} <= input_names
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "target_service": "cellular",
                    "wifi_enabled": True,
                    "cellular_enabled": False,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": False,
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "cellular is disabled and must be enabled first",
                },
            ),
            ToolExample(
                {
                    "target_service": "location",
                    "wifi_enabled": False,
                    "cellular_enabled": False,
                    "location_service_enabled": False,
                    "low_battery_mode": False,
                    "user_request": "buy chocolate milk at Whole Foods on McKinley Ave",
                    "visible_state_or_error": (
                        "PermissionError: Location service is not enabled."
                    ),
                    "available_tools": [
                        "set_location_service_status",
                        "set_wifi_status",
                    ],
                },
                {
                    "ready": False,
                    "tool_name": "set_location_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "location is disabled and must be enabled first",
                },
            ),
            ToolExample(
                {
                    "target_service": "wifi",
                    "wifi_enabled": False,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": True,
                },
                {
                    "ready": False,
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "wifi cannot be enabled while low battery mode is on",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "target_service": "location",
                    "wifi_enabled": True,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": True,
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "location is already enabled",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_device_state_sequence_abstains_when_target_already_off(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="cellular_off_3_distraction_tools",
        observation="Need exact device-state setter planning without redundant calls.",
        allowed_families=("state_precondition_helper",),
        suggested_tool_name="plan_device_state_action_sequence_v3",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": "Turn off cellular",
                    "visible_state_or_error": "",
                },
                {
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "set_cellular_off",
                    "action_sequence": [
                        {
                            "tool_name": "set_cellular_service_status",
                            "arguments": {"on": False},
                            "reason": "set_cellular_off",
                        }
                    ],
                    "final_response_recommendation": (
                        "Cellular service has been turned off."
                    ),
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": "Turn off cellular service",
                    "visible_state_or_error": "Cellular service is currently off.",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "cellular_already_off",
                    "action_sequence": [],
                    "final_response_recommendation": (
                        "Cellular service is already off."
                    ),
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "already_in_desired_state",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Ensure cellular service stays off",
                    "visible_state_or_error": "Cellular service has been turned off.",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "cellular_already_off",
                    "action_sequence": [],
                    "final_response_recommendation": (
                        "Cellular service is already off."
                    ),
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "already_in_desired_state",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Tell me the time",
                    "visible_state_or_error": "",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "no_device_state_target",
                    "action_sequence": [],
                    "final_response_recommendation": "",
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "no_device_state_target",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert result.accepted, result.errors


def test_device_state_sequence_clears_low_battery_for_downstream_service_error(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name=(
            "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode"
        ),
        observation=(
            "A downstream reminder/location task is blocked by device state and "
            "needs a generated setter sequence before continuing the original task."
        ),
        allowed_families=("state_precondition_helper",),
        suggested_tool_name="plan_device_state_action_sequence_v3",
    )

    tool = generator.generate(request)
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "user_request": (
                        "Add a reminder to buy chocolate milk at Whole Foods."
                    ),
                    "visible_state_or_error": (
                        "Location service cannot be turned on in low battery mode."
                    ),
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_location_service_status",
                            "arguments": {"on": True},
                            "reason": "set_location_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "user_request": (
                        "Add a reminder to buy chocolate milk at Whole Foods."
                    ),
                    "visible_state_or_error": (
                        "PermissionError: Location service is not enabled."
                    ),
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_location_service_status",
                            "arguments": {"on": True},
                            "reason": "set_location_on",
                        },
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": ("enable_wifi_for_downstream_location_search"),
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Search for the current weather near me.",
                    "visible_state_or_error": "Wifi is not enabled.",
                },
                {
                    "tool_name": "set_wifi_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "set_wifi_on",
                    "action_sequence": [
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": "set_wifi_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": (
                        "Add a reminder to buy chocolate milk at Whole Foods."
                    ),
                    "visible_state_or_error": "ConnectionError: Wifi is not enabled",
                    "available_tools": [
                        {
                            "type": "function",
                            "function": {"name": "functions.set_wifi_status"},
                        }
                    ],
                },
                {
                    "tool_name": "set_wifi_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "set_wifi_on",
                    "action_sequence": [
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": "set_wifi_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Search for the current weather near me.",
                    "visible_state_or_error": (
                        "Wifi cannot be turned on in low battery mode."
                    ),
                },
                {
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "clear_low_battery_before_enabling_service",
                    "action_sequence": [
                        {
                            "tool_name": "set_low_battery_mode_status",
                            "arguments": {"on": False},
                            "reason": "clear_low_battery_before_enabling_service",
                        },
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": "set_wifi_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Search for the current weather near me.",
                    "visible_state_or_error": (
                        "Wifi is not enabled. Known state: low battery mode is off."
                    ),
                },
                {
                    "tool_name": "set_wifi_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "set_wifi_on",
                    "action_sequence": [
                        {
                            "tool_name": "set_wifi_status",
                            "arguments": {"on": True},
                            "reason": "set_wifi_on",
                        },
                    ],
                    "final_response_recommendation": "continue_original_task",
                    "continue_original_task_after_sequence": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "user_request": "Tell me the time.",
                    "visible_state_or_error": "",
                },
                {
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "no_device_state_target",
                    "action_sequence": [],
                    "final_response_recommendation": "",
                    "continue_original_task_after_sequence": False,
                    "abstain_reason": "no_device_state_target",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert completer.calls == 0
    assert result.accepted, result.errors


def test_message_counterparty_repair_normalizes_abstain_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="modify_contact_with_message_recency",
        observation="Need deterministic non-self message counterparty selection.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="select_message_counterparty_for_contact_update",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_message_counterparty_for_contact_update",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Rejected counterparty selector.",
            inputs=(ToolInput("records", "list", "records"),),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {"selected_record": {}}},
            positive_triggers=("modify_contact_with_message_recency",),
            negative_triggers=("missing updates",),
            preserves_side_effect_tools=("modify_contact",),
            required_original_tool_calls=("modify_contact",),
            abstain_behavior="Abstain on missing updates.",
            generalization_rationale="Message counterparty selection recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("modify_contact_with_message_recency",),
            reason_tool_is_decisive="It prepares original modify_contact kwargs.",
            shortfall_cluster_evidence=("message_counterparty_update",),
            known_failure_mechanisms_addressed=("wrong_selected_record",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Counterparty selector used a non-machine-readable abstain reason.",
                signals=("negative_example_mismatch",),
            ),
        ),
        code="def select_message_counterparty_for_contact_update(records: list) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(request, rejected, ("negative_0_mismatch",))

    assert completer.calls == 0
    assert repaired.spec.tool_name == "select_message_counterparty_for_contact_update"
    assert "updates: dict," in repaired.code
    assert "updates: dict = {}" not in repaired.code
    assert 'message_direction: str = ""' in repaired.code
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "self",
                            "recipient_person_id": "p2",
                            "recipient_phone_number": "+15550100",
                            "creation_timestamp": 20.0,
                        }
                    ],
                    "selection_mode": "latest",
                    "updates": {"phone_number": "+15550999"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {
                        "message_id": "m1",
                        "sender_person_id": "self",
                        "recipient_person_id": "p2",
                        "recipient_phone_number": "+15550100",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message": {
                        "message_id": "m1",
                        "sender_person_id": "self",
                        "recipient_person_id": "p2",
                        "recipient_phone_number": "+15550100",
                        "creation_timestamp": 20.0,
                    },
                    "selected_message_id": "m1",
                    "selected_person_id": "p2",
                    "selected_phone_number": "+15550100",
                    "selected_timestamp": 20.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p2",
                        "phone_number": "+15550999",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m_old",
                            "sender_person_id": "p_old",
                            "sender_phone_number": "+15550111",
                            "recipient_person_id": "self",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "m_new",
                            "sender_person_id": "self",
                            "recipient_person_id": "p_new",
                            "recipient_phone_number": "+15550222",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "oldest",
                    "updates": {"relationship": "friend"},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {
                        "message_id": "m_old",
                        "sender_person_id": "p_old",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message": {
                        "message_id": "m_old",
                        "sender_person_id": "p_old",
                        "sender_phone_number": "+15550111",
                        "recipient_person_id": "self",
                        "creation_timestamp": 10.0,
                    },
                    "selected_message_id": "m_old",
                    "selected_person_id": "p_old",
                    "selected_phone_number": "+15550111",
                    "selected_timestamp": 10.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p_old",
                        "relationship": "friend",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m_latest",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_latest",
                            "recipient_phone_number": "+15550222",
                            "content": "Latest outgoing",
                            "creation_timestamp": 30.0,
                        },
                        {
                            "message_id": "m_latest",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_latest",
                            "recipient_phone_number": "+15550222",
                            "content": "Latest outgoing",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "latest",
                    "updates": {"phone_number": "+15550999"},
                    "self_person_id": "",
                    "message_direction": "sent",
                },
                {
                    "selected_record": {
                        "message_id": "m_latest",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_latest",
                        "recipient_phone_number": "+15550222",
                        "content": "Latest outgoing",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message": {
                        "message_id": "m_latest",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_latest",
                        "recipient_phone_number": "+15550222",
                        "content": "Latest outgoing",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message_id": "m_latest",
                    "selected_person_id": "p_latest",
                    "selected_phone_number": "+15550222",
                    "selected_timestamp": 30.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p_latest",
                        "phone_number": "+15550999",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m_old",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_old",
                            "recipient_phone_number": "+15550111",
                            "creation_timestamp": 10.0,
                        },
                        {
                            "message_id": "m_new",
                            "sender_person_id": "self",
                            "sender_phone_number": "+15550000",
                            "recipient_person_id": "p_new",
                            "recipient_phone_number": "+15550222",
                            "creation_timestamp": 30.0,
                        },
                    ],
                    "selection_mode": "latest",
                    "updates": {"phone_number": "+15550999"},
                    "self_person_id": "self-typo",
                },
                {
                    "selected_record": {
                        "message_id": "m_new",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_new",
                        "recipient_phone_number": "+15550222",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message": {
                        "message_id": "m_new",
                        "sender_person_id": "self",
                        "sender_phone_number": "+15550000",
                        "recipient_person_id": "p_new",
                        "recipient_phone_number": "+15550222",
                        "creation_timestamp": 30.0,
                    },
                    "selected_message_id": "m_new",
                    "selected_person_id": "p_new",
                    "selected_phone_number": "+15550222",
                    "selected_timestamp": 30.0,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p_new",
                        "phone_number": "+15550999",
                    },
                    "should_call_tool": True,
                    "tie_candidates": [],
                    "abstain_reason": "",
                    "safety_notes": "call modify_contact with downstream_tool_kwargs",
                    "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "message_id": "m1",
                            "sender_person_id": "self",
                            "recipient_person_id": "p2",
                            "recipient_phone_number": "+15550100",
                            "creation_timestamp": 20.0,
                        }
                    ],
                    "selection_mode": "latest",
                    "updates": {},
                    "self_person_id": "self",
                },
                {
                    "selected_record": {},
                    "selected_message": {},
                    "selected_message_id": "",
                    "selected_person_id": "",
                    "selected_phone_number": "",
                    "selected_timestamp": 0.0,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "missing_updates",
                    "safety_notes": "abstain; no safe contact update target",
                    "final_answer_recommendation": "abstain:missing_updates",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_action_selector_preserves_unique_modify_target_without_updates(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="visible_task_context(family=recency_action)",
        observation="Need to select the visible reminder target before a side effect.",
        allowed_families=("search_filter_ranking_helper",),
        suggested_tool_name="select_action_target_by_recency",
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Rejected recency selector.",
            inputs=(ToolInput("records", "list", "records"),),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                },
            },
            positive_triggers=("recency_action",),
            negative_triggers=("ambiguous_tie",),
            preserves_side_effect_tools=("modify_reminder",),
            required_original_tool_calls=("modify_reminder",),
            abstain_behavior="Abstain on ambiguity.",
            generalization_rationale="Recency target selection recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("recency_action",),
            reason_tool_is_decisive="It selects a visible action target by recency.",
            diagnostic_only=True,
            known_failure_mechanisms_addressed=("target_selection_loss",),
        ),
        code="def select_action_target_by_recency(records: list) -> dict:\n    return {}\n",
    )

    repaired = generator.repair(
        request,
        rejected,
        ("action_selector_missing_downstream_kwargs_contract",),
    )

    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "old",
                            "creation_timestamp": 10.0,
                            "reminder_timestamp": 100.0,
                        },
                        {
                            "reminder_id": "new",
                            "creation_timestamp": 20.0,
                            "reminder_timestamp": 200.0,
                        },
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {
                        "reminder_id": "new",
                        "creation_timestamp": 20.0,
                        "reminder_timestamp": 200.0,
                    },
                    "selected_index": 1,
                    "selected_id": "new",
                    "selected_timestamp": 20.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "modify_reminder",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "missing_update_fields",
                    "safety_notes": (
                        "selected target only; call the original side-effect only "
                        "after required mutation fields are available"
                    ),
                    "final_answer_recommendation": (
                        "use_selected_record:modify_reminder:reminder_id=new; "
                        "supply required update fields from visible context before "
                        "calling the original tool"
                    ),
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "reminder_id": "first",
                            "creation_timestamp": 30.0,
                            "reminder_timestamp": 300.0,
                        },
                        {
                            "reminder_id": "second",
                            "creation_timestamp": 40.0,
                            "reminder_timestamp": 400.0,
                        },
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {
                        "reminder_id": "second",
                        "creation_timestamp": 40.0,
                        "reminder_timestamp": 400.0,
                    },
                    "selected_index": 1,
                    "selected_id": "second",
                    "selected_timestamp": 40.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "modify_reminder",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "missing_update_fields",
                    "safety_notes": (
                        "selected target only; call the original side-effect only "
                        "after required mutation fields are available"
                    ),
                    "final_answer_recommendation": (
                        "use_selected_record:modify_reminder:reminder_id=second; "
                        "supply required update fields from visible context before "
                        "calling the original tool"
                    ),
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                    "action_type": "modify_reminder",
                    "constraints": {},
                    "updates": {},
                },
                {
                    "selected_record": {},
                    "selected_index": -1,
                    "selected_id": "",
                    "selected_timestamp": 0.0,
                    "action_type": "modify_reminder",
                    "downstream_tool_name": "modify_reminder",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "tie_candidates": [],
                    "abstain_reason": "no_records",
                    "safety_notes": "do not guess before side-effect action",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_side_effect_args_generation_allows_remove_without_updates(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="remove_contact_by_phone",
        observation="Need selected records translated into side-effect kwargs.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_side_effect_args_from_selected_record",
    )

    tool = generator.generate(request)

    assert completer.calls == 0
    assert tool.spec.tool_name == "prepare_side_effect_args_from_selected_record"
    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "selected_record": {"person_id": "p1", "phone_number": "+15550100"},
                    "action_type": "remove_contact",
                    "updates": {},
                    "user_intent": "remove contact",
                },
                {
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "p1"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "selected_record": {"person_id": "p1", "phone_number": "+15550100"},
                    "action_type": "remove",
                    "updates": {},
                    "user_intent": "delete that contact entirely",
                },
                {
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "p1"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "selected_record": {"person_id": "p1"},
                    "action_type": "modify_contact",
                    "updates": {"phone_number": "+15550200"},
                    "user_intent": "update contact",
                },
                {
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "p1",
                        "phone_number": "+15550200",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "selected_record": {"person_id": "p1"},
                    "action_type": "modify_contact",
                    "updates": {},
                    "user_intent": "update contact",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "missing_update_fields",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_message_counterparty_search_generation_uses_deterministic_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="modify_contact_with_message_recency",
        observation="Need deterministic self-id lookup before message search.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="plan_message_counterparty_search",
    )

    tool = generator.generate(request)

    assert completer.calls == 0
    assert tool.spec.tool_name == "plan_message_counterparty_search"
    assert tool.spec.required_original_tool_calls == ("search_messages",)

    def counterparty_expected(payload: dict) -> dict:
        expected = {
            "selected_message": {},
            "counterparty_phone_number": "",
            "answer_value": "",
            "exact_final_answer": "",
            "final_answer_recommendation": "",
            "copy_exactly": False,
        }
        expected.update(payload)
        return expected

    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "message_direction": "sent",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "self_lookup_required",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": True,
                        "search_contacts_kwargs": {"is_self": True},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_contacts, then call this helper again with self_person_id",
                    }
                ),
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "oldest",
                    "self_person_id": "self-id",
                    "content_keyword": "invoice",
                },
                counterparty_expected(
                    {
                        "phase": "message_search_required",
                        "message_direction": "received",
                        "selection_mode": "oldest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": True,
                        "search_messages_kwargs": {
                            "recipient_person_id": "self-id",
                            "content": "invoice",
                        },
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_messages with search_messages_kwargs",
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "GPUs",
                },
                counterparty_expected(
                    {
                        "phase": "message_search_required",
                        "message_direction": "received",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": True,
                        "search_messages_kwargs": {"content": "GPUs"},
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_messages with search_messages_kwargs",
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "GPUs",
                    "messages": [
                        {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        }
                    ],
                },
                counterparty_expected(
                    {
                        "phase": "answer_ready",
                        "message_direction": "received",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "",
                        "next_step": "answer with final_answer_recommendation",
                        "selected_message": {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        },
                        "counterparty_phone_number": "+18307976530",
                        "answer_value": "+18307976530",
                        "exact_final_answer": "+18307976530 asked you if you want some GPUs",
                        "final_answer_recommendation": "+18307976530 asked you if you want some GPUs",
                        "copy_exactly": True,
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "outgoing",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                    "messages": [
                        {
                            "sender_person_id": "other-id",
                            "sender_phone_number": "+10000000000",
                            "recipient_person_id": "self-id",
                            "recipient_phone_number": "+11233344455",
                            "content": "Good, keep me posted",
                            "creation_timestamp": 1781283797.0,
                        }
                    ],
                },
                counterparty_expected(
                    {
                        "phase": "answer_ready",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "",
                        "next_step": "answer with final_answer_recommendation",
                        "selected_message": {
                            "sender_person_id": "other-id",
                            "sender_phone_number": "+10000000000",
                            "recipient_person_id": "self-id",
                            "recipient_phone_number": "+11233344455",
                            "content": "Good, keep me posted",
                            "creation_timestamp": 1781283797.0,
                        },
                        "counterparty_phone_number": "+10000000000",
                        "answer_value": "+10000000000",
                        "exact_final_answer": "+10000000000",
                        "final_answer_recommendation": "+10000000000",
                        "copy_exactly": True,
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "received",
                    "selection_mode": "latest",
                    "self_person_id": "",
                    "content_keyword": "",
                    "messages": [
                        {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        }
                    ],
                },
                counterparty_expected(
                    {
                        "phase": "answer_ready",
                        "message_direction": "received",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "",
                        "next_step": "answer with final_answer_recommendation",
                        "selected_message": {
                            "sender_phone_number": "+18307976530",
                            "recipient_phone_number": "+11233344455",
                            "content": "Hey kid, you want some GPU?",
                            "creation_timestamp": 1781008782.0,
                        },
                        "counterparty_phone_number": "+18307976530",
                        "answer_value": "+18307976530",
                        "exact_final_answer": "+18307976530 asked you if you want some GPU",
                        "final_answer_recommendation": "+18307976530 asked you if you want some GPU",
                        "copy_exactly": True,
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "sent/outgoing/from_me",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "message_search_required",
                        "message_direction": "sent",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": True,
                        "search_messages_kwargs": {"sender_person_id": "self-id"},
                        "should_call_tool": True,
                        "abstain_reason": "",
                        "next_step": "call search_messages with search_messages_kwargs",
                    }
                ),
                held_out=True,
            ),
            ToolExample(
                {
                    "message_direction": "either",
                    "selection_mode": "latest",
                    "self_person_id": "self-id",
                    "content_keyword": "",
                },
                counterparty_expected(
                    {
                        "phase": "abstain",
                        "message_direction": "either",
                        "selection_mode": "latest",
                        "should_call_search_contacts": False,
                        "search_contacts_kwargs": {},
                        "should_call_search_messages": False,
                        "search_messages_kwargs": {},
                        "should_call_tool": False,
                        "abstain_reason": "ambiguous_message_direction",
                        "next_step": "ask_for_sent_or_received_direction",
                    }
                ),
                negative_applicability=True,
            ),
        ),
    )
    assert result.accepted, result.errors


def test_contact_update_from_id_repair_uses_dict_contract(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="update_contact_with_id_and_phone_number",
        observation="Need deterministic modify_contact kwargs from visible scalar id update.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="plan_contact_update_from_id",
        inadequacy_evidence={
            "summary": "Contact id update planner failed validation.",
            "signals": ("side_effect_argument_preparation_failure",),
            "failed_tool_calls": ("modify_contact",),
        },
    )
    rejected = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_contact_update_from_id",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Rejected contact update planner.",
            inputs=(
                ToolInput("person_id", "str", "Stable contact id."),
                ToolInput("phone_number", "str", "New phone number."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {"downstream_tool_kwargs": {"type": "object"}},
            },
            positive_triggers=("update_contact_with_id_and_phone_number",),
            negative_triggers=("missing person id",),
            preserves_side_effect_tools=("modify_contact",),
            required_original_tool_calls=("modify_contact",),
            abstain_behavior="Abstain when person id is missing.",
            generalization_rationale="Contact id updates recur.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("update_contact_with_id_and_phone_number",),
            reason_tool_is_decisive="It prepares original modify_contact kwargs.",
            shortfall_cluster_evidence=("contact_id_update_argument_planning",),
            known_failure_mechanisms_addressed=(
                "side_effect_argument_preparation_failure",
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Contact id update planner failed validation.",
                signals=("side_effect_argument_preparation_failure",),
            ),
        ),
        code=(
            "def plan_contact_update_from_id(person_id: str, "
            "phone_number: str) -> object:\n    return {}\n"
        ),
    )

    repaired = generator.repair(
        request,
        rejected,
        ("return_annotation_mismatch:object!=dict",),
    )

    assert completer.calls == 0
    assert repaired.spec.tool_name == "plan_contact_update_from_id"
    assert "-> dict" in repaired.code
    result = validate_generated_tool(
        repaired,
        examples=(
            ToolExample(
                {
                    "person_id": "9e137f06-916a-5310-8174-cf0b7e9f7054",
                    "phone_number": "+1 (987) 654-3210",
                    "name": "",
                    "relationship": "",
                    "user_request": "Update phone number for this contact",
                },
                {
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "9e137f06-916a-5310-8174-cf0b7e9f7054",
                        "phone_number": "+19876543210",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "person_id": "",
                    "phone_number": "+19876543210",
                    "name": "",
                    "relationship": "",
                    "user_request": "Update phone number for this contact",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "missing_person_id",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "person_id": "9e137f06-916a-5310-8174-cf0b7e9f7054",
                    "phone_number": "+19876543210",
                    "name": "",
                    "relationship": "",
                    "user_request": "Remove contact with this id",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "not_contact_update_task",
                },
                negative_applicability=True,
            ),
        ),
    )

    assert result.accepted, result.errors


def test_direct_contact_action_generation_supports_remove_and_send(
    tmp_path: Path,
) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="remove_contact_with_id",
        observation="Need direct scalar side-effect kwargs from visible inputs.",
        allowed_families=("composite_workflow_helper",),
        suggested_tool_name="prepare_direct_contact_action_args",
        inadequacy_evidence={
            "summary": "Direct scalar contact action failed without a generated planner.",
            "signals": ("side_effect_argument_preparation_failure",),
            "failed_tool_calls": (
                "remove_contact",
                "send_message_with_phone_number",
            ),
        },
    )

    tool = generator.generate(request)

    assert completer.calls == 0
    assert tool.spec.tool_name == "prepare_direct_contact_action_args"
    assert "remove_contact_with_id" in tool.spec.applicable_task_families
    assert "send_message_with_phone_number_and_content" in (
        tool.spec.applicable_task_families
    )

    result = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "action_type": "remove_contact",
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "",
                    "record_id": "person-123",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "",
                    "user_request": "Remove contact id person-123",
                },
                {
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "person-123"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {
                    "action_type": "send_message",
                    "contact_name": "",
                    "phone_number": "+1 (555) 0100",
                    "relationship": "",
                    "record_id": "",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "Running late",
                    "user_request": "Send +1 (555) 0100 Running late",
                },
                {
                    "downstream_tool_name": "send_message_with_phone_number",
                    "downstream_tool_kwargs": {
                        "phone_number": "+15550100",
                        "content": "Running late",
                    },
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "action_type": "send_message",
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": "",
                    "record_id": "",
                    "target_field": "",
                    "new_value": "",
                    "message_text": "Hello",
                    "user_request": "Search messages with content Hello",
                },
                {
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                    "should_call_tool": False,
                    "abstain_reason": "not_direct_scalar_contact_action",
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
