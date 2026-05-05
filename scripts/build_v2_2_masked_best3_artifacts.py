#!/usr/bin/env python3
"""Build V2.2 masked-best3 discovery artifacts.

The manifest intentionally hides the frozen best3 tools and emphasizes
non-best3 shortfall mechanisms so new generated tools must prove value on
previously uncovered lanes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord
from sage_ts.evaluation.task_strata import cohort_policy_report
from scripts.build_v2_1_gap_closure_artifacts import (
    BEST3,
    FROZEN_BEST3,
    _select,
    build_gap_atlas,
)


def _add(
    selected: list[ScenarioRecord],
    prefixes: tuple[str, ...],
    *,
    count: int,
    already: set[str],
    family_counts: Counter[str],
    max_per_family: int = 8,
    include_insufficient: bool = False,
    include_ambiguous: bool = False,
) -> None:
    selected.extend(
        _select(
            prefixes,
            size=count,
            already=already,
            family_counts=family_counts,
            max_per_family=max_per_family,
            include_insufficient=include_insufficient,
            include_ambiguous=include_ambiguous,
        )
    )


def build_manifest() -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()

    # 20 early examples across several uncovered mechanisms. The mix keeps the
    # birth signal broad enough to avoid selector-only near-duplicate inflation.
    early: list[ScenarioRecord] = []
    _add(
        early,
        ("search_phone_number_with_name",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("search_relationship_with_phone_number",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("update_contact_relationship_with_relationship",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("remove_contact_by_phone",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("turn_on_cellular_low_battery_mode",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("turn_on_wifi_low_battery_mode",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("find_days_till_holiday",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        early,
        ("turn_on_cellular_low_battery_mode",),
        count=1,
        already=already,
        family_counts=family_counts,
    )

    # 25 held-out reuse opportunities after birth chances.
    held_out: list[ScenarioRecord] = []
    _add(
        held_out,
        ("search_phone_number_with_name",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("search_relationship_with_phone_number",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("search_sender_phone_number_with_content",),
        count=4,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("update_contact_relationship_with_relationship",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("remove_contact_by_phone",),
        count=3,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("turn_on_cellular_low_battery_mode",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("turn_on_wifi_low_battery_mode",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("find_days_till_holiday",),
        count=4,
        already=already,
        family_counts=family_counts,
    )
    _add(
        held_out,
        ("turn_on_wifi_low_battery_mode",),
        count=1,
        already=already,
        family_counts=family_counts,
    )

    # 15 negatives/ambiguity/direct-route cases. These protect routing and
    # abstention behavior while keeping the best3 lanes masked.
    negative: list[ScenarioRecord] = []
    _add(
        negative,
        ("remove_contact_by_phone_no_remove_contact_insufficient_information",),
        count=3,
        already=already,
        family_counts=family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        ("remove_contact_by_phone_no_search_contacts_insufficient_information",),
        count=3,
        already=already,
        family_counts=family_counts,
        include_insufficient=True,
    )
    _add(
        negative,
        ("remove_contact_with_id",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        negative,
        ("add_contact_with_name_and_phone_number",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(
        negative,
        ("send_message_with_phone_number_and_content",),
        count=2,
        already=already,
        family_counts=family_counts,
    )
    _add(negative, ("get_wifi",), count=1, already=already, family_counts=family_counts)
    _add(
        negative,
        ("get_cellular",),
        count=1,
        already=already,
        family_counts=family_counts,
    )
    _add(
        negative,
        ("cellular_off",),
        count=1,
        already=already,
        family_counts=family_counts,
    )

    selected = early + held_out + negative
    if len(early) != 20 or len(held_out) != 25 or len(negative) != 15:
        raise RuntimeError(
            f"Expected 20/25/15 split, got {len(early)}/{len(held_out)}/{len(negative)}"
        )
    if len(selected) != 60:
        raise RuntimeError(f"Expected 60 scenarios, selected {len(selected)}")

    categories_by_name: dict[str, Iterable[str]] = {
        record.name: record.categories for record in selected
    }
    diversity = cohort_policy_report(
        [record.name for record in selected],
        categories_by_name=categories_by_name,
        generation_enabled=True,
        registry_tool_count=0,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"Cohort quality failed: {diversity['quality_gate_failures']}"
        )

    return {
        "manifest_type": "sage_v2_2_masked_best3_discovery60",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": (
            "Masked-best3 discovery: 20 early cluster-positive examples, 25 held-out "
            "reuse opportunities, and 15 negative/ambiguity/direct-route cases. "
            "The frozen best3 tools are intentionally absent from the runtime registry."
        ),
        "masked_tools": sorted(BEST3),
        "protected_baseline_registry": str(FROZEN_BEST3 / "registry_manifest.json"),
        "candidate_registry_role": "v2_2_masked_best3_candidate_registry",
        "splits": {"mechanism_60": [record.to_json() for record in selected]},
        "split_sizes": {"mechanism_60": len(selected)},
        "role_counts": {
            "early_cluster_positive": len(early),
            "held_out_reuse": len(held_out),
            "negative_or_ambiguity": len(negative),
        },
        "cohort_diversity_report": diversity,
    }


def write_report(atlas: dict[str, Any], manifest: dict[str, Any], path: Path) -> None:
    path.write_text(
        f"""# V2.2 Masked-Best3 Discovery Setup

