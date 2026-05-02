"""Migrate registry manifests: backfill schema_version and code_hash_verified fields.

Usage:
    python scripts/migrate_registry.py [registry_manifest.json ...]

If no paths are provided, finds all registry_manifest.json files under the
project root (excluding .git and __pycache__).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REGISTRY_SCHEMA_VERSION = 2
TOOL_SPEC_SCHEMA_VERSION = 2


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def migrate_entry(
    entry: dict[str, Any], tool_name: str
) -> tuple[dict[str, Any], list[str]]:
    """Migrate a single registry entry dict in-place. Returns (entry, changes)."""
    changes: list[str] = []
    entry = dict(entry)

    # Fix top-level schema_version
    if entry.get("schema_version", 0) != REGISTRY_SCHEMA_VERSION:
        old = entry.get("schema_version", "MISSING")
        entry["schema_version"] = REGISTRY_SCHEMA_VERSION
        changes.append(f"schema_version: {old!r} -> {REGISTRY_SCHEMA_VERSION}")

    # Fix tool.spec.schema_version
    tool = entry.get("tool", {})
    if isinstance(tool, dict):
        tool = dict(tool)
        spec = tool.get("spec", {})
        if isinstance(spec, dict):
            spec = dict(spec)
            if spec.get("schema_version", 0) != TOOL_SPEC_SCHEMA_VERSION:
                old = spec.get("schema_version", "MISSING")
                spec["schema_version"] = TOOL_SPEC_SCHEMA_VERSION
                changes.append(
                    f"tool.spec.schema_version: {old!r} -> {TOOL_SPEC_SCHEMA_VERSION}"
                )
            tool["spec"] = spec
        entry["tool"] = tool

    # Fix code_hash: set stored_code_hash if code is non-empty and hash is missing
    code = tool.get("code", "") if isinstance(tool, dict) else ""
    stored_hash = entry.get("code_hash")
    if code and not stored_hash:
        computed = code_hash(code)
        entry["code_hash"] = computed
        changes.append(f"code_hash: MISSING -> {computed[:16]}...")

    return entry, changes


def migrate_manifest(path: Path) -> dict[str, Any]:
    """Migrate a registry manifest file atomically. Returns migration summary."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    tools = data.get("tools", {})

    migrated_entries: list[str] = []
    unchanged_entries: list[str] = []
    all_changes: dict[str, list[str]] = {}

    new_tools = {}
    for tool_name, entry in tools.items():
        new_entry, changes = migrate_entry(entry, tool_name)
        new_tools[tool_name] = new_entry
        if changes:
            migrated_entries.append(tool_name)
            all_changes[tool_name] = changes
        else:
            unchanged_entries.append(tool_name)

    data["tools"] = new_tools

    # Atomic write
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

    return {
        "path": str(path),
        "total_entries": len(tools),
        "migrated_count": len(migrated_entries),
        "unchanged_count": len(unchanged_entries),
        "migrated_entries": migrated_entries,
        "changes": all_changes,
    }


def check_quarantine(path: Path) -> list[dict[str, Any]]:
    """Return entries that still fail has_current_validation_proof after migration."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    tools = data.get("tools", {})
    quarantined = []
    for tool_name, entry in tools.items():
        reasons = []
        validation = entry.get("validation", {})
        if not validation.get("accepted", False):
            reasons.append("validation.accepted=False")
        if validation.get("held_out_check_count", 0) <= 0:
            reasons.append("held_out_check_count=0")
        if entry.get("schema_version", 0) != REGISTRY_SCHEMA_VERSION:
            reasons.append(
                f"schema_version={entry.get('schema_version', 'MISSING')} != {REGISTRY_SCHEMA_VERSION}"
            )
        tool = entry.get("tool", {})
        spec = tool.get("spec", {}) if isinstance(tool, dict) else {}
        if spec.get("schema_version", 0) != TOOL_SPEC_SCHEMA_VERSION:
            reasons.append(
                f"tool.spec.schema_version={spec.get('schema_version', 'MISSING')} != {TOOL_SPEC_SCHEMA_VERSION}"
            )
        code = tool.get("code", "") if isinstance(tool, dict) else ""
        stored_hash = entry.get("code_hash")
        if code and stored_hash and stored_hash != code_hash(code):
            reasons.append("code_hash_mismatch")
        if entry.get("retired", False):
            reasons.append("retired=True")
        if not validation.get("runtime_smoke_passed", False):
            reasons.append("runtime_smoke_passed=False")
        if reasons:
            quarantined.append(
                {"tool_name": tool_name, "path": str(path), "reasons": reasons}
            )
    return quarantined


def find_all_registries(root: Path) -> list[Path]:
    results = []
    for p in root.rglob("registry_manifest.json"):
        parts = p.parts
        if ".git" in parts or "__pycache__" in parts:
            continue
        results.append(p)
    return sorted(results)


def main(argv: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]

    if argv:
        paths = [Path(p) for p in argv]
    else:
        paths = find_all_registries(root)

    print(f"Found {len(paths)} registry manifests to migrate.")

    all_summaries = []
    all_quarantine = []
    total_migrated = 0
    total_entries = 0

    for path in paths:
        try:
            summary = migrate_manifest(path)
            all_summaries.append(summary)
            total_migrated += summary["migrated_count"]
            total_entries += summary["total_entries"]
            if summary["migrated_count"] > 0:
                print(
                    f"  MIGRATED {path.relative_to(root)}: {summary['migrated_count']}/{summary['total_entries']} entries updated"
                )
                for tool, changes in summary["changes"].items():
                    for change in changes:
                        print(f"    {tool}: {change}")
            else:
                print(
                    f"  OK       {path.relative_to(root)}: {summary['total_entries']} entries already current"
                )
        except Exception as exc:
            print(f"  ERROR    {path}: {exc}", file=sys.stderr)
            all_summaries.append({"path": str(path), "error": str(exc)})

    # Re-check quarantine after migration
    for path in paths:
        try:
            quarantined = check_quarantine(path)
            all_quarantine.extend(quarantined)
        except Exception as exc:
            print(f"  QUARANTINE CHECK ERROR {path}: {exc}", file=sys.stderr)

    print(
        f"\nSummary: {total_migrated} entries migrated across {len(paths)} manifests ({total_entries} total entries)."
    )
    if all_quarantine:
        print(
            f"WARNING: {len(all_quarantine)} entries still fail has_current_validation_proof after migration."
        )

    # Write reports
    summaries_dir = root / "artifacts" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    migration_report = {
        "date": "2026-05-01",
        "registries_scanned": len(paths),
        "total_entries": total_entries,
        "total_migrated": total_migrated,
        "summaries": all_summaries,
    }
    report_path = summaries_dir / "registry_migration_report.json"
    tmp = report_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(migration_report, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, report_path)
    print(f"Migration report written to: {report_path}")

    quarantine_report = {
        "date": "2026-05-01",
        "quarantined_count": len(all_quarantine),
        "entries": all_quarantine,
    }
    quarantine_path = summaries_dir / "registry_quarantine_report.json"
    tmp = quarantine_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(quarantine_report, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, quarantine_path)
    print(f"Quarantine report written to: {quarantine_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
