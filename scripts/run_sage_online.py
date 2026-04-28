#!/usr/bin/env python3
"""Run the SAGE online lane.

This is intentionally a scaffold until the SAGE tool-generation loop is added.
It preserves the fixed-split interface and records that generation is not yet active.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/sage_online")
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = args.output_dir / "sage_online_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "scaffold_only",
                "split": args.split,
                "manifest": str(args.manifest),
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
