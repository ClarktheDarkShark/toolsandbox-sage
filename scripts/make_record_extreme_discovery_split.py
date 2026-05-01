#!/usr/bin/env python3
"""Create focused oldest-record discovery splits for SAGE coverage expansion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.config.splits import ScenarioRecord, scenario_records

PREFIX = "search_message_with_recency_oldest"
SEEDS = (
    "search_message_with_recency_oldest_3_distraction_tools",
    "search_message_with_recency_oldest_10_distraction_tools",
)


def _priority(record: ScenarioRecord) -> tuple[int, str]:
    name = record.name
    if name in SEEDS:
        return (0, name)
    if "multiple_user_turn" not in name:
        return (1, name)
    return (2, name)


def _eligible_records() -> list[ScenarioRecord]:
    records = [
        record
        for record in scenario_records()
        if record.name.startswith(PREFIX)
        and "INSUFFICIENT_INFORMATION" not in set(record.categories)
    ]
    by_name = {record.name: record for record in records}
    missing = [name for name in SEEDS if name not in by_name]
    if missing:
        raise ValueError(f"Seed scenarios are missing from ToolSandbox: {missing}")
    return sorted(records, key=_priority)


def build_manifest() -> dict[str, object]:
    records = _eligible_records()
    if len(records) < 12:
        raise ValueError(
            f"Need at least 12 oldest-record scenarios, found {len(records)}"
        )
    mechanism = records[: min(20, len(records))]
    return {
        "manifest_type": "sage_record_extreme_discovery_splits",
        "strategy": (
            "front-load oldest message-search failures to birth a deterministic "
            "timestamp-extreme record selector, then confirm across all available "
            "oldest-message variants."
        ),
        "splits": {
            "mechanism_40": [record.to_json() for record in mechanism],
            "transfer_40": [record.to_json() for record in records],
            "extended_reuse_100": [record.to_json() for record in records],
        },
        "split_sizes": {
            "mechanism_40": len(mechanism),
            "transfer_40": len(records),
            "extended_reuse_100": len(records),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/splits/record_extreme_discovery_protocol.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
