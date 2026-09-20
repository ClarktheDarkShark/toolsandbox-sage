#!/usr/bin/env python3
"""Build a sealed external admission binding for a verified paper registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.registry.legacy_admission_binding import (
    build_legacy_admission_binding,
    file_sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-dir", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--selected-cohort-manifest", type=Path, required=True)
    parser.add_argument("--selected-cohort-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    payload = build_legacy_admission_binding(
        registry_dir=args.registry_dir,
        observations_path=args.observations,
        events_path=args.events,
        output_path=args.output,
        selected_cohort_manifest_path=args.selected_cohort_manifest,
        expected_selected_cohort_sha256=args.selected_cohort_sha256,
    )
    print(
        json.dumps(
            {
                "path": str(args.output.resolve()),
                "sha256": file_sha256(args.output),
                "active_tool_count": payload["active_tool_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
