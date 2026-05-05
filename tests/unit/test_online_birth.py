# mypy: ignore-errors
import json
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adequacy.inadequacy_classifier import classify_scenario_observations
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.online_birth import OnlineBirthController
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ValidationResult
from tool_sandbox.common.execution_context import ExecutionContext, ScenarioCategories
from tool_sandbox.common.scenario import Scenario

_TOOL_NAME = "recency_to_timestamp_bounds"
_RELATIVE_TIME_TOOL_NAME = "relative_day_time_to_timestamp"
_RECORD_SELECTOR_TOOL_NAME = "select_record_by_timestamp_extreme"
_RESOLVE_WINDOW_TOOL_NAME = "resolve_search_window_or_bounds"


def test_generic_dependency_bundle_observation_uses_allowed_tool_structure(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "dependency_logic")
    scenario = Scenario(
        starting_context=ExecutionContext(
            tool_allow_list=[
                "set_example_service_status",
                "search_records",
                "send_message",
            ]
        )
    )

    observations = classify_scenario_observations(
        "generic_dependency_bundle_case",
        scenario,
        {"similarity": 0.0},
    )

    dependency = next(
        observation
        for observation in observations
        if observation.canonical_key
        == "state_precondition:dependency_precondition_tool_call"
    )
    assert dependency.generation_allowed
    assert dependency.failed_tool_calls == ("set_example_service_status",)


def test_dependency_bundle_feature_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "grading_accounting")
    scenario = Scenario(
        starting_context=ExecutionContext(
            tool_allow_list=[
                "set_example_service_status",
                "search_records",
                "send_message",
            ]
        )
    )

    observations = classify_scenario_observations(
        "generic_dependency_bundle_case",
        scenario,
        {"similarity": 0.0},
    )

    assert not any(
        observation.canonical_key
        == "state_precondition:dependency_precondition_tool_call"
        for observation in observations
    )


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
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    observations = classify_scenario_observations(
        "modify_contact_with_message_recency_10_distraction_tools",
        scenario,
        {"similarity": 0.0},
    )
    return next(
        observation
        for observation in observations
        if observation.canonical_key
        == "search_filter:select_record_by_timestamp_extreme"
    )


def test_recency_observation_rejects_bounds_only_birth_after_recurrence(
    tmp_path: Path,
) -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0},
    )
    recency = next(
        observation
        for observation in observations
        if observation.canonical_key == "derived_value:recency_timestamp_bounds"
    )
    assert recency.generation_allowed

    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecencyGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
    )

    controller.observe(recency)
    assert generator.calls == 0
    assert store.get(_TOOL_NAME) is None

    controller.observe(recency)
    assert generator.calls == 1
    assert store.get(_TOOL_NAME) is None

    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is False
    assert birth_event["tool_name"] == _TOOL_NAME
    assert birth_event["errors"] == ["bounds_only_derived_helper_low_value"]
    assert birth_event["estimated_step_compression"] == 3
    assert birth_event["cross_task_applicability_count"] == 2


def test_successful_recency_task_does_not_birth_from_task_type_alone() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 1.0},
    )

    assert observations == ()


def test_existing_bounds_only_registry_tool_does_not_skip_repaired_gate(
    tmp_path: Path,
) -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0},
    )

    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecencyGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
    )
    tool = generator.generate(
        ToolGenerationRequest(
            scenario_name="seed",
            observation="Seed accepted recency helper.",
            allowed_families=("derived_value_calculator",),
            suggested_tool_name=_TOOL_NAME,
        )
    )
    store.put(
        RegistryEntry.accepted(
            tool,
            ValidationResult(
                accepted=True,
                errors=(),
                source_example_count=1,
                held_out_check_count=1,
                runtime_smoke_passed=True,
            ),
            birth_scenario="seed",
        )
    )
    generator.calls = 0

    controller.observe(observations[0])
    controller.observe(observations[0])

    assert generator.calls == 1
    assert store.get(_TOOL_NAME) is not None
    events = (tmp_path / "tool_birth_events.jsonl").read_text()
    assert "bounds_only_derived_helper_low_value" in events


