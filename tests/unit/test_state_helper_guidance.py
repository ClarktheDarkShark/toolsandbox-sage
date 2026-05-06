from sage_ts.adequacy.inadequacy_classifier import _next_service_tool_call_observation
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime.toolsandbox_integration import (
    _google_docstring,
    compile_toolsandbox_tool,
)
from sage_ts.validation.sandbox_validator import ValidationResult
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    new_context,
)
from tool_sandbox.common.tool_conversion import convert_to_openai_tool
from tool_sandbox.common.utils import add_tool_trace


def _state_helper_entry() -> RegistryEntry:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="next_service_tool_call",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            description="Return the exact next ToolSandbox tool call.",
            inputs=(
                ToolInput("target_service", "str", "Requested service."),
                ToolInput("wifi_enabled", "bool", "Whether wifi is already enabled."),
                ToolInput(
                    "cellular_enabled",
                    "bool",
                    "Whether cellular is already enabled.",
                ),
                ToolInput(
                    "location_service_enabled",
                    "bool",
                    "Whether location service is already enabled.",
                ),
                ToolInput(
                    "low_battery_mode",
                    "bool",
                    "Whether low battery mode is enabled.",
                ),
            ),
            output_annotation="dict",
            generalization_rationale="State precondition handling recurs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Base tools do not expose a deterministic next step.",
                signals=("state_precondition",),
            ),
        ),
        code="def next_service_tool_call(*args, **kwargs):\n    return {}\n",
    )
    validation = ValidationResult(
        accepted=True,
        errors=(),
        source_example_count=2,
        held_out_check_count=1,
        runtime_smoke_passed=True,
    )
    return RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth")


def test_next_service_tool_call_observation_scopes_to_single_target() -> None:
    observation = _next_service_tool_call_observation(
        "turn_on_wifi_low_battery_mode"
    ).observation

    assert "one chosen target service at a time" in observation
    assert "must not encourage calling parallel or alternative service flows" in (
        observation
    )
    assert "report only the final state of that chosen target service" in observation


def test_next_service_tool_call_docstring_includes_usage_constraints() -> None:
    docstring = _google_docstring(_state_helper_entry())

    assert "Usage:" in docstring
    assert "Dependency/precondition usage:" in docstring
    assert "Use only for the single service you are actively trying to change." in (
        docstring
    )
    assert "Do not call this helper for multiple alternative services in parallel." in (
        docstring
    )
    assert "answer only about that final target state" in docstring


def test_generic_state_precondition_docstring_explains_affordance() -> None:
    base = _state_helper_entry()
    entry = RegistryEntry.accepted(
        GeneratedTool(
            spec=ToolSpec(
                tool_name="next_dependency_precondition_call",
                family=ToolFamily.STATE_PRECONDITION_HELPER,
                description="Plan the next visible dependency precondition call.",
                inputs=(ToolInput("state", "dict", "Visible state."),),
                output_annotation="dict",
                positive_triggers=("service not ready with active blocker",),
                negative_triggers=("already ready state", "insufficient state"),
                required_original_tool_calls=("set_low_battery_mode_status",),
                preserves_side_effect_tools=("set_low_battery_mode_status",),
                canonical_route_substitution_risk="medium",
                final_state_preservation_plan=(
                    "Caller must execute the returned original tool and verify "
                    "the final visible service state."
                ),
                grading_accounting_note=(
                    "Canonical intermediate route may differ and is reported "
                    "separately from task outcome."
                ),
                generalization_rationale=(
                    "Service dependency planning recurs across state tasks."
                ),
                inadequacy_evidence=StructuredInadequacyEvidence(
                    summary="Agents miss precondition order.",
                    signals=("state_precondition",),
                ),
            ),
            code=(
                "def next_dependency_precondition_call(state: dict) -> dict:\n"
                "    return {'should_call': bool(state['service_ready']) and bool(state['blocker_active'])}\n"
            ),
        ),
        base.validation,
        birth_scenario="turn_on_wifi_low_battery_mode",
    )

    docstring = _google_docstring(entry)

    assert "Dependency/precondition usage:" in docstring
    assert "execute the returned original ToolSandbox tool" in docstring
    assert "does not perform the side effect" in docstring
    assert "canonical-route impact is reported separately" in docstring
    assert "Expected visible keys: blocker_active, service_ready." in docstring


