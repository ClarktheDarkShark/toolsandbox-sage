#!/usr/bin/env python3
"""Build the standalone dashboard for the H1/H2/H3/H4 pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

from sage_ts.dashboard.hypothesis_pilot import (
    HYPOTHESIS_PILOT_HTML_NAME,
    write_hypothesis_pilot_dashboard,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--latest-pointer",
        type=Path,
        help="Optional path for a relative HTML redirect to this pilot dashboard.",
    )
    args = parser.parse_args()

    payload = write_hypothesis_pilot_dashboard(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        latest_path=args.latest_pointer,
    )
    print(
        "hypothesis_pilot_dashboard "
        f"pilot_id={payload['pilot_id']} "
        f"status={payload['status']} "
        f"dashboard={(args.output_dir / HYPOTHESIS_PILOT_HTML_NAME).resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()
