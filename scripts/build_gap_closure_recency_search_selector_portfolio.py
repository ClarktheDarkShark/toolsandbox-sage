"""Build a tiny recency search + contact selector portfolio for adoption tests."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEARCH_SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_adoption_minimal_pack/registry_manifest.json"
)
SELECTOR_SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_contact_selector_bridge_contract_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_portfolio_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_portfolio_build_summary.json"
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


def _load_tool(path: Path, name: str) -> dict[str, Any]:
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8"))["tools"][name])


def _search_window_entry() -> dict[str, Any]:
    entry = _load_tool(SEARCH_SRC, "resolve_search_window_or_bounds")
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Recency search-window helper that prepares search kwargs before the "
        "original ToolSandbox search. Use for latest, oldest, last, most recent, "
        "yesterday, today, recent, or upcoming message/reminder searches. Call "
        "get_current_timestamp first when needed, then call this helper, then call "
        "target_tool_name with search_kwargs. For contact updates such as the last "
        "person I messaged, use target_domain='message', "
        "timestamp_intent='message_creation', and direction='latest' so "
        "search_messages receives bounded timestamp criteria instead of blank or "
        "null arguments. This helper never searches and never performs side "
        "effects."
    )
    spec["positive_triggers"] = [
        "last person I messaged",
        "last person I sent a message to",
        "latest message before contact update",
        "modify_contact_with_message_recency",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_reminder_with_recency_upcoming",
        "bounded_recency_search_requires_time_window",
    ]
    spec["negative_triggers"] = [
        "add_reminder",
        "pure_service_enablement",
        "insufficient_information",
        "search_without_time_phrase",
        "lookup by known contact name only",
    ]
    spec["generalization_rationale"] = (
        "The repaired contact selector has value only after search_messages "
        "returns records. Repair replay showed the actor may call search_messages "
        "with blank criteria and never reach records. This tiny portfolio adds the "
        "retained recency search-window helper so natural routing has a bounded "
        "path from a recency phrase to visible message records before selection."
    )
    spec["shortfall_cluster_evidence"] = [
        "contact_selector_affordance_expanded60_called_subset_outcome_plus_0_50",
        "contact_selector_bridge_repair_smoke6_visible_not_called_after_blank_search",
        "resolve_search_window_or_bounds_retained_low_frequency_positive",
    ]
    entry["accepted_at"] = datetime.now(timezone.utc).isoformat()
    entry["birth_scenario"] = "gap_closure_lab_recency_search_selector_portfolio"
    entry["version"] = int(entry.get("version", 2)) + 1
    return entry


def _selector_entry() -> dict[str, Any]:
    entry = _load_tool(SELECTOR_SRC, "select_message_counterparty_for_contact_update")
    spec = entry["tool"]["spec"]
    spec["description"] = (
        "Visible-record constraint selection for contact update tasks. Call after "
        "search_messages returns visible message records when the user wants to "
        "modify the contact for the latest, oldest, last, or most recent message "
        "counterparty. It selects by creation_timestamp, infers the non-self "
        "counterparty person_id, and returns selected_person_id plus a "
        "side-effect-preserving modify_contact bridge recommendation. Do not use "
        "before message records are visible, for reminder tasks, search-only "
        "answers, send/remove tasks, or insufficient-information tasks."
    )
    spec["positive_triggers"] = [
        "last person I messaged",
        "last person I sent a message to",
        "modify_contact_with_message_recency",
        "latest message counterparty contact update",
        "oldest message counterparty contact update",
        "contact update after search_messages recency",
    ]
    spec["negative_triggers"] = [
        "insufficient_information",
        "search_message_with_recency_oldest",
        "search_message_with_recency_latest",
        "search_reminder",
        "modify_reminder",
        "remove_reminder",
        "send_message",
        "remove_contact",
        "add_contact",
        "search-only answer",
        "no visible messages",
        "ambiguous timestamp tie",
    ]
    spec["generalization_rationale"] = (
        "Affordance expanded60 showed natural selector adoption with +0.50 "
        "target outcome when message records were available. This portfolio keeps "
        "the selector narrow and pairs it with a recency search-window helper so "
        "the actor can reach the records needed for the selector."
    )
    entry["accepted_at"] = datetime.now(timezone.utc).isoformat()
    entry["birth_scenario"] = "gap_closure_lab_recency_search_selector_portfolio"
    entry["version"] = int(entry.get("version", 3)) + 1
    return entry


def main() -> None:
    tools = {
        "resolve_search_window_or_bounds": _search_window_entry(),
        "select_message_counterparty_for_contact_update": _selector_entry(),
    }
    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "objective": (
            "Test whether a tiny two-tool recency/search-plus-selector portfolio "
            "improves natural adoption on contact-recency action tasks while "
            "preserving narrow routing and zero side-effect incidents."
        ),
        "leakage_statement": (
            "Tool metadata uses generic user-facing recency phrases and prior "
            "experimental diagnostics. It does not encode scenario IDs, hidden "
            "truth labels, expected answers, or benchmark-specific task facts."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
