"""Artifact-backed capability observations for online tool birth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.generation.tool_spec import ToolFamily
from sage_ts.validation.sandbox_validator import ToolExample
from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario


@dataclass(frozen=True)
class CapabilityObservation:
    scenario_name: str
    canonical_key: str
    observation: str
    allowed_families: tuple[str, ...]
    validation_examples: tuple[ToolExample, ...]
    generation_allowed: bool
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "canonical_key": self.canonical_key,
            "observation": self.observation,
            "allowed_families": list(self.allowed_families),
            "validation_examples": [
                {"inputs": item.inputs, "expected": item.expected}
                for item in self.validation_examples
            ],
            "generation_allowed": self.generation_allowed,
            "reason": self.reason,
        }


def classify_scenario_observations(
    scenario_name: str,
    scenario: Scenario,
    result: dict[str, Any],
) -> tuple[CapabilityObservation, ...]:
    """Classify only narrow, repeated ToolSandbox hard-mode observations."""
    categories = {str(category) for category in scenario.categories}
    if ScenarioCategories.INSUFFICIENT_INFORMATION in scenario.categories:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="insufficient_information",
                observation=(
                    "Scenario is marked insufficient-information; this should be "
                    "stored as abstention/guard evidence, not immediate tool birth."
                ),
                allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
                validation_examples=(),
                generation_allowed=False,
                reason="insufficient_information_observation_only",
            ),
        )

    if (
        "recency" in scenario_name
        and ScenarioCategories.CANONICALIZATION in scenario.categories
    ):
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="canonicalization:recency_label",
                observation=(
                    "Repeated ToolSandbox scenarios require normalizing user-facing "
                    "recency words such as latest, oldest, yesterday, and upcoming "
                    "before choosing search/sort arguments."
                ),
                allowed_families=(str(ToolFamily.CANONICALIZER),),
                validation_examples=(
                    ToolExample({"label": "Newest"}, "latest"),
                    ToolExample({"label": "oldest"}, "oldest"),
                    ToolExample({"label": " yesterday "}, "yesterday"),
                    ToolExample({"label": "upcoming reminders"}, "upcoming"),
                ),
                generation_allowed=True,
                reason=f"categories:{','.join(sorted(categories))}",
            ),
        )

    if result.get("similarity") == 0:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="failed:unclassified",
                observation=(
                    "Scenario failed, but no narrow repeated SAGE helper class is "
                    "eligible yet."
                ),
                allowed_families=(),
                validation_examples=(),
                generation_allowed=False,
                reason="no_repeated_supported_pattern",
            ),
        )
    return ()
