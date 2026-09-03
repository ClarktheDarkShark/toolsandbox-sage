# mypy: ignore-errors
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import sage_ts.orchestration.online_birth as online_birth
from sage_ts.adequacy.inadequacy_classifier import (
    _latest_record_selection_observation,
    _location_search_argument_observation,
    _plan_device_state_action_sequence_observation,
    _recency_action_target_observation,
    _relative_day_time_timestamp_observation,
    _reminder_optional_location_argument_observation,
    _resolve_search_window_or_bounds_observation,
    _visible_task_signals,
    classify_visible_task_observations,
)
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.online_birth import (
    CHAIN_ROUTING_FAMILIES_BY_KEY,
    FIRST_OBSERVATION_BIRTH_KEYS,
    OnlineBirthController,
    _advances_repair_case_frontier,
    _complements_validated_native_action,
    _native_action_observation_priority,
    _validation_error_case_labels,
    _validation_failure_score,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ValidationResult
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)
from tool_sandbox.common.scenario import Scenario

_TOOL_NAME = "recency_to_timestamp_bounds"
_RELATIVE_TIME_TOOL_NAME = "relative_day_time_to_timestamp"
_RECORD_SELECTOR_TOOL_NAME = "select_record_by_timestamp_extreme"
_RESOLVE_WINDOW_TOOL_NAME = "resolve_search_window_or_bounds"
_CONTACT_LOOKUP_TOOL_NAME = "plan_contact_lookup_query"


def test_contact_update_counterparty_helper_does_not_route_to_answer_only_sender_lookup() -> (
    None
):
    families = CHAIN_ROUTING_FAMILIES_BY_KEY[
        "composite:select_message_counterparty_for_contact_update"
    ]

    assert "modify_contact_with_message_recency" in families
    assert "modify_contact_with_message_recency_alt" in families
    assert "search_sender_phone_number_with_content" not in families


def test_first_observation_birth_includes_direct_status_and_day_distance() -> None:
    assert "derived_value:plan_device_status_lookup" in FIRST_OBSERVATION_BIRTH_KEYS
    assert (
        "composite:prepare_direct_contact_action_args" in FIRST_OBSERVATION_BIRTH_KEYS
    )
    assert "composite:constraint_to_action_planner" not in FIRST_OBSERVATION_BIRTH_KEYS
    assert (
        "composite:prepare_side_effect_args_from_selected_record"
        not in FIRST_OBSERVATION_BIRTH_KEYS
    )
    assert "derived_value:days_between_timestamps" in FIRST_OBSERVATION_BIRTH_KEYS
    assert "derived_value:extract_stock_symbol" in FIRST_OBSERVATION_BIRTH_KEYS
    assert "composite:prepare_holiday_search_args" in FIRST_OBSERVATION_BIRTH_KEYS


def test_decomposed_recency_tools_route_only_to_matching_visible_signals() -> None:
    assert (
        CHAIN_ROUTING_FAMILIES_BY_KEY.get(
            "derived_value:prepare_upcoming_reminder_search_args", ()
        )
        == ()
    )
    assert online_birth.VISIBLE_ROUTING_FAMILIES_BY_KEY[
        "derived_value:prepare_upcoming_reminder_search_args"
    ] == ("upcoming_reminder_search",)
    assert online_birth.VISIBLE_ROUTING_FAMILIES_BY_KEY[
        "derived_value:prepare_past_reminder_recency_search_args"
    ] == ("past_reminder_recency_search",)


def test_visible_context_contact_phone_mutation_is_not_external_lookup() -> None:
    signals = _visible_task_signals(
        "Remove phone number +12453344098 from my contact",
        (
            "search_contacts",
            "remove_contact",
            "search_location_around_lat_lon",
            "calculate_lat_lon_distance",
            "convert_currency",
        ),
    )

    assert "contact_lookup" in signals
    assert "external_lookup" not in signals
    assert "service_answer_extraction" not in signals


def test_visible_contact_update_by_id_uses_narrow_action_contract() -> None:
    signals = _visible_task_signals(
        "Update phone number of the person with id "
        "11111111-1111-1111-1111-111111111111 to +1 (555) 0199",
        (
            "modify_contact",
            "search_contacts",
            "search_location_around_lat_lon",
            "set_location_service_status",
            "end_conversation",
        ),
    )

    assert "contact_update_by_id" in signals
    assert "direct_contact_action" in signals
    assert "location_phrase" not in signals
    assert "state_precondition_possible" not in signals


def test_device_observation_uses_structured_visible_transition_contract() -> None:
    observation = _plan_device_state_action_sequence_observation(
        "visible_task_context(family=device_state_action; "
        "signals=direct_device_state_action,device_state_action; "
        "request='Turn on wifi')"
    )

    input_shapes = {
        tuple(sorted(example.inputs)) for example in observation.validation_examples
    }
    services = {
        str(example.inputs.get("target_service") or "")
        for example in observation.validation_examples
    }
    assert observation.canonical_key == (
        "state_precondition:plan_device_state_action_sequence"
    )
    assert len(input_shapes) == 1
    assert next(iter(input_shapes)) == (
        "additional_services_to_enable",
        "desired_on",
        "low_battery_blocks_enable",
        "resume_original_task",
        "target_service",
    )
    assert {"wifi", "cellular", "location", "contact"} <= services
    assert all(
        "user_request" not in example.inputs
        for example in observation.validation_examples
    )


