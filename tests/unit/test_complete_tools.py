import json
from dataclasses import replace

from sage_ts.adequacy.inadequacy_classifier import (
    _message_counterparty_contact_update_observation,
    _recency_action_target_observation,
    _reminder_optional_location_argument_observation,
    _single_device_state_action_observation,
)
from sage_ts.generation.complete_tools import native_action_tool_enabled
from sage_ts.generation.tool_generator import (
    ToolGenerationRequest,
    _model_authored_final_repair_directive,
    _model_authored_generation_prompt,
    _model_authored_repair_analysis_prompt,
    _model_authored_repair_prompt,
    _native_action_behavior_summary,
    _native_action_validation_examples,
    _normalize_model_authored_tool,
    _request_complete_tools_enabled,
    _request_native_action_names,
    _tool_examples_from_request,
    _validation_error_distance,
    parse_generated_tool_candidates_json,
)
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime.toolsandbox_integration import (
    _native_action_google_docstring,
    compile_toolsandbox_tool,
    route_registry_entries,
)
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    ValidationResult,
    validate_generated_tool,
)
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    new_context,
)


def _native_add_contact_tool(code: str) -> GeneratedTool:
    return GeneratedTool(
        spec=ToolSpec(
            tool_name="complete_add_contact",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description=(
                "Normalize a visible contact request and delegate the final creation "
                "to the preserved native contact action."
            ),
            inputs=(
                ToolInput("name", "str", "Visible contact name."),
                ToolInput("phone_number", "str", "Visible phone number."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("visible_name_and_phone",),
            negative_triggers=("missing_name_or_phone",),
            preserves_side_effect_tools=("add_contact",),
            required_original_tool_calls=("add_contact",),
            native_action_delegation=True,
            abstain_behavior="Call no native action when name or phone is missing.",
            generalization_rationale=(
                "The same visible name and phone normalization recurs across contact "
                "creation requests."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("contact_creation", "contact_import"),
            reason_tool_is_decisive=(
                "It turns visible contact fields into one validated native action."
            ),
            shortfall_cluster_evidence=("contact_creation_argument_failure",),
            known_failure_mechanisms_addressed=("wrong_contact_action",),
            final_state_preservation_plan=(
                "The generated tool delegates to the native add_contact implementation."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Visible contact values were not reaching the native action.",
                signals=("final_action_argument_preparation",),
            ),
        ),
        code=code,
    )


def test_native_action_candidate_distance_prefers_near_argument_match() -> None:
    near_match = (
        "source_0_native_action_arguments:{'person_id': 'p1', "
        "'phone_number': '+1555', 'relationship': None}!="
        "{'person_id': 'p1', 'phone_number': '+1555', "
        "'relationship': NOT_GIVEN}"
    )
    missing_action = (
        "source_0_native_action_count:0!=1:expected=modify_contact:{'person_id': 'p1'}"
    )

    assert _validation_error_distance((near_match,)) < _validation_error_distance(
        (missing_action,)
    )


def test_native_action_behavior_summary_keeps_gap_logic_not_planner_contract() -> None:
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation=(
            "The agent selects the wrong record. Generate a deterministic "
            "side-effect-free helper. Inputs must be records and self_person_id. "
            "It must identify the non-self person, and return a final-action-ready "
            "modify_contact plan. Return exactly downstream_tool_name and kwargs. "
            "The helper must never call modify_contact; it only prepares the call. "
            "Abstain on missing records. Include modify_contact in "
            "required_original_tool_calls and preserves_side_effect_tools."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
    )

    summary = _native_action_behavior_summary(request)

    assert "native-action tool" in summary
    assert "identify the non-self person" in summary
    assert "Abstain on missing records" in summary
    assert "Return exactly" not in summary
    assert "must never call" not in summary
    assert "required_original_tool_calls" not in summary


def _examples() -> tuple[ToolExample, ...]:
    return (
        ToolExample(
            {"name": "Avery Stone", "phone_number": "+1 555 0100"},
            {
                "should_call_downstream_tool": True,
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Avery Stone",
                    "phone_number": "+15550100",
                },
            },
        ),
        ToolExample(
            {"name": "Jordan Lee", "phone_number": "+1 555 0111"},
            {
                "should_call_downstream_tool": True,
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Jordan Lee",
                    "phone_number": "+15550111",
                },
            },
            held_out=True,
        ),
        ToolExample(
            {"name": "Morgan", "phone_number": ""},
            {
                "should_call_downstream_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
            },
            negative_applicability=True,
        ),
    )


def test_generation_request_detects_declared_native_action(monkeypatch) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="The visible contact fields need one native contact action.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="complete_add_contact",
        validation_examples=(
            {
                "inputs": {"name": "Avery Stone", "phone_number": "+15550100"},
                "expected": {
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Avery Stone",
                        "phone_number": "+15550100",
                    },
                },
            },
            {
                "inputs": {"name": "Jordan Lee", "phone_number": "+15550111"},
                "expected": {
                    "should_call_downstream_tool": True,
                    "downstream_tool_name": "add_contact",
                    "downstream_tool_kwargs": {
                        "name": "Jordan Lee",
                        "phone_number": "+15550111",
                    },
                },
                "held_out": True,
            },
            {
                "inputs": {"name": "Morgan", "phone_number": ""},
                "expected": {
                    "should_call_downstream_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                },
                "negative_applicability": True,
            },
        ),
    )

    assert _request_native_action_names(request) == ("add_contact",)
    assert _request_complete_tools_enabled(request)
    projected = _native_action_validation_examples(request)
    assert [item["case_label"] for item in projected] == [
        "source_0",
        "held_out_0",
        "negative_0",
    ]
    assert projected[0]["expected_native_action"] == {
        "name": "add_contact",
        "arguments": {
            "name": "Avery Stone",
            "phone_number": "+15550100",
        },
        "argument_value_locations": {
            "name": ["inputs.name"],
            "phone_number": ["inputs.phone_number"],
        },
    }
    assert projected[2]["expected_native_action"] is None
    unmarked = _native_add_contact_tool(
        "def complete_add_contact(name: str, phone_number: str) -> dict:\n"
        "    return {'abstain_reason': 'diagnostic'}\n"
    )
    unmarked = replace(
        unmarked,
        spec=replace(unmarked.spec, native_action_delegation=False),
    )
    assert _normalize_model_authored_tool(
        request, unmarked
    ).spec.native_action_delegation
    prompt = _model_authored_generation_prompt(request)
    assert '"validation_contract": "native_action_delegation"' in prompt
    assert '"expected_native_action"' in prompt
    assert '"should_call_downstream_tool"' not in prompt
    assert "Do not reproduce the former should_call/kwargs planning object" in prompt
    assert "Every positive case is valid by contract" in prompt
    assert "Derive abstention conditions from negative examples" in prompt
    assert "remove blank values and the self value" not in prompt
    assert "Any guard that tests one role equals self" not in prompt
    assert "any non-None entry as actionable" in prompt


def test_search_filter_action_contract_can_delegate_native_action(monkeypatch) -> None:
    observation = _recency_action_target_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="select_action_target_by_recency",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )

    assert set(_request_native_action_names(request)) == {
        "modify_reminder",
        "remove_reminder",
    }
    assert _request_complete_tools_enabled(request)
    projected = _native_action_validation_examples(request)
    assert any(
        item.get("held_out")
        and item.get("inputs", {}).get("action_type") == "modify"
        and item.get("expected_native_action", {}).get("name") == "modify_reminder"
        for item in projected
    )
    target_override = next(
        item
        for item in projected
        if str(item.get("case_label", "")).startswith("held_out_target_override_")
    )
    assert target_override["inputs"]["updates"]["reminder_id"] == "r-old"
    assert (
        target_override["expected_native_action"]["arguments"]["reminder_id"] == "r-new"
    )
    prompt = _model_authored_generation_prompt(request)
    assert "latest selects the unique maximum" in prompt
    assert "oldest selects the unique minimum" in prompt
    assert "Do not default both modes to max" in prompt
    assert "A target identifier is not an update field" in prompt
    assert "Never allow an updates mapping to replace that selected identity" in prompt
    assert any(
        item.get("held_out")
        and item.get("inputs", {}).get("action_type") == "remove"
        and item.get("expected_native_action", {}).get("name") == "remove_reminder"
        for item in projected
    )


