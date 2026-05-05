"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import re
from collections.abc import Iterable, MutableMapping
from typing import Any, Callable, cast

from sage_ts.evaluation.task_strata import (
    HELPER_TRIGGERS,
    base_task_family,
    classify_task_strata,
)
from sage_ts.generation.tool_spec import ToolFamily, ToolSpec
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.routing_scorer import (
    DEFAULT_MAX_RUNTIME_BUNDLE_SIZE,
    RuntimeRoutingDecision,
    score_registry_entry_for_scenario,
)
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common import tool_conversion
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    get_current_context,
)
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend, get_scrambled_tool_names
from tool_sandbox.common.utils import add_tool_trace

tool_conversion.PYTHON_TO_JSON_TYPES.setdefault("dict", "object")
tool_conversion.PYTHON_TO_JSON_TYPES.setdefault("list", "array")

PYTHON_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
}

OPTIONAL_HELPER_DEFAULTS: dict[str, Any] = {
    "constraints": {},
    "filters": {},
    "required_filters": {},
    "tie_break_fields": [],
}


def _call_path_note(spec: ToolSpec) -> list[str]:
    """General call-path note for any side-effect-preserving prep helper."""
    if not spec.required_original_tool_calls:
        return []
    targets = ", ".join(spec.required_original_tool_calls)
    lines = ["", f"Downstream ToolSandbox tool to preserve: {targets}."]
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if isinstance(output_properties, dict):
        for target in spec.required_original_tool_calls:
            kwargs_key = f"{target}_kwargs"
            if kwargs_key in output_properties:
                lines.extend(
                    [
                        f"Call path: {spec.tool_name}(...) -> {target}(**result['{kwargs_key}']).",
                        f"Do not treat {spec.tool_name} as completing the task; call {target} next when safe.",
                    ]
                )
                return lines
        schema_keys = ", ".join(sorted(output_properties))
        if schema_keys:
            lines.extend(
                [
                    f"Call {spec.tool_name}(...) to compute these reusable fields: {schema_keys}.",
                    f"Then pass the relevant returned fields into {targets}.",
                ]
            )
    lines.extend(
        [
            f"Use this helper instead of manually deriving arguments for {targets}.",
            f"Do not treat {spec.tool_name} as completing the task; call {targets} next when safe.",
        ]
    )
    return lines


def _post_selection_composite_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for helpers that prepare one downstream side effect."""
    input_names = {item.name for item in spec.inputs}
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    if "downstream_tool_name" not in output_properties:
        return []
    if not any(str(key).endswith("_kwargs") for key in output_properties):
        return []

    lines = [
        "",
        "Post-selection usage:",
        "    Use this helper only after the target record has already been",
        " selected from visible ToolSandbox results.",
    ]
    if "selected_record" in input_names:
        lines.extend(
            [
                "    Pass selected_record as the full selected record object from",
                " the previous search/selector result; do not pass a summary string.",
            ]
        )
    if "updates" in input_names:
        lines.extend(
            [
                "    Pass updates as a dict of fields to change. Use {} only when",
                " the downstream action requires no updates, such as remove/delete.",
            ]
        )
    if "action_type" in input_names:
        lines.extend(
            [
                "    Pass action_type as the intended downstream action category",
                " such as modify_contact, remove_reminder, or send_message.",
            ]
        )
    lines.extend(
        [
            f"    Do not call {spec.tool_name} with only action_type or user_intent.",
            "    If selected_record or required update fields are unavailable,",
            " do not call this helper; continue searching, selecting, or ask for",
            " clarification.",
            "    If should_call_tool is true, call the returned downstream_tool_name",
            " with downstream_tool_kwargs next. This helper does not perform the",
            " side effect.",
        ]
    )
    return lines


def _search_filter_action_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for selectors over visible search results."""
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    if "selected_record" not in output_properties:
        return []

    has_downstream_action = "downstream_tool_name" in output_properties
    if has_downstream_action:
        lines = [
            "",
            "Selection/action usage:",
            "    Use this helper after an original search tool returns visible",
            " candidate records and before choosing a target for modify, remove,",
            " reply, send, or another downstream action.",
            "    Pass records as the full list returned by the search tool; do not",
            " summarize or invent records.",
        ]
    else:
        lines = [
            "",
            "Visible-record constraint selection usage:",
            "    Use this helper immediately after an original search tool returns",
            " visible candidate records and the user asks for a field, contact,",
            " message, reminder, or exact target selected by a visible constraint.",
            "    This is useful before answering lookup questions such as phone",
            " number/relationship/sender lookups and before modify/remove/send",
            " actions that need one safe selected record.",
            "    Pass records as the full list returned by the search tool; do not",
            " summarize or invent records.",
            "    Pass field_name as the visible field to match, expected_value as",
            " the user constraint, and return_field as the field needed for the",
            " answer or next ToolSandbox call, such as phone_number, relationship,",
            " person_id, message_id, reminder_id, or id.",
            "    If abstain_reason is empty, use value/selected_record directly",
            " for the final answer or next original ToolSandbox action.",
            "    If abstain_reason is non-empty, do not guess; search further or",
            " ask for clarification before any side-effect action.",
        ]
    input_names = {item.name for item in spec.inputs}
    if "timestamp_key" in input_names:
        lines.extend(
            [
                "    Pass timestamp_key as the visible timestamp field to rank",
                " such as creation_timestamp or reminder_timestamp.",
            ]
        )
    if "selection_mode" in input_names:
        lines.extend(
            [
                "    Pass selection_mode='latest' for newest/most recent/last,",
                " and selection_mode='oldest' for oldest/earliest/next upcoming",
                " when ranking future timestamps from soonest to latest.",
            ]
        )
    if "constraints" in input_names:
        lines.extend(
            [
                "    constraints is optional. Omit it or pass {} when there are",
                " no extra user constraints beyond recency/timestamp/action type.",
            ]
        )
    lines.extend(
        [
            "    If abstain_reason is empty, use selected_record/selected_id for",
            " the next original ToolSandbox action. This helper does not perform",
            " the action.",
            "    If abstain_reason is non-empty, do not guess before a side-effect",
            " action; search further or ask for clarification.",
        ]
    )
    return lines


