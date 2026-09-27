"""Source-level mutation-strength tests for the black-box signal corpus."""

from __future__ import annotations

from collections import Counter

import pytest

from validation.replay import visible_signal_contracts as contracts
from validation.replay import visible_signal_mutation_audit as audit


@pytest.fixture(scope="module")
def mutation_report() -> dict[str, object]:
    return audit.run_mutation_audit()


def test_mutation_inventory_is_complete_and_fail_closed(
    mutation_report: dict[str, object],
) -> None:
    mutations = audit.enumerate_mutations()

    audit.verify_mutation_audit(mutation_report)
    assert (
        audit.mutation_audit_projection(mutation_report)
        == audit.EXPECTED_MUTATION_AUDIT
    )

    assert Counter(item.kind for item in mutations) == {
        "literal": 419,
        "tool": 101,
        "boolean_operand": 223,
        "string_constant": 122,
        "helper_string": 51,
        "temporal_prefix": 15,
    }
    assert mutation_report["mutation_count"] == 931
    assert mutation_report["caught_count"] == 862
    assert mutation_report["invisible_count"] == 69
    assert mutation_report["expected_equivalent_count"] == 69
    assert mutation_report["unexpected_invisible"] == []
    assert mutation_report["unexpected_caught_equivalence"] == []

    for row in mutation_report["rows"]:
        if row["caught"]:
            assert row["changes"]
            assert all(
                change["baseline"] != change["mutant"] for change in row["changes"]
            )
        else:
            assert row["mutation"] in audit.EXPECTED_EQUIVALENT_MUTANTS
            assert audit.EXPECTED_EQUIVALENT_MUTANTS[row["mutation"]]


@pytest.mark.parametrize(
    ("mutation_key", "carrier_id"),
    (
        ("literal:243:2:everyone", "relationship_everyone"),
        ("literal:232:5:phone", "contact_lookup_phone_operand"),
        ("literal:403:2:text", "message_followup_text_domain"),
        (
            "literal:404:1:sent me",
            "message_followup_sent_me_suppression",
        ),
        ("literal:475:4:delete", "missing_search_delete_action"),
        ("literal:625:15:sent last", "recency_sent_last_terminal"),
        ("literal:881:0:find", "external_phone_find_verb"),
        (
            "tool:774:12:search_location_around_lat_lon",
            "location_around_is_stateful_downstream",
        ),
        (
            "string_constant:592:12:requested_remove_contact",
            "remove_request_suppresses_location_phrase",
        ),
        (
            "string_constant:596:12:direct_contact_action",
            "direct_action_suppresses_location_phrase",
        ),
        (
            "string_constant:844:12:requested_remove_contact",
            "remove_request_suppresses_external_phone_lookup",
        ),
        (
            "string_constant:847:12:direct_contact_action",
            "direct_action_suppresses_external_phone_lookup",
        ),
        (
            "helper_string:_visible_reverse_geocode_request:7:12: address ",
            "reverse_geocode_space_address_alias",
        ),
        (
            "helper_string:_visible_reverse_geocode_request:8:12:address of",
            "reverse_geocode_address_of_alias",
        ),
        (
            "helper_string:_visible_reverse_geocode_request:9:12:what is the address",
            "reverse_geocode_what_is_address_alias",
        ),
        (
            "helper_string:_visible_reverse_geocode_request:10:12:where is",
            "reverse_geocode_where_is_alias",
        ),
        (
            "helper_string:_visible_reverse_geocode_request:11:12:location of",
            "reverse_geocode_location_of_alias",
        ),
        ("temporal_prefix:4:tomorrow", "temporal_at_tomorrow"),
    ),
)
def test_reviewed_source_mutants_have_specific_carriers(
    mutation_report: dict[str, object],
    mutation_key: str,
    carrier_id: str,
) -> None:
    row = next(
        item for item in mutation_report["rows"] if item["mutation"] == mutation_key
    )

    assert row["caught"] is True
    assert any(carrier_id in path for path in row["changed_paths"])


@pytest.fixture(scope="module")
def baseline_results() -> dict[str, tuple[object, ...]]:
    signal_fn, family_fn = contracts._production_functions()
    return audit._flatten_results(contracts._semantic_body(signal_fn, family_fn))


@pytest.mark.parametrize(
    ("kind", "name", "carrier_id"),
    (
        ("named", "absolute_date_false", "absolute_date_iso"),
        ("named", "drop_natural_text_regex", "natural_text_recipient_regex"),
        (
            "named",
            "ignore_safe_abstain_precondition",
            "safe_abstain_suppresses_state_precondition",
        ),
        ("named", "broaden_tell_boundary", "teller_boundary_negative"),
        (
            "helper",
            "reverse_geocode_location_leak",
            "reverse_geocode_suppresses_location_phrase",
        ),
        ("helper", "reject_parenthesized_phone", "parenthesized_phone"),
        ("helper", "reject_dotted_phone", "dotted"),
        ("helper", "allow_alphanumeric_phone", "alphanumeric"),
        ("helper", "allow_temporal_at_location", "temporal_at_not_location"),
        (
            "helper",
            "allow_weather_stopword_location",
            "weather_stopword_not_location",
        ),
        ("helper", "reject_bare_city_weather", "weather_bare_city_location"),
    ),
)
def test_reviewed_predicate_and_regex_mutants_are_rejected(
    baseline_results: dict[str, tuple[object, ...]],
    kind: str,
    name: str,
    carrier_id: str,
) -> None:
    mutant = (
        audit.compile_named_mutant(name)
        if kind == "named"
        else audit.compile_helper_override(name)
    )
    _signal_fn, family_fn = contracts._production_functions()
    mutant_results = audit._flatten_results(contracts._semantic_body(mutant, family_fn))
    changed = {
        path
        for path in baseline_results.keys() | mutant_results.keys()
        if baseline_results.get(path) != mutant_results.get(path)
    }

    assert any(carrier_id in path for path in changed)
    mutant_contract = contracts.build_visible_signal_trace(
        signal_fn=mutant,
        family_fn=family_fn,
    )
    with pytest.raises(ValueError, match="frozen reference contract"):
        contracts.verify_visible_signal_trace(mutant_contract)
