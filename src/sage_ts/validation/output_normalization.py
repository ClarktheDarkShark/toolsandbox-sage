"""Runtime/validation normalization for generated helper outputs.

This layer enforces framework-level safety contracts that generated code declares
but may implement imperfectly. It should avoid injecting task answers or hidden
labels; repairs are limited to contract-level corrections from visible inputs.
"""

from __future__ import annotations

import re
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily


def _dedupe_strings(values: Any) -> list[str]:
    if isinstance(values, str):
        text = values.strip()
        if text.startswith("functions."):
            text = text.split(".", 1)[1]
        return [text] if text else []
    if not isinstance(values, list):
        return []
    if values and all(isinstance(item, str) and len(item) <= 1 for item in values):
        joined = "".join(values).strip()
        if joined:
            if joined.startswith("functions."):
                joined = joined.split(".", 1)[1]
            return [joined]
    seen: set[str] = set()
    deduped: list[str] = []
    for item in values:
        text = str(item)
        if text.startswith("functions."):
            text = text.split(".", 1)[1]
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _normalize_constraint_value(field_name: str, value: Any) -> str:
    text = str(value)
    lowered_field = field_name.lower()
    if "phone" in lowered_field or "number" in lowered_field:
        return "".join(re.findall(r"\d", text))
    return text.strip().lower()


def _infer_matching_records(inputs: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not inputs:
        return []
    records = inputs.get("records") or inputs.get("candidates")
    field_name = str(inputs.get("field_name", inputs.get("match_field", "")))
    if not isinstance(records, list) or not field_name:
        return []
    if "expected_value" in inputs:
        expected = inputs.get("expected_value")
    elif "match_value" in inputs:
        expected = inputs.get("match_value")
    elif "value" in inputs:
        expected = inputs.get("value")
    else:
        return []
    normalized_expected = _normalize_constraint_value(field_name, expected)
    matches: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict) or field_name not in record:
            continue
        if (
            _normalize_constraint_value(field_name, record.get(field_name))
            == normalized_expected
        ):
            matches.append(dict(record))
    return matches


def _stable_record_id(record: dict[str, Any]) -> str:
    for key in (
        "person_id",
        "message_id",
        "reminder_id",
        "sender_person_id",
        "recipient_person_id",
        "id",
    ):
        if record.get(key) not in (None, ""):
            return str(record[key])
    return ""


def _normalize_abstain_reason(value: Any) -> str:
    reason = str(value or "").strip()
    if not reason:
        return ""
    # Generated helpers often vary harmless punctuation/case in negative examples.
    return reason.rstrip(".!").strip().lower()


def _has_contact_lookup_constraint(inputs: dict[str, Any] | None) -> bool:
    if not inputs:
        return False
    for key in (
        "contact_name",
        "name",
        "target_name",
        "phone_number",
        "target_phone_number",
        "relationship",
    ):
        if str(inputs.get(key) or "").strip():
            return True
    return False


def _normalize_send_message_contact_lookup_output(
    value: dict[str, Any],
) -> dict[str, Any]:
    """Fill non-operational advisory fields for send-message lookup planners."""
    required_keys = {
        "should_call_search_contacts",
        "search_contacts_kwargs",
        "downstream_tool_name",
        "message_content",
        "next_step",
        "final_answer_recommendation",
    }
    if not required_keys <= set(value):
        return value
    normalized = dict(value)
    if (
        bool(normalized.get("should_call_search_contacts"))
        and isinstance(normalized.get("search_contacts_kwargs"), dict)
        and str(normalized.get("downstream_tool_name") or "")
        == "send_message_with_phone_number"
        and str(normalized.get("message_content") or "").strip()
    ):
        if not str(normalized.get("next_step") or "").strip():
            normalized["next_step"] = (
                "call search_contacts, then send_message_with_phone_number"
            )
        if not str(normalized.get("final_answer_recommendation") or "").strip():
            normalized["final_answer_recommendation"] = (
                "After search_contacts returns exactly one matching contact, call "
                "send_message_with_phone_number with that contact's phone number "
                "and the prepared message_content."
            )
    return normalized


def _strip_null_values_from_generated_kwargs(value: dict[str, Any]) -> dict[str, Any]:
    """Remove null optional arguments from helper-prepared downstream kwargs."""
    normalized = dict(value)
    for key, item in list(normalized.items()):
        if key.endswith("_kwargs") and isinstance(item, dict):
            cleaned = {k: v for k, v in item.items() if v is not None}
            if key == "search_contacts_kwargs" and str(
                cleaned.get("relationship") or ""
            ).strip().lower() in {"__all_contacts__", "all_contacts", "all contacts"}:
                cleaned.pop("relationship", None)
                cleaned.setdefault("is_self", False)
            normalized[key] = cleaned
        elif key.endswith("_kwargs_list") and isinstance(item, list):
            cleaned_items: list[Any] = []
            for entry in item:
                if isinstance(entry, dict):
                    cleaned_items.append(
                        {k: v for k, v in entry.items() if v is not None}
                    )
                else:
                    cleaned_items.append(entry)
            normalized[key] = cleaned_items
        elif key == "action_sequence" and isinstance(item, list):
            cleaned_sequence: list[Any] = []
            for entry in item:
                if not isinstance(entry, dict):
                    cleaned_sequence.append(entry)
                    continue
                cleaned_entry = dict(entry)
                arguments = cleaned_entry.get("arguments")
                if isinstance(arguments, dict):
                    cleaned_entry["arguments"] = {
                        k: v for k, v in arguments.items() if v is not None
                    }
                cleaned_sequence.append(cleaned_entry)
            normalized[key] = cleaned_sequence
    return normalized


