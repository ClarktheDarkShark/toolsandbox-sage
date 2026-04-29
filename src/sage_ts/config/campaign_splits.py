"""Focused split construction for SAGE ToolSandbox campaign gates."""

from __future__ import annotations

from sage_ts.config.splits import ScenarioRecord, scenario_records

SEED_SCENARIOS = (
    "search_reminder_with_recency_yesterday_implicit_3_distraction_tools_arg_type_scrambled",
    "search_reminder_with_recency_upcoming_3_distraction_tools_arg_type_scrambled",
)


def _priority(record: ScenarioRecord) -> tuple[int, str]:
    name = record.name
    if name in SEED_SCENARIOS:
        return (0, name)
    if name.startswith("search_reminder_with_recency"):
        return (1, name)
    if name.startswith("search_reminder_with_creation_recency"):
        return (2, name)
    if name.startswith(
        ("modify_reminder_with_recency", "remove_reminder_with_recency")
    ):
        return (3, name)
    if name.startswith("search_message_with_recency"):
        return (4, name)
    return (5, name)


def _eligible_recency_records() -> list[ScenarioRecord]:
    records = []
    for record in scenario_records():
        categories = set(record.categories)
        if "recency" not in record.name:
            continue
        if "CANONICALIZATION" not in categories:
            continue
        if "INSUFFICIENT_INFORMATION" in categories:
            continue
        records.append(record)
    name_to_record = {record.name: record for record in records}
    missing = [name for name in SEED_SCENARIOS if name not in name_to_record]
    if missing:
        raise ValueError(f"Seed scenarios are missing from ToolSandbox: {missing}")
    ordered_seed = [name_to_record[name] for name in SEED_SCENARIOS]
    remaining = [
        record
        for record in sorted(records, key=_priority)
        if record.name not in SEED_SCENARIOS
    ]
    return ordered_seed + remaining


def make_campaign_manifest() -> dict[str, object]:
    recency = _eligible_recency_records()
    if len(recency) < 100:
        raise ValueError(
            f"Need at least 100 eligible recency scenarios, found {len(recency)}"
        )
    mechanism = recency[:40]
    transfer = recency[40:80]
    extended = recency[:100]
    return {
        "manifest_type": "sage_toolsandbox_campaign_splits",
        "strategy": (
            "front-load two repeated recency canonicalization scenarios to make "
            "accepted tool birth likely, then keep later recency scenarios for "
            "transfer/reuse measurement"
        ),
        "splits": {
            "mechanism_40": [record.to_json() for record in mechanism],
            "transfer_40": [record.to_json() for record in transfer],
            "extended_reuse_100": [record.to_json() for record in extended],
        },
        "split_sizes": {
            "mechanism_40": len(mechanism),
            "transfer_40": len(transfer),
            "extended_reuse_100": len(extended),
        },
    }
