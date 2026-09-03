#!/usr/bin/env python
"""Build a per-task LLM usage cache from live ToolSandbox run artifacts.

This is an accounting cache only. It records call counts and token totals that
already appear in live result summaries or usage event logs; it does not cache
model responses, prompts, or task answers.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

USAGE_FIELDS = (
    "llm_usage_recorded",
    "llm_call_count",
    "llm_live_call_count",
    "llm_cached_call_count",
    "llm_prompt_tokens",
    "llm_provider_cached_prompt_tokens",
    "llm_provider_cached_prompt_call_count",
    "llm_provider_cached_prompt_tokens_available_count",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_usage_available_count",
    "llm_usage_by_source",
)

BASELINE_CACHE_RECORD_ROOT = Path("artifacts/baselines/control_task_baselines/records")
BASELINE_CACHE_USAGE_RECORD_LIMIT = int(
    os.environ.get("SAGE_BASELINE_USAGE_RECORD_LIMIT", "1")
)
CURRENT_RUN_USAGE_FIELDS = (
    "llm_call_count",
    "llm_live_call_count",
    "llm_cached_call_count",
    "llm_prompt_tokens",
    "llm_provider_cached_prompt_tokens",
    "llm_provider_cached_prompt_call_count",
    "llm_provider_cached_prompt_tokens_available_count",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_usage_available_count",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    for _ in range(3):
        try:
            if not path.is_file():
                return default
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.25)
    return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        temp = Path(handle.name)
    temp.replace(path)


def _latest_arm_dir(run_root: Path, arm: str) -> Path | None:
    arm_root = run_root / arm
    if not arm_root.is_dir():
        return None
    candidates = [path for path in arm_root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _sum_int(rows: list[dict[str, Any]], key: str) -> int:
    total = 0
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values: list[int] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            values.append(int(value))
        except (TypeError, ValueError):
            continue
    return sum(values) if values else None


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


def _event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_source[str(event.get("source") or "unknown")].append(event)
    source_summary: dict[str, dict[str, Any]] = {}
    for source, rows in sorted(by_source.items()):
        provider_tokens, provider_calls, provider_available = _provider_cache_summary(
            rows
        )
        source_summary[source] = {
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
            "models": sorted(
                {str(row.get("model")) for row in rows if row.get("model")}
            ),
        }
    provider_tokens, provider_calls, provider_available = _provider_cache_summary(
        events
    )
    return {
        "llm_usage_recorded": bool(events),
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
        "llm_usage_by_source": source_summary,
    }


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _baseline_cache_usage(control_cache: Any) -> dict[str, Any]:
    if not isinstance(control_cache, dict):
        return {}
    if BASELINE_CACHE_USAGE_RECORD_LIMIT < 0:
        record_ids = control_cache.get("record_ids") or []
        return {
            "cached_baseline_llm_usage_recorded": False,
            "cached_baseline_record_count": len(record_ids)
            if isinstance(record_ids, list)
            else 0,
            "cached_baseline_usage_sampled_record_count": 0,
            "cached_baseline_usage_record_count": 0,
            "cached_baseline_usage_missing_record_count": 0,
            "cached_baseline_usage_skipped": True,
        }
    record_ids = [
        str(record_id)
        for record_id in (control_cache.get("record_ids") or [])
        if record_id
    ]
    sampled_record_ids = (
        record_ids[:BASELINE_CACHE_USAGE_RECORD_LIMIT]
        if BASELINE_CACHE_USAGE_RECORD_LIMIT > 0
        else record_ids
    )
    usage_rows: list[dict[str, Any]] = []
    missing_records = 0
    for record_id in sampled_record_ids:
        usage = _baseline_record_llm_usage(record_id)
        if usage is None:
            missing_records += 1
            continue
        usage_rows.append(usage)
    if not usage_rows:
        return {
            "cached_baseline_llm_usage_recorded": False,
            "cached_baseline_record_count": len(record_ids),
            "cached_baseline_usage_sampled_record_count": len(sampled_record_ids),
            "cached_baseline_usage_record_count": 0,
            "cached_baseline_usage_missing_record_count": missing_records,
        }

    payload: dict[str, Any] = {
        "cached_baseline_llm_usage_recorded": True,
        "cached_baseline_usage_cache_source": "control_task_baseline_records",
        "cached_baseline_record_count": len(record_ids),
        "cached_baseline_usage_sampled_record_count": len(sampled_record_ids),
        "cached_baseline_usage_record_count": len(usage_rows),
        "cached_baseline_usage_missing_record_count": missing_records,
    }
    for field in (
        "llm_call_count",
        "llm_live_call_count",
        "llm_cached_call_count",
        "llm_prompt_tokens",
        "llm_provider_cached_prompt_tokens",
        "llm_provider_cached_prompt_call_count",
        "llm_provider_cached_prompt_tokens_available_count",
        "llm_completion_tokens",
        "llm_total_tokens",
        "llm_usage_available_count",
    ):
        values = _numeric_values(usage_rows, field)
        payload[f"cached_baseline_{field}_mean"] = _mean(values)
        payload[f"cached_baseline_{field}_min"] = min(values) if values else None
        payload[f"cached_baseline_{field}_max"] = max(values) if values else None
    return payload


@lru_cache(maxsize=65536)
def _baseline_record_llm_usage(record_id: str) -> dict[str, Any] | None:
    record_path = BASELINE_CACHE_RECORD_ROOT / f"{record_id}.json"
    record = _read_json(record_path, {})
    if not isinstance(record, dict):
        return None
    usage = record.get("llm_usage")
    return usage if isinstance(usage, dict) and usage else None


def _events_by_scenario(run_dir: Path) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in _read_jsonl(run_dir / "llm_usage_events.jsonl"):
        scenario = str(event.get("scenario") or "")
        if scenario and scenario != "__run__":
            grouped[scenario].append(event)
    return {scenario: _event_summary(events) for scenario, events in grouped.items()}


def _add_current_run_usage(
    usage: dict[str, Any],
    *,
    is_current_run_usage: bool,
) -> dict[str, Any]:
    usage["current_run_llm_usage_recorded"] = bool(
        is_current_run_usage and usage.get("llm_usage_recorded")
    )
    for field in CURRENT_RUN_USAGE_FIELDS:
        usage[f"current_run_{field}"] = (
            usage.get(field, 0) if is_current_run_usage else 0
        )
    return usage


def _usage_from_row(
    row: dict[str, Any],
    fallback: dict[str, Any],
    *,
    arm: str,
) -> dict[str, Any]:
    cached_baseline_usage = _baseline_cache_usage(row.get("control_cache"))
    cached_control_row = (
        arm == "control" and row.get("control_cache_source") == "cached"
    )
    usage = {field: row.get(field) for field in USAGE_FIELDS if field in row}
    has_row_counts = any(
        row.get(field) is not None
        for field in (
            "llm_call_count",
            "llm_prompt_tokens",
            "llm_completion_tokens",
            "llm_total_tokens",
        )
    )
    if has_row_counts:
        usage.setdefault("llm_usage_recorded", bool(row.get("llm_usage_recorded")))
        usage.setdefault("llm_call_count", 0)
        usage.setdefault("llm_live_call_count", 0)
        usage.setdefault("llm_cached_call_count", 0)
        usage.setdefault("llm_prompt_tokens", 0)
        provider_fields = (
            "llm_provider_cached_prompt_tokens",
            "llm_provider_cached_prompt_call_count",
            "llm_provider_cached_prompt_tokens_available_count",
        )
        fallback_reconciles = all(
            _sum_optional_int([row], field) is not None
            and _sum_optional_int([row], field) == _sum_optional_int([fallback], field)
            for field in (
                "llm_call_count",
                "llm_prompt_tokens",
                "llm_completion_tokens",
                "llm_total_tokens",
            )
        )
        current_available = _sum_optional_int(
            [usage],
            "llm_provider_cached_prompt_tokens_available_count",
        )
        fallback_available = _sum_optional_int(
            [fallback],
            "llm_provider_cached_prompt_tokens_available_count",
        )
        fallback_is_at_least_as_complete = (
            fallback_available is not None
            and fallback_available >= (current_available or 0)
            and all(
                usage.get(field) is None or fallback.get(field) is not None
                for field in provider_fields[:2]
            )
        )
        if fallback_reconciles and fallback_is_at_least_as_complete:
            for field in provider_fields:
                usage[field] = fallback.get(field)
        else:
            for field in provider_fields:
                usage.setdefault(field, fallback.get(field))
        usage.setdefault("llm_completion_tokens", 0)
        usage.setdefault("llm_total_tokens", 0)
        usage.setdefault("llm_usage_available_count", 0)
        fallback_sources = fallback.get("llm_usage_by_source")
        if fallback_reconciles and isinstance(fallback_sources, dict):
            current_sources = usage.get("llm_usage_by_source")
            if not isinstance(current_sources, dict):
                current_sources = {}
            merged_sources: dict[str, Any] = {}
            for source, fallback_source in fallback_sources.items():
                if not isinstance(fallback_source, dict):
                    continue
                merged_source = dict(fallback_source)
                current_source = current_sources.get(source)
                if isinstance(current_source, dict):
                    current_source_available = _sum_optional_int(
                        [current_source],
                        "llm_provider_cached_prompt_tokens_available_count",
                    )
                    fallback_source_available = _sum_optional_int(
                        [fallback_source],
                        "llm_provider_cached_prompt_tokens_available_count",
                    )
                    fallback_source_is_at_least_as_complete = (
                        fallback_source_available is not None
                        and fallback_source_available >= (current_source_available or 0)
                        and all(
                            current_source.get(field) is None
                            or fallback_source.get(field) is not None
                            for field in provider_fields[:2]
                        )
                    )
                    if not fallback_source_is_at_least_as_complete:
                        for field in provider_fields:
                            if field in current_source:
                                merged_source[field] = current_source[field]
                merged_sources[str(source)] = merged_source
            usage["llm_usage_by_source"] = dict(sorted(merged_sources.items()))
        else:
            usage.setdefault("llm_usage_by_source", {})
        usage["usage_cache_source"] = (
            "control_task_baseline_result_summary"
            if cached_control_row
            else "live_result_summary"
        )
        usage.update(cached_baseline_usage)
        return _add_current_run_usage(
            usage,
            is_current_run_usage=not cached_control_row,
        )
    usage = dict(fallback)
    usage["usage_cache_source"] = (
        "control_task_baseline_records"
        if cached_baseline_usage.get("cached_baseline_llm_usage_recorded")
        else "llm_usage_events_jsonl"
    )
    usage.update(cached_baseline_usage)
    return _add_current_run_usage(
        usage,
        is_current_run_usage=not cached_control_row
        and bool(fallback.get("llm_usage_recorded")),
    )


def _arm_cache(run_root: Path, arm: str) -> dict[str, Any]:
    run_dir = _latest_arm_dir(run_root, arm)
    if run_dir is None:
        return {
            "run_dir": None,
            "status": "not_started",
            "completed_count": 0,
            "scenario_count": 0,
            "tasks": [],
            "totals": _event_summary([]),
        }
    live = _read_json(run_dir / "live_result_summary.json", {})
    rows = live.get("per_scenario_results", []) if isinstance(live, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    fallback_by_scenario = _events_by_scenario(run_dir)
    tasks: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        scenario = str(row.get("name") or row.get("scenario") or "")
        fallback = fallback_by_scenario.get(scenario, _event_summary([]))
        usage = _usage_from_row(row, fallback, arm=arm)
        tasks.append(
            {
                "arm": arm,
                "task_index": index,
                "scenario": scenario,
                "control_cache_source": row.get("control_cache_source"),
                "status": row.get("status") or "complete",
                "similarity": row.get("similarity"),
                "outcome_similarity": row.get("outcome_similarity"),
                "turn_count": row.get("turn_count"),
                **usage,
            }
        )
    totals = _event_summary([])
    for field in (
        "llm_call_count",
        "llm_live_call_count",
        "llm_cached_call_count",
        "llm_prompt_tokens",
        "llm_provider_cached_prompt_tokens",
        "llm_provider_cached_prompt_call_count",
        "llm_provider_cached_prompt_tokens_available_count",
        "llm_completion_tokens",
        "llm_total_tokens",
        "llm_usage_available_count",
    ):
        totals[field] = (
            _sum_optional_int(tasks, field)
            if field.startswith("llm_provider_cached")
            else _sum_int(tasks, field)
        )
    totals["llm_usage_recorded"] = any(task.get("llm_usage_recorded") for task in tasks)
    for field in CURRENT_RUN_USAGE_FIELDS:
        current_field = f"current_run_{field}"
        totals[current_field] = (
            _sum_optional_int(tasks, current_field)
            if field.startswith("llm_provider_cached")
            else _sum_int(tasks, current_field)
        )
    totals["current_run_llm_usage_recorded"] = any(
        task.get("current_run_llm_usage_recorded") for task in tasks
    )
    totals["scenario_count_with_usage"] = sum(
        1 for task in tasks if task.get("llm_usage_recorded")
    )
    return {
        "run_dir": str(run_dir),
        "status": live.get("status") if isinstance(live, dict) else None,
        "completed_count": len(tasks),
        "scenario_count": live.get("scenario_count")
        if isinstance(live, dict)
        else None,
        "tasks": tasks,
        "totals": totals,
    }


def build_cache(run_root: Path) -> dict[str, Any]:
    arms = {arm: _arm_cache(run_root, arm) for arm in ("control", "candidate")}
    all_tasks = [
        task
        for arm_payload in arms.values()
        for task in arm_payload.get("tasks", [])
        if isinstance(task, dict)
    ]
    totals = _event_summary([])
    for field in (
        "llm_call_count",
        "llm_live_call_count",
        "llm_cached_call_count",
        "llm_prompt_tokens",
        "llm_provider_cached_prompt_tokens",
        "llm_provider_cached_prompt_call_count",
        "llm_provider_cached_prompt_tokens_available_count",
        "llm_completion_tokens",
        "llm_total_tokens",
        "llm_usage_available_count",
    ):
        totals[field] = (
            _sum_optional_int(all_tasks, field)
            if field.startswith("llm_provider_cached")
            else _sum_int(all_tasks, field)
        )
    totals["llm_usage_recorded"] = any(
        task.get("llm_usage_recorded") for task in all_tasks
    )
    for field in CURRENT_RUN_USAGE_FIELDS:
        current_field = f"current_run_{field}"
        totals[current_field] = (
            _sum_optional_int(all_tasks, current_field)
            if field.startswith("llm_provider_cached")
            else _sum_int(all_tasks, current_field)
        )
    totals["current_run_llm_usage_recorded"] = any(
        task.get("current_run_llm_usage_recorded") for task in all_tasks
    )
    totals["scenario_count_with_usage"] = sum(
        1 for task in all_tasks if task.get("llm_usage_recorded")
    )
    return {
        "schema_version": 2,
        "cache_type": "llm_usage_by_task",
        "cache_policy": "write_completed_tasks_immediately_no_minimum_count",
        "token_source": "openai_chat_completion_usage",
        "contains_prompts_or_responses": False,
        "run_root": str(run_root),
        "updated_at": _now(),
        "arms": arms,
        "totals": totals,
    }


def write_cache(run_root: Path, output: Path) -> dict[str, Any]:
    payload = build_cache(run_root)
    _atomic_write_json(output, payload)
    rows = [
        {"run_root": str(run_root), **task}
        for arm_payload in payload["arms"].values()
        for task in arm_payload["tasks"]
    ]
    _atomic_write_jsonl(output.with_suffix(".jsonl"), rows)
    return payload


def _is_finished(payload: dict[str, Any]) -> bool:
    candidate = payload.get("arms", {}).get("candidate", {})
    return candidate.get("status") in {"complete", "stopped_early", "failed"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=20.0)
    parser.add_argument("--until-complete", action="store_true")
    args = parser.parse_args()

    run_root = args.run_root
    output = args.output or (run_root / "llm_usage_task_cache.json")
    while True:
        payload = write_cache(run_root, output)
        control = payload["arms"]["control"]
        candidate = payload["arms"]["candidate"]
        print(
            f"{payload['updated_at']} "
            f"control={control['completed_count']}/{control.get('scenario_count')} "
            f"candidate={candidate['completed_count']}/{candidate.get('scenario_count')} "
            f"calls={payload['totals']['llm_call_count']} "
            f"tokens={payload['totals']['llm_total_tokens']} "
            f"current_run_calls={payload['totals']['current_run_llm_call_count']} "
            f"current_run_tokens={payload['totals']['current_run_llm_total_tokens']} "
            f"cached_calls={payload['totals']['llm_cached_call_count']}",
            flush=True,
        )
        if not args.watch:
            break
        if args.until_complete and _is_finished(payload):
            break
        time.sleep(max(args.interval_seconds, 1.0))


if __name__ == "__main__":
    main()
