"""Run live CyberGym standalone SAGE in bounded download/image batches."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
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
from sage_agent.dashboard import write_standalone_dashboard  # noqa: E402
from sage_agent.generators import (  # noqa: E402
    OpenAIHelperGenerator,
    TemplateHelperGenerator,
)
from sage_agent.interfaces import EnvironmentAdapter, TaskRunResult  # noqa: E402

DATASET_REPO = "sunblaze-ucb/cybergym"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks-json", type=Path, default=Path("cybergym_data/tasks.json")
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--difficulty", default="level1")
    parser.add_argument("--server", default="http://127.0.0.1:8666")
    parser.add_argument("--start-server", action="store_true", default=True)
    parser.add_argument("--no-start-server", action="store_false", dest="start_server")
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--model", default="gpt-4o-mini")
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
        default=Path("outputs/cybergym_live_sage/batched_work"),
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--reset-registry", action="store_true")
    parser.add_argument("--clear-images", action="store_true", default=True)
    parser.add_argument("--no-clear-images", action="store_false", dest="clear_images")
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()

    if args.model != "gpt-4o-mini":
        raise SystemExit("CyberGym batched smoke is capped to gpt-4o-mini.")
    if args.reset_registry and args.registry_dir.exists():
        shutil.rmtree(args.registry_dir)

    tasks = _select_tasks(args.tasks_json, limit=args.limit, difficulty=args.difficulty)
    run_id = args.run_id or _default_run_id(args.limit)
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    server_proc = _ensure_server(args.server, run_dir) if args.start_server else None
    try:
        summary, baseline, batch_reports = _run_batches(args, tasks)
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()

    run_metadata = {
        "execution_mode": "cybergym_live_level1_submit_vul_batched",
        "benchmark_ready": False,
        "requested_limit": args.limit,
        "available_tasks": len(tasks),
        "limit_satisfied": len(tasks) == args.limit,
        "batch_size": args.batch_size,
        "real_task_generator_used": True,
        "real_submission_server_used": True,
        "real_poc_verifier_used": True,
        "official_success_verification": False,
        "interpretation": (
            "Real CyberGym submit.sh smoke using generated Level 1 task dirs in "
            "bounded batches. This confirms environment wiring and SAGE lifecycle "
            "on live CyberGym submission, but it is not final CyberGym benchmark "
            "evidence because fix-side verification is not run."
        ),
        "setup_notes": (
            "Only level1 visible assets are downloaded: repo-vul.tar.gz and description.txt.",
            "Batch work directories and Docker images are cleared after each batch unless requested otherwise.",
            "SAGE starts from the supplied registry; use --reset-registry for an empty generated-tool registry.",
            "Submissions remain environment-side effects; generated helpers only prepare candidate strings.",
        ),
        "batch_reports": batch_reports,
    }
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


def _select_tasks(
    tasks_json: Path, *, limit: int, difficulty: str
) -> list[dict[str, Any]]:
    tasks = json.loads(tasks_json.read_text(encoding="utf-8"))
    selected = []
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id.startswith(("arvo:", "oss-fuzz:")):
            continue
        files = task.get("task_difficulty", {}).get(difficulty)
        if not files:
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
    cmd = [
        sys.executable,
        "-m",
        "cybergym.server",
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
    args: argparse.Namespace, tasks: list[dict[str, Any]]
) -> tuple[SAGERunSummary, dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    baseline_results: list[dict[str, Any]] = []
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
        skipped: list[str] = []
        try:
            for local_index, task in enumerate(batch, 1):
                task_id = str(task["task_id"])
                try:
                    _download_visible_assets(task, args.difficulty, data_root)
                    _generate_task_dir(
                        task_id,
                        task_root / _task_dir_name(local_index, task_id),
                        data_root,
                        args.server,
                        args.difficulty,
                    )
                    image = _vul_image(task_id)
                    images.append(image)
                    _pull_image(image)
                except Exception as exc:
                    skipped.append(f"{task_id}: {type(exc).__name__}: {exc}")
            live_tasks = _live_tasks_for_batch(batch, task_root, skipped)
            adapter = CyberGymLiveSubmitAdapter(
                tasks_root=task_root,
                tasks_to_run=tuple(live_tasks),
                max_candidates=args.max_candidates,
            )
            baseline = _run_no_helper_baseline(adapter)
            baseline_results.extend(baseline["results"])
            agent = SAGEAgent(
                adapter=adapter,
                generator=_helper_generator(args.generator),
                config=SAGEConfig(
                    model=args.model,
                    registry_dir=args.registry_dir,
                    max_new_tools=6,
                    max_refinements=2,
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
                }
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
    summary = SAGERunSummary(
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
    baseline_successes = sum(1 for result in baseline_results if result["success"])
    baseline = {
        "policy": "fixed_four_byte_poc_batched",
        "comparison_valid": True,
        "tasks_seen": len(baseline_results),
        "tasks_succeeded": baseline_successes,
        "success_rate": baseline_successes / len(baseline_results)
        if baseline_results
        else 0.0,
        "results": baseline_results,
    }
    return summary, baseline, batch_reports


def _helper_generator(name: str) -> TemplateHelperGenerator | OpenAIHelperGenerator:
    if name == "openai":
        return OpenAIHelperGenerator()
    return TemplateHelperGenerator()


def _download_visible_assets(
    task: dict[str, Any], difficulty: str, data_root: Path
) -> None:
    from huggingface_hub import hf_hub_download

    files = task.get("task_difficulty", {}).get(difficulty, [])
    for filename in files:
        if not (
            filename.endswith("repo-vul.tar.gz") or filename.endswith("description.txt")
        ):
            continue
        hf_hub_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            filename=str(filename),
            local_dir=data_root,
            cache_dir=ROOT / "cybergym_data/.cache/huggingface",
        )


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


def _pull_image(image: str) -> None:
    subprocess.run(["docker", "pull", image], check=True, timeout=1800)


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


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _default_run_id(limit: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"batched_live_level1_{limit}_{stamp}"


if __name__ == "__main__":
    main()
