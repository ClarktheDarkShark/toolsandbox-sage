"""Canonical byte identity for publication generated-tool registries."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path
from typing import Any

REGISTRY_CONTENT_IDENTITY_SCHEMA_VERSION = 1
REGISTRY_CONTENT_IDENTITY_ARTIFACT_TYPE = "sage_registry_content_identity"
REQUIRED_REGISTRY_FILES = (
    "registry_manifest.json",
    "tool_lifecycle.json",
)


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_required_registry_json(path: Path, required_field: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read required registry file {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get(required_field), dict
    ):
        raise ValueError(
            f"Required registry file {path} must contain object field "
            f"{required_field!r}."
        )
    return payload


def _registry_files(registry_root: Path) -> list[Path]:
    if registry_root.is_symlink():
        raise ValueError(f"Registry root must not be a symlink: {registry_root}")
    if not registry_root.exists():
        return []
    if not registry_root.is_dir():
        raise ValueError(f"Registry root is not a directory: {registry_root}")

    files: list[Path] = []
    for path in registry_root.rglob("*"):
        relative = path.relative_to(registry_root).as_posix()
        if path.is_symlink():
            raise ValueError(f"Registry content must not contain symlinks: {relative}")
        mode = path.stat(follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(
                f"Registry content must contain only directories and regular files: "
                f"{relative}"
            )
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(registry_root).as_posix())


def registry_content_identity(
    registry_root: Path,
    *,
    require_complete: bool,
) -> dict[str, Any]:
    """Return a path-independent manifest and digest of exact registry bytes."""

    registry_root = Path(registry_root)
    paths = _registry_files(registry_root)
    relative_paths = {
        path.relative_to(registry_root).as_posix(): path for path in paths
    }
    missing = [name for name in REQUIRED_REGISTRY_FILES if name not in relative_paths]
    if require_complete and missing:
        raise ValueError(
            "Complete publication registry is missing required files: "
            + ", ".join(missing)
        )

    helper_entry_count: int | None = None
    if "registry_manifest.json" in relative_paths:
        registry_manifest = _read_required_registry_json(
            relative_paths["registry_manifest.json"], "tools"
        )
        helper_entry_count = len(registry_manifest["tools"])
    if "tool_lifecycle.json" in relative_paths:
        _read_required_registry_json(
            relative_paths["tool_lifecycle.json"], "tool_lifecycle"
        )

    file_records = [
        {
            "path": path.relative_to(registry_root).as_posix(),
            "size": path.stat(follow_symlinks=False).st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
    ]
    by_name = {record["path"]: record for record in file_records}
    material: dict[str, Any] = {
        "schema_version": REGISTRY_CONTENT_IDENTITY_SCHEMA_VERSION,
        "artifact_type": REGISTRY_CONTENT_IDENTITY_ARTIFACT_TYPE,
        "coverage": "all_regular_files_recursively",
        "required_files": list(REQUIRED_REGISTRY_FILES),
        "complete": not missing,
        "file_count": len(file_records),
        "helper_entry_count": helper_entry_count,
        "registry_manifest_sha256": (by_name.get("registry_manifest.json") or {}).get(
            "sha256"
        ),
        "tool_lifecycle_sha256": (by_name.get("tool_lifecycle.json") or {}).get(
            "sha256"
        ),
        "files": file_records,
    }
    return {
        **material,
        "content_sha256": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
    }


def validate_registry_content_identity(identity: object) -> dict[str, Any]:
    """Validate a stored identity, including its canonical aggregate digest."""

    if not isinstance(identity, dict):
        raise ValueError("Registry content identity must be a JSON object.")
    expected_fields = {
        "schema_version",
        "artifact_type",
        "coverage",
        "required_files",
        "complete",
        "file_count",
        "helper_entry_count",
        "registry_manifest_sha256",
        "tool_lifecycle_sha256",
        "files",
        "content_sha256",
    }
    if set(identity) != expected_fields:
        raise ValueError("Registry content identity fields are incomplete or unknown.")
    if (
        identity.get("schema_version") != REGISTRY_CONTENT_IDENTITY_SCHEMA_VERSION
        or identity.get("artifact_type") != REGISTRY_CONTENT_IDENTITY_ARTIFACT_TYPE
        or identity.get("coverage") != "all_regular_files_recursively"
        or identity.get("required_files") != list(REQUIRED_REGISTRY_FILES)
        or not isinstance(identity.get("complete"), bool)
    ):
        raise ValueError("Registry content identity metadata is invalid.")
    files = identity.get("files")
    if not isinstance(files, list) or not all(isinstance(row, dict) for row in files):
        raise ValueError("Registry content identity files must be a list of objects.")
    paths: list[str] = []
    by_name: dict[str, dict[str, Any]] = {}
    for row in files:
        if set(row) != {"path", "size", "sha256"}:
            raise ValueError("Registry content identity file record is invalid.")
        relative = row.get("path")
        size = row.get("size")
        digest = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("Registry content identity file record is malformed.")
        paths.append(relative)
        by_name[relative] = row
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError(
            "Registry content identity file paths are not unique and sorted."
        )
    if identity.get("file_count") != len(files):
        raise ValueError("Registry content identity file count is invalid.")
    missing = [name for name in REQUIRED_REGISTRY_FILES if name not in by_name]
    if identity.get("complete") is not (not missing):
        raise ValueError("Registry content identity completeness flag is invalid.")
    if identity.get("registry_manifest_sha256") != (
        by_name.get("registry_manifest.json") or {}
    ).get("sha256") or identity.get("tool_lifecycle_sha256") != (
        by_name.get("tool_lifecycle.json") or {}
    ).get("sha256"):
        raise ValueError("Registry content identity primary-file digests are invalid.")
    helper_count = identity.get("helper_entry_count")
    if helper_count is not None and (
        isinstance(helper_count, bool)
        or not isinstance(helper_count, int)
        or helper_count < 0
    ):
        raise ValueError("Registry content identity helper count is invalid.")
    material = {
        key: value for key, value in identity.items() if key != "content_sha256"
    }
    observed_digest = identity.get("content_sha256")
    expected_digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
    if observed_digest != expected_digest:
        raise ValueError("Registry content identity aggregate digest is invalid.")
    return dict(identity)


def write_registry_content_identity(
    output_path: Path,
    identity: dict[str, Any],
) -> None:
    """Write a validated identity using deterministic human-readable JSON."""

    validated = validate_registry_content_identity(identity)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")


def _read_identity(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Cannot read registry content identity {path}: {exc}"
        ) from exc
    return validate_registry_content_identity(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--expect-identity", type=Path)
    parser.add_argument("--expect-sha256")
    args = parser.parse_args()
    try:
        identity = registry_content_identity(
            args.registry_root,
            require_complete=args.require_complete,
        )
        if args.expect_identity is not None:
            expected = _read_identity(args.expect_identity)
            if identity != expected:
                raise ValueError(
                    "Registry bytes do not match the expected canonical identity."
                )
        if (
            args.expect_sha256 is not None
            and identity["content_sha256"] != args.expect_sha256
        ):
            raise ValueError(
                "Registry bytes do not match the expected canonical SHA-256."
            )
        write_registry_content_identity(args.output, identity)
    except ValueError as exc:
        raise SystemExit(f"registry_content_identity=failed\n{exc}") from exc
    print("registry_content_identity=pass")
    print(identity["content_sha256"])


if __name__ == "__main__":
    main()
