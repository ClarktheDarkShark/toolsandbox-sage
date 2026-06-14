"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import re
from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path
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
    _is_insufficient_information_guard,
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
    "contact_name": "",
    "name": "",
    "phone_number": "",
    "default_country_code": "1",
    "email": "",
    "relationship": "",
    "target_field": "",
    "new_value": "",
    "message_text": "",
    "record_id": "",
    "person_id": "",
    "resolved_reminder_timestamp": None,
    "current_timestamp": None,
    "day_offset": None,
    "hour": None,
    "minute": None,
    "local_utc_offset_hours": None,
    "location_requested": False,
    "location_required": False,
    "location_available": False,
    "latitude": None,
    "longitude": None,
    "location_lookup_failed": False,
    "current_datetime_info": {},
}

DIRECT_STATUS_LOOKUP_ENV = "SAGE_ENABLE_DIRECT_STATUS_LOOKUP_TOOL"
DISABLE_SCENARIO_NAME_ROUTING_ENV = "SAGE_DISABLE_SCENARIO_NAME_ROUTING"
SCENARIO_METADATA_POLICY_ENV = "SAGE_SCENARIO_METADATA_POLICY"


def _direct_status_lookup_enabled() -> bool:
    raw = os.environ.get(DIRECT_STATUS_LOOKUP_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off", "disabled"}


def _scenario_name_routing_disabled() -> bool:
    raw = os.environ.get(DISABLE_SCENARIO_NAME_ROUTING_ENV, "").strip().lower()
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    policy = os.environ.get(SCENARIO_METADATA_POLICY_ENV, "").strip().lower()
    return policy in {
        "visible_context",
        "visible-context",
        "visible",
        "no_scenario_names",
        "no-scenario-names",
    }


SETTING_SETTER_TOOL_NAMES = {
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
}

SETTING_STATE_LABELS = {
    "set_cellular_service_status": "cellular service",
    "set_location_service_status": "location service",
    "set_low_battery_mode_status": "low battery mode",
    "set_wifi_status": "wifi",
}

BIRTH_SCENARIO_FAIR_CHANCE_ENV = "SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE"
GENERATED_TOOL_DOCSTRING_MODE_ENV = "SAGE_GENERATED_TOOL_DOCSTRING_MODE"
MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE_ENV = (
    "SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE"
)


def _birth_scenario_fair_chance_enabled() -> bool:
    return os.environ.get(BIRTH_SCENARIO_FAIR_CHANCE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _generated_tool_docstring_mode() -> str:
    raw = os.environ.get(GENERATED_TOOL_DOCSTRING_MODE_ENV, "full").strip().lower()
    if raw in {"nano", "min", "lowest"}:
        return "nano"
    if raw in {"micro", "tiny", "schema_only", "schema-only", "small"}:
        return "micro"
    if raw in {"ultra", "lean", "low_token", "low-token", "efficient"}:
        return "ultra"
    if raw in {"compact", "minimal", "clean", "primary"}:
        return "compact"
    return "full"


def _compact_text(text: object, *, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _runtime_generated_tool_bundle_size(default: int) -> int:
    raw = os.environ.get(MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE_ENV, "").strip()
    if not raw:
        return default
    try:
        return max(1, min(default, int(raw)))
    except ValueError:
        return default


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


def _lookup_query_planner_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for helpers that prepare lookup/search kwargs."""
    input_names = {item.name for item in spec.inputs}
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    search_kwargs_keys = [
        str(key)
        for key in output_properties
        if str(key).startswith(("search_", "find_", "get_"))
        and str(key).endswith("_kwargs")
    ]
    if not search_kwargs_keys:
        return []
    if {"records", "candidates", "contact_record"} & input_names:
        return []
    scalar_inputs = sorted(input_names)
    lines = [
        "",
        "Lookup-query planner usage:",
        "    Use this helper before the original lookup/search tool when the",
        " user supplied scalar constraints and the task is to retrieve a",
        " specific field from a contact, message, reminder, or record, or to",
        " locate the target record for a later preserved side-effect action.",
        f"    Pass visible scalar inputs such as {', '.join(scalar_inputs)};",
        " omit unknown optional fields rather than inventing them.",
        "    If the helper returns should_call_search_contacts or",
        " should_call_tool true, call the returned original ToolSandbox search",
        " kwargs next exactly as returned; do not add optional filters such as",
        " is_self, sender id, recipient id, or unrelated status fields unless",
        " they came from the helper or visible tool output.",
        "    Then answer from the returned record, use a visible post-search",
        " extractor, or use a visible post-selection action helper before",
        " calling the original side-effect tool.",
        "    For contact removal/update target lookup, requested_field may be",
        " person_id because the downstream original contact action needs that",
        " stable id.",
        "    This helper does not execute the lookup and does not complete a",
        " final side-effect action.",
        "    If abstain_reason is non-empty, do not guess; ask for",
        " clarification or use the ordinary ToolSandbox route.",
    ]
    if "selected_record" in input_names:
        lines.extend(
            [
                "    If the helper also accepts selected_record and an original",
                " search returns exactly one visible record for an answer-only",
                " task, call the helper again with that selected_record to obtain",
                " answer_value or final_answer_recommendation before responding.",
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
    if "selected_record" not in input_names and "records" not in input_names:
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


def _message_counterparty_search_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for current-user message counterparty search planners."""
    input_names = {item.name for item in spec.inputs}
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    if not {
        "message_direction",
        "selection_mode",
        "self_person_id",
    }.issubset(input_names):
        return []
    if not {
        "search_contacts_kwargs",
        "search_messages_kwargs",
    }.issubset(output_properties):
        return []
    return [
        "",
        "Message-counterparty search usage:",
        "    Use this helper before manual message search when a task identifies",
        " a contact or answer target by messages involving the current user.",
        "    First call it with message_direction sent or received and",
        " selection_mode latest/oldest. Common aliases such as outgoing/from_me",
        " and incoming/to_me are accepted, but sent/received are preferred. Leave",
        " self_person_id blank if it is not yet visible.",
        "    If it returns should_call_search_contacts true, call original",
        " search_contacts with search_contacts_kwargs exactly as returned.",
        "    Then call this helper again with self_person_id copied from the",
        " visible self contact record's person_id.",
        "    If it returns should_call_search_messages true, call original",
        " search_messages with search_messages_kwargs exactly as returned.",
        "    After messages are visible, use a generated selector/action helper",
        " such as select_message_counterparty_for_contact_update before the",
        " original modify_contact call.",
        "    The helper only prepares lookup kwargs; it does not search, select,",
        " or modify contacts by itself.",
    ]


def _direct_scalar_action_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for direct scalar side-effect argument helpers."""
    input_names = {item.name for item in spec.inputs}
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    if "downstream_tool_name" not in output_properties:
        return []
    if "downstream_tool_kwargs" not in output_properties:
        return []
    if "action_type" not in input_names:
        return []
    if "selected_record" in input_names or "records" in input_names:
        return []
    scalar_inputs = sorted(
        name
        for name in input_names
        if name
        not in {
            "action_type",
            "user_intent",
        }
    )
    if not scalar_inputs:
        return []
    return [
        "",
        "Direct scalar action-prep usage:",
        "    Use this helper only when the user directly supplied the scalar",
        " fields needed for the contact/message action. It is not a selector.",
        "    Pass action_type as add_contact, remove_contact, modify_contact,",
        " or send_message. Pass only visible user-provided scalar fields such",
        f" as {', '.join(scalar_inputs)}.",
        "    Optional scalar fields may be omitted; the helper must abstain if",
        " required fields for the chosen action are still missing.",
        "    If should_call_tool is true, call downstream_tool_name next with",
        " downstream_tool_kwargs unchanged. This helper only prepares kwargs",
        " and does not perform the side effect.",
        "    Do not use this helper for relationship, recency, search, or",
        " selected-record workflows where the target must first be found.",
    ]


def _medium_grain_composite_usage_note(spec: ToolSpec) -> list[str]:
    """Affordance guidance for search-result-to-action workflow helpers."""
    input_names = {item.name for item in spec.inputs}
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if not isinstance(output_properties, dict):
        return []
    if "records" not in input_names or "downstream_tool_name" not in output_properties:
        return []
    if "downstream_tool_kwargs" not in output_properties:
        return []
    return [
        "",
        "Medium-grain workflow usage:",
        "    Use this helper after an original search/get tool returns visible",
        " candidate records and the task requires selecting a target, answering",
        " from a selected field, or preparing one downstream ToolSandbox action.",
        "    Pass records as the full list returned by the prior ToolSandbox",
        " result. If the payload is visible and you omit records, SAGE may",
        " safely autofill it from the latest matching original search trace.",
        "    Pass match_field and match_value as the visible constraint to match,",
        " such as phone_number/name/relationship/sender/content.",
        "    Pass action_type as answer_field, remove_contact, modify_contact,",
        " or send_message. Pass update_fields only for required updates/content.",
        "    If should_call_tool is true, call downstream_tool_name next with",
        " downstream_tool_kwargs unchanged. This helper does not perform the",
        " side effect.",
        "    If abstain_reason is non-empty or tie_candidates is non-empty, do",
        " not guess before a side-effect action; search further or ask for",
        " clarification.",
    ]


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
    if "downstream_tool_kwargs" in output_properties:
        lines.extend(
            [
                "    If abstain_reason is empty and should_call_tool is true,",
                " immediately call downstream_tool_name next with",
                " downstream_tool_kwargs unchanged. This helper does not perform",
                " the action.",
                "    If should_call_tool is false, do not guess; use safety_notes,",
                " search further, or ask for clarification before any side-effect",
                " action.",
            ]
        )
    else:
        lines.extend(
            [
                "    If abstain_reason is empty, use selected_record/selected_id for",
                " the next original ToolSandbox action. For older retained tools",
                " without downstream_tool_kwargs, map selected_id to reminder_id for",
                " remove_reminder/modify_reminder and to person_id for",
                " remove_contact/modify_contact.",
                "    If abstain_reason is non-empty, do not guess before a",
                " side-effect action; search further or ask for clarification.",
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


def _schema_abstain_result(entry: RegistryEntry, reason: str) -> Any:
    """Return a schema-shaped abstain payload for side-effect-free helpers."""
    output_schema = entry.tool.spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    if entry.tool.spec.output_annotation != "dict" or not isinstance(
        output_properties, dict
    ):
        raise TypeError("generated tool output is not abstain-compatible")
    if "abstain_reason" not in output_properties:
        raise TypeError("generated tool output has no abstain_reason")

    result = {
        key: _schema_default_value(schema) for key, schema in output_properties.items()
    }
    for key in tuple(result):
        if key.startswith("should_") or key in {"should_call", "should_call_tool"}:
            result[key] = False
    result["abstain_reason"] = reason
    return result


def _missing_argument_abstain_result(entry: RegistryEntry, error: TypeError) -> Any:
    """Return a safe abstain payload for omitted required args, or re-raise."""
    message = str(error)
    if "missing" not in message or "required positional argument" not in message:
        raise error
    try:
        return _schema_abstain_result(entry, "missing_required_helper_inputs")
    except TypeError:
        raise error


def _invalid_input_abstain_result(
    entry: RegistryEntry,
    error: TypeError,
    kwargs: Mapping[str, Any],
) -> Any:
    """Return a safe abstain payload for invalid generated-tool inputs."""
    message = str(error)
    invalid_input_markers = (
        "NoneType",
        "could not convert",
        "must be a string or a real number",
        "unsupported operand",
    )
    if not any(marker in message for marker in invalid_input_markers):
        raise error
    reason = "invalid_helper_inputs"
    if kwargs.get("current_timestamp") is None and any(
        item.name == "current_timestamp" for item in entry.tool.spec.inputs
    ):
        reason = "missing_current_timestamp"
    try:
        return _schema_abstain_result(entry, reason)
    except TypeError:
        raise error


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


def _latest_original_search_records() -> list[dict[str, Any]] | None:
    """Return the newest visible list of records from an original search trace."""
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
            if not tool_name.startswith(("search_", "find_", "get_")):
                continue
            result = payload.get("result")
            if isinstance(result, list) and all(
                isinstance(record, dict) for record in result
            ):
                return [dict(record) for record in result]
            if isinstance(result, dict):
                return [dict(result)]
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
            if isinstance(result, list):
                first = next(
                    (item for item in result if isinstance(item, dict) and item),
                    None,
                )
                if isinstance(first, dict):
                    return dict(first)
            if isinstance(result, (str, int, float, bool)):
                return {"result": result}
    return None


def _latest_original_tool_scalar(tool_name: str) -> float | None:
    """Return the latest scalar result from a visible original tool trace."""
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
            if str(payload.get("tool_name", "")) != tool_name:
                continue
            try:
                return float(payload.get("result"))
            except (TypeError, ValueError):
                return None
    return None


def _latest_datetime_info_for_timestamp(timestamp_value: Any) -> dict[str, Any] | None:
    """Return visible timestamp_to_datetime_info output for the given timestamp."""
    try:
        timestamp = float(timestamp_value)
    except (TypeError, ValueError):
        return None
    try:
        sandbox = get_current_context().get_database(
            namespace=DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
        )
    except Exception:
        return None
    required = {"year", "month", "day", "hour", "minute", "second"}
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
            if str(payload.get("tool_name", "")) != "timestamp_to_datetime_info":
                continue
            arguments = payload.get("arguments")
            if isinstance(arguments, dict) and "timestamp" in arguments:
                try:
                    if abs(float(arguments.get("timestamp")) - timestamp) > 1.0:
                        continue
                except (TypeError, ValueError):
                    continue
            result = payload.get("result")
            if isinstance(result, dict) and required <= set(result):
                return dict(result)
    return None


def _latest_original_tool_records(
    tool_names: Iterable[str],
) -> list[dict[str, Any]] | None:
    """Return the newest visible list/dict records from one of the named tools."""
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
            if isinstance(result, list) and all(
                isinstance(record, dict) for record in result
            ):
                return [dict(record) for record in result]
            if isinstance(result, dict):
                return [dict(result)]
    return None


def _setting_trace_result_succeeded(result: Any) -> bool:
    if result is None:
        return True
    text = str(result).strip().lower()
    if text in {"", "none", "null"}:
        return True
    if "already" in text and any(
        token in text for token in ("enabled", "disabled", "on", "off")
    ):
        return True
    if any(token in text for token in ("error", "exception", "cannot", "failed")):
        return False
    return False


def _visible_setting_state_summary_from_trace() -> str:
    """Summarize visible prior setting setters from SANDBOX tool traces only."""
    try:
        sandbox = get_current_context().get_database(
            namespace=DatabaseNamespace.SANDBOX,
            get_all_history_snapshots=True,
        )
    except Exception:
        return ""
    latest_by_tool: dict[str, str] = {}
    for row in sandbox.to_dicts():
        existing = row.get("tool_trace")
        if existing is None:
            continue
        traces = existing.to_list() if hasattr(existing, "to_list") else list(existing)
        for item in traces:
            try:
                payload = json.loads(str(item))
            except json.JSONDecodeError:
                continue
            tool_name = str(payload.get("tool_name", ""))
            if tool_name not in SETTING_SETTER_TOOL_NAMES:
                continue
            if not _setting_trace_result_succeeded(payload.get("result")):
                continue
            arguments = payload.get("arguments")
            if not isinstance(arguments, dict) or "on" not in arguments:
                continue
            label = SETTING_STATE_LABELS[tool_name]
            state = "on" if bool(arguments.get("on")) else "off"
            latest_by_tool[tool_name] = f"{label} is {state}"
    return "; ".join(latest_by_tool[name] for name in sorted(latest_by_tool))


def _visible_original_tool_names() -> list[str]:
    try:
        context = get_current_context()
    except Exception:
        return []
    names: Iterable[str]
    if context.tool_allow_list is not None:
        names = context.tool_allow_list
    else:
        names = context.name_to_tool.keys()
    return sorted(
        str(name)
        for name in names
        if str(name) in SETTING_SETTER_TOOL_NAMES
        or str(name)
        in {
            "end_conversation",
            "get_current_timestamp",
            "get_wifi_status",
            "get_cellular_service_status",
            "get_location_service_status",
            "get_low_battery_mode_status",
            "search_holiday",
            "timestamp_diff",
        }
    )


def _normalized_available_tool_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        name = ""
        if isinstance(item, str):
            name = item
        elif isinstance(item, Mapping):
            function = item.get("function")
            if isinstance(function, Mapping):
                name = str(function.get("name") or "")
            else:
                name = str(item.get("name") or "")
        name = str(name or "").strip()
        if name.startswith("functions."):
            name = name.split(".", 1)[1]
        if name:
            names.append(name)
    return names


def _with_visible_setting_state_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    spec = entry.tool.spec
    input_names = {item.name for item in spec.inputs}
    if not ({"visible_state_summary", "available_tools"} & input_names):
        return kwargs
    updated = dict(kwargs)
    if (
        spec.tool_name.startswith("plan_device_state_action_sequence")
        and "visible_state_summary" in input_names
    ):
        summary = _visible_setting_state_summary_from_trace()
        if summary:
            existing = str(updated.get("visible_state_summary") or "").strip()
            if existing:
                if summary not in existing:
                    updated["visible_state_summary"] = f"{existing}; {summary}"
            else:
                updated["visible_state_summary"] = summary
    if "available_tools" in input_names:
        available_tools = _visible_original_tool_names()
        if available_tools:
            merged = {
                *_normalized_available_tool_names(updated.get("available_tools")),
                *available_tools,
            }
            updated["available_tools"] = sorted(merged)
    return updated


def _with_visible_datetime_context_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Autofill generated timestamp-tool context from visible original traces."""
    input_names = {item.name for item in entry.tool.spec.inputs}
    if "current_datetime_info" not in input_names:
        return kwargs
    updated = dict(kwargs)
    if "current_timestamp" in input_names and updated.get("current_timestamp") is None:
        current_timestamp = _latest_original_tool_scalar("get_current_timestamp")
        if current_timestamp is not None:
            updated["current_timestamp"] = current_timestamp
    if updated.get("current_datetime_info"):
        return updated
    current_info = _latest_datetime_info_for_timestamp(updated.get("current_timestamp"))
    if current_info:
        updated["current_datetime_info"] = current_info
    return updated


def _with_chained_visible_payload_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Autofill low-risk scalar-extraction helpers from prior raw tool output."""
    spec = entry.tool.spec
    if spec.family != ToolFamily.DERIVED_VALUE_CALCULATOR:
        return kwargs
    dict_inputs = [item for item in spec.inputs if item.annotation == "dict"]
    if len(dict_inputs) != 1:
        return kwargs
    input_name = dict_inputs[0].name
    if kwargs.get(input_name):
        return kwargs
    payload = _latest_original_tool_payload(spec.required_original_tool_calls)
    if payload is None and spec.required_original_tool_calls:
        return kwargs
    if isinstance(payload, list):
        payload = next(
            (item for item in payload if isinstance(item, dict) and item),
            None,
        )
    if payload is None:
        payload = _latest_single_original_search_record()
    if not isinstance(payload, dict) or not payload:
        return kwargs
    updated = dict(kwargs)
    updated[input_name] = payload
    return updated


def _with_chained_contact_records_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Pass full visible contact records into helpers instead of lossy id subsets."""
    spec = entry.tool.spec
    if spec.family not in {
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
    }:
        return kwargs
    input_names = {item.name for item in spec.inputs}
    if "contacts" not in input_names:
        return kwargs
    if "search_contacts" not in spec.required_original_tool_calls:
        return kwargs
    visible_contacts = _latest_original_tool_records(("search_contacts",))
    if not visible_contacts:
        return kwargs

    updated = dict(kwargs)
    supplied = updated.get("contacts")
    if spec.tool_name == "plan_contact_relationship_batch_update" and not supplied:
        return kwargs
    if not supplied:
        updated["contacts"] = visible_contacts
        return updated
    if not isinstance(supplied, list) or not all(
        isinstance(item, dict) for item in supplied
    ):
        return kwargs

    contacts_by_id = {
        str(contact.get("person_id") or ""): contact
        for contact in visible_contacts
        if str(contact.get("person_id") or "").strip()
    }
    if not contacts_by_id:
        return kwargs

    merged: list[dict[str, Any]] = []
    changed = False
    for item in supplied:
        person_id = str(item.get("person_id") or "").strip()
        visible = contacts_by_id.get(person_id)
        if not visible:
            merged.append(dict(item))
            continue
        merged_item = dict(visible)
        merged_item.update(item)
        if merged_item != item:
            changed = True
        merged.append(merged_item)
    if changed:
        updated["contacts"] = merged
        return updated
    return kwargs


def _canonicalize_records_from_visible_trace(
    supplied: Any,
    visible_records: list[dict[str, Any]] | None,
) -> tuple[Any, bool]:
    """Replace copied records with exact prior tool records when ids match."""
    if not isinstance(supplied, list) or not visible_records:
        return supplied, False
    id_fields = ("message_id", "reminder_id", "person_id")
    visible_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in visible_records:
        if not isinstance(record, dict):
            continue
        for field in id_fields:
            value = str(record.get(field) or "").strip()
            if value:
                visible_by_key[(field, value)] = record

    if not visible_by_key:
        return supplied, False

    changed = False
    canonicalized: list[Any] = []
    for item in supplied:
        if not isinstance(item, dict):
            canonicalized.append(item)
            continue
        replacement = None
        for field in id_fields:
            value = str(item.get(field) or "").strip()
            if value:
                replacement = visible_by_key.get((field, value))
                if replacement is not None:
                    break
        if replacement is None:
            canonicalized.append(item)
            continue
        replacement_dict = dict(replacement)
        canonicalized.append(replacement_dict)
        if replacement_dict != item:
            changed = True
    return canonicalized, changed


def _with_chained_post_selection_arguments(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Autofill mechanical chaining args from prior traces when safe."""
    spec = entry.tool.spec
    input_names = {item.name for item in spec.inputs}
    if spec.family not in {
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        ToolFamily.SEARCH_FILTER_RANKING_HELPER,
    }:
        return kwargs
    if not ({"selected_record", "records"} & input_names):
        return kwargs

    updated = dict(kwargs)
    if "records" in input_names:
        records = _latest_original_search_records()
        if not updated.get("records"):
            if records:
                updated["records"] = records
        else:
            canonicalized, changed = _canonicalize_records_from_visible_trace(
                updated.get("records"),
                records,
            )
            if changed:
                updated["records"] = canonicalized
    if "selected_record" in input_names and not updated.get("selected_record"):
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
            "contact_name",
            "name",
            "phone_number",
            "default_country_code",
            "email",
            "relationship",
            "target_field",
            "new_value",
            "message_text",
            "record_id",
            "person_id",
            "resolved_reminder_timestamp",
            "current_timestamp",
            "day_offset",
            "hour",
            "minute",
            "local_utc_offset_hours",
            "location_requested",
            "location_required",
            "location_available",
            "latitude",
            "longitude",
            "location_lookup_failed",
            "current_datetime_info",
        }:
            continue
        updated[item.name] = copy.deepcopy(OPTIONAL_HELPER_DEFAULTS[item.name])
    input_names = {item.name for item in entry.tool.spec.inputs}
    if (
        entry.tool.spec.tool_name == "prepare_reminder_creation_args"
        and "location_available" in input_names
    ):
        coordinates_are_search_backed = _latest_location_search_matches_coordinates(
            updated.get("latitude"),
            updated.get("longitude"),
        )
        if coordinates_are_search_backed:
            updated["location_available"] = True
            if "location_requested" in input_names:
                updated["location_requested"] = True
        elif bool(updated.get("location_requested")) or bool(
            updated.get("location_required")
        ):
            updated["location_available"] = False
    return updated


def _without_unknown_helper_kwargs(
    entry: RegistryEntry,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Drop model-invented fields that are outside the accepted tool spec."""
    input_names = {item.name for item in entry.tool.spec.inputs}
    if not input_names:
        return dict(kwargs)
    return {key: value for key, value in kwargs.items() if key in input_names}


def _latest_location_search_matches_coordinates(
    latitude_value: Any,
    longitude_value: Any,
) -> bool:
    """Return whether coordinates are visible from an original location search."""
    try:
        latitude = float(latitude_value)
        longitude = float(longitude_value)
    except (TypeError, ValueError):
        return False
    if latitude == 0.0 or longitude == 0.0:
        return False
    records = _latest_original_tool_records(("search_location_around_lat_lon",))
    if not records:
        return False
    for record in records:
        try:
            record_latitude = float(record.get("latitude", record.get("lat")))
            record_longitude = float(
                record.get("longitude", record.get("lon", record.get("lng")))
            )
        except (TypeError, ValueError):
            continue
        if (
            abs(record_latitude - latitude) <= 0.001
            and abs(record_longitude - longitude) <= 0.001
        ):
            return True
    return False


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


def _compact_google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    dict_input_keys = _dict_input_keys(entry)
    lines = [_compact_text(spec.description, limit=220), "", "Args:"]
    for item in spec.inputs:
        description = _compact_text(item.description, limit=140)
        if item.name in dict_input_keys:
            keys = ", ".join(dict_input_keys[item.name])
            description = f"{description} Visible keys: {keys}."
        lines.append(f"    {item.name}: {description}")

    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    output_keys: list[str] = []
    if isinstance(output_properties, dict):
        output_keys = [str(key) for key in output_properties]
    returns = spec.output_annotation
    if output_keys:
        visible_keys = ", ".join(output_keys[:10])
        if len(output_keys) > 10:
            visible_keys = f"{visible_keys}, ..."
        returns = f"{returns}. Keys: {visible_keys}"
    lines.extend(["", "Returns:", f"    {_compact_text(returns, limit=220)}"])

    if spec.positive_triggers:
        lines.extend(["", "Use when:"])
        for trigger in spec.positive_triggers[:5]:
            lines.append(f"    - {_compact_text(trigger, limit=110)}")
    if spec.negative_triggers:
        lines.extend(["", "Do not use when:"])
        for trigger in spec.negative_triggers[:5]:
            lines.append(f"    - {_compact_text(trigger, limit=110)}")
    if spec.applicable_task_families:
        families = ", ".join(spec.applicable_task_families[:8])
        if len(spec.applicable_task_families) > 8:
            families = f"{families}, ..."
        lines.extend(["", "Applies to:", f"    {_compact_text(families, limit=180)}"])

    lines.extend(
        [
            "",
            "Generated SAGE tool usage:",
            "    Use only when visible task constraints, visible records, or prior tool output match this schema.",
            "    Generated tools prepare values, select records, normalize evidence, or construct arguments.",
            "    Original environment tools still perform state-changing actions.",
            "    If the result has a true should_call flag with a tool name and kwargs, call that original tool next using the returned kwargs unchanged.",
            "    If the result has final_answer, final_answer_recommendation, answer_value, selected_record, or value and no downstream action is required, answer from that result.",
            "    If the result has abstain_reason, missing information, tie candidates, or a false should_call flag, do not guess missing fields.",
        ]
    )
    if spec.tool_name == "relative_day_time_to_timestamp":
        lines.extend(
            [
                "    For this timestamp tool, pass current_timestamp plus day_offset/hour/minute and current_datetime_info from timestamp_to_datetime_info. Do not infer local day boundaries from a bare Unix timestamp.",
                "    If this tool returns 0.0, treat the timestamp context as unresolved and do not use 0.0 as a reminder timestamp.",
            ]
        )
    elif spec.tool_name == "plan_device_status_lookup":
        lines.extend(
            [
                "    For this status tool, call only the original getter named by tool_name when that getter is visible.",
                "    If abstain_reason is status_getter_not_visible, do not substitute a different device getter.",
            ]
        )
    elif spec.tool_name == "plan_contact_lookup_query":
        lines.extend(
            [
                "    For scalar contact lookup, call this generated tool before manually choosing search_contacts arguments.",
                "    Use only user-visible constraints. Do not add is_self or unrelated filters unless the user explicitly supplied them.",
                "    For remove/update by phone or name, requested_field should be person_id so the original side-effect tool receives a stable id.",
                "    If a contact side-effect task lacks a name, phone number, relationship, or person id, ask for a name or phone number rather than asking for an internal person_id.",
            ]
        )
    return "\n".join(lines)


def _ultra_google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    output_keys: list[str] = []
    if isinstance(output_properties, dict):
        output_keys = [str(key) for key in output_properties]
    arg_parts = []
    dict_input_keys = _dict_input_keys(entry)
    for item in spec.inputs:
        part = item.name
        if item.name in dict_input_keys:
            keys = ", ".join(dict_input_keys[item.name][:8])
            part = f"{part} keys: {keys}"
        arg_parts.append(part)
    args = "; ".join(arg_parts) if arg_parts else "none"
    returns = ", ".join(output_keys[:12]) if output_keys else spec.output_annotation
    if output_keys and len(output_keys) > 12:
        returns = f"{returns}, ..."
    family = str(getattr(spec.family, "value", spec.family))
    lines = [
        _compact_text(spec.description, limit=120),
        f"Args: {_compact_text(args, limit=420)}.",
        f"Returns: {_compact_text(returns, limit=300)}.",
        (
            "SAGE generated tool: use only with visible inputs; it prepares, "
            "selects, normalizes, or builds kwargs. Original tools perform "
            "state changes. If should_call/*_kwargs names an original tool, "
            "call that original tool next unchanged. If final/value output is "
            "terminal, answer from it. If abstain/missing/tie, do not guess."
        ),
    ]
    if spec.required_original_tool_calls:
        required = ", ".join(spec.required_original_tool_calls[:6])
        lines.append(f"Preserves original tool path: {required}.")
    elif spec.preserves_side_effect_tools:
        preserved = ", ".join(spec.preserves_side_effect_tools[:6])
        lines.append(f"Preserves side-effect path: {preserved}.")
    if family:
        lines.append(f"Family: {family}.")
    return "\n".join(lines)


def _micro_google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    output_keys: list[str] = []
    if isinstance(output_properties, dict):
        output_keys = [str(key) for key in output_properties]
    dict_input_keys = _dict_input_keys(entry)
    lines = [_compact_text(spec.description, limit=72), "", "Args:"]
    for item in spec.inputs:
        description = _compact_text(item.description, limit=46)
        if item.name in dict_input_keys:
            keys = ", ".join(dict_input_keys[item.name][:5])
            description = _compact_text(f"visible dict keys: {keys}", limit=58)
        lines.append(f"  {item.name}: {description}")
    returns = ", ".join(output_keys[:8]) if output_keys else spec.output_annotation
    if output_keys and len(output_keys) > 8:
        returns = f"{returns}, ..."
    lines.extend(
        [
            "",
            f"Returns: {_compact_text(returns, limit=180)}.",
            (
                "Use only visible inputs. This SAGE tool prepares/selects/"
                "normalizes; original tools do side effects. If it returns a "
                "true should_call flag plus tool name or *_kwargs, call that "
                "original tool next unchanged. If it returns final/value with "
                "no action left, answer from it. If it abstains, do not guess."
            ),
        ]
    )
    return "\n".join(lines)


def _nano_google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    output_schema = spec.output_schema or {}
    output_properties = output_schema.get("properties", {})
    output_keys: list[str] = []
    if isinstance(output_properties, dict):
        output_keys = [str(key) for key in output_properties]
    args = ", ".join(item.name for item in spec.inputs) or "none"
    returns = ", ".join(output_keys[:8]) if output_keys else spec.output_annotation
    if output_keys and len(output_keys) > 8:
        returns = f"{returns}, ..."
    return "\n".join(
        [
            _compact_text(spec.description, limit=56),
            f"Args: {_compact_text(args, limit=260)}.",
            f"Returns: {_compact_text(returns, limit=180)}.",
            (
                "SAGE generated tool. Use visible inputs only; original tools "
                "perform side effects. If returned *_kwargs/tool name authorizes "
                "an original call, call that original next unchanged. If it "
                "abstains, do not guess."
            ),
        ]
    )


def _google_docstring(entry: RegistryEntry) -> str:
    docstring_mode = _generated_tool_docstring_mode()
    if docstring_mode == "nano":
        return _nano_google_docstring(entry)
    if docstring_mode == "micro":
        return _micro_google_docstring(entry)
    if docstring_mode == "ultra":
        return _ultra_google_docstring(entry)
    if docstring_mode == "compact":
        return _compact_google_docstring(entry)
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
    if spec.tool_name == "plan_device_status_lookup":
        description = (
            f"{description} Use this helper only for read-only device-status "
            "checks. If it returns should_call=True, execute the returned "
            "original ToolSandbox getter with the returned arguments. After the "
            "getter returns, answer from the visible getter result or call the "
            "helper again with visible_state_result to normalize the final "
            "status sentence. Do not use this helper to change settings."
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
                " a timestamp, pass it as resolved_reminder_timestamp.",
                "    For plain relative times ('tomorrow at 5 PM', 'next Friday'),",
                " pass current_timestamp with day_offset, hour, minute, and",
                " current_datetime_info from timestamp_to_datetime_info.",
                "    If the user did not provide a reminder date/time and you do",
                " not already have a resolved timestamp, do not pass day_offset=0,",
                " hour=0, and minute=0 as a placeholder. Let the generated tool",
                " abstain and ask for the missing time instead.",
                "    Keep reminder content separate from location. If the user",
                " said 'buy milk at Store', pass content='buy milk' and pass",
                " Store only through location lookup and coordinate fields.",
                "    Do not use a searched place's timezone for reminder",
                " timestamps; use current_datetime_info from the sandbox clock.",
                "    Set location_requested=True when the user mentioned an optional",
                " location that might still need lookup.",
                "    Set location_required=True only when the user explicitly requires",
                " a location on the reminder. A mentioned location is not required.",
                "    If optional location is mentioned but not resolved and lookup",
                " has not failed, the helper abstains so the actor can search or",
                " ask instead of creating the reminder prematurely.",
                "    If optional location lookup failed or no location was requested,",
                " pass latitude=0.0 and longitude=0.0 to the helper; it omits",
                " coordinates from add_reminder kwargs.",
                "    If result['should_call_add_reminder'] is True, immediately call",
                " add_reminder(**result['add_reminder_kwargs']) unchanged.",
                "    If result['should_call_add_reminder'] is False, do not call",
                " add_reminder with a manual timestamp or previous partial args.",
                " Satisfy result['abstain_reason'] and call this generated tool",
                " again until it returns call-ready add_reminder_kwargs.",
            ]
        )
    elif spec.tool_name == "next_weekday_time_to_timestamp":
        lines.extend(
            [
                "",
                "Usage:",
                "    Use this generated tool only for explicit next-weekday",
                " reminder times such as 'next Friday at 5 PM'.",
                "    First call get_current_timestamp. Then call",
                " timestamp_to_datetime_info on that exact timestamp and pass the",
                " returned dict as current_datetime_info.",
                "    Do not guess local_utc_offset_hours or use a searched place's",
                " timezone. The generated tool derives the sandbox local offset",
                " from current_timestamp plus current_datetime_info.",
                "    If the generated tool returns 0.0, do not call add_reminder;",
                " resolve the missing or inconsistent time context first.",
                "    This generated tool only prepares reminder_timestamp. The",
                " original add_reminder side-effect tool must still create the",
                " reminder.",
            ]
        )
    elif spec.tool_name == "prepare_add_contact_args":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this generated tool before the original add_contact call",
                " when the user request visibly contains the contact name and phone",
                " number.",
                "    Call path: prepare_add_contact_args(...) ->",
                " add_contact(**result['add_contact_kwargs'])",
                "    This generated tool only prepares arguments. It does not search",
                " contacts, modify contacts, or create contacts by itself.",
                "    If result['should_call_downstream_tool'] is true, immediately",
                " call the original ToolSandbox tool named in",
                " result['downstream_tool_name'] with",
                " result['downstream_tool_kwargs'] unchanged.",
                "    If it abstains, use result['abstain_reason'] instead of",
                " guessing missing name or phone fields.",
            ]
        )
    elif spec.tool_name == "plan_contact_update_from_id":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this generated tool before the original modify_contact",
                " call when the user request visibly contains a stable",
                " person/contact id and a new phone number, name, or relationship.",
                "    Call path: plan_contact_update_from_id(...) ->",
                " modify_contact(**result['downstream_tool_kwargs'])",
                "    This generated tool only prepares arguments. It does not",
                " search contacts, modify contacts, or infer missing ids.",
                "    If result['should_call_tool'] is true, immediately call the",
                " original ToolSandbox modify_contact tool with",
                " result['downstream_tool_kwargs'] unchanged.",
                "    If it abstains, use result['abstain_reason'] instead of",
                " guessing missing person id or update fields.",
            ]
        )
    elif spec.tool_name == "prepare_location_search_args":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this generated tool before the original",
                " search_location_around_lat_lon call when the user request visibly",
                " contains a place phrase for a reminder location.",
                "    Pass the full user request as user_request, or pass the exact",
                " visible place phrase as location_phrase if already isolated.",
                "    Preserve street, venue, and neighborhood qualifiers such as",
                " 'on Stevens Creek'; do not reduce the query to only a brand name.",
                "    If this generated tool abstains because the reminder",
                " date/time is missing, ask the user for that time before",
                " location lookup, device-state repair, or add_reminder.",
                "    For broad place names without street, neighborhood, or venue",
                " qualifiers, the generated result may route the next call to",
                " original get_current_location. If so, call it, then call this",
                " generated tool again with the returned latitude/longitude.",
                "    Call path: prepare_location_search_args(...) ->",
                " get_current_location() if requested, otherwise",
                " search_location_around_lat_lon(**result['search_location_kwargs'])",
                "    If result['should_call_downstream_tool'] is true, immediately",
                " call the original tool named in result['downstream_tool_name'] with",
                " result['downstream_tool_kwargs'] unchanged.",
                "    Do not pass latitude=0 or longitude=0 to the original search",
                " tool. If no real coordinates are visible, let the generated tool",
                " route to current location for broad place names or omit coordinate",
                " keys for qualified place queries.",
                "    This generated tool only prepares the search call. It does not",
                " return coordinates and does not create the reminder.",
            ]
        )
    elif spec.tool_name == "extract_service_answer_field" and len(spec.inputs) == 1:
        input_name = spec.inputs[0].name
        lines.extend(
            [
                "",
                "Deterministic extraction usage:",
                "    First call the relevant original ToolSandbox lookup or",
                " conversion tool needed for the user's request.",
                f"    Then call {spec.tool_name} with {input_name} set to the",
                " actual visible result from that original tool. The visible",
                " result may be a dict, a list of result dicts, or a scalar",
                " string/number returned by the original tool.",
                "    For list results, pass the relevant result dict when it is",
                " clear; otherwise pass the full list and the helper will use",
                " the first supported answer field.",
                "    Use the helper result for the final scalar answer. This",
                " helper does not perform side effects and does not replace the",
                " original lookup/conversion call.",
            ]
        )
    elif spec.tool_name == "extract_service_answer_field":
        lines.extend(
            [
                "",
                "Deterministic extraction usage:",
                "    First call the relevant original ToolSandbox lookup,",
                " conversion, or distance tool needed for the user's request.",
                "    Then call extract_service_answer_field with service_payload",
                " set to the visible dict, result-list item, result list, or",
                " {'result': scalar_value} wrapper from that original tool.",
                "    If the original tool returns a bare number or string, do",
                " not pass it directly; pass service_payload={'result': value}",
                " so the JSON object schema is satisfied.",
                "    For search_lat_lon address strings, wrap the returned",
                " address as {'result': address_string} and answer from",
                " exact_final_answer.",
                "    Set requested_unit from the user's requested answer unit",
                " when visible, for example Fahrenheit or kilometers.",
                "    Set answer_subject from the visible user request or payload",
                " when the final answer should name a place/entity.",
                "    If should_call_downstream_tool is true, immediately call",
                " the original downstream_tool_name with downstream_tool_kwargs",
                " unchanged, then call this helper again on that visible result.",
                "    If exact_final_answer is nonempty and no downstream tool",
                " remains, answer with exact_final_answer.",
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
            lines.extend(_lookup_query_planner_usage_note(spec))
            lines.extend(_message_counterparty_search_usage_note(spec))
            lines.extend(_medium_grain_composite_usage_note(spec))
            lines.extend(_post_selection_composite_usage_note(spec))
            lines.extend(_direct_scalar_action_usage_note(spec))
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
        kwargs = _with_chained_contact_records_arguments(entry, kwargs)
        kwargs = _with_chained_post_selection_arguments(entry, kwargs)
        kwargs = _with_visible_setting_state_arguments(entry, kwargs)
        kwargs = _with_visible_datetime_context_arguments(entry, kwargs)
        kwargs = _with_optional_helper_defaults(entry, kwargs)
        kwargs = _without_unknown_helper_kwargs(entry, kwargs)
        missing_update_result = _missing_modify_update_abstain_result(entry, kwargs)
        if missing_update_result is not None:
            add_tool_trace(_wrapped, missing_update_result, *args, **kwargs)
            if on_reuse is not None:
                on_reuse(_tool_name)
            return missing_update_result
        try:
            result = _inner(*args, **kwargs)
        except TypeError as error:
            try:
                result = _missing_argument_abstain_result(entry, error)
            except TypeError:
                result = _invalid_input_abstain_result(entry, error, kwargs)
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
    # Adding safe defaults to optional scalar helper inputs can create an
    # invalid signature when a required selector input follows them in generated
    # code, e.g. contact_name="", requested_field. ToolSandbox/OpenAI call these
    # helpers by keyword, so expose a valid keyword signature by listing required
    # positional-or-keyword parameters before defaulted optional parameters.
    positional = [
        p
        for p in signature_parameters
        if p.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    non_positional = [p for p in signature_parameters if p not in positional]
    required_positional = [
        p for p in positional if p.default is inspect.Parameter.empty
    ]
    defaulted_positional = [
        p for p in positional if p.default is not inspect.Parameter.empty
    ]
    signature_parameters = [
        *required_positional,
        *defaulted_positional,
        *non_positional,
    ]
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
    if spec.negative_triggers:
        for token in spec.negative_triggers:
            if token.lower() in name_lower:
                return False, "negative_trigger_suppressed"
    if spec.positive_triggers:
        for token in spec.positive_triggers:
            if token.lower() in name_lower:
                return True, "positive_trigger_match"
    return None


VISIBLE_CONTEXT_TOOL_SIGNALS: dict[str, tuple[str, ...]] = {
    "prepare_safe_action_or_abstain": (
        "insufficient_information",
        "safe_abstain_needed",
    ),
    "plan_device_status_lookup": ("device_status_read",),
    "plan_device_state_action_sequence_v3": (
        "device_state_action",
        "direct_device_state_action",
        "state_precondition_possible",
    ),
    "next_service_tool_call": ("state_precondition_possible",),
    "prepare_reminder_creation_args": ("reminder_create",),
    "relative_day_time_to_timestamp": ("relative_time",),
    "next_weekday_time_to_timestamp": ("weekday_time",),
    "prepare_location_search_args": (
        "location_phrase",
        "external_lookup",
        "service_answer_extraction",
    ),
    "prepare_add_contact_args": ("add_contact",),
    "prepare_direct_contact_action_args": ("direct_contact_action",),
    "plan_contact_lookup_query": ("contact_lookup",),
    "plan_send_message_contact_lookup": ("named_message_recipient",),
    "plan_contact_relationship_batch_update": ("relationship_batch_update",),
    "select_message_counterparty_for_contact_update": ("message_counterparty_update",),
    "plan_message_counterparty_search": (
        "message_counterparty_lookup",
        "message_counterparty_update",
    ),
    "resolve_search_window_or_bounds": (
        "recency_search",
        "message_search_followup_possible",
    ),
    "select_record_by_timestamp_extreme": (
        "recency_search",
        "message_search_followup_possible",
    ),
    "select_message_content_by_recency": (
        "message_recency",
        "message_search_followup_possible",
    ),
    "select_action_target_by_recency": ("recency_action",),
    "prepare_holiday_search_args": ("holiday",),
    "days_between_timestamps": ("calendar_distance",),
    "extract_stock_symbol": ("stock_lookup",),
    "extract_service_answer_field": ("service_answer_extraction",),
}

LOWER_LEVEL_TOOL_FAMILIES = {
    ToolFamily.CANONICALIZER,
    ToolFamily.DERIVED_VALUE_CALCULATOR,
}


def _tool_spec_input_names(spec: ToolSpec) -> set[str]:
    return {str(item.name) for item in spec.inputs if str(item.name)}


def _tool_spec_side_effect_targets(spec: ToolSpec) -> set[str]:
    return {
        str(item)
        for item in (
            *spec.preserves_side_effect_tools,
            *spec.required_original_tool_calls,
        )
        if str(item)
    }


def _composite_subsumes_lower_level_tool(
    composite: RegistryEntry,
    lower_level: RegistryEntry,
    *,
    task_context_text: str | None,
) -> bool:
    """Prefer a visible composite tool when it can consume a lower-level tool's inputs.

    This is a general token discipline: when a generated composite tool accepts
    the same primitive inputs as a lower-level generated canonicalizer and
    preserves the same downstream side-effect route, exposing both tools usually
    causes the actor to call both. The composite remains an autonomous generated
    tool; this rule only keeps the runtime bundle from offering a redundant
    lower-level abstraction for the same visible task context.
    """

    if not task_context_text:
        return False
    composite_spec = composite.tool.spec
    lower_spec = lower_level.tool.spec
    if lower_spec.tool_name in {
        "relative_day_time_to_timestamp",
        "next_weekday_time_to_timestamp",
    }:
        # These generated timestamp tools are not redundant in practice. They
        # prevent the actor from hand-computing relative reminder times before a
        # composite action-argument tool is called.
        return False
    if composite_spec.family != ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        return False
    if lower_spec.family not in LOWER_LEVEL_TOOL_FAMILIES:
        return False
    composite_inputs = _tool_spec_input_names(composite_spec)
    lower_inputs = _tool_spec_input_names(lower_spec)
    if not lower_inputs or not lower_inputs <= composite_inputs:
        return False
    composite_targets = _tool_spec_side_effect_targets(composite_spec)
    lower_targets = _tool_spec_side_effect_targets(lower_spec)
    if not composite_targets or not lower_targets:
        return False
    return bool(composite_targets & lower_targets)


def _visible_context_route_decision(
    entry: RegistryEntry,
    *,
    task_context_text: str | None,
    task_family_key: str | None,
) -> RuntimeRoutingDecision:
    spec = entry.tool.spec
    tool_name = spec.tool_name
    if entry.retired or not entry.validation.accepted:
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "registry_entry_not_active", -100
        )
    if not has_current_validation_proof(entry):
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "legacy_validation_missing_current_proof", -100
        )
    if not task_context_text:
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "missing_visible_task_context", -20
        )
    if tool_name == "plan_device_status_lookup" and not _direct_status_lookup_enabled():
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "direct_status_lookup_disabled", -30
        )
    context = f"{task_context_text} family={task_family_key or ''}".lower()
    match_context = context
    if " tools=" in context and " signals=" in context:
        request_part = context.split(" tools=", 1)[0]
        signal_part = context.split(" signals=", 1)[1]
        match_context = f"{request_part} signals={signal_part}"
    matched_negative = tuple(
        token
        for token in spec.negative_triggers
        if token and str(token).lower() in match_context
    )
    if matched_negative:
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "blocked_by_negative_trigger",
            -50,
            matched_negative_triggers=matched_negative,
        )
    matched_signals = tuple(
        signal
        for signal in VISIBLE_CONTEXT_TOOL_SIGNALS.get(tool_name, ())
        if signal in match_context
    )
    if tool_name in VISIBLE_CONTEXT_TOOL_SIGNALS and not matched_signals:
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "visible_context_required_signal_missing",
            -20,
        )
    if (
        tool_name == "relative_day_time_to_timestamp"
        and "external_lookup" in match_context
        and "service_answer_extraction" in match_context
        and "reminder" not in match_context
        and "message" not in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "relative_time_suppressed_for_external_service_lookup",
            -25,
            matched_task_families=matched_signals,
        )
    if tool_name == "prepare_location_search_args" and not (
        "reminder_create" in match_context
        or "external_lookup" in match_context
        or "service_answer_extraction" in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "location_search_args_requires_location_task_context",
            -25,
            matched_task_families=matched_signals,
        )
    if tool_name == "extract_service_answer_field" and any(
        token in match_context
        for token in ("temperature", " temp ", "celsius", "fahrenheit")
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "service_answer_extractor_suppressed_temperature_unit_context",
            -25,
            matched_task_families=matched_signals,
        )
    if (
        tool_name == "select_action_target_by_recency"
        and "recency_action" not in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "recency_action_selector_requires_visible_action_signal",
            -25,
        )
    if (
        tool_name == "select_action_target_by_recency"
        and "reminder" not in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "recency_action_selector_requires_reminder_action_context",
            -25,
        )
    if (
        tool_name == "plan_send_message_contact_lookup"
        and "has_phone_number" in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "direct_phone_message_does_not_need_contact_lookup",
            -20,
        )
    if (
        tool_name == "prepare_direct_contact_action_args"
        and "message_counterparty_update" in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "direct_contact_action_suppressed_for_message_counterparty_update",
            -30,
        )
    if (
        tool_name == "prepare_direct_contact_action_args"
        and "direct_contact_action" not in match_context
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "direct_scalar_action_signal_required",
            -20,
        )
    if (
        spec.family
        in {
            ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        }
        and (
            "insufficient_information" in match_context
            or "safe_abstain_needed" in match_context
        )
        and (spec.preserves_side_effect_tools or spec.required_original_tool_calls)
        and tool_name != "prepare_safe_action_or_abstain"
        and not (
            tool_name == "prepare_direct_contact_action_args"
            and "direct_contact_action" in match_context
        )
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "side_effect_tool_suppressed_for_insufficient_information",
            -30,
        )
    matched_positive = tuple(
        token
        for token in spec.positive_triggers
        if token and str(token).lower() in match_context
    )
    matched_families = tuple(
        family
        for family in spec.applicable_task_families
        if family and str(family).lower() in match_context
    )
    if matched_signals:
        return RuntimeRoutingDecision(
            tool_name,
            True,
            "shown",
            "visible_context_signal_match",
            12 + len(matched_signals),
            matched_positive_triggers=matched_positive,
            matched_task_families=matched_families or matched_signals,
        )
    if matched_positive or matched_families:
        return RuntimeRoutingDecision(
            tool_name,
            True,
            "shown",
            "visible_context_metadata_match",
            6 + len(matched_positive) + len(matched_families),
            matched_positive_triggers=matched_positive,
            matched_task_families=matched_families,
        )
    return RuntimeRoutingDecision(
        tool_name,
        False,
        "hidden",
        "visible_context_no_match",
        -10,
    )


