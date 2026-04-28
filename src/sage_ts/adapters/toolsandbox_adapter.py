"""Thin adapter around upstream ToolSandbox execution."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from tool_sandbox.cli import run_sandbox
from tool_sandbox.cli.utils import RoleImplType, resolve_scenarios
from tool_sandbox.common.tool_discovery import ToolBackend

DEFAULT_TOOL_BACKEND = cast(ToolBackend, ToolBackend.DEFAULT)


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


def run_toolsandbox(config: ToolSandboxRunConfig) -> None:
    write_run_manifest(config)
    name_to_scenario = resolve_scenarios(
        desired_scenario_names=list(config.scenario_names),
        preferred_tool_backend=DEFAULT_TOOL_BACKEND,
    )
    run_sandbox(
        agent_type=RoleImplType(config.agent),
        user_type=RoleImplType(config.user),
        name_to_scenario=name_to_scenario,
        processes=config.processes,
        output_base_dir=config.output_dir,
    )
