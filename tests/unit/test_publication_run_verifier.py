from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import scripts.run_sage_auto_selection_replay as auto_selection_replay
import scripts.run_sage_protocol as protocol_runner
import scripts.verify_publication_run as publication_verifier
from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from sage_ts.registry.content_identity import registry_content_identity
from scripts.research import actor_selection_comparison
from scripts.run_chapter4_evidence_campaign import _job_command
from scripts.verify_publication_run import verify_run

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_GIT_COMMIT = "1" * 40
TEST_GIT_TREE = "2" * 40
POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC = {
    "protocol_gate_policy": "actor_selection_donor_integrity_only",
    "protocol_gate_passed": True,
    "protocol_gate_reasons": [],
    "protocol_performance_thresholds_applied": False,
    "protocol_performance_diagnostic_passed": False,
    "protocol_performance_diagnostic_reasons": [
        "non_positive_outcome_delta",
        "confirmation_outcome_delta_below_0_08",
    ],
}


def _test_environment_identity(repo_root: Path) -> dict[str, object]:
    lock_path = repo_root / publication_verifier.PUBLICATION_ENVIRONMENT_LOCK
    count, distribution_sha256 = (
        publication_verifier._external_distribution_lock_identity(lock_path)
    )
    publication_prefix = repo_root / ".venv-publication"
    return {
        "schema_version": 1,
        "status": "pass",
        "python_executable": str(publication_prefix / "bin" / "python"),
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "python_prefix": str(publication_prefix),
        "python_base_prefix": "/Library/Frameworks/Python.framework/Versions/3.12",
        "isolated_environment": True,
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "environment_lock_path": str(lock_path),
        "environment_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "external_distribution_count": count,
        "external_distribution_sha256": distribution_sha256,
    }


@pytest.fixture(autouse=True)
def _exact_publication_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publication_verifier, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        publication_verifier,
        "_clean_source_identity",
        lambda repo_root: {
            "git_commit": TEST_GIT_COMMIT,
            "git_tree": TEST_GIT_TREE,
            "git_clean": True,
        },
    )
    monkeypatch.setattr(
        publication_verifier,
        "_active_publication_environment",
        lambda lock_path, repo_root: _test_environment_identity(repo_root),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_llm_usage_artifacts(
    run_dir: Path,
    rows: list[dict[str, Any]],
    *,
    event_arm: str,
) -> None:
    totals = {
        field: sum(int(row[field]) for row in rows)
        for field in publication_verifier.LLM_USAGE_INTEGER_FIELDS
    }
    events: list[dict[str, Any]] = []
    for row in rows:
        call_count = int(row["llm_call_count"])
        for call_index in range(call_count):
            first_call = call_index == 0
            prompt_tokens = int(row["llm_prompt_tokens"]) if first_call else 0
            cached_prompt_tokens = (
                int(row["llm_provider_cached_prompt_tokens"]) if first_call else 0
            )
            completion_tokens = int(row["llm_completion_tokens"]) if first_call else 0
            events.append(
                {
                    "scenario": row["name"],
                    "arm": event_arm,
                    "source": "toolsandbox_agent",
                    "model": publication_verifier.PUBLICATION_MODEL,
                    "response_cache_status": "live",
                    "prompt_tokens": prompt_tokens,
                    "provider_cached_prompt_tokens": cached_prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "usage_available": True,
                    "raw_usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "prompt_tokens_details": {
                            "cached_tokens": cached_prompt_tokens
                        },
                    },
                }
            )
    _write_json(
        run_dir / "llm_usage_summary.json",
        {
            "schema_version": 2,
            "token_source": "openai_chat_completion_usage",
            "llm_usage_recorded": bool(events),
            "scenario_count_with_usage": sum(
                1 for row in rows if row["llm_call_count"] > 0
            ),
            "llm_usage_by_source": {
                "toolsandbox_agent": {
                    field: totals[field]
                    for field in publication_verifier.LLM_USAGE_SOURCE_INTEGER_FIELDS
                }
            },
            **totals,
        },
    )
    (run_dir / "llm_usage_events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def _fresh_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "search" / "online_build_full_1"
    control_dir = run_root / "control" / "run"
    candidate_dir = run_root / "candidate" / "run"
    lock_path = tmp_path / publication_verifier.PUBLICATION_ENVIRONMENT_LOCK
    shutil.copy2(
        PROJECT_ROOT / publication_verifier.PUBLICATION_ENVIRONMENT_LOCK,
        lock_path,
    )
    environment = _test_environment_identity(tmp_path)
    outcome_evaluator = outcome_evaluator_manifest()
    fixture_path = tmp_path / "rapid_api_cache.json"
    fixture_path.write_text('{"fixture": true}\n', encoding="utf-8")
    fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text('{"benchmark": true}\n', encoding="utf-8")
    benchmark_sha256 = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    registry_dir = tmp_path / "registry"
    _write_json(
        registry_dir / "registry_manifest.json",
        {"tools": {"helper": {"tool": {"code": "return 1"}}}},
    )
    _write_json(
        registry_dir / "tool_lifecycle.json",
        {"tool_lifecycle": {"helper": {"decision": "retain"}}},
    )
    helper_artifact = registry_dir / "helper_artifacts" / "helper.txt"
    helper_artifact.parent.mkdir()
    helper_artifact.write_text("exact helper artifact bytes\n", encoding="utf-8")
    registry_before = registry_content_identity(
        tmp_path / "empty_registry_before_run",
        require_complete=False,
    )
    registry_after = registry_content_identity(
        registry_dir,
        require_complete=True,
    )
    control_rows: list[dict[str, Any]] = [
        {
            "name": "task_a",
            "exception_type": None,
            "traceback": None,
            "transient_retry_count": 0,
            "transient_retry_archives": [],
            "transient_retry_failures": [],
            "similarity": 0.25,
            "outcome_similarity": 0.5,
            "llm_usage_recorded": True,
            "llm_cached_call_count": 0,
            "llm_call_count": 2,
            "llm_live_call_count": 2,
            "llm_prompt_tokens": 100,
            "llm_provider_cached_prompt_tokens": 64,
            "llm_provider_cached_prompt_call_count": 1,
            "llm_provider_cached_prompt_tokens_available_count": 2,
            "llm_completion_tokens": 20,
            "llm_total_tokens": 120,
            "llm_usage_available_count": 2,
        },
        {
            "name": "task_b",
            "exception_type": None,
            "traceback": None,
            "transient_retry_count": 0,
            "transient_retry_archives": [],
            "transient_retry_failures": [],
            "similarity": 1.0,
            "outcome_similarity": 0.0,
            "llm_usage_recorded": True,
            "llm_cached_call_count": 0,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_prompt_tokens": 50,
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 60,
            "llm_usage_available_count": 1,
        },
    ]
    candidate_rows: list[dict[str, Any]] = [
        {
            "name": "task_a",
            "exception_type": None,
            "traceback": None,
            "transient_retry_count": 0,
            "transient_retry_archives": [],
            "transient_retry_failures": [],
            "similarity": 0.75,
            "outcome_similarity": 1.0,
            "llm_usage_recorded": True,
            "llm_cached_call_count": 0,
            "llm_call_count": 3,
            "llm_live_call_count": 3,
            "llm_prompt_tokens": 200,
            "llm_provider_cached_prompt_tokens": 128,
            "llm_provider_cached_prompt_call_count": 1,
            "llm_provider_cached_prompt_tokens_available_count": 3,
            "llm_completion_tokens": 30,
            "llm_total_tokens": 230,
            "llm_usage_available_count": 3,
        },
        {
            "name": "task_b",
            "exception_type": None,
            "traceback": None,
            "transient_retry_count": 0,
            "transient_retry_archives": [],
            "transient_retry_failures": [],
            "similarity": 1.0,
            "outcome_similarity": 0.25,
            "llm_usage_recorded": True,
            "llm_cached_call_count": 0,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_prompt_tokens": 60,
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 70,
            "llm_usage_available_count": 1,
        },
    ]
    for row in (*control_rows, *candidate_rows):
        row.update(
            {
                "outcome_evaluator_version": outcome_evaluator["version"],
                "outcome_evaluator_contract_sha256": outcome_evaluator[
                    "contract_sha256"
                ],
                "outcome_evaluator_source_sha256": outcome_evaluator["source_sha256"],
            }
        )
    for arm_root in (control_dir.parent, candidate_dir.parent):
        _write_json(
            arm_root / "sage_ts_run_manifest.json",
            {
                "outcome_evaluator": outcome_evaluator,
                "timezone": publication_verifier.PUBLICATION_TIMEZONE,
            },
        )
    _write_json(
        control_dir / "result_summary.json",
        {"per_scenario_results": control_rows},
    )
    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": candidate_rows},
    )
    _write_llm_usage_artifacts(
        control_dir,
        control_rows,
        event_arm="online_build_full_control",
    )
    _write_llm_usage_artifacts(
        candidate_dir,
        candidate_rows,
        event_arm="online_build_full_candidate",
    )
    feedback = [
        {
            "event": "self_evolution_task_assessed",
            "scenario": row["name"],
            "control_source": "same_run_fresh",
            "control_score": row["similarity"],
            "control_outcome": row["outcome_similarity"],
        }
        for row in control_rows
    ]
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )
    task_compare_path = run_root / "dashboard" / "task_compare.html"
    task_compare_path.parent.mkdir(parents=True)
    task_compare_path.write_text("dashboard", encoding="utf-8")
    _write_json(
        task_compare_path.with_name("task_compare_data.json"),
        {
            "arm_labels": {
                "control": "Fresh non-learning control",
                "candidate": "SAGE policy selection",
            },
            "summary": {"scenario_count": 2},
        },
    )
    task_compare_url = "http://127.0.0.1:63105/dashboard/task_compare.html"
    dashboard_receipt_path = run_root / "dashboard_open_receipt.json"
    _write_json(
        dashboard_receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "fresh_control_vs_sage_policy_selection",
            "path": str(task_compare_path.resolve()),
            "url": task_compare_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
            "dashboard_server_root": str(run_root.resolve()),
            "opened_at": "2026-09-03T12:00:00+00:00",
            "opened_monotonic_ns": 500_000_000,
            "opened_before_model_processes": True,
        },
    )
    parallel_arms = {
        "control": {
            "status": "complete",
            "process_pid": 101,
            "started_at": "2026-09-03T12:00:01+00:00",
            "completed_at": "2026-09-03T12:00:03+00:00",
            "started_monotonic_ns": 1_000_000_000,
            "completed_monotonic_ns": 3_000_000_000,
        },
        "candidate": {
            "status": "complete",
            "process_pid": 102,
            "started_at": "2026-09-03T12:00:02+00:00",
            "completed_at": "2026-09-03T12:00:04+00:00",
            "started_monotonic_ns": 2_000_000_000,
            "completed_monotonic_ns": 4_000_000_000,
        },
    }
    for arm, arm_status in parallel_arms.items():
        _write_json(
            run_root / f"{arm}_arm_status.json",
            {"arm": arm, **arm_status},
        )
    parallel_execution = {
        "unit": "isolated_child_process",
        "arms": parallel_arms,
        "positive_overlap_asserted": True,
        "overlap_monotonic_ns": 1_000_000_000,
        "overlap_seconds": 1.0,
    }
    _write_json(
        run_root / "protocol_manifest.json",
        {
            "agent": publication_verifier.PUBLICATION_MODEL,
            "user": publication_verifier.PUBLICATION_MODEL,
            "generation_model": publication_verifier.PUBLICATION_MODEL,
            "mode": "online_build_full",
            "generation_enabled": True,
            "sage_policy": "self-evolving-praxis",
            "scenario_count": 2,
            "benchmark_manifest_path": str(benchmark_path),
            "benchmark_manifest_sha256": benchmark_sha256,
            "scenario_order_sha256": hashlib.sha256(b"task_a\ntask_b\n").hexdigest(),
            "control_dir": str(control_dir),
            "candidate_dir": str(candidate_dir),
            "registry_dir": str(registry_dir),
            "registry_content_identity_before_run": registry_before,
            "registry_content_identity_after_run": registry_after,
            "frozen_registry_content_immutable": True,
            "registry_manifest_digest_after_run": registry_after[
                "registry_manifest_sha256"
            ],
            "candidate_actor_selection_mode": "policy",
            "fresh_control_required": True,
            "publication_performance_endpoint": "outcome_task_completion_similarity",
            "timezone": publication_verifier.PUBLICATION_TIMEZONE,
            "outcome_evaluator": outcome_evaluator,
            "control_cache_mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": 2,
            "reflection_control_source": "same_run_fresh",
            "openai_response_cache_enabled": False,
            "openai_response_cache_mode": "off",
            "openai_response_cache_scope": (
                "persistent_repository_whole_response_replay"
            ),
            "prompt_cache_enabled": False,
            "prompt_cache_scope": "persistent_generation_output_replay",
            "generator_contract_and_repair_analysis_memoization": (
                "disabled_every_analysis_request_live"
            ),
            "openai_provider_prompt_prefix_cache_policy": "automatic_implicit",
            "openai_provider_prompt_prefix_cache_reuses_responses": False,
            "sage_task_cache_enabled": False,
            "cross_run_failure_memory_enabled": False,
            "cross_run_failure_memory_path": None,
            "diagnostic_force_allowed": False,
            "active_diagnostic_force_env": [],
            "parallel_arms": True,
            "parallel_arm_execution": parallel_execution,
            "reflection_control_delivery": "task_synchronous_stream",
            "dashboard_open_required": True,
            "dashboard_open_receipt_path": str(dashboard_receipt_path),
            "dashboard_task_compare_url": task_compare_url,
            "run_affecting_sage_env": dict(
                publication_verifier.PUBLICATION_EXECUTION_ENV
            ),
            "resume_run_root": None,
            "resume_completed_limit": None,
            "control_resume_dir": None,
            "candidate_resume_dir": None,
            "toolsandbox_clock_policy": "frozen",
            "toolsandbox_fixed_now_timestamp": str(
                publication_verifier.PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
            ),
            "publication_provenance": {
                "schema_version": 2,
                "git_commit": TEST_GIT_COMMIT,
                "git_tree": TEST_GIT_TREE,
                "git_clean": True,
                "fixed_toolsandbox_timestamp": (
                    publication_verifier.PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
                ),
                "python_executable": environment["python_executable"],
                "python_version": environment["python_version"],
                "python_implementation": environment["python_implementation"],
                "python_prefix": environment["python_prefix"],
                "python_base_prefix": environment["python_base_prefix"],
                "isolated_environment": environment["isolated_environment"],
                "platform_system": environment["platform_system"],
                "platform_machine": environment["platform_machine"],
                "environment_lock_path": (
                    publication_verifier.PUBLICATION_ENVIRONMENT_LOCK
                ),
                "environment_lock_sha256": environment["environment_lock_sha256"],
                "external_distribution_count": environment[
                    "external_distribution_count"
                ],
                "external_distribution_sha256": environment[
                    "external_distribution_sha256"
                ],
                "execution_environment": dict(
                    publication_verifier.PUBLICATION_EXECUTION_ENV
                ),
            },
            "external_fixture": {
                "policy": "validated_read_only_fixture",
                "path": str(fixture_path),
                "sha256": fixture_sha256,
                "mode": "read_only",
            },
        },
    )
    _write_json(
        run_root / "control_cache_report.json",
        {
            "mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": 2,
            "cache_accessed": False,
            "fresh_control_enforced": True,
        },
    )
    _write_json(
        run_root / "paired_comparison.json",
        {"deltas": [], "outcome_evaluator": outcome_evaluator},
    )
    return run_root


