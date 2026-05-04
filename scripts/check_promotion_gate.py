#!/usr/bin/env python3
"""Check whether a candidate registry has enough evidence for promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.registry.promotion_gate import evaluate_registry_promotion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry")
    parser.add_argument("helper_contribution_summary")
    parser.add_argument("--failure-memory", type=Path)
    parser.add_argument(
        "--target-lifecycle",
        choices=("candidate", "active", "frozen"),
        default="active",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_registry_promotion(
        Path(args.registry),
        Path(args.helper_contribution_summary),
        failure_memory_path=args.failure_memory,
        target_lifecycle=args.target_lifecycle,
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if not result["allowed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
