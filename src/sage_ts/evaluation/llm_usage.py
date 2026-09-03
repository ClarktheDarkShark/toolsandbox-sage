"""LLM usage accounting for ToolSandbox SAGE runs.

The tracker records OpenAI-reported prompt/completion/total tokens and
provider-cached prompt-prefix tokens for every chat-completion inference path
owned by the ToolSandbox protocol runner: baseline/user simulation calls, SAGE
actor calls, and SAGE-owned generation calls. It stores counts only, not prompt
text. Provider prefix caching is distinct from persistent repository
whole-response replay.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import ChatCompletion

from tool_sandbox.roles.openai_api_agent import OpenAIAPIAgent
from tool_sandbox.roles.openai_api_user import OpenAIAPIUser

_AGENT_PATCH: Any = None
_AGENT_ORIGINAL: Any = None
_USER_PATCH: Any = None
_USER_ORIGINAL: Any = None
_ACTIVE = contextvars.ContextVar("sage_ts_llm_usage_active", default=False)
_ACTIVE_ACTOR_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "sage_ts_actor_request_id", default=None
)
_RUN_DIR: Path | None = None
_RUN_ARM: str | None = None
_EXPECTED_ACTOR_SELECTION_MODE: str | None = None
_EVENTS: list[dict[str, Any]] = []
_SCENARIO_EVENTS: dict[str, list[dict[str, Any]]] = defaultdict(list)
_ACTOR_REQUEST_EVENTS: list[dict[str, Any]] = []
_ACTOR_SCHEMA_CATALOG: dict[str, dict[str, Any]] = {}
_ACTOR_REQUEST_SEQUENCE = 0
_ACTOR_AUDIT_EVENT_FLUSH_COUNTS: dict[str, int] = {}
_ACTOR_AUDIT_SCHEMA_FLUSHED: dict[str, set[str]] = {}
_ACTOR_AUDIT_FINALIZED_TARGETS: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _canonical_payload(value: Any) -> tuple[Any, str]:
    payload = _jsonable(value)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return payload, hashlib.sha256(encoded).hexdigest()


def _schema_catalog_entry(
    *,
    ordered_schemas: Any,
    native_schemas: Any,
    generated_schemas: Any,
    schema_classification: Any,
) -> str:
    entry = {
        "ordered_schemas": _jsonable(ordered_schemas),
        "native_schemas": _jsonable(native_schemas),
        "generated_schemas": _jsonable(generated_schemas),
        "schema_classification": _jsonable(schema_classification),
    }
    _payload, digest = _canonical_payload(entry)
    existing = _ACTOR_SCHEMA_CATALOG.setdefault(digest, entry)
    if existing != entry:
        raise AssertionError("Actor schema-catalog SHA-256 collision")
    return digest


def _validated_schema_bundle(
    *,
    ordered_schemas: Any,
    native_schemas: Any,
    generated_schemas: Any,
    schema_classification: Any,
) -> tuple[Any, Any, Any, Any]:
    ordered_payload = _jsonable(ordered_schemas)
    native_payload = _jsonable(native_schemas)
    generated_payload = _jsonable(generated_schemas)
    classification_payload = _jsonable(schema_classification)
    expected_count = len(ordered_payload) if isinstance(ordered_payload, list) else 0
    if (
        not isinstance(classification_payload, list)
        or len(classification_payload) != expected_count
    ):
        raise AssertionError(
            "Actor request schema classification does not align with sent schemas"
        )
    expected_native: list[Any] = []
    expected_generated: list[Any] = []
    for index, schema in enumerate(ordered_payload or []):
        classification = classification_payload[index]
        if not isinstance(classification, dict):
            raise AssertionError("Actor request schema classification must be mappings")
        if classification.get("schema_index") != index:
            raise AssertionError("Actor request schema classification order drifted")
        kind = classification.get("kind")
        if kind == "native":
            expected_native.append(schema)
        elif kind == "generated":
            expected_generated.append(schema)
        else:
            raise AssertionError(
                f"Actor request schema classification has invalid kind: {kind!r}"
            )
    if native_payload != expected_native or generated_payload != expected_generated:
        raise AssertionError(
            "Actor request native/generated schema partition is not exact"
        )
    return (
        ordered_payload,
        native_payload,
        generated_payload,
        classification_payload,
    )


def _finish_actor_request_audit(
    event: dict[str, Any],
    *,
    messages: Any,
    sent_schemas: Any,
    error: BaseException | None,
) -> None:
    _messages_payload, final_message_sha256 = _canonical_payload(messages)
    _schemas_payload, final_schema_sha256 = _canonical_payload(sent_schemas)
    event["messages_unchanged"] = (
        final_message_sha256 == event["original_messages_sha256"]
    )
    event["sent_schemas_unchanged"] = (
        final_schema_sha256 == event["sent_schemas_sha256"]
    )
    if error is None:
        event["status"] = "complete"
    else:
        event.update(
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
    if event["choice_mode"] == "auto" and error is None:
        if not event["messages_unchanged"]:
            event["status"] = "invariant_failed"
            raise AssertionError("Auto actor inference mutated the original messages")
        if not event["sent_schemas_unchanged"]:
            event["status"] = "invariant_failed"
            raise AssertionError("Auto actor inference mutated the routed tool schemas")


@contextmanager
def audit_actor_request(
    *,
    choice_mode: str,
    model: str,
    messages: Any,
    routed_schemas: Any,
    routed_native_schemas: Any,
    routed_generated_schemas: Any,
    routed_schema_classification: Any,
    sent_schemas: Any,
    sent_native_schemas: Any,
    sent_generated_schemas: Any,
    sent_schema_classification: Any,
    named_tool_choice: str | None,
) -> Iterator[str]:
    """Record and fail closed on actor-request selection invariants.

    Exact schemas are stored once in ``actor_schema_catalog.json`` and each
    request refers to the content-addressed catalog entry. This keeps the
    per-request log complete without copying a large schema bundle on every
    conversational turn.
    """

    if choice_mode not in {"policy", "auto"}:
        raise ValueError(f"Unsupported actor choice mode: {choice_mode!r}")
    if choice_mode == "auto" and named_tool_choice is not None:
        raise AssertionError("Auto actor inference must not use a named tool_choice")

    _messages_payload, original_message_sha256 = _canonical_payload(messages)
    (
        routed_payload,
        routed_native_payload,
        routed_generated_payload,
        routed_classification_payload,
    ) = _validated_schema_bundle(
        ordered_schemas=routed_schemas,
        native_schemas=routed_native_schemas,
        generated_schemas=routed_generated_schemas,
        schema_classification=routed_schema_classification,
    )
    (
        sent_payload,
        sent_native_payload,
        sent_generated_payload,
        sent_classification_payload,
    ) = _validated_schema_bundle(
        ordered_schemas=sent_schemas,
        native_schemas=sent_native_schemas,
        generated_schemas=sent_generated_schemas,
        schema_classification=sent_schema_classification,
    )
    _routed_payload, routed_schema_sha256 = _canonical_payload(routed_payload)
    _sent_payload, sent_schema_sha256 = _canonical_payload(sent_payload)
    schemas_exact = routed_payload == sent_payload
    if choice_mode == "auto" and not schemas_exact:
        raise AssertionError(
            "Auto actor inference must send every routed schema exactly"
        )

    global _ACTOR_REQUEST_SEQUENCE
    _ACTOR_REQUEST_SEQUENCE += 1
    request_id = f"actor-request-{_ACTOR_REQUEST_SEQUENCE:06d}"
    routed_catalog_sha256 = _schema_catalog_entry(
        ordered_schemas=routed_payload,
        native_schemas=routed_native_payload,
        generated_schemas=routed_generated_payload,
        schema_classification=routed_classification_payload,
    )
    sent_catalog_sha256 = _schema_catalog_entry(
        ordered_schemas=sent_payload,
        native_schemas=sent_native_payload,
        generated_schemas=sent_generated_payload,
        schema_classification=sent_classification_payload,
    )
    ordered_agent_names = [
        str(item.get("agent_facing_name") or "") for item in sent_classification_payload
    ]
    ordered_execution_names = [
        str(item.get("execution_facing_name") or "")
        for item in sent_classification_payload
    ]
    routed_agent_names = [
        str(item.get("agent_facing_name") or "")
        for item in routed_classification_payload
    ]
    routed_execution_names = [
        str(item.get("execution_facing_name") or "")
        for item in routed_classification_payload
    ]
    event: dict[str, Any] = {
        "request_id": request_id,
        "created_at": _now(),
        "scenario": _scenario_key(),
        "arm": _arm(),
        "model": model,
        "choice_mode": choice_mode,
        "tool_choice": (
            None
            if named_tool_choice is None
            else {"type": "function", "function": {"name": named_tool_choice}}
        ),
        "named_tool_choice": named_tool_choice,
        "named_tool_choice_absent": named_tool_choice is None,
        "original_messages_sha256": original_message_sha256,
        "routed_schemas_sha256": routed_schema_sha256,
        "sent_schemas_sha256": sent_schema_sha256,
        "schemas_exact": schemas_exact,
        "schema_catalog_sha256": sent_catalog_sha256,
        "routed_schema_catalog_sha256": routed_catalog_sha256,
        "sent_schema_catalog_sha256": sent_catalog_sha256,
        "routed_schema_count": len(routed_payload)
        if isinstance(routed_payload, list)
        else 0,
        "sent_schema_count": len(sent_payload) if isinstance(sent_payload, list) else 0,
        "native_schema_count": len(sent_native_payload or []),
        "generated_schema_count": len(sent_generated_payload or []),
        "routed_ordered_agent_facing_tool_names": routed_agent_names,
        "routed_ordered_execution_facing_tool_names": routed_execution_names,
        "routed_native_agent_facing_tool_names": [
            routed_agent_names[index]
            for index, item in enumerate(routed_classification_payload)
            if item.get("kind") == "native"
        ],
        "routed_native_execution_facing_tool_names": [
            routed_execution_names[index]
            for index, item in enumerate(routed_classification_payload)
            if item.get("kind") == "native"
        ],
        "routed_generated_agent_facing_tool_names": [
            routed_agent_names[index]
            for index, item in enumerate(routed_classification_payload)
            if item.get("kind") == "generated"
        ],
        "routed_generated_execution_facing_tool_names": [
            routed_execution_names[index]
            for index, item in enumerate(routed_classification_payload)
            if item.get("kind") == "generated"
        ],
        "ordered_agent_facing_tool_names": ordered_agent_names,
        "ordered_execution_facing_tool_names": ordered_execution_names,
        "native_agent_facing_tool_names": [
            ordered_agent_names[index]
            for index, item in enumerate(sent_classification_payload)
            if item.get("kind") == "native"
        ],
        "native_execution_facing_tool_names": [
            ordered_execution_names[index]
            for index, item in enumerate(sent_classification_payload)
            if item.get("kind") == "native"
        ],
        "generated_agent_facing_tool_names": [
            ordered_agent_names[index]
            for index, item in enumerate(sent_classification_payload)
            if item.get("kind") == "generated"
        ],
        "generated_execution_facing_tool_names": [
            ordered_execution_names[index]
            for index, item in enumerate(sent_classification_payload)
            if item.get("kind") == "generated"
        ],
        "status": "started",
    }
    _ACTOR_REQUEST_EVENTS.append(event)
    token = _ACTIVE_ACTOR_REQUEST_ID.set(request_id)
    try:
        yield request_id
    except BaseException as exc:
        _finish_actor_request_audit(
            event,
            messages=messages,
            sent_schemas=sent_schemas,
            error=exc,
        )
        raise
    else:
        _finish_actor_request_audit(
            event,
            messages=messages,
            sent_schemas=sent_schemas,
            error=None,
        )
    finally:
        _ACTIVE_ACTOR_REQUEST_ID.reset(token)


def _usage_value(usage: Any, key: str) -> int | None:
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_detail_value(usage: Any, container_key: str, key: str) -> int | None:
    container = getattr(usage, container_key, None)
    if container is None and isinstance(usage, dict):
        container = usage.get(container_key)
    return _usage_value(container, key)


def _usage_payload(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    provider_cached_prompt_tokens = _usage_detail_value(
        usage,
        "prompt_tokens_details",
        "cached_tokens",
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        # This is OpenAI-managed prompt-prefix/KV reuse, not an application
        # response-cache hit. The API still generates a new response.
        "provider_cached_prompt_tokens": provider_cached_prompt_tokens,
        "usage_available": any(
            value is not None
            for value in (prompt_tokens, completion_tokens, total_tokens)
        ),
        "raw_usage": _jsonable(usage) if usage is not None else None,
    }


def _message_count(messages: Any) -> int | None:
    if isinstance(messages, list):
        return len(messages)
    return None


def _tool_count(tools: Any) -> int | None:
    if tools is NOT_GIVEN or isinstance(tools, NotGiven) or tools is None:
        return 0
    if isinstance(tools, list):
        return len(tools)
    try:
        return len(list(cast(Iterable[Any], tools)))
    except TypeError:
        return None


def _scenario_key() -> str:
    return os.environ.get("SAGE_TS_CURRENT_SCENARIO") or "__run__"


def _arm() -> str:
    return _RUN_ARM or os.environ.get("SAGE_TS_RUN_ARM") or "unknown"


def reset_llm_usage(
    *,
    run_dir: Path | None = None,
    arm: str | None = None,
    expected_actor_selection_mode: str | None = None,
) -> None:
    """Reset usage state for a new arm run."""
    global _ACTOR_REQUEST_SEQUENCE, _EXPECTED_ACTOR_SELECTION_MODE, _RUN_DIR, _RUN_ARM
    if expected_actor_selection_mode not in {None, "policy", "auto"}:
        raise ValueError("expected_actor_selection_mode must be policy, auto, or None")
    _RUN_DIR = run_dir
    _RUN_ARM = arm
    _EXPECTED_ACTOR_SELECTION_MODE = expected_actor_selection_mode
    _EVENTS.clear()
    _SCENARIO_EVENTS.clear()
    _ACTOR_REQUEST_EVENTS.clear()
    _ACTOR_SCHEMA_CATALOG.clear()
    _ACTOR_AUDIT_EVENT_FLUSH_COUNTS.clear()
    _ACTOR_AUDIT_SCHEMA_FLUSHED.clear()
    _ACTOR_AUDIT_FINALIZED_TARGETS.clear()
    _ACTOR_REQUEST_SEQUENCE = 0


def record_chat_completion_usage(
    *,
    source: str,
    model: str,
    messages: Any,
    tools: Any = None,
    response: Any,
) -> dict[str, Any]:
    """Record one chat-completion inference result."""
    usage = _usage_payload(response)
    scenario = _scenario_key()
    event = {
        "created_at": _now(),
        "scenario": scenario,
        "arm": _arm(),
        "source": source,
        "model": model,
        "response_cache_status": "live",
        "message_count": _message_count(messages),
        "tool_count": _tool_count(tools),
        **usage,
    }
    actor_request_id = _ACTIVE_ACTOR_REQUEST_ID.get()
    if source == "toolsandbox_agent" and actor_request_id is not None:
        event["actor_request_id"] = actor_request_id
    _EVENTS.append(event)
    _SCENARIO_EVENTS[scenario].append(event)
    return event


def _sum_int(events: list[dict[str, Any]], key: str) -> int | None:
    values = [event.get(key) for event in events if event.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _provider_cached_prompt_tokens(event: dict[str, Any]) -> int | None:
    value = event.get("provider_cached_prompt_tokens")
    if value is None:
        raw_usage = event.get("raw_usage")
        if isinstance(raw_usage, dict):
            details = raw_usage.get("prompt_tokens_details")
            if isinstance(details, dict):
                value = details.get("cached_tokens")
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _provider_cache_summary(
    events: list[dict[str, Any]],
) -> tuple[int | None, int | None, int]:
    values = [
        value
        for event in events
        if (value := _provider_cached_prompt_tokens(event)) is not None
    ]
    if not values:
        return None, None, 0
    return sum(values), sum(1 for value in values if value > 0), len(values)


def _source_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_source[str(event.get("source") or "unknown")].append(event)
    summaries: dict[str, dict[str, Any]] = {}
    for source, rows in sorted(by_source.items()):
        provider_tokens, provider_calls, provider_available = _provider_cache_summary(
            rows
        )
        summaries[source] = {
            "llm_call_count": len(rows),
            "llm_live_call_count": sum(
                1 for row in rows if row.get("response_cache_status") != "hit"
            ),
            "llm_cached_call_count": sum(
                1 for row in rows if row.get("response_cache_status") == "hit"
            ),
            "llm_prompt_tokens": _sum_int(rows, "prompt_tokens"),
            "llm_provider_cached_prompt_tokens": provider_tokens,
            "llm_provider_cached_prompt_call_count": provider_calls,
            "llm_provider_cached_prompt_tokens_available_count": provider_available,
            "llm_completion_tokens": _sum_int(rows, "completion_tokens"),
            "llm_total_tokens": _sum_int(rows, "total_tokens"),
        }
    return summaries


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return row-safe aggregate usage fields."""
    if not events:
        return {
            "llm_usage_recorded": False,
            "llm_call_count": 0,
            "llm_live_call_count": 0,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 0,
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": 0,
            "llm_completion_tokens": 0,
            "llm_total_tokens": 0,
            "llm_usage_available_count": 0,
            "llm_usage_by_source": {},
        }
    provider_tokens, provider_calls, provider_available = _provider_cache_summary(
        events
    )
    return {
        "llm_usage_recorded": True,
        "llm_call_count": len(events),
        "llm_live_call_count": sum(
            1 for event in events if event.get("response_cache_status") != "hit"
        ),
        "llm_cached_call_count": sum(
            1 for event in events if event.get("response_cache_status") == "hit"
        ),
        "llm_prompt_tokens": _sum_int(events, "prompt_tokens"),
        "llm_provider_cached_prompt_tokens": provider_tokens,
        "llm_provider_cached_prompt_call_count": provider_calls,
        "llm_provider_cached_prompt_tokens_available_count": provider_available,
        "llm_completion_tokens": _sum_int(events, "completion_tokens"),
        "llm_total_tokens": _sum_int(events, "total_tokens"),
        "llm_usage_available_count": sum(
            1 for event in events if event.get("usage_available") is True
        ),
        "llm_usage_by_source": _source_summary(events),
    }


