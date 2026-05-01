#!/usr/bin/env python3
"""Create focused holiday/calendar discovery splits for SAGE coverage expansion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.config.splits import ScenarioRecord, scenario_records

PREFIX = "find_days_till_holiday"
SEEDS = (
    "find_days_till_holiday_3_distraction_tools_tool_name_scrambled",
    "find_days_till_holiday_alt_3_distraction_tools_tool_name_scrambled",
)


def _priority(record: ScenarioRecord) -> tuple[int, str]:
    name = record.name
    if name in SEEDS:
        return (0, name)
    if "wifi_off" not in name and "multiple_user_turn" not in name:
        return (1, name)
    if "multiple_user_turn" in name and "wifi_off" not in name:
        return (2, name)
    if "wifi_off" in name:
        return (3, name)
    return (9, name)


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
    if len(records) < 40:
        raise ValueError(f"Need at least 40 holiday scenarios, found {len(records)}")
    return {
        "manifest_type": "sage_holiday_discovery_splits",
        "strategy": (
            "front-load non-state holiday day-difference failures, then include "
            "multi-turn and wifi-off variants for same-stratum confirmation."
        ),
        "splits": {
            "mechanism_40": [record.to_json() for record in records[:20]],
            "transfer_40": [record.to_json() for record in records[8:48]],
            "extended_reuse_100": [record.to_json() for record in records[:48]],
        },
        "split_sizes": {
            "mechanism_40": 20,
            "transfer_40": 40,
            "extended_reuse_100": 48,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/splits/holiday_discovery_protocol.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
