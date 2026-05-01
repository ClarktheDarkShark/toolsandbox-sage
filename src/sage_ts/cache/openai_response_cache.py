"""Exact on-disk cache for ToolSandbox OpenAI chat completions."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import ChatCompletion

from sage_ts.config.models import model_metadata
from sage_ts.runtime.toolsandbox_integration import (
    retained_tool_visibility_policy_digest,
)
from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent

_ORIGINAL_MODEL_INFERENCE: Any = None
_CACHE_ROOT: Path | None = None
_CACHE_MODE = "read_write"
_EVENTS: list[dict[str, Any]] = []
_METRICS: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "writes": 0,
    "live_model_call_count": 0,
    "cached_model_call_count": 0,
}

CACHE_MODES = {"off", "read_write", "read_only", "write_only"}

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
    agent_model = model_metadata(agent)
    generation_model_metadata = (
        model_metadata(generation_model) if generation_model is not None else None
    )
    os.environ["SAGE_TS_MODEL_VERSION"] = str(agent_model["comparison_key"])
    registry_digest = (
        digest_file(registry_dir / "registry_manifest.json")
        if registry_dir is not None
        else "none"
    )
    os.environ["SAGE_TS_REGISTRY_DIGEST"] = registry_digest
    os.environ["SAGE_TS_REGISTRY_LOCK_DIGEST"] = registry_digest
    os.environ["SAGE_TS_RETAINED_TOOL_VISIBILITY_DIGEST"] = (
        retained_tool_visibility_policy_digest()
    )
    run_config = {
        "mode": mode,
        "arm": arm,
        "agent": agent,
        "agent_resolved_model": agent_model["resolved_model"],
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
            "generation_resolved_model": (
                generation_model_metadata["resolved_model"]
                if generation_model_metadata is not None
                else None
            ),
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


def _legacy_cache_file(cache_key: str) -> Path:
    if _CACHE_ROOT is None:
        raise RuntimeError("OpenAI response cache is not installed")
    shard = _CACHE_ROOT / cache_key[:2]
    shard.mkdir(parents=True, exist_ok=True)
    return shard / f"{cache_key}.json"


def _cache_db_path() -> Path:
    if _CACHE_ROOT is None:
        raise RuntimeError("OpenAI response cache is not installed")
    return _CACHE_ROOT / "openai_response_cache.sqlite"


def _connect() -> sqlite3.Connection:
    db_path = _cache_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS responses (
            cache_key TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            context_json TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            cache_mode TEXT NOT NULL
        )
        """
    )
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_event(event: str, cache_key: str) -> None:
    item = {
        "created_at": _now(),
        "event": event,
        "cache_key": cache_key,
        "cache_mode": _CACHE_MODE,
    }
    _EVENTS.append(item)
    if _CACHE_ROOT is None or _CACHE_MODE == "off":
        return
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events(created_at, event, cache_key, cache_mode) VALUES (?, ?, ?, ?)",
            (item["created_at"], event, cache_key, _CACHE_MODE),
        )


def _read_cached_response(cache_key: str) -> dict[str, Any] | None:
    if _CACHE_ROOT is None:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT response_json FROM responses WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    if row is not None:
        return cast(dict[str, Any], json.loads(str(row[0])))

    legacy_path = _legacy_cache_file(cache_key)
    if not legacy_path.exists():
        return None
    payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    response = payload.get("response")
    if not isinstance(response, dict):
        return None
    if _CACHE_MODE in {"read_write"}:
        _write_cached_response(
            cache_key=cache_key,
            model=str(payload.get("model", "")),
            context=cast(dict[str, str], payload.get("context", {})),
            response=response,
            count_metric=False,
        )
    return response


def _write_cached_response(
    *,
    cache_key: str,
    model: str,
    context: dict[str, str],
    response: dict[str, Any],
    count_metric: bool = True,
) -> None:
    if _CACHE_ROOT is None:
        return
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO responses(cache_key, model, context_json, response_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                model,
                stable_json(context),
                stable_json(response),
                _now(),
            ),
        )
    if count_metric:
        _METRICS["writes"] += 1


def reset_metrics() -> None:
    for key in _METRICS:
        _METRICS[key] = 0
    _EVENTS.clear()


def metrics() -> dict[str, Any]:
    return {
        "cache_mode": _CACHE_MODE,
        **dict(_METRICS),
    }


def write_metrics(path: Path) -> None:
    path.write_text(json.dumps(metrics(), indent=2) + "\n", encoding="utf-8")


def write_cache_artifacts(artifact_root: Path) -> None:
    cache_root = artifact_root / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "cache_mode": _CACHE_MODE,
        "cache_root": None if _CACHE_ROOT is None else str(_CACHE_ROOT),
        "sqlite_path": str(cache_root / "openai_response_cache.sqlite"),
        "key_context_env_keys": list(CONTEXT_ENV_KEYS),
        "key_includes": [
            "model",
            "model_version",
            "messages_digest",
            "full_tool_schema_digest",
            "tool_order_digest",
            "registry_lock_digest",
            "registry_digest",
            "retained_tool_visibility_digest",
            "run_config_digest",
            "current_scenario",
            "scenario_order_index",
            "generation_settings_digest",
            "prompt_policy_digest",
            "run_arm",
            "runtime_digest",
        ],
    }
    (cache_root / "cache_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (cache_root / "cache_stats.json").write_text(
        json.dumps(metrics(), indent=2) + "\n", encoding="utf-8"
    )
    (cache_root / "cache_events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in _EVENTS),
        encoding="utf-8",
    )
    if _CACHE_ROOT is not None and _cache_db_path().exists():
        (cache_root / "openai_response_cache.sqlite").write_bytes(
            _cache_db_path().read_bytes()
        )
    else:
        (cache_root / "openai_response_cache.sqlite").touch()


def install_openai_response_cache(
    cache_root: Path,
    *,
    mode: str = "read_write",
) -> None:
    """Patch ToolSandbox OpenAI agents to reuse exact matching responses."""
    global _CACHE_ROOT, _CACHE_MODE, _ORIGINAL_MODEL_INFERENCE
    if mode not in CACHE_MODES:
        raise ValueError(f"Unsupported OpenAI response cache mode: {mode}")
    _CACHE_ROOT = cache_root
    _CACHE_MODE = mode
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    if mode != "off":
        with _connect():
            pass
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
        if _CACHE_MODE in {"read_write", "read_only"}:
            cached_response = _read_cached_response(cache_key)
        else:
            cached_response = None
        if cached_response is not None:
            _METRICS["hits"] += 1
            _METRICS["cached_model_call_count"] += 1
            _record_event("cache_hit", cache_key)
            return ChatCompletion.model_validate(cached_response)

        _METRICS["misses"] += 1
        _METRICS["live_model_call_count"] += 1
        _record_event("cache_miss", cache_key)
        assert _ORIGINAL_MODEL_INFERENCE is not None
        response = cast(
            ChatCompletion,
            _ORIGINAL_MODEL_INFERENCE(
                self,
                openai_messages=openai_messages,
                openai_tools=tools_for_call,
            ),
        )
        if _CACHE_MODE in {"read_write", "write_only"}:
            _write_cached_response(
                cache_key=cache_key,
                model=self.model_name,
                context=_context_payload(),
                response=response.model_dump(mode="json"),
            )
            _record_event("cache_write", cache_key)
        return response

    OpenAIAPIAgent.model_inference = cast(Any, cached_model_inference)  # type: ignore[method-assign]
