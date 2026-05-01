#!/usr/bin/env python3
"""Build a claim-safe registry from prior generated helpers plus fresh validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

PORTFOLIO_EXAMPLES: dict[str, tuple[ToolExample, ...]] = {
    "relative_day_time_to_timestamp": (
        ToolExample(
            {
                "current_timestamp": 1000.0,
                "day_offset": 1,
                "hour": 5,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
            },
            106200.0,
        ),
        ToolExample(
            {
                "current_timestamp": 90000.0,
                "day_offset": 0,
                "hour": 2,
                "minute": 0,
                "local_utc_offset_hours": 0.0,
            },
            93600.0,
            held_out=True,
        ),
    ),
    "recency_to_timestamp_bounds": (
        ToolExample(
            {"recency_label": "today", "current_timestamp": 867600.0},
            {"lower_bound": 864000.0, "upper_bound": 867600.0},
        ),
        ToolExample(
            {"recency_label": "yesterday", "current_timestamp": 867600.0},
            {"lower_bound": 777600.0, "upper_bound": 864000.0},
            held_out=True,
        ),
    ),
    "days_between_timestamps": (
        ToolExample(
            {"timestamp_0": 0.0, "timestamp_1": 90061.0},
            {"days": 1, "seconds": 3661},
        ),
        ToolExample(
            {"timestamp_0": 86400.0, "timestamp_1": 86400.0},
            {"days": 0, "seconds": 0},
            held_out=True,
        ),
    ),
    "select_record_by_timestamp_extreme": (
        ToolExample(
            {
                "records": [
                    {"content": "old", "creation_timestamp": 10.0},
                    {"content": "new", "creation_timestamp": 20.0},
                ],
                "timestamp_key": "creation_timestamp",
                "selection_mode": "latest",
            },
            {"content": "new", "creation_timestamp": 20.0},
        ),
        ToolExample(
            {
                "records": [
                    {"content": "missing"},
                    {"content": "old", "reminder_timestamp": 5.0},
                    {"content": "new", "reminder_timestamp": 15.0},
                ],
                "timestamp_key": "reminder_timestamp",
                "selection_mode": "oldest",
            },
            {"content": "old", "reminder_timestamp": 5.0},
            held_out=True,
        ),
    ),
    "prepare_reminder_arguments_with_optional_location": (
        ToolExample(
            {
                "content": "Buy milk",
                "current_timestamp": 86400.0,
                "day_offset": 1,
                "hour": 9,
                "minute": 30,
                "local_utc_offset_hours": 0.0,
                "location_available": False,
                "latitude": 0.0,
                "longitude": 0.0,
                "location_lookup_failed": True,
            },
            {
                "add_reminder_kwargs": {
                    "content": "Buy milk",
                    "reminder_timestamp": 207000.0,
                    "latitude": None,
                    "longitude": None,
                },
                "should_call_add_reminder": True,
                "should_retry_location_lookup": False,
                "location_status": "omitted",
            },
        ),
        ToolExample(
            {
                "content": "Pick up flowers",
                "current_timestamp": 90000.0,
                "day_offset": 2,
                "hour": 8,
                "minute": 15,
                "local_utc_offset_hours": -8.0,
                "location_available": True,
                "latitude": 37.7749,
                "longitude": -122.4194,
                "location_lookup_failed": False,
            },
            {
                "add_reminder_kwargs": {
                    "content": "Pick up flowers",
                    "reminder_timestamp": 231300.0,
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                },
                "should_call_add_reminder": True,
                "should_retry_location_lookup": False,
                "location_status": "provided",
            },
            held_out=True,
        ),
    ),
    "message_search_time_window": (
        ToolExample(
            {"anchor_timestamp": 864000.0, "lookback_days": 2},
            {
                "creation_timestamp_lowerbound": 691200.0,
                "creation_timestamp_upperbound": 864000.0,
            },
        ),
        ToolExample(
            {"anchor_timestamp": 1000.0, "lookback_days": -5},
            {
                "creation_timestamp_lowerbound": 1000.0,
                "creation_timestamp_upperbound": 1000.0,
            },
            held_out=True,
        ),
    ),
    "select_contact_by_constraint": (
        ToolExample(
            {
                "records": [
                    {
                        "person_id": "a",
                        "name": "Ada Lovelace",
                        "phone_number": "+1 (555) 0100",
                    },
                    {
                        "person_id": "b",
                        "name": "Grace Hopper",
                        "phone_number": "+1 (555) 0200",
                    },
                ],
                "field_name": "phone_number",
                "expected_value": "15550200",
            },
            {
                "person_id": "b",
                "name": "Grace Hopper",
                "phone_number": "+1 (555) 0200",
            },
        ),
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "name": "Ada Lovelace"},
                    {"person_id": "b", "name": "Grace Hopper"},
                ],
                "field_name": "name",
                "expected_value": "Ada Lovelace",
            },
            {"person_id": "a", "name": "Ada Lovelace"},
            held_out=True,
        ),
    ),
}


def _load_entries(paths: list[Path]) -> dict[str, RegistryEntry]:
    entries: dict[str, RegistryEntry] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        tools = payload.get("tools", {})
        if not isinstance(tools, dict):
            continue
        for name, item in tools.items():
            if name not in entries:
                entries[name] = RegistryEntry.from_json(item)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-registry", action="append", type=Path, required=True)
    parser.add_argument("--output-registry", type=Path, required=True)
    default_tools = [
        "relative_day_time_to_timestamp",
        "days_between_timestamps",
        "prepare_reminder_arguments_with_optional_location",
        "select_record_by_timestamp_extreme",
        "recency_to_timestamp_bounds",
    ]
    parser.add_argument("--tool", action="append", default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/summaries/claim_portfolio_validation.json"),
    )
    args = parser.parse_args()

    source_entries = _load_entries(args.source_registry)
    store = RegistryStore(args.output_registry)
    store.save_entries({})
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    requested_tools = args.tool or default_tools
    for tool_name in requested_tools:
        entry = source_entries.get(tool_name)
        if entry is None:
            rejected.append(
                {"tool_name": tool_name, "errors": ["missing_source_entry"]}
            )
            continue
        examples = PORTFOLIO_EXAMPLES.get(tool_name)
        if examples is None:
            rejected.append(
                {"tool_name": tool_name, "errors": ["missing_portfolio_examples"]}
            )
            continue
        validation = validate_generated_tool(entry.tool, examples=examples)
        row = {
            "tool_name": tool_name,
            "source_example_count": validation.source_example_count,
            "held_out_check_count": validation.held_out_check_count,
            "runtime_smoke_passed": validation.runtime_smoke_passed,
            "errors": list(validation.errors),
            "source_birth_scenario": entry.birth_scenario,
        }
        if validation.accepted:
            store.put(
                RegistryEntry.accepted(
                    entry.tool,
                    validation,
                    birth_scenario=entry.birth_scenario,
                )
            )
            accepted.append(row)
        else:
            rejected.append(row)

    report = {
        "source_registries": [str(path) for path in args.source_registry],
        "output_registry": str(args.output_registry),
        "accepted_tools": accepted,
        "rejected_tools": rejected,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.report)


if __name__ == "__main__":
    main()
