"""Reproduce the upstream ToolSandbox tool visibility for SAGE runs."""

from __future__ import annotations

import copy

from tool_sandbox.common.scenario import Scenario

UPSTREAM_POLICY = "upstream"


def apply_base_tool_policy(scenario: Scenario, policy: str) -> Scenario:
    """Return an isolated copy of the unmodified upstream scenario."""
    if policy != UPSTREAM_POLICY:
        raise ValueError(
            f"Unsupported base tool policy {policy!r}; only {UPSTREAM_POLICY!r} "
            "is part of the publication protocol"
        )
    return copy.deepcopy(scenario)
