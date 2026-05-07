import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime import routing_scorer, toolsandbox_integration
from sage_ts.runtime.routing_scorer import score_registry_entry_for_scenario
from sage_ts.runtime.toolsandbox_integration import (
    compile_toolsandbox_tool,
    route_registry_entries,
)
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool
from tests.unit.test_promotion_gate import _entry


def _state_dependency_entry() -> RegistryEntry:
    base = _entry()
    return RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="next_dependency_precondition_call",
                family=ToolFamily.STATE_PRECONDITION_HELPER,
                description=(
                    "Plan the next original service tool_call when visible state "
                    "shows a dependency or precondition blocks the requested action."
                ),
                positive_triggers=(
                    "service not ready with active blocker",
                    "service not ready with missing dependency",
                ),
                negative_triggers=("already ready state", "insufficient state"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": ["", "set_low_battery_mode_status"],
                        },
                        "arguments": {"type": "object"},
                        "should_call": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["tool_name", "arguments", "should_call"],
                },
                abstain_behavior=(
                    "Return should_call=False with a reason when state is ready, "
                    "missing, or ambiguous."
                ),
                applicable_task_families=(
                    "turn_on_wifi_low_battery_mode",
                    "turn_on_cellular_low_battery_mode",
                ),
                shortfall_cluster_evidence=(
                    "state_precondition:dependency_precondition_tool_call",
                ),
                known_failure_mechanisms_addressed=(
                    "precondition_bundle_before_downstream_action",
                ),
                required_original_tool_calls=("set_low_battery_mode_status",),
                preserves_side_effect_tools=("set_low_battery_mode_status",),
                final_state_preservation_plan=(
                    "The caller must execute the returned original ToolSandbox "
                    "tool and verify the resulting service state."
                ),
                grading_accounting_note=(
                    "Canonical route differences are reported separately from "
                    "final task outcome."
                ),
            ),
        ),
        base.validation,
        birth_scenario="turn_on_wifi_low_battery_mode",
    )


def test_generic_routing_shows_positive_trigger_and_hides_negative() -> None:
    entry = _entry()
    shown = score_registry_entry_for_scenario(
        entry, "visible_candidate_selection_for_contact"
    )
    hidden = score_registry_entry_for_scenario(
        entry, "ambiguous_tie_visible_candidate_selection"
    )

    assert shown.visible
    assert shown.reason == "generic_relevance_score_passed"
    assert not hidden.visible
    assert hidden.reason == "blocked_by_negative_trigger"


def test_helper_trigger_strata_do_not_expose_without_specific_match() -> None:
    base = _entry()
    tool = replace(
        base.tool,
        spec=replace(
            base.tool.spec,
            tool_name="select_record_by_timestamp_extreme",
            positive_triggers=("search_message_with_recency_latest",),
            applicable_task_families=("message_lookup", "contact_update"),
        ),
    )
    entry = RegistryEntry.accepted(tool, base.validation, birth_scenario="seed")

    decision = score_registry_entry_for_scenario(entry, "find_thanksgiving_timestamp")

    assert not decision.visible
    assert decision.reason == "generic_relevance_score_insufficient"


