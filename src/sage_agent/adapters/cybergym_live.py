"""Live CyberGym submission adapter for standalone SAGE smoke runs."""

from __future__ import annotations

import json
import subprocess
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


@dataclass(frozen=True)
class CyberGymLiveTask:
    """Private live-task execution record."""

    task_key: str
    task_dir: Path
    display_name: str


@dataclass
class CyberGymLiveSubmitAdapter:
    """Run CyberGym tasks through generated task dirs and submit.sh."""

    tasks_root: Path
    tasks_to_run: tuple[CyberGymLiveTask, ...]
    max_candidates: int = 6

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="cybergym-live",
            description=(
                "CyberGym live task directories with visible README, description, "
                "and submit.sh verifier calls."
            ),
            base_tools=("file_read", "shell", "submit_poc"),
            action_tools=("submit_poc",),
            observation_fields=("README.md", "description.txt", "submit_result"),
            helper_families=("poc_seed_candidate_planner",),
            safety_rules=(
                "helpers must not submit PoCs",
                "helpers must not read reference PoCs or hidden labels",
                "helpers return candidate content only; the adapter performs submission",
            ),
            metadata={"tasks_root": str(self.tasks_root)},
        )

    def prepare(self) -> None:
        if not self.tasks_root.exists():
            raise FileNotFoundError(
                f"CyberGym live task root not found: {self.tasks_root}"
            )
        for task in self.tasks_to_run:
            for filename in ("README.md", "description.txt", "submit.sh"):
                path = task.task_dir / filename
                if not path.exists():
                    raise FileNotFoundError(f"missing CyberGym task file: {path}")

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        selected = self.tasks_to_run[:limit] if limit is not None else self.tasks_to_run
        return tuple(self._task_spec(task) for task in selected)

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(
            name
            for name, record in helpers.items()
            if record.candidate.spec.family == "poc_seed_candidate_planner"
            and not record.retired
        )[:1]

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        live_task = self._live_task(task.task_id)
        description = task.artifacts.get("description", "")
        candidates = ["\x00\x01\x02\x03"]
        tool_uses: list[ToolUseRecord] = []
        if helpers:
            name, record = next(iter(helpers.items()))
            validation = validate_helper_candidate(record.candidate)
            if validation.accepted:
                planner = _load_helper(record)
                planned = planner(
                    description=str(description),
                    max_candidates=self.max_candidates,
                )
                candidates = [
                    str(item)
                    for item in planned.get("candidates", [])
                    if isinstance(item, str)
                ][: self.max_candidates]
                if not candidates:
                    candidates = ["\x00\x01\x02\x03"]
                tool_uses.append(
                    ToolUseRecord(
                        tool_name=name,
                        arguments={"description_chars": len(str(description))},
                        result={
                            "candidate_count": len(candidates),
                            "first_candidate_len": len(candidates[0])
                            if candidates
                            else 0,
                        },
                        success=True,
                        generated_helper=True,
                    )
                )
            else:
                tool_uses.append(
                    ToolUseRecord(name, generated_helper=True, success=False)
                )
        attempts = []
        success = False
        best_score = 0.0
        error = ""
        for index, candidate in enumerate(candidates):
            result = _submit_candidate(live_task.task_dir, index, candidate)
            attempts.append(result)
            exit_code = int(result.get("exit_code", 0)) if result.get("ok") else 0
            if result.get("ok") and exit_code not in (0, 300):
                success = True
                best_score = 1.0
                break
            if not result.get("ok"):
                error = str(result.get("error", ""))
        transcript = tuple(_attempt_summary(item) for item in attempts)
        return TaskRunResult(
            task=task,
            success=success,
            score=best_score,
            outcome_score=best_score,
            transcript=transcript,
            tool_uses=tuple(tool_uses),
            artifacts={"attempts": attempts},
            error=error,
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
            key="cybergym_visible_seed_poc_candidate_planning",
            summary=(
                "Create side-effect-free seed PoC candidate strings from visible "
                "CyberGym task descriptions for later submission by the environment."
            ),
            source_task_id=task.task_id,
            source_environment="cybergym-live",
            severity=0.8,
            suggested_tool_name="plan_visible_seed_poc_candidates",
            suggested_helper_family="poc_seed_candidate_planner",
            evidence=("description.txt", "README.md", "baseline submit result"),
            required_inputs={"description": "str", "max_candidates": "int"},
            expected_outputs={
                "candidates": "list[str]",
                "candidate_count": "int",
                "first_candidate": "str",
                "abstain": "bool",
            },
            generation_directives={"template": "cybergym_seed_poc_candidates"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="yara_rule_description",
                inputs={"description": "YARA rule parser crash", "max_candidates": 6},
                expected={
                    "candidate_count": 6,
                    "first_candidate": "\x00\x01\x02\x03",
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="json_description",
                inputs={"description": "JSON parser issue", "max_candidates": 8},
                expected={
                    "candidate_count": 8,
                    "first_candidate": "\x00\x01\x02\x03",
                    "abstain": False,
                },
            ),
        )

    def _task_spec(self, task: CyberGymLiveTask) -> TaskSpec:
        readme = (task.task_dir / "README.md").read_text(encoding="utf-8")
        description = (task.task_dir / "description.txt").read_text(encoding="utf-8")
        return TaskSpec(
            task_id=task.task_key,
            name=task.display_name,
            prompt=readme,
            artifacts={"description": description, "readme": readme},
            metadata={"task_dir": str(task.task_dir)},
        )

    def _live_task(self, task_key: str) -> CyberGymLiveTask:
        for task in self.tasks_to_run:
            if task.task_key == task_key:
                return task
        raise KeyError(task_key)


def _load_helper(record: HelperRecord) -> Callable[..., Any]:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - helper already passed standalone validator
        record.candidate.code,
        {
            "__builtins__": {
                "bool": bool,
                "dict": dict,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "set": set,
                "str": str,
            }
        },
        namespace,
    )
    return cast(Callable[..., Any], namespace[record.candidate.spec.name])


def _submit_candidate(task_dir: Path, index: int, candidate: str) -> dict[str, Any]:
    poc_path = task_dir / f"sage_candidate_{index}.poc"
    poc_path.write_bytes(candidate.encode("latin1", errors="ignore"))
    completed = subprocess.run(
        ["bash", str(task_dir / "submit.sh"), str(poc_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    raw = completed.stdout.strip()
    payload: dict[str, Any] = {}
    if raw:
        start = raw.rfind("{")
        if start >= 0:
            try:
                payload = json.loads(raw[start:])
            except json.JSONDecodeError:
                payload = {}
    if not payload:
        return {
            "ok": False,
            "candidate_index": index,
            "returncode": completed.returncode,
            "error": (completed.stderr or completed.stdout)[-800:],
        }
    payload["ok"] = completed.returncode == 0
    payload["candidate_index"] = index
    payload["poc_length"] = len(candidate)
    output = str(payload.get("output", ""))
    payload["output_excerpt"] = output[:600]
    payload.pop("output", None)
    return payload


def _attempt_summary(attempt: Mapping[str, Any]) -> str:
    if not attempt.get("ok"):
        return f"candidate {attempt.get('candidate_index')}: submit failed"
    return (
        f"candidate {attempt.get('candidate_index')}: "
        f"exit_code={attempt.get('exit_code')} len={attempt.get('poc_length')}"
    )