def test_generic_state_precondition_affordance_reaches_openai_schema() -> None:
    base = _state_helper_entry()
    entry = RegistryEntry.accepted(
        GeneratedTool(
            spec=ToolSpec(
                tool_name="next_dependency_precondition_call",
                family=ToolFamily.STATE_PRECONDITION_HELPER,
                description="Plan the next visible dependency precondition call.",
                inputs=(ToolInput("state", "dict", "Visible state."),),
                output_annotation="dict",
                positive_triggers=("service not ready with active blocker",),
                negative_triggers=("already ready state", "insufficient state"),
                generalization_rationale=(
                    "Service dependency planning recurs across state tasks."
                ),
                inadequacy_evidence=StructuredInadequacyEvidence(
                    summary="Agents miss precondition order.",
                    signals=("state_precondition",),
                ),
            ),
            code=(
                "def next_dependency_precondition_call(state: dict) -> dict:\n"
                "    return {'should_call': bool(state['service_ready']) and bool(state['blocker_active'])}\n"
            ),
        ),
        base.validation,
        birth_scenario="turn_on_wifi_low_battery_mode",
    )

    def fn(state: dict[str, object]) -> dict[str, object]:
        return {}

    fn.__name__ = "next_dependency_precondition_call"
    fn.__doc__ = _google_docstring(entry)
    fn.__annotations__ = {"state": dict, "return": dict}

    schema = convert_to_openai_tool(fn, name="next_dependency_precondition_call")[
        "function"
    ]

    assert "blocked by a visible service" in schema["description"]
    assert "execute the returned original ToolSandbox tool" in schema["description"]
    assert (
        "Expected visible keys: blocker_active, service_ready."
        in schema["parameters"]["properties"]["state"]["description"]
    )


def test_generic_downstream_helper_docstring_uses_actual_output_schema() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="message_search_time_window",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Compute timestamp bounds for message search.",
            inputs=(
                ToolInput("anchor_timestamp", "float", "Reference timestamp."),
                ToolInput("lookback_days", "int", "Days to look back."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "creation_timestamp_lowerbound": {"type": "number"},
                    "creation_timestamp_upperbound": {"type": "number"},
                },
            },
            positive_triggers=("latest message", "oldest message"),
            negative_triggers=("missing current timestamp",),
            required_original_tool_calls=("search_messages",),
            generalization_rationale="Message recency search recurs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Manual timestamp bounds are error-prone.",
                signals=("derived_value",),
            ),
        ),
        code="def message_search_time_window(anchor_timestamp: float, lookback_days: int) -> dict:\n    return {}\n",
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="search_message_with_recency_oldest",
    )

    docstring = _google_docstring(entry)

    assert "Use when:" in docstring
    assert "latest message" in docstring
    assert "Do not use when:" in docstring
    assert "creation_timestamp_lowerbound" in docstring
    assert "Then pass the relevant returned fields into search_messages." in docstring
    assert "should_call_add_reminder" not in docstring
    assert "search_messages_kwargs" not in docstring


