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


@dataclass
class FakeRecencyGenerator:
    calls: int = 0

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        spec = ToolSpec(
            tool_name="canonicalize_recency_label",
            family=ToolFamily("canonicalizer"),
            description="Normalize recency labels to stable search directives.",
            inputs=(ToolInput("label", "str", "Raw recency label."),),
            output_annotation="str",
            generalization_rationale=(
                "Recency labels recur across message and reminder search scenarios."
            ),
            inadequacy_evidence=(
                "Existing tools search records, but do not normalize recency words."
            ),
        )
        code = """
def canonicalize_recency_label(label: str) -> str:
    cleaned = " ".join(label.strip().lower().split())
    if cleaned in {"newest", "latest", "recent", "most recent"}:
        return "latest"
    if cleaned in {"oldest", "earliest"}:
        return "oldest"
    if "upcoming" in cleaned:
        return "upcoming"
    if "yesterday" in cleaned:
        return "yesterday"
    return cleaned
"""
        return GeneratedTool(spec=spec, code=code)


def test_recency_observation_requires_recurrence_before_birth(tmp_path: Path) -> None:
    scenario = Scenario(categories=[ScenarioCategories.CANONICALIZATION])  # type: ignore[list-item]
    observations = classify_scenario_observations(
        "search_message_with_recency_latest",
        scenario,
        {"similarity": 0},
    )
    assert len(observations) == 1
    assert observations[0].canonical_key == "canonicalization:recency_label"
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
    assert store.get("canonicalize_recency_label") is None

    controller.observe(observations[0])
    assert generator.calls == 1
    assert store.get("canonicalize_recency_label") is not None

    birth_event = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_event["accepted"] is True
    assert birth_event["tool_name"] == "canonicalize_recency_label"
