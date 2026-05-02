import json
from pathlib import Path

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.toy_mechanism import canonicalizer_tool
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.toolsandbox_integration import (
    compile_toolsandbox_tool,
    inject_registry_tools_into_context,
    with_registry_tools,
)
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    ScenarioCategories,
    new_context,
)
from tool_sandbox.common.message_conversion import Message
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_conversion import convert_to_openai_tool
from tool_sandbox.roles.execution_environment import respond_to_single_message


def _registry_with_canonicalizer(tmp_path: Path) -> RegistryStore:
    tool = canonicalizer_tool()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular", held_out=True),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_state_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="next_service_tool_call",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description="Return the exact next ToolSandbox tool call and readiness predicate.",
        inputs=(
            ToolInput("target_service", "str", "Requested service."),
            ToolInput("wifi_enabled", "bool", "Whether Wi-Fi is already enabled."),
            ToolInput(
                "cellular_enabled", "bool", "Whether cellular is already enabled."
            ),
            ToolInput(
                "location_service_enabled",
                "bool",
                "Whether location service is already enabled.",
            ),
            ToolInput(
                "low_battery_mode", "bool", "Whether low battery mode is enabled."
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
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
                "ready": {"type": "boolean"},
            },
        },
        positive_triggers=("service_precondition_failure",),
        negative_triggers=("insufficient_information", "service_already_enabled"),
        preserves_side_effect_tools=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        required_original_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        abstain_behavior=(
            "Return should_call false with empty tool_name and arguments when the "
            "target is already enabled or the target service is unknown."
        ),
        generalization_rationale=(
            "Direct service-state scenarios repeatedly need a deterministic readiness "
            "predicate and exact benchmark tool call before finalizing."
        ),
        inadequacy_evidence=(
            "Base tools expose raw service setters/getters but not a reusable "
            "state-precondition decision helper that preserves trace compatibility."
        ),
    )
    code = """
def next_service_tool_call(target_service: str, wifi_enabled: bool, cellular_enabled: bool, location_service_enabled: bool, low_battery_mode: bool) -> dict:
    target = target_service.strip().lower()
    state_by_target = {
        "wifi": wifi_enabled,
        "cellular": cellular_enabled,
        "location": location_service_enabled,
    }
    if target not in state_by_target:
        return {"ready": False, "tool_name": "", "arguments": {}, "should_call": False, "reason": "unknown target service"}
    if state_by_target[target]:
        return {"ready": True, "tool_name": "", "arguments": {}, "should_call": False, "reason": f"{target} is already enabled"}
    if low_battery_mode:
        return {"ready": False, "tool_name": "set_low_battery_mode_status", "arguments": {"on": False}, "should_call": True, "reason": f"{target} cannot be enabled while low battery mode is on"}
    tool_by_target = {
        "wifi": "set_wifi_status",
        "cellular": "set_cellular_service_status",
        "location": "set_location_service_status",
    }
    return {"ready": False, "tool_name": tool_by_target[target], "arguments": {"on": True}, "should_call": True, "reason": f"{target} is disabled and must be enabled first"}
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "target_service": "wifi",
                    "wifi_enabled": False,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": True,
                },
                {
                    "ready": False,
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "wifi cannot be enabled while low battery mode is on",
                },
            ),
            ToolExample(
                {
                    "target_service": "cellular",
                    "wifi_enabled": True,
                    "cellular_enabled": False,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": False,
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "cellular is disabled and must be enabled first",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "target_service": "location",
                    "wifi_enabled": True,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": True,
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "location is already enabled",
                },
                negative_applicability=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_recency_bounds(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="recency_to_timestamp_bounds",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Convert a bounded recency label into timestamp bounds.",
        inputs=(
            ToolInput("recency_label", "str", "Bounded recency label."),
            ToolInput("current_timestamp", "float", "Current Unix timestamp."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "lower_bound": {"type": "number"},
                "upper_bound": {"type": "number"},
            },
        },
        generalization_rationale=(
            "Creation-recency search repeatedly needs deterministic timestamp bounds."
        ),
        inadequacy_evidence="The base tools expose timestamps but not recency bounds.",
    )
    code = """
