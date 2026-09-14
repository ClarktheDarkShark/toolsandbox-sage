import json
from pathlib import Path

import pytest

from sage_ts.adequacy.inadequacy_classifier import (
    _safe_action_or_abstain_observation,
)
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    _action_requires_target,
    _recommendation_mentions_fact,
    validate_generated_tool,
)


def _abstention_tool(code: str) -> GeneratedTool:
    return GeneratedTool(
        spec=ToolSpec(
            tool_name="safe_record_action_gate",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            description="Decide whether a record action has safe visible inputs.",
            inputs=(
                ToolInput("user_request", "str", "Visible user request."),
                ToolInput("requested_action", "str", "Requested record action."),
                ToolInput("target_identifier", "str", "Visible target identifier."),
                ToolInput("required_original_tools", "list", "Required capabilities."),
                ToolInput(
                    "available_original_tools", "list", "Available capabilities."
                ),
                ToolInput("visible_records_count", "int", "Visible record count."),
            ),
            output_annotation="dict",
            positive_triggers=("missing capability", "missing target", "ambiguity"),
            negative_triggers=("complete safe request",),
            generalization_rationale=(
                "Record actions repeatedly require the same visible dependency and "
                "target checks before execution."
            ),
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary=(
                    "Visible record actions can be unsafe when a prerequisite or "
                    "unique target is absent."
                ),
                signals=("missing_precondition", "ambiguous_target"),
            ),
        ),
        code=code,
    )


def _examples() -> tuple[ToolExample, ...]:
    return (
        ToolExample(
            {
                "user_request": "Archive the labelled record.",
                "requested_action": "archive_record",
                "target_identifier": "labelled-record",
                "required_original_tools": ["record_lookup"],
                "available_original_tools": [],
                "visible_records_count": 0,
            },
            {
                "should_abstain": True,
                "missing_information": ["record_lookup"],
                "required_original_tools": ["record_lookup"],
                "safe_next_action": "ask_user_or_abstain",
                "final_answer_recommendation": (
                    "Record lookup is unavailable, so the action cannot continue."
                ),
                "abstain_reason": "missing_required_original_tool",
            },
        ),
        ToolExample(
            {
                "user_request": "Archive the labelled record.",
                "requested_action": "archive_record",
                "target_identifier": "labelled-record",
                "required_original_tools": ["record_lookup", "record_archive"],
                "available_original_tools": ["record_lookup", "record_archive"],
                "visible_records_count": 1,
            },
            {
                "should_abstain": False,
                "missing_information": [],
                "required_original_tools": ["record_lookup", "record_archive"],
                "safe_next_action": "continue_with_original_tool",
                "final_answer_recommendation": "",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Archive a record.",
                "requested_action": "archive_record",
                "target_identifier": "",
                "required_original_tools": ["record_archive"],
                "available_original_tools": ["record_archive"],
                "visible_records_count": 0,
            },
            {
                "should_abstain": True,
                "missing_information": ["target_identifier"],
                "required_original_tools": ["record_archive"],
                "safe_next_action": "ask_user_or_abstain",
                "final_answer_recommendation": (
                    "A target record identifier is required before archiving."
                ),
                "abstain_reason": "missing_target_identifier",
            },
            negative_applicability=True,
        ),
    )


