# mypy: ignore-errors
"""Build slim schedule-v2 portfolio ablations for broad gap-closure testing.

Experimental only. These variants remove helpers that repeatedly show
visible-not-called or outcome-neutral behavior in broad runs while preserving
the retained positive schedule/recency/contact selectors.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
SUMMARY_OUT = (
    Path("artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop")
    / "schedule_v2_slim_variants_summary.json"
)
BASE = (
    REGISTRY_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
)

NO_DAYS_REMOVE = ("days_between_timestamps",)
SLIM_REMOVE = (
    "days_between_timestamps",
    "plan_contact_search_from_scalar_constraint",
    "relative_weeks_time_to_timestamp",
)
POSITIVE_CORE = (
    "next_weekday_time_to_timestamp",
    "plan_contact_lookup_query",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
    "select_record_by_timestamp_extreme",
)


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
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["tools"])


def _mark(entry: dict[str, Any], note: str) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    existing = str(spec.get("adoption_experiment_note", "")).strip()
    spec["adoption_experiment_note"] = f"{existing}; {note}" if existing else note
    return updated


def _minus(
    source: dict[str, Any],
    removed: tuple[str, ...],
    note: str,
) -> dict[str, Any]:
    missing = [name for name in removed if name not in source]
    if missing:
        raise KeyError(f"source registry missing removable tools: {missing}")
    return {
        name: _mark(entry, note)
        for name, entry in source.items()
        if name not in set(removed)
    }


def _select(
    source: dict[str, Any],
    names: tuple[str, ...],
    note: str,
) -> dict[str, Any]:
    missing = [name for name in names if name not in source]
    if missing:
        raise KeyError(f"source registry missing selected tools: {missing}")
    return {name: _mark(source[name], note) for name in names}


def main() -> None:
    source = _load_tools(BASE)
    variants = {
        "full_timestamp_schedule_v2_no_days_pack": _minus(
            source,
            NO_DAYS_REMOVE,
            "schedule_v2_no_days: remove days_between_timestamps after repeated outcome-neutral/canonical-negative broad calls",
        ),
        "full_timestamp_schedule_v2_slim_pack": _minus(
            source,
            SLIM_REMOVE,
            "schedule_v2_slim: remove days, scalar contact planner, and relative-weeks helper after broad visible-not-called or neutral evidence",
        ),
        "full_timestamp_schedule_v2_positive_core_pack": _select(
            source,
            POSITIVE_CORE,
            "schedule_v2_positive_core: retain only naturally positive broad schedule/recency/contact helpers",
        ),
    }
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "base_registry": str(BASE),
        "base_registry_sha256": _sha256(BASE.read_bytes()),
        "objective": (
            "Reduce broad context pollution while keeping low-frequency positive "
            "helpers. Candidate arms remain fresh; controls may use eligible cache."
        ),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "candidate_arms_fresh_only": True,
            "baseline_cache_policy": "use-if-eligible",
        },
        "variants": {},
    }
    for label, tools in variants.items():
        path = REGISTRY_ROOT / label / "registry_manifest.json"
        digest = _write_json(path, {"tools": tools})
        summary["variants"][label] = {
            "path": str(path),
            "sha256": digest,
            "tools": sorted(tools),
        }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
