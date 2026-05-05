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
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


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
    normalized = dict(value)
    selected_record = normalized.get("selected_record")
    if not isinstance(selected_record, dict):
        selected_record = {}
        normalized["selected_record"] = selected_record

    abstain_reason = str(normalized.get("abstain_reason", "")).lower()
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
    if tool.spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        output_schema = tool.spec.output_schema or {}
        output_props = output_schema.get("properties", {})
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
