"""Low-cost helper generators for standalone SAGE smoke tests.

Production environments can pass an LLM-backed generator that uses the same
``HelperGenerator`` protocol. These templates are intentionally generic and
consume environment-supplied gap directives rather than hard-coded benchmark
answers.
"""

from __future__ import annotations

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
        raise ValueError(f"unsupported_template:{template or 'missing'}")


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


def _safe_name(value: str) -> str:
    kept = [ch.lower() if ch.isalnum() else "_" for ch in value]
    name = "".join(kept).strip("_")
    return name or "generated_helper"
