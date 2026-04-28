#!/usr/bin/env python3
"""Run paired ToolSandbox SAGE mechanism/transfer/extended-reuse gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.config.splits import load_split_names
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
    args = parser.parse_args()

    scenario_names = tuple(load_split_names(args.manifest, args.mode))
    run_root = args.output_root / f"{args.mode}_{_timestamp()}"
    control_root = run_root / "control"
    candidate_root = run_root / "candidate"
    registry_dir = args.registry_dir or (run_root / "registry")

    control_dir = run_toolsandbox(
        ToolSandboxRunConfig(
            agent=args.agent,
            user=args.user,
            scenario_names=scenario_names,
            output_dir=control_root,
            processes=1,
            run_type=f"{args.mode}_control",
            base_tool_policy=args.base_tool_policy,
        )
    )

    generation_enabled = args.mode in {"mechanism_40", "extended_reuse_100"}
    prompt_cache = PromptCache(args.prompt_cache_dir)
    generator = (
        ToolGenerator(
            completer=OpenAIChatAdapter(model=args.generation_model),
            cache=prompt_cache,
        )
        if generation_enabled
        else None
    )
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
    )
    (candidate_dir / "prompt_cache_metrics.json").write_text(
        json.dumps(prompt_cache.metrics(), indent=2) + "\n",
        encoding="utf-8",
    )
    comparison = compare_runs(control_dir, candidate_dir, registry_dir=registry_dir)
    comparison_path = run_root / "paired_comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
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
    }
    manifest_path = run_root / "protocol_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
