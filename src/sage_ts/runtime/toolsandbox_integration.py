"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import re
from collections.abc import Iterable, Mapping, MutableMapping
from pathlib import Path
from typing import Any, Callable, Literal, cast

from sage_ts.evaluation.task_strata import base_task_family
from sage_ts.generation.complete_tools import (
    COMPLETE_TOOLS_NATIVE_NAMES,
    native_action_names_for_tool,
    native_action_tool_enabled,
)
from sage_ts.generation.tool_spec import ToolFamily, ToolSpec
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.routing_scorer import (
    DEFAULT_MAX_RUNTIME_BUNDLE_SIZE,
    RuntimeRoutingDecision,
    _is_insufficient_information_guard,
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
    "latitude": 0.0,
    "longitude": 0.0,
    "location_lookup_failed": False,
    "current_datetime_info": {},
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

MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE = 4


def _compact_text(text: object, *, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _runtime_generated_tool_bundle_size(default: int) -> int:
    return min(default, MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE)


def _dict_input_keys(entry: RegistryEntry) -> dict[str, tuple[str, ...]]:
    """Return literal dict keys used by generated code as affordance hints."""
    keys_by_input: dict[str, tuple[str, ...]] = {}
    code = entry.tool.code
    for item in entry.tool.spec.inputs:
        if item.annotation != "dict":
            continue
        pattern = rf"{re.escape(item.name)}\[['\"]([^'\"]+)['\"]\]"
        get_pattern = rf"{re.escape(item.name)}\.get\(['\"]([^'\"]+)['\"]"
        keys = sorted(
            set(re.findall(pattern, code)) | set(re.findall(get_pattern, code))
        )
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
    supplied = kwargs.get(input_name)
    if isinstance(supplied, dict) and supplied:
        is_exact_visible_subset = all(
            key in payload and payload[key] == value for key, value in supplied.items()
        )
        if not is_exact_visible_subset:
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
    elif spec.tool_name == "plan_send_message_contact_lookup":
        lines.extend(
            [
                "    For named-recipient communication requests, call this generated tool before manually asking for a phone number.",
                "    Treat visible requests to send, text, message, ask, or tell a named person as message intents when message content is explicit.",
                "    Pass message_content only when the user supplied the content. Do not invent placeholders such as hello.",
                "    If message content is missing, ask the user for the message content before calling this generated tool.",
            ]
        )
    return "\n".join(lines)


def _native_action_google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    dict_input_keys = _dict_input_keys(entry)
    native_action_names = native_action_names_for_tool(entry.tool)
    lines = [
        (
            f"{spec.description} This generated composite completes one final "
            "action by delegating to an approved native ToolSandbox tool. The "
            "native tool remains the state-changing implementation. If this "
            "tool confirms success, do not repeat the native action."
        ),
        "",
        "Args:",
    ]
    for item in spec.inputs:
        description = item.description
        if item.name == "action_type" and native_action_names:
            description = (
                "Choose exactly one validated native action name: "
                f"{', '.join(native_action_names)}. Match both parts of the "
                "name to the visible request: the prefix identifies the "
                "operation (for example, modify or remove), and the suffix "
                "identifies the record type (for example, contact or reminder). "
                "Never choose an action for a different record type."
            )
        elif item.name == "timestamp_key":
            description = (
                f"{description} Choose the visible field that matches the user's "
                "recency basis: use a creation/history timestamp for the most "
                "recently created record, and use a scheduled/due timestamp only "
                "for next, upcoming, or due-time selection."
            )
        elif item.name == "updates":
            description = (
                f"{description} Include only writable values requested by the user. "
                "Never include a target identifier or any key ending in _id; the "
                "tool must derive identity from its selected visible record."
            )
        elif item.annotation == "list":
            description = (
                f"{description} Pass the complete visible record list from the "
                "preceding read or search result. Use the records' visible "
                "identifier fields to determine their record type."
            )
        elif item.annotation == "dict":
            expected_keys = dict_input_keys.get(item.name, ())
            key_note = (
                f" Use only these accepted keys: {', '.join(expected_keys)}."
                if expected_keys
                else ""
            )
            description = (
                f"{description} Pass a JSON object containing every concrete "
                "field requested by the user; do not omit this mapping."
                f"{key_note}"
            )
        elif "self" in item.name and item.name.endswith("_id"):
            description = (
                f"{description} Use only a self identifier returned by a visible "
                "lookup; do not guess it."
            )
        lines.append(f"    {item.name}: {description}")
    if native_action_names:
        lines.extend(
            [
                "",
                "Validated native actions:",
                *(
                    f"    - {name}: use only when the visible request calls for "
                    f"{name.replace('_', ' ')}."
                    for name in native_action_names
                ),
            ]
        )
    lines.extend(
        [
            "",
            "Returns:",
            "    dict: Native action result and confirmation, or an abstention.",
        ]
    )
    if spec.negative_triggers:
        lines.extend(["", "Do not use when:"])
        lines.extend(f"    - {trigger}" for trigger in spec.negative_triggers)
    return "\n".join(lines)


def _google_docstring(entry: RegistryEntry) -> str:
    if native_action_tool_enabled(entry.tool):
        return _native_action_google_docstring(entry)
    return _compact_google_docstring(entry)


def compile_toolsandbox_tool(entry: RegistryEntry) -> Callable[..., Any]:
    """Compile an accepted registry entry into a ToolSandbox-visible callable."""
    return _compile_toolsandbox_tool(entry, on_reuse=None)


def _current_tool_trace_count() -> int:
    try:
        sandbox = get_current_context().get_database(DatabaseNamespace.SANDBOX)
        traces = sandbox["tool_trace"][0]
    except (IndexError, KeyError, TypeError):
        return 0
    return 0 if traces is None else len(traces)


def _literal_string_values(node: ast.AST) -> tuple[str, ...]:
    """Return a finite string collection encoded directly in generated code."""

    if isinstance(node, ast.Dict):
        elements = node.keys
    elif isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        elements = node.elts
    else:
        return ()
    values = tuple(
        element.value
        for element in elements
        if isinstance(element, ast.Constant)
        and isinstance(element.value, str)
        and element.value
    )
    return values if len(values) == len(elements) else ()


def _generated_finite_string_input_domains(
    entry: RegistryEntry,
) -> dict[str, tuple[str, ...]]:
    """Infer authoritative finite input domains from model-authored guards.

    A guard such as ``if target not in {"a", "b"}: return abstain`` defines
    the callable contract more precisely than a plain ``str`` annotation.
    Exposing that model-authored domain as ``Literal`` lets the actor supply a
    valid value without changing the generated implementation.
    """

    string_inputs = {
        item.name for item in entry.tool.spec.inputs if item.annotation == "str"
    }
    if not string_inputs:
        return {}
    try:
        tree = ast.parse(entry.tool.code)
    except SyntaxError:
        return {}

    domains: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], ast.NotIn) or len(node.comparators) != 1:
            continue
        if not isinstance(node.left, ast.Name) or node.left.id not in string_inputs:
            continue
        values = _literal_string_values(node.comparators[0])
        if not 2 <= len(values) <= 16:
            continue
        current = domains.setdefault(node.left.id, [])
        for value in values:
            if value not in current:
                current.append(value)
    return {name: tuple(values) for name, values in domains.items()}


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
        trace_count_before = _current_tool_trace_count()
        try:
            result = _inner(*args, **kwargs)
        except TypeError as error:
            try:
                result = _missing_argument_abstain_result(entry, error)
            except TypeError:
                result = _invalid_input_abstain_result(entry, error, kwargs)
        result = normalize_generated_tool_output(entry.tool, result, inputs=kwargs)
        native_trace_preserved = (
            native_action_tool_enabled(entry.tool)
            and _current_tool_trace_count() > trace_count_before
        )
        if not native_trace_preserved:
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
    finite_string_domains = _generated_finite_string_input_domains(entry)
    for input_name, allowed_values in finite_string_domains.items():
        annotations[input_name] = Literal.__getitem__(allowed_values)
    native_action_names = native_action_names_for_tool(entry.tool)
    if native_action_tool_enabled(entry.tool) and native_action_names:
        for item in entry.tool.spec.inputs:
            if item.name == "action_type" and item.annotation == "str":
                annotations[item.name] = Literal.__getitem__(native_action_names)
    if entry.tool.spec.output_annotation in PYTHON_TYPES:
        annotations["return"] = PYTHON_TYPES[entry.tool.spec.output_annotation]
    fn.__annotations__ = annotations
    fn.__doc__ = _google_docstring(entry)
    fn.__module__ = "sage_ts.generated_tools"
    fn.sage_native_action_delegation = native_action_tool_enabled(entry.tool)  # type: ignore[attr-defined]
    fn.sage_native_action_names = native_action_names  # type: ignore[attr-defined]
    fn.sage_generated_input_domains = finite_string_domains  # type: ignore[attr-defined]

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
    "plan_device_state_action_sequence_location_recovery": ("location_phrase",),
    "next_service_tool_call": ("state_precondition_possible",),
    "prepare_reminder_creation_args": ("reminder_create",),
    "relative_day_time_to_timestamp": ("relative_time",),
    "next_weekday_time_to_timestamp": ("weekday_time",),
    "prepare_location_search_args": (
        "location_phrase",
        "external_lookup",
    ),
    "prepare_specific_location_search_args": (
        "location_phrase",
        "external_lookup",
    ),
    "prepare_broad_location_search_args": (
        "location_phrase",
        "external_lookup",
    ),
    "prepare_add_contact_args": ("add_contact",),
    "prepare_direct_contact_action_args": ("direct_contact_action",),
    "plan_contact_lookup_query": ("contact_lookup",),
    "plan_send_message_contact_lookup": ("named_message_recipient",),
    "plan_contact_relationship_batch_update": ("relationship_batch_update",),
    "select_message_counterparty_for_contact_update": (
        "contact_lookup",
        "message_counterparty_lookup",
        "message_counterparty_update",
    ),
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
    "extract_address_result": ("service_answer_extraction",),
    "extract_converted_amount_result": ("service_answer_extraction",),
    "extract_phone_number_result": ("service_answer_extraction",),
    "extract_distance_result": ("service_answer_extraction",),
    "extract_temperature_result": ("service_answer_extraction",),
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
    if native_action_tool_enabled(composite.tool):
        if native_action_tool_enabled(lower_level.tool):
            return False
        composite_inputs = _tool_spec_input_names(composite_spec)
        lower_inputs = _tool_spec_input_names(lower_spec)
        composite_targets = _tool_spec_side_effect_targets(composite_spec)
        lower_targets = _tool_spec_side_effect_targets(lower_spec)
        return bool(
            "records" in composite_inputs
            and "records" in lower_inputs
            and "selection_mode" in lower_inputs
            and lower_spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER
            and composite_targets
            and lower_targets
            and composite_targets & lower_targets
        )
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