def recency_to_timestamp_bounds(recency_label: str, current_timestamp: float) -> dict:
    if recency_label == "yesterday":
        return {"lower_bound": current_timestamp - 86400.0, "upper_bound": current_timestamp}
    return {"lower_bound": 0.0, "upper_bound": current_timestamp}
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {"recency_label": "yesterday", "current_timestamp": 172800.0},
                {"lower_bound": 86400.0, "upper_bound": 172800.0},
            ),
            ToolExample(
                {"recency_label": "today", "current_timestamp": 1000.0},
                {"lower_bound": 0.0, "upper_bound": 1000.0},
                held_out=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_latest_selector(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="select_latest_record_by_timestamp",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select the visible candidate record with the largest timestamp.",
        inputs=(
            ToolInput("records_payload", "dict", "Dict containing records list."),
            ToolInput("timestamp_key", "str", "Timestamp field to compare."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
            },
        },
        positive_triggers=("visible_candidate_list_wrong_selected_record",),
        negative_triggers=("no_valid_timestamp_candidates",),
        abstain_behavior=(
            "Return {} when no valid timestamped candidate exists or timestamp ties "
            "make the choice ambiguous."
        ),
        generalization_rationale=(
            "Latest-record tasks repeatedly require selecting the newest visible "
            "search result before using original ToolSandbox tools."
        ),
        inadequacy_evidence=(
            "Base search tools return records but do not provide a reusable "
            "timestamp-ranking helper."
        ),
    )
    code = """
def select_latest_record_by_timestamp(records_payload: dict, timestamp_key: str) -> dict:
    records = records_payload.get("records", [])
    best = {}
    best_value = None
    for record in records:
        if not isinstance(record, dict):
            continue
        value = record.get(timestamp_key)
        if not isinstance(value, (int, float)):
            continue
        if best_value is None or float(value) > best_value:
            best_value = float(value)
            best = dict(record)
    return best
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"content": "old", "creation_timestamp": 10.0},
                            {"content": "new", "creation_timestamp": 20.0},
                        ]
                    },
                    "timestamp_key": "creation_timestamp",
                },
                {"content": "new", "creation_timestamp": 20.0},
            ),
            ToolExample(
                {
                    "records_payload": {
                        "records": [
                            {"content": "older", "creation_timestamp": 5.0},
                            {"content": "newer", "creation_timestamp": 7.0},
                        ]
                    },
                    "timestamp_key": "creation_timestamp",
                },
                {"content": "newer", "creation_timestamp": 7.0},
                held_out=True,
            ),
            ToolExample(
                {
                    "records_payload": {"records": [{"content": "missing"}]},
                    "timestamp_key": "creation_timestamp",
                },
                {},
                negative_applicability=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_timestamp_extreme_selector(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="select_record_by_timestamp_extreme",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select the oldest or latest visible candidate by timestamp.",
        inputs=(
            ToolInput("records", "list", "Visible records returned by a search tool."),
            ToolInput("timestamp_key", "str", "Timestamp field to compare."),
            ToolInput("selection_mode", "str", "Either oldest or latest."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
            },
        },
        positive_triggers=("visible_candidate_list_wrong_selected_record",),
        negative_triggers=("no_valid_timestamp_candidates",),
        abstain_behavior=(
            "Return {} when no valid timestamped candidate exists or timestamp ties "
            "make the choice ambiguous."
        ),
        generalization_rationale=(
            "Oldest/latest record tasks repeatedly require deterministic timestamp "
            "ranking over visible search results before using original tools."
        ),
        inadequacy_evidence=(
            "Base search tools return records but not a reusable min/max timestamp "
            "selector for the returned candidates."
        ),
    )
    code = """
def select_record_by_timestamp_extreme(records: list, timestamp_key: str, selection_mode: str) -> dict:
    choose_oldest = str(selection_mode).strip().lower() == "oldest"
    best = {}
    best_value = None
    for record in records:
        if not isinstance(record, dict):
            continue
        value = record.get(timestamp_key)
        if not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if best_value is None or (numeric < best_value if choose_oldest else numeric > best_value):
            best_value = numeric
            best = dict(record)
    return best
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records": [
                        {"content": "old", "creation_timestamp": 10.0},
                        {"content": "new", "creation_timestamp": 20.0},
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "oldest",
                },
                {"content": "old", "creation_timestamp": 10.0},
            ),
            ToolExample(
                {
                    "records": [
                        {"content": "old", "creation_timestamp": 10.0},
                        {"content": "new", "creation_timestamp": 20.0},
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {"content": "new", "creation_timestamp": 20.0},
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [{"content": "missing"}],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {},
                negative_applicability=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_message_search_window(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="message_search_time_window",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Create broad timestamp bounds for benchmark message search.",
        inputs=(
            ToolInput("anchor_timestamp", "float", "Current or anchor Unix timestamp."),
            ToolInput("lookback_days", "int", "Days to include before the anchor."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "add_reminder_kwargs": {"type": "object"},
                "should_call_add_reminder": {"type": "boolean"},
                "should_retry_location_lookup": {"type": "boolean"},
                "location_status": {"type": "string"},
            },
        },
        positive_triggers=("optional_info_treated_as_required",),
        negative_triggers=("insufficient_information", "service_precondition_blocker"),
        preserves_side_effect_tools=("add_reminder",),
        required_original_tool_calls=("add_reminder",),
        abstain_behavior=(
            "Prepare add_reminder kwargs only; never perform reminder side effects "
            "inside the helper."
        ),
        generalization_rationale=(
            "Message workflows repeatedly need safe timestamp criteria before "
            "calling search_messages when no contact id or phone number is known."
        ),
        inadequacy_evidence=(
            "search_messages requires at least one criterion, so unconstrained "
            "latest/oldest message tasks need a reusable time-window helper."
        ),
    )
    code = """
def message_search_time_window(anchor_timestamp: float, lookback_days: int) -> dict:
    days = int(lookback_days)
    if days < 0:
        days = 0
    anchor = float(anchor_timestamp)
    return {
        "creation_timestamp_lowerbound": anchor - days * 86400.0,
        "creation_timestamp_upperbound": anchor,
    }
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "anchor_timestamp": 864000.0,
                    "lookback_days": 2,
                },
                {
                    "creation_timestamp_lowerbound": 691200.0,
                    "creation_timestamp_upperbound": 864000.0,
                },
            ),
            ToolExample(
                {
                    "anchor_timestamp": 1000.0,
                    "lookback_days": -1,
                },
                {
                    "creation_timestamp_lowerbound": 1000.0,
                    "creation_timestamp_upperbound": 1000.0,
                },
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_reminder_creation_args(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="prepare_reminder_creation_args",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Use this as the normal final step immediately before add_reminder "
            "on reminder-creation tasks once content and time are known. It "
            "prepares add_reminder kwargs, preserves the original benchmark "
            "side-effect call, and omits optional coordinates safely instead of "
            "blocking reminder creation."
        ),
        inputs=(
            ToolInput(
                "content",
                "str",
                "Exact reminder content to pass through to add_reminder.",
            ),
            ToolInput(
                "resolved_reminder_timestamp",
                "float",
                "Preferred whenever available. Pass the exact Unix reminder "
                "timestamp when it is already known from prior reasoning or "
                "tool results. If current benchmark timestamp context already "
                "makes the relative reminder time resolvable, prefer passing "
                "the resolved timestamp instead of asking the user for "
                "timezone or UTC offset again. Pass 0 only when the helper "
                "must compute from relative time fields instead.",
            ),
            ToolInput(
                "current_timestamp",
                "float",
                "Current Unix timestamp used only when computing from relative "
                "time fields.",
            ),
            ToolInput("day_offset", "int", "Local-day offset for the reminder date."),
            ToolInput("hour", "int", "Target local reminder hour."),
            ToolInput("minute", "int", "Target local reminder minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local UTC offset used for relative-time conversion. Use the "
                "existing ToolSandbox local timestamp context when it is "
                "already sufficient; do not ask the user for timezone again "
                "unless the request is truly ambiguous.",
            ),
            ToolInput(
                "time_fields_complete",
                "bool",
                "True only when day_offset, hour, minute, and "
                "local_utc_offset_hours are fully known and safe to use for "
                "add_reminder.",
            ),
            ToolInput(
                "location_requested",
                "bool",
                "True when the user mentioned a location and you would like to "
                "attach it if resolution succeeds. Mentioned does not mean "
                "required and does not block add_reminder.",
            ),
            ToolInput(
                "location_required",
                "bool",
                "True only when the user explicitly requires the reminder to "
                "include a location.",
            ),
            ToolInput(
                "location_available",
                "bool",
                "True only when both latitude and longitude are already available.",
            ),
            ToolInput("latitude", "float", "Latitude when coordinates are available."),
            ToolInput(
                "longitude",
                "float",
                "Longitude when coordinates are available.",
            ),
            ToolInput(
                "location_lookup_failed",
                "bool",
                "True when optional location lookup already failed and the "
                "helper should omit coordinates instead of blocking "
                "add_reminder. False does not require waiting: optional "
                "unresolved location may still be omitted if reminder creation "
                "is otherwise ready.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "add_reminder_kwargs": {"type": "object"},
                "should_call_add_reminder": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
                "location_status": {"type": "string"},
                "timestamp_source": {"type": "string"},
            },
            "required": [
                "add_reminder_kwargs",
                "should_call_add_reminder",
                "abstain_reason",
                "location_status",
                "timestamp_source",
            ],
        },
        positive_triggers=(
            "add_reminder",
            "optional_info_treated_as_required",
            "relative_time_needs_typed_kwargs",
        ),
        negative_triggers=(
            "modify_reminder",
            "search_reminder",
            "delete_reminder",
            "insufficient_information",
        ),
        preserves_side_effect_tools=("add_reminder",),
        required_original_tool_calls=("add_reminder",),
        abstain_behavior=(
            "Use this as the standard last step right before add_reminder. "
            "Return should_call_add_reminder=False only when time information "
            "is missing or malformed or when a user explicitly requires a "
            "location that is unresolved. Prefer "
            "resolved_reminder_timestamp whenever it is already available from "
            "prior tool results or existing timestamp context, and do not ask "
            "the user for timezone or UTC offset again when the current "
            "ToolSandbox timestamp context is already sufficient. Optional "
            "unresolved location should not block reminder creation. If "
            "should_call_add_reminder=True, call add_reminder with "
            "add_reminder_kwargs unchanged."
        ),
        generalization_rationale=(
            "Reminder creation tasks need a deterministic final preparation step "
            "before add_reminder so the agent can stop re-asking for optional "
            "location details, stop retrying failed location lookup, and still "
            "call the original ToolSandbox side-effect tool."
        ),
        inadequacy_evidence=(
            "Agents repeatedly retry optional location lookup, ask unnecessary "
            "clarifications, or prepare incorrect timestamps before calling "
            "add_reminder."
        ),
    )
    code = """
def prepare_reminder_creation_args(content: str, resolved_reminder_timestamp: float, current_timestamp: float, day_offset: int, hour: int, minute: int, local_utc_offset_hours: float, time_fields_complete: bool, location_requested: bool, location_required: bool, location_available: bool, latitude: float, longitude: float, location_lookup_failed: bool) -> dict:
    timestamp_source = "none"
    if float(resolved_reminder_timestamp) > 0:
        reminder_timestamp = float(resolved_reminder_timestamp)
        timestamp_source = "resolved"
    else:
        if not time_fields_complete:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "abstain_reason": "missing_time_info",
                "location_status": "omitted_optional",
                "timestamp_source": timestamp_source,
            }
        if int(hour) < 0 or int(hour) > 23 or int(minute) < 0 or int(minute) > 59:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "abstain_reason": "malformed_time_info",
                "location_status": "omitted_optional",
                "timestamp_source": timestamp_source,
            }
        offset_seconds = float(local_utc_offset_hours) * 3600.0
        local_seconds = float(current_timestamp) + offset_seconds
        local_midnight = int(local_seconds // 86400.0) * 86400.0
        reminder_timestamp = (
            local_midnight
            + int(day_offset) * 86400.0
            - offset_seconds
            + int(hour) * 3600.0
            + int(minute) * 60.0
        )
        timestamp_source = "relative_fields"
    coords_available = bool(location_available) and not (
        float(latitude) == 0.0 or float(longitude) == 0.0
    )
    if coords_available:
        latitude_out = float(latitude)
        longitude_out = float(longitude)
        location_status = "provided"
    elif bool(location_required):
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "abstain_reason": "required_location_unresolved",
            "location_status": "required_missing",
            "timestamp_source": timestamp_source,
        }
    else:
        latitude_out = None
        longitude_out = None
        location_status = "omitted_optional"
    return {
        "add_reminder_kwargs": {
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": latitude_out,
            "longitude": longitude_out,
        },
        "should_call_add_reminder": True,
        "abstain_reason": "",
        "location_status": location_status,
        "timestamp_source": timestamp_source,
    }
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "content": "Buy tickets",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Buy tickets",
                        "reminder_timestamp": 147600.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "omitted_optional",
                    "abstain_reason": "",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Team meeting",
                    "resolved_reminder_timestamp": 1777500000.0,
                    "current_timestamp": 1777428906.0,
                    "day_offset": 0,
                    "hour": 0,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": False,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Team meeting",
                        "reminder_timestamp": 1777500000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "omitted_optional",
                    "abstain_reason": "",
                    "timestamp_source": "resolved",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "content": "Arrive early",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 1777428906.194959,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": -4.0,
                    "time_fields_complete": True,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": True,
                    "latitude": 37.3237926356735,
                    "longitude": -122.03961770355414,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Arrive early",
                        "reminder_timestamp": 1777496400.0,
                        "latitude": 37.3237926356735,
                        "longitude": -122.03961770355414,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "provided",
                    "abstain_reason": "",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Whole Foods while low battery",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 864000.0,
                    "day_offset": 0,
                    "hour": 9,
                    "minute": 30,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Whole Foods while low battery",
                        "reminder_timestamp": 898200.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "omitted_optional",
                    "abstain_reason": "",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Meet at park",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 14,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": True,
                    "location_required": True,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "location_status": "required_missing",
                    "abstain_reason": "required_location_unresolved",
                    "timestamp_source": "relative_fields",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Dentist",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 0.0,
                    "day_offset": 0,
                    "hour": 0,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": False,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "location_status": "omitted_optional",
                    "abstain_reason": "missing_time_info",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Bad time",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 0.0,
                    "day_offset": 0,
                    "hour": 25,
                    "minute": 61,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "location_status": "omitted_optional",
                    "abstain_reason": "malformed_time_info",
                    "timestamp_source": "none",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Pick up package",
                    "resolved_reminder_timestamp": 0.0,
                    "current_timestamp": 0.0,
                    "day_offset": 0,
                    "hour": 12,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": True,
                    "latitude": 0.0,
                    "longitude": -122.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Pick up package",
                        "reminder_timestamp": 43200.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "omitted_optional",
                    "abstain_reason": "",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 1777687768.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "time_fields_complete": True,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Buy chocolate milk at Whole Foods",
                        "reminder_timestamp": 1777776000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "location_status": "omitted_optional",
                    "abstain_reason": "",
                    "timestamp_source": "resolved",
                },
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_relative_time_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="relative_day_time_to_timestamp",
        family=ToolFamily.CANONICALIZER,
        description="Convert relative local day/time into a timestamp.",
        inputs=(
            ToolInput("current_timestamp", "float", "Current timestamp."),
            ToolInput("day_offset", "int", "Days forward from today."),
            ToolInput("hour", "int", "Local hour."),
            ToolInput("minute", "int", "Local minute."),
            ToolInput("local_utc_offset_hours", "float", "Local UTC offset."),
        ),
        output_annotation="float",
        generalization_rationale="Reminder updates repeatedly need this conversion.",
        inadequacy_evidence="Agents miscompute local-day timestamp arithmetic.",
    )
    code = """
def relative_day_time_to_timestamp(current_timestamp: float, day_offset: int, hour: int, minute: int, local_utc_offset_hours: float) -> float:
    return float(current_timestamp + day_offset * 86400 + hour * 3600 + minute * 60 - local_utc_offset_hours * 3600)
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "current_timestamp": 1000.0,
                    "day_offset": 1,
                    "hour": 5,
                    "minute": 30,
                    "local_utc_offset_hours": 0.0,
                },
                107200.0,
            ),
            ToolExample(
                {
                    "current_timestamp": 1000.0,
                    "day_offset": 0,
                    "hour": 1,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                },
                4600.0,
                held_out=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_days_between_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="days_between_timestamps",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Compute day and second difference between two timestamps.",
        inputs=(
            ToolInput("timestamp_0", "float", "Timestamp to subtract."),
            ToolInput("timestamp_1", "float", "Timestamp to subtract from."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer"},
                "seconds": {"type": "integer"},
            },
        },
        generalization_rationale=(
            "Calendar-distance tasks repeatedly need deterministic day/second "
            "differences after retrieving current and target timestamps."
        ),
        inadequacy_evidence=(
            "The reduced base toolset removes timestamp_diff, leaving no direct "
            "deterministic difference helper."
        ),
    )
    code = """
