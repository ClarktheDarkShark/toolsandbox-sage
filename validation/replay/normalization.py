"""Narrow, reviewed normalization for replay snapshots.

The comparison is deliberately fail-closed. A field is changed only when its
JSON-pointer path matches a rule in ``approved_nondeterminism.json``. There is
no command-line escape hatch for adding rules during a comparison.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppliedNormalization:
    """One normalization applied to a concrete snapshot path."""

    path: str
    pattern: str
    action: str


def _escape_pointer_part(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _iter_nodes(value: Any, path: str = "") -> list[tuple[str, Any, object]]:
    """Return ``(pointer, parent, key)`` entries for every non-root node."""

    nodes: list[tuple[str, Any, object]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child_path = f"{path}/{_escape_pointer_part(key)}"
            nodes.append((child_path, value, key))
            nodes.extend(_iter_nodes(value[key], child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}/{index}"
            nodes.append((child_path, value, index))
            nodes.extend(_iter_nodes(child, child_path))
    return nodes


def _pointer_matches(pointer: str, pattern: str) -> bool:
    """Match an exact pointer, allowing ``*`` for one complete segment only."""

    pointer_parts = pointer.split("/")[1:]
    pattern_parts = pattern.split("/")[1:]
    return len(pointer_parts) == len(pattern_parts) and all(
        expected == "*" or expected == actual
        for actual, expected in zip(pointer_parts, pattern_parts, strict=True)
    )


def load_rules(path: Path) -> list[dict[str, Any]]:
    """Load and strictly validate the checked-in normalization allowlist."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"Unsupported normalization schema in {path}")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"Normalization rules must be a list in {path}")
    validated: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(rules):
        if not isinstance(raw_rule, dict):
            raise ValueError(f"Normalization rule {index} must be an object")
        unexpected = set(raw_rule) - {"path", "action", "replacement", "reason"}
        if unexpected:
            raise ValueError(
                f"Normalization rule {index} has unsupported keys: {sorted(unexpected)}"
            )
        pattern = raw_rule.get("path")
        action = raw_rule.get("action")
        reason = raw_rule.get("reason")
        if not isinstance(pattern, str) or not pattern.startswith("/probes/"):
            raise ValueError(
                f"Normalization rule {index} must target an explicit /probes path"
            )
        if "**" in pattern:
            raise ValueError(
                f"Normalization rule {index} may use segment wildcards, not '**'"
            )
        if action not in {"remove", "replace"}:
            raise ValueError(
                f"Normalization rule {index} has unsupported action {action!r}"
            )
        if action == "replace" and "replacement" not in raw_rule:
            raise ValueError(
                f"Normalization rule {index} must provide a replacement value"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                f"Normalization rule {index} must explain the nondeterminism"
            )
        validated.append(dict(raw_rule))
    return validated


def normalize_snapshot(
    snapshot: dict[str, Any], rules: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[AppliedNormalization]]:
    """Apply only allowlisted normalizations and return an auditable record."""

    normalized = copy.deepcopy(snapshot)
    applied: list[AppliedNormalization] = []
    # Work deepest-first so removing a parent cannot conceal a child match.
    nodes = sorted(
        _iter_nodes(normalized), key=lambda row: row[0].count("/"), reverse=True
    )
    for pointer, parent, key in nodes:
        matching = [
            rule for rule in rules if _pointer_matches(pointer, str(rule["path"]))
        ]
        if len(matching) > 1:
            raise ValueError(f"Multiple normalization rules match {pointer}")
        if not matching:
            continue
        rule = matching[0]
        action = str(rule["action"])
        if action == "remove":
            if isinstance(parent, dict):
                parent.pop(key)
            else:
                # List removal would shift later JSON-pointer indexes and make the
                # audit record ambiguous. Replace list entries with a sentinel.
                parent[int(key)] = "<approved-nondeterministic-field-removed>"
        else:
            parent[key] = copy.deepcopy(rule["replacement"])
        applied.append(
            AppliedNormalization(
                path=pointer,
                pattern=str(rule["path"]),
                action=action,
            )
        )
    return normalized, sorted(applied, key=lambda item: item.path)
