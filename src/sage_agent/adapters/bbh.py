"""BIG-Bench Hard adapter for standalone SAGE integration checks.

This adapter loads public BIG-Bench Hard JSON tasks from a local clone and
scores exact-answer text privately. SAGE-visible task specs include the prompt,
task family, and benchmark metadata, but never include the target answer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
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
class BBHAdapter:
    """Small executable BIG-Bench Hard adapter.

    The default task mix uses symbolic tasks where reusable deterministic
    helpers should plausibly transfer across examples: boolean expressions,
    arithmetic expressions, Dyck completion, and word sorting.
    """

    repo_root: Path = Path("external/BIG-Bench-Hard")
    task_names: tuple[str, ...] = (
        "boolean_expressions",
        "multistep_arithmetic_two",
        "dyck_languages",
        "word_sorting",
    )
    _tasks: tuple[TaskSpec, ...] = field(default=(), init=False)
    _targets: dict[str, str] = field(default_factory=dict, init=False)

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="bbh",
            description=(
                "BIG-Bench Hard exact-answer reasoning tasks loaded from the "
                "published public JSON task files."
            ),
            base_tools=("read_prompt", "submit_answer"),
            action_tools=("submit_answer",),
            observation_fields=("task_family", "prompt", "answer_format"),
            helper_families=("symbolic_text_answerer",),
            safety_rules=(
                "helpers may only transform visible prompt text into an answer",
                "helpers must not read target answers or external files",
                "the adapter alone scores predictions against private targets",
            ),
            metadata={
                "paper": (
                    "Challenging BIG-Bench Tasks and Whether Chain-of-Thought "
                    "Can Solve Them"
                ),
                "repo": "https://github.com/suzgunmirac/BIG-Bench-Hard",
                "clone_path": str(self.repo_root),
            },
        )

    def prepare(self) -> None:
        task_dir = self.repo_root / "bbh"
        if not task_dir.exists():
            raise FileNotFoundError(
                f"BIG-Bench-Hard task directory not found: {task_dir}"
            )
        tasks: list[TaskSpec] = []
        targets: dict[str, str] = {}
        examples_by_family: dict[str, list[dict[str, str]]] = {}
        for family in self.task_names:
            path = task_dir / f"{family}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            examples = payload.get("examples", [])
            if not isinstance(examples, list):
                raise ValueError(f"invalid BBH examples list: {path}")
            examples_by_family[family] = [
                item
                for item in examples
                if isinstance(item, dict)
                and isinstance(item.get("input"), str)
                and isinstance(item.get("target"), str)
            ]
        max_examples = min(len(items) for items in examples_by_family.values())
        for index in range(max_examples):
            for family in self.task_names:
                item = examples_by_family[family][index]
                task_id = f"bbh:{family}:{index}"
                tasks.append(
                    TaskSpec(
                        task_id=task_id,
                        name=f"BIG-Bench Hard {family} #{index}",
                        prompt=str(item["input"]),
                        artifacts={
                            "benchmark": "BIG-Bench Hard",
                            "task_family": family,
                            "answer_format": _answer_format_for_family(family),
                        },
                        metadata={
                            "benchmark": "BIG-Bench Hard",
                            "task_family": family,
                            "example_index": index,
                        },
                    )
                )
                targets[task_id] = str(item["target"])
        self._tasks = tuple(tasks)
        self._targets = targets

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        if not self._tasks:
            self.prepare()
        return tuple(self._tasks[:limit] if limit is not None else self._tasks)

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        eligible = [
            name
            for name, record in helpers.items()
            if record.candidate.spec.family == "symbolic_text_answerer"
            and not record.retired
        ]
        return tuple(eligible[:2])

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        if not helpers:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=("No generated symbolic answer helper was available.",),
                artifacts={
                    "task_family": task.metadata.get("task_family", ""),
                    "answer_format": task.artifacts.get("answer_format", ""),
                },
            )
        name, record = next(iter(helpers.items()))
        validation = validate_helper_candidate(record.candidate)
        if not validation.accepted:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=(f"Generated helper {name} failed validation.",),
                tool_uses=(ToolUseRecord(name, generated_helper=True, success=False),),
            )
        function = _load_helper(record)
        result = function(
            prompt=task.prompt,
            task_family=str(task.metadata.get("task_family", "")),
        )
        predicted = str(result.get("answer", "")).strip()
        scored = self.score_answer(
            task,
            predicted,
            transcript_prefix=f"{name} predicted {predicted!r}",
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    arguments={
                        "task_family": task.metadata.get("task_family", ""),
                    },
                    result=result,
                    success=False,
                    generated_helper=True,
                ),
            ),
        )
        normalized_uses = tuple(
            ToolUseRecord(
                tool_name=use.tool_name,
                arguments=use.arguments,
                result=use.result,
                success=scored.success if use.generated_helper else use.success,
                generated_helper=use.generated_helper,
            )
            for use in scored.tool_uses
        )
        return TaskRunResult(
            task=scored.task,
            success=scored.success,
            score=scored.score,
            outcome_score=scored.outcome_score,
            transcript=scored.transcript,
            tool_uses=normalized_uses,
            artifacts=scored.artifacts,
            error=scored.error,
        )

    def score_answer(
        self,
        task: TaskSpec,
        answer: str,
        *,
        transcript_prefix: str,
        tool_uses: tuple[ToolUseRecord, ...] = (),
    ) -> TaskRunResult:
        """Privately score a predicted answer against the withheld target."""

        predicted = str(answer).strip()
        success = _normalize_answer(predicted) == _normalize_answer(
            self._targets[task.task_id]
        )
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            outcome_score=1.0 if success else 0.0,
            transcript=(transcript_prefix,),
            tool_uses=tool_uses,
            artifacts={
                "predicted_answer": predicted,
                "task_family": task.metadata.get("task_family", ""),
            },
        )

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        if result.success or any(
            record.candidate.spec.family == "symbolic_text_answerer"
            for record in helpers.values()
        ):
            return None
        family = str(task.metadata.get("task_family", ""))
        return GapSignal(
            key="visible_symbolic_text_answering",
            summary=(
                "Answer visible symbolic text tasks by deterministically parsing "
                "the prompt and returning a final exact-answer string."
            ),
            source_task_id=task.task_id,
            source_environment="bbh",
            severity=0.9,
            suggested_tool_name="answer_visible_symbolic_text_task",
            suggested_helper_family="symbolic_text_answerer",
            evidence=(
                "visible prompt text",
                f"task family {family}",
                "exact-answer benchmark format",
            ),
            required_inputs={
                "prompt": "str",
                "task_family": "str",
            },
            expected_outputs={
                "answer": "str",
                "abstain": "bool",
                "abstain_reason": "str",
            },
            generation_directives={"template": "symbolic_text_answerer"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="boolean_expression",
                inputs={
                    "prompt": "not ( True ) and ( True ) is",
                    "task_family": "boolean_expressions",
                },
                expected={"answer": "False", "abstain": False},
            ),
            ValidationCase(
                name="arithmetic_expression",
                inputs={
                    "prompt": "((-1 + 2 + 9 * 5) - (-2 + -4 + -4 * -7)) =",
                    "task_family": "multistep_arithmetic_two",
                },
                expected={"answer": "24", "abstain": False},
            ),
            ValidationCase(
                name="dyck_completion",
                inputs={
                    "prompt": (
                        "Complete the rest of the sequence, making sure that the "
                        "parentheses are closed properly. Input: < [ ["
                    ),
                    "task_family": "dyck_languages",
                },
                expected={"answer": "] ] >", "abstain": False},
            ),
            ValidationCase(
                name="word_sorting",
                inputs={
                    "prompt": (
                        "Sort the following words alphabetically: "
                        "List: zebra apple middle"
                    ),
                    "task_family": "word_sorting",
                },
                expected={"answer": "apple middle zebra", "abstain": False},
            ),
            ValidationCase(
                name="unsupported_abstains",
                inputs={
                    "prompt": "Who is the main character?",
                    "task_family": "unsupported_family",
                },
                expected={"abstain": True},
                should_abstain=True,
            ),
        )


def _answer_format_for_family(family: str) -> str:
    if family == "boolean_expressions":
        return "True or False"
    if family == "multistep_arithmetic_two":
        return "integer"
    if family == "dyck_languages":
        return "space-separated closing brackets"
    if family == "word_sorting":
        return "space-separated sorted words"
    return "exact string"


def _normalize_answer(value: str) -> str:
    return " ".join(str(value).strip().split()).lower()


def _load_helper(record: HelperRecord) -> Callable[..., Any]:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - helper already passed standalone validator
        record.candidate.code,
        {
            "__builtins__": {
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "range": range,
                "reversed": reversed,
                "sorted": sorted,
                "str": str,
                "sum": sum,
            }
        },
        namespace,
    )
    return cast(Callable[..., Any], namespace[record.candidate.spec.name])