_GENERAL_IMPLEMENTATION = """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])
    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])
    missing = [capability for capability in required if capability not in available]
    if missing:
        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.', 'abstain_reason': 'missing_required_original_tool'}
    if not str(target_identifier or '').strip():
        return {'should_abstain': True, 'missing_information': ['target_identifier'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'A target identifier is required.', 'abstain_reason': 'missing_target_identifier'}
    if int(visible_records_count or 0) > 1:
        return {'should_abstain': True, 'missing_information': ['ambiguous_target'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'The target is ambiguous because multiple matches are visible.', 'abstain_reason': 'ambiguous_target'}
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""


_TARGET_FIRST_IMPLEMENTATION = """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])
    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])
    missing = [capability for capability in required if capability not in available]
    if not str(target_identifier or '').strip():
        return {'should_abstain': True, 'missing_information': ['target_identifier'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'A target identifier is required.', 'abstain_reason': 'missing_target_identifier'}
    if missing:
        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.', 'abstain_reason': 'missing_required_original_tool'}
    if int(visible_records_count or 0) > 1:
        return {'should_abstain': True, 'missing_information': ['ambiguous_target'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'The target is ambiguous because multiple matches are visible.', 'abstain_reason': 'ambiguous_target'}
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""


_READ_ONLY_PRIORITY_IMPLEMENTATION = """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])
    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])
    missing = [capability for capability in required if capability not in available]
    if missing:
        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Cannot continue because ' + ', '.join(item.replace('_', ' ') for item in missing) + ' is unavailable.', 'abstain_reason': 'missing_required_original_tool'}
    action = str(requested_action or '').strip().lower()
    read_only = any(marker in action for marker in ('search', 'lookup', 'find', 'list', 'read', 'check'))
    mutating = any(marker in action for marker in ('add', 'archive', 'create', 'delete', 'modify', 'remove', 'send', 'set', 'update'))
    if mutating and not read_only and not str(target_identifier or '').strip():
        return {'should_abstain': True, 'missing_information': ['target_identifier'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'A target identifier is required.', 'abstain_reason': 'missing_target_identifier'}
    if mutating and not read_only and int(visible_records_count or 0) > 1:
        return {'should_abstain': True, 'missing_information': ['ambiguous_target'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'The target is ambiguous because multiple matches are visible.', 'abstain_reason': 'ambiguous_target'}
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""


def _relative_time_examples() -> tuple[ToolExample, ...]:
    return (
        ToolExample(
            {
                "user_request": "Search for records from yesterday.",
                "requested_action": "relative_time_search",
                "target_identifier": "",
                "required_original_tools": ["get_current_timestamp"],
                "available_original_tools": [],
                "visible_records_count": 0,
            },
            {
                "should_abstain": True,
                "missing_information": ["current_time"],
                "required_original_tools": ["current_time"],
                "safe_next_action": "ask_user_or_abstain",
                "final_answer_recommendation": (
                    "Current time is unavailable, so the search cannot continue."
                ),
                "abstain_reason": "missing_required_original_tool",
            },
        ),
        ToolExample(
            {
                "user_request": "Search for records from yesterday.",
                "requested_action": "relative_time_search",
                "target_identifier": "",
                "required_original_tools": ["get_current_timestamp"],
                "available_original_tools": ["get_current_timestamp"],
                "visible_records_count": 0,
            },
            {
                "should_abstain": False,
                "missing_information": [],
                "required_original_tools": ["current_time"],
                "safe_next_action": "continue_with_original_tool",
                "final_answer_recommendation": "",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Archive a record.",
                "requested_action": "archive_record",
                "target_identifier": "",
                "required_original_tools": ["record_archive"],
                "available_original_tools": ["record_archive"],
                "visible_records_count": 0,
            },
            {
                "should_abstain": True,
                "missing_information": ["target_identifier"],
                "required_original_tools": ["record_archive"],
                "safe_next_action": "ask_user_or_abstain",
                "final_answer_recommendation": (
                    "A target record identifier is required before archiving."
                ),
                "abstain_reason": "missing_target_identifier",
            },
            negative_applicability=True,
        ),
    )


def test_validator_accepts_raw_semantics_and_fact_preserving_paraphrases() -> None:
    result = validate_generated_tool(
        _abstention_tool(_GENERAL_IMPLEMENTATION),
        _examples(),
    )

    assert result.accepted, result.errors


def test_validator_accepts_clear_dynamic_deficit_recommendation() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "'Cannot continue because ' + ', '.join(item.replace('_', ' ') for item in missing) + ' is unavailable.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert result.accepted, result.errors


def test_validator_accepts_required_to_complete_as_deficit_recommendation() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'A target identifier is required.'",
        "'A target identifier is required to complete the action.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert result.accepted, result.errors


def test_validator_accepts_required_before_actor_can_complete() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'A target identifier is required.'",
        "'A target identifier is required before I can complete the action.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert result.accepted, result.errors


@pytest.mark.parametrize("modal", ["can", "will"])
def test_validator_rejects_required_lookup_completion_claim(modal: str) -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        (
            "'The required ' + ', '.join(item.replace('_', ' ') for item in missing) "
            f"+ ' {modal} complete successfully.'"
        ),
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_deficit_semantics" in error
        for error in result.errors
    )


def test_validator_rejects_fact_named_only_as_successful() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "', '.join(item.replace('_', ' ') for item in missing) + ' succeeded.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_deficit_semantics" in error
        for error in result.errors
    )


def test_validator_rejects_negated_deficit_recommendation() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "', '.join(item.replace('_', ' ') for item in missing) + ' is not needed.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_deficit_semantics" in error
        for error in result.errors
    )


def test_validator_rejects_contradictory_missing_success_recommendation() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "'The missing ' + ', '.join(item.replace('_', ' ') for item in missing) + ' succeeded.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_deficit_semantics" in error
        for error in result.errors
    )


def test_validator_rejects_missing_fact_described_as_complete() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "'The missing ' + ', '.join(item.replace('_', ' ') for item in missing) + ' is now complete.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_deficit_semantics" in error
        for error in result.errors
    )


def test_validator_rejects_extra_abstention_output_key() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'abstain_reason': 'missing_required_original_tool'",
        (
            "'abstain_reason': 'missing_required_original_tool', "
            "'downstream_tool_name': 'remove_contact'"
        ),
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any("source_0_raw_extra_keys" in error for error in result.errors)


def test_validator_rejects_truthy_non_boolean_abstention_decision() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'should_abstain': True", "'should_abstain': 'yes'"
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_should_abstain_not_bool" in error for error in result.errors
    )


def test_validator_enforces_capability_priority_for_simultaneous_deficits() -> None:
    result = validate_generated_tool(
        _abstention_tool(_TARGET_FIRST_IMPLEMENTATION),
        _examples(),
    )

    assert not result.accepted
    assert any(
        "_missing_capability_0_and_target_abstain_reason" in error
        for error in result.errors
    )


def test_relative_time_search_allows_blank_target_after_clock_is_available() -> None:
    result = validate_generated_tool(
        _abstention_tool(_READ_ONLY_PRIORITY_IMPLEMENTATION),
        _relative_time_examples(),
    )

    assert result.accepted, result.errors


@pytest.mark.parametrize(
    "action",
    (
        "remove_contact",
        "delete_contact",
        "modify_contact",
        "update_contact",
        "send_message",
        "send_message_with_phone_number",
        "message",
        "remove_reminder",
        "modify_reminder",
        "add_reminder",
        "contact_removal",
        "reminder_removal",
        "reminder_creation",
        "thread_send",
        "checklist_create",
        "record_deletion",
        "contact_creation",
        "record_modification",
        "record_archival",
        "contact_addition",
    ),
)
def test_canonical_mutating_action_aliases_require_targets(action: str) -> None:
    assert _action_requires_target(action)


@pytest.mark.parametrize(
    "action",
    (
        "search_contacts",
        "search_messages",
        "search_reminder",
        "relative_time_search",
        "contact_lookup",
        "message_lookup",
        "reminder_lookup",
        "current_time",
        "location_lookup",
        "asset_validation",
        "record_inspection",
        "record_listing",
    ),
)
def test_canonical_read_only_action_aliases_do_not_require_targets(
    action: str,
) -> None:
    assert not _action_requires_target(action)


@pytest.mark.parametrize(
    "fact",
    (
        "contact_removal",
        "contact_update",
        "message_send",
        "reminder_removal",
        "reminder_update",
        "reminder_creation",
    ),
)
def test_canonical_capability_name_is_valid_recommendation_fact(fact: str) -> None:
    assert _recommendation_mentions_fact(
        f"The {fact} capability is unavailable.",
        fact,
    )


def test_validator_exercises_remove_contact_target_and_ambiguity_properties() -> None:
    alias_examples = tuple(
        ToolExample(
            {
                **example.inputs,
                "requested_action": (
                    "archive_record"
                    if example.negative_applicability
                    else "remove_contact"
                ),
            },
            example.expected,
            held_out=example.held_out,
            negative_applicability=example.negative_applicability,
        )
        for example in _examples()
    )
    remove_blind_candidate = _GENERAL_IMPLEMENTATION.replace(
        "if not str(target_identifier or '').strip():",
        "if 'archive' in requested_action and not str(target_identifier or '').strip():",
    ).replace(
        "if int(visible_records_count or 0) > 1:",
        "if 'archive' in requested_action and int(visible_records_count or 0) > 1:",
    )

    result = validate_generated_tool(
        _abstention_tool(remove_blind_candidate),
        alias_examples,
    )

    assert not result.accepted
    assert any("blind_property_1_missing_target" in error for error in result.errors)
    assert any("blind_property_1_ambiguous_target" in error for error in result.errors)


def test_validator_rejects_raw_decision_repaired_only_by_normalizer() -> None:
    tool = _abstention_tool(
        """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = list(required_original_tools or [])
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any("source_0_raw_should_abstain" in error for error in result.errors)
    assert any("negative_0_raw_should_abstain" in error for error in result.errors)


def test_validator_rejects_historical_generic_missing_tool_implementation() -> None:
    """Regression: the paper-run helper's branch structure cannot be promoted."""

    tool = _abstention_tool(
        """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])
    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])
    missing = [capability for capability in required if capability not in available]
    if missing:
        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'I do not have enough information to proceed.', 'abstain_reason': 'missing_required_original_tool'}
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_facts:record_lookup" in error
        for error in result.errors
    )
    assert any("negative_0_raw_should_abstain" in error for error in result.errors)


def test_pinned_historical_fault_fixture_fails_current_public_contract() -> None:
    """The exact development fixture must exercise a real validator defect."""

    repository_root = Path(__file__).resolve().parents[2]
    fixture = json.loads(
        (
            repository_root / "docs/sage_protocol/fixtures/"
            "historical_faulty_safe_action_registry.json"
        ).read_text(encoding="utf-8")
    )
    entry = RegistryEntry.from_json(fixture["tools"]["prepare_safe_action_or_abstain"])
    observation = _safe_action_or_abstain_observation("public_contract_fixture_check")

    result = validate_generated_tool(entry.tool, observation.validation_examples)

    assert not result.accepted
    assert any("raw_" in error for error in result.errors)
    assert any(
        marker in error
        for error in result.errors
        for marker in (
            "missing_target",
            "missing_capability",
            "raw_should_abstain",
        )
    )


def test_validator_rejects_generic_recommendation_without_missing_fact() -> None:
    code = _GENERAL_IMPLEMENTATION.replace(
        "'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.'",
        "'I cannot continue.'",
    )

    result = validate_generated_tool(_abstention_tool(code), _examples())

    assert not result.accepted
    assert any(
        "source_0_raw_final_recommendation_missing_facts:record_lookup" in error
        for error in result.errors
    )


def test_validator_runs_hidden_metamorphic_cases_without_leaking_values() -> None:
    tool = _abstention_tool(
        """
def safe_record_action_gate(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])
    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])
    missing = [capability for capability in required if capability not in available]
    if visible_records_count == 0 and missing:
        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Missing capability: ' + ', '.join(item.replace('_', ' ') for item in missing) + '.', 'abstain_reason': 'missing_required_original_tool'}
    if visible_records_count == 0 and not str(target_identifier or '').strip():
        return {'should_abstain': True, 'missing_information': ['target_identifier'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'A target identifier is required.', 'abstain_reason': 'missing_target_identifier'}
    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}
"""
    )

    result = validate_generated_tool(tool, _examples())

    assert not result.accepted
    hidden_errors = [
        error for error in result.errors if error.startswith("blind_property_")
    ]
    assert hidden_errors
    assert any("missing_capability" in error for error in hidden_errors)
    assert all("labelled-record" not in error for error in hidden_errors)
    assert all("record_lookup" not in error for error in hidden_errors)