def _dict_input_keys(entry: RegistryEntry) -> dict[str, tuple[str, ...]]:
    """Return literal dict keys used by generated code as affordance hints."""
    keys_by_input: dict[str, tuple[str, ...]] = {}
    code = entry.tool.code
    for item in entry.tool.spec.inputs:
        if item.annotation != "dict":
            continue
        pattern = rf"{re.escape(item.name)}\[['\"]([^'\"]+)['\"]\]"
        keys = sorted(set(re.findall(pattern, code)))
        if keys:
            keys_by_input[item.name] = tuple(keys)
    return keys_by_input


def _schema_default_value(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return None
    schema_type = schema.get("type")
    if schema_type == "object":
        return {}
    if schema_type == "array":
        return []
    if schema_type == "boolean":
        return False
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "string":
        return ""
    return None


def _missing_argument_abstain_result(entry: RegistryEntry, error: TypeError) -> Any:
    """Return a safe abstain payload for omitted required args, or re-raise."""
    message = str(error)
    if "missing" not in message or "required positional argument" not in message:
        raise error
    output_schema = entry.tool.spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if entry.tool.spec.output_annotation != "dict" or not isinstance(
        output_properties, dict
    ):
        raise error
    if "abstain_reason" not in output_properties:
        raise error

    result = {
        key: _schema_default_value(schema) for key, schema in output_properties.items()
    }
    for key in tuple(result):
        if key.startswith("should_") or key in {"should_call", "should_call_tool"}:
            result[key] = False
    result["abstain_reason"] = "missing_required_helper_inputs"
    return result


def _latest_generated_tool_result_with_key(key: str) -> dict[str, Any] | None:
    """Read the current message tool trace and return the newest result with key."""
    try:
        sandbox = get_current_context().get_database(
            namespace=DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
        )
    except Exception:
        return None
    for row in reversed(sandbox.to_dicts()):
        existing = row.get("tool_trace")
        if existing is None:
            continue
        traces = existing.to_list() if hasattr(existing, "to_list") else list(existing)
        for item in reversed(traces):
            try:
                payload = json.loads(str(item))
            except json.JSONDecodeError:
                continue
            result = payload.get("result")
            if isinstance(result, dict) and key in result:
                return result
    return None


def _latest_single_original_search_record() -> dict[str, Any] | None:
    """Return the newest unambiguous record from an original search tool trace."""
    try:
        sandbox = get_current_context().get_database(
            namespace=DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
        )
    except Exception:
        return None
    for row in reversed(sandbox.to_dicts()):
        existing = row.get("tool_trace")
        if existing is None:
            continue
        traces = existing.to_list() if hasattr(existing, "to_list") else list(existing)
        for item in reversed(traces):
            try:
                payload = json.loads(str(item))
            except json.JSONDecodeError:
                continue
            tool_name = str(payload.get("tool_name", ""))
            if not tool_name.startswith("search_"):
                continue
            result = payload.get("result")
            if (
                isinstance(result, list)
                and len(result) == 1
                and isinstance(result[0], dict)
            ):
                return dict(result[0])
            if isinstance(result, dict):
                return dict(result)
    return None


def _latest_original_tool_payload(
    tool_names: Iterable[str],
) -> dict[str, Any] | None:
    """Return the newest dict payload from one of the named original tools."""
    wanted = set(tool_names)
    if not wanted:
        return None
    try:
        sandbox = get_current_context().get_database(
            namespace=DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
        )
    except Exception:
        return None
    for row in reversed(sandbox.to_dicts()):
        existing = row.get("tool_trace")
        if existing is None:
            continue
        traces = existing.to_list() if hasattr(existing, "to_list") else list(existing)
        for item in reversed(traces):
            try:
                payload = json.loads(str(item))
            except json.JSONDecodeError:
                continue
            if str(payload.get("tool_name", "")) not in wanted:
                continue
            result = payload.get("result")
            if isinstance(result, dict):
                return dict(result)
            if (
                isinstance(result, list)
                and len(result) == 1
                and isinstance(result[0], dict)
            ):
                return dict(result[0])
    return None


def _with_chained_visible_payload_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Autofill low-risk scalar-extraction helpers from prior raw tool output."""
    spec = entry.tool.spec
    if spec.family != ToolFamily.DERIVED_VALUE_CALCULATOR:
        return kwargs
    if len(spec.inputs) != 1 or spec.inputs[0].annotation != "dict":
        return kwargs
    input_name = spec.inputs[0].name
    if kwargs.get(input_name):
        return kwargs
    payload = _latest_original_tool_payload(spec.required_original_tool_calls)
    if payload is None and spec.required_original_tool_calls:
        return kwargs
    if payload is None:
        payload = _latest_single_original_search_record()
    if not isinstance(payload, dict) or not payload:
        return kwargs
    updated = dict(kwargs)
    updated[input_name] = payload
    return updated


def _with_chained_post_selection_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Autofill mechanical chaining args from prior traces when safe."""
    spec = entry.tool.spec
    input_names = {item.name for item in spec.inputs}
    if spec.family != ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        return kwargs
    if "selected_record" not in input_names:
        return kwargs

    updated = dict(kwargs)
    if not updated.get("selected_record"):
        latest_selection = _latest_generated_tool_result_with_key("selected_record")
        selected_record = (
            latest_selection.get("selected_record")
            if latest_selection is not None
            else None
        )
        if not isinstance(selected_record, dict) or not selected_record:
            selected_record = _latest_single_original_search_record()
        if isinstance(selected_record, dict) and selected_record:
            updated["selected_record"] = selected_record
    action_type = str(updated.get("action_type", "")).lower()
    if "updates" in input_names and "updates" not in updated:
        if action_type.startswith(("remove", "delete")):
            updated["updates"] = {}
    return updated


def _with_optional_helper_defaults(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Fill safe defaults for optional filter/list inputs omitted by the model."""
    updated = dict(kwargs)
    for item in entry.tool.spec.inputs:
        if item.name in updated:
            continue
        if item.name not in OPTIONAL_HELPER_DEFAULTS:
            continue
        description = item.description.lower()
        if "optional" not in description and item.name not in {
            "constraints",
            "required_filters",
            "tie_break_fields",
        }:
            continue
        updated[item.name] = copy.deepcopy(OPTIONAL_HELPER_DEFAULTS[item.name])
    return updated


def _missing_modify_update_abstain_result(
    entry: RegistryEntry, kwargs: dict[str, Any]
) -> Any:
    """Avoid turning a mechanically filled selected record into unsafe no-op modify."""
    if entry.tool.spec.family != ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        return None
    input_names = {item.name for item in entry.tool.spec.inputs}
    if "updates" not in input_names:
        return None
    action_type = str(kwargs.get("action_type", "")).lower()
    if not action_type.startswith(("modify", "update")):
        return None
    updates = kwargs.get("updates")
    if isinstance(updates, dict) and updates:
        return None
    output_schema = entry.tool.spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if (
        not isinstance(output_properties, dict)
        or "abstain_reason" not in output_properties
    ):
        return None
    result = {
        key: _schema_default_value(schema) for key, schema in output_properties.items()
    }
    for key in tuple(result):
        if key.startswith("should_") or key in {"should_call", "should_call_tool"}:
            result[key] = False
    result["abstain_reason"] = "missing_required_update_fields"
    return result


def _google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    description = spec.description
    if spec.tool_name in {"next_service_tool_call", "recover_from_tool_error"}:
        description = (
            f"{description} Use only for the single service you are actively "
            "trying to change. Do not call this helper for multiple alternative "
            "services in parallel. Use this helper only to prepare the next "
            "original ToolSandbox side-effect call. After calling it, execute "
            "the returned original ToolSandbox tool; do not treat the helper "
            "itself as completing the task."
        )
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        description = (
            f"{description} Call this helper when the requested action appears "
            "blocked by a visible service, device-state, or dependency "
            "precondition. If it returns should_call=True, execute the returned "
            "original ToolSandbox tool name with the returned arguments next. "
            "The helper plans the next precondition call; it does not perform "
            "the side effect or complete the task by itself."
        )
    dict_input_keys = _dict_input_keys(entry)
    lines = [description, "", "Args:"]
    for item in spec.inputs:
        description = item.description
        if item.name in dict_input_keys:
            description = (
                f"{description} Expected visible keys: "
                f"{', '.join(dict_input_keys[item.name])}."
            )
        lines.append(f"    {item.name}: {description}")
    lines.extend(["", "Returns:", f"    {spec.output_annotation}"])
    if spec.positive_triggers:
        lines.extend(["", "Use when:"])
        for trigger in spec.positive_triggers:
            lines.append(f"    - {trigger}")
    if spec.negative_triggers:
        lines.extend(["", "Do not use when:"])
        for trigger in spec.negative_triggers:
            lines.append(f"    - {trigger}")
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
        lines.extend(
            [
                "",
                "Dependency/precondition usage:",
                "    Call this helper when the requested action appears blocked",
                " by a visible service, device-state, or dependency precondition.",
                "    Provide only visible state and the target action; do not",
                " invent hidden service or device state.",
                "    If the helper returns should_call=True, execute the returned original ToolSandbox tool name with the returned arguments next.",
                "    The helper only plans the next precondition call; it does not perform the side effect or complete the user task by itself.",
                "    Do not call it when state is already ready, inputs are",
                " insufficient or ambiguous, or the task is unrelated to service",
                " or dependency preconditions.",
            ]
        )
        if spec.canonical_route_substitution_risk.strip().lower() != "none":
            lines.extend(
                [
                    "    This helper may substitute for an expected canonical",
                    " intermediate route. Preserve final state and side effects;",
                    " canonical-route impact is reported separately.",
                ]
            )
    if spec.tool_name == "next_service_tool_call":
        lines.extend(
            [
                "",
                "Usage:",
                "    Use only for the single service you are actively trying to"
                " change.",
                "    Do not call this helper for multiple alternative services in"
                " parallel.",
                "    Execute only the returned ToolSandbox tool call for the"
                " chosen target service.",
                "    If the target service succeeds, answer only about that final"
                " target state unless the user asked to broaden scope.",
            ]
        )
    if spec.tool_name == "recover_from_tool_error":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this helper immediately after a ToolSandbox tool returns",
                " a PermissionError or ConnectionError about service state.",
                "    Then execute the returned original ToolSandbox tool name with",
                " the returned JSON arguments.",
                "    This helper prepares the next legal call; it does not perform",
                " the side effect itself.",
            ]
        )
    if spec.tool_name == "prepare_reminder_creation_args":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this helper as the LAST prep step immediately before",
                " add_reminder once reminder content and time are already resolved,",
                " or once relative time fields are complete.",
                "    Call path: prepare_reminder_creation_args(...) →",
                " add_reminder(**result['add_reminder_kwargs'])",
                "    NEVER call datetime_info_to_timestamp and this helper in the",
                " same turn. If you need a timestamp first, call",
                " datetime_info_to_timestamp, wait for the result, then call this",
                " helper in a later turn.",
                "    If you have already called datetime_info_to_timestamp and have",
                " a timestamp, pass it as resolved_reminder_timestamp and set",
                " time_fields_complete=False.",
                "    For plain relative times ('tomorrow at 5 PM', 'next Friday'),",
                " set time_fields_complete=True and supply day_offset, hour, minute,",
                " local_utc_offset_hours only when that offset is explicitly known.",
                "    Set location_required=True only when the user explicitly requires",
                " a location on the reminder. A mentioned location is not required.",
                "    If location_available=False or lookup failed and location is not",
                " required, set latitude=0.0, longitude=0.0 and proceed without coords.",
                "    If the user is still choosing or refining the location, set",
                " location_refinement_in_progress=True so the helper abstains.",
                "    If result['should_call_add_reminder'] is True, immediately call",
                " add_reminder(**result['add_reminder_kwargs']) unchanged.",
                "    If result['should_call_add_reminder'] is False, check",
                " result['abstain_reason'] before deciding next action.",
            ]
        )
    elif spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR and len(spec.inputs) == 1:
        required = ", ".join(spec.required_original_tool_calls)
        input_name = spec.inputs[0].name
        if required:
            lines.extend(
                [
                    "",
                    "Deterministic extraction usage:",
                    f"    First call the original ToolSandbox tool: {required}.",
                    f"    Then call {spec.tool_name} with {input_name} set to the",
                    " full dict/list item returned by that original tool.",
                    "    If the prior payload is visible and the model omits this",
                    " argument, SAGE may safely autofill it from the latest matching",
                    " original tool trace.",
                    "    Use the helper result for the final answer; it does not",
                    " perform side effects or replace the original lookup call.",
                ]
            )
    elif spec.required_original_tool_calls:
        if spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
            lines.extend(_search_filter_action_usage_note(spec))
        if spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
            lines.extend(_post_selection_composite_usage_note(spec))
        # General call-path note for any other side-effect-preserving prep helper
        lines.extend(_call_path_note(spec))
    return "\n".join(lines)


def compile_toolsandbox_tool(entry: RegistryEntry) -> Callable[..., Any]:
    """Compile an accepted registry entry into a ToolSandbox-visible callable."""
    return _compile_toolsandbox_tool(entry, on_reuse=None)


def _compile_toolsandbox_tool(
    entry: RegistryEntry,
    on_reuse: Callable[[str], None] | None,
) -> Callable[..., Any]:
    if entry.retired or not entry.validation.accepted:
        raise ValueError(f"registry entry is not active: {entry.tool.spec.tool_name}")
    if not has_current_validation_proof(entry):
        raise ValueError(
            "registry entry lacks current validation proof: "
            f"{entry.tool.spec.tool_name}"
        )

    compiled = compile_generated_tool(entry.tool)
    if compiled.function is None:
        raise ValueError(
            f"registry entry failed schema compilation: {entry.tool.spec.tool_name}"
        )

    raw_fn = compiled.function

    # ToolSandbox expects every successful tool call to append a tool_trace.
    # We keep this as a plain closure instead of register_as_tool so injected
    # generated helpers stay pickle-safe for scenario execution.
    _tool_name = entry.tool.spec.tool_name
    _inner = raw_fn

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        kwargs = _with_chained_visible_payload_arguments(entry, kwargs)
        kwargs = _with_chained_post_selection_arguments(entry, kwargs)
        kwargs = _with_optional_helper_defaults(entry, kwargs)
        missing_update_result = _missing_modify_update_abstain_result(entry, kwargs)
        if missing_update_result is not None:
            add_tool_trace(_wrapped, missing_update_result, *args, **kwargs)
            if on_reuse is not None:
                on_reuse(_tool_name)
            return missing_update_result
        try:
            result = _inner(*args, **kwargs)
        except TypeError as error:
            result = _missing_argument_abstain_result(entry, error)
        result = normalize_generated_tool_output(entry.tool, result, inputs=kwargs)
        add_tool_trace(_wrapped, result, *args, **kwargs)
        if on_reuse is not None:
            on_reuse(_tool_name)
        return result

    _wrapped.__name__ = _tool_name
    _wrapped.__doc__ = raw_fn.__doc__
    fn = _wrapped

    # Build annotations using Python type objects.
    annotations: dict[str, Any] = {}
    for item in entry.tool.spec.inputs:
        if item.annotation in PYTHON_TYPES:
            annotations[item.name] = PYTHON_TYPES[item.annotation]
    if entry.tool.spec.output_annotation in PYTHON_TYPES:
        annotations["return"] = PYTHON_TYPES[entry.tool.spec.output_annotation]
    fn.__annotations__ = annotations
    fn.__doc__ = _google_docstring(entry)
    fn.__module__ = "sage_ts.generated_tools"

    # Set ToolSandbox tool metadata directly — avoids the register_as_tool
    # decorator which wraps the function with new_context_with_attribute, a
    # contextvars-backed context manager whose internals are not picklable by dill.
    fn.is_tool = True  # type: ignore[attr-defined]
    fn.visible_to = (RoleType.AGENT,)  # type: ignore[attr-defined]
    fn.backend = ToolBackend.DEFAULT  # type: ignore[attr-defined]

    # Rebuild the inspect.Signature so the agent role can introspect parameters.
    sig = inspect.signature(raw_fn)
    signature_parameters = []
    for p in sig.parameters.values():
        replacement = p.replace(annotation=annotations.get(p.name, p.annotation))
        if (
            p.default is inspect.Parameter.empty
            and p.name in OPTIONAL_HELPER_DEFAULTS
            and any(item.name == p.name for item in entry.tool.spec.inputs)
        ):
            replacement = replacement.replace(
                default=copy.deepcopy(OPTIONAL_HELPER_DEFAULTS[p.name])
            )
        signature_parameters.append(replacement)
    fn.__signature__ = sig.replace(  # type: ignore[attr-defined]
        parameters=signature_parameters,
        return_annotation=annotations.get("return", inspect.Parameter.empty),
    )
    return fn


def inject_registry_tools_into_context(
    context: ExecutionContext,
    entries: Iterable[RegistryEntry],
    *,
    on_reuse: Callable[[str], None] | None = None,
) -> list[str]:
    """Inject accepted generated helpers into a ToolSandbox execution context."""
    injected: list[str] = []
    seen_tool_names: set[str] = set()
    compiled_by_name: dict[str, Callable[..., Any]] = {}
    for entry in entries:
        tool_name = entry.tool.spec.tool_name
        if tool_name in seen_tool_names or tool_name in context.name_to_tool:
            continue
        try:
            compiled_tool = _compile_toolsandbox_tool(entry, on_reuse)
        except Exception:
            continue
        compiled_by_name[tool_name] = compiled_tool
        seen_tool_names.add(tool_name)
        console_locals = cast(
            MutableMapping[str, Any],
            context.interactive_console.locals,
        )
        console_locals[tool_name] = compiled_tool
        injected.append(tool_name)

    if injected:
        # OpenAI receives tools in dict insertion order. Put retained SAGE tools
        # first so transfer runs test whether the model will adopt them when useful.
        context.name_to_tool = {**compiled_by_name, **context.name_to_tool}
        if context.tool_allow_list is not None:
            context.tool_allow_list = injected + [
                tool for tool in context.tool_allow_list if tool not in set(injected)
            ]
        context._actual_to_scrambled_tool_name = get_scrambled_tool_names(
            context.name_to_tool.values()
        )
        context._scrambled_to_actual_tool_name = {
            value: key for key, value in context._actual_to_scrambled_tool_name.items()
        }
    return injected


def _trigger_based_visibility(
    entry: RegistryEntry,
    scenario_name: str,
) -> tuple[bool, str] | None:
    """Check positive/negative trigger tokens against scenario_name.

    Returns a visibility tuple if a trigger matches, or None if no match.
    Called as a supplementary fallback after all hardcoded route checks.
    """
    name_lower = scenario_name.lower()
    spec = entry.tool.spec
    if spec.positive_triggers:
        for token in spec.positive_triggers:
            if token.lower() in name_lower:
                return True, "positive_trigger_match"
    if spec.negative_triggers:
        for token in spec.negative_triggers:
            if token.lower() in name_lower:
                return False, "negative_trigger_suppressed"
    return None


def registry_entry_visibility_reason(
    entry: RegistryEntry,
    scenario_name: str | None,
) -> tuple[bool, str]:
    """Return whether a retained helper should be exposed and why."""
    if entry.retired or not entry.validation.accepted:
        return False, "registry_entry_not_active"
    if not has_current_validation_proof(entry):
        return False, "legacy_validation_missing_current_proof"

    if not scenario_name:
        # Allow explicit global-safe tools; suppress everything else.
        if (
            "global" in entry.tool.spec.positive_triggers
            or "all_scenarios" in entry.tool.spec.positive_triggers
        ):
            return True, "global_safe_explicit"
        return False, "missing_scenario_name_suppressed"

    generic_route = score_registry_entry_for_scenario(entry, scenario_name)
    if generic_route.status in {"shown", "hidden"}:
        return generic_route.visible, generic_route.reason

    name = scenario_name.lower()
    tool_name = entry.tool.spec.tool_name
    scenario_strata = set(classify_task_strata(name))
    is_insufficient = "insufficient_information" in name

    if tool_name == "relative_day_time_to_timestamp":
        if name.startswith("modify_reminder_with_recency_latest"):
            return True, "relative_time_modify_latest_reminder"
        if name.startswith("add_reminder_content_and_week_delta"):
            return True, "relative_time_add_reminder_week_delta"
        return False, "relative_time_requires_explicit_relative_datetime_task"

    if tool_name == "recency_to_timestamp_bounds":
        bounded_recency = any(
            token in name for token in ("yesterday", "today", "upcoming")
        )
        if (
            "insufficient_information" not in name
            and name.startswith("search_reminder_with_creation_recency_")
            and bounded_recency
        ):
            return True, "recency_bounds_creation_search_task"
        if name.startswith("search_message_with_recency_") and bounded_recency:
            return True, "recency_bounds_search_task"
        return False, "recency_bounds_requires_bounded_recency_task"

    if tool_name == "resolve_search_window_or_bounds":
        if is_insufficient:
            return False, "search_window_bounds_suppressed_for_insufficient_information"
        if name.startswith("search_reminder_with_creation_recency_") and any(
            token in name for token in ("yesterday", "today")
        ):
            return True, "search_window_bounds_creation_recency_task"
        if name.startswith("search_reminder_with_recency_") and any(
            token in name for token in ("yesterday", "today", "later_today", "upcoming")
        ):
            return True, "search_window_bounds_due_recency_task"
        if name.startswith(
            (
                "modify_reminder_with_recency_latest",
                "remove_reminder_with_recency_latest",
            )
        ):
            return True, "search_window_bounds_reminder_recency_action_task"
        if name.startswith(
            (
                "search_message_with_recency_latest",
                "search_message_with_recency_oldest",
            )
        ):
            return True, "search_window_bounds_message_recency_task"
        return False, "search_window_bounds_requires_bounded_search_task"

    if tool_name == "days_between_timestamps":
        if name.startswith("find_days_till_holiday"):
            return True, "calendar_day_distance_task"
        return False, "calendar_day_distance_requires_holiday_task"

    if tool_name == "prepare_reminder_arguments_with_optional_location":
        if is_insufficient:
            return (
                False,
                "reminder_argument_prep_suppressed_for_insufficient_information",
            )
        if "low_battery" in name:
            return (
                False,
                "reminder_argument_prep_suppressed_for_service_precondition_task",
            )
        if (
            name.startswith("add_reminder_content_and_")
            and "_time" in name
            and "_location" in name
        ):
            return True, "reminder_argument_prep_add_reminder_time_location_task"
        return False, "reminder_argument_prep_requires_add_reminder_time_location_task"

    if tool_name == "prepare_reminder_creation_args":
        if is_insufficient:
            return False, "reminder_creation_args_suppressed_insufficient_information"
        # General reminder-creation detection: scenario involves adding/creating a
        # reminder and is not a modify/search/update/delete task.
        creation_signals = ("add_reminder", "remind", "create_reminder", "set_reminder")
        suppress_signals = (
            "modify_reminder",
            "search_reminder",
            "update_reminder",
            "delete_reminder",
        )
        if any(token in name for token in suppress_signals):
            return False, "reminder_creation_args_suppressed_non_creation_task"
        if (
            name.startswith("add_reminder_content_and_week_delta_and_time")
            and "_location" not in name
        ):
            return (
                False,
                "reminder_creation_args_suppressed_relative_no_location_lane",
            )
        if any(token in name for token in creation_signals):
            return True, "reminder_creation_args_narrow_creation_task"
        # No creation signal detected — hide (safe default).
        return False, "reminder_creation_args_no_creation_signal"

    if tool_name == "message_search_time_window":
        return (
            False,
            "message_search_window_suppressed_bounds_only_low_value_mechanism",
        )

    if tool_name == "message_search_args_for_contact":
        return (
            False,
            "message_search_args_suppressed_schema_requires_preexisting_contact",
        )

    if entry.tool.spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        if tool_name == "select_contact_by_constraint":
            return False, "contact_selector_suppressed_visible_not_called_pollution"
        if tool_name == "select_contact_field_by_constraint":
            return (
                False,
                "contact_field_selector_suppressed_visible_not_called_pollution",
            )
        if tool_name == "select_latest_record_by_timestamp":
            if "insufficient_information" not in name and name.startswith(
                ("modify_contact_with_message_recency",)
            ):
                return True, "latest_message_record_selection_required"
            return False, "latest_record_suppressed_outside_message_search"
        if tool_name == "select_record_by_timestamp_extreme":
            if "insufficient_information" not in name and name.startswith(
                (
                    "modify_contact_with_message_recency",
                    "remove_reminder_with_recency_latest",
                    "search_message_with_recency_latest",
                    "search_message_with_recency_oldest",
                )
            ):
                return True, "message_timestamp_extreme_selection_required"
            return False, "timestamp_extreme_suppressed_outside_message_ranking_tasks"
        if tool_name == "select_self_message_by_timestamp":
            return False, "self_message_selector_suppressed_empty_input_misuse"
        return _provisional_birth_family_visibility(entry, name)

    if entry.tool.spec.family == ToolFamily.CANONICALIZER:
        return _provisional_birth_family_visibility(entry, name)

    if tool_name == "extract_stock_symbol":
        if "insufficient_information" not in name and name.startswith(
            "find_stock_symbol_with_company_name"
        ):
            return True, "stock_symbol_extraction_task"
        return False, "stock_symbol_requires_stock_lookup_task"

    # Supplementary trigger-based fallback: checked after all hardcoded routes.
    trigger_result = _trigger_based_visibility(entry, name)
    if trigger_result is not None:
        return trigger_result

    if entry.tool.spec.family != ToolFamily.STATE_PRECONDITION_HELPER:
        return _provisional_birth_family_visibility(entry, name)

    if tool_name == "next_service_enablement_action":
        return False, "state_helper_suppressed_trace_mismatch_use_tool_call_variant"

    if tool_name == "next_service_tool_call":
        if "insufficient_information" in name:
            return False, "state_helper_suppressed_for_insufficient_information"
        direct_service_prefixes = (
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
        )
        if name.startswith(direct_service_prefixes):
            return True, "state_tool_call_direct_service_precondition_task"
        if "low_battery_mode" in name:
            return True, "state_tool_call_downstream_service_precondition_task"
        return False, "state_helper_requires_direct_service_precondition_task"

    if tool_name == "recover_from_tool_error":
        if "insufficient_information" in name:
            return False, "error_recovery_suppressed_for_insufficient_information"
        if "low_battery_mode" in name:
            return True, "error_recovery_low_battery_service_precondition_task"
        return False, "error_recovery_requires_service_precondition_task"

    return False, "state_helper_requires_direct_service_state_task"


def route_registry_entries(
    entries: dict[str, RegistryEntry],
    scenario_name: str | None,
    *,
    max_bundle_size: int = DEFAULT_MAX_RUNTIME_BUNDLE_SIZE,
    available_base_tools: set[str] | None = None,
) -> tuple[list[RegistryEntry], dict[str, RuntimeRoutingDecision]]:
    """Select a bounded runtime helper bundle and explain each routing decision."""
    decisions: dict[str, RuntimeRoutingDecision] = {}
    visible: list[tuple[int, str, RegistryEntry]] = []
    generic_hard_blocks = {
        "blocked_by_negative_trigger",
        "blocked_by_visible_not_called_adoption_risk",
        "recency_action_selector_requires_recency_action_task",
        "side_effect_selector_suppressed_for_insufficient_information",
        "side_effect_composite_suppressed_for_insufficient_information",
        "post_selection_composite_requires_downstream_action_task",
    }
    for tool_name, entry in sorted(entries.items()):
        generic = score_registry_entry_for_scenario(entry, scenario_name)
        is_visible, reason = registry_entry_visibility_reason(entry, scenario_name)
        status = "shown" if is_visible else "hidden"
        score = generic.score
        if generic.status == "hidden" and generic.reason in generic_hard_blocks:
            is_visible = False
            status = "hidden"
            reason = generic.reason
        downstream_tools = set(entry.tool.spec.required_original_tool_calls)
        requires_any_downstream = False
        output_schema = entry.tool.spec.output_schema or {}
        output_props = output_schema.get("properties", {})
        if isinstance(output_props, dict):
            tool_name_schema = output_props.get("tool_name", {})
            if isinstance(tool_name_schema, dict):
                emitted = {
                    str(item) for item in tool_name_schema.get("enum", ()) if str(item)
                }
                if emitted:
                    downstream_tools = emitted
                    requires_any_downstream = True
            if "downstream_tool_name" in output_props and (
                entry.tool.spec.family
                in {
                    ToolFamily.COMPOSITE_WORKFLOW_HELPER,
                    ToolFamily.SEARCH_FILTER_RANKING_HELPER,
                }
            ):
                # Action-target selectors and side-effect argument preparers return
                # one downstream ToolSandbox action, not all actions named in
                # their preservation contract. Requiring every preserved action to
                # be available hides valid candidate tools on narrower per-scenario
                # allow-lists.
                downstream_tools = set(entry.tool.spec.preserves_side_effect_tools)
                requires_any_downstream = True
        if not downstream_tools:
            downstream_tools = set(entry.tool.spec.preserves_side_effect_tools)
        if entry.tool.spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
            producer_tools = {
                tool_name
                for tool_name in downstream_tools
                | set(entry.tool.spec.preserves_side_effect_tools)
                if tool_name.startswith(("search_", "get_", "find_"))
            }
            if producer_tools:
                downstream_tools = producer_tools
                requires_any_downstream = True
        if is_visible and available_base_tools is not None and downstream_tools:
            if requires_any_downstream:
                missing = (
                    downstream_tools
                    if not downstream_tools & available_base_tools
                    else set()
                )
            else:
                missing = downstream_tools - available_base_tools
            if missing:
                is_visible = False
                status = "hidden"
                reason = "blocked_by_missing_downstream_original_tool"
        forced_tool = os.environ.get("SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "").strip()
        if (
            forced_tool
            and tool_name == forced_tool
            and not is_visible
            and (
                reason == "blocked_by_visible_not_called_adoption_risk"
                or "visible_not_called_pollution" in reason
            )
        ):
            is_visible = True
            status = "shown"
            reason = "diagnostic_force_overrode_adoption_risk"
        if is_visible:
            visible.append((score, tool_name, entry))
        decisions[tool_name] = RuntimeRoutingDecision(
            tool_name=tool_name,
            visible=is_visible,
            status=status,
            reason=reason,
            score=score,
            matched_positive_triggers=generic.matched_positive_triggers,
            matched_negative_triggers=generic.matched_negative_triggers,
            matched_task_families=generic.matched_task_families,
            fair_chance_candidate=generic.fair_chance_candidate,
            fair_chance_reason=generic.fair_chance_reason,
        )
    visible.sort(key=lambda item: (-item[0], item[1]))
    selected = visible[:max_bundle_size]
    for score, tool_name, _entry in visible[max_bundle_size:]:
        decisions[tool_name] = RuntimeRoutingDecision(
            tool_name=tool_name,
            visible=False,
            status="deprioritized",
            reason="blocked_by_context_budget",
            score=score,
        )
    return [entry for _score, _tool_name, entry in selected], decisions


def retained_tool_visibility_policy_digest() -> str:
    """Return a digest that changes when retained-tool routing policy changes."""
    payload = {
        "policy_version": "v4_failure_driven_strata_shared_birth",
        "helper_triggers": HELPER_TRIGGERS,
        "visibility_source": inspect.getsource(registry_entry_visibility_reason),
        "provisional_source": inspect.getsource(_provisional_birth_family_visibility),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _provisional_birth_family_visibility(
    entry: RegistryEntry,
    normalized_scenario_name: str,
) -> tuple[bool, str]:
    """Expose unknown helpers by task stratum before falling back to birth family."""
    scenario_strata = set(classify_task_strata(normalized_scenario_name))
    tool_name = entry.tool.spec.tool_name
    trigger_strata = set(HELPER_TRIGGERS.get(tool_name, ()))
    if trigger_strata and scenario_strata & trigger_strata:
        return True, "provisional_helper_trigger_stratum_visibility"

    family_strata = {
        ToolFamily.CANONICALIZER: {
            "temporal_reminder_date_canonicalization",
            "holiday_calendar_business_day_logic",
        },
        ToolFamily.DERIVED_VALUE_CALCULATOR: {
            "temporal_reminder_date_canonicalization",
            "record_filtering_ranking_latest_selection",
            "holiday_calendar_business_day_logic",
            "contact_message_search_disambiguation",
            "stock_market_numeric_normalization",
        },
        ToolFamily.SEARCH_FILTER_RANKING_HELPER: {
            "contact_message_search_disambiguation",
            "record_filtering_ranking_latest_selection",
        },
        ToolFamily.STATE_PRECONDITION_HELPER: {
            "direct_state_precondition_service_enablement",
        },
        ToolFamily.COMPOSITE_WORKFLOW_HELPER: {
            "generic_multi_tool_composition",
        },
        ToolFamily.VALIDATION_ABSTENTION_HELPER: {
            "insufficient_information_clarification",
        },
    }.get(entry.tool.spec.family, set())
    birth_scenario = (entry.birth_scenario or "").lower()
    if birth_scenario:
        birth_strata = set(classify_task_strata(birth_scenario))
        shared_family_strata = scenario_strata & birth_strata & family_strata
        if shared_family_strata:
            return True, "provisional_shared_birth_stratum_visibility"

    if birth_scenario and base_task_family(birth_scenario) == base_task_family(
        normalized_scenario_name
    ):
        return True, "provisional_same_birth_family_visibility"
    return False, "unknown_helper_requires_visibility_policy"


def registry_entry_matches_scenario(
    entry: RegistryEntry,
    scenario_name: str | None,
) -> bool:
    """Return whether a retained helper should be exposed for this scenario."""
    return registry_entry_visibility_reason(entry, scenario_name)[0]


def with_registry_tools(
    scenario: Scenario,
    store: RegistryStore,
    *,
    on_reuse: Callable[[str], None] | None = None,
    scenario_name: str | None = None,
) -> Scenario:
    """Return a scenario copy whose starting context includes registry tools."""
    scenario_copy = copy.deepcopy(scenario)
    available_base_tools = set(
        scenario_copy.starting_context.get_available_tools(scrambling_allowed=False)
    )
    entries, _decisions = route_registry_entries(
        store.load_entries(),
        scenario_name,
        available_base_tools=available_base_tools,
    )
    inject_registry_tools_into_context(
        scenario_copy.starting_context,
        entries,
        on_reuse=on_reuse,
    )
    return scenario_copy
