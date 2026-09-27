"""Fail-closed classifier replay corpus for the external validation harness.

The corpus deliberately lives outside the installed SAGE package.  It freezes
the classifier's observable values and Python container types without freezing
the classifier's source layout, so a behavior-preserving refactor can move code
while a semantic or order change still fails.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import math
import random
from collections import OrderedDict
from enum import Enum
from typing import Any


EXPECTED_CONTRACT: dict[str, Any] = {
    "body": {
        "byte_count": 5_039_270,
        "sha256": "cbf49dfae370fa8a11c7e487a5fd627a249282735e393dc00362a1e5c768f637",
    },
    "task_count": 1_032,
    "observation_count": 1_874,
    "ordered_hashes": {
        "scenario_names": {
            "byte_count": 104_681,
            "sha256": "41f7a899d68a5752d4d9d48b155a8fea204efa23982e57f3439e89efba773992",
        },
        "signals": {
            "byte_count": 306_164,
            "sha256": "570d2dce84bd67cfb51d6b6bf834a21b6257be18640f2bd3f2ffc9b708d57df9",
        },
        "primary_families": {
            "byte_count": 177_014,
            "sha256": "639f552b140a78e1a29d214e3aa2e7360f0a6203f9728c5926a57bc17c41c0c0",
        },
        "observations": {
            "byte_count": 18_528_798,
            "sha256": "39116920ec579a53ab4a792df50ac05485dcc64d02c8e93af597f4080c55185a",
        },
        "cases": {
            "byte_count": 4_546_526,
            "sha256": "ea7aaa3961d57a4b832b80419f84dc87f4b1ccac083665fb9af87d222b0d81c5",
        },
    },
    "factory_count": 32,
    "expected_result_key_sequence_count": 21,
    "scalar_expected_type_count": 2,
    "duplicate_case_count": 8,
    "benchmark_collision_count": 726,
    "factory_refactor_guards": {
        "byte_count": 244_896,
        "sha256": "029a38fa90af28c0c7d2a9066847e1303c8ad8d1fde8c8913509243216c961b2",
    },
    "direct_factory_count": 11,
    "direct_factory_example_count": 38,
    "location_non_alias_case_count": 9,
}


_FACTORY_REFACTOR_SPECS: tuple[tuple[str, str], ...] = (
    ("service", "_external_service_answer_extraction_observation"),
    ("service", "_address_answer_extraction_observation"),
    ("service", "_currency_answer_extraction_observation"),
    ("service", "_phone_answer_extraction_observation"),
    ("service", "_distance_answer_extraction_observation"),
    ("service", "_temperature_answer_extraction_observation"),
    ("location", "_location_search_argument_observation"),
    ("location", "_broad_location_search_argument_observation"),
    ("search", "_prepare_upcoming_reminder_search_args_observation"),
    ("search", "_prepare_message_recency_search_args_observation"),
    ("search", "_prepare_past_reminder_recency_search_args_observation"),
)

_EXPECTED_FACTORY_MUTABLE_COUNTS: dict[str, int] = {
    "_external_service_answer_extraction_observation": 28,
    "_address_answer_extraction_observation": 12,
    "_currency_answer_extraction_observation": 8,
    "_phone_answer_extraction_observation": 8,
    "_distance_answer_extraction_observation": 8,
    "_temperature_answer_extraction_observation": 16,
    "_location_search_argument_observation": 20,
    "_broad_location_search_argument_observation": 16,
    "_prepare_upcoming_reminder_search_args_observation": 9,
    "_prepare_message_recency_search_args_observation": 9,
    "_prepare_past_reminder_recency_search_args_observation": 9,
}


def _typed(value: Any) -> dict[str, Any]:
    """Return a JSON value that preserves Python type and insertion order."""

    if value is None:
        return {"type": "none"}
    if type(value) is bool:
        return {"type": "bool", "value": value}
    if type(value) is int:
        return {"type": "int", "value": str(value)}
    if type(value) is float:
        if math.isnan(value):
            representation = "nan"
        elif math.isinf(value):
            representation = "inf" if value > 0 else "-inf"
        else:
            representation = value.hex()
        return {"type": "float", "value": representation}
    if type(value) is str:
        return {"type": "str", "value": value}
    if type(value) is bytes:
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, Enum):
        return {
            "type": "enum",
            "class": type(value).__name__,
            "name": value.name,
            "value": _typed(value.value),
        }
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "type": "dataclass",
            "class": type(value).__name__,
            "fields": [
                [field.name, _typed(getattr(value, field.name))]
                for field in dataclasses.fields(value)
            ],
        }
    if type(value) is dict or isinstance(value, OrderedDict):
        return {
            "type": "dict",
            "items": [[_typed(key), _typed(item)] for key, item in value.items()],
        }
    if type(value) is list:
        return {"type": "list", "items": [_typed(item) for item in value]}
    if type(value) is tuple:
        return {"type": "tuple", "items": [_typed(item) for item in value]}
    if type(value) is set:
        items = [_typed(item) for item in value]
        items.sort(key=_canonical_bytes)
        return {"type": "set", "items": items}
    if type(value) is frozenset:
        items = [_typed(item) for item in value]
        items.sort(key=_canonical_bytes)
        return {"type": "frozenset", "items": items}
    raise TypeError(
        "Classifier corpus encountered an unsupported value type: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any, *, already_typed: bool = False) -> dict[str, Any]:
    tagged = value if already_typed else _typed(value)
    raw = _canonical_bytes(tagged)
    return {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _static_factory_contract(observation: Any) -> tuple[Any, ...]:
    """Remove request-specific routing fields from one factory product."""

    return (
        observation.canonical_key,
        observation.observation,
        observation.allowed_families,
        observation.validation_examples,
        observation.generation_allowed,
        observation.inadequacy_signals,
        observation.failed_tool_calls,
        observation.repeated_failed_tool_calls,
        observation.visible_data_gaps,
        observation.planner_failures,
        observation.final_answer_route_mismatch,
    )


def _observation_summary(index: int, observation: Any) -> dict[str, Any]:
    return {
        "emission_index": index,
        "canonical_key": observation.canonical_key,
        "task_family_key": observation.task_family_key,
        "reason": observation.reason,
        "evidence_source": observation.evidence_source,
        "prompt": _digest(observation.observation),
        "validation_examples": _digest(observation.validation_examples),
        "factory_product": _digest(_static_factory_contract(observation)),
        "exact_observation": _digest(observation),
    }


def _mutable_ids(value: Any) -> set[int]:
    seen: set[int] = set()

    def visit(item: Any) -> None:
        if dataclasses.is_dataclass(item) and not isinstance(item, type):
            for field in dataclasses.fields(item):
                visit(getattr(item, field.name))
            return
        if isinstance(item, dict):
            seen.add(id(item))
            for key, nested in item.items():
                visit(key)
                visit(nested)
            return
        if isinstance(item, (list, set)):
            seen.add(id(item))
            for nested in item:
                visit(nested)
            return
        if isinstance(item, (tuple, frozenset)):
            for nested in item:
                visit(nested)

    visit(value)
    return seen


def _mutable_identity_topology(value: Any) -> dict[str, Any]:
    """Describe repeated dict/list/set identities using deterministic paths."""

    occurrences: dict[int, dict[str, Any]] = {}
    active: set[int] = set()

    def visit(item: Any, path: list[dict[str, Any]]) -> None:
        if dataclasses.is_dataclass(item) and not isinstance(item, type):
            for field in dataclasses.fields(item):
                visit(
                    getattr(item, field.name),
                    [*path, {"kind": "field", "name": field.name}],
                )
            return

        mutable = isinstance(item, (dict, list, set))
        if mutable:
            identity = id(item)
            entry = occurrences.setdefault(
                identity,
                {"type": type(item).__name__, "paths": []},
            )
            entry["paths"].append(path)
            if identity in active:
                return
            active.add(identity)

        if isinstance(item, dict):
            for index, (key, nested) in enumerate(item.items()):
                visit(
                    key,
                    [*path, {"kind": "mapping_key", "index": index}],
                )
                visit(
                    nested,
                    [
                        *path,
                        {
                            "kind": "mapping_value",
                            "index": index,
                            "key": _typed(key),
                        },
                    ],
                )
        elif isinstance(item, (list, tuple)):
            for index, nested in enumerate(item):
                visit(nested, [*path, {"kind": "sequence_item", "index": index}])
        elif isinstance(item, (set, frozenset)):
            ordered = sorted(item, key=lambda nested: _canonical_bytes(_typed(nested)))
            for index, nested in enumerate(ordered):
                visit(nested, [*path, {"kind": "set_item", "index": index}])

        if mutable:
            active.remove(id(item))

    visit(value, [])
    alias_groups = [entry for entry in occurrences.values() if len(entry["paths"]) > 1]
    return {
        "mutable_container_count": len(occurrences),
        "mutable_container_occurrence_count": sum(
            len(entry["paths"]) for entry in occurrences.values()
        ),
        "duplicate_mutable_identity_count": len(alias_groups),
        "alias_groups": alias_groups,
    }


def _ordered_shape(value: Any) -> dict[str, Any]:
    """Describe container shape and mapping-key order without hiding values."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "type": "dataclass",
            "class": type(value).__name__,
            "fields": [
                [field.name, _ordered_shape(getattr(value, field.name))]
                for field in dataclasses.fields(value)
            ],
        }
    if isinstance(value, dict):
        return {
            "type": "dict",
            "items": [
                {
                    "key": _typed(key),
                    "value_shape": _ordered_shape(item),
                }
                for key, item in value.items()
            ],
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": type(value).__name__,
            "items": [_ordered_shape(item) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        items = [_ordered_shape(item) for item in value]
        items.sort(key=_canonical_bytes)
        return {"type": type(value).__name__, "items": items}
    typed = _typed(value)
    return {
        "type": typed["type"],
        **({"class": typed["class"]} if "class" in typed else {}),
    }


def _example_shape(index: int, example: Any) -> dict[str, Any]:
    """Localize exact example values separately from ordered container shape."""

    return {
        "index": index,
        "held_out": example.held_out,
        "negative_applicability": example.negative_applicability,
        "inputs": _digest(example.inputs),
        "input_shape": _ordered_shape(example.inputs),
        "expected": _digest(example.expected),
        "expected_shape": _ordered_shape(example.expected),
    }


def _direct_factory_guard(
    classifier: Any,
    *,
    group: str,
    factory_name: str,
) -> dict[str, Any]:
    """Characterize one factory and prove products have fresh mutable data."""

    factory = getattr(classifier, factory_name)
    scenario_name = f"replay_factory_guard:{factory_name}"
    first = factory(scenario_name)
    second = factory(scenario_name)
    first_before = _digest(first)
    second_before = _digest(second)
    shared_before = _mutable_ids(first) & _mutable_ids(second)
    if not first.validation_examples:
        raise AssertionError(f"{factory_name} produced no validation examples")
    first_example = first.validation_examples[0]
    first_example.inputs["__factory_mutation_probe__"] = [factory_name]
    if isinstance(first_example.expected, dict):
        first_example.expected["__factory_mutation_probe__"] = {"first": True}
    first_after = _digest(first)
    second_after = _digest(second)
    third = factory(scenario_name)
    third_after = _digest(third)
    return {
        "group": group,
        "factory_name": factory_name,
        "scenario_name": scenario_name,
        "canonical_key": second.canonical_key,
        "example_count": len(second.validation_examples),
        "factory_product": _digest(_static_factory_contract(second)),
        "exact_observation": second_before,
        "within_product_mutable_topology": _mutable_identity_topology(second),
        "examples": [
            _example_shape(index, example)
            for index, example in enumerate(second.validation_examples)
        ],
        "freshness": {
            "first_before": first_before,
            "first_after": first_after,
            "second_before": second_before,
            "second_after": second_after,
            "third_after": third_after,
            "first_mutation_changed_first": first_before != first_after,
            "first_mutation_left_second_unchanged": second_before == second_after,
            "fresh_third_matches_unmutated_second": second_before == third_after,
            "first_second_shared_mutable_count": len(shared_before),
            "second_third_shared_mutable_count": len(
                _mutable_ids(second) & _mutable_ids(third)
            ),
        },
    }


def _location_kwargs_non_alias_cases(
    classifier: Any,
) -> list[dict[str, Any]]:
    """Prove paired location kwargs are distinct inside every example."""

    cases: list[dict[str, Any]] = []
    location_factories = (
        "_location_search_argument_observation",
        "_broad_location_search_argument_observation",
    )
    for factory_name in location_factories:
        observation = getattr(classifier, factory_name)(
            f"replay_location_alias_guard:{factory_name}"
        )
        for index, example in enumerate(observation.validation_examples):
            expected = example.expected
            if not isinstance(expected, dict):
                raise AssertionError(
                    f"{factory_name} example {index} expected a mapping"
                )
            search_kwargs = expected.get("search_location_kwargs")
            downstream_kwargs = expected.get("downstream_tool_kwargs")
            if not isinstance(search_kwargs, dict) or not isinstance(
                downstream_kwargs, dict
            ):
                raise AssertionError(
                    f"{factory_name} example {index} lacks location kwargs mappings"
                )
            search_before = _digest(search_kwargs)
            downstream_before = _digest(downstream_kwargs)
            shared_before = _mutable_ids(search_kwargs) & _mutable_ids(
                downstream_kwargs
            )
            search_kwargs["__location_kwargs_alias_probe__"] = factory_name
            search_after = _digest(search_kwargs)
            downstream_after = _digest(downstream_kwargs)
            cases.append(
                {
                    "factory_name": factory_name,
                    "example_index": index,
                    "search_before": search_before,
                    "search_after": search_after,
                    "downstream_before": downstream_before,
                    "downstream_after": downstream_after,
                    "same_object_before": search_kwargs is downstream_kwargs,
                    "shared_mutable_count_before": len(shared_before),
                    "search_mutation_changed_search": search_before != search_after,
                    "search_mutation_left_downstream_unchanged": (
                        downstream_before == downstream_after
                    ),
                }
            )
    return cases


def _factory_refactor_guards(classifier: Any) -> dict[str, Any]:
    factories = [
        _direct_factory_guard(
            classifier,
            group=group,
            factory_name=factory_name,
        )
        for group, factory_name in _FACTORY_REFACTOR_SPECS
    ]
    return {
        "schema_version": 1,
        "factories": factories,
        "location_kwargs_non_alias": _location_kwargs_non_alias_cases(classifier),
    }


def _mutation_isolation(
    classifier: Any, scenario_name: str, scenario: Any
) -> dict[str, Any]:
    first = classifier.classify_visible_task_observations(scenario_name, scenario)
    second = classifier.classify_visible_task_observations(scenario_name, scenario)
    first_before = _digest(first)
    second_before = _digest(second)
    shared_before = _mutable_ids(first) & _mutable_ids(second)
    if not first or not first[0].validation_examples:
        raise AssertionError("mutation-isolation fixture produced no examples")
    example = first[0].validation_examples[0]
    example.inputs["__classifier_mutation_probe__"] = ["first-only"]
    if isinstance(example.expected, dict):
        example.expected["__classifier_mutation_probe__"] = {"first": True}
    first_after = _digest(first)
    second_after = _digest(second)
    third = classifier.classify_visible_task_observations(scenario_name, scenario)
    third_after = _digest(third)
    shared_with_third = _mutable_ids(second) & _mutable_ids(third)
    return {
        "scenario": scenario_name,
        "first_before": first_before,
        "first_after": first_after,
        "second_before": second_before,
        "second_after": second_after,
        "third_after": third_after,
        "first_mutation_changed_first": first_before != first_after,
        "first_mutation_left_second_unchanged": second_before == second_after,
        "fresh_third_matches_unmutated_second": second_before == third_after,
        "first_second_shared_mutable_count": len(shared_before),
        "second_third_shared_mutable_count": len(shared_with_third),
    }


class _FakeRows:
    def __init__(self, rows: tuple[dict[str, Any], ...]) -> None:
        self._rows = rows

    def iter_rows(self, *, named: bool) -> Any:
        if not named:
            raise AssertionError("classifier must request named sandbox rows")
        return iter(self._rows)


class _FakeStartingContext:
    def __init__(
        self,
        rows: tuple[dict[str, Any], ...],
        tools: tuple[str, ...],
    ) -> None:
        self._rows = rows
        self._tools = tools

    def get_database(self, *_args: Any, **_kwargs: Any) -> _FakeRows:
        return _FakeRows(self._rows)

    def get_available_tools(self, *, scrambling_allowed: bool) -> tuple[str, ...]:
        if scrambling_allowed:
            raise AssertionError("classifier must disable tool scrambling")
        return self._tools


class _FakeScenario:
    def __init__(self, starting_context: _FakeStartingContext) -> None:
        self.starting_context = starting_context


def _generic_service_fallback(classifier: Any) -> dict[str, Any]:
    from tool_sandbox.common.execution_context import RoleType

    request = "Find a restaurant nearby"
    scenario = _FakeScenario(
        _FakeStartingContext(
            (
                {
                    "sender": RoleType.USER,
                    "recipient": RoleType.AGENT,
                    "content": request,
                },
            ),
            ("search_location_around_lat_lon", "get_current_location"),
        )
    )
    context = classifier.visible_task_context_from_scenario(scenario)
    observations = classifier.classify_visible_task_observations(
        "synthetic_generic_service_fallback", scenario
    )
    return {
        "request": request,
        "signals": _typed(context.signals),
        "primary_family_key": context.primary_family_key,
        "canonical_keys": [item.canonical_key for item in observations],
        "observations": [
            _observation_summary(index, item) for index, item in enumerate(observations)
        ],
    }


def _trace_case(
    classifier: Any,
    scenarios: dict[str, Any],
    *,
    case_id: str,
    scenario_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    observations = classifier.classify_visible_trace_observations(
        scenario_name,
        scenarios[scenario_name],
        result,
    )
    return {
        "id": case_id,
        "scenario": scenario_name,
        "result": _typed(result),
        "canonical_keys": [item.canonical_key for item in observations],
        "observations": [
            _observation_summary(index, item) for index, item in enumerate(observations)
        ],
        "exact_observations": _digest(observations),
    }


def _trace_contracts(
    classifier: Any, scenarios: dict[str, Any]
) -> list[dict[str, Any]]:
    neutral = "wifi_off"
    reminder = "add_reminder_content_and_week_delta_and_time_and_location"
    precondition = "find_temperature_f_with_location_wifi_off"
    safe_abstain = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    return [
        _trace_case(
            classifier,
            scenarios,
            case_id="empty_result",
            scenario_name=neutral,
            result={},
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="malformed_trace_fields",
            scenario_name=neutral,
            result={
                "similarity": "not-a-number",
                "outcome_similarity": [],
                "messages": [None, 7, "not-a-message", {}],
                "agent_actions": ["not", "text"],
                "agent_result_summary": {"not": "text"},
                "observed_evidence": 3,
                "outcome": [],
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="next_weekday_temporal_failure",
            scenario_name=neutral,
            result={
                "similarity": 0.0,
                "messages": [
                    {
                        "role": "tool",
                        "recipient": "agent",
                        "content": "add_reminder failed for next Monday at 3 pm",
                    }
                ],
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="relative_day_temporal_failure_from_nested_outcome",
            scenario_name=neutral,
            result={
                "similarity": 1.0,
                "outcome_similarity": "0.5",
                "outcome": {
                    "agent_result_summary": (
                        "modify_reminder failed for tomorrow at 7:30 a.m."
                    )
                },
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="reminder_creation_suppresses_temporal_trace_birth",
            scenario_name=reminder,
            result={
                "similarity": 0,
                "agent_actions": "add_reminder failed for next Friday at 8 pm",
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="visible_precondition_failure",
            scenario_name=precondition,
            result={
                "similarity": 0,
                "observed_evidence": "ConnectionError: wifi is not enabled",
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="precondition_without_downstream_affordance",
            scenario_name=neutral,
            result={
                "similarity": 0,
                "messages": [
                    {
                        "role": "tool",
                        "content": "ConnectionError: wifi is not enabled",
                    }
                ],
            },
        ),
        _trace_case(
            classifier,
            scenarios,
            case_id="safe_abstention_task_suppresses_trace_birth",
            scenario_name=safe_abstain,
            result={
                "similarity": 0,
                "messages": [
                    {
                        "role": "tool",
                        "content": "ConnectionError: cellular service is not enabled",
                    }
                ],
            },
        ),
    ]


def build_classifier_corpus() -> dict[str, Any]:
    """Materialize the complete deterministic classifier behavior corpus."""

    from sage_ts.adequacy import inadequacy_classifier as classifier
    from tool_sandbox.cli.utils import resolve_scenarios
    from tool_sandbox.common.tool_discovery import ToolBackend

    random.seed(0)
    scenarios = resolve_scenarios(
        desired_scenario_names=None,
        preferred_tool_backend=ToolBackend.DEFAULT,
    )
    cases: list[dict[str, Any]] = []
    ordered_signals: list[Any] = []
    ordered_families: list[Any] = []
    ordered_observations: list[Any] = []
    expected_key_sequences: dict[tuple[Any, ...], dict[str, Any]] = {}
    scalar_expected_types: dict[str, dict[str, Any]] = {}
    factory_catalog: dict[str, dict[str, Any]] = {}
    duplicate_cases: list[dict[str, Any]] = []
    priority = (
        "relationship_batch_update",
        "named_message_recipient",
        "message_counterparty_lookup",
        "message_counterparty_update",
        "recency_action",
        "recency_search",
        "reminder_create",
        "add_contact",
        "direct_contact_action",
        "contact_lookup",
        "device_state_action",
        "device_status_read",
        "stock_lookup",
        "holiday",
        "service_answer_extraction",
        "external_lookup",
        "message",
        "contact",
        "reminder",
    )
    benchmark_collisions: list[dict[str, Any]] = []

    for index, (scenario_name, scenario) in enumerate(scenarios.items()):
        context = classifier.visible_task_context_from_scenario(scenario)
        observations = classifier.classify_visible_task_observations(
            scenario_name, scenario
        )
        summaries = [
            _observation_summary(emission_index, observation)
            for emission_index, observation in enumerate(observations)
        ]
        case = {
            "index": index,
            "scenario": scenario_name,
            "request": _digest(context.user_request),
            "available_tools": _digest(context.available_tools),
            "signals": list(context.signals),
            "signals_typed": _digest(context.signals),
            "primary_family_key": context.primary_family_key,
            "observations": summaries,
            "observation_sequence": _digest(observations),
        }
        cases.append(case)
        ordered_signals.append((scenario_name, context.signals))
        ordered_families.append((scenario_name, context.primary_family_key))
        ordered_observations.append((scenario_name, observations))

        canonical_keys = [item.canonical_key for item in observations]
        if len(canonical_keys) != len(set(canonical_keys)):
            duplicate_cases.append(
                {
                    "index": index,
                    "scenario": scenario_name,
                    "canonical_keys": canonical_keys,
                    "repeated_keys": [
                        key
                        for position, key in enumerate(canonical_keys)
                        if key in canonical_keys[:position]
                    ],
                    "observation_sequence": _digest(observations),
                }
            )

        priority_signals = [item for item in priority if item in context.signals]
        if len(priority_signals) > 1:
            benchmark_collisions.append(
                {
                    "index": index,
                    "scenario": scenario_name,
                    "priority_signals": priority_signals,
                    "selected": context.primary_family_key,
                }
            )

        for observation in observations:
            static_contract = _static_factory_contract(observation)
            static_digest = _digest(static_contract)
            entry = factory_catalog.setdefault(
                observation.canonical_key,
                {
                    "canonical_key": observation.canonical_key,
                    "first_scenario": scenario_name,
                    "prompt": _digest(observation.observation),
                    "validation_examples": _digest(observation.validation_examples),
                    "factory_product": static_digest,
                    "factory_product_variants": [],
                    "route_variants": [],
                    "emission_count": 0,
                },
            )
            entry["emission_count"] += 1
            if static_digest not in entry["factory_product_variants"]:
                entry["factory_product_variants"].append(static_digest)
            route = [observation.task_family_key, observation.reason]
            if route not in entry["route_variants"]:
                entry["route_variants"].append(route)

            for example_index, example in enumerate(observation.validation_examples):
                expected = example.expected
                if isinstance(expected, dict):
                    sequence = tuple(expected.keys())
                    sequence_entry = expected_key_sequences.setdefault(
                        sequence,
                        {
                            "typed_keys": _typed(sequence),
                            "keys": list(sequence),
                            "digest": _digest(sequence),
                            "first_scenario": scenario_name,
                            "first_canonical_key": observation.canonical_key,
                            "first_example_index": example_index,
                            "occurrence_count": 0,
                        },
                    )
                    sequence_entry["occurrence_count"] += 1
                else:
                    expected_type = type(expected).__name__
                    scalar_entry = scalar_expected_types.setdefault(
                        expected_type,
                        {
                            "python_type": expected_type,
                            "first_scenario": scenario_name,
                            "first_canonical_key": observation.canonical_key,
                            "occurrence_count": 0,
                        },
                    )
                    scalar_entry["occurrence_count"] += 1

    direct_priority_cases = (
        (
            "top_beats_all_later",
            priority,
        ),
        (
            "named_recipient_beats_counterparty_and_contact",
            ("contact", "message_counterparty_lookup", "named_message_recipient"),
        ),
        (
            "recency_action_beats_recency_search",
            ("recency_search", "recency_action", "reminder"),
        ),
        (
            "reminder_create_beats_contact",
            ("contact", "add_contact", "reminder_create"),
        ),
        (
            "stock_beats_generic_external",
            ("external_lookup", "stock_lookup"),
        ),
        (
            "service_extraction_beats_external",
            ("external_lookup", "service_answer_extraction"),
        ),
        (
            "unknown_signals_fall_back",
            ("unrecognized_one", "unrecognized_two"),
        ),
    )
    direct_collisions = [
        {
            "id": case_id,
            "signals": _typed(signals),
            "selected": classifier._visible_primary_family(signals),
        }
        for case_id, signals in direct_priority_cases
    ]

    terminal_name = "find_days_till_holiday_insufficient_information"
    nonterminal_name = "search_reminder_with_recency_upcoming_insufficient_information"

    def focused_task(name: str) -> dict[str, Any]:
        context = classifier.visible_task_context_from_scenario(scenarios[name])
        observations = classifier.classify_visible_task_observations(
            name, scenarios[name]
        )
        return {
            "scenario": name,
            "signals": list(context.signals),
            "canonical_keys": [item.canonical_key for item in observations],
            "exact_observations": _digest(observations),
        }

    duplicate_name = "modify_contact_with_message_recency_alt"
    body = {
        "schema_version": 1,
        "task_count": len(scenarios),
        "observation_count": sum(len(case["observations"]) for case in cases),
        "ordered_hashes": {
            "scenario_names": _digest(tuple(scenarios)),
            "signals": _digest(tuple(ordered_signals)),
            "primary_families": _digest(tuple(ordered_families)),
            "observations": _digest(tuple(ordered_observations)),
            "cases": _digest(tuple(cases)),
        },
        "cases": cases,
        "factory_catalog": list(factory_catalog.values()),
        "expected_result_key_sequences": list(expected_key_sequences.values()),
        "scalar_expected_types": list(scalar_expected_types.values()),
        "focused_contracts": {
            "fresh_materialization_mutation_isolation": _mutation_isolation(
                classifier,
                "add_reminder_content_and_week_delta_and_time_and_location",
                scenarios["add_reminder_content_and_week_delta_and_time_and_location"],
            ),
            "duplicate_emissions": duplicate_cases,
            "deliberate_duplicate_case": focused_task(duplicate_name),
            "benchmark_primary_family_collisions": benchmark_collisions,
            "direct_primary_family_collisions": direct_collisions,
            "terminal_insufficient_information": focused_task(terminal_name),
            "nonterminal_safe_abstention": focused_task(nonterminal_name),
            "trace_cases": _trace_contracts(classifier, scenarios),
            "generic_service_fallback": _generic_service_fallback(classifier),
        },
    }
    factory_refactor_guards = _factory_refactor_guards(classifier)
    corpus = dict(body)
    corpus["factory_refactor_guards"] = factory_refactor_guards
    corpus["integrity"] = {
        "body": _digest(body),
        "factory_refactor_guards": _digest(factory_refactor_guards),
    }
    return corpus


def _contract_projection(corpus: dict[str, Any]) -> dict[str, Any]:
    factory_refactor_guards = corpus["factory_refactor_guards"]
    return {
        "body": corpus["integrity"]["body"],
        "task_count": corpus["task_count"],
        "observation_count": corpus["observation_count"],
        "ordered_hashes": corpus["ordered_hashes"],
        "factory_count": len(corpus["factory_catalog"]),
        "expected_result_key_sequence_count": len(
            corpus["expected_result_key_sequences"]
        ),
        "scalar_expected_type_count": len(corpus["scalar_expected_types"]),
        "duplicate_case_count": len(corpus["focused_contracts"]["duplicate_emissions"]),
        "benchmark_collision_count": len(
            corpus["focused_contracts"]["benchmark_primary_family_collisions"]
        ),
        "factory_refactor_guards": corpus["integrity"]["factory_refactor_guards"],
        "direct_factory_count": len(factory_refactor_guards["factories"]),
        "direct_factory_example_count": sum(
            item["example_count"] for item in factory_refactor_guards["factories"]
        ),
        "location_non_alias_case_count": len(
            factory_refactor_guards["location_kwargs_non_alias"]
        ),
    }


def _verify_factory_refactor_guards(factory_refactor_guards: dict[str, Any]) -> None:
    actual_specs = [
        (item["group"], item["factory_name"])
        for item in factory_refactor_guards["factories"]
    ]
    if actual_specs != list(_FACTORY_REFACTOR_SPECS):
        raise ValueError("classifier direct-factory guard order or membership changed")
    for item in factory_refactor_guards["factories"]:
        expected_mutable_count = _EXPECTED_FACTORY_MUTABLE_COUNTS[item["factory_name"]]
        topology = item["within_product_mutable_topology"]
        if not (
            topology["mutable_container_count"] == expected_mutable_count
            and topology["mutable_container_occurrence_count"] == expected_mutable_count
            and topology["duplicate_mutable_identity_count"] == 0
            and topology["alias_groups"] == []
        ):
            raise ValueError(
                "classifier factory mutable identity topology changed: "
                f"{item['factory_name']} expected_count={expected_mutable_count} "
                f"actual={topology!r}"
            )
        freshness = item["freshness"]
        if not (
            freshness["first_mutation_changed_first"]
            and freshness["first_mutation_left_second_unchanged"]
            and freshness["fresh_third_matches_unmutated_second"]
            and freshness["first_second_shared_mutable_count"] == 0
            and freshness["second_third_shared_mutable_count"] == 0
        ):
            raise ValueError(
                f"classifier factory {item['factory_name']} reuses mutable data"
            )
        if len(item["examples"]) != item["example_count"]:
            raise ValueError(
                f"classifier factory {item['factory_name']} example shapes are incomplete"
            )
    for item in factory_refactor_guards["location_kwargs_non_alias"]:
        if not (
            item["same_object_before"] is False
            and item["shared_mutable_count_before"] == 0
            and item["search_mutation_changed_search"]
            and item["search_mutation_left_downstream_unchanged"]
        ):
            raise ValueError(
                "classifier location kwargs alias within one validation example: "
                f"{item['factory_name']}[{item['example_index']}]"
            )


def verify_classifier_corpus(corpus: dict[str, Any]) -> None:
    body = {
        key: value
        for key, value in corpus.items()
        if key not in {"factory_refactor_guards", "integrity"}
    }
    actual_integrity = _digest(body)
    if corpus.get("integrity", {}).get("body") != actual_integrity:
        raise ValueError("classifier corpus body digest does not match its contents")
    factory_refactor_guards = corpus.get("factory_refactor_guards")
    guard_integrity = _digest(factory_refactor_guards)
    if corpus.get("integrity", {}).get("factory_refactor_guards") != guard_integrity:
        raise ValueError(
            "classifier factory-refactor guard digest does not match its contents"
        )
    actual = _contract_projection(corpus)
    if not EXPECTED_CONTRACT:
        raise ValueError("classifier corpus expected contract has not been frozen")
    if actual != EXPECTED_CONTRACT:
        raise ValueError(
            "classifier corpus differs from its frozen reference contract: "
            f"expected={EXPECTED_CONTRACT!r}, actual={actual!r}"
        )

    _verify_factory_refactor_guards(factory_refactor_guards)

    focused = corpus["focused_contracts"]
    isolation = focused["fresh_materialization_mutation_isolation"]
    if not (
        isolation["first_mutation_changed_first"]
        and isolation["first_mutation_left_second_unchanged"]
        and isolation["fresh_third_matches_unmutated_second"]
        and isolation["first_second_shared_mutable_count"] == 0
        and isolation["second_third_shared_mutable_count"] == 0
    ):
        raise ValueError("classifier factories do not freshly materialize mutable data")
    if focused["deliberate_duplicate_case"]["canonical_keys"] != [
        "composite:plan_message_counterparty_search",
        "composite:select_message_counterparty_for_contact_update",
        "composite:plan_message_counterparty_search",
        "derived_value:prepare_message_recency_search_args",
        "search_filter:select_record_by_timestamp_extreme",
    ]:
        raise ValueError("deliberate duplicate emission order changed")
    if focused["terminal_insufficient_information"]["canonical_keys"] != [
        "validation:prepare_safe_action_or_abstain"
    ]:
        raise ValueError("terminal insufficient-information behavior changed")
    if focused["nonterminal_safe_abstention"]["canonical_keys"] != [
        "validation:prepare_safe_action_or_abstain",
        "derived_value:prepare_upcoming_reminder_search_args",
        "search_filter:select_record_by_timestamp_extreme",
    ]:
        raise ValueError("nonterminal safe-abstention behavior changed")
    generic_keys = focused["generic_service_fallback"]["canonical_keys"]
    if "derived_value:extract_service_answer_field" not in generic_keys:
        raise ValueError("generic external-service fallback is not emitted")
    trace_keys = {item["id"]: item["canonical_keys"] for item in focused["trace_cases"]}
    expected_trace_keys = {
        "empty_result": [],
        "malformed_trace_fields": [],
        "next_weekday_temporal_failure": [
            "canonicalizer:next_weekday_time_to_timestamp"
        ],
        "relative_day_temporal_failure_from_nested_outcome": [
            "canonicalizer:relative_day_time_timestamp"
        ],
        "reminder_creation_suppresses_temporal_trace_birth": [],
        "visible_precondition_failure": [
            "state_precondition:plan_device_state_action_sequence"
        ],
        "precondition_without_downstream_affordance": [],
        "safe_abstention_task_suppresses_trace_birth": [],
    }
    if trace_keys != expected_trace_keys:
        raise ValueError("visible-trace classifier edge behavior changed")
    collision_choices = {
        item["id"]: item["selected"]
        for item in focused["direct_primary_family_collisions"]
    }
    if collision_choices != {
        "top_beats_all_later": "relationship_batch_update",
        "named_recipient_beats_counterparty_and_contact": ("named_message_recipient"),
        "recency_action_beats_recency_search": "recency_action",
        "reminder_create_beats_contact": "reminder_create",
        "stock_beats_generic_external": "stock_lookup",
        "service_extraction_beats_external": "service_answer_extraction",
        "unknown_signals_fall_back": "general_visible_task",
    }:
        raise ValueError("primary-family collision precedence changed")


def probe_classifier_corpus(_root: Any) -> dict[str, Any]:
    corpus = build_classifier_corpus()
    verify_classifier_corpus(corpus)
    return corpus


def _tamper_self_test(corpus: dict[str, Any]) -> None:
    tampered = copy.deepcopy(corpus)
    tampered["cases"][0]["signals"].append("tampered_signal")
    try:
        verify_classifier_corpus(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("unhashed classifier corpus tamper was not rejected")

    forged = copy.deepcopy(tampered)
    forged_body = {
        key: value
        for key, value in forged.items()
        if key not in {"factory_refactor_guards", "integrity"}
    }
    forged["integrity"]["body"] = _digest(forged_body)
    try:
        verify_classifier_corpus(forged)
    except ValueError:
        pass
    else:
        raise AssertionError("rehashed classifier corpus tamper was not rejected")

    guard_tampered = copy.deepcopy(corpus)
    guard_tampered["factory_refactor_guards"]["factories"][0]["examples"][0][
        "input_shape"
    ]["type"] = "tampered"
    try:
        verify_classifier_corpus(guard_tampered)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "unhashed classifier factory guard tamper was not rejected"
        )

    guard_forged = copy.deepcopy(guard_tampered)
    guard_forged["integrity"]["factory_refactor_guards"] = _digest(
        guard_forged["factory_refactor_guards"]
    )
    try:
        verify_classifier_corpus(guard_forged)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "rehashed classifier factory guard tamper was not rejected"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-contract", action="store_true")
    parser.add_argument("--tamper-self-test", action="store_true")
    args = parser.parse_args()
    corpus = build_classifier_corpus()
    if args.print_contract:
        print(json.dumps(_contract_projection(corpus), indent=2))
        return 0
    verify_classifier_corpus(corpus)
    if args.tamper_self_test:
        _tamper_self_test(corpus)
    print(
        json.dumps(
            {
                "status": "verified",
                "contract": _contract_projection(corpus),
                "tamper_self_test": args.tamper_self_test,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