def days_between_timestamps(timestamp_0: float, timestamp_1: float) -> dict:
    total_seconds = int(float(timestamp_1) - float(timestamp_0))
    days = total_seconds // 86400
    seconds = total_seconds - days * 86400
    return {"days": days, "seconds": seconds}
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {"timestamp_0": 0.0, "timestamp_1": 90061.0},
                {"days": 1, "seconds": 3661},
            ),
            ToolExample(
                {"timestamp_0": 86400.0, "timestamp_1": 86400.0},
                {"days": 0, "seconds": 0},
                held_out=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def _registry_with_contact_constraint_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="select_contact_field_by_constraint",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description="Select one contact by a normalized field constraint and return a requested field.",
        inputs=(
            ToolInput("records", "list", "Contact records."),
            ToolInput("match_field", "str", "Field to match."),
            ToolInput("expected_value", "str", "Expected field value."),
            ToolInput(
                "output_field", "str", "Field to return from the matched contact."
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "value": {},
            },
        },
        positive_triggers=("wrong_selected_record",),
        negative_triggers=("ambiguous_match", "no_match"),
        abstain_behavior=(
            "Return {} when there is not exactly one normalized match, ties remain, "
            "or the output field is unavailable."
        ),
        generalization_rationale="Contact lookup tasks repeatedly need one exact field from one record.",
        inadequacy_evidence="Agents confuse contact candidates, phone formatting, and target fields.",
    )
    code = """
def select_contact_field_by_constraint(records: list, match_field: str, expected_value: str, output_field: str) -> dict:
    matches = []
    expected = ''.join(filter(str.isdigit, expected_value)) if match_field == 'phone_number' else str(expected_value).strip().lower()
    for record in records:
        value = record.get(match_field)
        normalized = ''.join(filter(str.isdigit, str(value))) if match_field == 'phone_number' else str(value).strip().lower()
        if normalized == expected:
            matches.append(record)
    if len(matches) != 1 or output_field not in matches[0]:
        return {}
    return {'selected_record': matches[0], 'value': matches[0][output_field]}
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "person_id": "a",
                            "name": "Ada Lovelace",
                            "phone_number": "+1 (555) 0100",
                        }
                    ],
                    "match_field": "phone_number",
                    "expected_value": "15550100",
                    "output_field": "person_id",
                },
                {
                    "selected_record": {
                        "person_id": "a",
                        "name": "Ada Lovelace",
                        "phone_number": "+1 (555) 0100",
                    },
                    "value": "a",
                },
            ),
            ToolExample(
                {
                    "records": [],
                    "match_field": "name",
                    "expected_value": "Ada",
                    "output_field": "phone_number",
                },
                {},
                held_out=True,
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "a", "relationship": "friend"},
                        {"person_id": "b", "relationship": "friend"},
                    ],
                    "match_field": "relationship",
                    "expected_value": "friend",
                    "output_field": "person_id",
                },
                {},
                negative_applicability=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(
        RegistryEntry.accepted(
            tool,
            validation,
            birth_scenario="remove_contact_by_phone_3_distraction_tools",
        )
    )
    return store


def _registry_with_stock_symbol_helper(tmp_path: Path) -> RegistryStore:
    spec = ToolSpec(
        tool_name="extract_stock_symbol",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description="Extract a normalized stock symbol from a stock payload.",
        inputs=(ToolInput("stock_payload", "dict", "search_stock payload."),),
        output_annotation="str",
        generalization_rationale="Stock lookup tasks need the symbol field only.",
        inadequacy_evidence="Agents report extra fields or fail to strip exchange prefixes.",
    )
    code = """
