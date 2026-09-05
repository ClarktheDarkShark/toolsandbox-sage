#!/usr/bin/env python3
"""Prepare and execute the bounded Chapter 4 SAGE evidence campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import subprocess
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, cast

from sage_ts.registry.content_identity import (
    registry_content_identity,
    validate_registry_content_identity,
)
from scripts.research.chapter4_evidence import (
    load_run_evidence,
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
EXPECTED_REPLICATIONS = 10
MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB = 2
MAX_CONCURRENT_MODEL_ARMS = 10
# Backward-compatible name used by the CLI/tests: the unit is now explicitly a
# paired protocol job, and each job starts control + SAGE child processes.
MAX_CONCURRENCY = MAX_CONCURRENT_MODEL_ARMS // MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB
EXPECTED_TASKS_PER_RUN = 1032
EXPECTED_OUTCOME_SCORED_TASKS_PER_RUN = EXPECTED_TASKS_PER_RUN
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
    Path("src/sage_ts/registry/content_identity.py"),
    Path("docs/sage_protocol/publication_validation_thresholds_v5.json"),
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
REGISTRY_LINEAGE_ENTRY_FIELDS = (
    "registry_content_identity_before_run",
    "registry_content_identity_after_run",
    "source_registry_identity_before_copy",
    "registry_identity_before_run_path",
    "registry_identity_after_run_path",
    "source_registry_identity_before_copy_path",
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
        "primary_measure": "outcome/task completion",
        "hypothesis_1_threshold_percent": 80,
        "hypothesis_2_threshold_percent": 10,
        "hypothesis_3_threshold_percent": 30,
        "bootstrap_iterations": DEFAULT_BOOTSTRAP_ITERATIONS,
        "randomization_iterations": DEFAULT_RANDOMIZATION_ITERATIONS,
        "seed": DEFAULT_ANALYSIS_SEED,
        "run_level_replications": EXPECTED_REPLICATIONS,
        "matched_online_task_pairs": (EXPECTED_REPLICATIONS * EXPECTED_TASKS_PER_RUN),
        "expected_outcome_scored_pairs": (
            EXPECTED_REPLICATIONS * EXPECTED_OUTCOME_SCORED_TASKS_PER_RUN
        ),
        "outcome_scored_tasks_per_run": EXPECTED_OUTCOME_SCORED_TASKS_PER_RUN,
    }


def _expected_claim_safeguards() -> dict[str, Any]:
    return {
        "scenario_name_birth_disabled": True,
        "scenario_name_routing_disabled": True,
        "visible_task_context_only": True,
        "synthetic_bridge_completions_disabled": True,
        "diagnostic_force_calls_disabled": True,
        "performance_endpoint": "outcome_task_completion_similarity",
        "sage_task_cache": "off",
        "openai_response_cache": "disabled",
        "openai_response_cache_scope": "persistent_repository_whole_response_replay",
        "persistent_generation_output_cache": "disabled",
        "generator_contract_and_repair_analysis_memoization": (
            "disabled_every_analysis_request_live"
        ),
        "openai_provider_prompt_prefix_cache": "automatic_implicit",
        "execution_environment": dict(PUBLICATION_EXECUTION_ENV),
        "control_cache": "off",
        "cross_run_failure_memory": "disabled",
        "fresh_control_required": True,
        "parallel_arms": True,
        "reflection_control_delivery": {
            "online": "task_synchronous_stream",
            "frozen": "not_applicable_generation_disabled",
        },
        "online_reflection_control": "same_run_fresh",
        "online_registry_start": "empty",
        "frozen_generation": "off",
        "frozen_candidate_repair": "off",
    }


def _expected_execution_waves(maximum_parallel: int) -> list[dict[str, Any]]:
    return [
        {
            "wave": 1,
            "description": (
                "Ten new online-build replications, each with a same-run fresh control."
            ),
            "maximum_parallel": maximum_parallel,
            "parallelism_unit": "paired_protocol_job",
            "maximum_concurrent_model_arms": (
                maximum_parallel * MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB
            ),
        },
        {
            "wave": 2,
            "description": (
                "Ten paired frozen-reuse replications using registries produced "
                "by wave 1."
            ),
            "maximum_parallel": maximum_parallel,
            "parallelism_unit": "paired_protocol_job",
            "maximum_concurrent_model_arms": (
                maximum_parallel * MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB
            ),
        },
    ]


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
                    "content_identity.py",
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
    pairs = existing.get("run_pairs")
    if existing.get("status") != "prepared":
        errors.append("the existing campaign status is not prepared")
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
        for arm in ("online", "frozen"):
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
            "run_root": "",
            "search_root": _relative(repo_root, online_output),
            "registry_dir": _relative(
                repo_root,
                online_artifacts / "native_action_registry",
            ),
            "execution_status": "queued",
        }

        frozen_output = output_root / "frozen" / rep_label / "frozen_registry"
        frozen_artifacts = artifact_root / "frozen" / rep_label
        frozen = {
            "source": "paired_frozen_registry_reuse",
            "run_root": "",
            "search_root": _relative(repo_root, frozen_output),
            "registry_dir": _relative(
                repo_root,
                frozen_artifacts / "frozen_registry_registry",
            ),
            "source_registry_dir": online["registry_dir"],
            "execution_status": "queued",
        }
        run_pairs.append(
            {
                "replication": replicate,
                "online": online,
                "frozen": frozen,
            }
        )

    manifest = {
        "schema_version": 2,
        "campaign_id": campaign_id,
        "created_at": _now(),
        "updated_at": _now(),
        "status": "prepared",
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
        "control_execution": _expected_control_execution(),
        "fixed_toolsandbox_timestamp": args.fixed_now,
        "expected_online_runs": args.expected_online_runs,
        "expected_frozen_runs": args.expected_online_runs,
        "expected_tasks_per_run": scenario_count,
        "sample_validation": sample_validation,
        "maximum_parallel_runs": args.max_parallel,
        "parallelism_unit": "paired_protocol_job",
        "model_arms_per_paired_protocol_job": MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB,
        "maximum_concurrent_model_arms": (
            args.max_parallel * MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB
        ),
        "execution_waves": _expected_execution_waves(args.max_parallel),
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
        "execution_events": [
            {
                "at": _now(),
                "event": "campaign_prepared",
                "detail": (
                    f"{args.expected_online_runs} new online runs and "
                    f"{args.expected_online_runs} frozen runs queued; all controls "
                    "must execute live and uncached."
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
    if manifest.get("expected_frozen_runs") != EXPECTED_REPLICATIONS:
        errors.append("expected_frozen_runs must be exactly 10")
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
    for expected_replication, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            errors.append("campaign contains a non-object run pair")
            continue
        online = pair.get("online")
        frozen = pair.get("frozen")
        if not isinstance(online, dict) or not isinstance(frozen, dict):
            errors.append(f"replication {pair.get('replication')} lacks both arms")
            continue
        if online.get("source") != "campaign_online_build_fresh_control":
            errors.append(
                f"replication {pair.get('replication')} online source is invalid"
            )
        if frozen.get("source") != "paired_frozen_registry_reuse":
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
        expected_arm_paths = (
            (
                "online",
                online,
                expected_online_search_root,
                expected_online_registry,
            ),
            (
                "frozen",
                frozen,
                expected_frozen_search_root,
                expected_frozen_registry,
            ),
        )
        for (
            arm_name,
            entry,
            expected_search_root,
            expected_registry,
        ) in expected_arm_paths:
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
                    *REGISTRY_LINEAGE_ENTRY_FIELDS,
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
        if frozen.get("source_registry_dir") != expected_online_registry:
            errors.append(
                f"replication {expected_replication} frozen source_registry_dir "
                "does not match its online registry"
            )

    maximum_parallel = manifest.get("maximum_parallel_runs")
    if (
        isinstance(maximum_parallel, bool)
        or not isinstance(maximum_parallel, int)
        or not 1 <= maximum_parallel <= MAX_CONCURRENCY
    ):
        errors.append(
            "maximum_parallel_runs must be between 1 and "
            f"{MAX_CONCURRENCY} paired protocol jobs"
        )
    elif not _exact_value(
        manifest.get("execution_waves"),
        _expected_execution_waves(maximum_parallel),
    ):
        errors.append(
            "execution_waves must exactly match the declared campaign parallelism"
        )
    if manifest.get("parallelism_unit") != "paired_protocol_job":
        errors.append("campaign parallelism unit must be paired_protocol_job")
    if not _exact_value(
        manifest.get("model_arms_per_paired_protocol_job"),
        MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB,
    ):
        errors.append("campaign must launch exactly two model arms per paired job")
    expected_model_arms = (
        maximum_parallel * MODEL_ARMS_PER_PAIRED_PROTOCOL_JOB
        if isinstance(maximum_parallel, int) and not isinstance(maximum_parallel, bool)
        else None
    )
    if not _exact_value(
        manifest.get("maximum_concurrent_model_arms"), expected_model_arms
    ):
        errors.append("campaign maximum concurrent model-arm count is invalid")

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


def _registry_receipt_paths(
    repo_root: Path,
    manifest: dict[str, Any],
    *,
    replication: int,
    arm: str,
) -> dict[str, Path]:
    artifact_root_raw = (manifest.get("paths") or {}).get("artifact_root")
    if not isinstance(artifact_root_raw, str) or not artifact_root_raw:
        raise ValueError("Campaign does not declare its artifact root.")
    rep_label = f"rep{replication:02d}"
    if arm == "online":
        root = (
            _resolve_repo_path(repo_root, artifact_root_raw)
            / "online"
            / rep_label
            / "native_action_artifacts"
        )
        return {"after_run": root / "registry_identity_after_run.json"}
    if arm == "frozen":
        root = (
            _resolve_repo_path(repo_root, artifact_root_raw)
            / "frozen"
            / rep_label
            / "frozen_registry_artifacts"
        )
        return {
            "source_before_copy": root / "source_registry_identity_before_copy.json",
            "before_run": root / "frozen_registry_identity_before_run.json",
            "after_run": root / "frozen_registry_identity_after_run.json",
        }
    raise ValueError(f"Unsupported campaign arm: {arm}")


def _read_registry_identity(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Cannot read registry identity receipt {path}: {exc}"
        ) from exc
    try:
        return validate_registry_content_identity(payload)
    except ValueError as exc:
        raise ValueError(f"Invalid registry identity receipt {path}: {exc}") from exc


def _entry_registry_identity(
    repo_root: Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    registry_raw = entry.get("registry_dir")
    if not isinstance(registry_raw, str) or not registry_raw:
        raise ValueError("Campaign entry does not declare a registry_dir.")
    try:
        return registry_content_identity(
            _resolve_repo_path(repo_root, registry_raw),
            require_complete=True,
        )
    except ValueError as exc:
        raise ValueError(f"Campaign registry bytes are invalid: {exc}") from exc


def _owning_pair(
    manifest: dict[str, Any],
    entry: dict[str, Any],
    arm: str,
) -> dict[str, Any]:
    matches = [
        pair
        for pair in manifest.get("run_pairs") or []
        if isinstance(pair, dict)
        and isinstance(pair.get(arm), dict)
        and (pair[arm] is entry or pair[arm] == entry)
    ]
    if len(matches) != 1:
        raise ValueError(f"Cannot bind {arm} entry to exactly one campaign pair.")
    return cast(dict[str, Any], matches[0])


def _assert_existing_registry_lineage_fields(
    entry: dict[str, Any],
    expected: dict[str, Any],
    *,
    arm: str,
) -> None:
    for field, value in expected.items():
        if field in entry and entry[field] != value:
            raise ValueError(f"{arm} campaign registry lineage changed: {field}.")


def _bound_online_registry_identity(
    repo_root: Path,
    manifest: dict[str, Any],
    pair: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    entry = pair.get("online")
    if not isinstance(entry, dict):
        raise ValueError("Frozen campaign pair has no online entry.")
    try:
        stored = validate_registry_content_identity(
            entry.get("registry_content_identity_after_run")
        )
    except ValueError as exc:
        raise ValueError(
            "Frozen campaign source lacks a valid online post-run registry identity."
        ) from exc
    replication = int(pair.get("replication") or 0)
    receipt_path = _registry_receipt_paths(
        repo_root,
        manifest,
        replication=replication,
        arm="online",
    )["after_run"]
    expected_receipt = _relative(repo_root, receipt_path)
    if entry.get("registry_identity_after_run_path") != expected_receipt:
        raise ValueError("Online registry identity receipt path is not campaign-bound.")
    receipt = _read_registry_identity(receipt_path)
    current = _entry_registry_identity(repo_root, entry)
    if receipt != stored or current != stored:
        raise ValueError(
            "Online registry bytes no longer match their persisted post-run identity."
        )
    return stored, receipt_path


def _campaign_registry_lineage(
    repo_root: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    arm: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    pair = _owning_pair(manifest, entry, arm)
    replication = int(pair.get("replication") or 0)
    entry_registry_raw = entry.get("registry_dir")
    verified_registry_raw = verification.get("registry_dir")
    if (
        not isinstance(entry_registry_raw, str)
        or not entry_registry_raw
        or not isinstance(verified_registry_raw, str)
        or not verified_registry_raw
        or _resolve_repo_path(repo_root, verified_registry_raw)
        != _resolve_repo_path(repo_root, entry_registry_raw)
    ):
        raise ValueError(f"{arm} verifier bound a different registry path.")
    try:
        protocol_before = validate_registry_content_identity(
            verification.get("registry_content_identity_before_run")
        )
        protocol_after = validate_registry_content_identity(
            verification.get("registry_content_identity_after_run")
        )
    except ValueError as exc:
        raise ValueError(
            f"{arm} verifier returned invalid registry lineage: {exc}"
        ) from exc
    current = _entry_registry_identity(repo_root, entry)
    receipts = _registry_receipt_paths(
        repo_root,
        manifest,
        replication=replication,
        arm=arm,
    )
    if arm == "online":
        receipt_after = _read_registry_identity(receipts["after_run"])
        if current != protocol_after or receipt_after != protocol_after:
            raise ValueError(
                "Online post-run registry bytes, protocol identity, and launcher "
                "receipt do not match."
            )
        lineage = {
            "registry_content_identity_before_run": protocol_before,
            "registry_content_identity_after_run": protocol_after,
            "registry_identity_after_run_path": _relative(
                repo_root, receipts["after_run"]
            ),
        }
    elif arm == "frozen":
        online_identity, _ = _bound_online_registry_identity(
            repo_root,
            manifest,
            pair,
        )
        source_before_copy = _read_registry_identity(receipts["source_before_copy"])
        copy_before_run = _read_registry_identity(receipts["before_run"])
        copy_after_run = _read_registry_identity(receipts["after_run"])
        identities = (
            source_before_copy,
            copy_before_run,
            copy_after_run,
            protocol_before,
            protocol_after,
            current,
        )
        if any(identity != online_identity for identity in identities):
            raise ValueError(
                "Frozen registry lineage does not exactly match online post-run, "
                "source pre-copy, copy pre-run, and copy post-run bytes."
            )
        lineage = {
            "source_registry_identity_before_copy": source_before_copy,
            "registry_content_identity_before_run": copy_before_run,
            "registry_content_identity_after_run": copy_after_run,
            "source_registry_identity_before_copy_path": _relative(
                repo_root, receipts["source_before_copy"]
            ),
            "registry_identity_before_run_path": _relative(
                repo_root, receipts["before_run"]
            ),
            "registry_identity_after_run_path": _relative(
                repo_root, receipts["after_run"]
            ),
        }
    else:
        raise ValueError(f"Unsupported campaign arm: {arm}")
    _assert_existing_registry_lineage_fields(entry, lineage, arm=arm)
    return lineage


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
    result["campaign_registry_lineage"] = _campaign_registry_lineage(
        repo_root,
        manifest,
        entry,
        arm,
        result,
    )
    return cast(dict[str, Any], result)


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
    for pair in manifest.get("run_pairs") or []:
        for arm in ("online", "frozen"):
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
            entry.setdefault("completed_at", reconciled_at)
            entry["status_reconciled_at"] = reconciled_at
            entry.update(verified["campaign_registry_lineage"])


def _job_command(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    pair: dict[str, Any],
    arm: str,
    port: int,
    execution_approved: bool,
) -> tuple[list[str], dict[str, str], Path]:
    if execution_approved is not True:
        raise ValueError(
            "Canonical publication launcher command requires explicit campaign approval."
        )
    replicate = int(pair["replication"])
    rep_label = f"rep{replicate:02d}"
    paths = manifest["paths"]
    output_root = repo_root / paths["output_root"]
    artifact_root = repo_root / paths["artifact_root"]
    model_stamp = manifest["campaign_id"]
    env = os.environ.copy()
    env.update(
        {
            "SAGE_RUN_STAMP": f"{model_stamp}_{rep_label}_{arm}",
            # This campaign estimates control-versus-SAGE outcomes. The separate
            # one-off selector experiment must never leak in from the parent shell.
            "SAGE_AUTO_SELECTION_EXPERIMENT": "0",
            "SAGE_BATCH_NO_DASHBOARD_OPEN": "0",
            "SAGE_APPROVE_LIVE_RUN": "YES",
            "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP": str(
                manifest["fixed_toolsandbox_timestamp"]
            ),
            "SAGE_BENCHMARK_MANIFEST": str(repo_root / manifest["benchmark_manifest"]),
            "CONTROL_CACHE": "off",
            "TOOLSANDBOX_RAPID_CACHE_MODE": "read_only",
            "TOOLSANDBOX_RAPID_CACHE_PATH": str(
                repo_root / manifest["external_fixture"]["path"]
            ),
            **PUBLICATION_EXECUTION_ENV,
        }
    )
    for stale_name in (
        "CONTROL_CACHE_ROOT",
        "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
        "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
        "RESUME_RUN_ROOT",
        "RESUME_COMPLETED_LIMIT",
        "RESUME_REGISTRY_CHECKPOINT",
        "SAGE_AUTO_SELECTION_PILOT_EVIDENCE",
        "SAGE_EXPECTED_SOURCE_REGISTRY_IDENTITY",
        "SAGE_EXPECTED_SOURCE_REGISTRY_SHA256",
        *DIAGNOSTIC_FORCE_ENV_VARS,
    ):
        env.pop(stale_name, None)
    if arm == "online":
        env["SAGE_OUTPUT_ROOT"] = str(output_root / "online" / rep_label)
        env["SAGE_ARTIFACT_ROOT"] = str(artifact_root / "online" / rep_label)
        mode = "native-only"
    elif arm == "frozen":
        source_registry = repo_root / pair["frozen"]["source_registry_dir"]
        online_identity, online_receipt_path = _bound_online_registry_identity(
            repo_root,
            manifest,
            pair,
        )
        env["SAGE_OUTPUT_ROOT"] = str(output_root / "frozen" / rep_label)
        env["SAGE_ARTIFACT_ROOT"] = str(artifact_root / "frozen" / rep_label)
        env["RESUME_REGISTRY_CHECKPOINT"] = str(source_registry)
        env["SAGE_EXPECTED_SOURCE_REGISTRY_IDENTITY"] = str(online_receipt_path)
        env["SAGE_EXPECTED_SOURCE_REGISTRY_SHA256"] = str(
            online_identity["content_sha256"]
        )
        mode = "frozen-only"
    else:
        raise ValueError(f"Unsupported campaign arm: {arm}")
    command = [
        "bash",
        "scripts/run_native_action_4omini_ab.sh",
        "full",
        str(port),
        mode,
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
    execution_approved: bool,
) -> dict[str, Any]:
    command, env, log_path = _job_command(
        repo_root=repo_root,
        manifest=manifest,
        pair=pair,
        arm=arm,
        port=port,
        execution_approved=execution_approved,
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
        return_code = process.wait()
        verification_error: str | None = None
        registry_lineage: dict[str, Any] | None = None
        if return_code == 0:
            try:
                result = _verify_publication_entry(
                    repo_root,
                    manifest,
                    pair[arm],
                    arm,
                )
                handle.write(
                    "publication_campaign_verification=pass "
                    f"run_root={result['run_root']}\n"
                )
                registry_lineage = cast(
                    dict[str, Any], result["campaign_registry_lineage"]
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
        "registry_lineage": registry_lineage,
    }


def _replication_dashboard_port(*, base_port: int, replication: int) -> int:
    """Return the wave-local, resume-stable dashboard port for a replication."""

    if not 1 <= replication <= EXPECTED_REPLICATIONS:
        raise ValueError(f"Replication must be between 1 and {EXPECTED_REPLICATIONS}.")
    return base_port + replication - 1


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


def _run_wave(
    *,
    repo_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    jobs: list[tuple[int, str]],
    max_parallel: int,
    base_port: int,
    execution_approved: bool,
) -> None:
    if execution_approved is not True:
        raise ValueError("Campaign wave execution requires explicit approval.")
    if not jobs:
        return
    if max_parallel > MAX_CONCURRENCY:
        raise ValueError(
            "Campaign concurrency cannot exceed "
            f"{MAX_CONCURRENCY} paired protocol jobs "
            f"({MAX_CONCURRENT_MODEL_ARMS} child model arms)."
        )
    lock = threading.Lock()
    for replicate, arm in jobs:
        pair = _find_pair(manifest, replicate)
        pair[arm]["execution_status"] = "running"
        pair[arm]["started_at"] = _now()
    manifest["status"] = "running"
    manifest["updated_at"] = _now()
    _atomic_json(manifest_path, manifest)
    _refresh_dashboard(
        repo_root=repo_root,
        manifest_path=manifest_path,
        manifest=manifest,
        final=False,
    )

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
    try:
        futures: dict[Future[dict[str, Any]], tuple[int, str]] = {}
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            for replicate, arm in jobs:
                pair = _find_pair(manifest, replicate)
                future = executor.submit(
                    _execute_job,
                    repo_root=repo_root,
                    manifest=manifest,
                    pair=pair,
                    arm=arm,
                    execution_approved=execution_approved,
                    # Bind a replication to the same port on both an initial
                    # wave and a partial-wave resume. Position-based ports can
                    # collide with detached dashboard servers left by already
                    # completed jobs when only a subset is resumed.
                    port=_replication_dashboard_port(
                        base_port=base_port,
                        replication=replicate,
                    ),
                )
                futures[future] = (replicate, arm)

            for future in as_completed(futures):
                replicate, arm = futures[future]
                result = future.result()
                with lock:
                    pair = _find_pair(manifest, replicate)
                    entry = pair[arm]
                    entry["execution_status"] = (
                        "completed" if result["return_code"] == 0 else "failed"
                    )
                    entry["return_code"] = result["return_code"]
                    entry["completed_at"] = result["completed_at"]
                    entry["log_path"] = result["log_path"]
                    if result["registry_lineage"] is not None:
                        entry.update(result["registry_lineage"])
                    manifest["updated_at"] = _now()
                    manifest.setdefault("execution_events", []).append(
                        {
                            "at": _now(),
                            "event": f"{arm}_run_finished",
                            "replication": replicate,
                            "return_code": result["return_code"],
                        }
                    )
                    _atomic_json(manifest_path, manifest)
                    _refresh_dashboard(
                        repo_root=repo_root,
                        manifest_path=manifest_path,
                        manifest=manifest,
                        final=False,
                    )
                if result["return_code"] != 0:
                    raise RuntimeError(
                        f"{arm} replication {replicate} failed; "
                        f"see {result['log_path']}"
                    )
    finally:
        stop_refresh.set()
        refresh_thread.join(timeout=5)


def _wave_jobs(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    wave: int,
) -> list[tuple[int, str]]:
    pairs = manifest.get("run_pairs") or []
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
    waves = [1, 2] if args.wave == "all" else [int(args.wave)]
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
            # Detached dashboard servers persist after a wave. Reserve one port
            # per replication so wave 2 never reuses a wave-1 server/root.
            base_port=args.base_port + ((wave - 1) * EXPECTED_REPLICATIONS),
            execution_approved=args.approve_execution,
        )

    manifest = _load_manifest(manifest_path)
    prerequisite_errors = _campaign_prerequisite_errors(repo_root, manifest)
    if prerequisite_errors:
        raise SystemExit("\n".join(prerequisite_errors))
    _reconcile_completed_entries(repo_root, manifest)
    complete = all(
        _entry_is_valid(repo_root, manifest, pair["online"], "online")
        and _entry_is_valid(repo_root, manifest, pair["frozen"], "frozen")
        for pair in manifest.get("run_pairs") or []
    )
    manifest["status"] = "complete" if complete else "incomplete"
    manifest["updated_at"] = _now()
    manifest.setdefault("execution_events", []).append(
        {
            "at": _now(),
            "event": "campaign_execution_finished",
            "complete": complete,
        }
    )
    _atomic_json(manifest_path, manifest)
    _refresh_dashboard(
        repo_root=repo_root,
        manifest_path=manifest_path,
        manifest=manifest,
        final=complete,
    )
    if not complete:
        raise SystemExit("Campaign is incomplete; inspect the campaign manifest.")
    print(repo_root / manifest["paths"]["dashboard_dir"] / "chapter4_evidence.html")


def verify_campaign(args: argparse.Namespace) -> None:
    repo_root = args.repo_root.resolve()
    manifest_path = args.campaign_manifest.resolve()
    manifest = _load_manifest(manifest_path)
    errors = _campaign_prerequisite_errors(repo_root, manifest)
    status = manifest.get("status")
    for pair in manifest.get("run_pairs") or []:
        for arm in ("online", "frozen"):
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
                _verify_publication_entry(repo_root, manifest, entry, arm)
            except ValueError as exc:
                errors.append(f"replication {pair.get('replication')} {arm}: {exc}")
    if errors:
        raise SystemExit("\n".join(errors))
    _refresh_dashboard(
        repo_root=repo_root,
        manifest_path=manifest_path,
        manifest=manifest,
        final=False,
    )
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
    prepare.add_argument(
        "--max-parallel",
        type=int,
        default=MAX_CONCURRENCY,
        help=(
            "Maximum paired protocol jobs. Each job runs two model arms; the "
            f"default {MAX_CONCURRENCY} caps live model arms at "
            f"{MAX_CONCURRENT_MODEL_ARMS}."
        ),
    )
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
            "Acknowledge review of preserved artifacts before resuming an "
            "incomplete campaign."
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
        parser.error(
            "--max-parallel must be between 1 and "
            f"{MAX_CONCURRENCY} paired protocol jobs"
        )
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
        prepare_campaign(args)
    elif args.command == "run":
        run_campaign(args)
    else:
        verify_campaign(args)


if __name__ == "__main__":
    main()
