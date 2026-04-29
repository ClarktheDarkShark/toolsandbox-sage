"""Exact on-disk cache for ToolSandbox OpenAI chat completions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import ChatCompletion

from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent

_ORIGINAL_MODEL_INFERENCE: Any = None
_CACHE_ROOT: Path | None = None
_METRICS: dict[str, int] = {"hits": 0, "misses": 0, "writes": 0}

CONTEXT_ENV_KEYS = (
    "SAGE_TS_MODEL_VERSION",
    "SAGE_TS_REGISTRY_LOCK_DIGEST",
    "SAGE_TS_REGISTRY_DIGEST",
    "SAGE_TS_RETAINED_TOOL_VISIBILITY_DIGEST",
    "SAGE_TS_RUN_CONFIG_DIGEST",
    "SAGE_TS_CURRENT_SCENARIO",
    "SAGE_TS_SCENARIO_ORDER_INDEX",
    "SAGE_TS_GENERATION_SETTINGS_DIGEST",
    "SAGE_TS_PROMPT_POLICY_DIGEST",
    "SAGE_TS_RUN_ARM",
    "SAGE_TS_RUNTIME_DIGEST",
)


def _jsonable(value: Any) -> Any:
    if value is NOT_GIVEN or isinstance(value, NotGiven):
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def digest_value(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_response_cache_context(
    *,
    mode: str,
    arm: str,
    agent: str,
    user: str,
    base_tool_policy: str,
    scenario_names: tuple[str, ...],
    registry_dir: Path | None,
    generation_enabled: bool,
    generation_model: str | None,
    recurrence_threshold: int | None,
    run_config_extra: dict[str, Any] | None = None,
) -> None:
    registry_digest = (
        digest_file(registry_dir / "registry_manifest.json")
        if registry_dir is not None
        else "none"
    )
    os.environ["SAGE_TS_REGISTRY_DIGEST"] = registry_digest
    os.environ["SAGE_TS_REGISTRY_LOCK_DIGEST"] = registry_digest
    os.environ["SAGE_TS_RETAINED_TOOL_VISIBILITY_DIGEST"] = (
        "scenario_relevance_filter_v1"
    )
    run_config = {
        "mode": mode,
        "arm": arm,
        "agent": agent,
        "user": user,
        "base_tool_policy": base_tool_policy,
        "scenario_names": list(scenario_names),
    }
    if run_config_extra:
        run_config.update(run_config_extra)
    os.environ["SAGE_TS_RUN_CONFIG_DIGEST"] = digest_value(run_config)
    os.environ["SAGE_TS_GENERATION_SETTINGS_DIGEST"] = digest_value(
        {
            "generation_enabled": generation_enabled,
            "generation_model": generation_model,
            "recurrence_threshold": recurrence_threshold,
        }
    )
    os.environ["SAGE_TS_PROMPT_POLICY_DIGEST"] = "sage_ts_protocol_v1"
    os.environ["SAGE_TS_RUN_ARM"] = arm
    os.environ["SAGE_TS_RUNTIME_DIGEST"] = digest_value(
        {"tool_sandbox_protocol_runner": "v1", "dashboard_schema": "v1"}
    )


def _normalize_tools(
    openai_tools: Iterable[dict[str, Any]] | NotGiven,
) -> tuple[Any, Iterable[dict[str, Any]] | NotGiven]:
    if openai_tools is NOT_GIVEN or isinstance(openai_tools, NotGiven):
        return None, openai_tools
    if isinstance(openai_tools, list):
        return _jsonable(openai_tools), openai_tools
    tools_list = list(openai_tools)
    return _jsonable(tools_list), tools_list


def _tool_order(normalized_tools: Any) -> list[str]:
    if not isinstance(normalized_tools, list):
        return []
    names: list[str] = []
    for item in normalized_tools:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.append(function["name"])
    return names


def _context_payload() -> dict[str, str]:
    return {key: os.environ.get(key, "") for key in CONTEXT_ENV_KEYS}


def build_response_cache_key(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: Any,
) -> str:
    """Build a strict key that separates tool/schema/registry/run contexts."""
    payload = {
        "model": model,
        "model_version": os.environ.get("SAGE_TS_MODEL_VERSION", ""),
        "messages_digest": digest_value(messages),
        "full_tool_schema_digest": digest_value(tools),
        "tool_order_digest": digest_value(_tool_order(tools)),
        "context": _context_payload(),
    }
    return digest_value(payload)


def _cache_file(cache_key: str) -> Path:
    if _CACHE_ROOT is None:
        raise RuntimeError("OpenAI response cache is not installed")
    shard = _CACHE_ROOT / cache_key[:2]
    shard.mkdir(parents=True, exist_ok=True)
    return shard / f"{cache_key}.json"


def reset_metrics() -> None:
    for key in _METRICS:
        _METRICS[key] = 0


def metrics() -> dict[str, int]:
    return dict(_METRICS)


def write_metrics(path: Path) -> None:
    path.write_text(json.dumps(metrics(), indent=2) + "\n", encoding="utf-8")


def install_openai_response_cache(cache_root: Path) -> None:
    """Patch ToolSandbox OpenAI agents to reuse exact matching responses."""
    global _CACHE_ROOT, _ORIGINAL_MODEL_INFERENCE
    _CACHE_ROOT = cache_root
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    if _ORIGINAL_MODEL_INFERENCE is not None:
        return

    _ORIGINAL_MODEL_INFERENCE = OpenAIAPIAgent.model_inference

    def cached_model_inference(
        self: OpenAIAPIAgent,
        openai_messages: list[dict[str, Any]],
        openai_tools: Iterable[dict[str, Any]] | NotGiven,
    ) -> ChatCompletion:
        normalized_tools, tools_for_call = _normalize_tools(openai_tools)
        cache_key = build_response_cache_key(
            model=self.model_name,
            messages=openai_messages,
            tools=normalized_tools,
        )
        cache_path = _cache_file(cache_key)
        if cache_path.exists():
            _METRICS["hits"] += 1
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return ChatCompletion.model_validate(payload["response"])

        _METRICS["misses"] += 1
        assert _ORIGINAL_MODEL_INFERENCE is not None
        response = cast(
            ChatCompletion,
            _ORIGINAL_MODEL_INFERENCE(
                self,
                openai_messages=openai_messages,
                openai_tools=tools_for_call,
            ),
        )
        cache_path.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "model": self.model_name,
                    "context": _context_payload(),
                    "response": response.model_dump(mode="json"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _METRICS["writes"] += 1
        return response

    OpenAIAPIAgent.model_inference = cast(Any, cached_model_inference)  # type: ignore[method-assign]
