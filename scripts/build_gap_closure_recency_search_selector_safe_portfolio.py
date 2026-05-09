"""Build a safe repaired recency search + contact selector portfolio."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_portfolio_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_portfolio_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_portfolio_build_summary.json"
)

SAFE_SELECTOR_CODE = '''def select_message_counterparty_for_contact_update(records: list, selection_mode: str, updates: dict = None, self_person_id: str = "") -> dict:
    """Select a message counterparty for contact updates without emitting unsafe ids."""
    updates = updates if isinstance(updates, dict) else {}
    self_person_id = str(self_person_id or "").strip()

    def _text(value) -> str:
        return "" if value in (None, "") else str(value).strip()

    def _uuid_like(value) -> bool:
        text = _text(value)
        if len(text) != 36:
            return False
        if [text[8], text[13], text[18], text[23]] != ["-", "-", "-", "-"]:
            return False
        return all(ch in "0123456789abcdefABCDEF" for ch in text.replace("-", ""))

    def _phone_like(value) -> bool:
        text = _text(value)
        return text.startswith("+") and text[1:].isdigit() and len(text) >= 8

    def empty(reason: str, selected_record=None, selected_timestamp=0.0, tie_candidates=None) -> dict:
        return {
            "selected_record": selected_record if isinstance(selected_record, dict) else {},
            "selected_message": selected_record if isinstance(selected_record, dict) else {},
            "selected_message_id": "",
            "selected_person_id": "",
            "selected_phone_number": "",
            "selected_timestamp": float(selected_timestamp or 0.0),
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "tie_candidates": tie_candidates if isinstance(tie_candidates, list) else [],
            "abstain_reason": str(reason or ""),
            "safety_notes": "abstain; no unique safe contact update target",
            "final_answer_recommendation": "abstain:" + str(reason or "insufficient_information"),
        }

    if not isinstance(records, list) or not records:
        return empty("no_records")
    mode = str(selection_mode or "").strip().lower()
    if mode not in ("latest", "oldest"):
        return empty("invalid_selection_mode")

    candidates = []
    id_counts = {}
    phone_counts = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        for key in ("sender_person_id", "recipient_person_id"):
            value = _text(record.get(key))
            if _uuid_like(value):
                id_counts[value] = id_counts.get(value, 0) + 1
        for key in ("sender_phone_number", "recipient_phone_number"):
            value = _text(record.get(key))
            if _phone_like(value):
                phone_counts[value] = phone_counts.get(value, 0) + 1
        raw_ts = record.get("creation_timestamp")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, (int, float)):
            continue
        candidates.append((index, record, float(raw_ts)))
    if not candidates:
        return empty("no_numeric_creation_timestamps")

    target_ts = max(item[2] for item in candidates) if mode == "latest" else min(item[2] for item in candidates)
    tied = [(idx, msg, ts) for idx, msg, ts in candidates if ts == target_ts]
    if len(tied) != 1:
        return empty("ambiguous_timestamp_tie", selected_timestamp=target_ts, tie_candidates=[msg for _, msg, _ in tied])

    _idx, selected, selected_ts = tied[0]
    sender_id = _text(selected.get("sender_person_id"))
    recipient_id = _text(selected.get("recipient_person_id"))
    sender_phone = _text(selected.get("sender_phone_number"))
    recipient_phone = _text(selected.get("recipient_phone_number"))

    sides = [
        {
            "role": "sender",
            "person_id": sender_id if _uuid_like(sender_id) else "",
            "raw_person_id": sender_id,
            "phone_number": sender_phone if _phone_like(sender_phone) else "",
        },
        {
            "role": "recipient",
            "person_id": recipient_id if _uuid_like(recipient_id) else "",
            "raw_person_id": recipient_id,
            "phone_number": recipient_phone if _phone_like(recipient_phone) else "",
        },
    ]

    if self_person_id and _uuid_like(self_person_id):
        if sender_id == self_person_id:
            selected_side = sides[1]
        elif recipient_id == self_person_id:
            selected_side = sides[0]
        else:
            selected_side = None
    else:
        usable = [
            side for side in sides
            if side["person_id"] or side["phone_number"]
        ]
        if not usable:
            return empty("missing_counterparty_identity", selected, selected_ts)

        def side_rank(side):
            phone = side["phone_number"]
            person_id = side["person_id"]
            phone_count = phone_counts.get(phone, 9999) if phone else 9999
            id_count = id_counts.get(person_id, 9999) if person_id else 9999
            # Prefer the less frequent phone/identity in the visible messages.
            # The more frequent side is usually the user's own endpoint.
            return (
                phone_count,
                id_count,
                0 if person_id else 1,
                0 if phone else 1,
                side["role"],
            )

        ranked = sorted(usable, key=side_rank)
        if len(ranked) > 1 and side_rank(ranked[0])[:4] == side_rank(ranked[1])[:4]:
            return empty("ambiguous_counterparty_without_self_id", selected, selected_ts)
        selected_side = ranked[0]

    if selected_side is None:
        return empty("self_id_not_present_in_selected_message", selected, selected_ts)

    person_id = selected_side["person_id"]
    phone_number = selected_side["phone_number"]
    if not person_id and not phone_number:
        return empty("selected_counterparty_has_no_safe_identifier", selected, selected_ts)

    message_id = selected.get("message_id")
    has_update = any(
        value is not None and (not isinstance(value, str) or value.strip())
        for value in updates.values()
    )
    if person_id:
        downstream_tool_name = "modify_contact"
        downstream_tool_kwargs = {"person_id": person_id, **updates} if has_update else {}
        should_call_tool = bool(has_update)
        recommendation = "call:modify_contact" if has_update else "use_selected_record:missing_update_fields"
        safety = (
            "safe contact id selected; call modify_contact with selected_person_id "
            "after collecting requested update fields"
        )
    else:
        downstream_tool_name = "search_contacts"
        downstream_tool_kwargs = {"phone_number": phone_number}
        should_call_tool = True
        recommendation = "call:search_contacts_then_modify_contact"
        safety = (
            "no reliable person_id in message record; search_contacts by selected_phone_number "
            "before any modify_contact call"
        )

    return {
        "selected_record": selected,
        "selected_message": selected,
        "selected_message_id": "" if message_id in (None, "") else str(message_id),
        "selected_person_id": person_id,
        "selected_phone_number": phone_number,
        "selected_timestamp": float(selected_ts),
        "downstream_tool_name": downstream_tool_name,
        "downstream_tool_kwargs": downstream_tool_kwargs,
        "should_call_tool": should_call_tool,
        "tie_candidates": [],
        "abstain_reason": "",
        "safety_notes": safety,
        "final_answer_recommendation": recommendation,
    }
'''


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
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    tools = copy.deepcopy(source["tools"])
    selector = tools["select_message_counterparty_for_contact_update"]
    selector["tool"]["code"] = SAFE_SELECTOR_CODE
    selector["code_hash"] = _sha256(SAFE_SELECTOR_CODE.encode("utf-8"))
    selector["accepted_at"] = datetime.now(timezone.utc).isoformat()
    selector["birth_scenario"] = "gap_closure_lab_safe_contact_selector_bridge_repair"
    selector["version"] = int(selector.get("version", 4)) + 1

    spec = selector["tool"]["spec"]
    spec["description"] = (
        "Safe visible-record selector for contact update tasks. Call after "
        "search_messages returns visible message records when the user wants to "
        "modify the contact for the latest, oldest, last, or most recent message "
        "counterparty. It ranks the less-frequent visible phone/person endpoint "
        "as the counterparty, validates person_id shape before exposing it for "
        "modify_contact, and falls back to search_contacts by phone when the "
        "message record contains no reliable contact id. Do not use before "
        "message records are visible, for reminder tasks, search-only answers, "
        "send/remove tasks, or insufficient-information tasks."
    )
    spec["generalization_rationale"] = (
        "Confirm100 showed the two-tool portfolio has large natural adoption "
        "value but one real contact-update failure caused by a malformed message "
        "person_id being handed to modify_contact. This repair preserves the "
        "positive selector while preventing malformed IDs from becoming action "
        "arguments, preserving the modify_contact bridge while update fields are "
        "pending, and using phone lookup as the safe fallback."
    )
    spec["shortfall_cluster_evidence"] = list(
        dict.fromkeys(
            list(spec.get("shortfall_cluster_evidence", []))
            + [
                "confirm100_safe_repair_single_side_effect_failure_malformed_person_id",
                "contact_selector_called_subset_outcome_positive_but_needs_id_safety",
                "safe_repair_smoke6_contract_mismatch_downstream_tool_name_empty",
            ]
        )
    )
    spec["final_state_preservation_plan"] = (
        "The helper never performs side effects. It emits modify_contact kwargs "
        "only when it has a UUID-shaped selected_person_id. If only a phone "
        "number is reliable, it emits search_contacts kwargs first so the actor "
        "can retrieve a valid person_id before modifying the contact."
    )

    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_registry": str(SOURCE),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "repair_trigger": (
            "Confirm100 for recency_search_contact_selector_portfolio_pack had "
            "one side-effect preservation failure: the selector exposed a "
            "malformed message person_id as modify_contact input."
        ),
        "leakage_statement": (
            "Repair uses a generic malformed/inconsistent visible-ID failure mode "
            "observed after a sealed diagnostic run. It does not encode truth labels, "
            "expected answers, scenario-specific strings, or hidden benchmark facts; "
            "the triggering scenario is repair-contaminated and cannot be used as "
            "promotion evidence for this repaired registry."
        ),
        "cache_policy": {
            "baseline_control_cache": "eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
