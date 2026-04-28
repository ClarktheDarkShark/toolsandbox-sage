#!/usr/bin/env python3
"""Create focused SAGE mechanism/transfer/extended-reuse split manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.config.campaign_splits import make_campaign_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/splits/sage_campaign_splits.json"),
    )
    args = parser.parse_args()
    payload = make_campaign_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