def snapshot_scenario_usage(scenario: str) -> dict[str, Any]:
    return summarize_events(list(_SCENARIO_EVENTS.get(scenario, [])))


def clear_scenario_usage(scenario: str) -> None:
    _SCENARIO_EVENTS.pop(scenario, None)


def _flush_incremental_actor_audit(
    target: Path,
    *,
    finalize: bool,
) -> tuple[int, int]:
    target_key = str(target.resolve())
    first_flush = target_key not in _ACTOR_AUDIT_EVENT_FLUSH_COUNTS
    event_path = target / "actor_request_audit.jsonl"
    schema_jsonl_path = target / "actor_schema_catalog.jsonl"
    consolidated_catalog_path = target / "actor_schema_catalog.json"
    if first_flush:
        event_path.write_text("", encoding="utf-8")
        schema_jsonl_path.write_text("", encoding="utf-8")
        consolidated_catalog_path.unlink(missing_ok=True)
        _ACTOR_AUDIT_EVENT_FLUSH_COUNTS[target_key] = 0
        _ACTOR_AUDIT_SCHEMA_FLUSHED[target_key] = set()

    event_start = _ACTOR_AUDIT_EVENT_FLUSH_COUNTS[target_key]
    if event_start > len(_ACTOR_REQUEST_EVENTS):
        raise AssertionError("Actor request incremental event state moved backwards")
    new_events = _ACTOR_REQUEST_EVENTS[event_start:]
    flushed_schema_hashes = _ACTOR_AUDIT_SCHEMA_FLUSHED[target_key]
    new_schema_hashes = sorted(set(_ACTOR_SCHEMA_CATALOG) - flushed_schema_hashes)
    if (new_events or new_schema_hashes) and (
        target_key in _ACTOR_AUDIT_FINALIZED_TARGETS
    ):
        consolidated_catalog_path.unlink(missing_ok=True)
        _ACTOR_AUDIT_FINALIZED_TARGETS.discard(target_key)

    if new_events:
        with event_path.open("a", encoding="utf-8") as handle:
            for event in new_events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        _ACTOR_AUDIT_EVENT_FLUSH_COUNTS[target_key] = len(_ACTOR_REQUEST_EVENTS)
    if new_schema_hashes:
        with schema_jsonl_path.open("a", encoding="utf-8") as handle:
            for digest in new_schema_hashes:
                handle.write(
                    json.dumps(
                        {
                            "schema_catalog_sha256": digest,
                            "bundle": _ACTOR_SCHEMA_CATALOG[digest],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        flushed_schema_hashes.update(new_schema_hashes)

    persisted_event_count = _ACTOR_AUDIT_EVENT_FLUSH_COUNTS[target_key]
    persisted_schema_count = len(flushed_schema_hashes)
    if finalize:
        if persisted_event_count != len(_ACTOR_REQUEST_EVENTS):
            raise AssertionError("Final actor request audit has unflushed events")
        if flushed_schema_hashes != set(_ACTOR_SCHEMA_CATALOG):
            raise AssertionError("Final actor schema catalog has unflushed bundles")
        consolidated_catalog_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "bundles": dict(sorted(_ACTOR_SCHEMA_CATALOG.items())),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _ACTOR_AUDIT_FINALIZED_TARGETS.add(target_key)
    return persisted_event_count, persisted_schema_count


def _write_actor_request_audit_artifacts(
    target: Path,
    *,
    finalize: bool,
) -> None:
    audit_events = list(_ACTOR_REQUEST_EVENTS)
    auto_events = [
        event for event in audit_events if event.get("choice_mode") == "auto"
    ]
    policy_events = [
        event for event in audit_events if event.get("choice_mode") == "policy"
    ]
    complete_ids = {
        str(event["request_id"])
        for event in audit_events
        if event.get("status") == "complete"
    }
    linked_agent_ids = [
        str(event["actor_request_id"])
        for event in _EVENTS
        if event.get("source") == "toolsandbox_agent"
        and event.get("actor_request_id") is not None
    ]
    linked_agent_id_set = set(linked_agent_ids)
    agent_call_count = sum(
        1 for event in _EVENTS if event.get("source") == "toolsandbox_agent"
    )
    unlinked_agent_calls = sum(
        1
        for event in _EVENTS
        if event.get("source") == "toolsandbox_agent"
        and event.get("actor_request_id") is None
    )
    missing_usage_ids = sorted(complete_ids - linked_agent_id_set)
    unexpected_usage_ids = sorted(linked_agent_id_set - complete_ids)
    duplicate_usage_ids = sorted(
        request_id
        for request_id, count in Counter(linked_agent_ids).items()
        if count != 1
    )
    mode_mismatch_ids = sorted(
        str(event.get("request_id"))
        for event in audit_events
        if _EXPECTED_ACTOR_SELECTION_MODE is not None
        and event.get("choice_mode") != _EXPECTED_ACTOR_SELECTION_MODE
    )
    invariant_failures = [
        str(event.get("request_id"))
        for event in audit_events
        if (
            event.get("messages_unchanged") is not True
            or event.get("sent_schemas_unchanged") is not True
            or (
                event.get("choice_mode") == "auto"
                and (
                    event.get("named_tool_choice_absent") is not True
                    or event.get("schemas_exact") is not True
                )
            )
        )
    ]
    coverage_errors = bool(
        (
            agent_call_count
            and not audit_events
            and _EXPECTED_ACTOR_SELECTION_MODE == "auto"
        )
        or (
            audit_events
            and (
                unlinked_agent_calls
                or missing_usage_ids
                or unexpected_usage_ids
                or duplicate_usage_ids
                or mode_mismatch_ids
                or invariant_failures
            )
        )
    )
    persisted_event_count, persisted_schema_count = _flush_incremental_actor_audit(
        target,
        finalize=finalize,
    )
    (target / "actor_request_audit_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "finalized": finalize,
                "expected_actor_selection_mode": _EXPECTED_ACTOR_SELECTION_MODE,
                "request_count": len(audit_events),
                "complete_request_count": len(complete_ids),
                "failed_request_count": sum(
                    1 for event in audit_events if event.get("status") == "failed"
                ),
                "auto_request_count": len(auto_events),
                "complete_auto_request_count": sum(
                    1 for event in auto_events if event.get("status") == "complete"
                ),
                "failed_auto_request_count": sum(
                    1 for event in auto_events if event.get("status") == "failed"
                ),
                "policy_request_count": len(policy_events),
                "complete_policy_request_count": sum(
                    1 for event in policy_events if event.get("status") == "complete"
                ),
                "failed_policy_request_count": sum(
                    1 for event in policy_events if event.get("status") == "failed"
                ),
                "linked_agent_call_count": len(linked_agent_ids),
                "agent_call_count": agent_call_count,
                "unlinked_agent_call_count": unlinked_agent_calls,
                "persisted_event_count": persisted_event_count,
                "schema_catalog_entry_count": len(_ACTOR_SCHEMA_CATALOG),
                "persisted_schema_catalog_entry_count": persisted_schema_count,
                "missing_usage_request_ids": missing_usage_ids,
                "unexpected_usage_request_ids": unexpected_usage_ids,
                "duplicate_usage_request_ids": duplicate_usage_ids,
                "mode_mismatch_request_ids": mode_mismatch_ids,
                "invariant_failure_request_ids": invariant_failures,
                "coverage_verified": bool(audit_events) and not coverage_errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if coverage_errors:
        raise AssertionError(
            "Actor request audit does not cover agent inference calls exactly: "
            f"unlinked={unlinked_agent_calls}, missing={missing_usage_ids}, "
            f"unexpected={unexpected_usage_ids}, duplicates={duplicate_usage_ids}, "
            f"mode_mismatches={mode_mismatch_ids}, "
            f"invariant_failures={invariant_failures}"
        )


def write_llm_usage_artifacts(
    run_dir: Path | None = None,
    *,
    finalize: bool = True,
) -> None:
    target = run_dir or _RUN_DIR
    if target is None:
        return
    target.mkdir(parents=True, exist_ok=True)
    (target / "llm_usage_events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in _EVENTS),
        encoding="utf-8",
    )
    summary = summarize_events(_EVENTS)
    summary["scenario_count_with_usage"] = len(
        {event.get("scenario") for event in _EVENTS if event.get("scenario")}
    )
    summary["schema_version"] = 2
    summary["token_source"] = "openai_chat_completion_usage"
    (target / "llm_usage_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    _write_actor_request_audit_artifacts(target, finalize=finalize)


def _record_unless_nested(
    *,
    source: str,
    model: str,
    messages: Any,
    tools: Any,
    call: Any,
) -> ChatCompletion:
    nested = _ACTIVE.get()
    if nested:
        return cast(ChatCompletion, call())
    token = _ACTIVE.set(True)
    try:
        response = cast(ChatCompletion, call())
    finally:
        _ACTIVE.reset(token)
    record_chat_completion_usage(
        source=source,
        model=model,
        messages=messages,
        tools=tools,
        response=response,
    )
    return response


def install_llm_usage_tracking() -> None:
    """Patch ToolSandbox OpenAI role inference methods for usage capture."""
    global _AGENT_ORIGINAL, _AGENT_PATCH, _USER_ORIGINAL, _USER_PATCH
    current_agent = OpenAIAPIAgent.model_inference
    if current_agent is not _AGENT_PATCH:
        _AGENT_ORIGINAL = current_agent

        def agent_model_inference(
            self: OpenAIAPIAgent,
            openai_messages: list[dict[str, Any]],
            openai_tools: Iterable[dict[str, Any]] | NotGiven,
        ) -> ChatCompletion:
            assert _AGENT_ORIGINAL is not None
            return _record_unless_nested(
                source="toolsandbox_agent",
                model=self.model_name,
                messages=openai_messages,
                tools=openai_tools,
                call=lambda: _AGENT_ORIGINAL(
                    self,
                    openai_messages=openai_messages,
                    openai_tools=openai_tools,
                ),
            )

        _AGENT_PATCH = agent_model_inference
        OpenAIAPIAgent.model_inference = cast(Any, agent_model_inference)  # type: ignore[method-assign]

    current_user = OpenAIAPIUser.model_inference
    if current_user is not _USER_PATCH:
        _USER_ORIGINAL = current_user

        def user_model_inference(
            self: OpenAIAPIUser,
            openai_messages: list[dict[str, Any]],
            openai_tools: Iterable[dict[str, Any]] | NotGiven,
        ) -> ChatCompletion:
            assert _USER_ORIGINAL is not None
            return _record_unless_nested(
                source="toolsandbox_user",
                model=self.model_name,
                messages=openai_messages,
                tools=openai_tools,
                call=lambda: _USER_ORIGINAL(
                    self,
                    openai_messages=openai_messages,
                    openai_tools=openai_tools,
                ),
            )

        _USER_PATCH = user_model_inference
        OpenAIAPIUser.model_inference = cast(Any, user_model_inference)  # type: ignore[method-assign]
