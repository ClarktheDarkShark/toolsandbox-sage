from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

import scripts.run_sage_protocol as protocol_runner
import scripts.verify_publication_run as publication_verifier
from scripts.run_chapter4_evidence_campaign import _job_command
from scripts.verify_publication_run import verify_run
from tool_sandbox.common.execution_context import ExecutionContext

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_GIT_COMMIT = "1" * 40
TEST_GIT_TREE = "2" * 40
_TEST_OUTCOME_MARKER = "__publication_test_outcome__"
_REAL_LOAD_PUBLICATION_SCENARIOS = publication_verifier._load_publication_scenarios
_REAL_RECOMPUTE_TRAJECTORY = publication_verifier._independently_recompute_trajectory


def _test_audited_outcome(value: float) -> dict[str, Any]:
    identity = publication_verifier.outcome_evaluator_manifest()
    return {
        "outcome_similarity": value,
        "outcome_milestone_similarity": value,
        "outcome_minefield_similarity": 0.0,
        "outcome_check_count": 1,
        "outcome_checks": [
            {
                "index": 0,
                "kind": "synthetic_test_outcome",
                "included": True,
                "score": value,
            }
        ],
        "outcome_evaluator_version": identity["version"],
        "outcome_evaluator_contract_sha256": identity["contract_sha256"],
        "outcome_evaluator_source_sha256": identity["source_sha256"],
    }


