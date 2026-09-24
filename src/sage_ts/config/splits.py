"""Deterministic ToolSandbox split manifests for SAGE experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tool_sandbox.common.tool_discovery import ToolBackend
from tool_sandbox.scenarios import named_scenarios

DEFAULT_TOOL_BACKEND = ToolBackend("DEFAULT")


@dataclass(frozen=True)
class ScenarioRecord:
    name: str
    categories: tuple[str, ...]
    allowed_tools: tuple[str, ...]


def scenario_records() -> list[ScenarioRecord]:
    scenarios = named_scenarios(preferred_tool_backend=DEFAULT_TOOL_BACKEND)
    records: list[ScenarioRecord] = []
    for name, scenario in scenarios.items():
        allowed_tools = scenario.starting_context.tool_allow_list or []
        records.append(
            ScenarioRecord(
                name=name,
                categories=tuple(str(category) for category in scenario.categories),
                allowed_tools=tuple(str(tool) for tool in allowed_tools),
            )
        )
    return sorted(records, key=lambda record: record.name)


def load_split_names(manifest_path: Path, split_name: str) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        records = manifest["splits"][split_name]
    except KeyError as exc:
        available = sorted(manifest.get("splits", {}).keys())
        raise KeyError(f"Unknown split {split_name!r}; available: {available}") from exc
    return [str(record["name"]) for record in records]
