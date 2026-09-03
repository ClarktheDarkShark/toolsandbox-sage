#!/usr/bin/env python3
"""Preflight and print the full ToolSandbox self-evolving SAGE run command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MANIFEST = (
    ROOT / "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
)
DEFAULT_REGISTRY = (
    ROOT / "artifacts/self_evolving_sage/full_toolsandbox_current/registry"
)
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/self_evolving_sage/full_toolsandbox_current"
DEFAULT_ARTIFACT_ROOT = (
    ROOT / "artifacts/self_evolving_sage/full_toolsandbox_current_artifacts"
)
DEFAULT_RAPID_CACHE = (
    ROOT
    / "artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
)
PINNED_RAPID_CACHE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--registry-dir", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--rapid-cache-path", type=Path, default=DEFAULT_RAPID_CACHE)
    parser.add_argument("--agent", default="gpt-4o-mini")
    parser.add_argument("--user", default="gpt-4o-mini")
    parser.add_argument("--generation-model", default="gpt-4o-mini")
    parser.add_argument("--dashboard-port", type=int, default=62624)
    parser.add_argument(
        "--mode",
        default="online_build_full",
        help="Generation-enabled full-dataset mode; maps to manifest split full_benchmark.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the command after preflight. Default only prints the command.",
    )
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    registry_dir = args.registry_dir.resolve()
    output_root = args.output_root.resolve()
    artifact_root = args.artifact_root.resolve()
    rapid_cache_path = args.rapid_cache_path.resolve()
    if not rapid_cache_path.is_file():
        raise SystemExit(f"Missing publication external fixture: {rapid_cache_path}")
    rapid_cache_sha256 = _sha256(rapid_cache_path)
    if rapid_cache_sha256 != PINNED_RAPID_CACHE_SHA256:
        raise SystemExit(
            "Publication external fixture hash mismatch: "
            f"expected {PINNED_RAPID_CACHE_SHA256}, observed {rapid_cache_sha256}."
        )

    payload = _read_json(manifest)
    split = "full_benchmark" if args.mode == "online_build_full" else args.mode
    scenarios = payload.get("splits", {}).get(split)
    if not isinstance(scenarios, list) or not scenarios:
        raise SystemExit(
            f"Manifest {manifest} does not contain non-empty split {split!r}."
        )

    env_report = {
        "manifest": str(manifest),
        "manifest_sha256": _sha256(manifest),
        "mode": args.mode,
        "manifest_split": split,
        "scenario_count": len(scenarios),
        "registry_dir": str(registry_dir),
        "registry_starts_empty": not (registry_dir / "registry_manifest.json").exists(),
        "control_cache_mode": "off",
        "fresh_control_required": True,
        "expected_fresh_control_count": len(scenarios),
        "reflection_control_source": "same_run_fresh",
        "rapid_cache_path": str(rapid_cache_path),
        "rapid_cache_exists": True,
        "rapid_cache_sha256": rapid_cache_sha256,
        "rapid_cache_mode": "read_only",
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "agent": args.agent,
        "user": args.user,
        "generation_model": args.generation_model,
        "sage_policy": "self-evolving-praxis",
        "generation": "on",
        "candidate_task_cache": "off",
        "openai_response_cache": "off",
        "prompt_cache": "off",
        "created_at": int(time.time()),
    }

    registry_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    report_path = artifact_root / "full_toolsandbox_self_evolving_preflight.json"
    report_path.write_text(json.dumps(env_report, indent=2) + "\n", encoding="utf-8")

    command = [
        sys.executable,
        "scripts/run_sage_protocol.py",
        "--mode",
        args.mode,
        "--manifest",
        str(manifest),
        "--registry-dir",
        str(registry_dir),
        "--sage-policy",
        "self-evolving-praxis",
        "--agent",
        args.agent,
        "--user",
        args.user,
        "--generation-model",
        args.generation_model,
        "--generation",
        "on",
        "--control-cache",
        "off",
        "--require-fresh-control",
        "--validated-external-fixture",
        str(rapid_cache_path),
        "--validated-external-fixture-sha256",
        PINNED_RAPID_CACHE_SHA256,
        "--freeze-toolsandbox-clock",
        "--dashboard-port",
        str(args.dashboard_port),
        "--output-root",
        str(output_root),
        "--artifact-root",
        str(artifact_root),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "src:.")
    env["CONTROL_CACHE"] = "off"
    for stale_name in (
        "CONTROL_CACHE_ROOT",
        "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
        "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
    ):
        env.pop(stale_name, None)
    env["TOOLSANDBOX_RAPID_CACHE_MODE"] = "read_only"
    env["TOOLSANDBOX_RAPID_CACHE_PATH"] = str(rapid_cache_path)

    print("Full ToolSandbox self-evolving SAGE preflight")
    print(json.dumps(env_report, indent=2))
    print("\nCommand:")
    print(
        _format_env_prefix(env, True)
        + " "
        + " ".join(shlex.quote(part) for part in command)
    )
    print(f"\nPreflight report: {report_path}")

    if args.execute:
        raise SystemExit(subprocess.call(command, cwd=ROOT, env=env))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SystemExit(f"Expected object JSON at {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_env_prefix(env: dict[str, str], include_rapid_cache: bool) -> str:
    parts = [
        "PYTHONPATH=src:.",
        "CONTROL_CACHE=off",
    ]
    if include_rapid_cache:
        parts.extend(
            [
                "TOOLSANDBOX_RAPID_CACHE_MODE=read_only",
                "TOOLSANDBOX_RAPID_CACHE_PATH="
                + shlex.quote(env["TOOLSANDBOX_RAPID_CACHE_PATH"]),
            ]
        )
    return " ".join(parts)


if __name__ == "__main__":
    main()