def _fixture_sha256(run_root: Path) -> str:
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    return str(protocol["external_fixture"]["sha256"])


def _verification_pins(run_root: Path) -> dict[str, str]:
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    return {
        "expected_fixture_sha256": str(protocol["external_fixture"]["sha256"]),
        "expected_benchmark_sha256": str(protocol["benchmark_manifest_sha256"]),
        "expected_scenario_order_sha256": str(protocol["scenario_order_sha256"]),
    }


def test_publication_cohort_pins_are_internal_and_exact() -> None:
    assert publication_verifier.publication_cohort_pins("full") == (
        1032,
        publication_verifier.PINNED_BENCHMARK_SHA256,
        publication_verifier.PINNED_SCENARIO_ORDER_SHA256,
    )
    assert publication_verifier.publication_cohort_pins("pilot") == (
        30,
        publication_verifier.PINNED_PILOT_BENCHMARK_SHA256,
        publication_verifier.PINNED_PILOT_SCENARIO_ORDER_SHA256,
    )
    with pytest.raises(ValueError, match="Unknown publication cohort"):
        publication_verifier.publication_cohort_pins("custom")


def test_pinned_run_resolves_pins_without_caller_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_verify_run(search_root: Path, **kwargs: object) -> dict[str, object]:
        observed["search_root"] = search_root
        observed.update(kwargs)
        return {"status": "pass"}

    monkeypatch.setattr(publication_verifier, "verify_run", fake_verify_run)

    result = publication_verifier.verify_pinned_run(
        tmp_path,
        cohort="pilot",
        expect_reflection="same-run-fresh",
    )

    assert observed == {
        "search_root": tmp_path,
        "expected_tasks": 30,
        "expect_reflection": "same-run-fresh",
        "expected_benchmark_sha256": (
            publication_verifier.PINNED_PILOT_BENCHMARK_SHA256
        ),
        "expected_scenario_order_sha256": (
            publication_verifier.PINNED_PILOT_SCENARIO_ORDER_SHA256
        ),
    }
    assert result == {"status": "pass", "publication_cohort": "pilot"}
    with pytest.raises(ValueError, match="expect_reflection"):
        publication_verifier.verify_pinned_run(
            tmp_path,
            cohort="pilot",
            expect_reflection="unknown",
        )


def test_auto_replay_preflight_requires_verified_policy_donor_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "policy_donor"
    run_root.mkdir()
    _write_json(
        run_root / "protocol_manifest.json",
        POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
    )
    _write_json(
        run_root / "paired_comparison.json",
        POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
    )
    monkeypatch.setattr(
        publication_verifier,
        "verify_pinned_run",
        lambda *args, **kwargs: {"run_root": str(run_root), "status": "pass"},
    )

    result = auto_selection_replay._verify_policy_donor(run_root, stage="pilot")

    assert result["policy_donor_gate"] == (POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC)

    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    protocol["protocol_gate_policy"] = "ordinary_outcome_viability"
    _write_json(run_root / "protocol_manifest.json", protocol)
    with pytest.raises(
        actor_selection_comparison.ActorSelectionVerificationError,
        match="integrity-only gate policy",
    ):
        auto_selection_replay._verify_policy_donor(run_root, stage="pilot")


