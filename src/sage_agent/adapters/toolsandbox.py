"""ToolSandbox adapter slice for the standalone SAGE package.

This adapter is intentionally small: it proves the new SAGE package can operate
against ToolSandbox-shaped tasks without baking ToolSandbox concepts into the
core controller. The existing full ToolSandbox runner remains in ``sage_ts``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
class ToolSandboxMiniAdapter:
    """A low-cost ToolSandbox compatibility adapter for smoke validation."""

    include_reuse_task: bool = True

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="toolsandbox",
            description=(
                "Stateful assistant benchmark with structured tools, traces, and "
                "scored task outcomes."
            ),
            base_tools=("search_contacts", "modify_contact", "end_conversation"),
            action_tools=("modify_contact",),
            observation_fields=("task_name", "tool_trace", "final_state", "score"),
            helper_families=("record_selector", "argument_preparer", "canonicalizer"),
            safety_rules=(
                "helpers must not mutate ToolSandbox state",
                "original side-effect tools remain responsible for state changes",
            ),
        )

    def prepare(self) -> None:
        return None

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        tasks = [
            TaskSpec(
                task_id="ts-smoke-1",
                name="update contact by visible phone",
                prompt="Find the one visible contact with phone +1 555-0100 and return its person_id.",
                artifacts={
                    "records": (
                        "[{'person_id':'p1','name':'A','phone_number':'+15550100'},"
                        "{'person_id':'p2','name':'B','phone_number':'+15550101'}]"
                    )
                },
                metadata={
                    "expected_person_id": "p1",
                    "match_value": "+1 555-0100",
                    "phase": "birth",
                },
            )
        ]
        if self.include_reuse_task:
            tasks.append(
                TaskSpec(
                    task_id="ts-smoke-2",
                    name="reuse contact selector by formatted phone",
                    prompt="Use the retained helper to select phone 15550101.",
                    artifacts={
                        "records": (
                            "[{'person_id':'p1','name':'A','phone_number':'+1 (555) 0100'},"
                            "{'person_id':'p2','name':'B','phone_number':'+1-555-0101'}]"
                        )
                    },
                    metadata={
                        "expected_person_id": "p2",
                        "match_value": "15550101",
                        "phase": "reuse",
                    },
                )
            )
        return tuple(tasks[:limit] if limit is not None else tasks)

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(
            name
            for name, record in helpers.items()
            if record.candidate.spec.family == "record_selector" and not record.retired
        )[:2]

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        if not helpers:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=("No generated selector was available.",),
                artifacts={"records": task.artifacts.get("records", "")},
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
        records = _records_for_task(task)
        result = function(
            records=records,
            field_name="phone_number",
            expected_value=str(task.metadata.get("match_value", "")),
            return_field="person_id",
        )
        success = result.get("value") == task.metadata.get("expected_person_id")
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            outcome_score=1.0 if success else 0.0,
            transcript=(f"{name} returned {result}",),
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    arguments={
                        "field_name": "phone_number",
                        "return_field": "person_id",
                    },
                    result=result,
                    success=success,
                    generated_helper=True,
                ),
            ),
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
            key="visible_record_unique_selector",
            summary=(
                "Select exactly one visible structured record by a scalar field and "
                "return a final-action-ready field."
            ),
            source_task_id=task.task_id,
            source_environment="toolsandbox",
            severity=0.9,
            suggested_tool_name="select_visible_record_by_field",
            suggested_helper_family="record_selector",
            evidence=("visible records", "scalar match", "final field extraction"),
            required_inputs={
                "records": "list",
                "field_name": "str",
                "expected_value": "str",
                "return_field": "str",
            },
            expected_outputs={
                "selected_index": "int",
                "selected_record": "dict",
                "value": "str",
                "abstain_reason": "str",
            },
            generation_directives={"template": "unique_record_selector"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="unique_phone_match",
                inputs={
                    "records": [
                        {"person_id": "p1", "phone_number": "+1 (555) 0100"},
                        {"person_id": "p2", "phone_number": "+1-555-0101"},
                    ],
                    "field_name": "phone_number",
                    "expected_value": "15550101",
                    "return_field": "person_id",
                },
                expected={"selected_index": 1, "value": "p2", "abstain": False},
            ),
            ValidationCase(
                name="ambiguous_match_abstains",
                inputs={
                    "records": [
                        {"person_id": "p1", "name": "Alex"},
                        {"person_id": "p2", "name": "Alex"},
                    ],
                    "field_name": "name",
                    "expected_value": "Alex",
                    "return_field": "person_id",
                },
                expected={"selected_index": -1, "abstain": True},
                should_abstain=True,
            ),
        )


def _records_for_task(task: TaskSpec) -> list[dict[str, str]]:
    if task.task_id == "ts-smoke-2":
        return [
            {"person_id": "p1", "name": "A", "phone_number": "+1 (555) 0100"},
            {"person_id": "p2", "name": "B", "phone_number": "+1-555-0101"},
        ]
    return [
        {"person_id": "p1", "name": "A", "phone_number": "+15550100"},
        {"person_id": "p2", "name": "B", "phone_number": "+15550101"},
    ]


def _load_helper(record: HelperRecord) -> Callable[..., Any]:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - helper already passed standalone validator
        record.candidate.code,
        {
            "__builtins__": {
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "str": str,
            }
        },
        namespace,
    )
    return cast(Callable[..., Any], namespace[record.candidate.spec.name])
