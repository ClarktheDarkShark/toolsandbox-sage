#!/usr/bin/env python3
"""Load and verify the compact synthetic reporting replay fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURE = HERE / "fixtures" / "reporting_v1.json"
DEFAULT_MANIFEST = HERE / "fixtures" / "reporting_v1.manifest.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Reporting fixture manifest must be an object")
    return payload


def _verify_fixture_bytes(
    fixture_bytes: bytes,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    observed_sha = sha256_bytes(fixture_bytes)
    expected_sha = str(manifest["fixture_sha256"])
    if observed_sha != expected_sha:
        raise ValueError(
            f"Reporting fixture hash mismatch: {observed_sha} != {expected_sha}"
        )
    if len(fixture_bytes) != int(manifest["fixture_byte_count"]):
        raise ValueError("Reporting fixture byte count mismatch")
    fixture = json.loads(fixture_bytes)
    if not isinstance(fixture, dict):
        raise ValueError("Reporting fixture must be an object")
    if fixture.get("schema_version") != 1 or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported reporting fixture schema")
    control_rows = fixture.get("control_rows")
    candidate_rows = fixture.get("candidate_rows")
    if not isinstance(control_rows, list) or not isinstance(candidate_rows, list):
        raise ValueError("Reporting fixture must contain paired result rows")
    expected_count = int(manifest["paired_scenario_count"])
    if len(control_rows) != expected_count or len(candidate_rows) != expected_count:
        raise ValueError("Reporting fixture paired scenario count mismatch")
    observed_canonical_sha = sha256_bytes(canonical_bytes(fixture))
    if observed_canonical_sha != str(manifest["canonical_payload_sha256"]):
        raise ValueError("Reporting fixture canonical payload hash mismatch")
    required = set(manifest.get("required_coverage") or [])
    coverage = set(fixture.get("coverage") or [])
    if not required.issubset(coverage):
        raise ValueError(
            f"Reporting fixture coverage missing: {sorted(required - coverage)}"
        )
    serialized = fixture_bytes.decode("utf-8")
    if "/Users/" in serialized or "OPENAI_API_KEY" in serialized:
        raise ValueError("Reporting fixture contains an absolute path or credential key")
    return fixture


def load_verified_fixture(
    fixture_path: Path = DEFAULT_FIXTURE,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the checked fixture and fail closed on any content drift."""

    manifest = _read_manifest(manifest_path)
    fixture = _verify_fixture_bytes(fixture_path.read_bytes(), manifest)
    return fixture, manifest


def _tamper_self_test(fixture_path: Path, manifest: dict[str, Any]) -> None:
    original = fixture_path.read_bytes()
    if not original:
        raise ValueError("Cannot tamper-test an empty reporting fixture")
    tampered = bytearray(original)
    tampered[len(tampered) // 2] ^= 1
    try:
        _verify_fixture_bytes(bytes(tampered), manifest)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return
    raise RuntimeError("Reporting fixture tamper self-test was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tamper-self-test", action="store_true")
    args = parser.parse_args()
    fixture, manifest = load_verified_fixture(args.fixture, args.manifest)
    if args.tamper_self_test:
        _tamper_self_test(args.fixture, manifest)
    print(
        json.dumps(
            {
                "status": "verified",
                "fixture_sha256": manifest["fixture_sha256"],
                "paired_scenario_count": len(fixture["control_rows"]),
                "coverage": fixture["coverage"],
                "tamper_self_test": bool(args.tamper_self_test),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