def test_existing_broader_registry_tool_suppresses_narrow_birth(
    tmp_path: Path,
) -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0},
    )
    recency = next(
        observation
        for observation in observations
        if observation.canonical_key == "derived_value:recency_timestamp_bounds"
    )

    store = RegistryStore(tmp_path / "registry")
    store.put(
        RegistryEntry.accepted(
            _resolve_search_window_tool(),
            ValidationResult(
                accepted=True,
                errors=(),
                source_example_count=1,
                held_out_check_count=1,
                runtime_smoke_passed=True,
            ),
            birth_scenario="seed",
        )
    )
    generator = FakeRecencyGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
    )

    controller.observe(recency)
    controller.observe(recency)

    assert generator.calls == 0
    assert store.get(_TOOL_NAME) is None
    assert "derived_value:recency_timestamp_bounds" in controller.generated_keys
    events = (tmp_path / "sage_run_events.jsonl").read_text()
    assert "tool_birth_skipped_existing_broader_helper" in events
    assert _RESOLVE_WINDOW_TOOL_NAME in events


def test_modify_reminder_relative_datetime_observation_is_canonicalizer() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "modify_reminder_with_recency_latest_3_distraction_tools",
        scenario,
        {"similarity": 2 / 3},
    )

    keys = {observation.canonical_key for observation in observations}
    assert "derived_value:recency_timestamp_bounds" in keys
    assert "canonicalizer:relative_day_time_timestamp" in keys

    relative = next(
        observation
        for observation in observations
        if observation.canonical_key == "canonicalizer:relative_day_time_timestamp"
    )
    assert relative.generation_allowed
    assert relative.allowed_families == (str(ToolFamily.CANONICALIZER),)
    assert relative.validation_examples[0].inputs == {
        "current_timestamp": 1777428906.194959,
        "day_offset": 1,
        "hour": 17,
        "minute": 0,
        "local_utc_offset_hours": -4,
    }
    assert relative.validation_examples[0].expected == 1777496400.0


def test_add_reminder_optional_location_observation_prepares_side_effect_args() -> None:
    scenario = Scenario(
        categories=[
            ScenarioCategories(str(ScenarioCategories.CANONICALIZATION)),
            ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL)),
        ]
    )
    observations = classify_scenario_observations(
        "add_reminder_content_and_week_delta_and_time_and_location_3_distraction_tools",
        scenario,
        {"similarity": 0.2},
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation.canonical_key == "composite:prepare_reminder_creation_args"
    assert observation.allowed_families == (str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),)
    assert observation.generation_allowed
    assert "add_reminder" in observation.observation
    assert "must not create or modify reminders itself" in observation.observation
    assert observation.validation_examples[0].expected == {
        "add_reminder_kwargs": {
            "content": "Buy tickets",
            "reminder_timestamp": 147600.0,
            "latitude": None,
            "longitude": None,
        },
        "should_call_add_reminder": True,
        "location_status": "omitted_optional",
        "abstain_reason": "",
        "timestamp_source": "relative_fields",
    }


def test_modify_contact_message_recency_requests_search_filter_helper() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    observations = classify_scenario_observations(
        "modify_contact_with_message_recency_10_distraction_tools",
        scenario,
        {"similarity": 0.0},
    )

    selector = next(
        observation
        for observation in observations
        if observation.canonical_key
        == "search_filter:select_record_by_timestamp_extreme"
    )
    assert selector.generation_allowed
    assert selector.allowed_families == (str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),)
    assert selector.validation_examples[0].inputs == {
        "records": [
            {"content": "older", "creation_timestamp": 10.0},
            {"content": "newer", "creation_timestamp": 20.0},
        ],
        "timestamp_key": "creation_timestamp",
        "selection_mode": "latest",
    }
    assert selector.validation_examples[0].expected == {
        "selected_record": {"content": "newer", "creation_timestamp": 20.0},
        "selected_index": 1,
        "selected_timestamp": 20.0,
        "abstain_reason": "",
    }


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


