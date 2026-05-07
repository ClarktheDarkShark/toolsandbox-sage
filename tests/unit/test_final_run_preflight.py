from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _load_preflight() -> Any:
    path = Path("scripts/preflight_final_run.py")
    spec = importlib.util.spec_from_file_location("preflight_final_run", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["preflight_final_run"] = module
    spec.loader.exec_module(module)
    return module


def test_diagnostic_force_env_detection() -> None:
    preflight = _load_preflight()

    active = preflight.active_diagnostic_force_env(
        {
            "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME": "tool",
            "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR": "",
        }
    )

    assert active == {"SAGE_DIAGNOSTIC_FORCE_TOOL_NAME": "tool"}


def test_run_affecting_sage_env_redacts_secret_like_keys() -> None:
    preflight = _load_preflight()

    env = preflight.run_affecting_sage_env(
        {"SAGE_FOO": "bar", "SAGE_API_KEY": "secret", "OTHER": "ignored"}
    )

    assert env == {"SAGE_API_KEY": "<redacted>", "SAGE_FOO": "bar"}


def test_registry_sha_check_detects_mismatch(tmp_path: Path) -> None:
    preflight = _load_preflight()
    registry_dir = tmp_path / "registry"
    manifest = registry_dir / "registry_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"entries": []}) + "\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    config = {
        "protected_registries": [
            {
                "label": "test_registry",
                "path": str(manifest),
                "sha256": "0" * 64,
            }
        ]
    }
    results: list[Any] = []

    checked = preflight.check_registries(
        results,
        registry_dirs=[registry_dir],
        config=config,
        allow_unlisted=False,
    )

    assert checked[0]["sha256"] == digest
    assert any(
        result.name == "registry_sha_matches:test_registry" and result.status == "fail"
        for result in results
    )
