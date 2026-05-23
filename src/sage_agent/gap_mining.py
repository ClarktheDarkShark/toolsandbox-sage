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
    existing_tool_names = {
        name for name, record in helpers.items() if not record.retired
    }
    gaps: list[GapSignal] = []

    if _looks_like_candidate_submission_context(profile, task, result):
        existing_candidate_planner_count = len(
            existing_families.intersection(
                {
                    "public_local_search_candidate_planner",
                    "visible_text_candidate_planner",
                    "artifact_literal_candidate_planner",
                    "source_boundary_candidate_planner",
                    "execution_feedback_candidate_mutation_planner",
                    "structured_input_candidate_planner",
                    "semantic_description_candidate_planner",
                    "harness_envelope_candidate_planner",
                    "visible_sample_candidate_planner",
                    "public_crash_pattern_candidate_planner",
                    "adaptive_candidate_portfolio_planner",
                    "format_edge_candidate_planner",
                    "visible_evidence_portfolio_candidate_planner",
                }
            )
        )
        format_kind = _candidate_format_kind(lowered)
        source_family = _candidate_source_family(lowered)
        if (
            "public_local_search_candidate_planner" not in existing_families
            and _has_public_local_search_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="public_local_search_candidate_planning",
                    summary=(
                        "Request a bounded public local execution search when "
                        "static candidate strings are insufficient and visible "
                        "runtime, fuzzer, seed-corpus, or harness cues indicate "
                        "that candidate quality should be improved by public "
                        "vulnerable-side feedback. The helper returns search "
                        "intent and public seed candidates only; the adapter "
                        "must not inspect labels, reference PoCs, hidden answers, "
                        "or fixed-side behavior during search."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_public_local_fuzz_search_candidates",
                    family="public_local_search_candidate_planner",
                    evidence=(
                        "public runtime or fuzzer cue",
                        "public seed/corpus artifact cue",
                        "static candidate attempts did not solve task",
                    ),
                    template="public_local_search_candidate_planner",
                )
            )
        if (
            "public_crash_pattern_candidate_planner" not in existing_families
            and _has_public_crash_pattern_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="public_crash_pattern_candidate_planning",
                    summary=(
                        "Generate a manually reviewed candidate set from public "
                        "vulnerability and harness cues such as libmagic regex "
                        "patterns, PCRE short-text fuzzsupport, PE/MZ parser "
                        "inputs, libxml option strings, and media decoder seeds. "
                        "The helper uses visible artifacts only and only returns "
                        "candidate content."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_public_crash_pattern_candidates",
                    family="public_crash_pattern_candidate_planner",
                    evidence=(
                        "public vulnerability description",
                        "public fuzzer source cue",
                        "manual diagnostic candidate family approved for test",
                    ),
                    template="public_crash_pattern_candidate_planner",
                )
            )

        if (
            "visible_sample_candidate_planner" not in existing_families
            and _has_visible_sample_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="visible_sample_candidate_planning",
                    summary=(
                        "Generate candidate inputs by preserving and normalizing "
                        "public visible sample, fixture, corpus, or test inputs "
                        "from task artifacts. The helper must not inspect hidden "
                        "solutions or execute side effects."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_visible_sample_input_candidates",
                    family="visible_sample_candidate_planner",
                    evidence=(
                        "visible public sample",
                        "visible fixture or corpus input",
                        "candidate attempts failed",
                    ),
                    template="visible_sample_candidate_planner",
                )
            )

        if format_kind:
            tool_name = f"plan_{format_kind}_edge_input_candidates"
            if tool_name not in existing_tool_names:
                gaps.append(
                    _candidate_gap(
                        key=f"{format_kind}_format_edge_candidate_planning",
                        summary=(
                            "Generate candidate inputs for a recurring visible "
                            f"{format_kind.replace('_', ' ')} format or parser edge case."
                        ),
                        source_task_id=task.task_id,
                        source_environment=profile.name,
                        tool_name=tool_name,
                        family="format_edge_candidate_planner",
                        evidence=(
                            "strong visible format cue",
                            "candidate attempts failed",
                            "format-specific edge candidates needed before broad portfolios",
                        ),
                        template="format_edge_candidate_planner",
                        extra_directives={"format_kind": format_kind},
                    )
                )

        if source_family:
            tool_name = f"plan_{source_family}_source_family_candidates"
            if tool_name not in existing_tool_names:
                gaps.append(
                    _candidate_gap(
                        key=f"{source_family}_source_family_candidate_strategy",
                        summary=(
                            "Generate candidate inputs for a visible hard source "
                            f"family: {source_family.replace('_', ' ')}. This "
                            "specialist should be born even when broader candidate "
                            "planners already exist, because weak generic planners "
                            "do not cover every parser or binary format family."
                        ),
                        source_task_id=task.task_id,
                        source_environment=profile.name,
                        tool_name=tool_name,
                        family="source_family_candidate_strategy_planner",
                        evidence=(
                            "visible hard source-family cue",
                            "existing candidate planners did not solve task",
                            "family-specific input strategy needed",
                        ),
                        template="format_edge_candidate_planner",
                        extra_directives={
                            "format_kind": source_family,
                            "source_family": source_family,
                            "birth_even_if_generic_candidate_planners_exist": True,
                        },
                    )
                )

        if (
            "harness_envelope_candidate_planner" not in existing_families
            and _has_harness_envelope_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="public_harness_envelope_candidate_planning",
                    summary=(
                        "Generate candidate inputs that satisfy the visible public "
                        "fuzzer or parser harness envelope before inserting "
                        "format-specific payloads. This is derived from public "
                        "source structure only, not hidden PoCs or labels."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_public_harness_envelope_candidates",
                    family="harness_envelope_candidate_planner",
                    evidence=(
                        "visible fuzzer harness source",
                        "length-split or entity envelope",
                        "candidate attempts failed with shallow inputs",
                    ),
                    template="harness_envelope_candidate_planner",
                )
            )

        if (
            existing_candidate_planner_count >= 2
            and "adaptive_candidate_portfolio_planner" not in existing_families
            and (_attempt_count(result) >= 4 or "exit_code=0" in lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="adaptive_candidate_portfolio_planning",
                    summary=(
                        "Synthesize several weak candidate planners into one "
                        "adaptive portfolio planner that combines visible "
                        "artifact literals, source-boundary values, structured "
                        "format cues, and execution feedback."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_adaptive_candidate_portfolio",
                    family="adaptive_candidate_portfolio_planner",
                    evidence=(
                        "multiple candidate planners visible",
                        "prior candidate attempts failed",
                        "portfolio synthesis needed",
                    ),
                    template="adaptive_candidate_portfolio_planner",
                )
            )

        if (
            existing_candidate_planner_count >= 3
            and "visible_evidence_portfolio_candidate_planner" not in existing_families
            and (_attempt_count(result) >= 4 or "exit_code=0" in lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="visible_evidence_budgeted_portfolio_planning",
                    summary=(
                        "Recognize that several narrower candidate planners are "
                        "not enough, then generate a larger budgeted candidate "
                        "portfolio planner that allocates a limited candidate "
                        "budget across visible samples, artifact literals, "
                        "source constants, semantic format cues, and safe "
                        "mutations."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_visible_evidence_candidate_portfolio",
                    family="visible_evidence_portfolio_candidate_planner",
                    evidence=(
                        "multiple current planners insufficient",
                        "candidate budget allocation needed",
                        "visible artifact and execution evidence available",
                    ),
                    template="visible_evidence_portfolio_candidate_planner",
                )
            )

        if (
            "semantic_description_candidate_planner" not in existing_families
            and _has_semantic_candidate_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="semantic_description_candidate_planning",
                    summary=(
                        "Generate candidate inputs from visible task semantics, "
                        "format names, domain concepts, protocol names, and "
                        "artifact cues without using hidden labels."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_semantic_description_input_candidates",
                    family="semantic_description_candidate_planner",
                    evidence=(
                        "visible task description",
                        "visible artifact domain terms",
                        "semantic input-shape cues",
                    ),
                    template="semantic_description_candidate_planner",
                )
            )

        if (
            "source_boundary_candidate_planner" not in existing_families
            and _has_source_boundary_cue(lowered)
        ):
            gaps.append(
                _candidate_gap(
                    key="source_boundary_value_candidate_planning",
                    summary=(
                        "Generate candidate inputs from visible source-artifact "
                        "boundary values, magic literals, parser constants, and "
                        "size/length/check comparisons."
                    ),
                    source_task_id=task.task_id,
                    source_environment=profile.name,
                    tool_name="plan_source_boundary_input_candidates",
                    family="source_boundary_candidate_planner",
                    evidence=(
                        "visible source-like lines",
                        "boundary or size constants",
                        "magic strings or parser comparisons",
                    ),
                    template="source_boundary_candidate_planner",
                )
            )

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
    extra_directives: Mapping[str, object] | None = None,
) -> GapSignal:
    directives: dict[str, object] = {"template": template}
    if extra_directives:
        directives.update(extra_directives)
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
        generation_directives=directives,
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
        "packet",
        "frame",
        "transport",
        "codec",
        "decoder",
        "media",
        "audio",
    )
    return any(cue in text for cue in cues)


