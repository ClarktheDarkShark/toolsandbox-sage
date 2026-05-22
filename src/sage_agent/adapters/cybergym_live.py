"""Live CyberGym submission adapter for standalone SAGE smoke runs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tarfile
import time
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

_SUBMIT_TIMESTAMPS: list[float] = []


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
    max_candidates: int = 12
    submit_timeout_seconds: float = 300.0
    fixed_side_check: bool = False
    fixed_side_api_key: str = "cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d"
    _feedback_memory: list[str] | None = None

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
            helper_families=(
                "visible_text_candidate_planner",
                "artifact_literal_candidate_planner",
                "source_boundary_candidate_planner",
                "execution_feedback_candidate_mutation_planner",
                "structured_input_candidate_planner",
                "adaptive_candidate_portfolio_planner",
                "format_edge_candidate_planner",
            ),
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
        candidate_families = {
            "visible_text_candidate_planner",
            "artifact_literal_candidate_planner",
            "source_boundary_candidate_planner",
            "execution_feedback_candidate_mutation_planner",
            "structured_input_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "format_edge_candidate_planner",
        }
        eligible = [
            (name, record)
            for name, record in helpers.items()
            if record.candidate.spec.family in candidate_families and not record.retired
        ]
        eligible.sort(key=_candidate_helper_route_key)
        return tuple(name for name, _ in eligible[:5])

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        description = task.artifacts.get("description", "")
        readme = task.artifacts.get("readme", "")
        artifact_summary = task.artifacts.get("artifact_summary", "")
        feedback = "\n".join((self._feedback_memory or [])[-12:])
        candidates = ["\x00\x01\x02\x03"]
        tool_uses: list[ToolUseRecord] = []
        if helpers:
            primary_batches: list[list[str]] = []
            secondary_batches: list[list[str]] = []
            per_helper_limit = max(3, self.max_candidates // max(len(helpers), 1))
            helper_items = sorted(
                helpers.items(),
                key=lambda item: (
                    0
                    if item[1].candidate.spec.family == "format_edge_candidate_planner"
                    else 1
                    if item[1].candidate.spec.family
                    == "adaptive_candidate_portfolio_planner"
                    else 2,
                    item[0],
                ),
            )
            for name, record in helper_items:
                validation = validate_helper_candidate(record.candidate)
                if validation.accepted:
                    planner = _load_helper(record)
                    is_adaptive_portfolio = record.candidate.spec.family in {
                        "adaptive_candidate_portfolio_planner",
                        "format_edge_candidate_planner",
                    }
                    candidate_limit = (
                        self.max_candidates
                        if is_adaptive_portfolio
                        else per_helper_limit
                    )
                    planned = _call_planner(
                        planner,
                        description=str(description),
                        readme=str(readme),
                        feedback=feedback,
                        artifact_summary=str(artifact_summary),
                        max_candidates=candidate_limit,
                    )
                    planned_candidates = [
                        str(item)
                        for item in planned.get("candidates", [])
                        if isinstance(item, str)
                    ][:candidate_limit]
                    if is_adaptive_portfolio:
                        primary_batches.append(planned_candidates)
                    else:
                        secondary_batches.append(planned_candidates)
                    tool_uses.append(
                        ToolUseRecord(
                            tool_name=name,
                            arguments={"description_chars": len(str(description))},
                            result={
                                "candidate_count": len(planned_candidates),
                                "artifact_summary_chars": len(str(artifact_summary)),
                                "first_candidate_len": len(planned_candidates[0])
                                if planned_candidates
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
            if primary_batches:
                candidates = _merge_candidate_batches(
                    primary_batches, limit=self.max_candidates
                )
                if len(candidates) < self.max_candidates:
                    candidates = _append_unique_candidates(
                        candidates,
                        _merge_candidate_batches(
                            secondary_batches,
                            limit=self.max_candidates - len(candidates),
                        ),
                        limit=self.max_candidates,
                    )
            else:
                candidates = _merge_candidate_batches(
                    secondary_batches, limit=self.max_candidates
                )
            if not candidates:
                candidates = ["\x00\x01\x02\x03"]
        return self.run_candidate_strings(
            task,
            candidates,
            transcript_prefix="SAGE generated-helper candidate submission",
            tool_uses=tuple(tool_uses),
            remember_feedback=True,
        )

    def run_candidate_strings(
        self,
        task: TaskSpec,
        candidates: list[str],
        *,
        transcript_prefix: str,
        tool_uses: tuple[ToolUseRecord, ...] = (),
        remember_feedback: bool = False,
    ) -> TaskRunResult:
        """Submit provided candidate strings through the live CyberGym task."""

        live_task = self._live_task(task.task_id)
        attempts = []
        success = False
        best_score = 0.0
        error = ""
        for index, candidate in enumerate(candidates[: self.max_candidates]):
            result = _submit_candidate(
                live_task.task_dir,
                index,
                candidate,
                timeout_seconds=self.submit_timeout_seconds,
                fixed_side_check=self.fixed_side_check,
                fixed_side_api_key=os.getenv("CYBERGYM_API_KEY")
                or self.fixed_side_api_key,
            )
            preview = _candidate_text_preview(candidate)
            if preview:
                result["candidate_text_preview"] = preview
            attempts.append(result)
            exit_code = int(result.get("exit_code", 0)) if result.get("ok") else 0
            if result.get("ok") and exit_code not in (0, 300):
                if not self.fixed_side_check or result.get("official_success"):
                    success = True
                    best_score = 1.0
                    break
            if not result.get("ok"):
                error = str(result.get("error", ""))
        transcript = (transcript_prefix,) + tuple(
            _attempt_summary(item) for item in attempts
        )
        if remember_feedback and self._feedback_memory is None:
            self._feedback_memory = []
        if remember_feedback and attempts and self._feedback_memory is not None:
            self._feedback_memory.extend(_attempt_summary(item) for item in attempts)
            self._feedback_memory = self._feedback_memory[-40:]
        normalized_tool_uses = tuple(
            ToolUseRecord(
                tool_name=use.tool_name,
                arguments=use.arguments,
                result=use.result,
                success=success if use.success else False,
                generated_helper=use.generated_helper,
            )
            for use in tool_uses
        )
        return TaskRunResult(
            task=task,
            success=success,
            score=best_score,
            outcome_score=best_score,
            transcript=transcript,
            tool_uses=normalized_tool_uses,
            artifacts={"attempts": attempts},
            error=error,
        )

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        if result.success:
            return None
        return GapSignal(
            key="visible_text_candidate_planning_from_context",
            summary=(
                "Create side-effect-free candidate input strings from visible task "
                "context and prior execution feedback for later submission by the "
                "environment."
            ),
            source_task_id=task.task_id,
            source_environment="cybergym-live",
            severity=0.8,
            suggested_tool_name="plan_visible_text_input_candidates",
            suggested_helper_family="visible_text_candidate_planner",
            evidence=(
                "visible description",
                "visible instructions",
                "visible source artifact summary",
                "execution feedback",
            ),
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
            generation_directives={"template": "visible_text_candidate_planner"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        template = str(gap.generation_directives.get("template", ""))
        if template == "artifact_literal_candidate_planner":
            return (
                ValidationCase(
                    name="artifact_literal_first",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": "literal: MAGIC_HEADER\nsource_line: size=4294967295",
                        "max_candidates": 4,
                    },
                    expected={
                        "candidate_count": 4,
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                    },
                ),
            )
        if template == "source_boundary_candidate_planner":
            return (
                ValidationCase(
                    name="source_boundary_constants",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": (
                            "literal: MAGIC_HEADER\n"
                            "source_line: if (size == 4294967295) crash();\n"
                            'source_line: if (!strcmp(token, "OPEN")) abort();'
                        ),
                        "max_candidates": 6,
                    },
                    expected={
                        "candidate_count": 6,
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                    },
                ),
            )
        if template == "execution_feedback_candidate_mutation_planner":
            return (
                ValidationCase(
                    name="feedback_mutations",
                    inputs={
                        "description": "Input length matters.",
                        "readme": "",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": "",
                        "max_candidates": 4,
                    },
                    expected={
                        "candidate_count": 4,
                        "first_candidate": "",
                        "abstain": False,
                    },
                ),
            )
        if template == "structured_input_candidate_planner":
            return (
                ValidationCase(
                    name="xml_structured_candidate",
                    inputs={
                        "description": "The parser reads XML input.",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": "",
                        "max_candidates": 4,
                    },
                    expected={
                        "candidate_count": 4,
                        "first_candidate": "<a/>",
                        "abstain": False,
                    },
                ),
            )
        if template == "adaptive_candidate_portfolio_planner":
            return (
                ValidationCase(
                    name="adaptive_candidate_portfolio",
                    inputs={
                        "description": "The parser reads XML input and has length checks.",
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "literal: MAGIC_HEADER\n"
                            "dict: \\\\A\n"
                            "source_line: if (size == 4294967295) crash();\n"
                            'source_line: if (!strcmp(token, "OPEN")) abort();'
                        ),
                        "max_candidates": 8,
                    },
                    expected={
                        "candidate_count": 8,
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                    },
                ),
            )
        if template == "format_edge_candidate_planner":
            kind = str(gap.generation_directives.get("format_kind", "generic"))
            return (
                ValidationCase(
                    name=f"{kind}_format_edges",
                    inputs={
                        "description": "The visible parser accepts regex input.",
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": "dict: \\\\A\nliteral: MAGIC_HEADER",
                        "max_candidates": 6,
                    },
                    expected={
                        "candidate_count": 6,
                        "abstain": False,
                    },
                ),
            )
        return (
            ValidationCase(
                name="visible_example_input",
                inputs={
                    "description": 'Example input: .file 4294967289 "xxx.c"',
                    "readme": "",
                    "feedback": "",
                    "artifact_summary": "",
                    "max_candidates": 6,
                },
                expected={
                    "candidate_count": 6,
                    "first_candidate": '.file 4294967289 "xxx.c"',
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="visible_artifact_literal",
                inputs={
                    "description": "",
                    "readme": "",
                    "feedback": "",
                    "artifact_summary": "literal: MAGIC_HEADER\nsource_line: size=4294967295",
                    "max_candidates": 6,
                },
                expected={
                    "candidate_count": 6,
                    "abstain": False,
                },
            ),
        )

    def _task_spec(self, task: CyberGymLiveTask) -> TaskSpec:
        readme = (task.task_dir / "README.md").read_text(encoding="utf-8")
        description = (task.task_dir / "description.txt").read_text(encoding="utf-8")
        artifact_summary = _visible_artifact_summary(task.task_dir)
        return TaskSpec(
            task_id=task.task_key,
            name=task.display_name,
            prompt=readme,
            artifacts={
                "description": description,
                "readme": readme,
                "artifact_summary": artifact_summary,
            },
            metadata={"environment": "cybergym-live"},
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
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
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
    return cast(Callable[..., Any], namespace[record.candidate.spec.name])


def _candidate_helper_route_key(
    item: tuple[str, HelperRecord],
) -> tuple[int, int, float, str]:
    """Prefer untested helpers, then helpers with stronger natural evidence."""

    name, record = item
    success_rate = record.successes / record.uses if record.uses else 0.0
    has_been_tested = 1 if record.uses else 0
    portfolio_priority = (
        0
        if record.candidate.spec.family == "format_edge_candidate_planner"
        else 1
        if record.candidate.spec.family == "adaptive_candidate_portfolio_planner"
        else 2
    )
    return (portfolio_priority, has_been_tested, -success_rate, name)


def _call_planner(
    planner: Callable[..., Any],
    *,
    description: str,
    readme: str,
    feedback: str,
    artifact_summary: str,
    max_candidates: int,
) -> dict[str, Any]:
    try:
        planned = planner(
            description=description,
            readme=readme,
            feedback=feedback,
            artifact_summary=artifact_summary,
            max_candidates=max_candidates,
        )
    except TypeError:
        try:
            planned = planner(
                description=description,
                readme=readme,
                feedback=feedback,
                max_candidates=max_candidates,
            )
        except TypeError:
            planned = planner(description=description, max_candidates=max_candidates)
    return planned if isinstance(planned, dict) else {}


def _merge_candidate_batches(
    candidate_batches: list[list[str]], *, limit: int
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    width = max((len(batch) for batch in candidate_batches), default=0)
    for index in range(width):
        for batch in candidate_batches:
            if index >= len(batch):
                continue
            candidate = batch[index]
            if candidate in seen:
                continue
            seen.add(candidate)
            unique.append(candidate)
            if len(unique) >= limit:
                return unique
    return unique


def _append_unique_candidates(
    primary: list[str], secondary: list[str], *, limit: int
) -> list[str]:
    unique = list(primary)
    seen = set(unique)
    for candidate in secondary:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return unique


def _visible_artifact_summary(task_dir: Path) -> str:
    """Summarize visible task artifacts without opening labels or reference PoCs."""

    archive = task_dir / "repo-vul.tar.gz"
    if not archive.exists():
        return ""
    lines: list[str] = []
    literal_count = 0
    source_count = 0
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = sorted(
                [
                    member
                    for member in tar.getmembers()
                    if member.isfile()
                    and member.size <= 350_000
                    and _looks_text_source(member.name)
                ],
                key=_artifact_member_priority,
            )[:80]
            for member in members:
                lines.append(f"file: {member.name}")
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                text = extracted.read(160_000).decode("utf-8", errors="ignore")
                if member.name.lower().endswith(".dict"):
                    for value in _dictionary_entries(text):
                        lines.append(f"dict: {value}")
                        literal_count += 1
                        if literal_count >= 80:
                            break
                for value in re.findall(r'"([^"\n\r]{1,96})"', text):
                    cleaned = value.strip()
                    if cleaned and _literal_has_signal(cleaned):
                        lines.append(f"literal: {cleaned}")
                        literal_count += 1
                        if literal_count >= 80:
                            break
                for raw_line in text.splitlines()[:600]:
                    if source_count >= 80:
                        break
                    stripped = raw_line.strip()
                    if 8 <= len(stripped) <= 160 and _source_line_has_signal(stripped):
                        lines.append(f"source_line: {stripped}")
                        source_count += 1
                if len("\n".join(lines)) >= 12_000:
                    break
    except (OSError, tarfile.TarError):
        return ""
    return "\n".join(lines)[:12_000]


def _looks_text_source(name: str) -> bool:
    lowered = name.lower()
    suffixes = (
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".py",
        ".rs",
        ".go",
        ".java",
        ".js",
        ".ts",
        ".txt",
        ".md",
        ".options",
        ".dict",
        ".diff",
        ".patch",
    )
    return lowered.endswith(suffixes)


def _dictionary_entries(text: str) -> list[str]:
    """Return visible fuzz-dictionary entries from a source archive member."""

    entries: list[str] = []
    for raw_line in text.splitlines()[:500]:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            line = line.split("=", 1)[1].strip()
        line = line.strip('"').strip("'")
        if 0 < len(line) <= 160:
            entries.append(line)
    return entries


def _literal_has_signal(value: str) -> bool:
    if len(value) >= 4 and any(ch.isalpha() for ch in value):
        return True
    return any(ch in value for ch in "()[]{}<>/\\_=:+-.0123456789")


def _artifact_member_priority(member: tarfile.TarInfo) -> tuple[int, int, int, str]:
    lowered = member.name.lower()
    basename = Path(lowered).name
    dictionary_or_options = basename.endswith((".dict", ".options"))
    fuzz_driver = "fuzz" in basename
    readme = basename in {"readme", "readme.md"}
    generated_patch = lowered.endswith((".diff", ".patch"))
    return (
        0 if dictionary_or_options else 1 if fuzz_driver else 2 if readme else 3,
        1 if generated_patch else 0,
        lowered.count("/"),
        lowered,
    )


def _source_line_has_signal(line: str) -> bool:
    lowered = line.lower()
    tokens = (
        "fuzz",
        "parse",
        "read",
        "input",
        "magic",
        "header",
        "version",
        "size",
        "length",
        "chunk",
        "token",
        "format",
        "assert",
        "crash",
        "memcpy",
        "strcpy",
        "strcmp",
    )
    return any(token in lowered for token in tokens) and any(
        ch in line for ch in "()[]{}<>/\\_=:+-.0123456789"
    )


def _submit_candidate(
    task_dir: Path,
    index: int,
    candidate: str,
    *,
    timeout_seconds: float,
    fixed_side_check: bool = False,
    fixed_side_api_key: str = "cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d",
) -> dict[str, Any]:
    _respect_submit_rate_limit()
    poc_path = task_dir / f"sage_candidate_{index}.poc"
    poc_path.write_bytes(candidate.encode("latin1", errors="ignore"))
    completed = subprocess.run(
        ["bash", str(task_dir / "submit.sh"), str(poc_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
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
    payload["ok"] = completed.returncode == 0 and "exit_code" in payload
    payload["candidate_index"] = index
    payload["poc_length"] = len(candidate)
    output = str(payload.get("output", ""))
    payload["output_excerpt"] = output[:600]
    payload.pop("output", None)
    payload["fixed_side_checked"] = False
    payload["official_success"] = False
    exit_code = int(payload.get("exit_code", 0))
    if fixed_side_check and exit_code not in (0, 300):
        fix_payload = _submit_fix_candidate(
            task_dir,
            poc_path,
            timeout_seconds=timeout_seconds,
            api_key=fixed_side_api_key,
        )
        payload["fixed_side_checked"] = bool(fix_payload.get("ok"))
        payload["fix_exit_code"] = fix_payload.get("exit_code")
        payload["fix_output_excerpt"] = str(fix_payload.get("output_excerpt", ""))[:600]
        if fix_payload.get("error"):
            payload["fixed_side_error"] = fix_payload.get("error")
        try:
            fix_exit_code = int(fix_payload.get("exit_code", 0))
        except (TypeError, ValueError):
            fix_exit_code = 0
        payload["official_success"] = bool(
            fix_payload.get("ok") and fix_exit_code in (0, 300)
        )
    elif not fixed_side_check:
        payload["official_success"] = exit_code not in (0, 300)
    return payload


def _submit_fix_candidate(
    task_dir: Path,
    poc_path: Path,
    *,
    timeout_seconds: float,
    api_key: str,
) -> dict[str, Any]:
    try:
        submit_script = (task_dir / "submit.sh").read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"read_submit_script_failed:{exc}"}
    server_match = re.search(r"curl\s+-X\s+POST\s+(\S+)/submit-vul", submit_script)
    metadata_match = re.search(r"-F\s+'metadata=(\{.*?\})'", submit_script, re.S)
    if not server_match or not metadata_match:
        return {"ok": False, "error": "submit_fix_metadata_unavailable"}
    server = server_match.group(1).strip()
    metadata = metadata_match.group(1).strip()
    completed = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            f"{server}/submit-fix",
            "-H",
            f"X-API-Key: {api_key}",
            "-F",
            f"metadata={metadata}",
            "-F",
            f"file=@{poc_path}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
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
            "returncode": completed.returncode,
            "error": (completed.stderr or completed.stdout)[-800:],
        }
    payload["ok"] = completed.returncode == 0 and "exit_code" in payload
    output = str(payload.get("output", ""))
    payload["output_excerpt"] = output[:600]
    payload.pop("output", None)
    return payload


def _respect_submit_rate_limit(
    *, max_requests: int = 18, window_seconds: float = 60.0
) -> None:
    """Stay below the CyberGym server's request limit during live comparisons."""

    now = time.monotonic()
    cutoff = now - window_seconds
    _SUBMIT_TIMESTAMPS[:] = [ts for ts in _SUBMIT_TIMESTAMPS if ts >= cutoff]
    if len(_SUBMIT_TIMESTAMPS) >= max_requests:
        sleep_for = window_seconds - (now - _SUBMIT_TIMESTAMPS[0]) + 0.5
        if sleep_for > 0:
            time.sleep(sleep_for)
        now = time.monotonic()
        cutoff = now - window_seconds
        _SUBMIT_TIMESTAMPS[:] = [ts for ts in _SUBMIT_TIMESTAMPS if ts >= cutoff]
    _SUBMIT_TIMESTAMPS.append(time.monotonic())


def _attempt_summary(attempt: Mapping[str, Any]) -> str:
    if not attempt.get("ok"):
        return f"candidate {attempt.get('candidate_index')}: submit failed"
    summary = (
        f"candidate {attempt.get('candidate_index')}: "
        f"exit_code={attempt.get('exit_code')} len={attempt.get('poc_length')}"
    )
    if attempt.get("fixed_side_checked"):
        summary += (
            f" fix_exit_code={attempt.get('fix_exit_code')} "
            f"official_success={bool(attempt.get('official_success'))}"
        )
    preview = str(attempt.get("candidate_text_preview", ""))
    if preview:
        summary += f"\ncandidate_text: {preview}"
        try:
            exit_code = int(attempt.get("exit_code", 0))
        except (TypeError, ValueError):
            exit_code = 0
        if exit_code not in (0, 300):
            summary += f"\ncrashing_candidate: {preview}"
    return summary


def _candidate_text_preview(candidate: str) -> str:
    """Return printable generated candidate text for feedback memory."""

    if not candidate or len(candidate) > 200:
        return ""
    if all(ch in "\n\r\t" or 32 <= ord(ch) <= 126 for ch in candidate):
        return candidate.replace("\r", "\\r").replace("\n", "\\n")
    return ""
