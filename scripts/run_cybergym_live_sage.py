"""Run a small real CyberGym submit.sh comparison for standalone SAGE."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sage_agent import SAGEAgent, SAGEConfig, SAGERunSummary  # noqa: E402
from sage_agent.adapters import (  # noqa: E402
    CyberGymLiveSubmitAdapter,
    CyberGymLiveTask,
)
from sage_agent.dashboard import (  # noqa: E402
    open_standalone_dashboard,
    write_standalone_dashboard,
)
from sage_agent.generators import TemplateHelperGenerator  # noqa: E402
from sage_agent.interfaces import EnvironmentAdapter, TaskRunResult  # noqa: E402

OFFICIAL_10 = (
    "arvo:47101",
    "arvo:3938",
    "arvo:24993",
    "arvo:1065",
    "arvo:10400",
    "arvo:368",
    "oss-fuzz:42535201",
    "oss-fuzz:42535468",
    "oss-fuzz:370689421",
    "oss-fuzz:385167047",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks-root",
        type=Path,
        default=Path("outputs/cybergym_live_sage/official10_level1/tasks"),
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("artifacts/cybergym_live_sage/official10_level1_registry"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/cybergym_live_sage"),
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--reset-registry", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--dashboard-port", type=int, default=62630)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument(
        "--ignore-missing-images",
        action="store_true",
        help=(
            "Include task dirs even if Docker images are not currently local. "
            "Use only when prior server-side submissions are cached."
        ),
    )
    args = parser.parse_args()

    if args.model != "gpt-4o-mini":
        raise SystemExit("Live smoke is capped to gpt-4o-mini.")
    if args.reset_registry and args.registry_dir.exists():
        shutil.rmtree(args.registry_dir)

    run_id = args.run_id or _default_run_id()
    run_dir = args.output_root / run_id
    run_metadata = {
        "execution_mode": "cybergym_live_level1_submit_vul",
        "benchmark_ready": False,
        "requested_limit": len(OFFICIAL_10),
        "available_tasks": 0,
        "limit_satisfied": False,
        "real_task_generator_used": True,
        "real_submission_server_used": True,
        "real_poc_verifier_used": True,
        "official_success_verification": False,
        "status": "running",
        "interpretation": (
            "Real CyberGym submit.sh smoke using generated Level 1 task dirs and "
            "the live local /submit-vul server. It is not a final CyberGym claim "
            "because fix-side re-verification was not run."
        ),
        "setup_notes": (
            "Dashboard is opened at run start; results populate as the run finishes.",
        ),
    }
    initial_dashboard = write_standalone_dashboard(
        _empty_summary("cybergym-live", args.model, args.registry_dir),
        run_dir,
        registry_path=args.registry_dir / "sage_registry.json",
        baseline={
            "policy": "fixed_four_byte_poc_pending",
            "tasks_seen": 0,
            "tasks_succeeded": 0,
            "success_rate": 0.0,
            "results": [],
        },
        run_metadata=run_metadata,
    )
    if not args.no_dashboard_open:
        url = open_standalone_dashboard(initial_dashboard, port=args.dashboard_port)
        print(f"Dashboard opened at run start: {url}", flush=True)

    runnable, skipped = _discover_runnable_tasks(
        args.tasks_root, ignore_missing_images=args.ignore_missing_images
    )
    adapter = CyberGymLiveSubmitAdapter(
        tasks_root=args.tasks_root,
        tasks_to_run=tuple(runnable),
        max_candidates=args.max_candidates,
    )
    baseline = _run_no_helper_baseline(adapter)
    agent = SAGEAgent(
        adapter=adapter,
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(model=args.model, registry_dir=args.registry_dir),
    )
    summary = agent.run()
    run_metadata = {
        "execution_mode": "cybergym_live_level1_submit_vul",
        "benchmark_ready": False,
        "requested_limit": len(OFFICIAL_10),
        "available_tasks": len(runnable),
        "limit_satisfied": len(runnable) == len(OFFICIAL_10),
        "real_task_generator_used": True,
        "real_submission_server_used": True,
        "real_poc_verifier_used": True,
        "official_success_verification": False,
        "status": "complete",
        "interpretation": (
            "Real CyberGym submit.sh smoke using generated Level 1 task dirs and "
            "the live local /submit-vul server. It is not a final CyberGym claim "
            "because fix-side re-verification was not run. Skipped tasks are "
            "reported separately if Docker infrastructure blocks them."
        ),
        "setup_notes": tuple(
            [
                "Task directories were generated from downloaded official dataset files.",
                "Task IDs are masked in submit.sh via CyberGym mask_map.json.",
                "Baseline uses one fixed four-byte PoC.",
                "SAGE may generate and reuse a side-effect-free candidate planner; submissions remain environment-side effects.",
            ]
            + [f"Skipped {item}" for item in skipped]
        ),
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
    payload["skipped"] = skipped
    payload["run_dir"] = str(run_dir)
    payload["dashboard_path"] = str(dashboard_path)
    (run_dir / "live_summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


def _discover_runnable_tasks(
    tasks_root: Path, *, ignore_missing_images: bool = False
) -> tuple[list[CyberGymLiveTask], list[str]]:
    runnable: list[CyberGymLiveTask] = []
    skipped: list[str] = []
    for index, task_id in enumerate(OFFICIAL_10, 1):
        task_dir = tasks_root / f"{index:02d}_{task_id.replace(':', '_')}"
        image = _vul_image(task_id)
        if not task_dir.exists():
            skipped.append(f"{task_id}: missing generated task dir")
            continue
        if not ignore_missing_images and not _docker_image_exists(image):
            skipped.append(f"{task_id}: missing Docker image {image}")
            continue
        runnable.append(
            CyberGymLiveTask(
                task_key=f"cybergym-live-{index:02d}",
                task_dir=task_dir,
                display_name=f"CyberGym live Level 1 task {index:02d}",
            )
        )
    return runnable, skipped


def _vul_image(task_id: str) -> str:
    family, sub_id = task_id.split(":", 1)
    if family == "arvo":
        return f"n132/arvo:{sub_id}-vul"
    return f"cybergym/oss-fuzz:{sub_id}-vul"


def _docker_image_exists(image: str) -> bool:
    return (
        subprocess.run(
            ["docker", "image", "inspect", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def _run_no_helper_baseline(adapter: EnvironmentAdapter) -> dict[str, object]:
    adapter.prepare()
    results: list[dict[str, object]] = []
    for task in adapter.tasks():
        result = adapter.run_task(task, {})
        results.append(_baseline_result_json(result))
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": "fixed_four_byte_poc",
        "tasks_seen": len(results),
        "tasks_succeeded": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "results": results,
    }


def _baseline_result_json(result: TaskRunResult) -> dict[str, object]:
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


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"official10_level1_live_{stamp}"


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


if __name__ == "__main__":
    main()
