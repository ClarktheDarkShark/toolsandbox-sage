#!/usr/bin/env python3
"""Verify that ``make package`` produces a clean, reproducible wheel.

This is deliberately external validation infrastructure. It builds an exact
candidate commit in a disposable clone, poisons ignored build state, and then
compares the wheel's application payload with the bytes stored in Git.
"""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
from typing import Any, Mapping, Sequence
import zipfile


REQUIRED_ENTRY_POINTS = {
    "sage-build-chapter4-evolution": (
        "scripts.build_chapter4_evolution_dashboard:main"
    ),
    "sage-dashboard": "sage_ts.dashboard.server:main",
    "sage-protocol": "scripts.run_sage_protocol:main",
    "tool_sandbox": "tool_sandbox.cli:main",
}
POISON_MARKER = b"SAGE_STALE_BUILD_POISON_9d2d85c7"
POISON_MODULE = "stale_release_sentinel_9d2d85c7.py"


class VerificationError(RuntimeError):
    """Raised when the candidate violates the release packaging contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        output = result.stdout.decode("utf-8", errors="replace")
        raise VerificationError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{output}"
        )
    return result


def git_archive_files(repository: Path, revision: str) -> dict[str, bytes]:
    """Return regular-file bytes from a revision without reading its checkout."""

    archive = _run(
        ["git", "-C", str(repository), "archive", "--format=tar", revision]
    ).stdout
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            handle = bundle.extractfile(member)
            if handle is None:
                raise VerificationError(f"could not read archive member {member.name}")
            files[member.name] = handle.read()
    return files


def _matches_package(
    package: str,
    includes: Sequence[str],
    excludes: Sequence[str],
) -> bool:
    included = not includes or any(
        fnmatch.fnmatchcase(package, pattern) for pattern in includes
    )
    excluded = any(fnmatch.fnmatchcase(package, pattern) for pattern in excludes)
    return included and not excluded


def _discover_packages(
    archive_files: Mapping[str, bytes],
    config: Mapping[str, Any],
) -> list[tuple[str, str]]:
    """Discover regular (non-namespace) packages using committed files only."""

    try:
        find = config["tool"]["setuptools"]["packages"]["find"]
    except (KeyError, TypeError) as error:
        raise VerificationError(
            "pyproject lacks [tool.setuptools.packages.find]"
        ) from error

    if find.get("namespaces", True) is not False:
        raise VerificationError("packaging verifier requires namespaces = false")

    where = tuple(str(value).strip("/") for value in find.get("where", ["."]))
    includes = tuple(str(value) for value in find.get("include", []))
    excludes = tuple(str(value) for value in find.get("exclude", []))
    archive_names = set(archive_files)
    packages: dict[str, str] = {}

    for source_root in where:
        root = "" if source_root in {"", "."} else f"{source_root}/"
        for filename in archive_names:
            if not filename.endswith("/__init__.py") or not filename.startswith(root):
                continue
            package_dir = filename[: -len("/__init__.py")]
            relative_dir = package_dir[len(root) :]
            if not relative_dir:
                continue
            parts = relative_dir.split("/")
            # With namespaces disabled, every directory from the configured
            # source root to this package must itself be a package.
            if any(
                f"{root}{'/'.join(parts[:index])}/__init__.py" not in archive_names
                for index in range(1, len(parts))
            ):
                continue
            package = ".".join(parts)
            if not _matches_package(package, includes, excludes):
                continue
            previous = packages.get(package_dir)
            if previous is not None and previous != package:
                raise VerificationError(
                    f"ambiguous package mapping for {package_dir}: {previous}, {package}"
                )
            packages[package_dir] = package

    if not packages:
        raise VerificationError("no packages were discovered from the Git archive")
    return sorted(packages.items())


def derive_application_payload(
    archive_files: Mapping[str, bytes],
) -> dict[str, bytes]:
    """Map committed package sources to their exact paths inside the wheel."""

    try:
        pyproject_bytes = archive_files["pyproject.toml"]
    except KeyError as error:
        raise VerificationError(
            "Git archive does not contain pyproject.toml"
        ) from error
    config = tomllib.loads(pyproject_bytes.decode("utf-8"))
    packages = _discover_packages(archive_files, config)
    package_data = config.get("tool", {}).get("setuptools", {}).get("package-data", {})
    payload: dict[str, bytes] = {}

    for package_dir, package in packages:
        package_prefix = f"{package_dir}/"
        wheel_prefix = package.replace(".", "/")
        patterns: list[str] = []
        for key in ("*", package):
            patterns.extend(str(value) for value in package_data.get(key, []))

        for source_name, source_bytes in archive_files.items():
            if not source_name.startswith(package_prefix):
                continue
            relative = source_name[len(package_prefix) :]
            if "/" in relative:
                continue
            include = relative.endswith(".py") or any(
                fnmatch.fnmatchcase(relative, pattern) for pattern in patterns
            )
            if not include:
                continue
            wheel_name = f"{wheel_prefix}/{relative}"
            previous = payload.get(wheel_name)
            if previous is not None and previous != source_bytes:
                raise VerificationError(f"conflicting source bytes for {wheel_name}")
            payload[wheel_name] = source_bytes

    if not payload:
        raise VerificationError("derived wheel application payload is empty")
    return dict(sorted(payload.items()))


def inspect_wheel(wheel: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Read application files and console entry points from a wheel."""

    application: dict[str, bytes] = {}
    entry_point_files: list[str] = []
    all_entries: dict[str, bytes] = {}
    with zipfile.ZipFile(wheel) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            data = bundle.read(info.filename)
            all_entries[info.filename] = data
            first_component = info.filename.split("/", 1)[0]
            if first_component.endswith(".dist-info"):
                if info.filename.endswith(".dist-info/entry_points.txt"):
                    entry_point_files.append(info.filename)
                continue
            application[info.filename] = data

    if len(entry_point_files) != 1:
        raise VerificationError(
            f"expected one entry_points.txt, found {len(entry_point_files)}"
        )
    if any(POISON_MARKER in data for data in all_entries.values()):
        raise VerificationError("ignored build poison leaked into the wheel")
    if any(POISON_MODULE in name for name in all_entries):
        raise VerificationError("stale ignored module leaked into the wheel")

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(all_entries[entry_point_files[0]].decode("utf-8"))
    sections = set(parser.sections())
    if sections != {"console_scripts"}:
        raise VerificationError(
            f"entry-point sections differ: expected console_scripts, got {sorted(sections)}"
        )
    entries = {name: value.strip() for name, value in parser["console_scripts"].items()}
    return dict(sorted(application.items())), dict(sorted(entries.items()))