def test_complete_reminder_contract_uses_normalized_final_action_inputs(
    monkeypatch,
) -> None:
    observation = _reminder_optional_location_argument_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="prepare_reminder_creation_args",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )

    assert _request_complete_tools_enabled(request)
    assert set(observation.validation_examples[0].inputs) == {
        "content",
        "reminder_timestamp",
        "location_requested",
        "location_required",
        "location_available",
        "latitude",
        "longitude",
        "location_lookup_failed",
    }
    projected = _native_action_validation_examples(request)
    positives = [item for item in projected if item["expected_native_action"]]
    negatives = [item for item in projected if item["negative_applicability"]]
    assert len(positives) == 4
    assert len(negatives) >= 4
    assert {item["expected_native_action"]["name"] for item in positives} == {
        "add_reminder"
    }
    prompt = _model_authored_generation_prompt(request)
    assert "optional requested location with lookup_failed=true calls" in prompt
    assert "optional requested location with lookup_failed=false abstains" in prompt
    assert "Do not merge the pending and failed branches" in prompt
    assert "Classify examples by expected_native_action" in prompt
    assert "input name sounds adverse" in prompt


def test_complete_device_contract_executes_exactly_one_native_setter(
    monkeypatch,
) -> None:
    observation = _single_device_state_action_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="apply_single_device_state_action",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )

    assert set(_request_native_action_names(request)) == {
        "set_wifi_status",
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
    }
    projected = _native_action_validation_examples(request)
    assert len([case for case in projected if case["expected_native_action"]]) == 4
    assert len([case for case in projected if case["negative_applicability"]]) == 2
    prompt = _model_authored_generation_prompt(request)
    assert "call exactly one setter" in prompt
    assert "low_battery_mode to set_low_battery_mode_status" in prompt
    assert "do not add prerequisite or recovery actions" in prompt


def test_required_tool_name_repairs_missing_model_spec_name() -> None:
    response = json.dumps(
        {
            "spec": {
                "family": "search_filter_ranking_helper",
                "inputs": [],
                "output_annotation": "dict",
            },
            "code_lines": [
                "def select_action_target_by_recency() -> dict:",
                "    return {}",
            ],
        }
    )

    tools = parse_generated_tool_candidates_json(
        response, default_tool_name="select_action_target_by_recency"
    )

    assert tools[0].spec.tool_name == "select_action_target_by_recency"


def test_string_code_lines_from_model_are_normalized() -> None:
    response = json.dumps(
        {
            "spec": {
                "family": "search_filter_ranking_helper",
                "inputs": [],
                "output_annotation": "dict",
            },
            "code_lines": (
                "def select_action_target_by_recency() -> dict:\n"
                "    return {'status': 'abstain'}\n"
            ),
        }
    )

    tools = parse_generated_tool_candidates_json(
        response, default_tool_name="select_action_target_by_recency"
    )

    assert tools[0].code == (
        "def select_action_target_by_recency() -> dict:\n"
        "    return {'status': 'abstain'}\n"
    )


def test_malformed_model_candidate_does_not_discard_valid_candidate() -> None:
    response = json.dumps(
        {
            "candidates": [
                {
                    "spec": {
                        "family": "search_filter_ranking_helper",
                        "inputs": [],
                        "output_annotation": "dict",
                    }
                },
                {
                    "spec": {
                        "family": "search_filter_ranking_helper",
                        "inputs": [],
                        "output_annotation": "dict",
                    },
                    "code_lines": [
                        "def select_action_target_by_recency() -> dict:",
                        "    return {}",
                    ],
                },
            ]
        }
    )

    tools = parse_generated_tool_candidates_json(
        response, default_tool_name="select_action_target_by_recency"
    )

    assert len(tools) == 1
    assert tools[0].spec.tool_name == "select_action_target_by_recency"


def test_complex_action_contract_remains_standard_generated_tool(monkeypatch) -> None:
    base_inputs = {f"field_{index}": index for index in range(7)}
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="Transform visible fields before the native action.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="prepare_complex_action",
        validation_examples=(
            {
                "inputs": base_inputs,
                "expected": {
                    "should_call_tool": True,
                    "downstream_tool_name": "add_reminder",
                    "downstream_tool_kwargs": {
                        "content": "visible",
                        "reminder_timestamp": 100.0,
                        "latitude": None,
                        "longitude": None,
                    },
                },
            },
            {
                "inputs": {**base_inputs, "field_0": 2},
                "expected": {
                    "should_call_tool": True,
                    "downstream_tool_name": "add_reminder",
                    "downstream_tool_kwargs": {
                        "content": "visible",
                        "reminder_timestamp": 200.0,
                        "latitude": None,
                        "longitude": None,
                    },
                },
                "held_out": True,
            },
            {
                "inputs": {**base_inputs, "field_0": None},
                "expected": {
                    "should_call_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                },
                "negative_applicability": True,
            },
        ),
    )

    assert not _request_complete_tools_enabled(request)
    prompt = _model_authored_generation_prompt(request)
    assert '"validation_contract": "exact_return_value"' in prompt
    assert '"validation_contract": "native_action_delegation"' not in prompt


def test_densely_validated_single_action_contract_can_be_native(monkeypatch) -> None:
    base_inputs = {f"field_{index}": index for index in range(8)}
    positives = tuple(
        {
            "inputs": {**base_inputs, "field_0": index},
            "expected": {
                "should_call_tool": True,
                "downstream_tool_name": "add_reminder",
                "downstream_tool_kwargs": {
                    "content": f"visible-{index}",
                    "reminder_timestamp": float(index + 100),
                },
            },
            "held_out": index >= 2,
        }
        for index in range(4)
    )
    negatives = tuple(
        {
            "inputs": {**base_inputs, "field_0": None, "field_1": index},
            "expected": {
                "should_call_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
            },
            "negative_applicability": True,
        }
        for index in range(2)
    )
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="Map a densely tested visible contract to one native action.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="complete_dense_action",
        validation_examples=(*positives, *negatives),
    )

    assert _request_complete_tools_enabled(request)


def test_multi_action_contract_remains_standard_generated_tool(monkeypatch) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="Apply one visible update to several selected records.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="prepare_batch_update",
        validation_examples=(
            {
                "inputs": {"records": [{"person_id": "p1"}], "update": "friend"},
                "expected": {
                    "should_call_tools": True,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p1", "relationship": "friend"}
                    ],
                },
            },
            {
                "inputs": {"records": [{"person_id": "p2"}], "update": "friend"},
                "expected": {
                    "should_call_tools": True,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs_list": [
                        {"person_id": "p2", "relationship": "friend"}
                    ],
                },
                "held_out": True,
            },
            {
                "inputs": {"records": [], "update": "friend"},
                "expected": {
                    "should_call_tools": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs_list": [],
                },
                "negative_applicability": True,
            },
        ),
    )

    assert not _request_complete_tools_enabled(request)


