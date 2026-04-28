#!/usr/bin/env python3
"""Run frozen-registry SAGE transfer evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.config.splits import load_split_names
from sage_ts.runtime.base_toolset import KNOWN_POLICIES, UPSTREAM_POLICY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--agent", default="gpt-5-mini")
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument(
        "--base-tool-policy",
        choices=KNOWN_POLICIES,
        default=UPSTREAM_POLICY,
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/sage_transfer")
    )
    args = parser.parse_args()

    scenario_names = tuple(load_split_names(args.manifest, args.split))
    output_directory = run_sage_with_registry(
        SageRunConfig(
            agent=args.agent,
            user=args.user,
            scenario_names=scenario_names,
            output_dir=args.output_dir,
            registry_dir=args.registry,
            run_type="sage_transfer",
            base_tool_policy=args.base_tool_policy,
        ),
        generator=None,
    )
    print(json.dumps({"output_directory": str(output_directory)}, indent=2))


if __name__ == "__main__":
    main()
