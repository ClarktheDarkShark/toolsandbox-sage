from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_publication_inputs import (
    EXPECTED_REPLACEMENT_POLICY,
    InputVerificationError,
    verify_inputs,
)


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _build_public_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "publication-test@example.invalid")
    _git(repo, "config", "user.name", "Publication Test")
    (repo / "checkpoint_seed.txt").write_text("checkpoint\n", encoding="utf-8")
    _git(repo, "add", "checkpoint_seed.txt")
    _git(repo, "commit", "-q", "-m", "checkpoint")
    checkpoint_commit = _git(repo, "rev-parse", "HEAD")
    checkpoint_tree = _git(repo, "rev-parse", "HEAD^{tree}")

    benchmark_path = repo / "benchmark.json"
    _write_json(
        benchmark_path,
        {"splits": {"full_benchmark": [{"name": "task_a"}, {"name": "task_b"}]}},
    )
    benchmark_names = ["task_a", "task_b"]
    benchmark_order_hash = hashlib.sha256(
        ("\n".join(benchmark_names) + "\n").encode("utf-8")
    ).hexdigest()

    request = {
        "host": "example.p.rapidapi.com",
        "params": {"query": "paper"},
        "url": "https://example.p.rapidapi.com/search",
    }
    request_key = hashlib.sha256(
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    fixture_path = repo / "fixture.json"
    _write_json(
        fixture_path,
        {
            "entries": {
                request_key: {
                    "request": request,
                    "response": {"answer": 42},
                }
            }
        },
    )

    campaign_path = repo / "analysis" / "campaign.json"
    evidence_path = repo / "analysis" / "evidence.json"
    _write_json(campaign_path, {"status": "archival", "completed_runs": 20})
    _write_json(evidence_path, {"status": "archival", "paired_observations": 10320})

    thresholds_path = repo / "thresholds.json"
    _write_json(
        thresholds_path,
        {
            "benchmark": {
                "task_count": 2,
                "manifest_sha256": _sha256(benchmark_path),
                "ordered_task_name_sha256": benchmark_order_hash,
            },
            "historical_reference": {
                "candidate_outcome_mean": 0.75,
                "candidate_outcome_minimum": 0.7,
                "campaign_manifest": "analysis/campaign.json",
                "campaign_manifest_sha256": _sha256(campaign_path),
                "evidence_data": "analysis/evidence.json",
                "evidence_data_sha256": _sha256(evidence_path),
            },
            "required_integrity": {
                "validated_external_fixture_sha256": _sha256(fixture_path)
            },
        },
    )

    checkpoint_path = repo / "checkpoint.json"
    _write_json(
        checkpoint_path,
        {"git_checkpoint": {"commit": checkpoint_commit, "tree": checkpoint_tree}},
    )
    lock_path = repo / "requirements-publication-lock.txt"
    lock_path.write_text("Alpha==1.2.3\nAlpha.Package==4.5.6\n", encoding="utf-8")
    lock_identity = hashlib.sha256(b"alpha-package==4.5.6\nalpha==1.2.3\n").hexdigest()
    manifest_path = repo / "publication_inputs.json"
    _write_json(
        manifest_path,
        {
            "schema_version": 1,
            "public_verification": {
                "requires_local_recovery_bundle": False,
            },
            "checkpoint": {
                "manifest_path": "checkpoint.json",
                "manifest_sha256": _sha256(checkpoint_path),
                "commit": checkpoint_commit,
                "tree": checkpoint_tree,
            },
            "benchmark": {
                "path": "benchmark.json",
                "task_count": 2,
                "sha256": _sha256(benchmark_path),
                "ordered_task_names_sha256": benchmark_order_hash,
            },
            "publication_runtime": {
                "python_version": "3.12.7",
                "python_implementation": "CPython",
                "platform_system": "Darwin",
                "platform_machine": "arm64",
                "isolated_virtual_environment_required": True,
                "lock_path": "requirements-publication-lock.txt",
                "lock_sha256": _sha256(lock_path),
                "external_distribution_count": 2,
                "external_distribution_sha256": lock_identity,
            },
            "rapidapi_fixture": {
                "usage": "read_only_benchmark_input",
                "entry_count": 1,
                "contains_api_credentials": False,
                "sanitized_path": "fixture.json",
                "sanitized_sha256": _sha256(fixture_path),
            },
            "analysis": {
                "public_campaign_manifest_path": "analysis/campaign.json",
                "campaign_manifest_sha256": _sha256(campaign_path),
                "public_evidence_data_path": "analysis/evidence.json",
                "evidence_data_sha256": _sha256(evidence_path),
            },
            "validation_thresholds": {
                "path": "thresholds.json",
                "sha256": _sha256(thresholds_path),
            },
        },
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "public inputs")
    return repo, manifest_path


def _wrap_public_repo(repo: Path, base_manifest_path: Path) -> Path:
    base_manifest = _read_json(base_manifest_path)
    checkpoint = base_manifest["checkpoint"]
    amendment_path = repo / "checkpoint_amendment.json"
    _write_json(
        amendment_path,
        {
            "schema_version": 2,
            "amends": {
                "path": checkpoint["manifest_path"],
                "sha256": checkpoint["manifest_sha256"],
                "scope": [
                    "publication_policy.strict_publication_provenance_exceptions",
                    "replacement_publication_execution_policy",
                    "replacement_publication_validation_policy",
                ],
            },
            "replacement_policy": EXPECTED_REPLACEMENT_POLICY,
            "immutable_inputs_changed": False,
        },
    )
    wrapper_path = repo / "publication_release.json"
    active_thresholds_path = repo / "active_thresholds.json"
    base_thresholds = _read_json(repo / "thresholds.json")
    _write_json(
        active_thresholds_path,
        {
            **base_thresholds,
            "schema_version": 2,
            "performance_endpoint": "outcome_task_completion_similarity",
            "canonical_metric_policy": "descriptive_only_never_a_release_gate",
            "supersedes": {
                "path": "thresholds.json",
                "sha256": _sha256(repo / "thresholds.json"),
            },
            "historical_reference": {
                **base_thresholds["historical_reference"],
            },
            "required_integrity": {
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
                "validated_external_fixture_sha256": base_thresholds[
                    "required_integrity"
                ]["validated_external_fixture_sha256"],
            },
            "required_no_regression": {
                "candidate_outcome_minimum": 0.7,
                "minimum_relative_outcome_lift_percent_over_same_run_control": 10.0,
                "minimum_accepted_tool_count": 1,
                "minimum_tool_reuse_event_count": 1,
                "minimum_generated_tool_called_scenario_count": 1,
            },
            "report_only": {
                "compare_candidate_outcome_to_historical_mean": 0.75,
            },
        },
    )
    _write_json(
        wrapper_path,
        {
            "schema_version": 1,
            "manifest_type": "publication_release_input_chain",
            "base_input_manifest": {
                "path": base_manifest_path.relative_to(repo).as_posix(),
                "sha256": _sha256(base_manifest_path),
            },
            "checkpoint_policy_amendment": {
                "path": amendment_path.relative_to(repo).as_posix(),
                "sha256": _sha256(amendment_path),
            },
            "active_validation_thresholds": {
                "path": active_thresholds_path.relative_to(repo).as_posix(),
                "sha256": _sha256(active_thresholds_path),
            },
        },
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "publication release chain")
    return wrapper_path


def test_compact_verifier_accepts_tracked_inputs_without_local_bundle(
    tmp_path: Path,
) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)

    result = verify_inputs(repo, manifest_path)

    assert result["status"] == "pass"
    assert result["requires_local_recovery_bundle"] is False
    assert result["benchmark"]["task_count"] == 2
    assert result["publication_runtime"]["external_distribution_count"] == 2
    assert result["rapidapi_fixture"]["credential_safety_scan"] == "pass"
    assert result["checkpoint"]["git_objects_resolvable"] is True


