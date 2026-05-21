"""Environment-neutral SAGE lifecycle controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

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
    min_gap_severity: float = 0.2
    registry_dir: Path = Path(".sage_agent_registry")
    stop_after_first_birth: bool = False
    repair_attempts: int = 1
    retry_birth_task_with_new_tool: bool = True
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
        birth_task_retries = 0
        birth_task_retry_successes = 0

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
            tools_reused += _record_reuse_events(self.registry, helper_bundle, result)
            events.append(
                {
                    "event": "task",
                    "task_id": task.task_id,
                    "success": result.success,
                    "visible_helpers": list(visible),
                }
            )
            gap = self.adapter.observe_gap(task, result, records)
            if gap is None:
                continue
            gap_integrity = check_gap_signal(gap, self.config.integrity_policy)
            integrity_report = merge_reports(integrity_report, gap_integrity)
            gap_integrity.raise_for_issues()
            gaps_observed += 1
            events.append(_gap_event(gap))
            if (
                gap.severity < self.config.min_gap_severity
                or tools_born >= self.config.max_new_tools
            ):
                continue
            if gap.key in generated_gap_keys or (
                gap.suggested_tool_name
                and gap.suggested_tool_name in generated_tool_names
            ):
                events.append(
                    {
                        "event": "tool_generation_skipped_existing",
                        "gap_key": gap.key,
                        "task_id": task.task_id,
                        "tool_name": gap.suggested_tool_name or "",
                    }
                )
                continue
            candidate = self.generator.generate(
                gap,
                profile,
                self.adapter.validation_cases_for_gap(gap),
                model=self.config.model,
            )
            tools_born += 1
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
                integrity_report = merge_reports(integrity_report, candidate_integrity)
                validation = _integrity_or_validation(candidate_integrity, candidate)
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
                if self.config.retry_birth_task_with_new_tool:
                    retry_bundle = {candidate.spec.name: records[candidate.spec.name]}
                    retry_result = self.adapter.run_task(task, retry_bundle)
                    birth_task_retries += 1
                    birth_task_retry_successes += int(retry_result.success)
                    tools_reused += _record_reuse_events(
                        self.registry, retry_bundle, retry_result
                    )
                    if retry_result.success and not result.success:
                        tasks_succeeded += 1
                    events.append(
                        {
                            "event": "birth_task_retry",
                            "task_id": task.task_id,
                            "tool_name": candidate.spec.name,
                            "success": retry_result.success,
                        }
                    )
                if self.config.stop_after_first_birth:
                    break
            else:
                tools_rejected += 1

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
