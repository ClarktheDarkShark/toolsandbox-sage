"""Focused fail-closed tests for classifier factory-refactor guards."""

from __future__ import annotations

import pytest

from validation.replay import classifier_contracts as contracts
from validation.replay.classifier_contracts import (
    _EXPECTED_FACTORY_TOPOLOGIES,
    _FACTORY_REFACTOR_SPECS,
    _digest,
    _mutable_identity_topology,
    _ordered_shape,
    _verify_factory_refactor_guards,
)


def _passing_guards(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Build a compact synthetic contract while retaining all 33 products."""

    factories = []
    synthetic_expectations: dict[str, tuple[int, int, int, str]] = {}
    for group, factory_name in _FACTORY_REFACTOR_SPECS:
        unique_count, occurrence_count, alias_count, _sha256 = (
            _EXPECTED_FACTORY_TOPOLOGIES[factory_name]
        )
        topology = {
            "mutable_container_count": unique_count,
            "mutable_container_occurrence_count": occurrence_count,
            "duplicate_mutable_identity_count": alias_count,
            "alias_groups": [
                {"type": "dict", "paths": [[], []]} for _index in range(alias_count)
            ],
        }
        topology_digest = _digest(topology)
        synthetic_expectations[factory_name] = (
            unique_count,
            occurrence_count,
            alias_count,
            topology_digest["sha256"],
        )
        factories.append(
            {
                "group": group,
                "factory_name": factory_name,
                "example_count": 1,
                "examples": [{}],
                "within_product_mutable_topology": topology,
                "within_product_mutable_topology_digest": topology_digest,
                "freshness": {
                    "first_mutation_changed_first": True,
                    "first_mutation_left_second_unchanged": True,
                    "fresh_third_matches_unmutated_second": True,
                    "first_second_shared_mutable_count": 0,
                    "second_third_shared_mutable_count": 0,
                },
            }
        )
    monkeypatch.setattr(
        contracts,
        "_EXPECTED_FACTORY_TOPOLOGIES",
        synthetic_expectations,
    )
    unchanged_digest = {"byte_count": 1, "sha256": "unchanged"}
    return {
        "schema_version": 2,
        "factories": factories,
        "reminder_factory_alias_equivalence": {
            "alias_factory": "_reminder_optional_location_argument_observation",
            "canonical_factory": "_reminder_creation_finalizer_observation",
            "equal_by_value_before_mutation": True,
            "same_object_before_mutation": False,
            "shared_mutable_count_before_mutation": 0,
            "optional_before": unchanged_digest,
            "optional_after": {"byte_count": 2, "sha256": "changed"},
            "finalizer_before": unchanged_digest,
            "finalizer_after": unchanged_digest,
            "optional_mutation_changed_optional": True,
            "optional_mutation_left_finalizer_unchanged": True,
            "fresh_optional": unchanged_digest,
            "fresh_finalizer": unchanged_digest,
            "fresh_products_equal_by_value": True,
            "fresh_products_match_unmutated_value": True,
            "fresh_products_shared_mutable_count": 0,
        },
        "location_kwargs_non_alias": [
            {
                "factory_name": "_location_search_argument_observation",
                "example_index": 0,
                "same_object_before": False,
                "shared_mutable_count_before": 0,
                "search_mutation_changed_search": True,
                "search_mutation_left_downstream_unchanged": True,
            }
        ],
    }


def test_factory_guard_inventory_covers_all_33_concrete_products() -> None:
    names = [name for _group, name in _FACTORY_REFACTOR_SPECS]

    assert len(names) == len(set(names)) == 33
    assert names[0] == "_safe_action_or_abstain_observation"
    assert names[-1] == "_single_device_state_action_observation"
    assert "_reminder_optional_location_argument_observation" in names
    assert "_reminder_creation_finalizer_observation" not in names
    assert set(_EXPECTED_FACTORY_TOPOLOGIES) == set(names)
    assert {
        name
        for name, (_unique, _occurrences, aliases, _sha256) in (
            _EXPECTED_FACTORY_TOPOLOGIES.items()
        )
        if aliases
    } == {
        "_plan_device_state_action_sequence_observation",
        "_message_counterparty_contact_update_observation",
        "_single_device_state_action_observation",
    }


def test_intentional_alias_topology_expectations_are_exact() -> None:
    assert _EXPECTED_FACTORY_TOPOLOGIES[
        "_plan_device_state_action_sequence_observation"
    ] == (
        31,
        48,
        8,
        "67e2ef08b687dc9ec8c7264a6e5455a48a530218e9a595022dd9e28017b13a2d",
    )
    assert _EXPECTED_FACTORY_TOPOLOGIES[
        "_message_counterparty_contact_update_observation"
    ] == (
        41,
        48,
        2,
        "284ea11ddadcac12542fa0143cca7b5e9c6688541442898bbc27159cdf7e64a1",
    )
    assert _EXPECTED_FACTORY_TOPOLOGIES["_single_device_state_action_observation"] == (
        17,
        18,
        1,
        "018104e014a76b78f3604f5da3dbfb6df7dd8609cbfed803c585ec65a2ba0465",
    )


def test_ordered_shape_localizes_nested_key_order_and_scalar_types() -> None:
    shape = _ordered_shape(
        {
            "service_payload": {"distance_km": 12.5, "name": "Park"},
            "requested_unit": "kilometers",
        }
    )

    assert [item["key"]["value"] for item in shape["items"]] == [
        "service_payload",
        "requested_unit",
    ]
    payload_shape = shape["items"][0]["value_shape"]
    assert [item["key"]["value"] for item in payload_shape["items"]] == [
        "distance_km",
        "name",
    ]
    assert payload_shape["items"][0]["value_shape"] == {"type": "float"}
    assert payload_shape["items"][1]["value_shape"] == {"type": "str"}


def test_factory_guard_accepts_frozen_alias_topologies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _verify_factory_refactor_guards(_passing_guards(monkeypatch))


def test_factory_guard_rejects_cross_call_mutable_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["factories"][0]["freshness"]["first_second_shared_mutable_count"] = 1

    with pytest.raises(ValueError, match="reuses mutable data"):
        _verify_factory_refactor_guards(guards)


def test_mutable_identity_topology_localizes_within_product_alias() -> None:
    shared: dict[str, object] = {"location": "pharmacy"}

    topology = _mutable_identity_topology(
        {
            "search_location_kwargs": shared,
            "downstream_tool_kwargs": shared,
        }
    )

    assert topology["mutable_container_count"] == 2
    assert topology["mutable_container_occurrence_count"] == 3
    assert topology["duplicate_mutable_identity_count"] == 1
    assert topology["alias_groups"] == [
        {
            "type": "dict",
            "paths": [
                [
                    {
                        "kind": "mapping_value",
                        "index": 0,
                        "key": {"type": "str", "value": "search_location_kwargs"},
                    }
                ],
                [
                    {
                        "kind": "mapping_value",
                        "index": 1,
                        "key": {
                            "type": "str",
                            "value": "downstream_tool_kwargs",
                        },
                    }
                ],
            ],
        }
    ]


def test_factory_guard_rejects_unapproved_within_product_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    topology = guards["factories"][0]["within_product_mutable_topology"]
    topology["mutable_container_occurrence_count"] += 1
    topology["duplicate_mutable_identity_count"] = 1
    topology["alias_groups"] = [{"type": "dict", "paths": [[], []]}]
    guards["factories"][0]["within_product_mutable_topology_digest"] = _digest(topology)

    with pytest.raises(ValueError, match="mutable identity topology changed"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_topology_digest_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["factories"][0]["within_product_mutable_topology_digest"]["sha256"] = (
        "tampered"
    )

    with pytest.raises(ValueError, match="mutable identity topology changed"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_reminder_alias_value_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["reminder_factory_alias_equivalence"]["finalizer_before"] = {
        "byte_count": 9,
        "sha256": "different",
    }

    with pytest.raises(ValueError, match="differ or share mutable data"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_reminder_alias_mutable_sharing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["reminder_factory_alias_equivalence"][
        "shared_mutable_count_before_mutation"
    ] = 1

    with pytest.raises(ValueError, match="differ or share mutable data"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_intra_example_location_kwargs_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["location_kwargs_non_alias"][0]["same_object_before"] = True

    with pytest.raises(ValueError, match="location kwargs alias"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_schema_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = _passing_guards(monkeypatch)
    guards["schema_version"] = 3

    with pytest.raises(ValueError, match="guard schema changed"):
        _verify_factory_refactor_guards(guards)
