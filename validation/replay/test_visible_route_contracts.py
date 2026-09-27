"""Focused fail-closed tests for the black-box visible route contract."""

from __future__ import annotations

import copy

import pytest

from validation.replay import classifier_contracts
from validation.replay import visible_route_contracts as routes


@pytest.fixture(scope="module")
def contract() -> dict[str, object]:
    value = routes.build_visible_route_trace()
    routes.verify_visible_route_trace(value)
    return value


def _forged(
    contract: dict[str, object],
    mutation: object,
) -> dict[str, object]:
    value = copy.deepcopy(contract)
    mutation(value)
    routes._rehash(value)
    return value


def test_existing_classifier_integrity_domains_remain_frozen() -> None:
    assert classifier_contracts.EXPECTED_CONTRACT["body"] == {
        "byte_count": 5_039_270,
        "sha256": "cbf49dfae370fa8a11c7e487a5fd627a249282735e393dc00362a1e5c768f637",
    }
    assert classifier_contracts.EXPECTED_CONTRACT["factory_refactor_guards"] == {
        "byte_count": 1_076_645,
        "sha256": "8ed7b3704ba1074f66e2aa09d408bfb8d38ce5df3b0ee884d0147af6e6cdab21",
    }


def test_primary_contract_covers_each_dispatch_site_once(
    contract: dict[str, object],
) -> None:
    cases = contract["primary_cases"]

    assert len(cases) == 39
    assert [item["route_site"] for item in cases] == list(range(1, 40))
    assert len({item["case_id"] for item in cases}) == 39
    assert sum(len(item["emitted_products"]) for item in cases) == 57


def test_device_routes_preserve_generation_label_factory_argument(
    contract: dict[str, object],
) -> None:
    cases = contract["primary_cases"]
    for route_site in (3, 4):
        case = cases[route_site - 1]
        target = case["emitted_products"][case["target_emission_index"]]
        assert target["raw_observation_scenario_label"] == target["task_context_label"]
        assert target["raw_observation_scenario_label"] != case["scenario_name"]


def test_terminal_nonterminal_and_duplicate_edges_are_explicit(
    contract: dict[str, object],
) -> None:
    extras = contract["focused_extras"]
    assert extras["terminal_insufficient_information"]["canonical_keys"] == [
        "validation:prepare_safe_action_or_abstain"
    ]
    collision = extras["nonterminal_safe_abstain_global_order"]
    assert len(collision["emitted_products"]) > 1
    assert collision["emitted_products"][0]["canonical_key"] == (
        "validation:prepare_safe_action_or_abstain"
    )
    duplicate = extras["duplicate_modify_contact_route"]
    assert duplicate["target_emission_index"] == 2
    assert duplicate["target_canonical_occurrence_index"] == 1


def test_layered_cases_freeze_every_complete_sequence(
    contract: dict[str, object],
) -> None:
    layered = contract["focused_extras"]["layered_nonterminal_collisions"]
    actual = {
        item["case_id"]: tuple(
            product["canonical_key"] for product in item["emitted_products"]
        )
        for item in layered
    }

    assert actual == routes._EXPECTED_LAYERED_KEY_SEQUENCES


