#!/usr/bin/env python3
"""Fail closed unless the active publication Python environment is exact.

The publication launcher calls this verifier before making any model request.
External distributions must match the version-pinned lock one-for-one.  The only
unlocked metadata allowed is editable/source metadata for this repository's
``tool-sandbox`` and ``toolsandbox-sage`` distributions; the Git commit and
tree bind that code separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import distributions
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = REPO_ROOT / "requirements-publication-lock.txt"
PINNED_LOCK_SHA256 = "5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f"
REQUIRED_PYTHON_VERSION = (3, 12, 7)
REQUIRED_PYTHON_IMPLEMENTATION = "CPython"
REQUIRED_PLATFORM_SYSTEM = "Darwin"
REQUIRED_PLATFORM_MACHINE = "arm64"
REPOSITORY_DISTRIBUTIONS = frozenset({"tool-sandbox", "toolsandbox-sage"})
REQUIRED_EDITABLE_PROJECT = ("toolsandbox-sage", "0.1.0")
_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")


class EnvironmentVerificationError(ValueError):
    """Raised when the active interpreter does not match the publication lock."""


@dataclass(frozen=True)
class DistributionRecord:
    """Installed-distribution metadata needed for exact environment checks."""

    name: str
    version: str
    metadata_path: Path
    direct_url_json: str | None = None


def canonicalize_name(name: str) -> str:
    """Return the PEP 503 normalized distribution name."""

    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_lock(lock_path: Path) -> dict[str, tuple[str, str]]:
    if not lock_path.is_file():
        raise EnvironmentVerificationError(
            f"Publication environment lock is missing: {lock_path}"
        )
    locked: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LOCK_LINE.fullmatch(line)
        if match is None:
            raise EnvironmentVerificationError(
                "Publication environment lock must contain only exact, unmarked "
                f"name==version entries; line {line_number} is invalid: {line!r}"
            )
        display_name, version = match.groups()
        canonical_name = canonicalize_name(display_name)
        if canonical_name in REPOSITORY_DISTRIBUTIONS:
            raise EnvironmentVerificationError(
                f"Repository distribution {display_name!r} must not be in the "
                "external environment lock"
            )
        if canonical_name in locked:
            raise EnvironmentVerificationError(
                f"Duplicate distribution in publication lock: {display_name!r}"
            )
        locked[canonical_name] = (display_name, version)
    if not locked:
        raise EnvironmentVerificationError("Publication environment lock is empty")
    return locked


def _installed_distribution_records() -> tuple[DistributionRecord, ...]:
    records: list[DistributionRecord] = []
    for distribution in distributions():
        name = str(distribution.metadata.get("Name") or "").strip()
        version = str(distribution.version or "").strip()
        metadata_path_value = getattr(distribution, "_path", None)
        if metadata_path_value is None:
            metadata_path = Path(str(distribution.locate_file(""))).resolve()
        else:
            metadata_path = Path(str(metadata_path_value)).resolve()
        records.append(
            DistributionRecord(
                name=name,
                version=version,
                metadata_path=metadata_path,
                direct_url_json=distribution.read_text("direct_url.json"),
            )
        )
    return tuple(records)


def _editable_repository_url(direct_url_json: str | None, repo_root: Path) -> bool:
    if not direct_url_json:
        return False
    try:
        payload = json.loads(direct_url_json)
        parsed = urlparse(str(payload.get("url") or ""))
        editable = (payload.get("dir_info") or {}).get("editable") is True
        if parsed.scheme != "file" or not editable:
            return False
        source = Path(unquote(parsed.path)).resolve()
    except (AttributeError, json.JSONDecodeError, OSError, TypeError, ValueError):
        return False
    return source == repo_root or _is_relative_to(source, repo_root)


def _is_repository_distribution(record: DistributionRecord, repo_root: Path) -> bool:
    name = canonicalize_name(record.name)
    if name not in REPOSITORY_DISTRIBUTIONS:
        return False
    metadata_path = record.metadata_path.resolve()
    return _is_relative_to(metadata_path, repo_root) or _editable_repository_url(
        record.direct_url_json, repo_root
    )


def _run_pip_check() -> str:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentVerificationError(f"pip dependency check could not run: {exc}")
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0:
        detail = output or f"exit status {completed.returncode}"
        raise EnvironmentVerificationError(f"pip dependency check failed: {detail}")
    return output or "pip check passed"


def verify_environment(
    lock_path: Path = DEFAULT_LOCK,
    *,
    repo_root: Path = REPO_ROOT,
    expected_lock_sha256: str = PINNED_LOCK_SHA256,
    expected_python_version: tuple[int, int, int] = REQUIRED_PYTHON_VERSION,
    python_version: tuple[int, int, int] | None = None,
    python_executable: str | None = None,
    python_prefix: str | None = None,
    python_base_prefix: str | None = None,
    python_implementation: str | None = None,
    platform_system: str | None = None,
    platform_machine: str | None = None,
    installed_distributions: Iterable[DistributionRecord] | None = None,
    pip_checker: Callable[[], str] | None = None,
) -> dict[str, object]:
    """Verify and describe the active, exact publication runtime."""

    lock_path = lock_path.resolve()
    repo_root = repo_root.resolve()
    observed_python = python_version or (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    if observed_python != expected_python_version:
        required = ".".join(str(value) for value in expected_python_version)
        observed = ".".join(str(value) for value in observed_python)
        raise EnvironmentVerificationError(
            f"Publication runs require Python {required} exactly; observed {observed}"
        )
    observed_prefix = str(Path(python_prefix or sys.prefix).absolute())
    observed_base_prefix = str(Path(python_base_prefix or sys.base_prefix).absolute())
    if observed_prefix == observed_base_prefix:
        raise EnvironmentVerificationError(
            "Publication runs require an isolated virtual environment "
            "(sys.prefix must differ from sys.base_prefix)"
        )
    observed_implementation = python_implementation or platform.python_implementation()
    observed_system = platform_system or platform.system()
    observed_machine = platform_machine or platform.machine()
    if observed_implementation != REQUIRED_PYTHON_IMPLEMENTATION:
        raise EnvironmentVerificationError(
            "Publication runs require "
            f"{REQUIRED_PYTHON_IMPLEMENTATION}; observed {observed_implementation}"
        )
    if (observed_system, observed_machine) != (
        REQUIRED_PLATFORM_SYSTEM,
        REQUIRED_PLATFORM_MACHINE,
    ):
        raise EnvironmentVerificationError(
            "Publication runs require the validated platform "
            f"{REQUIRED_PLATFORM_SYSTEM}/{REQUIRED_PLATFORM_MACHINE}; observed "
            f"{observed_system}/{observed_machine}"
        )

    observed_lock_sha256 = _sha256(lock_path) if lock_path.is_file() else "missing"
    if observed_lock_sha256 != expected_lock_sha256:
        raise EnvironmentVerificationError(
            "Publication environment lock hash mismatch: expected "
            f"{expected_lock_sha256}, observed {observed_lock_sha256}"
        )
    locked = _read_lock(lock_path)

    records = tuple(
        _installed_distribution_records()
        if installed_distributions is None
        else installed_distributions
    )
    external: dict[str, tuple[str, str, Path]] = {}
    repository_metadata: list[dict[str, str | bool]] = []
    unidentified: list[str] = []
    duplicate_external: list[str] = []
    for record in records:
        if not record.name or not record.version:
            unidentified.append(str(record.metadata_path))
            continue
        canonical_name = canonicalize_name(record.name)
        if _is_repository_distribution(record, repo_root):
            editable = _editable_repository_url(record.direct_url_json, repo_root)
            repository_metadata.append(
                {
                    "name": canonical_name,
                    "version": record.version,
                    "metadata_path": str(record.metadata_path),
                    "editable": editable,
                }
            )
            continue
        if canonical_name in external:
            duplicate_external.append(canonical_name)
            continue
        external[canonical_name] = (record.name, record.version, record.metadata_path)

    missing = sorted(set(locked) - set(external))
    unexpected = sorted(set(external) - set(locked))
    mismatched = sorted(
        name
        for name in set(locked) & set(external)
        if external[name][1] != locked[name][1]
    )
    errors: list[str] = []
    if unidentified:
        errors.append("unidentified metadata: " + ", ".join(sorted(unidentified)))
    if duplicate_external:
        errors.append(
            "duplicate external distributions: "
            + ", ".join(sorted(set(duplicate_external)))
        )
    if missing:
        errors.append("missing locked distributions: " + ", ".join(missing))
    if unexpected:
        details = [
            f"{external[name][0]}=={external[name][1]} ({external[name][2]})"
            for name in unexpected
        ]
        errors.append("unexpected external distributions: " + ", ".join(details))
    if mismatched:
        details = [
            f"{name}: expected {locked[name][1]}, observed {external[name][1]}"
            for name in mismatched
        ]
        errors.append("version mismatches: " + ", ".join(details))
    required_project, required_project_version = REQUIRED_EDITABLE_PROJECT
    if not any(
        item["name"] == required_project
        and item["version"] == required_project_version
        and item["editable"] is True
        for item in repository_metadata
    ):
        errors.append(
            "missing repository-local editable metadata for "
            f"{required_project}=={required_project_version}"
        )
    if errors:
        raise EnvironmentVerificationError("; ".join(errors))

    pip_check_output = (pip_checker or _run_pip_check)()
    executable = str(Path(python_executable or sys.executable).absolute())
    version_text = ".".join(str(value) for value in observed_python)
    external_distribution_entries = sorted(
        f"{name}=={record[1]}\n" for name, record in external.items()
    )
    external_distribution_bytes = "".join(external_distribution_entries).encode("utf-8")
    external_distribution_sha256 = hashlib.sha256(
        external_distribution_bytes
    ).hexdigest()
    return {
        "schema_version": 1,
        "status": "pass",
        "python_executable": executable,
        "python_version": version_text,
        "python_implementation": observed_implementation,
        "python_prefix": observed_prefix,
        "python_base_prefix": observed_base_prefix,
        "isolated_environment": True,
        "platform_system": observed_system,
        "platform_machine": observed_machine,
        "environment_lock_path": str(lock_path),
        "environment_lock_sha256": observed_lock_sha256,
        "external_distribution_count": len(external),
        "external_distribution_sha256": external_distribution_sha256,
        "repository_distribution_metadata": sorted(
            repository_metadata,
            key=lambda item: (item["name"], item["metadata_path"]),
        ),
        "pip_check": pip_check_output,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the verified environment report as JSON.",
    )
    args = parser.parse_args()
    try:
        report = verify_environment(args.lock)
    except (EnvironmentVerificationError, OSError, UnicodeError) as exc:
        raise SystemExit(f"publication_environment_verification=failed\n{exc}") from exc
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("publication_environment_verification=pass")
        print(f"python_executable={report['python_executable']}")
        print(f"python_version={report['python_version']}")
        print(f"python_prefix={report['python_prefix']}")
        print(f"python_base_prefix={report['python_base_prefix']}")
        print(f"platform={report['platform_system']}/{report['platform_machine']}")
        print(f"environment_lock={report['environment_lock_path']}")
        print(f"environment_lock_sha256={report['environment_lock_sha256']}")
        print(f"external_distribution_count={report['external_distribution_count']}")
        print(f"external_distribution_sha256={report['external_distribution_sha256']}")


if __name__ == "__main__":
    main()