def test_family_matching_ignores_connector_words_for_contact_scalar_planner(
    monkeypatch: Any,
) -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="plan_contact_search_from_scalar_constraint",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description=(
                "Plan a safe search_contacts call from a scalar contact "
                "constraint such as name, phone number, or relationship."
            ),
            inputs=(
                ToolInput(
                    "constraint_field",
                    "str",
                    "name, phone_number, or relationship.",
                ),
                ToolInput("constraint_value", "str", "Visible scalar constraint."),
            ),
            positive_triggers=(
                "valid phone number provided",
                "valid name provided",
                "valid relationship provided",
            ),
            negative_triggers=(
                "missing contact constraint",
                "unknown constraint field",
            ),
            applicable_task_families=(
                "remove_contact_by_phone",
                "search_phone_number_with_name",
                "search_relationship_with_phone_number",
                "send_message_with_contact_content_cellular_off",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "should_call_search": {"type": "boolean"},
                    "search_tool_name": {"type": "string"},
                    "search_kwargs": {"type": "object"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("search_contacts",),
            preserves_side_effect_tools=("search_contacts",),
            abstain_behavior=(
                "Return should_call_search=False when the scalar contact "
                "constraint is missing, ambiguous, or not supported."
            ),
        ),
        code=(
            "def plan_contact_search_from_scalar_constraint("
            "constraint_field: str, constraint_value: str) -> dict:\n"
            "    return {'should_call_search': False, 'search_tool_name': '', "
            "'search_kwargs': {}, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="remove_contact_by_phone",
    )
    monkeypatch.setattr(routing_scorer, "_helper_evidence", lambda _tool_name: {})

    unrelated_contact_create = score_registry_entry_for_scenario(
        entry, "add_contact_with_name_and_phone_number"
    )
    unrelated_message_recency = score_registry_entry_for_scenario(
        entry, "search_message_with_recency_latest"
    )
    related_remove = score_registry_entry_for_scenario(entry, "remove_contact_by_phone")
    related_lookup = score_registry_entry_for_scenario(
        entry, "search_relationship_with_phone_number"
    )

    assert not unrelated_contact_create.visible
    assert unrelated_contact_create.reason == "generic_relevance_score_insufficient"
    assert not unrelated_message_recency.visible
    assert unrelated_message_recency.reason == "generic_relevance_score_insufficient"
    assert related_remove.visible
    assert related_lookup.visible


def test_route_registry_entries_bounds_runtime_bundle() -> None:
    entries = {
        f"tool_{index}": replace(
            _entry(),
            tool=replace(
                _entry().tool,
                spec=replace(_entry().tool.spec, tool_name=f"tool_{index}"),
            ),
        )
        for index in range(6)
    }

    selected, decisions = route_registry_entries(
        entries,
        "visible_candidate_selection_for_contact",
        max_bundle_size=5,
    )

    assert len(selected) == 5
    assert sum(1 for item in decisions.values() if item.status == "deprioritized") == 1


def test_route_registry_entries_requires_downstream_base_tool_availability() -> None:
    entry = _entry()

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts"},
    )

    assert selected == []
    assert not decisions["select_visible_record"].visible
    assert (
        decisions["select_visible_record"].reason
        == "blocked_by_missing_downstream_original_tool"
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == ["select_visible_record"]
    assert decisions["select_visible_record"].visible


def test_route_registry_entries_treats_preserved_tools_as_conditional_when_required_exists() -> (
    None
):
    base = _entry()
    entry = replace(
        base,
        tool=replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
            ),
        ),
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts"},
    )

    assert [item.tool.spec.tool_name for item in selected] == ["select_visible_record"]
    assert decisions["select_visible_record"].visible


