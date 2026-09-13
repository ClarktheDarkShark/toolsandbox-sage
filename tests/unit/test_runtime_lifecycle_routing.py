from __future__ import annotations

import pytest

from sage_ts.runtime.toolsandbox_integration import (
    _lifecycle_visibility_override,
    load_tool_lifecycle_routing_state,
)


@pytest.mark.parametrize(
    ("decision", "reason"),
    (
        ("park", "lifecycle_suppressed_parked_tool"),
        ("parked", "lifecycle_suppressed_parked_tool"),
        (
            "needs_implementation_repair",
            "lifecycle_suppressed_pending_implementation_repair",
        ),
        ("quarantined", "lifecycle_suppressed_quarantined_tool"),
        ("retired_after_failed_repair", "lifecycle_suppressed_retired_tool"),
    ),
)
def test_non_executable_lifecycle_states_are_hidden_globally(
    decision: str,
    reason: str,
) -> None:
    state = {"generated_helper": {"decision": decision}}

    assert _lifecycle_visibility_override(
        tool_name="generated_helper",
        scenario_name=None,
        lifecycle_state=state,
    ) == (False, reason)


def test_operational_cleanliness_does_not_exempt_abstention_tool_from_repair_route() -> (
    None
):
    family = "modify_contact_with_message_recency_insufficient_information"
    state = {
        "prepare_safe_action_or_abstain": {
            "decision": "retain_with_route_repair",
            "failed_count": 0,
            "side_effect_incident_count": 0,
            "harmful_called_count": 2,
            "harmful_called_families": [family, f"{family}_alt"],
            "helpful_called_families": ["unrelated_safe_abstention"],
            "route_repair_families": [family],
        }
    }

    assert _lifecycle_visibility_override(
        tool_name="prepare_safe_action_or_abstain",
        scenario_name=family,
        lifecycle_state=state,
    ) == (False, "lifecycle_suppressed_harmful_called_family")


def test_mixed_tool_is_hidden_only_in_its_harmful_family() -> None:
    harmful_family = "contact_dependency_resolution"
    state = {
        "generic_dependency_helper": {
            "decision": "retain_with_route_repair",
            "harmful_called_count": 2,
            "harmful_called_families": [
                harmful_family,
                f"{harmful_family}_alt",
            ],
            "helpful_called_families": ["reminder_dependency_resolution"],
            "route_repair_families": [harmful_family],
        }
    }

    assert _lifecycle_visibility_override(
        tool_name="generic_dependency_helper",
        scenario_name=harmful_family,
        lifecycle_state=state,
    ) == (False, "lifecycle_suppressed_harmful_called_family")
    assert (
        _lifecycle_visibility_override(
            tool_name="generic_dependency_helper",
            scenario_name="reminder_dependency_resolution",
            lifecycle_state=state,
        )
        is None
    )


@pytest.mark.parametrize(
    "content",
    (
        "{not-json",
        "[]",
        "{}",
        '{"tool_lifecycle":[]}',
        '{"tool_lifecycle":{"helper":[]}}',
    ),
)
def test_lifecycle_state_loader_fails_closed_on_malformed_state(
    tmp_path,
    content: str,
) -> None:
    registry_root = tmp_path / "registry"
    registry_root.mkdir()
    (registry_root / "tool_lifecycle.json").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed lifecycle routing state"):
        load_tool_lifecycle_routing_state(registry_root)


def test_lifecycle_state_loader_allows_missing_state(tmp_path) -> None:
    assert load_tool_lifecycle_routing_state(tmp_path / "missing_registry") == {}
