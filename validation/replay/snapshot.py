#!/usr/bin/env python3
"""Collect a deterministic semantic snapshot from one repository checkout.

This file executes in a fresh ``python -I`` subprocess for every checkout. It
must not import SAGE or ToolSandbox until the selected checkout has been placed
at the front of ``sys.path``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import os
import random
import sys
import tempfile
import time
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


def probe_trajectory(_root: Path) -> dict[str, Any]:
    """Replay a content-hashed corpus from the frozen paper cohort.

    The historical fixture supplies captured model/tool boundary rows and exact
    state snapshots.  Each checkout supplies its own scenario definitions,
    visible-context parser, and outcome evaluator.  This therefore detects
    behavior drift without replaying model responses in a live evidence run.
    """

    import polars as pl
    from tool_sandbox.cli.utils import resolve_scenarios
    from tool_sandbox.common.execution_context import DatabaseNamespace
    from tool_sandbox.common.tool_discovery import ToolBackend

    # python -I deliberately excludes the script directory from sys.path. Load
    # this validation-only helper by exact path so neither checkout can shadow
    # it with production code.
    fixture_module_path = Path(__file__).resolve().parent / "trajectory_fixture.py"
    fixture_spec = importlib.util.spec_from_file_location(
        "sage_validation_trajectory_fixture",
        fixture_module_path,
    )
    if fixture_spec is None or fixture_spec.loader is None:
        raise RuntimeError(f"Cannot load trajectory fixture helper: {fixture_module_path}")
    fixture_module = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture_module)
    load_verified_fixture = fixture_module.load_verified_fixture

    classifier = importlib.import_module("sage_ts.adequacy.inadequacy_classifier")
    evaluator = importlib.import_module("sage_ts.evaluation.outcome_score")
    fixture, manifest = load_verified_fixture()
    cases = list(fixture["cases"])
    scenario_names = [str(case["scenario"]) for case in cases]
    fixed_timestamp = str(fixture["fixed_toolsandbox_timestamp"])
    previous_fixed_timestamp = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")
    try:
        os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = fixed_timestamp
        random.seed(0)
        scenarios = resolve_scenarios(
            desired_scenario_names=scenario_names,
            preferred_tool_backend=ToolBackend.DEFAULT,
        )

        case_results: dict[str, Any] = {}
        for case in cases:
            case_id = str(case["id"])
            scenario_name = str(case["scenario"])
            scenario = scenarios[scenario_name]
            context = copy.deepcopy(scenario.starting_context)
            sandbox_rows = [
                *fixture["shared"]["sandbox_prefix"],
                *case["sandbox_rows"],
            ]
            context._dbs[DatabaseNamespace.SANDBOX] = pl.DataFrame(
                sandbox_rows,
                schema=context.dbs_schemas[DatabaseNamespace.SANDBOX],
            )
            for namespace_name in (
                "SETTING",
                "CONTACT",
                "MESSAGING",
                "REMINDER",
            ):
                namespace = DatabaseNamespace[namespace_name]
                rows = [
                    *fixture["shared"]["initial_state"][namespace_name],
                    *case["state_rows"][namespace_name],
                ]
                context._dbs[namespace] = pl.DataFrame(
                    rows,
                    schema=context.dbs_schemas[namespace],
                )

            outcome = evaluator.compute_outcome_score(
                scenario,
                context,
                scenario_name=scenario_name,
            )
            historical = case["historical"]
            expected = {
                "outcome_similarity": historical["outcome_similarity"],
                "outcome_check_count": historical["outcome_check_count"],
                "outcome_state_history_safe": historical[
                    "outcome_state_history_safe"
                ],
            }
            observed = {
                "outcome_similarity": outcome.get("outcome_similarity"),
                "outcome_check_count": outcome.get("outcome_check_count"),
                "outcome_state_history_safe": outcome.get(
                    "outcome_state_history_safe"
                ),
            }
            if observed != expected:
                raise RuntimeError(
                    f"Historical trajectory no longer reproduces for {case_id}: "
                    f"{observed!r} != {expected!r}"
                )

            trace: list[dict[str, Any]] = []
            for row in case["sandbox_rows"]:
                for raw_trace in row.get("tool_trace") or []:
                    parsed = json.loads(raw_trace)
                    if not isinstance(parsed, dict):
                        raise ValueError(f"Non-object tool trace in {case_id}")
                    trace.append(parsed)
            visible = classifier.visible_task_context_from_scenario(scenario)
            state_hashes = {
                namespace_name: hashlib.sha256(
                    json.dumps(
                        context._dbs[DatabaseNamespace[namespace_name]].to_dicts(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                for namespace_name in (
                    "SETTING",
                    "CONTACT",
                    "MESSAGING",
                    "REMINDER",
                )
            }
            case_results[case_id] = _jsonable(
                {
                    "scenario": scenario_name,
                    "task_index_zero_based": case["task_index_zero_based"],
                    "coverage": case["coverage"],
                    "historical": historical,
                    "visible_context": {
                        "user_request": visible.user_request,
                        "available_tools": list(visible.available_tools),
                        "signals": list(visible.signals),
                        "primary_family_key": visible.primary_family_key,
                        "routing_text": visible.routing_text(),
                        "generation_label": visible.generation_label(),
                    },
                    "tool_trace": trace,
                    "final_state_sha256": state_hashes,
                    "outcome": outcome,
                }
            )
    finally:
        if previous_fixed_timestamp is None:
            os.environ.pop("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", None)
        else:
            os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = (
                previous_fixed_timestamp
            )

    return {
        "fixture": {
            "cohort_id": fixture["cohort_id"],
            "source_arm": fixture["source_arm"],
            "fixed_toolsandbox_timestamp": int(fixed_timestamp),
            "timezone": fixture["timezone"],
            "fixture_byte_count": manifest["fixture_byte_count"],
            "fixture_sha256": manifest["fixture_sha256"],
            "case_sha256": manifest["case_sha256"],
            "coverage": manifest["coverage"],
            "source_files_sha256": {
                path: details["sha256"]
                for path, details in manifest["source_files"].items()
            },
            "privacy": manifest["privacy"],
            "known_boundary_gap": manifest["known_boundary_gap"],
        },
        "birth_facts": fixture["birth_facts"],
        "cases": case_results,
    }


def probe_classifier(_root: Path) -> dict[str, Any]:
    """Snapshot visible-context and trace-derived birth observations."""

    classifier = importlib.import_module("sage_ts.adequacy.inadequacy_classifier")
    from tool_sandbox.cli.utils import resolve_scenarios
    from tool_sandbox.common.execution_context import RoleType
    from tool_sandbox.common.tool_discovery import ToolBackend

    # Freeze the entire ordered 1,032-task facts seam, not only the targeted
    # characterization cases below. These canonical bytes and digests were
    # independently measured by the pre-refactor seam analysis.
    random.seed(0)
    all_scenarios = resolve_scenarios(
        desired_scenario_names=None,
        preferred_tool_backend=ToolBackend.DEFAULT,
    )
    raw_task_facts: list[Any] = []
    full_visible_contexts: list[dict[str, Any]] = []
    for scenario_name, scenario in all_scenarios.items():
        context = classifier.visible_task_context_from_scenario(scenario)
        raw_task_facts.append(
            [scenario_name, context.user_request, list(context.available_tools)]
        )
        full_visible_contexts.append(
            {
                "scenario": scenario_name,
                "user_request": context.user_request,
                "available_tools": list(context.available_tools),
                "signals": list(context.signals),
                "primary_family_key": context.primary_family_key,
                "routing_text": context.routing_text(),
                "generation_label": context.generation_label(),
            }
        )

    def canonical_digest(value: Any) -> dict[str, Any]:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "byte_count": len(canonical),
            "sha256": hashlib.sha256(canonical).hexdigest(),
        }

    raw_digest = canonical_digest(raw_task_facts)
    full_digest = canonical_digest(full_visible_contexts)
    expected_raw = {
        "byte_count": 381344,
        "sha256": "9a1b7c21a7f91520b8b64771ee3fb99a6a50fae605b33a7a0e7259d1fd04bac8",
    }
    expected_full = {
        "byte_count": 1138325,
        "sha256": "e948d18d00746eb3e92b07cae0ea5c58c7c3415ec821f35216a8fb0de56339b5",
    }
    if raw_digest != expected_raw or full_digest != expected_full:
        raise RuntimeError(
            "Full benchmark visible-context seam drifted "
            f"(raw={raw_digest!r}, full={full_digest!r})"
        )

    class _FakeRows:
        def __init__(self, rows: tuple[dict[str, Any], ...]) -> None:
            self._rows = rows

        def iter_rows(self, *, named: bool) -> Any:
            if not named:
                raise AssertionError("visible context must request named rows")
            return iter(self._rows)

    class _FakeStartingContext:
        def __init__(
            self,
            *,
            rows: tuple[dict[str, Any], ...] = (),
            tools: tuple[Any, ...] = (),
            database_error: bool = False,
            tool_error: bool = False,
        ) -> None:
            self._rows = rows
            self._tools = tools
            self._database_error = database_error
            self._tool_error = tool_error

        def get_database(self, *_args: Any, **_kwargs: Any) -> _FakeRows:
            if self._database_error:
                raise RuntimeError("fixture database failure")
            return _FakeRows(self._rows)

        def get_available_tools(self, *, scrambling_allowed: bool) -> tuple[Any, ...]:
            if scrambling_allowed:
                raise AssertionError("visible context must disable scrambling")
            if self._tool_error:
                raise RuntimeError("fixture tool-discovery failure")
            return self._tools

    class _FakeScenario:
        def __init__(self, starting_context: _FakeStartingContext) -> None:
            self.starting_context = starting_context

    fake_cases = {
        "last_nonempty_user_to_agent_and_sorted_string_tools": _FakeScenario(
            _FakeStartingContext(
                rows=(
                    {
                        "sender": RoleType.USER,
                        "recipient": RoleType.AGENT,
                        "content": "Demonstration request",
                    },
                    {
                        "sender": RoleType.AGENT,
                        "recipient": RoleType.USER,
                        "content": "Wrong direction",
                    },
                    {
                        "sender": RoleType.USER,
                        "recipient": RoleType.EXECUTION_ENVIRONMENT,
                        "content": "Wrong recipient",
                    },
                    {
                        "sender": RoleType.USER,
                        "recipient": RoleType.AGENT,
                        "content": "   ",
                    },
                    {
                        "sender": RoleType.USER,
                        "recipient": RoleType.AGENT,
                        "content": 917,
                    },
                ),
                tools=("z_tool", 2, "a_tool"),
            )
        ),
        "database_failure_preserves_tool_discovery": _FakeScenario(
            _FakeStartingContext(
                tools=("z_tool", "a_tool"),
                database_error=True,
            )
        ),
        "tool_failure_preserves_database_request": _FakeScenario(
            _FakeStartingContext(
                rows=(
                    {
                        "sender": RoleType.USER,
                        "recipient": RoleType.AGENT,
                        "content": "Keep this request when discovery fails",
                    },
                ),
                tool_error=True,
            )
        ),
    }
    fake_results: dict[str, Any] = {}
    for case_id, fake_scenario in fake_cases.items():
        context = classifier.visible_task_context_from_scenario(fake_scenario)
        fake_results[case_id] = {
            "user_request": context.user_request,
            "available_tools": list(context.available_tools),
            "signals": list(context.signals),
            "primary_family_key": context.primary_family_key,
            "routing_text": context.routing_text(),
            "generation_label": context.generation_label(),
        }

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
        "full_benchmark_facts": {
            "task_count": len(all_scenarios),
            "canonical_serialization": (
                "json.dumps(value, ensure_ascii=False, separators=(',', ':'))"
            ),
            "raw_task_facts": raw_digest,
            "full_visible_contexts": full_digest,
            "first_scenario": next(iter(all_scenarios)),
            "last_scenario": next(reversed(all_scenarios)),
        },
        "fake_scenario_edge_cases": _jsonable(fake_results),
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


def _reporting_sanitize(value: Any, temporary_root: Path) -> Any:
    """Replace probe-local paths while retaining value and container order."""

    if isinstance(value, str):
        return value.replace(str(temporary_root), "<REPORTING_FIXTURE>")
    if isinstance(value, dict):
        return {
            key: _reporting_sanitize(item, temporary_root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_reporting_sanitize(item, temporary_root) for item in value]
    if isinstance(value, tuple):
        return tuple(_reporting_sanitize(item, temporary_root) for item in value)
    return value


def _reporting_key_order(value: Any, path: str = "") -> list[dict[str, Any]]:
    """Record insertion order for every nested JSON object."""

    orders: list[dict[str, Any]] = []
    if isinstance(value, dict):
        orders.append(
            {
                "path": path or "/",
                "keys": [str(key) for key in value],
            }
        )
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            orders.extend(_reporting_key_order(item, f"{path}/{escaped}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            orders.extend(_reporting_key_order(item, f"{path}/{index}"))
    return orders


def _reporting_value_snapshot(value: Any, temporary_root: Path) -> dict[str, Any]:
    sanitized = _reporting_sanitize(value, temporary_root)
    canonical = json.dumps(
        sanitized,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return {
        "value": _jsonable(sanitized),
        "object_key_order": _reporting_key_order(sanitized),
        "canonical_json": canonical,
        "canonical_json_byte_count": len(canonical.encode("utf-8")),
        "canonical_json_sha256": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
    }


def _capture_reporting_call(
    call: Callable[[], Any], temporary_root: Path
) -> dict[str, Any]:
    try:
        return {
            "status": "returned",
            "result": _reporting_value_snapshot(call(), temporary_root),
        }
    except Exception as exc:  # Validation must snapshot exact legacy failures.
        details: dict[str, Any] = {
            "status": "raised",
            "exception_module": type(exc).__module__,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "args": list(exc.args),
        }
        for name in ("lineno", "colno", "pos"):
            if hasattr(exc, name):
                details[name] = getattr(exc, name)
        return _jsonable(_reporting_sanitize(details, temporary_root))


def _write_reporting_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_reporting_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _materialize_reporting_run(
    run_dir: Path,
    *,
    rows: list[dict[str, Any]],
    artifacts: dict[str, Any] | None,
    started_at: str,
    updated_at: str,
    include_final: bool = True,
    live_rows: list[Any] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    if include_final:
        _write_reporting_json(
            run_dir / "result_summary.json",
            {"per_scenario_results": rows},
        )
    _write_reporting_json(
        run_dir / "live_result_summary.json",
        {
            "status": "complete" if include_final else "running",
            "scenario_count": str(len(rows)),
            "completed_count": len(rows),
            "updated_at": updated_at,
            "per_scenario_results": rows if live_rows is None else live_rows,
        },
    )
    _write_reporting_json(
        run_dir.parent / "sage_ts_run_manifest.json",
        {"started_at": started_at},
    )
    for name, payload in (artifacts or {}).items():
        path = run_dir / name
        if name.endswith(".jsonl"):
            if not isinstance(payload, list):
                raise ValueError(f"Reporting JSONL fixture is not a list: {name}")
            _write_reporting_jsonl(path, payload)
        else:
            _write_reporting_json(path, payload)


def probe_reporting(_root: Path) -> dict[str, Any]:
    """Freeze report values, serialization order, and artifact edge semantics."""

    fixture_module_path = Path(__file__).resolve().parent / "reporting_fixture.py"
    fixture_spec = importlib.util.spec_from_file_location(
        "sage_validation_reporting_fixture",
        fixture_module_path,
    )
    if fixture_spec is None or fixture_spec.loader is None:
        raise RuntimeError(f"Cannot load reporting fixture helper: {fixture_module_path}")
    fixture_module = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture_module)
    fixture, fixture_manifest = fixture_module.load_verified_fixture()

    run_metrics = importlib.import_module("sage_ts.evaluation.run_metrics")
    helper = importlib.import_module("sage_ts.evaluation.helper_contribution")
    campaign = importlib.import_module("sage_ts.campaign.artifacts")
    dashboard = importlib.import_module("sage_ts.dashboard.exporters")
    adapter = importlib.import_module("sage_ts.adapters.sage_run_adapter")
    protocol = importlib.import_module("scripts.run_sage_protocol")

    control_rows = copy.deepcopy(fixture["control_rows"])
    candidate_rows = copy.deepcopy(fixture["candidate_rows"])
    started_at = str(fixture["started_at"])
    updated_at = str(fixture["updated_at"])

    with tempfile.TemporaryDirectory(prefix="sage-reporting-replay-") as temporary:
        temporary_root = Path(temporary)
        control_dir = temporary_root / "primary" / "control" / "run"
        candidate_dir = temporary_root / "primary" / "candidate" / "run"
        registry_dir = temporary_root / "primary" / "registry"
        _materialize_reporting_run(
            control_dir,
            rows=control_rows,
            artifacts=copy.deepcopy(fixture["control_artifacts"]),
            started_at=started_at,
            updated_at=updated_at,
        )
        _materialize_reporting_run(
            candidate_dir,
            rows=candidate_rows,
            artifacts=copy.deepcopy(fixture["candidate_artifacts"]),
            started_at=started_at,
            updated_at=updated_at,
        )
        _write_reporting_json(
            registry_dir / "registry_manifest.json",
            copy.deepcopy(fixture["registry_manifest"]),
        )

        primary = {
            "summarize_control": _capture_reporting_call(
                lambda: run_metrics.summarize_run(control_dir), temporary_root
            ),
            "summarize_candidate": _capture_reporting_call(
                lambda: run_metrics.summarize_run(
                    candidate_dir,
                    registry_dir=registry_dir,
                ),
                temporary_root,
            ),
            "compare_complete": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    control_dir,
                    candidate_dir,
                    registry_dir=registry_dir,
                ),
                temporary_root,
            ),
            "helper_contribution": _capture_reporting_call(
                lambda: helper.build_helper_contribution_summary(
                    control_dir,
                    candidate_dir,
                    registry_dir=registry_dir,
                ),
                temporary_root,
            ),
        }

        helper_output = temporary_root / "primary" / "helper_contribution.json"

        def write_helper_summary() -> dict[str, Any]:
            result = helper.write_helper_contribution_summary(
                control_dir,
                candidate_dir,
                helper_output,
                registry_dir=registry_dir,
            )
            return {
                "returned": result,
                "serialized_text": helper_output.read_text(encoding="utf-8"),
                "round_trip": json.loads(helper_output.read_text(encoding="utf-8")),
            }

        primary["helper_contribution_writer"] = _capture_reporting_call(
            write_helper_summary,
            temporary_root,
        )

        atomic_output = temporary_root / "primary" / "atomic_ordered.json"

        def write_atomic_ordered_json() -> dict[str, Any]:
            protocol._atomic_write_json(
                atomic_output,
                {
                    "zeta": 1,
                    "alpha": {"second": 2, "first": 1},
                    "list": [{"right": True, "left": False}],
                },
            )
            raw = atomic_output.read_bytes()
            return {
                "raw_utf8": raw.decode("utf-8"),
                "byte_count": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "terminal_newline": raw.endswith(b"\n"),
                "temporary_siblings": sorted(
                    path.name
                    for path in atomic_output.parent.iterdir()
                    if path.name.startswith(f".{atomic_output.name}.")
                ),
            }

        primary["protocol_atomic_json_writer"] = _capture_reporting_call(
            write_atomic_ordered_json,
            temporary_root,
        )

        def variant_run(
            case_id: str,
            arm: str,
            rows: list[dict[str, Any]],
        ) -> Path:
            run_dir = temporary_root / "compare_cases" / case_id / arm / "run"
            _materialize_reporting_run(
                run_dir,
                rows=copy.deepcopy(rows),
                artifacts={},
                started_at=started_at,
                updated_at=updated_at,
            )
            return run_dir

        reordered_control = variant_run("reordered", "control", control_rows)
        reordered_candidate = variant_run(
            "reordered", "candidate", list(reversed(candidate_rows))
        )
        missing_control = variant_run("missing", "control", control_rows)
        missing_candidate = variant_run(
            "missing",
            "candidate",
            [row for row in candidate_rows if row["name"] not in {"beta_visible_not_called", "delta_runtime_failure"}],
        )
        duplicate_control_rows = [
            copy.deepcopy(control_rows[0]),
            {**copy.deepcopy(control_rows[0]), "similarity": 0.75},
        ]
        duplicate_candidate_rows = [
            copy.deepcopy(candidate_rows[0]),
            {**copy.deepcopy(candidate_rows[0]), "similarity": 0.5},
        ]
        duplicate_control = variant_run(
            "duplicate_aligned", "control", duplicate_control_rows
        )
        duplicate_candidate = variant_run(
            "duplicate_aligned", "candidate", duplicate_candidate_rows
        )
        bad_control = variant_run("bad_metric", "control", control_rows[:1])
        bad_candidate_rows = copy.deepcopy(candidate_rows[:1])
        bad_candidate_rows[0]["similarity"] = "not-a-float"
        bad_candidate = variant_run("bad_metric", "candidate", bad_candidate_rows)
        compare_edges = {
            "reordered_strict": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    reordered_control,
                    reordered_candidate,
                ),
                temporary_root,
            ),
            "reordered_partial_mode": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    reordered_control,
                    reordered_candidate,
                    require_complete_match=False,
                ),
                temporary_root,
            ),
            "missing_strict": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    missing_control,
                    missing_candidate,
                ),
                temporary_root,
            ),
            "missing_partial_mode": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    missing_control,
                    missing_candidate,
                    require_complete_match=False,
                ),
                temporary_root,
            ),
            "duplicate_aligned": _capture_reporting_call(
                lambda: run_metrics.compare_runs(
                    duplicate_control,
                    duplicate_candidate,
                ),
                temporary_root,
            ),
            "invalid_similarity_type": _capture_reporting_call(
                lambda: run_metrics.compare_runs(bad_control, bad_candidate),
                temporary_root,
            ),
        }

        reader_root = temporary_root / "reader_cases"
        reader_root.mkdir(parents=True)
        json_paths = {
            "missing": reader_root / "missing.json",
            "empty": reader_root / "empty.json",
            "whitespace": reader_root / "whitespace.json",
            "ordered_object": reader_root / "ordered_object.json",
            "array": reader_root / "array.json",
            "scalar": reader_root / "scalar.json",
            "malformed": reader_root / "malformed.json",
        }
        json_paths["empty"].write_text("", encoding="utf-8")
        json_paths["whitespace"].write_text(" \n\t", encoding="utf-8")
        json_paths["ordered_object"].write_text(
            '{"z":1,"a":{"second":2,"first":1}}\n', encoding="utf-8"
        )
        json_paths["array"].write_text('[{"b":2,"a":1},3]\n', encoding="utf-8")
        json_paths["scalar"].write_text('"scalar-value"\n', encoding="utf-8")
        json_paths["malformed"].write_text('{"broken":\n', encoding="utf-8")

        prior_sleep = run_metrics.time.sleep
        run_metrics.time.sleep = lambda _seconds: None
        try:
            json_readers: dict[str, Any] = {}
            for reader_name, reader in (
                ("run_metrics_strict_retry", run_metrics._read_json),
                ("campaign_strict", campaign.read_json),
                (
                    "dashboard_tolerant_object",
                    lambda path: dashboard._read_json(
                        path, {"fallback": "dashboard-object"}
                    ),
                ),
                (
                    "dashboard_tolerant_value",
                    lambda path: dashboard._read_json_value(
                        path, ["dashboard-value-fallback"]
                    ),
                ),
                ("protocol_strict", protocol._read_metrics),
            ):
                json_readers[reader_name] = {
                    case_id: _capture_reporting_call(
                        lambda path=path, reader=reader: reader(path),
                        temporary_root,
                    )
                    for case_id, path in json_paths.items()
                }
        finally:
            run_metrics.time.sleep = prior_sleep

        jsonl_paths = {
            "missing": reader_root / "missing.jsonl",
            "blank": reader_root / "blank.jsonl",
            "mixed_valid_types": reader_root / "mixed_valid_types.jsonl",
            "malformed_middle": reader_root / "malformed_middle.jsonl",
        }
        jsonl_paths["blank"].write_text("\n \n", encoding="utf-8")
        jsonl_paths["mixed_valid_types"].write_text(
            '{"z":1,"a":2}\n\n[1,2]\n"scalar"\n', encoding="utf-8"
        )
        jsonl_paths["malformed_middle"].write_text(
            '{"scenario":"alpha_gain","tool_name":"first"}\n'
            "not-json\n"
            '{"scenario":"alpha_gain","tool_name":"second"}\n',
            encoding="utf-8",
        )
        jsonl_readers: dict[str, Any] = {}
        for reader_name, reader in (
            ("run_metrics_strict", run_metrics._read_jsonl),
            ("campaign_strict", campaign.read_jsonl),
            ("dashboard_strict", dashboard._read_jsonl),
        ):
            jsonl_readers[reader_name] = {
                case_id: _capture_reporting_call(
                    lambda path=path, reader=reader: reader(path),
                    temporary_root,
                )
                for case_id, path in jsonl_paths.items()
            }

        tolerant_adapter_root = reader_root / "adapter_tolerant"
        tolerant_adapter_root.mkdir()
        (tolerant_adapter_root / "reuse_events.jsonl").write_text(
            jsonl_paths["malformed_middle"].read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (tolerant_adapter_root / "scenario_tool_selection.jsonl").write_text(
            '{"scenario":"alpha_gain","chosen":"first"}\n'
            "not-json\n"
            '["ignored-non-object"]\n'
            '{"scenario":"beta_visible_not_called","chosen":"second"}\n',
            encoding="utf-8",
        )
        jsonl_readers["adapter_tolerant"] = {
            "reuse_matching_and_deduplicated": _capture_reporting_call(
                lambda: adapter._reuse_log_tools(
                    tolerant_adapter_root, "alpha_gain"
                ),
                temporary_root,
            ),
            "reuse_missing_scenario": _capture_reporting_call(
                lambda: adapter._reuse_log_tools(tolerant_adapter_root, "absent"),
                temporary_root,
            ),
            "selection_skips_bad_and_non_object": _capture_reporting_call(
                lambda: adapter._selection_log_rows(tolerant_adapter_root),
                temporary_root,
            ),
        }

        arm_status_cases: dict[str, Any] = {}
        for case_id, raw in (
            ("missing", None),
            ("empty", ""),
            ("malformed", "not-json"),
            ("scalar", '"not-an-object"'),
            ("ordered_object", '{"status":"running","completed_count":2}'),
        ):
            case_root = reader_root / "arm_status" / case_id
            case_root.mkdir(parents=True)
            if raw is not None:
                (case_root / "control_arm_status.json").write_text(
                    raw, encoding="utf-8"
                )
            arm_status_cases[case_id] = _capture_reporting_call(
                lambda case_root=case_root: protocol._read_arm_status(
                    case_root, "control"
                ),
                temporary_root,
            )

        scenario_loading_root = temporary_root / "scenario_loading"
        final_preferred = scenario_loading_root / "final_preferred" / "run"
        _materialize_reporting_run(
            final_preferred,
            rows=control_rows[:2],
            artifacts={},
            started_at=started_at,
            updated_at=updated_at,
            live_rows=[candidate_rows[4]],
        )
        live_fallback = scenario_loading_root / "live_fallback" / "run"
        _materialize_reporting_run(
            live_fallback,
            rows=candidate_rows[:2],
            artifacts={},
            started_at=started_at,
            updated_at=updated_at,
            include_final=False,
        )
        no_summaries = scenario_loading_root / "no_summaries" / "run"
        no_summaries.mkdir(parents=True)
        scenario_loading = {
            "run_metrics_final_preferred": _capture_reporting_call(
                lambda: run_metrics._scenario_rows(final_preferred), temporary_root
            ),
            "run_metrics_live_fallback": _capture_reporting_call(
                lambda: run_metrics._scenario_rows(live_fallback), temporary_root
            ),
            "run_metrics_missing": _capture_reporting_call(
                lambda: run_metrics._scenario_rows(no_summaries), temporary_root
            ),
            "dashboard_final_preferred": _capture_reporting_call(
                lambda: dashboard._scenario_rows(final_preferred), temporary_root
            ),
            "dashboard_live_fallback": _capture_reporting_call(
                lambda: dashboard._scenario_rows(live_fallback), temporary_root
            ),
            "protocol_final_complete": _capture_reporting_call(
                lambda: protocol._run_result_rows(
                    final_preferred, require_complete=True
                ),
                temporary_root,
            ),
            "protocol_live_partial": _capture_reporting_call(
                lambda: protocol._run_result_rows(
                    live_fallback, require_complete=False
                ),
                temporary_root,
            ),
            "protocol_live_rejected_as_complete": _capture_reporting_call(
                lambda: protocol._run_result_rows(
                    live_fallback, require_complete=True
                ),
                temporary_root,
            ),
        }

        def uncached_case(
            case_id: str,
            rows: list[Any],
            *,
            expected: tuple[str, ...] = ("alpha_gain", "beta_visible_not_called"),
            require_complete: bool = True,
            include_final: bool = True,
            cache_artifact: str | None = None,
            payload_override: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            run_dir = temporary_root / "uncached_cases" / case_id / "run"
            _materialize_reporting_run(
                run_dir,
                rows=[row for row in rows if isinstance(row, dict)],
                artifacts={},
                started_at=started_at,
                updated_at=updated_at,
                include_final=include_final,
                live_rows=rows,
            )
            source = (
                run_dir / "result_summary.json"
                if include_final
                else run_dir / "live_result_summary.json"
            )
            if payload_override is not None:
                _write_reporting_json(source, payload_override)
            elif any(not isinstance(row, dict) for row in rows):
                _write_reporting_json(source, {"per_scenario_results": rows})
            if cache_artifact is not None:
                _write_reporting_json(run_dir / cache_artifact, {})
            return _capture_reporting_call(
                lambda: protocol._validate_uncached_result_rows(
                    run_dir,
                    expected_scenarios=expected,
                    arm="fixture",
                    require_complete=require_complete,
                ),
                temporary_root,
            )

        valid_alpha = copy.deepcopy(candidate_rows[0])
        valid_beta = copy.deepcopy(candidate_rows[1])
        uncached_validation = {
            "valid_reordered": uncached_case(
                "valid_reordered", [valid_beta, valid_alpha]
            ),
            "valid_partial": uncached_case(
                "valid_partial",
                [valid_alpha],
                require_complete=False,
            ),
            "missing_complete": uncached_case(
                "missing_complete", [valid_alpha]
            ),
            "duplicate_expected_names": uncached_case(
                "duplicate_expected_names",
                [valid_alpha],
                expected=("alpha_gain", "alpha_gain"),
            ),
            "duplicate_result_rows": uncached_case(
                "duplicate_result_rows", [valid_alpha, copy.deepcopy(valid_alpha)]
            ),
            "non_object_row_filtered": uncached_case(
                "non_object_row_filtered",
                [valid_alpha, "filtered-scalar"],
                expected=("alpha_gain",),
            ),
            "missing_task_name": uncached_case(
                "missing_task_name",
                [{**valid_alpha, "name": ""}],
                expected=("alpha_gain",),
            ),
            "unexpected_task_name": uncached_case(
                "unexpected_task_name",
                [{**valid_alpha, "name": "unexpected"}],
            ),
            "cached_source_marker": uncached_case(
                "cached_source_marker",
                [{**valid_alpha, "control_cache_source": "cached"}, valid_beta],
            ),
            "cached_detail_source": uncached_case(
                "cached_detail_source",
                [
                    {
                        **valid_alpha,
                        "control_cache": {"source": "cached", "record_ids": []},
                    },
                    valid_beta,
                ],
            ),
            "cached_detail_record_ids": uncached_case(
                "cached_detail_record_ids",
                [
                    {
                        **valid_alpha,
                        "control_cache": {"source": "fresh", "record_ids": ["r1"]},
                    },
                    valid_beta,
                ],
            ),
            "missing_replay_provenance": uncached_case(
                "missing_replay_provenance",
                [
                    {
                        key: value
                        for key, value in valid_alpha.items()
                        if key != "llm_cached_call_count"
                    },
                    valid_beta,
                ],
            ),
            "nonzero_replay_calls": uncached_case(
                "nonzero_replay_calls",
                [{**valid_alpha, "llm_cached_call_count": "2"}, valid_beta],
            ),
            "cache_artifact_present": uncached_case(
                "cache_artifact_present",
                [valid_alpha, valid_beta],
                cache_artifact="openai_response_cache_metrics.json",
            ),
            "complete_summary_missing": uncached_case(
                "complete_summary_missing",
                [valid_alpha, valid_beta],
                include_final=False,
            ),
            "scenario_rows_missing": uncached_case(
                "scenario_rows_missing",
                [],
                expected=(),
                payload_override={"status": "complete"},
            ),
        }

        strict_fresh_reports = {
            "valid": _capture_reporting_call(
                lambda: protocol._assert_strict_fresh_report(
                    {
                        "mode": "off",
                        "control_source": "fresh",
                        "cached_control_tasks": 0,
                        "fresh_control_tasks": "5",
                        "cache_accessed": False,
                    },
                    scenario_count=5,
                ),
                temporary_root,
            ),
            "wrong_mode": _capture_reporting_call(
                lambda: protocol._assert_strict_fresh_report(
                    {
                        "mode": "read",
                        "control_source": "fresh",
                        "cached_control_tasks": 0,
                        "fresh_control_tasks": 5,
                        "cache_accessed": False,
                    },
                    scenario_count=5,
                ),
                temporary_root,
            ),
            "cache_accessed_truthy": _capture_reporting_call(
                lambda: protocol._assert_strict_fresh_report(
                    {
                        "mode": "off",
                        "control_source": "fresh",
                        "cached_control_tasks": 0,
                        "fresh_control_tasks": 5,
                        "cache_accessed": 0,
                    },
                    scenario_count=5,
                ),
                temporary_root,
            ),
        }

        return {
            "fixture": {
                "fixture_id": fixture["fixture_id"],
                "fixture_byte_count": fixture_manifest["fixture_byte_count"],
                "fixture_sha256": fixture_manifest["fixture_sha256"],
                "canonical_payload_sha256": fixture_manifest[
                    "canonical_payload_sha256"
                ],
                "paired_scenario_count": fixture_manifest[
                    "paired_scenario_count"
                ],
                "coverage": fixture["coverage"],
                "provenance": fixture_manifest["provenance"],
            },
            "primary_outputs": primary,
            "compare_edge_cases": compare_edges,
            "json_reader_semantics": json_readers,
            "jsonl_reader_semantics": jsonl_readers,
            "arm_status_reader_semantics": arm_status_cases,
            "scenario_row_loading": scenario_loading,
            "uncached_result_validation": uncached_validation,
            "strict_fresh_report_validation": strict_fresh_reports,
        }


# Extension point: each deterministic probe receives the selected root and
# returns JSON-compatible data. Volatile timestamps/PIDs may be normalized only
# through the checked-in approved_nondeterminism.json allowlist.
PROBES: dict[str, Callable[[Path], dict[str, Any]]] = {
    "imports": probe_imports,
    "config": probe_config,
    "evaluator_manifest": probe_evaluator_manifest,
    "splits": probe_splits,
    "outcomes": probe_outcomes,
    "trajectory": probe_trajectory,
    "classifier": probe_classifier,
    "actor": probe_actor,
    "normalization": probe_normalization,
    "validation": probe_validation,
    "routing": probe_routing,
    "lifecycle": probe_lifecycle,
    "reporting": probe_reporting,
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
    if "trajectory" in selected:
        # ToolSandbox scenario factories cache time-derived starting state on
        # first resolution. Pin the historical clock before *any* selected-root
        # import/probe can resolve a scenario, not only inside probe_trajectory.
        fixture_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "full_trajectory_v1.json"
        )
        fixture_metadata = json.loads(fixture_path.read_text(encoding="utf-8"))
        os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = str(
            fixture_metadata["fixed_toolsandbox_timestamp"]
        )
        os.environ["TZ"] = str(fixture_metadata["timezone"])
        if hasattr(time, "tzset"):
            time.tzset()
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
