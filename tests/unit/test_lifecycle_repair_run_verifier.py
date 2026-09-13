"""Focused lifecycle-closure checks for the development cohort verifier."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts import verify_lifecycle_repair_run
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TEST_OUTCOME_MARKER = "__lifecycle_test_outcome__"


def _synthetic_conversation(helper_called: bool) -> list[dict[str, object]]:
    if not helper_called:
        return []
    return [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "synthetic-call",
                    "type": "function",
                    "function": {
                        "name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                        "arguments": "{}",
                    },
                }
            ],
        },
        {
            "tool_call_id": "synthetic-call",
            "role": "tool",
            "name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
            "content": "{'should_abstain': True}",
        },
    ]


def _fake_trajectory_recomputation(
    _scenario: object,
    execution_context: ExecutionContext,
    *,
    scenario_name: str,
) -> dict[str, object]:
    marker = next(
        (
            item
            for item in (execution_context.tool_allow_list or [])
            if item.startswith(_TEST_OUTCOME_MARKER)
        ),
        None,
    )
    if marker is None:
        raise ValueError("synthetic lifecycle trajectory has no outcome marker")
    outcome = float(marker.removeprefix(_TEST_OUTCOME_MARKER))
    result = _result_row(scenario_name, outcome)
    return {
        "audited_outcome": {
            key: value for key, value in result.items() if key.startswith("outcome_")
        },
        "paper_outcome": {"outcome_similarity": None},
        "conversation": _synthetic_conversation(
            verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
            in (execution_context.tool_allow_list or [])
        ),
    }


@pytest.fixture(autouse=True)
def _synthetic_trajectory_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    strict = verify_lifecycle_repair_run._strict_run_verifier
    monkeypatch.setattr(
        strict,
        "_load_publication_scenarios",
        lambda scenario_names: {name: object() for name in scenario_names},
    )
    monkeypatch.setattr(
        strict,
        "_independently_recompute_trajectory",
        _fake_trajectory_recomputation,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_synthetic_trajectory(
    run_dir: Path,
    *,
    scenario_name: str,
    outcome: float,
    helper_called: bool,
) -> None:
    trajectory_dir = run_dir / "trajectories" / scenario_name
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    context = ExecutionContext()
    context.tool_allow_list = [f"{_TEST_OUTCOME_MARKER}{outcome!r}"]
    if helper_called:
        context.tool_allow_list.append(
            verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
        )
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            rows=[
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "synthetic generated-tool request",
                    "openai_tool_call_id": "synthetic-call",
                    "openai_function_name": (
                        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                    ),
                },
                {
                    "sender": RoleType.EXECUTION_ENVIRONMENT,
                    "recipient": RoleType.AGENT,
                    "content": "{'should_abstain': True}",
                    "openai_tool_call_id": "synthetic-call",
                    "openai_function_name": (
                        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                    ),
                },
            ],
        )
    _write_json(
        trajectory_dir / "execution_context.json",
        context.to_dict(serialize_console=False),
    )
    _write_json(
        trajectory_dir / "conversation.json",
        _synthetic_conversation(helper_called),
    )


def _write_registry_checkpoints(
    candidate_dir: Path,
    registry_dir: Path,
    *,
    scenario_order: tuple[str, ...],
    versions: dict[str, int | None],
) -> None:
    promoted_manifest = _promoted_registry_manifest()
    fault_manifest = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "sage_protocol"
            / "fixtures"
            / "historical_faulty_safe_action_registry.json"
        ).read_text(encoding="utf-8")
    )
    for completed_count, scenario_name in enumerate(scenario_order, start=1):
        checkpoint_dir = (
            candidate_dir
            / "registry_checkpoints"
            / (
                f"after_{completed_count:04d}_"
                f"{verify_lifecycle_repair_run._safe_checkpoint_name(scenario_name)}"
            )
        )
        version = versions.get(scenario_name)
        manifest = fault_manifest if version == 1 else promoted_manifest
        _write_json(checkpoint_dir / "registry_manifest.json", manifest)
        _write_json(
            checkpoint_dir / "checkpoint.json",
            {
                "scenario": scenario_name,
                "completed_count": completed_count,
                "registry_dir": str(registry_dir),
                "copied_files": ["registry_manifest.json"],
            },
        )


def _promoted_registry_manifest() -> dict[str, object]:
    code = (
        "def prepare_safe_action_or_abstain(user_request: str, "
        "requested_action: str):\n"
        "    return {'should_abstain': True, 'missing_information': "
        "['contact_lookup'], 'required_original_tools': ['search_contacts'], "
        "'safe_next_action': 'ask_user_or_abstain', "
        "'final_answer_recommendation': 'I do not have enough information.', "
        "'abstain_reason': 'missing_required_original_tool'}\n"
    )
    return {
        "tools": {
            verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: {
                "version": 2,
                "retired": False,
                "birth_scenario": "post_deployment_repair:contact",
                "code_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "tool": {
                    "spec": {
                        "schema_version": 2,
                        "tool_name": (
                            verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                        ),
                        "family": "validation_abstention_helper",
                        "description": "Safely abstain when a required lookup is absent.",
                        "inputs": [],
                        "output_annotation": "dict",
                    },
                    "code": code,
                },
            }
        }
    }


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
        "online_feedback_outcome_similarity": None,
        "online_feedback_evaluator_version": (
            verify_lifecycle_repair_run._strict_run_verifier.ONLINE_FEEDBACK_EVALUATOR_VERSION
        ),
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
                "generated_tools_attempted": visible,
                "generated_tools_failed": [],
                "generated_tool_contract_failures": (
                    [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
                    if name == trigger_name
                    else []
                ),
                "generated_tool_versions": (
                    {
                        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: (
                            1 if name == trigger_name else 2
                        )
                    }
                    if safe
                    else {}
                ),
                "exception_type": None,
            }
        )
        feedback_rows.append(
            {
                "event": "self_evolution_task_assessed",
                "scenario": name,
                "completed_count": completed_count,
                "candidate_outcome": 0.0 if name == trigger_name else 1.0,
                "generated_tools_visible": visible,
                "generated_tools_called": visible,
                "generated_tools_attempted": visible,
                "generated_tools_failed": [],
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
                "exception_type": None,
            }
        )
    _write_jsonl(candidate_dir / "scenario_tool_selection.jsonl", selection_rows)
    _write_jsonl(candidate_dir / "self_evolution_task_feedback.jsonl", feedback_rows)
    candidate_outcome_by_name = {
        str(row["name"]): float(row["outcome_similarity"]) for row in candidate_rows
    }
    control_outcome_by_name = {
        str(row["name"]): float(row["outcome_similarity"]) for row in control_rows
    }
    for name in order:
        _write_synthetic_trajectory(
            control_dir,
            scenario_name=name,
            outcome=control_outcome_by_name[name],
            helper_called=False,
        )
        _write_synthetic_trajectory(
            candidate_dir,
            scenario_name=name,
            outcome=candidate_outcome_by_name[name],
            helper_called=name in safe_names,
        )
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
    _write_json(registry_manifest_path, _promoted_registry_manifest())
    _write_json(
        registry_dir / "tool_lifecycle.json",
        {
            "schema_version": 1,
            "tools": {
                verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: {
                    "status": "promoted"
                }
            },
        },
    )
    _write_jsonl(
        registry_dir / "success_flip_events.jsonl",
        [{"tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL}],
    )
    _write_registry_checkpoints(
        candidate_dir,
        registry_dir,
        scenario_order=order,
        versions={
            name: 1 if name == trigger_name else 2 if name in safe_names else None
            for name in order
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


def _transfer_artifacts(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path]:
    source_search, source_run, _, _ = _development_artifacts(
        tmp_path / "source", "dev10"
    )
    source_report = verify_lifecycle_repair_run.verify(source_search, 10)
    assert source_report["status"] == "pass"
    source_protocol_path = source_run / "protocol_manifest.json"
    source_protocol = json.loads(source_protocol_path.read_text(encoding="utf-8"))
    source_report_path = source_run / "lifecycle_repair_validation_report.json"
    source_registry_dir = Path(source_protocol["registry_dir"])

    search_root, run_root, candidate_dir, _ = _development_artifacts(
        tmp_path / "destination", "dev30"
    )
    control_dir = run_root / "control"
    registry_dir = run_root / "registry"
    shutil.rmtree(registry_dir)
    shutil.copytree(source_registry_dir, registry_dir)

    manifest_path = (
        REPOSITORY_ROOT
        / "docs"
        / "sage_protocol"
        / "manifests"
        / "lifecycle_repair_transfer_dev30.json"
    )
    benchmark = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = verify_lifecycle_repair_run.COHORT_SPECS[benchmark["manifest_type"]]
    order = tuple(spec["order"])
    safe_names = tuple(spec["roles"][spec["safe_role"]])
    preservation_names = tuple(spec["roles"]["preservation"])

    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": [_result_row(name, 1.0) for name in order]},
    )
    _write_json(
        control_dir / "result_summary.json",
        {
            "per_scenario_results": [
                _result_row(name, 0.0 if name in safe_names else 1.0) for name in order
            ]
        },
    )
    selection_rows = []
    for name in order:
        visible = (
            [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
            if name in safe_names
            else []
        )
        selection_rows.append(
            {
                "scenario": name,
                "generated_tools_visible": visible,
                "generated_tools_called": visible,
                "generated_tools_attempted": visible,
                "generated_tools_failed": [],
                "generated_tool_versions": (
                    {verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: 2}
                    if visible
                    else {}
                ),
            }
        )
    _write_jsonl(candidate_dir / "scenario_tool_selection.jsonl", selection_rows)
    for name in order:
        _write_synthetic_trajectory(
            control_dir,
            scenario_name=name,
            outcome=0.0 if name in safe_names else 1.0,
            helper_called=False,
        )
        _write_synthetic_trajectory(
            candidate_dir,
            scenario_name=name,
            outcome=1.0,
            helper_called=name in safe_names,
        )
    _write_registry_checkpoints(
        candidate_dir,
        registry_dir,
        scenario_order=order,
        versions={name: 2 if name in safe_names else None for name in order},
    )
    for filename in (
        "capability_observations.jsonl",
        "tool_birth_events.jsonl",
        "self_evolution_reflections.jsonl",
        "self_evolution_task_feedback.jsonl",
        "self_evolution_tool_lifecycle.jsonl",
        "self_evolution_tool_repair_requests.jsonl",
        "self_evolution_tool_repair_acknowledgements.jsonl",
        "post_deployment_repair_state.json",
        "self_evolution_reflection_state.json",
        "tool_generation_status.json",
    ):
        path = candidate_dir / filename
        if path.exists():
            path.unlink()
    _write_jsonl(
        candidate_dir / "sage_run_events.jsonl",
        [
            {
                "event": "registry_load",
                "generation_enabled": False,
                "registry_tools": [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL],
            },
            {
                "event": "run_finished",
                "lifecycle_finalization_count": 0,
                "final_registry_tools": [
                    verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                ],
            },
        ],
    )
    for arm, run_dir in (("control", control_dir), ("candidate", candidate_dir)):
        _write_json(
            run_dir / "sage_ts_run_manifest.json",
            {
                "agent_runtime": "sage_wrapped",
                "actor_selection_mode": "policy",
                "scenario_names": list(order),
                "run_type": f"transfer_30_{arm}",
            },
        )

    inventory = verify_lifecycle_repair_run._registry_inventory(registry_dir)
    inventory_sha256 = verify_lifecycle_repair_run._inventory_sha256(inventory)
    target_identity = verify_lifecycle_repair_run._target_tool_identity(registry_dir)
    assert target_identity is not None
    snapshot_path = run_root / "registry_gate" / "registry_manifest_before_run.json"
    snapshot_path.write_bytes((registry_dir / "registry_manifest.json").read_bytes())
    snapshot = {
        "registry_dir": str(registry_dir),
        "manifest_existed_before_run": True,
        "snapshot_path": str(snapshot_path),
        "manifest_digest_before_run": hashlib.sha256(
            snapshot_path.read_bytes()
        ).hexdigest(),
        "registry_directory_existed_before_run": True,
        "registry_inventory_before_run": inventory,
        "registry_inventory_count_before_run": len(inventory),
        "registry_inventory_sha256": inventory_sha256,
    }
    _write_json(run_root / "registry_gate" / "registry_gate_snapshot.json", snapshot)
    provenance = {
        "mode": "frozen_promoted_registry_transfer",
        "source_run_root": str(source_run.resolve()),
        "source_protocol_path": str(source_protocol_path),
        "source_protocol_sha256": hashlib.sha256(
            source_protocol_path.read_bytes()
        ).hexdigest(),
        "source_validation_report_path": str(source_report_path),
        "source_validation_report_sha256": hashlib.sha256(
            source_report_path.read_bytes()
        ).hexdigest(),
        "source_registry_dir": str(source_registry_dir.resolve()),
        "source_registry_inventory_count": len(inventory),
        "source_registry_inventory_sha256": inventory_sha256,
        "installed_registry_dir": str(registry_dir.resolve()),
        "installed_registry_inventory_sha256": inventory_sha256,
        "target_tool": target_identity,
    }
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol.update(
        {
            "mode": "transfer_30",
            "manifest_type": benchmark["manifest_type"],
            "benchmark_manifest_path": str(manifest_path),
            "benchmark_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "scenario_order_sha256": spec["order_sha256"],
            "generation_enabled": False,
            "candidate_generated_tools_enabled": False,
            "lifecycle_mutation_enabled": False,
            "sage_policy": "none",
            "actor_selection_mode": "policy",
            "control_condition": "matched_policy_wrapper_without_generated_tools",
            "control_agent_runtime": "sage_wrapped",
            "candidate_agent_runtime": "sage_wrapped",
            "registry_manifest_digest_after_run": hashlib.sha256(
                (registry_dir / "registry_manifest.json").read_bytes()
            ).hexdigest(),
            "registry_gate_snapshot": snapshot,
            "registry_transfer_provenance": provenance,
        }
    )
    _write_json(protocol_path, protocol)
    assert set(preservation_names).isdisjoint(safe_names)
    return search_root, run_root, candidate_dir, registry_dir, source_run


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


def test_frozen_dev30_transfer_passes_with_exact_promoted_registry(
    tmp_path: Path,
) -> None:
    search_root, _, _, _, _ = _transfer_artifacts(tmp_path)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "pass"
    assert report["registry_unchanged"] is True
    assert report["source_and_confirmation_cohorts_disjoint"] is True
    assert report["safe_abstain_visible_and_called_count"] == 26
    assert report["safe_abstain_exact_outcome_count"] >= 21
    assert report["fresh_control_success_flip_count"] >= 1
    assert report["preservation_exact_hidden_nonregression_count"] == 4


def test_development_cohort_requires_complete_trajectory_artifacts(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    missing_path = (
        run_root
        / "candidate"
        / "trajectories"
        / verify_lifecycle_repair_run.DEV10_ORDER[0]
        / "conversation.json"
    )
    missing_path.unlink()

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "trajectory_integrity_failed" in report["reasons"]


def test_development_cohort_rejects_summary_not_backed_by_trajectory(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    summary_path = candidate_dir / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["outcome_checks"] = []
    _write_json(summary_path, summary)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "trajectory_integrity_failed" in report["reasons"]


def test_development_control_rejects_generated_tool_leakage(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[0]
    _write_synthetic_trajectory(
        run_root / "control",
        scenario_name=scenario_name,
        outcome=0.0,
        helper_called=True,
    )

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "trajectory_integrity_failed" in report["reasons"]


def test_development_cohort_rejects_checkpoint_version_corruption(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[0]
    checkpoint_path = (
        run_root
        / "candidate"
        / "registry_checkpoints"
        / (
            "after_0001_"
            f"{verify_lifecycle_repair_run._safe_checkpoint_name(scenario_name)}"
        )
        / "registry_manifest.json"
    )
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["tools"][verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL][
        "version"
    ] = 99
    _write_json(checkpoint_path, checkpoint)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "registry_checkpoint_version_mismatch" in report["reasons"]


def test_frozen_transfer_requires_complete_trajectory_artifacts(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _, _ = _transfer_artifacts(tmp_path)
    missing_path = (
        candidate_dir
        / "trajectories"
        / verify_lifecycle_repair_run.DEV30_ORDER[0]
        / "execution_context.json"
    )
    missing_path.unlink()

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert "transfer_trajectory_integrity_failed" in report["reasons"]


def test_frozen_transfer_rejects_nonpassing_source_report(tmp_path: Path) -> None:
    search_root, _, _, _, source_run = _transfer_artifacts(tmp_path)
    source_protocol = json.loads(
        (source_run / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    source_candidate = Path(source_protocol["candidate_dir"])
    result_path = source_candidate / "result_summary.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["per_scenario_results"] = [
        _result_row(str(row["name"]), 0.0) for row in result["per_scenario_results"]
    ]
    _write_json(result_path, result)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert "transfer_source_dev10_not_passing" in report["reasons"]


def test_frozen_transfer_rejects_registry_sidecar_mutation(tmp_path: Path) -> None:
    search_root, _, _, registry_dir, _ = _transfer_artifacts(tmp_path)
    lifecycle_path = registry_dir / "tool_lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["tampered"] = True
    _write_json(lifecycle_path, lifecycle)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert "transfer_registry_mutated_during_confirmation" in report["reasons"]


def test_frozen_transfer_rejects_generation_or_lifecycle_activity(
    tmp_path: Path,
) -> None:
    search_root, run_root, candidate_dir, _, _ = _transfer_artifacts(tmp_path)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["generation_enabled"] = True
    protocol["lifecycle_mutation_enabled"] = True
    _write_json(protocol_path, protocol)
    _write_jsonl(
        candidate_dir / "tool_birth_events.jsonl",
        [{"event": "tool_birth_accepted"}],
    )

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert "transfer_protocol_generation_enabled_mismatch" in report["reasons"]
    assert "transfer_lifecycle_activity_present" in report["reasons"]


def test_frozen_transfer_rejects_missing_exact_version_call(tmp_path: Path) -> None:
    search_root, _, candidate_dir, _, _ = _transfer_artifacts(tmp_path)
    selection_path = candidate_dir / "scenario_tool_selection.jsonl"
    rows = [json.loads(line) for line in selection_path.read_text().splitlines()]
    rows[0]["generated_tool_versions"][
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    ] = 3
    _write_jsonl(selection_path, rows)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert (
        "transfer_helper_not_visible_called_at_exact_version_26_of_26"
        in report["reasons"]
    )


def test_frozen_transfer_rejects_absent_fresh_control_flip(tmp_path: Path) -> None:
    search_root, run_root, _, _, _ = _transfer_artifacts(tmp_path)
    control_path = run_root / "control" / "result_summary.json"
    control = json.loads(control_path.read_text(encoding="utf-8"))
    control["per_scenario_results"] = [
        _result_row(str(row["name"]), 1.0) for row in control["per_scenario_results"]
    ]
    _write_json(control_path, control)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert "transfer_fresh_control_success_flip_missing" in report["reasons"]


def test_frozen_transfer_rejects_preservation_regression_or_helper_leak(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _, _ = _transfer_artifacts(tmp_path)
    summary_path = candidate_dir / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][-1] = _result_row(
        str(summary["per_scenario_results"][-1]["name"]), 0.0
    )
    _write_json(summary_path, summary)
    selection_path = candidate_dir / "scenario_tool_selection.jsonl"
    selections = [json.loads(line) for line in selection_path.read_text().splitlines()]
    selections[-1]["generated_tools_visible"] = [
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    ]
    _write_jsonl(selection_path, selections)

    report = verify_lifecycle_repair_run.verify(search_root, 30)

    assert report["status"] == "fail"
    assert (
        "transfer_preservation_exact_hidden_nonregression_gate_failed"
        in report["reasons"]
    )


def test_development_cohort_recursively_rejects_private_repair_evidence(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    request_path = candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    request = json.loads(request_path.read_text(encoding="utf-8").splitlines()[0])
    request["nested_diagnostics"] = {
        "history": [
            {"evaluator_trace": {"expected_answer": "private"}},
            {"candidate_outcome_similarity": 1.0},
            {"fresh_control_success_flip": True},
        ]
    }
    _write_jsonl(request_path, [request])

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "repair_request_contains_prohibited_evidence" in report["reasons"]
    prohibited_paths = report["repair_request_prohibited_paths"][
        "prepare-safe-v1-after-1"
    ]
    assert any(path.endswith("evaluator_trace") for path in prohibited_paths)
    assert any(path.endswith("expected_answer") for path in prohibited_paths)
    assert any(
        path.endswith("candidate_outcome_similarity") for path in prohibited_paths
    )
    assert any(path.endswith("fresh_control_success_flip") for path in prohibited_paths)


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
