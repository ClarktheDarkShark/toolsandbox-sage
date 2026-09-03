"""LLM usage accounting for ToolSandbox SAGE runs.

The tracker records OpenAI-reported prompt/completion/total tokens and
provider-cached prompt-prefix tokens for every chat-completion inference path
owned by the ToolSandbox protocol runner: baseline/user simulation calls, SAGE
actor calls, and SAGE-owned generation calls. It stores counts only, not prompt
text. Provider prefix caching is distinct from persistent repository
whole-response replay.
"""

from __future__ import annotations

import contextvars
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import ChatCompletion

from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

_AGENT_PATCH: Any = None
_AGENT_ORIGINAL: Any = None
_USER_PATCH: Any = None
_USER_ORIGINAL: Any = None
_ACTIVE = contextvars.ContextVar("sage_ts_llm_usage_active", default=False)
_RUN_DIR: Path | None = None
_RUN_ARM: str | None = None
_EVENTS: list[dict[str, Any]] = []
_SCENARIO_EVENTS: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if value is NOT_GIVEN or isinstance(value, NotGiven):
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _usage_value(usage: Any, key: str) -> int | None:
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_detail_value(usage: Any, container_key: str, key: str) -> int | None:
    container = getattr(usage, container_key, None)
    if container is None and isinstance(usage, dict):
        container = usage.get(container_key)
    return _usage_value(container, key)


