#!/usr/bin/env python3
# mypy: ignore-errors
"""Build Best4 candidate registry and ablation60 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import base_task_family, cohort_policy_report

BEST3_REGISTRY = Path("artifacts/registry_frozen_best3_claim/registry_manifest.json")
DAYS_REGISTRY = Path(
    "artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json"
)
BEST3_TOOLS = (
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_record_by_timestamp_extreme",
)
DAYS_TOOL = "days_between_timestamps"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _select(
    prefixes: tuple[str, ...],
    *,
    size: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int = 8,
    include_insufficient: bool = False,
) -> list[ScenarioRecord]:
    candidates = [
        record
        for record in scenario_records()
        if record.name.startswith(prefixes)
        and record.name not in already
        and (
            include_insufficient or "INSUFFICIENT_INFORMATION" not in record.categories
        )
    ]
    candidates.sort(
        key=lambda record: (
            0 if "_3_distraction_tools_arg_description_scrambled" in record.name else 1,
            0 if "_10_distraction_tools" in record.name else 1,
            base_task_family(record.name),
            record.name,
        )
    )
    selected: list[ScenarioRecord] = []
    for record in candidates:
        if len(selected) >= size:
            break
        family = base_task_family(record.name)
        if family_counts[family] >= max_per_family:
            continue
        selected.append(record)
        already.add(record.name)
        family_counts[family] += 1
    if len(selected) != size:
        raise RuntimeError(
            f"Could only select {len(selected)} of {size} for {prefixes}"
        )
    return selected


def build_best4_registry(out_dir: Path) -> dict[str, Any]:
    best3 = json.loads(BEST3_REGISTRY.read_text(encoding="utf-8"))
    days = json.loads(DAYS_REGISTRY.read_text(encoding="utf-8"))
    tools: dict[str, Any] = {}
    for name in BEST3_TOOLS:
        tools[name] = best3["tools"][name]
    tools[DAYS_TOOL] = days["tools"][DAYS_TOOL]
    manifest = {"tools": dict(sorted(tools.items()))}
    registry_path = out_dir / "registry_manifest.json"
    _write_json(registry_path, manifest)
    lock = {
        "label": "v2_2_best4_candidate",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_best3_registry": str(BEST3_REGISTRY),
        "source_best3_sha256": _sha256(BEST3_REGISTRY),
        "source_days_registry": str(DAYS_REGISTRY),
        "source_days_sha256": _sha256(DAYS_REGISTRY),
        "included_tools": sorted(manifest["tools"]),
        "registry_manifest_sha256": _sha256(registry_path),
    }
    _write_json(out_dir / "registry_lock.json", lock)
    return lock


def build_days_only_registry(out_dir: Path) -> dict[str, Any]:
    days = json.loads(DAYS_REGISTRY.read_text(encoding="utf-8"))
    manifest = {"tools": {DAYS_TOOL: days["tools"][DAYS_TOOL]}}
    registry_path = out_dir / "registry_manifest.json"
    _write_json(registry_path, manifest)
    lock = {
        "label": "v2_2_days_only_ablation",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_days_registry": str(DAYS_REGISTRY),
        "source_days_sha256": _sha256(DAYS_REGISTRY),
        "included_tools": [DAYS_TOOL],
        "registry_manifest_sha256": _sha256(registry_path),
    }
    _write_json(out_dir / "registry_lock.json", lock)
    return lock


def build_manifest() -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    records: list[ScenarioRecord] = []
    role_counts: dict[str, int] = {}

    plan: tuple[tuple[str, tuple[str, ...], int, bool], ...] = (
        ("days_positive", ("find_days_till_holiday",), 8, False),
        ("days_positive", ("find_thanksgiving_timestamp",), 2, False),
        (
            "best3_relative_time",
            ("add_reminder_content_and_weekday_delta_and_time",),
            4,
            False,
        ),
        (
            "best3_relative_time",
            ("add_reminder_content_and_week_delta_and_time",),
            4,
            False,
        ),
        (
            "best3_search_window",
            ("search_reminder_with_creation_recency_yesterday",),
            4,
            False,
        ),
        (
            "best3_search_window",
            ("search_reminder_with_recency_upcoming",),
            4,
            False,
        ),
        (
            "best3_record_selection",
            ("search_message_with_recency_latest",),
            4,
            False,
        ),
        (
            "best3_record_selection",
            ("search_message_with_recency_oldest",),
            4,
            False,
        ),
        (
            "days_negative_or_no_helper",
            ("find_days_till_holiday_insufficient_information",),
            4,
            True,
        ),
        ("no_helper_negative", ("remove_contact_with_id",), 3, False),
        ("no_helper_negative", ("add_contact_with_name_and_phone_number",), 3, False),
        ("no_helper_negative", ("get_wifi", "get_cellular"), 4, False),
        (
            "no_helper_negative",
            ("send_message_with_phone_number_and_content",),
            4,
            False,
        ),
        ("no_helper_negative", ("search_name_with_relationship",), 4, False),
        ("no_helper_negative", ("search_phone_number_with_name",), 2, False),
        (
            "no_helper_negative",
            ("remove_contact_by_phone_no_search_contacts_insufficient_information",),
            2,
            True,
        ),
    )
    for role, prefixes, count, include_insufficient in plan:
        chosen = _select(
            prefixes,
            size=count,
            already=already,
            family_counts=family_counts,
            include_insufficient=include_insufficient,
        )
        records.extend(chosen)
        role_counts[role] = role_counts.get(role, 0) + len(chosen)

    if len(records) != 60:
        raise RuntimeError(f"Expected 60 records, selected {len(records)}")
    categories_by_name: dict[str, Iterable[str]] = {
        record.name: record.categories for record in records
    }
    diversity = cohort_policy_report(
        [record.name for record in records],
        categories_by_name=categories_by_name,
        generation_enabled=False,
        registry_tool_count=4,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"Cohort quality failed: {diversity['quality_gate_failures']}"
        )
    return {
        "manifest_type": "sage_v2_2_best4_ablation60",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": (
            "Quality-gated frozen ablation manifest mixing days-between opportunities, "
            "ordinary best3 lanes, no-helper negatives, and non-date cases where the "
            "days helper should remain hidden or abstain."
        ),
        "split_sizes": {"mechanism_60": len(records)},
        "splits": {"mechanism_60": [record.to_json() for record in records]},
        "role_counts": role_counts,
        "protected_best3_registry": str(BEST3_REGISTRY),
        "candidate_days_registry": str(DAYS_REGISTRY),
        "cohort_diversity_report": diversity,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    registry_root = Path("artifacts/registry_candidates")
    summary_root = (
        Path("artifacts/summaries") / f"v2_2_best4_ablation60_{args.timestamp}"
    )
    best4_dir = registry_root / "v2_2_best4_candidate"
    days_only_dir = registry_root / "v2_2_days_only_ablation"

    best4_lock = build_best4_registry(best4_dir)
    days_lock = build_days_only_registry(days_only_dir)
    manifest = build_manifest()
    _write_json(summary_root / "cohort_manifest.json", manifest)
    _write_json(
        summary_root / "cohort_diversity_report.json",
        manifest["cohort_diversity_report"],
    )
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "best4_registry": str(best4_dir / "registry_manifest.json"),
        "best4_registry_sha256": best4_lock["registry_manifest_sha256"],
        "days_only_registry": str(days_only_dir / "registry_manifest.json"),
        "days_only_registry_sha256": days_lock["registry_manifest_sha256"],
        "manifest": str(summary_root / "cohort_manifest.json"),
        "cohort_quality": manifest["cohort_diversity_report"]["quality_gate_status"],
        "role_counts": manifest["role_counts"],
    }
    _write_json(summary_root / "setup_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
