#!/usr/bin/env python3
"""Create the SAGE gap-closure lab split manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.config.gap_closure_lab import (
    DEFAULT_GAP_CLOSURE_SEED,
    write_gap_closure_lab_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/experiment_manifests/gap_closure_lab/gap_closure_lab_splits.json"
        ),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_GAP_CLOSURE_SEED)
    parser.add_argument("--generated-at", default="2026-05-07")
    args = parser.parse_args()

    path, file_hash = write_gap_closure_lab_manifest(
        args.output, seed=args.seed, generated_at=args.generated_at
    )
    print(
        json.dumps(
            {
                "manifest": str(path),
                "sha256": file_hash,
                "sha256_file": str(path.with_suffix(path.suffix + ".sha256")),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
