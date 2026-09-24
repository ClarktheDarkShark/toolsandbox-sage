from __future__ import annotations

from typing import Any

import pytest

import sage_ts.adapters.role_factory as role_factory

REMOVED_NON_OPENAI_ROLES = (
    "Hermes",
    "Gorilla",
    "Claude_3_Opus",
    "Claude_3_Sonnet",
    "Claude_3_Haiku",
    "Gemini_1_0",
    "Gemini_1_5",
    "Gemini_1_5_Flash",
    "MistralOpenAIServer",
    "Cohere_Command_R",
    "Cohere_Command_R_Plus",
)


@pytest.mark.parametrize("role_name", REMOVED_NON_OPENAI_ROLES)
def test_removed_non_openai_agent_roles_fail_closed(role_name: str) -> None:
    with pytest.raises(ValueError, match="supports only OpenAI"):
        role_factory.make_agent(role_name)


@pytest.mark.parametrize("role_name", REMOVED_NON_OPENAI_ROLES)
def test_removed_non_openai_user_roles_fail_closed(role_name: str) -> None:
    with pytest.raises(ValueError, match="supports only OpenAI"):
        role_factory.make_user(role_name)


def test_current_openai_agent_model_uses_configurable_role(monkeypatch: Any) -> None:
    marker = object()
    monkeypatch.setattr(
        role_factory,
        "ConfigurableOpenAIAgent",
        lambda model: marker if model == "gpt-4o-mini" else None,
    )

    assert role_factory.make_agent("  gpt-4o-mini  ") is marker


def test_current_openai_user_model_uses_configurable_role(monkeypatch: Any) -> None:
    marker = object()
    monkeypatch.setattr(
        role_factory,
        "ConfigurableOpenAIUser",
        lambda model: marker if model == "o3-mini" else None,
    )

    assert role_factory.make_user("o3-mini") is marker


def test_legacy_openai_alias_uses_retained_factory(monkeypatch: Any) -> None:
    marker = object()
    role_type = role_factory.RoleImplType.GPT_4_o_2024_05_13
    monkeypatch.setitem(role_factory.AGENT_TYPE_TO_FACTORY, role_type, lambda: marker)

    assert role_factory.make_agent("GPT_4_o_2024_05_13") is marker


def test_known_role_without_factory_fails_closed() -> None:
    with pytest.raises(ValueError, match="supports only OpenAI"):
        role_factory.make_agent("Deterministic")
