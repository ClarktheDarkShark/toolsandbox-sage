"""Configurable OpenAI ToolSandbox roles for current model names."""

from __future__ import annotations

import os
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
from tool_sandbox.common.utils import all_logging_disabled
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

SELECTOR_ACTOR_POLICY_SENTINEL = "[SAGE selector actor policy]"
DERIVED_ACTOR_POLICY_SENTINEL = "[SAGE derived-value actor policy]"
LOOKUP_PLANNER_ACTOR_POLICY_SENTINEL = "[SAGE lookup-planner actor policy]"
SEARCH_WINDOW_ACTOR_POLICY_SENTINEL = "[SAGE search-window actor policy]"
SAFE_ARGUMENT_ACTOR_POLICY_SENTINEL = "[SAGE safe-argument actor policy]"
ANSWER_RETENTION_ACTOR_POLICY_SENTINEL = "[SAGE answer-retention actor policy]"
TEMPORAL_ANCHOR_ACTOR_POLICY_SENTINEL = "[SAGE temporal-anchor actor policy]"
PRAXIS_BRIDGE_POLICY_ENV = "SAGE_PRAXIS_BRIDGE_POLICY"
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


def _praxis_bridge_policy_enabled() -> bool:
    raw = os.environ.get(PRAXIS_BRIDGE_POLICY_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on", "combined", "full"}


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


def _message_already_called_tool(
    openai_messages: object,
    tool_name: str,
) -> bool:
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if isinstance(function, dict) and function.get("name") == tool_name:
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
            "what ",
            "why ",
            "how ",
            "search",
            "find",
            "add ",
            "remove ",
            "modify ",
            "send ",
        )
    ):
        return False
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
    for message in cast(Iterable[Mapping[str, Any]], openai_messages):
        role = message.get("role")
        if role == "tool":
            saw_tool = True
            continue
        if role != "assistant" or not saw_tool:
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
            'arguments. Phrases like "my boss" or "with +1555..." count as '
            "relationship/phone scalar constraints for lookup planning. "
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
            "or oldest. Do not call this helper on insufficient-information tasks "
            "or when no time/recency search phrase is present."
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
    )


def _safe_argument_actor_policy_message(
    openai_messages: object,
    openai_tools: object,
) -> dict[str, str] | None:
    """Generic guard against placeholder arguments that crash ToolSandbox."""
    if not _has_experimental_helper_tools(openai_tools):
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
            "or a guessed 'last'/'latest' id. First obtain a concrete visible "
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
