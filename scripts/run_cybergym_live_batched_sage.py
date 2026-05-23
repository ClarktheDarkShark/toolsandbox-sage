"""Run live CyberGym standalone SAGE in bounded download/image batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sage_agent import SAGEAgent, SAGEConfig, SAGERunSummary  # noqa: E402
from sage_agent.adapters import (  # noqa: E402
    CyberGymLiveSubmitAdapter,
    CyberGymLiveTask,
)
from sage_agent.baselines import OpenAIEnvironmentBaseline  # noqa: E402
from sage_agent.dashboard import (  # noqa: E402
    open_standalone_dashboard,
    write_standalone_dashboard,
)
from sage_agent.generators import (  # noqa: E402
    OpenAIHelperGenerator,
    TemplateHelperGenerator,
)
from sage_agent.interfaces import EnvironmentAdapter, TaskRunResult  # noqa: E402

DATASET_REPO = "sunblaze-ucb/cybergym"
DEFAULT_WORK_ROOT = Path("outputs/cybergym_live_sage/batched_work")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks-json", type=Path, default=Path("cybergym_data/tasks.json")
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--task-offset",
        type=int,
        default=0,
        help=(
            "Skip this many eligible tasks after applying public task filters. "
            "This supports fair contiguous-window probes without selecting by "
            "labels, answers, or cache availability."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--difficulty", default="level1")
    parser.add_argument("--server", default="http://127.0.0.1:8666")
    parser.add_argument(
        "--pulse-reference",
        choices=("off", "first20-reference"),
        default="first20-reference",
        help=(
            "Record batch-level progress checks against a prior same-window "
            "reference curve. Diagnostic metadata only; does not change "
            "generation, routing, candidate ordering, or scoring."
        ),
    )
    parser.add_argument("--start-server", action="store_true", default=True)
    parser.add_argument("--no-start-server", action="store_false", dest="start_server")
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--baseline-max-candidates", type=int, default=12)
    parser.add_argument(
        "--adaptive-reserve-candidates",
        type=int,
        default=0,
        help=(
            "SAGE-only failure reserve: keep the normal max-candidates ordering, "
            "then submit up to this many additional diverse reserve candidates "
            "only if the initial budget does not solve the task. This is a "
            "recorded candidate-budget allocation policy, not force-calling."
        ),
    )
    parser.add_argument(
        "--candidate-strategy",
        choices=(
            "balanced",
            "format-focus",
            "literal-reserve",
            "sample-first",
            "source-first",
            "context-aware",
            "wide-diverse",
        ),
        default="balanced",
        help=(
            "General candidate-planning strategy for SAGE helper routing and "
            "candidate composition. These are environment-neutral policies, not "
            "task-specific answers."
        ),
    )
    parser.add_argument(
        "--candidate-prescreen",
        choices=("off", "vulnerable-local", "vulnerable-batch", "vulnerable-search"),
        default="off",
        help=(
            "Optional SAGE candidate-budget triage. vulnerable-local runs each "
            "generated candidate against the public vulnerable target locally; "
            "vulnerable-batch runs many generated candidates in one public local "
            "container before official submit.sh submission; vulnerable-search "
            "also allows a generated helper to request bounded public vulnerable "
            "local fuzz/search from visible seeds. These modes do not use "
            "fixed-side results, reference PoCs, or labels during candidate "
            "discovery, and official score still comes only from submit.sh/"
            "fixed-side verification."
        ),
    )
    parser.add_argument(
        "--prescreen-submit-floor",
        type=int,
        default=0,
        help=(
            "When candidate-prescreen is enabled, still submit this many early "
            "candidates officially even if local vulnerable pre-screen does not "
            "crash. Use 0 for strict triage."
        ),
    )
    parser.add_argument(
        "--prescreen-cmd-timeout",
        type=int,
        default=10,
        help="Per-candidate target command timeout for local vulnerable pre-screen.",
    )
    parser.add_argument("--max-new-tools", type=int, default=8)
    parser.add_argument("--max-new-tools-per-task", type=int, default=3)
    parser.add_argument("--max-refinements", type=int, default=4)
    parser.add_argument("--max-gap-signals-per-task", type=int, default=6)
    parser.add_argument(
        "--defer-birth-task-retries",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Birth a small helper bundle from a failed task, then retry once with "
            "the complete bundle. This is useful for expensive candidate-submission "
            "environments and avoids retrying after every individual helper birth."
        ),
    )
    parser.add_argument("--min-uses-before-lifecycle-action", type=int, default=4)
    parser.add_argument("--weak-helper-success-rate", type=float, default=0.25)
    parser.add_argument("--failed-repair-limit-before-parking", type=int, default=2)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--llm-timeout", type=float, default=180.0)
    parser.add_argument("--submit-timeout", type=float, default=300.0)
    parser.add_argument(
        "--fixed-side-check",
        action="store_true",
        help=(
            "Score CyberGym success only when a candidate crashes the vulnerable "
            "target and passes the fixed-side verifier."
        ),
    )
    parser.add_argument(
        "--baseline",
        choices=("llm", "fixed"),
        default="llm",
        help="Baseline policy. llm uses gpt-4o-mini over visible task artifacts.",
    )
    parser.add_argument(
        "--baseline-cache",
        choices=("off", "use-if-eligible"),
        default="use-if-eligible",
        help=(
            "Reuse cached baseline task results when the task, visible artifacts, "
            "model, and baseline candidate budget match."
        ),
    )
    parser.add_argument(
        "--baseline-cache-path",
        type=Path,
        default=Path("artifacts/cybergym_live_sage/baseline_cache.json"),
    )
    parser.add_argument(
        "--generator",
        choices=("template", "openai"),
        default="template",
        help="Helper generator. Template is deterministic and token-free; openai uses the configured API key.",
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("artifacts/cybergym_live_sage/batched20_registry"),
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("outputs/cybergym_live_sage")
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_WORK_ROOT,
    )
    parser.add_argument(
        "--task-dir-cache-root",
        type=Path,
        default=Path("artifacts/cybergym_live_sage/materialized_task_cache"),
        help=(
            "Cache public CyberGym visible assets and generated task dirs by "
            "task/difficulty/server mode. This never stores labels, reference "
            "PoCs, hidden answers, or SAGE outcomes."
        ),
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--dashboard-port", type=int, default=62630)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument("--reset-registry", action="store_true")
    parser.add_argument(
        "--image-pull-workers",
        type=int,
        default=4,
        help=("Parallel Docker image pulls per batch. Set to 1 for serial pulls."),
    )
    parser.add_argument(
        "--skip-existing-images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip docker pull when the exact requested image already exists locally.",
    )
    parser.add_argument(
        "--require-existing-images",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Diagnostic speed mode: skip tasks whose required vulnerable/fixed "
            "Docker images are not already local instead of pulling them. This "
            "uses environment setup cache only, not labels, answers, or prior "
            "SAGE outcomes, and is recorded as non-formal sampling metadata."
        ),
    )
    parser.add_argument(
        "--clear-images",
        action="store_true",
        default=False,
        help=(
            "Remove pulled Docker images after each batch. Disabled by default "
            "so repeated validation does not re-download the same images."
        ),
    )
    parser.add_argument("--no-clear-images", action="store_false", dest="clear_images")
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()

    if args.model != "gpt-4o-mini":
        raise SystemExit("CyberGym batched smoke is capped to gpt-4o-mini.")
    if args.reset_registry and args.registry_dir.exists():
        shutil.rmtree(args.registry_dir)

    tasks = _select_tasks(
        args.tasks_json,
        limit=args.limit,
        difficulty=args.difficulty,
        offset=args.task_offset,
    )
    run_id = args.run_id or _default_run_id(args.limit)
    run_dir = args.output_root / run_id
    if args.work_root == DEFAULT_WORK_ROOT:
        args.work_root = args.output_root / f"{run_id}_work"
    run_dir.mkdir(parents=True, exist_ok=True)
    initial_metadata = _run_metadata(args, tasks, batch_reports=())
    initial_dashboard = write_standalone_dashboard(
        _empty_summary("cybergym-live", args.model, args.registry_dir),
        run_dir,
        registry_path=args.registry_dir / "sage_registry.json",
        baseline={
            "policy": f"{args.baseline}_baseline_pending",
            "tasks_seen": 0,
            "tasks_succeeded": 0,
            "success_rate": 0.0,
            "results": [],
        },
        run_metadata={**initial_metadata, "status": "running"},
    )
    if not args.no_dashboard_open:
        url = open_standalone_dashboard(initial_dashboard, port=args.dashboard_port)
        print(f"Dashboard opened at run start: {url}", flush=True)
    server_proc = _ensure_server(args.server, run_dir) if args.start_server else None
    try:
        summary, baseline, batch_reports = _run_batches(args, tasks, run_dir=run_dir)
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()

    run_metadata = _run_metadata(args, tasks, batch_reports=batch_reports)
    dashboard_path = write_standalone_dashboard(
        summary,
        run_dir,
        registry_path=args.registry_dir / "sage_registry.json",
        baseline=baseline,
        run_metadata=run_metadata,
    )
    payload = asdict(summary)
    payload["baseline"] = baseline
    payload["run_metadata"] = run_metadata
    payload["dashboard_path"] = str(dashboard_path)
    (run_dir / "batched_live_summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


def _run_metadata(
    args: argparse.Namespace,
    tasks: list[dict[str, Any]],
    *,
    batch_reports: Any,
) -> dict[str, Any]:
    return {
        "execution_mode": "cybergym_live_level1_submit_vul_batched",
        "benchmark_ready": False,
        "requested_limit": args.limit,
        "task_offset": args.task_offset,
        "available_tasks": len(tasks),
        "limit_satisfied": len(tasks) == args.limit,
        "batch_size": args.batch_size,
        "real_task_generator_used": True,
        "real_submission_server_used": True,
        "real_poc_verifier_used": True,
        "official_success_verification": bool(args.fixed_side_check),
        "fixed_side_check": bool(args.fixed_side_check),
        "llm_timeout_seconds": args.llm_timeout,
        "submit_timeout_seconds": args.submit_timeout,
        "baseline_cache_policy": args.baseline_cache,
        "baseline_cache_path": str(args.baseline_cache_path),
        "pulse_reference": args.pulse_reference,
        "image_cache_policy": {
            "clear_images_after_batch": bool(args.clear_images),
            "skip_existing_images": bool(args.skip_existing_images),
            "require_existing_images": bool(args.require_existing_images),
            "image_pull_workers": max(1, int(args.image_pull_workers)),
        },
        "task_dir_cache_policy": {
            "enabled": True,
            "cache_root": str(args.task_dir_cache_root),
            "contents": (
                "public repo-vul.tar.gz, public description.txt, generated "
                "README.md, generated submit.sh, and cache manifest hashes only"
            ),
            "excluded": (
                "labels, reference PoCs, hidden answers, fixed-side outputs, "
                "SAGE traces, and candidate outcomes"
            ),
        },
        "sage_lifecycle_policy": {
            "candidate_strategy": args.candidate_strategy,
            "adaptive_reserve_candidates": args.adaptive_reserve_candidates,
            "max_new_tools": args.max_new_tools,
            "max_new_tools_per_task": args.max_new_tools_per_task,
            "max_refinements": args.max_refinements,
            "max_gap_signals_per_task": args.max_gap_signals_per_task,
            "defer_birth_task_retries": bool(args.defer_birth_task_retries),
            "min_uses_before_lifecycle_action": args.min_uses_before_lifecycle_action,
            "weak_helper_success_rate": args.weak_helper_success_rate,
            "failed_repair_limit_before_parking": args.failed_repair_limit_before_parking,
            "candidate_prescreen": args.candidate_prescreen,
            "prescreen_submit_floor": args.prescreen_submit_floor,
            "prescreen_cmd_timeout": args.prescreen_cmd_timeout,
        },
        "interpretation": (
            "Real CyberGym submit.sh smoke using generated Level 1 task dirs in "
            "bounded batches. This confirms environment wiring and SAGE lifecycle "
            "on live CyberGym submission. If fixed_side_check is enabled, scoring "
            "requires vulnerable-side crash plus fixed-side preservation; otherwise "
            "this is a vulnerable-side portability smoke only."
        ),
        "setup_notes": (
            "Only level1 visible assets are downloaded: repo-vul.tar.gz and description.txt.",
            "Batch work directories are cleared after each batch unless requested otherwise.",
            "Docker images are retained by default and reused as environment setup cache; use --clear-images to reclaim disk space.",
            "SAGE starts from the supplied registry; use --reset-registry for an empty generated-tool registry.",
            "Submissions remain environment-side effects; generated helpers only prepare candidate strings.",
        ),
        "batch_reports": batch_reports,
    }


def _select_tasks(
    tasks_json: Path, *, limit: int, difficulty: str, offset: int = 0
) -> list[dict[str, Any]]:
    tasks = json.loads(tasks_json.read_text(encoding="utf-8"))
    if offset < 0:
        raise ValueError("task offset must be non-negative")
    selected = []
    skipped_eligible = 0
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id.startswith(("arvo:", "oss-fuzz:")):
            continue
        files = task.get("task_difficulty", {}).get(difficulty)
        if not files:
            continue
        if skipped_eligible < offset:
            skipped_eligible += 1
            continue
        selected.append(task)
        if len(selected) >= limit:
            break
    return selected


def _ensure_server(server: str, run_dir: Path) -> subprocess.Popen[str] | None:
    parsed = urlparse(server)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8666
    if _port_open(host, port):
        return None
    log_dir = run_dir / "server"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_entrypoint = ROOT / "external/cybergym/src/cybergym/server/__main__.py"
    if server_entrypoint.exists():
        cmd = [sys.executable, str(server_entrypoint)]
    else:
        cmd = [sys.executable, "-m", "cybergym.server"]
    cmd.extend(
        [
            "--host",
            host,
            "--port",
            str(port),
            "--mask_map_path",
            str(ROOT / "external/cybergym/mask_map.json"),
            "--log_dir",
            str(log_dir),
            "--db_path",
            str(log_dir / "poc.db"),
        ]
    )
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=(log_dir / "server.stdout.log").open("w", encoding="utf-8"),
        stderr=(log_dir / "server.stderr.log").open("w", encoding="utf-8"),
    )
    for _ in range(60):
        if _port_open(host, port):
            return proc
        if proc.poll() is not None:
            raise RuntimeError(f"CyberGym server exited early: {proc.returncode}")
        time.sleep(1)
    raise TimeoutError("CyberGym server did not open its port")


def _run_batches(
    args: argparse.Namespace, tasks: list[dict[str, Any]], *, run_dir: Path
) -> tuple[SAGERunSummary, dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    baseline_results: list[dict[str, Any]] = []
    baseline_cache = _load_baseline_cache(args.baseline_cache_path)
    baseline_cache_stats = {"cached": 0, "fresh": 0}
    baseline_planner: OpenAIEnvironmentBaseline | None = None
    shared_feedback_memory: list[str] = []
    totals = {
        "tasks_seen": 0,
        "tasks_succeeded": 0,
        "gaps_observed": 0,
        "tools_born": 0,
        "tools_accepted": 0,
        "tools_rejected": 0,
        "tools_reused": 0,
        "repair_attempts": 0,
        "tools_refined": 0,
        "birth_task_retries": 0,
        "birth_task_retry_successes": 0,
        "integrity_issues": 0,
    }
    batch_reports: list[dict[str, Any]] = []
    for batch_index, start in enumerate(range(0, len(tasks), args.batch_size), 1):
        batch = tasks[start : start + args.batch_size]
        batch_root = args.work_root / f"batch_{batch_index:02d}"
        data_root = batch_root / "data"
        task_root = batch_root / "tasks"
        data_root.mkdir(parents=True, exist_ok=True)
        task_root.mkdir(parents=True, exist_ok=True)
        images: list[str] = []
        task_images: list[tuple[str, list[str]]] = []
        skipped: list[str] = []
        try:
            _write_partial_dashboard(
                args=args,
                run_dir=run_dir,
                totals=totals,
                events=events,
                baseline_results=baseline_results,
                batch_reports=batch_reports,
                current_status={
                    "stage": "preparing_visible_assets",
                    "batch": batch_index,
                    "tasks": [str(task["task_id"]) for task in batch],
                    "message": "Downloading visible assets and generating task directories.",
                },
            )
            for local_index, task in enumerate(batch, 1):
                task_id = str(task["task_id"])
                try:
                    required_images = [_vul_image(task_id)]
                    if args.fixed_side_check:
                        required_images.append(_fix_image(task_id))
                    if args.require_existing_images:
                        missing_images = [
                            image
                            for image in required_images
                            if not _image_exists(image)
                        ]
                        if missing_images:
                            skipped.append(
                                f"{task_id}: LocalDockerImageMissing: "
                                + ", ".join(missing_images)
                            )
                            continue
                    _ensure_materialized_task_dir(
                        task,
                        args.difficulty,
                        task_root / _task_dir_name(local_index, task_id),
                        data_root,
                        args.server,
                        args.task_dir_cache_root,
                    )
                    image = _vul_image(task_id)
                    current_images = [image]
                    if args.fixed_side_check:
                        fix_image = _fix_image(task_id)
                        current_images.append(fix_image)
                    images.extend(current_images)
                    task_images.append((task_id, current_images))
                except Exception as exc:
                    skipped.append(f"{task_id}: {type(exc).__name__}: {exc}")
            _write_partial_dashboard(
                args=args,
                run_dir=run_dir,
                totals=totals,
                events=events,
                baseline_results=baseline_results,
                batch_reports=batch_reports,
                current_status={
                    "stage": "preparing_docker_images",
                    "batch": batch_index,
                    "tasks": [task_id for task_id, _ in task_images],
                    "skipped": skipped,
                    "message": (
                        "Checking local Docker images."
                        if args.require_existing_images
                        else "Pulling or checking required Docker images."
                    ),
                },
            )
            if not args.require_existing_images:
                skipped.extend(
                    _pull_images_for_tasks(
                        task_images,
                        workers=max(1, int(args.image_pull_workers)),
                        skip_existing=bool(args.skip_existing_images),
                    )
                )
            live_tasks = _live_tasks_for_batch(batch, task_root, skipped)
            _write_partial_dashboard(
                args=args,
                run_dir=run_dir,
                totals=totals,
                events=events,
                baseline_results=baseline_results,
                batch_reports=batch_reports,
                current_status={
                    "stage": "running_matched_arms",
                    "batch": batch_index,
                    "tasks": [task.task_key for task in live_tasks],
                    "skipped": skipped,
                    "message": "Running cached baseline lookups and fresh SAGE submissions.",
                },
            )
            adapter = CyberGymLiveSubmitAdapter(
                tasks_root=task_root,
                tasks_to_run=tuple(live_tasks),
                max_candidates=args.max_candidates,
                submit_timeout_seconds=args.submit_timeout,
                fixed_side_check=args.fixed_side_check,
                candidate_strategy=args.candidate_strategy,
                adaptive_reserve_candidates=args.adaptive_reserve_candidates,
                candidate_prescreen=args.candidate_prescreen,
                prescreen_submit_floor=args.prescreen_submit_floor,
                prescreen_cmd_timeout_seconds=args.prescreen_cmd_timeout,
                _feedback_memory=shared_feedback_memory,
            )
            baseline = _run_baseline(
                adapter,
                args=args,
                planner=baseline_planner,
                baseline_cache=baseline_cache,
                baseline_cache_stats=baseline_cache_stats,
            )
            if args.baseline_cache != "off":
                _save_baseline_cache(args.baseline_cache_path, baseline_cache)
            baseline_results.extend(baseline["results"])
            agent = SAGEAgent(
                adapter=adapter,
                generator=_helper_generator(args.generator),
                config=SAGEConfig(
                    model=args.model,
                    registry_dir=args.registry_dir,
                    max_new_tools=args.max_new_tools,
                    max_new_tools_per_task=args.max_new_tools_per_task,
                    max_refinements=args.max_refinements,
                    max_gap_signals_per_task=args.max_gap_signals_per_task,
                    defer_birth_task_retries=bool(args.defer_birth_task_retries),
                    min_uses_before_lifecycle_action=(
                        args.min_uses_before_lifecycle_action
                    ),
                    weak_helper_success_rate=args.weak_helper_success_rate,
                    failed_repair_limit_before_parking=(
                        args.failed_repair_limit_before_parking
                    ),
                ),
            )
            batch_summary = agent.run()
            for key in totals:
                if key == "integrity_issues":
                    totals[key] += batch_summary.integrity_issues
                else:
                    totals[key] += int(getattr(batch_summary, key))
            for event in batch_summary.events:
                item = dict(event)
                item["batch"] = batch_index
                events.append(item)
            batch_reports.append(
                {
                    "batch": batch_index,
                    "tasks_requested": [str(task["task_id"]) for task in batch],
                    "tasks_run": len(live_tasks),
                    "skipped": skipped,
                    "baseline_successes": baseline["tasks_succeeded"],
                    "sage_successes": batch_summary.tasks_succeeded,
                    "tools_born": batch_summary.tools_born,
                    "tools_reused": batch_summary.tools_reused,
                    "baseline_cached": baseline_cache_stats["cached"],
                    "baseline_fresh": baseline_cache_stats["fresh"],
                    "pulse_assessment": _pulse_assessment(
                        args=args,
                        totals=totals,
                        baseline_results=baseline_results,
                    ),
                }
            )
            _write_partial_dashboard(
                args=args,
                run_dir=run_dir,
                totals=totals,
                events=events,
                baseline_results=baseline_results,
                batch_reports=batch_reports,
                current_status={
                    "stage": "batch_complete",
                    "batch": batch_index,
                    "tasks": [str(task["task_id"]) for task in batch],
                    "skipped": skipped,
                    "message": "Batch complete.",
                },
            )
        finally:
            if args.clear_images:
                for image in images:
                    subprocess.run(
                        ["docker", "rmi", image],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            if not args.keep_work:
                shutil.rmtree(batch_root, ignore_errors=True)
    summary = _summary_from_totals(args=args, totals=totals, events=events)
    baseline = _baseline_from_results(args, baseline_results)
    return summary, baseline, batch_reports


def _write_partial_dashboard(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    totals: dict[str, int],
    events: list[dict[str, Any]],
    baseline_results: list[dict[str, Any]],
    batch_reports: list[dict[str, Any]],
    current_status: dict[str, Any] | None = None,
) -> None:
    metadata = _run_metadata(
        args,
        _select_tasks(
            args.tasks_json,
            limit=args.limit,
            difficulty=args.difficulty,
            offset=args.task_offset,
        ),
        batch_reports=batch_reports,
    )
    if current_status is not None:
        metadata["current_status"] = current_status
    write_standalone_dashboard(
        _summary_from_totals(args=args, totals=totals, events=events),
        run_dir,
        registry_path=args.registry_dir / "sage_registry.json",
        baseline=_baseline_from_results(args, baseline_results),
        run_metadata={
            **metadata,
            "status": "running",
        },
    )


def _summary_from_totals(
    *,
    args: argparse.Namespace,
    totals: dict[str, int],
    events: list[dict[str, Any]],
) -> SAGERunSummary:
    registry_path = args.registry_dir / "sage_registry.json"
    lifecycle: tuple[dict[str, Any], ...] = ()
    if registry_path.exists():
        from sage_agent.lifecycle import assess_helper_lifecycle
        from sage_agent.registry import LocalSAGERegistry

        lifecycle = tuple(
            item.to_json()
            for item in assess_helper_lifecycle(
                LocalSAGERegistry(args.registry_dir).load()
            )
        )
    return SAGERunSummary(
        environment="cybergym-live",
        tasks_seen=totals["tasks_seen"],
        tasks_succeeded=totals["tasks_succeeded"],
        gaps_observed=totals["gaps_observed"],
        tools_born=totals["tools_born"],
        tools_accepted=totals["tools_accepted"],
        tools_rejected=totals["tools_rejected"],
        tools_reused=totals["tools_reused"],
        repair_attempts=totals["repair_attempts"],
        tools_refined=totals["tools_refined"],
        birth_task_retries=totals["birth_task_retries"],
        birth_task_retry_successes=totals["birth_task_retry_successes"],
        model=args.model,
        registry_path=str(registry_path),
        integrity_passed=totals["integrity_issues"] == 0,
        integrity_issues=totals["integrity_issues"],
        lifecycle_decisions=lifecycle,
        events=tuple(events),
    )


def _baseline_from_results(
    args: argparse.Namespace, baseline_results: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline_successes = sum(1 for result in baseline_results if result["success"])
    baseline_policy, baseline_note = _baseline_metadata(args)
    return {
        "policy": baseline_policy,
        "comparison_valid": True,
        "comparison_note": baseline_note,
        "tasks_seen": len(baseline_results),
        "tasks_succeeded": baseline_successes,
        "success_rate": baseline_successes / len(baseline_results)
        if baseline_results
        else 0.0,
        "cache_policy": args.baseline_cache,
        "cache_path": str(args.baseline_cache_path),
        "cached_count": sum(
            1
            for result in baseline_results
            if result.get("control_cache_source") == "cached"
        ),
        "fresh_count": sum(
            1
            for result in baseline_results
            if result.get("control_cache_source") == "fresh"
        ),
        "results": baseline_results,
    }


def _baseline_metadata(args: argparse.Namespace) -> tuple[str, str]:
    if args.baseline == "llm":
        return (
            f"llm_visible_artifact_baseline:{args.model}",
            (
                "Basic LLM baseline over visible CyberGym task files. It sees "
                "README.md, description.txt, and a bounded visible source summary, "
                "then submits candidate strings through the same submit.sh path. "
                "This is a real live comparison for this adapter; fixed-side "
                "verification is included only when fixed_side_check is enabled."
            ),
        )
    return (
        "fixed_four_byte_poc_batched",
        (
            "Fixed four-byte PoC smoke baseline for CyberGym wiring checks. It is "
            "not a fully functional LLM baseline."
        ),
    )


def _pulse_assessment(
    *,
    args: argparse.Namespace,
    totals: dict[str, int],
    baseline_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return same-window progress metadata for human run monitoring."""

    if args.pulse_reference == "off":
        return {
            "enabled": False,
            "reference": "off",
        }
    tasks_seen = int(totals.get("tasks_seen", 0))
    sage_successes = int(totals.get("tasks_succeeded", 0))
    baseline_successes = sum(1 for result in baseline_results if result.get("success"))
    reference_curve = {
        4: {"baseline_successes": 0, "sage_successes": 1},
        8: {"baseline_successes": 0, "sage_successes": 2},
        12: {"baseline_successes": 1, "sage_successes": 3},
        16: {"baseline_successes": 1, "sage_successes": 3},
        20: {"baseline_successes": 1, "sage_successes": 5},
    }
    checkpoints = sorted(reference_curve)
    checkpoint = max((point for point in checkpoints if tasks_seen >= point), default=0)
    if checkpoint == 0:
        return {
            "enabled": True,
            "reference": args.pulse_reference,
            "tasks_seen": tasks_seen,
            "status": "too_early",
            "message": "No reference checkpoint reached yet.",
        }
    target = reference_curve[checkpoint]
    sage_gap = sage_successes - target["sage_successes"]
    baseline_gap = baseline_successes - target["baseline_successes"]
    if sage_gap >= 0:
        status = "on_track"
        message = "SAGE is meeting or exceeding the same-window reference curve."
    elif checkpoint < 20 and sage_gap == -1:
        status = "watch"
        message = (
            "SAGE is one success below the same-window reference; continue to the "
            "next checkpoint before changing policy."
        )
    else:
        status = "reassess"
        message = (
            "SAGE is below the same-window reference; inspect candidate ordering, "
            "tool acceptance, and whether this is the intended task window."
        )
    return {
        "enabled": True,
        "reference": args.pulse_reference,
        "checkpoint_tasks": checkpoint,
        "tasks_seen": tasks_seen,
        "baseline_successes": baseline_successes,
        "sage_successes": sage_successes,
        "reference_baseline_successes": target["baseline_successes"],
        "reference_sage_successes": target["sage_successes"],
        "baseline_gap_vs_reference": baseline_gap,
        "sage_gap_vs_reference": sage_gap,
        "status": status,
        "message": message,
    }


