# mypy: ignore-errors
"""Build top-tool combination registries and pilot/scale split manifests.

Experimental only. The suite tests whether adding the full best3 set back into
the high-fit recency/day/contact portfolio improves broad transfer without
reintroducing routing pollution.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import base_task_family

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption"
)
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption"
)

HIGH_FIT = (
    REGISTRY_ROOT
    / "recency_day_contact_high_power_scale_pack"
    / "registry_manifest.json"
)
BEST3_DAYS = (
    REGISTRY_ROOT / "best3_plus_final_selector_days_pack" / "registry_manifest.json"
)
FORMAL500 = Path("docs/sage_protocol/manifests/v2_1_formal_500.json")

FULL_OUT = (
    REGISTRY_ROOT / "top_tools_full_best3_highfit_pack" / "registry_manifest.json"
)
TIGHT_OUT = (
    REGISTRY_ROOT
    / "top_tools_tight_timestamp_best3_highfit_pack"
    / "registry_manifest.json"
)
NO_FIELD_OUT = (
    REGISTRY_ROOT
    / "top_tools_tight_timestamp_no_field_extractor_pack"
    / "registry_manifest.json"
)
FULL_NO_FIELD_OUT = (
    REGISTRY_ROOT
    / "top_tools_full_timestamp_no_field_extractor_pack"
    / "registry_manifest.json"
)
TARGETED_MANIFEST_OUT = MANIFEST_ROOT / "top_tool_combo_targeted_splits.json"
BROAD_MANIFEST_OUT = MANIFEST_ROOT / "top_tool_combo_broad_splits.json"
SUMMARY_OUT = MANIFEST_ROOT / "top_tool_combo_suite_build_summary.json"

HIGH_FIT_TOOLS = (
    "days_between_timestamps",
    "extract_contact_field_from_search_result",
    "plan_contact_lookup_query",
    "plan_contact_search_from_scalar_constraint",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
)
BEST3_REINSERT_TOOLS = ("select_record_by_timestamp_extreme",)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def _load_tools(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload["tools"])


def _tool(source: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in source:
        raise KeyError(f"Missing expected tool {name!r}")
    return copy.deepcopy(source[name])


def _tighten_timestamp_selector(entry: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(entry)
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Select one already-visible record by timestamp when the user explicitly "
        "asks for latest/newest/most recent or oldest/earliest/first and the "
        "task needs a generic timestamp extreme. Call only after records are "
        "returned. Prefer narrower tools for message-content recency, contact "
        "updates from recent messages, and holiday/day arithmetic. This helper "
        "does not search and does not perform side effects. Timestamp ties are "
        "handled deterministically by original input order; do not invent a "
        "secondary tie-break unless tie_break_fields are explicitly supplied."
    )
    spec["negative_triggers"] = sorted(
        set(
            list(spec.get("negative_triggers") or [])
            + [
                "message content extraction by recency",
                "contact update from recent message",
                "holiday or day-distance arithmetic",
                "contact scalar lookup",
                "external service tasks",
                "insufficient_information",
            ]
        )
    )
    spec["adoption_experiment_note"] = (
        "top_tool_combo_tight_timestamp_selector; keep full best3 coverage "
        "while reducing overlap with newer recency/day helpers"
    )
    return entry


def _tighten_contact_extractor(entry: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(entry)
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Extract a requested field from exactly one already-visible contact "
        "record after search_contacts. Use only when the user asks for a contact "
        "field such as phone number, relationship, name, or email and the search "
        "result is unambiguous. Abstain on multiple contacts, missing field, "
        "message/reminder tasks, or side-effect-only contact updates."
    )
    spec["negative_triggers"] = sorted(
        set(
            list(spec.get("negative_triggers") or [])
            + [
                "multiple visible contacts",
                "side-effect-only contact update",
                "remove_contact tasks",
                "message recency tasks",
                "reminder tasks",
                "external service tasks",
            ]
        )
    )
    spec["adoption_experiment_note"] = (
        "top_tool_combo_tight_contact_extractor; reduce negative called-subset "
        "seen in high-fit scale500"
    )
    return entry


def _build_registries() -> dict[str, Any]:
    high_fit = _load_tools(HIGH_FIT)
    best3_days = _load_tools(BEST3_DAYS)

    full_tools = {name: _tool(high_fit, name) for name in HIGH_FIT_TOOLS}
    for name in BEST3_REINSERT_TOOLS:
        full_tools[name] = _tool(best3_days, name)

    tight_tools = copy.deepcopy(full_tools)
    tight_tools["select_record_by_timestamp_extreme"] = _tighten_timestamp_selector(
        tight_tools["select_record_by_timestamp_extreme"]
    )
    tight_tools["extract_contact_field_from_search_result"] = (
        _tighten_contact_extractor(
            tight_tools["extract_contact_field_from_search_result"]
        )
    )

    no_field_tools = {
        name: copy.deepcopy(tool)
        for name, tool in tight_tools.items()
        if name != "extract_contact_field_from_search_result"
    }
    full_no_field_tools = {
        name: copy.deepcopy(tool)
        for name, tool in full_tools.items()
        if name != "extract_contact_field_from_search_result"
    }

    full_hash = _write_json(FULL_OUT, {"tools": full_tools})
    tight_hash = _write_json(TIGHT_OUT, {"tools": tight_tools})
    no_field_hash = _write_json(NO_FIELD_OUT, {"tools": no_field_tools})
    full_no_field_hash = _write_json(FULL_NO_FIELD_OUT, {"tools": full_no_field_tools})
    return {
        "full_top_tools": {
            "path": str(FULL_OUT),
            "sha256": full_hash,
            "tools": sorted(full_tools),
        },
        "tight_timestamp_top_tools": {
            "path": str(TIGHT_OUT),
            "sha256": tight_hash,
            "tools": sorted(tight_tools),
        },
        "tight_timestamp_no_field_extractor": {
            "path": str(NO_FIELD_OUT),
            "sha256": no_field_hash,
            "tools": sorted(no_field_tools),
        },
        "full_timestamp_no_field_extractor": {
            "path": str(FULL_NO_FIELD_OUT),
            "sha256": full_no_field_hash,
            "tools": sorted(full_no_field_tools),
        },
    }


def _records_by_name() -> dict[str, ScenarioRecord]:
    return {record.name: record for record in scenario_records()}


def _round_robin(records: list[ScenarioRecord], limit: int) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)
    selected: list[ScenarioRecord] = []
    families = sorted(buckets)
    while any(buckets.values()) and len(selected) < limit:
        for family in families:
            if len(selected) >= limit:
                break
            if buckets[family]:
                selected.append(buckets[family].popleft())
    if len(selected) != limit:
        raise RuntimeError(f"needed {limit} records, selected {len(selected)}")
    return selected


def _row(
    record: ScenarioRecord, split: str, *, final_evaluation: bool
) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "task_labels": list(record.categories),
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": final_evaluation,
        "split": split,
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    labels = Counter(label for row in rows for label in row.get("task_labels", []))
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "top_task_labels": dict(labels.most_common(20)),
        "near_duplicate_dominated": bool(
            rows and max(families.values()) / len(rows) > 0.35
        ),
    }


def _manifest(
    *,
    manifest_type: str,
    splits: dict[str, list[dict[str, Any]]],
    aliases: dict[str, str],
    selection_note: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": manifest_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "selection_policy": {
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
            "selection_note": selection_note,
        },
        "split_aliases": aliases,
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {name: _diversity(rows) for name, rows in splits.items()},
        "cache_policy": {
            "baseline_control_cache": "use-if-eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }


def _build_manifests() -> dict[str, Any]:
    records = _records_by_name()
    high_fit = json.loads(
        (MANIFEST_ROOT / "high_fit_scale_splits.json").read_text(encoding="utf-8")
    )
    targeted_names = [
        str(row["scenario_id"])
        for row in high_fit["splits"]["high_fit_scale500"]
        if str(row.get("high_fit_lane")) in {"recency_day", "contact_scalar"}
    ]
    targeted_records = _round_robin([records[name] for name in targeted_names], 20)
    targeted_rows = {
        "top_tool_targeted20": [
            _row(record, "top_tool_targeted20", final_evaluation=False)
            for record in targeted_records
        ]
    }
    targeted_manifest = _manifest(
        manifest_type="sage_gap_closure_lab_top_tool_targeted_splits",
        splits=targeted_rows,
        aliases={"pilot_20": "top_tool_targeted20"},
        selection_note=(
            "Round-robin 20 from prior high-fit recency/contact lanes for fast "
            "adoption and routing diagnosis. No labels or cache status used."
        ),
    )

    formal = json.loads(FORMAL500.read_text(encoding="utf-8"))
    formal_names = [str(row["name"]) for row in formal["splits"]["full_benchmark"]]
    formal_records = [records[name] for name in formal_names]
    broad500 = _round_robin(formal_records, 500)
    broad_splits = {
        "top_tool_broad20": [
            _row(record, "top_tool_broad20", final_evaluation=False)
            for record in broad500[:20]
        ],
        "top_tool_broad60": [
            _row(record, "top_tool_broad60", final_evaluation=False)
            for record in broad500[:60]
        ],
        "top_tool_broad100": [
            _row(record, "top_tool_broad100", final_evaluation=True)
            for record in broad500[:100]
        ],
        "top_tool_broad250": [
            _row(record, "top_tool_broad250", final_evaluation=True)
            for record in broad500[:250]
        ],
        "top_tool_broad500": [
            _row(record, "top_tool_broad500", final_evaluation=True)
            for record in broad500
        ],
    }
    broad_manifest = _manifest(
        manifest_type="sage_gap_closure_lab_top_tool_broad_splits",
        splits=broad_splits,
        aliases={
            "pilot_20": "top_tool_broad20",
            "expanded_60": "top_tool_broad60",
            "confirm_100": "top_tool_broad100",
            "promotion_250": "top_tool_broad250",
            "validate_250": "top_tool_broad250",
            "full_benchmark": "top_tool_broad500",
        },
        selection_note=(
            "Round-robin ordering of the existing formal500 scenario names to "
            "create progressive broad samples. No labels or cache status used."
        ),
    )

    targeted_hash = _write_json(TARGETED_MANIFEST_OUT, targeted_manifest)
    broad_hash = _write_json(BROAD_MANIFEST_OUT, broad_manifest)
    return {
        "targeted_manifest": {
            "path": str(TARGETED_MANIFEST_OUT),
            "sha256": targeted_hash,
            "split_sizes": targeted_manifest["split_sizes"],
            "split_diversity": targeted_manifest["split_diversity"],
        },
        "broad_manifest": {
            "path": str(BROAD_MANIFEST_OUT),
            "sha256": broad_hash,
            "split_sizes": broad_manifest["split_sizes"],
            "split_diversity": broad_manifest["split_diversity"],
        },
    }


def main() -> None:
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "objective": (
            "Test whether reinserting all three best3 tools into the high-fit "
            "portfolio improves targeted and broad adoption without route pollution."
        ),
        "registries": _build_registries(),
        "manifests": _build_manifests(),
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
