"""Online reflection and lifecycle policy for self-evolving SAGE runs.

The controller uses cached control rows as a baseline comparator during a
candidate run. It does not read labels, expected answers, or prior SAGE traces.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sage_ts.evaluation.control_baseline_cache import (
    CACHE_ROOT,
    ControlBaselineCache,
    compatibility_context,
)
from sage_ts.evaluation.task_strata import base_task_family
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.store import RegistryStore
from tool_sandbox.common.scenario import Scenario

REFLECTION_ENABLED_ENV = "SAGE_SELF_EVOLVING_REFLECTION"
REFLECTION_STOP_ENV = "SAGE_SELF_EVOLVING_STOP_IF_OFF_TRACK"
REFLECTION_PULSE_INTERVAL_ENV = "SAGE_SELF_EVOLVING_PULSE_INTERVAL"
REFLECTION_MIN_TASKS_ENV = "SAGE_SELF_EVOLVING_MIN_PULSE_TASKS"
REFLECTION_MIN_SCORE_LIFT_ENV = "SAGE_SELF_EVOLVING_MIN_SCORE_LIFT_PERCENT"
REFLECTION_MIN_OUTCOME_DELTA_ENV = "SAGE_SELF_EVOLVING_MIN_OUTCOME_DELTA"
REFLECTION_CONTROL_CACHE_ROOT_ENV = "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT"


def _env_enabled(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@dataclass
class ToolLifecycleStats:
    visible_count: int = 0
    called_count: int = 0
    attempted_count: int = 0
    failed_count: int = 0
    visible_not_called_count: int = 0
    side_effect_incident_count: int = 0
    called_score_deltas: list[float] = field(default_factory=list)
    called_outcome_deltas: list[float] = field(default_factory=list)
    visible_score_deltas: list[float] = field(default_factory=list)
    visible_outcome_deltas: list[float] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    harmful_called_scenarios: list[str] = field(default_factory=list)
    helpful_called_scenarios: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        called_score_mean = _mean(self.called_score_deltas)
        called_outcome_mean = _mean(self.called_outcome_deltas)
        visible_score_mean = _mean(self.visible_score_deltas)
        visible_outcome_mean = _mean(self.visible_outcome_deltas)
        return {
            "visible_count": self.visible_count,
            "called_count": self.called_count,
            "attempted_count": self.attempted_count,
            "failed_count": self.failed_count,
            "visible_not_called_count": self.visible_not_called_count,
            "side_effect_incident_count": self.side_effect_incident_count,
            "called_score_delta_mean": called_score_mean,
            "called_outcome_delta_mean": called_outcome_mean,
            "visible_score_delta_mean": visible_score_mean,
            "visible_outcome_delta_mean": visible_outcome_mean,
            "harmful_called_count": len(self.harmful_called_scenarios),
            "helpful_called_count": len(self.helpful_called_scenarios),
            "route_repair_families": sorted(
                {
                    base_task_family(scenario)
                    for scenario in self.harmful_called_scenarios
                    if scenario
                }
            ),
            "scenarios": self.scenarios[-20:],
            "harmful_called_scenarios": self.harmful_called_scenarios[-20:],
            "helpful_called_scenarios": self.helpful_called_scenarios[-20:],
        }


@dataclass(frozen=True)
class ReflectionDecision:
    stop_run: bool
    reason: str = ""


@dataclass
class SelfEvolutionReflectionController:
    store: RegistryStore
    output_dir: Path
    agent: str
    user: str
    base_tool_policy: str
    manifest_path: Path
    control_cache: ControlBaselineCache
    pulse_interval: int = 8
    min_pulse_tasks: int = 16
    min_score_lift_percent: float = 8.0
    min_outcome_delta: float = 0.12
    stop_if_off_track: bool = False
    completed_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    score_deltas: list[float] = field(default_factory=list)
    outcome_deltas: list[float] = field(default_factory=list)
    control_scores: list[float] = field(default_factory=list)
    control_outcomes: list[float] = field(default_factory=list)
    runtime_exceptions: int = 0
    side_effect_incidents: int = 0
    tool_stats: dict[str, ToolLifecycleStats] = field(default_factory=dict)
    bucket_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    retired_this_run: set[str] = field(default_factory=set)

    @classmethod
    def from_env(
        cls,
        *,
        store: RegistryStore,
        output_dir: Path,
        agent: str,
        user: str,
        base_tool_policy: str,
        manifest_path: Path,
    ) -> "SelfEvolutionReflectionController | None":
        if not _env_enabled(REFLECTION_ENABLED_ENV):
            return None
        cache_root = Path(
            os.environ.get(REFLECTION_CONTROL_CACHE_ROOT_ENV, "") or CACHE_ROOT
        )
        controller = cls(
            store=store,
            output_dir=output_dir,
            agent=agent,
            user=user,
            base_tool_policy=base_tool_policy,
            manifest_path=manifest_path,
            control_cache=ControlBaselineCache(cache_root),
            pulse_interval=max(1, _env_int(REFLECTION_PULSE_INTERVAL_ENV, 8)),
            min_pulse_tasks=max(1, _env_int(REFLECTION_MIN_TASKS_ENV, 16)),
            min_score_lift_percent=_env_float(
                REFLECTION_MIN_SCORE_LIFT_ENV,
                8.0,
            ),
            min_outcome_delta=_env_float(REFLECTION_MIN_OUTCOME_DELTA_ENV, 0.12),
            stop_if_off_track=_env_enabled(REFLECTION_STOP_ENV),
        )
        controller._hydrate_from_existing_feedback()
        return controller

    def _hydrate_from_existing_feedback(self) -> None:
        """Restore cumulative lifecycle state after a resumable run restart."""
        path = self.output_dir / "self_evolution_task_feedback.jsonl"
        if not path.exists():
            return
        by_scenario: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") != "self_evolution_task_assessed":
                continue
            scenario = row.get("scenario")
            if isinstance(scenario, str) and scenario:
                by_scenario[scenario] = row

        for row in by_scenario.values():
            self._record_feedback_row(row)
        if by_scenario:
            self._write_current_state()

    def _record_feedback_row(self, row: dict[str, Any]) -> None:
        scenario_name = str(row.get("scenario") or "")
        if not scenario_name:
            return

        self.completed_count += 1
        if row.get("control_cache_hit", row.get("control_cache_eligible")):
            self.cache_hit_count += 1
        else:
            self.cache_miss_count += 1

        control_score = _optional_float(row.get("control_score"))
        score_delta = _optional_float(row.get("score_delta"))
        control_outcome = _optional_float(row.get("control_outcome"))
        outcome_delta = _optional_float(row.get("outcome_delta"))
        if score_delta is not None:
            self.score_deltas.append(score_delta)
            if control_score is not None:
                self.control_scores.append(control_score)
        if outcome_delta is not None:
            self.outcome_deltas.append(outcome_delta)
            if control_outcome is not None:
                self.control_outcomes.append(control_outcome)

        if row.get("exception_type"):
            self.runtime_exceptions += 1
        side_effect_failures = [
            str(item)
            for item in (row.get("side_effect_failures") or [])
            if isinstance(item, str)
        ]
        self.side_effect_incidents += len(side_effect_failures)

        family = base_task_family(scenario_name)
        bucket = self.bucket_stats.setdefault(
            family,
            {
                "scenario_count": 0,
                "score_regressions": 0,
                "outcome_regressions": 0,
                "no_visible_helper": 0,
                "no_called_helper": 0,
                "negative_score_mass": 0.0,
                "negative_outcome_mass": 0.0,
            },
        )
        bucket["scenario_count"] += 1
        if score_delta is not None and score_delta < 0:
            bucket["score_regressions"] += 1
            bucket["negative_score_mass"] += abs(score_delta)
        if outcome_delta is not None and outcome_delta < 0:
            bucket["outcome_regressions"] += 1
            bucket["negative_outcome_mass"] += abs(outcome_delta)

        visible = [
            str(item)
            for item in (row.get("generated_tools_visible") or [])
            if isinstance(item, str)
        ]
        called = [
            str(item)
            for item in (row.get("generated_tools_called") or [])
            if isinstance(item, str)
        ]
        attempted = [
            str(item)
            for item in (row.get("generated_tools_attempted") or [])
            if isinstance(item, str)
        ]
        failed = [
            str(item)
            for item in (row.get("generated_tools_failed") or [])
            if isinstance(item, str)
        ]
        if not visible:
            bucket["no_visible_helper"] += 1
        if not called:
            bucket["no_called_helper"] += 1

        for tool_name in sorted(
            set(visible) | set(called) | set(attempted) | set(failed)
        ):
            stats = self.tool_stats.setdefault(tool_name, ToolLifecycleStats())
            if scenario_name not in stats.scenarios:
                stats.scenarios.append(scenario_name)
            if tool_name in visible:
                stats.visible_count += 1
                if score_delta is not None:
                    stats.visible_score_deltas.append(score_delta)
                if outcome_delta is not None:
                    stats.visible_outcome_deltas.append(outcome_delta)
            if tool_name in called:
                stats.called_count += 1
                if score_delta is not None:
                    stats.called_score_deltas.append(score_delta)
                if outcome_delta is not None:
                    stats.called_outcome_deltas.append(outcome_delta)
                if self._is_harmful_call(score_delta, outcome_delta):
                    stats.harmful_called_scenarios.append(scenario_name)
                elif self._is_helpful_call(score_delta, outcome_delta):
                    stats.helpful_called_scenarios.append(scenario_name)
            if tool_name in attempted:
                stats.attempted_count += 1
            if tool_name in failed:
                stats.failed_count += 1
            if tool_name in visible and tool_name not in called:
                stats.visible_not_called_count += 1
            if tool_name in side_effect_failures:
                stats.side_effect_incident_count += 1

    def assess_scenario(
        self,
        *,
        scenario_name: str,
        baseline_scenario: Scenario,
        result: dict[str, Any],
        selection_record: dict[str, Any],
        side_effect_failures: list[str],
    ) -> ReflectionDecision:
        """Record feedback and optionally stop a run at a pulse boundary."""

        lookup = self.control_cache.lookup(
            compatibility_context(
                scenario_key=scenario_name,
                scenario=baseline_scenario,
                agent=self.agent,
                user=self.user,
                base_tool_policy=self.base_tool_policy,
                manifest_path=self.manifest_path,
            )
        )
        control_score = None
        control_outcome = None
        candidate_score = _optional_float(result.get("similarity"))
        candidate_outcome = _optional_float(result.get("outcome_similarity"))
        score_delta = None
        outcome_delta = None
        if lookup.eligible and lookup.row is not None:
            control_score = _optional_float(lookup.row.get("similarity"))
            control_outcome = _optional_float(lookup.row.get("outcome_similarity"))
            if control_score is not None and candidate_score is not None:
                score_delta = candidate_score - control_score
            if control_outcome is not None and candidate_outcome is not None:
                outcome_delta = candidate_outcome - control_outcome

        visible = list(selection_record.get("generated_tools_visible") or [])
        called = list(selection_record.get("generated_tools_called") or [])
        attempted = list(selection_record.get("generated_tools_attempted") or [])
        failed = list(selection_record.get("generated_tools_failed") or [])
        family = base_task_family(scenario_name)

        immediate_actions = self._immediate_lifecycle_actions(
            scenario_name=scenario_name,
            called_tools=called,
            side_effect_failures=side_effect_failures,
            score_delta=score_delta,
            outcome_delta=outcome_delta,
            exception_type=result.get("exception_type"),
        )
        task_feedback = {
            "event": "self_evolution_task_assessed",
            "scenario": scenario_name,
            "base_family": family,
            "completed_count": self.completed_count + 1,
            "control_cache_eligible": lookup.eligible,
            "control_cache_hit": bool(lookup.eligible and lookup.row is not None),
            "control_cache_reason": lookup.reason,
            "control_score": control_score,
            "candidate_score": candidate_score,
            "score_delta": score_delta,
            "control_outcome": control_outcome,
            "candidate_outcome": candidate_outcome,
            "outcome_delta": outcome_delta,
            "generated_tools_visible": visible,
            "generated_tools_called": called,
            "generated_tools_attempted": attempted,
            "generated_tools_failed": failed,
            "side_effect_failures": side_effect_failures,
            "immediate_actions": immediate_actions,
        }
        self._record_feedback_row(task_feedback)
        append_jsonl(
            self.output_dir / "self_evolution_task_feedback.jsonl", task_feedback
        )

        if self.completed_count % self.pulse_interval != 0:
            self._write_current_state()
            return ReflectionDecision(False)
        return self._pulse()

    def _is_harmful_call(
        self,
        score_delta: float | None,
        outcome_delta: float | None,
    ) -> bool:
        if outcome_delta is not None and outcome_delta <= -0.35:
            return True
        return score_delta is not None and score_delta <= -0.50

    def _is_helpful_call(
        self,
        score_delta: float | None,
        outcome_delta: float | None,
    ) -> bool:
        if outcome_delta is not None and outcome_delta >= 0.10:
            return True
        return score_delta is not None and score_delta >= 0.10

    def _retire_tool(
        self, tool_name: str, reason: str, scenario_name: str
    ) -> dict[str, Any]:
        self.store.retire(tool_name)
        self.retired_this_run.add(tool_name)
        action = {
            "tool_name": tool_name,
            "decision": "parked",
            "reason": reason,
            "scenario": scenario_name,
        }
        append_jsonl(self.output_dir / "self_evolution_tool_lifecycle.jsonl", action)
        return action

    def _route_repair_tool(
        self,
        tool_name: str,
        reason: str,
        scenario_name: str,
    ) -> dict[str, Any]:
        action = {
            "tool_name": tool_name,
            "decision": "needs_route_repair",
            "reason": reason,
            "scenario": scenario_name,
        }
        append_jsonl(self.output_dir / "self_evolution_tool_lifecycle.jsonl", action)
        return action

    def _immediate_lifecycle_actions(
        self,
        *,
        scenario_name: str,
        called_tools: list[str],
        side_effect_failures: list[str],
        score_delta: float | None,
        outcome_delta: float | None,
        exception_type: Any,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for tool_name in side_effect_failures:
            actions.append(
                self._retire_tool(
                    tool_name,
                    "side_effect_preservation_failure",
                    scenario_name,
                )
            )
        for tool_name in called_tools:
            if tool_name in self.retired_this_run:
                continue
            if exception_type:
                actions.append(
                    self._retire_tool(
                        tool_name,
                        "runtime_exception_after_generated_tool_call",
                        scenario_name,
                    )
                )
                continue
            if self._is_harmful_call(score_delta, outcome_delta):
                actions.append(
                    self._route_repair_tool(
                        tool_name,
                        "severe_negative_called_delta",
                        scenario_name,
                    )
                )
        return actions

    def _tool_lifecycle_snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for tool_name, stats in sorted(self.tool_stats.items()):
            row = stats.to_json()
            decision = "diagnostic"
            reason = "insufficient_evidence"
            called_outcome = row["called_outcome_delta_mean"]
            called_score = row["called_score_delta_mean"]
            if tool_name in self.retired_this_run:
                decision = "parked"
                reason = "retired_this_run"
            elif stats.side_effect_incident_count:
                decision = "park"
                reason = "side_effect_incident"
            elif stats.harmful_called_scenarios and stats.helpful_called_scenarios:
                decision = "retain_with_route_repair"
                reason = "mixed_called_subset_family_specific_repair"
            elif stats.harmful_called_scenarios:
                decision = "needs_route_repair"
                reason = "harmful_called_subset_without_global_retirement"
            elif stats.called_count >= 2 and (
                (called_outcome is not None and called_outcome > 0.05)
                or (called_score is not None and called_score > 0.05)
            ):
                decision = "retain"
                reason = "positive_called_subset"
            elif stats.called_count >= 2 and (
                (called_outcome is not None and called_outcome < 0)
                and (called_score is None or called_score < 0)
            ):
                decision = "needs_repair"
                reason = "negative_called_subset"
            elif stats.visible_count >= 8 and stats.called_count == 0:
                decision = "adoption_repair"
                reason = "visible_not_called_repeatedly"
            elif stats.called_count == 1 and (
                (called_outcome is not None and called_outcome > 0.05)
                or (called_score is not None and called_score > 0.05)
            ):
                decision = "keep_sparse_positive"
                reason = "single_positive_called_event"
            row["decision"] = decision
            row["decision_reason"] = reason
            snapshot[tool_name] = row
        return snapshot

    def _pulse(self) -> ReflectionDecision:
        score_delta_mean = _mean(self.score_deltas)
        outcome_delta_mean = _mean(self.outcome_deltas)
        control_score_mean = _mean(self.control_scores)
        score_lift_percent = (
            (score_delta_mean / control_score_mean) * 100.0
            if score_delta_mean is not None and control_score_mean
            else None
        )
        on_track = True
        reasons: list[str] = []
        if self.runtime_exceptions:
            on_track = False
            reasons.append("runtime_exceptions_present")
        if self.side_effect_incidents:
            on_track = False
            reasons.append("side_effect_incidents_present")
        if self.completed_count >= self.min_pulse_tasks:
            score_ok = (
                score_lift_percent is not None
                and score_lift_percent >= self.min_score_lift_percent
            )
            outcome_ok = (
                outcome_delta_mean is not None
                and outcome_delta_mean >= self.min_outcome_delta
            )
            if not (score_ok or outcome_ok):
                on_track = False
                reasons.append("pulse_lift_below_threshold")

        pulse = {
            "event": "self_evolution_reflection_pulse",
            "completed_count": self.completed_count,
            "cache_hits": self.cache_hit_count,
            "cache_misses": self.cache_miss_count,
            "score_delta_mean": score_delta_mean,
            "score_lift_percent": score_lift_percent,
            "outcome_delta_mean": outcome_delta_mean,
            "runtime_exceptions": self.runtime_exceptions,
            "side_effect_incidents": self.side_effect_incidents,
            "on_track": on_track,
            "off_track_reasons": reasons,
            "stop_recommended": bool(
                self.stop_if_off_track
                and self.completed_count >= self.min_pulse_tasks
                and not on_track
            ),
            "tool_lifecycle": self._tool_lifecycle_snapshot(),
            "top_gap_buckets": self._top_gap_buckets(),
        }
        append_jsonl(self.output_dir / "self_evolution_reflections.jsonl", pulse)
        self._write_current_state(extra=pulse)
        if pulse["stop_recommended"]:
            return ReflectionDecision(True, ",".join(reasons))
        return ReflectionDecision(False)

    def _top_gap_buckets(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for bucket, stats in self.bucket_stats.items():
            score = (
                float(stats["negative_outcome_mass"]) * 10.0
                + float(stats["negative_score_mass"])
                + float(stats["no_visible_helper"]) * 0.05
                + float(stats["no_called_helper"]) * 0.025
            )
            rows.append({"bucket": bucket, "opportunity_score": score, **stats})
        return sorted(rows, key=lambda row: row["opportunity_score"], reverse=True)[:10]

    def _write_current_state(self, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "artifact_type": "self_evolution_reflection_state",
            "completed_count": self.completed_count,
            "cache_hits": self.cache_hit_count,
            "cache_misses": self.cache_miss_count,
            "score_delta_mean": _mean(self.score_deltas),
            "outcome_delta_mean": _mean(self.outcome_deltas),
            "runtime_exceptions": self.runtime_exceptions,
            "side_effect_incidents": self.side_effect_incidents,
            "tool_lifecycle": self._tool_lifecycle_snapshot(),
            "top_gap_buckets": self._top_gap_buckets(),
        }
        if extra is not None:
            payload["last_pulse"] = extra
        (self.output_dir / "self_evolution_reflection_state.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        registry_state_path = self.store.root / "tool_lifecycle.json"
        registry_state_path.write_text(
            json.dumps(
                {
                    "artifact_type": "self_evolution_tool_lifecycle",
                    "source_run": str(self.output_dir),
                    "tool_lifecycle": payload["tool_lifecycle"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