def _helper_generator(name: str) -> TemplateHelperGenerator | OpenAIHelperGenerator:
    if name == "openai":
        return OpenAIHelperGenerator()
    return TemplateHelperGenerator()


def _run_baseline(
    adapter: CyberGymLiveSubmitAdapter,
    *,
    args: argparse.Namespace,
    planner: OpenAIEnvironmentBaseline | None,
    baseline_cache: dict[str, Any],
    baseline_cache_stats: dict[str, int],
) -> dict[str, Any]:
    if args.baseline == "llm":
        return _run_llm_baseline(
            adapter,
            planner=planner,
            model=args.model,
            timeout=args.llm_timeout,
            max_candidates=args.baseline_max_candidates,
            cache_policy=args.baseline_cache,
            baseline_cache=baseline_cache,
            baseline_cache_stats=baseline_cache_stats,
        )
    return _run_no_helper_baseline(adapter)


def _run_llm_baseline(
    adapter: CyberGymLiveSubmitAdapter,
    *,
    planner: OpenAIEnvironmentBaseline | None,
    model: str,
    timeout: float,
    max_candidates: int,
    cache_policy: str,
    baseline_cache: dict[str, Any],
    baseline_cache_stats: dict[str, int],
) -> dict[str, Any]:
    adapter.prepare()
    results: list[dict[str, Any]] = []
    for task in adapter.tasks():
        cache_key = _baseline_cache_key(
            task,
            model=model,
            max_candidates=max_candidates,
            fixed_side_check=adapter.fixed_side_check,
        )
        legacy_cache_key = (
            ""
            if adapter.fixed_side_check
            else _baseline_legacy_cache_key(
                task, model=model, max_candidates=max_candidates
            )
        )
        cache_hit_key = _eligible_baseline_cache_key(
            baseline_cache,
            task=task,
            cache_key=cache_key,
            legacy_cache_key=legacy_cache_key,
            fixed_side_check=adapter.fixed_side_check,
        )
        if cache_policy == "use-if-eligible" and cache_hit_key:
            cached = dict(baseline_cache[cache_hit_key])
            cached["control_cache_source"] = "cached"
            cached["control_cache_key"] = cache_key
            cached["control_cache_match"] = (
                "visible_artifact_hash"
                if cache_hit_key == cache_key
                else "task_id_model_budget"
            )
            results.append(cached)
            baseline_cache_stats["cached"] += 1
            if cache_hit_key != cache_key:
                baseline_cache[cache_key] = cached
            continue
        try:
            if planner is None:
                planner = OpenAIEnvironmentBaseline(model=model, timeout=timeout)
            candidates = planner.plan_candidate_inputs(
                task,
                max_candidates=max_candidates,
            )
            if not candidates:
                candidates = ["\x00\x01\x02\x03"]
            result = adapter.run_candidate_strings(
                task,
                candidates,
                transcript_prefix=(
                    f"LLM baseline planned {len(candidates)} candidate inputs."
                ),
                remember_feedback=False,
            )
        except Exception as exc:  # pragma: no cover - live API/environment failure
            result = TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=(f"LLM baseline failed: {type(exc).__name__}: {exc}",),
                error=str(exc),
            )
        result_json = _baseline_result_json(result)
        result_json["control_cache_source"] = "fresh"
        result_json["control_cache_key"] = cache_key
        results.append(result_json)
        if not _baseline_result_is_credential_failure(result_json):
            baseline_cache[cache_key] = result_json
        baseline_cache_stats["fresh"] += 1
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": f"llm_visible_artifact_baseline:{model}",
        "tasks_seen": len(results),
        "tasks_succeeded": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "cache_policy": cache_policy,
        "cached_count": sum(
            1 for result in results if result.get("control_cache_source") == "cached"
        ),
        "fresh_count": sum(
            1 for result in results if result.get("control_cache_source") == "fresh"
        ),
        "results": results,
    }