def test_route_registry_entries_allows_composite_one_of_many_downstream_tools() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            positive_triggers=("modify_contact_with_message_recency",),
            negative_triggers=("empty selected record",),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
            preserves_side_effect_tools=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record(records: list) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    selected, decisions = route_registry_entries(
        {"prepare_side_effect_args_from_selected_record": entry},
        "modify_contact_with_message_recency_3_distraction_tools",
        available_base_tools={"search_messages", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "prepare_side_effect_args_from_selected_record"
    ]
    assert decisions["prepare_side_effect_args_from_selected_record"].visible


def test_route_registry_entries_allows_action_selector_one_of_many_downstream_tools() -> (
    None
):
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            positive_triggers=("modify_contact_with_message_recency",),
            negative_triggers=("no records", "ambiguous timestamp tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
            preserves_side_effect_tools=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
        ),
        code=(
            "def select_action_target_by_recency(records: list) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    selected, decisions = route_registry_entries(
        {"select_action_target_by_recency": entry},
        "modify_contact_with_message_recency_3_distraction_tools",
        available_base_tools={"search_messages", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_action_target_by_recency"
    ]
    assert decisions["select_action_target_by_recency"].visible


def test_recency_action_selector_hides_on_non_recency_contact_tasks() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select an action target by recency from visible records.",
            inputs=(
                replace(base.tool.spec.inputs[0], name="records", annotation="list"),
                replace(
                    base.tool.spec.inputs[0], name="timestamp_key", annotation="str"
                ),
                replace(
                    base.tool.spec.inputs[0], name="selection_mode", annotation="str"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
            ),
            positive_triggers=("latest visible action target",),
            negative_triggers=("no records", "ambiguous tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("modify_contact", "remove_reminder"),
            preserves_side_effect_tools=("modify_contact", "remove_reminder"),
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    decision = score_registry_entry_for_scenario(entry, "remove_contact_by_phone")

    assert not decision.visible
    assert decision.reason == "recency_action_selector_requires_recency_action_task"


def test_side_effect_selector_hides_on_insufficient_information() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select an action target by recency from visible records.",
            inputs=(
                replace(base.tool.spec.inputs[0], name="records", annotation="list"),
                replace(
                    base.tool.spec.inputs[0], name="timestamp_key", annotation="str"
                ),
                replace(
                    base.tool.spec.inputs[0], name="selection_mode", annotation="str"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
            ),
            positive_triggers=("latest visible action target",),
            negative_triggers=("no records", "ambiguous tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("modify_contact", "remove_reminder"),
            preserves_side_effect_tools=("modify_contact", "remove_reminder"),
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    decision = score_registry_entry_for_scenario(
        entry, "modify_contact_with_message_recency_insufficient_information"
    )

    assert not decision.visible
    assert (
        decision.reason
        == "side_effect_selector_suppressed_for_insufficient_information"
    )


def test_side_effect_composite_hides_on_insufficient_information() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare kwargs for an original side-effect tool.",
            inputs=(
                replace(
                    base.tool.spec.inputs[0], name="selected_record", annotation="dict"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
                replace(base.tool.spec.inputs[0], name="updates", annotation="dict"),
                replace(base.tool.spec.inputs[0], name="user_intent", annotation="str"),
            ),
            positive_triggers=("selected record with required id",),
            negative_triggers=("missing selected record",),
            applicable_task_families=(
                "remove_contact_by_phone",
                "update_contact_relationship_with_relationship",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("remove_contact",),
            preserves_side_effect_tools=("remove_contact",),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="remove_contact_by_phone",
    )

    decision = score_registry_entry_for_scenario(
        entry, "remove_contact_by_phone_no_remove_contact_insufficient_information"
    )

    assert not decision.visible
    assert (
        decision.reason
        == "side_effect_composite_suppressed_for_insufficient_information"
    )


def test_derived_calculator_with_original_call_hides_on_insufficient_information() -> (
    None
):
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="format_calculated_distance_km",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description=(
                "Format visible calculate_lat_lon_distance output in kilometers."
            ),
            inputs=(
                ToolInput("distance_km", "float", "Calculated distance in km."),
                ToolInput("target_unit", "str", "Requested output unit."),
                ToolInput("precision", "int", "Decimal precision."),
            ),
            positive_triggers=(
                "find_distance_with_location_name",
                "calculate_lat_lon_distance result visible",
            ),
            negative_triggers=(
                "current_location_unavailable",
                "missing_distance_km",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "answer_value": {"type": "string"},
                    "answer_unit": {"type": "string"},
                    "source_unit": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            applicable_task_families=("distance_answer", "distance_verification"),
            required_original_tool_calls=("calculate_lat_lon_distance",),
            preserves_side_effect_tools=(),
        ),
        code=(
            "def format_calculated_distance_km(distance_km: float, "
            "target_unit: str, precision: int) -> dict:\n"
            "    return {'answer_value': str(distance_km), "
            "'answer_unit': 'kilometers', 'abstain_reason': ''}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="find_distance_with_location_name",
    )

    decision = score_registry_entry_for_scenario(
        entry, "find_distance_with_location_name_insufficient_information"
    )

    assert not decision.visible
    assert (
        decision.reason == "derived_calculator_suppressed_for_insufficient_information"
    )

    _selected, decisions = route_registry_entries(
        {"format_calculated_distance_km": entry},
        "find_distance_with_location_name_insufficient_information",
        available_base_tools={"calculate_lat_lon_distance"},
    )
    assert not decisions["format_calculated_distance_km"].visible
    assert (
        decisions["format_calculated_distance_km"].reason
        == "derived_calculator_suppressed_for_insufficient_information"
    )


def test_insufficient_information_guard_shows_despite_missing_original_tool() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="detect_missing_information_before_minefield",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description=(
                "Detect missing information before a forbidden minefield call and "
                "return a clarification plan."
            ),
            inputs=(
                ToolInput("user_request", "str", "The current user request."),
                ToolInput("failed_tool_name", "str", "Failed producer tool."),
                ToolInput("error_text", "str", "Visible error text."),
                ToolInput("intended_downstream_tool", "str", "Forbidden tool."),
            ),
            positive_triggers=(
                "insufficient_information",
                "failed current-location lookup before minefield call",
            ),
            negative_triggers=("no_error_visible", "all_required_information_present"),
            output_schema={
                "type": "object",
                "properties": {
                    "should_abstain": {"type": "boolean"},
                    "missing_information": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "clarification_prompt": {"type": "string"},
                    "forbidden_downstream_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "abstain_reason": {"type": "string"},
                },
            },
            applicable_task_families=(
                "find_distance_with_location_name_insufficient_information",
                "find_current_city_insufficient_information",
            ),
            required_original_tool_calls=("get_current_location",),
            preserves_side_effect_tools=(),
            abstain_behavior=(
                "Return should_abstain=True with a clarification prompt when "
                "required information is missing."
            ),
            shortfall_cluster_evidence=("insufficient_information_or_clarification",),
            known_failure_mechanisms_addressed=("missing_current_location_minefield",),
        ),
        code=(
            "def detect_missing_information_before_minefield("
            "user_request: str, failed_tool_name: str, error_text: str, "
            "intended_downstream_tool: str) -> dict:\n"
            "    return {'should_abstain': True, "
            "'missing_information': ['current_location'], "
            "'clarification_prompt': 'I need your current location to continue.', "
            "'forbidden_downstream_tools': [intended_downstream_tool], "
            "'abstain_reason': 'missing_current_location'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="find_distance_with_location_name_insufficient_information",
    )

    decision = score_registry_entry_for_scenario(
        entry, "find_distance_with_location_name_insufficient_information"
    )

    assert decision.visible
    assert decision.reason == "generic_relevance_score_passed"

    selected, decisions = route_registry_entries(
        {"detect_missing_information_before_minefield": entry},
        "find_distance_with_location_name_insufficient_information",
        available_base_tools={"calculate_lat_lon_distance"},
    )
    assert selected == [entry]
    assert decisions["detect_missing_information_before_minefield"].visible


def test_derived_calculator_with_original_call_requires_trigger_match() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="format_calculated_distance_km",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description=(
                "Format visible calculate_lat_lon_distance output in kilometers."
            ),
            inputs=(
                ToolInput("distance_km", "float", "Calculated distance in km."),
                ToolInput("target_unit", "str", "Requested output unit."),
                ToolInput("precision", "int", "Decimal precision."),
            ),
            positive_triggers=(
                "find_distance_with_location_name",
                "calculate_lat_lon_distance result visible",
            ),
            negative_triggers=("missing_distance_km",),
            output_schema={
                "type": "object",
                "properties": {
                    "answer_value": {"type": "string"},
                    "answer_unit": {"type": "string"},
                    "source_unit": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            applicable_task_families=("distance_answer", "distance_verification"),
            required_original_tool_calls=("calculate_lat_lon_distance",),
            preserves_side_effect_tools=(),
        ),
        code=(
            "def format_calculated_distance_km(distance_km: float, "
            "target_unit: str, precision: int) -> dict:\n"
            "    return {'answer_value': str(distance_km), "
            "'answer_unit': 'kilometers', 'abstain_reason': ''}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="find_distance_with_location_name",
    )

    selected, decisions = route_registry_entries(
        {"format_calculated_distance_km": entry},
        "search_message_with_recency_latest_10_distraction_tools",
        available_base_tools={"calculate_lat_lon_distance", "search_messages"},
    )

    assert selected == []
    assert not decisions["format_calculated_distance_km"].visible
    assert (
        decisions["format_calculated_distance_km"].reason
        == "derived_calculator_requires_trigger_or_family_match"
    )


def test_derived_payload_bridge_autofills_single_dict_among_scalar_inputs(
    monkeypatch: Any,
) -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="resolve_location_lookup_field",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            inputs=(
                ToolInput("location_payload", "dict", "Visible lookup payload."),
                ToolInput("requested_field", "str", "address or phone_number."),
            ),
            required_original_tool_calls=("search_location_around_lat_lon",),
        ),
        code=(
            "def resolve_location_lookup_field(location_payload: dict, "
            "requested_field: str) -> dict:\n"
            "    return {'answer_value': '', 'answer_field': requested_field, "
            "'abstain_reason': ''}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="find_phone_number_with_location_name",
    )
    monkeypatch.setattr(
        toolsandbox_integration,
        "_latest_original_tool_payload",
        lambda tool_names: {"phone_number": "+14089961010"},
    )

    kwargs = toolsandbox_integration._with_chained_visible_payload_arguments(
        entry, {"requested_field": "phone_number"}
    )

    assert kwargs["location_payload"] == {"phone_number": "+14089961010"}
    assert kwargs["requested_field"] == "phone_number"


def test_original_scalar_payload_bridge_wraps_result(monkeypatch: Any) -> None:
    traces = [
        json.dumps(
            {
                "tool_name": "search_lat_lon",
                "result": "Apple Park 1 Apple Park Way Cupertino, CA 95014 United States",
            }
        )
    ]

    class _Existing:
        def to_list(self) -> list[str]:
            return traces

    class _Sandbox:
        def to_dicts(self) -> list[dict[str, Any]]:
            return [{"tool_trace": _Existing()}]

    class _Context:
        def get_database(self, **_kwargs: Any) -> _Sandbox:
            return _Sandbox()

    monkeypatch.setattr(
        toolsandbox_integration,
        "get_current_context",
        lambda: _Context(),
    )

    payload = toolsandbox_integration._latest_original_tool_payload({"search_lat_lon"})

    assert payload == {
        "result": "Apple Park 1 Apple Park Way Cupertino, CA 95014 United States"
    }


def test_side_effect_composite_hides_without_downstream_action_signal() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare kwargs for an original side-effect tool.",
            inputs=(
                replace(
                    base.tool.spec.inputs[0], name="selected_record", annotation="dict"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
                replace(base.tool.spec.inputs[0], name="updates", annotation="dict"),
                replace(base.tool.spec.inputs[0], name="user_intent", annotation="str"),
            ),
            positive_triggers=("selected record with required id",),
            negative_triggers=("missing selected record",),
            applicable_task_families=(
                "remove_contact_by_phone",
                "update_contact_relationship_with_relationship",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("remove_contact",),
            preserves_side_effect_tools=("remove_contact",),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="remove_contact_by_phone",
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_name_with_relationship_3_distraction_tools"
    )

    assert not decision.visible
    assert decision.reason == "post_selection_composite_requires_downstream_action_task"

    _entries, decisions = route_registry_entries(
        {"prepare_side_effect_args_from_selected_record": entry},
        "search_name_with_relationship_3_distraction_tools",
        available_base_tools={"search_contacts", "modify_contact", "remove_contact"},
    )
    assert not decisions["prepare_side_effect_args_from_selected_record"].visible
    assert (
        decisions["prepare_side_effect_args_from_selected_record"].reason
        == "post_selection_composite_requires_downstream_action_task"
    )


def test_route_registry_entries_allows_one_available_emitted_downstream_tool() -> None:
    base = _state_dependency_entry()
    entry = replace(
        base,
        tool=replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                output_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": [
                                "",
                                "set_low_battery_mode_status",
                                "set_cellular_service_status",
                            ],
                        },
                        "arguments": {"type": "object"},
                        "should_call": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["tool_name", "arguments", "should_call"],
                },
                required_original_tool_calls=(
                    "set_low_battery_mode_status",
                    "set_cellular_service_status",
                ),
                preserves_side_effect_tools=(
                    "set_low_battery_mode_status",
                    "set_cellular_service_status",
                ),
            ),
        ),
    )

    selected, decisions = route_registry_entries(
        {"next_dependency_precondition_call": entry},
        "turn_on_wifi_low_battery_mode",
        available_base_tools={"set_low_battery_mode_status"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "next_dependency_precondition_call"
    ]
    assert decisions["next_dependency_precondition_call"].visible


def test_routing_suppresses_visible_not_called_pollution(monkeypatch: Any) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    entry = _entry()
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record": {
                    "visible_count": 12,
                    "called_count": 0,
                    "visible_not_called_count": 12,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "visible_candidate_selection_for_contact"
    )

    assert not decision.visible
    assert decision.reason == "blocked_by_visible_not_called_adoption_risk"


def test_strong_selector_match_gets_actor_policy_fair_chance(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_visible_record_by_constraints",
                applicable_task_families=(
                    "search_phone_number_with_name",
                    "search_relationship_with_phone_number",
                ),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "selected_record": {"type": "object"},
                        "abstain_reason": {"type": "string"},
                    },
                },
            ),
        ),
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record_by_constraints": {
                    "visible_count": 34,
                    "called_count": 0,
                    "visible_not_called_count": 34,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_phone_number_with_name_3_distraction_tools"
    )

    assert decision.visible
    assert decision.reason == "generic_relevance_score_passed"


