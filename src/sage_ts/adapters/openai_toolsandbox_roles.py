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
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from sage_ts.config.models import reasoning_effort_kwargs, resolve_model_name
from sage_ts.config.openai_client import build_robust_openai_client
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
MESSAGE_CONTACT_LOOKUP_COMPLETION_POLICY_SENTINEL = (
    "[SAGE message-contact-lookup completion policy]"
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
NATIVE_ACTION_TOOL_POLICY_SENTINEL = "[SAGE native-action tool policy]"
DYNAMIC_GENERATED_TOOL_SCHEMA_MAX = 3
MESSAGE_COUNTERPARTY_SEARCH_POLICY_SENTINEL = (
    "[SAGE message-counterparty search policy]"
)
MESSAGE_COUNTERPARTY_SELECTOR_SETUP_POLICY_SENTINEL = (
    "[SAGE message-counterparty selector setup policy]"
)
MESSAGE_COUNTERPARTY_UPDATE_COMPLETION_POLICY_SENTINEL = (
    "[SAGE message-counterparty update completion policy]"
)
MESSAGE_COUNTERPARTY_SELF_LOOKUP_HANDOFF_POLICY_SENTINEL = (
    "[SAGE message-counterparty self-lookup handoff policy]"
)
GENERATED_RECORD_HANDOFF_POLICY_SENTINEL = "[SAGE generated-record handoff policy]"
GENERATED_TOOL_ABSTAIN_CONTINUATION_POLICY_SENTINEL = (
    "[SAGE generated-tool abstain continuation policy]"
)
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
REMINDER_MISSING_TIME_POLICY_SENTINEL = "[SAGE reminder-missing-time policy]"
SHARED_TASK_CLOSURE_POLICY_SENTINEL = "[ToolSandbox shared task-closure policy]"
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


def _downstream_original_tool_from_payload(
    payload: Mapping[str, Any],
    openai_tools: object,
) -> str | None:
    """Resolve the original ToolSandbox tool a generated payload hands off to."""

    available_names = _tool_names_execution_facing(openai_tools)

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
    if bool(payload.get("should_call_search_contacts")) and isinstance(
        payload.get("search_contacts_kwargs"), Mapping
    ):
        candidates.append("search_contacts")
    if bool(payload.get("should_call_search_messages")) and isinstance(
        payload.get("search_messages_kwargs"), Mapping
    ):
        candidates.append("search_messages")
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


def _generated_downstream_original_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Follow a generated tool's explicit original-tool continuation."""

    available_names = _tool_names_execution_facing(openai_tools)
    state_action = _state_action_sequence_next_action(
        openai_messages,
        openai_tools,
    )
    if state_action is not None:
        state_tool = _execution_facing_tool_name(
            str(state_action.get("tool_name") or "")
        )
        if state_tool in available_names:
            return _tool_name_for_call(openai_tools, state_tool)
    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    if generated_names:
        pending_action = _next_generated_downstream_list_action(
            openai_messages, openai_tools
        )
        if pending_action is not None:
            pending_tool = _execution_facing_tool_name(
                str(pending_action.get("tool_name") or "")
            )
            if pending_tool in available_names:
                return _tool_name_for_call(openai_tools, pending_tool)
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    if latest is None:
        return None
    _helper_name, payload = latest
    return _downstream_original_tool_from_payload(payload, openai_tools)


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

    latest_generated = _latest_generated_helper_payload(
        openai_messages,
        openai_tools,
    )
    if latest_generated is not None:
        helper_name, payload = latest_generated
        native_action = str(payload.get("native_action") or "").strip()
        if (
            _generated_tool_uses_native_action(openai_tools, helper_name)
            and str(payload.get("status") or "").strip().lower() == "success"
            and native_action in ORIGINAL_SIDE_EFFECT_TOOL_NAMES
            and payload.get("native_result") is not None
        ):
            return True
    if "end_conversation" in _tool_names_execution_facing(openai_tools):
        return False
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


def _last_tool_result_index(openai_messages: object, tool_name: str) -> int:
    target = _execution_facing_tool_name(tool_name)
    latest = -1
    for index, message in enumerate(cast(Iterable[Mapping[str, Any]], openai_messages)):
        if message.get("role") != "tool":
            continue
        called = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if called == target:
            latest = index
    return latest


def _generated_tool_new_information_since_call(
    openai_messages: object,
    tool_name: str,
) -> bool:
    last_call = _last_tool_call_index(openai_messages, tool_name)
    if last_call < 0:
        return True
    last_result = _last_tool_result_index(openai_messages, tool_name)
    comparison_index = last_result if last_result >= 0 else last_call
    return _latest_any_tool_message_index(openai_messages) > comparison_index


def _declared_service_answer_producers(
    openai_tools: object,
    tool_name: str,
) -> tuple[str, ...]:
    """Read producer dependencies from all visible parts of the tool schema."""

    schema_text = ""
    if openai_tools is not NOT_GIVEN:
        target = _execution_facing_tool_name(tool_name)
        for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
            function = tool.get("function", {})
            if not isinstance(function, Mapping):
                continue
            name = function.get("name")
            if not isinstance(name, str):
                continue
            if _execution_facing_tool_name(name) == target:
                schema_text = _tool_schema_text(tool)
                break
    return tuple(
        name for name in sorted(SERVICE_ANSWER_PRODUCER_TOOLS) if name in schema_text
    )


def _latest_declared_service_payload_ready(
    openai_messages: object,
    openai_tools: object,
    tool_name: str,
) -> bool:
    """Require a current-turn result from a producer declared by the tool itself."""

    producers = set(_declared_service_answer_producers(openai_tools, tool_name))
    if not producers:
        return bool(_latest_service_answer_payload(openai_messages))
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = max(
        (
            index
            for index, message in enumerate(messages)
            if message.get("role") == "user"
        ),
        default=-1,
    )
    for message in reversed(messages[latest_user_index + 1 :]):
        if message.get("role") != "tool":
            continue
        producer = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if producer not in producers:
            continue
        content = str(message.get("content", "") or "").strip()
        lower = content.lower()
        return bool(content and "error" not in lower and "exception" not in lower)
    return False


def _dynamic_generated_tool_schema_filter(
    openai_messages: list[OpenAIMessage],
    openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    *,
    selected_tool_name: str | None = None,
) -> Union[Iterable[ChatCompletionToolParam], NotGiven]:
    """Keep generated tool schemas turn-local while leaving baseline tools intact."""

    if openai_tools is NOT_GIVEN:
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
    if (
        selected_execution_name in generated_names
        and _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            tools,
            selected_execution_name,
        )
        and _generated_tool_new_information_since_call(
            openai_messages,
            selected_execution_name,
        )
    ):
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
        )[:DYNAMIC_GENERATED_TOOL_SCHEMA_MAX]:
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


def _generated_tool_uses_native_action(
    openai_tools: object,
    tool_name: str,
) -> bool:
    execution_name = _execution_facing_tool_name(tool_name)
    try:
        runtime_tool = get_current_context().name_to_tool.get(execution_name)
    except Exception:
        runtime_tool = None
    if bool(getattr(runtime_tool, "sage_native_action_delegation", False)):
        return True
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        if _tool_schema_execution_name(tool) != execution_name:
            continue
        schema_text = _tool_schema_text(tool)
        return (
            "delegating to an approved native toolsandbox tool" in schema_text
            and "native tool remains the state-changing implementation" in schema_text
        )
    return False


def _generated_native_action_names(openai_tools: object) -> set[str]:
    """Return native actions owned by routed generated-tool contracts."""

    native_actions: set[str] = set()
    for tool_name in _generated_tool_names_execution_facing(openai_tools):
        native_actions.update(
            _generated_tool_native_action_names(openai_tools, tool_name)
        )
    return native_actions


def _generated_tool_native_action_names(
    openai_tools: object,
    tool_name: str,
) -> set[str]:
    """Return the original actions declared by one generated tool."""

    if not _generated_tool_uses_native_action(openai_tools, tool_name):
        return set()
    execution_tool_name = _execution_facing_tool_name(tool_name)
    try:
        runtime_tool = get_current_context().name_to_tool.get(execution_tool_name)
    except Exception:
        runtime_tool = None
    declared = getattr(runtime_tool, "sage_native_action_names", ())
    if isinstance(declared, str):
        declared = (declared,)
    return {
        execution_name
        for action_name in declared or ()
        if (execution_name := _execution_facing_tool_name(str(action_name)))
        in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    }


def _hide_wrapped_native_action_schemas(
    prompt_openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    *,
    routed_openai_tools: object,
    selected_tool_name: str | None = None,
) -> Union[Iterable[ChatCompletionToolParam], NotGiven]:
    """Hide wrapped actions except a generated contract's selected continuation."""

    if prompt_openai_tools is NOT_GIVEN:
        return prompt_openai_tools
    wrapped_actions = _generated_native_action_names(routed_openai_tools)
    if not wrapped_actions:
        return prompt_openai_tools
    selected_execution_name = _execution_facing_tool_name(selected_tool_name or "")
    return [
        tool
        for tool in cast(Iterable[ChatCompletionToolParam], prompt_openai_tools)
        if (
            _tool_schema_execution_name(cast(Mapping[str, Any], tool))
            not in wrapped_actions
            or _tool_schema_execution_name(cast(Mapping[str, Any], tool))
            == selected_execution_name
        )
    ]


def _native_action_tool_input_contracts(
    openai_tools: object,
    tool_names: Iterable[str],
) -> tuple[str, ...]:
    contracts: list[str] = []
    targets = {_execution_facing_tool_name(name) for name in tool_names}
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        name = _tool_schema_execution_name(tool)
        if name not in targets:
            continue
        inputs = sorted(_tool_input_names_execution_facing(openai_tools, name))
        if inputs:
            contracts.append(f"{name} inputs: {', '.join(inputs)}")
    return tuple(contracts)