def _normalize_generic_composite_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make abstaining composite helper outputs side-effect safe and comparable."""
    normalized = _strip_null_values_from_generated_kwargs(
        _normalize_send_message_contact_lookup_output(dict(value))
    )
    abstain_reason = _normalize_abstain_reason(normalized.get("abstain_reason"))
    if (
        not abstain_reason
        and "should_call_search_contacts" in normalized
        and "search_contacts_kwargs" in normalized
        and "answer_field" in normalized
        and not bool(normalized.get("should_call_search_contacts"))
        and not normalized.get("search_contacts_kwargs")
    ):
        requested = str(
            (inputs or {}).get("requested_field")
            or normalized.get("answer_field")
            or ""
        ).strip()
        abstain_reason = (
            "missing_lookup_constraint"
            if requested and not _has_contact_lookup_constraint(inputs)
            else "missing_requested_field"
        )
    if not abstain_reason:
        return _strip_null_values_from_generated_kwargs(normalized)
    normalized["abstain_reason"] = abstain_reason
    should_call_tool = bool(normalized.get("should_call_tool"))
    should_call_tools = bool(normalized.get("should_call_tools"))
    should_call_search = bool(normalized.get("should_call_search_contacts"))
    should_call_downstream = bool(normalized.get("should_call_downstream_tool"))
    if (
        not should_call_tool
        and not should_call_tools
        and not should_call_search
        and not should_call_downstream
    ):
        if "downstream_tool_name" in normalized:
            normalized["downstream_tool_name"] = ""
        if "downstream_tool_kwargs" in normalized:
            normalized["downstream_tool_kwargs"] = {}
        if "downstream_tool_kwargs_list" in normalized:
            normalized["downstream_tool_kwargs_list"] = []
    return _strip_null_values_from_generated_kwargs(normalized)


def _relationship_label(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "all": "__all_contacts__",
        "all contacts": "__all_contacts__",
        "all_contacts": "__all_contacts__",
        "bosses": "boss",
        "colleagues": "coworker",
        "contacts": "__all_contacts__",
        "coworkers": "coworker",
        "enemies": "enemy",
        "friends": "friend",
        "relatives": "family",
    }
    return aliases.get(text, text)


def _normalize_contact_relationship_batch_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Treat stale visible contact records as a need for current-state search."""

    normalized = _normalize_generic_composite_output(value, inputs=inputs)
    source = _relationship_label(
        normalized.get("source_relationship")
        or (inputs or {}).get("source_relationship")
    )
    target = _relationship_label(
        normalized.get("target_relationship")
        or (inputs or {}).get("target_relationship")
    )
    contacts = (inputs or {}).get("contacts") if inputs else None
    if not source or not target or source == target or not isinstance(contacts, list):
        return normalized
    if not contacts:
        return normalized
    downstream = normalized.get("downstream_tool_kwargs_list")
    has_downstream = isinstance(downstream, list) and bool(downstream)
    if has_downstream or bool(normalized.get("should_call_tools")):
        return normalized
    if bool(normalized.get("should_call_search_contacts")):
        return normalized
    phase = str(normalized.get("phase") or "").strip().lower()
    abstain_reason = _normalize_abstain_reason(normalized.get("abstain_reason"))
    stale_or_mismatched = any(
        isinstance(contact, dict)
        and str(contact.get("person_id") or "").strip()
        and _relationship_label(contact.get("relationship")) != source
        for contact in contacts
    )
    if not stale_or_mismatched:
        return normalized
    if phase != "abstain" and "match" not in abstain_reason:
        return normalized
    normalized["phase"] = "search_required"
    normalized["should_call_search_contacts"] = True
    normalized["search_contacts_kwargs"] = (
        {"is_self": False} if source == "__all_contacts__" else {"relationship": source}
    )
    normalized["selected_contacts"] = []
    normalized["downstream_tool_name"] = ""
    normalized["downstream_tool_kwargs_list"] = []
    normalized["should_call_tools"] = False
    normalized["abstain_reason"] = ""
    normalized["final_answer_recommendation"] = ""
    return _strip_null_values_from_generated_kwargs(normalized)


def _record_index(inputs: dict[str, Any] | None, record: dict[str, Any]) -> int:
    if not inputs:
        return -1
    records = inputs.get("records") or inputs.get("candidates")
    if not isinstance(records, list):
        return -1
    for index, item in enumerate(records):
        if isinstance(item, dict) and item == record:
            return index
    return -1


def _normalize_composite_workflow_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = _normalize_generic_composite_output(value, inputs=inputs)
    selected_record = normalized.get("selected_record")
    if not isinstance(selected_record, dict):
        selected_record = {}
        normalized["selected_record"] = selected_record

    abstain_reason = _normalize_abstain_reason(normalized.get("abstain_reason"))
    ambiguous = any(
        token in abstain_reason
        for token in ("ambig", "tie", "multiple_match", "multiple match")
    )
    if ambiguous:
        inferred_matches = _infer_matching_records(inputs)
        existing_ties = normalized.get("tie_candidates")
        tie_candidates = list(existing_ties) if isinstance(existing_ties, list) else []
        if len(inferred_matches) > 1:
            tie_candidates = inferred_matches
        elif selected_record:
            tie_candidates = [dict(selected_record), *tie_candidates]
        normalized["selected_record"] = {}
        normalized["selected_index"] = -1
        normalized["selected_id"] = ""
        normalized["value"] = ""
        normalized["downstream_tool_name"] = ""
        normalized["downstream_tool_kwargs"] = {}
        normalized["should_call_tool"] = False
        normalized["tie_candidates"] = tie_candidates
        normalized["abstain_reason"] = (
            normalized.get("abstain_reason") or "ambiguous_multiple_matches"
        )
        normalized["safety_notes"] = "do not guess before side-effect action"
        return normalized

    if selected_record:
        selected_id = str(
            normalized.get("selected_id") or _stable_record_id(selected_record)
        )
        normalized["selected_id"] = selected_id
        if normalized.get("selected_index") in (None, "", -1):
            normalized["selected_index"] = _record_index(inputs, selected_record)
        downstream_tool = str(normalized.get("downstream_tool_name") or "")
        downstream_kwargs = normalized.get("downstream_tool_kwargs")
        has_downstream_kwargs = isinstance(downstream_kwargs, dict) and bool(
            downstream_kwargs
        )
        if downstream_tool and has_downstream_kwargs and not abstain_reason:
            normalized["should_call_tool"] = True
            normalized["value"] = str(normalized.get("value") or selected_id)
            normalized["safety_notes"] = "call downstream ToolSandbox side-effect next"
        elif not downstream_tool and not abstain_reason:
            return_field = str(inputs.get("return_field", "")) if inputs else ""
            if not normalized.get("value"):
                normalized["value"] = str(
                    selected_record.get(return_field, selected_id)
                )
            normalized["should_call_tool"] = False
            normalized["safety_notes"] = "answer from value; no side effect needed"
    elif abstain_reason and not normalized.get("safety_notes"):
        normalized["safety_notes"] = "abstain; no safe unique action"

    return normalized


