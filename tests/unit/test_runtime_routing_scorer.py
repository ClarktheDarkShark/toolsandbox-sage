import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime import routing_scorer
from sage_ts.runtime.routing_scorer import score_registry_entry_for_scenario
from sage_ts.runtime.toolsandbox_integration import route_registry_entries
from tests.unit.test_promotion_gate import _entry


def _state_dependency_entry() -> RegistryEntry:
    base = _entry()
    return RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="next_dependency_precondition_call",
                family=ToolFamily.STATE_PRECONDITION_HELPER,
                description=(
                    "Plan the next original service tool_call when visible state "
                    "shows a dependency or precondition blocks the requested action."
                ),
                positive_triggers=(
                    "service not ready with active blocker",
                    "service not ready with missing dependency",
                ),
                negative_triggers=("already ready state", "insufficient state"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": ["", "set_low_battery_mode_status"],
                        },
                        "arguments": {"type": "object"},
                        "should_call": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["tool_name", "arguments", "should_call"],
                },
                abstain_behavior=(
                    "Return should_call=False with a reason when state is ready, "
                    "missing, or ambiguous."
                ),
                applicable_task_families=(
                    "turn_on_wifi_low_battery_mode",
                    "turn_on_cellular_low_battery_mode",
                ),
                shortfall_cluster_evidence=(
                    "state_precondition:dependency_precondition_tool_call",
                ),
                known_failure_mechanisms_addressed=(
                    "precondition_bundle_before_downstream_action",
                ),
                required_original_tool_calls=("set_low_battery_mode_status",),
                preserves_side_effect_tools=("set_low_battery_mode_status",),
                final_state_preservation_plan=(
                    "The caller must execute the returned original ToolSandbox "
                    "tool and verify the resulting service state."
                ),
                grading_accounting_note=(
                    "Canonical route differences are reported separately from "
                    "final task outcome."
                ),
            ),
        ),
        base.validation,
        birth_scenario="turn_on_wifi_low_battery_mode",
    )


def test_generic_routing_shows_positive_trigger_and_hides_negative() -> None:
    entry = _entry()
    shown = score_registry_entry_for_scenario(
        entry, "visible_candidate_selection_for_contact"
    )
    hidden = score_registry_entry_for_scenario(
        entry, "ambiguous_tie_visible_candidate_selection"
    )

    assert shown.visible
    assert shown.reason == "generic_relevance_score_passed"
    assert not hidden.visible
    assert hidden.reason == "blocked_by_negative_trigger"


def test_helper_trigger_strata_do_not_expose_without_specific_match() -> None:
    base = _entry()
    tool = replace(
        base.tool,
        spec=replace(
            base.tool.spec,
            tool_name="select_record_by_timestamp_extreme",
            positive_triggers=("search_message_with_recency_latest",),
            applicable_task_families=("message_lookup", "contact_update"),
        ),
    )
    entry = RegistryEntry.accepted(tool, base.validation, birth_scenario="seed")

    decision = score_registry_entry_for_scenario(entry, "find_thanksgiving_timestamp")

    assert not decision.visible
    assert decision.reason == "generic_relevance_score_insufficient"


def test_route_registry_entries_bounds_runtime_bundle() -> None:
    entries = {
        f"tool_{index}": replace(
            _entry(),
            tool=replace(
                _entry().tool,
                spec=replace(_entry().tool.spec, tool_name=f"tool_{index}"),
            ),
        )
        for index in range(6)
    }

    selected, decisions = route_registry_entries(
        entries,
        "visible_candidate_selection_for_contact",
        max_bundle_size=5,
    )

    assert len(selected) == 5
    assert sum(1 for item in decisions.values() if item.status == "deprioritized") == 1


