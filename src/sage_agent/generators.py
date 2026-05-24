"""Helper generators for standalone SAGE.

Template generation is used for deterministic smoke tests. ``OpenAIHelperGenerator``
provides the same protocol for low-cost live generation with ``gpt-4o-mini``.
"""

from __future__ import annotations

import json
import re
from importlib import import_module
from typing import Any, cast

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperSpec,
    TaskRunResult,
    ValidationCase,
)

CANDIDATE_PLANNER_FAMILIES = {
    "public_local_search_candidate_planner",
    "public_crash_pattern_candidate_planner",
    "visible_text_candidate_planner",
    "artifact_literal_candidate_planner",
    "execution_feedback_candidate_mutation_planner",
    "structured_input_candidate_planner",
    "semantic_description_candidate_planner",
    "source_boundary_candidate_planner",
    "harness_envelope_candidate_planner",
    "adaptive_candidate_portfolio_planner",
    "visible_evidence_portfolio_candidate_planner",
    "format_edge_candidate_planner",
    "visible_sample_candidate_planner",
}

TEMPLATE_BACKED_DIRECTIVES = {
    "unique_record_selector",
    "log_signal_classifier",
    "public_local_search_candidate_planner",
    "public_crash_pattern_candidate_planner",
    "visible_text_candidate_planner",
    "artifact_literal_candidate_planner",
    "visible_sample_candidate_planner",
    "source_boundary_candidate_planner",
    "harness_envelope_candidate_planner",
    "semantic_description_candidate_planner",
    "execution_feedback_candidate_mutation_planner",
    "structured_input_candidate_planner",
    "adaptive_candidate_portfolio_planner",
    "visible_evidence_portfolio_candidate_planner",
    "format_edge_candidate_planner",
    "grid_shortest_path_action_planner",
    "symbolic_text_answerer",
    "policy_action_precondition_planner",
    "terminal_task_repair_planner",
}


