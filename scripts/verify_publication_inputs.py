#!/usr/bin/env python3
"""Verify the compact, Git-tracked publication inputs without local archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import lzma
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
EXPECTED_ACTIVE_PRODUCTION_CORE = {
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
EXPECTED_AMENDMENT_POLICY_SUPERSESSION = {
    "field": "generator_contract_and_repair_analysis_memoization",
    "superseded_value": "within_run_only",
    "active_value": "disabled_every_analysis_request_live",
    "scope": "all_live_publication_generation_analysis_requests",
    "reason": (
        "The repaired production runner no longer reuses contract or repair "
        "analysis responses within a run; every generation analysis request is "
        "live. The immutable 2026-09-02 amendment remains preserved as release "
        "history and is explicitly superseded only for this active policy."
    ),
}
EXPECTED_PARALLEL_TOOL_CALL_EXECUTION = {
    "auto_response_postprocessing": "none",
    "auto_response_truncation": "none",
    "parallel_model_returned_tool_calls_preserved": True,
    "all_distinct_call_content_orderings_validated": True,
    "semantic_permutation_deduplication": (
        "execution_equivalent_identical_call_contents_only"
    ),
    "semantic_permutation_deduplication_applies_to_all_arms": True,
    "tool_call_ids_alone_create_distinct_execution_order": False,
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
        "generator_contract_and_repair_analysis_memoization": (
            "disabled_every_analysis_request_live"
        ),
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
    "parallel_tool_call_execution": EXPECTED_PARALLEL_TOOL_CALL_EXECUTION,
    "actor_selection_experiment": {
        "pair_1_control_and_policy_sage": "concurrent_isolated_child_processes",
        "pair_2_independent_control_and_auto_sage": (
            "concurrent_isolated_child_processes"
        ),
        "auto_replay_timing": "after_policy_inventory_authority_completion",
        "policy_and_auto_inventory_match_required_per_task": True,
        "pilot_mechanism_eligibility_gate": {
            "applies_to": "sage_auto_selection",
            "minimum_generated_tool_called_scenarios": 1,
            "maximum_generated_tool_execution_failure_scenarios": 0,
            "called_scenario_evidence_field": (
                "auto_selection.generated_tool_called_scenarios"
            ),
            "failure_scenario_evidence_field": (
                "auto_selection.generated_tool_failed_scenarios"
            ),
            "required_before_recommending_full_1032_task_comparison": True,
            "mechanism_eligibility_not_outcome_performance": True,
        },
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


def _canonical_json_sha256(payload: Any) -> str:
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ordered_names_sha256(names: list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


def _verify_measurement_archive(
    repo_root: Path,
    source: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    expected_source_fields = {
        "raw_local_path",
        "raw_available_in_public_release",
        "raw_file_sha256",
        "payload_content_address_sha256",
        "public_archive",
    }
    if set(source) != expected_source_fields:
        raise InputVerificationError(f"{label} source-artifact fields are not exact")
    _string(source, "raw_local_path", label)
    if source.get("raw_available_in_public_release") is not False:
        raise InputVerificationError(f"{label} raw ignored JSON is marked public")
    raw_sha256 = _hash(source, "raw_file_sha256", label)
    expected_payload_sha256 = _hash(source, "payload_content_address_sha256", label)
    archive = _object(source, "public_archive", label)
    if set(archive) != {
        "path",
        "compression",
        "sha256",
        "size",
        "uncompressed_size",
        "uncompressed_sha256",
    }:
        raise InputVerificationError(f"{label} public-archive fields are not exact")
    archive_path, archive_relative = _tracked_file(
        repo_root,
        _string(archive, "path", f"{label} archive"),
        f"{label} public archive",
    )
    archive_sha256 = _assert_hash(
        archive_path,
        _hash(archive, "sha256", f"{label} archive"),
        f"{label} public archive",
    )
    archive_size = _integer(archive, "size", f"{label} archive")
    if archive_size != archive_path.stat().st_size or archive_size >= 500_000:
        raise InputVerificationError(
            f"{label} public archive size is wrong or reaches the 500 KB hook limit"
        )
    compression = _string(archive, "compression", f"{label} archive")
    compressed = archive_path.read_bytes()
    try:
        if compression == "gzip-9-no-name":
            if len(compressed) < 10 or compressed[:3] != b"\x1f\x8b\x08":
                raise InputVerificationError(f"{label} is not a gzip stream")
            if compressed[3] & 0x08 or compressed[4:8] != b"\x00\x00\x00\x00":
                raise InputVerificationError(
                    f"{label} gzip header contains a name or nonzero timestamp"
                )
            raw = gzip.decompress(compressed)
        elif compression == "xz-9e-single-thread-sha256":
            raw = lzma.decompress(compressed, format=lzma.FORMAT_XZ)
        else:
            raise InputVerificationError(f"{label} has unsupported compression")
    except (OSError, EOFError, lzma.LZMAError) as exc:
        raise InputVerificationError(f"Cannot decompress {label}: {exc}") from exc
    raw_size = _integer(archive, "uncompressed_size", f"{label} archive")
    if len(raw) != raw_size:
        raise InputVerificationError(f"{label} uncompressed size does not match")
    archive_raw_sha256 = _hash(archive, "uncompressed_sha256", f"{label} archive")
    actual_raw_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_raw_sha256 != raw_sha256 or archive_raw_sha256 != raw_sha256:
        raise InputVerificationError(f"{label} uncompressed SHA-256 does not match")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputVerificationError(f"{label} archive is not JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise InputVerificationError(f"{label} archived document is not an object")
    address = _object(document, "content_address", f"{label} archived document")
    payload = _object(document, "payload", f"{label} archived document")
    if address.get("algorithm") != "sha256(canonical-json(payload))":
        raise InputVerificationError(f"{label} content-address algorithm changed")
    recorded_payload_sha256 = _hash(address, "sha256", f"{label} content address")
    actual_payload_sha256 = _canonical_json_sha256(payload)
    if (
        recorded_payload_sha256 != expected_payload_sha256
        or actual_payload_sha256 != expected_payload_sha256
    ):
        raise InputVerificationError(f"{label} payload content address does not match")
    return {
        "path": archive_relative,
        "sha256": archive_sha256,
        "size": archive_size,
        "raw_sha256": raw_sha256,
        "raw_size": raw_size,
        "payload_content_address_sha256": expected_payload_sha256,
        "document": document,
    }


def _verify_production_core_manifest(
    repo_root: Path,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    if not _exact_equal(declaration, EXPECTED_ACTIVE_PRODUCTION_CORE):
        raise InputVerificationError("Active production core declaration changed")
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "production_core_manifest"),
        "production core manifest",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "production_core_manifest"),
        "production core manifest",
    )
    payload = _read_object(path, "production core manifest")
    if set(payload) != {
        "schema_version",
        "manifest_type",
        "purpose",
        "source_checkpoint",
        "counting_method",
        "physical_lines",
        "file_manifest_sha256",
        "files",
    }:
        raise InputVerificationError("Production core manifest fields are not exact")
    if (
        payload.get("schema_version") != 1
        or payload.get("manifest_type") != "sage_production_scientific_core"
    ):
        raise InputVerificationError("Unsupported production core manifest schema")
    source_checkpoint = _object(payload, "source_checkpoint", "production core")
    if set(source_checkpoint) != {"git_commit", "git_tree"}:
        raise InputVerificationError("Production core source checkpoint is not exact")
    _git_oid(source_checkpoint, "git_commit", "production core checkpoint")
    _git_oid(source_checkpoint, "git_tree", "production core checkpoint")
    files = payload.get("files")
    if not isinstance(files, list) or len(files) != 12:
        raise InputVerificationError("Production core must contain exactly 12 files")
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(files):
        if not isinstance(record, dict) or set(record) != {
            "path",
            "physical_lines",
            "sha256",
        }:
            raise InputVerificationError(f"Production core file {index} is not exact")
        source_path, source_relative = _tracked_file(
            repo_root,
            _string(record, "path", f"production core file {index}"),
            f"production core source file {index}",
        )
        source_sha256 = _assert_hash(
            source_path,
            _hash(record, "sha256", f"production core file {index}"),
            f"production core source file {index}",
        )
        physical_lines = _integer(
            record, "physical_lines", f"production core file {index}"
        )
        if physical_lines != len(source_path.read_bytes().splitlines()):
            raise InputVerificationError(
                f"Production core source line count changed for {source_relative}"
            )
        normalized.append(
            {
                "path": source_relative,
                "physical_lines": physical_lines,
                "sha256": source_sha256,
            }
        )
    if len({record["path"] for record in normalized}) != len(normalized):
        raise InputVerificationError("Production core manifest duplicates a file")
    physical_lines = _integer(payload, "physical_lines", "production core")
    if physical_lines != sum(record["physical_lines"] for record in normalized):
        raise InputVerificationError("Production core physical-line total changed")
    file_manifest_sha256 = _hash(payload, "file_manifest_sha256", "production core")
    manifest_rows = "".join(
        f"{record['path']}\t{record['physical_lines']}\t{record['sha256']}\n"
        for record in normalized
    ).encode("utf-8")
    if hashlib.sha256(manifest_rows).hexdigest() != file_manifest_sha256:
        raise InputVerificationError("Production core file-manifest digest changed")
    return {
        "path": relative,
        "sha256": observed_hash,
        "physical_lines": physical_lines,
        "file_count": len(normalized),
        "file_manifest_sha256": file_manifest_sha256,
        "source_checkpoint": source_checkpoint,
    }


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
        "amendment_policy_supersession",
        *EXPECTED_ACTIVE_EXECUTION_POLICY,
        "immutable_inputs_changed",
    }
    if set(payload) != expected_top_level:
        raise InputVerificationError(
            "Active publication execution policy fields are not exact"
        )
    if (
        payload.get("schema_version") != 2
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
    supersession = _object(
        payload,
        "amendment_policy_supersession",
        "active publication execution policy",
    )
    if not _exact_equal(supersession, EXPECTED_AMENDMENT_POLICY_SUPERSESSION):
        raise InputVerificationError(
            "Active publication execution policy does not exactly supersede the "
            "amendment's within-run generator memoization policy"
        )
    amendment_replacement = cast(dict[str, Any], amendment["replacement_policy"])
    if (
        amendment_replacement.get(supersession["field"])
        != supersession["superseded_value"]
    ):
        raise InputVerificationError(
            "Active execution-policy supersession does not name the frozen "
            "amendment value"
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
        "parallel_tool_call_execution": payload["parallel_tool_call_execution"],
        "actor_selection_experiment": payload["actor_selection_experiment"],
    }


def _verify_legacy_superseded_release_manifest(
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
    """Verify either the legacy release or a complete chained generation.

    The 2026-09-02 release predates the execution-policy and rescore links. Newer
    generations carry those links and recursively content-address their
    predecessor. Prior manifests are never rewritten to fit the newest schema.
    """

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
    legacy_fields = {
        "schema_version",
        "manifest_type",
        "created_at",
        "purpose",
        "base_input_manifest",
        "checkpoint_policy_amendment",
        "active_validation_thresholds",
    }
    complete_fields = {
        *legacy_fields,
        "supersedes_release_manifest",
        "active_execution_policy",
        "historical_outcome_rescore_summary",
    }
    if set(payload) == legacy_fields:
        return _verify_legacy_superseded_release_manifest(
            repo_root,
            declaration,
            base_declaration=base_declaration,
            amendment_declaration=amendment_declaration,
            benchmark=benchmark,
            fixture=fixture,
            analysis=analysis,
        )
    if set(payload) != complete_fields:
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

    predecessor = _verify_superseded_release_manifest(
        repo_root,
        _object(
            payload,
            "supersedes_release_manifest",
            "superseded publication release manifest",
        ),
        base_declaration=base_declaration,
        amendment_declaration=amendment_declaration,
        benchmark=benchmark,
        fixture=fixture,
        analysis=analysis,
    )
    component_records: dict[str, dict[str, Any]] = {}
    for field, label in (
        ("active_execution_policy", "superseded active execution policy"),
        (
            "historical_outcome_rescore_summary",
            "superseded historical outcome rescore summary",
        ),
        ("active_validation_thresholds", "superseded validation thresholds"),
    ):
        component = _object(payload, field, "superseded publication release manifest")
        component_path, component_relative = _tracked_file(
            repo_root,
            _string(component, "path", field),
            label,
        )
        component_hash = _assert_hash(
            component_path,
            _hash(component, "sha256", field),
            label,
        )
        component_records[field] = {
            "path": component_relative,
            "sha256": component_hash,
        }
    threshold_payload = _read_object(
        repo_root / component_records["active_validation_thresholds"]["path"],
        "superseded active validation thresholds",
    )
    if (
        threshold_payload.get("schema_version") != 2
        or threshold_payload.get("performance_endpoint")
        != "outcome_task_completion_similarity"
    ):
        raise InputVerificationError(
            "Superseded complete release does not identify outcome-only thresholds"
        )
    return {
        "path": relative,
        "sha256": observed_hash,
        "predecessor": {
            "path": predecessor["path"],
            "sha256": predecessor["sha256"],
        },
        "validation_thresholds": component_records["active_validation_thresholds"],
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
        "source_report_content_address_sha256": source_report["content_address_sha256"],
        "source_report_file_sha256": source_report["file_sha256"],
    }


def _verify_outcome_discrepancy_summary(
    repo_root: Path,
    declaration: dict[str, Any],
    *,
    benchmark: dict[str, Any],
    historical_rescore: dict[str, Any],
) -> dict[str, Any]:
    path, relative = _tracked_file(
        repo_root,
        _string(declaration, "path", "outcome_discrepancy_resolution_summary"),
        "outcome discrepancy resolution summary",
    )
    observed_hash = _assert_hash(
        path,
        _hash(declaration, "sha256", "outcome_discrepancy_resolution_summary"),
        "outcome discrepancy resolution summary",
    )
    payload = _read_object(path, "outcome discrepancy resolution summary")
    expected_fields = {
        "schema_version",
        "report_type",
        "created_at",
        "purpose",
        "method",
        "canonical_toolsandbox_scores_consumed",
        "source_artifacts",
        "source_run",
        "outcome_evaluator",
        "frozen_cohorts",
        "current_saved_pair",
        "historical_final_evaluator_reference",
        "same_final_evaluator_comparison",
        "paper_reported_metric_context",
        "conclusion",
        "limitation",
    }
    if set(payload) != expected_fields:
        raise InputVerificationError(
            "Outcome discrepancy resolution summary fields are not exact"
        )
    if (
        payload.get("schema_version") != 2
        or payload.get("report_type") != "outcome_discrepancy_resolution_summary"
        or payload.get("canonical_toolsandbox_scores_consumed") is not False
    ):
        raise InputVerificationError(
            "Outcome discrepancy summary schema or outcome-only policy changed"
        )
    evaluator = _outcome_evaluator_identity(
        _object(payload, "outcome_evaluator", "outcome discrepancy summary"),
        "outcome discrepancy evaluator",
    )
    if evaluator != historical_rescore["outcome_evaluator"]:
        raise InputVerificationError(
            "Outcome discrepancy summary uses a different final evaluator"
        )
    expected_cohorts = {
        "all_1032": {
            "count": benchmark["task_count"],
            "ordered_names_sha256": benchmark["ordered_task_names_sha256"],
        },
        "legacy_800": {
            "count": 800,
            "ordered_names_sha256": (
                "e296668682aca636c6812d5d730d52610b97eab65129357cb297d14f4391af8c"
            ),
        },
        "excluded_232": {
            "count": 232,
            "ordered_names_sha256": (
                "620149e549459dd831bfbc84780aaace51e3bd5a3780e01ec712434cc66be816"
            ),
        },
    }
    if not _exact_equal(payload.get("frozen_cohorts"), expected_cohorts):
        raise InputVerificationError("Outcome discrepancy cohort identities changed")

    sources = _object(payload, "source_artifacts", "outcome discrepancy summary")
    if set(sources) != {
        "historical_rescore",
        "current_pair_rescore",
        "outcome_metric_crosswalk",
        "paper_rep05_metric_bridge",
    }:
        raise InputVerificationError(
            "Outcome discrepancy source artifacts are not exact"
        )
    archives = {
        key: _verify_measurement_archive(
            repo_root,
            _object(sources, key, "outcome discrepancy sources"),
            label=key.replace("_", " "),
        )
        for key in (
            "historical_rescore",
            "current_pair_rescore",
            "outcome_metric_crosswalk",
        )
    }
    if (
        archives["historical_rescore"]["payload_content_address_sha256"]
        != historical_rescore["source_report_content_address_sha256"]
        or archives["historical_rescore"]["raw_sha256"]
        != historical_rescore["source_report_file_sha256"]
    ):
        raise InputVerificationError(
            "Historical compact summary and public archive identify different reports"
        )
    paper_bridge = _object(
        sources, "paper_rep05_metric_bridge", "outcome discrepancy sources"
    )
    if set(paper_bridge) != {
        "raw_local_path",
        "raw_available_in_public_release",
        "raw_file_sha256",
    }:
        raise InputVerificationError("Paper rep05 bridge provenance is not exact")
    _string(paper_bridge, "raw_local_path", "paper rep05 bridge")
    if paper_bridge.get("raw_available_in_public_release") is not False:
        raise InputVerificationError("Ignored paper rep05 bridge is marked public")
    paper_bridge_sha256 = _hash(paper_bridge, "raw_file_sha256", "paper rep05 bridge")

    historical_document = archives["historical_rescore"]["document"]
    current_document = archives["current_pair_rescore"]["document"]
    crosswalk_document = archives["outcome_metric_crosswalk"]["document"]
    historical_payload = _object(
        historical_document, "payload", "archived historical rescore"
    )
    current_payload = _object(current_document, "payload", "archived current rescore")
    crosswalk = _object(crosswalk_document, "payload", "archived outcome crosswalk")
    if (
        historical_payload.get("report_type")
        != "historical_terminal_trajectory_outcome_rescore"
        or current_payload.get("report_type")
        != "current_saved_pair_terminal_trajectory_outcome_rescore"
        or crosswalk.get("report_type") != "final_outcome_metric_crosswalk"
    ):
        raise InputVerificationError("An archived measurement report type changed")
    for label, report in (
        ("historical rescore", historical_payload),
        ("current-pair rescore", current_payload),
        ("metric crosswalk", crosswalk),
    ):
        report_evaluator = _outcome_evaluator_identity(
            _object(report, "outcome_evaluator", label), f"{label} evaluator"
        )
        if report_evaluator != evaluator:
            raise InputVerificationError(f"{label} evaluator identity changed")
    historical_rescorer = _object(
        historical_payload, "rescorer", "archived historical rescore"
    )
    if historical_rescorer.get("stored_score_fields_consumed") is not False:
        raise InputVerificationError("Historical rescore consumed stored scores")
    archived_baseline_results = _object(
        _object(historical_payload, "baseline", "archived historical rescore"),
        "results",
        "archived historical baseline",
    )
    archived_candidate_summary = _object(
        historical_payload, "candidate_summary", "archived historical rescore"
    )
    if (
        archived_baseline_results.get("outcome_mean")
        != historical_rescore["baseline_outcome_mean"]
        or archived_baseline_results.get("exact_outcome_successes")
        != historical_rescore["baseline_exact_outcome_successes"]
        or archived_candidate_summary.get("mean_of_run_outcome_means")
        != historical_rescore["candidate_outcome_mean"]
        or _object(
            archived_candidate_summary,
            "lower_envelope",
            "archived historical candidate summary",
        ).get("minimum_run_outcome_mean")
        != historical_rescore["candidate_outcome_minimum"]
        or archived_candidate_summary.get("total_exact_outcome_successes")
        != historical_rescore["candidate_total_exact_outcome_successes"]
    ):
        raise InputVerificationError(
            "Historical compact summary values differ from the archived raw report"
        )
    current_arms = _object(current_payload, "arms", "archived current rescore")
    if set(current_arms) != {"control", "candidate"} or any(
        not isinstance(arm, dict)
        or arm.get("stored_canonical_similarity_consumed") is not False
        for arm in current_arms.values()
    ):
        raise InputVerificationError("Current rescore consumed canonical similarity")
    metric = _object(crosswalk, "metric", "archived outcome crosswalk")
    validation = _object(crosswalk, "validation", "archived outcome crosswalk")
    if (
        metric.get("name") != "outcome_task_completion_similarity"
        or metric.get("canonical_toolsandbox_score_consumed") is not False
        or validation.get("stored_canonical_scores_consumed") is not False
    ):
        raise InputVerificationError("Outcome crosswalk consumed a canonical score")
    if not _exact_equal(crosswalk.get("cohorts"), expected_cohorts):
        raise InputVerificationError("Outcome crosswalk cohort identities changed")

    crosswalk_inputs = _object(crosswalk, "inputs", "archived outcome crosswalk")
    expected_input_links = {
        "historical_rescore": archives["historical_rescore"],
        "current_pair_rescore": archives["current_pair_rescore"],
    }
    for key, archive in expected_input_links.items():
        input_record = _object(crosswalk_inputs, key, "crosswalk inputs")
        file_record = _object(input_record, "file", f"crosswalk {key} input")
        if (
            file_record.get("sha256") != archive["raw_sha256"]
            or file_record.get("size") != archive["raw_size"]
            or input_record.get("payload_content_address_sha256")
            != archive["payload_content_address_sha256"]
        ):
            raise InputVerificationError(f"Crosswalk {key} input identity changed")
    bridge_input = _object(
        crosswalk_inputs, "paper_rep05_metric_bridge", "crosswalk inputs"
    )
    if (
        _object(bridge_input, "file", "crosswalk paper bridge").get("sha256")
        != paper_bridge_sha256
    ):
        raise InputVerificationError("Crosswalk paper bridge input identity changed")

    rows = crosswalk.get("joined_task_rows")
    if not isinstance(rows, list) or len(rows) != benchmark["task_count"]:
        raise InputVerificationError("Crosswalk does not contain 1,032 joined rows")
    if _canonical_json_sha256(rows) != crosswalk.get("joined_task_rows_sha256"):
        raise InputVerificationError("Crosswalk joined-row content hash changed")
    names: list[str] = []
    legacy_names: list[str] = []
    excluded_names: list[str] = []
    expected_arm_ids = {
        "historical_original_v140",
        *(f"historical_sage_rep{replication:02d}" for replication in range(1, 11)),
        "current_control",
        "current_candidate",
    }
    raw_joined_values: dict[str, dict[str, float]] = {
        arm_id: {} for arm_id in expected_arm_ids
    }
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != {
            "task_index",
            "task",
            "cohort",
            "outcomes",
        }:
            raise InputVerificationError(f"Crosswalk joined row {index} is not exact")
        if row.get("task_index") != index:
            raise InputVerificationError("Crosswalk task indexes are not ordered")
        name = row.get("task")
        if (
            not isinstance(name, str)
            or not name
            or name in raw_joined_values["current_candidate"]
        ):
            raise InputVerificationError("Crosswalk has a missing or duplicate task")
        cohort = row.get("cohort")
        if cohort == "legacy_800":
            legacy_names.append(name)
        elif cohort == "excluded_232":
            excluded_names.append(name)
        else:
            raise InputVerificationError("Crosswalk task has an unknown cohort")
        outcomes = row.get("outcomes")
        if not isinstance(outcomes, dict) or set(outcomes) != expected_arm_ids:
            raise InputVerificationError("Crosswalk task has incomplete arm coverage")
        names.append(name)
        for arm_id, outcome in outcomes.items():
            if not isinstance(outcome, dict) or set(outcome) != {
                "outcome_value",
                "exact_outcome_success",
            }:
                raise InputVerificationError("Crosswalk task outcome is not exact")
            value = _number(outcome, "outcome_value", f"crosswalk {arm_id}/{name}")
            if not 0.0 <= value <= 1.0:
                raise InputVerificationError("Crosswalk outcome is outside [0, 1]")
            if outcome.get("exact_outcome_success") is not (value == 1.0):
                raise InputVerificationError("Crosswalk exact-success flag disagrees")
            raw_joined_values[arm_id][name] = value
    if (
        len(names) != len(set(names))
        or _ordered_names_sha256(names) != benchmark["ordered_task_names_sha256"]
    ):
        raise InputVerificationError("Crosswalk all-1,032 order changed")
    if (
        _ordered_names_sha256(legacy_names)
        != expected_cohorts["legacy_800"]["ordered_names_sha256"]
        or _ordered_names_sha256(excluded_names)
        != expected_cohorts["excluded_232"]["ordered_names_sha256"]
    ):
        raise InputVerificationError("Crosswalk legacy/complement projection changed")

    def report_values(
        report_rows: Any, *, value_field: str, label: str
    ) -> dict[str, float]:
        if not isinstance(report_rows, list) or len(report_rows) != len(names):
            raise InputVerificationError(f"{label} row coverage is incomplete")
        result: dict[str, float] = {}
        for row in report_rows:
            if not isinstance(row, dict) or not isinstance(row.get("task"), str):
                raise InputVerificationError(f"{label} contains an invalid task row")
            value = _number(row, value_field, f"{label}/{row['task']}")
            result[row["task"]] = value
        if list(result) != names:
            raise InputVerificationError(f"{label} task order changed")
        return result

    historical_candidates = historical_payload.get("candidates")
    if not isinstance(historical_candidates, list) or len(historical_candidates) != 10:
        raise InputVerificationError("Historical archive candidate coverage changed")
    source_value_maps = {
        "historical_original_v140": report_values(
            _object(historical_payload, "baseline", "archived historical rescore").get(
                "task_outcomes"
            ),
            value_field="outcome_value",
            label="historical original-v140",
        ),
        **{
            f"historical_sage_rep{int(candidate['replication']):02d}": report_values(
                candidate.get("task_outcomes"),
                value_field="outcome_value",
                label=f"historical replication {candidate.get('replication')}",
            )
            for candidate in historical_candidates
            if isinstance(candidate, dict)
        },
        **{
            f"current_{arm_name}": report_values(
                arm.get("task_outcomes"),
                value_field="new_outcome_value",
                label=f"current {arm_name}",
            )
            for arm_name, arm in current_arms.items()
            if isinstance(arm, dict)
        },
    }
    if set(source_value_maps) != expected_arm_ids:
        raise InputVerificationError("Raw reports do not provide all 13 crosswalk arms")
    if source_value_maps != raw_joined_values:
        raise InputVerificationError(
            "Crosswalk values differ from archived raw reports"
        )

    arm_summaries = crosswalk.get("arm_summaries")
    if not isinstance(arm_summaries, list) or len(arm_summaries) != 13:
        raise InputVerificationError("Crosswalk arm summaries are incomplete")
    summaries_by_id = {
        summary.get("arm_id"): summary
        for summary in arm_summaries
        if isinstance(summary, dict)
    }
    if set(summaries_by_id) != expected_arm_ids:
        raise InputVerificationError("Crosswalk arm summary IDs changed")
    cohort_names = {
        "all_1032": names,
        "legacy_800": legacy_names,
        "excluded_232": excluded_names,
    }
    for arm_id, values_by_name in source_value_maps.items():
        arm_cohorts = _object(
            summaries_by_id[arm_id], "cohorts", f"crosswalk summary {arm_id}"
        )
        for cohort, cohort_task_names in cohort_names.items():
            values = [values_by_name[name] for name in cohort_task_names]
            expected_summary = {
                "denominator": len(values),
                "outcome_value_sum": math.fsum(values),
                "outcome_mean": math.fsum(values) / len(values),
                "exact_outcome_successes": sum(value == 1.0 for value in values),
                "exact_outcome_success_rate": sum(value == 1.0 for value in values)
                / len(values),
                "non_exact_outcomes": sum(value != 1.0 for value in values),
            }
            if not _exact_equal(arm_cohorts.get(cohort), expected_summary):
                raise InputVerificationError(
                    f"Crosswalk {arm_id}/{cohort} summary was not recomputed"
                )

    def compact(arm_id: str, cohort: str) -> dict[str, Any]:
        full = _object(
            _object(summaries_by_id[arm_id], "cohorts", f"crosswalk summary {arm_id}"),
            cohort,
            f"crosswalk summary {arm_id}",
        )
        return {
            "outcome_mean": full["outcome_mean"],
            "exact_outcome_successes": full["exact_outcome_successes"],
            "denominator": full["denominator"],
        }

    current_summary = _object(
        payload, "current_saved_pair", "outcome discrepancy summary"
    )
    for arm_name in ("control", "candidate"):
        arm = _object(current_summary, arm_name, "current saved pair summary")
        for cohort in cohort_names:
            if not _exact_equal(
                arm.get(cohort), compact(f"current_{arm_name}", cohort)
            ):
                raise InputVerificationError(
                    f"Current {arm_name}/{cohort} compact result changed"
                )
    current_candidate_all = compact("current_candidate", "all_1032")
    current_control_all = compact("current_control", "all_1032")
    if (
        current_summary.get("all_1032_candidate_minus_control_outcome_mean")
        != current_candidate_all["outcome_mean"] - current_control_all["outcome_mean"]
        or current_summary.get("all_1032_candidate_minus_control_exact_successes")
        != current_candidate_all["exact_outcome_successes"]
        - current_control_all["exact_outcome_successes"]
    ):
        raise InputVerificationError("Current compact paired outcome delta changed")
    historical_summary = _object(
        payload,
        "historical_final_evaluator_reference",
        "outcome discrepancy summary",
    )
    for summary_name, arm_id in (
        ("original_v140", "historical_original_v140"),
        ("paper_replication_05", "historical_sage_rep05"),
    ):
        arm = _object(historical_summary, summary_name, "historical compact summary")
        for cohort in cohort_names:
            if not _exact_equal(arm.get(cohort), compact(arm_id, cohort)):
                raise InputVerificationError(
                    f"Historical {summary_name}/{cohort} compact result changed"
                )
    primary = _object(
        crosswalk,
        "primary_same_final_evaluator_comparison",
        "archived outcome crosswalk",
    )
    primary_cohorts = _object(primary, "cohorts", "crosswalk primary comparison")
    compact_comparison = _object(
        payload, "same_final_evaluator_comparison", "outcome discrepancy summary"
    )
    for cohort in ("all_1032", "legacy_800"):
        delta = _object(
            _object(primary_cohorts, cohort, "crosswalk primary comparison"),
            "current_candidate_minus_historical_paper_rep05",
            "crosswalk primary comparison",
        )
        summary_delta = _object(
            compact_comparison, cohort, "outcome discrepancy comparison"
        )
        if summary_delta.get(
            "current_candidate_minus_paper_replication_05_outcome_mean"
        ) != delta.get("outcome_mean_delta") or summary_delta.get(
            "current_candidate_minus_paper_replication_05_exact_successes"
        ) != delta.get("exact_outcome_successes_delta"):
            raise InputVerificationError(
                f"Outcome discrepancy {cohort} primary delta changed"
            )
    aggregate = _object(
        crosswalk, "historical_candidate_aggregate", "archived outcome crosswalk"
    )
    aggregate_cohorts = _object(
        aggregate, "cohorts", "crosswalk historical candidate aggregate"
    )
    compact_aggregate = _object(
        historical_summary,
        "ten_run_aggregate",
        "historical compact summary",
    )
    aggregate_expectations = {
        "all_1032_mean_of_run_outcome_means": _object(
            aggregate_cohorts, "all_1032", "crosswalk historical aggregate"
        )["mean_of_run_outcome_means"],
        "all_1032_minimum_run_outcome_mean": _object(
            aggregate_cohorts, "all_1032", "crosswalk historical aggregate"
        )["minimum_run_outcome_mean"],
        "all_1032_total_exact_outcome_successes": _object(
            aggregate_cohorts, "all_1032", "crosswalk historical aggregate"
        )["total_exact_outcome_successes"],
        "legacy_800_mean_of_run_outcome_means": _object(
            aggregate_cohorts, "legacy_800", "crosswalk historical aggregate"
        )["mean_of_run_outcome_means"],
        "legacy_800_total_exact_outcome_successes": _object(
            aggregate_cohorts, "legacy_800", "crosswalk historical aggregate"
        )["total_exact_outcome_successes"],
        "excluded_232_mean_of_run_outcome_means": _object(
            aggregate_cohorts, "excluded_232", "crosswalk historical aggregate"
        )["mean_of_run_outcome_means"],
        "excluded_232_total_exact_outcome_successes": _object(
            aggregate_cohorts, "excluded_232", "crosswalk historical aggregate"
        )["total_exact_outcome_successes"],
        "run_count": aggregate["run_count"],
    }
    if not _exact_equal(compact_aggregate, aggregate_expectations):
        raise InputVerificationError("Historical compact aggregate changed")
    return {
        "path": relative,
        "sha256": observed_hash,
        "outcome_evaluator": evaluator,
        "archives": {
            key: {
                field: value for field, value in archive.items() if field != "document"
            }
            for key, archive in archives.items()
        },
        "current_candidate_outcome_mean": compact("current_candidate", "all_1032")[
            "outcome_mean"
        ],
        "historical_rep05_outcome_mean": compact("historical_sage_rep05", "all_1032")[
            "outcome_mean"
        ],
        "canonical_toolsandbox_scores_consumed": False,
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
        "generator_contract_and_repair_analysis_memoization": (
            "disabled_every_analysis_request_live"
        ),
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


def verify_active_production_scientific_core(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify the active core independently of the release chain."""

    return _verify_production_core_manifest(
        repo_root.resolve(),
        EXPECTED_ACTIVE_PRODUCTION_CORE,
    )


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
    release_schema_version = selected_payload.get("schema_version")
    common_release_fields = {
        "schema_version",
        "manifest_type",
        "created_at",
        "purpose",
        "supersedes_release_manifest",
        "base_input_manifest",
        "checkpoint_policy_amendment",
        "active_execution_policy",
        "historical_outcome_rescore_summary",
        "active_validation_thresholds",
    }
    release_v2_fields = {
        *common_release_fields,
        "outcome_discrepancy_resolution_summary",
        "production_scientific_core",
    }
    if release_schema_version == 1:
        expected_release_fields = common_release_fields
    elif release_schema_version == 2:
        expected_release_fields = release_v2_fields
    else:
        raise InputVerificationError("Unsupported publication release manifest schema")
    if set(selected_payload) != expected_release_fields:
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
    if release_schema_version == 2:
        result["outcome_discrepancy_resolution_summary"] = (
            _verify_outcome_discrepancy_summary(
                root,
                _object(
                    selected_payload,
                    "outcome_discrepancy_resolution_summary",
                    "publication release manifest",
                ),
                benchmark=result["benchmark"],
                historical_rescore=historical_rescore,
            )
        )
        result["production_scientific_core"] = _verify_production_core_manifest(
            root,
            _object(
                selected_payload,
                "production_scientific_core",
                "publication release manifest",
            ),
        )
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
            "full publication release chain."
        ),
    )
    args = parser.parse_args()
    try:
        if args.core_manifest_only:
            result = verify_active_production_scientific_core(args.repo_root)
        else:
            result = verify_inputs(args.repo_root, args.manifest)
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