## Objective

Create the first masked-best3 V2.2 discovery cohort and candidate registry without modifying frozen best3 evidence.

## Protected Registry

- `{manifest["protected_baseline_registry"]}`

## Masked Tools

{chr(10).join(f"- `{tool}`" for tool in manifest["masked_tools"])}

## Cohort

- Manifest type: `{manifest["manifest_type"]}`
- Scenario count: `{manifest["split_sizes"]["mechanism_60"]}`
- Role counts: `{manifest["role_counts"]}`
- Quality gate: `{manifest["cohort_diversity_report"]["quality_gate_status"]}`
- Distinct families: `{manifest["cohort_diversity_report"]["distinct_base_task_families"]}`
- Largest family share: `{manifest["cohort_diversity_report"]["largest_family_share"]:.3f}`
- Largest helper lane share: `{manifest["cohort_diversity_report"]["largest_helper_lane_share"]:.3f}`

## Ranked Atlas Source

- Shortfall records: `{atlas["record_count"]}`
- Recommendation: {atlas["recommendation"]}

## Decision Label

`continue masked discovery`
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/summaries/v2_2_masked_best3_discovery60"),
    )
    parser.add_argument(
        "--candidate-registry-dir",
        type=Path,
        default=Path("artifacts/registry_candidates/v2_2_masked_best3_discovery60"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.candidate_registry_dir.mkdir(parents=True, exist_ok=True)

    atlas = build_gap_atlas()
    manifest = build_manifest()
    (args.output_dir / "gap_atlas.json").write_text(
        json.dumps(atlas, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "cohort_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "cohort_diversity_report.json").write_text(
        json.dumps(manifest["cohort_diversity_report"], indent=2) + "\n",
        encoding="utf-8",
    )
    # Empty manifest is intentional: it masks best3 and lets online birth fill a
    # separate V2.2 candidate registry.
    (args.candidate_registry_dir / "registry_manifest.json").write_text(
        json.dumps({"tools": {}}, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.candidate_registry_dir / "registry_lock.json").write_text(
        json.dumps(
            {
                "label": "v2_2_masked_best3_candidate_registry",
                "masked_tools": sorted(BEST3),
                "protected_frozen_best3_registry": str(FROZEN_BEST3),
                "created_at": manifest["created_at"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(
        atlas,
        manifest,
        Path("docs/sage_protocol/v2_2_masked_best3_discovery_report.md"),
    )
    print(args.output_dir / "cohort_manifest.json")
    print(args.candidate_registry_dir / "registry_manifest.json")


if __name__ == "__main__":
    main()
