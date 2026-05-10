"""Configurable OpenAI ToolSandbox roles for current model names."""

from __future__ import annotations

import ast
import json
import os
import re
from typing import Any, Iterable, Literal, Mapping, Union, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion import Choice

from sage_ts.config.models import resolve_model_name
from tool_sandbox.common.execution_context import get_current_context
from tool_sandbox.common.utils import all_logging_disabled
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

SELECTOR_ACTOR_POLICY_SENTINEL = "[SAGE selector actor policy]"
DERIVED_ACTOR_POLICY_SENTINEL = "[SAGE derived-value actor policy]"
LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL = "[SAGE lookup-planner actor policy]"
SEARCH_WINDOW_ACTOR_POLICY_SENTINEL = "[SAGE search-window actor policy]"
STATE_ACTION_ACTOR_POLICY_SENTINEL = "[SAGE state-action actor policy]"
DOMAIN_ABSTENTION_ACTOR_POLICY_SENTINEL = "[SAGE domain-abstention actor policy]"
CRUD_BRIDGE_ACTOR_POLICY_SENTINEL = "[SAGE CRUD-bridge actor policy]"
SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL = "[SAGE scheduling-timestamp actor policy]"
SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL = "[SAGE safe-argument actor policy]"
ANSWER_RETENTION_ACTOR_POLICY_SENTINEL = "[SAGE answer-retention actor policy]"
SETTING_SUCCESS_ACTOR_POLICY_SENTINEL = "[SAGE setting-success actor policy]"
CRUD_SUCCESS_ACTOR_POLICY_SENTINEL = "[SAGE CRUD-success actor policy]"
OpenAIMessage = dict[
    Literal["role", "content", "tool_call_id", "name", "tool_calls"],
    Any,
]

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

SETTING_SETTER_TOOL_NAMES = {
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
}


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
        return str(get_current_context().get_execution_facing_tool_name(tool_name))
    except Exception:
        return tool_name


def _tool_names_execution_facing(openai_tools: object) -> set[str]:
    return {_execution_facing_tool_name(name) for name in _tool_names(openai_tools)}


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
        is_state_action_planner = name == "plan_device_state_action_sequence" or (
            {"user_request", "visible_state_or_error"}.issubset(input_names)
            and "state action sequence" in description
        )
        if is_state_action_planner:
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


def _domain_abstention_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that produce final-answer-ready abstentions."""
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
        is_domain_abstention_helper = name == "recommend_domain_safe_abstention" or (
            {"user_request", "available_original_tools", "missing_signal"}.issubset(
                input_names
            )
            and "domain-specific insufficient-information" in description
        )
        if is_domain_abstention_helper:
            helpers.add(name)
    return helpers


def _crud_bridge_tool_names(openai_tools: object) -> set[str]:
    """Return helpers that bridge CRUD selection/planning to original kwargs."""
    if openai_tools is NOT_GIVEN:
        return set()
    helpers: set[str] = set()
    for tool in cast(Iterable[Mapping[str, Any]], openai_tools):
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if name in {"plan_contact_crud_action", "prepare_reminder_crud_action"}:
            helpers.add(str(name))
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
            "temperature",
            "latitude",
            "longitude",
        )
    )


def _messages_show_prior_candidate_records(openai_messages: object) -> bool:
    """Return whether a prior base tool exposed candidate records/lists."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        name = str(message.get("name", ""))
        if not name.startswith(("search_", "get_", "find_")):
            continue
        if _tool_content_has_candidate_records(message.get("content")):
            return True
    return False


def _messages_show_prior_structured_payload(openai_messages: object) -> bool:
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        name = str(message.get("name", ""))
        if name.startswith(("search_", "get_", "find_", "convert_", "calculate_")):
            if _tool_content_has_structured_payload(message.get("content")):
                return True
    return False


