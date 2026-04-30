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
        if (
            _similarity(result) < 1.0
            and "latest" in scenario_name
            and scenario_name.startswith(
                (
                    "modify_reminder_with_recency_latest",
                    "remove_reminder_with_recency_latest",
                    "search_message_with_recency_latest",
                )
            )
        ):
            observations.append(
                CapabilityObservation(
                    scenario_name=scenario_name,
                    canonical_key="search_filter:select_latest_record_by_timestamp",
                    observation=(
                        "Repeated latest-result scenarios require choosing the "
                        "single record with the greatest timestamp from a visible "
                        "list returned by search tools. Agents can compute valid "
                        "search bounds but still select or report the wrong "
                        "candidate. Generate a small deterministic "
                        "search/filter/ranking helper named "
                        "select_latest_record_by_timestamp. Inputs: "
                        "records_payload as a dict containing a 'records' list of "
                        "record dictionaries, and timestamp_key as the timestamp "
                        "field to compare. Ignore records missing a numeric "
                        "timestamp. Return the full record with the largest "
                        "timestamp, or an empty dict if no valid timestamp exists."
                    ),
                    allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
                    validation_examples=(
                        ToolExample(
                            {
                                "records_payload": {
                                    "records": [
                                        {
                                            "content": "older",
                                            "creation_timestamp": 10.0,
                                        },
                                        {
                                            "content": "newer",
                                            "creation_timestamp": 20.0,
                                        },
                                    ]
                                },
                                "timestamp_key": "creation_timestamp",
                            },
                            {"content": "newer", "creation_timestamp": 20.0},
                        ),
                        ToolExample(
                            {
                                "records_payload": {
                                    "records": [
                                        {"content": "missing"},
                                        {
                                            "content": "old",
                                            "reminder_timestamp": 5.0,
                                        },
                                        {
                                            "content": "new",
                                            "reminder_timestamp": 15.0,
                                        },
                                    ]
                                },
                                "timestamp_key": "reminder_timestamp",
                            },
                            {"content": "new", "reminder_timestamp": 15.0},
                        ),
                        ToolExample(
                            {
                                "records_payload": {"records": [{"content": "none"}]},
                                "timestamp_key": "creation_timestamp",
                            },
                            {},
                        ),
                    ),
                    generation_allowed=True,
                    reason="repeated_latest_record_selection_failure",
                )
            )
        return tuple(observations)

    if (
        ScenarioCategories.STATE_DEPENDENCY in scenario.categories
        and scenario_name.startswith(("turn_on_", "enable_", "set_"))
        and any(
            token in scenario_name
            for token in ("wifi", "cellular", "location", "low_battery")
        )
        and _similarity(result) < 1.0
    ):
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="state_precondition:service_next_action",
                observation=(
                    "Direct state-dependency scenarios repeatedly require deciding "
                    "one concrete service-precondition action before finalizing. "
                    "Generate a small deterministic helper named "
                    "next_service_enablement_action. It must return a dictionary "
                    "with exactly a readiness predicate and one concrete next_action, "
                    "not an advisory ordered plan. Inputs: target_service, "
                    "wifi_enabled, cellular_enabled, location_service_enabled, "
                    "low_battery_mode. If the target is already enabled, return "
                    "ready=True and next_action='none'. If the target is disabled "
                    "and low_battery_mode is true, return next_action="
                    "'set_low_battery_mode_status_false'. Otherwise return the "
                    "single setter action for the target service."
                ),
                allowed_families=(str(ToolFamily.STATE_PRECONDITION_HELPER),),
                validation_examples=(
                    ToolExample(
                        {
                            "target_service": "wifi",
                            "wifi_enabled": False,
                            "cellular_enabled": True,
                            "location_service_enabled": True,
                            "low_battery_mode": True,
                        },
                        {
                            "ready": False,
                            "next_action": "set_low_battery_mode_status_false",
                            "target_service": "wifi",
                        },
                    ),
                    ToolExample(
                        {
                            "target_service": "cellular",
                            "wifi_enabled": True,
                            "cellular_enabled": False,
                            "location_service_enabled": True,
                            "low_battery_mode": False,
                        },
                        {
                            "ready": False,
                            "next_action": "set_cellular_service_status_true",
                            "target_service": "cellular",
                        },
                    ),
                    ToolExample(
                        {
                            "target_service": "location",
                            "wifi_enabled": True,
                            "cellular_enabled": True,
                            "location_service_enabled": True,
                            "low_battery_mode": False,
                        },
                        {
                            "ready": True,
                            "next_action": "none",
                            "target_service": "location",
                        },
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