def test_post_selection_composite_docstring_explains_required_inputs() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description=(
                "Prepare arguments for one original ToolSandbox side-effect tool "
                "after a visible record has been selected."
            ),
            inputs=(
                ToolInput("selected_record", "dict", "Selected visible record."),
                ToolInput("action_type", "str", "Intended downstream action."),
                ToolInput("updates", "dict", "Fields to update."),
                ToolInput("user_intent", "str", "Original user request."),
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
            positive_triggers=("selected record needs downstream side effect",),
            negative_triggers=("selected record unavailable",),
            required_original_tool_calls=("modify_contact", "remove_reminder"),
            preserves_side_effect_tools=("modify_contact", "remove_reminder"),
            abstain_behavior=(
                "Return should_call_tool=False with abstain_reason when selected_record, "
                "action_type, or required updates are unavailable."
            ),
            generalization_rationale=(
                "Post-selection side-effect argument preparation recurs."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            reason_tool_is_decisive=(
                "It compresses selected-record inspection, action routing, and "
                "downstream kwargs preparation while preserving original tools."
            ),
            shortfall_cluster_evidence=(
                "composite:prepare_side_effect_args_from_selected_record",
            ),
            known_failure_mechanisms_addressed=(
                "failed_side_effect_argument_preparation_after_selection",
            ),
            final_state_preservation_plan=(
                "Caller must execute the returned original ToolSandbox tool."
            ),
            grading_accounting_note=(
                "Helper prepares kwargs only; canonical and outcome are reported separately."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents select a record but fail to prepare action kwargs.",
                signals=("side_effect_argument_preparation",),
            ),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    return {'downstream_tool_name': action_type, "
            "'downstream_tool_kwargs': updates, 'should_call_tool': True, "
            "'abstain_reason': ''}\n"
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
        birth_scenario="modify_contact_with_message_recency",
    )

    docstring = _google_docstring(entry)

    assert "Post-selection usage:" in docstring
    assert "target record has already been" in docstring
    assert "Pass selected_record as the full selected record object" in docstring
    assert "Pass updates as a dict of fields to change." in docstring
    assert "Do not call prepare_side_effect_args_from_selected_record with only" in (
        docstring
    )
    assert "returned downstream_tool_name" in docstring
    assert "downstream_tool_kwargs next" in docstring

    fn = compile_toolsandbox_tool(entry)
    result = fn(action_type="remove_reminder", user_intent="Remove latest reminder.")
    assert result["should_call_tool"] is False
    assert result["abstain_reason"] == "missing_required_helper_inputs"
    assert result["downstream_tool_kwargs"] == {}


def test_post_selection_composite_chains_selected_record_from_prior_trace() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare downstream side-effect kwargs after selection.",
            inputs=(
                ToolInput("selected_record", "dict", "Selected visible record."),
                ToolInput("action_type", "str", "Intended downstream action."),
                ToolInput("updates", "dict", "Fields to update."),
                ToolInput("user_intent", "str", "Original user request."),
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
            positive_triggers=("selected record needs downstream side effect",),
            negative_triggers=("selected record unavailable",),
            required_original_tool_calls=("remove_reminder", "modify_reminder"),
            preserves_side_effect_tools=("remove_reminder", "modify_reminder"),
            abstain_behavior=(
                "Return should_call_tool=False when selected_record or required "
                "updates are unavailable."
            ),
            generalization_rationale=(
                "Post-selection side-effect argument preparation recurs."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "remove_reminder_with_recency_latest",
                "modify_reminder_with_recency_latest",
            ),
            reason_tool_is_decisive=(
                "It converts a selected record and action intent into original "
                "ToolSandbox kwargs."
            ),
            shortfall_cluster_evidence=(
                "composite:prepare_side_effect_args_from_selected_record",
            ),
            known_failure_mechanisms_addressed=(
                "failed_side_effect_argument_preparation_after_selection",
            ),
            final_state_preservation_plan=(
                "Caller executes the returned original ToolSandbox tool."
            ),
            grading_accounting_note=(
                "Helper prepares kwargs only; side effects stay with base tools."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to prepare kwargs after selecting records.",
                signals=("side_effect_argument_preparation",),
            ),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    if not selected_record:\n"
            "        return {'downstream_tool_name': '', "
            "'downstream_tool_kwargs': {}, 'should_call_tool': False, "
            "'abstain_reason': 'missing_selected_record'}\n"
            "    if action_type == 'remove_reminder' and selected_record.get('reminder_id'):\n"
            "        return {'downstream_tool_name': 'remove_reminder', "
            "'downstream_tool_kwargs': {'reminder_id': selected_record['reminder_id']}, "
            "'should_call_tool': True, 'abstain_reason': ''}\n"
            "    if action_type == 'modify_reminder' and selected_record.get('reminder_id'):\n"
            "        return {'downstream_tool_name': 'modify_reminder', "
            "'downstream_tool_kwargs': {'reminder_id': selected_record['reminder_id'], "
            "**updates}, 'should_call_tool': True, 'abstain_reason': ''}\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'unsupported_action_type'}\n"
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
        birth_scenario="remove_reminder_with_recency_latest",
    )

    def select_record_by_timestamp_extreme() -> dict[str, object]:
        return {}

    select_record_by_timestamp_extreme.__name__ = "select_record_by_timestamp_extreme"

    context = ExecutionContext()
    context.trace_tool = True
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "test chained helper call",
                "openai_tool_call_id": "test-call",
                "openai_function_name": "select_record_by_timestamp_extreme",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
            }
        ],
    )
    with new_context(context):
        add_tool_trace(
            select_record_by_timestamp_extreme,
            {
                "selected_record": {
                    "reminder_id": "r1",
                    "content": "Buy tickets",
                }
            },
        )
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "test downstream prep helper call",
                    "openai_tool_call_id": "test-call-2",
                    "openai_function_name": (
                        "prepare_side_effect_args_from_selected_record"
                    ),
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        fn = compile_toolsandbox_tool(entry)

        remove_result = fn(
            action_type="remove_reminder",
            user_intent="Remove the selected reminder.",
        )
        assert remove_result == {
            "downstream_tool_name": "remove_reminder",
            "downstream_tool_kwargs": {"reminder_id": "r1"},
            "should_call_tool": True,
            "abstain_reason": "",
        }

        modify_result = fn(
            action_type="modify_reminder",
            user_intent="Modify the selected reminder.",
        )
        assert modify_result["should_call_tool"] is False
        assert modify_result["abstain_reason"] == "missing_required_update_fields"