def _latest_user_is_brief_acknowledgement(openai_messages: object) -> bool:
    latest_user = ""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages):
        if message.get("role") == "user":
            latest_user = str(message.get("content", "")).strip().lower()
            break
    if not latest_user:
        return False
    if "?" in latest_user or any(
        token in latest_user
        for token in (
            "can you",
            "could you",
            "please ",
            "what ",
            "why ",
            "how ",
            "try ",
            "turn ",
            "enable ",
            "disable ",
            "switch ",
            "set ",
            "search",
            "find",
            "add ",
            "remove ",
            "modify ",
            "update ",
            "change ",
            "make ",
            "delete ",
            "create ",
            "send ",
            "text ",
            "call ",
        )
    ):
        return False
    if "thank" in latest_user or "thanks" in latest_user:
        return True
    acknowledgement_tokens = (
        "thank",
        "thanks",
        "got it",
        "great",
        "cool",
        "okay",
        "ok",
        "alright",
        "you found it",
    )
    return any(token in latest_user for token in acknowledgement_tokens)


def _recent_tool_backed_answer_text(openai_messages: object) -> str | None:
    saw_tool = False
    answer: str | None = None
    latest_tool_name = ""
    excluded_latest_tools: set[str] = set()
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        role = message.get("role")
        if role == "tool":
            saw_tool = True
            latest_tool_name = str(message.get("name", "") or "")
            continue
        if role != "assistant" or not saw_tool:
            continue
        if latest_tool_name in excluded_latest_tools:
            continue
        content = str(message.get("content", "") or "").strip()
        if len(content) < 8:
            continue
        lower = content.lower()
        if lower.startswith(("you're welcome", "you are welcome")):
            continue
        if any(
            token in lower
            for token in (" is ", " are ", "phone", "+", "boss", "message", "says")
        ):
            answer = content
    return answer


def _messages_show_recent_tool_backed_answer(openai_messages: object) -> bool:
    return _recent_tool_backed_answer_text(openai_messages) is not None


def _answer_retention_response_text(openai_messages: object) -> str | None:
    if not _latest_user_is_brief_acknowledgement(openai_messages):
        return None
    answer = _recent_tool_backed_answer_text(openai_messages)
    if not answer:
        return None
    answer = " ".join(answer.split())
    if len(answer) > 280:
        answer = answer[:277].rstrip() + "..."
    return f"You're welcome. To recap: {answer}"


def _latest_user_request_text(openai_messages: object) -> str:
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        if message.get("role") == "user":
            return str(message.get("content", "") or "")
    return ""


def _latest_successful_setting_tool_call(
    openai_messages: object,
) -> tuple[str, dict[str, Any]] | None:
    """Return the latest original setting setter call if it just succeeded."""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    if latest.get("role") != "tool":
        return None
    tool_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if tool_name not in {
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
        "set_wifi_status",
    }:
        return None
    content = str(latest.get("content", "") or "").strip().lower()
    if content not in {"", "none", "null"}:
        return None
    tool_call_id = str(latest.get("tool_call_id", "") or "")
    for message in reversed(messages[:-1]):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            if tool_call_id and tool_call.get("id") != tool_call_id:
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            function_name = _execution_facing_tool_name(
                str(function.get("name", "") or "")
            )
            if function_name != tool_name:
                continue
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = json.loads(str(raw_arguments or "{}"))
            except json.JSONDecodeError:
                arguments = {}
            if isinstance(arguments, dict):
                return tool_name, arguments
            return tool_name, {}
    return tool_name, {}


