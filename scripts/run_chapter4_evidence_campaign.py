#!/usr/bin/env python3
"""Prepare and execute the bounded Chapter 4 SAGE evidence campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, cast

from scripts.research.chapter4_evidence import (
    EVIDENCE_DATA_NAME,
    EVIDENCE_HTML_NAME,
    load_run_evidence,
    verify_run_endpoint_measurements,
    write_evidence_dashboard,
)

try:
    _environment_verifier = importlib.import_module(
        "scripts.verify_publication_environment"
    )
    _run_verifier = importlib.import_module("scripts.verify_publication_run")
    _sample_verifier = importlib.import_module("scripts.verify_publication_sample")
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    _environment_verifier = importlib.import_module("verify_publication_environment")
    _run_verifier = importlib.import_module("verify_publication_run")
    _sample_verifier = importlib.import_module("verify_publication_sample")
verify_environment = _environment_verifier.verify_environment
verify_run = _run_verifier.verify_run
verify_sample = _sample_verifier.verify_sample
PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE = (
    _run_verifier.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
)
PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION = (
    _run_verifier.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
)

DEFAULT_BENCHMARK = Path(
    "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
)
DEFAULT_EXTERNAL_FIXTURE = Path(
    "artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
)
PINNED_EXTERNAL_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)
DEFAULT_FIXED_NOW = 1784832588
DEFAULT_BOOTSTRAP_ITERATIONS = 10_000
DEFAULT_RANDOMIZATION_ITERATIONS = 20_000
DEFAULT_ANALYSIS_SEED = 20260730
MAX_CONCURRENCY = 10
EXPECTED_REPLICATIONS = 10
EXPECTED_TASKS_PER_RUN = 1032
EXPECTED_PAPER_COMPARABLE_TASKS_PER_RUN = 800
DEFAULT_CAMPAIGN_SCOPE = "online-only"
CAMPAIGN_SCOPES = (DEFAULT_CAMPAIGN_SCOPE, "online-and-frozen")
PUBLICATION_MODEL = "gpt-4o-mini"
PUBLICATION_EXECUTION_ENV = {
    "TZ": "America/New_York",
    "SAGE_OPENAI_MAX_RETRIES": "5",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}
DIAGNOSTIC_FORCE_ENV_VARS = (
    "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)
BASELINE_CACHE_POLICY = "prohibited; every arm executes a live matched control"
CAMPAIGN_EXECUTION_LOCK_NAME = ".campaign_execution.lock"
CAMPAIGN_FAILURE_RECOVERY_POLICY = (
    "preserve_partial_artifacts_and_start_a_new_campaign; "
    "never_reuse_a_failed_registry_or_run"
)
GENERATION_SETTINGS_FILES = (
    Path("requirements-publication-lock.txt"),
    Path("scripts/run_native_action_4omini_ab.sh"),
    Path("scripts/run_sage_protocol.py"),
    Path("scripts/verify_publication_environment.py"),
    Path("scripts/verify_publication_run.py"),
    Path("scripts/verify_publication_sample.py"),
    Path("src/sage_ts/adapters/sage_run_adapter.py"),
    Path("src/sage_ts/generation/tool_generator.py"),
    Path("src/sage_ts/orchestration/online_birth.py"),
    Path("src/sage_ts/orchestration/self_evolution_reflection.py"),
    Path("docs/sage_protocol/publication_validation_thresholds_v3.json"),
)
SAMPLE_RELEASE_IDENTITY_FIELDS = (
    "git_commit",
    "git_tree",
    "fixed_toolsandbox_timestamp",
    "python_version",
    "python_implementation",
    "platform_system",
    "platform_machine",
    "isolated_environment",
    "environment_lock_sha256",
    "external_distribution_count",
    "external_distribution_sha256",
    "execution_environment",
)


def _expected_control_execution() -> dict[str, Any]:
    return {
        "mode": "same_run_fresh",
        "control_baseline_cache_allowed": False,
        "control_baseline_cache_constructed": False,
        "expected_fresh_controls_per_arm": EXPECTED_TASKS_PER_RUN,
        "online_reflection_source": "exact same-run control row by task name",
        "duplicate_or_missing_control_policy": "fail_closed",
    }


def _expected_statistical_plan() -> dict[str, Any]:
    return {
        "primary_measure": "outcome/task-completion similarity",
        "hypothesis_1_threshold_percent": 80,
        "hypothesis_2_threshold_percent": 10,
        "hypothesis_3_threshold_percent": 30,
        "bootstrap_iterations": DEFAULT_BOOTSTRAP_ITERATIONS,
        "randomization_iterations": DEFAULT_RANDOMIZATION_ITERATIONS,
        "seed": DEFAULT_ANALYSIS_SEED,
        "run_level_replications": EXPECTED_REPLICATIONS,
        "matched_online_task_pairs": (EXPECTED_REPLICATIONS * EXPECTED_TASKS_PER_RUN),
        "hypothesis_2_confirmatory_rule": {
            "analysis_role": "confirmatory_two_way_run_task_clustered",
            "target_contrast": "candidate_mean - 1.10 * control_mean",
            "estimate_requirement": "audited_relative_outcome_lift_percent >= 10",
            "two_way_uncertainty_requirement": (
                "two_way_run_task_bootstrap_95_ci_lower_for_target_contrast > 0"
            ),
            "run_cluster_requirement": (
                "run_cluster_bootstrap_95_ci_lower_for_target_contrast > 0"
            ),
            "run_sign_flip_requirement": "two_sided_exact_p < 0.05",
            "replication_unit": "independently_evolved_registry_run",
            "task_unit": "fixed_matched_benchmark_task",
            "iid_task_analysis_role": "descriptive_only",
        },
        "hypothesis_3_analysis_rule": {
            "analysis_role": "selection_conditioned_descriptive_only",
            "subset": "matched_tasks_with_at_least_one_generated_tool_call",
            "causal_attribution_allowed": False,
            "classification": "descriptive_only_no_hypothesis_support_decision",
            "threshold_role": "predeclared_descriptive_reference_only",
        },
        "performance_endpoints": {
            "audited_current_all_tasks": {
                "metric_field": "outcome_similarity",
                "evaluator_version": "sage_outcome_contracts_v9",
                "task_count_per_run": EXPECTED_TASKS_PER_RUN,
                "expected_matched_pairs": (
                    EXPECTED_REPLICATIONS * EXPECTED_TASKS_PER_RUN
                ),
                "aggregate_statistics": None,
            },
            "paper_comparable_historical_subset": {
                "metric_field": "online_feedback_outcome_similarity",
                "evaluator_version": "sage_paper_outcome_contracts_v1",
                "task_count_per_run": EXPECTED_PAPER_COMPARABLE_TASKS_PER_RUN,
                "expected_matched_pairs": (
                    EXPECTED_REPLICATIONS * EXPECTED_PAPER_COMPARABLE_TASKS_PER_RUN
                ),
                "aggregate_statistics": None,
            },
        },
    }


def _expected_claim_safeguards() -> dict[str, Any]:
    return {
        "scenario_name_birth_disabled": True,
        "scenario_name_routing_disabled": True,
        "visible_task_context_only": True,
        "synthetic_bridge_completions_disabled": True,
        "diagnostic_force_calls_disabled": True,
        "performance_endpoint_policy": "dual_scoped_outcome_endpoints",
        "canonical_metric_policy": "descriptive_only_never_a_release_gate",
        "sage_task_cache": "off",
        "openai_response_cache": "disabled",
        "openai_response_cache_scope": "persistent_repository_whole_response_replay",
        "persistent_generation_output_cache": "disabled",
        "generator_contract_and_repair_analysis_memoization": "within_run_only",
        "openai_provider_prompt_prefix_cache": "automatic_implicit",
        "execution_environment": dict(PUBLICATION_EXECUTION_ENV),
        "control_cache": "off",
        "cross_run_failure_memory": "disabled",
        "fresh_control_required": True,
        "parallel_arms": True,
        "release_sample_gate_purpose": PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
        "replication_gate_purpose": (PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION),
        "replication_inclusion_policy": ("integrity_provenance_completeness_only"),
        "observed_performance_controls_replication_inclusion": False,
        "online_reflection_control": "same_run_fresh",
        "online_registry_start": "empty",
        "frozen_generation": "off",
        "frozen_candidate_repair": "off",
    }


def _planned_arms(campaign_scope: str) -> tuple[str, ...]:
    if campaign_scope == DEFAULT_CAMPAIGN_SCOPE:
        return ("online",)
    if campaign_scope == "online-and-frozen":
        return ("online", "frozen")
    raise ValueError(f"Unsupported campaign scope: {campaign_scope!r}")


def _expected_execution_waves(
    maximum_parallel: int,
    campaign_scope: str = DEFAULT_CAMPAIGN_SCOPE,
) -> list[dict[str, Any]]:
    waves = [
        {
            "wave": 1,
            "description": (
                "Ten new online-build replications, each with a same-run fresh control."
            ),
            "maximum_parallel": maximum_parallel,
        },
    ]
    if campaign_scope == "online-and-frozen":
        waves.append(
            {
                "wave": 2,
                "description": (
                    "Ten paired frozen-reuse replications using registries produced "
                    "by wave 1."
                ),
                "maximum_parallel": maximum_parallel,
            }
        )
    elif campaign_scope != DEFAULT_CAMPAIGN_SCOPE:
        raise ValueError(f"Unsupported campaign scope: {campaign_scope!r}")
    return waves


def _parallel_wave_record_errors(
    manifest: dict[str, Any],
    wave: int,
) -> list[str]:
    evidence = manifest.get("parallel_wave_execution")
    if not isinstance(evidence, dict):
        return ["parallel_wave_execution must be an object"]
    record = evidence.get(str(wave))
    if not isinstance(record, dict):
        return [f"wave {wave} lacks parallel execution evidence"]

    errors: list[str] = []
    if not _exact_value(record.get("wave"), wave):
        errors.append(f"wave {wave} parallel execution evidence has the wrong wave")
    if not _exact_value(record.get("job_count"), EXPECTED_REPLICATIONS):
        errors.append(f"wave {wave} did not execute exactly 10 jobs")

    jobs = record.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_REPLICATIONS:
        errors.append(f"wave {wave} lacks exactly 10 child-process intervals")
        jobs = []

    expected_arm = "online" if wave == 1 else "frozen" if wave == 2 else None
    process_ids: list[int] = []
    ports: list[int] = []
    starts: list[int] = []
    completions: list[int] = []
    replications: list[int] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            errors.append(f"wave {wave} child interval {index} is not an object")
            continue
        replication = job.get("replication")
        process_id = job.get("process_pid")
        port = job.get("port")
        started = job.get("process_started_monotonic_ns")
        completed = job.get("process_completed_monotonic_ns")
        if (
            isinstance(replication, bool)
            or not isinstance(replication, int)
            or not 1 <= replication <= EXPECTED_REPLICATIONS
        ):
            errors.append(
                f"wave {wave} child interval {index} has an invalid replication"
            )
        else:
            replications.append(replication)
        if expected_arm is None or job.get("arm") != expected_arm:
            errors.append(f"wave {wave} child interval {index} has the wrong arm")
        if (
            isinstance(process_id, bool)
            or not isinstance(process_id, int)
            or process_id <= 0
        ):
            errors.append(f"wave {wave} child interval {index} has an invalid PID")
        else:
            process_ids.append(process_id)
        if (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
        ):
            errors.append(f"wave {wave} child interval {index} has an invalid port")
        else:
            ports.append(port)
        if isinstance(started, bool) or not isinstance(started, int) or started <= 0:
            errors.append(
                f"wave {wave} child interval {index} has an invalid start time"
            )
        else:
            starts.append(started)
        if (
            isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed <= 0
        ):
            errors.append(
                f"wave {wave} child interval {index} has an invalid completion time"
            )
        else:
            completions.append(completed)
        if (
            isinstance(started, int)
            and not isinstance(started, bool)
            and isinstance(completed, int)
            and not isinstance(completed, bool)
            and completed <= started
        ):
            errors.append(
                f"wave {wave} child interval {index} is not a positive lifetime"
            )
        if not _exact_value(job.get("return_code"), 0):
            errors.append(f"wave {wave} child interval {index} did not succeed")
        if isinstance(replication, int) and not isinstance(replication, bool):
            pair = next(
                (
                    candidate
                    for candidate in manifest.get("run_pairs") or []
                    if isinstance(candidate, dict)
                    and _exact_value(candidate.get("replication"), replication)
                ),
                None,
            )
            entry = (
                pair.get(expected_arm)
                if isinstance(pair, dict) and isinstance(expected_arm, str)
                else None
            )
            if not isinstance(entry, dict):
                errors.append(
                    f"wave {wave} child interval {index} lacks a bound run entry"
                )
            else:
                entry_bindings = {
                    "dashboard_port": port,
                    "process_pid": process_id,
                    "process_started_monotonic_ns": started,
                    "process_completed_monotonic_ns": completed,
                    "process_return_code": job.get("return_code"),
                }
                for field, expected_value in entry_bindings.items():
                    if not _exact_value(entry.get(field), expected_value):
                        errors.append(
                            f"wave {wave} child interval {index} is not bound to "
                            f"entry field {field}"
                        )

    if jobs and sorted(replications) != list(range(1, EXPECTED_REPLICATIONS + 1)):
        errors.append(f"wave {wave} child intervals are not replications 1 through 10")
    distinct_process_ids = (
        len(process_ids) == EXPECTED_REPLICATIONS
        and len(set(process_ids)) == EXPECTED_REPLICATIONS
    )
    distinct_ports = (
        len(ports) == EXPECTED_REPLICATIONS and len(set(ports)) == EXPECTED_REPLICATIONS
    )
    if record.get("distinct_process_ids") is not distinct_process_ids:
        errors.append(f"wave {wave} PID-distinctness attestation is inconsistent")
    if not distinct_process_ids:
        errors.append(f"wave {wave} did not use 10 distinct child processes")
    if record.get("distinct_ports") is not distinct_ports:
        errors.append(f"wave {wave} port-distinctness attestation is inconsistent")
    if not distinct_ports:
        errors.append(f"wave {wave} did not use 10 distinct dashboard ports")

    global_overlap_ns: int | None = None
    latest_start: int | None = None
    earliest_completion: int | None = None
    if (
        len(starts) == EXPECTED_REPLICATIONS
        and len(completions) == EXPECTED_REPLICATIONS
    ):
        latest_start = max(starts)
        earliest_completion = min(completions)
        global_overlap_ns = earliest_completion - latest_start
    if not _exact_value(record.get("latest_process_start_monotonic_ns"), latest_start):
        errors.append(f"wave {wave} latest process start is inconsistent")
    if not _exact_value(
        record.get("earliest_process_completion_monotonic_ns"),
        earliest_completion,
    ):
        errors.append(f"wave {wave} earliest process completion is inconsistent")
    if not _exact_value(record.get("global_overlap_ns"), global_overlap_ns):
        errors.append(f"wave {wave} global overlap attestation is inconsistent")
    if global_overlap_ns is None or global_overlap_ns <= 0:
        errors.append(f"wave {wave} lacks positive across-job process overlap")
    if record.get("verified") is not True:
        errors.append(f"wave {wave} parallel execution is not verified")
    return errors


def _parallel_wave_execution_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    execution_waves = manifest.get("execution_waves")
    if not isinstance(execution_waves, list):
        return ["execution_waves must be a list"]
    for wave_plan in execution_waves:
        wave = wave_plan.get("wave") if isinstance(wave_plan, dict) else None
        if isinstance(wave, bool) or not isinstance(wave, int):
            errors.append("execution wave lacks an integer wave number")
            continue
        errors.extend(_parallel_wave_record_errors(manifest, wave))
    return errors


def _exact_value(observed: Any, expected: Any) -> bool:
    """Compare plan values without treating booleans as integers."""
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _exact_value(observed[field], expected_value)
            for field, expected_value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _exact_value(observed_value, expected_value)
            for observed_value, expected_value in zip(observed, expected, strict=True)
        )
    return bool(observed == expected)


def _exact_mapping_errors(
    label: str,
    observed: Any,
    expected: dict[str, Any],
) -> list[str]:
    if not isinstance(observed, dict):
        return [f"{label} is missing"]
    errors = [
        f"{label} mismatch: {field}"
        for field, expected_value in expected.items()
        if field not in observed or not _exact_value(observed[field], expected_value)
    ]
    unexpected = sorted(set(observed) - set(expected))
    if unexpected:
        errors.append(f"{label} has undeclared fields: {', '.join(unexpected)}")
    return errors


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_paths(repo_root: Path, paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for relative_path in paths:
        path = repo_root / relative_path
        if not path.is_file():
            raise ValueError(f"Missing configuration input: {path}")
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_value(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require_clean_git(repo_root: Path) -> dict[str, Any]:
    dirty = _git_value(repo_root, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ValueError(
            "Publication campaign preparation/execution requires a clean Git tree."
        )
    environment = verify_environment(
        repo_root / "requirements-publication-lock.txt",
        repo_root=repo_root,
    )
    return {
        "git_commit": _git_value(repo_root, "rev-parse", "HEAD"),
        "git_tree": _git_value(repo_root, "rev-parse", "HEAD^{tree}"),
        "fixed_toolsandbox_timestamp": DEFAULT_FIXED_NOW,
        "python_version": environment["python_version"],
        "python_implementation": environment["python_implementation"],
        "platform_system": environment["platform_system"],
        "platform_machine": environment["platform_machine"],
        "isolated_environment": environment["isolated_environment"],
        "environment_lock_sha256": environment["environment_lock_sha256"],
        "external_distribution_count": environment["external_distribution_count"],
        "external_distribution_sha256": environment["external_distribution_sha256"],
        "execution_environment": dict(PUBLICATION_EXECUTION_ENV),
        "runtime_digest": _digest_paths(repo_root, GENERATION_SETTINGS_FILES),
        "generation_settings_digest": _digest_paths(
            repo_root,
            tuple(
                path
                for path in GENERATION_SETTINGS_FILES
                if path.name
                in {
                    "run_native_action_4omini_ab.sh",
                    "run_sage_protocol.py",
                    "sage_run_adapter.py",
                    "tool_generator.py",
                    "online_birth.py",
                    "self_evolution_reflection.py",
                }
            ),
        ),
    }


def _sample_release_identity(payload: dict[str, Any]) -> dict[str, Any]:
    integrity = payload.get("integrity_verification")
    if not isinstance(integrity, dict):
        raise ValueError("Publication sample lacks integrity verification.")
    provenance = integrity.get("publication_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Publication sample lacks release provenance.")
    identity: dict[str, Any] = {}
    for field in SAMPLE_RELEASE_IDENTITY_FIELDS:
        if field not in provenance:
            raise ValueError(f"Publication sample release provenance lacks {field!r}.")
        identity[field] = provenance[field]
    return identity


def _resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _sample_reports_match(
    repo_root: Path,
    stored: dict[str, Any],
    verified: dict[str, Any],
) -> bool:
    stored_copy = copy.deepcopy(stored)
    verified_copy = copy.deepcopy(verified)
    for payload in (stored_copy, verified_copy):
        run_root = payload.get("run_root")
        if not isinstance(run_root, str) or not run_root:
            return False
        payload["run_root"] = str(_resolve_repo_path(repo_root, run_root))
        thresholds_path = payload.get("thresholds_path")
        if isinstance(thresholds_path, str) and thresholds_path:
            payload["thresholds_path"] = str(
                _resolve_repo_path(repo_root, thresholds_path)
            )
        integrity = payload.get("integrity_verification")
        if isinstance(integrity, dict):
            integrity_run_root = integrity.get("run_root")
            if not isinstance(integrity_run_root, str) or not integrity_run_root:
                return False
            integrity["run_root"] = str(
                _resolve_repo_path(repo_root, integrity_run_root)
            )
    return stored_copy == verified_copy


def _validated_sample_report(
    repo_root: Path,
    report_path: Path,
    expected_identity: dict[str, Any],
) -> dict[str, Any]:
    resolved = report_path.resolve()
    if not resolved.is_file():
        raise ValueError(f"Publication sample report not found: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "pass":
        raise ValueError("Publication sample report is not a passing report.")
    if (
        payload.get("publication_gate_purpose")
        != PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
    ):
        raise ValueError("Publication sample did not use the release-sample gate.")
    run_root_value = payload.get("run_root")
    if not isinstance(run_root_value, str) or not run_root_value:
        raise ValueError("Publication sample report does not identify its run root.")
    declared_run_root = _resolve_repo_path(repo_root, run_root_value)
    verified = verify_sample(
        declared_run_root,
        output_path=resolved,
        write_report=False,
    )
    if verified.get("status") != "pass":
        raise ValueError("Publication sample no longer passes its frozen gates.")
    if not _sample_reports_match(repo_root, payload, verified):
        raise ValueError(
            "Publication sample report does not match a fresh read-only verification."
        )
    verified_run_root = _resolve_repo_path(repo_root, str(verified["run_root"]))
    if verified_run_root != declared_run_root:
        raise ValueError("Publication sample report/run-root binding is inconsistent.")
    release_identity = _sample_release_identity(verified)
    for field in SAMPLE_RELEASE_IDENTITY_FIELDS:
        if release_identity.get(field) != expected_identity.get(field):
            raise ValueError(
                "Publication sample was not produced by the current release "
                f"identity: {field}."
            )
    return {
        "path": _relative(repo_root, resolved),
        "sha256": _sha256(resolved),
        "run_root": _relative(repo_root, verified_run_root),
        "status": "pass",
        "publication_gate_purpose": PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
        "release_identity": release_identity,
    }


def _relative(repo_root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _campaign_paths(
    repo_root: Path,
    campaign_id: str,
) -> tuple[Path, Path, Path]:
    artifact_root = repo_root / "artifacts" / "chapter4_evidence" / campaign_id
    output_root = repo_root / "outputs" / "chapter4_evidence" / campaign_id
    return artifact_root, output_root, artifact_root / "campaign_manifest.json"


@contextmanager
def _campaign_execution_claim(
    repo_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> Iterator[Path]:
    campaign_id = manifest.get("campaign_id")
    if (
        not isinstance(campaign_id, str)
        or not campaign_id
        or campaign_id in {".", ".."}
        or Path(campaign_id).parts != (campaign_id,)
    ):
        raise SystemExit(
            "Cannot claim campaign execution: campaign_id is not one safe path "
            "component."
        )
    artifact_root, _, _ = _campaign_paths(repo_root, campaign_id)
    if not artifact_root.is_dir():
        raise SystemExit(
            "Cannot claim campaign execution because its artifact root is missing: "
            f"{artifact_root}"
        )
    lock_path = artifact_root / CAMPAIGN_EXECUTION_LOCK_NAME
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        raise SystemExit(
            "Campaign execution lock already exists. Refusing to launch; inspect "
            f"the manifest and lock before human-reviewed recovery: {lock_path}"
        ) from exc
    except OSError as exc:
        raise SystemExit(
            f"Cannot create campaign execution lock {lock_path}: {exc}"
        ) from exc

    payload = {
        "schema_version": 1,
        "pid": os.getpid(),
        "acquired_at": _now(),
        "campaign_manifest": str(manifest_path.resolve()),
    }
    lock_bytes = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    try:
        remaining = memoryview(lock_bytes)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write while recording campaign execution lock")
            remaining = remaining[written:]
        os.fsync(descriptor)
    except OSError:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)
        raise
    try:
        yield lock_path
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _stale_campaign_arm_root_errors(
    artifact_root: Path,
    output_root: Path,
) -> list[str]:
    errors: list[str] = []
    for arm_root in (
        artifact_root / "online",
        artifact_root / "frozen",
        artifact_root / "launcher_logs",
        artifact_root / CAMPAIGN_EXECUTION_LOCK_NAME,
        output_root / "online",
        output_root / "frozen",
    ):
        if arm_root.exists() or arm_root.is_symlink():
            errors.append(f"stale campaign arm root exists: {arm_root}")
    return errors


def _force_replacement_errors(
    existing: dict[str, Any],
    artifact_root: Path,
    output_root: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        planned_arms = _planned_arms(str(existing.get("campaign_scope")))
    except ValueError:
        errors.append("the existing campaign scope is invalid")
        planned_arms = ()
    pairs = existing.get("run_pairs")
    if existing.get("status") != "prepared":
        errors.append("the existing campaign status is not prepared")
    if existing.get("parallel_wave_execution") != {}:
        errors.append("the existing campaign has parallel execution evidence")
    if not isinstance(pairs, list) or len(pairs) != EXPECTED_REPLICATIONS:
        errors.append("the existing campaign does not contain exactly 10 run pairs")
        pairs = []
    events = existing.get("execution_events")
    if (
        not isinstance(events, list)
        or len(events) != 1
        or not isinstance(events[0], dict)
        or events[0].get("event") != "campaign_prepared"
    ):
        errors.append("the existing campaign has execution history beyond preparation")
    for expected_replication, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict) or not _exact_value(
            pair.get("replication"), expected_replication
        ):
            errors.append(
                f"existing replication {expected_replication} is missing or reordered"
            )
            continue
        for arm in planned_arms:
            entry = pair.get(arm)
            if not isinstance(entry, dict):
                errors.append(
                    f"existing replication {expected_replication} lacks {arm}"
                )
                continue
            if entry.get("execution_status") != "queued":
                errors.append(
                    f"existing replication {expected_replication} {arm} is not queued"
                )
            for field in (
                "run_root",
                "started_at",
                "completed_at",
                "return_code",
                "log_path",
                "verification_error",
                "verification_status",
                "status_reconciled_at",
                "dashboard_port",
                "recovery_disposition",
                "endpoint_measurements",
                "process_pid",
                "process_started_monotonic_ns",
                "process_completed_monotonic_ns",
                "process_return_code",
            ):
                value = entry.get(field)
                if value is not None and value != "":
                    errors.append(
                        f"existing replication {expected_replication} {arm} has "
                        f"execution field {field}"
                    )

    errors.extend(_stale_campaign_arm_root_errors(artifact_root, output_root))
    return errors


def prepare_campaign(args: argparse.Namespace) -> Path:
    repo_root = args.repo_root.resolve()
    campaign_scope = getattr(args, "scope", DEFAULT_CAMPAIGN_SCOPE)
    planned_arms = _planned_arms(campaign_scope)
    try:
        configuration_identity = _require_clean_git(repo_root)
        sample_validation = _validated_sample_report(
            repo_root,
            (repo_root / args.sample_validation_report),
            configuration_identity,
        )
    except (ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    benchmark = (repo_root / args.benchmark_manifest).resolve()
    if not benchmark.exists():
        raise SystemExit(f"Benchmark manifest not found: {benchmark}")
    benchmark_payload = json.loads(benchmark.read_text(encoding="utf-8"))
    scenarios = (benchmark_payload.get("splits") or {}).get("full_benchmark")
    if not isinstance(scenarios, list) or not scenarios:
        raise SystemExit(f"Benchmark has no full_benchmark split: {benchmark}")
    scenario_count = len(scenarios)
    if scenario_count != EXPECTED_TASKS_PER_RUN:
        raise SystemExit(
            f"Publication benchmark must contain 1,032 tasks; found {scenario_count}."
        )
    observed_benchmark_sha256 = _sha256(benchmark)
    if observed_benchmark_sha256 != PINNED_BENCHMARK_SHA256:
        raise SystemExit(
            "Publication benchmark hash mismatch: "
            f"expected {PINNED_BENCHMARK_SHA256}, "
            f"observed {observed_benchmark_sha256}."
        )
    external_fixture = (repo_root / args.external_fixture).resolve()
    if not external_fixture.is_file():
        raise SystemExit(f"Publication external fixture not found: {external_fixture}")
    observed_fixture_sha256 = _sha256(external_fixture)
    if observed_fixture_sha256 != PINNED_EXTERNAL_FIXTURE_SHA256:
        raise SystemExit(
            "Publication external fixture hash mismatch: "
            f"expected {PINNED_EXTERNAL_FIXTURE_SHA256}, "
            f"observed {observed_fixture_sha256}."
        )

    campaign_id = args.campaign_id or f"chapter4_claim_evidence_{_stamp()}"
    artifact_root, output_root, manifest_path = _campaign_paths(
        repo_root,
        campaign_id,
    )
    if manifest_path.exists():
        if not args.force:
            raise SystemExit(
                f"Campaign already exists: {manifest_path}. Use --force only to "
                "replace a preparation that has not started."
            )
        existing = _load_manifest(manifest_path)
        force_errors = _force_replacement_errors(
            existing,
            artifact_root,
            output_root,
        )
        if force_errors:
            raise SystemExit(
                "--force may replace only an entirely unstarted prepared campaign "
                "with no stale arm artifacts:\n" + "\n".join(force_errors)
            )
    else:
        stale_errors = _stale_campaign_arm_root_errors(
            artifact_root,
            output_root,
        )
        if stale_errors:
            raise SystemExit(
                "Campaign ID has stale arm artifacts but no campaign manifest; "
                "choose a new campaign ID after preserving the stale artifacts:\n"
                + "\n".join(stale_errors)
            )
    artifact_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    run_pairs: list[dict[str, Any]] = []
    for replicate in range(1, args.expected_online_runs + 1):
        rep_label = f"rep{replicate:02d}"
        online_output = output_root / "online" / rep_label / "native_action"
        online_artifacts = artifact_root / "online" / rep_label
        online = {
            "source": "campaign_online_build_fresh_control",
            "publication_gate_purpose": (PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION),
            "run_root": "",
            "search_root": _relative(repo_root, online_output),
            "registry_dir": _relative(
                repo_root,
                online_artifacts / "native_action_registry",
            ),
            "execution_status": "queued",
        }

        pair = {
            "replication": replicate,
            "online": online,
        }
        if "frozen" in planned_arms:
            frozen_output = output_root / "frozen" / rep_label / "frozen_registry"
            frozen_artifacts = artifact_root / "frozen" / rep_label
            pair["frozen"] = {
                "source": "paired_frozen_registry_reuse",
                "publication_gate_purpose": (
                    PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
                ),
                "run_root": "",
                "search_root": _relative(repo_root, frozen_output),
                "registry_dir": _relative(
                    repo_root,
                    frozen_artifacts / "frozen_registry_registry",
                ),
                "source_registry_dir": online["registry_dir"],
                "execution_status": "queued",
            }
        run_pairs.append(pair)

    manifest = {
        "schema_version": 2,
        "campaign_id": campaign_id,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "prepared",
        "campaign_scope": campaign_scope,
        "model": PUBLICATION_MODEL,
        "benchmark_label": "ToolSandbox complete 1,032-task benchmark",
        "benchmark_manifest": _relative(repo_root, benchmark),
        "benchmark_sha256": observed_benchmark_sha256,
        "external_fixture": {
            "policy": "validated_read_only_fixture",
            "path": _relative(repo_root, external_fixture),
            "sha256": observed_fixture_sha256,
            "mode": "read_only",
        },
        "baseline_cache": "",
        "baseline_cache_policy": BASELINE_CACHE_POLICY,
        "failure_recovery_policy": CAMPAIGN_FAILURE_RECOVERY_POLICY,
        "control_execution": _expected_control_execution(),
        "fixed_toolsandbox_timestamp": args.fixed_now,
        "expected_online_runs": args.expected_online_runs,
        "expected_frozen_runs": (
            args.expected_online_runs if "frozen" in planned_arms else 0
        ),
        "expected_tasks_per_run": scenario_count,
        "sample_validation": sample_validation,
        "maximum_parallel_runs": args.max_parallel,
        "execution_waves": _expected_execution_waves(
            args.max_parallel,
            campaign_scope,
        ),
        "statistical_plan": _expected_statistical_plan(),
        "claim_safeguards": _expected_claim_safeguards(),
        "configuration_identity": {
            **configuration_identity,
            "prompt_policy_digest": "sage_ts_protocol_v1",
        },
        "paths": {
            "artifact_root": _relative(repo_root, artifact_root),
            "output_root": _relative(repo_root, output_root),
            "dashboard_dir": _relative(repo_root, output_root / "dashboard"),
        },
        "run_pairs": run_pairs,
        "parallel_wave_execution": {},
        "execution_events": [
            {
                "at": _now(),
                "event": "campaign_prepared",
                "detail": (
                    f"{args.expected_online_runs} new online runs and "
                    f"{args.expected_online_runs if 'frozen' in planned_arms else 0} "
                    "frozen runs "
                    "queued; all controls must execute live and uncached."
                ),
            }
        ],
    }
    _atomic_json(manifest_path, manifest)
    write_evidence_dashboard(
        repo_root=repo_root,
        campaign_manifest_path=manifest_path,
        output_dir=output_root / "dashboard",
        bootstrap_iterations=args.bootstrap_iterations,
        randomization_iterations=args.randomization_iterations,
        seed=args.seed,
    )
    print(manifest_path)
    print(output_root / "dashboard" / "chapter4_evidence.html")
    return manifest_path


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Campaign manifest must be a JSON object.")
    return payload


def _campaign_prerequisite_errors(
    repo_root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    campaign_scope = manifest.get("campaign_scope")
    try:
        planned_arms = _planned_arms(str(campaign_scope))
    except ValueError:
        errors.append("campaign_scope must be exactly online-only or online-and-frozen")
        planned_arms = ()
    if not _exact_value(manifest.get("schema_version"), 2):
        errors.append("schema_version must be exactly 2")
    if manifest.get("model") != PUBLICATION_MODEL:
        errors.append(f"model must be exactly {PUBLICATION_MODEL}")
    if not _exact_value(
        manifest.get("fixed_toolsandbox_timestamp"),
        DEFAULT_FIXED_NOW,
    ):
        errors.append(
            f"fixed_toolsandbox_timestamp must be exactly {DEFAULT_FIXED_NOW}"
        )
    errors.extend(
        _exact_mapping_errors(
            "statistical plan",
            manifest.get("statistical_plan"),
            _expected_statistical_plan(),
        )
    )
    errors.extend(
        _exact_mapping_errors(
            "control execution",
            manifest.get("control_execution"),
            _expected_control_execution(),
        )
    )
    if not _exact_value(manifest.get("baseline_cache"), ""):
        errors.append("baseline_cache must be empty")
    if manifest.get("baseline_cache_policy") != BASELINE_CACHE_POLICY:
        errors.append("baseline_cache_policy must prohibit baseline-cache use")
    if manifest.get("failure_recovery_policy") != CAMPAIGN_FAILURE_RECOVERY_POLICY:
        errors.append("failure_recovery_policy must prohibit partial-run reuse")

    campaign_id = manifest.get("campaign_id")
    expected_artifact_root: Path | None = None
    expected_output_root: Path | None = None
    if (
        not isinstance(campaign_id, str)
        or not campaign_id
        or campaign_id in {".", ".."}
        or Path(campaign_id).parts != (campaign_id,)
    ):
        errors.append("campaign_id must be one non-empty path component")
    else:
        expected_artifact_root, expected_output_root, _ = _campaign_paths(
            repo_root,
            campaign_id,
        )
        expected_paths = {
            "artifact_root": _relative(repo_root, expected_artifact_root),
            "output_root": _relative(repo_root, expected_output_root),
            "dashboard_dir": _relative(
                repo_root,
                expected_output_root / "dashboard",
            ),
        }
        errors.extend(
            _exact_mapping_errors(
                "campaign paths",
                manifest.get("paths"),
                expected_paths,
            )
        )

    if manifest.get("expected_online_runs") != EXPECTED_REPLICATIONS:
        errors.append("expected_online_runs must be exactly 10")
    expected_frozen_runs = EXPECTED_REPLICATIONS if "frozen" in planned_arms else 0
    if manifest.get("expected_frozen_runs") != expected_frozen_runs:
        errors.append(
            f"expected_frozen_runs must be exactly {expected_frozen_runs} "
            f"for campaign scope {campaign_scope!r}"
        )
    if manifest.get("expected_tasks_per_run") != EXPECTED_TASKS_PER_RUN:
        errors.append("expected_tasks_per_run must be exactly 1,032")
    if manifest.get("benchmark_sha256") != PINNED_BENCHMARK_SHA256:
        errors.append("benchmark manifest hash is not the publication pin")
    benchmark_path = repo_root / str(manifest.get("benchmark_manifest") or "")
    if not benchmark_path.is_file():
        errors.append(f"missing benchmark manifest: {benchmark_path}")
    elif _sha256(benchmark_path) != PINNED_BENCHMARK_SHA256:
        errors.append("benchmark manifest bytes changed")

    pairs = manifest.get("run_pairs")
    if not isinstance(pairs, list) or len(pairs) != EXPECTED_REPLICATIONS:
        errors.append("campaign must contain exactly 10 run pairs")
        pairs = []
    replications = [pair.get("replication") for pair in pairs if isinstance(pair, dict)]
    if len(replications) != EXPECTED_REPLICATIONS or any(
        not _exact_value(observed, expected)
        for expected, observed in enumerate(replications, start=1)
    ):
        errors.append("campaign replications must be ordered 1 through 10")
    campaign_status = manifest.get("status")
    parallel_wave_execution = manifest.get("parallel_wave_execution")
    if not isinstance(parallel_wave_execution, dict):
        errors.append("parallel_wave_execution must be an object")
    elif campaign_status == "prepared" and parallel_wave_execution:
        errors.append("parallel_wave_execution must be empty while prepared")
    elif campaign_status == "complete":
        errors.extend(_parallel_wave_execution_errors(manifest))
    for expected_replication, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            errors.append("campaign contains a non-object run pair")
            continue
        online = pair.get("online")
        frozen = pair.get("frozen")
        if not isinstance(online, dict):
            errors.append(f"replication {pair.get('replication')} lacks online arm")
            continue
        if "frozen" in planned_arms and not isinstance(frozen, dict):
            errors.append(f"replication {pair.get('replication')} lacks frozen arm")
            continue
        if "frozen" not in planned_arms and "frozen" in pair:
            errors.append(
                f"replication {pair.get('replication')} has an undeclared frozen arm"
            )
        if online.get("source") != "campaign_online_build_fresh_control":
            errors.append(
                f"replication {pair.get('replication')} online source is invalid"
            )
        if (
            isinstance(frozen, dict)
            and frozen.get("source") != "paired_frozen_registry_reuse"
        ):
            errors.append(
                f"replication {pair.get('replication')} frozen source is invalid"
            )
        if expected_artifact_root is None or expected_output_root is None:
            continue
        rep_label = f"rep{expected_replication:02d}"
        expected_online_search_root = _relative(
            repo_root,
            expected_output_root / "online" / rep_label / "native_action",
        )
        expected_online_registry = _relative(
            repo_root,
            expected_artifact_root / "online" / rep_label / "native_action_registry",
        )
        expected_frozen_search_root = _relative(
            repo_root,
            expected_output_root / "frozen" / rep_label / "frozen_registry",
        )
        expected_frozen_registry = _relative(
            repo_root,
            expected_artifact_root / "frozen" / rep_label / "frozen_registry_registry",
        )
        expected_arm_paths = [
            (
                "online",
                online,
                expected_online_search_root,
                expected_online_registry,
            )
        ]
        if isinstance(frozen, dict):
            expected_arm_paths.append(
                (
                    "frozen",
                    frozen,
                    expected_frozen_search_root,
                    expected_frozen_registry,
                )
            )
        for (
            arm_name,
            entry,
            expected_search_root,
            expected_registry,
        ) in expected_arm_paths:
            if (
                entry.get("publication_gate_purpose")
                != PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
            ):
                errors.append(
                    f"replication {expected_replication} {arm_name} gate purpose "
                    "is not campaign-inclusion"
                )
            if entry.get("search_root") != expected_search_root:
                errors.append(
                    f"replication {expected_replication} {arm_name} search_root "
                    "does not match the campaign layout"
                )
            if entry.get("registry_dir") != expected_registry:
                errors.append(
                    f"replication {expected_replication} {arm_name} registry_dir "
                    "does not match the campaign layout"
                )
            declared_run_root: Path | None = None
            try:
                _, declared_run_root = _entry_roots(
                    repo_root,
                    entry,
                    arm_name,
                )
            except ValueError as exc:
                errors.append(f"replication {expected_replication} {arm_name}: {exc}")
            if campaign_status == "prepared":
                if entry.get("execution_status") != "queued":
                    errors.append(
                        f"replication {expected_replication} {arm_name} must be queued"
                    )
                if not _exact_value(entry.get("run_root"), ""):
                    errors.append(
                        f"replication {expected_replication} {arm_name} run_root "
                        "must be empty while prepared"
                    )
                for field in (
                    "started_at",
                    "completed_at",
                    "return_code",
                    "log_path",
                    "verification_error",
                    "verification_status",
                    "status_reconciled_at",
                    "dashboard_port",
                    "recovery_disposition",
                    "endpoint_measurements",
                    "process_pid",
                    "process_started_monotonic_ns",
                    "process_completed_monotonic_ns",
                    "process_return_code",
                ):
                    if field in entry:
                        errors.append(
                            f"replication {expected_replication} {arm_name} has "
                            f"prepared-state execution field {field}"
                        )
                for root_field in ("search_root", "registry_dir"):
                    root_value = entry.get(root_field)
                    if not isinstance(root_value, str) or not root_value:
                        continue
                    prepared_root = Path(root_value)
                    if not prepared_root.is_absolute():
                        prepared_root = repo_root / prepared_root
                    if prepared_root.exists() or prepared_root.is_symlink():
                        errors.append(
                            f"replication {expected_replication} {arm_name} "
                            f"prepared {root_field} already exists: {prepared_root}"
                        )
            elif campaign_status == "complete":
                if entry.get("execution_status") != "completed":
                    errors.append(
                        f"replication {expected_replication} {arm_name} is not completed"
                    )
                if not _exact_value(entry.get("return_code"), 0):
                    errors.append(
                        f"replication {expected_replication} {arm_name} did not succeed"
                    )
                if entry.get("verification_status") != "pass":
                    errors.append(
                        f"replication {expected_replication} {arm_name} lacks an "
                        "explicit passing verification attestation"
                    )
                endpoint_measurements = entry.get("endpoint_measurements")
                if (
                    not isinstance(endpoint_measurements, dict)
                    or endpoint_measurements.get("status") != "pass"
                ):
                    errors.append(
                        f"replication {expected_replication} {arm_name} lacks passing "
                        "dual-endpoint measurements"
                    )
            elif campaign_status == "incomplete" and declared_run_root is not None:
                try:
                    _verify_publication_entry(
                        repo_root,
                        manifest,
                        entry,
                        arm_name,
                    )
                except ValueError as exc:
                    errors.append(
                        f"replication {expected_replication} {arm_name} declared "
                        f"run_root is invalid: {exc}"
                    )
        if (
            isinstance(frozen, dict)
            and frozen.get("source_registry_dir") != expected_online_registry
        ):
            errors.append(
                f"replication {expected_replication} frozen source_registry_dir "
                "does not match its online registry"
            )

    maximum_parallel = manifest.get("maximum_parallel_runs")
    if campaign_scope == DEFAULT_CAMPAIGN_SCOPE and not _exact_value(
        maximum_parallel,
        MAX_CONCURRENCY,
    ):
        errors.append(
            "maximum_parallel_runs must be exactly 10 for the online-only "
            "publication campaign"
        )
    elif (
        isinstance(maximum_parallel, bool)
        or not isinstance(maximum_parallel, int)
        or not 1 <= maximum_parallel <= MAX_CONCURRENCY
    ):
        errors.append("maximum_parallel_runs must be between 1 and 10")
    elif planned_arms and not _exact_value(
        manifest.get("execution_waves"),
        _expected_execution_waves(maximum_parallel, str(campaign_scope)),
    ):
        errors.append(
            "execution_waves must exactly match the declared campaign parallelism"
        )

    fixture = manifest.get("external_fixture")
    if not isinstance(fixture, dict):
        errors.append("external fixture declaration is missing")
    else:
        fixture_path = repo_root / str(fixture.get("path") or "")
        if fixture.get("policy") != "validated_read_only_fixture":
            errors.append("external fixture policy is invalid")
        if fixture.get("mode") != "read_only":
            errors.append("external fixture mode is not read_only")
        if fixture.get("sha256") != PINNED_EXTERNAL_FIXTURE_SHA256:
            errors.append("external fixture hash is not the publication pin")
        if not fixture_path.is_file():
            errors.append(f"missing external fixture: {fixture_path}")
        elif _sha256(fixture_path) != PINNED_EXTERNAL_FIXTURE_SHA256:
            errors.append("external fixture bytes changed")

    sample = manifest.get("sample_validation")
    if not isinstance(sample, dict):
        errors.append("passing publication sample validation is not declared")
    else:
        sample_path = repo_root / str(sample.get("path") or "")
        if sample.get("status") != "pass":
            errors.append("publication sample validation is not passing")
        elif (
            sample.get("publication_gate_purpose")
            != PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
        ):
            errors.append("publication sample gate purpose is not release-sample")
        elif not sample_path.is_file():
            errors.append(f"publication sample report is missing: {sample_path}")
        elif _sha256(sample_path) != sample.get("sha256"):
            errors.append("publication sample report hash changed")
        else:
            try:
                sample_payload = _load_manifest(sample_path)
                declared_run_root_value = sample.get("run_root")
                payload_run_root_value = sample_payload.get("run_root")
                if (
                    not isinstance(declared_run_root_value, str)
                    or not declared_run_root_value
                    or not isinstance(payload_run_root_value, str)
                    or not payload_run_root_value
                ):
                    raise ValueError("sample run-root binding is missing")
                declared_run_root = _resolve_repo_path(
                    repo_root,
                    declared_run_root_value,
                )
                payload_run_root = _resolve_repo_path(
                    repo_root,
                    payload_run_root_value,
                )
                if payload_run_root != declared_run_root:
                    raise ValueError(
                        "sample report run root does not match the campaign declaration"
                    )
                verified_sample = verify_sample(
                    declared_run_root,
                    output_path=sample_path,
                    write_report=False,
                )
                if verified_sample.get("status") != "pass":
                    errors.append("publication sample no longer passes")
                elif not _sample_reports_match(
                    repo_root,
                    sample_payload,
                    verified_sample,
                ):
                    errors.append(
                        "publication sample report differs from read-only verification"
                    )
                elif _sha256(sample_path) != sample.get("sha256"):
                    errors.append(
                        "publication sample report changed during verification"
                    )
                else:
                    verified_release_identity = _sample_release_identity(
                        verified_sample
                    )
                    if sample.get("release_identity") != verified_release_identity:
                        errors.append("publication sample release identity changed")
            except ValueError as exc:
                errors.append(f"publication sample verification failed: {exc}")

    identity = manifest.get("configuration_identity")
    if not isinstance(identity, dict):
        errors.append("configuration identity is missing")
    else:
        try:
            current_identity = _require_clean_git(repo_root)
        except (ValueError, subprocess.CalledProcessError) as exc:
            errors.append(str(exc))
        else:
            for field, observed in current_identity.items():
                if identity.get(field) != observed:
                    errors.append(f"configuration identity mismatch: {field}")
            sample_identity = (
                sample.get("release_identity") if isinstance(sample, dict) else None
            )
            if not isinstance(sample_identity, dict):
                errors.append("publication sample release identity is missing")
            else:
                for field in SAMPLE_RELEASE_IDENTITY_FIELDS:
                    if sample_identity.get(field) != current_identity.get(field):
                        errors.append(
                            f"publication sample/current release mismatch: {field}"
                        )
        if identity.get("prompt_policy_digest") != "sage_ts_protocol_v1":
            errors.append("prompt policy digest is invalid")

    errors.extend(
        _exact_mapping_errors(
            "claim safeguards",
            manifest.get("claim_safeguards"),
            _expected_claim_safeguards(),
        )
    )
    return errors


def _find_pair(
    manifest: dict[str, Any],
    replicate: int,
) -> dict[str, Any]:
    for pair in manifest.get("run_pairs") or []:
        if not isinstance(pair, dict):
            continue
        if int(pair.get("replication") or 0) == replicate:
            return cast(dict[str, Any], pair)
    raise KeyError(f"Replication {replicate} is not in the campaign manifest.")


def _entry_roots(
    repo_root: Path,
    entry: dict[str, Any],
    arm: str,
) -> tuple[Path, Path | None]:
    search_raw = entry.get("search_root")
    if not isinstance(search_raw, str) or not search_raw:
        raise ValueError(f"{arm} entry does not declare a search_root.")
    search_root = _resolve_repo_path(repo_root, search_raw)
    run_raw = entry.get("run_root")
    if run_raw in (None, ""):
        return search_root, None
    if not isinstance(run_raw, str):
        raise ValueError(f"{arm} entry run_root must be a string.")
    run_root = _resolve_repo_path(repo_root, run_raw)
    try:
        run_root.relative_to(search_root)
    except ValueError as exc:
        raise ValueError(
            f"{arm} entry run_root escapes its exact campaign search_root."
        ) from exc
    return search_root, run_root


def _entry_complete(
    repo_root: Path,
    entry: dict[str, Any],
) -> bool:
    try:
        _, declared_run_root = _entry_roots(repo_root, entry, "campaign")
    except ValueError:
        return False
    if declared_run_root is not None and not declared_run_root.exists():
        return False
    evidence = load_run_evidence(repo_root, entry)
    return bool(evidence and evidence.complete)


def _verify_publication_entry(
    repo_root: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    arm: str,
) -> dict[str, Any]:
    search_root, declared_run_root = _entry_roots(repo_root, entry, arm)
    verification_root = declared_run_root or search_root
    result = verify_run(
        verification_root,
        expected_tasks=int(manifest["expected_tasks_per_run"]),
        expect_reflection=("same-run-fresh" if arm == "online" else "not-applicable"),
        expected_fixture_sha256=PINNED_EXTERNAL_FIXTURE_SHA256,
        expected_benchmark_sha256=PINNED_BENCHMARK_SHA256,
        expected_scenario_order_sha256=PINNED_SCENARIO_ORDER_SHA256,
        gate_purpose=PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION,
    )
    if not isinstance(result, dict):
        raise ValueError(f"{arm} publication verifier returned a non-object result.")
    verified_run_root_raw = result.get("run_root")
    if not isinstance(verified_run_root_raw, str) or not verified_run_root_raw:
        raise ValueError(f"{arm} publication verifier did not return a run_root.")
    verified_run_root = _resolve_repo_path(repo_root, verified_run_root_raw)
    try:
        verified_run_root.relative_to(search_root)
    except ValueError as exc:
        raise ValueError(
            f"{arm} verified run_root escapes its exact campaign search_root."
        ) from exc
    if declared_run_root is not None and verified_run_root != declared_run_root:
        raise ValueError(
            f"{arm} verifier selected a run other than its declared run_root."
        )
    endpoint_measurements = verify_run_endpoint_measurements(
        repo_root=repo_root,
        campaign_manifest=manifest,
        entry={**entry, "run_root": str(verified_run_root)},
    )
    verified = cast(dict[str, Any], dict(result))
    verified["endpoint_measurements"] = endpoint_measurements
    return verified


def _entry_is_valid(
    repo_root: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    arm: str,
) -> bool:
    if manifest.get("status") == "incomplete" and not entry.get("run_root"):
        return False
    if not _entry_complete(repo_root, entry):
        return False
    try:
        _verify_publication_entry(repo_root, manifest, entry, arm)
    except ValueError:
        return False
    return True


def _reconcile_completed_entries(
    repo_root: Path,
    manifest: dict[str, Any],
) -> None:
    """Make artifact completeness authoritative after a resumed execution."""
    reconciled_at = _now()
    arms = _planned_arms(str(manifest["campaign_scope"]))
    for pair in manifest.get("run_pairs") or []:
        for arm in arms:
            entry = pair.get(arm) or {}
            evidence = load_run_evidence(repo_root, entry)
            if evidence is None or not evidence.complete:
                continue
            try:
                verified = _verify_publication_entry(
                    repo_root,
                    manifest,
                    entry,
                    arm,
                )
            except ValueError:
                continue
            entry["run_root"] = _relative(
                repo_root,
                Path(str(verified["run_root"])),
            )
            entry["execution_status"] = "completed"
            entry["return_code"] = 0
            entry["verification_status"] = "pass"
            entry.setdefault("completed_at", reconciled_at)
            entry["status_reconciled_at"] = reconciled_at
            entry["endpoint_measurements"] = verified["endpoint_measurements"]


def _incomplete_recovery_errors(
    repo_root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    """Reject reuse of any failed, partial, or indeterminate campaign job."""
    errors: list[str] = []
    for pair in manifest.get("run_pairs") or []:
        replicate = pair.get("replication")
        for arm in _planned_arms(str(manifest["campaign_scope"])):
            entry = pair.get(arm) or {}
            execution_status = entry.get("execution_status")
            if (
                execution_status == "completed"
                and _exact_value(entry.get("return_code"), 0)
                and entry.get("verification_status") == "pass"
                and isinstance(entry.get("endpoint_measurements"), dict)
                and entry["endpoint_measurements"].get("status") == "pass"
                and isinstance(entry.get("run_root"), str)
                and entry["run_root"]
            ):
                continue
            if execution_status == "queued":
                entry_roots = [entry.get("search_root"), entry.get("registry_dir")]
                declared_roots = [
                    Path(root) if Path(root).is_absolute() else repo_root / root
                    for root in entry_roots
                    if isinstance(root, str) and root
                ]
                if len(declared_roots) == 2 and all(
                    not root.exists() and not root.is_symlink()
                    for root in declared_roots
                ):
                    continue
            errors.append(
                f"replication {replicate} {arm} is {execution_status!r} without a "
                "verified complete run; its registry/output may be partial"
            )
    for wave_plan in manifest.get("execution_waves") or []:
        if not isinstance(wave_plan, dict):
            continue
        wave = wave_plan.get("wave")
        if isinstance(wave, bool) or not isinstance(wave, int):
            continue
        wave_arm: str | None = (
            "online" if wave == 1 else "frozen" if wave == 2 else None
        )
        if wave_arm is None:
            continue
        wave_entries = [
            pair.get(wave_arm) or {}
            for pair in manifest.get("run_pairs") or []
            if isinstance(pair, dict)
        ]
        if len(wave_entries) == EXPECTED_REPLICATIONS and all(
            entry.get("execution_status") == "completed"
            and _exact_value(entry.get("return_code"), 0)
            and entry.get("verification_status") == "pass"
            and isinstance(entry.get("run_root"), str)
            and bool(entry["run_root"])
            for entry in wave_entries
        ):
            errors.extend(_parallel_wave_record_errors(manifest, wave))
    return errors


def _job_command(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    pair: dict[str, Any],
    arm: str,
    port: int,
) -> tuple[list[str], dict[str, str], Path]:
    replicate = int(pair["replication"])
    rep_label = f"rep{replicate:02d}"
    paths = manifest["paths"]
    output_root = repo_root / paths["output_root"]
    artifact_root = repo_root / paths["artifact_root"]
    model_stamp = manifest["campaign_id"]
    configuration_identity = manifest["configuration_identity"]
    provenance_env = {
        "SAGE_TS_RUNTIME_DIGEST": configuration_identity["runtime_digest"],
        "SAGE_TS_GENERATION_SETTINGS_DIGEST": configuration_identity[
            "generation_settings_digest"
        ],
        "SAGE_TS_PROMPT_POLICY_DIGEST": configuration_identity["prompt_policy_digest"],
    }
    if not all(isinstance(value, str) and value for value in provenance_env.values()):
        raise ValueError("Campaign configuration digests must be non-empty strings.")
    env = os.environ.copy()
    publication_bin = (repo_root / ".venv-publication" / "bin").resolve()
    publication_python = publication_bin / "python"
    if not publication_python.is_file() or not os.access(publication_python, os.X_OK):
        raise ValueError(
            "Publication child interpreter is missing or not executable: "
            f"{publication_python}"
        )
    interpreter_bin = str(publication_bin)
    inherited_path = env.get("PATH", "")
    env["PATH"] = (
        interpreter_bin
        if not inherited_path
        else interpreter_bin + os.pathsep + inherited_path
    )
    env.update(
        {
            "SAGE_RUN_STAMP": f"{model_stamp}_{rep_label}_{arm}",
            "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP": str(
                manifest["fixed_toolsandbox_timestamp"]
            ),
            "SAGE_BENCHMARK_MANIFEST": str(repo_root / manifest["benchmark_manifest"]),
            "CONTROL_CACHE": "off",
            "TOOLSANDBOX_RAPID_CACHE_MODE": "read_only",
            "TOOLSANDBOX_RAPID_CACHE_PATH": str(
                repo_root / manifest["external_fixture"]["path"]
            ),
            **provenance_env,
            **PUBLICATION_EXECUTION_ENV,
        }
    )
    for stale_name in (
        "SAGE_BATCH_NO_DASHBOARD_OPEN",
        "CONTROL_CACHE_ROOT",
        "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
        "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
        "RESUME_RUN_ROOT",
        "RESUME_COMPLETED_LIMIT",
        "RESUME_REGISTRY_CHECKPOINT",
        *DIAGNOSTIC_FORCE_ENV_VARS,
    ):
        env.pop(stale_name, None)
    if arm == "online":
        env["SAGE_OUTPUT_ROOT"] = str(output_root / "online" / rep_label)
        env["SAGE_ARTIFACT_ROOT"] = str(artifact_root / "online" / rep_label)
        mode = "native-only"
    elif arm == "frozen":
        source_registry = repo_root / pair["frozen"]["source_registry_dir"]
        if not (source_registry / "registry_manifest.json").exists():
            raise ValueError(
                f"Frozen replication {replicate} is missing source registry "
                f"{source_registry}"
            )
        env["SAGE_OUTPUT_ROOT"] = str(output_root / "frozen" / rep_label)
        env["SAGE_ARTIFACT_ROOT"] = str(artifact_root / "frozen" / rep_label)
        env["RESUME_REGISTRY_CHECKPOINT"] = str(source_registry)
        mode = "frozen-only"
    else:
        raise ValueError(f"Unsupported campaign arm: {arm}")
    command = [
        "bash",
        "scripts/run_native_action_4omini_ab.sh",
        "full",
        str(port),
        mode,
        PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION,
    ]
    log_path = artifact_root / "launcher_logs" / f"{rep_label}_{arm}.log"
    return command, env, log_path


def _execute_job(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    pair: dict[str, Any],
    arm: str,
    port: int,
) -> dict[str, Any]:
    command, env, log_path = _job_command(
        repo_root=repo_root,
        manifest=manifest,
        pair=pair,
        arm=arm,
        port=port,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = _now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{started_at}] command={' '.join(command)} port={port}\n")
        handle.flush()
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        process_started_monotonic_ns = time.monotonic_ns()
        return_code = process.wait()
        process_completed_monotonic_ns = time.monotonic_ns()
        verification_error: str | None = None
        verified_run_root: str | None = None
        endpoint_measurements: dict[str, Any] | None = None
        if return_code == 0:
            try:
                result = _verify_publication_entry(
                    repo_root,
                    manifest,
                    pair[arm],
                    arm,
                )
                verified_run_root = _relative(
                    repo_root,
                    Path(str(result["run_root"])),
                )
                endpoint_measurements = cast(
                    dict[str, Any],
                    result["endpoint_measurements"],
                )
                handle.write(
                    "publication_campaign_verification=pass "
                    f"run_root={result['run_root']}\n"
                )
            except ValueError as exc:
                verification_error = str(exc)
                return_code = 97
                handle.write(
                    "publication_campaign_verification=failed "
                    f"error={verification_error}\n"
                )
    return {
        "replication": int(pair["replication"]),
        "arm": arm,
        "port": port,
        "return_code": return_code,
        "started_at": started_at,
        "completed_at": _now(),
        "log_path": _relative(repo_root, log_path),
        "verification_error": verification_error,
        "verification_status": "pass" if return_code == 0 else "fail",
        "run_root": verified_run_root,
        "endpoint_measurements": endpoint_measurements,
        "process_pid": process.pid,
        "process_started_monotonic_ns": process_started_monotonic_ns,
        "process_completed_monotonic_ns": process_completed_monotonic_ns,
    }


def _refresh_dashboard(
    *,
    repo_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    final: bool,
) -> None:
    output_dir = repo_root / manifest["paths"]["dashboard_dir"]
    plan = manifest["statistical_plan"]
    write_evidence_dashboard(
        repo_root=repo_root,
        campaign_manifest_path=manifest_path,
        output_dir=output_dir,
        bootstrap_iterations=(int(plan["bootstrap_iterations"]) if final else 500),
        randomization_iterations=(
            int(plan["randomization_iterations"]) if final else 1_000
        ),
        seed=int(plan["seed"]),
    )


def _archive_failed_terminal_dashboard(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Preserve stale dashboard files away from their canonical public paths."""

    output_dir = repo_root / manifest["paths"]["dashboard_dir"]
    suffix = f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{time.time_ns()}"
    archived: list[str] = []
    errors: list[str] = []
    for filename in (EVIDENCE_HTML_NAME, EVIDENCE_DATA_NAME):
        source = output_dir / filename
        if not source.is_file() and not source.is_symlink():
            continue
        destination = source.with_name(
            f"{source.stem}.failed-verification-{suffix}{source.suffix}"
        )
        try:
            source.replace(destination)
        except OSError as exc:
            errors.append(f"{source}: {type(exc).__name__}: {exc}")
        else:
            archived.append(_relative(repo_root, destination))
    return archived, errors


