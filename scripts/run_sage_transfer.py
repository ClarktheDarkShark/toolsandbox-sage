#!/usr/bin/env python3
"""Run frozen-registry SAGE transfer evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/sage_transfer")
    )
    parser.parse_args()
    raise SystemExit("SAGE transfer evaluation requires the registry runtime first.")


if __name__ == "__main__":
    main()