def test_near_duplicate_only_birth_is_marked_diagnostic(tmp_path: Path) -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    first = next(
        item
        for item in classify_scenario_observations(
            "modify_contact_with_message_recency",
            scenario,
            {"similarity": 0.0},
        )
        if item.canonical_key == "search_filter:select_record_by_timestamp_extreme"
    )
    second = next(
        item
        for item in classify_scenario_observations(
            "modify_contact_with_message_recency_3_distraction_tools",
            scenario,
            {"similarity": 0.0},
        )
        if item.canonical_key == "search_filter:select_record_by_timestamp_extreme"
    )
    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecordSelectorGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
        failure_memory_path=None,
    )

    controller.observe(first)
    controller.observe(second)

    entry = store.get(_RECORD_SELECTOR_TOOL_NAME)
    assert entry is not None
    assert entry.tool.spec.diagnostic_only is True


def test_raw_latest_message_births_selector_and_marks_window_diagnostic() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0.0},
    )

    keys = {observation.canonical_key for observation in observations}
    assert "search_filter:select_record_by_timestamp_extreme" in keys
    assert "derived_value:message_search_time_window" in keys
    window = next(
        observation
        for observation in observations
        if observation.canonical_key == "derived_value:message_search_time_window"
    )
    assert not window.generation_allowed


def test_modify_contact_message_recency_marks_message_window_diagnostic() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    observations = classify_scenario_observations(
        "modify_contact_with_message_recency",
        scenario,
        {"similarity": 0.0},
    )

    assert {observation.canonical_key for observation in observations} == {
        "search_filter:select_record_by_timestamp_extreme",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_side_effect_args_from_selected_record",
        "derived_value:message_search_time_window",
    }
    window_helper = next(
        observation
        for observation in observations
        if observation.canonical_key == "derived_value:message_search_time_window"
    )
    assert not window_helper.generation_allowed
    assert window_helper.reason == "diagnostic_only_bounds_helper_low_value"
    assert window_helper.allowed_families == (str(ToolFamily.DERIVED_VALUE_CALCULATOR),)
    assert window_helper.validation_examples[0].inputs == {
        "anchor_timestamp": 864000.0,
        "lookback_days": 2,
    }


