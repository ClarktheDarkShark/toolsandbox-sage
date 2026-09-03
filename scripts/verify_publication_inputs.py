#!/usr/bin/env python3
"""Verify the compact, Git-tracked publication inputs without local archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.build_publication_freeze import (
        FreezeError,
        sanitized_rapid_fixture_bytes,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from build_publication_freeze import (  # type: ignore[import-not-found,no-redef]
        FreezeError,
        sanitized_rapid_fixture_bytes,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_INPUT_MANIFEST = Path(
    "docs/sage_protocol/publication_input_manifest_20260901.json"
)
DEFAULT_MANIFEST = Path("docs/sage_protocol/publication_release_manifest_20260902.json")
EXPECTED_REPLACEMENT_POLICY = {
    "generator_contract_and_repair_analysis_memoization": "within_run_only",
    "repository_whole_response_replay": "disabled",
    "persistent_generation_output_replay": "disabled",
    "openai_provider_prompt_prefix_cache": "automatic_implicit",
    "diagnostic_force_calls": "disabled",
    "performance_endpoint": "outcome_task_completion_similarity",
    "canonical_metric_policy": "descriptive_only_never_a_release_gate",
    "execution_environment": {
        "SAGE_OPENAI_MAX_RETRIES": "5",
        "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
        "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
        "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
    },
}
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX_GIT_OBJECT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")


class InputVerificationError(RuntimeError):
    """Raised when a compact publication-input invariant is not satisfied."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputVerificationError(
            f"Cannot read {label} JSON object {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise InputVerificationError(f"Expected {label} to be a JSON object: {path}")
    return payload


def _object(mapping: dict[str, Any], field: str, label: str) -> dict[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, dict):
        raise InputVerificationError(f"{label} is missing object {field!r}")
    return value


def _string(mapping: dict[str, Any], field: str, label: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise InputVerificationError(f"{label} is missing string {field!r}")
    return value


def _integer(mapping: dict[str, Any], field: str, label: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputVerificationError(f"{label} is missing integer {field!r}")
    return value


def _hash(mapping: dict[str, Any], field: str, label: str) -> str:
    value = _string(mapping, field, label)
    if not _HEX_SHA256.fullmatch(value):
        raise InputVerificationError(f"{label}.{field} is not a lowercase SHA-256")
    return value


def _git_oid(mapping: dict[str, Any], field: str, label: str) -> str:
    value = _string(mapping, field, label)
    if not _HEX_GIT_OBJECT.fullmatch(value):
        raise InputVerificationError(f"{label}.{field} is not a full Git object ID")
    return value


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise InputVerificationError(
            f"Git command failed: git {' '.join(arguments)}{suffix}"
        ) from exc
    return completed.stdout.strip()


def _tracked_file(repo_root: Path, raw_path: str, label: str) -> tuple[Path, str]:
    candidate = Path(raw_path)
    path = candidate if candidate.is_absolute() else repo_root / candidate
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise InputVerificationError(f"{label} escapes the repository: {path}") from exc
    if not resolved.is_file():
        raise InputVerificationError(f"Missing {label}: {resolved}")
    _git(repo_root, "ls-files", "--error-unmatch", "--", relative)
    return resolved, relative


def _assert_hash(path: Path, expected: str, label: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise InputVerificationError(
            f"{label} hash mismatch: expected {expected}, observed {observed}"
        )
    return observed


def _canonical_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _verify_publication_runtime(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    expected_runtime = {
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "isolated_virtual_environment_required": True,
    }
    for field, expected in expected_runtime.items():
        if declaration.get(field) != expected:
            raise InputVerificationError(
                f"publication_runtime.{field} must be {expected!r}"
            )

    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "lock_path", "publication_runtime"),
        "publication environment lock",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "lock_sha256", "publication_runtime"),
        "publication environment lock",
    )
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LOCK_LINE.fullmatch(line)
        if match is None:
            raise InputVerificationError(
                "Publication environment lock must contain only exact, unmarked "
                f"name==version entries; line {line_number} is invalid"
            )
        display_name, version = match.groups()
        name = _canonical_distribution_name(display_name)
        if name in entries:
            raise InputVerificationError(
                f"Publication environment lock duplicates distribution {name!r}"
            )
        entries[name] = version
    if not entries:
        raise InputVerificationError("Publication environment lock is empty")
    canonical_entries = sorted(
        f"{name}=={version}\n" for name, version in entries.items()
    )
    identity_bytes = "".join(canonical_entries).encode("utf-8")
    identity_sha256 = hashlib.sha256(identity_bytes).hexdigest()
    expected_count = _integer(
        declaration,
        "external_distribution_count",
        "publication_runtime",
    )
    if len(entries) != expected_count:
        raise InputVerificationError(
            "Publication environment distribution count mismatch: "
            f"expected {expected_count}, observed {len(entries)}"
        )
    expected_identity = _hash(
        declaration,
        "external_distribution_sha256",
        "publication_runtime",
    )
    if identity_sha256 != expected_identity:
        raise InputVerificationError(
            "Publication environment distribution identity mismatch: "
            f"expected {expected_identity}, observed {identity_sha256}"
        )
    return {
        **expected_runtime,
        "lock_path": relative,
        "lock_sha256": observed_hash,
        "external_distribution_count": len(entries),
        "external_distribution_sha256": identity_sha256,
    }


def _verify_benchmark(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "benchmark"),
        "benchmark manifest",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "benchmark"),
        "benchmark manifest",
    )
    payload = _read_object(path, "benchmark")
    splits = payload.get("splits")
    full = splits.get("full_benchmark") if isinstance(splits, dict) else None
    if not isinstance(full, list):
        raise InputVerificationError("Benchmark has no full_benchmark list")
    names: list[str] = []
    for index, item in enumerate(full):
        if not isinstance(item, dict):
            raise InputVerificationError(f"Benchmark task {index} is not an object")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise InputVerificationError(f"Benchmark task {index} has no name")
        names.append(name)
    expected_count = _integer(declaration, "task_count", "benchmark")
    if len(names) != expected_count or len(set(names)) != expected_count:
        raise InputVerificationError(
            "Benchmark task coverage changed: "
            f"expected {expected_count} unique tasks, found {len(names)} entries "
            f"and {len(set(names))} unique names"
        )
    order_hash = hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()
    expected_order_hash = _hash(
        declaration,
        "ordered_task_names_sha256",
        "benchmark",
    )
    if order_hash != expected_order_hash:
        raise InputVerificationError(
            "Benchmark ordered task-name hash mismatch: "
            f"expected {expected_order_hash}, observed {order_hash}"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "task_count": len(names),
        "ordered_task_names_sha256": order_hash,
    }


