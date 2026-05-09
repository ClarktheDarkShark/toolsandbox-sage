# mypy: ignore-errors
"""Ingest fresh control-arm outputs into the authoritative task cache.

This only reads completed non-SAGE control-arm result summaries. It skips
synthetic cached-control directories and does not inspect candidate/SAGE traces
or labels. The cache itself still enforces task-level compatibility before any
future reuse.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig
from sage_ts.evaluation.control_baseline_cache import ControlBaselineCache
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _fresh_control_result_dirs(output_root: Path) -> list[Path]:
    dirs: list[Path] = []
    for path in output_root.glob("**/*control_agent*/result_summary.json"):
        run_dir = path.parent
        if "_control_cached_" in run_dir.name:
            continue
        dirs.append(run_dir)
    return sorted(set(dirs), key=lambda item: str(item))


def _existing_keys(cache: ControlBaselineCache) -> set[tuple[str, str, str, str, str]]:
    keys: set[tuple[str, str, str, str, str]] = set()
    index = cache.index_path
    if not index.exists():
        return keys
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        record_path = Path(str(row.get("record_path", "")))
        record = _read_json(record_path, {})
        if not record:
            continue
        keys.add(
            (
                str(record.get("run_dir")),
                str(record.get("scenario_key")),
                str(record.get("agent_model")),
                str(record.get("user_model")),
                str(record.get("base_tool_policy")),
            )
        )
    return keys


def _manifest_for_run_dir(run_dir: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _read_json(run_dir.parent / "sage_ts_run_manifest.json", {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/gap_closure_lab"),
        help="Root containing prior protocol run outputs.",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("artifacts/baselines/control_task_baselines"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
            "control_cache_ingest_report.json"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--refresh-existing-run-rows",
        action="store_true",
        help=(
            "Re-add rows even when the same run_dir/scenario/model tuple already "
            "exists. Use after runner/scorer compatibility hashes change."
        ),
    )
    args = parser.parse_args()

    cache = ControlBaselineCache(args.cache_root)
    existing = _existing_keys(cache)
    scanned = 0
    skipped_cached = 0
    skipped_missing_manifest = 0
    skipped_duplicate_rows = 0
    skipped_empty = 0
    collected_records = 0
    collected_run_dirs: list[str] = []

    for run_dir in _fresh_control_result_dirs(args.output_root):
        scanned += 1
        if "_control_cached_" in run_dir.name:
            skipped_cached += 1
            continue
        manifest = _manifest_for_run_dir(run_dir)
        scenario_names = tuple(str(name) for name in manifest.get("scenario_names", []))
        if not scenario_names:
            skipped_missing_manifest += 1
            continue
        result = _read_json(run_dir / "result_summary.json", {})
        by_name = {
            str(row.get("name")): row
            for row in result.get("per_scenario_results", [])
            if isinstance(row, dict) and row.get("name")
        }
        scenario_names = tuple(name for name in scenario_names if name in by_name)
        if not scenario_names:
            skipped_empty += 1
            continue

        agent = str(manifest.get("agent") or "gpt-4o-mini")
        user = str(manifest.get("user") or "GPT_4_o_2024_05_13")
        base_tool_policy = str(manifest.get("base_tool_policy") or UPSTREAM_POLICY)
        new_names = [
            name
            for name in scenario_names
            if args.refresh_existing_run_rows
            or (
                str(run_dir),
                name,
                agent,
                user,
                base_tool_policy,
            )
            not in existing
        ]
        skipped_duplicate_rows += len(scenario_names) - len(new_names)
        if not new_names:
            continue

        if not args.dry_run:
            records = cache.collect_run(
                run_dir=run_dir,
                config=ToolSandboxRunConfig(
                    agent=agent,
                    user=user,
                    scenario_names=tuple(new_names),
                    output_dir=run_dir.parent,
                    processes=1,
                    run_type=str(manifest.get("run_type") or "control"),
                    base_tool_policy=base_tool_policy,
                ),
                manifest_path=run_dir.parent / "sage_ts_run_manifest.json",
            )
            collected_records += len(records)
            for name in new_names:
                existing.add((str(run_dir), name, agent, user, base_tool_policy))
        else:
            collected_records += len(new_names)
        collected_run_dirs.append(str(run_dir))

    report = {
        "output_root": str(args.output_root),
        "cache_root": str(args.cache_root),
        "dry_run": args.dry_run,
        "refresh_existing_run_rows": args.refresh_existing_run_rows,
        "fresh_control_run_dirs_scanned": scanned,
        "skipped_cached_control_dirs": skipped_cached,
        "skipped_missing_manifest": skipped_missing_manifest,
        "skipped_empty_result": skipped_empty,
        "skipped_duplicate_rows": skipped_duplicate_rows,
        "collected_or_collectable_records": collected_records,
        "collected_run_dir_count": len(collected_run_dirs),
        "collected_run_dirs": collected_run_dirs,
        "policy": {
            "candidate_or_sage_traces_read": False,
            "truth_labels_read": False,
            "synthetic_cached_control_dirs_ingested": False,
            "future_reuse_requires_task_level_compatibility": True,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
