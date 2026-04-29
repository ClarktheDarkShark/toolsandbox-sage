"""Artifact-backed capability observations for online tool birth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.generation.tool_spec import ToolFamily
from sage_ts.validation.sandbox_validator import ToolExample
from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario


def _similarity(result: dict[str, Any]) -> float:
    value = result.get("similarity", 0.0)
    try:
        return float(value) if isinstance(value, (int, float, str)) else 0.0
    except ValueError:
        return 0.0


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
        observations = [
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
            )
        ]
        if (
            scenario_name.startswith("modify_reminder_with_recency_latest")
            and _similarity(result) < 1.0
        ):
            observations.append(
                CapabilityObservation(
                    scenario_name=scenario_name,
                    canonical_key="canonicalizer:relative_day_time_timestamp",
                    observation=(
                        "Repeated modify_reminder recency scenarios require turning "
                        "a user-facing relative date/time such as 'tomorrow 5PM' "
                        "into the exact local Unix timestamp passed to "
                        "modify_reminder. In the reduced base toolset the date/time "
                        "decomposition helpers are absent, so agents find the right "
                        "reminder but often write the wrong timestamp. Generate a "
                        "small deterministic canonicalizer named "
                        "relative_day_time_to_timestamp that accepts current_timestamp, "
                        "day_offset, hour, minute, and local_utc_offset_hours. Use "
                        "local_utc_offset_hours=-4 for the current ToolSandbox local "
                        "environment unless another offset is explicitly known."
                    ),
                    allowed_families=(str(ToolFamily.CANONICALIZER),),
                    validation_examples=(
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 1,
                                "hour": 17,
                                "minute": 0,
                                "local_utc_offset_hours": -4,
                            },
                            1777496400.0,
                        ),
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 2,
                                "hour": 8,
                                "minute": 30,
                                "local_utc_offset_hours": -4,
                            },
                            1777552200.0,
                        ),
                    ),
                    generation_allowed=True,
                    reason="repeated_modify_reminder_relative_datetime_failure",
                )
            )
        return tuple(observations)

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
