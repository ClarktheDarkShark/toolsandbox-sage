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

from sage_agent import SAGEAgent, SAGEConfig  # noqa: E402
from sage_agent.adapters import (  # noqa: E402
    CyberGymAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
)
from sage_agent.dashboard import write_standalone_dashboard  # noqa: E402
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
        choices=("toolsandbox", "toolsandbox-probe", "cybergym"),
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
        "--generator", choices=("template", "openai"), default="template"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/sage_agent_standalone"),
    )
    parser.add_argument("--run-id", default="")
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
    else:
        adapter = CyberGymAdapter(
            repo_root=args.cybergym_repo,
            task_ids=tuple(args.cybergym_task_id),
        )

    if args.generator == "template":
        generator: HelperGenerator = TemplateHelperGenerator()
    else:
        generator = OpenAIHelperGenerator()
    run_metadata = _run_metadata(args, adapter)
    baseline = _run_no_helper_baseline(adapter, limit=args.limit)
    agent = SAGEAgent(
        adapter=adapter,
        generator=generator,
        config=SAGEConfig(model=args.model, registry_dir=args.registry_dir),
    )
    summary = agent.run(limit=args.limit)
    run_id = args.run_id or _default_run_id(args.env)
    run_dir = args.output_root / run_id
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


def _baseline_result_json(result: TaskRunResult) -> dict[str, object]:
    return {
        "task_id": result.task.task_id,
        "name": result.task.name,
        "success": result.success,
        "score": result.score,
        "outcome_score": result.outcome_score,
        "error": result.error,
        "transcript": list(result.transcript),
    }


if __name__ == "__main__":
    main()
