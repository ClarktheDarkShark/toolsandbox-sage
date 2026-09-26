#!/usr/bin/env python3
"""Collect a deterministic semantic snapshot from one repository checkout.

This file executes in a fresh ``python -I`` subprocess for every checkout. It
must not import SAGE or ToolSandbox until the selected checkout has been placed
at the front of ``sys.path``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import random
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from queue import Queue
from typing import Any, Callable


SNAPSHOT_SCHEMA_VERSION = 2

IMPORT_MODULES = (
    "sage_ts",
    "sage_ts.config.models",
    "sage_ts.config.splits",
    "sage_ts.evaluation.outcome_score",
    "sage_ts.adequacy.inadequacy_classifier",
    "sage_ts.generation.tool_generator",
    "sage_ts.orchestration.online_birth",
    "sage_ts.orchestration.self_evolution_reflection",
    "sage_ts.registry.store",
    "sage_ts.runtime.toolsandbox_integration",
    "sage_ts.validation.sandbox_validator",
    "sage_ts.adapters.role_factory",
    "sage_ts.dashboard.server",
    "scripts.run_sage_protocol",
)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted((_jsonable(item) for item in value), key=repr)
    return str(value)


def _relative_source(module: Any, root: Path) -> str:
    raw = getattr(module, "__file__", None)
    if not raw:
        return "<namespace-or-builtin>"
    path = Path(raw).resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"Module {module.__name__} resolved outside selected root: {path}"
        ) from exc


def probe_imports(root: Path) -> dict[str, Any]:
    modules: dict[str, Any] = {}
    for module_name in IMPORT_MODULES:
        module = importlib.import_module(module_name)
        modules[module_name] = {
            "source": _relative_source(module, root),
            "version": _jsonable(getattr(module, "__version__", None)),
        }
    return {"modules": modules}


def probe_config(_root: Path) -> dict[str, Any]:
    models = importlib.import_module("sage_ts.config.models")
    requested_models = (None, "", "gpt-4o-mini", "gpt-5-mini", "gpt-5", "unknown")
    prior_agent_effort = os.environ.pop("SAGE_GPT5_REASONING_EFFORT", None)
    prior_user_effort = os.environ.pop("SAGE_GPT5_USER_SIM_REASONING_EFFORT", None)
    try:
        default_effort = {
            str(model): {
                "agent": models.reasoning_effort_kwargs(model),
                "user": models.user_simulator_reasoning_effort_kwargs(model),
            }
            for model in requested_models
        }
        os.environ["SAGE_GPT5_REASONING_EFFORT"] = "high"
        os.environ["SAGE_GPT5_USER_SIM_REASONING_EFFORT"] = "low"
        explicit_effort = {
            str(model): {
                "agent": models.reasoning_effort_kwargs(model),
                "user": models.user_simulator_reasoning_effort_kwargs(model),
            }
            for model in requested_models
        }
    finally:
        if prior_agent_effort is None:
            os.environ.pop("SAGE_GPT5_REASONING_EFFORT", None)
        else:
            os.environ["SAGE_GPT5_REASONING_EFFORT"] = prior_agent_effort
        if prior_user_effort is None:
            os.environ.pop("SAGE_GPT5_USER_SIM_REASONING_EFFORT", None)
        else:
            os.environ["SAGE_GPT5_USER_SIM_REASONING_EFFORT"] = prior_user_effort
    return _jsonable(
        {
            "default_model": models.DEFAULT_MODEL,
            "model_metadata_table": models.MODEL_METADATA,
            "resolved_models": {
                str(model): models.resolve_model_name(model)
                for model in requested_models
            },
            "metadata": {
                str(model): models.model_metadata(model) for model in requested_models
            },
            "supports_temperature": {
                str(model): models.supports_temperature(model)
                for model in requested_models
            },
            "paired_metadata": models.paired_model_metadata(
                agent_model="gpt-4o-mini",
                generation_model="gpt-4o-mini",
                user_model="gpt-4o-mini",
            ),
            "default_reasoning_effort": default_effort,
            "explicit_reasoning_effort": explicit_effort,
        }
    )


def probe_evaluator_manifest(_root: Path) -> dict[str, Any]:
    evaluator = importlib.import_module("sage_ts.evaluation.outcome_score")
    return _jsonable(evaluator.outcome_evaluator_manifest())


def probe_splits(root: Path) -> dict[str, Any]:
    splits = importlib.import_module("sage_ts.config.splits")
    manifest_root = root / "docs" / "sage_protocol" / "manifests"
    manifests: dict[str, Any] = {}
    for path in sorted(manifest_root.glob("*.json")):
        raw = path.read_bytes()
        payload = json.loads(raw)
        split_payload = payload.get("splits", {})
        if not isinstance(split_payload, dict):
            raise ValueError(f"Manifest has non-object splits field: {path}")
        manifests[path.relative_to(root).as_posix()] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "splits": {
                name: splits.load_split_names(path, str(name))
                for name in sorted(split_payload)
            },
        }
    # ToolSandbox intentionally shuffles distraction-tool inventories when it
    # materializes scenarios. Seed that upstream behavior so two isolated
    # subprocesses describe the same published split rather than two random
    # presentation orders. The recorded order is still compared exactly.
    random.seed(0)
    records = [
        {
            "name": record.name,
            "categories": list(record.categories),
            "allowed_tools": list(record.allowed_tools),
        }
        for record in splits.scenario_records()
    ]
    return {
        "default_tool_backend": str(splits.DEFAULT_TOOL_BACKEND),
        "manifests": manifests,
        "scenario_records": records,
    }


def _resolve_scenarios(names: tuple[str, ...]) -> dict[str, Any]:
    """Resolve a stable ToolSandbox scenario subset for behavior probes."""

    from tool_sandbox.cli.utils import resolve_scenarios
    from tool_sandbox.common.tool_discovery import ToolBackend

    # Upstream distraction-tool materialization intentionally shuffles schemas.
    # Every isolated checkout receives the same seed, and any semantic difference
    # after that point remains visible in the snapshot.
    random.seed(0)
    return resolve_scenarios(
        desired_scenario_names=list(names),
        preferred_tool_backend=ToolBackend.DEFAULT,
    )


def _rollout_context(events: tuple[dict[str, Any], ...]) -> Any:
    """Build one deterministic execution context from model-boundary events."""

    from tool_sandbox.common.execution_context import (
        DatabaseNamespace,
        ExecutionContext,
        RoleType,
    )

    context = ExecutionContext()
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Publication benchmark request",
            }
        ],
    )
    for event in events:
        kind = str(event["kind"])
        if kind == "agent":
            row = {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": str(event["content"]),
            }
        elif kind == "user":
            row = {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": str(event["content"]),
            }
        elif kind == "tool":
            result = event.get("result")
            row = {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": json.dumps(result, sort_keys=True),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": str(event["tool_name"]),
                            "arguments": event.get("arguments", {}),
                            "result": result,
                        },
                        sort_keys=True,
                    )
                ],
            }
        else:
            raise ValueError(f"Unknown replay event kind: {kind}")
        context.add_to_database(DatabaseNamespace.SANDBOX, [row])
    return context


def probe_outcomes(_root: Path) -> dict[str, Any]:
    """Replay high-value answer/state contracts without an LLM or network."""

    evaluator = importlib.import_module("sage_ts.evaluation.outcome_score")
    cases: tuple[dict[str, Any], ...] = (
        {
            "id": "insufficient_targeted_clarification",
            "scenario": "find_current_city_insufficient_information",
            "events": ({"kind": "agent", "content": "Where are you?"},),
        },
        {
            "id": "insufficient_generic_refusal",
            "scenario": "find_current_city_insufficient_information",
            "events": ({"kind": "agent", "content": "I can't help with that."},),
        },
        {
            "id": "insufficient_later_correction",
            "scenario": "find_current_city_insufficient_information_3_distraction_tools",
            "events": (
                {"kind": "agent", "content": "Your current city is Boston."},
                {
                    "kind": "agent",
                    "content": (
                        "I can't determine your current city without your current "
                        "location or coordinates."
                    ),
                },
                {
                    "kind": "agent",
                    "content": "You're welcome—let me know if you need anything else!",
                },
            ),
        },
        {
            "id": "insufficient_later_contradiction",
            "scenario": "find_current_city_insufficient_information",
            "events": (
                {
                    "kind": "agent",
                    "content": "I can't determine your city without your current location.",
                },
                {"kind": "agent", "content": "Actually, your current city is Boston."},
            ),
        },
        {
            "id": "currency_exact_with_context",
            "scenario": "convert_currency",
            "events": (
                {"kind": "agent", "content": "The result is 13,988.46 CNY."},
            ),
        },
        {
            "id": "currency_later_wrong_correction",
            "scenario": "convert_currency",
            "events": (
                {"kind": "agent", "content": "The result is 13988.4544 CNY."},
                {
                    "kind": "agent",
                    "content": "Actually, correction: the result is 12000 CNY.",
                },
            ),
        },
        {
            "id": "thanksgiving_ignores_non_outcome_tail",
            "scenario": "find_thanksgiving_timestamp",
            "events": (
                {
                    "kind": "agent",
                    "content": "The Thanksgiving timestamp is 1795669200.",
                },
                {
                    "kind": "agent",
                    "content": (
                        "Thanksgiving is celebrated on the fourth Thursday of November. "
                        "If you would like a specific year's timestamp, please let me know."
                    ),
                },
            ),
        },
        {
            "id": "frozen_distance_corrected_target",
            "scenario": "find_distance_with_location_name",
            "events": (
                {
                    "kind": "agent",
                    "content": (
                        "You are approximately 67.98 kilometers away from "
                        "Golden Gate Bridge."
                    ),
                },
            ),
        },
        {
            "id": "frozen_distance_stale_target",
            "scenario": "find_distance_with_location_name",
            "events": (
                {
                    "kind": "agent",
                    "content": (
                        "You are approximately 67.86 kilometers away from "
                        "Golden Gate Bridge."
                    ),
                },
            ),
        },
        {
            "id": "fixture_temperature_fahrenheit",
            "scenario": "find_temperature_f_with_location_all_tools",
            "events": (
                {
                    "kind": "agent",
                    "content": (
                        "The temperature in the Grand Canyon is approximately 54.14°F."
                    ),
                },
            ),
        },
        {
            "id": "quoted_message_denial",
            "scenario": (
                "search_message_with_recency_latest_alt_3_distraction_tools_"
                "tool_description_scrambled"
            ),
            "events": (
                {
                    "kind": "agent",
                    "content": (
                        "There are no records of a message with the content "
                        "\"Good, keep me posted.\" in your text history."
                    ),
                },
            ),
        },
        {
            "id": "quoted_message_explicit_correction",
            "scenario": (
                "search_message_with_recency_latest_alt_3_distraction_tools_"
                "tool_description_scrambled"
            ),
            "events": (
                {
                    "kind": "agent",
                    "content": (
                        "There are no records saying \"Good, keep me posted\"—"
                        "correction: the latest message does say "
                        "\"Good, keep me posted\"."
                    ),
                },
            ),
        },
        {
            "id": "dynamic_days_with_grounded_clock",
            "scenario": "find_days_till_holiday_3_distraction_tools",
            "events": (
                {
                    "kind": "tool",
                    "tool_name": "get_current_timestamp",
                    "arguments": {},
                    "result": 1777597539.872639,
                },
                {
                    "kind": "agent",
                    "content": "There are 238 days until Christmas Day.",
                },
            ),
        },
    )
    scenario_names = tuple(dict.fromkeys(str(case["scenario"]) for case in cases))
    scenarios = _resolve_scenarios(scenario_names)
    snapshots: dict[str, Any] = {}
    for case in cases:
        scenario_name = str(case["scenario"])
        outcome = evaluator.compute_outcome_score(
            scenarios[scenario_name],
            _rollout_context(case["events"]),
            scenario_name=scenario_name,
        )
        snapshots[str(case["id"])] = {
            "scenario": scenario_name,
            "outcome": _jsonable(outcome),
        }
    return {"cases": snapshots}


def probe_classifier(_root: Path) -> dict[str, Any]:
    """Snapshot visible-context and trace-derived birth observations."""

    classifier = importlib.import_module("sage_ts.adequacy.inadequacy_classifier")
    names = (
        "find_current_city_insufficient_information",
        "add_reminder_content_and_week_delta_and_time_and_location",
        "update_contact_relationship_with_relationship",
        "search_message_with_recency_latest_alt_3_distraction_tools",
        "find_distance_with_location_name",
        "find_temperature_f_with_location_all_tools",
        "find_thanksgiving_timestamp",
        "search_phone_number_with_name",
        "add_contact_with_name_and_phone_number",
        "send_message_with_contact_content_cellular_off_insufficient_information",
        "wifi_off",
    )
    scenarios = _resolve_scenarios(names)
    results: dict[str, Any] = {}
    for name in names:
        scenario = scenarios[name]
        context = classifier.visible_task_context_from_scenario(scenario)
        observations = classifier.classify_visible_task_observations(name, scenario)
        results[name] = {
            "context": {
                "user_request": context.user_request,
                "available_tools": list(context.available_tools),
                "signals": list(context.signals),
                "primary_family_key": context.primary_family_key,
                "routing_text": context.routing_text(),
                "generation_label": context.generation_label(),
            },
            "observations": [item.to_json() for item in observations],
        }

    trace_name = "find_temperature_f_with_location_wifi_off"
    trace_scenario = _resolve_scenarios((trace_name,))[trace_name]
    trace_observations = classifier.classify_visible_trace_observations(
        trace_name,
        trace_scenario,
        {
            "similarity": 0.0,
            "outcome_similarity": 0.0,
            "messages": [
                {
                    "role": "tool",
                    "recipient": "agent",
                    "content": "ConnectionError: wifi is not enabled",
                }
            ],
        },
    )
    return {
        "visible_context_cases": _jsonable(results),
        "visible_trace_case": {
            "scenario": trace_name,
            "observations": [item.to_json() for item in trace_observations],
        },
    }


def _openai_tool(
    name: str,
    *,
    properties: dict[str, Any] | None = None,
    required: tuple[str, ...] = (),
    description: str = "Replay fixture tool.",
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
    }
    if required:
        parameters["required"] = list(required)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def probe_actor(_root: Path) -> dict[str, Any]:
    """Characterize prompt, schema filtering, ordering, and named selection."""

    actor = importlib.import_module("sage_ts.adapters.openai_toolsandbox_roles")
    string = {"type": "string"}
    number = {"type": "number"}
    integer = {"type": "integer"}
    mapping = {"type": "object"}
    records = {"type": "array", "items": {"type": "object"}}

    cases: tuple[dict[str, Any], ...] = (
        {
            "id": "relative_reminder_first_turn",
            "messages": [
                {"role": "system", "content": "You are a tool-use agent."},
                {
                    "role": "user",
                    "content": "Remind me tomorrow at 3 PM to call Dana.",
                },
            ],
            "tools": [
                _openai_tool("end_conversation"),
                _openai_tool("get_current_timestamp"),
                _openai_tool(
                    "timestamp_to_datetime_info",
                    properties={"timestamp": number},
                    required=("timestamp",),
                ),
                _openai_tool(
                    "relative_day_time_to_timestamp",
                    properties={
                        "current_datetime_info": mapping,
                        "day_offset": integer,
                        "hour": integer,
                        "minute": integer,
                    },
                    required=(
                        "current_datetime_info",
                        "day_offset",
                        "hour",
                        "minute",
                    ),
                    description=(
                        "Convert a visible relative day and local time after the "
                        "original datetime producer has supplied current_datetime_info."
                    ),
                ),
                _openai_tool(
                    "add_reminder",
                    properties={
                        "content": string,
                        "reminder_timestamp": number,
                    },
                    required=("content", "reminder_timestamp"),
                ),
            ],
        },
        {
            "id": "temperature_payload_handoff",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "What is the current temperature in the Grand Canyon "
                        "in Fahrenheit?"
                    ),
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-weather",
                            "type": "function",
                            "function": {
                                "name": "search_weather_around_lat_lon",
                                "arguments": json.dumps(
                                    {"latitude": 36.054, "longitude": -112.139}
                                ),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "search_weather_around_lat_lon",
                    "tool_call_id": "call-weather",
                    "content": repr(
                        {
                            "current_temperature": 15.1,
                            "temperature_unit": "Celsius",
                            "lat": 36.054,
                            "lon": -112.139,
                        }
                    ),
                },
            ],
            "tools": [
                _openai_tool(
                    "search_weather_around_lat_lon",
                    properties={"latitude": number, "longitude": number},
                    required=("latitude", "longitude"),
                ),
                _openai_tool(
                    "extract_temperature_result",
                    properties={
                        "service_payload": mapping,
                        "requested_unit": string,
                        "answer_subject": string,
                        "requested_metric": string,
                    },
                    required=(
                        "service_payload",
                        "requested_unit",
                        "answer_subject",
                        "requested_metric",
                    ),
                    description=(
                        "Extract a deterministic temperature answer. First call one "
                        "declared original producer: search_weather_around_lat_lon."
                    ),
                ),
                _openai_tool("end_conversation"),
            ],
        },
        {
            "id": "insufficient_contact_guard",
            "messages": [
                {
                    "role": "user",
                    "content": "Remove the contact with phone number +15550100.",
                }
            ],
            "tools": [
                _openai_tool(
                    "remove_contact",
                    properties={"person_id": string},
                    required=("person_id",),
                ),
                _openai_tool(
                    "prepare_safe_action_or_abstain",
                    properties={
                        "user_request": string,
                        "requested_action": string,
                        "target_identifier": string,
                        "required_original_tools": {"type": "array"},
                        "available_original_tools": {"type": "array"},
                        "visible_records_count": integer,
                    },
                    required=(
                        "user_request",
                        "requested_action",
                        "target_identifier",
                        "required_original_tools",
                        "available_original_tools",
                        "visible_records_count",
                    ),
                    description=(
                        "Decide whether visible information is sufficient or a "
                        "targeted clarification is required."
                    ),
                ),
                _openai_tool("end_conversation"),
            ],
        },
        {
            "id": "message_recency_result_handoff",
            "messages": [
                {
                    "role": "user",
                    "content": "What does my latest message say?",
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-search",
                            "type": "function",
                            "function": {
                                "name": "search_messages",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "search_messages",
                    "tool_call_id": "call-search",
                    "content": repr(
                        [
                            {"content": "older", "creation_timestamp": 10.0},
                            {"content": "newest", "creation_timestamp": 20.0},
                        ]
                    ),
                },
            ],
            "tools": [
                _openai_tool("search_messages"),
                _openai_tool(
                    "select_message_content_by_recency",
                    properties={
                        "records": records,
                        "timestamp_key": string,
                        "selection_mode": string,
                        "content_field": string,
                    },
                    required=(
                        "records",
                        "timestamp_key",
                        "selection_mode",
                        "content_field",
                    ),
                    description=(
                        "Select message content from visible records using oldest "
                        "or latest timestamp semantics."
                    ),
                ),
                _openai_tool(
                    "select_record_by_timestamp_extreme",
                    properties={
                        "records": records,
                        "timestamp_key": string,
                        "selection_mode": string,
                    },
                    required=("records", "timestamp_key", "selection_mode"),
                ),
                _openai_tool("end_conversation"),
            ],
        },
    )

    results: dict[str, Any] = {}
    for case in cases:
        messages = case["messages"]
        tools = case["tools"]
        prompted = actor._with_selector_actor_policy(messages, tools)
        completion_tool_free_turn = actor._helper_answer_completion_tool_free_turn(
            messages, tools
        )
        if completion_tool_free_turn:
            choices = {}
            retry_choice = None
            sent: Any = "<NOT_GIVEN>"
        else:
            # This order and the original-versus-prompted message choice mirror
            # ConfigurableOpenAIAgent.model_inference exactly.
            choices = {
                "helper_answer_completion_tool_choice": (
                    actor._helper_answer_completion_tool_choice(messages, tools)
                ),
                "device_status_completion_tool_choice": (
                    actor._device_status_completion_tool_choice(messages, tools)
                ),
                "shared_task_closure_tool_choice": (
                    actor._shared_task_closure_tool_choice(messages, tools)
                ),
                "generated_downstream_original_tool_choice": (
                    actor._generated_downstream_original_tool_choice(prompted, tools)
                ),
                "state_action_planner_tool_choice": (
                    actor._state_action_planner_tool_choice(prompted, tools)
                ),
                "reminder_recency_workflow_tool_choice": (
                    actor._reminder_recency_workflow_tool_choice(prompted, tools)
                ),
                "relationship_batch_generated_tool_choice": (
                    actor._relationship_batch_generated_tool_choice(prompted, tools)
                ),
                "reminder_location_batch_tool_choice": (
                    actor._reminder_location_batch_tool_choice(prompted, tools)
                ),
                "generated_tool_continuation_choice": (
                    actor._generated_tool_continuation_choice(prompted, tools)
                ),
                "new_user_turn_generated_tool_choice": (
                    actor._new_user_turn_generated_tool_choice(prompted, tools)
                ),
                "first_attempt_generated_tool_choice": (
                    actor._first_attempt_generated_tool_choice(prompted, tools)
                ),
            }
            retry_choice = next((value for value in choices.values() if value), None)
            filtered = actor._dynamic_generated_tool_schema_filter(
                prompted,
                tools,
                selected_tool_name=retry_choice,
            )
            sent = actor._hide_wrapped_native_action_schemas(
                filtered,
                routed_openai_tools=tools,
                selected_tool_name=retry_choice,
            )
        results[str(case["id"])] = {
            "original_messages": messages,
            "routed_tool_schemas": tools,
            "prompted_messages": prompted,
            "helper_answer_completion_tool_free_turn": completion_tool_free_turn,
            "selector_results_in_precedence_order": choices,
            "selected_named_tool_choice": retry_choice,
            "sent_tool_schemas": list(sent) if not isinstance(sent, str) else sent,
        }
    return _jsonable({"cases": results})


def _tool_spec(
    *,
    name: str,
    family: Any,
    inputs: tuple[Any, ...],
    output_annotation: str = "dict",
    output_properties: dict[str, Any] | None = None,
    positive_triggers: tuple[str, ...] = (),
    negative_triggers: tuple[str, ...] = (),
    preserves: tuple[str, ...] = (),
    required_calls: tuple[str, ...] = (),
    abstain_behavior: str = "",
) -> Any:
    from sage_ts.generation.tool_spec import StructuredInadequacyEvidence, ToolSpec

    output_schema = (
        {"type": "object", "properties": output_properties}
        if output_properties is not None
        else None
    )
    return ToolSpec(
        tool_name=name,
        family=family,
        description=(
            f"Deterministic replay characterization helper for {name}; it handles "
            "visible task inputs without hidden benchmark labels."
        ),
        inputs=inputs,
        output_annotation=output_annotation,
        output_schema=output_schema,
        positive_triggers=positive_triggers,
        negative_triggers=negative_triggers,
        preserves_side_effect_tools=preserves,
        required_original_tool_calls=required_calls,
        abstain_behavior=abstain_behavior,
        generalization_rationale=(
            "The same deterministic transformation recurs across multiple visible "
            "task variants and therefore merits a reusable helper."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "The visible inventory lacks a deterministic reusable operation for "
                f"the {name} capability across related tasks."
            ),
            signals=(positive_triggers[0] if positive_triggers else "replay_gap",),
        ),
    )


def probe_normalization(_root: Path) -> dict[str, Any]:
    """Snapshot contract-level output repair across core generated-tool families."""

    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.validation.output_normalization import (
        normalize_generated_tool_output,
    )

    state_tool = GeneratedTool(
        spec=_tool_spec(
            name="plan_device_state_action_sequence_v3",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            inputs=(
                ToolInput("target_service", "str", "Visible service target."),
                ToolInput("desired_on", "bool", "Visible desired state."),
                ToolInput("resume_original_task", "bool", "Resume after repair."),
            ),
            output_properties={
                "tool_name": {
                    "type": "string",
                    "enum": [
                        "",
                        "set_wifi_status",
                        "set_cellular_service_status",
                        "set_location_service_status",
                        "set_low_battery_mode_status",
                    ],
                },
                "arguments": {"type": "object"},
                "should_call": {"type": "boolean"},
                "reason": {"type": "string"},
                "action_sequence": {"type": "array"},
                "final_response_recommendation": {"type": "string"},
                "continue_original_task_after_sequence": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
            },
            negative_triggers=("unknown service",),
            preserves=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
                "set_low_battery_mode_status",
            ),
            required_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
                "set_low_battery_mode_status",
            ),
        ),
        code="def plan_device_state_action_sequence_v3(**kwargs):\n    return {}\n",
    )
    state_raw = {
        "tool_name": "set_low_battery_mode_status",
        "arguments": {"on": False},
        "should_call": True,
        "reason": "clear_low_battery_before_enabling_service",
        "action_sequence": [
            {
                "tool_name": "set_low_battery_mode_status",
                "arguments": {"on": False},
                "reason": "clear_low_battery_before_enabling_service",
            },
            {
                "tool_name": "set_cellular_service_status",
                "arguments": {"on": True},
                "reason": "set_cellular_on",
            },
        ],
        "final_response_recommendation": "Cellular has been turned on.",
        "continue_original_task_after_sequence": False,
        "abstain_reason": "",
    }

    selector_tool = GeneratedTool(
        spec=_tool_spec(
            name="select_visible_record_by_constraints",
            family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            inputs=(
                ToolInput("records", "list", "Visible candidate records."),
                ToolInput("field_name", "str", "Field to match."),
                ToolInput("expected_value", "str", "Value to match."),
            ),
            output_properties={
                "selected_record": {"type": "object"},
                "selected_index": {"type": "integer"},
                "selected_id": {"type": "string"},
                "value": {"type": "string"},
                "matched_constraints": {"type": "array"},
                "tie_candidates": {"type": "array"},
                "abstain_reason": {"type": "string"},
            },
            positive_triggers=("visible record constraint selection",),
            negative_triggers=("ambiguous multiple matches", "tie"),
            preserves=("search_contacts",),
            required_calls=("search_contacts",),
            abstain_behavior="Abstain on ties or ambiguous multiple matches.",
        ),
        code="def select_visible_record_by_constraints(**kwargs):\n    return {}\n",
    )
    selector_inputs = {
        "records": [
            {"person_id": "a", "relationship": "friend"},
            {"person_id": "b", "relationship": "friend"},
        ],
        "field_name": "relationship",
        "expected_value": "friend",
    }
    selector_raw = {
        "selected_record": {},
        "selected_index": 0,
        "selected_id": "a",
        "value": "a",
        "matched_constraints": ["relationship", "relationship"],
        "tie_candidates": [{"person_id": "b", "relationship": "friend"}],
        "abstain_reason": "ambiguous_multiple_matches",
    }

    derived_tool = GeneratedTool(
        spec=_tool_spec(
            name="extract_temperature_result",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            inputs=(
                ToolInput("service_payload", "dict", "Visible weather payload."),
                ToolInput("requested_metric", "str", "Requested metric."),
                ToolInput("requested_unit", "str", "Requested display unit."),
                ToolInput("answer_subject", "str", "Visible answer subject."),
            ),
            output_properties={
                "answer_value": {"type": "string"},
                "answer_kind": {"type": "string"},
                "answer_unit": {"type": "string"},
                "exact_final_answer": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "copy_exactly": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
            },
            positive_triggers=("service_answer_extraction",),
            preserves=("search_weather_around_lat_lon",),
            required_calls=("search_weather_around_lat_lon",),
        ),
        code="def extract_temperature_result(**kwargs):\n    return {}\n",
    )
    derived_raw = {
        "answer_value": "15.1",
        "answer_kind": "temperature",
        "answer_unit": "Celsius",
        "exact_final_answer": "",
        "final_answer_recommendation": "",
        "copy_exactly": False,
        "abstain_reason": "",
    }

    guard_tool = GeneratedTool(
        spec=_tool_spec(
            name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            inputs=(
                ToolInput("user_request", "str", "Visible user request."),
                ToolInput("requested_action", "str", "Requested action."),
                ToolInput("target_identifier", "str", "Visible target."),
                ToolInput("required_original_tools", "list", "Required tools."),
                ToolInput("available_original_tools", "list", "Available tools."),
                ToolInput("visible_records_count", "int", "Visible record count."),
            ),
            output_properties={
                "should_abstain": {"type": "boolean"},
                "missing_information": {"type": "array"},
                "required_original_tools": {"type": "array"},
                "forbidden_downstream_tools": {"type": "array"},
                "safe_next_action": {"type": "string"},
                "clarification_prompt": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
            },
            positive_triggers=("insufficient_information",),
            preserves=("search_contacts", "remove_contact"),
            required_calls=("search_contacts", "remove_contact"),
            abstain_behavior=(
                "Return a targeted clarification on missing information and never "
                "perform the downstream action."
            ),
        ),
        code="def prepare_safe_action_or_abstain(**kwargs):\n    return {}\n",
    )
    guard_raw = {
        "should_abstain": False,
        "missing_information": [],
        "required_original_tools": ["search_contacts", "remove_contact"],
        "forbidden_downstream_tools": [],
        "safe_next_action": "continue_with_original_tool",
        "clarification_prompt": "",
        "final_answer_recommendation": "",
        "abstain_reason": "",
    }
    guard_inputs = {
        "user_request": "Remove that contact.",
        "requested_action": "remove_contact",
        "target_identifier": "",
        "required_original_tools": ["search_contacts", "remove_contact"],
        "available_original_tools": ["remove_contact"],
        "visible_records_count": 0,
    }

    cases = {
        "state_sequence_control_fields": normalize_generated_tool_output(
            state_tool,
            state_raw,
            inputs={
                "target_service": "cellular",
                "desired_on": True,
                "resume_original_task": True,
            },
        ),
        "ambiguous_selector_abstention": normalize_generated_tool_output(
            selector_tool,
            selector_raw,
            inputs=selector_inputs,
        ),
        "derived_temperature_final_answer": normalize_generated_tool_output(
            derived_tool,
            derived_raw,
            inputs={
                "service_payload": {
                    "current_temperature": 15.1,
                    "temperature_unit": "Celsius",
                },
                "requested_metric": "current_temperature",
                "requested_unit": "Celsius",
                "answer_subject": "Grand Canyon",
            },
        ),
        "missing_contact_target_guard": normalize_generated_tool_output(
            guard_tool,
            guard_raw,
            inputs=guard_inputs,
        ),
    }
    return _jsonable({"cases": cases})


def probe_validation(_root: Path) -> dict[str, Any]:
    """Run deterministic compile, safety, held-out, and negative validation."""

    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

    canonical_spec = _tool_spec(
        name="canonicalize_connectivity_label",
        family=ToolFamily.CANONICALIZER,
        inputs=(ToolInput("label", "str", "Raw visible connectivity label."),),
        output_annotation="str",
        positive_triggers=("connectivity label normalization",),
    )
    safe_tool = GeneratedTool(
        spec=canonical_spec,
        code=(
            "def canonicalize_connectivity_label(label: str) -> str:\n"
            "    cleaned = label.strip().lower().replace('-', ' ').replace('_', ' ')\n"
            "    cleaned = ' '.join(cleaned.split())\n"
            "    if cleaned in {'wi fi', 'wifi', 'wireless'}:\n"
            "        return 'wifi'\n"
            "    if cleaned in {'cell', 'cellular', 'mobile data'}:\n"
            "        return 'cellular'\n"
            "    return cleaned\n"
        ),
    )
    canonical_examples = (
        ToolExample({"label": "Wi-Fi"}, "wifi"),
        ToolExample({"label": "mobile data"}, "cellular", held_out=True),
    )

    unsafe_tool = GeneratedTool(
        spec=canonical_spec,
        code=(
            "def canonicalize_connectivity_label(label: str) -> str:\n"
            "    return eval(label)\n"
        ),
    )

    selector_spec = _tool_spec(
        name="select_contact_by_constraint",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        inputs=(
            ToolInput("records", "list", "Visible candidate records."),
            ToolInput("field_name", "str", "Field to match."),
            ToolInput("expected_value", "str", "Expected field value."),
        ),
        output_properties={
            "selected_record": {"type": "object"},
            "selected_id": {"type": "string"},
            "value": {"type": "string"},
            "tie_candidates": {"type": "array"},
            "matched_constraints": {"type": "array"},
            "abstain_reason": {"type": "string"},
        },
        positive_triggers=("visible candidate selection",),
        negative_triggers=("no match", "ambiguous multiple matches", "tie"),
        preserves=("search_contacts",),
        required_calls=("search_contacts",),
        abstain_behavior="Abstain on no match, ties, or ambiguous multiple matches.",
    )
    selector_tool = GeneratedTool(
        spec=selector_spec,
        code=(
            "def select_contact_by_constraint(records: list, field_name: str, "
            "expected_value: str) -> dict:\n"
            "    target = expected_value.strip().lower()\n"
            "    matches = [record for record in records if "
            "str(record.get(field_name, '')).strip().lower() == target]\n"
            "    if len(matches) != 1:\n"
            "        reason = 'no_match' if not matches else 'ambiguous_multiple_matches'\n"
            "        return {'selected_record': {}, 'selected_id': '', 'value': '', "
            "'tie_candidates': matches, 'matched_constraints': [], "
            "'abstain_reason': reason}\n"
            "    record = matches[0]\n"
            "    selected_id = str(record.get('person_id', ''))\n"
            "    return {'selected_record': record, 'selected_id': selected_id, "
            "'value': selected_id, 'tie_candidates': [], "
            "'matched_constraints': [field_name], 'abstain_reason': ''}\n"
        ),
    )
    selector_examples = (
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "name": "Ada"},
                    {"person_id": "b", "name": "Grace"},
                ],
                "field_name": "name",
                "expected_value": "Grace",
            },
            {
                "selected_record": {"person_id": "b", "name": "Grace"},
                "selected_id": "b",
                "value": "b",
                "tie_candidates": [],
                "matched_constraints": ["name"],
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "records": [{"person_id": "a", "name": "Ada"}],
                "field_name": "name",
                "expected_value": "Ada",
            },
            {
                "selected_record": {"person_id": "a", "name": "Ada"},
                "selected_id": "a",
                "value": "a",
                "tie_candidates": [],
                "matched_constraints": ["name"],
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "records": [
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
                ],
                "field_name": "relationship",
                "expected_value": "friend",
            },
            {
                "selected_record": {},
                "selected_id": "",
                "value": "",
                "tie_candidates": [
                    {"person_id": "a", "relationship": "friend"},
                    {"person_id": "b", "relationship": "friend"},
                ],
                "matched_constraints": [],
                "abstain_reason": "ambiguous_multiple_matches",
            },
            negative_applicability=True,
        ),
    )

    results = {
        "safe_canonicalizer": asdict(
            validate_generated_tool(safe_tool, canonical_examples)
        ),
        "unsafe_eval_rejected": asdict(
            validate_generated_tool(unsafe_tool, canonical_examples)
        ),
        "selector_with_held_out_and_negative": asdict(
            validate_generated_tool(selector_tool, selector_examples)
        ),
    }
    return _jsonable({"results": results})


def _accepted_entry(tool: Any) -> Any:
    from sage_ts.registry.manifest import RegistryEntry, code_hash
    from sage_ts.validation.sandbox_validator import ValidationResult

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
        birth_scenario="replay_fixture",
        accepted_at="2026-01-01T00:00:00+00:00",
        stored_code_hash=code_hash(tool.code),
    )


def probe_routing(_root: Path) -> dict[str, Any]:
    """Snapshot bundle selection, schema order, and lifecycle suppression."""

    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.registry.manifest import has_current_validation_proof
    from sage_ts.runtime.toolsandbox_integration import route_registry_entries

    string = {"type": "string"}
    boolean = {"type": "boolean"}
    array = {"type": "array"}
    mapping = {"type": "object"}

    relative = GeneratedTool(
        spec=_tool_spec(
            name="relative_day_time_to_timestamp",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            inputs=(
                ToolInput("current_datetime_info", "dict", "Visible datetime info."),
                ToolInput("day_offset", "int", "Visible relative day offset."),
                ToolInput("hour", "int", "Visible hour."),
                ToolInput("minute", "int", "Visible minute."),
            ),
            output_annotation="float",
            positive_triggers=("relative_time",),
            preserves=("get_current_timestamp",),
            required_calls=("get_current_timestamp",),
        ),
        code="def relative_day_time_to_timestamp(**kwargs):\n    return 0.0\n",
    )
    weekday = GeneratedTool(
        spec=_tool_spec(
            name="next_weekday_time_to_timestamp",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            inputs=(
                ToolInput("current_datetime_info", "dict", "Visible datetime info."),
                ToolInput("weekday", "str", "Visible weekday."),
                ToolInput("hour", "int", "Visible hour."),
                ToolInput("minute", "int", "Visible minute."),
            ),
            output_annotation="float",
            positive_triggers=("weekday_time",),
            preserves=("get_current_timestamp",),
            required_calls=("get_current_timestamp",),
        ),
        code="def next_weekday_time_to_timestamp(**kwargs):\n    return 0.0\n",
    )
    temperature = GeneratedTool(
        spec=_tool_spec(
            name="extract_temperature_result",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            inputs=(
                ToolInput("service_payload", "dict", "Visible weather payload."),
                ToolInput("requested_unit", "str", "Visible requested unit."),
            ),
            output_properties={
                "answer_value": string,
                "answer_unit": string,
                "abstain_reason": string,
            },
            positive_triggers=("service_answer_extraction",),
            preserves=("search_weather_around_lat_lon",),
            required_calls=("search_weather_around_lat_lon",),
        ),
        code="def extract_temperature_result(**kwargs):\n    return {}\n",
    )
    safe_guard = GeneratedTool(
        spec=_tool_spec(
            name="prepare_safe_action_or_abstain",
            family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
            inputs=(
                ToolInput("user_request", "str", "Visible user request."),
                ToolInput("requested_action", "str", "Requested action."),
                ToolInput("target_identifier", "str", "Visible target."),
                ToolInput("required_original_tools", "list", "Required tools."),
                ToolInput("available_original_tools", "list", "Available tools."),
                ToolInput("visible_records_count", "int", "Visible record count."),
            ),
            output_properties={
                "should_abstain": boolean,
                "missing_information": array,
                "required_original_tools": array,
                "forbidden_downstream_tools": array,
                "safe_next_action": string,
                "clarification_prompt": string,
                "final_answer_recommendation": string,
                "abstain_reason": string,
            },
            positive_triggers=("insufficient_information", "safe_abstain_needed"),
            preserves=(
                "search_contacts",
                "remove_contact",
                "send_message_with_phone_number",
            ),
            required_calls=(
                "search_contacts",
                "remove_contact",
                "send_message_with_phone_number",
            ),
            abstain_behavior=(
                "Return a targeted clarification for insufficient_information or "
                "missing information without executing a side effect."
            ),
        ),
        code="def prepare_safe_action_or_abstain(**kwargs):\n    return {}\n",
    )

    def selector(name: str) -> Any:
        return GeneratedTool(
            spec=_tool_spec(
                name=name,
                family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
                inputs=(
                    ToolInput("records", "list", "Visible candidate records."),
                    ToolInput("selection_mode", "str", "Oldest or latest."),
                ),
                output_properties={
                    "selected_record": mapping,
                    "selected_id": string,
                    "value": string,
                    "tie_candidates": array,
                    "abstain_reason": string,
                },
                positive_triggers=("recency_search", "message_recency"),
                negative_triggers=("ambiguous multiple match", "tie"),
                preserves=("search_messages",),
                required_calls=("search_messages",),
                abstain_behavior="Abstain on a tie or ambiguous multiple match.",
            ),
            code=f"def {name}(**kwargs):\n    return {{}}\n",
        )

    state = GeneratedTool(
        spec=_tool_spec(
            name="plan_device_state_action_sequence_v3",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            inputs=(
                ToolInput("target_service", "str", "Visible target service."),
                ToolInput("desired_on", "bool", "Visible requested state."),
                ToolInput("next_action", "str", "Optional visible action hint."),
            ),
            output_properties={
                "tool_name": {
                    "type": "string",
                    "enum": [
                        "",
                        "set_wifi_status",
                        "set_cellular_service_status",
                        "set_location_service_status",
                        "set_low_battery_mode_status",
                    ],
                },
                "arguments": mapping,
                "should_call": boolean,
                "reason": string,
                "abstain_reason": string,
            },
            positive_triggers=("device_state_action", "state_precondition_possible"),
            negative_triggers=("unknown service",),
            preserves=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
                "set_low_battery_mode_status",
            ),
            required_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
                "set_low_battery_mode_status",
            ),
        ),
        code="def plan_device_state_action_sequence_v3(**kwargs):\n    return {}\n",
    )

    def location_helper(name: str, *, broad: bool) -> Any:
        inputs = [ToolInput("location_query", "str", "Visible location phrase.")]
        if broad:
            inputs.extend(
                [
                    ToolInput("latitude", "float", "Visible current latitude."),
                    ToolInput("longitude", "float", "Visible current longitude."),
                ]
            )
        return GeneratedTool(
            spec=_tool_spec(
                name=name,
                family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
                inputs=tuple(inputs),
                output_properties={
                    "search_location_kwargs": mapping,
                    "abstain_reason": string,
                },
                positive_triggers=("location_phrase", "external_lookup"),
                negative_triggers=("missing location",),
                preserves=("search_location_around_lat_lon",),
                required_calls=("search_location_around_lat_lon",),
                abstain_behavior="Abstain when the visible location phrase is missing.",
            ),
            code=f"def {name}(**kwargs):\n    return {{}}\n",
        )

    tools = (
        relative,
        weekday,
        temperature,
        safe_guard,
        selector("select_record_by_timestamp_extreme"),
        selector("select_message_content_by_recency"),
        state,
        location_helper("prepare_specific_location_search_args", broad=False),
        location_helper("prepare_broad_location_search_args", broad=True),
    )
    entries = {
        tool.spec.tool_name: _accepted_entry(tool)
        for tool in tools
    }
    proof = {
        name: has_current_validation_proof(entry)
        for name, entry in sorted(entries.items())
    }
    if not all(proof.values()):
        invalid = [name for name, current in proof.items() if not current]
        raise RuntimeError(f"Replay routing fixtures lack validation proof: {invalid}")

    cases: tuple[dict[str, Any], ...] = (
        {
            "id": "relative_reminder",
            "context": (
                "request=Remind me tomorrow at 3 PM to call Dana "
                "tools=get_current_timestamp add_reminder "
                "signals=reminder_create relative_time"
            ),
            "family": "reminder_create",
            "base_tools": {"get_current_timestamp", "add_reminder"},
            "lifecycle": None,
        },
        {
            "id": "weekday_reminder_precedence",
            "context": (
                "request=Remind me next Friday at 3 PM to call Dana "
                "tools=get_current_timestamp add_reminder "
                "signals=reminder_create relative_time weekday_time"
            ),
            "family": "reminder_create",
            "base_tools": {"get_current_timestamp", "add_reminder"},
            "lifecycle": None,
        },
        {
            "id": "temperature_service_answer",
            "context": (
                "request=What is the temperature in the Grand Canyon in Fahrenheit "
                "tools=search_weather_around_lat_lon "
                "signals=external_lookup location_phrase service_answer_extraction"
            ),
            "family": "service_answer_extraction",
            "base_tools": {"search_weather_around_lat_lon"},
            "lifecycle": None,
        },
        {
            "id": "message_recency_specific_selector",
            "context": (
                "request=What does my latest message say "
                "tools=search_messages "
                "signals=recency_search message_recency message_recency_search"
            ),
            "family": "message_recency",
            "base_tools": {"search_messages"},
            "lifecycle": None,
        },
        {
            "id": "remove_contact_no_lookup_guardrail",
            "context": (
                "request=Remove contact +15550100 "
                "tools=remove_contact "
                "signals=insufficient_information safe_abstain_needed"
            ),
            "family": "safe_abstain",
            "base_tools": {"remove_contact"},
            "lifecycle": None,
        },
        {
            "id": "named_send_missing_lookup_guard",
            "context": (
                "request=Send Dana a message saying hello "
                "tools=send_message_with_phone_number "
                "signals=insufficient_information named_message_recipient"
            ),
            "family": "safe_abstain",
            "base_tools": {"send_message_with_phone_number"},
            "lifecycle": None,
        },
        {
            "id": "direct_device_state_action",
            "context": (
                "request=Turn on wifi tools=set_wifi_status "
                "signals=device_state_action direct_device_state_action"
            ),
            "family": "device_state_action",
            "base_tools": {"set_wifi_status"},
            "lifecycle": None,
        },
        {
            "id": "specific_location_query",
            "context": (
                "request=Find weather at 1 Apple Park Way Cupertino "
                "tools=search_location_around_lat_lon "
                "signals=external_lookup location_phrase service_answer_extraction"
            ),
            "family": "location_phrase",
            "base_tools": {"search_location_around_lat_lon"},
            "lifecycle": None,
        },
        {
            "id": "broad_location_query",
            "context": (
                "request=Find weather in Boston "
                "tools=search_location_around_lat_lon "
                "signals=external_lookup location_phrase service_answer_extraction"
            ),
            "family": "location_phrase",
            "base_tools": {"search_location_around_lat_lon"},
            "lifecycle": None,
        },
        {
            "id": "parked_temperature_tool",
            "context": (
                "request=What is the temperature in Boston "
                "tools=search_weather_around_lat_lon "
                "signals=external_lookup location_phrase service_answer_extraction"
            ),
            "family": "service_answer_extraction",
            "base_tools": {"search_weather_around_lat_lon"},
            "lifecycle": {
                "extract_temperature_result": {"decision": "parked"}
            },
        },
        {
            "id": "clean_guard_overrides_coarse_route_repair",
            "context": (
                "request=Send Dana a message saying hello "
                "tools=send_message_with_phone_number "
                "signals=insufficient_information named_message_recipient"
            ),
            "family": "safe_abstain",
            "base_tools": {"send_message_with_phone_number"},
            "lifecycle": {
                "prepare_safe_action_or_abstain": {
                    "decision": "retain_with_route_repair",
                    "failed_count": 0,
                    "side_effect_incident_count": 0,
                    "route_repair_families": ["safe_abstain"],
                    "harmful_called_families": ["safe_abstain", "safe_abstain"],
                    "helpful_called_families": [],
                    "harmful_called_count": 2,
                }
            },
        },
    )
    results: dict[str, Any] = {}
    for case in cases:
        selected, decisions = route_registry_entries(
            entries,
            str(case["id"]),
            max_bundle_size=4,
            available_base_tools=set(case["base_tools"]),
            lifecycle_state=case["lifecycle"],
            task_context_text=str(case["context"]),
            task_family_key=str(case["family"]),
        )
        results[str(case["id"])] = {
            "selected_in_schema_order": [item.tool.spec.tool_name for item in selected],
            "decisions": {
                name: decision.to_json()
                for name, decision in sorted(decisions.items())
            },
        }
    return _jsonable({"validation_proof": proof, "cases": results})


def probe_lifecycle(_root: Path) -> dict[str, Any]:
    """Replay ordered feedback into retention, repair, and adoption decisions."""

    lifecycle = importlib.import_module(
        "sage_ts.orchestration.self_evolution_reflection"
    )
    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.registry.store import RegistryStore

    events: list[dict[str, Any]] = [
        {
            "scenario": "helpful_1",
            "family": "contact_lookup",
            "control": 0.0,
            "candidate": 1.0,
            "visible": ["helpful_tool"],
            "called": ["helpful_tool"],
        },
        {
            "scenario": "helpful_2",
            "family": "contact_lookup",
            "control": 0.0,
            "candidate": 1.0,
            "visible": ["helpful_tool"],
            "called": ["helpful_tool"],
        },
        {
            "scenario": "harmful_1",
            "family": "reminder_create",
            "control": 1.0,
            "candidate": 0.0,
            "visible": ["harmful_tool"],
            "called": ["harmful_tool"],
        },
        {
            "scenario": "mixed_helpful",
            "family": "location_phrase",
            "control": 0.0,
            "candidate": 1.0,
            "visible": ["mixed_tool"],
            "called": ["mixed_tool"],
        },
        {
            "scenario": "mixed_harmful",
            "family": "service_answer_extraction",
            "control": 1.0,
            "candidate": 0.0,
            "visible": ["mixed_tool"],
            "called": ["mixed_tool"],
        },
        {
            "scenario": "safety_audit",
            "family": "reminder_create",
            "control": 1.0,
            "candidate": 1.0,
            "visible": ["audited_tool"],
            "called": ["audited_tool"],
            "side_effect_failures": ["audited_tool"],
        },
    ]
    for index in range(8):
        events.append(
            {
                "scenario": f"adoption_{index + 1}",
                "family": "message_recency",
                "control": 1.0,
                "candidate": 1.0,
                "visible": ["unused_visible_tool"],
                "called": [],
            }
        )
    events.append(
        {
            "scenario": "runtime_exception",
            "family": "device_state_action",
            "control": 1.0,
            "candidate": 0.0,
            "visible": ["exception_tool"],
            "called": ["exception_tool"],
            "exception_type": "ReplayRuntimeError",
        }
    )

    channel: Queue = Queue()
    for event in events:
        channel.put(
            {
                "event": lifecycle.FRESH_CONTROL_ROW_EVENT,
                "scenario": event["scenario"],
                "row": {
                    "name": event["scenario"],
                    "similarity": event["control"],
                    "outcome_similarity": event["control"],
                    "online_feedback_outcome_similarity": event["control"],
                    "llm_cached_call_count": 0,
                },
            }
        )
    channel.put(
        {
            "event": lifecycle.FRESH_CONTROL_COMPLETE_EVENT,
            "scenario_count": len(events),
        }
    )

    with tempfile.TemporaryDirectory(prefix="sage-lifecycle-replay-") as temporary:
        temporary_root = Path(temporary)
        output_dir = temporary_root / "run"
        store = RegistryStore(temporary_root / "registry")
        tool_names = sorted(
            {
                str(tool_name)
                for event in events
                for tool_name in (*event["visible"], *event["called"])
            }
        )
        for tool_name in tool_names:
            registry_tool = GeneratedTool(
                spec=_tool_spec(
                    name=tool_name,
                    family=ToolFamily.CANONICALIZER,
                    inputs=(
                        ToolInput("value", "str", "Visible replay fixture value."),
                    ),
                    output_annotation="str",
                    positive_triggers=("replay lifecycle fixture",),
                ),
                code=f"def {tool_name}(value: str) -> str:\n    return value\n",
            )
            store.put(_accepted_entry(registry_tool))
        store.record_reuse("helpful_tool", success_flip=True)
        store.record_reuse("helpful_tool", success_flip=False)
        controller = lifecycle.SelfEvolutionReflectionController(
            store=store,
            output_dir=output_dir,
            fresh_control_channel=channel,
            pulse_interval=len(events),
            min_pulse_tasks=1,
        )
        for event in events:
            controller.assess_scenario(
                scenario_name=event["scenario"],
                result={
                    "similarity": event["candidate"],
                    "outcome_similarity": event["candidate"],
                    "online_feedback_outcome_similarity": event["candidate"],
                    "exception_type": event.get("exception_type"),
                },
                selection_record={
                    "generated_tools_visible": event["visible"],
                    "generated_tools_called": event["called"],
                    "generated_tools_attempted": event["called"],
                    "generated_tools_failed": (
                        event["called"] if event.get("exception_type") else []
                    ),
                },
                side_effect_failures=event.get("side_effect_failures", []),
                task_context_label=f"replay_context:{event['scenario']}",
                task_family_key=event["family"],
            )
        controller.assert_fresh_control_complete(
            tuple(str(event["scenario"]) for event in events)
        )

        def jsonl(name: str) -> list[dict[str, Any]]:
            path = output_dir / name
            if not path.exists():
                return []
            return [json.loads(line) for line in path.read_text().splitlines()]

        state = json.loads(
            (output_dir / "self_evolution_reflection_state.json").read_text(
                encoding="utf-8"
            )
        )
        registry_bytes = store.manifest_path.read_bytes()
        return _jsonable(
            {
                "final_state": state,
                "registry_manifest_sha256": hashlib.sha256(
                    registry_bytes
                ).hexdigest(),
                "registry_entries": {
                    name: entry.to_json()
                    for name, entry in sorted(store.load_entries().items())
                },
                "feedback_events": jsonl("self_evolution_task_feedback.jsonl"),
                "lifecycle_actions": jsonl("self_evolution_tool_lifecycle.jsonl"),
                "reflection_pulses": jsonl("self_evolution_reflections.jsonl"),
            }
        )


# Extension point: each deterministic probe receives the selected root and
# returns JSON-compatible data. Volatile timestamps/PIDs may be normalized only
# through the checked-in approved_nondeterminism.json allowlist.
PROBES: dict[str, Callable[[Path], dict[str, Any]]] = {
    "imports": probe_imports,
    "config": probe_config,
    "evaluator_manifest": probe_evaluator_manifest,
    "splits": probe_splits,
    "outcomes": probe_outcomes,
    "classifier": probe_classifier,
    "actor": probe_actor,
    "normalization": probe_normalization,
    "validation": probe_validation,
    "routing": probe_routing,
    "lifecycle": probe_lifecycle,
}


def _prepare_import_path(root: Path) -> None:
    required = (root / "pyproject.toml", root / "src" / "sage_ts")
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"Not a SAGE checkout; missing: {missing}")
    sys.dont_write_bytecode = True
    sys.path[:] = [str(root / "src"), str(root), *sys.path]
    os.chdir(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--probes",
        default=",".join(PROBES),
        help=f"Comma-separated probes ({', '.join(PROBES)})",
    )
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    selected = [item.strip() for item in args.probes.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(PROBES))
    if unknown:
        parser.error(f"unknown probes: {', '.join(unknown)}")
    _prepare_import_path(root)
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "probes": {name: PROBES[name](root) for name in selected},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
