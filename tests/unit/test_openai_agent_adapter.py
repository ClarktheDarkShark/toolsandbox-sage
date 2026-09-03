from __future__ import annotations

import httpx
from openai import APIConnectionError

from sage_ts.adapters import openai_agent_adapter


def test_generation_retries_transient_connection_failure(monkeypatch) -> None:
    attempts = 0

    def call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise APIConnectionError(
                request=httpx.Request("POST", "https://example.test")
            )
        return "ok"

    monkeypatch.setenv("SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS", "0")

    assert openai_agent_adapter._with_transient_generation_retries(call) == "ok"
    assert attempts == 2


def test_generation_does_not_retry_non_transport_failure(monkeypatch) -> None:
    attempts = 0

    def call() -> str:
        nonlocal attempts
        attempts += 1
        raise ValueError("invalid generated response")

    monkeypatch.setenv("SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS", "0,0")

    try:
        openai_agent_adapter._with_transient_generation_retries(call)
    except ValueError as exc:
        assert str(exc) == "invalid generated response"
    else:
        raise AssertionError("expected ValueError")
    assert attempts == 1