def _normalize_validation_abstention_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    def looks_like_phone(raw: Any) -> bool:
        text = str(raw or "").strip()
        digits = re.findall(r"\d", text)
        return len(digits) >= 7 and (
            text.startswith("+") or bool(re.search(r"[\d][\d\s().-]{6,}", text))
        )

    def to_capability(raw: Any) -> str:
        text = str(raw or "").strip()
        if text.startswith("functions."):
            text = text.split(".", 1)[1]
        normalized_text = text.lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "search_contacts": "contact_lookup",
            "remove_contact": "contact_removal",
            "delete_contact": "contact_removal",
            "modify_contact": "contact_update",
            "update_contact": "contact_update",
            "search_messages": "message_lookup",
            "send_message": "message_send",
            "send_message_with_phone_number": "message_send",
            "search_reminder": "reminder_lookup",
            "remove_reminder": "reminder_removal",
            "modify_reminder": "reminder_update",
            "add_reminder": "reminder_creation",
            "get_current_location": "location_lookup",
            "get_current_city": "location_lookup",
            "find_current_city": "location_lookup",
            "current_city": "location_lookup",
            "current_location": "location_lookup",
            "get_my_current_city": "location_lookup",
            "get_my_current_location": "location_lookup",
            "where_am_i": "location_lookup",
            "what_city_am_i_in": "location_lookup",
        }
        return mapping.get(text, mapping.get(normalized_text, text))

    normalized = dict(value)
    missing_information = [
        to_capability(item)
        for item in _dedupe_strings(normalized.get("missing_information"))
    ]
    required_original_tools = [
        to_capability(item)
        for item in _dedupe_strings(normalized.get("required_original_tools"))
    ]
    if not required_original_tools and inputs:
        required_original_tools = [
            to_capability(item)
            for item in _dedupe_strings(inputs.get("required_original_tools"))
        ]
    available_original_tools = (
        [
            to_capability(item)
            for item in _dedupe_strings(inputs.get("available_original_tools"))
        ]
        if inputs
        else []
    )
    action = to_capability((inputs or {}).get("requested_action"))
    user_request_lower = str((inputs or {}).get("user_request") or "").lower()
    target = str((inputs or {}).get("target_identifier") or "").strip()
    message_send_request = action == "message_send" or (
        bool(target)
        and any(
            token in user_request_lower
            for token in ("send", "text", "message", "ask", "tell")
        )
    )
    if message_send_request:
        if "message_send" not in required_original_tools:
            required_original_tools.append("message_send")
        if target and not looks_like_phone(target):
            _append_unique(required_original_tools, "contact_lookup")
    if action == "location_lookup" and "location_lookup" not in required_original_tools:
        required_original_tools.append("location_lookup")
    if not required_original_tools and any(
        phrase in user_request_lower
        for phrase in (
            "current city",
            "current location",
            "where am i",
            "what city am i",
            "which city am i",
        )
    ):
        action = "location_lookup"
        required_original_tools.append("location_lookup")
    missing_required_tools = [
        tool for tool in required_original_tools if tool not in available_original_tools
    ]
    for tool in missing_required_tools:
        _append_unique(missing_information, tool)
    try:
        visible_records_count = int((inputs or {}).get("visible_records_count") or 0)
    except (TypeError, ValueError):
        visible_records_count = 0
    stable_id_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    id_required_actions = {
        "contact_removal",
        "contact_update",
        "reminder_removal",
        "reminder_update",
        "remove_contact",
        "modify_contact",
        "remove_reminder",
        "modify_reminder",
    }
    if action in id_required_actions:
        target_is_stable_id = bool(stable_id_pattern.match(target))
        if not missing_required_tools and (
            not target or (visible_records_count <= 0 and not target_is_stable_id)
        ):
            _append_unique(missing_information, "target_identifier")
    normalized["missing_information"] = missing_information
    normalized["required_original_tools"] = required_original_tools

    should_abstain = bool(normalized.get("should_abstain"))
    missing_lower = {item.lower() for item in missing_information}
    if missing_information:
        should_abstain = True
    normalized["should_abstain"] = should_abstain

    if should_abstain:
        reason = str(normalized.get("abstain_reason") or "").strip()
        final_answer_recommendation = str(
            normalized.get("final_answer_recommendation") or ""
        ).strip()
        if missing_required_tools:
            reason = "missing_required_original_tool"
        elif "target_identifier" in missing_lower or "target" in missing_lower:
            reason = "missing_target_identifier"
        elif missing_information:
            reason = "missing_required_original_tool"
        normalized["safe_next_action"] = "ask_user_or_abstain"
        normalized["abstain_reason"] = reason or "insufficient_information"
        if action == "location_lookup" and "location_lookup" in missing_lower:
            final_answer_recommendation = (
                "I cannot determine what city you are in because I do not have "
                "access to your current location, GPS, or latitude and longitude "
                "coordinates."
            )
        elif message_send_request and "contact_lookup" in missing_lower:
            final_answer_recommendation = (
                "The recipient cannot be resolved to a phone number with the "
                "available information/tools."
            )
        normalized["final_answer_recommendation"] = (
            final_answer_recommendation
            or "I do not have enough information to complete the action."
        )
    else:
        normalized["missing_information"] = []
        normalized["safe_next_action"] = "continue_with_original_tool"
        normalized["final_answer_recommendation"] = ""
        normalized["abstain_reason"] = ""
    return normalized


