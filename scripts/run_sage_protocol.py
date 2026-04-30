#!/usr/bin/env python3
"""Run paired ToolSandbox SAGE mechanism/transfer/extended-reuse gates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import traceback
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any, cast

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.cache.openai_response_cache import (
    configure_response_cache_context,
    install_openai_response_cache,
    write_cache_artifacts,
)
from sage_ts.cache.openai_response_cache import (
    reset_metrics as reset_openai_response_cache_metrics,
)
from sage_ts.cache.openai_response_cache import (
    write_metrics as write_openai_response_cache_metrics,
)
from sage_ts.campaign.artifacts import (
    append_event,
    initialize_campaign,
    record_run,
    snapshot_registry,
    update_task,
)
from sage_ts.config.splits import load_split_names
from sage_ts.dashboard.exporters import open_dashboard, write_protocol_dashboard
from sage_ts.evaluation.run_metrics import compare_runs
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerator
from sage_ts.runtime.base_toolset import KNOWN_POLICIES, UPSTREAM_POLICY

MODES = ("mechanism_40", "transfer_40", "extended_reuse_100")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _arm_status_path(run_root: Path, arm: str) -> Path:
    return run_root / f"{arm}_arm_status.json"


def _write_arm_status(
    run_root: Path,
    arm: str,
    *,
    status: str,
    run_dir: Path | None = None,
    completed_count: int | None = None,
    scenario_count: int | None = None,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "arm": arm,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir)
    if completed_count is not None:
        payload["completed_count"] = completed_count
    if scenario_count is not None:
        payload["scenario_count"] = scenario_count
    if error is not None:
        payload["error"] = error
    _arm_status_path(run_root, arm).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _read_arm_status(run_root: Path, arm: str) -> dict[str, Any]:
    path = _arm_status_path(run_root, arm)
    if not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _latest_run_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _status_run_dir(run_root: Path, arm: str, root: Path) -> Path | None:
    status = _read_arm_status(run_root, arm)
    raw = status.get("run_dir")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.exists():
            return path
    return _latest_run_dir(root)


def _protocol_event(
    *,
    event: str,
    mode: str,
    run_root: Path,
    run_dir: Path,
    payload: dict[str, object],
    artifact_root: Path,
) -> None:
    append_event(
        event,
        {
            "mode": mode,
            "run_root": str(run_root),
            "run_dir": str(run_dir),
            **payload,
        },
        root=artifact_root,
    )


def _run_control_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    control_root = Path(params["control_root"])
    registry_dir = Path(params["registry_dir"])
    scenario_names = tuple(params["scenario_names"])
    response_cache_enabled = bool(params["response_cache_enabled"])
    _write_arm_status(
        run_root,
        "control",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:
        if response_cache_enabled:
            install_openai_response_cache(
                Path(params["openai_response_cache_dir"]),
                mode=str(params["cache_mode"]),
            )
        configure_response_cache_context(
            mode=str(params["mode"]),
            arm="control",
            agent=str(params["agent"]),
            user=str(params["user"]),
            base_tool_policy=str(params["base_tool_policy"]),
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=False,
            generation_model=str(params["generation_model"]),
            recurrence_threshold=int(params["recurrence_threshold"]),
            run_config_extra={"parallel_arms": True},
        )
        reset_openai_response_cache_metrics()

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            _write_arm_status(
                run_root,
                "control",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        def event_hook(event: str, run_dir: Path, payload: dict[str, object]) -> None:
            _protocol_event(
                event=event,
                mode=str(params["mode"]),
                run_root=run_root,
                run_dir=run_dir,
                payload=payload,
                artifact_root=artifact_root,
            )

        run_dir = run_toolsandbox(
            ToolSandboxRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=control_root,
                processes=1,
                run_type=f"{params['mode']}_control",
                base_tool_policy=str(params["base_tool_policy"]),
            ),
            progress_hook=progress,
            event_hook=event_hook,
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                run_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(run_root / "cache_artifacts" / "control")
        append_event(
            "phase_completed",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_dir": str(run_dir),
                "parallel_arms": True,
            },
            root=artifact_root,
        )
        _write_arm_status(
            run_root,
            "control",
            status="complete",
            run_dir=run_dir,
            completed_count=len(scenario_names),
            scenario_count=len(scenario_names),
        )
    except Exception:
        error = traceback.format_exc()
        _write_arm_status(run_root, "control", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _run_candidate_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    candidate_root = Path(params["candidate_root"])
    registry_dir = Path(params["registry_dir"])
    scenario_names = tuple(params["scenario_names"])
    generation_enabled = bool(params["generation_enabled"])
    response_cache_enabled = bool(params["response_cache_enabled"])
    _write_arm_status(
        run_root,
        "candidate",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:
        if response_cache_enabled:
            install_openai_response_cache(
                Path(params["openai_response_cache_dir"]),
                mode=str(params["cache_mode"]),
            )
        configure_response_cache_context(
            mode=str(params["mode"]),
            arm="candidate",
            agent=str(params["agent"]),
            user=str(params["user"]),
            base_tool_policy=str(params["base_tool_policy"]),
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=generation_enabled,
            generation_model=str(params["generation_model"]),
            recurrence_threshold=int(params["recurrence_threshold"]),
            run_config_extra={"parallel_arms": True},
        )
        reset_openai_response_cache_metrics()
        prompt_cache = PromptCache(Path(params["prompt_cache_dir"]))
        generator = (
            ToolGenerator(
                completer=OpenAIChatAdapter(model=str(params["generation_model"])),
                cache=prompt_cache,
            )
            if generation_enabled
            else None
        )

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            _write_arm_status(
                run_root,
                "candidate",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        def event_hook(event: str, run_dir: Path, payload: dict[str, object]) -> None:
            _protocol_event(
                event=event,
                mode=str(params["mode"]),
                run_root=run_root,
                run_dir=run_dir,
                payload=payload,
                artifact_root=artifact_root,
            )

        run_dir = run_sage_with_registry(
            SageRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=candidate_root,
                registry_dir=registry_dir,
                run_type=f"{params['mode']}_candidate",
                recurrence_threshold=int(params["recurrence_threshold"]),
                base_tool_policy=str(params["base_tool_policy"]),
            ),
            generator=generator,
            progress_hook=progress,
            event_hook=event_hook,
        )
        (run_dir / "prompt_cache_metrics.json").write_text(
            json.dumps(prompt_cache.metrics(), indent=2) + "\n",
            encoding="utf-8",
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                run_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(run_root / "cache_artifacts" / "candidate")
        _write_arm_status(
            run_root,
            "candidate",
            status="complete",
            run_dir=run_dir,
            completed_count=len(scenario_names),
            scenario_count=len(scenario_names),
        )
    except Exception:
        error = traceback.format_exc()
        _write_arm_status(run_root, "candidate", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "candidate",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _read_metrics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_parallel_cache_artifacts(
    *,
    artifact_root: Path,
    run_root: Path,
    cache_mode: str,
    control_cache_dir: Path,
    candidate_cache_dir: Path,
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> None:
    cache_root = artifact_root / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    metrics_by_arm = {
        "control": _read_metrics(
            control_dir / "openai_response_cache_metrics.json"
            if control_dir is not None
            else Path("")
        ),
        "candidate": _read_metrics(
            candidate_dir / "openai_response_cache_metrics.json"
            if candidate_dir is not None
            else Path("")
        ),
    }
    totals: dict[str, int] = {}
    for metrics in metrics_by_arm.values():
        for key, value in metrics.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    manifest = {
        "cache_mode": cache_mode,
        "parallel_arms": True,
        "parallel_cache_policy": "per_arm",
        "arm_cache_roots": {
            "control": str(control_cache_dir),
            "candidate": str(candidate_cache_dir),
        },
        "run_root": str(run_root),
        "combined_sqlite_path": str(cache_root / "openai_response_cache.sqlite"),
        "note": "Parallel paired runs keep per-arm SQLite caches to avoid cross-arm cache state and write-lock contention.",
    }
    stats = {
        "cache_mode": cache_mode,
        "parallel_arms": True,
        "control_evolve_cache_symmetry": cache_mode,
        "arms": metrics_by_arm,
        "totals": totals,
    }
    (cache_root / "cache_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (cache_root / "cache_stats.json").write_text(
        json.dumps(stats, indent=2) + "\n", encoding="utf-8"
    )
    event_parts: list[str] = []
    for arm in ("control", "candidate"):
        events_path = (
            run_root / "cache_artifacts" / arm / "cache" / "cache_events.jsonl"
        )
        if events_path.exists():
            event_parts.append(events_path.read_text(encoding="utf-8"))
    (cache_root / "cache_events.jsonl").write_text(
        "".join(event_parts), encoding="utf-8"
    )
    (cache_root / "openai_response_cache.sqlite").touch()
    for arm, source_root in (
        ("control", control_cache_dir),
        ("candidate", candidate_cache_dir),
    ):
        source = source_root / "openai_response_cache.sqlite"
        if source.exists():
            shutil.copy2(source, cache_root / f"{arm}_openai_response_cache.sqlite")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--agent", default="gpt-5-mini")
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument("--generation-model", default="gpt-5-mini")
    parser.add_argument("--recurrence-threshold", type=int, default=2)
    parser.add_argument(
        "--base-tool-policy",
        choices=KNOWN_POLICIES,
        default=UPSTREAM_POLICY,
    )
    parser.add_argument("--registry-dir", type=Path)
    parser.add_argument(
        "--prompt-cache-dir",
        type=Path,
        default=Path("outputs/prompt_cache"),
    )
    parser.add_argument(
        "-o",
        "--output-root",
        type=Path,
        default=Path("outputs/sage_protocol"),
    )
    parser.add_argument("--dashboard-port", type=int, default=5520)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--openai-response-cache-dir",
        type=Path,
        default=Path("outputs/openai_response_cache"),
    )
    parser.add_argument(
        "--cache-mode",
        choices=("off", "read_write", "read_only", "write_only"),
        default=os.environ.get("CACHE_MODE", "read_write"),
    )
    parser.add_argument("--disable-openai-response-cache", action="store_true")
    parser.add_argument(
        "--parallel-arms",
        action="store_true",
        help="Run the matched control and SAGE arms concurrently in isolated processes.",
    )
    args = parser.parse_args()

    scenario_names = tuple(load_split_names(args.manifest, args.mode))
    run_root = args.output_root / f"{args.mode}_{_timestamp()}"
    control_root = run_root / "control"
    candidate_root = run_root / "candidate"
    registry_dir = args.registry_dir or (run_root / "registry")
    control_dir: Path | None = None
    candidate_dir: Path | None = None
    generation_enabled = args.mode in {"mechanism_40", "extended_reuse_100"}
    initialize_campaign(root=args.artifact_root, phase=args.mode)
    append_event(
        "phase_started",
        {
            "mode": args.mode,
            "run_root": str(run_root),
            "scenario_count": len(scenario_names),
        },
        root=args.artifact_root,
    )
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "status": "running",
            "agent": args.agent,
            "generation_enabled": generation_enabled,
            "base_tool_policy": args.base_tool_policy,
            "scenario_count": len(scenario_names),
        },
        root=args.artifact_root,
    )
    dashboard_index = write_protocol_dashboard(
        run_root,
        mode=args.mode,
        status="running",
        phase="control",
        agent=args.agent,
        user=args.user,
        generation_enabled=generation_enabled,
        base_tool_policy=args.base_tool_policy,
        scenario_count=len(scenario_names),
        registry_dir=registry_dir,
        artifact_root=args.artifact_root,
    )
    should_open_dashboard = (
        not args.no_dashboard_open
        and os.environ.get("SAGE_TS_DASHBOARD_OPEN", "1") != "0"
    )
    dashboard_url = (
        open_dashboard(dashboard_index, port=args.dashboard_port)
        if should_open_dashboard
        else None
    )
    response_cache_enabled = (
        not args.disable_openai_response_cache and args.cache_mode != "off"
    )
    control_cache_dir = args.openai_response_cache_dir
    candidate_cache_dir = args.openai_response_cache_dir
    if args.parallel_arms:
        control_cache_dir = args.openai_response_cache_dir / "control"
        candidate_cache_dir = args.openai_response_cache_dir / "candidate"
    if response_cache_enabled and not args.parallel_arms:
        install_openai_response_cache(
            args.openai_response_cache_dir,
            mode=args.cache_mode,
        )

    def refresh_dashboard(phase: str, status: str) -> None:
        write_protocol_dashboard(
            run_root,
            mode=args.mode,
            status=status,
            phase=phase,
            agent=args.agent,
            user=args.user,
            generation_enabled=generation_enabled,
            base_tool_policy=args.base_tool_policy,
            scenario_count=len(scenario_names),
            control_dir=control_dir,
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            artifact_root=args.artifact_root,
        )

    def campaign_event(
        event: str,
        run_dir: Path,
        payload: dict[str, object],
    ) -> None:
        append_event(
            event,
            {
                "mode": args.mode,
                "run_root": str(run_root),
                "run_dir": str(run_dir),
                **payload,
            },
            root=args.artifact_root,
        )

    if args.parallel_arms:
        append_event(
            "subtask_started",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "parallel_cache_policy": "per_arm",
            },
            root=args.artifact_root,
        )
        base_params: dict[str, Any] = {
            "mode": args.mode,
            "run_root": str(run_root),
            "artifact_root": str(args.artifact_root),
            "agent": args.agent,
            "user": args.user,
            "generation_model": args.generation_model,
            "recurrence_threshold": args.recurrence_threshold,
            "base_tool_policy": args.base_tool_policy,
            "registry_dir": str(registry_dir),
            "scenario_names": list(scenario_names),
            "cache_mode": args.cache_mode,
            "response_cache_enabled": response_cache_enabled,
        }
        ctx = get_context("spawn")
        control_process = ctx.Process(
            target=_run_control_arm_worker,
            args=(
                {
                    **base_params,
                    "control_root": str(control_root),
                    "openai_response_cache_dir": str(control_cache_dir),
                },
            ),
            name="sage_ts_control_arm",
        )
        candidate_process = ctx.Process(
            target=_run_candidate_arm_worker,
            args=(
                {
                    **base_params,
                    "candidate_root": str(candidate_root),
                    "prompt_cache_dir": str(args.prompt_cache_dir),
                    "openai_response_cache_dir": str(candidate_cache_dir),
                    "generation_enabled": generation_enabled,
                },
            ),
            name="sage_ts_candidate_arm",
        )
        control_process.start()
        candidate_process.start()
        while control_process.is_alive() or candidate_process.is_alive():
            control_dir = _status_run_dir(run_root, "control", control_root)
            candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
            refresh_dashboard("parallel", "running")
            time.sleep(5)
        control_process.join()
        candidate_process.join()
        control_dir = _status_run_dir(run_root, "control", control_root)
        candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
        refresh_dashboard("parallel", "running")
        failed = {
            "control": control_process.exitcode,
            "candidate": candidate_process.exitcode,
        }
        if control_process.exitcode != 0 or candidate_process.exitcode != 0:
            append_event(
                "blocker_detected",
                {
                    "mode": args.mode,
                    "run_root": str(run_root),
                    "parallel_arms": True,
                    "exitcodes": failed,
                    "control_status": _read_arm_status(run_root, "control"),
                    "candidate_status": _read_arm_status(run_root, "candidate"),
                },
                root=args.artifact_root,
            )
            raise SystemExit(f"Parallel arm failure: {failed}")
        if control_dir is None or candidate_dir is None:
            raise SystemExit(
                "Parallel arms finished but run directories were not found"
            )
        if response_cache_enabled:
            _write_parallel_cache_artifacts(
                artifact_root=args.artifact_root,
                run_root=run_root,
                cache_mode=args.cache_mode,
                control_cache_dir=control_cache_dir,
                candidate_cache_dir=candidate_cache_dir,
                control_dir=control_dir,
                candidate_dir=candidate_dir,
            )
        append_event(
            "subtask_completed",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "control_dir": str(control_dir),
                "candidate_dir": str(candidate_dir),
            },
            root=args.artifact_root,
        )
    else:

        def control_progress(
            run_dir: Path,
            _rows: list[dict[str, object]],
            status: str,
            _scenario_count: int,
        ) -> None:
            nonlocal control_dir
            control_dir = run_dir
            refresh_dashboard("control", status)

        configure_response_cache_context(
            mode=args.mode,
            arm="control",
            agent=args.agent,
            user=args.user,
            base_tool_policy=args.base_tool_policy,
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=False,
            generation_model=args.generation_model,
            recurrence_threshold=args.recurrence_threshold,
        )
        reset_openai_response_cache_metrics()
        control_dir = run_toolsandbox(
            ToolSandboxRunConfig(
                agent=args.agent,
                user=args.user,
                scenario_names=scenario_names,
                output_dir=control_root,
                processes=1,
                run_type=f"{args.mode}_control",
                base_tool_policy=args.base_tool_policy,
            ),
            progress_hook=control_progress,
            event_hook=campaign_event,
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                control_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(args.artifact_root)
        append_event(
            "phase_completed",
            {"mode": args.mode, "phase": "control", "run_dir": str(control_dir)},
            root=args.artifact_root,
        )
        refresh_dashboard("candidate", "running")

        prompt_cache = PromptCache(args.prompt_cache_dir)
        generator = (
            ToolGenerator(
                completer=OpenAIChatAdapter(model=args.generation_model),
                cache=prompt_cache,
            )
            if generation_enabled
            else None
        )

        def candidate_progress(
            run_dir: Path,
            _rows: list[dict[str, object]],
            status: str,
            _scenario_count: int,
        ) -> None:
            nonlocal candidate_dir
            candidate_dir = run_dir
            refresh_dashboard("candidate", status)

        configure_response_cache_context(
            mode=args.mode,
            arm="candidate",
            agent=args.agent,
            user=args.user,
            base_tool_policy=args.base_tool_policy,
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=generation_enabled,
            generation_model=args.generation_model,
            recurrence_threshold=args.recurrence_threshold,
        )
        reset_openai_response_cache_metrics()
        candidate_dir = run_sage_with_registry(
            SageRunConfig(
                agent=args.agent,
                user=args.user,
                scenario_names=scenario_names,
                output_dir=candidate_root,
                registry_dir=registry_dir,
                run_type=f"{args.mode}_candidate",
                recurrence_threshold=args.recurrence_threshold,
                base_tool_policy=args.base_tool_policy,
            ),
            generator=generator,
            progress_hook=candidate_progress,
            event_hook=campaign_event,
        )
        (candidate_dir / "prompt_cache_metrics.json").write_text(
            json.dumps(prompt_cache.metrics(), indent=2) + "\n",
            encoding="utf-8",
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                candidate_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(args.artifact_root)
    comparison = compare_runs(control_dir, candidate_dir, registry_dir=registry_dir)
    comparison_path = run_root / "paired_comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    gate_event = (
        "gate_passed"
        if float(comparison.get("mean_similarity_delta", 0.0)) >= 0
        else "gate_failed"
    )
    append_event(
        gate_event,
        {
            "mode": args.mode,
            "run_root": str(run_root),
            "mean_similarity_delta": comparison.get("mean_similarity_delta"),
            "gain_count": comparison.get("gain_count"),
            "regression_count": comparison.get("regression_count"),
        },
        root=args.artifact_root,
    )
    append_event(
        "phase_completed",
        {"mode": args.mode, "phase": "comparison", "run_root": str(run_root)},
        root=args.artifact_root,
    )
    snapshot_registry(
        registry_dir, name=f"{args.mode}_{run_root.name}", root=args.artifact_root
    )
    if args.mode == "mechanism_40":
        update_task(
            "reproduce_clean_recency_birth", "completed", root=args.artifact_root
        )
    elif args.mode == "transfer_40":
        update_task("frozen_registry_transfer", "completed", root=args.artifact_root)
    refresh_dashboard("comparison", "complete")
    manifest = {
        "mode": args.mode,
        "agent": args.agent,
        "user": args.user,
        "generation_model": args.generation_model,
        "generation_enabled": generation_enabled,
        "base_tool_policy": args.base_tool_policy,
        "scenario_count": len(scenario_names),
        "control_dir": str(control_dir),
        "candidate_dir": str(candidate_dir),
        "registry_dir": str(registry_dir),
        "comparison_path": str(comparison_path),
        "dashboard_path": str(dashboard_index),
        "dashboard_url": dashboard_url,
        "parallel_arms": args.parallel_arms,
        "parallel_cache_policy": "per_arm" if args.parallel_arms else "shared_process",
        "openai_response_cache_enabled": response_cache_enabled,
        "openai_response_cache_mode": args.cache_mode,
        "openai_response_cache_dir": str(args.openai_response_cache_dir),
        "control_openai_response_cache_dir": str(control_cache_dir),
        "candidate_openai_response_cache_dir": str(candidate_cache_dir),
    }
    manifest_path = run_root / "protocol_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "status": "complete",
            "agent": args.agent,
            "generation_enabled": generation_enabled,
            "base_tool_policy": args.base_tool_policy,
            "scenario_count": len(scenario_names),
            "control_dir": str(control_dir),
            "candidate_dir": str(candidate_dir),
            "registry_dir": str(registry_dir),
            "comparison_path": str(comparison_path),
            "dashboard_path": str(dashboard_index),
            "dashboard_url": dashboard_url,
            "parallel_arms": args.parallel_arms,
            "mean_similarity_delta": comparison.get("mean_similarity_delta"),
        },
        root=args.artifact_root,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
