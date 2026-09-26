"""Immutable facts extracted from ToolSandbox task inputs."""

from __future__ import annotations

from dataclasses import dataclass

from tool_sandbox.common.execution_context import DatabaseNamespace, RoleType
from tool_sandbox.common.scenario import Scenario


@dataclass(frozen=True, slots=True)
class TaskFacts:
    """Raw user-visible request and tool inventory for one scenario."""

    user_request: str
    available_tools: tuple[str, ...]

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> TaskFacts:
        """Extract task facts while isolating unavailable context components."""

        request = ""
        try:
            sandbox_db = scenario.starting_context.get_database(
                DatabaseNamespace.SANDBOX,
                get_all_history_snapshots=True,
                drop_sandbox_message_index=False,
            )
            for row in sandbox_db.iter_rows(named=True):
                if (
                    row.get("sender") == RoleType.USER
                    and row.get("recipient") == RoleType.AGENT
                ):
                    content = str(row.get("content") or "").strip()
                    if content:
                        request = content
        except Exception:
            request = ""

        try:
            available = scenario.starting_context.get_available_tools(
                scrambling_allowed=False
            )
            tools = tuple(sorted(str(name) for name in available))
        except Exception:
            tools = ()

        return cls(user_request=request, available_tools=tools)