def test_route_registry_entries_requires_downstream_base_tool_availability() -> None:
    entry = _entry()

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts"},
    )

    assert selected == []
    assert not decisions["select_visible_record"].visible
    assert (
        decisions["select_visible_record"].reason
        == "blocked_by_missing_downstream_original_tool"
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == ["select_visible_record"]
    assert decisions["select_visible_record"].visible


def test_route_registry_entries_treats_preserved_tools_as_conditional_when_required_exists() -> (
    None
):
    base = _entry()
    entry = replace(
        base,
        tool=replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
            ),
        ),
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record": entry},
        "visible_candidate_selection_for_contact",
        available_base_tools={"search_contacts"},
    )

    assert [item.tool.spec.tool_name for item in selected] == ["select_visible_record"]
    assert decisions["select_visible_record"].visible


def test_route_registry_entries_allows_composite_one_of_many_downstream_tools() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            positive_triggers=("modify_contact_with_message_recency",),
            negative_triggers=("empty selected record",),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
            preserves_side_effect_tools=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record(records: list) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    selected, decisions = route_registry_entries(
        {"prepare_side_effect_args_from_selected_record": entry},
        "modify_contact_with_message_recency_3_distraction_tools",
        available_base_tools={"search_messages", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "prepare_side_effect_args_from_selected_record"
    ]
    assert decisions["prepare_side_effect_args_from_selected_record"].visible


def test_route_registry_entries_allows_action_selector_one_of_many_downstream_tools() -> (
    None
):
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            positive_triggers=("modify_contact_with_message_recency",),
            negative_triggers=("no records", "ambiguous timestamp tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
            preserves_side_effect_tools=(
                "modify_contact",
                "remove_contact",
                "modify_reminder",
                "remove_reminder",
            ),
        ),
        code=(
            "def select_action_target_by_recency(records: list) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    selected, decisions = route_registry_entries(
        {"select_action_target_by_recency": entry},
        "modify_contact_with_message_recency_3_distraction_tools",
        available_base_tools={"search_messages", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_action_target_by_recency"
    ]
    assert decisions["select_action_target_by_recency"].visible


def test_recency_action_selector_hides_on_non_recency_contact_tasks() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select an action target by recency from visible records.",
            inputs=(
                replace(base.tool.spec.inputs[0], name="records", annotation="list"),
                replace(
                    base.tool.spec.inputs[0], name="timestamp_key", annotation="str"
                ),
                replace(
                    base.tool.spec.inputs[0], name="selection_mode", annotation="str"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
            ),
            positive_triggers=("latest visible action target",),
            negative_triggers=("no records", "ambiguous tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("modify_contact", "remove_reminder"),
            preserves_side_effect_tools=("modify_contact", "remove_reminder"),
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    decision = score_registry_entry_for_scenario(entry, "remove_contact_by_phone")

    assert not decision.visible
    assert decision.reason == "recency_action_selector_requires_recency_action_task"


def test_side_effect_selector_hides_on_insufficient_information() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_action_target_by_recency",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select an action target by recency from visible records.",
            inputs=(
                replace(base.tool.spec.inputs[0], name="records", annotation="list"),
                replace(
                    base.tool.spec.inputs[0], name="timestamp_key", annotation="str"
                ),
                replace(
                    base.tool.spec.inputs[0], name="selection_mode", annotation="str"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
            ),
            positive_triggers=("latest visible action target",),
            negative_triggers=("no records", "ambiguous tie"),
            applicable_task_families=(
                "modify_contact_with_message_recency",
                "remove_reminder_with_recency_latest",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "downstream_tool_name": {"type": "string"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("modify_contact", "remove_reminder"),
            preserves_side_effect_tools=("modify_contact", "remove_reminder"),
        ),
        code=(
            "def select_action_target_by_recency(records: list, timestamp_key: str, "
            "selection_mode: str, action_type: str) -> dict:\n"
            "    return {'selected_record': {}, 'downstream_tool_name': '', "
            "'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="modify_contact_with_message_recency",
    )

    decision = score_registry_entry_for_scenario(
        entry, "modify_contact_with_message_recency_insufficient_information"
    )

    assert not decision.visible
    assert (
        decision.reason
        == "side_effect_selector_suppressed_for_insufficient_information"
    )


def test_side_effect_composite_hides_on_insufficient_information() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare kwargs for an original side-effect tool.",
            inputs=(
                replace(
                    base.tool.spec.inputs[0], name="selected_record", annotation="dict"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
                replace(base.tool.spec.inputs[0], name="updates", annotation="dict"),
                replace(base.tool.spec.inputs[0], name="user_intent", annotation="str"),
            ),
            positive_triggers=("selected record with required id",),
            negative_triggers=("missing selected record",),
            applicable_task_families=(
                "remove_contact_by_phone",
                "update_contact_relationship_with_relationship",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("remove_contact",),
            preserves_side_effect_tools=("remove_contact",),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="remove_contact_by_phone",
    )

    decision = score_registry_entry_for_scenario(
        entry, "remove_contact_by_phone_no_remove_contact_insufficient_information"
    )

    assert not decision.visible
    assert (
        decision.reason
        == "side_effect_composite_suppressed_for_insufficient_information"
    )


def test_side_effect_composite_hides_without_downstream_action_signal() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="prepare_side_effect_args_from_selected_record",
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description="Prepare kwargs for an original side-effect tool.",
            inputs=(
                replace(
                    base.tool.spec.inputs[0], name="selected_record", annotation="dict"
                ),
                replace(base.tool.spec.inputs[0], name="action_type", annotation="str"),
                replace(base.tool.spec.inputs[0], name="updates", annotation="dict"),
                replace(base.tool.spec.inputs[0], name="user_intent", annotation="str"),
            ),
            positive_triggers=("selected record with required id",),
            negative_triggers=("missing selected record",),
            applicable_task_families=(
                "remove_contact_by_phone",
                "update_contact_relationship_with_relationship",
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "downstream_tool_name": {"type": "string"},
                    "downstream_tool_kwargs": {"type": "object"},
                    "should_call_tool": {"type": "boolean"},
                    "abstain_reason": {"type": "string"},
                },
            },
            required_original_tool_calls=("remove_contact",),
            preserves_side_effect_tools=("remove_contact",),
        ),
        code=(
            "def prepare_side_effect_args_from_selected_record("
            "selected_record: dict, action_type: str, updates: dict, "
            "user_intent: str) -> dict:\n"
            "    return {'downstream_tool_name': '', 'downstream_tool_kwargs': {}, "
            "'should_call_tool': False, 'abstain_reason': 'test'}\n"
        ),
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="remove_contact_by_phone",
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_name_with_relationship_3_distraction_tools"
    )

    assert not decision.visible
    assert decision.reason == "post_selection_composite_requires_downstream_action_task"

    _entries, decisions = route_registry_entries(
        {"prepare_side_effect_args_from_selected_record": entry},
        "search_name_with_relationship_3_distraction_tools",
        available_base_tools={"search_contacts", "modify_contact", "remove_contact"},
    )
    assert not decisions["prepare_side_effect_args_from_selected_record"].visible
    assert (
        decisions["prepare_side_effect_args_from_selected_record"].reason
        == "post_selection_composite_requires_downstream_action_task"
    )


def test_route_registry_entries_allows_one_available_emitted_downstream_tool() -> None:
    base = _state_dependency_entry()
    entry = replace(
        base,
        tool=replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                output_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": [
                                "",
                                "set_low_battery_mode_status",
                                "set_cellular_service_status",
                            ],
                        },
                        "arguments": {"type": "object"},
                        "should_call": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["tool_name", "arguments", "should_call"],
                },
                required_original_tool_calls=(
                    "set_low_battery_mode_status",
                    "set_cellular_service_status",
                ),
                preserves_side_effect_tools=(
                    "set_low_battery_mode_status",
                    "set_cellular_service_status",
                ),
            ),
        ),
    )

    selected, decisions = route_registry_entries(
        {"next_dependency_precondition_call": entry},
        "turn_on_wifi_low_battery_mode",
        available_base_tools={"set_low_battery_mode_status"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "next_dependency_precondition_call"
    ]
    assert decisions["next_dependency_precondition_call"].visible


def test_routing_suppresses_visible_not_called_pollution(monkeypatch: Any) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    entry = _entry()
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record": {
                    "visible_count": 12,
                    "called_count": 0,
                    "visible_not_called_count": 12,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "visible_candidate_selection_for_contact"
    )

    assert not decision.visible
    assert decision.reason == "blocked_by_visible_not_called_adoption_risk"


