#!/usr/bin/env python3
"""Compare deterministic probes from independent SAGE checkouts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__:
    from .normalization import (
        AppliedNormalization,
        load_rules,
        normalize_snapshot,
    )
else:
    from normalization import AppliedNormalization, load_rules, normalize_snapshot


HERE = Path(__file__).resolve().parent
SNAPSHOT_SCRIPT = HERE / "snapshot.py"
NORMALIZATION_RULES = HERE / "approved_nondeterminism.json"
DEFAULT_PROBES = (
    "imports",
    "config",
    "evaluator_manifest",
    "splits",
    "outcomes",
    "trajectory",
    "classifier",
    "actor",
    "normalization",
    "validation",
    "routing",
    "lifecycle",
)


def _child_environment() -> dict[str, str]:
    """Create a stable environment without checkout-affecting Python/SAGE state."""

    environment = dict(os.environ)
    for name in list(environment):
        if name.startswith("SAGE_") or name in {"PYTHONHOME", "PYTHONPATH"}:
            environment.pop(name, None)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    return environment


def _run_snapshot(
    *, root: Path, output: Path, python: Path, probes: tuple[str, ...], timeout: int
) -> dict[str, Any]:
    command = [
        str(python),
        "-I",
        str(SNAPSHOT_SCRIPT),
        "--root",
        str(root),
        "--output",
        str(output),
        "--probes",
        ",".join(probes),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        env=_child_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Probe subprocess failed for {root} (exit {completed.returncode})\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return json.loads(output.read_text(encoding="utf-8"))


def _escape_pointer_part(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _diff(reference: Any, candidate: Any, path: str = "") -> list[dict[str, Any]]:
    """Return every semantic difference using stable JSON-pointer paths."""

    if type(reference) is not type(candidate):
        return [
            {
                "path": path or "/",
                "kind": "type_changed",
                "reference": reference,
                "candidate": candidate,
            }
        ]
    if isinstance(reference, dict):
        differences: list[dict[str, Any]] = []
        reference_keys = set(reference)
        candidate_keys = set(candidate)
        for key in sorted(reference_keys - candidate_keys):
            differences.append(
                {
                    "path": f"{path}/{_escape_pointer_part(key)}",
                    "kind": "missing_from_candidate",
                    "reference": reference[key],
                }
            )
        for key in sorted(candidate_keys - reference_keys):
            differences.append(
                {
                    "path": f"{path}/{_escape_pointer_part(key)}",
                    "kind": "added_to_candidate",
                    "candidate": candidate[key],
                }
            )
        for key in sorted(reference_keys & candidate_keys):
            differences.extend(
                _diff(
                    reference[key],
                    candidate[key],
                    f"{path}/{_escape_pointer_part(key)}",
                )
            )
        return differences
    if isinstance(reference, list):
        differences = []
        common = min(len(reference), len(candidate))
        for index in range(common):
            differences.extend(
                _diff(reference[index], candidate[index], f"{path}/{index}")
            )
        for index in range(common, len(reference)):
            differences.append(
                {
                    "path": f"{path}/{index}",
                    "kind": "missing_from_candidate",
                    "reference": reference[index],
                }
            )
        for index in range(common, len(candidate)):
            differences.append(
                {
                    "path": f"{path}/{index}",
                    "kind": "added_to_candidate",
                    "candidate": candidate[index],
                }
            )
        return differences
    if reference != candidate:
        return [
            {
                "path": path or "/",
                "kind": "value_changed",
                "reference": reference,
                "candidate": candidate,
            }
        ]
    return []


def _applied_payload(items: list[AppliedNormalization]) -> list[dict[str, str]]:
    return [
        {"path": item.path, "pattern": item.pattern, "action": item.action}
        for item in items
    ]


def _write_report(path: Path | None, report: dict[str, Any]) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run each checkout in an isolated subprocess and fail on every "
            "difference except fields in the reviewed normalization allowlist."
        )
    )
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--probes",
        default=",".join(DEFAULT_PROBES),
        help=f"Comma-separated probes (default: {', '.join(DEFAULT_PROBES)})",
    )
    args = parser.parse_args()
    reference_root = args.reference_root.expanduser().resolve()
    candidate_root = args.candidate_root.expanduser().resolve()
    python = args.python.expanduser().resolve()
    probes = tuple(item.strip() for item in args.probes.split(",") if item.strip())
    if not probes:
        parser.error("at least one probe is required")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        rules = load_rules(NORMALIZATION_RULES)
        with tempfile.TemporaryDirectory(prefix="sage-replay-") as temporary:
            temporary_root = Path(temporary)
            reference = _run_snapshot(
                root=reference_root,
                output=temporary_root / "reference.json",
                python=python,
                probes=probes,
                timeout=args.timeout,
            )
            candidate = _run_snapshot(
                root=candidate_root,
                output=temporary_root / "candidate.json",
                python=python,
                probes=probes,
                timeout=args.timeout,
            )
        normalized_reference, reference_normalizations = normalize_snapshot(
            reference, rules
        )
        normalized_candidate, candidate_normalizations = normalize_snapshot(
            candidate, rules
        )
        differences = _diff(normalized_reference, normalized_candidate)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report = {
            "schema_version": 1,
            "status": "probe_error",
            "reference_root": str(reference_root),
            "candidate_root": str(candidate_root),
            "probes": list(probes),
            "error": str(exc),
        }
        _write_report(args.output, report)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = {
        "schema_version": 1,
        "status": "equivalent" if not differences else "different",
        "reference_root": str(reference_root),
        "candidate_root": str(candidate_root),
        "probes": list(probes),
        "approved_normalizations": {
            "reference": _applied_payload(reference_normalizations),
            "candidate": _applied_payload(candidate_normalizations),
        },
        "difference_count": len(differences),
        "differences": differences,
    }
    _write_report(args.output, report)
    if differences:
        print(f"FAIL: {len(differences)} unapproved difference(s)")
        for difference in differences[:20]:
            print(f"  {difference['path']}: {difference['kind']}")
        if len(differences) > 20:
            print(f"  ... {len(differences) - 20} more (see JSON report)")
        return 1
    print(
        "PASS: reference and candidate snapshots are equivalent "
        f"for {', '.join(probes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
