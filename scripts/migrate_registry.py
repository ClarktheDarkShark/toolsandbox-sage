# mypy: ignore-errors
"""Migrate registry manifests: backfill schema_version and code_hash_verified fields.

Usage:
    python scripts/migrate_registry.py [registry_manifest.json ...]
    python scripts/migrate_registry.py --check-only [registry_manifest.json ...]
    python scripts/migrate_registry.py --registry registry_manifest.json [--check-only]

If no paths are provided, finds all registry_manifest.json files under the
project root (excluding .git and __pycache__).

--check-only: inspect manifests without writing anything; exits 1 if any active
(non-retired) entry fails has_current_validation_proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate  # noqa: E402
from sage_ts.registry.manifest import (  # noqa: E402
    RegistryEntry,
    has_current_validation_proof,
)

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


def check_validation_proof(path: Path) -> list[dict[str, Any]]:
    """Return active (non-retired) entries that fail has_current_validation_proof."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    tools = data.get("tools", {})
    failing = []
    for tool_name, entry in tools.items():
        registry_entry = RegistryEntry.from_json(entry)
        if registry_entry.retired:
            continue
        if not has_current_validation_proof(registry_entry):
            reasons = _validation_proof_reasons(registry_entry)
            failing.append(
                {
                    "tool_name": tool_name,
                    "path": str(path),
                    "schema_version": registry_entry.schema_version,
                    "passes_validation_proof": False,
                    "reasons": reasons,
                }
            )
    return failing


def _validation_proof_reasons(entry: RegistryEntry) -> list[str]:
    reasons: list[str] = []
    gate = evaluate_candidate_gate(entry.tool.spec)
    if not entry.validation.accepted:
        reasons.append("validation.accepted=False")
    if entry.validation.held_out_check_count <= 0:
        reasons.append("held_out_check_count=0")
    requires_negative = entry.tool.spec.family.value in {
        "state_precondition_helper",
        "search_filter_ranking_helper",
        "composite_workflow_helper",
    }
    if requires_negative and entry.validation.negative_applicability_count <= 0:
        reasons.append("negative_applicability_count=0")
    if not entry.validation.runtime_smoke_passed:
        reasons.append("runtime_smoke_passed=False")
    if entry.schema_version != REGISTRY_SCHEMA_VERSION:
        reasons.append(
            f"schema_version={entry.schema_version} != {REGISTRY_SCHEMA_VERSION}"
        )
    if entry.tool.spec.schema_version != TOOL_SPEC_SCHEMA_VERSION:
        reasons.append(
            "tool.spec.schema_version="
            f"{entry.tool.spec.schema_version} != {TOOL_SPEC_SCHEMA_VERSION}"
        )
    if not entry.code_hash_verified:
        reasons.append("code_hash_unverified")
    if not gate.allowed:
        reasons.append(f"candidate_gate:{gate.reason}")
    return reasons


def check_only_manifest(
    path: Path, root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Inspect a manifest without writing. Returns (passing, failing) rows for active entries."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    tools = data.get("tools", {})
    passing: list[dict[str, Any]] = []
    failing: list[dict[str, Any]] = []
    for tool_name, entry in tools.items():
        registry_entry = RegistryEntry.from_json(entry)
        retired = registry_entry.retired
        schema_version = registry_entry.schema_version
        reasons = [] if retired else _validation_proof_reasons(registry_entry)

        row = {
            "tool_name": tool_name,
            "path": str(path.relative_to(root)),
            "schema_version": schema_version,
            "retired": retired,
            "passes_validation_proof": not retired and not reasons,
            "reasons": reasons,
        }
        if retired or not reasons:
            passing.append(row)
        else:
            failing.append(row)
    return passing, failing


def check_quarantine(path: Path) -> list[dict[str, Any]]:
    """Return entries that still fail has_current_validation_proof after migration."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    tools = data.get("tools", {})
    quarantined = []
    for tool_name, entry in tools.items():
        registry_entry = RegistryEntry.from_json(entry)
        reasons = _validation_proof_reasons(registry_entry)
        if registry_entry.retired:
            reasons.append("retired=True")
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


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_check_only(paths: list[Path], root: Path) -> int:
    """Inspect all manifests without writing. Prints per-entry summary. Returns exit code."""
    all_passing: list[dict[str, Any]] = []
    all_failing: list[dict[str, Any]] = []
    had_error = False

    for path in paths:
        try:
            passing, failing = check_only_manifest(path, root)
            all_passing.extend(passing)
            all_failing.extend(failing)
            rel = _display_path(path, root)
            print(f"\nRegistry: {rel}  ({len(passing) + len(failing)} entries)")
            for row in passing:
                tag = "RETIRED " if row["retired"] else "PASS    "
                print(
                    f"  {tag} {row['tool_name']}  schema_version={row['schema_version']}"
                )
            for row in failing:
                print(
                    f"  FAIL     {row['tool_name']}  schema_version={row['schema_version']}"
                    f"  reasons={row['reasons']}"
                )
        except Exception as exc:
            had_error = True
            print(f"  ERROR    {path}: {exc}", file=sys.stderr)

    active_failing = [r for r in all_failing if not r.get("retired", False)]
    active_passing = [r for r in all_passing if not r.get("retired", False)]
    print(
        f"\nCheck-only summary: {len(paths)} registries scanned, "
        f"{len(active_passing)} active entries pass, "
        f"{len(active_failing)} active entries FAIL has_current_validation_proof."
    )
    if active_failing:
        print("FAIL: one or more active entries do not have current validation proof.")
        return 1
    if had_error:
        print("FAIL: one or more registries could not be inspected.")
        return 1
    print("OK: all active entries pass has_current_validation_proof.")
    return 0


def _normalize_paths(values: list[str], *, root: Path) -> list[Path]:
    return [
        (Path(value) if Path(value).is_absolute() else (root / value)).resolve()
        for value in values
    ]


def _extract_registry_flags(argv: list[str], *, root: Path) -> tuple[bool, list[str]]:
    args = list(argv)
    check_only = "--check-only" in args
    if check_only:
        args.remove("--check-only")

    paths: list[str] = []
    while "--registry" in args:
        index = args.index("--registry")
        if index == len(args) - 1:
            raise ValueError("--registry requires a registry path argument")
        paths.append(args[index + 1])
        del args[index : index + 2]

    # Keep backwards-compatible positional registry arguments
    paths.extend(args)
    return check_only, _normalize_paths(paths, root=root)


def main(argv: list[str]) -> None:
    try:
        check_only, paths = _extract_registry_flags(argv, root=_ROOT)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

    root = _ROOT

    if not paths:
        paths = [path.resolve() for path in find_all_registries(root)]

    if check_only:
        print(f"Found {len(paths)} registry manifests to check (read-only).")
        exit_code = run_check_only(paths, root)
        sys.exit(exit_code)

    # --- Normal migration mode ---
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
                    f"  MIGRATED {_display_path(path, root)}: {summary['migrated_count']}/{summary['total_entries']} entries updated"
                )
                for tool, changes in summary["changes"].items():
                    for change in changes:
                        print(f"    {tool}: {change}")
            else:
                print(
                    f"  OK       {_display_path(path, root)}: {summary['total_entries']} entries already current"
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