def _birth_scenario_fair_chance_visibility(
    entry: RegistryEntry,
    scenario_name: str,
) -> tuple[bool, str] | None:
    """Give a newly born helper a natural adoption chance on its birth task.

    This is deliberately bounded to the scenario/family that produced the
    helper from oracle-free task text. It does not force a call; it only keeps
    routing from hiding the helper before the actor can decide whether to use
    it.
    """

    if not _birth_scenario_fair_chance_enabled():
        return None
    birth_scenario = (entry.birth_scenario or "").strip().lower()
    if not birth_scenario:
        return None
    name = scenario_name.lower()
    for token in entry.tool.spec.negative_triggers:
        if token and token.lower() in name:
            return None
    if name == birth_scenario:
        return True, "birth_scenario_fair_chance_exact"
    if base_task_family(name) != base_task_family(birth_scenario):
        return None
    scenario_strata = set(classify_task_strata(name))
    birth_strata = set(classify_task_strata(birth_scenario))
    if scenario_strata & birth_strata:
        return True, "birth_scenario_fair_chance_family"
    return None


def _reminder_creation_args_task_route(name: str) -> tuple[bool, str]:
    if name.startswith("create_reminder_"):
        return True, "reminder_creation_args_create_reminder_task"
    if not (name.startswith("add_reminder_content_and_") and "_time" in name):
        return False, "reminder_creation_args_no_creation_signal"
    if "week_delta" in name or "weekday_delta" in name:
        return True, "reminder_creation_args_relative_time_task"
    if "_location" in name:
        return True, "reminder_creation_args_location_task"
    if "low_battery_mode" in name or "wifi_off" in name or "location_off" in name:
        return True, "reminder_creation_args_service_precondition_task"
    return True, "reminder_creation_args_absolute_time_task"


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

    name = scenario_name.lower()
    tool_name = entry.tool.spec.tool_name
    scenario_strata = set(classify_task_strata(name))
    is_insufficient = "insufficient_information" in name
    if tool_name == "prepare_location_search_args":
        if is_insufficient:
            return False, "location_search_args_suppressed_insufficient_information"
        if (
            name.startswith("add_reminder_content_and_")
            and "_time" in name
            and "_location" in name
        ):
            return True, "location_search_args_reminder_location_task"
        return False, "location_search_args_requires_reminder_location_task"
    reminder_creation_with_service_precondition = (
        name.startswith("add_reminder_content_and_")
        and "_time" in name
        and ("low_battery_mode" in name or "wifi_off" in name or "location_off" in name)
    )
    if (
        tool_name == "prepare_reminder_creation_args"
        and ("low_battery_mode" in name or "wifi_off" in name or "location_off" in name)
        and not reminder_creation_with_service_precondition
    ):
        return (
            False,
            "reminder_creation_args_suppressed_for_service_precondition_task",
        )
    if tool_name == "relative_day_time_to_timestamp" and name.startswith(
        "add_reminder_content_and_week_delta"
    ):
        return True, "relative_time_add_reminder_week_delta_task"
    if tool_name == "relative_day_time_to_timestamp" and name.startswith(
        "add_reminder_content_and_date_and_time"
    ):
        return False, "relative_time_suppressed_for_absolute_date_task"
    if tool_name == "next_weekday_time_to_timestamp" and (
        name.startswith("add_reminder_content_and_week_delta")
        or name.startswith("add_reminder_content_and_date_and_time")
    ):
        return False, "next_weekday_suppressed_for_non_weekday_delta_task"
    if tool_name.startswith("plan_device_state_action_sequence") and name.startswith(
        ("get_wifi", "get_cellular", "get_location", "get_low_battery")
    ):
        return False, "state_action_planner_suppressed_for_status_query"
    if tool_name == "plan_device_status_lookup":
        if not _direct_status_lookup_enabled():
            return False, "direct_status_lookup_disabled"
        return False, "device_status_lookup_requires_visible_context"

    if tool_name == "prepare_reminder_creation_args":
        if is_insufficient:
            return False, "reminder_creation_args_suppressed_insufficient_information"
        if (
            "low_battery_mode" in name or "wifi_off" in name or "location_off" in name
        ) and not reminder_creation_with_service_precondition:
            return (
                False,
                "reminder_creation_args_suppressed_for_service_precondition_task",
            )
        birth_scenario = (entry.birth_scenario or "").strip().lower()
        if birth_scenario and name == birth_scenario:
            return True, "birth_scenario_fair_chance_exact"
        creation_signals = ("add_reminder", "remind", "create_reminder", "set_reminder")
        suppress_signals = (
            "modify_reminder",
            "search_reminder",
            "update_reminder",
            "delete_reminder",
        )
        if any(token in name for token in suppress_signals):
            return False, "reminder_creation_args_suppressed_non_creation_task"
        if any(token in name for token in creation_signals):
            return _reminder_creation_args_task_route(name)
        return False, "reminder_creation_args_no_creation_signal"

    if tool_name == "extract_service_answer_field":
        if is_insufficient:
            return False, "service_answer_extractor_suppressed_insufficient_information"
        if name.startswith(("find_temperature", "find_temperature_f_with_location")):
            return False, "service_answer_extractor_suppressed_temperature_unit_task"
        if name.startswith(
            (
                "convert_currency",
                "find_distance_with_location_name",
                "find_phone_number_with_location_name",
            )
        ):
            return True, "external_service_answer_extraction_task"
        return False, "service_answer_extractor_requires_external_lookup_task"

    if entry.tool.spec.family == ToolFamily.VALIDATION_ABSTENTION_HELPER:
        if is_insufficient and name.startswith(
            ("search_contact", "search_message", "search_reminder")
        ):
            return True, "abstention_guard_insufficient_search_task"

    birth_fair_chance = _birth_scenario_fair_chance_visibility(entry, name)
    if birth_fair_chance is not None:
        return birth_fair_chance

    if tool_name == "relative_day_time_to_timestamp" and name.startswith(
        "modify_reminder_with_recency_latest"
    ):
        if is_insufficient:
            return False, "relative_time_suppressed_for_insufficient_information"
        return True, "relative_time_modify_latest_reminder"

    generic_route = score_registry_entry_for_scenario(entry, scenario_name)
    if generic_route.status in {"shown", "hidden"}:
        return generic_route.visible, generic_route.reason

    if tool_name == "relative_day_time_to_timestamp":
        if name.startswith("add_reminder_content_and_date_and_time"):
            return False, "relative_time_suppressed_for_absolute_date_task"
        if name.startswith("modify_reminder_with_recency_latest"):
            return True, "relative_time_modify_latest_reminder"
        if name.startswith("add_reminder_content_and_week_delta"):
            return True, "relative_time_add_reminder_week_delta_task"
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
                    "search_message_with_recency_latest",
                    "search_message_with_recency_oldest",
                )
            ):
                return True, "message_timestamp_extreme_selection_required"
            return False, "timestamp_extreme_suppressed_outside_message_ranking_tasks"
        if tool_name == "select_message_content_by_recency":
            if "insufficient_information" not in name and name.startswith(
                (
                    "search_message_with_recency_latest",
                    "search_message_with_recency_oldest",
                )
            ):
                return True, "message_content_recency_selection_required"
            return False, "message_content_selector_suppressed_outside_recency_tasks"
        if tool_name == "select_self_message_by_timestamp":
            return False, "self_message_selector_suppressed_empty_input_misuse"
        return _provisional_birth_family_visibility(entry, name)

    if entry.tool.spec.family == ToolFamily.CANONICALIZER:
        return _provisional_birth_family_visibility(entry, name)

    if (
        entry.tool.spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR
        and entry.tool.spec.required_original_tool_calls
        and generic_route.status == "defer"
    ):
        return False, "derived_calculator_requires_trigger_or_family_match"

    # Supplementary trigger-based fallback: checked after all hardcoded routes.
    trigger_result = _trigger_based_visibility(entry, name)
    if trigger_result is not None:
        return trigger_result

    if entry.tool.spec.positive_triggers or entry.tool.spec.applicable_task_families:
        return False, "explicit_contract_requires_trigger_or_family_match"

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


