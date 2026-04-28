"""Tool visibility policies for fair reduced-base ToolSandbox comparisons."""

from __future__ import annotations

import copy
from collections.abc import Iterable

from tool_sandbox.common.scenario import Scenario

UPSTREAM_POLICY = "upstream"
RECENCY_REDUCED_POLICY = "recency_reduced"
KNOWN_POLICIES = (UPSTREAM_POLICY, RECENCY_REDUCED_POLICY)

RECENCY_REDUCED_REMOVALS = frozenset(
    {
        "datetime_info_to_timestamp",
        "seconds_to_hours_minutes_seconds",
        "shift_timestamp",
        "timestamp_diff",
        "timestamp_to_datetime_info",
    }
)


def _remove_tools(tool_allow_list: Iterable[str], removals: set[str]) -> list[str]:
    return [tool for tool in tool_allow_list if tool not in removals]


def apply_base_tool_policy(scenario: Scenario, policy: str) -> Scenario:
    """Return a scenario copy with a reproducible base-tool policy applied."""
    if policy not in KNOWN_POLICIES:
        raise ValueError(
            f"Unknown base tool policy {policy!r}; expected {KNOWN_POLICIES}"
        )
    scenario_copy = copy.deepcopy(scenario)
    if policy == UPSTREAM_POLICY:
        return scenario_copy

    tool_allow_list = scenario_copy.starting_context.tool_allow_list
    if tool_allow_list is None:
        return scenario_copy
    if policy == RECENCY_REDUCED_POLICY:
        scenario_copy.starting_context.tool_allow_list = _remove_tools(
            tool_allow_list,
            set(RECENCY_REDUCED_REMOVALS),
        )
    return scenario_copy
