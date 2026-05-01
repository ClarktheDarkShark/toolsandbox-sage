"""Model defaults and comparison metadata for ToolSandbox SAGE runs."""

from __future__ import annotations

from typing import Any

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
