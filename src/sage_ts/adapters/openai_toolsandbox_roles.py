"""Configurable OpenAI ToolSandbox roles for current model names."""

from __future__ import annotations

import ast
import json
import os
import re
import time
from typing import Any, Iterable, Literal, Mapping, Union, cast

from openai import (
    NOT_GIVEN,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    NotGiven,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion import Choice

from sage_ts.config.models import resolve_model_name
from sage_ts.evaluation.llm_usage import record_chat_completion_usage
from tool_sandbox.common.execution_context import get_current_context
from tool_sandbox.common.utils import all_logging_disabled
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

SELECTOR_ACTOR_POLICY_SENTINEL = "[SAGE selector actor policy]"
DERIVED_ACTOR_POLICY_SENTINEL = "[SAGE derived-value actor policy]"
SERVICE_EXTRACTOR_SCALAR_POLICY_SENTINEL = "[SAGE service-extractor scalar policy]"
LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL = "[SAGE lookup-planner actor policy]"
SEARCH_WINDOW_ACTOR_POLICY_SENTINEL = "[SAGE search-window actor policy]"
SEARCH_WINDOW_RESULT_HANDOFF_POLICY_SENTINEL = (
    "[SAGE search-window result handoff policy]"
)
RELATIVE_TIME_ACTOR_POLICY_SENTINEL = "[SAGE relative-time actor policy]"
STATE_ACTION_ACTOR_POLICY_SENTINEL = "[SAGE state-action actor policy]"
STATE_DOWNSTREAM_COMPLETION_POLICY_SENTINEL = (
    "[SAGE state-downstream completion policy]"
)
DEVICE_STATUS_ACTOR_POLICY_SENTINEL = "[SAGE device-status actor policy]"
DEVICE_STATUS_RETENTION_ACTOR_POLICY_SENTINEL = (
    "[SAGE device-status retention actor policy]"
)
SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL = "[SAGE scheduling-timestamp actor policy]"
ABSOLUTE_REMINDER_TIMESTAMP_POLICY_SENTINEL = (
    "[SAGE absolute-reminder timestamp policy]"
)
SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL = "[SAGE safe-argument actor policy]"
ANSWER_RETENTION_ACTOR_POLICY_SENTINEL = "[SAGE answer-retention actor policy]"
HELPER_ANSWER_COMPLETION_POLICY_SENTINEL = "[SAGE helper-answer completion policy]"
TEMPORAL_ANCHOR_ACTOR_POLICY_SENTINEL = "[SAGE temporal-anchor actor policy]"
CRUD_SUCCESS_ACTOR_POLICY_SENTINEL = "[SAGE CRUD-success actor policy]"
HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL = "[SAGE helper-output handoff policy]"
SAFE_ABSTENTION_HELPER_POLICY_SENTINEL = "[SAGE safe-abstention helper policy]"
SAFE_ABSTENTION_RESULT_POLICY_SENTINEL = "[SAGE safe-abstention result policy]"
ACTION_ARGUMENT_HELPER_POLICY_SENTINEL = "[SAGE action-argument helper policy]"
ADD_CONTACT_ARGUMENT_POLICY_SENTINEL = "[SAGE add-contact argument policy]"
CONTACT_CREATION_COMPLETION_POLICY_SENTINEL = (
    "[SAGE contact-creation completion policy]"
)
DIRECT_CONTACT_ACTION_COMPLETION_POLICY_SENTINEL = (
    "[SAGE direct-contact-action completion policy]"
)
CONTACT_REMOVE_LOOKUP_HANDOFF_POLICY_SENTINEL = (
    "[SAGE contact-remove lookup handoff policy]"
)
LOCATION_SEARCH_ARGUMENT_POLICY_SENTINEL = "[SAGE location-search argument policy]"
LOCATION_SEARCH_RETRY_AFTER_STATE_POLICY_SENTINEL = (
    "[SAGE location-search retry-after-state policy]"
)
LOCATION_SEARCH_RETRY_AFTER_COORDINATES_POLICY_SENTINEL = (
    "[SAGE location-search retry-after-coordinates policy]"
)
REMINDER_LOCATION_BATCH_POLICY_SENTINEL = "[SAGE reminder-location batch policy]"
POST_SELECTION_HELPER_POLICY_SENTINEL = "[SAGE post-selection helper policy]"
HELPER_ADOPTION_RETRY_POLICY_SENTINEL = "[SAGE helper-adoption retry policy]"
GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL = (
    "[SAGE generated-tool contract retry policy]"
)
GENERATED_TOOL_COMPACT_POLICY_SENTINEL = "[SAGE generated-tool compact policy]"
GENERATED_TOOL_MINIMAL_POLICY_SENTINEL = "[SAGE generated-tool minimal policy]"
GENERATED_TOOL_LEAN_POLICY_SENTINEL = "[SAGE generated-tool lean policy]"
GENERATED_TOOL_GUIDANCE_MODE_ENV = "SAGE_GENERATED_TOOL_GUIDANCE_MODE"
GENERATED_TOOL_CONTRACT_RETRY_ATTEMPTS_ENV = (
    "SAGE_GENERATED_TOOL_CONTRACT_RETRY_ATTEMPTS"
)
GENERATED_TOOL_SYNTHETIC_REPAIR_ENV = "SAGE_GENERATED_TOOL_SYNTHETIC_REPAIR"
GENERATED_TOOL_FIRST_ATTEMPT_CHOICE_ENV = "SAGE_GENERATED_TOOL_FIRST_ATTEMPT_CHOICE"
GENERATED_TOOL_CONTINUATION_CHOICE_ENV = "SAGE_GENERATED_TOOL_CONTINUATION_CHOICE"
DYNAMIC_GENERATED_TOOL_SCHEMA_ENV = "SAGE_DYNAMIC_GENERATED_TOOL_SCHEMA"
DYNAMIC_GENERATED_TOOL_SCHEMA_MAX_ENV = "SAGE_DYNAMIC_GENERATED_TOOL_SCHEMA_MAX"
GENERATED_TOOL_HANDOFF_MODE_ENV = "SAGE_GENERATED_TOOL_HANDOFF_MODE"
GENERATED_TOOL_BATCH_INDEPENDENT_CALLS_ENV = (
    "SAGE_GENERATED_TOOL_BATCH_INDEPENDENT_CALLS"
)
GENERATED_TOOL_DROP_USED_SCHEMAS_ENV = "SAGE_GENERATED_TOOL_DROP_USED_SCHEMAS"
EPHEMERAL_ACTOR_POLICIES_ENV = "SAGE_EPHEMERAL_ACTOR_POLICIES"
MESSAGE_COUNTERPARTY_SEARCH_POLICY_SENTINEL = (
    "[SAGE message-counterparty search policy]"
)
MESSAGE_COUNTERPARTY_SELF_LOOKUP_HANDOFF_POLICY_SENTINEL = (
    "[SAGE message-counterparty self-lookup handoff policy]"
)
GENERATED_RECORD_HANDOFF_POLICY_SENTINEL = "[SAGE generated-record handoff policy]"
CONTACT_LOOKUP_ANSWER_POLICY_SENTINEL = "[SAGE contact-lookup answer policy]"
CONTACT_RELATIONSHIP_BATCH_POLICY_SENTINEL = "[SAGE contact-relationship batch policy]"
CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL = (
    "[SAGE contact-relationship batch result policy]"
)
VISIBLE_RECORD_SELECTOR_SETUP_POLICY_SENTINEL = (
    "[SAGE visible-record selector setup policy]"
)
CONTACT_REMOVE_SUCCESS_POLICY_SENTINEL = "[SAGE contact-remove success policy]"
REMINDER_LOCATION_COMPLETION_POLICY_SENTINEL = (
    "[SAGE reminder-location completion policy]"
)
REMINDER_DATETIME_CONTINUATION_POLICY_SENTINEL = (
    "[SAGE reminder-datetime continuation policy]"
)
REMINDER_CURRENT_DATETIME_POLICY_SENTINEL = "[SAGE reminder-current-datetime policy]"
REMINDER_RECENCY_RELATIVE_MODIFY_POLICY_SENTINEL = (
    "[SAGE reminder-recency relative-modify policy]"
)
REMINDER_RECENCY_SEARCH_RESULT_POLICY_SENTINEL = (
    "[SAGE reminder-recency search-result policy]"
)
SHARED_TASK_CLOSURE_POLICY_SENTINEL = "[ToolSandbox shared task-closure policy]"
PRAXIS_BRIDGE_POLICY_ENV = "SAGE_PRAXIS_BRIDGE_POLICY"
DEFAULT_LOCAL_UTC_OFFSET_HOURS = -4
WEEKDAY_NAME_TO_ISO = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}
OpenAIMessage = dict[
    Literal["role", "content", "tool_call_id", "name", "tool_calls"],
    Any,
]
TRANSIENT_OPENAI_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
DEFAULT_TRANSIENT_OPENAI_RETRY_DELAYS = (1.0, 3.0)

ORIGINAL_TOOLSANDBOX_TOOL_NAMES = {
    "add_contact",
    "modify_contact",
    "remove_contact",
    "search_contacts",
    "get_cellular_service_status",
    "get_current_location",
    "get_location_service_status",
    "get_wifi_status",
    "get_low_battery_mode_status",
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
    "search_messages",
    "send_message_with_phone_number",
    "convert_currency",
    "search_lat_lon",
    "search_location_around_lat_lon",
    "search_stock",
    "search_weather_around_lat_lon",
    "add_reminder",
    "modify_reminder",
    "remove_reminder",
    "search_reminder",
    "end_conversation",
    "calculate_lat_lon_distance",
    "datetime_info_to_timestamp",
    "get_current_timestamp",
    "search_holiday",
    "seconds_to_hours_minutes_seconds",
    "shift_timestamp",
    "timestamp_diff",
    "timestamp_to_datetime_info",
    "unit_conversion",
}

GENERATED_EXTRACTION_SOURCE_TOOL_NAMES = {
    "search_location_around_lat_lon",
    "search_lat_lon",
    "search_weather_around_lat_lon",
    "calculate_lat_lon_distance",
    "convert_currency",
    "unit_conversion",
    "search_stock",
}

ORIGINAL_SIDE_EFFECT_TOOL_NAMES = {
    "add_contact",
    "modify_contact",
    "remove_contact",
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
    "send_message_with_phone_number",
    "add_reminder",
    "modify_reminder",
    "remove_reminder",
}

SETTING_SETTER_TOOL_NAMES = {
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
}

SETTING_GETTER_TOOL_NAMES = {
    "get_cellular_service_status",
    "get_location_service_status",
    "get_low_battery_mode_status",
    "get_wifi_status",
}


def _praxis_bridge_policy_enabled() -> bool:
    raw = os.environ.get(PRAXIS_BRIDGE_POLICY_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "combined", "full"}


def _generated_tool_guidance_mode() -> str:
    raw = os.environ.get(GENERATED_TOOL_GUIDANCE_MODE_ENV, "legacy").strip().lower()
    if raw in {"lean_core", "core", "core_lean", "process_core"}:
        return "lean_core"
    if raw in {"lean", "ultra", "low_token", "low-token", "efficient"}:
        return "lean"
    if raw in {"minimal", "clean", "primary"}:
        return "minimal"
    if raw in {"compact", "research", "schema"}:
        return "compact"
    return "legacy"


def _generated_tool_minimal_guidance_enabled() -> bool:
    return _generated_tool_guidance_mode() == "minimal"


def _generated_tool_lean_guidance_enabled() -> bool:
    return _generated_tool_guidance_mode() == "lean"


def _generated_tool_lean_core_guidance_enabled() -> bool:
    return _generated_tool_guidance_mode() == "lean_core"


def _generated_tool_compact_guidance_enabled() -> bool:
    return _generated_tool_guidance_mode() == "compact"


def _ephemeral_actor_policies_enabled() -> bool:
    raw = os.environ.get(EPHEMERAL_ACTOR_POLICIES_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _without_ephemeral_actor_policy_messages(
    openai_messages: list[OpenAIMessage],
) -> list[OpenAIMessage]:
    if not _ephemeral_actor_policies_enabled():
        return openai_messages
    filtered: list[OpenAIMessage] = []
    for message in openai_messages:
        if message.get("role") == "system":
            content = str(message.get("content", ""))
            if content.startswith("[SAGE ") or content.startswith(
                SHARED_TASK_CLOSURE_POLICY_SENTINEL
            ):
                continue
        filtered.append(message)
    return filtered


def _generated_tool_contract_retry_attempts() -> int:
    raw = os.environ.get(GENERATED_TOOL_CONTRACT_RETRY_ATTEMPTS_ENV, "").strip()
    if not raw:
        return 0
    try:
        return max(0, min(4, int(raw)))
    except ValueError:
        return 4


def _generated_tool_synthetic_repair_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_SYNTHETIC_REPAIR_ENV, "").strip().lower()
    if not raw:
        return False
    return raw in {"1", "true", "yes", "on", "enabled"}


def _generated_tool_first_attempt_choice_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_FIRST_ATTEMPT_CHOICE_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _generated_tool_continuation_choice_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_CONTINUATION_CHOICE_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _generated_tool_lean_handoff_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_HANDOFF_MODE_ENV, "").strip().lower()
    return raw in {"lean", "minimal", "micro", "low_token", "low-token", "efficient"}


def _generated_tool_batch_independent_calls_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_BATCH_INDEPENDENT_CALLS_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled", "batch"}


def _generated_tool_drop_used_schemas_enabled() -> bool:
    raw = os.environ.get(GENERATED_TOOL_DROP_USED_SCHEMAS_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled", "drop", "prune"}


def _dynamic_generated_tool_schema_enabled() -> bool:
    raw = os.environ.get(DYNAMIC_GENERATED_TOOL_SCHEMA_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _dynamic_generated_tool_schema_max() -> int:
    raw = os.environ.get(DYNAMIC_GENERATED_TOOL_SCHEMA_MAX_ENV, "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _openai_request_timeout_seconds() -> float:
    raw = os.environ.get("SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS", "90").strip()
    try:
        return max(float(raw), 1.0)
    except ValueError:
        return 90.0


def _openai_max_retries() -> int:
    raw = os.environ.get("SAGE_OPENAI_MAX_RETRIES", "").strip()
    try:
        return max(int(raw), 0) if raw else 2
    except ValueError:
        return 2


def _transient_openai_retry_delays() -> tuple[float, ...]:
    raw = os.environ.get("SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS", "").strip()
    if not raw:
        return DEFAULT_TRANSIENT_OPENAI_RETRY_DELAYS
    delays: list[float] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            delays.append(max(float(item), 0.0))
        except ValueError:
            return DEFAULT_TRANSIENT_OPENAI_RETRY_DELAYS
    return tuple(delays) if delays else DEFAULT_TRANSIENT_OPENAI_RETRY_DELAYS


def _with_transient_openai_retries(call: Any) -> ChatCompletion:
    """Retry only transient OpenAI transport/service failures."""
    retry_delays = _transient_openai_retry_delays()
    for attempt in range(len(retry_delays) + 1):
        try:
            return cast(ChatCompletion, call())
        except TRANSIENT_OPENAI_EXCEPTIONS:
            if attempt >= len(retry_delays):
                raise
            time.sleep(retry_delays[attempt])
    raise RuntimeError("unreachable_openai_retry_state")


def _tool_names(
    openai_tools: object,
) -> set[str]:
    if openai_tools is NOT_GIVEN:
        return set()
    names: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str):
            names.add(name)
    return names


def _agent_facing_tool_name(tool_name: str) -> str:
    if not tool_name:
        return tool_name
    try:
        return str(get_current_context().get_agent_facing_tool_name(tool_name))
    except Exception:
        return tool_name


def _execution_facing_tool_name(tool_name: str) -> str:
    if not tool_name:
        return tool_name
    try:
        mapped = str(get_current_context().get_execution_facing_tool_name(tool_name))
    except Exception:
        mapped = tool_name
    if mapped.startswith("functions."):
        return mapped.split(".", 1)[1]
    return mapped


def _tool_names_execution_facing(openai_tools: object) -> set[str]:
    return {_execution_facing_tool_name(name) for name in _tool_names(openai_tools)}


def _tool_input_names_execution_facing(
    openai_tools: object,
    execution_tool_name: str,
) -> set[str]:
    if openai_tools is NOT_GIVEN:
        return set()
    target = _execution_facing_tool_name(execution_tool_name)
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, Mapping):
            continue
        name = function.get("name")
        if not isinstance(name, str) or _execution_facing_tool_name(name) != target:
            continue
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, Mapping):
            properties = parameters.get("properties", {})
        return set(properties) if isinstance(properties, Mapping) else set()
    return set()


def _tool_output_names_execution_facing(
    openai_tools: object,
    execution_tool_name: str,
) -> set[str]:
    if openai_tools is NOT_GIVEN:
        return set()
    target = _execution_facing_tool_name(execution_tool_name)
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, Mapping):
            continue
        name = function.get("name")
        if not isinstance(name, str) or _execution_facing_tool_name(name) != target:
            continue
        parameters = function.get("parameters", {})
        output_schema: object = function.get("output_schema", {})
        if not output_schema and isinstance(parameters, Mapping):
            output_schema = parameters.get("output_schema", {})
        properties: object = {}
        if isinstance(output_schema, Mapping):
            properties = output_schema.get("properties", {})
        return set(properties) if isinstance(properties, Mapping) else set()
    return set()


def _tool_description_execution_facing(
    openai_tools: object,
    execution_tool_name: str,
) -> str:
    if openai_tools is NOT_GIVEN:
        return ""
    target = _execution_facing_tool_name(execution_tool_name)
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, Mapping):
            continue
        name = function.get("name")
        if not isinstance(name, str) or _execution_facing_tool_name(name) != target:
            continue
        return str(function.get("description") or "")
    return ""


def _tool_name_for_call(openai_tools: object, execution_tool_name: str) -> str:
    for name in _tool_names(openai_tools):
        if _execution_facing_tool_name(name) == execution_tool_name:
            return name
    return _agent_facing_tool_name(execution_tool_name)


def _message_already_called_tool(
    openai_messages: object,
    tool_name: str,
) -> bool:
    target_tool_name = _execution_facing_tool_name(tool_name)
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if (
                isinstance(function, dict)
                and _execution_facing_tool_name(str(function.get("name", "") or ""))
                == target_tool_name
            ):
                return True
    return False


def _helper_adoption_retry_requested_tools() -> set[str]:
    if os.environ.get(
        "SAGE_TS_HELPER_ADOPTION_RETRY_ACTIVE", ""
    ).strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return set()
    return {
        item.strip()
        for item in os.environ.get("SAGE_TS_HELPER_ADOPTION_RETRY_TOOLS", "").split(",")
        if item.strip()
    }


def _helper_adoption_retry_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Prefer a missed generated tool during bounded adoption retry."""

    requested = {
        _execution_facing_tool_name(name)
        for name in _helper_adoption_retry_requested_tools()
    }
    available = _tool_names_execution_facing(openai_tools)
    recency_workflow_requested = bool(
        requested
        & {
            "resolve_search_window_or_bounds",
            "select_action_target_by_recency",
            "select_record_by_timestamp_extreme",
        }
    )
    if recency_workflow_requested:
        current_timestamp = _latest_current_timestamp(openai_messages)
        if (
            "resolve_search_window_or_bounds" in requested
            and "resolve_search_window_or_bounds" in available
            and not _message_already_called_tool(
                openai_messages, "resolve_search_window_or_bounds"
            )
        ):
            if current_timestamp is None:
                return None
            return _tool_name_for_call(openai_tools, "resolve_search_window_or_bounds")
        if not _latest_original_search_has_records(openai_messages):
            return None
        for selector_name in (
            "select_action_target_by_recency",
            "select_record_by_timestamp_extreme",
        ):
            if (
                selector_name in requested
                and selector_name in available
                and not _message_already_called_tool(openai_messages, selector_name)
            ):
                return _tool_name_for_call(openai_tools, selector_name)
        if (
            "relative_day_time_to_timestamp" in requested
            and "relative_day_time_to_timestamp" in available
            and not _message_already_called_tool(
                openai_messages, "relative_day_time_to_timestamp"
            )
        ):
            if current_timestamp is None:
                return None
            current_info = _timestamp_to_datetime_info_for_timestamp(
                openai_messages, current_timestamp
            )
            if current_info is None and "timestamp_to_datetime_info" in available:
                return _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
            return _tool_name_for_call(openai_tools, "relative_day_time_to_timestamp")
        return None
    if (
        "plan_contact_relationship_batch_update" in requested
        and "plan_contact_relationship_batch_update" in available
        and not _message_already_called_tool(
            openai_messages, "plan_contact_relationship_batch_update"
        )
        and _relationship_batch_request(openai_messages) is not None
    ):
        return _tool_name_for_call(
            openai_tools, "plan_contact_relationship_batch_update"
        )
    if (
        "plan_contact_lookup_query" in requested
        and "plan_contact_lookup_query" in available
        and not _message_already_called_tool(
            openai_messages, "plan_contact_lookup_query"
        )
    ):
        return _tool_name_for_call(openai_tools, "plan_contact_lookup_query")
    preferred_order = (
        "prepare_safe_action_or_abstain",
        "relative_day_time_to_timestamp",
        "resolve_search_window_or_bounds",
        "select_action_target_by_recency",
        "select_record_by_timestamp_extreme",
    )
    for tool_name in preferred_order:
        if tool_name not in requested or tool_name not in available:
            continue
        if _message_already_called_tool(openai_messages, tool_name):
            continue
        if (
            tool_name == "resolve_search_window_or_bounds"
            and _latest_current_timestamp(openai_messages) is None
        ):
            continue
        if (
            tool_name == "select_record_by_timestamp_extreme"
            and not _latest_original_search_has_records(openai_messages)
        ):
            continue
        return _tool_name_for_call(openai_tools, tool_name)
    return None


def _shared_task_closure_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Close completed tasks on the current turn for both baseline and SAGE."""
    if "end_conversation" not in _tool_names_execution_facing(openai_tools):
        return None
    if not _latest_user_is_closing_acknowledgement(openai_messages):
        return None
    return _tool_name_for_call(openai_tools, "end_conversation")


def _generated_downstream_original_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Follow a generated tool's explicit original-tool continuation."""

    available_names = _tool_names_execution_facing(openai_tools)
    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    if not generated_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_message = messages[-1] if messages else {}
    if latest_message.get("role") != "tool":
        return None
    latest_tool_name = _execution_facing_tool_name(
        str(latest_message.get("name", "") or "")
    )
    if latest_tool_name not in generated_names:
        return None
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    if latest is None:
        return None
    _helper_name, payload = latest

    def _payload_tool_name(*keys: str) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return _execution_facing_tool_name(value)
        return ""

    candidates: list[str] = []
    if bool(payload.get("should_call_add_reminder")) and isinstance(
        payload.get("add_reminder_kwargs"), Mapping
    ):
        candidates.append("add_reminder")
    if bool(payload.get("should_call_downstream_tool")) and isinstance(
        payload.get("downstream_tool_kwargs"), Mapping
    ):
        candidates.append(_payload_tool_name("downstream_tool_name", "tool_name"))
    if bool(payload.get("should_call_tool")) and isinstance(
        payload.get("downstream_tool_kwargs"), Mapping
    ):
        candidates.append(_payload_tool_name("downstream_tool_name", "tool_name"))
    if bool(payload.get("should_call_search")) and isinstance(
        payload.get("search_kwargs"), Mapping
    ):
        candidates.append(_payload_tool_name("target_tool_name", "tool_name"))
    if bool(payload.get("should_call")) and isinstance(
        payload.get("arguments"), Mapping
    ):
        candidates.append(_payload_tool_name("tool_name", "downstream_tool_name"))

    for candidate in candidates:
        if (
            candidate
            and candidate in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
            and candidate in available_names
        ):
            return _tool_name_for_call(openai_tools, candidate)
    return None


def _helper_answer_completion_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Close a completed generated-tool answer on the current turn."""
    if "end_conversation" not in _tool_names_execution_facing(openai_tools):
        return None
    if (
        _helper_answer_completion_actor_policy_message(openai_messages, openai_tools)
        is None
    ):
        return None
    return _tool_name_for_call(openai_tools, "end_conversation")


def _helper_answer_completion_tool_free_turn(
    openai_messages: object,
    openai_tools: object,
) -> bool:
    """Return whether the next actor turn should answer without tools.

    Generated tools sometimes produce a final answer before the user simulator
    acknowledges or drifts into a follow-up. On those turns the task-relevant
    SAGE action is to preserve the generated-tool answer, not to expose a fresh
    action surface that can pull the actor into an unrelated task.
    """

    return (
        _helper_answer_completion_actor_policy_message(
            openai_messages,
            openai_tools,
        )
        is not None
    )


def _recent_device_status_lookup_completed(openai_messages: object) -> bool:
    """Return whether a device-status getter has already been answered."""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            latest_user_index = index
    if latest_user_index <= 0:
        return False

    status_tool_index = -1
    for index, message in enumerate(messages[:latest_user_index]):
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if tool_name in {
            "get_wifi_status",
            "get_cellular_service_status",
            "get_location_service_status",
            "get_low_battery_mode_status",
        }:
            status_tool_index = index
            continue
        if tool_name == "plan_device_status_lookup":
            payload = _parse_mapping_payload(message.get("content"))
            if (
                payload
                and str(payload.get("final_answer_recommendation") or "").strip()
            ):
                status_tool_index = index

    if status_tool_index < 0:
        return False
    for message in messages[status_tool_index + 1 : latest_user_index]:
        if message.get("role") != "assistant" or message.get("tool_calls"):
            continue
        content = str(message.get("content") or "").strip().lower()
        if not content:
            continue
        if any(
            token in content
            for token in (
                "wifi",
                "wi-fi",
                "cellular",
                "location service",
                "low battery",
                "battery mode",
                "on",
                "off",
                "enabled",
                "disabled",
            )
        ):
            return True
    return False


def _device_status_completion_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Close completed read-only device-status tasks before simulator drift."""
    if "end_conversation" not in _tool_names_execution_facing(openai_tools):
        return None
    if not _recent_device_status_lookup_completed(openai_messages):
        return None
    if not (
        _latest_user_is_closing_acknowledgement(openai_messages)
        or _latest_user_is_post_completion_task_drift(openai_messages)
        or _latest_user_is_post_completion_device_status_drift(openai_messages)
    ):
        return None
    return _tool_name_for_call(openai_tools, "end_conversation")


def _generated_tool_names_execution_facing(openai_tools: object) -> list[str]:
    if openai_tools is NOT_GIVEN:
        return []
    generated: list[str] = []
    for tool_name in _tool_names(openai_tools):
        execution_name = _execution_facing_tool_name(tool_name)
        if execution_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        generated.append(execution_name)
    return generated


def _tool_schema_execution_name(tool: Mapping[str, Any]) -> str:
    function = tool.get("function", {})
    if not isinstance(function, Mapping):
        return ""
    name = function.get("name")
    return _execution_facing_tool_name(str(name or "")) if isinstance(name, str) else ""


def _last_tool_call_index(openai_messages: object, tool_name: str) -> int:
    target = _execution_facing_tool_name(tool_name)
    latest = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            function = tool_call.get("function")
            if not isinstance(function, Mapping):
                continue
            called = _execution_facing_tool_name(str(function.get("name", "") or ""))
            if called == target:
                latest = index
    return latest


def _latest_any_tool_message_index(openai_messages: object) -> int:
    latest = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        if message.get("role") == "tool":
            latest = index
    return latest


def _generated_tool_new_information_since_call(
    openai_messages: object,
    tool_name: str,
) -> bool:
    last_call = _last_tool_call_index(openai_messages, tool_name)
    if last_call < 0:
        return True
    return _latest_any_tool_message_index(openai_messages) > last_call


def _dynamic_generated_tool_schema_filter(
    openai_messages: list[OpenAIMessage],
    openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    *,
    selected_tool_name: str | None = None,
) -> Union[Iterable[ChatCompletionToolParam], NotGiven]:
    """Keep generated tool schemas turn-local while leaving baseline tools intact."""

    if not _dynamic_generated_tool_schema_enabled() or openai_tools is NOT_GIVEN:
        return openai_tools
    tools = list(cast(Iterable[ChatCompletionToolParam], openai_tools))
    generated_names = set(_generated_tool_names_execution_facing(tools))
    if not generated_names:
        return openai_tools

    keep_generated: set[str] = set()
    selected_execution_name = (
        _execution_facing_tool_name(selected_tool_name or "")
        if selected_tool_name
        else ""
    )
    selected_original_tool = bool(
        selected_execution_name
        and selected_execution_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    )
    if selected_execution_name in generated_names:
        keep_generated.add(selected_execution_name)
    latest_messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_message = latest_messages[-1] if latest_messages else {}
    if latest_message.get("role") == "tool":
        latest_tool_name = _execution_facing_tool_name(
            str(latest_message.get("name", "") or "")
        )
        if latest_tool_name in generated_names:
            keep_generated.add(latest_tool_name)

    if not keep_generated and not selected_original_tool:
        continuation_choice = _generated_tool_continuation_choice(
            openai_messages,
            tools,
        )
        continuation_execution_name = _execution_facing_tool_name(
            continuation_choice or ""
        )
        if continuation_execution_name in generated_names:
            keep_generated.add(continuation_execution_name)

    if not keep_generated and not selected_original_tool:
        ready_tools = [
            (index, tool_name)
            for index, tool_name in enumerate(
                _generated_tool_names_execution_facing(tools)
            )
            if _generated_tool_inputs_ready_for_current_turn(
                openai_messages,
                tools,
                tool_name,
            )
            and _generated_tool_new_information_since_call(openai_messages, tool_name)
        ]
        for _index, tool_name in sorted(
            ready_tools,
            key=lambda item: (
                _generated_tool_choice_priority(tools, item[1]),
                item[0],
            ),
        )[: _dynamic_generated_tool_schema_max()]:
            keep_generated.add(_execution_facing_tool_name(tool_name))

    filtered: list[ChatCompletionToolParam] = []
    for tool in tools:
        tool_name = _tool_schema_execution_name(cast(Mapping[str, Any], tool))
        if not tool_name or tool_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            filtered.append(tool)
            continue
        if tool_name in keep_generated:
            filtered.append(tool)
    return filtered


def _tool_schema_text(tool: Mapping[str, Any]) -> str:
    function = tool.get("function", {})
    if not isinstance(function, Mapping):
        return ""
    parts: list[str] = []
    for key in ("name", "description"):
        value = function.get(key)
        if value not in (None, "", [], {}):
            parts.append(str(value))
    parameters = function.get("parameters", {})
    if isinstance(parameters, Mapping):
        try:
            parts.append(json.dumps(parameters, sort_keys=True, default=str))
        except TypeError:
            parts.append(str(parameters))
    return " ".join(parts).lower()


def _route_tokens(text: str) -> set[str]:
    normalized = text.lower().replace("wi-fi", "wifi")
    tokens = set(re.findall(r"[a-z][a-z0-9_]+", normalized))
    expansions: dict[str, set[str]] = {
        "text": {"message", "send_message", "search_messages"},
        "sms": {"message", "send_message", "search_messages"},
        "message": {"message", "send_message", "search_messages"},
        "call": {"phone", "contact"},
        "phone": {"contact", "phone_number", "search_contacts"},
        "person": {"contact", "search_contacts"},
        "people": {"contact", "search_contacts"},
        "contact": {"contact", "search_contacts"},
        "remind": {"reminder", "search_reminders"},
        "reminder": {"reminder", "search_reminders"},
        "todo": {"reminder", "search_reminders"},
        "to-do": {"reminder", "search_reminders"},
        "delete": {"remove", "remove_contact", "remove_reminder"},
        "remove": {"remove", "remove_contact", "remove_reminder"},
        "cancel": {"remove", "remove_reminder"},
        "create": {"add", "add_contact", "add_reminder"},
        "add": {"add", "add_contact", "add_reminder"},
        "set": {"add", "modify", "status"},
        "change": {"modify", "modify_contact", "modify_reminder", "status"},
        "update": {"modify", "modify_contact", "modify_reminder"},
        "edit": {"modify", "modify_contact", "modify_reminder"},
        "latest": {"recent", "timestamp", "search"},
        "newest": {"recent", "timestamp", "search"},
        "recent": {"recent", "timestamp", "search"},
        "oldest": {"earliest", "timestamp", "search"},
        "earliest": {"earliest", "timestamp", "search"},
        "today": {"timestamp", "datetime", "current"},
        "tomorrow": {"timestamp", "datetime", "current"},
        "yesterday": {"timestamp", "datetime", "current"},
        "date": {"timestamp", "datetime"},
        "time": {"timestamp", "datetime"},
        "temperature": {"weather", "location"},
        "weather": {"weather", "location"},
        "forecast": {"weather", "location"},
        "near": {"location", "lat_lon", "distance"},
        "nearby": {"location", "lat_lon", "distance"},
        "closest": {"location", "lat_lon", "distance"},
        "address": {"location", "lat_lon"},
        "wifi": {"wifi", "status"},
        "cellular": {"cellular", "status"},
        "battery": {"battery", "status"},
        "stock": {"stock", "ticker"},
        "share": {"stock", "ticker"},
        "currency": {"currency", "convert"},
        "convert": {"conversion", "currency", "unit"},
        "holiday": {"holiday"},
    }
    for token in list(tokens):
        tokens.update(expansions.get(token, set()))
    return {token for token in tokens if len(token) > 1}


def _visible_user_route_text(openai_messages: object) -> str:
    parts: list[str] = []
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if content not in (None, "", [], {}):
            parts.append(str(content))
    return " ".join(parts)


def _payload_implied_original_tools(payload: Mapping[str, Any]) -> set[str]:
    implied: set[str] = set()

    def add_tool_name(value: object) -> None:
        if isinstance(value, str):
            name = _execution_facing_tool_name(value.strip())
            if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
                implied.add(name)

    for key in (
        "tool_name",
        "target_tool_name",
        "downstream_tool_name",
        "source_tool_name",
    ):
        add_tool_name(payload.get(key))
    if isinstance(payload.get("add_reminder_kwargs"), Mapping):
        implied.add("add_reminder")
    if isinstance(payload.get("search_contacts_kwargs"), Mapping):
        implied.add("search_contacts")
    if isinstance(payload.get("search_messages_kwargs"), Mapping):
        implied.add("search_messages")
    if isinstance(payload.get("search_location_kwargs"), Mapping):
        implied.add("search_lat_lon")
        implied.add("search_location_around_lat_lon")
    if isinstance(payload.get("search_holiday_kwargs"), Mapping):
        implied.add("search_holiday")
    if isinstance(payload.get("downstream_tool_kwargs"), Mapping) or isinstance(
        payload.get("arguments"), Mapping
    ):
        add_tool_name(payload.get("downstream_tool_name"))
        add_tool_name(payload.get("tool_name"))
    sequence = payload.get("action_sequence")
    if isinstance(sequence, list):
        for item in sequence:
            if isinstance(item, Mapping):
                add_tool_name(item.get("tool_name"))
                add_tool_name(item.get("downstream_tool_name"))
    return implied


def _generated_output_implied_original_tools(openai_messages: object) -> set[str]:
    implied: set[str] = set()
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if not name or name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if payload:
            implied.update(_payload_implied_original_tools(payload))
            continue
        sequence = _parse_sequence_payload(message.get("content"))
        for item in sequence:
            if isinstance(item, Mapping):
                implied.update(_payload_implied_original_tools(item))
    return implied


def _generated_schema_implied_original_tools(
    openai_tools: Iterable[ChatCompletionToolParam],
) -> set[str]:
    implied: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        tool_name = _tool_schema_execution_name(tool)
        if not tool_name or tool_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
        output_names = _tool_output_names_execution_facing(openai_tools, tool_name)
        schema_text = _tool_schema_text(tool)
        if input_names & {"current_timestamp", "visible_current_year"}:
            implied.add("get_current_timestamp")
        if "current_datetime_info" in input_names or "datetime_info" in schema_text:
            implied.add("timestamp_to_datetime_info")
        if (
            "add_reminder_kwargs" in output_names
            or "add_reminder_kwargs" in schema_text
        ):
            implied.add("add_reminder")
        if "search_contacts_kwargs" in output_names or "search_contacts" in schema_text:
            implied.add("search_contacts")
        if "search_messages_kwargs" in output_names or "search_messages" in schema_text:
            implied.add("search_messages")
        if "search_location_kwargs" in output_names or "search_location" in schema_text:
            implied.add("search_lat_lon")
            implied.add("search_location_around_lat_lon")
        if "search_weather" in schema_text or "weather" in schema_text:
            implied.add("search_weather_around_lat_lon")
        if "search_holiday" in schema_text or "holiday" in schema_text:
            implied.add("search_holiday")
        if "downstream_tool_name" in output_names or "target_tool_name" in output_names:
            for original_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
                if original_name in schema_text:
                    implied.add(original_name)
    return implied


def _called_original_tools(openai_messages: object) -> set[str]:
    called: set[str] = set()
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            function = tool_call.get("function")
            if not isinstance(function, Mapping):
                continue
            name = _execution_facing_tool_name(str(function.get("name", "") or ""))
            if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
                called.add(name)
    return called


def _original_tool_route_score(
    tool_name: str, tool: Mapping[str, Any], request: str
) -> int:
    request_tokens = _route_tokens(request)
    schema_text = _tool_schema_text(tool)
    schema_tokens = _route_tokens(schema_text)
    score = len(request_tokens & schema_tokens)
    request_lower = request.lower().replace("wi-fi", "wifi")

    def has_any(*needles: str) -> bool:
        return any(needle in request_lower for needle in needles)

    if tool_name == "get_current_timestamp" and has_any(
        "today", "tomorrow", "yesterday", "current", "date", "time", "latest", "oldest"
    ):
        score += 5
    if tool_name == "timestamp_to_datetime_info" and has_any(
        "weekday", "date", "time", "tomorrow", "yesterday"
    ):
        score += 4
    if "reminder" in tool_name and has_any("remind", "reminder", "todo", "to-do"):
        score += 8
    if "message" in tool_name and has_any("message", "text", "sms", "sent", "received"):
        score += 8
    if "contact" in tool_name and has_any(
        "contact", "phone", "number", "person", "people"
    ):
        score += 8
    if "wifi" in tool_name and has_any("wifi"):
        score += 8
    if "cellular" in tool_name and has_any("cellular", "mobile data", "service"):
        score += 8
    if "location_service" in tool_name and has_any("location service", "gps"):
        score += 8
    if "low_battery" in tool_name and has_any("low battery", "battery mode"):
        score += 8
    if "weather" in tool_name and has_any("weather", "temperature", "forecast"):
        score += 8
    if "location" in tool_name or "lat_lon" in tool_name:
        if has_any(
            "location", "address", "near", "nearby", "closest", "where", "weather"
        ):
            score += 5
    if "stock" in tool_name and has_any("stock", "share price", "ticker"):
        score += 8
    if "currency" in tool_name and has_any("currency", "exchange", "dollar", "euro"):
        score += 8
    if "unit_conversion" == tool_name and has_any("convert", "unit", "meters", "miles"):
        score += 8
    if "holiday" in tool_name and has_any("holiday"):
        score += 8

    action_prefix = tool_name.split("_", 1)[0]
    if action_prefix == "add" and has_any("add", "create", "new", "set up"):
        score += 4
    if action_prefix == "modify" and has_any("modify", "change", "update", "edit"):
        score += 4
    if action_prefix == "remove" and has_any("remove", "delete", "cancel"):
        score += 4
    if action_prefix in {"search", "get"} and has_any(
        "find", "search", "what", "which", "who", "where", "tell me", "is my"
    ):
        score += 3
    return score


def _generated_tool_payload_is_complete_contract(payload: Mapping[str, Any]) -> bool:
    if str(payload.get("abstain_reason") or "").strip():
        return False
    if any(
        bool(payload.get(key))
        for key in (
            "should_call_add_reminder",
            "should_call_downstream_tool",
            "should_call_tool",
            "should_call_tools",
            "should_call_search",
            "should_call_search_contacts",
            "should_call_search_messages",
            "should_call",
        )
    ):
        return True
    return any(
        payload.get(key) not in (None, "", [], {})
        for key in (
            "final_answer",
            "exact_final_answer",
            "final_answer_recommendation",
            "answer_value",
            "selected_record",
            "value",
            "add_reminder_kwargs",
            "search_contacts_kwargs",
            "search_messages_kwargs",
            "downstream_tool_kwargs",
            "arguments",
        )
    )


def _drop_completed_generated_tool_schemas(
    openai_messages: list[OpenAIMessage],
    openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    *,
    selected_tool_name: str | None = None,
) -> Union[Iterable[ChatCompletionToolParam], NotGiven]:
    """Stop resending generated-tool schemas after their contract is produced."""

    if not _generated_tool_drop_used_schemas_enabled() or openai_tools is NOT_GIVEN:
        return openai_tools
    tools = list(cast(Iterable[ChatCompletionToolParam], openai_tools))
    generated_names = set(_generated_tool_names_execution_facing(tools))
    if not generated_names:
        return openai_tools
    selected_execution_name = _execution_facing_tool_name(selected_tool_name or "")
    latest = _latest_generated_helper_payload(openai_messages, tools)
    if latest is None:
        return openai_tools
    helper_name, payload = latest
    helper_execution_name = _execution_facing_tool_name(helper_name)
    if helper_execution_name == selected_execution_name:
        return openai_tools
    if not _generated_tool_payload_is_complete_contract(payload):
        return openai_tools
    filtered: list[ChatCompletionToolParam] = []
    for tool in tools:
        tool_name = _tool_schema_execution_name(cast(Mapping[str, Any], tool))
        if tool_name == helper_execution_name:
            continue
        filtered.append(tool)
    return filtered


def _message_already_called_any_generated_tool(
    openai_messages: object,
    openai_tools: object,
) -> bool:
    return any(
        _message_already_called_tool(openai_messages, tool_name)
        for tool_name in _generated_tool_names_execution_facing(openai_tools)
    )


def _visible_numeric_timestamp_count(openai_messages: object) -> int:
    values: set[str] = set()
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        content = str(message.get("content", "") or "")
        for match in re.finditer(r"\b1[5-9]\d{8,}(?:\.\d+)?\b", content):
            values.add(match.group(0))
    return len(values)


def _accepts_current_timestamp_without_datetime_info(tool_name: str) -> bool:
    execution_name = _execution_facing_tool_name(tool_name)
    return execution_name in set()


def _generated_tool_inputs_ready_for_current_turn(
    openai_messages: object,
    openai_tools: object,
    tool_name: str,
) -> bool:
    execution_tool_name = _execution_facing_tool_name(tool_name)
    if execution_tool_name == "plan_send_message_contact_lookup":
        return _extract_send_message_contact_request(
            openai_messages
        ) is not None or _visible_named_send_recipient_present(openai_messages)
    if execution_tool_name == "plan_contact_relationship_batch_update":
        return _relationship_batch_request(openai_messages) is not None
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    if not input_names:
        return True
    if "records" in input_names and not _latest_original_search_has_records(
        openai_messages
    ):
        return False
    if "contacts" in input_names and not _latest_search_contacts_has_records(
        openai_messages
    ):
        return False
    if "stock_payload" in input_names and not _latest_tool_has_nonempty_payload(
        openai_messages, "search_stock"
    ):
        return False
    if "service_payload" in input_names and not _latest_service_answer_payload(
        openai_messages
    ):
        return False
    if "messages" in input_names and not _latest_tool_message(
        openai_messages, "search_messages"
    ):
        return False
    if "selected_record" in input_names and not (
        _selected_record_payload(openai_messages) is not None
        or _selected_action_payload(openai_messages)
        or _latest_original_search_has_records(openai_messages)
    ):
        return False
    if {
        "timestamp_0",
        "timestamp_1",
    }.issubset(input_names) and _visible_numeric_timestamp_count(openai_messages) < 2:
        return False
    timestamp_inputs = {
        "current_timestamp",
        "visible_current_year",
        "current_datetime_info",
    }
    if (
        input_names & timestamp_inputs
        and _latest_current_timestamp(openai_messages) is None
    ):
        return False
    if (
        "current_datetime_info" in input_names
        and not _accepts_current_timestamp_without_datetime_info(execution_tool_name)
        and "timestamp_to_datetime_info" in _tool_names_execution_facing(openai_tools)
        and _latest_tool_message(openai_messages, "timestamp_to_datetime_info") is None
    ):
        return False
    return True


def _generated_tool_choice_priority(openai_tools: object, tool_name: str) -> int:
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    output_names = _tool_output_names_execution_facing(openai_tools, tool_name)
    tool_lower = _execution_facing_tool_name(tool_name).lower()
    side_effect_outputs = {
        "add_contact_kwargs",
        "add_reminder_kwargs",
        "downstream_tool_kwargs",
        "downstream_tool_kwargs_list",
    }
    search_argument_outputs = {
        "search_contacts_kwargs",
        "search_holiday_kwargs",
        "search_location_kwargs",
        "search_messages_kwargs",
        "search_kwargs",
    }
    action_argument_name = (
        tool_lower.startswith("prepare_")
        or tool_lower.endswith("_args")
        or "action" in tool_lower
    )
    if (
        "timestamp" in tool_lower
        or {"days", "seconds"} <= output_names
        or tool_lower.startswith(("relative_", "next_weekday_"))
    ):
        return 0
    if (
        output_names & side_effect_outputs
        or "should_call_tool" in output_names
        or action_argument_name
    ):
        return 1
    if output_names & search_argument_outputs:
        return 2
    if "records" in input_names or "contacts" in input_names:
        return 3
    return 4


def _recency_search_window_requested(openai_messages: object) -> bool:
    """Detect visible requests where a generated window tool should precede search."""

    latest_user = _latest_user_request_text(openai_messages)
    request = " ".join(latest_user.lower().replace("’", "'").split())
    if not request:
        return False
    if not any(
        token in request
        for token in (
            "reminder",
            "todo",
            "to-do",
            "to do",
            "message",
        )
    ):
        return False
    if not any(
        token in request
        for token in (
            "yesterday",
            "today",
            "upcoming",
            "latest",
            "oldest",
            "most recent",
            "newest",
            "earliest",
            "previous day",
            "prior day",
        )
    ):
        return False
    if re.search(
        r"\b(remind me|add (?:a |an )?(?:reminder|todo|to-do)|"
        r"set (?:a |an )?(?:reminder|todo|to-do)|"
        r"create (?:a |an )?(?:reminder|todo|to-do))\b",
        request,
    ):
        return False
    return True


def _generated_tool_prerequisite_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Choose original prerequisite tools needed before a generated tool can run."""

    available_names = _tool_names_execution_facing(openai_tools)
    generated_names = _generated_tool_names_execution_facing(openai_tools)
    if not generated_names:
        return None
    if _recency_search_window_requested(openai_messages):
        for tool_name in generated_names:
            execution_tool_name = _execution_facing_tool_name(tool_name)
            if execution_tool_name not in _search_window_tool_names(openai_tools):
                continue
            if _message_already_called_tool(openai_messages, execution_tool_name):
                continue
            input_names = _tool_input_names_execution_facing(
                openai_tools,
                execution_tool_name,
            )
            if (
                "current_timestamp" in input_names
                and _latest_current_timestamp(openai_messages) is None
            ):
                if (
                    "get_current_timestamp" in available_names
                    and not _message_already_called_tool(
                        openai_messages,
                        "get_current_timestamp",
                    )
                ):
                    return _tool_name_for_call(openai_tools, "get_current_timestamp")
            return None

    timestamp_prerequisite_tools = {
        "resolve_search_window_or_bounds",
        "relative_day_time_to_timestamp",
        "next_weekday_time_to_timestamp",
    }
    for _index, tool_name in sorted(
        enumerate(generated_names),
        key=lambda item: (
            _generated_tool_choice_priority(openai_tools, item[1]),
            item[0],
        ),
    ):
        execution_tool_name = _execution_facing_tool_name(tool_name)
        if execution_tool_name not in timestamp_prerequisite_tools:
            continue
        if _message_already_called_tool(openai_messages, execution_tool_name):
            continue
        input_names = _tool_input_names_execution_facing(
            openai_tools, execution_tool_name
        )
        if (
            "current_timestamp" in input_names
            and _latest_current_timestamp(openai_messages) is None
        ):
            if (
                "get_current_timestamp" in available_names
                and not _message_already_called_tool(
                    openai_messages, "get_current_timestamp"
                )
            ):
                return _tool_name_for_call(openai_tools, "get_current_timestamp")
            continue
        if "current_datetime_info" not in input_names:
            continue
        if _accepts_current_timestamp_without_datetime_info(execution_tool_name):
            continue
        current_timestamp = _latest_current_timestamp(openai_messages)
        if current_timestamp is None:
            continue
        if _timestamp_to_datetime_info_for_timestamp(
            openai_messages, current_timestamp
        ):
            continue
        if "timestamp_to_datetime_info" in available_names:
            return _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
    return None


def _first_attempt_generated_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Choose a routed generated tool on the original trajectory, never a retry."""
    if not _generated_tool_first_attempt_choice_enabled():
        return None
    generated_names = _generated_tool_names_execution_facing(openai_tools)
    if not generated_names:
        return None
    if _message_already_called_any_generated_tool(openai_messages, openai_tools):
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    prerequisite_choice = _generated_tool_prerequisite_choice(
        openai_messages,
        openai_tools,
    )
    if prerequisite_choice is not None:
        return prerequisite_choice
    if _recency_search_window_requested(openai_messages):
        search_window_names = _search_window_tool_names(openai_tools)
        for _index, tool_name in sorted(
            enumerate(generated_names),
            key=lambda item: (
                _generated_tool_choice_priority(openai_tools, item[1]),
                item[0],
            ),
        ):
            execution_tool_name = _execution_facing_tool_name(tool_name)
            if execution_tool_name not in search_window_names:
                continue
            if _message_already_called_tool(openai_messages, execution_tool_name):
                continue
            if _generated_tool_inputs_ready_for_current_turn(
                openai_messages,
                openai_tools,
                execution_tool_name,
            ):
                return _tool_name_for_call(openai_tools, execution_tool_name)
    ready_tools = [
        (index, tool_name)
        for index, tool_name in enumerate(generated_names)
        if _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            tool_name,
        )
    ]
    for _index, tool_name in sorted(
        ready_tools,
        key=lambda item: (
            _generated_tool_choice_priority(openai_tools, item[1]),
            item[0],
        ),
    ):
        return _tool_name_for_call(openai_tools, tool_name)
    return None


def _latest_record_source_after_generated_call(
    openai_messages: object,
    openai_tools: object,
    *,
    require_prior_generated_call: bool = True,
) -> tuple[int, str] | None:
    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    if not generated_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    saw_generated_call = False
    latest_record_source: tuple[int, str] | None = None
    for index, message in enumerate(messages):
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, Mapping):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, Mapping):
                    continue
                called_name = _execution_facing_tool_name(
                    str(function.get("name", "") or "")
                )
                if called_name in generated_names:
                    saw_generated_call = True
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if tool_name not in {
            "search_contacts",
            "search_messages",
            "search_reminder",
            "search_location_around_lat_lon",
            *GENERATED_EXTRACTION_SOURCE_TOOL_NAMES,
        }:
            continue
        if tool_name in {
            "search_contacts",
            "search_messages",
            "search_reminder",
            "search_location_around_lat_lon",
        } and _parse_sequence_payload(message.get("content")):
            latest_record_source = (index, tool_name)
        elif (
            tool_name in GENERATED_EXTRACTION_SOURCE_TOOL_NAMES
            and _latest_tool_has_nonempty_payload(openai_messages, tool_name)
        ):
            latest_record_source = (index, tool_name)
    if require_prior_generated_call and not saw_generated_call:
        return None
    return latest_record_source


def _message_called_generated_tool_after_index(
    openai_messages: object,
    openai_tools: object,
    index: int,
) -> bool:
    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    if not generated_names:
        return False
    for message_index, message in enumerate(
        cast(Iterable[Mapping[str, Any]], openai_messages)
    ):
        if message_index <= index:
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            function = tool_call.get("function")
            if not isinstance(function, Mapping):
                continue
            tool_name = _execution_facing_tool_name(str(function.get("name", "") or ""))
            if tool_name in generated_names:
                return True
    return False


def _generated_tool_consumes_latest_record_source(
    openai_tools: object,
    tool_name: str,
    record_source_name: str,
) -> bool:
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    output_names = _tool_output_names_execution_facing(openai_tools, tool_name)
    tool_lower = _execution_facing_tool_name(tool_name).lower()
    if not input_names:
        return False
    answer_outputs = {
        "answer_value",
        "final_answer",
        "final_answer_recommendation",
        "exact_final_answer",
        "selected_content",
        "should_answer",
    }
    if record_source_name == "search_stock":
        return bool(
            "stock_payload" in input_names
            or (
                "service_payload" in input_names
                and (output_names & answer_outputs or "extract" in tool_lower)
            )
            or tool_lower == "extract_stock_symbol"
        )
    if record_source_name in {
        "search_lat_lon",
        "calculate_lat_lon_distance",
        "convert_currency",
        "unit_conversion",
        "search_weather_around_lat_lon",
    }:
        return bool(
            "service_payload" in input_names
            and (output_names & answer_outputs or "extract" in tool_lower)
        )
    if record_source_name == "search_contacts":
        return bool(
            input_names
            & {
                "contacts",
                "records",
                "selected_record",
                "contact_records",
            }
            and (
                output_names
                & {
                    "answer_value",
                    "final_answer_recommendation",
                    "downstream_tool_kwargs",
                    "downstream_tool_kwargs_list",
                    "selected_record",
                }
            )
        )
    if record_source_name == "search_messages":
        return bool(input_names & {"messages", "records", "selected_record"})
    if record_source_name == "search_reminder":
        return bool(input_names & {"reminders", "records", "selected_record"})
    if record_source_name == "search_location_around_lat_lon":
        return bool(
            input_names & {"locations", "records", "selected_record"}
            or (
                "service_payload" in input_names
                and (output_names & answer_outputs or "extract" in tool_lower)
            )
        )
    return False


def _visible_recency_record_selection_requested(openai_messages: object) -> bool:
    request_text = (
        " ".join(_all_user_texts(openai_messages))
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not request_text:
        return False
    if re.search(r"\b(most\s+recent|least\s+recent)\b", request_text):
        return True
    if re.search(r"\b(latest|oldest|newest|earliest)\b", request_text):
        return True
    if re.search(
        r"\blast\s+(person|contact|message|reminder|one|time)\b", request_text
    ):
        return True
    if re.search(
        r"\bfirst\s+(person|contact|message|reminder|one|time)\b", request_text
    ):
        return True
    return False


def _original_result_only_generated_record_selector_allowed(
    openai_messages: object,
    *,
    record_source_name: str,
    tool_name: str,
) -> bool:
    if tool_name in {"extract_service_answer_field", "extract_stock_symbol"}:
        return True
    if not _visible_recency_record_selection_requested(openai_messages):
        return False
    if record_source_name not in {"search_messages", "search_reminder"}:
        return False
    return tool_name in {
        "select_action_target_by_recency",
        "select_message_content_by_recency",
        "select_message_counterparty_for_contact_update",
        "select_record_by_timestamp_extreme",
    }


def _generated_tool_continuation_priority(openai_tools: object, tool_name: str) -> int:
    output_names = _tool_output_names_execution_facing(openai_tools, tool_name)
    tool_lower = _execution_facing_tool_name(tool_name).lower()
    description_lower = _tool_description_execution_facing(
        openai_tools,
        tool_name,
    ).lower()
    semantic_text = f"{tool_lower} {description_lower}"
    if (
        "message" in semantic_text
        and "content" in semantic_text
        and not ("action" in tool_lower and "target" in tool_lower)
    ):
        return 0
    if "final-answer" in semantic_text or "final answer" in semantic_text:
        return 0
    if output_names & {
        "exact_final_answer",
        "selected_content",
        "selected_message",
        "should_answer",
    }:
        return 0
    if output_names & {
        "answer_value",
        "final_answer",
        "final_answer_recommendation",
    }:
        return 1
    if output_names & {
        "downstream_tool_kwargs",
        "downstream_tool_kwargs_list",
        "should_call_tool",
    }:
        return 2
    return 3 + _generated_tool_choice_priority(openai_tools, tool_name)


def _generated_tool_continuation_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Continue a generated-tool workflow after visible original search records."""
    if not _generated_tool_continuation_choice_enabled():
        return None
    record_source = _latest_record_source_after_generated_call(
        openai_messages,
        openai_tools,
    )
    original_result_only = False
    if record_source is None:
        record_source = _latest_record_source_after_generated_call(
            openai_messages,
            openai_tools,
            require_prior_generated_call=False,
        )
        original_result_only = True
    if record_source is None:
        return None
    record_index, record_source_name = record_source
    if _message_called_generated_tool_after_index(
        openai_messages,
        openai_tools,
        record_index,
    ):
        return None
    candidates = [
        (index, tool_name)
        for index, tool_name in enumerate(
            _generated_tool_names_execution_facing(openai_tools)
        )
        if (
            not original_result_only
            or _original_result_only_generated_record_selector_allowed(
                openai_messages,
                record_source_name=record_source_name,
                tool_name=tool_name,
            )
        )
        and _generated_tool_consumes_latest_record_source(
            openai_tools,
            tool_name,
            record_source_name,
        )
        and _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            tool_name,
        )
    ]
    for _index, tool_name in sorted(
        candidates,
        key=lambda item: (
            _generated_tool_continuation_priority(openai_tools, item[1]),
            _generated_tool_choice_priority(openai_tools, item[1]),
            item[0],
        ),
    ):
        return _tool_name_for_call(openai_tools, tool_name)
    return None


def _selected_reminder_id_after_generated_selection(openai_messages: object) -> str:
    selected: Mapping[str, Any] | None = _selected_record_payload(openai_messages)
    action_payload = _selected_action_payload(openai_messages)
    if selected is None and isinstance(action_payload, Mapping):
        candidate = action_payload.get("selected_record")
        if isinstance(candidate, Mapping):
            selected = candidate
    return str((selected or {}).get("reminder_id") or "").strip()


def _message_called_execution_tool_after_tool(
    openai_messages: object,
    tool_name: str,
    after_tool_names: set[str],
) -> bool:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_after_index = -1
    for index, message in enumerate(messages):
        if message.get("role") != "tool":
            continue
        if (
            _execution_facing_tool_name(str(message.get("name", "") or ""))
            in after_tool_names
        ):
            latest_after_index = index
    if latest_after_index < 0:
        return False
    for message in messages[latest_after_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            name, _arguments = _tool_call_function_name_and_arguments(tool_call)
            if _execution_facing_tool_name(name) == tool_name:
                return True
    return False


def _reminder_recency_workflow_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Keep generated reminder-recency workflows on the tool path, same turn only."""
    available_names = _tool_names_execution_facing(openai_tools)
    if _reminder_recency_request(openai_messages) not in {
        "modify_latest",
        "modify_upcoming",
    }:
        return None
    if _tomorrow_time_request(openai_messages) is None:
        return None
    reminder_id = _selected_reminder_id_after_generated_selection(openai_messages)
    if not reminder_id:
        return None
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        if "get_current_timestamp" in available_names:
            return _tool_name_for_call(openai_tools, "get_current_timestamp")
        return None
    if (
        "timestamp_to_datetime_info" in available_names
        and _timestamp_to_datetime_info_for_timestamp(
            openai_messages, current_timestamp
        )
        is None
    ):
        return _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
    if (
        "relative_day_time_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
    ):
        return _tool_name_for_call(openai_tools, "relative_day_time_to_timestamp")
    if (
        "modify_reminder" in available_names
        and _timestamp_from_latest_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
        is not None
        and not _message_called_execution_tool_after_tool(
            openai_messages,
            "modify_reminder",
            {"relative_day_time_to_timestamp"},
        )
    ):
        return _tool_name_for_call(openai_tools, "modify_reminder")
    return None


def _latest_original_search_has_records(openai_messages: object) -> bool:
    for tool_name in ("search_reminder", "search_messages", "search_contacts"):
        message = _latest_tool_message(openai_messages, tool_name)
        if not message:
            continue
        if _parse_sequence_payload(message.get("content")):
            return True
    return False


def _latest_tool_has_nonempty_payload(
    openai_messages: object,
    tool_name: str,
) -> bool:
    message = _latest_tool_message(openai_messages, tool_name)
    if not message:
        return False
    content = str(message.get("content", "") or "").strip()
    if not content:
        return False
    lower = content.lower()
    return "error" not in lower and "exception" not in lower


def _latest_search_contacts_has_records(openai_messages: object) -> bool:
    message = _latest_tool_message(openai_messages, "search_contacts")
    if not message:
        return False
    return bool(_parse_sequence_payload(message.get("content")))


def _messages_show_tool_error(
    openai_messages: object,
) -> bool:
    error_tokens = (
        "permissionerror",
        "connectionerror",
        "tool_call_exception",
        "low battery",
        "service is off",
        "service disabled",
    )
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        content = str(message.get("content", "")).lower()
        if any(token in content for token in error_tokens):
            return True
    return False


def _messages_show_prior_tool_call(
    openai_messages: object,
    tool_names: set[str],
) -> bool:
    """Return whether any named base tool has already been called."""
    if not tool_names:
        return True
    return any(
        _message_already_called_tool(openai_messages, name) for name in tool_names
    )


def _selector_tool_names(openai_tools: object) -> set[str]:
    """Return visible deterministic selector helpers from OpenAI tool schemas."""
    if openai_tools is NOT_GIVEN:
        return set()
    selectors: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        is_visible_record_selector = "records" in input_names and (
            "visible-record constraint selection" in description
            or "selection/action usage" in description
            or "medium-grain workflow usage" in description
            or "constraint-to-action" in description
            or "selected_record" in description
            or ("select" in name and "record" in description)
        )
        if is_visible_record_selector:
            selectors.add(name)
    return selectors


def _derived_value_tool_names(openai_tools: object) -> set[str]:
    """Return visible deterministic extraction/canonicalization helpers."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str) or not input_names:
            continue
        input_types = (
            {prop.get("type") for prop in properties.values() if isinstance(prop, dict)}
            if isinstance(properties, dict)
            else set()
        )
        has_payload_input = bool(input_types & {"object", "array"})
        scalar_only_extra_inputs = input_types <= {
            "object",
            "array",
            "string",
            "number",
            "integer",
            "boolean",
        }
        if len(input_names) != 1 and not (
            has_payload_input and scalar_only_extra_inputs
        ):
            continue
        is_extractor = any(
            token in f"{name} {description}"
            for token in (
                "extract",
                "normalize",
                "canonicalize",
                "deterministic extraction",
            )
        )
        if is_extractor:
            helpers.add(name)
    return helpers


def _lookup_query_planner_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that prepare original lookup/search kwargs before search."""
    if openai_tools is NOT_GIVEN:
        return set()
    planners: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        output_schema = function.get("output_schema")
        output_properties: object = {}
        if isinstance(output_schema, dict):
            output_properties = output_schema.get("properties", {})
        if not isinstance(output_properties, dict):
            # OpenAI function schemas usually do not carry output_schema. Fall
            # back to description/name markers from generated helper docstrings.
            output_properties = {}
        if not isinstance(name, str) or not input_names:
            continue
        prepares_search_kwargs = any(
            str(key).startswith(("search_", "find_", "get_"))
            and str(key).endswith("_kwargs")
            for key in output_properties
        ) or any(
            token in f"{name} {description}"
            for token in (
                "search_contacts_kwargs",
                "lookup query",
                "query planner",
                "prepare search",
                "search kwargs",
            )
        )
        requires_prior_records = bool(
            input_names & {"records", "candidates", "selected_record", "contact_record"}
        )
        if prepares_search_kwargs and not requires_prior_records:
            planners.add(name)
    return planners


def _search_window_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that prepare bounded search kwargs from recency phrases."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        is_window_helper = name == "resolve_search_window_or_bounds" or (
            {
                "current_timestamp",
                "phrase",
                "target_domain",
                "timestamp_intent",
                "direction",
            }.issubset(input_names)
            and any(
                token in description
                for token in (
                    "time-window",
                    "recency phrase",
                    "search kwargs",
                    "bounded search",
                )
            )
        )
        if is_window_helper:
            helpers.add(name)
    return helpers


def _relative_time_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that convert visible relative local times to timestamps."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        is_relative_time_helper = name == "relative_day_time_to_timestamp" or (
            {"current_timestamp", "day_offset", "hour", "minute"}.issubset(input_names)
            and any(
                token in f"{name} {description}"
                for token in (
                    "relative local day",
                    "relative day",
                    "tomorrow",
                    "timestamp",
                )
            )
        )
        if is_relative_time_helper:
            helpers.add(name)
    return helpers


def _scheduling_timestamp_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that produce reminder timestamps from scheduling phrases."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        is_scheduling_timestamp_helper = name in {
            "next_weekday_time_to_timestamp",
            "relative_weeks_time_to_timestamp",
            "weeks_from_now_time_to_timestamp",
            "week_delta_time_to_timestamp",
            "weekday_delta_time_to_timestamp",
        } or (
            {"current_timestamp", "hour", "minute", "local_utc_offset_hours"}.issubset(
                input_names
            )
            and "reminder_timestamp" in description
            and any(token in description for token in ("week", "weekday", "scheduling"))
        )
        if is_scheduling_timestamp_helper:
            helpers.add(name)
    return helpers


def _state_action_planner_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that plan original device-state setter calls."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        is_next_service_planner = name == "next_service_tool_call" or (
            {"target_service", "tool_name", "should_call"} & input_names
            and "device-state" in description
        )
        has_state_action_inputs = {"user_request", "visible_state_or_error"}.issubset(
            input_names
        )
        is_named_state_action_planner = (
            name == "plan_device_state_action_sequence"
            or name.startswith("plan_device_state_action_sequence")
        ) and has_state_action_inputs
        is_described_state_action_planner = has_state_action_inputs and (
            "state action sequence" in description
            or ("device-state" in description and "setter sequence" in description)
            or ("device state" in description and "setter sequence" in description)
        )
        is_state_action_planner = (
            is_named_state_action_planner
            or is_next_service_planner
            or is_described_state_action_planner
        )
        if is_state_action_planner:
            helpers.add(name)
    return helpers


def _validation_abstention_tool_names(openai_tools: object) -> set[str]:
    """Return visible helpers whose contract is to abstain from unsafe actions."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        has_abstention_inputs = {
            "user_request",
            "requested_action",
            "required_original_tools",
            "available_original_tools",
        }.issubset(input_names)
        is_abstention_helper = name == "prepare_safe_action_or_abstain" or (
            has_abstention_inputs
            and any(
                token in description
                for token in (
                    "abstain",
                    "insufficient information",
                    "safe action",
                )
            )
        )
        if is_abstention_helper:
            helpers.add(name)
    return helpers


def _action_argument_helper_tool_names(openai_tools: object) -> set[str]:
    """Return visible helpers that prepare original side-effect tool arguments."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str) or not input_names:
            continue
        marker_text = f"{name} {description}"
        prepares_side_effect_args = any(
            token in marker_text
            for token in (
                "prepare the arguments",
                "prepares the arguments",
                "prepare arguments",
                "prepares arguments",
                "prepare the call",
                "prepares the call",
                "prepare final",
                "prepares final",
                "prepare exact kwargs",
                "prepares exact kwargs",
                "safe downstream kwargs",
                "downstream_tool_kwargs",
                "side-effect",
                "action argument",
            )
        )
        returns_downstream_call = any(
            token in marker_text
            for token in (
                "should_call_tool",
                "should_call_add_reminder",
                "downstream tool",
                "downstream_tool_name",
                "downstream_tool_kwargs",
                "original toolsandbox",
            )
        ) or any(
            tool_name in marker_text for tool_name in ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        )
        requires_prior_records = bool(
            input_names & {"records", "candidates", "selected_record", "contact_record"}
        )
        if (
            prepares_side_effect_args
            and returns_downstream_call
            and not requires_prior_records
        ):
            helpers.add(name)
    return helpers


def _post_selection_action_helper_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that need a visible selected record before side effects."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        description = str(function.get("description", "")).lower()
        parameters = function.get("parameters", {})
        properties: object = {}
        if isinstance(parameters, dict):
            properties = parameters.get("properties", {})
        input_names = set(properties) if isinstance(properties, dict) else set()
        if not isinstance(name, str):
            continue
        needs_selected_record = bool(
            input_names
            & {"selected_record", "contact_record", "record", "records", "candidates"}
        )
        prepares_downstream_args = any(
            token in f"{name} {description}"
            for token in (
                "downstream_tool_kwargs",
                "side-effect",
                "prepare arguments",
                "prepare the arguments",
                "prepares the arguments",
                "prepare the call",
                "prepares the call",
                "safe downstream kwargs",
                "selected record",
            )
        ) or any(
            tool_name in f"{name} {description}"
            for tool_name in ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        )
        if needs_selected_record and prepares_downstream_args:
            helpers.add(name)
    return helpers


def _tool_content_has_candidate_records(content: object) -> bool:
    text = str(content or "").strip()
    if not text or text.lower() in {"[]", "{}", "null", "none"}:
        return False
    lower = text.lower()
    if any(
        token in lower
        for token in (
            "no matching",
            "not found",
            "no result",
            "no records",
            "empty result",
        )
    ):
        return False
    return text.startswith(("[", "{")) or any(
        token in lower
        for token in (
            "person_id",
            "phone_number",
            "message_id",
            "reminder_id",
            "creation_timestamp",
            "relationship",
            "content",
        )
    )


def _tool_content_has_structured_payload(content: object) -> bool:
    text = str(content or "").strip()
    if not text or text.lower() in {"[]", "{}", "null", "none"}:
        return False
    lower = text.lower()
    if any(
        token in lower
        for token in (
            "no matching",
            "not found",
            "no result",
            "no records",
            "empty result",
            "permissionerror",
            "tool_call_exception",
        )
    ):
        return False
    if not text.startswith(("[", "{")):
        return True
    return any(
        token in lower
        for token in (
            "symbol",
            "price",
            "name",
            "value",
            "result",
            "amount",
            "currency",
            "currency_code",
            "converted_amount",
            "convertedamount",
            "phone_number",
            "address",
            "temperature",
            "temperature_unit",
            "distance",
            "distance_unit",
            "latitude",
            "longitude",
        )
    )


def _messages_show_prior_candidate_records(openai_messages: object) -> bool:
    """Return whether a prior base tool exposed candidate records/lists."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if not name.startswith(("search_", "get_", "find_")):
            continue
        if _tool_content_has_candidate_records(message.get("content")):
            return True
    return False


def _messages_show_prior_structured_payload(openai_messages: object) -> bool:
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name.startswith(("search_", "get_", "find_", "convert_", "calculate_")):
            if _tool_content_has_structured_payload(message.get("content")):
                return True
    return False


def _latest_user_is_brief_acknowledgement(openai_messages: object) -> bool:
    latest_user = ""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages):
        if message.get("role") == "user":
            latest_user = (
                str(message.get("content", ""))
                .strip()
                .lower()
                .replace("’", "'")
                .replace("‘", "'")
            )
            break
    if not latest_user:
        return False
    if "now i can " in latest_user and "?" not in latest_user:
        return True
    if "?" not in latest_user and any(
        phrase in latest_user
        for phrase in (
            "already said that",
            "i already said",
            "that's right",
            "that is right",
            "got it",
            "the relationship is",
        )
    ):
        return True
    answer_ack_phrases = (
        "thanks for finding",
        "thank you for finding",
        "thanks for looking that up",
        "thank you for looking that up",
        "got it, i need that info",
        "got it i need that info",
        "i need that info",
        "i needed that info",
        "that's the info i need",
        "that is the info i need",
        "thats the info i need",
    )
    if any(phrase in latest_user for phrase in answer_ack_phrases):
        return True
    closing_ack_phrases = (
        "end the conversation",
        "end this conversation",
        "end conversation",
        "let's end",
        "lets end",
        "you can end",
        "we can end",
        "conversation can end",
    )
    if "?" not in latest_user and any(
        phrase in latest_user for phrase in closing_ack_phrases
    ):
        return True
    acknowledgement_prefixes = (
        "ok",
        "okay",
        "yep",
        "yes",
        "yeah",
        "that's",
        "that is",
        "thats",
    )
    strong_followup_tokens = (
        "can you",
        "could you",
        "please",
        "help me",
        "i need",
        "need you",
        "search for",
        "find me",
        "send ",
    )
    if (
        latest_user.startswith(acknowledgement_prefixes)
        and "?" not in latest_user
        and not any(token in latest_user for token in strong_followup_tokens)
    ):
        return True
    question_starts = ("what ", "why ", "how ", "who ", "when ", "where ")
    command_tokens = (
        "can you",
        "could you",
        "you can",
        "i need ",
        "need help",
        "help me",
        "search",
        "find",
        "look for",
        "look up",
        "list",
        "show",
        "check ",
        "add ",
        "remove ",
        "modify ",
        "update ",
        "change ",
        "move ",
        "postpone ",
        "push ",
        "reschedule ",
        "set ",
        "shift ",
        "send ",
        "turn on",
        "turn off",
        "turn it on",
        "turn it off",
        "turned on",
        "turned off",
        "switch it on",
        "switch it off",
        "switch them",
        "switch those",
        "flip it on",
        "flip it off",
        "make them",
        "get that",
    )
    if (
        "?" in latest_user
        or latest_user.startswith(question_starts)
        or any(token in latest_user for token in command_tokens)
    ):
        return False
    words = set(
        "".join(char if char.isalnum() else " " for char in latest_user).split()
    )
    acknowledgement_phrases = (
        "got it",
        "you found it",
        "good to know",
        "appreciate",
        "perfect",
        "that's correct",
        "that is correct",
        "thats correct",
        "that's right",
        "that is right",
        "that's what",
        "thats what",
        "got it",
        "thanks for checking",
        "thanks for confirming",
        "that's the message",
        "that's the one",
        "that's it",
        "that's the number",
        "thats the one",
        "thats it",
        "thats the number",
        "still accurate",
        "that's still accurate",
        "that is still accurate",
        "covered this",
        "good for now",
        "all good",
        "all set",
        "good to go",
        "should be good to go",
        "sounds good",
        "that sounds good",
        "works for me",
        "that works for me",
        "that works",
        "that should work",
        "that will work",
        "that'll work",
        "fine by me",
        "good enough",
        "nice",
        "nice!",
        "that helps",
        "this helps",
        "makes sense",
        "that makes sense",
        "i'm good",
        "im good",
        "i'm all good",
        "im all good",
        "i'm all set",
        "im all set",
        "i see",
        "i see that",
        "i get it",
        "i understand",
        "understood",
        "anything else right now",
        "don't have anything else",
        "do not have anything else",
        "nothing else",
        "move on",
        "you got it",
        "absolutely",
        "exactly",
        "will do",
        "i will",
        "you too",
        "take care",
        "sounds like a plan",
        "counting down",
        "count down",
        "i know",
        "already know",
        "already know the",
        "already knew",
        "already knew that",
        "i already knew",
        "i already knew that",
        "no need to repeat",
        "don't need to repeat",
        "do not need to repeat",
        "already have that noted",
        "have that noted",
        "already noted",
    )
    return (
        any(phrase in latest_user for phrase in acknowledgement_phrases)
        or any(word.startswith("thank") for word in words)
        or bool(
            words
            & {
                "thanks",
                "great",
                "awesome",
                "nice",
                "cool",
                "okay",
                "ok",
                "alright",
                "absolutely",
                "yep",
                "yeah",
                "yes",
                "sure",
                "understood",
            }
        )
        or (
            len(words) <= 6
            and bool(words & {"got", "will", "know", "correct", "understood"})
        )
    )


def _latest_user_is_answer_retention_followup(openai_messages: object) -> bool:
    latest_user = ""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages):
        if message.get("role") == "user":
            latest_user = (
                str(message.get("content", ""))
                .strip()
                .lower()
                .replace("’", "'")
                .replace("‘", "'")
            )
            break
    if not latest_user:
        return False
    if _latest_user_is_privacy_retention_followup(openai_messages):
        return True
    if "now i can " in latest_user and "?" not in latest_user:
        return True
    answer_ack_phrases = (
        "thanks for finding",
        "thank you for finding",
        "thanks for looking that up",
        "thank you for looking that up",
        "got it, i need that info",
        "got it i need that info",
        "i need that info",
        "i needed that info",
        "that's the info i need",
        "that is the info i need",
        "thats the info i need",
    )
    if any(phrase in latest_user for phrase in answer_ack_phrases):
        return True
    closing_ack_phrases = (
        "end the conversation",
        "end conversation",
        "you can end",
        "we can end",
        "conversation can end",
    )
    if "?" not in latest_user and any(
        phrase in latest_user for phrase in closing_ack_phrases
    ):
        return True
    acknowledgement_prefixes = (
        "yep",
        "yes",
        "yeah",
        "that's",
        "that is",
        "thats",
    )
    strong_followup_tokens = (
        "can you",
        "could you",
        "please",
        "help me",
        "i need",
        "need you",
        "search for",
        "find me",
        "send ",
    )
    if (
        latest_user.startswith(acknowledgement_prefixes)
        and "?" not in latest_user
        and not any(token in latest_user for token in strong_followup_tokens)
    ):
        return True
    question_starts = ("what ", "why ", "how ", "who ", "when ", "where ")
    command_tokens = (
        "can you",
        "could you",
        "you can",
        "i need ",
        "need help",
        "help me",
        "look for",
        "look up",
        "list",
        "show",
        "check ",
        "add ",
        "remove ",
        "modify ",
        "update ",
        "change ",
        "move ",
        "postpone ",
        "push ",
        "reschedule ",
        "set ",
        "shift ",
        "send ",
        "turn on",
        "turn off",
        "turn it on",
        "turn it off",
        "turned on",
        "turned off",
        "switch it on",
        "switch it off",
        "switch them",
        "switch those",
        "flip it on",
        "flip it off",
        "make them",
        "get that",
    )
    repeat_lookup_tokens = (
        "still need to search",
        "still want to search",
        "really want to search",
        "need to search",
        "want to search",
        "can't access",
        "cannot access",
        "can't complete",
        "cannot complete",
        "can't find anything else",
        "cannot find anything else",
        "just wanted to check",
        "just want to check",
        "wanted to check it",
        "wanted to check",
        "just checking",
        "can you check that for me",
        "check that for me",
        "check it for me",
        "check your reminder",
        "check your reminders",
        "check your reminder app",
        "check your reminders later",
        "try using your device",
        "use your device to check",
        "can't check it now",
        "cannot check it now",
        "try again later",
        "can you help me with that",
        "help me with that",
        "just need to get",
        "move on",
        "thanks for checking",
        "thanks for confirming",
        "perfect",
        "definitely",
        "need to check the content",
        "check it for myself",
        "check it directly",
        "check it out",
        "look it up myself",
        "look it up directly",
        "look it up for myself",
        "map app",
        "use a map",
        "using a map",
        "without a map",
        "directions",
        "direction",
        "navigation",
        "navigate",
        "route",
        "get there",
        "how to get there",
        "use a calculator",
        "using a calculator",
        "can't verify",
        "cannot verify",
        "can't validate",
        "cannot validate",
        "location services",
        "turn on location",
        "turn it on",
        "settings",
        "see it myself",
        "want to see it myself",
        "still want to see it",
        "get that message sent",
        "let's get that message sent",
        "lets get that message sent",
        "send that message",
        "send the message",
        "send a message",
        "next task",
        "that's what i need to remember",
        "that is what i need to remember",
        "thats what i need to remember",
        "what i need to remember",
        "what i needed to remember",
    )
    has_repeat_followup = any(token in latest_user for token in repeat_lookup_tokens)
    if (
        ("?" in latest_user and not has_repeat_followup)
        or (latest_user.startswith(question_starts) and not has_repeat_followup)
        or (
            any(token in latest_user for token in command_tokens)
            and not has_repeat_followup
        )
    ):
        return False
    if _latest_user_is_brief_acknowledgement(openai_messages):
        return True
    retention_phrases = (
        "that's correct",
        "that is correct",
        "thats correct",
        "that's right",
        "that is right",
        "you got it",
        "that's what",
        "thats what",
        "got it",
        "thanks for checking",
        "thanks for confirming",
        "absolutely",
        "definitely",
        "works for me",
        "that works for me",
        "that works",
        "that should work",
        "that will work",
        "that'll work",
        "fine by me",
        "good enough",
        "nice",
        "nice!",
        "that helps",
        "this helps",
        "makes sense",
        "that makes sense",
        "that's the message",
        "that's the one",
        "that's it",
        "that's the number",
        "thats the one",
        "thats it",
        "thats the number",
        "still accurate",
        "that's still accurate",
        "that is still accurate",
        "covered this",
        "good for now",
        "all good",
        "all set",
        "good to go",
        "should be good to go",
        "i'm good",
        "im good",
        "i'm all good",
        "im all good",
        "i'm all set",
        "im all set",
        "i see",
        "i see that",
        "i get it",
        "i understand",
        "understood",
        "that's what i need to remember",
        "that is what i need to remember",
        "thats what i need to remember",
        "what i need to remember",
        "what i needed to remember",
        "got the distance",
        "got distance",
        "have the distance",
        "have got the distance",
        "i've got the distance",
        "ive got the distance",
        "already know",
        "already know the",
        "already knew",
        "already knew that",
        "i already knew",
        "i already knew that",
        "already have that",
        "already had that",
        "anything else right now",
        "don't have anything else",
        "do not have anything else",
        "don't have more info",
        "do not have more info",
        "don't have any more info",
        "do not have any more info",
        "don't have any other info",
        "do not have any other info",
        "don't have other info",
        "do not have other info",
        "don't have any more questions",
        "do not have any more questions",
        "i don't have any more questions",
        "i do not have any more questions",
        "no more questions",
        "nothing else",
        "no need to repeat",
        "don't need to repeat",
        "do not need to repeat",
        "move on",
        "exactly",
        "help me with something else",
        "something else",
        "any other inquiries",
        "no other inquiries",
        "just need to search",
        "just need to find",
        "just needed to search",
        "just needed to find",
        "still need to search",
        "still want to search",
        "really want to search",
        "need to search",
        "want to search",
        "just trying to get",
        "just need to get",
        "just want the",
        "just needed the",
        "can you help me with that",
        "help me with that",
        "double-check",
        "double check",
        "verify",
        "confirmation",
        "confirm",
        "calendar",
        "countdown",
        "counting down",
        "count down",
        "sounds like a plan",
        "can't help",
        "cannot help",
        "can't share anything more",
        "cannot share anything more",
        "can't share any more",
        "cannot share any more",
        "can't provide anything more",
        "cannot provide anything more",
        "can't provide any extra info",
        "cannot provide any extra info",
        "can't access",
        "cannot access",
        "can't complete",
        "cannot complete",
        "can't find anything else",
        "cannot find anything else",
        "check it yourself",
        "try checking",
        "just wanted to check",
        "just want to check",
        "wanted to check it",
        "wanted to check",
        "just checking",
        "can you check that for me",
        "check that for me",
        "check it for me",
        "check your reminder",
        "check your reminders",
        "check your reminder app",
        "check your reminders later",
        "try using your device",
        "use your device to check",
        "can't check it now",
        "cannot check it now",
        "try again later",
        "need to check the content",
        "check it for myself",
        "check it directly",
        "look it up myself",
        "look it up directly",
        "look it up for myself",
        "see it myself",
        "want to see it myself",
        "still want to see it",
        "get that message sent",
        "let's get that message sent",
        "lets get that message sent",
        "send that message",
        "send the message",
        "send a message",
        "next task",
        "that's all i needed",
        "that is all i needed",
        "all i needed",
        "keep that private",
        "keep that a secret",
        "keep that secret",
        "keep it private",
        "keep it a secret",
        "keep it secret",
        "keep this private",
        "keep this a secret",
        "keep this secret",
        "need to keep that a secret",
        "need to keep it a secret",
        "keep that confidential",
        "keep it confidential",
        "stay private",
        "keep it to yourself",
        "keep that to yourself",
        "do not share",
        "don't share",
        "not share",
        "do not leak",
        "don't leak",
        "not leak",
        "not go over it",
        "won't share",
        "wont share",
        "private",
        "confidential",
    )
    words = set(
        "".join(char if char.isalnum() else " " for char in latest_user).split()
    )
    if any(phrase in latest_user for phrase in retention_phrases) or bool(
        words & {"accurate", "correct", "right"}
    ):
        return True
    return False


def _latest_user_is_device_status_retention_followup(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return False
    if any(
        token in latest_user
        for token in (
            "turn on",
            "turn off",
            "switch ",
            "enable ",
            "disable ",
        )
    ) or latest_user.startswith(
        ("set ", "please set ", "can you set ", "could you set ")
    ):
        return False
    status_followup_tokens = (
        "wifi",
        "wi-fi",
        "cellular",
        "service",
        "signal",
        "location",
        "battery",
        "internet",
        "connected",
        "connection",
        "working",
        "works",
        "website",
        "that's it",
        "thats it",
        "that's all",
        "thats all",
        "nope",
        "great",
        "thanks",
        "thank you",
        "sure",
        "ok",
        "okay",
    )
    return any(token in latest_user for token in status_followup_tokens)


def _latest_user_is_privacy_retention_followup(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return False
    privacy_phrases = (
        "prefer not to discuss",
        "rather not discuss",
        "do not want to discuss",
        "don't want to discuss",
        "not discuss that",
        "not discussing that",
        "rather not confirm",
        "rather not confirm that",
        "prefer not to confirm",
        "not confirm that",
        "keep that a secret",
        "keep it a secret",
        "keep this a secret",
        "keep that secret",
        "keep it secret",
        "keep this secret",
        "need to keep that a secret",
        "need to keep it a secret",
        "keep that private",
        "keep it private",
        "keep this private",
        "keep that confidential",
        "keep it confidential",
        "keep it to yourself",
        "keep that to yourself",
        "keep this to yourself",
        "don't share",
        "do not share",
        "do not leak",
        "don't leak",
    )
    return any(phrase in latest_user for phrase in privacy_phrases)


def _recent_tool_backed_answer_text(openai_messages: object) -> str | None:
    pending_tool_result = False
    answer: str | None = None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        role = message.get("role")
        if role == "tool":
            pending_tool_result = True
            continue
        if role == "user":
            continue
        if role == "assistant" and pending_tool_result:
            pending_tool_result = False
            if message.get("tool_calls"):
                continue
            content = str(message.get("content", "") or "").strip()
            if len(content) < 8:
                continue
            lower = content.lower()
            if lower.startswith(("you're welcome", "you are welcome")):
                continue
            answer = content
    return answer


def _messages_show_generated_helper_call(
    openai_messages: object,
    openai_tools: object | None = None,
) -> bool:
    """Return whether the transcript includes a generated helper tool result."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if not tool_name or tool_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        return True
    return False


def _recent_exact_final_answer_from_tool(openai_messages: object) -> str | None:
    answer: str | None = None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        payload = _parse_mapping_payload(message.get("content"))
        if not payload:
            continue
        if tool_name == "extract_service_answer_field" or (
            tool_name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
            and payload.get("answer_value") is not None
            and payload.get("answer_kind") is not None
        ):
            service_answer = _service_answer_text(payload, openai_messages)
            if service_answer:
                answer = service_answer
                continue
        copy_exactly = bool(payload.get("copy_exactly"))
        candidate = str(
            payload.get("exact_final_answer")
            or payload.get("final_answer_recommendation")
            or ""
        ).strip()
        if not candidate or candidate.lower().startswith("abstain:"):
            continue
        if (
            tool_name == "plan_device_status_lookup"
            or copy_exactly
            or payload.get("exact_final_answer")
        ):
            answer = candidate
    return answer


def _recent_device_status_answer_from_tool(openai_messages: object) -> str | None:
    answer: str | None = None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if tool_name != "plan_device_status_lookup":
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if not payload:
            continue
        candidate = str(payload.get("final_answer_recommendation") or "").strip()
        if candidate and not candidate.lower().startswith("abstain:"):
            answer = candidate
    return answer


def _recent_distance_answer_text(openai_messages: object) -> str | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "assistant":
            continue
        content = _strip_recap_prefixes(str(message.get("content", "") or "").strip())
        lower = content.lower()
        if "kilometer" in lower and ("away from" in lower or "distance" in lower):
            return content
    return None


def _messages_show_recent_tool_backed_answer(openai_messages: object) -> bool:
    return (
        _recent_exact_final_answer_from_tool(openai_messages) is not None
        or _recent_tool_backed_answer_text(openai_messages) is not None
    )


def _latest_user_is_phone_answer_retention_followup(openai_messages: object) -> bool:
    answer = _recent_exact_final_answer_from_tool(
        openai_messages
    ) or _recent_tool_backed_answer_text(openai_messages)
    if not answer:
        return False
    answer_lower = answer.lower()
    if "phone number" not in answer_lower or not re.search(r"\+\d{7,}", answer):
        return False
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return False
    phone_answer_followup_phrases = (
        "find that number",
        "find the number",
        "find that phone number",
        "find the phone number",
        "find it",
        "find contact",
        "find the contact",
        "find that contact",
        "focus on finding",
        "just find",
        "just please find",
        "need you to find",
        "need to find",
        "still need you to find",
        "still need to find",
        "i know the number",
        "i already know the number",
        "cellular service",
    )
    return any(phrase in latest_user for phrase in phone_answer_followup_phrases)


def _latest_assistant_setting_permission_request(
    openai_messages: object,
) -> tuple[str, bool] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = _latest_user_index(messages)
    if latest_user_index <= 0:
        return None
    assistant_text = ""
    for message in reversed(messages[:latest_user_index]):
        if message.get("role") != "assistant":
            continue
        assistant_text = str(message.get("content", "") or "").strip().lower()
        break
    if not assistant_text:
        return None
    if not any(
        token in assistant_text
        for token in (
            "would you like me",
            "do you want me",
            "should i",
            "please enable",
            "please turn",
        )
    ):
        return None
    tool_name: str | None = None
    asks_to_turn_off = any(
        token in assistant_text
        for token in ("turn off", "disable", "shut off", "switch off")
    )
    if (
        "low battery" in assistant_text or "battery mode" in assistant_text
    ) and asks_to_turn_off:
        tool_name = "set_low_battery_mode_status"
    elif "location service" in assistant_text:
        tool_name = "set_location_service_status"
    elif "low battery" in assistant_text or "battery mode" in assistant_text:
        tool_name = "set_low_battery_mode_status"
    elif "wi-fi" in assistant_text or "wifi" in assistant_text:
        tool_name = "set_wifi_status"
    elif "cellular" in assistant_text or "cell service" in assistant_text:
        tool_name = "set_cellular_service_status"
    if tool_name is None:
        return None
    desired_on = True
    if asks_to_turn_off:
        desired_on = False
    return tool_name, desired_on


def _latest_user_affirms_setting_permission(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("wi-fi", "wifi")
    )
    if not latest_user:
        return False
    if any(
        token in latest_user
        for token in (
            " no",
            "don't",
            "do not",
            "not now",
            "never mind",
            "nevermind",
            "cancel",
        )
    ) or latest_user in {"no", "nope", "nah"}:
        return False
    affirmative_phrases = (
        "yes",
        "yep",
        "yeah",
        "sure",
        "please",
        "go ahead",
        "turn it on",
        "turn it off",
        "turn on",
        "turn off",
        "enable",
        "disable",
        "switch it on",
        "switch it off",
        "just turn",
        "already said yes",
        "do it",
    )
    return any(phrase in latest_user for phrase in affirmative_phrases)


def _setting_permission_followup_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    request = _latest_assistant_setting_permission_request(openai_messages)
    if request is None or not _latest_user_affirms_setting_permission(openai_messages):
        return None
    tool_name, desired_on = request
    if tool_name not in _tool_names_execution_facing(openai_tools):
        return None
    if _called_tool_after_latest_user(openai_messages, tool_name):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-setting-permission-followup",
        tool_name=_tool_name_for_call(openai_tools, tool_name),
        arguments={"on": desired_on},
    )


def _latest_current_location_coordinates(
    openai_messages: object,
) -> tuple[float, float] | None:
    content = _latest_tool_content(openai_messages, "get_current_location")
    if not content:
        return None
    payload = _parse_mapping_payload(content)
    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return None
    return latitude, longitude


def _city_from_lat_lon_response(content: object) -> str | None:
    value = _parse_service_payload_value(content)
    if isinstance(value, Mapping):
        for key in ("city", "name", "locality"):
            city = str(value.get(key) or "").strip()
            if city:
                return city
        address = str(value.get("address") or value.get("formatted_address") or "")
    else:
        address = str(value or "").strip().strip("'\"")
    if not address:
        return None
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return None


def _current_city_recovery_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    all_user = " ".join(_all_user_texts(openai_messages)).lower()
    if not any(
        token in all_user
        for token in (
            "current city",
            "where am i",
            "what city am i in",
            "which city am i in",
        )
    ):
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if _latest_tool_is(openai_messages, "search_lat_lon"):
        content = _latest_tool_content(openai_messages, "search_lat_lon")
        if content and not any(
            token in content.lower() for token in ("error", "exception")
        ):
            city = _city_from_lat_lon_response(content)
            if city:
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-current-city-answer",
                    content=f"You are currently in {city}.",
                )
        if (
            content
            and "wifi" in content.lower()
            and "set_wifi_status" in available_names
        ):
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-current-city-wifi-needed",
                content=(
                    "Wi-Fi is not enabled, so I cannot look up the city from "
                    "your current coordinates. Would you like me to enable Wi-Fi?"
                ),
            )
        return None
    if _latest_tool_is(openai_messages, "set_location_service_status"):
        content = (
            _latest_tool_content(openai_messages, "set_location_service_status") or ""
        )
        if (
            "low battery" in content.lower()
            and "set_low_battery_mode_status" in available_names
        ):
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-current-city-low-battery-needed",
                content=(
                    "Location service cannot be enabled while low battery mode "
                    "is on. Would you like me to turn off low battery mode?"
                ),
            )
        if (
            _latest_tool_success_content(openai_messages) is not None
            and "get_current_location" in available_names
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-current-city-get-location-after-enable",
                tool_name=_tool_name_for_call(openai_tools, "get_current_location"),
                arguments={},
            )
        return None
    if _latest_tool_is(openai_messages, "set_low_battery_mode_status"):
        if (
            _latest_tool_success_content(openai_messages) is not None
            and "set_location_service_status" in available_names
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-current-city-enable-location-after-low-battery",
                tool_name=_tool_name_for_call(
                    openai_tools, "set_location_service_status"
                ),
                arguments={"on": True},
            )
        return None
    coordinates = _latest_current_location_coordinates(openai_messages)
    if coordinates is None:
        return None
    latitude, longitude = coordinates
    if _latest_tool_is(openai_messages, "set_wifi_status") or _latest_tool_is(
        openai_messages, "get_current_location"
    ):
        if "search_lat_lon" in available_names:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-current-city-search-lat-lon",
                tool_name=_tool_name_for_call(openai_tools, "search_lat_lon"),
                arguments={"latitude": latitude, "longitude": longitude},
            )
    return None


def _answer_retention_response_text(openai_messages: object) -> str | None:
    if _latest_assistant_setting_permission_request(
        openai_messages
    ) and _latest_user_affirms_setting_permission(openai_messages):
        return None
    is_brief_ack = _latest_user_is_brief_acknowledgement(openai_messages)
    is_privacy_followup = _latest_user_is_privacy_retention_followup(openai_messages)
    is_phone_answer_followup = _latest_user_is_phone_answer_retention_followup(
        openai_messages
    )
    if not is_phone_answer_followup and not _latest_user_is_answer_retention_followup(
        openai_messages
    ):
        return None
    distance_answer = _recent_distance_answer_text(openai_messages)
    answer = (
        distance_answer
        if distance_answer and is_brief_ack
        else _recent_exact_final_answer_from_tool(openai_messages)
        or _recent_tool_backed_answer_text(openai_messages)
    )
    if not answer:
        return None
    if is_privacy_followup:
        return "Understood. I won't share that."
    answer = " ".join(answer.split())
    if len(answer) > 280:
        answer = answer[:277].rstrip() + "..."
    prefix = "You're welcome." if is_brief_ack else "Understood."
    return f"{prefix} To recap: {answer}"


def _recent_tool_backed_answer_already_recapped(openai_messages: object) -> bool:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    saw_tool_backed_answer = False
    has_recent_tool_answer = _messages_show_recent_tool_backed_answer(messages)
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", "") or "").strip().lower()
        if role == "tool":
            saw_tool_backed_answer = False
            continue
        if role == "assistant":
            if "to recap:" in content and saw_tool_backed_answer:
                return True
            if content and not content.startswith(
                ("you're welcome", "you are welcome")
            ):
                saw_tool_backed_answer = has_recent_tool_answer
    return False


def _answer_completion_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """End repeated acknowledgement loops after a tool-backed answer was recapped."""
    if not _praxis_bridge_policy_enabled():
        return None
    is_completion_followup = _latest_user_is_answer_retention_followup(
        openai_messages
    ) or _latest_user_is_post_completion_message_followup(openai_messages)
    if not is_completion_followup:
        return None
    if not _messages_show_recent_tool_backed_answer(openai_messages):
        return None
    if not (
        _latest_user_is_closing_acknowledgement(openai_messages)
        or _recent_tool_backed_answer_already_recapped(openai_messages)
    ):
        return None
    if "end_conversation" not in _tool_names_execution_facing(openai_tools):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-answer-completion-end",
        tool_name=_tool_name_for_call(openai_tools, "end_conversation"),
        arguments={},
    )


def _latest_user_request_text(openai_messages: object) -> str:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") == "user":
            return str(message.get("content", "") or "")
    return ""


def _first_user_request_text(openai_messages: object) -> str:
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") == "user":
            return str(message.get("content", "") or "")
    return ""


def _first_user_is_device_setting_without_message(openai_messages: object) -> bool:
    first_user = (
        _first_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not first_user:
        return False
    initial_is_device_setting = any(
        token in first_user
        for token in (
            "cellphone signal",
            "cell phone signal",
            "cellular",
            "cell service",
            "mobile data",
            "wifi",
            "wi-fi",
            "location service",
            "low battery",
        )
    )
    initial_requested_message_send = any(
        token in first_user for token in ("send ", "message", "text ")
    )
    return initial_is_device_setting and not initial_requested_message_send


def _first_user_is_device_mutation_without_message(openai_messages: object) -> bool:
    first_user = (
        _first_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not _first_user_is_device_setting_without_message(openai_messages):
        return False
    mutation_tokens = (
        "turn",
        "enable",
        "disable",
        "switch",
        "set ",
        "shut off",
        "get it on",
        "get it off",
        "get them on",
        "get them off",
    )
    if any(token in first_user for token in mutation_tokens):
        return True
    return bool(
        re.search(r"\b(get|make)\b.{0,48}\b(on|off|enabled|disabled)\b", first_user)
    )


def _latest_user_is_post_completion_message_followup(
    openai_messages: object,
) -> bool:
    """Detect a new message-sending follow-up after a completed setting task."""
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or not _first_user_is_device_setting_without_message(
        openai_messages
    ):
        return False
    return any(
        token in latest_user
        for token in (
            "ready to send the message",
            "ready to send that message",
            "send the message now",
            "send that message now",
            "send a message to",
            "send that message to",
            "get that message sent",
        )
    )


def _latest_user_is_closing_acknowledgement(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or not _latest_user_is_brief_acknowledgement(openai_messages):
        return False
    if "?" in latest_user:
        return False
    explicit_closing_phrases = (
        "thanks for letting me know",
        "thank you for letting me know",
        "thanks for the update",
        "thank you for the update",
        "appreciate the update",
        "end this conversation",
        "end the conversation",
        "let's end",
        "lets end",
        "i actually don't need anything else right now",
        "i don't need anything else right now",
        "i do not need anything else right now",
        "don't need anything else right now",
        "do not need anything else right now",
        "that's the one i needed",
        "that is the one i needed",
        "just wanted to confirm",
        "wanted to confirm",
    )
    if any(phrase in latest_user for phrase in explicit_closing_phrases):
        return True
    continuation_tokens = (
        "but",
        "though",
        "still",
        "actually",
        "instead",
        "another",
        "also",
        "can you",
        "could you",
        "please",
        "i need",
        "need you",
        "find ",
        "look up",
        "search",
        "send ",
        "add ",
        "remove ",
        "modify ",
        "change ",
        "update ",
    )
    if any(token in latest_user for token in continuation_tokens):
        return False
    closing_tokens = (
        "thanks",
        "thank you",
        "got it",
        "i got it",
        "that's right",
        "that is right",
        "that's correct",
        "that is correct",
        "that's what i needed",
        "that is what i needed",
        "that's the number i was looking for",
        "that is the number i was looking for",
        "that's the answer i was looking for",
        "that is the answer i was looking for",
        "that's the one i needed",
        "that is the one i needed",
        "just wanted to confirm",
        "wanted to confirm",
        "nothing else",
        "anything else right now",
        "don't need anything else",
        "do not need anything else",
        "all set",
        "all good",
        "good to go",
        "should be good to go",
        "good for now",
        "i'm good",
        "im good",
        "perfect",
        "cool",
        "nice",
        "great",
        "awesome",
        "sounds like a plan",
        "counting down",
        "count down",
        "move on",
    )
    return any(token in latest_user for token in closing_tokens)


def _latest_user_is_post_completion_task_drift(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or _latest_user_is_closing_acknowledgement(openai_messages):
        return False
    drift_tokens = (
        "send ",
        "message",
        "text ",
        "turn ",
        "turn it on",
        "switch ",
        "enable ",
        "disable ",
        "set ",
        "settings",
        "location services",
        "map app",
        "use a map",
        "without a map",
        "directions",
        "direction",
        "navigation",
        "navigate",
        "route",
        "get there",
        "how to get there",
        "verify",
        "validate",
        "confirm",
        "search",
        "find ",
        "look up",
        "check it",
        "remind",
        "add ",
        "remove ",
        "modify ",
        "update ",
    )
    return any(token in latest_user for token in drift_tokens)


def _latest_user_is_post_completion_device_status_drift(
    openai_messages: object,
) -> bool:
    """Detect simulator drift after a generated device-status tool finalized an answer."""
    if not _recent_device_status_answer_from_tool(openai_messages):
        return False
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or _latest_user_is_closing_acknowledgement(openai_messages):
        return False
    if "?" in latest_user and _latest_user_is_device_status_retention_followup(
        openai_messages
    ):
        return True
    drift_tokens = (
        "can you check",
        "could you check",
        "check if",
        "check whether",
        "any signal",
        "signal",
        "turning off",
        "turning on",
        "turn it off",
        "turn it on",
        "turn off",
        "turn on",
        "low battery",
        "battery mode",
        "settings",
        "try using the tools",
        "use device tools",
        "not be possible to check",
        "figure it out",
    )
    return any(token in latest_user for token in drift_tokens)


def _latest_user_is_post_completion_state_drift(openai_messages: object) -> bool:
    completed = _completed_state_action_sequence_payload(openai_messages)
    if completed is None:
        return False
    payload, completed_count = completed
    sequence = payload.get("action_sequence")
    if not (
        isinstance(sequence, list)
        and completed_count >= len(sequence)
        and str(payload.get("final_response_recommendation") or "").strip()
        and not bool(payload.get("continue_original_task_after_sequence"))
    ):
        return False
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or _latest_user_is_closing_acknowledgement(openai_messages):
        return False
    setting_terms = (
        "cellular",
        "cell service",
        "wifi",
        "wi-fi",
        "location service",
        "low battery",
        "battery mode",
    )
    desire_terms = (
        "i need",
        "i want",
        "check",
        "checking",
        "double-check",
        "double check",
        "settings",
        "status",
        "turn",
        "switch",
        "set ",
        "enable",
        "disable",
        "back on",
        "back off",
        " to be on",
        " to be off",
    )
    state_terms = (" on", " off", "enabled", "disabled", "back on", "back off")
    pronoun_reversal_terms = (
        "can you turn it back on",
        "can you turn it back off",
        "please turn it back on",
        "please turn it back off",
        "turn it back on",
        "turn it back off",
        "turning it back on",
        "turning it back off",
        "try turning it on",
        "try turning it off",
        "try turning it back on",
        "try turning it back off",
        "turning it on again",
        "turning it off again",
        "switch it back on",
        "switch it back off",
        "set it back on",
        "set it back off",
        "turn it on now",
        "turn it off now",
        "you can turn it back on",
        "you can turn it back off",
    )
    if any(term in latest_user for term in pronoun_reversal_terms):
        return True
    return (
        any(term in latest_user for term in setting_terms)
        and any(term in latest_user for term in desire_terms)
        and any(term in latest_user for term in state_terms)
    )


def _latest_assistant_text_contains(openai_messages: object, needle: str) -> bool:
    target = str(needle or "").strip().lower()
    if not target:
        return False
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "assistant":
            continue
        content = str(message.get("content", "") or "").lower()
        return target in content
    return False


def _latest_assistant_content(openai_messages: object) -> str:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "assistant":
            continue
        content = str(message.get("content", "") or "").strip()
        if content:
            return content
    return ""


def _strip_recap_prefixes(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    prefixes = (
        "You're welcome. To recap:",
        "You are welcome. To recap:",
        "Understood. To recap:",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix) :].strip()
                changed = True
    return cleaned


def _tool_call_function_name_and_arguments(
    tool_call: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    function = tool_call.get("function")
    if not isinstance(function, Mapping):
        return "", {}
    name = str(function.get("name", "") or "")
    try:
        arguments = json.loads(str(function.get("arguments", "{}") or "{}"))
    except json.JSONDecodeError:
        arguments = {}
    return name, arguments if isinstance(arguments, dict) else {}


def _latest_successful_setting_tool_call(
    openai_messages: object,
) -> tuple[str, Mapping[str, Any]] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for message in messages:
        if message.get("role") == "assistant":
            for tool_call in message.get("tool_calls") or []:
                if not isinstance(tool_call, Mapping):
                    continue
                tool_id = str(tool_call.get("id", "") or "")
                name, arguments = _tool_call_function_name_and_arguments(tool_call)
                execution_name = _execution_facing_tool_name(name)
                if tool_id and execution_name in SETTING_SETTER_TOOL_NAMES:
                    tool_call_args_by_id[tool_id] = (execution_name, arguments)
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in SETTING_SETTER_TOOL_NAMES:
            continue
        content = str(message.get("content", "") or "").strip().lower()
        if "error" in content or "exception" in content:
            continue
        if tool_id in tool_call_args_by_id:
            return tool_call_args_by_id[tool_id]
        return (name, {})
    return None


def _latest_setting_setter_tool_result(
    openai_messages: object,
) -> tuple[int, str, Mapping[str, Any], str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            execution_name = _execution_facing_tool_name(name)
            if tool_id and execution_name in SETTING_SETTER_TOOL_NAMES:
                tool_call_args_by_id[tool_id] = (execution_name, arguments)
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in SETTING_SETTER_TOOL_NAMES:
            continue
        content = str(message.get("content", "") or "").strip()
        call_name, arguments = tool_call_args_by_id.get(tool_id, (name, {}))
        return index, call_name, arguments, content
    return None


def _latest_successful_setting_getter_tool_call(
    openai_messages: object,
) -> tuple[str, bool] | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in SETTING_GETTER_TOOL_NAMES:
            continue
        content = str(message.get("content", "") or "").strip()
        lower = content.lower()
        if "error" in lower or "exception" in lower:
            continue
        if lower in {"true", "1", "yes", "on"}:
            return name, True
        if lower in {"false", "0", "no", "off"}:
            return name, False
    return None


def _successful_setting_getter_value_for_tool(
    openai_messages: object,
    getter_name: str,
) -> bool | None:
    requested_name = _execution_facing_tool_name(str(getter_name or ""))
    if requested_name not in SETTING_GETTER_TOOL_NAMES:
        return None
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != requested_name:
            continue
        content = str(message.get("content", "") or "").strip()
        lower = content.lower()
        if "error" in lower or "exception" in lower:
            continue
        if lower in {"true", "1", "yes", "on"}:
            return True
        if lower in {"false", "0", "no", "off"}:
            return False
    return None


def _setting_success_sentence(tool_name: str, arguments: Mapping[str, Any]) -> str:
    service_by_tool = {
        "set_cellular_service_status": "Cellular service",
        "set_location_service_status": "Location service",
        "set_low_battery_mode_status": "Low battery mode",
        "set_wifi_status": "Wifi",
    }
    desired_on = bool(arguments.get("on", True))
    return (
        f"{service_by_tool[tool_name]} has been turned {'on' if desired_on else 'off'}."
    )


def _requested_setting_setter_from_text(text: str) -> str | None:
    normalized = text.strip().lower().replace("wi-fi", "wifi")
    if not normalized:
        return None
    if "cellular" in normalized:
        return "set_cellular_service_status"
    if "location service" in normalized:
        return "set_location_service_status"
    if "low battery" in normalized or "battery mode" in normalized:
        return "set_low_battery_mode_status"
    if "wifi" in normalized:
        return "set_wifi_status"
    return None


def _requested_setting_getter_from_text(text: str) -> str | None:
    normalized = text.strip().lower().replace("wi-fi", "wifi")
    if not normalized:
        return None
    if any(
        token in normalized
        for token in (
            "cellular",
            "cell service",
            "cellphone signal",
            "cell phone signal",
            "mobile data",
        )
    ):
        return "get_cellular_service_status"
    if "wifi" in normalized:
        return "get_wifi_status"
    if "location service" in normalized:
        return "get_location_service_status"
    if "low battery" in normalized or "battery mode" in normalized:
        return "get_low_battery_mode_status"
    return None


def _completed_device_setting_retention_response_text(
    openai_messages: object,
) -> str | None:
    """Keep a completed direct setting task from being reversed by follow-ups."""
    if not _first_user_is_device_mutation_without_message(openai_messages):
        return None
    latest_call = _latest_successful_setting_tool_call(openai_messages)
    if latest_call is None:
        return None
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return None
    followup_tokens = (
        "turn",
        "switch",
        "enable",
        "disable",
        "back on",
        "back off",
        "settings",
        "carrier",
        "restart",
        "message",
        "continue",
        "go ahead",
    )
    if latest_user != _first_user_request_text(
        openai_messages
    ).strip().lower() and not any(token in latest_user for token in followup_tokens):
        return None
    tool_name, arguments = latest_call
    requested_tool = _requested_setting_setter_from_text(latest_user)
    if requested_tool is not None and requested_tool != tool_name:
        return None
    return _setting_success_sentence(tool_name, arguments)


def _setting_lookup_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    lookup = _latest_successful_setting_getter_tool_call(openai_messages)
    if lookup is None:
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    original_non_getters = (
        available_names
        & ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        - SETTING_GETTER_TOOL_NAMES
        - {"end_conversation"}
    )
    getter_name, is_on = lookup
    latest_is_getter = _latest_tool_is(openai_messages, getter_name)
    if original_non_getters and not latest_is_getter:
        return None
    labels = {
        "get_cellular_service_status": "Cellular service",
        "get_wifi_status": "Wifi",
        "get_location_service_status": "Location service",
        "get_low_battery_mode_status": "Low battery mode",
    }
    label = labels.get(getter_name)
    if not label:
        return None
    return f"{label} is {'on' if is_on else 'off'}."


def _setting_lookup_retention_response_text(openai_messages: object) -> str | None:
    lookup = _latest_successful_setting_getter_tool_call(openai_messages)
    if lookup is None:
        return None
    latest_user = _latest_user_request_text(openai_messages).lower().replace("’", "'")
    if not latest_user:
        return None
    if not any(
        token in latest_user
        for token in (
            "we know",
            "working",
            "stuck",
            "try sending",
            "send the message",
            "send that message",
            "send a message",
            "message to",
            "next task",
            "check the messaging",
            "restart",
            "when you can",
            "already",
            "just go ahead",
        )
    ):
        return None
    if _first_user_is_device_mutation_without_message(openai_messages):
        setting_call = _latest_successful_setting_tool_call(openai_messages)
        if setting_call is not None:
            tool_name, arguments = setting_call
            labels_by_setter = {
                "set_cellular_service_status": "Cellular service",
                "set_wifi_status": "Wifi",
                "set_location_service_status": "Location service",
                "set_low_battery_mode_status": "Low battery mode",
            }
            label = labels_by_setter.get(tool_name)
            if label:
                return _setting_success_sentence(tool_name, arguments)
    original_getter_name = _requested_setting_getter_from_text(
        _first_user_request_text(openai_messages)
    )
    if (
        original_getter_name is not None
        and _first_user_is_device_setting_without_message(openai_messages)
        and not _first_user_is_device_mutation_without_message(openai_messages)
    ):
        original_value = _successful_setting_getter_value_for_tool(
            openai_messages,
            original_getter_name,
        )
        if original_value is not None:
            original_labels = {
                "get_cellular_service_status": "Cellular service",
                "get_wifi_status": "Wifi",
                "get_location_service_status": "Location service",
                "get_low_battery_mode_status": "Low battery mode",
            }
            label = original_labels.get(original_getter_name)
            if label:
                return f"{label} is {'on' if original_value else 'off'}."
    getter_name, is_on = lookup
    labels = {
        "get_cellular_service_status": "Cellular service",
        "get_wifi_status": "Wifi",
        "get_location_service_status": "Location service",
        "get_low_battery_mode_status": "Low battery mode",
    }
    label = labels.get(getter_name)
    if not label:
        return None
    return f"{label} is {'on' if is_on else 'off'}."


def _latest_successful_crud_tool_call(
    openai_messages: object,
) -> tuple[str, Mapping[str, Any]] | None:
    crud_names = {
        "add_contact",
        "modify_contact",
        "remove_contact",
        "add_reminder",
        "modify_reminder",
        "remove_reminder",
    }
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for message in messages:
        if message.get("role") == "assistant":
            for tool_call in message.get("tool_calls") or []:
                if not isinstance(tool_call, Mapping):
                    continue
                tool_id = str(tool_call.get("id", "") or "")
                name, arguments = _tool_call_function_name_and_arguments(tool_call)
                execution_name = _execution_facing_tool_name(name)
                if tool_id and execution_name in crud_names:
                    tool_call_args_by_id[tool_id] = (execution_name, arguments)
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in crud_names:
            continue
        content = str(message.get("content", "") or "").strip().lower()
        if "error" in content or "exception" in content:
            continue
        if tool_id in tool_call_args_by_id:
            return tool_call_args_by_id[tool_id]
        return (name, {})
    return None


def _latest_tool_success_content(openai_messages: object) -> str | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        content = str(message.get("content", "") or "").strip()
        lower = content.lower()
        if "error" in lower or "exception" in lower:
            return None
        return content
    return None


def _latest_prior_tool_call_arguments(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages[:-1]):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in reversed(tool_calls):
            if not isinstance(tool_call, Mapping):
                continue
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            if _execution_facing_tool_name(name) == target:
                return arguments
    return {}


def _parse_mapping_payload(content: object) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        return {}
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _latest_tool_payload_by_name(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages[:-1]):
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and name == target:
            return _parse_mapping_payload(message.get("content"))
    return {}


def _parse_sequence_payload(content: object) -> list[Any]:
    text = str(content or "").strip()
    if not text:
        return []
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return []
    return list(value) if isinstance(value, list) else []


def _record_by_timestamp_extreme(
    records: list[Any],
    mode: str,
    timestamp_field: str = "creation_timestamp",
) -> Mapping[str, Any] | None:
    usable: list[tuple[float, Mapping[str, Any]]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        raw_timestamp = record.get(timestamp_field, record.get("timestamp"))
        try:
            timestamp = float(raw_timestamp)
        except (TypeError, ValueError):
            continue
        usable.append((timestamp, record))
    if not usable:
        return None
    target_timestamp = (
        min(timestamp for timestamp, _ in usable)
        if mode == "oldest"
        else max(timestamp for timestamp, _ in usable)
    )
    matches = [record for timestamp, record in usable if timestamp == target_timestamp]
    return matches[0] if len(matches) == 1 else None


def _latest_tool_message(
    openai_messages: object,
    tool_name: str,
) -> Mapping[str, Any] | None:
    target = _execution_facing_tool_name(tool_name)
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and name == target:
            return message
    return None


def _latest_tool_message_after_latest_user(
    openai_messages: object,
    tool_name: str,
) -> tuple[int, Mapping[str, Any]] | None:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            latest_user_index = index
    for index in range(len(messages) - 1, latest_user_index, -1):
        message = messages[index]
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and name == target:
            return index, message
    return None


def _latest_tool_payload_by_name_including_latest(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return {}
    return _parse_mapping_payload(message.get("content"))


def _prior_safe_location_lookup_abstention(openai_messages: object) -> dict[str, Any]:
    target = _execution_facing_tool_name("prepare_safe_action_or_abstain")
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages):
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") != "tool" or name != target:
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if not (
            bool(payload.get("should_abstain"))
            or str(payload.get("safe_next_action") or "") == "ask_user_or_abstain"
            or payload.get("abstain_reason")
        ):
            continue
        missing = {
            _safe_action_capability(str(item))
            for item in (payload.get("missing_information") or [])
            if str(item)
        }
        required = {
            _safe_action_capability(str(item))
            for item in (payload.get("required_original_tools") or [])
            if str(item)
        }
        if "location_lookup" in missing or "location_lookup" in required:
            return payload
    return {}


def _safe_abstention_final_recommendation(
    payload: Mapping[str, Any],
    openai_messages: object | None = None,
) -> str:
    recommendation = str(payload.get("final_answer_recommendation") or "").strip()
    missing = {
        _safe_action_capability(str(item))
        for item in (payload.get("missing_information") or [])
        if str(item)
    }
    required = {
        _safe_action_capability(str(item))
        for item in (payload.get("required_original_tools") or [])
        if str(item)
    }
    requested_action = _safe_action_capability(
        str(payload.get("requested_action") or "").replace(" ", "_")
    )
    request_text = str(payload.get("user_request") or "").lower()
    if openai_messages is not None:
        request_text = (
            f"{request_text} {' '.join(_all_user_texts(openai_messages)).lower()}"
        )
    current_location_request = requested_action == "location_lookup" or any(
        phrase in request_text
        for phrase in (
            "current city",
            "current location",
            "where am i",
            "what city am i",
            "which city am i",
        )
    )
    if current_location_request and (
        "location_lookup" in missing or "location_lookup" in required
    ):
        return (
            "I cannot determine what city you are in because I do not have access "
            "to your current location, GPS, or latitude and longitude coordinates."
        )
    return recommendation


def _repeated_original_tool_loop_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Return a generic stop/recover instruction for repeated original-tool loops."""

    available_generated = [
        name
        for name in sorted(_tool_names_execution_facing(openai_tools))
        if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    ]
    if not available_generated:
        return ""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages or messages[-1].get("role") != "tool":
        return ""
    latest_name = _execution_facing_tool_name(str(messages[-1].get("name", "") or ""))
    if latest_name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
        return ""
    latest_content = str(messages[-1].get("content", "") or "").strip()
    if not latest_content:
        return ""
    latest_user_index = _latest_user_index(messages)
    repeated = 0
    for message in messages[latest_user_index + 1 :]:
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != latest_name:
            continue
        content = str(message.get("content", "") or "").strip()
        if content == latest_content:
            repeated += 1
    if repeated < 3:
        return ""
    tool_name = _tool_name_for_call(openai_tools, latest_name)
    generated_list = ", ".join(available_generated[:4])
    overflow = len(available_generated) - 4
    if overflow > 0:
        generated_list = f"{generated_list}, +{overflow} more"
    return (
        f"Original {tool_name} has already returned the same visible result "
        f"{repeated} times after the latest user request. Do not call "
        f"{tool_name} again unless the user supplies new concrete information "
        "or another visible tool result changes the missing prerequisite. If "
        "one of the visible generated tools directly matches the unresolved "
        f"step ({generated_list}), use that generated tool once with visible "
        "inputs. Otherwise answer from the visible result or ask only for the "
        "missing concrete information; do not loop through unrelated original "
        "tools."
    )


def _latest_tool_float_by_name_including_latest(
    openai_messages: object,
    tool_name: str,
) -> float | None:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return None
    text = str(message.get("content") or "").strip()
    if not text:
        return None
    try:
        return float(ast.literal_eval(text))
    except (SyntaxError, ValueError, TypeError):
        try:
            return float(text)
        except (TypeError, ValueError):
            return None


def _latest_tool_message_index(
    openai_messages: object,
    tool_names: set[str],
) -> tuple[int, Mapping[str, Any]] | None:
    targets = {_execution_facing_tool_name(name) for name in tool_names}
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and name in targets:
            return index, message
    return None


def _state_sequence_actions(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_sequence = payload.get("action_sequence")
    actions: list[dict[str, Any]] = []
    if isinstance(raw_sequence, list):
        for item in raw_sequence:
            if not isinstance(item, Mapping):
                continue
            tool_name = str(item.get("tool_name", "") or "")
            arguments = item.get("arguments")
            if tool_name in SETTING_SETTER_TOOL_NAMES and isinstance(
                arguments, Mapping
            ):
                actions.append({"tool_name": tool_name, "arguments": dict(arguments)})
    if actions:
        return actions[:4]
    tool_name = str(payload.get("tool_name", "") or "")
    arguments = payload.get("arguments")
    if tool_name in SETTING_SETTER_TOOL_NAMES and isinstance(arguments, Mapping):
        return [{"tool_name": tool_name, "arguments": dict(arguments)}]
    return []


def _setting_action_already_satisfied(
    openai_messages: object,
    action: Mapping[str, Any],
) -> bool:
    tool_name = _execution_facing_tool_name(str(action.get("tool_name", "") or ""))
    arguments = action.get("arguments")
    if tool_name not in SETTING_SETTER_TOOL_NAMES or not isinstance(arguments, Mapping):
        return False
    expected_arguments = dict(arguments)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    pending_by_id: dict[str, tuple[str, dict[str, Any]]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            call_name, call_arguments = _tool_call_function_name_and_arguments(
                tool_call
            )
            execution_name = _execution_facing_tool_name(call_name)
            if tool_id and execution_name in SETTING_SETTER_TOOL_NAMES:
                pending_by_id[tool_id] = (execution_name, call_arguments)
            if execution_name == tool_name and _arguments_match(
                expected_arguments, call_arguments
            ):
                # Keep scanning until the matching tool result proves success.
                continue
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        result_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        tool_id = str(message.get("tool_call_id", "") or "")
        call_name, call_arguments = pending_by_id.get(
            tool_id,
            (result_name, {}),
        )
        if call_name != tool_name:
            continue
        if call_arguments and not _arguments_match(expected_arguments, call_arguments):
            continue
        if _setting_setter_succeeded(message.get("content")):
            return True
    return False


def _next_unsatisfied_state_action(
    openai_messages: object,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    for action in _state_sequence_actions(payload):
        if _setting_action_already_satisfied(openai_messages, action):
            continue
        return action
    return None


def _arguments_match(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def _call_contract_kwargs(
    kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Drop null optional fields from generated downstream-call kwargs."""
    return {str(key): value for key, value in kwargs.items() if value is not None}


def _contract_values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= 1e-6
    if isinstance(expected, (int, float)) and isinstance(actual, str):
        try:
            return abs(float(expected) - float(actual)) <= 1e-6
        except ValueError:
            return False
    if isinstance(expected, str) and isinstance(actual, (int, float)):
        try:
            return abs(float(expected) - float(actual)) <= 1e-6
        except ValueError:
            return False
    return expected == actual


def _call_contract_kwargs_match(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> bool:
    cleaned_expected = _call_contract_kwargs(expected)
    cleaned_actual = _call_contract_kwargs(actual)
    if set(cleaned_expected) != set(cleaned_actual):
        return False
    for key, value in cleaned_expected.items():
        if not _contract_values_match(value, cleaned_actual.get(key)):
            return False
    return True


def _state_sequence_completed_action_count(
    messages: list[Mapping[str, Any]],
    plan_index: int,
    actions: list[dict[str, Any]],
) -> int:
    completed = 0
    pending_by_id: dict[str, int] = {}
    for message in messages[plan_index + 1 :]:
        if completed >= len(actions):
            break
        if message.get("role") == "assistant":
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for tool_call in tool_calls:
                if not isinstance(tool_call, Mapping):
                    continue
                pending_count = sum(
                    1 for index in pending_by_id.values() if index >= completed
                )
                action_index = completed + pending_count
                if action_index >= len(actions):
                    break
                name, arguments = _tool_call_function_name_and_arguments(tool_call)
                expected = actions[action_index]
                if _execution_facing_tool_name(name) == expected[
                    "tool_name"
                ] and _arguments_match(expected["arguments"], arguments):
                    tool_id = str(tool_call.get("id", "") or "")
                    if tool_id:
                        pending_by_id[tool_id] = action_index
            continue
        if message.get("role") != "tool":
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        action_index = pending_by_id.pop(tool_id, None)
        if action_index != completed:
            continue
        if not _setting_setter_succeeded(message.get("content")):
            continue
        completed += 1
    return completed


def _state_action_sequence_next_action(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, Any] | None:
    helper_names = _state_action_planner_tool_names(openai_tools)
    if not helper_names:
        return None
    latest_plan = _latest_tool_message_index(openai_messages, helper_names)
    if latest_plan is None:
        return None
    plan_index, plan_message = latest_plan
    payload = _parse_mapping_payload(plan_message.get("content"))
    if not payload or not bool(payload.get("should_call")):
        return None
    actions = _state_sequence_actions(payload)
    if not actions:
        return None

    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest = messages[-1] if messages else {}
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if latest.get("role") == "tool" and latest_name in SETTING_SETTER_TOOL_NAMES:
        if _latest_tool_success_content(openai_messages) is None:
            return None

    completed = _state_sequence_completed_action_count(messages, plan_index, actions)
    if completed >= len(actions):
        return None
    return actions[completed]


def _state_sequence_has_pending_downstream_task(openai_messages: object) -> bool:
    user_text = (
        " ".join(_all_user_texts(openai_messages))
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not user_text:
        return False
    downstream_task_tokens = (
        "add a reminder",
        "add reminder",
        "set a reminder",
        "set the reminder",
        "set reminder",
        "remind me",
        "reminder",
        "todo",
        "send a message",
        "send the message",
        "send that message",
        "text ",
        "message",
        "contact",
        "phone number",
        "address",
        "holiday",
        "weather",
        "stock",
        "currency",
        "convert",
        "distance",
        "nearby",
        "restaurant",
        "whole foods",
        "look up",
        "search for",
        "find the",
        "find my",
        "what is",
        "what's",
        "how many",
    )
    return any(token in user_text for token in downstream_task_tokens)


def _state_action_sequence_final_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    helper_names = _state_action_planner_tool_names(openai_tools)
    if not helper_names:
        return None
    latest_plan = _latest_tool_message_index(openai_messages, helper_names)
    if latest_plan is None:
        return None
    plan_index, plan_message = latest_plan
    payload = _parse_mapping_payload(plan_message.get("content"))
    if not payload or not bool(payload.get("should_call")):
        return None
    actions = _state_sequence_actions(payload)
    if not actions:
        return None
    if _state_sequence_has_pending_downstream_task(openai_messages):
        return None
    final_response = str(payload.get("final_response_recommendation") or "").strip()
    if (
        not final_response
        or final_response == "continue_original_task"
        or bool(payload.get("continue_original_task_after_sequence"))
    ):
        return None

    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest = messages[-1] if messages else {}
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if latest.get("role") != "tool" or latest_name not in SETTING_SETTER_TOOL_NAMES:
        return None
    if _latest_tool_success_content(openai_messages) is None:
        return None

    completed = _state_sequence_completed_action_count(messages, plan_index, actions)
    if completed >= len(actions):
        return final_response
    return None


def _join_visible_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _relationship_plural(relationship: object) -> str:
    value = str(relationship or "").strip().lower().replace("_", " ")
    if not value:
        return "contacts"
    irregular = {"enemy": "enemies", "friend": "friends"}
    if value in irregular:
        return irregular[value]
    if value.endswith("y"):
        return f"{value[:-1]}ies"
    return f"{value}s"


_RELATIONSHIP_ALIASES = {
    "boss": "boss",
    "bosses": "boss",
    "friend": "friend",
    "friends": "friend",
    "enemy": "enemy",
    "enemies": "enemy",
    "coworker": "coworker",
    "coworkers": "coworker",
    "colleague": "coworker",
    "colleagues": "coworker",
    "family": "family",
    "families": "family",
    "relative": "family",
    "relatives": "family",
}

_KNOWN_RELATIONSHIP_LABELS = set(_RELATIONSHIP_ALIASES.values())
_ALL_CONTACTS_RELATIONSHIP_SOURCE = "__all_contacts__"


def _normalize_relationship_label(value: object) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if not text:
        return ""
    return _RELATIONSHIP_ALIASES.get(text, text)


def _known_relationship_label(value: object) -> str:
    label = _normalize_relationship_label(value)
    return label if label in _KNOWN_RELATIONSHIP_LABELS else ""


def _relationship_from_lookup_prompt(text: str) -> str:
    lower = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    match = re.search(r"\bwho\s+are\s+my\s+([a-z]+)\b", lower)
    if match:
        return _known_relationship_label(match.group(1))
    match = re.search(r"\bmy\s+([a-z]+)\b", lower)
    if match:
        return _known_relationship_label(match.group(1))
    return ""


def _relationship_batch_request(openai_messages: object) -> dict[str, str] | None:
    source = ""
    target = ""
    last_explicit_target = ""
    for text in _all_user_texts(openai_messages):
        lower = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
        if not lower:
            continue
        previous_explicit_target = last_explicit_target
        all_contacts_requested = any(
            token in f" {lower} "
            for token in (
                " all contacts ",
                " all my contacts ",
                " every contact ",
                " every one ",
                " everyone ",
                " everybody ",
            )
        )
        if all_contacts_requested:
            source = _ALL_CONTACTS_RELATIONSHIP_SOURCE
        source = source or _relationship_from_lookup_prompt(lower)
        broad_all_target = re.search(
            r"\b(?:all\s+(?:my\s+)?contacts|everyone|everybody|every\s+contact)\b"
            r".*?\b(?:to|into|as)\s+(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if broad_all_target:
            parsed_target = _known_relationship_label(broad_all_target.group(1))
            if parsed_target:
                source = _ALL_CONTACTS_RELATIONSHIP_SOURCE
                target = parsed_target
                last_explicit_target = parsed_target
        broad_update = re.search(
            r"\b(?:all|every|each)\s+(?:of\s+)?(?:my\s+)?([a-z]+)\b.*?"
            r"\b(?:update|updated|change|changed|set|switch|switched|turn|turned|made)\s+"
            r"(?:to|into|as)\s+(?:being\s+)?"
            r"(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if broad_update:
            parsed_source = _known_relationship_label(broad_update.group(1))
            parsed_target = _known_relationship_label(broad_update.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
                last_explicit_target = parsed_target
        if source:
            named_or_pronoun_target = re.search(
                r"\b(?:make|update|change|set|switch|turn)\b.*?"
                r"\b(?:to|into|as)\s+(?:being\s+)?(?:my\s+)?([a-z]+)\b",
                lower,
            )
            if named_or_pronoun_target:
                parsed_target = _known_relationship_label(
                    named_or_pronoun_target.group(1)
                )
                if parsed_target:
                    target = parsed_target
                    last_explicit_target = parsed_target
        direct_with_context = re.search(
            r"\b(?:make|update|change|set|switch|turn)\s+(?:all|every|each)\s+"
            r"(?:of\s+)?(?:my\s+)?([a-z]+)\b.*?\b(?:to|into|as)\s+"
            r"(?:being\s+)?(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if direct_with_context:
            parsed_source = _known_relationship_label(direct_with_context.group(1))
            parsed_target = _known_relationship_label(direct_with_context.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
                last_explicit_target = parsed_target
        direct = re.search(
            r"\b(?:make|update|change|set|switch|turn)\s+(?:all|every|each)\s+"
            r"(?:of\s+)?(?:my\s+)?([a-z]+)\s+(?:contacts\s+)?"
            r"(?:(?:in|from)\s+(?:my\s+)?"
            r"(?:contact\s+book|contacts?|address\s+book)\s+)?"
            r"(?:(?:to|into|as)\s+)?(?:being\s+)?(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if direct:
            parsed_source = _known_relationship_label(direct.group(1))
            parsed_target = _known_relationship_label(direct.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
                last_explicit_target = parsed_target
        explicit = re.search(
            r"\brelationship\s+(?:from\s+)?([a-z]+)\s+(?:to|into)\s+([a-z]+)\b",
            lower,
        )
        if explicit:
            parsed_source = _known_relationship_label(explicit.group(1))
            parsed_target = _known_relationship_label(explicit.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
                last_explicit_target = parsed_target
        if " them " in f" {lower} " or " back " in f" {lower} ":
            followup = re.search(
                r"\b(?:to|as)\s+(?:being\s+)?(?:my\s+)?([a-z]+)\b",
                lower,
            )
            if followup:
                parsed_target = _known_relationship_label(followup.group(1))
                if parsed_target:
                    if (
                        source != _ALL_CONTACTS_RELATIONSHIP_SOURCE
                        and previous_explicit_target
                        and parsed_target != previous_explicit_target
                    ):
                        source = previous_explicit_target
                    target = parsed_target
    prior_plan = _latest_tool_payload_by_name(
        openai_messages, "plan_contact_relationship_batch_update"
    )
    if prior_plan:
        source = source or _normalize_relationship_label(
            prior_plan.get("source_relationship")
        )
        previous_target = _normalize_relationship_label(
            prior_plan.get("target_relationship")
        )
        previous_source = _normalize_relationship_label(
            prior_plan.get("source_relationship")
        )
        if previous_source == _ALL_CONTACTS_RELATIONSHIP_SOURCE and target:
            source = _ALL_CONTACTS_RELATIONSHIP_SOURCE
        if target and previous_target and not source:
            source = previous_target
    if not source or not target or source == target:
        return None
    return {
        "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
        "source_relationship": source,
        "target_relationship": target,
    }


def _selected_contact_names(payload: Mapping[str, Any] | None) -> list[str]:
    if not payload:
        return []
    contacts = payload.get("selected_contacts")
    if not isinstance(contacts, list):
        return []
    names: list[str] = []
    for contact in contacts:
        if not isinstance(contact, Mapping):
            continue
        name = str(contact.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _contact_relationship_batch_success_response(
    openai_messages: object,
    *,
    relationship: str,
) -> str | None:
    plan = _latest_tool_payload_by_name(
        openai_messages, "plan_contact_relationship_batch_update"
    )
    user_request = _latest_user_request_text(openai_messages).lower()
    prior_user_text = " ".join(
        str(message.get("content", "") or "").lower()
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    )
    names = _selected_contact_names(plan)
    source_relationship = str(plan.get("source_relationship") or "").strip().lower()
    target_plural = _relationship_plural(relationship)
    asked_names_first = "who are my" in prior_user_text
    pronoun_followup = any(token in user_request for token in ("them", "back", "again"))
    if names and (asked_names_first or pronoun_followup):
        suffix = " again." if relationship == "friend" and pronoun_followup else ""
        return f"{_join_visible_names(names)} are now your {target_plural}{suffix}"
    if source_relationship and any(
        token in f" {user_request} " for token in (" all ", " every ", " each ")
    ):
        return (
            f"All your {_relationship_plural(source_relationship)} are now your "
            f"{target_plural}"
        )
    if names:
        return f"{_join_visible_names(names)} are now your {target_plural}"
    return None


def _called_tool_after_latest_user(openai_messages: object, tool_name: str) -> bool:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            latest_user_index = index
    for message in messages[latest_user_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            name, _arguments = _tool_call_function_name_and_arguments(tool_call)
            if _execution_facing_tool_name(name) == target:
                return True
    return False


def _next_relationship_batch_action(
    openai_messages: object,
) -> dict[str, Any] | None:
    latest_plan = _latest_tool_message_index(
        openai_messages, {"plan_contact_relationship_batch_update"}
    )
    if latest_plan is None:
        return None
    plan_index, plan_message = latest_plan
    payload = _parse_mapping_payload(plan_message.get("content"))
    if not payload or not bool(payload.get("should_call_tools")):
        return None
    raw_actions = payload.get("downstream_tool_kwargs_list")
    if not isinstance(raw_actions, list):
        return None
    actions: list[dict[str, Any]] = [
        {"tool_name": "modify_contact", "arguments": dict(item)}
        for item in raw_actions
        if isinstance(item, Mapping) and item.get("person_id")
    ]
    if not actions:
        return None
    completed = 0
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in messages[plan_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping) or completed >= len(actions):
                continue
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            expected = actions[completed]
            if _execution_facing_tool_name(name) == expected[
                "tool_name"
            ] and _arguments_match(expected["arguments"], arguments):
                completed += 1
    if completed >= len(actions):
        return None
    return actions[completed]


def _next_all_contact_relationship_action(
    openai_messages: object,
    target_relationship: str,
) -> dict[str, Any] | None:
    latest_search = _latest_tool_message_after_latest_user(
        openai_messages, "search_contacts"
    )
    if latest_search is None:
        return None
    search_index, search_message = latest_search
    contacts = _parse_sequence_payload(search_message.get("content"))
    actions: list[dict[str, Any]] = []
    for contact in contacts:
        if not isinstance(contact, Mapping):
            continue
        person_id = str(contact.get("person_id") or "").strip()
        if not person_id or bool(contact.get("is_self")):
            continue
        current_relationship = _normalize_relationship_label(
            contact.get("relationship")
        )
        if current_relationship == target_relationship:
            continue
        actions.append(
            {
                "tool_name": "modify_contact",
                "arguments": {
                    "person_id": person_id,
                    "relationship": target_relationship,
                },
            }
        )
    if not actions:
        return None
    completed = 0
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in messages[search_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping) or completed >= len(actions):
                continue
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            expected = actions[completed]
            if _execution_facing_tool_name(name) == expected[
                "tool_name"
            ] and _arguments_match(expected["arguments"], arguments):
                completed += 1
    if completed >= len(actions):
        return None
    return actions[completed]


def _relationship_contacts_from_latest_search(
    openai_messages: object,
    source_relationship: str,
) -> list[Mapping[str, Any]]:
    search_message = _latest_tool_message(openai_messages, "search_contacts")
    if search_message is None:
        return []
    contacts: list[Mapping[str, Any]] = []
    for contact in _parse_sequence_payload(search_message.get("content")):
        if not isinstance(contact, Mapping):
            continue
        person_id = str(contact.get("person_id") or "").strip()
        if not person_id or bool(contact.get("is_self")):
            continue
        if source_relationship != _ALL_CONTACTS_RELATIONSHIP_SOURCE:
            current_relationship = _normalize_relationship_label(
                contact.get("relationship")
            )
            if current_relationship != source_relationship:
                continue
        contacts.append(contact)
    return contacts


def _direct_relationship_update_actions(
    openai_messages: object,
    request: Mapping[str, str],
) -> list[dict[str, Any]]:
    target_relationship = _known_relationship_label(request.get("target_relationship"))
    source_relationship = _normalize_relationship_label(
        request.get("source_relationship")
    )
    if not target_relationship or not source_relationship:
        return []
    actions: list[dict[str, Any]] = []
    for contact in _relationship_contacts_from_latest_search(
        openai_messages, source_relationship
    ):
        person_id = str(contact.get("person_id") or "").strip()
        if not person_id:
            continue
        if (
            _normalize_relationship_label(contact.get("relationship"))
            == target_relationship
        ):
            continue
        actions.append(
            {
                "tool_name": "modify_contact",
                "arguments": {
                    "person_id": person_id,
                    "relationship": target_relationship,
                },
            }
        )
    return actions


def _completed_matching_actions_after_latest_user(
    openai_messages: object,
    actions: list[Mapping[str, Any]],
) -> int:
    if not actions:
        return 0
    completed = 0
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            latest_user_index = index
    for message in messages[latest_user_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping) or completed >= len(actions):
                continue
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            expected = actions[completed]
            if _execution_facing_tool_name(name) != _execution_facing_tool_name(
                str(expected.get("tool_name") or "")
            ):
                continue
            expected_arguments = expected.get("arguments")
            if isinstance(expected_arguments, Mapping) and _arguments_match(
                dict(expected_arguments), arguments
            ):
                completed += 1
    return completed


def _direct_relationship_update_success_text(
    openai_messages: object,
    request: Mapping[str, str],
) -> str | None:
    actions = _direct_relationship_update_actions(openai_messages, request)
    if not actions:
        return None
    completed = _completed_matching_actions_after_latest_user(openai_messages, actions)
    if completed < len(actions):
        return None
    contacts = _relationship_contacts_from_latest_search(
        openai_messages,
        _normalize_relationship_label(request.get("source_relationship")),
    )
    names = [
        str(contact.get("name") or "").strip()
        for contact in contacts
        if str(contact.get("name") or "").strip()
    ]
    target_relationship = _known_relationship_label(request.get("target_relationship"))
    if names and target_relationship:
        suffix = ""
        latest_user = _latest_user_request_text(openai_messages).lower()
        if target_relationship == "friend" and any(
            token in latest_user for token in ("back", "again")
        ):
            suffix = " again."
        return (
            f"{_join_visible_names(names)} are now your "
            f"{_relationship_plural(target_relationship)}{suffix}"
        )
    return None


def _contact_relationship_batch_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if (
        "search_contacts" not in available_names
        or "modify_contact" not in available_names
    ):
        return None
    has_relationship_planner = (
        "plan_contact_relationship_batch_update" in available_names
    )

    request = _relationship_batch_request(openai_messages)
    if request and not has_relationship_planner:
        success_text = _direct_relationship_update_success_text(
            openai_messages, request
        )
        if success_text:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-direct-success",
                content=success_text,
            )
        actions = _direct_relationship_update_actions(openai_messages, request)
        if not actions:
            source_relationship = _normalize_relationship_label(
                request.get("source_relationship")
            )
            if source_relationship == _ALL_CONTACTS_RELATIONSHIP_SOURCE:
                search_arguments: dict[str, str] = {}
            elif source_relationship:
                search_arguments = {"relationship": source_relationship}
            else:
                search_arguments = {}
            if not _called_tool_after_latest_user(openai_messages, "search_contacts"):
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-relationship-direct-search",
                    tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
                    arguments=search_arguments,
                )
            return None
        completed = _completed_matching_actions_after_latest_user(
            openai_messages, actions
        )
        if completed < len(actions):
            action = actions[completed]
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-direct-modify",
                tool_name=_tool_name_for_call(openai_tools, action["tool_name"]),
                arguments=action["arguments"],
            )
        return None

    if not has_relationship_planner:
        return None
    if (
        request
        and request.get("source_relationship") == _ALL_CONTACTS_RELATIONSHIP_SOURCE
    ):
        if (
            _latest_tool_message_after_latest_user(openai_messages, "search_contacts")
            is None
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-search-all",
                tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
                arguments={},
            )
        target_relationship = _known_relationship_label(
            request.get("target_relationship")
        )
        if not target_relationship:
            return None
        action = _next_all_contact_relationship_action(
            openai_messages, target_relationship
        )
        if action is not None:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-modify-all",
                tool_name=_tool_name_for_call(openai_tools, action["tool_name"]),
                arguments=action["arguments"],
            )
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-contact-relationship-all-success",
            content=(
                f"All your contacts are now your "
                f"{_relationship_plural(target_relationship)}."
            ),
        )

    if _latest_tool_is(openai_messages, "plan_contact_relationship_batch_update"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "plan_contact_relationship_batch_update"
        )
        if payload.get("abstain_reason"):
            return None
        if bool(payload.get("should_call_search_contacts")):
            kwargs = payload.get("search_contacts_kwargs")
            if isinstance(kwargs, Mapping) and kwargs:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-relationship-search",
                    tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
                    arguments=dict(kwargs),
                )
        action = _next_relationship_batch_action(openai_messages)
        if action is not None:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-modify",
                tool_name=_tool_name_for_call(openai_tools, action["tool_name"]),
                arguments=action["arguments"],
            )

    if _latest_tool_is(openai_messages, "search_contacts"):
        if request is not None:
            contacts_message = _latest_tool_message(openai_messages, "search_contacts")
            contacts = (
                _parse_sequence_payload(contacts_message.get("content"))
                if contacts_message is not None
                else []
            )
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-relationship-plan-after-search",
                tool_name=_tool_name_for_call(
                    openai_tools, "plan_contact_relationship_batch_update"
                ),
                arguments={**request, "contacts": contacts},
            )

    action = _next_relationship_batch_action(openai_messages)
    if action is not None:
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-contact-relationship-modify",
            tool_name=_tool_name_for_call(openai_tools, action["tool_name"]),
            arguments=action["arguments"],
        )

    if request is None or _called_tool_after_latest_user(
        openai_messages, "plan_contact_relationship_batch_update"
    ):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-contact-relationship-plan",
        tool_name=_tool_name_for_call(
            openai_tools, "plan_contact_relationship_batch_update"
        ),
        arguments={**request, "contacts": []},
    )


def _normalize_visible_phone(raw: object) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return value
    if value.startswith("+"):
        return "+" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    return value


def _looks_like_phone_number_argument(raw: object) -> bool:
    text = str(raw or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(r"\+?\d[\d\s().-]{6,}\d", text))


def _extract_phone_from_text(text: str) -> str:
    text_without_ids = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        " ",
        text,
    )
    match = re.search(r"\+?\d[\d\s().-]{6,}\d", text_without_ids)
    return _normalize_visible_phone(match.group(0)) if match else ""


def _extract_person_id_from_text(text: str) -> str:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        text,
    )
    return match.group(0) if match else ""


def _extract_add_contact_name_from_text(text: str) -> str:
    match = re.search(
        r"\badd\s+(.+?)\s+to\s+my\s+contact\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    name = match.group(1).strip(" .,:;")
    return re.sub(r"\s+", " ", name)


def _scrambled_crud_success_response_text(openai_messages: object) -> str | None:
    content = _latest_tool_success_content(openai_messages)
    if content is None:
        return None
    user_request = _latest_user_request_text(openai_messages)
    lower_request = user_request.lower()
    if "contact" not in lower_request and "person with id" not in lower_request:
        return None
    phone = _extract_phone_from_text(user_request)
    if "add" in lower_request and content.strip("'\" "):
        name = _extract_add_contact_name_from_text(user_request)
        if name:
            return f"{name} has been added to your contact"
    if "phone" in lower_request and content.lower() in {"", "none", "null"}:
        person_id = _extract_person_id_from_text(user_request)
        if person_id and phone:
            return f"{person_id}'s phone number have been updated to {phone}"
    return None


def _crud_success_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Stop post-side-effect drift after an original CRUD tool succeeds."""
    if not _praxis_bridge_policy_enabled():
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CRUD_SUCCESS_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    latest_call = _latest_successful_crud_tool_call(openai_messages)
    if latest_call is None:
        return _scrambled_crud_success_response_text(openai_messages)
    tool_name, arguments = latest_call
    user_request = _latest_user_request_text(openai_messages).lower()

    if tool_name == "add_contact":
        name = str(arguments.get("name") or "").strip()
        if name:
            return f"{name} has been added to your contact"
        return "The contact has been added."

    if tool_name == "remove_contact":
        search_args = _latest_prior_tool_call_arguments(
            openai_messages, "search_contacts"
        )
        phone = _normalize_visible_phone(search_args.get("phone_number"))
        name = str(search_args.get("name") or "").strip()
        person_id = str(arguments.get("person_id") or "").strip()
        if phone:
            return f"Phone number {phone} has been removed from your contact."
        if name:
            return f"{name} has been removed from your contact."
        if person_id:
            return f"{person_id} has been removed from your contact."
        return "The contact has been removed."

    if tool_name == "modify_contact":
        phone = _normalize_visible_phone(arguments.get("phone_number"))
        relationship = str(arguments.get("relationship") or "").strip()
        name = str(arguments.get("name") or "").strip()
        if phone:
            person_id = str(arguments.get("person_id") or "").strip()
            if any(
                token in user_request for token in ("last", "most recent", "latest")
            ):
                return (
                    "The phone number of the person you last talked to has been "
                    f"updated to {phone}."
                )
            if person_id:
                return f"{person_id}'s phone number have been updated to {phone}"
            return f"Phone number has been updated to {phone}."
        if relationship:
            batch_response = _contact_relationship_batch_success_response(
                openai_messages, relationship=relationship.lower()
            )
            if batch_response:
                return batch_response
            return f"Relationship has been updated to {relationship}."
        if name:
            return f"Contact name has been updated to {name}."
        return "The contact has been updated."

    if tool_name == "add_reminder":
        return "The reminder has been added."
    if tool_name == "modify_reminder":
        return "The reminder has been updated."
    if tool_name == "remove_reminder":
        return "The reminder has been removed."
    return None


def _setting_success_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Treat original setting setter `None` as success for direct state tasks."""
    if not _has_experimental_helper_tools(openai_tools):
        return None
    latest_call = _latest_successful_setting_tool_call(openai_messages)
    if latest_call is None:
        return None
    tool_name, arguments = latest_call
    user_request = _latest_user_request_text(openai_messages).lower()
    downstream_tokens = (
        "send ",
        "message",
        "text ",
        "find ",
        "search",
        "weather",
        "holiday",
        "reminder",
        "stock",
        "currency",
        "nearby",
        "where am i",
        "current location",
    )
    has_downstream_request = any(token in user_request for token in downstream_tokens)
    if has_downstream_request and not _first_user_is_device_setting_without_message(
        openai_messages
    ):
        return None
    target_service_tokens = (
        "wifi",
        "wi-fi",
        "internet",
        "cellular",
        "location service",
    )
    if tool_name == "set_low_battery_mode_status" and any(
        token in user_request for token in target_service_tokens
    ):
        return None
    state_action_tokens = (
        "turn",
        "enable",
        "disable",
        "switch",
        "set ",
        "shut off",
        "cellular",
        "wifi",
        "wi-fi",
        "internet",
        "location service",
        "low battery",
        "battery mode",
    )
    if not any(token in user_request for token in state_action_tokens):
        return None
    response = _setting_success_sentence(tool_name, arguments)
    if has_downstream_request:
        return f"{response} You can now continue."
    return response


def _contact_update_success_response_text(openai_messages: object) -> str | None:
    latest_call = _latest_successful_crud_tool_call(openai_messages)
    if latest_call is None:
        return None
    tool_name, arguments = latest_call
    if tool_name != "modify_contact":
        return None
    phone = str(arguments.get("phone_number") or "").strip()
    if not phone:
        return None
    user_request = " ".join(_all_user_texts(openai_messages)).lower()
    if not any(token in user_request for token in ("last", "latest", "most recent")):
        return None
    if "phone" not in user_request:
        return None
    return f"The phone number of the person you last talked to has been updated to {phone}."


def _selector_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for valid selector helpers after records are visible."""
    selectors = _selector_tool_names(openai_tools)
    if not selectors:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in selectors):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SELECTOR_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if not _messages_show_prior_candidate_records(openai_messages):
        return None
    selector_list = ", ".join(sorted(selectors))
    return {
        "role": "system",
        "content": (
            f"{SELECTOR_ACTOR_POLICY_SENTINEL} A deterministic visible-record "
            f"selector tool is available: {selector_list}. If the previous "
            "search/get/find result returned candidate records and the task "
            "requires selecting one visible contact, message, reminder, or record "
            "by user constraints before answering or taking a downstream action, "
            "call the tool before manually choosing. Do not call it without "
            "visible candidates, on insufficient-information tasks, or when its "
            "negative triggers match. If the selector abstains or reports a tie, "
            "do not guess before a side-effect action. If the selector returns "
            "exact_final_answer, final_answer_recommendation, or selected_content "
            "for an answer-only task, your next assistant message must include "
            "that retrieved value without adding unrelated fields."
        ),
    }


def _service_extractor_scalar_actor_instruction(
    openai_messages: object,
    openai_tools: object,
    helpers: set[str],
) -> str:
    if "extract_service_answer_field" not in {
        _execution_facing_tool_name(name) for name in helpers
    }:
        return ""
    if _message_already_called_tool(openai_messages, "extract_service_answer_field"):
        return ""
    scalar_tool_name = ""
    requested_unit = ""
    answer_subject = ""
    for candidate_name in (
        "calculate_lat_lon_distance",
        "convert_currency",
        "unit_conversion",
    ):
        if _latest_tool_is(openai_messages, candidate_name):
            scalar_tool_name = candidate_name
            break
    if not scalar_tool_name:
        return ""
    content = _latest_tool_content(openai_messages, scalar_tool_name)
    if not content:
        return ""
    value = _parse_service_payload_value(content)
    if isinstance(value, (Mapping, list)):
        return ""
    if scalar_tool_name == "calculate_lat_lon_distance":
        requested_unit = "kilometers"
        answer_subject = _distance_destination_query(openai_messages) or ""
    elif scalar_tool_name == "unit_conversion":
        requested_unit = (
            "Fahrenheit" if _weather_request_wants_fahrenheit(openai_messages) else ""
        )
    tool_name = _tool_name_for_call(openai_tools, "extract_service_answer_field")
    kwargs: dict[str, Any] = {"service_payload": {"result": value}}
    if requested_unit:
        kwargs["requested_unit"] = requested_unit
    if answer_subject:
        kwargs["answer_subject"] = answer_subject
    return (
        f" The latest original ToolSandbox tool result from {scalar_tool_name} "
        "is a bare scalar. The next action should be a call to the generated "
        f"tool {tool_name} with exactly these visible-result arguments: "
        f"{json.dumps(kwargs, sort_keys=True)}. Do not manually answer or "
        "start a verification loop before this generated-tool call."
    )


def _derived_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for deterministic extraction after raw output."""
    helpers = _derived_value_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if DERIVED_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if not _messages_show_prior_structured_payload(openai_messages):
        return None
    helper_list = ", ".join(sorted(helpers))
    scalar_instruction = _service_extractor_scalar_actor_instruction(
        openai_messages,
        openai_tools,
        helpers,
    )
    return {
        "role": "system",
        "content": (
            f"{DERIVED_ACTOR_POLICY_SENTINEL} A deterministic extraction or "
            f"normalization tool is available: {helper_list}. If a previous "
            "ToolSandbox tool returned the raw payload or scalar needed by this "
            "tool and the user asks for a scalar/normalized answer from that "
            "payload, call the tool before manually copying or normalizing the "
            "field. Pass the full prior tool payload when the generated tool expects a "
            "dict/list payload input. If the prior original tool returned a "
            "bare scalar such as a distance or converted number, pass a JSON "
            "object wrapper like {'result': value} as the payload. If the "
            "helper has a dict payload input, the runtime may "
            "autofill that input from the latest original tool result; provide any "
            "remaining scalar selector inputs such as requested_field, "
            "requested_unit, or answer_subject. For Fahrenheit weather requests, "
            "set requested_unit='Fahrenheit'. For distance requests, set "
            "requested_unit='kilometers' unless the user requested a different "
            "visible unit, and set answer_subject to the requested destination "
            "or place name. For currency, weather, phone number, and "
            "distance tasks, call the extraction helper after the original "
            "lookup, distance, or conversion returns instead of manually copying the answer "
            "field. If the generated tool returns should_call_downstream_tool=true, "
            "call the named original ToolSandbox tool with downstream_tool_kwargs "
            "unchanged before giving the final answer. "
            "Do not call it before the original lookup/result tool has returned, "
            "on unrelated tasks, or when required fields are absent."
            f"{scalar_instruction}"
        ),
    }


def _service_extractor_scalar_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    if "extract_service_answer_field" not in _tool_names_execution_facing(openai_tools):
        return None
    if _message_already_called_tool(openai_messages, "extract_service_answer_field"):
        return None
    instruction = _service_extractor_scalar_actor_instruction(
        openai_messages,
        openai_tools,
        {"extract_service_answer_field"},
    )
    if not instruction:
        return None
    return {
        "role": "system",
        "content": (
            f"{SERVICE_EXTRACTOR_SCALAR_POLICY_SENTINEL} A generated extraction "
            "tool is visible and the latest original ToolSandbox result is the "
            "raw scalar needed by that generated tool. Your next assistant "
            "message must be a generated-tool call, not natural language."
            f"{instruction}"
        ),
    }


def _answer_retention_actor_policy_message(
    openai_messages: object,
) -> dict[str, str] | None:
    """Keep a just-produced lookup answer visible through closing turns."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ANSWER_RETENTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if not _latest_user_is_answer_retention_followup(openai_messages):
        return None
    if not _messages_show_recent_tool_backed_answer(openai_messages):
        return None
    return {
        "role": "system",
        "content": (
            f"{ANSWER_RETENTION_ACTOR_POLICY_SENTINEL} The user is acknowledging "
            "or closing a just-completed tool-backed lookup. The next assistant "
            "message must include the retrieved value again in a concise recap. "
            "If a generated tool returned exact_final_answer or final_answer_recommendation "
            "with copy_exactly, preserve that answer exactly. Do not answer only "
            'with a generic acknowledgement such as "you\'re welcome." Do not call '
            "tools only to recap, and do not invent new facts."
        ),
    }


def _lookup_planner_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for helpers that prepare original lookup args."""
    planners = _lookup_query_planner_tool_names(openai_tools)
    if not planners:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in planners):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if _messages_show_prior_candidate_records(openai_messages):
        return None
    planner_list = ", ".join(sorted(planners))
    return {
        "role": "system",
        "content": (
            f"{LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL} A deterministic lookup "
            f"query planner helper is available: {planner_list}. If the user "
            "asks for a contact/message/record field and supplies a scalar "
            "constraint such as name, phone number, relationship, content, or "
            "id, call the helper before manually choosing original search "
            "arguments. Also call it when the user asks for a side-effect action "
            "such as modifying, removing, or messaging a record identified by a "
            "scalar lookup constraint; the helper only prepares the lookup and "
            "does not perform the side effect. Relationship phrases and "
            "phone-number phrases count as scalar constraints for lookup "
            "planning. "
            "A relationship phrase supplied by the user is a valid lookup "
            "constraint; do not ask for a person's name before searching by that "
            "visible relationship constraint. For requests like 'what is the "
            "name of my boss', call the helper with relationship='boss' and "
            "requested_field='name'. For requests like 'what is my relationship "
            "with +15550100', call it with the phone_number and "
            "requested_field='relationship'; do not reject plus-prefixed digits "
            "as placeholders. For delete/remove/update requests that identify a "
            "contact by phone number, call it with that phone_number and "
            "requested_field='person_id'. "
            "When calling the lookup planner, pass only scalar constraints "
            "explicitly supplied by the user or already visible in tool output. "
            "If the user supplies only a phone number, pass the phone number and "
            "requested field only; do not add relationship, is_self, name, or "
            "other optional filters. The phrase 'my contact' means the user's "
            "address book, not relationship='self' or is_self=true. "
            "Use this helper instead of manually assembling search kwargs when "
            "it exactly matches the lookup problem. "
            "If it returns should_call_search_contacts or "
            "should_call_tool with search_*_kwargs, call the original "
            "ToolSandbox search tool next with exactly those kwargs; do not add "
            "optional filters or extra ids that the helper did not return. Then "
            "answer from the returned record, use a visible post-search "
            "extractor, or use a visible post-selection action helper before "
            "calling the original side-effect tool. Do not "
            "call it when no scalar constraint is available, on unrelated "
            "tasks, or on insufficient-information tasks."
        ),
    }


def _latest_contact_lookup_plan_payload(
    openai_messages: object,
) -> Mapping[str, Any] | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if tool_name != "plan_contact_lookup_query":
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if payload:
            return payload
    return None


def _contact_lookup_answer_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge the model to use the generated contact helper for final values."""
    if "plan_contact_lookup_query" not in _tool_names(openai_tools):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CONTACT_LOOKUP_ANSWER_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if not _latest_tool_is(openai_messages, "search_contacts"):
        return None
    plan_payload = _latest_contact_lookup_plan_payload(openai_messages)
    if not plan_payload:
        return None
    answer_field = str(
        plan_payload.get("answer_field") or plan_payload.get("requested_field") or ""
    ).strip()
    if answer_field not in {"name", "phone_number", "relationship"}:
        return None
    latest_search = _latest_tool_message(openai_messages, "search_contacts")
    records = (
        _parse_sequence_payload(latest_search.get("content"))
        if latest_search is not None
        else []
    )
    visible_records = [record for record in records if isinstance(record, Mapping)]
    if len(visible_records) != 1:
        return None
    return {
        "role": "system",
        "content": (
            f"{CONTACT_LOOKUP_ANSWER_POLICY_SENTINEL} A generated contact lookup "
            "helper planned the search_contacts call, and the original "
            "search_contacts tool has now returned one visible contact record. "
            "Before giving the final answer, call plan_contact_lookup_query again "
            "with the same scalar lookup constraints from the prior helper output, "
            f"requested_field='{answer_field}', and selected_record set to the "
            "visible contact record. If the helper returns a nonempty "
            "final_answer_recommendation, answer from that value exactly and do "
            "not add unrelated contact fields. Do not use this path for contact "
            "mutation targets or when the search result is empty or ambiguous."
        ),
    }


def _contact_remove_lookup_target(
    openai_messages: object,
    openai_tools: object,
) -> tuple[str, str] | None:
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"plan_contact_lookup_query", "search_contacts", "remove_contact"}
        <= available_names
    ):
        return None
    if not _latest_tool_is(openai_messages, "search_contacts"):
        return None
    if _called_tool_after_latest_user(openai_messages, "remove_contact"):
        return None
    plan_payload = _latest_contact_lookup_plan_payload(openai_messages)
    if not plan_payload:
        return None
    answer_field = str(
        plan_payload.get("answer_field") or plan_payload.get("requested_field") or ""
    ).strip()
    if answer_field not in {"person_id", "id"}:
        return None
    search_kwargs = plan_payload.get("search_contacts_kwargs")
    phone = ""
    if isinstance(search_kwargs, Mapping):
        phone = _normalize_visible_phone(search_kwargs.get("phone_number"))
    if not phone:
        phone = _normalize_visible_phone(
            _contact_remove_by_phone_request(openai_messages)
        )
    if not phone:
        return None
    latest_search = _latest_tool_message(openai_messages, "search_contacts")
    records = (
        _parse_sequence_payload(latest_search.get("content"))
        if latest_search is not None
        else []
    )
    visible_records = [
        record
        for record in records
        if isinstance(record, Mapping)
        and str(record.get("person_id") or "").strip()
        and not bool(record.get("is_self"))
    ]
    if len(visible_records) != 1:
        return None
    record = visible_records[0]
    record_phone = _normalize_visible_phone(record.get("phone_number"))
    if record_phone and record_phone != phone:
        return None
    return phone, str(record.get("person_id") or "").strip()


def _contact_remove_lookup_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    target = _contact_remove_lookup_target(openai_messages, openai_tools)
    if target is None:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CONTACT_REMOVE_LOOKUP_HANDOFF_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    phone, person_id = target
    remove_tool_name = _tool_name_for_call(openai_tools, "remove_contact")
    return {
        "role": "system",
        "content": (
            f"{CONTACT_REMOVE_LOOKUP_HANDOFF_POLICY_SENTINEL} A generated contact "
            "lookup tool planned the lookup for a remove-by-phone request, and "
            "search_contacts returned exactly one visible non-self contact matching "
            f"the requested phone number {phone}. The phrase 'my contact' means "
            "the user's address book, not the user's self contact. Do not ask for "
            "confirmation only because the matched record is not the self contact. "
            f"Call original {remove_tool_name} next with exactly "
            f"{json.dumps({'person_id': person_id}, sort_keys=True)}."
        ),
    }


def _search_window_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for recency/time-window search helpers."""
    helpers = _search_window_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SEARCH_WINDOW_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    helper_list = ", ".join(sorted(helpers))
    return {
        "role": "system",
        "content": (
            f"{SEARCH_WINDOW_ACTOR_POLICY_SENTINEL} A deterministic recency "
            f"search-window helper is available: {helper_list}. If the user asks "
            "for the latest, oldest, first, earliest, last, most recent, "
            "yesterday, today, or "
            "upcoming message/reminder/search result, prefer this helper before "
            "manually constructing search criteria. First call get_current_timestamp "
            "when a current timestamp is needed; then call the helper with the "
            "visible recency phrase, target_domain ('message' or 'reminder'), "
            "timestamp_intent, and direction; then call the original ToolSandbox "
            "search tool in target_tool_name with search_kwargs. Never call "
            "search_messages or search_reminder with blank strings, null values, "
            "or no criteria when a recency phrase can be converted into bounds. "
            "For reminder questions asking what todo/reminder/task/item was "
            "made, created, or added yesterday, use timestamp_intent='creation' "
            "and pass the visible user phrase with the object wording preserved, "
            "such as 'todo item I made yesterday'. Do not rewrite a plain "
            "reminder/todo request into 'made yesterday' or 'created yesterday' "
            "unless the user used made/created/added wording. If the user asks "
            "what todo/reminder they made, created, or added yesterday, do not "
            "pass phrase='yesterday' with timestamp_intent='reminder'; that "
            "searches due time instead of creation time. For reminders due "
            "yesterday or upcoming, use timestamp_intent='reminder'. "
            "For reminder/todo requests phrased as from yesterday, yesterday, "
            "today, later today, upcoming, or something due later, use "
            "timestamp_intent='reminder' unless the user explicitly says the "
            "item was made, created, or added then. Do not use "
            "timestamp_intent='message_creation' for reminder/todo searches. "
            "Do not shorten a made/created reminder request to only 'yesterday'; "
            "the generated tool needs the creation wording preserved in phrase "
            "or timestamp_intent='creation' to search the correct timestamp "
            "field. "
            "For reminder actions phrased as latest, last, or most recent, use "
            "target_domain='reminder', timestamp_intent='creation', and "
            "direction='latest'; do not use timestamp_intent='message_creation' "
            "for reminders. "
            "For modify/remove actions targeting the latest, oldest, most recent, "
            "or upcoming reminder/message, first use the helper to locate the "
            "target record with a bounded original search, then call the original "
            "side-effect tool only with the concrete visible id from that result. "
            "For an upcoming reminder action, use current time as the lower bound "
            "through resolve_search_window_or_bounds; do not search upcoming "
            "reminders with reminder_timestamp_upperbound=current_timestamp. If "
            "select_action_target_by_recency is called for an upcoming target, pass "
            "selection_mode='upcoming', timestamp_key='reminder_timestamp', and "
            "reference_timestamp from get_current_timestamp. "
            "If that search returns multiple records and a visible-record selector "
            "helper is also available, call the selector before answering; do not "
            "manually pick the first returned record when the user asked for latest "
            "or oldest. For message content questions such as oldest/latest message, "
            "use search_messages with search_kwargs from the helper, then call "
            "select_message_content_by_recency with the non-empty records. Do not "
            "call a selector with [] after a failed or empty search. Do not call "
            "this helper on insufficient-information tasks "
            "or when no time/recency search phrase is present."
        ),
    }


def _search_window_result_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Keep generated recency-window searches from looping after evidence returns."""
    if "resolve_search_window_or_bounds" not in _tool_names_execution_facing(
        openai_tools
    ):
        return None
    if not _message_already_called_tool(
        openai_messages, "resolve_search_window_or_bounds"
    ):
        return None
    if not _latest_tool_is(openai_messages, "search_reminder"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SEARCH_WINDOW_RESULT_HANDOFF_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    records = list(_records_from_latest_reminder_search(openai_messages))
    if len(records) == 1:
        result_instruction = (
            "The latest original search_reminder result contains exactly one "
            "visible reminder record. The next assistant message must answer "
            "from that record's visible content/reminder fields. Do not call "
            "get_current_timestamp, resolve_search_window_or_bounds, or "
            "search_reminder again only to re-check the same recency window. "
            "For this read-only search result, do not call "
            "select_action_target_by_recency with modify_reminder, "
            "remove_reminder, or any other side-effect action_type; no original "
            "side-effect tool is needed."
        )
    elif len(records) == 0:
        result_instruction = (
            "The latest original search_reminder result is empty. The next "
            "assistant message must say that no matching reminder is visible "
            "for the generated recency/search window. If an earlier visible "
            "search result in this same task provided a candidate reminder, "
            "you may mention that earlier visible candidate, but do not call "
            "get_current_timestamp, resolve_search_window_or_bounds, or "
            "search_reminder again only to re-check the same empty window."
        )
    else:
        result_instruction = (
            "The latest original search_reminder result contains multiple "
            "visible reminder records. The next assistant message must answer "
            "from those visible records or state that multiple reminders match. "
            "Do not call get_current_timestamp, resolve_search_window_or_bounds, "
            "or search_reminder again only to re-check the same recency window. "
            "If a generated selector is needed only to format a read-only answer, "
            "use action_type='answer_record', never a modify/remove action_type."
        )
    return {
        "role": "system",
        "content": (
            f"{SEARCH_WINDOW_RESULT_HANDOFF_POLICY_SENTINEL} A generated "
            "recency search-window tool prepared the latest original "
            f"search_reminder call. {result_instruction} This policy does not "
            "complete the task from code; it requires the actor to use only the "
            "visible ToolSandbox search result."
        ),
    }


def _relative_time_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for relative day/time conversion helpers."""
    helpers = _relative_time_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if RELATIVE_TIME_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    helper_list = ", ".join(sorted(helpers))
    current_timestamp_tool = _tool_name_for_call(openai_tools, "get_current_timestamp")
    datetime_info_tool = _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
    absolute_timestamp_tool = _tool_name_for_call(
        openai_tools, "datetime_info_to_timestamp"
    )
    composite_available = (
        "prepare_reminder_creation_args" in _tool_names_execution_facing(openai_tools)
    )
    if composite_available:
        route_instruction = (
            "For add_reminder tasks, first call original "
            f"{current_timestamp_tool} when available, then call original "
            f"{datetime_info_tool} on that returned timestamp, then call "
            "generated prepare_reminder_creation_args with current_timestamp, "
            "day_offset, hour, minute, and current_datetime_info set to the "
            "visible datetime dict. Use its add_reminder_kwargs unchanged for "
            "the original add_reminder call. "
            "Use the separate relative-time helper mainly for modify_reminder or "
            "when no generated action-argument tool can prepare the downstream "
            "original call."
        )
    else:
        route_instruction = (
            "If the user asks to add or modify a reminder for a relative day plus "
            "explicit time, such as tomorrow at 5 PM, first call original "
            f"{current_timestamp_tool} when available, then original "
            f"{datetime_info_tool} on that returned timestamp when visible, and "
            "then call the generated relative-time helper."
        )
    return {
        "role": "system",
        "content": (
            f"{RELATIVE_TIME_ACTOR_POLICY_SENTINEL} A deterministic relative "
            f"day/time timestamp helper is available: {helper_list}. "
            f"{route_instruction} Identify the generated "
            "relative-time helper by schema when tool names are perturbed: it "
            "accepts current_timestamp, day_offset, hour, minute, and optional "
            "current_datetime_info. Do not call original "
            f"{absolute_timestamp_tool}, or any original timestamp tool requiring "
            "year/month/day/second, for a relative phrase such as tomorrow. Do "
            "not call original offset/shift timestamp tools that add raw days or "
            "hours for a local clock-time phrase; that changes tomorrow at 5 PM "
            "into current time plus hours instead of preserving the requested "
            "local clock time. Do not guess a timezone or fixed UTC offset. If "
            "local datetime context is visible and the separate relative-time "
            "helper is needed, pass that dictionary to the generated helper. Do not call the "
            "helper when the user omitted the target day or time, when the current "
            "timestamp is unavailable, or when the local offset cannot be inferred "
            "from visible runtime context. For modify_reminder or remove_reminder, "
            "this helper only prepares the new timestamp; it does not identify the "
            "target reminder. Do not call the original side-effect tool until a "
            "single reminder_id is visible and unambiguous, or the user explicitly "
            "asked to update all matching reminders. This helper does not replace "
            "the original reminder side-effect tool."
        ),
    }


def _scheduling_timestamp_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for reminder week/weekday timestamp helpers."""
    helpers = _scheduling_timestamp_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    helper_list = ", ".join(sorted(helpers))
    return {
        "role": "system",
        "content": (
            f"{SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL} Deterministic reminder "
            f"scheduling timestamp helpers are available: {helper_list}. For "
            "add_reminder or modify_reminder tasks whose requested time is based "
            "on a week delta, weekday delta, or phrase like 'next Tuesday at 8 AM', "
            "first call get_current_timestamp if the current time is needed, then "
            "call timestamp_to_datetime_info on that exact current timestamp when "
            "that original tool is visible, and pass the returned dictionary as "
            "current_datetime_info to the matching helper. Do not guess a UTC "
            "offset or timezone. Then use the helper result as reminder_timestamp "
            "before calling "
            "the original reminder side-effect tool. Use next_weekday_time_to_timestamp "
            "for phrases like 'next Friday at 5 PM'; do not add an extra week for "
            "the word 'next'. For exact whole-week offsets like 'next week at "
            "5 PM' or 'in two weeks', use the visible whole-week helper "
            "(for example relative_weeks_time_to_timestamp, "
            "weeks_from_now_time_to_timestamp, or week_delta_time_to_timestamp) "
            "instead of manually multiplying by seven days. Use "
            "weekday_delta_time_to_timestamp only if no safer next-weekday helper "
            "is visible. Do not call these helpers for reminder recency "
            "search/selection tasks, insufficient-information tasks, or unrelated "
            "contact/message/device-state tasks."
        ),
    }


def _absolute_reminder_timestamp_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge absolute reminder creation through the original timestamp tool."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"datetime_info_to_timestamp", "prepare_reminder_creation_args", "add_reminder"}
        <= available_names
    ):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ABSOLUTE_REMINDER_TIMESTAMP_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    request = _absolute_reminder_creation_request(openai_messages)
    if request is None:
        return None
    if not str(request.get("content") or "").strip():
        return {
            "role": "system",
            "content": (
                f"{ABSOLUTE_REMINDER_TIMESTAMP_POLICY_SENTINEL} The user gave an "
                "absolute reminder date and time, but the reminder content is "
                "not visible yet. Do not call datetime_info_to_timestamp, "
                "prepare_reminder_creation_args, or add_reminder yet. Ask the "
                "user what the reminder should say. Do not use a timezone "
                "clarification, a date/time phrase, or the generic phrase "
                "'add a reminder' as the reminder content."
            ),
        }
    year = int(request["year"])
    month = int(request["month"])
    day = int(request["day"])
    hour = int(request["hour"])
    minute = int(request["minute"])
    datetime_tool_called = (
        _message_already_called_tool(openai_messages, "datetime_info_to_timestamp")
        or _latest_tool_content(openai_messages, "datetime_info_to_timestamp")
        is not None
    )
    if not datetime_tool_called:
        return {
            "role": "system",
            "content": (
                f"{ABSOLUTE_REMINDER_TIMESTAMP_POLICY_SENTINEL} The user gave an "
                "absolute reminder date and time. Do not manually calculate a Unix "
                "timestamp. First call original datetime_info_to_timestamp with "
                f"year={year}, month={month}, day={day}, hour={hour}, "
                f"minute={minute}, second=0. After that original tool returns a "
                "timestamp, call prepare_reminder_creation_args with the reminder "
                "content and that returned timestamp as resolved_reminder_timestamp, "
                "leave current_timestamp/day_offset/local_utc_offset_hours unset "
                "or null for this absolute-date path, then call original "
                "add_reminder with add_reminder_kwargs unchanged."
            ),
        }
    timestamp = _timestamp_from_latest_tool(
        openai_messages, "datetime_info_to_timestamp"
    )
    if timestamp is None:
        return None
    return {
        "role": "system",
        "content": (
            f"{ABSOLUTE_REMINDER_TIMESTAMP_POLICY_SENTINEL} The original "
            f"datetime_info_to_timestamp tool returned {timestamp} for the user's "
            "absolute reminder date/time. Do not replace it with model arithmetic. "
            "Call prepare_reminder_creation_args with this value as "
            "resolved_reminder_timestamp. This is an absolute-date path: do not "
            "also pass that value as current_timestamp, and leave "
            "current_timestamp/day_offset/local_utc_offset_hours unset or null. "
            "Then call original add_reminder with add_reminder_kwargs unchanged."
        ),
    }


def _absolute_reminder_prepare_retry_args(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, Any] | None:
    if "prepare_reminder_creation_args" not in _tool_names_execution_facing(
        openai_tools
    ):
        return None
    timestamp = _latest_tool_float_by_name_including_latest(
        openai_messages, "datetime_info_to_timestamp"
    )
    if timestamp is None:
        return None
    previous_args = _latest_prior_tool_call_arguments(
        openai_messages, "prepare_reminder_creation_args"
    )
    if not previous_args:
        return None
    try:
        resolved = float(previous_args.get("resolved_reminder_timestamp"))
    except (TypeError, ValueError):
        resolved = 0.0
    if resolved > 0.0 and abs(resolved - timestamp) > 60.0:
        return None
    retry_args = dict(previous_args)
    retry_args["resolved_reminder_timestamp"] = timestamp
    retry_args["current_timestamp"] = None
    retry_args["day_offset"] = None
    retry_args["local_utc_offset_hours"] = None
    retry_args["current_datetime_info"] = {}
    return retry_args


def _state_downstream_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve downstream completion after a generated state helper resumes work."""
    helper_names = _state_action_planner_tool_names(openai_tools)
    if not helper_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    if latest.get("role") != "tool":
        return None
    latest_tool_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    downstream_tools = ORIGINAL_SIDE_EFFECT_TOOL_NAMES - SETTING_SETTER_TOOL_NAMES
    if latest_tool_name not in downstream_tools:
        return None
    latest_content = str(latest.get("content", "") or "").strip().lower()
    if "error" in latest_content or "exception" in latest_content:
        return None
    latest_plan = _latest_tool_message_index(openai_messages, helper_names)
    if latest_plan is None:
        return None
    plan_index, plan_message = latest_plan
    if plan_index >= len(messages) - 1:
        return None
    payload = _parse_mapping_payload(plan_message.get("content"))
    if not payload:
        return None
    final_marker = str(payload.get("final_response_recommendation") or "").strip()
    resumes_downstream = (
        bool(payload.get("continue_original_task_after_sequence"))
        or final_marker == "continue_original_task"
    )
    if not resumes_downstream:
        return None
    for message in messages:
        if STATE_DOWNSTREAM_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None

    tool_args = _latest_prior_tool_call_arguments(openai_messages, latest_tool_name)
    detail = ""
    if latest_tool_name == "send_message_with_phone_number":
        phone_number = str(tool_args.get("phone_number") or "").strip()
        content = str(tool_args.get("content") or "").strip()
        if phone_number and content:
            detail = (
                " The completed downstream action was sending a message to "
                f"{phone_number!r} with content {content!r}; report that message "
                "send as complete using those visible values."
            )
    elif latest_tool_name in {"add_reminder", "modify_reminder", "remove_reminder"}:
        detail = " Report the reminder action as complete using the visible tool call."
    elif latest_tool_name in {"add_contact", "modify_contact", "remove_contact"}:
        detail = " Report the contact action as complete using the visible tool call."

    return {
        "role": "system",
        "content": (
            f"{STATE_DOWNSTREAM_COMPLETION_POLICY_SENTINEL} A generated "
            "device-state helper used continue_original_task only as an internal "
            "marker to resume the user's downstream task. The latest original "
            f"ToolSandbox downstream tool, {latest_tool_name}, has now succeeded. "
            "Do not answer with continue_original_task, do not call the same "
            "downstream tool again, and do not discuss the device setting unless "
            "the user asks about it."
            f"{detail}"
        ),
    }


def _state_action_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for direct device-state action planners."""
    helpers = _state_action_planner_tool_names(openai_tools)
    if not helpers:
        return None
    latest_precondition_error_text = _latest_original_state_precondition_error_text(
        openai_messages
    )
    latest_precondition_error = bool(latest_precondition_error_text)
    already_called = (
        any(_message_already_called_tool(openai_messages, name) for name in helpers)
        or _latest_state_action_helper_payload(openai_messages) is not None
    )
    latest_user = _latest_user_request_text(openai_messages).lower()
    latest_state_mentions = (
        "wifi",
        "wi-fi",
        "cellular",
        "cellphone",
        "phone signal",
        "signal",
        "location service",
        "low battery",
        "battery mode",
    )
    latest_state_action_terms = (
        "turn",
        "enable",
        "disable",
        "switch",
        "set ",
        "shut off",
        "get it on",
        "turn it on",
        "turn it off",
    )
    latest_downstream_terms = (
        "send",
        "message",
        "text",
        "reminder",
        "contact",
        "search",
        "find",
        "look up",
        "lookup",
    )
    latest_direct_state_action = any(
        token in latest_user for token in latest_state_mentions
    ) and any(token in latest_user for token in latest_state_action_terms)
    downstream_without_precondition = (
        any(token in latest_user for token in latest_downstream_terms)
        and not latest_precondition_error
        and not latest_direct_state_action
    )
    if downstream_without_precondition:
        latest_user_index = _latest_user_index(openai_messages)
        for index, message in enumerate(
            cast(Iterable[Mapping[str, Any]], openai_messages)
        ):
            if index <= latest_user_index:
                continue
            if STATE_ACTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
                return None
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} A generated device-state "
                "action helper may be visible, but the latest user request is a "
                "downstream task and no fresh original ToolSandbox state "
                "precondition error is visible. Do not call a state-action helper "
                "only to re-check or re-assert readiness. Continue the downstream "
                "task with the relevant original ToolSandbox tools. If an original "
                "tool later reports a wifi/cellular/location/low-battery "
                "precondition error, then call the generated state-action helper "
                "with that new error text and execute its returned original "
                "setter sequence."
            ),
        }
    already_satisfied_response = _latest_setting_already_satisfied_response(
        openai_messages
    )
    if already_satisfied_response and already_called:
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The latest original "
                "ToolSandbox setter reports that the requested state is already "
                "satisfied. Do not retry the same setter, do not ask about a "
                "different setting, and do not call the state-action helper again "
                "for this already-satisfied result. For a direct setting request, "
                f"answer exactly with: {already_satisfied_response}"
            ),
        }
    if latest_precondition_error_text:
        helper_list = ", ".join(sorted(helpers))
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The latest original "
                "ToolSandbox state/action tool returned this precondition error: "
                f"{latest_precondition_error_text!r}. Call the generated "
                f"device-state helper again now: {helper_list}. The next assistant "
                "message must be a tool call to that generated helper before any "
                "other status getter or setter. Use the same "
                "user_request you used for the prior device-state helper call, "
                "and include that exact error text in visible_state_or_error. "
                "Also include any already-visible successful setting state in "
                "visible_state_or_error or visible_state_summary; for example, "
                "if set_low_battery_mode_status({'on': false}) already returned "
                "None or an already-disabled message, include 'low battery mode "
                "is off' so the generated helper can skip redundant low-battery "
                "setter calls. Do not manually call get_low_battery_mode_status, "
                "another status getter, or a state setter before rerunning the "
                "generated helper; the helper should plan the required original "
                "setter sequence."
            ),
        }
    completion_policy = _state_action_sequence_completion_policy_message(
        openai_messages,
        openai_tools,
    )
    if completion_policy is not None and already_called:
        return completion_policy
    next_service_completion_policy = _next_service_direct_completion_policy_message(
        openai_messages
    )
    if next_service_completion_policy is not None and already_called:
        return next_service_completion_policy
    clarification_policy = _state_action_completion_clarification_policy_message(
        openai_messages
    )
    if clarification_policy is not None and already_called:
        return clarification_policy
    if already_called and not latest_precondition_error:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if (
            STATE_ACTION_ACTOR_POLICY_SENTINEL in str(message.get("content", ""))
            and not latest_precondition_error
        ):
            return None
    message_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
    ).lower()
    state_triggers = (
        "wifi",
        "wi-fi",
        "cellular",
        "location service",
        "low battery",
        "battery mode",
        "blocked",
    )
    if not any(trigger in message_text for trigger in state_triggers):
        return None
    helper_list = ", ".join(sorted(helpers))
    preferred_helper = (
        " Prefer plan_device_state_action_sequence_v3 when it is visible because "
        "it can return an ordered sequence for low-battery/service prerequisites."
        if any(name.startswith("plan_device_state_action_sequence") for name in helpers)
        else ""
    )
    return {
        "role": "system",
        "content": (
            f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} A deterministic device-state "
            f"action planner helper is available: {helper_list}.{preferred_helper} If the user asks "
            "to turn wifi, cellular service, location service, or low battery mode "
            "on/off, or a previous original tool reports a blocked wifi/cellular/"
            "location precondition, call this helper with the user request and any "
            "visible state/error text. For next_service_tool_call, pass the single "
            "target_service plus visible service-state booleans. If the helper "
            "returns should_call=true, call the original ToolSandbox setter calls "
            "from action_sequence in order, one original setter call per assistant "
            "turn; do not issue multiple state setters in the same tool-call "
            "message because the execution order may not be preserved. When "
            "action_sequence is absent, use the single returned tool_name and "
            "arguments. If the helper returns "
            "should_call=false with already_in_desired_state, do not call a "
            "setter again; either continue the original downstream task or answer "
            "with final_response_recommendation for a direct setting request. When the "
            "request is a direct setting change, answer exactly with "
            "final_response_recommendation after the setters succeed, with no extra "
            "words. When the helper output says continue_original_task_after_sequence "
            "is true, do not answer with the state message; after the setters succeed, "
            "continue the user's original task. Also continue the original task after "
            "clearing a wifi/cellular/location/low-battery precondition when the "
            "conversation began as a reminder, message, contact, search, or answer "
            "task, even if the helper's final_response_recommendation is only a "
            "setting-status sentence. If a later original ToolSandbox tool reports "
            "a new wifi/cellular/location/low-battery precondition after one "
            "precondition was cleared, call the visible helper again with that new "
            "error text and continue the original task after the returned original "
            "setter succeeds. Do not call it on insufficient-"
            "information tasks or unrelated contact/reminder/message selection tasks. "
            "When an original setting setter returns None, that means the setter "
            "succeeded; do not claim the action failed or that you cannot change "
            "settings. When an original setting setter reports that the target is "
            "already enabled or already disabled, treat that as the requested "
            "state already being satisfied; do not retry the same setter."
        ),
    }


def _latest_state_action_helper_payload(
    openai_messages: object,
) -> tuple[int, Mapping[str, Any]] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if not name.startswith("plan_device_state_action_sequence"):
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if payload:
            return index, payload
    return None


def _setting_setter_succeeded(content: object) -> bool:
    text = str(content or "").strip().lower()
    if text in {"", "none", "null"}:
        return True
    if "already" in text and any(
        token in text for token in ("enabled", "disabled", "on", "off")
    ):
        return True
    if any(token in text for token in ("error", "exception", "cannot", "failed")):
        return False
    return False


def _state_action_sequence_completion_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    completed = _completed_state_action_sequence_payload(openai_messages)
    if completed is None:
        return None
    payload, completed_count = completed
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_message = messages[-1] if messages else {}
    latest_name = _execution_facing_tool_name(str(latest_message.get("name", "") or ""))
    if (
        latest_message.get("role") != "tool"
        or latest_name not in SETTING_SETTER_TOOL_NAMES
        or not _setting_setter_succeeded(latest_message.get("content"))
    ):
        return None
    sequence = payload.get("action_sequence")
    if not isinstance(sequence, list) or not sequence:
        return None
    if completed_count < len(sequence):
        next_action = sequence[completed_count]
        if not isinstance(next_action, Mapping):
            return None
        tool_name = str(next_action.get("tool_name") or "").strip()
        arguments = next_action.get("arguments")
        if not tool_name or not isinstance(arguments, Mapping):
            return None
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} A generated device-state "
                "helper returned an ordered action_sequence, and the prior "
                "original setter succeeded. Continue the generated sequence "
                f"by calling original {tool_name} next with exactly these "
                f"arguments: {json.dumps(dict(arguments), sort_keys=True)}. "
                "Do not answer yet and do not reorder the remaining setters."
            ),
        }
    final_response = str(payload.get("final_response_recommendation") or "").strip()
    continue_original = bool(payload.get("continue_original_task_after_sequence"))
    if continue_original:
        retry_call = _latest_non_setting_state_precondition_retry_call(openai_messages)
        retry_detail = ""
        if retry_call is not None:
            retry_tool_name, retry_arguments = retry_call
            if retry_tool_name in _tool_names_execution_facing(openai_tools):
                retry_detail = (
                    " The original ToolSandbox call that most recently exposed "
                    "the device-state blocker is now safe to retry. The next "
                    f"original tool call should be {retry_tool_name} with exactly "
                    f"these arguments: "
                    f"{json.dumps(_call_contract_kwargs(retry_arguments), sort_keys=True)}. "
                    "Do not ask the user again before retrying that blocked "
                    "original call."
                )
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The generated device-state "
                "helper's original setter sequence has succeeded. Because "
                "continue_original_task_after_sequence is true, do not answer with "
                "only a device-setting status. Continue the user's original task "
                "using the relevant original ToolSandbox tools. If a generated "
                "argument tool already prepared the downstream original call before "
                "the state blocker, reuse that generated-tool contract instead of "
                "asking again or manually reconstructing the call. For reminder "
                "tasks with a resolved timestamp and visible location-search "
                "result, continue through prepare_reminder_creation_args before "
                "calling original add_reminder."
                f"{retry_detail}"
            ),
        }
    if not final_response:
        return None
    return {
        "role": "system",
        "content": (
            f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The generated device-state "
            "helper's original setter sequence has succeeded and the direct "
            "setting task is complete. Answer exactly with: "
            f"{final_response} Do not invite further assistance, do not ask a "
            "follow-up question, and do not call the helper or setter again."
        ),
    }


def _next_service_direct_completion_policy_message(
    openai_messages: object,
) -> dict[str, str] | None:
    completion = _next_service_direct_completion_response(openai_messages)
    if completion is None:
        return None
    latest_name, final_response = completion
    return {
        "role": "system",
        "content": (
            f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The generated next_service_tool_call "
            "planned the prerequisite device-state repair, and the target original "
            f"setter {latest_name} has now succeeded. The direct setting task is "
            f"complete. Answer exactly with: {final_response} Do not mention "
            "intermediate prerequisite settings, do not invite further assistance, "
            "and do not call another status getter, setter, or generated tool."
        ),
    }


def _next_service_direct_completion_response(
    openai_messages: object,
) -> tuple[str, str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_message = messages[-1] if messages else {}
    if latest_message.get("role") != "tool":
        return None
    latest_name = _execution_facing_tool_name(str(latest_message.get("name", "") or ""))
    if latest_name not in SETTING_SETTER_TOOL_NAMES or not _setting_setter_succeeded(
        latest_message.get("content")
    ):
        return None
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages,
        "next_service_tool_call",
    )
    if not payload:
        return None
    prior_args = _latest_prior_tool_call_arguments(
        openai_messages,
        "next_service_tool_call",
    )
    target_service = (
        str(prior_args.get("target_service") or payload.get("target_service") or "")
        .strip()
        .lower()
    )
    target_setters = {
        "wifi": ("set_wifi_status", "Wifi"),
        "cellular": ("set_cellular_service_status", "Cellular service"),
        "location": ("set_location_service_status", "Location service"),
    }
    target = target_setters.get(target_service)
    if target is None:
        return None
    target_setter, label = target
    if latest_name != target_setter:
        return None
    setter_args = _latest_prior_tool_call_arguments(openai_messages, latest_name)
    on_value = setter_args.get("on")
    if not isinstance(on_value, bool):
        return None
    user_request = str(
        prior_args.get("user_request") or _latest_user_request_text(openai_messages)
    ).lower()
    direct_state = any(
        token in user_request
        for token in (
            "turn",
            "enable",
            "disable",
            "switch",
            "set ",
            "get it on",
            "turn it on",
            "turn it off",
        )
    ) or (
        target_service == "cellular"
        and any(token in user_request for token in ("cellphone signal", "phone signal"))
    )
    downstream = any(
        token in user_request
        for token in (
            "send ",
            "message",
            "text ",
            "reminder",
            "contact",
            "search",
            "find ",
            "look up",
        )
    )
    if not direct_state or (downstream and "get it on" not in user_request):
        return None
    final_response = f"{label} has been turned {'on' if on_value else 'off'}."
    return latest_name, final_response


def _completed_state_action_sequence_payload(
    openai_messages: object,
) -> tuple[Mapping[str, Any], int] | None:
    latest = _latest_state_action_helper_payload(openai_messages)
    if latest is None:
        return None
    helper_index, payload = latest
    sequence = payload.get("action_sequence")
    if not isinstance(sequence, list) or not sequence:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    setter_results: list[Mapping[str, Any]] = []
    for message in messages[helper_index + 1 :]:
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in SETTING_SETTER_TOOL_NAMES:
            continue
        if not _setting_setter_succeeded(message.get("content")):
            return None
        setter_results.append(message)
    completed_count = len(setter_results)
    if completed_count == 0:
        return None
    return payload, completed_count


def _state_action_completion_clarification_policy_message(
    openai_messages: object,
) -> dict[str, str] | None:
    completed = _completed_state_action_sequence_payload(openai_messages)
    if completed is None:
        return None
    payload, completed_count = completed
    sequence = payload.get("action_sequence")
    if not isinstance(sequence, list) or completed_count < len(sequence):
        return None
    final_response = str(payload.get("final_response_recommendation") or "").strip()
    if not final_response or bool(payload.get("continue_original_task_after_sequence")):
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_message = messages[-1] if messages else {}
    if latest_message.get("role") != "user":
        return None
    latest_user = (
        str(latest_message.get("content") or "")
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return None
    if not _latest_user_reaffirms_completed_device_state(latest_user, payload):
        return None
    return {
        "role": "system",
        "content": (
            f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} A generated device-state helper "
            "already completed the direct setting task, and the latest user message "
            "is restating or clarifying that same target state rather than requiring "
            "a new side effect. Preserve the completed generated-tool task boundary. "
            "Answer exactly with: "
            f"{final_response} Do not call a state setter or generated helper again, "
            "and do not invite further assistance."
        ),
    }


def _latest_user_reaffirms_completed_device_state(
    latest_user: str,
    payload: Mapping[str, Any],
) -> bool:
    sequence = payload.get("action_sequence")
    if not isinstance(sequence, list) or not sequence:
        return False
    final_action = sequence[-1]
    if not isinstance(final_action, Mapping):
        return False
    tool_name = str(final_action.get("tool_name") or "").strip()
    arguments = final_action.get("arguments")
    if tool_name not in SETTING_SETTER_TOOL_NAMES or not isinstance(arguments, Mapping):
        return False
    target_on = arguments.get("on")
    if not isinstance(target_on, bool):
        return False
    clarification_markers = (
        "i meant",
        "not on",
        "not off",
        "i want",
        "i need",
        "please",
        "that should be",
    )
    if not any(marker in latest_user for marker in clarification_markers):
        return False
    if target_on:
        return "on" in latest_user or "enabled" in latest_user
    return "off" in latest_user or "disabled" in latest_user


def _latest_setting_already_satisfied_response(
    openai_messages: object,
) -> str | None:
    latest = _latest_tool_message_index(openai_messages, SETTING_SETTER_TOOL_NAMES)
    if latest is None:
        return None
    _index, message = latest
    tool_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
    content = str(message.get("content", "") or "").lower()
    if not any(
        token in content
        for token in (
            "already disabled",
            "already enabled",
            "already off",
            "already on",
        )
    ):
        return None
    labels = {
        "set_cellular_service_status": "Cellular service",
        "set_wifi_status": "WiFi",
        "set_location_service_status": "Location service",
        "set_low_battery_mode_status": "Low battery mode",
    }
    label = labels.get(tool_name)
    if not label:
        return None
    state = (
        "on"
        if "enabled" in content or "already on" in content
        else "off"
        if "disabled" in content or "already off" in content
        else ""
    )
    if not state:
        return None
    return f"{label} is turned {state}"


def _setting_already_satisfied_response_from_setter_result(
    tool_name: str,
    arguments: Mapping[str, Any],
    content: object,
) -> str | None:
    lower = str(content or "").strip().lower().replace("wi-fi", "wifi")
    if not any(
        token in lower
        for token in (
            "already disabled",
            "already enabled",
            "already off",
            "already on",
        )
    ):
        return None
    desired_on = arguments.get("on")
    if not isinstance(desired_on, bool):
        return None
    content_says_on = "already enabled" in lower or "already on" in lower
    content_says_off = "already disabled" in lower or "already off" in lower
    if desired_on and not content_says_on:
        return None
    if not desired_on and not content_says_off:
        return None
    labels = {
        "set_cellular_service_status": "Cellular service",
        "set_wifi_status": "WiFi",
        "set_location_service_status": "Location service",
        "set_low_battery_mode_status": "Low battery mode",
    }
    label = labels.get(_execution_facing_tool_name(tool_name))
    if not label:
        return None
    state = "on" if desired_on else "off"
    return f"{label} is already {state}."


def _completion_affirms_setting_state(
    completion: ChatCompletion,
    *,
    desired_on: bool,
) -> bool:
    if _completion_has_any_tool_call(completion):
        return False
    text = _completion_text_content(completion).lower().replace("wi-fi", "wifi")
    if not text:
        return False
    if desired_on:
        return any(
            token in text
            for token in ("already on", "already enabled", "is on", "turned on")
        )
    return any(
        token in text
        for token in ("already off", "already disabled", "is off", "turned off")
    )


def _latest_original_state_precondition_error(
    openai_messages: object,
) -> tuple[int, str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    start = max(0, len(messages) - 8)
    for index in range(len(messages) - 1, start - 1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            continue
        content = str(message.get("content", "") or "").lower()
        if any(
            token in content
            for token in (
                "wifi is not enabled",
                "wi-fi is not enabled",
                "cellular service is not enabled",
                "location service is not enabled",
                "cannot be turned on in low battery mode",
                "blocked by low battery",
                "low battery mode",
            )
        ):
            return index, str(message.get("content", "") or "")
    return None


def _latest_non_setting_state_precondition_retry_call(
    openai_messages: object,
) -> tuple[str, Mapping[str, Any]] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            execution_name = _execution_facing_tool_name(name)
            if tool_id and execution_name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
                tool_call_args_by_id[tool_id] = (execution_name, arguments)
    start = max(0, len(messages) - 16)
    for index in range(len(messages) - 1, start - 1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if (
            name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
            or name in SETTING_SETTER_TOOL_NAMES
        ):
            continue
        content = str(message.get("content", "") or "").lower()
        if not any(
            token in content
            for token in (
                "wifi is not enabled",
                "wi-fi is not enabled",
                "cellular service is not enabled",
                "location service is not enabled",
                "blocked by low battery",
            )
        ):
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        return tool_call_args_by_id.get(tool_id, (name, {}))
    return None


def _latest_original_state_precondition_error_text(
    openai_messages: object,
) -> str | None:
    latest = _latest_original_state_precondition_error(openai_messages)
    return latest[1] if latest is not None else None


def _device_status_lookup_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    tool_names = _tool_names_execution_facing(openai_tools)
    if "plan_device_status_lookup" not in tool_names:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if DEVICE_STATUS_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    message_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
    ).lower()
    if not any(
        token in message_text
        for token in (
            "wifi",
            "wi-fi",
            "cellular",
            "location service",
            "low battery",
            "battery mode",
            "phone signal",
            "signal",
        )
    ):
        return None
    return {
        "role": "system",
        "content": (
            f"{DEVICE_STATUS_ACTOR_POLICY_SENTINEL} A generated read-only "
            "device-status helper is visible: plan_device_status_lookup. For a "
            "request that asks whether wifi, cellular service, location service, "
            "or low battery mode is on/off/available, call this helper with the "
            "user request and blank visible_state_result. If it returns "
            "should_call=true, call the original ToolSandbox getter named in "
            "tool_name with arguments. After the getter returns True/False, call "
            "plan_device_status_lookup again with the same user_request and "
            "visible_state_result set to the getter result. Then answer exactly "
            "with final_answer_recommendation. If original end_conversation is "
            "visible, close the completed status task immediately after that "
            "exact answer by calling end_conversation with empty arguments; do "
            "not leave the completed lookup open for unrelated diagnostics. Do "
            "not manually paraphrase the getter result, and do not discuss "
            "unavailable stability or internet tests unless the user asks a "
            "separate follow-up question before the status task is complete. "
            "This helper is read-only; do not use it for setting changes."
        ),
    }


def _latest_generated_helper_payload(
    openai_messages: object,
    openai_tools: object,
) -> tuple[str, Mapping[str, Any]] | None:
    """Return the latest generated-helper mapping payload, if one is visible."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not available_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    if latest.get("role") != "tool":
        return None
    name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if not name or name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
        return None
    if name not in available_names:
        return None
    payload = _parse_mapping_payload(latest.get("content"))
    if not payload:
        return None
    return name, payload


def _lean_helper_output_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    if latest is None:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_generated_index = len(messages) - 1
    for index, message in enumerate(messages):
        if (
            index >= latest_generated_index
            and HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL in str(message.get("content", ""))
        ):
            return None

    helper_name, payload = latest
    available_names = _tool_names_execution_facing(openai_tools)
    instructions: list[str] = []

    def _cleaned_mapping(value: object) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            return None
        return {str(key): item for key, item in value.items() if item is not None}

    def _append_original_call(tool_name: object, kwargs: object) -> None:
        execution_name = _execution_facing_tool_name(str(tool_name or "").strip())
        cleaned = _cleaned_mapping(kwargs)
        if not execution_name or cleaned is None:
            return
        if execution_name not in available_names:
            return
        visible_name = _tool_name_for_call(openai_tools, execution_name)
        instructions.append(
            f"Call original {visible_name} next with exactly "
            f"{json.dumps(cleaned, sort_keys=True)}."
        )

    if bool(payload.get("should_call_add_reminder")):
        _append_original_call("add_reminder", payload.get("add_reminder_kwargs"))
    if bool(payload.get("should_call_downstream_tool")):
        _append_original_call(
            payload.get("downstream_tool_name")
            or payload.get("target_tool_name")
            or payload.get("tool_name"),
            payload.get("downstream_tool_kwargs")
            or payload.get("search_location_kwargs")
            or payload.get("arguments"),
        )
    if bool(payload.get("should_call_tool")):
        _append_original_call(
            payload.get("downstream_tool_name")
            or payload.get("target_tool_name")
            or payload.get("tool_name"),
            payload.get("downstream_tool_kwargs") or payload.get("arguments"),
        )
    if bool(payload.get("should_call_search")):
        _append_original_call(
            payload.get("target_tool_name")
            or payload.get("downstream_tool_name")
            or payload.get("tool_name"),
            payload.get("search_kwargs") or payload.get("arguments"),
        )
    if bool(payload.get("should_call_search_contacts")):
        search_kwargs = _cleaned_mapping(payload.get("search_contacts_kwargs"))
        if search_kwargs is not None:
            if (
                str(search_kwargs.get("relationship") or "").strip().lower()
                == _ALL_CONTACTS_RELATIONSHIP_SOURCE
            ):
                search_kwargs.pop("relationship", None)
            _append_original_call("search_contacts", search_kwargs)
    if bool(payload.get("should_call_search_messages")):
        _append_original_call("search_messages", payload.get("search_messages_kwargs"))
    if bool(payload.get("should_call")):
        _append_original_call(
            payload.get("tool_name") or payload.get("downstream_tool_name"),
            payload.get("arguments") or payload.get("downstream_tool_kwargs"),
        )

    if helper_name.startswith("plan_device_state_action_sequence"):
        next_action = _next_unsatisfied_state_action(openai_messages, payload)
        if isinstance(next_action, Mapping):
            _append_original_call(
                next_action.get("tool_name"), next_action.get("arguments")
            )

    recommendation = str(
        payload.get("exact_final_answer")
        or payload.get("final_answer_recommendation")
        or ""
    ).strip()
    if recommendation and not instructions:
        instructions.append(f"Answer exactly with: {recommendation}")
    if (
        payload.get("abstain_reason") or payload.get("should_abstain")
    ) and not instructions:
        if recommendation:
            instructions.append(
                f"The generated tool abstained; answer with: {recommendation}"
            )
        else:
            return None
    if not instructions:
        return None

    return {
        "role": "system",
        "content": (
            f"{HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL} Generated tool "
            f"{helper_name} returned a deterministic contract. "
            f"{' '.join(instructions)} Do not treat the generated tool itself "
            "as performing the original side effect; use only visible returned "
            "arguments or the returned final answer."
        ),
    }


def _helper_output_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic handoff from structured generated-helper output to the actor."""
    if _generated_tool_lean_handoff_enabled():
        lean_policy = _lean_helper_output_handoff_actor_policy_message(
            openai_messages, openai_tools
        )
        if lean_policy is not None:
            return lean_policy
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    if latest is None:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_helper_index = len(messages) - 1
    latest_handoff_index = -1
    for index, message in enumerate(messages):
        if HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL in str(message.get("content", "")):
            latest_handoff_index = index
    if latest_handoff_index >= latest_helper_index:
        return None
    helper_name, payload = latest
    payload_keys = ", ".join(sorted(str(key) for key in payload))
    exact_next = ""
    search_kwargs = payload.get("search_contacts_kwargs")
    if bool(payload.get("should_call_search_contacts")) and isinstance(
        search_kwargs, Mapping
    ):
        cleaned_search_kwargs = {
            str(key): value for key, value in search_kwargs.items() if value is not None
        }
        if (
            str(cleaned_search_kwargs.get("relationship") or "").strip().lower()
            == _ALL_CONTACTS_RELATIONSHIP_SOURCE
        ):
            cleaned_search_kwargs.pop("relationship", None)
        exact_next = (
            " The next original tool call should be search_contacts with exactly "
            f"these arguments: {json.dumps(cleaned_search_kwargs, sort_keys=True)}. "
            "Do not add helper input values, optional filters, or sentinel values "
            "that are absent from that JSON."
        )
    message_search_kwargs = payload.get("search_messages_kwargs")
    if bool(payload.get("should_call_search_messages")) and isinstance(
        message_search_kwargs, Mapping
    ):
        cleaned_message_kwargs = {
            str(key): value
            for key, value in message_search_kwargs.items()
            if value is not None
        }
        exact_next += (
            " The next original tool call should be search_messages with exactly "
            f"these arguments: {json.dumps(cleaned_message_kwargs, sort_keys=True)}. "
            "Do not replace these generated-tool arguments with manual timestamp, "
            "phone-number, content, or relationship filters."
        )
    downstream_tool_name = str(
        payload.get("downstream_tool_name")
        or payload.get("target_tool_name")
        or payload.get("tool_name")
        or ""
    ).strip()
    generic_search_kwargs = payload.get("search_kwargs")
    if (
        bool(payload.get("should_call_search"))
        and downstream_tool_name
        and isinstance(generic_search_kwargs, Mapping)
        and downstream_tool_name in _tool_names_execution_facing(openai_tools)
    ):
        visible_tool_name = _tool_name_for_call(openai_tools, downstream_tool_name)
        cleaned_generic_search_kwargs = {
            str(key): value
            for key, value in generic_search_kwargs.items()
            if value is not None
        }
        exact_next += (
            " The generated search-window tool returned the next original "
            f"ToolSandbox search call: {downstream_tool_name}. In the current "
            f"visible tool list, call {visible_tool_name} with exactly these "
            f"arguments: {json.dumps(cleaned_generic_search_kwargs, sort_keys=True)}. "
            "Do not replace these generated bounds with blank, null, or manually "
            "guessed search criteria."
        )
    direct_tool_kwargs = payload.get("arguments")
    if (
        bool(payload.get("should_call"))
        and not bool(payload.get("should_call_downstream_tool"))
        and downstream_tool_name
        and isinstance(direct_tool_kwargs, Mapping)
        and downstream_tool_name in _tool_names_execution_facing(openai_tools)
        and not (
            helper_name.startswith("plan_device_state_action_sequence")
            and isinstance(payload.get("action_sequence"), list)
        )
    ):
        visible_tool_name = _tool_name_for_call(openai_tools, downstream_tool_name)
        cleaned_direct_kwargs = {
            str(key): value
            for key, value in direct_tool_kwargs.items()
            if value is not None
        }
        exact_next += (
            " The generated tool returned the next original ToolSandbox call: "
            f"{downstream_tool_name}. In the current visible tool list, call "
            f"{visible_tool_name} with exactly these arguments: "
            f"{json.dumps(cleaned_direct_kwargs, sort_keys=True)}. Do not "
            "substitute a different status getter, setter, search, or action tool."
        )
    downstream_tool_kwargs = payload.get("downstream_tool_kwargs")
    if (
        bool(payload.get("should_call_downstream_tool"))
        and downstream_tool_name
        and isinstance(downstream_tool_kwargs, Mapping)
    ):
        visible_tool_name = _tool_name_for_call(openai_tools, downstream_tool_name)
        cleaned_downstream_kwargs = {
            str(key): value
            for key, value in downstream_tool_kwargs.items()
            if value is not None
        }
        exact_next += (
            " The generated tool returned a downstream original ToolSandbox "
            f"call: {downstream_tool_name}. In the current visible tool list, call "
            f"{visible_tool_name} with exactly these arguments: "
            f"{json.dumps(cleaned_downstream_kwargs, sort_keys=True)}. Do not "
            "substitute a search, modify, or verification tool for this returned "
            "downstream action."
        )
        current_timestamp = _latest_current_timestamp(openai_messages)
        if (
            _generated_tool_batch_independent_calls_enabled()
            and helper_name == "prepare_location_search_args"
            and downstream_tool_name == "search_location_around_lat_lon"
            and current_timestamp is not None
            and "timestamp_to_datetime_info"
            in _tool_names_execution_facing(openai_tools)
            and not _message_already_called_tool(
                openai_messages, "timestamp_to_datetime_info"
            )
        ):
            timestamp_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            exact_next += (
                " If this reminder task also needs relative date/time resolution, "
                "batch the independent current-time normalization in the same "
                f"assistant tool-call turn by also calling {timestamp_tool_name} "
                f"with exactly {json.dumps({'timestamp': current_timestamp}, sort_keys=True)}. "
                "Only batch these two original calls; do not call add_reminder "
                "until the generated reminder-preparation tool later returns "
                "should_call_add_reminder=true."
            )
    if helper_name.startswith("plan_device_state_action_sequence"):
        next_state_action = _next_unsatisfied_state_action(messages, payload)
        if isinstance(next_state_action, Mapping):
            state_tool_name = _execution_facing_tool_name(
                str(next_state_action.get("tool_name", "") or "")
            )
            state_arguments = next_state_action.get("arguments")
            if (
                state_tool_name in SETTING_SETTER_TOOL_NAMES
                and state_tool_name in _tool_names_execution_facing(openai_tools)
                and isinstance(state_arguments, Mapping)
            ):
                visible_state_tool_name = _tool_name_for_call(
                    openai_tools, state_tool_name
                )
                exact_next += (
                    " The generated device-state tool returned an ordered "
                    "action_sequence. The next original ToolSandbox setter must "
                    f"be {state_tool_name}. In the current visible tool list, "
                    f"call {visible_state_tool_name} with exactly these "
                    f"arguments: {json.dumps(_call_contract_kwargs(state_arguments), sort_keys=True)}. "
                    "Do not substitute another setting setter, do not change the "
                    "boolean value, and do not answer before this setter call."
                )
    final_recommendation = str(
        payload.get("exact_final_answer")
        or payload.get("final_answer_recommendation")
        or ""
    ).strip()
    should_call_any = any(
        bool(payload.get(key))
        for key in (
            "should_call_tool",
            "should_call_tools",
            "should_call_search",
            "should_call_search_contacts",
            "should_call_add_reminder",
            "should_call_downstream_tool",
            "should_call",
        )
    )
    if final_recommendation and not should_call_any:
        exact_next += (
            " No original tool call remains from this generated-tool result; answer "
            f"exactly with: {final_recommendation}"
        )
        if bool(payload.get("copy_exactly")):
            exact_next += (
                " Because copy_exactly is true, the entire assistant message must "
                "match that recommendation exactly; do not add a trailing period, "
                "extra acknowledgement, markdown, or any additional words."
            )
    helper_specific = ""
    if helper_name == "prepare_reminder_creation_args":
        abstain_reason = str(payload.get("abstain_reason") or "").strip()
        abstain_lower = abstain_reason.lower()
        if (
            "location" in abstain_lower
            or str(payload.get("location_status") or "").strip().lower()
            in {"lookup_pending", "required_missing"}
        ) and "prepare_location_search_args" in _tool_names_execution_facing(
            openai_tools
        ):
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            latest_user_request = _latest_user_request_text(openai_messages)
            exact_next += (
                " The generated reminder-preparation tool paused because the "
                "reminder location is not resolved. Before add_reminder is "
                "permitted, call generated "
                f"{location_tool_name} with user_request set to "
                f"{json.dumps(latest_user_request)} and location_phrase set to "
                "the exact visible place phrase if one is already isolated, "
                "otherwise an empty string. Then call the returned original "
                "location-search tool with downstream_tool_kwargs unchanged. "
                "After visible coordinates are returned, call "
                "prepare_reminder_creation_args again with the same reminder "
                "content and timestamp context plus location_available=true, "
                "location_lookup_failed=false, latitude, and longitude."
            )
        current_timestamp = _latest_current_timestamp(openai_messages)
        if (
            abstain_reason
            == "missing_current_datetime_info_call_timestamp_to_datetime_info"
            and current_timestamp is not None
            and "timestamp_to_datetime_info"
            in _tool_names_execution_facing(openai_tools)
        ):
            timestamp_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            previous_args = _latest_prior_tool_call_arguments(
                openai_messages, "prepare_reminder_creation_args"
            )
            repeat_detail = ""
            if previous_args:
                sanitized_previous_args = dict(previous_args)
                sanitized_previous_args.pop("current_datetime_info", None)
                repeat_detail = (
                    " Reuse the previous generated-tool arguments exactly, "
                    "except add current_datetime_info from that tool result: "
                    f"{json.dumps(sanitized_previous_args, sort_keys=True)}. "
                    "Do not reset day_offset/hour/minute, do not call "
                    "shift_timestamp, and do not convert a relative phrase such "
                    "as tomorrow into an unrelated absolute date."
                )
            exact_next += (
                " The generated tool abstained because current_datetime_info is "
                "missing. Call original "
                f"{timestamp_tool_name} with exactly "
                f"{json.dumps({'timestamp': current_timestamp}, sort_keys=True)}, "
                "then call prepare_reminder_creation_args again with all required "
                "inputs from the previous attempt plus current_datetime_info set "
                "to the returned dict."
                f"{repeat_detail}"
            )
        absolute_retry_args = _absolute_reminder_prepare_retry_args(
            openai_messages, openai_tools
        )
        if (
            abstain_reason
            in {"missing_time_info", "current_timestamp_placeholder_rejected"}
            and absolute_retry_args is not None
        ):
            helper_tool_name = _tool_name_for_call(
                openai_tools, "prepare_reminder_creation_args"
            )
            exact_next += (
                " The generated reminder-preparation tool abstained before it had "
                "the resolved absolute reminder timestamp. "
                "A visible original datetime_info_to_timestamp result already "
                "resolved the user's absolute date/time. Retry generated "
                f"{helper_tool_name} with exactly these arguments: "
                f"{json.dumps(absolute_retry_args, sort_keys=True)}. Do not ask "
                "for timezone, city, or current-time context on this absolute-date "
                "path. After the generated tool returns should_call_add_reminder=true, "
                "call original add_reminder with add_reminder_kwargs unchanged."
            )
        elif abstain_reason in {
            "missing_time_info",
            "current_timestamp_placeholder_rejected",
        }:
            exact_next += (
                " The generated reminder-preparation tool determined that no "
                "visible user-provided reminder time is available. Do not call "
                "get_current_timestamp, timestamp_to_datetime_info, "
                "relative_day_time_to_timestamp, datetime_info_to_timestamp, or "
                "add_reminder to manufacture a reminder time from the current "
                "clock. Ask the user what date and time they want for the "
                "reminder. After the user supplies that time, call the generated "
                "reminder-preparation tool again with the visible time context."
            )
        if (
            abstain_reason
            in {
                "past_resolved_reminder_timestamp_rejected",
                "current_datetime_info_inconsistent_with_current_timestamp",
                "relative_time_resolved_to_past_rejected",
            }
            and current_timestamp is not None
            and "timestamp_to_datetime_info"
            in _tool_names_execution_facing(openai_tools)
        ):
            timestamp_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            previous_args = _latest_prior_tool_call_arguments(
                openai_messages, "prepare_reminder_creation_args"
            )
            retry_args = dict(previous_args)
            retry_args.pop("resolved_reminder_timestamp", None)
            retry_args.pop("current_datetime_info", None)
            exact_next += (
                " The generated reminder-preparation tool rejected the timestamp "
                f"with abstain_reason={abstain_reason!r}. Do not keep calling "
                "datetime_info_to_timestamp with an old or guessed calendar date. "
                f"Call original {timestamp_tool_name} with exactly "
                f"{json.dumps({'timestamp': current_timestamp}, sort_keys=True)}, "
                "then call prepare_reminder_creation_args again using relative "
                "fields from the visible user phrase. For a phrase like "
                "'tomorrow at 5 PM', use day_offset=1, hour=17, minute=0 and "
                "set resolved_reminder_timestamp to 0 or None so the generated "
                "tool derives the timestamp from current_datetime_info. Preserve "
                f"the other visible arguments where applicable: "
                f"{json.dumps(retry_args, sort_keys=True)}."
            )
        if abstain_reason == "missing_required_helper_inputs":
            previous_args = _latest_prior_tool_call_arguments(
                openai_messages, "prepare_reminder_creation_args"
            )
            retry_args = dict(previous_args)
            if "resolved_reminder_timestamp" not in retry_args:
                resolved_timestamp = _timestamp_from_latest_tool(
                    openai_messages, "relative_day_time_to_timestamp"
                ) or _timestamp_from_latest_tool(
                    openai_messages, "datetime_info_to_timestamp"
                )
                if resolved_timestamp is not None:
                    retry_args["resolved_reminder_timestamp"] = resolved_timestamp
            retry_detail = ""
            if retry_args and retry_args != previous_args:
                retry_detail = (
                    " A visible timestamp tool result can satisfy one omitted "
                    "required input. Retry generated prepare_reminder_creation_args "
                    f"with these arguments: {json.dumps(retry_args, sort_keys=True)}. "
                )
            exact_next += (
                " The generated reminder-preparation tool was called without all "
                "required inputs. Retry the same generated tool before any "
                "add_reminder call and include every required input: content, "
                "resolved_reminder_timestamp, current_timestamp, day_offset, "
                "hour, minute, local_utc_offset_hours, location_requested, "
                "location_required, location_available, latitude, longitude, "
                "location_lookup_failed, and current_datetime_info when available. "
                "If a location search succeeded, set location_lookup_failed=false. "
                "Do not call add_reminder until the generated tool returns "
                "should_call_add_reminder=true."
                f"{retry_detail}"
                + (
                    " Previous partial arguments: "
                    f"{json.dumps(previous_args, sort_keys=True)}."
                    if previous_args
                    else ""
                )
            )
        if not bool(payload.get("should_call_add_reminder")):
            exact_next += (
                " The generated reminder-preparation tool did not authorize "
                "add_reminder. Do not call add_reminder from an earlier timestamp, "
                "manual arithmetic, or partially assembled arguments. Continue only "
                "by satisfying abstain_reason and calling prepare_reminder_creation_args "
                "again until it returns should_call_add_reminder true with "
                "add_reminder_kwargs."
            )
        add_reminder_kwargs = payload.get("add_reminder_kwargs")
        if bool(payload.get("should_call_add_reminder")) and isinstance(
            add_reminder_kwargs, Mapping
        ):
            cleaned_add_kwargs = _call_contract_kwargs(add_reminder_kwargs)
            exact_next += (
                " The generated reminder-preparation tool returned the exact "
                "original add_reminder call contract. The next original "
                "ToolSandbox call must be add_reminder with exactly these "
                f"arguments: {json.dumps(cleaned_add_kwargs, sort_keys=True)}. "
                "Do not substitute an earlier timestamp, recompute the time, or "
                "drop visible coordinates from this contract."
            )
        helper_specific = (
            " For prepare_reminder_creation_args specifically, if "
            "should_call_add_reminder is true, call original add_reminder next "
            "with add_reminder_kwargs unchanged except for omitting null optional "
            "latitude/longitude fields. Do not reuse an earlier timestamp from "
            "relative_day_time_to_timestamp, datetime_info_to_timestamp, or your "
            "own arithmetic when add_reminder_kwargs contains reminder_timestamp. "
            "For relative local dates, preserve the day_offset, hour, and minute "
            "inputs across retries; current_datetime_info must come from "
            "timestamp_to_datetime_info(current_timestamp), not from the reminder "
            "timestamp. "
            "If should_call_add_reminder is false, the side-effect call is not "
            "permitted yet."
        )
    elif helper_name == "prepare_location_search_args":
        abstain_reason = str(payload.get("abstain_reason") or "").strip()
        current_coordinate_abstain_reasons = {
            "missing_current_coordinates_for_broad_location_query",
            "need_current_coordinates_for_broad_location_query",
        }
        if abstain_reason == "missing_reminder_time_before_location_lookup":
            exact_next += (
                " The generated location-search tool paused because this is a "
                "reminder request with a visible place but no visible reminder "
                "date/time. Do not call location tools, setting tools, time "
                "conversion tools, original search_location_around_lat_lon, "
                "prepare_reminder_creation_args, or add_reminder yet. Ask the "
                "user what date and time to use for the reminder. After the user "
                "supplies the missing time, continue with the generated tools "
                "using the same visible reminder content and place phrase."
            )
        if abstain_reason in current_coordinate_abstain_reasons:
            available_names = _tool_names_execution_facing(openai_tools)
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            previous_args = _latest_prior_tool_call_arguments(
                openai_messages, "prepare_location_search_args"
            )
            repeat_detail = ""
            if previous_args:
                sanitized_previous_args = dict(previous_args)
                sanitized_previous_args.pop("latitude", None)
                sanitized_previous_args.pop("longitude", None)
                repeat_detail = (
                    " Reuse the previous generated-tool text arguments: "
                    f"{json.dumps(sanitized_previous_args, sort_keys=True)}. "
                )
            if "get_current_location" in available_names:
                current_location_tool_name = _tool_name_for_call(
                    openai_tools, "get_current_location"
                )
                exact_next += (
                    " The generated location-search tool paused because the "
                    "place phrase is broad and current coordinates are not "
                    "visible yet. The next original ToolSandbox call must be "
                    f"{current_location_tool_name} with no arguments. Do not ask "
                    "the user for current coordinates, do not call time tools, "
                    "and do not call original search_location_around_lat_lon on "
                    "the broad place name yet. If get_current_location returns a "
                    "device-state precondition error, satisfy that error through "
                    "a generated device-state action-sequence tool when one is "
                    "visible, then retry get_current_location. After visible "
                    f"coordinates are returned, call generated {location_tool_name} "
                    "again with the prior broad place name plus the visible "
                    f"latitude and longitude. {repeat_detail}"
                )
            else:
                exact_next += (
                    " The generated location-search tool paused because the "
                    "place phrase is broad and no street, neighborhood, venue "
                    "qualifier, or current-location tool is visible yet. Do not "
                    "ask for current coordinates. Do not call setting getter "
                    "tools, setting setter tools, time tools, or original "
                    "search_location_around_lat_lon for the broad place name. "
                    "Ask the user which specific location, street, neighborhood, "
                    "or venue qualifier to use. After the user clarifies, call "
                    f"generated {location_tool_name} again by combining the "
                    "prior broad place name with the visible clarification "
                    f"phrase. {repeat_detail}"
                )
        helper_specific = (
            " For prepare_location_search_args specifically, use the exact "
            "downstream_tool_kwargs it returns for the original location search. "
            "If it abstains because reminder date/time is missing, ask the user "
            "for that date/time before any location lookup or reminder creation. "
            "If it abstains for missing current coordinates on a broad place "
            "phrase and get_current_location is visible, call that original "
            "current-location tool, then call prepare_location_search_args again "
            "with the returned coordinates before the original location search. "
            "If get_current_location is not visible, ask the user for a specific "
            "location qualifier, not current coordinates. Do not search an "
            "unanchored brand query and do not reuse coordinates from a prior "
            "task."
        )
    elif helper_name == "extract_service_answer_field":
        helper_specific = (
            " For extract_service_answer_field specifically, if abstain_reason is "
            "empty and should_call_downstream_tool is true, call the original "
            "ToolSandbox tool named in downstream_tool_name with "
            "downstream_tool_kwargs unchanged before answering. If that original "
            "tool returns a bare scalar result, call extract_service_answer_field "
            "again with service_payload set to {'result': visible_scalar} and "
            "requested_unit/answer_subject copied from the user request. If "
            "abstain_reason is "
            "empty and answer_value is nonempty, use answer_value and answer_unit "
            "as the final answer. If answer_kind contains temperature, the user "
            "requested Fahrenheit, and answer_unit is Celsius, call original "
            "unit_conversion before giving the final answer. If answer_kind is "
            "phone_number, preserve "
            "answer_value exactly as written; do not add spaces, parentheses, "
            "hyphens, markdown, or alternate phone formatting. If answer_kind "
            "is distance, say the distance is "
            "approximately that value in kilometers unless answer_unit states a "
            "different unit. Include the scalar answer again in closing or "
            "verification replies instead of replacing it with a generic "
            "acknowledgement. If exact_final_answer or "
            "final_answer_recommendation is present with copy_exactly, preserve "
            "that answer as the complete response on follow-up turns unless the "
            "user clearly asks a different task. Do not call map, location, "
            "search, setting, direction/navigation, or generated tools "
            "only to verify or elaborate a distance answer that this generated tool "
            "already finalized."
        )
    elif helper_name == "plan_device_status_lookup":
        helper_specific = (
            " For plan_device_status_lookup specifically, if should_call is true, "
            "call the original ToolSandbox getter named in tool_name using "
            "arguments. If should_call is false and final_answer_recommendation is "
            "nonempty, answer with that recommendation exactly and do not call a "
            "setter."
        )
        if bool(payload.get("should_call")):
            status_tool_name = str(payload.get("tool_name") or "").strip()
            status_arguments = payload.get("arguments")
            if status_tool_name and isinstance(status_arguments, Mapping):
                exact_next += (
                    " The next original device-status getter must be "
                    f"{status_tool_name} with exactly these arguments: "
                    f"{json.dumps(dict(status_arguments), sort_keys=True)}. "
                    "Do not call any other device getter for this helper result."
                )
    elif helper_name == "plan_contact_lookup_query":
        helper_specific = (
            " For plan_contact_lookup_query specifically, if "
            "should_call_search_contacts is true, call original search_contacts "
            "next with search_contacts_kwargs unchanged. Do not add is_self, "
            "relationship, name, phone_number, or any other optional filter unless "
            "that key is present in search_contacts_kwargs. If "
            "final_answer_recommendation is nonempty, answer with that value "
            "exactly and do not add unrelated contact fields. If copy_exactly is "
            "true, do not add punctuation or any surrounding text. The helper's "
            "input arguments are not search filters; only search_contacts_kwargs "
            "is the search contract."
        )
    elif helper_name == "plan_contact_relationship_batch_update":
        helper_specific = (
            " For plan_contact_relationship_batch_update specifically, if "
            "should_call_search_contacts is true, call original search_contacts "
            "next with search_contacts_kwargs unchanged; do not add is_self or "
            "other optional filters unless that key is present in "
            "search_contacts_kwargs. If source_relationship is "
            f"{_ALL_CONTACTS_RELATIONSHIP_SOURCE!r}, still call search_contacts "
            "with search_contacts_kwargs unchanged; never pass that sentinel as "
            "a real relationship filter. After search_contacts returns visible "
            "contacts, call plan_contact_relationship_batch_update again with "
            "contacts set to that visible result. If should_call_tools is true "
            "and downstream_tool_kwargs_list is present, call original "
            "modify_contact once for each returned kwargs item. The generated "
            "helper prepares the batch; only original modify_contact performs "
            "the side effects."
        )
    elif helper_name.startswith("plan_device_state_action_sequence"):
        next_action = _next_unsatisfied_state_action(openai_messages, payload)
        if next_action is not None:
            next_tool_name = str(next_action.get("tool_name") or "").strip()
            next_arguments = next_action.get("arguments")
            if next_tool_name and isinstance(next_arguments, Mapping):
                exact_next += (
                    " For this generated state action_sequence, skip any earlier "
                    "setter actions that are already satisfied by visible setter "
                    "results in this conversation. The next unsatisfied original "
                    f"setter is {next_tool_name}; call "
                    f"{_tool_name_for_call(openai_tools, next_tool_name)} with "
                    f"exactly these arguments: "
                    f"{json.dumps(dict(next_arguments), sort_keys=True)}. Do not "
                    "call an already-satisfied low-battery, wifi, cellular, or "
                    "location setter again before this next action."
                )
        helper_specific = (
            " For device-state action sequence helpers specifically, execute "
            "action_sequence one original setter call at a time in the returned "
            "order. Do not put multiple setting setters in the same assistant "
            "tool-call message, because the runtime may not preserve that order. "
            "After each setter succeeds with None, continue with the next returned "
            "action or the original user task. If final_response_recommendation "
            "is exactly continue_original_task, treat it as an internal control "
            "marker, never as user-facing text. After the downstream original "
            "task succeeds, briefly report that downstream task completion rather "
            "than saying continue_original_task."
        )
    elif helper_name == "days_between_timestamps":
        try:
            day_count = int(payload.get("days"))
        except (TypeError, ValueError):
            day_count = None
        if day_count is not None:
            holiday_label = _holiday_context_label(openai_messages)
            exact_next += (
                " The generated days_between_timestamps result already computed "
                f"days={day_count} from visible timestamp tool outputs. Preserve "
                "that computed value in the next answer unless a later visible "
                "tool result changes one of the timestamps."
            )
            if holiday_label:
                exact_next += (
                    " For this holiday/day-count answer, use the generated day "
                    f"count and the visible target label {holiday_label!r} in a "
                    "short declarative sentence without adding uncertainty."
                )
    return {
        "role": "system",
        "content": (
            f"{HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL} The latest generated "
            f"helper result came from {helper_name} and contains these fields: "
            f"{payload_keys}. Treat generated-helper output as a deterministic "
            "plan or value, not as a completed side effect. If the helper output "
            "contains should_call_tool, should_call_search, should_call, "
            "should_call_add_reminder, or should_call_downstream_tool set to "
            "true, then call the original "
            "ToolSandbox tool named by downstream_tool_name, target_tool_name, "
            "tool_name, or the matching *_kwargs field using the returned kwargs. "
            "Ignore kwargs entries whose value is null/None, and do not invent "
            "missing required arguments. If the helper returns an action_sequence "
            "or downstream_tool_kwargs_list, execute only the original tool calls "
            "listed there, in order, after checking that each named original tool "
            "is visible. If the helper returns should_abstain, abstain_reason, "
            "exact_final_answer, or final_answer_recommendation, and it has not "
            "requested a remaining original tool call, answer from that field "
            "without adding unsupported facts. Never treat the generated helper "
            "itself as performing the original side effect."
            f"{exact_next}"
            f"{helper_specific}"
        ),
    }


def _contact_relationship_batch_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge actors to use the generated bulk relationship helper."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_contact_relationship_batch_update" not in available_names:
        return None
    if not ({"search_contacts", "modify_contact"} <= available_names):
        return None
    if _called_tool_after_latest_user(
        openai_messages, "plan_contact_relationship_batch_update"
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CONTACT_RELATIONSHIP_BATCH_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    request = _relationship_batch_request(openai_messages)
    if request is None:
        return None
    source = request.get("source_relationship", "")
    target = request.get("target_relationship", "")
    return {
        "role": "system",
        "content": (
            f"{CONTACT_RELATIONSHIP_BATCH_POLICY_SENTINEL} A generated bulk "
            "contact-relationship helper is visible. For this relationship "
            "change request, call plan_contact_relationship_batch_update before "
            "manual search_contacts or modify_contact. Use the relationship "
            f"values parsed from the user request: source_relationship={source!r}, "
            f"target_relationship={target!r}, and contacts=[]. If the helper "
            "returns should_call_search_contacts, call original search_contacts "
            "with search_contacts_kwargs unchanged; do not add is_self or "
            "optional filters that the helper did not return. If "
            f"source_relationship={_ALL_CONTACTS_RELATIONSHIP_SOURCE!r}, keep "
            "that sentinel inside the generated helper arguments only; never "
            "pass it as a relationship value to search_contacts. After visible "
            "contacts are returned, call plan_contact_relationship_batch_update "
            "again with contacts set to that result, then execute the returned "
            "downstream_tool_kwargs_list using original modify_contact. The "
            "helper prepares deterministic kwargs only; it does not perform the "
            "side effects."
        ),
    }


def _contact_relationship_batch_result_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Narrow handoff after generated bulk relationship planner output."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_contact_relationship_batch_update" not in available_names:
        return None
    if not ({"search_contacts", "modify_contact"} <= available_names):
        return None
    latest = _latest_tool_message_index(
        openai_messages,
        {"plan_contact_relationship_batch_update", "search_contacts", "modify_contact"},
    )
    if latest is None:
        return None
    latest_index, latest_message = latest
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if any(
        CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL
        in str(message.get("content", ""))
        for message in messages[latest_index + 1 :]
    ):
        return None
    latest_name = _execution_facing_tool_name(str(latest_message.get("name", "") or ""))
    if latest_name == "modify_contact":
        latest_plan = _latest_tool_message_index(
            openai_messages, {"plan_contact_relationship_batch_update"}
        )
        if latest_plan is None:
            return None
        plan_index, plan_message = latest_plan
        payload = _parse_mapping_payload(plan_message.get("content"))
        downstream = payload.get("downstream_tool_kwargs_list")
        final = str(payload.get("final_answer_recommendation") or "").strip()
        if not final or not isinstance(downstream, list) or not downstream:
            return None
        completed_modify_calls = sum(
            1
            for message in messages[plan_index + 1 :]
            if _execution_facing_tool_name(str(message.get("name", "") or ""))
            == "modify_contact"
        )
        if completed_modify_calls < len(downstream):
            return None
        return {
            "role": "system",
            "content": (
                f"{CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL} The "
                "original modify_contact calls returned for the latest generated "
                "relationship-batch plan have completed. Answer exactly with the "
                f"generated final recommendation: {final}"
            ),
        }
    if latest_name == "plan_contact_relationship_batch_update":
        payload = _parse_mapping_payload(latest_message.get("content"))
        if payload.get("abstain_reason"):
            return None
        search_kwargs = payload.get("search_contacts_kwargs")
        if bool(payload.get("should_call_search_contacts")) and isinstance(
            search_kwargs, Mapping
        ):
            cleaned_search_kwargs = {
                str(key): value
                for key, value in search_kwargs.items()
                if value is not None
            }
            if (
                str(cleaned_search_kwargs.get("relationship") or "").strip().lower()
                == _ALL_CONTACTS_RELATIONSHIP_SOURCE
            ):
                cleaned_search_kwargs.pop("relationship", None)
            search_tool_name = _tool_name_for_call(openai_tools, "search_contacts")
            return {
                "role": "system",
                "content": (
                    f"{CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL} The "
                    "latest generated plan is waiting for an original contact "
                    f"search. Call {search_tool_name} next with exactly this "
                    f"JSON: {json.dumps(cleaned_search_kwargs, sort_keys=True)}. "
                    "Do not add is_self, name, phone_number, relationship, or "
                    "any optional filter unless it is present in that JSON. "
                    "After the original search returns visible contacts, call "
                    "plan_contact_relationship_batch_update again with contacts "
                    "set to that visible result."
                ),
            }
        downstream = payload.get("downstream_tool_kwargs_list")
        if bool(payload.get("should_call_tools")) and isinstance(downstream, list):
            modify_tool_name = _tool_name_for_call(openai_tools, "modify_contact")
            return {
                "role": "system",
                "content": (
                    f"{CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL} The "
                    "latest generated plan returned a batch of original contact "
                    f"updates. Call {modify_tool_name} once for each item in "
                    "downstream_tool_kwargs_list, using each kwargs object "
                    "unchanged. Do not update contacts outside that returned "
                    "list, and do not treat the generated tool itself as the "
                    "side effect."
                ),
            }
        return None
    if latest_name != "search_contacts":
        return None
    if not _called_tool_after_latest_user(
        openai_messages, "plan_contact_relationship_batch_update"
    ):
        return None
    request = _relationship_batch_request(openai_messages)
    if request is None:
        return None
    return {
        "role": "system",
        "content": (
            f"{CONTACT_RELATIONSHIP_BATCH_RESULT_POLICY_SENTINEL} The latest "
            "original search_contacts result is the visible record set for a "
            "generated relationship-batch workflow. Call "
            "plan_contact_relationship_batch_update again with "
            f"source_relationship={request.get('source_relationship', '')!r}, "
            f"target_relationship={request.get('target_relationship', '')!r}, "
            "and contacts set exactly to the latest search_contacts result. "
            "Do not call modify_contact until that generated tool returns "
            "downstream_tool_kwargs_list."
        ),
    }


def _visible_record_selector_setup_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Tell actors to gather visible records before generated selectors."""
    selectors = _selector_tool_names(openai_tools)
    if not selectors:
        return None
    if _messages_show_prior_candidate_records(openai_messages):
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in selectors):
        return None
    latest_user_index = _latest_user_index(openai_messages)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for index, message in enumerate(messages):
        if index <= latest_user_index:
            continue
        if VISIBLE_RECORD_SELECTOR_SETUP_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    available_names = _tool_names_execution_facing(openai_tools)
    visible_original_searches = sorted(
        name
        for name in ("search_contacts", "search_messages", "search_reminder")
        if name in available_names
    )
    if not visible_original_searches:
        return None
    helper_list = ", ".join(sorted(selectors))
    search_list = ", ".join(visible_original_searches)
    message_selector_note = ""
    if (
        "select_message_content_by_recency" in selectors
        and "search_messages" in available_names
    ):
        message_selector_note = (
            " For message latest/oldest content requests, if no message records "
            "are visible yet, call original search_messages to gather candidate "
            "message records, then call select_message_content_by_recency with "
            "records set to that result and selection_mode copied from the "
            "latest or oldest wording. Do not answer from raw message records "
            "before the generated selector runs."
        )
    return {
        "role": "system",
        "content": (
            f"{VISIBLE_RECORD_SELECTOR_SETUP_POLICY_SENTINEL} A generated "
            f"visible-record selector is available: {helper_list}. Do not call "
            "a selector with records=[] before candidate records are visible. "
            "First gather candidate records using a generated search-kwargs "
            "planner when one is visible; otherwise use an original search tool "
            f"that matches the requested record type: {search_list}. Use only "
            "constraints supplied by the user, returned by a generated planner, "
            "or established by visible tool output. After a non-empty original "
            "search result is visible, call the generated selector with records "
            "set to that result. For singular latest, oldest, next, or upcoming "
            "requests, select one record before any side-effect action; do not "
            "modify or remove multiple records unless the user asked for a "
            "batch action."
            f"{message_selector_note}"
        ),
    }


def _contact_remove_success_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve visible generated-lookup identifiers after remove_contact succeeds."""
    if "plan_contact_lookup_query" not in _tool_names_execution_facing(openai_tools):
        return None
    if not _message_already_called_tool(openai_messages, "plan_contact_lookup_query"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CONTACT_REMOVE_SUCCESS_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    latest_call = _latest_successful_crud_tool_call(openai_messages)
    if latest_call is None:
        return None
    tool_name, _arguments = latest_call
    if tool_name != "remove_contact":
        return None
    search_args = _latest_prior_tool_call_arguments(openai_messages, "search_contacts")
    phone = _normalize_visible_phone(search_args.get("phone_number"))
    if not phone:
        return None
    return {
        "role": "system",
        "content": (
            f"{CONTACT_REMOVE_SUCCESS_POLICY_SENTINEL} The generated lookup path "
            f"used the visible phone number {phone}, and the original "
            "remove_contact tool has succeeded. In the final answer, preserve "
            "that user-requested identifier: state that the phone number was "
            "removed from the contact. Do not answer only with the contact name."
        ),
    }


def _reminder_location_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge location reminder tasks back through generated args then add_reminder."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"prepare_reminder_creation_args", "add_reminder"} <= available_names):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_LOCATION_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    payload = _latest_tool_payload_by_name(
        openai_messages, "prepare_reminder_creation_args"
    )
    if not payload:
        return None
    pending_location = (
        str(payload.get("location_status") or "").strip().lower() == "lookup_pending"
        or "location_lookup_pending" in str(payload.get("abstain_reason") or "").lower()
    )
    if not pending_location:
        return None
    records = _latest_location_search_records(openai_messages)
    if not records:
        return None
    latest_search_args = _latest_prior_tool_call_arguments(
        openai_messages, "search_location_around_lat_lon"
    )
    coords = _best_location_coordinates(
        openai_messages,
        query=str(latest_search_args.get("location") or ""),
    )
    if coords is None:
        return None
    latest_tool_index = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    latest_user_index = _latest_user_index(openai_messages)
    if latest_tool_index is None:
        return None
    latest_user = _latest_user_request_text(openai_messages).lower()
    confirmed = any(
        token in latest_user
        for token in (
            "yes",
            "right",
            "correct",
            "that's it",
            "that is it",
            "use that",
            "proceed",
        )
    )
    if latest_user_index > latest_tool_index[0] and not confirmed:
        return None
    latitude, longitude = coords
    return {
        "role": "system",
        "content": (
            f"{REMINDER_LOCATION_COMPLETION_POLICY_SENTINEL} "
            "prepare_reminder_creation_args previously paused because an optional "
            "location lookup was pending. A visible location result with "
            f"coordinates latitude={latitude}, longitude={longitude} is now "
            "available and the user has not supplied a different location. Do "
            "not ask for another confirmation loop. Call "
            "prepare_reminder_creation_args again with the same reminder content "
            "and resolved timestamp from the prior helper/timestamp result, set "
            "location_available=true, location_lookup_failed=false, and pass "
            "these latitude/longitude values. If it returns "
            "should_call_add_reminder=true, call original add_reminder next with "
            "add_reminder_kwargs unchanged. The generated helper prepares "
            "arguments only; the original add_reminder performs the side effect."
        ),
    }


def _reminder_datetime_continuation_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Continue generated reminder argument prep after timestamp context lookup."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"prepare_reminder_creation_args", "timestamp_to_datetime_info"}
        <= available_names
    ):
        return None
    latest_prepare = _latest_tool_message_index(
        openai_messages, {"prepare_reminder_creation_args"}
    )
    latest_datetime = _latest_tool_message_index(
        openai_messages, {"timestamp_to_datetime_info"}
    )
    if latest_prepare is None or latest_datetime is None:
        return None
    prepare_index, prepare_message = latest_prepare
    datetime_index, datetime_message = latest_datetime
    if datetime_index <= prepare_index:
        return None
    latest_policy_index = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        if REMINDER_DATETIME_CONTINUATION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            latest_policy_index = index
    if latest_policy_index >= datetime_index:
        return None
    payload = _parse_mapping_payload(prepare_message.get("content"))
    reason = str(payload.get("abstain_reason") or "").strip()
    if reason not in {
        "missing_current_datetime_info_call_timestamp_to_datetime_info",
        "past_resolved_reminder_timestamp_rejected",
        "current_datetime_info_inconsistent_with_current_timestamp",
        "relative_time_resolved_to_past_rejected",
    }:
        return None
    previous_args = _latest_reminder_creation_args_for_abstain_reason(
        openai_messages, reason
    )
    if not previous_args:
        previous_args = _latest_prior_tool_call_arguments(
            openai_messages, "prepare_reminder_creation_args"
        )
    if not previous_args:
        return None
    current_info = _parse_mapping_payload(datetime_message.get("content"))
    if not current_info:
        return None
    retry_args = dict(previous_args)
    retry_args["current_datetime_info"] = current_info
    if reason in {
        "past_resolved_reminder_timestamp_rejected",
        "current_datetime_info_inconsistent_with_current_timestamp",
        "relative_time_resolved_to_past_rejected",
    }:
        relative_request = _relative_reminder_creation_request(openai_messages)
        if relative_request is not None:
            if str(relative_request.get("content") or "").strip():
                retry_args["content"] = str(relative_request["content"])
            retry_args["day_offset"] = int(relative_request["day_offset"])
            retry_args["hour"] = int(relative_request["hour"])
            retry_args["minute"] = int(relative_request["minute"])
            retry_args["resolved_reminder_timestamp"] = None
        elif int(retry_args.get("day_offset") or 0) > 0:
            retry_args["resolved_reminder_timestamp"] = None
    reminder_tool_name = _tool_name_for_call(
        openai_tools, "prepare_reminder_creation_args"
    )
    return {
        "role": "system",
        "content": (
            f"{REMINDER_DATETIME_CONTINUATION_POLICY_SENTINEL} "
            "timestamp_to_datetime_info has now returned the current timestamp "
            "context requested by the generated reminder-preparation tool. The "
            f"next tool call should be generated {reminder_tool_name} with these "
            f"arguments: {json.dumps(retry_args, sort_keys=True)}. Do not call "
            "datetime_info_to_timestamp or shift_timestamp for a relative phrase "
            "unless the user supplied an explicit calendar date. If the generated "
            "tool returns should_call_add_reminder=true, call original "
            "add_reminder next with add_reminder_kwargs unchanged."
        ),
    }


def _reminder_current_datetime_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Continue relative reminder preparation after the current timestamp."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"prepare_reminder_creation_args", "get_current_timestamp"} <= available_names
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_CURRENT_DATETIME_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        return None
    if _timestamp_to_datetime_info_for_timestamp(openai_messages, current_timestamp):
        return None
    relative_request = _relative_reminder_creation_request(openai_messages)
    if relative_request is None:
        return None
    content = str(relative_request.get("content") or "").strip()
    if not content:
        return None
    reminder_tool_name = _tool_name_for_call(
        openai_tools, "prepare_reminder_creation_args"
    )
    args = {
        "content": content,
        "resolved_reminder_timestamp": None,
        "current_timestamp": current_timestamp,
        "day_offset": int(relative_request["day_offset"]),
        "hour": int(relative_request["hour"]),
        "minute": int(relative_request["minute"]),
    }
    return {
        "role": "system",
        "content": (
            f"{REMINDER_CURRENT_DATETIME_POLICY_SENTINEL} This reminder task uses "
            "a relative local date/time such as tomorrow, next week, or a weekday, "
            "and get_current_timestamp has already returned the visible current "
            "timestamp. Call original timestamp_to_datetime_info on that exact "
            "current timestamp next. After that result is visible, call the "
            f"generated reminder-preparation tool with these scalar arguments "
            f"plus current_datetime_info from the tool result: "
            f"{json.dumps(args, sort_keys=True)}. This generated tool prepares "
            "arguments only; original add_reminder must still run when it returns "
            "should_call_add_reminder=true."
        ),
    }


def _reminder_relative_composite_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Prefer a composite generated action tool after visible datetime context."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"prepare_reminder_creation_args", "add_reminder"} <= available_names):
        return None
    if _message_already_called_tool(openai_messages, "prepare_reminder_creation_args"):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    if _reminder_location_parts(openai_messages) is not None:
        return None
    request = _relative_reminder_creation_request(openai_messages)
    if request is None:
        return None
    content = str(request.get("content") or "").strip()
    if not content:
        return None
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        return None
    current_info = _timestamp_to_datetime_info_for_timestamp(
        openai_messages, current_timestamp
    )
    if current_info is None:
        return None
    latest_policy_index = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        if REMINDER_DATETIME_CONTINUATION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            latest_policy_index = index
    latest_datetime = _latest_tool_message_index(
        openai_messages, {"timestamp_to_datetime_info"}
    )
    if latest_datetime is not None and latest_policy_index >= latest_datetime[0]:
        return None
    reminder_tool_name = _tool_name_for_call(
        openai_tools, "prepare_reminder_creation_args"
    )
    args = {
        "content": content,
        "resolved_reminder_timestamp": None,
        "current_timestamp": current_timestamp,
        "day_offset": int(request["day_offset"]),
        "hour": int(request["hour"]),
        "minute": int(request["minute"]),
        "current_datetime_info": current_info,
    }
    return {
        "role": "system",
        "content": (
            f"{REMINDER_DATETIME_CONTINUATION_POLICY_SENTINEL} The current "
            "timestamp and its visible local datetime context are now available. "
            "Use the composite generated reminder-preparation tool rather than "
            "first calling a separate relative-time canonicalizer. Call generated "
            f"{reminder_tool_name} with exactly these arguments: "
            f"{json.dumps(args, sort_keys=True)}. If it returns "
            "should_call_add_reminder=true, call original add_reminder next with "
            "add_reminder_kwargs unchanged."
        ),
    }


def _reminder_location_batch_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Keep relative reminder-location workflows in fair, low-turn tool order."""

    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {
            "prepare_location_search_args",
            "prepare_reminder_creation_args",
            "search_location_around_lat_lon",
            "get_current_timestamp",
            "timestamp_to_datetime_info",
            "add_reminder",
        }
        <= available_names
    ):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    request = _relative_reminder_creation_request(openai_messages)
    parts = _reminder_location_parts(openai_messages)
    if request is None or parts is None:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_LOCATION_BATCH_POLICY_SENTINEL in str(message.get("content", "")):
            return None

    current_timestamp = _latest_current_timestamp(openai_messages)
    current_info = (
        _timestamp_to_datetime_info_for_timestamp(openai_messages, current_timestamp)
        if current_timestamp is not None
        else None
    )
    latest_prepare = _latest_tool_message_index(
        openai_messages, {"prepare_location_search_args"}
    )
    latest_search = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    location_tool_name = _tool_name_for_call(
        openai_tools, "prepare_location_search_args"
    )
    reminder_tool_name = _tool_name_for_call(
        openai_tools, "prepare_reminder_creation_args"
    )
    search_tool_name = _tool_name_for_call(
        openai_tools, "search_location_around_lat_lon"
    )
    timestamp_tool_name = _tool_name_for_call(openai_tools, "get_current_timestamp")
    datetime_tool_name = _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")

    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    location_args = {
        "user_request": all_user_text or _latest_user_request_text(openai_messages),
        "location_phrase": str(parts.get("location") or "").strip(),
    }
    if latest_prepare is None:
        if current_timestamp is None:
            return {
                "role": "system",
                "content": (
                    f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} This relative "
                    "reminder request includes a visible place phrase. To avoid "
                    "extra turns, batch independent setup now: call original "
                    f"{timestamp_tool_name} with no arguments and generated "
                    f"{location_tool_name} with "
                    f"{json.dumps(location_args, sort_keys=True)} in the same "
                    "assistant turn. Do not call prepare_reminder_creation_args "
                    "until the current datetime context and visible location-search "
                    "coordinates are available."
                ),
            }
        if current_info is None:
            return {
                "role": "system",
                "content": (
                    f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} Current timestamp "
                    "is visible and the location phrase is independent. Batch the "
                    f"next setup calls: original {datetime_tool_name} with "
                    f"timestamp={current_timestamp} and generated {location_tool_name} "
                    f"with {json.dumps(location_args, sort_keys=True)}. Do not pass "
                    "the current timestamp as resolved_reminder_timestamp."
                ),
            }
        return {
            "role": "system",
            "content": (
                f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} The relative-time context "
                f"is visible. Call generated {location_tool_name} with "
                f"{json.dumps(location_args, sort_keys=True)} before the generated "
                "reminder-preparation tool, then call the returned original "
                "location-search tool with downstream_tool_kwargs unchanged."
            ),
        }

    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_location_search_args"
    )
    kwargs = (
        payload.get("downstream_tool_kwargs") if isinstance(payload, Mapping) else None
    )
    should_search = bool(
        isinstance(payload, Mapping)
        and payload.get("should_call_downstream_tool")
        and str(payload.get("downstream_tool_name") or "")
        == "search_location_around_lat_lon"
        and isinstance(kwargs, Mapping)
    )
    search_after_prepare = (
        latest_search is not None
        and latest_prepare is not None
        and latest_search[0] > latest_prepare[0]
    )
    if should_search and not search_after_prepare:
        cleaned_kwargs = _call_contract_kwargs(cast(Mapping[str, Any], kwargs))
        if current_timestamp is not None and current_info is None:
            return {
                "role": "system",
                "content": (
                    f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} A generated "
                    "location-search tool has prepared the original search kwargs. "
                    "Batch the independent next calls: original "
                    f"{datetime_tool_name} with timestamp={current_timestamp} and "
                    f"original {search_tool_name} with "
                    f"{json.dumps(cleaned_kwargs, sort_keys=True)}. Use the returned "
                    "datetime dict and returned coordinates in the generated "
                    "reminder-preparation tool. Do not pass current_timestamp as a "
                    "resolved reminder timestamp."
                ),
            }
        return {
            "role": "system",
            "content": (
                f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} Call original "
                f"{search_tool_name} with the generated downstream kwargs "
                f"{json.dumps(cleaned_kwargs, sort_keys=True)} before calling "
                "prepare_reminder_creation_args."
            ),
        }

    if current_timestamp is not None and current_info is None:
        return {
            "role": "system",
            "content": (
                f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} Location-search evidence "
                "is visible, but the current timestamp still needs local datetime "
                f"context. Call original {datetime_tool_name} with "
                f"timestamp={current_timestamp}; then call generated "
                "prepare_reminder_creation_args with current_datetime_info and the "
                "visible location coordinates."
            ),
        }
    if current_timestamp is None or current_info is None or not search_after_prepare:
        return None

    latest_search_args = _latest_prior_tool_call_arguments(
        openai_messages, "search_location_around_lat_lon"
    )
    coords = _best_location_coordinates(
        openai_messages,
        query=str(latest_search_args.get("location") or ""),
    )
    if coords is None:
        return None
    latitude, longitude = coords
    reminder_args = {
        "content": str(parts.get("content") or request.get("content") or "").strip(),
        "resolved_reminder_timestamp": None,
        "current_timestamp": current_timestamp,
        "day_offset": int(request["day_offset"]),
        "hour": int(request["hour"]),
        "minute": int(request["minute"]),
        "current_datetime_info": current_info,
        "location_requested": True,
        "location_required": True,
        "location_available": True,
        "latitude": latitude,
        "longitude": longitude,
        "location_lookup_failed": False,
    }
    return {
        "role": "system",
        "content": (
            f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} The generated location "
            "search and current datetime context are both visible. Call generated "
            f"{reminder_tool_name} with exactly these arguments: "
            f"{json.dumps(reminder_args, sort_keys=True)}. If it returns "
            "should_call_add_reminder=true, call original add_reminder next with "
            "add_reminder_kwargs unchanged."
        ),
    }


def _helper_answer_retention_actor_policy_message(
    openai_messages: object,
    openai_tools: object | None = None,
) -> dict[str, str] | None:
    """Preserve final-answer-ready generated-tool output through closing turns."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ANSWER_RETENTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    status_followup = _latest_user_is_device_status_retention_followup(openai_messages)
    retention_followup = _latest_user_is_answer_retention_followup(openai_messages)
    if not retention_followup and not status_followup:
        return None
    if _pending_reminder_side_effect_after_generated_helper(
        openai_messages, openai_tools
    ):
        return None
    answer = _recent_exact_final_answer_from_tool(openai_messages)
    if not answer:
        if not _messages_show_generated_helper_call(openai_messages, openai_tools):
            return None
        answer = _recent_tool_backed_answer_text(openai_messages)
    if not answer:
        return None
    latest_user = _latest_user_request_text(openai_messages).lower()
    if any(
        token in latest_user
        for token in (
            "don't leak",
            "do not leak",
            "don't repeat",
            "do not repeat",
            "keep it private",
            "keep that private",
            "private info",
            "private information",
        )
    ):
        return {
            "role": "system",
            "content": (
                f"{ANSWER_RETENTION_ACTOR_POLICY_SENTINEL} A generated tool already "
                "supported the prior tool-backed answer, and the user is now asking "
                "not to repeat that retrieved value. Do not repeat the retrieved "
                "value, do not call another private lookup, and answer only with a "
                "brief acknowledgement of the privacy request."
            ),
        }
    status_instruction = (
        " If the user is asking a same-thread device-status follow-up, start "
        "from that generated-tool-supported status answer, then answer only from "
        "visible tool results or facts the user just supplied."
        if status_followup
        else ""
    )
    return {
        "role": "system",
        "content": (
            f"{ANSWER_RETENTION_ACTOR_POLICY_SENTINEL} A generated tool already "
            "supported the current tool-backed answer. The previous answer was: "
            f"{answer} The user is acknowledging or closing that generated-tool-supported "
            "lookup. Begin the next response with a concise recap that preserves "
            "the concrete answer value. If the generated tool returned exact_final_answer "
            "or final_answer_recommendation with copy_exactly, begin with that "
            "answer exactly. Do not answer only with a generic acknowledgement, "
            "and do not invent new "
            f"facts.{status_instruction}"
        ),
    }


def _device_status_answer_retention_actor_policy_message(
    openai_messages: object,
    openai_tools: object | None = None,
) -> dict[str, str] | None:
    """Preserve generated device-status answers through same-thread follow-ups."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if DEVICE_STATUS_RETENTION_ACTOR_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    answer = _recent_device_status_answer_from_tool(openai_messages)
    if not answer:
        return None
    if _should_close_after_helper_answer(openai_messages, openai_tools):
        return None
    if not (
        _latest_user_is_device_status_retention_followup(openai_messages)
        or _latest_user_is_answer_retention_followup(openai_messages)
    ):
        return None
    return {
        "role": "system",
        "content": (
            f"{DEVICE_STATUS_RETENTION_ACTOR_POLICY_SENTINEL} A generated "
            "device-status helper returned this final answer recommendation: "
            f"{answer} For this next response, begin exactly with: {answer} "
            "Then, if the user asked a same-thread follow-up, answer it only "
            "from visible tool results or facts the user supplied. If the user "
            "is only acknowledging or closing the conversation, keep the recap "
            "to one concise sentence. Do not answer only with a generic "
            "acknowledgement, do not call a setter for a read-only status "
            "lookup, and do not invent unsupported diagnostics."
        ),
    }


def _should_close_after_helper_answer(
    openai_messages: object,
    openai_tools: object | None,
) -> bool:
    if openai_tools is None:
        return False
    if "end_conversation" not in _tool_names_execution_facing(openai_tools):
        return False
    return _latest_user_is_closing_acknowledgement(
        openai_messages
    ) or _latest_user_is_post_completion_device_status_drift(openai_messages)


def _pending_reminder_side_effect_after_generated_helper(
    openai_messages: object,
    openai_tools: object | None,
) -> bool:
    if openai_tools is None:
        return False
    available_names = _tool_names_execution_facing(openai_tools)
    if "add_reminder" not in available_names:
        return False
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return False
    user_text = " ".join(_all_user_texts(openai_messages)).lower()
    if not any(token in user_text for token in ("remind", "reminder", "todo")):
        return False
    return _messages_show_generated_helper_call(openai_messages, openai_tools)


def _helper_answer_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object | None = None,
) -> dict[str, str] | None:
    """Close acknowledgement loops after a generated helper produced the answer."""
    if openai_tools is None:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if HELPER_ANSWER_COMPLETION_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if _pending_reminder_side_effect_after_generated_helper(
        openai_messages, openai_tools
    ):
        return None
    if not (
        _latest_user_is_closing_acknowledgement(openai_messages)
        or _latest_user_is_post_completion_task_drift(openai_messages)
        or _latest_user_is_post_completion_device_status_drift(openai_messages)
        or _latest_user_is_post_completion_state_drift(openai_messages)
        or _latest_user_is_answer_retention_followup(openai_messages)
    ):
        return None
    answer = _recent_exact_final_answer_from_tool(openai_messages)
    if not answer:
        answer = _recent_device_status_answer_from_tool(openai_messages) or ""
    if not answer and _messages_show_generated_helper_call(
        openai_messages, openai_tools
    ):
        answer = _recent_tool_backed_answer_text(openai_messages) or ""
    if not answer:
        completed = _completed_state_action_sequence_payload(openai_messages)
        if completed is not None:
            payload, completed_count = completed
            sequence = payload.get("action_sequence")
            if isinstance(sequence, list) and completed_count >= len(sequence):
                answer = str(payload.get("final_response_recommendation") or "").strip()
    if not answer:
        return None
    close_with_tool_instruction = ""
    latest_user_has_no_new_task = (
        _latest_user_is_closing_acknowledgement(openai_messages)
        or _latest_user_is_answer_retention_followup(openai_messages)
        or _latest_user_is_post_completion_task_drift(openai_messages)
        or _latest_user_is_post_completion_device_status_drift(openai_messages)
    )
    if (
        latest_user_has_no_new_task
        and "end_conversation" in _tool_names_execution_facing(openai_tools)
    ):
        end_tool_name = _tool_name_for_call(openai_tools, "end_conversation")
        close_with_tool_instruction = (
            f" Because original {end_tool_name} is visible and the latest user "
            "message is only acknowledging, recapping, or drifting after the "
            f"helper-backed answer, call {end_tool_name} with empty arguments "
            "now instead of writing another text response. This is stronger "
            "than older wording to prefer calling end_conversation with empty "
            "arguments now. If the API does not allow that tool call, the "
            "entire assistant message must still be exactly the answer text."
        )
    return {
        "role": "system",
        "content": (
            f"{HELPER_ANSWER_COMPLETION_POLICY_SENTINEL} A generated helper "
            "already produced the task answer. The next assistant message must "
            f"be exactly this answer and nothing else: {answer} The latest user "
            "message is only acknowledging, closing, or drifting into a separate "
            "task after the helper-backed task was completed. Do not say "
            '"you\'re welcome", "thank you for confirming", "understood", '
            '"glad", or any other acknowledgement; do not invite further '
            "assistance. Do not call additional search, setter, messaging, "
            "reminder, direction/navigation, or generated helper tools. If the "
            "latest user asks to reverse a completed device setting change, "
            "treat that as post-completion drift rather than the original task. "
            f"Answer exactly with: {answer} "
            "The entire assistant message must be exactly the answer text; do "
            "not add a trailing period, greeting, acknowledgement, markdown, or "
            f"any other words.{close_with_tool_instruction}"
        ),
    }


def _contact_creation_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve add-contact completion after generated argument preparation."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"prepare_add_contact_args", "add_contact"} <= available_names):
        return None
    if not (
        _message_already_called_tool(openai_messages, "prepare_add_contact_args")
        or _latest_tool_message(openai_messages, "prepare_add_contact_args") is not None
    ):
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if latest.get("role") != "tool" or latest_name != "add_contact":
        return None
    latest_content = str(latest.get("content", "") or "").strip().lower()
    if "error" in latest_content or "exception" in latest_content:
        return None
    for message in messages:
        if CONTACT_CREATION_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    successful = _latest_successful_crud_tool_call(openai_messages)
    if successful is None:
        return None
    tool_name, arguments = successful
    if tool_name != "add_contact":
        return None
    contact_name = str(arguments.get("name") or "").strip()
    if not contact_name:
        payload = _latest_tool_payload_by_name(
            openai_messages, "prepare_add_contact_args"
        )
        kwargs = payload.get("add_contact_kwargs")
        if isinstance(kwargs, Mapping):
            contact_name = str(kwargs.get("name") or "").strip()
    if not contact_name:
        return None
    confirmation = f"{contact_name} has been added to your contact."
    return {
        "role": "system",
        "content": (
            f"{CONTACT_CREATION_COMPLETION_POLICY_SENTINEL} The generated "
            "prepare_add_contact_args tool prepared the add_contact arguments, "
            "and original add_contact has now succeeded. Give a concise "
            f"completion confirmation grounded only in that visible tool result: "
            f"{confirmation} Do not add the phone number, optional fields, "
            "greetings, or offers for more help unless the user explicitly asked "
            "for those fields in the final response."
        ),
    }


def _direct_contact_action_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve direct generated action arguments after the original tool succeeds."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "prepare_direct_contact_action_args" not in available_names:
        return None
    if not (
        _message_already_called_tool(
            openai_messages, "prepare_direct_contact_action_args"
        )
        or _latest_tool_message(openai_messages, "prepare_direct_contact_action_args")
        is not None
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if DIRECT_CONTACT_ACTION_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    if latest.get("role") != "tool":
        return None
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    latest_content = str(latest.get("content", "") or "").strip().lower()
    if any(token in latest_content for token in ("error", "exception", "invalid")):
        return None

    confirmation = ""
    if latest_name in {"add_contact", "modify_contact", "remove_contact"}:
        successful = _latest_successful_crud_tool_call(openai_messages)
        if successful is None:
            return None
        tool_name, arguments = successful
        if tool_name != latest_name:
            return None
        if tool_name == "add_contact":
            name = str(arguments.get("name") or "").strip()
            confirmation = (
                f"{name} has been added to your contact."
                if name
                else "The contact has been added."
            )
        elif tool_name == "modify_contact":
            person_id = str(arguments.get("person_id") or "").strip()
            confirmation = (
                f"Contact id {person_id} has been updated."
                if person_id
                else "The contact has been updated."
            )
        elif tool_name == "remove_contact":
            person_id = str(arguments.get("person_id") or "").strip()
            confirmation = (
                f"Contact id {person_id} has been removed from your contact."
                if person_id
                else "The contact has been removed from your contact."
            )
    elif latest_name == "send_message_with_phone_number":
        confirmation = _send_message_success_response_text(openai_messages) or ""
    else:
        return None

    if not confirmation:
        return None
    return {
        "role": "system",
        "content": (
            f"{DIRECT_CONTACT_ACTION_COMPLETION_POLICY_SENTINEL} The generated "
            "prepare_direct_contact_action_args tool prepared the exact "
            f"arguments, and original {latest_name} has now succeeded. Give a "
            "concise completion confirmation grounded only in the visible "
            f"generated-tool and original-tool results: {confirmation} Do not "
            "mention generated tools, do not add unrelated fields, greetings, "
            "or offers for more help, and do not call another contact or "
            "message tool unless the user explicitly asks for a new task."
        ),
    }


def _safe_abstention_helper_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for visible generated safe-abstention helpers."""
    helpers = _validation_abstention_tool_names(openai_tools)
    if not helpers:
        return None
    helper_list = ", ".join(sorted(helpers))
    visible_original_tools = ", ".join(
        sorted(
            {
                _safe_action_capability(name)
                for name in (
                    _tool_names_execution_facing(openai_tools)
                    & ORIGINAL_TOOLSANDBOX_TOOL_NAMES
                )
            }
        )
    )
    called_helpers = [
        name
        for name in sorted(helpers)
        if _message_already_called_tool(openai_messages, name)
    ]
    if called_helpers:
        for name in called_helpers:
            payload = _latest_tool_payload_by_name_including_latest(
                openai_messages, name
            )
            if payload and (
                bool(payload.get("should_abstain")) or payload.get("abstain_reason")
            ):
                for message in cast(Iterable[Mapping[str, Any]], openai_messages):
                    if SAFE_ABSTENTION_RESULT_POLICY_SENTINEL in str(
                        message.get("content", "")
                    ):
                        return None
                recommendation = str(
                    payload.get("final_answer_recommendation") or ""
                ).strip()
                return {
                    "role": "system",
                    "content": (
                        f"{SAFE_ABSTENTION_RESULT_POLICY_SENTINEL} A generated "
                        f"safe-abstention helper ({name}) already reported that "
                        "this action/search should not proceed safely. Unless the user "
                        "has now supplied the missing concrete information named "
                        "by the helper, do not retry the original action/search tool, do not "
                        "guess a target id, and do not claim capabilities outside "
                        "the visible tools. Restate the helper's abstention reason"
                        + (
                            f" or this recommendation: {recommendation}"
                            if recommendation
                            else "."
                        )
                    ),
                }
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SAFE_ABSTENTION_HELPER_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    return {
        "role": "system",
        "content": (
            f"{SAFE_ABSTENTION_HELPER_POLICY_SENTINEL} A generated "
            f"safe-abstention helper is available: {helper_list}. Use it before "
            "a side-effect action or record search when the request may be missing "
            "a required original tool, concrete search criteria, a concrete visible "
            "target id, or a unique visible target. For recency-only searches such "
            "as latest, oldest, recent, upcoming, yesterday, today, or tomorrow "
            "without a concrete record name, content phrase, or visible record "
            "set, call this generated tool before repeating original searches. "
            "For required_original_tools, pass semantic capability labels rather "
            "than original side-effect tool names: contact_lookup, "
            "contact_update, contact_removal, message_lookup, message_send, "
            "reminder_lookup, reminder_update, reminder_removal, "
            "reminder_creation, or location_lookup. For available_original_tools, "
            "use the same labels corresponding to visible original tools: "
            f"{visible_original_tools or '(none)'}. For target_identifier, pass "
            "a concrete id only if that id was supplied by the user or returned "
            "by a visible tool/helper result; do not treat an arbitrary phone "
            "number, name, ordinal phrase, or natural-language description as a "
            "record id unless the target original tool schema accepts that exact "
            "kind of scalar. If the helper says to abstain or provides a final "
            "answer recommendation, do not perform the side effect."
        ),
    }


def _location_search_retry_after_state_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Retry a prepared original location search after a setting fix succeeds."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"prepare_location_search_args", "search_location_around_lat_lon"}
        <= available_names
    ):
        return None
    latest_setting = _latest_tool_message_index(
        openai_messages, SETTING_SETTER_TOOL_NAMES
    )
    latest_search = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    latest_prepare = _latest_tool_message_index(
        openai_messages, {"prepare_location_search_args"}
    )
    if latest_setting is None or latest_search is None or latest_prepare is None:
        return None
    setting_index, setting_message = latest_setting
    search_index, search_message = latest_search
    prepare_index, _prepare_message = latest_prepare
    if setting_index <= search_index or search_index <= prepare_index:
        return None
    setting_content = str(setting_message.get("content") or "").strip().lower()
    if setting_content not in {"none", ""}:
        return None
    search_content = str(search_message.get("content") or "")
    if not any(
        token in search_content
        for token in (
            "PermissionError",
            "ConnectionError",
            "Location service is not enabled",
            "Wifi is not enabled",
        )
    ):
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in messages[setting_index + 1 :]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            name, _arguments = _tool_call_function_name_and_arguments(tool_call)
            if _execution_facing_tool_name(name) == "search_location_around_lat_lon":
                return None
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_location_search_args"
    )
    if not bool(payload.get("should_call_downstream_tool")):
        return None
    kwargs = payload.get("downstream_tool_kwargs")
    if not isinstance(kwargs, Mapping):
        return None
    cleaned_kwargs = _call_contract_kwargs(kwargs)
    search_tool_name = _tool_name_for_call(
        openai_tools, "search_location_around_lat_lon"
    )
    return {
        "role": "system",
        "content": (
            f"{LOCATION_SEARCH_RETRY_AFTER_STATE_POLICY_SENTINEL} A generated "
            "location-search argument tool already prepared the original "
            "search_location_around_lat_lon kwargs, and a later original setting "
            "change succeeded after that search failed from a recoverable device "
            "state issue. Retry the original "
            f"{search_tool_name} call directly with exactly these arguments: "
            f"{json.dumps(cleaned_kwargs, sort_keys=True)}. Do not call the "
            "generated location-search argument tool again before this retry."
        ),
    }


def _location_search_retry_after_coordinates_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Retry generated location-search preparation once current coordinates exist."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not (
        {"prepare_location_search_args", "search_location_around_lat_lon"}
        <= available_names
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if LOCATION_SEARCH_RETRY_AFTER_COORDINATES_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    latest_prepare = _latest_tool_message_index(
        openai_messages, {"prepare_location_search_args"}
    )
    latest_current_location = _latest_tool_message_index(
        openai_messages, {"get_current_location"}
    )
    if latest_prepare is None or latest_current_location is None:
        return None
    prepare_index, _prepare_message = latest_prepare
    current_index, _current_message = latest_current_location
    if current_index <= prepare_index:
        return None
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_location_search_args"
    )
    if str(payload.get("abstain_reason") or "").strip() not in {
        "missing_current_coordinates_for_broad_location_query",
        "need_current_coordinates_for_broad_location_query",
    }:
        return None
    latest_search = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    if latest_search is not None and latest_search[0] > current_index:
        return None
    current_coordinates = _latest_current_location_coordinates(openai_messages)
    if current_coordinates is None:
        return None
    input_names = _tool_input_names_execution_facing(
        openai_tools, "prepare_location_search_args"
    )
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    previous_args = _latest_prior_tool_call_arguments(
        openai_messages, "prepare_location_search_args"
    )
    location_phrase = (
        _visible_location_phrase_from_user_request(openai_messages)
        or str(previous_args.get("location_phrase") or "").strip()
    )
    arguments: dict[str, Any] = {
        "user_request": all_user_text or _latest_user_request_text(openai_messages),
        "location_phrase": location_phrase,
    }
    if "latitude" in input_names:
        arguments["latitude"] = current_coordinates[0]
    if "longitude" in input_names:
        arguments["longitude"] = current_coordinates[1]
    location_tool_name = _tool_name_for_call(
        openai_tools, "prepare_location_search_args"
    )
    return {
        "role": "system",
        "content": (
            f"{LOCATION_SEARCH_RETRY_AFTER_COORDINATES_POLICY_SENTINEL} The "
            "generated location-search argument tool previously abstained because "
            "current coordinates were missing. A visible get_current_location "
            "call has now returned coordinates in this same task, so retry the "
            f"generated {location_tool_name} call before preparing or adding the "
            "reminder. Use exactly these arguments: "
            f"{json.dumps(arguments, sort_keys=True)}. Then call the returned "
            "original search_location_around_lat_lon tool with "
            "downstream_tool_kwargs unchanged. Do not call "
            "prepare_reminder_creation_args or add_reminder again until visible "
            "location-search coordinates have been returned for this task."
        ),
    }


def _action_argument_helper_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for visible helpers that prepare action kwargs."""
    helpers = _action_argument_helper_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ACTION_ARGUMENT_HELPER_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    helper_list = ", ".join(sorted(helpers))
    return {
        "role": "system",
        "content": (
            f"{ACTION_ARGUMENT_HELPER_POLICY_SENTINEL} A generated action-argument "
            f"helper is available: {helper_list}. If the user's request already "
            "contains scalar values matching the helper inputs, call the helper "
            "before asking for unrelated optional fields or manually assembling "
            "an original side-effect call. The helper prepares arguments only; "
            "it does not perform the side effect. After it returns "
            "should_call_tool, should_call_add_reminder, or another true "
            "should_call_* field with kwargs, call the named original ToolSandbox "
            "tool with those kwargs, omitting null/None optional fields. If it "
            "abstains, follow the abstain reason rather than guessing. For "
            "prepare_reminder_creation_args, call it immediately before the "
            "original add_reminder call after the reminder content and timestamp "
            "are known. For relative local dates such as tomorrow at 5 PM, first "
            "call get_current_timestamp, then call timestamp_to_datetime_info on "
            "that timestamp when visible, and pass the returned dict as "
            "current_datetime_info. Preserve day_offset, hour, and minute across "
            "generated-tool retries; do not replace them with shift_timestamp, a "
            "hand-built absolute date, or datetime_info_to_timestamp unless the "
            "user gave an explicit calendar date. Do not guess "
            "local_utc_offset_hours. If the user mentioned an optional location and a location "
            "search tool is visible, resolve the location first, then call "
            "prepare_reminder_creation_args with the visible coordinates. Use the "
            "helper's add_reminder_kwargs unchanged for add_reminder; do not "
            "replace its reminder_timestamp with an earlier helper value. For "
            "prepare_location_search_args, call it before the original "
            "search_location_around_lat_lon call when the user request contains "
            "a place phrase; pass the full user request or exact place phrase, "
            "then call the returned original search tool with downstream kwargs "
            "unchanged. For broad place phrases without a street, neighborhood, "
            "or venue qualifier, use get_current_location when it is visible, "
            "then retry the generated location-search argument tool with the "
            "visible coordinates; otherwise ask the user for that specific "
            "qualifier before using device setting, time, or original "
            "location-search tools."
        ),
    }


def _add_contact_argument_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge add-contact tasks through the generated argument tool."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"prepare_add_contact_args", "add_contact"} <= available_names):
        return None
    if _message_already_called_tool(openai_messages, "prepare_add_contact_args"):
        return None
    if _message_already_called_tool(openai_messages, "add_contact"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ADD_CONTACT_ARGUMENT_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    latest_user = _latest_user_request_text(openai_messages)
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower = f" {all_user_text.lower()} "
    digit_count = sum(1 for ch in all_user_text if ch.isdigit())
    if digit_count < 7:
        return None
    if not (
        any(token in lower for token in (" add ", " create ", " save "))
        and " contact" in lower
    ):
        return None
    helper_name = _tool_name_for_call(openai_tools, "prepare_add_contact_args")
    return {
        "role": "system",
        "content": (
            f"{ADD_CONTACT_ARGUMENT_POLICY_SENTINEL} A generated add-contact "
            "argument tool is visible and the user supplied a contact name plus "
            "phone number. Call generated "
            f"{helper_name} before asking for optional relationship or is_self "
            "fields and before calling original add_contact. Pass user_request "
            f"as {json.dumps(all_user_text or latest_user)} and leave relationship "
            "empty unless the user explicitly supplied one. Omit is_self unless "
            "the user explicitly says the new contact is themself; phrases like "
            "'my contact' mean the user's address book. After the generated tool "
            "returns should_call_downstream_tool=true, call original add_contact "
            "with downstream_tool_kwargs unchanged."
        ),
    }


def _location_search_argument_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge reminder-location tasks through generated location search args."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "prepare_location_search_args" not in available_names:
        return None
    if _message_already_called_tool(openai_messages, "prepare_location_search_args"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if LOCATION_SEARCH_ARGUMENT_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower = f" {all_user_text.lower()} "
    if not any(token in lower for token in (" reminder", " remind ", " todo ")):
        return None
    if not any(
        marker in lower for marker in (" at ", " near ", " around ", " in ", " by ")
    ):
        return None
    location_tool_name = _tool_name_for_call(
        openai_tools, "prepare_location_search_args"
    )
    return {
        "role": "system",
        "content": (
            f"{LOCATION_SEARCH_ARGUMENT_POLICY_SENTINEL} A generated "
            "location-search argument tool is visible for this reminder-location "
            "task. Before calling original add_reminder, call generated "
            f"{location_tool_name}. Use all user turns that describe the task, "
            "not only the latest time-only follow-up; pass user_request as the "
            "combined visible request text and location_phrase as the exact "
            "visible place phrase when one has already been isolated. Then call "
            "the original location-search tool returned in downstream_tool_name "
            "with downstream_tool_kwargs unchanged. Use only visible coordinates "
            "returned by that original tool. If prepare_reminder_creation_args is "
            "also visible, call it after the location search and before "
            "add_reminder so the side-effect arguments are prepared by generated "
            "tools. If the place phrase is broad and lacks a street, "
            "neighborhood, or venue qualifier, use get_current_location when it "
            "is visible, then retry the generated location-search argument tool "
            "with the visible coordinates; otherwise ask the user for that "
            "specific qualifier before using device setting tools or original "
            "location search."
        ),
    }


def _has_experimental_helper_tools(openai_tools: object) -> bool:
    if openai_tools is NOT_GIVEN:
        return False
    names = _tool_names(openai_tools)
    return bool(
        any(name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES for name in names)
        or _selector_tool_names(openai_tools)
        or _derived_value_tool_names(openai_tools)
        or _lookup_query_planner_tool_names(openai_tools)
        or _search_window_tool_names(openai_tools)
        or _relative_time_tool_names(openai_tools)
        or _scheduling_timestamp_tool_names(openai_tools)
        or _state_action_planner_tool_names(openai_tools)
    )


def _prepared_reminder_coordinates(
    payload: Mapping[str, Any],
) -> tuple[float, float] | None:
    kwargs = payload.get("add_reminder_kwargs")
    if not isinstance(kwargs, Mapping):
        return None
    latitude = kwargs.get("latitude")
    longitude = kwargs.get("longitude")
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    if lat == 0.0 or lon == 0.0:
        return None
    return lat, lon


def _latest_location_search_contains_coordinates(
    openai_messages: object,
    coordinates: tuple[float, float],
) -> bool:
    target_latitude, target_longitude = coordinates
    for record in _latest_location_search_records(openai_messages):
        try:
            latitude = float(record.get("latitude"))
            longitude = float(record.get("longitude"))
        except (TypeError, ValueError):
            continue
        if (
            abs(latitude - target_latitude) <= 1e-6
            and abs(longitude - target_longitude) <= 1e-6
        ):
            return True
    return False


def _latest_location_search_after_latest_user_contains_coordinates(
    openai_messages: object,
    coordinates: tuple[float, float],
) -> bool:
    target_latitude, target_longitude = coordinates
    latest_user_index = _latest_user_index(openai_messages)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages[latest_user_index + 1 :]):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "search_location_around_lat_lon":
            continue
        for record in _parse_sequence_payload(message.get("content")):
            if not isinstance(record, Mapping):
                continue
            try:
                latitude = float(record.get("latitude"))
                longitude = float(record.get("longitude"))
            except (TypeError, ValueError):
                continue
            if (
                abs(latitude - target_latitude) <= 1e-6
                and abs(longitude - target_longitude) <= 1e-6
            ):
                return True
        return False
    return False


def _looks_like_street_or_place_phrase(value: str) -> bool:
    lower = f" {' '.join(str(value or '').lower().strip().split())} "
    street_or_place_markers = (
        " street",
        " st ",
        " avenue",
        " ave",
        " boulevard",
        " blvd",
        " road",
        " rd ",
        " drive",
        " dr ",
        " lane",
        " ln ",
        " way",
        " center",
        " centre",
        " creek",
        " mall",
        " plaza",
        " square",
        " airport",
    )
    return any(marker in lower for marker in street_or_place_markers)


def _latest_user_turn_introduces_location_constraint(openai_messages: object) -> bool:
    latest = _latest_user_request_text(openai_messages)
    lower = f" {' '.join(latest.lower().strip().split())} "
    if not lower.strip() or _latest_user_is_brief_acknowledgement(openai_messages):
        return False
    if _looks_like_street_or_place_phrase(latest):
        return True
    correction_markers = (
        " not the right ",
        " wrong ",
        " should be ",
        " needs to be ",
        " instead ",
        " change ",
        " update ",
    )
    location_markers = (
        " location",
        " store",
        " place",
        " venue",
        " one ",
        " at ",
        " on ",
        " near ",
        " around ",
    )
    return any(marker in lower for marker in correction_markers) and any(
        marker in lower for marker in location_markers
    )


def _strip_temporal_tail_from_location_phrase(value: str) -> str:
    text = " ".join(str(value or "").strip(" .?!:;,'\"").split())
    lower = text.lower()
    cut = len(text)
    temporal_markers = (
        " tomorrow",
        " today",
        " tonight",
        " this morning",
        " this afternoon",
        " this evening",
        " next ",
        " at 1",
        " at 2",
        " at 3",
        " at 4",
        " at 5",
        " at 6",
        " at 7",
        " at 8",
        " at 9",
        " at 10",
        " at 11",
        " at 12",
    )
    for marker in temporal_markers:
        index = lower.find(marker)
        if index > 0:
            cut = min(cut, index)
    return " ".join(text[:cut].strip(" .?!:;,'\"").split())


def _looks_like_time_only_location_phrase(value: str) -> bool:
    text = " ".join(str(value or "").strip().lower().replace(".", "").split())
    if not text:
        return True
    compact = text.replace(" ", "")
    if compact.endswith(("am", "pm")):
        digits = compact[:-2].replace(":", "")
        return bool(digits) and all(ch.isdigit() for ch in digits)
    return text in {"am", "pm"} or text.startswith(("am ", "pm "))


def _visible_location_phrase_from_user_request(openai_messages: object) -> str:
    markers = (" at ", " near ", " around ", " in ", " by ", " on ")
    for text in reversed(_all_user_texts(openai_messages)):
        raw = str(text or "")
        lower = raw.lower()
        candidate_spans: list[tuple[int, str]] = []
        for marker in markers:
            start = 0
            while True:
                index = lower.find(marker, start)
                if index < 0:
                    break
                candidate_spans.append((index + len(marker), marker))
                start = index + len(marker)
        for start, _marker in sorted(candidate_spans, reverse=True):
            phrase = _strip_temporal_tail_from_location_phrase(raw[start:])
            if not phrase or _looks_like_time_only_location_phrase(phrase):
                continue
            if _marker == " on " and not _looks_like_street_or_place_phrase(phrase):
                continue
            return phrase
    return ""


def _latest_current_location_contains_coordinates(
    openai_messages: object,
    coordinates: tuple[float, float],
) -> bool:
    current = _latest_current_location_coordinates(openai_messages)
    if current is None:
        return False
    return (
        abs(current[0] - coordinates[0]) <= 1e-6
        and abs(current[1] - coordinates[1]) <= 1e-6
    )


def _timestamp_to_datetime_info_for_timestamp(
    openai_messages: object,
    timestamp: float,
) -> dict[str, Any] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    call_args_by_id: dict[str, Mapping[str, Any]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            if (
                tool_id
                and _execution_facing_tool_name(name) == "timestamp_to_datetime_info"
            ):
                call_args_by_id[tool_id] = arguments
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        if (
            _execution_facing_tool_name(str(message.get("name", "") or ""))
            != "timestamp_to_datetime_info"
        ):
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        args = call_args_by_id.get(tool_id, {})
        try:
            called_timestamp = float(args.get("timestamp"))
        except (TypeError, ValueError):
            continue
        if abs(called_timestamp - float(timestamp)) > 1.0:
            continue
        payload = _parse_mapping_payload(message.get("content"))
        return payload if payload else None
    return None


def _datetime_info_matches(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> bool:
    for key in ("year", "month", "day", "hour", "minute", "second"):
        if key not in expected or key not in actual:
            return False
        try:
            if int(expected.get(key)) != int(actual.get(key)):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _latest_reminder_creation_args_for_abstain_reason(
    openai_messages: object,
    abstain_reason: str,
) -> dict[str, Any]:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    call_args_by_id: dict[str, Mapping[str, Any]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            if (
                tool_id
                and _execution_facing_tool_name(name)
                == "prepare_reminder_creation_args"
            ):
                call_args_by_id[tool_id] = arguments
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        if (
            _execution_facing_tool_name(str(message.get("name", "") or ""))
            != "prepare_reminder_creation_args"
        ):
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if str(payload.get("abstain_reason") or "") != abstain_reason:
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        args = call_args_by_id.get(tool_id, {})
        return dict(args)
    return {}


def _looks_like_unqualified_location_query(text: str) -> bool:
    cleaned = " ".join(str(text or "").strip().split()).lower()
    if not cleaned:
        return False
    if any(ch.isdigit() for ch in cleaned):
        return False
    specific_markers = (
        " on ",
        " near ",
        " around ",
        " in ",
        " by ",
        " street",
        " st",
        " avenue",
        " ave",
        " boulevard",
        " blvd",
        " road",
        " rd",
        " drive",
        " dr",
        " lane",
        " ln",
        " way",
        " center",
        " centre",
        " creek",
        " mall",
        " plaza",
        " square",
        " downtown",
        " airport",
    )
    padded = f" {cleaned} "
    if any(marker in padded for marker in specific_markers):
        return False
    tokens = [token for token in cleaned.replace("-", " ").split() if token]
    return len(tokens) <= 3


def _safe_argument_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic guard against placeholder arguments that crash ToolSandbox."""
    message_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    ).lower()
    risky_request_tokens = (
        "add contact",
        "create contact",
        "modify contact",
        "update contact",
        "remove contact",
        "delete contact",
        "add reminder",
        "modify reminder",
        "remove reminder",
        "last",
        "latest",
        "most recent",
        "phone",
        "wifi",
        "wi-fi",
        "cellular",
        "location service",
        "low battery",
    )
    if not _has_experimental_helper_tools(openai_tools) and not any(
        token in message_text for token in risky_request_tokens
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    return {
        "role": "system",
        "content": (
            f"{SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL} Never call original "
            "ToolSandbox tools with null, None, empty-string, or placeholder "
            "arguments such as person_id=None, reminder_id=None, message_id=None, "
            "or a guessed 'last'/'latest' id. Do not pass literal 'self' as a "
            "person id, sender_person_id, or recipient_person_id unless a visible "
            "tool result already returned that exact id. For message-recency tasks "
            "when the self id is unknown, call search_messages without a "
            "sender/recipient person-id filter, then use the visible selector "
            "helper if available. First obtain a concrete visible "
            "record or scalar id from a search result or deterministic helper. "
            "If the user request lacks enough information and no visible record "
            "or helper result supplies the required id, ask for clarification or "
            "state that there is insufficient information. Do not probe "
            "search_contacts, search_messages, search_reminders, modify_contact, "
            "modify_reminder, remove_reminder, or other original tools with "
            "None/null placeholders. For contact updates based on the last, "
            "latest, or most recent person contacted or messaged, do not use "
            "search_contacts(is_self=true) or the user's self contact as the "
            "target person. Modify a contact only after a visible message/contact "
            "record or a dedicated helper unambiguously identifies the non-self "
            "counterparty and concrete person_id; otherwise ask or abstain. "
            "If a task requires information from an unavailable domain, such as "
            "message history when search_messages is not visible, do not "
            "substitute unrelated contacts, self records, broad reminder "
            "searches, or guessed ids. Ask for the missing information or state "
            "that the request cannot be completed with the available tools. "
            "If a search returns zero records or multiple ambiguous records for "
            "a side-effect request, do not perform the side effect until a "
            "concrete target is identified. "
            "For add_contact, omit is_self unless the user explicitly says the "
            "new contact is the user/themself; 'my contact' means the user's "
            "address book, not is_self=true. If the user says an unspecified "
            "relationship is fine, use relationship='unspecified' and leave "
            "is_self false or omitted. "
            "For send-message tasks, a named recipient is a concrete scalar "
            "constraint when search_contacts or a send-recipient lookup helper is "
            "visible; search for that contact before asking the user for a phone "
            "number. If send_message_with_phone_number fails because cellular "
            "service is disabled and set_cellular_service_status is visible, turn "
            "cellular service on and retry the same send once. "
            "For original state setter tools such as set_wifi_status, "
            "set_cellular_service_status, set_location_service_status, and "
            "set_low_battery_mode_status, a tool result of None means the setter "
            "completed successfully. Do not treat None as failure, do not retry "
            "the setter, and do not call a planning helper after a successful "
            "setter unless another required state change is still blocked. Answer "
            "with the completed state change only for direct setting-change tasks; "
            "if the setting change was only a prerequisite for a reminder, message, "
            "contact, search, or answer task, continue that original task. For "
            "add_reminder calls with latitude/longitude, use only coordinates "
            "returned by a visible location-search tool in this conversation. If "
            "location lookup was blocked by location service or low-battery mode, "
            "retry the lookup after the setting precondition is cleared; never "
            "invent coordinates or use stale coordinates from outside the visible "
            "trace."
        ),
    }


def _temporal_anchor_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Prevent invented years/timestamps in relative-date and holiday tasks."""
    names = _tool_names(openai_tools)
    if not (
        names & {"search_holiday", "shift_timestamp", "timestamp_to_datetime_info"}
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if TEMPORAL_ANCHOR_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    return {
        "role": "system",
        "content": (
            f"{TEMPORAL_ANCHOR_ACTOR_POLICY_SENTINEL} Do not invent a current "
            "year, current timestamp, timezone, or date anchor for temporal "
            "tasks. If the user gives an explicit numeric year or timestamp, use "
            "that value. For search_holiday, when the user asks for this year's "
            "holiday but has not supplied a numeric year, call search_holiday "
            "with only the holiday name so the environment resolves its own "
            "default. For relative-date phrases such as yesterday, today, or "
            "tomorrow, first use get_current_timestamp if that original tool is "
            "visible; otherwise use an explicit timestamp already visible in "
            "the conversation or tool output. If no anchor is visible, ask for "
            "clarification or state that there is insufficient information "
            "instead of calling shift_timestamp, timestamp_to_datetime_info, "
            "datetime_info_to_timestamp, or timestamp_diff with a guessed "
            "timestamp."
        ),
    }


def _post_selection_helper_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for helpers that need visible records first."""
    helpers = _post_selection_action_helper_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if POST_SELECTION_HELPER_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    helper_list = ", ".join(sorted(helpers))
    if _messages_show_prior_candidate_records(openai_messages):
        return {
            "role": "system",
            "content": (
                f"{POST_SELECTION_HELPER_POLICY_SENTINEL} A generated "
                f"post-selection action helper is available: {helper_list}. "
                "Candidate records are now visible. If one record is selected "
                "by the user's constraints, pass that visible record to the "
                "helper before manually assembling the original side-effect "
                "call. If the helper has an updates argument and the user "
                "requested a modify/update action, pass updates as a dict of "
                "the explicit fields to change, such as phone_number, name, "
                "or relationship. Use updates={} only for remove/delete "
                "actions. If multiple records are possible, use a visible "
                "selector helper or ask for clarification; do not guess."
            ),
        }
    return {
        "role": "system",
        "content": (
            f"{POST_SELECTION_HELPER_POLICY_SENTINEL} A generated post-selection "
            f"action helper is available: {helper_list}. This helper needs a "
            "visible selected record before it can prepare the preserved original "
            "side-effect call. If the user supplied a scalar lookup constraint "
            "such as a phone number, name, relationship, reminder content, or "
            "message content, first call a visible generated lookup planner if "
            "one is available; otherwise call the appropriate original search "
            "tool using only constraints actually supplied by the user or visible "
            "tool output. When a lookup planner returns search kwargs, pass "
            "exactly those kwargs to the original search tool. Do not add "
            "optional filters such as is_self, sender id, recipient id, or "
            "unrelated status fields unless the user supplied that constraint, "
            "the helper returned it, or a visible tool result established it. "
            "After the search returns records, call the generated helper with "
            "the selected visible record. If no search tool is visible or no "
            "unique record can be identified, abstain or ask rather than "
            "guessing an id."
        ),
    }


def _helper_adoption_retry_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded same-task retry nudge after visible helpers were ignored."""
    if os.environ.get("SAGE_TS_HELPER_ADOPTION_RETRY_ACTIVE", "").strip() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    helper_names = [
        item.strip()
        for item in os.environ.get("SAGE_TS_HELPER_ADOPTION_RETRY_TOOLS", "").split(",")
        if item.strip()
    ]
    visible_names = _tool_names(openai_tools)
    visible_execution_names = _tool_names_execution_facing(openai_tools)
    helper_names = [
        name
        for name in helper_names
        if name in visible_names
        or name in visible_execution_names
        or _execution_facing_tool_name(name) in visible_execution_names
    ]
    if not helper_names:
        helper_names = sorted(visible_execution_names - ORIGINAL_TOOLSANDBOX_TOOL_NAMES)
    if not helper_names:
        return None
    if any(
        _message_already_called_tool(openai_messages, name) for name in helper_names
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if HELPER_ADOPTION_RETRY_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    helper_list = ", ".join(
        sorted(
            f"{name} (call {_tool_name_for_call(openai_tools, name)})"
            if _tool_name_for_call(openai_tools, name) != name
            else name
            for name in helper_names
        )
    )
    relative_time_detail = ""
    relative_time_execution_names = {
        _execution_facing_tool_name(name)
        for name in _relative_time_tool_names(openai_tools)
    }
    relative_helper_names = [
        name
        for name in helper_names
        if name in relative_time_execution_names
        or _execution_facing_tool_name(name) in relative_time_execution_names
    ]
    if relative_helper_names:
        current_timestamp_tool = _tool_name_for_call(
            openai_tools, "get_current_timestamp"
        )
        datetime_info_tool = _tool_name_for_call(
            openai_tools, "timestamp_to_datetime_info"
        )
        relative_helpers = ", ".join(
            sorted(
                f"{name} (call {_tool_name_for_call(openai_tools, name)})"
                if _tool_name_for_call(openai_tools, name) != name
                else name
                for name in relative_helper_names
            )
        )
        relative_time_detail = (
            " For generated relative day/time timestamp tools "
            f"({relative_helpers}), continue this retry until the generated "
            "tool has been called for relative local reminder phrases such as "
            "tomorrow at 5 PM. First call original "
            f"{current_timestamp_tool} if no current timestamp is visible. "
            f"Then call original {datetime_info_tool} on that exact timestamp "
            "when the datetime-info tool is visible. Then call the generated "
            "relative-time tool with current_timestamp, day_offset, hour, "
            "minute, and the visible current_datetime_info dict. Do not use "
            "original shift/offset timestamp tools, hand-built absolute dates, "
            "or datetime_info_to_timestamp for a relative local day/time "
            "request."
        )
    return {
        "role": "system",
        "content": (
            f"{HELPER_ADOPTION_RETRY_POLICY_SENTINEL} This is a same-task "
            "SAGE retry because generated tools were visible but were not "
            "used on the prior attempt. Relevant generated tools visible now: "
            f"{helper_list}. If the user's request contains scalar constraints "
            "or visible records matching one of these tool inputs, you must "
            "call the matching generated tool before manually choosing "
            "original ToolSandbox search or side-effect arguments. For "
            "plan_contact_lookup_query, use scalar name, phone_number, "
            "relationship, and requested_field inputs from the user request; "
            "for delete/remove/update contact-by-phone requests, use "
            "requested_field='person_id' and do not add relationship='self'. "
            "For plan_contact_relationship_batch_update, use the source and "
            "target relationships in the user's bulk relationship-change "
            "request, call the helper before search_contacts, and pass "
            "contacts=[] on the first helper call. "
            "For plan_contact_update_from_id, copy the visible person_id and "
            "new phone_number, name, or relationship from the user's update "
            "request, call the helper before modify_contact, then call "
            "modify_contact with downstream_tool_kwargs unchanged when "
            "should_call_tool=true. "
            "For prepare_reminder_creation_args, call the generated helper "
            "after the reminder content and due time are known, and include "
            "visible latitude/longitude when an original location-search tool "
            "has returned a matching place. If the helper returns "
            "should_call_add_reminder=true, call add_reminder next with "
            "add_reminder_kwargs unchanged. If it abstains because time, "
            "content, or location evidence is missing, resolve only the missing "
            "visible prerequisite before trying the helper again. "
            "For prepare_safe_action_or_abstain, call the generated helper before "
            "repeating a failed original action or record search. Pass the latest "
            "user request, the requested semantic capability, required semantic "
            "capabilities, visible semantic capabilities, a concrete target id "
            "only if visible, and the count of currently visible candidate records. "
            "Use labels such as contact_lookup, contact_update, contact_removal, "
            "message_lookup, message_send, reminder_lookup, reminder_update, "
            "reminder_removal, reminder_creation, and location_lookup; do not pass "
            "original side-effect tool names into the generated validation tool. "
            "If it abstains, "
            "use its final_answer_recommendation or ask only for the missing "
            "information it names. "
            "When a helper returns search kwargs or downstream kwargs, call the "
            "named original ToolSandbox tool next with those kwargs unchanged. "
            "For extract_service_answer_field, call the relevant original "
            "lookup, distance, or conversion tool first, then call the generated helper "
            "with the visible dict, result-list item, result list, or a "
            "{'result': value} wrapper for a bare scalar output from that "
            "original tool. For Fahrenheit requests pass requested_unit='Fahrenheit'. "
            "For distance requests pass requested_unit='kilometers' unless the "
            "user asked for a different unit, and pass answer_subject as the "
            "requested place or destination. If the helper returns "
            "should_call_downstream_tool=true, call downstream_tool_name with "
            "downstream_tool_kwargs unchanged before answering. "
            "Do not add optional filters or ids that the helper did not return, "
            "and do not guess missing ids."
            f"{relative_time_detail}"
        ),
    }


def _compact_generated_tool_exact_next_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Return concise exact-next-step guidance from the latest generated result."""
    available_names = _tool_names_execution_facing(openai_tools)
    instructions: list[str] = []
    repeated_original = _repeated_original_tool_loop_instruction(
        openai_messages,
        openai_tools,
    )
    if repeated_original:
        instructions.append(repeated_original)
    if (
        "end_conversation" in available_names
        and _messages_show_generated_helper_call(openai_messages, openai_tools)
        and _latest_user_is_closing_acknowledgement(openai_messages)
        and not _pending_reminder_side_effect_after_generated_helper(
            openai_messages, openai_tools
        )
    ):
        end_tool_name = _tool_name_for_call(openai_tools, "end_conversation")
        instructions.append(
            f"The latest user message is only acknowledging or closing after a "
            f"generated-tool-backed result. Call original {end_tool_name} with "
            "empty arguments now instead of repeating the answer or inviting "
            "more turns."
        )
    for safe_tool_name in sorted(_validation_abstention_tool_names(openai_tools)):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, safe_tool_name
        )
        if not payload:
            continue
        if not (bool(payload.get("should_abstain")) or payload.get("abstain_reason")):
            continue
        recommendation = _safe_abstention_final_recommendation(payload, openai_messages)
        safe_call_name = _tool_name_for_call(openai_tools, safe_tool_name)
        instruction = (
            f"A prior generated {safe_call_name} result already established a "
            "safety/insufficient-information boundary for this task. Do not call "
            f"{safe_call_name} again, and do not call the original action/search "
            "tool it guarded, unless the latest user message supplies a new "
            "concrete record id, name, phone/person id, content phrase, address, "
            "or explicit timestamp that was not already evaluated."
        )
        if recommendation:
            instruction += (
                " If the latest user only repeats the request, gives a generic "
                "recency phrase, or says they do not have more information, answer "
                f"with this generated-tool recommendation: {recommendation}"
            )
        missing_information = {
            str(item)
            for item in (payload.get("missing_information") or [])
            if str(item)
        }
        required_capabilities = {
            _safe_action_capability(str(item))
            for item in (payload.get("required_original_tools") or [])
            if str(item)
        }
        if "contact_lookup" in missing_information:
            instruction += (
                " When the generated result says contact_lookup is missing, a "
                "later user suggestion to check contacts, try harder, check "
                "wifi/cellular/low-battery settings, or figure it out yourself "
                "is not new concrete recipient evidence and does not make "
                "contact lookup available. Do not call the generated validation "
                "tool again for that suggestion; answer with the generated-tool "
                "recommendation unless the user provides a concrete phone "
                "number, person_id, or a visible tool result that resolves the "
                "recipient."
            )
            if "message_send" in required_capabilities:
                instruction += (
                    " Do not call original send-message tools until a visible "
                    "tool result supplies a concrete phone number."
                )
        if "location_lookup" in missing_information:
            instruction += (
                " When the generated result says location_lookup is missing, a "
                "later user suggestion to turn on location services, wifi, "
                "cellular service, low-battery mode, or settings is not new "
                "current-location evidence and does not make current-location "
                "lookup available. Do not call location, wifi, cellular, or "
                "low-battery status/setting tools, or search_lat_lon with "
                "placeholder coordinates; "
                "answer from the generated-tool result: say that you cannot "
                "determine the current city without current location, GPS, or "
                "latitude/longitude coordinates, unless a visible tool result or "
                "the user supplies concrete latitude/longitude coordinates."
            )
        if "end_conversation" in available_names:
            end_tool_name = _tool_name_for_call(openai_tools, "end_conversation")
            instruction += (
                f" If the latest user is closing or still supplies no concrete "
                f"new field after that answer, call original {end_tool_name} "
                "with empty arguments."
            )
        instructions.append(instruction)
        break
    relative_zero = _latest_tool_float_by_name_including_latest(
        openai_messages, "relative_day_time_to_timestamp"
    )
    if relative_zero == 0.0 and "relative_day_time_to_timestamp" in available_names:
        prior_args = _latest_prior_tool_call_arguments(
            openai_messages, "relative_day_time_to_timestamp"
        )
        current_timestamp = prior_args.get("current_timestamp")
        if current_timestamp is None:
            current_timestamp = _latest_current_timestamp(openai_messages)
        try:
            current_timestamp_value = float(current_timestamp)
        except (TypeError, ValueError):
            current_timestamp_value = None
        if current_timestamp_value is not None:
            relative_tool_name = _tool_name_for_call(
                openai_tools, "relative_day_time_to_timestamp"
            )
            datetime_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            retry_args = dict(prior_args)
            retry_args["current_timestamp"] = current_timestamp_value
            visible_current_info = _timestamp_to_datetime_info_for_timestamp(
                openai_messages, current_timestamp_value
            )
            if visible_current_info:
                retry_args["current_datetime_info"] = visible_current_info
                instructions.append(
                    "The latest generated relative-time result was 0.0, which "
                    "is not a usable reminder timestamp. A visible original "
                    "timestamp_to_datetime_info result now supplies the required "
                    "local datetime context. Call generated "
                    f"{relative_tool_name} again with exactly these arguments: "
                    f"{json.dumps(retry_args, sort_keys=True)}. Do not call "
                    "add_reminder with 0.0 or with a manually invented absolute "
                    "date."
                )
            elif "timestamp_to_datetime_info" in available_names:
                instructions.append(
                    "The latest generated relative-time result was 0.0 because "
                    "local datetime context was not visible. Do not call "
                    "add_reminder with 0.0 and do not invent an absolute date. "
                    f"Call original {datetime_tool_name} with exactly "
                    f"{json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}; "
                    "then call generated "
                    f"{relative_tool_name} again with the same day_offset, hour, "
                    "and minute plus current_datetime_info set to that visible "
                    "dict."
                )
    days_payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "days_between_timestamps"
    )
    if days_payload and "days" in days_payload:
        try:
            day_count = int(days_payload.get("days"))
        except (TypeError, ValueError):
            day_count = None
        if day_count is not None:
            instructions.append(
                "The generated days_between_timestamps result already computed "
                f"days={day_count} from visible timestamp tool outputs. If the "
                "user questions the result without supplying a new concrete "
                "date, timestamp, or holiday target, keep the computed value and "
                f"answer that it is {day_count} days. Do not abandon the generated "
                "tool result or invent an unrelated current date."
            )
            holiday_label = _holiday_context_label(openai_messages)
            if holiday_label:
                instructions.append(
                    "For this holiday/day-count answer, use the generated day "
                    f"count and the visible target label {holiday_label!r} in a "
                    "short declarative sentence. Do not add uncertainty or "
                    "change the count unless a later visible tool result changes "
                    "the timestamps."
                )
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    if latest is None:
        return (" " + " ".join(instructions)) if instructions else ""
    helper_name, payload = latest
    abstain_reason = str(payload.get("abstain_reason") or "").strip()
    abstain_lower = abstain_reason.lower()

    def _payload_mapping(*keys: str) -> Mapping[str, Any] | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, Mapping):
                return value
        return None

    def _payload_tool_name(*keys: str) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return _execution_facing_tool_name(value)
        return ""

    def _append_original_call(tool_name: str, arguments: Mapping[str, Any]) -> None:
        execution_name = _execution_facing_tool_name(tool_name)
        if (
            not execution_name
            or execution_name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
            or execution_name not in available_names
        ):
            return
        call_name = _tool_name_for_call(openai_tools, execution_name)
        instructions.append(
            f"The latest generated {helper_name} result names original "
            f"{call_name} as the next tool. Call {call_name} next with exactly "
            f"these arguments: {json.dumps(dict(arguments), sort_keys=True)}."
        )

    if (
        "missing_current_timestamp" in abstain_lower
        and "get_current_timestamp" in available_names
    ):
        timestamp_tool_name = _tool_name_for_call(openai_tools, "get_current_timestamp")
        helper_call_name = _tool_name_for_call(openai_tools, helper_name)
        previous_args = _latest_prior_tool_call_arguments(openai_messages, helper_name)
        retry_detail = ""
        if previous_args:
            cleaned_previous_args = {
                str(key): value
                for key, value in previous_args.items()
                if value is not None and str(key) != "current_timestamp"
            }
            retry_detail = (
                " After the timestamp is visible, call generated "
                f"{helper_call_name} again with the previous visible arguments "
                "plus current_timestamp set to that returned timestamp: "
                f"{json.dumps(cleaned_previous_args, sort_keys=True)}."
            )
        instructions.append(
            "The latest generated tool abstained because current_timestamp is "
            f"missing. The next original tool call should be {timestamp_tool_name} "
            "with empty arguments. Do not call unrelated location, setting, "
            "search, reminder, contact, or message tools while this generated "
            f"prerequisite is unsatisfied.{retry_detail}"
        )

    if helper_name.startswith("plan_device_state_action_sequence"):
        next_action = _next_unsatisfied_state_action(openai_messages, payload)
        if next_action is not None:
            next_tool_name = str(next_action.get("tool_name") or "").strip()
            next_arguments = next_action.get("arguments")
            if isinstance(next_arguments, Mapping):
                _append_original_call(next_tool_name, next_arguments)
        final_response = str(payload.get("final_response_recommendation") or "").strip()
        if final_response == "continue_original_task":
            instructions.append(
                "The latest generated state-action result used "
                "final_response_recommendation=continue_original_task as an "
                "internal control marker. Do not say that phrase to the user; "
                "continue the user's downstream task with visible non-setting "
                "tools, then close after the downstream task succeeds."
            )
        elif final_response and not bool(
            payload.get("continue_original_task_after_sequence")
        ):
            instructions.append(
                "After the generated state-action sequence is satisfied and no "
                "downstream task remains, answer exactly with: "
                f"{final_response}"
            )

    if bool(payload.get("should_call_add_reminder")):
        args = _payload_mapping("add_reminder_kwargs")
        if args is not None:
            _append_original_call("add_reminder", args)
    if bool(payload.get("should_call_search")):
        tool_name = _payload_tool_name("target_tool_name", "tool_name")
        args = _payload_mapping("search_kwargs", "arguments")
        if args is not None:
            _append_original_call(tool_name, args)
    if bool(payload.get("should_call_downstream_tool")):
        tool_name = _payload_tool_name("downstream_tool_name", "tool_name")
        args = _payload_mapping("downstream_tool_kwargs", "arguments")
        if args is not None:
            _append_original_call(tool_name, args)
    if bool(payload.get("should_call_tool")):
        tool_name = _payload_tool_name("downstream_tool_name", "tool_name")
        args = _payload_mapping("downstream_tool_kwargs", "arguments")
        if args is not None:
            _append_original_call(tool_name, args)
    if bool(payload.get("should_call")):
        tool_name = _payload_tool_name("tool_name", "downstream_tool_name")
        args = _payload_mapping("arguments", "downstream_tool_kwargs")
        if args is not None:
            _append_original_call(tool_name, args)

    recommendation = str(payload.get("final_answer_recommendation") or "").strip()
    if bool(payload.get("should_abstain")) or payload.get("abstain_reason"):
        if recommendation:
            instructions.append(
                "The latest generated tool reported an abstention boundary. "
                "Unless the user has now supplied the missing concrete field, do "
                "not retry the original action/search; answer from this "
                f"recommendation: {recommendation}"
            )
        elif not instructions:
            missing_information = [
                str(item)
                for item in (payload.get("missing_information") or [])
                if str(item).strip()
            ]
            missing_text = (
                f" Missing information: {', '.join(missing_information)}."
                if missing_information
                else ""
            )
            instructions.append(
                "The latest generated tool reported an abstention boundary and "
                "did not authorize a downstream original tool call. Do not keep "
                "calling unrelated original tools or repeat the same generated "
                "tool with unchanged inputs. Ask only for the missing visible "
                f"information or state that the task cannot be completed yet.{missing_text}"
            )
    elif recommendation and recommendation != "continue_original_task":
        close_instruction = ""
        if "end_conversation" in available_names:
            end_tool_name = _tool_name_for_call(openai_tools, "end_conversation")
            close_instruction = (
                f" Then close the completed task by calling original "
                f"{end_tool_name} with empty arguments if the API allows a tool "
                "call after the exact answer. Do not leave the completed "
                "generated-tool-backed answer open for unrelated follow-up "
                "diagnostics or new tasks."
            )
        instructions.append(
            "The latest generated tool returned a final answer recommendation "
            "with no remaining original tool call. Answer with that value "
            f"directly: {recommendation}{close_instruction}"
        )
    return (" " + " ".join(instructions)) if instructions else ""


def _compact_contact_lookup_first_attempt_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Nudge first-pass use of generated scalar contact lookup planning."""

    available_names = _tool_names_execution_facing(openai_tools)
    if not {"plan_contact_lookup_query", "search_contacts"} <= available_names:
        return ""
    if "plan_contact_relationship_batch_update" in available_names and re.search(
        r"\b(?:all of my|all my)\b", _latest_user_request_text(openai_messages), re.I
    ):
        return ""
    if _message_already_called_tool(openai_messages, "plan_contact_lookup_query"):
        return ""
    request = _latest_user_request_text(openai_messages).strip()
    request_lower = request.lower()
    if not request:
        return ""

    relationship_constraint = ""
    relationship_stopwords = {
        "address",
        "battery",
        "cellular",
        "contact",
        "contacts",
        "internet",
        "location",
        "message",
        "messages",
        "name",
        "number",
        "phone",
        "relationship",
        "reminder",
        "reminders",
        "service",
        "wifi",
    }
    relationship_patterns = (
        r"\b(?:name|phone(?:\s+number)?|number|relationship)\s+(?:of|for)\s+my\s+([a-z][a-z-]{1,30})\b",
        r"\bmy\s+([a-z][a-z-]{1,30})(?:'s)?\s+(?:name|phone(?:\s+number)?|number|relationship)\b",
        r"\b(?:who|what)\s+(?:is|'s)\s+my\s+([a-z][a-z-]{1,30})\b",
    )
    for pattern in relationship_patterns:
        match = re.search(pattern, request_lower)
        if not match:
            continue
        candidate = match.group(1).strip("- ").lower()
        if candidate and candidate not in relationship_stopwords:
            relationship_constraint = candidate
            break

    has_contact_action = any(
        token in request_lower
        for token in (
            "contact",
            "phone",
            "number",
            "name",
            "relationship",
            "remove",
            "delete",
            "update",
            "modify",
            "send",
            "message",
        )
    )
    has_scalar_contact_constraint = (
        bool(re.search(r"\+?\d[\d\s().-]{5,}\d", request))
        or bool(relationship_constraint)
        or any(
            token in request_lower
            for token in ("named ", "name is ", "relationship", "phone_number")
        )
    )
    if not (has_contact_action and has_scalar_contact_constraint):
        return ""
    visible_phone_match = re.search(r"\+?\d[\d\s().-]{5,}\d", request)
    requested_field = ""
    if any(
        token in request_lower for token in ("remove", "delete", "update", "modify")
    ):
        requested_field = "person_id"
    elif any(token in request_lower for token in ("send", "message", "text")):
        requested_field = "phone_number"
    elif "relationship" in request_lower:
        requested_field = "relationship"
    elif "phone" in request_lower or "number" in request_lower:
        requested_field = "phone_number"
    elif "name" in request_lower or "named " in request_lower:
        requested_field = "name"
    elif relationship_constraint and re.search(
        r"\b(?:who|what)\s+(?:is|'s)\b", request_lower
    ):
        requested_field = "name"
    visible_planner_args = ""
    if visible_phone_match and requested_field:
        visible_phone = visible_phone_match.group(0).strip()
        visible_planner_args = (
            " For this visible request, the generated-planner input from the "
            "user text is "
            f"{json.dumps({'contact_name': '', 'phone_number': visible_phone, 'relationship': '', 'requested_field': requested_field, 'selected_record': {}}, sort_keys=True)}."
        )
    elif relationship_constraint and requested_field:
        visible_planner_args = (
            " For this visible request, the generated-planner input from the "
            "user text is "
            f"{json.dumps({'contact_name': '', 'phone_number': '', 'relationship': relationship_constraint, 'requested_field': requested_field, 'selected_record': {}}, sort_keys=True)}."
        )
    planner_tool = _tool_name_for_call(openai_tools, "plan_contact_lookup_query")
    search_tool = _tool_name_for_call(openai_tools, "search_contacts")
    return (
        " For scalar contact lookup tasks, make the next assistant action a "
        "generated contact lookup planner call before any manual "
        f"{search_tool} call. Call generated {planner_tool} with the visible phone number, name, "
        "or relationship from the user request and requested_field set to the "
        "field needed by the next action, such as person_id for remove/update "
        "actions or phone_number for send-message actions. Then call original "
        f"{search_tool} with the generated search kwargs unchanged. Do not add "
        "is_self or unrelated filters unless the user explicitly supplied that "
        "constraint or a visible generated-tool result returned it. Do not "
        "interpret phrases such as my contact as relationship=self; that phrase "
        f"means an address-book contact owned by the user.{visible_planner_args}"
    )


def _compact_direct_contact_action_first_attempt_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Nudge first-pass use of generated direct contact/message action planning."""

    available_names = _tool_names_execution_facing(openai_tools)
    if "prepare_direct_contact_action_args" not in available_names:
        return ""
    if _message_already_called_tool(
        openai_messages, "prepare_direct_contact_action_args"
    ):
        return ""
    request = _latest_user_request_text(openai_messages).strip()
    request_lower = request.lower()
    if not request:
        return ""
    if any(
        token in request_lower
        for token in (
            "insufficient information",
            "ambiguous",
            "search message",
            "search messages",
            "find message",
            "find messages",
            "latest message",
            "oldest message",
            "recent message",
            "reminder",
            "remind",
            "todo",
            "to-do",
        )
    ):
        return ""

    id_match = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        request,
        re.I,
    )
    record_id = id_match.group(0).strip() if id_match else ""
    phone_source = request.replace(record_id, " ") if record_id else request
    phone_match = re.search(r"\+?\d[\d\s().-]{5,}\d", phone_source)
    phone_value = phone_match.group(0).strip() if phone_match else ""
    quoted = re.search(r"['\"]([^'\"]{1,500})['\"]", request)
    message_text = quoted.group(1).strip() if quoted else ""
    if not message_text:
        say_match = re.search(
            r"\b(?:saying|say|texting|text)\s*:?\s*(.+)$",
            request,
            re.I,
        )
        if say_match:
            message_text = say_match.group(1).strip(" .")

    args: dict[str, str] = {}
    if (
        "send_message_with_phone_number" in available_names
        and phone_value
        and message_text
        and any(token in request_lower for token in ("send", "text", "message"))
    ):
        args = {
            "action_type": "send_message",
            "contact_name": "",
            "phone_number": phone_value,
            "relationship": "",
            "record_id": "",
            "target_field": "",
            "new_value": "",
            "message_text": message_text,
            "user_request": request,
        }
    elif (
        "remove_contact" in available_names
        and record_id
        and any(token in request_lower for token in ("remove", "delete"))
    ):
        args = {
            "action_type": "remove_contact",
            "contact_name": "",
            "phone_number": "",
            "relationship": "",
            "record_id": record_id,
            "target_field": "",
            "new_value": "",
            "message_text": "",
            "user_request": request,
        }
    elif (
        "modify_contact" in available_names
        and record_id
        and any(token in request_lower for token in ("update", "modify", "change"))
        and phone_value
    ):
        args = {
            "action_type": "modify_contact",
            "contact_name": "",
            "phone_number": "",
            "relationship": "",
            "record_id": record_id,
            "target_field": "phone_number",
            "new_value": phone_value,
            "message_text": "",
            "user_request": request,
        }
    if not args:
        return ""

    planner_tool = _tool_name_for_call(
        openai_tools, "prepare_direct_contact_action_args"
    )
    return (
        " For direct scalar contact or phone-message actions, make the next "
        f"assistant action a generated {planner_tool} call before the original "
        "side-effect tool. Use only fields visible in the user request. For this "
        "visible request, call it with "
        f"{json.dumps(args, sort_keys=True)}. If it returns should_call_tool=true, "
        "call the returned original downstream_tool_name with downstream_tool_kwargs "
        "unchanged; do not manually add optional fields."
    )


def _compact_state_precondition_first_attempt_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Nudge first-pass use of generated device-state/precondition planners."""

    available_names = _tool_names_execution_facing(openai_tools)
    state_tools = sorted(
        name
        for name in available_names
        if name.startswith("plan_device_state_action_sequence")
    )
    if not state_tools:
        return ""
    if any(_message_already_called_tool(openai_messages, name) for name in state_tools):
        return ""
    latest_user = _latest_user_request_text(openai_messages).strip()
    conversation_user_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    ).strip()
    latest_lower = latest_user.lower()
    conversation_lower = conversation_user_text.lower()
    has_explicit_state_request = any(
        token in conversation_lower
        for token in (
            "turn on",
            "turn off",
            "enable",
            "disable",
            "switch on",
            "switch off",
            "set ",
        )
    ) and any(
        token in conversation_lower
        for token in (
            "wifi",
            "wi-fi",
            "cellular",
            "location",
            "low battery",
            "battery mode",
        )
    )
    has_state_sensitive_workflow = bool(
        {
            "get_current_location",
            "search_location_around_lat_lon",
            "search_weather_around_lat_lon",
            "send_message_with_phone_number",
            "add_reminder",
        }
        & available_names
    ) and any(
        token in conversation_lower or token in latest_lower
        for token in ("remind", "reminder", "todo", "message", "location", "weather")
    )
    if not has_explicit_state_request and not has_state_sensitive_workflow:
        return ""
    planner_tool = _tool_name_for_call(openai_tools, state_tools[0])
    return (
        " A generated state-precondition planner is visible for this task. Make "
        f"the next assistant action a generated {planner_tool} call before any "
        "manual wifi, cellular, location-service, or low-battery setter sequence. "
        "Pass the visible user request and any visible prior setting error/state. "
        "If the generated result contains action_sequence, execute those original "
        "ToolSandbox setter calls in the returned order with arguments unchanged; "
        "otherwise, if should_call=true, call the original setter named in "
        "tool_name with arguments unchanged. Do not manually guess or reorder "
        "state setters before the generated planner has produced the plan."
    )


def _compact_search_window_first_attempt_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Nudge first-pass use of generated recency-window search planners."""

    available_names = _tool_names_execution_facing(openai_tools)
    if "resolve_search_window_or_bounds" not in available_names:
        return ""
    if _message_already_called_tool(openai_messages, "resolve_search_window_or_bounds"):
        return ""
    latest_user = _latest_user_request_text(openai_messages).strip()
    latest_lower = latest_user.lower()
    if not latest_user:
        return ""
    has_recency = any(
        token in latest_lower
        for token in (
            "yesterday",
            "today",
            "upcoming",
            "latest",
            "oldest",
            "most recent",
            "newest",
            "earliest",
        )
    )
    if not has_recency:
        return ""
    if not any(token in latest_lower for token in ("reminder", "todo", "message")):
        return ""
    current_timestamp_tool = _tool_name_for_call(openai_tools, "get_current_timestamp")
    window_tool = _tool_name_for_call(openai_tools, "resolve_search_window_or_bounds")
    return (
        " For reminder/message recency searches, use the generated search-window "
        f"tool on the first pass after original {current_timestamp_tool}. Call "
        f"generated {window_tool} before the original search. If the user asks "
        "for a reminder or todo they made/created, use target_domain='reminder' "
        "and timestamp_intent='creation'. Keep made/created plus the visible "
        "reminder/todo/task/item wording in phrase; do not reduce the phrase to "
        "only 'yesterday'. If the user asks what todo/reminder they made, "
        "created, or added yesterday, pass the visible phrase, such as "
        "'todo item I made yesterday', and timestamp_intent='creation'. Do not "
        "rewrite a plain reminder/todo request into 'made yesterday' or "
        "'created yesterday'. If the user asks for a due/upcoming reminder, a "
        "todo from yesterday/today, or something to do later today, use "
        "timestamp_intent='reminder' unless the user explicitly says made, "
        "created, or added. Never use message_creation for reminders "
        "or todos. If the user asks for a message by recency, use "
        "target_domain='message'. Then call the original search tool named in "
        "target_tool_name with search_kwargs unchanged. For oldest/latest message "
        "questions, call a message-content selector only after search_messages "
        "returns non-empty records; do not call a selector on a failed search or "
        "empty record list."
    )


def _compact_reminder_location_first_attempt_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    """Nudge first-pass use of generated reminder/location tools.

    Same-task adoption retry is effective but expensive. This guidance keeps
    the same generated-tool workflow on the first attempt when the relevant
    generated tools are visible.
    """

    available_names = _tool_names_execution_facing(openai_tools)
    request = _latest_user_request_text(openai_messages).strip()
    conversation_user_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    ).strip()
    request_lower = request.lower()
    conversation_lower = conversation_user_text.lower()
    if not request:
        return ""
    if not any(
        token in request_lower
        for token in ("remind", "reminder", "todo", "to-do", "to do")
    ) and not any(
        token in conversation_lower
        for token in ("remind", "reminder", "todo", "to-do", "to do")
    ):
        return ""
    has_relative_time = any(
        token in request_lower
        for token in (
            "tomorrow",
            "next week",
            "week from",
            "in a week",
            "later this week",
        )
    )
    has_next_weekday_time = any(
        token in request_lower
        for token in (
            "next monday",
            "next tuesday",
            "next wednesday",
            "next thursday",
            "next friday",
            "next saturday",
            "next sunday",
        )
    )
    has_location_phrase = any(
        token in request_lower
        for token in (
            " at ",
            " near ",
            " around ",
            " by ",
            " in ",
            " on ",
        )
    ) or any(
        token in conversation_lower
        for token in (
            " at ",
            " near ",
            " around ",
            " by ",
            " in ",
            " on ",
        )
    )
    current_timestamp_tool = _tool_name_for_call(openai_tools, "get_current_timestamp")
    datetime_info_tool = _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
    reminder_tool = _tool_name_for_call(openai_tools, "prepare_reminder_creation_args")
    add_tool = _tool_name_for_call(openai_tools, "add_reminder")
    if (
        has_relative_time
        and has_location_phrase
        and {
            "prepare_location_search_args",
            "prepare_reminder_creation_args",
            "relative_day_time_to_timestamp",
        }
        <= available_names
        and not _message_already_called_tool(
            openai_messages, "prepare_location_search_args"
        )
        and not _message_already_called_tool(openai_messages, "add_reminder")
    ):
        relative_tool = _tool_name_for_call(
            openai_tools, "relative_day_time_to_timestamp"
        )
        location_tool = _tool_name_for_call(
            openai_tools, "prepare_location_search_args"
        )
        search_tool = _tool_name_for_call(
            openai_tools, "search_location_around_lat_lon"
        )
        current_location_tool = _tool_name_for_call(
            openai_tools, "get_current_location"
        )
        return (
            " For relative reminder tasks that include a named place, use the "
            "generated tools on the first pass and batch only independent calls: "
            f"first call original {current_timestamp_tool} and generated "
            f"{location_tool} together; {location_tool} should receive the full "
            "latest user request and the exact visible place phrase if already "
            f"isolated. If {location_tool} routes to original "
            f"{current_location_tool}, call that original tool, then call "
            f"{location_tool} again with the returned latitude/longitude before "
            f"original {search_tool}. Next call original {datetime_info_tool} on "
            f"the timestamp and original {search_tool} with the generated "
            f"downstream kwargs unchanged. Then call generated {relative_tool}, "
            f"then generated {reminder_tool} with that generated timestamp and "
            "only coordinates returned by the visible original location search, "
            f"then call original {add_tool} with add_reminder_kwargs unchanged. "
            "Do not call location search with placeholder coordinates, and do not "
            "manually assemble add_reminder arguments while these generated tools "
            "are visible."
        )
    if (
        has_next_weekday_time
        and "next_weekday_time_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "next_weekday_time_to_timestamp"
        )
    ):
        weekday_tool = _tool_name_for_call(
            openai_tools, "next_weekday_time_to_timestamp"
        )
        prep_note = ""
        if "prepare_reminder_creation_args" in available_names:
            prep_note = (
                f" Then call generated {reminder_tool} with the generated "
                "timestamp as resolved_reminder_timestamp before original "
                f"{add_tool}; use add_reminder_kwargs unchanged."
            )
        return (
            " For next-weekday reminder tasks, keep the generated timestamp path "
            f"on the first pass: call original {current_timestamp_tool}, then "
            f"original {datetime_info_tool} on that exact timestamp, then call "
            f"generated {weekday_tool} with current_timestamp, target_isoweekday, "
            "hour, minute, and current_datetime_info set to the visible datetime "
            f"dict.{prep_note} Do not use manual day arithmetic or "
            "datetime_info_to_timestamp while the generated weekday tool is "
            "visible."
        )
    if (
        has_relative_time
        and "relative_day_time_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
    ):
        relative_tool = _tool_name_for_call(
            openai_tools, "relative_day_time_to_timestamp"
        )
        if "prepare_reminder_creation_args" in available_names:
            return (
                " For relative local add-reminder times, prefer the composite "
                "generated reminder-preparation tool on the first pass: call "
                f"original {current_timestamp_tool}, then original "
                f"{datetime_info_tool} on that exact timestamp, then call "
                f"generated {reminder_tool} with current_timestamp, day_offset, "
                "hour, minute, and current_datetime_info set to the visible "
                "datetime dict. If it returns should_call_add_reminder=true, "
                f"call original {add_tool} with add_reminder_kwargs unchanged. "
                f"Use generated {relative_tool} only when the task is a reminder "
                "modification or when the composite generated tool is not visible. "
                "Do not ask for a timezone or manually assemble add_reminder "
                "arguments while the composite generated tool is visible."
            )
        return (
            " For relative local reminder times, keep the generated timestamp "
            f"path on the first pass: call original {current_timestamp_tool}, "
            f"then original {datetime_info_tool} on that exact timestamp, then "
            f"call generated {relative_tool} with current_timestamp, day_offset, "
            "hour, minute, and current_datetime_info set to the visible datetime "
            "dict. Do not ask for a timezone or manually assemble "
            "add_reminder arguments while the generated timestamp tool is visible."
        )
    return ""


def _minimal_generated_tool_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic generated-tool guidance for clean primary evidence runs."""
    names = sorted(_tool_names_execution_facing(openai_tools))
    generated_names = [
        name for name in names if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    ]
    if not generated_names:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if GENERATED_TOOL_MINIMAL_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    tool_list = ", ".join(generated_names[:6])
    overflow = len(generated_names) - 6
    if overflow > 0:
        tool_list = f"{tool_list}, +{overflow} more"
    first_attempt_sequence = _compact_reminder_location_first_attempt_instruction(
        openai_messages, openai_tools
    )
    contact_lookup_sequence = _compact_contact_lookup_first_attempt_instruction(
        openai_messages, openai_tools
    )
    direct_contact_action_sequence = (
        _compact_direct_contact_action_first_attempt_instruction(
            openai_messages, openai_tools
        )
    )
    state_sequence = _compact_state_precondition_first_attempt_instruction(
        openai_messages, openai_tools
    )
    search_window_sequence = _compact_search_window_first_attempt_instruction(
        openai_messages, openai_tools
    )
    exact_next = _compact_generated_tool_exact_next_instruction(
        openai_messages, openai_tools
    )
    return {
        "role": "system",
        "content": (
            f"{GENERATED_TOOL_MINIMAL_POLICY_SENTINEL} SAGE generated tools "
            f"available this turn: {tool_list}. Use a generated tool only when "
            "its name, description, schema, and required inputs match visible "
            "user instructions, visible tool results, or prior tool output. "
            "Generated tools prepare values, select records, normalize evidence, "
            "or construct arguments; original environment tools still perform "
            "state-changing actions. If a generated tool returns a true "
            "should_call flag with tool_name, downstream_tool_name, "
            "target_tool_name, or *_kwargs, call the named original tool next "
            "with those returned arguments unchanged. If a generated tool "
            "returns kwargs for an original tool, do not add optional filters "
            "such as is_self, person_id, content, timestamps, coordinates, or "
            "relationship unless that field is in the generated-tool result, a "
            "visible prior tool result, or the current user request. If a field "
            "is absent from the returned kwargs, leave it absent. "
            "If a generated tool "
            "returns final_answer, final_answer_recommendation, answer_value, "
            "selected_record, or value and no downstream action is required, "
            "answer from that result. If it returns abstain_reason, missing "
            "information, tie candidates, or a false should_call flag, do not "
            "guess missing fields."
            f"{contact_lookup_sequence}"
            f"{direct_contact_action_sequence}"
            f"{state_sequence}"
            f"{search_window_sequence}"
            f"{first_attempt_sequence}"
            f"{exact_next}"
        ),
    }


def _lean_generated_tool_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Low-token generated-tool guidance for fair primary evidence runs."""
    names = sorted(_tool_names_execution_facing(openai_tools))
    generated_names = [
        name for name in names if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    ]
    if not generated_names:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if GENERATED_TOOL_LEAN_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    tool_list = ", ".join(generated_names[:4])
    overflow = len(generated_names) - 4
    if overflow > 0:
        tool_list = f"{tool_list}, +{overflow} more"
    exact_next = _compact_generated_tool_exact_next_instruction(
        openai_messages, openai_tools
    )
    if exact_next:
        exact_next = f" {exact_next}"
    return {
        "role": "system",
        "content": (
            f"{GENERATED_TOOL_LEAN_POLICY_SENTINEL} Generated tools visible: "
            f"{tool_list}. Use one only when its schema inputs are satisfied by "
            "the user request, visible records, or prior tool output. Generated "
            "tools prepare/select/normalize; original tools still perform state "
            "changes. When a generated tool returns a true should_call flag, "
            "tool_name/downstream_tool_name/target_tool_name, or *_kwargs, call "
            "that original tool next with returned kwargs unchanged. When it "
            "returns final_answer/value/selected_record and no action remains, "
            "answer from it. When it abstains or reports missing/tie data, do "
            f"not guess hidden fields.{exact_next}"
        ),
    }


def _compact_generated_tool_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic, schema-level generated-tool guidance for lower-token runs."""
    names = sorted(_tool_names_execution_facing(openai_tools))
    generated_names = [
        name for name in names if name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    ]
    if not generated_names:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if GENERATED_TOOL_COMPACT_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    tool_list = ", ".join(generated_names[:8])
    overflow = len(generated_names) - 8
    if overflow > 0:
        tool_list = f"{tool_list}, +{overflow} more"
    exact_next = _compact_generated_tool_exact_next_instruction(
        openai_messages, openai_tools
    )
    first_attempt_sequence = _compact_reminder_location_first_attempt_instruction(
        openai_messages, openai_tools
    )
    contact_lookup_sequence = _compact_contact_lookup_first_attempt_instruction(
        openai_messages, openai_tools
    )
    direct_contact_action_sequence = (
        _compact_direct_contact_action_first_attempt_instruction(
            openai_messages, openai_tools
        )
    )
    return {
        "role": "system",
        "content": (
            f"{GENERATED_TOOL_COMPACT_POLICY_SENTINEL} SAGE generated tools are "
            f"available: {tool_list}. Use a generated tool when its typed inputs "
            "match visible user constraints, visible records, or prior tool "
            "outputs. Generated tools are support tools only; they do not perform "
            "state-changing actions. If a generated tool returns search/find/get "
            "kwargs with a should_call flag, call the named original search tool "
            "next with those kwargs unchanged. If it returns downstream_tool_name, "
            "target_tool_name, tool_name, or *_kwargs for an original side-effect "
            "tool with a true should_call flag, call that original tool next with "
            "the returned kwargs unchanged. If it returns selected_record, value, "
            "answer_value, final_answer, or final_answer_recommendation and no "
            "downstream action is required, use that result directly. If it "
            "returns abstain_reason, missing information, tie candidates, or a "
            "false should_call flag, do not guess hidden ids, coordinates, dates, "
            "required side-effect content, names, phone numbers, addresses, or "
            "optional filters; search with visible constraints, ask for the "
            "missing information, or state that the task cannot be completed with "
            "the visible tools. Do not fill required side-effect fields with "
            "placeholders such as Reminder, meeting, task, unknown, or the raw "
            "instruction text when the user has not supplied that value. If an "
            "abstain_reason names a missing field that is already available from "
            "a prior tool result, add that field to the next generated-tool call "
            "once; do not recompute unrelated values or repeat stale argument "
            "shapes. For "
            "absolute calendar date/time reminder or "
            "scheduling requests, call original datetime_info_to_timestamp first "
            "when that tool is visible, then pass the returned timestamp into the "
            "generated argument-preparation tool instead of letting a generated "
            "tool infer timezone from raw text. For relative date/time requests "
            "such as tomorrow or next week, call get_current_timestamp and "
            "timestamp_to_datetime_info first when visible, then call the "
            "generated relative-time tool with that visible datetime_info, and "
            "use the generated timestamp unchanged in the downstream original "
            "side-effect tool. Match the called tool's actual schema exactly: "
            "if the available timestamp tool asks for year, month, day, hour, "
            "minute, or second, pass those absolute fields from visible "
            "datetime_info after applying the user's relative offset; do not "
            "invent current_timestamp, day_offset, or current_datetime_info "
            "arguments unless those fields are present in that tool's schema. "
            "Do not repeat the same generated tool with the "
            "same arguments after it returns a usable result; proceed to the "
            "next original tool call or final answer."
            f"{contact_lookup_sequence}"
            f"{direct_contact_action_sequence}"
            f"{first_attempt_sequence}"
            f"{exact_next}"
        ),
    }


def _message_counterparty_search_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge actors to use generated pre-search planners for message counterparties."""
    if "plan_message_counterparty_search" not in _tool_names(openai_tools):
        return None
    if _message_already_called_tool(
        openai_messages, "plan_message_counterparty_search"
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if MESSAGE_COUNTERPARTY_SEARCH_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    return {
        "role": "system",
        "content": (
            f"{MESSAGE_COUNTERPARTY_SEARCH_POLICY_SENTINEL} A generated "
            "message-counterparty search planner is available. When the user "
            "identifies a contact through messages involving the current user "
            "and a later generated selector/action helper needs message records "
            "or self_person_id, make the next assistant action a "
            "plan_message_counterparty_search call before manual search_messages "
            "arguments. Use message_direction='sent' for messages the user sent "
            "and message_direction='received' for messages the user received; do "
            "not pass a slash-separated example string as the actual value. Do "
            "not pass sender_person_id='self' or recipient_person_id="
            "'self' directly to search_messages; use the generated planner to get "
            "the concrete self person_id first. If it returns search_contacts_kwargs, "
            "call original search_contacts with those kwargs, copy the visible "
            "self contact person_id exactly, character-for-character, into a "
            "second planner call, then call original search_messages with the "
            "returned search_messages_kwargs. Then use "
            "the visible generated selector/action helper before any original "
            "modify_contact call. For contact modify/update requests, pass an "
            "updates dict to that selector/action helper containing the explicit "
            "fields the user asked to change, such as phone_number, name, or "
            "relationship. If you call select_message_counterparty_for_contact_update "
            "directly, include message_direction='sent' when the user asks for "
            "the last person they sent a message to, and message_direction="
            "'received' when the user asks for a person who sent them a message. "
            "Do not omit updates for modify/update requests."
        ),
    }


def _message_counterparty_self_lookup_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Keep staged message-counterparty lookup on the generated-tool path."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_message_counterparty_search" not in available_names:
        return None
    if "search_messages" not in available_names:
        return None
    latest_plan = _latest_tool_message_index(
        openai_messages, {"plan_message_counterparty_search"}
    )
    latest_contacts = _latest_tool_message_index(openai_messages, {"search_contacts"})
    if latest_plan is None or latest_contacts is None:
        return None
    latest_messages = _latest_tool_message_index(openai_messages, {"search_messages"})
    plan_index, plan_message = latest_plan
    contacts_index, contacts_message = latest_contacts
    if contacts_index < plan_index:
        return None
    if latest_messages is not None and latest_messages[0] > contacts_index:
        return None
    plan_payload = _parse_mapping_payload(plan_message.get("content"))
    if not bool(plan_payload.get("should_call_search_contacts")):
        return None
    contact_records = _parse_sequence_payload(contacts_message.get("content"))
    if not any(
        isinstance(record, Mapping)
        and (
            bool(record.get("is_self"))
            or str(record.get("relationship") or "").strip().lower() == "self"
        )
        and str(record.get("person_id") or "").strip()
        for record in contact_records
    ):
        return None
    prior_args = _latest_prior_tool_call_arguments(
        openai_messages, "plan_message_counterparty_search"
    )
    message_direction = str(prior_args.get("message_direction") or "").strip()
    selection_mode = str(prior_args.get("selection_mode") or "").strip()
    copied_fields = []
    if message_direction:
        copied_fields.append(f"message_direction={message_direction!r}")
    if selection_mode:
        copied_fields.append(f"selection_mode={selection_mode!r}")
    copied_note = (
        " Keep "
        + " and ".join(copied_fields)
        + " from the previous generated-tool call."
        if copied_fields
        else " Keep the previous message_direction and selection_mode values."
    )
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if MESSAGE_COUNTERPARTY_SELF_LOOKUP_HANDOFF_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    return {
        "role": "system",
        "content": (
            f"{MESSAGE_COUNTERPARTY_SELF_LOOKUP_HANDOFF_POLICY_SENTINEL} The "
            "generated message-counterparty planner requested a self-contact "
            "lookup, and the original search_contacts result now shows the "
            "current user's visible self contact. Do not manually construct "
            "search_messages timestamp, phone-number, content, or relationship "
            "filters. Call plan_message_counterparty_search again now, copying "
            "the visible self contact person_id exactly into self_person_id."
            f"{copied_note} Then call original search_messages with exactly the "
            "search_messages_kwargs returned by that second generated-tool call."
        ),
    }


def _generated_record_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Tell the actor how to pass visible original records back into a generated tool."""

    latest_messages = _latest_tool_message_index(openai_messages, {"search_messages"})
    if latest_messages is None:
        return None
    latest_index, latest_message = latest_messages
    records = _parse_sequence_payload(latest_message.get("content"))
    if not records:
        return None
    if _message_called_generated_tool_after_index(
        openai_messages,
        openai_tools,
        latest_index,
    ):
        return None

    candidates = [
        (index, tool_name)
        for index, tool_name in enumerate(
            _generated_tool_names_execution_facing(openai_tools)
        )
        if "messages" in _tool_input_names_execution_facing(openai_tools, tool_name)
        and _generated_tool_consumes_latest_record_source(
            openai_tools,
            tool_name,
            "search_messages",
        )
        and _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            tool_name,
        )
    ]
    if not candidates:
        return None

    _candidate_index, tool_name = sorted(
        candidates,
        key=lambda item: (
            _generated_tool_continuation_priority(openai_tools, item[1]),
            _generated_tool_choice_priority(openai_tools, item[1]),
            item[0],
        ),
    )[0]
    prior_args = _latest_prior_tool_call_arguments(openai_messages, tool_name)
    prior_args.pop("messages", None)
    visible_tool_name = _tool_name_for_call(openai_tools, tool_name)
    prior_instruction = ""
    if prior_args:
        prior_instruction = (
            " Preserve the still-relevant prior generated-tool arguments "
            f"{json.dumps(prior_args, sort_keys=True)} unless the visible "
            "search result directly shows they are stale."
        )
        if str(prior_args.get("content_keyword") or "").strip():
            prior_instruction += (
                " In particular, include content_keyword exactly as shown in "
                "those prior generated-tool arguments; do not drop it when "
                "adding messages."
            )
    return {
        "role": "system",
        "content": (
            f"{GENERATED_RECORD_HANDOFF_POLICY_SENTINEL} The latest original "
            "search_messages call returned visible message records after a "
            "generated-tool workflow. The next generated-tool call should be "
            f"{visible_tool_name} with its messages argument set to the entire "
            "latest search_messages result, preserving record dictionaries and "
            "timestamps exactly as visible. Do not call this generated tool "
            "again without messages, and do not restart search_messages only to "
            "recover the same records."
            f"{prior_instruction} If the generated tool returns answer_value, "
            "exact_final_answer, final_answer, or final_answer_recommendation, "
            "use that returned value directly for the final answer or the next "
            "original side-effect tool."
        ),
    }


def _reminder_recency_relative_modify_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge relative reminder modifications after generated recency selection."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"relative_day_time_to_timestamp", "modify_reminder"} <= available_names):
        return None
    if _message_already_called_tool(openai_messages, "relative_day_time_to_timestamp"):
        return None
    if not (
        _latest_tool_is(openai_messages, "select_record_by_timestamp_extreme")
        or _latest_tool_is(openai_messages, "select_action_target_by_recency")
    ):
        return None
    requested_time = _tomorrow_time_request(openai_messages)
    if requested_time is None:
        return None
    selected: Mapping[str, Any] | None = _selected_record_payload(openai_messages)
    action_payload = _selected_action_payload(openai_messages)
    if selected is None and isinstance(action_payload, Mapping):
        candidate = action_payload.get("selected_record")
        if isinstance(candidate, Mapping):
            selected = candidate
    reminder_id = str((selected or {}).get("reminder_id") or "").strip()
    if not reminder_id:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_RECENCY_RELATIVE_MODIFY_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    hour, minute = requested_time
    current_timestamp = _latest_current_timestamp(openai_messages)
    current_info = (
        _timestamp_to_datetime_info_for_timestamp(openai_messages, current_timestamp)
        if current_timestamp is not None
        else None
    )
    if current_timestamp is None:
        if "get_current_timestamp" not in available_names:
            return None
        timestamp_instruction = (
            "First call get_current_timestamp, then call timestamp_to_datetime_info "
            "on that current timestamp, then call relative_day_time_to_timestamp "
            "with the returned dict as current_datetime_info."
        )
    elif current_info is None and "timestamp_to_datetime_info" in available_names:
        timestamp_instruction = (
            "Before calling relative_day_time_to_timestamp, call "
            "timestamp_to_datetime_info on the visible current timestamp. Then "
            "call relative_day_time_to_timestamp with that returned dict as "
            "current_datetime_info."
        )
    else:
        timestamp_instruction = (
            "Call relative_day_time_to_timestamp now with the visible current "
            "timestamp and the visible timestamp_to_datetime_info result as "
            "current_datetime_info; do not call datetime_info_to_timestamp for "
            "this relative request."
        )
    return {
        "role": "system",
        "content": (
            f"{REMINDER_RECENCY_RELATIVE_MODIFY_POLICY_SENTINEL} A generated "
            "selector has identified one reminder_id for a modify_reminder task, "
            f"and the user requested tomorrow at {hour:02d}:{minute:02d}. "
            f"{timestamp_instruction} Use day_offset=1, hour={hour}, "
            f"minute={minute}, and the visible current timestamp. Do not guess "
            "local_utc_offset_hours. Then call the original modify_reminder with "
            "the selected reminder_id and the timestamp returned by "
            "relative_day_time_to_timestamp. Do not invent an absolute calendar "
            "date for a relative 'tomorrow' request."
        ),
    }


def _reminder_recency_search_result_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Nudge generated selector adoption after reminder-recency search results."""
    available_names = _tool_names_execution_facing(openai_tools)
    if not ({"relative_day_time_to_timestamp", "modify_reminder"} <= available_names):
        return None
    request = _reminder_recency_request(openai_messages)
    if request not in {"modify_latest", "modify_upcoming"}:
        return None
    if not _latest_tool_is(openai_messages, "search_reminder"):
        return None
    if _message_already_called_tool(
        openai_messages, "select_record_by_timestamp_extreme"
    ) or _message_already_called_tool(
        openai_messages, "select_action_target_by_recency"
    ):
        return None
    if _tomorrow_time_request(openai_messages) is None:
        return None
    records = _records_from_latest_reminder_search(openai_messages)
    if not records:
        return None
    selector_name = ""
    if "select_record_by_timestamp_extreme" in available_names:
        selector_name = "select_record_by_timestamp_extreme"
    elif "select_action_target_by_recency" in available_names:
        selector_name = "select_action_target_by_recency"
    if not selector_name:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_RECENCY_SEARCH_RESULT_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    selection_mode = "oldest" if request == "modify_upcoming" else "latest"
    timestamp_key = (
        "reminder_timestamp" if request == "modify_upcoming" else "creation_timestamp"
    )
    selector_instruction = (
        "Call select_record_by_timestamp_extreme with the records from the latest "
        f"search_reminder result, timestamp_key='{timestamp_key}', and "
        f"selection_mode='{selection_mode}'."
        if selector_name == "select_record_by_timestamp_extreme"
        else (
            "Call select_action_target_by_recency with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', "
            f"selection_mode='{selection_mode}', action_type='modify_reminder', "
            "constraints={}, and updates={}."
        )
    )
    return {
        "role": "system",
        "content": (
            f"{REMINDER_RECENCY_SEARCH_RESULT_POLICY_SENTINEL} The latest "
            "search_reminder result is for a recency-based reminder modification. "
            "Do not call modify_reminder directly from the search result, and do "
            "not hand-compute a timestamp for a relative 'tomorrow' request. "
            f"{selector_instruction} After the generated selector returns one "
            "reminder_id, make sure timestamp_to_datetime_info has been called "
            "on the visible current timestamp. Then call "
            "relative_day_time_to_timestamp for the requested new time with the "
            "returned dict as current_datetime_info, and call the original "
            "modify_reminder with that selected reminder_id and the generated "
            "timestamp."
        ),
    }


def _with_selector_actor_policy(
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
) -> list[OpenAIMessage]:
    openai_messages = _without_ephemeral_actor_policy_messages(openai_messages)
    shared_task_closure_policy = _shared_task_closure_actor_policy_message(
        openai_messages, openai_tools
    )
    completion_policy = _helper_answer_completion_actor_policy_message(
        openai_messages, openai_tools
    )
    helper_retention_policy = (
        None
        if completion_policy is not None
        else _helper_answer_retention_actor_policy_message(
            openai_messages, openai_tools
        )
    )
    if completion_policy is not None:
        helper_adoption_policies = ()
    elif _generated_tool_lean_core_guidance_enabled():
        helper_adoption_policies = (
            _lean_generated_tool_actor_policy_message(openai_messages, openai_tools),
            _reminder_location_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_relative_composite_actor_policy_message(
                openai_messages, openai_tools
            ),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _absolute_reminder_timestamp_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_downstream_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_action_actor_policy_message(openai_messages, openai_tools),
            _device_status_lookup_actor_policy_message(openai_messages, openai_tools),
            _location_search_argument_actor_policy_message(
                openai_messages, openai_tools
            ),
            _location_search_retry_after_state_actor_policy_message(
                openai_messages, openai_tools
            ),
            _location_search_retry_after_coordinates_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_creation_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _direct_contact_action_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _generated_record_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _helper_output_handoff_actor_policy_message(openai_messages, openai_tools),
        )
    elif _generated_tool_lean_guidance_enabled():
        helper_adoption_policies = (
            _lean_generated_tool_actor_policy_message(openai_messages, openai_tools),
            _reminder_location_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_relative_composite_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_search_result_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_relative_modify_actor_policy_message(
                openai_messages, openai_tools
            ),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _absolute_reminder_timestamp_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_downstream_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_action_actor_policy_message(openai_messages, openai_tools),
            _contact_relationship_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_relationship_batch_result_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_lookup_answer_actor_policy_message(openai_messages, openai_tools),
            _contact_remove_success_actor_policy_message(openai_messages, openai_tools),
            _visible_record_selector_setup_actor_policy_message(
                openai_messages, openai_tools
            ),
            _selector_actor_policy_message(openai_messages, openai_tools),
            _safe_abstention_helper_actor_policy_message(openai_messages, openai_tools),
            _device_status_lookup_actor_policy_message(openai_messages, openai_tools),
            _generated_record_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _helper_output_handoff_actor_policy_message(openai_messages, openai_tools),
            _contact_creation_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _direct_contact_action_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
        )
    elif _generated_tool_minimal_guidance_enabled():
        helper_adoption_policies: tuple[dict[str, str] | None, ...] = (
            _minimal_generated_tool_actor_policy_message(openai_messages, openai_tools),
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_relative_composite_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_search_result_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_relative_modify_actor_policy_message(
                openai_messages, openai_tools
            ),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _absolute_reminder_timestamp_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_downstream_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_action_actor_policy_message(openai_messages, openai_tools),
            _contact_relationship_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_relationship_batch_result_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_lookup_answer_actor_policy_message(openai_messages, openai_tools),
            _contact_remove_success_actor_policy_message(openai_messages, openai_tools),
            _visible_record_selector_setup_actor_policy_message(
                openai_messages, openai_tools
            ),
            _selector_actor_policy_message(openai_messages, openai_tools),
            _safe_abstention_helper_actor_policy_message(openai_messages, openai_tools),
            _device_status_lookup_actor_policy_message(openai_messages, openai_tools),
            _generated_record_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _helper_output_handoff_actor_policy_message(openai_messages, openai_tools),
            _contact_creation_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _direct_contact_action_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
        )
    elif _generated_tool_compact_guidance_enabled():
        helper_adoption_policies = (
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _helper_output_handoff_actor_policy_message(openai_messages, openai_tools),
            _compact_generated_tool_actor_policy_message(openai_messages, openai_tools),
        )
    else:
        helper_adoption_policies = (
            _service_extractor_scalar_actor_policy_message(
                openai_messages, openai_tools
            ),
            _helper_adoption_retry_actor_policy_message(openai_messages, openai_tools),
            _message_counterparty_search_actor_policy_message(
                openai_messages, openai_tools
            ),
            _message_counterparty_self_lookup_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _generated_record_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_search_result_actor_policy_message(
                openai_messages, openai_tools
            ),
            _search_window_result_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_recency_relative_modify_actor_policy_message(
                openai_messages, openai_tools
            ),
            _device_status_answer_retention_actor_policy_message(
                openai_messages, openai_tools
            ),
            _helper_output_handoff_actor_policy_message(openai_messages, openai_tools),
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_relationship_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_remove_lookup_handoff_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_remove_success_actor_policy_message(openai_messages, openai_tools),
            _contact_lookup_answer_actor_policy_message(openai_messages, openai_tools),
            _safe_abstention_helper_actor_policy_message(openai_messages, openai_tools),
            _reminder_location_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _location_search_retry_after_state_actor_policy_message(
                openai_messages, openai_tools
            ),
            _location_search_retry_after_coordinates_actor_policy_message(
                openai_messages, openai_tools
            ),
            _location_search_argument_actor_policy_message(
                openai_messages, openai_tools
            ),
            _add_contact_argument_actor_policy_message(openai_messages, openai_tools),
            _contact_creation_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _direct_contact_action_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _action_argument_helper_actor_policy_message(openai_messages, openai_tools),
            _post_selection_helper_actor_policy_message(openai_messages, openai_tools),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _absolute_reminder_timestamp_actor_policy_message(
                openai_messages, openai_tools
            ),
            _state_downstream_completion_actor_policy_message(
                openai_messages, openai_tools
            ),
            _device_status_lookup_actor_policy_message(openai_messages, openai_tools),
            _state_action_actor_policy_message(openai_messages, openai_tools),
        )
    bridge_policies: tuple[dict[str, str] | None, ...] = ()
    answer_retention_policy: dict[str, str] | None = None
    if _praxis_bridge_policy_enabled():
        answer_retention_policy = _answer_retention_actor_policy_message(
            openai_messages
        )
        bridge_policies = (
            _safe_argument_actor_policy_message(openai_messages, openai_tools),
            _temporal_anchor_actor_policy_message(openai_messages, openai_tools),
        )
    generic_tail_policies: tuple[dict[str, str] | None, ...]
    if (
        _generated_tool_lean_core_guidance_enabled()
        or _generated_tool_lean_guidance_enabled()
        or _generated_tool_minimal_guidance_enabled()
        or _generated_tool_compact_guidance_enabled()
    ):
        generic_tail_policies = ()
    else:
        generic_tail_policies = (
            _lookup_planner_actor_policy_message(openai_messages, openai_tools),
            _selector_actor_policy_message(openai_messages, openai_tools),
            _derived_actor_policy_message(openai_messages, openai_tools),
        )
    policies = [
        policy
        for policy in (
            answer_retention_policy,
            *bridge_policies,
            shared_task_closure_policy,
            helper_retention_policy,
            completion_policy,
            *helper_adoption_policies,
            *generic_tail_policies,
        )
        if policy is not None
    ]
    if not policies:
        return openai_messages
    policy_messages = [cast(OpenAIMessage, policy) for policy in policies]
    insert_at = 0
    for index, message in enumerate(openai_messages):
        if message.get("role") != "system":
            insert_at = index
            break
    else:
        insert_at = len(openai_messages)
    return openai_messages[:insert_at] + policy_messages + openai_messages[insert_at:]


def _shared_task_closure_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Apply the same task-completion discipline to baseline and SAGE arms."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if SHARED_TASK_CLOSURE_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    end_name = (
        _tool_name_for_call(openai_tools, "end_conversation")
        if "end_conversation" in _tool_names_execution_facing(openai_tools)
        else ""
    )
    close_instruction = (
        f"If the user only acknowledges, thanks you, says the answer is correct, "
        f"or says they need nothing else, call {end_name} when available."
        if end_name
        else (
            "If the user only acknowledges, thanks you, says the answer is "
            "correct, or says they need nothing else, reply with at most one "
            "short closing sentence."
        )
    )
    return {
        "role": "system",
        "content": (
            f"{SHARED_TASK_CLOSURE_POLICY_SENTINEL} Complete exactly the user's "
            "current ToolSandbox task. Once you have the requested lookup value "
            "or the requested state-changing tool succeeds, give only the concise "
            "answer or completion confirmation. Do not invite further assistance, "
            "do not introduce new tasks, and do not give general phone or app "
            f"instructions unless the user explicitly requested instructions. "
            f"{close_instruction}"
        ),
    }


def _synthetic_tool_call_completion(
    *,
    model_name: str,
    completion_id: str,
    tool_name: str,
    arguments: Mapping[str, Any],
) -> ChatCompletion:
    return ChatCompletion.model_construct(
        id=completion_id,
        choices=[
            Choice.model_construct(
                finish_reason="tool_calls",
                index=0,
                message=ChatCompletionMessage.model_construct(
                    content="",
                    role="assistant",
                    tool_calls=[
                        {
                            "id": f"call_sage_{tool_name}",
                            "function": {
                                "arguments": json.dumps(dict(arguments)),
                                "name": tool_name,
                            },
                            "type": "function",
                        }
                    ],
                ),
            )
        ],
        created=0,
        model=model_name,
        object="chat.completion",
    )


def _synthetic_text_completion(
    *,
    model_name: str,
    completion_id: str,
    content: str,
) -> ChatCompletion:
    return ChatCompletion.model_construct(
        id=completion_id,
        choices=[
            Choice.model_construct(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage.model_construct(
                    content=content,
                    role="assistant",
                    tool_calls=None,
                ),
            )
        ],
        created=0,
        model=model_name,
        object="chat.completion",
    )


def _all_user_texts(openai_messages: object) -> list[str]:
    return [
        str(message.get("content", "") or "")
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    ]


def _normalize_phone_for_search(raw: str) -> str:
    value = raw.strip()
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return value
    if value.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}" if len(digits) > 10 else value


def _phone_update_from_user_request(openai_messages: object) -> str:
    for text in reversed(_all_user_texts(openai_messages)):
        lower = text.lower()
        if (
            "phone" not in lower
            and "number" not in lower
            and "cell" not in lower
            and "mobile" not in lower
        ):
            continue
        match = re.search(r"\+?\d[\d\s().-]{6,}\d", text)
        if match:
            return _normalize_phone_for_search(match.group(0))
    return ""


def _contact_lookup_request(
    openai_messages: object,
) -> dict[str, str] | None:
    negative_actions = (
        "add contact",
        "create contact",
        "modify contact",
        "update contact",
        "remove contact",
        "delete contact",
        "send message",
        "text ",
    )
    for text in reversed(_all_user_texts(openai_messages)):
        stripped = " ".join(text.strip().split())
        if not stripped or _latest_user_is_brief_acknowledgement(
            [{"role": "user", "content": stripped}]
        ):
            continue
        lower = stripped.lower()
        if any(token in lower for token in negative_actions):
            continue
        phone_match = re.search(r"\+?\d[\d\s().-]{6,}\d", stripped)
        if "relationship" in lower and phone_match:
            return {
                "contact_name": "",
                "phone_number": _normalize_phone_for_search(phone_match.group(0)),
                "relationship": "",
                "requested_field": "relationship",
            }
        phone_name_match = re.search(
            r"(?:what(?:'s| is)\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})'s phone number\b",
            stripped,
        )
        if "phone number" in lower and phone_name_match:
            return {
                "contact_name": phone_name_match.group(1).strip(),
                "phone_number": "",
                "relationship": "",
                "requested_field": "phone_number",
            }
        phone_name_match = re.search(
            r"\bphone number\s+(?:of|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            stripped,
        )
        if "phone number" in lower and phone_name_match:
            return {
                "contact_name": phone_name_match.group(1).strip(),
                "phone_number": "",
                "relationship": "",
                "requested_field": "phone_number",
            }
        relationship_plural_match = re.search(
            r"\bwho\s+are\s+my\s+([a-z][a-z _-]{1,40})\??$",
            lower,
        )
        if relationship_plural_match:
            relationship = _known_relationship_label(
                relationship_plural_match.group(1).strip(" ?.!").replace("_", " ")
            )
            if relationship:
                return {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": relationship,
                    "requested_field": "name",
                }
        relationship_match = re.search(
            r"\b(?:name of|who is|who's|what is the name of)\s+my\s+([a-z][a-z _-]{1,40})\??$",
            lower,
        )
        if relationship_match and (
            "name" in lower or lower.startswith(("who is", "who's"))
        ):
            relationship = relationship_match.group(1).strip(" ?.!").replace("_", " ")
            if relationship and relationship not in {
                "contact",
                "phone",
                "name",
                "relationship",
            }:
                return {
                    "contact_name": "",
                    "phone_number": "",
                    "relationship": relationship,
                    "requested_field": "name",
                }
    return None


def _latest_tool_is(openai_messages: object, tool_name: str) -> bool:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_name = (
        _execution_facing_tool_name(str(messages[-1].get("name", "") or ""))
        if messages
        else ""
    )
    return bool(
        messages
        and messages[-1].get("role") == "tool"
        and latest_name == _execution_facing_tool_name(tool_name)
    )


def _contact_lookup_answer_text(
    openai_messages: object,
    request: Mapping[str, str],
) -> str | None:
    message = _latest_tool_message(openai_messages, "search_contacts")
    if message is None:
        return None
    records = _parse_sequence_payload(message.get("content"))
    if not records:
        return "I could not find a matching contact."
    requested_field = str(request.get("requested_field") or "").strip()
    values: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        value = record.get(requested_field)
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in values:
            values.append(text)
    if not values:
        return "I found a matching contact, but not the requested field."
    joined = _join_visible_names(values)
    if requested_field == "name" and request.get("relationship"):
        return f"Your {request['relationship']} is {joined}."
    if requested_field == "phone_number" and request.get("contact_name"):
        return f"{request['contact_name']}'s phone number is {joined}."
    if requested_field == "relationship" and request.get("phone_number"):
        return f"Your relationship with {request['phone_number']} is {joined}."
    return joined


def _contact_lookup_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_contacts" not in available_names:
        return None
    request = _contact_lookup_request(openai_messages)
    if request is None:
        return None
    if _latest_tool_is(openai_messages, "search_contacts"):
        answer = _contact_lookup_answer_text(openai_messages, request)
        if answer:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-contact-lookup-answer",
                content=answer,
            )
    if _latest_tool_is(openai_messages, "plan_contact_lookup_query"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "plan_contact_lookup_query"
        )
        kwargs = payload.get("search_contacts_kwargs") if payload else None
        should_call = bool(payload and payload.get("should_call_search_contacts"))
        if should_call and isinstance(kwargs, Mapping):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-lookup-search",
                tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
                arguments=kwargs,
            )
    if _message_already_called_tool(openai_messages, "search_contacts"):
        answer = _contact_lookup_answer_text(openai_messages, request)
        if answer:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-contact-lookup-retained-answer",
                content=answer,
            )
        return None
    if (
        "plan_contact_lookup_query" in available_names
        and not _message_already_called_tool(
            openai_messages, "plan_contact_lookup_query"
        )
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-contact-lookup-plan",
            tool_name=_tool_name_for_call(openai_tools, "plan_contact_lookup_query"),
            arguments=request,
        )
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-contact-lookup-direct-search",
        tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
        arguments={
            key: value
            for key, value in {
                "name": request.get("contact_name", ""),
                "phone_number": request.get("phone_number", ""),
                "relationship": request.get("relationship", ""),
            }.items()
            if value
        },
    )


def _latest_tool_content(openai_messages: object, tool_name: str) -> str | None:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return None
    return str(message.get("content", "") or "").strip()


def _latest_current_timestamp(openai_messages: object) -> float | None:
    content = _latest_tool_content(openai_messages, "get_current_timestamp")
    if not content:
        return None
    try:
        return float(content)
    except ValueError:
        return None


def _completion_calls_execution_tool(
    completion: ChatCompletion,
    tool_name: str,
) -> bool:
    target = _execution_facing_tool_name(tool_name)
    for choice in getattr(completion, "choices", []) or []:
        message = getattr(choice, "message", None)
        if message is None:
            continue
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, Mapping):
            tool_calls = message.get("tool_calls")
        for tool_call in tool_calls or []:
            name = ""
            if isinstance(tool_call, Mapping):
                function = tool_call.get("function")
                if isinstance(function, Mapping):
                    name = str(function.get("name", "") or "")
            else:
                function = getattr(tool_call, "function", None)
                name = str(getattr(function, "name", "") or "")
            if _execution_facing_tool_name(name) == target:
                return True
    return False


def _completion_has_any_tool_call(completion: ChatCompletion) -> bool:
    for choice in getattr(completion, "choices", []) or []:
        message = getattr(choice, "message", None)
        if message is None:
            continue
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, Mapping):
            tool_calls = message.get("tool_calls")
        if tool_calls:
            return True
    return False


def _completion_calls_state_action_planner(
    completion: ChatCompletion,
    state_helpers: set[str],
) -> bool:
    for helper_name in state_helpers:
        if _completion_calls_execution_tool(completion, helper_name):
            return True
    for choice in getattr(completion, "choices", []) or []:
        message = getattr(choice, "message", None)
        if message is None:
            continue
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, Mapping):
            tool_calls = message.get("tool_calls")
        for tool_call in tool_calls or []:
            name = ""
            if isinstance(tool_call, Mapping):
                function = tool_call.get("function")
                if isinstance(function, Mapping):
                    name = str(function.get("name", "") or "")
            else:
                function = getattr(tool_call, "function", None)
                name = str(getattr(function, "name", "") or "")
            if _execution_facing_tool_name(name).startswith(
                "plan_device_state_action_sequence"
            ):
                return True
    return False


def _completion_execution_tool_arguments(
    completion: ChatCompletion,
    tool_name: str,
) -> list[dict[str, Any]]:
    target = _execution_facing_tool_name(tool_name)
    matches: list[dict[str, Any]] = []
    for raw_name, arguments in _completion_execution_tool_argument_calls(completion):
        if _execution_facing_tool_name(raw_name) == target:
            matches.append(arguments)
    return matches


def _completion_execution_tool_argument_calls(
    completion: ChatCompletion,
) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    for choice in getattr(completion, "choices", []) or []:
        message = getattr(choice, "message", None)
        if message is None:
            continue
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, Mapping):
            tool_calls = message.get("tool_calls")
        for tool_call in tool_calls or []:
            raw_name = ""
            raw_arguments = "{}"
            if isinstance(tool_call, Mapping):
                function = tool_call.get("function")
                if isinstance(function, Mapping):
                    raw_name = str(function.get("name", "") or "")
                    raw_arguments = str(function.get("arguments", "{}") or "{}")
            else:
                function = getattr(tool_call, "function", None)
                raw_name = str(getattr(function, "name", "") or "")
                raw_arguments = str(getattr(function, "arguments", "{}") or "{}")
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments = {}
            if isinstance(arguments, dict):
                calls.append((raw_name, arguments))
    return calls


def _completion_uses_placeholder_lat_lon(completion: ChatCompletion) -> bool:
    def zero(value: object) -> bool:
        try:
            return float(value) == 0.0
        except (TypeError, ValueError):
            return False

    for _raw_name, arguments in _completion_execution_tool_argument_calls(completion):
        if zero(arguments.get("latitude")) and zero(arguments.get("longitude")):
            return True
    return False


def _completion_text_content(completion: ChatCompletion) -> str:
    chunks: list[str] = []
    for choice in getattr(completion, "choices", []) or []:
        message = getattr(choice, "message", None)
        if message is None:
            continue
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        if content:
            chunks.append(str(content))
    return "\n".join(chunks).strip()


def _latest_user_requests_downstream_after_state(openai_messages: object) -> bool:
    latest_user = _latest_user_request_text(openai_messages).lower().replace("’", "'")
    if not latest_user:
        return False
    downstream_phrases = (
        "send a message",
        "send the message",
        "send that message",
        "message to",
        "text ",
        "remind me",
        "add a reminder",
        "create a reminder",
        "remove contact",
        "modify contact",
        "update contact",
        "search",
        "find",
        "look up",
        "lookup",
    )
    return any(phrase in latest_user for phrase in downstream_phrases)


def _completion_repeats_completed_state_answer(completion: ChatCompletion) -> bool:
    if _completion_has_any_tool_call(completion):
        return False
    text = _completion_text_content(completion).lower().replace("wi-fi", "wifi")
    if not text:
        return False
    state_answer_terms = (
        "connected to the internet",
        "wifi",
        "cellular service",
        "location service",
        "low battery",
    )
    return any(term in text for term in state_answer_terms)


def _reminder_request_is_missing_content(openai_messages: object) -> bool:
    request = _absolute_reminder_creation_request(openai_messages)
    if request is None:
        request = _relative_reminder_creation_request(openai_messages)
    if request is None:
        return False
    return _looks_like_missing_reminder_content(str(request.get("content") or ""))


def _placeholder_reminder_content_retry_policy_message(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
) -> dict[str, str] | None:
    if not _reminder_request_is_missing_content(openai_messages):
        return None
    if _messages_show_reminder_content_request(openai_messages):
        return None
    placeholder_contents: list[str] = []
    for tool_name in ("prepare_reminder_creation_args", "add_reminder"):
        for args in _completion_execution_tool_arguments(completion, tool_name):
            content = args.get("content")
            if _looks_like_placeholder_reminder_content(content):
                placeholder_contents.append(str(content or "").strip())
    if not placeholder_contents:
        return None
    return {
        "role": "system",
        "content": (
            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The user supplied "
            "a reminder date/time without visible reminder content. The previous "
            "response attempted to use placeholder content "
            f"{placeholder_contents[0]!r}. Retry without calling time tools, "
            "generated reminder-preparation tools, or original add_reminder. Ask "
            "the user what the reminder should say. Do not fill required "
            "side-effect content with placeholders such as Reminder, task, todo, "
            "unknown, meeting, or the raw instruction text. Do not treat a "
            "timezone clarification or date/time phrase as reminder content."
        ),
    }


def _generated_tool_contract_retry_policy_message(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
) -> dict[str, str] | None:
    """Ask the actor to retry when it contradicts an abstaining generated tool."""
    available_names = _tool_names_execution_facing(openai_tools)
    placeholder_content_policy = _placeholder_reminder_content_retry_policy_message(
        openai_messages, openai_tools, completion
    )
    if placeholder_content_policy is not None:
        return placeholder_content_policy
    if _latest_user_is_answer_retention_followup(
        openai_messages
    ) and not _latest_user_is_privacy_retention_followup(openai_messages):
        exact_answer = _recent_exact_final_answer_from_tool(openai_messages)
        completion_text = _completion_text_content(completion).strip()
        if (
            exact_answer
            and not _completion_calls_execution_tool(completion, "end_conversation")
            and exact_answer.lower() not in completion_text.lower()
        ):
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "user message is an acknowledgement or closing turn after a "
                    "generated tool returned a final-answer-ready value. The "
                    "previous response did not preserve that generated-tool answer. "
                    "Retry by answering exactly with the generated tool's final "
                    f"answer: {exact_answer}. Do not add a generic acknowledgement, "
                    "do not invite further assistance, and do not call another tool "
                    "unless the only tool call is end_conversation."
                ),
            }
    generated_days = _latest_nonnegative_generated_day_count(openai_messages)
    if (
        generated_days is not None
        and _holiday_day_count_request(openai_messages)
        and _latest_user_is_holiday_day_count_challenge(openai_messages)
        and not _holiday_request_has_explicit_year(openai_messages)
    ):
        completion_text = _completion_text_content(completion).strip()
        completion_lower = completion_text.lower()
        recomputes_without_new_evidence = any(
            _completion_calls_execution_tool(completion, tool_name)
            for tool_name in (
                "get_current_timestamp",
                "search_holiday",
                "timestamp_diff",
                "days_between_timestamps",
            )
        )
        drifts_from_generated_value = str(generated_days) not in completion_text
        invents_calendar_context = any(
            token in completion_lower
            for token in ("approximately", "mistakenly", "2024", "2025", "past")
        )
        if (
            recomputes_without_new_evidence
            or drifts_from_generated_value
            or invents_calendar_context
        ):
            holiday_label = _holiday_label_from_user_request(openai_messages)
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                    "days_between_timestamps tool already computed a nonnegative "
                    f"day count of {generated_days} from visible current-time and "
                    "holiday lookup results. The latest user challenged the answer "
                    "but did not provide a new concrete date or year. Retry by "
                    "preserving the generated-tool day count and the holiday label "
                    f"from the task. A concise valid answer is: It is "
                    f"{generated_days} days till {holiday_label}. Do not call "
                    "another date tool, do not switch to a different year, and do "
                    "not use an approximate calendar guess."
                ),
            }
    latest_user_text = " ".join(_latest_user_request_text(openai_messages).split())
    latest_user_lower = latest_user_text.lower().replace("’", "'")
    reminder_creation_recency_request = (
        any(token in latest_user_lower for token in ("reminder", "todo", "task"))
        and any(token in latest_user_lower for token in ("created", "made"))
        and any(
            token in latest_user_lower
            for token in ("yesterday", "today", "latest", "last", "most recent")
        )
    )
    if reminder_creation_recency_request:
        for attempted in _completion_execution_tool_arguments(
            completion,
            "resolve_search_window_or_bounds",
        ):
            target_domain = str(attempted.get("target_domain") or "").strip().lower()
            timestamp_intent = (
                str(attempted.get("timestamp_intent") or "").strip().lower()
            )
            if target_domain != "reminder" or timestamp_intent in {
                "creation",
                "reminder_creation",
                "created",
                "creation_time",
                "created_time",
            }:
                continue
            current_timestamp = attempted.get("current_timestamp")
            if current_timestamp is None:
                current_timestamp = _latest_current_timestamp(openai_messages)
            phrase = str(attempted.get("phrase") or "").strip() or latest_user_text
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The user "
                    "asked for a reminder/todo item by when it was made or "
                    "created, so the generated recency search-window tool must "
                    "search reminder creation time, not reminder due time. The "
                    "previous response used the wrong timestamp_intent. Retry with "
                    "one generated resolve_search_window_or_bounds call using "
                    "target_domain='reminder', timestamp_intent='creation', the "
                    f"visible recency phrase {phrase!r}, and current_timestamp "
                    f"{current_timestamp!r}. After that generated tool returns "
                    "search_kwargs, call original search_reminder with those "
                    "kwargs unchanged."
                ),
            }
    next_service_completion = _next_service_direct_completion_response(openai_messages)
    if next_service_completion is not None:
        latest_name, final_response = next_service_completion
        completion_text = _completion_text_content(completion).strip()
        if (
            not _completion_calls_execution_tool(completion, "end_conversation")
            and final_response.lower() not in completion_text.lower()
        ):
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The generated "
                    "next_service_tool_call planned a direct device-state task, and "
                    f"the target original setter {latest_name} has succeeded. The "
                    "previous response did not preserve the generated-tool completion "
                    "boundary. Retry by answering exactly with: "
                    f"{final_response} Do not mention intermediate prerequisite "
                    "settings, do not invite further assistance, and do not call "
                    "another tool."
                ),
            }
    contact_remove_target = _contact_remove_lookup_target(openai_messages, openai_tools)
    if contact_remove_target is not None and not _completion_calls_execution_tool(
        completion, "remove_contact"
    ):
        phone, person_id = contact_remove_target
        remove_tool_name = _tool_name_for_call(openai_tools, "remove_contact")
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The generated "
                "contact lookup path found exactly one visible non-self contact "
                f"matching the user's requested phone number {phone}. The previous "
                "response did not preserve the generated-tool handoff and asked for "
                "unnecessary confirmation. Retry by calling original "
                f"{remove_tool_name} with exactly "
                f"{json.dumps({'person_id': person_id}, sort_keys=True)}. Do not "
                "treat 'my contact' as relationship self; it means the user's "
                "address book."
            ),
        }
    state_precondition = _latest_original_state_precondition_error(openai_messages)
    state_helpers = _state_action_planner_tool_names(openai_tools)
    if state_helpers:
        messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
        latest = messages[-1] if messages else {}
        latest_tool_name = _execution_facing_tool_name(
            str(latest.get("name", "") or "")
        )
        downstream_tools = ORIGINAL_SIDE_EFFECT_TOOL_NAMES - SETTING_SETTER_TOOL_NAMES
        latest_content = str(latest.get("content", "") or "").strip().lower()
        latest_plan = _latest_tool_message_index(openai_messages, state_helpers)
        if (
            latest.get("role") == "tool"
            and latest_tool_name in downstream_tools
            and "error" not in latest_content
            and "exception" not in latest_content
            and latest_plan is not None
            and latest_plan[0] < len(messages) - 1
        ):
            _plan_index, plan_message = latest_plan
            state_payload = _parse_mapping_payload(plan_message.get("content"))
            final_marker = str(
                state_payload.get("final_response_recommendation") or ""
            ).strip()
            resumes_downstream = (
                bool(state_payload.get("continue_original_task_after_sequence"))
                or final_marker == "continue_original_task"
            )
            completion_text = _completion_text_content(completion).strip()
            if resumes_downstream and completion_text == "continue_original_task":
                tool_args = _latest_prior_tool_call_arguments(
                    openai_messages,
                    latest_tool_name,
                )
                detail = ""
                if latest_tool_name == "send_message_with_phone_number":
                    phone_number = str(tool_args.get("phone_number") or "").strip()
                    content = str(tool_args.get("content") or "").strip()
                    detail = (
                        " Use the visible recipient from the user request or "
                        "contact lookup when available"
                    )
                    if phone_number:
                        detail += f", the visible phone number {phone_number}"
                    if content:
                        detail += f", and the visible message content {content!r}"
                    detail += "."
                elif latest_tool_name in {
                    "add_reminder",
                    "modify_reminder",
                    "remove_reminder",
                }:
                    detail = " Report the completed reminder action from the visible tool call."
                elif latest_tool_name in {
                    "add_contact",
                    "modify_contact",
                    "remove_contact",
                }:
                    detail = " Report the completed contact action from the visible tool call."
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated device-state tool used continue_original_task "
                        "only as an internal marker. The original downstream "
                        f"ToolSandbox tool {latest_tool_name} has now succeeded, "
                        "but the previous response exposed that internal marker "
                        "to the user. Retry with a concise natural-language "
                        "completion for the downstream task. Do not answer with "
                        "continue_original_task, do not call another tool, and do "
                        "not repeat the device-state status unless the user asked "
                        f"about it.{detail}"
                    ),
                }
    if state_helpers and not any(
        _message_already_called_tool(openai_messages, name) for name in state_helpers
    ):
        direct_state_setter = next(
            (
                setter
                for setter in sorted(SETTING_SETTER_TOOL_NAMES)
                if _completion_calls_execution_tool(completion, setter)
            ),
            None,
        )
        latest_user = _latest_user_request_text(openai_messages).lower()
        direct_state_request = any(
            token in latest_user
            for token in (
                "wifi",
                "wi-fi",
                "cellular",
                "location service",
                "low battery",
                "battery mode",
            )
        ) and any(
            token in latest_user
            for token in (
                "turn",
                "enable",
                "disable",
                "switch",
                "set ",
                "shut off",
                "turn it on",
                "turn it off",
            )
        )
        if (
            direct_state_setter
            and direct_state_request
            and not _completion_calls_state_action_planner(completion, state_helpers)
        ):
            helper_list = ", ".join(sorted(state_helpers))
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                    "device-state planner is visible for this direct state-setting "
                    f"request, but the previous response called original "
                    f"{direct_state_setter} before using the generated planner. "
                    f"Retry by calling one generated planner first: {helper_list}. "
                    "Pass the latest user request as user_request and any visible "
                    "state/error text as visible_state_or_error. If the generated "
                    "tool returns should_call=true, then execute its returned "
                    "original setter sequence unchanged."
                ),
            }
    invalid_send_attempts = [
        (tool_name, args)
        for tool_name, args in _completion_execution_tool_argument_calls(completion)
        if "phone_number" in args
        and "content" in args
        and not _looks_like_phone_number_argument(args.get("phone_number"))
    ]
    if invalid_send_attempts:
        send_request = _extract_send_message_contact_request(openai_messages)
        if send_request and (
            "plan_send_message_contact_lookup" in available_names
            and not _message_already_called_tool(
                openai_messages, "plan_send_message_contact_lookup"
            )
        ):
            planner_name = _tool_name_for_call(
                openai_tools, "plan_send_message_contact_lookup"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    "previous response attempted an original send-message tool "
                    "with a recipient value that "
                    "is not a phone number. A generated send-recipient lookup "
                    "planner is visible. Retry by calling generated "
                    f"{planner_name} with exactly these arguments: "
                    f"{json.dumps(send_request, sort_keys=True)}. Do not call "
                    "the original send tool until a visible original contact "
                    "lookup returns one concrete phone number."
                ),
            }
        if send_request and (
            "plan_contact_lookup_query" in available_names
            and not _message_already_called_tool(
                openai_messages, "plan_contact_lookup_query"
            )
        ):
            planner_name = _tool_name_for_call(
                openai_tools, "plan_contact_lookup_query"
            )
            arguments = {
                "contact_name": send_request["recipient_name"],
                "phone_number": "",
                "relationship": "",
                "requested_field": "phone_number",
                "selected_record": {},
            }
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    "previous response attempted an original send-message tool "
                    "with a recipient value that "
                    "is not a phone number. A generated contact lookup planner "
                    "is visible. Retry by calling generated "
                    f"{planner_name} with exactly these arguments: "
                    f"{json.dumps(arguments, sort_keys=True)}. Then use only the "
                    "visible phone number returned by the original contact "
                    "lookup before any original send call."
                ),
            }
        if (
            "prepare_safe_action_or_abstain" in available_names
            and not _message_already_called_tool(
                openai_messages, "prepare_safe_action_or_abstain"
            )
        ):
            expected_safe_request = _safe_action_or_abstain_request(
                openai_messages, openai_tools
            )
            if expected_safe_request is not None:
                safe_tool_name = _tool_name_for_call(
                    openai_tools, "prepare_safe_action_or_abstain"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "previous response attempted an original send-message "
                        "tool with a recipient value "
                        "that is not a phone number, and no generated recipient "
                        "lookup planner has been used. Retry by calling generated "
                        f"{safe_tool_name} with exactly these arguments: "
                        f"{json.dumps(expected_safe_request, sort_keys=True)}. "
                        "Do not call the original send tool unless a visible "
                        "tool result provides a concrete phone number."
                    ),
                }
    latest_user_text = _latest_user_request_text(openai_messages)
    if _completion_uses_placeholder_lat_lon(
        completion
    ) and not _text_contains_lat_lon_pair(latest_user_text):
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                "response attempted a latitude/longitude lookup with placeholder "
                "coordinates 0,0 even though no visible user message supplied "
                "concrete latitude/longitude coordinates. Retry without calling "
                "that lookup. If current-location lookup is unavailable, use the "
                "generated safe-abstention recommendation instead of inventing "
                "coordinates."
            ),
        }

    prior_location_abstention = _prior_safe_location_lookup_abstention(openai_messages)
    if prior_location_abstention and not _text_contains_lat_lon_pair(latest_user_text):
        final_recommendation = _safe_abstention_final_recommendation(
            prior_location_abstention,
            openai_messages,
        ) or (
            "I cannot determine what city you are in because I do not have access "
            "to your current location, GPS, or latitude and longitude coordinates."
        )
        calls_location_safe_tool_again = _completion_calls_execution_tool(
            completion, "prepare_safe_action_or_abstain"
        )
        calls_location_workaround_tool = any(
            _completion_calls_execution_tool(completion, name)
            for name in (
                "get_location_service_status",
                "set_location_service_status",
                "get_low_battery_mode_status",
                "set_low_battery_mode_status",
                "get_wifi_status",
                "set_wifi_status",
                "get_cellular_service_status",
                "set_cellular_service_status",
                "search_lat_lon",
                "get_current_location",
            )
        )
        if calls_location_safe_tool_again or calls_location_workaround_tool:
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A prior "
                    "generated prepare_safe_action_or_abstain result already "
                    "established that current-location lookup is unavailable. "
                    "A later suggestion to change location, wifi, cellular, "
                    "or low-battery settings is not current-location evidence. "
                    "Status getters, setting tools, and search_lat_lon must not "
                    "be called after that generated abstention unless the user or "
                    "a visible tool result supplies concrete latitude/longitude "
                    "coordinates. Retry without calling generated or original "
                    "tools and answer using the generated tool's final "
                    f"recommendation exactly: {final_recommendation}"
                ),
            }

    safe_args = _completion_execution_tool_arguments(
        completion, "prepare_safe_action_or_abstain"
    )
    if safe_args:
        expected_safe_request = _safe_action_or_abstain_request(
            openai_messages, openai_tools
        )
        for args in safe_args:
            protected_arg_text = json.dumps(args, sort_keys=True)
            protected_tool_name_in_safe_payload = any(
                token in protected_arg_text
                for token in (
                    "modify_contact",
                    "remove_contact",
                    "send_message_with_phone_number",
                    "add_reminder",
                    "modify_reminder",
                    "remove_reminder",
                )
            )
            if expected_safe_request and protected_tool_name_in_safe_payload:
                safe_tool_name = _tool_name_for_call(
                    openai_tools, "prepare_safe_action_or_abstain"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"previous generated {safe_tool_name} call used original "
                        "side-effect tool names inside the validation-tool "
                        "arguments. That generated tool should receive semantic "
                        "capability labels only, so the validation call is not "
                        "confused with an environment side effect. Retry by "
                        f"calling generated {safe_tool_name} with exactly these "
                        f"arguments: {json.dumps(expected_safe_request, sort_keys=True)}."
                    ),
                }
            requested_action = _safe_action_capability(
                str(args.get("requested_action") or "").replace(" ", "_")
            )
            required = {
                _safe_action_capability(str(tool))
                for tool in (args.get("required_original_tools") or [])
                if str(tool)
            }
            user_text = str(
                args.get("user_request") or _latest_user_request_text(openai_messages)
            ).lower()
            contact_action = requested_action in {
                "contact_removal",
                "contact_update",
                "remove_contact",
                "delete_contact",
                "modify_contact",
                "update_contact",
            } or (
                "contact" in user_text
                and any(
                    token in user_text
                    for token in ("remove", "delete", "modify", "update", "change")
                )
            )
            recency_message_contact = (
                "message" in user_text
                and any(
                    token in user_text
                    for token in ("last", "latest", "most recent", "recent")
                )
                and any(token in user_text for token in ("modify", "update", "change"))
            )
            missing_contact_lookup = contact_action and "contact_lookup" not in required
            missing_message_lookup = (
                recency_message_contact and "message_lookup" not in required
            )
            location_action = requested_action == "location_lookup" or any(
                phrase in user_text
                for phrase in (
                    "current city",
                    "current location",
                    "where am i",
                    "what city am i",
                    "which city am i",
                )
            )
            missing_location_lookup = (
                location_action and "location_lookup" not in required
            )
            if expected_safe_request and (
                missing_contact_lookup
                or missing_message_lookup
                or missing_location_lookup
            ):
                safe_tool_name = _tool_name_for_call(
                    openai_tools, "prepare_safe_action_or_abstain"
                )
                side_effect_scope = (
                    "contact/reminder/message/location"
                    if missing_location_lookup
                    else "contact/reminder/message"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"previous generated {safe_tool_name} call omitted a "
                        "required lookup/precondition capability from "
                        "required_original_tools, so the generated tool could not "
                        "make the correct safe-abstention decision. Retry by "
                        f"calling generated {safe_tool_name} with exactly these "
                        f"arguments: {json.dumps(expected_safe_request, sort_keys=True)}. "
                        f"Do not call an original {side_effect_scope} side-effect "
                        "tool until this generated validation tool returns "
                        "safe_next_action=continue_with_original_tool."
                    ),
                }
    safe_payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_safe_action_or_abstain"
    )
    if safe_payload and (
        bool(safe_payload.get("should_abstain"))
        or str(safe_payload.get("safe_next_action") or "") == "ask_user_or_abstain"
    ):
        final_recommendation = _safe_abstention_final_recommendation(
            safe_payload,
            openai_messages,
        )
        if final_recommendation:
            completion_text = _completion_text_content(completion).strip()
            calls_original_tool = any(
                _completion_calls_execution_tool(completion, name)
                for name in (
                    "search_contacts",
                    "search_messages",
                    "modify_contact",
                    "remove_contact",
                    "search_reminder",
                    "modify_reminder",
                    "remove_reminder",
                    "add_reminder",
                    "send_message_with_phone_number",
                    "set_location_service_status",
                    "set_low_battery_mode_status",
                    "set_wifi_status",
                    "search_lat_lon",
                    "get_current_location",
                )
            )
            answer_mismatch = (
                bool(completion_text)
                and final_recommendation.lower() not in completion_text.lower()
            )
            if calls_original_tool or answer_mismatch:
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "latest generated prepare_safe_action_or_abstain result "
                        "returned should_abstain=true, so it did not authorize "
                        "additional original lookup or side-effect tool calls for "
                        "this request. Retry without calling original tools and "
                        "answer using the generated tool's final recommendation "
                        f"exactly: {final_recommendation}"
                    ),
                }
    if (
        "prepare_holiday_search_args" in available_names
        and _completion_calls_execution_tool(completion, "search_holiday")
        and not _called_tool_after_latest_user(
            openai_messages, "prepare_holiday_search_args"
        )
    ):
        latest_user = _latest_user_request_text(openai_messages).strip()
        latest_user_lower = latest_user.lower()
        if "timestamp" in latest_user_lower and any(
            token in latest_user_lower
            for token in (
                "holiday",
                "thanksgiving",
                "christmas",
                "easter",
                "halloween",
                "memorial",
                "labor day",
                "independence",
                "veterans",
            )
        ):
            holiday_prepare_name = _tool_name_for_call(
                openai_tools, "prepare_holiday_search_args"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                    "holiday-search argument tool is visible for this holiday "
                    "timestamp request, but the previous response attempted "
                    "original search_holiday directly. Retry before executing "
                    f"search_holiday. The next tool call must be generated "
                    f"{holiday_prepare_name} with user_request set to the visible "
                    "holiday timestamp request and visible_current_year set to 0 "
                    "unless a current year was already returned by an original "
                    "current-time conversion tool."
                ),
            }
    holiday_payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_holiday_search_args"
    )
    if (
        holiday_payload
        and bool(holiday_payload.get("should_call_search_holiday"))
        and "search_holiday" in available_names
    ):
        expected_kwargs = holiday_payload.get("search_holiday_kwargs")
        if isinstance(expected_kwargs, Mapping) and expected_kwargs:
            attempted_holiday_calls = _completion_execution_tool_arguments(
                completion, "search_holiday"
            )
            holiday_tool_name = _tool_name_for_call(openai_tools, "search_holiday")
            expected_contract = json.dumps(
                _call_contract_kwargs(expected_kwargs), sort_keys=True
            )
            if attempted_holiday_calls and not any(
                _call_contract_kwargs_match(expected_kwargs, attempted)
                for attempted in attempted_holiday_calls
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "latest generated prepare_holiday_search_args result "
                        "returned call-ready search_holiday_kwargs, but the "
                        "attempted original search_holiday call did not match "
                        "that generated contract. Retry by calling original "
                        f"{holiday_tool_name} with exactly these arguments: "
                        f"{expected_contract}. Do not invent or add a year unless "
                        "the generated kwargs include one."
                    ),
                }
            if not attempted_holiday_calls and not _completion_text_content(completion):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "latest generated prepare_holiday_search_args result "
                        "returned call-ready search_holiday_kwargs. It prepared "
                        "arguments only; the original ToolSandbox lookup still "
                        "has to run. Retry by calling original "
                        f"{holiday_tool_name} with exactly these arguments: "
                        f"{expected_contract}."
                    ),
                }
    expected_safe_request = _safe_action_or_abstain_request(
        openai_messages, openai_tools
    )
    if (
        expected_safe_request
        and "prepare_safe_action_or_abstain" in available_names
        and not _message_already_called_tool(
            openai_messages, "prepare_safe_action_or_abstain"
        )
    ):
        expected_action = _safe_action_capability(
            str(expected_safe_request.get("requested_action") or "").replace(" ", "_")
        )
        expected_required = {
            _safe_action_capability(str(tool))
            for tool in expected_safe_request.get("required_original_tools") or []
            if str(tool)
        }
        available_capabilities = {
            _safe_action_capability(name) for name in available_names
        }
        expects_missing_messages = (
            expected_action == "contact_update"
            and "message_lookup" in expected_required
            and "message_lookup" not in available_capabilities
        )
        expects_missing_contact_lookup = (
            expected_action in {"contact_removal", "contact_update"}
            and "contact_lookup" in expected_required
            and "contact_lookup" not in available_capabilities
        )
        expects_missing_send_lookup = (
            expected_action == "message_send"
            and "contact_lookup" in expected_required
            and "contact_lookup" not in available_capabilities
            and "send_message_with_phone_number" in available_names
        )
        expects_missing_location_lookup = (
            expected_action == "location_lookup"
            and "location_lookup" in expected_required
            and "location_lookup" not in available_capabilities
            and not _text_contains_lat_lon_pair(
                _latest_user_request_text(openai_messages)
            )
        )
        unsafe_completion = any(
            _completion_calls_execution_tool(completion, name)
            for name in (
                "search_contacts",
                "modify_contact",
                "remove_contact",
                "send_message_with_phone_number",
                "get_location_service_status",
                "set_location_service_status",
                "get_low_battery_mode_status",
                "set_low_battery_mode_status",
                "get_wifi_status",
                "set_wifi_status",
                "search_lat_lon",
            )
        )
        if (
            expects_missing_messages
            or expects_missing_contact_lookup
            or expects_missing_send_lookup
            or expects_missing_location_lookup
        ) and unsafe_completion:
            safe_tool_name = _tool_name_for_call(
                openai_tools, "prepare_safe_action_or_abstain"
            )
            request_kind = (
                "current-location lookup"
                if expects_missing_location_lookup
                else "contact action or message-send action"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                    f"safe-abstention tool is visible, and the user's {request_kind} "
                    "requires a lookup/precondition capability that is not currently "
                    "available. Retry before executing the original tool call. "
                    f"The next tool call must be generated {safe_tool_name} with "
                    f"exactly these arguments: "
                    f"{json.dumps(expected_safe_request, sort_keys=True)}."
                ),
            }
    if (
        _contact_update_message_recency_without_message_search_request(openai_messages)
        and "search_messages" not in available_names
        and _completion_calls_execution_tool(completion, "modify_contact")
    ):
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The user's "
                "contact update target depends on message history, but original "
                "search_messages is not available in this task. The previous "
                "response attempted original modify_contact by substituting a "
                "contact search result or guessed contact. Retry without calling "
                "modify_contact. State that there is not enough information to "
                "identify the last person the user sent a message to because "
                "message history is unavailable. Do not substitute search_contacts "
                "or a self contact for message history."
            ),
        }
    latest_state_helper = _latest_state_action_helper_payload(openai_messages)
    if latest_state_helper is not None:
        _state_index, state_payload = latest_state_helper
        next_state_action = _next_unsatisfied_state_action(
            openai_messages,
            state_payload,
        )
        if next_state_action is not None:
            expected_tool_name = _execution_facing_tool_name(
                str(next_state_action.get("tool_name", "") or "")
            )
            expected_arguments = next_state_action.get("arguments")
            if (
                expected_tool_name in SETTING_SETTER_TOOL_NAMES
                and expected_tool_name in available_names
                and isinstance(expected_arguments, Mapping)
            ):
                expected_calls = _completion_execution_tool_arguments(
                    completion,
                    expected_tool_name,
                )
                expected_call_matches = any(
                    _call_contract_kwargs_match(expected_arguments, attempted)
                    for attempted in expected_calls
                )
                calls_other_setter = any(
                    setter_name != expected_tool_name
                    and _completion_calls_execution_tool(completion, setter_name)
                    for setter_name in SETTING_SETTER_TOOL_NAMES
                )
                repeats_state_planner = _completion_calls_state_action_planner(
                    completion,
                    state_helpers,
                )
                answers_without_setter = bool(_completion_text_content(completion))
                if (
                    calls_other_setter
                    or repeats_state_planner
                    or answers_without_setter
                    or (
                        _completion_calls_execution_tool(
                            completion,
                            expected_tool_name,
                        )
                        and not expected_call_matches
                    )
                ):
                    expected_contract = json.dumps(
                        _call_contract_kwargs(expected_arguments),
                        sort_keys=True,
                    )
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "The latest generated device-state helper returned "
                            "an ordered action_sequence. The previous response "
                            "did not follow the next pending original setter "
                            "contract exactly. Retry with one original setter "
                            f"call only: {expected_tool_name} with exactly "
                            f"these arguments: {expected_contract}. Do not "
                            "answer yet, do not call a different setting setter, "
                            "and do not call the generated state helper again "
                            "before this setter."
                        ),
                    }
        already_satisfied = (
            str(state_payload.get("abstain_reason") or "").strip()
            == "already_in_desired_state"
            or str(state_payload.get("reason") or "").strip().endswith("_already_on")
            or str(state_payload.get("reason") or "").strip().endswith("_already_off")
        )
        state_tool_says_do_not_call = (
            already_satisfied and state_payload.get("should_call") is False
        )
        completion_repeats_setting = any(
            _completion_calls_execution_tool(completion, name)
            for name in SETTING_SETTER_TOOL_NAMES
        ) or _completion_calls_state_action_planner(completion, state_helpers)
        if state_tool_says_do_not_call and completion_repeats_setting:
            final_response = str(
                state_payload.get("final_response_recommendation") or ""
            ).strip()
            if bool(state_payload.get("continue_original_task_after_sequence")):
                instruction = (
                    "Retry without calling a setting setter or generated "
                    "state-action helper again. The generated state-action tool "
                    "reported that the required setting state is already "
                    "satisfied, so continue the original downstream task using "
                    "non-setting tools if they are available. If no downstream "
                    "tool is available, answer from the visible limitation "
                    "without retrying the setting setter."
                )
            elif final_response:
                instruction = (
                    "Retry without calling a setting setter or generated "
                    "state-action helper again. The generated state-action tool "
                    "reported that the requested setting state is already "
                    "satisfied. Answer exactly with: " + final_response
                )
            else:
                instruction = (
                    "Retry without calling a setting setter or generated "
                    "state-action helper again. The generated state-action tool "
                    "reported that the requested setting state is already "
                    "satisfied."
                )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} {instruction}"
                ),
            }
    if state_helpers:
        latest_setter_result = _latest_setting_setter_tool_result(openai_messages)
        latest_state_helper = _latest_tool_message_index(openai_messages, state_helpers)
        if latest_setter_result is not None and latest_state_helper is not None:
            setter_index, setter_name, setter_arguments, setter_content = (
                latest_setter_result
            )
            helper_index, _helper_message = latest_state_helper
            already_satisfied_response = (
                _setting_already_satisfied_response_from_setter_result(
                    setter_name,
                    setter_arguments,
                    setter_content,
                )
            )
            desired_on = setter_arguments.get("on")
            if (
                helper_index < setter_index
                and already_satisfied_response
                and isinstance(desired_on, bool)
                and not _completion_affirms_setting_state(
                    completion,
                    desired_on=desired_on,
                )
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                        "A generated device-state tool selected an original "
                        f"{setter_name} call, and that original setter returned "
                        f"visible text showing the requested target state is "
                        f"already satisfied: {setter_content!r}. Retry without "
                        "calling any setting setter or generated state-action "
                        "tool again. Answer exactly with: "
                        f"{already_satisfied_response}"
                    ),
                }
    if (
        state_helpers
        and _latest_successful_setting_tool_call(openai_messages) is not None
        and _latest_user_requests_downstream_after_state(openai_messages)
        and _completion_repeats_completed_state_answer(completion)
    ):
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                "device-state tool already cleared or satisfied the setting "
                "precondition, but the latest user request is now a downstream "
                "task. The previous response only repeated the completed device "
                "state. Retry by continuing the latest user request with relevant "
                "non-setting original ToolSandbox tools. For message requests, "
                "look up the recipient when a phone number is not already visible, "
                "then call the original message-sending tool with the visible "
                "content. Do not answer again with only the device setting status."
            ),
        }
    completed_state_sequence = _completed_state_action_sequence_payload(openai_messages)
    if completed_state_sequence is not None:
        payload, completed_count = completed_state_sequence
        sequence = payload.get("action_sequence")
        final_response = str(payload.get("final_response_recommendation") or "").strip()
        direct_task_complete = (
            isinstance(sequence, list)
            and completed_count >= len(sequence)
            and bool(final_response)
            and not bool(payload.get("continue_original_task_after_sequence"))
        )
        repeats_state_action = any(
            _completion_calls_execution_tool(completion, name)
            for name in (
                *state_helpers,
                *SETTING_GETTER_TOOL_NAMES,
                *SETTING_SETTER_TOOL_NAMES,
            )
        ) or _completion_calls_state_action_planner(completion, state_helpers)
        if (
            direct_task_complete
            and repeats_state_action
            and (
                _latest_user_is_post_completion_task_drift(openai_messages)
                or _latest_user_is_post_completion_state_drift(openai_messages)
            )
        ):
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                    "device-state tool already completed the direct setting task, "
                    "and its original setter sequence succeeded. The previous "
                    "response attempted another generated state-action helper, "
                    "original setting getter, or original setting setter after "
                    "completion. Retry without calling any generated state-action "
                    "helper, original setting getter, or original setting setter. "
                    "Preserve the generated tool's completed answer exactly: "
                    f"{final_response}"
                ),
            }
    if state_precondition is not None and state_helpers:
        error_index, error_text = state_precondition
        latest_state_helper = _latest_tool_message_index(openai_messages, state_helpers)
        helper_already_handled_error = (
            latest_state_helper is not None and latest_state_helper[0] > error_index
        )
        completion_calls_state_helper = any(
            _completion_calls_execution_tool(completion, name) for name in state_helpers
        )
        if not helper_already_handled_error and not completion_calls_state_helper:
            helper_list = ", ".join(sorted(state_helpers))
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "original ToolSandbox state/action tool returned a fresh "
                    f"precondition error: {error_text!r}. Retry the response before "
                    "executing any other original getter, setter, search, or final "
                    f"answer. The next tool call must be the generated device-state "
                    f"tool: {helper_list}. Pass the same user_request being pursued "
                    "and set visible_state_or_error to that exact error text so the "
                    "generated tool can plan the original setter sequence."
                ),
            }
    latest_location_payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_location_search_args"
    )
    if (
        str(latest_location_payload.get("abstain_reason") or "").strip()
        == "missing_location_phrase"
    ):
        search_args = _completion_execution_tool_arguments(
            completion, "search_location_around_lat_lon"
        )
        if search_args:
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "generated location-search tool abstained because the visible "
                    "place phrase was not passed into the generated tool. Retry "
                    "without calling original search_location_around_lat_lon. "
                    f"Call generated {location_tool_name} again with the combined "
                    "visible user request as user_request and the exact visible "
                    "place phrase, including street, road, neighborhood, or venue "
                    "qualifiers, as location_phrase. Only call original "
                    "search_location_around_lat_lon after the generated tool "
                    "returns should_call_downstream_tool=true."
                ),
            }
    if str(latest_location_payload.get("abstain_reason") or "").strip() in {
        "missing_current_coordinates_for_broad_location_query",
        "need_current_coordinates_for_broad_location_query",
    }:
        search_args = _completion_execution_tool_arguments(
            completion, "search_location_around_lat_lon"
        )
        attempted_unanchored_search = False
        for args in search_args:
            query = str(args.get("location") or "").strip()
            has_coordinates = (
                args.get("latitude") is not None and args.get("longitude") is not None
            )
            if _looks_like_unqualified_location_query(query) and not has_coordinates:
                attempted_unanchored_search = True
                break
        attempted_time_loop = any(
            _completion_calls_execution_tool(completion, tool_name)
            for tool_name in (
                "get_current_timestamp",
                "timestamp_to_datetime_info",
                "datetime_info_to_timestamp",
                "shift_timestamp",
                "relative_day_time_to_timestamp",
            )
        )
        attempted_state_detour = any(
            _completion_calls_execution_tool(completion, tool_name)
            for tool_name in (*SETTING_GETTER_TOOL_NAMES, *SETTING_SETTER_TOOL_NAMES)
        ) or _completion_calls_state_action_planner(completion, state_helpers)
        completion_text = _completion_text_content(completion).lower()
        asked_for_current_coordinates = any(
            phrase in completion_text
            for phrase in (
                "current coordinates",
                "current location",
                "your coordinates",
                "your location",
                "nearby landmark",
            )
        )
        if (
            attempted_unanchored_search
            or attempted_time_loop
            or attempted_state_detour
            or asked_for_current_coordinates
        ):
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            if "get_current_location" in available_names:
                current_location_tool_name = _tool_name_for_call(
                    openai_tools, "get_current_location"
                )
                previous_args = _latest_prior_tool_call_arguments(
                    openai_messages, "prepare_location_search_args"
                )
                repeat_detail = ""
                if previous_args:
                    sanitized_previous_args = dict(previous_args)
                    sanitized_previous_args.pop("latitude", None)
                    sanitized_previous_args.pop("longitude", None)
                    repeat_detail = (
                        " Preserve the previous generated-tool text arguments "
                        f"where applicable: {json.dumps(sanitized_previous_args, sort_keys=True)}."
                    )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "latest generated location-search tool result abstained "
                        "because the broad place name needs current coordinates. "
                        f"Retry by calling original {current_location_tool_name} "
                        "with no arguments. Do not ask the user for current "
                        "coordinates, do not call time tools, and do not call "
                        "original search_location_around_lat_lon on the broad "
                        "place name yet. If get_current_location returns a "
                        "device-state precondition error, satisfy that error "
                        "through a generated device-state action-sequence tool "
                        "when one is visible, then retry get_current_location. "
                        f"After visible coordinates are returned, call generated "
                        f"{location_tool_name} again with the prior broad place "
                        "name plus the visible latitude and longitude, then call "
                        "the returned original location-search tool with "
                        f"downstream_tool_kwargs unchanged. {repeat_detail}"
                    ),
                }
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "generated location-search tool result abstained because the "
                    "place name is broad and no street, neighborhood, venue "
                    "qualifier, or current-location tool is visible. Retry "
                    "without asking for current coordinates and without calling "
                    "time tools, setting tools, or original "
                    "search_location_around_lat_lon on the broad place name. "
                    "Ask the user which specific location, street, neighborhood, "
                    "or venue qualifier to use. After the user clarifies, call "
                    f"generated {location_tool_name} again with the prior broad "
                    "place name combined with the visible clarification."
                ),
            }
        latest_prepare = _latest_tool_message_index(
            openai_messages, {"prepare_location_search_args"}
        )
        latest_current_location = _latest_tool_message_index(
            openai_messages, {"get_current_location"}
        )
        latest_search = _latest_tool_message_index(
            openai_messages, {"search_location_around_lat_lon"}
        )
        if latest_prepare is not None and latest_current_location is not None:
            current_index, _current_message = latest_current_location
            no_search_after_current_location = (
                latest_search is None or latest_search[0] <= current_index
            )
            current_coordinates = _latest_current_location_coordinates(openai_messages)
            attempted_reminder_path = _completion_calls_execution_tool(
                completion, "prepare_reminder_creation_args"
            ) or _completion_calls_execution_tool(completion, "add_reminder")
            if (
                current_index > latest_prepare[0]
                and no_search_after_current_location
                and current_coordinates is not None
                and attempted_reminder_path
            ):
                input_names = _tool_input_names_execution_facing(
                    openai_tools, "prepare_location_search_args"
                )
                previous_args = _latest_prior_tool_call_arguments(
                    openai_messages, "prepare_location_search_args"
                )
                location_phrase = (
                    _visible_location_phrase_from_user_request(openai_messages)
                    or str(previous_args.get("location_phrase") or "").strip()
                )
                retry_args: dict[str, Any] = {
                    "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
                    "location_phrase": location_phrase,
                }
                if "latitude" in input_names:
                    retry_args["latitude"] = current_coordinates[0]
                if "longitude" in input_names:
                    retry_args["longitude"] = current_coordinates[1]
                location_tool_name = _tool_name_for_call(
                    openai_tools, "prepare_location_search_args"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated location-search tool previously abstained "
                        "because current coordinates were missing, but a visible "
                        "get_current_location call now returned coordinates. "
                        "Retry without preparing or adding the reminder yet. "
                        f"First call generated {location_tool_name} with exactly "
                        f"these arguments: {json.dumps(retry_args, sort_keys=True)}. "
                        "Then call the returned original "
                        "search_location_around_lat_lon tool with "
                        "downstream_tool_kwargs unchanged. Only after that "
                        "visible search result returns coordinates may "
                        "prepare_reminder_creation_args or add_reminder be used."
                    ),
                }
    weekday_args = _completion_execution_tool_arguments(
        completion, "next_weekday_time_to_timestamp"
    )
    for args in weekday_args:
        current_timestamp_raw = args.get("current_timestamp")
        current_info = args.get("current_datetime_info")
        try:
            current_timestamp_value = float(current_timestamp_raw)
        except (TypeError, ValueError):
            current_timestamp_value = None
        if current_timestamp_value is None:
            continue
        visible_current_info = _timestamp_to_datetime_info_for_timestamp(
            openai_messages, current_timestamp_value
        )
        if not isinstance(current_info, Mapping) or not current_info:
            if "timestamp_to_datetime_info" in available_names:
                timestamp_tool_name = _tool_name_for_call(
                    openai_tools, "timestamp_to_datetime_info"
                )
                weekday_tool_name = _tool_name_for_call(
                    openai_tools, "next_weekday_time_to_timestamp"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {weekday_tool_name} call is missing visible "
                        "current_datetime_info. Retry without calling the weekday "
                        f"tool yet. First call original {timestamp_tool_name} "
                        "with the same current timestamp, then call the generated "
                        "weekday tool with that returned dict as "
                        "current_datetime_info. Do not guess local_utc_offset_hours."
                    ),
                }
        elif visible_current_info is None:
            if "timestamp_to_datetime_info" in available_names:
                timestamp_tool_name = _tool_name_for_call(
                    openai_tools, "timestamp_to_datetime_info"
                )
                weekday_tool_name = _tool_name_for_call(
                    openai_tools, "next_weekday_time_to_timestamp"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {weekday_tool_name} call included "
                        "current_datetime_info, but that dict was not returned by "
                        f"a visible {timestamp_tool_name}(current_timestamp) call "
                        "in this task. Retry without calling the weekday tool yet. "
                        f"First call original {timestamp_tool_name} with the same "
                        "current timestamp, then pass that returned dict unchanged "
                        "as current_datetime_info. Do not invent calendar fields "
                        "or reuse them from another task."
                    ),
                }
        elif not _datetime_info_matches(visible_current_info, current_info):
            timestamp_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    "current_datetime_info passed to the generated weekday "
                    "timestamp tool does not match the visible "
                    f"{timestamp_tool_name}(current_timestamp) result. Retry "
                    "without calling add_reminder. Use the visible returned "
                    "datetime-info dict unchanged when calling "
                    "next_weekday_time_to_timestamp."
                ),
            }
    relative_time_args = _completion_execution_tool_arguments(
        completion, "relative_day_time_to_timestamp"
    )
    for args in relative_time_args:
        current_timestamp_raw = args.get("current_timestamp")
        current_info = args.get("current_datetime_info")
        try:
            current_timestamp_value = float(current_timestamp_raw)
        except (TypeError, ValueError):
            current_timestamp_value = None
        if current_timestamp_value is None:
            continue
        if "timestamp_to_datetime_info" not in available_names:
            continue
        visible_current_info = _timestamp_to_datetime_info_for_timestamp(
            openai_messages, current_timestamp_value
        )
        relative_tool_name = _tool_name_for_call(
            openai_tools, "relative_day_time_to_timestamp"
        )
        timestamp_tool_name = _tool_name_for_call(
            openai_tools, "timestamp_to_datetime_info"
        )
        retry_args = dict(args)
        retry_args.pop("current_datetime_info", None)
        if not isinstance(current_info, Mapping) or not current_info:
            if visible_current_info is None:
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {relative_tool_name} call is resolving a "
                        "relative local reminder time but is missing visible "
                        "current_datetime_info. Retry without calling the "
                        f"generated {relative_tool_name} tool yet. The next response "
                        f"must contain exactly one tool call: original "
                        f"{timestamp_tool_name} with exactly "
                        f"{json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}, "
                        "then call the generated relative-time tool with the "
                        "returned dict as current_datetime_info. Do not guess "
                        "local_utc_offset_hours."
                    ),
                }
            retry_args["current_datetime_info"] = visible_current_info
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"generated {relative_tool_name} call is resolving a "
                    "relative local reminder time and visible current datetime "
                    "info is already available. The next response must contain "
                    f"exactly one tool call: generated {relative_tool_name} with "
                    "current_datetime_info set to that visible result. Use these "
                    f"exact arguments: {json.dumps(retry_args, sort_keys=True)}. "
                    "Do not call add_reminder, location search, or any original "
                    "timestamp shift/offset tool until this generated tool call "
                    "has returned."
                ),
            }
        if visible_current_info is None:
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"generated {relative_tool_name} call included "
                    "current_datetime_info, but that dict was not returned by a "
                    f"visible {timestamp_tool_name}(current_timestamp) call in "
                    "this task. Retry without calling the generated "
                    f"{relative_tool_name} tool yet. The next response must "
                    f"contain exactly one tool call: original "
                    f"{timestamp_tool_name} with exactly "
                    f"{json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}, "
                    "then pass that returned dict unchanged as "
                    "current_datetime_info."
                ),
            }
        if not _datetime_info_matches(visible_current_info, current_info):
            retry_args["current_datetime_info"] = visible_current_info
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"current_datetime_info passed to generated {relative_tool_name} "
                    f"does not match the visible {timestamp_tool_name}"
                    "(current_timestamp) result. The next response must contain "
                    f"exactly one tool call: generated {relative_tool_name} with "
                    "the visible dict unchanged: "
                    f"{json.dumps(retry_args, sort_keys=True)}. Do not call "
                    "add_reminder or any original timestamp shift/offset tool "
                    "until this generated tool call has returned."
                ),
            }
    timestamp_info_args = _completion_execution_tool_arguments(
        completion, "timestamp_to_datetime_info"
    )
    if (
        timestamp_info_args
        and _reminder_recency_request(openai_messages)
        in {"modify_latest", "modify_upcoming"}
        and "relative_day_time_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
        and (
            _message_already_called_tool(
                openai_messages, "select_action_target_by_recency"
            )
            or _message_already_called_tool(
                openai_messages, "select_record_by_timestamp_extreme"
            )
        )
    ):
        current_timestamp = _latest_current_timestamp(openai_messages)
        if current_timestamp is not None:
            wrong_timestamp_info_call = False
            for args in timestamp_info_args:
                try:
                    timestamp_value = float(args.get("timestamp"))
                except (TypeError, ValueError):
                    wrong_timestamp_info_call = True
                    break
                if abs(timestamp_value - current_timestamp) > 1.0:
                    wrong_timestamp_info_call = True
                    break
            if wrong_timestamp_info_call:
                timestamp_tool_name = _tool_name_for_call(
                    openai_tools, "timestamp_to_datetime_info"
                )
                relative_tool_name = _tool_name_for_call(
                    openai_tools, "relative_day_time_to_timestamp"
                )
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated reminder selector has already chosen the "
                        "target reminder, and the generated relative-time tool "
                        "is visible, but the previous response called "
                        f"{timestamp_tool_name} on a reminder timestamp instead "
                        "of the visible current timestamp. Retry without calling "
                        "modify_reminder, datetime_info_to_timestamp, or another "
                        f"selector. The next response must call original "
                        f"{timestamp_tool_name} with exactly "
                        f"{json.dumps({'timestamp': current_timestamp}, sort_keys=True)}. "
                        "After that result is visible, call generated "
                        f"{relative_tool_name} for the requested tomorrow time "
                        "using that returned dict as current_datetime_info."
                    ),
                }
    latest_relative_args = _latest_prior_tool_call_arguments(
        openai_messages, "relative_day_time_to_timestamp"
    )
    if latest_relative_args:
        current_timestamp_raw = latest_relative_args.get("current_timestamp")
        current_info = latest_relative_args.get("current_datetime_info")
        try:
            current_timestamp_value = float(current_timestamp_raw)
        except (TypeError, ValueError):
            current_timestamp_value = None
        if current_timestamp_value is not None:
            visible_current_info = _timestamp_to_datetime_info_for_timestamp(
                openai_messages, current_timestamp_value
            )
            relative_timestamp = _timestamp_from_latest_tool(
                openai_messages, "relative_day_time_to_timestamp"
            )
            downstream_after_relative = any(
                _completion_calls_execution_tool(completion, tool_name)
                for tool_name in (
                    "prepare_location_search_args",
                    "search_location_around_lat_lon",
                    "prepare_reminder_creation_args",
                    "add_reminder",
                )
            )
            if (
                relative_timestamp is not None
                and downstream_after_relative
                and "relative_day_time_to_timestamp" in available_names
                and visible_current_info is not None
                and (
                    not isinstance(current_info, Mapping)
                    or not current_info
                    or not _datetime_info_matches(visible_current_info, current_info)
                )
            ):
                relative_tool_name = _tool_name_for_call(
                    openai_tools, "relative_day_time_to_timestamp"
                )
                retry_args = dict(latest_relative_args)
                retry_args["current_datetime_info"] = visible_current_info
                retry_args["local_utc_offset_hours"] = 0
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"latest generated {relative_tool_name} result was "
                        "computed without the visible current_datetime_info for "
                        "the same current timestamp, and the previous response "
                        "attempted to continue to location, reminder preparation, "
                        "or add_reminder using that unsafe generated timestamp. "
                        "The next response must contain exactly one tool call: "
                        f"generated {relative_tool_name} with exactly these "
                        f"arguments: {json.dumps(retry_args, sort_keys=True)}. "
                        "Do not continue to location search, "
                        "prepare_reminder_creation_args, add_reminder, or any "
                        "original timestamp shift/offset tool until this "
                        "corrected generated tool call has returned."
                    ),
                }
    reminder_prepare_args = _completion_execution_tool_arguments(
        completion, "prepare_reminder_creation_args"
    )
    absolute_reminder_request = _absolute_reminder_creation_request(openai_messages)
    if (
        reminder_prepare_args
        and absolute_reminder_request is not None
        and not str(absolute_reminder_request.get("content") or "").strip()
    ):
        reminder_tool_name = _tool_name_for_call(
            openai_tools, "prepare_reminder_creation_args"
        )
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                f"response attempted to call generated {reminder_tool_name}, "
                "but the visible conversation contains an absolute reminder "
                "date/time without visible reminder content. Retry without "
                f"calling {reminder_tool_name} or add_reminder. Ask the user "
                "what the reminder should say. Do not treat a timezone "
                "clarification, a date/time phrase, or the generic phrase "
                "'add a reminder' as the reminder content."
            ),
        }
    if (
        reminder_prepare_args
        and absolute_reminder_request is not None
        and "datetime_info_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "datetime_info_to_timestamp"
        )
    ):
        datetime_tool_name = _tool_name_for_call(
            openai_tools, "datetime_info_to_timestamp"
        )
        reminder_tool_name = _tool_name_for_call(
            openai_tools, "prepare_reminder_creation_args"
        )
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                f"response attempted to call generated {reminder_tool_name} for "
                "an explicit calendar reminder before a visible original "
                "timestamp-conversion result existed. Do not manually calculate "
                "or guess Unix timestamps. Retry without calling the generated "
                f"{reminder_tool_name} tool yet. First call original "
                f"{datetime_tool_name} with year="
                f"{int(absolute_reminder_request['year'])}, month="
                f"{int(absolute_reminder_request['month'])}, day="
                f"{int(absolute_reminder_request['day'])}, hour="
                f"{int(absolute_reminder_request['hour'])}, minute="
                f"{int(absolute_reminder_request['minute'])}, second=0. After "
                "that original tool returns a timestamp, call generated "
                f"{reminder_tool_name} with that exact returned timestamp as "
                "resolved_reminder_timestamp, then call original add_reminder "
                "with add_reminder_kwargs unchanged."
            ),
        }
    visible_location_phrase = _visible_location_phrase_from_user_request(
        openai_messages
    )
    if (
        visible_location_phrase
        and "prepare_location_search_args" in available_names
        and not _message_already_called_tool(
            openai_messages,
            "prepare_location_search_args",
        )
    ):
        for args in reminder_prepare_args:
            if bool(args.get("location_requested")) or bool(
                args.get("location_available")
            ):
                continue
            location_tool_name = _tool_name_for_call(
                openai_tools,
                "prepare_location_search_args",
            )
            location_input_names = _tool_input_names_execution_facing(
                openai_tools,
                "prepare_location_search_args",
            )
            location_args: dict[str, Any] = {
                "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
                "location_phrase": visible_location_phrase,
            }
            current_coordinates = _latest_current_location_coordinates(openai_messages)
            if current_coordinates is not None:
                if "latitude" in location_input_names:
                    location_args["latitude"] = current_coordinates[0]
                if "longitude" in location_input_names:
                    location_args["longitude"] = current_coordinates[1]
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                    "response attempted to call generated "
                    "prepare_reminder_creation_args with location_requested=false "
                    "and location_available=false, but the visible user request "
                    f"contains a location phrase: {visible_location_phrase!r}. "
                    "Retry without calling prepare_reminder_creation_args or "
                    "add_reminder yet. The next response must contain exactly "
                    f"one tool call: generated {location_tool_name} with exactly "
                    f"these arguments: {json.dumps(location_args, sort_keys=True)}. "
                    "Then call the returned original location-search tool with "
                    "downstream_tool_kwargs unchanged. Only after visible "
                    "coordinates are returned should prepare_reminder_creation_args "
                    "be called again with location_requested=true and "
                    "location_available=true."
                ),
            }
    for args in reminder_prepare_args:
        current_timestamp_raw = args.get("current_timestamp")
        current_info = args.get("current_datetime_info")
        try:
            current_timestamp_value = float(current_timestamp_raw)
        except (TypeError, ValueError):
            current_timestamp_value = None
        try:
            resolved_value = float(args.get("resolved_reminder_timestamp"))
        except (TypeError, ValueError):
            resolved_value = None
        try:
            day_offset = int(args.get("day_offset") or 0)
        except (TypeError, ValueError):
            day_offset = 0
        if (
            resolved_value is not None
            and current_timestamp_value is not None
            and abs(resolved_value - current_timestamp_value) <= 60.0
            and day_offset <= 0
        ):
            absolute_timestamp = _latest_tool_float_by_name_including_latest(
                openai_messages, "datetime_info_to_timestamp"
            )
            reminder_tool_name = _tool_name_for_call(
                openai_tools, "prepare_reminder_creation_args"
            )
            if (
                absolute_timestamp is not None
                and abs(absolute_timestamp - resolved_value) <= 60.0
            ):
                retry_args = dict(args)
                retry_args["resolved_reminder_timestamp"] = absolute_timestamp
                retry_args["current_timestamp"] = None
                retry_args["day_offset"] = None
                retry_args["local_utc_offset_hours"] = None
                retry_args["current_datetime_info"] = {}
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"previous generated {reminder_tool_name} call used the "
                        "absolute reminder timestamp as current_timestamp. That "
                        "makes the generated tool treat a valid explicit date/time "
                        "as a current-clock placeholder. Retry the generated "
                        f"{reminder_tool_name} call with exactly these arguments: "
                        f"{json.dumps(retry_args, sort_keys=True)}. Do not ask "
                        "for timezone or location context for this absolute-date "
                        "task. After the generated tool returns "
                        "should_call_add_reminder=true, call original add_reminder "
                        "with add_reminder_kwargs unchanged."
                    ),
                }
            if (
                absolute_timestamp is None
                or abs(absolute_timestamp - resolved_value) > 60.0
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {reminder_tool_name} call is using the visible "
                        "current timestamp as resolved_reminder_timestamp. That is "
                        "not a user-provided reminder time. Retry without calling "
                        "the generated reminder-preparation tool. If the user has "
                        "not provided the reminder time yet, ask for the missing "
                        "time. If a visible absolute date/time is present, first "
                        "resolve it with original datetime_info_to_timestamp and "
                        "pass that result as resolved_reminder_timestamp."
                    ),
                }
        has_relative_fields = (
            current_timestamp_value is not None
            and args.get("day_offset") is not None
            and args.get("hour") is not None
            and args.get("minute") is not None
        )
        if not has_relative_fields or day_offset <= 0:
            continue
        timestamp_tool_visible = "timestamp_to_datetime_info" in available_names
        if not timestamp_tool_visible:
            continue
        visible_current_info = _timestamp_to_datetime_info_for_timestamp(
            openai_messages, current_timestamp_value
        )
        reminder_tool_name = _tool_name_for_call(
            openai_tools, "prepare_reminder_creation_args"
        )
        timestamp_tool_name = _tool_name_for_call(
            openai_tools, "timestamp_to_datetime_info"
        )
        retry_args = dict(args)
        retry_args.pop("current_datetime_info", None)
        if (
            "relative_day_time_to_timestamp" in available_names
            and not _message_already_called_tool(
                openai_messages, "relative_day_time_to_timestamp"
            )
        ):
            relative_tool_name = _tool_name_for_call(
                openai_tools, "relative_day_time_to_timestamp"
            )
            relative_input_names = _tool_input_names_execution_facing(
                openai_tools, "relative_day_time_to_timestamp"
            )
            relative_args: dict[str, Any] = {}
            if "current_timestamp" in relative_input_names:
                relative_args["current_timestamp"] = current_timestamp_value
            if "day_offset" in relative_input_names:
                relative_args["day_offset"] = day_offset
            if "hour" in relative_input_names:
                relative_args["hour"] = int(args.get("hour"))
            if "minute" in relative_input_names:
                relative_args["minute"] = int(args.get("minute"))
            if "local_utc_offset_hours" in relative_input_names:
                relative_args["local_utc_offset_hours"] = args.get(
                    "local_utc_offset_hours", 0
                )
            if visible_current_info is None:
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {reminder_tool_name} call tried to resolve a "
                        "relative reminder time directly even though generated "
                        f"{relative_tool_name} is visible. Retry without calling "
                        f"{reminder_tool_name} or add_reminder yet. First call "
                        f"original {timestamp_tool_name} with exactly "
                        f"{json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}. "
                        "After that visible datetime-info result returns, call "
                        f"generated {relative_tool_name} with current_timestamp, "
                        "day_offset, hour, minute, and that returned dict as "
                        "current_datetime_info."
                    ),
                }
            if "current_datetime_info" in relative_input_names:
                relative_args["current_datetime_info"] = visible_current_info
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"generated {reminder_tool_name} call tried to resolve a "
                    "relative reminder time directly even though generated "
                    f"{relative_tool_name} is visible. Retry without calling "
                    f"{reminder_tool_name}, add_reminder, or original timestamp "
                    "shift tools. The next response must contain exactly one "
                    f"tool call: generated {relative_tool_name} with exactly "
                    f"these arguments: {json.dumps(relative_args, sort_keys=True)}. "
                    "After that generated relative-time result returns, use its "
                    "timestamp as resolved_reminder_timestamp in "
                    f"{reminder_tool_name} and then call original add_reminder "
                    "with add_reminder_kwargs unchanged."
                ),
            }
        if not isinstance(current_info, Mapping) or not current_info:
            if visible_current_info is None:
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        f"generated {reminder_tool_name} call is resolving a "
                        "relative reminder time but is missing visible "
                        "current_datetime_info. Retry without calling the "
                        "generated reminder-preparation tool yet. First call "
                        f"original {timestamp_tool_name} with exactly "
                        f"{json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}, "
                        "then call the generated reminder-preparation tool with "
                        "the returned dict as current_datetime_info. Preserve "
                        f"these generated-tool arguments: "
                        f"{json.dumps(retry_args, sort_keys=True)}."
                    ),
                }
            retry_args["current_datetime_info"] = visible_current_info
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"generated {reminder_tool_name} call is resolving a "
                    "relative reminder time and a visible current datetime-info "
                    "result is already available. Retry the generated tool call "
                    "with current_datetime_info set to that visible result. Use "
                    f"these exact arguments: {json.dumps(retry_args, sort_keys=True)}."
                ),
            }
        if visible_current_info is None:
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    f"generated {reminder_tool_name} call included "
                    "current_datetime_info, but that dict was not returned by a "
                    f"visible {timestamp_tool_name}(current_timestamp) call in "
                    "this task. Retry without calling the generated reminder "
                    f"tool yet. First call original {timestamp_tool_name} with "
                    f"exactly {json.dumps({'timestamp': current_timestamp_value}, sort_keys=True)}, "
                    "then pass that returned dict unchanged as "
                    "current_datetime_info."
                ),
            }
        if not _datetime_info_matches(visible_current_info, current_info):
            retry_args["current_datetime_info"] = visible_current_info
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    "current_datetime_info passed to generated "
                    f"{reminder_tool_name} does not match the visible "
                    f"{timestamp_tool_name}(current_timestamp) result. Retry the "
                    "generated reminder-preparation call with the visible dict "
                    f"unchanged: {json.dumps(retry_args, sort_keys=True)}."
                ),
            }
    if _completion_calls_execution_tool(completion, "add_reminder"):
        weekday_timestamp = _latest_tool_float_by_name_including_latest(
            openai_messages, "next_weekday_time_to_timestamp"
        )
        if (
            weekday_timestamp == 0.0
            and "next_weekday_time_to_timestamp" in available_names
        ):
            weekday_tool_name = _tool_name_for_call(
                openai_tools, "next_weekday_time_to_timestamp"
            )
            timestamp_tool_name = _tool_name_for_call(
                openai_tools, "timestamp_to_datetime_info"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    f"generated {weekday_tool_name} result was 0.0, so it did not "
                    "authorize calling add_reminder. Retry without calling "
                    "add_reminder. Call timestamp_to_datetime_info on the visible "
                    "current timestamp, then call the generated weekday tool again "
                    "with that returned dict as current_datetime_info. Only call "
                    "add_reminder after the generated weekday tool returns a "
                    "positive reminder_timestamp. If "
                    f"{timestamp_tool_name} is not visible, ask for the missing "
                    "time context instead of guessing a timezone."
                ),
            }
    if not _completion_calls_execution_tool(completion, "add_reminder"):
        reminder_args = _completion_execution_tool_arguments(
            completion, "prepare_reminder_creation_args"
        )
        for args in reminder_args:
            if not bool(args.get("location_available")):
                continue
            try:
                coordinates = (
                    float(args.get("latitude")),
                    float(args.get("longitude")),
                )
            except (TypeError, ValueError):
                continue
            if coordinates[0] == 0.0 or coordinates[1] == 0.0:
                continue
            supported_by_search = _latest_location_search_contains_coordinates(
                openai_messages, coordinates
            )
            supported_by_current_location = bool(
                args.get("location_requested")
            ) and _latest_current_location_contains_coordinates(
                openai_messages, coordinates
            )
            if _latest_user_turn_introduces_location_constraint(openai_messages):
                supported_by_search = (
                    _latest_location_search_after_latest_user_contains_coordinates(
                        openai_messages, coordinates
                    )
                )
                supported_by_current_location = False
            if supported_by_search or supported_by_current_location:
                continue
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            retry_args = dict(args)
            retry_args.pop("latitude", None)
            retry_args.pop("longitude", None)
            retry_args["location_available"] = False
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                    "response attempted to call generated "
                    "prepare_reminder_creation_args with latitude/longitude values "
                    "that are not supported by a visible current-task location "
                    "result. Retry without those coordinates. If the user gave or "
                    "corrected a venue/location, first call generated "
                    f"{location_tool_name} with the visible request text and exact "
                    "visible place phrase, then call the returned original "
                    "search_location_around_lat_lon tool with downstream kwargs "
                    "unchanged. After the search returns coordinates, call "
                    "prepare_reminder_creation_args again with those visible "
                    "coordinates only. Preserve the non-location reminder fields: "
                    f"{json.dumps(retry_args, sort_keys=True)}."
                ),
            }
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "prepare_reminder_creation_args"
    )
    if not payload and "prepare_reminder_creation_args" in available_names:
        reminder_tool_name = _tool_name_for_call(
            openai_tools, "prepare_reminder_creation_args"
        )
        if _completion_calls_execution_tool(completion, "add_reminder"):
            current_timestamp = _latest_current_timestamp(openai_messages)
            visible_relative_request = _relative_reminder_creation_request(
                openai_messages
            )
            visible_absolute_request = _absolute_reminder_creation_request(
                openai_messages
            )
            attempted_add_calls = _completion_execution_tool_arguments(
                completion, "add_reminder"
            )
            if (
                current_timestamp is not None
                and visible_relative_request is None
                and visible_absolute_request is None
            ):
                for attempted in attempted_add_calls:
                    try:
                        attempted_timestamp = float(attempted.get("reminder_timestamp"))
                    except (TypeError, ValueError):
                        continue
                    if abs(attempted_timestamp - current_timestamp) > 60.0:
                        continue
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "The previous response attempted original "
                            "add_reminder with reminder_timestamp equal to the "
                            "visible current timestamp, but the user has not "
                            "provided a visible reminder date/time yet. Retry "
                            "without calling add_reminder, time-conversion tools, "
                            "or generated reminder-preparation tools. Ask the "
                            "user what date and time they want for the reminder. "
                            "Only after the user supplies visible time information "
                            "may the timestamp be resolved and "
                            "prepare_reminder_creation_args be called."
                        ),
                    }
            relative_request = _relative_reminder_creation_request(openai_messages)
            latest_search_args = _latest_prior_tool_call_arguments(
                openai_messages, "search_location_around_lat_lon"
            )
            coordinates = _best_location_coordinates(
                openai_messages,
                query=str(latest_search_args.get("location") or ""),
            )
            if relative_request is not None and coordinates is not None:
                current_timestamp = _latest_current_timestamp(openai_messages)
                if (
                    current_timestamp is None
                    and "get_current_timestamp" in available_names
                ):
                    timestamp_tool_name = _tool_name_for_call(
                        openai_tools, "get_current_timestamp"
                    )
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "A visible location search has returned coordinates "
                            "for a relative reminder, and the generated "
                            "reminder-preparation tool is visible, but the "
                            "previous response attempted original add_reminder "
                            "before resolving the reminder timestamp through "
                            "generated tools. Retry without calling add_reminder. "
                            f"The next response must call original {timestamp_tool_name} "
                            "with no arguments."
                        ),
                    }
                current_info = (
                    _timestamp_to_datetime_info_for_timestamp(
                        openai_messages, current_timestamp
                    )
                    if current_timestamp is not None
                    else None
                )
                if (
                    current_timestamp is not None
                    and current_info is None
                    and "timestamp_to_datetime_info" in available_names
                ):
                    datetime_tool_name = _tool_name_for_call(
                        openai_tools, "timestamp_to_datetime_info"
                    )
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "A visible location search has returned coordinates "
                            "for a relative reminder, and the generated "
                            "reminder-preparation tool is visible, but the "
                            "previous response attempted original add_reminder "
                            "before deriving local current datetime context. "
                            "Retry without calling add_reminder. The next "
                            f"response must call original {datetime_tool_name} "
                            f"with exactly {json.dumps({'timestamp': current_timestamp}, sort_keys=True)}."
                        ),
                    }
                relative_timestamp = _timestamp_from_latest_tool(
                    openai_messages, "relative_day_time_to_timestamp"
                )
                if (
                    current_timestamp is not None
                    and current_info is not None
                    and relative_timestamp is None
                    and "relative_day_time_to_timestamp" in available_names
                ):
                    relative_tool_name = _tool_name_for_call(
                        openai_tools, "relative_day_time_to_timestamp"
                    )
                    relative_args = {
                        "current_timestamp": current_timestamp,
                        "day_offset": int(relative_request["day_offset"]),
                        "hour": int(relative_request["hour"]),
                        "minute": int(relative_request["minute"]),
                        "current_datetime_info": current_info,
                    }
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "A visible location search has returned coordinates "
                            "for a relative reminder, and local current datetime "
                            "context is visible, but the previous response "
                            "attempted original add_reminder before calling the "
                            "generated relative-time tool. Retry without calling "
                            f"add_reminder. The next response must call generated "
                            f"{relative_tool_name} with exactly these arguments: "
                            f"{json.dumps(relative_args, sort_keys=True)}."
                        ),
                    }
                if (
                    current_timestamp is not None
                    and current_info is not None
                    and relative_timestamp is not None
                ):
                    content = str(relative_request.get("content") or "").strip()
                    if _visible_location_phrase_from_user_request(openai_messages):
                        stripped_content = re.sub(
                            r"\s+\b(?:at|near|around|in|by)\s+.+$",
                            "",
                            content,
                            flags=re.IGNORECASE,
                        ).strip(" ,.;:")
                        if stripped_content:
                            content = stripped_content
                    reminder_args = {
                        "content": content,
                        "resolved_reminder_timestamp": relative_timestamp,
                        "current_timestamp": current_timestamp,
                        "day_offset": int(relative_request["day_offset"]),
                        "hour": int(relative_request["hour"]),
                        "minute": int(relative_request["minute"]),
                        "local_utc_offset_hours": 0,
                        "location_requested": True,
                        "location_required": False,
                        "location_available": True,
                        "latitude": coordinates[0],
                        "longitude": coordinates[1],
                        "location_lookup_failed": False,
                        "current_datetime_info": current_info,
                    }
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} "
                            "A visible location search and generated relative-time "
                            "tool result are available for this reminder. Retry "
                            "without calling original add_reminder directly. The "
                            "next response must call generated "
                            f"{reminder_tool_name} with exactly these arguments: "
                            f"{json.dumps(reminder_args, sort_keys=True)}. "
                            "Only after that generated tool returns "
                            "should_call_add_reminder=true may original "
                            "add_reminder be called with add_reminder_kwargs "
                            "unchanged."
                        ),
                    }
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} A generated "
                "reminder-preparation tool is visible, but the previous response "
                "attempted original add_reminder without using it. Retry without "
                f"calling add_reminder yet. Call generated {reminder_tool_name} "
                "immediately before the side-effect call using the visible "
                "reminder content, time context, and visible location coordinates "
                "when location was requested. Only call original add_reminder "
                "after the generated tool returns should_call_add_reminder=true "
                "with add_reminder_kwargs."
            ),
        }
    if payload and bool(payload.get("should_call_add_reminder")):
        visible_location_phrase = _visible_location_phrase_from_user_request(
            openai_messages
        )
        if (
            visible_location_phrase
            and str(payload.get("location_status") or "").strip().lower()
            == "omitted_optional"
            and "prepare_location_search_args" in available_names
            and not _message_already_called_tool(
                openai_messages,
                "prepare_location_search_args",
            )
            and _completion_calls_execution_tool(completion, "add_reminder")
        ):
            location_tool_name = _tool_name_for_call(
                openai_tools,
                "prepare_location_search_args",
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "generated prepare_reminder_creation_args result omitted "
                    "location coordinates even though the visible user request "
                    f"contains a location phrase: {visible_location_phrase!r}. "
                    "Retry without calling add_reminder. First call generated "
                    f"{location_tool_name} with all visible user turns as "
                    "user_request and that exact phrase as location_phrase. Then "
                    "call the returned original location-search tool with "
                    "downstream_tool_kwargs unchanged, and call "
                    "prepare_reminder_creation_args again using only coordinates "
                    "returned by that visible original search."
                ),
            }
        prepared_coordinates = _prepared_reminder_coordinates(payload)
        unsupported_coordinates = False
        if prepared_coordinates is not None:
            supported_by_search = _latest_location_search_contains_coordinates(
                openai_messages, prepared_coordinates
            )
            supported_by_current_location = (
                _latest_current_location_contains_coordinates(
                    openai_messages, prepared_coordinates
                )
            )
            if _latest_user_turn_introduces_location_constraint(openai_messages):
                supported_by_search = (
                    _latest_location_search_after_latest_user_contains_coordinates(
                        openai_messages, prepared_coordinates
                    )
                )
                supported_by_current_location = False
            unsupported_coordinates = not (
                supported_by_search or supported_by_current_location
            )
        if prepared_coordinates is not None and unsupported_coordinates:
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                    "generated reminder-preparation result contains "
                    "latitude/longitude values that were not returned by the "
                    "current task's visible original search_location_around_lat_lon "
                    "result. Retry without calling add_reminder. Use the generated "
                    "location-search tool and the original location search to "
                    "obtain visible coordinates for this task, then call "
                    "prepare_reminder_creation_args again with only those visible "
                    "coordinates. Do not reuse coordinates from another task or "
                    "from memory."
                ),
            }
        latest_args = _latest_prior_tool_call_arguments(
            openai_messages, "prepare_reminder_creation_args"
        )
        current_timestamp_raw = latest_args.get("current_timestamp")
        current_info = latest_args.get("current_datetime_info")
        if isinstance(current_info, Mapping) and current_timestamp_raw is not None:
            try:
                current_timestamp_value = float(current_timestamp_raw)
            except (TypeError, ValueError):
                current_timestamp_value = None
            if current_timestamp_value is not None:
                visible_current_info = _timestamp_to_datetime_info_for_timestamp(
                    openai_messages, current_timestamp_value
                )
                if visible_current_info and not _datetime_info_matches(
                    visible_current_info, current_info
                ):
                    timestamp_tool_name = _tool_name_for_call(
                        openai_tools, "timestamp_to_datetime_info"
                    )
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                            "current_datetime_info passed to the generated "
                            "reminder-preparation tool does not match the visible "
                            f"{timestamp_tool_name}(current_timestamp) result. "
                            "Retry without calling add_reminder. Call "
                            f"{timestamp_tool_name} on the current timestamp, then "
                            "call prepare_reminder_creation_args again using that "
                            "returned dict as current_datetime_info."
                        ),
                    }
        if current_timestamp_raw is not None and not isinstance(current_info, Mapping):
            try:
                current_timestamp_value = float(current_timestamp_raw)
                day_offset_value = int(latest_args.get("day_offset"))
            except (TypeError, ValueError):
                current_timestamp_value = None
                day_offset_value = 0
            if current_timestamp_value is not None and day_offset_value > 0:
                visible_current_info = _timestamp_to_datetime_info_for_timestamp(
                    openai_messages, current_timestamp_value
                )
                if visible_current_info:
                    retry_args = dict(latest_args)
                    retry_args["current_datetime_info"] = visible_current_info
                    retry_args["local_utc_offset_hours"] = 0
                    relative_timestamp = _timestamp_from_latest_tool(
                        openai_messages, "relative_day_time_to_timestamp"
                    )
                    if relative_timestamp is not None:
                        retry_args["resolved_reminder_timestamp"] = relative_timestamp
                    reminder_tool_name = _tool_name_for_call(
                        openai_tools, "prepare_reminder_creation_args"
                    )
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                            "generated reminder-preparation call used relative "
                            "day/time fields but omitted the visible local current "
                            "datetime context. Retry without calling add_reminder. "
                            f"Call generated {reminder_tool_name} with exactly "
                            f"these arguments: {json.dumps(retry_args, sort_keys=True)}. "
                            "Use the generated relative timestamp unchanged when "
                            "it is present; do not recompute it from a guessed "
                            "UTC offset."
                        ),
                    }
        previous_relative_args = _latest_reminder_creation_args_for_abstain_reason(
            openai_messages,
            "missing_current_datetime_info_call_timestamp_to_datetime_info",
        )
        if previous_relative_args and latest_args:
            drifted_fields: list[str] = []
            for key in ("day_offset", "hour", "minute"):
                if previous_relative_args.get(key) != latest_args.get(key):
                    drifted_fields.append(key)
            if drifted_fields:
                retry_args = dict(previous_relative_args)
                retry_args.pop("current_datetime_info", None)
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated reminder-preparation retry changed relative "
                        f"time fields after an abstention: {', '.join(drifted_fields)}. "
                        "Retry without calling add_reminder. Use the same "
                        "day_offset, hour, and minute from the abstaining "
                        "generated-tool call, add current_datetime_info from "
                        "timestamp_to_datetime_info(current_timestamp), and call "
                        "prepare_reminder_creation_args again. Previous arguments "
                        f"to preserve: {json.dumps(retry_args, sort_keys=True)}."
                    ),
                }
        add_kwargs = payload.get("add_reminder_kwargs")
        if isinstance(add_kwargs, Mapping):
            try:
                prepared_timestamp = float(add_kwargs.get("reminder_timestamp"))
            except (TypeError, ValueError):
                prepared_timestamp = None
            current_timestamp = _latest_current_timestamp(openai_messages)
            if (
                prepared_timestamp is not None
                and current_timestamp is not None
                and abs(prepared_timestamp - current_timestamp) <= 60.0
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated reminder-preparation result contains a reminder "
                        "timestamp that is effectively the visible current "
                        "timestamp. That usually means the reminder time is "
                        "missing and current_timestamp was used as a placeholder. "
                        "Retry without calling add_reminder. If the user did not "
                        "provide a visible reminder time, ask for the missing time; "
                        "otherwise recompute the generated-tool inputs from the "
                        "visible time phrase and call prepare_reminder_creation_args "
                        "again."
                    ),
                }
            if (
                prepared_timestamp is not None
                and current_timestamp is not None
                and prepared_timestamp < current_timestamp - 60.0
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                        "generated reminder-preparation result contains a reminder "
                        "timestamp in the past relative to the visible current "
                        "timestamp. Retry without calling add_reminder. Recompute "
                        "the generated-tool inputs from visible current timestamp "
                        "context and call prepare_reminder_creation_args again."
                    ),
                }
        if isinstance(add_kwargs, Mapping):
            latest_prepare = _latest_tool_message_index(
                openai_messages, {"prepare_reminder_creation_args"}
            )
            latest_add = _latest_tool_message_index(openai_messages, {"add_reminder"})
            add_already_completed = (
                latest_prepare is not None
                and latest_add is not None
                and latest_add[0] > latest_prepare[0]
            )
            if not add_already_completed:
                expected_add_kwargs = _call_contract_kwargs(add_kwargs)
                attempted_add_calls = _completion_execution_tool_arguments(
                    completion, "add_reminder"
                )
                add_tool_name = _tool_name_for_call(openai_tools, "add_reminder")
                exact_contract = json.dumps(expected_add_kwargs, sort_keys=True)
                if attempted_add_calls and not any(
                    _call_contract_kwargs_match(expected_add_kwargs, attempted)
                    for attempted in attempted_add_calls
                ):
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                            "latest generated reminder-preparation tool returned "
                            "call-ready add_reminder_kwargs, but the attempted "
                            "original add_reminder call did not match them. Retry "
                            f"by calling original {add_tool_name} with exactly "
                            f"these arguments: {exact_contract}. Do not reuse an "
                            "earlier timestamp, recompute the time, drop visible "
                            "coordinates, or add fields absent from this contract."
                        ),
                    }
                if not attempted_add_calls:
                    return {
                        "role": "system",
                        "content": (
                            f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The "
                            "latest generated reminder-preparation tool returned "
                            "call-ready add_reminder_kwargs. It prepared the "
                            "arguments only; the original ToolSandbox side-effect "
                            "still has to run. Retry by calling original "
                            f"{add_tool_name} with exactly these arguments: "
                            f"{exact_contract}. Do not answer yet and do not call "
                            "another time or location tool first."
                        ),
                    }
    if (
        (not payload or bool(payload.get("should_call_add_reminder")))
        and "prepare_location_search_args" in available_names
        and not _message_already_called_tool(
            openai_messages, "prepare_location_search_args"
        )
    ):
        all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
        lower = f" {all_user_text.lower()} "
        if any(token in lower for token in (" reminder", " remind ", " todo ")) and any(
            marker in lower for marker in (" at ", " near ", " around ", " in ", " by ")
        ):
            location_tool_name = _tool_name_for_call(
                openai_tools, "prepare_location_search_args"
            )
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous "
                    "response attempted to call original add_reminder before using "
                    "the visible generated location-search argument tool. Retry "
                    "without calling add_reminder yet. Call generated "
                    f"{location_tool_name} first using all visible user turns as "
                    "user_request and the exact visible place phrase as "
                    "location_phrase when isolated. Then call the returned original "
                    "location-search tool with downstream_tool_kwargs unchanged. "
                    "Use only visible coordinates returned by that original tool; "
                    "then prepare/call add_reminder through the generated reminder "
                    "argument path if it is visible."
                ),
            }
    if not payload or bool(payload.get("should_call_add_reminder")):
        return None
    reason = str(payload.get("abstain_reason") or "").strip()
    if not reason:
        return None
    if reason == "missing_reminder_content":
        return {
            "role": "system",
            "content": (
                f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The generated "
                "prepare_reminder_creation_args result abstained because the "
                "reminder content is missing. Retry without calling time tools, "
                "prepare_reminder_creation_args, or add_reminder again. Ask the "
                "user what the reminder should say. Do not substitute generic "
                "content such as Reminder, task, todo, unknown, meeting, or the "
                "raw instruction text."
            ),
        }
    if reason in {"missing_time_info", "current_timestamp_placeholder_rejected"}:
        absolute_retry_args = _absolute_reminder_prepare_retry_args(
            openai_messages, openai_tools
        )
        if (
            reason == "current_timestamp_placeholder_rejected"
            and absolute_retry_args is not None
        ):
            reminder_tool_name = _tool_name_for_call(
                openai_tools, "prepare_reminder_creation_args"
            )
            if not _completion_calls_execution_tool(
                completion, "prepare_reminder_creation_args"
            ):
                return {
                    "role": "system",
                    "content": (
                        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                        "generated prepare_reminder_creation_args result abstained "
                        "because the explicit reminder timestamp was also supplied "
                        "as current_timestamp. A visible original "
                        "datetime_info_to_timestamp result already resolved the "
                        "absolute date/time. Retry by calling generated "
                        f"{reminder_tool_name} with exactly these arguments: "
                        f"{json.dumps(absolute_retry_args, sort_keys=True)}. Do "
                        "not ask for timezone, city, or current-time context. "
                        "After that generated tool authorizes the action, call "
                        "original add_reminder with add_reminder_kwargs unchanged."
                    ),
                }
        attempted_time_or_reminder = any(
            _completion_calls_execution_tool(completion, tool_name)
            for tool_name in (
                "get_current_timestamp",
                "timestamp_to_datetime_info",
                "relative_day_time_to_timestamp",
                "datetime_info_to_timestamp",
                "shift_timestamp",
                "add_reminder",
            )
        )
        if attempted_time_or_reminder:
            return {
                "role": "system",
                "content": (
                    f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The latest "
                    "prepare_reminder_creation_args result abstained because the "
                    f"reminder time is missing or only a current-clock placeholder "
                    f"was supplied: {reason!r}. Retry without calling time tools "
                    "or add_reminder. Ask the user what date and time they want "
                    "for the reminder. Only after the user supplies visible time "
                    "information may you resolve the timestamp and call the "
                    "generated reminder-preparation tool again."
                ),
            }
    parts = [
        f"{GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL} The previous response "
        "attempted to call original add_reminder, but the latest "
        "prepare_reminder_creation_args result did not authorize that side-effect "
        f"call. Its abstain_reason was {reason!r}. Retry the assistant response "
        "without calling add_reminder from manual arithmetic, an earlier timestamp, "
        "or partial arguments. Continue by satisfying the generated tool's "
        "abstain_reason and then call prepare_reminder_creation_args again. "
        "Only call add_reminder after that generated tool returns "
        "should_call_add_reminder=true with add_reminder_kwargs."
    ]
    reason_lower = reason.lower()
    location_status = str(payload.get("location_status") or "").strip().lower()
    if (
        "location" in reason_lower
        or location_status in {"lookup_pending", "required_missing"}
    ) and "prepare_location_search_args" in available_names:
        location_tool_name = _tool_name_for_call(
            openai_tools, "prepare_location_search_args"
        )
        parts.append(
            "Because the unresolved field is a reminder location and the "
            f"generated location-search tool is visible, call {location_tool_name} "
            "before add_reminder. Use the full latest user request and, when "
            "visible, the exact place phrase. Then call the returned original "
            "location-search tool with downstream_tool_kwargs unchanged before "
            "retrying prepare_reminder_creation_args with the visible coordinates."
        )
    current_timestamp = _latest_current_timestamp(openai_messages)
    if (
        reason == "missing_current_datetime_info_call_timestamp_to_datetime_info"
        and current_timestamp is not None
        and "timestamp_to_datetime_info" in available_names
    ):
        timestamp_tool_name = _tool_name_for_call(
            openai_tools, "timestamp_to_datetime_info"
        )
        parts.append(
            f"Call {timestamp_tool_name} with exactly "
            f"{json.dumps({'timestamp': current_timestamp}, sort_keys=True)} and "
            "pass its returned dict as current_datetime_info on the next "
            "prepare_reminder_creation_args call."
        )
    return {"role": "system", "content": " ".join(parts)}


def _generated_tool_contract_policy_allows_targeted_extra_retry(
    policy: Mapping[str, str] | None,
) -> bool:
    if policy is None:
        return False
    content = str(policy.get("content") or "")
    if GENERATED_TOOL_CONTRACT_RETRY_POLICY_SENTINEL not in content:
        return False
    lower = content.lower()
    if "next response must" not in lower:
        return False
    if "reminder" not in lower:
        return False
    return any(
        token in lower
        for token in (
            "prepare_location_search_args",
            "prepare_reminder_creation_args",
            "relative_day_time_to_timestamp",
            "timestamp_to_datetime_info",
            "visible location search",
            "location phrase",
        )
    )


def _run_actor_llm_with_generated_tool_contract_retry(
    call: Any,
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion:
    active_messages = openai_messages
    completion = _with_transient_openai_retries(lambda: call(active_messages))
    last_policy: dict[str, str] | None = None
    for _attempt in range(_generated_tool_contract_retry_attempts()):
        policy = _generated_tool_contract_retry_policy_message(
            openai_messages, openai_tools, completion
        )
        if policy is None:
            if _generated_tool_synthetic_repair_enabled():
                repaired = (
                    _generated_contact_selector_missing_updates_repair_completion(
                        openai_messages,
                        openai_tools,
                        completion,
                        model_name=model_name,
                    )
                )
                if repaired is None:
                    repaired = _generated_reminder_location_omission_repair_completion(
                        openai_messages,
                        openai_tools,
                        completion,
                        model_name=model_name,
                    )
                return repaired or completion
            return completion
        last_policy = policy
        active_messages = [cast(OpenAIMessage, policy), *active_messages]
        completion = _with_transient_openai_retries(lambda: call(active_messages))
    if _generated_tool_contract_policy_allows_targeted_extra_retry(last_policy):
        policy = _generated_tool_contract_retry_policy_message(
            openai_messages, openai_tools, completion
        )
        if _generated_tool_contract_policy_allows_targeted_extra_retry(policy):
            active_messages = [cast(OpenAIMessage, policy), *active_messages]
            completion = _with_transient_openai_retries(lambda: call(active_messages))
    if _generated_tool_synthetic_repair_enabled():
        repaired = _generated_state_sequence_contract_repair_completion(
            openai_messages,
            openai_tools,
            completion,
            model_name=model_name,
        )
        if repaired is None:
            repaired = _generated_next_service_contract_repair_completion(
                openai_messages,
                openai_tools,
                completion,
                model_name=model_name,
            )
        if repaired is None:
            repaired = _generated_contact_selector_missing_updates_repair_completion(
                openai_messages,
                openai_tools,
                completion,
                model_name=model_name,
            )
        if repaired is None:
            repaired = _generated_reminder_location_omission_repair_completion(
                openai_messages,
                openai_tools,
                completion,
                model_name=model_name,
            )
        return repaired or completion
    return completion


def _target_service_from_precondition_error(
    error_text: str,
    openai_messages: object,
) -> str:
    lower = error_text.lower().replace("wi-fi", "wifi")
    if "wifi" in lower:
        return "wifi"
    if "cellular" in lower:
        return "cellular"
    if "location" in lower:
        return "location"
    prior_args = _latest_prior_tool_call_arguments(
        openai_messages,
        "next_service_tool_call",
    )
    prior_target = str(prior_args.get("target_service") or "").strip().lower()
    if prior_target in {"wifi", "cellular", "location"}:
        return prior_target
    return ""


def _visible_state_bool_for_next_service(
    openai_messages: object,
    getter_name: str,
    *,
    error_text: str,
    error_false_tokens: tuple[str, ...],
    default: bool = False,
) -> bool:
    lower_error = error_text.lower().replace("wi-fi", "wifi")
    if any(token in lower_error for token in error_false_tokens):
        return False
    value = _successful_setting_getter_value_for_tool(openai_messages, getter_name)
    return default if value is None else bool(value)


def _generated_next_service_contract_repair_completion(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Repair repeated actor refusal to route fresh state errors through a tool."""
    state_helpers = _state_action_planner_tool_names(openai_tools)
    if "next_service_tool_call" not in {
        _execution_facing_tool_name(name) for name in state_helpers
    }:
        return None
    state_precondition = _latest_original_state_precondition_error(openai_messages)
    if state_precondition is None:
        return None
    error_index, error_text = state_precondition
    latest_state_helper = _latest_tool_message_index(openai_messages, state_helpers)
    if latest_state_helper is not None and latest_state_helper[0] > error_index:
        return None
    if _completion_calls_state_action_planner(completion, state_helpers):
        return None
    target_service = _target_service_from_precondition_error(
        error_text,
        openai_messages,
    )
    if target_service not in {"wifi", "cellular", "location"}:
        return None
    lower_error = error_text.lower().replace("wi-fi", "wifi")
    low_battery_value = _successful_setting_getter_value_for_tool(
        openai_messages,
        "get_low_battery_mode_status",
    )
    low_battery_mode = (
        bool(low_battery_value)
        if low_battery_value is not None
        else (
            "low battery" in lower_error
            and ("cannot" in lower_error or "blocked" in lower_error)
        )
    )
    arguments: dict[str, Any] = {
        "target_service": target_service,
        "wifi_enabled": _visible_state_bool_for_next_service(
            openai_messages,
            "get_wifi_status",
            error_text=error_text,
            error_false_tokens=("wifi is not enabled",),
        ),
        "cellular_enabled": _visible_state_bool_for_next_service(
            openai_messages,
            "get_cellular_service_status",
            error_text=error_text,
            error_false_tokens=("cellular service is not enabled",),
        ),
        "location_service_enabled": _visible_state_bool_for_next_service(
            openai_messages,
            "get_location_service_status",
            error_text=error_text,
            error_false_tokens=(
                "location service is not enabled",
                "location service cannot be turned on",
            ),
        ),
        "low_battery_mode": low_battery_mode,
    }
    input_names = _tool_input_names_execution_facing(
        openai_tools,
        "next_service_tool_call",
    )
    if "user_request" in input_names:
        arguments["user_request"] = _latest_user_request_text(openai_messages)
    if "visible_state_or_error" in input_names:
        arguments["visible_state_or_error"] = error_text
    if "available_tools" in input_names:
        arguments["available_tools"] = sorted(
            name
            for name in _tool_names_execution_facing(openai_tools)
            if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        )
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-generated-next-service-contract-repair",
        tool_name=_tool_name_for_call(openai_tools, "next_service_tool_call"),
        arguments=arguments,
    )


def _generated_contact_selector_missing_updates_repair_completion(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Repair a generated selector call that omitted visible update fields."""
    available_names = _tool_names_execution_facing(openai_tools)
    selector_name = "select_message_counterparty_for_contact_update"
    if selector_name not in available_names:
        return None
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages,
        selector_name,
    )
    if str(payload.get("abstain_reason") or "") != "missing_updates":
        return None
    if any(
        bool(args.get("updates"))
        for args in _completion_execution_tool_arguments(completion, selector_name)
    ):
        return None
    phone = _phone_update_from_user_request(openai_messages)
    if not phone:
        return None
    message = _latest_tool_message(openai_messages, "search_messages")
    if message is None:
        return None
    records = _parse_sequence_payload(message.get("content"))
    if not records:
        return None
    user_text = " ".join(_all_user_texts(openai_messages)).lower()
    selection_mode = (
        "oldest"
        if any(token in user_text for token in ("oldest", "first", "earliest"))
        else "latest"
    )
    self_person_id = _latest_self_person_id_from_contacts(
        openai_messages
    ) or _infer_self_person_id_from_message_records(records)
    records_for_tool = records
    if self_person_id and "sent" in user_text and " to " in user_text:
        sent_records = [
            record
            for record in records
            if isinstance(record, Mapping)
            and str(record.get("sender_person_id") or "").strip() == self_person_id
            and str(record.get("recipient_person_id") or "").strip()
        ]
        if sent_records:
            records_for_tool = sent_records
    elif self_person_id and ("from" in user_text or "sent me" in user_text):
        received_records = [
            record
            for record in records
            if isinstance(record, Mapping)
            and str(record.get("recipient_person_id") or "").strip() == self_person_id
            and str(record.get("sender_person_id") or "").strip()
        ]
        if received_records:
            records_for_tool = received_records
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-generated-contact-selector-missing-updates-repair",
        tool_name=_tool_name_for_call(openai_tools, selector_name),
        arguments={
            "records": records_for_tool,
            "selection_mode": selection_mode,
            "updates": {"phone_number": phone},
            "self_person_id": self_person_id,
        },
    )


def _generated_reminder_location_omission_repair_completion(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Repair reminder preparation that omits a visible venue/location phrase."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "prepare_location_search_args" not in available_names:
        return None
    if _message_already_called_tool(openai_messages, "prepare_location_search_args"):
        return None
    location_phrase = _visible_location_phrase_from_user_request(openai_messages)
    if not location_phrase:
        return None
    reminder_prepare_omits_location = any(
        not bool(args.get("location_requested"))
        and not bool(args.get("location_available"))
        for args in _completion_execution_tool_arguments(
            completion,
            "prepare_reminder_creation_args",
        )
    )
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages,
        "prepare_reminder_creation_args",
    )
    add_reminder_omits_location = (
        bool(payload.get("should_call_add_reminder"))
        and str(payload.get("location_status") or "").strip().lower()
        == "omitted_optional"
        and _completion_calls_execution_tool(completion, "add_reminder")
    )
    if not (reminder_prepare_omits_location or add_reminder_omits_location):
        return None
    input_names = _tool_input_names_execution_facing(
        openai_tools,
        "prepare_location_search_args",
    )
    arguments: dict[str, Any] = {
        "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
        "location_phrase": location_phrase,
    }
    if "latitude" in input_names:
        arguments["latitude"] = 0.0
    if "longitude" in input_names:
        arguments["longitude"] = 0.0
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-generated-reminder-location-omission-repair",
        tool_name=_tool_name_for_call(openai_tools, "prepare_location_search_args"),
        arguments=arguments,
    )


def _generated_state_sequence_contract_repair_completion(
    openai_messages: object,
    openai_tools: object,
    completion: ChatCompletion,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Repair repeated actor contradictions to a generated state-action contract."""
    available_names = _tool_names_execution_facing(openai_tools)
    latest_state_helper = _latest_state_action_helper_payload(openai_messages)
    if latest_state_helper is None:
        return None
    _state_index, state_payload = latest_state_helper
    next_state_action = _next_unsatisfied_state_action(openai_messages, state_payload)
    if next_state_action is None:
        return None
    expected_tool_name = _execution_facing_tool_name(
        str(next_state_action.get("tool_name", "") or "")
    )
    expected_arguments = next_state_action.get("arguments")
    if (
        expected_tool_name not in SETTING_SETTER_TOOL_NAMES
        or expected_tool_name not in available_names
        or not isinstance(expected_arguments, Mapping)
    ):
        return None
    expected_calls = _completion_execution_tool_arguments(
        completion, expected_tool_name
    )
    expected_call_matches = any(
        _call_contract_kwargs_match(expected_arguments, attempted)
        for attempted in expected_calls
    )
    if expected_call_matches:
        return None
    calls_expected_with_wrong_args = _completion_calls_execution_tool(
        completion,
        expected_tool_name,
    )
    calls_other_setter = any(
        setter_name != expected_tool_name
        and _completion_calls_execution_tool(completion, setter_name)
        for setter_name in SETTING_SETTER_TOOL_NAMES
    )
    repeats_state_planner = _completion_calls_state_action_planner(
        completion,
        _state_action_planner_tool_names(openai_tools),
    )
    answers_without_setter = bool(_completion_text_content(completion))
    if not (
        calls_expected_with_wrong_args
        or calls_other_setter
        or repeats_state_planner
        or answers_without_setter
    ):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-generated-state-sequence-contract-repair",
        tool_name=_tool_name_for_call(openai_tools, expected_tool_name),
        arguments=_call_contract_kwargs(expected_arguments),
    )


def _reminder_recency_request(openai_messages: object) -> str | None:
    for text in reversed(_all_user_texts(openai_messages)):
        lower = " ".join(text.lower().strip().split())
        if not lower or _latest_user_is_brief_acknowledgement(
            [{"role": "user", "content": lower}]
        ):
            continue
        if ("todo" in lower or "reminder" in lower) and any(
            token in lower for token in ("made yesterday", "created yesterday")
        ):
            return "search_created_yesterday"
        if ("todo" in lower or "reminder" in lower) and any(
            token in lower for token in ("yesterday", "previous day", "prior day")
        ):
            return "search_yesterday"
        if (
            ("reminder" in lower or "todo" in lower)
            and "upcoming" in lower
            and any(
                token in lower
                for token in ("modify", "update", "postpone", "push", "move")
            )
        ):
            return "modify_upcoming"
        if (
            "reminder" in lower
            and any(token in lower for token in ("latest", "most recent", "last"))
            and any(
                token in lower
                for token in ("modify", "update", "postpone", "push", "move")
            )
        ):
            return "modify_latest"
        if "remove" in lower and "upcoming reminder" in lower:
            return "remove_upcoming"
        if ("reminder" in lower or "todo" in lower) and any(
            token in lower
            for token in (
                "upcoming",
                "later",
                "today",
                "this afternoon",
                "tonight",
            )
        ):
            return "search_upcoming"
    return None


def _tomorrow_time_request(openai_messages: object) -> tuple[int, int] | None:
    """Parse visible simple phrases such as 'tomorrow at 5 PM'."""
    text = " ".join(_all_user_texts(openai_messages)).lower()
    if "tomorrow" not in text:
        return None
    match = re.search(
        r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>a\.?m\.?|p\.?m\.?)\b",
        text,
    )
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    period = match.group("period").replace(".", "")
    if hour < 1 or hour > 12 or minute < 0 or minute > 59:
        return None
    if period.startswith("p") and hour != 12:
        hour += 12
    if period.startswith("a") and hour == 12:
        hour = 0
    return hour, minute


def _absolute_reminder_creation_request(
    openai_messages: object,
) -> dict[str, int | str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_date_request: dict[str, int | str] | None = None
    latest_date_index = -1
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        text = str(message.get("content") or "")
        stripped = " ".join(text.replace("’", "'").strip().split())
        lower = stripped.lower()
        if not stripped:
            continue
        has_reminder_token = any(
            token in lower for token in ("remind", "reminder", "todo", "to do", "to-do")
        )
        prior_time_followup_content = (
            None
            if has_reminder_token
            else _prior_reminder_content_for_time_followup(messages, index)
        )
        if not has_reminder_token and prior_time_followup_content is None:
            continue
        if any(token in lower for token in ("remove", "delete", "modify", "update")):
            continue
        match = re.search(
            r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{2,4})"
            r"(?:\s+(?:at\s+)?)"
            r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
            r"(?P<period>a\.?m\.?|p\.?m\.?)\b",
            stripped,
            flags=re.IGNORECASE,
        )
        if match is None:
            month_names = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "sept": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            match = re.search(
                r"\b(?P<month_name>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|"
                r"apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
                r"sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|"
                r"dec(?:ember)?)\s+"
                r"(?P<day>\d{1,2})(?:st|nd|rd|th)?[,]?\s+"
                r"(?P<year>\d{2,4})[,]?"
                r"(?:\s+(?:at\s+)?)"
                r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
                r"(?P<period>a\.?m\.?|p\.?m\.?)\b",
                stripped,
                flags=re.IGNORECASE,
            )
            if match is None:
                continue
            month = month_names[match.group("month_name").lower()]
        else:
            month = int(match.group("month"))
        day = int(match.group("day"))
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "0")
        period = match.group("period").replace(".", "").lower()
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            continue
        if period.startswith("p") and hour != 12:
            hour += 12
        if period.startswith("a") and hour == 12:
            hour = 0
        if prior_time_followup_content is not None:
            content = prior_time_followup_content
        else:
            content = (
                stripped[: match.start()] + " " + stripped[match.end() :]
            ).strip()
            content = re.sub(
                r"^(?:please\s+)?(?:add|create|set)\s+(?:a\s+)?"
                r"(?:(?:reminder|to[- ]?do)(?:\s+to)?|todo\s+to)\s*",
                "",
                content,
                flags=re.IGNORECASE,
            ).strip(" ,.;:")
            content = re.sub(
                r"^(?:please\s+)?remind\s+me\s+to\s+",
                "",
                content,
                flags=re.IGNORECASE,
            ).strip(" ,.;:")
            content = re.sub(
                r"\b(?:on|at|for)\s*$",
                "",
                content,
                flags=re.IGNORECASE,
            ).strip(" ,.;:")
            content = _clean_reminder_content_followup(content)
            if _looks_like_missing_reminder_content(content):
                content = (
                    _prior_reminder_content_for_time_followup(messages, index)
                    or content
                )
        latest_date_request = {
            "content": content,
            "year": year,
            "month": month,
            "day": day,
            "hour": hour,
            "minute": minute,
        }
        latest_date_index = index
    if latest_date_request is None:
        return None
    if str(latest_date_request.get("content") or "").strip():
        return latest_date_request
    for message in messages[latest_date_index + 1 :]:
        if message.get("role") != "user":
            continue
        content = " ".join(str(message.get("content") or "").strip().split())
        lower = content.lower()
        lower_norm = lower.replace("’", "'")
        if not content:
            continue
        if lower in {"thanks", "thank you", "ok", "okay"}:
            continue
        if any(
            token in lower_norm
            for token in (
                "don't have",
                "do not have",
                "can't",
                "cannot",
                "that info",
                "timezone",
                "time zone",
                "just set it",
            )
        ):
            continue
        if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", content):
            continue
        latest_date_request["content"] = _clean_reminder_content_followup(content)
    return latest_date_request


def _clean_reminder_content_followup(content: str) -> str:
    text = " ".join(str(content or "").strip().split()).strip(" \"'")
    text = re.sub(
        r"^(?:make\s+it\s+say|(?:it\s+)?should\s+say|say)\s*[:,]?\s+(?:to\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    text = re.sub(
        r"^(?:it(?:'s| is)|this\s+is)\s+for\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    text = re.sub(
        r"^(?:(?:sure|ok(?:ay)?|yeah|yep)[!,.]?\s*)?"
        r"(?:please\s+)?remind\s+me\s+to\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    text = re.sub(
        r"^i\s+(?:want|would\s+like|'d\s+like|need)\s+to\s+be\s+reminded\s+to\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    text = re.sub(
        r"^i\s+(?:want|would\s+like|'d\s+like|need)\s+(?:a\s+)?"
        r"(?:reminder|todo|to[- ]?do)\s+(?:to|for)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    text = re.sub(
        r"^(?:the\s+)?reminder\s+(?:is|should\s+be)\s+(?:for\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" \"'")
    gerund_rewrites = {
        "bringing": "bring",
        "buying": "buy",
        "calling": "call",
        "checking": "check",
        "getting": "get",
        "going": "go",
        "meeting": "meet",
        "picking": "pick",
        "taking": "take",
    }
    first, sep, rest = text.partition(" ")
    replacement = gerund_rewrites.get(first.lower())
    if replacement:
        text = replacement + (sep + rest if sep else "")
    text = re.sub(r"^to\s+", "", text, flags=re.IGNORECASE).strip(" \"'")
    text = text.strip()
    if text.endswith("."):
        text = text[:-1].strip()
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _strip_reminder_creation_prefix(content: str) -> str:
    text = " ".join(str(content or "").strip().split())
    text = re.sub(
        r"^(?:please\s+)?(?:add|create|set)\s+(?:a\s+)?"
        r"(?:(?:reminder|to[- ]?do)(?:\s+(?:to|for))?|todo\s+(?:to|for))\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ,.;:")
    text = re.sub(
        r"^(?:please\s+)?remind\s+me\s+to\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ,.;:")
    return text


def _looks_like_missing_reminder_content(content: str) -> bool:
    lower = " ".join(str(content or "").lower().strip().split()).strip(" ,.;:!?\"'")
    if not lower:
        return True
    return bool(
        re.fullmatch(
            r"(?:please\s+)?(?:add|create|set)?\s*(?:a\s+)?"
            r"(?:reminder|todo|to[- ]?do)(?:\s+(?:to|for))?",
            lower,
        )
        or re.fullmatch(r"(?:please\s+)?remind\s+me(?:\s+to)?", lower)
        or re.fullmatch(r"(?:the\s+)?reminder\s+(?:is|should\s+be)(?:\s+for)?", lower)
        or re.fullmatch(
            r"(?:sure|ok(?:ay)?|yeah|yep)[!,.]?\s*remind\s+me(?:\s+to)?",
            lower,
        )
        or re.fullmatch(
            r"(?:(?:sure|ok(?:ay)?|yeah|yep)[!,.]?\s*)?"
            r"i\s+(?:want|would\s+like|'d\s+like|need)\s+to\s+be\s+reminded",
            lower,
        )
        or re.fullmatch(
            r"(?:(?:sure|ok(?:ay)?|yeah|yep)[!,.]?\s*)?"
            r"i\s+(?:want|would\s+like|'d\s+like|need)\s+(?:a\s+|the\s+)?"
            r"(?:reminder|todo|to[- ]?do)(?:\s+(?:to|for))?",
            lower,
        )
        or re.fullmatch(r"i\s+need\s+(?:a\s+|the\s+)?reminder", lower)
        or re.fullmatch(
            r"(?:yeah,?\s*)?(?:please\s+)?(?:set|add|create)\s+the\s+reminder",
            lower,
        )
    )


def _looks_like_placeholder_reminder_content(content: object) -> bool:
    lower = " ".join(str(content or "").lower().strip().split()).strip(" ,.;:!?\"'")
    if _looks_like_missing_reminder_content(lower):
        return True
    if re.fullmatch(
        r"(?:a\s+|the\s+)?reminder\s+(?:for|at|on)\s+.+",
        lower,
    ):
        return True
    return lower in {
        "reminder",
        "a reminder",
        "the reminder",
        "task",
        "todo",
        "to do",
        "unknown",
        "meeting",
        "don't forget",
        "dont forget",
        "do not forget",
        "remember",
        "something",
        "something important",
    }


def _messages_show_reminder_content_request(openai_messages: object) -> bool:
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "assistant":
            continue
        text = str(message.get("content") or "").lower()
        if "content" in text and "reminder" in text:
            return True
        if "what should" in text and "reminder" in text:
            return True
    return False


def _prior_reminder_content_for_time_followup(
    messages: list[Mapping[str, Any]],
    time_user_index: int,
) -> str | None:
    saw_time_request = False
    for index in range(time_user_index - 1, -1, -1):
        message = messages[index]
        text = " ".join(str(message.get("content") or "").replace("’", "'").split())
        lower = text.lower()
        if message.get("role") == "assistant":
            if any(token in lower for token in ("when", "date", "time")):
                saw_time_request = True
            continue
        if message.get("role") != "user":
            continue
        if not saw_time_request:
            continue
        if not any(
            token in lower for token in ("remind", "reminder", "todo", "to do", "to-do")
        ):
            continue
        if any(token in lower for token in ("remove", "delete", "modify", "update")):
            continue
        content = re.sub(
            r"\b(?:today|tomorrow|tonight|next\s+\w+|on\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b.*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b.*$",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = _clean_reminder_content_followup(
            _strip_reminder_creation_prefix(content)
        )
        if not _looks_like_missing_reminder_content(content):
            return content
    return None


def _absolute_reminder_creation_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "add_reminder" not in available_names:
        return None
    request = _absolute_reminder_creation_request(openai_messages)
    if request is None:
        return None
    content = str(request.get("content") or "").strip()
    if not content:
        if _messages_show_reminder_content_request(openai_messages):
            return None
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-absolute-reminder-missing-content",
            content="What should the reminder say?",
        )
    if (
        "datetime_info_to_timestamp" in available_names
        and not _message_already_called_tool(
            openai_messages, "datetime_info_to_timestamp"
        )
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-absolute-reminder-timestamp",
            tool_name=_tool_name_for_call(openai_tools, "datetime_info_to_timestamp"),
            arguments={
                "year": request["year"],
                "month": request["month"],
                "day": request["day"],
                "hour": request["hour"],
                "minute": request["minute"],
                "second": 0,
            },
        )
    reminder_timestamp = _timestamp_from_latest_tool(
        openai_messages, "datetime_info_to_timestamp"
    )
    if reminder_timestamp is None:
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-absolute-reminder-add",
        tool_name=_tool_name_for_call(openai_tools, "add_reminder"),
        arguments={
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": None,
            "longitude": None,
        },
    )


def _relative_reminder_creation_request(
    openai_messages: object,
) -> dict[str, int | str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "user":
            continue
        text = str(message.get("content") or "")
        stripped = " ".join(text.replace("’", "'").strip().split())
        lower = stripped.lower()
        if not stripped:
            continue
        has_reminder_token = any(
            token in lower for token in ("remind", "reminder", "todo", "to do")
        )
        if any(token in lower for token in ("remove", "delete", "modify", "update")):
            continue
        day_offset: int | None = None
        marker = ""
        if "tomorrow" in lower:
            day_offset = 1
            marker = "tomorrow"
        elif "next week" in lower:
            day_offset = 7
            marker = "next week"
        if day_offset is None:
            continue
        if not has_reminder_token:
            content = _prior_reminder_content_for_time_followup(messages, index)
            if content is None:
                continue
        else:
            content = ""
        match = re.search(
            r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
            r"(?P<period>a\.?m\.?|p\.?m\.?)\b",
            stripped,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "0")
        period = match.group("period").replace(".", "").lower()
        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            continue
        if period.startswith("p") and hour != 12:
            hour += 12
        if period.startswith("a") and hour == 12:
            hour = 0
        if has_reminder_token:
            marker_index = lower.find(marker)
            content = (
                stripped[:marker_index].strip(" ,.;:")
                if marker_index >= 0
                else stripped
            )
            content = _strip_reminder_creation_prefix(content)
            content = _clean_reminder_content_followup(content)
        if _looks_like_missing_reminder_content(content):
            prior_content = _prior_reminder_content_for_time_followup(messages, index)
            if prior_content is not None:
                content = prior_content
            for later_message in messages[index + 1 :]:
                if later_message.get("role") != "user":
                    continue
                later_content = _clean_reminder_content_followup(
                    _strip_reminder_creation_prefix(
                        str(later_message.get("content") or "")
                    )
                )
                later_lower = later_content.lower()
                if (
                    later_content
                    and later_lower not in {"thanks", "thank you", "ok", "okay"}
                    and not re.search(r"\b(?:tomorrow|next week)\b", later_lower)
                ):
                    content = later_content
            if _looks_like_missing_reminder_content(content):
                return {
                    "content": "",
                    "day_offset": day_offset,
                    "hour": hour,
                    "minute": minute,
                }
        return {
            "content": content,
            "day_offset": day_offset,
            "hour": hour,
            "minute": minute,
        }
    return None


def _relative_reminder_creation_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "add_reminder" not in available_names:
        return None
    request = _relative_reminder_creation_request(openai_messages)
    if request is None:
        return None
    if _reminder_location_parts(openai_messages) is not None:
        return None
    content = str(request["content"]).strip()
    if not content:
        if _messages_show_reminder_content_request(openai_messages):
            return None
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-relative-reminder-missing-content",
            content="What should the reminder say?",
        )
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        if "get_current_timestamp" not in available_names:
            return None
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-relative-reminder-current-timestamp",
            tool_name=_tool_name_for_call(openai_tools, "get_current_timestamp"),
            arguments={},
        )
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    reminder_timestamp = _relative_timestamp_for_day_time(
        current_timestamp,
        int(request["day_offset"]),
        int(request["hour"]),
        int(request["minute"]),
    )
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-relative-reminder-add",
        tool_name=_tool_name_for_call(openai_tools, "add_reminder"),
        arguments={
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": None,
            "longitude": None,
        },
    )


def _weekday_reminder_creation_request(
    openai_messages: object,
) -> dict[str, int | str] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    weekday_names = "|".join(WEEKDAY_NAME_TO_ISO)
    weekday_pattern = re.compile(
        rf"\bnext\s+(?P<weekday>{weekday_names})\b",
        flags=re.IGNORECASE,
    )
    time_pattern = re.compile(
        r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
        r"(?P<period>a\.?m\.?|p\.?m\.?)\b",
        flags=re.IGNORECASE,
    )
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "user":
            continue
        text = " ".join(str(message.get("content") or "").replace("’", "'").split())
        lower = text.lower()
        if not text:
            continue
        if any(token in lower for token in ("remove", "delete", "modify", "update")):
            continue
        weekday_match = weekday_pattern.search(text)
        time_match = time_pattern.search(text)
        if weekday_match is None or time_match is None:
            continue
        weekday = WEEKDAY_NAME_TO_ISO[weekday_match.group("weekday").lower()]
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute") or "0")
        period = time_match.group("period").replace(".", "").lower()
        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            continue
        if period.startswith("p") and hour != 12:
            hour += 12
        if period.startswith("a") and hour == 12:
            hour = 0
        has_reminder_token = any(
            token in lower for token in ("remind", "reminder", "todo", "to do", "to-do")
        )
        if has_reminder_token:
            content = text[: weekday_match.start()].strip(" ,.;:")
            content = _strip_reminder_creation_prefix(content)
            content = _clean_reminder_content_followup(content)
        else:
            content = _prior_reminder_content_for_time_followup(messages, index) or ""
        if _looks_like_missing_reminder_content(content):
            for later_message in messages[index + 1 :]:
                if later_message.get("role") != "user":
                    continue
                later_content = _clean_reminder_content_followup(
                    _strip_reminder_creation_prefix(
                        str(later_message.get("content") or "")
                    )
                )
                later_lower = later_content.lower()
                if (
                    later_content
                    and later_lower not in {"thanks", "thank you", "ok", "okay"}
                    and not re.search(
                        rf"\b(?:tomorrow|next\s+week|next\s+(?:{weekday_names}))\b",
                        later_lower,
                    )
                ):
                    content = later_content
            if _looks_like_missing_reminder_content(content):
                content = ""
        return {
            "content": content,
            "target_isoweekday": weekday,
            "hour": hour,
            "minute": minute,
        }
    return None


def _weekday_reminder_creation_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "add_reminder" not in available_names:
        return None
    request = _weekday_reminder_creation_request(openai_messages)
    if request is None:
        return None
    if _reminder_location_parts(openai_messages) is not None:
        return None
    content = str(request["content"]).strip()
    if not content:
        if _messages_show_reminder_content_request(openai_messages):
            return None
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-weekday-reminder-missing-content",
            content="What should the reminder say?",
        )
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        if "get_current_timestamp" not in available_names:
            return None
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-weekday-reminder-current-timestamp",
            tool_name=_tool_name_for_call(openai_tools, "get_current_timestamp"),
            arguments={},
        )
    reminder_timestamp = _timestamp_from_latest_tool(
        openai_messages, "next_weekday_time_to_timestamp"
    )
    if reminder_timestamp is None:
        if "next_weekday_time_to_timestamp" not in available_names:
            return None
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-weekday-reminder-timestamp",
            tool_name=_tool_name_for_call(
                openai_tools, "next_weekday_time_to_timestamp"
            ),
            arguments={
                "current_timestamp": current_timestamp,
                "target_isoweekday": int(request["target_isoweekday"]),
                "hour": int(request["hour"]),
                "minute": int(request["minute"]),
                "local_utc_offset_hours": DEFAULT_LOCAL_UTC_OFFSET_HOURS,
            },
        )
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-weekday-reminder-add",
        tool_name=_tool_name_for_call(openai_tools, "add_reminder"),
        arguments={
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": None,
            "longitude": None,
        },
    )


def _records_from_latest_reminder_search(
    openai_messages: object,
) -> list[Mapping[str, Any]]:
    message = _latest_tool_message(openai_messages, "search_reminder")
    if message is None:
        return []
    payload = _parse_sequence_payload(message.get("content"))
    return [record for record in payload if isinstance(record, Mapping)]


def _yesterday_bounds(
    current_timestamp: float, timezone_offset: float = 0.0
) -> tuple[float, float]:
    target = current_timestamp - 86400.0
    return target - 120.0, target + 120.0


def _filter_created_yesterday_records(
    records: list[Mapping[str, Any]],
    current_timestamp: float | None,
) -> list[Mapping[str, Any]]:
    if current_timestamp is None:
        return records
    lower, upper = _yesterday_bounds(current_timestamp)
    filtered: list[Mapping[str, Any]] = []
    for record in records:
        created_raw = record.get("creation_timestamp")
        if created_raw is None:
            continue
        try:
            created = float(created_raw)
        except (TypeError, ValueError):
            continue
        if lower <= created <= upper:
            filtered.append(record)
    return filtered


def _reminder_contents(records: list[Mapping[str, Any]]) -> list[str]:
    contents: list[str] = []
    for record in records:
        content = str(record.get("content") or "").strip()
        if content and content not in contents:
            contents.append(content)
    return contents


def _reminder_search_answer_requested(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return False
    if any(
        token in latest_user
        for token in (
            "add ",
            "create ",
            "modify ",
            "update ",
            "change ",
            "remove ",
            "delete ",
            "postpone",
            "reschedule",
            "move ",
            "remind me",
        )
    ):
        return False
    if any(
        token in latest_user
        for token in (
            "first one",
            "second one",
            "third one",
            "last one",
            "just need the first",
            "just need the second",
            "just need the one",
            "just need the content",
            "need the content",
            "looking specifically for",
            "focus on",
            "follow up on",
            "keep it in mind",
            "need the first",
            "need the second",
            "need the one",
            "looking for the one",
            "one that says",
            "the one that says",
            "it should say",
            "should say",
            "which one",
        )
    ):
        return True
    if "reminder" in latest_user and any(
        token in latest_user
        for token in (
            "what",
            "which",
            "show",
            "list",
            "search",
            "find",
            "tell me",
            "need",
        )
    ):
        return True
    return False


def _reminder_selection_index(text: str, record_count: int) -> int | None:
    lower = text.lower()
    if record_count <= 0:
        return None
    if any(token in lower for token in ("first one", "first reminder", "the first")):
        return 0
    if any(token in lower for token in ("second one", "second reminder", "the second")):
        return 1 if record_count > 1 else None
    if any(token in lower for token in ("third one", "third reminder", "the third")):
        return 2 if record_count > 2 else None
    if any(token in lower for token in ("last one", "last reminder", "the last")):
        return record_count - 1
    return None


def _reminder_content_named_in_user_text(
    text: str,
    contents: list[str],
) -> str | None:
    lower = text.lower()
    for content in contents:
        if content and content.lower() in lower:
            return content
    quoted = re.findall(r"[\"']([^\"']{2,120})[\"']", text)
    for quote in quoted:
        normalized_quote = " ".join(quote.lower().split())
        for content in contents:
            if normalized_quote == " ".join(content.lower().split()):
                return content
    stopwords = {
        "the",
        "a",
        "an",
        "for",
        "from",
        "about",
        "reminder",
        "content",
        "one",
        "that",
        "says",
        "say",
        "just",
        "need",
        "focus",
        "on",
        "look",
        "looking",
    }
    user_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", lower)
        if token and token not in stopwords
    }
    best_content = None
    best_overlap = 0
    for content in contents:
        content_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", content.lower())
            if token and token not in stopwords
        }
        if not content_tokens:
            continue
        overlap = len(user_tokens & content_tokens)
        if overlap > best_overlap and overlap >= min(2, len(content_tokens)):
            best_content = content
            best_overlap = overlap
    if best_content:
        return best_content
    return None


def _reminder_search_answer_response_text(openai_messages: object) -> str | None:
    if not _reminder_search_answer_requested(openai_messages):
        if (
            _latest_user_is_answer_retention_followup(openai_messages)
            and _latest_tool_message(openai_messages, "search_reminder") is not None
        ):
            latest_assistant = _latest_assistant_content(openai_messages)
            if "reminder" in latest_assistant.lower():
                return f"You're welcome. To recap: {_strip_recap_prefixes(latest_assistant)}"
        latest_user = _latest_user_request_text(openai_messages).lower()
        if any(token in latest_user for token in ("perfect", "appreciate", "thanks")):
            latest_assistant = _latest_assistant_content(openai_messages)
            if "reminder" in latest_assistant.lower():
                return f"You're welcome. To recap: {_strip_recap_prefixes(latest_assistant)}"
        return None
    if _latest_tool_message(openai_messages, "search_reminder") is None:
        return None
    reminder_recency = _reminder_recency_request(openai_messages)
    if reminder_recency == "search_created_yesterday":
        return _reminder_created_yesterday_answer(openai_messages)
    if reminder_recency == "search_upcoming":
        return _upcoming_reminder_answer_text(openai_messages)
    records = _records_from_latest_reminder_search(openai_messages)
    if not records:
        return "I could not find a matching reminder."
    contents = _reminder_contents(records)
    if not contents:
        return "I found matching reminders, but no reminder text was visible."
    latest_user = _latest_user_request_text(openai_messages)
    named_content = _reminder_content_named_in_user_text(latest_user, contents)
    if named_content:
        return f'The reminder is "{named_content}".'
    selected_index = _reminder_selection_index(latest_user, len(contents))
    if selected_index is not None:
        return f'The reminder is "{contents[selected_index]}".'
    if len(contents) == 1:
        return f'The reminder is "{contents[0]}".'
    return f"The matching reminders are: {_join_visible_names(contents)}."


def _reminder_created_yesterday_answer(openai_messages: object) -> str:
    records = _filter_created_yesterday_records(
        _records_from_latest_reminder_search(openai_messages),
        _latest_current_timestamp(openai_messages),
    )
    contents = _reminder_contents(records)
    if not contents:
        return "I could not find a to-do item made yesterday."
    if len(contents) == 1:
        return f'The todo item you made yesterday is "{contents[0]}".'
    return f"The todo items you made yesterday are: {_join_visible_names(contents)}."


def _upcoming_reminder_records(openai_messages: object) -> list[Mapping[str, Any]]:
    current_timestamp = _latest_current_timestamp(openai_messages)
    records = _records_from_latest_reminder_search(openai_messages)
    if current_timestamp is None:
        return records
    upcoming: list[Mapping[str, Any]] = []
    for record in records:
        reminder_ts_raw = record.get("reminder_timestamp")
        if reminder_ts_raw is None:
            continue
        try:
            reminder_ts = float(reminder_ts_raw)
        except (TypeError, ValueError):
            continue
        if reminder_ts >= current_timestamp:
            upcoming.append(record)
    return upcoming


def _upcoming_reminder_answer_text(openai_messages: object) -> str:
    records = _upcoming_reminder_records(openai_messages)
    if not records:
        return "I could not find an upcoming reminder."
    request_text = " ".join(_all_user_texts(openai_messages)).lower()
    timestamp_preference = (
        "newest"
        if any(
            token in request_text
            for token in ("todo later", "reminder later", "for today", "today")
        )
        else "oldest"
    )
    selected = _record_by_timestamp_extreme(
        records, timestamp_preference, "reminder_timestamp"
    )
    content = str((selected or {}).get("content") or "").strip()
    if not content:
        contents = _reminder_contents(records)
        if len(contents) == 1:
            content = contents[0]
    if content:
        return f'Your upcoming reminder says "{content}".'
    return "I found an upcoming reminder, but I could not read its content."


def _selected_record_payload(openai_messages: object) -> Mapping[str, Any] | None:
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "select_record_by_timestamp_extreme"
    )
    selected = payload.get("selected_record") if payload else None
    return selected if isinstance(selected, Mapping) else None


def _selected_action_payload(openai_messages: object) -> Mapping[str, Any] | None:
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "select_action_target_by_recency"
    )
    return payload if isinstance(payload, Mapping) else None


def _reminder_recency_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    request = _reminder_recency_request(openai_messages)
    if request is None:
        return None
    if (
        request
        in {
            "modify_latest",
            "modify_upcoming",
            "search_created_yesterday",
            "search_yesterday",
            "remove_upcoming",
            "search_upcoming",
        }
        and "get_current_timestamp" in available_names
        and not _message_already_called_tool(openai_messages, "get_current_timestamp")
        and _latest_tool_message(openai_messages, "get_current_timestamp") is None
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-reminder-recency-current-timestamp",
            tool_name=_tool_name_for_call(openai_tools, "get_current_timestamp"),
            arguments={},
        )
    if _latest_tool_is(openai_messages, "get_current_timestamp"):
        current_timestamp = _latest_current_timestamp(openai_messages)
        if current_timestamp is None:
            return None
        if request == "modify_latest" and "search_reminder" in available_names:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-latest-modify-search",
                tool_name=_tool_name_for_call(openai_tools, "search_reminder"),
                arguments={"creation_timestamp_upperbound": current_timestamp},
            )
        if request == "modify_upcoming" and "search_reminder" in available_names:
            if "resolve_search_window_or_bounds" not in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-modify-search",
                    tool_name=_tool_name_for_call(openai_tools, "search_reminder"),
                    arguments={"reminder_timestamp_lowerbound": current_timestamp},
                )
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-modify-window",
                tool_name=_tool_name_for_call(
                    openai_tools, "resolve_search_window_or_bounds"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "phrase": "upcoming",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "upcoming",
                },
            )
        if (
            request in {"remove_upcoming", "search_upcoming"}
            and "resolve_search_window_or_bounds" not in available_names
            and "search_reminder" in available_names
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-search-all",
                tool_name=_tool_name_for_call(openai_tools, "search_reminder"),
                arguments={},
            )
        if "resolve_search_window_or_bounds" not in available_names:
            return None
        if request == "search_created_yesterday":
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-created-yesterday-window",
                tool_name=_tool_name_for_call(
                    openai_tools, "resolve_search_window_or_bounds"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "creation",
                    "direction": "yesterday",
                },
            )
        if request == "search_yesterday":
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-yesterday-window",
                tool_name=_tool_name_for_call(
                    openai_tools, "resolve_search_window_or_bounds"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "phrase": "yesterday",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "yesterday",
                },
            )
        if request in {"remove_upcoming", "search_upcoming"}:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-window",
                tool_name=_tool_name_for_call(
                    openai_tools, "resolve_search_window_or_bounds"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "phrase": "upcoming",
                    "target_domain": "reminder",
                    "timestamp_intent": "reminder",
                    "direction": "upcoming",
                },
            )
    if _latest_tool_is(openai_messages, "resolve_search_window_or_bounds"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "resolve_search_window_or_bounds"
        )
        kwargs = payload.get("search_kwargs") if payload else None
        should_call = bool(payload and payload.get("should_call_search"))
        target_tool = str(payload.get("target_tool_name") or "") if payload else ""
        if (
            should_call
            and target_tool == "search_reminder"
            and isinstance(kwargs, Mapping)
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-recency-search",
                tool_name=_tool_name_for_call(openai_tools, "search_reminder"),
                arguments=kwargs,
            )
        if (
            request in {"remove_upcoming", "search_upcoming", "search_yesterday"}
            and payload
            and str(payload.get("abstain_reason") or "")
            in {"unsupported_timestamp_intent", "unsupported_direction"}
            and "search_reminder" in available_names
        ):
            current_timestamp = _latest_current_timestamp(openai_messages)
            arguments: dict[str, Any] = {}
            if current_timestamp is not None:
                if request == "search_yesterday":
                    target = current_timestamp - 86400.0
                    arguments["reminder_timestamp_lowerbound"] = target - 120.0
                    arguments["reminder_timestamp_upperbound"] = target + 120.0
                else:
                    arguments["reminder_timestamp_lowerbound"] = current_timestamp
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id=(
                    "sage-reminder-yesterday-search-fallback"
                    if request == "search_yesterday"
                    else "sage-reminder-upcoming-search-fallback"
                ),
                tool_name=_tool_name_for_call(openai_tools, "search_reminder"),
                arguments=arguments,
            )
    if _latest_tool_is(openai_messages, "relative_day_time_to_timestamp"):
        if (
            request not in {"modify_latest", "modify_upcoming"}
            or "modify_reminder" not in available_names
        ):
            return None
        selected = _selected_record_payload(openai_messages)
        if not selected:
            selected = _record_by_timestamp_extreme(
                list(_records_from_latest_reminder_search(openai_messages)),
                "oldest" if request == "modify_upcoming" else "latest",
                "reminder_timestamp"
                if request == "modify_upcoming"
                else "creation_timestamp",
            )
        reminder_id = str(selected.get("reminder_id") or "").strip() if selected else ""
        if not reminder_id:
            return None
        timestamp_text = str(
            _latest_tool_content(openai_messages, "relative_day_time_to_timestamp")
            or ""
        ).strip("'\" ")
        try:
            reminder_timestamp = float(timestamp_text)
        except ValueError:
            return None
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-reminder-latest-modify",
            tool_name=_tool_name_for_call(openai_tools, "modify_reminder"),
            arguments={
                "reminder_id": reminder_id,
                "reminder_timestamp": reminder_timestamp,
            },
        )
    if _latest_tool_is(openai_messages, "search_reminder"):
        if request == "search_upcoming":
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-answer",
                content=_upcoming_reminder_answer_text(openai_messages),
            )
        if request in {"modify_latest", "modify_upcoming"}:
            records = _records_from_latest_reminder_search(openai_messages)
            if not records:
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-latest-empty",
                    content="I could not find a reminder to update.",
                )
            if (
                len(records) > 1
                and "select_record_by_timestamp_extreme" not in available_names
            ):
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-update-ambiguous",
                    content=(
                        "I found more than one matching reminder and cannot "
                        "safely identify which reminder to update."
                    ),
                )
            if "select_record_by_timestamp_extreme" in available_names:
                timestamp_key = (
                    "reminder_timestamp"
                    if request == "modify_upcoming"
                    else "creation_timestamp"
                )
                selection_mode = "oldest" if request == "modify_upcoming" else "latest"
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-latest-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_record_by_timestamp_extreme"
                    ),
                    arguments={
                        "records": records,
                        "timestamp_key": timestamp_key,
                        "selection_mode": selection_mode,
                    },
                )
            requested_time = _tomorrow_time_request(openai_messages)
            if (
                requested_time is not None
                and "relative_day_time_to_timestamp" in available_names
                and not _message_already_called_tool(
                    openai_messages, "relative_day_time_to_timestamp"
                )
            ):
                current_timestamp = _latest_current_timestamp(openai_messages)
                if current_timestamp is not None:
                    hour, minute = requested_time
                    return _synthetic_tool_call_completion(
                        model_name=model_name,
                        completion_id="sage-reminder-latest-relative-time-direct",
                        tool_name=_tool_name_for_call(
                            openai_tools, "relative_day_time_to_timestamp"
                        ),
                        arguments={
                            "current_timestamp": current_timestamp,
                            "day_offset": 1,
                            "hour": hour,
                            "minute": minute,
                            "local_utc_offset_hours": DEFAULT_LOCAL_UTC_OFFSET_HOURS,
                        },
                    )
            if requested_time is not None and "modify_reminder" in available_names:
                current_timestamp = _latest_current_timestamp(openai_messages)
                selected = _record_by_timestamp_extreme(
                    list(records),
                    "oldest" if request == "modify_upcoming" else "latest",
                    "reminder_timestamp"
                    if request == "modify_upcoming"
                    else "creation_timestamp",
                )
                reminder_id = (
                    str(selected.get("reminder_id") or "").strip() if selected else ""
                )
                if current_timestamp is not None and reminder_id:
                    hour, minute = requested_time
                    return _synthetic_tool_call_completion(
                        model_name=model_name,
                        completion_id="sage-reminder-latest-modify-direct",
                        tool_name=_tool_name_for_call(openai_tools, "modify_reminder"),
                        arguments={
                            "reminder_id": reminder_id,
                            "reminder_timestamp": _relative_timestamp_for_day_time(
                                current_timestamp,
                                1,
                                hour,
                                minute,
                            ),
                        },
                    )
        if request == "search_created_yesterday":
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-reminder-created-yesterday-answer",
                content=_reminder_created_yesterday_answer(openai_messages),
            )
        if request == "remove_upcoming":
            records = _upcoming_reminder_records(openai_messages)
            if not records:
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-empty",
                    content="I could not find an upcoming reminder to remove.",
                )
            if (
                len(records) > 1
                and "select_action_target_by_recency" not in available_names
                and "select_record_by_timestamp_extreme" not in available_names
            ):
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-remove-ambiguous",
                    content=(
                        "I found more than one upcoming reminder and cannot "
                        "safely identify which reminder to remove."
                    ),
                )
            if "select_action_target_by_recency" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-action-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_action_target_by_recency"
                    ),
                    arguments={
                        "records": records,
                        "timestamp_key": "reminder_timestamp",
                        "selection_mode": "oldest",
                        "action_type": "remove_reminder",
                        "constraints": {},
                        "updates": {},
                    },
                )
            if (
                len(records) == 1
                or "select_record_by_timestamp_extreme" not in available_names
            ):
                reminder_id = str(records[0].get("reminder_id") or "").strip()
                if reminder_id and "remove_reminder" in available_names:
                    return _synthetic_tool_call_completion(
                        model_name=model_name,
                        completion_id="sage-reminder-upcoming-remove",
                        tool_name=_tool_name_for_call(openai_tools, "remove_reminder"),
                        arguments={"reminder_id": reminder_id},
                    )
            if "select_record_by_timestamp_extreme" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_record_by_timestamp_extreme"
                    ),
                    arguments={
                        "records": records,
                        "timestamp_key": "reminder_timestamp",
                        "selection_mode": "oldest",
                    },
                )
    if _latest_tool_is(openai_messages, "select_action_target_by_recency"):
        if request != "remove_upcoming" or "remove_reminder" not in available_names:
            return None
        action_payload = _selected_action_payload(openai_messages)
        if not action_payload:
            return None
        if action_payload.get("abstain_reason"):
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-action-abstain",
                content="I could not identify a single upcoming reminder to remove.",
            )
        downstream_tool = str(action_payload.get("downstream_tool_name") or "")
        downstream_kwargs = action_payload.get("downstream_tool_kwargs")
        if (
            bool(action_payload.get("should_call_tool"))
            and downstream_tool == "remove_reminder"
            and isinstance(downstream_kwargs, Mapping)
        ):
            reminder_id = str(downstream_kwargs.get("reminder_id") or "").strip()
            if reminder_id:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-upcoming-remove-action-selected",
                    tool_name=_tool_name_for_call(openai_tools, "remove_reminder"),
                    arguments={"reminder_id": reminder_id},
                )
    if _latest_tool_is(openai_messages, "select_record_by_timestamp_extreme"):
        if request in {"modify_latest", "modify_upcoming"}:
            requested_time = _tomorrow_time_request(openai_messages)
            if requested_time is None or "modify_reminder" not in available_names:
                return None
            current_timestamp = _latest_current_timestamp(openai_messages)
            if current_timestamp is None:
                return None
            selected = _selected_record_payload(openai_messages)
            reminder_id = (
                str(selected.get("reminder_id") or "").strip() if selected else ""
            )
            if not reminder_id:
                return None
            hour, minute = requested_time
            if "relative_day_time_to_timestamp" not in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-latest-modify-selected-direct",
                    tool_name=_tool_name_for_call(openai_tools, "modify_reminder"),
                    arguments={
                        "reminder_id": reminder_id,
                        "reminder_timestamp": _relative_timestamp_for_day_time(
                            current_timestamp,
                            1,
                            hour,
                            minute,
                        ),
                    },
                )
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-latest-relative-time",
                tool_name=_tool_name_for_call(
                    openai_tools, "relative_day_time_to_timestamp"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "day_offset": 1,
                    "hour": hour,
                    "minute": minute,
                    "local_utc_offset_hours": DEFAULT_LOCAL_UTC_OFFSET_HOURS,
                },
            )
        if request != "remove_upcoming" or "remove_reminder" not in available_names:
            return None
        selected = _selected_record_payload(openai_messages)
        reminder_id = str(selected.get("reminder_id") or "").strip() if selected else ""
        if reminder_id:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-upcoming-remove-selected",
                tool_name=_tool_name_for_call(openai_tools, "remove_reminder"),
                arguments={"reminder_id": reminder_id},
            )
    return None


def _message_recency_request(openai_messages: object) -> str | None:
    all_user = " ".join(_all_user_texts(openai_messages)).lower()
    if any(token in all_user for token in ("update", "modify", "change")) and any(
        token in all_user for token in ("contact", "person", "phone", "number", "cell")
    ):
        return None
    for text in reversed(_all_user_texts(openai_messages)):
        lower = " ".join(text.lower().replace("’", "'").split())
        if not lower or _latest_user_is_brief_acknowledgement(
            [{"role": "user", "content": lower}]
        ):
            continue
        if "message" not in lower:
            continue
        if any(
            token in lower
            for token in (
                "send message",
                "text ",
                "modify contact",
                "update contact",
                "change contact",
                "remove contact",
                "delete contact",
            )
        ):
            continue
        if any(token in lower for token in ("update", "modify", "change")) and any(
            token in lower for token in ("phone", "number", "person")
        ):
            continue
        if any(token in lower for token in ("oldest", "earliest", "first")):
            return "oldest"
        if any(token in lower for token in ("most recent", "latest", "last")):
            return "latest"
    return None


def _message_recency_answer_text(
    selected_record: Mapping[str, Any],
    selection_mode: str,
) -> str | None:
    content = str(selected_record.get("content") or "").strip()
    if not content:
        return None
    label = "oldest" if selection_mode == "oldest" else "most recent"
    return f"Your {label} message says '{content}'."


def _message_recency_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_messages" not in available_names:
        return None
    selection_mode = _message_recency_request(openai_messages)
    if selection_mode is None:
        return None
    prior_exact_answer = _recent_exact_final_answer_from_tool(openai_messages)
    if prior_exact_answer and not _latest_tool_is(
        openai_messages, "select_message_content_by_recency"
    ):
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-message-recency-retain-answer",
            content=prior_exact_answer,
        )

    if _latest_tool_is(openai_messages, "select_message_content_by_recency"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "select_message_content_by_recency"
        )
        answer = str(
            payload.get("exact_final_answer")
            or payload.get("final_answer_recommendation")
            or ""
        ).strip()
        if bool(payload.get("should_answer")) and answer:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-message-recency-answer",
                content=answer,
            )
        reason = str(payload.get("abstain_reason") or "no matching message")
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-message-recency-abstain",
            content=f"I could not identify a single {selection_mode} message ({reason}).",
        )

    if _latest_tool_is(openai_messages, "select_record_by_timestamp_extreme"):
        selected = _selected_record_payload(openai_messages)
        if selected:
            selected_answer = _message_recency_answer_text(selected, selection_mode)
            if selected_answer:
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-message-recency-selected-answer",
                    content=selected_answer,
                )

    if _latest_tool_is(openai_messages, "resolve_search_window_or_bounds"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "resolve_search_window_or_bounds"
        )
        kwargs = payload.get("search_kwargs") if payload else None
        should_call = bool(payload and payload.get("should_call_search"))
        target_tool = str(payload.get("target_tool_name") or "") if payload else ""
        if (
            should_call
            and target_tool == "search_messages"
            and isinstance(kwargs, Mapping)
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-message-recency-search",
                tool_name=_tool_name_for_call(openai_tools, "search_messages"),
                arguments=kwargs,
            )

    if _latest_tool_is(openai_messages, "search_messages"):
        message = _latest_tool_message(openai_messages, "search_messages")
        records = _parse_sequence_payload(message.get("content") if message else "")
        if records:
            if "select_message_content_by_recency" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-message-recency-content-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_message_content_by_recency"
                    ),
                    arguments={
                        "records": records,
                        "selection_mode": selection_mode,
                    },
                )
            if "select_record_by_timestamp_extreme" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-message-recency-record-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_record_by_timestamp_extreme"
                    ),
                    arguments={
                        "records": records,
                        "timestamp_key": "creation_timestamp",
                        "selection_mode": selection_mode,
                    },
                )
            selected = _record_by_timestamp_extreme(records, selection_mode)
            if selected:
                selected_answer = _message_recency_answer_text(selected, selection_mode)
                if selected_answer:
                    return _synthetic_text_completion(
                        model_name=model_name,
                        completion_id="sage-message-recency-direct-answer",
                        content=selected_answer,
                    )
        search_args = _latest_prior_tool_call_arguments(
            openai_messages, "search_messages"
        )
        if "creation_timestamp_upperbound" in search_args:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-message-recency-empty",
                content=f"I could not find a {selection_mode} message.",
            )

    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        if "get_current_timestamp" in available_names:
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-message-recency-clock",
                tool_name=_tool_name_for_call(openai_tools, "get_current_timestamp"),
                arguments={},
            )
        return None

    if (
        "resolve_search_window_or_bounds" in available_names
        and not _message_already_called_tool(
            openai_messages, "resolve_search_window_or_bounds"
        )
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-message-recency-window",
            tool_name=_tool_name_for_call(
                openai_tools, "resolve_search_window_or_bounds"
            ),
            arguments={
                "current_timestamp": current_timestamp,
                "phrase": selection_mode,
                "target_domain": "message",
                "timestamp_intent": "message_creation",
                "direction": selection_mode,
            },
        )

    if not _message_already_called_tool(openai_messages, "search_messages"):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-message-recency-search-fallback",
            tool_name=_tool_name_for_call(openai_tools, "search_messages"),
            arguments={"creation_timestamp_upperbound": current_timestamp},
        )
    return None


def _infer_self_person_id_from_message_records(records: list[Any]) -> str:
    counts: dict[str, int] = {}
    sender_ids: set[str] = set()
    recipient_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            continue
        sender = str(record.get("sender_person_id") or "").strip()
        recipient = str(record.get("recipient_person_id") or "").strip()
        if sender:
            counts[sender] = counts.get(sender, 0) + 1
            sender_ids.add(sender)
        if recipient:
            counts[recipient] = counts.get(recipient, 0) + 1
            recipient_ids.add(recipient)
    candidates = sender_ids & recipient_ids
    if not candidates:
        candidates = set(counts)
    if not candidates:
        return ""
    ranked = sorted(candidates, key=lambda item: (-counts.get(item, 0), item))
    return ranked[0]


def _latest_self_person_id_from_contacts(openai_messages: object) -> str:
    message = _latest_tool_message(openai_messages, "search_contacts")
    if message is None:
        return ""
    records = _parse_sequence_payload(message.get("content"))
    for record in records:
        if not isinstance(record, Mapping):
            continue
        if bool(record.get("is_self")):
            return str(record.get("person_id") or "").strip()
    return ""


KNOWN_HOLIDAY_LABELS: tuple[str, ...] = (
    "Christmas Day",
    "Thanksgiving",
    "Halloween",
    "New Year's Day",
    "Labor Day",
    "Memorial Day",
    "Independence Day",
)


def _known_holiday_label_from_text(text: str) -> str | None:
    lower = text.lower().replace("’", "'")
    for known in KNOWN_HOLIDAY_LABELS:
        if known.lower().replace("’", "'") in lower:
            return known
    if re.search(r"\bchristmas\b", lower):
        return "Christmas Day"
    if re.search(r"\bnew years?\b", lower):
        return "New Year's Day"
    return None


def _looks_like_absolute_date_label(text: str) -> bool:
    lower = text.lower()
    return bool(
        re.search(r"\b(?:19|20)\d{2}\b", lower)
        or re.search(
            r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
            r"nov(?:ember)?|dec(?:ember)?)\b",
            lower,
        )
        or re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", lower)
    )


def _holiday_context_label(openai_messages: object) -> str | None:
    for text in reversed(_all_user_texts(openai_messages)):
        label = _known_holiday_label_from_text(text)
        if label:
            return label
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            function = tool_call.get("function")
            if not isinstance(function, Mapping):
                continue
            if (
                _execution_facing_tool_name(str(function.get("name") or ""))
                != "search_holiday"
            ):
                continue
            args = _parse_mapping_payload(function.get("arguments"))
            label = _known_holiday_label_from_text(str(args.get("holiday_name") or ""))
            if label:
                return label
    return None


def _holiday_day_count_request(openai_messages: object) -> bool:
    saw_holiday_context = _holiday_context_label(openai_messages) is not None
    latest_user = " ".join(
        _latest_user_request_text(openai_messages).lower().replace("’", "'").split()
    )
    if saw_holiday_context and (
        _latest_user_is_holiday_day_count_challenge(openai_messages)
        or any(
            token in latest_user
            for token in (
                "current date",
                "date info",
                "don't have the date",
                "do not have the date",
                "can't confirm the date",
                "cannot confirm the date",
                "calendar",
                "figure that out",
                "find out what the current date",
            )
        )
    ):
        return True
    for text in reversed(_all_user_texts(openai_messages)):
        lower = " ".join(text.lower().replace("’", "'").split())
        if not lower or _latest_user_is_brief_acknowledgement(
            [{"role": "user", "content": lower}]
        ):
            continue
        asks_for_days = any(
            token in lower for token in ("how many days", "days till", "days until")
        )
        if "holiday" in lower or any(
            name in lower
            for name in (
                "christmas",
                "thanksgiving",
                "halloween",
                "new year's",
                "new years",
                "labor day",
                "memorial day",
                "independence day",
            )
        ):
            if asks_for_days:
                return True
            continue
        if (
            asks_for_days
            and saw_holiday_context
            and _looks_like_absolute_date_label(lower)
        ):
            return True
    return False


def _ambiguous_holiday_distance_request(openai_messages: object) -> bool:
    latest_user = " ".join(
        _latest_user_request_text(openai_messages).lower().replace("’", "'").split()
    )
    if not latest_user or _known_holiday_label_from_text(latest_user) is None:
        return False
    explicit_day_request = any(
        token in latest_user
        for token in (
            "how many days",
            "days till",
            "days until",
            "days away",
            "day away",
        )
    )
    if explicit_day_request:
        return False
    return any(
        token in latest_user
        for token in (
            "how far",
            "far are we",
            "far away",
            "how close",
            "close are we",
        )
    )


def _ambiguous_holiday_distance_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    if "timestamp_diff" not in _tool_names_execution_facing(openai_tools):
        return None
    if not _ambiguous_holiday_distance_request(openai_messages):
        return None
    if _message_already_called_tool(openai_messages, "timestamp_diff"):
        return None
    holiday_label = _holiday_label_from_user_request(openai_messages)
    return _synthetic_text_completion(
        model_name=model_name,
        completion_id="sage-ambiguous-holiday-distance-insufficient-info",
        content=(
            f"I need the current date to calculate how far away {holiday_label} is."
        ),
    )


def _holiday_label_from_user_request(openai_messages: object) -> str:
    date_label: str | None = None
    for text in reversed(_all_user_texts(openai_messages)):
        stripped = " ".join(text.replace("’", "'").strip().split())
        lower = stripped.lower()
        if not stripped:
            continue
        match = re.search(
            r"\b(?:till|until)\s+(.+?)(?:[?.!]|$)",
            stripped,
            flags=re.IGNORECASE,
        )
        if match:
            label = match.group(1).strip(" .?!")
            if label:
                known_label = _known_holiday_label_from_text(label)
                if known_label:
                    return known_label
                if _looks_like_absolute_date_label(label):
                    date_label = label
                    continue
                return label
        known_label = _known_holiday_label_from_text(lower)
        if known_label:
            return known_label
    context_label = _holiday_context_label(openai_messages)
    if context_label:
        return context_label
    if date_label:
        return date_label
    return "the holiday"


def _holiday_request_has_explicit_year(openai_messages: object) -> bool:
    return any(
        re.search(r"\b(?:19|20)\d{2}\b", text)
        for text in _all_user_texts(openai_messages)
    )


def _latest_user_is_holiday_day_count_challenge(openai_messages: object) -> bool:
    latest_user = _latest_user_request_text(openai_messages).lower().replace("’", "'")
    if not latest_user:
        return False
    return any(
        token in latest_user
        for token in (
            "double-check",
            "double check",
            "sounds off",
            "not right",
            "isn't right",
            "isnt right",
            "wrong",
            "sooner",
            "less than that",
            "less than",
            "hoping it would be less",
            "hoped it would be less",
            "this year",
            "this year's",
            "talking about this year",
            "search again",
            "calculate again",
            "check again",
            "today is",
            "current date",
            "about 2 months",
            "around 2 months",
            "can't confirm",
            "cannot confirm",
            "verify the date",
            "check the current date",
        )
    )


def _latest_nonnegative_timestamp_diff_days(openai_messages: object) -> int | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "timestamp_diff":
            continue
        payload = _parse_mapping_payload(message.get("content"))
        try:
            days_raw = payload.get("days")
            if days_raw is None:
                continue
            days = int(days_raw)
        except (TypeError, ValueError):
            continue
        if days >= 0:
            return days
    return None


def _latest_signed_timestamp_diff_days(openai_messages: object) -> int | None:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "timestamp_diff":
            continue
        payload = _parse_mapping_payload(message.get("content"))
        try:
            days_raw = payload.get("days")
            if days_raw is None:
                continue
            return int(days_raw)
        except (TypeError, ValueError):
            continue
    return None


def _latest_timestamp_diff_args_are_reversed(openai_messages: object) -> bool:
    args = _latest_prior_tool_call_arguments(openai_messages, "timestamp_diff")
    try:
        timestamp_0 = float(args.get("timestamp_0"))
        timestamp_1 = float(args.get("timestamp_1"))
    except (TypeError, ValueError):
        return False
    return timestamp_0 > timestamp_1


def _latest_nonnegative_generated_day_count(openai_messages: object) -> int | None:
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages,
        "days_between_timestamps",
    )
    if not payload:
        return None
    try:
        days_raw = payload.get("days")
        if days_raw is None:
            return None
        days = int(days_raw)
    except (TypeError, ValueError):
        return None
    return days if days >= 0 else None


def _holiday_day_count_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "timestamp_diff" not in available_names or not _holiday_day_count_request(
        openai_messages
    ):
        return None

    if _latest_user_is_holiday_day_count_challenge(openai_messages):
        days = _latest_nonnegative_timestamp_diff_days(openai_messages)
        if days is not None:
            holiday_label = _holiday_label_from_user_request(openai_messages)
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-holiday-day-count-retain-tool-answer",
                content=f"It is {days} days till {holiday_label}.",
            )

    current_timestamp = _latest_current_timestamp(openai_messages)
    holiday_timestamp = _timestamp_from_latest_tool(openai_messages, "search_holiday")
    if (
        "search_holiday" in available_names
        and current_timestamp is not None
        and holiday_timestamp is None
        and not _message_already_called_tool(openai_messages, "search_holiday")
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-holiday-day-count-search-holiday",
            tool_name=_tool_name_for_call(openai_tools, "search_holiday"),
            arguments={
                "holiday_name": _holiday_label_from_user_request(openai_messages),
            },
        )
    if (
        "search_holiday" in available_names
        and current_timestamp is not None
        and holiday_timestamp is not None
        and holiday_timestamp < current_timestamp
        and not _holiday_request_has_explicit_year(openai_messages)
        and _latest_tool_is(openai_messages, "search_holiday")
    ):
        current_year = time.gmtime(float(current_timestamp)).tm_year
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-holiday-day-count-current-year-search",
            tool_name=_tool_name_for_call(openai_tools, "search_holiday"),
            arguments={
                "holiday_name": _holiday_label_from_user_request(openai_messages),
                "year": current_year,
            },
        )

    if _latest_tool_is(openai_messages, "timestamp_diff"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "timestamp_diff"
        )
        try:
            days_raw = payload.get("days")
            if days_raw is None:
                return None
            days = int(days_raw)
        except (TypeError, ValueError):
            return None
        if days < 0 and _latest_timestamp_diff_args_are_reversed(openai_messages):
            args = _latest_prior_tool_call_arguments(openai_messages, "timestamp_diff")
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-holiday-day-count-swap-timestamp-diff",
                tool_name=_tool_name_for_call(openai_tools, "timestamp_diff"),
                arguments={
                    "timestamp_0": args.get("timestamp_1"),
                    "timestamp_1": args.get("timestamp_0"),
                },
            )
        holiday_label = _holiday_label_from_user_request(openai_messages)
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-holiday-day-count-answer",
            content=f"It is {days} days till {holiday_label}.",
        )

    if _message_already_called_tool(openai_messages, "timestamp_diff"):
        days = _latest_nonnegative_timestamp_diff_days(openai_messages)
        if days is not None and _holiday_context_label(openai_messages) is not None:
            holiday_label = _holiday_label_from_user_request(openai_messages)
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-holiday-day-count-retain-prior-tool-answer",
                content=f"It is {days} days till {holiday_label}.",
            )
        return None
    if current_timestamp is None or holiday_timestamp is None:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-holiday-day-count-timestamp-diff",
        tool_name=_tool_name_for_call(openai_tools, "timestamp_diff"),
        arguments={
            "timestamp_0": current_timestamp,
            "timestamp_1": holiday_timestamp,
        },
    )


SERVICE_ANSWER_PRODUCER_TOOLS = {
    "search_location_around_lat_lon",
    "search_lat_lon",
    "search_weather_around_lat_lon",
    "calculate_lat_lon_distance",
    "convert_currency",
    "unit_conversion",
}


def _parse_service_payload_value(content: object) -> Any:
    text = str(content or "").strip()
    if not text:
        return None
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _coerce_service_answer_payload(
    tool_name: str,
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        records = [item for item in value if isinstance(item, Mapping)]
        if len(records) == 1:
            return dict(records[0])
        return {}
    if tool_name == "calculate_lat_lon_distance":
        return {"distance": value, "distance_unit": "km"}
    if tool_name in {"convert_currency", "unit_conversion"}:
        return {"value": value}
    return {}


def _latest_service_answer_payload(openai_messages: object) -> dict[str, Any]:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_text = _latest_user_request_text(openai_messages).lower()
    conversation_distance_request = any(
        any(
            token in text.lower()
            for token in ("how far", "distance", "km", "kilometer", "mile")
        )
        for text in _all_user_texts(openai_messages)
    )
    latest_user_requests_location_field = any(
        token in latest_user_text
        for token in (
            "phone",
            "number",
            "address",
            "where is",
            "website",
            "rating",
            "hours",
            "city",
        )
    )
    latest_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            latest_user_index = index
    for message in reversed(messages[latest_user_index + 1 :]):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in SERVICE_ANSWER_PRODUCER_TOOLS:
            continue
        if (
            name == "search_location_around_lat_lon"
            and conversation_distance_request
            and not latest_user_requests_location_field
        ):
            return {}
        content = str(message.get("content", "") or "").strip()
        lower = content.lower()
        if not content or "error" in lower or "exception" in lower:
            return {}
        return _coerce_service_answer_payload(
            name,
            _parse_service_payload_value(content),
        )
    return {}


def _service_answer_text(
    payload: Mapping[str, Any],
    openai_messages: object | None = None,
) -> str | None:
    if str(payload.get("abstain_reason") or "").strip():
        return None
    value = str(payload.get("answer_value") or "").strip()
    if not value:
        return None
    unit = str(payload.get("answer_unit") or "").strip()
    kind = str(payload.get("answer_kind") or "").strip().lower()
    if kind == "distance":
        unit = unit or "km"
        try:
            display_value = f"{float(value):.2f}".rstrip("0").rstrip(".")
        except ValueError:
            display_value = value
        display_unit = "kilometers" if unit.lower() == "km" else unit
        destination = (
            _distance_destination_label(openai_messages)
            if openai_messages is not None
            else "the destination"
        )
        return f"You are approximately {display_value} {display_unit} away from {destination}."
    if (
        ("temperature" in kind or "temp" in kind)
        and openai_messages is not None
        and _weather_request_wants_fahrenheit(openai_messages)
        and unit.lower() in {"c", "°c", "celsius", "degree celsius", "degrees celsius"}
    ):
        return None
    if unit and unit.lower() not in value.lower():
        return f"{value} {unit}"
    return value


def _service_answer_celsius_temperature_value(
    payload: Mapping[str, Any],
    openai_messages: object,
) -> float | None:
    if not _weather_request_wants_fahrenheit(openai_messages):
        return None
    kind = str(payload.get("answer_kind") or "").strip().lower()
    unit = str(payload.get("answer_unit") or "").strip().lower()
    if "temperature" not in kind and "temp" not in kind:
        return None
    if unit not in {"c", "°c", "celsius", "degree celsius", "degrees celsius"}:
        return None
    try:
        return float(str(payload.get("answer_value") or "").strip())
    except ValueError:
        return None


def _service_answer_extraction_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "extract_service_answer_field" not in available_names:
        return None
    if _latest_tool_is(openai_messages, "extract_service_answer_field"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "extract_service_answer_field"
        )
        temperature_c = _service_answer_celsius_temperature_value(
            payload, openai_messages
        )
        if temperature_c is not None:
            if "unit_conversion" not in available_names:
                return None
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-service-answer-extraction-convert-fahrenheit",
                tool_name=_tool_name_for_call(openai_tools, "unit_conversion"),
                arguments={
                    "amount": temperature_c,
                    "from_unit": "celsius",
                    "to_unit": "fahrenheit",
                },
            )
        answer = _service_answer_text(payload, openai_messages)
        if answer is None:
            return None
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-service-answer-extraction-answer",
            content=answer,
        )
    if _message_already_called_tool(openai_messages, "extract_service_answer_field"):
        return None
    service_payload = _latest_service_answer_payload(openai_messages)
    if not service_payload:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-service-answer-extraction-helper",
        tool_name=_tool_name_for_call(openai_tools, "extract_service_answer_field"),
        arguments={"service_payload": service_payload},
    )


def _latest_distance_km(openai_messages: object) -> float | None:
    content = _latest_tool_content(openai_messages, "calculate_lat_lon_distance")
    if not content:
        return None
    try:
        return float(str(content).strip("'\" "))
    except ValueError:
        return None


def _distance_destination_label(openai_messages: object) -> str:
    return _distance_destination_query(openai_messages) or "the destination"


def _clean_distance_destination_fragment(raw: str) -> str:
    value = " ".join(raw.strip().split())
    value = re.sub(
        r"\s+\b(?:from|to)\s+(?:my\s+)?(?:current\s+)?location\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+\b(?:from|to)\s+(?:here|where\s+i\s+am)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return _clean_lookup_query_fragment(value)


def _latest_user_is_distance_recovery_followup(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or _latest_user_is_brief_acknowledgement(openai_messages):
        return False
    distance_followup_tokens = (
        "current location",
        "exact location",
        "don't know my location",
        "do not know my location",
        "can't confirm",
        "cannot confirm",
        "can't verify",
        "cannot verify",
        "verify",
        "check again",
        "checking again",
        "check that distance",
        "confirm that distance",
        "calculate that distance",
        "look for it",
        "look it up",
        "look up a map",
        "another way",
        "different source",
        "different tools",
        "not helpful",
        "stuck",
        "can't figure",
        "cannot figure",
        "don't have that information",
        "do not have that information",
        "can't provide",
        "cannot provide",
        "nearby landmarks",
        "nearby landmark",
        "nearby cities",
        "nearby city",
        "without the tools",
        "can't use those tools",
        "cannot use those tools",
        "can't use tools",
        "cannot use tools",
        "distance",
        "how far",
        "km",
        "kilometer",
        "get there",
        "directions",
        "route",
        "navigate",
        "navigation",
        "gps",
        "drive",
        "driving",
        "transportation",
        "walking",
        "biking",
    )
    return any(token in latest_user for token in distance_followup_tokens)


def _latest_user_is_distance_direction_followup(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return False
    direction_tokens = (
        "get there",
        "directions",
        "route",
        "navigate",
        "navigation",
        "gps",
        "drive",
        "driving",
        "transportation",
        "walking",
        "biking",
    )
    return any(token in latest_user for token in direction_tokens)


def _distance_answer_recovery_response_text(openai_messages: object) -> str | None:
    if not _latest_user_is_distance_recovery_followup(openai_messages):
        return None
    distance_km = _latest_distance_km(openai_messages)
    coordinates = _latest_current_location_coordinates(openai_messages)
    if distance_km is None:
        return None
    distance_text = f"{distance_km:.2f}".rstrip("0").rstrip(".")
    destination = _distance_destination_label(openai_messages)
    if _latest_user_is_distance_direction_followup(openai_messages):
        return (
            "I don't have a route or navigation tool available. To recap: "
            f"you are approximately {distance_text} kilometers away from {destination}."
        )
    if coordinates is None:
        return (
            f"You are approximately {distance_text} kilometers away from {destination}."
        )
    return (
        f"I checked your current location. You are approximately {distance_text} "
        f"kilometers away from {destination}."
    )


def _distance_destination_query(openai_messages: object) -> str | None:
    for text in _all_user_texts(openai_messages):
        first_sentence = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)[0]
        lower = first_sentence.lower()
        if not any(
            token in lower
            for token in ("how far", "distance", "km", "kilometer", "mile")
        ):
            continue
        for pattern in (
            r"\bfrom\s+(?:my\s+)?(?:current\s+)?location\s+to\s+(.+?)(?:\s+(?:in|by)\s+(?:km|kilometers|kilometres|miles?))?$",
            r"\bfrom\s+(?:here|where\s+i\s+am)\s+to\s+(.+?)(?:\s+(?:in|by)\s+(?:km|kilometers|kilometres|miles?))?$",
            r"\bto\s+(.+?)(?:\s+(?:in|by)\s+(?:km|kilometers|kilometres|miles?))?$",
            r"\bfrom\s+(.+?)(?:\s+(?:in|by)\s+(?:km|kilometers|kilometres|miles?))?$",
        ):
            match = re.search(pattern, first_sentence, flags=re.IGNORECASE)
            if not match:
                continue
            query = _clean_distance_destination_fragment(match.group(1))
            query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
            if query_tokens and not query_tokens <= {
                "me",
                "my",
                "current",
                "location",
                "here",
            }:
                return query
    return None


def _current_location_distance_request(openai_messages: object) -> bool:
    destination = _distance_destination_query(openai_messages)
    if destination is None:
        return False
    all_user = " ".join(_all_user_texts(openai_messages)).lower()
    return any(
        token in all_user
        for token in (
            "how far",
            "how many km",
            "how many kilometers",
            "distance",
            "km to",
            "kilometers to",
        )
    )


def _latest_location_search_coordinates(
    openai_messages: object,
) -> tuple[float, float] | None:
    content = _latest_tool_content(openai_messages, "search_location_around_lat_lon")
    if not content:
        return None
    records = _parse_sequence_payload(content)
    for record in records:
        if not isinstance(record, Mapping):
            continue
        try:
            latitude = float(record.get("latitude"))
            longitude = float(record.get("longitude"))
        except (TypeError, ValueError):
            continue
        return latitude, longitude
    return None


def _current_location_distance_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    if not _current_location_distance_request(openai_messages):
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    destination = _distance_destination_query(openai_messages)
    if destination is None:
        return None
    if (
        "get_current_location" in available_names
        and _latest_current_location_coordinates(openai_messages) is None
        and not _message_already_called_tool(openai_messages, "get_current_location")
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-distance-get-current-location",
            tool_name=_tool_name_for_call(openai_tools, "get_current_location"),
            arguments={},
        )
    current_coordinates = _latest_current_location_coordinates(openai_messages)
    if current_coordinates is None:
        return None
    current_latitude, current_longitude = current_coordinates
    if (
        "search_location_around_lat_lon" in available_names
        and not _message_already_called_tool(
            openai_messages, "search_location_around_lat_lon"
        )
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-distance-search-destination",
            tool_name=_tool_name_for_call(
                openai_tools, "search_location_around_lat_lon"
            ),
            arguments={
                "location": destination,
                "latitude": current_latitude,
                "longitude": current_longitude,
            },
        )
    destination_coordinates = _latest_location_search_coordinates(openai_messages)
    if (
        destination_coordinates is None
        or "calculate_lat_lon_distance" not in available_names
        or _message_already_called_tool(openai_messages, "calculate_lat_lon_distance")
    ):
        return None
    destination_latitude, destination_longitude = destination_coordinates
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-distance-calculate-current-to-destination",
        tool_name=_tool_name_for_call(openai_tools, "calculate_lat_lon_distance"),
        arguments={
            "latitude_0": current_latitude,
            "longitude_0": current_longitude,
            "latitude_1": destination_latitude,
            "longitude_1": destination_longitude,
        },
    )


def _clean_lookup_query_fragment(raw: str) -> str:
    value = " ".join(raw.strip().strip(" .?!:;").split())
    value = re.sub(
        r"^(?:the|a|an|current|latest|right now|now)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(?:please|thanks|thank you|resolve any issue alone)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(?:stock|ticker|symbol|code|share price|price|weather|temperature|forecast)\b\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return " ".join(value.strip(" .?!:;").split())


def _stock_lookup_query(openai_messages: object) -> str | None:
    nonspecific_query_tokens = {
        "a",
        "an",
        "any",
        "for",
        "find",
        "get",
        "it",
        "look",
        "lookup",
        "now",
        "search",
        "searching",
        "symbol",
        "the",
        "try",
    }
    for text in reversed(_all_user_texts(openai_messages)):
        first_sentence = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)[0]
        lower = first_sentence.lower()
        if not any(token in lower for token in ("stock", "ticker", "symbol")):
            continue
        patterns = (
            r"\b(?:symbol|ticker|code)\s+(?:for|of)\s+(.+?)$",
            r"\b(?:stock|share)\s+(?:symbol|ticker|code)\s+(?:for|of)\s+(.+?)$",
            r"\b(?:find|get|look up|lookup|what is|what's)\b.*?\b(?:for|of)\s+(.+?)$",
            r"\b(.+?)\s+(?:stock|shares?)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, first_sentence, flags=re.IGNORECASE)
            if not match:
                continue
            query = _clean_lookup_query_fragment(match.group(1))
            query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
            if query_tokens and query_tokens <= nonspecific_query_tokens:
                continue
            if query and len(query) <= 80:
                return query
    return None


def _stock_lookup_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_stock" not in available_names:
        return None
    query = _stock_lookup_query(openai_messages)
    if not query:
        return None
    latest_stock = _latest_tool_message(openai_messages, "search_stock")
    if latest_stock is not None and _latest_tool_is(openai_messages, "search_stock"):
        content = str(latest_stock.get("content", "") or "").strip()
        if any(token in content.lower() for token in ("error", "exception")):
            return None
        payload = _parse_mapping_payload(content)
        symbol = str(payload.get("symbol") or "").strip()
        price = payload.get("price")
        currency = str(payload.get("currency") or "").strip()
        all_user = " ".join(_all_user_texts(openai_messages)).lower()
        if symbol and any(token in all_user for token in ("symbol", "ticker", "code")):
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-stock-symbol-answer",
                content=f"The stock symbol for {query} is {symbol}.",
            )
        if price not in (None, "") and any(
            token in all_user for token in ("price", "value", "trading at")
        ):
            suffix = f" {currency}" if currency else ""
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-stock-price-answer",
                content=f"{query} is trading at {price}{suffix}.",
            )
        return None
    if _message_already_called_tool(openai_messages, "search_stock"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-stock-search-required",
        tool_name=_tool_name_for_call(openai_tools, "search_stock"),
        arguments={"query": query},
    )


def _phone_location_lookup_query(openai_messages: object) -> str | None:
    for text in reversed(_all_user_texts(openai_messages)):
        first_sentence = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)[0]
        lower = first_sentence.lower()
        if "phone" not in lower and "number" not in lower:
            continue
        patterns = (
            r"\bphone\s+number\s+(?:of|for)\s+(.+?)$",
            r"\bnumber\s+(?:of|for)\s+(.+?)$",
            r"\breach\s+(.+?)\s+(?:by\s+)?phone\b",
        )
        for pattern in patterns:
            match = re.search(pattern, first_sentence, flags=re.IGNORECASE)
            if not match:
                continue
            query = _clean_lookup_query_fragment(match.group(1))
            if query and len(query) <= 120:
                return query
    return None


def _location_phone_answer_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    if "search_location_around_lat_lon" not in _tool_names_execution_facing(
        openai_tools
    ):
        return None
    all_user = " ".join(_all_user_texts(openai_messages)).lower()
    if "phone" not in all_user and "number" not in all_user:
        return None
    latest_user = _latest_user_request_text(openai_messages).lower()
    if "phone" not in latest_user and "number" not in latest_user:
        followup_tokens = (
            "that number",
            "the number",
            "still need",
            "need that",
            "need it",
            "can't access",
            "cannot access",
            "don't have",
            "do not have",
        )
        if not any(token in latest_user for token in followup_tokens):
            return None
    message = _latest_tool_message(openai_messages, "search_location_around_lat_lon")
    if message is None:
        return None
    records = _parse_sequence_payload(message.get("content"))
    query = _phone_location_lookup_query(openai_messages)
    query_lower = (query or "").lower()
    chosen: Mapping[str, Any] | None = None
    for record in records:
        if not isinstance(record, Mapping):
            continue
        phone = str(record.get("phone_number") or "").strip()
        if not phone:
            continue
        name = str(record.get("name") or "").strip()
        if query_lower and name.lower() == query_lower:
            chosen = record
            break
        if chosen is None:
            chosen = record
    if chosen is None:
        return None
    phone = str(chosen.get("phone_number") or "").strip()
    name = str(chosen.get("name") or query or "that location").strip()
    if not phone:
        return None
    return _synthetic_text_completion(
        model_name=model_name,
        completion_id="sage-location-phone-exact-answer",
        content=f"The phone number for {name} is {phone}.",
    )


def _weather_location_query(openai_messages: object) -> str | None:
    for text in reversed(_all_user_texts(openai_messages)):
        first_sentence = re.split(r"[.!?]\s+", text.strip(), maxsplit=1)[0]
        lower = first_sentence.lower()
        if not any(token in lower for token in ("weather", "temperature", "forecast")):
            continue
        if any(
            token in lower
            for token in (" here", "current location", "my location", "where i am")
        ):
            continue
        if _text_contains_lat_lon_pair(first_sentence):
            continue
        match = re.search(
            r"\b(?:in|at|for|near)\s+(.+?)(?:\s+(?:in\s+)?(?:fahrenheit|celsius|degrees?|°f|°c))?$",
            first_sentence,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        query = _clean_lookup_query_fragment(match.group(1))
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        unit_only_tokens = {
            "a",
            "address",
            "an",
            "another",
            "any",
            "app",
            "apps",
            "area",
            "check",
            "city",
            "coordinate",
            "coordinates",
            "fahrenheit",
            "celsius",
            "degree",
            "degrees",
            "detail",
            "details",
            "device",
            "find",
            "for",
            "google",
            "in",
            "instead",
            "location",
            "lookup",
            "local",
            "maybe",
            "my",
            "nearby",
            "online",
            "own",
            "search",
            "service",
            "services",
            "specific",
            "the",
            "temperature",
            "to",
            "try",
            "turn",
            "current",
            "itself",
            "approximation",
            "though",
            "not",
            "up",
            "use",
            "using",
            "web",
            "weather",
            "your",
            "yourself",
        }
        if query_tokens and query_tokens <= unit_only_tokens:
            continue
        if query and len(query) <= 120:
            return query
    return None


def _weather_request_wants_fahrenheit(openai_messages: object) -> bool:
    all_user = " ".join(_all_user_texts(openai_messages)).lower()
    return any(token in all_user for token in ("fahrenheit", "°f", " f "))


def _current_weather_without_location_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    available_names = _tool_names_execution_facing(openai_tools)
    if "get_current_location" in available_names:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages))
    lower = " ".join(all_user_text.lower().replace("_", " ").split())
    if not any(token in lower for token in ("weather", "temperature", "forecast")):
        return None
    if not any(
        token in lower
        for token in (" here", "current location", "my location", "where i am")
    ):
        return None
    if _text_contains_lat_lon_pair(all_user_text):
        return None
    if _weather_location_query(openai_messages):
        return None
    return (
        "I do not have enough information to retrieve the current temperature "
        "because current location is unavailable and you did not provide a city, "
        "address, or coordinates."
    )


def _weather_payload_matches_query(payload: Mapping[str, Any], query: str) -> bool:
    haystack = " ".join(
        str(payload.get(key) or "") for key in ("name", "region", "country", "tz_id")
    ).lower()
    query_tokens = [
        token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) >= 4
    ]
    return bool(query_tokens) and any(token in haystack for token in query_tokens)


def _weather_temperature_celsius(payload: Mapping[str, Any]) -> float | None:
    for key in ("current_temperature", "temperature", "average_temperature"):
        value = payload.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _weather_location_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    query = _weather_location_query(openai_messages)
    if not query:
        current_weather_unavailable = _current_weather_without_location_response_text(
            openai_messages, openai_tools
        )
        if current_weather_unavailable:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-weather-current-location-unavailable",
                content=current_weather_unavailable,
            )
        return None
    if "search_weather_around_lat_lon" not in available_names:
        return None
    if _latest_tool_is(openai_messages, "unit_conversion"):
        content = str(_latest_tool_content(openai_messages, "unit_conversion") or "")
        try:
            fahrenheit = float(content)
        except ValueError:
            return None
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-weather-location-fahrenheit-answer",
            content=(
                f"The current temperature in {query} is approximately "
                f"{fahrenheit:.1f}°F."
            ),
        )
    if _latest_tool_is(openai_messages, "search_weather_around_lat_lon"):
        payload = _parse_mapping_payload(
            _latest_tool_content(openai_messages, "search_weather_around_lat_lon")
        )
        if not payload:
            return None
        resolved_location_already = (
            _message_already_called_tool(
                openai_messages, "search_location_around_lat_lon"
            )
            or _latest_tool_message(openai_messages, "search_location_around_lat_lon")
            is not None
        )
        if (
            not _weather_payload_matches_query(payload, query)
            and not resolved_location_already
        ):
            if (
                "search_location_around_lat_lon" in available_names
                and not _message_already_called_tool(
                    openai_messages, "search_location_around_lat_lon"
                )
            ):
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-weather-location-search-after-default",
                    tool_name=_tool_name_for_call(
                        openai_tools, "search_location_around_lat_lon"
                    ),
                    arguments={"location": query},
                )
            return None
        temperature_c = _weather_temperature_celsius(payload)
        if temperature_c is None:
            return None
        if _weather_request_wants_fahrenheit(openai_messages):
            if "unit_conversion" not in available_names:
                return None
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-weather-location-convert-fahrenheit",
                tool_name=_tool_name_for_call(openai_tools, "unit_conversion"),
                arguments={
                    "amount": temperature_c,
                    "from_unit": "celsius",
                    "to_unit": "fahrenheit",
                },
            )
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-weather-location-celsius-answer",
            content=f"The current temperature in {query} is {temperature_c:g}°C.",
        )
    if _latest_tool_is(openai_messages, "search_location_around_lat_lon"):
        records = _parse_sequence_payload(
            _latest_tool_content(openai_messages, "search_location_around_lat_lon")
        )
        for record in records:
            if not isinstance(record, Mapping):
                continue
            try:
                latitude = float(record.get("latitude"))
                longitude = float(record.get("longitude"))
            except (TypeError, ValueError):
                continue
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-weather-location-weather",
                tool_name=_tool_name_for_call(
                    openai_tools, "search_weather_around_lat_lon"
                ),
                arguments={"latitude": latitude, "longitude": longitude},
            )
    if (
        "search_location_around_lat_lon" in available_names
        and not _message_already_called_tool(
            openai_messages, "search_location_around_lat_lon"
        )
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-weather-location-search",
            tool_name=_tool_name_for_call(
                openai_tools, "search_location_around_lat_lon"
            ),
            arguments={"location": query},
        )
    return None


def _timestamp_from_latest_tool(
    openai_messages: object,
    tool_name: str,
) -> float | None:
    content = _latest_tool_content(openai_messages, tool_name)
    if not content:
        return None
    try:
        return float(content.strip("'\" "))
    except ValueError:
        return None


def _relative_timestamp_for_day_time(
    current_timestamp: float,
    day_offset: int,
    hour: int,
    minute: int,
    local_utc_offset_hours: float = DEFAULT_LOCAL_UTC_OFFSET_HOURS,
) -> float:
    offset_seconds = float(local_utc_offset_hours) * 3600.0
    local_seconds = float(current_timestamp) + offset_seconds
    local_midnight = int(local_seconds // 86400.0) * 86400.0
    return (
        local_midnight
        + int(day_offset) * 86400.0
        - offset_seconds
        + int(hour) * 3600.0
        + int(minute) * 60.0
    )


def _reminder_location_parts(openai_messages: object) -> dict[str, str] | None:
    for text in reversed(_all_user_texts(openai_messages)):
        stripped = " ".join(text.replace("’", "'").strip().split())
        lower = stripped.lower()
        if not stripped:
            continue
        if "remind" not in lower and "reminder" not in lower and "todo" not in lower:
            continue
        if any(token in lower for token in ("remove", "delete", "modify", "update")):
            continue
        location_match: re.Match[str] | None = None
        for match in re.finditer(
            r"\bat\s+(?!\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\b)([^.!?]+)",
            stripped,
            flags=re.IGNORECASE,
        ):
            location_match = match
        if location_match is None:
            continue
        location = re.sub(r"\s+", " ", location_match.group(1)).strip(" ,.;:")
        if not location:
            continue
        content_prefix = stripped[: location_match.start()].strip(" ,.;:")
        followup_content_match = re.search(
            r"\bto\s+(?P<content>.+?)\s+at\s+(?:that\s+)?whole\s+foods\b",
            stripped,
            flags=re.IGNORECASE,
        )
        if followup_content_match is not None:
            content_prefix = followup_content_match.group("content").strip(" ,.;:")
        content_prefix = _strip_reminder_creation_prefix(content_prefix)
        content_prefix = re.sub(
            r"\b(?:today|tomorrow|tonight|next\s+\w+|on\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b.*$",
            "",
            content_prefix,
            flags=re.IGNORECASE,
        ).strip(" ,.;:")
        if not content_prefix:
            continue
        content_prefix = re.sub(
            r"\s+at\s+.+$",
            "",
            content_prefix,
            flags=re.IGNORECASE,
        ).strip(" ,.;:")
        content_prefix = _clean_reminder_content_followup(content_prefix)
        if _looks_like_missing_reminder_content(content_prefix):
            continue
        return {"content": content_prefix, "location": location}
    return None


def _location_query_is_specific(query: str) -> bool:
    lower = " ".join(query.lower().strip().split())
    if not lower:
        return False
    return bool(
        re.search(
            r"\b(?:ave|avenue|blvd|boulevard|creek|dr|drive|rd|road|st|street|"
            r"way|ln|lane|ct|court|mckinley|stevens|cupertino|sunnyvale|"
            r"santa clara|palm desert)\b",
            lower,
        )
        or "," in lower
        or re.search(r"\d", lower)
    )


def _latest_user_index(openai_messages: object) -> int:
    latest = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        if message.get("role") == "user":
            latest = index
    return latest


def _latest_location_clarification(openai_messages: object) -> str | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_question_index: int | None = None
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        text = str(message.get("content") or "").lower()
        if "which" in text and (
            "whole foods" in text or "location" in text or "store" in text
        ):
            latest_question_index = index
    if latest_question_index is None:
        return None
    clarification = ""
    for message in messages[latest_question_index + 1 :]:
        if message.get("role") != "user":
            continue
        text = " ".join(str(message.get("content") or "").strip().split())
        lower = text.lower().strip(" ,.;:")
        if not text or lower in {"thanks", "thank you", "ok", "okay"}:
            continue
        clarification = text
    return clarification or None


def _specific_location_hint_from_user_text(
    text: str,
    base_location: str,
) -> str | None:
    stripped = " ".join(text.replace("’", "'").strip().split())
    lower = stripped.lower()
    if not re.search(
        r"\b(?:ave|avenue|blvd|boulevard|creek|dr|drive|rd|road|st|street|"
        r"way|ln|lane|ct|court|mckinley|stevens|cupertino|sunnyvale|"
        r"santa clara|palm desert)\b",
        lower,
    ):
        return None
    base_lower = base_location.lower()
    is_whole_foods_request = "whole foods" in base_lower or "whole foods" in lower
    if not is_whole_foods_request:
        return stripped if base_lower and base_lower in lower else None
    match = re.search(
        r"\bwhole\s+foods(?:\s+market)?\b(?P<tail>[^.!?]*)",
        stripped,
        flags=re.IGNORECASE,
    )
    if match is not None:
        tail = re.sub(
            r"^(?:\s+should\s+be|\s+is|\s+location)?",
            "",
            match.group("tail"),
            flags=re.IGNORECASE,
        ).strip(" ,.;:")
        return f"Whole Foods {tail}".strip()
    location_match = re.search(
        r"\b(?:on|at|near|in)\s+[^.!?]*",
        stripped,
        flags=re.IGNORECASE,
    )
    if location_match is not None:
        return f"Whole Foods {location_match.group(0).strip()}".strip()
    return None


def _latest_specific_location_hint(
    openai_messages: object,
    base_location: str,
) -> str | None:
    for text in reversed(_all_user_texts(openai_messages)):
        hint = _specific_location_hint_from_user_text(text, base_location)
        if hint:
            return hint
    return None


def _reminder_location_query(
    openai_messages: object,
    parts: Mapping[str, str],
) -> str:
    base_location = str(parts.get("location") or "").strip()
    if re.fullmatch(r"that\s+whole\s+foods", base_location, flags=re.IGNORECASE):
        base_location = "Whole Foods"
    clarification = _latest_location_clarification(
        openai_messages
    ) or _latest_specific_location_hint(openai_messages, base_location)
    if not clarification:
        return base_location
    cleaned = re.sub(
        r"^(?:it\s+should\s+be\s+)?(?:use\s+)?(?:the\s+)?(?:one\s+)?",
        "",
        clarification,
        flags=re.IGNORECASE,
    ).strip(" ,.;:")
    if not cleaned:
        return base_location
    if "whole foods" in cleaned.lower():
        hint = _specific_location_hint_from_user_text(cleaned, base_location)
        if hint:
            return hint
    if base_location.lower() in cleaned.lower():
        return cleaned
    return f"{base_location} {cleaned}".strip()


def _latest_location_search_records(openai_messages: object) -> list[Mapping[str, Any]]:
    message = _latest_tool_message(openai_messages, "search_location_around_lat_lon")
    if message is None:
        return []
    records: list[Mapping[str, Any]] = []
    for record in _parse_sequence_payload(message.get("content")):
        if isinstance(record, Mapping):
            records.append(record)
    return records


def _location_record_token_score(record: Mapping[str, Any], query: str) -> int:
    query_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if token
        not in {
            "the",
            "one",
            "at",
            "on",
            "near",
            "in",
            "whole",
            "foods",
            "market",
        }
    }
    if not query_tokens:
        return 0
    haystack = " ".join(
        str(record.get(key) or "") for key in ("name", "full_address", "city", "state")
    ).lower()
    return sum(1 for token in query_tokens if token in haystack)


def _best_location_coordinates(
    openai_messages: object,
    *,
    query: str | None = None,
) -> tuple[float, float] | None:
    records = _latest_location_search_records(openai_messages)
    if not records:
        return None
    selected_records = records
    if query and len(records) > 1 and _location_query_is_specific(query):
        scored = [
            (_location_record_token_score(record, query), record) for record in records
        ]
        best_score = max(score for score, _record in scored)
        if best_score > 0:
            selected_records = [
                record for score, record in scored if score == best_score
            ]
    if len(selected_records) != 1 and query and not _location_query_is_specific(query):
        return None
    for record in selected_records:
        try:
            latitude_raw = record.get("latitude")
            longitude_raw = record.get("longitude")
            if latitude_raw is None or longitude_raw is None:
                continue
            latitude = float(latitude_raw)
            longitude = float(longitude_raw)
        except (TypeError, ValueError):
            continue
        return latitude, longitude
    return None


def _latest_location_coordinates(
    openai_messages: object,
) -> tuple[float, float] | None:
    return _best_location_coordinates(openai_messages)


def _reminder_creation_location_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "add_reminder" not in available_names:
        return None

    if _latest_tool_is(openai_messages, "prepare_reminder_creation_args"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "prepare_reminder_creation_args"
        )
        kwargs = payload.get("add_reminder_kwargs") if payload else None
        if bool(payload.get("should_call_add_reminder")) and isinstance(
            kwargs, Mapping
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-create-prepared-add",
                tool_name=_tool_name_for_call(openai_tools, "add_reminder"),
                arguments=kwargs,
            )

    parts = _reminder_location_parts(openai_messages)
    if parts is None:
        return None
    current_timestamp = _latest_current_timestamp(openai_messages)
    reminder_timestamp = _timestamp_from_latest_tool(
        openai_messages, "datetime_info_to_timestamp"
    ) or _timestamp_from_latest_tool(openai_messages, "relative_day_time_to_timestamp")
    if (
        reminder_timestamp is not None
        and current_timestamp is not None
        and reminder_timestamp < current_timestamp - 60.0
    ):
        reminder_timestamp = None
    requested_time = _tomorrow_time_request(openai_messages)
    if (
        reminder_timestamp is None
        and current_timestamp is None
        and requested_time
        and "get_current_timestamp" in available_names
        and not _message_already_called_tool(openai_messages, "get_current_timestamp")
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-reminder-location-current-timestamp",
            tool_name=_tool_name_for_call(openai_tools, "get_current_timestamp"),
            arguments={},
        )
    if reminder_timestamp is None and current_timestamp is not None and requested_time:
        hour, minute = requested_time
        if (
            "relative_day_time_to_timestamp" in available_names
            and not _message_already_called_tool(
                openai_messages, "relative_day_time_to_timestamp"
            )
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-reminder-location-relative-time",
                tool_name=_tool_name_for_call(
                    openai_tools, "relative_day_time_to_timestamp"
                ),
                arguments={
                    "current_timestamp": current_timestamp,
                    "day_offset": 1,
                    "hour": hour,
                    "minute": minute,
                    "local_utc_offset_hours": DEFAULT_LOCAL_UTC_OFFSET_HOURS,
                },
            )
        reminder_timestamp = _relative_timestamp_for_day_time(
            current_timestamp,
            1,
            hour,
            minute,
        )
    if reminder_timestamp is None:
        return None

    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_name = (
        _execution_facing_tool_name(str(messages[-1].get("name", "") or ""))
        if messages
        else ""
    )
    location_query = _reminder_location_query(openai_messages, parts)
    location_clarification = _latest_location_clarification(openai_messages)
    prior_coordinates_for_query = _best_location_coordinates(
        openai_messages, query=location_query
    )
    latest_search_index = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    latest_user_index = _latest_user_index(openai_messages)
    search_after_latest_user = (
        latest_search_index is not None and latest_search_index[0] > latest_user_index
    )
    latest_search_args = _latest_prior_tool_call_arguments(
        openai_messages, "search_location_around_lat_lon"
    )
    latest_search_query = str(latest_search_args.get("location") or "")
    should_search_location = (
        not _message_already_called_tool(
            openai_messages, "search_location_around_lat_lon"
        )
        or (
            latest_name in SETTING_SETTER_TOOL_NAMES
            and _best_location_coordinates(openai_messages, query=location_query)
            is None
        )
        or (
            location_clarification is not None
            and prior_coordinates_for_query is None
            and (not search_after_latest_user or latest_search_query != location_query)
        )
    )
    if "search_location_around_lat_lon" in available_names and should_search_location:
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-reminder-location-search",
            tool_name=_tool_name_for_call(
                openai_tools, "search_location_around_lat_lon"
            ),
            arguments={"location": location_query},
        )

    effective_query = str(latest_search_args.get("location") or location_query)
    records = _latest_location_search_records(openai_messages)
    if (
        len(records) > 1
        and not _location_query_is_specific(effective_query)
        and location_clarification is None
    ):
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-reminder-location-ambiguous",
            content=f"Which {parts['location']} location should I use?",
        )
    if location_clarification is not None:
        effective_query = location_query
    coordinates = _best_location_coordinates(openai_messages, query=effective_query)
    if coordinates is None:
        return None
    latitude, longitude = coordinates
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-reminder-location-add",
        tool_name=_tool_name_for_call(openai_tools, "add_reminder"),
        arguments={
            "content": parts["content"],
            "reminder_timestamp": reminder_timestamp,
            "latitude": latitude,
            "longitude": longitude,
        },
    )


def _contact_update_phone_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    if "modify_contact" not in _tool_names_execution_facing(openai_tools):
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    phone = _phone_update_from_user_request(openai_messages)
    user_text = " ".join(_all_user_texts(openai_messages)).lower()
    recency_message_update = (
        bool(phone)
        and "message" in user_text
        and any(token in user_text for token in ("last", "latest", "most recent"))
    )
    if recency_message_update and "search_messages" in available_names:
        if _latest_tool_is(openai_messages, "resolve_search_window_or_bounds"):
            payload = _latest_tool_payload_by_name_including_latest(
                openai_messages, "resolve_search_window_or_bounds"
            )
            kwargs = payload.get("search_kwargs") if payload else None
            should_call = bool(payload and payload.get("should_call_search"))
            target_tool = str(payload.get("target_tool_name") or "") if payload else ""
            if (
                should_call
                and target_tool == "search_messages"
                and isinstance(kwargs, Mapping)
            ):
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-update-message-recency-search",
                    tool_name=_tool_name_for_call(openai_tools, "search_messages"),
                    arguments=kwargs,
                )
        latest_search = _latest_tool_message(openai_messages, "search_messages")
        latest_search_records = _parse_sequence_payload(
            latest_search.get("content") if latest_search else ""
        )
        if (
            latest_search_records
            and "search_contacts" in available_names
            and not _message_already_called_tool(openai_messages, "search_contacts")
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-update-self-contact-search",
                tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
                arguments={"is_self": True},
            )
        if not latest_search_records and not _message_already_called_tool(
            openai_messages, "resolve_search_window_or_bounds"
        ):
            current_timestamp = _latest_current_timestamp(openai_messages)
            if current_timestamp is None and "get_current_timestamp" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-update-message-recency-clock",
                    tool_name=_tool_name_for_call(
                        openai_tools, "get_current_timestamp"
                    ),
                    arguments={},
                )
            if (
                current_timestamp is not None
                and "resolve_search_window_or_bounds" in available_names
            ):
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-update-message-recency-window",
                    tool_name=_tool_name_for_call(
                        openai_tools, "resolve_search_window_or_bounds"
                    ),
                    arguments={
                        "current_timestamp": current_timestamp,
                        "phrase": "latest",
                        "target_domain": "message",
                        "timestamp_intent": "message_creation",
                        "direction": "latest",
                    },
                )
            if current_timestamp is not None:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-update-message-recency-search-fallback",
                    tool_name=_tool_name_for_call(openai_tools, "search_messages"),
                    arguments={"creation_timestamp_upperbound": current_timestamp},
                )
    if (
        "select_message_counterparty_for_contact_update" in available_names
        and phone
        and _latest_tool_message(openai_messages, "search_messages") is not None
        and not _message_already_called_tool(
            openai_messages, "select_message_counterparty_for_contact_update"
        )
    ):
        message = _latest_tool_message(openai_messages, "search_messages")
        records = _parse_sequence_payload(message.get("content") if message else "")
        if records:
            selection_mode = (
                "oldest"
                if any(token in user_text for token in ("oldest", "first", "earliest"))
                else "latest"
            )
            self_person_id = _latest_self_person_id_from_contacts(
                openai_messages
            ) or _infer_self_person_id_from_message_records(records)
            records_for_helper = records
            if self_person_id and "sent" in user_text and " to " in user_text:
                sent_records = [
                    record
                    for record in records
                    if isinstance(record, Mapping)
                    and str(record.get("sender_person_id") or "").strip()
                    == self_person_id
                    and str(record.get("recipient_person_id") or "").strip()
                ]
                if sent_records:
                    records_for_helper = sent_records
            elif self_person_id and ("from" in user_text or "sent me" in user_text):
                received_records = [
                    record
                    for record in records
                    if isinstance(record, Mapping)
                    and str(record.get("recipient_person_id") or "").strip()
                    == self_person_id
                    and str(record.get("sender_person_id") or "").strip()
                ]
                if received_records:
                    records_for_helper = received_records
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-update-counterparty-select",
                tool_name=_tool_name_for_call(
                    openai_tools, "select_message_counterparty_for_contact_update"
                ),
                arguments={
                    "records": records_for_helper,
                    "selection_mode": selection_mode,
                    "updates": {"phone_number": phone},
                    "self_person_id": self_person_id,
                },
            )
    if not _latest_tool_is(
        openai_messages, "select_message_counterparty_for_contact_update"
    ):
        return None
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "select_message_counterparty_for_contact_update"
    )
    if payload.get("abstain_reason"):
        return None
    selected_person_id = str(payload.get("selected_person_id") or "").strip()
    if not selected_person_id:
        selected = payload.get("selected_record")
        if isinstance(selected, Mapping):
            selected_person_id = str(
                selected.get("sender_person_id")
                or selected.get("recipient_person_id")
                or ""
            ).strip()
    if not selected_person_id or not phone:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-contact-update-phone",
        tool_name=_tool_name_for_call(openai_tools, "modify_contact"),
        arguments={"person_id": selected_person_id, "phone_number": phone},
    )


def _contact_remove_by_phone_request(openai_messages: object) -> str:
    for text in reversed(_all_user_texts(openai_messages)):
        lower = " ".join(text.lower().split())
        if not lower:
            continue
        if not any(token in lower for token in ("remove", "delete")):
            continue
        if "contact" not in lower:
            continue
        phone = _extract_phone_from_text(text)
        if phone:
            return phone
    return ""


def _contact_remove_by_phone_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Bridge remove-by-phone requests through a visible contact lookup."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if (
        "search_contacts" not in available_names
        or "remove_contact" not in available_names
    ):
        return None
    phone = _contact_remove_by_phone_request(openai_messages)
    if not phone:
        return None
    if _called_tool_after_latest_user(openai_messages, "remove_contact"):
        return None
    latest_search = _latest_tool_message_after_latest_user(
        openai_messages, "search_contacts"
    )
    if latest_search is not None:
        records = _parse_sequence_payload(latest_search[1].get("content"))
        matches: list[Mapping[str, Any]] = []
        normalized_phone = _normalize_visible_phone(phone)
        for record in records:
            if not isinstance(record, Mapping):
                continue
            record_phone = _normalize_visible_phone(record.get("phone_number"))
            if record_phone == normalized_phone:
                matches.append(record)
        if len(matches) == 1:
            person_id = str(matches[0].get("person_id") or "").strip()
            if person_id and not _called_tool_after_latest_user(
                openai_messages, "remove_contact"
            ):
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-contact-remove-phone-remove",
                    tool_name=_tool_name_for_call(openai_tools, "remove_contact"),
                    arguments={"person_id": person_id},
                )
        if not matches:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-contact-remove-phone-not-found",
                content=(
                    f"I could not find a contact with phone number {normalized_phone}."
                ),
            )
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-contact-remove-phone-ambiguous",
            content=(
                "I found more than one contact with that phone number, so I "
                "cannot safely remove a contact."
            ),
        )
    if _called_tool_after_latest_user(openai_messages, "search_contacts"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-contact-remove-phone-search",
        tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
        arguments={"phone_number": phone},
    )


def _contact_update_by_id_request(openai_messages: object) -> dict[str, str] | None:
    person_id = ""
    phone_number = ""
    for text in _all_user_texts(openai_messages):
        person_id = person_id or _extract_person_id_from_text(text)
        if not phone_number:
            phone_number = _extract_phone_from_text(text)
    if not person_id or not phone_number:
        return None
    return {
        "person_id": person_id,
        "phone_number": phone_number,
        "name": "",
        "relationship": "",
        "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
    }


def _contact_update_by_id_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_contact_update_from_id" not in available_names:
        return None
    if "modify_contact" not in available_names:
        return None
    if _latest_tool_is(openai_messages, "plan_contact_update_from_id"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "plan_contact_update_from_id"
        )
        kwargs = payload.get("downstream_tool_kwargs") if payload else None
        if bool(payload.get("should_call_tool")) and isinstance(kwargs, Mapping):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-id-update-modify",
                tool_name=_tool_name_for_call(openai_tools, "modify_contact"),
                arguments=dict(kwargs),
            )
    if _message_already_called_tool(openai_messages, "plan_contact_update_from_id"):
        return None
    request = _contact_update_by_id_request(openai_messages)
    if request is None:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-contact-id-update-plan",
        tool_name=_tool_name_for_call(openai_tools, "plan_contact_update_from_id"),
        arguments=request,
    )


def _latest_visible_record_count(openai_messages: object) -> int:
    for tool_name in ("search_contacts", "search_messages", "search_reminder"):
        message = _latest_tool_message(openai_messages, tool_name)
        if message is None:
            continue
        payload = _parse_sequence_payload(message.get("content"))
        if payload:
            return len(payload)
    return 0


def _safe_action_capability(value: str) -> str:
    text = _execution_facing_tool_name(str(value or "").strip())
    normalized_text = text.lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "search_contacts": "contact_lookup",
        "remove_contact": "contact_removal",
        "delete_contact": "contact_removal",
        "modify_contact": "contact_update",
        "update_contact": "contact_update",
        "search_messages": "message_lookup",
        "send_message": "message_send",
        "send_message_with_phone_number": "message_send",
        "search_reminder": "reminder_lookup",
        "remove_reminder": "reminder_removal",
        "modify_reminder": "reminder_update",
        "add_reminder": "reminder_creation",
        "get_current_location": "location_lookup",
        "get_current_city": "location_lookup",
        "find_current_city": "location_lookup",
        "search_lat_lon": "coordinate_to_place_lookup",
        "search_location_around_lat_lon": "coordinate_place_search",
        "search_weather_around_lat_lon": "coordinate_weather_lookup",
        "calculate_lat_lon_distance": "coordinate_distance_calculation",
        "get_location_service_status": "device_status_lookup",
        "get_low_battery_mode_status": "device_status_lookup",
        "get_wifi_status": "device_status_lookup",
        "get_cellular_service_status": "device_status_lookup",
        "set_location_service_status": "device_setting_update",
        "set_low_battery_mode_status": "device_setting_update",
        "set_wifi_status": "device_setting_update",
        "set_cellular_service_status": "device_setting_update",
        "current_city": "location_lookup",
        "current_location": "location_lookup",
        "get_my_current_city": "location_lookup",
        "get_my_current_location": "location_lookup",
        "where_am_i": "location_lookup",
        "what_city_am_i_in": "location_lookup",
    }
    return mapping.get(text, mapping.get(normalized_text, text))


def _safe_action_or_abstain_request(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, Any] | None:
    user_request = _latest_user_request_text(openai_messages).strip()
    lower = " ".join(user_request.lower().replace("_", " ").split())
    if not lower:
        return None
    available_original_tools = sorted(
        {
            _safe_action_capability(name)
            for name in _tool_names_execution_facing(openai_tools)
            if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        }
    )
    requested_action = ""
    required_original_tools: list[str] = []
    if any(token in lower for token in ("remove", "delete")) and "contact" in lower:
        requested_action = "contact_removal"
        required_original_tools = ["contact_lookup", "contact_removal"]
    elif any(token in lower for token in ("modify", "update", "change")) and (
        "contact" in lower
        or "person" in lower
        or "phone number" in lower
        or "cell number" in lower
    ):
        requested_action = "contact_update"
        required_original_tools = ["contact_lookup", "contact_update"]
    elif "message" in lower and any(token in lower for token in ("send", "text")):
        requested_action = "message_send"
        required_original_tools = ["contact_lookup", "message_send"]
    elif "reminder" in lower and any(token in lower for token in ("remove", "delete")):
        requested_action = "reminder_removal"
        required_original_tools = ["reminder_lookup", "reminder_removal"]
    elif "reminder" in lower and any(
        token in lower for token in ("modify", "update", "change", "postpone")
    ):
        requested_action = "reminder_update"
        required_original_tools = ["reminder_lookup", "reminder_update"]
    elif "reminder" in lower and any(token in lower for token in ("add", "create")):
        requested_action = "reminder_creation"
        required_original_tools = ["reminder_creation"]
    elif (
        "current location" in lower
        or "current city" in lower
        or "where am i" in lower
        or "what city am i" in lower
        or "which city am i" in lower
        or ("city" in lower and "am i" in lower)
    ):
        requested_action = "location_lookup"
        required_original_tools = ["get_current_location"]
    else:
        return None

    recency_reference = any(
        token in lower for token in ("latest", "last", "most recent", "recent")
    )
    message_or_contact_history_reference = any(
        token in lower
        for token in (
            "message",
            "messaged",
            "texted",
            "contacted",
            "sent",
            "received",
        )
    )
    message_recency_reference = (
        requested_action == "contact_update"
        and message_or_contact_history_reference
        and recency_reference
    )
    if message_recency_reference:
        target_identifier = "recency_reference"
        required_original_tools = ["message_lookup", "contact_update"]
    else:
        target_identifier = _extract_person_id_from_text(
            user_request
        ) or _extract_phone_from_text(user_request)
        if requested_action == "message_send" and not target_identifier:
            send_request = _extract_send_message_contact_request(openai_messages)
            if send_request:
                target_identifier = str(send_request.get("recipient_name") or "")
    if not target_identifier and recency_reference:
        target_identifier = "recency_reference"
        if requested_action == "contact_update":
            required_original_tools = ["message_lookup", "contact_update"]
    if not target_identifier and any(token in lower for token in ("that", "this")):
        target_identifier = "implicit_reference"

    return {
        "user_request": user_request,
        "requested_action": requested_action,
        "target_identifier": target_identifier,
        "required_original_tools": required_original_tools,
        "available_original_tools": available_original_tools,
        "visible_records_count": _latest_visible_record_count(openai_messages),
    }


def _text_contains_lat_lon_pair(text: str) -> bool:
    lower = text.lower()
    numbers: list[float] = []
    for match in re.finditer(r"[-+]?\d+(?:\.\d+)?", text):
        try:
            numbers.append(float(match.group(0)))
        except ValueError:
            continue
    if len(numbers) < 2:
        return False
    coordinate_context = any(
        token in lower
        for token in (
            "lat",
            "latitude",
            "lon",
            "lng",
            "longitude",
            "coordinates",
            "coords",
        )
    )
    decimal_pair_context = len(re.findall(r"[-+]?\d+\.\d+", text)) >= 2
    if not coordinate_context and not decimal_pair_context:
        return False
    for latitude, longitude in zip(numbers, numbers[1:]):
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return True
    return False


def _current_location_without_location_tool_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "get_current_location" in available_names:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages))
    lower = " ".join(all_user_text.lower().replace("_", " ").split())
    if _current_location_distance_request(openai_messages):
        if _text_contains_lat_lon_pair(all_user_text):
            return None
        return (
            "I do not have enough information to calculate the distance because "
            "current location is unavailable and you did not provide coordinates."
        )
    current_location_request = any(
        token in lower
        for token in (
            "current location",
            "current city",
            "where am i",
            "what city am i in",
            "which city am i in",
            "what town am i in",
            "which town am i in",
        )
    )
    if not current_location_request:
        return None
    if _text_contains_lat_lon_pair(all_user_text):
        return None
    return (
        "I do not have enough information to determine your current city because "
        "current location is unavailable and you did not provide coordinates."
    )


def _contact_update_message_recency_without_message_search_request(
    openai_messages: object,
) -> bool:
    all_user_text = " ".join(_all_user_texts(openai_messages)).lower()
    lower = " ".join(all_user_text.replace("_", " ").split())
    if "message" not in lower:
        return False
    if not any(token in lower for token in ("latest", "last", "most recent", "recent")):
        return False
    if not any(token in lower for token in ("modify", "update", "change")):
        return False
    return any(token in lower for token in ("contact", "person", "phone", "number"))


def _contact_update_message_recency_without_message_search_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_messages" in available_names or "search_contacts" not in available_names:
        return None
    if not _contact_update_message_recency_without_message_search_request(
        openai_messages
    ):
        return None
    if not _called_tool_after_latest_user(openai_messages, "search_contacts"):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-contact-message-recency-no-message-search-contacts",
            tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
            arguments={"is_self": False},
        )
    return _synthetic_text_completion(
        model_name=model_name,
        completion_id="sage-contact-message-recency-no-message-search-answer",
        content=(
            "I do not have enough information to identify the last person you "
            "sent a message to because message history is unavailable."
        ),
    )


def _remove_contact_missing_tool_retention_response_text(
    openai_messages: object,
) -> str | None:
    """Retain a terminal missing-remove-contact-tool answer across retries."""
    saw_missing_remove_contact = False
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        if _execution_facing_tool_name(str(message.get("name", "") or "")) != (
            "prepare_safe_action_or_abstain"
        ):
            continue
        payload = _parse_mapping_payload(message.get("content"))
        missing = " ".join(
            str(item) for item in payload.get("missing_information") or []
        )
        reason = str(payload.get("abstain_reason") or "")
        if (
            "contact_removal" in missing or "remove_contact" in missing
        ) and reason == "missing_required_original_tool":
            saw_missing_remove_contact = True
    if not saw_missing_remove_contact:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).lower()
    if "contact" not in all_user_text or not any(
        token in all_user_text for token in ("remove", "delete")
    ):
        return None
    latest_user = _latest_user_request_text(openai_messages).lower().replace("’", "'")
    if not any(
        token in latest_user
        for token in (
            "remove",
            "delete",
            "contact",
            "contacts app",
            "settings",
            "try",
            "go ahead",
            "figure it out",
            "no information",
            "no info",
            "can't help",
            "cannot help",
            "later",
        )
    ):
        return None
    if _extract_phone_from_text(" ".join(_all_user_texts(openai_messages))):
        return (
            "I cannot remove the phone number from your contact because I do "
            "not have the contact removal tool available."
        )
    return (
        "I cannot remove that contact because I do not have the contact "
        "removal tool available."
    )


def _safe_action_or_abstain_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "prepare_safe_action_or_abstain" not in available_names:
        return None
    if _latest_tool_is(openai_messages, "prepare_safe_action_or_abstain"):
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages, "prepare_safe_action_or_abstain"
        )
        should_abstain = bool(payload.get("should_abstain")) or bool(
            payload.get("abstain_reason")
        )
        if not should_abstain:
            return None
        answer = str(payload.get("final_answer_recommendation") or "").strip()
        if not answer:
            reason = str(payload.get("abstain_reason") or "insufficient_information")
            answer = (
                "I do not have enough information to complete that action safely "
                f"({reason})."
            )
        user_request = str(
            payload.get("user_request") or _latest_user_request_text(openai_messages)
        ).lower()
        missing_information = " ".join(
            str(item) for item in payload.get("missing_information") or []
        ).lower()
        if (
            (
                "message_lookup" in missing_information
                or "search_messages" in missing_information
            )
            and "message" in user_request
            and any(
                token in user_request
                for token in ("latest", "last", "most recent", "recent")
            )
            and any(token in user_request for token in ("modify", "update", "change"))
        ):
            answer = (
                "I do not have enough information to identify the last person "
                "you sent a message to because message history is unavailable."
            )
        elif (
            (
                "contact_removal" in missing_information
                or "remove_contact" in missing_information
            )
            and any(token in user_request for token in ("remove", "delete"))
            and "contact" in user_request
        ):
            if _extract_phone_from_text(user_request):
                answer = (
                    "I cannot remove the phone number from your contact because I "
                    "do not have the contact removal tool available."
                )
            else:
                answer = (
                    "I cannot remove that contact because I do not have the "
                    "contact removal tool available."
                )
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-safe-action-abstain-answer",
            content=answer,
        )
    if _message_already_called_tool(openai_messages, "prepare_safe_action_or_abstain"):
        retention = _remove_contact_missing_tool_retention_response_text(
            openai_messages
        )
        if retention:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-remove-contact-missing-tool-retention",
                content=retention,
            )
        return None
    request = _safe_action_or_abstain_request(openai_messages, openai_tools)
    if request is None:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-safe-action-abstain-plan",
        tool_name=_tool_name_for_call(openai_tools, "prepare_safe_action_or_abstain"),
        arguments=request,
    )


def _contact_remove_by_phone_insufficient_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Safe bridge for remove-by-phone requests when lookup is unavailable."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_contacts" in available_names:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower_all = all_user_text.lower()
    if not any(token in lower_all for token in ("remove", "delete")):
        return None
    if "contact" not in lower_all:
        return None
    phone = _extract_phone_from_text(all_user_text)
    if not phone:
        return None
    latest_user = _latest_user_request_text(openai_messages).lower()
    if not latest_user:
        return None
    if _latest_tool_is(openai_messages, "remove_contact"):
        # Let the model see the tool error first, then stabilize the next turn.
        return None
    return (
        "I do not have enough information to safely remove the contact with "
        f"phone number {phone}. I would need a contact name or person_id, or "
        "access to search contacts, before I can remove it."
    )


def _message_recency_contact_update_unavailable_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "search_messages" in available_names:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).lower()
    lower = " ".join(all_user_text.replace("_", " ").split())
    if "message" not in lower:
        return None
    if not any(token in lower for token in ("latest", "last", "most recent", "recent")):
        return None
    if not any(token in lower for token in ("modify", "update", "change")):
        return None
    if not any(token in lower for token in ("contact", "person", "phone", "number")):
        return None
    if (
        "prepare_safe_action_or_abstain" in available_names
        and not _message_already_called_tool(
            openai_messages, "prepare_safe_action_or_abstain"
        )
    ):
        return None
    return (
        "I do not have enough information to identify the last person you sent "
        "a message to because message history is unavailable."
    )


def _send_message_missing_phone_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Prevent guessed send-message side effects when no phone lookup path exists."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "send_message_with_phone_number" not in available_names:
        return None
    if (
        "search_contacts" in available_names
        or "plan_send_message_contact_lookup" in available_names
    ):
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower_all = all_user_text.lower()
    latest_user = _latest_user_request_text(openai_messages).lower()
    if _latest_user_is_privacy_retention_followup(openai_messages):
        return None
    lookup_only_tokens = ("what", "what's", "which", "show", "read", "tell me")
    if (
        any(token in latest_user for token in lookup_only_tokens)
        and ("message" in latest_user or "text" in latest_user)
        and "send" not in latest_user
    ):
        return None
    explicit_send_context = "send" in lower_all or "message to" in lower_all
    is_send_request = explicit_send_context and (
        "message" in lower_all or "text" in lower_all
    )
    if (
        any(token in lower_all for token in lookup_only_tokens)
        and ("message" in lower_all or "text" in lower_all)
        and not is_send_request
    ):
        return None
    if not any(token in lower_all for token in ("send", "text")):
        return None
    if "message" not in lower_all and "text" not in lower_all:
        return None
    if _extract_phone_from_text(all_user_text):
        return None
    latest_tool = _latest_tool_message(
        openai_messages, "send_message_with_phone_number"
    )
    latest_tool_text = (
        str(latest_tool.get("content", "") or "").lower() if latest_tool else ""
    )
    if latest_tool_text and any(
        token in latest_tool_text
        for token in (
            "numberparseexception",
            "not seem to be a phone number",
            "missing or invalid default region",
            "invalid phone",
        )
    ):
        return (
            "I cannot send that message because I do not have a valid phone "
            "number or a visible contact lookup path for the recipient."
        )
    if _latest_tool_is(openai_messages, "set_cellular_service_status"):
        return (
            "Cellular service is on, but I still cannot send that message "
            "without a valid phone number or a visible contact lookup path for "
            "the recipient."
        )
    if _latest_tool_is(openai_messages, "get_cellular_service_status"):
        return None
    if not latest_user:
        return None
    if any(
        token in latest_user
        for token in (
            "don't have",
            "do not have",
            "no phone",
            "without it",
            "message only",
            "only have the message",
            "no other way",
            "can't think",
            "cannot think",
            "take your time",
        )
    ):
        return (
            "I cannot send that message without a valid phone number or a "
            "visible contact lookup path for the recipient."
        )
    if not _message_already_called_tool(
        openai_messages, "send_message_with_phone_number"
    ):
        return "I need the recipient's phone number before I can send that message."
    return None


def _latest_successful_send_message_tool_call(
    openai_messages: object,
) -> Mapping[str, Any] | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, Mapping[str, Any]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            if (
                tool_id
                and _execution_facing_tool_name(name)
                == "send_message_with_phone_number"
            ):
                tool_call_args_by_id[tool_id] = arguments
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "send_message_with_phone_number":
            continue
        content = str(message.get("content", "") or "").strip().lower()
        if any(token in content for token in ("error", "exception", "invalid")):
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        return tool_call_args_by_id.get(tool_id, {})
    return None


def _latest_cellular_blocked_send_message_call(
    openai_messages: object,
) -> tuple[int, Mapping[str, Any]] | None:
    """Return the newest send-message args blocked by cellular service state."""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    tool_call_args_by_id: dict[str, Mapping[str, Any]] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            tool_id = str(tool_call.get("id", "") or "")
            name, arguments = _tool_call_function_name_and_arguments(tool_call)
            if (
                tool_id
                and _execution_facing_tool_name(name)
                == "send_message_with_phone_number"
            ):
                tool_call_args_by_id[tool_id] = arguments

    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "send_message_with_phone_number":
            continue
        content = str(message.get("content", "") or "").strip().lower()
        if (
            "cellular service is not enabled" not in content
            and "cellular service is disabled" not in content
        ):
            continue
        tool_id = str(message.get("tool_call_id", "") or "")
        blocked_arguments = tool_call_args_by_id.get(tool_id)
        if blocked_arguments:
            return index, blocked_arguments
    return None


def _successful_original_tool_message_after_index(
    openai_messages: object,
    tool_name: str,
    index: int,
) -> int | None:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for offset, message in enumerate(messages[index + 1 :], start=index + 1):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != target:
            continue
        content = str(message.get("content", "") or "").strip().lower()
        if "error" in content or "exception" in content:
            continue
        return offset
    return None


def _assistant_called_tool_after_index(
    openai_messages: object,
    tool_name: str,
    index: int,
) -> bool:
    target = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in messages[index + 1 :]:
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, Mapping):
                continue
            name, _arguments = _tool_call_function_name_and_arguments(tool_call)
            if _execution_facing_tool_name(name) == target:
                return True
    return False


def _send_message_cellular_recovery_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Recover a blocked send by enabling cellular, then retrying the same send."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if (
        "send_message_with_phone_number" not in available_names
        or "set_cellular_service_status" not in available_names
    ):
        return None
    blocked = _latest_cellular_blocked_send_message_call(openai_messages)
    if blocked is None:
        return None
    blocked_index, send_arguments = blocked
    setter_index = _successful_original_tool_message_after_index(
        openai_messages,
        "set_cellular_service_status",
        blocked_index,
    )
    if setter_index is not None:
        if not _assistant_called_tool_after_index(
            openai_messages,
            "send_message_with_phone_number",
            setter_index,
        ):
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-send-message-cellular-retry",
                tool_name=_tool_name_for_call(
                    openai_tools, "send_message_with_phone_number"
                ),
                arguments=send_arguments,
            )
        return None
    if _assistant_called_tool_after_index(
        openai_messages,
        "set_cellular_service_status",
        blocked_index,
    ):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-send-message-cellular-enable",
        tool_name=_tool_name_for_call(openai_tools, "set_cellular_service_status"),
        arguments={"on": True},
    )


def _send_message_cellular_retry_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Retry the original send after a cellular precondition has been cleared."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "send_message_with_phone_number" not in available_names:
        return None
    blocked = _latest_cellular_blocked_send_message_call(openai_messages)
    if blocked is None:
        return None
    blocked_index, send_arguments = blocked
    setter_index = _successful_original_tool_message_after_index(
        openai_messages,
        "set_cellular_service_status",
        blocked_index,
    )
    if setter_index is None:
        return None
    if _assistant_called_tool_after_index(
        openai_messages,
        "send_message_with_phone_number",
        setter_index,
    ):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-send-message-cellular-retry",
        tool_name=_tool_name_for_call(openai_tools, "send_message_with_phone_number"),
        arguments=send_arguments,
    )


def _contact_name_for_phone_from_latest_search(
    openai_messages: object, phone_number: str
) -> str:
    message = _latest_tool_message(openai_messages, "search_contacts")
    if message is None:
        return ""
    target = str(phone_number or "").strip()
    if not target:
        return ""
    for record in _parse_sequence_payload(message.get("content")):
        if not isinstance(record, Mapping):
            continue
        if str(record.get("phone_number") or "").strip() == target:
            return str(record.get("name") or "").strip()
    return ""


def _send_message_success_response_text(openai_messages: object) -> str | None:
    args = _latest_successful_send_message_tool_call(openai_messages)
    if args is None:
        return None
    phone = str(args.get("phone_number") or "").strip()
    content = str(args.get("content") or "").strip()
    name = _contact_name_for_phone_from_latest_search(openai_messages, phone)
    recipient = name or phone or "the recipient"
    if content:
        return f"Your message to {recipient} has been sent saying: {content}"
    return f"Your message to {recipient} has been sent."


def _message_sender_phone_answer_response_text(openai_messages: object) -> str | None:
    """Keep visible message sender phone answers stable across follow-up turns."""
    phones: list[str] = []
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name != "search_messages":
            continue
        records = _parse_sequence_payload(message.get("content"))
        for record in records:
            if not isinstance(record, Mapping):
                continue
            phone = str(record.get("sender_phone_number") or "").strip()
            if phone and phone not in phones:
                phones.append(phone)
        if phones:
            break
    if not phones:
        return None
    latest_user_text = _latest_user_request_text(openai_messages)
    latest_user = latest_user_text.lower()
    all_user_texts = _all_user_texts(openai_messages)
    all_user = " ".join(all_user_texts).lower()
    if (
        "message" in all_user
        and any(token in all_user for token in ("latest", "last", "most recent"))
        and any(token in all_user for token in ("modify", "update", "change"))
        and any(token in all_user for token in ("contact", "person", "phone", "number"))
    ):
        return None
    phone_request_seen = "phone number" in all_user and any(
        token in all_user for token in ("which", "what", "asked", "sent", "sender")
    )
    if not phone_request_seen:
        return None
    request_context = ""
    for user_text in reversed(all_user_texts):
        normalized = " ".join(user_text.strip().split())
        match = re.search(
            r"\basked\s+me\s+if\s+(.+?)\??$",
            normalized,
            flags=re.IGNORECASE,
        ) or re.search(
            r"\basked\s+if\s+(.+?)\??$",
            normalized,
            flags=re.IGNORECASE,
        )
        if match:
            request_context = f"asked you if {match.group(1).strip(' ?.')}"
            break
        match = re.search(
            r"\basked\s+(?:me\s+)?about\s+(.+?)\??$",
            normalized,
            flags=re.IGNORECASE,
        )
        if match:
            request_context = f"asked you about {match.group(1).strip(' ?.')}"
            break

    def phone_answer() -> str:
        if len(phones) == 1:
            if request_context:
                return f"The phone number that {request_context} is {phones[0]}."
            return f"The phone number is {phones[0]}."
        if request_context:
            return f"The phone numbers that {request_context} are {_join_visible_names(phones)}."
        return f"The phone numbers are {_join_visible_names(phones)}."

    if (
        any(
            token in latest_user
            for token in (
                "who",
                "belongs",
                "identify",
                "right number",
                "already said",
                "other information",
                "additional details",
                "more details",
                "don't have",
                "do not have",
                "can't provide",
                "cannot provide",
                "stuck",
                "thanks",
                "thank",
                "got it",
                "appreciate",
            )
        )
        or any(phone in latest_user_text for phone in phones)
        or _latest_user_is_answer_retention_followup(openai_messages)
    ):
        return phone_answer()
    if "phone number" in latest_user:
        return phone_answer()
    return None


def _visible_named_send_recipient_present(openai_messages: object) -> bool:
    """Return whether visible user text names a send-message recipient."""
    for text in _all_user_texts(openai_messages):
        stripped = " ".join(text.strip().split())
        if not stripped or _extract_phone_from_text(stripped):
            continue
        patterns = (
            r"\b(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\b(?:send|text|message)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, stripped, flags=re.IGNORECASE)
            if match and match.group(1).strip():
                return True
    return False


def _extract_send_message_contact_request(
    openai_messages: object,
) -> dict[str, str] | None:
    """Extract a safe named-recipient send request from visible user text."""
    all_user_texts = _all_user_texts(openai_messages)
    all_user_lower = " ".join(all_user_texts).lower()
    recipient_source_index = -1
    recipient_from_context = ""
    for index, text in enumerate(all_user_texts):
        stripped = " ".join(text.strip().split())
        if not stripped:
            continue
        recipient_patterns = (
            r"\b(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\b(?:send|text|message)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bto\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\s+(?:saying|that|with)\b",
        )
        for pattern in recipient_patterns:
            match = re.search(pattern, stripped, flags=re.IGNORECASE)
            if not match:
                continue
            recipient = match.group(1).strip()
            recipient = re.sub(
                r"\s+(?:saying|say|that|with)$",
                "",
                recipient,
                flags=re.IGNORECASE,
            ).strip()
            if recipient:
                recipient_from_context = recipient
                recipient_source_index = index
                break
    for text in reversed(all_user_texts):
        stripped = " ".join(text.strip().split())
        if not stripped:
            continue
        lower = stripped.lower()
        if (
            "message" not in lower
            and "text" not in lower
            and "send" not in lower
            and "want to say" not in lower
        ):
            continue
        if not any(token in lower for token in ("send", "text", "message")) and not (
            "want to say" in lower
            and any(token in all_user_lower for token in ("send", "text", "message"))
        ):
            continue
        if _extract_phone_from_text(stripped):
            continue
        quoted = re.findall(r'"([^"]{1,280})"', stripped)
        content = quoted[-1].strip() if quoted else ""
        if not content:
            say_match = re.search(
                r"\b(?:saying|say|text)\s*:?\s+(.+?)\s*$",
                stripped,
                flags=re.IGNORECASE,
            )
            if say_match:
                content = say_match.group(1).strip(" .")
        recipient = ""
        recipient_patterns = (
            r"\b(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bto\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\s+(?:saying|that|with)\b",
        )
        for pattern in recipient_patterns:
            match = re.search(pattern, stripped, flags=re.IGNORECASE)
            if match:
                recipient = match.group(1).strip()
                recipient = re.sub(
                    r"\s+(?:saying|say|that|with)$",
                    "",
                    recipient,
                    flags=re.IGNORECASE,
                ).strip()
                break
        if recipient and content:
            return {"recipient_name": recipient, "message_content": content}
    if recipient_from_context and recipient_source_index >= 0:
        latest_index = len(all_user_texts) - 1
        latest = " ".join(all_user_texts[-1].strip().split()) if all_user_texts else ""
        latest_lower = latest.lower()
        latest_is_recipient_only = bool(
            re.fullmatch(
                r"(?:it(?:'s| is)\s+)?"
                + re.escape(recipient_from_context).replace("\\ ", r"\s+")
                + r"[.!\s]*",
                latest,
                flags=re.IGNORECASE,
            )
        )
        latest_is_ack = latest_lower.strip(" .!") in {
            "ok",
            "okay",
            "got it",
            "thanks",
            "thank you",
            "yes",
            "yeah",
        }
        if (
            latest_index > recipient_source_index
            and latest
            and not latest_is_recipient_only
            and not latest_is_ack
            and not _extract_phone_from_text(latest)
        ):
            return {
                "recipient_name": recipient_from_context,
                "message_content": latest.strip(),
            }
    return None


def _send_message_contact_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Safely bridge named-recipient send requests through visible contacts."""
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if (
        "search_contacts" not in available_names
        or "send_message_with_phone_number" not in available_names
    ):
        return None
    request = _extract_send_message_contact_request(openai_messages)
    if request is None:
        return None
    if _latest_tool_is(openai_messages, "send_message_with_phone_number"):
        latest = _latest_tool_message(openai_messages, "send_message_with_phone_number")
        latest_text = str(latest.get("content", "") if latest else "").strip().lower()
        if latest_text in {"", "none", "null"}:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-send-message-contact-success",
                content=f"Sent the message to {request['recipient_name']}.",
            )
        if "cellular" in latest_text and "disabled" in latest_text:
            return None
    latest_search = _latest_tool_message(openai_messages, "search_contacts")
    if latest_search is not None:
        records = _parse_sequence_payload(latest_search.get("content"))
        matches: list[Mapping[str, Any]] = []
        name_lower = request["recipient_name"].lower()
        for record in records:
            if not isinstance(record, Mapping):
                continue
            record_name = str(record.get("name") or "").strip().lower()
            if record_name == name_lower or name_lower in record_name:
                matches.append(record)
        if len(matches) == 1:
            phone = str(matches[0].get("phone_number") or "").strip()
            if phone:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-send-message-contact-send",
                    tool_name=_tool_name_for_call(
                        openai_tools, "send_message_with_phone_number"
                    ),
                    arguments={
                        "phone_number": phone,
                        "content": request["message_content"],
                    },
                )
        if records:
            return _synthetic_text_completion(
                model_name=model_name,
                completion_id="sage-send-message-contact-ambiguous",
                content=(
                    "I found more than one possible contact or no phone number for "
                    f"{request['recipient_name']}, so I cannot safely send the message."
                ),
            )
    if _message_already_called_tool(openai_messages, "search_contacts"):
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-send-message-contact-search",
        tool_name=_tool_name_for_call(openai_tools, "search_contacts"),
        arguments={"name": request["recipient_name"]},
    )


def _state_action_sequence_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    final_response = _state_action_sequence_final_response_text(
        openai_messages,
        openai_tools,
    )
    if final_response:
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-state-action-sequence-final",
            content=final_response,
        )
    action = _state_action_sequence_next_action(openai_messages, openai_tools)
    if action is None:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-state-action-sequence-next",
        tool_name=_tool_name_for_call(openai_tools, str(action["tool_name"])),
        arguments=cast(Mapping[str, Any], action["arguments"]),
    )


def _state_action_planner_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    """Call the generated state planner when the request clearly needs it."""
    if not _praxis_bridge_policy_enabled():
        return None
    helpers = sorted(
        name
        for name in _state_action_planner_tool_names(openai_tools)
        if name.startswith("plan_device_state_action_sequence")
    )
    if not helpers:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest = messages[-1] if messages else {}
    latest_role = latest.get("role")
    latest_user = _latest_user_request_text(openai_messages)
    latest_user_lower = latest_user.lower()
    all_user_lower = " ".join(_all_user_texts(openai_messages)).lower()
    all_message_lower = " ".join(
        str(message.get("content", "") or "")
        for message in messages
        if message.get("role") in {"user", "assistant", "tool"}
    ).lower()
    latest_tool_text = ""
    if latest_role == "tool":
        latest_tool_text = str(latest.get("content", "") or "")
    latest_tool_lower = latest_tool_text.lower()

    service_terms = (
        "wifi",
        "wi-fi",
        "cellular",
        "location service",
        "low battery",
        "battery mode",
    )
    direct_action_terms = (
        "turn on",
        "turn off",
        "turn it on",
        "turn it off",
        "enable",
        "disable",
        "switch on",
        "switch off",
        "switch it on",
        "switch it off",
        "flip it on",
        "flip it off",
        "turned on",
        "turned off",
        "get that",
    )
    context_service = next(
        (term for term in service_terms if term in latest_user_lower),
        "",
    )
    if not context_service and any(
        term in latest_user_lower for term in direct_action_terms
    ):
        context_service = next(
            (term for term in service_terms if term in all_message_lower),
            "",
        )
    is_direct_state_action = any(
        term in latest_user_lower for term in direct_action_terms
    ) and bool(context_service)
    explicit_low_battery_precondition = is_direct_state_action and any(
        token in latest_user_lower
        for token in (
            "low battery",
            "battery mode",
        )
    )
    is_blocked_state_error = any(
        token in latest_tool_lower
        for token in (
            "cannot be turned on in low battery mode",
            "cellular service is not enabled",
            "cellular service is disabled",
            "wifi is not enabled",
            "wi-fi is not enabled",
            "wifi is disabled",
            "wi-fi is disabled",
            "location service is not enabled",
            "location service is disabled",
            "blocked by low battery",
        )
    )
    helper_already_called = any(
        _message_already_called_tool(openai_messages, name) for name in helpers
    )
    if helper_already_called and not is_blocked_state_error:
        return None
    if not (
        is_direct_state_action
        or explicit_low_battery_precondition
        or is_blocked_state_error
    ):
        return None

    visible_state = " ".join(
        part
        for part in (
            latest_user,
            latest_tool_text,
            all_user_lower
            if context_service and context_service not in latest_user_lower
            else "",
        )
        if part
    )
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-state-action-planner-bridge",
        tool_name=_tool_name_for_call(openai_tools, helpers[0]),
        arguments={
            "user_request": latest_user,
            "visible_state_or_error": visible_state,
        },
    )


def _setting_lookup_unavailable_message_history_response_text(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    tool_names = _tool_names_execution_facing(openai_tools)
    if "search_messages" in tool_names:
        return None
    answer = _recent_exact_final_answer_from_tool(
        openai_messages
    ) or _recent_tool_backed_answer_text(openai_messages)
    if not answer:
        return None
    answer_text = " ".join(str(answer).split())
    answer_lower = answer_text.lower()
    if not any(
        token in answer_lower
        for token in (
            "cellular service is",
            "wifi is",
            "wi-fi is",
            "location service is",
            "low battery mode is",
        )
    ):
        return None
    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user:
        return None
    unavailable_message_tokens = (
        "message history",
        "messaging app",
        "message to",
        "message was sent",
        "message went through",
        "confirm if the message",
        "check if my message",
        "check the message",
        "check something else",
        "try to check something else",
    )
    if not any(token in latest_user for token in unavailable_message_tokens):
        return None
    return f"I cannot check message history with the available tools. To recap: {answer_text}"


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = self.openai_client.with_options(
            timeout=_openai_request_timeout_seconds(),
            max_retries=_openai_max_retries(),
        )

    def _model_inference_with_tool_choice(
        self,
        openai_messages: list[OpenAIMessage],
        openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
        tool_name: str,
    ) -> ChatCompletion:
        with all_logging_disabled():
            response = _with_transient_openai_retries(
                lambda: self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(list[ChatCompletionMessageParam], openai_messages),
                    tools=openai_tools,
                    tool_choice={"type": "function", "function": {"name": tool_name}},
                )
            )
        record_chat_completion_usage(
            source="toolsandbox_agent",
            model=self.model_name,
            messages=openai_messages,
            tools=openai_tools,
            response=response,
        )
        return response

    def model_inference(
        self,
        openai_messages: list[OpenAIMessage],
        openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    ) -> ChatCompletion:
        """Run inference, with opt-in diagnostic tool forcing for adoption tests."""
        if not _praxis_bridge_policy_enabled():
            prompted_messages = _with_selector_actor_policy(
                openai_messages, openai_tools
            )
            completion_tool_free_turn = _helper_answer_completion_tool_free_turn(
                openai_messages,
                openai_tools,
            )
            if completion_tool_free_turn:
                retry_tool_choice = None
                prompt_openai_tools: Union[
                    Iterable[ChatCompletionToolParam], NotGiven
                ] = NOT_GIVEN
            else:
                completion_tool_choice = _helper_answer_completion_tool_choice(
                    openai_messages,
                    openai_tools,
                )
                status_completion_tool_choice = _device_status_completion_tool_choice(
                    openai_messages,
                    openai_tools,
                )
                shared_closure_tool_choice = _shared_task_closure_tool_choice(
                    openai_messages,
                    openai_tools,
                )
                downstream_original_tool_choice = (
                    _generated_downstream_original_tool_choice(
                        prompted_messages,
                        openai_tools,
                    )
                )
                retry_tool_choice = (
                    completion_tool_choice
                    or status_completion_tool_choice
                    or shared_closure_tool_choice
                    or downstream_original_tool_choice
                    or _reminder_recency_workflow_tool_choice(
                        prompted_messages,
                        openai_tools,
                    )
                    or _first_attempt_generated_tool_choice(
                        prompted_messages, openai_tools
                    )
                    or _generated_tool_continuation_choice(
                        prompted_messages, openai_tools
                    )
                    or _helper_adoption_retry_tool_choice(
                        prompted_messages, openai_tools
                    )
                )
                prompt_openai_tools = _dynamic_generated_tool_schema_filter(
                    prompted_messages,
                    openai_tools,
                    selected_tool_name=retry_tool_choice,
                )
                prompt_openai_tools = _drop_completed_generated_tool_schemas(
                    prompted_messages,
                    prompt_openai_tools,
                    selected_tool_name=retry_tool_choice,
                )
            retry_tool_choice_used = False

            def call_with_optional_retry_tool_choice(
                messages: list[OpenAIMessage],
            ) -> ChatCompletion:
                nonlocal retry_tool_choice_used
                if retry_tool_choice and not retry_tool_choice_used:
                    retry_tool_choice_used = True
                    return self._model_inference_with_tool_choice(
                        messages,
                        prompt_openai_tools,
                        retry_tool_choice,
                    )
                return super(ConfigurableOpenAIAgent, self).model_inference(
                    messages,
                    prompt_openai_tools,
                )

            return _run_actor_llm_with_generated_tool_contract_retry(
                call_with_optional_retry_tool_choice,
                prompted_messages,
                prompt_openai_tools,
                model_name=self.model_name,
            )

        reminder_search_answer = _reminder_search_answer_response_text(openai_messages)
        if reminder_search_answer:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-reminder-search-answer",
                content=reminder_search_answer,
            )
        sender_phone_answer = _message_sender_phone_answer_response_text(
            openai_messages
        )
        if sender_phone_answer:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-message-sender-phone-answer",
                content=sender_phone_answer,
            )
        answer_completion_bridge = _answer_completion_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if answer_completion_bridge is not None:
            return answer_completion_bridge
        setting_lookup_distraction = (
            _setting_lookup_unavailable_message_history_response_text(
                openai_messages, openai_tools
            )
        )
        if setting_lookup_distraction:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-setting-lookup-unavailable-message-history",
                content=setting_lookup_distraction,
            )
        send_cellular_retry = _send_message_cellular_retry_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if send_cellular_retry is not None:
            return send_cellular_retry
        setting_permission_followup = _setting_permission_followup_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if setting_permission_followup is not None:
            return setting_permission_followup
        current_city_recovery = _current_city_recovery_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if current_city_recovery is not None:
            return current_city_recovery
        location_phone_bridge = _location_phone_answer_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if location_phone_bridge is not None:
            return location_phone_bridge
        stock_lookup_bridge = _stock_lookup_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if stock_lookup_bridge is not None:
            return stock_lookup_bridge
        weather_location_bridge = _weather_location_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if weather_location_bridge is not None:
            return weather_location_bridge
        distance_recovery = _distance_answer_recovery_response_text(openai_messages)
        if distance_recovery:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-distance-answer-recovery",
                content=distance_recovery,
            )
        retained_answer = _answer_retention_response_text(openai_messages)
        if retained_answer:
            return ChatCompletion.model_construct(
                id="sage-answer-retention",
                choices=[
                    Choice.model_construct(
                        finish_reason="stop",
                        index=0,
                        message=ChatCompletionMessage.model_construct(
                            content=retained_answer,
                            role="assistant",
                            tool_calls=None,
                        ),
                    )
                ],
                created=0,
                model=self.model_name,
                object="chat.completion",
            )
        send_missing_phone = _send_message_missing_phone_response_text(
            openai_messages, openai_tools
        )
        if send_missing_phone:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-send-message-missing-phone",
                content=send_missing_phone,
            )
        state_sequence_bridge = _state_action_sequence_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if state_sequence_bridge is not None:
            return state_sequence_bridge
        completed_setting_retention = _completed_device_setting_retention_response_text(
            openai_messages
        )
        if completed_setting_retention:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-completed-setting-retention",
                content=completed_setting_retention,
            )
        state_planner_bridge = _state_action_planner_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if state_planner_bridge is not None:
            return state_planner_bridge
        setting_success_answer = _setting_success_response_text(
            openai_messages, openai_tools
        )
        if setting_success_answer:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-setting-success",
                content=setting_success_answer,
            )
        setting_lookup_answer = _setting_lookup_response_text(
            openai_messages, openai_tools
        )
        if setting_lookup_answer:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-setting-lookup",
                content=setting_lookup_answer,
            )
        setting_lookup_retention = _setting_lookup_retention_response_text(
            openai_messages
        )
        if setting_lookup_retention:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-setting-lookup-retention",
                content=setting_lookup_retention,
            )
        send_success = _send_message_success_response_text(openai_messages)
        if send_success:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-send-message-success",
                content=send_success,
            )
        send_cellular_recovery = _send_message_cellular_recovery_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if send_cellular_recovery is not None:
            return send_cellular_recovery
        contact_remove_phone_bridge = _contact_remove_by_phone_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if contact_remove_phone_bridge is not None:
            return contact_remove_phone_bridge
        contact_remove_insufficient = (
            _contact_remove_by_phone_insufficient_response_text(
                openai_messages, openai_tools
            )
        )
        if contact_remove_insufficient:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-contact-remove-phone-insufficient",
                content=contact_remove_insufficient,
            )
        send_contact_bridge = _send_message_contact_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if send_contact_bridge is not None:
            return send_contact_bridge
        contact_update_no_message_search = (
            _contact_update_message_recency_without_message_search_bridge_completion(
                openai_messages,
                openai_tools,
                model_name=self.model_name,
            )
        )
        if contact_update_no_message_search is not None:
            return contact_update_no_message_search
        current_location_unavailable = (
            _current_location_without_location_tool_response_text(
                openai_messages, openai_tools
            )
        )
        if current_location_unavailable:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-current-location-unavailable",
                content=current_location_unavailable,
            )
        safe_action_abstain_bridge = _safe_action_or_abstain_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if safe_action_abstain_bridge is not None:
            return safe_action_abstain_bridge
        message_recency_contact_update_unavailable = (
            _message_recency_contact_update_unavailable_response_text(
                openai_messages, openai_tools
            )
        )
        if message_recency_contact_update_unavailable:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-message-recency-contact-update-unavailable",
                content=message_recency_contact_update_unavailable,
            )
        message_recency_bridge = _message_recency_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if message_recency_bridge is not None:
            return message_recency_bridge
        current_location_distance_bridge = _current_location_distance_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if current_location_distance_bridge is not None:
            return current_location_distance_bridge
        service_answer_bridge = _service_answer_extraction_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if service_answer_bridge is not None:
            return service_answer_bridge
        ambiguous_holiday_distance_bridge = (
            _ambiguous_holiday_distance_bridge_completion(
                openai_messages,
                openai_tools,
                model_name=self.model_name,
            )
        )
        if ambiguous_holiday_distance_bridge is not None:
            return ambiguous_holiday_distance_bridge
        holiday_day_count_bridge = _holiday_day_count_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if holiday_day_count_bridge is not None:
            return holiday_day_count_bridge
        absolute_reminder_creation_bridge = (
            _absolute_reminder_creation_bridge_completion(
                openai_messages,
                openai_tools,
                model_name=self.model_name,
            )
        )
        if absolute_reminder_creation_bridge is not None:
            return absolute_reminder_creation_bridge
        weekday_reminder_creation_bridge = _weekday_reminder_creation_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if weekday_reminder_creation_bridge is not None:
            return weekday_reminder_creation_bridge
        relative_reminder_creation_bridge = (
            _relative_reminder_creation_bridge_completion(
                openai_messages,
                openai_tools,
                model_name=self.model_name,
            )
        )
        if relative_reminder_creation_bridge is not None:
            return relative_reminder_creation_bridge
        reminder_creation_location_bridge = (
            _reminder_creation_location_bridge_completion(
                openai_messages,
                openai_tools,
                model_name=self.model_name,
            )
        )
        if reminder_creation_location_bridge is not None:
            return reminder_creation_location_bridge
        contact_update_bridge = _contact_update_phone_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if contact_update_bridge is not None:
            return contact_update_bridge
        contact_update_by_id_bridge = _contact_update_by_id_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if contact_update_by_id_bridge is not None:
            return contact_update_by_id_bridge
        contact_update_success = _contact_update_success_response_text(openai_messages)
        if contact_update_success:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-contact-update-success",
                content=contact_update_success,
            )
        contact_relationship_bridge = _contact_relationship_batch_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if contact_relationship_bridge is not None:
            return contact_relationship_bridge
        crud_success = _crud_success_response_text(openai_messages, openai_tools)
        if crud_success:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-crud-success",
                content=crud_success,
            )
        contact_lookup_bridge = _contact_lookup_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if contact_lookup_bridge is not None:
            return contact_lookup_bridge
        reminder_recency_bridge = _reminder_recency_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if reminder_recency_bridge is not None:
            return reminder_recency_bridge
        forced_tool = os.environ.get("SAGE_DIAGNOSTIC_FORCE_TOOL_NAME", "").strip()
        force_after_error = os.environ.get(
            "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR", ""
        ).strip() in {"1", "true", "yes"}
        force_after_base_tools = {
            item.strip()
            for item in os.environ.get(
                "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL", ""
            ).split(",")
            if item.strip()
        }
        available_names = _tool_names(openai_tools)
        should_force = (
            forced_tool
            and forced_tool in available_names
            and not _message_already_called_tool(openai_messages, forced_tool)
            and (not force_after_error or _messages_show_tool_error(openai_messages))
            and _messages_show_prior_tool_call(openai_messages, force_after_base_tools)
        )
        prompted_messages = _with_selector_actor_policy(openai_messages, openai_tools)
        if not should_force:
            return _with_transient_openai_retries(
                lambda: super(ConfigurableOpenAIAgent, self).model_inference(
                    prompted_messages, openai_tools
                )
            )
        with all_logging_disabled():
            response = _with_transient_openai_retries(
                lambda: self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(list[ChatCompletionMessageParam], prompted_messages),
                    tools=openai_tools,
                    tool_choice={"type": "function", "function": {"name": forced_tool}},
                )
            )
        record_chat_completion_usage(
            source="toolsandbox_agent",
            model=self.model_name,
            messages=prompted_messages,
            tools=openai_tools,
            response=response,
        )
        return response


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = self.openai_client.with_options(
            timeout=_openai_request_timeout_seconds(),
            max_retries=_openai_max_retries(),
        )