def _normalize_state_precondition_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep state-action planner duplicate fields consistent with its sequence.

    State precondition tools return both an ordered ``action_sequence`` and a
    top-level next action for actor convenience. Model-authored tools often get
    the sequence right but leave one of the duplicated top-level fields blank.
    The public contract says the top-level action mirrors the first sequence
    item. When generated code abstains despite an unambiguous visible service
    blocker, this also repairs the contract by deriving the setting action from
    that visible error text.
    """

    normalized = dict(value)
    visible_text = " ".join(
        str((inputs or {}).get(key) or "")
        for key in ("user_request", "visible_state_or_error", "visible_state_summary")
    ).lower()

    def has_any(*markers: str) -> bool:
        return any(marker in visible_text for marker in markers)

    low_battery_already_off = any(
        marker in visible_text
        for marker in (
            "low battery mode is off",
            "low battery mode already off",
            "low battery mode is disabled",
            "low battery mode already disabled",
            "low battery=false",
            "low battery mode false",
        )
    )
    low_battery_needs_clear = not low_battery_already_off and has_any(
        "low battery mode is on",
        "low battery mode enabled",
        "low battery=true",
        "low battery mode true",
    )

    sequence = normalized.get("action_sequence")
    if not isinstance(sequence, list):
        sequence = []
        normalized["action_sequence"] = sequence

    if not sequence:
        inferred_sequence: list[dict[str, Any]] = []
        direct_state_actions = [
            (
                "set_cellular_service_status",
                True,
                "set_cellular_on",
                (
                    "turn on cellular",
                    "turn cellular on",
                    "enable cellular",
                    "turn on cellular service",
                    "turn cellular service on",
                    "enable cellular service",
                ),
            ),
            (
                "set_cellular_service_status",
                False,
                "set_cellular_off",
                (
                    "turn off cellular",
                    "turn cellular off",
                    "disable cellular",
                    "turn off cellular service",
                    "turn cellular service off",
                    "disable cellular service",
                ),
            ),
            (
                "set_wifi_status",
                True,
                "set_wifi_on",
                (
                    "turn on wifi",
                    "turn wifi on",
                    "enable wifi",
                    "turn on wi-fi",
                    "turn wi-fi on",
                    "enable wi-fi",
                ),
            ),
            (
                "set_wifi_status",
                False,
                "set_wifi_off",
                (
                    "turn off wifi",
                    "turn wifi off",
                    "disable wifi",
                    "turn off wi-fi",
                    "turn wi-fi off",
                    "disable wi-fi",
                ),
            ),
            (
                "set_location_service_status",
                True,
                "set_location_on",
                (
                    "turn on location",
                    "turn location on",
                    "enable location",
                    "turn on location service",
                    "turn location service on",
                    "enable location service",
                    "turn on location services",
                    "turn location services on",
                    "enable location services",
                ),
            ),
            (
                "set_location_service_status",
                False,
                "set_location_off",
                (
                    "turn off location",
                    "turn location off",
                    "disable location",
                    "turn off location service",
                    "turn location service off",
                    "disable location service",
                    "turn off location services",
                    "turn location services off",
                    "disable location services",
                ),
            ),
            (
                "set_low_battery_mode_status",
                True,
                "set_low_battery_on",
                (
                    "turn on low battery mode",
                    "turn low battery mode on",
                    "enable low battery mode",
                ),
            ),
            (
                "set_low_battery_mode_status",
                False,
                "set_low_battery_off",
                (
                    "turn off low battery mode",
                    "turn low battery mode off",
                    "disable low battery mode",
                ),
            ),
        ]
        for tool_name, on_value, reason, markers in direct_state_actions:
            if has_any(*markers):
                inferred_sequence.append(
                    {
                        "tool_name": tool_name,
                        "arguments": {"on": on_value},
                        "reason": reason,
                    }
                )
                break
        cellular_blocked = has_any(
            "cellular service is not enabled",
            "cellular service not enabled",
            "cellular service is disabled",
            "cellular service disabled",
            "cellular is not enabled",
            "cellular is disabled",
        )
        wifi_blocked = has_any(
            "wifi is not enabled",
            "wi-fi is not enabled",
            "wifi not enabled",
            "wi-fi not enabled",
            "wifi is disabled",
            "wi-fi is disabled",
            "wifi is off",
            "wi-fi is off",
        )
        location_blocked = has_any(
            "location service is not enabled",
            "location service not enabled",
            "location service is disabled",
            "location service disabled",
            "location is not enabled",
            "location is disabled",
            "permissionerror",
        )
        if inferred_sequence:
            pass
        elif cellular_blocked:
            if low_battery_needs_clear:
                inferred_sequence.append(
                    {
                        "tool_name": "set_low_battery_mode_status",
                        "arguments": {"on": False},
                        "reason": "clear_low_battery_before_enabling_service",
                    }
                )
            inferred_sequence.append(
                {
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "reason": "set_cellular_on",
                }
            )
        elif location_blocked:
            if not low_battery_already_off:
                inferred_sequence.append(
                    {
                        "tool_name": "set_low_battery_mode_status",
                        "arguments": {"on": False},
                        "reason": "clear_low_battery_before_enabling_service",
                    }
                )
            inferred_sequence.append(
                {
                    "tool_name": "set_location_service_status",
                    "arguments": {"on": True},
                    "reason": "set_location_on",
                }
            )
            if not has_any("wifi is on", "wifi already on", "wi-fi is on"):
                inferred_sequence.append(
                    {
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": True},
                        "reason": "enable_wifi_for_downstream_location_search",
                    }
                )
        elif wifi_blocked:
            inferred_sequence.append(
                {
                    "tool_name": "set_wifi_status",
                    "arguments": {"on": True},
                    "reason": "enable_wifi_for_downstream_task",
                }
            )
        if inferred_sequence:
            sequence = inferred_sequence
            normalized["action_sequence"] = inferred_sequence

    if isinstance(sequence, list):
        cleaned_sequence: list[Any] = []
        seen_actions: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
        for entry in sequence:
            if not isinstance(entry, dict):
                cleaned_sequence.append(entry)
                continue
            tool_name = str(entry.get("tool_name") or "").strip()
            arguments = entry.get("arguments")
            arguments_key = (
                tuple(sorted(arguments.items())) if isinstance(arguments, dict) else ()
            )
            if (
                low_battery_already_off
                and tool_name == "set_low_battery_mode_status"
                and isinstance(arguments, dict)
                and arguments.get("on") is False
            ):
                continue
            action_key = (tool_name, arguments_key)
            if action_key in seen_actions:
                continue
            seen_actions.add(action_key)
            cleaned_sequence.append(dict(entry))
        normalized["action_sequence"] = cleaned_sequence
        sequence = cleaned_sequence

    if isinstance(sequence, list) and sequence and isinstance(sequence[0], dict):
        first = dict(sequence[0])
        tool_name = str(first.get("tool_name") or "").strip()
        arguments = first.get("arguments")
        reason = str(first.get("reason") or "").strip()
        if tool_name:
            normalized["tool_name"] = tool_name
            normalized["should_call"] = True
        if isinstance(arguments, dict):
            normalized["arguments"] = arguments
        if reason:
            normalized["reason"] = reason
        normalized["abstain_reason"] = ""

    final_response = str(normalized.get("final_response_recommendation") or "").strip()
    structured_target = str((inputs or {}).get("target_service") or "").strip().lower()
    structured_desired_on = (inputs or {}).get("desired_on")
    structured_resume = bool((inputs or {}).get("resume_original_task"))
    structured_labels = {
        "wifi": "Wifi",
        "cellular": "Cellular service",
        "location": "Location service",
        "low_battery": "Low battery mode",
    }
    if (
        sequence
        and structured_target in structured_labels
        and isinstance(structured_desired_on, bool)
    ):
        if structured_resume:
            final_response = "continue_original_task"
        else:
            state = "on" if structured_desired_on else "off"
            final_response = (
                f"{structured_labels[structured_target]} has been turned {state}."
            )
        normalized["final_response_recommendation"] = final_response
    if final_response in {"Device state has been updated.", "Completed action."}:
        final_response = ""
    direct_setting_request = any(
        marker in visible_text
        for marker in (
            "turn on wifi",
            "turn wifi on",
            "enable wifi",
            "turn off wifi",
            "turn wifi off",
            "disable wifi",
            "turn on cellular",
            "turn cellular on",
            "enable cellular",
            "turn off cellular",
            "turn cellular off",
            "disable cellular",
            "turn on location",
            "turn location on",
            "enable location",
            "turn off location",
            "turn location off",
            "disable location",
        )
    )
    downstream_precondition = (not direct_setting_request) and (
        "permissionerror" in visible_text
        or "not enabled" in visible_text
        or "is disabled" in visible_text
        or any(
            marker in visible_text
            for marker in (
                "send ",
                "text ",
                "message",
                "add a reminder",
                "set a reminder",
                "remind me",
                "find ",
                "search",
                "look up",
                "weather",
                "distance",
                "holiday",
            )
        )
    )
    if downstream_precondition and isinstance(sequence, list) and sequence:
        final_response = "continue_original_task"
        normalized["final_response_recommendation"] = final_response
    if not final_response and isinstance(sequence, list) and sequence:
        last_action = sequence[-1] if isinstance(sequence[-1], dict) else {}
        last_tool = str(last_action.get("tool_name") or "")
        last_args = last_action.get("arguments")
        if isinstance(last_args, dict) and "on" in last_args:
            suffix = "on." if bool(last_args.get("on")) else "off."
            if last_tool == "set_wifi_status":
                final_response = f"Wifi has been turned {suffix}"
            elif last_tool == "set_cellular_service_status":
                final_response = f"Cellular service has been turned {suffix}"
            elif last_tool == "set_location_service_status":
                final_response = f"Location service has been turned {suffix}"
            elif last_tool == "set_low_battery_mode_status":
                final_response = f"Low battery mode has been turned {suffix}"
            normalized["final_response_recommendation"] = final_response

    if structured_resume or final_response == "continue_original_task":
        normalized["continue_original_task_after_sequence"] = True
    elif final_response:
        normalized["continue_original_task_after_sequence"] = False

    return normalized


def _has_complete_coordinates(inputs: dict[str, Any] | None) -> bool:
    if not inputs:
        return False
    try:
        latitude = float(inputs.get("latitude"))
        longitude = float(inputs.get("longitude"))
    except (TypeError, ValueError):
        return False
    return (
        bool(inputs.get("location_available")) and latitude != 0.0 and longitude != 0.0
    )


def _timestamp_source_from_inputs(inputs: dict[str, Any] | None, fallback: Any) -> str:
    if not inputs:
        return str(fallback or "none")
    current_info = inputs.get("current_datetime_info")
    if isinstance(current_info, dict) and {
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
    } <= set(current_info):
        return "current_datetime_info"
    try:
        resolved = float(inputs.get("resolved_reminder_timestamp"))
    except (TypeError, ValueError):
        resolved = 0.0
    if resolved > 0.0:
        return "resolved"
    return str(fallback or "none")


def _strip_attached_location_from_reminder_content(content: Any) -> str:
    text = re.sub(r"\s+", " ", str(content or "").strip())
    if not text:
        return text
    stripped = re.sub(
        r"\s+(?:at|near|by|in)\s+[^.!?]+$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ,.;:")
    return stripped or text


def _has_concrete_coordinates(inputs: dict[str, Any] | None) -> bool:
    if not inputs or not bool(inputs.get("location_available")):
        return False
    try:
        latitude = float(inputs.get("latitude"))
        longitude = float(inputs.get("longitude"))
    except (TypeError, ValueError):
        return False
    return latitude != 0.0 and longitude != 0.0


def _relative_reminder_timestamp(inputs: dict[str, Any] | None) -> float | None:
    if not inputs:
        return None
    try:
        resolved = float(inputs.get("resolved_reminder_timestamp"))
    except (TypeError, ValueError):
        resolved = 0.0
    if resolved > 0.0:
        return resolved
    current_info = inputs.get("current_datetime_info")
    if not isinstance(current_info, dict) or not current_info:
        return None
    try:
        current_timestamp = float(inputs.get("current_timestamp"))
        day_offset = int(inputs.get("day_offset"))
        target_hour = int(inputs.get("hour"))
        target_minute = int(inputs.get("minute"))
        current_hour = int(current_info.get("hour"))
        current_minute = int(current_info.get("minute"))
        current_second = int(current_info.get("second"))
    except (TypeError, ValueError):
        return None
    if not (0 <= target_hour <= 23 and 0 <= target_minute <= 59):
        return None
    local_midnight = (
        int(current_timestamp)
        - current_hour * 3600
        - current_minute * 60
        - current_second
    )
    return float(
        local_midnight + day_offset * 86400 + target_hour * 3600 + target_minute * 60
    )


def _normalize_reminder_creation_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Normalize reminder argument-prep outputs to the side-effect contract.

    The generated tool may prepare arguments for the original add_reminder tool,
    or it may abstain because required visible inputs are missing. It must not do
    both. This keeps model-authored tools conservative without inventing
    benchmark-specific answers.
    """

    normalized = _strip_null_values_from_generated_kwargs(dict(value))
    abstain_reason = _normalize_abstain_reason(normalized.get("abstain_reason"))
    concrete_coordinates = _has_concrete_coordinates(inputs)
    if bool((inputs or {}).get("location_required")) and not concrete_coordinates:
        abstain_reason = "required_location_unresolved"
        normalized["location_status"] = "required_missing"
    elif (
        bool((inputs or {}).get("location_requested"))
        and not concrete_coordinates
        and not bool((inputs or {}).get("location_lookup_failed"))
    ):
        abstain_reason = "optional_location_lookup_pending_do_not_call_add_reminder"
        normalized["location_status"] = "lookup_pending"

    kwargs_for_time_check = normalized.get("add_reminder_kwargs")
    if not isinstance(kwargs_for_time_check, dict):
        kwargs_for_time_check = {}
    else:
        kwargs_for_time_check = dict(kwargs_for_time_check)
    if bool(normalized.get("should_call_add_reminder")) and not abstain_reason:
        try:
            has_prepared_timestamp = (
                float(kwargs_for_time_check.get("reminder_timestamp")) > 0.0
            )
        except (TypeError, ValueError):
            has_prepared_timestamp = False
        if not has_prepared_timestamp:
            recovered_timestamp = _relative_reminder_timestamp(inputs)
            if recovered_timestamp is not None:
                kwargs_for_time_check["reminder_timestamp"] = recovered_timestamp
                if not str(kwargs_for_time_check.get("content") or "").strip():
                    kwargs_for_time_check["content"] = str(
                        (inputs or {}).get("content") or ""
                    ).strip()
                normalized["add_reminder_kwargs"] = kwargs_for_time_check

    current_info = (inputs or {}).get("current_datetime_info")
    has_current_info = isinstance(current_info, dict) and {
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
    } <= set(current_info)
    relative_fields_present = all(
        (inputs or {}).get(key) is not None
        for key in ("current_timestamp", "day_offset", "hour", "minute")
    )
    needs_datetime_info = (
        relative_fields_present
        and not has_current_info
        and (inputs or {}).get("local_utc_offset_hours") is None
        and (inputs or {}).get("resolved_reminder_timestamp") is None
    )
    if needs_datetime_info:
        abstain_reason = "missing_current_datetime_info_call_timestamp_to_datetime_info"
    has_prepared_timestamp = False
    if isinstance(kwargs_for_time_check, dict):
        try:
            has_prepared_timestamp = (
                float(kwargs_for_time_check.get("reminder_timestamp")) > 0.0
            )
        except (TypeError, ValueError):
            has_prepared_timestamp = False
    if (
        not abstain_reason
        and bool(normalized.get("should_call_add_reminder"))
        and not has_prepared_timestamp
        and (inputs or {}).get("resolved_reminder_timestamp") is None
        and not relative_fields_present
    ):
        abstain_reason = "missing_time_info"
    if (
        not abstain_reason
        and bool(normalized.get("should_call_add_reminder"))
        and not has_prepared_timestamp
    ):
        abstain_reason = "invalid_resolved_timestamp_requires_numeric_unix_time"
    should_call = (
        bool(normalized.get("should_call_add_reminder")) and not abstain_reason
    )

    if not should_call:
        normalized["should_call_add_reminder"] = False
        normalized["add_reminder_kwargs"] = {}
        if abstain_reason:
            normalized["abstain_reason"] = abstain_reason
        normalized["timestamp_source"] = _timestamp_source_from_inputs(
            inputs,
            normalized.get("timestamp_source"),
        )
        return normalized

    kwargs = normalized.get("add_reminder_kwargs")
    if not isinstance(kwargs, dict):
        kwargs = {}
    else:
        kwargs = dict(kwargs)
    if bool((inputs or {}).get("location_requested")) and _has_complete_coordinates(
        inputs
    ):
        kwargs["content"] = _strip_attached_location_from_reminder_content(
            kwargs.get("content") or (inputs or {}).get("content")
        )
        kwargs["latitude"] = float((inputs or {}).get("latitude"))
        kwargs["longitude"] = float((inputs or {}).get("longitude"))
        normalized["location_status"] = "provided"
    elif not str(normalized.get("location_status") or "").strip():
        normalized["location_status"] = "omitted_optional"
    normalized["add_reminder_kwargs"] = _strip_null_values_from_generated_kwargs(kwargs)
    normalized["abstain_reason"] = ""
    normalized["timestamp_source"] = _timestamp_source_from_inputs(
        inputs,
        normalized.get("timestamp_source"),
    )
    return normalized


