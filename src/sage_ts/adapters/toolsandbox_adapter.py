"""Thin adapter around upstream ToolSandbox execution."""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import polars as pl
from tqdm import tqdm

from sage_ts.adapters.role_factory import make_agent, make_user
from sage_ts.evaluation.outcome_score import compute_outcome_score
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
DEFAULT_TRANSIENT_SCENARIO_RETRY_ATTEMPTS = 3
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
    resume_from_dir: Path | None = None


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
        "resume_from_dir": str(config.resume_from_dir)
        if config.resume_from_dir
        else None,
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


def _resume_rows(resume_from_dir: Path | None) -> list[dict[str, Any]]:
    if resume_from_dir is None:
        return []
    for filename in ("result_summary.json", "live_result_summary.json"):
        path = resume_from_dir / filename
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        rows = payload.get("per_scenario_results")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _copy_resume_artifacts(
    resume_from_dir: Path | None, output_directory: Path
) -> None:
    if resume_from_dir is None or not resume_from_dir.exists():
        return
    trajectories = resume_from_dir / "trajectories"
    if trajectories.exists():
        shutil.copytree(
            trajectories,
            output_directory / "trajectories",
            dirs_exist_ok=True,
        )
    for path in resume_from_dir.glob("*.jsonl"):
        shutil.copy2(path, output_directory / path.name)


def _transient_scenario_retry_attempts() -> int:
    raw = os.environ.get("SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS", "")
    try:
        return max(1, int(raw)) if raw else DEFAULT_TRANSIENT_SCENARIO_RETRY_ATTEMPTS
    except ValueError:
        return DEFAULT_TRANSIENT_SCENARIO_RETRY_ATTEMPTS


def _is_transient_model_exception(exc: Exception, traceback_text: str) -> bool:
    names: set[str] = set()
    current: BaseException | None = exc
    while current is not None:
        names.add(type(current).__name__)
        current = current.__cause__ or current.__context__
    transient_names = {
        "APIConnectionError",
        "APITimeoutError",
        "APIStatusError",
        "InternalServerError",
        "RateLimitError",
        "RetryError",
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
    }
    if names & transient_names:
        return True
    transient_markers = (
        "openai.APIConnectionError",
        "openai.APITimeoutError",
        "Connection error.",
        "ReadTimeout",
        "ConnectTimeout",
        "RateLimitError",
        "RetryError[",
    )
    return any(marker in traceback_text for marker in transient_markers)


def _archive_transient_failed_trajectory(
    output_directory: Path,
    scenario_name: str,
    *,
    attempt: int,
) -> str | None:
    trajectory_dir = output_directory / "trajectories" / scenario_name
    if not trajectory_dir.exists():
        return None
    archive_base = (
        output_directory
        / "trajectories"
        / f"{scenario_name}__transient_retry_failed_attempt_{attempt}"
    )
    archive_dir = archive_base
    suffix = 2
    while archive_dir.exists():
        archive_dir = archive_base.with_name(f"{archive_base.name}_{suffix}")
        suffix += 1
    shutil.move(str(trajectory_dir), str(archive_dir))
    return str(archive_dir)