def test_modify_contact_message_recency_can_birth_record_selector() -> None:
    scenario = Scenario(
        categories=[
            ScenarioCategories(str(ScenarioCategories.CANONICALIZATION)),
            ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL)),
        ]
    )
    observations = classify_scenario_observations(
        "modify_contact_with_message_recency_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    keys = {observation.canonical_key for observation in observations}
    assert "derived_value:recency_timestamp_bounds" in keys
    assert "search_filter:select_record_by_timestamp_extreme" in keys


def test_oldest_record_failure_births_trace_compatible_search_helpers() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_oldest_10_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    keys = {observation.canonical_key for observation in observations}
    assert "search_filter:select_record_by_timestamp_extreme" in keys
    window = next(
        observation
        for observation in observations
        if observation.canonical_key == "derived_value:message_search_time_window"
    )
    assert not window.generation_allowed


def test_holiday_distance_failure_requests_timestamp_diff_helper() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "find_days_till_holiday_3_distraction_tools_tool_name_scrambled",
        scenario,
        {"similarity": 0.5},
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation.canonical_key == "derived_value:days_between_timestamps"
    assert observation.generation_allowed
    assert observation.allowed_families == (str(ToolFamily.DERIVED_VALUE_CALCULATOR),)
    assert observation.validation_examples[1].expected == {
        "days": 1,
        "seconds": 3661,
    }


def test_direct_contact_remove_by_phone_failure_births_constraint_helpers() -> None:
    scenario = Scenario(categories=[ScenarioCategories.MULTIPLE_TOOL_CALL])

    observations = classify_scenario_observations(
        "remove_contact_by_phone_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert [item.canonical_key for item in observations] == [
        "search_filter:select_visible_record_by_constraints",
        "composite:prepare_side_effect_args_from_selected_record",
    ]


def test_ambiguous_contact_lookup_failure_does_not_birth_helper() -> None:
    scenario = Scenario(categories=[ScenarioCategories.MULTIPLE_TOOL_CALL])

    observations = classify_scenario_observations(
        "remove_contact_by_phone_ambiguous_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert observations == ()


def test_contact_update_failure_births_contact_selection_helper() -> None:
    scenario = Scenario(categories=[ScenarioCategories.MULTIPLE_TOOL_CALL])

    observations = classify_scenario_observations(
        "update_contact_relationship_with_relationship_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert [item.canonical_key for item in observations] == [
        "search_filter:select_visible_record_by_constraints",
        "composite:prepare_side_effect_args_from_selected_record",
    ]


def test_recency_action_failure_births_action_target_and_arg_prep_helpers() -> None:
    scenario = Scenario(categories=[ScenarioCategories.MULTIPLE_TOOL_CALL])

    observations = classify_scenario_observations(
        "remove_reminder_with_recency_latest_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    keys = {item.canonical_key for item in observations}
    assert "search_filter:select_action_target_by_recency" in keys
    assert "composite:prepare_side_effect_args_from_selected_record" in keys


def test_stock_symbol_failure_births_symbol_extraction_helper() -> None:
    scenario = Scenario(categories=[ScenarioCategories.MULTIPLE_TOOL_CALL])

    observations = classify_scenario_observations(
        "find_stock_symbol_with_company_name_low_battery_mode_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert [item.canonical_key for item in observations] == [
        "derived_value:extract_stock_symbol"
    ]
    assert observations[0].validation_examples[-1].expected == ""
    assert observations[0].validation_examples[-1].negative_applicability


def test_medium_grain_constraint_action_observation_is_opt_in(
    monkeypatch,
) -> None:
    scenario = Scenario(starting_context=ExecutionContext())

    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "contract_synthesis")
    disabled = classify_scenario_observations(
        "update_contact_relationship_with_relationship_3_distraction_tools",
        scenario,
        {"similarity": 0.0},
    )
    assert not any(
        item.canonical_key == "composite:constraint_to_action_planner"
        for item in disabled
    )

    monkeypatch.setenv(
        "SAGE_V2_EXPERIMENT_FEATURES",
        "contract_synthesis,medium_grain_skills",
    )
    enabled = classify_scenario_observations(
        "update_contact_relationship_with_relationship_3_distraction_tools",
        scenario,
        {"similarity": 0.0},
    )
    medium = next(
        item
        for item in enabled
        if item.canonical_key == "composite:constraint_to_action_planner"
    )
    assert medium.generation_allowed
    assert medium.allowed_families == ("composite_workflow_helper",)
    assert len(medium.validation_examples) >= 4
    assert any(item.negative_applicability for item in medium.validation_examples)


def test_direct_state_failure_births_trace_compatible_tool_call_helper() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.STATE_DEPENDENCY))]
    )

    observations = classify_scenario_observations(
        "turn_on_wifi_low_battery_mode_implicit_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert [item.canonical_key for item in observations] == [
        "state_precondition:next_service_tool_call"
    ]
    observation = observations[0]
    assert observation.generation_allowed
    assert observation.allowed_families == (str(ToolFamily.STATE_PRECONDITION_HELPER),)
    assert observation.validation_examples[0].expected == {
        "ready": False,
        "tool_name": "set_low_battery_mode_status",
        "arguments": {"on": False},
        "should_call": True,
        "reason": "wifi cannot be enabled while low battery mode is on",
    }