def test_lookup_before_action_contract_remains_standard_generated_tool(
    monkeypatch,
) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="Look up a named contact before sending a visible message.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="plan_send_message_contact_lookup",
        validation_examples=(
            {
                "inputs": {"recipient_name": "Ada", "message_content": "Hello"},
                "expected": {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"name": "Ada"},
                    "downstream_tool_name": "send_message_with_phone_number",
                },
            },
            {
                "inputs": {"recipient_name": "Grace", "message_content": "Hi"},
                "expected": {
                    "should_call_search_contacts": True,
                    "search_contacts_kwargs": {"name": "Grace"},
                    "downstream_tool_name": "send_message_with_phone_number",
                },
                "held_out": True,
            },
            {
                "inputs": {"recipient_name": "", "message_content": "Hello"},
                "expected": {
                    "should_call_search_contacts": False,
                    "search_contacts_kwargs": {},
                    "downstream_tool_name": "",
                },
                "negative_applicability": True,
            },
        ),
    )

    assert not _request_complete_tools_enabled(request)


def test_native_action_prompt_removes_conflicting_planner_prohibition(
    monkeypatch,
) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible contact update request",
        observation=(
            "Prepare modify_contact kwargs. The tool must never call modify_contact; "
            "it only prepares the original action."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="select_contact_for_update",
        inadequacy_evidence={
            "summary": "The tool must never call modify_contact.",
            "signals": ["side_effect_argument_preparation_failure"],
            "failed_tool_calls": ["modify_contact"],
        },
        validation_examples=(
            {
                "inputs": {"person_id": "person-1", "phone_number": "+15550100"},
                "expected": {
                    "should_call_tool": True,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "person-1",
                        "phone_number": "+15550100",
                    },
                },
            },
            {
                "inputs": {"person_id": "person-2", "phone_number": "+15550111"},
                "expected": {
                    "should_call_tool": True,
                    "downstream_tool_name": "modify_contact",
                    "downstream_tool_kwargs": {
                        "person_id": "person-2",
                        "phone_number": "+15550111",
                    },
                },
                "held_out": True,
            },
            {
                "inputs": {"person_id": "", "phone_number": "+15550122"},
                "expected": {
                    "should_call_tool": False,
                    "downstream_tool_name": "",
                    "downstream_tool_kwargs": {},
                },
                "negative_applicability": True,
            },
        ),
    )

    prompt = _model_authored_generation_prompt(request)

    assert "must never call modify_contact" not in prompt
    assert "exactly one validated native action" in prompt
    assert '"failed_tool_calls": ["modify_contact"]' in prompt


def test_native_action_recency_prompt_removes_legacy_planner_contract(
    monkeypatch,
) -> None:
    observation = _recency_action_target_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="select_action_target_by_recency",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )

    prompt = _model_authored_generation_prompt(request)

    assert "Never call the original search, modify, remove" not in prompt
    assert "Call that native function exactly once" in prompt
    assert "validate every candidate before sorting" in prompt
    assert "collect every record at that value" in prompt


def test_native_action_semantic_repair_preserves_near_candidate_structure(
    monkeypatch,
) -> None:
    observation = _message_counterparty_contact_update_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="select_message_counterparty_for_contact_update",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )
    rejected = GeneratedTool(
        spec=replace(
            _native_add_contact_tool(
                "def complete_add_contact(name: str, phone_number: str) -> dict:\n"
                "    return {'sentinel_bad_branch': True}\n"
            ).spec,
            tool_name="select_message_counterparty_for_contact_update",
        ),
        code=(
            "def select_message_counterparty_for_contact_update(records: list, "
            "selection_mode: str, updates: dict, self_person_id: str) -> dict:\n"
            "    return {'sentinel_bad_branch': True}\n"
        ),
    )
    conflicting = replace(
        rejected,
        spec=replace(
            rejected.spec,
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary=observation.observation,
                signals=("wrong selected record",),
            ),
        ),
    )
    normalized = _normalize_model_authored_tool(request, conflicting)
    assert "must never call" not in normalized.spec.inadequacy_evidence.summary
    assert normalized.spec.native_action_delegation
    assert "validated native action" in normalized.spec.reason_tool_is_decisive
    assert normalized.spec.output_schema["required"] == [
        "status",
        "confirmation",
        "abstain_reason",
        "native_action",
    ]
    updates_input = next(
        item for item in normalized.spec.inputs if item.name == "updates"
    )
    assert "writable approved native-action parameters" in updates_input.description
    assert "phone_number" in updates_input.description
    assert "Do not use role-prefixed record fields" in updates_input.description
    self_input = next(
        item for item in normalized.spec.inputs if item.name == "self_person_id"
    )
    assert "search_contacts" in self_input.description
    assert "never infer" in self_input.description

    prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "source_0_native_action_count:0!=1",
            "held_out_0_native_action_count:0!=1",
        ),
    )

    assert "sentinel_bad_branch" in prompt
    assert "Rewrite the implementation from the public contract" not in prompt
    assert "self_person_id is a required visible input" in prompt
    assert "never pass self_person_id to modify_contact" in prompt
    assert "Never call next() directly on a tuple or list" in prompt
    assert "pass only keys that are present with non-None values" in prompt
    assert "Forward all such entries together" in prompt
    assert "Every return path must contain all five keys" in prompt
    assert "native_action=''" in prompt
    assert "native_result=None" in prompt
    assert "Return a top-level candidates array with exactly 3" in prompt

    confirmation_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("source_0_native_action_confirmation_missing_update_value:+15550999",),
    )
    assert "construct confirmation from the updates mapping" in confirmation_prompt
    assert "do not hard-code any example value" in confirmation_prompt
    assert "A fixed generic confirmation is never valid" in confirmation_prompt

    repeated_confirmation_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "source_0_native_action_confirmation_missing_update_value:+15550999",
            "repair_strategy:2",
        ),
    )
    assert "repeated a confirmation-contract failure" in repeated_confirmation_prompt
    assert "sentinel_bad_branch" not in repeated_confirmation_prompt
    assert '"code": ""' in repeated_confirmation_prompt

    structural_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "negative_2_native_action_execution_error:KeyError:'creation_timestamp'",
            "negative_3_unexpected_native_action:modify_contact",
        ),
    )
    assert "FOCUSED RANKED-RECORD REPAIR" in structural_prompt
    assert "Before sorted, min, max, indexing, or the native call" in structural_prompt
    assert "require len(winners) == 1" in structural_prompt

    single_case_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "negative_3_unexpected_native_action:modify_contact",
            "negative_3_native_action_abstain_status_missing",
            "negative_3_native_action_abstain_reason_missing",
            "negative_3_native_action_abstain_confirmation_present",
            "negative_3_native_action_abstain_action_present",
        ),
    )
    assert "sentinel_bad_branch" in single_case_prompt
    assert "FOCUSED RANKED-RECORD REPAIR" in single_case_prompt
    assert "Focused attempt 1" in single_case_prompt
    assert "Make one minimal edit" in single_case_prompt
    assert "Only then select winners[0]" in single_case_prompt
    assert (
        "setting winners to all structurally valid records is incorrect"
        in single_case_prompt
    )
    assert (
        "Do not build valid_records by filtering malformed entries"
        in single_case_prompt
    )
    assert "rank the unchanged collection" in single_case_prompt
    assert "if no concrete update remains, abstain" in single_case_prompt
    assert "blank required context identifier" in single_case_prompt
    assert '"validator_case_label": "negative_3"' in single_case_prompt
    assert '"case_label": "negative_structural_1_tied_rank"' in single_case_prompt

    final_directive = _model_authored_final_repair_directive(
        request,
        (
            "negative_2_native_action_execution_error:KeyError:'creation_timestamp'",
            "negative_3_unexpected_native_action:modify_contact",
        ),
    )
    assert "FINAL BINDING REPAIR CHECKLIST" in final_directive
    assert "original records collection without filtering" in final_directive
    assert "Abstain unless len(winners) is exactly one" in final_directive
    assert "Never assume a fixed sender or recipient direction" in final_directive
    assert "Never mutate the list with remove()" in final_directive
    assert "Every public positive and held-out case must reach exactly one" in (
        final_directive
    )

    monkeypatch.setenv("SAGE_MODEL_AUTHORED_REPAIR_CANDIDATES", "3")
    batch_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("negative_3_unexpected_native_action:modify_contact",),
    )
    assert (
        "top-level candidates array with exactly 3 independent objects" in batch_prompt
    )
    assert "explicit extreme-value winner set" in batch_prompt
    assert "grouped rank-value uniqueness check" in batch_prompt
    assert "must define exactly one complete top-level function" in batch_prompt
    assert "never return only a function body" in batch_prompt

    nonfocused_batch_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("source_0_native_action_confirmation_missing_update_value:+15550999",),
    )
    assert (
        "top-level candidates array with exactly 3 independent objects"
        in nonfocused_batch_prompt
    )
    monkeypatch.delenv("SAGE_MODEL_AUTHORED_REPAIR_CANDIDATES")

    negative_only_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "negative_1_unexpected_native_action:modify_contact",
            "negative_3_unexpected_native_action:modify_contact",
        ),
    )
    assert "FOCUSED RANKED-RECORD REPAIR" in negative_only_prompt
    assert "sentinel_bad_branch" in negative_only_prompt

    negative_strategy_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "negative_2_native_action_execution_error:KeyError",
            "negative_3_unexpected_native_action:modify_contact",
            "repair_strategy:4",
        ),
    )
    assert "Focused attempt 4" in negative_strategy_prompt
    assert "Rewrite only the ranked-selection block" in negative_strategy_prompt

    focused_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("held_out_0_native_action_count:0!=1",),
    )
    assert "FOCUSED RANKED-RECORD REPAIR" in focused_prompt
    assert "sentinel_bad_branch" in focused_prompt
    assert "CRITICAL FIRST STEP" in focused_prompt
    assert "field name or value that sounds adverse" in focused_prompt
    assert '"case_label": "held_out_0"' in focused_prompt
    assert "self_person_id is a required visible input" in focused_prompt
    assert (
        "derive every action argument from the listed argument_value_locations"
        in focused_prompt
    )
    second_strategy_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("held_out_0_native_action_count:0!=1", "repair_strategy:2"),
    )
    assert "Focused attempt 2" in second_strategy_prompt
    assert "Build a compact case table" in second_strategy_prompt
    assert "CRITICAL FIRST STEP" in second_strategy_prompt
    assert "sentinel_bad_branch" in second_strategy_prompt
    assert "repair_strategy:2" not in second_strategy_prompt

    clean_rewrite_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        (
            "source_0_native_action_count:0!=1",
            "held_out_0_native_action_count:0!=1",
            "repair_strategy:4",
        ),
    )
    assert "Rewrite the implementation from the public contract" in clean_rewrite_prompt
    assert "sentinel_bad_branch" not in clean_rewrite_prompt
    assert '"code": ""' in clean_rewrite_prompt

    monkeypatch.setenv("SAGE_MODEL_AUTHORED_REPAIR_CANDIDATES", "3")
    multi_candidate_prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("held_out_0_native_action_count:0!=1",),
    )
    assert "top-level candidates array with exactly 3 independent objects" in (
        multi_candidate_prompt
    )

    repair_analysis_prompt = _model_authored_repair_analysis_prompt(
        request,
        rejected,
        ("held_out_0_native_action_count:0!=1",),
    )
    assert "Substitute the complete input values" in repair_analysis_prompt
    assert '"case_label": "held_out_0"' in repair_analysis_prompt
    assert "sentinel_bad_branch" in repair_analysis_prompt
    assert "first_blocking_condition" in repair_analysis_prompt


