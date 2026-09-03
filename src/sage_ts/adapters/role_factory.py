"""Role factory helpers that preserve upstream roles and allow current OpenAI models."""

from __future__ import annotations

from sage_ts.adapters.openai_toolsandbox_roles import (
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
)
from tool_sandbox.cli.utils import (
    AGENT_TYPE_TO_FACTORY,
    USER_TYPE_TO_FACTORY,
    RoleImplType,
)
from tool_sandbox.roles.base_role import BaseRole


def make_agent(agent: str, *, actor_selection_mode: str = "policy") -> BaseRole:
    try:
        role_impl = RoleImplType(agent)
    except ValueError:
        return ConfigurableOpenAIAgent(
            agent,
            actor_selection_mode=actor_selection_mode,
        )
    if actor_selection_mode != "policy":
        raise ValueError(
            "actor_selection_mode='auto' requires a configurable OpenAI model "
            f"name; ToolSandbox role alias {agent!r} does not expose the audited "
            "auto-selection path."
        )
    return AGENT_TYPE_TO_FACTORY[role_impl]()


def make_user(user: str) -> BaseRole:
    try:
        return USER_TYPE_TO_FACTORY[RoleImplType(user)]()
    except ValueError:
        return ConfigurableOpenAIUser(user)
