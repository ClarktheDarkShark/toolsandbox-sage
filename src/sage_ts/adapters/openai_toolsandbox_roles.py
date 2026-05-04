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


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()

    def model_inference(
        self,
        openai_messages: list[
            dict[
                Literal["role", "content", "tool_call_id", "name", "tool_calls"],
                Any,
            ]
        ],
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
        if not should_force:
            return super().model_inference(openai_messages, openai_tools)
        with all_logging_disabled():
            return self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=cast(list[ChatCompletionMessageParam], openai_messages),
                tools=openai_tools,
                tool_choice={"type": "function", "function": {"name": forced_tool}},
            )


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
