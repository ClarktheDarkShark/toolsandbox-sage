"""Deterministically bind validation evidence to all production Python sources."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


PRODUCTION_PYTHON_SOURCE_SCOPE: dict[str, str] = {
    "root": "src/sage_ts",
    "include": "**/*.py",
    "relative_paths": "repository_root",
    "framing": "uint64be(path_length)+path_utf8+uint64be(content_length)+content",
    "symlinks": "rejected",
}


def production_python_source_identity(repo_root: Path) -> dict[str, Any]:
    """Hash the sorted repository-relative path and exact bytes of every source."""

    root = repo_root.expanduser().resolve()
    source_relative = Path(PRODUCTION_PYTHON_SOURCE_SCOPE["root"])
    source_root = root / source_relative
    if not source_root.is_dir():
        raise ValueError(f"production source root is not a directory: {source_root}")
    scope_cursor = root
    for part in source_relative.parts:
        scope_cursor /= part
        if scope_cursor.is_symlink():
            raise ValueError(
                f"production source scope contains a symlink: {scope_cursor}"
            )
    symlinks = sorted(
        (path for path in source_root.rglob("*") if path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if symlinks:
        rendered = ", ".join(path.relative_to(root).as_posix() for path in symlinks)
        raise ValueError(f"production source scope contains symlinks: {rendered}")
    files = sorted(
        (path for path in source_root.rglob("*.py") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        raise ValueError(
            f"production source scope contains no Python files: {source_root}"
        )

    digest = hashlib.sha256()
    for path in files:
        relative_bytes = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return {
        "scope": dict(PRODUCTION_PYTHON_SOURCE_SCOPE),
        "file_count": len(files),
        "sha256": digest.hexdigest(),
    }