def test_strong_selector_match_still_blocks_harmful_called_history(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_visible_record_by_constraints",
                applicable_task_families=(
                    "search_phone_number_with_name",
                    "search_relationship_with_phone_number",
                ),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "selected_record": {"type": "object"},
                        "abstain_reason": {"type": "string"},
                    },
                },
            ),
        ),
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record_by_constraints": {
                    "visible_count": 34,
                    "called_count": 2,
                    "visible_not_called_count": 32,
                    "called_subset": {"mean_outcome_delta": -0.2},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_phone_number_with_name_3_distraction_tools"
    )

    assert not decision.visible
    assert decision.reason == "blocked_by_visible_not_called_adoption_risk"


def test_routing_evidence_ignores_runtime_exception_runs(
    monkeypatch: Any, tmp_path: Path
) -> None:
    invalid_run = tmp_path / "outputs" / "invalid_run"
    valid_run = tmp_path / "outputs" / "valid_run"
    invalid_candidate = invalid_run / "candidate" / "arm"
    valid_candidate = valid_run / "candidate" / "arm"
    invalid_candidate.mkdir(parents=True)
    valid_candidate.mkdir(parents=True)
    (invalid_run / "paired_comparison.json").write_text(
        json.dumps({"runtime_exception_count": 1}) + "\n"
    )
    (valid_run / "paired_comparison.json").write_text(
        json.dumps({"runtime_exception_count": 0}) + "\n"
    )
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "candidate_dir": str(valid_candidate),
                "helpers": {"tool": {"visible_count": 1}},
            }
        )
        + "\n"
    )
    (new_dir / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "candidate_dir": str(invalid_candidate),
                "helpers": {"tool": {"visible_count": 9}},
            }
        )
        + "\n"
    )
    monkeypatch.setattr(routing_scorer, "ROUTING_EVIDENCE_ROOT", tmp_path)
    routing_scorer._latest_helper_contribution_summary.cache_clear()

    evidence = routing_scorer._latest_helper_contribution_summary()

    assert evidence["helpers"]["tool"]["visible_count"] == 1
    routing_scorer._latest_helper_contribution_summary.cache_clear()


