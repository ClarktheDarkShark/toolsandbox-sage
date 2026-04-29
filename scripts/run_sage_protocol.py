#!/usr/bin/env python3
"""Run paired ToolSandbox SAGE mechanism/transfer/extended-reuse gates."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.cache.openai_response_cache import (
    configure_response_cache_context,
    install_openai_response_cache,
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
    parser.add_argument("--disable-openai-response-cache", action="store_true")
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
    response_cache_enabled = not args.disable_openai_response_cache
    if response_cache_enabled:
        install_openai_response_cache(args.openai_response_cache_dir)

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
        "openai_response_cache_enabled": response_cache_enabled,
        "openai_response_cache_dir": str(args.openai_response_cache_dir),
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
            "mean_similarity_delta": comparison.get("mean_similarity_delta"),
        },
        root=args.artifact_root,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
