"""Configurable OpenAI ToolSandbox roles for current model names."""

from __future__ import annotations

from sage_ts.config.models import resolve_model_name
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser


class ConfigurableOpenAIAgent(OpenAIAPIAgent):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()


class ConfigurableOpenAIUser(OpenAIAPIUser):
    def __init__(self, model_name: str) -> None:
        self.requested_model_name = model_name
        self.model_name = resolve_model_name(model_name)
        super().__init__()
