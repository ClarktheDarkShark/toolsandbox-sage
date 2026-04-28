"""Thin adapter around upstream ToolSandbox execution."""

from __future__ import annotations

import json
import random
import subprocess
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import polars as pl
from tqdm import tqdm

from sage_ts.adapters.role_factory import make_agent, make_user
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY, apply_base_tool_policy
from tool_sandbox.cli import write_result_summary
from tool_sandbox.cli.utils import (
    get_category_summary,
    resolve_scenarios,
)
from tool_sandbox.common.execution_context import RoleType
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend
from tool_sandbox.roles.base_role import BaseRole
from tool_sandbox.roles.execution_environment import ExecutionEnvironment

DEFAULT_TOOL_BACKEND = ToolBackend("DEFAULT")
ScenarioTransform = Callable[[str, Scenario, Path], Scenario]
ResultHook = Callable[[str, Scenario, dict[str, Any], Path], Optional[dict[str, Any]]]
ProgressHook = Callable[[Path, list[dict[str, Any]], str, int], None]
EventHook = Callable[[str, Path, dict[str, Any]], None]


@dataclass(frozen=True)
class ToolSandboxRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    processes: int = 1
    run_type: str = "baseline"
    base_tool_policy: str = UPSTREAM_POLICY


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


def write_live_result_summary(
    *,
    output_directory: Path,
    result_summary: list[dict[str, Any]],
    status: str,
    scenario_count: int,
) -> Path:
    """Write a lightweight progress summary while ToolSandbox is still running."""
    path = output_directory / "live_result_summary.json"
    payload = {
        "status": status,
        "completed_count": len(result_summary),
        "scenario_count": scenario_count,
        "per_scenario_results": result_summary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
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
    roles: dict[RoleType, BaseRole] = {
        RoleType("USER"): make_user(user),
        RoleType("EXECUTION_ENVIRONMENT"): ExecutionEnvironment(),
        RoleType("AGENT"): make_agent(agent),
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
    result_hook: ResultHook | None = None,
    progress_hook: ProgressHook | None = None,
    event_hook: EventHook | None = None,
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
    write_live_result_summary(
        output_directory=output_directory,
        result_summary=result_summary,
        status="running",
        scenario_count=len(ordered_items),
    )
    if progress_hook is not None:
        progress_hook(output_directory, result_summary, "running", len(ordered_items))
    for name, scenario in tqdm(ordered_items, desc="Scenarios"):
        if event_hook is not None:
            event_hook(
                "scenario_started",
                output_directory,
                {
                    "scenario": name,
                    "run_type": config.run_type,
                    "completed_count": len(result_summary),
                    "scenario_count": len(ordered_items),
                },
            )
        base_scenario = apply_base_tool_policy(scenario, config.base_tool_policy)
        active_scenario = (
            scenario_transform(name, base_scenario, output_directory)
            if scenario_transform is not None
            else base_scenario
        )
        result = run_one_scenario(
            name,
            active_scenario,
            agent=config.agent,
            user=config.user,
            output_directory=output_directory,
        )
        if result_hook is not None:
            result = (
                result_hook(name, active_scenario, result, output_directory) or result
            )
        result_summary.append(result)
        if event_hook is not None:
            event_hook(
                "scenario_finished",
                output_directory,
                {
                    "scenario": name,
                    "run_type": config.run_type,
                    "similarity": result.get("similarity"),
                    "turn_count": result.get("turn_count"),
                    "exception_type": result.get("exception_type"),
                    "completed_count": len(result_summary),
                    "scenario_count": len(ordered_items),
                },
            )
        write_live_result_summary(
            output_directory=output_directory,
            result_summary=result_summary,
            status="running",
            scenario_count=len(ordered_items),
        )
        if progress_hook is not None:
            progress_hook(
                output_directory, result_summary, "running", len(ordered_items)
            )

    write_result_summary(
        result_summary=result_summary,
        category_summary=get_category_summary(result_summary),
        output_directory=output_directory,
    )
    write_live_result_summary(
        output_directory=output_directory,
        result_summary=result_summary,
        status="complete",
        scenario_count=len(ordered_items),
    )
    if progress_hook is not None:
        progress_hook(output_directory, result_summary, "complete", len(ordered_items))
    return output_directory


def run_toolsandbox(
    config: ToolSandboxRunConfig,
    *,
    progress_hook: ProgressHook | None = None,
    event_hook: EventHook | None = None,
) -> Path:
    if config.processes != 1:
        raise ValueError("SAGE-owned matched runs require processes=1 for fixed order")
    return run_scenario_sequence(
        config, progress_hook=progress_hook, event_hook=event_hook
    )