def _load_baseline_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    records = payload.get("records", payload)
    if not isinstance(records, dict):
        return {}
    return {
        str(key): value for key, value in records.items() if isinstance(value, dict)
    }


def _save_baseline_cache(path: Path, records: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            import fcntl

            fcntl.flock(lock_handle, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        merged_records = _load_baseline_cache(path)
        merged_records.update(records)
        records = merged_records
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        payload = {
            "schema_version": 1,
            "policy": "cybergym_visible_llm_baseline_task_cache",
            "records": records,
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            import fcntl

            fcntl.flock(lock_handle, fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock_handle.close()


def _eligible_baseline_cache_key(
    records: dict[str, Any],
    *,
    task: Any,
    cache_key: str,
    legacy_cache_key: str,
    fixed_side_check: bool,
) -> str:
    """Find an eligible cached control record even after visible summaries change."""

    for key in (cache_key, legacy_cache_key):
        record = records.get(key)
        if isinstance(record, dict) and _usable_cached_baseline_record(
            record, task=task, fixed_side_check=fixed_side_check
        ):
            return key
    task_id = str(task.task_id)
    for key, record in records.items():
        if not isinstance(record, dict):
            continue
        if str(record.get("task_id", "")) != task_id:
            continue
        if _usable_cached_baseline_record(
            record, task=task, fixed_side_check=fixed_side_check
        ):
            return str(key)
    return ""


def _usable_cached_baseline_record(
    record: dict[str, Any], *, task: Any, fixed_side_check: bool
) -> bool:
    """Return true when a cached baseline record is safe to reuse for this task."""

    if str(record.get("task_id", "")) != str(task.task_id):
        return False
    if _baseline_result_is_credential_failure(record):
        return False
    if not fixed_side_check or not bool(record.get("success")):
        return True
    attempts = record.get("artifacts", {}).get("attempts", [])
    if not isinstance(attempts, list):
        return False
    return any(
        isinstance(attempt, dict)
        and bool(attempt.get("fixed_side_checked"))
        and bool(attempt.get("official_success"))
        for attempt in attempts
    )


def _baseline_result_is_credential_failure(record: dict[str, Any]) -> bool:
    text = f"{record.get('error', '')} {' '.join(record.get('transcript', []))}"
    return "missing credentials" in text.lower() or "missing api" in text.lower()


def _baseline_cache_key(
    task: Any, *, model: str, max_candidates: int, fixed_side_check: bool
) -> str:
    visible_payload = {
        "policy_version": "cybergym-visible-llm-baseline-v1",
        "task_id": task.task_id,
        "task_name": task.name,
        "prompt": task.prompt,
        "artifacts": task.artifacts,
        "model": model,
        "max_candidates": max_candidates,
        "fixed_side_check": fixed_side_check,
    }
    raw = json.dumps(visible_payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _baseline_legacy_cache_key(task: Any, *, model: str, max_candidates: int) -> str:
    raw = json.dumps(
        {
            "policy_version": "cybergym-visible-llm-baseline-v1-legacy-task-key",
            "task_id": task.task_id,
            "model": model,
            "max_candidates": max_candidates,
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _download_visible_assets(
    task: dict[str, Any], difficulty: str, data_root: Path
) -> None:
    from huggingface_hub import hf_hub_download

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    stable_data_root = ROOT / "cybergym_data"
    files = task.get("task_difficulty", {}).get(difficulty, [])
    for filename in files:
        if not (
            filename.endswith("repo-vul.tar.gz") or filename.endswith("description.txt")
        ):
            continue
        stable_path = stable_data_root / str(filename)
        batch_path = data_root / str(filename)
        if stable_path.exists() and (
            not filename.endswith("repo-vul.tar.gz") or stable_path.stat().st_size > 0
        ):
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stable_path, batch_path)
            continue
        if stable_path.exists() and stable_path.stat().st_size == 0:
            stable_path.unlink()
        hf_hub_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            filename=str(filename),
            local_dir=stable_data_root,
            cache_dir=ROOT / "cybergym_data/.cache/huggingface",
        )
        if stable_path.exists():
            if filename.endswith("repo-vul.tar.gz") and stable_path.stat().st_size == 0:
                raise RuntimeError(
                    f"downloaded empty public source archive: {filename}"
                )
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stable_path, batch_path)


def _ensure_materialized_task_dir(
    task: dict[str, Any],
    difficulty: str,
    out_dir: Path,
    data_root: Path,
    server: str,
    cache_root: Path,
) -> None:
    """Reuse public CyberGym task materialization without caching outcomes."""

    task_id = str(task["task_id"])
    cache_dir = _task_dir_cache_path(
        task,
        difficulty=difficulty,
        server=server,
        cache_root=cache_root,
    )
    manifest_path = cache_dir / "materialized_task_manifest.json"
    if _valid_materialized_task_cache(cache_dir, manifest_path, task_id=task_id):
        _copy_cached_task_dir(cache_dir / "task", out_dir, server=server)
        _copy_cached_public_data(cache_dir / "data", data_root)
        print(f"CyberGym task cache hit: {task_id}", flush=True)
        return

    harvested = _harvest_existing_materialized_task(
        task,
        difficulty=difficulty,
        out_dir=out_dir,
        data_root=data_root,
        server=server,
        cache_dir=cache_dir,
    )
    if harvested:
        print(f"CyberGym task cache harvested: {task_id}", flush=True)
        return

    staging_root = cache_dir.with_name(f"{cache_dir.name}.tmp.{os.getpid()}")
    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)
    staging_data = staging_root / "data"
    staging_task = staging_root / "task"
    staging_data.mkdir(parents=True, exist_ok=True)
    staging_task.mkdir(parents=True, exist_ok=True)
    _download_visible_assets(task, difficulty, staging_data)
    _generate_task_dir(task_id, staging_task, staging_data, server, difficulty)
    manifest = {
        "schema_version": 1,
        "policy": "cybergym_public_visible_task_materialization_cache",
        "task_id": task_id,
        "difficulty": difficulty,
        "server_mode": _server_cache_mode(server),
        "public_files": _public_data_hashes(staging_data),
        "task_files": _task_dir_hashes(staging_task),
        "research_integrity": {
            "labels_cached": False,
            "reference_pocs_cached": False,
            "hidden_answers_cached": False,
            "sage_outcomes_cached": False,
            "candidate_outputs_cached": False,
        },
    }
    (staging_root / "materialized_task_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
    staging_root.replace(cache_dir)
    _copy_cached_task_dir(cache_dir / "task", out_dir, server=server)
    _copy_cached_public_data(cache_dir / "data", data_root)
    print(f"CyberGym task cache stored: {task_id}", flush=True)


def _harvest_existing_materialized_task(
    task: dict[str, Any],
    *,
    difficulty: str,
    out_dir: Path,
    data_root: Path,
    server: str,
    cache_dir: Path,
) -> bool:
    """Import old public task dirs into the formal materialized-task cache."""

    task_id = str(task["task_id"])
    safe_suffix = task_id.replace(":", "_")
    for candidate_task_dir in sorted(
        (ROOT / "outputs/cybergym_live_sage").glob(f"**/*_{safe_suffix}")
    ):
        if not candidate_task_dir.is_dir():
            continue
        if not all(
            (candidate_task_dir / name).exists()
            for name in ("README.md", "description.txt", "repo-vul.tar.gz", "submit.sh")
        ):
            continue
        if (candidate_task_dir / "repo-vul.tar.gz").stat().st_size == 0:
            continue
        staging_root = cache_dir.with_name(f"{cache_dir.name}.harvest.{os.getpid()}")
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        staging_task = staging_root / "task"
        staging_data = staging_root / "data"
        staging_task.mkdir(parents=True, exist_ok=True)
        _copy_task_public_files(candidate_task_dir, staging_task)
        _copy_public_files_for_task(task, difficulty, candidate_task_dir, staging_data)
        manifest = {
            "schema_version": 1,
            "policy": "cybergym_public_visible_task_materialization_cache",
            "task_id": task_id,
            "difficulty": difficulty,
            "server_mode": "rewritten_on_copy",
            "public_files": _public_data_hashes(staging_data),
            "task_files": _task_dir_hashes(staging_task),
            "source": "harvested_existing_public_task_dir",
            "source_task_dir": str(candidate_task_dir),
            "research_integrity": {
                "labels_cached": False,
                "reference_pocs_cached": False,
                "hidden_answers_cached": False,
                "sage_outcomes_cached": False,
                "candidate_outputs_cached": False,
            },
        }
        (staging_root / "materialized_task_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
        staging_root.replace(cache_dir)
        _copy_cached_task_dir(cache_dir / "task", out_dir, server=server)
        _copy_cached_public_data(cache_dir / "data", data_root)
        return True
    return False


def _copy_task_public_files(source_task_dir: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("README.md", "description.txt", "repo-vul.tar.gz", "submit.sh"):
        shutil.copy2(source_task_dir / name, destination / name)


def _copy_public_files_for_task(
    task: dict[str, Any], difficulty: str, source_task_dir: Path, data_root: Path
) -> None:
    task_id = str(task["task_id"])
    family, sub_id = task_id.split(":", 1)
    files = [
        str(filename)
        for filename in task.get("task_difficulty", {}).get(difficulty, [])
        if str(filename).endswith(("repo-vul.tar.gz", "description.txt"))
    ]
    for filename in files:
        source = source_task_dir / Path(filename).name
        if not source.exists():
            continue
        target = data_root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if not files:
        visible_dir = data_root / "data" / family / sub_id
        visible_dir.mkdir(parents=True, exist_ok=True)
        for name in ("repo-vul.tar.gz", "description.txt"):
            shutil.copy2(source_task_dir / name, visible_dir / name)


def _task_dir_cache_path(
    task: dict[str, Any], *, difficulty: str, server: str, cache_root: Path
) -> Path:
    del server
    task_id = str(task["task_id"])
    files = [
        str(filename)
        for filename in task.get("task_difficulty", {}).get(difficulty, [])
        if str(filename).endswith(("repo-vul.tar.gz", "description.txt"))
    ]
    payload = {
        "task_id": task_id,
        "difficulty": difficulty,
        "files": files,
        "server_mode": "rewritten_on_copy",
        "generator": "cybergym.task.gen_task",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    safe_task_id = task_id.replace(":", "_")
    return cache_root / difficulty / f"{safe_task_id}_{digest}"


def _server_cache_mode(server: str) -> str:
    parsed = urlparse(server)
    return f"{parsed.scheme or 'http'}://{parsed.hostname or '127.0.0.1'}:{parsed.port or 8666}"


def _valid_materialized_task_cache(
    cache_dir: Path, manifest_path: Path, *, task_id: str
) -> bool:
    if not cache_dir.exists() or not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if str(manifest.get("task_id", "")) != task_id:
        return False
    integrity = manifest.get("research_integrity", {})
    if not isinstance(integrity, dict):
        return False
    if any(
        bool(integrity.get(key))
        for key in (
            "labels_cached",
            "reference_pocs_cached",
            "hidden_answers_cached",
            "sage_outcomes_cached",
            "candidate_outputs_cached",
        )
    ):
        return False
    task_dir = cache_dir / "task"
    data_dir = cache_dir / "data"
    if not all(
        (task_dir / name).exists()
        for name in ("README.md", "description.txt", "repo-vul.tar.gz", "submit.sh")
    ):
        return False
    if (task_dir / "repo-vul.tar.gz").stat().st_size == 0:
        return False
    return data_dir.exists()


def _copy_cached_task_dir(source: Path, destination: Path, *, server: str) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    submit_path = destination / "submit.sh"
    if submit_path.exists():
        text = submit_path.read_text(encoding="utf-8")
        text = re.sub(r"https?://[^\s/'\"]+:\d+", server, text)
        submit_path.write_text(text, encoding="utf-8")


def _copy_cached_public_data(source: Path, destination_root: Path) -> None:
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        target = destination_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _public_data_hashes(data_root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(data_root)): _file_sha256(path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file()
    }


def _task_dir_hashes(task_dir: Path) -> dict[str, str]:
    allowed = {"README.md", "description.txt", "repo-vul.tar.gz", "submit.sh"}
    return {
        path.name: _file_sha256(path)
        for path in sorted(task_dir.iterdir())
        if path.is_file() and path.name in allowed
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generate_task_dir(
    task_id: str, out_dir: Path, data_root: Path, server: str, difficulty: str
) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cybergym.task.gen_task",
            "--task-id",
            task_id,
            "--out-dir",
            str(out_dir),
            "--data-dir",
            str(data_root / "data"),
            "--server",
            server,
            "--difficulty",
            difficulty,
            "--mask-map",
            str(ROOT / "external/cybergym/mask_map.json"),
        ],
        check=True,
        cwd=ROOT,
    )


def _pull_images_for_tasks(
    task_images: list[tuple[str, list[str]]], *, workers: int, skip_existing: bool
) -> list[str]:
    """Pull required Docker images, returning task-level skip reasons."""
    if not task_images:
        return []
    workers = max(1, min(workers, len(task_images)))
    if workers == 1:
        serial_failures = []
        for task_id, images in task_images:
            try:
                for image in images:
                    _pull_image(image, skip_existing=skip_existing)
            except Exception as exc:
                serial_failures.append(f"{task_id}: DockerImagePullError: {exc}")
        return serial_failures

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _pull_task_images, task_id, images, skip_existing=skip_existing
            ): task_id
            for task_id, images in task_images
        }
        for future in as_completed(futures):
            task_id = futures[future]
            try:
                future.result()
            except Exception as exc:
                failures.append(f"{task_id}: DockerImagePullError: {exc}")
    return failures


def _pull_task_images(task_id: str, images: list[str], *, skip_existing: bool) -> None:
    del task_id
    for image in images:
        _pull_image(image, skip_existing=skip_existing)


def _pull_image(image: str, *, skip_existing: bool) -> None:
    if skip_existing and _image_exists(image):
        print(f"Docker image cached: {image}", flush=True)
        return
    print(f"Pulling Docker image: {image}", flush=True)
    result = subprocess.run(
        ["docker", "pull", image],
        check=False,
        timeout=1800,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        tail = (result.stdout or "").strip()[-2000:]
        raise RuntimeError(f"docker pull failed for {image}: {tail}")
    print(f"Docker image ready: {image}", flush=True)


def _image_exists(image: str) -> bool:
    return (
        subprocess.run(
            ["docker", "image", "inspect", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def _run_no_helper_baseline(adapter: EnvironmentAdapter) -> dict[str, Any]:
    adapter.prepare()
    results = [
        _baseline_result_json(adapter.run_task(task, {})) for task in adapter.tasks()
    ]
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": "fixed_four_byte_poc",
        "tasks_seen": len(results),
        "tasks_succeeded": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "results": results,
    }


def _baseline_result_json(result: TaskRunResult) -> dict[str, Any]:
    return {
        "task_id": result.task.task_id,
        "name": result.task.name,
        "success": result.success,
        "score": result.score,
        "outcome_score": result.outcome_score,
        "error": result.error,
        "transcript": list(result.transcript),
        "artifacts": dict(result.artifacts),
    }


def _empty_summary(environment: str, model: str, registry_dir: Path) -> SAGERunSummary:
    return SAGERunSummary(
        environment=environment,
        tasks_seen=0,
        tasks_succeeded=0,
        gaps_observed=0,
        tools_born=0,
        tools_accepted=0,
        tools_rejected=0,
        tools_reused=0,
        repair_attempts=0,
        tools_refined=0,
        birth_task_retries=0,
        birth_task_retry_successes=0,
        model=model,
        registry_path=str(registry_dir / "sage_registry.json"),
        integrity_passed=True,
        integrity_issues=0,
    )


def _live_tasks_for_batch(
    batch: list[dict[str, Any]], task_root: Path, skipped: list[str]
) -> list[CyberGymLiveTask]:
    skipped_ids = {
        item.split(":", 2)[0] + ":" + item.split(":", 2)[1]
        for item in skipped
        if item.count(":") >= 1
    }
    live_tasks = []
    for local_index, task in enumerate(batch, 1):
        task_id = str(task["task_id"])
        if task_id in skipped_ids:
            continue
        live_tasks.append(
            CyberGymLiveTask(
                task_key=task_id,
                task_dir=task_root / _task_dir_name(local_index, task_id),
                display_name=f"CyberGym live Level 1 {task_id}",
            )
        )
    return live_tasks


def _task_dir_name(index: int, task_id: str) -> str:
    return f"{index:02d}_{task_id.replace(':', '_')}"


def _vul_image(task_id: str) -> str:
    family, sub_id = task_id.split(":", 1)
    if family == "arvo":
        return f"n132/arvo:{sub_id}-vul"
    return f"cybergym/oss-fuzz:{sub_id}-vul"


def _fix_image(task_id: str) -> str:
    family, sub_id = task_id.split(":", 1)
    if family == "arvo":
        return f"n132/arvo:{sub_id}-fix"
    return f"cybergym/oss-fuzz:{sub_id}-fix"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _default_run_id(limit: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"batched_live_level1_{limit}_{stamp}"


if __name__ == "__main__":
    main()
