#!/usr/bin/env python3
"""Initialize or inspect ToolSandbox SAGE campaign artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.campaign.artifacts import (
    append_event,
    initialize_campaign,
    read_json,
    read_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", type=Path, default=Path("artifacts"))
    init.add_argument("--dashboard-path")
    status = sub.add_parser("status")
    status.add_argument("--root", type=Path, default=Path("artifacts"))
    event = sub.add_parser("event")
    event.add_argument("event")
    event.add_argument("--root", type=Path, default=Path("artifacts"))
    event.add_argument("--payload", default="{}")
    args = parser.parse_args()

    if args.command == "init":
        print(initialize_campaign(root=args.root, dashboard_path=args.dashboard_path))
    elif args.command == "status":
        payload = read_json(args.root / "campaign_status.json")
        payload["recent_events"] = read_jsonl(args.root / "events" / "latest.jsonl")[
            -20:
        ]
        print(json.dumps(payload, indent=2))
    elif args.command == "event":
        print(
            json.dumps(
                append_event(
                    args.event,
                    json.loads(args.payload),
                    root=args.root,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