def _usage_payload(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    provider_cached_prompt_tokens = _usage_detail_value(
        usage,
        "prompt_tokens_details",
        "cached_tokens",
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        # This is OpenAI-managed prompt-prefix/KV reuse, not an application
        # response-cache hit. The API still generates a new response.
        "provider_cached_prompt_tokens": provider_cached_prompt_tokens,
        "usage_available": any(
            value is not None
            for value in (prompt_tokens, completion_tokens, total_tokens)
        ),
        "raw_usage": _jsonable(usage) if usage is not None else None,
    }


def _message_count(messages: Any) -> int | None:
    if isinstance(messages, list):
        return len(messages)
    return None


def _tool_count(tools: Any) -> int | None:
    if tools is NOT_GIVEN or isinstance(tools, NotGiven) or tools is None:
        return 0
    if isinstance(tools, list):
        return len(tools)
    try:
        return len(list(cast(Iterable[Any], tools)))
    except TypeError:
        return None


def _scenario_key() -> str:
    return os.environ.get("SAGE_TS_CURRENT_SCENARIO") or "__run__"


def _arm() -> str:
    return _RUN_ARM or os.environ.get("SAGE_TS_RUN_ARM") or "unknown"


def reset_llm_usage(*, run_dir: Path | None = None, arm: str | None = None) -> None:
    """Reset usage state for a new arm run."""
    global _RUN_DIR, _RUN_ARM
    _RUN_DIR = run_dir
    _RUN_ARM = arm
    _EVENTS.clear()
    _SCENARIO_EVENTS.clear()


def record_chat_completion_usage(
    *,
    source: str,
    model: str,
    messages: Any,
    tools: Any = None,
    response: Any,
) -> dict[str, Any]:
    """Record one chat-completion inference result."""
    usage = _usage_payload(response)
    scenario = _scenario_key()
    event = {
        "created_at": _now(),
        "scenario": scenario,
        "arm": _arm(),
        "source": source,
        "model": model,
        "response_cache_status": "live",
        "message_count": _message_count(messages),
        "tool_count": _tool_count(tools),
        **usage,
    }
    _EVENTS.append(event)
    _SCENARIO_EVENTS[scenario].append(event)
    return event


def _sum_int(events: list[dict[str, Any]], key: str) -> int | None:
    values = [event.get(key) for event in events if event.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _provider_cached_prompt_tokens(event: dict[str, Any]) -> int | None:
    value = event.get("provider_cached_prompt_tokens")
    if value is None:
        raw_usage = event.get("raw_usage")
        if isinstance(raw_usage, dict):
            details = raw_usage.get("prompt_tokens_details")
            if isinstance(details, dict):
                value = details.get("cached_tokens")
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _provider_cache_summary(
    events: list[dict[str, Any]],
) -> tuple[int | None, int | None, int]:
    values = [
        value
        for event in events
        if (value := _provider_cached_prompt_tokens(event)) is not None
    ]
    if not values:
        return None, None, 0
    return sum(values), sum(1 for value in values if value > 0), len(values)


def _source_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_source[str(event.get("source") or "unknown")].append(event)
    summaries: dict[str, dict[str, Any]] = {}
    for source, rows in sorted(by_source.items()):
        provider_tokens, provider_calls, provider_available = _provider_cache_summary(
            rows
        )
        summaries[source] = {
            "llm_call_count": len(rows),
            "llm_live_call_count": sum(
                1 for row in rows if row.get("response_cache_status") != "hit"
            ),
            "llm_cached_call_count": sum(
                1 for row in rows if row.get("response_cache_status") == "hit"
            ),
            "llm_prompt_tokens": _sum_int(rows, "prompt_tokens"),
            "llm_provider_cached_prompt_tokens": provider_tokens,
            "llm_provider_cached_prompt_call_count": provider_calls,
            "llm_provider_cached_prompt_tokens_available_count": provider_available,
            "llm_completion_tokens": _sum_int(rows, "completion_tokens"),
            "llm_total_tokens": _sum_int(rows, "total_tokens"),
        }
    return summaries


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return row-safe aggregate usage fields."""
    if not events:
        return {
            "llm_usage_recorded": False,
            "llm_call_count": 0,
            "llm_live_call_count": 0,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 0,
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": 0,
            "llm_completion_tokens": 0,
            "llm_total_tokens": 0,
            "llm_usage_available_count": 0,
            "llm_usage_by_source": {},
        }
    provider_tokens, provider_calls, provider_available = _provider_cache_summary(
        events
    )
    return {
        "llm_usage_recorded": True,
        "llm_call_count": len(events),
        "llm_live_call_count": sum(
            1 for event in events if event.get("response_cache_status") != "hit"
        ),
        "llm_cached_call_count": sum(
            1 for event in events if event.get("response_cache_status") == "hit"
        ),
        "llm_prompt_tokens": _sum_int(events, "prompt_tokens"),
        "llm_provider_cached_prompt_tokens": provider_tokens,
        "llm_provider_cached_prompt_call_count": provider_calls,
        "llm_provider_cached_prompt_tokens_available_count": provider_available,
        "llm_completion_tokens": _sum_int(events, "completion_tokens"),
        "llm_total_tokens": _sum_int(events, "total_tokens"),
        "llm_usage_available_count": sum(
            1 for event in events if event.get("usage_available") is True
        ),
        "llm_usage_by_source": _source_summary(events),
    }


def snapshot_scenario_usage(scenario: str) -> dict[str, Any]:
    return summarize_events(list(_SCENARIO_EVENTS.get(scenario, [])))


def clear_scenario_usage(scenario: str) -> None:
    _SCENARIO_EVENTS.pop(scenario, None)


def write_llm_usage_artifacts(run_dir: Path | None = None) -> None:
    target = run_dir or _RUN_DIR
    if target is None:
        return
    target.mkdir(parents=True, exist_ok=True)
    (target / "llm_usage_events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in _EVENTS),
        encoding="utf-8",
    )
    summary = summarize_events(_EVENTS)
    summary["scenario_count_with_usage"] = len(
        {event.get("scenario") for event in _EVENTS if event.get("scenario")}
    )
    summary["schema_version"] = 2
    summary["token_source"] = "openai_chat_completion_usage"
    (target / "llm_usage_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def _record_unless_nested(
    *,
    source: str,
    model: str,
    messages: Any,
    tools: Any,
    call: Any,
) -> ChatCompletion:
    nested = _ACTIVE.get()
    if nested:
        return cast(ChatCompletion, call())
    token = _ACTIVE.set(True)
    try:
        response = cast(ChatCompletion, call())
    finally:
        _ACTIVE.reset(token)
    record_chat_completion_usage(
        source=source,
        model=model,
        messages=messages,
        tools=tools,
        response=response,
    )
    return response


def install_llm_usage_tracking() -> None:
    """Patch ToolSandbox OpenAI role inference methods for usage capture."""
    global _AGENT_ORIGINAL, _AGENT_PATCH, _USER_ORIGINAL, _USER_PATCH
    current_agent = OpenAIAPIAgent.model_inference
    if current_agent is not _AGENT_PATCH:
        _AGENT_ORIGINAL = current_agent

        def agent_model_inference(
            self: OpenAIAPIAgent,
            openai_messages: list[dict[str, Any]],
            openai_tools: Iterable[dict[str, Any]] | NotGiven,
        ) -> ChatCompletion:
            assert _AGENT_ORIGINAL is not None
            return _record_unless_nested(
                source="toolsandbox_agent",
                model=self.model_name,
                messages=openai_messages,
                tools=openai_tools,
                call=lambda: _AGENT_ORIGINAL(
                    self,
                    openai_messages=openai_messages,
                    openai_tools=openai_tools,
                ),
            )

        _AGENT_PATCH = agent_model_inference
        OpenAIAPIAgent.model_inference = cast(Any, agent_model_inference)  # type: ignore[method-assign]

    current_user = OpenAIAPIUser.model_inference
    if current_user is not _USER_PATCH:
        _USER_ORIGINAL = current_user

        def user_model_inference(
            self: OpenAIAPIUser,
            openai_messages: list[dict[str, Any]],
            openai_tools: Iterable[dict[str, Any]] | NotGiven,
        ) -> ChatCompletion:
            assert _USER_ORIGINAL is not None
            return _record_unless_nested(
                source="toolsandbox_user",
                model=self.model_name,
                messages=openai_messages,
                tools=openai_tools,
                call=lambda: _USER_ORIGINAL(
                    self,
                    openai_messages=openai_messages,
                    openai_tools=openai_tools,
                ),
            )

        _USER_PATCH = user_model_inference
        OpenAIAPIUser.model_inference = cast(Any, user_model_inference)  # type: ignore[method-assign]
