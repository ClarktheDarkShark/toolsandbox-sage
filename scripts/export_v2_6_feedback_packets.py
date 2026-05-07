#!/usr/bin/env python3
"""Export V2.6 task feedback packets from completed paired protocol runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.evaluation.feedback_packets import write_feedback_packets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        action="append",
        required=True,
        help="Completed paired protocol run root containing control/ and candidate/ arms.",
    )
    parser.add_argument(
        "--output-root",
        default="artifacts/summaries/v2_6_feedback_packets",
        help="Directory where <run_id>/task_feedback.jsonl will be written.",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        help="Optional run id override. Provide once per --run-root if used.",
    )
    args = parser.parse_args()

    roots = [Path(value) for value in args.run_root]
    run_ids = args.run_id or []
    if run_ids and len(run_ids) != len(roots):
        parser.error("--run-id must be omitted or supplied once per --run-root")

    output_root = Path(args.output_root)
    exported = []
    for index, root in enumerate(roots):
        run_id = run_ids[index] if run_ids else None
        path = write_feedback_packets(root, output_root, run_id=run_id)
        summary_path = path.parent / "feedback_summary.json"
        exported.append(
            {
                "run_root": str(root),
                "task_feedback_path": str(path),
                "summary_path": str(summary_path),
                "packet_count": sum(1 for _ in path.open("r", encoding="utf-8")),
            }
        )
    print(json.dumps({"exported": exported}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