def test_derived_value_helper_chains_visible_payload_from_required_tool_trace() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="extract_stock_symbol",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Extract a normalized stock symbol from a stock payload.",
            inputs=(
                ToolInput(
                    "stock_payload",
                    "dict",
                    "Dictionary returned by search_stock.",
                ),
            ),
            output_annotation="str",
            positive_triggers=("stock payload contains a symbol",),
            negative_triggers=("stock payload has no symbol",),
            required_original_tool_calls=("search_stock",),
            preserves_side_effect_tools=("search_stock",),
            abstain_behavior="Return an empty string when no symbol is present.",
            generalization_rationale="Stock symbol extraction recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "find_stock_symbol_with_company_name",
                "find_stock_symbol_with_company_name_low_battery_mode",
            ),
            reason_tool_is_decisive="It avoids manual symbol normalization errors.",
            shortfall_cluster_evidence=("derived_value:extract_stock_symbol",),
            known_failure_mechanisms_addressed=(
                "visible_raw_data_lacking_deterministic_transform",
            ),
            canonical_route_substitution_risk="low",
            final_state_preservation_plan="The original lookup result is unchanged.",
            grading_accounting_note="Only deterministic extraction is substituted.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to extract visible stock symbol fields.",
                signals=("visible_raw_data_lacking_deterministic_transform",),
            ),
        ),
        code=(
            "def extract_stock_symbol(stock_payload: dict) -> str:\n"
            "    return str(stock_payload.get('symbol', '')).split(':')[-1]\n"
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
        birth_scenario="find_stock_symbol_with_company_name",
    )

    docstring = _google_docstring(entry)
    assert "Deterministic extraction usage:" in docstring
    assert "First call the original ToolSandbox tool: search_stock" in docstring

    def search_stock() -> dict[str, object]:
        return {}

    search_stock.__name__ = "search_stock"

    context = ExecutionContext()
    context.trace_tool = True
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "test stock lookup",
                "openai_tool_call_id": "stock-call",
                "openai_function_name": "search_stock",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
            }
        ],
    )
    with new_context(context):
        add_tool_trace(search_stock, {"symbol": "NASDAQ:AAPL", "name": "Apple Inc"})
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "test derived helper call",
                    "openai_tool_call_id": "helper-call",
                    "openai_function_name": "extract_stock_symbol",
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        fn = compile_toolsandbox_tool(entry)

        assert fn() == "AAPL"


