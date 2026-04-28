#!/usr/bin/env python3
"""Run the SAGE online lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.orchestration.toy_mechanism import run_toy_birth_reuse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split")
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

    status_path = args.output_dir / "sage_online_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "scaffold_only",
                "split": args.split or "",
                "manifest": str(args.manifest or ""),
                "generation_active": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    raise SystemExit("SAGE online generation is not implemented yet; scaffold written.")


if __name__ == "__main__":
    main()
