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
        if template in {
            "visible_text_candidate_planner",
            "cybergym_seed_poc_candidates",
        }:
            return _visible_text_candidate_planner(
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
        """Repair by regenerating from the environment directives."""

        del rejected, errors
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
    code = f"""def {name}(description: str, readme: str = "", feedback: str = "", max_candidates: int = 12) -> dict:
    text = (str(description or "") + "\\n" + str(readme or "") + "\\n" + str(feedback or "")).lower()
    candidates = []

    if "json" in text or "jq" in text:
        candidates.extend(["{{}}", "[]", "{{\\"a\\":1}}", "{{\\"a\\":[1,2,3]}}", "-10E-1000010001"])
    if "xml" in text or "libxml" in text or "namespace" in text or "entity" in text:
        candidates.extend(["<a/>", "<root></root>", "<!DOCTYPE a [<!ENTITY x 'x'>]><a>&x;</a>", "<a xmlns:x='urn:x' x:id='x'/>"])
    if "regex" in text or "pcre" in text or "regexp" in text:
        candidates.extend(["(", "(a", "(?C)", "(?<a>a)", "\\\\C", "a{{100000}}"])
    if "yara" in text or "rule" in text:
        candidates.extend(["rule a {{ condition: true }}", "rule a {{ strings: $a = \\"A\\" condition: $a }}", "import \\"pe\\"\\nrule a {{ condition: pe.number_of_sections > 0 }}"])
    if "csv" in text or "comma" in text:
        candidates.extend(["a,b\\n", "1,2,3\\n", "\\"a\\",\\"b\\"\\n"])
    if "png" in text:
        candidates.extend(["\\x89PNG\\r\\n\\x1a\\n", "\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR"])
    if "jpeg" in text or "jpg" in text:
        candidates.extend(["\\xff\\xd8\\xff\\xd9", "\\xff\\xd8\\xff\\xe0JFIF\\x00\\xff\\xd9"])
    if "zip" in text:
        candidates.extend(["PK\\x03\\x04", "PK\\x05\\x06"])
    if "font" in text or "freetype" in text or "cff" in text or "ttf" in text:
        candidates.extend(["OTTO\\x00\\x01\\x00\\x00", "\\x00\\x01\\x00\\x00\\x00\\x01\\x00\\x00", "ttcf\\x00\\x01\\x00\\x00"])
    if "bam" in text or "sam" in text or "cram" in text or "htslib" in text:
        candidates.extend(["@HD\\tVN:1.6\\n", "BAM\\x01", "CRAM\\x03\\x00"])
    if "aac" in text or "faad" in text or "xaac" in text:
        candidates.extend(["\\xff\\xf1\\x50\\x80\\x00\\x1f\\xfc", "\\x00\\x00\\x00\\x00\\xff\\xf1"])
    if "empty" in text or "null" in text:
        candidates.extend(["", "\\x00"])
    if "timeout" in text:
        candidates.extend(["A" * 64, "0" * 64])

    candidates.extend(["\\x00\\x01\\x02\\x03", "", "A", "AAAA", "0", "1", "A" * 32])
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
