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
    )
    payload = asdict(summary)
    payload["baseline"] = baseline
    payload["run_dir"] = str(run_dir)
    payload["dashboard_path"] = str(dashboard_path)
    print(json.dumps(payload, indent=2))


def _default_run_id(environment: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_env = "".join(ch if ch.isalnum() else "_" for ch in environment)
    return f"{safe_env}_{stamp}"


def _run_no_helper_baseline(
    adapter: EnvironmentAdapter, *, limit: int | None
) -> dict[str, object]:
    """Run the same adapter task stream without generated helpers."""

    adapter.prepare()
    tasks = adapter.tasks(limit=limit)
    results: list[dict[str, object]] = []
    for task in tasks:
        result = adapter.run_task(task, {})
        results.append(_baseline_result_json(result))
    successes = sum(1 for result in results if result["success"])
    return {
        "policy": "no_generated_helpers",
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