def test_visible_context_raw_phone_remove_births_contact_lookup_signal() -> None:
    signals = _visible_task_signals(
        "Remove +12453344098 from my contact",
        (
            "search_contacts",
            "remove_contact",
            "search_location_around_lat_lon",
            "calculate_lat_lon_distance",
        ),
    )

    assert "requested_remove_contact" in signals
    assert "contact_lookup" in signals
    assert "external_lookup" not in signals
    assert "location_phrase" not in signals


def test_visible_context_get_rid_phone_remove_births_contact_lookup_signal() -> None:
    signals = _visible_task_signals(
        "Get rid of +12453344098",
        (
            "search_contacts",
            "remove_contact",
            "search_location_around_lat_lon",
            "calculate_lat_lon_distance",
        ),
    )

    assert "requested_remove_contact" in signals
    assert "contact_lookup" in signals
    assert "external_lookup" not in signals
    assert "location_phrase" not in signals


def test_visible_context_pronoun_out_of_contacts_births_contact_lookup_signal() -> None:
    signals = _visible_task_signals(
        "The guy at +12453344098, I feel like we don't talk much anymore. "
        "Get him out of my contacts.",
        (
            "search_contacts",
            "remove_contact",
            "search_location_around_lat_lon",
            "calculate_lat_lon_distance",
        ),
    )

    assert "requested_remove_contact" in signals
    assert "contact_lookup" in signals
    assert "external_lookup" not in signals


def test_visible_context_underspecified_contact_remove_births_contact_lookup_signal() -> (
    None
):
    signals = _visible_task_signals(
        "I want to delete someone from my contact",
        (
            "search_contacts",
            "remove_contact",
        ),
    )

    assert "requested_remove_contact" in signals
    assert "contact_lookup" in signals


def test_visible_context_external_lookup_keeps_distance_and_phone_queries() -> None:
    external_tools = (
        "search_location_around_lat_lon",
        "calculate_lat_lon_distance",
        "convert_currency",
    )

    distance_signals = _visible_task_signals(
        "How far is Whole Foods from me?", external_tools
    )
    phone_signals = _visible_task_signals(
        "Find the phone number for Whole Foods",
        external_tools,
    )

    assert "external_lookup" in distance_signals
    assert "service_answer_extraction" in distance_signals
    assert "external_lookup" in phone_signals
    assert "service_answer_extraction" in phone_signals


def test_visible_context_weather_lookup_is_external_service_payload() -> None:
    signals = _visible_task_signals(
        "What's the temperature near Grand Canyon in Fahrenheit?",
        ("search_weather_around_lat_lon", "unit_conversion", "end_conversation"),
    )

    assert "external_lookup" in signals
    assert "service_answer_extraction" in signals


def test_visible_context_weather_lookup_handles_temp_abbreviation() -> None:
    signals = _visible_task_signals(
        "Current temp Grand Canyon. I can't read Celsius.",
        ("search_weather_around_lat_lon", "unit_conversion", "end_conversation"),
    )

    assert "external_lookup" in signals
    assert "service_answer_extraction" in signals


def test_visible_context_weather_today_ignores_distractor_recency_tools() -> None:
    signals = _visible_task_signals(
        "What's the lowest temperature in Grand Canyon today",
        (
            "search_weather_around_lat_lon",
            "search_location_around_lat_lon",
            "unit_conversion",
            "search_messages",
            "search_reminder",
            "end_conversation",
        ),
    )

    assert "relative_time" in signals
    assert "external_lookup" in signals
    assert "service_answer_extraction" in signals
    assert "recency_search" not in signals


def test_visible_reminder_relative_time_births_timestamp_tool_without_scenario_name() -> (
    None
):
    context = ExecutionContext(
        tool_allow_list=[
            "add_reminder",
            "search_location_around_lat_lon",
            "timestamp_to_datetime_info",
        ]
    )
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Remind me to buy milk tomorrow at 5 PM.",
            }
        ],
    )
    scenario = Scenario(starting_context=context)

    observations = classify_visible_task_observations("redacted", scenario)
    keys = {observation.canonical_key for observation in observations}

    assert "canonicalizer:relative_day_time_timestamp" in keys
    assert "composite:prepare_reminder_creation_args" in keys


def test_visible_context_stock_lookup_birth_signal_from_request_text() -> None:
    signals = _visible_task_signals(
        "What's the stock symbol for Apple?",
        ("search_stock", "end_conversation"),
    )

    assert "stock_lookup" in signals
    assert "external_lookup" in signals
    assert "service_answer_extraction" not in signals


def test_visible_context_direct_device_setting_is_not_precondition_workflow() -> None:
    signals = _visible_task_signals(
        "Turn off cellular service.",
        (
            "set_cellular_service_status",
            "get_cellular_service_status",
            "send_message_with_phone_number",
            "search_location_around_lat_lon",
        ),
    )

    assert "direct_device_state_action" in signals
    assert "device_state_action" in signals
    assert "state_precondition_possible" not in signals