def _native_action_tool_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Explain the validated native-action contract when one is visible."""

    native_action_names = [
        name
        for name in _generated_tool_names_execution_facing(openai_tools)
        if _generated_tool_uses_native_action(openai_tools, name)
    ]
    if not native_action_names:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if NATIVE_ACTION_TOOL_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    input_contracts = _native_action_tool_input_contracts(
        openai_tools, native_action_names
    )
    input_contract_text = (
        " Required generated-tool input contracts: " + "; ".join(input_contracts) + "."
        if input_contracts
        else ""
    )
    return {
        "role": "system",
        "content": (
            f"{NATIVE_ACTION_TOOL_POLICY_SENTINEL} Validated generated "
            f"native-action tools are visible: {', '.join(native_action_names)}. "
            "Unlike preparatory generated tools, a native-action tool may call "
            "exactly one approved original state-changing tool, as declared by "
            "its own description and schema. When its typed inputs are fully "
            "available from the user request or visible tool results, call it "
            "instead of separately repeating the final original action."
            + input_contract_text
            + " Do not omit a listed input. When the user supplies one or more "
            "field changes and the generated tool declares an updates input, pass "
            "those changes together in the updates mapping. Every updates key must "
            "exactly match a writable parameter named by the generated-tool schema "
            "and original native-action schema; do not copy role-prefixed record "
            "field names into updates. When an input description requires complete "
            "visible records, copy the matching original tool result intact; do "
            "not synthesize, summarize, reorder, or substitute a different record "
            "list. If that description mentions an is_self marker, use the visible "
            "original result containing the record whose is_self field is true. "
            "If the generated tool "
            "reports missing_required_helper_inputs, correct the omitted arguments "
            "on the next ordinary tool call; do not bypass it with the original "
            "state-changing action. A "
            "result with status='success', native_action, and native_result means "
            "the state change is complete; confirm it without calling the "
            "original action again. In that confirmation, preserve the user's "
            "visible target description and every visible changed field value "
            "from the native-action tool call; do not replace them with a generic "
            "success statement. If the generated-tool call includes a semantic "
            "selection_mode such as latest or oldest, describe the target by that "
            "visible relationship to the user's request. Do not perform another "
            "lookup solely to replace a semantically identified target with an "
            "internal identifier or proper name. A result with status='abstain' means no "
            "action occurred; respect the abstain_reason and do not invent "
            "missing identifiers, records, or updates."
        ),
    }


def _message_already_called_any_generated_tool(
    openai_messages: object,
    openai_tools: object,
) -> bool:
    return any(
        _message_already_called_tool(openai_messages, tool_name)
        for tool_name in _generated_tool_names_execution_facing(openai_tools)
    )


def _message_called_any_generated_tool_after_latest_user(
    openai_messages: object,
    openai_tools: object,
) -> bool:
    return any(
        _called_tool_after_latest_user(openai_messages, tool_name)
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


def _latest_user_requests_structured_update(openai_messages: object) -> bool:
    """Return whether the current visible user turn supplies update intent."""

    latest_user = " ".join(
        _latest_user_request_text(openai_messages)
        .lower()
        .replace("\u2019", "'")
        .split()
    )
    if not latest_user:
        return False
    return bool(
        re.search(
            r"\b(?:change|correct|delay|edit|make|mark|modify|move|postpone|"
            r"rename|replace|reschedule|restore|set|switch|turn|update)\b",
            latest_user,
        )
    )


def _generated_tool_inputs_ready_for_current_turn(
    openai_messages: object,
    openai_tools: object,
    tool_name: str,
) -> bool:
    execution_tool_name = _execution_facing_tool_name(tool_name)
    if execution_tool_name in _search_window_tool_names(
        openai_tools
    ) and not _recency_search_window_requested(openai_messages):
        # A retained search-window tool is not a generic temporal parser. Only
        # expose it when the visible request actually asks for a recency-bounded
        # search; otherwise it can steal reminder-creation or clarification turns.
        return False
    device_setters = {
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
        "set_wifi_status",
    }
    native_actions = _generated_tool_native_action_names(openai_tools, tool_name)
    if native_actions and native_actions <= device_setters:
        return (
            _latest_original_state_precondition_error(openai_messages) is not None
            or _latest_user_requests_direct_device_state_action(openai_messages)
            or _first_user_is_device_mutation_without_message(openai_messages)
            or (
                _latest_user_requests_device_state_repair(openai_messages)
                and _device_status_evidence_after_latest_user(openai_messages)
            )
        )
    if execution_tool_name.startswith("plan_device_state_action_sequence"):
        return (
            _latest_original_state_precondition_error(openai_messages) is not None
            or _latest_user_requests_direct_device_state_action(openai_messages)
            or _first_user_is_device_mutation_without_message(openai_messages)
            or (
                _latest_user_requests_device_state_repair(openai_messages)
                and _device_status_evidence_after_latest_user(openai_messages)
            )
        )
    if execution_tool_name == "plan_contact_lookup_query":
        if (
            "plan_contact_relationship_batch_update"
            in _tool_names_execution_facing(openai_tools)
            and _relationship_batch_request(openai_messages) is not None
        ):
            return False
        return (
            _latest_original_search_has_records(openai_messages)
            or _contact_lookup_request(openai_messages) is not None
            or bool(_contact_remove_by_phone_request(openai_messages))
            or _extract_send_message_contact_request(openai_messages) is not None
            or _visible_named_send_recipient_present(openai_messages)
        )
    if execution_tool_name == "plan_send_message_contact_lookup":
        return _extract_send_message_contact_request(openai_messages) is not None
    if execution_tool_name == "plan_message_counterparty_search":
        return True
    if execution_tool_name == "plan_contact_relationship_batch_update":
        return _relationship_batch_request(openai_messages) is not None
    if execution_tool_name == "relative_day_time_to_timestamp":
        creation_request = _relative_reminder_creation_request(openai_messages)
        if (
            creation_request is not None
            and not str(creation_request.get("content") or "").strip()
        ):
            return False
        return _visible_relative_day_time_request(openai_messages)
    if execution_tool_name == "next_weekday_time_to_timestamp":
        creation_request = _weekday_reminder_creation_request(openai_messages)
        if (
            creation_request is not None
            and not str(creation_request.get("content") or "").strip()
        ):
            return False
        return _visible_next_weekday_time_request(openai_messages)
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    if not input_names:
        return True
    if "updates" in input_names and not _latest_user_requests_structured_update(
        openai_messages
    ):
        # A retained update tool can be relevant to a multi-turn task before the
        # user has supplied the actual change. Keep the schema hidden until that
        # visible requirement exists so lookup turns remain lookup-only. A
        # multi-action tool with an explicit action_type may also implement a
        # removal contract where updates is intentionally empty.
        explicit_removal = bool(
            "action_type" in input_names
            and _visible_removal_action_requested(
                _latest_user_request_text(openai_messages)
            )
        )
        if not explicit_removal:
            return False
    if (
        execution_tool_name == "prepare_reminder_creation_args"
        and _generated_tool_uses_native_action(openai_tools, tool_name)
        and "reminder_timestamp" in input_names
    ):
        for creation_request in (
            _absolute_reminder_creation_request(openai_messages),
            _relative_reminder_creation_request(openai_messages),
            _weekday_reminder_creation_request(openai_messages),
        ):
            if (
                creation_request is not None
                and not str(creation_request.get("content") or "").strip()
            ):
                return False
        resolved_timestamp = next(
            (
                value
                for producer in (
                    "relative_day_time_to_timestamp",
                    "next_weekday_time_to_timestamp",
                    "datetime_info_to_timestamp",
                )
                if (value := _timestamp_from_latest_tool(openai_messages, producer))
                is not None
                and value > 0
            ),
            None,
        )
        if resolved_timestamp is None:
            return False
        if (
            _reminder_location_parts(openai_messages) is not None
            and _latest_tool_message(openai_messages, "search_location_around_lat_lon")
            is None
        ):
            return False
    if (
        {"records", "updates"}.issubset(input_names)
        and "modify_reminder"
        in _tool_description_execution_facing(openai_tools, tool_name).lower()
        and _reminder_recency_request(openai_messages)
        in {"modify_latest", "modify_upcoming"}
        and _tomorrow_time_request(openai_messages) is not None
        and _timestamp_from_latest_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
        is None
    ):
        # An update selector must not be forced before its explicit update
        # value exists. The generated tool's negative contract correctly abstains
        # on an empty updates mapping, so keep it hidden until the visible temporal
        # producer has completed.
        return False
    if "records" in input_names:
        record_source = _latest_compatible_original_record_source_with_records(
            openai_messages,
            openai_tools,
            tool_name,
        )
        if record_source is None:
            return False
    if "contacts" in input_names and not _latest_search_contacts_has_records(
        openai_messages
    ):
        return False
    if "stock_payload" in input_names and not _latest_tool_has_nonempty_payload(
        openai_messages, "search_stock"
    ):
        return False
    if "service_payload" in input_names and not _latest_declared_service_payload_ready(
        openai_messages,
        openai_tools,
        tool_name,
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


def _visible_next_weekday_time_request(openai_messages: object) -> bool:
    weekday_names = "|".join(WEEKDAY_NAME_TO_ISO)
    text = " ".join(_all_user_texts(openai_messages)).lower()
    if not re.search(rf"\bnext\s+(?:{weekday_names})\b", text):
        return False
    return bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b", text))


def _visible_relative_day_time_request(openai_messages: object) -> bool:
    weekday_names = "|".join(WEEKDAY_NAME_TO_ISO)
    text = " ".join(_all_user_texts(openai_messages)).lower()
    if not re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b", text):
        return False
    if re.search(rf"\bnext\s+(?:{weekday_names})\b", text):
        return False
    return bool(
        re.search(
            r"\b(?:today|tomorrow|tonight|yesterday|next\s+week|in\s+(?:a|one|two|three|\d+)\s+(?:day|days|week|weeks)|\d+\s+(?:day|days|week|weeks)\s+from)\b",
            text,
        )
    )


def _latest_user_requests_direct_device_state_action(openai_messages: object) -> bool:
    latest_user = (
        _latest_user_request_text(openai_messages).lower().replace("wi-fi", "wifi")
    )
    if not latest_user:
        return False
    return any(
        token in latest_user
        for token in (
            "wifi",
            "cellular",
            "mobile service",
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


def _latest_user_requests_device_state_repair(openai_messages: object) -> bool:
    """Detect a visible request to repair a device capability, not just read it."""

    latest_user = " ".join(
        _latest_user_request_text(openai_messages)
        .lower()
        .replace("wi-fi", "wifi")
        .replace("\u2019", "'")
        .split()
    )
    if not latest_user:
        return False
    has_device_context = any(
        token in latest_user
        for token in (
            "wifi",
            "internet",
            "cellular",
            "mobile service",
            "phone signal",
            "location",
            "battery",
            "settings",
        )
    )
    has_repair_intent = any(
        token in latest_user
        for token in (
            "fix",
            "repair",
            "can't",
            "cannot",
            "unable",
            "not working",
            "doesn't work",
            "help me",
            "problem",
            "issue",
        )
    )
    if not (has_device_context and has_repair_intent):
        return False
    status_only = bool(
        re.search(
            r"\b(?:check|tell me|what is|what's|is|are)\b.*"
            r"\b(?:status|on|off|enabled|disabled)\b",
            latest_user,
        )
    )
    return not status_only or has_repair_intent


def _device_status_evidence_after_latest_user(openai_messages: object) -> bool:
    """Return whether the actor has gathered visible setting state this turn."""

    latest_user_index = _latest_user_index(openai_messages)
    latest_status = _latest_tool_message_index(
        openai_messages,
        {
            "get_wifi_status",
            "get_cellular_service_status",
            "get_location_service_status",
            "get_low_battery_mode_status",
        },
    )
    return latest_status is not None and latest_status[0] > latest_user_index


def _state_action_planner_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    helper_names = sorted(_state_action_planner_tool_names(openai_tools))
    if not helper_names:
        return None
    sequence_helpers = [
        helper_name
        for helper_name in helper_names
        if _execution_facing_tool_name(helper_name).startswith(
            "plan_device_state_action_sequence"
        )
    ]
    state_precondition = _latest_original_state_precondition_error(openai_messages)
    repair_evidence_ready = _latest_user_requests_device_state_repair(
        openai_messages
    ) and _device_status_evidence_after_latest_user(openai_messages)
    if state_precondition is not None or repair_evidence_ready:
        preferred_helpers = sequence_helpers or helper_names
        latest_evidence_index = (
            state_precondition[0]
            if state_precondition is not None
            else _latest_tool_message_index(
                openai_messages,
                {
                    "get_wifi_status",
                    "get_cellular_service_status",
                    "get_location_service_status",
                    "get_low_battery_mode_status",
                },
            )[0]
        )
        latest_plan = _latest_tool_message_index(
            openai_messages, set(preferred_helpers)
        )
        if latest_plan is None or latest_plan[0] < latest_evidence_index:
            for helper_name in preferred_helpers:
                if _generated_tool_inputs_ready_for_current_turn(
                    openai_messages,
                    openai_tools,
                    helper_name,
                ):
                    return _tool_name_for_call(openai_tools, helper_name)
    if _latest_user_requests_direct_device_state_action(
        openai_messages
    ) or _first_user_is_device_mutation_without_message(openai_messages):
        for helper_name in sequence_helpers or helper_names:
            if not _message_already_called_tool(openai_messages, helper_name):
                return _tool_name_for_call(openai_tools, helper_name)
    return None


def _generated_tool_choice_priority(openai_tools: object, tool_name: str) -> int:
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    output_names = _tool_output_names_execution_facing(openai_tools, tool_name)
    tool_lower = _execution_facing_tool_name(tool_name).lower()
    if _generated_tool_uses_native_action(openai_tools, tool_name):
        return -1
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
    if tool_lower in {
        "prepare_broad_location_search_args",
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
    }:
        return 0
    if (
        "timestamp" in tool_lower
        or {"days", "seconds"} <= output_names
        or tool_lower.startswith(("relative_", "next_weekday_"))
    ):
        return 1
    if (
        output_names & side_effect_outputs
        or "should_call_tool" in output_names
        or action_argument_name
    ):
        return 2
    if input_names & {"records", "messages", "selected_record"} and output_names & {
        "answer_value",
        "exact_final_answer",
        "final_answer",
        "final_answer_recommendation",
        "selected_content",
        "should_answer",
    }:
        return 3
    if output_names & search_argument_outputs:
        return 3
    if "records" in input_names or "contacts" in input_names:
        return 4
    return 5


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
            "contacted",
            "texted",
            "sent",
            "received",
        )
    ):
        return False
    if not any(
        token in request
        for token in (
            "yesterday",
            "today",
            "upcoming",
            "next reminder",
            "next todo",
            "next to-do",
            "latest",
            "oldest",
            "most recent",
            "newest",
            "earliest",
            "last",
            "previous day",
            "prior day",
            "last",
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
    message_record_tools_requiring_self = [
        tool_name
        for tool_name in generated_names
        if {"records", "self_person_id"}.issubset(
            _tool_input_names_execution_facing(openai_tools, tool_name)
        )
        and "search_messages"
        in _tool_schema_text(
            next(
                tool
                for tool in cast(Iterable[Mapping[str, Any]], openai_tools)
                if _tool_schema_execution_name(tool)
                == _execution_facing_tool_name(tool_name)
            )
        )
    ]
    if message_record_tools_requiring_self:
        if (
            "search_contacts" in available_names
            and not _latest_self_person_id_from_contacts(openai_messages)
            and not _message_already_called_tool(openai_messages, "search_contacts")
        ):
            return _tool_name_for_call(openai_tools, "search_contacts")
        latest_contacts = _latest_tool_message_index(
            openai_messages, {"search_contacts"}
        )
        latest_messages = _latest_tool_message_index(
            openai_messages, {"search_messages"}
        )
        if (
            "search_messages" in available_names
            and _latest_self_person_id_from_contacts(openai_messages)
            and latest_contacts is not None
            and (latest_messages is None or latest_messages[0] < latest_contacts[0])
        ):
            return _tool_name_for_call(openai_tools, "search_messages")
    message_recency_mode = _message_recency_request(openai_messages)
    if (
        "select_message_content_by_recency" in generated_names
        and message_recency_mode is not None
        and "search_messages" in available_names
    ):
        if (
            "get_current_timestamp" in available_names
            and _latest_current_timestamp(openai_messages) is None
            and not _message_already_called_tool(
                openai_messages, "get_current_timestamp"
            )
        ):
            return _tool_name_for_call(openai_tools, "get_current_timestamp")
        latest_user_index = _latest_user_index(openai_messages)
        latest_messages = _latest_tool_message_index(
            openai_messages, {"search_messages"}
        )
        if latest_messages is None or latest_messages[0] < latest_user_index:
            return _tool_name_for_call(openai_tools, "search_messages")
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
            # A satisfied recency-window timestamp prerequisite must not hide a
            # second generated temporal tool's datetime-info prerequisite.
            break

    timestamp_prerequisite_tools = {
        "prepare_message_recency_search_args",
        "prepare_past_reminder_recency_search_args",
        "prepare_upcoming_reminder_search_args",
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
        if execution_tool_name in _search_window_tool_names(
            openai_tools
        ) and not _recency_search_window_requested(openai_messages):
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
    generated_names = _generated_tool_names_execution_facing(openai_tools)
    if not generated_names:
        return None
    if _message_already_called_any_generated_tool(openai_messages, openai_tools):
        return None
    prerequisite_choice = _generated_tool_prerequisite_choice(
        openai_messages,
        openai_tools,
    )
    if prerequisite_choice is not None:
        return prerequisite_choice
    for preferred_tool in ("plan_message_counterparty_search",):
        if preferred_tool not in generated_names:
            continue
        if _message_already_called_tool(openai_messages, preferred_tool):
            continue
        if _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            preferred_tool,
        ):
            return _tool_name_for_call(openai_tools, preferred_tool)
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
    if (
        "next_weekday_time_to_timestamp" in generated_names
        and _visible_next_weekday_time_request(openai_messages)
        and not _message_already_called_tool(
            openai_messages,
            "next_weekday_time_to_timestamp",
        )
        and _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            "next_weekday_time_to_timestamp",
        )
    ):
        return _tool_name_for_call(openai_tools, "next_weekday_time_to_timestamp")
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


def _new_user_turn_generated_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Allow generated-tool routing when a later user turn adds new requirements."""
    generated_names = _generated_tool_names_execution_facing(openai_tools)
    if not generated_names:
        return None
    latest_user_index = _latest_user_index(openai_messages)
    if latest_user_index < 0:
        return None
    latest_generated_call_index = max(
        (
            _last_tool_call_index(openai_messages, tool_name)
            for tool_name in generated_names
        ),
        default=-1,
    )
    if latest_user_index <= latest_generated_call_index:
        return None
    if _message_called_any_generated_tool_after_latest_user(
        openai_messages,
        openai_tools,
    ):
        return None
    prerequisite_choice = _generated_tool_prerequisite_choice(
        openai_messages,
        openai_tools,
    )
    if prerequisite_choice is not None:
        return prerequisite_choice
    ready_tools = [
        (index, tool_name)
        for index, tool_name in enumerate(generated_names)
        if _generated_tool_inputs_ready_for_current_turn(
            openai_messages,
            openai_tools,
            tool_name,
        )
        and not _called_tool_after_latest_user(openai_messages, tool_name)
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


def _relationship_batch_generated_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Select the generated relationship-batch planner for visible update turns."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_contact_relationship_batch_update" not in available_names:
        return None
    if not ({"search_contacts", "modify_contact"} <= available_names):
        return None
    if _called_tool_after_latest_user(
        openai_messages,
        "plan_contact_relationship_batch_update",
    ):
        return None
    if _relationship_batch_request(openai_messages) is None:
        return None
    return _tool_name_for_call(openai_tools, "plan_contact_relationship_batch_update")


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
    if tool_name in {*SERVICE_ANSWER_EXTRACTOR_TOOLS, "extract_stock_symbol"}:
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
    counterparty_handoff = _message_counterparty_self_lookup_tool_choice(
        openai_messages,
        openai_tools,
    )
    if counterparty_handoff is not None:
        return counterparty_handoff
    location_relative_choice = _relative_time_after_location_search_tool_choice(
        openai_messages,
        openai_tools,
    )
    if location_relative_choice is not None:
        return location_relative_choice
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


def _relative_time_after_location_search_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Continue a multi-generated-tool reminder path after location search records."""

    available_names = _tool_names_execution_facing(openai_tools)
    if "relative_day_time_to_timestamp" not in available_names:
        return None
    if _message_already_called_tool(openai_messages, "relative_day_time_to_timestamp"):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    if not location_arg_tool:
        return None
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
    latest_search = _latest_tool_message_index(
        openai_messages,
        {"search_location_around_lat_lon"},
    )
    if latest_prepare is None or latest_search is None:
        return None
    if latest_search[0] <= latest_prepare[0]:
        return None
    if not _latest_location_search_records(openai_messages):
        return None
    if not _visible_relative_day_time_request(openai_messages):
        return None
    if not _generated_tool_inputs_ready_for_current_turn(
        openai_messages,
        openai_tools,
        "relative_day_time_to_timestamp",
    ):
        return None
    return _tool_name_for_call(openai_tools, "relative_day_time_to_timestamp")


def _reminder_location_batch_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Keep relative reminder-location workflows on generated prep tools."""

    available_names = _tool_names_execution_facing(openai_tools)
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    reminder_finalizer = "prepare_reminder_creation_args"
    if not location_arg_tool:
        return None
    required = {
        location_arg_tool,
        "search_location_around_lat_lon",
        "get_current_timestamp",
        "timestamp_to_datetime_info",
        reminder_finalizer,
        "add_reminder",
    }
    native_finalizer = _generated_tool_uses_native_action(
        openai_tools, reminder_finalizer
    )
    if native_finalizer:
        required.add("relative_day_time_to_timestamp")
    if not (required <= available_names):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    request = _relative_reminder_creation_request(openai_messages)
    parts = _reminder_location_parts(openai_messages)
    if request is None or parts is None:
        return None
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
    latest_search = _latest_tool_message_index(
        openai_messages,
        {"search_location_around_lat_lon"},
    )
    search_after_prepare = (
        latest_prepare is not None
        and latest_search is not None
        and latest_search[0] > latest_prepare[0]
        and bool(_latest_location_search_records(openai_messages))
    )
    if latest_prepare is None:
        return _tool_name_for_call(openai_tools, location_arg_tool)
    if not search_after_prepare:
        return _tool_name_for_call(openai_tools, "search_location_around_lat_lon")
    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None:
        return _tool_name_for_call(openai_tools, "get_current_timestamp")
    current_info = _timestamp_to_datetime_info_for_timestamp(
        openai_messages,
        current_timestamp,
    )
    if current_info is None:
        return _tool_name_for_call(openai_tools, "timestamp_to_datetime_info")
    if (
        native_finalizer
        and _timestamp_from_latest_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
        is None
    ):
        return _tool_name_for_call(openai_tools, "relative_day_time_to_timestamp")
    latest_reminder_prepare = _latest_tool_message_index(
        openai_messages,
        {reminder_finalizer},
    )
    if latest_reminder_prepare is None or latest_reminder_prepare[0] < max(
        latest_search[0],
        latest_prepare[0],
    ):
        return _tool_name_for_call(openai_tools, reminder_finalizer)
    return None


def _message_counterparty_self_lookup_tool_choice(
    openai_messages: object,
    openai_tools: object,
) -> str | None:
    """Force the second staged planner call after original self-contact lookup."""

    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_message_counterparty_search" not in available_names:
        return None
    latest_plan = _latest_tool_message_index(
        openai_messages, {"plan_message_counterparty_search"}
    )
    latest_contacts = _latest_tool_message_index(openai_messages, {"search_contacts"})
    if latest_plan is None or latest_contacts is None:
        return None
    plan_index, plan_message = latest_plan
    contacts_index, contacts_message = latest_contacts
    if contacts_index < plan_index:
        return None
    if _assistant_called_tool_after_index(
        openai_messages,
        "plan_message_counterparty_search",
        contacts_index,
    ):
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
    return _tool_name_for_call(openai_tools, "plan_message_counterparty_search")


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
    request = _reminder_recency_request(openai_messages)
    modify_request = request in {"modify_latest", "modify_upcoming"}
    remove_request = request in {"remove_latest", "remove_upcoming"}
    if not (modify_request or remove_request):
        return None
    if modify_request and _tomorrow_time_request(openai_messages) is None:
        return None
    reminder_records = _records_from_latest_reminder_search(openai_messages)
    native_selector = next(
        (
            tool_name
            for tool_name in _generated_tool_names_execution_facing(openai_tools)
            if _generated_tool_uses_native_action(openai_tools, tool_name)
            and {"records", "updates"}.issubset(
                _tool_input_names_execution_facing(openai_tools, tool_name)
            )
            and (
                "action_type"
                in _tool_input_names_execution_facing(openai_tools, tool_name)
                or "modify_reminder"
                in _tool_description_execution_facing(openai_tools, tool_name).lower()
            )
        ),
        None,
    )
    native_records_ready = bool(native_selector and reminder_records)
    if (
        remove_request
        and native_selector
        and native_records_ready
        and not _message_already_called_tool(openai_messages, native_selector)
    ):
        return _tool_name_for_call(openai_tools, native_selector)
    if remove_request and reminder_records and not native_selector:
        for selector_name in (
            "select_record_by_timestamp_extreme",
            "select_action_target_by_recency",
        ):
            if selector_name in available_names and not _message_already_called_tool(
                openai_messages, selector_name
            ):
                return _tool_name_for_call(openai_tools, selector_name)

    current_timestamp = _latest_current_timestamp(openai_messages)
    if current_timestamp is None and (modify_request or not reminder_records):
        if "get_current_timestamp" in available_names:
            return _tool_name_for_call(openai_tools, "get_current_timestamp")
        return None
    if not reminder_records:
        preferred_search_planners = (
            ("prepare_upcoming_reminder_search_args",)
            if request in {"modify_upcoming", "remove_upcoming"}
            else (
                "prepare_past_reminder_recency_search_args",
                "resolve_search_window_or_bounds",
            )
        )
        for planner_name in preferred_search_planners:
            if (
                planner_name in available_names
                and not _message_already_called_tool(openai_messages, planner_name)
                and _generated_tool_inputs_ready_for_current_turn(
                    openai_messages,
                    openai_tools,
                    planner_name,
                )
            ):
                return _tool_name_for_call(openai_tools, planner_name)
    if remove_request:
        if native_selector and _message_already_called_tool(
            openai_messages, native_selector
        ):
            return None
        reminder_id = _selected_reminder_id_after_generated_selection(openai_messages)
        if (
            reminder_id
            and "remove_reminder" in available_names
            and not _message_called_execution_tool_after_tool(
                openai_messages,
                "remove_reminder",
                {
                    "select_record_by_timestamp_extreme",
                    "select_action_target_by_recency",
                },
            )
        ):
            return _tool_name_for_call(openai_tools, "remove_reminder")
        return None

    if current_timestamp is None:
        return None
    reminder_id = _selected_reminder_id_after_generated_selection(openai_messages)
    if not reminder_id and not native_records_ready:
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
        native_selector
        and native_records_ready
        and _timestamp_from_latest_tool(
            openai_messages, "relative_day_time_to_timestamp"
        )
        is not None
        and not _message_already_called_tool(openai_messages, native_selector)
    ):
        return _tool_name_for_call(openai_tools, native_selector)
    if (
        "modify_reminder" in available_names
        and reminder_id
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
    return _latest_original_record_source_with_records(openai_messages) is not None


def _latest_original_record_source_with_records(
    openai_messages: object,
) -> str | None:
    """Return the most recent original record producer with visible records."""

    latest: tuple[int, str] | None = None
    for tool_name in (
        "search_reminder",
        "search_messages",
        "search_contacts",
        "search_location_around_lat_lon",
    ):
        indexed = _latest_tool_message_index(openai_messages, {tool_name})
        if indexed is None or not _parse_sequence_payload(indexed[1].get("content")):
            continue
        if latest is None or indexed[0] > latest[0]:
            latest = (indexed[0], tool_name)
    return latest[1] if latest is not None else None


def _latest_compatible_original_record_source_with_records(
    openai_messages: object,
    openai_tools: object,
    tool_name: str,
) -> str | None:
    """Return the newest visible record source accepted by a tool contract."""

    latest: tuple[int, str] | None = None
    for record_source_name in (
        "search_reminder",
        "search_messages",
        "search_contacts",
        "search_location_around_lat_lon",
    ):
        if not _generated_tool_consumes_latest_record_source(
            openai_tools,
            tool_name,
            record_source_name,
        ):
            continue
        indexed = _latest_tool_message_index(openai_messages, {record_source_name})
        if indexed is None or not _parse_sequence_payload(indexed[1].get("content")):
            continue
        if latest is None or indexed[0] > latest[0]:
            latest = (indexed[0], record_source_name)
    return latest[1] if latest is not None else None


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
        is_window_helper = (
            name
            in {
                "prepare_message_recency_search_args",
                "prepare_past_reminder_recency_search_args",
                "resolve_search_window_or_bounds",
                "prepare_upcoming_reminder_search_args",
            }
            or (
                "current_timestamp" in input_names
                and "search kwargs" in description
                and "reminder" in description
            )
            or (
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
            and ("device-state" in description or "device state" in description)
        )
        has_structured_state_action_inputs = {
            "target_service",
            "desired_on",
        }.issubset(input_names)
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
        is_structured_state_action_tool = has_structured_state_action_inputs and (
            name.startswith("plan_device_state_action_sequence")
            or name.startswith("apply_single_device_state_action")
            or "device-state" in description
            or "device state" in description
        )
        is_state_action_planner = (
            is_named_state_action_planner
            or is_next_service_planner
            or is_described_state_action_planner
            or is_structured_state_action_tool
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
        "hide that message",
        "hide the message",
        "hide it",
        "not visible anymore",
        "not visible",
        "make sure that message is not visible",
        "make sure it is not visible",
        "don't have enough information",
        "do not have enough information",
        "not enough information",
        "don't have any details",
        "do not have any details",
        "no details",
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
        "hide that message",
        "hide the message",
        "hide it",
        "not visible anymore",
        "not visible",
        "make sure that message is not visible",
        "make sure it is not visible",
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
        copy_exactly = bool(payload.get("copy_exactly"))
        candidate = str(
            payload.get("exact_final_answer")
            or payload.get("final_answer_recommendation")
            or ""
        ).strip()
        if candidate and not candidate.lower().startswith("abstain:"):
            if (
                tool_name == "plan_device_status_lookup"
                or copy_exactly
                or payload.get("exact_final_answer")
            ):
                answer = candidate
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
        "looking for that number",
        "looking for the number",
        "looking for that phone number",
        "looking for the phone number",
        "search for that number",
        "search for the number",
        "search for that phone number",
        "search for the phone number",
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


def _latest_tool_payload_by_name_including_latest(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return {}
    return _parse_mapping_payload(message.get("content"))


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


def _available_state_sequence_actions(
    payload: Mapping[str, Any],
    openai_tools: object,
) -> list[dict[str, Any]]:
    """Project a generated sequence onto the current native action surface."""

    available_names = _tool_names_execution_facing(openai_tools)
    return [
        action
        for action in _state_sequence_actions(payload)
        if action["tool_name"] in available_names
    ]


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
    actions = _available_state_sequence_actions(payload, openai_tools)
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
            r".*?\b(?:to|into|as)\s+(?:(?:be|being)\s+)?(?:my\s+)?([a-z]+)\b",
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
                r"\b(?:to|into|as)\s+(?:(?:be|being)\s+)?(?:my\s+)?([a-z]+)\b",
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
            r"(?:(?:be|being)\s+)?(?:my\s+)?([a-z]+)\b",
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
            r"(?:(?:to|into|as)\s+)?(?:(?:be|being)\s+)?(?:my\s+)?([a-z]+)\b",
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
                r"\b(?:to|as)\s+(?:(?:be|being)\s+)?(?:my\s+)?([a-z]+)\b",
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


def _next_generated_downstream_list_action(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, Any] | None:
    """Return the next original call from any generated tool's ordered call list."""

    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    available_names = _tool_names_execution_facing(openai_tools)
    if not generated_names or not available_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for plan_index in range(len(messages) - 1, -1, -1):
        plan_message = messages[plan_index]
        if plan_message.get("role") != "tool":
            continue
        generated_name = _execution_facing_tool_name(
            str(plan_message.get("name", "") or "")
        )
        if generated_name not in generated_names:
            continue
        payload = _parse_mapping_payload(plan_message.get("content"))
        raw_actions = payload.get("downstream_tool_kwargs_list")
        downstream_name = _execution_facing_tool_name(
            str(payload.get("downstream_tool_name") or "")
        )
        if (
            not isinstance(raw_actions, list)
            or not downstream_name
            or downstream_name not in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
            or downstream_name not in available_names
        ):
            continue
        actions: list[dict[str, Any]] = []
        for item in raw_actions:
            if not isinstance(item, Mapping):
                continue
            arguments = _call_contract_kwargs(item)
            if arguments:
                actions.append({"tool_name": downstream_name, "arguments": arguments})
        if not actions:
            continue
        completed = 0
        for message in messages[plan_index + 1 :]:
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for tool_call in tool_calls:
                if not isinstance(tool_call, Mapping) or completed >= len(actions):
                    continue
                name, arguments = _tool_call_function_name_and_arguments(tool_call)
                expected = actions[completed]
                if _execution_facing_tool_name(name) != expected["tool_name"]:
                    continue
                if _arguments_match(expected["arguments"], arguments):
                    completed += 1
        if completed < len(actions):
            return actions[completed]
    return None


def _generated_downstream_list_instruction(
    openai_messages: object,
    openai_tools: object,
) -> str:
    action = _next_generated_downstream_list_action(openai_messages, openai_tools)
    if action is None:
        return ""
    tool_name = _execution_facing_tool_name(str(action.get("tool_name") or ""))
    arguments = action.get("arguments")
    if not tool_name or not isinstance(arguments, Mapping):
        return ""
    visible_tool_name = _tool_name_for_call(openai_tools, tool_name)
    return (
        " A generated tool returned an ordered list of original ToolSandbox calls. "
        "The next unsatisfied original call is "
        f"{tool_name}. In the current visible tool list, call {visible_tool_name} "
        f"with exactly these arguments: {json.dumps(dict(arguments), sort_keys=True)}. "
        "Do not answer, ask for confirmation, or skip ahead until this original "
        "side-effect call has been attempted."
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


def _extract_phone_from_text(text: str) -> str:
    text_without_ids = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        " ",
        text,
    )
    match = re.search(r"\+?\d[\d\s().-]{6,}\d", text_without_ids)
    return _normalize_visible_phone(match.group(0)) if match else ""


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
    helper_execution_names = {_execution_facing_tool_name(name) for name in helpers}
    service_scalar_extractors = {
        "extract_service_answer_field",
        "extract_address_result",
        "extract_converted_amount_result",
        "extract_distance_result",
        "extract_temperature_result",
    }
    if not (helper_execution_names & service_scalar_extractors):
        return ""
    if any(
        _message_already_called_tool(openai_messages, name)
        for name in service_scalar_extractors
    ):
        return ""
    scalar_tool_name = ""
    requested_unit = ""
    answer_subject = ""
    for candidate_name in (
        "calculate_lat_lon_distance",
        "convert_currency",
        "unit_conversion",
        "search_lat_lon",
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
    elif scalar_tool_name == "search_lat_lon":
        answer_subject = "address"
    preferred_extractors = {
        "calculate_lat_lon_distance": (
            "extract_distance_result",
            "extract_service_answer_field",
        ),
        "convert_currency": (
            "extract_converted_amount_result",
            "extract_service_answer_field",
        ),
        "unit_conversion": (
            "extract_temperature_result",
            "extract_service_answer_field",
        ),
        "search_lat_lon": ("extract_address_result", "extract_service_answer_field"),
    }
    extractor_name = next(
        (
            name
            for name in preferred_extractors.get(scalar_tool_name, ())
            if name in helper_execution_names
        ),
        "",
    )
    if not extractor_name:
        return ""
    tool_name = _tool_name_for_call(openai_tools, extractor_name)
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
    helpers = {
        name
        for name in helpers
        if "service_payload"
        not in _tool_input_names_execution_facing(openai_tools, name)
        or _latest_declared_service_payload_ready(
            openai_messages,
            openai_tools,
            name,
        )
    }
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
    phone_subject_instruction = ""
    if "extract_phone_number_result" in helpers:
        phone_subject = _phone_location_lookup_query(openai_messages) or ""
        if phone_subject:
            phone_subject_instruction = (
                " For extract_phone_number_result, set answer_subject exactly to "
                f"{json.dumps(phone_subject)} so the generated tool can produce "
                "the complete final-answer recommendation while preserving the "
                "visible phone_number value exactly."
            )
    temperature_subject_instruction = ""
    if "extract_temperature_result" in helpers:
        temperature_subject = _weather_location_query(openai_messages) or ""
        if temperature_subject:
            temperature_subject_instruction = (
                " For extract_temperature_result, set answer_subject exactly to "
                f"{json.dumps(temperature_subject)} so the generated tool can "
                "produce the complete final-answer recommendation. Set requested_metric "
                "from the user's visible request using exactly one canonical selector "
                "value listed in that generated tool's requested_metric parameter "
                "description; translate visible user synonyms to that declared value. "
                "The generated tool completes any visible deterministic unit conversion "
                "and returns the answer-ready value in one call."
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
            "bare scalar such as a distance, converted number, or address string, pass a JSON "
            "object wrapper like {'result': value} as the payload. If the "
            "helper has a dict payload input, the runtime may "
            "autofill that input from the latest original tool result; provide any "
            "remaining scalar selector inputs such as requested_field, "
            "requested_unit, or answer_subject. For Fahrenheit weather requests, "
            "set requested_unit='Fahrenheit'. For distance requests, set "
            "requested_unit='kilometers' unless the user requested a different "
            "visible unit, and set answer_subject to the requested destination "
            "or place name. For currency, weather, address, phone number, and "
            "distance tasks, call the extraction helper after the original "
            "lookup, distance, or conversion returns instead of manually copying the answer "
            "field. If the generated tool returns should_call_downstream_tool=true, "
            "call the named original ToolSandbox tool with downstream_tool_kwargs "
            "unchanged before giving the final answer. "
            "Do not call it before the original lookup/result tool has returned, "
            "on unrelated tasks, or when required fields are absent."
            f"{phone_subject_instruction}"
            f"{temperature_subject_instruction}"
            f"{scalar_instruction}"
        ),
    }


def _service_extractor_scalar_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    extractor_names = {
        "extract_service_answer_field",
        "extract_address_result",
        "extract_converted_amount_result",
        "extract_distance_result",
        "extract_temperature_result",
    }
    available_extractors = extractor_names & _tool_names_execution_facing(openai_tools)
    if not available_extractors:
        return None
    if any(
        _message_already_called_tool(openai_messages, name)
        for name in available_extractors
    ):
        return None
    instruction = _service_extractor_scalar_actor_instruction(
        openai_messages,
        openai_tools,
        available_extractors,
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
            "calling resolve_search_window_or_bounds for an upcoming reminder, "
            "pass phrase='upcoming', target_domain='reminder', "
            "timestamp_intent='reminder', and direction='upcoming'. Never pass "
            "direction='latest' or timestamp_intent='creation' for a request "
            "whose visible target is an upcoming due reminder. If "
            "select_action_target_by_recency is called for an upcoming target, pass "
            "selection_mode='upcoming', timestamp_key='reminder_timestamp', and "
            "reference_timestamp from get_current_timestamp. "
            "If that search returns multiple records and a visible-record selector "
            "helper is also available, call the selector before answering; do not "
            "manually pick the first returned record when the user asked for latest "
            "or oldest. For latest message content questions, get the current "
            "timestamp first when needed, search messages up to that timestamp, "
            "then call the generated message-content selector with the non-empty "
            "records. For oldest message content questions with no other user "
            "filters, do not invent a timestamp bound; call search_messages with "
            "empty arguments to gather the visible message records, then call the "
            "generated message-content selector with selection_mode='oldest'. Do "
            "not pass selection_mode, timestamp_key, or records to original "
            "search_messages; those are generated-selector arguments only. Do "
            "not call a selector with [] after a failed or empty search. Do not call "
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
    creation_request = _relative_reminder_creation_request(openai_messages)
    if (
        creation_request is not None
        and not str(creation_request.get("content") or "").strip()
    ):
        return {
            "role": "system",
            "content": (
                f"{RELATIVE_TIME_ACTOR_POLICY_SENTINEL} The visible reminder "
                "creation request includes a relative day and time but no reminder "
                "content. Ask the user what the reminder should say before calling "
                "a timestamp tool, generated reminder tool, or add_reminder. Do not "
                "use the scheduling phrase itself as reminder content."
            ),
        }
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
    creation_request = _weekday_reminder_creation_request(openai_messages)
    if (
        creation_request is not None
        and not str(creation_request.get("content") or "").strip()
    ):
        return {
            "role": "system",
            "content": (
                f"{SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL} The visible reminder "
                "creation request includes a weekday and time but no reminder "
                "content. Ask the user what the reminder should say before calling "
                "a scheduling tool, generated reminder tool, or add_reminder. Do not "
                "use the scheduling phrase itself as reminder content."
            ),
        }
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
        structured_contract = any(
            {"target_service", "desired_on"}.issubset(
                _tool_input_names_execution_facing(openai_tools, helper_name)
            )
            for helper_name in helpers
        )
        contract_guidance = (
            "Match the generated tool's current structured schema. Pass "
            "target_service and desired_on from the visible user request. If the "
            "schema includes low_battery_blocks_enable and the quoted error says "
            "low battery mode blocks enabling the requested service, pass "
            "low_battery_blocks_enable=true; do not repeat a prior false value "
            "that contradicts the visible error. Set resume_original_task only "
            "from whether a downstream user task remains, and include only "
            "additional service requirements stated in visible evidence. Do not "
            "invent blockers or pass retired fields that are absent from the "
            "current schema. "
            if structured_contract
            else (
                "Use the same user_request used for the prior device-state tool "
                "call and include the exact quoted error in "
                "visible_state_or_error. Include any already-visible successful "
                "setting state in visible_state_or_error or "
                "visible_state_summary. "
            )
        )
        return {
            "role": "system",
            "content": (
                f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} The latest original "
                "ToolSandbox state/action tool returned this precondition error: "
                f"{latest_precondition_error_text!r}. Call the generated "
                f"device-state helper again now: {helper_list}. The next assistant "
                "message must be a tool call to that generated helper before any "
                f"other status getter or setter. {contract_guidance}For example, "
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
        " Prefer the plan_device_state_action_sequence helper when it is visible "
        "because it can return an ordered sequence for low-battery/service "
        "prerequisites."
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
            "location precondition, call plan_device_state_action_sequence with "
            "structured facts derived from that visible request/result: normalized "
            "target_service, desired_on, whether low_battery_blocks_enable, whether "
            "the original task must resume, and any additional visible service "
            "requirements. For this generated contract, normalize target_service "
            "to wifi, cellular, location, or low_battery. Remove a user-facing "
            "service or mode suffix rather than passing location_service, "
            "cellular_service, or low_battery_mode. Apply the same normalization "
            "to additional_services_to_enable. Do not infer blockers that are not "
            "visible. For "
            "next_service_tool_call, pass the single "
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
    sequence = _available_state_sequence_actions(payload, openai_tools)
    if not sequence:
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
    for message in reversed(messages):
        # Tool-choice selection is computed after ephemeral actor guidance has
        # been appended. Those guidance messages should not hide the latest
        # generated tool contract.
        if message.get("role") in {"system", "developer"}:
            continue
        if message.get("role") != "tool":
            return None
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if not name or name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES:
            return None
        payload = _parse_mapping_payload(message.get("content"))
        if not payload:
            return None
        has_available_original_handoff = (
            _downstream_original_tool_from_payload(payload, openai_tools) is not None
        )
        if (
            name not in available_names
            and not has_available_original_handoff
            and not (
                {
                    "final_answer_recommendation",
                    "exact_final_answer",
                    "abstain_reason",
                }
                & set(payload)
            )
        ):
            return None
        return name, payload
    return None


def _latest_generated_tool_abstention_before_latest_user(
    openai_messages: object,
    openai_tools: object,
) -> tuple[str, Mapping[str, Any]] | None:
    """Return the latest generated-tool abstention preceding a user follow-up."""

    generated_names = set(_generated_tool_names_execution_facing(openai_tools))
    if not generated_names:
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest_user_index = _latest_user_index(messages)
    if latest_user_index <= 0:
        return None
    for message in reversed(messages[:latest_user_index]):
        if message.get("role") != "tool":
            continue
        name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if name not in generated_names:
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if not payload:
            return None
        status = str(payload.get("status") or "").strip().lower()
        reason = str(payload.get("abstain_reason") or "").strip()
        return (name, payload) if status == "abstain" or reason else None
    return None


def _generated_tool_abstain_continuation_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Keep an abstaining generated tool available when a user adds information."""

    if _latest_user_is_closing_acknowledgement(openai_messages):
        return None
    latest = _latest_generated_tool_abstention_before_latest_user(
        openai_messages, openai_tools
    )
    if latest is None:
        return None
    tool_name, payload = latest
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if GENERATED_TOOL_ABSTAIN_CONTINUATION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    reason = str(payload.get("abstain_reason") or "missing information").strip()
    visible_name = _tool_name_for_call(openai_tools, tool_name)
    prior_argument_names = sorted(
        _latest_prior_tool_call_arguments(openai_messages, tool_name)
    )
    prior_note = (
        " Preserve the prior values for "
        + ", ".join(prior_argument_names)
        + " unless the latest user message explicitly changes one of them."
        if prior_argument_names
        else " Preserve all still-valid inputs from the previous call."
    )
    return {
        "role": "system",
        "content": (
            f"{GENERATED_TOOL_ABSTAIN_CONTINUATION_POLICY_SENTINEL} The previous "
            f"{visible_name} call abstained because: {reason}. That abstention did "
            "not complete the task. Re-evaluate the same generated tool using the "
            "latest user-supplied information. If the missing input is now visible, "
            f"call {visible_name} again on this ordinary user turn using its exact "
            "schema field names."
            f"{prior_note} Do not claim that a native action succeeded unless the "
            "generated result explicitly returns status success."
        ),
    }


def _helper_output_handoff_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic handoff from structured generated-helper output to the actor."""
    latest = _latest_generated_helper_payload(openai_messages, openai_tools)
    pending_list_instruction = _generated_downstream_list_instruction(
        openai_messages, openai_tools
    )
    if latest is None:
        if pending_list_instruction:
            return {
                "role": "system",
                "content": (
                    f"{HELPER_OUTPUT_HANDOFF_POLICY_SENTINEL}"
                    f"{pending_list_instruction} The generated tool planned "
                    "the side effect, but only the original ToolSandbox tool "
                    "performs it."
                ),
            }
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
    if pending_list_instruction:
        exact_next += pending_list_instruction
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
        location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
        abstain_reason = str(payload.get("abstain_reason") or "").strip()
        abstain_lower = abstain_reason.lower()
        if (
            "location" in abstain_lower
            or str(payload.get("location_status") or "").strip().lower()
            in {"lookup_pending", "required_missing"}
        ) and location_arg_tool:
            location_tool_name = _tool_name_for_call(openai_tools, location_arg_tool)
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
    elif helper_name in {
        "prepare_broad_location_search_args",
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
    }:
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
            location_tool_name = _tool_name_for_call(openai_tools, helper_name)
            previous_args = _latest_prior_tool_call_arguments(
                openai_messages, helper_name
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
            "task. If this is a reminder-creation request and the original "
            "location search returns coordinates, keep going in the same task: "
            "use the visible or generated reminder timestamp and the returned "
            "coordinates to call the preserved original add_reminder tool. Do not "
            "stop after location lookup when the user asked to create a reminder."
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
    if _generated_tool_uses_native_action(
        openai_tools, "prepare_reminder_creation_args"
    ):
        return None
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
    native_finalizer = _generated_tool_uses_native_action(
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
    continuation = (
        "After that result is visible, call the generated relative-time tool, then "
        "call the generated reminder finalizer with normalized content, the generated "
        "reminder_timestamp, and explicit location-state fields. A successful "
        "finalizer result means add_reminder has already executed."
        if native_finalizer
        else (
            "After that result is visible, call the generated reminder-preparation "
            f"tool with these scalar arguments plus current_datetime_info from the "
            f"tool result: {json.dumps(args, sort_keys=True)}. This generated tool "
            "prepares arguments only; original add_reminder must still run when it "
            "returns should_call_add_reminder=true."
        )
    )
    return {
        "role": "system",
        "content": (
            f"{REMINDER_CURRENT_DATETIME_POLICY_SENTINEL} This reminder task uses "
            "a relative local date/time such as tomorrow, next week, or a weekday, "
            "and get_current_timestamp has already returned the visible current "
            "timestamp. Call original timestamp_to_datetime_info on that exact "
            f"current timestamp next. {continuation}"
        ),
    }


def _reminder_location_batch_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Keep relative reminder-location workflows in fair, low-turn tool order."""

    available_names = _tool_names_execution_facing(openai_tools)
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    if not location_arg_tool:
        return None
    common_required = {
        location_arg_tool,
        "search_location_around_lat_lon",
        "get_current_timestamp",
        "timestamp_to_datetime_info",
        "add_reminder",
    }
    has_composite_reminder_tool = "prepare_reminder_creation_args" in available_names
    has_relative_time_tool = "relative_day_time_to_timestamp" in available_names
    native_composite_reminder_tool = (
        has_composite_reminder_tool
        and _generated_tool_uses_native_action(
            openai_tools, "prepare_reminder_creation_args"
        )
    )
    if not (common_required <= available_names):
        return None
    if not (has_composite_reminder_tool or has_relative_time_tool):
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    request = _relative_reminder_creation_request(openai_messages)
    parts = _reminder_location_parts(openai_messages)
    if request is None or parts is None:
        return None

    def emitted(stage: str) -> bool:
        marker = f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} {stage}"
        return any(
            marker in str(message.get("content", ""))
            for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        )

    def policy(stage: str, content: str) -> dict[str, str] | None:
        marker = f"{REMINDER_LOCATION_BATCH_POLICY_SENTINEL} {stage}"
        if emitted(stage):
            return None
        return {"role": "system", "content": f"{marker} {content}"}

    current_timestamp = _latest_current_timestamp(openai_messages)
    current_info = (
        _timestamp_to_datetime_info_for_timestamp(openai_messages, current_timestamp)
        if current_timestamp is not None
        else None
    )
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
    latest_search = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    location_tool_name = _tool_name_for_call(openai_tools, location_arg_tool)
    reminder_tool_name = (
        _tool_name_for_call(openai_tools, "prepare_reminder_creation_args")
        if has_composite_reminder_tool
        else ""
    )
    relative_tool_name = (
        _tool_name_for_call(openai_tools, "relative_day_time_to_timestamp")
        if has_relative_time_tool
        else ""
    )
    add_tool_name = _tool_name_for_call(openai_tools, "add_reminder")
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
            return policy(
                "setup",
                (
                    "This relative "
                    "reminder request includes a visible place phrase. To avoid "
                    "extra turns, batch independent setup now: call original "
                    f"{timestamp_tool_name} with no arguments and generated "
                    f"{location_tool_name} with "
                    f"{json.dumps(location_args, sort_keys=True)} in the same "
                    "assistant turn. Do not call prepare_reminder_creation_args "
                    "until the current datetime context and visible location-search "
                    "coordinates are available."
                ),
            )
        if current_info is None:
            return policy(
                "datetime-plus-location",
                (
                    "Current timestamp "
                    "is visible and the location phrase is independent. Batch the "
                    f"next setup calls: original {datetime_tool_name} with "
                    f"timestamp={current_timestamp} and generated {location_tool_name} "
                    f"with {json.dumps(location_args, sort_keys=True)}. Do not pass "
                    "the current timestamp as resolved_reminder_timestamp."
                ),
            )
        return policy(
            "location-args",
            (
                "The relative-time context is visible. Call generated "
                f"{location_tool_name} with "
                f"{json.dumps(location_args, sort_keys=True)} before the generated "
                "reminder timestamp or argument-preparation tool, then call the "
                "returned original location-search tool with downstream_tool_kwargs "
                f"unchanged. If a later original {add_tool_name} call is needed, keep "
                "the reminder content separate from the place/address and pass "
                "location via latitude and longitude."
            ),
        )

    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages,
        location_arg_tool,
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
            return policy(
                "search-plus-datetime",
                (
                    "A generated "
                    "location-search tool has prepared the original search kwargs. "
                    "Batch the independent next calls: original "
                    f"{datetime_tool_name} with timestamp={current_timestamp} and "
                    f"original {search_tool_name} with "
                    f"{json.dumps(cleaned_kwargs, sort_keys=True)}. Use the returned "
                    "datetime dict and returned coordinates in the generated "
                    "reminder-preparation tool. Do not pass current_timestamp as a "
                    "resolved reminder timestamp."
                ),
            )
        return policy(
            "search",
            (
                "Call original "
                f"{search_tool_name} with the generated downstream kwargs "
                f"{json.dumps(cleaned_kwargs, sort_keys=True)} before calling "
                "prepare_reminder_creation_args. Preserve the returned record's "
                f"latitude and longitude for the later {add_tool_name} call; do not "
                "put the address into reminder content."
            ),
        )

    if current_timestamp is not None and current_info is None:
        return policy(
            "datetime-after-search",
            (
                "Location-search evidence "
                "is visible, but the current timestamp still needs local datetime "
                f"context. Call original {datetime_tool_name} with "
                f"timestamp={current_timestamp}; then call generated "
                "prepare_reminder_creation_args with current_datetime_info and the "
                "visible location coordinates."
            ),
        )
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
    if native_composite_reminder_tool:
        relative_timestamp = _latest_tool_float_by_name_including_latest(
            openai_messages,
            "relative_day_time_to_timestamp",
        )
        if relative_timestamp is None:
            relative_args = {
                "current_timestamp": current_timestamp,
                "day_offset": int(request["day_offset"]),
                "hour": int(request["hour"]),
                "minute": int(request["minute"]),
                "current_datetime_info": current_info,
            }
            return policy(
                "relative-timestamp",
                (
                    f"Call generated {relative_tool_name} with exactly these "
                    f"arguments: {json.dumps(relative_args, sort_keys=True)}."
                ),
            )
        finalizer_args = {
            "content": str(
                parts.get("content") or request.get("content") or ""
            ).strip(),
            "reminder_timestamp": relative_timestamp,
            "location_requested": True,
            "location_required": True,
            "location_available": True,
            "latitude": latitude,
            "longitude": longitude,
            "location_lookup_failed": False,
        }
        return policy(
            "native-finalizer",
            (
                f"Call generated {reminder_tool_name} with exactly these normalized "
                f"arguments: {json.dumps(finalizer_args, sort_keys=True)}. If it "
                "returns status='success', the native add_reminder action is complete; "
                "do not call add_reminder again."
            ),
        )
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
    if not has_composite_reminder_tool and has_relative_time_tool:
        relative_timestamp = _latest_tool_float_by_name_including_latest(
            openai_messages,
            "relative_day_time_to_timestamp",
        )
        clean_content = str(
            parts.get("content") or request.get("content") or ""
        ).strip()
        add_reminder_args = {
            "content": clean_content,
            "reminder_timestamp": relative_timestamp,
            "latitude": latitude,
            "longitude": longitude,
        }
        if relative_timestamp is not None:
            return policy(
                "final-add-reminder",
                (
                    "The generated relative-time timestamp and selected location "
                    f"coordinates are visible. Call original {add_tool_name} now with "
                    "exactly these arguments: "
                    f"{json.dumps(add_reminder_args, sort_keys=True)}. Do not "
                    "append the place name, address, or search result text to "
                    "content; the latitude and longitude arguments carry the "
                    "location."
                ),
            )
        relative_args = {
            "current_timestamp": current_timestamp,
            "day_offset": int(request["day_offset"]),
            "hour": int(request["hour"]),
            "minute": int(request["minute"]),
            "current_datetime_info": current_info,
        }
        return policy(
            "relative-timestamp",
            (
                "The generated location "
                "search and current datetime context are both visible. Call generated "
                f"{relative_tool_name} with exactly these arguments: "
                f"{json.dumps(relative_args, sort_keys=True)}. Use the generated "
                f"timestamp as reminder_timestamp when calling original {add_tool_name} "
                f"with content={json.dumps(str(parts.get('content') or request.get('content') or '').strip())}, "
                f"latitude={latitude}, and longitude={longitude}. Do not use "
                "manual calendar arithmetic or a hard-coded timestamp. When "
                f"calling {add_tool_name}, keep content as only the reminder text; "
                "pass location through latitude and longitude."
            ),
        )
    return policy(
        "composite-reminder",
        (
            "The generated location "
            "search and current datetime context are both visible. Call generated "
            f"{reminder_tool_name} with exactly these arguments: "
            f"{json.dumps(reminder_args, sort_keys=True)}. If it returns "
            f"should_call_add_reminder=true, call original {add_tool_name} next with "
            "add_reminder_kwargs unchanged."
        ),
    )


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
    phone_followup = _latest_user_is_phone_answer_retention_followup(openai_messages)
    if not retention_followup and not status_followup and not phone_followup:
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
            "don't share",
            "do not share",
            "not share",
            "keep it private",
            "keep that private",
            "private info",
            "private information",
            "confidential",
        )
    ):
        return {
            "role": "system",
            "content": (
                f"{ANSWER_RETENTION_ACTOR_POLICY_SENTINEL} A generated tool already "
                "supported the prior tool-backed answer. The user follow-up does "
                "not introduce a new task; preserve the generated-tool answer as "
                f"the final task answer. Answer exactly with: {answer} Do not call "
                "another lookup, do not add a privacy acknowledgement, and do not "
                "change the wording."
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


def _latest_user_requests_new_tool_action(openai_messages: object) -> bool:
    """Return whether the newest user turn is an actionable request, not closure."""

    latest_user = (
        _latest_user_request_text(openai_messages)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
    )
    if not latest_user or _latest_user_is_closing_acknowledgement(openai_messages):
        return False
    if _relationship_batch_request(openai_messages) is not None:
        return True
    action_verbs = (
        "add",
        "change",
        "delete",
        "disable",
        "enable",
        "find",
        "look up",
        "lookup",
        "message",
        "modify",
        "remove",
        "search",
        "send",
        "set",
        "switch",
        "tell",
        "text",
        "turn",
        "update",
    )
    action_domains = (
        "alarm",
        "battery",
        "cellular",
        "contact",
        "contacts",
        "email",
        "location",
        "message",
        "messages",
        "phone",
        "reminder",
        "reminders",
        "service",
        "wifi",
        "wi-fi",
    )
    if any(verb in latest_user for verb in action_verbs) and any(
        domain in latest_user for domain in action_domains
    ):
        return True
    return bool(
        re.search(
            r"\b(?:send|text|message|tell|ask)\s+(?:a\s+)?(?:message\s+)?"
            r"(?:to\s+)?[A-Z+a-z0-9]",
            _latest_user_request_text(openai_messages),
        )
    )


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
    if (
        not _latest_user_is_closing_acknowledgement(openai_messages)
        and _latest_generated_tool_abstention_before_latest_user(
            openai_messages, openai_tools
        )
        is not None
    ):
        return None
    if _latest_user_requests_new_tool_action(openai_messages):
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
        or _latest_user_is_privacy_retention_followup(openai_messages)
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
        or _latest_user_is_privacy_retention_followup(openai_messages)
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


def _message_contact_lookup_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve generated named-recipient message planning after original send."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_send_message_contact_lookup" not in available_names:
        return None
    if not _message_already_called_tool(
        openai_messages, "plan_send_message_contact_lookup"
    ):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if MESSAGE_CONTACT_LOOKUP_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    latest_content = str(latest.get("content", "") or "").strip().lower()
    if latest.get("role") != "tool" or latest_name != "send_message_with_phone_number":
        return None
    if any(token in latest_content for token in ("error", "exception", "invalid")):
        return None

    send_args = _latest_successful_send_message_tool_call(openai_messages)
    if send_args is None:
        return None
    planner_args = _latest_prior_tool_call_arguments(
        openai_messages, "plan_send_message_contact_lookup"
    )
    phone = str(send_args.get("phone_number") or "").strip()
    recipient = str(planner_args.get("recipient_name") or "").strip()
    if not recipient:
        recipient = _contact_name_for_phone_from_latest_search(openai_messages, phone)
    if not recipient:
        recipient = phone or "the recipient"
    content = str(send_args.get("content") or "").strip()
    if not content:
        content = str(planner_args.get("message_content") or "").strip()
    if not content:
        return None
    confirmation = f"Your message to {recipient} has been sent saying: {content}"
    return {
        "role": "system",
        "content": (
            f"{MESSAGE_CONTACT_LOOKUP_COMPLETION_POLICY_SENTINEL} The generated "
            "plan_send_message_contact_lookup tool identified the named-recipient "
            "message plan, and original send_message_with_phone_number has now "
            "succeeded. Give the concise completion confirmation grounded only "
            f"in those visible generated-tool and original-tool results: "
            f"{confirmation} Do not mention generated tools, do not add the "
            "phone number unless it is the only visible recipient identifier, "
            "do not add greetings or offers for more help, and do not call "
            "another tool unless the user asks for a new task."
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
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    if not location_arg_tool:
        return None
    if not ({location_arg_tool, "search_location_around_lat_lon"} <= available_names):
        return None
    latest_setting = _latest_tool_message_index(
        openai_messages, SETTING_SETTER_TOOL_NAMES
    )
    latest_search = _latest_tool_message_index(
        openai_messages, {"search_location_around_lat_lon"}
    )
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
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
        openai_messages,
        location_arg_tool,
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
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    if not location_arg_tool:
        return None
    if not ({location_arg_tool, "search_location_around_lat_lon"} <= available_names):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if LOCATION_SEARCH_RETRY_AFTER_COORDINATES_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
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
        openai_messages,
        location_arg_tool,
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
        openai_tools,
        location_arg_tool,
    )
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    previous_args = _latest_prior_tool_call_arguments(
        openai_messages, location_arg_tool
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
    location_tool_name = _tool_name_for_call(openai_tools, location_arg_tool)
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
    location_arg_tool = _location_search_arg_tool_execution_name(openai_tools)
    if not location_arg_tool:
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if LOCATION_SEARCH_ARGUMENT_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    latest_prepare = _latest_tool_message_index(openai_messages, {location_arg_tool})
    if latest_prepare is not None:
        payload = _latest_tool_payload_by_name_including_latest(
            openai_messages,
            location_arg_tool,
        )
        if (
            str(payload.get("abstain_reason") or "").strip()
            == "missing_reminder_time_before_location_lookup"
        ):
            messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
            later_user_text = " ".join(
                str(message.get("content") or "")
                for message in messages[latest_prepare[0] + 1 :]
                if message.get("role") == "user"
            ).strip()
            has_later_time = bool(later_user_text) and (
                _relative_reminder_creation_request(openai_messages) is not None
                or bool(
                    re.search(
                        r"\b(?:today|tomorrow|tonight|next week|next "
                        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
                        r"|\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?))\b",
                        later_user_text,
                        flags=re.IGNORECASE,
                    )
                )
            )
            latest_search = _latest_tool_message_index(
                openai_messages,
                {"search_location_around_lat_lon"},
            )
            search_after_prepare = (
                latest_search is not None and latest_search[0] > latest_prepare[0]
            )
            if has_later_time and not search_after_prepare:
                previous_args = _latest_prior_tool_call_arguments(
                    openai_messages,
                    location_arg_tool,
                )
                location_phrase = (
                    _visible_location_phrase_from_user_request(openai_messages)
                    or str(previous_args.get("location_phrase") or "").strip()
                )
                arguments = {
                    "user_request": " ".join(_all_user_texts(openai_messages)).strip(),
                    "location_phrase": location_phrase,
                }
                input_names = _tool_input_names_execution_facing(
                    openai_tools,
                    location_arg_tool,
                )
                if "latitude" in input_names and "latitude" in previous_args:
                    arguments["latitude"] = previous_args["latitude"]
                if "longitude" in input_names and "longitude" in previous_args:
                    arguments["longitude"] = previous_args["longitude"]
                location_tool_name = _tool_name_for_call(
                    openai_tools,
                    location_arg_tool,
                )
                return {
                    "role": "system",
                    "content": (
                        f"{LOCATION_SEARCH_ARGUMENT_POLICY_SENTINEL} The generated "
                        "location-search argument tool previously abstained because "
                        "the reminder time was missing. A later visible user turn has "
                        "now supplied reminder time information, so continue the "
                        "generated-tool workflow before any add_reminder call. Call "
                        f"generated {location_tool_name} with exactly these arguments: "
                        f"{json.dumps(arguments, sort_keys=True)}. Then call the "
                        "original location-search tool returned in downstream_tool_name "
                        "with downstream_tool_kwargs unchanged. Use only visible "
                        "coordinates returned by that original search when creating "
                        "the reminder."
                    ),
                }
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower = f" {all_user_text.lower()} "
    if not any(token in lower for token in (" reminder", " remind ", " todo ")):
        return None
    if not any(
        marker in lower for marker in (" at ", " near ", " around ", " in ", " by ")
    ):
        return None
    location_tool_name = _tool_name_for_call(openai_tools, location_arg_tool)
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
        " i can't",
        " i cannot",
        " in celsius",
        " in fahrenheit",
        " as celsius",
        " as fahrenheit",
        " to celsius",
        " to fahrenheit",
        " celsius",
        " fahrenheit",
        " °c",
        " °f",
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
        weather_match = re.search(
            r"\b(?:current\s+)?(?:temp|temperature|weather|forecast)\s+"
            r"(?!in\b|at\b|near\b|around\b|for\b)([^,.!?;]+)",
            raw,
            flags=re.IGNORECASE,
        )
        if weather_match:
            phrase = _strip_temporal_tail_from_location_phrase(weather_match.group(1))
            if phrase and not _looks_like_time_only_location_phrase(phrase):
                return phrase
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


def _reminder_missing_time_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Ask for missing reminder time instead of inventing a timestamp."""

    available_names = _tool_names_execution_facing(openai_tools)
    generated_reminder_tools = {
        "relative_day_time_to_timestamp",
        "next_weekday_time_to_timestamp",
        "prepare_reminder_creation_args",
        "prepare_broad_location_search_args",
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
    } & available_names
    if not generated_reminder_tools or "add_reminder" not in available_names:
        return None
    if _message_already_called_tool(openai_messages, "add_reminder"):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if REMINDER_MISSING_TIME_POLICY_SENTINEL in str(message.get("content", "")):
            return None

    conversation_user_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
        if message.get("role") == "user"
    ).strip()
    conversation_lower = conversation_user_text.lower()
    if not any(
        token in conversation_lower
        for token in ("remind", "reminder", "todo", "to-do", "to do")
    ):
        return None
    has_clock_time = bool(
        re.search(
            r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b",
            conversation_lower,
        )
    )
    has_date_or_relative_time = any(
        token in conversation_lower
        for token in (
            "today",
            "tomorrow",
            "tonight",
            "yesterday",
            "next ",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "week",
            "day",
        )
    ) or bool(
        re.search(
            r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
            conversation_lower,
        )
    )
    if has_clock_time or has_date_or_relative_time:
        return None

    add_tool = _tool_name_for_call(openai_tools, "add_reminder")
    return {
        "role": "system",
        "content": (
            f"{REMINDER_MISSING_TIME_POLICY_SENTINEL} A generated reminder "
            "timestamp or argument-preparation tool is visible, but the visible "
            "user request does not contain a reminder date or time. Do not call "
            f"original {add_tool} with current_timestamp, midnight, noon, or any "
            "placeholder reminder_timestamp. Ask the user for the missing "
            "reminder date/time. After the user supplies it, use the generated "
            "timestamp or argument tool whose schema matches that visible time "
            "phrase."
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


def _message_counterparty_direction_from_request(openai_messages: object) -> str:
    request = " ".join(
        _latest_user_request_text(openai_messages).lower().replace("’", "'").split()
    )
    if not request or "message" not in request:
        return ""
    received_patterns = (
        r"\b(sent|messaged|texted)\s+me\b",
        r"\b(i|i've|i have)\s+(received|got)\b",
        r"\bfrom\s+the\s+(last|latest|most recent|first|oldest)\b",
        r"\bperson\s+who\s+(sent|messaged|texted)\s+me\b",
    )
    if any(re.search(pattern, request) for pattern in received_patterns):
        return "received"
    sent_patterns = (
        r"\b(i|i've|i have)\s+sent\b",
        r"\blast\s+person\s+i\s+sent\b",
        r"\blatest\s+person\s+i\s+sent\b",
        r"\bmost\s+recent\s+person\s+i\s+sent\b",
        r"\bperson\s+i\s+(sent|messaged|texted)\b",
    )
    if any(re.search(pattern, request) for pattern in sent_patterns):
        return "sent"
    return ""


def _message_counterparty_selection_mode_from_request(openai_messages: object) -> str:
    request = " ".join(
        _latest_user_request_text(openai_messages).lower().replace("’", "'").split()
    )
    if any(token in request for token in ("oldest", "first", "earliest")):
        return "oldest"
    return "latest"


def _message_counterparty_selector_setup_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Set up public original calls needed before a generated counterparty selector."""
    available_names = _tool_names_execution_facing(openai_tools)
    if "select_message_counterparty_for_contact_update" not in available_names:
        return None
    if _message_already_called_tool(
        openai_messages, "select_message_counterparty_for_contact_update"
    ):
        return None
    direction = _message_counterparty_direction_from_request(openai_messages)
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if MESSAGE_COUNTERPARTY_SELECTOR_SETUP_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    selection_mode = _message_counterparty_selection_mode_from_request(openai_messages)
    self_person_id = _latest_self_person_id_from_contacts(openai_messages)
    if not self_person_id:
        if "search_contacts" not in available_names:
            return None
        return {
            "role": "system",
            "content": (
                f"{MESSAGE_COUNTERPARTY_SELECTOR_SETUP_POLICY_SENTINEL} A "
                "generated message-counterparty selector is visible for this "
                "contact update. The selector needs the current user's concrete "
                "self_person_id before message records can be selected. Do not "
                "pass sender_person_id='self' or recipient_person_id='self' to "
                "search_messages. First call the original search_contacts tool "
                "with is_self=true, then use the visible person_id from that "
                "result for the next original search_messages call."
            ),
        }

    latest_contacts = _latest_tool_message_index(openai_messages, {"search_contacts"})
    latest_messages = _latest_tool_message_index(openai_messages, {"search_messages"})
    messages_after_self_lookup = (
        latest_contacts is not None
        and latest_messages is not None
        and latest_messages[0] > latest_contacts[0]
    )
    if not messages_after_self_lookup:
        if "search_messages" not in available_names:
            return None
        if direction:
            id_field = (
                "sender_person_id" if direction == "sent" else "recipient_person_id"
            )
            search_instruction = (
                "Now call the original search_messages tool with "
                f"{id_field}={self_person_id!r}."
            )
        else:
            search_instruction = (
                "Now call the original search_messages tool without sender or "
                "recipient filters so the generated selector can identify the "
                "non-self counterparty from complete visible records."
            )
        return {
            "role": "system",
            "content": (
                f"{MESSAGE_COUNTERPARTY_SELECTOR_SETUP_POLICY_SENTINEL} The "
                "original search_contacts result exposes the current user's "
                f"person_id as {self_person_id!r}. {search_instruction} Do "
                "not add a content or contact-name filter unless the user made "
                "that filter part of the task. After search_messages returns "
                "visible records, call select_message_counterparty_for_contact_update "
                f"with records from that result, selection_mode={selection_mode!r}, "
                "the explicit update fields from the user request, and "
                f"self_person_id={self_person_id!r}."
            ),
        }

    if not _messages_show_prior_candidate_records(openai_messages):
        return None
    phone = _phone_update_from_user_request(openai_messages)
    update_note = (
        f"updates={{'phone_number': {phone!r}}}"
        if phone
        else "updates containing only fields explicitly requested by the user"
    )
    return {
        "role": "system",
        "content": (
            f"{MESSAGE_COUNTERPARTY_SELECTOR_SETUP_POLICY_SENTINEL} The latest "
            "original search_messages result contains visible message records, "
            "and a generated selector is available for choosing the safe contact "
            "update target. Call select_message_counterparty_for_contact_update "
            f"now with those records, selection_mode={selection_mode!r}, "
            f"{update_note}, and self_person_id={self_person_id!r}. Do not "
            "call modify_contact before the generated selector returns "
            "downstream_tool_kwargs."
        ),
    }


def _message_counterparty_update_completion_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Preserve visible update values after generated counterparty selection."""
    if (
        "select_message_counterparty_for_contact_update"
        not in _tool_names_execution_facing(openai_tools)
    ):
        return None
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    for message in messages:
        if MESSAGE_COUNTERPARTY_UPDATE_COMPLETION_POLICY_SENTINEL in str(
            message.get("content", "")
        ):
            return None
    latest = messages[-1]
    latest_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if latest.get("role") != "tool" or latest_name != "modify_contact":
        return None
    latest_content = str(latest.get("content", "") or "").strip().lower()
    if any(token in latest_content for token in ("error", "exception", "invalid")):
        return None
    selector_payload = _latest_tool_payload_by_name(
        openai_messages,
        "select_message_counterparty_for_contact_update",
    )
    if not selector_payload:
        return None
    downstream_tool = str(selector_payload.get("downstream_tool_name") or "").strip()
    if downstream_tool and downstream_tool != "modify_contact":
        return None
    successful = _latest_successful_crud_tool_call(openai_messages)
    if successful is None:
        return None
    tool_name, arguments = successful
    if tool_name != "modify_contact":
        return None
    phone = str(arguments.get("phone_number") or "").strip()
    if not phone:
        downstream_kwargs = selector_payload.get("downstream_tool_kwargs")
        if isinstance(downstream_kwargs, Mapping):
            phone = str(downstream_kwargs.get("phone_number") or "").strip()
    if not phone:
        phone = _phone_update_from_user_request(openai_messages)
    if not phone:
        return None
    direction = _message_counterparty_direction_from_request(openai_messages)
    if direction == "received":
        subject = "the person who last sent you a message"
    elif direction == "sent":
        subject = "the last person you sent a message to"
    else:
        subject = "the contact selected from the latest visible message"
    confirmation = f"The phone number of {subject} has been updated to {phone}."
    return {
        "role": "system",
        "content": (
            f"{MESSAGE_COUNTERPARTY_UPDATE_COMPLETION_POLICY_SENTINEL} The "
            "generated message-counterparty selector prepared the modify_contact "
            "arguments, and original modify_contact has now succeeded. Give a "
            "concise completion confirmation grounded only in the visible user "
            f"request and tool results: {confirmation} Include the updated phone "
            "number exactly. Do not mention generated tools, add unrelated "
            "fields, greetings, or offers for more help."
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
        if (
            _tool_input_names_execution_facing(openai_tools, tool_name)
            & {"messages", "records"}
        )
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
    input_names = _tool_input_names_execution_facing(openai_tools, tool_name)
    record_argument = "messages" if "messages" in input_names else "records"
    prior_args = _latest_prior_tool_call_arguments(openai_messages, tool_name)
    prior_args.pop("messages", None)
    prior_args.pop("records", None)
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
            f"{visible_tool_name} with its {record_argument} argument set to the entire "
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
    request = _reminder_recency_request(openai_messages)
    modify_request = request in {"modify_latest", "modify_upcoming"}
    remove_request = request in {"remove_latest", "remove_upcoming"}
    if not (modify_request or remove_request):
        return None
    if modify_request and not (
        {"relative_day_time_to_timestamp", "modify_reminder"} <= available_names
    ):
        return None
    if remove_request and "remove_reminder" not in available_names:
        return None
    if not _latest_tool_is(openai_messages, "search_reminder"):
        return None
    if _message_already_called_tool(
        openai_messages, "select_record_by_timestamp_extreme"
    ) or _message_already_called_tool(
        openai_messages, "select_action_target_by_recency"
    ):
        return None
    if modify_request and _tomorrow_time_request(openai_messages) is None:
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
    selection_mode = (
        "oldest" if request in {"modify_upcoming", "remove_upcoming"} else "latest"
    )
    timestamp_key = (
        "reminder_timestamp"
        if request in {"modify_upcoming", "remove_upcoming"}
        else "creation_timestamp"
    )
    native_action_selector = (
        selector_name == "select_action_target_by_recency"
        and _generated_tool_uses_native_action(openai_tools, selector_name)
    )
    resolved_timestamp = _timestamp_from_latest_tool(
        openai_messages, "relative_day_time_to_timestamp"
    )
    if remove_request and native_action_selector:
        selector_instruction = (
            "Call select_action_target_by_recency now with the records from the "
            "latest search_reminder result, "
            f"timestamp_key='{timestamp_key}', selection_mode='{selection_mode}', "
            "action_type='remove_reminder', constraints={}, and updates={}."
        )
        continuation_instruction = (
            "This generated tool delegates the validated native removal. If it "
            "returns status='success', the state change is complete; do not call "
            "remove_reminder again."
        )
    elif remove_request:
        selector_instruction = (
            f"Call {selector_name} now with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', and "
            f"selection_mode='{selection_mode}'."
        )
        continuation_instruction = (
            "After the generated selector returns one reminder_id, call the "
            "original remove_reminder exactly once with that visible identifier."
        )
    elif selector_name == "select_record_by_timestamp_extreme":
        selector_instruction = (
            "Call select_record_by_timestamp_extreme with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', and "
            f"selection_mode='{selection_mode}'."
        )
        continuation_instruction = (
            "After the generated selector returns one reminder_id, make sure "
            "timestamp_to_datetime_info has been called on the visible current "
            "timestamp. Then call relative_day_time_to_timestamp for the requested "
            "new time with the returned dict as current_datetime_info, and call "
            "the original modify_reminder with that selected reminder_id and the "
            "generated timestamp."
        )
    elif native_action_selector and resolved_timestamp is not None:
        selector_instruction = (
            "Call select_action_target_by_recency with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', "
            f"selection_mode='{selection_mode}', action_type='modify_reminder', "
            "constraints={}, and updates="
            f"{json.dumps({'reminder_timestamp': resolved_timestamp}, sort_keys=True)}."
        )
        continuation_instruction = (
            "This generated tool delegates the validated native modification. If it "
            "returns status='success', the state change is complete; do not call "
            "modify_reminder again."
        )
    elif native_action_selector:
        selector_instruction = (
            "First obtain the requested timestamp with the visible generated "
            "relative-time tool and its required original datetime producer. Then "
            "call select_action_target_by_recency with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', "
            f"selection_mode='{selection_mode}', action_type='modify_reminder', "
            "constraints={}, and updates containing that concrete "
            "reminder_timestamp."
        )
        continuation_instruction = (
            "If the generated action tool returns status='success', the delegated "
            "native state change is complete; do not call modify_reminder again."
        )
    else:
        selector_instruction = (
            "Call select_action_target_by_recency with the records from the latest "
            f"search_reminder result, timestamp_key='{timestamp_key}', "
            f"selection_mode='{selection_mode}', action_type='modify_reminder', "
            "constraints={}, and updates={}."
        )
        continuation_instruction = (
            "After the generated selector returns one reminder_id, make sure "
            "timestamp_to_datetime_info has been called on the visible current "
            "timestamp. Then call relative_day_time_to_timestamp for the requested "
            "new time with the returned dict as current_datetime_info, and call "
            "the original modify_reminder with that selected reminder_id and the "
            "generated timestamp."
        )
    return {
        "role": "system",
        "content": (
            f"{REMINDER_RECENCY_SEARCH_RESULT_POLICY_SENTINEL} The latest "
            "search_reminder result is for a recency-based reminder action. "
            "Use the validated generated selector/action tool before manually "
            "assembling the original state-changing call. "
            f"{selector_instruction} {continuation_instruction}"
        ),
    }


def _with_selector_actor_policy(
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
) -> list[OpenAIMessage]:
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
    else:
        helper_adoption_policies = (
            _service_extractor_scalar_actor_policy_message(
                openai_messages, openai_tools
            ),
            _message_counterparty_search_actor_policy_message(
                openai_messages, openai_tools
            ),
            _message_counterparty_selector_setup_actor_policy_message(
                openai_messages, openai_tools
            ),
            _message_counterparty_update_completion_actor_policy_message(
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
            _reminder_missing_time_actor_policy_message(openai_messages, openai_tools),
            _reminder_location_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_datetime_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
            _reminder_current_datetime_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_relationship_batch_actor_policy_message(
                openai_messages, openai_tools
            ),
            _contact_relationship_batch_result_actor_policy_message(
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
    message_contact_lookup_completion_policy = (
        _message_contact_lookup_completion_actor_policy_message(
            openai_messages, openai_tools
        )
    )
    if message_contact_lookup_completion_policy is not None:
        helper_adoption_policies = (
            message_contact_lookup_completion_policy,
            *helper_adoption_policies,
        )
    native_action_policy = _native_action_tool_actor_policy_message(
        openai_messages, openai_tools
    )
    if native_action_policy is not None:
        helper_adoption_policies = (
            native_action_policy,
            *helper_adoption_policies,
        )
    generic_tail_policies = (
        _lookup_planner_actor_policy_message(openai_messages, openai_tools),
        _selector_actor_policy_message(openai_messages, openai_tools),
        _derived_actor_policy_message(openai_messages, openai_tools),
    )
    policies = [
        policy
        for policy in (
            shared_task_closure_policy,
            helper_retention_policy,
            completion_policy,
            _generated_tool_abstain_continuation_actor_policy_message(
                openai_messages, openai_tools
            ),
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
        f"or says they need nothing else after the task is complete, call "
        f"{end_name}. Do not answer with a social closing sentence when "
        f"{end_name} is available."
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
            "instructions unless the user explicitly requested instructions. "
            "For send-message tasks, if a successful visible "
            "send_message_with_phone_number call includes message content, confirm "
            "the recipient and include that same visible content in the completion "
            "confirmation; do not omit it or replace it with a paraphrase. "
            "For contact-update tasks, if a successful visible modify_contact "
            "call updates a visible person_id, phone number, name, or relationship, "
            "include the visible identifier or contact name and the updated visible "
            "field value in the completion confirmation. "
            f"{close_instruction}"
        ),
    }


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


def _location_search_arg_tool_execution_name(openai_tools: object) -> str:
    available_names = _tool_names_execution_facing(openai_tools)
    for name in (
        "prepare_broad_location_search_args",
        "prepare_specific_location_search_args",
        "prepare_location_search_args",
    ):
        if name in available_names:
            return name
    return ""


def _visible_removal_action_requested(text: str) -> bool:
    normalized = " ".join(text.lower().strip().split())
    return bool(
        re.search(
            r"\b(?:remove|delete|cancel|discard)\b|\bget\s+rid\s+of\b",
            normalized,
        )
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
        reminder_request = "reminder" in lower or "todo" in lower or "to-do" in lower
        remove_request = _visible_removal_action_requested(lower)
        modify_request = bool(
            re.search(r"\b(?:modify|update|postpone|push|move)\b", lower)
        )
        latest_request = bool(
            re.search(r"\b(?:latest|last)\b|\bmost\s+recent\b", lower)
        )
        upcoming_request = bool(re.search(r"\b(?:upcoming|next|soonest)\b", lower))
        if reminder_request and remove_request and latest_request:
            return "remove_latest"
        if reminder_request and remove_request and upcoming_request:
            return "remove_upcoming"
        if reminder_request and modify_request and upcoming_request:
            return "modify_upcoming"
        if reminder_request and modify_request and latest_request:
            return "modify_latest"
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


def _records_from_latest_reminder_search(
    openai_messages: object,
) -> list[Mapping[str, Any]]:
    message = _latest_tool_message(openai_messages, "search_reminder")
    if message is None:
        return []
    payload = _parse_sequence_payload(message.get("content"))
    return [record for record in payload if isinstance(record, Mapping)]


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


SERVICE_ANSWER_PRODUCER_TOOLS = {
    "search_location_around_lat_lon",
    "search_lat_lon",
    "search_weather_around_lat_lon",
    "calculate_lat_lon_distance",
    "convert_currency",
    "unit_conversion",
}
SERVICE_ANSWER_EXTRACTOR_TOOLS = {
    "extract_service_answer_field",
    "extract_address_result",
    "extract_converted_amount_result",
    "extract_phone_number_result",
    "extract_distance_result",
    "extract_temperature_result",
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
    if tool_name == "search_lat_lon":
        return {"result": value}
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
        parsed = _parse_service_payload_value(content)
        if isinstance(parsed, list):
            records = [item for item in parsed if isinstance(item, Mapping)]
            if records and latest_user_requests_location_field:
                return dict(records[0])
        return _coerce_service_answer_payload(
            name,
            parsed,
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


def _direct_ask_tell_request_from_text(text: str) -> dict[str, str] | None:
    stripped = " ".join(text.strip().split())
    match = re.match(r"\b(?:ask|tell)\s+(.+?)\s*$", stripped, flags=re.IGNORECASE)
    if not match:
        return None
    tokens = match.group(1).split()
    if len(tokens) < 2:
        return None
    content_starters = {
        "how",
        "what",
        "when",
        "where",
        "why",
        "who",
        "can",
        "could",
        "would",
        "will",
        "please",
        "that",
        "if",
        "whether",
        "to",
        "about",
        "i",
        "i'm",
        "im",
        "you",
        "we",
    }
    max_name_tokens = min(4, len(tokens) - 1)
    for split_index in range(1, max_name_tokens + 1):
        name_tokens = tokens[:split_index]
        if not all(re.match(r"^[A-Z][A-Za-z.]*$", token) for token in name_tokens):
            continue
        next_token = re.sub(r"[^A-Za-z']", "", tokens[split_index]).lower()
        next_root = next_token.split("'", 1)[0]
        if next_token not in content_starters and next_root not in content_starters:
            continue
        content = " ".join(tokens[split_index:]).strip(" .")
        if content:
            return {
                "recipient_name": " ".join(name_tokens).strip(),
                "message_content": content,
            }
    return None


def _text_is_contact_method_denial(text: str) -> bool:
    lower = text.lower().replace("’", "'").replace("‘", "'")
    if not any(
        token in lower
        for token in (
            "phone",
            "number",
            "contact method",
            "other way",
            "way to contact",
        )
    ):
        return False
    return any(
        token in lower
        for token in (
            "don't have",
            "do not have",
            "don't know",
            "do not know",
            "can't",
            "cannot",
            "no ",
            "not have",
        )
    )


def _visible_named_send_recipient_present(openai_messages: object) -> bool:
    """Return whether visible user text names a send-message recipient."""
    name_pattern = r"([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})"
    for text in _all_user_texts(openai_messages):
        stripped = " ".join(text.strip().split())
        if not stripped or _extract_phone_from_text(stripped):
            continue
        patterns = (
            rf"\b(?i:(?:send|text|message|ask|tell))\s+(?:a\s+)?(?:message\s+)?to\s+{name_pattern}\b",
            r"\b(?:send|text|message|ask|tell)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            rf"\b(?i:(?:send|text|message))\s+(?:it|this|that)\s+to\s+{name_pattern}\b",
            rf"\b(?i:(?:send|text|message))\s+{name_pattern}\b",
            rf"\b(?i:(?:full\s+name|name))\s+is\s+{name_pattern}\b",
            rf"\b(?i:(?:his|her|their))\s+name\s*,\s*{name_pattern}\b",
            rf"\b(?i:know)\s+(?:(?:his|her|their)\s+)?name\s*,?\s*{name_pattern}\b",
            rf"\b(?i:know)\s+{name_pattern}\s+(?:is|as|from|in)\b",
            rf"\b(?i:it(?:'s| is))\s+(?:to|for)\s+{name_pattern}\b",
            rf"\b(?i:it(?:'s| is))\s+{name_pattern}\b",
            r"\b(?:send|text|message|ask|tell)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            rf"\bto\s+{name_pattern}\s*[.?!]?$",
        )
        for pattern in patterns:
            match = re.search(
                pattern, stripped, flags=_recipient_pattern_flags(pattern)
            )
            if match and match.group(1).strip():
                return True
    return False


def _strip_named_recipient_suffix(content: str, recipient: str) -> str:
    """Remove trailing "to <recipient>" when it framed the send target."""
    if not content or not recipient:
        return content.strip()
    pattern = (
        r"(?:[.?!]\s*)?(?:it(?:'s| is)\s+)?(?:to|for)\s+"
        + re.escape(recipient).replace(r"\ ", r"\s+")
        + r"\s*[.?!]*$"
    )
    return re.sub(pattern, "", content.strip(), flags=re.IGNORECASE).strip(" .")


def _recipient_pattern_flags(pattern: str) -> int:
    """Keep visible name spans case-sensitive while allowing scoped verbs."""
    if "?i:" in pattern or "[A-Z]" in pattern:
        return 0
    return re.IGNORECASE


def _send_message_content_from_visible_text(text: str) -> str:
    stripped = " ".join(str(text or "").strip().split())
    if not stripped:
        return ""
    quoted = re.findall(r'"([^"]{1,280})"', stripped)
    if quoted:
        return quoted[-1].strip(" .")
    say_match = re.search(
        r"\b(?:saying|say)\s*:?\s+(.+?)\s*$|\btext\s*:\s+(.+?)\s*$",
        stripped,
        flags=re.IGNORECASE,
    )
    if say_match:
        return (say_match.group(1) or say_match.group(2) or "").strip(" .")
    explicit_message_match = re.search(
        r"\b(?:message|text)\s+(?:is|should\s+be|should\s+say)"
        r"\s*[:,]?\s+(.+?)\s*$",
        stripped,
        flags=re.IGNORECASE,
    )
    if explicit_message_match:
        return explicit_message_match.group(1).strip(" .")
    framed_message_match = re.search(
        r"\b(?:need|want|wanted|would\s+like)\s+to\s+"
        r"(?:send|say|text|message)\s*:?\s+(.+?)\s*$",
        stripped,
        flags=re.IGNORECASE,
    )
    if framed_message_match:
        return framed_message_match.group(1).strip(" .")
    return ""


def _extract_send_message_contact_request(
    openai_messages: object,
) -> dict[str, str] | None:
    """Extract a safe named-recipient send request from visible user text."""
    all_user_texts = _all_user_texts(openai_messages)
    all_user_lower = " ".join(all_user_texts).lower()
    name_pattern = r"([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})"
    recipient_source_index = -1
    recipient_from_context = ""
    for index, text in enumerate(all_user_texts):
        stripped = " ".join(text.strip().split())
        if not stripped:
            continue
        direct_request = _direct_ask_tell_request_from_text(stripped)
        if direct_request is not None:
            recipient_from_context = direct_request["recipient_name"]
            recipient_source_index = index
            continue
        recipient_patterns = (
            rf"\b(?i:(?:send|text|message|ask|tell))\s+(?:a\s+)?(?:message\s+)?to\s+{name_pattern}\b",
            r"\b(?:send|text|message|ask|tell)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            rf"\b(?i:(?:send|text|message))\s+(?:it|this|that)\s+to\s+{name_pattern}\b",
            rf"\b(?i:(?:send|text|message))\s+{name_pattern}\b",
            rf"\b(?i:(?:full\s+name|name))\s+is\s+{name_pattern}\b",
            rf"\b(?i:(?:his|her|their))\s+name\s*,\s*{name_pattern}\b",
            rf"\b(?i:know)\s+(?:(?:his|her|their)\s+)?name\s*,?\s*{name_pattern}\b",
            rf"\b(?i:know)\s+{name_pattern}\s+(?:is|as|from|in)\b",
            rf"\b(?i:it(?:'s| is))\s+(?:to|for)\s+{name_pattern}\b",
            rf"\b(?i:it(?:'s| is))\s+{name_pattern}\b",
            r"\b(?:send|text|message|ask|tell)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bto\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\s+(?:saying|that|with)\b",
            rf"\bto\s+{name_pattern}\s*[.?!]?$",
        )
        for pattern in recipient_patterns:
            match = re.search(
                pattern, stripped, flags=_recipient_pattern_flags(pattern)
            )
            if not match:
                continue
            recipient = match.group(1).strip(" .?!")
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
            and "ask" not in lower
            and "tell" not in lower
            and "want to say" not in lower
        ):
            continue
        if not any(
            token in lower for token in ("send", "text", "message", "ask", "tell")
        ) and not (
            "want to say" in lower
            and any(
                token in all_user_lower
                for token in ("send", "text", "message", "ask", "tell")
            )
        ):
            continue
        if _extract_phone_from_text(stripped):
            continue
        quoted = re.findall(r'"([^"]{1,280})"', stripped)
        content = quoted[-1].strip() if quoted else ""
        if not content:
            say_match = re.search(
                r"\b(?:saying|say)\s*:?\s+(.+?)\s*$|\btext\s*:\s+(.+?)\s*$",
                stripped,
                flags=re.IGNORECASE,
            )
            if say_match:
                content = (say_match.group(1) or say_match.group(2) or "").strip(" .")
        if not content:
            explicit_message_match = re.search(
                r"\b(?:message|text)\s+(?:is|should\s+be|should\s+say)"
                r"\s*[:,]?\s+(.+?)\s*$",
                stripped,
                flags=re.IGNORECASE,
            )
            if explicit_message_match:
                content = explicit_message_match.group(1).strip(" .")
        if not content:
            framed_message_match = re.search(
                r"\b(?:need|want|wanted|would\s+like)\s+to\s+"
                r"(?:send|say|text|message)\s*:?\s+(.+?)\s*$",
                stripped,
                flags=re.IGNORECASE,
            )
            if framed_message_match:
                content = framed_message_match.group(1).strip(" .")
        if not content:
            direct_request = _direct_ask_tell_request_from_text(stripped)
            if direct_request is not None:
                return direct_request
        recipient = ""
        recipient_patterns = (
            rf"\b(?i:(?:send|text|message|ask|tell))\s+(?:a\s+)?(?:message\s+)?to\s+{name_pattern}\b",
            r"\b(?:send|text|message|ask|tell)\s+(?:a\s+)?(?:message\s+)?to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            rf"\b(?i:(?:send|text|message))\s+(?:it|this|that)\s+to\s+{name_pattern}\b",
            rf"\b(?i:(?:send|text|message))\s+{name_pattern}\b",
            rf"\b(?i:(?:full\s+name|name))\s+is\s+{name_pattern}\b",
            rf"\b(?i:(?:his|her|their))\s+name\s*,\s*{name_pattern}\b",
            rf"\b(?i:know)\s+(?:(?:his|her|their)\s+)?name\s*,?\s*{name_pattern}\b",
            rf"\b(?i:know)\s+{name_pattern}\s+(?:is|as|from|in)\b",
            rf"\b(?i:it(?:'s| is))\s+(?:to|for)\s+{name_pattern}\b",
            rf"\b(?i:it(?:'s| is))\s+{name_pattern}\b",
            r"\b(?:ask|tell)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\s+.+",
            r"\bit(?:'s| is)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\b",
            r"\bto\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z.]+){0,3})\s+(?:saying|that|with)\b",
            rf"\bto\s+{name_pattern}\s*[.?!]?$",
        )
        for pattern in recipient_patterns:
            match = re.search(
                pattern, stripped, flags=_recipient_pattern_flags(pattern)
            )
            if match:
                recipient = match.group(1).strip(" .?!")
                recipient = re.sub(
                    r"\s+(?:saying|say|that|with)$",
                    "",
                    recipient,
                    flags=re.IGNORECASE,
                ).strip()
                break
        if recipient and content:
            content = _strip_named_recipient_suffix(content, recipient)
            if not content:
                continue
            return {"recipient_name": recipient, "message_content": content}
    if recipient_from_context and recipient_source_index >= 0:
        if recipient_source_index > 0:
            for prior_text in reversed(all_user_texts[:recipient_source_index]):
                if _extract_phone_from_text(prior_text):
                    continue
                prior_content = _send_message_content_from_visible_text(prior_text)
                prior_content = _strip_named_recipient_suffix(
                    prior_content, recipient_from_context
                )
                if prior_content:
                    return {
                        "recipient_name": recipient_from_context,
                        "message_content": prior_content,
                    }
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
        latest_explicit_message_match = re.search(
            r"\b(?:message|text)\s+(?:is|should\s+be|should\s+say)"
            r"\s*[:,]?\s+(.+?)\s*$",
            latest,
            flags=re.IGNORECASE,
        )
        latest_framed_message_match = latest_explicit_message_match or re.search(
            r"\b(?:need|want|wanted|would\s+like)\s+to\s+"
            r"(?:send|say|text|message)\s*:?\s+(.+?)\s*$",
            latest,
            flags=re.IGNORECASE,
        )
        if (
            latest_index > recipient_source_index
            and latest
            and not latest_is_recipient_only
            and not latest_is_ack
            and (
                latest_framed_message_match is not None
                or not _text_is_contact_method_denial(latest)
            )
            and not _extract_phone_from_text(latest)
        ):
            content = (
                latest_framed_message_match.group(1).strip(" .")
                if latest_framed_message_match
                else latest.strip()
            )
            return {
                "recipient_name": recipient_from_context,
                "message_content": content,
            }
    return None


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = build_robust_openai_client(
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
                    **reasoning_effort_kwargs(self.model_name),
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
        prompted_messages = _with_selector_actor_policy(openai_messages, openai_tools)
        completion_tool_free_turn = _helper_answer_completion_tool_free_turn(
            openai_messages,
            openai_tools,
        )
        if completion_tool_free_turn:
            retry_tool_choice = None
            prompt_openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven] = (
                NOT_GIVEN
            )
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
                or _state_action_planner_tool_choice(
                    prompted_messages,
                    openai_tools,
                )
                or _reminder_recency_workflow_tool_choice(
                    prompted_messages,
                    openai_tools,
                )
                or _relationship_batch_generated_tool_choice(
                    prompted_messages,
                    openai_tools,
                )
                or _reminder_location_batch_tool_choice(
                    prompted_messages,
                    openai_tools,
                )
                or _generated_tool_continuation_choice(prompted_messages, openai_tools)
                or _new_user_turn_generated_tool_choice(prompted_messages, openai_tools)
                or _first_attempt_generated_tool_choice(prompted_messages, openai_tools)
            )
            prompt_openai_tools = _dynamic_generated_tool_schema_filter(
                prompted_messages,
                openai_tools,
                selected_tool_name=retry_tool_choice,
            )
            prompt_openai_tools = _hide_wrapped_native_action_schemas(
                prompt_openai_tools,
                routed_openai_tools=openai_tools,
                selected_tool_name=retry_tool_choice,
            )
            if retry_tool_choice and _execution_facing_tool_name(
                retry_tool_choice
            ) not in _tool_names_execution_facing(prompt_openai_tools):
                retry_tool_choice = None
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

        return _with_transient_openai_retries(
            lambda: call_with_optional_retry_tool_choice(prompted_messages)
        )


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = build_robust_openai_client(
            timeout=_openai_request_timeout_seconds(),
            max_retries=_openai_max_retries(),
        )
