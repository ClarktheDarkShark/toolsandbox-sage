"""Run low-cost standalone SAGE adapter smoke tests.

This script exercises the importable ``sage_agent`` package without spending
model tokens. It uses deterministic template generation with the model metadata
fixed to gpt-4o-mini, matching the low-cost policy for this development stage.
"""

from __future__ import annotations

import argparse
import json
import shutil
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
    CyberGymAdapter,
    MiniGridAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
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
from sage_agent.interfaces import (  # noqa: E402
    EnvironmentAdapter,
    HelperGenerator,
    TaskRunResult,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env",
        choices=("toolsandbox", "toolsandbox-probe", "cybergym", "minigrid"),
        required=True,
    )
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("artifacts/sage_standalone/smoke_registry"),
    )
    parser.add_argument(
        "--cybergym-repo",
        type=Path,
        default=Path("external/cybergym"),
    )
    parser.add_argument("--reset-registry", action="store_true")
    parser.add_argument("--toolsandbox-scenario", action="append", default=[])
    parser.add_argument("--cybergym-task-id", action="append", default=[])
    parser.add_argument(
        "--minigrid-env-id",
        action="append",
        default=[],
        help="MiniGrid env ID to include. Repeat to include multiple envs.",
    )
    parser.add_argument(
        "--minigrid-seeds",
        default="1,2,3,4,5",
        help="Comma-separated MiniGrid seeds or ranges, e.g. 1-14,21.",
    )
    parser.add_argument("--minigrid-max-steps", type=int, default=160)
    parser.add_argument("--llm-timeout", type=float, default=180.0)
    parser.add_argument(
        "--generator", choices=("template", "openai"), default="template"
    )
    parser.add_argument(
        "--baseline",
        choices=("smoke", "llm"),
        default="smoke",
        help="Baseline policy. llm uses gpt-4o-mini over visible task artifacts.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/sage_agent_standalone"),
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--dashboard-port", type=int, default=62630)
    parser.add_argument("--no-dashboard-open", action="store_true")
    args = parser.parse_args()

    if args.model != "gpt-4o-mini":
        raise SystemExit("This smoke script is intentionally capped to gpt-4o-mini.")
    if args.reset_registry and args.registry_dir.exists():
        shutil.rmtree(args.registry_dir)

    if args.env == "toolsandbox":
        adapter: EnvironmentAdapter = ToolSandboxMiniAdapter()
    elif args.env == "toolsandbox-probe":
        adapter = ToolSandboxScenarioProbeAdapter(
            scenario_names=tuple(args.toolsandbox_scenario)
        )
    elif args.env == "cybergym":
        adapter = CyberGymAdapter(
            repo_root=args.cybergym_repo,
            task_ids=tuple(args.cybergym_task_id),
        )
    else:
        adapter = MiniGridAdapter(
            env_ids=tuple(args.minigrid_env_id) or MiniGridAdapter.env_ids,
            seeds=tuple(_parse_int_ranges(args.minigrid_seeds)),
            max_steps=args.minigrid_max_steps,
        )

    if args.generator == "template":
        generator: HelperGenerator = TemplateHelperGenerator()
    else:
        generator = OpenAIHelperGenerator()
    run_metadata = _run_metadata(args, adapter)
    run_id = args.run_id or _default_run_id(args.env)
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    initial_dashboard = write_standalone_dashboard(
        _empty_summary(adapter.profile().name, args.model, args.registry_dir),
        run_dir,
        registry_path=args.registry_dir / "sage_registry.json",
        baseline={
            "policy": f"{args.baseline}_baseline_pending",
            "tasks_seen": 0,
            "tasks_succeeded": 0,
            "success_rate": 0.0,
            "results": [],
        },
        run_metadata={**run_metadata, "status": "running"},
    )
    if not args.no_dashboard_open:
        url = open_standalone_dashboard(initial_dashboard, port=args.dashboard_port)
        print(f"Dashboard opened at run start: {url}", flush=True)

    baseline = _run_baseline(adapter, args=args, limit=args.limit)
    agent = SAGEAgent(
        adapter=adapter,
        generator=generator,
        config=SAGEConfig(model=args.model, registry_dir=args.registry_dir),
    )
    summary = agent.run(limit=args.limit)
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
    payload["run_dir"] = str(run_dir)
    payload["dashboard_path"] = str(dashboard_path)
    print(json.dumps(payload, indent=2))