def test_layered_selector_and_reminder_precedence(
    contract: dict[str, object],
) -> None:
    layered = {
        item["case_id"]: item
        for item in contract["focused_extras"]["layered_nonterminal_collisions"]
    }
    keys = {
        case_id: tuple(product["canonical_key"] for product in item["emitted_products"])
        for case_id, item in layered.items()
    }

    assert (
        keys["A_address_weekday_upcoming"].count(
            "canonicalizer:next_weekday_time_to_timestamp"
        )
        == 2
    )
    assert (
        "canonicalizer:relative_day_time_timestamp"
        not in keys["A_address_weekday_upcoming"]
    )
    assert (
        "derived_value:prepare_upcoming_reminder_search_args"
        in keys["A_address_weekday_upcoming"]
    )
    assert (
        "derived_value:prepare_message_recency_search_args"
        not in keys["A_address_weekday_upcoming"]
    )
    assert (
        "derived_value:prepare_past_reminder_recency_search_args"
        not in keys["A_address_weekday_upcoming"]
    )
    assert keys["A_address_weekday_upcoming"][-1] == (
        "derived_value:extract_address_result"
    )

    assert (
        "derived_value:prepare_message_recency_search_args"
        in keys["B_currency_relative_message"]
    )
    assert (
        keys["B_currency_relative_message"].count(
            "canonicalizer:relative_day_time_timestamp"
        )
        == 2
    )
    assert (
        "derived_value:prepare_past_reminder_recency_search_args"
        not in keys["B_currency_relative_message"]
    )
    assert keys["B_currency_relative_message"][-1] == (
        "derived_value:extract_converted_amount_result"
    )
    assert keys["C_phone_weekday_past"][-1] == (
        "derived_value:extract_phone_number_result"
    )
    assert (
        keys["C_phone_weekday_past"].count(
            "canonicalizer:next_weekday_time_to_timestamp"
        )
        == 2
    )
    assert (
        "derived_value:prepare_past_reminder_recency_search_args"
        in keys["C_phone_weekday_past"]
    )
    assert keys["D_distance_relative_generic_recency"][-1] == (
        "derived_value:extract_distance_result"
    )
    assert (
        "derived_value:resolve_search_window_or_bounds"
        in keys["D_distance_relative_generic_recency"]
    )
    assert (
        "search_filter:select_message_content_by_recency"
        in keys["E_temperature_standalone_message"]
    )
    assert not {
        "derived_value:prepare_upcoming_reminder_search_args",
        "derived_value:prepare_message_recency_search_args",
        "derived_value:prepare_past_reminder_recency_search_args",
        "derived_value:resolve_search_window_or_bounds",
        "search_filter:select_record_by_timestamp_extreme",
    } & set(keys["E_temperature_standalone_message"])
    assert keys["E_temperature_standalone_message"][-1] == (
        "derived_value:extract_temperature_result"
    )

    device_only = layered["F_generic_device_only_reminder_gap"]
    assert not {
        "relative_time",
        "weekday_time",
        "location_phrase",
        "state_precondition_possible",
    } & set(device_only["supplied_context"]["signals"])
    assert (
        "composite:prepare_reminder_creation_args"
        in keys["F_generic_device_only_reminder_gap"]
    )
    assert keys["F_generic_device_only_reminder_gap"][-1] == (
        "derived_value:extract_service_answer_field"
    )
    assert keys["G_no_route_base_signals"] == ()


def test_double_run_products_are_fresh(contract: dict[str, object]) -> None:
    isolation = contract["double_run_mutation_isolation"]

    assert isolation["case_count_per_run"] == 39
    assert isolation["first_mutation_changed_first"] is True
    assert isolation["first_mutation_left_second_unchanged"] is True
    assert isolation["fresh_third_matches_unmutated_second"] is True
    assert isolation["first_second_shared_mutable_count"] == 0
    assert isolation["second_third_shared_mutable_count"] == 0


def test_context_patch_is_restored_after_dispatch_exception() -> None:
    from sage_ts.adequacy import inadequacy_classifier as classifier

    original_context_helper = classifier.visible_task_context_from_scenario
    original_classifier = classifier.classify_visible_task_observations

    def fail_after_context_patch(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("deliberate dispatch failure")

    classifier.classify_visible_task_observations = fail_after_context_patch
    try:
        with pytest.raises(RuntimeError, match="deliberate dispatch failure"):
            routes._invoke_case(classifier, routes._NONTERMINAL_COLLISION)
    finally:
        classifier.classify_visible_task_observations = original_classifier
    assert classifier.visible_task_context_from_scenario is original_context_helper


def test_unhashed_route_tamper_is_rejected(contract: dict[str, object]) -> None:
    tampered = copy.deepcopy(contract)
    tampered["primary_cases"][0]["case_id"] = "tampered"

    with pytest.raises(ValueError, match="body digest"):
        routes.verify_visible_route_trace(tampered)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value["primary_cases"].__setitem__(
            slice(0, 2), list(reversed(value["primary_cases"][:2]))
        ),
        lambda value: value["primary_cases"].pop(4),
        lambda value: value["primary_cases"][2]["emitted_products"][0].__setitem__(
            "raw_observation_scenario_label", "tampered-device-label"
        ),
        lambda value: value["focused_extras"]["layered_nonterminal_collisions"][0][
            "emitted_products"
        ].reverse(),
    ),
    ids=("order", "drop", "device-label", "layered-order"),
)
def test_rehashed_semantic_tamper_is_rejected(
    contract: dict[str, object],
    mutation: object,
) -> None:
    forged = _forged(contract, mutation)

    with pytest.raises(ValueError, match="frozen reference contract"):
        routes.verify_visible_route_trace(forged)