def test_complete_tools_direct_device_setting_births_action_and_sequence_tools(
    monkeypatch,
) -> None:
    context = ExecutionContext(
        tool_allow_list=[
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "end_conversation",
        ]
    )
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Turn off cellular service.",
            }
        ],
    )

    observations = classify_visible_task_observations(
        "redacted", Scenario(starting_context=context)
    )
    keys = {observation.canonical_key for observation in observations}

    assert "state_precondition:apply_single_device_state_action" in keys
    assert "state_precondition:plan_device_state_action_sequence" in keys


def test_visible_context_dependent_device_setting_is_precondition_workflow() -> None:
    signals = _visible_task_signals(
        "Send a message to Alex saying hi. Resolve any issue alone.",
        (
            "set_cellular_service_status",
            "get_cellular_service_status",
            "send_message_with_phone_number",
            "search_contacts",
        ),
    )

    assert "state_precondition_possible" in signals


def test_visible_context_relationship_lookup_can_seed_batch_update_for_followup() -> (
    None
):
    signals = _visible_task_signals(
        "Who are my friends?",
        ("search_contacts", "modify_contact"),
    )

    assert "contact_lookup" in signals
    assert "relationship_batch_update" in signals


def test_visible_context_relationship_update_requires_change_intent() -> None:
    signals = _visible_task_signals(
        "Can you update all of them to enemies?",
        ("search_contacts", "modify_contact"),
    )

    assert "relationship_batch_update" in signals


def test_visible_context_contact_message_recency_update_is_not_generic_recency_action() -> (
    None
):
    signals = _visible_task_signals(
        "Update the phone number of the last person I sent a message to to +10293847563",
        ("search_messages", "modify_contact", "search_contacts"),
    )

    assert "message_counterparty_update" in signals
    assert "contact_lookup" not in signals
    assert "direct_contact_action" not in signals
    assert "recency_action" not in signals


def test_visible_context_contacted_last_update_is_message_counterparty_update() -> None:
    signals = _visible_task_signals(
        "Find whoever I contacted last, change his cell to +10293847563.",
        ("search_messages", "modify_contact", "search_contacts"),
    )

    assert "message_counterparty_update" in signals
    assert "message_counterparty_lookup" in signals
    assert "message_recency_search" in signals
    assert "contact_lookup" not in signals
    assert "direct_contact_action" not in signals
    assert "recency_action" not in signals


def test_visible_context_mark_latest_sender_is_message_counterparty_update() -> None:
    signals = _visible_task_signals(
        "Whoever wrote to me most recently should be marked as my coworker.",
        ("search_messages", "modify_contact", "search_contacts"),
    )

    assert "message_counterparty_update" in signals
    assert "contact_lookup" not in signals


def test_visible_context_reminder_recency_update_still_routes_recency_action() -> None:
    signals = _visible_task_signals(
        "Postpone my most recent reminder to tomorrow 5PM.",
        ("search_reminder", "modify_reminder"),
    )

    assert "recency_action" in signals
    assert "past_reminder_recency_search" in signals


def test_visible_context_upcoming_reminder_push_routes_recency_action() -> None:
    signals = _visible_task_signals(
        "Push my upcoming reminder to tomorrow 5PM.",
        ("search_reminder", "modify_reminder"),
    )

    assert "reminder_modify" in signals
    assert "recency_action" in signals
    assert "upcoming_reminder_search" in signals


def test_visible_context_reminder_recency_remove_still_routes_recency_action() -> None:
    signals = _visible_task_signals(
        "Get rid of my next reminder.",
        ("search_reminder", "remove_reminder", "search_messages"),
    )

    assert "recency_action" in signals
    assert "upcoming_reminder_search" in signals
    assert "message_recency" not in signals


def test_visible_upcoming_reminder_uses_small_search_argument_contract() -> None:
    context = ExecutionContext(
        tool_allow_list=["search_reminder", "remove_reminder", "search_messages"]
    )
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Get rid of my next reminder.",
            }
        ],
    )

    observations = classify_visible_task_observations(
        "redacted", Scenario(starting_context=context)
    )
    keys = {observation.canonical_key for observation in observations}

    assert "derived_value:prepare_upcoming_reminder_search_args" in keys
    assert "derived_value:resolve_search_window_or_bounds" not in keys
    upcoming = next(
        observation
        for observation in observations
        if observation.canonical_key
        == "derived_value:prepare_upcoming_reminder_search_args"
    )
    assert upcoming.validation_examples[0].expected["search_kwargs"] == {
        "reminder_timestamp_lowerbound": 1700000000.0
    }


def test_visible_context_reminder_recency_does_not_birth_message_selector() -> None:
    signals = _visible_task_signals(
        "Postpone my most recent reminder to tomorrow 5PM.",
        ("search_reminder", "modify_reminder", "search_messages"),
    )

    assert "recency_action" in signals
    assert "message_recency" not in signals


def test_native_action_contract_is_prioritized_before_preparatory_tools(
    monkeypatch,
) -> None:
    context = ExecutionContext(
        tool_allow_list=[
            "search_reminder",
            "modify_reminder",
            "search_messages",
        ]
    )
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Postpone my most recent reminder to tomorrow 5PM.",
            }
        ],
    )
    observations = classify_visible_task_observations(
        "redacted", Scenario(starting_context=context)
    )
    priorities = {
        observation.canonical_key: _native_action_observation_priority(observation)
        for observation in observations
    }

    assert priorities["search_filter:select_action_target_by_recency"] == 0
    assert priorities["search_filter:select_record_by_timestamp_extreme"] == 1
    assert "canonicalizer:relative_day_time_timestamp" in priorities
    assert "derived_value:prepare_past_reminder_recency_search_args" in priorities
    assert "derived_value:resolve_search_window_or_bounds" not in priorities


