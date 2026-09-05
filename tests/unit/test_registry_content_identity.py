from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from sage_ts.registry.content_identity import (
    registry_content_identity,
    validate_registry_content_identity,
)


def _complete_registry(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "registry_manifest.json").write_text(
        json.dumps(
            {
                "tools": {
                    "helper": {"tool": {"code": "def helper() -> int:\n    return 1\n"}}
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "tool_lifecycle.json").write_text(
        '{"tool_lifecycle":{"helper":{"decision":"retain"}}}\n',
        encoding="utf-8",
    )
    sidecar = root / "helper_artifacts" / "proof.bin"
    sidecar.parent.mkdir()
    sidecar.write_bytes(b"exact helper proof bytes\x00\xff")
    return root


def test_registry_identity_is_path_independent_and_covers_every_file(
    tmp_path: Path,
) -> None:
    source = _complete_registry(tmp_path / "source")
    copied = tmp_path / "copied"
    shutil.copytree(source, copied)

    source_identity = registry_content_identity(source, require_complete=True)
    copied_identity = registry_content_identity(copied, require_complete=True)

    assert source_identity == copied_identity
    assert source_identity["file_count"] == 3
    assert source_identity["helper_entry_count"] == 1
    assert [row["path"] for row in source_identity["files"]] == [
        "helper_artifacts/proof.bin",
        "registry_manifest.json",
        "tool_lifecycle.json",
    ]

    (copied / "helper_artifacts" / "proof.bin").write_bytes(b"mutated")
    assert registry_content_identity(copied, require_complete=True) != source_identity


def test_complete_registry_identity_requires_both_primary_artifacts(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "registry_manifest.json").write_text('{"tools":{}}\n')

    with pytest.raises(ValueError, match="tool_lifecycle.json"):
        registry_content_identity(registry, require_complete=True)


def test_registry_identity_rejects_symlinked_content(tmp_path: Path) -> None:
    registry = _complete_registry(tmp_path / "registry")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (registry / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="must not contain symlinks"):
        registry_content_identity(registry, require_complete=True)


def test_registry_identity_rejects_tampered_aggregate_digest(tmp_path: Path) -> None:
    identity = registry_content_identity(
        _complete_registry(tmp_path / "registry"),
        require_complete=True,
    )
    tampered = copy.deepcopy(identity)
    tampered["files"][0]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="aggregate digest"):
        validate_registry_content_identity(tampered)