def compare_application_payload(
    expected: Mapping[str, bytes],
    actual: Mapping[str, bytes],
) -> None:
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    changed = sorted(
        name for name in set(expected) & set(actual) if expected[name] != actual[name]
    )
    if missing or unexpected or changed:
        details = {
            "missing": missing,
            "unexpected": unexpected,
            "changed": changed,
        }
        raise VerificationError(
            "wheel application payload differs from committed sources:\n"
            + json.dumps(details, indent=2)
        )


def verify_entry_points(actual: Mapping[str, str]) -> None:
    if dict(actual) != REQUIRED_ENTRY_POINTS:
        raise VerificationError(
            "console entry points differ:\n"
            + json.dumps(
                {"expected": REQUIRED_ENTRY_POINTS, "actual": dict(actual)},
                indent=2,
                sort_keys=True,
            )
        )


def _release_environment() -> dict[str, str]:
    environment = os.environ.copy()
    # The package target, rather than this verifier, owns reproducible-time
    # configuration. Remove ambient values that could make a bad target pass.
    environment.pop("SOURCE_DATE_EPOCH", None)
    environment.pop("PYTHONPATH", None)
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    environment["TZ"] = "UTC"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _single_wheel(directory: Path) -> Path:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise VerificationError(
            f"expected one wheel in {directory}, found {[path.name for path in wheels]}"
        )
    return wheels[0]


def _run_package(
    checkout: Path,
    output: Path,
    *,
    python: Path,
    make: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    output.mkdir(parents=True, exist_ok=True)
    return _run(
        [make, "package", f"PYTHON={python}", f"DIST_DIR={output}"],
        cwd=checkout,
        env=_release_environment(),
        check=check,
    )


def _poison_ignored_build_state(checkout: Path) -> None:
    poison_paths = [
        checkout / "build/lib/sage_ts/__init__.py",
        checkout / f"build/lib/sage_ts/{POISON_MODULE}",
        checkout / f"build/lib/tool_sandbox/{POISON_MODULE}",
        checkout / "toolsandbox_sage.egg-info/SOURCES.txt",
        checkout / "src/toolsandbox_sage.egg-info/SOURCES.txt",
    ]
    for path in poison_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(POISON_MARKER + b"\n" + POISON_MODULE.encode() + b"\n")

    status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout
    ).stdout
    if status:
        raise VerificationError(
            "poison fixture is not fully ignored by Git:\n"
            + status.decode("utf-8", errors="replace")
        )


def _assert_dirty_rejected(
    checkout: Path,
    output: Path,
    *,
    python: Path,
    make: str,
    label: str,
) -> None:
    result = _run_package(
        checkout,
        output,
        python=python,
        make=make,
        check=False,
    )
    if result.returncode == 0:
        raise VerificationError(f"make package accepted a {label} working tree")
    if list(output.glob("*.whl")):
        raise VerificationError(
            f"make package left a wheel after rejecting a {label} working tree"
        )


