from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


def _state_sequence_tool() -> GeneratedTool:
    return GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_device_state_action_sequence_v3",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            description="Plan native setter calls from visible structured state.",
            inputs=(
                ToolInput("target_service", "str", "Visible service target."),
                ToolInput("desired_on", "bool", "Visible requested state."),
            ),
            output_annotation="dict",
        ),
        code="def plan_device_state_action_sequence_v3(**kwargs):\n    return {}\n",
    )


def test_structured_state_sequence_normalizes_control_fields() -> None:
    tool = _state_sequence_tool()
    raw = {
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
                "tool_name": "set_cellular_service_status",
                "arguments": {"on": True},
                "reason": "set_cellular_on",
            },
        ],
        "final_response_recommendation": "Cellular has been turned on.",
        "continue_original_task_after_sequence": False,
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "target_service": "cellular",
            "desired_on": True,
            "resume_original_task": True,
        },
    )

    assert normalized["action_sequence"] == raw["action_sequence"]
    assert normalized["final_response_recommendation"] == "continue_original_task"
    assert normalized["continue_original_task_after_sequence"] is True


def test_derived_value_abstention_does_not_synthesize_visible_fallback() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="extract_visible_temperature",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Extract one requested visible temperature field.",
            inputs=(
                ToolInput("service_payload", "dict", "Visible weather payload."),
                ToolInput("requested_metric", "str", "Requested field selector."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "answer_value": {"type": "string"},
                    "answer_kind": {"type": "string"},
                    "answer_unit": {"type": "string"},
                    "should_call_downstream_tool": {"type": "boolean"},
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "exact_final_answer": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                    "copy_exactly": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
        ),
        code="def extract_visible_temperature(**kwargs):\n    return {}\n",
    )
    raw = {
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
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "service_payload": {
                "current_temperature": 15.1,
                "min_temperature": 8.9,
            },
            "requested_metric": "unsupported_alias",
        },
    )

    assert normalized == raw