def test_strong_selector_match_gets_actor_policy_fair_chance(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_visible_record_by_constraints",
                applicable_task_families=(
                    "search_phone_number_with_name",
                    "search_relationship_with_phone_number",
                ),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "selected_record": {"type": "object"},
                        "abstain_reason": {"type": "string"},
                    },
                },
            ),
        ),
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record_by_constraints": {
                    "visible_count": 34,
                    "called_count": 0,
                    "visible_not_called_count": 34,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_phone_number_with_name_3_distraction_tools"
    )

    assert decision.visible
    assert decision.reason == "generic_relevance_score_passed"


def test_strong_selector_match_still_blocks_harmful_called_history(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_visible_record_by_constraints",
                applicable_task_families=(
                    "search_phone_number_with_name",
                    "search_relationship_with_phone_number",
                ),
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
                output_schema={
                    "type": "object",
                    "properties": {
                        "selected_record": {"type": "object"},
                        "abstain_reason": {"type": "string"},
                    },
                },
            ),
        ),
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record_by_constraints": {
                    "visible_count": 34,
                    "called_count": 2,
                    "visible_not_called_count": 32,
                    "called_subset": {"mean_outcome_delta": -0.2},
                }
            }
        },
    )

    decision = score_registry_entry_for_scenario(
        entry, "search_phone_number_with_name_3_distraction_tools"
    )

    assert not decision.visible
    assert decision.reason == "blocked_by_visible_not_called_adoption_risk"