def test_full_replay_policy_donor_record_validation_is_fail_closed() -> None:
    assert auto_selection_replay._valid_policy_donor_gate_record(
        POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC
    )
    for field, value in (
        ("protocol_gate_policy", "ordinary_outcome_viability"),
        ("protocol_gate_passed", False),
        ("protocol_performance_thresholds_applied", True),
        ("protocol_performance_diagnostic_reasons", "not-a-list"),
    ):
        tampered = copy.deepcopy(POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC)
        tampered[field] = value
        assert not auto_selection_replay._valid_policy_donor_gate_record(tampered)


def test_selector_full_gate_revalidates_linked_pilot_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "online_build_full_pilot"
    policy_dir = run_root / "candidate" / "policy_run"
    auto_dir = run_root / "sage_auto_selection" / "auto_run"
    auto_control_dir = (
        run_root / "sage_auto_selection_parallel_pair" / "control" / "control_run"
    )
    policy_dir.mkdir(parents=True)
    auto_dir.mkdir(parents=True)
    auto_control_dir.mkdir(parents=True)
    benchmark_path = tmp_path / "pilot_manifest.json"
    benchmark_path.write_text('{"sealed": true}\n', encoding="utf-8")
    benchmark_sha256 = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    order_sha256 = "3" * 64
    outcome_evaluator = outcome_evaluator_manifest()
    monkeypatch.setitem(
        publication_verifier.PUBLICATION_COHORT_PINS,
        "pilot",
        (30, benchmark_sha256, order_sha256),
    )
    authority_path = tmp_path / "authority" / "inventory_authority.json"
    _write_json(authority_path, {"complete": True})
    authority_sha256 = hashlib.sha256(authority_path.read_bytes()).hexdigest()
    tasks_sha256 = "4" * 64
    protocol_path = run_root / "protocol_manifest.json"
    _write_json(
        protocol_path,
        {
            "candidate_actor_selection_mode": "policy",
            "inventory_authority_mode": "capture",
            "inventory_authority_manifest_sha256": authority_sha256,
            "inventory_authority_tasks_sha256": tasks_sha256,
            "scenario_count": 30,
            "benchmark_manifest_path": str(benchmark_path),
            "benchmark_manifest_sha256": benchmark_sha256,
            "scenario_order_sha256": order_sha256,
            "candidate_dir": str(policy_dir),
            "timezone": publication_verifier.PUBLICATION_TIMEZONE,
            "outcome_evaluator": outcome_evaluator,
            **POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
        },
    )
    _write_json(
        run_root / "paired_comparison.json",
        POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
    )
    for arm_dir in (policy_dir, auto_dir):
        _write_json(
            arm_dir.parent / "sage_ts_run_manifest.json",
            {"timezone": publication_verifier.PUBLICATION_TIMEZONE},
        )
    protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    comparison = {
        "schema_version": 1,
        "experiment": "sage_auto_selection",
        "scenario_count": 30,
        "mechanism_counts_are_performance_gates": False,
        "outcome_evidence_complete": True,
        "performance_gate_applied": False,
        "performance_gate_reason": "no_predeclared_selector_performance_threshold",
        "integrity_gate_passed": True,
        "integrity_gate_reasons": [],
        "experiment_passed": True,
        "stability_gate_passed": True,
        "stability_gate_reasons": [],
        "full_comparison_eligibility_gate_applied": True,
        "full_comparison_eligibility_gate_passed": True,
        "full_comparison_eligibility_gate_reasons": [],
        "recommend_full_comparison": True,
        "outcome_evaluator": outcome_evaluator,
        "outcomes": {
            "policy_exact_outcome_successes": 10,
            "auto_exact_outcome_successes": 20,
            "policy_mean_outcome_similarity": 10 / 30,
            "auto_mean_outcome_similarity": 20 / 30,
            "auto_minus_policy_mean_outcome_delta": 10 / 30,
        },
    }
    comparison_path = run_root / "actor_selection_outcome_comparison.json"
    _write_json(comparison_path, comparison)
    pair_manifest_path = (
        run_root / "sage_auto_selection_parallel_pair" / "parallel_pair_manifest.json"
    )
    _write_json(pair_manifest_path, {"sealed": True})
    pair_manifest_sha256 = hashlib.sha256(pair_manifest_path.read_bytes()).hexdigest()
    parallel_execution = {"positive_overlap_asserted": True}
    auto_control_outcomes = {
        "scenario_count": 30,
        "control_exact_outcome_successes": 10,
        "auto_exact_outcome_successes": 20,
    }
    auto_control_outcome_path = (
        run_root
        / "sage_auto_selection_parallel_pair"
        / "auto_control_outcome_comparison.json"
    )
    _write_json(auto_control_outcome_path, auto_control_outcomes)
    live_receipt_path = (
        run_root / "sage_auto_selection_parallel_pair" / "dashboard_open_receipt.json"
    )
    live_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(live_receipt_path, {"sealed": True})
    policy_auto_dashboard_path = (
        run_root / "actor_selection_dashboard" / "dashboard" / "task_compare.html"
    )
    policy_auto_dashboard_path.parent.mkdir(parents=True)
    policy_auto_dashboard_path.write_text("dashboard", encoding="utf-8")
    policy_auto_dashboard_data_path = policy_auto_dashboard_path.with_name(
        "task_compare_data.json"
    )
    policy_auto_pairs = [
        {
            "scenario": f"scenario_{index}",
            "control": {
                "scenario": f"scenario_{index}",
                "phase": "control",
                "status": "complete",
                "outcome_similarity": 1.0 if index < 10 else 0.0,
            },
            "candidate": {
                "scenario": f"scenario_{index}",
                "phase": "candidate",
                "status": "complete",
                "outcome_similarity": 1.0 if index < 20 else 0.0,
            },
        }
        for index in range(30)
    ]
    policy_auto_dashboard_data: dict[str, Any] = {
        "arm_labels": {
            "control": "SAGE policy selection",
            "candidate": "SAGE auto selection",
        },
        "scenario_count": 30,
        "pairs": policy_auto_pairs,
        "summary": {
            "balanced_completed": 30,
            "balanced_control_mean_outcome_similarity": 10 / 30,
            "balanced_candidate_mean_outcome_similarity": 20 / 30,
            "balanced_outcome_delta": 10 / 30,
        },
    }
    _write_json(policy_auto_dashboard_data_path, policy_auto_dashboard_data)
    policy_auto_dashboard_url = (
        "http://127.0.0.1:63105/actor_selection_dashboard/dashboard/task_compare.html"
    )
    policy_auto_receipt_path = (
        run_root / "actor_selection_dashboard" / "dashboard_open_receipt.json"
    )
    _write_json(
        policy_auto_receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "policy_vs_sage_auto_selection",
            "path": str(policy_auto_dashboard_path),
            "url": policy_auto_dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
            "dashboard_server_root": str(run_root.resolve()),
            "opened_phase": "post_run_causal_comparison",
        },
    )
    _write_json(
        run_root / "sage_auto_selection_arm_status.json",
        {
            "arm": "sage_auto_selection",
            "status": "complete",
            "run_dir": str(auto_dir),
        },
    )
    evidence_path = run_root / "actor_selection_experiment_manifest.json"
    _write_json(
        evidence_path,
        {
            "schema_version": 2,
            "experiment": "sage_auto_selection",
            "stage": "pilot",
            "status": "complete",
            "scenario_count": 30,
            "policy_generation_enabled": True,
            "auto_generation_enabled": False,
            "auto_evolution_source": "matched_policy_inventory_authority",
            "auto_parallel_arms": True,
            "auto_control_cache_mode": "off",
            "auto_control_source": "fresh",
            "auto_cached_control_tasks": 0,
            "auto_fresh_control_tasks": 30,
            "auto_control_cache_accessed": False,
            "auto_control_delivery": "not_connected",
            "auto_control_output_influences_inventory": False,
            "auto_control_output_influences_execution": False,
            "publication_performance_endpoint": ("outcome_task_completion_similarity"),
            "legacy_score_is_performance_gate": False,
            "mechanism_counts_are_performance_gates": False,
            "persistent_response_cache_reuse": False,
            "outcome_evidence_complete": True,
            "performance_gate_applied": False,
            "performance_gate_reason": (
                "no_predeclared_selector_performance_threshold"
            ),
            "integrity_gate_passed": True,
            "integrity_gate_reasons": [],
            "experiment_passed": True,
            "stability_gate_passed": True,
            "stability_gate_reasons": [],
            "full_comparison_eligibility_gate_applied": True,
            "full_comparison_eligibility_gate_passed": True,
            "full_comparison_eligibility_gate_reasons": [],
            "recommend_full_comparison": True,
            "policy_protocol_manifest_path": str(protocol_path),
            "policy_protocol_manifest_sha256": protocol_sha256,
            "policy_run_dir": str(policy_dir),
            "auto_run_dir": str(auto_dir),
            "auto_control_run_dir": str(auto_control_dir),
            "auto_parallel_pair_manifest_path": str(pair_manifest_path),
            "auto_parallel_pair_manifest_sha256": pair_manifest_sha256,
            "auto_parallel_arm_execution": parallel_execution,
            "auto_control_outcome_comparison_path": str(auto_control_outcome_path),
            "auto_control_outcomes": auto_control_outcomes,
            "inventory_authority_path": str(authority_path),
            "inventory_authority_sha256": authority_sha256,
            "inventory_authority_tasks_sha256": tasks_sha256,
            "benchmark_manifest_path": str(benchmark_path),
            "benchmark_manifest_sha256": benchmark_sha256,
            "scenario_order_sha256": order_sha256,
            "source_identity": {
                "git_commit": TEST_GIT_COMMIT,
                "git_tree": TEST_GIT_TREE,
            },
            "policy_donor_gate": POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
            "outcome_evaluator": outcome_evaluator,
            "outcome_comparison_path": str(comparison_path),
            "dashboard_task_compare_path": str(policy_auto_dashboard_path),
            "dashboard_task_compare_url": policy_auto_dashboard_url,
            "dashboard_open_receipt_path": str(policy_auto_receipt_path),
            "policy_auto_dashboard_open_receipt_path": str(policy_auto_receipt_path),
            "live_auto_control_dashboard_open_receipt_path": str(live_receipt_path),
        },
    )
    monkeypatch.setattr(
        publication_verifier,
        "verify_pinned_run",
        lambda *args, **kwargs: {
            "run_root": str(run_root),
            "status": "pass",
            "outcome_evaluator": outcome_evaluator,
        },
    )
    monkeypatch.setattr(
        actor_selection_comparison,
        "verify_matched_actor_selection_experiment",
        lambda **kwargs: comparison,
    )
    monkeypatch.setattr(
        publication_verifier,
        "verify_auto_selection_parallel_pair",
        lambda *args, **kwargs: {
            "status": "pass",
            "control_run_dir": str(auto_control_dir),
            "auto_run_dir": str(auto_dir),
            "parallel_arm_execution": parallel_execution,
            "outcomes": auto_control_outcomes,
            "outcome_comparison_path": str(auto_control_outcome_path),
            "dashboard_open_receipt_path": str(live_receipt_path),
        },
    )

    result = publication_verifier.verify_selector_pilot_evidence(evidence_path)

    assert result["status"] == "pass"
    assert result["scenario_count"] == 30
    assert result["outcome_evidence_complete"] is True
    assert result["performance_gate_applied"] is False
    assert result["integrity_gate_passed"] is True
    assert result["experiment_passed"] is True
    assert result["stability_gate_passed"] is True
    assert result["full_comparison_eligibility_gate_passed"] is True
    assert result["recommend_full_comparison"] is True
    assert result["policy_donor_gate"] == (POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC)
    assert result["outcome_evaluator"] == outcome_evaluator
    assert result["git_commit"] == TEST_GIT_COMMIT
    assert (
        result["evidence_sha256"]
        == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    )
    assert result["timezone"] == publication_verifier.PUBLICATION_TIMEZONE

    def reseal_protocol(payload: dict[str, Any]) -> None:
        _write_json(protocol_path, payload)
        sealed_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        sealed_evidence["policy_protocol_manifest_sha256"] = hashlib.sha256(
            protocol_path.read_bytes()
        ).hexdigest()
        _write_json(evidence_path, sealed_evidence)

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["protocol_gate_policy"] = "ordinary_outcome_viability"
    reseal_protocol(protocol)
    with pytest.raises(ValueError, match="integrity-only gate policy"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    protocol["protocol_gate_policy"] = "actor_selection_donor_integrity_only"
    protocol["protocol_performance_thresholds_applied"] = True
    reseal_protocol(protocol)
    with pytest.raises(ValueError, match="applied ordinary outcome-performance"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    protocol["protocol_performance_thresholds_applied"] = False
    protocol["protocol_gate_passed"] = False
    protocol["protocol_gate_reasons"] = ["runtime_exceptions_present"]
    reseal_protocol(protocol)
    with pytest.raises(ValueError, match="did not pass its integrity gate"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    protocol["protocol_gate_passed"] = True
    protocol["protocol_gate_reasons"] = []
    reseal_protocol(protocol)

    paired_comparison_path = run_root / "paired_comparison.json"
    paired_comparison = json.loads(paired_comparison_path.read_text(encoding="utf-8"))
    paired_comparison["protocol_performance_diagnostic_passed"] = True
    _write_json(paired_comparison_path, paired_comparison)
    with pytest.raises(ValueError, match="protocol and paired comparison gates"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    _write_json(
        paired_comparison_path,
        POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC,
    )

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["policy_donor_gate"]["protocol_gate_policy"] = "ordinary_outcome_viability"
    _write_json(evidence_path, evidence)
    with pytest.raises(ValueError, match="preserve the verified policy-donor gate"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    evidence["policy_donor_gate"] = POLICY_DONOR_GATE_WITH_NEGATIVE_DIAGNOSTIC
    _write_json(evidence_path, evidence)

    first_policy_row = dict(policy_auto_dashboard_data["pairs"][0]["control"])
    policy_auto_dashboard_data["pairs"][0]["control"] = None
    _write_json(policy_auto_dashboard_data_path, policy_auto_dashboard_data)
    with pytest.raises(ValueError, match="has no complete control arm"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    policy_auto_dashboard_data["pairs"][0]["control"] = first_policy_row
    policy_auto_dashboard_data["summary"]["balanced_completed"] = 0
    _write_json(policy_auto_dashboard_data_path, policy_auto_dashboard_data)
    with pytest.raises(ValueError, match="balanced outcome count is incomplete"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    policy_auto_dashboard_data["summary"]["balanced_completed"] = 30
    _write_json(policy_auto_dashboard_data_path, policy_auto_dashboard_data)

    policy_auto_receipt = json.loads(
        policy_auto_receipt_path.read_text(encoding="utf-8")
    )
    policy_auto_receipt["dashboard_server_root"] = str(run_root.parent.resolve())
    _write_json(policy_auto_receipt_path, policy_auto_receipt)
    with pytest.raises(ValueError, match="policy/auto Task Compare receipt is invalid"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    policy_auto_receipt["dashboard_server_root"] = str(run_root.resolve())
    _write_json(policy_auto_receipt_path, policy_auto_receipt)

    auto_manifest_path = auto_dir.parent / "sage_ts_run_manifest.json"
    auto_manifest = json.loads(auto_manifest_path.read_text(encoding="utf-8"))
    auto_manifest["timezone"] = "America/Los_Angeles"
    _write_json(auto_manifest_path, auto_manifest)
    with pytest.raises(ValueError, match="sage_auto_selection run manifest timezone"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)
    auto_manifest["timezone"] = publication_verifier.PUBLICATION_TIMEZONE
    _write_json(auto_manifest_path, auto_manifest)

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["outcome_evaluator"]["source_sha256"] = "0" * 64
    _write_json(evidence_path, evidence)
    with pytest.raises(ValueError, match="field 'outcome_evaluator'"):
        publication_verifier.verify_selector_pilot_evidence(evidence_path)


def test_verifier_proves_same_run_fresh_control_mapping(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        **_verification_pins(run_root),
    )

    assert result["status"] == "pass"
    assert result["cached_control_tasks"] == 0
    assert result["repository_whole_response_replay_hits"] == 0
    assert result["openai_provider_prompt_prefix_cache_policy"] == "automatic_implicit"
    assert result["openai_provider_cached_prompt_tokens"] == {
        "control": 64,
        "candidate": 128,
    }
    assert result["openai_provider_cached_prompt_call_count"] == {
        "control": 1,
        "candidate": 1,
    }
    assert result["openai_provider_cached_prompt_tokens_available_count"] == {
        "control": 3,
        "candidate": 4,
    }
    assert result["reflection_control_source"] == "same_run_fresh"
    assert result["git_commit"] == TEST_GIT_COMMIT
    assert result["git_tree"] == TEST_GIT_TREE
    assert result["python_version"] == "3.12.7"
    assert result["platform_system"] == "Darwin"
    assert result["platform_machine"] == "arm64"
    assert result["timezone"] == "America/New_York"
    assert result["external_distribution_count"] == 108
    assert len(result["external_distribution_sha256"]) == 64
    assert result["outcome_evaluator"] == outcome_evaluator_manifest()
    assert result["registry_content_identity_before_run"]["file_count"] == 0
    assert result["registry_content_identity_after_run"]["complete"] is True


@pytest.mark.parametrize(
    ("relative_path", "replacement"),
    [
        ("registry_manifest.json", '{"tools":{"different":{}}}\n'),
        ("tool_lifecycle.json", '{"tool_lifecycle":{"helper":{"decision":"park"}}}\n'),
        ("helper_artifacts/helper.txt", "substituted helper artifact bytes\n"),
    ],
)
def test_verifier_rejects_registry_byte_mutation_after_protocol_completion(
    tmp_path: Path,
    relative_path: str,
    replacement: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads((run_root / "protocol_manifest.json").read_text())
    registry_dir = Path(protocol["registry_dir"])
    (registry_dir / relative_path).write_text(replacement, encoding="utf-8")

    with pytest.raises(ValueError, match="Current publication registry bytes"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_registry_path_substitution_with_different_bytes(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    substitute = tmp_path / "substitute_registry"
    shutil.copytree(Path(protocol["registry_dir"]), substitute)
    (substitute / "registry_manifest.json").write_text(
        '{"tools":{"different":{"tool":{"code":"return 2"}}}}\n',
        encoding="utf-8",
    )
    protocol["registry_dir"] = str(substitute)
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="Current publication registry bytes"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_frozen_registry_pre_post_identity_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["mode"] = "full_benchmark"
    protocol["generation_enabled"] = False
    protocol["sage_policy"] = "none"
    protocol["registry_content_identity_before_run"] = registry_content_identity(
        tmp_path / "empty_frozen_registry",
        require_complete=False,
    )
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="Frozen publication registry bytes changed"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="not-applicable",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    "artifact",
    ["protocol", "comparison", "arm_manifest", "result_row"],
)
def test_verifier_rejects_outcome_evaluator_identity_drift(
    tmp_path: Path,
    artifact: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads((run_root / "protocol_manifest.json").read_text())
    if artifact == "protocol":
        protocol["outcome_evaluator"]["source_sha256"] = "0" * 64
        _write_json(run_root / "protocol_manifest.json", protocol)
        expected_message = "Protocol manifest has the wrong outcome evaluator"
    elif artifact == "comparison":
        path = run_root / "paired_comparison.json"
        comparison = json.loads(path.read_text())
        comparison["outcome_evaluator"]["contract_sha256"] = "0" * 64
        _write_json(path, comparison)
        expected_message = "Paired comparison has the wrong outcome evaluator"
    elif artifact == "arm_manifest":
        candidate_dir = Path(protocol["candidate_dir"])
        path = candidate_dir.parent / "sage_ts_run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["outcome_evaluator"]["version"] = "stale"
        _write_json(path, manifest)
        expected_message = "candidate run manifest has the wrong outcome evaluator"
    else:
        candidate_dir = Path(protocol["candidate_dir"])
        path = candidate_dir / "result_summary.json"
        summary = json.loads(path.read_text())
        summary["per_scenario_results"][0]["outcome_evaluator_contract_sha256"] = (
            "0" * 64
        )
        _write_json(path, summary)
        expected_message = "mismatched outcome_evaluator_contract_sha256"

    with pytest.raises(ValueError, match=expected_message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_accepts_exception_free_zero_retry_rows(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        **_verification_pins(run_root),
    )

    assert result["status"] == "pass"


@pytest.mark.parametrize(
    ("protocol_dir_field", "arm"),
    [
        ("control_dir", "control"),
        ("candidate_dir", "candidate"),
    ],
)
def test_verifier_rejects_runtime_exception_row_in_either_arm(
    tmp_path: Path,
    protocol_dir_field: str,
    arm: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol[protocol_dir_field]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["exception_type"] = "RuntimeError"
    _write_json(summary_path, summary)

    with pytest.raises(
        ValueError,
        match=rf"{arm} task 'task_a' contains runtime exception 'RuntimeError'",
    ):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_non_null_traceback_without_exception_type(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["traceback"] = "hidden failure"
    _write_json(summary_path, summary)

    with pytest.raises(
        ValueError,
        match="candidate task 'task_a' contains a runtime exception traceback",
    ):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_accepts_consistent_successful_retry_provenance(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    row = summary["per_scenario_results"][0]
    archive = (
        Path(protocol["candidate_dir"])
        / "trajectories"
        / "task_a__transient_retry_failed_attempt_1"
    )
    archive.mkdir(parents=True)
    archive_path = str(archive)
    row["transient_retry_count"] = 1
    row["transient_retry_archives"] = [archive_path]
    row["transient_retry_failures"] = [
        {
            "attempt": 1,
            "exception_type": "APIConnectionError",
            "exception_message": "connection reset",
            "traceback": "Traceback: openai.APIConnectionError: connection reset",
            "exception_chain_type_names": ["APIConnectionError"],
            "retry_reason": {
                "kind": "exception_chain_type",
                "identifier": "APIConnectionError",
            },
            "archive_path": archive_path,
        }
    ]
    _write_json(summary_path, summary)

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        **_verification_pins(run_root),
    )

    assert result["status"] == "pass"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("transient_retry_count", True, "invalid or missing transient_retry_count"),
        ("transient_retry_count", -1, "negative transient_retry_count"),
        (
            "transient_retry_archives",
            None,
            "invalid or missing transient_retry_archives",
        ),
        (
            "transient_retry_failures",
            None,
            "invalid or missing transient_retry_failures",
        ),
    ],
)
def test_verifier_rejects_malformed_retry_provenance(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0][field] = value
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("failure_count", "retry failure count does not match"),
        ("attempt_sequence", "retry attempts are not exactly 1..1"),
        ("archive_type", "invalid or missing archive_path"),
        ("archive_mismatch", "archives do not exactly match"),
        ("zero_retry_orphan_archive", "archives do not exactly match"),
        ("archive_outside_run", "not the exact expected trajectory directory"),
        ("archive_missing", "archive is not an existing directory"),
        ("empty_chain", "invalid exception_chain_type_names"),
        ("chain_first_mismatch", "does not start with exception_type"),
        ("reason_kind_not_string", "reason outside the producer allowlist"),
        ("chain_identifier_absent", "does not occur in its exception chain"),
        (
            "unknown_marker_identifier",
            "traceback-marker identifier outside the producer allowlist",
        ),
        ("classified_marker_absent", "does not contain its classified marker"),
        ("null_archive", "invalid or missing archive_path"),
    ],
)
def test_verifier_rejects_inconsistent_retry_provenance(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    row = summary["per_scenario_results"][0]
    archive = (
        Path(protocol["candidate_dir"])
        / "trajectories"
        / "task_a__transient_retry_failed_attempt_1"
    )
    archive.mkdir(parents=True)
    archive_path = str(archive)
    failure: dict[str, Any] = {
        "attempt": 1,
        "exception_type": "APIConnectionError",
        "exception_message": "connection reset",
        "traceback": "Traceback: openai.APIConnectionError: connection reset",
        "exception_chain_type_names": ["APIConnectionError"],
        "retry_reason": {
            "kind": "exception_chain_type",
            "identifier": "APIConnectionError",
        },
        "archive_path": archive_path,
    }
    row["transient_retry_count"] = 1
    row["transient_retry_archives"] = [archive_path]
    row["transient_retry_failures"] = [failure]
    if case == "failure_count":
        row["transient_retry_failures"] = []
    elif case == "attempt_sequence":
        failure["attempt"] = 2
    elif case == "archive_type":
        failure["archive_path"] = 1
    elif case == "archive_mismatch":
        row["transient_retry_archives"] = ["different/archive"]
    elif case == "zero_retry_orphan_archive":
        row["transient_retry_count"] = 0
        row["transient_retry_failures"] = []
    elif case == "archive_outside_run":
        forged_archive = tmp_path / "forged_retry_archive"
        forged_archive.mkdir()
        failure["archive_path"] = str(forged_archive)
        row["transient_retry_archives"] = [str(forged_archive)]
    elif case == "archive_missing":
        archive.rmdir()
    elif case == "empty_chain":
        failure["exception_chain_type_names"] = []
    elif case == "chain_first_mismatch":
        failure["exception_chain_type_names"] = [
            "WrapperError",
            "APIConnectionError",
        ]
    elif case == "reason_kind_not_string":
        failure["retry_reason"]["kind"] = []
    elif case == "chain_identifier_absent":
        failure["exception_type"] = "WrapperError"
        failure["exception_chain_type_names"] = ["WrapperError"]
    elif case == "unknown_marker_identifier":
        failure["exception_type"] = "WrapperError"
        failure["exception_chain_type_names"] = ["WrapperError"]
        failure["retry_reason"] = {
            "kind": "traceback_marker",
            "identifier": "unknown_marker",
        }
    elif case == "classified_marker_absent":
        failure["exception_type"] = "WrapperError"
        failure["exception_chain_type_names"] = ["WrapperError"]
        failure["retry_reason"] = {
            "kind": "traceback_marker",
            "identifier": "read_timeout",
        }
        failure["traceback"] = "Traceback: no transient marker"
    elif case == "null_archive":
        failure["archive_path"] = None
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    "field",
    ["exception_type", "exception_message", "traceback"],
)
def test_verifier_rejects_empty_retry_failure_evidence(
    tmp_path: Path,
    field: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    row = summary["per_scenario_results"][0]
    row["transient_retry_count"] = 1
    row["transient_retry_archives"] = []
    row["transient_retry_failures"] = [
        {
            "attempt": 1,
            "exception_type": "APIConnectionError",
            "exception_message": "connection reset",
            "traceback": "Traceback: openai.APIConnectionError: connection reset",
            "exception_chain_type_names": ["APIConnectionError"],
            "retry_reason": {
                "kind": "exception_chain_type",
                "identifier": "APIConnectionError",
            },
            "archive_path": None,
        }
    ]
    row["transient_retry_failures"][0][field] = "   "
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match=rf"invalid or missing {field}"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_hybrid_control_report(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    report_path = run_root / "control_cache_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cached_control_tasks"] = 1
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="cached_control_tasks"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_cross_run_failure_memory(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["cross_run_failure_memory_enabled"] = True
    protocol["cross_run_failure_memory_path"] = (
        "artifacts/summaries/failure_memory.json"
    )
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="cross_run_failure_memory_enabled"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered"),
    [
        ("diagnostic_force_allowed", True),
        ("active_diagnostic_force_env", ["SAGE_DIAGNOSTIC_FORCE_TOOL_NAME"]),
    ],
)
def test_verifier_rejects_diagnostic_force_policy(
    tmp_path: Path,
    field: str,
    tampered: object,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol[field] = tampered
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=field):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    "env_name",
    tuple(publication_verifier.PUBLICATION_EXECUTION_ENV),
)
def test_verifier_rejects_execution_policy_drift(
    tmp_path: Path,
    env_name: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["run_affecting_sage_env"][env_name] = "tampered"
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=env_name):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_protocol_timezone_drift(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["timezone"] = "America/Los_Angeles"
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="Protocol field 'timezone'"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize("arm", ["control", "candidate"])
def test_verifier_rejects_arm_manifest_timezone_drift(
    tmp_path: Path,
    arm: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    run_dir = Path(protocol[f"{arm}_dir"])
    manifest_path = run_dir.parent / "sage_ts_run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["timezone"] = "America/Los_Angeles"
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match=rf"{arm} run manifest timezone"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_arm_directory_outside_selected_run(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    external_control = tmp_path / "historical_control"
    shutil.copytree(Path(protocol["control_dir"]), external_control)
    protocol["control_dir"] = str(external_control)
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="escapes its same-run directory"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_missing_llm_cache_provenance(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    control_summary = Path(protocol["control_dir"]) / "result_summary.json"
    payload = json.loads(control_summary.read_text(encoding="utf-8"))
    payload["per_scenario_results"][0].pop("llm_cached_call_count")
    _write_json(control_summary, payload)

    with pytest.raises(ValueError, match="does not report repository whole-response"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered", "message"),
    [
        ("llm_provider_cached_prompt_tokens", None, "invalid or missing"),
        ("llm_provider_cached_prompt_call_count", -1, "invalid or missing"),
        ("llm_provider_cached_prompt_call_count", 3, "more provider-prefix"),
        ("llm_provider_cached_prompt_tokens", 101, "more provider-prefix"),
        (
            "llm_provider_cached_prompt_tokens_available_count",
            1,
            "missing provider-prefix cache metadata",
        ),
    ],
)
def test_verifier_rejects_invalid_provider_prefix_cache_accounting(
    tmp_path: Path,
    field: str,
    tampered: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    control_summary = Path(protocol["control_dir"]) / "result_summary.json"
    payload = json.loads(control_summary.read_text(encoding="utf-8"))
    if tampered is None:
        payload["per_scenario_results"][0].pop(field)
    else:
        payload["per_scenario_results"][0][field] = tampered
    _write_json(control_summary, payload)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_missing_llm_usage_summary(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    (Path(protocol["control_dir"]) / "llm_usage_summary.json").unlink()

    with pytest.raises(ValueError, match="Cannot read required JSON artifact"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_old_llm_usage_schema(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["control_dir"]) / "llm_usage_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["schema_version"] = 1
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="summary schema version"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_llm_usage_summary_row_mismatch(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["control_dir"]) / "llm_usage_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["llm_provider_cached_prompt_tokens"] += 1
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="does not match the result rows"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_missing_provider_metadata_in_raw_event(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    events_path = Path(protocol["control_dir"]) / "llm_usage_events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    events[0].pop("provider_cached_prompt_tokens")
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="provider_cached_prompt_tokens"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_raw_event_row_mismatch(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    events_path = Path(protocol["control_dir"]) / "llm_usage_events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    events[0]["scenario"] = "task_b"
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="do not match the result row"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize("model_field", ("agent", "user", "generation_model"))
def test_verifier_rejects_protocol_model_drift(
    tmp_path: Path,
    model_field: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol[model_field] = "gpt-4o"
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=model_field):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered"),
    [("generation_enabled", False), ("sage_policy", "none")],
)
def test_verifier_rejects_online_generation_policy_drift(
    tmp_path: Path,
    field: str,
    tampered: object,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol[field] = tampered
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=field):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered", "message"),
    [
        ("model", "gpt-4o", "does not use gpt-4o-mini"),
        ("source", "unknown_source", "invalid source"),
        ("arm", "online_build_full_candidate", "invalid arm"),
    ],
)
def test_verifier_rejects_raw_event_model_or_source_drift(
    tmp_path: Path,
    field: str,
    tampered: str,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    events_path = Path(protocol["control_dir"]) / "llm_usage_events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    events[0][field] = tampered
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_event_raw_usage_mismatch(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    events_path = Path(protocol["control_dir"]) / "llm_usage_events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    events[0]["raw_usage"]["prompt_tokens_details"]["cached_tokens"] += 1
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="disagrees with its raw API usage"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered", "message"),
    [
        ("scenario_count_with_usage", 1, "scenario count"),
        ("llm_usage_by_source", {}, "source summary"),
    ],
)
def test_verifier_rejects_llm_usage_summary_structure_drift(
    tmp_path: Path,
    field: str,
    tampered: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["control_dir"]) / "llm_usage_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary[field] = tampered
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_generation_calls_in_frozen_candidate(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["mode"] = "full_benchmark"
    protocol["generation_enabled"] = False
    protocol["sage_policy"] = "none"
    protocol["reflection_control_source"] = "not_applicable"
    protocol["reflection_control_delivery"] = "not_applicable_generation_disabled"
    protocol["registry_content_identity_before_run"] = copy.deepcopy(
        protocol["registry_content_identity_after_run"]
    )
    _write_json(protocol_path, protocol)
    for arm in ("control", "candidate"):
        events_path = Path(protocol[f"{arm}_dir"]) / "llm_usage_events.jsonl"
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
        ]
        for event in events:
            event["arm"] = f"full_benchmark_{arm}"
        if arm == "candidate":
            events[0]["source"] = "sage_generation"
        events_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="candidate.*invalid source"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="not-applicable",
            **_verification_pins(run_root),
        )


def test_verifier_resolves_repo_relative_paths_and_validates_fixture_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for field in ("benchmark_manifest_path", "control_dir", "candidate_dir"):
        protocol[field] = str(Path(protocol[field]).relative_to(tmp_path))
    fixture_path = Path(protocol["external_fixture"]["path"])
    protocol["external_fixture"]["path"] = str(fixture_path.relative_to(tmp_path))
    _write_json(protocol_path, protocol)
    monkeypatch.setattr(publication_verifier, "REPO_ROOT", tmp_path)

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        **_verification_pins(run_root),
    )

    assert result["external_fixture_sha256"] == _fixture_sha256(run_root)


def test_verifier_ignores_compatibility_canonical_reflection_value(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    feedback_path = (
        Path(
            json.loads((run_root / "protocol_manifest.json").read_text())[
                "candidate_dir"
            ]
        )
        / "self_evolution_task_feedback.jsonl"
    )
    feedback = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    feedback[0]["control_score"] = -999.0
    feedback_path.write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        **_verification_pins(run_root),
    )

    assert result["status"] == "pass"


def test_verifier_rejects_nonoverlapping_parallel_arm_evidence(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    candidate = protocol["parallel_arm_execution"]["arms"]["candidate"]
    candidate["started_monotonic_ns"] = 3_000_000_000
    candidate["completed_monotonic_ns"] = 4_000_000_000
    protocol["parallel_arm_execution"]["overlap_monotonic_ns"] = 0
    protocol["parallel_arm_execution"]["overlap_seconds"] = 0.0
    _write_json(protocol_path, protocol)
    candidate_status_path = run_root / "candidate_arm_status.json"
    candidate_status = json.loads(candidate_status_path.read_text(encoding="utf-8"))
    candidate_status["started_monotonic_ns"] = 3_000_000_000
    candidate_status["completed_monotonic_ns"] = 4_000_000_000
    _write_json(candidate_status_path, candidate_status)

    with pytest.raises(ValueError, match="do not prove overlap"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_dashboard_opened_after_model_process_start(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    receipt_path = run_root / "dashboard_open_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["opened_monotonic_ns"] = 2_500_000_000
    _write_json(receipt_path, receipt)

    with pytest.raises(ValueError, match="pre-model open"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_dashboard_server_root_outside_current_run(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    receipt_path = run_root / "dashboard_open_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["dashboard_server_root"] = str(run_root.parent.resolve())
    _write_json(receipt_path, receipt)

    with pytest.raises(ValueError, match="pre-model open"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize("artifact", ["receipt", "dashboard_data"])
def test_verifier_rejects_ambiguous_parallel_dashboard_identity(
    tmp_path: Path,
    artifact: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    if artifact == "receipt":
        path = run_root / "dashboard_open_receipt.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["comparison"] = "fresh_control_vs_sage_auto_selection"
        expected = "pre-model open"
    else:
        path = run_root / "dashboard" / "task_compare_data.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["arm_labels"]["candidate"] = "SAGE"
        expected = "unambiguously identify"
    _write_json(path, payload)

    with pytest.raises(ValueError, match=expected):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_conflicting_parallel_dashboard_counts(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    path = run_root / "dashboard" / "task_compare_data.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["scenario_count"] = 1
    _write_json(path, payload)

    with pytest.raises(ValueError, match="unambiguously identify"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_parallel_manifest_status_drift(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    status_path = run_root / "candidate_arm_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["process_pid"] = 999
    _write_json(status_path, status)

    with pytest.raises(ValueError, match="differs from its arm status"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def _auto_parallel_pair_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path]:
    run_root = tmp_path / "online_build_full_pilot"
    pair_root = run_root / "sage_auto_selection_parallel_pair"
    control_dir = pair_root / "control" / "control_run"
    auto_dir = run_root / "sage_auto_selection" / "auto_run"
    control_dir.mkdir(parents=True)
    auto_dir.mkdir(parents=True)
    outcome_evaluator = outcome_evaluator_manifest()
    common = {
        "agent": publication_verifier.PUBLICATION_MODEL,
        "user": publication_verifier.PUBLICATION_MODEL,
        "scenario_names": ["task_a", "task_b"],
        "processes": 1,
        "base_tool_policy": "upstream",
        "resume_from_dir": None,
        "resume_completed_limit": None,
        "timezone": publication_verifier.PUBLICATION_TIMEZONE,
        "outcome_evaluator": outcome_evaluator,
    }
    _write_json(
        control_dir.parent / "sage_ts_run_manifest.json",
        {**common, "actor_selection_mode": "policy"},
    )
    _write_json(
        auto_dir.parent / "sage_ts_run_manifest.json",
        {**common, "actor_selection_mode": "auto"},
    )
    _write_json(
        auto_dir / "selection_summary.json",
        {
            "generation_enabled": False,
            "actor_selection_mode": "auto",
            "inventory_authority_mode": "replay",
            "inventory_authority_task_count": 2,
            "inventory_authority_controls_later_exposure": True,
            "inventory_authority_source_actor_selection_mode": "policy",
        },
    )
    authority_path = tmp_path / "authority" / "inventory_authority.json"
    _write_json(authority_path, {"complete": True})
    parallel_arms = {
        "control": {
            "status": "complete",
            "process_pid": 201,
            "started_at": "start",
            "completed_at": "complete",
            "started_monotonic_ns": 1_000,
            "completed_monotonic_ns": 3_000,
        },
        "candidate": {
            "status": "complete",
            "process_pid": 202,
            "started_at": "start",
            "completed_at": "complete",
            "started_monotonic_ns": 2_000,
            "completed_monotonic_ns": 4_000,
        },
    }
    for arm, status in parallel_arms.items():
        _write_json(pair_root / f"{arm}_arm_status.json", {"arm": arm, **status})
    parallel_execution = {
        "unit": "isolated_child_process",
        "arms": parallel_arms,
        "positive_overlap_asserted": True,
        "overlap_monotonic_ns": 1_000,
        "overlap_seconds": 0.000001,
    }
    dashboard_path = pair_root / "dashboard" / "task_compare.html"
    dashboard_path.parent.mkdir(parents=True)
    dashboard_path.write_text("dashboard", encoding="utf-8")
    _write_json(
        dashboard_path.with_name("task_compare_data.json"),
        {
            "arm_labels": {
                "control": "Fresh non-learning control",
                "candidate": "SAGE auto selection",
            },
            "scenario_count": 2,
        },
    )
    dashboard_url = (
        "http://127.0.0.1:63105/sage_auto_selection_parallel_pair/"
        "dashboard/task_compare.html"
    )
    receipt_path = pair_root / "dashboard_open_receipt.json"
    _write_json(
        receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "fresh_control_vs_sage_auto_selection",
            "path": str(dashboard_path),
            "url": dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "opened_before_model_processes": True,
            "opened_monotonic_ns": 500,
            "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
            "dashboard_server_root": str(run_root.resolve()),
        },
    )
    order_sha256 = hashlib.sha256(b"task_a\ntask_b\n").hexdigest()
    row_mapping = {
        "task_a": {"outcome_similarity": 0.0},
        "task_b": {"outcome_similarity": 1.0},
    }
    auto_row_mapping = {
        "task_a": {"outcome_similarity": 1.0},
        "task_b": {"outcome_similarity": 1.0},
    }
    outcome_comparison_path = pair_root / "auto_control_outcome_comparison.json"
    _write_json(
        outcome_comparison_path,
        publication_verifier._outcome_only_pair_summary(
            row_mapping,
            auto_row_mapping,
            ["task_a", "task_b"],
        ),
    )
    pair_manifest_path = pair_root / "parallel_pair_manifest.json"
    _write_json(
        pair_manifest_path,
        {
            "schema_version": 1,
            "experiment": "sage_auto_selection_parallel_control_pair",
            "status": "complete",
            "mode": "online_build_full",
            "agent": publication_verifier.PUBLICATION_MODEL,
            "user": publication_verifier.PUBLICATION_MODEL,
            "base_tool_policy": "upstream",
            "scenario_count": 2,
            "scenario_order_sha256": order_sha256,
            "control_role": "fresh_non_learning_control",
            "candidate_role": "sage_auto_selection",
            "control_run_dir": str(control_dir),
            "auto_run_dir": str(auto_dir),
            "control_cache_mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": 2,
            "cache_accessed": False,
            "openai_response_cache_enabled": False,
            "sage_task_cache_enabled": False,
            "persistent_response_cache_reuse": False,
            "publication_performance_endpoint": ("outcome_task_completion_similarity"),
            "legacy_score_is_performance_gate": False,
            "parallel_arms": True,
            "parallel_arm_execution": parallel_execution,
            "auto_control_delivery": "not_connected",
            "auto_control_output_influences_inventory": False,
            "auto_control_output_influences_execution": False,
            "auto_inventory_source": "matched_policy_inventory_authority",
            "inventory_authority_path": str(authority_path),
            "inventory_authority_sha256": hashlib.sha256(
                authority_path.read_bytes()
            ).hexdigest(),
            "outcome_evaluator": outcome_evaluator,
            "outcome_comparison_path": str(outcome_comparison_path),
            "outcome_comparison_sha256": hashlib.sha256(
                outcome_comparison_path.read_bytes()
            ).hexdigest(),
            "timezone": publication_verifier.PUBLICATION_TIMEZONE,
            "dashboard_task_compare_path": str(dashboard_path),
            "dashboard_task_compare_url": dashboard_url,
            "dashboard_open_receipt_path": str(receipt_path),
        },
    )

    def fake_rows(*args: object, **kwargs: object) -> object:
        return (
            (
                auto_row_mapping
                if kwargs.get("arm") == "sage_auto_selection"
                else row_mapping
            ),
            ["task_a", "task_b"],
            {},
        )

    monkeypatch.setattr(publication_verifier, "_uncached_rows", fake_rows)
    monkeypatch.setattr(
        publication_verifier, "_verify_llm_usage_artifacts", lambda *a, **k: None
    )
    return run_root, pair_manifest_path, auto_dir


def test_auto_selection_parallel_pair_proves_fresh_control_overlap_and_pre_model_dashboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root, pair_manifest_path, auto_dir = _auto_parallel_pair_fixture(
        tmp_path, monkeypatch
    )

    result = publication_verifier.verify_auto_selection_parallel_pair(
        pair_manifest_path,
        run_root=run_root,
        expected_tasks=2,
        expected_scenario_order_sha256=hashlib.sha256(b"task_a\ntask_b\n").hexdigest(),
        expected_auto_dir=auto_dir,
    )

    assert result["status"] == "pass"
    assert result["parallel_arm_execution"]["positive_overlap_asserted"] is True


def test_auto_control_outcome_summary_counts_only_exact_one_as_success() -> None:
    summary = publication_verifier._outcome_only_pair_summary(
        {"task": {"outcome_similarity": 1.0 - 1e-13}},
        {"task": {"outcome_similarity": 1.0}},
        ["task"],
    )

    assert summary["control_exact_outcome_successes"] == 0
    assert summary["auto_exact_outcome_successes"] == 1


@pytest.mark.parametrize(
    "failure",
    [
        "nonoverlap",
        "late_dashboard",
        "wrong_dashboard_root",
        "control_feedback",
        "control_influence",
    ],
)
def test_auto_selection_parallel_pair_rejects_invalid_independence_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    run_root, pair_manifest_path, auto_dir = _auto_parallel_pair_fixture(
        tmp_path, monkeypatch
    )
    if failure == "nonoverlap":
        pair = json.loads(pair_manifest_path.read_text(encoding="utf-8"))
        candidate = pair["parallel_arm_execution"]["arms"]["candidate"]
        candidate["started_monotonic_ns"] = 3_000
        candidate["completed_monotonic_ns"] = 4_000
        pair["parallel_arm_execution"]["overlap_monotonic_ns"] = 0
        pair["parallel_arm_execution"]["overlap_seconds"] = 0.0
        _write_json(pair_manifest_path, pair)
        candidate_status_path = pair_manifest_path.parent / "candidate_arm_status.json"
        candidate_status = json.loads(candidate_status_path.read_text(encoding="utf-8"))
        candidate_status["started_monotonic_ns"] = 3_000
        candidate_status["completed_monotonic_ns"] = 4_000
        _write_json(candidate_status_path, candidate_status)
        expected = "do not prove overlap"
    elif failure == "late_dashboard":
        pair = json.loads(pair_manifest_path.read_text(encoding="utf-8"))
        receipt_path = Path(pair["dashboard_open_receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["opened_monotonic_ns"] = 2_500
        _write_json(receipt_path, receipt)
        expected = "pre-model opening"
    elif failure == "wrong_dashboard_root":
        pair = json.loads(pair_manifest_path.read_text(encoding="utf-8"))
        receipt_path = Path(pair["dashboard_open_receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["dashboard_server_root"] = str(run_root.parent.resolve())
        _write_json(receipt_path, receipt)
        expected = "pre-model opening"
    elif failure == "control_feedback":
        (auto_dir / "self_evolution_task_feedback.jsonl").write_text(
            "{}\n", encoding="utf-8"
        )
        expected = "consumed control feedback"
    else:
        pair = json.loads(pair_manifest_path.read_text(encoding="utf-8"))
        pair["auto_control_output_influences_execution"] = True
        _write_json(pair_manifest_path, pair)
        expected = "auto_control_output_influences_execution"

    with pytest.raises(ValueError, match=expected):
        publication_verifier.verify_auto_selection_parallel_pair(
            pair_manifest_path,
            run_root=run_root,
            expected_tasks=2,
            expected_scenario_order_sha256=hashlib.sha256(
                b"task_a\ntask_b\n"
            ).hexdigest(),
            expected_auto_dir=auto_dir,
        )


def test_verifier_rejects_fixture_mode_or_mutated_bytes(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    pins = _verification_pins(run_root)
    protocol["external_fixture"]["mode"] = "read_write"
    _write_json(protocol_path, protocol)
    with pytest.raises(ValueError, match="read-only"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **pins,
        )

    protocol["external_fixture"]["mode"] = "read_only"
    _write_json(protocol_path, protocol)
    Path(protocol["external_fixture"]["path"]).write_text(
        '{"fixture": "mutated"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bytes no longer match"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **pins,
        )


def test_verifier_rejects_missing_publication_provenance(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol.pop("publication_provenance")
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="does not record publication provenance"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered", "message"),
    [
        ("schema_version", 1, "schema version"),
        ("git_commit", "3" * 40, "Current clean source identity"),
        ("git_tree", "4" * 40, "Current clean source identity"),
        ("git_clean", False, "clean Git worktree"),
        ("fixed_toolsandbox_timestamp", 1784832589, "timestamp"),
        ("python_version", "3.12.8", "python_version"),
        ("python_implementation", "PyPy", "python_implementation"),
        ("isolated_environment", False, "isolated_environment"),
        ("platform_system", "Linux", "platform_system"),
        ("platform_machine", "x86_64", "platform_machine"),
        ("environment_lock_path", "requirements.txt", "canonical environment lock"),
        ("environment_lock_sha256", "0" * 64, "lock hash"),
        ("external_distribution_count", 107, "distribution count"),
        ("external_distribution_sha256", "0" * 64, "distribution identity"),
        ("execution_environment", {}, "complete execution policy"),
    ],
)
def test_verifier_rejects_tampered_publication_provenance(
    tmp_path: Path,
    field: str,
    tampered: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["publication_provenance"][field] = tampered
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_wrong_protocol_timestamp(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["toolsandbox_fixed_now_timestamp"] = "1784832589"
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="timestamp"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_dirty_or_different_current_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _fresh_run(tmp_path)
    monkeypatch.setattr(
        publication_verifier,
        "_clean_source_identity",
        lambda repo_root: (_ for _ in ()).throw(
            ValueError("Current publication source worktree is not clean")
        ),
    )

    with pytest.raises(ValueError, match="not clean"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_mutated_environment_lock(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    lock_path = tmp_path / publication_verifier.PUBLICATION_ENVIRONMENT_LOCK
    lock_path.write_text(
        lock_path.read_text(encoding="utf-8") + "# post-run mutation\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exact pin"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_different_active_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _fresh_run(tmp_path)
    active = _test_environment_identity(tmp_path)
    active["python_executable"] = str(tmp_path / "other-venv" / "bin" / "python")
    monkeypatch.setattr(
        publication_verifier,
        "_active_publication_environment",
        lambda lock_path, repo_root: active,
    )

    with pytest.raises(ValueError, match="python_executable"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_runner_requires_launcher_package_count_and_records_exact_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path = tmp_path / protocol_runner.PUBLICATION_ENVIRONMENT_LOCK
    shutil.copy2(
        PROJECT_ROOT / protocol_runner.PUBLICATION_ENVIRONMENT_LOCK,
        lock_path,
    )
    environment = _test_environment_identity(tmp_path)
    source = {
        "git_commit": TEST_GIT_COMMIT,
        "git_tree": TEST_GIT_TREE,
        "git_clean": True,
    }
    monkeypatch.setattr(
        protocol_runner,
        "_clean_source_identity",
        lambda repo_root: source,
    )
    monkeypatch.setattr(
        protocol_runner,
        "_active_publication_environment",
        lambda lock_path, repo_root: environment,
    )
    exported = {
        "SAGE_PUBLICATION_GIT_COMMIT": TEST_GIT_COMMIT,
        "SAGE_PUBLICATION_GIT_TREE": TEST_GIT_TREE,
        "SAGE_PUBLICATION_PYTHON_EXECUTABLE": environment["python_executable"],
        "SAGE_PUBLICATION_PYTHON_VERSION": environment["python_version"],
        "SAGE_PUBLICATION_PYTHON_PREFIX": environment["python_prefix"],
        "SAGE_PUBLICATION_PYTHON_BASE_PREFIX": environment["python_base_prefix"],
        "SAGE_PUBLICATION_PYTHON_IMPLEMENTATION": environment["python_implementation"],
        "SAGE_PUBLICATION_PLATFORM_SYSTEM": environment["platform_system"],
        "SAGE_PUBLICATION_PLATFORM_MACHINE": environment["platform_machine"],
        "SAGE_PUBLICATION_ENVIRONMENT_LOCK": environment["environment_lock_path"],
        "SAGE_PUBLICATION_ENVIRONMENT_LOCK_SHA256": environment[
            "environment_lock_sha256"
        ],
        "SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT": str(
            environment["external_distribution_count"]
        ),
        "SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_SHA256": environment[
            "external_distribution_sha256"
        ],
        **protocol_runner.PUBLICATION_EXECUTION_ENV,
    }
    for name, value in exported.items():
        monkeypatch.setenv(name, str(value))

    provenance = protocol_runner._publication_provenance(
        fixed_toolsandbox_timestamp=str(
            protocol_runner.PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
        ),
        freeze_toolsandbox_clock=True,
        repo_root=tmp_path,
    )

    assert provenance["external_distribution_count"] == 108
    assert (
        provenance["external_distribution_sha256"]
        == environment["external_distribution_sha256"]
    )
    assert (
        provenance["execution_environment"] == protocol_runner.PUBLICATION_EXECUTION_ENV
    )
    monkeypatch.delenv("SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT")
    with pytest.raises(
        ValueError,
        match="SAGE_PUBLICATION_EXTERNAL_DISTRIBUTION_COUNT",
    ):
        protocol_runner._publication_provenance(
            fixed_toolsandbox_timestamp=str(
                protocol_runner.PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
            ),
            freeze_toolsandbox_clock=True,
            repo_root=tmp_path,
        )
    monkeypatch.setenv("SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS", "0")
    with pytest.raises(ValueError, match="execution policy changed"):
        protocol_runner._assert_publication_source_unchanged(
            provenance,
            repo_root=tmp_path,
        )
    monkeypatch.setenv("SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS", "1,3")

    changed_environment = dict(environment)
    changed_environment["python_executable"] = str(
        tmp_path / "replacement-venv" / "bin" / "python"
    )
    monkeypatch.setattr(
        protocol_runner,
        "_active_publication_environment",
        lambda lock_path, repo_root: changed_environment,
    )
    with pytest.raises(ValueError, match="changed during execution"):
        protocol_runner._assert_publication_source_unchanged(
            provenance,
            repo_root=tmp_path,
        )


def test_campaign_job_removes_every_baseline_cache_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "CONTROL_CACHE_ROOT",
        "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
        "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
        "RESUME_RUN_ROOT",
        "RESUME_COMPLETED_LIMIT",
        "RESUME_REGISTRY_CHECKPOINT",
        *protocol_runner.DIAGNOSTIC_FORCE_ENV_VARS,
    ):
        monkeypatch.setenv(name, "should-not-survive")
    manifest = {
        "campaign_id": "fresh_campaign",
        "fixed_toolsandbox_timestamp": 123,
        "benchmark_manifest": "benchmark.json",
        "external_fixture": {
            "path": "fixtures/rapid.json",
            "sha256": "fixture-sha",
            "mode": "read_only",
        },
        "paths": {
            "output_root": "outputs/campaign",
            "artifact_root": "artifacts/campaign",
        },
    }
    pair = {
        "replication": 1,
        "online": {
            "search_root": "outputs/campaign/online/rep01/native_action",
            "registry_dir": "artifacts/campaign/online/rep01/native_action_registry",
        },
    }

    command, env, _ = _job_command(
        repo_root=tmp_path,
        manifest=manifest,
        pair=pair,
        arm="online",
        port=63000,
        execution_approved=True,
    )

    assert command == [
        "bash",
        "scripts/run_native_action_4omini_ab.sh",
        "full",
        "63000",
        "native-only",
    ]
    assert env["CONTROL_CACHE"] == "off"
    assert env["SAGE_BENCHMARK_MANIFEST"] == str(tmp_path / "benchmark.json")
    assert env["TOOLSANDBOX_RAPID_CACHE_MODE"] == "read_only"
    assert env["TOOLSANDBOX_RAPID_CACHE_PATH"] == str(tmp_path / "fixtures/rapid.json")
    assert env["SAGE_APPROVE_LIVE_RUN"] == "YES"
    for name, expected in publication_verifier.PUBLICATION_EXECUTION_ENV.items():
        assert env[name] == expected
    assert all(
        env.get(name) is None
        for name in (
            "CONTROL_CACHE_ROOT",
            "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
            "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
            "RESUME_RUN_ROOT",
            "RESUME_COMPLETED_LIMIT",
            "RESUME_REGISTRY_CHECKPOINT",
            *protocol_runner.DIAGNOSTIC_FORCE_ENV_VARS,
        )
    )