def _verify_rapidapi_fixture(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    if declaration.get("usage") != "read_only_benchmark_input":
        raise InputVerificationError(
            "RapidAPI fixture is not declared as a read-only benchmark input"
        )
    if declaration.get("contains_api_credentials") is not False:
        raise InputVerificationError(
            "RapidAPI fixture declaration does not prohibit API credentials"
        )
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "sanitized_path", "rapidapi_fixture"),
        "sanitized RapidAPI fixture",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sanitized_sha256", "rapidapi_fixture"),
        "sanitized RapidAPI fixture",
    )
    try:
        sanitized_bytes, metadata = sanitized_rapid_fixture_bytes(path)
    except (FreezeError, OSError, json.JSONDecodeError) as exc:
        raise InputVerificationError(
            f"RapidAPI fixture failed credential and cache-key safety checks: {exc}"
        ) from exc
    if path.read_bytes() != sanitized_bytes:
        raise InputVerificationError(
            "RapidAPI fixture bytes are not the canonical credential-safe form"
        )
    expected_count = _integer(declaration, "entry_count", "rapidapi_fixture")
    if metadata.get("entry_count") != expected_count:
        raise InputVerificationError(
            "RapidAPI fixture entry count changed: "
            f"expected {expected_count}, observed {metadata.get('entry_count')}"
        )
    if metadata.get("contains_api_credentials") is not False:
        raise InputVerificationError("RapidAPI fixture safety scan did not pass")
    if metadata.get("request_cache_keys_revalidated") != expected_count:
        raise InputVerificationError(
            "RapidAPI fixture cache keys were not all revalidated"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "entry_count": expected_count,
        "contains_api_credentials": False,
        "request_cache_keys_revalidated": expected_count,
        "credential_safety_scan": "pass",
    }