def _latest_successful_crud_tool_call(
    openai_messages: object,
) -> tuple[str, dict[str, Any]] | None:
    """Return the latest original CRUD side-effect call if it just succeeded."""
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages:
        return None
    latest = messages[-1]
    if latest.get("role") != "tool":
        return None
    tool_name = _execution_facing_tool_name(str(latest.get("name", "") or ""))
    if tool_name not in {
        "add_contact",
        "modify_contact",
        "remove_contact",
        "add_reminder",
        "modify_reminder",
        "remove_reminder",
    }:
        return None
    content = str(latest.get("content", "") or "").strip().lower()
    if any(
        token in content
        for token in (
            "permissionerror",
            "connectionerror",
            "tool_call_exception",
            "error",
            "failed",
            "not found",
        )
    ):
        return None
    tool_call_id = str(latest.get("tool_call_id", "") or "")
    for message in reversed(messages[:-1]):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            if tool_call_id and tool_call.get("id") != tool_call_id:
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            function_name = _execution_facing_tool_name(
                str(function.get("name", "") or "")
            )
            if function_name != tool_name:
                continue
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = json.loads(str(raw_arguments or "{}"))
            except json.JSONDecodeError:
                arguments = {}
            if isinstance(arguments, dict):
                return tool_name, arguments
            return tool_name, {}
    return tool_name, {}


def _latest_tool_success_content(openai_messages: object) -> str | None:
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    if not messages or messages[-1].get("role") != "tool":
        return None
    content = str(messages[-1].get("content", "") or "").strip()
    lower = content.lower()
    if any(
        token in lower
        for token in (
            "permissionerror",
            "connectionerror",
            "tool_call_exception",
            "error",
            "failed",
            "not found",
        )
    ):
        return None
    return content


def _latest_prior_tool_call_arguments(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    target_tool_name = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages[:-1]):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in reversed(tool_calls):
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            function_name = _execution_facing_tool_name(
                str(function.get("name", "") or "")
            )
            if function_name != target_tool_name:
                continue
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = json.loads(str(raw_arguments or "{}"))
            except json.JSONDecodeError:
                return {}
            return arguments if isinstance(arguments, dict) else {}
    return {}


