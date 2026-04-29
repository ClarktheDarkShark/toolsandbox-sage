#!/usr/bin/env python3
"""Run a fixed ToolSandbox split without SAGE generation."""

from __future__ import annotations

import argparse
from pathlib import Path

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
from sage_ts.config.splits import load_split_names
from sage_ts.runtime.base_toolset import KNOWN_POLICIES, UPSTREAM_POLICY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--agent", default="Unhelpful")
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument(
        "--base-tool-policy",
        choices=KNOWN_POLICIES,
        default=UPSTREAM_POLICY,
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/baseline")
    )
    parser.add_argument(
        "--openai-response-cache-dir",
        type=Path,
        default=Path("outputs/openai_response_cache"),
    )
    parser.add_argument(
        "--cache-mode",
        choices=("off", "read_write", "read_only", "write_only"),
        default="read_write",
    )
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--disable-openai-response-cache", action="store_true")
    args = parser.parse_args()

    scenario_names = tuple(load_split_names(args.manifest, args.split))
    response_cache_enabled = (
        not args.disable_openai_response_cache and args.cache_mode != "off"
    )
    if response_cache_enabled:
        install_openai_response_cache(
            args.openai_response_cache_dir,
            mode=args.cache_mode,
        )
    configure_response_cache_context(
        mode=f"baseline:{args.split}",
        arm="control",
        agent=args.agent,
        user=args.user,
        base_tool_policy=args.base_tool_policy,
        scenario_names=scenario_names,
        registry_dir=None,
        generation_enabled=False,
        generation_model=None,
        recurrence_threshold=None,
    )
    reset_openai_response_cache_metrics()
    output_directory = run_toolsandbox(
        ToolSandboxRunConfig(
            agent=args.agent,
            user=args.user,
            scenario_names=scenario_names,
            output_dir=args.output_dir,
            processes=args.processes,
            run_type="baseline",
            base_tool_policy=args.base_tool_policy,
        )
    )
    if response_cache_enabled:
        write_openai_response_cache_metrics(
            output_directory / "openai_response_cache_metrics.json"
        )
        write_cache_artifacts(args.artifact_root)


if __name__ == "__main__":
    main()