def _verify_analysis_inputs(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for label, path_field, hash_field in (
        (
            "campaign_manifest",
            "public_campaign_manifest_path",
            "campaign_manifest_sha256",
        ),
        ("evidence_data", "public_evidence_data_path", "evidence_data_sha256"),
    ):
        path, relative = _tracked_file(
            repo_root,
            _string(declaration, path_field, "analysis"),
            f"historical {label}",
        )
        observed_hash = _assert_hash(
            path,
            _hash(declaration, hash_field, "analysis"),
            f"historical {label}",
        )
        _read_object(path, f"historical {label}")
        records[label] = {"path": relative, "sha256": observed_hash}
    return records


def _verify_thresholds(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    benchmark: dict[str, Any],
    fixture: dict[str, Any],
    analysis: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "validation_thresholds"),
        "publication validation thresholds",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "validation_thresholds"),
        "publication validation thresholds",
    )
    thresholds = _read_object(path, "publication validation thresholds")
    threshold_benchmark = _object(thresholds, "benchmark", "validation thresholds")
    expected_benchmark = {
        "task_count": benchmark["task_count"],
        "manifest_sha256": benchmark["sha256"],
        "ordered_task_name_sha256": benchmark["ordered_task_names_sha256"],
    }
    for field, expected in expected_benchmark.items():
        if threshold_benchmark.get(field) != expected:
            raise InputVerificationError(
                f"Validation thresholds disagree with the benchmark: {field}"
            )
    historical = _object(thresholds, "historical_reference", "validation thresholds")
    for label, path_field, hash_field in (
        ("campaign_manifest", "campaign_manifest", "campaign_manifest_sha256"),
        ("evidence_data", "evidence_data", "evidence_data_sha256"),
    ):
        if historical.get(path_field) != analysis[label]["path"]:
            raise InputVerificationError(
                f"Validation thresholds disagree with the historical {label} path"
            )
        if historical.get(hash_field) != analysis[label]["sha256"]:
            raise InputVerificationError(
                f"Validation thresholds disagree with the historical {label} hash"
            )
    integrity = _object(thresholds, "required_integrity", "validation thresholds")
    if integrity.get("validated_external_fixture_sha256") != fixture["sha256"]:
        raise InputVerificationError(
            "Validation thresholds disagree with the sanitized fixture hash"
        )
    return {"path": relative, "sha256": observed_hash}


def _verify_checkpoint(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "manifest_path", "checkpoint"),
        "publication checkpoint manifest",
    )
    manifest_hash = _assert_hash(
        path,
        _hash(declaration, "manifest_sha256", "checkpoint"),
        "publication checkpoint manifest",
    )
    checkpoint_manifest = _read_object(path, "publication checkpoint")
    recorded = _object(checkpoint_manifest, "git_checkpoint", "checkpoint manifest")
    expected_commit = _git_oid(declaration, "commit", "checkpoint")
    expected_tree = _git_oid(declaration, "tree", "checkpoint")
    if (
        recorded.get("commit") != expected_commit
        or recorded.get("tree") != expected_tree
    ):
        raise InputVerificationError(
            "Checkpoint manifest commit/tree disagree with the compact input manifest"
        )
    resolved_commit = _git(
        repo_root, "rev-parse", "--verify", f"{expected_commit}^{{commit}}"
    )
    if resolved_commit != expected_commit:
        raise InputVerificationError(
            f"Checkpoint commit resolves unexpectedly: {resolved_commit}"
        )
    resolved_tree = _git(
        repo_root, "rev-parse", "--verify", f"{expected_commit}^{{tree}}"
    )
    if resolved_tree != expected_tree:
        raise InputVerificationError(
            "Checkpoint tree mismatch: "
            f"expected {expected_tree}, observed {resolved_tree}"
        )
    if _git(repo_root, "cat-file", "-t", expected_tree) != "tree":
        raise InputVerificationError("Checkpoint tree object is not a Git tree")
    return {
        "manifest_path": relative,
        "manifest_sha256": manifest_hash,
        "commit": resolved_commit,
        "tree": resolved_tree,
        "git_objects_resolvable": True,
    }


