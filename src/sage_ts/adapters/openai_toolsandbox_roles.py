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
from tool_sandbox.common.execution_context import get_current_context
from tool_sandbox.common.utils import all_logging_disabled
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

SELECTOR_ACTOR_POLICY_SENTINEL = "[SAGE selector actor policy]"
DERIVED_ACTOR_POLICY_SENTINEL = "[SAGE derived-value actor policy]"
LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL = "[SAGE lookup-planner actor policy]"
SEARCH_WINDOW_ACTOR_POLICY_SENTINEL = "[SAGE search-window actor policy]"
RELATIVE_TIME_ACTOR_POLICY_SENTINEL = "[SAGE relative-time actor policy]"
STATE_ACTION_ACTOR_POLICY_SENTINEL = "[SAGE state-action actor policy]"
SCHEDULING_TIMESTAMP_ACTOR_POLICY_SENTINEL = "[SAGE scheduling-timestamp actor policy]"
SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL = "[SAGE safe-argument actor policy]"
ANSWER_RETENTION_ACTOR_POLICY_SENTINEL = "[SAGE answer-retention actor policy]"
TEMPORAL_ANCHOR_ACTOR_POLICY_SENTINEL = "[SAGE temporal-anchor actor policy]"
CRUD_SUCCESS_ACTOR_POLICY_SENTINEL = "[SAGE CRUD-success actor policy]"
PRAXIS_BRIDGE_POLICY_ENV = "SAGE_PRAXIS_BRIDGE_POLICY"
DEFAULT_LOCAL_UTC_OFFSET_HOURS = -4
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
TRANSIENT_OPENAI_RETRY_DELAYS = (1.0, 3.0)

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

SETTING_GETTER_TOOL_NAMES = {
    "get_cellular_service_status",
    "get_location_service_status",
    "get_low_battery_mode_status",
    "get_wifi_status",
}


def _praxis_bridge_policy_enabled() -> bool:
    raw = os.environ.get(PRAXIS_BRIDGE_POLICY_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "combined", "full"}


def _openai_request_timeout_seconds() -> float:
    raw = os.environ.get("SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS", "90").strip()
    try:
        return max(float(raw), 1.0)
    except ValueError:
        return 90.0


def _with_transient_openai_retries(call: Any) -> ChatCompletion:
    """Retry only transient OpenAI transport/service failures."""
    for attempt in range(len(TRANSIENT_OPENAI_RETRY_DELAYS) + 1):
        try:
            return cast(ChatCompletion, call())
        except TRANSIENT_OPENAI_EXCEPTIONS:
            if attempt >= len(TRANSIENT_OPENAI_RETRY_DELAYS):
                raise
            time.sleep(TRANSIENT_OPENAI_RETRY_DELAYS[attempt])
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
    question_starts = ("what ", "why ", "how ", "who ", "when ", "where ")
    command_tokens = (
        "can you",
        "could you",
        "you can",
        "i need",
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
        "send ",
        "turn on",
        "turn off",
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
        "that's correct",
        "that is correct",
        "thats correct",
        "that's right",
        "that is right",
        "that's what",
        "thats what",
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
        "i'm good",
        "im good",
        "i'm all good",
        "im all good",
        "i'm all set",
        "im all set",
        "i see that",
        "i understand",
        "anything else right now",
        "don't have anything else",
        "do not have anything else",
        "nothing else",
        "move on",
        "you got it",
        "exactly",
    )
    return (
        any(phrase in latest_user for phrase in acknowledgement_phrases)
        or any(word.startswith("thank") for word in words)
        or bool(words & {"thanks", "great", "cool", "okay", "ok", "alright"})
    )


