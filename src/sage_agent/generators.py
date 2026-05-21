"""Helper generators for standalone SAGE.

Template generation is used for deterministic smoke tests. ``OpenAIHelperGenerator``
provides the same protocol for low-cost live generation with ``gpt-4o-mini``.
"""

from __future__ import annotations

import json
from importlib import import_module
from typing import Any, cast

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperSpec,
    ValidationCase,
)

CANDIDATE_PLANNER_FAMILIES = {
    "visible_text_candidate_planner",
    "artifact_literal_candidate_planner",
    "execution_feedback_candidate_mutation_planner",
    "structured_input_candidate_planner",
    "source_boundary_candidate_planner",
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
        if template == "artifact_literal_candidate_planner":
            return _artifact_literal_candidate_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "source_boundary_candidate_planner":
            return _source_boundary_candidate_planner(
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
        if template == "grid_shortest_path_action_planner":
            return _grid_shortest_path_action_planner(
                name, gap, profile, validation_cases, model
            )
        if template == "symbolic_text_answerer":
            return _symbolic_text_answerer(name, gap, profile, validation_cases, model)
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
                value = line[pos + len(marker):].strip(" :-,;\\t")
                if 0 < len(value) <= 240:
                    candidates.append(value)
        if ":" in line and line_lower.split(":", 1)[0] in ("literal", "symbol", "source_line", "dict", "example", "input"):
            value = line.split(":", 1)[1].strip(" :-,;\\t")
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
    prefixes = ("literal:", "source_line:", "dict:", "token:", "example:", "input:")
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("file:"):
            continue
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = line[len(prefix):].strip(" :-,;\\t")
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
        for prefix in ("literal:", "dict:", "token:", "magic:", "example:", "input:"):
            if line_lower.startswith(prefix):
                value = line[len(prefix):].strip(" :-,;\\t")
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


def _execution_feedback_candidate_mutation_planner(
    name: str,
    gap: GapSignal,
    profile: EnvironmentProfile,
    validation_cases: tuple[ValidationCase, ...],
    model: str,
) -> HelperCandidate:
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", artifact_summary: str = "", max_candidates: int = 12) -> dict:
    text = str(feedback or "") + "\\n" + str(description or "") + "\\n" + str(artifact_summary or "")
    candidates = []
    lengths = []
    for token in text.replace("=", " ").replace(":", " ").split():
        if token.isdigit():
            value = int(token)
            if 0 <= value <= 4096:
                lengths.append(value)
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
    if "xml" in text.lower() or "<" in text:
        candidates.extend(["<a/>", "<root></root>", "<root>A</root>"])
    if "json" in text.lower() or "{{" in text:
        candidates.extend(["{{}}", "[]", "{{\\"a\\":1}}"])
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
    candidates = []

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
    )
    for raw_line in text.splitlines():
        line = raw_line.strip(" \\t\\r\\n-*")
        if not line:
            continue
        line_lower = line.lower()
        if line_lower.startswith("file:"):
            continue
        for prefix in explicit_prefixes:
            pos = line_lower.find(prefix)
            if pos >= 0 and "provided as input to the vulnerable program" not in line_lower:
                value = line[pos + len(prefix):].strip(" :-,;\\t")
                if value:
                    candidates.append(str(value))
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
                        candidates.append(str(value))
                    start = right + 1

    if "xml" in lower or "html" in lower or "<" in text:
        for value in ("<a/>", "<root></root>", "<root>A</root>", "<!DOCTYPE a><a/>"):
            candidates.append(str(value))
    if "json" in lower or "javascript" in lower:
        for value in ("{{}}", "[]", "{{\\"a\\":1}}", "[1,2,3]"):
            candidates.append(str(value))
    if "csv" in lower or "comma" in lower:
        for value in ("a,b\\n", "1,2,3\\n", "name,value\\na,1\\n"):
            candidates.append(str(value))
    if "regex" in lower or "pcre" in lower:
        for value in ("(", "(a", ".*", "[a-", "(?P<a>a)"):
            candidates.append(str(value))
    if "path" in lower or "file" in lower:
        for value in ("/tmp/a", "../a", "A/B", "file.txt"):
            candidates.append(str(value))
    if "size" in lower or "length" in lower or "chunk" in lower:
        for value in ("0", "1", "-1", "4294967295", "A" * 32, "A" * 128):
            candidates.append(str(value))

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
        "A" * 8,
        "A" * 32,
        "A" * 128,
    ]
    for value in seed_pool:
        candidates.append(str(value))
    for length in lengths[:16]:
        if length <= 0:
            continue
        capped = min(max(length, 1), 512)
        candidates.append(str("A" * capped))
        candidates.append(str("\\x00" * min(capped, 64)))
        if capped > 1:
            candidates.append(str("A" * (capped - 1)))
            candidates.append(str("A" * (capped + 1)))

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
                candidates.append(str(value))
            start = right + 1

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
        "open files, call network APIs, execute shell commands, mutate external "
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