def test_model_authored_signature_uses_all_validation_values_for_numeric_type(
    monkeypatch,
) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible reminder creation request",
        observation="Create one reminder from normalized visible fields.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="prepare_reminder_creation_args",
        validation_examples=(
            {
                "inputs": {"latitude": None},
                "expected": {"status": "success"},
            },
            {
                "inputs": {"latitude": 37.7749},
                "expected": {"status": "success"},
            },
        ),
    )
    authored = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_reminder_creation_args",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Create one reminder from normalized visible fields.",
            inputs=(ToolInput("latitude", "str", "Visible latitude."),),
            output_annotation="dict",
        ),
        code=(
            "def prepare_reminder_creation_args(latitude: str) -> dict:\n"
            "    return {'status': 'success', 'latitude': latitude}\n"
        ),
    )

    normalized = _normalize_model_authored_tool(request, authored)

    assert normalized.spec.inputs[0].annotation == "float"
    assert "latitude: float" in normalized.code


def test_native_action_validation_checks_source_held_out_and_negative(
    monkeypatch,
) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    digits = ''.join(ch for ch in phone_number if ch.isdigit())
    if not name.strip() or not digits:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_name_or_phone', 'native_action': ''}
    normalized_phone = '+' + digits
    native_result = add_contact(name=name.strip(), phone_number=normalized_phone)
    return {'status': 'success', 'confirmation': f'{name.strip()} has been added as a contact.', 'abstain_reason': '', 'native_action': 'add_contact', 'native_result': native_result}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert result.accepted
    assert result.held_out_check_count == 1
    assert result.negative_applicability_count == 1


