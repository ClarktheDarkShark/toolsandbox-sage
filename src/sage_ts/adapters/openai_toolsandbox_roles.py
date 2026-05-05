"""Configurable OpenAI ToolSandbox roles for current model names."""

from __future__ import annotations

import os
from typing import Any, Iterable, Literal, Mapping, Union, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from sage_ts.config.models import resolve_model_name
from tool_sandbox.common.utils import all_logging_disabled
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

SELECTOR_ACTOR_POLICY_SENTINEL = "[SAGE selector actor policy]"
DERIVED_ACTOR_POLICY_SENTINEL = "[SAGE derived-value actor policy]"
OpenAIMessage = dict[
    Literal["role", "content", "tool_call_id", "name", "tool_calls"],
    Any,
]


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
        if not isinstance(name, str) or len(input_names) != 1:
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
    if not text.startswith(("[", "{")):
        return False
    lower = text.lower()
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
            "call the selector before manually choosing. Do not call it without "
            "visible candidates, on insufficient-information tasks, or when its "
            "negative triggers match. If the selector abstains or reports a tie, "
            "do not guess before a side-effect action."
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
            "field. Pass the full prior tool payload as the helper's dict input. "
            "Do not call it before the original lookup/result tool has returned, "
            "on unrelated tasks, or when required fields are absent."
        ),
    }


def _with_selector_actor_policy(
    openai_messages: list[OpenAIMessage],
    openai_tools: object,
) -> list[OpenAIMessage]:
    policies = [
        policy
        for policy in (
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
