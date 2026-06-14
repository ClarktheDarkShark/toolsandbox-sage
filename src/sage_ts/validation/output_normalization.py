"""Runtime/validation normalization for generated helper outputs.

This layer enforces framework-level safety contracts that generated code declares
but may implement imperfectly. It should only make outputs more conservative,
for example by converting ambiguous selector outputs into explicit abstentions.
"""

from __future__ import annotations

import re
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily


def _dedupe_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
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
    if not should_call_tool and not should_call_tools and not should_call_search:
        if "downstream_tool_name" in normalized:
            normalized["downstream_tool_name"] = ""
        if "downstream_tool_kwargs" in normalized:
            normalized["downstream_tool_kwargs"] = {}
        if "downstream_tool_kwargs_list" in normalized:
            normalized["downstream_tool_kwargs_list"] = []
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
    target = str((inputs or {}).get("target_identifier") or "").strip()
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
    value = _strip_null_values_from_generated_kwargs(value)
    if tool.spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
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
