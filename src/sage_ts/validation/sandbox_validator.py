"""Validation pipeline for generated deterministic helpers."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import dataclass
from typing import Any, cast

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.complete_tools import (
    COMPLETE_TOOLS_NATIVE_NAMES,
    native_action_tool_enabled,
    native_side_effect_tools,
)
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    new_context,
)
from tool_sandbox.common.tool_conversion import convert_to_openai_tool
from tool_sandbox.common.utils import add_tool_trace


@dataclass(frozen=True)
class ToolExample:
    inputs: dict[str, Any]
    expected: Any
    held_out: bool = False
    negative_applicability: bool = False


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    errors: tuple[str, ...]
    source_example_count: int = 0
    held_out_check_count: int = 0
    negative_applicability_count: int = 0
    runtime_smoke_passed: bool = False


def _json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


def _benign_negative_abstain_reason_mismatch(
    label: str,
    actual: Any,
    expected: Any,
) -> bool:
    """Allow wording variation only for semantically identical negative abstains."""

    if not label.startswith("negative_"):
        return False
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    actual_reason = str(actual.get("abstain_reason") or "").strip()
    expected_reason = str(expected.get("abstain_reason") or "").strip()
    if not actual_reason or not expected_reason:
        return False
    normalized_actual = dict(actual)
    normalized_actual["abstain_reason"] = expected_reason
    return normalized_actual == expected


def _structured_abstention_outputs_match(
    tool: GeneratedTool,
    actual: Any,
    expected: Any,
) -> bool:
    """Validate the safe-abstention decision, not one acceptable sentence."""

    if tool.spec.family is not ToolFamily.VALIDATION_ABSTENTION_HELPER:
        return False
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if not bool(actual.get("should_abstain")) or not bool(
        expected.get("should_abstain")
    ):
        return False
    for key in (
        "should_abstain",
        "missing_information",
        "required_original_tools",
        "safe_next_action",
        "abstain_reason",
    ):
        if actual.get(key) != expected.get(key):
            return False
    return bool(str(actual.get("final_answer_recommendation") or "").strip())


def _partition_examples(
    examples: tuple[ToolExample, ...],
) -> tuple[tuple[ToolExample, ...], tuple[ToolExample, ...], tuple[ToolExample, ...]]:
    """Split examples into source and semantic held-out cases.

    Existing observations predate the ``held_out`` flag and usually include
    multiple semantic expected-output examples. For those, keep all but the
    final case as source and reserve the final case as held-out. A single
    example is no longer sufficient for claim-grade acceptance.
    """
    negative_examples = tuple(
        example for example in examples if example.negative_applicability
    )
    non_negative_examples = tuple(
        example for example in examples if not example.negative_applicability
    )
    marked_held_out = tuple(
        example
        for example in examples
        if example.held_out and not example.negative_applicability
    )
    if marked_held_out:
        source = tuple(
            example
            for example in examples
            if not example.held_out and not example.negative_applicability
        )
        return source, marked_held_out, negative_examples
    if len(non_negative_examples) >= 2:
        source = non_negative_examples[:-1]
        held_out = non_negative_examples[-1:]
        return source, held_out, negative_examples
    source = non_negative_examples
    return source, (), negative_examples


def _requires_negative_applicability(tool: GeneratedTool) -> bool:
    return tool.spec.family in {
        ToolFamily.STATE_PRECONDITION_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    }


def _runtime_smoke(
    tool: GeneratedTool,
    example: ToolExample | None,
) -> tuple[bool, str | None]:
    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return False, "runtime_smoke_schema_invalid"
    try:
        convert_to_openai_tool(schema.function, name=tool.spec.tool_name)
    except Exception as exc:
        return False, f"runtime_smoke_tool_schema_error:{type(exc).__name__}:{exc}"
    if example is None:
        return False, "runtime_smoke_missing_example"
    try:
        context = ExecutionContext()
        context.trace_tool = True
        sandbox_namespace = cast(DatabaseNamespace, DatabaseNamespace.SANDBOX)
        context.add_to_database(
            sandbox_namespace,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": f"runtime smoke for {tool.spec.tool_name}",
                    "openai_tool_call_id": "sage-runtime-smoke",
                    "openai_function_name": tool.spec.tool_name,
                    "conversation_active": True,
                    "tool_call_exception": None,
                    "tool_trace": None,
                    "visible_to": [RoleType.AGENT, RoleType.EXECUTION_ENVIRONMENT],
                }
            ],
        )
        with new_context(context):
            result = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
            add_tool_trace(schema.function, result, **example.inputs)
            sandbox = context.get_database(sandbox_namespace)
            traces = sandbox["tool_trace"][0]
            if traces is None or len(traces) == 0:
                return False, "runtime_smoke_missing_tool_trace"
    except Exception as exc:
        return False, f"runtime_smoke_toolsandbox_error:{type(exc).__name__}:{exc}"
    return True, None


def _expected_native_actions(expected: Any) -> list[tuple[str, dict[str, Any]]]:
    """Read the native-action contract from a public validation example."""

    if not isinstance(expected, dict):
        return []
    sequence = expected.get("action_sequence")
    if isinstance(sequence, list) and sequence:
        actions: list[tuple[str, dict[str, Any]]] = []
        for item in sequence:
            if not isinstance(item, dict):
                continue
            name = str(item.get("tool_name") or "")
            arguments = item.get("arguments")
            if name in COMPLETE_TOOLS_NATIVE_NAMES and isinstance(arguments, dict):
                actions.append((name, dict(arguments)))
        return actions

    should_call_values = [
        bool(value)
        for key, value in expected.items()
        if str(key) == "should_call" or str(key).startswith("should_call_")
    ]
    if should_call_values and not any(should_call_values):
        return []

    name = str(expected.get("downstream_tool_name") or expected.get("tool_name") or "")
    arguments = expected.get("downstream_tool_kwargs")
    if not isinstance(arguments, dict):
        arguments = expected.get("arguments")
    if name in COMPLETE_TOOLS_NATIVE_NAMES and isinstance(arguments, dict):
        return [(name, dict(arguments))]

    for native_name in COMPLETE_TOOLS_NATIVE_NAMES:
        native_kwargs = expected.get(f"{native_name}_kwargs")
        should_call = expected.get(f"should_call_{native_name}")
        if isinstance(native_kwargs, dict) and (
            should_call is None or bool(should_call)
        ):
            return [(native_name, dict(native_kwargs))]
    return []


def _with_native_action_structural_negatives(
    examples: tuple[ToolExample, ...],
) -> tuple[ToolExample, ...]:
    """Add generic malformed-record and tie cases for native selectors."""

    existing_inputs = {
        json.dumps(example.inputs, sort_keys=True, default=str) for example in examples
    }
    additions: list[ToolExample] = []
    for example in examples:
        if example.negative_applicability or not _expected_native_actions(
            example.expected
        ):
            continue
        records = example.inputs.get("records")
        if (
            not isinstance(records, list)
            or not records
            or not all(isinstance(record, dict) for record in records)
        ):
            continue
        timestamp_key = str(example.inputs.get("timestamp_key") or "").strip()
        if not timestamp_key:
            common_keys = set(records[0])
            for record in records[1:]:
                common_keys.intersection_update(record)
            timestamp_key = next(
                (
                    key
                    for key in sorted(common_keys)
                    if key.endswith("_timestamp")
                    and all(
                        isinstance(record.get(key), (int, float)) for record in records
                    )
                ),
                "",
            )
        if not timestamp_key or not any(timestamp_key in record for record in records):
            continue

        malformed_records = [dict(record) for record in records]
        malformed_records[0].pop(timestamp_key, None)
        malformed_inputs = dict(example.inputs)
        malformed_inputs["records"] = malformed_records
        serialized = json.dumps(malformed_inputs, sort_keys=True, default=str)
        if serialized not in existing_inputs:
            additions.append(
                ToolExample(
                    inputs=malformed_inputs,
                    expected={},
                    negative_applicability=True,
                )
            )
            existing_inputs.add(serialized)

        numeric_records = [
            record
            for record in records
            if isinstance(record.get(timestamp_key), (int, float))
        ]
        if numeric_records:
            mode = str(example.inputs.get("selection_mode") or "latest").lower()
            selected = (
                min(numeric_records, key=lambda record: record[timestamp_key])
                if mode in {"oldest", "first", "oldest_by_time", "earliest"}
                else max(numeric_records, key=lambda record: record[timestamp_key])
            )
            tied_inputs = dict(example.inputs)
            tied_inputs["records"] = [
                *[dict(record) for record in records],
                dict(selected),
            ]
            serialized = json.dumps(tied_inputs, sort_keys=True, default=str)
            if serialized not in existing_inputs:
                additions.append(
                    ToolExample(
                        inputs=tied_inputs,
                        expected={},
                        negative_applicability=True,
                    )
                )
                existing_inputs.add(serialized)
        break
    return (*examples, *additions)


def _native_calls_inside_loops(code: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ()
    errors: list[str] = []
    loop_nodes = (ast.For, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    for loop in (node for node in ast.walk(tree) if isinstance(node, loop_nodes)):
        for node in ast.walk(loop):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in COMPLETE_TOOLS_NATIVE_NAMES
            ):
                errors.append(f"native_action_in_loop:{node.func.id}")
    return tuple(sorted(set(errors)))


def _recording_native_tools(
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
) -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for native_name in COMPLETE_TOOLS_NATIVE_NAMES:

        def record(
            *args: Any,
            _native_name: str = native_name,
            **kwargs: Any,
        ) -> Any:
            calls.append((_native_name, args, dict(kwargs)))
            if _native_name in {
                "add_contact",
                "add_reminder",
                "send_message_with_phone_number",
            }:
                return f"validation-{_native_name}-id"
            return None

        record.__name__ = native_name
        tools[native_name] = record
    return tools


def _normalized_native_arguments(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    native_function = native_side_effect_tools()[name]
    bound = inspect.signature(native_function).bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _validate_native_action_tool(
    tool: GeneratedTool,
    examples: tuple[tuple[str, ToolExample], ...],
) -> tuple[str, ...]:
    """Validate exact native delegation without mutating ToolSandbox state."""

    errors = list(_native_calls_inside_loops(tool.code))
    positive_contract_count = 0
    for label, example in examples:
        expected_actions = _expected_native_actions(example.expected)
        if len(expected_actions) > 1:
            errors.append(f"{label}_multiple_native_actions_not_supported")
            continue
        calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        schema = compile_generated_tool(
            tool,
            native_tool_overrides=_recording_native_tools(calls),
        )
        if not schema.valid or schema.function is None:
            errors.extend(f"{label}_{error}" for error in schema.errors)
            continue
        try:
            result = schema.function(**example.inputs)
        except Exception as exc:
            errors.append(
                f"{label}_native_action_execution_error:{type(exc).__name__}:{exc}"
            )
            continue
        if not isinstance(result, dict) or not _json_serializable(result):
            errors.append(
                f"{label}_native_action_result_must_be_json_object:"
                f"actual_type={type(result).__name__}"
            )
        if not expected_actions:
            if calls:
                errors.append(f"{label}_unexpected_native_action:{calls[0][0]}")
            if isinstance(result, dict):
                status = str(result.get("status") or "").strip().lower()
                abstain_reason = str(result.get("abstain_reason") or "").strip()
                confirmation = str(result.get("confirmation") or "").strip()
                native_action = str(result.get("native_action") or "").strip()
                if status != "abstain":
                    errors.append(f"{label}_native_action_abstain_status_missing")
                if not abstain_reason:
                    errors.append(f"{label}_native_action_abstain_reason_missing")
                if confirmation:
                    errors.append(f"{label}_native_action_abstain_confirmation_present")
                if native_action:
                    errors.append(f"{label}_native_action_abstain_action_present")
                if "native_action" not in result:
                    errors.append(f"{label}_native_action_abstain_action_missing")
                if "confirmation" not in result:
                    errors.append(f"{label}_native_action_abstain_confirmation_missing")
            continue
        positive_contract_count += 1
        if len(calls) != 1:
            expected_name, expected_kwargs = expected_actions[0]
            errors.append(
                f"{label}_native_action_count:{len(calls)}!=1:"
                f"expected={expected_name}:{expected_kwargs!r}"
            )
            continue
        expected_name, expected_kwargs = expected_actions[0]
        actual_name, args, kwargs = calls[0]
        if isinstance(result, dict):
            status = str(result.get("status") or "").strip().lower()
            confirmation = str(result.get("confirmation") or "").strip()
            native_action = str(result.get("native_action") or "").strip()
            reports_failure = (
                status in {"abstain", "error", "failed", "failure"}
                or result.get("success") is False
                or bool(str(result.get("abstain_reason") or "").strip())
            )
            if reports_failure:
                errors.append(
                    f"{label}_native_action_result_reports_failure_after_call"
                )
            if status != "success":
                errors.append(f"{label}_native_action_success_status_missing")
            if not confirmation:
                errors.append(f"{label}_native_action_confirmation_missing")
            if expected_name == "add_contact":
                visible_name = str(example.inputs.get("name") or "").strip()
                if visible_name and not confirmation.casefold().startswith(
                    visible_name.casefold()
                ):
                    errors.append(
                        f"{label}_native_action_confirmation_not_subject_first:"
                        f"{visible_name}"
                    )
            if native_action != expected_name:
                errors.append(
                    f"{label}_native_action_result_name:{native_action}!={expected_name}"
                )
        if actual_name != expected_name:
            errors.append(f"{label}_native_action_name:{actual_name}!={expected_name}")
            continue
        try:
            actual_arguments = _normalized_native_arguments(actual_name, args, kwargs)
            expected_arguments = _normalized_native_arguments(
                expected_name, (), expected_kwargs
            )
        except (TypeError, ValueError) as exc:
            errors.append(
                f"{label}_native_action_arguments_invalid:{type(exc).__name__}:{exc}"
            )
            continue
        if actual_arguments != expected_arguments:
            errors.append(
                f"{label}_native_action_arguments:{actual_arguments!r}!={expected_arguments!r}"
            )
    if positive_contract_count == 0:
        errors.append("native_action_contract_missing_positive_action")
    return tuple(errors)


def validate_generated_tool(
    tool: GeneratedTool,
    examples: tuple[ToolExample, ...],
) -> ValidationResult:
    if not examples:
        return ValidationResult(False, ("missing_source_examples",))
    if native_action_tool_enabled(tool):
        examples = _with_native_action_structural_negatives(examples)
    source_examples, held_out_examples, negative_examples = _partition_examples(
        examples
    )
    if not source_examples:
        return ValidationResult(False, ("missing_source_examples",))
    if not held_out_examples:
        return ValidationResult(
            False,
            ("missing_semantic_held_out_examples",),
            source_example_count=len(source_examples),
        )
    if _requires_negative_applicability(tool) and not negative_examples:
        return ValidationResult(
            False,
            ("missing_negative_applicability_examples",),
            source_example_count=len(source_examples),
            held_out_check_count=len(held_out_examples),
        )

    gate = evaluate_candidate_gate(tool.spec)
    if not gate.allowed:
        return ValidationResult(
            False, (gate.reason,), source_example_count=len(source_examples)
        )

    safety = check_ast_safety(tool.code)
    if not safety.safe:
        return ValidationResult(
            False, safety.errors, source_example_count=len(source_examples)
        )

    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return ValidationResult(
            False, schema.errors, source_example_count=len(source_examples)
        )

    if native_action_tool_enabled(tool):
        labeled_examples = tuple(
            [
                *(
                    (f"source_{index}", example)
                    for index, example in enumerate(source_examples)
                ),
                *(
                    (f"held_out_{index}", example)
                    for index, example in enumerate(held_out_examples)
                ),
                *(
                    (f"negative_{index}", example)
                    for index, example in enumerate(negative_examples)
                ),
            ]
        )
        native_action_errors = _validate_native_action_tool(tool, labeled_examples)
        return ValidationResult(
            not native_action_errors,
            native_action_errors,
            source_example_count=len(source_examples),
            held_out_check_count=len(held_out_examples),
            negative_applicability_count=len(negative_examples),
            runtime_smoke_passed=not native_action_errors,
        )

    errors: list[str] = []
    all_examples = (
        *(
            (f"source_{index}", example)
            for index, example in enumerate(source_examples)
        ),
        *(
            (f"held_out_{index}", example)
            for index, example in enumerate(held_out_examples)
        ),
        *(
            (f"negative_{index}", example)
            for index, example in enumerate(negative_examples)
        ),
    )
    for label, example in all_examples:
        try:
            actual = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
            replay = normalize_generated_tool_output(
                tool, schema.function(**example.inputs), inputs=example.inputs
            )
            expected = normalize_generated_tool_output(
                tool, example.expected, inputs=example.inputs
            )
        except Exception as exc:
            errors.append(f"{label}_error:{type(exc).__name__}:{exc}")
            continue
        if actual != replay:
            errors.append(f"{label}_nondeterministic:{actual!r}!={replay!r}")
        if (
            actual != expected
            and not _benign_negative_abstain_reason_mismatch(label, actual, expected)
            and not _structured_abstention_outputs_match(tool, actual, expected)
        ):
            errors.append(f"{label}_mismatch:{actual!r}!={expected!r}")
        if not _json_serializable(actual):
            errors.append(f"{label}_non_json_serializable_output")

    runtime_smoke_passed, runtime_error = _runtime_smoke(
        tool,
        source_examples[0] if source_examples else None,
    )
    if runtime_error is not None:
        errors.append(runtime_error)

    return ValidationResult(
        not errors,
        tuple(errors),
        source_example_count=len(source_examples),
        held_out_check_count=len(held_out_examples),
        negative_applicability_count=len(negative_examples),
        runtime_smoke_passed=runtime_smoke_passed,
    )
