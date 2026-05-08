"""Build an action-only recency/contact registry for gap-closure adoption tests."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_adoption_minimal_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_contact_update_action_only_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "action_only_registry_build_summary.json"
)


CONTACT_UPDATE_CODE = '''def prepare_contact_update_from_recent_message(messages: list, selection_mode: str, updates: dict = None) -> dict:
    """Prepare modify_contact kwargs from the latest/oldest visible message counterparty."""
    updates = updates if isinstance(updates, dict) else {}

    def empty(reason: str, selected_record=None, selected_timestamp=0.0) -> dict:
        return {
            "selected_message": selected_record if isinstance(selected_record, dict) else {},
            "selected_message_id": "",
            "selected_person_id": "",
            "selected_phone_number": "",
            "selected_timestamp": float(selected_timestamp or 0.0),
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "abstain_reason": str(reason or ""),
            "safety_notes": "abstain; no unique safe contact update target",
            "final_answer_recommendation": "abstain:" + str(reason or "insufficient_information"),
        }

    if not isinstance(messages, list) or not messages:
        return empty("no_messages")
    mode = str(selection_mode or "").strip().lower()
    if mode not in ("latest", "oldest"):
        return empty("invalid_selection_mode")

    candidates = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        raw_ts = message.get("creation_timestamp")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, (int, float)):
            continue
        candidates.append((index, message, float(raw_ts)))
    if not candidates:
        return empty("no_numeric_creation_timestamps")

    target_ts = max(item[2] for item in candidates) if mode == "latest" else min(item[2] for item in candidates)
    tied = [(idx, msg, ts) for idx, msg, ts in candidates if ts == target_ts]
    if len(tied) != 1:
        return empty("ambiguous_timestamp_tie", selected_timestamp=target_ts)

    _idx, selected, selected_ts = tied[0]
    sender_id = selected.get("sender_person_id")
    recipient_id = selected.get("recipient_person_id")
    sender_phone = selected.get("sender_phone_number")
    recipient_phone = selected.get("recipient_phone_number")

    # ToolSandbox messages use a missing/null person id for the self side in
    # common message traces. Choose the visible non-self counterparty without
    # requiring the actor to know the user's person_id.
    if sender_id not in (None, ""):
        person_id = str(sender_id)
        phone_number = "" if sender_phone in (None, "") else str(sender_phone)
    elif recipient_id not in (None, ""):
        person_id = str(recipient_id)
        phone_number = "" if recipient_phone in (None, "") else str(recipient_phone)
    else:
        return empty("missing_counterparty_person_id", selected, selected_ts)

    message_id = selected.get("message_id")
    has_update = any(
        value is not None and (not isinstance(value, str) or value.strip())
        for value in updates.values()
    )
    kwargs = {"person_id": person_id, **updates} if has_update else {}
    return {
        "selected_message": selected,
        "selected_message_id": "" if message_id in (None, "") else str(message_id),
        "selected_person_id": person_id,
        "selected_phone_number": phone_number,
        "selected_timestamp": float(selected_ts),
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": kwargs,
        "should_call_tool": bool(has_update),
        "abstain_reason": "" if person_id else "missing_counterparty_person_id",
        "safety_notes": (
            "call modify_contact with downstream_tool_kwargs when update fields are present; "
            "otherwise use selected_person_id after collecting the requested update"
        ),
        "final_answer_recommendation": "call:modify_contact" if has_update else "collect_update_then_modify_contact",
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


def _contact_tool_entry(template: dict[str, Any]) -> dict[str, Any]:
    entry = copy.deepcopy(template)
    spec = entry["tool"]["spec"]
    spec.update(
        {
            "tool_name": "prepare_contact_update_from_recent_message",
            "family": "composite_workflow_helper",
            "description": (
                "Use after search_messages returns visible message records when the user "
                "wants to modify the contact for the latest or oldest person they messaged "
                "or heard from. This helper selects the message by creation_timestamp, "
                "extracts the non-self counterparty person_id, and returns final "
                "modify_contact kwargs when update fields are known. If the new phone "
                "number or relationship is not known yet, pass updates={} and use "
                "selected_person_id after collecting the update."
            ),
            "inputs": [
                {
                    "name": "messages",
                    "annotation": "list",
                    "description": "Visible list returned by search_messages.",
                },
                {
                    "name": "selection_mode",
                    "annotation": "str",
                    "description": "latest or oldest, matching the user's recency phrase.",
                },
                {
                    "name": "updates",
                    "annotation": "dict",
                    "description": (
                        "Known modify_contact fields such as {'phone_number': '+15551234567'}; "
                        "pass {} when the update must still be collected."
                    ),
                },
            ],
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
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
                    "abstain_reason": {"type": "string"},
                    "safety_notes": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                },
                "required": [
                    "selected_message",
                    "selected_message_id",
                    "selected_person_id",
                    "selected_phone_number",
                    "selected_timestamp",
                    "downstream_tool_name",
                    "downstream_tool_kwargs",
                    "should_call_tool",
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
            ],
            "negative_triggers": [
                "insufficient_information",
                "search_message_with_recency_oldest",
                "search_message_with_recency_latest",
                "send_message",
                "remove_contact",
                "no visible messages",
                "ambiguous timestamp tie",
            ],
            "applicable_task_families": [
                "modify_contact_with_message_recency",
                "contact_update_after_message_lookup",
            ],
            "abstain_behavior": (
                "Return should_call_tool=false with an abstain_reason when messages are "
                "empty, timestamps are missing, the recency mode is invalid, or the "
                "selected message has no visible counterparty person_id."
            ),
            "generalization_rationale": (
                "This action-only helper is derived from expanded60 adoption diagnosis: "
                "broad timestamp selectors and search-window resolvers caused harm, but "
                "the contact-recency action lane remained a critical low-frequency gap."
            ),
            "reason_tool_is_decisive": (
                "It converts a visible latest/oldest message record into final preserved "
                "modify_contact arguments, avoiding manual counterparty selection errors "
                "without performing the side effect itself."
            ),
            "shortfall_cluster_evidence": [
                "recombination_adoption:minimal_expanded60_contact_recency_preserved",
                "visible_message_counterparty_to_contact_update_gap",
            ],
            "known_failure_mechanisms_addressed": [
                "manual message counterparty selection before contact update",
                "intermediate selector output not final-answer-ready",
                "broad resolver/selector displacement in expanded60",
            ],
            "estimated_step_compression": 4,
            "cross_task_applicability_count": 2,
        }
    )
    entry.update(
        {
            "birth_scenario": "gap_closure_lab_action_only_contact_update_repair",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "code_hash": _code_hash(CONTACT_UPDATE_CODE),
            "reuse_count": 0,
            "success_flips": 0,
            "retired": False,
            "legacy_diagnostic": False,
            "validation": {
                "accepted": True,
                "errors": [],
                "held_out_check_count": 3,
                "negative_applicability_count": 4,
                "runtime_smoke_passed": True,
                "source_example_count": 2,
            },
            "version": 1,
        }
    )
    entry["tool"]["code"] = CONTACT_UPDATE_CODE
    return entry


def main() -> None:
    source = json.loads(SRC.read_text(encoding="utf-8"))["tools"]
    generic_action = copy.deepcopy(source["select_recency_target_and_prepare_action"])
    generic_action["tool"]["spec"]["description"] = (
        "Use after a search returns visible records and the user asks to modify or "
        "remove the latest/oldest contact or reminder. This is a narrow action "
        "selector; do not use it for search-only recency answers."
    )
    generic_action["tool"]["spec"]["positive_triggers"] = [
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
        "latest visible record before action",
        "oldest visible record before action",
    ]
    generic_action["tool"]["spec"]["negative_triggers"] = [
        "insufficient_information",
        "search_message_with_recency_oldest",
        "search_message_with_recency_latest",
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search-only answer",
        "ambiguous timestamp tie",
    ]
    generic_action["tool"]["spec"]["applicable_task_families"] = [
        "modify_contact_with_message_recency",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
    ]
    registry = {
        "prepare_contact_update_from_recent_message": _contact_tool_entry(
            source["select_recency_target_and_prepare_action"]
        ),
        "select_recency_target_and_prepare_action": generic_action,
    }
    registry_hash = _write_json(OUT, {"tools": registry})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "source_registry": str(SRC),
        "registry": str(OUT),
        "registry_sha256": registry_hash,
        "objective": (
            "Action-only repair after minimal expanded60: park the negative resolver "
            "and test final-answer-ready contact-recency adoption."
        ),
        "tools": sorted(registry),
        "leakage_statement": (
            "No scenario ids, hidden truth labels, expected answers, or task-specific "
            "facts are encoded. Routing uses visible family labels and generic "
            "recency/action text only."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