@dataclass
class FakeRecencyGenerator:
    calls: int = 0

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        assert request.suggested_tool_name == _TOOL_NAME
        spec = ToolSpec(
            tool_name=_TOOL_NAME,
            family=ToolFamily("derived_value_calculator"),
            description="Convert recency label to Unix timestamp lower/upper bounds.",
            inputs=(
                ToolInput("recency_label", "str", "Recency word, e.g. yesterday."),
                ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "lower_bound": {"type": "number"},
                    "upper_bound": {"type": "number"},
                },
            },
            positive_triggers=("bounded_recency_search",),
            negative_triggers=("ambiguous_recency_label",),
            preserves_side_effect_tools=(
                "search_messages",
                "search_reminders",
            ),
            required_original_tool_calls=("search_messages",),
            generalization_rationale="Recency-to-bounds needed across reminder/message search.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=("reminder_search", "message_search"),
            reason_tool_is_decisive=(
                "It compresses phrase interpretation, time-bound construction, and "
                "downstream search-argument preparation across search tasks."
            ),
            shortfall_cluster_evidence=("bounded_recency_search_failures",),
            known_failure_mechanisms_addressed=("missing_timestamp_bounds",),
            inadequacy_evidence="Base toolset lacks a single recency→bounds helper.",
        )
        code = (
            "def recency_to_timestamp_bounds(recency_label: str, current_timestamp: float) -> dict:\n"
            "    SECONDS_PER_DAY = 86400\n"
            "    label = recency_label.strip().lower()\n"
            "    day_start = float(int(current_timestamp) // SECONDS_PER_DAY * SECONDS_PER_DAY)\n"
            "    if label == 'yesterday':\n"
            "        return {'lower_bound': day_start - SECONDS_PER_DAY, 'upper_bound': day_start}\n"
            "    if label in ('today', 'earlier today'):\n"
            "        return {'lower_bound': day_start, 'upper_bound': current_timestamp}\n"
            "    if 'upcoming' in label or label == 'future':\n"
            "        return {'lower_bound': current_timestamp, 'upper_bound': current_timestamp + 365 * SECONDS_PER_DAY}\n"
            "    return {'lower_bound': 0.0, 'upper_bound': current_timestamp}\n"
        )
        return GeneratedTool(spec=spec, code=code)