def test_routing_evidence_ignores_runtime_exception_runs(
    monkeypatch: Any, tmp_path: Path
) -> None:
    invalid_run = tmp_path / "outputs" / "invalid_run"
    valid_run = tmp_path / "outputs" / "valid_run"
    invalid_candidate = invalid_run / "candidate" / "arm"
    valid_candidate = valid_run / "candidate" / "arm"
    invalid_candidate.mkdir(parents=True)
    valid_candidate.mkdir(parents=True)
    (invalid_run / "paired_comparison.json").write_text(
        json.dumps({"runtime_exception_count": 1}) + "\n"
    )
    (valid_run / "paired_comparison.json").write_text(
        json.dumps({"runtime_exception_count": 0}) + "\n"
    )
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "candidate_dir": str(valid_candidate),
                "helpers": {"tool": {"visible_count": 1}},
            }
        )
        + "\n"
    )
    (new_dir / "helper_contribution_summary.json").write_text(
        json.dumps(
            {
                "candidate_dir": str(invalid_candidate),
                "helpers": {"tool": {"visible_count": 9}},
            }
        )
        + "\n"
    )
    monkeypatch.setattr(routing_scorer, "ROUTING_EVIDENCE_ROOT", tmp_path)
    routing_scorer._latest_helper_contribution_summary.cache_clear()

    evidence = routing_scorer._latest_helper_contribution_summary()

    assert evidence["helpers"]["tool"]["visible_count"] == 1
    routing_scorer._latest_helper_contribution_summary.cache_clear()


def test_routing_gives_new_cluster_born_state_helper_fair_chance(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {"helpers": {}},
    )
    entry = _state_dependency_entry()

    decision = score_registry_entry_for_scenario(
        entry, "turn_on_wifi_low_battery_mode_3_distraction_tools"
    )

    assert decision.visible
    assert decision.reason == "fair_chance_cluster_fit"
    assert decision.fair_chance_candidate
    assert decision.fair_chance_reason


