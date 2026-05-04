from dataclasses import replace

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
