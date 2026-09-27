"""Exact family-catalog contracts for behavior-preserving consolidation.

This validation-only probe freezes the duplicated registries that currently
connect generation, online birth, runtime routing, and actor policy.  It
records recursive Python container types and mapping insertion order rather
than relying on source hashes, so the implementation may move while its public
behavior remains unchanged.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import asdict
from typing import Any, Mapping


LOCATION_ARGUMENT_TOOL_NAMES = (
    "prepare_location_search_args",
    "prepare_specific_location_search_args",
    "prepare_broad_location_search_args",
)


def _typed(value: Any) -> dict[str, Any]:
    """Return a deterministic, recursively type-tagged representation."""

    if isinstance(value, re.Pattern):
        return {
            "python_type": type(value).__name__,
            "pattern": value.pattern,
            "flags_type": type(value.flags).__name__,
            "flags": int(value.flags),
        }
    if isinstance(value, Mapping):
        return {
            "python_type": type(value).__name__,
            "items": [
                {"key": _typed(key), "value": _typed(item)}
                for key, item in value.items()
            ],
        }
    if isinstance(value, (list, tuple)):
        return {
            "python_type": type(value).__name__,
            "items": [_typed(item) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        items = [_typed(item) for item in value]
        items.sort(
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
        )
        return {"python_type": type(value).__name__, "items": items}
    if value is None or isinstance(value, (bool, int, float, str)):
        return {"python_type": type(value).__name__, "value": value}
    return {
        "python_type": type(value).__name__,
        "value": str(value),
    }


def _lookup(mapping: Mapping[Any, Any], key: Any) -> dict[str, Any]:
    """Preserve the observable distinction between a missing and empty value."""

    if key not in mapping:
        return {"present": False}
    return {"present": True, "value": _typed(mapping[key])}


def _ordered_union(*iterables: Any) -> tuple[Any, ...]:
    return tuple(dict.fromkeys(item for values in iterables for item in values))


def _tool_schema(name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Replay schema for {name}.",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _accepted_entry(tool_name: str) -> Any:
    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolSpec
    from sage_ts.registry.manifest import RegistryEntry, code_hash
    from sage_ts.validation.sandbox_validator import ValidationResult

    code = f"def {tool_name}():\n    return {{}}\n"
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name=tool_name,
            family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            description=(
                "Replay-only general helper used to characterize visible routing."
            ),
            inputs=(),
            output_annotation="dict",
            positive_triggers=(),
            negative_triggers=(),
            applicable_task_families=(),
            generalization_rationale=(
                "The validation harness needs one accepted entry for each catalog key."
            ),
        ),
        code=code,
    )
    return RegistryEntry(
        tool=tool,
        validation=ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=2,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="family_catalog_replay",
        accepted_at="2026-01-01T00:00:00+00:00",
        stored_code_hash=code_hash(code),
    )


def _runtime_signal_contracts(runtime: Any) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for tool_name, signals in runtime.VISIBLE_CONTEXT_TOOL_SIGNALS.items():
        entry = _accepted_entry(tool_name)

        def decision(context: str) -> dict[str, Any]:
            value = runtime._visible_context_route_decision(
                entry,
                task_context_text=context,
                task_family_key=None,
            )
            return _typed(asdict(value))

        individual = []
        for signal in signals:
            context = f"request=ordinary visible task tools=replay signals={signal}"
            individual.append(
                {
                    "signal": _typed(signal),
                    "context": _typed(context),
                    "decision": decision(context),
                }
            )
        all_context = "request=ordinary visible task tools=replay signals=" + " ".join(
            signals
        )
        absent_context = (
            "request=ordinary visible task tools=replay signals=unrelated_signal"
        )
        results[tool_name] = {
            "declared_signals": _typed(signals),
            "individual_matches": individual,
            "all_context": _typed(all_context),
            "all_decision": decision(all_context),
            "absent_context": _typed(absent_context),
            "absent_decision": decision(absent_context),
        }
    return results


def _location_selection_contracts(actor: Any) -> dict[str, Any]:
    """Freeze the actor's behaviorally significant location-tool priority."""

    names = LOCATION_ARGUMENT_TOOL_NAMES
    cases: list[dict[str, Any]] = []
    for size in range(len(names) + 1):
        for present in itertools.combinations(names, size):
            for ordered in itertools.permutations(present):
                schemas = [_tool_schema(name) for name in ordered]
                cases.append(
                    {
                        "schema_order": _typed(ordered),
                        "selected": _typed(
                            actor._location_search_arg_tool_execution_name(schemas)
                        ),
                    }
                )
    return {
        "declared_name_order": _typed(names),
        "selection_cases": cases,
    }


