"""Authoritative control-arm baseline cache for unchanged ToolSandbox tasks."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, git_sha
from sage_ts.config.models import paired_model_metadata
from sage_ts.runtime.base_toolset import apply_base_tool_policy
from tool_sandbox.cli import write_result_summary
from tool_sandbox.cli.utils import get_category_summary, resolve_scenarios
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend

CACHE_SCHEMA_VERSION = 1
MIN_COMPATIBLE_RUNS = 3
CACHE_ROOT = Path("artifacts/baselines/control_task_baselines")
DEFAULT_TOOL_BACKEND = ToolBackend("DEFAULT")

COMPATIBILITY_FIELDS = (
    "scenario_key",
    "scenario_checksum",
    "initial_state_checksum",
    "agent_model",
    "user_model",
    "model_version",
    "model_parameters_hash",
    "prompt_hashes",
    "runner_version",
    "scorer_version",
    "toolsandbox_version",
    "manifest_checksum",
    "base_tool_policy",
)
ORDER_INSENSITIVE_LIST_KEYS = frozenset(
    {
        "categories",
        "tool_allow_list",
        "tool_deny_list",
        "tool_augmentation_list",
    }
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "to_dicts"):
        return value.to_dicts()
    return repr(value)


def stable_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=_json_default
    )


def _timestamp_anchor(value: Any) -> float | None:
    timestamps: list[float] = []

    def visit(item: Any, *, key: str | None = None) -> None:
        if isinstance(item, dict):
            for child_key, child_value in item.items():
                visit(child_value, key=str(child_key))
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child)
            return
        if (
            key is not None
            and key.endswith("timestamp")
            and key != "sandbox_message_index"
            and isinstance(item, int | float)
            and item
        ):
            timestamps.append(float(item))

    visit(value)
    return min(timestamps) if timestamps else None


def _canonicalize_for_checksum(
    value: Any,
    *,
    key: str | None = None,
    timestamp_anchor: float | None = None,
) -> Any:
    """Canonicalize semantically unordered fields before compatibility hashing."""
    if isinstance(value, dict):
        return {
            str(item_key): _canonicalize_for_checksum(
                item_value,
                key=str(item_key),
                timestamp_anchor=timestamp_anchor,
            )
            for item_key, item_value in sorted(
                value.items(), key=lambda item: str(item[0])
            )
        }
    if isinstance(value, (list, tuple, set)):
        items = [
            _canonicalize_for_checksum(item, timestamp_anchor=timestamp_anchor)
            for item in value
        ]
        if key in ORDER_INSENSITIVE_LIST_KEYS:
            return sorted(items, key=stable_json)
        return items
    if (
        timestamp_anchor is not None
        and key is not None
        and key.endswith("timestamp")
        and key != "sandbox_message_index"
        and isinstance(value, int | float)
        and value
    ):
        return round(float(value) - timestamp_anchor, 3)
    if hasattr(value, "value"):
        return value.value
    return value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digest(paths: Iterable[str]) -> str:
    h = hashlib.sha256()
    for raw in paths:
        path = Path(raw)
        h.update(raw.encode())
        h.update(b"\0")
        if path.exists():
            h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def toolsandbox_version() -> str:
    try:
        import importlib.metadata as metadata

        return metadata.version("tool-sandbox")
    except Exception:
        return f"local:{git_sha() or 'unknown'}"


def scorer_version() -> str:
    return code_digest(
        [
            "src/sage_ts/evaluation/outcome_score.py",
            "src/sage_ts/evaluation/run_metrics.py",
            "src/sage_ts/adapters/toolsandbox_adapter.py",
        ]
    )


def runner_version() -> str:
    return code_digest(
        [
            "scripts/run_sage_protocol.py",
            "src/sage_ts/adapters/toolsandbox_adapter.py",
            "src/sage_ts/adapters/role_factory.py",
        ]
    )


def prompt_hashes(*, agent: str, user: str) -> dict[str, str]:
    return {
        "agent_role": sha256_text(agent),
        "user_role": sha256_text(user),
        "role_factory": code_digest(["src/sage_ts/adapters/role_factory.py"]),
    }


def model_parameters_hash(*, agent: str, user: str, base_tool_policy: str) -> str:
    return sha256_text(
        stable_json(
            {
                "agent": agent,
                "user": user,
                "base_tool_policy": base_tool_policy,
                "temperature": None,
            }
        )
    )


def scenario_checksum(scenario_key: str, scenario: Scenario) -> str:
    payload = {
        "scenario_key": scenario_key,
        "categories": sorted(str(item) for item in getattr(scenario, "categories", [])),
        "max_messages": getattr(scenario, "max_messages", None),
        "tool_allow_list": _canonicalize_for_checksum(
            getattr(scenario.starting_context, "tool_allow_list", None),
            key="tool_allow_list",
        ),
        "evaluation_type": type(getattr(scenario, "evaluation", None)).__name__,
    }
    return sha256_text(stable_json(payload))


def initial_state_checksum(scenario: Scenario) -> str:
    context = scenario.starting_context.to_dict()
    timestamp_anchor = _timestamp_anchor(context)
    payload = {
        str(key): _canonicalize_for_checksum(
            value,
            key=str(key),
            timestamp_anchor=timestamp_anchor,
        )
        for key, value in context.items()
        if key != "interactive_console"
    }
    return sha256_text(stable_json(payload))


def compatibility_context(
    *,
    scenario_key: str,
    scenario: Scenario,
    agent: str,
    user: str,
    base_tool_policy: str,
    manifest_path: Path,
) -> dict[str, Any]:
    scenario = apply_base_tool_policy(scenario, base_tool_policy)
    models = paired_model_metadata(
        agent_model=agent,
        generation_model=agent,
        user_model=user,
    )
    return {
        "scenario_key": scenario_key,
        "scenario_checksum": scenario_checksum(scenario_key, scenario),
        "initial_state_checksum": initial_state_checksum(scenario),
        "agent_model": agent,
        "user_model": user,
        "model_version": models["comparison_key"],
        "model_parameters_hash": model_parameters_hash(
            agent=agent,
            user=user,
            base_tool_policy=base_tool_policy,
        ),
        "prompt_hashes": prompt_hashes(agent=agent, user=user),
        "runner_version": runner_version(),
        "scorer_version": scorer_version(),
        "toolsandbox_version": toolsandbox_version(),
        "manifest_checksum": sha256_file(manifest_path),
        "base_tool_policy": base_tool_policy,
    }


def compatibility_key(context: dict[str, Any]) -> str:
    return sha256_text(
        stable_json({field: context.get(field) for field in COMPATIBILITY_FIELDS})
    )


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


@dataclass(frozen=True)
class CacheLookup:
    scenario_key: str
    eligible: bool
    reason: str
    row: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    compatible_record_ids: tuple[str, ...] = ()


class ControlBaselineCache:
    def __init__(self, root: Path = CACHE_ROOT) -> None:
        self.root = root
        self.records_dir = root / "records"
        self.manifest_path = root / "cache_manifest.json"
        self.index_path = root / "index.jsonl"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_manifest()

    def _ensure_manifest(self) -> None:
        self.index_path.touch(exist_ok=True)
        if self.manifest_path.exists():
            return
        self.manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "policy": {
                        "min_compatible_completed_runs": MIN_COMPATIBLE_RUNS,
                        "cache_scope": "control_arm_only",
                        "uses_past_scores_before_implementation": False,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def manifest_hash(self) -> str:
        return sha256_file(self.manifest_path) or ""

    def add_record(
        self,
        *,
        context: dict[str, Any],
        result_row: dict[str, Any],
        run_dir: Path,
        manifest_path: Path,
        complete_run: bool = True,
    ) -> dict[str, Any]:
        scenario_key = str(context["scenario_key"])
        exception_type = result_row.get("exception_type")
        side_effect_violations = result_row.get("side_effect_preservation_failures", [])
        trajectory_dir = run_dir / "trajectories" / scenario_key
        transcript = trajectory_dir / "conversation.json"
        transcript_hash = sha256_file(transcript)
        execution_context = trajectory_dir / "execution_context.json"
        execution_context_hash = sha256_file(execution_context)
        final_state_hash_source = (
            "execution_context.json"
            if execution_context_hash is not None
            else "outcome_checks_fallback"
        )
        final_state_hash = execution_context_hash or sha256_text(
            stable_json(result_row.get("outcome_checks", []))
        )
        record_id = sha256_text(
            stable_json(
                {
                    "context": context,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "run_dir": str(run_dir),
                }
            )
        )
        record = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "record_id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "complete_run": bool(complete_run),
            "valid_for_cache": bool(
                complete_run
                and exception_type in {None, ""}
                and not side_effect_violations
            ),
            "compatibility_key": compatibility_key(context),
            **context,
            "manifest_path": str(manifest_path),
            "run_dir": str(run_dir),
            "milestone_scores": result_row.get("milestone_mapping", {}),
            "canonical_score": float(result_row.get("similarity", 0.0) or 0.0),
            "outcome_score": result_row.get("outcome_similarity"),
            "exact_success": float(result_row.get("similarity", 0.0) or 0.0) >= 1.0,
            "final_state_hash": final_state_hash,
            "final_state_hash_source": final_state_hash_source,
            "runtime_exceptions": [] if not exception_type else [exception_type],
            "side_effect_violations": side_effect_violations,
            "turn_count": result_row.get("turn_count"),
            "token_tool_call_model_turn_wall_time": {
                "turn_count": result_row.get("turn_count"),
                "token_count": result_row.get("token_count"),
                "tool_call_count": result_row.get("tool_call_count"),
                "wall_time_seconds": result_row.get("wall_time_seconds"),
            },
            "transcript_path": str(transcript) if transcript.exists() else None,
            "transcript_hash": transcript_hash,
            "result_row": result_row,
        }
        record_path = self.records_dir / f"{record_id}.json"
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "record_id": record_id,
                        "scenario_key": scenario_key,
                        "compatibility_key": record["compatibility_key"],
                        "record_path": str(record_path),
                        "complete_run": record["complete_run"],
                        "valid_for_cache": record["valid_for_cache"],
                        "timestamp": record["timestamp"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return record

    def _index_rows(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def compatible_records(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        key = compatibility_key(context)
        records: list[dict[str, Any]] = []
        for row in self._index_rows():
            if row.get("compatibility_key") != key or not row.get("valid_for_cache"):
                continue
            record = _read_json(Path(str(row["record_path"])), {})
            if record.get("valid_for_cache") and record.get("complete_run"):
                records.append(record)
        return records

    def lookup(self, context: dict[str, Any]) -> CacheLookup:
        records = self.compatible_records(context)
        if len(records) < MIN_COMPATIBLE_RUNS:
            return CacheLookup(
                str(context["scenario_key"]),
                False,
                "fewer_than_3_compatible_completed_controls",
                compatible_record_ids=tuple(
                    str(record.get("record_id")) for record in records
                ),
            )
        canonical = [
            float(record.get("canonical_score", 0.0) or 0.0) for record in records
        ]
        outcome = [
            float(record["outcome_score"])
            for record in records
            if record.get("outcome_score") is not None
        ]
        exact = [1.0 if record.get("exact_success") else 0.0 for record in records]
        base_row = dict(records[-1].get("result_row", {}))
        base_row.update(
            {
                "similarity": sum(canonical) / len(canonical),
                "outcome_similarity": sum(outcome) / len(outcome) if outcome else None,
                "exception_type": None,
                "traceback": None,
                "control_cache": {
                    "source": "cached",
                    "compatible_count": len(records),
                    "canonical_mean": sum(canonical) / len(canonical),
                    "canonical_variance": _variance(canonical),
                    "outcome_mean": sum(outcome) / len(outcome) if outcome else None,
                    "outcome_variance": _variance(outcome),
                    "exact_success_rate": sum(exact) / len(exact),
                    "record_ids": [record["record_id"] for record in records],
                    "cache_manifest_hash": self.manifest_hash(),
                },
            }
        )
        stats = base_row["control_cache"]
        return CacheLookup(
            str(context["scenario_key"]),
            True,
            "eligible",
            row=base_row,
            stats=stats,
            compatible_record_ids=tuple(
                str(record.get("record_id")) for record in records
            ),
        )

    def collect_run(
        self,
        *,
        run_dir: Path,
        config: ToolSandboxRunConfig,
        manifest_path: Path,
    ) -> list[dict[str, Any]]:
        rows_payload = _read_json(run_dir / "result_summary.json", {})
        rows = rows_payload.get("per_scenario_results", [])
        by_name = {str(row.get("name")): row for row in rows if isinstance(row, dict)}
        scenarios = resolve_scenarios(
            desired_scenario_names=list(config.scenario_names),
            preferred_tool_backend=DEFAULT_TOOL_BACKEND,
        )
        records = []
        for name in config.scenario_names:
            if name not in by_name:
                continue
            context = compatibility_context(
                scenario_key=name,
                scenario=scenarios[name],
                agent=config.agent,
                user=config.user,
                base_tool_policy=config.base_tool_policy,
                manifest_path=manifest_path,
            )
            records.append(
                self.add_record(
                    context=context,
                    result_row=by_name[name],
                    run_dir=run_dir,
                    manifest_path=manifest_path,
                    complete_run=True,
                )
            )
        return records


def plan_control_cache(
    *,
    cache: ControlBaselineCache,
    scenario_names: tuple[str, ...],
    agent: str,
    user: str,
    base_tool_policy: str,
    manifest_path: Path,
) -> dict[str, Any]:
    scenarios = resolve_scenarios(
        desired_scenario_names=list(scenario_names),
        preferred_tool_backend=DEFAULT_TOOL_BACKEND,
    )
    lookups: dict[str, CacheLookup] = {}
    contexts: dict[str, dict[str, Any]] = {}
    for name in scenario_names:
        context = compatibility_context(
            scenario_key=name,
            scenario=scenarios[name],
            agent=agent,
            user=user,
            base_tool_policy=base_tool_policy,
            manifest_path=manifest_path,
        )
        contexts[name] = context
        lookups[name] = cache.lookup(context)
    cached = [name for name, lookup in lookups.items() if lookup.eligible]
    fresh = [name for name, lookup in lookups.items() if not lookup.eligible]
    return {
        "contexts": contexts,
        "lookups": lookups,
        "cached_scenarios": cached,
        "fresh_scenarios": fresh,
        "miss_reasons": {name: lookups[name].reason for name in fresh},
    }


def write_synthetic_control_run(
    *,
    output_root: Path,
    run_type: str,
    agent: str,
    user: str,
    scenario_names: tuple[str, ...],
    cached_rows_by_name: dict[str, dict[str, Any]],
    fresh_run_dir: Path | None,
    cache_report: dict[str, Any],
) -> Path:
    output_dir = (
        output_root
        / f"{run_type}_control_cached_agent_{agent}_user_{user}_{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    fresh_rows: dict[str, dict[str, Any]] = {}
    if fresh_run_dir is not None:
        payload = _read_json(fresh_run_dir / "result_summary.json", {})
        fresh_rows = {
            str(row.get("name")): row
            for row in payload.get("per_scenario_results", [])
            if isinstance(row, dict)
        }
        trajectories = fresh_run_dir / "trajectories"
        if trajectories.exists():
            shutil.copytree(
                trajectories, output_dir / "trajectories", dirs_exist_ok=True
            )
    rows: list[dict[str, Any]] = []
    for name in scenario_names:
        if name in cached_rows_by_name:
            row = dict(cached_rows_by_name[name])
            row.setdefault("name", name)
            row["control_cache_source"] = "cached"
            rows.append(row)
        else:
            row = dict(fresh_rows[name])
            row["control_cache_source"] = "fresh"
            row["control_cache"] = {"source": "fresh"}
            rows.append(row)
    write_result_summary(
        result_summary=rows,
        category_summary=get_category_summary(rows),
        output_directory=output_dir,
    )
    manifest_payload = {
        "run_type": f"{run_type}_control_cached",
        "agent": agent,
        "user": user,
        "output_dir": str(output_root),
        "scenario_names": list(scenario_names),
        "control_cache_source": cache_report.get("control_source"),
        "control_cache_manifest_hash": cache_report.get("cache_manifest_hash"),
    }
    for manifest_path in (
        output_root / "sage_ts_run_manifest.json",
        output_dir / "sage_ts_run_manifest.json",
    ):
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2) + "\n",
            encoding="utf-8",
        )
    (output_dir / "live_result_summary.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "completed_count": len(rows),
                "scenario_count": len(rows),
                "per_scenario_results": rows,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "control_cache_report.json").write_text(
        json.dumps(cache_report, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_dir


def build_control_cache_report(
    *,
    mode: str,
    cache: ControlBaselineCache,
    scenario_names: tuple[str, ...],
    cached_scenarios: list[str],
    fresh_scenarios: list[str],
    miss_reasons: dict[str, str],
    lookups: dict[str, CacheLookup],
) -> dict[str, Any]:
    control_source = (
        "cached"
        if cached_scenarios and not fresh_scenarios
        else "fresh"
        if fresh_scenarios and not cached_scenarios
        else "mixed"
        if cached_scenarios and fresh_scenarios
        else "fresh"
    )
    cached_stats = {
        name: lookups[name].stats
        for name in cached_scenarios
        if lookups[name].stats is not None
    }
    estimated_cached_turns = sum(
        int((lookups[name].row or {}).get("turn_count", 0) or 0)
        for name in cached_scenarios
    )
    return {
        "mode": mode,
        "control_source": control_source,
        "cached_control_tasks": len(cached_scenarios),
        "fresh_control_tasks": len(fresh_scenarios),
        "cached_scenarios": cached_scenarios,
        "fresh_scenarios": fresh_scenarios,
        "cache_misses": miss_reasons,
        "cache_manifest_hash": cache.manifest_hash(),
        "baseline_count_and_variance_per_cached_task": cached_stats,
        "estimated_token_time_savings": {
            "cached_tasks_skipped": len(cached_scenarios),
            "cached_control_turns_avoided": estimated_cached_turns,
            "token_savings": None,
            "wall_time_seconds_savings": None,
        },
        "confidence_intervals_account_for_cached_control_variance": bool(
            cached_scenarios
        ),
        "cohort_selection_influenced_by_cache": False,
    }
