"""Modern OpenAI adapter for SAGE-owned generation calls."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from sage_ts.config.models import (
    DEFAULT_MODEL,
    resolve_model_name,
    supports_temperature,
)
from sage_ts.evaluation.llm_usage import record_chat_completion_usage


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    model: str
    temperature: float = 0.0


class OpenAIChatAdapter:
    model: str

    def __init__(self, model: str | None = None) -> None:
        self.model = resolve_model_name(model or os.environ.get("SAGE_TS_MODEL"))
        self.client = OpenAI(
            base_url="https://api.openai.com/v1",
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
        if supports_temperature(model):
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
            )
        else:
            response = self.client.chat.completions.create(
                model=model, messages=messages
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
