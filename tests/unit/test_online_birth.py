import json
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adequacy.inadequacy_classifier import classify_scenario_observations
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.online_birth import OnlineBirthController
from sage_ts.registry.store import RegistryStore

from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario

_TOOL_NAME = "recency_to_timestamp_bounds"


@dataclass
class FakeRecencyGenerator:
    calls: int = 0

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
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
    scenario = Scenario(categories=[ScenarioCategories.CANONICALIZATION])  # type: ignore[list-item]
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0},
    )
    assert len(observations) == 1
    assert observations[0].canonical_key == "derived_value:recency_timestamp_bounds"
    assert observations[0].generation_allowed

    store = RegistryStore(tmp_path / "registry")
    generator = FakeRecencyGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
    )

    controller.observe(observations[0])
    assert generator.calls == 0
    assert store.get(_TOOL_NAME) is None

    controller.observe(observations[0])
    assert generator.calls == 1
    assert store.get(_TOOL_NAME) is not None

    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is True
    assert birth_event["tool_name"] == _TOOL_NAME