@dataclass
class FakeRecordSelectorGenerator:
    invalid_attempts: int = 0
    calls: int = 0

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        assert request.suggested_tool_name == _RECORD_SELECTOR_TOOL_NAME
        spec = ToolSpec(
            tool_name=_RECORD_SELECTOR_TOOL_NAME,
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select the oldest or latest record by a timestamp field.",
            inputs=(
                ToolInput("records", "list", "Candidate records."),
                ToolInput("timestamp_key", "str", "Timestamp field name."),
                ToolInput("selection_mode", "str", "Either latest or oldest."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_index": {"type": "integer"},
                    "selected_timestamp": {"type": "number"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("visible_candidate_list_wrong_selected_record",),
            negative_triggers=("no_valid_timestamp_candidates",),
            preserves_side_effect_tools=(
                "search_messages",
                "modify_contact",
                "modify_reminder",
            ),
            required_original_tool_calls=("search_messages", "modify_contact"),
            abstain_behavior=(
                "Return {} when there are no valid timestamped candidates or ties "
                "make the selection ambiguous."
            ),
            generalization_rationale=(
                "Timestamp record selection is reused across search and modify tasks."
            ),
            estimated_step_compression=3,
            cross_task_applicability_count=3,
            applicable_task_families=(
                "message_search",
                "contact_update",
                "reminder_modify",
            ),
            reason_tool_is_decisive=(
                "It compresses candidate inspection, timestamp comparison, and "
                "record selection before the original side-effect tool is called."
            ),
            shortfall_cluster_evidence=("visible_candidate_selection_failures",),
            known_failure_mechanisms_addressed=("wrong_timestamp_extreme_selected",),
            inadequacy_evidence=(
                "The base tools return candidate records but do not select the "
                "requested timestamp extreme."
            ),
        )
        if self.calls <= self.invalid_attempts:
            code = (
                "def select_record_by_timestamp_extreme(records: list, "
                "timestamp_key: str, selection_mode: str) -> dict:\n"
                "    if True return {}\n"
            )
        else:
            code = (
                "def select_record_by_timestamp_extreme(records: list, "
                "timestamp_key: str, selection_mode: str) -> dict:\n"
                "    mode = selection_mode.strip().lower()\n"
                "    if mode not in ('latest', 'oldest'):\n"
                "        return {'selected_record': {}, 'selected_index': -1, 'selected_timestamp': 0.0, 'abstain_reason': 'invalid_selection_mode'}\n"
                "    filtered = []\n"
                "    for index, item in enumerate(records):\n"
                "        value = item.get(timestamp_key) if isinstance(item, dict) else None\n"
                "        if isinstance(value, (int, float)):\n"
                "            filtered.append((index, item, float(value)))\n"
                "    if not filtered:\n"
                "        return {'selected_record': {}, 'selected_index': -1, 'selected_timestamp': 0.0, 'abstain_reason': 'no_numeric_timestamp'}\n"
                "    reverse = mode == 'latest'\n"
                "    ordered = sorted(filtered, key=lambda item: item[2], reverse=reverse)\n"
                "    if len(ordered) > 1 and ordered[0][2] == ordered[1][2]:\n"
                "        return {'selected_record': {}, 'selected_index': -1, 'selected_timestamp': ordered[0][2], 'abstain_reason': 'ambiguous_tie'}\n"
                "    index, record, timestamp = ordered[0]\n"
                "    return {'selected_record': record, 'selected_index': index, 'selected_timestamp': timestamp, 'abstain_reason': ''}\n"
            )
        return GeneratedTool(spec=spec, code=code)


@dataclass
class FakeRepairRecordSelectorGenerator(FakeRecordSelectorGenerator):
    repair_calls: int = 0

    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool:
        self.repair_calls += 1
        self.invalid_attempts = 0
        return self.generate(request)


@dataclass
class FakeRepairCandidateBatchGenerator(FakeRecordSelectorGenerator):
    repair_calls: int = 0

    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool:
        raise AssertionError("batch-aware repair should validate repair_candidates")

    def repair_candidates(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> tuple[GeneratedTool, ...]:
        self.repair_calls += 1
        self.invalid_attempts = 0
        return rejected_tool, self.generate(request)


@dataclass
class FakeStagedRepairRecordSelectorGenerator(FakeRecordSelectorGenerator):
    repair_calls: int = 0
    repair_error_inputs: tuple[tuple[str, ...], ...] = ()

    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool:
        self.repair_calls += 1
        self.repair_error_inputs += (errors,)
        if "if True return" in rejected_tool.code:
            return GeneratedTool(
                spec=rejected_tool.spec,
                code=rejected_tool.code.replace("if True return", "if False return"),
            )
        self.invalid_attempts = 0
        return self.generate(request)


@dataclass
class FakeContactLookupGenerator:
    calls: int = 0

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        assert request.suggested_tool_name == _CONTACT_LOOKUP_TOOL_NAME
        spec = ToolSpec(
            tool_name=_CONTACT_LOOKUP_TOOL_NAME,
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare original search_contacts kwargs from scalar contact constraints.",
            inputs=(
                ToolInput("contact_name", "str", "Visible contact name."),
                ToolInput("phone_number", "str", "Visible phone number."),
                ToolInput("relationship", "str", "Visible relationship."),
                ToolInput("requested_field", "str", "Requested answer field."),
                ToolInput("selected_record", "dict", "Visible contact record."),
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
                },
            },
            positive_triggers=("search_phone_number_with_name",),
            negative_triggers=("missing_lookup_constraint",),
            preserves_side_effect_tools=("search_contacts",),
            required_original_tool_calls=("search_contacts",),
            abstain_behavior="Abstain when requested_field or contact constraints are missing.",
            generalization_rationale="Scalar contact lookup recurs before contact actions.",
            estimated_step_compression=3,
            cross_task_applicability_count=2,
            applicable_task_families=(
                "search_phone_number_with_name",
                "search_name_with_relationship",
            ),
            reason_tool_is_decisive="It prepares original search_contacts kwargs and answer field.",
            shortfall_cluster_evidence=("composite:plan_contact_lookup_query",),
            known_failure_mechanisms_addressed=("contact_lookup_argument_planning",),
            final_state_preservation_plan="Caller executes search_contacts later.",
            inadequacy_evidence={
                "summary": "Missing contact lookup planner.",
                "signals": ("visible_contact_scalar_constraint_unused",),
                "failed_tool_calls": ("search_contacts",),
            },
        )
        code = """
def plan_contact_lookup_query(contact_name: str = "", phone_number: str = "", relationship: str = "", requested_field: str = "", selected_record: dict = {}) -> dict:
    requested = str(requested_field or "").strip()
    kwargs = {}
    if str(contact_name or "").strip():
        kwargs["name"] = str(contact_name).strip()
    if str(phone_number or "").strip():
        kwargs["phone_number"] = str(phone_number).strip()
    if str(relationship or "").strip():
        kwargs["relationship"] = str(relationship).strip()
    if not requested:
        return {"should_call_search_contacts": False, "search_contacts_kwargs": {}, "answer_field": "", "selected_record": {}, "answer_value": "", "final_answer_recommendation": "", "copy_exactly": False, "abstain_reason": "missing_requested_field"}
    selected = selected_record if isinstance(selected_record, dict) else {}
    if selected:
        value = str(selected.get(requested) or "").strip()
        final = value
        if requested == "phone_number" and str(contact_name or "").strip():
            final = str(contact_name).strip() + "'s phone number is " + value
        if requested == "relationship" and str(phone_number or "").strip():
            final = str(phone_number).strip() + " is your " + value
        return {"should_call_search_contacts": False, "search_contacts_kwargs": kwargs, "answer_field": requested, "selected_record": selected, "answer_value": value, "final_answer_recommendation": final, "copy_exactly": bool(final), "abstain_reason": ""}
    if not kwargs:
        return {"should_call_search_contacts": False, "search_contacts_kwargs": {}, "answer_field": requested, "selected_record": {}, "answer_value": "", "final_answer_recommendation": "", "copy_exactly": False, "abstain_reason": "missing_lookup_constraint"}
    return {"should_call_search_contacts": True, "search_contacts_kwargs": kwargs, "answer_field": requested, "selected_record": {}, "answer_value": "", "final_answer_recommendation": "", "copy_exactly": False, "abstain_reason": ""}
""".strip()
        return GeneratedTool(spec=spec, code=code)


def _resolve_search_window_tool() -> GeneratedTool:
    spec = ToolSpec(
        tool_name=_RESOLVE_WINDOW_TOOL_NAME,
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description=(
            "Prepare bounded search kwargs from natural time phrases before "
            "calling original reminder or message search tools."
        ),
        inputs=(
            ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ToolInput("phrase", "str", "Natural time phrase."),
            ToolInput("target_domain", "str", "reminder or message."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "target_tool_name": {"type": "string"},
                "search_kwargs": {"type": "object"},
                "should_call_search": {"type": "boolean"},
            },
        },
        positive_triggers=("bounded_time_search_needed",),
        negative_triggers=("ambiguous_phrase",),
        preserves_side_effect_tools=("search_messages", "search_reminder"),
        required_original_tool_calls=("search_messages",),
        abstain_behavior="Return should_call_search false for ambiguous phrases.",
        generalization_rationale=(
            "The same bounded search preparation is useful for reminder and "
            "message retrieval tasks."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("message_search_window", "reminder_search_window"),
        reason_tool_is_decisive=(
            "It compresses current-time lookup, phrase interpretation, bounds "
            "construction, and downstream search-argument preparation."
        ),
        shortfall_cluster_evidence=("bounded_search_window_failures",),
        known_failure_mechanisms_addressed=("empty_or_unbounded_search_kwargs",),
        inadequacy_evidence={
            "summary": "Repeated search tasks need deterministic timestamp bounds.",
            "signals": ("repeated_failed_tool_call",),
            "failed_tool_calls": ("search_messages",),
            "repeated_failed_tool_calls": (),
            "visible_data_gaps": ("missing search timestamp bounds",),
            "planner_failures": (),
            "final_answer_route_mismatch": False,
        },
    )
    code = (
        "def resolve_search_window_or_bounds(current_timestamp: float, phrase: str, target_domain: str) -> dict:\n"
        "    return {'target_tool_name': 'search_messages', 'search_kwargs': {'creation_timestamp_upperbound': current_timestamp}, 'should_call_search': True}\n"
    )
    return GeneratedTool(spec=spec, code=code)


def _latest_record_observation():
    return _latest_record_selection_observation(
        "visible_task_context(message_recency,contact_update)"
    )


def test_visible_context_first_ever_text_marks_message_recency() -> None:
    signals = _visible_task_signals(
        "What's the first ever text I have?",
        ("search_messages",),
    )

    assert "message" in signals
    assert "message_recency" in signals
    assert "recency_search" in signals


def test_visible_context_oldest_message_with_send_tool_is_read_only() -> None:
    signals = _visible_task_signals(
        "What does my oldest message say?",
        (
            "search_messages",
            "send_message_with_phone_number",
            "get_current_timestamp",
        ),
    )

    assert "message" in signals
    assert "message_recency" in signals
    assert "recency_search" in signals
    assert "send_message" not in signals
    assert "safe_abstain_needed" not in signals


def test_visible_context_explicit_text_request_still_marks_send_intent() -> None:
    signals = _visible_task_signals(
        "Text Alice that I am running late",
        (
            "search_contacts",
            "send_message_with_phone_number",
        ),
    )

    assert "send_message" in signals
    assert "named_message_recipient" in signals


def test_visible_context_vague_message_search_marks_followup_possible() -> None:
    signals = _visible_task_signals(
        "There's a text I want to find",
        ("search_messages",),
    )

    assert "message" in signals
    assert "message_search_followup_possible" in signals
    assert "device_state_action" not in signals
    assert "state_precondition_possible" not in signals


def test_rejected_birth_can_retry_on_later_observation(tmp_path: Path) -> None:
    observation = _latest_record_observation()
    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecordSelectorGenerator(invalid_attempts=1)
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=1,
    )

    controller.observe(observation)
    assert generator.calls == 1
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is None

    controller.observe(observation)
    assert generator.calls == 2
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is not None
    assert (
        "search_filter:select_record_by_timestamp_extreme" in controller.generated_keys
    )
    assert (
        controller.rejected_counts["search_filter:select_record_by_timestamp_extreme"]
        == 1
    )

    birth_events = [
        json.loads(line)
        for line in (tmp_path / "tool_birth_events.jsonl").read_text().splitlines()
    ]
    assert [event["accepted"] for event in birth_events] == [False, True]


def test_native_action_repair_ranking_keeps_near_argument_match() -> None:
    near_match = ValidationResult(
        accepted=False,
        errors=(
            "source_0_native_action_arguments:{'person_id': 'p1', "
            "'phone_number': '+1555', 'relationship': None}!="
            "{'person_id': 'p1', 'phone_number': '+1555', "
            "'relationship': NOT_GIVEN}",
        ),
    )
    missing_action = ValidationResult(
        accepted=False,
        errors=(
            "source_0_native_action_count:0!=1:"
            "expected=modify_contact:{'person_id': 'p1'}",
        ),
    )

    assert _validation_failure_score(near_match) < _validation_failure_score(
        missing_action
    )


def test_native_action_repair_ranking_never_prefers_invalid_python() -> None:
    executable_candidate = ValidationResult(
        accepted=False,
        errors=("negative_0_unexpected_native_action:modify_contact",),
    )
    syntax_failure = ValidationResult(
        accepted=False,
        errors=("syntax_error:invalid syntax",),
    )

    assert _validation_failure_score(executable_candidate) < (
        _validation_failure_score(syntax_failure)
    )

    invalid_shape = ValidationResult(
        accepted=False,
        errors=("expected_exactly_one_function",),
    )
    assert _validation_failure_score(executable_candidate) < (
        _validation_failure_score(invalid_shape)
    )


def test_native_action_repair_can_advance_across_complementary_case_failures() -> None:
    previous = (
        "negative_3_unexpected_native_action:add_reminder",
        "negative_3_native_action_abstain_status_missing",
    )
    repaired = (
        "source_0_native_action_count:0!=1:expected=add_reminder:{}",
        "held_out_0_native_action_count:0!=1:expected=add_reminder:{}",
    )

    assert _validation_error_case_labels(previous) == {"negative_3"}
    assert _validation_error_case_labels(repaired) == {"source_0", "held_out_0"}
    assert _advances_repair_case_frontier(previous, repaired)
    assert not _advances_repair_case_frontier(previous, (*previous, *repaired))
    assert not _advances_repair_case_frontier(previous, ("syntax_error:bad",))


def test_just_in_time_birth_stops_after_validated_native_action_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_PROACTIVE_BIRTH", "1")
    observations = (_latest_record_observation(), _latest_record_observation())
    monkeypatch.setattr(
        online_birth,
        "classify_visible_task_observations",
        lambda _name, _scenario: observations,
    )
    store = RegistryStore(tmp_path / "registry")
    emitted_events: list[str] = []
    controller = OnlineBirthController(
        store=store,
        generator=FakeRecordSelectorGenerator(),
        output_dir=tmp_path,
        recurrence_threshold=1,
        event_hook=lambda event, _payload: emitted_events.append(event),
    )
    observed: list[str] = []

    def observe(observation) -> str:
        observed.append(observation.canonical_key)
        return "complete_action"

    monkeypatch.setattr(controller, "observe", observe)
    monkeypatch.setattr(
        store,
        "get",
        lambda _name: SimpleNamespace(
            tool=SimpleNamespace(spec=SimpleNamespace(native_action_delegation=True))
        ),
    )

    accepted = controller.prime_before_scenario("redacted", Scenario())

    assert accepted == ["complete_action"]
    assert len(observed) == 1
    assert "redacted" in controller.pre_scenario_visible_observations
    assert "jit_proactive_birth_stopped_after_action_tool" in emitted_events


def test_just_in_time_birth_stops_for_existing_validated_native_action_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_PROACTIVE_BIRTH", "1")
    observations = (_latest_record_observation(), _latest_record_observation())
    monkeypatch.setattr(
        online_birth,
        "classify_visible_task_observations",
        lambda _name, _scenario: observations,
    )
    monkeypatch.setattr(
        online_birth, "has_current_validation_proof", lambda _entry: True
    )
    store = RegistryStore(tmp_path / "registry")
    emitted_events: list[str] = []
    controller = OnlineBirthController(
        store=store,
        generator=FakeRecordSelectorGenerator(),
        output_dir=tmp_path,
        recurrence_threshold=1,
        event_hook=lambda event, _payload: emitted_events.append(event),
    )
    observed: list[str] = []

    def observe(observation) -> None:
        observed.append(observation.canonical_key)
        return None

    monkeypatch.setattr(controller, "observe", observe)
    monkeypatch.setattr(
        store,
        "get",
        lambda _name: SimpleNamespace(
            retired=False,
            tool=SimpleNamespace(spec=SimpleNamespace(native_action_delegation=True)),
        ),
    )

    accepted = controller.prime_before_scenario("redacted", Scenario())

    assert accepted == []
    assert len(observed) == 1
    assert "jit_proactive_birth_stopped_after_action_tool" in emitted_events


def test_just_in_time_birth_keeps_input_transforms_after_native_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_PROACTIVE_BIRTH", "1")
    observations = (
        _recency_action_target_observation("redacted"),
        _relative_day_time_timestamp_observation("redacted"),
        _resolve_search_window_or_bounds_observation("redacted"),
        _latest_record_selection_observation("redacted"),
    )
    monkeypatch.setattr(
        online_birth,
        "classify_visible_task_observations",
        lambda _name, _scenario: observations,
    )
    store = RegistryStore(tmp_path / "registry")
    emitted_events: list[str] = []
    controller = OnlineBirthController(
        store=store,
        generator=FakeRecordSelectorGenerator(),
        output_dir=tmp_path,
        recurrence_threshold=1,
        event_hook=lambda event, _payload: emitted_events.append(event),
    )
    observed: list[str] = []
    names = {
        "search_filter:select_action_target_by_recency": "complete_action",
        "canonicalizer:relative_day_time_timestamp": "canonicalize_time",
        "derived_value:resolve_search_window_or_bounds": "prepare_search",
        "search_filter:select_record_by_timestamp_extreme": "redundant_selector",
    }

    def observe(observation) -> str:
        observed.append(observation.canonical_key)
        return names[observation.canonical_key]

    monkeypatch.setattr(controller, "observe", observe)
    monkeypatch.setattr(
        store,
        "get",
        lambda name: SimpleNamespace(
            retired=False,
            tool=SimpleNamespace(
                spec=SimpleNamespace(native_action_delegation=name == "complete_action")
            ),
        ),
    )

    accepted = controller.prime_before_scenario("redacted", Scenario())

    assert accepted == ["complete_action", "canonicalize_time", "prepare_search"]
    assert observed == [
        "search_filter:select_action_target_by_recency",
        "canonicalizer:relative_day_time_timestamp",
        "derived_value:resolve_search_window_or_bounds",
    ]
    assert "jit_proactive_action_tool_ready" in emitted_events
    assert "jit_proactive_birth_stopped_after_action_tool" in emitted_events


def test_native_action_complements_allow_read_only_producers_not_second_action(
    monkeypatch,
) -> None:

    assert _complements_validated_native_action(
        _location_search_argument_observation("visible request")
    )
    assert _complements_validated_native_action(
        _plan_device_state_action_sequence_observation(
            "visible_task_context location_phrase reminder"
        )
    )
    assert not _complements_validated_native_action(
        _reminder_optional_location_argument_observation("visible request")
    )


def test_rejected_birth_retry_is_capped(tmp_path: Path) -> None:
    observation = _latest_record_observation()
    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecordSelectorGenerator(invalid_attempts=10)
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=1,
        max_rejections_per_key=2,
    )

    for _ in range(4):
        controller.observe(observation)

    assert generator.calls == 2
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is None
    assert (
        controller.rejected_counts["search_filter:select_record_by_timestamp_extreme"]
        == 2
    )
    assert (
        "tool_birth_retry_suppressed"
        in (tmp_path / "sage_run_events.jsonl").read_text()
    )


def test_candidate_repair_pass_can_accept_initial_rejection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "candidate_repair")
    observation = _latest_record_observation()
    store = RegistryStore(tmp_path / "registry")
    generator = FakeRepairRecordSelectorGenerator(invalid_attempts=1)
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=1,
        failure_memory_path=None,
    )

    controller.observe(observation)

    assert generator.calls == 2
    assert generator.repair_calls == 1
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is not None
    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is True
    assert birth_event["repair_attempted"] is True
    assert birth_event["repair_attempt_count"] == 1
    assert birth_event["repair_final_errors"] == []


