"""Online reflection and lifecycle policy for self-evolving SAGE runs.

Publication runs compare against exact same-run live control rows. The legacy
cache comparator remains available only to non-publication callers. Neither
path reads labels, expected answers, or prior SAGE traces.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty
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

REFLECTION_CONTROL_CACHE_ROOT_ENV = "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT"
FRESH_CONTROL_ROW_EVENT = "fresh_control_row"
FRESH_CONTROL_COMPLETE_EVENT = "fresh_control_complete"
FRESH_CONTROL_ERROR_EVENT = "fresh_control_error"
FRESH_CONTROL_WAIT_TIMEOUT_SECONDS = 1800.0


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
    # Canonical deltas remain in artifacts for backward compatibility only.
    # Outcome deltas are the sole quality signal used by lifecycle decisions.
    called_score_deltas: list[float] = field(default_factory=list)
    called_outcome_deltas: list[float] = field(default_factory=list)
    visible_score_deltas: list[float] = field(default_factory=list)
    visible_outcome_deltas: list[float] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    harmful_called_scenarios: list[str] = field(default_factory=list)
    helpful_called_scenarios: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)
    harmful_called_families: list[str] = field(default_factory=list)
    helpful_called_families: list[str] = field(default_factory=list)

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
                {family for family in self.harmful_called_families if family}
            ),
            "task_contexts": self.scenarios[-20:],
            "task_families": self.families[-20:],
            "harmful_called_task_contexts": self.harmful_called_scenarios[-20:],
            "helpful_called_task_contexts": self.helpful_called_scenarios[-20:],
            "harmful_called_families": self.harmful_called_families[-20:],
            "helpful_called_families": self.helpful_called_families[-20:],
            "scenarios": self.scenarios[-20:],
            "harmful_called_scenarios": self.harmful_called_scenarios[-20:],
            "helpful_called_scenarios": self.helpful_called_scenarios[-20:],
        }


@dataclass
class SelfEvolutionReflectionController:
    store: RegistryStore
    output_dir: Path
    agent: str
    user: str
    base_tool_policy: str
    manifest_path: Path
    control_cache: ControlBaselineCache | None
    fresh_control_rows: dict[str, dict[str, Any]] | None = None
    require_fresh_control: bool = False
    fresh_control_channel: Any | None = field(default=None, repr=False)
    fresh_control_stream_complete: bool = field(default=False, init=False)
    fresh_control_consumed: set[str] = field(default_factory=set)
    pulse_interval: int = 4
    min_pulse_tasks: int = 8
    min_score_lift_percent: float = 8.0
    min_outcome_delta: float = 0.12
    completed_count: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    # Report-only compatibility series; never consulted by reflection policy.
    score_deltas: list[float] = field(default_factory=list)
    outcome_deltas: list[float] = field(default_factory=list)
    control_scores: list[float] = field(default_factory=list)
    control_outcomes: list[float] = field(default_factory=list)
    runtime_exceptions: int = 0
    side_effect_incidents: int = 0
    tool_stats: dict[str, ToolLifecycleStats] = field(default_factory=dict)
    bucket_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    retired_this_run: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if (
            self.fresh_control_rows is not None
            and self.fresh_control_channel is not None
        ):
            raise ValueError(
                "Strict fresh-control reflection accepts either completed rows or "
                "a streaming channel, not both."
            )
        if self.fresh_control_channel is not None and not self.require_fresh_control:
            raise ValueError(
                "A fresh-control streaming channel requires strict fresh-control "
                "reflection."
            )
        if (
            self.require_fresh_control
            and self.fresh_control_rows is None
            and self.fresh_control_channel is None
        ):
            raise ValueError(
                "Strict fresh-control reflection requires same-run control rows or "
                "a streaming channel."
            )
        if self.fresh_control_channel is not None:
            self.fresh_control_rows = {}

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
        fresh_control_rows: dict[str, dict[str, Any]] | None = None,
        require_fresh_control: bool = False,
        fresh_control_channel: Any | None = None,
    ) -> "SelfEvolutionReflectionController":
        if fresh_control_rows is not None and fresh_control_channel is not None:
            raise ValueError(
                "Strict fresh-control reflection accepts either completed rows or "
                "a streaming channel, not both."
            )
        if fresh_control_channel is not None and not require_fresh_control:
            raise ValueError(
                "A fresh-control streaming channel requires strict fresh-control "
                "reflection."
            )
        if (
            require_fresh_control
            and fresh_control_rows is None
            and fresh_control_channel is None
        ):
            raise ValueError(
                "Strict fresh-control reflection requires same-run control rows or "
                "a streaming channel."
            )
        control_cache: ControlBaselineCache | None = None
        if not require_fresh_control:
            cache_root = Path(
                os.environ.get(REFLECTION_CONTROL_CACHE_ROOT_ENV, "") or CACHE_ROOT
            )
            control_cache = ControlBaselineCache(cache_root)
        controller = cls(
            store=store,
            output_dir=output_dir,
            agent=agent,
            user=user,
            base_tool_policy=base_tool_policy,
            manifest_path=manifest_path,
            control_cache=control_cache,
            fresh_control_rows=(
                {name: dict(row) for name, row in fresh_control_rows.items()}
                if fresh_control_rows is not None
                else None
            ),
            require_fresh_control=require_fresh_control,
            fresh_control_channel=fresh_control_channel,
            pulse_interval=4,
            min_pulse_tasks=8,
            min_score_lift_percent=8.0,
            min_outcome_delta=0.12,
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
            self._consume_resumed_fresh_control(row)
            self._record_feedback_row(row)
        if by_scenario:
            self._write_current_state()

    def _consume_resumed_fresh_control(self, feedback: dict[str, Any]) -> None:
        if not self.require_fresh_control:
            return
        scenario_name = str(feedback.get("scenario") or "")
        row = self._fresh_control_row(scenario_name, consume=False)
        if feedback.get("control_source") != "same_run_fresh":
            raise ValueError(
                "Cannot resume strict fresh-control reflection from feedback "
                f"without same-run provenance: {scenario_name!r}."
            )
        expected_outcome = _optional_float(row.get("outcome_similarity"))
        if _optional_float(feedback.get("control_outcome")) != expected_outcome:
            raise ValueError(
                f"Resumed fresh control outcome changed for {scenario_name!r}."
            )
        self.fresh_control_consumed.add(scenario_name)

    def _fresh_control_row(
        self,
        scenario_name: str,
        *,
        consume: bool = True,
    ) -> dict[str, Any]:
        if self.fresh_control_rows is None:
            raise ValueError("Same-run fresh control rows are not configured.")
        if (
            scenario_name
            and scenario_name not in self.fresh_control_rows
            and self.fresh_control_channel is not None
        ):
            self._consume_streamed_control_message(expected_scenario=scenario_name)
        if not scenario_name or scenario_name not in self.fresh_control_rows:
            raise ValueError(
                f"Missing same-run fresh control observation for {scenario_name!r}."
            )
        if consume and scenario_name in self.fresh_control_consumed:
            raise ValueError(
                f"Duplicate same-run fresh control use for {scenario_name!r}."
            )
        row = self.fresh_control_rows[scenario_name]
        if str(row.get("name") or "") != scenario_name:
            raise ValueError(
                f"Mismatched same-run fresh control observation for {scenario_name!r}."
            )
        if consume:
            self.fresh_control_consumed.add(scenario_name)
        return row

    def _consume_streamed_control_message(
        self,
        *,
        expected_scenario: str | None,
    ) -> None:
        if self.fresh_control_channel is None:
            raise ValueError("Same-run fresh control streaming is not configured.")
        if self.fresh_control_stream_complete:
            if expected_scenario is None:
                return
            raise ValueError(
                "Missing streamed same-run fresh control observation for "
                f"{expected_scenario!r}; the control stream is already complete."
            )
        try:
            message = self.fresh_control_channel.get(
                timeout=FRESH_CONTROL_WAIT_TIMEOUT_SECONDS
            )
        except Empty as exc:
            awaited = (
                repr(expected_scenario)
                if expected_scenario is not None
                else "the completion marker"
            )
            raise ValueError(
                f"Timed out waiting for streamed same-run fresh control for {awaited}."
            ) from exc
        except (EOFError, OSError) as exc:
            raise ValueError(
                "Same-run fresh control stream failed before completion."
            ) from exc
        if not isinstance(message, dict):
            raise ValueError(
                "Same-run fresh control stream emitted a non-object message."
            )

        event = message.get("event")
        if event == FRESH_CONTROL_ERROR_EVENT:
            detail = str(message.get("error") or "unknown control-arm failure")
            raise ValueError(f"Same-run fresh control producer failed: {detail}")
        if event == FRESH_CONTROL_COMPLETE_EVENT:
            self.fresh_control_stream_complete = True
            if expected_scenario is not None:
                raise ValueError(
                    "Missing streamed same-run fresh control observation for "
                    f"{expected_scenario!r}; the control stream completed first."
                )
            return
        if event != FRESH_CONTROL_ROW_EVENT:
            raise ValueError(
                f"Same-run fresh control stream emitted unknown event {event!r}."
            )

        scenario_name = message.get("scenario")
        row = message.get("row")
        if not isinstance(scenario_name, str) or not scenario_name:
            raise ValueError(
                "Streamed same-run fresh control row has no scenario name."
            )
        if not isinstance(row, dict):
            raise ValueError(
                f"Streamed same-run fresh control row for {scenario_name!r} is invalid."
            )
        if str(row.get("name") or "") != scenario_name:
            raise ValueError(
                "Streamed same-run fresh control message and result row disagree for "
                f"{scenario_name!r}."
            )
        cache_source = str(row.get("control_cache_source") or "").strip().lower()
        cache_detail = row.get("control_cache")
        if cache_source and cache_source != "fresh":
            raise ValueError(
                f"Streamed control row for {scenario_name!r} is cache sourced."
            )
        if isinstance(cache_detail, dict) and (
            str(cache_detail.get("source") or "").strip().lower() == "cached"
            or bool(cache_detail.get("record_ids"))
        ):
            raise ValueError(
                f"Streamed control row for {scenario_name!r} contains cached data."
            )
        if "llm_cached_call_count" not in row:
            raise ValueError(
                f"Streamed control row for {scenario_name!r} lacks response-replay "
                "provenance."
            )
        try:
            cached_call_count = int(row["llm_cached_call_count"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Streamed control row for {scenario_name!r} has invalid "
                "response-replay provenance."
            ) from exc
        if cached_call_count:
            raise ValueError(
                f"Streamed control row for {scenario_name!r} contains repository "
                "whole-response replay."
            )
        if scenario_name in (self.fresh_control_rows or {}):
            raise ValueError(
                f"Duplicate streamed same-run fresh control for {scenario_name!r}."
            )
        if expected_scenario is None:
            raise ValueError(
                "Unexpected streamed same-run fresh control row after the candidate "
                f"cohort: {scenario_name!r}."
            )
        if scenario_name != expected_scenario:
            raise ValueError(
                "Out-of-order streamed same-run fresh control: expected "
                f"{expected_scenario!r}, observed {scenario_name!r}."
            )
        if self.fresh_control_rows is None:
            raise AssertionError(
                "Fresh-control stream row storage was not initialized."
            )
        self.fresh_control_rows[scenario_name] = dict(row)

    def assert_fresh_control_complete(
        self,
        expected_scenarios: tuple[str, ...],
    ) -> None:
        """Fail closed unless reflection consumed one fresh row per candidate task."""
        if not self.require_fresh_control:
            return
        if (
            self.fresh_control_channel is not None
            and not self.fresh_control_stream_complete
        ):
            self._consume_streamed_control_message(expected_scenario=None)
        expected = set(expected_scenarios)
        available = set(self.fresh_control_rows or {})
        consumed = set(self.fresh_control_consumed)
        if len(expected) != len(expected_scenarios):
            raise ValueError("Candidate scenario list contains duplicate task names.")
        if available != expected:
            raise ValueError(
                "Same-run fresh control map does not exactly match the candidate "
                f"cohort (missing={sorted(expected - available)!r}, "
                f"extra={sorted(available - expected)!r})."
            )
        if consumed != expected:
            raise ValueError(
                "Reflection did not consume exactly one same-run fresh control per "
                f"candidate task (missing={sorted(expected - consumed)!r}, "
                f"extra={sorted(consumed - expected)!r})."
            )

    def _record_feedback_row(self, row: dict[str, Any]) -> None:
        scenario_name = str(row.get("scenario") or "")
        if not scenario_name:
            return
        task_context_label = str(row.get("task_context_label") or scenario_name)
        task_family_key = str(
            row.get("task_family_key") or base_task_family(scenario_name)
        )

        self.completed_count += 1
        if row.get("control_cache_hit", row.get("control_cache_eligible")):
            self.cache_hit_count += 1
        else:
            self.cache_miss_count += 1

        control_score = _optional_float(row.get("control_score"))
        score_delta = _optional_float(row.get("score_delta"))
        control_outcome = _optional_float(row.get("control_outcome"))
        candidate_outcome = _optional_float(row.get("candidate_outcome"))
        outcome_delta = _optional_float(row.get("outcome_delta"))
        if (
            control_outcome is None
            or candidate_outcome is None
            or outcome_delta is None
        ):
            raise ValueError(
                "Outcome-only reflection requires non-null matched control and "
                f"candidate outcomes for {scenario_name!r}."
            )
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

        family = task_family_key
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
            if task_context_label not in stats.scenarios:
                stats.scenarios.append(task_context_label)
            if family not in stats.families:
                stats.families.append(family)
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
                if self._is_harmful_call(outcome_delta):
                    stats.harmful_called_scenarios.append(task_context_label)
                    stats.harmful_called_families.append(family)
                elif self._is_helpful_call(outcome_delta):
                    stats.helpful_called_scenarios.append(task_context_label)
                    stats.helpful_called_families.append(family)
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
        task_context_label: str | None = None,
        task_family_key: str | None = None,
    ) -> None:
        """Record feedback and update lifecycle state at pulse boundaries."""

        if self.require_fresh_control:
            control_row = self._fresh_control_row(scenario_name)
            control_source = "same_run_fresh"
            control_available = True
            control_reason = "exact_same_run_task_match"
        else:
            if self.control_cache is None:
                raise ValueError("Legacy reflection requires a control baseline cache.")
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
            control_row = lookup.row
            control_source = "legacy_control_cache"
            control_available = bool(lookup.eligible and lookup.row is not None)
            control_reason = lookup.reason
        control_score = None
        control_outcome = None
        candidate_score = _optional_float(result.get("similarity"))
        candidate_outcome = _optional_float(result.get("outcome_similarity"))
        score_delta = None
        outcome_delta = None
        if control_available and control_row is not None:
            control_score = _optional_float(control_row.get("similarity"))
            control_outcome = _optional_float(control_row.get("outcome_similarity"))
            if control_score is not None and candidate_score is not None:
                score_delta = candidate_score - control_score
            if control_outcome is not None and candidate_outcome is not None:
                outcome_delta = candidate_outcome - control_outcome
        if control_outcome is None or candidate_outcome is None:
            raise ValueError(
                "Outcome-only reflection requires non-null matched control and "
                f"candidate outcomes for {scenario_name!r}."
            )

        visible = list(selection_record.get("generated_tools_visible") or [])
        called = list(selection_record.get("generated_tools_called") or [])
        attempted = list(selection_record.get("generated_tools_attempted") or [])
        failed = list(selection_record.get("generated_tools_failed") or [])
        lifecycle_context = task_context_label or scenario_name
        family = task_family_key or base_task_family(scenario_name)

        immediate_actions = self._immediate_lifecycle_actions(
            scenario_name=lifecycle_context,
            called_tools=called,
            side_effect_failures=side_effect_failures,
            outcome_delta=outcome_delta,
            exception_type=result.get("exception_type"),
        )
        task_feedback = {
            "event": "self_evolution_task_assessed",
            "scenario": scenario_name,
            "task_context_label": lifecycle_context,
            "task_family_key": family,
            "source_task_id_redacted": bool(task_context_label),
            "base_family": family,
            "completed_count": self.completed_count + 1,
            "control_source": control_source,
            "control_baseline_available": control_available,
            "control_cache_eligible": (
                control_available if control_source == "legacy_control_cache" else False
            ),
            "control_cache_hit": (
                control_available if control_source == "legacy_control_cache" else False
            ),
            "control_cache_reason": control_reason,
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
            return
        self._pulse()

    def _is_harmful_call(
        self,
        outcome_delta: float | None,
    ) -> bool:
        return outcome_delta is not None and outcome_delta <= -0.25

    def _is_helpful_call(
        self,
        outcome_delta: float | None,
    ) -> bool:
        return outcome_delta is not None and outcome_delta >= 0.10

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

    def _safety_audit_tool(
        self,
        tool_name: str,
        reason: str,
        scenario_name: str,
    ) -> dict[str, Any]:
        action = {
            "tool_name": tool_name,
            "decision": "needs_safety_audit",
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
        outcome_delta: float | None,
        exception_type: Any,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for tool_name in side_effect_failures:
            if exception_type or self._is_harmful_call(outcome_delta):
                actions.append(
                    self._retire_tool(
                        tool_name,
                        "side_effect_preservation_failure",
                        scenario_name,
                    )
                )
            else:
                actions.append(
                    self._safety_audit_tool(
                        tool_name,
                        "side_effect_preservation_audit",
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
            if self._is_harmful_call(outcome_delta):
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
            negative_called_subset = (
                called_outcome is not None and called_outcome < -0.05
            )
            if tool_name in self.retired_this_run:
                decision = "parked"
                reason = "retired_this_run"
            elif stats.side_effect_incident_count and negative_called_subset:
                decision = "park"
                reason = "side_effect_incident_with_negative_called_subset"
            elif stats.harmful_called_scenarios and stats.helpful_called_scenarios:
                decision = "retain_with_route_repair"
                if stats.side_effect_incident_count:
                    reason = (
                        "mixed_called_subset_family_specific_repair_with_safety_audit"
                    )
                else:
                    reason = "mixed_called_subset_family_specific_repair"
            elif stats.side_effect_incident_count:
                decision = "retain_with_safety_audit"
                reason = "positive_called_subset_with_side_effect_audit"
            elif stats.harmful_called_scenarios:
                decision = "needs_route_repair"
                reason = "harmful_called_subset_without_global_retirement"
            elif (
                stats.called_count >= 2
                and called_outcome is not None
                and called_outcome > 0.05
            ):
                decision = "retain"
                reason = "positive_called_subset"
            elif (
                stats.called_count >= 2
                and called_outcome is not None
                and called_outcome < 0
            ):
                decision = "needs_repair"
                reason = "negative_called_subset"
            elif stats.visible_count >= 8 and stats.called_count == 0:
                decision = "adoption_repair"
                reason = "visible_not_called_repeatedly"
            elif (
                stats.called_count == 1
                and called_outcome is not None
                and called_outcome > 0.05
            ):
                decision = "keep_sparse_positive"
                reason = "single_positive_called_event"
            row["decision"] = decision
            row["decision_reason"] = reason
            snapshot[tool_name] = row
        return snapshot

    def _pulse(self) -> None:
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
            outcome_ok = (
                outcome_delta_mean is not None
                and outcome_delta_mean >= self.min_outcome_delta
            )
            if not outcome_ok:
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
            "tool_lifecycle": self._tool_lifecycle_snapshot(),
            "top_gap_buckets": self._top_gap_buckets(),
        }
        append_jsonl(self.output_dir / "self_evolution_reflections.jsonl", pulse)
        self._write_current_state(extra=pulse)

    def _top_gap_buckets(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for bucket, stats in self.bucket_stats.items():
            score = (
                float(stats["negative_outcome_mass"]) * 10.0
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
