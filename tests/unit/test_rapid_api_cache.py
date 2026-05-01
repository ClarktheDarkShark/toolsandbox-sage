# mypy: ignore-errors
from __future__ import annotations

from typing import Any

import pytest

import tool_sandbox.tools.rapid_api_search_tools as rapid_tools


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_rapid_api_cache_hit_bypasses_api_key_and_requests(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "rapid_api_cache.json"
    calls: list[dict[str, Any]] = []

    def fake_get(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        return _FakeResponse({"data": {"value": 42}})

    monkeypatch.setattr(rapid_tools, "get_wifi_status", lambda: True)
    monkeypatch.setattr(rapid_tools.requests, "get", fake_get)
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_MODE", "read_write")
    monkeypatch.setenv("RAPID_API_KEY", "test-key")

    first = rapid_tools.rapid_api_get_request(
        url="https://example.p.rapidapi.com/search",
        params={"query": "Apple Park"},
        headers={"X-RapidAPI-Host": "example.p.rapidapi.com"},
    )

    assert first == {"data": {"value": 42}}
    assert len(calls) == 1

    monkeypatch.delenv("RAPID_API_KEY")
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_MODE", "read_only")
    monkeypatch.setattr(
        rapid_tools.requests,
        "get",
        lambda **_: pytest.fail("cache hit should not call requests.get"),
    )

    second = rapid_tools.rapid_api_get_request(
        url="https://example.p.rapidapi.com/search",
        params={"query": "Apple Park"},
        headers={"X-RapidAPI-Host": "example.p.rapidapi.com"},
    )

    assert second == first


def test_currency_converter_host_is_disabled_by_default(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rapid_tools, "get_wifi_status", lambda: True)
    monkeypatch.setattr(
        rapid_tools.requests,
        "get",
        lambda **_: pytest.fail("disabled host should not call requests.get"),
    )
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_MODE", "read_write")
    monkeypatch.setenv("RAPID_API_KEY", "test-key")

    with pytest.raises(PermissionError, match="currency-converter18"):
        rapid_tools.rapid_api_get_request(
            url="https://currency-converter18.p.rapidapi.com/api/v1/convert",
            params={"from": "USD", "to": "CNY", "amount": 2048},
            headers={"X-RapidAPI-Host": "currency-converter18.p.rapidapi.com"},
        )
