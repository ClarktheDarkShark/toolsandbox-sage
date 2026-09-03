#!/usr/bin/env python3
"""Fail-fast preflight for frozen SAGE final or near-final validation runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

DIAGNOSTIC_FORCE_ENV_VARS = (
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)
REDACTED_ENV_TOKENS = ("API", "KEY", "TOKEN", "SECRET")
FINAL_MODES = {"validate_100", "validate_250", "promotion_250", "full_benchmark"}


@dataclass
class CheckResult:
    name: str
    status: str
    severity: str
    detail: str

    def to_json(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def git_output(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def run_affecting_sage_env(env: dict[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, value in sorted(env.items()):
        if not name.startswith("SAGE_"):
            continue
        values[name] = (
            "<redacted>"
            if any(token in name.upper() for token in REDACTED_ENV_TOKENS)
            else value
        )
    return values


def active_diagnostic_force_env(env: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name in DIAGNOSTIC_FORCE_ENV_VARS
        if (value := env.get(name, "").strip())
    }


def add(
    results: list[CheckResult],
    name: str,
    ok: bool,
    detail: str,
    *,
    severity: str = "critical",
) -> None:
    results.append(CheckResult(name, "pass" if ok else "fail", severity, detail))


def check_git(results: list[CheckResult], *, allow_dirty: bool) -> dict[str, Any]:
    try:
        commit = git_output(["rev-parse", "HEAD"])
        branch = git_output(["branch", "--show-current"])
        status = git_output(["status", "--porcelain"])
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        add(results, "git_state_known", False, f"git query failed: {exc}")
        return {"commit": None, "branch": None, "dirty_entries": None}
    add(results, "git_state_known", True, f"branch={branch} commit={commit}")
    is_clean = status == ""
    add(
        results,
        "git_worktree_clean",
        is_clean or allow_dirty,
        "clean" if is_clean else f"dirty entries: {status.splitlines()[:10]}",
    )
    return {"commit": commit, "branch": branch, "dirty_entries": status.splitlines()}


def check_registries(
    results: list[CheckResult],
    *,
    registry_dirs: list[Path],
    config: dict[str, Any],
    allow_unlisted: bool,
) -> list[dict[str, Any]]:
    protected = {
        str(Path(item["path"]).resolve()): item
        for item in config.get("protected_registries", [])
    }
    checked: list[dict[str, Any]] = []
    for registry_dir in registry_dirs:
        manifest = registry_dir / "registry_manifest.json"
        resolved = str(manifest.resolve())
        exists = manifest.exists()
        add(results, f"registry_manifest_exists:{registry_dir}", exists, str(manifest))
        if not exists:
            continue
        digest = sha256_file(manifest)
        listed = protected.get(resolved)
        if listed is None:
            add(
                results,
                f"registry_is_configured:{registry_dir}",
                allow_unlisted,
                "registry is not listed in final_run_preflight_config.json",
                severity="high",
            )
            expected = None
            label = "unlisted"
        else:
            expected = str(listed.get("sha256"))
            label = str(listed.get("label"))
            add(
                results,
                f"registry_sha_matches:{label}",
                digest == expected,
                f"actual={digest} expected={expected}",
            )
        checked.append(
            {
                "registry_dir": str(registry_dir),
                "manifest": str(manifest),
                "label": label,
                "sha256": digest,
                "expected_sha256": expected,
            }
        )
    add(
        results,
        "registry_selection_unambiguous",
        len(registry_dirs) == len(set(map(str, registry_dirs))),
        "registry dirs are unique",
    )
    return checked


def check_manifest(
    results: list[CheckResult], *, manifest: Path, mode: str
) -> dict[str, Any]:
    add(results, "manifest_exists", manifest.exists(), str(manifest))
    if not manifest.exists():
        return {}
    payload = read_json(manifest)
    missing = [field for field in ("manifest_type", "splits") if field not in payload]
    add(results, "manifest_required_fields", not missing, f"missing={missing}")
    splits = (
        payload.get("splits", {}) if isinstance(payload.get("splits"), dict) else {}
    )
    split = splits.get(mode)
    if split is None and len(splits) == 1:
        split = next(iter(splits.values()))
    add(
        results,
        "manifest_split_available",
        isinstance(split, list) and len(split) > 0,
        f"mode={mode} count={len(split) if isinstance(split, list) else 0}",
    )
    scenario_names = []
    if isinstance(split, list):
        for item in split:
            if isinstance(item, str):
                scenario_names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                scenario_names.append(str(item["name"]))
    return {
        "manifest_type": payload.get("manifest_type"),
        "scenario_count": len(scenario_names),
        "manifest_sha256": sha256_file(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("docs/sage_protocol/final_run_preflight_config.json"),
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--registry-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation", choices=("off", "on", "auto"), required=True)
    parser.add_argument(
        "--control-cache",
        choices=("use-if-eligible", "strict", "off", "collect", "refresh"),
        required=True,
    )
    parser.add_argument("--allow-low-quality-cohort", action="store_true")
    parser.add_argument("--diagnostic-mode", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--allow-unlisted-registry", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report path. Use /tmp for clean-tree preflight checks.",
    )
    args = parser.parse_args()

    results: list[CheckResult] = []
    config = read_json(args.config)
    git_state = check_git(results, allow_dirty=args.allow_dirty)
    registries = check_registries(
        results,
        registry_dirs=args.registry_dir,
        config=config,
        allow_unlisted=args.allow_unlisted_registry,
    )
    manifest = check_manifest(results, manifest=args.manifest, mode=args.mode)

    final_mode = args.mode in FINAL_MODES
    add(results, "final_mode_known", final_mode, f"mode={args.mode}")
    add(
        results,
        "generation_disabled_for_final_run",
        (not final_mode) or args.generation == "off",
        f"generation={args.generation}",
    )
    add(
        results,
        "control_cache_off",
        args.control_cache == "off",
        f"control_cache={args.control_cache}",
        severity="high",
    )
    add(
        results,
        "low_quality_override_disabled",
        not args.allow_low_quality_cohort,
        "--allow-low-quality-cohort must not be used for final runs",
    )
    force_env = active_diagnostic_force_env(dict(os.environ))
    add(
        results,
        "diagnostic_force_env_absent",
        not force_env or args.diagnostic_mode,
        f"active={sorted(force_env)} diagnostic_mode={args.diagnostic_mode}",
    )

    add(
        results,
        "output_root_parent_exists",
        args.output_root.parent.exists(),
        str(args.output_root.parent),
        severity="high",
    )
    heuristics_path = Path(
        str(
            config.get(
                "methodology_heuristics_path",
                "docs/sage_protocol/protocol_heuristics_v1.json",
            )
        )
    )
    add(
        results,
        "heuristics_config_exists",
        heuristics_path.exists(),
        str(heuristics_path),
        severity="high",
    )

    passed = all(result.status == "pass" for result in results)
    report = {
        "schema_version": "sage_final_run_preflight_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "git": git_state,
        "manifest": {"path": str(args.manifest), **manifest},
        "registries": registries,
        "mode": args.mode,
        "generation": args.generation,
        "control_cache": args.control_cache,
        "fresh_control_required": args.control_cache == "off",
        "diagnostic_mode": args.diagnostic_mode,
        "run_affecting_sage_env": run_affecting_sage_env(dict(os.environ)),
        "checks": [result.to_json() for result in results],
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