def test_derived_value_helper_chains_first_visible_record_from_list_trace() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="extract_service_answer_field",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Extract a scalar answer from a visible service payload.",
            inputs=(
                ToolInput(
                    "service_payload",
                    "dict",
                    "Dictionary returned by a lookup or one visible result row.",
                ),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "answer_value": {"type": "string"},
                    "answer_kind": {"type": "string"},
                    "answer_unit": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("visible service payload contains phone_number",),
            negative_triggers=("service payload has no supported answer field",),
            required_original_tool_calls=(
                "search_location_around_lat_lon",
                "search_weather_around_lat_lon",
            ),
            preserves_side_effect_tools=(
                "search_location_around_lat_lon",
                "search_weather_around_lat_lon",
            ),
            abstain_behavior="Return empty answer fields when no supported field exists.",
            generalization_rationale=(
                "Several external lookup tasks expose structured payloads that "
                "need deterministic scalar answer extraction."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "find_phone_number_with_location_name",
                "find_temperature_f_with_location",
            ),
            reason_tool_is_decisive=(
                "It prevents manual answer-field copying errors after original "
                "lookup tools return visible payloads."
            ),
            shortfall_cluster_evidence=("derived_value:extract_service_answer_field",),
            known_failure_mechanisms_addressed=(
                "visible_raw_data_lacking_deterministic_transform",
            ),
            canonical_route_substitution_risk="low",
            final_state_preservation_plan=(
                "The original lookup result is preserved; the helper only reads "
                "visible payload fields."
            ),
            grading_accounting_note=(
                "Manual field extraction is substituted but lookup calls remain visible."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to extract visible answer fields from service payloads.",
                signals=("visible_raw_data_lacking_deterministic_transform",),
            ),
        ),
        code=(
            "def extract_service_answer_field(service_payload: dict) -> dict:\n"
            "    value = service_payload.get('phone_number', '')\n"
            "    return {'answer_value': str(value), 'answer_kind': 'phone_number' if value else '', 'answer_unit': '', 'abstain_reason': '' if value else 'no_supported_answer_field'}\n"
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
        birth_scenario="find_phone_number_with_location_name",
    )

    def search_location_around_lat_lon() -> list[dict[str, object]]:
        return []

    search_location_around_lat_lon.__name__ = "search_location_around_lat_lon"

    context = ExecutionContext()
    context.trace_tool = True
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "test location lookup",
                "openai_tool_call_id": "location-call",
                "openai_function_name": "search_location_around_lat_lon",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
            }
        ],
    )
    with new_context(context):
        add_tool_trace(
            search_location_around_lat_lon,
            [
                {"name": "Main Branch", "phone_number": "+1 555 0100"},
                {"name": "Other Branch", "phone_number": "+1 555 0199"},
            ],
        )
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "test derived helper call",
                    "openai_tool_call_id": "helper-call",
                    "openai_function_name": "extract_service_answer_field",
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        fn = compile_toolsandbox_tool(entry)

        assert fn()["answer_value"] == "+1 555 0100"


def test_post_selection_composite_chains_selected_record_from_unique_search_trace() -> (
    None
):
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare downstream side-effect kwargs after selection.",
            inputs=(
                ToolInput("selected_record", "dict", "Selected visible record."),
                ToolInput("action_type", "str", "Intended downstream action."),
                ToolInput("updates", "dict", "Fields to update."),
                ToolInput("user_intent", "str", "Original user request."),
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
            positive_triggers=("selected record needs downstream side effect",),
            negative_triggers=("selected record unavailable",),
            required_original_tool_calls=("remove_contact",),
            preserves_side_effect_tools=("remove_contact",),
            abstain_behavior=(
                "Return should_call_tool=False when selected_record is unavailable."
            ),
            generalization_rationale=(
                "Post-selection side-effect argument preparation recurs."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "remove_contact_by_phone",
                "remove_contact_by_name",
            ),
            reason_tool_is_decisive=(
                "It converts a selected record and action intent into original "
                "ToolSandbox kwargs."
            ),
            shortfall_cluster_evidence=(
                "composite:prepare_side_effect_args_from_selected_record",
            ),
            known_failure_mechanisms_addressed=(
                "failed_side_effect_argument_preparation_after_selection",
            ),
            final_state_preservation_plan=(
                "Caller executes the returned original ToolSandbox tool."
            ),
            grading_accounting_note=(
                "Helper prepares kwargs only; side effects stay with base tools."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to prepare kwargs after selecting records.",
                signals=("side_effect_argument_preparation",),
            ),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    if not selected_record:\n"
            "        return {'downstream_tool_name': '', "
            "'downstream_tool_kwargs': {}, 'should_call_tool': False, "
            "'abstain_reason': 'missing_selected_record'}\n"
            "    if action_type == 'remove_contact' and selected_record.get('person_id'):\n"
            "        return {'downstream_tool_name': 'remove_contact', "
            "'downstream_tool_kwargs': {'person_id': selected_record['person_id']}, "
            "'should_call_tool': True, 'abstain_reason': ''}\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'unsupported_action_type'}\n"
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
        birth_scenario="remove_contact_by_phone",
    )

    def search_contacts() -> list[dict[str, object]]:
        return []

    search_contacts.__name__ = "search_contacts"

    context = ExecutionContext()
    context.trace_tool = True
    with new_context(context):
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "test original search tool call",
                    "openai_tool_call_id": "test-search-call",
                    "openai_function_name": "search_contacts",
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        add_tool_trace(
            search_contacts,
            [
                {
                    "person_id": "p1",
                    "name": "Ada",
                    "phone_number": "+15550000000",
                }
            ],
        )
        fn = compile_toolsandbox_tool(entry)
        result = fn(
            action_type="remove_contact",
            user_intent="Remove the contact returned by search.",
        )
        assert result == {
            "downstream_tool_name": "remove_contact",
            "downstream_tool_kwargs": {"person_id": "p1"},
            "should_call_tool": True,
            "abstain_reason": "",
        }


