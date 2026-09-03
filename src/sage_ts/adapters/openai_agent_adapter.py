"""Modern OpenAI adapter for SAGE-owned generation calls."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, cast

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam

from sage_ts.config.models import (
    DEFAULT_MODEL,
    reasoning_effort_kwargs,
    resolve_model_name,
    supports_temperature,
)
from sage_ts.config.openai_client import build_robust_openai_client
from sage_ts.evaluation.llm_usage import record_chat_completion_usage


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    model: str
    temperature: float = 0.0
    response_format_json: bool = False


class OpenAIChatAdapter:
    model: str

    def __init__(self, model: str | None = None) -> None:
        self.model = resolve_model_name(model or os.environ.get("SAGE_TS_MODEL"))
        self.client = build_robust_openai_client(
            timeout=_openai_request_timeout_seconds(),
            max_retries=_openai_max_retries(),
        )

    def complete(self, request: ChatRequest) -> str:
        model = resolve_model_name(request.model or self.model or DEFAULT_MODEL)
        messages = cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        )
        completion_args: dict[str, Any] = {"model": model, "messages": messages}
        if supports_temperature(model):
            completion_args["temperature"] = request.temperature
        if request.response_format_json:
            completion_args["response_format"] = {"type": "json_object"}
        completion_args.update(reasoning_effort_kwargs(model))
        response = _with_transient_generation_retries(
            lambda: self.client.chat.completions.create(**completion_args)
        )
        record_chat_completion_usage(
            source="sage_generation",
            model=model,
            messages=messages,
            tools=None,
            response=response,
        )
        content = cast(str, response.choices[0].message.content)
        if content is None:
            raise ValueError("OpenAI response had no content")
        return content


def _openai_request_timeout_seconds() -> float:
    raw = (
        os.environ.get("SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS")
        or os.environ.get("SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS")
        or "90"
    ).strip()
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


def _transient_generation_retry_delays() -> tuple[float, ...]:
    raw = os.environ.get(
        "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS", "1,3"
    ).strip()
    delays: list[float] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            delays.append(max(float(item), 0.0))
        except ValueError:
            return (1.0, 3.0)
    return tuple(delays)


def _with_transient_generation_retries(call: Any) -> Any:
    transient_errors = (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )
    for delay in (*_transient_generation_retry_delays(), None):
        try:
            return call()
        except transient_errors:
            if delay is None:
                raise
            if delay:
                time.sleep(delay)
    raise AssertionError("unreachable")
