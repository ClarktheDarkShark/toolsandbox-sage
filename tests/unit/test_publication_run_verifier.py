from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import scripts.run_sage_protocol as protocol_runner
import scripts.verify_publication_run as publication_verifier
from scripts.run_chapter4_evidence_campaign import _job_command
from scripts.verify_publication_run import verify_run

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_GIT_COMMIT = "1" * 40
TEST_GIT_TREE = "2" * 40


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
    fixture_path = tmp_path / "rapid_api_cache.json"
    fixture_path.write_text('{"fixture": true}\n', encoding="utf-8")
    fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text('{"benchmark": true}\n', encoding="utf-8")
    benchmark_sha256 = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    control_rows = [
        {
            "name": "task_a",
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
            "similarity": 1.0,
            "outcome_similarity": None,
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
    candidate_rows = [
        {
            "name": "task_a",
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
            "similarity": 1.0,
            "outcome_similarity": None,
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
    dashboard_path = run_root / "dashboard" / "task_compare.html"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("<!doctype html>\n", encoding="utf-8")
    control_status = {
        "arm": "control",
        "status": "complete",
        "process_pid": 101,
        "started_at": "2026-09-08T10:00:00-04:00",
        "completed_at": "2026-09-08T10:01:00-04:00",
        "started_monotonic_ns": 200,
        "completed_monotonic_ns": 500,
    }
    candidate_status = {
        "arm": "candidate",
        "status": "complete",
        "process_pid": 202,
        "started_at": "2026-09-08T10:00:01-04:00",
        "completed_at": "2026-09-08T10:01:01-04:00",
        "started_monotonic_ns": 210,
        "completed_monotonic_ns": 600,
    }
    _write_json(run_root / "control_arm_status.json", control_status)
    _write_json(run_root / "candidate_arm_status.json", candidate_status)
    parallel_execution = {
        "unit": "isolated_child_process",
        "arms": {
            "control": {
                key: control_status[key]
                for key in (
                    "status",
                    "process_pid",
                    "started_at",
                    "completed_at",
                    "started_monotonic_ns",
                    "completed_monotonic_ns",
                )
            },
            "candidate": {
                key: candidate_status[key]
                for key in (
                    "status",
                    "process_pid",
                    "started_at",
                    "completed_at",
                    "started_monotonic_ns",
                    "completed_monotonic_ns",
                )
            },
        },
        "positive_overlap_asserted": True,
        "overlap_monotonic_ns": 290,
        "overlap_seconds": 0.00000029,
    }
    dashboard_url = "http://127.0.0.1:63105/dashboard/task_compare.html"
    dashboard_receipt_path = run_root / "dashboard_open_receipt.json"
    _write_json(
        dashboard_receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "fresh_control_vs_policy_sage",
            "path": str(dashboard_path.resolve()),
            "url": dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "dashboard_server_protocol": (
                publication_verifier.DASHBOARD_SERVER_PROTOCOL  # type: ignore[attr-defined]
            ),
            "dashboard_server_root": str(run_root.resolve()),
            "opened_before_model_processes": True,
            "opened_monotonic_ns": 100,
        },
    )
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
            "fresh_control_required": True,
            "publication_performance_endpoint": "outcome_task_completion_similarity",
            "actor_selection_mode": "policy",
            "reporting_outcome_evaluator": (
                publication_verifier.outcome_evaluator_manifest()  # type: ignore[attr-defined]
            ),
            "online_feedback_evaluator_version": (
                publication_verifier.ONLINE_FEEDBACK_EVALUATOR_VERSION  # type: ignore[attr-defined]
            ),
            "timezone": publication_verifier.PUBLICATION_TIMEZONE,
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
            "generator_contract_and_repair_analysis_memoization": "within_run_only",
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
            "dashboard_task_compare_url": dashboard_url,
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
    _write_json(run_root / "paired_comparison.json", {"deltas": []})
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
    assert result["external_distribution_count"] == 108
    assert len(result["external_distribution_sha256"]) == 64


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
        "SAGE_BATCH_NO_DASHBOARD_OPEN",
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
    assert "SAGE_BATCH_NO_DASHBOARD_OPEN" not in env
    for name, expected in publication_verifier.PUBLICATION_EXECUTION_ENV.items():
        assert env[name] == expected
    assert all(
        env.get(name) is None
        for name in (
            "SAGE_BATCH_NO_DASHBOARD_OPEN",
            "CONTROL_CACHE_ROOT",
            "SAGE_SELF_EVOLVING_CONTROL_CACHE_ROOT",
            "SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY",
            "RESUME_RUN_ROOT",
            "RESUME_COMPLETED_LIMIT",
            "RESUME_REGISTRY_CHECKPOINT",
            *protocol_runner.DIAGNOSTIC_FORCE_ENV_VARS,
        )
    )