def _has_semantic_candidate_cue(text: str) -> bool:
    """Detect visible domain/format terms that imply reusable input families."""

    cues = (
        "namespace",
        "xmlns",
        "doctype",
        "entity",
        "attribute",
        "xml",
        "html",
        "regex",
        "regexp",
        "pcre",
        "oniguruma",
        "capturing",
        "ovector",
        "portable executable",
        "pe module",
        "yara",
        "bam",
        "cram",
        "sam",
        "aux tag",
        "auxiliary tag",
        "ssh",
        "libssh",
        "kex",
        "handshake",
        "decimal",
        "numeric",
        "bignum",
        "tpm",
        "selinux",
        "policy",
        "common class",
        "font",
        "cff",
        "freetype",
        "opentype",
        "codec",
        "decoder",
        "decode",
        "media",
        "audio",
        "aac",
        "xaac",
        "adts",
        "uart",
        "transport",
        "packet",
        "frame",
        "binary message",
        "binary_message",
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


def _has_public_crash_pattern_cue(text: str) -> bool:
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


def _has_public_local_search_cue(text: str) -> bool:
    cues = (
        "runtime_binary:",
        "runtime_entrypoint:",
        "llvmfuzzertestoneinput",
        "honggfuzz",
        "libfuzzer",
        "seed_corpus",
        "corpus_sample:",
        "sample_escape:",
        "sample_text:",
        "fuzzer",
        "fuzz target",
    )
    return any(cue in text for cue in cues) and any(
        marker in text
        for marker in (
            "exit_code=0",
            "candidate",
            "failed",
            "submit",
            "prescreen",
            "runtime_binary:",
        )
    )


def _has_harness_envelope_cue(text: str) -> bool:
    """Detect public harness parsing patterns that require shaped inputs."""

    if "llvmfuzzertestoneinput" in text and any(
        cue in text
        for cue in (
            "sizeof(",
            "memcpy(",
            "len1",
            "len2",
            "flags",
            "fuzzeddata",
            "consumeintegral",
            "consume_bytes",
            "xmlfuzz",
        )
    ):
        return True
    if any(
        cue in text
        for cue in (
            "xmlfuzzdatainit",
            "xmlfuzzreadentities",
            "xmlfuzzmainentity",
            "xmlfuzzreadstring",
        )
    ):
        return True
    return "source_line:" in text and any(
        cue in text
        for cue in (
            "size_t preamble",
            "sizeof(neaacdecconfiguration)",
            "len1 = data[0]",
            "len2 = data[0]",
            "fuzzeddata",
        )
    )


def _candidate_format_kind(text: str) -> str:
    """Classify visible candidate-input format cues without labels or answers."""

    cue_sets = (
        ("regex", ("regex", "regexp", "pcre", "oniguruma", "capture", "ovector")),
        ("xml", ("xml", "html", "doctype", "xmlns", "namespace", "libxml")),
        ("json", ("json", "jq", "decnumber", "parse_extended")),
        (
            "file_format",
            (
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
        ),
        (
            "numeric",
            (
                "float",
                "double",
                "decimal",
                "numeric",
                "number",
                "scientific notation",
            ),
        ),
        (
            "binary_protocol",
            (
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
        ),
    )
    best: tuple[int, str] | None = None
    for kind, cues in cue_sets:
        positions = [text.find(cue) for cue in cues if cue in text]
        if not positions:
            continue
        position = min(positions)
        if best is None or position < best[0]:
            best = (position, kind)
    return best[1] if best else ""


def _candidate_source_family(text: str) -> str:
    """Classify visible hard source families for specialist helper birth.

    This uses only public task text, public artifact summaries, and execution
    feedback visible to SAGE. It intentionally returns broad families rather
    than benchmark IDs or expected answers.
    """

    cue_sets = (
        (
            "xml_namespace",
            (
                "xmlsearchnssafe",
                "xmladdidsafe",
                "xmlremoveid",
                "xmlvalidateonenamespace",
                "namespace",
                "xmlns",
                "doctype",
                "entity",
                "libxml",
                "--with-html",
            ),
        ),
        (
            "aac_audio",
            (
                "aac",
                "adts",
                "adif",
                "faad",
                "neaac",
                "xaac",
                "usac",
                "sbr",
                "drc",
                "audio",
                "decoder",
            ),
        ),
        (
            "htslib_alignment",
            ("htslib", "sam", "bam", "cram", "aux tag", "auxiliary tag", "@hd"),
        ),
        (
            "libssh_kex",
            ("libssh", " kex", "key exchange", "namelist", "diffie-hellman"),
        ),
        (
            "pcre_ovector",
            ("pcre", "pcre2", "ovector", "regexec", "regex", "regexp", "capture"),
        ),
        (
            "pe_module",
            ("portable executable", "pe module", "mz header", 'import "pe"', "is_pe"),
        ),
        (
            "font_cff",
            ("freetype", "cff", "opentype", "font", "glyph", "charstring"),
        ),
        (
            "selinux_policy",
            ("libsepol", "selinux", "policy", "common class", "allow ", "sid "),
        ),
        ("tpm_binary", ("tpm", "tpm2", "marshal", "unmarshal", "binary message")),
        (
            "afl_filter",
            ("duplicate filter", "filter list", "afl", "deferred forkserver"),
        ),
    )
    best: tuple[int, str] | None = None
    for family, cues in cue_sets:
        positions = [text.find(cue) for cue in cues if cue in text]
        if not positions:
            continue
        position = min(positions)
        if best is None or position < best[0]:
            best = (position, family)
    return best[1] if best else ""


def _has_source_boundary_cue(text: str) -> bool:
    if "source_line:" not in text:
        return False
    cues = (
        "size",
        "length",
        "chunk",
        "version",
        "magic",
        "header",
        "token",
        "strcmp",
        "memcmp",
        "==",
        ">=",
        "<=",
        "boundary",
        "overflow",
    )
    return any(cue in text for cue in cues) and any(ch.isdigit() for ch in text)


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
