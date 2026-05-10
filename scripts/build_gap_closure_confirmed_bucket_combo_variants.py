# mypy: ignore-errors
"""Build confirmed-bucket broad-combination registry variants.

Experimental only. These registries recombine the retained positive recency,
reminder, contact-counterparty, and best3-aligned tools after the narrow
contact/reminder bucket loop. The purpose is to test whether a smaller routed
portfolio improves broad natural adoption by reducing low-value scalar-planner
context exposure.
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
SOURCE = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "top_tools_full_timestamp_no_field_extractor_pack/registry_manifest.json"
)
CURRENT_TOP = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop/"
    "top_tools_plus_action_precondition_v2_pack/registry_manifest.json"
)
SUMMARY_OUT = (
    Path("artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop")
    / "confirmed_bucket_combo_variants_summary.json"
)

CORE_TOOLS = (
    "days_between_timestamps",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
    "select_record_by_timestamp_extreme",
)

NO_DAYS_TOOLS = tuple(name for name in CORE_TOOLS if name != "days_between_timestamps")


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


def _mark_variant(entry: dict[str, Any], note: str) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    existing = str(spec.get("adoption_experiment_note", "")).strip()
    spec["adoption_experiment_note"] = f"{existing}; {note}" if existing else note
    return updated


def _variant(
    source_tools: dict[str, Any], names: tuple[str, ...], note: str
) -> dict[str, Any]:
    missing = [name for name in names if name not in source_tools]
    if missing:
        raise KeyError(f"source registry missing tools: {missing}")
    return {name: _mark_variant(source_tools[name], note) for name in names}


def main() -> None:
    source_tools = _load_tools(SOURCE)
    current_top_tools = _load_tools(CURRENT_TOP) if CURRENT_TOP.exists() else {}

    variants: dict[str, dict[str, Any]] = {
        "confirmed_bucket_core_pack": _variant(
            source_tools,
            CORE_TOOLS,
            "confirmed_bucket_core: retained only tools with positive broad or narrow contact/reminder evidence; scalar contact planners omitted for broad-context ablation",
        ),
        "confirmed_bucket_core_no_days_pack": _variant(
            source_tools,
            NO_DAYS_TOOLS,
            "confirmed_bucket_core_no_days: same as confirmed core but removes days_between_timestamps after broad500 outcome-neutral/canonical-negative calls",
        ),
        "confirmed_bucket_current_top_minus_state_abstain_pack": _variant(
            current_top_tools or source_tools,
            tuple(
                name
                for name in (current_top_tools or source_tools)
                if name
                not in {
                    "plan_device_state_action_sequence",
                    "recommend_domain_safe_abstention",
                }
            ),
            "confirmed_bucket_current_top_minus_state_abstain: current top-v2 without settings/abstention tools after those buckets showed outcome-negative pilots",
        ),
    }

    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "source_registry": str(SOURCE),
        "source_registry_sha256": _sha256(SOURCE.read_bytes()),
        "objective": (
            "Test broad recombination variants after contact/reminder narrow "
            "bucket success. These are registry-only ablations; no protected "
            "evidence or locked registries are modified."
        ),
        "variants": {},
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "candidate_arms_fresh_only": True,
            "baseline_cache_policy": "use-if-eligible",
        },
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
