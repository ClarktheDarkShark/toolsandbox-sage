"""Dashboard data exporters for ToolSandbox SAGE protocol runs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from sage_ts.campaign.artifacts import ARTIFACT_ROOT, read_jsonl
from sage_ts.dashboard.template import DASHBOARD_HTML
from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _campaign_payload(root: Path) -> dict[str, Any]:
    return {
        "status": _read_json(root / "campaign_status.json"),
        "task_plan": _read_json(root / "task_plan.json"),
        "run_index": _read_json(root / "run_index.json", {"runs": []}),
        "events": read_jsonl(root / "events" / "latest.jsonl")[-80:],
        "registry_snapshots": [
            str(path) for path in sorted((root / "registries").glob("*.json"))
        ]
        if (root / "registries").exists()
        else [],
    }


def _scenario_rows(run_dir: Path | None) -> list[dict[str, Any]]:
    if run_dir is None:
        return []
    summary = run_dir / "result_summary.json"
    live = run_dir / "live_result_summary.json"
    data = _read_json(summary if summary.exists() else live)
    return list(data.get("per_scenario_results", []))


def _trace_url(dashboard_dir: Path, run_dir: Path | None, scenario: str) -> str | None:
    if run_dir is None:
        return None
    pretty = run_dir / "trajectories" / scenario / "pretty_print.txt"
    if not pretty.exists():
        return None
    return os.path.relpath(pretty, dashboard_dir)


def _scenario_table(
    dashboard_dir: Path,
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> list[dict[str, Any]]:
    control = {str(row.get("name")): row for row in _scenario_rows(control_dir)}
    candidate = {str(row.get("name")): row for row in _scenario_rows(candidate_dir)}
    reuse_by_scenario: dict[str, set[str]] = {}
    if candidate_dir is not None:
        for event in _read_jsonl(candidate_dir / "reuse_events.jsonl"):
            scenario = str(event.get("scenario", ""))
            tool = str(event.get("tool_name", ""))
            if scenario and tool:
                reuse_by_scenario.setdefault(scenario, set()).add(tool)
    names = list(dict.fromkeys([*control.keys(), *candidate.keys()]))
    rows: list[dict[str, Any]] = []
    for name in names:
        c_row = control.get(name, {})
        s_row = candidate.get(name, {})
        c_score = float(c_row.get("similarity", 0.0)) if c_row else None
        s_score = float(s_row.get("similarity", 0.0)) if s_row else None
        delta = (
            (s_score - c_score) if c_score is not None and s_score is not None else None
        )
        status = (
            "gain"
            if delta is not None and delta > 0
            else "regression"
            if delta is not None and delta < 0
            else "preserved"
        )
        rows.append(
            {
                "scenario": name,
                "categories": c_row.get("categories") or s_row.get("categories") or [],
                "control_similarity": c_score,
                "candidate_similarity": s_score,
                "delta": delta,
                "status": status,
                "control_turns": c_row.get("turn_count"),
                "candidate_turns": s_row.get("turn_count"),
                "control_exception": c_row.get("exception_type"),
                "candidate_exception": s_row.get("exception_type"),
                "reused_tools": sorted(reuse_by_scenario.get(name, set())),
                "control_trace_url": _trace_url(dashboard_dir, control_dir, name),
                "candidate_trace_url": _trace_url(dashboard_dir, candidate_dir, name),
            }
        )
    return rows


def _partial_comparison(
    control_dir: Path | None,
    candidate_dir: Path | None,
    registry_dir: Path | None,
) -> dict[str, Any]:
    if control_dir is not None and candidate_dir is not None:
        return compare_runs(control_dir, candidate_dir, registry_dir=registry_dir)
    return {
        "control": summarize_run(control_dir) if control_dir is not None else {},
        "candidate": summarize_run(candidate_dir, registry_dir=registry_dir)
        if candidate_dir is not None
        else {},
        "scenario_count": 0,
        "mean_similarity_delta": 0.0,
        "gain_count": 0,
        "regression_count": 0,
        "preserved_count": 0,
        "gains": [],
        "regressions": [],
        "deltas": [],
    }


def write_protocol_dashboard(
    run_root: Path,
    *,
    mode: str,
    status: str,
    phase: str,
    agent: str,
    user: str,
    generation_enabled: bool,
    base_tool_policy: str,
    scenario_count: int,
    control_dir: Path | None = None,
    candidate_dir: Path | None = None,
    registry_dir: Path | None = None,
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    """Write dashboard HTML and data for a paired protocol run."""
    dashboard_dir = run_root / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    comparison = _partial_comparison(control_dir, candidate_dir, registry_dir)
    data = {
        "mode": mode,
        "status": status,
        "phase": phase,
        "agent": agent,
        "user": user,
        "generation_enabled": generation_enabled,
        "base_tool_policy": base_tool_policy,
        "scenario_count": scenario_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "control": comparison.get("control", {}),
        "candidate": comparison.get("candidate", {}),
        "comparison": {
            key: comparison.get(key)
            for key in ("gain_count", "regression_count", "preserved_count")
        },
        "mean_similarity_delta": comparison.get("mean_similarity_delta", 0.0),
        "scenarios": _scenario_table(dashboard_dir, control_dir, candidate_dir),
        "birth_events": _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
        if candidate_dir
        else [],
        "reuse_events": _read_jsonl(candidate_dir / "reuse_events.jsonl")
        if candidate_dir
        else [],
        "run_events": _read_jsonl(candidate_dir / "sage_run_events.jsonl")
        if candidate_dir
        else [],
        "campaign": _campaign_payload(artifact_root),
        "registry_manifest": _read_json(registry_dir / "registry_manifest.json")
        if registry_dir
        else {},
    }
    (dashboard_dir / "data.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "index.html").write_text(DASHBOARD_HTML, encoding="utf-8")
    _write_latest_pointer(dashboard_dir / "index.html")
    return dashboard_dir / "index.html"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dashboard_url(index_path: Path, *, port: int = 5520) -> str:
    rel = index_path.resolve().relative_to(_repo_root())
    return f"http://127.0.0.1:{port}/{quote(str(rel))}"


def ensure_dashboard_server(*, port: int = 5520) -> None:
    """Start a repo-root static file server if the dashboard port is unused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            return
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
        ],
        cwd=_repo_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_dashboard(index_path: Path, *, port: int = 5520) -> str:
    ensure_dashboard_server(port=port)
    url = dashboard_url(index_path, port=port)
    webbrowser.open(url)
    return url


def _write_latest_pointer(index_path: Path) -> None:
    latest_dir = _repo_root() / "outputs" / "dashboard"
    latest_dir.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(index_path, latest_dir)
    (latest_dir / "latest_sage_ts.html").write_text(
        f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={rel}">
<a href="{rel}">Open latest ToolSandbox SAGE dashboard</a>
""",
        encoding="utf-8",
    )