def _default_run_id(environment: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_env = "".join(ch if ch.isalnum() else "_" for ch in environment)
    return f"{safe_env}_{stamp}"


def _run_metadata(
    args: argparse.Namespace, adapter: EnvironmentAdapter
) -> dict[str, object]:
    """Describe whether this run is benchmark evidence or an adapter probe."""

    adapter.prepare()
    available_tasks = len(adapter.tasks(limit=None))
    base: dict[str, object] = {
        "requested_limit": args.limit,
        "available_tasks": available_tasks,
        "limit_satisfied": args.limit <= available_tasks,
    }
    if args.env == "minigrid":
        base.update(
            {
                "execution_mode": "official_minigrid_standalone_smoke",
                "benchmark_ready": False,
                "real_task_generator_used": True,
                "real_submission_server_used": False,
                "real_poc_verifier_used": False,
                "interpretation": (
                    "This run validates SAGE on official MiniGrid environments "
                    "using visible grid observations. It is a small integration "
                    "smoke, not a protected MiniGrid benchmark claim."
                ),
                "setup_notes": (
                    "The adapter exposes visible grid rows and pose fields, then "
                    "scores only by executing action names through MiniGrid.",
                ),
                "minigrid_env_ids": tuple(args.minigrid_env_id)
                or MiniGridAdapter.env_ids,
                "minigrid_seeds": tuple(_parse_int_ranges(args.minigrid_seeds)),
                "minigrid_max_steps": args.minigrid_max_steps,
                "llm_timeout_seconds": args.llm_timeout,
            }
        )
        return base

    if args.env != "cybergym":
        base.update(
            {
                "execution_mode": "standalone_adapter_smoke",
                "benchmark_ready": False,
                "real_task_generator_used": False,
                "real_submission_server_used": False,
                "real_poc_verifier_used": False,
                "interpretation": (
                    "This run validates standalone SAGE adapter lifecycle. "
                    "It is not protected benchmark evidence."
                ),
                "setup_notes": (
                    "The adapter exposes visible task inputs through the generic "
                    "SAGE interface.",
                ),
            }
        )
        return base

    repo_root = _resolve_path(args.cybergym_repo)
    data_candidates = (
        repo_root / "cybergym_data/data",
        ROOT / "cybergym_data/data",
    )
    server_data_candidates = (
        repo_root / "cybergym-server-data",
        ROOT / "cybergym-server-data",
    )
    data_dir_exists = any(path.exists() for path in data_candidates)
    server_data_dir_exists = any(path.exists() for path in server_data_candidates)
    notes = [
        "CyberGym Python source is present in the cloned external repository.",
        "This adapter currently uses CyberGym-shaped synthetic verifier outputs, not generated task directories.",
        "No CyberGym PoC submission server is launched by this smoke runner.",
        "No real PoC is generated, submitted, or verified.",
        "The public README lists 10 subset task IDs; a real 40-task run requires downloaded benchmark data and a real task selection source.",
    ]
    if not data_dir_exists:
        notes.append(
            "Missing cybergym_data/data; real CyberGym task generation is not available."
        )
    if not server_data_dir_exists:
        notes.append(
            "Missing cybergym-server-data; binary verifier/server data is not available."
        )
    if args.limit > available_tasks:
        notes.append(
            f"Requested {args.limit} tasks, but this probe adapter exposes only {available_tasks} tasks."
        )
    base.update(
        {
            "execution_mode": "cybergym_synthetic_probe",
            "benchmark_ready": False,
            "real_task_generator_used": False,
            "real_submission_server_used": False,
            "real_poc_verifier_used": False,
            "cybergym_data_dir_exists": data_dir_exists,
            "cybergym_server_data_dir_exists": server_data_dir_exists,
            "interpretation": (
                "This is a CyberGym-shaped SAGE integration smoke. It validates "
                "helper generation, routing, reuse, dashboards, and integrity "
                "checks, but it is not real CyberGym benchmark evidence."
            ),
            "setup_notes": tuple(notes),
        }
    )
    return base


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _run_no_helper_baseline(
    adapter: EnvironmentAdapter, *, limit: int | None
) -> dict[str, object]:
    """Run the same adapter task stream without generated helpers.

    This is a lifecycle baseline for standalone adapter smoke tests. It is not a
    ToolSandbox control baseline unless a concrete adapter marks it as such.
    """

    adapter.prepare()
    tasks = adapter.tasks(limit=limit)
    results: list[dict[str, object]] = []
    for task in tasks:
        result = adapter.run_task(task, {})
        results.append(_baseline_result_json(result))
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": "no_generated_helpers",
        "comparison_valid": False,
        "comparison_note": (
            "Standalone adapter smoke baseline only. This is not a benchmark "
            "control arm and must not be reported as ToolSandbox score lift."
        ),
        "tasks_seen": len(results),
        "tasks_succeeded": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "results": results,
    }


def _run_baseline(
    adapter: EnvironmentAdapter, *, args: argparse.Namespace, limit: int | None
) -> dict[str, object]:
    if args.baseline == "llm":
        if isinstance(adapter, MiniGridAdapter):
            return _run_minigrid_llm_baseline(
                adapter,
                limit=limit,
                model=str(args.model),
                timeout=float(args.llm_timeout),
            )
        raise SystemExit(f"--baseline llm is not implemented for env={args.env}")
    return _run_no_helper_baseline(adapter, limit=limit)


def _run_minigrid_llm_baseline(
    adapter: MiniGridAdapter, *, limit: int | None, model: str, timeout: float
) -> dict[str, object]:
    planner = OpenAIEnvironmentBaseline(model=model, timeout=timeout)
    adapter.prepare()
    results: list[dict[str, object]] = []
    for task in adapter.tasks(limit=limit):
        try:
            actions = planner.plan_minigrid_actions(task, max_steps=adapter.max_steps)
            result = adapter.run_action_sequence(
                task,
                actions,
                transcript_prefix=(
                    f"LLM baseline planned {len(actions)} actions: {actions[:20]}"
                ),
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
        results.append(_baseline_result_json(result))
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": f"llm_visible_artifact_baseline:{model}",
        "comparison_valid": True,
        "comparison_note": (
            "Basic LLM baseline over visible MiniGrid task artifacts. It receives "
            "the grid rows, start pose, goal, and allowed actions, then the adapter "
            "executes its action sequence in MiniGrid."
        ),
        "tasks_seen": len(results),
        "tasks_succeeded": successes,
        "success_rate": successes / len(results) if results else 0.0,
        "results": results,
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


def _parse_int_ranges(value: str) -> list[int]:
    parsed: list[int] = []
    for chunk in value.split(","):
        item = chunk.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            step = 1 if end >= start else -1
            parsed.extend(range(start, end + step, step))
        else:
            parsed.append(int(item))
    if not parsed:
        raise ValueError("at least one MiniGrid seed is required")
    return parsed


if __name__ == "__main__":
    main()
