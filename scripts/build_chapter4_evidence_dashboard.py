#!/usr/bin/env python3
"""Build or continuously refresh the Chapter 4 SAGE evidence dashboard."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from scripts.research.chapter4_evidence import (
    EVIDENCE_HTML_NAME,
    write_evidence_dashboard,
)


def _build(args: argparse.Namespace) -> None:
    data = write_evidence_dashboard(
        repo_root=args.repo_root.resolve(),
        campaign_manifest_path=args.campaign_manifest.resolve(),
        output_dir=args.output_dir.resolve(),
        bootstrap_iterations=args.bootstrap_iterations,
        randomization_iterations=args.randomization_iterations,
        seed=args.seed,
    )
    campaign = data["campaign"]
    print(
        "chapter4_evidence "
        f"online={campaign['completed_online_runs']} "
        f"frozen={campaign['completed_frozen_runs']} "
        f"observations={campaign['paired_observations']} "
        f"dashboard={args.output_dir / EVIDENCE_HTML_NAME}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--randomization-iterations", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument(
        "--watch-seconds",
        type=float,
        default=0.0,
        help="Refresh continuously at this interval; zero builds once.",
    )
    args = parser.parse_args()
    if args.bootstrap_iterations < 100:
        parser.error("--bootstrap-iterations must be at least 100")
    if args.randomization_iterations < 100:
        parser.error("--randomization-iterations must be at least 100")
    if args.watch_seconds < 0:
        parser.error("--watch-seconds cannot be negative")

    while True:
        try:
            _build(args)
        except Exception as exc:  # noqa: BLE001 - watcher must report and continue.
            if not args.watch_seconds:
                raise
            print(f"chapter4_evidence refresh failed: {exc!r}", flush=True)
        if not args.watch_seconds:
            return
        time.sleep(args.watch_seconds)


if __name__ == "__main__":
    main()
