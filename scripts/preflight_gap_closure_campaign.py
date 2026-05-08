#!/usr/bin/env python3
"""Preflight the SAGE gap-closure lab before live campaign execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.config.gap_closure_lab import payload_sha256
from sage_ts.config.splits import load_split_names

REQUIRED_RUNNER_SPLITS = {
    "pilot_20": 20,
    "expanded_60": 60,
    "confirm_100": 100,
    "validate_250": 250,
}

PROTECTED_PATHS = (
    "artifacts/registry_frozen_best3_claim/registry_manifest.json",
    "artifacts/final_sage_praxis_package",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except subprocess.CalledProcessError as exc:
        return f"ERROR: {exc}"


def _manifest_payload_hash(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_integrity", None)
    return payload_sha256(payload)


def _check_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    integrity = manifest.get("manifest_integrity", {})
    expected_payload_hash = integrity.get("payload_sha256")
    actual_payload_hash = _manifest_payload_hash(manifest)
    sha_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    file_hash = _sha256_file(manifest_path)
    recorded_file_hash = ""
    if sha_path.is_file():
        recorded_file_hash = sha_path.read_text(encoding="utf-8").split()[0]

    split_counts: dict[str, int] = {}
    split_errors: dict[str, str] = {}
    for split_name, expected_count in REQUIRED_RUNNER_SPLITS.items():
        try:
            names = load_split_names(manifest_path, split_name)
            split_counts[split_name] = len(names)
            if len(names) != expected_count:
                split_errors[split_name] = (
                    f"expected {expected_count}, found {len(names)}"
                )
        except Exception as exc:  # pragma: no cover - surfaced in preflight artifact
            split_errors[split_name] = f"{type(exc).__name__}: {exc}"

    return {
        "manifest_path": str(manifest_path),
        "manifest_type": manifest.get("manifest_type"),
        "file_sha256": file_hash,
        "recorded_file_sha256": recorded_file_hash,
        "file_hash_matches_sidecar": bool(recorded_file_hash == file_hash),
        "payload_sha256": actual_payload_hash,
        "recorded_payload_sha256": expected_payload_hash,
        "payload_hash_matches": bool(expected_payload_hash == actual_payload_hash),
        "runner_split_counts": split_counts,
        "runner_split_errors": split_errors,
    }


def _check_openai_key() -> dict[str, Any]:
    present = bool(os.environ.get("OPENAI_API_KEY"))
    return {
        "OPENAI_API_KEY_present": present,
        "status": "pass" if present else "blocker",
        "required_for": [
            "ToolSandbox agent/user live runs",
            "SAGE tool generation and repair",
            "fresh candidate arms without cross-arm cache leakage",
        ],
    }


def build_preflight(manifest_path: Path) -> dict[str, Any]:
    manifest_check = _check_manifest(manifest_path)
    openai_check = _check_openai_key()
    blockers: list[str] = []
    if not manifest_check["file_hash_matches_sidecar"]:
        blockers.append("manifest_file_hash_mismatch")
    if not manifest_check["payload_hash_matches"]:
        blockers.append("manifest_payload_hash_mismatch")
    if manifest_check["runner_split_errors"]:
        blockers.append("runner_split_errors")
    if not openai_check["OPENAI_API_KEY_present"]:
        blockers.append("missing_openai_api_key")

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "branch": _git_output("branch", "--show-current"),
        "head": _git_output("rev-parse", "--short", "HEAD"),
        "status": "blocked" if blockers else "ready",
        "blockers": blockers,
        "manifest": manifest_check,
        "openai": openai_check,
        "protected_paths": [
            {
                "path": path,
                "exists": Path(path).exists(),
                "policy": "do_not_modify",
            }
            for path in PROTECTED_PATHS
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "artifacts/experiment_manifests/gap_closure_lab/gap_closure_lab_splits.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/experiment_manifests/gap_closure_lab/campaign_preflight.json"
        ),
    )
    args = parser.parse_args()

    payload = build_preflight(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if payload["status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
