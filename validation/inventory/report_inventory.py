#!/usr/bin/env python3
"""Report an honest, reproducible inventory of SAGE-authored source.

The inventory deliberately starts from ``git ls-files``.  This prevents local
run output, generated dashboards, build products, and virtual environments from
silently inflating the result.  Tracked benchmark fixtures and rendered
dashboard artifacts are also reported as exclusions rather than source.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import subprocess
import sys
import tokenize
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


SOURCE_SUFFIXES = {".py", ".sh", ".html", ".toml", ".txt"}
SOURCE_FILENAMES = {"Makefile", ".env.example"}
BEHAVIOR_DATA_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".jinja", ".j2", ".txt"}

# These markers identify prose and catalogs that affect generation, routing,
# policy selection, validation, or evaluation.  Their lines remain part of the
# source totals; the separate count prevents prompt/config LOC from disappearing
# behind a narrower definition of "code".
BEHAVIOR_NAME_MARKERS = (
    "contract",
    "example",
    "guidance",
    "instruction",
    "observation",
    "pattern",
    "policy",
    "prompt",
    "rule",
    "schema",
    "sentinel",
    "signal",
    "trigger",
)
CATALOG_NAME_SUFFIXES = (
    "_GROUP",
    "_GROUPS",
    "_MAP",
    "_MAPPING",
    "_NAMES",
    "_PATTERN",
    "_PATTERNS",
    "_REGISTRY",
    "_SCHEMA",
    "_SCHEMAS",
    "_SUFFIXES",
    "_TOOLS",
)


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    dashboard: bool = False


CATEGORIES = {
    "algorithm_core": Category(
        "algorithm_core",
        "SAGE algorithm core (adequacy, generation, lifecycle, registry, routing, validation)",
    ),
    "adapters": Category("adapters", "ToolSandbox and model adapters"),
    "evaluation": Category("evaluation", "Outcome evaluation and contribution accounting"),
    "execution": Category("execution", "Execution, reproducibility, and package configuration"),
    "behavior_catalogs": Category(
        "behavior_catalogs", "External behavior-defining prompts and catalogs"
    ),
    "live_dashboard": Category("live_dashboard", "Live run dashboard source", dashboard=True),
    "chapter4_dashboard": Category(
        "chapter4_dashboard", "Chapter 4 aggregate dashboard source", dashboard=True
    ),
}


@dataclass(frozen=True)
class LineMetrics:
    physical: int
    nonblank: int
    source: int
    blank: int
    comment_only: int
    behavior_definition_source: int


@dataclass(frozen=True)
class FileRecord:
    path: str
    category: str
    metrics: LineMetrics


@dataclass(frozen=True)
class SymbolRecord:
    path: str
    category: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    span: int


@dataclass(frozen=True)
class ExcludedRecord:
    path: str
    reason: str
    physical_lines: int


def _git_root(path: Path) -> Path:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _tracked_paths(root: Path) -> list[PurePosixPath]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        PurePosixPath(raw.decode("utf-8"))
        for raw in completed.stdout.split(b"\0")
        if raw
    ]


def _is_source_candidate(path: PurePosixPath) -> bool:
    return (
        path.suffix.lower() in SOURCE_SUFFIXES
        or path.name in SOURCE_FILENAMES
        or _is_behavior_data_path(path)
    )


def _is_behavior_data_path(path: PurePosixPath) -> bool:
    if path.suffix.lower() not in BEHAVIOR_DATA_SUFFIXES:
        return False
    searchable = " ".join(part.lower() for part in path.parts)
    return any(marker in searchable for marker in BEHAVIOR_NAME_MARKERS)


def classify_path(path: PurePosixPath) -> tuple[Category | None, str | None]:
    """Classify a tracked path, returning an explicit exclusion reason."""
    value = path.as_posix()
    parts = path.parts

    if parts and parts[0] == "tool_sandbox":
        return None, "native_toolsandbox"
    if parts and parts[0] in {"artifacts", "outputs", "dist", "build"}:
        return None, "generated_or_static_output"
    if parts and parts[0] == "validation":
        return None, "validation_tooling"
    if parts and parts[0] in {"docs", "figures"}:
        return None, "documentation_or_frozen_input"
    if path.name in {
        "README.md",
        "LICENSE",
        "NOTICE.md",
        "ACKNOWLEDGEMENTS",
        "CITATION.cff",
        ".gitignore",
    }:
        return None, "documentation_or_legal"
    if not _is_source_candidate(path):
        return None, "non_source_input"

    if value.startswith("src/sage_ts/dashboard/"):
        return CATEGORIES["live_dashboard"], None
    if value in {
        "scripts/build_chapter4_evidence_dashboard.py",
        "scripts/build_chapter4_evolution_dashboard.py",
    } or value.startswith("scripts/research/"):
        return CATEGORIES["chapter4_dashboard"], None
    if value.startswith("src/sage_ts/adapters/"):
        return CATEGORIES["adapters"], None
    if value.startswith("src/sage_ts/evaluation/"):
        return CATEGORIES["evaluation"], None
    if any(
        value.startswith(f"src/sage_ts/{area}/")
        for area in (
            "adequacy",
            "generation",
            "orchestration",
            "registry",
            "runtime",
            "validation",
        )
    ):
        return CATEGORIES["algorithm_core"], None
    if value.startswith("src/sage_ts/") or value.startswith("scripts/"):
        return CATEGORIES["execution"], None
    if _is_behavior_data_path(path):
        return CATEGORIES["behavior_catalogs"], None
    if value in {
        ".env.example",
        "Makefile",
        "pyproject.toml",
        "requirements-publication-lock.txt",
    }:
        return CATEGORIES["execution"], None
    return None, "outside_sage_source_scope"


def _python_comment_lines(text: str) -> set[int]:
    comments: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comments.update(range(token.start[0], token.end[0] + 1))
    except (IndentationError, SyntaxError, tokenize.TokenError):
        # Syntax errors are surfaced separately by AST parsing.  Returning no
        # comment lines here keeps the inventory conservative.
        return set()
    return comments


def _non_python_comment_lines(lines: Sequence[str], suffix: str) -> set[int]:
    result: set[int] = set()
    in_html_comment = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if suffix == ".html":
            if stripped.startswith("<!--"):
                in_html_comment = True
            if in_html_comment:
                result.add(number)
            if in_html_comment and "-->" in stripped:
                in_html_comment = False
        elif stripped.startswith("#"):
            result.add(number)
    return result


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in _target_names(item)]
    return []


def _assignment_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Assign):
        return [name for target in node.targets for name in _target_names(target)]
    if isinstance(node, ast.AnnAssign):
        return _target_names(node.target)
    return []


def _behavior_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in BEHAVIOR_NAME_MARKERS) or name.endswith(
        CATALOG_NAME_SUFFIXES
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


class _BehaviorLineVisitor(ast.NodeVisitor):
    def __init__(self, docstrings: set[int]) -> None:
        self.docstrings = docstrings
        self.lines: set[int] = set()
        self.behavior_scope: list[bool] = [False]

    @staticmethod
    def _span(node: ast.AST) -> range:
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        return range(start, end + 1) if start else range(0)

    def _visit_scoped(self, node: ast.AST, name: str) -> None:
        self.behavior_scope.append(self.behavior_scope[-1] or _behavior_name(name))
        self.generic_visit(node)
        self.behavior_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scoped(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scoped(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scoped(node, node.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        names = _assignment_names(node)
        if any(_behavior_name(name) for name in names):
            self.lines.update(self._span(node))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        names = _assignment_names(node)
        if any(_behavior_name(name) for name in names):
            self.lines.update(self._span(node))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if (
            isinstance(node.value, str)
            and id(node) not in self.docstrings
            and self.behavior_scope[-1]
        ):
            self.lines.update(self._span(node))


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: str, category: str) -> None:
        self.path = path
        self.category = category
        self.stack: list[str] = []
        self.symbols: list[SymbolRecord] = []

    def _record(self, node: ast.AST, name: str, kind: str) -> None:
        start = int(getattr(node, "lineno"))
        end = int(getattr(node, "end_lineno", start))
        qualified = ".".join((*self.stack, name))
        self.symbols.append(
            SymbolRecord(
                path=self.path,
                category=self.category,
                qualified_name=qualified,
                kind=kind,
                start_line=start,
                end_line=end,
                span=end - start + 1,
            )
        )
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node, node.name, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record(node, node.name, "async_function")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node, node.name, "class")


def _python_details(
    text: str, path: str, category: str
) -> tuple[set[int], list[SymbolRecord], str | None]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        return set(), [], f"{path}:{exc.lineno}: {exc.msg}"
    behavior = _BehaviorLineVisitor(_docstring_nodes(tree))
    behavior.visit(tree)
    symbols = _SymbolVisitor(path, category)
    symbols.visit(tree)
    return behavior.lines, symbols.symbols, None


def _line_metrics(
    text: str,
    suffix: str,
    behavior_lines: set[int],
) -> LineMetrics:
    lines = text.splitlines()
    blank_lines = {number for number, line in enumerate(lines, 1) if not line.strip()}
    if suffix == ".py":
        comment_lines = _python_comment_lines(text)
    else:
        comment_lines = _non_python_comment_lines(lines, suffix)
    comment_only = {
        number
        for number in comment_lines
        if number not in blank_lines
        and (
            suffix != ".py"
            or lines[number - 1].lstrip().startswith("#")
        )
    }
    nonblank = set(range(1, len(lines) + 1)) - blank_lines
    source = nonblank - comment_only
    behavior_source = behavior_lines & source
    return LineMetrics(
        physical=len(lines),
        nonblank=len(nonblank),
        source=len(source),
        blank=len(blank_lines),
        comment_only=len(comment_only),
        behavior_definition_source=len(behavior_source),
    )


def build_inventory(root: Path) -> dict[str, object]:
    root = _git_root(root)
    files: list[FileRecord] = []
    symbols: list[SymbolRecord] = []
    exclusions: list[ExcludedRecord] = []
    parse_errors: list[str] = []

    for relative in _tracked_paths(root):
        absolute = root / relative.as_posix()
        try:
            text = absolute.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        category, reason = classify_path(relative)
        if category is None:
            exclusions.append(
                ExcludedRecord(
                    path=relative.as_posix(),
                    reason=reason or "excluded",
                    physical_lines=len(text.splitlines()),
                )
            )
            continue

        behavior_lines: set[int] = set()
        file_symbols: list[SymbolRecord] = []
        if relative.suffix == ".py":
            behavior_lines, file_symbols, error = _python_details(
                text, relative.as_posix(), category.key
            )
            if error:
                parse_errors.append(error)
        elif _is_behavior_data_path(relative):
            behavior_lines = set(range(1, len(text.splitlines()) + 1))
        metrics = _line_metrics(text, relative.suffix, behavior_lines)
        files.append(FileRecord(relative.as_posix(), category.key, metrics))
        symbols.extend(file_symbols)

    category_rows: list[dict[str, object]] = []
    for key, category in CATEGORIES.items():
        members = [record for record in files if record.category == key]
        category_rows.append(
            {
                "key": key,
                "label": category.label,
                "dashboard": category.dashboard,
                "file_count": len(members),
                "physical_lines": sum(item.metrics.physical for item in members),
                "source_lines": sum(item.metrics.source for item in members),
                "behavior_definition_source_lines": sum(
                    item.metrics.behavior_definition_source for item in members
                ),
                "symbol_count": sum(1 for item in symbols if item.category == key),
            }
        )

    dashboard_keys = {key for key, value in CATEGORIES.items() if value.dashboard}
    production_files = [item for item in files if item.category not in dashboard_keys]
    dashboard_files = [item for item in files if item.category in dashboard_keys]
    excluded_by_reason = Counter(item.reason for item in exclusions)
    excluded_lines_by_reason = Counter()
    for item in exclusions:
        excluded_lines_by_reason[item.reason] += item.physical_lines

    functions = [
        item for item in symbols if item.kind in {"function", "async_function"}
    ]
    classes = [item for item in symbols if item.kind == "class"]
    largest_files = sorted(
        files,
        key=lambda item: (-item.metrics.physical, item.path),
    )
    largest_functions = sorted(
        functions,
        key=lambda item: (-item.span, item.path, item.start_line),
    )

    return {
        "schema_version": 1,
        "repository_root": str(root),
        "method": {
            "universe": "git-tracked files only",
            "loc": "physical and nonblank/non-comment source lines are both reported",
            "native_toolsandbox": "excluded by tool_sandbox/ path",
            "generated_outputs": "artifacts/, outputs/, dist/, and build/ are excluded",
            "behavior_definitions": (
                "prompt/policy/contract/example/rule string literals and named catalogs "
                "remain in totals and are additionally identified as a non-additive subset"
            ),
        },
        "totals": {
            "all_sage_source_physical_lines": sum(item.metrics.physical for item in files),
            "all_sage_source_lines": sum(item.metrics.source for item in files),
            "production_excluding_dashboards_physical_lines": sum(
                item.metrics.physical for item in production_files
            ),
            "production_excluding_dashboards_source_lines": sum(
                item.metrics.source for item in production_files
            ),
            "dashboard_source_physical_lines": sum(
                item.metrics.physical for item in dashboard_files
            ),
            "dashboard_source_lines": sum(item.metrics.source for item in dashboard_files),
            "behavior_definition_source_subset": sum(
                item.metrics.behavior_definition_source for item in files
            ),
            "tracked_source_file_count": len(files),
            "function_count": len(functions),
            "class_count": len(classes),
        },
        "categories": category_rows,
        "largest_files": [
            {
                "path": item.path,
                "category": item.category,
                **asdict(item.metrics),
            }
            for item in largest_files
        ],
        "largest_functions": [asdict(item) for item in largest_functions],
        "largest_classes": [
            asdict(item)
            for item in sorted(
                classes, key=lambda item: (-item.span, item.path, item.start_line)
            )
        ],
        "exclusions": {
            "file_count_by_reason": dict(sorted(excluded_by_reason.items())),
            "physical_lines_by_reason": dict(sorted(excluded_lines_by_reason.items())),
            "files": [asdict(item) for item in exclusions],
        },
        "parse_errors": parse_errors,
    }


def _format_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    rendered = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rendered:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = ["  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend(
        "  ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        for row in rendered
    )
    return "\n".join(lines)


def render_text(inventory: dict[str, object], top: int) -> str:
    totals = inventory["totals"]
    assert isinstance(totals, dict)
    categories = inventory["categories"]
    assert isinstance(categories, list)
    largest_files = inventory["largest_files"]
    largest_functions = inventory["largest_functions"]
    assert isinstance(largest_files, list)
    assert isinstance(largest_functions, list)
    exclusions = inventory["exclusions"]
    assert isinstance(exclusions, dict)

    lines = [
        "SAGE source inventory",
        "=====================",
        f"Repository: {inventory['repository_root']}",
        "Scope: git-tracked SAGE-authored source; native ToolSandbox and generated/static output excluded.",
        "",
        "Totals",
        "------",
        f"Production excluding dashboards (physical): {totals['production_excluding_dashboards_physical_lines']:,}",
        f"Production excluding dashboards (source):   {totals['production_excluding_dashboards_source_lines']:,}",
        f"Dashboard source (physical):                 {totals['dashboard_source_physical_lines']:,}",
        f"All SAGE source (physical):                  {totals['all_sage_source_physical_lines']:,}",
        f"Behavior-defining source-line subset:        {totals['behavior_definition_source_subset']:,}",
        f"Functions / classes:                         {totals['function_count']:,} / {totals['class_count']:,}",
        "",
        "Categories",
        "----------",
        _format_table(
            ("category", "files", "physical", "source", "behavior", "symbols"),
            (
                (
                    row["key"],
                    row["file_count"],
                    row["physical_lines"],
                    row["source_lines"],
                    row["behavior_definition_source_lines"],
                    row["symbol_count"],
                )
                for row in categories
            ),
        ),
        "",
        f"Largest {top} source files",
        "-----------------------",
        _format_table(
            ("physical", "source", "behavior", "category", "path"),
            (
                (
                    row["physical"],
                    row["source"],
                    row["behavior_definition_source"],
                    row["category"],
                    row["path"],
                )
                for row in largest_files[:top]
            ),
        ),
        "",
        f"Largest {top} functions",
        "--------------------",
        _format_table(
            ("span", "category", "function", "location"),
            (
                (
                    row["span"],
                    row["category"],
                    row["qualified_name"],
                    f"{row['path']}:{row['start_line']}",
                )
                for row in largest_functions[:top]
            ),
        ),
        "",
        "Excluded tracked material",
        "-------------------------",
        _format_table(
            ("reason", "files", "physical lines"),
            (
                (
                    reason,
                    exclusions["file_count_by_reason"].get(reason, 0),
                    count,
                )
                for reason, count in exclusions["physical_lines_by_reason"].items()
            ),
        ),
    ]
    parse_errors = inventory["parse_errors"]
    if parse_errors:
        lines.extend(("", "Python parse errors", "-------------------", *parse_errors))
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Any path inside the repository (default: current directory).",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    parser.add_argument(
        "--top", type=int, default=20, help="Number of largest files/functions to print."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. If omitted, write to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.top < 1:
        raise SystemExit("--top must be at least 1")
    inventory = build_inventory(args.root)
    if args.format == "json":
        rendered = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_text(inventory, args.top) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 1 if inventory["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