def test_candidate_repair_validates_every_model_authored_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "candidate_repair")
    observation = _latest_record_observation()
    store = RegistryStore(tmp_path / "registry")
    generator = FakeRepairCandidateBatchGenerator(invalid_attempts=1)
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=1,
        failure_memory_path=None,
    )

    controller.observe(observation)

    assert generator.repair_calls == 1
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is not None
    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    repair_event = birth_event["repair_history"][0]
    assert repair_event["repair_candidate_count"] == 2
    assert repair_event["selected_candidate_index"] == 1
    assert repair_event["repair_candidate_validations"][0]["accepted"] is False
    assert repair_event["repair_candidate_validations"][1]["accepted"] is True


def test_candidate_repair_can_build_on_flat_intermediate_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "candidate_repair")
    monkeypatch.setenv("SAGE_CANDIDATE_REPAIR_ATTEMPTS", "2")
    observation = _latest_record_observation()
    store = RegistryStore(tmp_path / "registry")
    generator = FakeStagedRepairRecordSelectorGenerator(invalid_attempts=1)
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=1,
        failure_memory_path=None,
    )

    controller.observe(observation)

    assert generator.repair_calls == 2
    substantive_errors = [
        {error for error in errors if not error.startswith("repair_strategy:")}
        for errors in generator.repair_error_inputs
    ]
    assert substantive_errors[0].issubset(substantive_errors[1])
    assert [
        next(error for error in errors if error.startswith("repair_strategy:"))
        for errors in generator.repair_error_inputs
    ] == ["repair_strategy:1", "repair_strategy:2"]
    assert store.get(_RECORD_SELECTOR_TOOL_NAME) is not None
    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is True
    assert birth_event["repair_attempt_count"] == 2


def test_recency_action_contract_is_decomposed_to_reminder_actions() -> None:
    observation = _recency_action_target_observation("redacted")
    positive_examples = [
        example
        for example in observation.validation_examples
        if not example.negative_applicability
    ]
    actions = {
        str(example.expected.get("downstream_tool_name") or "")
        for example in positive_examples
    }
    modes = {
        str(example.inputs.get("selection_mode") or "") for example in positive_examples
    }
    negative_examples = [
        example
        for example in observation.validation_examples
        if example.negative_applicability
    ]

    assert actions == {"modify_reminder", "remove_reminder"}
    assert modes == {"latest", "oldest"}
    assert negative_examples[0].inputs["updates"] == {"reminder_timestamp": 99.0}
