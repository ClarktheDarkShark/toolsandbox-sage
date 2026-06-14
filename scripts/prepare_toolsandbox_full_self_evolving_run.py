#!/usr/bin/env python3
"""Preflight and print the full ToolSandbox self-evolving SAGE run command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MANIFEST = (
    ROOT / "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
)
DEFAULT_REGISTRY = (
    ROOT / "artifacts/self_evolving_sage/full_toolsandbox_current/registry"
)
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/self_evolving_sage/full_toolsandbox_current"
DEFAULT_ARTIFACT_ROOT = (
    ROOT / "artifacts/self_evolving_sage/full_toolsandbox_current_artifacts"
)
DEFAULT_CONTROL_CACHE = ROOT / "artifacts/baselines/control_task_baselines"
DEFAULT_RAPID_CACHE = ROOT / ".secrets/rapid_api_cache.json"
UPSTREAM_POLICY = "upstream"
MIN_COMPATIBLE_CONTROL_RECORDS = 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--registry-dir", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--control-cache-root", type=Path, default=DEFAULT_CONTROL_CACHE
    )
    parser.add_argument("--rapid-cache-path", type=Path, default=DEFAULT_RAPID_CACHE)
    parser.add_argument("--agent", default="gpt-4o-mini")
    parser.add_argument("--user", default="gpt-4o-mini")
    parser.add_argument("--generation-model", default="gpt-4o-mini")
    parser.add_argument("--dashboard-port", type=int, default=62624)
    parser.add_argument(
        "--mode",
        default="online_build_full",
        help="Generation-enabled full-dataset mode; maps to manifest split full_benchmark.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the command after preflight. Default only prints the command.",
    )
    parser.add_argument(
        "--strict-control-cache",
        action="store_true",
        help="Require every control task to be served from the baseline cache.",
    )
    parser.add_argument(
        "--strict-model-user-cache",
        action="store_true",
        help=(
            "Require cached controls to match agent and user model. The default "
            "matches the high-lift Praxis runs and enables task-level control "
            "cache reuse by scenario/task name plus base tool policy."
        ),
    )
    parser.add_argument(
        "--control-cache-min-compatible-runs",
        type=int,
        default=MIN_COMPATIBLE_CONTROL_RECORDS,
        help=(
            "Minimum compatible cached control records required per task. The "
            "default preserves the formal three-record policy; recovery runs can "
            "set this to 1 when every task has at least one prior control."
        ),
    )
    parser.add_argument(
        "--allow-contaminated-preflight",
        action="store_true",
        help=(
            "Pass through the explicit external-service cohort warning override. "
            "Use only with a declared read-only external-service fixture cache."
        ),
    )
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    registry_dir = args.registry_dir.resolve()
    output_root = args.output_root.resolve()
    artifact_root = args.artifact_root.resolve()
    control_cache_root = args.control_cache_root.resolve()
    rapid_cache_path = args.rapid_cache_path.resolve()

    payload = _read_json(manifest)
    split = "full_benchmark" if args.mode == "online_build_full" else args.mode
    scenarios = payload.get("splits", {}).get(split)
    if not isinstance(scenarios, list) or not scenarios:
        raise SystemExit(
            f"Manifest {manifest} does not contain non-empty split {split!r}."
        )

    cache_coverage = _control_cache_coverage(
        control_cache_root=control_cache_root,
        scenario_names=tuple(str(row["name"]) for row in scenarios),
        agent=args.agent,
        user=args.user,
        base_tool_policy=UPSTREAM_POLICY,
        strict_model_user=args.strict_model_user_cache,
        min_compatible_records=max(1, args.control_cache_min_compatible_runs),
    )

    env_report = {
        "manifest": str(manifest),
        "manifest_sha256": _sha256(manifest),
        "mode": args.mode,
        "manifest_split": split,
        "scenario_count": len(scenarios),
        "registry_dir": str(registry_dir),
        "registry_starts_empty": not (registry_dir / "registry_manifest.json").exists(),
        "control_cache_root": str(control_cache_root),
        "control_cache_exists": control_cache_root.exists(),
        "control_cache_cached_count": cache_coverage["cached_count"],
        "control_cache_fresh_count": cache_coverage["fresh_count"],
        "control_cache_miss_reason_counts": cache_coverage["miss_reason_counts"],
        "control_cache_min_compatible_records": max(
            1, args.control_cache_min_compatible_runs
        ),
        "rapid_cache_path": str(rapid_cache_path),
        "rapid_cache_exists": rapid_cache_path.exists(),
        "rapid_cache_sha256": _sha256(rapid_cache_path)
        if rapid_cache_path.exists()
        else None,
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "agent": args.agent,
        "user": args.user,
        "generation_model": args.generation_model,
        "sage_policy": "self-evolving-praxis",
        "generation": "on",
        "candidate_task_cache": "off",
        "openai_response_cache": "disabled",
        "routing_evidence_mode": "disabled",
        "control_cache_mode": "strict"
        if args.strict_control_cache
        else "use-if-eligible",
        "experimental_task_only_control_cache": not args.strict_model_user_cache,
        "allow_contaminated_preflight": args.allow_contaminated_preflight,
        "created_at": int(time.time()),
    }

    registry_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    report_path = artifact_root / "full_toolsandbox_self_evolving_preflight.json"
    report_path.write_text(json.dumps(env_report, indent=2) + "\n", encoding="utf-8")

    if args.strict_control_cache and cache_coverage["fresh_count"]:
        raise SystemExit(
            "Strict control cache requested, but "
            f"{cache_coverage['fresh_count']} of {len(scenarios)} scenarios are not eligible."
        )

    command = [
        sys.executable,
        "scripts/run_sage_protocol.py",
        "--mode",
        args.mode,
        "--manifest",
        str(manifest),
        "--registry-dir",
        str(registry_dir),
        "--sage-policy",
        "self-evolving-praxis",
        "--agent",
        args.agent,
        "--user",
        args.user,
        "--generation-model",
        args.generation_model,
        "--generation",
        "on",
        "--disable-openai-response-cache",
        "--cache-mode",
        "off",
        "--control-cache",
        "strict" if args.strict_control_cache else "use-if-eligible",
        "--control-cache-root",
        str(control_cache_root),
        "--routing-evidence-mode",
        "disabled",
        "--freeze-toolsandbox-clock",
        "--dashboard-port",
        str(args.dashboard_port),
        "--output-root",
        str(output_root),
        "--artifact-root",
        str(artifact_root),
    ]
    if args.allow_contaminated_preflight:
        command.append("--allow-contaminated-preflight")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src:.")
    env["SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS"] = str(
        max(1, args.control_cache_min_compatible_runs)
    )
    if not args.strict_model_user_cache:
        env["SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY"] = "1"
    if rapid_cache_path.exists():
        env["TOOLSANDBOX_RAPID_CACHE_MODE"] = "read_only"
        env["TOOLSANDBOX_RAPID_CACHE_PATH"] = str(rapid_cache_path)

    print("Full ToolSandbox self-evolving SAGE preflight")
    print(json.dumps(env_report, indent=2))
    print("\nCommand:")
    print(
        _format_env_prefix(env, rapid_cache_path.exists())
        + " "
        + " ".join(shlex.quote(part) for part in command)
    )
    print(f"\nPreflight report: {report_path}")

    if args.execute:
        raise SystemExit(subprocess.call(command, cwd=ROOT, env=env))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SystemExit(f"Expected object JSON at {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _control_cache_coverage(
    *,
    control_cache_root: Path,
    scenario_names: tuple[str, ...],
    agent: str,
    user: str,
    base_tool_policy: str,
    strict_model_user: bool,
    min_compatible_records: int,
) -> dict[str, Any]:
    """Estimate task-level baseline-cache coverage without importing ToolSandbox."""
    if not control_cache_root.exists():
        return {
            "cached_count": 0,
            "fresh_count": len(scenario_names),
            "miss_reason_counts": {"control_cache_root_missing": len(scenario_names)},
        }
    needed = set(scenario_names)
    counts = {name: 0 for name in scenario_names}
    compact_records_path = control_cache_root / "compact_records.jsonl"
    if compact_records_path.exists():
        for line in compact_records_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except (OSError, json.JSONDecodeError):
                continue
            scenario_key = str(record.get("scenario_key", ""))
            if scenario_key not in needed:
                continue
            if not record.get("valid_for_cache") or not record.get("complete_run"):
                continue
            if str(record.get("base_tool_policy")) != base_tool_policy:
                continue
            if strict_model_user:
                if str(record.get("agent_model")) != agent:
                    continue
                if str(record.get("user_model")) != user:
                    continue
            counts[scenario_key] += 1
        cached = sum(1 for count in counts.values() if count >= min_compatible_records)
        fresh = len(scenario_names) - cached
        miss_reason = (
            f"fewer_than_{min_compatible_records}_model_user_matched_controls"
            if strict_model_user
            else f"fewer_than_{min_compatible_records}_task_level_controls"
        )
        return {
            "cached_count": cached,
            "fresh_count": fresh,
            "miss_reason_counts": {miss_reason: fresh} if fresh else {},
        }
    index_path = control_cache_root / "index.jsonl"
    if not index_path.exists():
        return {
            "cached_count": 0,
            "fresh_count": len(scenario_names),
            "miss_reason_counts": {"control_cache_index_missing": len(scenario_names)},
        }
    for line in index_path.read_text(encoding="utf-8").splitlines():
        try:
            index_row = json.loads(line)
        except (OSError, json.JSONDecodeError):
            continue
        scenario_key = str(index_row.get("scenario_key", ""))
        if scenario_key not in needed:
            continue
        if not index_row.get("valid_for_cache"):
            continue
        if strict_model_user:
            record_path = Path(str(index_row.get("record_path", "")))
            if not record_path.is_absolute():
                record_path = ROOT / record_path
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not record.get("complete_run"):
                continue
            if str(record.get("agent_model")) != agent:
                continue
            if str(record.get("user_model")) != user:
                continue
            if str(record.get("base_tool_policy")) != base_tool_policy:
                continue
        counts[scenario_key] += 1

    cached = sum(1 for count in counts.values() if count >= min_compatible_records)
    fresh = len(scenario_names) - cached
    miss_reason = (
        f"fewer_than_{min_compatible_records}_model_user_matched_controls"
        if strict_model_user
        else f"fewer_than_{min_compatible_records}_task_level_controls"
    )
    miss_reason_counts = {miss_reason: fresh} if fresh else {}
    return {
        "cached_count": cached,
        "fresh_count": fresh,
        "miss_reason_counts": miss_reason_counts,
    }


def _format_env_prefix(env: dict[str, str], include_rapid_cache: bool) -> str:
    parts = ["PYTHONPATH=src:."]
    if env.get("SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY"):
        parts.append("SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1")
    if env.get("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS"):
        parts.append(
            "SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS="
            + shlex.quote(env["SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS"])
        )
    if include_rapid_cache:
        parts.extend(
            [
                "TOOLSANDBOX_RAPID_CACHE_MODE=read_only",
                "TOOLSANDBOX_RAPID_CACHE_PATH="
                + shlex.quote(env["TOOLSANDBOX_RAPID_CACHE_PATH"]),
            ]
        )
    return " ".join(parts)


if __name__ == "__main__":
    main()
