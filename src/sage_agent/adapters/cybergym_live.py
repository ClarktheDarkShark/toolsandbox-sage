"""Live CyberGym submission adapter for standalone SAGE smoke runs."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import time
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
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
    candidate_strategy: str = "balanced"
    adaptive_reserve_candidates: int = 0
    candidate_prescreen: str = "off"
    prescreen_submit_floor: int = 0
    prescreen_cmd_timeout_seconds: int = 10
    _feedback_memory: list[str] | None = None
    _last_feedback_task_id: str = ""

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
                "public_local_search_candidate_planner",
                "public_crash_pattern_candidate_planner",
                "visible_text_candidate_planner",
                "artifact_literal_candidate_planner",
                "source_boundary_candidate_planner",
                "semantic_description_candidate_planner",
                "execution_feedback_candidate_mutation_planner",
                "structured_input_candidate_planner",
                "adaptive_candidate_portfolio_planner",
                "visible_evidence_portfolio_candidate_planner",
                "format_edge_candidate_planner",
                "visible_sample_candidate_planner",
                "harness_envelope_candidate_planner",
            ),
            safety_rules=(
                "helpers must not submit PoCs",
                "helpers must not read reference PoCs or hidden labels",
                "helpers return candidate content only; the adapter performs submission",
            ),
            metadata={
                "tasks_root": str(self.tasks_root),
                "candidate_strategy": self.candidate_strategy,
                "adaptive_reserve_candidates": self.adaptive_reserve_candidates,
                "candidate_prescreen": self.candidate_prescreen,
                "prescreen_submit_floor": self.prescreen_submit_floor,
            },
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
        task_text = _task_visible_text(task)
        candidate_families = {
            "public_local_search_candidate_planner",
            "public_crash_pattern_candidate_planner",
            "visible_text_candidate_planner",
            "artifact_literal_candidate_planner",
            "source_boundary_candidate_planner",
            "semantic_description_candidate_planner",
            "execution_feedback_candidate_mutation_planner",
            "structured_input_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "visible_evidence_portfolio_candidate_planner",
            "format_edge_candidate_planner",
            "visible_sample_candidate_planner",
            "harness_envelope_candidate_planner",
        }
        eligible = [
            (name, record)
            for name, record in helpers.items()
            if record.candidate.spec.family in candidate_families and not record.retired
        ]
        strategy = _normalized_candidate_strategy(self.candidate_strategy)
        if strategy == "format_focus":
            eligible = _format_focused_helpers(eligible, task_text)
        eligible.sort(key=lambda item: _candidate_helper_route_key(item, task_text))
        route_limit = (
            8
            if strategy in {"sample_first", "wide_diverse"}
            else 5
            if strategy == "format_focus"
            else 8
            if strategy == "context_aware"
            else 6
        )
        return tuple(name for name, _ in eligible[:route_limit])

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        description = task.artifacts.get("description", "")
        readme = task.artifacts.get("readme", "")
        artifact_summary = task.artifacts.get("artifact_summary", "")
        if (
            self._feedback_memory is not None
            and self._last_feedback_task_id != task.task_id
        ):
            self._feedback_memory.clear()
            self._last_feedback_task_id = task.task_id
        feedback = "\n".join((self._feedback_memory or [])[-12:])
        candidates = ["\x00\x01\x02\x03"]
        tool_uses: list[ToolUseRecord] = []
        if helpers:
            primary_batches: list[list[str]] = []
            secondary_batches: list[list[str]] = []
            candidate_sources: dict[str, set[str]] = {}
            planning_limit = max(
                self.max_candidates,
                min(max(self.max_candidates * 16, 128), 256),
            )
            helper_items = sorted(
                helpers.items(),
                key=lambda item: _candidate_helper_route_key(
                    item, _task_visible_text(task)
                ),
            )
            task_text = _task_visible_text(task)
            for name, record in helper_items:
                validation = validate_helper_candidate(record.candidate)
                if validation.accepted:
                    planner = _load_helper(record)
                    is_adaptive_portfolio = _is_primary_candidate_family(
                        record.candidate.spec.family,
                        strategy=_normalized_candidate_strategy(
                            self.candidate_strategy
                        ),
                    )
                    planned = _call_planner(
                        planner,
                        description=str(description),
                        readme=str(readme),
                        feedback=feedback,
                        artifact_summary=str(artifact_summary),
                        max_candidates=planning_limit,
                    )
                    raw_planned_candidates = [
                        str(item)
                        for item in planned.get("candidates", [])
                        if isinstance(item, str)
                    ]
                    planned_candidates = _promote_candidates_for_strategy(
                        raw_planned_candidates,
                        task_text,
                        self.candidate_strategy,
                    )[:planning_limit]
                    for candidate in planned_candidates:
                        candidate_sources.setdefault(candidate, set()).add(name)
                        for payload in _expand_candidate_payload_variants([candidate]):
                            candidate_sources.setdefault(payload, set()).add(name)
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
            reserve_budget = max(0, int(self.adaptive_reserve_candidates))
            if primary_batches:
                candidates = _compose_candidate_submission_plan(
                    primary_batches,
                    secondary_batches,
                    limit=self.max_candidates,
                    reserve=reserve_budget,
                    strategy=self.candidate_strategy,
                    task_text=task_text,
                )
            else:
                initial_candidates = _promote_candidates_for_strategy(
                    _merge_candidate_batches(
                        secondary_batches, limit=max(self.max_candidates, 1) * 4
                    ),
                    task_text,
                    self.candidate_strategy,
                )[: self.max_candidates]
                if reserve_budget:
                    reserve_pool = _promote_candidates_for_strategy(
                        _merge_candidate_batches(
                            secondary_batches,
                            limit=max(self.max_candidates + reserve_budget, 1) * 4,
                        ),
                        task_text,
                        self.candidate_strategy,
                    )
                    candidates = _append_missing_candidates(
                        initial_candidates,
                        reserve_pool,
                        limit=self.max_candidates + reserve_budget,
                    )
                else:
                    candidates = initial_candidates
            if not candidates:
                candidates = ["\x00\x01\x02\x03"]
            submitted_source_map = {
                candidate: tuple(sorted(candidate_sources.get(candidate, ())))
                for candidate in candidates
            }
        else:
            submitted_source_map = {}
        return self.run_candidate_strings(
            task,
            candidates,
            transcript_prefix="SAGE generated-helper candidate submission",
            tool_uses=tuple(tool_uses),
            remember_feedback=True,
            candidate_sources=submitted_source_map,
        )

    def run_candidate_strings(
        self,
        task: TaskSpec,
        candidates: list[str],
        *,
        transcript_prefix: str,
        tool_uses: tuple[ToolUseRecord, ...] = (),
        remember_feedback: bool = False,
        candidate_sources: Mapping[str, tuple[str, ...]] | None = None,
    ) -> TaskRunResult:
        """Submit provided candidate strings through the live CyberGym task."""

        live_task = self._live_task(task.task_id)
        attempts = []
        success = False
        best_score = 0.0
        error = ""
        winning_candidate = ""
        winning_candidate_index = -1
        reserve_budget = max(0, int(self.adaptive_reserve_candidates))
        submit_limit = self.max_candidates + reserve_budget
        raw_candidate_pool = candidates[:submit_limit]
        candidate_pool = [
            candidate
            for candidate in raw_candidate_pool
            if not _is_public_search_control_candidate(candidate)
        ]
        runtime_candidate_sources: dict[str, set[str]] = {
            candidate: set((candidate_sources or {}).get(candidate, ()))
            for candidate in candidate_pool
        }
        batch_prescreens: dict[int, dict[str, Any]] = {}
        public_search_artifacts: list[dict[str, Any]] = []
        if self.candidate_prescreen in {"vulnerable-batch", "vulnerable-search"}:
            batch_prescreens = _local_vulnerable_batch_prescreen_candidates(
                live_task.task_key,
                live_task.task_dir,
                candidate_pool,
                timeout_seconds=self.submit_timeout_seconds,
                cmd_timeout_seconds=self.prescreen_cmd_timeout_seconds,
            )
        if self.candidate_prescreen == "vulnerable-search" and _public_search_requested(
            raw_candidate_pool,
            tool_uses,
        ):
            public_search_artifacts = _local_vulnerable_public_search_candidates(
                live_task.task_key,
                live_task.task_dir,
                seed_candidates=candidate_pool,
                timeout_seconds=self.submit_timeout_seconds,
                search_seconds=self.prescreen_cmd_timeout_seconds,
                max_artifacts=max(1, min(4, reserve_budget or 4)),
            )
            search_source = _public_search_source_name(tool_uses)
            for artifact in public_search_artifacts:
                candidate = str(artifact.get("candidate", ""))
                if not candidate or candidate in candidate_pool:
                    continue
                index = len(candidate_pool)
                candidate_pool.append(candidate)
                runtime_candidate_sources.setdefault(candidate, set()).add(
                    search_source
                )
                batch_prescreens[index] = {
                    "ok": True,
                    "candidate_index": index,
                    "prescreen_mode": "vulnerable-search",
                    "prescreen_exit_code": artifact.get("vulnerable_exit_code", 1),
                    "prescreen_crashed": True,
                    "prescreen_output_excerpt": str(artifact.get("log_excerpt", ""))[
                        :600
                    ],
                    "public_search_target": artifact.get("target", ""),
                    "public_search_artifact_size": artifact.get("size", len(candidate)),
                }
        for index, candidate in enumerate(candidate_pool):
            prescreen: dict[str, Any] = {}
            submit_official = True
            if self.candidate_prescreen == "vulnerable-local":
                prescreen = _local_vulnerable_prescreen_candidate(
                    live_task.task_key,
                    live_task.task_dir,
                    index,
                    candidate,
                    timeout_seconds=self.submit_timeout_seconds,
                    cmd_timeout_seconds=self.prescreen_cmd_timeout_seconds,
                )
                submit_official = (
                    not prescreen.get("ok")
                    or bool(prescreen.get("prescreen_crashed"))
                    or index < max(0, int(self.prescreen_submit_floor))
                )
            elif self.candidate_prescreen in {"vulnerable-batch", "vulnerable-search"}:
                prescreen = batch_prescreens.get(
                    index,
                    {
                        "ok": False,
                        "candidate_index": index,
                        "prescreen_mode": self.candidate_prescreen,
                        "error": "batch_prescreen_missing_result",
                    },
                )
                submit_official = bool(
                    prescreen.get("prescreen_crashed")
                ) or index < max(0, int(self.prescreen_submit_floor))
            if submit_official:
                result = _submit_candidate(
                    live_task.task_dir,
                    index,
                    candidate,
                    timeout_seconds=self.submit_timeout_seconds,
                    fixed_side_check=self.fixed_side_check,
                    fixed_side_api_key=os.getenv("CYBERGYM_API_KEY")
                    or self.fixed_side_api_key,
                )
                result["official_submitted"] = True
                if prescreen:
                    result.update(prescreen)
                    result["official_submitted"] = True
            else:
                result = {
                    **prescreen,
                    "ok": True,
                    "candidate_index": index,
                    "poc_length": len(candidate),
                    "exit_code": 0,
                    "official_submitted": False,
                    "official_success": False,
                }
            preview = _candidate_text_preview(candidate)
            if preview:
                result["candidate_text_preview"] = preview
            attempts.append(result)
            exit_code = int(result.get("exit_code", 0)) if result.get("ok") else 0
            if result.get("ok") and exit_code not in (0, 300):
                if not self.fixed_side_check or result.get("official_success"):
                    success = True
                    best_score = 1.0
                    winning_candidate = candidate
                    winning_candidate_index = index
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
            if len(self._feedback_memory) > 40:
                del self._feedback_memory[:-40]
        winning_sources = set(runtime_candidate_sources.get(winning_candidate, ()))
        normalized_tool_uses = tuple(
            _normalize_tool_use_success(
                use,
                task_success=success,
                winning_sources=winning_sources,
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
            artifacts={
                "attempts": attempts,
                "winning_candidate_index": winning_candidate_index,
                "winning_candidate_preview": _candidate_text_preview(winning_candidate),
                "candidate_budget": {
                    "initial": self.max_candidates,
                    "adaptive_reserve": reserve_budget,
                    "base_submit_limit": submit_limit,
                    "submit_limit": len(candidate_pool),
                    "submitted": len(attempts),
                    "reserve_used": len(attempts) > self.max_candidates,
                    "candidate_prescreen": self.candidate_prescreen,
                    "public_search_artifacts": len(public_search_artifacts),
                    "official_submitted": sum(
                        1 for item in attempts if item.get("official_submitted", True)
                    ),
                    "official_skipped": sum(
                        1
                        for item in attempts
                        if item.get("official_submitted") is False
                    ),
                },
            },
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
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                        "candidates_contains": ("MAGIC_HEADER",),
                        "candidates_max_count": 4,
                    },
                ),
            )
        if template == "public_local_search_candidate_planner":
            return (
                ValidationCase(
                    name="public_local_search_request_from_runtime_and_seeds",
                    inputs={
                        "description": "Public task exposes a fuzzer and visible seed corpus.",
                        "readme": "Submit one candidate input.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "runtime_binary: xaac_dec_fuzzer\n"
                            "source_line: LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)\n"
                            "corpus_sample: \\xff\\xf1\\x50\\x80"
                        ),
                        "max_candidates": 8,
                    },
                    expected={
                        "abstain": False,
                        "candidates_contains": ("search_strategy: public_local_fuzz",),
                        "candidates_contains_any_fragment": (
                            "runtime_binary",
                            "corpus_sample",
                            "source_line",
                        ),
                        "candidates_max_count": 8,
                    },
                ),
            )
        if template == "public_crash_pattern_candidate_planner":
            return (
                ValidationCase(
                    name="manual_public_patterns_from_visible_cues",
                    inputs={
                        "description": (
                            "A public parser task mentions glibc regex regexec, "
                            "PCRE2 fuzzsupport with very short input text, "
                            "libxml2 xmlSearchNsSafe, and jpeg_write_raw_data MCU padding."
                        ),
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "source_line: #include <magic.h>\n"
                            "source_line: magic_buffer(env->magic, data, size);\n"
                            "source_line: fuzzsupport short text\n"
                            "--with-html             HTML parser (on)"
                        ),
                        "max_candidates": 12,
                    },
                    expected={
                        "abstain": False,
                        "candidates_contains_any_fragment": (
                            "#include <magic.h>",
                            "0E-100000",
                            "MZ",
                            "--with-html",
                        ),
                        "candidates_max_count": 12,
                    },
                ),
            )
        if template == "visible_sample_candidate_planner":
            return (
                ValidationCase(
                    name="visible_samples_preserve_provenance",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "sample_escape: MZ\\x90\\x00PE\\x00\\x00A\n"
                            "sample_text: <root><a/></root>\n"
                            "literal: MAGIC_HEADER"
                        ),
                        "max_candidates": 5,
                    },
                    expected={
                        "first_candidate": "sample_escape: MZ\\x90\\x00PE\\x00\\x00A",
                        "abstain": False,
                        "candidates_contains": (
                            "sample_escape: MZ\\x90\\x00PE\\x00\\x00A",
                            "sample_text: <root><a/></root>",
                        ),
                        "candidates_max_count": 5,
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
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                        "candidates_contains_any": ("OPEN", "4294967295"),
                        "candidates_max_count": 6,
                    },
                ),
            )
        if template == "harness_envelope_candidate_planner":
            return (
                ValidationCase(
                    name="faad_length_split_harness_envelope",
                    inputs={
                        "description": (
                            "The public fuzzer uses len1, len2, flags, and "
                            "sizeof(NeAACDecConfiguration) before decoding AAC."
                        ),
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "source_line: size_t preamble = 2 + 2 + 1 + sizeof(NeAACDecConfiguration);\n"
                            "source_line: size_t len1 = data[0] | (data[1] << 8);\n"
                            "source_line: NeAACDecDecode(decoder, &faad_info, part2, len2);"
                        ),
                        "max_candidates": 6,
                    },
                    expected={
                        "abstain": False,
                        "candidates_min_unique": 4,
                        "candidates_contains_any_fragment": ("\xff\xf1", "ADIF"),
                        "candidates_max_count": 6,
                    },
                ),
                ValidationCase(
                    name="libxml_entity_harness_envelope",
                    inputs={
                        "description": (
                            "The public harness calls xmlFuzzDataInit, "
                            "xmlFuzzReadEntities, and xmlFuzzMainEntity."
                        ),
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "source_line: xmlFuzzDataInit(data, size);\n"
                            "source_line: xmlFuzzReadEntities();\n"
                            "source_line: docBuffer = xmlFuzzMainEntity(&docSize);"
                        ),
                        "max_candidates": 6,
                    },
                    expected={
                        "abstain": False,
                        "candidates_min_unique": 4,
                        "candidates_contains_any_fragment": ("main.xml", "<!DOCTYPE"),
                        "candidates_max_count": 6,
                    },
                ),
            )
        if template == "semantic_description_candidate_planner":
            return (
                ValidationCase(
                    name="semantic_visible_description",
                    inputs={
                        "description": (
                            "A parser validates XML namespace declarations and "
                            "attribute IDs from visible input text."
                        ),
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": "source_line: xmlValidateOneNamespace(ctx, node)",
                        "max_candidates": 8,
                    },
                    expected={
                        "abstain": False,
                        "candidates_min_unique": 2,
                        "candidates_max_count": 8,
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
                        "first_candidate": "",
                        "abstain": False,
                        "candidates_min_unique": 4,
                        "candidates_max_count": 4,
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
                        "first_candidate": "<a/>",
                        "abstain": False,
                        "candidates_contains": ("<root></root>",),
                        "candidates_max_count": 4,
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
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                        "candidates_contains_any_fragment": (
                            "OPEN",
                            "4294967295",
                            "\\A",
                        ),
                        "candidates_max_count": 8,
                    },
                ),
            )
        if template == "visible_evidence_portfolio_candidate_planner":
            return (
                ValidationCase(
                    name="visible_evidence_budgeted_portfolio",
                    inputs={
                        "description": (
                            "The visible harness accepts parser inputs for regex, "
                            "XML, htslib BAM/CRAM, and numeric boundary cases."
                        ),
                        "readme": "Submit candidate input strings only.",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": (
                            "sample_escape: MZ\\x90\\x00PE\\x00\\x00A\n"
                            "literal: MAGIC_HEADER\n"
                            "dict: \\\\A\n"
                            "--with-html             HTML parser (on)\n"
                            "source_line: #include <magic.h>\n"
                            "source_line: if (size == 4294967295) crash();\n"
                            'source_line: if (!strcmp(token, "OPEN")) abort();'
                        ),
                        "max_candidates": 10,
                    },
                    expected={
                        "abstain": False,
                        "candidates_min_unique": 8,
                        "candidates_contains_any_fragment": (
                            "MAGIC_HEADER",
                            "#include <magic.h>",
                            "4294967295",
                            "\\A",
                            "BAM",
                            "CRAM",
                            "--with-html",
                            "0E-100000",
                        ),
                        "candidates_max_count": 10,
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
                        "abstain": False,
                        "candidates_min_unique": 6,
                        "candidates_max_count": 6,
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
                    "abstain": False,
                    "candidates_contains_fragment": ('.file 4294967289 "xxx.c"',),
                    "candidates_max_count": 6,
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
                    "abstain": False,
                    "candidates_contains": ("MAGIC_HEADER",),
                    "candidates_max_count": 6,
                },
            ),
        )

    def _task_spec(self, task: CyberGymLiveTask) -> TaskSpec:
        readme = (task.task_dir / "README.md").read_text(encoding="utf-8")
        description = (task.task_dir / "description.txt").read_text(encoding="utf-8")
        runtime_summary = _public_runtime_entrypoint_summary(task.task_key)
        artifact_summary = "\n".join(
            item
            for item in (
                runtime_summary,
                _visible_artifact_summary(
                    task.task_dir,
                    context_text=f"{description}\n{readme}",
                ),
            )
            if item
        )
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
                "chr": chr,
                "dict": dict,
                "enumerate": enumerate,
                "float": float,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "ord": ord,
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


def _normalize_tool_use_success(
    use: ToolUseRecord,
    *,
    task_success: bool,
    winning_sources: set[str],
) -> ToolUseRecord:
    if not use.success:
        helper_success = False
    elif not task_success:
        helper_success = False
    elif winning_sources:
        helper_success = use.tool_name in winning_sources
    else:
        helper_success = task_success
    result = use.result
    if isinstance(result, dict):
        result = {
            **result,
            "attribution": "winning_candidate" if winning_sources else "task",
        }
    return ToolUseRecord(
        tool_name=use.tool_name,
        arguments=use.arguments,
        result=result,
        success=helper_success,
        generated_helper=use.generated_helper,
    )


def _task_visible_text(task: TaskSpec) -> str:
    parts = [task.name, task.prompt]
    parts.extend(str(value) for value in task.artifacts.values())
    return "\n".join(parts).lower()[:24_000]


def _normalized_candidate_strategy(strategy: str) -> str:
    value = str(strategy or "balanced").strip().lower().replace("-", "_")
    allowed = {
        "balanced",
        "format_focus",
        "context_aware",
        "literal_reserve",
        "sample_first",
        "source_first",
        "wide_diverse",
    }
    return value if value in allowed else "balanced"


def _format_focused_helpers(
    eligible: list[tuple[str, HelperRecord]], task_text: str
) -> list[tuple[str, HelperRecord]]:
    """Keep a compact bundle around the dominant visible input family."""

    scores = _format_cue_scores(task_text)
    dominant = (
        max(scores, key=scores.get) if scores and max(scores.values()) > 0 else ""
    )
    if not dominant:
        return eligible
    kept: list[tuple[str, HelperRecord]] = []
    for item in eligible:
        record = item[1]
        family = record.candidate.spec.family
        name = record.candidate.spec.name.lower()
        if family != "format_edge_candidate_planner":
            kept.append(item)
            continue
        if _format_edge_kind_from_name(name) == dominant:
            kept.append(item)
    return kept or eligible


def _is_primary_candidate_family(family: str, *, strategy: str) -> bool:
    if strategy == "sample_first":
        return family in {
            "public_local_search_candidate_planner",
            "visible_sample_candidate_planner",
            "artifact_literal_candidate_planner",
            "visible_text_candidate_planner",
            "format_edge_candidate_planner",
            "harness_envelope_candidate_planner",
            "public_crash_pattern_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "visible_evidence_portfolio_candidate_planner",
            "semantic_description_candidate_planner",
        }
    if strategy == "context_aware":
        return family in {
            "public_local_search_candidate_planner",
            "visible_sample_candidate_planner",
            "format_edge_candidate_planner",
            "harness_envelope_candidate_planner",
            "public_crash_pattern_candidate_planner",
            "semantic_description_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "visible_evidence_portfolio_candidate_planner",
            "source_boundary_candidate_planner",
            "artifact_literal_candidate_planner",
            "execution_feedback_candidate_mutation_planner",
        }
    if strategy == "source_first":
        return family in {
            "public_local_search_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "visible_evidence_portfolio_candidate_planner",
            "visible_sample_candidate_planner",
            "format_edge_candidate_planner",
            "harness_envelope_candidate_planner",
            "public_crash_pattern_candidate_planner",
            "semantic_description_candidate_planner",
            "source_boundary_candidate_planner",
            "artifact_literal_candidate_planner",
        }
    if strategy == "format_focus":
        return family in {
            "public_local_search_candidate_planner",
            "format_edge_candidate_planner",
            "harness_envelope_candidate_planner",
            "public_crash_pattern_candidate_planner",
            "visible_sample_candidate_planner",
            "visible_evidence_portfolio_candidate_planner",
            "adaptive_candidate_portfolio_planner",
            "semantic_description_candidate_planner",
            "source_boundary_candidate_planner",
        }
    return family in {
        "public_local_search_candidate_planner",
        "visible_sample_candidate_planner",
        "public_crash_pattern_candidate_planner",
        "visible_evidence_portfolio_candidate_planner",
        "adaptive_candidate_portfolio_planner",
        "format_edge_candidate_planner",
        "harness_envelope_candidate_planner",
        "semantic_description_candidate_planner",
    }


def _candidate_helper_route_key(
    item: tuple[str, HelperRecord],
    task_text: str = "",
) -> tuple[int, int, int, float, int, str]:
    """Route by public task fit, then by SAGE's natural-use evidence.

    The evidence term is intentionally label-free: it only uses whether a helper
    previously supplied a winning submitted candidate during this run. That lets
    the system exploit helpers that have demonstrated value without manually
    exposing a fixed tool set.
    """

    name, record = item
    success_rate = record.successes / record.uses if record.uses else 0.0
    has_been_tested = 1 if record.uses else 0
    family = record.candidate.spec.family
    task_relevance_penalty = _candidate_helper_task_penalty(record, task_text)
    portfolio_priority = {
        "public_local_search_candidate_planner": 0,
        "format_edge_candidate_planner": 1,
        "public_crash_pattern_candidate_planner": 2,
        "harness_envelope_candidate_planner": 3,
        "visible_sample_candidate_planner": 4,
        "visible_evidence_portfolio_candidate_planner": 5,
        "semantic_description_candidate_planner": 6,
        "adaptive_candidate_portfolio_planner": 7,
        "execution_feedback_candidate_mutation_planner": 8,
        "source_boundary_candidate_planner": 9,
        "artifact_literal_candidate_planner": 10,
        "structured_input_candidate_planner": 11,
        "visible_text_candidate_planner": 12,
    }.get(family, 8)
    portfolio_priority += task_relevance_penalty
    success_bonus = min(record.successes, 3)
    has_no_successes = 0 if record.successes else 1
    return (
        portfolio_priority - success_bonus,
        has_no_successes,
        has_been_tested,
        -success_rate,
        -record.successes,
        name,
    )


def _candidate_helper_task_penalty(record: HelperRecord, task_text: str) -> int:
    if not task_text:
        return 0
    family = record.candidate.spec.family
    name = record.candidate.spec.name.lower()
    if family == "format_edge_candidate_planner":
        kind = _format_edge_kind_from_name(name)
        if not kind:
            return 12
        scores = _format_cue_scores(task_text)
        own_score = scores.get(kind, 0)
        top_score = max(scores.values() or (0,))
        if own_score <= 0:
            return 24
        if own_score == top_score:
            return 0
        if own_score >= 3 and own_score >= int(top_score * 0.6):
            return 4
        return 24
    if family == "harness_envelope_candidate_planner":
        return 0 if _has_harness_visible_cue(task_text) else 14
    if family == "public_local_search_candidate_planner":
        return -4 if _has_public_local_search_visible_cue(task_text) else 18
    if family == "public_crash_pattern_candidate_planner":
        return 0 if _has_public_crash_pattern_visible_cue(task_text) else 8
    if family == "semantic_description_candidate_planner":
        return 0 if _has_semantic_visible_cue(task_text) else 6
    if family == "visible_evidence_portfolio_candidate_planner":
        return (
            0
            if _has_semantic_visible_cue(task_text)
            or _has_source_visible_cue(task_text)
            else 2
        )
    if family == "source_boundary_candidate_planner":
        return 0 if _has_source_visible_cue(task_text) else 4
    if family == "structured_input_candidate_planner":
        return 0 if _has_structured_visible_cue(task_text) else 5
    if family == "visible_sample_candidate_planner":
        return -3 if _has_visible_sample_cue(task_text) else 5
    if family == "visible_text_candidate_planner":
        return -2 if _has_visible_example_cue(task_text) else 2
    return 0


def _has_semantic_visible_cue(text: str) -> bool:
    cues = (
        "xml",
        "html",
        "namespace",
        "doctype",
        "regex",
        "pcre",
        "yara",
        "portable executable",
        "pe module",
        "bam",
        "cram",
        "sam",
        "ssh",
        "kex",
        "decimal",
        "bignum",
        "selinux",
        "policy",
        "font",
        "cff",
        "json",
        "jq",
    )
    return any(cue in text for cue in cues)


def _has_public_crash_pattern_visible_cue(text: str) -> bool:
    cues = (
        "magic_buffer",
        "#include <magic.h>",
        "regexec",
        "fuzzsupport",
        "very short",
        "pcre2",
        "rules_fuzzer",
        "incorrect argument type",
        "portable executable",
        "pe module",
        "jpeg_write_raw_data",
        "mcu",
        "xmlsearchnssafe",
        "xmladdidsafe",
        "xmlremoveid",
        "libxml2",
        "--with-html",
        "neaacdec",
        "faad",
        "xaac",
    )
    return any(cue in text for cue in cues)


def _has_public_local_search_visible_cue(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "runtime_binary:",
            "runtime_entrypoint:",
            "llvmfuzzertestoneinput",
            "libfuzzer",
            "honggfuzz",
            "seed_corpus",
            "corpus_sample:",
            "sample_escape:",
            "sample_text:",
            "fuzzer",
            "fuzz target",
        )
    )


def _has_harness_visible_cue(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "llvmfuzzertestoneinput",
            "fuzzeddata",
            "xmlfuzzdatainit",
            "xmlfuzzreadentities",
            "xmlfuzzmainentity",
            "sizeof(neaacdecconfiguration)",
            "size_t preamble",
            "len1 = data[0]",
            "len2 = data[0]",
            "consumeintegral",
            "consume_bytes",
        )
    )


def _has_source_visible_cue(text: str) -> bool:
    return "source_line:" in text and any(
        cue in text
        for cue in (
            "size",
            "length",
            "magic",
            "header",
            "version",
            "strcmp",
            "memcmp",
            "assert",
            "abort",
        )
    )


def _has_structured_visible_cue(text: str) -> bool:
    cues = (
        "xml",
        "html",
        "json",
        "csv",
        "regex",
        "pcre",
        "path",
        "parser",
        "reader",
    )
    return any(cue in text for cue in cues)


def _has_visible_example_cue(text: str) -> bool:
    cues = (
        "example input:",
        "example:",
        "such as",
        "for example",
        "e.g.",
        "candidate:",
        "literal:",
        "dict:",
        "token:",
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
    )
    return any(cue in text for cue in cues)


def _has_visible_sample_cue(text: str) -> bool:
    cues = (
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
        "/tests/",
        "/test/",
        "/samples/",
        "/sample",
        "/fixtures/",
        "/fixture",
        "corpus",
        "seed",
    )
    return any(cue in text for cue in cues)


def _format_edge_kind_from_name(name: str) -> str:
    for kind in ("regex", "xml", "numeric", "json", "file_format", "binary_protocol"):
        if f"plan_{kind}_" in name:
            return kind
    return ""


def _format_cue_scores(text: str) -> dict[str, int]:
    """Score dominant visible input families without using labels or outcomes."""

    cue_groups = {
        "regex": (
            "regex",
            "regexp",
            "pcre",
            "oniguruma",
            "capture",
            "capturing",
            "ovector",
            "pattern",
        ),
        "xml": (
            "xml",
            "html",
            "doctype",
            "xmlns",
            "namespace",
            "libxml",
            "xinclude",
            "xpath",
            "schema",
        ),
        "numeric": (
            "float",
            "double",
            "decimal",
            "numeric",
            "number",
            "integer",
            "bignum",
            "big num",
            "crypt_int",
            "array",
            "out-of-bounds",
            "tpm",
        ),
        "json": (
            "json",
            "jq",
            "decnumber",
            "jv_",
            "jvp_",
            "parse_extended",
        ),
        "file_format": (
            "portable executable",
            "pe module",
            "mz header",
            "elf",
            "png",
            "jpeg",
            "jpg",
            "zip",
            "pdf",
            "font",
            "freetype",
            "opentype",
            "cff",
            "bam",
            "cram",
            "sam",
            "htslib",
            "selinux",
            "policy",
            "binary file",
            "file format",
            "audio",
            "codec",
            "decoder",
            "decode",
            "media",
            "aac",
            "xaac",
            "adts",
            "wave",
            "wav",
            "ogg",
            "flac",
        ),
        "binary_protocol": (
            "ssh",
            "libssh",
            "kex",
            "handshake",
            "protocol",
            "packet",
            "frame",
            "framed",
            "transport",
            "uart",
            "message",
            "socket",
        ),
    }
    scores: dict[str, int] = {}
    lines = text.splitlines()
    for kind, cues in cue_groups.items():
        score = 0
        for line in lines:
            line_score = sum(1 for cue in cues if cue in line)
            if not line_score:
                continue
            if "description" in line or "vulnerability" in line:
                line_score *= 3
            if "fuzz" in line or "fuzzer" in line or line.startswith("file:"):
                line_score *= 2
            score += min(line_score, 8)
        scores[kind] = score
    return scores


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


def _promote_candidates_for_strategy(
    candidates: list[str],
    task_text: str,
    strategy: str,
) -> list[str]:
    mode = _normalized_candidate_strategy(strategy)
    if mode in {
        "context_aware",
        "format_focus",
        "source_first",
        "sample_first",
        "literal_reserve",
        "wide_diverse",
    }:
        seeded = _append_missing_candidates(
            list(candidates),
            _public_task_shape_seed_candidates(task_text),
            limit=max(len(candidates) + 64, 64),
        )
        ranked = _promote_task_relevant_candidate_signals(seeded, task_text)
        return _diversify_candidate_frontier(ranked, task_text)
    return _promote_visible_candidate_signals(candidates)


def _promote_task_relevant_candidate_signals(
    candidates: list[str],
    task_text: str = "",
) -> list[str]:
    """Promote visible candidates that match the current task's public cues.

    This is intentionally label-free: it uses README/description/artifact terms
    only, then ranks already generated candidate strings. It does not inspect
    hidden PoCs, expected answers, or previous SAGE outcome traces.
    """

    expanded = _promote_visible_candidate_signals(candidates)
    text = str(task_text or "").lower()
    if not text:
        return expanded
    indexed = list(enumerate(expanded))
    ranked = sorted(
        indexed,
        key=lambda item: (
            -_task_candidate_relevance_score(item[1], text),
            item[0],
        ),
    )
    return [candidate for _, candidate in ranked]


def _public_task_shape_seed_candidates(task_text: str) -> list[str]:
    """Add public, format-generic probes from visible task cues only.

    These are not answers and do not inspect hidden PoCs. They give the limited
    candidate budget a fair first pass across parser families when generated
    helpers identify a format but return mostly shallow generic seeds.
    """

    text = str(task_text or "").lower()
    seeds: list[str] = []
    if _has_binary_protocol_task_cue(text):
        seeds.extend(
            [
                "\\x00",
                "\\x00\\x00\\x00\\x00",
                "\\xff\\xff\\xff\\xff",
                "\\x01\\x00\\x00\\x00",
                "\\x02A\\x03",
                "\\x00A\\x00",
                "A\\x00A",
                "MSG\\x00\\x00\\x00\\x01A",
                "LEN=1\\nA",
            ]
        )
    if _has_media_file_task_cue(text):
        seeds.extend(
            [
                "\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc",
                "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc",
                "ADIF",
                "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00",
                "RIFF\\x24\\x00\\x00\\x00WAVEfmt ",
                "OggS\\x00\\x02",
                "fLaC\\x00\\x00\\x00\\x22",
            ]
        )
    if any(cue in text for cue in ("xml", "html", "doctype", "namespace", "xmlns")):
        seeds.extend(
            [
                "<a/>",
                "<?xml version='1.0'?><a/>",
                "<!DOCTYPE a><a/>",
                "<a xmlns:p='urn:x' p:id='x' id='x'/>",
            ]
        )
    if any(cue in text for cue in ("regex", "regexp", "pcre", "pattern")):
        seeds.extend(["(", "(a", "[a-", "\\K", "\\C", "(a)\\1"])
    if any(cue in text for cue in ("json", "jq", "javascript")):
        seeds.extend(["{}", "[]", '{"a":1}', "[1e309]", '"unterminated'])
    return _expand_candidate_payload_variants(seeds)


def _task_candidate_relevance_score(candidate: str, task_text: str) -> int:
    base = _visible_candidate_signal_score(candidate)
    value = str(candidate or "").strip()
    lowered = value.lower()
    payload = _candidate_payload_value(value)
    if payload:
        value = payload
        lowered = value.lower()
        base = max(base, _visible_candidate_signal_score(value))

    score = base
    format_scores = _format_cue_scores(task_text)
    dominant = max(format_scores, key=format_scores.get) if format_scores else ""
    dominant_score = format_scores.get(dominant, 0)

    if _has_harness_visible_cue(task_text) and _looks_harness_envelope_payload(value):
        score += 280

    if dominant == "regex" and dominant_score > 0:
        if any(token in value for token in ("(", "[a-", "\\K", "\\C", "\\1", "(?")):
            score += 170
        if _looks_file_magic_payload(value):
            score -= 120
    elif dominant == "xml" and dominant_score > 0:
        if lowered.startswith(("<?xml", "<!doctype", "<html", "<a", "<root", "<svg")):
            score += 180
        if "xmlns" in lowered or "doctype" in lowered or "entity" in lowered:
            score += 80
        if _looks_file_magic_payload(value):
            score -= 120
    elif dominant == "numeric" and dominant_score > 0:
        if _looks_numeric_edge_literal(value) or _wraps_numeric_edge_literal(value):
            score += 180
        if any(ch.isdigit() for ch in value) and len(value) <= 48:
            score += 70
        if lowered.startswith(("<", "mz", "%pdf", "pk")):
            score -= 100
    elif dominant == "json" and dominant_score > 0:
        if lowered.startswith(("{", "[", '"')) or lowered in {"true", "false", "null"}:
            score += 190
        if _looks_numeric_edge_literal(value) or _wraps_numeric_edge_literal(value):
            score += 140
        if any(token in lowered for token in ("decnumber", "0e", "1e", "e+", "e-")):
            score += 120
        if _looks_file_magic_payload(value):
            score -= 140
    elif dominant == "binary_protocol" and dominant_score > 0:
        if _looks_binary_protocol_payload(value) or "\\x" in candidate:
            score += 160
        if any(
            token in lowered
            for token in ("kex", "packet", "handshake", "msg", "len=", "uart")
        ):
            score += 80
        if _looks_file_magic_payload(value) and not _looks_media_file_payload(value):
            score -= 120
        if _looks_numeric_edge_literal(value) or lowered.startswith(
            ("<", "mz", "%pdf", "pk", "cram")
        ):
            score -= 80
    elif dominant == "file_format" and dominant_score > 0:
        score += _file_format_candidate_relevance(value, task_text)

    if lowered.startswith(("source_line: #include", "#include")) and not (
        dominant == "file_format" and "magic" in task_text and "magic" in lowered
    ):
        score -= 80
    if lowered.startswith(
        ("source_line:", "--with-", "--without-", "--enable-", "--disable-")
    ):
        score -= 35
    if _looks_documentation_or_badge(value):
        score -= 100
    return score


def _diversify_candidate_frontier(
    candidates: list[str], task_text: str = ""
) -> list[str]:
    """Keep the early submission frontier broad across input-shape families."""

    text = str(task_text or "").lower()
    caps = {
        "harness_envelope": 8 if _has_harness_visible_cue(text) else 2,
        "media_file": 6 if _has_media_file_task_cue(text) else 3,
        "binary_protocol": 6 if _has_binary_protocol_task_cue(text) else 3,
        "visible_sample": 6,
        "file_magic": 3,
        "markup": 4,
        "numeric": 3,
        "regex": 3,
        "json": 3,
        "option": 3,
        "source": 2,
        "tabular": 3,
        "long_fill": 2,
        "other": 5,
    }
    frontier: list[str] = []
    deferred: list[str] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        bucket = _candidate_frontier_bucket(candidate)
        cap = caps.get(bucket, 4)
        count = counts.get(bucket, 0)
        if count < cap:
            frontier.append(candidate)
            counts[bucket] = count + 1
        else:
            deferred.append(candidate)
    return frontier + deferred


def _candidate_frontier_bucket(candidate: str) -> str:
    value = str(candidate or "").strip()
    lowered = value.lower()
    payload = _candidate_payload_value(value)
    if payload:
        value = payload
        lowered = value.lower()
    if lowered.startswith(("sample_text:", "sample_escape:", "corpus_sample:")):
        return "visible_sample"
    if _looks_harness_envelope_payload(value):
        return "harness_envelope"
    if _looks_media_file_payload(value):
        return "media_file"
    if _looks_binary_protocol_payload(value):
        return "binary_protocol"
    if _looks_file_magic_payload(value):
        return "file_magic"
    if _looks_numeric_edge_literal(value) or _wraps_numeric_edge_literal(value):
        return "numeric"
    if value.startswith("<") or lowered.startswith(("<?xml", "<!doctype")):
        return "markup"
    if lowered.startswith(("{", "[", '"')) or lowered in {"true", "false", "null"}:
        return "json"
    if any(token in value for token in ("\\K", "\\C", "\\1", "(?", "[a-", "(")):
        return "regex"
    if value.startswith("--") or value.startswith("-D"):
        return "option"
    if lowered.startswith("source_line:"):
        return "source"
    if "\t" in value and value.count("\t") >= 2:
        return "tabular"
    if len(value) >= 96 and len(set(value)) <= 4:
        return "long_fill"
    return "other"


def _has_binary_protocol_task_cue(text: str) -> bool:
    cues = (
        "binary_message",
        "binary message",
        "protocol",
        "packet",
        "frame",
        "framed",
        "transport",
        "uart",
        "socket",
        "handshake",
        "kex",
        "ssh",
    )
    return any(cue in text for cue in cues)


def _has_media_file_task_cue(text: str) -> bool:
    cues = (
        "audio",
        "codec",
        "decoder",
        "decode",
        "encoder",
        "media",
        "aac",
        "xaac",
        "adts",
        "mpeg",
        "wave",
        "wav",
        "ogg",
        "flac",
    )
    return any(cue in text for cue in cues)


def _looks_binary_protocol_payload(value: str) -> bool:
    text = str(value or "")
    lowered = text.lower()
    if not text:
        return False
    return (
        text.startswith(("\x00", "\x01", "\x02", "\xff", "SSH-"))
        or "\\x" in text
        or lowered.startswith(("msg", "len=", "packet", "frame", "uart"))
        or "\x00" in text
    )


def _looks_media_file_payload(value: str) -> bool:
    text = str(value or "")
    lowered = text.lower()
    if not text:
        return False
    return text.startswith(
        (
            "\xff\xf1",
            "\xff\xf9",
            "ADIF",
            "ID3",
            "RIFF",
            "OggS",
            "fLaC",
        )
    ) or lowered.startswith(("adts", "aac", "wave", "wav", "ogg", "flac"))


def _looks_harness_envelope_payload(value: str) -> bool:
    text = str(value or "")
    lowered = text.lower()
    if not text:
        return False
    if "main.xml\\\n" in text or (
        "main.xml" in text
        and ("<!doctype" in lowered or "<?xml" in lowered or "<a" in lowered)
    ):
        return True
    if "\xff\xf1" in text or "\xff\xf9" in text or "ADIF" in text or "ID3" in text:
        if len(text) > 12 and (text[0] not in "\xffAIROf" or "\x00" in text[:32]):
            return True
    if (
        len(text) >= 8
        and any(ch == "\x00" for ch in text[:8])
        and ("<" in text[8:] or "\xff" in text[8:] or "ADIF" in text[8:])
    ):
        return True
    return False


def _file_format_candidate_relevance(candidate: str, task_text: str) -> int:
    value = str(candidate or "")
    lowered = value.lower()
    text = task_text
    score = 0
    if "magic" in text and lowered.startswith("#include") and "magic" in lowered:
        score += 260
    if any(cue in text for cue in ("yara", "rules_fuzzer", "yr_")):
        if lowered.startswith(("rule ", 'import "pe"', "import pe")):
            score += 220
        elif lowered.startswith(("mz", "\x7felf", "%pdf", "pk")):
            score += 35
    if any(
        cue in text for cue in ("htslib", "bam", "cram", " sam", ".sam", "bcf", "vcf")
    ):
        if lowered.startswith(("@hd", "@sq", "@rg", "@pg", "bam\x01", "cram")):
            score += 230
        if "\t" in value and value.count("\t") >= 4:
            score += 160
        if lowered.startswith(("mz", "%pdf", "pk", "otto", "cff ")):
            score -= 130
    if any(
        cue in text
        for cue in ("portable executable", "pe module", "mz header", "pe_fuzzer")
    ):
        if value.startswith("MZ") or lowered.startswith('import "pe"'):
            score += 220
    if any(cue in text for cue in ("selinux", "policycoreutils", "policy", "sepol")):
        if lowered.startswith(("policy_module", "class ", "common ", "allow ", "sid ")):
            score += 220
        if lowered.startswith(("mz", "%pdf", "pk")):
            score -= 130
    if any(
        cue in text for cue in ("freetype", "font", "cff", "opentype", "type_1", "sfnt")
    ):
        if value.startswith(("OTTO", "CFF ", "\x00\x01\x00\x00", "ttcf")):
            score += 220
        if lowered.startswith(("mz", "%pdf", "pk")):
            score -= 110
    if _has_media_file_task_cue(text):
        if _looks_media_file_payload(value):
            score += 240
        if lowered.startswith(("mz", "%pdf", "pk", "cram", "@hd", "@sq")):
            score -= 140
    if "pdf" in text and value.startswith("%PDF"):
        score += 220
    if "png" in text and value.startswith("\x89PNG"):
        score += 220
    if "jpeg" in text or "jpg" in text:
        if value.startswith("\xff\xd8\xff"):
            score += 220
    if "zip" in text and value.startswith("PK"):
        score += 220
    if "elf" in text and value.startswith("\x7fELF"):
        score += 220
    return score


def _promote_visible_candidate_signals(candidates: list[str]) -> list[str]:
    """Promote strong visible-artifact candidates without using hidden outcomes."""

    indexed = list(enumerate(_expand_candidate_payload_variants(candidates)))
    high_signal: list[tuple[int, int, str]] = []
    normal: list[tuple[int, int, str]] = []
    low_signal: list[tuple[int, int, str]] = []
    for index, candidate in indexed:
        score = _visible_candidate_signal_score(candidate)
        if score >= 50:
            high_signal.append((-score, index, candidate))
        elif score <= -25:
            low_signal.append((-score, index, candidate))
        else:
            normal.append((-score, index, candidate))
    high_signal.sort()
    diverse: list[str] = []
    deferred: list[tuple[int, int, str]] = []
    category_counts: dict[str, int] = {}
    category_caps = {
        "option": 2,
        "url": 2,
        "dict": 6,
        "escape": 4,
        "markup": 4,
        "source": 4,
        "sample": 8,
    }
    for item in high_signal:
        category = _visible_candidate_category(item[2])
        count = category_counts.get(category, 0)
        cap = category_caps.get(category, 8)
        if count < cap:
            diverse.append(item[2])
            category_counts[category] = count + 1
        else:
            deferred.append(item)
    return diverse + [item[2] for item in deferred + normal + low_signal]


def _expand_candidate_payload_variants(candidates: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = str(candidate)
        payload = _candidate_payload_value(value)
        # Provenance prefixes explain where a visible signal came from. The
        # environment should receive the clean payload, not the provenance text.
        variants = (payload,) if payload else (value,)
        for item in variants:
            if not item or item in seen:
                continue
            seen.add(item)
            expanded.append(item)
    return expanded


def _candidate_payload_value(candidate: str) -> str:
    value = str(candidate or "").strip()
    lowered = value.lower()
    for prefix in (
        "dict:",
        "literal:",
        "source_line:",
        "token:",
        "example input:",
        "example:",
        "input:",
        "candidate_text:",
        "crashing_candidate:",
        "trigger:",
        "poc:",
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
    ):
        if lowered.startswith(prefix):
            payload = value[len(prefix) :].strip(" :,;\t")
            if prefix in {"sample_escape:", "corpus_sample:"}:
                decoded = _decode_visible_escape_payload(payload)
                return decoded if decoded else payload
            return payload
    if "\\x" in value or "\\u" in value:
        decoded = _decode_visible_escape_payload(value)
        if decoded and decoded != value:
            return decoded
    return ""


def _decode_visible_escape_payload(value: str) -> str:
    """Decode visible escaped sample bytes into the candidate string to submit."""

    text = str(value or "")
    if not text or "\\" not in text:
        return text
    try:
        return text.encode("latin1", errors="backslashreplace").decode(
            "unicode_escape", errors="ignore"
        )
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError):
        return text


def _visible_candidate_category(candidate: str) -> str:
    value = str(candidate or "").strip()
    lowered = value.lower()
    if value.startswith("--") or value.startswith("-D"):
        return "option"
    if "://" in value:
        return "url"
    if _looks_file_magic_payload(value) or _looks_structured_sample_payload(value):
        return "sample"
    if value.startswith("\\") or "\\x" in value or "\\u" in value:
        return "escape"
    if lowered.startswith(("sample_text:", "sample_escape:", "corpus_sample:")):
        return "sample"
    if lowered.startswith("dict:"):
        return "dict"
    if value.startswith("<") and value.endswith(">"):
        return "markup"
    if lowered.startswith("source_line:"):
        return "source"
    return "other"


def _visible_candidate_signal_score(candidate: str) -> int:
    value = str(candidate or "").strip()
    lowered = value.lower()
    if not value:
        return -40
    payload = _candidate_payload_value(value)
    if payload:
        payload_score = _visible_candidate_signal_score(payload)
        if lowered.startswith("dict:"):
            if payload.startswith("&"):
                return max(payload_score + 35, 115)
            if payload.startswith("<"):
                return max(payload_score - 1, 70)
            if (
                payload.startswith("\\")
                or "\\x" in payload
                or "\\u" in payload
                or _looks_numeric_edge_literal(payload)
            ):
                return max(payload_score - 1, 84)
            return max(payload_score + 10, 75)
        if lowered.startswith("literal:"):
            return max(payload_score - 2, 70)
        if lowered.startswith(("sample_escape:", "corpus_sample:")):
            return max(payload_score + 25, 135)
        if lowered.startswith("sample_text:"):
            return max(payload_score + 15, 105)
        return max(payload_score - 5, 45)
    if _looks_file_magic_payload(value):
        return 155
    if _looks_structured_sample_payload(value):
        return 118
    if lowered in {"license", "as is"} or "copyright" in lowered:
        return -35
    if _looks_numeric_edge_literal(value):
        return 135
    if _wraps_numeric_edge_literal(value):
        return 125
    if lowered.startswith(("source_line: #include", "#include")):
        return _include_candidate_score(lowered)
    if _looks_documentation_or_badge(value):
        return 15
    score = 0
    if lowered.startswith("dict:"):
        score = max(score, 120)
    if lowered.startswith(("literal:", "source_line:", "token:")):
        score = max(score, 90)
    if lowered.startswith(("sample_escape:", "corpus_sample:")):
        score = max(score, 130)
    if lowered.startswith("sample_text:"):
        score = max(score, 100)
    if lowered.startswith("#include"):
        score = max(score, _include_candidate_score(lowered))
    if value.startswith("--") or value.startswith("-D"):
        score = max(score, 115)
        if any(
            token in lowered
            for token in (
                "html",
                "xml",
                "json",
                "regex",
                "regexp",
                "reader",
                "parser",
                "schema",
                "valid",
                "xinclude",
                "xpath",
            )
        ):
            score = max(score, 128)
        if any(
            token in lowered
            for token in (
                "debug",
                "history",
                "readline",
                "catalog",
                "thread",
                "python",
                "module",
            )
        ):
            score = min(score, 92)
    if "://" in value:
        score = max(score, 110)
    if value.startswith("\\") or "\\x" in value or "\\u" in value:
        score = max(score, 85)
    if value.startswith("<") and value.endswith(">"):
        score = max(score, 75)
    if lowered.startswith(("0x", "-0x")):
        score = max(score, 70)
    if any(ch.isdigit() for ch in value) and all(
        ch in "+-0123456789.eE" for ch in value
    ):
        score = max(score, 70)
    if "magic" in lowered and any(ch in value for ch in "<>/\\"):
        score = max(score, 65)
    if any(token in lowered for token in ("strcmp", "memcmp", "assert", "abort")):
        score = max(score, 60)
    if "example" in lowered:
        score = max(score, 50)
    return score


def _looks_file_magic_payload(value: str) -> bool:
    """Detect visible sample payloads that carry recognizable file signatures."""

    text = str(value or "")
    if not text:
        return False
    return text.startswith(
        (
            "MZ",
            "\x7fELF",
            "%PDF",
            "PK\x03\x04",
            "PK\x05\x06",
            "PK\x07\x08",
            "\x89PNG\r\n\x1a\n",
            "\xff\xd8\xff",
            "BAM\x01",
            "CRAM",
            "\xff\xf1",
            "\xff\xf9",
            "ADIF",
            "ID3",
            "RIFF",
            "OggS",
            "fLaC",
        )
    )


def _looks_structured_sample_payload(value: str) -> bool:
    """Score small public fixture inputs above generic prose or numeric guesses."""

    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if text.startswith(("<?xml", "<!doctype", "<html", "<svg")):
        return True
    if text.startswith(">") and "\n" in text:
        return True
    if lowered.startswith(("samtools", "@hd", "@sq")):
        return True
    if "\t" in text and text.count("\t") >= 3 and len(text) <= 2048:
        return True
    if lowered.startswith(("rule ", 'import "pe"', "import pe")):
        return True
    return False


def _looks_numeric_edge_literal(value: str) -> bool:
    text = value.strip()
    lowered = text.lower()
    if not text:
        return False
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?e[-+]?\d{3,}", lowered):
        return True
    if re.fullmatch(r"[-+]?0x[0-9a-f]{8,}", lowered):
        return True
    digits = sum(ch.isdigit() for ch in text)
    return digits >= 12 and all(ch in "+-0123456789.eExXaAbBcCdDeEfF" for ch in text)


def _wraps_numeric_edge_literal(value: str) -> bool:
    text = value.strip()
    if len(text) > 160:
        return False
    for match in re.findall(
        r"[-+]?\d+(?:\.\d+)?[eE][-+]?\d{3,}|[-+]?0x[0-9a-fA-F]{8,}", text
    ):
        if _looks_numeric_edge_literal(match):
            return True
    return False


def _looks_documentation_or_badge(value: str) -> bool:
    lowered = value.lower()
    documentation_tokens = (
        "fuzzing status",
        "oss-fuzz-build-logs",
        "badge",
        "license",
        "copyright",
        "readme",
        "documentation",
        "mailing list",
        "list archives",
        "markdown-link",
        "](",
        "https://github.com/",
    )
    return any(token in lowered for token in documentation_tokens)


def _include_candidate_score(lowered: str) -> int:
    common_code_headers = (
        "cassert",
        "assert.h",
        "cstddef",
        "cstdint",
        "cstdio",
        "cstdlib",
        "cstring",
        "stdint.h",
        "stdio.h",
        "stdlib.h",
        "string.h",
        "pthread.h",
        "vector",
        "string",
        "memory",
        "map",
        "set",
        "fuzzer/fuzzeddata",
        "libxml/",
    )
    if "magic" in lowered:
        return 125
    if any(header in lowered for header in common_code_headers):
        return 45
    return 95


def _compose_candidate_batches(
    primary_batches: list[list[str]],
    secondary_batches: list[list[str]],
    *,
    limit: int,
    strategy: str = "balanced",
    task_text: str = "",
) -> list[str]:
    """Blend portfolio and specialized helpers without letting either crowd out."""

    if not primary_batches:
        return _promote_candidates_for_strategy(
            _merge_candidate_batches(secondary_batches, limit=limit * 4),
            task_text,
            strategy,
        )[:limit]
    if not secondary_batches:
        return _promote_candidates_for_strategy(
            _merge_candidate_batches(primary_batches, limit=limit * 4),
            task_text,
            strategy,
        )[:limit]
    mode = _normalized_candidate_strategy(strategy)
    if mode == "context_aware":
        secondary_reserve = min(max(4, limit // 3), max(1, limit // 2))
    elif mode == "sample_first":
        secondary_reserve = min(max(3, limit // 4), max(1, limit // 3))
    elif mode == "literal_reserve":
        secondary_reserve = min(max(6, limit // 2), max(1, limit - 1))
    elif mode == "source_first":
        secondary_reserve = min(max(2, limit // 4), max(1, limit // 3))
    elif mode == "wide_diverse":
        secondary_reserve = min(max(5, limit // 3), max(1, limit // 2))
    else:
        secondary_reserve = min(max(4, limit // 3), max(1, limit // 2))
    primary_limit = max(1, limit - secondary_reserve)
    primary = _merge_candidate_batches(primary_batches, limit=primary_limit)
    secondary = _merge_candidate_batches(secondary_batches, limit=limit - len(primary))
    blended = _merge_candidate_batches([primary, secondary], limit=limit)
    if len(blended) < limit:
        full_primary = _merge_candidate_batches(primary_batches, limit=limit)
        blended = _append_missing_candidates(blended, full_primary, limit=limit)
    primary_anchor_limit = min(len(primary_batches), max(1, min(5, limit // 2)))
    primary_anchors = _first_candidate_from_each_batch(
        primary_batches,
        limit=primary_anchor_limit,
    )
    full_pool = _merge_candidate_batches(
        primary_batches + secondary_batches, limit=limit * 4
    )
    ranked_pool = _promote_candidates_for_strategy(
        _append_missing_candidates(blended, full_pool, limit=limit * 4),
        task_text,
        strategy,
    )
    anchored = _append_missing_candidates(
        primary_anchors,
        [
            candidate
            for candidate in ranked_pool
            if candidate not in set(primary_anchors)
        ],
        limit=limit,
    )
    return anchored[:limit]


def _compose_candidate_submission_plan(
    primary_batches: list[list[str]],
    secondary_batches: list[list[str]],
    *,
    limit: int,
    reserve: int = 0,
    strategy: str = "balanced",
    task_text: str = "",
) -> list[str]:
    """Return initial candidates plus a failure-only reserve without crowding out the initial plan."""

    initial = _compose_candidate_batches(
        primary_batches,
        secondary_batches,
        limit=limit,
        strategy=strategy,
        task_text=task_text,
    )
    if reserve <= 0:
        return initial
    reserve_limit = limit + max(0, int(reserve))
    broad_pool = _merge_candidate_batches(
        primary_batches + secondary_batches,
        limit=max(reserve_limit * 4, reserve_limit),
    )
    ranked_pool = _promote_candidates_for_strategy(
        broad_pool,
        task_text,
        strategy,
    )
    return _append_missing_candidates(initial, ranked_pool, limit=reserve_limit)


def _first_candidate_from_each_batch(
    candidate_batches: list[list[str]], *, limit: int
) -> list[str]:
    anchors: list[str] = []
    seen: set[str] = set()
    for batch in candidate_batches:
        for candidate in batch:
            if candidate in seen:
                continue
            seen.add(candidate)
            anchors.append(candidate)
            break
        if len(anchors) >= limit:
            break
    return anchors


def _append_missing_candidates(
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


def _visible_artifact_summary(task_dir: Path, context_text: str = "") -> str:
    """Summarize visible task artifacts without opening labels or reference PoCs."""

    archive = task_dir / "repo-vul.tar.gz"
    if not archive.exists():
        return ""
    context_terms = _artifact_context_terms(context_text)
    file_lines: list[str] = []
    option_lines: list[str] = []
    dict_lines: list[str] = []
    literal_lines: list[str] = []
    source_lines: list[str] = []
    sample_lines: list[str] = []
    sample_mutation_lines: list[str] = []
    seen_lines: set[str] = set()
    seen_files: set[str] = set()

    def append_file(name: str) -> None:
        if name not in seen_files:
            seen_files.add(name)
            file_lines.append(f"file: {name}")

    def append_signal(bucket: list[str], member_name: str, signal: str) -> None:
        if signal in seen_lines:
            return
        seen_lines.add(signal)
        append_file(member_name)
        bucket.append(signal)

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
                key=lambda member: _artifact_member_priority(member, context_terms),
            )[:120]
            for member in members:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                text = extracted.read(160_000).decode("utf-8", errors="ignore")
                if member.name.lower().endswith(".dict"):
                    member_dict_count = 0
                    for value in _dictionary_entries(text):
                        append_signal(dict_lines, member.name, f"dict: {value}")
                        member_dict_count += 1
                        if len(dict_lines) >= 80 or member_dict_count >= 18:
                            break
                for value in re.findall(r'"([^"\n\r]{1,96})"', text):
                    cleaned = value.strip()
                    if cleaned and _literal_has_signal(cleaned):
                        append_signal(literal_lines, member.name, f"literal: {cleaned}")
                        if len(literal_lines) >= 80:
                            break
                member_source_count = 0
                for raw_line in text.splitlines()[:900]:
                    stripped = raw_line.strip()
                    if not 8 <= len(stripped) <= 180:
                        continue
                    if _option_line_has_signal(stripped):
                        append_signal(
                            option_lines, member.name, f"source_line: {stripped}"
                        )
                        continue
                    if _source_line_has_signal(stripped):
                        append_signal(
                            source_lines, member.name, f"source_line: {stripped}"
                        )
                        member_source_count += 1
                        if len(source_lines) >= 140 or member_source_count >= 16:
                            break
                if (
                    _summary_candidate_chars(
                        file_lines,
                        option_lines,
                        dict_lines,
                        literal_lines,
                        source_lines,
                        sample_lines,
                    )
                    >= 18_000
                ):
                    break
            nested_archives = sorted(
                [
                    member
                    for member in tar.getmembers()
                    if member.isfile() and _looks_visible_seed_archive(member)
                ],
                key=lambda member: _artifact_sample_member_priority(
                    member, context_terms
                ),
            )[:8]
            for member in nested_archives:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                for sample in _nested_visible_seed_archive_samples(
                    extracted.read(min(member.size, 1_500_000)),
                    member.name,
                    context_terms=context_terms,
                ):
                    append_signal(sample_lines, member.name, sample)
                    payload = _candidate_payload_value(sample)
                    for mutation in _public_sample_mutation_lines(
                        payload.encode("latin1", errors="ignore")
                    ):
                        append_signal(sample_mutation_lines, member.name, mutation)
                    if len(sample_lines) >= 80:
                        break
                if len(sample_lines) >= 80:
                    break
            sample_members = sorted(
                [
                    member
                    for member in tar.getmembers()
                    if member.isfile() and _looks_visible_input_sample(member)
                ],
                key=lambda member: _artifact_sample_member_priority(
                    member, context_terms
                ),
            )[:80]
            for member in sample_members:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                sample_bytes = extracted.read(4096)
                sample = _sample_candidate_line(sample_bytes)
                if sample:
                    append_signal(sample_lines, member.name, sample)
                    for mutation in _public_sample_mutation_lines(sample_bytes):
                        append_signal(sample_mutation_lines, member.name, mutation)
                if len(sample_lines) >= 40:
                    break
    except (OSError, tarfile.TarError):
        return ""
    lines = (
        sample_lines[:80]
        + sample_mutation_lines[:120]
        + dict_lines[:80]
        + option_lines[:80]
        + literal_lines[:80]
        + source_lines[:140]
        + file_lines[:60]
    )
    return "\n".join(lines)[:18_000]


def _artifact_context_terms(context_text: str) -> frozenset[str]:
    """Return visible task terms used only to prioritize public artifacts.

    These terms come from the public task description/readme, not labels or
    reference PoCs. They help avoid wasting the candidate budget on unrelated
    build files when a repository contains many fuzzers or sample corpora.
    """

    text = str(context_text or "").lower()
    terms: set[str] = set()
    for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", text):
        if token in {
            "vulnerability",
            "provided",
            "submit",
            "single",
            "input",
            "program",
            "source",
            "files",
            "task",
            "instructions",
            "generate",
            "proof",
            "concept",
            "trigger",
        }:
            continue
        terms.add(token)
    for dotted in re.findall(r"[a-zA-Z0-9_./+-]{4,}", text):
        cleaned = dotted.strip("./").replace(".", "_").replace("-", "_")
        if len(cleaned) >= 4:
            terms.add(cleaned)
    return frozenset(list(terms)[:80])


def _public_runtime_entrypoint_summary(task_id: str) -> str:
    """Summarize public container entrypoint and fuzz binaries if image exists.

    This uses only locally available public vulnerable images and does not run
    candidates, inspect fixed-side behavior, or read reference PoCs. Missing
    images are treated as no summary so normal cached/downloaded runs remain
    portable.
    """

    try:
        image, command = _cybergym_image_and_command(task_id, "vul")
    except ValueError:
        return ""
    if not _docker_image_exists(image):
        return ""
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                image,
                "/bin/bash",
                "-lc",
                "printf 'runtime_command: '; printf '%q ' "
                + shlex.quote(" ".join(command))
                + "; printf '\\n'; "
                "printf 'runtime_entrypoint: '; sed -n '1,120p' /bin/arvo 2>/dev/null | tr '\\n' ' ' | cut -c1-900; printf '\\n'; "
                "find /out -maxdepth 1 -type f -perm -111 -printf 'runtime_binary: %f\\n' 2>/dev/null | head -40",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=12,
        )
    except Exception:
        return ""
    if completed.returncode not in (0, 1):
        return ""
    lines = []
    for raw_line in (completed.stdout or "").splitlines():
        line = raw_line.strip()
        if line and len(line) <= 1000:
            lines.append(line)
    return "\n".join(lines[:48])


def _summary_candidate_chars(*buckets: list[str]) -> int:
    return sum(len(line) + 1 for bucket in buckets for line in bucket)


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


def _looks_visible_input_sample(member: tarfile.TarInfo) -> bool:
    """Return true for small visible fixtures that can fairly seed candidates."""

    if not 1 <= member.size <= 4096:
        return False
    lowered = member.name.lower()
    if any(
        blocked in lowered
        for blocked in (
            "reference",
            "solution",
            "answer",
            "label",
            "secret",
            "hidden",
            "/poc",
            "poc-",
            "/crash",
            "crash-",
        )
    ):
        return False
    if not any(
        token in lowered
        for token in (
            "/test/",
            "/tests/",
            "/data/",
            "/sample",
            "/samples/",
            "/example",
            "/examples/",
            "corpus",
            "seed",
            "fixture",
        )
    ):
        return False
    suffix = Path(lowered).suffix
    source_suffixes = {
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
        ".md",
        ".rst",
        ".html",
        ".cmake",
        ".bp",
        ".mk",
        ".yml",
        ".yaml",
        ".toml",
        ".gradle",
        ".sh",
        ".am",
        ".in",
    }
    archive_suffixes = {".gz", ".zip", ".xz", ".bz2", ".tar", ".o", ".a", ".so"}
    if suffix in source_suffixes or suffix in archive_suffixes:
        return False
    return True


def _public_sample_mutation_lines(data: bytes) -> list[str]:
    """Return bounded mutations of public visible sample bytes.

    The mutations are generated from public task artifacts only. They are not
    based on labels, reference PoCs, hidden answers, or fixed-side behavior.
    """

    if not data:
        return []
    sample = data[:1024]
    variants: list[bytes] = []
    for extra in (
        b"\x00",
        b"\xff",
        b"A",
        b"\x7f",
        b"\x00\x00\x00\x00",
        b"\xff\xff\xff\xff",
    ):
        variants.append(sample + extra)
        variants.append(extra + sample)
    for size in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        if size < len(sample):
            variants.append(sample[:size])
    positions = []
    for pos in (
        0,
        1,
        2,
        3,
        len(sample) // 4,
        len(sample) // 2,
        len(sample) - 4,
        len(sample) - 2,
        len(sample) - 1,
    ):
        if 0 <= pos < len(sample) and pos not in positions:
            positions.append(pos)
    for pos in positions[:10]:
        for replacement in (b"\x00", b"\xff", b"A", b"\x7f"):
            variants.append(sample[:pos] + replacement + sample[pos + 1 :])
        variants.append(sample[:pos] + sample[pos + 1 :])
        variants.append(sample[:pos] + b"\x00" + sample[pos:])
    if sample.startswith(
        (b"\xff\xf1", b"\xff\xf9", b"ADIF", b"ID3", b"RIFF", b"OggS", b"fLaC")
    ):
        for fill in (b"\x00", b"\xff", b"A", b"\x7f"):
            for target_len in (16, 32, 64, 128, 256, 512):
                if len(sample) < target_len:
                    variants.append(sample + fill * (target_len - len(sample)))
    lines: list[str] = []
    seen: set[bytes] = set()
    for variant in variants:
        if not variant or len(variant) > 1024 or variant in seen:
            continue
        seen.add(variant)
        lines.append(f"corpus_sample: {_escape_visible_bytes(variant)[:1024]}")
        if len(lines) >= 24:
            break
    return lines


def _looks_visible_seed_archive(member: tarfile.TarInfo) -> bool:
    if not 1 <= member.size <= 1_500_000:
        return False
    lowered = member.name.lower()
    if Path(lowered).suffix != ".zip":
        return False
    if any(
        blocked in lowered
        for blocked in (
            "reference",
            "solution",
            "answer",
            "label",
            "secret",
            "hidden",
            "/poc",
            "poc-",
            "/crash",
            "crash-",
        )
    ):
        return False
    return any(token in lowered for token in ("corpus", "seed", "sample", "fixture"))


def _nested_visible_seed_archive_samples(
    data: bytes,
    archive_name: str,
    *,
    context_terms: frozenset[str] = frozenset(),
) -> list[str]:
    """Extract small public seed files from a visible nested archive."""

    if not data or not zipfile.is_zipfile(BytesIO(data)):
        return []
    samples: list[str] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = sorted(
                [
                    info
                    for info in archive.infolist()
                    if not info.is_dir() and _looks_visible_nested_seed_member(info)
                ],
                key=lambda info: _nested_seed_member_priority(info, context_terms),
            )[:60]
            for info in infos:
                with archive.open(info) as handle:
                    sample = _sample_candidate_line(handle.read(8192))
                if sample:
                    samples.append(sample)
                if len(samples) >= 40:
                    break
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return []
    del archive_name
    return samples


def _looks_visible_nested_seed_member(info: zipfile.ZipInfo) -> bool:
    if not 1 <= info.file_size <= 120_000:
        return False
    lowered = info.filename.lower()
    if any(
        blocked in lowered
        for blocked in (
            "reference",
            "solution",
            "answer",
            "label",
            "secret",
            "hidden",
            "/poc",
            "poc-",
            "/crash",
            "crash-",
        )
    ):
        return False
    suffix = Path(lowered).suffix
    if suffix in {".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".md", ".rst", ".sh"}:
        return False
    return True


def _nested_seed_member_priority(
    info: zipfile.ZipInfo, context_terms: frozenset[str]
) -> tuple[int, int, int, str]:
    lowered = info.filename.lower()
    suffix = Path(lowered).suffix
    media_or_binary = suffix in {
        ".aac",
        ".adts",
        ".m4a",
        ".mp4",
        ".wav",
        ".bin",
        ".dat",
        ".raw",
        ".xml",
        ".json",
        ".sam",
        ".fa",
        ".fasta",
    }
    context_hit = _name_context_hit(lowered, context_terms)
    return (
        0 if context_hit else 1,
        0 if media_or_binary else 1,
        info.file_size,
        lowered,
    )


def _artifact_sample_member_priority(
    member: tarfile.TarInfo, context_terms: frozenset[str] = frozenset()
) -> tuple[int, int, int, str]:
    lowered = member.name.lower()
    basename = Path(lowered).name
    suffix = Path(lowered).suffix
    preferred_suffix = suffix in {
        ".xml",
        ".json",
        ".csv",
        ".sam",
        ".fa",
        ".fasta",
        ".yar",
        ".rules",
        ".txt",
    }
    corpus = "corpus" in lowered or "seed" in lowered
    no_suffix = "." not in basename
    context_hit = _name_context_hit(lowered, context_terms)
    return (
        0 if context_hit else 1,
        0 if corpus else 1 if preferred_suffix else 2 if no_suffix else 3,
        member.size,
        lowered,
    )


def _sample_candidate_line(data: bytes) -> str:
    if not data:
        return ""
    sample = data[:4096]
    printable = sum(1 for byte in sample if byte in (9, 10, 13) or 32 <= byte <= 126)
    if printable / max(1, len(sample)) >= 0.86:
        text = sample.decode("utf-8", errors="ignore").strip()
        text = " ".join(part.strip() for part in text.splitlines() if part.strip())
        lowered = text.lower()
        if any(
            token in lowered
            for token in (
                "spdx-license",
                "copyright",
                "default_applicable_licenses",
                "package {",
                "cmake_minimum_required",
                "github.com/",
                "build_fuzzers",
            )
        ):
            return ""
        if text:
            return f"sample_text: {text[:520]}"
    return f"sample_escape: {_escape_visible_bytes(sample)[:4096]}"


def _escape_visible_bytes(data: bytes) -> str:
    parts: list[str] = []
    for byte in data:
        if byte == 9:
            parts.append("\\t")
        elif byte == 10:
            parts.append("\\n")
        elif byte == 13:
            parts.append("\\r")
        elif byte == 92:
            parts.append("\\\\")
        elif 32 <= byte <= 126:
            parts.append(chr(byte))
        else:
            parts.append(f"\\x{byte:02x}")
    return "".join(parts)


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


def _artifact_member_priority(
    member: tarfile.TarInfo, context_terms: frozenset[str] = frozenset()
) -> tuple[int, int, int, int, str]:
    lowered = member.name.lower()
    basename = Path(lowered).name
    dictionary_or_options = basename.endswith((".dict", ".options"))
    config_or_help = basename in {
        "readme",
        "readme.md",
        "configure",
        "configure.ac",
        "cmakelists.txt",
        "makefile",
        "makefile.am",
        "build.sh",
        "oss-fuzz-build.sh",
    }
    fuzz_driver = "fuzz" in basename
    generated_patch = lowered.endswith((".diff", ".patch"))
    context_hit = _name_context_hit(lowered, context_terms)
    return (
        0
        if fuzz_driver
        else 1
        if dictionary_or_options
        else 2
        if context_hit
        else 3
        if config_or_help
        else 4,
        1 if generated_patch else 0,
        lowered.count("/"),
        lowered,
    )


def _name_context_hit(name: str, context_terms: frozenset[str]) -> bool:
    if not context_terms:
        return False
    normalized = str(name or "").lower().replace("-", "_").replace(".", "_")
    for term in context_terms:
        if len(term) >= 4 and term in normalized:
            return True
    return False


def _option_line_has_signal(line: str) -> bool:
    lowered = line.lower()
    option_tokens = (
        "--with-",
        "--without-",
        "--enable-",
        "--disable-",
        "--help",
        "-d",
        "-f",
    )
    if any(token in lowered for token in option_tokens):
        return any(ch in line for ch in "-/[]()=:_")
    if lowered.startswith(("usage:", "options:", "flags:")):
        return True
    return False


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
        "sizeof",
        "length",
        "len1",
        "len2",
        "chunk",
        "flags",
        "token",
        "format",
        "fuzzeddata",
        "xmlfuzz",
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


def _local_vulnerable_prescreen_candidate(
    task_id: str,
    task_dir: Path,
    index: int,
    candidate: str,
    *,
    timeout_seconds: float,
    cmd_timeout_seconds: int,
) -> dict[str, Any]:
    """Run a candidate on the public vulnerable target before official submit.

    This is candidate-budget triage only. It never runs the fixed target, reads
    reference PoCs, or marks a task solved. Official scoring still requires the
    normal submit.sh path.
    """

    try:
        image, command = _cybergym_image_and_command(task_id, "vul")
    except ValueError as exc:
        return {
            "ok": False,
            "candidate_index": index,
            "prescreen_mode": "vulnerable-local",
            "error": str(exc),
        }
    poc_path = task_dir / f"sage_prescreen_{index}.poc"
    poc_path.write_bytes(candidate.encode("latin1", errors="ignore"))
    command_text = (
        f"timeout -s SIGKILL {int(cmd_timeout_seconds)} {shlex.join(command)} 2>&1"
    )
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                f"{poc_path.resolve()}:/tmp/poc:ro",
                image,
                "/bin/bash",
                "-c",
                command_text,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - Docker/environment failure
        return {
            "ok": False,
            "candidate_index": index,
            "prescreen_mode": "vulnerable-local",
            "error": f"local_prescreen_failed:{type(exc).__name__}:{exc}",
        }
    output = (completed.stdout or "") + (completed.stderr or "")
    infra_error = (
        completed.returncode in {125, 126, 127} and "docker:" in output.lower()
    )
    if infra_error:
        return {
            "ok": False,
            "candidate_index": index,
            "prescreen_mode": "vulnerable-local",
            "returncode": completed.returncode,
            "error": output[-800:],
        }
    exit_code = 300 if completed.returncode == 137 else completed.returncode
    return {
        "ok": True,
        "candidate_index": index,
        "prescreen_mode": "vulnerable-local",
        "prescreen_exit_code": exit_code,
        "prescreen_crashed": exit_code not in (0, 300),
        "prescreen_output_excerpt": output[:600],
    }


def _local_vulnerable_batch_prescreen_candidates(
    task_id: str,
    task_dir: Path,
    candidates: Sequence[str],
    *,
    timeout_seconds: float,
    cmd_timeout_seconds: int,
) -> dict[int, dict[str, Any]]:
    """Run many candidates inside one public vulnerable container.

    This is a candidate-quality and budget-allocation probe. It mounts only the
    generated candidate files, overwrites /tmp/poc before every run, and never
    executes the fixed image or reads reference PoCs, labels, or benchmark
    answers.
    """

    if not candidates:
        return {}
    try:
        image, command = _cybergym_image_and_command(task_id, "vul")
    except ValueError as exc:
        return {
            index: {
                "ok": False,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-batch",
                "error": str(exc),
            }
            for index, _ in enumerate(candidates)
        }

    input_dir = task_dir / "sage_prescreen_batch_inputs"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    for index, candidate in enumerate(candidates):
        (input_dir / f"candidate_{index:06d}.poc").write_bytes(
            candidate.encode("latin1", errors="ignore")
        )

    command_text = shlex.join(command)
    loop_script = f"""
