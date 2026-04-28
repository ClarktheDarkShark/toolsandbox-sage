#!/usr/bin/env python3
"""Run a fixed ToolSandbox split without SAGE generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
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
    args = parser.parse_args()

    scenario_names = tuple(load_split_names(args.manifest, args.split))
    run_toolsandbox(
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


if __name__ == "__main__":
    main()
