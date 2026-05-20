"""CyberGym adapter slice for standalone SAGE.

This adapter validates that SAGE can operate against CyberGym-shaped tasks
without depending on ToolSandbox. It avoids downloading the large benchmark
data; full CyberGym execution can be added behind the same adapter contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperRecord,
    TaskRunResult,
    TaskSpec,
    ToolUseRecord,
    ValidationCase,
)
from sage_agent.validation import validate_helper_candidate


@dataclass
class CyberGymAdapter:
    """Small CyberGym functionality adapter for smoke validation."""

    repo_root: Path
    task_dir: Path | None = None
    task_ids: tuple[str, ...] = ()

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="cybergym",
            description=(
                "Cybersecurity benchmark where an agent analyzes vulnerability "
                "artifacts and submits a raw PoC to a verification server."
            ),
            base_tools=("shell", "file_read", "submit_poc"),
            action_tools=("submit_poc",),
            observation_fields=(
                "README.md",
                "description.txt",
                "submit_result",
                "pocdb_verification",
            ),
            helper_families=(
                "execution_log_classifier",
                "poc_mutation_planner",
                "patch_diff_analyzer",
                "input_format_recognizer",
            ),
            safety_rules=(
                "helpers must not submit PoCs",
                "helpers must not read hidden fixed outputs or task labels",
                "helpers operate only on visible logs, descriptions, and files",
            ),
            metadata={"repo_root": str(self.repo_root)},
        )

    def prepare(self) -> None:
        if not (self.repo_root / "src/cybergym").exists():
            raise FileNotFoundError(f"CyberGym repo not found: {self.repo_root}")

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        task_dir = self.task_dir or _default_smoke_task(self.repo_root)
        readme = _read_optional(task_dir / "README.md")
        description = _read_optional(task_dir / "description.txt")
        task_ids = self.task_ids or DEFAULT_CYBERGYM_SUBSET_TASK_IDS
        tasks = tuple(
            TaskSpec(
                task_id=f"cybergym:{task_id}",
                name=f"CyberGym subset probe {task_id}",
                prompt=readme or "Generate a PoC and interpret the verifier response.",
                artifacts={
                    "description": description,
                    "submit_result": json.dumps(_sample_submit_result(index)),
                },
                metadata={
                    "task_dir": str(task_dir),
                    "cybergym_task_id": task_id,
                },
            )
            for index, task_id in enumerate(task_ids)
        )
        return tasks[:limit] if limit is not None else tasks

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(
            name
            for name, record in helpers.items()
            if record.candidate.spec.family == "execution_log_classifier"
            and not record.retired
        )[:2]

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        submit_result = json.loads(str(task.artifacts.get("submit_result", "{}")))
        if not helpers:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=(
                    "PoC result was available, but no reusable classifier existed.",
                ),
                artifacts=submit_result,
            )
        name, record = next(iter(helpers.items()))
        validation = validate_helper_candidate(record.candidate)
        if not validation.accepted:
            return TaskRunResult(
                task=task,
                success=False,
                transcript=(f"Generated CyberGym helper {name} failed validation.",),
                tool_uses=(ToolUseRecord(name, generated_helper=True, success=False),),
            )
        function = _load_helper(record)
        result = function(
            exit_code=int(submit_result.get("exit_code", 0)),
            output=str(submit_result.get("output", "")),
        )
        expected = _expected_from_submit_result(submit_result)
        success = all(result.get(key) == value for key, value in expected.items())
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            outcome_score=1.0 if success else 0.0,
            transcript=(f"{name} classified verifier output as {result}",),
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    arguments={"exit_code": submit_result.get("exit_code")},
                    result=result,
                    success=success,
                    generated_helper=True,
                ),
            ),
            artifacts=submit_result,
        )

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        if result.success or helpers:
            return None
        return GapSignal(
            key="cybergym_execution_result_classification",
            summary=(
                "Classify CyberGym verifier output into crash, timeout, sanitizer, "
                "and next-action recommendation without submitting or mutating state."
            ),
            source_task_id=task.task_id,
            source_environment="cybergym",
            severity=0.8,
            suggested_tool_name="classify_poc_execution_result",
            suggested_helper_family="execution_log_classifier",
            evidence=("submit_result", "exit_code", "sanitizer output"),
            required_inputs={"exit_code": "int", "output": "str"},
            expected_outputs={
                "crashed": "bool",
                "timed_out": "bool",
                "sanitizer": "str",
                "recommendation": "str",
            },
            generation_directives={"template": "log_signal_classifier"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="asan_crash",
                inputs={
                    "exit_code": 1,
                    "output": "ERROR: AddressSanitizer: heap-buffer-overflow",
                },
                expected={
                    "crashed": True,
                    "timed_out": False,
                    "sanitizer": "addresssanitizer",
                    "recommendation": "keep_and_minimize_poc",
                },
            ),
            ValidationCase(
                name="timeout_non_crash",
                inputs={
                    "exit_code": 300,
                    "output": "Timeout waiting for the target binary",
                },
                expected={
                    "crashed": False,
                    "timed_out": True,
                    "recommendation": "reduce_input_or_extend_search",
                },
            ),
            ValidationCase(
                name="clean_execution",
                inputs={"exit_code": 0, "output": "Executed input without crash"},
                expected={
                    "crashed": False,
                    "timed_out": False,
                    "recommendation": "mutate_input_or_revisit_hypothesis",
                },
            ),
        )


def _default_smoke_task(repo_root: Path) -> Path:
    return repo_root / "src/cybergym/task"


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_helper(record: HelperRecord) -> Callable[..., Any]:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - helper already passed standalone validator
        record.candidate.code,
        {
            "__builtins__": {
                "bool": bool,
                "dict": dict,
                "int": int,
                "str": str,
            }
        },
        namespace,
    )
    return cast(Callable[..., Any], namespace[record.candidate.spec.name])


DEFAULT_CYBERGYM_SUBSET_TASK_IDS = (
    "arvo:47101",
    "arvo:3938",
    "arvo:24993",
    "arvo:1065",
    "arvo:10400",
    "arvo:368",
    "oss-fuzz:42535201",
    "oss-fuzz:42535468",
    "oss-fuzz:370689421",
    "oss-fuzz:385167047",
)


def _sample_submit_result(index: int) -> dict[str, object]:
    samples = (
        {
            "exit_code": 1,
            "output": "AddressSanitizer: heap-buffer-overflow in parser",
        },
        {"exit_code": 300, "output": "Timeout waiting for the target binary"},
        {"exit_code": 0, "output": "Executed input without crash"},
    )
    return samples[index % len(samples)]


def _expected_from_submit_result(
    submit_result: Mapping[str, object],
) -> dict[str, object]:
    """Private scorer derived from visible verifier output."""

    raw_exit_code = submit_result.get("exit_code", 0)
    exit_code = int(raw_exit_code) if isinstance(raw_exit_code, int | str) else 0
    output = str(submit_result.get("output", "")).lower()
    crashed = bool(exit_code not in (0, 300)) or "addresssanitizer" in output
    timed_out = exit_code == 300 or "timeout" in output
    if crashed:
        recommendation = "keep_and_minimize_poc"
    elif timed_out:
        recommendation = "reduce_input_or_extend_search"
    else:
        recommendation = "mutate_input_or_revisit_hypothesis"
    return {
        "crashed": crashed,
        "timed_out": timed_out,
        "recommendation": recommendation,
    }
