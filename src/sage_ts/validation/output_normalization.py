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
    field_name = str(inputs.get("field_name", ""))
    if not isinstance(records, list) or not field_name:
        return []
    if "expected_value" in inputs:
        expected = inputs.get("expected_value")
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
    if tool.spec.family != ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        return value
    if not isinstance(value, dict):
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
