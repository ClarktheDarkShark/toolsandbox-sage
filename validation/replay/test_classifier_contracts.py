"""Focused fail-closed tests for classifier factory-refactor guards."""

from __future__ import annotations

import copy

import pytest

from validation.replay.classifier_contracts import (
    _EXPECTED_FACTORY_MUTABLE_COUNTS,
    _FACTORY_REFACTOR_SPECS,
    _mutable_identity_topology,
    _ordered_shape,
    _verify_factory_refactor_guards,
)


def _passing_guards() -> dict[str, object]:
    factories = []
    for group, factory_name in _FACTORY_REFACTOR_SPECS:
        factories.append(
            {
                "group": group,
                "factory_name": factory_name,
                "example_count": 1,
                "examples": [{}],
                "within_product_mutable_topology": {
                    "mutable_container_count": _EXPECTED_FACTORY_MUTABLE_COUNTS[
                        factory_name
                    ],
                    "mutable_container_occurrence_count": (
                        _EXPECTED_FACTORY_MUTABLE_COUNTS[factory_name]
                    ),
                    "duplicate_mutable_identity_count": 0,
                    "alias_groups": [],
                },
                "freshness": {
                    "first_mutation_changed_first": True,
                    "first_mutation_left_second_unchanged": True,
                    "fresh_third_matches_unmutated_second": True,
                    "first_second_shared_mutable_count": 0,
                    "second_third_shared_mutable_count": 0,
                },
            }
        )
    return {
        "factories": factories,
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


def test_factory_guard_inventory_covers_exact_11_refactor_targets() -> None:
    assert len(_FACTORY_REFACTOR_SPECS) == 11
    assert [group for group, _name in _FACTORY_REFACTOR_SPECS].count("service") == 6
    assert [group for group, _name in _FACTORY_REFACTOR_SPECS].count("location") == 2
    assert [group for group, _name in _FACTORY_REFACTOR_SPECS].count("search") == 3
    assert set(_EXPECTED_FACTORY_MUTABLE_COUNTS) == {
        name for _group, name in _FACTORY_REFACTOR_SPECS
    }
    _verify_factory_refactor_guards(_passing_guards())


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


def test_factory_guard_rejects_cross_call_mutable_alias() -> None:
    guards = copy.deepcopy(_passing_guards())
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


def test_factory_guard_rejects_within_product_alias_topology() -> None:
    guards = copy.deepcopy(_passing_guards())
    topology = guards["factories"][0]["within_product_mutable_topology"]
    topology["mutable_container_occurrence_count"] += 1
    topology["duplicate_mutable_identity_count"] = 1
    topology["alias_groups"] = [{"type": "dict", "paths": [[], []]}]

    with pytest.raises(ValueError, match="mutable identity topology changed"):
        _verify_factory_refactor_guards(guards)


def test_factory_guard_rejects_intra_example_location_kwargs_alias() -> None:
    guards = copy.deepcopy(_passing_guards())
    guards["location_kwargs_non_alias"][0]["same_object_before"] = True

    with pytest.raises(ValueError, match="location kwargs alias"):
        _verify_factory_refactor_guards(guards)
