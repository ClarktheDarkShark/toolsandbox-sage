#!/usr/bin/env python3
"""Export dashboard-ready JSON from ToolSandbox result artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.dashboard.exporters import write_protocol_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_summary", type=Path, nargs="?")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--protocol-run-root", type=Path)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    if args.protocol_run_root is not None:
        manifest = json.loads(
            (args.protocol_run_root / "protocol_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        path = write_protocol_dashboard(
            args.protocol_run_root,
            mode=str(manifest["mode"]),
            status="complete",
            phase="comparison",
            agent=str(manifest["agent"]),
            user=str(manifest["user"]),
            generation_enabled=bool(manifest["generation_enabled"]),
            base_tool_policy=str(manifest["base_tool_policy"]),
            scenario_count=int(manifest["scenario_count"]),
            control_dir=Path(manifest["control_dir"]),
            candidate_dir=Path(manifest["candidate_dir"]),
            registry_dir=Path(manifest["registry_dir"]),
            model_metadata=manifest.get("model_metadata"),
            artifact_root=args.artifact_root,
        )
        print(path)
        return
    if args.result_summary is None or args.output is None:
        parser.error(
            "result_summary and --output are required without --protocol-run-root"
        )

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