def load_tool_lifecycle_routing_state(registry_root: Path) -> dict[str, dict[str, Any]]:
    """Load self-evolution lifecycle state written next to an experimental registry."""
    lifecycle_path = registry_root / "tool_lifecycle.json"
    if not lifecycle_path.exists():
        return {}
    try:
        payload = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    lifecycle = payload.get("tool_lifecycle", {})
    if not isinstance(lifecycle, dict):
        return {}
    return {
        str(tool_name): row
        for tool_name, row in lifecycle.items()
        if isinstance(row, dict)
    }


def _lifecycle_visibility_override(
    *,
    tool_name: str,
    scenario_name: str | None,
    lifecycle_state: dict[str, dict[str, Any]] | None,
) -> tuple[bool, str] | None:
    if not scenario_name or not lifecycle_state:
        return None
    row = lifecycle_state.get(tool_name)
    if not row:
        return None
    decision = str(row.get("decision") or "")
    if decision in {"park", "parked"}:
        return False, "lifecycle_suppressed_parked_tool"

    scenario_family = base_task_family(scenario_name)
    route_repair_families = {
        str(item) for item in row.get("route_repair_families", []) if item
    }
    harmful_scenarios = [
        str(item) for item in row.get("harmful_called_scenarios", []) if item
    ]
    helpful_count = row.get("helpful_called_count")
    harmful_count = row.get("harmful_called_count")
    try:
        helpful_count_int = int(helpful_count)
    except (TypeError, ValueError):
        helpful_count_int = len(row.get("helpful_called_scenarios", []) or [])
    try:
        harmful_count_int = int(harmful_count)
    except (TypeError, ValueError):
        harmful_count_int = len(harmful_scenarios)
    helpful_families = [
        str(item) for item in row.get("helpful_called_families", []) if item
    ]
    harmful_families_list = [
        str(item) for item in row.get("harmful_called_families", []) if item
    ]
    if not harmful_families_list:
        harmful_families_list = harmful_scenarios
    if not helpful_families:
        helpful_families = [
            str(item) for item in row.get("helpful_called_scenarios", []) if item
        ]

    def same_family(value: str) -> bool:
        family = str(value or "")
        return family == scenario_family or base_task_family(family) == scenario_family

    harmful_family_count = sum(1 for item in harmful_families_list if same_family(item))
    helpful_family_count = sum(1 for item in helpful_families if same_family(item))
    is_validation_abstention_tool = tool_name == "prepare_safe_action_or_abstain"
    if is_validation_abstention_tool:
        try:
            side_effect_incident_count = int(row.get("side_effect_incident_count") or 0)
        except (TypeError, ValueError):
            side_effect_incident_count = 0
        try:
            failed_count = int(row.get("failed_count") or 0)
        except (TypeError, ValueError):
            failed_count = 0
        operationally_clean = side_effect_incident_count == 0 and failed_count == 0
    else:
        operationally_clean = False

    if decision == "retain_with_route_repair":
        if is_validation_abstention_tool and operationally_clean:
            return None
        if scenario_name in harmful_scenarios:
            return False, "lifecycle_suppressed_exact_harmful_called_scenario"
        if (
            harmful_family_count >= 2
            and harmful_family_count > helpful_family_count
            and scenario_family in route_repair_families
        ):
            return False, "lifecycle_suppressed_harmful_called_family"
        return None

    if scenario_family in route_repair_families:
        if is_validation_abstention_tool and operationally_clean:
            return None
        if harmful_family_count < 2 and not (
            is_validation_abstention_tool and not operationally_clean
        ):
            return None
        if harmful_family_count and harmful_family_count <= helpful_family_count:
            return None
        return False, "lifecycle_suppressed_harmful_called_family"
    if decision not in {
        "needs_route_repair",
        "needs_repair",
    }:
        return None

    harmful_families = {base_task_family(str(item)) for item in harmful_families_list}
    if scenario_family in harmful_families:
        if is_validation_abstention_tool and operationally_clean:
            return None
        if (
            harmful_family_count < 2
            and harmful_count_int < 2
            and not (is_validation_abstention_tool and not operationally_clean)
        ):
            return None
        return False, "lifecycle_suppressed_harmful_called_family"
    return None