def _verify_base_inputs(
    repo_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Verify the immutable compact input manifest."""
    root = repo_root.resolve()
    raw_manifest = (
        manifest_path if manifest_path.is_absolute() else root / manifest_path
    )
    manifest = raw_manifest.resolve()
    try:
        manifest_relative = manifest.relative_to(root).as_posix()
    except ValueError as exc:
        raise InputVerificationError(
            f"Publication input manifest escapes the repository: {manifest}"
        ) from exc
    if not manifest.is_file():
        raise InputVerificationError(f"Missing publication input manifest: {manifest}")
    _git(root, "ls-files", "--error-unmatch", "--", manifest_relative)
    payload = _read_object(manifest, "publication input manifest")
    if payload.get("schema_version") != 1:
        raise InputVerificationError("Unsupported publication input manifest schema")
    public_verification = _object(
        payload,
        "public_verification",
        "input manifest",
    )
    if public_verification.get("requires_local_recovery_bundle") is not False:
        raise InputVerificationError(
            "Compact verification must not require the local recovery bundle"
        )

    benchmark = _verify_benchmark(root, _object(payload, "benchmark", "input manifest"))
    publication_runtime = _verify_publication_runtime(
        root,
        _object(payload, "publication_runtime", "input manifest"),
    )
    fixture = _verify_rapidapi_fixture(
        root,
        _object(payload, "rapidapi_fixture", "input manifest"),
    )
    analysis = _verify_analysis_inputs(
        root,
        _object(payload, "analysis", "input manifest"),
    )
    thresholds = _verify_thresholds(
        root,
        _object(payload, "validation_thresholds", "input manifest"),
        benchmark=benchmark,
        fixture=fixture,
        analysis=analysis,
    )
    checkpoint = _verify_checkpoint(
        root,
        _object(payload, "checkpoint", "input manifest"),
    )
    return {
        "status": "pass",
        "publication_input_manifest": {
            "path": manifest_relative,
            "sha256": _sha256(manifest),
        },
        "benchmark": benchmark,
        "publication_runtime": publication_runtime,
        "rapidapi_fixture": fixture,
        "historical_analysis_inputs": analysis,
        "validation_thresholds": thresholds,
        "checkpoint": checkpoint,
        "requires_local_recovery_bundle": False,
    }


def _verify_policy_amendment(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "checkpoint_policy_amendment"),
        "publication checkpoint policy amendment",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "checkpoint_policy_amendment"),
        "publication checkpoint policy amendment",
    )
    amendment = _read_object(path, "publication checkpoint policy amendment")
    if amendment.get("schema_version") != 2:
        raise InputVerificationError(
            "Unsupported publication checkpoint policy amendment schema"
        )
    amended = _object(amendment, "amends", "checkpoint policy amendment")
    if amended.get("path") != checkpoint["manifest_path"]:
        raise InputVerificationError(
            "Checkpoint policy amendment names a different checkpoint manifest"
        )
    if amended.get("sha256") != checkpoint["manifest_sha256"]:
        raise InputVerificationError(
            "Checkpoint policy amendment names a different checkpoint hash"
        )
    expected_scope = [
        "publication_policy.strict_publication_provenance_exceptions",
        "replacement_publication_execution_policy",
        "replacement_publication_validation_policy",
    ]
    if amended.get("scope") != expected_scope:
        raise InputVerificationError("Checkpoint policy amendment scope is incomplete")
    if amendment.get("replacement_policy") != EXPECTED_REPLACEMENT_POLICY:
        raise InputVerificationError(
            "Checkpoint policy amendment replacement policy is not exact"
        )
    if amendment.get("immutable_inputs_changed") is not False:
        raise InputVerificationError(
            "Checkpoint policy amendment does not preserve immutable inputs"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "amended_checkpoint_path": checkpoint["manifest_path"],
        "amended_checkpoint_sha256": checkpoint["manifest_sha256"],
        "replacement_policy": EXPECTED_REPLACEMENT_POLICY,
    }


def _verify_active_validation_thresholds(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    benchmark: dict[str, Any],
    fixture: dict[str, Any],
    analysis: dict[str, dict[str, Any]],
    superseded: dict[str, Any],
) -> dict[str, Any]:
    verified = _verify_thresholds(
        repo_root,
        declaration,
        benchmark=benchmark,
        fixture=fixture,
        analysis=analysis,
    )
    path = repo_root / verified["path"]
    payload = _read_object(path, "active publication validation thresholds")
    if payload.get("schema_version") != 2:
        raise InputVerificationError(
            "Active publication validation thresholds schema version is not 2"
        )
    if payload.get("performance_endpoint") != "outcome_task_completion_similarity":
        raise InputVerificationError(
            "Active publication validation endpoint is not outcome/task completion"
        )
    if (
        payload.get("canonical_metric_policy")
        != "descriptive_only_never_a_release_gate"
    ):
        raise InputVerificationError(
            "Active publication validation does not make canonical report-only"
        )
    supersedes = _object(payload, "supersedes", "active validation thresholds")
    if supersedes.get("path") != superseded["path"] or supersedes.get(
        "sha256"
    ) != superseded.get("sha256"):
        raise InputVerificationError(
            "Active validation thresholds do not identify the superseded policy"
        )
    superseded_payload = _read_object(
        repo_root / superseded["path"],
        "superseded publication validation thresholds",
    )
    superseded_historical = _object(
        superseded_payload,
        "historical_reference",
        "superseded validation thresholds",
    )
    no_regression = _object(
        payload,
        "required_no_regression",
        "active validation thresholds",
    )
    expected_no_regression = {
        "candidate_outcome_minimum": superseded_historical.get(
            "candidate_outcome_minimum"
        ),
        "minimum_relative_outcome_lift_percent_over_same_run_control": 10.0,
        "minimum_accepted_tool_count": 1,
        "minimum_tool_reuse_event_count": 1,
        "minimum_generated_tool_called_scenario_count": 1,
    }
    if set(no_regression) != set(expected_no_regression) or any(
        type(no_regression[field]) is not type(expected)
        or no_regression[field] != expected
        for field, expected in expected_no_regression.items()
    ):
        raise InputVerificationError(
            "Active no-regression thresholds do not match the exact outcome-only policy"
        )
    historical = _object(payload, "historical_reference", "active thresholds")
    for field in ("candidate_outcome_minimum", "candidate_outcome_mean"):
        if historical.get(field) != superseded_historical.get(field):
            raise InputVerificationError(
                f"Active historical outcome reference changed: {field}"
            )
    expected_integrity = {
        "complete_control_and_candidate_arms": True,
        "identical_ordered_task_sequence": True,
        "runtime_exception_count_per_arm": 0,
        "control_cache_mode": "off",
        "cached_control_task_count": 0,
        "repository_whole_response_replay_call_count_per_arm": 0,
        "persistent_generation_output_replay_enabled": False,
        "sage_task_cache_enabled": False,
        "online_reflection_control_source": "same_run_fresh",
        "parallel_arms": False,
        "resume_allowed": False,
        "diagnostic_force_calls_allowed": False,
        "validated_external_fixture_mode": "read_only",
        "validated_external_fixture_sha256": fixture["sha256"],
    }
    integrity = _object(payload, "required_integrity", "active thresholds")
    if set(integrity) != set(expected_integrity) or any(
        type(integrity[field]) is not type(expected) or integrity[field] != expected
        for field, expected in expected_integrity.items()
    ):
        raise InputVerificationError("Active validation integrity policy is not exact")
    report_only = _object(payload, "report_only", "active thresholds")
    if report_only.get(
        "compare_candidate_outcome_to_historical_mean"
    ) != superseded_historical.get("candidate_outcome_mean"):
        raise InputVerificationError(
            "Active report-only outcome mean changed from the frozen reference"
        )
    return {
        **verified,
        "performance_endpoint": "outcome_task_completion_similarity",
        "canonical_metric_policy": "descriptive_only_never_a_release_gate",
    }


def verify_inputs(
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    """Verify the content-addressed publication input and policy chain."""

    root = repo_root.resolve()
    selected = manifest_path if manifest_path.is_absolute() else root / manifest_path
    selected = selected.resolve()
    try:
        selected_relative = selected.relative_to(root).as_posix()
    except ValueError as exc:
        raise InputVerificationError(
            f"Publication input manifest escapes the repository: {selected}"
        ) from exc
    if not selected.is_file():
        raise InputVerificationError(f"Missing publication input manifest: {selected}")
    _git(root, "ls-files", "--error-unmatch", "--", selected_relative)
    selected_payload = _read_object(selected, "publication input manifest")
    if selected_payload.get("manifest_type") != "publication_release_input_chain":
        return _verify_base_inputs(root, selected)
    if selected_payload.get("schema_version") != 1:
        raise InputVerificationError("Unsupported publication release manifest schema")

    base_declaration = _object(
        selected_payload,
        "base_input_manifest",
        "publication release manifest",
    )
    base_path, _ = _tracked_file(
        root,
        _string(base_declaration, "path", "base_input_manifest"),
        "base publication input manifest",
    )
    _assert_hash(
        base_path,
        _hash(base_declaration, "sha256", "base_input_manifest"),
        "base publication input manifest",
    )
    result = _verify_base_inputs(root, base_path)
    amendment = _verify_policy_amendment(
        root,
        _object(
            selected_payload,
            "checkpoint_policy_amendment",
            "publication release manifest",
        ),
        checkpoint=result["checkpoint"],
    )
    result["publication_release_manifest"] = {
        "path": selected_relative,
        "sha256": _sha256(selected),
    }
    result["checkpoint_policy_amendment"] = amendment
    superseded_thresholds = result["validation_thresholds"]
    result["superseded_validation_thresholds"] = superseded_thresholds
    result["validation_thresholds"] = _verify_active_validation_thresholds(
        root,
        _object(
            selected_payload,
            "active_validation_thresholds",
            "publication release manifest",
        ),
        benchmark=result["benchmark"],
        fixture=result["rapidapi_fixture"],
        analysis=result["historical_analysis_inputs"],
        superseded=superseded_thresholds,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        result = verify_inputs(args.repo_root, args.manifest)
    except InputVerificationError as exc:
        raise SystemExit(f"publication_input_verification=failed\n{exc}") from exc
    print("publication_input_verification=pass")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
