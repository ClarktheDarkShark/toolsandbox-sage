"""ToolSandbox runner with accepted SAGE registry tools injected."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    ToolSandboxRunConfig,
    run_scenario_sequence,
)
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.toolsandbox_integration import with_registry_tools
from tool_sandbox.common.scenario import Scenario


@dataclass(frozen=True)
class SageRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    registry_dir: Path
    run_type: str = "sage_online"


def run_sage_with_registry(config: SageRunConfig) -> Path:
    """Run ToolSandbox scenarios with accepted generated tools available."""
    store = RegistryStore(config.registry_dir)
    registry_tools = sorted(store.load_entries())

    def transform(name: str, scenario: Scenario, output_directory: Path) -> Scenario:
        def record_reuse(tool_name: str) -> None:
            store.record_reuse(tool_name)
            append_jsonl(
                output_directory / "reuse_events.jsonl",
                {
                    "scenario": name,
                    "tool_name": tool_name,
                    "event": "generated_tool_invoked",
                },
            )

        return with_registry_tools(scenario, store, on_reuse=record_reuse)

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent=config.agent,
            user=config.user,
            scenario_names=config.scenario_names,
            output_dir=config.output_dir,
            processes=1,
            run_type=config.run_type,
        ),
        scenario_transform=transform,
    )
    append_jsonl(
        output_directory / "sage_run_events.jsonl",
        {
            "event": "run_finished",
            "registry_dir": str(config.registry_dir),
            "registry_tools": registry_tools,
        },
    )
    return output_directory
