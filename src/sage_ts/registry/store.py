"""Filesystem-backed generated-tool registry."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from sage_ts.registry.manifest import RegistryEntry


class RegistryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "registry_manifest.json"

    def load_entries(self) -> dict[str, RegistryEntry]:
        if not self.manifest_path.exists():
            return {}
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {
            name: RegistryEntry.from_json(entry)
            for name, entry in payload.get("tools", {}).items()
        }

    def save_entries(self, entries: dict[str, RegistryEntry]) -> None:
        payload = {"tools": {name: entry.to_json() for name, entry in entries.items()}}
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.manifest_path)

    def put(self, entry: RegistryEntry) -> None:
        entries = self.load_entries()
        name = entry.tool.spec.tool_name
        if name in entries:
            prior = entries[name]
            entry = replace(entry, version=prior.version + 1)
        entries[name] = entry
        self.save_entries(entries)

    def get(self, tool_name: str) -> RegistryEntry | None:
        return self.load_entries().get(tool_name)

    def record_reuse(self, tool_name: str, success_flip: bool = False) -> None:
        entries = self.load_entries()
        entry = entries[tool_name]
        entries[tool_name] = replace(
            entry,
            reuse_count=entry.reuse_count + 1,
            success_flips=entry.success_flips + int(success_flip),
        )
        self.save_entries(entries)

    def retire(self, tool_name: str) -> None:
        entries = self.load_entries()
        entry = entries.get(tool_name)
        if entry is None or entry.retired:
            return
        entries[tool_name] = replace(entry, retired=True)
        self.save_entries(entries)