def test_routing_evidence_can_be_disabled_for_final_runs(
    monkeypatch: Any, tmp_path: Path
) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "helper_contribution_summary.json").write_text(
        json.dumps({"helpers": {"tool": {"visible_count": 9}}}) + "\n"
    )
    monkeypatch.setattr(routing_scorer, "ROUTING_EVIDENCE_ROOT", tmp_path)
    monkeypatch.setenv("SAGE_ROUTING_EVIDENCE_MODE", "disabled")
    routing_scorer._latest_helper_contribution_summary.cache_clear()

    assert routing_scorer._latest_helper_contribution_summary() == {}
    routing_scorer._latest_helper_contribution_summary.cache_clear()


def test_routing_evidence_can_be_pinned_to_explicit_summary(
    monkeypatch: Any, tmp_path: Path
) -> None:
    older = tmp_path / "older"
    newer = tmp_path / "newer"
    pinned = tmp_path / "pinned_summary.json"
    older.mkdir()
    newer.mkdir()
    (older / "helper_contribution_summary.json").write_text(
        json.dumps({"helpers": {"tool": {"visible_count": 1}}}) + "\n"
    )
    (newer / "helper_contribution_summary.json").write_text(
        json.dumps({"helpers": {"tool": {"visible_count": 99}}}) + "\n"
    )
    pinned.write_text(json.dumps({"helpers": {"tool": {"visible_count": 7}}}) + "\n")
    monkeypatch.setattr(routing_scorer, "ROUTING_EVIDENCE_ROOT", tmp_path)
    monkeypatch.setenv("SAGE_ROUTING_EVIDENCE_MODE", "pinned")
    monkeypatch.setenv("SAGE_ROUTING_EVIDENCE_PATH", str(pinned))
    routing_scorer._latest_helper_contribution_summary.cache_clear()

    evidence = routing_scorer._latest_helper_contribution_summary()

    assert evidence["helpers"]["tool"]["visible_count"] == 7
    routing_scorer._latest_helper_contribution_summary.cache_clear()