def test_search_filter_helper_defaults_optional_constraints() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select a visible record for a downstream action by recency.",
            inputs=(
                ToolInput("records", "list", "Visible candidate records."),
                ToolInput("timestamp_key", "str", "Timestamp field to compare."),
                ToolInput("selection_mode", "str", "latest or oldest."),
                ToolInput("action_type", "str", "Downstream action type."),
                ToolInput("constraints", "dict", "Optional constraints to apply."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_index": {"type": "integer"},
                    "selected_id": {"type": "string"},
                    "selected_timestamp": {"type": "number"},
                    "action_type": {"type": "string"},
                    "downstream_tool_name": {"type": "string"},
                    "tie_candidates": {"type": "array"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("modify reminder by latest visible record",),
            negative_triggers=("no records", "ambiguous timestamp tie"),
            required_original_tool_calls=("modify_reminder", "remove_reminder"),
            preserves_side_effect_tools=("modify_reminder", "remove_reminder"),
            abstain_behavior="Return abstain_reason when no unambiguous target exists.",
            generalization_rationale="Recency action target selection recurs.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "modify_reminder_with_recency_latest",
                "remove_reminder_with_recency_latest",
            ),
            reason_tool_is_decisive=(
                "It converts visible record filtering, recency ranking, and "
                "downstream action targeting into one deterministic helper call."
            ),
            shortfall_cluster_evidence=(
                "search_filter:select_action_target_by_recency",
            ),
            known_failure_mechanisms_addressed=(
                "wrong_target_selection_before_side_effect_action",
            ),
            final_state_preservation_plan=(
                "Caller must execute the downstream ToolSandbox side-effect tool."
            ),
            grading_accounting_note=(
                "Helper selection is reported separately from final side effect."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to select the correct recency action target.",
                signals=("record_selection",),
            ),
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str, constraints: dict) -> dict:\n"
            "    valid_records = [r for r in records if all(r.get(k) == v for k, v in constraints.items())]\n"
            "    selected = max(valid_records, key=lambda r: r[timestamp_key])\n"
            "    return {'selected_record': selected, 'selected_index': records.index(selected), "
            "'selected_id': selected.get('reminder_id', ''), "
            "'selected_timestamp': selected[timestamp_key], 'action_type': action_type, "
            "'downstream_tool_name': action_type, 'tie_candidates': [], 'abstain_reason': ''}\n"
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
        birth_scenario="modify_reminder_with_recency_latest",
    )
    docstring = _google_docstring(entry)
    assert "Selection/action usage:" in docstring
    assert "after an original search tool returns visible" in docstring
    assert "constraints is optional" in docstring

    fn = compile_toolsandbox_tool(entry)

    result = fn(
        records=[
            {"reminder_id": "older", "reminder_timestamp": 1.0},
            {"reminder_id": "newer", "reminder_timestamp": 2.0},
        ],
        timestamp_key="reminder_timestamp",
        selection_mode="latest",
        action_type="modify_reminder",
    )

    assert result["selected_id"] == "newer"
    assert result["abstain_reason"] == ""


def test_constraint_selector_docstring_explains_post_search_call_path() -> None:
    base = _state_helper_entry()
    entry = RegistryEntry.accepted(
        GeneratedTool(
            spec=ToolSpec(
                tool_name="select_visible_record_by_constraints",
                family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
                description="Select one visible record by explicit constraint.",
                inputs=(
                    ToolInput("records", "list", "Visible search result records."),
                    ToolInput("field_name", "str", "Visible field to match."),
                    ToolInput("expected_value", "str", "Constraint value."),
                    ToolInput("return_field", "str", "Field to return."),
                ),
                output_annotation="dict",
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
                positive_triggers=("search result with explicit user constraint",),
                negative_triggers=("ambiguous match",),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
                abstain_behavior="Abstain on ambiguity.",
                generalization_rationale="Constraint selection recurs across visible records.",
                inadequacy_evidence=StructuredInadequacyEvidence(
                    summary="Agents miss visible-record constraint matching.",
                    signals=("wrong_selection",),
                ),
            ),
            code="def select_visible_record_by_constraints(records: list, field_name: str, expected_value: str, return_field: str) -> dict:\n    return {}\n",
        ),
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )

    docstring = _google_docstring(entry)

    assert "Visible-record constraint selection usage:" in docstring
    assert (
        "Use this helper immediately after an original search tool returns" in docstring
    )
    assert "Pass field_name as the visible field to match" in docstring
    assert "use value/selected_record directly" in docstring


