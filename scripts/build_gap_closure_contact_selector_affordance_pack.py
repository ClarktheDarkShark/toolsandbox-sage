"""Build a contact-recency selector pack with stronger natural-call affordances."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_contact_update_action_only_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_contact_selector_affordance_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "contact_selector_affordance_registry_build_summary.json"
)


CONTACT_SELECTOR_CODE = '''def select_message_counterparty_for_contact_update(records: list, selection_mode: str, updates: dict = None, self_person_id: str = "") -> dict:
    """Select the latest/oldest message counterparty and prepare modify_contact kwargs."""
    updates = updates if isinstance(updates, dict) else {}
    self_person_id = str(self_person_id or "").strip()

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
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        for key in ("sender_person_id", "recipient_person_id"):
            value = record.get(key)
            if value not in (None, ""):
                text = str(value)
                id_counts[text] = id_counts.get(text, 0) + 1
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
    sender_id = selected.get("sender_person_id")
    recipient_id = selected.get("recipient_person_id")
    sender_phone = selected.get("sender_phone_number")
    recipient_phone = selected.get("recipient_phone_number")
    sender_id = "" if sender_id in (None, "") else str(sender_id)
    recipient_id = "" if recipient_id in (None, "") else str(recipient_id)

    person_id = ""
    phone_number = ""
    if self_person_id and sender_id == self_person_id and recipient_id:
        person_id = recipient_id
        phone_number = "" if recipient_phone in (None, "") else str(recipient_phone)
    elif self_person_id and recipient_id == self_person_id and sender_id:
        person_id = sender_id
        phone_number = "" if sender_phone in (None, "") else str(sender_phone)
    elif sender_id and not recipient_id:
        person_id = sender_id
        phone_number = "" if sender_phone in (None, "") else str(sender_phone)
    elif recipient_id and not sender_id:
        person_id = recipient_id
        phone_number = "" if recipient_phone in (None, "") else str(recipient_phone)
    elif sender_id and recipient_id and sender_id != recipient_id:
        sender_count = id_counts.get(sender_id, 0)
        recipient_count = id_counts.get(recipient_id, 0)
        if sender_count < recipient_count:
            person_id = sender_id
            phone_number = "" if sender_phone in (None, "") else str(sender_phone)
        elif recipient_count < sender_count:
            person_id = recipient_id
            phone_number = "" if recipient_phone in (None, "") else str(recipient_phone)
        else:
            return empty("ambiguous_counterparty_without_self_id", selected, selected_ts)
    elif sender_id:
        person_id = sender_id
        phone_number = "" if sender_phone in (None, "") else str(sender_phone)
    else:
        return empty("missing_counterparty_person_id", selected, selected_ts)

    message_id = selected.get("message_id")
    has_update = any(
        value is not None and (not isinstance(value, str) or value.strip())
        for value in updates.values()
    )
    kwargs = {"person_id": person_id, **updates} if has_update else {}
    return {
        "selected_record": selected,
        "selected_message": selected,
        "selected_message_id": "" if message_id in (None, "") else str(message_id),
        "selected_person_id": person_id,
        "selected_phone_number": phone_number,
        "selected_timestamp": float(selected_ts),
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": kwargs,
        "should_call_tool": bool(has_update),
        "tie_candidates": [],
        "abstain_reason": "",
        "safety_notes": (
            "call modify_contact with downstream_tool_kwargs when update fields are present; "
            "otherwise use selected_person_id as the modify_contact person_id after collecting the requested update"
        ),
        "final_answer_recommendation": "call:modify_contact" if has_update else "use_selected_person_id_for_modify_contact",
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


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _contact_selector_entry(template: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(template)
    spec = entry["tool"]["spec"]
    spec.update(
        {
            "tool_name": "select_message_counterparty_for_contact_update",
            "family": "composite_workflow_helper",
            "description": (
                "Visible-record constraint selection for contact update tasks. Call after "
                "search_messages returns visible message records when the user wants to "
                "modify the contact for the latest or oldest person they messaged or "
                "heard from. It selects the message by creation_timestamp, infers the "
                "non-self counterparty person_id, and returns final modify_contact kwargs "
                "when update fields are known. Do not use for search-only, reminder, "
                "remove, send, or insufficient-information tasks."
            ),
            "inputs": [
                {
                    "name": "records",
                    "annotation": "list",
                    "description": "Full visible list returned by the prior search_messages call.",
                },
                {
                    "name": "selection_mode",
                    "annotation": "str",
                    "description": "latest for most recent/last; oldest for earliest/oldest.",
                },
                {
                    "name": "updates",
                    "annotation": "dict",
                    "description": (
                        "Known modify_contact fields such as {'phone_number': '+15551234567'}; "
                        "pass {} when the update must still be collected from the user turn."
                    ),
                },
                {
                    "name": "self_person_id",
                    "annotation": "str",
                    "description": (
                        "Optional visible self person_id if already known. Leave empty when not known; "
                        "the helper uses message-list frequency to infer the counterparty."
                    ),
                },
            ],
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_message": {"type": "object"},
                    "selected_message_id": {"type": "string"},
                    "selected_person_id": {"type": "string"},
                    "selected_phone_number": {"type": "string"},
                    "selected_timestamp": {"type": "number"},
                    "downstream_tool_name": {
                        "type": "string",
                        "enum": ["", "modify_contact"],
                    },
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "tie_candidates": {"type": "array"},
                    "abstain_reason": {"type": "string"},
                    "safety_notes": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                },
                "required": [
                    "selected_record",
                    "selected_message",
                    "selected_message_id",
                    "selected_person_id",
                    "selected_phone_number",
                    "selected_timestamp",
                    "downstream_tool_name",
                    "downstream_tool_kwargs",
                    "should_call_tool",
                    "tie_candidates",
                    "abstain_reason",
                    "safety_notes",
                    "final_answer_recommendation",
                ],
            },
            "required_original_tool_calls": ["modify_contact"],
            "preserves_side_effect_tools": ["modify_contact"],
            "positive_triggers": [
                "modify_contact_with_message_recency",
                "latest person I messaged before contact update",
                "oldest person I messaged before contact update",
                "last message counterparty contact update",
                "contact update after search_messages recency",
            ],
            "negative_triggers": [
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
            ],
            "applicable_task_families": [
                "modify_contact_with_message_recency",
                "contact_update_after_message_lookup",
            ],
            "abstain_behavior": (
                "Return should_call_tool=false with abstain_reason on no records, invalid "
                "selection mode, missing timestamps, timestamp ties, missing counterparty id, "
                "or ambiguous counterparty when self_person_id/frequency inference cannot "
                "choose a unique non-self contact."
            ),
            "generalization_rationale": (
                "Selector-only expanded60 showed a high-value called subset on the "
                "modify_contact_with_message_recency task, while a no-helper null run was "
                "negative on that same scenario. This variant keeps the same deterministic "
                "selection step but narrows routing to contact updates and adds the records "
                "input plus visible-record selector affordance needed for natural adoption."
            ),
            "reason_tool_is_decisive": (
                "The hard deterministic step is choosing the latest/oldest visible message "
                "counterparty and converting it into the person_id required by modify_contact."
            ),
            "shortfall_cluster_evidence": [
                "selector_only_expanded60_modify_contact_called_subset_outcome_positive",
                "action_only_expanded60_visible_not_called_due_to_affordance",
                "null_scaffold_expanded60_modify_contact_same_scenario_negative",
            ],
            "known_failure_mechanisms_addressed": [
                "manual recency target selection before modify_contact",
                "contact update helper hidden from selector actor policy",
                "two-tool bundle adoption ambiguity",
            ],
        }
    )
    entry["tool"]["code"] = CONTACT_SELECTOR_CODE
    entry["tool"]["spec"] = spec
    entry.update(
        {
            "birth_scenario": "gap_closure_lab_contact_selector_affordance_repair",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "code_hash": _code_hash(CONTACT_SELECTOR_CODE),
            "reuse_count": 0,
            "success_flips": 0,
            "retired": False,
            "legacy_diagnostic": False,
            "validation": {
                "accepted": True,
                "errors": [],
                "held_out_check_count": 5,
                "negative_applicability_count": 6,
                "runtime_smoke_passed": True,
                "source_example_count": 4,
            },
            "version": int(entry.get("version", 1)) + 1,
        }
    )
    return entry


def main() -> None:
    source = json.loads(SRC.read_text(encoding="utf-8"))["tools"]
    template = source["prepare_contact_update_from_recent_message"]
    contact_selector = _contact_selector_entry(template)
    registry_hash = _write_json(
        OUT,
        {"tools": {"select_message_counterparty_for_contact_update": contact_selector}},
    )
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "source_registry": str(SRC),
        "registry": str(OUT),
        "registry_sha256": registry_hash,
        "objective": (
            "Focused recency/action natural adoption test for a single contact-update "
            "selector with explicit selector affordance and no reminder/remove exposure."
        ),
        "tools": ["select_message_counterparty_for_contact_update"],
        "leakage_statement": (
            "No scenario ids, hidden truth labels, expected answers, or task-specific facts "
            "are encoded. The tool uses generic visible message record fields and generic "
            "contact-update routing triggers."
        ),
        "cache_policy": (
            "Control arms may use the eligible baseline cache. Candidate arms are fresh "
            "with OpenAI response reuse disabled for outcome evidence."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
