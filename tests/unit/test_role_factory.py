from sage_ts.adapters import role_factory


def test_native_toolsandbox_runtime_uses_exact_upstream_actor(monkeypatch) -> None:
    class FakeNativeAgent:
        model_name = ""

    native_agent = FakeNativeAgent()
    monkeypatch.setattr(role_factory, "OpenAIAPIAgent", lambda: native_agent)

    observed = role_factory.make_agent(
        "gpt-4o-mini",
        runtime=role_factory.TOOL_SANDBOX_NATIVE_AGENT_RUNTIME,
    )

    assert observed is native_agent
    assert observed.model_name == "gpt-4o-mini"


def test_unknown_agent_runtime_is_rejected() -> None:
    try:
        role_factory.make_agent("gpt-4o-mini", runtime="unknown")
    except ValueError as exc:
        assert "Unknown agent runtime" in str(exc)
    else:
        raise AssertionError("Expected invalid runtime to fail closed")