def _verify_isolated_imports(
    wheel: Path,
    *,
    python: Path,
    install_target: Path,
) -> None:
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--no-deps",
            "--target",
            str(install_target),
            str(wheel),
        ],
        env=_release_environment(),
    )
    import_code = r"""
import importlib
import json
from pathlib import Path
import sys

target = Path(sys.argv[1]).resolve()
entry_points = json.loads(sys.argv[2])
sys.path.insert(0, str(target))
for root_name in ("sage_ts", "scripts", "tool_sandbox"):
    module = importlib.import_module(root_name)
    module_path = Path(module.__file__).resolve()
    if not module_path.is_relative_to(target):
        raise RuntimeError(f"{root_name} imported outside target: {module_path}")
for specification in entry_points.values():
    module_name, attribute_path = specification.split(":", 1)
    value = importlib.import_module(module_name)
    for part in attribute_path.split("."):
        value = getattr(value, part)
    if not callable(value):
        raise RuntimeError(f"entry point is not callable: {specification}")
"""
    _run(
        [
            str(python),
            "-I",
            "-c",
            import_code,
            str(install_target),
            json.dumps(REQUIRED_ENTRY_POINTS, sort_keys=True),
        ],
        env=_release_environment(),
    )


def verify_candidate(
    candidate_root: Path,
    *,
    python: Path,
    make: str = "make",
    separation_seconds: float = 3.0,
) -> dict[str, Any]:
    candidate_root = candidate_root.resolve()
    python = python.resolve()
    if not (candidate_root / ".git").exists():
        raise VerificationError(f"not a Git checkout: {candidate_root}")
    status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=candidate_root,
    ).stdout
    if status:
        raise VerificationError(
            "candidate checkout is dirty; commit or remove tracked/untracked changes:\n"
            + status.decode("utf-8", errors="replace")
        )
    head = (
        _run(["git", "rev-parse", "HEAD"], cwd=candidate_root)
        .stdout.decode("ascii")
        .strip()
    )
    archive_files = git_archive_files(candidate_root, head)
    expected_payload = derive_application_payload(archive_files)

    with tempfile.TemporaryDirectory(prefix="sage-wheel-verify-") as temporary:
        workspace = Path(temporary)
        checkout = workspace / "candidate"
        _run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                str(candidate_root),
                str(checkout),
            ]
        )
        _run(["git", "checkout", "--quiet", "--detach", head], cwd=checkout)
        _poison_ignored_build_state(checkout)

        first_output = workspace / "dist-first"
        second_output = workspace / "dist-second"
        _run_package(checkout, first_output, python=python, make=make)
        first_wheel = _single_wheel(first_output)
        if separation_seconds:
            time.sleep(separation_seconds)
        _run_package(checkout, second_output, python=python, make=make)
        second_wheel = _single_wheel(second_output)

        first_bytes = first_wheel.read_bytes()
        second_bytes = second_wheel.read_bytes()
        if first_wheel.name != second_wheel.name:
            raise VerificationError(
                "same HEAD produced different wheel names: "
                f"{first_wheel.name}, {second_wheel.name}"
            )
        if first_bytes != second_bytes:
            raise VerificationError(
                "same HEAD produced non-identical wheel bytes: "
                f"{sha256_bytes(first_bytes)} != {sha256_bytes(second_bytes)}"
            )

        actual_payload, entry_points = inspect_wheel(second_wheel)
        compare_application_payload(expected_payload, actual_payload)
        verify_entry_points(entry_points)
        _verify_isolated_imports(
            second_wheel,
            python=python,
            install_target=workspace / "installed",
        )

        untracked = checkout / "release-dirty-sentinel.txt"
        untracked.write_text("untracked release dirt\n", encoding="utf-8")
        _assert_dirty_rejected(
            checkout,
            workspace / "dist-untracked",
            python=python,
            make=make,
            label="tree with an untracked file",
        )
        untracked.unlink()

        readme = checkout / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\ntracked release dirt\n")
        _assert_dirty_rejected(
            checkout,
            workspace / "dist-tracked",
            python=python,
            make=make,
            label="tree with a modified tracked file",
        )

        return {
            "status": "pass",
            "head": head,
            "wheel": second_wheel.name,
            "wheel_sha256": sha256_bytes(second_bytes),
            "archive_application_files": len(expected_payload),
            "entry_points": entry_points,
            "checks": {
                "tracked_dirty_rejected": True,
                "untracked_dirty_rejected": True,
                "poisoned_ignored_state_excluded": True,
                "archive_payload_names_and_bytes_exact": True,
                "isolated_target_imports": True,
                "same_head_wheels_identical": True,
            },
        }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--make", default=shutil.which("make") or "make")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--separation-seconds",
        type=float,
        default=3.0,
        help="delay between builds to expose timestamp-dependent wheels",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(argv)
    try:
        report = verify_candidate(
            arguments.candidate_root,
            python=arguments.python,
            make=arguments.make,
            separation_seconds=arguments.separation_seconds,
        )
    except VerificationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