_VISIBLE_ABSOLUTE_DATE_RE = re.compile(
    r"\b(?:"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}"
    r")\b",
    re.IGNORECASE,
)

_VISIBLE_LAT_LON_REQUEST_RE = re.compile(
    r"\b(?:lat(?:itude)?|lattitude)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?"
    r".{0,80}\b(?:lon(?:gitude)?|lng)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?|"
    r"\b(?:lon(?:gitude)?|lng)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?"
    r".{0,80}\b(?:lat(?:itude)?|lattitude)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?",
    re.IGNORECASE,
)


def _visible_reverse_geocode_context(match_context: str) -> bool:
    """Detect visible address-from-coordinate tasks without using scenario names."""

    if not _VISIBLE_LAT_LON_REQUEST_RE.search(match_context):
        return False
    return any(
        token in match_context
        for token in (
            " address ",
            "address of",
            "what is the address",
            "where is",
            "location of",
        )
    )


_LOCATION_QUALIFIER_RE = re.compile(
    r"\b(?:"
    r"\d+|"
    r"street|st|avenue|ave|boulevard|blvd|road|rd|drive|dr|lane|ln|"
    r"way|court|ct|place|pl|parkway|pkwy|highway|hwy|suite|ste|"
    r"north|south|east|west|northeast|northwest|southeast|southwest|"
    r"airport|station|mall|plaza|square|center|centre|campus|downtown|"
    r"creek|valley|village|market street"
    r")\b",
    re.IGNORECASE,
)