def test_release_verifier_hashes_base_inputs_and_policy_amendment(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)

    result = verify_inputs(repo, wrapper_path)

    assert result["publication_input_manifest"]["path"] == "publication_inputs.json"
    assert result["publication_release_manifest"]["path"] == "publication_release.json"
    assert result["checkpoint_policy_amendment"]["replacement_policy"] == (
        EXPECTED_REPLACEMENT_POLICY
    )
    assert result["validation_thresholds"]["performance_endpoint"] == (
        "outcome_task_completion_similarity"
    )
    assert result["superseded_validation_thresholds"]["path"] == "thresholds.json"


def test_release_verifier_rejects_rehashed_policy_drift(tmp_path: Path) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    amendment_path = repo / wrapper["checkpoint_policy_amendment"]["path"]
    amendment = _read_json(amendment_path)
    amendment["replacement_policy"]["execution_environment"][
        "SAGE_OPENAI_MAX_RETRIES"
    ] = "2"
    _write_json(amendment_path, amendment)
    wrapper["checkpoint_policy_amendment"]["sha256"] = _sha256(amendment_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="replacement policy is not exact"):
        verify_inputs(repo, wrapper_path)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        (
            "required_no_regression",
            "minimum_relative_outcome_lift_percent_over_same_run_control",
            0.0,
            "exact outcome-only policy",
        ),
        (
            "required_no_regression",
            "candidate_canonical_minimum",
            0.0,
            "exact outcome-only policy",
        ),
        (
            "required_integrity",
            "diagnostic_force_calls_allowed",
            True,
            "integrity policy is not exact",
        ),
    ],
)
def test_release_verifier_rejects_rehashed_active_threshold_drift(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
    message: str,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds[section][field] = value
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match=message):
        verify_inputs(repo, wrapper_path)


