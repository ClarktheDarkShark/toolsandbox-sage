"""Validation for standalone SAGE helper candidates."""

from __future__ import annotations

import ast
import warnings
from collections.abc import Callable
from typing import Any, cast

from sage_agent.interfaces import HelperCandidate, HelperValidationReport

_BLOCKED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.ClassDef,
    ast.AsyncFunctionDef,
)

_BLOCKED_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "print",
    "setattr",
}

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
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


def validate_helper_candidate(candidate: HelperCandidate) -> HelperValidationReport:
    """Validate syntax, side-effect safety, callability, and semantic cases."""

    errors: list[str] = []
    tree = _parse(candidate.code, errors)
    if tree is not None:
        errors.extend(_static_safety_errors(tree))
    function = None if errors else _load_function(candidate, errors)
    cases_run = 0
    cases_passed = 0
    if function is not None:
        for case in candidate.validation_cases:
            cases_run += 1
            try:
                result = function(**dict(case.inputs))
            except Exception as exc:  # pragma: no cover - defensive detail in report
                errors.append(f"{case.name}:runtime_error:{type(exc).__name__}:{exc}")
                continue
            if _case_passes(result, dict(case.expected), case.should_abstain):
                cases_passed += 1
            else:
                errors.append(f"{case.name}:unexpected_output:{result!r}")
    accepted = not errors and cases_run > 0 and cases_run == cases_passed
    return HelperValidationReport(
        accepted=accepted,
        errors=tuple(errors),
        cases_run=cases_run,
        cases_passed=cases_passed,
        runtime_smoke_passed=function is not None,
        side_effect_free=tree is not None and not _static_safety_errors(tree),
    )


def _parse(code: str, errors: list[str]) -> ast.AST | None:
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SyntaxWarning)
            tree = ast.parse(code)
        errors.extend(_syntax_warning_errors(caught))
        return tree
    except SyntaxError as exc:
        errors.append(f"syntax_error:{exc.msg}:line_{exc.lineno}")
        return None


def _static_safety_errors(tree: ast.AST) -> list[str]:
    errors: list[str] = []
    function_count = 0
    for node in ast.walk(tree):
        if isinstance(node, _BLOCKED_NODES):
            errors.append(f"blocked_ast_node:{type(node).__name__}")
        if isinstance(node, ast.FunctionDef):
            function_count += 1
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in _BLOCKED_CALLS:
                errors.append(f"blocked_call:{name}")
    if function_count != 1:
        errors.append(f"expected_exactly_one_function:found_{function_count}")
    return errors


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _load_function(
    candidate: HelperCandidate, errors: list[str]
) -> Callable[..., Any] | None:
    namespace: dict[str, Any] = {}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SyntaxWarning)
            compiled = compile(
                candidate.code, f"<sage-helper:{candidate.spec.name}>", "exec"
            )
        warning_errors = _syntax_warning_errors(caught)
        if warning_errors:
            errors.extend(warning_errors)
            return None
        exec(  # noqa: S102 - deliberate execution inside restricted smoke namespace
            compiled,
            {"__builtins__": _SAFE_BUILTINS},
            namespace,
        )
    except Exception as exc:
        errors.append(f"compile_or_load_error:{type(exc).__name__}:{exc}")
        return None
    function = namespace.get(candidate.spec.name)
    if not callable(function):
        errors.append(f"missing_function:{candidate.spec.name}")
        return None
    return cast(Callable[..., Any], function)


def _syntax_warning_errors(caught: list[warnings.WarningMessage]) -> list[str]:
    errors: list[str] = []
    for warning in caught:
        if issubclass(warning.category, SyntaxWarning):
            errors.append(f"syntax_warning:{warning.message}")
    return errors


def _case_passes(result: Any, expected: dict[str, Any], should_abstain: bool) -> bool:
    if not isinstance(result, dict):
        return False
    if should_abstain:
        abstain_keys = ("abstain", "should_abstain", "abstain_reason")
        if not any(bool(result.get(key)) for key in abstain_keys):
            return False
    if "candidates" in result and not _candidate_output_passes(result, expected):
        return False
    special_keys = {
        "candidates_contains",
        "candidates_contains_any",
        "candidates_contains_fragment",
        "candidates_contains_any_fragment",
        "candidates_not_contains",
        "candidates_min_unique",
        "candidates_max_count",
        "first_candidate_in",
    }
    for key, value in expected.items():
        if key in special_keys:
            continue
        if result.get(key) != value:
            return False
    return True


def _candidate_output_passes(result: dict[str, Any], expected: dict[str, Any]) -> bool:
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        return False
    if not all(isinstance(item, str) for item in candidates):
        return False
    if len(candidates) != len(set(candidates)):
        return False
    if result.get("candidate_count") != len(candidates):
        return False
    first = candidates[0] if candidates else ""
    if result.get("first_candidate") != first:
        return False
    if not result.get("abstain", False) and not candidates:
        return False
    max_count = expected.get("candidates_max_count")
    if isinstance(max_count, int) and len(candidates) > max_count:
        return False
    min_unique = expected.get("candidates_min_unique")
    if isinstance(min_unique, int) and len(set(candidates)) < min_unique:
        return False
    required = expected.get("candidates_contains", ())
    if isinstance(required, str):
        required = (required,)
    if isinstance(required, (list, tuple, set)):
        for item in required:
            if str(item) not in candidates:
                return False
    any_required = expected.get("candidates_contains_any", ())
    if isinstance(any_required, str):
        any_required = (any_required,)
    if isinstance(any_required, (list, tuple, set)) and any_required:
        if not any(str(item) in candidates for item in any_required):
            return False
    required_fragments = expected.get("candidates_contains_fragment", ())
    if isinstance(required_fragments, str):
        required_fragments = (required_fragments,)
    if isinstance(required_fragments, (list, tuple, set)):
        for item in required_fragments:
            needle = str(item)
            if not any(needle in candidate for candidate in candidates):
                return False
    any_required_fragments = expected.get("candidates_contains_any_fragment", ())
    if isinstance(any_required_fragments, str):
        any_required_fragments = (any_required_fragments,)
    if (
        isinstance(any_required_fragments, (list, tuple, set))
        and any_required_fragments
    ):
        if not any(
            str(item) in candidate
            for item in any_required_fragments
            for candidate in candidates
        ):
            return False
    forbidden = expected.get("candidates_not_contains", ())
    if isinstance(forbidden, str):
        forbidden = (forbidden,)
    if isinstance(forbidden, (list, tuple, set)):
        for item in forbidden:
            if str(item) in candidates:
                return False
    first_candidate_in = expected.get("first_candidate_in", ())
    if isinstance(first_candidate_in, str):
        first_candidate_in = (first_candidate_in,)
    if isinstance(first_candidate_in, (list, tuple, set)) and first_candidate_in:
        if first not in {str(item) for item in first_candidate_in}:
            return False
    return True