def test_routing_gives_new_cluster_born_state_helper_fair_chance(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {"helpers": {}},
    )
    entry = _state_dependency_entry()

    decision = score_registry_entry_for_scenario(
        entry, "turn_on_wifi_low_battery_mode_3_distraction_tools"
    )

    assert decision.visible
    assert decision.reason == "fair_chance_cluster_fit"
    assert decision.fair_chance_candidate
    assert decision.fair_chance_reason


def test_fair_chance_state_helper_stays_hidden_on_unrelated_task(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {"helpers": {}},
    )
    entry = _state_dependency_entry()

    decision = score_registry_entry_for_scenario(entry, "find_days_till_holiday")

    assert not decision.visible
    assert decision.reason == "generic_relevance_score_insufficient"


def test_diagnostic_force_can_override_adoption_risk_for_target_tool(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setenv(
        "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "next_dependency_precondition_call"
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "next_dependency_precondition_call": {
                    "visible_count": 10,
                    "called_count": 0,
                    "visible_not_called_count": 10,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )
    entry = _state_dependency_entry()

    selected, decisions = route_registry_entries(
        {"next_dependency_precondition_call": entry},
        "turn_on_wifi_low_battery_mode",
        available_base_tools={"set_low_battery_mode_status"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "next_dependency_precondition_call"
    ]
    assert decisions["next_dependency_precondition_call"].visible
    assert (
        decisions["next_dependency_precondition_call"].reason
        == "diagnostic_force_overrode_adoption_risk"
    )


def test_diagnostic_force_can_override_name_specific_vnc_suppression(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setenv(
        "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "select_contact_field_by_constraint"
    )
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_contact_field_by_constraint",
                family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
            ),
        ),
        base.validation,
        birth_scenario="update_contact_relationship_with_relationship",
    )

    selected, decisions = route_registry_entries(
        {"select_contact_field_by_constraint": entry},
        "update_contact_relationship_with_relationship_3_distraction_tools",
        available_base_tools={"search_contacts", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_contact_field_by_constraint"
    ]
    assert decisions["select_contact_field_by_constraint"].visible
    assert (
        decisions["select_contact_field_by_constraint"].reason
        == "diagnostic_force_overrode_adoption_risk"
    )


def test_search_filter_selector_requires_any_record_producer_not_all_domains() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_visible_record_by_constraints",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select one visible record from search candidates by constraint.",
            inputs=base.tool.spec.inputs,
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_id": {"type": "string"},
                    "value": {"type": "string"},
                    "tie_candidates": {"type": "array"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("search_phone_number_with_name",),
            required_original_tool_calls=(
                "search_contacts",
                "search_messages",
                "search_reminder",
            ),
            preserves_side_effect_tools=(
                "search_contacts",
                "search_messages",
                "search_reminder",
                "modify_contact",
                "remove_reminder",
            ),
        ),
        code="def select_visible_record_by_constraints(records: list) -> dict:\n    return {}\n",
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record_by_constraints": entry},
        "search_phone_number_with_name_3_distraction_tools",
        available_base_tools={"search_contacts"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_visible_record_by_constraints"
    ]
    assert decisions["select_visible_record_by_constraints"].visible


def test_explicit_contact_lookup_contract_blocks_non_matching_all_tools() -> None:
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="plan_contact_lookup_query",
                family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
                positive_triggers=("search_name_with_relationship",),
                negative_triggers=("insufficient_information", "add_contact"),
                applicable_task_families=(
                    "search_name_with_relationship",
                    "search_phone_number_with_name",
                ),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts",),
                output_schema={
                    "type": "object",
                    "properties": {
                        "search_contacts_kwargs": {"type": "object"},
                        "answer_field": {"type": "string"},
                        "abstain_reason": {"type": "string"},
                    },
                },
            ),
        ),
        base.validation,
        birth_scenario="search_name_with_relationship",
    )

    selected, decisions = route_registry_entries(
        {"plan_contact_lookup_query": entry},
        "add_reminder_content_and_week_delta_and_time_all_tools",
        available_base_tools={"search_contacts", "add_reminder"},
    )

    assert selected == []
    assert not decisions["plan_contact_lookup_query"].visible
    assert (
        decisions["plan_contact_lookup_query"].reason
        == "explicit_contract_requires_trigger_or_family_match"
    )

    selected, decisions = route_registry_entries(
        {"plan_contact_lookup_query": entry},
        "search_name_with_relationship_3_distraction_tools",
        available_base_tools={"search_contacts"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "plan_contact_lookup_query"
    ]
    assert decisions["plan_contact_lookup_query"].visible


def test_scalar_phone_normalizer_compiles_with_optional_defaults() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="normalize_contact_phone_number",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Normalize a visible phone number before original contact tools.",
            inputs=(
                ToolInput("phone_number", "str", "Phone number."),
                ToolInput(
                    "default_country_code",
                    "str",
                    "Optional default country code, usually 1.",
                ),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "normalized_phone_number": {"type": "string"},
                    "country_code": {"type": "string"},
                    "is_valid": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("add_contact_with_name_and_phone_number",),
            negative_triggers=("insufficient_information",),
            required_original_tool_calls=("add_contact",),
            preserves_side_effect_tools=("add_contact",),
            abstain_behavior="Return is_valid=False and abstain_reason on invalid input.",
            generalization_rationale=(
                "Phone-number normalization recurs across contact creation, contact "
                "lookup, contact update, and phone-number message tasks."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "add_contact_with_name_and_phone_number",
                "send_message_with_phone_number_and_content",
            ),
            reason_tool_is_decisive="Normalizes phone scalars before preserved original tools.",
            shortfall_cluster_evidence=("direct_side_effect_no_helper",),
            known_failure_mechanisms_addressed=(
                "visible_raw_data_lacking_deterministic_transform",
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary=(
                    "The actor repeatedly has to manually strip phone-number "
                    "formatting before preserved contact/message ToolSandbox calls."
                ),
                signals=("visible_raw_data_lacking_deterministic_transform",),
                visible_data_gaps=("formatted phone number needs normalized scalar",),
                planner_failures=(
                    "manual phone normalization before direct tool call",
                ),
            ),
        ),
        code=(
            "def normalize_contact_phone_number(phone_number: str, default_country_code: str) -> dict:\n"
            "    digits = ''.join(filter(str.isdigit, phone_number))\n"
            "    country_code = ''.join(filter(str.isdigit, default_country_code)) or '1'\n"
            "    if phone_number.strip().startswith('+') and 8 <= len(digits) <= 15:\n"
            "        return {'normalized_phone_number': '+' + digits, 'country_code': country_code, 'is_valid': True, 'abstain_reason': ''}\n"
            "    if len(digits) == 10:\n"
            "        return {'normalized_phone_number': '+' + country_code + digits, 'country_code': country_code, 'is_valid': True, 'abstain_reason': ''}\n"
            "    return {'normalized_phone_number': '', 'country_code': country_code, 'is_valid': False, 'abstain_reason': 'invalid_phone_number'}\n"
        ),
    )
    validation = validate_generated_tool(
        tool,
        (
            ToolExample(
                {"phone_number": "+1 (987) 654-3210", "default_country_code": "1"},
                {
                    "normalized_phone_number": "+19876543210",
                    "country_code": "1",
                    "is_valid": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"phone_number": "245-334-4098", "default_country_code": "1"},
                {
                    "normalized_phone_number": "+12453344098",
                    "country_code": "1",
                    "is_valid": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
        ),
    )
    assert validation.accepted, validation.errors
    entry = RegistryEntry.accepted(
        tool,
        validation,
        birth_scenario="add_contact_with_name_and_phone_number",
    )

    fn = compile_toolsandbox_tool(entry)

    assert (
        fn(phone_number="+1 (987) 654-3210")["normalized_phone_number"]
        == "+19876543210"
    )
