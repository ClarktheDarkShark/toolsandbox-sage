#!/usr/bin/env python3
"""Verify the compact, Git-tracked publication inputs without local archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest

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
DEFAULT_MANIFEST = Path("docs/sage_protocol/publication_release_manifest_20260905.json")
ACTIVE_PRODUCTION_CORE_DECLARATION = {
    "path": "docs/sage_protocol/production_core_manifest_20260905.json",
    "sha256": "51bca58741f9917228e14d472f4e6401af85635457fd7e0af4e3206686c47a53",
}
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
EXPECTED_ACTIVE_EXECUTION_POLICY = {
    "execution_environment": {
        "TZ": "America/New_York",
        "SAGE_OPENAI_MAX_RETRIES": "5",
        "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
        "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
        "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
        "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
    },
    "strict_run_inputs": {
        "control_cache_mode": "off",
        "repository_whole_response_replay": "disabled",
        "persistent_generation_output_replay": "disabled",
        "sage_task_cache": "disabled",
        "cross_run_failure_memory": "disabled",
        "resume": "disabled",
        "diagnostic_tool_exposure_and_force_calls": "disabled",
        "rapidapi_fixture": "pinned_read_only",
    },
    "paired_arm_schedule": {
        "pair_1_fresh_control_and_policy_sage": {
            "control": "fresh_non_learning_control",
            "candidate": "policy_selection_sage",
            "execution": "concurrent_isolated_child_processes",
            "ordinary_publication_pair": True,
            "inventory_role": "capture_exact_per_task_actor_ready_authority",
        },
        "pair_2_fresh_independent_control_and_auto_sage": {
            "control": "fresh_independent_non_learning_control",
            "candidate": "sage_auto_selection",
            "execution": "concurrent_isolated_child_processes",
            "starts_after": "policy_inventory_authority_complete",
            "control_delivery": "not_connected",
            "control_output_influences_inventory": False,
            "control_output_influences_execution": False,
        },
        "positive_monotonic_process_interval_overlap_required": True,
        "distinct_child_process_ids_required": True,
        "complete_child_status_records_required": True,
        "peer_failure_handling": "terminate_join_and_fail_closed",
        "online_reflection": {
            "control_source": "same_run_fresh",
            "delivery": "task_synchronous_stream",
            "task_identity_and_order_required": True,
        },
        "frozen_reflection": {
            "delivery": "not_applicable_generation_disabled",
        },
    },
    "task_compare_dashboard": {
        "artifact": "dashboard/task_compare.html",
        "external_browser_open_required": True,
        "open_and_root_identity_receipt_required": True,
        "views": {
            "fresh_control_vs_policy_selection_sage": {
                "artifact": "dashboard/task_compare.html",
                "receipt": "dashboard_open_receipt.json",
                "timing": "before_pair_1_first_model_request",
                "live_refresh": True,
            },
            "fresh_independent_control_vs_sage_auto_selection": {
                "artifact": (
                    "sage_auto_selection_parallel_pair/dashboard/task_compare.html"
                ),
                "receipt": (
                    "sage_auto_selection_parallel_pair/dashboard_open_receipt.json"
                ),
                "timing": "before_pair_2_first_model_request",
                "live_refresh": True,
            },
            "policy_selection_sage_vs_sage_auto_selection": {
                "artifact": ("actor_selection_dashboard/dashboard/task_compare.html"),
                "receipt": ("actor_selection_dashboard/dashboard_open_receipt.json"),
                "timing": "after_both_treatment_arms_complete",
                "role": "causal_actor_selection_comparison",
            },
        },
    },
    "performance_endpoint": {
        "name": "outcome_task_completion_similarity",
        "benchmark_task_count": 1032,
        "non_null_outcome_required_for_every_task": True,
        "route_independent": True,
        "generated_tool_may_complete_action_directly": True,
        "separate_visible_native_tool_followup_required": False,
        "final_state_and_safety_checks_required": True,
        "mechanism_counts_are_release_gates": False,
    },
    "actor_selection_experiment": {
        "pair_1_control_and_policy_sage": "concurrent_isolated_child_processes",
        "pair_2_independent_control_and_auto_sage": (
            "concurrent_isolated_child_processes"
        ),
        "auto_replay_timing": "after_policy_inventory_authority_completion",
        "policy_and_auto_inventory_match_required_per_task": True,
        "reason": (
            "The auto arm must replay the policy donor's exact per-task routed "
            "inventory. Once that authority exists, auto runs concurrently with a "
            "fresh independent non-learning control whose output cannot affect auto "
            "inventory or execution."
        ),
    },
    "outcome_evaluator_identity_fields": [
        "version",
        "contract_sha256",
        "source_sha256",
    ],
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


def _number(mapping: dict[str, Any], field: str, label: str) -> float:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputVerificationError(f"{label} is missing numeric {field!r}")
    result = float(value)
    if not math.isfinite(result):
        raise InputVerificationError(f"{label}.{field} is not finite")
    return result


def _exact_equal(observed: Any, expected: Any) -> bool:
    """Compare JSON-like values without Python's bool/int coercion."""

    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _exact_equal(observed[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _exact_equal(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


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


def _verify_active_execution_policy(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    amendment: dict[str, Any],
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "active_execution_policy"),
        "active publication execution policy",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "active_execution_policy"),
        "active publication execution policy",
    )
    payload = _read_object(path, "active publication execution policy")
    expected_top_level = {
        "schema_version",
        "manifest_type",
        "created_at",
        "purpose",
        "extends",
        *EXPECTED_ACTIVE_EXECUTION_POLICY,
        "immutable_inputs_changed",
    }
    if set(payload) != expected_top_level:
        raise InputVerificationError(
            "Active publication execution policy fields are not exact"
        )
    if (
        payload.get("schema_version") != 1
        or payload.get("manifest_type") != "publication_execution_policy"
    ):
        raise InputVerificationError(
            "Unsupported active publication execution policy schema"
        )
    if not isinstance(payload.get("created_at"), str) or not isinstance(
        payload.get("purpose"), str
    ):
        raise InputVerificationError(
            "Active publication execution policy metadata is incomplete"
        )
    extends = _object(payload, "extends", "active publication execution policy")
    expected_extends = {
        "path": amendment["path"],
        "sha256": amendment["sha256"],
    }
    if not _exact_equal(extends, expected_extends):
        raise InputVerificationError(
            "Active publication execution policy extends a different amendment"
        )
    performance_endpoint = cast(
        dict[str, Any], EXPECTED_ACTIVE_EXECUTION_POLICY["performance_endpoint"]
    )
    expected_policy = {
        **EXPECTED_ACTIVE_EXECUTION_POLICY,
        "performance_endpoint": {
            **performance_endpoint,
            "benchmark_task_count": benchmark["task_count"],
        },
    }
    for field, expected in expected_policy.items():
        if not _exact_equal(payload.get(field), expected):
            raise InputVerificationError(
                f"Active publication execution policy drifted at {field!r}"
            )
    if payload.get("immutable_inputs_changed") is not False:
        raise InputVerificationError(
            "Active publication execution policy changes immutable inputs"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "performance_endpoint": "outcome_task_completion_similarity",
        "paired_arm_schedule": payload["paired_arm_schedule"],
        "task_compare_dashboard": payload["task_compare_dashboard"],
    }


def _verify_superseded_release_manifest(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    base_declaration: dict[str, Any],
    amendment_declaration: dict[str, Any],
    benchmark: dict[str, Any],
    fixture: dict[str, Any],
    analysis: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "superseded_release_manifest"),
        "superseded publication release manifest",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "superseded_release_manifest"),
        "superseded publication release manifest",
    )
    payload = _read_object(path, "superseded publication release manifest")
    if set(payload) != {
        "schema_version",
        "manifest_type",
        "created_at",
        "purpose",
        "base_input_manifest",
        "checkpoint_policy_amendment",
        "active_validation_thresholds",
    }:
        raise InputVerificationError(
            "Superseded publication release manifest fields are not exact"
        )
    if (
        payload.get("schema_version") != 1
        or payload.get("manifest_type") != "publication_release_input_chain"
    ):
        raise InputVerificationError(
            "Unsupported superseded publication release manifest schema"
        )
    if not _exact_equal(payload.get("base_input_manifest"), base_declaration):
        raise InputVerificationError(
            "Superseded release names a different base input manifest"
        )
    if not _exact_equal(
        payload.get("checkpoint_policy_amendment"), amendment_declaration
    ):
        raise InputVerificationError(
            "Superseded release names a different checkpoint policy amendment"
        )
    thresholds = _verify_thresholds(
        repo_root,
        _object(
            payload,
            "active_validation_thresholds",
            "superseded publication release manifest",
        ),
        benchmark=benchmark,
        fixture=fixture,
        analysis=analysis,
    )
    threshold_payload = _read_object(
        repo_root / thresholds["path"],
        "superseded active validation thresholds",
    )
    if (
        threshold_payload.get("schema_version") != 2
        or threshold_payload.get("performance_endpoint")
        != "outcome_task_completion_similarity"
    ):
        raise InputVerificationError(
            "Superseded release does not identify the v2 outcome thresholds"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "validation_thresholds": thresholds,
    }


