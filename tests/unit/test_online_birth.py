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
from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario

_TOOL_NAME = "recency_to_timestamp_bounds"
_RELATIVE_TIME_TOOL_NAME = "relative_day_time_to_timestamp"


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
            generalization_rationale="Recency-to-bounds needed across reminder/message search.",
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


def test_recency_observation_requires_recurrence_before_birth(tmp_path: Path) -> None:
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
    assert store.get(_TOOL_NAME) is not None

    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is True
    assert birth_event["tool_name"] == _TOOL_NAME


def test_existing_registry_tool_skips_duplicate_birth(tmp_path: Path) -> None:
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
            ValidationResult(accepted=True, errors=()),
            birth_scenario="seed",
        )
    )
    generator.calls = 0

    controller.observe(observations[0])
    controller.observe(observations[0])

    assert generator.calls == 0
    assert store.get(_TOOL_NAME) is not None
    assert (
        "tool_birth_skipped_existing"
        in (tmp_path / "sage_run_events.jsonl").read_text()
    )


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


def test_latest_record_failure_requests_search_filter_helper() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    observations = classify_scenario_observations(
        "modify_reminder_with_recency_latest_alt_10_distraction_tools",
        scenario,
        {"similarity": 2 / 3},
    )

    selector = next(
        observation
        for observation in observations
        if observation.canonical_key
        == "search_filter:select_latest_record_by_timestamp"
    )
    assert selector.generation_allowed
    assert selector.allowed_families == (str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),)
    assert selector.validation_examples[0].inputs == {
        "records_payload": {
            "records": [
                {"content": "older", "creation_timestamp": 10.0},
                {"content": "newer", "creation_timestamp": 20.0},
            ]
        },
        "timestamp_key": "creation_timestamp",
    }
    assert selector.validation_examples[0].expected == {
        "content": "newer",
        "creation_timestamp": 20.0,
    }


def test_latest_record_failure_does_not_require_canonicalization_category() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.MULTIPLE_TOOL_CALL))]
    )
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0.0},
    )

    assert tuple(observation.canonical_key for observation in observations) == (
        "search_filter:select_latest_record_by_timestamp",
    )


def test_direct_state_failure_observation_requests_next_action_helper() -> None:
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.STATE_DEPENDENCY))]
    )

    observations = classify_scenario_observations(
        "turn_on_wifi_low_battery_mode_implicit_3_distraction_tools",
        scenario,
        {"similarity": 0.5},
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation.canonical_key == "state_precondition:service_next_action"
    assert observation.generation_allowed
    assert observation.allowed_families == (str(ToolFamily.STATE_PRECONDITION_HELPER),)
    assert observation.validation_examples[0].expected == {
        "ready": False,
        "next_action": "set_low_battery_mode_status_false",
        "target_service": "wifi",
    }
