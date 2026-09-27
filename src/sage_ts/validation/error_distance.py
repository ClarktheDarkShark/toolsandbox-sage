"""Distance scoring for generated-tool validation errors."""

from __future__ import annotations

import ast
from typing import Any


_FATAL_ERROR_PREFIXES = (
    "syntax_error:",
    "missing_generated_code",
    "expected_exactly_one_function",
    "function_count_mismatch:",
    "compiled_function_count_mismatch:",
    "function_name_mismatch:",
    "missing_expected_function",
    "compile_error:",
    "denied_node:",
    "denied_call:",
    "denied_attribute_call:",
)
_MISMATCH_TOKENS = ("_mismatch:", "_native_action_arguments:")


def validation_error_distance(error: str) -> int:
    """Return the structural distance represented by one validator error."""

    if error.startswith(_FATAL_ERROR_PREFIXES):
        return 10_000
    mismatch_token = next((token for token in _MISMATCH_TOKENS if token in error), "")
    if not mismatch_token or "!=" not in error:
        if "_native_action_count:" in error:
            return 50
        if "_native_action_execution_error:" in error:
            return 100
        return 20
    try:
        _, rest = error.split(mismatch_token, 1)
        actual_text, expected_text = rest.split("!=", 1)
        actual = ast.literal_eval(actual_text.replace("NOT_GIVEN", "'__NOT_GIVEN__'"))
        expected = ast.literal_eval(
            expected_text.replace("NOT_GIVEN", "'__NOT_GIVEN__'")
        )
    except Exception:
        return 10
    return _value_distance(actual, expected)


def _value_distance(actual: Any, expected: Any) -> int:
    if actual == expected:
        return 0
    if isinstance(actual, dict) and isinstance(expected, dict):
        keys = set(actual) | set(expected)
        return sum(_value_distance(actual.get(key), expected.get(key)) for key in keys)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        length = max(len(actual), len(expected))
        return sum(
            _value_distance(
                actual[index] if index < len(actual) else None,
                expected[index] if index < len(expected) else None,
            )
            for index in range(length)
        )
    return 1