def test_fair_chance_state_helper_stays_hidden_on_unrelated_task(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {"helpers": {}},
    )
    entry = _state_dependency_entry()

    decision = score_registry_entry_for_scenario(entry, "find_days_till_holiday")

    assert not decision.visible
    assert decision.reason == "generic_relevance_score_insufficient"


def test_diagnostic_force_can_override_adoption_risk_for_target_tool(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setenv(
        "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "next_dependency_precondition_call"
    )
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "next_dependency_precondition_call": {
                    "visible_count": 10,
                    "called_count": 0,
                    "visible_not_called_count": 10,
                    "called_subset": {"mean_outcome_delta": None},
                }
            }
        },
    )
    entry = _state_dependency_entry()

    selected, decisions = route_registry_entries(
        {"next_dependency_precondition_call": entry},
        "turn_on_wifi_low_battery_mode",
        available_base_tools={"set_low_battery_mode_status"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "next_dependency_precondition_call"
    ]
    assert decisions["next_dependency_precondition_call"].visible
    assert (
        decisions["next_dependency_precondition_call"].reason
        == "diagnostic_force_overrode_adoption_risk"
    )


def test_diagnostic_force_can_override_name_specific_vnc_suppression(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    monkeypatch.setenv(
        "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "select_contact_field_by_constraint"
    )
    base = _entry()
    entry = RegistryEntry.accepted(
        replace(
            base.tool,
            spec=replace(
                base.tool.spec,
                tool_name="select_contact_field_by_constraint",
                family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
                required_original_tool_calls=("search_contacts",),
                preserves_side_effect_tools=("search_contacts", "modify_contact"),
            ),
        ),
        base.validation,
        birth_scenario="update_contact_relationship_with_relationship",
    )

    selected, decisions = route_registry_entries(
        {"select_contact_field_by_constraint": entry},
        "update_contact_relationship_with_relationship_3_distraction_tools",
        available_base_tools={"search_contacts", "modify_contact"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_contact_field_by_constraint"
    ]
    assert decisions["select_contact_field_by_constraint"].visible
    assert (
        decisions["select_contact_field_by_constraint"].reason
        == "diagnostic_force_overrode_adoption_risk"
    )


def test_search_filter_selector_requires_any_record_producer_not_all_domains() -> None:
    base = _entry()
    tool = GeneratedTool(
        spec=replace(
            base.tool.spec,
            tool_name="select_visible_record_by_constraints",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            description="Select one visible record from search candidates by constraint.",
            inputs=base.tool.spec.inputs,
            output_schema={
                "type": "object",
                "properties": {
                    "selected_record": {"type": "object"},
                    "selected_id": {"type": "string"},
                    "value": {"type": "string"},
                    "tie_candidates": {"type": "array"},
                    "abstain_reason": {"type": "string"},
                },
            },
            positive_triggers=("search_phone_number_with_name",),
            required_original_tool_calls=(
                "search_contacts",
                "search_messages",
                "search_reminder",
            ),
            preserves_side_effect_tools=(
                "search_contacts",
                "search_messages",
                "search_reminder",
                "modify_contact",
                "remove_reminder",
            ),
        ),
        code="def select_visible_record_by_constraints(records: list) -> dict:\n    return {}\n",
    )
    entry = RegistryEntry.accepted(
        tool,
        base.validation,
        birth_scenario="search_phone_number_with_name",
    )

    selected, decisions = route_registry_entries(
        {"select_visible_record_by_constraints": entry},
        "search_phone_number_with_name_3_distraction_tools",
        available_base_tools={"search_contacts"},
    )

    assert [item.tool.spec.tool_name for item in selected] == [
        "select_visible_record_by_constraints"
    ]
    assert decisions["select_visible_record_by_constraints"].visible
