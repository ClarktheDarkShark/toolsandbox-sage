#!/usr/bin/env python3
"""Create deterministic ToolSandbox scenario split manifests."""

from __future__ import annotations

import argparse
from pathlib import Path

from sage_ts.config.splits import write_split_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/splits/tool_sandbox_splits.json"),
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    path = write_split_manifest(args.output, seed=args.seed)
    print(path)


if __name__ == "__main__":
    main()