def _flawed_selector_tool() -> GeneratedTool:
    spec = ToolSpec(
        tool_name="select_visible_record_by_constraints",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select one visible record by a constraint and abstain on tie or "
            "ambiguous multiple match cases."
        ),
        inputs=(
            ToolInput("records", "list", "Visible candidate records."),
            ToolInput("field_name", "str", "Visible field to match."),
            ToolInput("expected_value", "str", "Expected field value."),
            ToolInput("return_field", "str", "Field to return."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "selected_index": {"type": "integer"},
                "selected_id": {"type": "string"},
                "value": {"type": "string"},
                "matched_constraints": {"type": "array"},
                "tie_candidates": {"type": "array"},
                "abstain_reason": {"type": "string"},
            },
        },
        positive_triggers=("visible records and one exact field match",),
        negative_triggers=("no records", "ambiguous multiple matches", "tie"),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts",),
        abstain_behavior="Return empty selected_record on tie or ambiguity.",
        generalization_rationale=(
            "Visible-record constraint selection recurs across contact and message tasks."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup", "message_lookup"),
        reason_tool_is_decisive=(
            "It turns search results plus user constraints into a safe selected record."
        ),
        shortfall_cluster_evidence=(
            "search_filter:select_visible_record_by_constraints",
        ),
        known_failure_mechanisms_addressed=("wrong_selected_record",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly fail to select the correct visible record safely.",
            signals=("wrong_selected_record", "visible_info_unused"),
        ),
    )
    code = """
def select_visible_record_by_constraints(records: list, field_name: str, expected_value: str, return_field: str) -> dict:
    matches = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        if field_name not in record:
            continue
        left = str(record.get(field_name, '')).strip().lower()
        right = str(expected_value).strip().lower()
        if left == right:
            matches.append((index, record))
    if len(matches) == 1:
        index, record = matches[0]
        selected_id = str(record.get('person_id', record.get('id', '')))
        value = str(record.get(return_field, selected_id))
        return {'selected_record': record, 'selected_index': index, 'selected_id': selected_id, 'value': value, 'matched_constraints': [field_name], 'tie_candidates': [], 'abstain_reason': ''}
    if len(matches) > 1:
        return {'selected_record': {}, 'selected_index': 0, 'selected_id': 'a', 'value': 'a', 'matched_constraints': [field_name, field_name], 'tie_candidates': [matches[1][1]], 'abstain_reason': 'ambiguous_multiple_matches'}
    return {'selected_record': {}, 'selected_index': -1, 'selected_id': '', 'value': '', 'matched_constraints': [], 'tie_candidates': [], 'abstain_reason': 'no_match'}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def test_selector_output_normalization_enforces_ambiguity_abstention() -> None:
    tool = _flawed_selector_tool()
    inputs = {
        "records": [
            {"person_id": "a", "relationship": "friend"},
            {"person_id": "b", "relationship": "friend"},
        ],
        "field_name": "relationship",
        "expected_value": "friend",
        "return_field": "person_id",
    }
    raw = {
        "selected_record": {},
        "selected_index": 0,
        "selected_id": "a",
        "value": "a",
        "matched_constraints": ["relationship", "relationship"],
        "tie_candidates": [{"person_id": "b", "relationship": "friend"}],
        "abstain_reason": "ambiguous_multiple_matches",
    }

    normalized = normalize_generated_tool_output(tool, raw, inputs=inputs)

    assert normalized == {
        "selected_record": {},
        "selected_index": -1,
        "selected_id": "",
        "value": "",
        "matched_constraints": ["relationship"],
        "tie_candidates": [
            {"person_id": "a", "relationship": "friend"},
            {"person_id": "b", "relationship": "friend"},
        ],
        "abstain_reason": "ambiguous_multiple_matches",
    }


def test_selector_validation_uses_normalized_ambiguity_output() -> None:
    tool = _flawed_selector_tool()
    examples = (
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "name": "Ada"},
                    {"person_id": "b", "name": "Grace"},
                ],
                "field_name": "name",
                "expected_value": "Grace",
                "return_field": "person_id",
            },
            {
                "selected_record": {"person_id": "b", "name": "Grace"},
                "selected_index": 1,
                "selected_id": "b",
                "value": "b",
                "matched_constraints": ["name"],
                "tie_candidates": [],
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "records": [{"person_id": "a", "name": "Ada"}],
                "field_name": "name",
                "expected_value": "Ada",
                "return_field": "person_id",
            },
            {
                "selected_record": {"person_id": "a", "name": "Ada"},
                "selected_index": 0,
                "selected_id": "a",
                "value": "a",
                "matched_constraints": ["name"],
                "tie_candidates": [],
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
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
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
                ],
                "abstain_reason": "ambiguous_multiple_matches",
            },
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted, result.errors


def _composite_constraint_action_tool() -> GeneratedTool:
    return GeneratedTool(
        spec=ToolSpec(
            tool_name="constraint_to_action_planner",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Select a visible record and prepare a downstream action.",
            inputs=(
                ToolInput("records", "list", "Visible records."),
                ToolInput("match_field", "str", "Field to match."),
                ToolInput("match_value", "str", "Value to match."),
                ToolInput("action_type", "str", "Action type."),
                ToolInput("update_fields", "dict", "Update fields."),
                ToolInput("return_field", "str", "Return field."),
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
            positive_triggers=(
                "visible records require constraint-to-action planning",
            ),
            negative_triggers=("no records", "ambiguous multiple matches"),
            preserves_side_effect_tools=("modify_contact", "remove_contact"),
            required_original_tool_calls=("modify_contact", "remove_contact"),
            abstain_behavior="Abstain on no records, no match, or ambiguity.",
            generalization_rationale="Constraint-to-action planning recurs across tasks.",
            estimated_step_compression=4,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "remove_contact_by_phone",
                "modify_contact_by_name",
            ),
            reason_tool_is_decisive=(
                "It combines normalization, selection, tie handling, and action prep."
            ),
            shortfall_cluster_evidence=("composite:constraint_to_action_planner",),
            known_failure_mechanisms_addressed=(
                "visible_info_unused",
                "side_effect_argument_preparation_failure",
            ),
            final_state_preservation_plan="Caller executes the original side-effect tool.",
            grading_accounting_note="Helper route is accounted separately from outcome.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail visible-record action planning.",
                signals=("visible_info_unused",),
            ),
        ),
        code="def constraint_to_action_planner(records: list, match_field: str, match_value: str, action_type: str, update_fields: dict, return_field: str) -> dict:\n    return {}\n",
    )


def test_composite_output_normalization_fills_safe_defaults() -> None:
    tool = _composite_constraint_action_tool()
    inputs = {
        "records": [
            {"person_id": "p1", "name": "Ada Lovelace", "relationship": "coworker"}
        ],
        "match_field": "name",
        "match_value": "ada lovelace",
        "action_type": "modify_contact",
        "update_fields": {"relationship": "friend"},
        "return_field": "person_id",
    }
    raw = {
        "selected_record": {
            "person_id": "p1",
            "name": "Ada Lovelace",
            "relationship": "coworker",
        },
        "selected_id": "p1",
        "selected_index": 0,
        "value": "",
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": {"person_id": "p1", "relationship": "friend"},
        "should_call_tool": True,
        "tie_candidates": [],
        "abstain_reason": "",
        "safety_notes": "",
    }

    normalized = normalize_generated_tool_output(tool, raw, inputs=inputs)

    assert normalized["value"] == "p1"
    assert normalized["safety_notes"] == "call downstream ToolSandbox side-effect next"


def test_generated_kwargs_normalization_removes_null_optional_values() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_reminder_creation_args",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare final add_reminder kwargs.",
            inputs=(),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "add_reminder_kwargs": {"type": "object"},
                    "should_call_add_reminder": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("add_reminder",),
            negative_triggers=("missing time",),
            preserves_side_effect_tools=("add_reminder",),
            required_original_tool_calls=("add_reminder",),
            generalization_rationale="Reminder args recur.",
            estimated_step_compression=2,
            cross_task_applicability_count=2,
            applicable_task_families=("add_reminder",),
            reason_tool_is_decisive="Prepares original add_reminder kwargs.",
            shortfall_cluster_evidence=("composite:prepare_reminder_creation_args",),
            known_failure_mechanisms_addressed=("side_effect_argument_preparation",),
            final_state_preservation_plan="Caller executes add_reminder later.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Missing reminder argument planner.",
                signals=("side_effect_argument_preparation_failure",),
            ),
        ),
        code="def prepare_reminder_creation_args() -> dict:\n    return {}\n",
    )
    raw = {
        "add_reminder_kwargs": {
            "content": "buy milk",
            "reminder_timestamp": 1711136400.0,
            "latitude": None,
            "longitude": None,
        },
        "should_call_add_reminder": True,
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(tool, raw)

    assert normalized["add_reminder_kwargs"] == {
        "content": "buy milk",
        "reminder_timestamp": 1711136400.0,
    }


def test_safe_abstention_normalization_rejects_unresolved_side_effect_target() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            description="Prepare safe abstention decisions.",
            inputs=(
                ToolInput("user_request", "str", "User request."),
                ToolInput("requested_action", "str", "Requested action."),
                ToolInput("target_identifier", "str", "Target id."),
                ToolInput("required_original_tools", "list", "Required tools."),
                ToolInput("available_original_tools", "list", "Available tools."),
                ToolInput("visible_records_count", "int", "Visible records."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {}},
            positive_triggers=("insufficient_information",),
            negative_triggers=("safe action",),
            preserves_side_effect_tools=("remove_contact",),
            required_original_tool_calls=("remove_contact",),
            generalization_rationale="Safe action decisions recur.",
            reason_tool_is_decisive="Prevents unsafe side effects.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Unsafe unresolved target.",
                signals=("missing_target_identifier",),
            ),
        ),
        code="def prepare_safe_action_or_abstain(*args, **kwargs):\n    return {}\n",
    )
    raw = {
        "should_abstain": False,
        "missing_information": [],
        "required_original_tools": [],
        "safe_next_action": "continue_with_original_tool",
        "final_answer_recommendation": "",
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "requested_action": "remove_contact",
            "target_identifier": "+12453344098",
            "visible_records_count": 0,
        },
    )

    assert normalized["should_abstain"] is True
    assert normalized["missing_information"] == ["target_identifier"]
    assert normalized["abstain_reason"] == "missing_target_identifier"


def test_safe_abstention_normalization_preserves_missing_original_tool_priority() -> (
    None
):
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            description="Prepare safe abstention decisions.",
            inputs=(
                ToolInput("user_request", "str", "User request."),
                ToolInput("requested_action", "str", "Requested action."),
                ToolInput("target_identifier", "str", "Target id."),
                ToolInput("required_original_tools", "list", "Required tools."),
                ToolInput("available_original_tools", "list", "Available tools."),
                ToolInput("visible_records_count", "int", "Visible records."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {}},
            positive_triggers=("insufficient_information",),
            negative_triggers=("safe action",),
            preserves_side_effect_tools=("search_contacts", "modify_contact"),
            required_original_tool_calls=("search_contacts", "modify_contact"),
            generalization_rationale="Safe action decisions recur.",
            reason_tool_is_decisive="Prevents unsafe side effects.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Missing original tool blocks safe target resolution.",
                signals=("missing_original_tool_precondition",),
            ),
        ),
        code="def prepare_safe_action_or_abstain(*args, **kwargs):\n    return {}\n",
    )
    raw = {
        "should_abstain": True,
        "missing_information": ["search_contacts"],
        "required_original_tools": ["search_contacts"],
        "safe_next_action": "ask_user_or_abstain",
        "final_answer_recommendation": (
            "I do not have enough information to identify the contact because "
            "contact search is unavailable."
        ),
        "abstain_reason": "missing_required_original_tool",
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "requested_action": "modify_contact",
            "target_identifier": "",
            "required_original_tools": ["search_contacts"],
            "available_original_tools": ["modify_contact"],
            "visible_records_count": 0,
        },
    )

    assert normalized["should_abstain"] is True
    assert normalized["missing_information"] == ["contact_lookup"]
    assert normalized["abstain_reason"] == "missing_required_original_tool"
    assert normalized["final_answer_recommendation"] == (
        "I do not have enough information to identify the contact because "
        "contact search is unavailable."
    )


def test_safe_abstention_normalization_forces_current_city_location_lookup() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            description="Prepare safe abstention decisions.",
            inputs=(
                ToolInput("user_request", "str", "User request."),
                ToolInput("requested_action", "str", "Requested action."),
                ToolInput("target_identifier", "str", "Target id."),
                ToolInput("required_original_tools", "list", "Required tools."),
                ToolInput("available_original_tools", "list", "Available tools."),
                ToolInput("visible_records_count", "int", "Visible records."),
            ),
            output_annotation="dict",
            output_schema={"type": "object", "properties": {}},
            positive_triggers=("insufficient_information",),
            negative_triggers=("safe action",),
            preserves_side_effect_tools=("get_current_location",),
            required_original_tool_calls=("get_current_location",),
            generalization_rationale="Safe action decisions recur.",
            reason_tool_is_decisive="Prevents unsafe side effects.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Missing location lookup blocks safe current-city lookup.",
                signals=("missing_original_tool_precondition",),
            ),
        ),
        code="def prepare_safe_action_or_abstain(*args, **kwargs):\n    return {}\n",
    )
    raw = {
        "should_abstain": False,
        "missing_information": [],
        "required_original_tools": [],
        "safe_next_action": "continue_with_original_tool",
        "final_answer_recommendation": "",
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "user_request": "What city am I in?",
            "requested_action": "get my current city",
            "target_identifier": "current location",
            "required_original_tools": [],
            "available_original_tools": ["set_location_service_status"],
            "visible_records_count": 0,
        },
    )

    assert normalized["should_abstain"] is True
    assert normalized["missing_information"] == ["location_lookup"]
    assert normalized["required_original_tools"] == ["location_lookup"]
    assert normalized["abstain_reason"] == "missing_required_original_tool"
    assert normalized["final_answer_recommendation"] == (
        "I cannot determine what city you are in because I do not have access "
        "to your current location, GPS, or latitude and longitude coordinates."
    )


def test_generic_composite_abstention_clears_downstream_action() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_contact_update_from_id",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare modify_contact kwargs from a visible id.",
            inputs=(
                ToolInput("person_id", "str", "Visible person id."),
                ToolInput("phone_number", "str", "New phone number."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("update_contact_with_id",),
            negative_triggers=("missing person id",),
            preserves_side_effect_tools=("modify_contact",),
            required_original_tool_calls=("modify_contact",),
            generalization_rationale="Contact id updates recur.",
            estimated_step_compression=2,
            cross_task_applicability_count=2,
            applicable_task_families=("contact_update",),
            reason_tool_is_decisive="Prepares original modify_contact kwargs.",
            shortfall_cluster_evidence=("composite:plan_contact_update_from_id",),
            known_failure_mechanisms_addressed=("side_effect_argument_preparation",),
            final_state_preservation_plan="Caller executes modify_contact later.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Missing modify_contact argument planner.",
                signals=("side_effect_argument_preparation_failure",),
            ),
        ),
        code="def plan_contact_update_from_id(person_id: str, phone_number: str) -> dict:\n    return {}\n",
    )
    raw = {
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": {},
        "should_call_tool": False,
        "abstain_reason": "Missing_Person_ID.",
    }

    normalized = normalize_generated_tool_output(tool, raw)

    assert normalized == {
        "downstream_tool_name": "",
        "downstream_tool_kwargs": {},
        "should_call_tool": False,
        "abstain_reason": "missing_person_id",
    }


def test_generic_contact_lookup_abstention_fills_missing_constraint_reason() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_contact_lookup_query",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare search_contacts kwargs from scalar contact constraints.",
            inputs=(
                ToolInput("contact_name", "str", "Visible contact name."),
                ToolInput("phone_number", "str", "Visible phone number."),
                ToolInput("relationship", "str", "Visible relationship."),
                ToolInput("requested_field", "str", "Field to answer."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "should_call_search_contacts": {"type": "boolean"},
                    "search_contacts_kwargs": {"type": "object"},
                    "answer_field": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("search_phone_number_with_name",),
            negative_triggers=("missing_lookup_constraint",),
            preserves_side_effect_tools=("search_contacts",),
            required_original_tool_calls=("search_contacts",),
            generalization_rationale="Contact lookup planning recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "search_phone_number_with_name",
                "search_name_with_relationship",
            ),
            reason_tool_is_decisive="Prepares original search_contacts kwargs.",
            shortfall_cluster_evidence=("composite:plan_contact_lookup_query",),
            known_failure_mechanisms_addressed=("contact_lookup_argument_planning",),
            final_state_preservation_plan="Caller executes search_contacts later.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Missing contact lookup planner.",
                signals=("visible_contact_scalar_constraint_unused",),
            ),
        ),
        code="def plan_contact_lookup_query(contact_name: str, phone_number: str, relationship: str, requested_field: str) -> dict:\n    return {}\n",
    )
    raw = {
        "should_call_search_contacts": False,
        "search_contacts_kwargs": {},
        "answer_field": "phone_number",
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(
        tool,
        raw,
        inputs={
            "contact_name": "",
            "phone_number": "",
            "relationship": "",
            "requested_field": "phone_number",
        },
    )

    assert normalized == {
        "should_call_search_contacts": False,
        "search_contacts_kwargs": {},
        "answer_field": "phone_number",
        "abstain_reason": "missing_lookup_constraint",
    }


def test_search_contacts_kwargs_converts_all_contacts_sentinel() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_contact_relationship_batch_update",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare relationship batch update kwargs.",
            inputs=(
                ToolInput("source_relationship", "str", "Source relationship."),
                ToolInput("target_relationship", "str", "Target relationship."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "should_call_search_contacts": {"type": "boolean"},
                    "search_contacts_kwargs": {"type": "object"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("all contacts as enemies",),
            preserves_side_effect_tools=("search_contacts", "modify_contact"),
            required_original_tool_calls=("search_contacts", "modify_contact"),
            generalization_rationale="Relationship batches recur.",
            reason_tool_is_decisive="Prepares original search and modify kwargs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="All-contact relationship update needs non-self search kwargs.",
                signals=("side_effect_argument_preparation_failure",),
            ),
        ),
        code="def plan_contact_relationship_batch_update(*args, **kwargs):\n    return {}\n",
    )

    normalized = normalize_generated_tool_output(
        tool,
        {
            "should_call_search_contacts": True,
            "search_contacts_kwargs": {"relationship": "__all_contacts__"},
            "abstain_reason": "",
        },
    )

    assert normalized["search_contacts_kwargs"] == {"is_self": False}


def test_send_message_lookup_normalization_fills_advisory_fields() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="plan_send_message_contact_lookup",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare contact lookup before sending a message.",
            inputs=(
                ToolInput("recipient_name", "str", "Recipient name."),
                ToolInput("message_content", "str", "Message body."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "should_call_search_contacts": {"type": "boolean"},
                    "search_contacts_kwargs": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "message_content": {"type": "string"},
                    "next_step": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("send message by contact name",),
            preserves_side_effect_tools=(
                "search_contacts",
                "send_message_with_phone_number",
            ),
            required_original_tool_calls=("search_contacts",),
            generalization_rationale="Named-recipient send tasks need lookup planning.",
            reason_tool_is_decisive="It preserves lookup before send.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Send-message helper advisory fields were brittle.",
                signals=("validation_output_shape",),
            ),
        ),
        code="def plan_send_message_contact_lookup(*args, **kwargs):\n    return {}\n",
    )
    raw = {
        "should_call_search_contacts": True,
        "search_contacts_kwargs": {"name": "Ada"},
        "downstream_tool_name": "send_message_with_phone_number",
        "message_content": "On my way",
        "next_step": "",
        "final_answer_recommendation": "",
        "abstain_reason": "",
    }

    normalized = normalize_generated_tool_output(tool, raw)

    assert normalized["next_step"] == (
        "call search_contacts, then send_message_with_phone_number"
    )
    assert "send_message_with_phone_number" in normalized["final_answer_recommendation"]
    assert normalized["abstain_reason"] == ""


def test_composite_output_normalization_enforces_ambiguity_abstention() -> None:
    tool = _composite_constraint_action_tool()
    inputs = {
        "records": [
            {"person_id": "p1", "relationship": "friend"},
            {"person_id": "p2", "relationship": "friend"},
        ],
        "match_field": "relationship",
        "match_value": "friend",
        "action_type": "modify_contact",
        "update_fields": {"relationship": "coworker"},
        "return_field": "person_id",
    }
    raw = {
        "selected_record": {"person_id": "p1", "relationship": "friend"},
        "selected_id": "p1",
        "selected_index": 0,
        "value": "p1",
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": {"person_id": "p1"},
        "should_call_tool": True,
        "tie_candidates": [{"person_id": "p2", "relationship": "friend"}],
        "abstain_reason": "ambiguous_multiple_matches",
        "safety_notes": "",
    }

    normalized = normalize_generated_tool_output(tool, raw, inputs=inputs)

    assert normalized["selected_record"] == {}
    assert normalized["selected_index"] == -1
    assert normalized["selected_id"] == ""
    assert normalized["value"] == ""
    assert normalized["downstream_tool_name"] == ""
    assert normalized["downstream_tool_kwargs"] == {}
    assert normalized["should_call_tool"] is False
    assert normalized["tie_candidates"] == [
        {"person_id": "p1", "relationship": "friend"},
        {"person_id": "p2", "relationship": "friend"},
    ]
    assert normalized["safety_notes"] == "do not guess before side-effect action"