def extract_stock_symbol(stock_payload: dict) -> str:
    value = stock_payload.get("symbol") if isinstance(stock_payload, dict) else ""
    return str(value).split(":")[-1] if isinstance(value, str) else ""
"""
    tool = GeneratedTool(spec=spec, code=code)
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"stock_payload": {"symbol": "NASDAQ:AAPL"}}, "AAPL"),
            ToolExample(
                {"stock_payload": {"symbol": "AAPL"}},
                "AAPL",
                held_out=True,
            ),
        ),
    )
    assert validation.accepted
    store = RegistryStore(tmp_path)
    store.put(
        RegistryEntry.accepted(
            tool,
            validation,
            birth_scenario="find_stock_symbol_with_company_name_3_distraction_tools",
        )
    )
    return store


def test_registry_tools_are_available_to_toolsandbox_context(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    tool_name = "canonicalize_connectivity_label"
    assert tool_name not in context.name_to_tool

    reused_tools: list[str] = []
    enhanced = Scenario(starting_context=context)
    inject_registry_tools_into_context(
        enhanced.starting_context,
        store.load_entries().values(),
        on_reuse=reused_tools.append,
    )

    assert tool_name in enhanced.starting_context.name_to_tool
    assert next(iter(enhanced.starting_context.name_to_tool)) == tool_name
    assert enhanced.starting_context.tool_allow_list is not None
    assert enhanced.starting_context.tool_allow_list[0] == tool_name

    available_tools = enhanced.starting_context.get_available_tools(
        scrambling_allowed=False
    )
    assert next(iter(available_tools)) == tool_name
    assert available_tools[tool_name]("Wi-Fi") == "wifi"
    assert reused_tools == [tool_name]

    openai_tool = convert_to_openai_tool(available_tools[tool_name], tool_name)
    parameters = openai_tool["function"]["parameters"]
    assert openai_tool["function"]["description"].startswith(
        "Normalize connectivity labels"
    )
    assert parameters["properties"]["label"]["type"] == "string"
    assert parameters["properties"]["label"]["description"] == (
        "Raw connectivity label."
    )
    assert parameters["required"] == ["label"]


def test_state_helpers_are_only_exposed_on_relevant_state_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_state_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest",
    )
    wifi_state = with_registry_tools(
        scenario,
        store,
        scenario_name="turn_on_wifi_low_battery_mode",
    )
    direct_state = with_registry_tools(
        scenario,
        store,
        scenario_name="turn_on_location_low_battery_mode",
    )
    downstream_state = with_registry_tools(
        scenario,
        store,
        scenario_name="find_temperature_low_battery_mode",
    )
    insufficient_information = with_registry_tools(
        scenario,
        store,
        scenario_name="find_current_city_low_battery_mode_insufficient_information",
    )

    assert "next_service_tool_call" not in unrelated.starting_context.name_to_tool
    assert "next_service_tool_call" in wifi_state.starting_context.name_to_tool
    assert "next_service_tool_call" in direct_state.starting_context.name_to_tool
    assert "next_service_tool_call" in downstream_state.starting_context.name_to_tool
    assert (
        "next_service_tool_call"
        not in insufficient_information.starting_context.name_to_tool
    )


def test_state_helper_openai_description_includes_single_target_guidance(
    tmp_path: Path,
) -> None:
    store = _registry_with_state_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )
    enhanced = with_registry_tools(
        scenario,
        store,
        scenario_name="turn_on_wifi_low_battery_mode",
    )

    openai_tool = convert_to_openai_tool(
        enhanced.starting_context.name_to_tool["next_service_tool_call"],
        "next_service_tool_call",
    )
    description = openai_tool["function"]["description"]

    assert "Use only for the single service you are actively trying to change." in (
        description
    )
    assert (
        "Do not call this helper for multiple alternative services in parallel."
        in description
    )


def test_latest_selector_only_exposed_on_latest_record_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_latest_selector(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_sender_phone_number_with_content",
    )
    latest = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_latest_10_distraction_tools",
    )
    modify_contact = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_contact_with_message_recency_10_distraction_tools",
    )

    tool_name = "select_latest_record_by_timestamp"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name not in latest.starting_context.name_to_tool
    assert tool_name in modify_contact.starting_context.name_to_tool

    openai_tool = convert_to_openai_tool(
        modify_contact.starting_context.name_to_tool[tool_name], tool_name
    )
    properties = openai_tool["function"]["parameters"]["properties"]
    assert properties["records_payload"]["type"] == "object"


def test_latest_selector_hidden_on_insufficient_information_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_latest_selector(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    insufficient = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest_insufficient_information",
    )

    assert (
        "select_latest_record_by_timestamp"
        not in insufficient.starting_context.name_to_tool
    )


def test_timestamp_extreme_selector_exposed_on_message_ranking_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_timestamp_extreme_selector(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    oldest = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_oldest_10_distraction_tools",
    )
    reminder_latest = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest_10_distraction_tools",
    )
    modify_contact = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_contact_with_message_recency_10_distraction_tools",
    )
    multi_turn = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_oldest_multiple_user_turn",
    )
    alt_variant = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_oldest_alt",
    )
    latest_message = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_latest_10_distraction_tools",
    )

    tool_name = "select_record_by_timestamp_extreme"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in oldest.starting_context.name_to_tool
    assert tool_name not in reminder_latest.starting_context.name_to_tool
    assert tool_name not in modify_contact.starting_context.name_to_tool
    assert tool_name not in multi_turn.starting_context.name_to_tool
    assert tool_name not in alt_variant.starting_context.name_to_tool
    assert tool_name in latest_message.starting_context.name_to_tool

    openai_tool = convert_to_openai_tool(
        latest_message.starting_context.name_to_tool[tool_name], tool_name
    )
    properties = openai_tool["function"]["parameters"]["properties"]
    assert properties["records"]["type"] == "array"
    assert properties["records"]["items"] == {}


def test_message_search_window_only_exposed_on_contact_message_tasks(
    tmp_path: Path,
) -> None:
    store = _registry_with_message_search_window(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    modify_contact = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_contact_with_message_recency_10_distraction_tools",
    )
    raw_latest_message = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_latest_10_distraction_tools",
    )
    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="remove_contact_by_phone_10_distraction_tools",
    )

    tool_name = "message_search_time_window"
    assert tool_name not in modify_contact.starting_context.name_to_tool
    assert tool_name not in raw_latest_message.starting_context.name_to_tool
    assert tool_name not in unrelated.starting_context.name_to_tool

    compiled = compile_toolsandbox_tool(next(iter(store.load_entries().values())))
    openai_tool = convert_to_openai_tool(compiled, tool_name)
    properties = openai_tool["function"]["parameters"]["properties"]
    assert properties["anchor_timestamp"]["type"] == "number"
    assert properties["lookback_days"]["type"] == "integer"


def test_reminder_creation_args_only_exposed_on_add_reminder_creation_tasks(
    tmp_path: Path,
) -> None:
    store = _registry_with_reminder_creation_args(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated_search = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_creation_recency_yesterday",
    )
    no_location = with_registry_tools(
        scenario,
        store,
        scenario_name="add_reminder_content_and_week_delta_and_time_3_distraction_tools",
    )
    insufficient = with_registry_tools(
        scenario,
        store,
        scenario_name=(
            "add_reminder_content_and_week_delta_and_time_and_location_insufficient_information"
        ),
    )
    modify = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest_alt",
    )
    service_precondition = with_registry_tools(
        scenario,
        store,
        scenario_name=(
            "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt"
        ),
    )
    applicable = with_registry_tools(
        scenario,
        store,
        scenario_name=(
            "add_reminder_content_and_week_delta_and_time_and_location_3_distraction_tools"
        ),
    )

    tool_name = "prepare_reminder_creation_args"
    assert tool_name not in unrelated_search.starting_context.name_to_tool
    assert tool_name in no_location.starting_context.name_to_tool
    assert tool_name not in insufficient.starting_context.name_to_tool
    assert tool_name not in modify.starting_context.name_to_tool
    assert tool_name in service_precondition.starting_context.name_to_tool
    assert tool_name in applicable.starting_context.name_to_tool
    reminder_helper = applicable.starting_context.name_to_tool[tool_name]
    assert "normal final step immediately before" in (reminder_helper.__doc__ or "")
    assert "add_reminder_kwargs" in (reminder_helper.__doc__ or "")
    assert "timezone or UTC offset again" in (reminder_helper.__doc__ or "")


def test_timestamp_extreme_selector_hidden_on_insufficient_information_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_timestamp_extreme_selector(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    insufficient = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_latest_insufficient_information",
    )

    assert (
        "select_record_by_timestamp_extreme"
        not in insufficient.starting_context.name_to_tool
    )


def test_relative_time_helper_only_exposed_on_relative_datetime_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_relative_time_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_message_with_recency_oldest_all_tools",
    )
    relative = with_registry_tools(
        scenario,
        store,
        scenario_name="modify_reminder_with_recency_latest_10_distraction_tools",
    )

    tool_name = "relative_day_time_to_timestamp"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in relative.starting_context.name_to_tool


def test_recency_bounds_helper_only_exposed_on_creation_recency_tasks(
    tmp_path: Path,
) -> None:
    store = _registry_with_recency_bounds(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    due_recency = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    creation_recency = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_creation_recency_yesterday",
    )
    insufficient = with_registry_tools(
        scenario,
        store,
        scenario_name=(
            "search_reminder_with_creation_recency_yesterday_insufficient_information"
        ),
    )

    tool_name = "recency_to_timestamp_bounds"
    assert tool_name not in due_recency.starting_context.name_to_tool
    assert tool_name in creation_recency.starting_context.name_to_tool
    assert tool_name not in insufficient.starting_context.name_to_tool


def test_calendar_distance_helper_only_exposed_on_holiday_scenarios(
    tmp_path: Path,
) -> None:
    store = _registry_with_days_between_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    holiday = with_registry_tools(
        scenario,
        store,
        scenario_name="find_days_till_holiday_3_distraction_tools",
    )

    tool_name = "days_between_timestamps"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in holiday.starting_context.name_to_tool


def test_contact_constraint_helper_is_suppressed_after_low_adoption(
    tmp_path: Path,
) -> None:
    store = _registry_with_contact_constraint_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    insufficient = with_registry_tools(
        scenario,
        store,
        scenario_name="remove_contact_by_phone_no_search_contacts_insufficient_information",
    )
    contact_lookup = with_registry_tools(
        scenario,
        store,
        scenario_name="remove_contact_by_phone_10_distraction_tools",
    )
    contact_search = with_registry_tools(
        scenario,
        store,
        scenario_name="search_phone_number_with_name_10_distraction_tools",
    )
    ambiguous = with_registry_tools(
        scenario,
        store,
        scenario_name="remove_contact_by_phone_ambiguous_10_distraction_tools",
    )

    tool_name = "select_contact_field_by_constraint"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name not in insufficient.starting_context.name_to_tool
    assert tool_name not in contact_lookup.starting_context.name_to_tool
    assert tool_name not in contact_search.starting_context.name_to_tool
    assert tool_name not in ambiguous.starting_context.name_to_tool


def test_stock_symbol_helper_only_exposed_on_stock_lookup(
    tmp_path: Path,
) -> None:
    store = _registry_with_stock_symbol_helper(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    stock = with_registry_tools(
        scenario,
        store,
        scenario_name="find_stock_symbol_with_company_name_low_battery_mode",
    )

    tool_name = "extract_stock_symbol"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in stock.starting_context.name_to_tool


def test_unknown_helpers_are_only_provisional_for_birth_family(
    tmp_path: Path,
) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    unrelated = with_registry_tools(
        scenario,
        store,
        scenario_name="search_reminder_with_recency_yesterday",
    )
    same_birth_family = with_registry_tools(
        scenario,
        store,
        scenario_name="toy_birth_3_distraction_tools",
    )

    tool_name = "canonicalize_connectivity_label"
    assert tool_name not in unrelated.starting_context.name_to_tool
    assert tool_name in same_birth_family.starting_context.name_to_tool


def test_registry_tools_execute_through_toolsandbox_console(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    reused_tools: list[str] = []
    enhanced = Scenario(starting_context=context)
    inject_registry_tools_into_context(
        enhanced.starting_context,
        store.load_entries().values(),
        on_reuse=reused_tools.append,
    )

    message = Message(
        sender=RoleType.AGENT,
        recipient=RoleType.EXECUTION_ENVIRONMENT,
        content=(
            "call_1_parameters = {'label': 'Wi-Fi'}\n"
            "call_1_response = canonicalize_connectivity_label(**call_1_parameters)\n"
            "print(repr(call_1_response))"
        ),
        openai_tool_call_id="call_1",
        openai_function_name="canonicalize_connectivity_label",
    )
    response = respond_to_single_message(
        enhanced.starting_context.interactive_console,
        message,
        RoleType.EXECUTION_ENVIRONMENT,
    )

    assert response is not None
    assert response.tool_call_exception is None
    assert response.content == "'wifi'"
    assert reused_tools == ["canonicalize_connectivity_label"]


def test_registry_tools_emit_toolsandbox_trace(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(tool_allow_list=["end_conversation"])
    enhanced = Scenario(starting_context=context)
    inject_registry_tools_into_context(
        enhanced.starting_context,
        store.load_entries().values(),
    )
    tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
        "canonicalize_connectivity_label"
    ]
    enhanced.starting_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.EXECUTION_ENVIRONMENT,
                "content": "canonicalize_connectivity_label(label='Wi-Fi')",
                "openai_tool_call_id": "call_1",
                "openai_function_name": "canonicalize_connectivity_label",
                "conversation_active": True,
                "tool_call_exception": None,
                "tool_trace": None,
                "visible_to": None,
            }
        ],
    )

    with new_context(enhanced.starting_context):
        enhanced.starting_context.trace_tool = True
        assert tool("Wi-Fi") == "wifi"
        trace_series = enhanced.starting_context.get_database(
            DatabaseNamespace.SANDBOX
        )["tool_trace"][0]

    traces = trace_series.to_list()
    assert len(traces) == 1
    payload = json.loads(traces[0])
    assert payload["tool_name"] == "canonicalize_connectivity_label"
    assert payload["arguments"] == {"label": "Wi-Fi"}
    assert payload["result"] == "wifi"


def test_generated_tools_support_toolsandbox_name_scrambling(tmp_path: Path) -> None:
    store = _registry_with_canonicalizer(tmp_path)
    context = ExecutionContext(
        tool_allow_list=["end_conversation"],
        tool_augmentation_list=[ScenarioCategories.TOOL_NAME_SCRAMBLED],
    )
    enhanced = Scenario(starting_context=context)
    inject_registry_tools_into_context(
        enhanced.starting_context,
        store.load_entries().values(),
    )

    available_tools = enhanced.starting_context.get_available_tools(
        scrambling_allowed=True
    )

    execution_names = {tool.__name__ for tool in available_tools.values()}
    assert "canonicalize_connectivity_label" in execution_names
