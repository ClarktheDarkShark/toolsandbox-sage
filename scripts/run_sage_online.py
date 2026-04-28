#!/usr/bin/env python3
"""Run the SAGE online lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.config.splits import load_split_names
from sage_ts.orchestration.toy_mechanism import run_toy_birth_reuse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split")
    parser.add_argument("--agent", default="Unhelpful")
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument(
        "--registry-dir", type=Path, default=Path("outputs/sage_registry")
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/sage_online")
    )
    parser.add_argument(
        "--toy-mechanism",
        action="store_true",
        help="Run a controlled generated-tool birth/reuse smoke.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.toy_mechanism:
        result = run_toy_birth_reuse(args.output_dir)
        print(json.dumps(result, indent=2))
        return

    if args.manifest is None or args.split is None:
        raise SystemExit(
            "--manifest and --split are required unless --toy-mechanism is used"
        )

    scenario_names = tuple(load_split_names(args.manifest, args.split))
    output_directory = run_sage_with_registry(
        SageRunConfig(
            agent=args.agent,
            user=args.user,
            scenario_names=scenario_names,
            output_dir=args.output_dir,
            registry_dir=args.registry_dir,
        )
    )
    print(json.dumps({"output_directory": str(output_directory)}, indent=2))


if __name__ == "__main__":
    main()
