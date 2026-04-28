#!/usr/bin/env python3
"""Small local secret scanner for pre-commit and bootstrap checks."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*['\"]?sk-[A-Za-z0-9_\-]+"),
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]

SKIP_PARTS = {
    ".git",
    ".secrets",
    "outputs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".pkl", ".parquet"}


def iter_files(paths: list[str]) -> list[Path]:
    if not paths:
        paths = ["."]
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and not any(
                    part in SKIP_PARTS for part in child.parts
                ):
                    files.append(child)
        elif path.is_file():
            files.append(path)
    return files


def main() -> int:
    offenders: list[str] = []
    for path in iter_files(sys.argv[1:]):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(str(path))
                break
    if offenders:
        print("Potential secrets detected:", file=sys.stderr)
        for offender in offenders:
            print(f"  {offender}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
