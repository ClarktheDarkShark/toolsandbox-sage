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

    def record_success_flip(
        self,
        tool_name: str,
        observation_id: str,
        *,
        tool_version: int | None = None,
    ) -> bool:
        """Record one idempotent prospective failure-to-success transition.

        Reuse is recorded when the generated function executes, before paired
        post-task feedback exists.  Keeping success-flip accounting separate
        prevents a later lifecycle assessment from incrementing reuse twice and
        makes resumable runs safe when the same completed task is hydrated.
        """

        observation_id = str(observation_id or "").strip()
        if not observation_id:
            raise ValueError("success-flip observation_id must be nonempty")
        entries = self.load_entries()
        entry = entries.get(tool_name)
        if entry is None:
            return False
        version = entry.version if tool_version is None else int(tool_version)
        if version != entry.version:
            # Registry manifests keep only the current implementation. Never
            # charge a late observation to a different version.
            return False

        event_path = self.root / "success_flip_events.jsonl"
        event_key = f"{tool_name}\0{version}\0{observation_id}"
        observed_keys: set[str] = set()
        if event_path.exists():
            for line in event_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_version = event.get("tool_version")
                if not isinstance(event_version, int) or isinstance(
                    event_version, bool
                ):
                    # Pre-versioned events are retained as historical records,
                    # but cannot be assigned to a replacement implementation.
                    continue
                prior_key = (
                    f"{str(event.get('tool_name') or '')}\0{event_version}\0"
                    f"{str(event.get('observation_id') or '')}"
                )
                observed_keys.add(prior_key)

        added = event_key not in observed_keys
        if added:
            with event_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "event": "generated_tool_success_flip",
                            "tool_name": tool_name,
                            "tool_version": version,
                            "observation_id": observation_id,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            observed_keys.add(event_key)

        durable_count = sum(
            1 for key in observed_keys if key.startswith(f"{tool_name}\0{version}\0")
        )
        if entry.success_flips != durable_count:
            entries[tool_name] = replace(entry, success_flips=durable_count)
            self.save_entries(entries)
        return added

    def retire(self, tool_name: str) -> None:
        entries = self.load_entries()
        entry = entries.get(tool_name)
        if entry is None or entry.retired:
            return
        entries[tool_name] = replace(entry, retired=True)
        self.save_entries(entries)