def _outcome_evaluator_identity(
    mapping: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    identity: dict[str, str | int] = {
        "version": _string(mapping, "version", label),
        "contract_sha256": _hash(mapping, "contract_sha256", label),
        "source_sha256": _hash(mapping, "source_sha256", label),
    }
    for field in (
        "insufficient_information_scenario_count",
        "scalar_scenario_count",
    ):
        if field in mapping:
            identity[field] = _integer(mapping, field, label)
    if set(mapping) != set(identity):
        raise InputVerificationError(f"{label} contains unsupported identity fields")
    return identity


def _verify_historical_outcome_rescore_summary(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    benchmark: dict[str, Any],
    analysis: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "historical_outcome_rescore_summary"),
        "historical outcome rescore summary",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "historical_outcome_rescore_summary"),
        "historical outcome rescore summary",
    )
    payload = _read_object(path, "historical outcome rescore summary")
    expected_fields = {
        "schema_version",
        "report_type",
        "created_at",
        "provenance_status",
        "provenance_caveat",
        "source_report",
        "benchmark",
        "outcome_evaluator",
        "rescorer",
        "coverage",
        "baseline",
        "candidate_summary",
        "candidate_runs",
        "primary_input_files",
    }
    if set(payload) != expected_fields:
        raise InputVerificationError(
            "Historical outcome rescore summary fields are not exact"
        )
    if (
        payload.get("schema_version") != 2
        or payload.get("report_type")
        != "historical_terminal_trajectory_outcome_rescore_summary"
    ):
        raise InputVerificationError(
            "Unsupported historical outcome rescore summary schema"
        )
    if (
        payload.get("provenance_status")
        != "historical_terminal_trajectories_timezone_inferred_not_confirmatory"
    ):
        raise InputVerificationError(
            "Historical outcome rescore summary overstates its provenance"
        )
    caveat = payload.get("provenance_caveat")
    if not isinstance(caveat, str) or not caveat:
        raise InputVerificationError(
            "Historical outcome rescore summary is missing its provenance caveat"
        )
    source_report = _object(payload, "source_report", "historical rescore summary")
    if set(source_report) != {
        "local_path",
        "available_in_public_release",
        "content_address_sha256",
        "file_sha256",
    }:
        raise InputVerificationError(
            "Historical rescore source-report record is not exact"
        )
    _string(source_report, "local_path", "historical rescore source report")
    if source_report.get("available_in_public_release") is not False:
        raise InputVerificationError(
            "Ignored full historical rescore must not be claimed as public"
        )
    _hash(source_report, "content_address_sha256", "historical rescore source report")
    _hash(source_report, "file_sha256", "historical rescore source report")
    summary_benchmark = _object(payload, "benchmark", "historical rescore summary")
    expected_benchmark = {
        "task_count": benchmark["task_count"],
        "manifest_sha256": benchmark["sha256"],
        "ordered_task_name_sha256": benchmark["ordered_task_names_sha256"],
    }
    if not _exact_equal(summary_benchmark, expected_benchmark):
        raise InputVerificationError(
            "Historical outcome rescore summary disagrees with the benchmark"
        )
    evaluator = _outcome_evaluator_identity(
        _object(payload, "outcome_evaluator", "historical rescore summary"),
        "historical rescore outcome evaluator",
    )
    shipped_evaluator = _outcome_evaluator_identity(
        outcome_evaluator_manifest(),
        "shipped outcome evaluator",
    )
    if evaluator != shipped_evaluator:
        raise InputVerificationError(
            "Historical outcome rescore does not use the shipped outcome evaluator"
        )
    rescorer = _object(payload, "rescorer", "historical rescore summary")
    if set(rescorer) != {
        "input_mode",
        "outcome_input_contract",
        "source",
        "stored_result_summary_consumed",
        "stored_score_fields_consumed",
        "timezone_inference",
    }:
        raise InputVerificationError("Historical rescorer record is not exact")
    if (
        rescorer.get("input_mode") != "read_only"
        or rescorer.get("outcome_input_contract")
        != ["resolved_scenario", "execution_context"]
        or rescorer.get("stored_result_summary_consumed") is not False
        or rescorer.get("stored_score_fields_consumed") is not False
    ):
        raise InputVerificationError(
            "Historical rescorer did not use the required raw read-only inputs"
        )
    rescorer_source = _object(rescorer, "source", "historical rescorer")
    if set(rescorer_source) != {"path", "sha256", "size"}:
        raise InputVerificationError("Historical rescorer source record is not exact")
    rescorer_path, _ = _tracked_file(
        repo_root,
        _string(rescorer_source, "path", "historical rescorer source"),
        "historical rescorer source",
    )
    _assert_hash(
        rescorer_path,
        _hash(rescorer_source, "sha256", "historical rescorer source"),
        "historical rescorer source",
    )
    if (
        _integer(rescorer_source, "size", "historical rescorer source")
        != rescorer_path.stat().st_size
    ):
        raise InputVerificationError("Historical rescorer source size changed")
    timezone_inference = _object(
        rescorer,
        "timezone_inference",
        "historical rescorer",
    )
    if set(timezone_inference) != {
        "arm_identity_or_replication_used_for_selection",
        "arm_independence",
        "candidate_timezones",
        "evidence_granularity",
        "failure_policy",
        "scope",
        "selection_inputs",
        "tool",
    }:
        raise InputVerificationError(
            "Historical rescorer timezone-inference record is not exact"
        )
    if (
        timezone_inference.get("arm_identity_or_replication_used_for_selection")
        is not False
        or timezone_inference.get("scope") != "all_complete_valid_traces_per_arm"
        or timezone_inference.get("selection_inputs")
        != ["tool_name", "arguments", "result"]
        or timezone_inference.get("tool") != "datetime_info_to_timestamp"
        or timezone_inference.get("failure_policy")
        != "fail_closed_on_missing_unmatched_ambiguous_or_conflicting_evidence"
    ):
        raise InputVerificationError(
            "Historical rescorer timezone inference is not fail-closed and arm-local"
        )
    candidate_timezones = timezone_inference.get("candidate_timezones")
    if (
        not isinstance(candidate_timezones, list)
        or not candidate_timezones
        or any(not isinstance(value, str) or not value for value in candidate_timezones)
        or len(candidate_timezones) != len(set(candidate_timezones))
    ):
        raise InputVerificationError(
            "Historical rescorer candidate timezones are invalid"
        )
    coverage = _object(payload, "coverage", "historical rescore summary")
    expected_coverage = {
        "arm_count": 11,
        "task_count_per_arm": benchmark["task_count"],
        "outcome_value_count_per_arm": benchmark["task_count"],
        "null_outcome_count": 0,
        "all_arms_complete": True,
        "all_arms_match_benchmark_order": True,
        "observed_order_sha256": benchmark["ordered_task_names_sha256"],
    }
    if not _exact_equal(coverage, expected_coverage):
        raise InputVerificationError(
            "Historical rescore coverage/order record is not exact"
        )
    baseline = _object(payload, "baseline", "historical rescore summary")
    if set(baseline) != {
        "task_count",
        "outcome_mean",
        "exact_outcome_successes",
        "input_files_sha256",
        "fixed_toolsandbox_timestamp",
        "timezone",
    }:
        raise InputVerificationError(
            "Historical outcome rescore baseline fields are not exact"
        )
    if (
        _integer(baseline, "task_count", "historical rescore baseline")
        != benchmark["task_count"]
    ):
        raise InputVerificationError(
            "Historical outcome rescore baseline coverage is incomplete"
        )
    baseline_mean = _number(baseline, "outcome_mean", "historical rescore baseline")
    baseline_exact = _integer(
        baseline,
        "exact_outcome_successes",
        "historical rescore baseline",
    )
    _hash(baseline, "input_files_sha256", "historical rescore baseline")
    _string(
        baseline,
        "fixed_toolsandbox_timestamp",
        "historical rescore baseline",
    )
    _string(baseline, "timezone", "historical rescore baseline")
    if not 0 <= baseline_exact <= benchmark["task_count"]:
        raise InputVerificationError(
            "Historical outcome rescore baseline exact-success count is invalid"
        )
    candidate = _object(payload, "candidate_summary", "historical rescore summary")
    if set(candidate) != {
        "run_count",
        "task_outcome_observation_count",
        "mean_of_run_outcome_means",
        "lower_envelope",
        "total_exact_outcome_successes",
    }:
        raise InputVerificationError(
            "Historical candidate summary fields are not exact"
        )
    run_count = _integer(candidate, "run_count", "historical candidate summary")
    observation_count = _integer(
        candidate,
        "task_outcome_observation_count",
        "historical candidate summary",
    )
    mean = _number(
        candidate, "mean_of_run_outcome_means", "historical candidate summary"
    )
    lower_envelope = _object(
        candidate,
        "lower_envelope",
        "historical candidate summary",
    )
    if set(lower_envelope) != {
        "minimum_run_exact_outcome_success_replications",
        "minimum_run_exact_outcome_successes",
        "minimum_run_outcome_mean",
        "minimum_run_outcome_mean_replications",
    }:
        raise InputVerificationError(
            "Historical candidate lower envelope fields are not exact"
        )
    minimum = _number(
        lower_envelope,
        "minimum_run_outcome_mean",
        "historical candidate lower envelope",
    )
    minimum_exact = _integer(
        lower_envelope,
        "minimum_run_exact_outcome_successes",
        "historical candidate lower envelope",
    )
    total_exact = _integer(
        candidate,
        "total_exact_outcome_successes",
        "historical candidate summary",
    )
    if run_count != 10 or observation_count != benchmark["task_count"] * run_count:
        raise InputVerificationError(
            "Historical outcome rescore candidate coverage is incomplete"
        )
    if not (0.0 <= baseline_mean <= 1.0 and 0.0 <= minimum <= mean <= 1.0):
        raise InputVerificationError(
            "Historical outcome rescore values are outside the outcome range"
        )
    candidate_runs = payload.get("candidate_runs")
    if not isinstance(candidate_runs, list) or len(candidate_runs) != run_count:
        raise InputVerificationError(
            "Historical outcome rescore summary does not list all candidate runs"
        )
    replications: list[int] = []
    run_means: list[float] = []
    run_exact_counts: list[int] = []
    run_timezones: list[str] = []
    for index, record in enumerate(candidate_runs):
        if not isinstance(record, dict):
            raise InputVerificationError(
                f"Historical candidate run {index} is not an object"
            )
        if set(record) != {
            "replication",
            "task_count",
            "outcome_mean",
            "exact_outcome_successes",
            "input_files_sha256",
            "fixed_toolsandbox_timestamp",
            "timezone",
        }:
            raise InputVerificationError(
                f"Historical candidate run {index} fields are not exact"
            )
        replications.append(
            _integer(record, "replication", f"historical candidate run {index}")
        )
        value = _number(record, "outcome_mean", f"historical candidate run {index}")
        task_count = _integer(record, "task_count", f"historical candidate run {index}")
        exact_count = _integer(
            record,
            "exact_outcome_successes",
            f"historical candidate run {index}",
        )
        _hash(
            record,
            "input_files_sha256",
            f"historical candidate run {index}",
        )
        _string(
            record,
            "fixed_toolsandbox_timestamp",
            f"historical candidate run {index}",
        )
        run_timezones.append(
            _string(record, "timezone", f"historical candidate run {index}")
        )
        if task_count != benchmark["task_count"] or not 0 <= exact_count <= task_count:
            raise InputVerificationError(
                f"Historical candidate run {index} coverage/count is invalid"
            )
        if not 0.0 <= value <= 1.0:
            raise InputVerificationError(
                f"Historical candidate run {index} outcome is outside [0, 1]"
            )
        run_means.append(value)
        run_exact_counts.append(exact_count)
    if sorted(replications) != list(range(1, run_count + 1)):
        raise InputVerificationError(
            "Historical outcome rescore replications are not exactly 1 through 10"
        )
    minimum_mean_replications = lower_envelope.get(
        "minimum_run_outcome_mean_replications"
    )
    minimum_exact_replications = lower_envelope.get(
        "minimum_run_exact_outcome_success_replications"
    )
    if minimum_mean_replications != [
        replication
        for replication, value in zip(replications, run_means, strict=True)
        if value == min(run_means)
    ] or minimum_exact_replications != [
        replication
        for replication, value in zip(
            replications,
            run_exact_counts,
            strict=True,
        )
        if value == min(run_exact_counts)
    ]:
        raise InputVerificationError(
            "Historical outcome rescore lower-envelope replications do not match"
        )
    if (
        mean != math.fsum(run_means) / run_count
        or minimum != min(run_means)
        or minimum_exact != min(run_exact_counts)
        or total_exact != sum(run_exact_counts)
    ):
        raise InputVerificationError(
            "Historical outcome rescore aggregate values do not match candidate runs"
        )
    if set(run_timezones) != set(candidate_timezones):
        raise InputVerificationError(
            "Historical candidate run timezones disagree with inference evidence"
        )
    primary_inputs = payload.get("primary_input_files")
    if not isinstance(primary_inputs, list) or len(primary_inputs) < 2:
        raise InputVerificationError(
            "Historical outcome rescore summary is missing primary inputs"
        )
    normalized_inputs: list[dict[str, Any]] = []
    for index, record in enumerate(primary_inputs):
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise InputVerificationError(
                f"Historical rescore primary input {index} is not exact"
            )
        size = _integer(record, "size", f"historical primary input {index}")
        normalized: dict[str, str | int] = {
            "path": _string(record, "path", f"historical primary input {index}"),
            "sha256": _hash(record, "sha256", f"historical primary input {index}"),
            "size": size,
        }
        if size <= 0:
            raise InputVerificationError(
                f"Historical rescore primary input {index} has invalid size"
            )
        normalized_inputs.append(normalized)
    if len({record["path"] for record in normalized_inputs}) != len(normalized_inputs):
        raise InputVerificationError("Historical rescore primary inputs are duplicated")
    required_inputs = {
        (
            analysis["campaign_manifest"]["path"],
            analysis["campaign_manifest"]["sha256"],
        ),
        (benchmark["path"], benchmark["sha256"]),
    }
    observed_inputs = {
        (record["path"], record["sha256"]) for record in normalized_inputs
    }
    if not required_inputs <= observed_inputs:
        raise InputVerificationError(
            "Historical outcome rescore summary is not tied to frozen inputs"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "outcome_evaluator": evaluator,
        "baseline_outcome_mean": baseline_mean,
        "candidate_outcome_mean": mean,
        "candidate_outcome_minimum": minimum,
        "candidate_exact_outcome_minimum": minimum_exact,
        "candidate_total_exact_outcome_successes": total_exact,
        "baseline_exact_outcome_successes": baseline_exact,
        "candidate_run_count": run_count,
        "provenance_status": payload["provenance_status"],
    }