def _latest_user_is_answer_retention_followup(openai_messages: object) -> bool:
    if _latest_user_is_brief_acknowledgement(openai_messages):
        return True
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
    question_starts = ("what ", "why ", "how ", "who ", "when ", "where ")
    command_tokens = (
        "can you",
        "could you",
        "you can",
        "i need",
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
        "send ",
        "turn on",
        "turn off",
    )
    if (
        "?" in latest_user
        or latest_user.startswith(question_starts)
        or any(token in latest_user for token in command_tokens)
    ):
        return False
    retention_phrases = (
        "that's correct",
        "that is correct",
        "thats correct",
        "that's right",
        "that is right",
        "you got it",
        "that's what",
        "thats what",
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
        "i'm good",
        "im good",
        "i'm all good",
        "im all good",
        "i'm all set",
        "im all set",
        "i see that",
        "i understand",
        "anything else right now",
        "don't have anything else",
        "do not have anything else",
        "nothing else",
        "move on",
        "exactly",
        "keep that private",
        "keep it private",
        "keep this private",
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
    return any(phrase in latest_user for phrase in retention_phrases) or bool(
        words & {"accurate", "correct", "right"}
    )


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
            content = str(message.get("content", "") or "").strip()
            if len(content) < 8:
                continue
            lower = content.lower()
            if lower.startswith(("you're welcome", "you are welcome")):
                continue
            answer = content
    return answer


def _recent_exact_final_answer_from_tool(openai_messages: object) -> str | None:
    answer: str | None = None
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        if message.get("role") != "tool":
            continue
        payload = _parse_mapping_payload(message.get("content"))
        if not payload:
            continue
        copy_exactly = bool(payload.get("copy_exactly"))
        candidate = str(
            payload.get("exact_final_answer")
            or payload.get("final_answer_recommendation")
            or ""
        ).strip()
        if not candidate or candidate.lower().startswith("abstain:"):
            continue
        if copy_exactly or payload.get("exact_final_answer"):
            answer = candidate
    return answer


def _messages_show_recent_tool_backed_answer(openai_messages: object) -> bool:
    return (
        _recent_exact_final_answer_from_tool(openai_messages) is not None
        or _recent_tool_backed_answer_text(openai_messages) is not None
    )


def _answer_retention_response_text(openai_messages: object) -> str | None:
    is_brief_ack = _latest_user_is_brief_acknowledgement(openai_messages)
    if not _latest_user_is_answer_retention_followup(openai_messages):
        return None
    answer = _recent_exact_final_answer_from_tool(
        openai_messages
    ) or _recent_tool_backed_answer_text(openai_messages)
    if not answer:
        return None
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
    if not _latest_user_is_answer_retention_followup(openai_messages):
        return None
    if not _messages_show_recent_tool_backed_answer(openai_messages):
        return None
    if not _recent_tool_backed_answer_already_recapped(openai_messages):
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


def _latest_tool_payload_by_name_including_latest(
    openai_messages: object,
    tool_name: str,
) -> dict[str, Any]:
    message = _latest_tool_message(openai_messages, tool_name)
    if message is None:
        return {}
    return _parse_mapping_payload(message.get("content"))


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
            ] and _arguments_match(expected["arguments"], arguments):
                completed += 1
    if completed >= len(actions):
        return None
    return actions[completed]


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
    for text in _all_user_texts(openai_messages):
        lower = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
        if not lower:
            continue
        source = source or _relationship_from_lookup_prompt(lower)
        broad_update = re.search(
            r"\b(?:all|every|each)\s+(?:of\s+)?(?:my\s+)?([a-z]+)\b.*?"
            r"\b(?:updated|changed|set|turned|made)\s+(?:to|into|as)\s+"
            r"(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if broad_update:
            parsed_source = _known_relationship_label(broad_update.group(1))
            parsed_target = _known_relationship_label(broad_update.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
        direct = re.search(
            r"\b(?:make|change|set|turn)\s+(?:all|every|each)\s+"
            r"(?:of\s+)?(?:my\s+)?([a-z]+)\s+(?:contacts\s+)?"
            r"(?:(?:to|into|as)\s+)?(?:my\s+)?([a-z]+)\b",
            lower,
        )
        if direct:
            parsed_source = _known_relationship_label(direct.group(1))
            parsed_target = _known_relationship_label(direct.group(2))
            if parsed_source and parsed_target:
                source = parsed_source
                target = parsed_target
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
        if " them " in f" {lower} " or " back " in f" {lower} ":
            followup = re.search(r"\b(?:to|as)\s+(?:my\s+)?([a-z]+)\b", lower)
            if followup:
                target = _known_relationship_label(followup.group(1)) or target
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


def _contact_relationship_batch_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
    available_names = _tool_names_execution_facing(openai_tools)
    if "plan_contact_relationship_batch_update" not in available_names:
        return None
    if (
        "search_contacts" not in available_names
        or "modify_contact" not in available_names
    ):
        return None

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
        request = _relationship_batch_request(openai_messages)
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

    request = _relationship_batch_request(openai_messages)
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
    if not _has_experimental_helper_tools(openai_tools):
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
            f"selector helper is available: {selector_list}. If the previous "
            "search/get/find result returned candidate records and the task "
            "requires selecting one visible contact, message, reminder, or record "
            "by user constraints before answering or taking a downstream action, "
            "call the helper before manually choosing. Do not call it without "
            "visible candidates, on insufficient-information tasks, or when its "
            "negative triggers match. If the selector abstains or reports a tie, "
            "do not guess before a side-effect action. If the selector returns "
            "exact_final_answer, final_answer_recommendation, or selected_content "
            "for an answer-only task, your next assistant message must include "
            "that retrieved value without adding unrelated fields."
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
            "dict/list payload input. If the helper has a dict payload input, the runtime may "
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
            "If a helper returned exact_final_answer or final_answer_recommendation "
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
            'arguments. Phrases like "my boss" or "with +1555..." count as '
            "relationship/phone scalar constraints for lookup planning. "
            "Relationship words such as boss, friend, coworker, family, or enemy "
            "are valid relationship constraints; do not ask for the person's name "
            "before searching by the supplied relationship. "
            "Prefer this helper over manually assembling search kwargs when it "
            "exactly matches the lookup problem. "
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
            "For modify/remove actions targeting the latest, oldest, most recent, "
            "or upcoming reminder/message, first use the helper to locate the "
            "target record with a bounded original search, then call the original "
            "side-effect tool only with the concrete visible id from that result. "
            "If that search returns multiple records and a visible-record selector "
            "helper is also available, call the selector before answering; do not "
            "manually pick the first returned record when the user asked for latest "
            "or oldest. Do not call this helper on insufficient-information tasks "
            "or when no time/recency search phrase is present."
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
    return {
        "role": "system",
        "content": (
            f"{RELATIVE_TIME_ACTOR_POLICY_SENTINEL} A deterministic relative "
            f"day/time timestamp helper is available: {helper_list}. If the user "
            "asks to add or modify a reminder for a relative day plus explicit "
            "time, such as tomorrow at 5 PM, first call get_current_timestamp "
            "when available and then call this helper with the visible day offset, "
            "hour, minute, and local UTC offset. Use the returned timestamp in "
            "the original add_reminder or modify_reminder call. Do not call the "
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
            "from action_sequence in order; when action_sequence is absent, use "
            "the single returned tool_name and arguments. When the "
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
            "setter. Answer with the completed state change instead."
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
            "instead of calling shift_timestamp or timestamp_to_datetime_info "
            "with a guessed timestamp."
        ),
    }


def _with_selector_actor_policy(
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
) -> list[OpenAIMessage]:
    bridge_policies: tuple[dict[str, str] | None, ...] = ()
    if _praxis_bridge_policy_enabled():
        bridge_policies = (
            _safe_argument_actor_policy_message(openai_messages, openai_tools),
            _temporal_anchor_actor_policy_message(openai_messages, openai_tools),
            _search_window_actor_policy_message(openai_messages, openai_tools),
            _relative_time_actor_policy_message(openai_messages, openai_tools),
            _scheduling_timestamp_actor_policy_message(openai_messages, openai_tools),
            _state_action_actor_policy_message(openai_messages, openai_tools),
        )
    policies = [
        policy
        for policy in (
            _answer_retention_actor_policy_message(openai_messages),
            *bridge_policies,
            _lookup_planner_actor_policy_message(openai_messages, openai_tools),
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
        if "phone" not in lower and "number" not in lower:
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
        request == "remove_upcoming"
        and "get_current_timestamp" in available_names
        and not _message_already_called_tool(openai_messages, "get_current_timestamp")
        and _latest_tool_message(openai_messages, "get_current_timestamp") is None
    ):
        return _synthetic_tool_call_completion(
            model_name=model_name,
            completion_id="sage-reminder-upcoming-current-timestamp",
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
        if (
            request == "remove_upcoming"
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
    if _latest_tool_is(openai_messages, "relative_day_time_to_timestamp"):
        if request != "modify_latest" or "modify_reminder" not in available_names:
            return None
        selected = _selected_record_payload(openai_messages)
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
        if request == "modify_latest":
            records = _records_from_latest_reminder_search(openai_messages)
            if not records:
                return _synthetic_text_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-latest-empty",
                    content="I could not find a reminder to update.",
                )
            if "select_record_by_timestamp_extreme" in available_names:
                return _synthetic_tool_call_completion(
                    model_name=model_name,
                    completion_id="sage-reminder-latest-select",
                    tool_name=_tool_name_for_call(
                        openai_tools, "select_record_by_timestamp_extreme"
                    ),
                    arguments={
                        "records": records,
                        "timestamp_field": "reminder_timestamp",
                        "mode": "latest",
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
                        "timestamp_field": "reminder_timestamp",
                        "mode": "oldest",
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
        if request == "modify_latest":
            requested_time = _tomorrow_time_request(openai_messages)
            if (
                requested_time is None
                or "relative_day_time_to_timestamp" not in available_names
            ):
                return None
            current_timestamp = _latest_current_timestamp(openai_messages)
            if current_timestamp is None:
                return None
            hour, minute = requested_time
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
        and _latest_tool_is(openai_messages, "search_messages")
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
            selected = _record_by_timestamp_extreme(records, selection_mode)
            self_person_id = ""
            if isinstance(selected, Mapping):
                if "sent" in user_text and " to " in user_text:
                    self_person_id = str(selected.get("sender_person_id") or "").strip()
                elif "from" in user_text or "sent me" in user_text:
                    self_person_id = str(
                        selected.get("recipient_person_id") or ""
                    ).strip()
            return _synthetic_tool_call_completion(
                model_name=model_name,
                completion_id="sage-contact-update-counterparty-select",
                tool_name=_tool_name_for_call(
                    openai_tools, "select_message_counterparty_for_contact_update"
                ),
                arguments={
                    "records": records,
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


def _safe_action_or_abstain_request(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, Any] | None:
    user_request = _latest_user_request_text(openai_messages).strip()
    lower = " ".join(user_request.lower().replace("_", " ").split())
    if not lower:
        return None
    available_original_tools = sorted(
        name
        for name in _tool_names_execution_facing(openai_tools)
        if name in ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    )
    requested_action = ""
    required_original_tools: list[str] = []
    if any(token in lower for token in ("remove", "delete")) and "contact" in lower:
        requested_action = "remove_contact"
        required_original_tools = ["search_contacts", "remove_contact"]
    elif (
        any(token in lower for token in ("modify", "update", "change"))
        and "contact" in lower
    ):
        requested_action = "modify_contact"
        required_original_tools = ["search_contacts", "modify_contact"]
    elif "message" in lower and any(token in lower for token in ("send", "text")):
        requested_action = "send_message"
        required_original_tools = ["search_contacts", "send_message_with_phone_number"]
    elif "reminder" in lower and any(token in lower for token in ("remove", "delete")):
        requested_action = "remove_reminder"
        required_original_tools = ["search_reminder", "remove_reminder"]
    elif "reminder" in lower and any(
        token in lower for token in ("modify", "update", "change", "postpone")
    ):
        requested_action = "modify_reminder"
        required_original_tools = ["search_reminder", "modify_reminder"]
    elif "reminder" in lower and any(token in lower for token in ("add", "create")):
        requested_action = "add_reminder"
        required_original_tools = ["add_reminder"]
    else:
        return None

    target_identifier = _extract_person_id_from_text(
        user_request
    ) or _extract_phone_from_text(user_request)
    if not target_identifier and any(
        token in lower for token in ("latest", "last", "most recent", "recent")
    ):
        target_identifier = "recency_reference"
        if requested_action == "modify_contact":
            required_original_tools = ["search_messages", "modify_contact"]
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
        return _synthetic_text_completion(
            model_name=model_name,
            completion_id="sage-safe-action-abstain-answer",
            content=answer,
        )
    if _message_already_called_tool(openai_messages, "prepare_safe_action_or_abstain"):
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
    if "remove_contact" not in available_names or "search_contacts" in available_names:
        return None
    all_user_text = " ".join(_all_user_texts(openai_messages)).strip()
    lower_all = all_user_text.lower()
    if not any(token in lower_all for token in ("remove", "delete")):
        return None
    if "contact" not in lower_all or "phone" not in lower_all:
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
    if _latest_assistant_text_contains(openai_messages, phone):
        if any(token in latest_user for token in ("thank", "ok", "okay", "alright")):
            return None
    return (
        "I do not have enough information to safely remove the contact with "
        f"phone number {phone}. I would need a contact name or person_id, or "
        "access to search contacts, before I can remove it."
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
    latest_user = _latest_user_request_text(openai_messages).lower()
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


def _state_action_sequence_bridge_completion(
    openai_messages: object,
    openai_tools: object,
    *,
    model_name: str,
) -> ChatCompletion | None:
    if not _praxis_bridge_policy_enabled():
        return None
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
    if any(_message_already_called_tool(openai_messages, name) for name in helpers):
        return None

    messages = list(cast(Iterable[Mapping[str, Any]], openai_messages))
    latest = messages[-1] if messages else {}
    latest_role = latest.get("role")
    latest_user = _latest_user_request_text(openai_messages)
    latest_user_lower = latest_user.lower()
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
        "enable",
        "disable",
        "switch on",
        "switch off",
    )
    is_direct_state_action = any(
        term in latest_user_lower for term in direct_action_terms
    ) and any(term in latest_user_lower for term in service_terms)
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
    if not (explicit_low_battery_precondition or is_blocked_state_error):
        return None

    visible_state = " ".join(
        part
        for part in (
            latest_user,
            latest_tool_text,
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


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = self.openai_client.with_options(
            timeout=_openai_request_timeout_seconds()
        )

    def model_inference(
        self,
        openai_messages: list[OpenAIMessage],
        openai_tools: Union[Iterable[ChatCompletionToolParam], NotGiven],
    ) -> ChatCompletion:
        """Run inference, with opt-in diagnostic tool forcing for adoption tests."""
        answer_completion_bridge = _answer_completion_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if answer_completion_bridge is not None:
            return answer_completion_bridge
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
        state_planner_bridge = _state_action_planner_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if state_planner_bridge is not None:
            return state_planner_bridge
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
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-setting-success",
                content=setting_success_answer,
            )
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
        send_missing_phone = _send_message_missing_phone_response_text(
            openai_messages, openai_tools
        )
        if send_missing_phone:
            return _synthetic_text_completion(
                model_name=self.model_name,
                completion_id="sage-send-message-missing-phone",
                content=send_missing_phone,
            )
        safe_action_abstain_bridge = _safe_action_or_abstain_bridge_completion(
            openai_messages,
            openai_tools,
            model_name=self.model_name,
        )
        if safe_action_abstain_bridge is not None:
            return safe_action_abstain_bridge
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
            return _with_transient_openai_retries(
                lambda: self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(list[ChatCompletionMessageParam], prompted_messages),
                    tools=openai_tools,
                    tool_choice={"type": "function", "function": {"name": forced_tool}},
                )
            )


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
        self.openai_client = self.openai_client.with_options(
            timeout=_openai_request_timeout_seconds()
        )
