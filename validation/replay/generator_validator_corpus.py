"""Readable, deterministic generator/validator refactor corpus.

This module is external validation infrastructure.  It intentionally exercises
private seams because those seams define the behavior that Step 5 may consolidate.
No request reaches a model service and no fixture is imported by production SAGE.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from typing import Any, Callable, Iterable


# This is the complete union of the named generator profiles at reference commit
# 2518a2a.  Keep the names explicit: a reviewer should be able to audit coverage
# without reverse engineering a generated or minified fixture.
PROFILE_NAMES: tuple[str, ...] = (
    "days_between_timestamps",
    "extract_address_result",
    "extract_converted_amount_result",
    "extract_distance_result",
    "extract_phone_number_result",
    "extract_service_answer_field",
    "extract_stock_symbol",
    "extract_temperature_result",
    "next_weekday_time_to_timestamp",
    "plan_contact_lookup_query",
    "plan_contact_relationship_batch_update",
    "plan_contact_update_from_id",
    "plan_device_state_action_sequence_location_recovery",
    "plan_device_state_action_sequence_v3",
    "plan_device_status_lookup",
    "plan_message_counterparty_search",
    "plan_send_message_contact_lookup",
    "prepare_add_contact_args",
    "prepare_broad_location_search_args",
    "prepare_direct_contact_action_args",
    "prepare_holiday_search_args",
    "prepare_location_search_args",
    "prepare_message_recency_search_args",
    "prepare_past_reminder_recency_search_args",
    "prepare_reminder_creation_args",
    "prepare_safe_action_or_abstain",
    "prepare_specific_location_search_args",
    "prepare_upcoming_reminder_search_args",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_action_target_by_recency",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
    "select_record_by_timestamp_extreme",
)

# The generic state-action profile is intentionally outside the 34-name union.
# It is born from a canonical-key suffix and must retain the generic path.
GENERIC_PROFILE_NAME = "apply_single_device_state_action"
EXTRA_PROFILE_CASES: tuple[tuple[str, str | None], ...] = (
    ("generic_state_action", GENERIC_PROFILE_NAME),
    ("legacy_recency_bounds", "recency_to_timestamp_bounds"),
    ("legacy_next_service_call", "next_service_tool_call"),
    ("legacy_dependency_call", "next_dependency_precondition_call"),
    ("legacy_constraint_planner", "constraint_to_action_planner"),
    ("unknown_name", "unknown_reusable_profile"),
    ("none_name", None),
)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted((_jsonable(item) for item in value), key=repr)
    return str(value)


def _ordered_key_paths(value: Any, path: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        result.append({"path": path or "/", "keys": [str(key) for key in value]})
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            result.extend(_ordered_key_paths(item, f"{path}/{escaped}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            result.extend(_ordered_key_paths(item, f"{path}/{index}"))
    return result


def _exact(value: Any) -> dict[str, Any]:
    jsonable = _jsonable(value)
    raw = json.dumps(jsonable, ensure_ascii=False, separators=(",", ":"))
    return {
        "python_type": type(value).__name__,
        "value": jsonable,
        "object_key_order": _ordered_key_paths(value),
        "raw_json": raw,
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _text_digest(value: str) -> dict[str, Any]:
    encoded = value.encode("utf-8")
    return {
        "python_type": type(value).__name__,
        "byte_count": len(encoded),
        "line_count": len(value.splitlines()),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "prefix": value[:240],
        "suffix": value[-240:],
    }


def _capture(call: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"status": "returned", "result": _exact(call())}
    except Exception as error:  # noqa: BLE001 - exception behavior is the contract.
        return {
            "status": "raised",
            "exception_type": type(error).__name__,
            "message": str(error),
        }


def _assert_profile_coverage(names: Iterable[str]) -> None:
    actual = tuple(names)
    if actual != PROFILE_NAMES:
        missing = [name for name in PROFILE_NAMES if name not in actual]
        unexpected = [name for name in actual if name not in PROFILE_NAMES]
        duplicates = sorted({name for name in actual if actual.count(name) > 1})
        raise RuntimeError(
            "generator profile corpus changed: "
            f"missing={missing!r}, unexpected={unexpected!r}, "
            f"duplicates={duplicates!r}, order_matches={set(actual) == set(PROFILE_NAMES)}"
        )


def _minimal_spec_payload(tool_name: str) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "family": "canonicalizer",
        "description": "short",
        "inputs": [
            {"name": "value", "annotation": "str", "description": "Visible value."}
        ],
        "output_annotation": "str",
        "output_schema": None,
        "positive_triggers": [],
        "negative_triggers": [],
        "preserves_side_effect_tools": [],
        "required_original_tool_calls": [],
        "abstain_behavior": "",
        "generalization_rationale": "short",
        "estimated_step_compression": 1,
        "cross_task_applicability_count": 1,
        "applicable_task_families": ["canonicalizer"],
        "reason_tool_is_decisive": "short",
        "diagnostic_only": False,
        "shortfall_cluster_evidence": [],
        "known_failure_mechanisms_addressed": [],
        "inadequacy_evidence": {},
    }


def _response_for(tool_name: str) -> str:
    return json.dumps(
        {
            "spec": _minimal_spec_payload(tool_name),
            "code_lines": [
                f"def {tool_name}(value: str) -> str:",
                "    return value.strip()",
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


class _StaticCompleter:
    model = "generator-corpus-model"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[Any] = []

    def complete(self, request: Any) -> str:
        self.calls.append(request)
        if request.system.startswith("You analyze public"):
            return '{"analysis":"contract-analysis"}'
        if request.system.startswith("You trace rejected"):
            return '{"analysis":"repair-analysis"}'
        return self.response


def _profile_request(suggested_name: str | None) -> Any:
    from sage_ts.generation.tool_generator import ToolGenerationRequest
    from sage_ts.generation.tool_spec import ToolFamily

    return ToolGenerationRequest(
        scenario_name="Readable generator profile corpus",
        observation=(
            "Repeated visible inputs require one deterministic reusable capability "
            "that preserves original ToolSandbox operations."
        ),
        allowed_families=tuple(str(family) for family in ToolFamily),
        validation_examples=(),
        suggested_tool_name=suggested_name,
        inadequacy_evidence={
            "summary": "Visible failures recur across related public task families.",
            "signals": ["repeated_visible_failure", "reusable_transformation"],
            "failed_tool_calls": ["search_contacts"],
        },
        failure_memory_context={
            "failure_mechanism": "repeated_visible_failure",
            "unresolved_count": 2,
        },
        shortfall_cluster_context={
            "cluster_id": "generator-corpus",
            "failure_mechanism": "repeated_visible_failure",
            "non_diagnostic_birth_allowed": True,
        },
    )


def _chat_request_projection(request: Any) -> dict[str, Any]:
    payload = asdict(request)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "type": type(request).__name__,
        "field_order": list(payload),
        "system": _text_digest(request.system),
        "user": _text_digest(request.user),
        "model": request.model,
        "response_format_json": request.response_format_json,
        "raw_byte_count": len(raw.encode("utf-8")),
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _run_profile(case_id: str, suggested_name: str | None) -> dict[str, Any]:
    from sage_ts.generation.tool_generator import (
        ToolGenerator,
        _model_authored_contract_rules,
        _model_authored_generation_prompt,
        _model_authored_tool_specific_guidance,
        _request_complete_tools_enabled,
        _request_native_action_names,
    )

    request = _profile_request(suggested_name)
    emitted_name = suggested_name or "inferred_profile_tool"
    completer = _StaticCompleter(_response_for(emitted_name))
    generated = ToolGenerator(completer).generate(request)
    direct_prompt = _model_authored_generation_prompt(request)
    if len(completer.calls) != 1:
        raise RuntimeError(f"non-native profile {case_id} emitted extra model calls")
    if completer.calls[0].user != direct_prompt:
        raise RuntimeError(f"live and direct generation prompts differ for {case_id}")
    return {
        "case_id": case_id,
        "suggested_tool_name": suggested_name,
        "complete_tools_enabled": _request_complete_tools_enabled(request),
        "native_action_names": list(_request_native_action_names(request)),
        "contract_rules": _exact(_model_authored_contract_rules(request)),
        "tool_specific_guidance": _text_digest(
            _model_authored_tool_specific_guidance(request)
        ),
        "generation_prompt": _text_digest(direct_prompt),
        "chat_requests": [_chat_request_projection(item) for item in completer.calls],
        "normalized_generated_tool": _exact(generated.to_json()),
    }


def _legacy_name_mappings() -> dict[str, Any]:
    from sage_ts.orchestration.online_birth import suggested_tool_name

    cases = (
        ("empty", ""),
        ("empty_suffix", "derived_value:"),
        ("recency_legacy", "derived_value:recency_timestamp_bounds"),
        ("search_window_identity", "derived_value:resolve_search_window_or_bounds"),
        ("relative_day_legacy", "canonicalizer:relative_day_time_timestamp"),
        ("location_recovery_legacy", "state:location_service_recovery_sequence"),
        ("device_state_alias", "state:device_state_action_sequence"),
        ("device_state_plan_alias", "state:plan_device_state_action_sequence"),
        ("service_alias", "state:service_next_action"),
        ("service_identity", "state:next_service_tool_call"),
        ("dependency_legacy", "state:dependency_precondition_tool_call"),
        ("constraint_identity", "composite:constraint_to_action_planner"),
        ("direct_contact_identity", "composite:prepare_direct_contact_action_args"),
        ("generic_state_action", "state_precondition:apply_single_device_state_action"),
        ("unknown_fallthrough", "derived_value:unknown_visible_capability"),
        ("first_colon_only", "outer:inner:remaining"),
    )
    return {
        "cases": [
            {
                "case_id": case_id,
                "canonical_key": key,
                "result": suggested_tool_name(key),
            }
            for case_id, key in cases
        ]
    }


def _action_expected(
    action: str,
    arguments: dict[str, Any],
    *,
    shape: str = "downstream",
) -> dict[str, Any]:
    if shape == "tool_name":
        return {"tool_name": action, "arguments": arguments, "should_call": True}
    if shape == "named_kwargs":
        return {f"{action}_kwargs": arguments, f"should_call_{action}": True}
    if shape == "sequence":
        return {"action_sequence": [{"tool_name": action, "arguments": arguments}]}
    return {
        "downstream_tool_name": action,
        "downstream_tool_kwargs": arguments,
        "should_call_tool": True,
    }


def _eligibility_request(
    *,
    family: str = "composite_workflow_helper",
    positives: int = 2,
    held_out: int = 1,
    negatives: int = 1,
    input_count: int = 2,
    action_names: tuple[str, ...] = ("add_contact",),
    argument_count: int = 2,
    shape: str = "downstream",
    evidence_actions: tuple[str, ...] = (),
    multi_sequence: bool = False,
    kwargs_list: bool = False,
    empty_arguments: bool = False,
) -> Any:
    from sage_ts.generation.tool_generator import ToolGenerationRequest

    examples: list[dict[str, Any]] = []
    for index in range(positives):
        action = action_names[index % len(action_names)]
        inputs = {f"input_{item}": f"v{index}_{item}" for item in range(input_count)}
        arguments = {
            f"arg_{item}": f"v{index}_{item}" for item in range(argument_count)
        }
        if action == "add_contact" and argument_count == 2:
            arguments = {
                "name": f"Person {index}",
                "phone_number": f"+155500{index:02d}",
            }
        expected = _action_expected(
            action,
            {} if empty_arguments else arguments,
            shape=shape,
        )
        if multi_sequence:
            expected = {
                "action_sequence": [
                    {"tool_name": action, "arguments": arguments},
                    {"tool_name": action, "arguments": arguments},
                ]
            }
        if kwargs_list:
            expected["downstream_tool_kwargs_list"] = [arguments]
        examples.append(
            {
                "inputs": inputs,
                "expected": expected,
                "held_out": index >= max(0, positives - held_out),
            }
        )
    for index in range(negatives):
        examples.append(
            {
                "inputs": {f"input_{item}": "" for item in range(input_count)},
                "expected": {"should_call_tool": False},
                "negative_applicability": True,
            }
        )
    evidence: dict[str, Any] | None = None
    if evidence_actions:
        evidence = {
            "summary": "Repeated visible native action failure requires repair.",
            "signals": ["native_action_failure"],
            "failed_tool_calls": list(evidence_actions),
        }
    return ToolGenerationRequest(
        scenario_name="Native eligibility boundary",
        observation="Map public visible values to one approved native action.",
        allowed_families=(family,),
        validation_examples=tuple(examples),
        suggested_tool_name="eligibility_boundary_tool",
        inadequacy_evidence=evidence,
    )


def _native_eligibility_matrix() -> dict[str, Any]:
    from sage_ts.generation.tool_generator import (
        _request_complete_tools_enabled,
        _request_native_action_names,
    )

    base = _eligibility_request()
    cases: list[tuple[str, Any]] = [
        ("compact_minimum", base),
        (
            "ineligible_family",
            _eligibility_request(family="canonicalizer"),
        ),
        ("no_positive", _eligibility_request(positives=0)),
        ("no_held_out", _eligibility_request(held_out=0)),
        ("no_negative", _eligibility_request(negatives=0)),
        ("multi_action_sequence", _eligibility_request(multi_sequence=True)),
        ("nonempty_kwargs_list", _eligibility_request(kwargs_list=True)),
        ("empty_action_arguments", _eligibility_request(empty_arguments=True)),
        ("positive_limit_8", _eligibility_request(positives=8, held_out=2)),
        ("positive_limit_9", _eligibility_request(positives=9, held_out=2)),
        (
            "seven_inputs_sparse",
            _eligibility_request(input_count=7, positives=3, held_out=1, negatives=2),
        ),
        (
            "seven_inputs_dense",
            _eligibility_request(input_count=7, positives=4, held_out=2, negatives=2),
        ),
        (
            "sixteen_inputs_dense",
            _eligibility_request(input_count=16, positives=4, held_out=2, negatives=2),
        ),
        (
            "seventeen_inputs_dense",
            _eligibility_request(input_count=17, positives=4, held_out=2, negatives=2),
        ),
        (
            "four_actions",
            _eligibility_request(
                positives=4,
                held_out=2,
                negatives=2,
                action_names=(
                    "add_contact",
                    "remove_contact",
                    "add_reminder",
                    "remove_reminder",
                ),
            ),
        ),
        (
            "five_actions",
            _eligibility_request(
                positives=5,
                held_out=2,
                negatives=2,
                action_names=(
                    "add_contact",
                    "remove_contact",
                    "add_reminder",
                    "remove_reminder",
                    "set_wifi_status",
                ),
            ),
        ),
        ("four_arguments", _eligibility_request(argument_count=4)),
        ("five_arguments", _eligibility_request(argument_count=5)),
        (
            "evidence_name_mismatch",
            _eligibility_request(evidence_actions=("remove_contact",)),
        ),
        ("tool_name_shape", _eligibility_request(shape="tool_name")),
        ("named_kwargs_shape", _eligibility_request(shape="named_kwargs")),
        ("single_sequence_shape", _eligibility_request(shape="sequence")),
    ]
    return {
        "case_order": [case_id for case_id, _request in cases],
        "rows": [
            {
                "case_id": case_id,
                "enabled": _request_complete_tools_enabled(request),
                "native_action_names": list(_request_native_action_names(request)),
                "validation_example_count": len(request.validation_examples),
            }
            for case_id, request in cases
        ],
    }


def _native_repair_request() -> Any:
    from sage_ts.generation.tool_generator import ToolGenerationRequest

    examples = (
        {
            "inputs": {"name": "Dana", "phone_number": "+15550100"},
            "expected": _action_expected(
                "add_contact", {"name": "Dana", "phone_number": "+15550100"}
            ),
        },
        {
            "inputs": {"name": "Lee", "phone_number": "+15550200"},
            "expected": _action_expected(
                "add_contact", {"name": "Lee", "phone_number": "+15550200"}
            ),
            "held_out": True,
        },
        {
            "inputs": {"name": "", "phone_number": ""},
            "expected": {"should_call_tool": False},
            "negative_applicability": True,
        },
    )
    return ToolGenerationRequest(
        scenario_name="Native repair strategy corpus",
        observation=(
            "Add one visible contact when both fields are present and safely abstain "
            "when either field is absent."
        ),
        allowed_families=("composite_workflow_helper",),
        validation_examples=examples,
        suggested_tool_name="prepare_add_contact_args",
        inadequacy_evidence={
            "summary": "Repeated visible add-contact requests need one safe action.",
            "signals": ["add_contact_failure"],
            "failed_tool_calls": ["add_contact"],
        },
    )


def _native_response() -> str:
    name = "prepare_add_contact_args"
    spec = _minimal_spec_payload(name)
    spec.update(
        {
            "family": "composite_workflow_helper",
            "inputs": [
                {"name": "name", "annotation": "str", "description": "Visible name."},
                {
                    "name": "phone_number",
                    "annotation": "str",
                    "description": "Visible phone number.",
                },
            ],
            "output_annotation": "dict",
            "output_schema": {"type": "object", "properties": {}},
            "negative_triggers": ["missing contact fields"],
            "preserves_side_effect_tools": ["add_contact"],
            "required_original_tool_calls": ["add_contact"],
        }
    )
    return json.dumps(
        {
            "spec": spec,
            "code_lines": [
                f"def {name}(name: str, phone_number: str) -> dict:",
                "    if not name.strip() or not phone_number.strip():",
                "        return {'status': 'abstain', 'confirmation': '', 'abstain_reason': 'missing contact fields', 'native_action': '', 'native_result': None}",
                "    native_result = add_contact(name=name, phone_number=phone_number)",
                "    return {'status': 'success', 'confirmation': name + ' added', 'abstain_reason': '', 'native_action': 'add_contact', 'native_result': native_result}",
            ],
        },
        separators=(",", ":"),
    )


def _repair_and_cache_corpus() -> dict[str, Any]:
    from sage_ts.generation.tool_generator import (
        ToolGenerator,
        _model_authored_contract_analysis_prompt,
        _model_authored_final_repair_directive,
        _model_authored_generation_prompt,
        _model_authored_repair_analysis_prompt,
        _model_authored_repair_prompt,
        _request_complete_tools_enabled,
    )

    request = _native_repair_request()
    if not _request_complete_tools_enabled(request):
        raise RuntimeError(
            "native repair fixture no longer reaches complete-tools mode"
        )
    completer = _StaticCompleter(_native_response())
    generator = ToolGenerator(completer)
    generated = generator.generate(request)
    generator.generate(request)

    strategy_rows: list[dict[str, Any]] = []
    for strategy in range(1, 8):
        errors = (
            "source_0_native_action_count:0!=1:expected=add_contact:{'name': 'Dana', 'phone_number': '+15550100'}",
            f"repair_strategy:{strategy}",
        )
        direct_repair = _model_authored_repair_prompt(request, generated, errors)
        analysis = _model_authored_repair_analysis_prompt(request, generated, errors)
        final = _model_authored_final_repair_directive(request, errors)
        first = generator.repair_candidates(request, generated, errors)
        repeated = generator.repair_candidates(request, generated, errors)
        strategy_rows.append(
            {
                "strategy": strategy,
                "repair_prompt": _text_digest(direct_repair),
                "repair_analysis_prompt": _text_digest(analysis),
                "final_repair_directive": _text_digest(final),
                "first_candidates": _exact([tool.to_json() for tool in first]),
                "repeated_candidates": _exact([tool.to_json() for tool in repeated]),
            }
        )

    def role(item: Any) -> str:
        if item.system.startswith("You analyze public"):
            return "contract_analysis"
        if item.system.startswith("You trace rejected"):
            return "repair_analysis"
        if item.system.startswith("You repair rejected"):
            return "repair"
        return "generation"

    calls = completer.calls
    roles = [role(item) for item in calls]
    expected_roles = ["contract_analysis", "generation", "generation"]
    for _strategy in range(1, 8):
        expected_roles.extend(("repair_analysis", "repair", "repair"))
    if roles != expected_roles:
        raise RuntimeError(f"generator cache/call order changed: {roles!r}")
    return {
        "generation_prompt": _text_digest(_model_authored_generation_prompt(request)),
        "contract_analysis_prompt": _text_digest(
            _model_authored_contract_analysis_prompt(request)
        ),
        "strategy_rows": strategy_rows,
        "call_roles": roles,
        "chat_requests": [_chat_request_projection(item) for item in calls],
        "cache_key_order": [
            _text_digest(key)
            for key in generator._contract_analyses  # noqa: SLF001
        ],
        "cache_values": list(generator._contract_analyses.values()),  # noqa: SLF001
    }


def _all_profile_repair_prompt_matrix() -> dict[str, Any]:
    """Freeze strategies 1–7 for every named and generic profile path."""

    from sage_ts.generation.tool_generator import _model_authored_repair_prompt
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput

    profile_cases: list[tuple[str, str | None]] = [
        (name, name) for name in PROFILE_NAMES
    ]
    profile_cases.extend(EXTRA_PROFILE_CASES)
    rows: list[dict[str, Any]] = []
    for case_id, suggested_name in profile_cases:
        request = _profile_request(suggested_name)
        emitted_name = suggested_name or "inferred_profile_tool"
        rejected = _tool(
            emitted_name,
            f"def {emitted_name}(value: str) -> str:\n    return value\n",
            family=ToolFamily.CANONICALIZER,
            inputs=(ToolInput("value", "str", "Visible value."),),
            required=(),
        )
        strategy_prompts = []
        for strategy in range(1, 8):
            errors = (
                "source_0_mismatch:'actual'!='expected'",
                f"repair_strategy:{strategy}",
            )
            strategy_prompts.append(
                {
                    "strategy": strategy,
                    "prompt": _text_digest(
                        _model_authored_repair_prompt(request, rejected, errors)
                    ),
                }
            )
        rows.append(
            {
                "case_id": case_id,
                "suggested_tool_name": suggested_name,
                "strategies": strategy_prompts,
            }
        )

    # These orthogonal failures activate repair branches that a plain semantic
    # mismatch does not.  Keep each string readable because validator errors are
    # part of the model-visible repair contract.
    native_request = _native_repair_request()
    rejected_native = _tool(
        "prepare_add_contact_args",
        (
            "def prepare_add_contact_args(name: str, phone_number: str) -> dict:\n"
            "    return {}\n"
        ),
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(
            ToolInput("name", "str", "Visible name."),
            ToolInput("phone_number", "str", "Visible phone number."),
        ),
        output_annotation="dict",
        output_schema={"type": "object", "properties": {}},
        native=True,
        required=("add_contact",),
    )
    failure_cases: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("syntax", ("syntax_error:invalid syntax",)),
        ("missing_code", ("missing_generated_code",)),
        ("semantic", ("source_0_mismatch:{}!={'status': 'success'}",)),
        (
            "native_count",
            (
                "source_0_native_action_count:0!=1:expected=add_contact:{'name': 'Dana', 'phone_number': '+15550100'}",
            ),
        ),
        (
            "native_arguments",
            (
                "source_0_native_action_arguments:{'name': 'Dana'}!={'name': 'Dana', 'phone_number': '+15550100'}",
            ),
        ),
        (
            "native_execution",
            ("source_0_native_action_execution_error:ValueError:boom",),
        ),
        (
            "confirmation",
            ("source_0_native_action_confirmation_missing",),
        ),
        (
            "multi_case_native_rewrite",
            (
                "source_0_native_action_count:0!=1:expected=add_contact:{}",
                "held_out_0_native_action_arguments:{}!={'name': 'Lee'}",
            ),
        ),
    )
    failure_rows = []
    for case_id, errors in failure_cases:
        failure_rows.append(
            {
                "case_id": case_id,
                "errors": list(errors),
                "strategy_prompts": [
                    {
                        "strategy": strategy,
                        "prompt": _text_digest(
                            _model_authored_repair_prompt(
                                native_request,
                                rejected_native,
                                (*errors, f"repair_strategy:{strategy}"),
                            )
                        ),
                    }
                    for strategy in range(1, 8)
                ],
            }
        )
    return {
        "profile_case_count": len(profile_cases),
        "profile_rows": rows,
        "orthogonal_failure_rows": failure_rows,
    }


def _prompt_nonreachability_proof() -> dict[str, Any]:
    """Prove the live generator does not call the legacy request.prompt method."""

    import tempfile
    from pathlib import Path
    from types import MethodType, SimpleNamespace

    from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
    from sage_ts.generation.tool_generator import ToolGenerationRequest, ToolGenerator
    from sage_ts.orchestration.online_birth import OnlineBirthController
    from sage_ts.registry.store import RegistryStore
    from sage_ts.validation.sandbox_validator import ToolExample, ValidationResult

    request = _profile_request("unknown_reusable_profile")
    completer = _StaticCompleter(_response_for("unknown_reusable_profile"))
    generator = ToolGenerator(completer)
    original = ToolGenerationRequest.prompt

    def fail_if_used(_self: Any) -> str:
        raise RuntimeError("legacy_request_prompt_was_called")

    ToolGenerationRequest.prompt = fail_if_used
    try:
        direct_call = _capture(request.prompt)
        generated = generator.generate(request)
        repaired = generator.repair_candidates(
            request,
            generated,
            ("source_0_mismatch:'actual'!='expected'", "repair_strategy:7"),
        )

        online_name = "prompt_reachability_online"
        online_completer = _StaticCompleter(_response_for(online_name))
        with tempfile.TemporaryDirectory(prefix="sage-prompt-reachability-") as raw:
            root = Path(raw)
            output_dir = root / "output"
            output_dir.mkdir()
            controller = OnlineBirthController(
                store=RegistryStore(root / "registry"),
                generator=ToolGenerator(online_completer),
                output_dir=output_dir,
                recurrence_threshold=1,
                failure_memory_path=None,
            )

            def accept_without_changing_generation(
                _self: Any, tool: Any, _observation: Any
            ) -> tuple[Any, None, ValidationResult]:
                return (
                    SimpleNamespace(grading_classification="canonical_preserving"),
                    None,
                    ValidationResult(
                        True,
                        (),
                        source_example_count=1,
                        held_out_check_count=1,
                        runtime_smoke_passed=True,
                    ),
                )

            controller._gate_and_validate = MethodType(  # noqa: SLF001
                accept_without_changing_generation,
                controller,
            )
            observation = CapabilityObservation(
                scenario_name="Legacy prompt online-birth reachability",
                canonical_key=f"canonicalizer:{online_name}",
                observation="Normalize repeated visible values deterministically.",
                allowed_families=("canonicalizer",),
                validation_examples=(
                    ToolExample({"value": " alpha "}, "alpha"),
                    ToolExample({"value": " beta "}, "beta", held_out=True),
                ),
                generation_allowed=True,
                reason="prompt_reachability",
                inadequacy_signals=("prompt_reachability",),
                evidence_source="visible_task_context",
                task_context_label="visible normalization request",
                task_family_key="prompt_reachability_family",
            )
            online_outcome = controller.observe(observation)
            online_registry_names = sorted(controller.store.load_entries())
    finally:
        ToolGenerationRequest.prompt = original
    if (
        direct_call.get("status") != "raised"
        or len(completer.calls) != 2
        or len(online_completer.calls) != 1
    ):
        raise RuntimeError("legacy prompt live-path reachability proof failed")
    return {
        "direct_prompt_call": direct_call,
        "live_generate_returned": _exact(generated.to_json()),
        "live_repair_returned": _exact([tool.to_json() for tool in repaired]),
        "live_generator_chat_requests": [
            _chat_request_projection(item) for item in completer.calls
        ],
        "online_birth_outcome": online_outcome,
        "online_birth_registry_names": online_registry_names,
        "online_birth_chat_requests": [
            _chat_request_projection(item) for item in online_completer.calls
        ],
        "proof": (
            "ToolGenerationRequest.prompt raised under the patch while "
            "ToolGenerator.generate, ToolGenerator.repair_candidates, and the "
            "OnlineBirthController generation path all completed."
        ),
    }


def _tool(
    name: str,
    code: str,
    *,
    family: Any,
    inputs: tuple[Any, ...],
    output_annotation: str = "str",
    output_schema: dict[str, Any] | None = None,
    native: bool = False,
    required: tuple[str, ...] = ("search_contacts",),
) -> Any:
    from sage_ts.generation.tool_spec import (
        GeneratedTool,
        StructuredInadequacyEvidence,
        ToolSpec,
    )

    spec = ToolSpec(
        tool_name=name,
        family=family,
        description="Deterministic visible-input replay helper for related tasks.",
        inputs=inputs,
        output_annotation=output_annotation,
        output_schema=output_schema,
        positive_triggers=("visible repeated capability",),
        negative_triggers=("missing visible input", "ambiguous visible input"),
        preserves_side_effect_tools=required,
        required_original_tool_calls=required,
        abstain_behavior="Abstain when visible information is insufficient.",
        generalization_rationale=(
            "The same deterministic transformation recurs across multiple public "
            "task families and safely preserves original operations."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("visible_text_cleanup", "visible_record_lookup"),
        reason_tool_is_decisive=(
            "It converts recurring visible constraints into one deterministic result "
            "before the preserved original operation."
        ),
        diagnostic_only=True,
        shortfall_cluster_evidence=("generator-validator-corpus",),
        known_failure_mechanisms_addressed=("repeated_visible_failure",),
        native_action_delegation=native,
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Repeated visible failures demonstrate one reusable deterministic "
                "capability gap across related public tasks."
            ),
            signals=("repeated_visible_failure",),
        ),
    )
    return GeneratedTool(spec=spec, code=code)


def _candidate_pipeline_corpus() -> dict[str, Any]:
    from sage_ts.generation.tool_generator import (
        ToolGenerationRequest,
        _normalize_model_authored_tool,
        _select_model_authored_candidate,
        parse_generated_tool_candidates_json,
    )
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation import sandbox_validator
    from sage_ts.validation.sandbox_validator import ValidationResult

    name = "pipeline_replay_tool"
    rich_spec = _minimal_spec_payload(name)
    rich_spec.update(
        {
            "inputs": [
                "value:str:Visible scalar.",
                {"param": "items", "type": "list", "description": "Visible items."},
            ],
            "positive_triggers": "one trigger",
            "negative_triggers": {"first": "missing", "second": "ambiguous"},
            "preserves_side_effect_tools": 7,
            "required_original_tool_calls": None,
            "estimated_step_compression": "about 4 steps",
            "cross_task_applicability_count": 2.9,
            "applicable_task_families": ["family_a", "family_b"],
            "diagnostic_only": 1,
            "inadequacy_evidence": "legacy evidence text",
        }
    )
    parse_cases = {
        "code_lines_list": json.dumps(
            {
                "spec": rich_spec,
                "code_lines": [
                    f"def {name}(value: str, items: list) -> str:",
                    "    return value",
                ],
            }
        ),
        "code_lines_string_fenced": "```json\n"
        + json.dumps(
            {
                "spec": rich_spec,
                "code_lines": f"def {name}(value, items):\n    return value\n",
            }
        )
        + "\n```",
        "raw_code": json.dumps(
            {
                "spec": rich_spec,
                "code": f"def {name}(value, items):\n    return value\n",
            }
        ),
        "candidate_filtering": json.dumps(
            {
                "candidates": [
                    None,
                    {"spec": {}},
                    {
                        "spec": rich_spec,
                        "code_lines": [
                            f"def {name}(value, items):",
                            "    return value",
                        ],
                    },
                ]
            }
        ),
        "default_name": json.dumps(
            {
                "spec": {**rich_spec, "tool_name": ""},
                "code": "def fallback_name(value, items):\n    return value\n",
            }
        ),
    }
    parsed: dict[str, Any] = {}
    for case_id, payload in parse_cases.items():
        tools = parse_generated_tool_candidates_json(
            payload,
            default_tool_name="fallback_name" if case_id == "default_name" else None,
        )
        parsed[case_id] = [tool.to_json() for tool in tools]

    parse_errors = {
        "malformed_json": "{",
        "top_level_list": "[]",
        "missing_spec": '{"code":"x"}',
        "missing_name": json.dumps(
            {"spec": {**rich_spec, "tool_name": ""}, "code": "x"}
        ),
        "surrounding_whitespace": json.dumps(
            {"spec": {**rich_spec, "tool_name": " bad "}, "code": "x"}
        ),
        "invalid_python_name": json.dumps(
            {"spec": {**rich_spec, "tool_name": "bad-name"}, "code": "x"}
        ),
        "invalid_family": json.dumps(
            {"spec": {**rich_spec, "family": "unknown"}, "code": "x"}
        ),
        "invalid_input": json.dumps(
            {"spec": {**rich_spec, "inputs": [7]}, "code": "x"},
        ),
        "code_lines_not_list": json.dumps(
            {"spec": rich_spec, "code_lines": {"line": "x"}}
        ),
        "missing_code": json.dumps({"spec": rich_spec}),
        "no_valid_candidates": json.dumps(
            {"candidates": [None, {"spec": {}}, {"spec": rich_spec}]}
        ),
    }
    captured_errors = {
        case_id: _capture(
            lambda payload=payload: parse_generated_tool_candidates_json(payload)
        )
        for case_id, payload in parse_errors.items()
    }

    request = ToolGenerationRequest(
        scenario_name="Candidate normalization and selection",
        observation="Normalize visible public examples into one reusable helper.",
        allowed_families=(str(ToolFamily.CANONICALIZER),),
        validation_examples=(
            {"inputs": {"value": "a", "count": 1}, "expected": "a"},
            {
                "inputs": {"value": "b", "count": 2.5},
                "expected": "b",
                "held_out": True,
            },
        ),
        suggested_tool_name=name,
        inadequacy_evidence={
            "summary": "Repeated visible normalization failures need one helper.",
            "signals": ["normalization_failure"],
        },
    )
    raw = _tool(
        name,
        "def wrong_signature(value):\n    return value\n",
        family=ToolFamily.CANONICALIZER,
        inputs=(ToolInput("wrong", "dict", ""),),
        required=(),
    )
    raw = replace(
        raw,
        spec=replace(
            raw.spec,
            description="short",
            generalization_rationale="short",
            estimated_step_compression=1,
            cross_task_applicability_count=1,
            applicable_task_families=("canonicalizer",),
            reason_tool_is_decisive="short",
            positive_triggers=(),
            negative_triggers=(),
            shortfall_cluster_evidence=(),
            known_failure_mechanisms_addressed=(),
        ),
    )
    normalized = _normalize_model_authored_tool(request, raw)

    def candidate(code: str) -> Any:
        return _tool(
            name,
            code,
            family=ToolFamily.CANONICALIZER,
            inputs=(
                ToolInput("value", "str", "Visible value."),
                ToolInput("count", "float", "Visible count."),
            ),
            required=(),
        )

    syntax = candidate(f"def {name}(:\n    pass\n")
    near = candidate(
        f"def {name}(value: str, count: float) -> str:\n    return value.upper()\n"
    )
    accepted = candidate(
        f"def {name}(value: str, count: float) -> str:\n    return value\n"
    )
    selected_accepted = _select_model_authored_candidate(
        request, [syntax, near, accepted]
    )
    selected_best = _select_model_authored_candidate(request, [syntax, near])
    selected_no_examples = _select_model_authored_candidate(
        replace(request, validation_examples=()), [near, accepted]
    )

    original_validate = sandbox_validator.validate_generated_tool
    calls: list[str] = []

    def synthetic_validate(tool: Any, _examples: Any) -> ValidationResult:
        calls.append(tool.code)
        if len(calls) == 1:
            raise RuntimeError("synthetic validator failure")
        return ValidationResult(True, ())

    sandbox_validator.validate_generated_tool = synthetic_validate
    try:
        selected_after_exception = _select_model_authored_candidate(
            request, [near, accepted]
        )
    finally:
        sandbox_validator.validate_generated_tool = original_validate

    return {
        "parsing": _exact(parsed),
        "parsing_errors": captured_errors,
        "normalization": {
            "before": _exact(raw.to_json()),
            "after": _exact(normalized.to_json()),
        },
        "candidate_selection": {
            "accepted_first_success": _exact(selected_accepted.to_json()),
            "lowest_error_distance": _exact(selected_best.to_json()),
            "no_examples_first_candidate": _exact(selected_no_examples.to_json()),
            "validator_exception_skipped": _exact(selected_after_exception.to_json()),
            "validator_exception_call_order": [_text_digest(item) for item in calls],
            "empty_candidates": _capture(
                lambda: _select_model_authored_candidate(request, [])
            ),
        },
    }


def probe_generator_profile_corpus() -> dict[str, Any]:
    """Cover all named profiles, generic/unknown paths, cache, and pipeline."""

    from sage_ts.generation import tool_generator

    _assert_profile_coverage(PROFILE_NAMES)
    cases = [_run_profile(name, name) for name in PROFILE_NAMES]
    cases.extend(_run_profile(case_id, name) for case_id, name in EXTRA_PROFILE_CASES)
    mapping_order = {
        "default_families": list(
            tool_generator.MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL.items()
        ),
        "default_original_calls": list(
            tool_generator.MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL.items()
        ),
        "output_tool_name_enums": list(
            tool_generator.MODEL_AUTHORED_OUTPUT_TOOL_NAME_ENUM_BY_TOOL.items()
        ),
    }
    return {
        "fixture": {
            "named_profile_count": len(PROFILE_NAMES),
            "named_profile_order": list(PROFILE_NAMES),
            "extra_profile_cases": [list(item) for item in EXTRA_PROFILE_CASES],
        },
        "constant_type_and_order": _exact(mapping_order),
        "profiles": cases,
        "legacy_name_mappings": _exact(_legacy_name_mappings()),
        "native_eligibility": _exact(_native_eligibility_matrix()),
        "repair_and_cache": _repair_and_cache_corpus(),
        "all_profile_repair_prompts": _all_profile_repair_prompt_matrix(),
        "candidate_pipeline": _candidate_pipeline_corpus(),
        "legacy_prompt_nonreachability": _prompt_nonreachability_proof(),
    }


VALIDATOR_ERROR_KINDS: tuple[str, ...] = (
    "missing_source_examples",
    "missing_semantic_held_out_examples",
    "missing_negative_applicability_examples",
    "weak_generalization_rationale",
    "denied_node",
    "function_name_mismatch",
    "error",
    "nondeterministic",
    "mismatch",
    "non_json_serializable_output",
    "runtime_smoke_schema_invalid",
    "runtime_smoke_tool_schema_error",
    "runtime_smoke_missing_example",
    "runtime_smoke_missing_tool_trace",
    "runtime_smoke_toolsandbox_error",
    "native_action_in_loop",
    "multiple_native_actions_not_supported",
    "native_action_execution_error",
    "native_action_result_must_be_json_object",
    "unexpected_native_action",
    "native_action_abstain_status_missing",
    "native_action_abstain_reason_missing",
    "native_action_abstain_confirmation_present",
    "native_action_abstain_action_present",
    "native_action_abstain_action_missing",
    "native_action_abstain_confirmation_missing",
    "native_action_count",
    "native_action_result_reports_failure_after_call",
    "native_action_success_status_missing",
    "native_action_confirmation_missing",
    "native_action_confirmation_not_subject_first",
    "native_action_result_name",
    "native_action_name",
    "native_action_arguments_invalid",
    "native_action_arguments",
    "native_action_contract_missing_positive_action",
)


def _validator_error_kind(error: str) -> str:
    import re

    value = re.sub(r"^(?:source|held_out|negative)_\d+_", "", error)
    for kind in VALIDATOR_ERROR_KINDS:
        if value == kind or value.startswith(kind + ":"):
            return kind
    return value.split(":", 1)[0]


def _assert_validator_error_coverage(errors: Iterable[str]) -> None:
    observed = {_validator_error_kind(error) for error in errors}
    missing = [kind for kind in VALIDATOR_ERROR_KINDS if kind not in observed]
    if missing:
        raise RuntimeError(f"validator error corpus missing branches: {missing!r}")


def _validation_payload(result: Any) -> dict[str, Any]:
    return {
        "accepted": result.accepted,
        "errors": list(result.errors),
        "source_example_count": result.source_example_count,
        "held_out_check_count": result.held_out_check_count,
        "negative_applicability_count": result.negative_applicability_count,
        "runtime_smoke_passed": result.runtime_smoke_passed,
    }


def _ordinary_validator_cases() -> tuple[dict[str, Any], list[str]]:
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation.sandbox_validator import (
        ToolExample,
        validate_generated_tool,
    )

    source = ToolExample({"value": "alpha"}, "alpha")
    held_out = ToolExample({"value": "beta"}, "beta", held_out=True)
    base = _tool(
        "validator_corpus",
        "def validator_corpus(value: str) -> str:\n    return value\n",
        family=ToolFamily.CANONICALIZER,
        inputs=(ToolInput("value", "str", "Visible value."),),
    )
    composite = _tool(
        "validator_composite_corpus",
        (
            "def validator_composite_corpus(value: str) -> dict:\n"
            "    return {'downstream_tool_kwargs': {'value': value}, "
            "'should_call_tool': True, 'abstain_reason': ''}\n"
        ),
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "downstream_tool_kwargs": {"type": "object"},
                "should_call_tool": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
            },
        },
        required=("modify_contact",),
    )
    composite_examples = (
        ToolExample(
            {"value": "alpha"},
            {
                "downstream_tool_kwargs": {"value": "alpha"},
                "should_call_tool": True,
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {"value": "beta"},
            {
                "downstream_tool_kwargs": {"value": "beta"},
                "should_call_tool": True,
                "abstain_reason": "",
            },
            held_out=True,
        ),
    )
    cases: dict[str, tuple[Any, tuple[Any, ...]]] = {
        "accepted": (base, (source, held_out)),
        "missing_examples": (base, ()),
        "negative_only_still_missing_source": (
            base,
            (ToolExample({"value": ""}, "", negative_applicability=True),),
        ),
        "missing_held_out": (base, (source,)),
        "missing_negative": (composite, composite_examples),
        "gate_precedes_ast": (
            replace(
                base,
                spec=replace(base.spec, generalization_rationale="weak"),
                code="import os\ndef other(value):\n    return value\n",
            ),
            (source, held_out),
        ),
        "ast_precedes_schema": (
            replace(
                base,
                code="import os\ndef other(value):\n    return value\n",
            ),
            (source, held_out),
        ),
        "schema_precedes_execution": (
            replace(base, code="def other(value):\n    return missing_name\n"),
            (source, held_out),
        ),
        "execution_error": (
            replace(
                base,
                code="def validator_corpus(value: str) -> str:\n    return 1 / 0\n",
            ),
            (source, held_out),
        ),
        "nondeterministic": (
            replace(
                base,
                code=(
                    "def validator_corpus(value: str, seen=[]) -> str:\n"
                    "    seen.append(value)\n"
                    "    return value if len(seen) % 2 else value + '!'\n"
                ),
            ),
            (source, held_out),
        ),
        "semantic_mismatch": (
            replace(
                base,
                code=(
                    "def validator_corpus(value: str) -> str:\n"
                    "    return value.upper()\n"
                ),
            ),
            (source, held_out),
        ),
        "non_json_serializable": (
            replace(
                base,
                code="def validator_corpus(value: str) -> str:\n    return {value}\n",
            ),
            (
                ToolExample({"value": "alpha"}, {"alpha"}),
                ToolExample({"value": "beta"}, {"beta"}, held_out=True),
            ),
        ),
    }
    results = {
        case_id: _validation_payload(validate_generated_tool(tool, examples))
        for case_id, (tool, examples) in cases.items()
    }
    errors = [error for result in results.values() for error in result["errors"]]
    return results, errors


def _semantic_match_helpers() -> dict[str, Any]:
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation.sandbox_validator import (
        _benign_negative_abstain_reason_mismatch,
        _structured_abstention_outputs_match,
    )

    abstention_tool = _tool(
        "abstention_match_corpus",
        "def abstention_match_corpus(value: str) -> dict:\n    return {}\n",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_annotation="dict",
        output_schema={"type": "object", "properties": {}},
    )
    expected = {
        "should_abstain": True,
        "missing_information": ["time"],
        "required_original_tools": ["add_reminder"],
        "safe_next_action": "ask for time",
        "final_answer_recommendation": "Please provide a time.",
        "abstain_reason": "missing time",
    }
    actual = {**expected, "final_answer_recommendation": "What time should I use?"}
    return {
        "benign_negative": {
            "accepted": _benign_negative_abstain_reason_mismatch(
                "negative_0",
                {"status": "abstain", "abstain_reason": "Need a time."},
                {"status": "abstain", "abstain_reason": "missing time"},
            ),
            "wrong_label": _benign_negative_abstain_reason_mismatch(
                "source_0",
                {"status": "abstain", "abstain_reason": "Need a time."},
                {"status": "abstain", "abstain_reason": "missing time"},
            ),
            "empty_reason": _benign_negative_abstain_reason_mismatch(
                "negative_0",
                {"status": "abstain", "abstain_reason": ""},
                {"status": "abstain", "abstain_reason": "missing time"},
            ),
        },
        "structured_abstention": {
            "accepted_text_variation": _structured_abstention_outputs_match(
                abstention_tool, actual, expected
            ),
            "empty_recommendation": _structured_abstention_outputs_match(
                abstention_tool,
                {**actual, "final_answer_recommendation": ""},
                expected,
            ),
            "wrong_family": _structured_abstention_outputs_match(
                replace(
                    abstention_tool,
                    spec=replace(abstention_tool.spec, family=ToolFamily.CANONICALIZER),
                ),
                actual,
                expected,
            ),
        },
    }


def _runtime_smoke_cases() -> tuple[dict[str, Any], list[str]]:
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation import sandbox_validator
    from sage_ts.validation.sandbox_validator import ToolExample

    example = ToolExample({"value": "alpha"}, "alpha")
    base = _tool(
        "runtime_smoke_corpus",
        "def runtime_smoke_corpus(value: str) -> str:\n    return value\n",
        family=ToolFamily.CANONICALIZER,
        inputs=(ToolInput("value", "str", "Visible value."),),
    )
    invalid = replace(base, code="def other(value):\n    return value\n")
    raising = replace(
        base,
        code="def runtime_smoke_corpus(value: str) -> str:\n    return 1 / 0\n",
    )

    rows: dict[str, Any] = {
        "success": sandbox_validator._runtime_smoke(base, example),  # noqa: SLF001
        "schema_invalid": sandbox_validator._runtime_smoke(  # noqa: SLF001
            invalid, example
        ),
        "missing_example": sandbox_validator._runtime_smoke(base, None),  # noqa: SLF001
        "toolsandbox_execution_error": sandbox_validator._runtime_smoke(  # noqa: SLF001
            raising, example
        ),
    }

    original_convert = sandbox_validator.convert_to_openai_tool
    original_trace = sandbox_validator.add_tool_trace

    def fail_conversion(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("synthetic schema conversion failure")

    sandbox_validator.convert_to_openai_tool = fail_conversion
    try:
        rows["tool_schema_error"] = sandbox_validator._runtime_smoke(  # noqa: SLF001
            base, example
        )
    finally:
        sandbox_validator.convert_to_openai_tool = original_convert

    def omit_trace(*_args: Any, **_kwargs: Any) -> None:
        return None

    sandbox_validator.add_tool_trace = omit_trace
    try:
        rows["missing_tool_trace"] = sandbox_validator._runtime_smoke(  # noqa: SLF001
            base, example
        )
    finally:
        sandbox_validator.add_tool_trace = original_trace

    errors = [str(row[1]) for row in rows.values() if row[1] is not None]
    return rows, errors


def _native_tool(body: str, *, required: tuple[str, ...] = ("add_contact",)) -> Any:
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput

    return _tool(
        "native_validator_corpus",
        "def native_validator_corpus(name: str, phone_number: str) -> dict:\n" + body,
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(
            ToolInput("name", "str", "Visible contact name."),
            ToolInput("phone_number", "str", "Visible contact phone number."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "confirmation": {"type": "string"},
                "abstain_reason": {"type": "string"},
                "native_action": {"type": "string"},
                "native_result": {},
            },
        },
        native=True,
        required=required,
    )


def _native_validator_cases() -> tuple[dict[str, Any], list[str]]:
    from sage_ts.validation.sandbox_validator import (
        ToolExample,
        _expected_native_actions,
        _validate_native_action_tool,
    )

    positive = ToolExample(
        {"name": "Dana", "phone_number": "+15550100"},
        _action_expected("add_contact", {"name": "Dana", "phone_number": "+15550100"}),
    )
    negative = ToolExample(
        {"name": "", "phone_number": ""},
        {"should_call_tool": False},
        negative_applicability=True,
    )
    success_body = (
        "    native_result = add_contact(name=name, phone_number=phone_number)\n"
        "    return {'status': 'success', 'confirmation': name + ' added', "
        "'abstain_reason': '', 'native_action': 'add_contact', "
        "'native_result': native_result}\n"
    )
    abstain_body = (
        "    return {'status': 'abstain', 'confirmation': '', "
        "'abstain_reason': 'missing contact fields', 'native_action': '', "
        "'native_result': None}\n"
    )
    accepted_body = (
        "    if not name.strip() or not phone_number.strip():\n"
        + "        "
        + abstain_body.removeprefix("    ")
        + success_body
    )
    labeled = (("source_0", positive), ("negative_0", negative))

    multiple = ToolExample(
        positive.inputs,
        {
            "action_sequence": [
                {
                    "tool_name": "add_contact",
                    "arguments": {"name": "Dana", "phone_number": "+15550100"},
                },
                {
                    "tool_name": "remove_contact",
                    "arguments": {"person_id": "p1"},
                },
            ]
        },
    )
    cases: dict[str, tuple[Any, tuple[tuple[str, Any], ...]]] = {
        "accepted": (_native_tool(accepted_body), labeled),
        "loop_call": (
            _native_tool(
                "    native_result = None\n"
                "    for _index in range(1):\n"
                "        native_result = add_contact(name=name, phone_number=phone_number)\n"
                "    return {'status': 'success', 'confirmation': name + ' added', 'abstain_reason': '', 'native_action': 'add_contact', 'native_result': native_result}\n"
            ),
            (("source_0", positive),),
        ),
        "multiple_expected_actions": (
            _native_tool(success_body, required=("add_contact", "remove_contact")),
            (("source_0", multiple),),
        ),
        "schema_invalid_per_case": (
            replace(
                _native_tool(success_body),
                code="def other(name: str, phone_number: str) -> dict:\n    return {}\n",
            ),
            (("source_0", positive),),
        ),
        "execution_error": (
            _native_tool("    return 1 / 0\n"),
            (("source_0", positive),),
        ),
        "non_object_result": (
            _native_tool(
                "    native_result = add_contact(name=name, phone_number=phone_number)\n"
                "    return {name}\n"
            ),
            (("source_0", positive),),
        ),
        "negative_unexpected_and_present_fields": (
            _native_tool(success_body),
            (("negative_0", negative),),
        ),
        "negative_missing_fields": (
            _native_tool(
                "    return {'status': 'abstain', 'abstain_reason': 'missing'}\n"
            ),
            (("negative_0", negative),),
        ),
        "positive_zero_calls_and_failure_result": (
            _native_tool(
                "    return {'status': 'abstain', 'confirmation': '', "
                "'abstain_reason': 'failed', 'native_action': 'remove_contact', "
                "'native_result': None}\n"
            ),
            (("source_0", positive),),
        ),
        "failure_result_after_one_call": (
            _native_tool(
                "    native_result = add_contact(name=name, phone_number=phone_number)\n"
                "    return {'status': 'abstain', 'confirmation': '', "
                "'abstain_reason': 'failed after call', 'native_action': 'add_contact', "
                "'native_result': native_result}\n"
            ),
            (("source_0", positive),),
        ),
        "positive_two_calls": (
            _native_tool(
                "    first = add_contact(name=name, phone_number=phone_number)\n"
                "    second = add_contact(name=name, phone_number=phone_number)\n"
                "    return {'status': 'success', 'confirmation': name + ' added', "
                "'abstain_reason': '', 'native_action': 'add_contact', "
                "'native_result': second}\n"
            ),
            (("source_0", positive),),
        ),
        "subject_not_first": (
            _native_tool(
                "    native_result = add_contact(name=name, phone_number=phone_number)\n"
                "    return {'status': 'success', 'confirmation': 'Added contact ' + name, "
                "'abstain_reason': '', 'native_action': 'add_contact', "
                "'native_result': native_result}\n"
            ),
            (("source_0", positive),),
        ),
        "wrong_action_name": (
            _native_tool(
                "    native_result = remove_contact(person_id=name)\n"
                "    return {'status': 'success', 'confirmation': name + ' removed', "
                "'abstain_reason': '', 'native_action': 'remove_contact', "
                "'native_result': native_result}\n",
                required=("add_contact", "remove_contact"),
            ),
            (("source_0", positive),),
        ),
        "arguments_invalid": (
            _native_tool(
                "    native_result = add_contact(bogus=name)\n"
                "    return {'status': 'success', 'confirmation': name + ' added', "
                "'abstain_reason': '', 'native_action': 'add_contact', "
                "'native_result': native_result}\n"
            ),
            (("source_0", positive),),
        ),
        "arguments_mismatch": (
            _native_tool(
                "    native_result = add_contact(name=name, phone_number='+1999')\n"
                "    return {'status': 'success', 'confirmation': name + ' added', "
                "'abstain_reason': '', 'native_action': 'add_contact', "
                "'native_result': native_result}\n"
            ),
            (("source_0", positive),),
        ),
        "positive_contract_missing": (
            _native_tool(abstain_body),
            (("negative_0", negative),),
        ),
    }
    results = {
        case_id: list(_validate_native_action_tool(tool, examples))
        for case_id, (tool, examples) in cases.items()
    }
    expected_action_shapes = {
        "not_object": _expected_native_actions("add_contact"),
        "empty_sequence_falls_through": _expected_native_actions(
            {
                "action_sequence": [],
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {"name": "Dana", "phone_number": "+1"},
            }
        ),
        "sequence_skips_malformed": _expected_native_actions(
            {
                "action_sequence": [
                    None,
                    {"tool_name": "unknown", "arguments": {}},
                    {
                        "tool_name": "add_contact",
                        "arguments": {"name": "Dana", "phone_number": "+1"},
                    },
                ]
            }
        ),
        "false_should_call_wins": _expected_native_actions(
            {
                "should_call": False,
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {"name": "Dana", "phone_number": "+1"},
            }
        ),
        "named_kwargs_false": _expected_native_actions(
            {
                "add_contact_kwargs": {"name": "Dana", "phone_number": "+1"},
                "should_call_add_contact": False,
            }
        ),
    }
    errors = [error for row in results.values() for error in row]
    return {
        "results": results,
        "expected_action_shapes": expected_action_shapes,
    }, errors


def probe_validator_error_corpus() -> dict[str, Any]:
    """Exercise every sandbox-validator error branch and preserve error order."""

    ordinary, ordinary_errors = _ordinary_validator_cases()
    runtime, runtime_errors = _runtime_smoke_cases()
    native, native_errors = _native_validator_cases()
    all_errors = [*ordinary_errors, *runtime_errors, *native_errors]
    _assert_validator_error_coverage(all_errors)
    observed_order: list[str] = []
    for error in all_errors:
        kind = _validator_error_kind(error)
        if kind not in observed_order:
            observed_order.append(kind)
    return {
        "fixture": {
            "required_error_kind_count": len(VALIDATOR_ERROR_KINDS),
            "required_error_kinds": list(VALIDATOR_ERROR_KINDS),
            "observed_first_occurrence_order": observed_order,
        },
        "ordinary_pipeline": _exact(ordinary),
        "semantic_match_helpers": _exact(_semantic_match_helpers()),
        "runtime_smoke": _exact(runtime),
        "native_action_validation": _exact(native),
        "all_errors_in_execution_order": _exact(all_errors),
    }


PROBES: dict[str, Callable[[], dict[str, Any]]] = {
    "generator_profile_corpus": probe_generator_profile_corpus,
    "validator_error_corpus": probe_validator_error_corpus,
}


def run_probe(name: str) -> dict[str, Any]:
    try:
        probe = PROBES[name]
    except KeyError as error:
        raise ValueError(f"unknown generator/validator corpus probe: {name}") from error
    return probe()
