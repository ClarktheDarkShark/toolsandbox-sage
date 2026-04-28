#!/usr/bin/env python3
"""Export SAGE run metrics or a matched control/candidate comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--control-dir", type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--registry-dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    if args.run_dir is not None:
        payload = summarize_run(args.run_dir, registry_dir=args.registry_dir)
    elif args.control_dir is not None and args.candidate_dir is not None:
        payload = compare_runs(
            args.control_dir,
            args.candidate_dir,
            registry_dir=args.registry_dir,
        )
    else:
        raise SystemExit("Pass either --run-dir or both --control-dir/--candidate-dir")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
