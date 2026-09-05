from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from scripts.verify_publication_inputs import (
    EXPECTED_ACTIVE_EXECUTION_POLICY,
    EXPECTED_ACTIVE_PRODUCTION_CORE,
    EXPECTED_AMENDMENT_POLICY_SUPERSESSION,
    EXPECTED_REPLACEMENT_POLICY,
    EXPECTED_SELECTOR_POLICY_DONOR_SCOPE,
    InputVerificationError,
    verify_active_production_scientific_core,
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
    prior_release_path = repo / "prior_publication_release.json"
    prior_thresholds_path = repo / "prior_active_thresholds.json"
    execution_policy_path = repo / "execution_policy.json"
    rescore_summary_path = repo / "historical_outcome_rescore_summary.json"
    rescorer_source_path = repo / "scripts" / "rescore_historical_outcomes.py"
    active_thresholds_path = repo / "active_thresholds.json"
    base_thresholds = _read_json(repo / "thresholds.json")
    _write_json(
        prior_thresholds_path,
        {
            **base_thresholds,
            "schema_version": 2,
            "performance_endpoint": "outcome_task_completion_similarity",
        },
    )
    base_declaration = {
        "path": base_manifest_path.relative_to(repo).as_posix(),
        "sha256": _sha256(base_manifest_path),
    }
    amendment_declaration = {
        "path": amendment_path.relative_to(repo).as_posix(),
        "sha256": _sha256(amendment_path),
    }
    _write_json(
        prior_release_path,
        {
            "schema_version": 1,
            "manifest_type": "publication_release_input_chain",
            "created_at": "2026-09-02",
            "purpose": "test prior release",
            "base_input_manifest": base_declaration,
            "checkpoint_policy_amendment": amendment_declaration,
            "active_validation_thresholds": {
                "path": prior_thresholds_path.relative_to(repo).as_posix(),
                "sha256": _sha256(prior_thresholds_path),
            },
        },
    )
    execution_policy = json.loads(json.dumps(EXPECTED_ACTIVE_EXECUTION_POLICY))
    execution_policy["performance_endpoint"]["benchmark_task_count"] = 2
    _write_json(
        execution_policy_path,
        {
            "schema_version": 2,
            "manifest_type": "publication_execution_policy",
            "created_at": "2026-09-04",
            "purpose": "test",
            "extends": {
                "path": amendment_path.relative_to(repo).as_posix(),
                "sha256": _sha256(amendment_path),
            },
            "amendment_policy_supersession": (EXPECTED_AMENDMENT_POLICY_SUPERSESSION),
            **execution_policy,
            "immutable_inputs_changed": False,
        },
    )
    evaluator = outcome_evaluator_manifest()
    rescorer_source_path.parent.mkdir(parents=True, exist_ok=True)
    rescorer_source_path.write_text(
        "# Synthetic read-only historical rescorer fixture.\n",
        encoding="utf-8",
    )
    _write_json(
        rescore_summary_path,
        {
            "schema_version": 2,
            "report_type": "historical_terminal_trajectory_outcome_rescore_summary",
            "created_at": "2026-09-03",
            "provenance_status": (
                "historical_terminal_trajectories_timezone_inferred_not_confirmatory"
            ),
            "provenance_caveat": "Terminal-trajectory rescore; not a replay.",
            "source_report": {
                "local_path": "artifacts/full_rescore.json",
                "available_in_public_release": False,
                "content_address_sha256": "a" * 64,
                "file_sha256": "b" * 64,
            },
            "benchmark": {
                "task_count": 2,
                "manifest_sha256": _sha256(repo / "benchmark.json"),
                "ordered_task_name_sha256": hashlib.sha256(
                    b"task_a\ntask_b\n"
                ).hexdigest(),
            },
            "outcome_evaluator": evaluator,
            "rescorer": {
                "input_mode": "read_only",
                "outcome_input_contract": [
                    "resolved_scenario",
                    "execution_context",
                ],
                "source": {
                    "path": rescorer_source_path.relative_to(repo).as_posix(),
                    "sha256": _sha256(rescorer_source_path),
                    "size": rescorer_source_path.stat().st_size,
                },
                "stored_result_summary_consumed": False,
                "stored_score_fields_consumed": False,
                "timezone_inference": {
                    "arm_identity_or_replication_used_for_selection": False,
                    "arm_independence": (
                        "baseline and every candidate replication are inferred "
                        "from their own raw trajectory traces"
                    ),
                    "candidate_timezones": ["America/New_York"],
                    "evidence_granularity": (
                        "trace occurrences, not deduplicated conversions"
                    ),
                    "failure_policy": (
                        "fail_closed_on_missing_unmatched_ambiguous_or_conflicting_"
                        "evidence"
                    ),
                    "scope": "all_complete_valid_traces_per_arm",
                    "selection_inputs": ["tool_name", "arguments", "result"],
                    "tool": "datetime_info_to_timestamp",
                },
            },
            "coverage": {
                "arm_count": 11,
                "task_count_per_arm": 2,
                "outcome_value_count_per_arm": 2,
                "null_outcome_count": 0,
                "all_arms_complete": True,
                "all_arms_match_benchmark_order": True,
                "observed_order_sha256": hashlib.sha256(
                    b"task_a\ntask_b\n"
                ).hexdigest(),
            },
            "baseline": {
                "task_count": 2,
                "outcome_mean": 0.45,
                "exact_outcome_successes": 0,
                "input_files_sha256": "f" * 64,
                "fixed_toolsandbox_timestamp": "100",
                "timezone": "America/New_York",
            },
            "candidate_summary": {
                "run_count": 10,
                "task_outcome_observation_count": 20,
                "mean_of_run_outcome_means": 0.745,
                "lower_envelope": {
                    "minimum_run_exact_outcome_success_replications": list(
                        range(1, 11)
                    ),
                    "minimum_run_exact_outcome_successes": 1,
                    "minimum_run_outcome_mean": 0.7,
                    "minimum_run_outcome_mean_replications": [1],
                },
                "total_exact_outcome_successes": 10,
            },
            "candidate_runs": [
                {
                    "replication": replication,
                    "task_count": 2,
                    "outcome_mean": 0.7 if replication == 1 else 0.75,
                    "exact_outcome_successes": 1,
                    "input_files_sha256": f"{replication:x}" * 64,
                    "fixed_toolsandbox_timestamp": "200",
                    "timezone": "America/New_York",
                }
                for replication in range(1, 11)
            ],
            "primary_input_files": [
                {
                    "path": "analysis/campaign.json",
                    "sha256": _sha256(repo / "analysis" / "campaign.json"),
                    "size": (repo / "analysis" / "campaign.json").stat().st_size,
                },
                {
                    "path": "benchmark.json",
                    "sha256": _sha256(repo / "benchmark.json"),
                    "size": (repo / "benchmark.json").stat().st_size,
                },
            ],
        },
    )
    _write_json(
        active_thresholds_path,
        {
            "schema_version": 2,
            "purpose": "test",
            "performance_endpoint": "outcome_task_completion_similarity",
            "supersedes": {
                "path": prior_thresholds_path.relative_to(repo).as_posix(),
                "sha256": _sha256(prior_thresholds_path),
            },
            "execution_policy": {
                "path": execution_policy_path.relative_to(repo).as_posix(),
                "sha256": _sha256(execution_policy_path),
            },
            "selector_policy_donor_scope": EXPECTED_SELECTOR_POLICY_DONOR_SCOPE,
            "outcome_evaluator": evaluator,
            "benchmark": {
                "task_count": 2,
                "outcome_scored_task_count": 2,
                "manifest_sha256": _sha256(repo / "benchmark.json"),
                "ordered_task_name_sha256": hashlib.sha256(
                    b"task_a\ntask_b\n"
                ).hexdigest(),
            },
            "historical_reference": {
                "status": (
                    "historical_terminal_trajectories_timezone_inferred_not_"
                    "confirmatory"
                ),
                "summary_path": rescore_summary_path.relative_to(repo).as_posix(),
                "summary_sha256": _sha256(rescore_summary_path),
                "campaign_manifest": "analysis/campaign.json",
                "campaign_manifest_sha256": _sha256(
                    repo / "analysis" / "campaign.json"
                ),
                "evidence_data": "analysis/evidence.json",
                "evidence_data_sha256": _sha256(repo / "analysis" / "evidence.json"),
                "online_run_count": 10,
                "candidate_outcome_mean": 0.745,
                "candidate_outcome_minimum": 0.7,
                "original_v140_outcome_mean": 0.45,
            },
            "required_integrity": {
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
                "validated_external_fixture_sha256": base_thresholds[
                    "required_integrity"
                ]["validated_external_fixture_sha256"],
            },
            "required_no_regression": {
                "candidate_outcome_minimum": 0.7,
                "minimum_relative_outcome_lift_percent_over_same_run_control": 10.0,
            },
            "report_only": {
                "compare_candidate_outcome_to_historical_mean": 0.745,
                "mechanism_counts_are_release_gates": False,
            },
        },
    )
    _write_json(
        wrapper_path,
        {
            "schema_version": 1,
            "manifest_type": "publication_release_input_chain",
            "created_at": "2026-09-04",
            "purpose": "test current release",
            "supersedes_release_manifest": {
                "path": prior_release_path.relative_to(repo).as_posix(),
                "sha256": _sha256(prior_release_path),
            },
            "base_input_manifest": base_declaration,
            "checkpoint_policy_amendment": amendment_declaration,
            "active_execution_policy": {
                "path": execution_policy_path.relative_to(repo).as_posix(),
                "sha256": _sha256(execution_policy_path),
            },
            "historical_outcome_rescore_summary": {
                "path": rescore_summary_path.relative_to(repo).as_posix(),
                "sha256": _sha256(rescore_summary_path),
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


def _extend_public_repo(repo: Path, prior_release_path: Path) -> Path:
    """Add one complete immutable release generation above another."""

    prior_release = _read_json(prior_release_path)
    prior_policy_path = repo / prior_release["active_execution_policy"]["path"]
    prior_summary_path = (
        repo / prior_release["historical_outcome_rescore_summary"]["path"]
    )
    prior_thresholds_path = repo / prior_release["active_validation_thresholds"]["path"]
    policy_path = repo / "execution_policy_next.json"
    summary_path = repo / "historical_outcome_rescore_summary_next.json"
    thresholds_path = repo / "active_thresholds_next.json"
    release_path = repo / "publication_release_next.json"
    _write_json(policy_path, _read_json(prior_policy_path))
    _write_json(summary_path, _read_json(prior_summary_path))
    thresholds = _read_json(prior_thresholds_path)
    thresholds["supersedes"] = {
        "path": prior_thresholds_path.relative_to(repo).as_posix(),
        "sha256": _sha256(prior_thresholds_path),
    }
    thresholds["execution_policy"] = {
        "path": policy_path.relative_to(repo).as_posix(),
        "sha256": _sha256(policy_path),
    }
    thresholds["historical_reference"]["summary_path"] = summary_path.relative_to(
        repo
    ).as_posix()
    thresholds["historical_reference"]["summary_sha256"] = _sha256(summary_path)
    _write_json(thresholds_path, thresholds)
    _write_json(
        release_path,
        {
            "schema_version": 1,
            "manifest_type": "publication_release_input_chain",
            "created_at": "2026-09-05",
            "purpose": "test chained release",
            "supersedes_release_manifest": {
                "path": prior_release_path.relative_to(repo).as_posix(),
                "sha256": _sha256(prior_release_path),
            },
            "base_input_manifest": prior_release["base_input_manifest"],
            "checkpoint_policy_amendment": prior_release["checkpoint_policy_amendment"],
            "active_execution_policy": {
                "path": policy_path.relative_to(repo).as_posix(),
                "sha256": _sha256(policy_path),
            },
            "historical_outcome_rescore_summary": {
                "path": summary_path.relative_to(repo).as_posix(),
                "sha256": _sha256(summary_path),
            },
            "active_validation_thresholds": {
                "path": thresholds_path.relative_to(repo).as_posix(),
                "sha256": _sha256(thresholds_path),
            },
        },
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "next publication release generation")
    return release_path


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
    paired_schedule = result["active_execution_policy"]["paired_arm_schedule"]
    assert (
        paired_schedule["pair_1_fresh_control_and_policy_sage"]["execution"]
        == "concurrent_isolated_child_processes"
    )
    second_pair = paired_schedule["pair_2_fresh_independent_control_and_auto_sage"]
    assert second_pair["execution"] == "concurrent_isolated_child_processes"
    assert second_pair["control_output_influences_inventory"] is False
    assert second_pair["control_output_influences_execution"] is False
    assert paired_schedule == EXPECTED_ACTIVE_EXECUTION_POLICY["paired_arm_schedule"]
    pilot_gate = result["active_execution_policy"]["actor_selection_experiment"][
        "pilot_mechanism_eligibility_gate"
    ]
    assert pilot_gate["minimum_generated_tool_called_scenarios"] == 1
    assert pilot_gate["maximum_generated_tool_execution_failure_scenarios"] == 0
    assert pilot_gate["mechanism_eligibility_not_outcome_performance"] is True
    donor_gate = result["active_execution_policy"]["actor_selection_experiment"][
        "policy_inventory_donor_gate"
    ]
    assert donor_gate == {
        "protocol_gate_policy": "actor_selection_donor_integrity_only",
        "integrity_gate_must_pass": True,
        "ordinary_outcome_performance_thresholds_applied": False,
        "ordinary_outcome_performance_result_and_reasons_recorded_diagnostically": (
            True
        ),
    }
    parallel_calls = result["active_execution_policy"]["parallel_tool_call_execution"]
    assert (
        parallel_calls
        == EXPECTED_ACTIVE_EXECUTION_POLICY["parallel_tool_call_execution"]
    )
    assert parallel_calls["auto_response_truncation"] == "none"
    assert parallel_calls["parallel_model_returned_tool_calls_preserved"] is True
    assert (
        result["active_execution_policy"]["task_compare_dashboard"][
            "external_browser_open_required"
        ]
        is True
    )
    task_compare_policy = result["active_execution_policy"]["task_compare_dashboard"]
    assert (
        task_compare_policy
        == EXPECTED_ACTIVE_EXECUTION_POLICY["task_compare_dashboard"]
    )
    assert result["historical_outcome_rescore_summary"]["outcome_evaluator"] == (
        outcome_evaluator_manifest()
    )
    assert result["superseded_validation_thresholds"]["path"] == (
        "prior_active_thresholds.json"
    )


def test_release_verifier_accepts_complete_chained_predecessor(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    prior_release_path = _wrap_public_repo(repo, base_manifest_path)
    release_path = _extend_public_repo(repo, prior_release_path)

    result = verify_inputs(repo, release_path)

    assert result["superseded_release_manifest"] == {
        "path": "publication_release.json",
        "sha256": _sha256(prior_release_path),
    }
    assert result["superseded_validation_thresholds"]["path"] == (
        "active_thresholds.json"
    )


def test_active_core_can_be_verified_without_release_generation() -> None:
    result = verify_active_production_scientific_core()

    assert result["physical_lines"] == 32540
    assert result["file_count"] == 12
    assert result["sha256"] == EXPECTED_ACTIVE_PRODUCTION_CORE["sha256"]


def test_make_verify_publication_uses_the_pinned_full_cohort_cli() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )
    target = makefile.split("verify-publication:", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]

    assert "--cohort full" in target
    assert "--expected-tasks" not in target


def test_tracked_execution_policy_matches_the_exact_verified_schema() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    policy = _read_json(
        repo_root / "docs/sage_protocol/publication_execution_policy_20260904.json"
    )

    observed = {field: policy[field] for field in EXPECTED_ACTIVE_EXECUTION_POLICY}
    assert observed == EXPECTED_ACTIVE_EXECUTION_POLICY


def test_tracked_final_release_verifies_measurement_archives_and_core() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = verify_inputs(
        repo_root,
        repo_root / "docs/sage_protocol/publication_release_manifest_20260905.json",
    )

    discrepancy = result["outcome_discrepancy_resolution_summary"]
    assert discrepancy["canonical_toolsandbox_scores_consumed"] is False
    assert discrepancy["current_candidate_outcome_mean"] == 0.6920219638242894
    assert discrepancy["historical_rep05_outcome_mean"] == 0.675952842377261
    assert discrepancy["archives"]["historical_rescore"]["size"] == 484876
    assert discrepancy["archives"]["current_pair_rescore"]["size"] == 18079
    assert discrepancy["archives"]["current_pair_rescore"]["raw_size"] == 823735
    assert discrepancy["archives"]["outcome_metric_crosswalk"]["size"] == 25374
    assert discrepancy["archives"]["outcome_metric_crosswalk"]["raw_size"] == 1923437
    core = result["production_scientific_core"]
    assert core["physical_lines"] == 32540
    assert core["file_count"] == 12


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
            "non-outcome performance gate",
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


def test_release_verifier_rejects_rehashed_execution_policy_drift(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    policy_path = repo / wrapper["active_execution_policy"]["path"]
    policy = _read_json(policy_path)
    policy["task_compare_dashboard"]["external_browser_open_required"] = False
    _write_json(policy_path, policy)
    wrapper["active_execution_policy"]["sha256"] = _sha256(policy_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="drifted"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_rehashed_memoization_supersession_drift(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    policy_path = repo / wrapper["active_execution_policy"]["path"]
    policy = _read_json(policy_path)
    policy["amendment_policy_supersession"]["active_value"] = "within_run_only"
    _write_json(policy_path, policy)
    wrapper["active_execution_policy"]["sha256"] = _sha256(policy_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="exactly supersede"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_type_coerced_execution_policy_value(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    policy_path = repo / wrapper["active_execution_policy"]["path"]
    policy = _read_json(policy_path)
    policy["task_compare_dashboard"]["external_browser_open_required"] = 1
    _write_json(policy_path, policy)
    wrapper["active_execution_policy"]["sha256"] = _sha256(policy_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="drifted"):
        verify_inputs(repo, wrapper_path)


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (
            (
                "paired_arm_schedule",
                "pair_1_fresh_control_and_policy_sage",
                "execution",
            ),
            "sequential",
        ),
        (
            (
                "paired_arm_schedule",
                "pair_2_fresh_independent_control_and_auto_sage",
                "execution",
            ),
            "sequential",
        ),
        (
            (
                "paired_arm_schedule",
                "pair_2_fresh_independent_control_and_auto_sage",
                "control_delivery",
            ),
            "task_synchronous_stream",
        ),
        (
            (
                "paired_arm_schedule",
                "pair_2_fresh_independent_control_and_auto_sage",
                "control_output_influences_inventory",
            ),
            True,
        ),
        (
            (
                "paired_arm_schedule",
                "pair_2_fresh_independent_control_and_auto_sage",
                "control_output_influences_execution",
            ),
            True,
        ),
        (
            (
                "actor_selection_experiment",
                "pair_1_control_and_policy_sage",
            ),
            "sequential",
        ),
        (
            (
                "actor_selection_experiment",
                "pair_2_independent_control_and_auto_sage",
            ),
            "sequential",
        ),
        (
            (
                "actor_selection_experiment",
                "auto_replay_timing",
            ),
            "before_policy_inventory_authority_completion",
        ),
        (
            (
                "actor_selection_experiment",
                "policy_and_auto_inventory_match_required_per_task",
            ),
            False,
        ),
        (
            (
                "actor_selection_experiment",
                "policy_inventory_donor_gate",
                "protocol_gate_policy",
            ),
            "ordinary_outcome_viability",
        ),
        (
            (
                "actor_selection_experiment",
                "policy_inventory_donor_gate",
                "integrity_gate_must_pass",
            ),
            False,
        ),
        (
            (
                "actor_selection_experiment",
                "policy_inventory_donor_gate",
                "ordinary_outcome_performance_thresholds_applied",
            ),
            True,
        ),
        (
            (
                "actor_selection_experiment",
                "pilot_mechanism_eligibility_gate",
                "minimum_generated_tool_called_scenarios",
            ),
            0,
        ),
        (
            (
                "actor_selection_experiment",
                "pilot_mechanism_eligibility_gate",
                "maximum_generated_tool_execution_failure_scenarios",
            ),
            1,
        ),
        (
            (
                "parallel_tool_call_execution",
                "auto_response_truncation",
            ),
            "first_call_only",
        ),
        (
            (
                "parallel_tool_call_execution",
                "semantic_permutation_deduplication_applies_to_all_arms",
            ),
            False,
        ),
        (
            (
                "parallel_tool_call_execution",
                "tool_call_ids_alone_create_distinct_execution_order",
            ),
            True,
        ),
        (
            (
                "task_compare_dashboard",
                "open_and_root_identity_receipt_required",
            ),
            False,
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_control_vs_policy_selection_sage",
                "artifact",
            ),
            "dashboard/index.html",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_control_vs_policy_selection_sage",
                "receipt",
            ),
            "missing.json",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_control_vs_policy_selection_sage",
                "timing",
            ),
            "after_pair_1",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_independent_control_vs_sage_auto_selection",
                "artifact",
            ),
            "dashboard/task_compare.html",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_independent_control_vs_sage_auto_selection",
                "receipt",
            ),
            "dashboard_open_receipt.json",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "fresh_independent_control_vs_sage_auto_selection",
                "timing",
            ),
            "after_pair_2",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "policy_selection_sage_vs_sage_auto_selection",
                "artifact",
            ),
            "dashboard/task_compare.html",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "policy_selection_sage_vs_sage_auto_selection",
                "receipt",
            ),
            "dashboard_open_receipt.json",
        ),
        (
            (
                "task_compare_dashboard",
                "views",
                "policy_selection_sage_vs_sage_auto_selection",
                "timing",
            ),
            "before_treatment_completion",
        ),
    ],
)
def test_release_verifier_rejects_rehashed_pair_or_dashboard_policy_drift(
    tmp_path: Path,
    field_path: tuple[str, ...],
    value: object,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    policy_path = repo / wrapper["active_execution_policy"]["path"]
    policy = _read_json(policy_path)
    target: dict[str, Any] = policy
    for component in field_path[:-1]:
        nested = target[component]
        assert isinstance(nested, dict)
        target = nested
    target[field_path[-1]] = value
    _write_json(policy_path, policy)
    wrapper["active_execution_policy"]["sha256"] = _sha256(policy_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="drifted"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_threshold_rescore_evaluator_mismatch(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds["outcome_evaluator"]["source_sha256"] = "e" * 64
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="different outcome evaluator"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_rehashed_selector_donor_threshold_scope(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds["selector_policy_donor_scope"]["required_no_regression_applies"] = True
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="policy-donor scope is not exact"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_mutually_matching_stale_evaluator_identity(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    summary_path = repo / wrapper["historical_outcome_rescore_summary"]["path"]
    summary = _read_json(summary_path)
    summary["outcome_evaluator"]["source_sha256"] = "e" * 64
    _write_json(summary_path, summary)
    wrapper["historical_outcome_rescore_summary"]["sha256"] = _sha256(summary_path)

    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds["outcome_evaluator"]["source_sha256"] = "e" * 64
    thresholds["historical_reference"]["summary_sha256"] = _sha256(summary_path)
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="shipped outcome evaluator"):
        verify_inputs(repo, wrapper_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mean_of_run_outcome_means", 0.8),
        ("total_exact_outcome_successes", 9),
    ],
)
def test_release_verifier_rejects_rehashed_historical_aggregate_drift(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    summary_path = repo / wrapper["historical_outcome_rescore_summary"]["path"]
    summary = _read_json(summary_path)
    summary["candidate_summary"][field] = value
    _write_json(summary_path, summary)
    wrapper["historical_outcome_rescore_summary"]["sha256"] = _sha256(summary_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="aggregate values"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_rehashed_historical_lower_envelope_drift(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    summary_path = repo / wrapper["historical_outcome_rescore_summary"]["path"]
    summary = _read_json(summary_path)
    summary["candidate_summary"]["lower_envelope"]["minimum_run_outcome_mean"] = 0.6
    _write_json(summary_path, summary)
    wrapper["historical_outcome_rescore_summary"]["sha256"] = _sha256(summary_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="aggregate values"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_score_metadata_outside_outcome_gate(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds["canonical_metric_policy"] = "report_only"
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="fields are not exact"):
        verify_inputs(repo, wrapper_path)


def test_release_verifier_rejects_non_linear_threshold_ancestry(
    tmp_path: Path,
) -> None:
    repo, base_manifest_path = _build_public_repo(tmp_path)
    wrapper_path = _wrap_public_repo(repo, base_manifest_path)
    wrapper = _read_json(wrapper_path)
    thresholds_path = repo / wrapper["active_validation_thresholds"]["path"]
    thresholds = _read_json(thresholds_path)
    thresholds["supersedes"] = {
        "path": "thresholds.json",
        "sha256": _sha256(repo / "thresholds.json"),
    }
    _write_json(thresholds_path, thresholds)
    wrapper["active_validation_thresholds"]["sha256"] = _sha256(thresholds_path)
    _write_json(wrapper_path, wrapper)

    with pytest.raises(InputVerificationError, match="superseded policy"):
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
