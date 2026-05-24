"""Repository-backed probe adapters for newly cloned benchmark datasets.

These adapters make external benchmark repositories selectable through the
standalone SAGE CLI before full benchmark-specific execution adapters exist.
They intentionally run metadata-level lifecycle probes: SAGE sees public task
records and must birth/reuse a generic structured-record selector. They are not
protected benchmark evaluations.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from csv import DictReader
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, cast

import yaml

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
class _RecordProbeTask:
    task: TaskSpec
    records: tuple[dict[str, str], ...]
    match_field: str
    match_value: str
    return_field: str
    return_value: str


@dataclass
class _StructuredRecordProbeAdapter:
    """Shared metadata-probe behavior for external benchmark repositories."""

    repo_root: Path
    _loaded_tasks: tuple[_RecordProbeTask, ...] = field(default=(), init=False)

    def profile(self) -> EnvironmentProfile:
        raise NotImplementedError

    def prepare(self) -> None:
        self._loaded_tasks = tuple(self._build_probe_tasks())

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        if not self._loaded_tasks:
            self.prepare()
        tasks = tuple(item.task for item in self._loaded_tasks)
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
        probe = self._probe_for_task(task)
        if not helpers:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=("No generated structured-record selector was available.",),
                artifacts={
                    "records": [dict(item) for item in probe.records],
                    "match_field": probe.match_field,
                    "return_field": probe.return_field,
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
            records=[dict(item) for item in probe.records],
            field_name=probe.match_field,
            expected_value=probe.match_value,
            return_field=probe.return_field,
        )
        selected_value = str(result.get("value", ""))
        scored = self.score_selected_value(
            task,
            selected_value,
            transcript_prefix=f"{name} selected {result}",
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    arguments={
                        "field_name": probe.match_field,
                        "return_field": probe.return_field,
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

    def score_selected_value(
        self,
        task: TaskSpec,
        selected_value: str,
        *,
        transcript_prefix: str,
        tool_uses: tuple[ToolUseRecord, ...] = (),
    ) -> TaskRunResult:
        """Score a selected public field value against dataset-derived metadata."""

        probe = self._probe_for_task(task)
        normalized = str(selected_value).strip()
        expected = probe.return_value
        success = normalized == expected
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            outcome_score=1.0 if success else 0.0,
            transcript=(transcript_prefix,),
            tool_uses=tool_uses,
            artifacts={
                "selected_value": normalized,
                "scored_field": probe.return_field,
            },
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
            key=f"{self.profile().name}_visible_record_selection",
            summary=(
                "Select exactly one visible benchmark task record by a public "
                "identifier and return a requested public field."
            ),
            source_task_id=task.task_id,
            source_environment=self.profile().name,
            severity=0.8,
            suggested_tool_name="select_visible_benchmark_record",
            suggested_helper_family="record_selector",
            evidence=("visible benchmark records", "public task identifier"),
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
                "abstain": "bool",
            },
            generation_directives={"template": "unique_record_selector"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="unique_task_key_match",
                inputs={
                    "records": [
                        {"task_key": "alpha:1", "category": "policy"},
                        {"task_key": "beta:2", "category": "terminal"},
                    ],
                    "field_name": "task_key",
                    "expected_value": "beta:2",
                    "return_field": "category",
                },
                expected={"selected_index": 1, "value": "terminal", "abstain": False},
            ),
            ValidationCase(
                name="ambiguous_task_key_abstains",
                inputs={
                    "records": [
                        {"task_key": "dup", "category": "a"},
                        {"task_key": "dup", "category": "b"},
                    ],
                    "field_name": "task_key",
                    "expected_value": "dup",
                    "return_field": "category",
                },
                expected={"selected_index": -1, "abstain": True},
                should_abstain=True,
            ),
        )

    def _build_probe_tasks(self) -> list[_RecordProbeTask]:
        raise NotImplementedError

    def _probe_for_task(self, task: TaskSpec) -> _RecordProbeTask:
        for probe in self._loaded_tasks:
            if probe.task.task_id == task.task_id:
                return probe
        raise KeyError(f"unknown probe task: {task.task_id}")


@dataclass
class TauBenchProbeAdapter(_StructuredRecordProbeAdapter):
    """Public-metadata probe for tau2/tau3 benchmark task repositories."""

    repo_root: Path = Path("external/tau2-bench")
    environment_name: str = "tau2-bench"
    domains: tuple[str, ...] = (
        "airline",
        "retail",
        "telecom",
        "banking_knowledge",
    )

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name=self.environment_name,
            description=(
                "tau2/tau3 conversational customer-service agent benchmark "
                "metadata probe over public task records, policies, and domains."
            ),
            base_tools=("domain_tools", "user_simulator", "policy_reader"),
            action_tools=("domain_tool_call", "respond_to_user"),
            observation_fields=("domain", "task_id", "task_purpose", "reason_for_call"),
            helper_families=("record_selector", "policy_argument_preparer"),
            safety_rules=(
                "helpers may only transform public task metadata",
                "helpers must not access hidden trajectories or private run results",
            ),
            metadata={
                "repo": "https://github.com/sierra-research/tau2-bench",
                "environment_name": self.environment_name,
                "probe_mode": "public_task_metadata",
            },
        )

    def _build_probe_tasks(self) -> list[_RecordProbeTask]:
        records: list[dict[str, str]] = []
        data_root = self.repo_root / "data/tau2/domains"
        for domain in self.domains:
            path = data_root / domain / "tasks.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                public_id = f"{domain}:{item.get('id', len(records))}"
                description = item.get("description")
                instructions = (
                    item.get("user_scenario", {}).get("instructions", {})
                    if isinstance(item.get("user_scenario"), dict)
                    else {}
                )
                records.append(
                    {
                        "task_key": public_id,
                        "domain": domain,
                        "purpose": _short_text(
                            description.get("purpose", "")
                            if isinstance(description, dict)
                            else ""
                        ),
                        "reason_for_call": _short_text(
                            instructions.get("reason_for_call", "")
                            if isinstance(instructions, dict)
                            else ""
                        ),
                    }
                )
        return _records_to_probe_tasks(
            records=records,
            environment=self.environment_name,
            prompt_template=(
                "Select tau benchmark task {task_key} from visible public task "
                "records and return its domain."
            ),
            name_template="tau2 public task {task_key}",
            return_field="domain",
        )


@dataclass
class TerminalBenchProbeAdapter(_StructuredRecordProbeAdapter):
    """Public-metadata probe for the cloned Terminal-Bench repository."""

    repo_root: Path = Path("external/terminal-bench")

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="terminal-bench",
            description=(
                "Terminal-Bench task metadata probe over public task.yaml files "
                "without running Dockerized benchmark environments."
            ),
            base_tools=("terminal", "file_read", "test_runner"),
            action_tools=("shell_command",),
            observation_fields=("task_id", "instruction", "category", "difficulty"),
            helper_families=("record_selector", "terminal_plan_preparer"),
            safety_rules=(
                "helpers may only transform public task metadata",
                "helpers must not inspect reference completion scripts",
            ),
            metadata={
                "repo": "https://github.com/laude-institute/terminal-bench",
                "probe_mode": "public_task_metadata",
            },
        )

    def _build_probe_tasks(self) -> list[_RecordProbeTask]:
        records: list[dict[str, str]] = []
        for path in sorted((self.repo_root / "original-tasks").glob("*/task.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, dict):
                continue
            task_key = path.parent.name
            records.append(
                {
                    "task_key": task_key,
                    "category": _short_text(payload.get("category", "uncategorized")),
                    "difficulty": _short_text(payload.get("difficulty", "unknown")),
                    "instruction_excerpt": _short_text(payload.get("instruction", "")),
                }
            )
        return _records_to_probe_tasks(
            records=records,
            environment="terminal-bench",
            prompt_template=(
                "Select Terminal-Bench task {task_key} from visible task.yaml "
                "metadata and return its category."
            ),
            name_template="Terminal-Bench task {task_key}",
            return_field="category",
        )


@dataclass
class ScienceAgentBenchProbeAdapter(_StructuredRecordProbeAdapter):
    """Public-metadata probe for the cloned ScienceAgentBench repository."""

    repo_root: Path = Path("external/ScienceAgentBench")

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="scienceagentbench",
            description=(
                "ScienceAgentBench metadata probe. Uses full benchmark artifact "
                "instance directories when present, otherwise falls back to "
                "repository-level public setup records."
            ),
            base_tools=("read_data", "write_program", "run_evaluation"),
            action_tools=("submit_python_program",),
            observation_fields=("instance_id", "artifact_group", "output_type"),
            helper_families=("record_selector", "scientific_code_preparer"),
            safety_rules=(
                "helpers may only transform public benchmark metadata",
                "helpers must not read private grading assets",
            ),
            metadata={
                "repo": "https://github.com/OSU-NLP-Group/ScienceAgentBench",
                "probe_mode": "public_task_metadata",
            },
        )

    def _build_probe_tasks(self) -> list[_RecordProbeTask]:
        records = self._artifact_records()
        if not records:
            records = self._huggingface_annotation_records()
        if not records:
            records = [
                {
                    "task_key": "scienceagentbench-summary",
                    "category": "benchmark_summary",
                    "output_type": "self_contained_python_program",
                    "source": "README",
                },
                {
                    "task_key": "scienceagentbench-access",
                    "category": "benchmark_access",
                    "output_type": "annotation_sheet_plus_separate_artifacts",
                    "source": "README",
                },
                {
                    "task_key": "scienceagentbench-docker-eval",
                    "category": "evaluation_harness",
                    "output_type": "dockerized_program_evaluation",
                    "source": "README",
                },
            ]
        return _records_to_probe_tasks(
            records=records,
            environment="scienceagentbench",
            prompt_template=(
                "Select ScienceAgentBench record {task_key} from visible public "
                "metadata and return its category."
            ),
            name_template="ScienceAgentBench record {task_key}",
            return_field="category",
        )

    def _artifact_records(self) -> list[dict[str, str]]:
        benchmark_root = self.repo_root / "benchmark"
        records: list[dict[str, str]] = []
        for group in ("datasets",):
            group_root = benchmark_root / group
            if not group_root.exists():
                continue
            for child in sorted(group_root.iterdir()):
                task_key = child.stem if child.is_file() else child.name
                if not task_key:
                    continue
                records.append(
                    {
                        "task_key": task_key,
                        "category": group,
                        "output_type": "self_contained_python_program",
                        "source": "benchmark_artifacts",
                    }
                )
        deduped: dict[str, dict[str, str]] = {}
        for record in records:
            deduped.setdefault(record["task_key"], record)
        return list(deduped.values())

    def _huggingface_annotation_records(self) -> list[dict[str, str]]:
        try:
            from huggingface_hub import hf_hub_download
        except Exception:
            return []
        try:
            csv_path = Path(
                hf_hub_download(
                    "osunlp/ScienceAgentBench",
                    "ScienceAgentBench.csv",
                    repo_type="dataset",
                    cache_dir=self.repo_root / ".hf_cache",
                )
            )
        except Exception:
            return []
        records: list[dict[str, str]] = []
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in DictReader(handle):
                instance_id = str(row.get("instance_id", "")).strip()
                if not instance_id:
                    continue
                records.append(
                    {
                        "task_key": f"scienceagentbench:{instance_id}",
                        "category": _short_text(row.get("domain", "")),
                        "subtask_categories": _short_text(
                            row.get("subtask_categories", "")
                        ),
                        "instruction_excerpt": _short_text(row.get("task_inst", "")),
                        "source": "huggingface_annotation_sheet",
                    }
                )
        return records


def _records_to_probe_tasks(
    *,
    records: list[dict[str, str]],
    environment: str,
    prompt_template: str,
    name_template: str,
    return_field: str,
) -> list[_RecordProbeTask]:
    if not records:
        raise FileNotFoundError(f"no public task records found for {environment}")
    tasks: list[_RecordProbeTask] = []
    for index, record in enumerate(records):
        task_key = record["task_key"]
        visible_records = tuple(_record_window(records, index))
        task = TaskSpec(
            task_id=f"{environment}:{task_key}",
            name=name_template.format(task_key=task_key),
            prompt=prompt_template.format(task_key=task_key),
            artifacts={
                "records": json.dumps(visible_records),
                "match_field": "task_key",
                "return_field": return_field,
                "record_count": str(len(visible_records)),
            },
            metadata={
                "benchmark": environment,
                "public_task_id": task_key,
                "probe_mode": "public_task_metadata",
            },
        )
        tasks.append(
            _RecordProbeTask(
                task=task,
                records=visible_records,
                match_field="task_key",
                match_value=task_key,
                return_field=return_field,
                return_value=record.get(return_field, ""),
            )
        )
    return tasks


def _record_window(
    records: list[dict[str, str]], index: int, *, radius: int = 2
) -> list[dict[str, str]]:
    start = max(0, index - radius)
    end = min(len(records), index + radius + 1)
    return [dict(item) for item in records[start:end]]


def _short_text(value: object, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


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
