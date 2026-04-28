#!/usr/bin/env python3
"""Export dashboard-ready JSON from ToolSandbox result artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_summary", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.result_summary.read_text(encoding="utf-8"))
    rows = data.get("per_scenario_results", [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "scenario_count": len(rows),
                "mean_similarity": (
                    sum(float(row.get("similarity", 0.0)) for row in rows) / len(rows)
                    if rows
                    else 0.0
                ),
                "scenarios": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