def _visible_signal_can_override_lifecycle_family_suppression(
    *,
    tool_name: str,
    generic_decision: RuntimeRoutingDecision,
    lifecycle_state: dict[str, dict[str, Any]] | None,
) -> bool:
    """Let strict visible-context evidence repair coarse lifecycle suppression.

    Lifecycle feedback is allowed to suppress tools after harmful calls, but a
    broad family label is intentionally coarse. If a retained tool is validated,
    operationally clean, and the current task text/tools/signals explicitly
    match that tool, the visible route is the more specific self-evolution
    signal. Parked tools and tools needing implementation repair remain hidden.
    """
    if not lifecycle_state:
        return False
    if not generic_decision.visible:
        return False
    if generic_decision.reason != "visible_context_signal_match":
        return False
    row = lifecycle_state.get(tool_name)
    if not row:
        return False
    if str(row.get("decision") or "") != "retain_with_route_repair":
        return False
    for key in ("failed_count", "side_effect_incident_count"):
        try:
            if int(row.get(key) or 0) > 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _abstention_guard_call_would_be_scored_as_forbidden_action(
    entry: RegistryEntry,
    scenario_name: str | None,
    available_base_tools: set[str] | None,
) -> bool:
    """Avoid executable abstention helpers on no-tool guardrail lanes.

    Some ToolSandbox insufficient-information tasks grade the absence of an
    execution-environment action. In those lanes, calling even a side-effect-free
    generated validation tool can be counted as the forbidden action if its
    arguments necessarily name that action. Suppress the executable helper when
    the original side-effect tool is visible but its required producer/search
    precondition is absent; the actor can still abstain without any tool call.
    """
    if not scenario_name or available_base_tools is None:
        return False
    scenario_lower = scenario_name.lower()
    if "insufficient_information" not in scenario_lower:
        return False
    if not _is_insufficient_information_guard(entry.tool.spec):
        return False
    available = {str(tool) for tool in available_base_tools}
    if (
        "remove_contact" in available
        and "search_contacts" not in available
        and "remove_contact" in scenario_lower
    ):
        return True
    if (
        "modify_contact" in available
        and "search_contacts" not in available
        and "modify_contact" in scenario_lower
    ):
        return True
    if (
        "modify_contact" in available
        and "search_messages" not in available
        and "message_recency" in scenario_lower
    ):
        # Message-recency contact updates are unsafe without message history. The
        # validation abstention tool is the generated-tool mechanism that prevents
        # guessed modify_contact calls in this lane, so keep it visible.
        return False
    if (
        "send_message_with_phone_number" in available
        and "search_contacts" not in available
        and "send_message" in scenario_lower
    ):
        # Named-recipient send tasks are unsafe when the actor has a send tool
        # but no contact lookup. The generated validation tool now uses
        # semantic capability labels instead of original side-effect tool names,
        # so keeping it visible routes the actor away from guessing a name as a
        # phone number without adding a synthetic completion path.
        return False
    if (
        "remove_reminder" in available
        and "search_reminder" not in available
        and "remove_reminder" in scenario_lower
    ):
        return True
    if (
        "modify_reminder" in available
        and "search_reminder" not in available
        and "modify_reminder" in scenario_lower
    ):
        return True
    return False