def _format_scalar_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return (f"{number:.6f}").rstrip("0").rstrip(".")
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer() and re.fullmatch(r"[-+]?\d+(?:\.0+)?", text):
        return str(int(number))
    return (f"{number:.6f}").rstrip("0").rstrip(".")


def _display_unit(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.lower().replace("degrees", "").replace("degree", "").strip()
    aliases = {
        "c": "Celsius",
        "celsius": "Celsius",
        "centigrade": "Celsius",
        "f": "Fahrenheit",
        "fahrenheit": "Fahrenheit",
        "km": "kilometers",
        "kilometer": "kilometers",
        "kilometers": "kilometers",
        "kilometre": "kilometers",
        "kilometres": "kilometers",
        "mi": "miles",
        "mile": "miles",
        "miles": "miles",
    }
    return aliases.get(normalized, text)


def _unit_conversion_unit(value: Any) -> str:
    unit = _display_unit(value)
    if unit in {"Celsius", "Fahrenheit"}:
        return unit.lower()
    return unit


def _first_visible_payload(inputs: dict[str, Any] | None) -> dict[str, Any]:
    if not inputs:
        return {}
    raw = inputs.get("service_payload") or inputs.get("payload")
    if isinstance(raw, dict):
        result = raw.get("result")
        if isinstance(result, dict):
            merged = dict(result)
            for key, value in raw.items():
                if key != "result" and key not in merged:
                    merged[key] = value
            return merged
        return dict(raw)
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                return dict(item)
        for item in raw:
            if item is not None and str(item).strip():
                return {"result": item}
    if raw is not None and str(raw).strip():
        return {"result": raw}
    return {}


def _visible_payload_temperature_value(payload: dict[str, Any]) -> Any:
    for key in (
        "current_temperature",
        "temperature",
        "average_temperature",
        "high_temperature",
        "low_temperature",
        "value",
        "result",
    ):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _normalize_derived_value_output(
    value: dict[str, Any],
    *,
    inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep derived-value tool contract fields internally consistent.

    Model-authored tools sometimes make the correct visible-data decision while
    leaving duplicated convenience fields blank. This fills only fields that are
    directly recoverable from the returned downstream call or visible inputs.
    """

    normalized = _strip_null_values_from_generated_kwargs(dict(value))
    output_keys = set(normalized)
    if (
        not {
            "answer_value",
            "answer_kind",
            "answer_unit",
            "should_call_downstream_tool",
            "downstream_tool_name",
            "downstream_tool_kwargs",
            "exact_final_answer",
            "final_answer_recommendation",
            "copy_exactly",
            "abstain_reason",
        }
        <= output_keys
    ):
        return normalized

    payload = _first_visible_payload(inputs)
    downstream_kwargs = normalized.get("downstream_tool_kwargs")
    if not isinstance(downstream_kwargs, dict):
        downstream_kwargs = {}
        normalized["downstream_tool_kwargs"] = downstream_kwargs

    normalized["abstain_reason"] = _normalize_abstain_reason(
        normalized.get("abstain_reason")
    )
    if normalized["abstain_reason"]:
        return normalized

    answer_kind = str(normalized.get("answer_kind") or "").strip()
    downstream_tool = str(normalized.get("downstream_tool_name") or "").strip()
    should_convert = bool(normalized.get("should_call_downstream_tool")) and (
        downstream_tool == "unit_conversion"
        or set(downstream_kwargs) >= {"from_unit", "to_unit"}
    )

    if should_convert:
        if not str(normalized.get("answer_value") or "").strip():
            normalized["answer_value"] = _format_scalar_value(
                downstream_kwargs.get("amount")
            )
        if not answer_kind and {
            str(downstream_kwargs.get("from_unit") or "").lower(),
            str(downstream_kwargs.get("to_unit") or "").lower(),
        } & {"celsius", "fahrenheit"}:
            normalized["answer_kind"] = "temperature"
            answer_kind = "temperature"
        if not str(normalized.get("answer_unit") or "").strip():
            normalized["answer_unit"] = _display_unit(
                downstream_kwargs.get("from_unit")
            )
        if downstream_kwargs.get("from_unit") is not None:
            downstream_kwargs["from_unit"] = _unit_conversion_unit(
                downstream_kwargs.get("from_unit")
            )
        if downstream_kwargs.get("to_unit") is not None:
            downstream_kwargs["to_unit"] = _unit_conversion_unit(
                downstream_kwargs.get("to_unit")
            )
        normalized["downstream_tool_kwargs"] = downstream_kwargs
        normalized["exact_final_answer"] = str(
            normalized.get("exact_final_answer") or ""
        )
        normalized["final_answer_recommendation"] = str(
            normalized.get("final_answer_recommendation") or ""
        )
        normalized["copy_exactly"] = False
        normalized["abstain_reason"] = _normalize_abstain_reason(
            normalized.get("abstain_reason")
        )
        return normalized

    if not str(normalized.get("answer_value") or "").strip():
        visible_value = _visible_payload_temperature_value(payload)
        if visible_value is not None:
            normalized["answer_value"] = _format_scalar_value(visible_value)
    if not answer_kind and str(normalized.get("answer_value") or "").strip():
        if any(
            key in payload for key in ("current_temperature", "temperature", "result")
        ):
            normalized["answer_kind"] = "temperature"
            answer_kind = "temperature"

    if answer_kind in {"temperature", "current_temperature"}:
        if not str(normalized.get("answer_unit") or "").strip():
            normalized["answer_unit"] = _display_unit(
                (inputs or {}).get("requested_unit")
                or payload.get("temperature_unit")
                or payload.get("unit")
            )
        value_text = _format_scalar_value(normalized.get("answer_value"))
        unit_text = _display_unit(normalized.get("answer_unit"))
        subject = str((inputs or {}).get("answer_subject") or "").strip()
        if value_text and unit_text:
            if subject:
                final = (
                    f"The current temperature in {subject} is {value_text} {unit_text}."
                )
            else:
                final = f"{value_text} {unit_text}"
            existing_final = str(
                normalized.get("final_answer_recommendation") or ""
            ).strip()
            if not existing_final or re.search(r"\s+\.$", existing_final):
                normalized["exact_final_answer"] = final
                normalized["final_answer_recommendation"] = final
                normalized["copy_exactly"] = True
            elif not str(normalized.get("exact_final_answer") or "").strip():
                normalized["exact_final_answer"] = existing_final

    normalized["abstain_reason"] = _normalize_abstain_reason(
        normalized.get("abstain_reason")
    )
    return normalized


def normalize_generated_tool_output(
    tool: GeneratedTool,
    value: Any,
    *,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Normalize generated helper output to its family safety contract.

    Search-filter helpers must never select a concrete record when their own
    output says the case is ambiguous. If possible, reconstruct the full tied
    candidate list from visible input records so validation/runtime behavior is
    deterministic and side-effect safe.
    """
    if not isinstance(value, dict):
        return value
    from sage_ts.generation.complete_tools import native_action_tool_enabled

    if native_action_tool_enabled(tool):
        return value
    value = _strip_null_values_from_generated_kwargs(value)
    if tool.spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        return _normalize_state_precondition_output(value, inputs=inputs)
    if tool.spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        if tool.spec.tool_name == "prepare_reminder_creation_args":
            return _normalize_reminder_creation_output(value, inputs=inputs)
        if tool.spec.tool_name == "plan_contact_relationship_batch_update":
            return _normalize_contact_relationship_batch_output(value, inputs=inputs)
        output_schema = tool.spec.output_schema or {}
        output_props = output_schema.get("properties", {})
        if isinstance(output_props, dict) and not {
            "selected_record",
            "selected_id",
            "value",
            "downstream_tool_name",
            "downstream_tool_kwargs",
            "should_call_tool",
            "abstain_reason",
        } <= set(output_props):
            return _normalize_generic_composite_output(value, inputs=inputs)
        if isinstance(output_props, dict) and {
            "selected_record",
            "selected_id",
            "value",
            "downstream_tool_name",
            "downstream_tool_kwargs",
            "should_call_tool",
            "abstain_reason",
        } <= set(output_props):
            return _normalize_composite_workflow_output(value, inputs=inputs)
        return value
    if tool.spec.family == ToolFamily.VALIDATION_ABSTENTION_HELPER:
        return _normalize_validation_abstention_output(value, inputs=inputs)
    if tool.spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR:
        return _normalize_derived_value_output(value, inputs=inputs)
    if tool.spec.family != ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        return value

    output_schema = tool.spec.output_schema or {}
    output_props = output_schema.get("properties", {})
    if not isinstance(output_props, dict) or not {
        "selected_id",
        "value",
        "tie_candidates",
    } <= set(output_props):
        return value

    normalized = dict(value)
    normalized["matched_constraints"] = _dedupe_strings(
        normalized.get("matched_constraints")
    )
    abstain_reason = str(normalized.get("abstain_reason", "")).lower()
    existing_ties = normalized.get("tie_candidates")
    tie_candidates = list(existing_ties) if isinstance(existing_ties, list) else []
    ambiguous = any(
        token in abstain_reason
        for token in ("ambig", "tie", "multiple_match", "multiple match")
    )
    if not ambiguous:
        return normalized

    inferred_matches = _infer_matching_records(inputs)
    if len(inferred_matches) > 1:
        tie_candidates = inferred_matches
    else:
        selected_record = normalized.get("selected_record")
        if isinstance(selected_record, dict) and selected_record:
            tie_candidates = [dict(selected_record), *tie_candidates]

    normalized["selected_record"] = {}
    normalized["selected_index"] = -1
    normalized["selected_id"] = ""
    normalized["value"] = ""
    normalized["tie_candidates"] = tie_candidates
    if (
        not normalized.get("matched_constraints")
        and inputs
        and inputs.get("field_name")
    ):
        normalized["matched_constraints"] = [str(inputs["field_name"])]
    if not normalized.get("abstain_reason"):
        normalized["abstain_reason"] = "ambiguous_multiple_matches"
    return normalized