def _parse_mapping_payload(raw: object) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            payload = parser(text)
        except (SyntaxError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _parse_sequence_payload(raw: object) -> list[Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            payload = parser(text)
        except (SyntaxError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, list):
            return payload
    return None


def _latest_tool_payload_by_name(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any] | None:
    target_tool_name = _execution_facing_tool_name(tool_name)
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for message in reversed(messages[:-1]):
        message_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") != "tool" or message_name != target_tool_name:
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if payload is not None:
            return payload
    return None


def _latest_tool_message(
    openai_messages: object,
    tool_name: str,
) -> Mapping[str, Any] | None:
    target_tool_name = _execution_facing_tool_name(tool_name)
    for message in reversed(list(cast(Iterable[Mapping[str, Any]], openai_messages))):
        message_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and message_name == target_tool_name:
            return message
    return None


def _latest_tool_payload_by_name_including_latest(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any] | None:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return None
    return _parse_mapping_payload(message.get("content"))


def _latest_tool_message_index(
    openai_messages: object,
    tool_names: set[str],
) -> tuple[int, Mapping[str, Any]] | None:
    target_tool_names = {_execution_facing_tool_name(name) for name in tool_names}
    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        message_name = _execution_facing_tool_name(str(message.get("name", "") or ""))
        if message.get("role") == "tool" and message_name in target_tool_names:
            return index, message
    return None


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


def _arguments_match(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


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
            if _execution_facing_tool_name(name) == expected[
                "tool_name"
            ] and _arguments_match(
                expected["arguments"],
                arguments,
            ):
                completed += 1
    if completed >= len(actions):
        return None
    return actions[completed]


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


def _join_visible_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


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
    source_relationship = (
        str(plan.get("source_relationship") or "").strip().lower()
        if plan is not None
        else ""
    )
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
    match = re.search(r"\+\d[\d\s().-]{6,}\d", text)
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
    if not _experimental_actor_policy_enabled(openai_tools):
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
    if any(token in user_request for token in downstream_tokens):
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
            f"selector helper is available: {selector_list}. If the previous "
            "search/get/find result returned candidate records and the task "
            "requires selecting one visible contact, message, reminder, or record "
            "by user constraints before answering or taking a downstream action, "
            "call the helper before manually choosing. Do not call it without "
            "visible candidates, on insufficient-information tasks, or when its "
            "negative triggers match. If the selector abstains or reports a tie, "
            "do not guess before a side-effect action. If the selector returns "
            "exact_final_answer, final_answer_recommendation, or selected_content "
            "for an answer-only task, your next assistant message must be exactly "
            "that value without markdown, extra punctuation, or additional fields."
        ),
    }


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
    return {
        "role": "system",
        "content": (
            f"{DERIVED_ACTOR_POLICY_SENTINEL} A deterministic extraction or "
            f"normalization helper is available: {helper_list}. If a previous "
            "ToolSandbox tool returned the raw structured payload needed by this "
            "helper and the user asks for a scalar/normalized answer from that "
            "payload, call the helper before manually copying or normalizing the "
            "field. Pass the full prior tool payload when the helper expects a "
            "dict/list payload input. If the helper has a dict payload input, "
            "the runtime may "
            "autofill that input from the latest original tool result; provide any "
            "remaining scalar selector inputs such as requested_field or target_unit. "
            "Do not call it before the original lookup/result tool has returned, "
            "on unrelated tasks, or when required fields are absent."
        ),
    }


def _answer_retention_actor_policy_message(
    openai_messages: object,
) -> dict[str, str] | None:
    """Keep a just-produced lookup answer visible through closing turns."""
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if ANSWER_RETENTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    if not _latest_user_is_brief_acknowledgement(openai_messages):
        return None
    if not _messages_show_recent_tool_backed_answer(openai_messages):
        return None
    return {
        "role": "system",
        "content": (
            f"{ANSWER_RETENTION_ACTOR_POLICY_SENTINEL} The user is acknowledging "
            "a just-completed tool-backed lookup. The next assistant message must "
            "include the retrieved value again in a concise recap. Do not answer "
            'only with a generic acknowledgement such as "you\'re welcome." Do not '
            "call tools only to recap, and do not invent new facts."
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
            "arguments or asking for clarification. For contact lookup tasks "
            "such as finding a name from a relationship, a relationship from a "
            "phone number, or a phone number from a name, a visible scalar is "
            "enough to call the helper first; then call original search_contacts "
            "with the returned search_contacts_kwargs and answer from the "
            'returned record field. Phrases like "my boss" or "with +1555..." '
            "count as relationship/phone scalar constraints for lookup planning. "
            "For send-message tasks where the user names a recipient but does not "
            "provide a phone number, a visible name is enough to call the lookup "
            "planner before asking for clarification; then search_contacts with "
            "the returned kwargs and send the requested content to the returned "
            "phone number. "
            "Use this helper instead of manually assembling search kwargs when "
            "it exactly matches the lookup problem. "
            "If it returns should_call_search_contacts or "
            "should_call_tool with search_*_kwargs, call the original "
            "ToolSandbox search tool next with those kwargs, then answer from "
            "the returned record or use a visible post-search extractor. Do not "
            "call it when no scalar constraint is available, on unrelated "
            "tasks, on insufficient-information tasks, or for final side-effect "
            "actions."
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
            "for the latest, oldest, last, most recent, yesterday, today, or "
            "upcoming message/reminder/search result, prefer this helper before "
            "manually constructing search criteria. First call get_current_timestamp "
            "when a current timestamp is needed; then call the helper with the "
            "visible recency phrase, target_domain ('message' or 'reminder'), "
            "timestamp_intent, and direction; then call the original ToolSandbox "
            "search tool in target_tool_name with search_kwargs. Never call "
            "search_messages or search_reminder with blank strings, null values, "
            "or no criteria when a recency phrase can be converted into bounds. "
            "If that search returns multiple records and a visible-record selector "
            "helper is also available, call the selector before answering; do not "
            "manually pick the first returned record when the user asked for latest "
            "or oldest. "
            "Do not call this helper on insufficient-information tasks or when no "
            "time/recency search phrase is present."
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
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if STATE_ACTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
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
    return {
        "role": "system",
        "content": (
            f"{STATE_ACTION_ACTOR_POLICY_SENTINEL} A deterministic device-state "
            f"action planner helper is available: {helper_list}. If the user asks "
            "to turn wifi, cellular service, location service, or low battery mode "
            "on/off, or a previous original tool reports a blocked wifi/cellular/"
            "location precondition, call this helper with the user request and any "
            "visible state/error text. If the helper returns should_call=true, call "
            "the original ToolSandbox setter calls from action_sequence in order; "
            "the first call is also provided in tool_name and arguments. When the "
            "request is a direct setting change, answer exactly with "
            "final_response_recommendation after the setters succeed, with no extra "
            "words. When the helper output says continue_original_task_after_sequence "
            "is true, do not answer with the state message; after the setters succeed, "
            "continue the user's original task. Do not call it on insufficient-"
            "information tasks or unrelated contact/reminder/message selection tasks. "
            "When an original setting setter returns None, that means the setter "
            "succeeded; do not claim the action failed or that you cannot change "
            "settings."
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
            "call the matching helper to produce reminder_timestamp before calling "
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


def _domain_abstention_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for final-answer-ready insufficient-info helpers."""
    helpers = _domain_abstention_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if DOMAIN_ABSTENTION_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    message_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
    ).lower()
    abstention_triggers = (
        "insufficient",
        "cannot determine",
        "not enough information",
        "missing",
        "unavailable",
        "no search_contacts",
        "no remove_contact",
        "no current",
    )
    if not any(trigger in message_text for trigger in abstention_triggers):
        return None
    helper_list = ", ".join(sorted(helpers))
    original_tool_names = sorted(
        name
        for name in _tool_names(openai_tools)
        if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    )
    original_tool_list = ", ".join(original_tool_names)
    return {
        "role": "system",
        "content": (
            f"{DOMAIN_ABSTENTION_ACTOR_POLICY_SENTINEL} A domain-specific safe "
            f"abstention helper is available: {helper_list}. If the request says "
            "there is not enough information, lacks a required current date/time/"
            "location, lacks a concrete contact/reminder/message id, or an original "
            "ToolSandbox action/search tool needed for a safe side effect is not "
            "available, call the helper before guessing or calling a risky original "
            "tool. Pass available_original_tools exactly as this comma-separated "
            f"visible original-tool list: {original_tool_list}. If should_abstain "
            "is true, do not call any forbidden_downstream_tools and answer exactly "
            "with final_answer_recommendation. Do not call it on ordinary solvable "
            "lookup/action tasks where the needed original tools and concrete ids "
            "are available."
        ),
    }


def _crud_bridge_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Bounded policy nudge for pure contact/reminder CRUD bridge helpers."""
    helpers = _crud_bridge_tool_names(openai_tools)
    if not helpers:
        return None
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if CRUD_BRIDGE_ACTOR_POLICY_SENTINEL in str(message.get("content", "")):
            return None
    message_text = " ".join(
        str(message.get("content", ""))
        for message in cast(Iterable[Mapping[str, Any]], openai_messages)
    ).lower()
    crud_triggers = (
        "add contact",
        "create contact",
        "modify contact",
        "update contact",
        "remove contact",
        "delete contact",
        "add reminder",
        "create reminder",
        "modify reminder",
        "update reminder",
        "remove reminder",
        "delete reminder",
        "phone number",
        "relationship",
    )
    if not any(trigger in message_text for trigger in crud_triggers):
        return None
    helper_list = ", ".join(sorted(helpers))
    return {
        "role": "system",
        "content": (
            f"{CRUD_BRIDGE_ACTOR_POLICY_SENTINEL} Pure CRUD bridge helpers are "
            f"available: {helper_list}. For contact add/modify/remove tasks with "
            "a concrete contact id, phone number, name, or relationship, prefer "
            "plan_contact_crud_action. If it returns should_call_search_contacts, "
            "call original search_contacts with search_contacts_kwargs, then call "
            "the helper again with the visible contacts list. If it returns "
            "should_call_tool, call the original downstream_tool_name with "
            "downstream_tool_kwargs. For reminder add/modify/remove tasks after "
            "search_reminder returns visible records, or when add_reminder fields "
            "are already known, use prepare_reminder_crud_action and then call "
            "the original downstream reminder tool when should_call_tool is true. "
            "These helpers never perform side effects themselves. Do not use them "
            "for insufficient-information tasks, unrelated service/weather tasks, "
            "or broad search-only answers."
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
        or _state_action_planner_tool_names(openai_tools)
        or _scheduling_timestamp_tool_names(openai_tools)
        or _domain_abstention_tool_names(openai_tools)
        or _crud_bridge_tool_names(openai_tools)
    )


def _experimental_actor_policy_enabled(openai_tools: object) -> bool:
    """Enable candidate-arm policies even when routing hides all helpers."""
    if _has_experimental_helper_tools(openai_tools):
        return True
    if os.environ.get("SAGE_TS_RUN_ARM") != "candidate":
        return False
    registry_digest = os.environ.get("SAGE_TS_REGISTRY_DIGEST", "")
    return registry_digest not in {"", "none", "missing"}


def _safe_argument_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic guard against placeholder arguments that crash ToolSandbox."""
    if not _experimental_actor_policy_enabled(openai_tools):
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
            "helper if available. For search_contacts by phone, name, or "
            "relationship, do not add is_self=true unless the user explicitly "
            "asks for their own/self contact. First obtain a concrete visible "
            "record or scalar id from a search result or deterministic helper. "
            "If the user request lacks enough information and no visible record "
            "or helper result supplies the required id, ask for clarification or "
            "state that there is insufficient information. Do not probe "
            "search_contacts, search_messages, search_reminders, modify_contact, "
            "modify_reminder, remove_reminder, or other original tools with "
            "None/null/self placeholders. For contact updates based on the last, "
            "latest, or most recent person contacted or messaged, do not use "
            "search_contacts(is_self=true) or the user's self contact as the "
            "target person. Modify a contact only after a visible message/contact "
            "record or a dedicated helper unambiguously identifies the non-self "
            "counterparty and concrete person_id; otherwise ask or abstain. "
            "For add_contact, when the user already supplied a contact name and "
            "phone_number, call add_contact immediately with those concrete fields; "
            "do not ask for optional relationship or is_self. Include relationship "
            "or is_self only when the user explicitly supplies them, and normalize "
            "relationship values to lowercase. "
            "If plan_contact_relationship_batch_update is visible and the user "
            "asks to make, mark, change, or update all/every/each contacts with "
            "a relationship such as friends or enemies to another relationship, "
            "call that helper first. The helper can search by relationship; do "
            "not ask the user for names or for the current relationship when the "
            "request already names the relationship group. "
            "For send-message tasks, a named recipient is a concrete scalar "
            "constraint when search_contacts or a send-recipient lookup helper is "
            "visible; search for that contact before asking the user for a phone "
            "number. If send_message_with_phone_number fails because cellular "
            "service is disabled and set_cellular_service_status is visible, turn "
            "cellular service on and retry the same send once."
        ),
    }


def _with_selector_actor_policy(
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
) -> list[OpenAIMessage]:
    policies = [
        policy
        for policy in (
            _answer_retention_actor_policy_message(openai_messages),
            _safe_argument_actor_policy_message(openai_messages, openai_tools),
            _domain_abstention_actor_policy_message(openai_messages, openai_tools),
            _crud_bridge_actor_policy_message(openai_messages, openai_tools),
            _state_action_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _lookup_planner_actor_policy_message(openai_messages, openai_tools),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _selector_actor_policy_message(openai_messages, openai_tools),
            _derived_actor_policy_message(openai_messages, openai_tools),
        )
        if policy is not None
    ]
    if not policies:
        return openai_messages
    return [cast(OpenAIMessage, policy) for policy in policies] + openai_messages


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


def _normalize_phone_for_search(text: str) -> str:
    value = re.sub(r"[^\d+]", "", text)
    if value.startswith("+"):
        return value
    if len(value) == 11 and value.startswith("1"):
        return f"+{value}"
    if len(value) == 10:
        return f"+1{value}"
    return value


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
    if not _experimental_actor_policy_enabled(openai_tools):
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
        if "remove" in lower and "upcoming reminder" in lower:
            return "remove_upcoming"
    return None


def _records_from_latest_reminder_search(
    openai_messages: object,
) -> list[Mapping[str, Any]]:
    message = _latest_tool_message(openai_messages, "search_reminder")
    if message is None:
        return []
    payload = _parse_sequence_payload(message.get("content")) or []
    return [record for record in payload if isinstance(record, Mapping)]


def _yesterday_bounds(
    current_timestamp: float, timezone_offset: float = 0.0
) -> tuple[float, float]:
    offset_seconds = timezone_offset * 3600.0
    local_now = current_timestamp + offset_seconds
    local_day_start = float(int(local_now // 86400.0) * 86400.0)
    day_start = local_day_start - offset_seconds
    return day_start - 86400.0, day_start - 1.0


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


def _selected_record_payload(openai_messages: object) -> Mapping[str, Any] | None:
    payload = _latest_tool_payload_by_name_including_latest(
        openai_messages, "select_record_by_timestamp_extreme"
    )
    selected = payload.get("selected_record") if payload else None
    return selected if isinstance(selected, Mapping) else None


def _reminder_recency_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _experimental_actor_policy_enabled(openai_tools):
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    request = _reminder_recency_request(openai_messages)
    if request is None:
        return None
    if _latest_tool_is(openai_messages, "get_current_timestamp"):
        current_timestamp = _latest_current_timestamp(openai_messages)
        if (
            current_timestamp is None
            or "resolve_search_window_or_bounds" not in available_names
        ):
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
        if request == "remove_upcoming":
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
    if _latest_tool_is(openai_messages, "search_reminder"):
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
                        "timestamp_field": "reminder_timestamp",
                        "mode": "oldest",
                    },
                )
    if _latest_tool_is(openai_messages, "select_record_by_timestamp_extreme"):
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


def _state_action_sequence_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    action = _state_action_sequence_next_action(openai_messages, openai_tools)
    if action is None:
        return None
    return _synthetic_tool_call_completion(
        model_name=model_name,
        completion_id="sage-state-action-sequence-next",
        tool_name=_tool_name_for_call(openai_tools, str(action["tool_name"])),
        arguments=cast(Mapping[str, Any], action["arguments"]),
    )


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()

    def model_inference(
        self,
        openai_messages: list[OpenAIMessage],
        openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    ) -> ChatCompletion:
        """Run inference, with opt-in diagnostic tool forcing for adoption tests."""
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
        state_sequence_bridge = _state_action_sequence_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if state_sequence_bridge is not None:
            return state_sequence_bridge
        setting_success_answer = _setting_success_response_text(
            openai_messages, openai_tools
        )
        if setting_success_answer:
            return ChatCompletion.model_construct(
                id="sage-setting-success",
                choices=[
                    Choice.model_construct(
                        finish_reason="stop",
                        index=0,
                        message=ChatCompletionMessage.model_construct(
                            content=setting_success_answer,
                            role="assistant",
                            tool_calls=None,
                        ),
                    )
                ],
                created=0,
                model=self.model_name,
                object="chat.completion",
            )
        crud_success_answer = _crud_success_response_text(openai_messages, openai_tools)
        if crud_success_answer:
            return ChatCompletion.model_construct(
                id="sage-crud-success",
                choices=[
                    Choice.model_construct(
                        finish_reason="stop",
                        index=0,
                        message=ChatCompletionMessage.model_construct(
                            content=crud_success_answer,
                            role="assistant",
                            tool_calls=None,
                        ),
                    )
                ],
                created=0,
                model=self.model_name,
                object="chat.completion",
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
            return super().model_inference(prompted_messages, openai_tools)
        with all_logging_disabled():
            return self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=cast(list[ChatCompletionMessageParam], prompted_messages),
                tools=openai_tools,
                tool_choice={"type": "function", "function": {"name": forced_tool}},
            )


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
