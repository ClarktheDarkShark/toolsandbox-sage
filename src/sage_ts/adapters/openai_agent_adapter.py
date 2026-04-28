"""Modern OpenAI adapter for SAGE-owned generation calls."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    model: str
    temperature: float = 0.0


class OpenAIChatAdapter:
    model: str

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model or os.environ.get("SAGE_TS_MODEL", "gpt-5-mini") or "gpt-5-mini"
        )
        self.client = OpenAI(base_url="https://api.openai.com/v1")

    def complete(self, request: ChatRequest) -> str:
        model = request.model or self.model
        messages = cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        )
        if model.startswith("gpt-5"):
            response = self.client.chat.completions.create(
                model=model, messages=messages
            )
        else:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
            )
        content = cast(str, response.choices[0].message.content)
        if content is None:
            raise ValueError("OpenAI response had no content")
        return content