def run_one_scenario(
    name: str,
    scenario: Scenario,
    *,
    agent: str,
    user: str,
    output_directory: Path,
) -> dict[str, Any]:
    max_attempts = _transient_scenario_retry_attempts()
    transient_retry_archives: list[str] = []
    for attempt in range(1, max_attempts + 1):
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
            canonical_milestone_scores = {
                int(index): float(score)
                for index, (
                    _,
                    score,
                ) in result.evaluation_result.milestone_mapping.items()
            }
            outcome = compute_outcome_score(
                scenario,
                result.ending_context,
                canonical_milestone_scores=canonical_milestone_scores,
                minefield_similarity=result.evaluation_result.minefield_similarity,
            )
            return {
                "name": name,
                "categories": scenario.categories,
                "traceback": None,
                "exception_type": None,
                "transient_retry_count": attempt - 1,
                "transient_retry_archives": transient_retry_archives,
                "milestone_similarity": result.evaluation_result.milestone_similarity,
                "minefield_similarity": result.evaluation_result.minefield_similarity,
                "similarity": result.evaluation_result.similarity,
                "turn_count": result.evaluation_result.turn_count,
                "milestone_mapping": result.evaluation_result.milestone_mapping,
                "minefield_mapping": result.evaluation_result.minefield_mapping,
                **outcome,
            }
        except Exception as exc:
            traceback_text = traceback.format_exc()
            should_retry = attempt < max_attempts and _is_transient_model_exception(
                exc, traceback_text
            )
            if should_retry:
                archive = _archive_transient_failed_trajectory(
                    output_directory,
                    name,
                    attempt=attempt,
                )
                if archive:
                    transient_retry_archives.append(archive)
            else:
                return {
                    "name": name,
                    "categories": scenario.categories,
                    "traceback": traceback_text,
                    "exception_type": type(exc).__name__,
                    "transient_retry_count": attempt - 1,
                    "transient_retry_archives": transient_retry_archives,
                    "milestone_similarity": 0,
                    "minefield_similarity": 0,
                    "similarity": 0,
                    "turn_count": scenario.max_messages,
                    "milestone_mapping": {},
                    "minefield_mapping": {},
                    "outcome_similarity": 0,
                    "outcome_milestone_similarity": 0,
                    "outcome_minefield_similarity": 0,
                    "outcome_check_count": 0,
                    "outcome_checks": [],
                }
        finally:
            for role in roles.values():
                role.teardown()

    raise AssertionError("unreachable transient retry loop exit")


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
    _copy_resume_artifacts(config.resume_from_dir, output_directory)

    name_to_scenario = resolve_scenarios(
        desired_scenario_names=list(config.scenario_names),
        preferred_tool_backend=DEFAULT_TOOL_BACKEND,
    )
    prior_by_name = {
        str(row.get("name")): row
        for row in _resume_rows(config.resume_from_dir)
        if row.get("name") in set(config.scenario_names)
    }
    result_summary: list[dict[str, Any]] = [
        prior_by_name[name] for name in config.scenario_names if name in prior_by_name
    ]
    ordered_items = [
        (name, name_to_scenario[name])
        for name in config.scenario_names
        if name not in prior_by_name
    ]
    write_live_result_summary(
        output_directory=output_directory,
        result_summary=result_summary,
        status="running",
        scenario_count=len(config.scenario_names),
    )
    if progress_hook is not None:
        progress_hook(
            output_directory,
            result_summary,
            "running",
            len(config.scenario_names),
        )
    final_status = "complete"
    for name, scenario in tqdm(ordered_items, desc="Scenarios"):
        os.environ["SAGE_TS_CURRENT_SCENARIO"] = name
        os.environ["SAGE_TS_SCENARIO_ORDER_INDEX"] = str(len(result_summary))
        if event_hook is not None:
            event_hook(
                "scenario_started",
                output_directory,
                {
                    "scenario": name,
                    "run_type": config.run_type,
                    "completed_count": len(result_summary),
                    "scenario_count": len(config.scenario_names),
                },
            )
        (output_directory / "currently_running.json").write_text(
            json.dumps(
                {
                    "scenario": name,
                    "completed_count": len(result_summary),
                    "scenario_count": len(config.scenario_names),
                }
            ),
            encoding="utf-8",
        )
        base_scenario = apply_base_tool_policy(scenario, config.base_tool_policy)
        active_scenario = base_scenario
        if scenario_transform is not None:
            try:
                active_scenario = scenario_transform(
                    name,
                    base_scenario,
                    output_directory,
                )
            except Exception:
                if event_hook is not None:
                    event_hook(
                        "scenario_transform_failed",
                        output_directory,
                        {
                            "scenario": name,
                            "error": traceback.format_exc(),
                        },
                    )
        result = run_one_scenario(
            name,
            active_scenario,
            agent=config.agent,
            user=config.user,
            output_directory=output_directory,
        )
        _p = output_directory / "currently_running.json"
        if _p.exists():
            _p.unlink()
        if result_hook is not None:
            result = (
                result_hook(name, active_scenario, result, output_directory) or result
            )
        stop_requested = bool(result.pop("_sage_stop_run", False))
        stop_reason = result.pop("_sage_stop_reason", None)
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
                    "scenario_count": len(config.scenario_names),
                    "stop_requested": stop_requested,
                    "stop_reason": stop_reason,
                },
            )
        write_live_result_summary(
            output_directory=output_directory,
            result_summary=result_summary,
            status="running",
            scenario_count=len(config.scenario_names),
        )
        if progress_hook is not None:
            progress_hook(
                output_directory,
                result_summary,
                "running",
                len(config.scenario_names),
            )
        if stop_requested:
            final_status = "stopped_early"
            if event_hook is not None:
                event_hook(
                    "run_stopped_early",
                    output_directory,
                    {
                        "scenario": name,
                        "run_type": config.run_type,
                        "completed_count": len(result_summary),
                        "scenario_count": len(config.scenario_names),
                        "reason": stop_reason,
                    },
                )
            break

    write_result_summary(
        result_summary=result_summary,
        category_summary=get_category_summary(result_summary),
        output_directory=output_directory,
    )
    write_live_result_summary(
        output_directory=output_directory,
        result_summary=result_summary,
        status=final_status,
        scenario_count=len(config.scenario_names),
    )
    if progress_hook is not None:
        progress_hook(
            output_directory,
            result_summary,
            final_status,
            len(config.scenario_names),
        )
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