_LOCATION_TEMPORAL_TAIL_RE = re.compile(
    r"\b(?:"
    r"today|tomorrow|tonight|yesterday|"
    r"next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)|"
    r"at\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|"
    r"by\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?"
    r")\b.*$",
    re.IGNORECASE,
)


def _visible_request_from_routing_context(match_context: str) -> str:
    """Extract the visible user request from the routing context string."""

    if "request=" not in match_context:
        return match_context
    request = match_context.split("request=", 1)[1]
    for marker in (" tools=", " signals=", " family="):
        if marker in request:
            request = request.split(marker, 1)[0]
    return request.strip(" '\"")


def _clean_candidate_location_phrase(value: str) -> str:
    cleaned = _LOCATION_TEMPORAL_TAIL_RE.sub("", value)
    cleaned = re.sub(
        r"\b(?:when|once|after|before|if|and|then|please|thanks?)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _candidate_location_phrases_from_request(request_text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for marker in (" at ", " near ", " around ", " by ", " in "):
        start = 0
        while True:
            index = request_text.find(marker, start)
            if index < 0:
                break
            candidate = _clean_candidate_location_phrase(
                request_text[index + len(marker) :]
            )
            if candidate:
                phrases.append(candidate)
            start = index + len(marker)
    cleaned_request = _clean_candidate_location_phrase(request_text)
    if cleaned_request:
        phrases.append(cleaned_request)
    return tuple(dict.fromkeys(phrases))


def _unqualified_broad_location_phrase(phrase: str) -> bool:
    """Return true for broad visible place names that need location anchoring."""

    normalized = re.sub(r"[^a-z0-9\s]", " ", phrase.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return False
    if _LOCATION_QUALIFIER_RE.search(normalized):
        return False
    if " on " in f" {normalized} ":
        return False
    tokens = normalized.split()
    return 1 <= len(tokens) <= 3


def _broad_location_requires_coordinate_capable_tool(match_context: str) -> bool:
    request_text = _visible_request_from_routing_context(match_context)
    if not request_text:
        return False
    return any(
        _unqualified_broad_location_phrase(candidate)
        for candidate in _candidate_location_phrases_from_request(request_text.lower())
    )


def _pending_relative_time_route_allowed(
    tool_name: str,
    match_context: str,
) -> tuple[bool, tuple[str, ...]]:
    """Keep relative-time tools available when reminder timing may arrive later."""

    if tool_name != "relative_day_time_to_timestamp":
        return False, ()
    families = tuple(
        family
        for family in ("reminder_create", "reminder_modify")
        if family in match_context
    )
    if not families:
        return False, ()
    if "weekday_time" in match_context:
        return False, ()
    if _VISIBLE_ABSOLUTE_DATE_RE.search(match_context):
        return False, ()
    return True, families


def _pending_weekday_time_route_allowed(
    tool_name: str,
    match_context: str,
) -> tuple[bool, tuple[str, ...]]:
    """Keep weekday-time tools available when a reminder time may arrive later."""

    if tool_name != "next_weekday_time_to_timestamp":
        return False, ()
    families = tuple(
        family
        for family in ("reminder_create", "reminder_modify")
        if family in match_context
    )
    if not families:
        return False, ()
    if _VISIBLE_ABSOLUTE_DATE_RE.search(match_context):
        return False, ()
    return True, families


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
        pending_weekday_time, pending_weekday_families = (
            _pending_weekday_time_route_allowed(
                tool_name,
                match_context,
            )
        )
        if pending_weekday_time:
            return RuntimeRoutingDecision(
                tool_name,
                True,
                "shown",
                "visible_context_pending_weekday_time",
                8 + len(pending_weekday_families),
                matched_positive_triggers=pending_weekday_families,
                matched_task_families=pending_weekday_families,
            )
        pending_relative_time, pending_families = _pending_relative_time_route_allowed(
            tool_name,
            match_context,
        )
        if pending_relative_time:
            return RuntimeRoutingDecision(
                tool_name,
                True,
                "shown",
                "visible_context_pending_relative_time",
                8 + len(pending_families),
                matched_positive_triggers=pending_families,
                matched_task_families=pending_families,
            )
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
    if tool_name in {
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
        "prepare_broad_location_search_args",
    }:
        if _visible_reverse_geocode_context(match_context):
            return RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "location_search_args_suppressed_for_reverse_geocode_request",
                -30,
                matched_task_families=matched_signals,
            )
        broad_location_context = _broad_location_requires_coordinate_capable_tool(
            match_context
        )
        if (
            tool_name == "prepare_broad_location_search_args"
            and not broad_location_context
        ):
            return RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "broad_location_search_args_requires_unqualified_place_query",
                -25,
                matched_task_families=matched_signals,
            )
        if (
            tool_name
            in {"prepare_location_search_args", "prepare_specific_location_search_args"}
            and broad_location_context
        ):
            return RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "specific_location_search_args_suppressed_for_broad_place_query",
                -20,
                matched_task_families=matched_signals,
            )
        if broad_location_context and not {
            "latitude",
            "longitude",
        } <= _tool_spec_input_names(spec):
            return RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "location_search_args_broad_query_requires_coordinate_capable_tool",
                -35,
                matched_task_families=matched_signals,
            )
        if not (
            "reminder_create" in match_context
            or (
                "external_lookup" in match_context
                and "location_phrase" in match_context
            )
        ):
            return RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "location_search_args_requires_visible_place_query",
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
    service_scalar_requirements = {
        "extract_address_result": lambda text: _visible_reverse_geocode_context(text),
        "extract_converted_amount_result": lambda text: (
            "currency_lookup" in text
            or "convert" in text
            or any(code in text for code in (" usd", " eur", " cny", " gbp", " jpy"))
        ),
        "extract_phone_number_result": lambda text: "phone number" in text,
        "extract_distance_result": lambda text: any(
            token in text
            for token in (
                "how far",
                "distance",
                "how many km",
                "how many miles",
                "km to",
                "miles to",
            )
        ),
        "extract_temperature_result": lambda text: any(
            token in text
            for token in (
                "temperature",
                " temp ",
                "weather",
                "forecast",
                "celsius",
                "fahrenheit",
            )
        ),
    }
    if tool_name in service_scalar_requirements and not service_scalar_requirements[
        tool_name
    ](match_context):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "service_scalar_extractor_requires_matching_visible_request",
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
    harmful_count = row.get("harmful_called_count")
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
    task_context_text: str | None,
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
    if not task_context_text or available_base_tools is None:
        return False
    visible_context = task_context_text.lower()
    if "insufficient_information" not in visible_context:
        return False
    if not _is_insufficient_information_guard(entry.tool.spec):
        return False
    available = {str(tool) for tool in available_base_tools}
    if (
        "remove_contact" in available
        and "search_contacts" not in available
        and "remove_contact" in visible_context
    ):
        return True
    if (
        "modify_contact" in available
        and "search_contacts" not in available
        and "modify_contact" in visible_context
    ):
        return True
    if (
        "modify_contact" in available
        and "search_messages" not in available
        and "message_recency" in visible_context
    ):
        # Message-recency contact updates are unsafe without message history. The
        # validation abstention tool is the generated-tool mechanism that prevents
        # guessed modify_contact calls in this lane, so keep it visible.
        return False
    if (
        "send_message_with_phone_number" in available
        and "search_contacts" not in available
        and "send_message" in visible_context
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
        and "remove_reminder" in visible_context
    ):
        return True
    if (
        "modify_reminder" in available
        and "search_reminder" not in available
        and "modify_reminder" in visible_context
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
    routing_lower = (task_context_text or "").lower()
    prefer_message_content_selector = (
        "select_message_content_by_recency" in entries
        and "insufficient_information" not in routing_lower
        and "message_recency" in routing_lower
    )
    prefer_message_counterparty_update_selector = (
        "select_message_counterparty_for_contact_update" in entries
        and "insufficient_information" not in routing_lower
        and "message_counterparty_update" in routing_lower
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
        else:
            generic = RuntimeRoutingDecision(
                tool_name,
                False,
                "hidden",
                "missing_visible_task_context_no_scenario_routing",
                -30,
            )
            is_visible = False
            reason = generic.reason
        lifecycle_override = _lifecycle_visibility_override(
            tool_name=tool_name,
            scenario_name=task_family_key,
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
        if (
            is_visible
            and task_context_text
            and (
                "insufficient_information" in routing_lower
                or "insufficient information" in routing_lower
            )
            and entry.tool.spec.family != ToolFamily.VALIDATION_ABSTENTION_HELPER
        ):
            is_visible = False
            status = "hidden"
            reason = "generated_tool_suppressed_for_insufficient_information_context"
        downstream_tools = set(entry.tool.spec.required_original_tool_calls)
        requires_any_downstream = False
        raw_output_schema = entry.tool.spec.output_schema or {}
        output_schema = raw_output_schema if isinstance(raw_output_schema, dict) else {}
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
        if (
            is_visible
            and prefer_message_counterparty_update_selector
            and tool_name == "select_record_by_timestamp_extreme"
        ):
            is_visible = False
            status = "hidden"
            reason = "message_counterparty_selector_preferred_over_generic_timestamp_selector"
        if (
            is_visible
            and task_context_text
            and tool_name == "resolve_search_window_or_bounds"
            and "message_recency" in routing_lower
        ):
            is_visible = False
            status = "hidden"
            reason = "message_recency_uses_content_selector_not_search_window"
        if (
            is_visible
            and task_context_text
            and tool_name == "select_record_by_timestamp_extreme"
            and "message_recency" in routing_lower
        ):
            is_visible = False
            status = "hidden"
            reason = "message_recency_answer_requires_content_selector"
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
                task_context_text,
                available_base_tools,
            ):
                is_visible = False
                status = "hidden"
                reason = "abstention_guard_suppressed_for_no_tool_guardrail"
                missing = set()
            elif (
                "insufficient_information" in routing_lower
                or "safe_abstain_needed" in routing_lower
            ) and _is_insufficient_information_guard(entry.tool.spec):
                # Abstention guards prevent unsafe downstream calls on missing-info
                # and visible missing-precondition tasks. They must not be hidden
                # just because the original producer or forbidden downstream tool is
                # absent from this scenario allow-list.
                missing: set[str] = set()
            elif entry.tool.spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
                # State helpers emit the next original ToolSandbox side-effect call,
                # but the exact callable may be represented by scrambled execution
                # names or a bridge policy outside this static allow-list. Keep the
                # helper scenario-gated instead of treating a minimal/scrambled
                # allow-list as proof that the downstream action is impossible.
                missing = set()
            elif (
                len(
                    alternative_actions := (
                        downstream_tools & set(COMPLETE_TOOLS_NATIVE_NAMES)
                    )
                )
                > 1
            ):
                # A generated contract may support mutually exclusive native
                # actions. Require every producer dependency, but only one
                # compatible action. Complete tools are separately validated to
                # execute at most one native action per invocation.
                producer_dependencies = downstream_tools - alternative_actions
                missing = producer_dependencies - available_base_tools
                if not alternative_actions & available_base_tools:
                    missing.update(alternative_actions)
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
        if (
            "weekday_time" in routing_lower
            and "next_weekday_time_to_timestamp" in visible_by_tool
            and "relative_day_time_to_timestamp" in visible_by_tool
        ):
            suppressed_by_composite["relative_day_time_to_timestamp"] = (
                "next_weekday_time_to_timestamp"
            )
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
                        "more_specific_generated_tool_preferred_over_redundant_"
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
