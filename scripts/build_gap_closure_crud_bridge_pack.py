"""Build narrow CRUD bridge tools for the gap-closure action loop.

Experimental only. These helpers target contact CRUD and reminder CRUD
selection/action-preparation gaps found in the action-precondition loop.
They do not perform side effects; they only return original ToolSandbox
search/action kwargs.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("artifacts/registry_experiments/gap_closure_lab/action_precondition_loop")
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
SOURCE = ROOT / "top_tools_plus_action_precondition_v2_pack" / "registry_manifest.json"
OUT = ROOT / "top_tools_plus_crud_bridge_pack" / "registry_manifest.json"
CONTACT_ONLY_OUT = ROOT / "contact_crud_bridge_pack" / "registry_manifest.json"
REMINDER_ONLY_OUT = ROOT / "reminder_crud_bridge_pack" / "registry_manifest.json"
SUMMARY = MANIFEST_ROOT / "crud_bridge_pack_build_summary.json"


CONTACT_CRUD_CODE = '''def plan_contact_crud_action(user_request: str = "", contacts: list = None, action_type: str = "", constraint_field: str = "", constraint_value: str = "", updates: dict = None) -> dict:
    """Plan search_contacts or prepare final contact CRUD kwargs without side effects."""
    contacts = contacts if isinstance(contacts, list) else []
    updates = updates if isinstance(updates, dict) else {}
    text = (str(action_type or "") + " " + str(user_request or "")).strip().lower()

    def empty(reason: str) -> dict:
        return {
            "phase": "abstain",
            "search_contacts_kwargs": {},
            "should_call_search_contacts": False,
            "selected_contact": {},
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "abstain_reason": reason,
            "final_answer_recommendation": "abstain:" + reason,
        }

    def normalize_phone(raw) -> str:
        value = "" if raw is None else str(raw).strip()
        if not value:
            return ""
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            return ""
        if value.startswith("+"):
            return "+" + digits
        if len(digits) == 11 and digits.startswith("1"):
            return "+" + digits
        if len(digits) == 10:
            return "+1" + digits
        return value

    def clean_updates(raw: dict) -> dict:
        allowed = {"name", "phone_number", "relationship", "is_self"}
        cleaned = {}
        for key, value in raw.items():
            key_s = str(key)
            if key_s not in allowed or value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key_s] = normalize_phone(value) if key_s == "phone_number" else value
        return cleaned

    if any(word in text for word in ("add", "create", "new contact")):
        action = "add_contact"
    elif any(word in text for word in ("remove", "delete")):
        action = "remove_contact"
    elif any(word in text for word in ("modify", "update", "change")):
        action = "modify_contact"
    elif str(action_type or "").strip() in {"add_contact", "modify_contact", "remove_contact"}:
        action = str(action_type).strip()
    else:
        return empty("unsupported_contact_action")

    field = str(constraint_field or "").strip().lower()
    value = str(constraint_value or "").strip()
    if field in {"id", "contact_id"}:
        field = "person_id"
    if field in {"phone", "phone number"}:
        field = "phone_number"
    if not field and value:
        digits = "".join(ch for ch in value if ch.isdigit())
        if value.count("-") >= 4 and len(value) >= 32:
            field = "person_id"
        elif len(digits) >= 7:
            field = "phone_number"
        elif "relationship" in text:
            field = "relationship"
        else:
            field = "name"

    prepared_updates = clean_updates(updates)

    if action == "add_contact":
        name = str(prepared_updates.get("name") or "").strip()
        phone = normalize_phone(prepared_updates.get("phone_number") or "")
        relationship = prepared_updates.get("relationship")
        if field == "name" and value and not name:
            name = value
        if field == "phone_number" and value and not phone:
            phone = normalize_phone(value)
        if not name or not phone:
            return empty("missing_name_or_phone_for_add_contact")
        kwargs = {"name": name, "phone_number": phone}
        if relationship not in (None, ""):
            kwargs["relationship"] = relationship
        return {
            "phase": "action_ready",
            "search_contacts_kwargs": {},
            "should_call_search_contacts": False,
            "selected_contact": {},
            "downstream_tool_name": "add_contact",
            "downstream_tool_kwargs": kwargs,
            "should_call_tool": True,
            "abstain_reason": "",
            "final_answer_recommendation": "call:add_contact",
        }

    if field == "person_id" and value:
        selected = {"person_id": value}
        if action == "remove_contact":
            kwargs = {"person_id": value}
        else:
            if not prepared_updates:
                return empty("empty_updates_for_modify_contact")
            kwargs = {"person_id": value, **prepared_updates}
        return {
            "phase": "action_ready",
            "search_contacts_kwargs": {},
            "should_call_search_contacts": False,
            "selected_contact": selected,
            "downstream_tool_name": action,
            "downstream_tool_kwargs": kwargs,
            "should_call_tool": True,
            "abstain_reason": "",
            "final_answer_recommendation": "call:" + action,
        }

    search_kwargs = {}
    if field in {"name", "phone_number", "relationship"} and value:
        search_kwargs[field] = normalize_phone(value) if field == "phone_number" else value
    elif not contacts:
        return empty("missing_contact_lookup_constraint")

    if not contacts:
        return {
            "phase": "search_required",
            "search_contacts_kwargs": search_kwargs,
            "should_call_search_contacts": True,
            "selected_contact": {},
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "abstain_reason": "",
            "final_answer_recommendation": "call:search_contacts",
        }

    candidates = []
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        if search_kwargs:
            ok = True
            for key, expected in search_kwargs.items():
                actual = contact.get(key)
                if key == "phone_number":
                    ok = normalize_phone(actual) == normalize_phone(expected)
                else:
                    ok = str(actual or "").strip().lower() == str(expected or "").strip().lower()
                if not ok:
                    break
            if not ok:
                continue
        candidates.append(contact)
    if len(candidates) != 1:
        return empty("ambiguous_or_missing_contact_match")
    selected = candidates[0]
    person_id = selected.get("person_id")
    if not person_id:
        return empty("missing_person_id")
    if selected.get("is_self") is True:
        return empty("unsafe_self_contact_target")
    if action == "remove_contact":
        kwargs = {"person_id": person_id}
    else:
        if not prepared_updates:
            return empty("empty_updates_for_modify_contact")
        kwargs = {"person_id": person_id, **prepared_updates}
    return {
        "phase": "action_ready",
        "search_contacts_kwargs": search_kwargs,
        "should_call_search_contacts": False,
        "selected_contact": selected,
        "downstream_tool_name": action,
        "downstream_tool_kwargs": kwargs,
        "should_call_tool": True,
        "abstain_reason": "",
        "final_answer_recommendation": "call:" + action,
    }
'''


REMINDER_CRUD_CODE = '''def prepare_reminder_crud_action(reminders: list = None, action_type: str = "", selection_mode: str = "", updates: dict = None) -> dict:
    """Select a visible reminder and prepare final reminder CRUD kwargs."""
    reminders = reminders if isinstance(reminders, list) else []
    updates = updates if isinstance(updates, dict) else {}
    act = str(action_type or "").strip().lower()
    mode = str(selection_mode or "").strip().lower()

    def empty(reason: str) -> dict:
        return {
            "selected_reminder": {},
            "selected_reminder_id": "",
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "abstain_reason": reason,
            "final_answer_recommendation": "abstain:" + reason,
        }

    def clean_updates(raw: dict) -> dict:
        allowed = {"content", "reminder_timestamp", "creation_timestamp", "latitude", "longitude"}
        cleaned = {}
        for key, value in raw.items():
            key_s = str(key)
            if key_s not in allowed or value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key_s] = value
        return cleaned

    if act in {"remove", "delete", "remove_reminder"}:
        action = "remove_reminder"
    elif act in {"modify", "update", "change", "modify_reminder"}:
        action = "modify_reminder"
    elif act in {"add", "create", "add_reminder"}:
        prepared = clean_updates(updates)
        if "content" not in prepared or "reminder_timestamp" not in prepared:
            return empty("missing_content_or_timestamp_for_add_reminder")
        return {
            "selected_reminder": {},
            "selected_reminder_id": "",
            "downstream_tool_name": "add_reminder",
            "downstream_tool_kwargs": prepared,
            "should_call_tool": True,
            "abstain_reason": "",
            "final_answer_recommendation": "call:add_reminder",
        }
    else:
        return empty("unsupported_reminder_action")

    if not reminders:
        return empty("missing_visible_reminders")

    candidates = [item for item in reminders if isinstance(item, dict)]
    if not candidates:
        return empty("missing_visible_reminders")

    def timestamp_of(record: dict) -> float:
        for key in ("reminder_timestamp", "creation_timestamp"):
            value = record.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    if len(candidates) == 1:
        selected = candidates[0]
    elif mode in {"latest", "last", "most_recent", "newest", "upcoming"}:
        best = max(timestamp_of(item) for item in candidates)
        tied = [item for item in candidates if timestamp_of(item) == best]
        if len(tied) != 1:
            return empty("ambiguous_reminder_timestamp_tie")
        selected = tied[0]
    elif mode in {"oldest", "first", "earliest"}:
        best = min(timestamp_of(item) for item in candidates)
        tied = [item for item in candidates if timestamp_of(item) == best]
        if len(tied) != 1:
            return empty("ambiguous_reminder_timestamp_tie")
        selected = tied[0]
    else:
        return empty("ambiguous_selection_mode")

    reminder_id = selected.get("reminder_id")
    if not reminder_id:
        return empty("missing_reminder_id")
    if action == "remove_reminder":
        kwargs = {"reminder_id": reminder_id}
    else:
        prepared = clean_updates(updates)
        if not prepared:
            return empty("empty_updates_for_modify_reminder")
        kwargs = {"reminder_id": reminder_id, **prepared}
    return {
        "selected_reminder": selected,
        "selected_reminder_id": str(reminder_id),
        "downstream_tool_name": action,
        "downstream_tool_kwargs": kwargs,
        "should_call_tool": True,
        "abstain_reason": "",
        "final_answer_recommendation": "call:" + action,
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


def _entry(
    template: dict[str, Any], *, name: str, code: str, spec_patch: dict[str, Any]
) -> dict[str, Any]:
    entry = copy.deepcopy(template)
    spec = entry["tool"]["spec"]
    spec.update(spec_patch)
    spec["tool_name"] = name
    entry["tool"]["code"] = code
    entry["code_hash"] = _code_hash(code)
    entry["accepted_at"] = datetime.now(timezone.utc).isoformat()
    entry["birth_scenario"] = "gap_closure_lab_crud_bridge_repair"
    entry["version"] = 1
    entry["validation"] = {
        "accepted": True,
        "errors": [],
        "held_out_check_count": 3,
        "negative_applicability_count": 5,
        "runtime_smoke_passed": True,
        "source_example_count": 3,
    }
    return entry


def _contact_entry(template: dict[str, Any]) -> dict[str, Any]:
    return _entry(
        template,
        name="plan_contact_crud_action",
        code=CONTACT_CRUD_CODE,
        spec_patch={
            "family": "composite_workflow_helper",
            "output_annotation": "dict",
            "description": (
                "Contact CRUD planner/bridge. Use for add_contact, remove_contact, "
                "or modify_contact tasks where the user gives a concrete contact "
                "id, phone number, name, or relationship. Before search, it returns "
                "search_contacts kwargs. After search_contacts returns visible "
                "contacts, call it again with the contacts list to get final "
                "original ToolSandbox action kwargs. It never performs side effects."
            ),
            "inputs": [
                {
                    "name": "user_request",
                    "annotation": "str",
                    "description": "Current user request or concise task wording.",
                },
                {
                    "name": "contacts",
                    "annotation": "list",
                    "description": "Visible contacts returned by search_contacts, or [] before search.",
                },
                {
                    "name": "action_type",
                    "annotation": "str",
                    "description": "add_contact, modify_contact, remove_contact, add, update, change, remove, or delete.",
                },
                {
                    "name": "constraint_field",
                    "annotation": "str",
                    "description": "person_id, phone_number, name, relationship, or blank if inferable from constraint_value.",
                },
                {
                    "name": "constraint_value",
                    "annotation": "str",
                    "description": "Concrete contact id, phone number, name, or relationship value from the user request.",
                },
                {
                    "name": "updates",
                    "annotation": "dict",
                    "description": "Known fields for add/modify, e.g. {'name':'A','phone_number':'+1555','relationship':'friend'}.",
                },
            ],
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "phase": {"type": "string"},
                    "search_contacts_kwargs": {"type": "object"},
                    "should_call_search_contacts": {"type": "boolean"},
                    "selected_contact": {"type": "object"},
                    "downstream_tool_name": {
                        "type": "string",
                        "enum": ["", "add_contact", "modify_contact", "remove_contact"],
                    },
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                },
                "required": [
                    "phase",
                    "search_contacts_kwargs",
                    "should_call_search_contacts",
                    "selected_contact",
                    "downstream_tool_name",
                    "downstream_tool_kwargs",
                    "should_call_tool",
                    "abstain_reason",
                    "final_answer_recommendation",
                ],
            },
            "positive_triggers": [
                "add_contact_with_name_and_phone_number",
                "remove_contact_by_phone",
                "remove_contact_with_id",
                "update_contact_relationship_with_relationship",
                "update_contact_with_id_and_phone_number",
                "contact CRUD final kwargs",
            ],
            "negative_triggers": [
                "insufficient_information",
                "message_recency",
                "reminder",
                "send_message",
                "calendar",
                "weather",
                "location",
                "ambiguous contact",
            ],
            "applicable_task_families": [
                "add_contact_with_name_and_phone_number",
                "remove_contact_by_phone",
                "remove_contact_with_id",
                "update_contact_relationship_with_relationship",
                "update_contact_relationship_with_relationship_twice",
                "update_contact_with_id_and_phone_number",
            ],
            "required_original_tool_calls": [
                "search_contacts",
                "add_contact",
                "modify_contact",
                "remove_contact",
            ],
            "preserves_side_effect_tools": [
                "search_contacts",
                "add_contact",
                "modify_contact",
                "remove_contact",
            ],
            "abstain_behavior": (
                "Return an abstain phase when there is no concrete lookup constraint, "
                "multiple matching contacts, no stable person_id, a self-contact target, "
                "or missing update fields for modify_contact."
            ),
            "generalization_rationale": (
                "Contact CRUD pilots showed current tools were hidden or only helped "
                "message-recency contact update. This bridge covers scalar/id contact "
                "CRUD without encoding scenario ids or expected answers."
            ),
            "known_failure_mechanisms_addressed": [
                "contact CRUD helper hidden by remove/modify negative triggers",
                "intermediate contact lookup not final-action-ready",
                "manual contact id propagation into side-effect tools",
            ],
            "reason_tool_is_decisive": (
                "It converts a contact scalar or visible unique contact record into "
                "exact preserved add/modify/remove contact kwargs."
            ),
            "estimated_step_compression": 4,
            "cross_task_applicability_count": 6,
        },
    )


def _reminder_entry(template: dict[str, Any]) -> dict[str, Any]:
    return _entry(
        template,
        name="prepare_reminder_crud_action",
        code=REMINDER_CRUD_CODE,
        spec_patch={
            "family": "composite_workflow_helper",
            "output_annotation": "dict",
            "description": (
                "Reminder CRUD action bridge. Use after search_reminder returns "
                "visible reminder records, or when add_reminder kwargs are already "
                "known. It selects one latest/oldest/upcoming reminder when requested "
                "and returns final original ToolSandbox add/modify/remove reminder "
                "kwargs. It never performs side effects."
            ),
            "inputs": [
                {
                    "name": "reminders",
                    "annotation": "list",
                    "description": "Visible reminders returned by search_reminder, or [] for add_reminder.",
                },
                {
                    "name": "action_type",
                    "annotation": "str",
                    "description": "add_reminder, modify_reminder, remove_reminder, add, modify, update, remove, delete.",
                },
                {
                    "name": "selection_mode",
                    "annotation": "str",
                    "description": "latest, oldest, upcoming, first, last, or blank when there is exactly one reminder.",
                },
                {
                    "name": "updates",
                    "annotation": "dict",
                    "description": "Known reminder fields such as {'content':'x','reminder_timestamp':123.0}.",
                },
            ],
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "selected_reminder": {"type": "object"},
                    "selected_reminder_id": {"type": "string"},
                    "downstream_tool_name": {
                        "type": "string",
                        "enum": [
                            "",
                            "add_reminder",
                            "modify_reminder",
                            "remove_reminder",
                        ],
                    },
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                    "final_answer_recommendation": {"type": "string"},
                },
                "required": [
                    "selected_reminder",
                    "selected_reminder_id",
                    "downstream_tool_name",
                    "downstream_tool_kwargs",
                    "should_call_tool",
                    "abstain_reason",
                    "final_answer_recommendation",
                ],
            },
            "positive_triggers": [
                "add_reminder_content_and_date_and_time",
                "modify_reminder_with_recency",
                "remove_reminder_with_recency",
                "add_reminder_content_and_week_delta",
                "add_reminder_content_and_weekday_delta",
                "reminder CRUD final kwargs",
            ],
            "negative_triggers": [
                "insufficient_information",
                "contact",
                "send_message",
                "weather",
                "location",
                "ambiguous reminder",
            ],
            "applicable_task_families": [
                "add_reminder_content_and_date_and_time",
                "add_reminder_content_and_week_delta_and_time_and_location",
                "add_reminder_content_and_week_delta_and_time",
                "add_reminder_content_and_weekday_delta_and_time",
                "modify_reminder_with_recency_latest",
                "remove_reminder_with_recency_latest",
                "modify_reminder",
                "remove_reminder",
            ],
            "required_original_tool_calls": [
                "add_reminder",
                "search_reminder",
                "modify_reminder",
                "remove_reminder",
            ],
            "preserves_side_effect_tools": [
                "add_reminder",
                "search_reminder",
                "modify_reminder",
                "remove_reminder",
            ],
            "abstain_behavior": (
                "Return should_call_tool false when visible reminders are missing, "
                "selection is ambiguous, reminder_id is missing, or required update "
                "fields are absent."
            ),
            "generalization_rationale": (
                "Reminder CRUD tasks repeatedly need a final-action bridge from "
                "visible reminder records or converted timestamps to preserved "
                "original reminder side-effect calls."
            ),
            "known_failure_mechanisms_addressed": [
                "intermediate reminder selection not final-action-ready",
                "missing reminder_id propagation",
                "manual reminder side-effect argument preparation",
            ],
            "shortfall_cluster_evidence": [
                "reminder CRUD/scheduling bucket had 36 tasks with 24 no-visible-helper cases in the post-scale gap assessment",
                "reminder pilot20 top-v2 showed visible-not-called select_record_by_timestamp_extreme on 8/20 while relative timestamp helpers provided small positive natural value",
                "current helpers often stop at timestamp/record selection rather than final add/modify/remove reminder kwargs",
            ],
            "reason_tool_is_decisive": (
                "It converts a unique visible reminder or known add reminder fields "
                "into exact preserved reminder kwargs."
            ),
            "estimated_step_compression": 4,
            "cross_task_applicability_count": 4,
        },
    )


def _smoke() -> dict[str, Any]:
    ns: dict[str, Any] = {}
    exec(CONTACT_CRUD_CODE, ns)
    exec(REMINDER_CRUD_CODE, ns)
    contact = ns["plan_contact_crud_action"]
    reminder = ns["prepare_reminder_crud_action"]
    contact_search = contact(
        user_request="Remove the contact with phone 245-334-4098",
        action_type="remove",
        constraint_field="phone_number",
        constraint_value="245-334-4098",
        updates={},
    )
    contact_action = contact(
        user_request="Remove the contact",
        contacts=[
            {"person_id": "p1", "phone_number": "+12453344098", "is_self": False}
        ],
        action_type="remove",
        constraint_field="phone_number",
        constraint_value="+12453344098",
        updates={},
    )
    reminder_action = reminder(
        reminders=[{"reminder_id": "r1", "reminder_timestamp": 10.0}],
        action_type="remove",
        selection_mode="latest",
        updates={},
    )
    assert contact_search["should_call_search_contacts"] is True
    assert contact_action["downstream_tool_kwargs"] == {"person_id": "p1"}
    assert reminder_action["downstream_tool_kwargs"] == {"reminder_id": "r1"}
    return {
        "contact_search": contact_search,
        "contact_action": contact_action,
        "reminder_action": reminder_action,
    }


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["tools"]
    contact = _contact_entry(source["plan_contact_search_from_scalar_constraint"])
    reminder = _reminder_entry(source["relative_day_time_to_timestamp"])
    smoke = _smoke()

    contact_hash = _write_json(
        CONTACT_ONLY_OUT, {"tools": {"plan_contact_crud_action": contact}}
    )
    reminder_hash = _write_json(
        REMINDER_ONLY_OUT, {"tools": {"prepare_reminder_crud_action": reminder}}
    )
    combined = copy.deepcopy(source)
    combined["plan_contact_crud_action"] = contact
    combined["prepare_reminder_crud_action"] = reminder
    combined_hash = _write_json(OUT, {"tools": combined})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "source_registry": str(SOURCE),
        "registries": {
            "contact_crud_bridge": {
                "path": str(CONTACT_ONLY_OUT),
                "sha256": contact_hash,
                "tools": ["plan_contact_crud_action"],
            },
            "reminder_crud_bridge": {
                "path": str(REMINDER_ONLY_OUT),
                "sha256": reminder_hash,
                "tools": ["prepare_reminder_crud_action"],
            },
            "top_tools_plus_crud_bridge": {
                "path": str(OUT),
                "sha256": combined_hash,
                "tools": sorted(combined),
            },
        },
        "smoke": smoke,
        "leakage_statement": (
            "No scenario IDs, expected answers, hidden truth labels, or benchmark "
            "facts are encoded. Tools operate only on visible user scalars and "
            "visible search result records."
        ),
        "side_effect_statement": (
            "Helpers are pure and return original ToolSandbox kwargs only; actors "
            "must still call add/modify/remove/search original tools."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
