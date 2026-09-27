"""Focused tests for the black-box visible signal contract."""

from __future__ import annotations

import copy

import pytest

from validation.replay import visible_signal_contracts as signals


@pytest.fixture(scope="module")
def contract() -> dict[str, object]:
    value = signals.build_visible_signal_trace()
    signals.verify_visible_signal_trace(value)
    return value


def test_all_ordered_add_sites_have_isolated_carriers(
    contract: dict[str, object],
) -> None:
    cases = contract["site_cases"]

    assert len(cases) == 49
    assert [case["site"] for case in cases] == list(range(1, 50))
    assert len({case["case_id"] for case in cases}) == 49
    assert all(case["target_in_positive"] for case in cases)
    assert not any(case["target_in_negative"] for case in cases)


def test_all_final_signals_are_observed(contract: dict[str, object]) -> None:
    observed = {
        signal
        for case in contract["site_cases"]
        for side in ("positive", "negative")
        for signal in case[side]["signals"]
    }

    assert observed == set(signals._ALL_FINAL_SIGNALS)
    assert len(observed) == 44


def test_literal_aliases_and_discriminating_near_misses(
    contract: dict[str, object],
) -> None:
    assert sum(len(group["cases"]) for group in contract["alias_groups"]) == 354
    assert all(
        group["target"] in case["result"]["signals"]
        for group in contract["alias_groups"]
        for case in group["cases"]
    )
    assert all(
        item["target"] not in item["result"]["signals"]
        for item in contract["near_misses"]
    )
    assert (
        sum(len(group["cases"]) for group in contract["suppression_alias_groups"]) == 43
    )
    assert all(
        group["suppressed_signal"] not in item["result"]["signals"]
        for group in contract["suppression_alias_groups"]
        for item in group["cases"]
    )


def test_phone_number_boundaries(contract: dict[str, object]) -> None:
    actual = {
        item["case_id"]: "has_phone_number" in item["result"]["signals"]
        for item in contract["phone_boundaries"]
    }

    assert actual == {
        "seven_digits": True,
        "fifteen_digits": True,
        "dotted": True,
        "six_digits": False,
        "sixteen_digits": False,
        "alphanumeric": False,
        "uuid": False,
        "latitude_longitude": False,
    }


def test_duplicate_insertions_keep_first_position(
    contract: dict[str, object],
) -> None:
    duplicate = contract["duplicate_insertions"]
    insufficient = duplicate["insufficient_information_three_sites"]["signals"]
    safe_relative = duplicate["safe_abstain_first_then_relative"]["signals"]
    safe_send = duplicate["safe_abstain_modify_then_send"]["signals"]

    assert insufficient.count("insufficient_information") == 1
    assert insufficient.index("insufficient_information") == 0
    assert safe_relative.count("safe_abstain_needed") == 1
    assert safe_relative.index("safe_abstain_needed") == 4
    assert safe_send.count("safe_abstain_needed") == 1
    assert safe_send.index("safe_abstain_needed") == 2


def test_forward_order_traps_are_explicit(contract: dict[str, object]) -> None:
    traps = contract["forward_order_traps"]
    counterparty = traps["message_recency_before_counterparty"]["signals"]
    holiday = traps["holiday_after_state_precondition"]["signals"]

    assert "message_counterparty_lookup" in counterparty
    assert "message_recency" not in counterparty
    assert "holiday" in holiday
    assert "state_precondition_possible" not in holiday


def test_tool_names_are_exact_and_inventory_is_set_like(
    contract: dict[str, object],
) -> None:
    assert len(contract["exact_tool_names"]) == 26
    for item in contract["exact_tool_names"]:
        assert item["exact_contains_target"] == item["expected_exact_contains_target"]
        assert (
            item["near_miss_contains_target"] != item["expected_exact_contains_target"]
        )

    inventory = contract["tool_inventory_set_semantics"]
    expected = (
        inventory["base"]["signals"],
        inventory["base"]["primary_family"],
    )
    for name in ("reversed", "duplicates", "unknown_appended"):
        assert (
            inventory[name]["signals"],
            inventory[name]["primary_family"],
        ) == expected


def test_primary_family_priority_and_fallback(contract: dict[str, object]) -> None:
    cases = contract["primary_family_cases"]

    assert [item["primary_family"] for item in cases[:19]] == list(
        signals._PRIMARY_PRIORITY
    )
    assert [item["primary_family"] for item in cases[-4:]] == [
        "relationship_batch_update",
        "relationship_batch_update",
        "general_visible_task",
        "general_visible_task",
    ]


def test_immutable_input_values_are_preserved_and_calls_repeat_exactly(
    contract: dict[str, object],
) -> None:
    assert all(
        result["immutable_inputs_equal_after_call"]
        for result in signals._all_results(contract)
    )
    repeated = contract["deterministic_repeated_calls"]
    assert repeated["equal"] is True
    assert repeated["first"] == repeated["second"]


def _expect_semantic_mutant_rejected(
    signal_mutant: signals.SignalFunction | None = None,
    family_mutant: signals.FamilyFunction | None = None,
) -> None:
    signal_fn, family_fn = signals._production_functions()
    mutant_contract = signals.build_visible_signal_trace(
        signal_fn=signal_mutant or signal_fn,
        family_fn=family_mutant or family_fn,
    )

    with pytest.raises(ValueError, match="frozen reference contract"):
        signals.verify_visible_signal_trace(mutant_contract)


@pytest.mark.parametrize(
    "mutation",
    ("drop", "reorder", "add"),
)
def test_guard_rejects_actual_signal_rule_mutants(mutation: str) -> None:
    production_signal_fn, _ = signals._production_functions()

    def mutant(request: str, tools: tuple[str, ...]) -> tuple[str, ...]:
        value = list(production_signal_fn(request, tools))
        if mutation == "drop" and "message_recency" in value:
            value.remove("message_recency")
        elif mutation == "reorder" and {
            "message",
            "message_recency",
        } <= set(value):
            left = value.index("message")
            right = value.index("message_recency")
            value[left], value[right] = value[right], value[left]
        elif mutation == "add" and request == "insufficient information":
            value.append("unexpected_visible_signal")
        return tuple(value)

    _expect_semantic_mutant_rejected(signal_mutant=mutant)


def test_guard_rejects_actual_primary_priority_mutant() -> None:
    def reverse_priority(value: tuple[str, ...]) -> str:
        for signal in reversed(signals._PRIMARY_PRIORITY):
            if signal in value:
                return signal
        return "general_visible_task"

    _expect_semantic_mutant_rejected(family_mutant=reverse_priority)


def test_unhashed_and_rehashed_data_tampering_is_rejected(
    contract: dict[str, object],
) -> None:
    unhashed = copy.deepcopy(contract)
    unhashed["site_cases"][0]["positive"]["signals"] = []
    with pytest.raises(ValueError, match="body digest"):
        signals.verify_visible_signal_trace(unhashed)

    rehashed = copy.deepcopy(contract)
    rehashed["site_cases"].reverse()
    signals._rehash(rehashed)
    with pytest.raises(ValueError, match="frozen reference contract"):
        signals.verify_visible_signal_trace(rehashed)
