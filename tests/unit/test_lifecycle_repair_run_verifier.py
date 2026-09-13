"""Focused lifecycle-closure checks for the development cohort verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import verify_lifecycle_repair_run

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _zero_usage() -> dict[str, object]:
    return {
        "llm_usage_recorded": False,
        "llm_call_count": 0,
        "llm_live_call_count": 0,
        "llm_cached_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_provider_cached_prompt_tokens": 0,
        "llm_provider_cached_prompt_call_count": 0,
        "llm_provider_cached_prompt_tokens_available_count": 0,
        "llm_completion_tokens": 0,
        "llm_total_tokens": 0,
        "llm_usage_available_count": 0,
    }


def _write_zero_usage_artifacts(run_dir: Path) -> None:
    _write_jsonl(run_dir / "llm_usage_events.jsonl", [])
    _write_json(
        run_dir / "llm_usage_summary.json",
        {
            **_zero_usage(),
            "llm_usage_by_source": {},
            "scenario_count_with_usage": 0,
            "schema_version": 2,
            "token_source": "openai_chat_completion_usage",
        },
    )


def _result_row(name: str, outcome: float) -> dict[str, object]:
    evaluator = verify_lifecycle_repair_run.outcome_evaluator_manifest()
    if "insufficient_information" in name:
        exact = outcome == 1.0
        checks: list[dict[str, object]] = [
            {
                "kind": "insufficient_information_contract",
                "included": True,
                "score": outcome,
                "outcome_basis": (
                    "targeted_abstention_or_clarification" if exact else "none"
                ),
                "forbidden_action_diagnostics": (
                    []
                    if exact
                    else [
                        {
                            "tool_name": "remove_contact",
                            "evidence": "agent_execution_request",
                        }
                    ]
                ),
            }
        ]
    else:
        checks = [{"kind": "state", "included": True, "score": outcome}]
    return {
        "name": name,
        "outcome_similarity": outcome,
        "outcome_forbidden_action_detected": outcome != 1.0,
        "outcome_checks": checks,
        "outcome_evaluator_version": evaluator["version"],
        "outcome_evaluator_contract_sha256": evaluator["contract_sha256"],
        "outcome_evaluator_source_sha256": evaluator["source_sha256"],
        "exception_type": None,
        "traceback": None,
        **_zero_usage(),
    }


def _development_artifacts(
    tmp_path: Path, cohort: str
) -> tuple[Path, Path, Path, Path]:
    manifest_path = (
        REPOSITORY_ROOT
        / "docs"
        / "sage_protocol"
        / "manifests"
        / f"lifecycle_repair_{cohort}.json"
    )
    benchmark = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = verify_lifecycle_repair_run.COHORT_SPECS[benchmark["manifest_type"]]
    order = tuple(spec["order"])
    safe_names = tuple(spec["roles"][spec["safe_role"]])
    preservation_names = tuple(spec["roles"]["preservation"])
    trigger_name = safe_names[0]
    request_id = "prepare-safe-v1-after-1"

    search_root = tmp_path / cohort
    run_root = search_root / "run"
    control_dir = run_root / "control"
    candidate_dir = run_root / "candidate"
    registry_dir = run_root / "registry"
    receipt_path = run_root / "dashboard_open_receipt.json"

    candidate_rows = [
        _result_row(name, 0.0 if name == trigger_name else 1.0) for name in order
    ]
    control_rows = [
        _result_row(name, 0.0 if name in safe_names else 1.0) for name in order
    ]
    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": candidate_rows},
    )
    _write_json(
        control_dir / "result_summary.json",
        {"per_scenario_results": control_rows},
    )
    _write_zero_usage_artifacts(candidate_dir)
    _write_zero_usage_artifacts(control_dir)

    selection_rows: list[dict[str, object]] = []
    feedback_rows: list[dict[str, object]] = []
    for completed_count, name in enumerate(order, start=1):
        safe = name in safe_names
        visible = [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL] if safe else []
        selection_rows.append(
            {
                "scenario": name,
                "generated_tools_visible": visible,
                "generated_tools_called": visible,
            }
        )
        feedback_rows.append(
            {
                "scenario": name,
                "completed_count": completed_count,
                "candidate_outcome": 0.0 if name == trigger_name else 1.0,
                "generated_tools_visible": visible,
                "generated_tools_called": visible,
                "generated_tool_versions": (
                    {
                        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: (
                            1 if name == trigger_name else 2
                        )
                    }
                    if safe
                    else {}
                ),
                "generated_tool_contract_failures": (
                    [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
                    if name == trigger_name
                    else []
                ),
                "post_deployment_repair_request_ids": (
                    [request_id] if name == trigger_name else []
                ),
            }
        )
    _write_jsonl(candidate_dir / "scenario_tool_selection.jsonl", selection_rows)
    _write_jsonl(candidate_dir / "self_evolution_task_feedback.jsonl", feedback_rows)
    _write_jsonl(
        candidate_dir / "self_evolution_tool_repair_requests.jsonl",
        [
            {
                "request_id": request_id,
                "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                "source_tool_version": 1,
                "repair_kind": "implementation",
                "trigger_reason_codes": ["deterministic_public_contract_failure"],
                "trigger_completed_count": 1,
                "eligible_from_completed_count": 2,
                "future_tasks_only": True,
                "triggering_task_replay_allowed": False,
                "public_evidence": {
                    "called_count": 1,
                    "contract_failure_count": 1,
                    "failed_count": 0,
                },
            }
        ],
    )
    _write_jsonl(
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl",
        [
            {
                "request_id": request_id,
                "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                "new_version": 2,
                "status": "canary_pending",
            },
            {
                "request_id": request_id,
                "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                "new_version": 2,
                "status": "promoted",
            },
        ],
    )
    _write_json(
        candidate_dir / "post_deployment_repair_state.json",
        {
            "schema_version": 1,
            "pending_repair_requests": [],
            "handled_repair_request_ids": [request_id],
            "canary_state_by_tool": {},
            "repair_transactions_by_tool": {},
        },
    )
    _write_jsonl(
        candidate_dir / "sage_run_events.jsonl",
        [
            {
                "event": "post_deployment_tool_repair_accepted",
                "request_id": request_id,
                "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                "source_tool_version": 1,
                "new_tool_version": 2,
                "triggering_task_replayed": False,
            }
        ],
    )
    registry_manifest_path = registry_dir / "registry_manifest.json"
    _write_json(
        registry_manifest_path,
        {
            "tools": {
                verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: {
                    "version": 2,
                    "retired": False,
                    "birth_scenario": "post_deployment_repair:contact",
                }
            }
        },
    )
    registry_sha256 = hashlib.sha256(registry_manifest_path.read_bytes()).hexdigest()
    dashboard_path = run_root / "dashboard" / "task_compare.html"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("<!doctype html><title>Task Compare</title>\n")
    dashboard_url = "http://127.0.0.1:63105/dashboard/task_compare.html"
    _write_json(
        receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "fresh_control_vs_policy_sage",
            "path": str(dashboard_path.resolve()),
            "url": dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "dashboard_server_protocol": (
                verify_lifecycle_repair_run.DASHBOARD_SERVER_PROTOCOL
            ),
            "dashboard_server_root": str(run_root.resolve()),
            "opened_before_model_processes": True,
            "opened_monotonic_ns": 100,
        },
    )
    arm_fields = {
        "control": {
            "status": "complete",
            "process_pid": 1001,
            "started_at": "2026-09-13T00:00:01+00:00",
            "completed_at": "2026-09-13T00:00:04+00:00",
            "started_monotonic_ns": 200,
            "completed_monotonic_ns": 500,
        },
        "candidate": {
            "status": "complete",
            "process_pid": 1002,
            "started_at": "2026-09-13T00:00:02+00:00",
            "completed_at": "2026-09-13T00:00:05+00:00",
            "started_monotonic_ns": 300,
            "completed_monotonic_ns": 600,
        },
    }
    for arm, status in arm_fields.items():
        _write_json(run_root / f"{arm}_arm_status.json", status)
    parallel_execution = {
        "unit": "isolated_child_process",
        "arms": arm_fields,
        "positive_overlap_asserted": True,
        "overlap_monotonic_ns": 200,
        "overlap_seconds": 2e-7,
    }
    fault_fixture = (
        REPOSITORY_ROOT
        / "docs"
        / "sage_protocol"
        / "fixtures"
        / "historical_faulty_safe_action_registry.json"
    )
    fault_snapshot_path = (
        run_root / "registry_gate" / "registry_manifest_before_run.json"
    )
    fault_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    fault_snapshot_path.write_bytes(fault_fixture.read_bytes())
    _write_json(
        run_root / "paired_comparison.json",
        {
            "runtime_exception_count": 0,
            "candidate_stopped_early": False,
            "control_cache": {
                "mode": "off",
                "cache_accessed": False,
                "cached_control_tasks": 0,
                "fresh_control_tasks": len(order),
            },
        },
    )
    _write_json(
        run_root / "control_cache_report.json",
        {
            "mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": len(order),
            "cache_accessed": False,
            "fresh_control_enforced": True,
        },
    )
    _write_json(
        run_root / "protocol_manifest.json",
        {
            "manifest_type": benchmark["manifest_type"],
            "benchmark_manifest_path": str(manifest_path),
            "benchmark_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "scenario_order_sha256": spec["order_sha256"],
            "publication_gate_purpose": "development-diagnostic",
            "scenario_count": len(order),
            "fresh_control_required": True,
            "control_cache_mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": len(order),
            "openai_response_cache_enabled": False,
            "openai_response_cache_mode": "off",
            "sage_task_cache_enabled": False,
            "cross_run_failure_memory_enabled": False,
            "parallel_arms": True,
            "parallel_arm_execution": parallel_execution,
            "reporting_outcome_evaluator": (
                verify_lifecycle_repair_run.outcome_evaluator_manifest()
            ),
            "control_dir": str(control_dir),
            "candidate_dir": str(candidate_dir),
            "registry_dir": str(registry_dir),
            "registry_manifest_digest_after_run": registry_sha256,
            "registry_gate_snapshot": {
                "manifest_existed_before_run": True,
                "manifest_digest_before_run": (
                    verify_lifecycle_repair_run.LIFECYCLE_FAULT_FIXTURE_SHA256
                ),
                "snapshot_path": str(fault_snapshot_path),
            },
            "dashboard_open_receipt_path": str(receipt_path),
            "dashboard_task_compare_url": dashboard_url,
        },
    )
    assert set(preservation_names).isdisjoint(safe_names)
    return search_root, run_root, candidate_dir, manifest_path


def test_development_outcome_ignores_legacy_feedback() -> None:
    assert (
        verify_lifecycle_repair_run._outcome(
            {
                "outcome_similarity": None,
                "online_feedback_outcome_similarity": 1.0,
            }
        )
        is None
    )


def _artifacts(tmp_path: Path, *, active: bool = False) -> tuple[Path, Path]:
    candidate_dir = tmp_path / "candidate"
    registry_dir = tmp_path / "registry"
    request = {
        "request_id": "request-1",
        "tool_name": "helper",
        "source_tool_version": 2,
    }
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "self_evolution_tool_repair_requests.jsonl").write_text(
        json.dumps(request) + "\n", encoding="utf-8"
    )
    (candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl").write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "tool_name": "helper",
                "new_version": 2,
                "status": "rolled_back",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        candidate_dir / "post_deployment_repair_state.json",
        {
            "schema_version": 1,
            "pending_repair_requests": [],
            "handled_repair_request_ids": ["request-1"],
            "canary_state_by_tool": {},
            "repair_transactions_by_tool": {},
        },
    )
    _write_json(
        registry_dir / "registry_manifest.json",
        {"tools": {"helper": {"version": 2, "retired": not active}}},
    )
    return candidate_dir, registry_dir


def test_development_lifecycle_integrity_reports_closed_state(tmp_path: Path) -> None:
    candidate_dir, registry_dir = _artifacts(tmp_path)

    report = verify_lifecycle_repair_run._lifecycle_integrity(
        candidate_dir, registry_dir
    )

    assert report["unacknowledged_repair_request_ids"] == []
    assert report["nonterminal_repair_request_ids"] == []
    assert report["pending_repair_request_count"] == 0
    assert report["open_canary_count"] == 0
    assert report["open_repair_transaction_count"] == 0
    assert report["unhandled_repair_request_ids"] == []
    assert report["orphaned_handled_repair_request_ids"] == []
    assert report["active_unresolved_tools"] == []
    assert report["active_repairs_without_promotion"] == []


def test_development_lifecycle_integrity_reports_active_failed_tool(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _artifacts(tmp_path, active=True)

    report = verify_lifecycle_repair_run._lifecycle_integrity(
        candidate_dir, registry_dir
    )

    assert report["active_unresolved_tools"] == ["helper:v2:request-1"]


def test_development_lifecycle_integrity_reports_open_transaction(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _artifacts(tmp_path)
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_transactions_by_tool"] = {
        "helper": {"request_id": "request-1", "phase": "canary_prepared"}
    }
    _write_json(state_path, state)

    report = verify_lifecycle_repair_run._lifecycle_integrity(
        candidate_dir, registry_dir
    )

    assert report["open_repair_transaction_count"] == 1


@pytest.mark.parametrize(
    ("handled", "unhandled", "orphaned"),
    [
        ([], ["request-1"], []),
        (["request-1", "orphan-request"], [], ["orphan-request"]),
    ],
)
def test_development_lifecycle_integrity_requires_exact_handled_reconciliation(
    tmp_path: Path,
    handled: list[str],
    unhandled: list[str],
    orphaned: list[str],
) -> None:
    candidate_dir, registry_dir = _artifacts(tmp_path)
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["handled_repair_request_ids"] = handled
    _write_json(state_path, state)

    report = verify_lifecycle_repair_run._lifecycle_integrity(
        candidate_dir, registry_dir
    )

    assert report["unhandled_repair_request_ids"] == unhandled
    assert report["orphaned_handled_repair_request_ids"] == orphaned


def test_development_lifecycle_integrity_reports_active_repair_without_promotion(
    tmp_path: Path,
) -> None:
    candidate_dir, registry_dir = _artifacts(tmp_path)
    _write_json(
        registry_dir / "registry_manifest.json",
        {
            "tools": {
                "helper": {"version": 2, "retired": True},
                "unpromoted_helper": {
                    "version": 3,
                    "retired": False,
                    "birth_scenario": "post_deployment_repair:contact",
                },
            }
        },
    )

    report = verify_lifecycle_repair_run._lifecycle_integrity(
        candidate_dir, registry_dir
    )

    assert report["active_repairs_without_promotion"] == ["unpromoted_helper:v3"]


@pytest.mark.parametrize("cohort", ["dev10", "dev30"])
def test_predeclared_development_cohort_passes_with_real_artifact_fields(
    tmp_path: Path, cohort: str
) -> None:
    search_root, _, _, _ = _development_artifacts(tmp_path, cohort)

    report = verify_lifecycle_repair_run.verify(
        search_root, 10 if cohort == "dev10" else 30
    )

    assert report["status"] == "pass"
    assert report["historical_v1_observed_failure_proved"] is True
    assert report["repaired_version_future_success_flip_count"] >= 1


def test_development_cohort_rejects_nonoverlapping_arm_processes(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    candidate = protocol["parallel_arm_execution"]["arms"]["candidate"]
    candidate["started_monotonic_ns"] = 700
    candidate["completed_monotonic_ns"] = 900
    _write_json(run_root / "candidate_arm_status.json", candidate)
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="do not prove overlap"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_cohort_rejects_forged_dashboard_receipt(tmp_path: Path) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    receipt_path = run_root / "dashboard_open_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["http_verified_before_open"] = False
    _write_json(receipt_path, receipt)

    with pytest.raises(ValueError, match="dashboard receipt"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_cohort_rejects_repository_response_replay_row(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    summary_path = run_root / "control" / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["llm_cached_call_count"] = 1
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="whole-response replay calls"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_cohort_rejects_cached_control_report(tmp_path: Path) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    report_path = run_root / "control_cache_report.json"
    cache_report = json.loads(report_path.read_text(encoding="utf-8"))
    cache_report["cached_control_tasks"] = 1
    cache_report["fresh_control_tasks"] = 9
    cache_report["cache_accessed"] = True
    _write_json(report_path, cache_report)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "control_cache_report_not_fully_fresh" in report["reasons"]


def test_development_cohort_rejects_tampered_initial_fault_snapshot(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    snapshot_path = run_root / "registry_gate" / "registry_manifest_before_run.json"
    snapshot_path.write_text("{}\n", encoding="utf-8")

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "pinned_historical_fault_snapshot_bytes_mismatch" in report["reasons"]


def test_development_cohort_rejects_candidate_path_outside_run(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["candidate_dir"] = str(tmp_path / "forged-candidate")
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="escapes its same-run directory"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_cohort_cannot_pass_without_lifecycle_evidence(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    for filename in (
        "self_evolution_tool_repair_requests.jsonl",
        "self_evolution_tool_repair_acknowledgements.jsonl",
        "self_evolution_task_feedback.jsonl",
        "sage_run_events.jsonl",
    ):
        (candidate_dir / filename).write_text("", encoding="utf-8")

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "historical_v1_repair_request_count_mismatch" in report["reasons"]
    assert "historical_v1_trigger_did_not_prove_observed_failure" in report["reasons"]
    assert "postdeployment_v2_acceptance_event_missing" in report["reasons"]


def test_development_cohort_cannot_pass_with_open_repair_transaction(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repair_transactions_by_tool"] = {
        "unresolved_helper": {
            "request_id": "unresolved-request",
            "phase": "canary_prepared",
        }
    }
    _write_json(state_path, state)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "open_lifecycle_repair_transactions_at_run_end" in report["reasons"]


def test_development_cohort_cannot_pass_with_unhandled_terminal_request(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["handled_repair_request_ids"] = []
    _write_json(state_path, state)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "terminal_lifecycle_requests_missing_from_handled_state" in report["reasons"]


def test_development_cohort_cannot_pass_with_active_unpromoted_repair(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    registry_path = run_root / "registry" / "registry_manifest.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["tools"]["unpromoted_helper"] = {
        "version": 3,
        "retired": False,
        "birth_scenario": "post_deployment_repair:contact",
    }
    _write_json(registry_path, registry)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["registry_manifest_digest_after_run"] = hashlib.sha256(
        registry_path.read_bytes()
    ).hexdigest()
    _write_json(protocol_path, protocol)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "active_repair_without_exact_promoted_acknowledgement" in report["reasons"]


def test_dev30_contact_gate_includes_alt_tasks(tmp_path: Path) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev30")
    summary_path = candidate_dir / "result_summary.json"
    summary = json.loads(summary_path.read_text())
    rows = summary["per_scenario_results"]
    failed = {
        "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_10_distraction_tools",
    }
    rows = [
        _result_row(str(row["name"]), 0.0) if row["name"] in failed else row
        for row in rows
    ]
    summary["per_scenario_results"] = rows
    _write_json(summary_path, summary)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["contact_repair_task_count"] == 9
    assert report["contact_exact_without_forbidden_remove_count"] == 7
    assert "contact_exact_without_forbidden_remove_gate_failed" in report["reasons"]


def test_preservation_fails_if_safe_helper_leaks_into_working_family(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    selection_path = candidate_dir / "scenario_tool_selection.jsonl"
    rows = [json.loads(line) for line in selection_path.read_text().splitlines()]
    rows[-1]["generated_tools_visible"] = [
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    ]
    rows[-1]["generated_tools_called"] = [
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    ]
    _write_jsonl(selection_path, rows)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert "preservation_exact_and_safe_helper_hidden_gate_failed" in report["reasons"]


def test_observed_before_after_gate_rejects_v1_trigger_success(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    summary_path = candidate_dir / "result_summary.json"
    summary = json.loads(summary_path.read_text())
    rows = summary["per_scenario_results"]
    rows[0] = _result_row(str(rows[0]["name"]), 1.0)
    summary["per_scenario_results"] = rows
    _write_json(summary_path, summary)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["historical_v1_trigger_outcome"] == 1.0
    assert "historical_v1_trigger_did_not_prove_observed_failure" in report["reasons"]


def test_coherent_manifest_reordering_cannot_change_the_frozen_cohort(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, manifest_path = _development_artifacts(tmp_path, "dev10")
    tampered_path = tmp_path / "tampered_dev10.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = manifest["splits"]["full_benchmark"]
    split[0], split[1] = split[1], split[0]
    tampered_names = [str(row["name"]) for row in split]
    tampered_sha256 = verify_lifecycle_repair_run._order_sha256(tampered_names)
    manifest["scenario_order_sha256"] = tampered_sha256
    _write_json(tampered_path, manifest)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["benchmark_manifest_path"] = str(tampered_path)
    protocol["benchmark_manifest_sha256"] = hashlib.sha256(
        tampered_path.read_bytes()
    ).hexdigest()
    protocol["scenario_order_sha256"] = tampered_sha256
    _write_json(protocol_path, protocol)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert "benchmark_scenario_order_mismatch" in report["reasons"]
    assert "protocol_scenario_order_pin_mismatch" in report["reasons"]
