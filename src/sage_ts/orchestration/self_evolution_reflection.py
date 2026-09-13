"""Online reflection and lifecycle policy for self-evolving SAGE runs.

Publication runs compare post-task evaluator-derived scalars with exact
same-run live control rows. The legacy cache comparator remains available only
to non-publication callers. This controller does not receive raw expected
answers, target state, or evaluator traces, but its outcome signals are computed
upstream from benchmark contracts; it is therefore reward-feedback-driven, not
globally label-free.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty
from typing import Any

from sage_ts.evaluation.control_baseline_cache import (
    CACHE_ROOT,
    ControlBaselineCache,
    compatibility_context,
)
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.store import RegistryStore
from tool_sandbox.common.scenario import Scenario

REFLECTION_CONTROL_CACHE_ROOT_ENV = "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT"
FRESH_CONTROL_ROW_EVENT = "fresh_control_row"
FRESH_CONTROL_COMPLETE_EVENT = "fresh_control_complete"
FRESH_CONTROL_ERROR_EVENT = "fresh_control_error"
FRESH_CONTROL_WAIT_TIMEOUT_SECONDS = 1800.0
POST_DEPLOYMENT_REPAIR_REQUEST_EVENT = "post_deployment_tool_repair_requested"
POST_DEPLOYMENT_REPAIR_REQUEST_SCHEMA_VERSION = 1
POST_DEPLOYMENT_REPAIR_REQUEST_FILENAME = "self_evolution_tool_repair_requests.jsonl"
POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME = (
    "self_evolution_tool_repair_acknowledgements.jsonl"
)
POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_STATUSES = frozenset(
    {
        "validation_failed",
        "canary_pending",
        "promoted",
        "rejected",
        "rolled_back",
    }
)
CROSS_FAMILY_EXECUTION_FAILURE = "cross_family_execution_failure"
RUN_END_EXECUTION_FAILURE_REASON = "unresolved_generated_tool_execution_failure"
UNCLASSIFIED_PUBLIC_TASK_CONTEXT = "visible_task_context(family=unclassified)"
_SHA256_HEX_CHARACTERS = frozenset("0123456789abcdef")


def _is_sha256_hex(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and set(value).issubset(_SHA256_HEX_CHARACTERS)
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _online_feedback_outcome_with_source(
    row: dict[str, Any],
) -> tuple[float | None, str]:
    """Return the audited lifecycle outcome and its explicit provenance.

    ``online_feedback_outcome_similarity`` is a legacy paper-comparability
    diagnostic. It is never substituted for a missing current endpoint because
    that would silently mix reward definitions across tasks.
    """

    audited_outcome = _optional_float(row.get("outcome_similarity"))
    if audited_outcome is not None:
        return audited_outcome, "audited_outcome"
    return None, "unavailable"


def _online_feedback_outcome(row: dict[str, Any]) -> float | None:
    """Return the outcome signal used by lifecycle feedback.

    New runs use the current route-independent audited reporting outcome. The
    legacy paper-era feedback remains reporting-only.
    """

    return _online_feedback_outcome_with_source(row)[0]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _read_jsonl_objects_strict(path: Path, *, label: str) -> list[dict[str, Any]]:
    """Read an append-only journal without silently discarding corruption."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Unable to read {label} journal: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed {label} journal row at {path}:{line_number}."
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(f"Non-object {label} journal row at {path}:{line_number}.")
        rows.append(row)
    return rows


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace one durable JSON state file in its own directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


@dataclass
class ToolFamilyLifecycleStats:
    """Post-deployment evidence for one visible, semantic task family."""

    visible_count: int = 0
    called_count: int = 0
    failed_count: int = 0
    contract_failure_count: int = 0
    success_flip_count: int = 0
    public_visible_context_count: int = 0
    sole_generated_call_count: int = 0
    attributable_harmful_call_count: int = 0
    attributable_helpful_call_count: int = 0
    candidate_outcomes: list[float] = field(default_factory=list)
    called_score_deltas: list[float] = field(default_factory=list)
    called_outcome_deltas: list[float] = field(default_factory=list)

    def to_json(self, *, outcome_success_threshold: float) -> dict[str, Any]:
        outcome_success_count = sum(
            outcome >= outcome_success_threshold for outcome in self.candidate_outcomes
        )
        outcome_observation_count = len(self.candidate_outcomes)
        return {
            "visible_count": self.visible_count,
            "called_count": self.called_count,
            "failed_count": self.failed_count,
            "contract_failure_count": self.contract_failure_count,
            "success_flip_count": self.success_flip_count,
            "public_visible_context_count": self.public_visible_context_count,
            "sole_generated_call_count": self.sole_generated_call_count,
            "attributable_harmful_call_count": (self.attributable_harmful_call_count),
            "attributable_helpful_call_count": (self.attributable_helpful_call_count),
            "candidate_outcome_observation_count": outcome_observation_count,
            "candidate_outcome_mean": _mean(self.candidate_outcomes),
            "candidate_outcome_success_count": outcome_success_count,
            "candidate_outcome_failure_count": (
                outcome_observation_count - outcome_success_count
            ),
            "candidate_outcome_success_rate": (
                outcome_success_count / outcome_observation_count
                if outcome_observation_count
                else None
            ),
            "called_score_delta_mean": _mean(self.called_score_deltas),
            "called_outcome_delta_mean": _mean(self.called_outcome_deltas),
        }