def test_medium_grain_composite_docstring_and_records_trace_bridge() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="constraint_to_action_planner",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Select a visible record and prepare a downstream action plan.",
            inputs=(
                ToolInput("records", "list", "Visible search result records."),
                ToolInput("match_field", "str", "Field to match."),
                ToolInput("match_value", "str", "Value to match."),
                ToolInput("action_type", "str", "answer_field or side-effect action."),
                ToolInput("update_fields", "dict", "Optional update fields."),
                ToolInput("return_field", "str", "Field to return."),
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
            negative_triggers=("no visible records", "ambiguous multiple matches"),
            required_original_tool_calls=("search_contacts", "remove_contact"),
            preserves_side_effect_tools=("search_contacts", "remove_contact"),
            abstain_behavior="Abstain on no records, no match, ties, or unsafe action.",
            generalization_rationale="Constraint-to-action workflows recur across contact tasks.",
            estimated_step_compression=5,
            cross_task_applicability_count=3,
            applicable_task_families=(
                "search_phone_number_with_name",
                "remove_contact_by_phone",
                "update_contact_relationship_with_relationship",
            ),
            reason_tool_is_decisive=(
                "It combines constraint normalization, record selection, ambiguity "
                "handling, and downstream kwargs preparation."
            ),
            shortfall_cluster_evidence=("composite:constraint_to_action_planner",),
            known_failure_mechanisms_addressed=(
                "visible_info_unused",
                "side_effect_argument_preparation_failure",
            ),
            final_state_preservation_plan="Caller must execute returned original ToolSandbox action.",
            grading_accounting_note="Helper prepares only the intermediate plan.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Agents fail to chain visible record selection into actions.",
                signals=("visible_info_unused",),
            ),
        ),
        code=(
            "def constraint_to_action_planner(records: list, match_field: str, "
            "match_value: str, action_type: str, update_fields: dict, "
            "return_field: str) -> dict:\n"
            "    matches = [r for r in records if str(r.get(match_field, '')).lower() == match_value.lower()]\n"
            "    if len(matches) != 1:\n"
            "        return {'selected_record': {}, 'selected_id': '', 'selected_index': -1, 'value': '', 'downstream_tool_name': '', 'downstream_tool_kwargs': {}, 'should_call_tool': False, 'tie_candidates': matches, 'abstain_reason': 'ambiguous_or_no_match', 'safety_notes': 'do not guess'}\n"
            "    record = matches[0]\n"
            "    selected_id = str(record.get('person_id', ''))\n"
            "    return {'selected_record': record, 'selected_id': selected_id, 'selected_index': records.index(record), 'value': str(record.get(return_field, '')), 'downstream_tool_name': '', 'downstream_tool_kwargs': {}, 'should_call_tool': False, 'tie_candidates': [], 'abstain_reason': '', 'safety_notes': 'answer from value'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=2,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="search_phone_number_with_name",
    )

    docstring = _google_docstring(entry)
    assert "Medium-grain workflow usage:" in docstring
    assert "Pass records as the full list" in docstring

    def search_contacts() -> list[dict[str, object]]:
        return []

    search_contacts.__name__ = "search_contacts"
    context = ExecutionContext()
    context.trace_tool = True
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "search visible contacts",
                "openai_tool_call_id": "search-call",
                "openai_function_name": "search_contacts",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
            }
        ],
    )
    with new_context(context):
        add_tool_trace(
            search_contacts,
            [
                {"person_id": "p1", "name": "Ada", "phone_number": "555"},
            ],
        )
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "helper call",
                    "openai_tool_call_id": "helper-call",
                    "openai_function_name": "constraint_to_action_planner",
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        fn = compile_toolsandbox_tool(entry)
        result = fn(
            match_field="name",
            match_value="ada",
            action_type="answer_field",
            update_fields={},
            return_field="phone_number",
        )

    assert result["selected_id"] == "p1"
    assert result["value"] == "555"
    assert result["abstain_reason"] == ""
