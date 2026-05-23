"""Environment-neutral SAGE lifecycle controller."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any, cast

from sage_agent.gap_mining import mine_gap_signals
from sage_agent.integrity import (
    IntegrityReport,
    ResearchIntegrityPolicy,
    check_gap_signal,
    check_helper_candidate,
    check_profile,
    check_task_specs,
    merge_reports,
)
from sage_agent.interfaces import (
    EnvironmentAdapter,
    EnvironmentProfile,
    GapSignal,
    HelperGenerator,
    HelperRecord,
    HelperRepairGenerator,
    HelperValidationReport,
    TaskRunResult,
)
from sage_agent.lifecycle import assess_helper_lifecycle
from sage_agent.registry import LocalSAGERegistry
from sage_agent.validation import validate_helper_candidate


@dataclass(frozen=True)
class SAGEConfig:
    """Standalone SAGE run configuration."""

    model: str = "gpt-4o-mini"
    max_new_tools: int = 4
    max_new_tools_per_task: int = 2
    min_gap_severity: float = 0.2
    registry_dir: Path = Path(".sage_agent_registry")
    stop_after_first_birth: bool = False
    repair_attempts: int = 1
    max_refinements: int = 2
    retry_birth_task_with_new_tool: bool = True
    defer_birth_task_retries: bool = False
    stop_task_gap_processing_after_successful_retry: bool = True
    min_uses_before_lifecycle_action: int = 6
    weak_helper_success_rate: float = 0.25
    failed_repair_limit_before_parking: int = 2
    enable_generic_gap_mining: bool = True
    max_gap_signals_per_task: int = 4
    integrity_policy: ResearchIntegrityPolicy = field(
        default_factory=ResearchIntegrityPolicy
    )


@dataclass(frozen=True)
class SAGERunSummary:
    """Compact run summary for smoke validation and dashboards."""

    environment: str
    tasks_seen: int
    tasks_succeeded: int
    gaps_observed: int
    tools_born: int
    tools_accepted: int
    tools_rejected: int
    tools_reused: int
    repair_attempts: int
    tools_refined: int
    birth_task_retries: int
    birth_task_retry_successes: int
    model: str
    registry_path: str
    integrity_passed: bool
    integrity_issues: int
    lifecycle_decisions: tuple[dict[str, Any], ...] = ()
    events: tuple[dict[str, Any], ...] = ()


@dataclass
class SAGEAgent:
    """A standalone self-evolving SAGE agent."""

    adapter: EnvironmentAdapter
    generator: HelperGenerator
    config: SAGEConfig = field(default_factory=SAGEConfig)

    def __post_init__(self) -> None:
        self.registry = LocalSAGERegistry(self.config.registry_dir)

    def run(self, *, limit: int | None = None) -> SAGERunSummary:
        """Run SAGE on an arbitrary environment adapter."""

        self.adapter.prepare()
        profile = self.adapter.profile()
        tasks = self.adapter.tasks(limit=limit)
        integrity_report = merge_reports(
            check_profile(profile, self.config.integrity_policy),
            check_task_specs(tasks, self.config.integrity_policy),
        )
        integrity_report.raise_for_issues()
        records = self.registry.load()
        generated_gap_keys = {
            record.birth_gap_key for record in records.values() if not record.retired
        }
        generated_tool_names = {
            name for name, record in records.items() if not record.retired
        }
        events: list[dict[str, Any]] = []
        tasks_seen = 0
        tasks_succeeded = 0
        gaps_observed = 0
        tools_born = 0
        tools_accepted = 0
        tools_rejected = 0
        tools_reused = 0
        repair_attempts = 0
        tools_refined = 0
        birth_task_retries = 0
        birth_task_retry_successes = 0
        failed_repairs: dict[str, int] = {}

        for task in tasks:
            visible = self.adapter.route_helpers(task, records)
            helper_bundle = {
                name: records[name]
                for name in visible
                if name in records and not records[name].retired
            }
            result = self.adapter.run_task(task, helper_bundle)
            tasks_seen += 1
            tasks_succeeded += int(result.success)
            task_counted_success = result.success
            tools_reused += _record_reuse_events(self.registry, helper_bundle, result)
            events.append(
                _task_result_event(
                    task_id=task.task_id,
                    result=result,
                    visible_helpers=visible,
                )
            )
            adapter_gap = self.adapter.observe_gap(task, result, records)
            gap_candidates = _gap_candidates(
                adapter_gap=adapter_gap,
                config=self.config,
                profile=profile,
                task=task,
                result=result,
                helper_bundle=helper_bundle,
            )
            stop_after_this_task = False
            stop_gap_processing_for_task = False
            tools_born_this_task = 0
            pending_retry_tools: list[str] = []
            for gap in gap_candidates:
                gap_integrity = check_gap_signal(gap, self.config.integrity_policy)
                integrity_report = merge_reports(integrity_report, gap_integrity)
                gap_integrity.raise_for_issues()
                gaps_observed += 1
                events.append(_gap_event(gap))
                if gap.severity < self.config.min_gap_severity:
                    continue
                active_gap_already_has_helper = gap.key in generated_gap_keys or (
                    gap.suggested_tool_name
                    and gap.suggested_tool_name in generated_tool_names
                )
                if active_gap_already_has_helper:
                    parked_existing_tool = False
                    existing_for_gap = _find_existing_helper_for_gap(records, gap)
                    can_refine_existing = (
                        existing_for_gap is not None
                        and _should_refine_existing_helper(
                            existing_for_gap[1], config=self.config
                        )
                    )
                    if (
                        tools_refined < self.config.max_refinements
                        and can_refine_existing
                    ):
                        refinement = _refine_existing_helper(
                            generator=self.generator,
                            registry=self.registry,
                            records=records,
                            gap=gap,
                            profile=profile,
                            validation_cases=self.adapter.validation_cases_for_gap(gap),
                            model=self.config.model,
                            result=result,
                            policy=self.config.integrity_policy,
                            integrity_report=integrity_report,
                        )
                        integrity_report = refinement.integrity_report
                        events.extend(refinement.events)
                        if refinement.accepted_tool_name:
                            tools_refined += 1
                            repair_attempts += 1
                            failed_repairs.pop(refinement.replaced_tool_name, None)
                            records = self.registry.load()
                            generated_gap_keys = {
                                record.birth_gap_key
                                for record in records.values()
                                if not record.retired
                            }
                            generated_tool_names = {
                                name
                                for name, record in records.items()
                                if not record.retired
                            }
                            if (
                                self.config.retry_birth_task_with_new_tool
                                and self.config.defer_birth_task_retries
                            ):
                                pending_retry_tools.append(
                                    refinement.accepted_tool_name
                                )
                                helper_bundle = _retry_bundle(
                                    records=records,
                                    helper_bundle=helper_bundle,
                                    new_tool_name=refinement.accepted_tool_name,
                                )
                                events.append(
                                    _deferred_retry_event(
                                        event_name="refined_tool_task_retry_deferred",
                                        task_id=task.task_id,
                                        tool_name=refinement.accepted_tool_name,
                                        visible_helpers=tuple(helper_bundle),
                                    )
                                )
                            elif self.config.retry_birth_task_with_new_tool:
                                retry_bundle = _retry_bundle(
                                    records=records,
                                    helper_bundle=helper_bundle,
                                    new_tool_name=refinement.accepted_tool_name,
                                )
                                retry_result = self.adapter.run_task(task, retry_bundle)
                                helper_bundle = retry_bundle
                                birth_task_retries += 1
                                birth_task_retry_successes += int(retry_result.success)
                                tools_reused += _record_reuse_events(
                                    self.registry, retry_bundle, retry_result
                                )
                                if retry_result.success and not task_counted_success:
                                    tasks_succeeded += 1
                                    task_counted_success = True
                                if (
                                    retry_result.success
                                    and self.config.stop_task_gap_processing_after_successful_retry
                                ):
                                    stop_gap_processing_for_task = True
                                events.append(
                                    _task_retry_event(
                                        event_name="refined_tool_task_retry",
                                        task_id=task.task_id,
                                        tool_name=refinement.accepted_tool_name,
                                        result=retry_result,
                                        visible_helpers=tuple(retry_bundle),
                                    )
                                )
                                if stop_gap_processing_for_task:
                                    break
                        elif refinement.replaced_tool_name:
                            name = refinement.replaced_tool_name
                            failed_repairs[name] = failed_repairs.get(name, 0) + 1
                            records = self.registry.load()
                            record = records.get(name)
                            if record and _should_park_failed_helper(
                                record,
                                failed_repairs=failed_repairs[name],
                                config=self.config,
                            ):
                                if self.registry.retire(name):
                                    parked_existing_tool = True
                                    events.append(
                                        {
                                            "event": "tool_parked",
                                            "tool_name": name,
                                            "gap_key": record.birth_gap_key,
                                            "task_id": task.task_id,
                                            "uses": record.uses,
                                            "successes": record.successes,
                                            "success_rate": _success_rate(record),
                                            "failed_repairs": failed_repairs[name],
                                            "reason": (
                                                "weak natural reuse evidence and "
                                                "repeated failed redesign attempts"
                                            ),
                                        }
                                    )
                                    records = self.registry.load()
                                    generated_gap_keys = {
                                        active.birth_gap_key
                                        for active in records.values()
                                        if not active.retired
                                    }
                                    generated_tool_names = {
                                        tool_name
                                        for tool_name, active in records.items()
                                        if not active.retired
                                    }
                    events.append(
                        {
                            "event": "tool_generation_skipped_existing",
                            "gap_key": gap.key,
                            "task_id": task.task_id,
                            "tool_name": gap.suggested_tool_name or "",
                            "active_helper_remains": not parked_existing_tool,
                        }
                    )
                    if not parked_existing_tool:
                        continue
                    gap = _redesign_gap(gap, failed_repairs=failed_repairs)
                if tools_born >= self.config.max_new_tools:
                    continue
                if tools_born_this_task >= self.config.max_new_tools_per_task:
                    continue
                candidate = self.generator.generate(
                    gap,
                    profile,
                    self.adapter.validation_cases_for_gap(gap),
                    model=self.config.model,
                )
                tools_born += 1
                tools_born_this_task += 1
                candidate_integrity = check_helper_candidate(
                    candidate, gap, self.config.integrity_policy
                )
                integrity_report = merge_reports(integrity_report, candidate_integrity)
                validation = _integrity_or_validation(candidate_integrity, candidate)
                for attempt in range(self.config.repair_attempts):
                    if validation.accepted or not _supports_repair(self.generator):
                        break
                    repair_attempts += 1
                    candidate = cast(HelperRepairGenerator, self.generator).repair(
                        gap,
                        profile,
                        candidate,
                        validation.errors,
                        self.adapter.validation_cases_for_gap(gap),
                        model=self.config.model,
                    )
                    candidate_integrity = check_helper_candidate(
                        candidate, gap, self.config.integrity_policy
                    )
                    integrity_report = merge_reports(
                        integrity_report, candidate_integrity
                    )
                    validation = _integrity_or_validation(
                        candidate_integrity, candidate
                    )
                    events.append(
                        {
                            "event": "tool_repair",
                            "tool_name": candidate.spec.name,
                            "attempt": attempt + 1,
                            "accepted": validation.accepted,
                            "errors": list(validation.errors),
                        }
                    )
                events.append(
                    {
                        "event": "tool_birth",
                        "tool_name": candidate.spec.name,
                        "accepted": validation.accepted,
                        "errors": list(validation.errors),
                        "cases": validation.cases_run,
                    }
                )
                if validation.accepted:
                    self.registry.add(
                        candidate,
                        validation,
                        birth_gap_key=gap.key,
                        birth_environment=profile.name,
                    )
                    records = self.registry.load()
                    generated_gap_keys.add(gap.key)
                    generated_tool_names.add(candidate.spec.name)
                    tools_accepted += 1
                    if (
                        self.config.retry_birth_task_with_new_tool
                        and self.config.defer_birth_task_retries
                    ):
                        pending_retry_tools.append(candidate.spec.name)
                        helper_bundle = _retry_bundle(
                            records=records,
                            helper_bundle=helper_bundle,
                            new_tool_name=candidate.spec.name,
                        )
                        events.append(
                            _deferred_retry_event(
                                event_name="birth_task_retry_deferred",
                                task_id=task.task_id,
                                tool_name=candidate.spec.name,
                                visible_helpers=tuple(helper_bundle),
                            )
                        )
                    elif self.config.retry_birth_task_with_new_tool:
                        retry_bundle = _retry_bundle(
                            records=records,
                            helper_bundle=helper_bundle,
                            new_tool_name=candidate.spec.name,
                        )
                        retry_result = self.adapter.run_task(task, retry_bundle)
                        helper_bundle = retry_bundle
                        birth_task_retries += 1
                        birth_task_retry_successes += int(retry_result.success)
                        tools_reused += _record_reuse_events(
                            self.registry, retry_bundle, retry_result
                        )
                        if retry_result.success and not task_counted_success:
                            tasks_succeeded += 1
                            task_counted_success = True
                        if (
                            retry_result.success
                            and self.config.stop_task_gap_processing_after_successful_retry
                        ):
                            stop_gap_processing_for_task = True
                        events.append(
                            _task_retry_event(
                                event_name="birth_task_retry",
                                task_id=task.task_id,
                                tool_name=candidate.spec.name,
                                result=retry_result,
                                visible_helpers=tuple(retry_bundle),
                            )
                        )
                        if stop_gap_processing_for_task:
                            break
                    if self.config.stop_after_first_birth:
                        stop_after_this_task = True
                        break
                else:
                    tools_rejected += 1
            if (
                pending_retry_tools
                and self.config.retry_birth_task_with_new_tool
                and self.config.defer_birth_task_retries
            ):
                retry_result = self.adapter.run_task(task, helper_bundle)
                birth_task_retries += 1
                birth_task_retry_successes += int(retry_result.success)
                tools_reused += _record_reuse_events(
                    self.registry, helper_bundle, retry_result
                )
                if retry_result.success and not task_counted_success:
                    tasks_succeeded += 1
                    task_counted_success = True
                events.append(
                    _task_retry_event(
                        event_name="deferred_birth_task_retry",
                        task_id=task.task_id,
                        tool_name=",".join(pending_retry_tools),
                        result=retry_result,
                        visible_helpers=tuple(helper_bundle),
                    )
                )
            if stop_after_this_task:
                break

        final_records = self.registry.load()
        return SAGERunSummary(
            environment=profile.name,
            tasks_seen=tasks_seen,
            tasks_succeeded=tasks_succeeded,
            gaps_observed=gaps_observed,
            tools_born=tools_born,
            tools_accepted=tools_accepted,
            tools_rejected=tools_rejected,
            tools_reused=tools_reused,
            repair_attempts=repair_attempts,
            tools_refined=tools_refined,
            birth_task_retries=birth_task_retries,
            birth_task_retry_successes=birth_task_retry_successes,
            model=self.config.model,
            registry_path=str(self.registry.manifest_path),
            lifecycle_decisions=tuple(
                item.to_json() for item in assess_helper_lifecycle(final_records)
            ),
            integrity_passed=integrity_report.passed,
            integrity_issues=len(integrity_report.issues),
            events=tuple(events),
        )


@dataclass(frozen=True)
class _RefinementResult:
    accepted_tool_name: str
    replaced_tool_name: str
    integrity_report: IntegrityReport
    events: tuple[dict[str, Any], ...]


def _gap_candidates(
    *,
    adapter_gap: GapSignal | None,
    config: SAGEConfig,
    profile: EnvironmentProfile,
    task: Any,
    result: TaskRunResult,
    helper_bundle: dict[str, HelperRecord],
) -> tuple[GapSignal, ...]:
    gaps: list[GapSignal] = []
    if adapter_gap is not None:
        gaps.append(adapter_gap)
    if config.enable_generic_gap_mining:
        gaps.extend(
            mine_gap_signals(
                profile=profile,
                task=task,
                result=result,
                helpers=helper_bundle,
                base_gap=adapter_gap,
            )
        )
    unique: list[GapSignal] = []
    seen: set[tuple[str, str]] = set()
    for gap in gaps:
        identity = (gap.key, gap.suggested_tool_name or "")
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(gap)
        if len(unique) >= config.max_gap_signals_per_task:
            break
    return tuple(unique)


def _retry_bundle(
    *,
    records: dict[str, HelperRecord],
    helper_bundle: dict[str, HelperRecord],
    new_tool_name: str,
) -> dict[str, HelperRecord]:
    retry = dict(helper_bundle)
    if new_tool_name in records and not records[new_tool_name].retired:
        retry[new_tool_name] = records[new_tool_name]
    return retry


def _refine_existing_helper(
    *,
    generator: HelperGenerator,
    registry: LocalSAGERegistry,
    records: dict[str, HelperRecord],
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[Any, ...],
    model: str,
    result: TaskRunResult,
    policy: ResearchIntegrityPolicy,
    integrity_report: IntegrityReport,
) -> _RefinementResult:
    if not _supports_repair(generator):
        return _RefinementResult("", "", integrity_report, ())
    existing = _find_existing_helper_for_gap(records, gap)
    if existing is None:
        return _RefinementResult("", "", integrity_report, ())
    name, record = existing
    errors = (
        "accepted_helper_underperformed_on_natural_reuse",
        f"task_success:{result.success}",
        f"task_score:{result.score}",
        f"task_error:{result.error[:240]}",
        "transcript:" + " | ".join(result.transcript[-4:])[:800],
    )
    candidate = cast(HelperRepairGenerator, generator).repair(
        gap,
        profile,
        record.candidate,
        errors,
        validation_cases,
        model=model,
    )
    candidate_integrity = check_helper_candidate(candidate, gap, policy)
    integrity_report = merge_reports(integrity_report, candidate_integrity)
    validation = _integrity_or_validation(candidate_integrity, candidate)
    event = {
        "event": "tool_refinement",
        "tool_name": candidate.spec.name,
        "replaced_tool_name": name,
        "accepted": validation.accepted,
        "errors": list(validation.errors),
        "cases": validation.cases_run,
    }
    if not validation.accepted:
        return _RefinementResult("", name, integrity_report, (event,))
    code_hash = hashlib.sha256(candidate.code.encode("utf-8")).hexdigest()
    if code_hash == record.code_hash:
        event = {
            **event,
            "accepted": False,
            "errors": ["refinement_no_code_change"],
        }
        return _RefinementResult("", name, integrity_report, (event,))
    registry.add(
        candidate,
        validation,
        birth_gap_key=gap.key,
        birth_environment=profile.name,
    )
    return _RefinementResult(candidate.spec.name, name, integrity_report, (event,))


def _find_existing_helper_for_gap(
    records: dict[str, HelperRecord], gap: GapSignal
) -> tuple[str, HelperRecord] | None:
    if gap.suggested_tool_name:
        record = records.get(gap.suggested_tool_name)
        if record is not None and not record.retired:
            return gap.suggested_tool_name, record
    for name, record in records.items():
        if not record.retired and record.birth_gap_key == gap.key:
            return name, record
    return None


def _record_reuse_events(
    registry: LocalSAGERegistry,
    helpers: dict[str, HelperRecord],
    result: TaskRunResult,
) -> int:
    count = 0
    for use in result.tool_uses:
        if not use.generated_helper or use.tool_name not in helpers:
            continue
        registry.record_use(use.tool_name, success=use.success and result.success)
        count += 1
    return count


def _task_result_event(
    *,
    task_id: str,
    result: TaskRunResult,
    visible_helpers: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "event": "task",
        "task_id": task_id,
        "name": result.task.name,
        "success": result.success,
        "score": result.score,
        "outcome_score": (
            result.outcome_score if result.outcome_score is not None else result.score
        ),
        "error": result.error,
        "visible_helpers": list(visible_helpers),
        "transcript": list(result.transcript),
        "tool_uses": _json_safe([asdict(use) for use in result.tool_uses]),
        "artifacts": _json_safe(result.artifacts),
    }


def _task_retry_event(
    *,
    event_name: str,
    task_id: str,
    tool_name: str,
    result: TaskRunResult,
    visible_helpers: tuple[str, ...],
) -> dict[str, Any]:
    event = _task_result_event(
        task_id=task_id,
        result=result,
        visible_helpers=visible_helpers,
    )
    event["event"] = event_name
    event["tool_name"] = tool_name
    return event


def _deferred_retry_event(
    *,
    event_name: str,
    task_id: str,
    tool_name: str,
    visible_helpers: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "event": event_name,
        "task_id": task_id,
        "tool_name": tool_name,
        "visible_helpers": list(visible_helpers),
        "success": False,
        "score": 0.0,
        "outcome_score": 0.0,
        "error": "",
        "transcript": ["retry deferred until current task gap batch is complete"],
        "tool_uses": [],
        "artifacts": {},
    }


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _gap_event(gap: GapSignal) -> dict[str, Any]:
    return {
        "event": "gap",
        "gap_key": gap.key,
        "task_id": gap.source_task_id,
        "summary": gap.summary,
        "severity": gap.severity,
        "suggested_tool_name": gap.suggested_tool_name,
    }


def _supports_repair(generator: HelperGenerator) -> bool:
    return callable(getattr(generator, "repair", None))


def _should_park_failed_helper(
    record: HelperRecord, *, failed_repairs: int, config: SAGEConfig
) -> bool:
    """Return true when a weak helper should stop being naturally routed."""

    if record.uses < config.min_uses_before_lifecycle_action:
        return False
    if failed_repairs < config.failed_repair_limit_before_parking:
        return False
    return _success_rate(record) < config.weak_helper_success_rate


def _should_refine_existing_helper(record: HelperRecord, *, config: SAGEConfig) -> bool:
    """Return true when natural-use evidence is mature enough to redesign."""

    if record.uses < config.min_uses_before_lifecycle_action:
        return False
    return _success_rate(record) < config.weak_helper_success_rate


def _success_rate(record: HelperRecord) -> float:
    if record.uses <= 0:
        return 0.0
    return record.successes / record.uses


def _redesign_gap(gap: GapSignal, *, failed_repairs: dict[str, int]) -> GapSignal:
    """Re-open a parked gap for a distinct redesign candidate."""

    base_name = gap.suggested_tool_name or _safe_tool_name(gap.key)
    version = max(failed_repairs.values() or (1,)) + 1
    directives = dict(gap.generation_directives)
    directives.update(
        {
            "redesign_after_failed_repair": True,
            "parked_tool_name": base_name,
            "redesign_version": version,
        }
    )
    return dataclass_replace(
        gap,
        suggested_tool_name=f"{base_name}_redesign_v{version}",
        generation_directives=directives,
    )


def _safe_tool_name(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "generated_helper"


def _integrity_or_validation(
    report: IntegrityReport, candidate: Any
) -> HelperValidationReport:
    if report.passed:
        return validate_helper_candidate(candidate)
    return HelperValidationReport(
        accepted=False,
        errors=tuple(
            f"integrity:{issue.location}:{issue.kind}:{issue.detail}"
            for issue in report.issues
        ),
        cases_run=0,
        cases_passed=0,
        runtime_smoke_passed=False,
        side_effect_free=False,
    )
