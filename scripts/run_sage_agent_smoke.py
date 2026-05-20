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
from sage_agent.generators import (  # noqa: E402
    OpenAIHelperGenerator,
    TemplateHelperGenerator,
)
from sage_agent.interfaces import EnvironmentAdapter, HelperGenerator  # noqa: E402


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
    agent = SAGEAgent(
        adapter=adapter,
        generator=generator,
        config=SAGEConfig(model=args.model, registry_dir=args.registry_dir),
    )
    summary = agent.run(limit=args.limit)
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