class TemplateHelperGenerator:
    """Generate deterministic helpers from environment-provided directives."""

    def generate(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        template = str(gap.generation_directives.get("template", "")).strip()
        name = gap.suggested_tool_name or _safe_name(gap.key)
        if template == "unique_record_selector":
            return _unique_record_selector(name, gap, profile, validation_cases, model)
        if template == "log_signal_classifier":
            return _log_signal_classifier(name, gap, profile, validation_cases, model)
        if template == "visible_text_candidate_planner":
            return _visible_text_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "public_local_search_candidate_planner":
            return _public_local_search_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "public_crash_pattern_candidate_planner":
            return _public_crash_pattern_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "artifact_literal_candidate_planner":
            return _artifact_literal_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "visible_sample_candidate_planner":
            return _visible_sample_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "source_boundary_candidate_planner":
            return _source_boundary_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "harness_envelope_candidate_planner":
            return _harness_envelope_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "semantic_description_candidate_planner":
            return _semantic_description_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "execution_feedback_candidate_mutation_planner":
            return _execution_feedback_candidate_mutation_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "structured_input_candidate_planner":
            return _structured_input_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "adaptive_candidate_portfolio_planner":
            return _adaptive_candidate_portfolio_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "visible_evidence_portfolio_candidate_planner":
            return _visible_evidence_portfolio_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "format_edge_candidate_planner":
            return _format_edge_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "grid_shortest_path_action_planner":
            return _grid_shortest_path_action_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "symbolic_text_answerer":
            return _symbolic_text_answerer(name, gap, profile, validation_cases, model)
        if template == "policy_action_precondition_planner":
            return _policy_action_precondition_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "terminal_task_repair_planner":
            return _terminal_task_repair_planner(
                name, gap, profile, validation_cases, model
            )
        raise ValueError(f"unsupported_template:{template or 'missing'}")

    def repair(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        rejected: HelperCandidate,
        errors: tuple[str, ...],
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        """Repair by regenerating or widening a generic helper design."""

        del errors
        if rejected.spec.family in CANDIDATE_PLANNER_FAMILIES:
            if rejected.spec.family == "public_local_search_candidate_planner":
                return _public_local_search_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "public_crash_pattern_candidate_planner":
                return _public_crash_pattern_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "format_edge_candidate_planner":
                return _format_edge_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "semantic_description_candidate_planner":
                return _semantic_description_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "visible_sample_candidate_planner":
                return _visible_sample_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "visible_evidence_portfolio_candidate_planner":
                return _visible_evidence_portfolio_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "harness_envelope_candidate_planner":
                return _harness_envelope_candidate_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            if rejected.spec.family == "policy_action_precondition_planner":
                return _policy_action_precondition_planner(
                    rejected.spec.name, gap, profile, validation_cases, model
                )
            return _adaptive_candidate_portfolio_planner(
                rejected.spec.name, gap, profile, validation_cases, model
            )
        return self.generate(gap, profile, validation_cases, model=model)


class OpenAIHelperGenerator:
    """LLM-backed helper generator using the OpenAI Python SDK.

    The generator is intentionally environment-neutral. It receives an adapter
    profile, a gap signal, and validation cases; it does not know benchmark
    labels or hidden answers. The default model is expected to be ``gpt-4o-mini``
    unless a run protocol deliberately overrides it.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        try:
            openai_module = import_module("openai")
        except Exception as exc:  # pragma: no cover - depends on local install
            raise RuntimeError(
                "openai package is required for live generation"
            ) from exc
        OpenAI = getattr(openai_module, "OpenAI")
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def generate(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        template = str(gap.generation_directives.get("template", "")).strip()
        if template in TEMPLATE_BACKED_DIRECTIVES:
            return TemplateHelperGenerator().generate(
                gap,
                profile,
                validation_cases,
                model=model,
            )
        payload = self._complete_json(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {
                    "role": "user",
                    "content": _generation_prompt(gap, profile, validation_cases),
                },
            ],
        )
        return _candidate_from_payload(payload, gap, profile, validation_cases, model)

    def generate_guidance(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        result: TaskRunResult,
        *,
        model: str,
    ) -> HelperCandidate:
        """Generate a prompt-guidance helper for import-mode harnesses."""

        payload = self._complete_json(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate safe SAGE prompt-guidance helpers from "
                        "official benchmark feedback. Return JSON with key "
                        "'guidance'. The guidance must be reusable, actionable, "
                        "and must not reveal hidden labels, reference solutions, "
                        "expected answers, or task-specific IDs."
                    ),
                },
                {
                    "role": "user",
                    "content": _guidance_generation_prompt(gap, profile, result),
                },
            ],
        )
        return _guidance_candidate_from_payload(payload, gap, profile, result, model)

    def repair(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        rejected: HelperCandidate,
        errors: tuple[str, ...],
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        template = str(gap.generation_directives.get("template", "")).strip()
        if template in TEMPLATE_BACKED_DIRECTIVES:
            return TemplateHelperGenerator().repair(
                gap,
                profile,
                rejected,
                errors,
                validation_cases,
                model=model,
            )
        payload = self._complete_json(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {
                    "role": "user",
                    "content": _repair_prompt(
                        gap, profile, rejected, errors, validation_cases
                    ),
                },
            ],
        )
        return _candidate_from_payload(payload, gap, profile, validation_cases, model)

    def _complete_json(
        self, *, model: str, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("generator_returned_non_object_json")
        return cast(dict[str, Any], parsed)


def _unique_record_selector(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(records: list, field_name: str, expected_value: str, return_field: str) -> dict:
    expected_text = str(expected_value).strip().lower()
    expected_digits = "".join(ch for ch in expected_text if ch.isdigit())
    digit_field = "phone" in field_name.lower() or "number" in field_name.lower()
    normalized_expected = expected_digits if digit_field and expected_digits else expected_text
    matches = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_text = str(record.get(field_name, "")).strip().lower()
        record_digits = "".join(ch for ch in record_text if ch.isdigit())
        normalized_record = record_digits if digit_field and record_digits else record_text
        if normalized_record == normalized_expected:
            matches.append((index, record))
    if len(matches) != 1:
        return {{
            "selected_index": -1,
            "selected_record": {{}},
            "value": "",
            "abstain_reason": "no_unique_match",
            "abstain": True,
        }}
    index, record = matches[0]
    return {{
        "selected_index": index,
        "selected_record": record,
        "value": str(record.get(return_field, "")),
        "abstain_reason": "",
        "abstain": False,
    }}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("no unique visible record", "ambiguous match"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _guidance_generation_prompt(
    gap: GapSignal,
    profile: EnvironmentProfile,
    result: TaskRunResult,
) -> str:
    payload = {
        "environment": profile.name,
        "environment_description": profile.description,
        "gap_summary": gap.summary,
        "failure_family": gap.generation_directives.get("failure_family", ""),
        "visible_failure_evidence": list(gap.evidence),
        "task_prompt_excerpt": result.task.prompt[:1200],
        "transcript_excerpt": "\n".join(result.transcript)[-6000:],
        "error": result.error[:800],
        "requirements": (
            "Return 2-5 concise bullet lines. Focus on reusable policy, "
            "precondition, tool-use, argument-checking, calculation, validation, "
            "or stop-condition guidance for later tasks in this environment. "
            "Do not include task IDs, hidden labels, reference solutions, exact "
            "answers, or benchmark-specific memorized strings."
        ),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _guidance_candidate_from_payload(
    payload: dict[str, Any],
    gap: GapSignal,
    profile: EnvironmentProfile,
    result: TaskRunResult,
    model: str,
) -> HelperCandidate:
    value = payload.get("guidance", "")
    if isinstance(value, list):
        guidance = "\n".join(str(item) for item in value)
    else:
        guidance = str(value)
    guidance = _normalize_guidance_text(guidance)
    name = gap.suggested_tool_name or _safe_name(gap.key)
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
        code=guidance,
        validation_cases=(),
        metadata={
            "model": model,
            "environment": profile.name,
            "gap_key": gap.key,
            "helper_type": "prompt_guidance",
            "source_task_name": result.task.name[:120],
        },
    )


def _normalize_guidance_text(guidance: str) -> str:
    lines = [line.strip() for line in guidance.splitlines() if line.strip()]
    normalized: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*[-*]\s*", "- ", line)
        line = re.sub(r"^\s*\d+[.)]\s*", "- ", line)
        if not line.startswith("- "):
            line = f"- {line}"
        normalized.append(line[:240])
    return "\n".join(normalized[:5])


def _log_signal_classifier(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(exit_code: int, output: str) -> dict:
    text = str(output or "")
    lower = text.lower()
    crashed = bool(exit_code not in (0, 300)) or "addresssanitizer" in lower or "runtime error" in lower or "segmentation fault" in lower
    timed_out = exit_code == 300 or "timeout" in lower
    sanitizer = ""
    for token in ("addresssanitizer", "undefinedbehaviorsanitizer", "memorysanitizer", "runtime error"):
        if token in lower:
            sanitizer = token
            break
    if crashed:
        recommendation = "keep_and_minimize_poc"
    elif timed_out:
        recommendation = "reduce_input_or_extend_search"
    else:
        recommendation = "mutate_input_or_revisit_hypothesis"
    return {{
        "crashed": crashed,
        "timed_out": timed_out,
        "sanitizer": sanitizer,
        "recommendation": recommendation,
        "abstain": False,
    }}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("no execution output", "irrelevant non-execution task"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _visible_text_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    candidates = []
    lower = text.lower()
    cue_markers = (
        "example input:",
        "input:",
        "such as",
        "for example",
        "e.g.",
        "trigger:",
        "poc:",
        "candidate:",
        "candidate_text:",
        "successful_candidate:",
        "crashing_candidate:",
    )
    deferred = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        line_lower = line.lower()
        if line_lower.startswith("file:"):
            continue
        for marker in cue_markers:
            pos = line_lower.find(marker)
            if pos >= 0 and "provided as input to the vulnerable program" not in line_lower:
                value = line[pos + len(marker):].strip(" :,;\\t")
                if 0 < len(value) <= 240:
                    candidates.append(value)
        if ":" in line and line_lower.split(":", 1)[0] in (
            "literal",
            "symbol",
            "source_line",
            "dict",
            "example",
            "input",
            "sample_text",
            "sample_escape",
            "corpus_sample",
        ):
            value = line.split(":", 1)[1].strip(" :,;\\t")
            if 0 < len(value) <= 240:
                deferred.append(value)
        if line_lower.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            line_lower = line.lower()
        if len(line) <= 180 and any(ch in line for ch in "()[]{{}}<>/\\\\_=:+-.0123456789") and "provided as input to the vulnerable program" not in line_lower:
            deferred.append(line)
    seed_pool = [
        "",
        "\\x00",
        "\\xff",
        "A",
        "AAAA",
        "0",
        "1",
        "-1",
        "0\\n",
        "(",
        "(a",
        "()",
        "{{}}",
        "[]",
        "<a/>",
        "<root></root>",
        "a,b\\n",
        "\\x00\\x01\\x02\\x03",
        "A" * 32,
        "A" * 128,
    ]
    if "short" in lower or "empty" in lower or "null" in lower:
        seed_pool = ["", "\\x00"] + seed_pool
    candidates.extend(seed_pool)
    for quote in ("`", "\\"", "'"):
        start = 0
        while True:
            left = text.find(quote, start)
            if left < 0:
                break
            right = text.find(quote, left + 1)
            if right < 0:
                break
            value = text[left + 1:right].strip()
            if 0 < len(value) <= 240:
                candidates.append(value)
            start = right + 1
    candidates.extend(deferred)
    for token in text.replace("\\n", " ").split():
        value = token.strip(" ,;")
        value = value.strip()
        if 1 < len(value) <= 160 and any(ch in value for ch in "()[]{{}}<>/\\\\_=:+-.0123456789"):
            candidates.append(value.strip(".,;"))
    base_values = list(candidates[:24])
    for value in base_values:
        if isinstance(value, str) and 0 < len(value) <= 80:
            candidates.append(value + "\\n")
            candidates.append(value + value)
    seen = set()
    unique = []
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("no visible description", "external state mutation"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _artifact_literal_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(artifact_summary or "") + "\\n" + str(description or "") + "\\n" + str(readme or "")
    candidates = []
    prefixes = (
        "literal:",
        "source_line:",
        "dict:",
        "token:",
        "example:",
        "input:",
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
    )
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("file:"):
            continue
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = line[len(prefix):].strip(" :,;\\t")
                if 0 < len(value) <= 240:
                    candidates.append(value)
        if lower.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            lower = line.lower()
        if "==" in line or "strcmp" in lower or "memcmp" in lower:
            for quote in ("\\"", "'"):
                start = 0
                while True:
                    left = line.find(quote, start)
                    if left < 0:
                        break
                    right = line.find(quote, left + 1)
                    if right < 0:
                        break
                    value = line[left + 1:right].strip()
                    if 0 < len(value) <= 240:
                        candidates.append(value)
                    start = right + 1
        if len(line) <= 160 and any(ch in line for ch in "()[]{{}}<>/\\\\_=:+-.0123456789"):
            candidates.append(line)
    literal_bases = [str(item) for item in candidates[:16] if 0 < len(str(item)) <= 80]
    for value in literal_bases:
        candidates.append(value + "\\n")
        candidates.append(value + "\\x00")
        candidates.append(value + value)
    candidates.extend(["MAGIC", "magic", "AAAA", "\\x00\\x01\\x02\\x03", "A" * 32])
    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _public_crash_pattern_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    raw_candidates = []

    if "magic_buffer" in lower or "#include <magic.h>" in lower or "libmagic" in lower or ("magic" in lower and "regexec" in lower):
        raw_candidates.extend((
            "#include <magic.h>",
            "@HD\\tVN:1.6",
            "MZ" + ("A" * 64),
        ))

    if "pcre2" in lower or "fuzzsupport" in lower or "short text" in lower or "very short" in lower or "regexec" in lower:
        raw_candidates.extend((
            "0E-100000",
            "0E-100000\\n",
            "(",
            "\\\\A",
            "\\\\K",
            "[a-",
            "(?<a>a)(?<a>b)",
        ))

    if "yara" in lower or "rules_fuzzer" in lower or "portable executable" in lower or "pe module" in lower or "jpeg_write_raw_data" in lower or "mcu" in lower:
        raw_candidates.extend((
            "MZ" + ("A" * 64),
            "MZ" + (" " * 56) + (chr(0) * 2) + (" " * 117) + "PE" + (chr(0) * 2) + "d " + (chr(0) * 4),
            "import \\"pe\\"\\nrule a {{ condition: pe.number_of_sections >= 0 }}",
            "rule a {{ condition: true }}",
        ))

    if "libxml2" in lower or "xmlsearchnssafe" in lower or "xmladdidsafe" in lower or "xmlremoveid" in lower or "xml reader" in lower:
        raw_candidates.extend((
            "--with-html             HTML parser (on)",
            "<a xmlns:p='urn:x' p:id='x' id='x'/>",
            "<!DOCTYPE a [<!ELEMENT a EMPTY><!ATTLIST a id ID #IMPLIED>]><a id='x'/>",
            "<?xml version='1.0'?><root><a id='x'/><b ref='x'/></root>",
        ))

    if "aac" in lower or "faad" in lower or "neaacdec" in lower or "xaac" in lower or "audio object" in lower:
        raw_candidates.extend((
            "\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc",
            "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc",
            "ADIF",
            "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00",
        ))

    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        lowered_line = line.lower()
        if not line or lowered_line.startswith("file:"):
            continue
        if lowered_line.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            lowered_line = line.lower()
        if lowered_line.startswith(("literal:", "dict:", "sample_text:", "sample_escape:", "corpus_sample:")):
            raw_candidates.append(line.split(":", 1)[1].strip())
            continue
        if len(line) <= 160 and any(cue in lowered_line for cue in ("--with-html", "#include <magic.h>", "0e-100000", "vn:1.6")):
            raw_candidates.append(line)

    if not raw_candidates:
        raw_candidates.extend(("A", "AAAA", "\\x00\\x00\\x00\\x00"))

    expanded = []
    for value in raw_candidates:
        candidate = str(value or "")
        if not candidate:
            continue
        if len(candidate) > 320:
            candidate = candidate[:320]
        expanded.append(candidate)
        if 0 < len(candidate) <= 96 and not candidate.endswith("\\n"):
            expanded.append(candidate + "\\n")

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in expanded:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _public_local_search_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    candidates = []

    public_runtime_cues = (
        "runtime_binary:",
        "runtime_entrypoint:",
        "libfuzzer",
        "honggfuzz",
        "llvmfuzzertestoneinput",
        "seed_corpus",
        "corpus_sample:",
        "sample_escape:",
        "sample_text:",
        "fuzz target",
        "fuzzer",
    )
    if any(cue in lower for cue in public_runtime_cues):
        candidates.append("search_strategy: public_local_fuzz")
        hard_source_cues = (
            "aac",
            "adts",
            "audio",
            "bam",
            "cff",
            "conditional section",
            "cram",
            "freetype",
            "htslib",
            "kex",
            "libsepol",
            "libssh",
            "libxml",
            "namespace",
            "ovector",
            "pcre",
            "pe module",
            "regex",
            "sam",
            "sbr",
            "selinux",
            "tpm",
            "usac",
            "xaac",
            "xml",
        )
        if any(cue in lower for cue in hard_source_cues):
            candidates.append("search_budget: source_guided_deep")
        else:
            candidates.append("search_budget: bounded_public_vulnerable_execution")

    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(("sample_escape:", "corpus_sample:", "sample_text:", "dict:", "literal:")):
            value = line.split(":", 1)[1].strip(" :,;\\t")
            if 0 < len(value) <= 4096:
                candidates.append(line)
                if lowered.startswith(("sample_escape:", "corpus_sample:")):
                    candidates.append("corpus_sample: " + value + "\\\\x00")
                    candidates.append("corpus_sample: " + value + "\\\\xff")
            continue
        if lowered.startswith("runtime_binary:") and "fuzz" in lowered:
            candidates.append("search_target_hint: " + line.split(":", 1)[1].strip())
        if lowered.startswith("source_line:") and any(cue in lowered for cue in ("llvmfuzzertestoneinput", "honggfuzz", "fuzzeddata", "data[", "size_t")):
            candidates.append(line)

    if "search_strategy: public_local_fuzz" not in candidates and candidates:
        candidates.insert(0, "search_strategy: public_local_fuzz")

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": not bool(unique),
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _visible_sample_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(artifact_summary or "") + "\\n" + str(description or "") + "\\n" + str(readme or "")
    candidates = []
    deferred = []
    sample_payloads = []
    sample_prefixes = ("sample_escape:", "corpus_sample:", "sample_text:")
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("file:"):
            continue
        for prefix in sample_prefixes:
            if lowered.startswith(prefix):
                value = line[len(prefix):].strip(" :,;\\t")
                if 0 < len(value) <= 1024:
                    candidates.append(prefix + " " + value)
                    if prefix == "sample_text:":
                        deferred.append(value)
                        sample_payloads.append(value)
                    else:
                        decoded = ""
                        index = 0
                        hexdigits = "0123456789abcdefABCDEF"
                        while index < len(value):
                            if index + 3 < len(value) and value[index:index + 2] == "\\\\x" and value[index + 2] in hexdigits and value[index + 3] in hexdigits:
                                decoded += chr(int(value[index + 2:index + 4], 16))
                                index += 4
                            elif index + 1 < len(value) and value[index:index + 2] == "\\\\n":
                                decoded += "\\n"
                                index += 2
                            elif index + 1 < len(value) and value[index:index + 2] == "\\\\r":
                                decoded += "\\r"
                                index += 2
                            elif index + 1 < len(value) and value[index:index + 2] == "\\\\t":
                                decoded += "\\t"
                                index += 2
                            else:
                                decoded += value[index]
                                index += 1
                        if decoded:
                            sample_payloads.append(decoded)
                break
        if lowered.startswith(("dict:", "literal:", "example:", "input:")):
            value = line.split(":", 1)[1].strip(" :,;\\t")
            if 0 < len(value) <= 240:
                deferred.append(value)
        if lowered.startswith("source_line:"):
            source = line.split(":", 1)[1].strip()
            source_lower = source.lower()
            if any(token in source_lower for token in ("magic", "header", "sample", "fixture", "corpus", "parse", "read")) and len(source) <= 180:
                deferred.append(source)
    for payload in sample_payloads[:8]:
        if not payload:
            continue
        candidates.append(payload)
        payload_length = len(payload)
        for size in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
            if size <= payload_length:
                candidates.append(payload[:size])
        if payload_length <= 1024:
            for marker in ("\\x00", "\\xff", "A", "\\x7f"):
                candidates.append(marker + payload)
                candidates.append(payload + marker)
        positions = []
        for pos in (0, 1, 2, 3, payload_length // 4, payload_length // 2, payload_length - 4, payload_length - 2, payload_length - 1):
            if 0 <= pos < payload_length and pos not in positions:
                positions.append(pos)
        for pos in positions[:10]:
            for replacement in ("\\x00", "\\xff", "A"):
                candidates.append(payload[:pos] + replacement + payload[pos + 1:])
            candidates.append(payload[:pos] + payload[pos + 1:])
            candidates.append(payload[:pos] + "\\x00" + payload[pos:])
    candidates.extend(deferred)
    if not candidates:
        candidates.extend(["\\x00\\x01\\x02\\x03", "A", "AAAA", "<a/>"])
    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _source_boundary_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(artifact_summary or "") + "\\n" + str(description or "") + "\\n" + str(readme or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    candidates = []
    literals = []
    numbers = []

    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        line_lower = line.lower()
        if line_lower.startswith("file:"):
            continue
        source_like_line = False
        if line_lower.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            line_lower = line.lower()
            source_like_line = True
        for prefix in (
            "literal:",
            "dict:",
            "token:",
            "magic:",
            "example:",
            "input:",
            "sample_text:",
            "sample_escape:",
            "corpus_sample:",
        ):
            if line_lower.startswith(prefix):
                value = line[len(prefix):].strip(" :,;\\t")
                if 0 < len(value) <= 240:
                    literals.append(value)
                    candidates.append(value)
        if "strcmp" in line_lower or "memcmp" in line_lower or "==" in line:
            for quote in ("\\"", "'"):
                start = 0
                while True:
                    left = line.find(quote, start)
                    if left < 0:
                        break
                    right = line.find(quote, left + 1)
                    if right < 0:
                        break
                    value = line[left + 1:right].strip()
                    if 0 < len(value) <= 240:
                        literals.append(value)
                        candidates.append(value)
                    start = right + 1
        if source_like_line and 0 < len(line) <= 180 and any(ch in line for ch in "()[]{{}}<>/\\\\_=:+-.0123456789"):
            candidates.append(line)
        token = ""
        for ch in line:
            if ch.isdigit():
                token += ch
            else:
                if token:
                    numbers.append(token)
                token = ""
        if token:
            numbers.append(token)

    for value in ("0", "1", "-1", "2", "3", "4", "7", "8", "15", "16", "31", "32", "63", "64", "127", "128", "255", "256", "257", "511", "512", "1023", "1024", "4095", "4096", "65535", "65536", "2147483647", "2147483648", "4294967295"):
        candidates.append(value)
    for value in ("\\x00", "\\xff", "\\xff\\xff", "\\xff\\xff\\xff\\xff", "\\x00\\x00\\x00\\x00", "\\x01\\x00\\x00\\x00", "A" * 8, "A" * 32, "A" * 128, "A" * 256):
        candidates.append(value)

    for number_text in numbers[:40]:
        if number_text.isdigit():
            value = int(number_text)
            if 0 <= value <= 4294967296:
                for delta in (-1, 0, 1):
                    candidate_number = value + delta
                    if candidate_number >= 0:
                        candidates.append(str(candidate_number))
                if 1 <= value <= 512:
                    candidates.append("A" * value)
                    candidates.append("\\x00" * min(value, 64))

    if "xml" in lower or "<" in text:
        for value in ("<a/>", "<root></root>", "<root>0</root>", "<root>4294967295</root>"):
            candidates.append(value)
    if "json" in lower or "javascript" in lower:
        for value in ("{{}}", "[]", "{{\\"size\\":0}}", "{{\\"size\\":4294967295}}"):
            candidates.append(value)
    if "csv" in lower or "comma" in lower:
        for value in ("0,0\\n", "1,4294967295\\n", "size,value\\n4294967295,A\\n"):
            candidates.append(value)

    base_literals = [str(item) for item in literals[:12] if 0 < len(str(item)) <= 96]
    boundary_values = ("0", "1", "-1", "255", "256", "1024", "4096", "65535", "4294967295")
    for literal in base_literals:
        candidates.append(literal + "\\n")
        candidates.append(literal + "\\x00")
        candidates.append(literal + literal)
        for number in boundary_values[:5]:
            candidates.append(literal + number)
            candidates.append(literal + "\\n" + number)

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _semantic_description_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    raw_candidates = []

    semantic_groups = []
    for group_name, cues in (
        ("regex", ("regex", "regexp", "pcre", "oniguruma", "capture", "capturing", "ovector", "pattern")),
        ("xml", ("xml", "html", "xmlns", "namespace", "doctype", "entity", "attribute", "id", "reader")),
        ("pe", ("portable executable", "pe module", "pe parser", "yara", "mz header", "mz")),
        ("sam", ("bam", "cram", "sam", "htslib", "aux tag", "auxiliary tag", "aux")),
        ("ssh", ("ssh", "libssh", "kex", "handshake", "algorithm", "protocol")),
        ("binary_protocol", ("binary_message", "binary message", "packet", "frame", "framed", "transport", "uart", "socket")),
        ("media", ("audio", "codec", "decoder", "decode", "media", "aac", "xaac", "adts", "mpeg", "wave", "wav", "ogg", "flac")),
        ("numeric", ("decimal", "number", "numeric", "bignum", "big num", "integer", "float", "double", "tpm")),
        ("selinux", ("selinux", "policy", "common class", "class file", "policy module")),
        ("font", ("font", "cff", "blend", "freetype", "type2", "opentype")),
    ):
        best_position = -1
        for cue in cues:
            position = lower.find(cue)
            if position >= 0 and (best_position < 0 or position < best_position):
                best_position = position
        if best_position >= 0:
            semantic_groups.append((best_position, group_name))

    for _, semantic_kind in sorted(semantic_groups):
        if semantic_kind == "xml":
            if "namespace" in lower or "xmlns" in lower:
                raw_candidates.extend((
                    "<a xmlns:p='urn:x' p:id='x' id='x'/>",
                    "<root xmlns='urn:x'><child id='x'/></root>",
                    "<root xmlns:x='urn:x'><x:a x:id='x'/></root>",
                ))
            if "entity" in lower or "doctype" in lower:
                raw_candidates.extend((
                    "<?xml version='1.0'?><!DOCTYPE a [<!ENTITY x 'x'>]><a>&x;</a>",
                    "<!DOCTYPE a><a/>",
                ))
            raw_candidates.extend((
                "<a/>",
                "<root></root>",
                "<root><a id='x'/><b ref='x'/></root>",
                "<a><b></a>",
                "<html><body>A</body></html>",
            ))
        elif semantic_kind == "regex":
            raw_candidates.extend((
                "(",
                "(a",
                "()",
                "(a)\\\\1",
                "(?<a>a)",
                "(?<a>a)(?<a>b)",
                "[a-",
                "\\\\A",
                "\\\\K",
                "\\\\C",
                "A\\\\x00A",
            ))
        elif semantic_kind == "pe":
            raw_candidates.extend((
                "MZ",
                "MZ\\x90\\x00",
                "MZ" + ("A" * 64),
                "rule a {{ condition: true }}",
                "import \\"pe\\"\\nrule a {{ condition: pe.number_of_sections >= 0 }}",
                "This is just an example",
            ))
        elif semantic_kind == "sam":
            raw_candidates.extend((
                "@HD\\tVN:1.6\\n",
                "r001\\t0\\tchr1\\t1\\t60\\t1M\\t*\\t0\\t0\\tA\\t*\\n",
                "r001\\t0\\tchr1\\t1\\t60\\t1M\\t*\\t0\\t0\\tA\\t*\\tXX:B:i,1,2,3\\n",
                "B:i,1,2,3",
                "XX:B:c,1,2,3,4,5,6,7",
            ))
        elif semantic_kind == "ssh":
            raw_candidates.extend((
                "diffie-hellman-group14-sha1",
                "curve25519-sha256,ecdh-sha2-nistp256",
                "kex_algorithms=diffie-hellman-group14-sha1",
                "SSH-2.0-test\\r\\n",
            ))
        elif semantic_kind == "binary_protocol":
            raw_candidates.extend((
                "\\x00",
                "\\x00\\x00\\x00\\x00",
                "\\xff\\xff\\xff\\xff",
                "\\x01\\x00\\x00\\x00",
                "\\x02A\\x03",
                "\\x00A\\x00",
                "A\\x00A",
                "MSG\\x00\\x00\\x00\\x01A",
                "LEN=1\\nA",
            ))
        elif semantic_kind == "media":
            raw_candidates.extend((
                "\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc",
                "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc",
                "ADIF",
                "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00",
                "RIFF\\x24\\x00\\x00\\x00WAVEfmt ",
                "OggS\\x00\\x02",
                "fLaC\\x00\\x00\\x00\\x22",
            ))
        elif semantic_kind == "numeric":
            raw_candidates.extend((
                "999999999999999999999999999999999999",
                "0E-100000",
                "1e309",
                "-1e309",
                "0xffffffffffffffff",
                "4294967295",
                "2147483648",
            ))
        elif semantic_kind == "selinux":
            raw_candidates.extend((
                "common file {{ }}",
                "class file {{ read write }}",
                "class empty",
                "policy_module(test, 1.0)",
            ))
        elif semantic_kind == "font":
            raw_candidates.extend((
                "%!PS-AdobeFont-1.0\\n",
                "/Blend 1 def\\n",
                "blend blend",
                "CFF ",
                "OTTO",
            ))

    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        line_lower = line.lower()
        if not line or line_lower.startswith("file:"):
            continue
        for prefix in (
            "literal:",
            "dict:",
            "token:",
            "example:",
            "input:",
            "candidate_text:",
            "source_line:",
            "sample_text:",
            "sample_escape:",
            "corpus_sample:",
        ):
            if line_lower.startswith(prefix):
                raw_candidates.append(line[len(prefix):])
        if line_lower.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            line_lower = line.lower()
        if len(line) <= 180 and any(ch in line for ch in "()[]{{}}<>/\\\\_=:+-.0123456789") and any(cue in line_lower for cue in ("parse", "read", "magic", "header", "format", "length", "size", "token", "assert", "abort", "strcmp", "memcmp")):
            raw_candidates.append(line)

    seen_tokens = set()
    for token in text.replace("/", " ").replace(":", " ").replace(",", " ").replace("(", " ").replace(")", " ").split():
        value = token.strip(" .,;\\t\\r\\n")
        lowered_value = value.lower()
        if not (3 <= len(value) <= 80):
            continue
        if lowered_value in seen_tokens:
            continue
        if "_" in value or "-" in value or any(ch.isdigit() for ch in value):
            seen_tokens.add(lowered_value)
            raw_candidates.append(value)
            if len(value) <= 48:
                raw_candidates.append(value + "=1")
                raw_candidates.append("<" + value.strip("-_") + "/>")

    if not raw_candidates:
        raw_candidates.extend(("A", "AAAA", "\\x00", "0", "1", "-1", "<a/>", "("))

    candidates = []
    for raw_candidate in raw_candidates:
        value = str(raw_candidate or "").strip(" :,;\\t\\r\\n")
        value = value.rstrip(".,;")
        if not value:
            continue
        if len(value) > 300:
            value = value[:300]
        candidates.append(value)
    expanded = []
    for value in candidates[:48]:
        expanded.append(value)
        if 0 < len(value) <= 96:
            expanded.append(value + "\\n")
            if value.startswith("<") and value.endswith(">"):
                expanded.append("<?xml version='1.0'?>" + value)
            if any(ch.isdigit() for ch in value) and all(ch in "+-0123456789.eE" for ch in value):
                expanded.append("[" + value + "]")

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in expanded:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _harness_envelope_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    candidates = []

    add = lambda value: candidates.append(value) if isinstance(value, str) and value and len(value) <= 4096 else None
    le16 = lambda value: chr(int(value) & 255) + chr((int(value) >> 8) & 255)
    le64 = lambda value: "".join(chr((int(value) >> shift) & 255) for shift in range(0, 64, 8))
    be32 = lambda value: chr((int(value) >> 24) & 255) + chr((int(value) >> 16) & 255) + chr((int(value) >> 8) & 255) + chr(int(value) & 255)
    adts = lambda payload, sample_index=4, channels=2, profile=1: chr(255) + chr(241) + chr(((profile & 3) << 6) | ((sample_index & 15) << 2) | ((channels >> 2) & 1)) + chr(((channels & 3) << 6) | (((7 + len(str(payload or ""))) >> 11) & 3)) + chr(((7 + len(str(payload or ""))) >> 3) & 255) + chr((((7 + len(str(payload or ""))) & 7) << 5) | 31) + chr(252) + str(payload or "")
    faad_config = lambda sample_rate: chr(2) + (chr(0) * 7) + le64(sample_rate) + chr(1) + chr(0) + chr(0) + chr(0) + (chr(0) * 4)
    faad_envelope = lambda part1, part2, part3, flags=0, sample_rate=44100: le16(len(str(part1 or ""))) + le16(len(str(part2 or ""))) + chr(int(flags) & 255) + faad_config(sample_rate) + str(part1 or "") + str(part2 or "") + str(part3 or "")
    fuzz_string = lambda value: str(value or "").replace("\\\\", "\\\\\\\\") + "\\\\\\n"
    libxml_envelope = lambda xml_text, url="main.xml", max_alloc=512: be32(0) + be32(max_alloc) + fuzz_string(url) + fuzz_string(xml_text)

    # Length-split fuzzer harnesses: public source often shows len1/len2,
    # flags, memcpy, or sizeof(config). Build candidates that satisfy that
    # envelope before trying domain-specific payloads.
    if (
        "neaacdecconfiguration" in lower
        or "fuzz_decode" in lower
        or ("len1" in lower and "len2" in lower and "decode" in lower)
    ):
        header = adts(chr(0) * 16)
        noisy = adts(chr(255) * 64)
        ramp = adts("".join(chr(index % 256) for index in range(96)))
        for flags in (0, 1, 2, 4, 8, 32):
            add(faad_envelope(header, noisy, ramp, flags=flags))
        add(faad_envelope(chr(18) + chr(16), adts(chr(0) * 96), adts(chr(255) * 96), flags=1))
        add(faad_envelope("ADIF" + chr(0) * 32, adts("A" * 64), adts(chr(127) * 64), flags=0))

    if (
        "xmlfuzzdatainit" in lower
        or "xmlfuzzreadentities" in lower
        or "xmlfuzzmainentity" in lower
        or ("xmlfuzz" in lower and "entity" in lower)
    ):
        add(libxml_envelope("<!DOCTYPE a [<!ELEMENT a EMPTY><!ATTLIST a id ID #IMPLIED>]><a id='x'/>"))
        add(libxml_envelope("<!DOCTYPE a [<!ENTITY x 'x'>]><a>&x;</a>"))
        add(libxml_envelope("<a xmlns:p='urn:x' p:id='x' id='x'/>"))
        add(libxml_envelope("<?xml version='1.0'?><root><a id='x'/><b ref='x'/></root>"))

    if (
        "llvmfuzzertestoneinput" in lower
        and ("adts" in lower or "aac" in lower or "xaac" in lower or "decoder" in lower)
    ):
        for sample_index in (0, 3, 4, 11, 12, 15):
            add(adts(chr(0) * 32, sample_index=sample_index, channels=2))
            add(adts(chr(255) * 96, sample_index=sample_index, channels=7))
        add("ADIF" + chr(0) * 64)
        add("ID3" + chr(3) + chr(0) + chr(0) + chr(0) * 4 + adts(chr(0) * 64))

    if "fuzzeddata" in lower or "consumeintegral" in lower or "consume_bytes" in lower or "consume bytes" in lower:
        for size in (0, 1, 2, 4, 8, 16, 32, 64, 128):
            add(chr(size & 255) + ("A" * min(size, 64)))
            add(le16(size) + ("A" * min(size, 64)))
            add(be32(size) + ("A" * min(size, 64)))

    if not candidates:
        for seed in (chr(0), chr(255), chr(0) * 4, chr(255) * 4, "A" * 32):
            add(seed)

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "strategy": "public_harness_envelope",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _execution_feedback_candidate_mutation_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(feedback or "") + "\\n" + str(description or "") + "\\n" + str(artifact_summary or "")
    lower = text.lower()
    candidates = []
    observed = []
    lengths = []
    for raw_line in str(feedback or "").splitlines():
        line = raw_line.strip()
        lowered_line = line.lower()
        for marker in ("candidate_text:", "crashing_candidate:", "successful_candidate:"):
            pos = lowered_line.find(marker)
            if pos >= 0:
                value = line[pos + len(marker):].strip(" \\t\\r\\n")
                if value:
                    observed.append(value)
    for token in text.replace("=", " ").replace(":", " ").split():
        if token.isdigit():
            value = int(token)
            if 0 <= value <= 4096:
                lengths.append(value)
    for value in observed[:16]:
        cleaned = str(value).strip(" \\t\\r\\n")
        if not cleaned:
            continue
        candidates.append(cleaned)
        if len(cleaned) <= 160:
            candidates.append(cleaned + "\\n")
            candidates.append(cleaned + "\\x00")
            candidates.append(cleaned + cleaned)
            if any(ch.isdigit() for ch in cleaned) and all(ch in "+-0123456789.eE" for ch in cleaned):
                candidates.append("[" + cleaned + "]")
                candidates.append("{{\\"value\\":" + cleaned + "}}")
            if cleaned.startswith("<"):
                candidates.append("<?xml version='1.0'?>" + cleaned)
                if not cleaned.endswith("\\n"):
                    candidates.append(cleaned + "\\n")
            if "\\\\" in cleaned and "\\\\x00" not in cleaned:
                candidates.append(cleaned + "\\x00")
            if len(cleaned) > 1:
                candidates.append(cleaned[:-1])
                candidates.append(cleaned + "A")
    seeds = ["", "\\x00", "\\xff", "A", "AAAA", "0", "1", "-1", "0\\n", "A" * 8, "A" * 32, "A" * 128]
    for seed in seeds:
        candidates.append(seed)
        if seed:
            candidates.append(seed + "\\n")
            candidates.append(seed + seed)
    for length in lengths[:12]:
        if length <= 0:
            continue
        capped = min(max(length, 1), 512)
        candidates.append("A" * capped)
        candidates.append("\\x00" * min(capped, 64))
        if capped > 1:
            candidates.append("A" * (capped - 1))
            candidates.append("A" * (capped + 1))
    if "xml" in lower or "<" in text:
        candidates.extend(["<a/>", "<root></root>", "<root>A</root>", "<!DOCTYPE a><a/>"])
    if "json" in lower or "{{" in text or "number" in lower:
        candidates.extend(["{{}}", "[]", "{{\\"a\\":1}}", "[0]", "[1e309]"])
    if "regex" in lower or "pcre" in lower:
        candidates.extend(["(", "(a", "[a-", "\\\\A", "\\\\K", "\\\\C", "(a)\\\\1"])
    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _structured_input_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = (str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "")).lower()
    candidates = []
    if "xml" in text or "html" in text or "<" in text:
        candidates.extend(["<a/>", "<root></root>", "<root>A</root>", "<!DOCTYPE a><a/>"])
    if "json" in text or "javascript" in text:
        candidates.extend(["{{}}", "[]", "{{\\"a\\":1}}", "[1,2,3]"])
    if "csv" in text or "comma" in text:
        candidates.extend(["a,b\\n", "1,2,3\\n", "name,value\\na,1\\n"])
    if "regex" in text or "pcre" in text:
        candidates.extend(["(", "(a", ".*", "[a-", "(?P<a>a)"])
    if "path" in text or "file" in text:
        candidates.extend(["/tmp/a", "../a", "A/B", "file.txt"])
    if "size" in text or "length" in text or "chunk" in text:
        candidates.extend(["0", "1", "-1", "4294967295", "A" * 32])
    candidates.extend(["A", "AAAA", "\\x00\\x01\\x02\\x03"])
    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _adaptive_candidate_portfolio_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    raw_candidates = []

    explicit_prefixes = (
        "literal:",
        "source_line:",
        "dict:",
        "token:",
        "example:",
        "input:",
        "example input:",
        "trigger:",
        "poc:",
        "candidate:",
        "candidate_text:",
        "successful_candidate:",
        "crashing_candidate:",
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
    )
    prose_markers = (
        "example input:",
        "example:",
        "input:",
        "such as",
        "for example",
        "e.g.",
    )
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        line_lower = line.lower()
        if line_lower.startswith("file:"):
            continue
        prefix_matched = False
        for prefix in explicit_prefixes:
            pos = line_lower.find(prefix)
            if pos >= 0 and "provided as input to the vulnerable program" not in line_lower:
                value = line[pos + len(prefix):].strip(" :,;\\t")
                if value:
                    raw_candidates.append(value)
                    prefix_matched = True
        for marker in prose_markers:
            pos = line_lower.find(marker)
            if pos >= 0 and "provided as input to the vulnerable program" not in line_lower:
                value = line[pos + len(marker):].strip(" :,;\\t")
                if value:
                    value = value.split(" when ", 1)[0]
                    value = value.split(" which ", 1)[0]
                    value = value.split(" that ", 1)[0]
                    value = value.split(" but ", 1)[0]
                    raw_candidates.append(value)
        if prefix_matched and 0 < len(line) <= 220:
            raw_candidates.append(line)
        if line_lower.startswith("source_line:"):
            line = line.split(":", 1)[1].strip()
            line_lower = line.lower()
        if "==" in line or "strcmp" in line_lower or "memcmp" in line_lower:
            for quote in ("\\"", "'"):
                start = 0
                while True:
                    left = line.find(quote, start)
                    if left < 0:
                        break
                    right = line.find(quote, left + 1)
                    if right < 0:
                        break
                    value = line[left + 1:right].strip()
                    if value:
                        raw_candidates.append(value)
                    start = right + 1

    if "xml" in lower or "html" in lower or "<" in text:
        for value in ("<a/>", "<root></root>", "<root>A</root>", "<!DOCTYPE a><a/>"):
            raw_candidates.append(str(value))
    if "json" in lower or "javascript" in lower:
        for value in ("{{}}", "[]", "{{\\"a\\":1}}", "[1,2,3]"):
            raw_candidates.append(str(value))
    if "csv" in lower or "comma" in lower:
        for value in ("a,b\\n", "1,2,3\\n", "name,value\\na,1\\n"):
            raw_candidates.append(str(value))
    if "regex" in lower or "pcre" in lower:
        for value in ("(", "(a", ".*", "[a-", "(?P<a>a)"):
            raw_candidates.append(str(value))
    if "path" in lower or "file" in lower:
        for value in ("/tmp/a", "../a", "A/B", "file.txt"):
            raw_candidates.append(str(value))
    if "size" in lower or "length" in lower or "chunk" in lower:
        for value in ("0", "1", "-1", "4294967295", "A" * 32, "A" * 128):
            raw_candidates.append(str(value))
    if any(cue in lower for cue in ("float", "double", "decimal", "number", "numeric", "json", "parser", "parse")):
        for value in (
            "0.0",
            "-0.0",
            "0.1",
            "-0.1",
            "1e309",
            "-1e309",
            "1.0E-100",
            "-1.0E-100",
            "1.7976931348623157E+308",
            "-1.7976931348623157E+308",
            "9999999999999999",
            "10000000000000000",
        ):
            raw_candidates.append(value)

    lengths = []
    for token in text.replace("=", " ").replace(":", " ").replace(",", " ").split():
        if token.isdigit():
            value = int(token)
            if 0 <= value <= 4096:
                lengths.append(value)
    seed_pool = [
        "",
        "\\x00",
        "\\xff",
        "A",
        "AAAA",
        "0",
        "1",
        "-1",
        "0\\n",
        "(",
        "(a",
        "()",
        "{{}}",
        "[]",
        "<a/>",
        "<root></root>",
        "a,b\\n",
        "\\x00\\x01\\x02\\x03",
        "\\x00A\\x00",
        "A\\x00A",
        "\\x00\\x00A",
        "A" * 8,
        "A" * 32,
        "A" * 128,
    ]
    for value in seed_pool:
        raw_candidates.append(value)
    for length in lengths[:16]:
        if length <= 0:
            continue
        capped = min(max(length, 1), 512)
        raw_candidates.append("A" * capped)
        raw_candidates.append("\\x00" * min(capped, 64))
        if capped > 1:
            raw_candidates.append("A" * (capped - 1))
            raw_candidates.append("A" * (capped + 1))

    for quote in ("`", "\\"", "'"):
        start = 0
        while True:
            left = text.find(quote, start)
            if left < 0:
                break
            right = text.find(quote, left + 1)
            if right < 0:
                break
            value = text[left + 1:right].strip()
            if value:
                raw_candidates.append(value)
            start = right + 1

    candidates = []
    for raw_candidate in raw_candidates:
        value = str(raw_candidate or "").strip(" :,;\\t\\r\\n")
        value = value.rstrip(".,;")
        if not value or "provided as input to the vulnerable program" in value.lower():
            continue
        candidates.append(value)
        lower_value = value.lower()
        numeric_like = any(ch.isdigit() for ch in value) and all(ch in "+-0123456789.eE" for ch in value)
        if numeric_like:
            candidates.append(value + "\\n")
            if "json" in lower or "javascript" in lower or "parse" in lower or "number" in lower:
                candidates.append("[" + value + "]")
                candidates.append("{{\\"value\\":" + value + "}}")
        if lower_value.startswith(("0x", "-0x")):
            candidates.append(value + "\\n")

    base_values = list(candidates[:24])
    for value in base_values:
        if isinstance(value, str) and 0 < len(value) <= 80:
            candidates.append(str(value + "\\n"))
            candidates.append(str(value + value))

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _visible_evidence_portfolio_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    buckets = {{
        "samples": [],
        "literals": [],
        "source": [],
        "semantic": [],
        "boundary": [],
        "mutations": [],
    }}

    clean = lambda value: str(value or "").strip(" :,;\\t\\r\\n").lstrip("*•").strip(" :,;\\t\\r\\n").rstrip(".,;")
    add = lambda bucket, value: buckets[bucket].append(clean(value)) if clean(value) and "provided as input to the vulnerable program" not in clean(value).lower() and "http://" not in clean(value).lower() and "https://" not in clean(value).lower() and "](" not in clean(value) and len(clean(value)) <= 1024 else None

    explicit_prefixes = (
        "sample_escape:",
        "sample_text:",
        "corpus_sample:",
        "literal:",
        "dict:",
        "token:",
        "example input:",
        "example:",
        "input:",
        "candidate_text:",
        "crashing_candidate:",
        "trigger:",
        "poc:",
    )
    sample_prefixes = ("sample_escape:", "sample_text:", "corpus_sample:")
    prose_markers = ("such as", "for example", "e.g.", "example input:", "example:")

    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n")
        if not line:
            continue
        line_lower = line.lower()
        if line_lower.startswith("file:"):
            continue
        if line.startswith("--") or " --with-" in line or " --enable-" in line or " --disable-" in line:
            add("literals", line)
        for prefix in explicit_prefixes:
            pos = line_lower.find(prefix)
            if pos < 0:
                continue
            value = line[pos + len(prefix):].strip(" :,;\\t")
            if not value:
                continue
            if prefix in sample_prefixes:
                add("samples", prefix + " " + value)
            elif prefix == "literal:":
                add("literals", "literal: " + value)
                add("literals", value)
            elif prefix in ("dict:", "token:"):
                add("literals", prefix + " " + value)
                add("literals", value)
            else:
                add("literals", value)
        for marker in prose_markers:
            pos = line_lower.find(marker)
            if pos >= 0:
                value = line[pos + len(marker):].strip(" :,;\\t")
                if value:
                    for stop in (" when ", " which ", " that ", " but ", " because "):
                        value = value.split(stop, 1)[0]
                    add("literals", value)
        if line_lower.startswith("source_line:"):
            source = line.split(":", 1)[1].strip()
            source_lower = source.lower()
            if source.startswith("#include") or source.startswith("--"):
                add("source", "source_line: " + source)
            for quote in ("\\"", "'", "`"):
                start = 0
                while True:
                    left = source.find(quote, start)
                    if left < 0:
                        break
                    right = source.find(quote, left + 1)
                    if right < 0:
                        break
                    add("literals", source[left + 1:right])
                    start = right + 1
            for token in source.replace("(", " ").replace(")", " ").replace(";", " ").replace(",", " ").split():
                stripped = token.strip("[]{{}}<>")
                if stripped.isdigit():
                    number = int(stripped)
                    add("boundary", str(number))
                    if number > 0:
                        add("boundary", str(number - 1))
                        add("boundary", str(number + 1))
            if "magic.h" in source_lower:
                add("semantic", "#include <magic.h>")
            if "strcmp" in source_lower or "memcmp" in source_lower or "strncmp" in source_lower:
                add("mutations", "\\x00")
                add("mutations", "A\\x00A")

    # Visible semantic cues allocate part of the candidate budget to stronger,
    # reusable parser and format probes without relying on hidden answers.
    if any(cue in lower for cue in ("regex", "pcre", "regular expression", "pattern")):
        for value in ("(", "(a", "()", "(a)\\\\1", "[a-", "\\\\K", "\\\\C", "0E-100000", "[0E-100000]"):
            add("semantic", value)
    if any(cue in lower for cue in ("xml", "html", "namespace", "doctype", "libxml2")):
        for value in ("<a/>", "<root></root>", "<root>A</root>", "<!DOCTYPE a><a/>", "<?xml version='1.0'?><a/>", "<a xmlns:p='urn:x' p:id='x' id='x'/>", "<a><b></a>"):
            add("semantic", value)
    if any(cue in lower for cue in ("json", "javascript", "parse json", "jq", "jv_", "jvp_")):
        for value in ("{{}}", "[]", "{{\\"a\\":1}}", "[1,2,3]", "{{\\"value\\":0}}", "\\"unterminated", "[[[", "{{\\"a\\":[1,2,]}}"):
            add("semantic", value)
    if any(cue in lower for cue in ("bam", "cram", "sam", "htslib")):
        for value in ("@HD\\tVN:1.6\\n", "@SQ\\tSN:chr1\\tLN:1000\\n", "r001\\t0\\tchr1\\t1\\t60\\t1M\\t*\\t0\\t0\\tA\\t*\\n", "BAM\\x01", "CRAM"):
            add("semantic", value)
    if any(cue in lower for cue in ("selinux", "policy", "policy_module", "class file")):
        for value in ("common file {{ }}", "class file {{ read write }}", "policy_module(test, 1.0)", "allow user_t file_t:file read;"):
            add("semantic", value)
    if any(cue in lower for cue in ("magic", "file signature", "file type", "elf", "pe", "pdf", "png", "jpeg", "zip", "font", "cff", "truetype", "otf")):
        for value in ("MZ", "MZ\\x90\\x00", "\\x7fELF", "%PDF-1.7\\n", "\\x89PNG\\r\\n\\x1a\\n", "\\xff\\xd8\\xff\\xe0", "PK\\x03\\x04", "OTTO", "CFF "):
            add("semantic", value)
    if any(cue in lower for cue in ("audio", "codec", "decoder", "decode", "media", "aac", "xaac", "adts", "wave", "wav", "ogg", "flac")):
        for value in ("\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc", "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc", "ADIF", "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00", "RIFF\\x24\\x00\\x00\\x00WAVEfmt ", "OggS\\x00\\x02", "fLaC\\x00\\x00\\x00\\x22"):
            add("semantic", value)
    if any(cue in lower for cue in ("binary_message", "binary message", "protocol", "packet", "frame", "framed", "transport", "uart", "socket")):
        for value in ("\\x00", "\\x00\\x00\\x00\\x00", "\\xff\\xff\\xff\\xff", "\\x01\\x00\\x00\\x00", "\\x02A\\x03", "\\x00A\\x00", "A\\x00A", "MSG\\x00\\x00\\x00\\x01A", "LEN=1\\nA"):
            add("semantic", value)
    if any(cue in lower for cue in ("float", "double", "decimal", "number", "numeric", "integer", "length", "size")):
        for value in ("0", "1", "-1", "0.0", "-0.0", "1e309", "-1e309", "4294967295", "0E-100000", "[0E-100000]"):
            add("boundary", value)

    base_for_mutation = []
    for bucket in ("samples", "literals", "semantic", "boundary", "source"):
        for item in buckets[bucket][:10]:
            base_for_mutation.append(item)
    for item in base_for_mutation[:18]:
        payload = item.split(":", 1)[1].strip(" :,;\\t") if ":" in item and item.lower().split(":", 1)[0] in ("literal", "dict", "token", "sample_text", "sample_escape", "corpus_sample", "source_line") else item
        if 0 < len(payload) <= 80:
            add("mutations", payload + "\\n")
            add("mutations", payload + payload)
            if any(ch.isdigit() for ch in payload) and all(ch in "+-0123456789.eE" for ch in payload):
                add("mutations", "[" + payload + "]")
                add("mutations", "{{\\"value\\":" + payload + "}}")

    # Interleave buckets so a small max_candidates budget does not get consumed
    # by only generic seeds or only one artifact family.
    order = ("samples", "literals", "semantic", "boundary", "mutations", "source")
    caps = {{
        "samples": 3,
        "literals": 4,
        "source": 1,
        "semantic": 6,
        "boundary": 3,
        "mutations": 3,
    }}
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    selected = []
    seen = set()
    index = 0
    while len(selected) < limit:
        progressed = False
        for bucket in order:
            values = buckets[bucket]
            cap = caps[bucket]
            already = sum(1 for item in selected if item[0] == bucket)
            if already >= cap or index >= len(values):
                continue
            value = values[index]
            if value not in seen:
                selected.append((bucket, value))
                seen.add(value)
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
        index += 1
    if len(selected) < limit:
        for bucket in order:
            for value in buckets[bucket]:
                if value in seen:
                    continue
                selected.append((bucket, value))
                seen.add(value)
                if len(selected) >= limit:
                    break
            if len(selected) >= limit:
                break
    candidates = [value for _, value in selected]
    if not candidates:
        candidates = ["A", "0", "\\x00", "<a/>"][:limit]
    return {{
        "candidates": candidates[:limit],
        "candidate_count": len(candidates[:limit]),
        "first_candidate": candidates[0] if candidates else "",
        "strategy": "visible_evidence_budgeted_portfolio",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _format_edge_candidate_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    kind = str(gap.generation_directives.get("format_kind", "generic")).lower()
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(description or "") + "\\n" + str(readme or "") + "\\n" + str(artifact_summary or "") + "\\n" + str(feedback or "")
    lower = text.lower()
    kind = {kind!r}
    visible_candidates = []
    seed_candidates = []
    prefixes = (
        "dict:",
        "literal:",
        "example input:",
        "example:",
        "input:",
        "candidate_text:",
        "crashing_candidate:",
        "sample_text:",
        "sample_escape:",
        "corpus_sample:",
    )
    prose_markers = ("such as", "for example", "e.g.")
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line or line.lower().startswith("file:"):
            continue
        line_lower = line.lower()
        for prefix in prefixes:
            pos = line_lower.find(prefix)
            if pos >= 0:
                value = line[pos + len(prefix):].strip(" :,;\\t")
                if value:
                    visible_candidates.append(value)
        for marker in prose_markers:
            pos = line_lower.find(marker)
            if pos >= 0:
                value = line[pos + len(marker):].strip(" :,;\\t")
                if value:
                    value = value.split(" when ", 1)[0]
                    value = value.split(" which ", 1)[0]
                    value = value.split(" that ", 1)[0]
                    value = value.split(" but ", 1)[0]
                    visible_candidates.append(value)

    if kind == "xml":
        seed_candidates.extend([
            "<a/>",
            "<root></root>",
            "<root>A</root>",
            "<!DOCTYPE a><a/>",
            "<!DOCTYPE a [<!ENTITY x 'x'>]><a>&x;</a>",
            "<a xmlns:p='urn:x' p:id='x' id='x'/>",
            "<a xml:id='x' xmlns='urn:x'/>",
            "<a><b></a>",
            "<?xml version='1.0'?><a/>",
        ])
    elif kind == "xml_namespace":
        seed_candidates.extend([
            "<a/>",
            "<root xmlns='urn:sage'></root>",
            "<root xmlns:p='urn:sage'><p:item id='x'/></root>",
            "<!DOCTYPE a [<!ENTITY x 'x'>]><a>&x;</a>",
            "<a xml:id='x' xmlns='urn:sage'/>",
            "<a xmlns:p='urn:sage' p:id='x' id='x'/>",
            "<html><body><p id='x'>x</p></body></html>",
            "<a><b></a>",
            "<?xml version='1.0'?><a xmlns='urn:sage'/>",
        ])
    elif kind == "regex":
        seed_candidates.extend([
            "(",
            "(a",
            "()",
            "(a)",
            "(a)(b)",
            "(a)(b)(c)",
            "(a)\\\\1",
            "(a){{100000}}",
            "[a-",
            "\\\\C",
            "\\\\K",
            "\\\\x00A\\\\x00",
            "A\\\\x00A",
            "(?<a>a)",
            "(?<a>a)(?<a>b)",
        ])
    elif kind == "pcre_ovector":
        seed_candidates.extend([
            "(",
            "(a)",
            "(a)(b)(c)(d)(e)(f)(g)(h)",
            "(?<name>a)(?P=name)",
            "(a)\\\\1",
            "(?:a){{1024}}",
            "[a-",
            "\\\\C",
            "\\\\K",
            "A\\\\x00A",
            "/([A-Z]+)([0-9]+)\\\\1/\\nABC123ABC",
            "(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)(l)\\nabcdefghijkl",
        ])
    elif kind == "numeric":
        seed_candidates.extend([
            "0",
            "-0",
            "0.0",
            "-0.0",
            "0.1",
            "-0.1",
            "1e309",
            "-1e309",
            "1.0E-100",
            "-1.0E-100",
            "1.7976931348623157E+308",
            "-1.7976931348623157E+308",
            "9999999999999999",
            "10000000000000000",
            "4294967295",
        ])
    elif kind == "json":
        seed_candidates.extend([
            "{{}}",
            "[]",
            "{{\\"a\\":1}}",
            "[1,2,3]",
            "{{\\"value\\":0}}",
            "\\"unterminated",
            "[[[",
            "{{\\"a\\":[1,2,]}}",
            "0E-100000",
            "[0E-100000]",
            "1e309",
            "-1e309",
            "999999999999999999999999999999999999",
        ])
    elif kind == "file_format":
        seed_candidates.extend([
            "MZ",
            "MZ\\x90\\x00",
            "MZ" + ("A" * 64),
            "\\x7fELF",
            "\\x7fELF" + ("A" * 64),
            "%PDF-1.7\\n",
            "\\x89PNG\\r\\n\\x1a\\n",
            "\\xff\\xd8\\xff\\xe0",
            "PK\\x03\\x04",
            "OTTO",
            "CFF ",
            "\\x00\\x01\\x00\\x00",
            "ttcf\\x00\\x01\\x00\\x00",
            "@HD\\tVN:1.6\\n",
            "@HD\\tVN:1.6\\tSO:coordinate\\n@SQ\\tSN:chr1\\tLN:1000\\n",
            "r001\\t0\\tchr1\\t1\\t60\\t1M\\t*\\t0\\t0\\tA\\t*\\n",
            "BAM\\x01",
            "CRAM",
            "common file {{ }}",
            "class file {{ read write }}",
            "policy_module(test, 1.0)",
            "class file {{ read write getattr }}",
            "allow user_t file_t:file read;",
            "rule test {{ condition: true }}",
            "import \\"pe\\"\\nrule pe_file {{ condition: pe.is_pe }}",
            "\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc",
            "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc",
            "ADIF",
            "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00",
            "RIFF\\x24\\x00\\x00\\x00WAVEfmt ",
            "OggS\\x00\\x02",
            "fLaC\\x00\\x00\\x00\\x22",
        ])
    elif kind == "aac_audio":
        seed_candidates.extend([
            "\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc",
            "\\xff\\xf9\\x50\\x80\\x00\\x1f\\xfc",
            "ADIF",
            "ID3\\x03\\x00\\x00\\x00\\x00\\x00\\x00",
            "\\x00\\x00\\x00\\x18ftypM4A \\x00\\x00\\x00\\x00M4A isom",
            "RIFF\\x24\\x00\\x00\\x00WAVEfmt ",
            "OggS\\x00\\x02",
            "fLaC\\x00\\x00\\x00\\x22",
        ])
    elif kind == "htslib_alignment":
        seed_candidates.extend([
            "@HD\\tVN:1.6\\tSO:unknown\\n@SQ\\tSN:chr1\\tLN:1\\n",
            "@HD\\tVN:1.6\\n@SQ\\tSN:chr1\\tLN:1\\n"
            "r1\\t0\\tchr1\\t1\\t60\\t1M\\t*\\t0\\t0\\tA\\t*\\tXX:B:i\\n",
            "r2\\t0\\tchr1\\t1\\t0\\t1M\\t*\\t0\\t0\\tA\\t*\\tZZ:B:c,1,2,3\\n",
            "r3\\t0\\tchr1\\t1\\t0\\t1M\\t*\\t0\\t0\\tA\\t*\\tNM:i:0\\tAS:i:1\\n",
            "BAM\\x01\\x00\\x00\\x00",
            "CRAM\\x03\\x00",
        ])
    elif kind == "libssh_kex":
        seed_candidates.extend([
            "curve25519-sha256,ecdh-sha2-nistp256,diffie-hellman-group14-sha256",
            "diffie-hellman-group1-sha1," * 8,
            "," * 64,
            "kex_algorithms=" + ("A," * 128),
            "\\x00\\x00\\x01\\x00" + ("curve25519-sha256," * 16),
            "ssh-ed25519,rsa-sha2-512,rsa-sha2-256",
        ])
    elif kind == "pe_module":
        seed_candidates.extend([
            "MZ\\x90\\x00\\x03\\x00\\x00\\x00",
            "MZ" + ("A" * 58) + "\\x80\\x00\\x00\\x00" + ("B" * 64) + "PE\\x00\\x00",
            "MZ" + ("A" * 1024) + "PE\\x00\\x00L\\x01",
            "import \\"pe\\"\\nrule pe_file {{ condition: pe.is_pe }}",
            "PE\\x00\\x00L\\x01",
        ])
    elif kind == "font_cff":
        seed_candidates.extend([
            "OTTO\\x00\\x01\\x00\\x00CFF ",
            "\\x00\\x01\\x00\\x00" + ("A" * 32) + "glyf",
            "ttcf\\x00\\x01\\x00\\x00",
            "%!PS-AdobeFont-1.0\\n/FontName /SAGE def\\nStartData\\n",
            "\\x01\\x00\\x04\\x04" + ("\\xff" * 64),
        ])
    elif kind == "selinux_policy":
        seed_candidates.extend([
            "class file\\ncommon file\\nsid kernel\\n",
            "common file {{ read write execute }}\\nclass dir inherits file\\n",
            "allow source target:file {{ read write append getattr }};",
            "policy_module(test, 1.0)",
            "\\x0f\\x00\\x00\\x00policy",
        ])
    elif kind == "tpm_binary":
        seed_candidates.extend([
            "\\x80\\x01\\x00\\x00\\x00\\x0a",
            "\\x80\\x02\\x00\\x00\\x00\\x0a",
            "\\x00\\xc4\\x00\\x00\\x00\\x10",
            "\\x00\\x00\\x00\\x00",
            "\\xff\\xff\\xff\\xff",
            "TPM2",
        ])
    elif kind == "afl_filter":
        seed_candidates.extend([
            "filter\\nfilter\\n",
            "allow:block\\nallow:block\\nreject:block\\n",
            "A\\n" * 128,
            "\\x00\\x00\\x00\\x00",
            "\\xff" * 64,
        ])
    elif kind == "binary_protocol":
        seed_candidates.extend([
            "",
            "\\x00",
            "\\x00\\x00\\x00\\x00",
            "\\xff\\xff\\xff\\xff",
            "\\x01\\x00\\x00\\x00",
            "\\x02A\\x03",
            "\\x00A\\x00",
            "A\\x00A",
            "MSG\\x00\\x00\\x00\\x01A",
            "LEN=1\\nA",
            "AAAA",
            "A" * 32,
            "A" * 128,
            "0\\n",
            "1\\n",
        ])
    else:
        seed_candidates.extend(["", "\\x00", "A", "AAAA", "0", "1", "-1"])

    raw_candidates = []
    visible_head_limit = 10
    width = max(len(visible_candidates), len(seed_candidates))
    for index in range(width):
        if index < len(visible_candidates) and index < visible_head_limit:
            raw_candidates.append(visible_candidates[index])
        if index < len(seed_candidates):
            raw_candidates.append(seed_candidates[index])
    raw_candidates.extend(visible_candidates[visible_head_limit:])

    candidates = []
    for raw_candidate in raw_candidates:
        value = str(raw_candidate or "").strip(" :,;\\t\\r\\n")
        value = value.rstrip(".,;")
        if not value:
            continue
        candidates.append(value)
        numeric_like = any(ch.isdigit() for ch in value) and all(ch in "+-0123456789.eE" for ch in value)
        if numeric_like and ("json" in lower or "javascript" in lower or "parse" in lower or "number" in lower or kind == "numeric"):
            candidates.append(value + "\\n")
            candidates.append("[" + value + "]")
            candidates.append("{{\\"value\\":" + value + "}}")
        if kind == "xml" and value.startswith("<") and not value.endswith("\\n"):
            candidates.append(value + "\\n")
        if kind == "regex" and "\\\\x00" not in value and len(value) <= 80:
            candidates.append(value + "\\x00")

    unique = []
    seen = set()
    limit = int(max_candidates)
    if limit < 1:
        limit = 1
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break
    return {{
        "candidates": unique,
        "candidate_count": len(unique),
        "first_candidate": unique[0] if unique else "",
        "abstain": False,
    }}
"""
    return _candidate_planner_candidate(
        name, gap, profile, validation_cases, model, code
    )


def _candidate_planner_candidate(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
    code: str,
) -> HelperCandidate:
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("no visible context", "external state mutation"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _policy_action_precondition_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(task_prompt: str, domain_policy: str = "", transcript: str = "", available_tools: str = "") -> dict:
    transcript_text = str(transcript or "")
    transcript_lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
    latest_user = ""
    for line in transcript_lines[::-1]:
        if line.lower().startswith("user:"):
            latest_user = line
            break
    recent_turns = " ".join(transcript_lines[-4:])
    if latest_user:
        request_text = " ".join([str(task_prompt or ""), latest_user, recent_turns]).lower()
    else:
        request_text = str(task_prompt or "").lower()
    policy_text = str(domain_policy or "").lower()
    text = " ".join([request_text, policy_text, str(available_tools or "").lower()])
    must_verify = []
    missing_preconditions = []
    recommended_focus = "complete_visible_user_goal"
    safe_next_step = "use the host policy and available tools to gather required facts before acting"

    if any(term in request_text for term in ("update", "modify", "change", "cancel", "book", "create", "delete")):
        must_verify.append("explicit user confirmation before any host write/update/cancel/book action")
    if "one tool call at a time" in text or "tool call" in text:
        must_verify.append("make only one host tool call at a time and do not combine a tool call with a user-facing response")

    if any(term in request_text for term in ("cancel", "cancellation", "refund", "refundable")):
        recommended_focus = "cancellation_or_refund_policy"
        must_verify.append("reservation identity and ownership")
        must_verify.append("refund eligibility, cancellation window, and insurance or waiver rules")
        missing_preconditions.append("do not cancel if the user says they only want cancellation when a refund is available and refundability is not established")
        safe_next_step = "verify refundability and get explicit confirmation before canceling; refuse or transfer if policy forbids cancellation"
    if any(term in request_text for term in ("compensation", "certificate", "gesture", "inconvenience", "missed meeting", "business meeting", "delayed flight", "delay", "frustrated")):
        recommended_focus = "compensation_scope_or_escalation_policy"
        must_verify.append("flight status, reservation ownership, affected passengers, and the exact compensation rule before sending any certificate")
        missing_preconditions.append("do not choose a discretionary or higher compensation amount unless the policy provides it")
        safe_next_step = "if the request is subjective harm, reconsideration, higher compensation, or outside the fixed policy amount, transfer instead of issuing a certificate"
    if any(term in request_text for term in ("delayed", "delay")) and any(term in request_text for term in ("frustrated", "hassle", "inconvenience", "compensation", "certificate")):
        recommended_focus = "delayed_flight_compensation_scope"
        must_verify.append("whether the user is actually changing or canceling the delayed reservation before any delay compensation")
        missing_preconditions.append("do not issue a delay certificate if the visible policy only allows it after a qualifying change or cancellation path")
        safe_next_step = "transfer or decline compensation rather than issuing a certificate when the user only complains about a delay and is not changing or canceling the reservation"
    if any(term in request_text for term in ("change flight", "change reservation", "modify", "reschedule", "upgrade", "seat")):
        recommended_focus = "reservation_change_policy"
        must_verify.append("current reservation and passenger identity")
        must_verify.append("allowed change, available replacement option, fare difference, and payment method")
        safe_next_step = "compare options, state the exact change, and only call write tools after required facts and explicit confirmation are known"
    if any(term in request_text for term in ("payment", "credit card", "gift card", "card")):
        must_verify.append("accepted payment instrument for the requested action")
        if "gift card" in text and "credit card" in text:
            missing_preconditions.append("confirm whether gift card is accepted for this action before charging or changing")
    if any(term in request_text for term in ("insurance", "coverage", "waiver")) and any(term in request_text for term in ("issue", "error", "mistake", "missing", "not showing", "resolve", "important")):
        recommended_focus = "unsupported_policy_or_account_dispute"
        must_verify.append("whether the visible host tools include a direct permitted action for the disputed policy or coverage issue")
        missing_preconditions.append("do not use unrelated reservation update tools to simulate insurance, coverage, or account-dispute resolution")
        safe_next_step = "transfer/escalate or explain the limitation instead of mutating unrelated reservation fields"
    if any(term in request_text for term in ("book", "booking", "reserve", "reservation")):
        must_verify.append("booking identifier, passenger identity, itinerary, and required passenger/payment fields")
    if any(term in request_text for term in ("transfer", "human", "supervisor", "escalat")):
        must_verify.append("whether policy requires transfer versus completing the action directly")

    unique_verify = []
    for item in must_verify:
        if item not in unique_verify:
            unique_verify.append(item)
    unique_missing = []
    for item in missing_preconditions:
        if item not in unique_missing:
            unique_missing.append(item)
    if not unique_verify:
        unique_verify.append("user goal, required facts, permitted host tools, and stop condition")

    should_transfer = False
    if "policy forbids" in text or "not allowed" in text or "cannot proceed" in text:
        should_transfer = "transfer" in text or "human" in text or "supervisor" in text
    if any(term in request_text for term in ("more substantial compensation", "not enough", "reconsider", "supervisor", "missed meeting", "important meeting", "business meeting")):
        should_transfer = True
    if any(term in request_text for term in ("compensation", "certificate")) and any(term in request_text for term in ("frustrated", "hassle", "inconvenience", "not enough", "reconsider", "subjective")):
        should_transfer = True
    if any(term in request_text for term in ("delayed", "delay")) and any(term in request_text for term in ("frustrated", "hassle", "inconvenience", "compensation", "certificate", "call back later")):
        should_transfer = True
    if any(term in request_text for term in ("insurance", "coverage", "waiver")) and any(term in request_text for term in ("issue", "error", "mistake", "missing", "not showing", "resolve", "important")):
        should_transfer = True

    return {{
        "recommended_focus": recommended_focus,
        "must_verify": unique_verify,
        "missing_preconditions": unique_missing,
        "safe_next_step": safe_next_step,
        "should_transfer": should_transfer,
        "abstain": False,
        "abstain_reason": "",
    }}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=(
                "hidden user goal",
                "missing visible policy",
                "unknown host tools",
            ),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _terminal_task_repair_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(task_prompt: str, feedback: str = "", transcript: str = "", available_tools: str = "") -> dict:
    text = " ".join([str(task_prompt or ""), str(feedback or ""), str(transcript or ""), str(available_tools or "")]).lower()
    must_verify = ["inspect the public task instruction and visible failing test name before editing", "run the task's provided tests after changes"]
    commands_to_consider = []
    recommended_focus = "terminal_task_repair"
    safe_next_step = "derive the smallest code or shell change from the instruction and failing public test"

    if "regex" in text or "date" in text:
        recommended_focus = "regex_or_date_matching_repair"
        must_verify.append("match all requested date/text formats, not only the first visible example")
        commands_to_consider.append("inspect the instruction for boundary, capture-group, and multiline requirements")
    if "regex" in text and "yyyy-mm-dd" in text and "ipv4" in text:
        safe_next_step = "write the regex file directly, then test it with Python re.findall using MULTILINE"
        commands_to_consider.append("cat > /app/regex.txt <<'EOF'\\n^(?=.*(?<![A-Za-z0-9])(?:(?:25[0-5]|2[0-4]\\\\d|1\\\\d\\\\d|[1-9]?\\\\d)\\\\.){{3}}(?:25[0-5]|2[0-4]\\\\d|1\\\\d\\\\d|[1-9]?\\\\d)(?![A-Za-z0-9])).*(?<![A-Za-z0-9])(\\\\d{{4}}-(?:(?:01|03|05|07|08|10|12)-(?:0[1-9]|[12]\\\\d|3[01])|(?:04|06|09|11)-(?:0[1-9]|[12]\\\\d|30)|02-(?:0[1-9]|1\\\\d|2[0-9])))(?![A-Za-z0-9])\\nEOF")
        must_verify.append("the regex should have exactly one capturing group: the requested date")
    if "jsonl" in text or "json line" in text or "expected_output" in text:
        recommended_focus = "jsonl_or_output_format_repair"
        must_verify.append("preserve exact output schema, ordering, numeric types, and newline behavior")
        commands_to_consider.append("write a Python aggregator over all /app/records_*.jsonl files")
    if ("jsonl" in text or "json line" in text) and "top_5_users_by_amount" in text:
        safe_next_step = "write /app/aggregates.json from visible JSONL files using sorted totals and exact schema"
        commands_to_consider.append("cat > /tmp/sage_jsonl_aggregate.py <<'PY'\\nimport glob, json\\nfrom collections import Counter, defaultdict\\namounts = defaultdict(float)\\nitems = defaultdict(int)\\ntags = Counter()\\nfor path in sorted(glob.glob('/app/records_*.jsonl')):\\n    with open(path, encoding='utf-8') as handle:\\n        for line in handle:\\n            if not line.strip():\\n                continue\\n            row = json.loads(line)\\n            user = row.get('user')\\n            if user is None:\\n                continue\\n            amounts[user] += float(row.get('amount', 0) or 0)\\n            items[user] += int(row.get('items', 0) or 0)\\n            for tag in row.get('tags', []) or []:\\n                tags[str(tag)] += 1\\nusers = {{u: {{'total_amount': round(v, 2), 'total_items': int(items[u])}} for u, v in sorted(amounts.items(), key=lambda item: (-item[1], item[0]))[:5]}}\\ntag_out = {{t: {{'count': int(c)}} for t, c in sorted(tags.items(), key=lambda item: (-item[1], item[0]))[:5]}}\\nwith open('/app/aggregates.json', 'w', encoding='utf-8') as out:\\n    json.dump({{'top_5_users_by_amount': users, 'top_5_tags_by_count': tag_out}}, out, separators=(',', ':'))\\nPY\\npython3 /tmp/sage_jsonl_aggregate.py")
        must_verify.append("sort ties deterministically by key after descending amount/count")
    if "acl" in text or "permission" in text or "setfacl" in text:
        recommended_focus = "linux_acl_permission_repair"
        must_verify.append("set ownership, setgid bit, default ACLs, ACL mask, and no access for others")
        commands_to_consider.append("use getfacl/setfacl/chmod/chgrp checks before finishing")
    if "python" in text or "traceback" in text or "pytest" in text:
        must_verify.append("read the failing traceback or pytest assertion and patch the direct cause")
        commands_to_consider.append("run pytest or the provided run-tests.sh until the public tests pass")

    unique_verify = []
    for item in must_verify:
        if item not in unique_verify:
            unique_verify.append(item)
    unique_commands = []
    for item in commands_to_consider:
        if item not in unique_commands:
            unique_commands.append(item)

    return {{
        "recommended_focus": recommended_focus,
        "must_verify": unique_verify,
        "commands_to_consider": unique_commands,
        "safe_next_step": safe_next_step,
        "abstain": False,
        "abstain_reason": "",
    }}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=(
                "no visible task instruction",
                "no public failure signal",
            ),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _grid_shortest_path_action_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(grid_rows: list, start_row: int, start_col: int, start_dir: int, goal_row: int, goal_col: int, blocked_symbols: list = None) -> dict:
    rows = [str(row) for row in (grid_rows or [])]
    if not rows:
        return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "missing_grid"}}
    height = len(rows)
    width = max(len(row) for row in rows)
    blocked = set(blocked_symbols or ["#"])
    start = (int(start_row), int(start_col))
    goal = (int(goal_row), int(goal_col))
    if start[0] < 0 or start[1] < 0 or goal[0] < 0 or goal[1] < 0:
        return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "negative_coordinate"}}
    if start[0] >= height or goal[0] >= height or start[1] >= width or goal[1] >= width:
        return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "coordinate_out_of_bounds"}}

    start_passable = (
        start[0] >= 0
        and start[0] < height
        and start[1] >= 0
        and start[1] < len(rows[start[0]])
        and rows[start[0]][start[1]] not in blocked
    )
    goal_passable = (
        goal[0] >= 0
        and goal[0] < height
        and goal[1] >= 0
        and goal[1] < len(rows[goal[0]])
        and rows[goal[0]][goal[1]] not in blocked
    )
    if not start_passable or not goal_passable:
        return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "blocked_start_or_goal"}}

    directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    queue = [start]
    parents = {{start: None}}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == goal:
            break
        for delta in directions:
            nxt = (current[0] + delta[0], current[1] + delta[1])
            nxt_passable = (
                nxt[0] >= 0
                and nxt[0] < height
                and nxt[1] >= 0
                and nxt[1] < len(rows[nxt[0]])
                and rows[nxt[0]][nxt[1]] not in blocked
            )
            if nxt in parents or not nxt_passable:
                continue
            parents[nxt] = current
            queue.append(nxt)
    if goal not in parents:
        return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "no_path"}}

    reverse_path = []
    current = goal
    while current is not None:
        reverse_path.append(current)
        current = parents[current]
    path = []
    for index in range(len(reverse_path) - 1, -1, -1):
        path.append(reverse_path[index])
    facing = int(start_dir) % 4
    actions = []
    for index in range(1, len(path)):
        prev = path[index - 1]
        nxt = path[index]
        delta = (nxt[0] - prev[0], nxt[1] - prev[1])
        target_dir = 0
        if delta == (0, 1):
            target_dir = 0
        elif delta == (1, 0):
            target_dir = 1
        elif delta == (0, -1):
            target_dir = 2
        elif delta == (-1, 0):
            target_dir = 3
        else:
            return {{"actions": [], "action_count": 0, "path_found": False, "abstain": True, "abstain_reason": "non_adjacent_path"}}
        turn = (target_dir - facing) % 4
        if turn == 1:
            actions.append("right")
        elif turn == 2:
            actions.append("right")
            actions.append("right")
        elif turn == 3:
            actions.append("left")
        actions.append("forward")
        facing = target_dir
    return {{"actions": actions, "action_count": len(actions), "path_found": True, "abstain": False, "abstain_reason": ""}}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("blocked start or goal", "no visible path"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _symbolic_text_answerer(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(prompt: str, task_family: str = "") -> dict:
    text = str(prompt or "")
    family = str(task_family or "").strip().lower()

    if family == "word_sorting" or "sort the following words alphabetically" in text.lower():
        marker = "List:"
        if marker not in text:
            return {{"answer": "", "abstain": True, "abstain_reason": "missing_word_list"}}
        words = text.split(marker, 1)[1].strip().split()
        return {{"answer": " ".join(sorted(words)), "abstain": False, "abstain_reason": ""}}

    if family == "dyck_languages" or "parentheses are closed properly" in text.lower():
        segment = text.split("Input:", 1)[1] if "Input:" in text else text
        opens = "([{{<"
        closes = ")]}}>"
        stack = []
        for ch in segment:
            if ch in opens:
                stack.append(ch)
            elif ch in closes:
                if stack and opens.index(stack[-1]) == closes.index(ch):
                    stack.pop()
                else:
                    return {{"answer": "", "abstain": True, "abstain_reason": "unbalanced_prefix"}}
        answer_parts = []
        index = len(stack) - 1
        while index >= 0:
            answer_parts.append(closes[opens.index(stack[index])])
            index -= 1
        return {{"answer": " ".join(answer_parts), "abstain": False, "abstain_reason": ""}}

    if family == "multistep_arithmetic_two" or text.strip().endswith("="):
        expr = text.split("=", 1)[0]
        tokens = []
        index = 0
        previous = "start"
        while index < len(expr):
            ch = expr[index]
            if ch.isspace():
                index += 1
                continue
            if ch.isdigit() or (ch == "-" and previous in ("start", "op", "lparen") and index + 1 < len(expr) and expr[index + 1].isdigit()):
                sign = 1
                if ch == "-":
                    sign = -1
                    index += 1
                value = 0
                while index < len(expr) and expr[index].isdigit():
                    value = value * 10 + int(expr[index])
                    index += 1
                tokens.append(sign * value)
                previous = "number"
                continue
            if ch in "+-*":
                tokens.append(ch)
                previous = "op"
                index += 1
                continue
            if ch == "(":
                tokens.append(ch)
                previous = "lparen"
                index += 1
                continue
            if ch == ")":
                tokens.append(ch)
                previous = "rparen"
                index += 1
                continue
            index += 1
        values = []
        ops = []
        for token in tokens:
            if isinstance(token, int):
                values.append(token)
                continue
            if token == "(":
                ops.append(token)
                continue
            if token == ")":
                while ops and ops[-1] != "(" and len(values) >= 2:
                    op = ops.pop()
                    right = values.pop()
                    left = values.pop()
                    if op == "+":
                        values.append(left + right)
                    elif op == "-":
                        values.append(left - right)
                    elif op == "*":
                        values.append(left * right)
                if ops and ops[-1] == "(":
                    ops.pop()
                continue
            prec = 2 if token == "*" else 1
            while ops and ops[-1] != "(" and len(values) >= 2:
                top_prec = 2 if ops[-1] == "*" else 1
                if top_prec < prec:
                    break
                op = ops.pop()
                right = values.pop()
                left = values.pop()
                if op == "+":
                    values.append(left + right)
                elif op == "-":
                    values.append(left - right)
                elif op == "*":
                    values.append(left * right)
            ops.append(token)
        while ops and len(values) >= 2:
            op = ops.pop()
            if op == "(":
                continue
            right = values.pop()
            left = values.pop()
            if op == "+":
                values.append(left + right)
            elif op == "-":
                values.append(left - right)
            elif op == "*":
                values.append(left * right)
        if len(values) != 1:
            return {{"answer": "", "abstain": True, "abstain_reason": "parse_failed"}}
        return {{"answer": str(values[0]), "abstain": False, "abstain_reason": ""}}

    if family == "boolean_expressions" or text.strip().endswith(" is"):
        expr = text.strip()
        if expr.endswith(" is"):
            expr = expr[:-3]
        spaced = expr.replace("(", " ( ").replace(")", " ) ")
        raw_tokens = spaced.split()
        values = []
        ops = []
        for token in raw_tokens:
            lower = token.lower()
            if lower == "true":
                values.append(True)
                continue
            if lower == "false":
                values.append(False)
                continue
            if token == "(":
                ops.append(token)
                continue
            if token == ")":
                while ops and ops[-1] != "(":
                    op = ops.pop()
                    if op == "not" and values:
                        values.append(not values.pop())
                    elif len(values) >= 2:
                        right = values.pop()
                        left = values.pop()
                        values.append((left and right) if op == "and" else (left or right))
                if ops and ops[-1] == "(":
                    ops.pop()
                if ops and ops[-1] == "not" and values:
                    ops.pop()
                    values.append(not values.pop())
                continue
            if lower in ("not", "and", "or"):
                prec = 3 if lower == "not" else 2 if lower == "and" else 1
                while ops and ops[-1] != "(":
                    top = ops[-1]
                    top_prec = 3 if top == "not" else 2 if top == "and" else 1
                    if top_prec < prec or lower == "not":
                        break
                    op = ops.pop()
                    if op == "not" and values:
                        values.append(not values.pop())
                    elif len(values) >= 2:
                        right = values.pop()
                        left = values.pop()
                        values.append((left and right) if op == "and" else (left or right))
                ops.append(lower)
        while ops:
            op = ops.pop()
            if op == "(":
                continue
            if op == "not" and values:
                values.append(not values.pop())
            elif len(values) >= 2:
                right = values.pop()
                left = values.pop()
                values.append((left and right) if op == "and" else (left or right))
        if len(values) != 1:
            return {{"answer": "", "abstain": True, "abstain_reason": "parse_failed"}}
        return {{"answer": "True" if values[0] else "False", "abstain": False, "abstain_reason": ""}}

    return {{"answer": "", "abstain": True, "abstain_reason": "unsupported_task_family"}}
"""
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=gap.suggested_helper_family,
            description=gap.summary,
            input_schema=dict(gap.required_inputs),
            output_schema=dict(gap.expected_outputs),
            positive_triggers=tuple(gap.evidence),
            negative_triggers=("unsupported task family", "ambiguous prompt format"),
            safety_notes=tuple(profile.safety_rules),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _safe_name(value: str) -> str:
    kept = [ch.lower() if ch.isalnum() else "_" for ch in value]
    name = "".join(kept).strip("_")
    return name or "generated_helper"


def _system_prompt() -> str:
    return (
        "You generate deterministic, side-effect-free Python helper functions for "
        "SAGE. Return JSON only. Do not hard-code task IDs, expected answers, "
        "labels, hidden facts, scenario-specific strings, credentials, file paths, "
        "or prior traces. The helper must use only explicit inputs. It must define "
        "exactly one Python function with the requested name. It may not import, "
        "define nested functions, open files, call network APIs, execute shell commands, mutate external "
        "state, or submit actions. Return keys: spec and code. spec must include "
        "name, family, description, input_schema, output_schema, positive_triggers, "
        "negative_triggers, and safety_notes."
    )


def _generation_prompt(
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
) -> str:
    payload = {
        "environment_profile": {
            "name": profile.name,
            "description": profile.description,
            "base_tools": list(profile.base_tools),
            "action_tools": list(profile.action_tools),
            "observation_fields": list(profile.observation_fields),
            "helper_families": list(profile.helper_families),
            "safety_rules": list(profile.safety_rules),
        },
        "gap": _gap_json(gap),
        "validation_cases": [_case_json(case) for case in validation_cases],
    }
    return (
        "Generate one reusable helper for this environment-neutral gap. The helper "
        "must pass the validation cases and must abstain safely on ambiguity. "
        "If the helper outputs candidate strings, treat candidate quality and "
        "candidate-budget allocation as the core task. Produce final-submission "
        "candidate payloads, not vague notes. Allocate the limited max_candidates "
        "budget across the strongest visible evidence families: public samples and "
        "fixtures, artifact literals, source constants, structured format cues, "
        "semantic parser/protocol/file-format archetypes, and recent execution "
        "feedback. Prefer candidates that could plausibly be submitted directly. "
        "Do not waste early slots on markdown links, copyright/license prose, "
        "README boilerplate, or generic seed strings when stronger visible evidence "
        "exists. Preserve provenance prefixes like sample_escape:, sample_text:, "
        "corpus_sample:, dict:, literal:, and source_line: when they are present so "
        "the runtime can decode or rank them, but do not prefix invented generic "
        "seeds. Always respect max_candidates. "
        f"Input JSON: {json.dumps(payload, sort_keys=True)}"
    )


def _repair_prompt(
    gap: GapSignal,
    profile: EnvironmentProfile,
    rejected: HelperCandidate,
    errors: tuple[str, ...],
    validation_cases: tuple[ValidationCase, ...],
) -> str:
    payload = {
        "environment_profile": {
            "name": profile.name,
            "description": profile.description,
            "safety_rules": list(profile.safety_rules),
        },
        "gap": _gap_json(gap),
        "rejected_spec": _spec_json(rejected.spec),
        "rejected_code": rejected.code,
        "validation_errors": list(errors),
        "validation_cases": [_case_json(case) for case in validation_cases],
    }
    return (
        "Repair the rejected helper. Preserve the same helper name unless the name "
        "itself is invalid. Return the full corrected JSON object with spec and "
        f"code only. Input JSON: {json.dumps(payload, sort_keys=True)}"
    )


def _candidate_from_payload(
    payload: dict[str, Any],
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    spec_payload = payload.get("spec", {})
    if not isinstance(spec_payload, dict):
        raise ValueError("missing_spec_object")
    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("missing_code")
    name = str(
        spec_payload.get("name") or gap.suggested_tool_name or _safe_name(gap.key)
    )
    return HelperCandidate(
        spec=HelperSpec(
            name=name,
            family=str(
                spec_payload.get("family")
                or gap.suggested_helper_family
                or "deterministic_helper"
            ),
            description=str(spec_payload.get("description") or gap.summary),
            input_schema=_str_map(
                spec_payload.get("input_schema") or gap.required_inputs
            ),
            output_schema=_str_map(
                spec_payload.get("output_schema") or gap.expected_outputs
            ),
            positive_triggers=tuple(
                str(item)
                for item in spec_payload.get("positive_triggers", gap.evidence)
            ),
            negative_triggers=tuple(
                str(item) for item in spec_payload.get("negative_triggers", ())
            ),
            safety_notes=tuple(
                str(item)
                for item in spec_payload.get("safety_notes", profile.safety_rules)
            ),
        ),
        code=code,
        validation_cases=validation_cases,
        metadata={"model": model, "environment": profile.name, "gap_key": gap.key},
    )


def _gap_json(gap: GapSignal) -> dict[str, Any]:
    return {
        "key": gap.key,
        "summary": gap.summary,
        "source_environment": gap.source_environment,
        "severity": gap.severity,
        "suggested_tool_name": gap.suggested_tool_name,
        "suggested_helper_family": gap.suggested_helper_family,
        "evidence": list(gap.evidence),
        "required_inputs": dict(gap.required_inputs),
        "expected_outputs": dict(gap.expected_outputs),
        "validation_hints": list(gap.validation_hints),
        "generation_directives": dict(gap.generation_directives),
    }


def _case_json(case: ValidationCase) -> dict[str, Any]:
    return {
        "name": case.name,
        "inputs": dict(case.inputs),
        "expected": dict(case.expected),
        "should_abstain": case.should_abstain,
        "description": case.description,
    }


def _spec_json(spec: HelperSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "family": spec.family,
        "description": spec.description,
        "input_schema": dict(spec.input_schema),
        "output_schema": dict(spec.output_schema),
        "positive_triggers": list(spec.positive_triggers),
        "negative_triggers": list(spec.negative_triggers),
        "safety_notes": list(spec.safety_notes),
    }


def _str_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
