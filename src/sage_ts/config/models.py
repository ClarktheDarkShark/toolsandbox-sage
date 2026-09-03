"""Model defaults and comparison metadata for ToolSandbox SAGE runs."""

from __future__ import annotations

import os
from typing import Any

_VALID_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}

DEFAULT_MODEL = "gpt-4o-mini"
LEGACY_MODEL = "gpt-5-mini"

MODEL_METADATA: dict[str, dict[str, Any]] = {
    "gpt-4o-mini": {
        "api_model": "gpt-4o-mini",
        "family": "gpt-4o",
        "context_window": 128000,
        "max_output_tokens": 16384,
        "chat_completions": True,
        "function_calling": True,
        "structured_outputs": True,
        "temperature_supported": True,
    },
    "gpt-5-mini": {
        "api_model": "gpt-5-mini",
        "family": "gpt-5",
        "context_window": 400000,
        "max_output_tokens": 128000,
        "chat_completions": True,
        "function_calling": True,
        "structured_outputs": True,
        "temperature_supported": False,
    },
    "gpt-5": {
        "api_model": "gpt-5",
        "family": "gpt-5",
        "context_window": 400000,
        "max_output_tokens": 128000,
        "chat_completions": True,
        "function_calling": True,
        "structured_outputs": True,
        "temperature_supported": False,
    },
}


def resolve_model_name(model: str | None) -> str:
    """Resolve a requested campaign model name to an OpenAI API model id."""
    requested = (model or DEFAULT_MODEL).strip()
    return requested or DEFAULT_MODEL


def model_metadata(model: str | None) -> dict[str, Any]:
    """Return metadata that should travel with run artifacts."""
    requested = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    resolved = resolve_model_name(requested)
    metadata = dict(MODEL_METADATA.get(resolved, {}))
    metadata.update(
        {
            "requested_model": requested,
            "resolved_model": resolved,
            "known_model": resolved in MODEL_METADATA,
            "comparison_key": resolved,
        }
    )
    return metadata


def paired_model_metadata(
    *, agent_model: str | None, generation_model: str | None, user_model: str | None
) -> dict[str, Any]:
    """Build the model block used to guard cross-run comparisons."""
    agent = model_metadata(agent_model)
    generation = model_metadata(generation_model)
    user = model_metadata(user_model)
    comparison_key = (
        f"agent={agent['comparison_key']}|"
        f"generation={generation['comparison_key']}|"
        f"user={user['comparison_key']}"
    )
    return {
        "agent": agent,
        "generation": generation,
        "user": user,
        "comparison_key": comparison_key,
        "mixed_model_warning": None,
    }


def supports_temperature(model: str | None) -> bool:
    """Whether this model should receive the Chat Completions temperature field."""
    resolved = resolve_model_name(model)
    metadata = MODEL_METADATA.get(resolved)
    if metadata is not None:
        return bool(metadata.get("temperature_supported"))
    return not resolved.startswith("gpt-5")


def _is_gpt5_family(model: str | None) -> bool:
    resolved = resolve_model_name(model)
    metadata = MODEL_METADATA.get(resolved)
    if metadata is not None:
        return metadata.get("family") == "gpt-5"
    return resolved.startswith("gpt-5")


def reasoning_effort(model: str | None) -> str | None:
    """Reasoning effort to pass to gpt-5 family Chat Completions calls.

    Opt-in and gpt-5 only: returns ``None`` (field omitted, API default) unless
    the model is a gpt-5 family model AND ``SAGE_GPT5_REASONING_EFFORT`` is set to
    one of minimal/low/medium/high. This keeps default behavior and every
    non-gpt-5 (e.g. gpt-4o-mini) path unchanged.
    """
    if not _is_gpt5_family(model):
        return None
    value = os.environ.get("SAGE_GPT5_REASONING_EFFORT", "").strip().lower()
    return value if value in _VALID_REASONING_EFFORTS else None


def reasoning_effort_kwargs(model: str | None) -> dict[str, str]:
    """``{"reasoning_effort": <effort>}`` when set for this model, else ``{}``."""
    effort = reasoning_effort(model)
    return {"reasoning_effort": effort} if effort else {}


def user_simulator_reasoning_effort_kwargs(model: str | None) -> dict[str, str]:
    """Reasoning effort for the gpt-5 user-simulator role.

    The user simulator is benchmark infrastructure that must faithfully drive
    multi-turn scenarios; at low effort gpt-5-mini ends conversations early and
    tanks state-dependency tasks. So the user role reads its OWN env
    ``SAGE_GPT5_USER_SIM_REASONING_EFFORT`` and, when unset, keeps the API
    default (medium) even if the agent/generation effort is lowered. gpt-5 only,
    so non-gpt-5 (e.g. gpt-4o-mini) is unaffected.
    """
    if not _is_gpt5_family(model):
        return {}
    value = os.environ.get("SAGE_GPT5_USER_SIM_REASONING_EFFORT", "").strip().lower()
    return {"reasoning_effort": value} if value in _VALID_REASONING_EFFORTS else {}
