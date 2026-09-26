"""Deterministic Step 5 replay probes for generation and validation.

This module belongs to the external validation harness.  It is never imported
by the SAGE package and deliberately uses fake completers and generators only.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any, Callable


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


def _ordered_key_paths(value: Any, path: str = "") -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    if isinstance(value, dict):
        orders.append({"path": path or "/", "keys": [str(key) for key in value]})
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            orders.extend(_ordered_key_paths(item, f"{path}/{escaped}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            orders.extend(_ordered_key_paths(item, f"{path}/{index}"))
    return orders


def _exact(value: Any) -> dict[str, Any]:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return {
        "python_type": type(value).__name__,
        "value": _jsonable(value),
        "object_key_order": _ordered_key_paths(value),
        "raw_json": raw,
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
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


def _spec(
    name: str,
    family: Any,
    *,
    inputs: tuple[Any, ...],
    output_annotation: str = "dict",
    output_properties: dict[str, Any] | None = None,
    positive: tuple[str, ...] = ("replay_gap",),
    negative: tuple[str, ...] = (),
    preserves: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
    native: bool = False,
) -> Any:
    from sage_ts.generation.tool_spec import StructuredInadequacyEvidence, ToolSpec

    return ToolSpec(
        tool_name=name,
        family=family,
        description=(
            f"Deterministic replay helper {name} operating only on visible inputs."
        ),
        inputs=inputs,
        output_annotation=output_annotation,
        output_schema=(
            {"type": "object", "properties": output_properties}
            if output_properties is not None
            else None
        ),
        positive_triggers=positive,
        negative_triggers=negative,
        preserves_side_effect_tools=preserves,
        required_original_tool_calls=required,
        abstain_behavior=(
            "Abstain on missing, ambiguous, or insufficient information."
            if negative
            else ""
        ),
        generalization_rationale=(
            "This deterministic transformation recurs across several visible task "
            "families and safely replaces repeated reasoning steps."
        ),
        native_action_delegation=native,
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Visible task evidence repeatedly lacks this deterministic reusable "
                "capability across related requests."
            ),
            signals=positive or ("replay_gap",),
        ),
    )


def _tool(
    name: str,
    family: Any,
    code: str,
    *,
    inputs: tuple[Any, ...],
    output_annotation: str = "dict",
    output_properties: dict[str, Any] | None = None,
    positive: tuple[str, ...] = ("replay_gap",),
    negative: tuple[str, ...] = (),
    preserves: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
    native: bool = False,
) -> Any:
    from sage_ts.generation.tool_spec import GeneratedTool

    return GeneratedTool(
        spec=_spec(
            name,
            family,
            inputs=inputs,
            output_annotation=output_annotation,
            output_properties=output_properties,
            positive=positive,
            negative=negative,
            preserves=preserves,
            required=required,
            native=native,
        ),
        code=code,
    )


def _validation_payload(result: Any) -> dict[str, Any]:
    return {
        "accepted": result.accepted,
        "errors": list(result.errors),
        "source_example_count": result.source_example_count,
        "held_out_check_count": result.held_out_check_count,
        "negative_applicability_count": result.negative_applicability_count,
        "runtime_smoke_passed": result.runtime_smoke_passed,
    }


def probe_generation_boundary() -> dict[str, Any]:
    """Freeze exact model requests, cache order, parsing, and selection."""

    from sage_ts.generation.tool_generator import (
        ToolGenerationRequest,
        ToolGenerator,
        parse_generated_tool_candidates_json,
    )
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput

    canonical_name = "canonicalize_replay_value"
    canonical_spec = replace(
        _spec(
            canonical_name,
            ToolFamily.CANONICALIZER,
            inputs=(ToolInput("value", "str", "Visible value."),),
            output_annotation="str",
            negative=("missing value", "ambiguous value"),
            preserves=("search_contacts",),
            required=("search_contacts",),
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("text_normalization", "visible_value_cleanup"),
        reason_tool_is_decisive=(
            "The helper deterministically normalizes visible values before the "
            "preserved downstream operation."
        ),
        diagnostic_only=True,
        known_failure_mechanisms_addressed=("inconsistent_visible_value_format",),
    )
    canonical_codes = (
        f"def {canonical_name}(value: str) -> str:\n    return value.strip()\n",
        f"def {canonical_name}(value: str) -> str:\n    return value.strip().lower()\n",
        f"def {canonical_name}(value: str) -> str:\n    return value.casefold().strip()\n",
    )
    canonical_candidates = [
        {"spec": canonical_spec.to_json(), "code": code}
        for code in canonical_codes
    ]
    canonical_response = json.dumps(
        {"candidates": ["skip-non-object", {"spec": {}}, *canonical_candidates]},
        separators=(",", ":"),
    )

    native_name = "prepare_add_contact_args"
    native_properties = {
        "status": {"type": "string"},
        "confirmation": {"type": "string"},
        "abstain_reason": {"type": "string"},
        "native_action": {"type": "string"},
        "native_result": {},
    }
    native_spec = _spec(
        native_name,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(
            ToolInput("name", "str", "Visible contact name."),
            ToolInput("phone_number", "str", "Visible contact phone number."),
        ),
        output_properties=native_properties,
        positive=("add_contact",),
        negative=("missing contact", "insufficient information"),
        preserves=("add_contact",),
        required=("add_contact",),
    )
    native_code = (
        f"def {native_name}(name: str, phone_number: str) -> dict:\n"
        "    if not name.strip() or not phone_number.strip():\n"
        "        return {'status': 'abstain', 'confirmation': '', "
        "'abstain_reason': 'missing contact fields', 'native_action': '', "
        "'native_result': None}\n"
        "    native_result = add_contact(name=name, phone_number=phone_number)\n"
        "    return {'status': 'success', 'confirmation': name + ' added', "
        "'abstain_reason': '', 'native_action': 'add_contact', "
        "'native_result': native_result}\n"
    )
    native_response = json.dumps(
        {"candidates": [{"spec": native_spec.to_json(), "code": native_code}]},
        separators=(",", ":"),
    )

    standard_request = ToolGenerationRequest(
        scenario_name="visible canonicalization replay",
        observation="Normalize a visible value consistently across related tasks.",
        allowed_families=(str(ToolFamily.CANONICALIZER),),
        validation_examples=(
            {"inputs": {"value": " Alpha "}, "expected": "alpha"},
            {
                "inputs": {"value": " Beta "},
                "expected": "beta",
                "held_out": True,
            },
        ),
        suggested_tool_name=canonical_name,
        inadequacy_evidence={
            "summary": "Visible values repeatedly require the same normalization.",
            "signals": ["canonicalization"],
        },
    )
    native_examples = (
        {
            "inputs": {"name": "Dana", "phone_number": "+15550100"},
            "expected": {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Dana",
                    "phone_number": "+15550100",
                },
                "should_call_tool": True,
            },
        },
        {
            "inputs": {"name": "Lee", "phone_number": "+15550200"},
            "expected": {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Lee",
                    "phone_number": "+15550200",
                },
                "should_call_tool": True,
            },
            "held_out": True,
        },
        {
            "inputs": {"name": "", "phone_number": ""},
            "expected": {
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "should_call_tool": False,
                "abstain_reason": "missing contact fields",
            },
            "negative_applicability": True,
        },
    )
    native_request = ToolGenerationRequest(
        scenario_name="visible add-contact replay",
        observation=(
            "Visible contact fields need one validated add-contact action or a safe "
            "abstention when required fields are missing."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=native_examples,
        suggested_tool_name=native_name,
        inadequacy_evidence={
            "summary": "Repeated visible contact requests need one native action.",
            "signals": ["add_contact"],
            "failed_tool_calls": ["add_contact"],
        },
    )

    class FakeCompleter:
        model = "replay-model"

        def __init__(self) -> None:
            self.calls: list[Any] = []

        def complete(self, request: Any) -> str:
            self.calls.append(request)
            if request.system.startswith("You analyze public"):
                return '{"analysis":"contract-analysis"}'
            if request.system.startswith("You trace rejected"):
                return '{"analysis":"repair-analysis"}'
            if request.system.startswith("You repair rejected"):
                return native_response
            if request.system.startswith("You generate safe"):
                return (
                    native_response
                    if native_name in request.user
                    else canonical_response
                )
            raise AssertionError(f"unexpected request: {request.system}")

    completer = FakeCompleter()
    generator = ToolGenerator(completer)
    selected_standard = generator.generate(standard_request)
    selected_native = generator.generate(native_request)
    first_repairs = generator.repair_candidates(
        native_request,
        selected_native,
        ("source_0_mismatch:{'status': 'bad'}!={'status': 'success'}",),
    )
    repeated_repairs = generator.repair_candidates(
        native_request,
        selected_native,
        ("source_0_mismatch:{'status': 'bad'}!={'status': 'success'}",),
    )
    strategy_repairs = generator.repair_candidates(
        native_request,
        selected_native,
        (
            "source_0_mismatch:{'status': 'bad'}!={'status': 'success'}",
            "repair_strategy:4",
        ),
    )

    def request_payload(request: Any) -> dict[str, Any]:
        payload = asdict(request)
        return {
            "request": _exact(payload),
            "user_byte_count": len(request.user.encode("utf-8")),
            "user_sha256": hashlib.sha256(request.user.encode("utf-8")).hexdigest(),
            "system_byte_count": len(request.system.encode("utf-8")),
            "system_sha256": hashlib.sha256(
                request.system.encode("utf-8")
            ).hexdigest(),
        }

    call_roles: list[str] = []
    for request in completer.calls:
        if request.system.startswith("You analyze public"):
            call_roles.append("contract_analysis")
        elif request.system.startswith("You trace rejected"):
            call_roles.append("repair_analysis")
        elif request.system.startswith("You repair rejected"):
            call_roles.append("repair")
        else:
            call_roles.append("generation")
    expected_roles = [
        "generation",
        "contract_analysis",
        "generation",
        "repair_analysis",
        "repair",
        "repair",
        "repair_analysis",
        "repair",
    ]
    if call_roles != expected_roles:
        raise RuntimeError(
            f"generator analysis-cache order changed: {call_roles!r}"
        )
    if "return value.strip().lower()" not in selected_standard.code:
        raise RuntimeError(
            "candidate selection no longer chooses first accepted tool: "
            f"{selected_standard.code!r}"
        )

    fenced = f"```json\n{canonical_response}\n```"
    parsed = parse_generated_tool_candidates_json(
        fenced, default_tool_name=canonical_name
    )
    parsing_errors = {
        "top_level_list": _capture(
            lambda: parse_generated_tool_candidates_json("[]")
        ),
        "no_valid_candidates": _capture(
            lambda: parse_generated_tool_candidates_json(
                '{"candidates":[null,{"spec":{}}]}'
            )
        ),
        "invalid_function_name": _capture(
            lambda: parse_generated_tool_candidates_json(
                json.dumps(
                    {
                        "spec": {**canonical_spec.to_json(), "tool_name": "bad name"},
                        "code": "def bad():\n    return ''\n",
                    }
                )
            )
        ),
    }
    return {
        "call_order": call_roles,
        "requests": [request_payload(request) for request in completer.calls],
        "contract_analysis_cache_keys": _exact(list(generator._contract_analyses)),  # noqa: SLF001
        "candidate_parsing": {
            "valid_candidate_count": len(parsed),
            "valid_candidates": _exact([tool.to_json() for tool in parsed]),
            "errors": parsing_errors,
        },
        "selection": {
            "standard": _exact(selected_standard.to_json()),
            "native": _exact(selected_native.to_json()),
            "first_repairs": _exact([tool.to_json() for tool in first_repairs]),
            "repeated_repairs": _exact(
                [tool.to_json() for tool in repeated_repairs]
            ),
            "strategy_repairs": _exact(
                [tool.to_json() for tool in strategy_repairs]
            ),
        },
    }


def probe_validation_distance() -> dict[str, Any]:
    """Freeze both copies of validation-error distance and frontier semantics."""

    from sage_ts.generation import tool_generator as generator
    from sage_ts.orchestration import online_birth
    from sage_ts.validation.sandbox_validator import ValidationResult

    errors = [
        "syntax_error:invalid syntax",
        "missing_generated_code",
        "expected_exactly_one_function",
        "function_count_mismatch:2",
        "compiled_function_count_mismatch:0",
        "function_name_mismatch:other!=expected",
        "missing_expected_function",
        "compile_error:NameError:name 'x' is not defined",
        "denied_node:Import",
        "denied_call:eval",
        "denied_attribute_call:os.system",
        "source_0_native_action_count:0!=1:expected=add_contact:{}",
        "source_0_native_action_execution_error:ValueError:boom",
        "source_0_error:ValueError:boom",
        "source_0_mismatch:1!=2",
        "source_0_mismatch:{'a': 1, 'b': [2, 3]}!={'a': 9, 'b': [2, 8, 7]}",
        "source_0_mismatch:NOT_GIVEN!='visible'",
        "source_0_native_action_arguments:{'name': 'Dana'}!={'name': 'Dana', 'phone': '1'}",
        "source_0_mismatch:not-python!=also-not-python",
        "source_0_mismatch:{'same': 1}!={'same': 1}",
    ]
    rows = []
    for error in errors:
        generator_distance = generator._single_validation_error_distance(error)  # noqa: SLF001
        online_distance = online_birth._validation_error_distance(error)  # noqa: SLF001
        if generator_distance != online_distance:
            raise RuntimeError(f"distance copies diverged for {error!r}")
        rows.append(
            {
                "error": error,
                "generator_distance": generator_distance,
                "online_birth_distance": online_distance,
            }
        )
    aggregate = tuple(errors[11:16])
    failure_results = {
        "accepted": online_birth._validation_failure_score(  # noqa: SLF001
            ValidationResult(True, ("ignored",))
        ),
        "rejected_empty": online_birth._validation_failure_score(  # noqa: SLF001
            ValidationResult(False, ())
        ),
        "rejected_aggregate": online_birth._validation_failure_score(  # noqa: SLF001
            ValidationResult(False, aggregate)
        ),
        "generator_empty": generator._validation_error_distance(()),  # noqa: SLF001
        "generator_aggregate": generator._validation_error_distance(aggregate),  # noqa: SLF001
    }
    frontier_vectors = []
    for previous, repaired in (
        (("source_0_mismatch:1!=2",), ("held_out_0_mismatch:1!=2",)),
        (("source_0_mismatch:1!=2",), ("source_0_error:boom",)),
        (("generic_error",), ("held_out_0_mismatch:1!=2",)),
        (
            ("source_0_mismatch:1!=2", "negative_2_error:boom"),
            ("held_out_3_mismatch:1!=2",),
        ),
    ):
        frontier_vectors.append(
            {
                "previous": list(previous),
                "repaired": list(repaired),
                "previous_labels": sorted(
                    online_birth._validation_error_case_labels(previous)  # noqa: SLF001
                ),
                "repaired_labels": sorted(
                    online_birth._validation_error_case_labels(repaired)  # noqa: SLF001
                ),
                "advances": online_birth._advances_repair_case_frontier(  # noqa: SLF001
                    previous, repaired
                ),
            }
        )
    return {
        "error_rows": _exact(rows),
        "aggregate_scores": _exact(failure_results),
        "frontier_vectors": _exact(frontier_vectors),
    }


def probe_native_structural_cases() -> dict[str, Any]:
    """Freeze native-action example projection and structural-negative order."""

    from sage_ts.generation.tool_generator import (
        ToolGenerationRequest,
        _native_action_validation_examples,
        _native_action_validator_labeled_examples,
    )
    from sage_ts.generation.tool_spec import ToolFamily
    from sage_ts.validation.sandbox_validator import (
        ToolExample,
        _with_native_action_structural_negatives,
    )

    def expected_action(identifier: str) -> dict[str, Any]:
        return {
            "downstream_tool_name": "remove_reminder",
            "downstream_tool_kwargs": {"reminder_id": identifier},
            "should_call_tool": True,
        }

    def raw_example(
        records: list[dict[str, Any]],
        *,
        identifier: str,
        timestamp_key: str = "",
        mode: str = "latest",
        held_out: bool = False,
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "records": records,
            "selection_mode": mode,
            "action_type": "remove_reminder",
        }
        if timestamp_key:
            inputs["timestamp_key"] = timestamp_key
        return {
            "inputs": inputs,
            "expected": expected_action(identifier),
            "held_out": held_out,
        }

    vectors: dict[str, tuple[dict[str, Any], ...]] = {
        "explicit_latest": (
            raw_example(
                [
                    {"reminder_id": "r1", "created_timestamp": 1.0},
                    {"reminder_id": "r2", "created_timestamp": 2.0},
                ],
                identifier="r2",
                timestamp_key="created_timestamp",
            ),
        ),
        "inferred_sorted_key": (
            raw_example(
                [
                    {"reminder_id": "r1", "z_timestamp": 9, "a_timestamp": 1},
                    {"reminder_id": "r2", "z_timestamp": 8, "a_timestamp": 2},
                ],
                identifier="r2",
            ),
        ),
        "oldest_alias": (
            raw_example(
                [
                    {"reminder_id": "r1", "created_timestamp": 1},
                    {"reminder_id": "r2", "created_timestamp": 2},
                ],
                identifier="r1",
                timestamp_key="created_timestamp",
                mode="earliest",
            ),
        ),
        "bool_is_numeric": (
            raw_example(
                [
                    {"reminder_id": "r1", "created_timestamp": False},
                    {"reminder_id": "r2", "created_timestamp": True},
                ],
                identifier="r2",
            ),
        ),
        "nonnumeric_no_inference": (
            raw_example(
                [
                    {"reminder_id": "r1", "created_timestamp": "one"},
                    {"reminder_id": "r2", "created_timestamp": "two"},
                ],
                identifier="r2",
            ),
        ),
        "multiple_eligible_first_only": (
            raw_example(
                [
                    {"reminder_id": "first-1", "created_timestamp": 1},
                    {"reminder_id": "first-2", "created_timestamp": 2},
                ],
                identifier="first-2",
                timestamp_key="created_timestamp",
            ),
            raw_example(
                [
                    {"reminder_id": "second-1", "reminder_timestamp": 3},
                    {"reminder_id": "second-2", "reminder_timestamp": 4},
                ],
                identifier="second-2",
                timestamp_key="reminder_timestamp",
                held_out=True,
            ),
        ),
    }

    results: dict[str, Any] = {}
    for vector_id, items in vectors.items():
        request = ToolGenerationRequest(
            scenario_name=f"native structural {vector_id}",
            observation="Select one visible reminder and remove it safely.",
            allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
            validation_examples=items,
            suggested_tool_name="select_action_target_by_recency",
        )
        validator_examples = tuple(
            ToolExample(
                inputs=dict(item["inputs"]),
                expected=item["expected"],
                held_out=bool(item.get("held_out")),
                negative_applicability=bool(item.get("negative_applicability")),
            )
            for item in items
        )
        projected = _native_action_validation_examples(request)
        labeled = _native_action_validator_labeled_examples(request)
        augmented = _with_native_action_structural_negatives(validator_examples)
        results[vector_id] = {
            "generator_projection": _exact(projected),
            "validator_labeled_projection": _exact(labeled),
            "validator_augmented_examples": _exact(
                [asdict(example) for example in augmented]
            ),
        }

    explicit = vectors["explicit_latest"][0]
    malformed_inputs = copy.deepcopy(explicit["inputs"])
    malformed_inputs["records"][0].pop("created_timestamp")
    preexisting = (
        ToolExample(dict(explicit["inputs"]), explicit["expected"]),
        ToolExample(malformed_inputs, {}, negative_applicability=True),
    )
    deduped = _with_native_action_structural_negatives(preexisting)
    results["preexisting_malformed_deduplication"] = {
        "before": _exact([asdict(example) for example in preexisting]),
        "after": _exact([asdict(example) for example in deduped]),
    }
    return {
        "vectors": results,
        "invariants": {
            "generator_structural_order": ["missing_rank_field", "tied_rank"],
            "only_first_eligible_contract_augmented": True,
            "bool_retains_python_numeric_semantics": True,
        },
    }


def probe_schema_ast_matrix() -> dict[str, Any]:
    """Freeze AST safety, schema compatibility, and error precedence surfaces."""

    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation.ast_safety import check_ast_safety
    from sage_ts.validation.schema_check import compile_generated_tool

    ast_cases = {
        "safe": "def replay(value: str) -> str:\n    return value.strip()\n",
        "syntax": "def replay(:\n    pass\n",
        "zero_functions": "value = 1\n",
        "two_functions": (
            "def replay(value):\n    return value\n\n"
            "def second(value):\n    return value\n"
        ),
        "denied_nodes_and_calls": (
            "import os\n"
            "def replay(value):\n"
            "    try:\n"
            "        while value:\n"
            "            return eval(value)\n"
            "    except Exception:\n"
            "        raise RuntimeError(os.system('true'))\n"
        ),
        "deduped_denied_call": (
            "def replay(value):\n"
            "    first = open(value)\n"
            "    second = open(value)\n"
            "    return str(first) + str(second)\n"
        ),
        "denied_attribute_roots": (
            "def replay(value):\n"
            "    return subprocess.run(value)\n"
        ),
        "allowed_comprehension": (
            "def replay(values: list) -> list:\n"
            "    return [str(item).strip() for item in values]\n"
        ),
    }
    ast_results = {
        case_id: asdict(check_ast_safety(code))
        for case_id, code in ast_cases.items()
    }

    base = _tool(
        "replay_schema_tool",
        ToolFamily.CANONICALIZER,
        "def replay_schema_tool(value: str) -> str:\n    return value\n",
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_annotation="str",
    )
    schema_cases = {
        "valid_exact_annotations": base,
        "valid_unannotated": replace(
            base,
            code="def replay_schema_tool(value):\n    return value\n",
        ),
        "valid_optional_subset": replace(
            base,
            spec=replace(
                base.spec,
                inputs=(ToolInput("value", "str | None", "Visible value."),),
            ),
            code=(
                "def replay_schema_tool(value: str) -> str:\n"
                "    return value\n"
            ),
        ),
        "syntax": replace(base, code="def replay_schema_tool(:\n    pass\n"),
        "zero_functions": replace(base, code="value = 1\n"),
        "two_functions": replace(
            base,
            code=(
                "def replay_schema_tool(value):\n    return value\n\n"
                "def second(value):\n    return value\n"
            ),
        ),
        "wrong_defined_name": replace(
            base,
            code="def other(value: str) -> str:\n    return value\n",
        ),
        "exec_failure": replace(
            base,
            code=(
                "@missing_decorator\n"
                "def replay_schema_tool(value: str) -> str:\n"
                "    return value\n"
            ),
        ),
        "compiled_function_removed": replace(
            base,
            code=(
                "def replay_schema_tool(value: str) -> str:\n"
                "    return value\n"
                "replay_schema_tool = 1\n"
            ),
        ),
        "wrong_input_annotation": replace(
            base,
            code=(
                "def replay_schema_tool(value: int) -> str:\n"
                "    return str(value)\n"
            ),
        ),
        "wrong_return_annotation": replace(
            base,
            code=(
                "def replay_schema_tool(value: str) -> int:\n"
                "    return len(value)\n"
            ),
        ),
    }

    def schema_payload(tool: Any) -> dict[str, Any]:
        result = compile_generated_tool(tool)
        function = result.function
        return {
            "valid": result.valid,
            "errors": list(result.errors),
            "function": (
                {
                    "name": function.__name__,
                    "signature": str(inspect.signature(function)),
                    "annotations": {
                        key: getattr(value, "__name__", str(value))
                        for key, value in function.__annotations__.items()
                    },
                }
                if function is not None
                else None
            ),
        }

    schema_results = {
        case_id: schema_payload(tool) for case_id, tool in schema_cases.items()
    }
    return {
        "ast": _exact(ast_results),
        "schema": _exact(schema_results),
        "unreachable_or_defensive_errors": ["missing_expected_function"],
    }


def probe_validator_matrix() -> dict[str, Any]:
    """Freeze partitioning, validation-stage precedence, and native contracts."""

    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.validation.sandbox_validator import (
        ToolExample,
        _expected_native_actions,
        _partition_examples,
        validate_generated_tool,
    )

    source = ToolExample({"value": "alpha"}, "alpha")
    second = ToolExample({"value": "beta"}, "beta")
    marked = ToolExample({"value": "gamma"}, "gamma", held_out=True)
    negative = ToolExample(
        {"value": ""}, "", held_out=True, negative_applicability=True
    )
    partition_vectors = {
        "empty": (),
        "single": (source,),
        "implicit_last_held_out": (source, second, ToolExample({"value": "c"}, "c")),
        "explicit_held_out": (source, second, marked),
        "negative_overrides_held_out": (source, marked, negative),
    }
    partitions: dict[str, Any] = {}
    for vector_id, examples in partition_vectors.items():
        groups = _partition_examples(examples)
        partitions[vector_id] = {
            "source": [asdict(item) for item in groups[0]],
            "held_out": [asdict(item) for item in groups[1]],
            "negative": [asdict(item) for item in groups[2]],
        }

    base = _tool(
        "validator_replay",
        ToolFamily.CANONICALIZER,
        "def validator_replay(value: str) -> str:\n    return value\n",
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_annotation="str",
    )
    ordinary_examples = (source, marked)
    validation_cases: dict[str, tuple[Any, tuple[Any, ...]]] = {
        "accepted": (base, ordinary_examples),
        "missing_examples": (base, ()),
        "missing_held_out": (base, (source,)),
        "candidate_gate_before_ast": (
            replace(
                base,
                spec=replace(base.spec, generalization_rationale="weak"),
                code="import os\ndef other(value):\n    return value\n",
            ),
            ordinary_examples,
        ),
        "ast_before_schema": (
            replace(
                base,
                code="import os\ndef other(value):\n    return value\n",
            ),
            ordinary_examples,
        ),
        "schema_before_execution": (
            replace(base, code="def other(value):\n    return missing_name\n"),
            ordinary_examples,
        ),
        "semantic_mismatch": (
            replace(
                base,
                code=(
                    "def validator_replay(value: str) -> str:\n"
                    "    return value.upper()\n"
                ),
            ),
            ordinary_examples,
        ),
        "nondeterministic_default_state": (
            replace(
                base,
                code=(
                    "def validator_replay(value: str, seen=[]):\n"
                    "    seen.append(value)\n"
                    "    return value if len(seen) % 2 else value + '!'\n"
                ),
            ),
            ordinary_examples,
        ),
    }
    composite = _tool(
        "validator_composite",
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        (
            "def validator_composite(value: str) -> dict:\n"
            "    return {'downstream_tool_kwargs': {'value': value}, "
            "'should_call_tool': True, 'abstain_reason': ''}\n"
        ),
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_properties={
            "downstream_tool_kwargs": {"type": "object"},
            "should_call_tool": {"type": "boolean"},
            "abstain_reason": {"type": "string"},
        },
        negative=("missing value",),
        preserves=("modify_contact",),
        required=("modify_contact",),
    )
    validation_cases["missing_negative_before_candidate_gate"] = (
        composite,
        (
            ToolExample(
                {"value": "a"},
                {
                    "downstream_tool_kwargs": {"value": "a"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
            ),
            ToolExample(
                {"value": "b"},
                {
                    "downstream_tool_kwargs": {"value": "b"},
                    "should_call_tool": True,
                    "abstain_reason": "",
                },
                held_out=True,
            ),
        ),
    )
    ordinary_results = {
        case_id: _validation_payload(validate_generated_tool(tool, examples))
        for case_id, (tool, examples) in validation_cases.items()
    }

    native_properties = {
        "status": {"type": "string"},
        "confirmation": {"type": "string"},
        "abstain_reason": {"type": "string"},
        "native_action": {"type": "string"},
        "native_result": {},
    }
    native_inputs = (
        ToolInput("name", "str", "Visible name."),
        ToolInput("phone_number", "str", "Visible phone."),
    )
    native_examples = (
        ToolExample(
            {"name": "Dana", "phone_number": "+15550100"},
            {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Dana",
                    "phone_number": "+15550100",
                },
                "should_call_tool": True,
            },
        ),
        ToolExample(
            {"name": "Lee", "phone_number": "+15550200"},
            {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Lee",
                    "phone_number": "+15550200",
                },
                "should_call_tool": True,
            },
            held_out=True,
        ),
        ToolExample(
            {"name": "", "phone_number": ""},
            {
                "should_call_tool": False,
                "abstain_reason": "missing contact fields",
            },
            negative_applicability=True,
        ),
    )

    def native_tool(body: str) -> Any:
        return _tool(
            "native_validator_replay",
            ToolFamily.COMPOSITE_WORKFLOW_HELPER,
            "def native_validator_replay(name: str, phone_number: str) -> dict:\n"
            + body,
            inputs=native_inputs,
            output_properties=native_properties,
            positive=("add_contact",),
            negative=("missing contact", "insufficient information"),
            preserves=("add_contact",),
            required=("add_contact",),
            native=True,
        )

    abstain = (
        "    if not name.strip() or not phone_number.strip():\n"
        "        return {'status': 'abstain', 'confirmation': '', "
        "'abstain_reason': 'missing contact fields', 'native_action': '', "
        "'native_result': None}\n"
    )
    success = (
        "    native_result = add_contact(name=name, phone_number=phone_number)\n"
        "    return {'status': 'success', 'confirmation': name + ' added', "
        "'abstain_reason': '', 'native_action': 'add_contact', "
        "'native_result': native_result}\n"
    )
    native_cases = {
        "accepted": native_tool(abstain + success),
        "wrong_call_count": native_tool(
            abstain
            + "    first = add_contact(name=name, phone_number=phone_number)\n"
            + "    second = add_contact(name=name, phone_number=phone_number)\n"
            + "    return {'status': 'success', 'confirmation': name + ' added', "
            "'abstain_reason': '', 'native_action': 'add_contact', "
            "'native_result': second}\n"
        ),
        "argument_mismatch": native_tool(
            abstain
            + "    native_result = add_contact(name=name, phone_number='+1999')\n"
            + "    return {'status': 'success', 'confirmation': name + ' added', "
            "'abstain_reason': '', 'native_action': 'add_contact', "
            "'native_result': native_result}\n"
        ),
        "native_action_inside_loop": native_tool(
            abstain
            + "    native_result = None\n"
            + "    for _index in range(1):\n"
            + "        native_result = add_contact(name=name, phone_number=phone_number)\n"
            + "    return {'status': 'success', 'confirmation': name + ' added', "
            "'abstain_reason': '', 'native_action': 'add_contact', "
            "'native_result': native_result}\n"
        ),
        "unexpected_action_on_negative": native_tool(success),
    }
    native_results = {
        case_id: _validation_payload(
            validate_generated_tool(tool, native_examples)
        )
        for case_id, tool in native_cases.items()
    }
    expected_action_vectors = {
        "sequence_precedence": _expected_native_actions(
            {
                "action_sequence": [
                    {
                        "tool_name": "remove_contact",
                        "arguments": {"person_id": "p1"},
                    }
                ],
                "tool_name": "add_contact",
                "arguments": {"name": "ignored", "phone_number": "+1"},
            }
        ),
        "false_should_call": _expected_native_actions(
            {
                "should_call_tool": False,
                "tool_name": "remove_contact",
                "arguments": {"person_id": "p1"},
            }
        ),
        "named_kwargs_fallback": _expected_native_actions(
            {
                "remove_contact_kwargs": {"person_id": "p1"},
                "should_call_remove_contact": True,
            }
        ),
        "multiple_sequence": _expected_native_actions(
            {
                "action_sequence": [
                    {
                        "tool_name": "remove_contact",
                        "arguments": {"person_id": "p1"},
                    },
                    {
                        "tool_name": "remove_reminder",
                        "arguments": {"reminder_id": "r1"},
                    },
                ]
            }
        ),
    }
    return {
        "partitions": _exact(partitions),
        "ordinary_validation": _exact(ordinary_results),
        "native_validation": _exact(native_results),
        "native_expected_action_parsing": _exact(expected_action_vectors),
    }


def probe_online_birth_repair() -> dict[str, Any]:
    """Exercise candidate batches, best/seed/frontier rules, and attempt cap."""

    from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
    from sage_ts.generation.tool_spec import ToolFamily, ToolInput
    from sage_ts.orchestration.online_birth import (
        CANDIDATE_REPAIR_ATTEMPTS,
        OnlineBirthController,
    )
    from sage_ts.registry.store import RegistryStore
    from sage_ts.validation.sandbox_validator import ToolExample, ValidationResult

    def marker(tool: Any) -> str:
        return tool.code.rsplit("# marker:", 1)[-1].strip()

    def make_tool(name: str, label: str, *, native: bool = False) -> Any:
        if native:
            return _tool(
                name,
                ToolFamily.COMPOSITE_WORKFLOW_HELPER,
                (
                    f"def {name}(value: str) -> dict:\n"
                    f"    return {{'value': value}}\n# marker:{label}"
                ),
                inputs=(ToolInput("value", "str", "Visible value."),),
                output_properties={"value": {"type": "string"}},
                positive=("repair_replay",),
                negative=("missing value",),
                preserves=("add_contact",),
                required=("add_contact",),
                native=True,
            )
        return _tool(
            name,
            ToolFamily.CANONICALIZER,
            (
                f"def {name}(value: str) -> str:\n"
                f"    return value\n# marker:{label}"
            ),
            inputs=(ToolInput("value", "str", "Visible value."),),
            output_annotation="str",
            positive=("repair_replay",),
        )

    def observation(name: str, *, native: bool = False) -> CapabilityObservation:
        family = (
            ToolFamily.COMPOSITE_WORKFLOW_HELPER
            if native
            else ToolFamily.CANONICALIZER
        )
        return CapabilityObservation(
            scenario_name=f"visible_{name}",
            canonical_key=(
                f"composite:{name}" if native else f"canonicalizer:{name}"
            ),
            observation=(
                "Repeated visible values require deterministic repair behavior "
                "across several related requests."
            ),
            allowed_families=(str(family),),
            validation_examples=(
                ToolExample({"value": "a"}, "a"),
                ToolExample({"value": "b"}, "b", held_out=True),
                ToolExample(
                    {"value": ""},
                    "",
                    negative_applicability=native,
                ),
            ),
            generation_allowed=True,
            reason="deterministic_repair_replay",
            inadequacy_signals=("repair_replay",),
            evidence_source="visible_task_context",
            task_context_label=f"visible {name} request",
            task_family_key="repair_replay_family",
        )

    class SequenceGenerator:
        def __init__(
            self,
            initial: Any,
            plans: dict[int, tuple[Any, ...]],
        ) -> None:
            self.initial = initial
            self.plans = plans
            self.generate_requests: list[dict[str, Any]] = []
            self.repair_calls: list[dict[str, Any]] = []

        def generate(self, request: Any) -> Any:
            self.generate_requests.append(
                {
                    "scenario_name": request.scenario_name,
                    "suggested_tool_name": request.suggested_tool_name,
                    "allowed_families": list(request.allowed_families),
                    "validation_example_count": len(request.validation_examples),
                }
            )
            return self.initial

        def repair(self, request: Any, rejected_tool: Any, errors: Any) -> Any:
            return self.repair_candidates(request, rejected_tool, errors)[0]

        def repair_candidates(
            self,
            request: Any,
            rejected_tool: Any,
            errors: tuple[str, ...],
        ) -> tuple[Any, ...]:
            strategy = next(
                int(item.split(":", 1)[1])
                for item in errors
                if item.startswith("repair_strategy:")
            )
            self.repair_calls.append(
                {
                    "strategy": strategy,
                    "seed_marker": marker(rejected_tool),
                    "errors": list(errors),
                }
            )
            return self.plans[strategy]

    class GenerateOnly:
        def __init__(self, initial: Any) -> None:
            self.initial = initial
            self.generate_count = 0

        def generate(self, _request: Any) -> Any:
            self.generate_count += 1
            return self.initial

    def project_event(event: str, payload: dict[str, Any]) -> dict[str, Any]:
        stable_keys = (
            "canonical_key",
            "tool_name",
            "attempt",
            "input_errors",
            "best_validation_score",
            "repaired_errors",
            "accepted",
            "validation_score",
            "improved_best",
            "advanced_case_frontier",
            "repair_candidate_count",
            "selected_candidate_index",
            "repair_candidate_validations",
            "repair_attempted",
            "repair_attempt_count",
            "errors",
            "rejection_count",
        )
        return {
            "event": event,
            **{key: copy.deepcopy(payload[key]) for key in stable_keys if key in payload},
        }

    def run_case(
        case_id: str,
        generated: Any,
        validations: dict[str, ValidationResult],
        *,
        native: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="sage-repair-replay-") as raw_dir:
            root = Path(raw_dir)
            output_dir = root / "output"
            output_dir.mkdir(parents=True)
            controller = OnlineBirthController(
                store=RegistryStore(root / "registry"),
                generator=generated,
                output_dir=output_dir,
                recurrence_threshold=1,
                failure_memory_path=None,
                event_hook=lambda event, payload: events.append(
                    project_event(event, payload)
                ),
            )

            def fake_gate_and_validate(
                _self: Any, tool: Any, _observation: Any
            ) -> tuple[Any, None, ValidationResult]:
                return (
                    SimpleNamespace(grading_classification="canonical_preserving"),
                    None,
                    validations[marker(tool)],
                )

            controller._gate_and_validate = MethodType(  # noqa: SLF001
                fake_gate_and_validate,
                controller,
            )
            outcome = controller.observe(observation(case_id, native=native))
            registry_names = sorted(controller.store.load_entries())
            return {
                "outcome": outcome,
                "registry_names": registry_names,
                "events": events,
                "rejected_count": controller.rejected_counts[
                    observation(case_id, native=native).canonical_key
                ],
                "generated_keys": sorted(controller.generated_keys),
            }

    nonnative_name = "repair_cap_replay"
    initial = make_tool(nonnative_name, "initial")
    first_worse = make_tool(nonnative_name, "first_worse")
    first_better = make_tool(nonnative_name, "first_better")
    plateau_tools = {
        index: make_tool(nonnative_name, f"plateau_{index}")
        for index in range(2, CANDIDATE_REPAIR_ATTEMPTS + 1)
    }
    alternate_tie = make_tool(nonnative_name, "plateau_2_alternate")
    nonnative_plans = {
        1: (first_worse, first_better),
        2: (plateau_tools[2], alternate_tie),
        **{
            index: (plateau_tools[index],)
            for index in range(3, CANDIDATE_REPAIR_ATTEMPTS + 1)
        },
    }
    initial_error = (
        "source_0_mismatch:{'a': 1, 'b': 2}!={'a': 9, 'b': 8}",
    )
    plateau_error = ("source_1_mismatch:1!=2",)
    nonnative_validations = {
        "initial": ValidationResult(False, initial_error),
        "first_worse": ValidationResult(False, ("generic_error",)),
        "first_better": ValidationResult(False, plateau_error),
        "plateau_2_alternate": ValidationResult(False, plateau_error),
        **{
            f"plateau_{index}": ValidationResult(False, plateau_error)
            for index in range(2, CANDIDATE_REPAIR_ATTEMPTS + 1)
        },
    }
    nonnative_generator = SequenceGenerator(initial, nonnative_plans)
    nonnative_result = run_case(
        nonnative_name,
        nonnative_generator,
        nonnative_validations,
        native=False,
    )
    if len(nonnative_generator.repair_calls) != CANDIDATE_REPAIR_ATTEMPTS:
        raise RuntimeError("online repair no longer honors the seven-attempt cap")

    native_name = "native_frontier_replay"
    native_initial = make_tool(native_name, "native_initial", native=True)
    frontier_one = make_tool(native_name, "frontier_one", native=True)
    frontier_stuck = make_tool(native_name, "frontier_stuck", native=True)
    frontier_two = make_tool(native_name, "frontier_two", native=True)
    native_accepted = make_tool(native_name, "native_accepted", native=True)
    native_generator = SequenceGenerator(
        native_initial,
        {
            1: (frontier_one,),
            2: (frontier_stuck,),
            3: (frontier_two,),
            4: (native_accepted,),
        },
    )
    native_validations = {
        "native_initial": ValidationResult(
            False, ("source_0_mismatch:1!=2",)
        ),
        "frontier_one": ValidationResult(
            False, ("held_out_0_mismatch:1!=2",)
        ),
        "frontier_stuck": ValidationResult(
            False, ("held_out_0_error:still failing",)
        ),
        "frontier_two": ValidationResult(
            False, ("negative_0_mismatch:1!=2",)
        ),
        "native_accepted": ValidationResult(
            True,
            (),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
    }
    native_result = run_case(
        native_name,
        native_generator,
        native_validations,
        native=True,
    )
    native_seed_order = [
        item["seed_marker"] for item in native_generator.repair_calls
    ]
    if native_seed_order != [
        "native_initial",
        "frontier_one",
        "native_initial",
        "frontier_two",
    ]:
        raise RuntimeError(f"native repair frontier changed: {native_seed_order!r}")

    no_repair_name = "no_repair_replay"
    no_repair_tool = make_tool(no_repair_name, "no_repair_initial")
    generate_only = GenerateOnly(no_repair_tool)
    no_repair_result = run_case(
        no_repair_name,
        generate_only,
        {"no_repair_initial": ValidationResult(False, ("generic_error",))},
        native=False,
    )

    return {
        "attempt_limit": CANDIDATE_REPAIR_ATTEMPTS,
        "nonnative_attempt_cap": {
            "controller": _exact(nonnative_result),
            "generation_requests": _exact(nonnative_generator.generate_requests),
            "repair_calls": _exact(nonnative_generator.repair_calls),
        },
        "native_case_frontier": {
            "controller": _exact(native_result),
            "generation_requests": _exact(native_generator.generate_requests),
            "repair_calls": _exact(native_generator.repair_calls),
        },
        "missing_repair_method": {
            "controller": _exact(no_repair_result),
            "generate_count": generate_only.generate_count,
        },
    }


PROBES: dict[str, Callable[[], dict[str, Any]]] = {
    "generation_boundary": probe_generation_boundary,
    "validation_distance": probe_validation_distance,
    "native_structural_cases": probe_native_structural_cases,
    "schema_ast_matrix": probe_schema_ast_matrix,
    "validator_matrix": probe_validator_matrix,
    "online_birth_repair": probe_online_birth_repair,
}


def run_probe(name: str) -> dict[str, Any]:
    """Run one named Step 5 contract probe."""

    try:
        probe = PROBES[name]
    except KeyError as error:
        raise ValueError(f"unknown Step 5 probe: {name}") from error
    return probe()
