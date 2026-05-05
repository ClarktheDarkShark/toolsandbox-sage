from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


def _flawed_selector_tool() -> GeneratedTool:
    spec = ToolSpec(
        tool_name="select_visible_record_by_constraints",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select one visible record by a constraint and abstain on tie or "
            "ambiguous multiple match cases."
        ),
        inputs=(
            ToolInput("records", "list", "Visible candidate records."),
            ToolInput("field_name", "str", "Visible field to match."),
            ToolInput("expected_value", "str", "Expected field value."),
            ToolInput("return_field", "str", "Field to return."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "selected_index": {"type": "integer"},
                "selected_id": {"type": "string"},
                "value": {"type": "string"},
                "matched_constraints": {"type": "array"},
                "tie_candidates": {"type": "array"},
                "abstain_reason": {"type": "string"},
            },
        },
        positive_triggers=("visible records and one exact field match",),
        negative_triggers=("no records", "ambiguous multiple matches", "tie"),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts",),
        abstain_behavior="Return empty selected_record on tie or ambiguity.",
        generalization_rationale=(
            "Visible-record constraint selection recurs across contact and message tasks."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup", "message_lookup"),
        reason_tool_is_decisive=(
            "It turns search results plus user constraints into a safe selected record."
        ),
        shortfall_cluster_evidence=(
            "search_filter:select_visible_record_by_constraints",
        ),
        known_failure_mechanisms_addressed=("wrong_selected_record",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Agents repeatedly fail to select the correct visible record safely.",
            signals=("wrong_selected_record", "visible_info_unused"),
        ),
    )
    code = """
def select_visible_record_by_constraints(records: list, field_name: str, expected_value: str, return_field: str) -> dict:
    matches = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        if field_name not in record:
            continue
        left = str(record.get(field_name, '')).strip().lower()
        right = str(expected_value).strip().lower()
        if left == right:
            matches.append((index, record))
    if len(matches) == 1:
        index, record = matches[0]
        selected_id = str(record.get('person_id', record.get('id', '')))
        value = str(record.get(return_field, selected_id))
        return {'selected_record': record, 'selected_index': index, 'selected_id': selected_id, 'value': value, 'matched_constraints': [field_name], 'tie_candidates': [], 'abstain_reason': ''}
    if len(matches) > 1:
        return {'selected_record': {}, 'selected_index': 0, 'selected_id': 'a', 'value': 'a', 'matched_constraints': [field_name, field_name], 'tie_candidates': [matches[1][1]], 'abstain_reason': 'ambiguous_multiple_matches'}
    return {'selected_record': {}, 'selected_index': -1, 'selected_id': '', 'value': '', 'matched_constraints': [], 'tie_candidates': [], 'abstain_reason': 'no_match'}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def test_selector_output_normalization_enforces_ambiguity_abstention() -> None:
    tool = _flawed_selector_tool()
    inputs = {
        "records": [
            {"person_id": "a", "relationship": "friend"},
            {"person_id": "b", "relationship": "friend"},
        ],
        "field_name": "relationship",
        "expected_value": "friend",
        "return_field": "person_id",
    }
    raw = {
        "selected_record": {},
        "selected_index": 0,
        "selected_id": "a",
        "value": "a",
        "matched_constraints": ["relationship", "relationship"],
        "tie_candidates": [{"person_id": "b", "relationship": "friend"}],
        "abstain_reason": "ambiguous_multiple_matches",
    }

    normalized = normalize_generated_tool_output(tool, raw, inputs=inputs)

    assert normalized == {
        "selected_record": {},
        "selected_index": -1,
        "selected_id": "",
        "value": "",
        "matched_constraints": ["relationship"],
        "tie_candidates": [
            {"person_id": "a", "relationship": "friend"},
            {"person_id": "b", "relationship": "friend"},
        ],
        "abstain_reason": "ambiguous_multiple_matches",
    }


def test_selector_validation_uses_normalized_ambiguity_output() -> None:
    tool = _flawed_selector_tool()
    examples = (
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "name": "Ada"},
                    {"person_id": "b", "name": "Grace"},
                ],
                "field_name": "name",
                "expected_value": "Grace",
                "return_field": "person_id",
            },
            {
                "selected_record": {"person_id": "b", "name": "Grace"},
                "selected_index": 1,
                "selected_id": "b",
                "value": "b",
                "matched_constraints": ["name"],
                "tie_candidates": [],
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "records": [{"person_id": "a", "name": "Ada"}],
                "field_name": "name",
                "expected_value": "Ada",
                "return_field": "person_id",
            },
            {
                "selected_record": {"person_id": "a", "name": "Ada"},
                "selected_index": 0,
                "selected_id": "a",
                "value": "a",
                "matched_constraints": ["name"],
                "tie_candidates": [],
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
                ],
                "field_name": "relationship",
                "expected_value": "friend",
                "return_field": "person_id",
            },
            {
                "selected_record": {},
                "selected_index": -1,
                "selected_id": "",
                "value": "",
                "matched_constraints": ["relationship"],
                "tie_candidates": [
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
                ],
                "abstain_reason": "ambiguous_multiple_matches",
            },
            negative_applicability=True,
        ),
    )

    result = validate_generated_tool(tool, examples)

    assert result.accepted, result.errors