def _open_aggregate_dashboard(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
) -> str:
    dashboard_path = (
        repo_root / manifest["paths"]["dashboard_dir"] / "chapter4_evidence.html"
    ).resolve()
    if not dashboard_path.is_file():
        raise ValueError(f"Aggregate campaign dashboard is missing: {dashboard_path}")
    dashboard_url = dashboard_path.as_uri()
    if sys.platform == "darwin":
        subprocess.run(
            ["open", dashboard_url],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    elif not webbrowser.open_new_tab(dashboard_url):
        raise ValueError(
            f"Could not open aggregate campaign dashboard externally: {dashboard_url}"
        )
    return str(dashboard_url)


@contextmanager
def _reserve_dashboard_ports(ports: list[int]) -> Iterator[None]:
    """Atomically prove the complete launch port set is unique and available."""
    if len(set(ports)) != len(ports):
        raise ValueError("Campaign dashboard ports must be unique.")
    invalid_ports = [port for port in ports if not 1 <= port <= 65535]
    if invalid_ports:
        raise ValueError(
            "Campaign dashboard ports must be between 1 and 65535; "
            f"observed {invalid_ports}."
        )
    reservations: list[socket.socket] = []
    try:
        for port in ports:
            reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                reservation.bind(("127.0.0.1", port))
                reservation.listen(1)
            except OSError as exc:
                reservation.close()
                raise ValueError(
                    f"Campaign dashboard port {port} is unavailable: {exc}"
                ) from exc
            reservations.append(reservation)
        yield
    finally:
        for reservation in reservations:
            reservation.close()


def _job_result_binding_error(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    pair: dict[str, Any],
    arm: str,
    port: int,
    result: Any,
) -> str | None:
    if not isinstance(result, dict):
        return "worker result binding mismatch: result is not an object"
    replicate = int(pair["replication"])
    expected_log_path = (
        repo_root
        / manifest["paths"]["artifact_root"]
        / "launcher_logs"
        / f"rep{replicate:02d}_{arm}.log"
    ).resolve()
    binding_errors: list[str] = []
    if not _exact_value(result.get("replication"), replicate):
        binding_errors.append("replication")
    if result.get("arm") != arm:
        binding_errors.append("arm")
    if not _exact_value(result.get("port"), port):
        binding_errors.append("port")
    return_code = result.get("return_code")
    if isinstance(return_code, bool) or not isinstance(return_code, int):
        binding_errors.append("return_code")
    if not isinstance(result.get("completed_at"), str) or not result["completed_at"]:
        binding_errors.append("completed_at")
    log_path = result.get("log_path")
    if (
        not isinstance(log_path, str)
        or not log_path
        or _resolve_repo_path(repo_root, log_path) != expected_log_path
    ):
        binding_errors.append("log_path")
    if return_code == 0:
        if result.get("verification_status") != "pass":
            binding_errors.append("verification_status")
        process_pid = result.get("process_pid")
        process_started = result.get("process_started_monotonic_ns")
        process_completed = result.get("process_completed_monotonic_ns")
        if (
            isinstance(process_pid, bool)
            or not isinstance(process_pid, int)
            or process_pid <= 0
        ):
            binding_errors.append("process_pid")
        if (
            isinstance(process_started, bool)
            or not isinstance(process_started, int)
            or process_started <= 0
        ):
            binding_errors.append("process_started_monotonic_ns")
        if (
            isinstance(process_completed, bool)
            or not isinstance(process_completed, int)
            or process_completed <= 0
        ):
            binding_errors.append("process_completed_monotonic_ns")
        if (
            isinstance(process_started, int)
            and not isinstance(process_started, bool)
            and isinstance(process_completed, int)
            and not isinstance(process_completed, bool)
            and process_completed <= process_started
        ):
            binding_errors.append("process_interval")
        run_root = result.get("run_root")
        if not isinstance(run_root, str) or not run_root:
            binding_errors.append("run_root")
        else:
            search_root = _resolve_repo_path(repo_root, str(pair[arm]["search_root"]))
            resolved_run_root = _resolve_repo_path(repo_root, run_root)
            try:
                resolved_run_root.relative_to(search_root)
            except ValueError:
                binding_errors.append("run_root_scope")
        if result.get("verification_error") not in (None, ""):
            binding_errors.append("verification_error")
        measurements = result.get("endpoint_measurements")
        if not isinstance(measurements, dict) or measurements.get("status") != "pass":
            binding_errors.append("endpoint_measurements")
        else:
            audited = measurements.get("audited_current_all_tasks")
            paper = measurements.get("paper_comparable_historical_subset")
            if not isinstance(audited, dict) or not _exact_value(
                audited.get("task_count"), EXPECTED_TASKS_PER_RUN
            ):
                binding_errors.append("audited_endpoint_count")
            if not isinstance(paper, dict) or not _exact_value(
                paper.get("task_count"), EXPECTED_PAPER_COMPARABLE_TASKS_PER_RUN
            ):
                binding_errors.append("paper_endpoint_count")
    if not binding_errors:
        return None
    return "worker result binding mismatch: " + ", ".join(binding_errors)


def _parallel_wave_execution_record(
    *,
    wave: int,
    jobs: list[tuple[int, str]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    def strict_int(record: dict[str, Any], key: str) -> int | None:
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    interval_records = sorted(
        [
            {
                "replication": result.get("replication"),
                "arm": result.get("arm"),
                "port": result.get("port"),
                "process_pid": result.get("process_pid"),
                "process_started_monotonic_ns": result.get(
                    "process_started_monotonic_ns"
                ),
                "process_completed_monotonic_ns": result.get(
                    "process_completed_monotonic_ns"
                ),
                "return_code": result.get("return_code"),
            }
            for result in results
        ],
        key=lambda record: (
            replication
            if (replication := strict_int(record, "replication")) is not None
            else sys.maxsize,
            str(record.get("arm")),
        ),
    )
    process_ids = [
        process_pid
        for record in interval_records
        if (process_pid := strict_int(record, "process_pid")) is not None
        and process_pid > 0
    ]
    ports = [
        port
        for record in interval_records
        if (port := strict_int(record, "port")) is not None and 1 <= port <= 65535
    ]
    starts = [
        process_started
        for record in interval_records
        if (process_started := strict_int(record, "process_started_monotonic_ns"))
        is not None
        and process_started > 0
    ]
    completions = [
        process_completed
        for record in interval_records
        if (process_completed := strict_int(record, "process_completed_monotonic_ns"))
        is not None
        and process_completed > 0
    ]
    latest_start = max(starts) if len(starts) == len(jobs) else None
    earliest_completion = min(completions) if len(completions) == len(jobs) else None
    global_overlap_ns = (
        earliest_completion - latest_start
        if latest_start is not None and earliest_completion is not None
        else None
    )
    distinct_process_ids = len(process_ids) == len(jobs) and len(
        set(process_ids)
    ) == len(jobs)
    distinct_ports = len(ports) == len(jobs) and len(set(ports)) == len(jobs)
    observed_jobs = sorted(
        (int(result["replication"]), str(result["arm"]))
        for result in results
        if isinstance(result.get("replication"), int)
        and not isinstance(result.get("replication"), bool)
        and isinstance(result.get("arm"), str)
    )
    verified = (
        len(jobs) == EXPECTED_REPLICATIONS
        and len(results) == EXPECTED_REPLICATIONS
        and observed_jobs == sorted(jobs)
        and all(_exact_value(result.get("return_code"), 0) for result in results)
        and distinct_process_ids
        and distinct_ports
        and isinstance(global_overlap_ns, int)
        and not isinstance(global_overlap_ns, bool)
        and global_overlap_ns > 0
    )
    return {
        "wave": wave,
        "job_count": len(results),
        "jobs": interval_records,
        "distinct_process_ids": distinct_process_ids,
        "distinct_ports": distinct_ports,
        "latest_process_start_monotonic_ns": latest_start,
        "earliest_process_completion_monotonic_ns": earliest_completion,
        "global_overlap_ns": global_overlap_ns,
        "verified": verified,
    }


def _stop_dashboard_refresh(
    stop_refresh: threading.Event,
    refresh_thread: threading.Thread,
) -> str | None:
    """Stop preview publishing before any terminal dashboard can be rendered."""
    stop_refresh.set()
    refresh_thread.join(timeout=30)
    if refresh_thread.is_alive():
        return (
            "dashboard refresh thread did not stop within 30 seconds; refusing "
            "terminal rendering because a stale preview could publish afterward"
        )
    return None


def _run_wave(
    *,
    repo_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    jobs: list[tuple[int, str]],
    max_parallel: int,
    base_port: int,
    wave: int,
) -> None:
    if not jobs:
        return
    if len(jobs) > MAX_CONCURRENCY or max_parallel > MAX_CONCURRENCY:
        raise ValueError("Campaign concurrency cannot exceed ten runs.")
    ports = [base_port + index for index in range(len(jobs))]
    lock = threading.Lock()
    with _reserve_dashboard_ports(ports):
        _refresh_dashboard(
            repo_root=repo_root,
            manifest_path=manifest_path,
            manifest=manifest,
            final=False,
        )
        for index, (replicate, arm) in enumerate(jobs):
            pair = _find_pair(manifest, replicate)
            pair[arm]["execution_status"] = "running"
            pair[arm]["started_at"] = _now()
            pair[arm]["dashboard_port"] = ports[index]
        manifest.setdefault("execution_events", []).append(
            {
                "at": _now(),
                "event": f"wave_{wave}_dashboard_ports_reserved",
                "ports": ports,
            }
        )
        manifest["status"] = "running"
        manifest["updated_at"] = _now()
        _atomic_json(manifest_path, manifest)

    stop_refresh = threading.Event()

    def refresh_while_running() -> None:
        while not stop_refresh.wait(30):
            try:
                current_manifest = _load_manifest(manifest_path)
                _refresh_dashboard(
                    repo_root=repo_root,
                    manifest_path=manifest_path,
                    manifest=current_manifest,
                    final=False,
                )
            except Exception as exc:  # noqa: BLE001 - preserve active runs.
                print(f"dashboard_refresh_error={exc!r}", flush=True)

    refresh_thread = threading.Thread(
        target=refresh_while_running,
        name="chapter4-evidence-refresh",
        daemon=True,
    )
    refresh_thread.start()
    failures: list[dict[str, Any]] = []
    dashboard_errors: list[str] = []
    recorded_results: list[dict[str, Any]] = []
    try:
        futures: dict[Future[dict[str, Any]], tuple[int, str]] = {}
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            for index, (replicate, arm) in enumerate(jobs):
                pair = _find_pair(manifest, replicate)
                future = executor.submit(
                    _execute_job,
                    repo_root=repo_root,
                    manifest=manifest,
                    pair=pair,
                    arm=arm,
                    port=base_port + index,
                )
                futures[future] = (replicate, arm)

            for future in as_completed(futures):
                replicate, arm = futures[future]
                expected_port = base_port + jobs.index((replicate, arm))
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - record every job result.
                    rep_label = f"rep{replicate:02d}"
                    artifact_root = repo_root / manifest["paths"]["artifact_root"]
                    result = {
                        "replication": replicate,
                        "arm": arm,
                        "port": expected_port,
                        "return_code": 98,
                        "completed_at": _now(),
                        "log_path": _relative(
                            repo_root,
                            artifact_root / "launcher_logs" / f"{rep_label}_{arm}.log",
                        ),
                        "verification_error": (
                            f"worker exception {type(exc).__name__}: {exc}"
                        ),
                        "verification_status": "fail",
                    }
                binding_error = _job_result_binding_error(
                    repo_root=repo_root,
                    manifest=manifest,
                    pair=_find_pair(manifest, replicate),
                    arm=arm,
                    port=expected_port,
                    result=result,
                )
                if binding_error is not None:
                    result = {
                        "replication": replicate,
                        "arm": arm,
                        "port": expected_port,
                        "return_code": 98,
                        "completed_at": _now(),
                        "log_path": _relative(
                            repo_root,
                            repo_root
                            / manifest["paths"]["artifact_root"]
                            / "launcher_logs"
                            / f"rep{replicate:02d}_{arm}.log",
                        ),
                        "verification_error": binding_error,
                        "verification_status": "fail",
                        "run_root": None,
                    }
                with lock:
                    pair = _find_pair(manifest, replicate)
                    entry = pair[arm]
                    entry["execution_status"] = (
                        "completed" if result["return_code"] == 0 else "failed"
                    )
                    entry["return_code"] = result["return_code"]
                    entry["completed_at"] = result["completed_at"]
                    entry["log_path"] = result["log_path"]
                    entry["verification_status"] = (
                        "pass" if result["return_code"] == 0 else "fail"
                    )
                    if result["return_code"] == 0:
                        verified_run_root = result.get("run_root")
                        if (
                            not isinstance(verified_run_root, str)
                            or not verified_run_root
                        ):
                            result["return_code"] = 98
                            result["verification_error"] = (
                                "successful worker result omitted verified run_root"
                            )
                            entry["execution_status"] = "failed"
                            entry["return_code"] = result["return_code"]
                            entry["verification_status"] = "fail"
                        else:
                            entry["run_root"] = verified_run_root
                            entry["endpoint_measurements"] = result[
                                "endpoint_measurements"
                            ]
                            entry["process_pid"] = result["process_pid"]
                            entry["process_started_monotonic_ns"] = result[
                                "process_started_monotonic_ns"
                            ]
                            entry["process_completed_monotonic_ns"] = result[
                                "process_completed_monotonic_ns"
                            ]
                            entry["process_return_code"] = 0
                    if result.get("verification_error"):
                        entry["verification_error"] = result["verification_error"]
                    else:
                        entry.pop("verification_error", None)
                    if result["return_code"] != 0:
                        entry["recovery_disposition"] = (
                            "preserve_artifacts_and_start_new_campaign"
                        )
                    else:
                        entry.pop("recovery_disposition", None)
                    manifest["updated_at"] = _now()
                    manifest.setdefault("execution_events", []).append(
                        {
                            "at": _now(),
                            "event": f"{arm}_run_finished",
                            "replication": replicate,
                            "return_code": result["return_code"],
                            "dashboard_port": result["port"],
                        }
                    )
                    _atomic_json(manifest_path, manifest)
                    try:
                        _refresh_dashboard(
                            repo_root=repo_root,
                            manifest_path=manifest_path,
                            manifest=manifest,
                            final=False,
                        )
                    except Exception as exc:  # noqa: BLE001 - finish all jobs.
                        dashboard_errors.append(repr(exc))
                        print(f"dashboard_refresh_error={exc!r}", flush=True)
                recorded_results.append(copy.deepcopy(result))
                if result["return_code"] != 0:
                    failures.append(result)
    finally:
        refresh_shutdown_error = _stop_dashboard_refresh(
            stop_refresh,
            refresh_thread,
        )
        if refresh_shutdown_error is not None:
            dashboard_errors.append(refresh_shutdown_error)

    parallel_execution = _parallel_wave_execution_record(
        wave=wave,
        jobs=jobs,
        results=recorded_results,
    )
    manifest.setdefault("parallel_wave_execution", {})[str(wave)] = parallel_execution
    manifest.setdefault("execution_events", []).append(
        {
            "at": _now(),
            "event": f"wave_{wave}_parallel_execution_checked",
            "job_count": parallel_execution["job_count"],
            "distinct_process_ids": parallel_execution["distinct_process_ids"],
            "distinct_ports": parallel_execution["distinct_ports"],
            "global_overlap_ns": parallel_execution["global_overlap_ns"],
            "verified": parallel_execution["verified"],
        }
    )
    if parallel_execution["verified"] is not True and not failures:
        attestation_error = (
            "parallel wave execution attestation failed: all 10 successful child "
            "processes must have distinct PIDs and ports with positive global overlap"
        )
        for result in recorded_results:
            result["return_code"] = 96
            result["verification_error"] = attestation_error
            result["verification_status"] = "fail"
            failures.append(result)
            pair = _find_pair(manifest, int(result["replication"]))
            entry = pair[str(result["arm"])]
            entry["execution_status"] = "failed"
            entry["return_code"] = 96
            entry["verification_error"] = attestation_error
            entry["verification_status"] = "fail"
            entry["recovery_disposition"] = "preserve_artifacts_and_start_new_campaign"
    manifest["updated_at"] = _now()
    _atomic_json(manifest_path, manifest)
    if failures or dashboard_errors:
        manifest["status"] = "incomplete"
        manifest["updated_at"] = _now()
        manifest.setdefault("execution_events", []).append(
            {
                "at": _now(),
                "event": f"wave_{wave}_failed",
                "failed_jobs": [
                    {
                        "replication": result["replication"],
                        "arm": result["arm"],
                        "return_code": result["return_code"],
                        "log_path": result["log_path"],
                    }
                    for result in failures
                ],
                "dashboard_errors": dashboard_errors,
                "parallel_execution": parallel_execution,
            }
        )
        _atomic_json(manifest_path, manifest)
        raise RuntimeError(
            f"Wave {wave} finished with {len(failures)} failed job(s) and "
            f"{len(dashboard_errors)} dashboard refresh error(s); all job results "
            "were recorded. Failed or partial jobs are preserved and may not be "
            "retried within this campaign."
        )


def _wave_jobs(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    wave: int,
) -> list[tuple[int, str]]:
    pairs = manifest.get("run_pairs") or []
    campaign_scope = str(manifest["campaign_scope"])
    jobs: list[tuple[int, str]] = []
    if wave == 1:
        for pair in pairs:
            replicate = int(pair["replication"])
            if not _entry_is_valid(
                repo_root,
                manifest,
                pair["online"],
                "online",
            ):
                jobs.append((replicate, "online"))
    elif wave == 2:
        if "frozen" not in _planned_arms(campaign_scope):
            raise ValueError("Wave 2 is not planned for an online-only campaign.")
        for pair in pairs:
            replicate = int(pair["replication"])
            if _entry_is_valid(
                repo_root,
                manifest,
                pair["online"],
                "online",
            ) and not _entry_is_valid(
                repo_root,
                manifest,
                pair["frozen"],
                "frozen",
            ):
                jobs.append((replicate, "frozen"))
    else:
        raise ValueError("Wave must be 1 or 2.")
    return jobs


def run_campaign(args: argparse.Namespace) -> None:
    repo_root = args.repo_root.resolve()
    manifest_path = args.campaign_manifest.resolve()
    manifest = _load_manifest(manifest_path)
    if not args.approve_execution:
        raise SystemExit(
            "Campaign execution is gated. Re-run with --approve-execution only "
            "after the publication rerun receives explicit human approval."
        )
    with _campaign_execution_claim(repo_root, manifest_path, manifest):
        _run_claimed_campaign(args, repo_root, manifest_path, manifest)


def _run_claimed_campaign(
    args: argparse.Namespace,
    repo_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    status = manifest.get("status")
    if status == "running":
        raise SystemExit(
            "Campaign status is 'running' after acquiring a new execution claim. "
            "Refusing automatic recovery; inspect the preserved manifest and "
            "artifacts, then mark it incomplete only after human review."
        )
    if status == "incomplete" and not getattr(args, "resume_incomplete", False):
        raise SystemExit(
            "Resuming an incomplete campaign requires --resume-incomplete after "
            "reviewing its manifest and preserved artifacts."
        )
    if status not in {"prepared", "incomplete"}:
        raise SystemExit(
            "Campaign must be prepared or explicitly resumed from a reviewed incomplete "
            f"execution; observed status={manifest.get('status')!r}."
        )
    prerequisite_errors = _campaign_prerequisite_errors(repo_root, manifest)
    if prerequisite_errors:
        raise SystemExit("\n".join(prerequisite_errors))
    if status == "incomplete":
        _reconcile_completed_entries(repo_root, manifest)
        manifest["updated_at"] = _now()
        _atomic_json(manifest_path, manifest)
        recovery_errors = _incomplete_recovery_errors(repo_root, manifest)
        if recovery_errors:
            raise SystemExit(
                "Incomplete campaign contains failed, partial, or indeterminate "
                "jobs. Their outputs and registries are preserved and must never "
                "be reused. Prepare a new campaign ID with new empty paths:\n"
                + "\n".join(recovery_errors)
            )
    declared_parallel = int(manifest["maximum_parallel_runs"])
    requested_parallel = getattr(args, "max_parallel", None)
    if requested_parallel is not None and not _exact_value(
        requested_parallel,
        declared_parallel,
    ):
        raise SystemExit(
            "--max-parallel cannot override the prepared campaign plan; it must "
            f"equal {declared_parallel}."
        )
    max_parallel = declared_parallel
    planned_waves = [int(wave["wave"]) for wave in manifest["execution_waves"]]
    waves = planned_waves if args.wave == "all" else [int(args.wave)]
    if any(wave not in planned_waves for wave in waves):
        raise SystemExit(
            f"Requested wave is not part of campaign scope {manifest['campaign_scope']!r}."
        )
    _refresh_dashboard(
        repo_root=repo_root,
        manifest_path=manifest_path,
        manifest=manifest,
        final=False,
    )
    try:
        aggregate_dashboard_url = _open_aggregate_dashboard(
            repo_root=repo_root,
            manifest=manifest,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    manifest.setdefault("execution_events", []).append(
        {
            "at": _now(),
            "event": "aggregate_dashboard_opened",
            "url": aggregate_dashboard_url,
            "external_browser": True,
        }
    )
    manifest["updated_at"] = _now()
    _atomic_json(manifest_path, manifest)
    for wave in waves:
        manifest = _load_manifest(manifest_path)
        prerequisite_errors = _campaign_prerequisite_errors(repo_root, manifest)
        if prerequisite_errors:
            raise SystemExit("\n".join(prerequisite_errors))
        jobs = _wave_jobs(
            repo_root=repo_root,
            manifest=manifest,
            wave=wave,
        )
        if len(jobs) > MAX_CONCURRENCY:
            raise SystemExit(
                f"Wave {wave} contains {len(jobs)} jobs. Split it before "
                "execution; more than ten simultaneous runs are prohibited."
            )
        manifest.setdefault("execution_events", []).append(
            {
                "at": _now(),
                "event": f"wave_{wave}_started",
                "jobs": [
                    {"replication": replicate, "arm": arm} for replicate, arm in jobs
                ],
            }
        )
        _atomic_json(manifest_path, manifest)
        _run_wave(
            repo_root=repo_root,
            manifest_path=manifest_path,
            manifest=manifest,
            jobs=jobs,
            max_parallel=max_parallel,
            base_port=args.base_port + ((wave - 1) * MAX_CONCURRENCY),
            wave=wave,
        )

    manifest = _load_manifest(manifest_path)
    prerequisite_errors = _campaign_prerequisite_errors(repo_root, manifest)
    if prerequisite_errors:
        raise SystemExit("\n".join(prerequisite_errors))
    _reconcile_completed_entries(repo_root, manifest)
    planned_arms = _planned_arms(str(manifest["campaign_scope"]))
    parallel_execution_errors = _parallel_wave_execution_errors(manifest)
    complete = not parallel_execution_errors and all(
        all(
            _entry_is_valid(repo_root, manifest, pair[arm], arm) for arm in planned_arms
        )
        for pair in manifest.get("run_pairs") or []
    )
    manifest["status"] = "complete" if complete else "incomplete"
    manifest["updated_at"] = _now()
    manifest.setdefault("execution_events", []).append(
        {
            "at": _now(),
            "event": "campaign_execution_finished",
            "complete": complete,
            "parallel_execution_errors": parallel_execution_errors,
        }
    )
    _atomic_json(manifest_path, manifest)
    try:
        _refresh_dashboard(
            repo_root=repo_root,
            manifest_path=manifest_path,
            manifest=manifest,
            final=complete,
        )
    except BaseException as exc:
        if complete:
            # A terminal dashboard is part of the publication deliverable. Never
            # leave a durable ``complete`` claim when that final aggregation could
            # not be published; all verified run/registry artifacts remain intact
            # and a reviewed resume can retry finalization without rerunning them.
            archived_dashboard_artifacts, dashboard_archive_errors = (
                _archive_failed_terminal_dashboard(
                    repo_root=repo_root,
                    manifest=manifest,
                )
            )
            manifest["status"] = "incomplete"
            manifest["updated_at"] = _now()
            terminal_event = manifest["execution_events"][-1]
            terminal_event["complete"] = False
            terminal_event["terminal_dashboard_error"] = f"{type(exc).__name__}: {exc}"
            manifest["execution_events"].append(
                {
                    "at": _now(),
                    "event": "terminal_dashboard_render_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "recovery_disposition": (
                        "preserve_verified_runs_and_retry_finalization_after_review"
                    ),
                    "archived_dashboard_artifacts": archived_dashboard_artifacts,
                    "dashboard_archive_errors": dashboard_archive_errors,
                }
            )
            _atomic_json(manifest_path, manifest)
        raise
    if not complete:
        raise SystemExit("Campaign is incomplete; inspect the campaign manifest.")
    print(repo_root / manifest["paths"]["dashboard_dir"] / "chapter4_evidence.html")


def verify_campaign(args: argparse.Namespace) -> None:
    repo_root = args.repo_root.resolve()
    manifest_path = args.campaign_manifest.resolve()
    manifest = _load_manifest(manifest_path)
    errors = _campaign_prerequisite_errors(repo_root, manifest)
    status = manifest.get("status")
    try:
        planned_arms = _planned_arms(str(manifest.get("campaign_scope")))
    except ValueError:
        planned_arms = ()
    for pair in manifest.get("run_pairs") or []:
        for arm in planned_arms:
            entry = pair.get(arm) or {}
            complete = _entry_complete(repo_root, entry)
            if status == "prepared":
                if entry.get("execution_status") != "queued":
                    errors.append(
                        f"replication {pair.get('replication')} {arm} is not queued"
                    )
                if complete or entry.get("run_root") or entry.get("started_at"):
                    errors.append(
                        f"replication {pair.get('replication')} {arm} is not unstarted"
                    )
                continue
            if status != "complete":
                errors.append(f"campaign status {status!r} is not verifiable")
                continue
            if not complete:
                errors.append(
                    f"replication {pair.get('replication')} {arm} is incomplete"
                )
                continue
            try:
                verified = _verify_publication_entry(repo_root, manifest, entry, arm)
            except ValueError as exc:
                errors.append(f"replication {pair.get('replication')} {arm}: {exc}")
            else:
                if entry.get("endpoint_measurements") != verified.get(
                    "endpoint_measurements"
                ):
                    errors.append(
                        f"replication {pair.get('replication')} {arm}: stored "
                        "dual-endpoint measurements differ from read-only verification"
                    )
    if errors:
        raise SystemExit("\n".join(errors))
    try:
        _refresh_dashboard(
            repo_root=repo_root,
            manifest_path=manifest_path,
            manifest=manifest,
            final=status == "complete",
        )
    except BaseException as exc:
        if status == "complete":
            archived_dashboard_artifacts, dashboard_archive_errors = (
                _archive_failed_terminal_dashboard(
                    repo_root=repo_root,
                    manifest=manifest,
                )
            )
            manifest["status"] = "incomplete"
            manifest["updated_at"] = _now()
            manifest.setdefault("execution_events", []).append(
                {
                    "at": _now(),
                    "event": "terminal_dashboard_render_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "recovery_disposition": (
                        "preserve_verified_runs_and_retry_finalization_after_review"
                    ),
                    "archived_dashboard_artifacts": archived_dashboard_artifacts,
                    "dashboard_archive_errors": dashboard_archive_errors,
                }
            )
            _atomic_json(manifest_path, manifest)
        raise
    if status == "prepared":
        print("chapter4_campaign_preparation_verification=pass")
    else:
        print("chapter4_campaign_completion_verification=pass")
    print(repo_root / manifest["paths"]["dashboard_dir"] / "chapter4_evidence.html")


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=Path("."))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    _common_parser(prepare)
    prepare.add_argument("--campaign-id")
    prepare.add_argument(
        "--scope",
        choices=CAMPAIGN_SCOPES,
        default=DEFAULT_CAMPAIGN_SCOPE,
        help=(
            "Execution scope. The publication default is ten online-build paired "
            "jobs; frozen reuse is optional and must be requested explicitly."
        ),
    )
    prepare.add_argument("--expected-online-runs", type=int, default=10)
    prepare.add_argument(
        "--sample-validation-report",
        type=Path,
        required=True,
        help="Passing report from the one-run strict publication validation gate.",
    )
    prepare.add_argument(
        "--benchmark-manifest",
        type=Path,
        default=DEFAULT_BENCHMARK,
    )
    prepare.add_argument(
        "--external-fixture",
        type=Path,
        default=DEFAULT_EXTERNAL_FIXTURE,
    )
    prepare.add_argument("--fixed-now", type=int, default=DEFAULT_FIXED_NOW)
    prepare.add_argument("--max-parallel", type=int, default=10)
    prepare.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=DEFAULT_BOOTSTRAP_ITERATIONS,
    )
    prepare.add_argument(
        "--randomization-iterations",
        type=int,
        default=DEFAULT_RANDOMIZATION_ITERATIONS,
    )
    prepare.add_argument("--seed", type=int, default=DEFAULT_ANALYSIS_SEED)
    prepare.add_argument("--force", action="store_true")

    run = subparsers.add_parser("run")
    _common_parser(run)
    run.add_argument("--campaign-manifest", type=Path, required=True)
    run.add_argument("--wave", choices=("1", "2", "all"), default="all")
    run.add_argument("--max-parallel", type=int)
    run.add_argument("--base-port", type=int, default=63900)
    run.add_argument(
        "--approve-execution",
        action="store_true",
        help="Acknowledge explicit human approval for the expensive paper rerun.",
    )
    run.add_argument(
        "--resume-incomplete",
        action="store_true",
        help=(
            "Acknowledge review before reconciling an incomplete campaign. Failed "
            "or partial jobs are never rerun; they require a new campaign ID."
        ),
    )

    verify = subparsers.add_parser("verify")
    _common_parser(verify)
    verify.add_argument("--campaign-manifest", type=Path, required=True)

    args = parser.parse_args()
    requested_parallel = getattr(args, "max_parallel", None)
    if (
        requested_parallel is not None
        and not 1 <= requested_parallel <= MAX_CONCURRENCY
    ):
        parser.error("--max-parallel must be between 1 and 10")
    if args.command == "prepare":
        if args.expected_online_runs != EXPECTED_REPLICATIONS:
            parser.error("--expected-online-runs must be exactly 10")
        if args.fixed_now != DEFAULT_FIXED_NOW:
            parser.error(f"--fixed-now must equal {DEFAULT_FIXED_NOW}")
        if args.bootstrap_iterations != DEFAULT_BOOTSTRAP_ITERATIONS:
            parser.error(
                f"--bootstrap-iterations must equal {DEFAULT_BOOTSTRAP_ITERATIONS}"
            )
        if args.randomization_iterations != DEFAULT_RANDOMIZATION_ITERATIONS:
            parser.error(
                "--randomization-iterations must equal "
                f"{DEFAULT_RANDOMIZATION_ITERATIONS}"
            )
        if args.seed != DEFAULT_ANALYSIS_SEED:
            parser.error(f"--seed must equal {DEFAULT_ANALYSIS_SEED}")
        if (
            args.scope == DEFAULT_CAMPAIGN_SCOPE
            and args.max_parallel != MAX_CONCURRENCY
        ):
            parser.error(
                "--max-parallel must be exactly 10 for the online-only "
                "publication campaign"
            )
        prepare_campaign(args)
    elif args.command == "run":
        run_campaign(args)
    else:
        verify_campaign(args)


if __name__ == "__main__":
    main()
