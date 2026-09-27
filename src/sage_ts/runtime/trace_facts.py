"""Immutable access to the visible ToolSandbox execution trace."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, cast

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


@dataclass(frozen=True, slots=True)
class OpenAITraceFacts:
    """Immutable structural view over one OpenAI-format actor transcript."""

    messages: tuple[Any, ...]

    @classmethod
    def from_messages(cls, messages: object) -> OpenAITraceFacts:
        return cls(tuple(cast(Iterable[Any], messages)))

    def user_texts(self) -> list[str]:
        return [
            str(message.get("content", "") or "")
            for message in self.messages
            if message.get("role") == "user"
        ]

    def first_user_text(self) -> str:
        for message in self.messages:
            if message.get("role") == "user":
                return str(message.get("content", "") or "")
        return ""

    def latest_user_text(self) -> str:
        for message in reversed(self.messages):
            if message.get("role") == "user":
                return str(message.get("content", "") or "")
        return ""

    def latest_user_index(self) -> int:
        return self.last_index(lambda message: message.get("role") == "user")

    def last_index(self, predicate: Callable[[Any], bool]) -> int:
        latest = -1
        for index, message in enumerate(self.messages):
            if predicate(message):
                latest = index
        return latest

    def tool_calls(
        self,
        *,
        after_index: int = -1,
        role: str | None = None,
        list_only: bool = True,
        dict_only: bool = False,
    ) -> Iterator[tuple[int, Mapping[str, Any]]]:
        """Yield raw tool calls while preserving each caller's container semantics."""

        for index, message in enumerate(self.messages):
            if index <= after_index:
                continue
            if role is not None and message.get("role") != role:
                continue
            tool_calls = message.get("tool_calls")
            if list_only:
                if not isinstance(tool_calls, list):
                    continue
            else:
                tool_calls = tool_calls or []
            for tool_call in tool_calls:
                if isinstance(tool_call, dict if dict_only else Mapping):
                    yield index, tool_call