set +e
for f in /inputs/candidate_*.poc; do
  [ -e "$f" ] || continue
  base="${{f##*/}}"
  idx="${{base#candidate_}}"
  idx="${{idx%.poc}}"
  idx="$((10#$idx))"
  rm -f /tmp/poc
  cp "$f" /tmp/poc
  out="$(timeout -s SIGKILL {int(cmd_timeout_seconds)} {command_text} 2>&1)"
  rc=$?
  if [ "$rc" -eq 137 ]; then rc=300; fi
  printf 'SAGE_PRESCREEN_BEGIN index=%s rc=%s\\n' "$idx" "$rc"
  printf '%s\\n' "$out" | head -c 700
  printf '\\nSAGE_PRESCREEN_END index=%s\\n' "$idx"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 300 ]; then
    break
  fi
done
"""
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                f"{input_dir.resolve()}:/inputs:ro",
                image,
                "/bin/bash",
                "-lc",
                loop_script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - Docker/environment failure
        return {
            index: {
                "ok": False,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-batch",
                "error": f"local_batch_prescreen_failed:{type(exc).__name__}:{exc}",
            }
            for index, _ in enumerate(candidates)
        }

    output = (completed.stdout or "") + (completed.stderr or "")
    infra_error = (
        completed.returncode in {125, 126, 127} and "docker:" in output.lower()
    )
    if infra_error:
        return {
            index: {
                "ok": False,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-batch",
                "returncode": completed.returncode,
                "error": output[-800:],
            }
            for index, _ in enumerate(candidates)
        }

    results: dict[int, dict[str, Any]] = {}
    pattern = re.compile(
        r"SAGE_PRESCREEN_BEGIN index=(?P<index>\d+) rc=(?P<rc>-?\d+)\n"
        r"(?P<body>.*?)\nSAGE_PRESCREEN_END index=(?P=index)",
        re.DOTALL,
    )
    for match in pattern.finditer(output):
        index = int(match.group("index"))
        exit_code = int(match.group("rc"))
        body = match.group("body")
        results[index] = {
            "ok": True,
            "candidate_index": index,
            "prescreen_mode": "vulnerable-batch",
            "prescreen_exit_code": exit_code,
            "prescreen_crashed": exit_code not in (0, 300),
            "prescreen_output_excerpt": body[:600],
        }
    for index, _ in enumerate(candidates):
        if index not in results:
            results[index] = {
                "ok": True,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-batch",
                "prescreen_exit_code": None,
                "prescreen_crashed": False,
                "prescreen_output_excerpt": "",
                "official_skipped_reason": "not_reached_after_prior_batch_crash"
                if any(item.get("prescreen_crashed") for item in results.values())
                else "batch_prescreen_no_result",
            }
    return results


def _public_search_requested(
    candidates: Sequence[str],
    tool_uses: tuple[ToolUseRecord, ...],
) -> bool:
    if any(
        "public_local_search" in use.tool_name.lower()
        or "public_local_fuzz" in use.tool_name.lower()
        or "public_local_fuzz" in str(use.result).lower()
        for use in tool_uses
    ):
        return True
    return any(
        str(candidate).strip().lower().startswith("search_strategy: public_local")
        for candidate in candidates
    )


def _public_search_source_name(tool_uses: tuple[ToolUseRecord, ...]) -> str:
    for use in tool_uses:
        lowered = use.tool_name.lower()
        if "public_local_search" in lowered or "public_local_fuzz" in lowered:
            return use.tool_name
    return "public_local_search"


def _is_public_search_control_candidate(candidate: str) -> bool:
    lowered = str(candidate or "").strip().lower()
    return lowered.startswith(
        (
            "search_strategy:",
            "search_budget:",
            "search_target_hint:",
        )
    )


def _local_vulnerable_public_search_candidates(
    task_id: str,
    task_dir: Path,
    *,
    seed_candidates: Sequence[str],
    timeout_seconds: float,
    search_seconds: int,
    max_artifacts: int,
) -> list[dict[str, Any]]:
    """Use public vulnerable-side execution to improve candidate quality.

    This is a bounded search over public task artifacts and generated candidate
    seeds. It removes any container-default /tmp/poc before execution, mounts
    only SAGE-created/public-visible seed files, never reads reference PoCs or
    labels, and never runs the fixed image. Fixed-side validation remains the
    responsibility of the official submit path.
    """

    try:
        image, _command = _cybergym_image_and_command(task_id, "vul")
    except ValueError:
        return []
    if not _docker_image_exists(image):
        return []

    work_dir = task_dir / "sage_public_local_search"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    seeds_dir = work_dir / "seeds"
    out_dir = work_dir / "out"
    seeds_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_count = _write_public_search_seed_candidates(seeds_dir, seed_candidates)
    seed_count += _write_public_seed_corpus(task_dir, seeds_dir, start_index=seed_count)
    seed_count += _write_public_format_probe_seeds(
        task_dir, seeds_dir, seed_candidates, start_index=seed_count
    )
    if seed_count == 0:
        for index, fallback in enumerate((b"\x00\x01\x02\x03", b"AAAA")):
            (seeds_dir / f"fallback_seed_{index:04d}").write_bytes(fallback)
        seed_count = 2

    target_hints = _public_search_target_hints(seed_candidates)
    targets = _public_vulnerable_fuzz_targets(image, target_hints)
    discoveries: list[dict[str, Any]] = []
    for target, engine in targets:
        if len(discoveries) >= max_artifacts:
            break
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        target_path = f"/out/{target}"
        command = _public_search_command(
            target_path,
            engine=engine,
            search_seconds=max(2, int(search_seconds)),
            max_artifacts=max_artifacts,
        )
        try:
            completed = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "-v",
                    f"{work_dir.resolve()}:/work",
                    image,
                    "/bin/bash",
                    "-lc",
                    command,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(float(timeout_seconds), float(search_seconds) + 20.0),
            )
        except Exception:
            continue
        output = ((completed.stdout or "") + (completed.stderr or ""))[-1200:]
        fuzz_log = out_dir / "fuzz.log"
        if fuzz_log.exists():
            output = (output + "\n" + fuzz_log.read_text(errors="ignore"))[-1200:]
        for artifact in sorted(out_dir.rglob("*")):
            if not artifact.is_file():
                continue
            if not _looks_public_search_artifact(artifact, out_dir):
                continue
            try:
                data = artifact.read_bytes()
            except OSError:
                continue
            if not 1 <= len(data) <= 250_000:
                continue
            discoveries.append(
                {
                    "candidate": data.decode("latin1", errors="ignore"),
                    "target": target,
                    "engine": engine,
                    "size": len(data),
                    "seed_count": seed_count,
                    "vulnerable_exit_code": completed.returncode,
                    "log_excerpt": output,
                }
            )
            if len(discoveries) >= max_artifacts:
                break
    return discoveries


def _looks_public_search_artifact(path: Path, out_dir: Path) -> bool:
    name = path.name.lower()
    if name in {"readme.txt", "plot_data", "fuzz.log"}:
        return False
    if name.startswith(("crash-", "oom-", "timeout-")):
        return True
    try:
        rel = str(path.relative_to(out_dir)).lower()
    except ValueError:
        rel = str(path).lower()
    if "/crashes/" in f"/{rel}" and not name.startswith("."):
        return True
    return False


def _write_public_search_seed_candidates(
    seeds_dir: Path, seed_candidates: Sequence[str]
) -> int:
    count = 0
    seen: set[bytes] = set()
    for candidate in seed_candidates:
        data = _public_search_seed_bytes(candidate)
        if not data or data in seen:
            continue
        seen.add(data)
        (seeds_dir / f"candidate_seed_{count:04d}").write_bytes(data)
        count += 1
        if count >= 80:
            break
    return count


def _write_public_seed_corpus(
    task_dir: Path, seeds_dir: Path, *, start_index: int = 0, max_files: int = 80
) -> int:
    archive_path = task_dir / "repo-vul.tar.gz"
    if not archive_path.exists():
        return 0
    try:
        context_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in (task_dir / "description.txt", task_dir / "README.md")
            if path.exists()
        )
    except OSError:
        context_text = ""
    context_terms = _artifact_context_terms(context_text)
    written = 0
    seen: set[bytes] = set()
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            nested_archives = sorted(
                [
                    member
                    for member in tar.getmembers()
                    if member.isfile() and _looks_visible_seed_archive(member)
                ],
                key=lambda member: _artifact_sample_member_priority(
                    member, context_terms
                ),
            )[:12]
            for member in nested_archives:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                data = extracted.read(min(member.size, 2_000_000))
                if not zipfile.is_zipfile(BytesIO(data)):
                    continue
                with zipfile.ZipFile(BytesIO(data)) as archive:
                    infos = sorted(
                        [
                            info
                            for info in archive.infolist()
                            if not info.is_dir()
                            and _looks_visible_nested_seed_member(info)
                        ],
                        key=lambda info: _nested_seed_member_priority(
                            info, context_terms
                        ),
                    )[:max_files]
                    for info in infos:
                        seed = archive.read(info)
                        if not 1 <= len(seed) <= 120_000:
                            continue
                        if seed in seen:
                            continue
                        seen.add(seed)
                        (
                            seeds_dir / f"public_seed_{start_index + written:04d}"
                        ).write_bytes(seed)
                        written += 1
                        if written >= max_files:
                            return written
            direct_members = sorted(
                [
                    member
                    for member in tar.getmembers()
                    if member.isfile() and _looks_public_search_seed_member(member)
                ],
                key=lambda member: _artifact_sample_member_priority(
                    member, context_terms
                ),
            )[: max_files * 2]
            for member in direct_members:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                seed = extracted.read(min(member.size, 120_000))
                if not 1 <= len(seed) <= 120_000:
                    continue
                if seed in seen:
                    continue
                seen.add(seed)
                (seeds_dir / f"public_seed_{start_index + written:04d}").write_bytes(
                    seed
                )
                written += 1
                if written >= max_files:
                    return written
    except (OSError, tarfile.TarError, zipfile.BadZipFile, RuntimeError):
        return written
    return written


def _looks_public_search_seed_member(member: tarfile.TarInfo) -> bool:
    """Return true for visible repository files that can seed active search.

    This is intentionally broader than dashboard/sample extraction: executable
    benchmarks often include useful fixtures directly under tests, examples,
    data, or corpus directories instead of nested seed archives. The guardrails
    still exclude source code, build files, reference PoCs, labels, and crash
    artifacts.
    """

    if not 1 <= member.size <= 120_000:
        return False
    lowered = member.name.lower()
    if any(
        blocked in lowered
        for blocked in (
            "reference",
            "solution",
            "answer",
            "label",
            "secret",
            "hidden",
            "/poc",
            "poc-",
            "/crash",
            "crash-",
        )
    ):
        return False
    suffix = Path(lowered).suffix
    source_or_build_suffixes = {
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
        ".md",
        ".rst",
        ".cmake",
        ".bp",
        ".mk",
        ".yml",
        ".yaml",
        ".toml",
        ".gradle",
        ".sh",
        ".am",
        ".in",
        ".m4",
        ".pdf",
        ".doc",
        ".docx",
    }
    archive_or_binary_suffixes = {
        ".gz",
        ".zip",
        ".xz",
        ".bz2",
        ".tar",
        ".o",
        ".a",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
    }
    if suffix in source_or_build_suffixes or suffix in archive_or_binary_suffixes:
        return False
    path_cue = any(
        token in lowered
        for token in (
            "/test/",
            "/tests/",
            "/data/",
            "/sample",
            "/samples/",
            "/example",
            "/examples/",
            "corpus",
            "seed",
            "fixture",
        )
    )
    input_suffix = suffix in {
        ".xml",
        ".dtd",
        ".xsd",
        ".rng",
        ".html",
        ".json",
        ".csv",
        ".txt",
        ".aac",
        ".adts",
        ".m4a",
        ".mp4",
        ".wav",
        ".ogg",
        ".flac",
        ".bin",
        ".dat",
        ".raw",
        ".sam",
        ".fa",
        ".fasta",
    }
    return path_cue or input_suffix


def _write_public_format_probe_seeds(
    task_dir: Path,
    seeds_dir: Path,
    seed_candidates: Sequence[str],
    *,
    start_index: int = 0,
) -> int:
    """Write generic format probes when visible artifacts imply an input grammar.

    The probes are intentionally broad and public: they are common file-format
    edge cases selected from visible task descriptions, runtime target names,
    and generated candidate hints. They do not use reference PoCs, fixed-side
    behavior, labels, or scenario IDs.
    """

    text_parts: list[str] = []
    for path in (task_dir / "description.txt", task_dir / "README.md"):
        if path.exists():
            try:
                text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    text_parts.extend(str(candidate) for candidate in seed_candidates[:40])
    visible = "\n".join(text_parts).lower()
    probes: list[bytes] = []
    if any(
        cue in visible
        for cue in (
            "xml",
            "libxml",
            "doctype",
            "dtd",
            "entity",
            "namespace",
            "sax",
            "reader",
            "conditional section",
        )
    ):
        probes.extend(
            [
                b'<?xml version="1.0"?><root/>',
                b'<!DOCTYPE root [<!ENTITY e "x">]><root>&e;</root>',
                b'<!DOCTYPE root [<!ELEMENT root ANY><!ATTLIST root id ID #IMPLIED>]><root id="a"><child/></root>',
                b'<root xmlns:a="urn:a"><a:child attr="value"/></root>',
                b"<!DOCTYPE root [<!ENTITY e \"<a:x xmlns:a='urn:a'/>\">]><root>&e;</root>",
                b"<!DOCTYPE root [<!ENTITY % p \"<!ENTITY e 'v'>\">%p;]><root>&e;</root>",
                b'<!DOCTYPE root [<![INCLUDE[<!ENTITY e "x">]]>]><root>&e;</root>',
                b'<?xml version="1.0"?><!DOCTYPE root SYSTEM "missing.dtd"><root/>',
                b'<root><a/><a id="dup"/><b id="dup"/></root>',
                b"<root>" + b'<n a="1">' * 16 + b"x" + b"</n>" * 16 + b"</root>",
            ]
        )
    if any(
        cue in visible
        for cue in (
            "aac",
            "faad",
            "xaac",
            "audio",
            "decode",
            "adts",
            "id3",
        )
    ):
        probes.extend(
            [
                b"\xff\xf1\x50\x80\x00\x1f\xfc" + b"\x00" * 32,
                b"\xff\xf9\x50\x80\x00\x1f\xfc" + b"\xff" * 64,
                b"ADIF" + b"\x00" * 64,
                b"ID3\x04\x00\x00\x00\x00\x00\x10" + b"\x00" * 32,
                b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A isom" + b"\x00" * 32,
            ]
        )
    written = 0
    seen: set[bytes] = set()
    for probe in probes:
        if not 1 <= len(probe) <= 120_000 or probe in seen:
            continue
        seen.add(probe)
        (seeds_dir / f"format_probe_seed_{start_index + written:04d}").write_bytes(
            probe
        )
        written += 1
    return written


def _public_search_seed_bytes(candidate: str) -> bytes:
    if _is_public_search_control_candidate(candidate):
        return b""
    value = _candidate_payload_value(candidate) or str(candidate or "")
    data = value.encode("latin1", errors="ignore")
    if not 1 <= len(data) <= 120_000:
        return b""
    return data


def _public_search_target_hints(candidates: Sequence[str]) -> tuple[str, ...]:
    hints: list[str] = []
    for candidate in candidates:
        text = str(candidate or "").strip()
        lowered = text.lower()
        if not lowered.startswith("search_target_hint:"):
            continue
        hint = text.split(":", 1)[1].strip()
        if re.fullmatch(r"[A-Za-z0-9_.+-]{1,120}", hint):
            hints.append(hint.lower())
    return tuple(hints[:8])


def _public_vulnerable_fuzz_targets(
    image: str, target_hints: tuple[str, ...]
) -> list[tuple[str, str]]:
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                image,
                "/bin/bash",
                "-lc",
                "printf 'SAGE_ENGINE='; "
                "grep -E '^export FUZZING_ENGINE=' /bin/arvo 2>/dev/null | "
                "head -1 | sed -E 's/.*FUZZING_ENGINE=([^ ]+).*/\\1/'; "
                "printf 'SAGE_RUN_TARGETS\\n'; "
                "grep -Eo '/out/[A-Za-z0-9_.+-]+[[:space:]]+/tmp/poc' /bin/arvo 2>/dev/null | "
                "sed -E 's#/out/([^[:space:]]+).*#\\1#'; "
                "printf 'SAGE_BINARIES\\n'; "
                "find /out -maxdepth 1 -type f -perm -111 -printf '%f\\n' 2>/dev/null",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return []
    output = completed.stdout or ""
    engine_match = re.search(r"SAGE_ENGINE=([A-Za-z0-9_+-]+)", output)
    engine = engine_match.group(1).strip().lower() if engine_match else "libfuzzer"
    run_targets = [
        line.strip()
        for line in _section_lines(output, "SAGE_RUN_TARGETS", "SAGE_BINARIES")
        if re.fullmatch(r"[A-Za-z0-9_.+-]{1,160}", line.strip())
    ]
    binaries = [
        line.strip()
        for line in _section_lines(output, "SAGE_BINARIES", "")
        if re.fullmatch(r"[A-Za-z0-9_.+-]{1,160}", line.strip())
    ]
    fuzzer_targets = [
        binary
        for binary in binaries
        if "fuzz" in binary.lower() and binary.lower() != "honggfuzz"
    ]
    if run_targets:
        # The submitted PoC is scored through the public wrapper's run target.
        # Searching unrelated fuzz binaries can find crashes that submit.sh will
        # not exercise, so use other executable fuzz targets only when the
        # wrapper target cannot be identified.
        targets = _append_missing_strings(run_targets, (), limit=4)
    else:
        if not fuzzer_targets:
            fuzzer_targets = [
                binary for binary in binaries if binary.lower() != "honggfuzz"
            ]
        targets = _append_missing_strings((), fuzzer_targets, limit=6)

    def priority(target: str) -> tuple[int, int, str]:
        lowered = target.lower()
        hint_hit = any(hint in lowered or lowered in hint for hint in target_hints)
        wrapper_hit = target in run_targets
        return (
            0 if wrapper_hit else 1,
            0 if hint_hit else 1,
            0 if "fuzzer" in lowered or "fuzz" in lowered else 1,
            lowered,
        )

    return [(target, engine) for target in sorted(targets, key=priority)[:6]]


def _public_search_command(
    target_path: str, *, engine: str, search_seconds: int, max_artifacts: int
) -> str:
    quoted_target = shlex.quote(target_path)
    seconds = max(2, int(search_seconds))
    wrapper_seconds = seconds + 8
    max_count = max(1, int(max_artifacts))
    honggfuzz_iterations = max(1000, seconds * 1000)
    if engine.lower() == "honggfuzz":
        return f"""