def test_native_action_validation_rejects_missing_positive_action_contract(
    monkeypatch,
) -> None:
    tool = _native_add_contact_tool(
        "def complete_add_contact(name: str, phone_number: str) -> dict:\n"
        "    return {'status': 'planned'}\n"
    )
    examples = (
        ToolExample(
            {"name": "Avery", "phone_number": "+15550100"},
            {"downstream_tool_name": "add_contact"},
        ),
        ToolExample(
            {"name": "Jordan", "phone_number": "+15550111"},
            {"downstream_tool_name": "add_contact"},
            held_out=True,
        ),
        ToolExample(
            {"name": "", "phone_number": ""},
            {"downstream_tool_name": ""},
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert not result.accepted
    assert "native_action_contract_missing_positive_action" in result.errors


def test_native_add_contact_confirmation_must_be_subject_first(monkeypatch) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    digits = ''.join(ch for ch in phone_number if ch.isdigit())
    if not name.strip() or not digits:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_name_or_phone', 'native_action': ''}
    normalized_phone = '+' + digits
    native_result = add_contact(name=name.strip(), phone_number=normalized_phone)
    return {'status': 'success', 'confirmation': f'Added contact {name.strip()}.', 'abstain_reason': '', 'native_action': 'add_contact', 'native_result': native_result}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any(
        "native_action_confirmation_not_subject_first" in error
        for error in result.errors
    )


def test_native_action_repair_uses_generic_subject_first_confirmation_rule(
    monkeypatch,
) -> None:
    request = ToolGenerationRequest(
        scenario_name="visible request",
        observation="Visible contact fields require one preserved native action.",
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        suggested_tool_name="complete_add_contact",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in _examples()
        ),
    )
    rejected = _native_add_contact_tool(
        "def complete_add_contact(name: str, phone_number: str) -> dict:\n"
        "    return {'status': 'abstain'}\n"
    )

    prompt = _model_authored_repair_prompt(
        request,
        rejected,
        ("source_0_native_action_confirmation_not_subject_first:Avery Stone",),
    )

    assert "CRITICAL subject-first confirmation rule" in prompt
    assert "begins with str(that parameter)" in prompt
    assert "never hard-code the example values" in prompt
    assert "construct confirmation from the updates mapping" not in prompt


def test_native_action_permission_is_recorded_per_generated_tool(monkeypatch) -> None:
    native_tool = _native_add_contact_tool(
        "def complete_add_contact(name: str, phone_number: str) -> dict:\n"
        "    return {'abstain_reason': 'diagnostic'}\n"
    )
    standard_tool = replace(
        native_tool,
        spec=replace(native_tool.spec, native_action_delegation=False),
    )

    assert native_action_tool_enabled(native_tool)
    assert not native_action_tool_enabled(standard_tool)
    assert GeneratedTool.from_json(native_tool.to_json()).spec.native_action_delegation


def test_native_action_docstring_exposes_validated_action_choices(monkeypatch) -> None:
    base = _native_add_contact_tool(
        "def select_action_target_by_recency(records: list, action_type: str) -> dict:\n"
        "    return {}\n"
    )
    tool = GeneratedTool(
        spec=replace(
            base.spec,
            tool_name="select_action_target_by_recency",
            inputs=(
                ToolInput("records", "list", "Visible candidate records."),
                ToolInput("timestamp_key", "str", "Visible timestamp field."),
                ToolInput("action_type", "str", "Requested final action."),
                ToolInput("updates", "dict", "Visible requested changes."),
            ),
            preserves_side_effect_tools=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
            required_original_tool_calls=(
                "search_contacts",
                "search_reminder",
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
        ),
        code=base.code,
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )

    docstring = _native_action_google_docstring(entry)

    assert "Choose exactly one validated native action name" in docstring
    assert (
        "modify_contact, remove_contact, modify_reminder, remove_reminder" in docstring
    )
    assert "Never choose an action for a different record type" in docstring
    assert "creation/history timestamp" in docstring
    assert "scheduled/due timestamp" in docstring
    assert "Never include a target identifier" in docstring
    assert "any key ending in _id" in docstring
    assert "- modify_reminder: use only when the visible request calls for" in docstring

    function = compile_toolsandbox_tool(entry)
    assert function.__annotations__["action_type"].__args__ == (
        "modify_contact",
        "remove_contact",
        "modify_reminder",
        "remove_reminder",
    )


def test_generated_rejection_guard_exposes_finite_input_domain() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_state_sequence",
            family=ToolFamily.CANONICALIZER,
            description="Canonicalize a finite visible service target.",
            inputs=(
                ToolInput("target_service", "str", "Visible service target."),
                ToolInput("desired_on", "bool", "Visible desired state."),
            ),
            output_annotation="str",
            positive_triggers=("device_state_action",),
            negative_triggers=("unsupported_target",),
            generalization_rationale="One finite service contract applies repeatedly.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="The actor needs a deterministic finite service plan.",
                signals=("finite_service_target",),
            ),
        ),
        code=(
            "def plan_state_sequence(target_service: str, desired_on: bool) -> str:\n"
            "    if target_service not in {'wifi', 'cellular', 'location'}:\n"
            "        return ''\n"
            "    return target_service\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )

    function = compile_toolsandbox_tool(entry)

    assert function.__annotations__["target_service"].__args__ == (
        "wifi",
        "cellular",
        "location",
    )
    assert function.sage_generated_input_domains == {
        "target_service": ("wifi", "cellular", "location")
    }


def test_positive_membership_branch_does_not_restrict_open_string_input() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="canonicalize_open_label",
            family=ToolFamily.CANONICALIZER,
            description="Canonicalize known labels while preserving unknown labels.",
            inputs=(ToolInput("label", "str", "Any visible label."),),
            output_annotation="str",
            positive_triggers=("label",),
            generalization_rationale="Unknown labels remain valid inputs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Visible labels need deterministic normalization.",
                signals=("open_label",),
            ),
        ),
        code=(
            "def canonicalize_open_label(label: str) -> str:\n"
            "    if label in {'wi-fi', 'wifi'}:\n"
            "        return 'wifi'\n"
            "    return label\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )

    function = compile_toolsandbox_tool(entry)

    assert function.__annotations__["label"] is str
    assert function.sage_generated_input_domains == {}


def test_standard_composite_validation_remains_standard_in_native_process(
    monkeypatch,
) -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_contact_creation",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare one visible contact creation action safely.",
            inputs=(
                ToolInput("name", "str", "Visible contact name."),
                ToolInput("phone_number", "str", "Visible contact number."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                },
                "required": ["downstream_tool_kwargs", "should_call_tool"],
            },
            positive_triggers=("visible contact creation",),
            negative_triggers=("missing contact fields",),
            preserves_side_effect_tools=("add_contact",),
            required_original_tool_calls=("add_contact",),
            generalization_rationale=(
                "The same visible-field preparation applies across contact creation."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("contact creation", "contact import"),
            reason_tool_is_decisive=(
                "It prepares validated arguments while preserving the native action."
            ),
            shortfall_cluster_evidence=("visible argument preparation",),
            known_failure_mechanisms_addressed=("missing action arguments",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Visible fields were not reaching the native contact action.",
                signals=("action argument preparation",),
            ),
        ),
        code=(
            "def prepare_contact_creation(name: str, phone_number: str) -> dict:\n"
            "    if not name or not phone_number:\n"
            "        return {'downstream_tool_kwargs': {}, "
            "'should_call_tool': False}\n"
            "    return {'downstream_tool_kwargs': {'name': name, "
            "'phone_number': phone_number}, 'should_call_tool': True}\n"
        ),
    )
    examples = (
        ToolExample(
            {"name": "Avery", "phone_number": "+15550100"},
            {
                "downstream_tool_kwargs": {
                    "name": "Avery",
                    "phone_number": "+15550100",
                },
                "should_call_tool": True,
            },
        ),
        ToolExample(
            {"name": "Jordan", "phone_number": "+15550111"},
            {
                "downstream_tool_kwargs": {
                    "name": "Jordan",
                    "phone_number": "+15550111",
                },
                "should_call_tool": True,
            },
            held_out=True,
        ),
        ToolExample(
            {"name": "", "phone_number": "+15550122"},
            {"downstream_tool_kwargs": {}, "should_call_tool": False},
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted
    assert not native_action_tool_enabled(tool)


def test_native_action_validation_rejects_wrong_arguments(monkeypatch) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    if not name.strip() or not phone_number.strip():
        return {'abstain_reason': 'missing_name_or_phone'}
    native_result = add_contact(name=name.strip(), phone_number=phone_number)
    return {'native_result': native_result, 'confirmation': 'Contact added.'}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any("native_action_arguments" in error for error in result.errors)


def test_native_action_validation_rejects_empty_actor_facing_results(
    monkeypatch,
) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    if not name.strip() or not phone_number.strip():
        return {}
    native_result = add_contact(name=name.strip(), phone_number=phone_number)
    return {}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any("native_action_confirmation_missing" in error for error in result.errors)
    assert any(
        "native_action_abstain_reason_missing" in error for error in result.errors
    )


def test_native_action_validation_allows_generic_nonempty_confirmation(
    monkeypatch,
) -> None:
    base = _native_add_contact_tool("")
    spec = replace(
        base.spec,
        tool_name="update_visible_contact",
        inputs=(
            ToolInput("person_id", "str", "Visible contact identifier."),
            ToolInput("updates", "dict", "Visible requested field updates."),
        ),
        preserves_side_effect_tools=("modify_contact",),
        required_original_tool_calls=("modify_contact",),
    )
    tool = GeneratedTool(
        spec=spec,
        code="""
def update_visible_contact(person_id: str, updates: dict) -> dict:
    if not person_id or not updates:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_input', 'native_action': ''}
    native_result = modify_contact(person_id=person_id, **updates)
    return {'status': 'success', 'confirmation': 'Contact updated successfully.', 'abstain_reason': '', 'native_action': 'modify_contact', 'native_result': native_result}
""",
    )
    examples = (
        ToolExample(
            {"person_id": "p1", "updates": {"phone_number": "+15550123"}},
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {
                    "person_id": "p1",
                    "phone_number": "+15550123",
                },
            },
        ),
        ToolExample(
            {"person_id": "p2", "updates": {"name": "Avery"}},
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {"person_id": "p2", "name": "Avery"},
            },
            held_out=True,
        ),
        ToolExample(
            {"person_id": "", "updates": {}},
            {
                "should_call_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
            },
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted, result.errors


def test_native_action_validation_allows_identifier_in_confirmation_when_action_is_correct(
    monkeypatch,
) -> None:
    base = _native_add_contact_tool("")
    spec = replace(
        base.spec,
        tool_name="update_selected_contact",
        inputs=(
            ToolInput("person_id", "str", "Visible selected contact identifier."),
            ToolInput("selection_mode", "str", "Visible target selection mode."),
            ToolInput("updates", "dict", "Visible requested field updates."),
        ),
        preserves_side_effect_tools=("modify_contact",),
        required_original_tool_calls=("modify_contact",),
    )
    tool = GeneratedTool(
        spec=spec,
        code="""
def update_selected_contact(person_id: str, selection_mode: str, updates: dict) -> dict:
    if not person_id or not updates:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_input', 'native_action': ''}
    native_result = modify_contact(person_id=person_id, **updates)
    value = list(updates.values())[0]
    return {'status': 'success', 'confirmation': f'Updated {selection_mode} target {person_id} to {value}.', 'abstain_reason': '', 'native_action': 'modify_contact', 'native_result': native_result}
""",
    )
    examples = (
        ToolExample(
            {
                "person_id": "p1",
                "selection_mode": "latest",
                "updates": {"phone_number": "+15550123"},
            },
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {
                    "person_id": "p1",
                    "phone_number": "+15550123",
                },
            },
        ),
        ToolExample(
            {
                "person_id": "p2",
                "selection_mode": "oldest",
                "updates": {"relationship": "friend"},
            },
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {"person_id": "p2", "relationship": "friend"},
            },
            held_out=True,
        ),
        ToolExample(
            {"person_id": "", "selection_mode": "latest", "updates": {}},
            {"should_call_tool": False, "downstream_tool_name": ""},
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted, result.errors


def test_native_action_validation_accepts_semantic_selection_confirmation(
    monkeypatch,
) -> None:
    base = _native_add_contact_tool("")
    spec = replace(
        base.spec,
        tool_name="update_selected_contact",
        inputs=(
            ToolInput("person_id", "str", "Visible selected contact identifier."),
            ToolInput("selection_mode", "str", "Visible target selection mode."),
            ToolInput("updates", "dict", "Visible requested field updates."),
        ),
        preserves_side_effect_tools=("modify_contact",),
        required_original_tool_calls=("modify_contact",),
    )
    tool = GeneratedTool(
        spec=spec,
        code="""
def update_selected_contact(person_id: str, selection_mode: str, updates: dict) -> dict:
    if not person_id or not updates:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_input', 'native_action': ''}
    native_result = modify_contact(person_id=person_id, **updates)
    changed = ', '.join(str(value) for value in updates.values())
    return {'status': 'success', 'confirmation': f'Updated the {selection_mode} selected contact with {changed}.', 'abstain_reason': '', 'native_action': 'modify_contact', 'native_result': native_result}
""",
    )
    examples = (
        ToolExample(
            {
                "person_id": "p1",
                "selection_mode": "latest",
                "updates": {"phone_number": "+15550123"},
            },
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {
                    "person_id": "p1",
                    "phone_number": "+15550123",
                },
            },
        ),
        ToolExample(
            {
                "person_id": "p2",
                "selection_mode": "oldest",
                "updates": {"relationship": "friend"},
            },
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {"person_id": "p2", "relationship": "friend"},
            },
            held_out=True,
        ),
        ToolExample(
            {"person_id": "", "selection_mode": "latest", "updates": {}},
            {"should_call_tool": False, "downstream_tool_name": ""},
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted, result.errors


def test_native_action_validation_rejects_action_on_negative(monkeypatch) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    digits = ''.join(ch for ch in phone_number if ch.isdigit())
    normalized_phone = '+' + digits
    native_result = add_contact(name=name.strip() or 'Unknown', phone_number=normalized_phone or '+1')
    return {'native_result': native_result, 'confirmation': 'Contact added.'}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any(
        "negative_0_unexpected_native_action" in error for error in result.errors
    )


def test_native_action_validation_rejects_abstain_after_completed_call(
    monkeypatch,
) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    if not name.strip() or not phone_number.strip():
        return {'status': 'abstain', 'abstain_reason': 'missing_name_or_phone'}
    native_result = add_contact(name=name.strip(), phone_number=phone_number)
    return {'status': 'abstain', 'message': 'Contact creation failed.', 'native_result': native_result}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any(
        "native_action_result_reports_failure_after_call" in error
        for error in result.errors
    )


def test_counterparty_validation_covers_received_message_direction(monkeypatch) -> None:
    observation = _message_counterparty_contact_update_observation("visible request")
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_message_counterparty_for_contact_update",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Update the selected visible message counterparty.",
            inputs=(
                ToolInput("records", "list", "Visible message records."),
                ToolInput("selection_mode", "str", "latest or oldest."),
                ToolInput("updates", "dict", "Requested contact updates."),
                ToolInput("self_person_id", "str", "Visible self person id."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("message counterparty update",),
            negative_triggers=("missing updates", "insufficient information"),
            preserves_side_effect_tools=("search_messages", "modify_contact"),
            required_original_tool_calls=("search_messages", "modify_contact"),
            native_action_delegation=True,
            generalization_rationale=(
                "The same non-self counterparty selection is required across sent "
                "and received message records before a contact update."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "sent message counterparty update",
                "received message counterparty update",
            ),
            reason_tool_is_decisive=(
                "It selects the visible non-self message participant before the "
                "native contact action."
            ),
            shortfall_cluster_evidence=("wrong selected message participant",),
            known_failure_mechanisms_addressed=("wrong selected record",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="The visible message records require counterparty selection.",
                signals=("wrong selected record",),
            ),
        ),
        code="""
def select_message_counterparty_for_contact_update(records: list, selection_mode: str, updates: dict, self_person_id: str) -> dict:
    selected = max(records, key=lambda row: row["creation_timestamp"]) if selection_mode == "latest" else min(records, key=lambda row: row["creation_timestamp"])
    if not updates:
        return {"abstain_reason": "missing_updates"}
    person_id = selected["recipient_person_id"]
    native_result = modify_contact(person_id=person_id, **updates)
    return {"native_result": native_result, "confirmation": "updated"}
""",
    )

    result = validate_generated_tool(tool, observation.validation_examples)

    assert (
        len(
            [example for example in observation.validation_examples if example.held_out]
        )
        == 2
    )
    assert not result.accepted
    assert any("held_out_1_native_action_arguments" in error for error in result.errors)


def test_counterparty_validation_requires_safe_missing_self_id_abstention(
    monkeypatch,
) -> None:
    observation = _message_counterparty_contact_update_observation("visible request")

    missing_self_cases = [
        example
        for example in observation.validation_examples
        if example.inputs.get("self_person_id") == ""
    ]

    assert len(missing_self_cases) == 1
    assert missing_self_cases[0].negative_applicability
    assert missing_self_cases[0].expected["abstain_reason"] == (
        "unresolved_counterparty"
    )


def test_counterparty_update_tool_remains_visible_on_initial_lookup_turn(
    monkeypatch,
) -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_message_counterparty_for_contact_update",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Update a uniquely selected visible message counterparty.",
            inputs=(
                ToolInput("records", "list", "Visible message records."),
                ToolInput("selection_mode", "str", "latest or oldest."),
                ToolInput("updates", "dict", "Requested contact updates."),
                ToolInput("self_person_id", "str", "Visible self person id."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("message_counterparty_update", "message_recency"),
            negative_triggers=("insufficient_information",),
            preserves_side_effect_tools=("search_messages", "modify_contact"),
            required_original_tool_calls=("search_messages", "modify_contact"),
            native_action_delegation=True,
            generalization_rationale="The same selection supports later update turns.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("message_counterparty_update",),
            reason_tool_is_decisive="It binds a visible counterparty to an update.",
            shortfall_cluster_evidence=("wrong_selected_record",),
            known_failure_mechanisms_addressed=("wrong_selected_record",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="A later update can depend on the initially requested counterparty.",
                signals=("message_counterparty_lookup",),
            ),
        ),
        code=(
            "def select_message_counterparty_for_contact_update(records: list, "
            "selection_mode: str, updates: dict, self_person_id: str) -> dict:\n"
            "    return {'status': 'abstain'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=2,
            negative_applicability_count=2,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )

    routed, decisions = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"search_messages", "search_contacts", "modify_contact"},
        task_context_text=(
            "request=Who did I talk to last "
            "tools=search_messages search_contacts modify_contact "
            "signals=message_counterparty_lookup message_recency_search "
            "family=message_counterparty_lookup"
        ),
        task_family_key="message_counterparty_lookup",
    )

    assert [item.tool.spec.tool_name for item in routed] == [tool.spec.tool_name]
    assert decisions[tool.spec.tool_name].reason == "visible_context_signal_match"

    routed, decisions = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"search_messages", "search_contacts", "modify_contact"},
        task_context_text=(
            "request=Change a contact "
            "tools=search_messages search_contacts modify_contact "
            "signals=contact contact_lookup family=contact_lookup"
        ),
        task_family_key="contact_lookup",
    )

    assert [item.tool.spec.tool_name for item in routed] == [tool.spec.tool_name]
    assert decisions[tool.spec.tool_name].reason == "visible_context_signal_match"


