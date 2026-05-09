"""Build a compact recency/action safe-bridge portfolio with abstention guard."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

SAFE_BRIDGE = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_portfolio_pack/registry_manifest.json"
)
GUARD = Path(
    "artifacts/registry_experiments/gap_closure_lab/"
    "affordance_rich_guard_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_plus_guard_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_plus_guard_build_summary.json"
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


def _read_tools(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, dict[str, Any]], payload["tools"])


def _guard_entry(source: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entry = copy.deepcopy(source["detect_insufficient_visible_records"])
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Use only on missing-information or cannot-determine tasks, preferably "
        "after an original search/list call has produced visible records or "
        "returned no records. It checks whether exactly one usable visible record "
        "contains the required fields, returns should_abstain plus a clarification "
        "prompt when information is insufficient, and never calls services or "
        "performs side effects. Keep using the recency/action helpers for normal "
        "latest/oldest tasks; use this guard to avoid over-answering or unsafe "
        "actions when required information is absent."
    )
    spec["positive_triggers"] = [
        "insufficient_information",
        "cannot_determine",
        "missing_information",
        "not enough visible information",
        "empty search result on missing-information task",
    ]
    spec["negative_triggers"] = [
        "direct_scalar_service_answer_available",
        "side_effect_action_already_has_complete_unique_target",
        "ordinary_recency_action_with_records_and_required_fields",
    ]
    spec["shortfall_cluster_evidence"] = list(
        dict.fromkeys(
            list(spec.get("shortfall_cluster_evidence", []))
            + [
                "safe_bridge_confirm100_exact_losses_hidden_insufficient_information",
                "candidate_no_runtime_incidents_but_exact_tied_by_missing_info_noise",
            ]
        )
    )
    spec["generalization_rationale"] = (
        "The safe recency/action bridge produced strong natural outcome lift and "
        "zero candidate incidents, but confirm100 exact success tied control "
        "because hidden-tool insufficient-information tasks moved in both "
        "directions. This compact recombination tests whether an existing "
        "validated abstention guard can absorb that missing-information lane "
        "without diluting recency/action adoption."
    )
    entry["accepted_at"] = datetime.now(timezone.utc).isoformat()
    entry["birth_scenario"] = "gap_closure_lab_safe_bridge_plus_guard_recombination"
    entry["version"] = int(entry.get("version", 2)) + 1
    return entry


def main() -> None:
    safe_bridge = copy.deepcopy(_read_tools(SAFE_BRIDGE))
    guard = _read_tools(GUARD)
    tools = {
        "detect_insufficient_visible_records": _guard_entry(guard),
        "resolve_search_window_or_bounds": safe_bridge[
            "resolve_search_window_or_bounds"
        ],
        "select_message_counterparty_for_contact_update": safe_bridge[
            "select_message_counterparty_for_contact_update"
        ],
    }
    digest = _write_json(OUT, {"tools": tools})
    summary_digest = _write_json(
        SUMMARY,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experimental_only": True,
            "source_registries": {
                "safe_bridge": str(SAFE_BRIDGE),
                "abstention_guard": str(GUARD),
            },
            "registry": str(OUT),
            "registry_sha256": digest,
            "tool_count": len(tools),
            "tools": sorted(tools),
            "hypothesis": (
                "A three-tool portfolio can preserve the high natural adoption "
                "of recency/action helpers while giving missing-information "
                "tasks an explicit safe-abstain affordance."
            ),
            "leakage_controls": [
                "No scenario IDs, expected answers, or truth labels are encoded in tool code.",
                "The guard operates only on actor-provided visible records, field names, and constraints.",
                "The experiment remains targeted and experimental, not protected final evidence.",
            ],
        },
    )
    print(
        json.dumps(
            {
                "registry": str(OUT),
                "registry_sha256": digest,
                "summary": str(SUMMARY),
                "summary_sha256": summary_digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