def _verify_active_validation_thresholds(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    benchmark: dict[str, Any],
    fixture: dict[str, Any],
    analysis: dict[str, dict[str, Any]],
    superseded: dict[str, Any],
    execution_policy: dict[str, Any],
    historical_rescore: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "active_validation_thresholds"),
        "active publication validation thresholds",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "active_validation_thresholds"),
        "active publication validation thresholds",
    )
    payload = _read_object(path, "active publication validation thresholds")
    expected_fields = {
        "schema_version",
        "purpose",
        "performance_endpoint",
        "supersedes",
        "execution_policy",
        "outcome_evaluator",
        "benchmark",
        "historical_reference",
        "required_integrity",
        "required_no_regression",
        "report_only",
    }
    if set(payload) != expected_fields:
        raise InputVerificationError(
            "Active publication validation threshold fields are not exact"
        )
    if payload.get("schema_version") != 2:
        raise InputVerificationError(
            "Active publication validation thresholds schema version is not 2"
        )
    if payload.get("performance_endpoint") != "outcome_task_completion_similarity":
        raise InputVerificationError(
            "Active publication validation endpoint is not outcome/task completion"
        )
    if any(
        "canonical" in str(key).lower() or "reference" in str(key).lower()
        for key in _object(
            payload,
            "required_no_regression",
            "active publication validation thresholds",
        )
    ):
        raise InputVerificationError(
            "Active publication validation contains a non-outcome performance gate"
        )
    supersedes = _object(payload, "supersedes", "active validation thresholds")
    if supersedes.get("path") != superseded["path"] or supersedes.get(
        "sha256"
    ) != superseded.get("sha256"):
        raise InputVerificationError(
            "Active validation thresholds do not identify the superseded policy"
        )
    no_regression = _object(
        payload,
        "required_no_regression",
        "active validation thresholds",
    )
    expected_no_regression = {
        "candidate_outcome_minimum": historical_rescore["candidate_outcome_minimum"],
        "minimum_relative_outcome_lift_percent_over_same_run_control": 10.0,
    }
    if set(no_regression) != set(expected_no_regression) or any(
        type(no_regression[field]) is not type(expected)
        or no_regression[field] != expected
        for field, expected in expected_no_regression.items()
    ):
        raise InputVerificationError(
            "Active no-regression thresholds do not match the exact outcome-only policy"
        )
    evaluator = _outcome_evaluator_identity(
        _object(payload, "outcome_evaluator", "active thresholds"),
        "active threshold outcome evaluator",
    )
    if evaluator != historical_rescore["outcome_evaluator"]:
        raise InputVerificationError(
            "Active thresholds use a different outcome evaluator than the rescore"
        )
    historical = _object(payload, "historical_reference", "active thresholds")
    expected_historical = {
        "status": historical_rescore["provenance_status"],
        "summary_path": historical_rescore["path"],
        "summary_sha256": historical_rescore["sha256"],
        "campaign_manifest": analysis["campaign_manifest"]["path"],
        "campaign_manifest_sha256": analysis["campaign_manifest"]["sha256"],
        "evidence_data": analysis["evidence_data"]["path"],
        "evidence_data_sha256": analysis["evidence_data"]["sha256"],
        "online_run_count": historical_rescore["candidate_run_count"],
        "candidate_outcome_mean": historical_rescore["candidate_outcome_mean"],
        "candidate_outcome_minimum": historical_rescore["candidate_outcome_minimum"],
        "original_v140_outcome_mean": historical_rescore["baseline_outcome_mean"],
    }
    if not _exact_equal(historical, expected_historical):
        raise InputVerificationError(
            "Active thresholds disagree with the historical outcome rescore"
        )
    execution = _object(payload, "execution_policy", "active thresholds")
    if not _exact_equal(
        execution,
        {
            "path": execution_policy["path"],
            "sha256": execution_policy["sha256"],
        },
    ):
        raise InputVerificationError(
            "Active thresholds reference a different execution policy"
        )
    threshold_benchmark = _object(payload, "benchmark", "active thresholds")
    expected_benchmark = {
        "task_count": benchmark["task_count"],
        "outcome_scored_task_count": benchmark["task_count"],
        "manifest_sha256": benchmark["sha256"],
        "ordered_task_name_sha256": benchmark["ordered_task_names_sha256"],
    }
    if not _exact_equal(threshold_benchmark, expected_benchmark):
        raise InputVerificationError("Active thresholds disagree with the benchmark")
    if threshold_benchmark.get("outcome_scored_task_count") != benchmark["task_count"]:
        raise InputVerificationError(
            "Active thresholds do not require an outcome for every benchmark task"
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
        "parallel_arms": True,
        "reflection_control_delivery": "task_synchronous_stream",
        "external_task_compare_dashboard_required": True,
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
    if (
        report_only.get("compare_candidate_outcome_to_historical_mean")
        != historical_rescore["candidate_outcome_mean"]
    ):
        raise InputVerificationError(
            "Active report-only outcome mean changed from the frozen reference"
        )
    expected_report_only = {
        "compare_candidate_outcome_to_historical_mean": historical_rescore[
            "candidate_outcome_mean"
        ],
        "mechanism_counts_are_release_gates": False,
    }
    if not _exact_equal(report_only, expected_report_only):
        raise InputVerificationError(
            "Active thresholds report-only policy is not exact"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "performance_endpoint": "outcome_task_completion_similarity",
        "outcome_evaluator": evaluator,
    }


def _verify_production_scientific_core(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    """Verify the exact result-critical core preserved during release cleanup."""

    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "production_scientific_core"),
        "production scientific core manifest",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "production_scientific_core"),
        "production scientific core manifest",
    )
    payload = _read_object(path, "production scientific core manifest")
    expected_fields = {
        "schema_version",
        "manifest_type",
        "purpose",
        "source_checkpoint",
        "counting_method",
        "physical_lines",
        "file_manifest_sha256",
        "files",
    }
    if set(payload) != expected_fields:
        raise InputVerificationError(
            "Production scientific core manifest fields are not exact"
        )
    if payload.get("schema_version") != 1 or payload.get("manifest_type") != (
        "sage_production_scientific_core"
    ):
        raise InputVerificationError("Unsupported production scientific core manifest")
    checkpoint = _object(payload, "source_checkpoint", "production scientific core")
    if set(checkpoint) != {"git_commit", "git_tree"} or any(
        not _HEX_GIT_OBJECT.fullmatch(str(checkpoint.get(field, "")))
        for field in ("git_commit", "git_tree")
    ):
        raise InputVerificationError(
            "Production scientific core source checkpoint is malformed"
        )
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        raise InputVerificationError("Production scientific core file list is empty")
    seen: set[str] = set()
    total_lines = 0
    canonical_rows: list[str] = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "path",
            "physical_lines",
            "sha256",
        }:
            raise InputVerificationError(
                f"Production scientific core entry {index} is malformed"
            )
        label = f"production scientific core entry {index}"
        source_path, source_relative = _tracked_file(
            repo_root,
            _string(raw_entry, "path", label),
            label,
        )
        if source_relative in seen:
            raise InputVerificationError(
                f"Duplicate production scientific core path: {source_relative}"
            )
        seen.add(source_relative)
        expected_lines = _integer(raw_entry, "physical_lines", label)
        observed_lines = len(source_path.read_text(encoding="utf-8").splitlines())
        if observed_lines != expected_lines:
            raise InputVerificationError(
                f"Production scientific core line count changed for {source_relative}: "
                f"expected {expected_lines}, observed {observed_lines}"
            )
        source_hash = _assert_hash(
            source_path,
            _hash(raw_entry, "sha256", label),
            label,
        )
        total_lines += observed_lines
        canonical_rows.append(f"{source_relative}\t{observed_lines}\t{source_hash}\n")
    declared_total = _integer(payload, "physical_lines", "production scientific core")
    if total_lines != declared_total:
        raise InputVerificationError(
            "Production scientific core aggregate line count changed"
        )
    observed_manifest_hash = hashlib.sha256(
        "".join(canonical_rows).encode("utf-8")
    ).hexdigest()
    if observed_manifest_hash != _hash(
        payload,
        "file_manifest_sha256",
        "production scientific core",
    ):
        raise InputVerificationError(
            "Production scientific core aggregate file manifest changed"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "physical_lines": total_lines,
        "file_count": len(entries),
        "file_manifest_sha256": observed_manifest_hash,
        "source_checkpoint": checkpoint,
    }


