"""Modern OpenAI adapter for SAGE-owned generation calls."""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    model: str
    temperature: float = 0.0


class OpenAIChatAdapter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("SAGE_TS_MODEL", "gpt-5-mini")
        self.client = OpenAI(base_url="https://api.openai.com/v1")

    def complete(self, request: ChatRequest) -> str:
        response = self.client.chat.completions.create(
            model=request.model or self.model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            temperature=request.temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI response had no content")
        return content
