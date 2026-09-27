"""Focused fail-closed tests for the actor tool-schema contract."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import Any

import pytest

from validation.replay import actor_tool_schema_contracts as contracts


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    value = contracts.build_actor_tool_schema_contract()
    contracts.verify_actor_tool_schema_contract(value)
    return value


def _case(contract: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(item for item in contract["cases"] if item["case_id"] == case_id)


def _target(case: dict[str, Any], target: str) -> dict[str, Any]:
    return next(item for item in case["target_operations"] if item["target"] == target)


def _returned_values(result: dict[str, Any], *, sorted_set: bool = True) -> list[Any]:
    assert result["status"] == "returned"
    typed = result["result"]
    if typed["python_type"] == "set":
        values = typed["sorted"] if sorted_set else typed["iteration"]
    else:
        values = typed.get("items", [])
    return [item["value"] for item in values]


def _target_values(
    case: dict[str, Any],
    target: str,
    operation: str,
) -> list[Any]:
    return _returned_values(_target(case, target)["operations"][operation])


def _rehash(value: dict[str, Any]) -> dict[str, Any]:
    contracts._rehash(value)
    return value


def _category_field_normalization_mutant(
    actor: Any,
    operation: str,
    *,
    normalize_name: Any = None,
    normalize_description: Any = None,
) -> Any:
    original = getattr(actor, operation)

    def mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return original(openai_tools)
        try:
            tools = copy.deepcopy(list(openai_tools))
        except TypeError:
            return original(openai_tools)
        raw_names_by_normalized: dict[str, set[str]] = {}
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            raw_name = function.get("name")
            if isinstance(raw_name, str):
                normalized_name = (
                    normalize_name(raw_name) if normalize_name else raw_name
                )
                function["name"] = normalized_name
                raw_names_by_normalized.setdefault(normalized_name, set()).add(raw_name)
            if normalize_description:
                description = str(function.get("description", ""))
                function["description"] = normalize_description(description)
        selected = original(tools)
        return {
            raw_name
            for normalized_name in selected
            for raw_name in raw_names_by_normalized.get(
                normalized_name,
                {normalized_name},
            )
        }

    return mutant


def _collapse_internal_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def _is_name_description_join(node: ast.AST) -> bool:
    if not isinstance(node, ast.JoinedStr) or len(node.values) != 3:
        return False
    first, separator, second = node.values
    return (
        isinstance(first, ast.FormattedValue)
        and isinstance(first.value, ast.Name)
        and first.value.id == "name"
        and isinstance(separator, ast.Constant)
        and separator.value == " "
        and isinstance(second, ast.FormattedValue)
        and isinstance(second.value, ast.Name)
        and second.value.id == "description"
    )


def _joined_markers_from_source(function: Any) -> tuple[str, ...]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    join_variables = {
        target.id
        for assignment in ast.walk(tree)
        if isinstance(assignment, ast.Assign)
        and _is_name_description_join(assignment.value)
        for target in assignment.targets
        if isinstance(target, ast.Name)
    }
    generators = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.GeneratorExp)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    markers: list[str] = []
    for generator in generators:
        comparison = generator.elt
        if not isinstance(comparison, ast.Compare) or len(comparison.comparators) != 1:
            continue
        compared_text = comparison.comparators[0]
        reads_join = _is_name_description_join(compared_text) or (
            isinstance(compared_text, ast.Name) and compared_text.id in join_variables
        )
        if not reads_join or len(generator.generators) != 1:
            continue
        iterable = generator.generators[0].iter
        if isinstance(iterable, (ast.Tuple, ast.List, ast.Set)):
            markers.extend(
                element.value
                for element in iterable.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
        elif isinstance(iterable, ast.Name) and iterable.id == (
            "ORIGINAL_SIDE_EFFECT_TOOL_NAMES"
        ):
            markers.extend(contracts.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES)
    return tuple(markers)


def test_inventory_and_reference_digest_are_frozen(contract: dict[str, Any]) -> None:
    assert tuple(item["case_id"] for item in contract["cases"]) == (
        contracts.EXPECTED_CASE_IDS
    )
    assert tuple(contract["collection_operations"]) == contracts.COLLECTION_OPERATIONS
    assert tuple(contract["category_operations"]) == contracts.CATEGORY_OPERATIONS
    assert tuple(contract["target_operations"]) == contracts.TARGET_OPERATIONS
    assert tuple(contract["individual_schema_operations"]) == (
        contracts.INDIVIDUAL_SCHEMA_OPERATIONS
    )
    assert contract["integrity"]["canonical_manifest_sha256"] == (
        contracts.EXPECTED_CANONICAL_SHA256
    )
    if os.environ.get("PYTHONHASHSEED") == "0" and not sys.flags.isolated:
        assert contracts._digest(contracts._seed_zero_exact_projection(contract)) == (
            contracts.EXPECTED_HASHSEED_ZERO_BODY_SHA256
        )


def test_replay_probe_exposes_only_cross_process_stable_order(
    contract: dict[str, Any],
) -> None:
    validation_root = Path(__file__).resolve().parents[2]
    replay = contracts.run_probe(validation_root)

    assert "body_sha256" not in replay["integrity"]
    assert replay["integrity"] == {
        "canonical_manifest_sha256": contracts.EXPECTED_CANONICAL_SHA256,
        "process_local_generated_order_verified": True,
        "process_local_tool_name_selection_verified": True,
    }
    assert replay["contract"] == contracts._manifest_projection(
        {key: value for key, value in contract.items() if key != "integrity"}
    )
    assert replay["seed_zero_exact"] == {
        "hash_seed": 0,
        "body_sha256": contracts.EXPECTED_HASHSEED_ZERO_BODY_SHA256,
        "ordering_sha256": contracts.EXPECTED_HASHSEED_ZERO_ORDER_SHA256,
        "selection_order_contract": [
            {
                "target": "generated_exec",
                "schema_first_raw_name": "agent_generated_primary",
                "set_first_raw_name": "agent_generated_secondary",
                "actual_raw_name": "agent_generated_secondary",
                "actual_matches_set_first": True,
            }
        ],
    }


def test_each_category_predicate_has_an_exact_positive_contract(
    contract: dict[str, Any],
) -> None:
    normal = _case(contract, "normal_catalog")
    expected = {
        "_selector_tool_names": ["generated_visible_selector"],
        "_derived_value_tool_names": [
            "extract_service_answer_field",
            "generated_payload_extractor",
        ],
        "_lookup_query_planner_tool_names": [
            "generated_lookup_planner",
            "resolve_search_window_or_bounds",
        ],
        "_search_window_tool_names": ["resolve_search_window_or_bounds"],
        "_relative_time_tool_names": ["relative_day_time_to_timestamp"],
        "_scheduling_timestamp_tool_names": ["next_weekday_time_to_timestamp"],
        "_state_action_planner_tool_names": ["plan_device_state_action_sequence"],
        "_validation_abstention_tool_names": ["prepare_safe_action_or_abstain"],
        "_action_argument_helper_tool_names": ["prepare_contact_action_args"],
        "_post_selection_action_helper_tool_names": ["prepare_selected_contact_action"],
    }

    actual = {
        name: _returned_values(normal["collection_operations"][name])
        for name in contracts.CATEGORY_OPERATIONS
    }
    assert actual == expected


def test_category_branch_matrix_is_complete_and_near_misses_stay_out(
    contract: dict[str, Any],
) -> None:
    expected_counts = {
        "category_branches_selector": (7, 4),
        "category_branches_derived_value": (13, 4),
        "category_branches_lookup_query_planner": (14, 9),
        "category_branches_search_window": (11, 37),
        "category_branches_relative_time": (10, 12),
        "category_branches_scheduling_timestamp": (9, 41),
        "category_branches_state_action_planner": (14, 17),
        "category_branches_validation_abstention": (5, 12),
        "category_branches_action_argument_helper": (63, 19),
        "category_branches_post_selection_action_helper": (46, 14),
    }
    operations: list[str] = []
    positive_count = 0
    near_miss_count = 0

    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        case = _case(contract, case_id)
        branch = case["category_branch_contract"]
        operation = branch["operation"]
        positives = {item["tool_name"] for item in branch["positives"]}
        near_misses = {item["tool_name"] for item in branch["near_misses"]}
        actual = set(_returned_values(case["collection_operations"][operation]))

        assert (len(positives), len(near_misses)) == expected_counts[case_id]
        assert actual == positives
        assert actual.isdisjoint(near_misses)
        assert len({item["alternative_id"] for item in branch["positives"]}) == len(
            positives
        )
        assert len({item["alternative_id"] for item in branch["near_misses"]}) == len(
            near_misses
        )
        operations.append(operation)
        positive_count += len(positives)
        near_miss_count += len(near_misses)

    assert tuple(operations) == contracts.CATEGORY_OPERATIONS
    assert positive_count == 192
    assert near_miss_count == 169


def test_deleting_every_category_alternative_is_detected(
    contract: dict[str, Any],
) -> None:
    mutation_count = 0
    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        baseline = _case(contract, case_id)
        branch = baseline["category_branch_contract"]
        operation = branch["operation"]
        for positive in branch["positives"]:
            mutated = copy.deepcopy(baseline)
            result = mutated["collection_operations"][operation]["result"]
            for key in ("iteration", "sorted"):
                result[key] = [
                    item
                    for item in result[key]
                    if item["value"] != positive["tool_name"]
                ]
            with pytest.raises(ValueError, match="category branch alternatives"):
                contracts._verify_category_branch_contract(mutated)
            mutation_count += 1
    assert mutation_count == 192


def test_admitting_every_category_near_miss_is_detected(
    contract: dict[str, Any],
) -> None:
    mutation_count = 0
    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        baseline = _case(contract, case_id)
        branch = baseline["category_branch_contract"]
        operation = branch["operation"]
        for near_miss in branch["near_misses"]:
            mutated = copy.deepcopy(baseline)
            result = mutated["collection_operations"][operation]["result"]
            typed_name = contracts._typed(near_miss["tool_name"])
            result["iteration"].append(typed_name)
            result["sorted"] = sorted(
                result["iteration"],
                key=contracts._stable_json,
            )
            with pytest.raises(ValueError, match="category branch alternatives"):
                contracts._verify_category_branch_contract(mutated)
            mutation_count += 1
    assert mutation_count == 169


def test_reduced_one_branch_only_family_mutants_are_detected(
    contract: dict[str, Any],
) -> None:
    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        mutated = copy.deepcopy(_case(contract, case_id))
        branch = mutated["category_branch_contract"]
        operation = branch["operation"]
        retained = branch["positives"][0]["tool_name"]
        result = mutated["collection_operations"][operation]["result"]
        result["iteration"] = [
            item for item in result["iteration"] if item["value"] == retained
        ]
        result["sorted"] = list(result["iteration"])
        with pytest.raises(ValueError, match="category branch alternatives"):
            contracts._verify_category_branch_contract(mutated)


@pytest.mark.parametrize("case_id", contracts.CATEGORY_BRANCH_CASE_IDS)
def test_one_branch_only_predicate_code_mutant_is_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    retained = branch["positives"][0]["tool_name"]
    original = getattr(actor, operation)

    def one_branch_only(openai_tools: object) -> set[str]:
        return set(original(openai_tools)) & {retained}

    monkeypatch.setattr(actor, operation, one_branch_only)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_requested_name_and_structural_alternatives_are_explicit(
    contract: dict[str, Any],
) -> None:
    expected_names = {
        "category_branches_derived_value": {
            "d_normalize_p08",
            "d_canonicalize_p09",
            "d_p11",
            "d_p12",
            "d_p13",
        },
        "category_branches_lookup_query_planner": {
            "search_contacts_kwargs_builder",
        },
        "category_branches_relative_time": {"tomorrow_converter"},
        "category_branches_action_argument_helper": {"downstream_tool_kwargs_builder"},
        "category_branches_post_selection_action_helper": {
            "downstream_tool_kwargs_builder"
        },
    }
    for case_id, required_names in expected_names.items():
        branch = _case(contract, case_id)["category_branch_contract"]
        actual_names = {row["tool_name"] for row in branch["positives"]}
        assert required_names <= actual_names

    lookup = _case(
        contract,
        "category_branches_lookup_query_planner",
    )["category_branch_contract"]
    lookup_near_misses = {
        row["alternative_id"]: row["tool_name"] for row in lookup["near_misses"]
    }
    assert lookup_near_misses["output_kwargs_suffix_without_allowed_prefix"] == (
        "l_n08"
    )


def test_every_exact_name_has_all_systematic_near_misses(
    contract: dict[str, Any],
) -> None:
    assert set(contracts.EXACT_NAMES_BY_CATEGORY_CASE) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        branch = _case(contract, case_id)["category_branch_contract"]
        expected = contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
        rows = branch["exact_name_contract"]
        assert tuple(row["exact_name"] for row in rows) == expected
        positives = {row["tool_name"] for row in branch["positives"]}
        near_misses = {row["tool_name"] for row in branch["near_misses"]}
        for row in rows:
            assert row["exact_name"] in positives
            assert row["suffix_near_miss"] in near_misses
            assert row["prefix_near_miss"] in near_misses
            assert row["uppercase_near_miss"] in near_misses
            assert row["mixed_case_near_miss"] in near_misses
            assert row["execution_alias_near_miss"] in near_misses
            assert row["leading_space_near_miss"] in near_misses
            assert row["trailing_space_near_miss"] in near_misses


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    ),
)
def test_exact_name_contains_code_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    spec = next(
        item
        for item in contracts._category_branch_specs()
        if item["case_id"] == case_id
    )
    operation = spec["category_branch_contract"]["operation"]
    exact_names = contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    original = getattr(actor, operation)

    def contains_instead_of_equality_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        for raw_name in actor._tool_names(openai_tools):
            if any(exact_name in raw_name for exact_name in exact_names):
                selected.add(raw_name)
        return selected

    monkeypatch.setattr(actor, operation, contains_instead_of_equality_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    ),
)
def test_exact_name_casefold_code_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    spec = next(
        item
        for item in contracts._category_branch_specs()
        if item["case_id"] == case_id
    )
    operation = spec["category_branch_contract"]["operation"]
    exact_casefolds = {
        name.casefold() for name in contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    }
    original = getattr(actor, operation)

    def casefold_equality_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        selected.update(
            raw_name
            for raw_name in actor._tool_names(openai_tools)
            if raw_name.casefold() in exact_casefolds
        )
        return selected

    monkeypatch.setattr(actor, operation, casefold_equality_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    ),
)
def test_exact_name_strip_code_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    spec = next(
        item
        for item in contracts._category_branch_specs()
        if item["case_id"] == case_id
    )
    operation = spec["category_branch_contract"]["operation"]
    exact_names = set(contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id])
    original = getattr(actor, operation)

    def stripped_exact_name_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        selected.update(
            raw_name
            for raw_name in actor._tool_names(openai_tools)
            if raw_name.strip() in exact_names
        )
        return selected

    monkeypatch.setattr(actor, operation, stripped_exact_name_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    ),
)
def test_execution_alias_normalized_exact_name_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    spec = next(
        item
        for item in contracts._category_branch_specs()
        if item["case_id"] == case_id
    )
    operation = spec["category_branch_contract"]["operation"]
    exact_names = set(contracts.EXACT_NAMES_BY_CATEGORY_CASE[case_id])
    original = getattr(actor, operation)

    def execution_alias_exact_name_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        selected.update(
            raw_name
            for raw_name in actor._tool_names(openai_tools)
            if actor._execution_facing_tool_name(raw_name) in exact_names
        )
        return selected

    monkeypatch.setattr(actor, operation, execution_alias_exact_name_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_subset_extra_field_inventory_is_systematic() -> None:
    assert set(contracts.SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    specs = {item["case_id"]: item for item in contracts._category_branch_specs()}
    for (
        case_id,
        expected_rows,
    ) in contracts.SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE.items():
        branch = specs[case_id]["category_branch_contract"]
        actual_rows = tuple(
            (row["alternative_id"], tuple(row["required_inputs"]))
            for row in branch["subset_extra_contract"]
        )
        assert actual_rows == expected_rows
        schemas_by_name = {
            schema["function"]["name"]: schema for schema in specs[case_id]["tools"]
        }
        for row in branch["subset_extra_contract"]:
            schema = schemas_by_name[row["positive_tool_name"]]
            inputs = set(schema["function"]["parameters"]["properties"])
            assert set(row["required_inputs"]) < inputs


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE[case_id]
    ),
)
def test_exact_input_equality_code_mutants_are_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    subset_rows = branch["subset_extra_contract"]
    original = getattr(actor, operation)

    def equality_instead_of_subset_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        for row in subset_rows:
            actual_inputs = actor._tool_input_names_execution_facing(
                openai_tools,
                row["positive_tool_name"],
            )
            if actual_inputs != set(row["required_inputs"]):
                selected.discard(row["positive_tool_name"])
        return selected

    monkeypatch.setattr(actor, operation, equality_instead_of_subset_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_non_subset_input_inventory_is_systematic() -> None:
    assert set(contracts.NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    specs = {item["case_id"]: item for item in contracts._category_branch_specs()}
    for (
        case_id,
        expected_rows,
    ) in contracts.NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE.items():
        branch = specs[case_id]["category_branch_contract"]
        actual_rows = tuple(
            (row["alternative_id"], tuple(row["minimal_inputs"]))
            for row in branch["non_subset_input_contract"]
        )
        assert actual_rows == expected_rows
        schemas_by_name = {
            schema["function"]["name"]: schema for schema in specs[case_id]["tools"]
        }
        for row in branch["non_subset_input_contract"]:
            schema = schemas_by_name[row["positive_tool_name"]]
            inputs = set(schema["function"]["parameters"]["properties"])
            assert set(row["minimal_inputs"]) < inputs


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if contracts.NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE[case_id]
    ),
)
def test_non_subset_exact_input_code_mutants_are_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    non_subset_rows = branch["non_subset_input_contract"]
    original = getattr(actor, operation)

    def exact_inputs_instead_of_membership_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        for row in non_subset_rows:
            actual_inputs = actor._tool_input_names_execution_facing(
                openai_tools,
                row["positive_tool_name"],
            )
            if actual_inputs != set(row["minimal_inputs"]):
                selected.discard(row["positive_tool_name"])
        return selected

    monkeypatch.setattr(
        actor,
        operation,
        exact_inputs_instead_of_membership_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_joined_name_description_inventory_matches_accepted_source() -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    source_inventory: dict[str, tuple[str, ...]] = {}
    for case_id in contracts.CATEGORY_BRANCH_CASE_IDS:
        operation = contracts.FIELD_NORMALIZATION_PLANS[case_id]["operation"]
        markers = _joined_markers_from_source(getattr(actor, operation))
        if markers:
            source_inventory[case_id] = markers
    assert source_inventory == (
        contracts.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE
    )
    assert tuple(source_inventory) == contracts.JOINED_NAME_DESCRIPTION_CATEGORY_CASES


def test_field_normalization_matrix_is_complete_and_exact(
    contract: dict[str, Any],
) -> None:
    assert contracts.ACTION_ARGUMENT_PREPARATION_MARKERS == (
        "prepare the arguments",
        "prepares the arguments",
        "prepare arguments",
        "prepares arguments",
        "prepare the call",
        "prepares the call",
        "prepare final",
        "prepares final",
        "prepare exact kwargs",
        "prepares exact kwargs",
        "safe downstream kwargs",
        "downstream_tool_kwargs",
        "side-effect",
        "action argument",
    )
    assert contracts.ACTION_ARGUMENT_RETURN_MARKERS == (
        "should_call_tool",
        "should_call_add_reminder",
        "downstream tool",
        "downstream_tool_name",
        "downstream_tool_kwargs",
        "original toolsandbox",
        *contracts.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES,
    )
    assert contracts.POST_SELECTION_ACTION_MARKERS == (
        "downstream_tool_kwargs",
        "side-effect",
        "prepare arguments",
        "prepare the arguments",
        "prepares the arguments",
        "prepare the call",
        "prepares the call",
        "safe downstream kwargs",
        "selected record",
        *contracts.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES,
    )
    expected_joined_markers = {
        "category_branches_derived_value": (
            "extract",
            "normalize",
            "canonicalize",
            "deterministic extraction",
        ),
        "category_branches_lookup_query_planner": (
            "search_contacts_kwargs",
            "lookup query",
            "query planner",
            "prepare search",
            "search kwargs",
        ),
        "category_branches_relative_time": (
            "relative local day",
            "relative day",
            "tomorrow",
            "timestamp",
        ),
        "category_branches_action_argument_helper": (
            *contracts.ACTION_ARGUMENT_PREPARATION_MARKERS,
            *contracts.ACTION_ARGUMENT_RETURN_MARKERS,
        ),
        "category_branches_post_selection_action_helper": (
            *contracts.POST_SELECTION_ACTION_MARKERS,
        ),
    }
    assert contracts.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE == (
        expected_joined_markers
    )
    assert contracts.JOINED_NAME_DESCRIPTION_CATEGORY_CASES == (
        "category_branches_derived_value",
        "category_branches_lookup_query_planner",
        "category_branches_relative_time",
        "category_branches_action_argument_helper",
        "category_branches_post_selection_action_helper",
    )
    assert set(contracts.FIELD_NORMALIZATION_PLANS) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    assert set(contracts.STRUCTURAL_CASE_INSENSITIVE_FIELDS_BY_CATEGORY_CASE) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    assert set(contracts.CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE) == set(
        contracts.CATEGORY_BRANCH_CASE_IDS
    )
    field_cases = [
        case for case in contract["cases"] if "field_normalization_contract" in case
    ]
    assert tuple(case["case_id"] for case in field_cases) == (
        contracts.FIELD_NORMALIZATION_CASE_IDS
    )
    field_probe_count = 0
    composition_probe_count = 0
    whitespace_probe_count = 0
    schema_type_probe_count = 0
    for case in field_cases:
        matrix = case["field_normalization_contract"]
        rows = matrix["rows"]
        token_plans = contracts._field_token_plans(matrix["category_case_id"])
        expected_probe_ids = {
            f"{token_kind}_{field}_{casing}"
            for token_kind, _token, _read_fields in token_plans
            for field in contracts.FIELD_MATRIX_FIELDS
            for casing in contracts.FIELD_MATRIX_CASINGS
        }
        assert len(rows) == len(token_plans) * 21
        assert {row["probe_id"] for row in rows} == expected_probe_ids
        assert tuple(matrix["joined_scan_markers"]) == expected_joined_markers.get(
            matrix["category_case_id"],
            (),
        )
        expected_markers = contracts.CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[
            matrix["category_case_id"]
        ]
        assert tuple(matrix["cross_field_markers"]) == expected_markers
        assert tuple(matrix["cross_field_variants"]) == (
            contracts.CROSS_FIELD_COMPOSITION_VARIANTS
        )
        composition_rows = matrix["composition_rows"]
        expected_splits = {
            (marker, split_index, left, right)
            for marker in expected_markers
            for split_index, (left, right) in enumerate(
                contracts._cross_field_marker_splits(marker),
                start=1,
            )
        }
        assert len(composition_rows) == len(expected_splits) * len(
            contracts.CROSS_FIELD_COMPOSITION_VARIANTS,
        )
        assert {(row["marker"], row["variant"]) for row in composition_rows} == {
            (marker, variant)
            for marker in expected_markers
            for variant in contracts.CROSS_FIELD_COMPOSITION_VARIANTS
        }
        assert {
            (row["marker"], row["split_index"], row["left"], row["right"])
            for row in composition_rows
        } == expected_splits
        assert tuple(matrix["whitespace_edge_variants"]) == (
            contracts.JOINED_FIELD_WHITESPACE_EDGE_VARIANTS
        )
        assert tuple(matrix["whitespace_internal_placements"]) == (
            contracts.JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS
        )
        whitespace_rows = matrix["whitespace_rows"]
        expected_whitespace_edges = {
            (marker, variant, None)
            for marker in expected_markers
            for variant in contracts.JOINED_FIELD_WHITESPACE_EDGE_VARIANTS
        }
        expected_whitespace_internal = {
            (marker, placement, boundary_index)
            for marker in expected_markers
            for boundary_index, _split in enumerate(
                contracts._cross_field_marker_splits(marker),
                start=1,
            )
            for placement in contracts.JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS
        }
        assert {
            (row["marker"], row["variant"], row["boundary_index"])
            for row in whitespace_rows
        } == expected_whitespace_edges | expected_whitespace_internal
        expected_schema_types = (
            contracts.DERIVED_SCHEMA_TYPE_VALUES
            if matrix["category_case_id"] == "category_branches_derived_value"
            else ()
        )
        assert tuple(matrix["schema_type_values"]) == expected_schema_types
        assert tuple(matrix["schema_type_casings"]) == (
            contracts.DERIVED_SCHEMA_TYPE_CASINGS if expected_schema_types else ()
        )
        schema_type_rows = matrix["schema_type_rows"]
        assert {(row["json_type"], row["casing"]) for row in schema_type_rows} == {
            (json_type, casing)
            for json_type in expected_schema_types
            for casing in contracts.DERIVED_SCHEMA_TYPE_CASINGS
        }
        actual = set(
            _returned_values(case["collection_operations"][matrix["operation"]])
        )
        expected = {
            row["tool_name"]
            for row in (*rows, *composition_rows, *whitespace_rows, *schema_type_rows)
            if row["expected_member"]
        }
        assert actual == expected
        field_probe_count += len(rows)
        composition_probe_count += len(composition_rows)
        whitespace_probe_count += len(whitespace_rows)
        schema_type_probe_count += len(schema_type_rows)

    assert field_probe_count == 483
    assert composition_probe_count == 369
    assert whitespace_probe_count == 194
    assert schema_type_probe_count == 18
    assert (
        field_probe_count
        + composition_probe_count
        + whitespace_probe_count
        + schema_type_probe_count
        == 1064
    )

    derived = _case(contract, "field_normalization_derived_value")
    derived_matrix = derived["field_normalization_contract"]
    uppercase_raw = next(
        row
        for row in derived_matrix["rows"]
        if row["probe_id"] == "lexical_raw_name_uppercase"
    )
    assert uppercase_raw["tool_name"] == "D_EXTRACT_CUSTOM"
    assert uppercase_raw["expected_member"] is False

    selector = _case(contract, "field_normalization_selector")
    selector_matrix = selector["field_normalization_contract"]
    output_only_records = next(
        row
        for row in selector_matrix["rows"]
        if row["probe_id"] == "structural_direct_output_property_lowercase"
    )
    assert output_only_records["expected_member"] is False

    relative = _case(contract, "category_branches_relative_time")
    exact_row = relative["category_branch_contract"]["exact_name_contract"][0]
    assert exact_row["execution_alias_near_miss"] == "relative_alias_custom"

    for category_case_id in contracts.JOINED_NAME_DESCRIPTION_CATEGORY_CASES:
        field_case_id = category_case_id.replace(
            "category_branches_",
            "field_normalization_",
        )
        matrix = _case(contract, field_case_id)["field_normalization_contract"]
        for marker in contracts.CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[
            category_case_id
        ]:
            marker_rows = [
                row for row in matrix["composition_rows"] if row["marker"] == marker
            ]
            mask_reason = contracts.CROSS_FIELD_MASK_REASONS.get(
                (category_case_id, marker)
            )
            expected_variants = (
                set(contracts.CROSS_FIELD_COMPOSITION_VARIANTS)
                if mask_reason
                else {
                    "forward_lowercase",
                    "forward_uppercase_description",
                    "raw_name_leading_space",
                    "description_trailing_space",
                }
            )
            assert {
                row["variant"] for row in marker_rows if row["expected_member"]
            } == expected_variants
            assert {row["mask_reason"] for row in marker_rows} == {mask_reason}

    derived_composition = derived_matrix["composition_rows"]
    assert derived_composition
    assert all(row["expected_member"] for row in derived_composition)
    assert all(not row["cross_boundary_required"] for row in derived_composition)
    assert {row["mask_reason"] for row in derived_composition} == {
        "description 'extraction' independently matches marker 'extract'"
    }

    relative_composition = _case(
        contract,
        "field_normalization_relative_time",
    )["field_normalization_contract"]["composition_rows"]
    relative_day = next(
        row
        for row in relative_composition
        if row["marker"] == "relative day" and row["variant"] == "forward_lowercase"
    )
    assert (relative_day["left"], relative_day["right"]) == ("relative", "day")
    assert relative_day["cross_boundary_required"] is True
    relative_day_leading_description = next(
        row
        for row in relative_composition
        if row["marker"] == "relative day"
        and row["variant"] == "description_leading_space"
    )
    assert relative_day_leading_description["tool_name"].endswith("relative")
    assert relative_day_leading_description["description"] == " day"
    assert relative_day_leading_description["expected_member"] is False

    action_composition = _case(
        contract,
        "field_normalization_action_argument_helper",
    )["field_normalization_contract"]["composition_rows"]
    prepare_final = next(
        row
        for row in action_composition
        if row["marker"] == "prepare final" and row["variant"] == "forward_lowercase"
    )
    assert (prepare_final["left"], prepare_final["description"]) == (
        "prepare",
        "final original toolsandbox",
    )
    assert prepare_final["cross_boundary_required"] is True

    post_composition = _case(
        contract,
        "field_normalization_post_selection_action_helper",
    )["field_normalization_contract"]["composition_rows"]
    selected_record = next(
        row
        for row in post_composition
        if row["marker"] == "selected record" and row["variant"] == "forward_lowercase"
    )
    assert (selected_record["left"], selected_record["right"]) == (
        "selected",
        "record",
    )
    assert selected_record["cross_boundary_required"] is True

    type_rows = derived_matrix["schema_type_rows"]
    for json_type in contracts.DERIVED_SCHEMA_TYPE_VALUES:
        rows_for_type = [row for row in type_rows if row["json_type"] == json_type]
        assert {row["casing"] for row in rows_for_type if row["expected_member"]} == {
            "lowercase"
        }


def test_toggling_every_field_matrix_result_is_detected(
    contract: dict[str, Any],
) -> None:
    mutation_count = 0
    for baseline in contract["cases"]:
        matrix = baseline.get("field_normalization_contract")
        if not matrix:
            continue
        operation = matrix["operation"]
        boundary_rows = [
            *matrix["rows"],
            *matrix["composition_rows"],
            *matrix["whitespace_rows"],
            *matrix["schema_type_rows"],
        ]
        for row in boundary_rows:
            mutated = copy.deepcopy(baseline)
            result = mutated["collection_operations"][operation]["result"]
            typed_name = contracts._typed(row["tool_name"])
            if row["expected_member"]:
                result["iteration"] = [
                    item
                    for item in result["iteration"]
                    if item["value"] != row["tool_name"]
                ]
            else:
                result["iteration"].append(typed_name)
            result["sorted"] = sorted(
                result["iteration"],
                key=contracts._stable_json,
            )
            with pytest.raises(ValueError, match="field-normalization behavior"):
                contracts._verify_field_normalization_contract(mutated)
            mutation_count += 1
    assert mutation_count == 1064


@pytest.mark.parametrize(
    "case_id",
    tuple(
        case_id
        for case_id in contracts.CATEGORY_BRANCH_CASE_IDS
        if any(
            "raw_name" in read_fields
            for _token_kind, _token, read_fields in contracts._field_token_plans(
                case_id
            )
        )
    ),
)
def test_raw_name_casefolding_code_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    spec = next(
        item
        for item in contracts._field_normalization_specs()
        if item["field_normalization_contract"]["category_case_id"] == case_id
    )
    matrix = spec["field_normalization_contract"]
    operation = matrix["operation"]
    casefold_raw_names = {
        row["tool_name"]
        for row in matrix["rows"]
        if row["field"] == "raw_name"
        and row["casing"] != "lowercase"
        and "raw_name"
        in next(
            read_fields
            for token_kind, _token, read_fields in contracts._field_token_plans(case_id)
            if token_kind == row["token_kind"]
        )
    }
    original = getattr(actor, operation)

    def raw_name_casefold_mutant(openai_tools: object) -> set[str]:
        visible = actor._tool_names(openai_tools)
        return set(original(openai_tools)) | (visible & casefold_raw_names)

    monkeypatch.setattr(actor, operation, raw_name_casefold_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_derived_split_field_scanner_is_explicitly_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    text_markers = contracts.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE[
        "category_branches_derived_value"
    ]

    def split_field_scanner_mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return set()
        helpers: set[str] = set()
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            description = str(function.get("description", "")).lower()
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            input_names = set(properties) if isinstance(properties, dict) else set()
            if not isinstance(name, str) or not input_names:
                continue
            input_types = (
                {
                    prop.get("type")
                    for prop in properties.values()
                    if isinstance(prop, dict)
                }
                if isinstance(properties, dict)
                else set()
            )
            has_payload_input = bool(input_types & {"object", "array"})
            scalar_only_extra_inputs = input_types <= {
                "object",
                "array",
                "string",
                "number",
                "integer",
                "boolean",
            }
            if len(input_names) != 1 and not (
                has_payload_input and scalar_only_extra_inputs
            ):
                continue
            if any(token in name or token in description for token in text_markers):
                helpers.add(name)
        return helpers

    monkeypatch.setattr(actor, "_derived_value_tool_names", split_field_scanner_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    contracts.verify_actor_tool_schema_contract(mutant)
    derived = _case(mutant, "field_normalization_derived_value")
    rows = derived["field_normalization_contract"]["composition_rows"]
    assert rows
    assert all(row["mask_reason"] for row in rows)
    assert all(not row["cross_boundary_required"] for row in rows)


def test_lookup_split_field_scanner_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    text_markers = contracts.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE[
        "category_branches_lookup_query_planner"
    ]

    def split_field_scanner_mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return set()
        planners: set[str] = set()
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            description = str(function.get("description", "")).lower()
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            input_names = set(properties) if isinstance(properties, dict) else set()
            output_schema = function.get("output_schema")
            output_properties = (
                output_schema.get("properties", {})
                if isinstance(output_schema, dict)
                else {}
            )
            if not isinstance(output_properties, dict):
                output_properties = {}
            if not isinstance(name, str) or not input_names:
                continue
            prepares_search_kwargs = any(
                str(key).startswith(("search_", "find_", "get_"))
                and str(key).endswith("_kwargs")
                for key in output_properties
            ) or any(token in name or token in description for token in text_markers)
            requires_prior_records = bool(
                input_names
                & {"records", "candidates", "selected_record", "contact_record"}
            )
            if prepares_search_kwargs and not requires_prior_records:
                planners.add(name)
        return planners

    monkeypatch.setattr(
        actor,
        "_lookup_query_planner_tool_names",
        split_field_scanner_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_relative_time_split_field_scanner_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    text_markers = contracts.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE[
        "category_branches_relative_time"
    ]

    def split_field_scanner_mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return set()
        helpers: set[str] = set()
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            description = str(function.get("description", "")).lower()
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            input_names = set(properties) if isinstance(properties, dict) else set()
            if not isinstance(name, str):
                continue
            is_relative_time_helper = name == "relative_day_time_to_timestamp" or (
                {"current_timestamp", "day_offset", "hour", "minute"}.issubset(
                    input_names
                )
                and any(token in name or token in description for token in text_markers)
            )
            if is_relative_time_helper:
                helpers.add(name)
        return helpers

    monkeypatch.setattr(actor, "_relative_time_tool_names", split_field_scanner_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_action_argument_split_field_scanner_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    def split_field_scanner_mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return set()
        helpers: set[str] = set()
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            description = str(function.get("description", "")).lower()
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            input_names = set(properties) if isinstance(properties, dict) else set()
            if not isinstance(name, str) or not input_names:
                continue
            prepares_side_effect_args = any(
                token in name or token in description
                for token in contracts.ACTION_ARGUMENT_PREPARATION_MARKERS
            )
            returns_downstream_call = any(
                token in name or token in description
                for token in contracts.ACTION_ARGUMENT_RETURN_MARKERS
            )
            requires_prior_records = bool(
                input_names
                & {"records", "candidates", "selected_record", "contact_record"}
            )
            if (
                prepares_side_effect_args
                and returns_downstream_call
                and not requires_prior_records
            ):
                helpers.add(name)
        return helpers

    monkeypatch.setattr(
        actor,
        "_action_argument_helper_tool_names",
        split_field_scanner_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_post_selection_split_field_scanner_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    def split_field_scanner_mutant(openai_tools: object) -> set[str]:
        if openai_tools is actor.NOT_GIVEN:
            return set()
        helpers: set[str] = set()
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            description = str(function.get("description", "")).lower()
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            input_names = set(properties) if isinstance(properties, dict) else set()
            if not isinstance(name, str):
                continue
            needs_selected_record = bool(
                input_names
                & {
                    "selected_record",
                    "contact_record",
                    "record",
                    "records",
                    "candidates",
                }
            )
            prepares_downstream_args = any(
                token in name or token in description
                for token in contracts.POST_SELECTION_ACTION_MARKERS
            )
            if needs_selected_record and prepares_downstream_args:
                helpers.add(name)
        return helpers

    monkeypatch.setattr(
        actor,
        "_post_selection_action_helper_tool_names",
        split_field_scanner_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    ("normalization_id", "normalize_name", "normalize_description"),
    (
        ("raw_name_strip", str.strip, None),
        ("description_strip", None, str.strip),
        ("raw_name_whitespace_collapse", _collapse_internal_whitespace, None),
        (
            "description_whitespace_collapse",
            None,
            _collapse_internal_whitespace,
        ),
    ),
)
@pytest.mark.parametrize(
    "case_id",
    contracts.JOINED_NAME_DESCRIPTION_CATEGORY_CASES,
)
def test_joined_field_strip_and_collapse_code_mutants_are_detected_or_masked(
    monkeypatch: pytest.MonkeyPatch,
    normalization_id: str,
    normalize_name: Any,
    normalize_description: Any,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    operation = contracts.FIELD_NORMALIZATION_PLANS[case_id]["operation"]
    mutant_operation = _category_field_normalization_mutant(
        actor,
        operation,
        normalize_name=normalize_name,
        normalize_description=normalize_description,
    )
    monkeypatch.setattr(actor, operation, mutant_operation)
    mutant = contracts.build_actor_tool_schema_contract()
    if case_id == "category_branches_derived_value":
        contracts.verify_actor_tool_schema_contract(mutant)
        rows = _case(mutant, "field_normalization_derived_value")[
            "field_normalization_contract"
        ]["composition_rows"]
        assert rows
        assert all(row["mask_reason"] for row in rows)
        return
    with pytest.raises(
        ValueError,
        match="category branch alternatives|field-normalization behavior",
    ):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_derived_schema_type_casefold_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    original = actor._derived_value_tool_names
    allowed_types = set(contracts.DERIVED_SCHEMA_TYPE_VALUES)

    def casefold_schema_types_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        if openai_tools is actor.NOT_GIVEN:
            return selected
        for tool in openai_tools:
            function = tool.get("function", {})
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            parameters = function.get("parameters", {})
            properties = (
                parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            )
            if not isinstance(name, str) or not isinstance(properties, dict):
                continue
            if len(properties) <= 1:
                continue
            normalized_types = {
                str(definition.get("type")).casefold()
                for definition in properties.values()
                if isinstance(definition, dict)
            }
            has_payload = bool(normalized_types & {"object", "array"})
            marker_text = f"{name} {str(function.get('description', '')).lower()}"
            is_extractor = any(
                token in marker_text
                for token in (
                    "extract",
                    "normalize",
                    "canonicalize",
                    "deterministic extraction",
                )
            )
            if has_payload and normalized_types <= allowed_types and is_extractor:
                selected.add(name)
        return selected

    monkeypatch.setattr(
        actor,
        "_derived_value_tool_names",
        casefold_schema_types_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_selector_output_fields_merged_into_inputs_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    original = actor._selector_tool_names

    def output_fields_as_inputs_mutant(openai_tools: object) -> set[str]:
        selected = set(original(openai_tools))
        for raw_name in actor._tool_names(openai_tools):
            description = actor._tool_description_execution_facing(
                openai_tools,
                raw_name,
            ).lower()
            outputs = actor._tool_output_names_execution_facing(
                openai_tools,
                raw_name,
            )
            if "records" in outputs and "selected_record" in description:
                selected.add(raw_name)
        return selected

    monkeypatch.setattr(actor, "_selector_tool_names", output_fields_as_inputs_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="field-normalization behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_derived_value_three_plus_input_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    derived_spec = next(
        item
        for item in contracts._category_branch_specs()
        if item["case_id"] == "category_branches_derived_value"
    )
    schema = next(
        item for item in derived_spec["tools"] if item["function"]["name"] == "d_p13"
    )
    properties = schema["function"]["parameters"]["properties"]
    assert len(properties) == 4
    assert {"object", "string", "integer"} <= {
        definition["type"] for definition in properties.values()
    }

    original = actor._derived_value_tool_names

    def at_most_two_inputs_mutant(openai_tools: object) -> set[str]:
        return {
            name
            for name in original(openai_tools)
            if len(actor._tool_input_names_execution_facing(openai_tools, name)) <= 2
        }

    monkeypatch.setattr(actor, "_derived_value_tool_names", at_most_two_inputs_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    ("case_id", "alternative_prefix"),
    (
        ("category_branches_derived_value", "marker_"),
        ("category_branches_lookup_query_planner", "name_marker_"),
        ("category_branches_relative_time", "required_inputs_name_marker_"),
        ("category_branches_action_argument_helper", "name_"),
        ("category_branches_post_selection_action_helper", "name_"),
    ),
)
def test_name_only_branch_code_mutants_are_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    alternative_prefix: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    name_only = {
        row["tool_name"]
        for row in branch["positives"]
        if row["alternative_id"].startswith(alternative_prefix)
        and (
            case_id != "category_branches_derived_value"
            or row["alternative_id"].endswith("_in_name")
        )
    }
    assert name_only
    original = getattr(actor, operation)

    def description_only_mutant(openai_tools: object) -> set[str]:
        return set(original(openai_tools)) - name_only

    monkeypatch.setattr(actor, operation, description_only_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize(
    "case_id",
    (
        "category_branches_action_argument_helper",
        "category_branches_post_selection_action_helper",
    ),
)
def test_broad_all_native_tool_name_code_mutants_are_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    read_only_native_near_misses = {
        row["tool_name"]
        for row in branch["near_misses"]
        if row["alternative_id"].startswith("read_only_native_")
    }
    assert len(read_only_native_near_misses) == 12
    original = getattr(actor, operation)

    def all_native_names_mutant(openai_tools: object) -> set[str]:
        return set(original(openai_tools)) | read_only_native_near_misses

    monkeypatch.setattr(actor, operation, all_native_names_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


@pytest.mark.parametrize("case_id", contracts.CATEGORY_BRANCH_CASE_IDS)
def test_removed_structural_gate_code_mutants_are_rejected(
    contract: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    branch = _case(contract, case_id)["category_branch_contract"]
    operation = branch["operation"]
    structural_near_misses = {
        row["tool_name"]
        for row in branch["near_misses"]
        if not row["alternative_id"].startswith("exact_name_")
        and not row["alternative_id"].startswith("read_only_native_")
    }
    assert structural_near_misses
    original = getattr(actor, operation)

    def weakened_gate_mutant(openai_tools: object) -> set[str]:
        return set(original(openai_tools)) | structural_near_misses

    monkeypatch.setattr(actor, operation, weakened_gate_mutant)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_lookup_arbitrary_kwargs_suffix_code_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    original = actor._lookup_query_planner_tool_names

    def arbitrary_kwargs_suffix_mutant(openai_tools: object) -> set[str]:
        planners = set(original(openai_tools))
        for raw_name in actor._tool_names(openai_tools):
            if not actor._tool_input_names_execution_facing(openai_tools, raw_name):
                continue
            outputs = actor._tool_output_names_execution_facing(
                openai_tools,
                raw_name,
            )
            if any(output.endswith("_kwargs") for output in outputs):
                planners.add(raw_name)
        return planners

    monkeypatch.setattr(
        actor,
        "_lookup_query_planner_tool_names",
        arbitrary_kwargs_suffix_mutant,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="category branch alternatives"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_producer_names_are_frozen_at_each_current_schema_location(
    contract: dict[str, Any],
) -> None:
    case = _case(contract, "producer_schema_locations")
    producer_contract = case["producer_location_contract"]
    expected = producer_contract["expected_by_target"]
    actual = {
        target: _target_values(
            case,
            target,
            "_declared_service_answer_producers",
        )
        for target in expected
    }

    assert actual == expected
    placements = producer_contract["placements_by_producer"]
    assert set(placements) == set(contracts.FIXTURE_SERVICE_PRODUCER_NAMES)
    for producer, locations in placements.items():
        for location in (
            "raw_name",
            "description",
            "input_property",
            "nested_output_property",
            "alias_first_schema",
        ):
            assert actual[locations[location]] == [producer]
        assert actual[locations["direct_output_near_miss"]] == []
        assert actual[locations["lexical_near_miss"]] == []
    for nonmember, target in producer_contract[
        "nonmember_constant_near_misses"
    ].items():
        assert nonmember == "search_stock"
        assert actual[target] == []


def test_behavior_defining_constant_inventories_are_exact(
    contract: dict[str, Any],
) -> None:
    assert contract["behavior_constant_inventories"] == {
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES": list(
            contracts.EXPECTED_ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        ),
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES": list(
            contracts.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        ),
        "SERVICE_ANSWER_PRODUCER_TOOLS": list(
            contracts.EXPECTED_SERVICE_ANSWER_PRODUCER_TOOLS
        ),
    }


@pytest.mark.parametrize(
    ("constant_name", "added_name"),
    (
        ("ORIGINAL_SIDE_EFFECT_TOOL_NAMES", "search_messages"),
        ("SERVICE_ANSWER_PRODUCER_TOOLS", "search_stock"),
        ("ORIGINAL_TOOLSANDBOX_TOOL_NAMES", "invented_native_tool"),
    ),
)
def test_behavior_constant_addition_code_mutants_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    added_name: str,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    monkeypatch.setattr(
        actor,
        constant_name,
        set(getattr(actor, constant_name)) | {added_name},
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="constant inventory"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_description_only_producer_scanner_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    def description_only(openai_tools: object, tool_name: str) -> tuple[str, ...]:
        description = actor._tool_description_execution_facing(
            openai_tools,
            tool_name,
        ).lower()
        return tuple(
            name
            for name in sorted(actor.SERVICE_ANSWER_PRODUCER_TOOLS)
            if name in description
        )

    monkeypatch.setattr(
        actor,
        "_declared_service_answer_producers",
        description_only,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="producer schema location behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_full_function_json_producer_scanner_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    def full_function_json(openai_tools: object, tool_name: str) -> tuple[str, ...]:
        if openai_tools is actor.NOT_GIVEN:
            return ()
        target = actor._execution_facing_tool_name(tool_name)
        for schema in openai_tools:
            if actor._tool_schema_execution_name(schema) != target:
                continue
            text = json.dumps(schema.get("function", {}), sort_keys=True).lower()
            return tuple(
                name
                for name in sorted(actor.SERVICE_ANSWER_PRODUCER_TOOLS)
                if name in text
            )
        return ()

    monkeypatch.setattr(
        actor,
        "_declared_service_answer_producers",
        full_function_json,
    )
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="producer schema location behavior"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_aliases_duplicates_and_first_schema_wins(contract: dict[str, Any]) -> None:
    aliases = _case(contract, "aliases_and_duplicates")

    assert [row["raw_name"]["value"] for row in aliases["schema_order"]] == [
        "agent_native_search",
        "agent_generated_primary",
        "agent_generated_secondary",
        "agent_generated_primary",
    ]
    assert _returned_values(aliases["collection_operations"]["_tool_names"]) == [
        "agent_generated_primary",
        "agent_generated_secondary",
        "agent_native_search",
    ]
    assert _returned_values(
        aliases["collection_operations"]["_tool_names_execution_facing"]
    ) == ["generated_exec", "search_contacts"]
    assert _returned_values(
        aliases["collection_operations"]["_generated_tool_names_execution_facing"]
    ) == ["generated_exec", "generated_exec"]

    assert _target_values(
        aliases,
        "generated_exec",
        "_tool_input_names_execution_facing",
    ) == ["first_input"]
    assert _target_values(
        aliases,
        "generated_exec",
        "_tool_output_names_execution_facing",
    ) == ["first_output"]
    assert aliases["generated_order_contract"]["matches"] is True


def test_direct_nested_empty_and_malformed_output_schema_boundaries(
    contract: dict[str, Any],
) -> None:
    outputs = _case(contract, "output_schema_boundaries")
    expected = {
        "direct_and_nested": ["direct_output"],
        "nested_only": ["nested_only_output"],
        "empty_direct": ["fallback_nested_output"],
        "malformed_direct": [],
        "direct_output_planner": ["search_contacts_kwargs"],
        "nested_output_only_planner": ["search_contacts_kwargs"],
    }

    actual = {
        target: _target_values(
            outputs,
            target,
            "_tool_output_names_execution_facing",
        )
        for target in expected
    }
    assert actual == expected
    assert _returned_values(
        outputs["collection_operations"]["_lookup_query_planner_tool_names"]
    ) == ["direct_output_planner"]


def test_mapping_subclasses_preserve_dict_vs_mapping_distinctions(
    contract: dict[str, Any],
) -> None:
    mappings = _case(contract, "mapping_and_malformed_members")
    raw_names = _returned_values(mappings["collection_operations"]["_tool_names"])

    assert "agent_mapping_function" not in raw_names
    assert raw_names == [
        "agent_mapping_parameters",
        "mapping_outer",
        "properties_as_list",
    ]
    assert _target_values(
        mappings,
        "mapping_function_exec",
        "_tool_input_names_execution_facing",
    ) == ["mapping_function_input"]
    assert _target_values(
        mappings,
        "mapping_parameters_exec",
        "_tool_input_names_execution_facing",
    ) == ["mapping_parameter_input"]
    assert _returned_values(
        mappings["collection_operations"]["_derived_value_tool_names"]
    ) == ["mapping_outer"]

    individual = mappings["individual_schema_operations"]
    mapping_function_name = individual[0]["operations"]["_tool_schema_execution_name"][
        "result"
    ]["value"]
    assert mapping_function_name == "mapping_function_exec"
    assert (
        individual[3]["operations"]["_tool_schema_execution_name"]["result"]["value"]
        == ""
    )
    assert (
        individual[5]["operations"]["_tool_schema_text"]["result"]["value"] == "17 {}"
    )


def test_not_given_and_empty_boundaries_remain_distinct_but_empty(
    contract: dict[str, Any],
) -> None:
    not_given = _case(contract, "not_given")
    empty = _case(contract, "empty")

    for case in (not_given, empty):
        for operation in contracts.COLLECTION_OPERATIONS:
            assert _returned_values(case["collection_operations"][operation]) == []
        for target in case["target_operations"]:
            operations = target["operations"]
            assert (
                _returned_values(operations["_tool_input_names_execution_facing"]) == []
            )
            assert (
                _returned_values(operations["_tool_output_names_execution_facing"])
                == []
            )

    assert not_given["freshness"] == {"applicable": False}
    assert empty["freshness"]["applicable"] is True
    assert not_given["individual_schema_operations"] == []
    assert empty["individual_schema_operations"] == []


@pytest.mark.parametrize(
    ("label", "exception_type"),
    (
        ("none", "TypeError"),
        ("scalar_member", "AttributeError"),
        ("exploding_mapping", "RuntimeError"),
    ),
)
def test_collection_exception_class_boundaries_are_frozen_without_messages(
    contract: dict[str, Any],
    label: str,
    exception_type: str,
) -> None:
    results = contract["boundary_exceptions"]["collection_boundaries"][label]
    assert set(results) == set(contracts.COLLECTION_OPERATIONS)
    assert {
        (result["status"], result["exception_type"], "message" in result)
        for result in results.values()
    } == {("raised", exception_type, False)}


def test_individual_schema_exception_boundaries_are_exact(
    contract: dict[str, Any],
) -> None:
    results = contract["boundary_exceptions"]["individual_boundaries"]
    assert {
        label: {
            (item["status"], item["exception_type"], "message" in item)
            for item in operations.values()
        }
        for label, operations in results.items()
    } == {
        "none": {("raised", "AttributeError", False)},
        "integer": {("raised", "AttributeError", False)},
        "exploding_mapping": {("raised", "RuntimeError", False)},
    }


def test_results_are_fresh_container_agnostic_and_nonmutating(
    contract: dict[str, Any],
) -> None:
    for case in contract["cases"]:
        assert case["input_unchanged"] is True
        freshness = case["freshness"]
        if freshness["applicable"]:
            for result in freshness["operations"].values():
                assert result == {
                    "same_identity": False,
                    "mutation_supported": True,
                    "mutation_leaked": False,
                    "second_matches_fresh_third": True,
                }
        equivalence = case["container_equivalence"]
        if equivalence["applicable"]:
            for result in equivalence["operations"].values():
                assert result["list_equals_tuple"] is True
                assert result["list_equals_iterator"] is True


def test_name_mapping_and_fallbacks_are_frozen(contract: dict[str, Any]) -> None:
    names = contract["name_mapping"]

    assert (
        names["functions.search_contacts"]["execution_facing"]["result"]["value"]
        == "search_contacts"
    )
    assert (
        names["agent_native_search"]["execution_facing"]["result"]["value"]
        == "search_contacts"
    )
    assert names["generated_exec"]["agent_facing"]["result"]["value"] == (
        "agent_generated_fallback"
    )
    assert (
        names["execution_mapping_error"]["execution_facing"]["result"]["value"]
        == "execution_mapping_error"
    )
    assert names["agent_mapping_error"]["agent_facing"]["result"]["value"] == (
        "agent_mapping_error"
    )


def test_tool_name_for_call_keeps_set_derived_selection_order(
    contract: dict[str, Any],
) -> None:
    aliases = _case(contract, "aliases_and_duplicates")
    order = aliases["generated_order_contract"]
    target_rows = {item["target"]: item for item in aliases["target_operations"]}

    for target in aliases["set_order_derived_targets"]:
        execution_target = order["execution_by_raw"].get(target, target)
        expected = next(
            raw
            for raw in order["raw_name_set_iteration"]
            if order["execution_by_raw"][raw] == execution_target
        )
        actual = target_rows[target]["operations"]["_tool_name_for_call"]["result"][
            "value"
        ]
        assert actual == expected


def test_seeded_children_prove_set_first_not_schema_first_across_seeds() -> None:
    validation_root = Path(__file__).resolve().parents[2]
    seed_zero = contracts._run_seeded_child(validation_root, 0)
    seed_one = contracts._run_seeded_child(validation_root, 1)
    zero = seed_zero["selection_order_contract"][0]
    one = seed_one["selection_order_contract"][0]

    assert seed_zero["body_sha256"] == contracts.EXPECTED_HASHSEED_ZERO_BODY_SHA256
    assert seed_zero["ordering_sha256"] == (
        contracts.EXPECTED_HASHSEED_ZERO_ORDER_SHA256
    )
    for selection in (zero, one):
        assert selection["actual_matches_set_first"] is True
        assert selection["actual_raw_name"] == selection["set_first_raw_name"]
        assert selection["schema_first_raw_name"] == "agent_generated_primary"
    assert zero["set_first_raw_name"] == "agent_generated_secondary"
    assert one["set_first_raw_name"] == "agent_generated_primary"


def test_unordered_category_set_iteration_is_not_frozen(
    contract: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(contract)
    case = _case(mutated, "category_branches_lookup_query_planner")
    result = case["collection_operations"]["_lookup_query_planner_tool_names"]["result"]
    before = contracts._digest(contracts._seed_zero_exact_projection(mutated))
    result["iteration"].reverse()
    _rehash(mutated)

    assert contracts._digest(contracts._seed_zero_exact_projection(mutated)) == before
    contracts.verify_actor_tool_schema_contract(mutated)


def test_native_unique_raw_name_set_order_is_not_frozen(
    contract: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(contract)
    normal = _case(mutated, "normal_catalog")
    raw_names = normal["collection_operations"]["_tool_names"]["result"]["iteration"]
    indexes = {
        item["value"]: index
        for index, item in enumerate(raw_names)
        if item["value"] in {"search_contacts", "add_reminder"}
    }
    assert set(indexes) == {"search_contacts", "add_reminder"}
    left = indexes["search_contacts"]
    right = indexes["add_reminder"]
    before = contracts._digest(contracts._seed_zero_exact_projection(mutated))
    raw_names[left], raw_names[right] = raw_names[right], raw_names[left]
    _rehash(mutated)

    assert contracts._digest(contracts._seed_zero_exact_projection(mutated)) == before
    contracts.verify_actor_tool_schema_contract(mutated)


def test_generated_name_order_remains_frozen(contract: dict[str, Any]) -> None:
    mutated = copy.deepcopy(contract)
    normal = _case(mutated, "normal_catalog")
    generated = normal["collection_operations"][
        "_generated_tool_names_execution_facing"
    ]["result"]["items"]
    assert len(generated) >= 2
    generated[0], generated[1] = generated[1], generated[0]
    _rehash(mutated)

    assert contracts._digest(contracts._seed_zero_exact_projection(mutated)) != (
        contracts.EXPECTED_HASHSEED_ZERO_BODY_SHA256
    )
    if os.environ.get("PYTHONHASHSEED") == "0" and not sys.flags.isolated:
        with pytest.raises(ValueError, match="hash-seed-zero semantics"):
            contracts.verify_actor_tool_schema_contract(mutated)


def test_schema_first_tool_name_mutant_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.isolated:
        pytest.skip("schema-first mutant requires the declared seed-zero test process")

    from sage_ts.adapters import openai_toolsandbox_roles as actor

    def schema_first(openai_tools: object, execution_tool_name: str) -> str:
        if openai_tools is not actor.NOT_GIVEN:
            for schema in openai_tools:
                function = schema.get("function", {})
                raw_name = function.get("name") if isinstance(function, dict) else None
                if (
                    isinstance(raw_name, str)
                    and actor._execution_facing_tool_name(raw_name)
                    == execution_tool_name
                ):
                    return raw_name
        return actor._agent_facing_tool_name(execution_tool_name)

    monkeypatch.setattr(actor, "_tool_name_for_call", schema_first)
    mutant = contracts.build_actor_tool_schema_contract()
    with pytest.raises(ValueError, match="set-derived tool-name selection"):
        contracts.verify_actor_tool_schema_contract(mutant)


def test_unhashed_tamper_is_rejected(contract: dict[str, Any]) -> None:
    tampered = copy.deepcopy(contract)
    tampered["cases"][0]["schema_order"][0]["raw_name"]["value"] = "tampered"

    with pytest.raises(ValueError, match="body digest"):
        contracts.verify_actor_tool_schema_contract(tampered)


def test_rehashed_generated_order_tamper_is_rejected(
    contract: dict[str, Any],
) -> None:
    tampered = copy.deepcopy(contract)
    tampered["cases"][0]["generated_order_contract"]["actual_generated_order"].reverse()

    with pytest.raises(ValueError, match="set-derived generated-tool ordering"):
        contracts.verify_actor_tool_schema_contract(_rehash(tampered))


def test_rehashed_category_tamper_is_rejected(contract: dict[str, Any]) -> None:
    tampered = copy.deepcopy(contract)
    selector = tampered["cases"][0]["collection_operations"]["_selector_tool_names"][
        "result"
    ]
    selector["iteration"].append(contracts._typed("tampered_selector"))
    selector["sorted"] = sorted(selector["iteration"], key=contracts._stable_json)

    with pytest.raises(ValueError, match="frozen reference contract"):
        contracts.verify_actor_tool_schema_contract(_rehash(tampered))


def test_context_patch_is_restored_after_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    original_context = actor.get_current_context

    def fail_after_patch(_actor: Any) -> tuple[dict[str, Any], ...]:
        raise RuntimeError("deliberate schema contract failure")

    monkeypatch.setattr(contracts, "_case_specs", fail_after_patch)
    with pytest.raises(RuntimeError, match="deliberate schema contract failure"):
        contracts.build_actor_tool_schema_contract()
    assert actor.get_current_context is original_context
