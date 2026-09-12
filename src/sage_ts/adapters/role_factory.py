"""Role factory helpers that preserve upstream roles and allow current OpenAI models."""

from __future__ import annotations

from sage_ts.adapters.openai_toolsandbox_roles import (
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
)
from sage_ts.config.models import resolve_model_name
from tool_sandbox.cli.utils import (
    AGENT_TYPE_TO_FACTORY,
    USER_TYPE_TO_FACTORY,
    RoleImplType,
)
from tool_sandbox.roles.base_role import BaseRole
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent

SAGE_WRAPPED_AGENT_RUNTIME = "sage_wrapped"
TOOL_SANDBOX_NATIVE_AGENT_RUNTIME = "toolsandbox_native"
AGENT_RUNTIMES = frozenset(
    {SAGE_WRAPPED_AGENT_RUNTIME, TOOL_SANDBOX_NATIVE_AGENT_RUNTIME}
)


def make_agent(
    agent: str,
    *,
    runtime: str = SAGE_WRAPPED_AGENT_RUNTIME,
) -> BaseRole:
    if runtime not in AGENT_RUNTIMES:
        raise ValueError(
            f"Unknown agent runtime {runtime!r}; expected one of {sorted(AGENT_RUNTIMES)}"
        )
    if runtime == TOOL_SANDBOX_NATIVE_AGENT_RUNTIME:
        # Use ToolSandbox's own actor implementation without overriding respond() or
        # model_inference(). Setting model_name is the only compatibility shim needed
        # because upstream's CLI enum predates gpt-4o-mini.
        native_agent = OpenAIAPIAgent()
        native_agent.model_name = resolve_model_name(agent)
        return native_agent
    try:
        return AGENT_TYPE_TO_FACTORY[RoleImplType(agent)]()
    except ValueError:
        return ConfigurableOpenAIAgent(agent)


def make_user(user: str) -> BaseRole:
    try:
        return USER_TYPE_TO_FACTORY[RoleImplType(user)]()
    except ValueError:
        return ConfigurableOpenAIUser(user)
