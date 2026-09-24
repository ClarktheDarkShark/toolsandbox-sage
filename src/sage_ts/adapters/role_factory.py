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

_OPENAI_MODEL_PREFIXES = ("gpt-", "o1", "o3", "o4")


def _is_openai_model_name(name: str) -> bool:
    return name.lower().startswith(_OPENAI_MODEL_PREFIXES)


def _unsupported_role(kind: str, name: str) -> ValueError:
    return ValueError(
        f"Unsupported {kind} role/model {name!r}. This release supports only "
        "OpenAI model names beginning with gpt-, o1, o3, or o4, plus the "
        "built-in OpenAI, Cli, and Unhelpful role aliases exposed by the CLI."
    )


def make_agent(agent: str) -> BaseRole:
    agent = agent.strip()
    try:
        role_type = RoleImplType(agent)
    except ValueError:
        if not _is_openai_model_name(agent):
            raise _unsupported_role("agent", agent) from None
        return ConfigurableOpenAIAgent(agent)
    factory = AGENT_TYPE_TO_FACTORY.get(role_type)
    if factory is None:
        raise _unsupported_role("agent", agent)
    return factory()


def make_user(user: str) -> BaseRole:
    user = user.strip()
    try:
        role_type = RoleImplType(user)
    except ValueError:
        if not _is_openai_model_name(user):
            raise _unsupported_role("user", user) from None
        return ConfigurableOpenAIUser(user)
    factory = USER_TYPE_TO_FACTORY.get(role_type)
    if factory is None:
        raise _unsupported_role("user", user)
    return factory()
