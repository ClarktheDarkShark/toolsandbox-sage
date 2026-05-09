"""Build an experimental best3 plus contact-selector recombination pack."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BEST3_SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_best3_bridge_pack/registry_manifest.json"
)
SELECTOR_SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_contact_selector_bridge_contract_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_best3_plus_contact_selector_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "best3_plus_contact_selector_registry_build_summary.json"
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


def main() -> None:
    best3 = json.loads(BEST3_SRC.read_text(encoding="utf-8"))
    selector = json.loads(SELECTOR_SRC.read_text(encoding="utf-8"))
    tools = copy.deepcopy(best3["tools"])
    selector_entry = copy.deepcopy(
        selector["tools"]["select_message_counterparty_for_contact_update"]
    )
    selector_entry["accepted_at"] = datetime.now(timezone.utc).isoformat()
    selector_entry["birth_scenario"] = (
        "gap_closure_lab_best3_plus_contact_selector_recombination"
    )
    selector_entry["version"] = int(selector_entry.get("version", 3)) + 1
    spec = selector_entry["tool"]["spec"]
    spec["description"] = (
        "Narrow contact-recency bridge. Call only after search_messages has "
        "returned visible message records and the user asks to modify/update the "
        "contact for the latest, oldest, last, or most recent message "
        "counterparty. It selects the non-self counterparty person_id and returns "
        "a side-effect-preserving modify_contact bridge. Do not use for "
        "search-only answers, reminder tasks, add/remove/send tasks, or "
        "insufficient-information tasks."
    )
    spec["positive_triggers"] = [
        "modify_contact_with_message_recency",
        "last person I messaged contact update",
        "latest message counterparty contact update",
        "oldest message counterparty contact update",
        "contact update after search_messages recency",
    ]
    spec["negative_triggers"] = [
        "insufficient_information",
        "search-only answer",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "search_reminder",
        "modify_reminder",
        "remove_reminder",
        "send_message",
        "remove_contact",
        "add_contact",
        "no visible messages",
        "ambiguous timestamp tie",
    ]
    spec["generalization_rationale"] = (
        "The best3 bridge already covers recency windows and timestamp selection. "
        "This experimental recombination adds the retained low-frequency contact "
        "selector that improved natural called-subset outcome after the side-effect "
        "bridge contract was repaired."
    )
    tools["select_message_counterparty_for_contact_update"] = selector_entry

    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_best3_experimental_copy": str(BEST3_SRC),
        "source_contact_selector": str(SELECTOR_SRC),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "experimental_only": True,
        "objective": (
            "Recombine protected-best3-equivalent recency/action tools with the "
            "retained repaired contact selector in an experimental registry for "
            "targeted natural adoption testing."
        ),
        "leakage_statement": (
            "Uses only existing experimental tool specs and generic surface "
            "recency/contact phrases. No hidden labels, expected answers, or "
            "scenario IDs are encoded in code or routing metadata."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
