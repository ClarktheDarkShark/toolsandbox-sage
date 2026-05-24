"""Import-mode SAGE boundary for external benchmark harnesses.

``SAGEAgent`` owns task execution through an ``EnvironmentAdapter``. Many
benchmarks already have a runner, simulator, scorer, retry policy, and dashboard
path. ``SAGEImportAgent`` is the thinner boundary for those harnesses: it
selects retained helpers before a task, renders them into harness-consumable
guidance, observes the official result after the task, and updates the same
SAGE registry/lifecycle without requiring the harness to become an adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sage_agent.gap_mining import mine_gap_signals
from sage_agent.integrity import (
    ResearchIntegrityPolicy,
    check_gap_signal,
    check_helper_candidate,
    check_profile,
    check_task_specs,
)
from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperGenerator,
    HelperRecord,
    HelperSpec,
    HelperValidationReport,
    ImportTaskContext,
    ImportTaskObservation,
    SAGEActionReview,
    SAGEGuidance,
    SAGEImportUpdate,
    TaskRunResult,
    TaskSpec,
    ValidationCase,
)
from sage_agent.registry import LocalSAGERegistry
from sage_agent.validation import validate_helper_candidate


@dataclass(frozen=True)
class SAGEImportConfig:
    """Configuration for SAGE import mode."""

    model: str = "gpt-4o-mini"
    registry_dir: Path = Path(".sage_import_registry")
    active_helpers: int = 3
    max_new_helpers: int = 8
    max_new_helpers_per_task: int = 2
    repair_attempts: int = 1
    retry_policy: str = "next_task_only"
    min_uses_before_lifecycle_action: int = 3
    weak_helper_success_rate: float = 0.25
    prompt_guidance_fallback: bool = False
    integrity_policy: ResearchIntegrityPolicy = field(
        default_factory=ResearchIntegrityPolicy
    )


@dataclass
class SAGEImportAgent:
    """Drop-in SAGE lifecycle for a host-owned task runner."""

    environment_profile: EnvironmentProfile
    registry_dir: Path
    generator: HelperGenerator
    config: SAGEImportConfig = field(default_factory=SAGEImportConfig)

    def __post_init__(self) -> None:
        base_config = self.config
        if base_config.registry_dir != self.registry_dir:
            base_config = SAGEImportConfig(
                model=base_config.model,
                registry_dir=self.registry_dir,
                active_helpers=base_config.active_helpers,
                max_new_helpers=base_config.max_new_helpers,
                max_new_helpers_per_task=base_config.max_new_helpers_per_task,
                repair_attempts=base_config.repair_attempts,
                retry_policy=base_config.retry_policy,
                min_uses_before_lifecycle_action=base_config.min_uses_before_lifecycle_action,
                weak_helper_success_rate=base_config.weak_helper_success_rate,
                prompt_guidance_fallback=base_config.prompt_guidance_fallback,
                integrity_policy=base_config.integrity_policy,
            )
        self.config = base_config
        self.registry = LocalSAGERegistry(self.registry_dir)
        self._visible_by_task: dict[str, tuple[str, ...]] = {}
        self._events: list[dict[str, Any]] = []
        check_profile(
            self.environment_profile, self.config.integrity_policy
        ).raise_for_issues()

    @property
    def events(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._events)

    def before_task(self, task_context: ImportTaskContext) -> SAGEGuidance:
        """Select retained helpers and render guidance for the host harness."""

        task = _task_from_context(task_context)
        check_task_specs((task,), self.config.integrity_policy).raise_for_issues()
        records = self.registry.load()
        visible = _route_import_helpers(
            task,
            records,
            active_helpers=max(0, self.config.active_helpers),
        )
        self._visible_by_task[task.task_id] = visible
        guidance = _render_guidance(
            profile=self.environment_profile,
            task=task,
            records={name: records[name] for name in visible if name in records},
        )
        event = {
            "event": "helper_visibility",
            "task_id": task.task_id,
            "visible_helpers": list(visible),
            "helper_count": len(visible),
        }
        self._events.append(event)
        return guidance

    def before_step(
        self,
        task_context: ImportTaskContext,
        transcript: Sequence[str],
    ) -> SAGEGuidance:
        """Refresh retained-helper guidance inside a host-owned task loop.

        Some benchmark harnesses cannot expose SAGE as a callable tool, but they
        can rebuild the agent prompt before each turn. This method gives those
        harnesses the same retained-helper execution path used by ``before_task``
        while adding the visible conversation so deterministic helpers can react
        to mid-task policy changes, failed command output, or newly observed
        user constraints.
        """

        metadata = dict(task_context.metadata)
        metadata["last_transcript"] = "\n".join(str(line) for line in transcript[-16:])
        step_context = ImportTaskContext(
            task_id=task_context.task_id,
            name=task_context.name,
            prompt=task_context.prompt,
            artifacts=task_context.artifacts,
            metadata=metadata,
        )
        task = _task_from_context(step_context)
        check_task_specs((task,), self.config.integrity_policy).raise_for_issues()
        records = self.registry.load()
        visible = _route_import_helpers(
            task,
            records,
            active_helpers=max(0, self.config.active_helpers),
        )
        self._visible_by_task[task.task_id] = visible
        guidance = _render_guidance(
            profile=self.environment_profile,
            task=task,
            records={name: records[name] for name in visible if name in records},
        )
        self._events.append(
            {
                "event": "helper_visibility_step",
                "task_id": task.task_id,
                "visible_helpers": list(visible),
                "helper_count": len(visible),
            }
        )
        return guidance

    def review_action(
        self,
        task_context: ImportTaskContext,
        transcript: Sequence[str],
        proposed_actions: Sequence[Mapping[str, Any]],
    ) -> SAGEActionReview:
        """Review host-proposed side-effecting actions against helper outputs.

        This is optional for host harnesses. When a harness can intercept an
        actor's proposed tool call before execution, SAGE can apply retained
        helper outputs as a generic safety/precondition guard. The guard does
        not invent labels or expected answers; it only blocks a proposed
        side-effecting action when the current visible helper output recommends
        transfer/escalation or abstention from visible context.
        """

        guidance = self.before_step(task_context, transcript)
        helper_outputs_raw = guidance.metadata.get("helper_outputs", ())
        helper_outputs: tuple[Mapping[str, Any], ...] = tuple(
            item
            for item in helper_outputs_raw
            if isinstance(item, Mapping) and isinstance(item.get("output"), Mapping)
        )
        action_names = tuple(
            name
            for name in (_action_name(action) for action in proposed_actions)
            if name
        )
        side_effecting = tuple(
            name for name in action_names if _looks_side_effecting_action(name)
        )
        if not side_effecting:
            return SAGEActionReview(
                allowed=True,
                visible_helpers=guidance.visible_helpers,
                helper_outputs=helper_outputs,
            )
        for helper_output in helper_outputs:
            output = helper_output.get("output")
            if not isinstance(output, Mapping):
                continue
            if output.get("abstain") is True:
                reason = str(output.get("abstain_reason") or "helper_abstain")
                review = SAGEActionReview(
                    allowed=False,
                    reason=reason,
                    guidance=_action_review_guidance(output, reason=reason),
                    visible_helpers=guidance.visible_helpers,
                    helper_outputs=helper_outputs,
                )
                self._events.append(
                    _action_review_event(task_context, action_names, review)
                )
                return review
            if output.get("should_transfer") is True:
                unsafe_side_effecting = tuple(
                    name
                    for name in side_effecting
                    if not _looks_transfer_or_escalation_action(name)
                )
                if not unsafe_side_effecting:
                    continue
                reason = "helper_recommends_transfer_or_escalation"
                review = SAGEActionReview(
                    allowed=False,
                    reason=reason,
                    guidance=_action_review_guidance(output, reason=reason),
                    visible_helpers=guidance.visible_helpers,
                    helper_outputs=helper_outputs,
                )
                self._events.append(
                    _action_review_event(task_context, action_names, review)
                )
                return review
        return SAGEActionReview(
            allowed=True,
            visible_helpers=guidance.visible_helpers,
            helper_outputs=helper_outputs,
        )

    def after_task(
        self,
        task_context: ImportTaskContext,
        result_observation: ImportTaskObservation,
    ) -> SAGEImportUpdate:
        """Observe an official task result and update SAGE lifecycle state."""

        task = _task_from_context(task_context)
        check_task_specs((task,), self.config.integrity_policy).raise_for_issues()
        visible = self._visible_by_task.get(task.task_id, ())
        result = _result_from_observation(task, result_observation)
        records = self.registry.load()
        active_records = {
            name: record for name, record in records.items() if not record.retired
        }
        for name in visible:
            if name in active_records:
                self.registry.record_use(name, success=result.success)
        for use in result.tool_uses:
            if use.generated_helper and use.tool_name in active_records:
                self.registry.record_use(
                    use.tool_name, success=use.success and result.success
                )

        accepted: list[str] = []
        rejected: list[str] = []
        events: list[dict[str, Any]] = [
            _task_result_event(result, visible_helpers=visible)
        ]
        self._retire_weak_helpers(events)

        helper_birth_decision = _helper_birth_decision(result)
        if (
            not result.success
            and helper_birth_decision == "generate"
            and _active_helper_count(self.registry.load()) < self.config.max_new_helpers
        ):
            birth_events, accepted, rejected = self._run_full_birth_lifecycle(
                task=task,
                result=result,
                records=self.registry.load(),
            )
            events.extend(birth_events)
        elif not result.success and helper_birth_decision != "generate":
            events.append(
                {
                    "event": "tool_birth_skipped",
                    "task_id": task.task_id,
                    "reason": helper_birth_decision,
                    "error": result.error,
                }
            )

        retry_guidance: SAGEGuidance | None = None
        retry_recommended = False
        if accepted and self.config.retry_policy == "same_task":
            retry_recommended = True
            retry_guidance = self.before_task(
                _retry_context_with_observation(task_context, result)
            )
            events.append(
                {
                    "event": "same_task_retry_recommended",
                    "task_id": task.task_id,
                    "tool_name": ",".join(accepted),
                    "visible_helpers": list(retry_guidance.visible_helpers),
                    "reason": "new_helper_birth",
                }
            )
        elif not result.success and visible and self.config.retry_policy == "same_task":
            retry_recommended = True
            retry_guidance = self.before_task(
                _retry_context_with_observation(task_context, result)
            )
            events.append(
                {
                    "event": "same_task_retry_recommended",
                    "task_id": task.task_id,
                    "tool_name": ",".join(visible),
                    "visible_helpers": list(retry_guidance.visible_helpers),
                    "reason": "failed_visible_helper_context_refresh",
                }
            )

        self._events.extend(events)
        return SAGEImportUpdate(
            task_result=result,
            accepted_helpers=tuple(accepted),
            rejected_helpers=tuple(rejected),
            visible_helpers=visible,
            retry_recommended=retry_recommended,
            retry_guidance=retry_guidance,
            events=tuple(events),
        )

    def _run_full_birth_lifecycle(
        self,
        *,
        task: TaskSpec,
        result: TaskRunResult,
        records: Mapping[str, HelperRecord],
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """Generate, validate, repair, and retain full helpers for import mode."""

        events: list[dict[str, Any]] = []
        accepted: list[str] = []
        rejected: list[str] = []
        births_this_task = 0
        for gap in _import_gap_candidates(
            profile=self.environment_profile,
            task=task,
            result=result,
            records=records,
            registry=self.registry,
        ):
            if (
                _active_helper_count(self.registry.load())
                >= self.config.max_new_helpers
            ):
                break
            if births_this_task >= self.config.max_new_helpers_per_task:
                break
            if _active_gap_already_has_helper(self.registry.load(), gap):
                events.append(
                    {
                        "event": "tool_generation_skipped_existing",
                        "gap_key": gap.key,
                        "task_id": task.task_id,
                        "tool_name": gap.suggested_tool_name or "",
                    }
                )
                continue
            check_gap_signal(gap, self.config.integrity_policy).raise_for_issues()
            validation_cases = _import_validation_cases_for_gap(gap, result)
            candidate = self.generator.generate(
                gap,
                self.environment_profile,
                validation_cases,
                model=self.config.model,
            )
            validation = self._validate_generated_candidate(candidate, gap)
            for attempt in range(self.config.repair_attempts):
                if validation.accepted or not _supports_repair(self.generator):
                    break
                candidate = self.generator.repair(  # type: ignore[attr-defined]
                    gap,
                    self.environment_profile,
                    candidate,
                    validation.errors,
                    validation_cases,
                    model=self.config.model,
                )
                validation = self._validate_generated_candidate(candidate, gap)
                events.append(
                    {
                        "event": "tool_repair",
                        "tool_name": candidate.spec.name,
                        "helper_type": candidate.spec.helper_type,
                        "attempt": attempt + 1,
                        "accepted": validation.accepted,
                        "errors": list(validation.errors),
                    }
                )
            events.append(
                {
                    "event": "tool_birth",
                    "tool_name": candidate.spec.name,
                    "helper_type": candidate.spec.helper_type,
                    "family": candidate.spec.family,
                    "accepted": validation.accepted,
                    "errors": list(validation.errors),
                    "cases": validation.cases_run,
                    "task_id": task.task_id,
                    "gap_key": gap.key,
                }
            )
            births_this_task += 1
            if validation.accepted:
                self.registry.add(
                    candidate,
                    validation,
                    birth_gap_key=gap.key,
                    birth_environment=self.environment_profile.name,
                )
                accepted.append(candidate.spec.name)
            else:
                rejected.append(candidate.spec.name)
        if (
            not accepted
            and self.config.prompt_guidance_fallback
            and _active_helper_count(self.registry.load()) < self.config.max_new_helpers
        ):
            prompt_events, prompt_accepted, prompt_rejected = (
                self._run_prompt_guidance_fallback(task=task, result=result)
            )
            events.extend(prompt_events)
            accepted.extend(prompt_accepted)
            rejected.extend(prompt_rejected)
        return events, accepted, rejected

    def _validate_generated_candidate(
        self, candidate: HelperCandidate, gap: GapSignal
    ) -> HelperValidationReport:
        candidate_integrity = check_helper_candidate(
            candidate, gap, self.config.integrity_policy
        )
        integrity_errors = tuple(
            f"{issue.kind}:{issue.detail}" for issue in candidate_integrity.issues
        )
        if candidate.spec.helper_type == "prompt_guidance":
            return _validate_prompt_guidance_candidate(
                candidate, gap=gap, integrity_errors=integrity_errors
            )
        if integrity_errors:
            return HelperValidationReport(
                accepted=False,
                errors=integrity_errors,
                cases_run=0,
                cases_passed=0,
                runtime_smoke_passed=False,
                side_effect_free=False,
            )
        return validate_helper_candidate(candidate)

    def _run_prompt_guidance_fallback(
        self, *, task: TaskSpec, result: TaskRunResult
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        gap = _make_prompt_guidance_gap(
            profile=self.environment_profile,
            task=task,
            result=result,
            registry=self.registry,
        )
        check_gap_signal(gap, self.config.integrity_policy).raise_for_issues()
        candidate = _generate_prompt_guidance_candidate(
            generator=self.generator,
            gap=gap,
            profile=self.environment_profile,
            result=result,
            model=self.config.model,
        )
        validation = self._validate_generated_candidate(candidate, gap)
        event = {
            "event": "tool_birth",
            "tool_name": candidate.spec.name,
            "helper_type": candidate.spec.helper_type,
            "family": candidate.spec.family,
            "accepted": validation.accepted,
            "errors": list(validation.errors),
            "cases": validation.cases_run,
            "task_id": task.task_id,
            "gap_key": gap.key,
            "fallback": True,
        }
        if validation.accepted:
            self.registry.add(
                candidate,
                validation,
                birth_gap_key=gap.key,
                birth_environment=self.environment_profile.name,
            )
            return [event], [candidate.spec.name], []
        return [event], [], [candidate.spec.name]

    def _retire_weak_helpers(self, events: list[dict[str, Any]]) -> None:
        records = self.registry.load()
        for name, record in records.items():
            if record.retired:
                continue
            if record.uses < self.config.min_uses_before_lifecycle_action:
                continue
            success_rate = record.successes / record.uses if record.uses else 0.0
            if success_rate >= self.config.weak_helper_success_rate:
                continue
            if self.registry.retire(name):
                events.append(
                    {
                        "event": "tool_parked",
                        "tool_name": name,
                        "uses": record.uses,
                        "successes": record.successes,
                        "success_rate": success_rate,
                        "reason": "weak_import_mode_visibility_outcome_evidence",
                    }
                )


def paired_task_order(task_ids: Sequence[str], *, seed: int = 0) -> tuple[str, ...]:
    """Return a deterministic paired-run task order for host harnesses."""

    decorated = []
    for task_id in task_ids:
        digest = hashlib.sha256(f"{seed}:{task_id}".encode("utf-8")).hexdigest()
        decorated.append((digest, task_id))
    return tuple(task_id for _, task_id in sorted(decorated))


def _action_name(action: Mapping[str, Any]) -> str:
    function = action.get("function")
    if isinstance(function, Mapping) and function.get("name"):
        return str(function.get("name"))
    for key in ("name", "tool_name", "action"):
        value = action.get(key)
        if value:
            return str(value)
    return ""


def _looks_side_effecting_action(name: str) -> bool:
    lowered = name.lower()
    read_prefixes = (
        "get_",
        "list_",
        "search_",
        "find_",
        "lookup_",
        "check_",
        "read_",
        "view_",
        "query_",
    )
    if lowered.startswith(read_prefixes):
        return False
    side_effect_terms = (
        "add",
        "book",
        "buy",
        "cancel",
        "charge",
        "create",
        "delete",
        "issue",
        "modify",
        "pay",
        "purchase",
        "refund",
        "remove",
        "reserve",
        "schedule",
        "send",
        "set_",
        "transfer",
        "update",
        "write",
    )
    return any(term in lowered for term in side_effect_terms)


def _looks_transfer_or_escalation_action(name: str) -> bool:
    lowered = name.lower()
    return "transfer" in lowered or "escalat" in lowered or "human" in lowered


def _action_review_guidance(output: Mapping[str, Any], *, reason: str) -> str:
    safe_next = str(output.get("safe_next_step") or "").strip()
    missing = output.get("missing_preconditions")
    lines = [
        f"SAGE action review blocked the proposed side-effecting action: {reason}.",
    ]
    if safe_next:
        lines.append(f"Safe next step: {safe_next}")
    if isinstance(missing, list) and missing:
        lines.append(
            "Visible precondition risks: "
            + "; ".join(str(item) for item in missing[:4])
        )
    if output.get("should_transfer") is True:
        lines.append(
            "Use transfer/escalation if the host policy provides that path; otherwise explain the policy limitation instead of taking the blocked action."
        )
    if output.get("abstain") is True:
        lines.append("Ask for missing information or decline the unsafe action.")
    return "\n".join(lines)


def _action_review_event(
    task_context: ImportTaskContext,
    action_names: Sequence[str],
    review: SAGEActionReview,
) -> dict[str, Any]:
    return {
        "event": "action_review_blocked",
        "task_id": task_context.task_id,
        "proposed_actions": list(action_names),
        "reason": review.reason,
        "visible_helpers": list(review.visible_helpers),
    }


def _task_from_context(context: ImportTaskContext) -> TaskSpec:
    return TaskSpec(
        task_id=context.task_id,
        name=context.name,
        prompt=context.prompt,
        artifacts=dict(context.artifacts),
        metadata=dict(context.metadata),
    )


def _retry_context_with_observation(
    context: ImportTaskContext, result: TaskRunResult
) -> ImportTaskContext:
    metadata = dict(context.metadata)
    metadata["last_transcript"] = "\n".join(result.transcript[-16:])
    feedback_parts = [result.error]
    parser_results = result.artifacts.get("parser_results")
    failure_mode = result.artifacts.get("failure_mode")
    if failure_mode:
        feedback_parts.append(f"failure_mode: {failure_mode}")
    if parser_results:
        feedback_parts.append(
            "parser_results: " + json.dumps(parser_results, sort_keys=True, default=str)
        )
    feedback_parts.extend(result.transcript[-6:])
    metadata["last_feedback"] = "\n".join(
        part for part in feedback_parts if str(part).strip()
    ).strip()
    return ImportTaskContext(
        task_id=context.task_id,
        name=context.name,
        prompt=context.prompt,
        artifacts=context.artifacts,
        metadata=metadata,
    )


def _result_from_observation(
    task: TaskSpec, observation: ImportTaskObservation
) -> TaskRunResult:
    return TaskRunResult(
        task=task,
        success=observation.success,
        score=observation.score,
        outcome_score=observation.outcome_score,
        transcript=observation.transcript,
        tool_uses=observation.tool_uses,
        artifacts=dict(observation.artifacts),
        error=observation.error,
    )


def _route_import_helpers(
    task: TaskSpec, records: Mapping[str, HelperRecord], *, active_helpers: int
) -> tuple[str, ...]:
    if active_helpers <= 0:
        return ()
    text = _task_text(task).lower()
    ranked: list[tuple[float, str]] = []
    for name, record in records.items():
        if record.retired:
            continue
        spec = record.candidate.spec
        trigger_text = " ".join(
            [spec.description, *spec.positive_triggers, spec.family, spec.helper_type]
        ).lower()
        overlap = _token_overlap(text, trigger_text)
        success_rate = record.successes / record.uses if record.uses else 0.0
        recency_bonus = 0.1 if record.uses == 0 else 0.0
        ranked.append((overlap + success_rate + recency_bonus, name))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(name for _, name in ranked[:active_helpers])


def _render_guidance(
    *,
    profile: EnvironmentProfile,
    task: TaskSpec,
    records: Mapping[str, HelperRecord],
) -> SAGEGuidance:
    if not records:
        return SAGEGuidance()
    sections: list[str] = [
        "SAGE reusable helpers from prior official outcomes.",
        "Use them only when they apply to the current task and the host harness policy.",
        "Do not infer hidden labels, expected outputs, reference solutions, or task-specific facts.",
    ]
    tool_schemas: list[Mapping[str, Any]] = []
    code_helpers: list[Mapping[str, Any]] = []
    helper_outputs: list[Mapping[str, Any]] = []
    policy_notes = tuple(profile.safety_rules)
    for name, record in records.items():
        spec = record.candidate.spec
        if spec.helper_type == "prompt_guidance":
            sections.append(
                f"\n[{name}] prompt guidance\n{record.candidate.code.strip()}"
            )
        elif spec.helper_type == "deterministic_callable":
            code_helpers.append(
                {
                    "name": name,
                    "family": spec.family,
                    "input_schema": dict(spec.input_schema),
                    "output_schema": dict(spec.output_schema),
                    "code": record.candidate.code,
                }
            )
            output = _execute_import_helper(record, task)
            if output is not None:
                helper_outputs.append(
                    {
                        "name": name,
                        "family": spec.family,
                        "helper_type": spec.helper_type,
                        "output": output,
                    }
                )
                sections.append(
                    f"\n[{name}] structured helper output\n"
                    f"{_format_helper_output(output)}"
                )
            else:
                sections.append(f"\n[{name}] deterministic helper\n{spec.description}")
        else:
            sections.append(f"\n[{name}] {spec.helper_type}\n{spec.description}")
        tool_schemas.append(
            {
                "name": name,
                "family": spec.family,
                "helper_type": spec.helper_type,
                "description": spec.description,
                "input_schema": dict(spec.input_schema),
                "output_schema": dict(spec.output_schema),
            }
        )
    return SAGEGuidance(
        system_prompt="\n".join(sections).strip(),
        visible_helpers=tuple(records),
        tool_schemas=tuple(tool_schemas),
        code_helpers=tuple(code_helpers),
        policy_notes=policy_notes,
        metadata={
            "environment": profile.name,
            "task_id": task.task_id,
            "render_mode": "system_prompt",
            "helper_outputs": helper_outputs,
        },
    )


def _format_helper_output(output: Mapping[str, Any]) -> str:
    lines: list[str] = []
    focus = output.get("recommended_focus")
    if focus:
        lines.append(f"- Focus: {focus}")
    safe_next = output.get("safe_next_step")
    if safe_next:
        lines.append(f"- Safe next step: {safe_next}")
    must_verify = output.get("must_verify")
    if isinstance(must_verify, list) and must_verify:
        lines.append(
            "- Verify before acting: "
            + "; ".join(str(item) for item in must_verify[:5])
        )
    missing = output.get("missing_preconditions")
    if isinstance(missing, list) and missing:
        lines.append(
            "- Missing/precondition risks: "
            + "; ".join(str(item) for item in missing[:4])
        )
    commands = output.get("commands_to_consider")
    if isinstance(commands, list) and commands:
        lines.append(
            "- Commands/checks to consider: "
            + "; ".join(str(item) for item in commands[:4])
        )
    if output.get("abstain") is True and output.get("abstain_reason"):
        lines.append(f"- Abstain reason: {output.get('abstain_reason')}")
    if output.get("should_transfer") is True:
        lines.append(
            "- Recommended action: transfer/escalate instead of taking a write or compensation action unless visible policy explicitly permits direct completion."
        )
    if not lines:
        lines.append(json.dumps(output, sort_keys=True, default=str)[:700])
    return "\n".join(lines[:6])


def _execute_import_helper(
    record: HelperRecord, task: TaskSpec
) -> Mapping[str, Any] | None:
    spec = record.candidate.spec
    if spec.helper_type != "deterministic_callable":
        return None
    namespace: dict[str, Any] = {}
    try:
        compiled = compile(
            record.candidate.code, f"<sage-import-helper:{spec.name}>", "exec"
        )
        exec(  # noqa: S102 - accepted helpers are prevalidated as side-effect-free
            compiled,
            {
                "__builtins__": {
                    "abs": abs,
                    "all": all,
                    "any": any,
                    "bool": bool,
                    "dict": dict,
                    "float": float,
                    "int": int,
                    "isinstance": isinstance,
                    "len": len,
                    "list": list,
                    "max": max,
                    "min": min,
                    "range": range,
                    "round": round,
                    "set": set,
                    "sorted": sorted,
                    "str": str,
                    "sum": sum,
                    "tuple": tuple,
                }
            },
            namespace,
        )
        function = namespace.get(spec.name)
        if not callable(function):
            return None
        output: object = function(**_helper_inputs_for_task(spec, task))
        if isinstance(output, Mapping):
            return output
        return {"result": output}
    except Exception as exc:
        return {
            "abstain": True,
            "abstain_reason": f"helper_execution_error:{type(exc).__name__}",
        }


def _helper_inputs_for_task(spec: HelperSpec, task: TaskSpec) -> dict[str, Any]:
    artifacts = dict(task.artifacts)
    metadata = dict(task.metadata)
    inputs: dict[str, Any] = {}
    for key, type_name in spec.input_schema.items():
        lowered_key = str(key).lower()
        lowered_type = str(type_name).lower()
        if lowered_key in {"task_prompt", "prompt", "task_context", "description"}:
            inputs[str(key)] = "\n".join([task.name, task.prompt]).strip()
        elif lowered_key == "domain_policy":
            inputs[str(key)] = artifacts.get("domain_policy", "")
        elif lowered_key in {"available_tools", "tool_names"}:
            inputs[str(key)] = artifacts.get("available_tools", "")
        elif lowered_key == "transcript":
            inputs[str(key)] = metadata.get("last_transcript", "")
        elif lowered_key == "artifact_summary":
            inputs[str(key)] = artifacts.get("artifact_summary", "")
        elif lowered_key == "readme":
            inputs[str(key)] = artifacts.get("readme", "")
        elif lowered_key == "feedback":
            parser_results = artifacts.get("parser_results", "")
            inputs[str(key)] = metadata.get("last_feedback", "") or str(parser_results)
        elif lowered_key == "max_candidates":
            inputs[str(key)] = 8
        elif "list" in lowered_type:
            inputs[str(key)] = []
        elif "int" in lowered_type:
            inputs[str(key)] = 0
        elif "float" in lowered_type:
            inputs[str(key)] = 0.0
        elif "bool" in lowered_type:
            inputs[str(key)] = False
        else:
            inputs[str(key)] = artifacts.get(str(key), metadata.get(str(key), ""))
    return inputs


def _import_gap_candidates(
    *,
    profile: EnvironmentProfile,
    task: TaskSpec,
    result: TaskRunResult,
    records: Mapping[str, HelperRecord],
    registry: LocalSAGERegistry,
) -> tuple[GapSignal, ...]:
    """Return full helper gaps for import mode before prompt fallback."""

    gaps: list[GapSignal] = []
    if _looks_like_policy_action_context(profile, result):
        gaps.append(
            GapSignal(
                key=f"import_policy_action_preconditions:{profile.name}",
                summary=(
                    "Create a structured helper that converts visible policy, "
                    "tool, and transcript cues into action preconditions, "
                    "required checks, safe next steps, and transfer/abstain "
                    "signals for host-owned policy simulators."
                ),
                source_task_id=task.task_id,
                source_environment=profile.name,
                severity=0.9,
                suggested_tool_name=_next_helper_name(
                    registry.load(), prefix="plan_policy_action_preconditions"
                ),
                suggested_helper_family="policy_action_precondition_planner",
                evidence=(
                    "official transcript",
                    "host tool or policy cues",
                    "failed task outcome",
                ),
                required_inputs={
                    "task_prompt": "str",
                    "domain_policy": "str",
                    "transcript": "str",
                    "available_tools": "str",
                },
                expected_outputs={
                    "recommended_focus": "str",
                    "must_verify": "list[str]",
                    "missing_preconditions": "list[str]",
                    "safe_next_step": "str",
                    "should_transfer": "bool",
                    "abstain": "bool",
                    "abstain_reason": "str",
                },
                generation_directives={
                    "template": "policy_action_precondition_planner"
                },
            )
        )
    if _looks_like_execution_feedback_context(profile, task, result):
        gaps.append(
            GapSignal(
                key=f"import_execution_feedback_repair:{profile.name}",
                summary=(
                    "Create a structured helper that turns visible public task "
                    "instructions, execution transcripts, and official "
                    "post-attempt failure feedback into a bounded repair plan. "
                    "The helper must recommend what to inspect or verify next; "
                    "it must not inspect hidden tests, reference solutions, "
                    "labels, or environment-private answers."
                ),
                source_task_id=task.task_id,
                source_environment=profile.name,
                severity=0.9,
                suggested_tool_name=_next_helper_name(
                    registry.load(), prefix="plan_execution_feedback_repair"
                ),
                suggested_helper_family="execution_feedback_repair_planner",
                evidence=(
                    "visible public task instruction",
                    "official post-attempt failure feedback",
                    "host-owned execution transcript",
                ),
                required_inputs={
                    "task_prompt": "str",
                    "feedback": "str",
                    "transcript": "str",
                    "available_tools": "str",
                },
                expected_outputs={
                    "recommended_focus": "str",
                    "must_verify": "list[str]",
                    "commands_to_consider": "list[str]",
                    "safe_next_step": "str",
                    "abstain": "bool",
                    "abstain_reason": "str",
                },
                generation_directives={"template": "terminal_task_repair_planner"},
            )
        )
    gaps.extend(
        mine_gap_signals(
            profile=profile,
            task=task,
            result=result,
            helpers=records,
        )
    )
    return _dedupe_gap_sequence(gaps)


def _import_validation_cases_for_gap(
    gap: GapSignal, result: TaskRunResult
) -> tuple[ValidationCase, ...]:
    template = str(gap.generation_directives.get("template", ""))
    if template == "policy_action_precondition_planner":
        return (
            ValidationCase(
                name="cancel_refund_policy_preconditions",
                inputs={
                    "task_prompt": "Airline cancellation request",
                    "domain_policy": (
                        "Cancellations require reservation ownership, refund "
                        "eligibility, and policy permission before any write tool."
                    ),
                    "transcript": (
                        "user asks to cancel; assistant must check refundability "
                        "and cannot proceed if policy forbids it"
                    ),
                    "available_tools": "get_reservation update_reservation transfer_to_human",
                },
                expected={
                    "recommended_focus": "cancellation_or_refund_policy",
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="reservation_change_policy_preconditions",
                inputs={
                    "task_prompt": "Change flight reservation",
                    "domain_policy": (
                        "Reservation changes require identity, flight option, "
                        "fare difference, and accepted payment method."
                    ),
                    "transcript": "user wants to change flight and pay with gift card",
                    "available_tools": "search_flights update_reservation",
                },
                expected={
                    "recommended_focus": "reservation_change_policy",
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="discretionary_compensation_transfer",
                inputs={
                    "task_prompt": (
                        "Customer requests more substantial compensation after a "
                        "cancelled business flight caused a missed meeting."
                    ),
                    "domain_policy": (
                        "Compensation certificates have fixed policy amounts. "
                        "Transfer requests outside the fixed policy to a human agent."
                    ),
                    "transcript": (
                        "user says the certificate is not enough and asks to "
                        "reconsider because they missed an important meeting"
                    ),
                    "available_tools": "send_certificate transfer_to_human_agents",
                },
                expected={
                    "recommended_focus": "compensation_scope_or_escalation_policy",
                    "should_transfer": True,
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="delayed_complaint_without_change_path",
                inputs={
                    "task_prompt": "Customer is frustrated about a delayed flight.",
                    "domain_policy": (
                        "Delay compensation is only available after a qualifying "
                        "change or cancellation path. Otherwise transfer or decline."
                    ),
                    "transcript": (
                        "user complains about a delayed flight inconvenience, "
                        "asks for a certificate, and says they will call back "
                        "later for the unrelated booking"
                    ),
                    "available_tools": "send_certificate transfer_to_human_agents",
                },
                expected={
                    "recommended_focus": "delayed_flight_compensation_scope",
                    "should_transfer": True,
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="unsupported_insurance_dispute_transfer",
                inputs={
                    "task_prompt": "Customer says purchased insurance is missing.",
                    "domain_policy": (
                        "Only listed host tools may mutate reservations. "
                        "Insurance disputes without a direct tool must be "
                        "transferred to a human agent."
                    ),
                    "transcript": (
                        "user says the insurance coverage is not showing, "
                        "believes this is an error, and asks the assistant to "
                        "resolve the issue without transfer"
                    ),
                    "available_tools": (
                        "get_reservation_details update_reservation_baggages "
                        "update_reservation_passengers transfer_to_human_agents"
                    ),
                },
                expected={
                    "recommended_focus": "unsupported_policy_or_account_dispute",
                    "should_transfer": True,
                    "abstain": False,
                },
            ),
        )
    if template == "terminal_task_repair_planner":
        return (
            ValidationCase(
                name="regex_date_feedback_repair",
                inputs={
                    "task_prompt": (
                        "Write a script that extracts valid dates from a log file."
                    ),
                    "feedback": (
                        'parser_results: {"test_regex_matches_dates": "failed"}'
                    ),
                    "transcript": "pytest failed on date matching",
                    "available_tools": "bash python pytest sed grep",
                },
                expected={
                    "recommended_focus": "regex_or_date_matching_repair",
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="jsonl_output_feedback_repair",
                inputs={
                    "task_prompt": "Aggregate JSON Lines records into output.jsonl.",
                    "feedback": 'parser_results: {"test_expected_output": "failed"}',
                    "transcript": "public expected output comparison failed",
                    "available_tools": "bash python pytest jq",
                },
                expected={
                    "recommended_focus": "jsonl_or_output_format_repair",
                    "abstain": False,
                },
            ),
        )
    if gap.expected_outputs.get("candidates") == "list[str]":
        return (
            ValidationCase(
                name="generic_visible_candidate_case",
                inputs={
                    "description": "Visible parser accepts XML and regex input.",
                    "readme": "Submit candidate input strings only.",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "literal: MAGIC_HEADER\n"
                        "source_line: if (size == 4294967295) crash();\n"
                        "dict: \\\\A"
                    ),
                    "max_candidates": 6,
                },
                expected={
                    "abstain": False,
                    "candidates_max_count": 6,
                },
            ),
        )
    if gap.required_inputs == {"exit_code": "int", "output": "str"}:
        return (
            ValidationCase(
                name="visible_execution_failure",
                inputs={"exit_code": 1, "output": "runtime error"},
                expected={"crashed": True, "abstain": False},
            ),
        )
    return (
        ValidationCase(
            name="generic_smoke",
            inputs=_validation_inputs_from_schema(gap.required_inputs, result),
            expected={},
        ),
    )


def _validation_inputs_from_schema(
    schema: Mapping[str, str], result: TaskRunResult
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for key, type_name in schema.items():
        lowered = str(type_name).lower()
        if key == "task_prompt":
            inputs[key] = result.task.prompt
        elif key == "transcript":
            inputs[key] = "\n".join(result.transcript[-8:])
        elif "list" in lowered:
            inputs[key] = []
        elif "int" in lowered:
            inputs[key] = 0
        elif "float" in lowered:
            inputs[key] = 0.0
        elif "bool" in lowered:
            inputs[key] = False
        else:
            inputs[key] = ""
    return inputs


def _looks_like_policy_action_context(
    profile: EnvironmentProfile, result: TaskRunResult
) -> bool:
    text = " ".join(
        [
            profile.name,
            profile.description,
            result.error,
            *result.transcript[-10:],
        ]
    ).lower()
    policy_cues = (
        "reservation",
        "refund",
        "cancel",
        "flight",
        "payment",
        "policy",
        "tool call",
        "transfer",
        "user simulator",
        "customer",
        "airline",
        "retail",
        "telecom",
    )
    return any(cue in text for cue in policy_cues)


def _looks_like_execution_feedback_context(
    profile: EnvironmentProfile, task: TaskSpec, result: TaskRunResult
) -> bool:
    if result.success:
        return False
    parser_results = result.artifacts.get("parser_results")
    failure_mode = result.artifacts.get("failure_mode")
    text = " ".join(
        [
            profile.name,
            profile.description,
            task.name,
            task.prompt,
            str(failure_mode or ""),
            json.dumps(parser_results, sort_keys=True, default=str)
            if parser_results
            else "",
            result.error,
            *result.transcript[-8:],
        ]
    ).lower()
    feedback_cues = (
        "parser_results",
        "test_",
        "pytest",
        "expected_output",
        "failed",
        "failure_mode",
        "traceback",
        "assert",
        "exit_code",
        "post_test",
    )
    execution_cues = (
        "terminal",
        "shell",
        "docker",
        "benchmark",
        "official harness",
        "task runner",
        "code",
        "script",
        "test",
    )
    return any(cue in text for cue in feedback_cues) and any(
        cue in text for cue in execution_cues
    )


def _dedupe_gap_sequence(gaps: Sequence[GapSignal]) -> tuple[GapSignal, ...]:
    seen: set[tuple[str, str]] = set()
    output: list[GapSignal] = []
    for gap in gaps:
        identity = (gap.key, gap.suggested_tool_name or "")
        if identity in seen:
            continue
        seen.add(identity)
        output.append(gap)
    return tuple(output)


def _active_gap_already_has_helper(
    records: Mapping[str, HelperRecord], gap: GapSignal
) -> bool:
    for name, record in records.items():
        if record.retired:
            continue
        if record.birth_gap_key == gap.key:
            return True
        if gap.suggested_tool_name and name == gap.suggested_tool_name:
            return True
    return False


def _supports_repair(generator: HelperGenerator) -> bool:
    return callable(getattr(generator, "repair", None))


def _make_prompt_guidance_gap(
    *,
    profile: EnvironmentProfile,
    task: TaskSpec,
    result: TaskRunResult,
    registry: LocalSAGERegistry,
) -> GapSignal:
    family = _failure_family(result)
    name = _next_helper_name(registry.load(), prefix=f"sage_{_slug(family)}_guidance")
    evidence = tuple(_compact_lines(result.transcript, limit=4))
    return GapSignal(
        key=f"import_prompt_guidance:{profile.name}:{family}",
        summary=(
            "Create reusable prompt guidance for an external harness task failure. "
            "The helper should describe visible policy, tool-use, verification, "
            "or stop-condition lessons that may help later tasks."
        ),
        source_task_id=task.task_id,
        source_environment=profile.name,
        suggested_tool_name=name,
        suggested_helper_family="prompt_guidance_helper",
        evidence=evidence,
        validation_hints=(
            "guidance must be reusable",
            "guidance must not mention hidden labels or exact task answers",
            "guidance must be short enough for a system prompt",
        ),
        generation_directives={
            "helper_type": "prompt_guidance",
            "failure_family": family,
        },
    )


def _generate_prompt_guidance_candidate(
    *,
    generator: HelperGenerator,
    gap: GapSignal,
    profile: EnvironmentProfile,
    result: TaskRunResult,
    model: str,
) -> HelperCandidate:
    generate_guidance = getattr(generator, "generate_guidance", None)
    if callable(generate_guidance):
        candidate = generate_guidance(gap, profile, result, model=model)
        if isinstance(candidate, HelperCandidate):
            return candidate
    guidance = _fallback_guidance(result)
    return _prompt_guidance_candidate(
        gap=gap,
        profile=profile,
        guidance=guidance,
        model=model,
    )


def _prompt_guidance_candidate(
    *,
    gap: GapSignal,
    profile: EnvironmentProfile,
    guidance: str,
    model: str,
) -> HelperCandidate:
    name = gap.suggested_tool_name or _slug(gap.key)
    normalized = _normalize_guidance(guidance)
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family="prompt_guidance_helper",
            helper_type="prompt_guidance",
            description=gap.summary,
            input_schema={"task_context": "visible external task context"},
            output_schema={"system_prompt_guidance": "str"},
            positive_triggers=tuple(gap.evidence),
            negative_triggers=(
                "hidden labels",
                "reference solutions",
                "task-specific expected answers",
            ),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=normalized,
        validation_cases=(),
        metadata={
            "model": model,
            "environment": profile.name,
            "gap_key": gap.key,
            "helper_type": "prompt_guidance",
        },
    )


def _validate_prompt_guidance_candidate(
    candidate: HelperCandidate,
    *,
    gap: GapSignal,
    integrity_errors: tuple[str, ...],
) -> HelperValidationReport:
    errors = list(integrity_errors)
    text = candidate.code.strip()
    if len(text.split()) < 12:
        errors.append("guidance_too_short")
    if gap.source_task_id and gap.source_task_id.lower() in text.lower():
        errors.append("source_task_id_hardcoded")
    blocked = (
        "gold answer",
        "ground truth",
        "hidden label",
        "reference solution",
        "expected answer",
        "use task id",
    )
    lower = text.lower()
    if any(item in lower for item in blocked):
        errors.append("leakage_prone_guidance_text")
    if not _guidance_actionable(text):
        errors.append("guidance_not_actionable")
    accepted = not errors
    return HelperValidationReport(
        accepted=accepted,
        errors=tuple(errors),
        cases_run=1,
        cases_passed=int(accepted),
        runtime_smoke_passed=True,
        side_effect_free=True,
    )


def _helper_birth_decision(result: TaskRunResult) -> str:
    """Return ``generate`` only for task failures that can teach reusable behavior."""

    text = " ".join([result.error, *result.transcript[-3:]]).lower()
    infrastructure_markers = (
        "runner_error",
        "subprocess_timeout",
        "results_missing",
        "jsondecodeerror",
        "expecting value: line 1 column 1",
        "connectionerror",
        "connection error",
        "rate limit",
        "authentication",
        "importerror",
        "modulenotfounderror",
        "docker daemon",
        "official runner error",
    )
    if any(marker in text for marker in infrastructure_markers):
        return "infrastructure_or_harness_failure"
    if not result.transcript and result.score <= 0.0:
        return "insufficient_visible_failure_evidence"
    return "generate"


def _task_result_event(
    result: TaskRunResult, *, visible_helpers: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "event": "task_result",
        "task_id": result.task.task_id,
        "task": {
            "task_id": result.task.task_id,
            "name": result.task.name,
            "prompt": result.task.prompt,
            "artifacts": dict(result.task.artifacts),
            "metadata": dict(result.task.metadata),
        },
        "name": result.task.name,
        "success": result.success,
        "score": result.score,
        "outcome_score": result.outcome_score
        if result.outcome_score is not None
        else result.score,
        "transcript": list(result.transcript),
        "tool_uses": [
            {
                "tool_name": use.tool_name,
                "arguments": dict(use.arguments),
                "result": use.result,
                "success": use.success,
                "generated_helper": use.generated_helper,
            }
            for use in result.tool_uses
        ],
        "visible_helpers": list(visible_helpers),
        "artifacts": _json_safe(result.artifacts),
        "error": result.error,
    }


def _fallback_guidance(result: TaskRunResult) -> str:
    tail = " ".join(result.transcript[-4:]).lower()
    if any(term in tail for term in ("policy", "not allowed", "cannot", "must")):
        return (
            "- Before acting, restate the applicable visible policy constraint.\n"
            "- Check all required preconditions before calling a tool or taking the final action.\n"
            "- If a required field or permission is missing, stop and ask for that missing information."
        )
    if any(term in tail for term in ("tool", "function", "api", "command")):
        return (
            "- Identify the exact host tool or command needed before answering.\n"
            "- Verify required arguments from visible state instead of guessing.\n"
            "- After each call, compare the observed result with the requested task before proceeding."
        )
    return (
        "- Convert the visible task request into explicit success conditions before acting.\n"
        "- Track which facts are observed and which are assumptions.\n"
        "- Do not finish until the official task goal is directly satisfied or a required fact is missing."
    )


def _normalize_guidance(guidance: str) -> str:
    lines = [line.strip() for line in guidance.splitlines() if line.strip()]
    normalized: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*[-*]\s*", "- ", line)
        line = re.sub(r"^\s*\d+[.)]\s*", "- ", line)
        if not line.startswith("- "):
            line = f"- {line}"
        normalized.append(line[:240])
    return "\n".join(normalized[:5])


def _guidance_actionable(guidance: str) -> bool:
    text = guidance.lower()
    if len(text.split()) < 12:
        return False
    terms = (
        "action",
        "argument",
        "calculate",
        "check",
        "command",
        "policy",
        "precondition",
        "required",
        "stop",
        "tool",
        "verify",
    )
    return any(term in text for term in terms)


def _failure_family(result: TaskRunResult) -> str:
    text = " ".join([result.error, *result.transcript[-6:]]).lower()
    families = (
        (
            "policy_precondition",
            ("policy", "not allowed", "precondition", "permission"),
        ),
        ("tool_argument", ("tool", "function", "argument", "missing parameter")),
        ("calculation", ("calculate", "total", "amount", "price", "count")),
        ("verification", ("test", "assert", "verify", "failed")),
        ("missing_information", ("missing", "insufficient", "unknown", "ask")),
    )
    for family, cues in families:
        if any(cue in text for cue in cues):
            return family
    return "task_completion"


def _next_helper_name(records: Mapping[str, HelperRecord], *, prefix: str) -> str:
    existing = set(records)
    index = 1
    while f"{prefix}_{index}" in existing:
        index += 1
    return f"{prefix}_{index}"


def _active_helper_count(records: Mapping[str, HelperRecord]) -> int:
    return sum(1 for record in records.values() if not record.retired)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens))


def _tokens(text: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9_]{3,}", text.lower())}


def _task_text(task: TaskSpec) -> str:
    return "\n".join(
        [
            task.name,
            task.prompt,
            *[str(value) for value in task.artifacts.values()],
            json.dumps(dict(task.metadata), sort_keys=True, default=str),
        ]
    )


def _compact_lines(lines: Iterable[str], *, limit: int) -> list[str]:
    compact = []
    for line in list(lines)[-limit:]:
        text = re.sub(r"\s+", " ", str(line)).strip()
        if text:
            compact.append(text[:320])
    return compact


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return slug[:80] or "helper"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))
