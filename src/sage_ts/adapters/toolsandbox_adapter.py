"""Thin adapter around upstream ToolSandbox execution."""

from __future__ import annotations

import json
import random
import subprocess
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import polars as pl
from tqdm import tqdm

from sage_ts.adapters.role_factory import make_agent, make_user
from tool_sandbox.cli import write_result_summary
from tool_sandbox.cli.utils import (
    get_category_summary,
    resolve_scenarios,
)
from tool_sandbox.common.execution_context import RoleType
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend
from tool_sandbox.roles.execution_environment import ExecutionEnvironment

DEFAULT_TOOL_BACKEND = ToolBackend.DEFAULT
ScenarioTransform = Callable[[str, Scenario, Path], Scenario]


@dataclass(frozen=True)
class ToolSandboxRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    processes: int = 1
    run_type: str = "baseline"


def git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        return None


def write_run_manifest(config: ToolSandboxRunConfig) -> Path:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    path = config.output_dir / "sage_ts_run_manifest.json"
    payload: dict[str, Any] = {
        **asdict(config),
        "output_dir": str(config.output_dir),
        "scenario_names": list(config.scenario_names),
        "git_sha": git_sha(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _output_directory(config: ToolSandboxRunConfig) -> Path:
    return (
        Path(config.output_dir)
        / f"{config.run_type}_agent_{config.agent}_user_{config.user}_"
        f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}"
    )


def run_one_scenario(
    name: str,
    scenario: Scenario,
    *,
    agent: str,
    user: str,
    output_directory: Path,
) -> dict[str, Any]:
    roles = {
        RoleType.USER: make_user(user),
        RoleType.EXECUTION_ENVIRONMENT: ExecutionEnvironment(),
        RoleType.AGENT: make_agent(agent),
    }
    try:
        result = scenario.play_and_evaluate(
            roles=roles,
            output_directory=output_directory,
            scenario_name=name,
        )
        return {
            "name": name,
            "categories": scenario.categories,
            "traceback": None,
            "exception_type": None,
            "milestone_similarity": result.evaluation_result.milestone_similarity,
            "minefield_similarity": result.evaluation_result.minefield_similarity,
            "similarity": result.evaluation_result.similarity,
            "turn_count": result.evaluation_result.turn_count,
            "milestone_mapping": result.evaluation_result.milestone_mapping,
            "minefield_mapping": result.evaluation_result.minefield_mapping,
        }
    except Exception as exc:
        return {
            "name": name,
            "categories": scenario.categories,
            "traceback": traceback.format_exc(),
            "exception_type": type(exc).__name__,
            "milestone_similarity": 0,
            "minefield_similarity": 0,
            "similarity": 0,
            "turn_count": scenario.max_messages,
            "milestone_mapping": {},
            "minefield_mapping": {},
        }
    finally:
        for role in roles.values():
            role.teardown()


def run_scenario_sequence(
    config: ToolSandboxRunConfig,
    *,
    scenario_transform: ScenarioTransform | None = None,
) -> Path:
    """Run scenarios in manifest order and write upstream-compatible summaries."""
    random.seed(42)
    pl.Config.set_tbl_rows(-1).set_tbl_cols(-1).set_fmt_str_lengths(10000)
    pl.Config.set_tbl_formatting("ASCII_FULL")
    write_run_manifest(config)
    output_directory = _output_directory(config)
    output_directory.mkdir(parents=True, exist_ok=True)

    name_to_scenario = resolve_scenarios(
        desired_scenario_names=list(config.scenario_names),
        preferred_tool_backend=DEFAULT_TOOL_BACKEND,
    )
    ordered_items = [(name, name_to_scenario[name]) for name in config.scenario_names]
    result_summary: list[dict[str, Any]] = []
    for name, scenario in tqdm(ordered_items, desc="Scenarios"):
        active_scenario = (
            scenario_transform(name, scenario, output_directory)
            if scenario_transform is not None
            else scenario
        )
        result_summary.append(
            run_one_scenario(
                name,
                active_scenario,
                agent=config.agent,
                user=config.user,
                output_directory=output_directory,
            )
        )

    write_result_summary(
        result_summary=result_summary,
        category_summary=get_category_summary(result_summary),
        output_directory=output_directory,
    )
    return output_directory


def run_toolsandbox(config: ToolSandboxRunConfig) -> Path:
    if config.processes != 1:
        raise ValueError("SAGE-owned matched runs require processes=1 for fixed order")
    return run_scenario_sequence(config)
