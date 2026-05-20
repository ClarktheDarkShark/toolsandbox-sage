"""Validation for standalone SAGE helper candidates."""

from __future__ import annotations

import ast
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
        return ast.parse(code)
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
        exec(  # noqa: S102 - deliberate execution inside restricted smoke namespace
            compile(candidate.code, f"<sage-helper:{candidate.spec.name}>", "exec"),
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


def _case_passes(result: Any, expected: dict[str, Any], should_abstain: bool) -> bool:
    if not isinstance(result, dict):
        return False
    if should_abstain:
        abstain_keys = ("abstain", "should_abstain", "abstain_reason")
        if not any(bool(result.get(key)) for key in abstain_keys):
            return False
    for key, value in expected.items():
        if result.get(key) != value:
            return False
    return True
