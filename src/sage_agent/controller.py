"""Environment-neutral SAGE lifecycle controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sage_agent.interfaces import (
    EnvironmentAdapter,
    GapSignal,
    HelperGenerator,
    HelperRecord,
    TaskRunResult,
)
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


@dataclass(frozen=True)
class SAGERunSummary:
    """Compact run summary for smoke validation and dashboards."""

    environment: str
    tasks_seen: int
    tasks_succeeded: int
    gaps_observed: int
    tools_born: int
    tools_accepted: int
    tools_reused: int
    model: str
    registry_path: str
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
        records = self.registry.load()
        events: list[dict[str, Any]] = []
        tasks_seen = 0
        tasks_succeeded = 0
        gaps_observed = 0
        tools_born = 0
        tools_accepted = 0
        tools_reused = 0

        for task in self.adapter.tasks(limit=limit):
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
            gaps_observed += 1
            events.append(_gap_event(gap))
            if (
                gap.severity < self.config.min_gap_severity
                or tools_born >= self.config.max_new_tools
            ):
                continue
            candidate = self.generator.generate(
                gap,
                profile,
                self.adapter.validation_cases_for_gap(gap),
                model=self.config.model,
            )
            tools_born += 1
            validation = validate_helper_candidate(candidate)
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
                tools_accepted += 1
                if self.config.stop_after_first_birth:
                    break

        return SAGERunSummary(
            environment=profile.name,
            tasks_seen=tasks_seen,
            tasks_succeeded=tasks_succeeded,
            gaps_observed=gaps_observed,
            tools_born=tools_born,
            tools_accepted=tools_accepted,
            tools_reused=tools_reused,
            model=self.config.model,
            registry_path=str(self.registry.manifest_path),
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
