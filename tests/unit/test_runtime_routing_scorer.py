from dataclasses import replace
from typing import Any

from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime import routing_scorer
from sage_ts.runtime.routing_scorer import score_registry_entry_for_scenario
from sage_ts.runtime.toolsandbox_integration import route_registry_entries
from tests.unit.test_promotion_gate import _entry


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


def test_routing_suppresses_visible_not_called_pollution(monkeypatch: Any) -> None:
    monkeypatch.setenv("SAGE_V2_EXPERIMENT_FEATURES", "evidence_routing")
    entry = _entry()
    monkeypatch.setattr(
        routing_scorer,
        "_latest_helper_contribution_summary",
        lambda: {
            "helpers": {
                "select_visible_record": {
                    "visible_count": 5,
                    "called_count": 0,
                    "visible_not_called_count": 5,
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