def _fake_trajectory_recomputation(
    _scenario: object,
    execution_context: ExecutionContext,
    *,
    scenario_name: str,
) -> dict[str, Any]:
    del scenario_name
    marker = next(
        (
            item
            for item in (execution_context.tool_allow_list or [])
            if item.startswith(_TEST_OUTCOME_MARKER)
        ),
        None,
    )
    if marker is None:
        raise ValueError("synthetic trajectory has no outcome marker")
    value = float(marker.removeprefix(_TEST_OUTCOME_MARKER))
    return {
        "audited_outcome": _test_audited_outcome(value),
        "paper_outcome": {"outcome_similarity": None},
        "conversation": [],
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
    monkeypatch.setattr(
        publication_verifier,
        "_load_publication_scenarios",
        lambda scenario_names: {name: object() for name in scenario_names},
    )
    monkeypatch.setattr(
        publication_verifier,
        "_independently_recompute_trajectory",
        _fake_trajectory_recomputation,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_synthetic_trajectory(
    run_dir: Path,
    *,
    scenario_name: str,
    outcome_similarity: float,
) -> None:
    trajectory_dir = run_dir / "trajectories" / scenario_name
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    context = ExecutionContext()
    context.tool_allow_list = [f"{_TEST_OUTCOME_MARKER}{outcome_similarity!r}"]
    _write_json(
        trajectory_dir / "execution_context.json",
        context.to_dict(serialize_console=False),
    )
    (trajectory_dir / "conversation.json").write_text("[]\n", encoding="utf-8")


def _feedback_outcome_with_source(
    row: dict[str, Any],
) -> tuple[float | None, str]:
    audited_outcome = row.get("outcome_similarity")
    if audited_outcome is not None:
        return float(audited_outcome), "audited_outcome"
    return None, "unavailable"


def _reflection_feedback_row(
    control: dict[str, Any],
    candidate: dict[str, Any],
    *,
    completed_count: int,
) -> dict[str, Any]:
    control_score = float(control["similarity"])
    candidate_score = float(candidate["similarity"])
    control_outcome, control_source = _feedback_outcome_with_source(control)
    candidate_outcome, candidate_source = _feedback_outcome_with_source(candidate)
    return {
        "event": "self_evolution_task_assessed",
        "scenario": control["name"],
        "completed_count": completed_count,
        "control_source": "same_run_fresh",
        "control_score": control_score,
        "candidate_score": candidate_score,
        "score_delta": candidate_score - control_score,
        "control_outcome": control_outcome,
        "control_outcome_source": control_source,
        "candidate_outcome": candidate_outcome,
        "candidate_outcome_source": candidate_source,
        "outcome_delta": (
            candidate_outcome - control_outcome
            if control_outcome is not None and candidate_outcome is not None
            else None
        ),
        "task_family_key": "synthetic_family",
        "source_task_id_redacted": True,
        "generated_tools_visible": [],
        "generated_tools_called": [],
        "generated_tools_attempted": [],
        "generated_tools_failed": [],
        "generated_tool_contract_failures": [],
        "generated_tool_versions": {},
    }


@pytest.mark.parametrize(
    (
        "online_feedback_outcome",
        "audited_outcome",
        "feedback_outcome",
        "feedback_source",
    ),
    [
        (None, 0.0, 0.0, "audited_outcome"),
        (0.0, 1.0, 1.0, "audited_outcome"),
        (0.0, None, None, "unavailable"),
        (None, None, None, "unavailable"),
    ],
)
def test_reflection_verifier_uses_null_aware_outcome_fallback(
    tmp_path: Path,
    online_feedback_outcome: float | None,
    audited_outcome: float | None,
    feedback_outcome: float | None,
    feedback_source: str,
) -> None:
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    control = {
        "name": "task_a",
        "similarity": 0.25,
        "outcome_similarity": audited_outcome,
        "online_feedback_outcome_similarity": online_feedback_outcome,
    }
    candidate = {
        "name": "task_a",
        "similarity": 0.75,
        "outcome_similarity": audited_outcome,
        "online_feedback_outcome_similarity": online_feedback_outcome,
    }
    feedback = _reflection_feedback_row(control, candidate, completed_count=1)
    assert feedback["control_outcome"] == feedback_outcome
    assert feedback["control_outcome_source"] == feedback_source
    feedback_path = candidate_dir / "self_evolution_task_feedback.jsonl"
    feedback_path.write_text(
        json.dumps(feedback) + "\n",
        encoding="utf-8",
    )
    control_rows = {"task_a": control}
    candidate_rows = {"task_a": candidate}

    publication_verifier._verify_reflection(
        candidate_dir,
        control_rows=control_rows,
        candidate_rows=candidate_rows,
    )


def test_reflection_verifier_rejects_audited_outcome_mismatch(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    control = {
        "name": "task_a",
        "similarity": 0.25,
        "outcome_similarity": 0.0,
        "online_feedback_outcome_similarity": None,
    }
    candidate = {
        "name": "task_a",
        "similarity": 0.75,
        "outcome_similarity": 0.5,
        "online_feedback_outcome_similarity": None,
    }
    feedback = _reflection_feedback_row(control, candidate, completed_count=1)
    feedback["control_outcome"] = 1.0
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        json.dumps(feedback) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Reflection control outcome mismatch"):
        publication_verifier._verify_reflection(
            candidate_dir,
            control_rows={"task_a": control},
            candidate_rows={"task_a": candidate},
        )


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
    outcome_evaluator = publication_verifier.outcome_evaluator_manifest()
    outcome_evaluator_fields = {
        "outcome_evaluator_version": outcome_evaluator["version"],
        "outcome_evaluator_contract_sha256": outcome_evaluator["contract_sha256"],
        "outcome_evaluator_source_sha256": outcome_evaluator["source_sha256"],
    }
    control_rows = [
        {
            "name": "task_a",
            "similarity": 0.25,
            "outcome_similarity": 0.5,
            "online_feedback_outcome_similarity": None,
            **outcome_evaluator_fields,
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
            "outcome_similarity": 0.0,
            **outcome_evaluator_fields,
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
            "online_feedback_outcome_similarity": None,
            **outcome_evaluator_fields,
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
            "outcome_similarity": 0.0,
            **outcome_evaluator_fields,
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
        row.update(_test_audited_outcome(float(row["outcome_similarity"])))
        row["online_feedback_outcome_similarity"] = None
        row["online_feedback_evaluator_version"] = (
            publication_verifier.ONLINE_FEEDBACK_EVALUATOR_VERSION
        )
        row["traceback"] = None
        row["exception_type"] = None
    _write_json(
        control_dir / "result_summary.json",
        {"per_scenario_results": control_rows},
    )
    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": candidate_rows},
    )
    for run_dir, rows in (
        (control_dir, control_rows),
        (candidate_dir, candidate_rows),
    ):
        for row in rows:
            _write_synthetic_trajectory(
                run_dir,
                scenario_name=str(row["name"]),
                outcome_similarity=float(row["outcome_similarity"]),
            )
    for run_dir, run_type in (
        (control_dir, "online_build_full_control"),
        (candidate_dir, "online_build_full_candidate"),
    ):
        _write_json(
            run_dir / "sage_ts_run_manifest.json",
            {
                "run_type": run_type,
                "agent_runtime": publication_verifier.SAGE_WRAPPED_AGENT_RUNTIME,
                "actor_selection_mode": "policy",
            },
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
        _reflection_feedback_row(
            control,
            candidate,
            completed_count=completed_count,
        )
        for completed_count, (control, candidate) in enumerate(
            zip(control_rows, candidate_rows, strict=True),
            start=1,
        )
    ]
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )
    (candidate_dir / "scenario_tool_selection.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "scenario": row["scenario"],
                    "generated_tools_visible": row["generated_tools_visible"],
                    "generated_tools_called": row["generated_tools_called"],
                    "generated_tools_attempted": row["generated_tools_attempted"],
                    "generated_tools_failed": row["generated_tools_failed"],
                    "generated_tool_contract_failures": row[
                        "generated_tool_contract_failures"
                    ],
                    "generated_tool_versions": row["generated_tool_versions"],
                }
            )
            + "\n"
            for row in feedback
        ),
        encoding="utf-8",
    )
    _write_json(
        candidate_dir / "post_deployment_repair_state.json",
        {
            "schema_version": 1,
            "pending_repair_requests": [],
            "handled_repair_request_ids": [],
            "canary_state_by_tool": {},
        },
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
    registry_dir = tmp_path / "artifacts" / "native_action_registry"
    registry_manifest = registry_dir / "registry_manifest.json"
    _write_json(registry_manifest, {"schema_version": 1, "tools": {}})
    registry_manifest_sha256 = hashlib.sha256(
        registry_manifest.read_bytes()
    ).hexdigest()
    _write_json(
        run_root / "protocol_manifest.json",
        {
            "publication_gate_purpose": (
                publication_verifier.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
            ),
            "performance_gate_passed": True,
            "performance_gate_reasons": [],
            "protocol_gate_passed": True,
            "protocol_gate_reasons": [],
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
            "registry_manifest_digest_after_run": registry_manifest_sha256,
            "registry_gate_snapshot": {
                "registry_dir": str(registry_dir),
                "manifest_existed_before_run": False,
                "snapshot_path": None,
                "manifest_digest_before_run": None,
                "registry_directory_existed_before_run": False,
                "registry_inventory_before_run": [],
                "registry_inventory_count_before_run": 0,
                "registry_inventory_sha256": hashlib.sha256(b"[]").hexdigest(),
            },
            "fresh_control_required": True,
            "scenario_transform_failure_policy": "abort",
            "publication_performance_endpoint": "outcome_task_completion_similarity",
            "actor_selection_mode": "policy",
            "control_condition": publication_verifier.MATCHED_CONTROL_CONDITION,
            "control_agent_runtime": (publication_verifier.SAGE_WRAPPED_AGENT_RUNTIME),
            "control_actor_selection_mode": "policy",
            "control_generated_tools_enabled": False,
            "candidate_agent_runtime": (
                publication_verifier.SAGE_WRAPPED_AGENT_RUNTIME
            ),
            "candidate_actor_selection_mode": "policy",
            "candidate_generated_tools_enabled": True,
            "reporting_outcome_evaluator": (
                publication_verifier.outcome_evaluator_manifest()
            ),
            "online_feedback_evaluator_version": (
                publication_verifier.ONLINE_FEEDBACK_EVALUATOR_VERSION
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
    protocol_payload = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    _write_json(
        run_root / "registry_gate" / "registry_gate_snapshot.json",
        protocol_payload["registry_gate_snapshot"],
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
        {
            "publication_gate_purpose": (
                publication_verifier.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
            ),
            "performance_gate_passed": True,
            "performance_gate_reasons": [],
            "protocol_gate_passed": True,
            "protocol_gate_reasons": [],
            "runtime_exception_count": 0,
            "scenario_count": 2,
            "outcome_scenario_count": 2,
            "control_mean_outcome_similarity": 0.25,
            "candidate_mean_outcome_similarity": 0.5,
            "mean_outcome_similarity_delta": 0.25,
            "outcome_gain_count": 1,
            "outcome_regression_count": 0,
            "outcome_preserved_count": 1,
            "control": {
                "run_status": "complete",
                "scenario_count": 2,
                "planned_scenario_count": 2,
                "exception_count": 0,
            },
            "candidate": {
                "run_status": "complete",
                "scenario_count": 2,
                "planned_scenario_count": 2,
                "exception_count": 0,
            },
            "deltas": [],
        },
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


def _lifecycle_artifacts(
    tmp_path: Path,
    *,
    request: bool = True,
    acknowledgement_status: str | None = "rolled_back",
    pending: bool = False,
    canary: bool = False,
    retired: bool = True,
) -> tuple[Path, Path]:
    candidate_dir = tmp_path / "candidate"
    registry_dir = tmp_path / "registry"
    candidate_dir.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    request_row = {
        "schema_version": 1,
        "request_id": "request-1",
        "tool_name": "helper",
        "source_tool_version": 2,
        "future_tasks_only": True,
        "triggering_task_replay_allowed": False,
    }
    if request:
        (candidate_dir / "self_evolution_tool_repair_requests.jsonl").write_text(
            json.dumps(request_row) + "\n", encoding="utf-8"
        )
    if acknowledgement_status is not None:
        (
            candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
        ).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": "request-1",
                    "tool_name": "helper",
                    "new_version": 2,
                    "status": acknowledgement_status,
                    "future_tasks_only": True,
                    "triggering_task_replay_allowed": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    feedback_row = {
        "event": "self_evolution_task_assessed",
        "scenario": "synthetic_task",
        "task_family_key": "synthetic_family",
        "source_task_id_redacted": True,
        "generated_tools_visible": [],
        "generated_tools_called": [],
        "generated_tools_attempted": [],
        "generated_tools_failed": [],
        "generated_tool_contract_failures": [],
        "generated_tool_versions": {},
    }
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        json.dumps(feedback_row) + "\n",
        encoding="utf-8",
    )
    selection_row = {
        key: value
        for key, value in feedback_row.items()
        if key
        in {
            "scenario",
            "generated_tools_visible",
            "generated_tools_called",
            "generated_tools_attempted",
            "generated_tools_failed",
            "generated_tool_contract_failures",
            "generated_tool_versions",
        }
    }
    (candidate_dir / "scenario_tool_selection.jsonl").write_text(
        json.dumps(selection_row) + "\n",
        encoding="utf-8",
    )
    _write_json(
        candidate_dir / "post_deployment_repair_state.json",
        {
            "schema_version": 1,
            "pending_repair_requests": [request_row] if pending else [],
            "handled_repair_request_ids": ["request-1"] if request else [],
            "canary_state_by_tool": {
                "helper": {"request_id": "request-1", "tool_version": 2}
            }
            if canary
            else {},
            "repair_transactions_by_tool": {},
        },
    )
    _write_json(
        registry_dir / "registry_manifest.json",
        {"tools": {"helper": {"version": 2, "retired": retired}}},
    )
    return candidate_dir, registry_dir


def _mark_lifecycle_request_as_metadata(
    candidate_dir: Path,
    *,
    source_code_hash: str = "a" * 64,
) -> None:
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.update(
        {
            "repair_kind": "metadata",
            "source_code_hash": source_code_hash,
        }
    )
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
    acknowledgement_path = (
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    acknowledgement = json.loads(acknowledgement_path.read_text(encoding="utf-8"))
    acknowledgement["implementation_proof"] = {
        "proof_schema_version": 1,
        "repair_kind": "metadata",
        "source_code_hash": source_code_hash,
        "replacement_code_hash": None,
        "replacement_activated": False,
        "implementation_preserved": True,
        "model_authored_code_change_discarded": False,
    }
    acknowledgement_path.write_text(
        json.dumps(acknowledgement) + "\n",
        encoding="utf-8",
    )


def _promoted_lifecycle_artifacts(
    tmp_path: Path,
    *,
    retired: bool = False,
) -> tuple[Path, Path]:
    candidate_dir, registry_dir = _lifecycle_artifacts(
        tmp_path,
        acknowledgement_status=None,
        retired=retired,
    )
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.update(
        {
            "source_tool_version": 1,
            "repair_kind": "implementation",
            "target_task_family": "synthetic_family",
            "trigger_reason_codes": ["deterministic_public_contract_failure"],
        }
    )
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
    acknowledgements = [
        {
            "schema_version": 1,
            "request_id": "request-1",
            "tool_name": "helper",
            "new_version": 2,
            "status": "canary_pending",
            "acknowledged_after_completed_count": 0,
            "eligible_from_completed_count": 1,
            "future_tasks_only": True,
            "triggering_task_replay_allowed": False,
        },
        {
            "schema_version": 1,
            "request_id": "request-1",
            "tool_name": "helper",
            "new_version": 2,
            "status": "promoted",
            "acknowledged_after_completed_count": 3,
            "eligible_from_completed_count": 4,
            "future_tasks_only": True,
            "triggering_task_replay_allowed": False,
        },
    ]
    (candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in acknowledgements),
        encoding="utf-8",
    )
    feedback_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for completed_count, (control_outcome, candidate_outcome) in enumerate(
        ((0.0, 1.0), (1.0, 1.0), (0.0, 0.0)),
        start=1,
    ):
        scenario = f"synthetic_task_{completed_count}"
        outcome_delta = candidate_outcome - control_outcome
        common = {
            "scenario": scenario,
            "generated_tools_visible": ["helper"],
            "generated_tools_called": ["helper"],
            "generated_tools_attempted": ["helper"],
            "generated_tools_failed": [],
            "generated_tool_contract_failures": [],
            "generated_tool_versions": {"helper": 2},
        }
        selection_rows.append(
            {
                **common,
                "outcome_similarity": candidate_outcome,
                "exception_type": None,
            }
        )
        feedback_rows.append(
            {
                **common,
                "event": "self_evolution_task_assessed",
                "completed_count": completed_count,
                "task_family_key": "synthetic_family",
                "source_task_id_redacted": True,
                "control_source": "same_run_fresh",
                "control_outcome": control_outcome,
                "control_outcome_source": "audited_outcome",
                "candidate_outcome": candidate_outcome,
                "candidate_outcome_source": "audited_outcome",
                "outcome_delta": outcome_delta,
                "candidate_success_flip": bool(
                    candidate_outcome == 1.0
                    and control_outcome < 1.0
                    and outcome_delta > 0.0
                ),
            }
        )
    (candidate_dir / "scenario_tool_selection.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in selection_rows),
        encoding="utf-8",
    )
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in feedback_rows),
        encoding="utf-8",
    )
    registry_path = registry_dir / "registry_manifest.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["tools"]["helper"]["birth_scenario"] = (
        "post_deployment_repair:synthetic_family"
    )
    _write_json(registry_path, registry)
    return candidate_dir, registry_dir


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"acknowledgement_status": None}, "unacknowledged"),
        ({"pending": True}, "pending lifecycle"),
        ({"canary": True}, "open repaired-tool canaries"),
        ({"retired": False}, "unresolved affected tools active"),
        ({"acknowledgement_status": "canary_pending"}, "nonterminal"),
    ],
)
def test_lifecycle_verifier_fails_closed(
    tmp_path: Path,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path, **kwargs)

    with pytest.raises(ValueError, match=message):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_accepts_terminal_retired_disposition(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)

    report = publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)

    assert report["repair_request_count"] == 1
    assert report["pending_repair_request_count"] == 0
    assert report["open_canary_count"] == 0
    assert report["open_repair_transaction_count"] == 0
    assert report["active_unresolved_tool_count"] == 0


