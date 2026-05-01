#!/usr/bin/env python3
"""Create focused contact/message discovery splits for SAGE coverage expansion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.config.splits import ScenarioRecord, scenario_records

PREFIXES = (
    "remove_contact_by_phone",
    "search_phone_number_with_name",
    "search_relationship_with_phone_number",
    "update_contact_relationship_with_relationship",
    "send_message_with_contact_content",
)

SEEDS = (
    "remove_contact_by_phone_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_alt_3_distraction_tools_arg_description_scrambled",
)


def _priority(record: ScenarioRecord) -> tuple[int, str]:
    name = record.name
    if name in SEEDS:
        return (0, name)
    for index, prefix in enumerate(PREFIXES, start=1):
        if name.startswith(prefix):
            return (index, name)
    return (99, name)


def _eligible_records() -> list[ScenarioRecord]:
    records = [
        record
        for record in scenario_records()
        if record.name.startswith(PREFIXES)
        and "INSUFFICIENT_INFORMATION" not in set(record.categories)
    ]
    by_name = {record.name: record for record in records}
    missing = [name for name in SEEDS if name not in by_name]
    if missing:
        raise ValueError(f"Seed scenarios are missing from ToolSandbox: {missing}")
    return sorted(records, key=_priority)


def build_manifest() -> dict[str, object]:
    records = _eligible_records()
    if len(records) < 50:
        raise ValueError(
            f"Need at least 50 contact/message scenarios, found {len(records)}"
        )
    return {
        "manifest_type": "sage_contact_message_discovery_splits",
        "strategy": (
            "front-load repeated contact candidate selection failures, then "
            "hold out adjacent contact/message tasks for same-stratum transfer."
        ),
        "splits": {
            "mechanism_40": [record.to_json() for record in records[:20]],
            "transfer_40": [record.to_json() for record in records[20:60]],
            "extended_reuse_100": [record.to_json() for record in records[:100]],
        },
        "split_sizes": {
            "mechanism_40": 20,
            "transfer_40": 40,
            "extended_reuse_100": 100,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/splits/contact_message_discovery_protocol.json"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
