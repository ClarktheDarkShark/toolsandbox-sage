"""Robust OpenAI client construction hardened against connection-pool stalls.

The gpt-5-mini baseline arm was observed to deadlock indefinitely with ~21
half-closed (CLOSE_WAIT) sockets while the process slept, never honoring the
request timeout. Root cause: reuse of poisoned keepalive connections and a
socket read/pool acquisition that could block without an effective per-phase
timeout. This builder removes both failure modes.
"""

from __future__ import annotations

import httpx
from openai import OpenAI

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _timeout(seconds: float) -> httpx.Timeout:
    # Explicit per-phase timeouts so a hung read or blocked pool acquisition
    # aborts (raising) instead of deadlocking the arm.
    return httpx.Timeout(seconds, connect=15.0, read=seconds, write=seconds, pool=30.0)


def build_robust_openai_client(
    *,
    base_url: str = _DEFAULT_BASE_URL,
    timeout: float,
    max_retries: int,
) -> OpenAI:
    """Return an OpenAI client that will not deadlock on poisoned sockets.

    - ``max_keepalive_connections=0``: every request uses a fresh connection
      that is closed afterward, so a server-closed (CLOSE_WAIT) connection is
      never reused — the observed cause of the baseline-arm stall.
    - Explicit per-phase ``httpx.Timeout`` on both the transport and the client
      so no phase can block indefinitely.
    """
    http_client = httpx.Client(
        timeout=_timeout(timeout),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=0),
    )
    return OpenAI(
        base_url=base_url,
        timeout=_timeout(timeout),
        max_retries=max_retries,
        http_client=http_client,
    )