def test_lifecycle_verifier_accepts_independently_proven_promotion(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _promoted_lifecycle_artifacts(tmp_path)

    report = publication_verifier._verify_lifecycle_closed(
        candidate_dir,
        registry_dir,
    )

    assert report["verified_promoted_canary_count"] == 1
    assert report["repair_acknowledgement_count"] == 2


def test_lifecycle_verifier_requires_ordered_canary_transition(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _promoted_lifecycle_artifacts(tmp_path)
    acknowledgement_path = (
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    promoted = json.loads(
        acknowledgement_path.read_text(encoding="utf-8").splitlines()[-1]
    )
    acknowledgement_path.write_text(json.dumps(promoted) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ordered canary_pending -> promoted"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_promotion_hidden_by_later_acknowledgement(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _promoted_lifecycle_artifacts(tmp_path)
    acknowledgement_path = (
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    promoted = json.loads(
        acknowledgement_path.read_text(encoding="utf-8").splitlines()[-1]
    )
    promoted["status"] = "rolled_back"
    with acknowledgement_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(promoted) + "\n")

    with pytest.raises(ValueError, match="ordered canary_pending -> promoted"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


@pytest.mark.parametrize(
    "corruption",
    [
        "too_few_calls",
        "wrong_family",
        "multiple_generated_calls",
        "wrong_version",
        "too_few_exact_outcomes",
        "audited_regression",
        "no_fresh_control_flip",
    ],
)
def test_lifecycle_verifier_recomputes_promoted_canary_evidence(
    tmp_path: Path,
    corruption: str,
) -> None:
    candidate_dir, registry_dir = _promoted_lifecycle_artifacts(tmp_path)
    selection_path = candidate_dir / "scenario_tool_selection.jsonl"
    feedback_path = candidate_dir / "self_evolution_task_feedback.jsonl"
    selection_rows = [
        json.loads(line)
        for line in selection_path.read_text(encoding="utf-8").splitlines()
    ]
    feedback_rows = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
    ]

    if corruption == "too_few_calls":
        for row in (selection_rows[2], feedback_rows[2]):
            row["generated_tools_visible"] = []
            row["generated_tools_called"] = []
            row["generated_tools_attempted"] = []
            row["generated_tool_versions"] = {}
    elif corruption == "wrong_family":
        feedback_rows[0]["task_family_key"] = "different_family"
    elif corruption == "multiple_generated_calls":
        for row in (selection_rows[0], feedback_rows[0]):
            row["generated_tools_called"].append("other_helper")
            row["generated_tools_attempted"].append("other_helper")
            row["generated_tool_versions"]["other_helper"] = 1
    elif corruption == "wrong_version":
        for row in (selection_rows[0], feedback_rows[0]):
            row["generated_tool_versions"]["helper"] = 3
    elif corruption == "too_few_exact_outcomes":
        selection_rows[1]["outcome_similarity"] = 0.0
        feedback_rows[1]["control_outcome"] = 0.0
        feedback_rows[1]["candidate_outcome"] = 0.0
        feedback_rows[1]["outcome_delta"] = 0.0
        feedback_rows[1]["candidate_success_flip"] = False
    elif corruption == "audited_regression":
        feedback_rows[2]["control_outcome"] = 1.0
        feedback_rows[2]["outcome_delta"] = -1.0
    elif corruption == "no_fresh_control_flip":
        feedback_rows[0]["control_outcome"] = 1.0
        feedback_rows[0]["outcome_delta"] = 0.0
        feedback_rows[0]["candidate_success_flip"] = False
    else:  # pragma: no cover - the parametrization is exhaustive.
        raise AssertionError(corruption)

    selection_path.write_text(
        "".join(json.dumps(row) + "\n" for row in selection_rows),
        encoding="utf-8",
    )
    feedback_path.write_text(
        "".join(json.dumps(row) + "\n" for row in feedback_rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Promoted canary"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_nested_private_repair_evidence(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["public_evidence"] = {
        "called_count": 1,
        "nested": {"expected_answer": "PRIVATE_SENTINEL"},
    }
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evaluator-private evidence"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_selection_feedback_failure_drift(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    feedback_path = candidate_dir / "self_evolution_task_feedback.jsonl"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    feedback["generated_tools_visible"] = ["helper"]
    feedback["generated_tools_attempted"] = ["helper"]
    feedback["generated_tools_failed"] = ["helper"]
    feedback["generated_tool_versions"] = {"helper": 2}
    feedback_path.write_text(json.dumps(feedback) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="generated-tool evidence disagree"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


@pytest.mark.parametrize(
    ("called", "failed", "contract_failed", "reason"),
    [
        ([], ["helper"], [], "unresolved_generated_tool_execution_failure"),
        (
            ["helper"],
            [],
            ["helper"],
            "deterministic_public_contract_failure",
        ),
    ],
)
def test_lifecycle_verifier_requires_terminal_attributable_failure_disposition(
    tmp_path: Path,
    called: list[str],
    failed: list[str],
    contract_failed: list[str],
    reason: str,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    common = {
        "generated_tools_visible": ["helper"],
        "generated_tools_called": called,
        "generated_tools_attempted": ["helper"],
        "generated_tools_failed": failed,
        "generated_tool_contract_failures": contract_failed,
        "generated_tool_versions": {"helper": 2},
    }
    for filename in (
        "self_evolution_task_feedback.jsonl",
        "scenario_tool_selection.jsonl",
    ):
        path = candidate_dir / filename
        row = json.loads(path.read_text(encoding="utf-8"))
        row.update(common)
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="lifecycle obligations"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)

    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.update(
        {
            "repair_kind": "implementation",
            "target_task_family": "synthetic_family",
            "trigger_reason_codes": [reason],
        }
    )
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")

    report = publication_verifier._verify_lifecycle_closed(
        candidate_dir,
        registry_dir,
    )
    assert report["derived_repair_obligation_count"] == 1


def test_lifecycle_verifier_requires_applied_attributable_route_repair(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(
        tmp_path,
        request=False,
        acknowledgement_status=None,
        retired=False,
    )
    feedback_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for index in (1, 2):
        scenario = f"private_route_case_{index}"
        common = {
            "scenario": scenario,
            "generated_tools_visible": ["helper"],
            "generated_tools_called": ["helper"],
            "generated_tools_attempted": ["helper"],
            "generated_tools_failed": [],
            "generated_tool_contract_failures": [],
            "generated_tool_versions": {"helper": 2},
        }
        selection_rows.append({**common, "exception_type": None})
        feedback_rows.append(
            {
                **common,
                "event": "self_evolution_task_assessed",
                "completed_count": index,
                "task_family_key": "public_route_family",
                "source_task_id_redacted": True,
                "control_source": "same_run_fresh",
                "control_outcome": 1.0,
                "control_outcome_source": "audited_outcome",
                "candidate_outcome": 0.0,
                "candidate_outcome_source": "audited_outcome",
                "outcome_delta": -1.0,
                "candidate_success_flip": False,
                "exception_type": None,
            }
        )
    (candidate_dir / "scenario_tool_selection.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in selection_rows),
        encoding="utf-8",
    )
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in feedback_rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no durable lifecycle routing state"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)

    _write_json(
        registry_dir / "tool_lifecycle.json",
        {
            "artifact_type": "self_evolution_tool_lifecycle",
            "tool_lifecycle": {
                "helper": {
                    "tool_version": 2,
                    "decision": "needs_route_repair",
                    "repair_kind": "routing",
                    "routing_disposition": "family_suppression_active",
                    "route_repair_families": ["public_route_family"],
                }
            },
        },
    )
    report = publication_verifier._verify_lifecycle_closed(
        candidate_dir,
        registry_dir,
    )
    assert report["derived_repair_obligation_count"] == 1
    assert report["verified_route_repair_count"] == 1


def test_lifecycle_verifier_requires_metadata_repair_after_nonadoption_threshold(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    feedback_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for index in range(publication_verifier.LIFECYCLE_METADATA_VISIBLE_THRESHOLD):
        common = {
            "scenario": f"synthetic_task_{index}",
            "generated_tools_visible": ["helper"],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
            "generated_tool_contract_failures": [],
            "generated_tool_versions": {"helper": 2},
        }
        selection_rows.append(dict(common))
        feedback_rows.append(
            {
                **common,
                "event": "self_evolution_task_assessed",
                "task_family_key": "synthetic_family",
                "source_task_id_redacted": True,
            }
        )
    (candidate_dir / "scenario_tool_selection.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in selection_rows),
        encoding="utf-8",
    )
    (candidate_dir / "self_evolution_task_feedback.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in feedback_rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lifecycle obligations"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)

    _mark_lifecycle_request_as_metadata(candidate_dir)
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.update(
        {
            "repair_kind": "metadata",
            "target_task_family": "synthetic_family",
            "trigger_reason_codes": ["visible_repeatedly_without_adoption"],
        }
    )
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")

    report = publication_verifier._verify_lifecycle_closed(
        candidate_dir,
        registry_dir,
    )
    assert report["derived_repair_obligation_count"] == 1


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_proof",
        "replacement_hash_changed",
        "false_preservation_claim",
        "malformed_source_hash",
        "registry_hash_changed",
    ],
)
def test_lifecycle_verifier_rejects_metadata_implementation_proof_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    _mark_lifecycle_request_as_metadata(candidate_dir)
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    acknowledgement_path = (
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    request = json.loads(request_path.read_text(encoding="utf-8"))
    acknowledgement = json.loads(acknowledgement_path.read_text(encoding="utf-8"))
    proof = acknowledgement["implementation_proof"]
    if corruption == "missing_proof":
        acknowledgement.pop("implementation_proof")
    elif corruption == "replacement_hash_changed":
        proof["replacement_activated"] = True
        proof["replacement_code_hash"] = "b" * 64
        proof["implementation_preserved"] = False
    elif corruption == "false_preservation_claim":
        proof["implementation_preserved"] = False
    elif corruption == "malformed_source_hash":
        request["source_code_hash"] = "not-a-sha256"
    else:
        proof["replacement_activated"] = True
        proof["replacement_code_hash"] = "a" * 64
        registry_path = registry_dir / "registry_manifest.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["tools"]["helper"]["code_hash"] = "b" * 64
        _write_json(registry_path, registry)
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
    acknowledgement_path.write_text(
        json.dumps(acknowledgement) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source|preserve|registry code hash"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_wrong_tool_or_unhandled_request(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    acknowledgement_path = (
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    acknowledgement = json.loads(acknowledgement_path.read_text(encoding="utf-8"))
    acknowledgement["tool_name"] = "different_helper"
    acknowledgement_path.write_text(
        json.dumps(acknowledgement) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="wrong tool"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)

    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path / "unhandled")
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["handled_repair_request_ids"] = []
    _write_json(state_path, state)
    with pytest.raises(ValueError, match="missing from state"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_requires_current_promoted_tool_to_be_active(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _promoted_lifecycle_artifacts(tmp_path, retired=True)

    with pytest.raises(ValueError, match="promoted tool as retired"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_open_repair_transaction(tmp_path: Path) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(tmp_path)
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_transactions_by_tool"] = {
        "helper": {"request_id": "request-1", "phase": "canary_prepared"}
    }
    _write_json(state_path, state)

    with pytest.raises(ValueError, match="open lifecycle repair transactions"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_rejects_active_repair_without_promoted_ack(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(
        tmp_path,
        request=False,
        acknowledgement_status=None,
        retired=False,
    )
    registry_path = registry_dir / "registry_manifest.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["tools"]["helper"]["birth_scenario"] = (
        "post_deployment_repair:record_safety"
    )
    _write_json(registry_path, registry)

    with pytest.raises(ValueError, match="without matching promoted acknowledgements"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_lifecycle_verifier_treats_missing_retired_flag_as_active(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _lifecycle_artifacts(
        tmp_path,
        request=False,
        acknowledgement_status=None,
    )
    registry_path = registry_dir / "registry_manifest.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["tools"]["helper"].pop("retired")
    registry["tools"]["helper"]["birth_scenario"] = (
        "post_deployment_repair:record_safety"
    )
    _write_json(registry_path, registry)

    with pytest.raises(ValueError, match="without matching promoted acknowledgements"):
        publication_verifier._verify_lifecycle_closed(candidate_dir, registry_dir)


def test_pinned_publication_benchmark_requires_exactly_1032_tasks(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="requires exactly 1032 tasks per arm"):
        verify_run(
            tmp_path,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
        )


def test_verifier_requires_exact_pinned_evaluator_hashes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    observed = publication_verifier.outcome_evaluator_manifest()
    monkeypatch.setattr(
        publication_verifier,
        "outcome_evaluator_manifest",
        lambda: {**observed, "contract_sha256": "0" * 64},
    )

    with pytest.raises(ValueError, match="exact pinned publication evaluator"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


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
    assert result["trajectory_audit_count"] == {"control": 2, "candidate": 2}
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
    assert result["matched_policy_runtimes"] == {
        "control_condition": publication_verifier.MATCHED_CONTROL_CONDITION,
        "control_agent_runtime": publication_verifier.SAGE_WRAPPED_AGENT_RUNTIME,
        "candidate_agent_runtime": publication_verifier.SAGE_WRAPPED_AGENT_RUNTIME,
        "actor_selection_mode": "policy",
    }
    assert result["git_commit"] == TEST_GIT_COMMIT
    assert result["git_tree"] == TEST_GIT_TREE
    assert result["python_version"] == "3.12.7"
    assert result["platform_system"] == "Darwin"
    assert result["platform_machine"] == "arm64"
    assert result["external_distribution_count"] == 108
    assert len(result["external_distribution_sha256"]) == 64


@pytest.mark.parametrize("arm", ("control", "candidate"))
def test_verifier_requires_complete_trajectory_for_every_task(
    tmp_path: Path,
    arm: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    execution_path = (
        Path(protocol[f"{arm}_dir"])
        / "trajectories"
        / "task_b"
        / "execution_context.json"
    )
    execution_path.unlink()

    with pytest.raises(ValueError, match="missing complete trajectory artifacts"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_trajectory_backed_v9_outcome_corruption(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["outcome_check_count"] = 2
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="independently recomputed audited v9"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_execution_context_outcome_corruption(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    execution_path = (
        Path(protocol["candidate_dir"])
        / "trajectories"
        / "task_a"
        / "execution_context.json"
    )
    execution_context = json.loads(execution_path.read_text(encoding="utf-8"))
    execution_context["tool_allow_list"] = [f"{_TEST_OUTCOME_MARKER}0.25"]
    _write_json(execution_path, execution_context)

    with pytest.raises(ValueError, match="independently recomputed audited v9"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_trajectory_backed_v1_outcome_corruption(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["control_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["online_feedback_outcome_similarity"] = 1.0
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="paper-era v1 outcome"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_noncanonical_trajectory_conversation(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    conversation_path = (
        Path(protocol["candidate_dir"])
        / "trajectories"
        / "task_a"
        / "conversation.json"
    )
    conversation_path.write_text(
        json.dumps([{"role": "assistant", "content": "tampered"}]) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonical serialization"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_lifecycle_verifier_rejects_selection_omitted_from_raw_trajectory(
    tmp_path: Path,
) -> None:
    candidate_dir, _ = _lifecycle_artifacts(tmp_path)
    trajectory_evidence = {
        "synthetic_task": {
            "generated_tools_visible": ("helper",),
            "generated_tools_called": (),
            "generated_tools_attempted": (),
            "generated_tools_failed": (),
        }
    }

    with pytest.raises(ValueError, match="disagrees with raw trajectory"):
        publication_verifier._paired_lifecycle_evidence_rows(
            candidate_dir,
            trajectory_evidence=trajectory_evidence,
        )


def test_trajectory_reconstructs_generated_attempt_and_failure() -> None:
    serialized_context = {
        "tool_allow_list": ["native_tool", "helper"],
        "tool_deny_list": None,
        "_dbs": {
            "SANDBOX": [
                {
                    "sender": "AGENT",
                    "recipient": "EXECUTION_ENVIRONMENT",
                    "openai_function_name": "helper",
                    "tool_call_exception": None,
                },
                {
                    "sender": "EXECUTION_ENVIRONMENT",
                    "recipient": "AGENT",
                    "openai_function_name": "helper",
                    "tool_call_exception": "ValueError: invalid input",
                },
            ]
        },
    }
    conversation = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"function": {"name": "helper", "arguments": "{}"}}],
        },
        {
            "role": "tool",
            "name": "helper",
            "content": "ValueError: invalid input",
        },
    ]

    assert publication_verifier._trajectory_generated_tool_evidence(
        serialized_context,
        conversation,
        generated_tool_names={"helper"},
        scenario_name="synthetic_task",
    ) == {
        "generated_tools_visible": ("helper",),
        "generated_tools_attempted": ("helper",),
        "generated_tools_failed": ("helper",),
        "generated_tools_called": (),
    }


def test_real_scenario_trajectory_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario_name = "search_phone_number_with_name"
    scenario = _REAL_LOAD_PUBLICATION_SCENARIOS([scenario_name])[scenario_name]
    execution_context = copy.deepcopy(scenario.starting_context)
    recomputed = _REAL_RECOMPUTE_TRAJECTORY(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )
    run_dir = tmp_path / "real_trajectory"
    trajectory_dir = run_dir / "trajectories" / scenario_name
    _write_json(
        trajectory_dir / "execution_context.json",
        execution_context.to_dict(serialize_console=False),
    )
    (trajectory_dir / "conversation.json").write_text(
        json.dumps(recomputed["conversation"]) + "\n",
        encoding="utf-8",
    )
    row = json.loads(json.dumps(recomputed["audited_outcome"]))
    row["online_feedback_outcome_similarity"] = recomputed["paper_outcome"].get(
        "outcome_similarity"
    )
    row["online_feedback_evaluator_version"] = (
        publication_verifier.ONLINE_FEEDBACK_EVALUATOR_VERSION
    )
    monkeypatch.setattr(
        publication_verifier,
        "_load_publication_scenarios",
        _REAL_LOAD_PUBLICATION_SCENARIOS,
    )
    monkeypatch.setattr(
        publication_verifier,
        "_independently_recompute_trajectory",
        _REAL_RECOMPUTE_TRAJECTORY,
    )

    evidence = publication_verifier._verify_trajectory_artifacts(
        run_dir,
        rows={scenario_name: row},
        order=[scenario_name],
        arm="candidate",
        generated_tool_names=set(),
    )

    assert evidence[scenario_name] == {
        "generated_tools_visible": (),
        "generated_tools_attempted": (),
        "generated_tools_failed": (),
        "generated_tools_called": (),
    }


@pytest.mark.parametrize("arm", ("control", "candidate"))
def test_verifier_rejects_native_or_unrecorded_arm_runtime(
    tmp_path: Path,
    arm: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    run_manifest_path = Path(protocol[f"{arm}_dir"]) / "sage_ts_run_manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    run_manifest["agent_runtime"] = "toolsandbox_native"
    _write_json(run_manifest_path, run_manifest)

    with pytest.raises(ValueError, match="matched SAGE policy wrapper"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_control_condition_label_drift(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["control_condition"] = "pure_toolsandbox"
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="control_condition"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_any_scenario_transform_failure(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    failure_path = Path(protocol["candidate_dir"]) / (
        "scenario_transform_failures.jsonl"
    )
    failure_path.write_text(
        json.dumps(
            {
                "event": "scenario_transform_failed",
                "scenario": "task_a",
                "error": "Traceback ...",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="scenario transformation failures"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_nonempty_online_registry_start(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    inventory = [
        {
            "path": "tool_lifecycle.json",
            "kind": "file",
            "sha256": "3" * 64,
        }
    ]
    snapshot = protocol["registry_gate_snapshot"]
    snapshot.update(
        {
            "registry_directory_existed_before_run": True,
            "registry_inventory_before_run": inventory,
            "registry_inventory_count_before_run": 1,
            "registry_inventory_sha256": hashlib.sha256(
                json.dumps(
                    inventory,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
    )
    _write_json(protocol_path, protocol)
    _write_json(
        run_root / "registry_gate" / "registry_gate_snapshot.json",
        snapshot,
    )

    with pytest.raises(ValueError, match="did not start exactly empty"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("protocol_gate_passed", False, "protocol_gate_passed"),
        (
            "protocol_gate_reasons",
            ["runtime_exceptions_present"],
            "protocol_gate_reasons",
        ),
    ],
)
def test_verifier_rejects_failed_protocol_manifest_gate(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol[field] = value
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_paired_runtime_exception_gate(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    comparison_path = run_root / "paired_comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["protocol_gate_passed"] = False
    comparison["protocol_gate_reasons"] = ["runtime_exceptions_present"]
    comparison["runtime_exception_count"] = 1
    comparison["control"]["exception_count"] = 1
    _write_json(comparison_path, comparison)

    with pytest.raises(ValueError, match="protocol gate did not pass"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_campaign_inclusion_accepts_integrity_valid_performance_failure(
    tmp_path: Path,
) -> None:
    run_root = _fresh_run(tmp_path)
    performance_reasons = [
        "non_positive_outcome_delta",
        "confirmation_outcome_delta_below_0_08",
    ]
    for filename in ("protocol_manifest.json", "paired_comparison.json"):
        path = run_root / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["publication_gate_purpose"] = (
            publication_verifier.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
        )
        payload["performance_gate_passed"] = False
        payload["performance_gate_reasons"] = performance_reasons
        _write_json(path, payload)

    result = verify_run(
        run_root.parent,
        expected_tasks=2,
        expect_reflection="same-run-fresh",
        gate_purpose=(publication_verifier.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION),
        **_verification_pins(run_root),
    )

    assert result["status"] == "pass"
    assert result["publication_gate_purpose"] == "campaign-inclusion"
    assert result["performance_gate_passed"] is False
    assert result["performance_gate_reasons"] == performance_reasons


def test_release_sample_rejects_recorded_performance_failure(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    for filename in ("protocol_manifest.json", "paired_comparison.json"):
        path = run_root / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["performance_gate_passed"] = False
        payload["performance_gate_reasons"] = ["non_positive_outcome_delta"]
        _write_json(path, payload)

    with pytest.raises(ValueError, match="Release-sample performance gate"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_gate_purpose_mismatch(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)

    with pytest.raises(ValueError, match="publication_gate_purpose"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            gate_purpose=(
                publication_verifier.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
            ),
            **_verification_pins(run_root),
        )


def test_verifier_rejects_runtime_exception_result_row(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["control_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["exception_type"] = "AssertionError"
    summary["per_scenario_results"][0]["traceback"] = "Traceback ..."
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="contains a runtime exception"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_missing_final_online_registry(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    (Path(protocol["registry_dir"]) / "registry_manifest.json").unlink()

    with pytest.raises(ValueError, match="missing its final registry manifest"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_final_online_registry_digest_drift(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    _write_json(
        Path(protocol["registry_dir"]) / "registry_manifest.json",
        {"schema_version": 1, "tools": {"tampered": {}}},
    )

    with pytest.raises(ValueError, match="does not match the protocol digest"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered", "message"),
    [
        ("candidate_score", 0.5, "Reflection candidate score mismatch"),
        ("score_delta", 0.0, "Reflection score delta mismatch"),
        ("candidate_outcome", 0.0, "Reflection candidate outcome mismatch"),
        (
            "candidate_outcome_source",
            "unavailable",
            "Reflection candidate outcome source mismatch",
        ),
        ("outcome_delta", 0.0, "Reflection outcome delta mismatch"),
    ],
)
def test_verifier_rejects_tampered_candidate_reflection_signal(
    tmp_path: Path,
    field: str,
    tampered: object,
    message: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    feedback_path = (
        Path(protocol["candidate_dir"]) / "self_evolution_task_feedback.jsonl"
    )
    feedback = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
    ]
    feedback[0][field] = tampered
    feedback_path.write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_reflection_completed_count_drift(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    feedback_path = (
        Path(protocol["candidate_dir"]) / "self_evolution_task_feedback.jsonl"
    )
    feedback = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
    ]
    feedback[1]["completed_count"] = 3
    feedback_path.write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Reflection completed_count mismatch"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


def test_verifier_rejects_reflection_task_reordering(tmp_path: Path) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    feedback_path = (
        Path(protocol["candidate_dir"]) / "self_evolution_task_feedback.jsonl"
    )
    feedback = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
    ][::-1]
    for completed_count, row in enumerate(feedback, start=1):
        row["completed_count"] = completed_count
    feedback_path.write_text(
        "".join(json.dumps(row) + "\n" for row in feedback),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Reflection task order"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered"),
    [
        ("outcome_evaluator_version", "sage_outcome_contracts_v7"),
        ("outcome_evaluator_contract_sha256", "0" * 64),
        ("outcome_evaluator_source_sha256", "f" * 64),
    ],
)
@pytest.mark.parametrize("arm", ("control", "candidate"))
def test_verifier_rejects_scored_row_outcome_evaluator_identity_drift(
    tmp_path: Path,
    field: str,
    tampered: str,
    arm: str,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol[f"{arm}_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0][field] = tampered
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="outcome evaluator field"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    "invalid_outcome",
    (None, float("nan"), float("inf"), -0.01, 1.01),
)
def test_verifier_rejects_nonfinite_or_missing_audited_outcome_even_with_legacy_value(
    tmp_path: Path,
    invalid_outcome: float | None,
) -> None:
    run_root = _fresh_run(tmp_path)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["outcome_similarity"] = invalid_outcome
    summary["per_scenario_results"][0]["online_feedback_outcome_similarity"] = 1.0
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="missing a finite audited outcome"):
        verify_run(
            run_root.parent,
            expected_tasks=2,
            expect_reflection="same-run-fresh",
            **_verification_pins(run_root),
        )


@pytest.mark.parametrize(
    ("field", "tampered"),
    [
        ("scenario_count", 3),
        ("outcome_scenario_count", 0),
        ("control_mean_outcome_similarity", 0.0),
        ("candidate_mean_outcome_similarity", 0.0),
        ("mean_outcome_similarity_delta", 0.0),
        ("outcome_gain_count", 0),
        ("outcome_regression_count", 1),
        ("outcome_preserved_count", 0),
    ],
)
def test_verifier_rejects_paired_outcome_aggregate_drift(
    tmp_path: Path,
    field: str,
    tampered: int | float,
) -> None:
    run_root = _fresh_run(tmp_path)
    comparison_path = run_root / "paired_comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison[field] = tampered
    _write_json(comparison_path, comparison)

    with pytest.raises(ValueError, match="Paired comparison outcome field"):
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
    protocol["candidate_generated_tools_enabled"] = False
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
    publication_python = tmp_path / ".venv-publication" / "bin" / "python"
    publication_python.parent.mkdir(parents=True)
    publication_python.write_text("#!/bin/sh\n", encoding="utf-8")
    publication_python.chmod(0o755)
    manifest = {
        "campaign_id": "fresh_campaign",
        "fixed_toolsandbox_timestamp": 123,
        "benchmark_manifest": "benchmark.json",
        "external_fixture": {
            "path": "fixtures/rapid.json",
            "sha256": "fixture-sha",
            "mode": "read_only",
        },
        "configuration_identity": {
            "runtime_digest": "runtime-sha",
            "generation_settings_digest": "generation-sha",
            "prompt_policy_digest": "prompt-policy-sha",
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
        "campaign-inclusion",
    ]
    assert env["CONTROL_CACHE"] == "off"
    assert env["SAGE_BENCHMARK_MANIFEST"] == str(tmp_path / "benchmark.json")
    assert env["TOOLSANDBOX_RAPID_CACHE_MODE"] == "read_only"
    assert env["TOOLSANDBOX_RAPID_CACHE_PATH"] == str(tmp_path / "fixtures/rapid.json")
    assert env["SAGE_TS_RUNTIME_DIGEST"] == "runtime-sha"
    assert env["SAGE_TS_GENERATION_SETTINGS_DIGEST"] == "generation-sha"
    assert env["SAGE_TS_PROMPT_POLICY_DIGEST"] == "prompt-policy-sha"
    assert env["PATH"].split(os.pathsep)[0] == str(publication_python.parent)
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
