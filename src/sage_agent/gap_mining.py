"""Environment-neutral gap mining for standalone SAGE.

Adapters still define safe environment boundaries. This module mines reusable
capability gaps only from SAGE-visible task text, artifacts, attempts, and
tool-use traces. It must not inspect labels, expected answers, or hidden files.
"""

from __future__ import annotations

from typing import Mapping

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperRecord,
    TaskRunResult,
    TaskSpec,
)


def mine_gap_signals(
    *,
    profile: EnvironmentProfile,
    task: TaskSpec,
    result: TaskRunResult,
    helpers: Mapping[str, HelperRecord],
    base_gap: GapSignal | None = None,
) -> tuple[GapSignal, ...]:
    """Mine additional reusable gap hypotheses from visible run evidence."""

    if result.success:
        return ()

    text = _visible_text(task, result)
    lowered = text.lower()
    existing_families = {
        record.candidate.spec.family
        for record in helpers.values()
        if not record.retired
    }
    gaps: list[GapSignal] = []

    if _looks_like_candidate_submission_context(profile, task, result):
        if "artifact_literal_candidate_planner" not in existing_families and (
            "literal:" in lowered or "source_line:" in lowered
        ):
            gaps.append(
                _candidate_gap(
                    key="visible_artifact_literal_candidate_extraction",
                    summary=(
                        "Extract candidate inputs from visible artifact literals, "
                        "source-like lines, dictionary entries, and format cues."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_artifact_literal_input_candidates",
                    family="artifact_literal_candidate_planner",
                    evidence=(
                        "visible artifact literals",
                        "source-like lines",
                        "dictionary or format cues",
                    ),
                    template="artifact_literal_candidate_planner",
                )
            )

        if (
            "execution_feedback_candidate_mutation_planner" not in existing_families
            and (_attempt_count(result) >= 2 or "exit_code=0" in lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="execution_feedback_candidate_mutation",
                    summary=(
                        "Generate safe follow-up candidate inputs from failed "
                        "execution attempts, observed lengths, and verifier text."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="mutate_candidates_from_execution_feedback",
                    family="execution_feedback_candidate_mutation_planner",
                    evidence=(
                        "failed execution attempts",
                        "candidate lengths",
                        "verifier feedback",
                    ),
                    template="execution_feedback_candidate_mutation_planner",
                )
            )

        if "structured_input_candidate_planner" not in existing_families and (
            _has_structured_format_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="structured_input_format_candidate_planning",
                    summary=(
                        "Generate candidate inputs for visible structured formats "
                        "such as XML, JSON, CSV, path-like, regex-like, or config-like text."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_structured_input_candidates",
                    family="structured_input_candidate_planner",
                    evidence=(
                        "visible structured format cue",
                        "parser or reader context",
                        "format-specific candidate needed",
                    ),
                    template="structured_input_candidate_planner",
                )
            )

    if _looks_like_grid_navigation_context(profile, task):
        gaps.append(
            GapSignal(
                key="grid_shortest_path_action_planning",
                summary=(
                    "Plan a shortest safe action sequence from a visible grid "
                    "state, start position, start direction, and goal position."
                ),
                source_task_id=task.task_id,
                source_environment=profile.name,
                severity=0.85,
                suggested_tool_name="plan_grid_shortest_path_actions",
                suggested_helper_family="grid_action_planner",
                evidence=(
                    "visible grid rows",
                    "agent start position",
                    "goal position",
                    "allowed action names",
                ),
                required_inputs={
                    "grid_rows": "list[str]",
                    "start_row": "int",
                    "start_col": "int",
                    "start_dir": "int",
                    "goal_row": "int",
                    "goal_col": "int",
                    "blocked_symbols": "list[str]",
                },
                expected_outputs={
                    "actions": "list[str]",
                    "action_count": "int",
                    "path_found": "bool",
                    "abstain": "bool",
                    "abstain_reason": "str",
                },
                generation_directives={"template": "grid_shortest_path_action_planner"},
            )
        )

    if base_gap is None and _has_execution_result(lowered):
        gaps.append(
            GapSignal(
                key="execution_result_signal_classification",
                summary=(
                    "Classify visible execution output into success, failure, "
                    "timeout, crash-like, and next-action signals."
                ),
                source_task_id=task.task_id,
                source_environment=profile.name,
                severity=0.6,
                suggested_tool_name="classify_execution_result_signal",
                suggested_helper_family="execution_log_classifier",
                evidence=("exit code", "execution output", "verifier text"),
                required_inputs={"exit_code": "int", "output": "str"},
                expected_outputs={
                    "crashed": "bool",
                    "timed_out": "bool",
                    "sanitizer": "str",
                    "recommendation": "str",
                    "abstain": "bool",
                },
                generation_directives={"template": "log_signal_classifier"},
            )
        )

    return _dedupe_gaps(gaps)


def _candidate_gap(
    *,
    key: str,
    summary: str,
    source_task_id: str,
    source_environment: str,
    tool_name: str,
    family: str,
    evidence: tuple[str, ...],
    template: str,
) -> GapSignal:
    return GapSignal(
        key=key,
        summary=summary,
        source_task_id=source_task_id,
        source_environment=source_environment,
        severity=0.75,
        suggested_tool_name=tool_name,
        suggested_helper_family=family,
        evidence=evidence,
        required_inputs={
            "description": "str",
            "readme": "str",
            "feedback": "str",
            "artifact_summary": "str",
            "max_candidates": "int",
        },
        expected_outputs={
            "candidates": "list[str]",
            "candidate_count": "int",
            "first_candidate": "str",
            "abstain": "bool",
        },
        generation_directives={"template": template},
    )


def _visible_text(task: TaskSpec, result: TaskRunResult) -> str:
    parts: list[str] = [task.name, task.prompt]
    parts.extend(str(value) for value in task.artifacts.values())
    parts.extend(result.transcript)
    for attempt in result.artifacts.get("attempts", []) if result.artifacts else []:
        if isinstance(attempt, dict):
            parts.append(str(attempt.get("output_excerpt", "")))
            parts.append(f"exit_code={attempt.get('exit_code')}")
            parts.append(f"poc_length={attempt.get('poc_length')}")
    for use in result.tool_uses:
        parts.append(use.tool_name)
        parts.append(str(use.result))
    return "\n".join(parts)[:32_000]


def _looks_like_candidate_submission_context(
    profile: EnvironmentProfile, task: TaskSpec, result: TaskRunResult
) -> bool:
    del profile
    artifact_keys = " ".join(task.artifacts.keys()).lower()
    if "artifact_summary" in artifact_keys:
        return True
    return bool(result.artifacts.get("attempts")) if result.artifacts else False


def _looks_like_grid_navigation_context(
    profile: EnvironmentProfile, task: TaskSpec
) -> bool:
    artifact_keys = " ".join(task.artifacts.keys()).lower()
    profile_text = " ".join(
        (
            profile.name,
            profile.description,
            " ".join(profile.observation_fields),
            " ".join(profile.helper_families),
        )
    ).lower()
    return (
        ("grid_rows" in artifact_keys or "grid_ascii" in artifact_keys)
        and "grid" in profile_text
        and ("goal" in profile_text or "navigation" in profile_text)
    )


def _attempt_count(result: TaskRunResult) -> int:
    attempts = result.artifacts.get("attempts", []) if result.artifacts else []
    return len(attempts) if isinstance(attempts, list) else 0


def _has_execution_result(text: str) -> bool:
    return "exit_code" in text or "executed" in text or "runtime error" in text


def _has_structured_format_cue(text: str) -> bool:
    cues = (
        "xml",
        "json",
        "csv",
        "html",
        "regex",
        "pcre",
        "parser",
        "parse",
        "read",
        "file:",
        ".c",
        ".h",
        ".dict",
        ".options",
        "header",
        "token",
        "chunk",
        "size",
        "length",
    )
    return any(cue in text for cue in cues)


def _dedupe_gaps(gaps: list[GapSignal]) -> tuple[GapSignal, ...]:
    seen: set[tuple[str, str]] = set()
    unique: list[GapSignal] = []
    for gap in gaps:
        identity = (gap.key, gap.suggested_tool_name or "")
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(gap)
    return tuple(unique)
