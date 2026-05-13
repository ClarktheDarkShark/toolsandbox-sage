"""Deterministic ToolSandbox split manifests for SAGE experiments."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tool_sandbox.common.tool_discovery import ToolBackend
from tool_sandbox.scenarios import named_scenarios

DEFAULT_TOOL_BACKEND = ToolBackend("DEFAULT")

DEFAULT_SPLIT_SIZES = {
    "smoke_10": 10,
    "mechanism_40": 40,
    "online_build_100": 100,
    "online_build_250": 250,
    "online_build_500": 500,
    "transfer_100": 100,
    "promotion_250": 250,
}


@dataclass(frozen=True)
class ScenarioRecord:
    name: str
    categories: tuple[str, ...]
    allowed_tools: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "categories": list(self.categories),
            "allowed_tools": list(self.allowed_tools),
        }


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


def make_split_manifest(seed: int = 42) -> dict[str, Any]:
    records = scenario_records()
    shuffled = records[:]
    random.Random(seed).shuffle(shuffled)

    cursor = 0
    splits: dict[str, list[dict[str, Any]]] = {}
    for split_name, size in DEFAULT_SPLIT_SIZES.items():
        split_records = shuffled[cursor : cursor + size]
        splits[split_name] = [record.to_json() for record in split_records]
        cursor += size

    splits["full_benchmark"] = [record.to_json() for record in records]
    return {
        "seed": seed,
        "total_scenarios": len(records),
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "splits": splits,
    }


def write_split_manifest(output_path: Path, seed: int = 42) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = make_split_manifest(seed=seed)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_split_names(manifest_path: Path, split_name: str) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        records = manifest["splits"][split_name]
    except KeyError as exc:
        available = sorted(manifest.get("splits", {}).keys())
        raise KeyError(f"Unknown split {split_name!r}; available: {available}") from exc
    return [str(record["name"]) for record in records]