set +e
rm -f /tmp/poc
mkdir -p /work/out
eval "$(grep '^export ' /bin/arvo 2>/dev/null)"
if [ ! -x {quoted_target} ] || [ ! -x /out/honggfuzz ]; then
  exit 0
fi
timeout -s SIGKILL {wrapper_seconds} /out/honggfuzz -P -i /work/seeds -o /work/out -n {honggfuzz_iterations} -t 2 -- {quoted_target} ___FILE___ > /work/out/fuzz.log 2>&1
rc=$?
if [ "$rc" -eq 137 ]; then rc=300; fi
printf 'SAGE_PUBLIC_SEARCH_RC=%s\\n' "$rc"
find /work/out -maxdepth 1 -type f \\( -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' \\) | head -{max_count}
"""
    if engine.lower() == "afl":
        return f"""
set +e
rm -f /tmp/poc
mkdir -p /work/out
eval "$(grep '^export ' /bin/arvo 2>/dev/null)"
export ASAN_OPTIONS="${{ASAN_OPTIONS:-}}:abort_on_error=1:symbolize=0"
export MSAN_OPTIONS="${{MSAN_OPTIONS:-}}:exit_code=86:symbolize=0"
export UBSAN_OPTIONS="${{UBSAN_OPTIONS:-}}:abort_on_error=1:symbolize=0"
if [ ! -x {quoted_target} ] || [ ! -x /out/afl-fuzz ]; then
  exit 0
fi
AFL_SKIP_CPUFREQ=1 AFL_NO_UI=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 timeout -s SIGKILL {wrapper_seconds} /out/afl-fuzz -d -m none -t 2000 -i /work/seeds -o /work/out -- {quoted_target} @@ > /work/out/fuzz.log 2>&1
rc=$?
if [ "$rc" -eq 137 ]; then rc=300; fi
printf 'SAGE_PUBLIC_SEARCH_RC=%s\\n' "$rc"
find /work/out -type f \\( -path '*/crashes/*' -o -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' \\) | head -{max_count}
"""
    return f"""
set +e
rm -f /tmp/poc
mkdir -p /work/out
eval "$(grep '^export ' /bin/arvo 2>/dev/null)"
if [ ! -x {quoted_target} ]; then
  exit 0
fi
timeout -s SIGKILL {wrapper_seconds} {quoted_target} -artifact_prefix=/work/out/crash- -max_total_time={seconds} -timeout=2 /work/seeds > /work/out/fuzz.log 2>&1
rc=$?
if [ "$rc" -eq 137 ]; then rc=300; fi
if ! find /work/out -maxdepth 1 -type f \\( -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' \\) | grep -q .; then
  if [ -x /out/honggfuzz ]; then
    rm -f /tmp/poc
    timeout -s SIGKILL {wrapper_seconds} /out/honggfuzz -P -i /work/seeds -o /work/out -n {honggfuzz_iterations} -t 2 -- {quoted_target} ___FILE___ >> /work/out/fuzz.log 2>&1
    rc=$?
    if [ "$rc" -eq 137 ]; then rc=300; fi
  fi
fi
printf 'SAGE_PUBLIC_SEARCH_RC=%s\\n' "$rc"
find /work/out -type f \\( -path '*/crashes/*' -o -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' \\) | head -{max_count}
"""


def _section_lines(text: str, start: str, end: str) -> list[str]:
    lines = str(text or "").splitlines()
    try:
        start_index = lines.index(start) + 1
    except ValueError:
        return []
    if end:
        try:
            end_index = lines.index(end, start_index)
        except ValueError:
            end_index = len(lines)
    else:
        end_index = len(lines)
    return lines[start_index:end_index]


def _append_missing_strings(
    primary: Sequence[str], secondary: Sequence[str], *, limit: int
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in list(primary) + list(secondary):
        if not item or item in seen:
            continue
        seen.add(item)
        values.append(item)
        if len(values) >= limit:
            break
    return values


def _cybergym_image_and_command(task_id: str, mode: str) -> tuple[str, list[str]]:
    if task_id.startswith("arvo:"):
        arvo_id = task_id.split(":", 1)[1]
        return f"n132/arvo:{arvo_id}-{mode}", ["/bin/arvo", "run"]
    if task_id.startswith("oss-fuzz:"):
        oss_fuzz_id = task_id.split(":", 1)[1]
        return f"cybergym/oss-fuzz:{oss_fuzz_id}-{mode}", ["/usr/local/bin/run_poc"]
    raise ValueError(f"unsupported CyberGym task id for local prescreen: {task_id}")


def _docker_image_exists(image: str) -> bool:
    completed = subprocess.run(
        ["docker", "image", "inspect", image],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


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
    if attempt.get("official_submitted") is False:
        summary = (
            f"candidate {attempt.get('candidate_index')}: "
            f"prescreen_exit_code={attempt.get('prescreen_exit_code')} "
            f"official_skipped=True len={attempt.get('poc_length')}"
        )
        preview = str(attempt.get("candidate_text_preview", ""))
        if preview:
            summary += f"\ncandidate_text: {preview}"
        return summary
    summary = (
        f"candidate {attempt.get('candidate_index')}: "
        f"exit_code={attempt.get('exit_code')} len={attempt.get('poc_length')}"
    )
    if attempt.get("prescreen_mode"):
        summary += f" prescreen_exit_code={attempt.get('prescreen_exit_code')}"
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