@dataclass
class ToolLifecycleStats:
    tool_version: int | None = None
    visible_count: int = 0
    called_count: int = 0
    attempted_count: int = 0
    failed_count: int = 0
    visible_not_called_count: int = 0
    side_effect_incident_count: int = 0
    contract_failure_count: int = 0
    success_flip_count: int = 0
    called_candidate_outcomes: list[float] = field(default_factory=list)
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
    family_stats: dict[str, ToolFamilyLifecycleStats] = field(default_factory=dict)

    def to_json(self, *, outcome_success_threshold: float = 1.0) -> dict[str, Any]:
        called_score_mean = _mean(self.called_score_deltas)
        called_outcome_mean = _mean(self.called_outcome_deltas)
        visible_score_mean = _mean(self.visible_score_deltas)
        visible_outcome_mean = _mean(self.visible_outcome_deltas)
        candidate_outcome_mean = _mean(self.called_candidate_outcomes)
        candidate_outcome_success_count = sum(
            outcome >= outcome_success_threshold
            for outcome in self.called_candidate_outcomes
        )
        candidate_outcome_observation_count = len(self.called_candidate_outcomes)
        return {
            "tool_version": self.tool_version,
            "visible_count": self.visible_count,
            "called_count": self.called_count,
            "attempted_count": self.attempted_count,
            "failed_count": self.failed_count,
            "visible_not_called_count": self.visible_not_called_count,
            "side_effect_incident_count": self.side_effect_incident_count,
            "contract_failure_count": self.contract_failure_count,
            "success_flip_count": self.success_flip_count,
            "candidate_outcome_observation_count": (
                candidate_outcome_observation_count
            ),
            "candidate_outcome_mean": candidate_outcome_mean,
            "candidate_outcome_success_count": candidate_outcome_success_count,
            "candidate_outcome_failure_count": (
                candidate_outcome_observation_count - candidate_outcome_success_count
            ),
            "candidate_outcome_success_rate": (
                candidate_outcome_success_count / candidate_outcome_observation_count
                if candidate_outcome_observation_count
                else None
            ),
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
            "family_evidence": {
                family: stats.to_json(
                    outcome_success_threshold=outcome_success_threshold
                )
                for family, stats in sorted(self.family_stats.items())
            },
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
    min_outcome_diagnostic_calls: int = 8
    min_implementation_repair_contract_failures: int = 1
    min_implementation_repair_execution_failures: int = 3
    min_metadata_repair_visible_count: int = 8
    min_route_repair_harmful_calls: int = 2
    min_acceptable_called_outcome_mean: float = 0.50
    outcome_success_threshold: float = 1.0
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
    pending_repair_requests: list[dict[str, Any]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    emitted_repair_request_keys: set[str] = field(
        default_factory=set,
        init=False,
        repr=False,
    )
    _feedback_hydrated: bool = field(default=False, init=False, repr=False)

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
        if self.min_outcome_diagnostic_calls < 1:
            raise ValueError("Outcome-diagnostic call threshold must be positive.")
        if self.min_implementation_repair_contract_failures < 1:
            raise ValueError(
                "Implementation-repair contract-failure threshold must be positive."
            )
        if self.min_implementation_repair_execution_failures < 1:
            raise ValueError(
                "Implementation-repair execution-failure threshold must be positive."
            )
        if self.min_metadata_repair_visible_count < 1:
            raise ValueError("Metadata-repair visibility threshold must be positive.")
        if self.min_route_repair_harmful_calls < 1:
            raise ValueError("Route-repair harm threshold must be positive.")
        if not 0.0 <= self.min_acceptable_called_outcome_mean <= 1.0:
            raise ValueError("Acceptable called-outcome mean must be in [0, 1].")
        if not 0.0 <= self.outcome_success_threshold <= 1.0:
            raise ValueError("Outcome success threshold must be in [0, 1].")
        self._load_emitted_repair_request_keys()
        self._restore_retired_registry_entries()
        self._hydrate_from_existing_feedback()

    @property
    def repair_request_path(self) -> Path:
        """Append-only handoff from reflection to the repair orchestrator."""

        return self.output_dir / POST_DEPLOYMENT_REPAIR_REQUEST_FILENAME

    @property
    def repair_acknowledgement_path(self) -> Path:
        """Durable orchestration responses to lifecycle repair requests."""

        return self.output_dir / POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME

    def _load_emitted_repair_request_keys(self) -> None:
        """Avoid duplicate repair requests when an online run resumes."""

        if not self.repair_request_path.exists():
            return
        for row in _read_jsonl_objects_strict(
            self.repair_request_path,
            label="self-evolution repair request",
        ):
            request_key = row.get("request_key")
            if not isinstance(request_key, str) or not request_key:
                raise ValueError(
                    "Self-evolution repair request journal contains a row without "
                    "a durable request_key."
                )
            self.emitted_repair_request_keys.add(request_key)

    def _restore_retired_registry_entries(self) -> None:
        """Preserve durable quarantine decisions across process restarts."""

        self.retired_this_run.update(
            tool_name
            for tool_name, entry in self.store.load_entries().items()
            if entry.retired
        )

    def drain_pending_repair_requests(self) -> tuple[dict[str, Any], ...]:
        """Return newly emitted future-only requests once to orchestration.

        The append-only JSONL remains the durable source of record. This in-memory
        drain is deliberately non-blocking and never applies a repair to the task
        whose post-task evidence caused the transition.
        """

        requests = tuple(self.pending_repair_requests)
        self.pending_repair_requests.clear()
        return requests

    def acknowledge_repair(
        self,
        tool_name: str,
        new_version: int,
        request_id: str,
        status: str,
        implementation_proof: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record orchestration's disposition and isolate new-version evidence.

        A validated version may enter a prospective canary on the *next* task. Its
        evidence starts empty so a vN+1 candidate is not immediately classified
        using failures accumulated by vN.
        """

        if not tool_name:
            raise ValueError("Repair acknowledgement requires a tool name.")
        if new_version < 1:
            raise ValueError("Repair acknowledgement requires a positive version.")
        if not request_id:
            raise ValueError("Repair acknowledgement requires a request id.")
        if status not in POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_STATUSES:
            raise ValueError(f"Unknown repair acknowledgement status: {status!r}.")
        request: dict[str, Any] | None = None
        if self.repair_request_path.exists():
            matching_requests = [
                row
                for row in _read_jsonl_objects_strict(
                    self.repair_request_path,
                    label="self-evolution repair request",
                )
                if row.get("request_id") == request_id
            ]
            if len(matching_requests) > 1:
                raise ValueError(
                    "Repair acknowledgement matches duplicate request ids."
                )
            if matching_requests:
                request = matching_requests[0]
        request_kind = str((request or {}).get("repair_kind") or "")
        if request_kind == "metadata":
            if not isinstance(implementation_proof, dict):
                raise ValueError(
                    "Metadata repair acknowledgement requires implementation proof."
                )
            source_hash = str((request or {}).get("source_code_hash") or "")
            proof_source_hash = implementation_proof.get("source_code_hash")
            replacement_hash = implementation_proof.get("replacement_code_hash")
            replacement_activated = implementation_proof.get("replacement_activated")
            implementation_preserved = implementation_proof.get(
                "implementation_preserved"
            )
            code_change_discarded = implementation_proof.get(
                "model_authored_code_change_discarded"
            )
            if (
                implementation_proof.get("proof_schema_version") != 1
                or implementation_proof.get("repair_kind") != "metadata"
                or not _is_sha256_hex(source_hash)
                or proof_source_hash != source_hash
                or not _is_sha256_hex(proof_source_hash)
                or not isinstance(replacement_activated, bool)
                or not isinstance(implementation_preserved, bool)
                or not isinstance(code_change_discarded, bool)
                or (replacement_activated and not _is_sha256_hex(replacement_hash))
                or (not replacement_activated and replacement_hash is not None)
                or implementation_preserved
                != (not replacement_activated or replacement_hash == proof_source_hash)
                or (
                    status in {"canary_pending", "promoted"}
                    and not replacement_activated
                )
            ):
                raise ValueError(
                    "Metadata repair acknowledgement has invalid implementation proof."
                )
        elif implementation_proof is not None:
            raise ValueError(
                "Implementation proof is permitted only for a metadata repair request."
            )
        current_stats = self.tool_stats.get(tool_name)
        if status in {"canary_pending", "promoted"} and (
            current_stats is None or current_stats.tool_version != new_version
        ):
            self.tool_stats[tool_name] = ToolLifecycleStats(tool_version=new_version)
        if status in {"canary_pending", "promoted"}:
            # Retirement applies to the failed implementation version, not to a
            # separately validated replacement with the same public tool name.
            self.retired_this_run.discard(tool_name)
        event = {
            "event": "post_deployment_tool_repair_acknowledged",
            "schema_version": POST_DEPLOYMENT_REPAIR_REQUEST_SCHEMA_VERSION,
            "request_id": request_id,
            "tool_name": tool_name,
            "new_version": new_version,
            "status": status,
            "acknowledged_after_completed_count": self.completed_count,
            "eligible_from_completed_count": self.completed_count + 1,
            "future_tasks_only": True,
            "triggering_task_replay_allowed": False,
        }
        if implementation_proof is not None:
            event["implementation_proof"] = dict(implementation_proof)
        append_jsonl(self.repair_acknowledgement_path, event)
        self._write_current_state()
        return event

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
        return controller

    def _hydrate_from_existing_feedback(self) -> None:
        """Restore cumulative lifecycle state after a resumable run restart."""
        if self._feedback_hydrated:
            return
        path = self.output_dir / "self_evolution_task_feedback.jsonl"
        if not path.exists():
            self._feedback_hydrated = True
            return
        rows = _read_jsonl_objects_strict(
            path,
            label="self-evolution task feedback",
        )
        self._validate_feedback_journal(rows, path=path)
        for row in rows:
            self._consume_resumed_fresh_control(row)
            self._record_feedback_row(row)
        self._feedback_hydrated = True
        if rows:
            self._write_current_state()

    @staticmethod
    def _validate_feedback_journal(
        rows: list[dict[str, Any]],
        *,
        path: Path,
    ) -> None:
        """Validate the durable replay source before mutating in-memory evidence."""

        list_fields = (
            "generated_tools_visible",
            "generated_tools_called",
            "generated_tools_attempted",
            "generated_tools_failed",
            "generated_tool_contract_failures",
            "side_effect_failures",
            "post_deployment_repair_request_ids",
        )
        numeric_fields = (
            "control_score",
            "candidate_score",
            "score_delta",
            "control_outcome",
            "candidate_outcome",
            "outcome_delta",
        )
        boolean_fields = (
            "control_cache_eligible",
            "control_cache_hit",
            "candidate_success_flip",
            "source_task_id_redacted",
        )
        scenarios: set[str] = set()
        for line_number, row in enumerate(rows, start=1):
            prefix = f"Malformed task feedback journal row at {path}:{line_number}"
            if row.get("event") != "self_evolution_task_assessed":
                raise ValueError(f"{prefix}: unexpected event.")
            scenario = row.get("scenario")
            if not isinstance(scenario, str) or not scenario:
                raise ValueError(f"{prefix}: scenario must be a non-empty string.")
            if scenario in scenarios:
                raise ValueError(f"{prefix}: duplicate scenario {scenario!r}.")
            scenarios.add(scenario)
            completed_count = row.get("completed_count")
            if (
                not isinstance(completed_count, int)
                or isinstance(completed_count, bool)
                or completed_count != line_number
            ):
                raise ValueError(f"{prefix}: completed_count must equal {line_number}.")
            family = row.get("task_family_key", row.get("base_family"))
            if not isinstance(family, str) or not family:
                raise ValueError(
                    f"{prefix}: task_family_key/base_family must be a non-empty string."
                )
            if "task_context_label" in row and (
                not isinstance(row["task_context_label"], str)
                or not row["task_context_label"]
            ):
                raise ValueError(
                    f"{prefix}: task_context_label must be a non-empty string."
                )
            for field_name in list_fields:
                if field_name not in row:
                    continue
                value = row[field_name]
                if not isinstance(value, list) or any(
                    not isinstance(item, str) or not item for item in value
                ):
                    raise ValueError(
                        f"{prefix}: {field_name} must be a list of non-empty strings."
                    )
            for field_name in numeric_fields:
                if field_name not in row or row[field_name] is None:
                    continue
                value = row[field_name]
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise ValueError(
                        f"{prefix}: {field_name} must be a finite number or null."
                    )
            for field_name in boolean_fields:
                if field_name in row and not isinstance(row[field_name], bool):
                    raise ValueError(f"{prefix}: {field_name} must be boolean.")
            if "exception_type" in row and not (
                row["exception_type"] is None or isinstance(row["exception_type"], str)
            ):
                raise ValueError(f"{prefix}: exception_type must be a string or null.")
            versions = row.get("generated_tool_versions")
            if versions is not None and (
                not isinstance(versions, dict)
                or any(
                    not isinstance(tool_name, str)
                    or not tool_name
                    or not isinstance(version, int)
                    or isinstance(version, bool)
                    or version < 1
                    for tool_name, version in versions.items()
                )
            ):
                raise ValueError(
                    f"{prefix}: generated_tool_versions must map non-empty tool "
                    "names to positive integer versions."
                )

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
        expected_score = _optional_float(row.get("similarity"))
        expected_outcome = _online_feedback_outcome(row)
        if _optional_float(feedback.get("control_score")) != expected_score:
            raise ValueError(
                f"Resumed fresh control score changed for {scenario_name!r}."
            )
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

    @staticmethod
    def _contract_failure_tools(row: dict[str, Any]) -> list[str]:
        """Read public-contract failures without accepting diagnostic payloads.

        Orchestration may provide only generated tool names in this field. Raw
        validator messages are intentionally not carried into lifecycle state or
        repair prompts because they could contain task-specific or hidden data.
        """

        raw = row.get("generated_tool_contract_failures") or []
        if not isinstance(raw, list):
            return []
        return sorted({item for item in raw if isinstance(item, str) and item})

    def _tool_stats_for_version(
        self,
        tool_name: str,
        tool_version: int | None,
    ) -> ToolLifecycleStats:
        stats = self.tool_stats.get(tool_name)
        if stats is None or (
            tool_version is not None
            and stats.tool_version is not None
            and stats.tool_version != tool_version
        ):
            stats = ToolLifecycleStats(tool_version=tool_version)
            self.tool_stats[tool_name] = stats
        elif stats.tool_version is None and tool_version is not None:
            stats.tool_version = tool_version
        return stats

    def _record_feedback_row(self, row: dict[str, Any]) -> None:
        scenario_name = str(row.get("scenario") or "")
        if not scenario_name:
            return
        raw_task_context_label = row.get("task_context_label")
        raw_task_family_key = row.get("task_family_key")
        has_public_lifecycle_context = bool(
            row.get("source_task_id_redacted") is True
            and isinstance(raw_task_context_label, str)
            and raw_task_context_label.strip()
            and isinstance(raw_task_family_key, str)
            and raw_task_family_key.strip()
        )
        task_context_label = (
            raw_task_context_label.strip()
            if has_public_lifecycle_context
            else UNCLASSIFIED_PUBLIC_TASK_CONTEXT
        )
        task_family_key = (
            raw_task_family_key.strip()
            if has_public_lifecycle_context
            else "unclassified"
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
        success_flip = bool(
            candidate_outcome is not None
            and control_outcome is not None
            and candidate_outcome >= self.outcome_success_threshold
            and control_outcome < self.outcome_success_threshold
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
        contract_failures = self._contract_failure_tools(row)
        raw_versions = row.get("generated_tool_versions")
        generated_tool_versions = (
            {
                str(tool_name): int(version)
                for tool_name, version in raw_versions.items()
                if isinstance(tool_name, str)
                and isinstance(version, int)
                and not isinstance(version, bool)
            }
            if isinstance(raw_versions, dict)
            else {}
        )
        if not visible:
            bucket["no_visible_helper"] += 1
        if not called:
            bucket["no_called_helper"] += 1

        generated_attempt_set = set(called) | set(attempted) | set(failed)
        route_attribution_available = bool(
            row.get("control_source") == "same_run_fresh"
            and row.get("control_outcome_source") == "audited_outcome"
            and row.get("candidate_outcome_source") == "audited_outcome"
            and control_outcome is not None
            and candidate_outcome is not None
            and outcome_delta is not None
            and not row.get("exception_type")
            and row.get("source_task_id_redacted") is True
        )

        for tool_name in sorted(
            set(visible)
            | set(called)
            | set(attempted)
            | set(failed)
            | set(contract_failures)
        ):
            stats = self._tool_stats_for_version(
                tool_name,
                generated_tool_versions.get(tool_name),
            )
            family_stats = stats.family_stats.setdefault(
                family,
                ToolFamilyLifecycleStats(),
            )
            if task_context_label not in stats.scenarios:
                stats.scenarios.append(task_context_label)
            if family not in stats.families:
                stats.families.append(family)
            if row.get("source_task_id_redacted"):
                family_stats.public_visible_context_count += 1
            if tool_name in visible:
                stats.visible_count += 1
                family_stats.visible_count += 1
                if score_delta is not None:
                    stats.visible_score_deltas.append(score_delta)
                if outcome_delta is not None:
                    stats.visible_outcome_deltas.append(outcome_delta)
            if tool_name in called:
                stats.called_count += 1
                family_stats.called_count += 1
                if candidate_outcome is not None:
                    stats.called_candidate_outcomes.append(candidate_outcome)
                    family_stats.candidate_outcomes.append(candidate_outcome)
                if success_flip:
                    stats.success_flip_count += 1
                    family_stats.success_flip_count += 1
                if score_delta is not None:
                    stats.called_score_deltas.append(score_delta)
                    family_stats.called_score_deltas.append(score_delta)
                if outcome_delta is not None:
                    stats.called_outcome_deltas.append(outcome_delta)
                    family_stats.called_outcome_deltas.append(outcome_delta)
                if self._is_harmful_call(score_delta, outcome_delta):
                    stats.harmful_called_scenarios.append(task_context_label)
                    stats.harmful_called_families.append(family)
                elif self._is_helpful_call(score_delta, outcome_delta):
                    stats.helpful_called_scenarios.append(task_context_label)
                    stats.helpful_called_families.append(family)
                if route_attribution_available and generated_attempt_set == {tool_name}:
                    family_stats.sole_generated_call_count += 1
                    if self._is_harmful_call(score_delta, outcome_delta):
                        family_stats.attributable_harmful_call_count += 1
                    elif self._is_helpful_call(score_delta, outcome_delta):
                        family_stats.attributable_helpful_call_count += 1
            if tool_name in attempted:
                stats.attempted_count += 1
            if tool_name in failed:
                stats.failed_count += 1
                family_stats.failed_count += 1
            if tool_name in contract_failures and tool_name in called:
                stats.contract_failure_count += 1
                family_stats.contract_failure_count += 1
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
    ) -> dict[str, Any]:
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
        control_outcome_source = "unavailable"
        candidate_score = _optional_float(result.get("similarity"))
        candidate_outcome, candidate_outcome_source = (
            _online_feedback_outcome_with_source(result)
        )
        score_delta = None
        outcome_delta = None
        if control_available and control_row is not None:
            control_score = _optional_float(control_row.get("similarity"))
            control_outcome, control_outcome_source = (
                _online_feedback_outcome_with_source(control_row)
            )
            if control_score is not None and candidate_score is not None:
                score_delta = candidate_score - control_score
            if control_outcome is not None and candidate_outcome is not None:
                outcome_delta = candidate_outcome - control_outcome
        candidate_success_flip = bool(
            candidate_outcome is not None
            and control_outcome is not None
            and candidate_outcome >= self.outcome_success_threshold
            and control_outcome < self.outcome_success_threshold
        )

        visible = list(selection_record.get("generated_tools_visible") or [])
        called = list(selection_record.get("generated_tools_called") or [])
        attempted = list(selection_record.get("generated_tools_attempted") or [])
        failed = list(selection_record.get("generated_tools_failed") or [])
        contract_failures = self._contract_failure_tools(selection_record)
        observed_tool_names = {
            str(item)
            for item in (*visible, *called, *attempted, *failed, *contract_failures)
            if isinstance(item, str) and item
        }
        registry_entries = self.store.load_entries() if observed_tool_names else {}
        generated_tool_versions = {
            tool_name: registry_entries[tool_name].version
            for tool_name in sorted(observed_tool_names)
            if tool_name in registry_entries
        }
        has_public_lifecycle_context = bool(
            isinstance(task_context_label, str)
            and task_context_label.strip()
            and isinstance(task_family_key, str)
            and task_family_key.strip()
        )
        lifecycle_context = (
            task_context_label.strip()
            if has_public_lifecycle_context
            else UNCLASSIFIED_PUBLIC_TASK_CONTEXT
        )
        family = (
            task_family_key.strip() if has_public_lifecycle_context else "unclassified"
        )

        immediate_actions = self._immediate_lifecycle_actions(
            scenario_name=lifecycle_context,
            called_tools=called,
            side_effect_failures=side_effect_failures,
            score_delta=score_delta,
            outcome_delta=outcome_delta,
        )
        task_feedback = {
            "event": "self_evolution_task_assessed",
            "scenario": scenario_name,
            "task_context_label": lifecycle_context,
            "task_family_key": family,
            "source_task_id_redacted": has_public_lifecycle_context,
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
            "control_outcome_source": control_outcome_source,
            "candidate_outcome": candidate_outcome,
            "candidate_outcome_source": candidate_outcome_source,
            "outcome_delta": outcome_delta,
            "candidate_success_flip": candidate_success_flip,
            "exception_type": result.get("exception_type"),
            "generated_tools_visible": visible,
            "generated_tools_called": called,
            "generated_tools_attempted": attempted,
            "generated_tools_failed": failed,
            "generated_tool_contract_failures": contract_failures,
            "generated_tool_versions": generated_tool_versions,
            "side_effect_failures": side_effect_failures,
            "immediate_actions": immediate_actions,
        }
        self._record_feedback_row(task_feedback)
        emitted_repair_requests = self._emit_post_deployment_repair_requests()
        task_feedback["post_deployment_repair_request_ids"] = [
            request["request_id"] for request in emitted_repair_requests
        ]
        append_jsonl(
            self.output_dir / "self_evolution_task_feedback.jsonl", task_feedback
        )

        if self.completed_count % self.pulse_interval != 0:
            self._write_current_state()
            return task_feedback
        self._pulse()
        return task_feedback

    def _is_harmful_call(
        self,
        score_delta: float | None,
        outcome_delta: float | None,
    ) -> bool:
        if outcome_delta is not None:
            if outcome_delta >= 0:
                return False
            return outcome_delta <= -0.25
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
        score_delta: float | None,
        outcome_delta: float | None,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for tool_name in side_effect_failures:
            if self._is_harmful_call(score_delta, outcome_delta):
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
            if self._is_harmful_call(score_delta, outcome_delta):
                actions.append(
                    self._route_repair_tool(
                        tool_name,
                        "severe_negative_called_delta",
                        scenario_name,
                    )
                )
        return actions

    def _implementation_repair_evidence(
        self,
        stats: ToolLifecycleStats,
        *,
        include_sparse_execution_failures: bool = False,
    ) -> dict[str, tuple[str, ...]]:
        """Classify implementation gaps separately from routing regressions.

        Only evidence attributable to the generated tool may mutate its
        implementation. A deterministic failure of the tool's public contract is
        conclusive on its own. Transcript-confirmed execution failures require a
        small repeated sample because malformed model arguments or transient
        runtime conditions can otherwise look like an implementation defect.

        Whole-task outcomes and paired deltas remain diagnostic/routing evidence;
        they cannot establish that any one of several co-called tools was faulty.
        """

        classified: dict[str, tuple[str, ...]] = {}
        for family, family_stats in sorted(stats.family_stats.items()):
            reasons: list[str] = []
            if (
                family_stats.contract_failure_count
                >= self.min_implementation_repair_contract_failures
            ):
                reasons.append("deterministic_public_contract_failure")
            if (
                family_stats.failed_count
                >= self.min_implementation_repair_execution_failures
            ):
                reasons.append("repeated_generated_tool_execution_failure")
            if reasons:
                classified[family] = tuple(reasons)
        if classified:
            return classified

        failed_families = sorted(
            family
            for family, family_stats in stats.family_stats.items()
            if family_stats.failed_count > 0
        )
        if stats.failed_count >= self.min_implementation_repair_execution_failures:
            target_family = (
                failed_families[0]
                if len(failed_families) == 1
                else CROSS_FAMILY_EXECUTION_FAILURE
            )
            classified[target_family] = ("repeated_generated_tool_execution_failure",)
        elif include_sparse_execution_failures and stats.failed_count > 0:
            target_family = (
                failed_families[0]
                if len(failed_families) == 1
                else CROSS_FAMILY_EXECUTION_FAILURE
            )
            classified[target_family] = (RUN_END_EXECUTION_FAILURE_REASON,)
        return classified

    def _outcome_shortfall_diagnostic_families(
        self,
        stats: ToolLifecycleStats,
    ) -> list[str]:
        """Flag low task outcomes without attributing them to a co-called tool."""

        return sorted(
            family
            for family, family_stats in stats.family_stats.items()
            if family_stats.called_count >= self.min_outcome_diagnostic_calls
            and len(family_stats.candidate_outcomes)
            >= self.min_outcome_diagnostic_calls
            and (candidate_mean := _mean(family_stats.candidate_outcomes)) is not None
            and candidate_mean < self.min_acceptable_called_outcome_mean
        )

    @staticmethod
    def _public_family_label(
        family: str,
        family_stats: ToolFamilyLifecycleStats,
    ) -> str:
        """Return only a compact family label proved to come from visible context."""

        if family_stats.public_visible_context_count <= 0:
            return "unclassified"
        normalized = str(family or "").strip().lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.:-")
        if not normalized or len(normalized) > 128:
            return "unclassified"
        if any(character not in allowed for character in normalized):
            return "unclassified"
        return normalized

    def _metadata_repair_families(
        self,
        stats: ToolLifecycleStats,
    ) -> list[str]:
        """Return families where a never-selected tool failed adoption.

        Metadata replacement and its canary operate on the registry entry as a
        whole. Do not expose a tool that has already been selected successfully
        in another family to global replacement or retirement merely because it
        was not adopted in one additional family.
        """

        if stats.called_count:
            return []

        return sorted(
            family
            for family, family_stats in stats.family_stats.items()
            if family_stats.visible_count >= self.min_metadata_repair_visible_count
            and family_stats.called_count == 0
        )

    def _active_route_repair_families(
        self,
        stats: ToolLifecycleStats,
    ) -> list[str]:
        """Return families with repeated, sole-tool, fresh-control regressions."""

        return sorted(
            family
            for family, family_stats in stats.family_stats.items()
            if family_stats.public_visible_context_count > 0
            and family_stats.attributable_harmful_call_count
            >= self.min_route_repair_harmful_calls
            and family_stats.attributable_harmful_call_count
            > family_stats.attributable_helpful_call_count
        )

    def _emit_post_deployment_repair_requests(
        self,
        *,
        include_sparse_execution_failures: bool = False,
    ) -> list[dict[str, Any]]:
        """Emit durable, future-only repair work without raw benchmark evidence."""

        emitted: list[dict[str, Any]] = []
        for tool_name, stats in sorted(self.tool_stats.items()):
            classified = self._implementation_repair_evidence(
                stats,
                include_sparse_execution_failures=include_sparse_execution_failures,
            )
            for family, reason_codes in sorted(classified.items()):
                if family == CROSS_FAMILY_EXECUTION_FAILURE:
                    evidence = stats.to_json(
                        outcome_success_threshold=self.outcome_success_threshold
                    )
                    public_family = CROSS_FAMILY_EXECUTION_FAILURE
                else:
                    family_stats = stats.family_stats[family]
                    evidence = family_stats.to_json(
                        outcome_success_threshold=self.outcome_success_threshold
                    )
                    public_family = self._public_family_label(family, family_stats)
                version_label = (
                    str(stats.tool_version)
                    if stats.tool_version is not None
                    else "unknown"
                )
                request_key = (
                    f"implementation:{tool_name}:v{version_label}:{public_family}"
                )
                if request_key in self.emitted_repair_request_keys:
                    continue
                request_id = (
                    f"{tool_name}:v{version_label}:{public_family}:"
                    f"after-{self.completed_count}"
                )
                public_evidence = {
                    key: evidence[key]
                    for key in (
                        "called_count",
                        "contract_failure_count",
                        "failed_count",
                    )
                }
                request = {
                    "event": POST_DEPLOYMENT_REPAIR_REQUEST_EVENT,
                    "schema_version": POST_DEPLOYMENT_REPAIR_REQUEST_SCHEMA_VERSION,
                    "request_id": request_id,
                    "request_key": request_key,
                    "status": "pending",
                    "repair_kind": "implementation",
                    "tool_name": tool_name,
                    "source_tool_version": stats.tool_version,
                    "target_task_family": public_family,
                    "trigger_reason_codes": list(reason_codes),
                    "trigger_completed_count": self.completed_count,
                    "eligible_from_completed_count": self.completed_count + 1,
                    "future_tasks_only": True,
                    "triggering_task_replay_allowed": False,
                    "requested_action": ("regenerate_validate_and_canary_new_version"),
                    "public_evidence": public_evidence,
                    "evidence_policy": {
                        "allowed": [
                            "public_contract_failure_count",
                            "generated_tool_execution_failure_count",
                            "visible_semantic_task_family",
                            "visible_and_called_counts",
                        ],
                        "prohibited": [
                            "scenario_name",
                            "task_id",
                            "expected_answer",
                            "target_state",
                            "evaluator_trace",
                            "outcome_values",
                            "success_flips",
                        ],
                    },
                }
                append_jsonl(self.repair_request_path, request)
                self.emitted_repair_request_keys.add(request_key)
                self.pending_repair_requests.append(request)
                emitted.append(request)
            for family in self._metadata_repair_families(stats):
                family_stats = stats.family_stats[family]
                public_family = self._public_family_label(family, family_stats)
                source_entry = self.store.get(tool_name)
                if (
                    source_entry is None
                    or stats.tool_version is None
                    or source_entry.version != stats.tool_version
                    or not source_entry.code_hash_verified
                    or not _is_sha256_hex(source_entry.stored_code_hash)
                ):
                    raise ValueError(
                        "Metadata repair cannot bind the observed tool version to a "
                        "verified source implementation."
                    )
                source_code_hash = str(source_entry.stored_code_hash)
                version_label = (
                    str(stats.tool_version)
                    if stats.tool_version is not None
                    else "unknown"
                )
                request_key = f"metadata:{tool_name}:v{version_label}:{public_family}"
                if request_key in self.emitted_repair_request_keys:
                    continue
                request_id = (
                    f"metadata:{tool_name}:v{version_label}:{public_family}:"
                    f"after-{self.completed_count}"
                )
                request = {
                    "event": POST_DEPLOYMENT_REPAIR_REQUEST_EVENT,
                    "schema_version": POST_DEPLOYMENT_REPAIR_REQUEST_SCHEMA_VERSION,
                    "request_id": request_id,
                    "request_key": request_key,
                    "status": "pending",
                    "repair_kind": "metadata",
                    "tool_name": tool_name,
                    "source_tool_version": stats.tool_version,
                    "source_code_hash": source_code_hash,
                    "target_task_family": public_family,
                    "trigger_reason_codes": ["visible_repeatedly_without_adoption"],
                    "trigger_completed_count": self.completed_count,
                    "eligible_from_completed_count": self.completed_count + 1,
                    "future_tasks_only": True,
                    "triggering_task_replay_allowed": False,
                    "requested_action": (
                        "repair_public_metadata_and_revalidate_or_retire"
                    ),
                    "public_evidence": {
                        "visible_count": family_stats.visible_count,
                        "called_count": family_stats.called_count,
                        "public_visible_context_count": (
                            family_stats.public_visible_context_count
                        ),
                        "failed_count": family_stats.failed_count,
                    },
                    "evidence_policy": {
                        "allowed": [
                            "visible_semantic_task_family",
                            "runtime_failure_count",
                            "visible_and_called_counts",
                            "public_tool_schema_and_metadata",
                        ],
                        "prohibited": [
                            "scenario_name",
                            "task_id",
                            "expected_answer",
                            "target_state",
                            "evaluator_trace",
                            "outcome_values",
                            "success_flips",
                        ],
                    },
                }
                append_jsonl(self.repair_request_path, request)
                self.emitted_repair_request_keys.add(request_key)
                self.pending_repair_requests.append(request)
                emitted.append(request)
        return emitted

    def drain_run_end_repair_requests(self) -> tuple[dict[str, Any], ...]:
        """Close sparse direct failures before orchestration finalizes the run.

        During a run, repeated execution failures trigger repair after three
        observations. At run end, one or two remaining explicit
        ``generated_tools_failed`` observations must not disappear merely because
        no third opportunity occurred. The caller must queue the returned requests
        before the online-birth controller performs its terminal repair/retirement
        finalization.
        """

        self._emit_post_deployment_repair_requests(
            include_sparse_execution_failures=True
        )
        self._write_current_state()
        return self.drain_pending_repair_requests()

    def _tool_lifecycle_snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for tool_name, stats in sorted(self.tool_stats.items()):
            row = stats.to_json(
                outcome_success_threshold=self.outcome_success_threshold
            )
            decision = "diagnostic"
            reason = "insufficient_evidence"
            repair_kind: str | None = None
            routing_disposition = "unchanged"
            called_outcome = row["called_outcome_delta_mean"]
            called_score = row["called_score_delta_mean"]
            helpful_count = len(stats.helpful_called_scenarios)
            harmful_count = len(stats.harmful_called_scenarios)
            implementation_repair_evidence = self._implementation_repair_evidence(stats)
            implementation_repair_families = sorted(implementation_repair_evidence)
            outcome_shortfall_alarm_families = (
                self._outcome_shortfall_diagnostic_families(stats)
            )
            metadata_repair_families = self._metadata_repair_families(stats)
            route_repair_families = self._active_route_repair_families(stats)
            row["implementation_repair_families"] = implementation_repair_families
            row["implementation_repair_reason_codes"] = {
                family: list(reason_codes)
                for family, reason_codes in implementation_repair_evidence.items()
            }
            row["outcome_shortfall_alarm_families"] = outcome_shortfall_alarm_families
            row["outcome_shortfall_alarm_reason"] = (
                "low_task_outcome_not_tool_attributable"
                if outcome_shortfall_alarm_families
                else None
            )
            row["metadata_repair_families"] = metadata_repair_families
            row["route_repair_families"] = route_repair_families
            if called_outcome is not None:
                negative_called_subset = called_outcome < -0.05
            else:
                negative_called_subset = (
                    called_score is not None and called_score < -0.05
                ) or harmful_count > helpful_count
            if tool_name in self.retired_this_run:
                decision = "parked"
                reason = "retired_this_run"
                routing_disposition = "quarantined"
            elif stats.side_effect_incident_count and negative_called_subset:
                decision = "park"
                reason = "side_effect_incident_with_negative_called_subset"
                repair_kind = "safety"
                routing_disposition = "quarantined"
            elif implementation_repair_families:
                decision = "needs_implementation_repair"
                if any(
                    "deterministic_public_contract_failure" in reason_codes
                    for reason_codes in implementation_repair_evidence.values()
                ):
                    reason = "deterministic_public_contract_failure"
                else:
                    reason = "repeated_generated_tool_execution_failure"
                repair_kind = "implementation"
                routing_disposition = "quarantine_pending_repair"
            elif route_repair_families:
                has_attributable_helpful_route = any(
                    family_stats.attributable_helpful_call_count > 0
                    for family, family_stats in stats.family_stats.items()
                    if family not in route_repair_families
                )
                decision = (
                    "retain_with_route_repair"
                    if has_attributable_helpful_route
                    else "needs_route_repair"
                )
                repair_kind = "routing"
                reason = "repeated_sole_tool_family_regression"
                routing_disposition = "family_suppression_active"
            elif stats.side_effect_incident_count:
                decision = "retain_with_safety_audit"
                reason = "positive_called_subset_with_side_effect_audit"
                repair_kind = "safety"
            elif outcome_shortfall_alarm_families:
                decision = "diagnostic_alarm"
                reason = "low_task_outcome_not_tool_attributable"
            elif stats.called_count >= 2 and (
                (called_outcome is not None and called_outcome > 0.05)
                or (called_score is not None and called_score > 0.05)
            ):
                decision = "retain"
                reason = "positive_called_subset"
            elif metadata_repair_families:
                decision = "adoption_repair"
                reason = "visible_not_called_repeatedly"
                repair_kind = "metadata"
            elif stats.called_count == 1 and (
                (called_outcome is not None and called_outcome > 0.05)
                or (called_score is not None and called_score > 0.05)
            ):
                decision = "keep_sparse_positive"
                reason = "single_positive_called_event"
            row["decision"] = decision
            row["decision_reason"] = reason
            row["repair_kind"] = repair_kind
            row["routing_disposition"] = routing_disposition
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
        _atomic_write_json(
            self.output_dir / "self_evolution_reflection_state.json",
            payload,
        )
        registry_state_path = self.store.root / "tool_lifecycle.json"
        _atomic_write_json(
            registry_state_path,
            {
                "artifact_type": "self_evolution_tool_lifecycle",
                "source_run": str(self.output_dir),
                "tool_lifecycle": payload["tool_lifecycle"],
            },
        )
