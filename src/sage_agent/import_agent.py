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
    SAGEGuidance,
    SAGEImportUpdate,
    TaskRunResult,
    TaskSpec,
)
from sage_agent.registry import LocalSAGERegistry


@dataclass(frozen=True)
class SAGEImportConfig:
    """Configuration for SAGE import mode."""

    model: str = "gpt-4o-mini"
    registry_dir: Path = Path(".sage_import_registry")
    active_helpers: int = 3
    max_new_helpers: int = 8
    retry_policy: str = "next_task_only"
    min_uses_before_lifecycle_action: int = 6
    weak_helper_success_rate: float = 0.25
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
                retry_policy=base_config.retry_policy,
                min_uses_before_lifecycle_action=base_config.min_uses_before_lifecycle_action,
                weak_helper_success_rate=base_config.weak_helper_success_rate,
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
            candidate_integrity = check_helper_candidate(
                candidate, gap, self.config.integrity_policy
            )
            validation = _validate_prompt_guidance_candidate(
                candidate,
                gap=gap,
                integrity_errors=tuple(
                    f"{issue.kind}:{issue.detail}"
                    for issue in candidate_integrity.issues
                ),
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
                }
            )
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
            retry_guidance = self.before_task(task_context)
            events.append(
                {
                    "event": "same_task_retry_recommended",
                    "task_id": task.task_id,
                    "tool_name": ",".join(accepted),
                    "visible_helpers": list(retry_guidance.visible_helpers),
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


def _task_from_context(context: ImportTaskContext) -> TaskSpec:
    return TaskSpec(
        task_id=context.task_id,
        name=context.name,
        prompt=context.prompt,
        artifacts=dict(context.artifacts),
        metadata=dict(context.metadata),
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
    policy_notes = tuple(profile.safety_rules)
    for name, record in records.items():
        spec = record.candidate.spec
        if spec.helper_type == "prompt_guidance":
            sections.append(
                f"\n[{name}] prompt guidance\n{record.candidate.code.strip()}"
            )
        elif spec.helper_type == "deterministic_callable":
            sections.append(
                f"\n[{name}] deterministic helper\n"
                f"{spec.description}\n"
                f"Inputs: {json.dumps(dict(spec.input_schema), sort_keys=True)}\n"
                f"Outputs: {json.dumps(dict(spec.output_schema), sort_keys=True)}"
            )
            code_helpers.append(
                {
                    "name": name,
                    "family": spec.family,
                    "input_schema": dict(spec.input_schema),
                    "output_schema": dict(spec.output_schema),
                    "code": record.candidate.code,
                }
            )
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
        },
    )


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
