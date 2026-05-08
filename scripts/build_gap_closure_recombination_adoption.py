"""Build experimental recombination registries for SAGE gap-closure adoption tests."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, cast

ROOT = Path("artifacts/registry_experiments/gap_closure_lab")
OUT_ROOT = ROOT / "recombination_adoption"
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption"
)


FOCUS20_SCENARIOS = [
    "modify_contact_with_message_recency",
    "modify_contact_with_message_recency_alt",
    "modify_contact_with_message_recency_3_distraction_tools",
    "modify_contact_with_message_recency_alt_3_distraction_tools",
    "modify_contact_with_message_recency_10_distraction_tools",
    "modify_contact_with_message_recency_alt_10_distraction_tools",
    "modify_reminder_with_recency_latest",
    "modify_reminder_with_recency_latest_alt",
    "modify_reminder_with_recency_latest_3_distraction_tools",
    "modify_reminder_with_recency_latest_alt_3_distraction_tools",
    "remove_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest_alt",
    "remove_reminder_with_recency_latest_3_distraction_tools",
    "remove_reminder_with_recency_latest_alt_3_distraction_tools",
    "search_message_with_recency_latest",
    "search_message_with_recency_oldest",
    "search_message_with_recency_latest_alt",
    "search_message_with_recency_oldest_alt",
    "search_reminder_with_recency_yesterday",
    "search_reminder_with_creation_recency_yesterday",
]


def _read_registry(name: str) -> dict[str, Any]:
    path = ROOT / name / "registry_manifest.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["tools"])


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json_with_hash(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def _tool(source: dict[str, Any], name: str) -> dict[str, Any]:
    return copy.deepcopy(source[name])


def _adopt_select_tool(entry: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(entry)
    spec = entry["tool"]["spec"]
    spec["diagnostic_only"] = False
    spec["description"] = (
        "Use this after an original search returns visible message, reminder, or "
        "contact records and the user asks for the latest, oldest, most recent, "
        "earliest, or first target for a downstream action. It selects the target "
        "record and returns selected_record, selected_id, selected_timestamp, and "
        "a downstream_tool_name. Frequency is expected to be low: call it when this "
        "exact recency/action problem appears instead of manually comparing "
        "timestamps. If updates are not known yet, pass updates={} and use the "
        "returned selected_record to compute the missing update before calling the "
        "original ToolSandbox side-effect tool."
    )
    spec["positive_triggers"] = [
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "latest visible record before action",
        "oldest visible record before action",
        "most recent message target for contact update",
        "latest reminder target for modify or remove",
    ]
    spec["negative_triggers"] = [
        "insufficient_information",
        "ambiguous timestamp tie",
        "direct scalar answer only",
        "pure reminder creation with no record selection",
    ]
    spec["reason_tool_is_decisive"] = (
        "It prevents the specific low-frequency failure where the actor manually "
        "chooses the wrong visible recency target before modifying or removing a "
        "record. It preserves the original downstream ToolSandbox call rather than "
        "performing the side effect itself."
    )
    spec["generalization_rationale"] = (
        "Retained from prior force and natural diagnostics because it showed safe "
        "latent value on recency/action tasks. This metadata variant tests whether "
        "shorter, trigger-focused affordances improve natural adoption without "
        "broadening exposure beyond recency/action families."
    )
    return entry


def _adopt_resolve_tool(entry: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(entry)
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Use this before an original search when the user gives a time-window or "
        "recency phrase such as yesterday, today, upcoming, latest, or oldest. "
        "Call get_current_timestamp first, then call this helper, then call the "
        "original search tool from target_tool_name with search_kwargs. For "
        "modify_contact_with_message_recency it can prepare the message search "
        "bounds before a later target selector. For reminder modify/remove/search "
        "tasks it prepares reminder search bounds. It never searches or performs "
        "side effects itself."
    )
    spec["positive_triggers"] = [
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_reminder_with_recency_upcoming",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "bounded_recency_search_requires_time_window",
    ]
    spec["applicable_task_families"] = [
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
    ]
    spec["negative_triggers"] = [
        "add_reminder",
        "pure_service_enablement",
        "insufficient_information",
        "search_without_time_phrase",
    ]
    spec["reason_tool_is_decisive"] = (
        "It converts the visible natural time phrase and current timestamp into "
        "trace-compatible search kwargs, keeping the original search tool in the "
        "route."
    )
    spec["estimated_step_compression"] = 3
    spec["cross_task_applicability_count"] = 6
    spec["shortfall_cluster_evidence"] = [
        "retained_low_frequency_positive:resolve_search_window_or_bounds_called_subset_positive",
        "recombination_adoption:recency_search_bounds_before_target_selection",
    ]
    spec["known_failure_mechanisms_addressed"] = [
        "manual timestamp-window construction drift",
        "search tool called without trace-compatible recency bounds",
        "recency/action chain hidden because search-window helper was negatively triggered by modify_contact",
    ]
    spec["required_original_tool_calls"] = ["search_messages", "search_reminder"]
    spec["preserves_side_effect_tools"] = ["search_messages", "search_reminder"]
    return entry


def _write_registry(name: str, tools: dict[str, dict[str, Any]]) -> dict[str, Any]:
    path = OUT_ROOT / name / "registry_manifest.json"
    digest = _write_json_with_hash(path, {"tools": tools})
    return {"name": name, "path": str(path), "sha256": digest, "tool_count": len(tools)}


def _focus20_manifest() -> dict[str, Any]:
    scenario_records_fn = cast(
        Any, getattr(import_module("sage_ts.config.splits"), "scenario_records")
    )
    records = {record.name: record for record in scenario_records_fn()}
    missing = [name for name in FOCUS20_SCENARIOS if name not in records]
    if missing:
        raise SystemExit(f"Missing expected focus scenarios: {missing}")
    rows = [
        {
            "scenario_id": name,
            "family_label": name.split("_3_distraction_tools")[0]
            .split("_10_distraction_tools")[0]
            .replace("_alt", ""),
            "task_labels": list(records[name].categories),
            "allowed_tools": list(records[name].allowed_tools),
            "truth_labels_inspected": False,
            "used_for_generation": False,
            "used_for_repair": False,
            "used_for_routing": True,
            "used_for_validation": True,
            "final_evaluation": False,
        }
        for name in FOCUS20_SCENARIOS
    ]
    return {
        "manifest_type": "sage_gap_closure_recombination_focus20",
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "truth_labels_inspected": False,
        "selection_policy": (
            "Task names were selected by visible scenario-family strings related "
            "to recency/action and recency search. Hidden truth labels were not "
            "inspected. This is a targeted adoption diagnostic, not broad claim "
            "evidence."
        ),
        "cache_policy": {
            "baseline_control": "use eligible control cache only with cache hash recorded",
            "sage_candidate": "fresh; OpenAI response reuse disabled",
        },
        "split_aliases": {
            "expanded_60": "pilot_20",
            "confirm_100": "pilot_20",
            "validate_250": "pilot_20",
        },
        "splits": {"pilot_20": rows},
    }


def main() -> None:
    focused = _read_registry("focused_chain_repaired_pack")
    best3 = _read_registry("best3_reference_copy")
    v26 = _read_registry("best3_v26_reference_copy")

    strict_minimal = {
        name: _tool(focused, name)
        for name in (
            "resolve_search_window_or_bounds",
            "select_recency_target_and_prepare_action",
        )
    }
    adopt_minimal = {
        "resolve_search_window_or_bounds": _adopt_resolve_tool(
            _tool(focused, "resolve_search_window_or_bounds")
        ),
        "select_recency_target_and_prepare_action": _adopt_select_tool(
            _tool(focused, "select_recency_target_and_prepare_action")
        ),
    }
    best3_bridge = {
        **copy.deepcopy(best3),
        "resolve_search_window_or_bounds": _adopt_resolve_tool(
            _tool(focused, "resolve_search_window_or_bounds")
        ),
        "select_recency_target_and_prepare_action": _adopt_select_tool(
            _tool(focused, "select_recency_target_and_prepare_action")
        ),
    }
    v26_bridge = {
        **copy.deepcopy(v26),
        "resolve_search_window_or_bounds": _adopt_resolve_tool(
            _tool(focused, "resolve_search_window_or_bounds")
        ),
        "select_recency_target_and_prepare_action": _adopt_select_tool(
            _tool(focused, "select_recency_target_and_prepare_action")
        ),
    }
    contact_bridge = {
        **adopt_minimal,
        "plan_contact_lookup_query": _tool(focused, "plan_contact_lookup_query"),
        "plan_contact_search_from_scalar_constraint": _tool(
            focused, "plan_contact_search_from_scalar_constraint"
        ),
        "extract_contact_field_from_search_result": _tool(
            focused, "extract_contact_field_from_search_result"
        ),
    }

    registries = [
        _write_registry("recency_action_minimal_strict_pack", strict_minimal),
        _write_registry("recency_action_adoption_minimal_pack", adopt_minimal),
        _write_registry("recency_action_best3_bridge_pack", best3_bridge),
        _write_registry("recency_action_v26_bridge_pack", v26_bridge),
        _write_registry("recency_action_contact_bridge_pack", contact_bridge),
    ]

    focus_path = MANIFEST_ROOT / "recombination_focus20_manifest.json"
    focus_hash = _write_json_with_hash(focus_path, _focus20_manifest())
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "objective": "Recombine retained positive recency/action helpers into small portfolios and test natural adoption/routing.",
        "registries": registries,
        "focus20_manifest": {"path": str(focus_path), "sha256": focus_hash},
    }
    _write_json_with_hash(
        MANIFEST_ROOT / "recombination_registry_build_summary.json", summary
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
