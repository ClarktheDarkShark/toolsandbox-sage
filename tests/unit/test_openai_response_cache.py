import pytest
from sage_ts.cache.openai_response_cache import build_response_cache_key


def test_openai_response_cache_key_includes_tool_order() -> None:
    messages = [{"role": "user", "content": "hello"}]
    tools_a = [
        {"type": "function", "function": {"name": "first", "parameters": {}}},
        {"type": "function", "function": {"name": "second", "parameters": {}}},
    ]
    tools_b = list(reversed(tools_a))

    assert build_response_cache_key(
        model="gpt-5-mini", messages=messages, tools=tools_a
    ) != build_response_cache_key(model="gpt-5-mini", messages=messages, tools=tools_b)


def test_openai_response_cache_key_includes_registry_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function", "function": {"name": "helper"}}]

    monkeypatch.setenv("SAGE_TS_REGISTRY_LOCK_DIGEST", "registry-a")
    key_a = build_response_cache_key(
        model="gpt-5-mini",
        messages=messages,
        tools=tools,
    )
    monkeypatch.setenv("SAGE_TS_REGISTRY_LOCK_DIGEST", "registry-b")
    key_b = build_response_cache_key(
        model="gpt-5-mini",
        messages=messages,
        tools=tools,
    )

    assert key_a != key_b