def _regex_contract(pattern: re.Pattern[str]) -> dict[str, Any]:
    texts = (
        "latitude 37.33 longitude -122.03",
        "LATTITUDE: 37.33, LNG: -122.03",
        "longitude -122.03 then latitude 37.33",
        "latitude unknown longitude -122.03",
        "Whole Foods on Stevens Creek",
    )
    return {
        "definition": _typed(pattern),
        "search_cases": [
            {
                "text": _typed(text),
                "matched": _typed(pattern.search(text) is not None),
            }
            for text in texts
        ],
    }


def run_probe(_root: Any) -> dict[str, Any]:
    """Snapshot the duplicated family catalogs and their routing behavior."""

    from sage_ts.adapters import openai_toolsandbox_roles as actor
    from sage_ts.adequacy import inadequacy_classifier as classifier
    from sage_ts.generation import complete_tools, tool_generator
    from sage_ts.orchestration import online_birth
    from sage_ts.runtime import toolsandbox_integration as runtime

    generator_maps = {
        "default_families_by_tool": (
            tool_generator.MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL
        ),
        "default_original_calls_by_tool": (
            tool_generator.MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL
        ),
        "output_tool_name_enum_by_tool": (
            tool_generator.MODEL_AUTHORED_OUTPUT_TOOL_NAME_ENUM_BY_TOOL
        ),
    }
    catalog_tool_names = _ordered_union(
        *(mapping.keys() for mapping in generator_maps.values()),
        runtime.VISIBLE_CONTEXT_TOOL_SIGNALS.keys(),
    )
    per_tool_projection = [
        {
            "tool_name": _typed(tool_name),
            "default_families": _lookup(
                generator_maps["default_families_by_tool"], tool_name
            ),
            "default_original_calls": _lookup(
                generator_maps["default_original_calls_by_tool"], tool_name
            ),
            "output_tool_name_enum": _lookup(
                generator_maps["output_tool_name_enum_by_tool"], tool_name
            ),
            "runtime_visible_signals": _lookup(
                runtime.VISIBLE_CONTEXT_TOOL_SIGNALS, tool_name
            ),
        }
        for tool_name in catalog_tool_names
    ]

    location_name_set = frozenset(LOCATION_ARGUMENT_TOOL_NAMES)

    def location_key_order(mapping: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(key for key in mapping if key in location_name_set)

    return {
        "generator_maps": {
            name: _typed(mapping) for name, mapping in generator_maps.items()
        },
        "per_tool_projection_with_missing_values": per_tool_projection,
        "runtime_visible_context_signals": _typed(runtime.VISIBLE_CONTEXT_TOOL_SIGNALS),
        "runtime_signal_behavior": _runtime_signal_contracts(runtime),
        "online_visible_routing_families_by_key": _typed(
            online_birth.VISIBLE_ROUTING_FAMILIES_BY_KEY
        ),
        "native_and_actor_groups": {
            "complete_tools_native_names": _typed(
                complete_tools.COMPLETE_TOOLS_NATIVE_NAMES
            ),
            "actor_original_side_effect_tool_names": _typed(
                actor.ORIGINAL_SIDE_EFFECT_TOOL_NAMES
            ),
            "actor_generated_extraction_source_tool_names": _typed(
                actor.GENERATED_EXTRACTION_SOURCE_TOOL_NAMES
            ),
            "actor_service_answer_producer_tools": _typed(
                actor.SERVICE_ANSWER_PRODUCER_TOOLS
            ),
            "actor_service_answer_extractor_tools": _typed(
                actor.SERVICE_ANSWER_EXTRACTOR_TOOLS
            ),
            "actor_setting_setter_tool_names": _typed(actor.SETTING_SETTER_TOOL_NAMES),
            "runtime_setting_setter_tool_names": _typed(
                runtime.SETTING_SETTER_TOOL_NAMES
            ),
            "runtime_setting_state_labels": _typed(runtime.SETTING_STATE_LABELS),
        },
        "coordinate_regexes": {
            "classifier_visible_lat_lon_request": _regex_contract(
                classifier._VISIBLE_LAT_LON_REQUEST_RE
            ),
            "runtime_visible_lat_lon_request": _regex_contract(
                runtime._VISIBLE_LAT_LON_REQUEST_RE
            ),
        },
        "location_argument_name_orders": {
            "generator_default_family_keys": _typed(
                location_key_order(generator_maps["default_families_by_tool"])
            ),
            "generator_default_original_call_keys": _typed(
                location_key_order(generator_maps["default_original_calls_by_tool"])
            ),
            "runtime_visible_signal_keys": _typed(
                location_key_order(runtime.VISIBLE_CONTEXT_TOOL_SIGNALS)
            ),
            "online_visible_routing_keys": _typed(
                tuple(
                    key
                    for key in online_birth.VISIBLE_ROUTING_FAMILIES_BY_KEY
                    if key.removeprefix("composite:") in location_name_set
                )
            ),
            "actor_selection": _location_selection_contracts(actor),
        },
    }