def verify_active_production_scientific_core(
    repo_root: Path = REPO_ROOT,
    declaration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify the active core independently of the pending release generation."""

    return _verify_production_scientific_core(
        repo_root.resolve(),
        declaration or ACTIVE_PRODUCTION_CORE_DECLARATION,
    )


def verify_inputs(
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    active_core_declaration: dict[str, Any] | None = None,
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
    if set(selected_payload) != {
        "schema_version",
        "manifest_type",
        "created_at",
        "purpose",
        "supersedes_release_manifest",
        "base_input_manifest",
        "production_scientific_core",
        "checkpoint_policy_amendment",
        "active_execution_policy",
        "historical_outcome_rescore_summary",
        "active_validation_thresholds",
    }:
        raise InputVerificationError(
            "Publication release manifest fields are not exact"
        )

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
    release_core_declaration = _object(
        selected_payload,
        "production_scientific_core",
        "publication release manifest",
    )
    if active_core_declaration is not None and not _exact_equal(
        release_core_declaration,
        active_core_declaration,
    ):
        raise InputVerificationError(
            "Publication release manifest does not bind the active production "
            "scientific core"
        )
    result["production_scientific_core"] = _verify_production_scientific_core(
        root,
        active_core_declaration or release_core_declaration,
    )
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
    superseded_release = _verify_superseded_release_manifest(
        root,
        _object(
            selected_payload,
            "supersedes_release_manifest",
            "publication release manifest",
        ),
        base_declaration=base_declaration,
        amendment_declaration=_object(
            selected_payload,
            "checkpoint_policy_amendment",
            "publication release manifest",
        ),
        benchmark=result["benchmark"],
        fixture=result["rapidapi_fixture"],
        analysis=result["historical_analysis_inputs"],
    )
    result["superseded_release_manifest"] = {
        "path": superseded_release["path"],
        "sha256": superseded_release["sha256"],
    }
    execution_policy = _verify_active_execution_policy(
        root,
        _object(
            selected_payload,
            "active_execution_policy",
            "publication release manifest",
        ),
        amendment=amendment,
        benchmark=result["benchmark"],
    )
    result["active_execution_policy"] = execution_policy
    historical_rescore = _verify_historical_outcome_rescore_summary(
        root,
        _object(
            selected_payload,
            "historical_outcome_rescore_summary",
            "publication release manifest",
        ),
        benchmark=result["benchmark"],
        analysis=result["historical_analysis_inputs"],
    )
    result["historical_outcome_rescore_summary"] = historical_rescore
    result["legacy_base_validation_thresholds"] = result["validation_thresholds"]
    superseded_thresholds = superseded_release["validation_thresholds"]
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
        execution_policy=execution_policy,
        historical_rescore=historical_rescore,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--core-manifest-only",
        action="store_true",
        help=(
            "Verify the active production scientific core without requiring the "
            "pending publication release generation."
        ),
    )
    args = parser.parse_args()
    try:
        if args.core_manifest_only:
            result = verify_active_production_scientific_core(args.repo_root)
        else:
            result = verify_inputs(
                args.repo_root,
                args.manifest,
                active_core_declaration=ACTIVE_PRODUCTION_CORE_DECLARATION,
            )
    except InputVerificationError as exc:
        raise SystemExit(f"publication_input_verification=failed\n{exc}") from exc
    print(
        "production_scientific_core_verification=pass"
        if args.core_manifest_only
        else "publication_input_verification=pass"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
