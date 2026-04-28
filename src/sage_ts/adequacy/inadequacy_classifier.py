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
        # Validation constants: day 10 boundary (all values are exact float arithmetic)
        _ts = float(10 * 86400)  # 864000.0
        _yesterday_start = float(9 * 86400)  # 777600.0
        _today_ts = float(10 * 86400 + 3600)  # 867600.0
        _today_start = float(10 * 86400)  # 864000.0
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="derived_value:recency_timestamp_bounds",
                observation=(
                    "ToolSandbox scenarios repeatedly require converting user-facing "
                    "recency words (yesterday, today, upcoming, latest, oldest) into "
                    "Unix timestamp lower/upper bounds to pass to search tools "
                    "(search_reminder, search_messages). The base toolset provides "
                    "get_current_timestamp, timestamp_to_datetime_info, and "
                    "datetime_info_to_timestamp as building blocks but not a single "
                    "recency-to-bounds helper. Agents must make 3+ extra calls and "
                    "are error-prone on day boundary arithmetic."
                ),
                allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
                validation_examples=(
                    ToolExample(
                        {"recency_label": "yesterday", "current_timestamp": _ts},
                        {"lower_bound": _yesterday_start, "upper_bound": _ts},
                    ),
                    ToolExample(
                        {"recency_label": "today", "current_timestamp": _today_ts},
                        {"lower_bound": _today_start, "upper_bound": _today_ts},
                    ),
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
