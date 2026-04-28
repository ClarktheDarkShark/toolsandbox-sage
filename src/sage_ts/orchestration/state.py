"""Serializable SAGE orchestration event types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ToolBirthEvent:
    scenario: str
    tool_name: str
    family: str
    accepted: bool
    errors: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


@dataclass(frozen=True)
class ReuseEvent:
    scenario: str
    tool_name: str
    improved: bool
    baseline_success: bool
    sage_success: bool

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