def test_complete_tool_validation_adds_selection_mode_aliases(monkeypatch) -> None:
    observation = _message_counterparty_contact_update_observation("visible request")
    request = ToolGenerationRequest(
        scenario_name=observation.scenario_name,
        observation=observation.observation,
        allowed_families=observation.allowed_families,
        suggested_tool_name="select_message_counterparty_for_contact_update",
        validation_examples=tuple(
            {
                "inputs": example.inputs,
                "expected": example.expected,
                "held_out": example.held_out,
                "negative_applicability": example.negative_applicability,
            }
            for example in observation.validation_examples
        ),
    )

    examples = _tool_examples_from_request(request)
    modes = {
        example.inputs.get("selection_mode") for example in examples if example.expected
    }

    assert {"latest", "oldest", "last", "latest_by_time", "most_recent"} <= modes
    assert {"first", "oldest_by_time", "earliest"} <= modes
    structural_negatives = [
        example
        for example in examples
        if example.negative_applicability
        and isinstance(example.inputs.get("records"), list)
    ]
    assert any(
        any("creation_timestamp" not in record for record in example.inputs["records"])
        for example in structural_negatives
    )
    assert any(
        len(example.inputs["records"]) > 1
        and len(
            {record.get("creation_timestamp") for record in example.inputs["records"]}
        )
        < len(example.inputs["records"])
        for example in structural_negatives
    )


