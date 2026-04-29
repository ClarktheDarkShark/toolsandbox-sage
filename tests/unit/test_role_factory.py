import pytest

from sage_ts.adapters.openai_toolsandbox_roles import (
    ConfigurableOpenAIAgent,
    ConfigurableOpenAIUser,
)
from sage_ts.adapters.role_factory import make_agent, make_user
from tool_sandbox.roles.unhelpful_agent import UnhelpfulAgent


def test_role_factory_preserves_upstream_agent() -> None:
    assert isinstance(make_agent("Unhelpful"), UnhelpfulAgent)


def test_role_factory_supports_current_openai_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    agent = make_agent("gpt-5-mini")
    user = make_user("gpt-5-mini")

    assert isinstance(agent, ConfigurableOpenAIAgent)
    assert isinstance(user, ConfigurableOpenAIUser)
    assert agent.model_name == "gpt-5-mini"
    assert user.model_name == "gpt-5-mini"
