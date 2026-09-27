"""Immutable access to the visible ToolSandbox execution trace."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from tool_sandbox.common.execution_context import DatabaseNamespace


@dataclass(frozen=True, slots=True)
class TraceFacts:
    """One uncached snapshot of visible sandbox trace rows."""

    _rows: tuple[Any, ...]

    @classmethod
    def from_current_context(
        cls,
        context_provider: Callable[[], Any],
    ) -> TraceFacts | None:
        """Capture current rows, returning ``None`` when context access fails."""
        try:
            sandbox = context_provider().get_database(
                namespace=DatabaseNamespace.SANDBOX,
                get_all_history_snapshots=True,
            )
        except Exception:
            return None
        return cls(_rows=tuple(sandbox.to_dicts()))

    def payloads(self, *, newest_first: bool) -> Iterator[Any]:
        """Yield decoded trace payloads without coercing their JSON type."""
        rows = reversed(self._rows) if newest_first else iter(self._rows)
        for row in rows:
            existing = row.get("tool_trace")
            if existing is None:
                continue
            traces = (
                existing.to_list() if hasattr(existing, "to_list") else list(existing)
            )
            ordered_traces = reversed(traces) if newest_first else traces
            for item in ordered_traces:
                try:
                    yield json.loads(str(item))
                except json.JSONDecodeError:
                    continue
