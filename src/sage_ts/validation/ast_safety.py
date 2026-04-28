"""AST safety checks for generated deterministic helper tools."""

from __future__ import annotations

import ast
from dataclasses import dataclass

DENIED_NODES = (
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
)

DENIED_CALL_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "locals",
    "open",
}

DENIED_ATTRIBUTE_ROOTS = {"os", "pathlib", "requests", "socket", "subprocess", "sys"}


@dataclass(frozen=True)
class SafetyResult:
    safe: bool
    errors: tuple[str, ...]


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = [node.attr]
        value = node.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
            return ".".join(reversed(parts))
    return None


def check_ast_safety(code: str) -> SafetyResult:
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return SafetyResult(False, (f"syntax_error:{exc.msg}",))

    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        errors.append("expected_exactly_one_function")

    for node in ast.walk(tree):
        if isinstance(node, DENIED_NODES):
            errors.append(f"denied_node:{type(node).__name__}")
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in DENIED_CALL_NAMES:
                errors.append(f"denied_call:{name}")
            root = name.split(".", 1)[0] if name else None
            if root in DENIED_ATTRIBUTE_ROOTS:
                errors.append(f"denied_attribute_call:{name}")
    return SafetyResult(not errors, tuple(sorted(set(errors))))