def test_retired_deferred_routing_flag_cannot_bypass_visible_context(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_DEFERRED_NATIVE_ACTION_ROUTING", "1")
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="remove_visible_contact",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Remove one uniquely selected visible contact.",
            inputs=(
                ToolInput("records", "list", "Visible contact records."),
                ToolInput("target_name", "str", "Visible requested contact name."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("remove visible contact",),
            negative_triggers=("insufficient_information",),
            preserves_side_effect_tools=("search_contacts", "remove_contact"),
            required_original_tool_calls=("search_contacts", "remove_contact"),
            native_action_delegation=True,
            generalization_rationale=(
                "The same unique visible-contact selection is reusable across "
                "contact removal requests after a contact search."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "contact removal by name",
                "contact removal after search",
            ),
            reason_tool_is_decisive=(
                "It maps a unique visible contact record to the native removal action."
            ),
            shortfall_cluster_evidence=("contact target selection failure",),
            known_failure_mechanisms_addressed=("wrong selected record",),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="A visible contact record must become a native removal target.",
                signals=("wrong selected record",),
            ),
        ),
        code="""
def remove_visible_contact(records: list, target_name: str) -> dict:
    matches = [row for row in records if row.get("name") == target_name]
    if len(matches) != 1:
        return {"status": "abstain", "confirmation": "", "abstain_reason": "non_unique_target", "native_action": ""}
    native_result = remove_contact(person_id=matches[0]["person_id"])
    return {"status": "success", "confirmation": "removed", "abstain_reason": "", "native_action": "remove_contact", "native_result": native_result}
""",
    )
    examples = (
        ToolExample(
            {"records": [{"person_id": "p1", "name": "Avery"}], "target_name": "Avery"},
            {
                "downstream_tool_name": "remove_contact",
                "downstream_tool_kwargs": {"person_id": "p1"},
            },
        ),
        ToolExample(
            {
                "records": [{"person_id": "p2", "name": "Jordan"}],
                "target_name": "Jordan",
            },
            {
                "downstream_tool_name": "remove_contact",
                "downstream_tool_kwargs": {"person_id": "p2"},
            },
            held_out=True,
        ),
        ToolExample(
            {"records": [], "target_name": "Missing"},
            {
                "should_call_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
            },
            negative_applicability=True,
        ),
    )
    validation = validate_generated_tool(tool, examples)
    assert validation.accepted
    entry = RegistryEntry.accepted(tool, validation, birth_scenario="visible request")

    routed, decisions = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"search_contacts", "remove_contact"},
        task_context_text=(
            "request=I need help tools=search_contacts remove_contact "
            "signals=general_conversation family=general_conversation"
        ),
        task_family_key="general_conversation",
    )

    assert routed == []
    assert not decisions[tool.spec.tool_name].visible

    monkeypatch.setenv("SAGE_DEFERRED_NATIVE_ACTION_ROUTING", "0")
    routed_when_disabled, decisions_when_disabled = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"search_contacts", "remove_contact"},
        task_context_text=(
            "request=I need help tools=search_contacts remove_contact "
            "signals=general_conversation family=general_conversation"
        ),
        task_family_key="general_conversation",
    )
    assert routed_when_disabled == []
    assert not decisions_when_disabled[tool.spec.tool_name].visible

    routed_without_producer, decisions_without_producer = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"remove_contact"},
        task_context_text=(
            "request=I need help tools=remove_contact "
            "signals=general_conversation family=general_conversation"
        ),
        task_family_key="general_conversation",
    )
    assert routed_without_producer == []
    assert not decisions_without_producer[tool.spec.tool_name].visible


