from pathlib import Path

from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.tool_invoker import invoke_registered_tool
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


def _evidence(summary: str, *signals: str) -> StructuredInadequacyEvidence:
    return StructuredInadequacyEvidence(summary=summary, signals=signals)


def _wifi_canonicalizer() -> GeneratedTool:
    spec = ToolSpec(
        tool_name="canonicalize_connectivity_label",
        family=ToolFamily.CANONICALIZER,
        description="Normalize connectivity labels to stable internal labels.",
        inputs=(ToolInput("label", "str", "Raw user-facing connectivity label."),),
        output_annotation="str",
        generalization_rationale=(
            "Connectivity labels recur across scenarios with spacing and punctuation "
            "differences, so a deterministic normalizer can transfer."
        ),
        inadequacy_evidence=_evidence(
            "The base tool list exposes state setters and getters, but not a reusable "
            "canonicalization helper for noisy connectivity labels.",
            "visible_raw_data_lacking_deterministic_transform",
        ),
    )
    code = """
def canonicalize_connectivity_label(label: str) -> str:
    cleaned = label.strip().lower().replace("-", " ").replace("_", " ")
    cleaned = " ".join(cleaned.split())
    if cleaned in {"wi fi", "wifi", "wireless"}:
        return "wifi"
    if cleaned in {"cell", "cellular", "mobile data"}:
        return "cellular"
    return cleaned
"""
    return GeneratedTool(spec=spec, code=code)


def test_generated_tool_birth_reuse_and_success_flip(tmp_path: Path) -> None:
    tool = _wifi_canonicalizer()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular"),
        ),
    )
    assert validation.accepted

    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))

    raw_label: str = "Wi Fi"
    expected_label: str = "wifi"
    baseline_later_success = raw_label == expected_label
    normalized = invoke_registered_tool(
        store,
        "canonicalize_connectivity_label",
        {"label": raw_label},
        success_flip=not baseline_later_success,
    )

    assert normalized == expected_label
    entry = store.get("canonicalize_connectivity_label")
    assert entry is not None
    assert entry.reuse_count == 1
    assert entry.success_flips == 1


def test_generated_tool_validation_allows_safe_filter_builtin() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_contact_by_constraint",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select exactly one contact by a normalized field match.",
            inputs=(
                ToolInput(
                    "records_payload",
                    "dict",
                    "Dictionary containing a records list of contact dictionaries.",
                ),
                ToolInput("field_name", "str", "Contact field to match."),
                ToolInput("expected_value", "str", "Expected field value."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                },
            },
            positive_triggers=("wrong_selected_record",),
            negative_triggers=("ambiguous_match", "no_match"),
            abstain_behavior=(
                "Return {} when there is not exactly one normalized match, ties remain, "
                "or the candidate set is empty."
            ),
            generalization_rationale=(
                "Contact lookup tasks repeatedly need deterministic candidate selection "
                "from search_contacts output before a downstream action."
            ),
            inadequacy_evidence=_evidence(
                "The base contact search returns candidate rows but does not provide "
                "a deterministic selector for exact normalized field matching.",
                "wrong_selected_record",
            ),
        ),
        code="""
def select_contact_by_constraint(records_payload: dict, field_name: str, expected_value: str) -> dict:
    matches = []
    expected_value = expected_value.strip().lower() if field_name == 'name' else ''.join(filter(str.isdigit, expected_value))
    for record in records_payload['records']:
        if field_name == 'name':
            if record['name'].strip().lower() == expected_value:
                matches.append(record)
        elif field_name == 'phone_number':
            normalized_phone = ''.join(filter(str.isdigit, record['phone_number']))
            if normalized_phone == expected_value:
                matches.append(record)
        elif field_name == 'relationship':
            if record['relationship'].lower() == expected_value:
                matches.append(record)
    return matches[0] if len(matches) == 1 else {}
""",
    )

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {
                                "name": "Ada Lovelace",
                                "person_id": "a",
                                "phone_number": "+1 (555) 0100",
                            },
                            {
                                "name": "Grace Hopper",
                                "person_id": "b",
                                "phone_number": "+1 (555) 0200",
                            },
                        ]
                    },
                    "field_name": "phone_number",
                    "expected_value": "15550200",
                },
                {
                    "name": "Grace Hopper",
                    "person_id": "b",
                    "phone_number": "+1 (555) 0200",
                },
            ),
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"person_id": "a", "relationship": "friend"},
                            {"person_id": "b", "relationship": "friend"},
                        ]
                    },
                    "field_name": "relationship",
                    "expected_value": "friend",
                },
                {},
                held_out=True,
            ),
            ToolExample(
                {
                    "records_payload": {"records": []},
                    "field_name": "name",
                    "expected_value": "Ada",
                },
                {},
                negative_applicability=True,
            ),
        ),
    )

    assert validation.accepted


def test_generated_tool_validation_allows_safe_lambda_sort_key() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="select_record_by_timestamp_extreme",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select the oldest or latest record by timestamp with deterministic tie handling.",
            inputs=(
                ToolInput("records_payload", "dict", "Records payload."),
                ToolInput("timestamp_key", "str", "Timestamp field."),
                ToolInput("selection_mode", "str", "oldest or latest."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                },
            },
            positive_triggers=("visible_candidate_list_wrong_selected_record",),
            negative_triggers=("no_valid_timestamp_candidates", "timestamp_tie"),
            abstain_behavior=(
                "Return {} when no valid timestamped candidate exists or timestamp ties "
                "make the selection ambiguous."
            ),
            generalization_rationale=(
                "Record-ranking tasks repeatedly need deterministic timestamp extrema."
            ),
            inadequacy_evidence=_evidence(
                "Base search tools return candidates but not a reusable timestamp ranker.",
                "wrong_selected_record",
            ),
        ),
        code="""
def select_record_by_timestamp_extreme(records_payload: dict, timestamp_key: str, selection_mode: str) -> dict:
    records = records_payload.get('records', [])
    valid = [record for record in records if isinstance(record.get(timestamp_key), (int, float))]
    if not valid:
        return {}
    reverse = selection_mode.strip().lower() == 'latest'
    return sorted(valid, key=lambda record: record[timestamp_key], reverse=reverse)[0]
""",
    )

    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"content": "old", "creation_timestamp": 10.0},
                            {"content": "new", "creation_timestamp": 20.0},
                        ]
                    },
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {"content": "new", "creation_timestamp": 20.0},
            ),
            ToolExample(
                {
                    "records_payload": {"records": [{"content": "missing"}]},
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {},
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"content": "old", "creation_timestamp": 10.0},
                            {"content": "new", "creation_timestamp": 20.0},
                        ]
                    },
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "oldest",
                },
                {"content": "old", "creation_timestamp": 10.0},
                held_out=True,
            ),
        ),
    )

    assert validation.accepted


def test_generated_tool_validation_rejects_dangerous_call_inside_lambda() -> None:
    safety = check_ast_safety(
        """
def bad_helper(records_payload: dict) -> dict:
    return sorted(records_payload.get('records', []), key=lambda record: eval('1'))[0]
"""
    )

    assert not safety.safe
    assert "denied_call:eval" in safety.errors