def _generated_tool_substitutes_available_original(
    entry: RegistryEntry,
    available_base_tools: set[str] | None,
) -> bool:
    """Suppress generated substitutes when the original operation is available.

    Clean primary evidence should favor generated tools that add a missing
    deterministic capability, prepare arguments, select records, or route
    downstream original tools. If a generated tool contract explicitly says it
    replaces an expected original route call, keep it hidden whenever that
    original call is already in the task's base toolset.
    """
    if available_base_tools is None:
        return False
    replaced = {
        str(tool_name)
        for tool_name in entry.tool.spec.expected_milestone_calls_replaced
        if str(tool_name)
    }
    return bool(replaced & {str(tool_name) for tool_name in available_base_tools})


def route_registry_entries(
    entries: dict[str, RegistryEntry],
    scenario_name: str | None,
    *,
    max_bundle_size: int = DEFAULT_MAX_RUNTIME_BUNDLE_SIZE,
    available_base_tools: set[str] | None = None,
    lifecycle_state: dict[str, dict[str, Any]] | None = None,
    task_context_text: str | None = None,
    task_family_key: str | None = None,
) -> tuple[list[RegistryEntry], dict[str, RuntimeRoutingDecision]]:
    """Select a bounded runtime helper bundle and explain each routing decision."""
    max_bundle_size = _runtime_generated_tool_bundle_size(max_bundle_size)
    decisions: dict[str, RuntimeRoutingDecision] = {}
    visible: list[tuple[int, str, RegistryEntry]] = []
    scenario_lower = (scenario_name or "").lower()
    routing_lower = (task_context_text or scenario_name or "").lower()
    prefer_message_content_selector = (
        "select_message_content_by_recency" in entries
        and "insufficient_information" not in routing_lower
        and (
            (task_context_text is not None and "message_recency" in routing_lower)
            or (
                task_context_text is None
                and scenario_lower.startswith(
                    (
                        "search_message_with_recency_latest",
                        "search_message_with_recency_oldest",
                    )
                )
            )
        )
    )
    generic_hard_blocks = {
        "blocked_by_negative_trigger",
        "blocked_by_visible_not_called_adoption_risk",
        "recency_action_selector_requires_recency_action_task",
        "side_effect_selector_suppressed_for_insufficient_information",
        "side_effect_composite_suppressed_for_insufficient_information",
        "derived_calculator_suppressed_for_insufficient_information",
        "post_selection_composite_requires_downstream_action_task",
    }
    for tool_name, entry in sorted(entries.items()):
        if task_context_text:
            generic = _visible_context_route_decision(
                entry,
                task_context_text=task_context_text,
                task_family_key=task_family_key,
            )
            is_visible = generic.visible
            reason = generic.reason
        elif _scenario_name_routing_disabled():
            generic = RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "missing_visible_task_context_no_scenario_routing",
                -30,
            )
            is_visible = False
            reason = generic.reason
        else:
            generic = score_registry_entry_for_scenario(entry, scenario_name)
            is_visible, reason = registry_entry_visibility_reason(entry, scenario_name)
        lifecycle_override = _lifecycle_visibility_override(
            tool_name=tool_name,
            scenario_name=task_family_key if task_context_text else scenario_name,
            lifecycle_state=lifecycle_state,
        )
        if lifecycle_override is not None:
            lifecycle_visible, lifecycle_reason = lifecycle_override
            if not (
                task_context_text
                and lifecycle_reason == "lifecycle_suppressed_harmful_called_family"
                and _visible_signal_can_override_lifecycle_family_suppression(
                    tool_name=tool_name,
                    generic_decision=generic,
                    lifecycle_state=lifecycle_state,
                )
            ):
                is_visible, reason = lifecycle_visible, lifecycle_reason
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
        if (
            entry.tool.spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR
            and len(downstream_tools) > 1
        ):
            # Generic derived extractors may preserve one of several producer
            # lookups depending on the scenario. Requiring all producers to be
            # available hides valid cross-family extractors before they get a
            # fair callability chance.
            requires_any_downstream = True
        if not downstream_tools:
            downstream_tools = set(entry.tool.spec.preserves_side_effect_tools)
        suppress_original_substitute = _generated_tool_substitutes_available_original(
            entry, available_base_tools
        )
        if (
            suppress_original_substitute
            and task_context_text
            and entry.tool.spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR
        ):
            suppress_original_substitute = False
        if is_visible and suppress_original_substitute:
            is_visible = False
            status = "hidden"
            reason = "generated_substitute_suppressed_original_available"
        if (
            is_visible
            and prefer_message_content_selector
            and tool_name == "select_record_by_timestamp_extreme"
        ):
            is_visible = False
            status = "hidden"
            reason = (
                "message_content_selector_preferred_over_generic_timestamp_selector"
            )
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
            if _abstention_guard_call_would_be_scored_as_forbidden_action(
                entry,
                task_context_text if task_context_text else scenario_name,
                available_base_tools,
            ):
                is_visible = False
                status = "hidden"
                reason = "abstention_guard_suppressed_for_no_tool_guardrail"
                missing = set()
            elif (
                "insufficient_information" in routing_lower
                and _is_insufficient_information_guard(entry.tool.spec)
            ):
                # Abstention guards prevent unsafe downstream calls on missing-info
                # tasks. They must not be hidden just because the original producer
                # or forbidden downstream tool is absent from this scenario allow-list.
                missing: set[str] = set()
            elif entry.tool.spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
                # State helpers emit the next original ToolSandbox side-effect call,
                # but the exact callable may be represented by scrambled execution
                # names or a bridge policy outside this static allow-list. Keep the
                # helper scenario-gated instead of treating a minimal/scrambled
                # allow-list as proof that the downstream action is impossible.
                missing = set()
            elif requires_any_downstream:
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
    if task_context_text:
        visible_by_tool = {tool_name: entry for _score, tool_name, entry in visible}
        suppressed_by_composite: dict[str, str] = {}
        for lower_tool_name, lower_entry in visible_by_tool.items():
            for composite_tool_name, composite_entry in visible_by_tool.items():
                if composite_tool_name == lower_tool_name:
                    continue
                if _composite_subsumes_lower_level_tool(
                    composite_entry,
                    lower_entry,
                    task_context_text=task_context_text,
                ):
                    suppressed_by_composite[lower_tool_name] = composite_tool_name
                    break
        if suppressed_by_composite:
            visible = [
                item for item in visible if item[1] not in suppressed_by_composite
            ]
            for lower_tool_name, composite_tool_name in suppressed_by_composite.items():
                prior = decisions[lower_tool_name]
                decisions[lower_tool_name] = RuntimeRoutingDecision(
                    tool_name=lower_tool_name,
                    visible=False,
                    status="deprioritized",
                    reason=(
                        "composite_generated_tool_preferred_over_redundant_"
                        f"lower_level_tool:{composite_tool_name}"
                    ),
                    score=prior.score,
                    matched_positive_triggers=prior.matched_positive_triggers,
                    matched_negative_triggers=prior.matched_negative_triggers,
                    matched_task_families=prior.matched_task_families,
                    fair_chance_candidate=prior.fair_chance_candidate,
                    fair_chance_reason=prior.fair_chance_reason,
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
        "policy_version": "v8_visible_context_routing",
        "helper_triggers": HELPER_TRIGGERS,
        "visibility_source": inspect.getsource(registry_entry_visibility_reason),
        "route_registry_entries_source": inspect.getsource(route_registry_entries),
        "visible_context_source": inspect.getsource(_visible_context_route_decision),
        "composite_preference_source": inspect.getsource(
            _composite_subsumes_lower_level_tool
        ),
        "visible_context_tool_signals": VISIBLE_CONTEXT_TOOL_SIGNALS,
        "abstention_guard_source": inspect.getsource(
            _abstention_guard_call_would_be_scored_as_forbidden_action
        ),
        "provisional_source": inspect.getsource(_provisional_birth_family_visibility),
        "lifecycle_source": inspect.getsource(_lifecycle_visibility_override),
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
    if tool_name == "extract_stock_symbol":
        return False, "stock_symbol_requires_visible_context_signal"
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
    task_context_text: str | None = None,
    task_family_key: str | None = None,
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
        lifecycle_state=load_tool_lifecycle_routing_state(store.root),
        task_context_text=task_context_text,
        task_family_key=task_family_key,
    )
    inject_registry_tools_into_context(
        scenario_copy.starting_context,
        entries,
        on_reuse=on_reuse,
    )
    return scenario_copy