def test_pure_transformer_routes_with_one_available_alternative_action() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="relative_day_time_to_timestamp",
            family=ToolFamily.CANONICALIZER,
            description="Normalize visible relative local time to a Unix timestamp.",
            inputs=(
                ToolInput("current_timestamp", "float", "Visible current timestamp."),
                ToolInput("current_datetime_info", "dict", "Visible local datetime."),
                ToolInput("day_offset", "int", "Visible relative day offset."),
            ),
            output_annotation="float",
            positive_triggers=("relative_time", "reminder_modify"),
            preserves_side_effect_tools=(
                "get_current_timestamp",
                "timestamp_to_datetime_info",
                "add_reminder",
                "modify_reminder",
            ),
            required_original_tool_calls=(
                "get_current_timestamp",
                "timestamp_to_datetime_info",
                "add_reminder",
                "modify_reminder",
            ),
            generalization_rationale=(
                "The same relative-time normalization serves reminder actions."
            ),
            inadequacy_evidence=(
                "Visible relative times need deterministic normalization."
            ),
        ),
        code=(
            "def relative_day_time_to_timestamp(current_timestamp: float, "
            "current_datetime_info: dict, day_offset: int) -> float:\n"
            "    return current_timestamp + day_offset * 86400\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )
    context = (
        "request=Postpone the reminder tomorrow at 5 PM "
        "signals=relative_time reminder_modify family=reminder_modify"
    )

    routed, decisions = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={
            "get_current_timestamp",
            "timestamp_to_datetime_info",
            "modify_reminder",
        },
        task_context_text=context,
        task_family_key="reminder_modify",
    )

    assert [item.tool.spec.tool_name for item in routed] == [tool.spec.tool_name]
    assert decisions[tool.spec.tool_name].visible

    routed_without_action, decisions_without_action = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"get_current_timestamp", "timestamp_to_datetime_info"},
        task_context_text=context,
        task_family_key="reminder_modify",
    )
    assert routed_without_action == []
    assert not decisions_without_action[tool.spec.tool_name].visible


def test_native_action_selector_subsumes_nonacting_record_selector(monkeypatch) -> None:
    monkeypatch.setattr(
        "sage_ts.runtime.toolsandbox_integration.has_current_validation_proof",
        lambda _entry: True,
    )
    validation = ValidationResult(
        accepted=True,
        errors=(),
        source_example_count=1,
        held_out_check_count=1,
        negative_applicability_count=1,
        runtime_smoke_passed=True,
    )
    native_tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select one visible record and complete one native action.",
            inputs=(
                ToolInput("records", "list", "Visible records."),
                ToolInput("timestamp_key", "str", "Visible rank field."),
                ToolInput("selection_mode", "str", "Latest or oldest."),
                ToolInput("action_type", "str", "Approved action."),
                ToolInput("updates", "dict", "Visible updates."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("recency_action",),
            preserves_side_effect_tools=("search_reminder", "modify_reminder"),
            required_original_tool_calls=("search_reminder", "modify_reminder"),
            native_action_delegation=True,
            generalization_rationale="Reusable visible-record action selection.",
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str, updates: dict) -> dict:\n"
            "    return {'status': 'abstain'}\n"
        ),
    )
    selector_tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_record_by_timestamp_extreme",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select one visible record without acting.",
            inputs=(
                ToolInput("records", "list", "Visible records."),
                ToolInput("timestamp_key", "str", "Visible rank field."),
                ToolInput("selection_mode", "str", "Latest or oldest."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {"selected_record": {"type": "object"}},
            },
            positive_triggers=("recency_search",),
            preserves_side_effect_tools=("search_reminder", "modify_reminder"),
            required_original_tool_calls=("search_reminder", "modify_reminder"),
            generalization_rationale="Reusable visible-record selection.",
        ),
        code=(
            "def select_record_by_timestamp_extreme(records: list, "
            "timestamp_key: str, selection_mode: str) -> dict:\n"
            "    return {'selected_record': {}}\n"
        ),
    )
    entries = {
        native_tool.spec.tool_name: RegistryEntry.accepted(
            native_tool, validation, birth_scenario="visible request"
        ),
        selector_tool.spec.tool_name: RegistryEntry.accepted(
            selector_tool, validation, birth_scenario="visible request"
        ),
    }

    routed, decisions = route_registry_entries(
        entries,
        scenario_name="redacted",
        available_base_tools={"search_reminder", "modify_reminder"},
        task_context_text=(
            "request=Postpone the most recent reminder tomorrow at 5 PM "
            "signals=recency_action recency_search reminder_recency reminder_modify "
            "family=reminder_modify"
        ),
        task_family_key="reminder_modify",
    )

    assert [entry.tool.spec.tool_name for entry in routed] == [
        native_tool.spec.tool_name
    ], {name: decision.reason for name, decision in decisions.items()}
    assert not decisions[selector_tool.spec.tool_name].visible
    assert (
        "more_specific_generated_tool_preferred"
        in decisions[selector_tool.spec.tool_name].reason
    )


def test_native_action_routes_with_one_available_alternative_action(
    monkeypatch,
) -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="apply_single_device_state_action",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Apply one explicit device-state change.",
            inputs=(
                ToolInput("target_service", "str", "Visible service name."),
                ToolInput("desired_on", "bool", "Visible desired state."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "additionalProperties": True},
            positive_triggers=("device_state_action", "single_native_action"),
            negative_triggers=("missing_required_input", "ambiguous_visible_match"),
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
            native_action_delegation=True,
            generalization_rationale=(
                "The same explicit service and Boolean state contract applies across "
                "single device-state requests."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("device_state_action",),
            reason_tool_is_decisive=(
                "It maps visible inputs to one validated native action or abstention."
            ),
            shortfall_cluster_evidence=("device_state_action_failure",),
            known_failure_mechanisms_addressed=("missing_final_native_action",),
            final_state_preservation_plan=(
                "Delegate exactly one action to the preserved native implementation."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="One visible state must reach one native setter safely.",
                signals=("single_native_action",),
            ),
        ),
        code=(
            "def apply_single_device_state_action(target_service: str, "
            "desired_on: bool) -> dict:\n"
            "    return {'status': 'abstain'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=2,
            negative_applicability_count=2,
            runtime_smoke_passed=True,
        ),
        birth_scenario="visible request",
    )
    context = (
        "request=Turn off wifi signals=device_state_action family=device_state_action"
    )

    routed, decisions = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"set_wifi_status"},
        task_context_text=context,
        task_family_key="device_state_action",
    )

    assert [item.tool.spec.tool_name for item in routed] == [tool.spec.tool_name], (
        decisions[tool.spec.tool_name]
    )
    assert decisions[tool.spec.tool_name].visible

    routed_without_action, decisions_without_action = route_registry_entries(
        {tool.spec.tool_name: entry},
        scenario_name="redacted",
        available_base_tools={"end_conversation"},
        task_context_text=context,
        task_family_key="device_state_action",
    )
    assert routed_without_action == []
    assert not decisions_without_action[tool.spec.tool_name].visible


def test_runtime_preserves_native_trace_without_duplicate_generated_trace(
    monkeypatch,
) -> None:
    tool = _native_add_contact_tool(
        """
def complete_add_contact(name: str, phone_number: str) -> dict:
    digits = ''.join(ch for ch in phone_number if ch.isdigit())
    if not name.strip() or not digits:
        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing_name_or_phone', 'native_action': ''}
    native_result = add_contact(name=name.strip(), phone_number='+' + digits)
    return {'status': 'success', 'confirmation': f'{name.strip()} has been added as a contact.', 'abstain_reason': '', 'native_action': 'add_contact', 'native_result': native_result}
"""
    )
    validation = validate_generated_tool(tool, _examples())
    assert validation.accepted
    entry = RegistryEntry.accepted(tool, validation, birth_scenario="visible request")
    function = compile_toolsandbox_tool(entry)
    assert function.sage_native_action_delegation is True
    assert function.sage_native_action_names == ("add_contact",)
    context = ExecutionContext()
    context.trace_tool = True
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "native action test",
                "openai_tool_call_id": "native-action-test",
                "openai_function_name": tool.spec.tool_name,
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
            }
        ],
    )

    with new_context(context):
        result = function(name="Avery Stone", phone_number="+1 555 0100")

    assert result["confirmation"] == "Avery Stone has been added as a contact."
    contacts = context.get_database(DatabaseNamespace.CONTACT).to_dicts()
    assert any(row["name"] == "Avery Stone" for row in contacts)
    trace_values = context.get_database(DatabaseNamespace.SANDBOX)["tool_trace"][0]
    traces = [json.loads(value) for value in trace_values]
    assert [trace["tool_name"] for trace in traces] == ["add_contact"]