def test_compact_verifier_rejects_changed_tracked_bytes(tmp_path: Path) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)
    (repo / "analysis" / "campaign.json").write_text(
        '{"status": "changed"}\n',
        encoding="utf-8",
    )

    with pytest.raises(
        InputVerificationError, match="historical campaign_manifest hash"
    ):
        verify_inputs(repo, manifest_path)


def test_compact_verifier_rejects_rehashed_runtime_identity_mismatch(
    tmp_path: Path,
) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)
    lock_path = repo / "requirements-publication-lock.txt"
    lock_path.write_text("Alpha_Package==1.2.3\nGamma==7.8.9\n", encoding="utf-8")
    manifest = _read_json(manifest_path)
    manifest["publication_runtime"]["lock_sha256"] = _sha256(lock_path)
    _write_json(manifest_path, manifest)

    with pytest.raises(InputVerificationError, match="distribution identity mismatch"):
        verify_inputs(repo, manifest_path)


def test_compact_verifier_rejects_rehashed_duplicate_benchmark_tasks(
    tmp_path: Path,
) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)
    benchmark_path = repo / "benchmark.json"
    _write_json(
        benchmark_path,
        {"splits": {"full_benchmark": [{"name": "task_a"}, {"name": "task_a"}]}},
    )
    manifest = _read_json(manifest_path)
    manifest["benchmark"]["sha256"] = _sha256(benchmark_path)
    _write_json(manifest_path, manifest)

    with pytest.raises(InputVerificationError, match="task coverage changed"):
        verify_inputs(repo, manifest_path)


def test_compact_verifier_rejects_rehashed_fixture_credentials(
    tmp_path: Path,
) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)
    request = {
        "host": "example.p.rapidapi.com",
        "params": {"api_key": "must-not-publish"},
        "url": "https://example.p.rapidapi.com/search",
    }
    request_key = hashlib.sha256(
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    fixture_path = repo / "fixture.json"
    _write_json(
        fixture_path,
        {
            "entries": {
                request_key: {
                    "request": request,
                    "response": {"answer": 42},
                }
            }
        },
    )
    manifest = _read_json(manifest_path)
    manifest["rapidapi_fixture"]["sanitized_sha256"] = _sha256(fixture_path)
    _write_json(manifest_path, manifest)

    with pytest.raises(InputVerificationError, match="credential and cache-key safety"):
        verify_inputs(repo, manifest_path)


def test_compact_verifier_rejects_checkpoint_tree_mismatch(tmp_path: Path) -> None:
    repo, manifest_path = _build_public_repo(tmp_path)
    wrong_tree = "0" * 40
    checkpoint_path = repo / "checkpoint.json"
    checkpoint = _read_json(checkpoint_path)
    checkpoint["git_checkpoint"]["tree"] = wrong_tree
    _write_json(checkpoint_path, checkpoint)
    manifest = _read_json(manifest_path)
    manifest["checkpoint"]["tree"] = wrong_tree
    manifest["checkpoint"]["manifest_sha256"] = _sha256(checkpoint_path)
    _write_json(manifest_path, manifest)

    with pytest.raises(InputVerificationError, match="Checkpoint tree mismatch"):
        verify_inputs(repo, manifest_path)
