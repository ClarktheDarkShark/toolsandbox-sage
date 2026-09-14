"""Focused lifecycle-closure checks for the development cohort verifier."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from sage_ts.adequacy.inadequacy_classifier import (
    _next_weekday_timestamp_observation,
    _safe_action_or_abstain_observation,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import ValidationContractBindingStore
from scripts import run_sage_protocol, verify_lifecycle_repair_run
from scripts.seed_lifecycle_validation_contract import seed_binding
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TEST_OUTCOME_MARKER = "__lifecycle_test_outcome__"


def _synthetic_conversation(tool_names: tuple[str, ...]) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for index, tool_name in enumerate(tool_names):
        call_id = f"synthetic-call-{index}"
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": "{}"},
                        }
                    ],
                },
                {
                    "tool_call_id": call_id,
                    "role": "tool",
                    "name": tool_name,
                    "content": "{}",
                },
            ]
        )
    return messages


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
            tuple(
                item
                for item in (execution_context.tool_allow_list or [])
                if not item.startswith(_TEST_OUTCOME_MARKER)
            )
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


def _rewrite_protocol_event_journal(
    run_root: Path, rows: list[dict[str, object]]
) -> Path:
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    journal = protocol["protocol_event_journal"]
    journal_path = Path(journal["path"])
    _write_jsonl(journal_path, rows)
    journal["sha256"] = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    journal["event_count"] = len(rows)
    _write_json(protocol_path, protocol)
    return journal_path


def _write_synthetic_trajectory(
    run_dir: Path,
    *,
    scenario_name: str,
    outcome: float,
    helper_called: bool = False,
    generated_tools: tuple[str, ...] = (),
) -> None:
    trajectory_dir = run_dir / "trajectories" / scenario_name
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    context = ExecutionContext()
    context.tool_allow_list = [f"{_TEST_OUTCOME_MARKER}{outcome!r}"]
    tool_names = tuple(
        dict.fromkeys(
            (
                *(
                    (verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,)
                    if helper_called
                    else ()
                ),
                *generated_tools,
            )
        )
    )
    for index, tool_name in enumerate(tool_names):
        context.tool_allow_list.append(tool_name)
        call_id = f"synthetic-call-{index}"
        context.add_to_database(
            DatabaseNamespace.SANDBOX,
            rows=[
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.EXECUTION_ENVIRONMENT,
                    "content": "synthetic generated-tool request",
                    "openai_tool_call_id": call_id,
                    "openai_function_name": tool_name,
                },
                {
                    "sender": RoleType.EXECUTION_ENVIRONMENT,
                    "recipient": RoleType.AGENT,
                    "content": "{'should_abstain': True}",
                    "openai_tool_call_id": call_id,
                    "openai_function_name": tool_name,
                },
            ],
        )
    _write_json(
        trajectory_dir / "execution_context.json",
        context.to_dict(serialize_console=False),
    )
    _write_json(
        trajectory_dir / "conversation.json",
        _synthetic_conversation(tool_names),
    )


def _write_registry_checkpoints(
    candidate_dir: Path,
    registry_dir: Path,
    initial_contract_dir: Path,
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
        use_initial = version == 1
        manifest = fault_manifest if use_initial else promoted_manifest
        _write_json(checkpoint_dir / "registry_manifest.json", manifest)
        contract_source = initial_contract_dir if use_initial else registry_dir
        copied_files = ["registry_manifest.json"]
        contract_index = contract_source / "validation_contract_bindings.json"
        shutil.copy2(contract_index, checkpoint_dir / contract_index.name)
        copied_files.append(contract_index.name)
        index = json.loads(contract_index.read_text(encoding="utf-8"))
        contract_hashes = sorted(
            {
                str(metadata["contract_hash"])
                for versions_by_tool in index["bindings"].values()
                for metadata in versions_by_tool.values()
            }
        )
        for contract_hash in contract_hashes:
            relative = Path("validation_contracts") / f"{contract_hash}.json"
            destination = checkpoint_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(contract_source / relative, destination)
            copied_files.append(relative.as_posix())
        _write_json(
            checkpoint_dir / "checkpoint.json",
            {
                "scenario": scenario_name,
                "completed_count": completed_count,
                "registry_dir": str(registry_dir),
                "copied_files": copied_files,
                "validation_contract_snapshot_errors": [],
            },
        )


def _promoted_registry_manifest() -> dict[str, object]:
    code = (
        "def prepare_safe_action_or_abstain(user_request: str=None, requested_action: str=None, "
        "target_identifier: str='', required_original_tools: list=[], "
        "available_original_tools: list=[], visible_records_count: int=0):\n"
        "    aliases = {'search_contacts': 'contact_lookup', 'search_reminder': 'reminder_lookup', "
        "'send_message_with_phone_number': 'message_send', 'send_message': 'message_send', "
        "'get_current_timestamp': 'current_time'}\n"
        "    required_raw = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools or [])\n"
        "    available_raw = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools or [])\n"
        "    required = [aliases.get(str(item).strip(), str(item).strip()) for item in required_raw]\n"
        "    available = [aliases.get(str(item).strip(), str(item).strip()) for item in available_raw]\n"
        "    action = str(requested_action or '').strip().lower().replace(' ', '_')\n"
        "    target = str(target_identifier or '').strip()\n"
        "    if ('send' in action or 'message' in action) and target and not target.replace('+', '').replace('-', '').replace(' ', '').isdigit() and 'contact_lookup' not in required:\n"
        "        required.append('contact_lookup')\n"
        "    missing = [item for item in required if item not in available]\n"
        "    if missing:\n"
        "        facts = ', '.join(item.replace('_', ' ') for item in missing)\n"
        "        recommendation = 'Cannot continue because the required ' + facts + ' capability is missing or unavailable.'\n"
        "        return {'should_abstain': True, 'missing_information': missing, 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': recommendation, 'abstain_reason': 'missing_required_original_tool'}\n"
        "    mutating = any(word in action for word in ('add', 'archive', 'create', 'delete', 'modify', 'remove', 'send', 'set', 'update')) and not any(word in action for word in ('search', 'lookup', 'find', 'list', 'read', 'check'))\n"
        "    if mutating and not target:\n"
        "        return {'should_abstain': True, 'missing_information': ['target_identifier'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Cannot continue because the target identifier or contact name is missing.', 'abstain_reason': 'missing_target_identifier'}\n"
        "    if mutating and int(visible_records_count or 0) > 1:\n"
        "        return {'should_abstain': True, 'missing_information': ['ambiguous_target'], 'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', 'final_answer_recommendation': 'Cannot continue because multiple matches make the target ambiguous; please clarify which one.', 'abstain_reason': 'ambiguous_target'}\n"
        "    return {'should_abstain': False, 'missing_information': [], 'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', 'final_answer_recommendation': '', 'abstain_reason': ''}\n"
    )
    fixture = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "sage_protocol"
            / "fixtures"
            / "historical_faulty_safe_action_registry.json"
        ).read_text(encoding="utf-8")
    )
    tools = dict(fixture["tools"])
    target = dict(tools[verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL])
    target.update(
        {
            "version": 2,
            "retired": False,
            "birth_scenario": "post_deployment_repair:contact",
            "code_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "tool": {
                "spec": target["tool"]["spec"],
                "code": code,
            },
            "validation": {
                "accepted": True,
                "errors": [],
                "source_example_count": 2,
                "held_out_check_count": 2,
                "negative_applicability_count": 2,
                "runtime_smoke_passed": True,
            },
        }
    )
    tools[verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL] = target
    working_path_evidence = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "sage_protocol"
            / "fixtures"
            / "paper_rep01_working_path_evidence.json"
        ).read_text(encoding="utf-8")
    )
    tools[verify_lifecycle_repair_run.NEXT_WEEKDAY_TOOL_NAME] = working_path_evidence[
        "tool_entries"
    ][verify_lifecycle_repair_run.NEXT_WEEKDAY_TOOL_NAME]
    return {"tools": tools}


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
    working_overlap_names = tuple(spec["roles"]["working_generated_overlap"])
    working_tool_paths = dict(spec["working_overlap_expected_tool_paths"])
    unrelated_preservation_names = tuple(spec["roles"]["unrelated_native_preservation"])
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
        if safe:
            visible = [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
        elif name in working_overlap_names:
            visible = list(working_tool_paths[name])
        else:
            visible = []
        versions = {
            tool_name: (
                2
                if tool_name == verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                and name != trigger_name
                else 1
            )
            for tool_name in visible
        }
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
                "generated_tool_versions": versions,
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
                "generated_tool_versions": versions,
                "generated_tool_contract_failures": (
                    [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
                    if name == trigger_name
                    else []
                ),
                "post_deployment_repair_request_ids": (
                    [request_id] if name == trigger_name else []
                ),
                "actor_followthrough_failures": [],
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
            generated_tools=(
                (verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,)
                if name in safe_names
                else tuple(working_tool_paths[name])
                if name in working_overlap_names
                else ()
            ),
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
    acceptance_event = {
        "event": "post_deployment_tool_repair_accepted",
        "request_id": request_id,
        "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
        "source_tool_version": 1,
        "new_tool_version": 2,
        "repair_kind": "implementation",
        "triggering_task_replayed": False,
        "mode": "online_build_full",
        "run_root": str(run_root),
        "run_dir": str(candidate_dir),
    }
    fault_fixture = (
        REPOSITORY_ROOT
        / "docs"
        / "sage_protocol"
        / "fixtures"
        / "historical_faulty_safe_action_registry.json"
    )
    registry_manifest_path = registry_dir / "registry_manifest.json"
    registry_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    registry_manifest_path.write_bytes(fault_fixture.read_bytes())
    contract_receipt_path = run_root / "validation_contract_seed_receipt.json"
    seed_binding(
        registry_dir=registry_dir,
        fixture_path=fault_fixture,
        receipt_path=contract_receipt_path,
    )
    initial_contract_dir = run_root / "registry_gate" / "initial_contract_store"
    initial_contract_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        registry_dir / "validation_contract_bindings.json",
        initial_contract_dir / "validation_contract_bindings.json",
    )
    shutil.copytree(
        registry_dir / "validation_contracts",
        initial_contract_dir / "validation_contracts",
    )
    sealed_contracts = run_sage_protocol._seal_development_validation_contract_receipt(
        run_root=run_root,
        registry_dir=registry_dir,
        registry_snapshot={
            "manifest_digest_before_run": (
                verify_lifecycle_repair_run.LIFECYCLE_FAULT_FIXTURE_SHA256
            )
        },
        receipt_path=contract_receipt_path,
        receipt_sha256=hashlib.sha256(contract_receipt_path.read_bytes()).hexdigest(),
    )
    _write_json(registry_manifest_path, _promoted_registry_manifest())
    final_entry = RegistryStore(registry_dir).get(
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    )
    assert final_entry is not None
    final_observation = _safe_action_or_abstain_observation(
        "development_synthetic_validation_contract"
    )
    final_binding = ValidationContractBindingStore(registry_dir).persist(
        final_entry,
        final_observation,
        validation_examples=final_observation.validation_examples,
    )
    successor_entry = RegistryStore(registry_dir).get(
        verify_lifecycle_repair_run.NEXT_WEEKDAY_TOOL_NAME
    )
    assert successor_entry is not None
    successor_observation = _next_weekday_timestamp_observation(
        "development_synthetic_validation_contract"
    )
    ValidationContractBindingStore(registry_dir).persist(
        successor_entry,
        successor_observation,
        validation_examples=successor_observation.validation_examples,
    )
    acceptance_event["validation_contract_hash"] = final_binding.contract_hash
    # Keep the historical local stream as a compatibility decoy. New manifests
    # must bind verification to the independently sealed protocol journal below.
    _write_jsonl(candidate_dir / "sage_run_events.jsonl", [acceptance_event])
    artifact_root = search_root / "protocol_artifacts"
    event_journal_path = artifact_root / "events" / "latest.jsonl"
    _write_jsonl(event_journal_path, [acceptance_event])
    event_journal_sha256 = hashlib.sha256(event_journal_path.read_bytes()).hexdigest()
    _write_json(
        registry_dir / "tool_lifecycle.json",
        {
            "schema_version": 1,
            "tools": {
                verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: {
                    "status": "promoted"
                },
                "relative_day_time_to_timestamp": {
                    "status": "retained",
                    "decision": "retain",
                    "routing_disposition": "unchanged",
                },
                "prepare_reminder_creation_args": {
                    "status": "retained",
                    "decision": "retain",
                    "routing_disposition": "unchanged",
                },
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
        initial_contract_dir,
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
            "mode": "online_build_full",
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
            "protocol_event_journal": {
                "schema_version": 1,
                "artifact_root": str(artifact_root),
                "path": str(event_journal_path),
                "sha256": event_journal_sha256,
                "event_count": 1,
                "append_closed_before_protocol_manifest": True,
            },
            "registry_gate_snapshot": {
                "manifest_existed_before_run": True,
                "manifest_digest_before_run": (
                    verify_lifecycle_repair_run.LIFECYCLE_FAULT_FIXTURE_SHA256
                ),
                "snapshot_path": str(fault_snapshot_path),
                "working_tool_provenance": json.loads(
                    fault_snapshot_path.read_text(encoding="utf-8")
                )["working_tool_provenance"],
                "seeded_validation_contract_bindings": sealed_contracts,
            },
            "seeded_validation_contract_bindings": sealed_contracts,
            "dashboard_open_receipt_path": str(receipt_path),
            "dashboard_task_compare_url": dashboard_url,
        },
    )
    assert set(working_overlap_names).isdisjoint(safe_names)
    assert set(unrelated_preservation_names).isdisjoint(safe_names)
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
    working_overlap_names = tuple(spec["roles"]["working_generated_overlap"])
    working_tool_paths = dict(spec["working_overlap_expected_tool_paths"])
    unrelated_preservation_names = tuple(spec["roles"]["unrelated_native_preservation"])

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
        if name in safe_names:
            visible = [verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL]
        elif name in working_overlap_names:
            visible = list(working_tool_paths[name])
        else:
            visible = []
        selection_rows.append(
            {
                "scenario": name,
                "generated_tools_visible": visible,
                "generated_tools_called": visible,
                "generated_tools_attempted": visible,
                "generated_tools_failed": [],
                "generated_tool_contract_failures": [],
                "generated_tool_versions": {
                    tool_name: (
                        2
                        if tool_name
                        == verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                        else 1
                    )
                    for tool_name in visible
                },
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
            generated_tools=(
                (verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,)
                if name in safe_names
                else tuple(working_tool_paths[name])
                if name in working_overlap_names
                else ()
            ),
        )
    _write_registry_checkpoints(
        candidate_dir,
        registry_dir,
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
                "registry_tools": list(verify_lifecycle_repair_run.FIXTURE_TOOL_NAMES),
            },
            {
                "event": "run_finished",
                "lifecycle_finalization_count": 0,
                "final_registry_tools": [
                    *verify_lifecycle_repair_run.FIXTURE_TOOL_NAMES
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
    target_contract_identity = (
        verify_lifecycle_repair_run._target_validation_contract_identity(registry_dir)
    )
    contract_identities = verify_lifecycle_repair_run._validation_contract_identities(
        registry_dir
    )
    assert target_contract_identity is not None
    assert contract_identities is not None
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
        "target_validation_contract": target_contract_identity,
        "validation_contract_bindings": contract_identities,
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
    assert set(working_overlap_names).isdisjoint(safe_names)
    assert set(unrelated_preservation_names).isdisjoint(safe_names)
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
    assert report["actor_followthrough_closure"]["derived_obligation_count"] == 0
    expected_paths = verify_lifecycle_repair_run.COHORT_SPECS[
        f"development_diagnostic_lifecycle_repair_{cohort}"
    ]["working_overlap_expected_tool_paths"]
    assert {
        row["scenario"]: tuple(row["expected_tools"])
        for row in report["working_generated_overlap_paths"]
    } == expected_paths
    assert all(
        row["exact_nonregressing_outcome"]
        and row["contract_bound_and_replayed"]
        and row["passed"]
        for row in report["working_generated_overlap_paths"]
    )
    assert report["preserved_working_tools_exercised_across_overlap"] == list(
        verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES
    )
    source_evidence = report["working_path_source_evidence"]
    assert len(source_evidence["task_paths"]) == 4
    assert len(source_evidence["tool_entry_sha256"]) == 3


def test_working_path_source_evidence_rejects_tampered_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        REPOSITORY_ROOT / verify_lifecycle_repair_run.WORKING_PATH_EVIDENCE["artifact"]
    )
    tampered = tmp_path / "tampered_working_path_evidence.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["source_campaign"] = "tampered"
    _write_json(tampered, payload)
    monkeypatch.setattr(
        verify_lifecycle_repair_run,
        "WORKING_PATH_EVIDENCE",
        {"artifact": str(tampered), "sha256": "0" * 64},
    )

    _, reasons = verify_lifecycle_repair_run._working_path_source_evidence_report(
        run_root=tmp_path
    )

    assert "working_path_evidence_digest_mismatch" in reasons


def test_working_path_source_evidence_rejects_malformed_task_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        REPOSITORY_ROOT / verify_lifecycle_repair_run.WORKING_PATH_EVIDENCE["artifact"]
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[7]
    payload["task_paths"][scenario_name]["called_tools"].reverse()
    malformed = tmp_path / "malformed_working_path_evidence.json"
    _write_json(malformed, payload)
    digest = hashlib.sha256(malformed.read_bytes()).hexdigest()
    monkeypatch.setattr(
        verify_lifecycle_repair_run,
        "WORKING_PATH_EVIDENCE",
        {"artifact": str(malformed), "sha256": digest},
    )

    _, reasons = verify_lifecycle_repair_run._working_path_source_evidence_report(
        run_root=tmp_path
    )

    assert f"working_path_evidence_task_mismatch:{scenario_name}" in reasons


def test_working_tool_provenance_is_hermetic_without_ignored_source_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run_root, _, manifest_path = _development_artifacts(tmp_path, "dev10")
    benchmark = json.loads(manifest_path.read_text(encoding="utf-8"))
    protocol = json.loads((run_root / "protocol_manifest.json").read_text())
    registry_snapshot = protocol["registry_gate_snapshot"]
    original_resolver = (
        verify_lifecycle_repair_run._strict_run_verifier._resolve_declared_path
    )
    ignored_source = verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_PROVENANCE[
        "source_artifact"
    ]

    def resolve_without_ignored_source(
        run_root_arg: Path,
        value: object,
        label: str,
        **kwargs: object,
    ) -> Path:
        if value == ignored_source:
            return tmp_path / "clean_clone_has_no_ignored_source.json"
        return original_resolver(run_root_arg, value, label, **kwargs)

    monkeypatch.setattr(
        verify_lifecycle_repair_run._strict_run_verifier,
        "_resolve_declared_path",
        resolve_without_ignored_source,
    )

    report, reasons = verify_lifecycle_repair_run._working_tool_provenance_report(
        run_root=run_root,
        benchmark_manifest=benchmark,
        registry_snapshot=registry_snapshot,
        initial_manifest_path=Path(registry_snapshot["snapshot_path"]),
    )

    assert reasons == []
    assert set(report["tools"]) == set(
        verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES
    )
    assert (
        report["declared_source_registry_sha256"]
        == (
            verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_PROVENANCE[
                "source_registry_sha256"
            ]
        )
    )
    assert report["observed_source_registry_sha256"] is None
    assert report["source_registry_verified"] is False


def test_followthrough_closure_orders_repeated_actions_and_binds_supersession(
    tmp_path: Path,
) -> None:
    search_root, run_root, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    registry_dir = Path(protocol["registry_dir"])
    spec = verify_lifecycle_repair_run.COHORT_SPECS[
        "development_diagnostic_lifecycle_repair_dev10"
    ]
    order = tuple(spec["order"])
    safe_names = tuple(spec["roles"][spec["safe_role"]])
    failing_names = safe_names[:3]
    family = "contact"
    context_label = "visible_task_context(family=contact; signals=followthrough)"

    selection_rows = verify_lifecycle_repair_run._read_jsonl(
        candidate_dir / "scenario_tool_selection.jsonl"
    )
    trajectory_evidence = {
        str(row["scenario"]): {
            field: tuple(row[field])
            for field in (
                "generated_tools_visible",
                "generated_tools_called",
                "generated_tools_attempted",
                "generated_tools_failed",
            )
        }
        for row in selection_rows
    }
    feedback_rows = verify_lifecycle_repair_run._read_jsonl(
        candidate_dir / "self_evolution_task_feedback.jsonl"
    )
    feedback_by_name = {str(row["scenario"]): row for row in feedback_rows}
    actions: list[dict[str, object]] = []
    for scenario_name in failing_names:
        completed_count = order.index(scenario_name) + 1
        version = 1 if scenario_name == safe_names[0] else 2
        conversation = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "followthrough-call",
                        "type": "function",
                        "function": {
                            "name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "followthrough-call",
                "name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
                "content": {
                    "should_call_tool": True,
                    "downstream_tool_name": "remove_contact",
                    "downstream_tool_kwargs": {"person_id": "public-record-id"},
                },
            },
            {"role": "assistant", "content": "Done."},
        ]
        _write_json(
            candidate_dir / "trajectories" / scenario_name / "conversation.json",
            conversation,
        )
        action = {
            "tool_name": verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL,
            "decision": "needs_route_repair",
            "repair_kind": "routing",
            "reason": "generated_helper_followup_failure",
            "scenario": context_label,
            "routing_disposition": "family_suppression_active",
            "target_task_family": family,
            "source_tool_version": version,
        }
        actions.append(action)
        feedback_by_name[scenario_name].update(
            {
                "task_context_label": context_label,
                "task_family_key": family,
                "source_task_id_redacted": True,
                "actor_followthrough_failures": [
                    verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
                ],
                "immediate_actions": [action],
            }
        )
        checkpoint_dir = verify_lifecycle_repair_run._checkpoint_directory(
            candidate_dir,
            completed_count=completed_count,
            scenario_name=scenario_name,
        )
        _write_json(
            checkpoint_dir / "tool_lifecycle.json",
            {
                "tools": {
                    verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL: {
                        "tool_version": version,
                        "actor_followthrough_failure_count": 1,
                        "actor_followthrough_failure_families": [family],
                        "route_repair_families": [family],
                        "route_repair_reason_codes": {
                            family: ["generated_helper_followup_failure"]
                        },
                        "repair_kind": "routing",
                        "routing_disposition": "family_suppression_active",
                        "decision": "needs_route_repair",
                    }
                }
            },
        )
    _write_jsonl(candidate_dir / "self_evolution_tool_lifecycle.jsonl", actions)

    lifecycle_path = registry_dir / "tool_lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    working_rows_before = {
        name: dict(lifecycle["tools"][name])
        for name in verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES
    }
    lifecycle["tools"][verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL] = {
        "tool_version": 2,
        "actor_followthrough_failure_count": 2,
        "actor_followthrough_failure_families": [family],
        "route_repair_families": [family],
        "route_repair_reason_codes": {family: ["generated_helper_followup_failure"]},
        "repair_kind": "routing",
        "routing_disposition": "family_suppression_active",
        "decision": "needs_route_repair",
    }
    _write_json(lifecycle_path, lifecycle)
    protocol_events, _journal = (
        verify_lifecycle_repair_run._verified_protocol_event_rows(
            run_root=run_root,
            protocol=protocol,
        )
    )

    report, reasons = verify_lifecycle_repair_run._actor_followthrough_closure_report(
        candidate_dir=candidate_dir,
        registry_dir=registry_dir,
        scenario_order=order,
        trajectory_evidence=trajectory_evidence,
        feedback_by_name=feedback_by_name,
        protocol_events=protocol_events,
    )

    assert reasons == []
    assert report["derived_obligation_count"] == 3
    assert report["closed_after_task_count"] == 3
    assert report["closed_at_run_end_count"] == 3
    assert [row["lifecycle_action_journal_index"] for row in report["obligations"]] == [
        0,
        1,
        2,
    ]
    assert report["obligations"][0]["terminal_disposition"] == (
        "validated_implementation_supersession"
    )
    assert all(
        report["obligations"][index]["terminal_disposition"] == "family_suppression"
        for index in (1, 2)
    )
    assert {
        name: lifecycle["tools"][name]
        for name in verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES
    } == working_rows_before

    tampered_events = [dict(row) for row in protocol_events]
    tampered_events[0]["validation_contract_hash"] = "0" * 64
    tampered_report, tampered_reasons = (
        verify_lifecycle_repair_run._actor_followthrough_closure_report(
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            scenario_order=order,
            trajectory_evidence=trajectory_evidence,
            feedback_by_name=feedback_by_name,
            protocol_events=tampered_events,
        )
    )
    assert tampered_report["obligations"][0]["closed_at_run_end"] is False
    assert any("obligation_stale_at_run_end" in reason for reason in tampered_reasons)

    _write_jsonl(
        candidate_dir / "self_evolution_tool_lifecycle.jsonl",
        [*actions, actions[-1]],
    )
    _extra_report, extra_reasons = (
        verify_lifecycle_repair_run._actor_followthrough_closure_report(
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            scenario_order=order,
            trajectory_evidence=trajectory_evidence,
            feedback_by_name=feedback_by_name,
            protocol_events=protocol_events,
        )
    )
    assert "actor_followthrough_action_journal_mismatch" in extra_reasons


def test_development_verifier_reads_sealed_protocol_event_journal(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    _write_jsonl(candidate_dir / "sage_run_events.jsonl", [])

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "pass"
    assert report["repair_acceptance_event_source"]["mode"] == (
        "sealed_protocol_event_journal"
    )
    assert report["repair_acceptance_event_source"]["sealed"] is True


def test_development_verifier_rejects_tampered_protocol_event_journal(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    journal_path = Path(protocol["protocol_event_journal"]["path"])
    with journal_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "forged"}) + "\n")

    with pytest.raises(ValueError, match="journal digest"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_verifier_rejects_symlink_protocol_event_journal(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    journal = protocol["protocol_event_journal"]
    journal_path = Path(journal["path"])
    target_path = journal_path.with_name("sealed.jsonl")
    journal_path.rename(target_path)
    journal_path.symlink_to(target_path.name)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        verify_lifecycle_repair_run.verify(search_root, 10)


def test_development_verifier_rejects_duplicate_acceptance_event(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    journal_path = Path(protocol["protocol_event_journal"]["path"])
    accepted = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    _rewrite_protocol_event_journal(run_root, [accepted, accepted])

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert report["repair_acceptance_event_count"] == 2
    assert "postdeployment_v2_acceptance_event_not_unique" in report["reasons"]


def test_development_verifier_rejects_foreign_acceptance_event_binding(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    journal_path = Path(protocol["protocol_event_journal"]["path"])
    accepted = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    accepted["run_dir"] = str(tmp_path / "different-run" / "candidate")
    _rewrite_protocol_event_journal(run_root, [accepted])

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert report["repair_acceptance_event_count"] == 0
    assert report["repair_acceptance_event_binding_mismatch_count"] == 1
    assert "postdeployment_v2_acceptance_event_binding_mismatch" in report["reasons"]


def test_development_verifier_rejects_unsealed_candidate_local_legacy_stream(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    del protocol["protocol_event_journal"]
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="requires a sealed protocol event journal"):
        verify_lifecycle_repair_run.verify(search_root, 10)


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
    assert report["working_generated_overlap_pass_count"] == 2
    assert report["unrelated_native_preservation_pass_count"] == 2
    assert all(
        row["exact_nonregressing_outcome"]
        and row["contract_bound_and_replayed"]
        and row["passed"]
        for row in report["working_generated_overlap_paths"]
    )
    assert report["preserved_working_tools_exercised_across_overlap"] == list(
        verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES
    )


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


def test_development_cohort_rejects_missing_checkpoint_contract_blob(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[0]
    checkpoint_dir = (
        run_root
        / "candidate"
        / "registry_checkpoints"
        / (
            "after_0001_"
            f"{verify_lifecycle_repair_run._safe_checkpoint_name(scenario_name)}"
        )
    )
    index = json.loads(
        (checkpoint_dir / "validation_contract_bindings.json").read_text()
    )
    contract_hash = index["bindings"][
        verify_lifecycle_repair_run.LIFECYCLE_USE_CASE_TOOL
    ]["1"]["contract_hash"]
    (checkpoint_dir / "validation_contracts" / f"{contract_hash}.json").unlink()

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "registry_checkpoint_version_mismatch" in report["reasons"]


def test_development_cohort_binds_acceptance_to_final_contract_hash(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    journal_path = Path(protocol["protocol_event_journal"]["path"])
    accepted = json.loads(journal_path.read_text().splitlines()[0])
    accepted["validation_contract_hash"] = "0" * 64
    _rewrite_protocol_event_journal(run_root, [accepted])

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "postdeployment_v2_acceptance_event_binding_mismatch" in report["reasons"]


def test_development_cohort_rejects_failure_of_preserved_working_tool(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.COHORT_SPECS[
        "development_diagnostic_lifecycle_repair_dev10"
    ]["roles"]["working_generated_overlap"][0]
    for filename in (
        "scenario_tool_selection.jsonl",
        "self_evolution_task_feedback.jsonl",
    ):
        path = candidate_dir / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if row["scenario"] == scenario_name:
                row["generated_tool_contract_failures"] = [
                    verify_lifecycle_repair_run.PRESERVED_WORKING_TOOL_NAMES[0]
                ]
        _write_jsonl(path, rows)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    assert report["status"] == "fail"
    assert "working_generated_overlap_gate_failed" in report["reasons"]


def test_development_cohort_rejects_missing_expected_successor_path(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[8]
    successor = verify_lifecycle_repair_run.NEXT_WEEKDAY_TOOL_NAME
    for filename in (
        "scenario_tool_selection.jsonl",
        "self_evolution_task_feedback.jsonl",
    ):
        path = candidate_dir / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        row = next(item for item in rows if item["scenario"] == scenario_name)
        for field in (
            "generated_tools_visible",
            "generated_tools_attempted",
            "generated_tools_called",
        ):
            row[field].remove(successor)
        del row["generated_tool_versions"][successor]
        _write_jsonl(path, rows)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    evidence = next(
        row
        for row in report["working_generated_overlap_paths"]
        if row["scenario"] == scenario_name
    )
    assert report["status"] == "fail"
    assert evidence["selection_path_present"] is False
    assert evidence["passed"] is False
    assert "working_generated_overlap_gate_failed" in report["reasons"]


def test_development_cohort_rejects_extra_working_path_tool(tmp_path: Path) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[8]
    expected = verify_lifecycle_repair_run.DEV10_WORKING_TOOL_PATHS[scenario_name]
    extra_tool = "relative_day_time_to_timestamp"
    observed = (*expected, extra_tool)
    for filename in (
        "scenario_tool_selection.jsonl",
        "self_evolution_task_feedback.jsonl",
    ):
        path = candidate_dir / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        row = next(item for item in rows if item["scenario"] == scenario_name)
        for field in (
            "generated_tools_visible",
            "generated_tools_attempted",
            "generated_tools_called",
        ):
            row[field] = list(observed)
        row["generated_tool_versions"][extra_tool] = 1
        _write_jsonl(path, rows)
    _write_synthetic_trajectory(
        candidate_dir,
        scenario_name=scenario_name,
        outcome=1.0,
        generated_tools=observed,
    )

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    evidence = next(
        row
        for row in report["working_generated_overlap_paths"]
        if row["scenario"] == scenario_name
    )
    assert report["status"] == "fail"
    assert evidence["selection_path_present"] is False
    assert evidence["trajectory_path_present"] is False
    assert "working_generated_overlap_gate_failed" in report["reasons"]


def test_development_cohort_rejects_reversed_working_call_order(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[7]
    reversed_path = tuple(
        reversed(verify_lifecycle_repair_run.DEV10_WORKING_TOOL_PATHS[scenario_name])
    )
    for filename in (
        "scenario_tool_selection.jsonl",
        "self_evolution_task_feedback.jsonl",
    ):
        path = candidate_dir / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        row = next(item for item in rows if item["scenario"] == scenario_name)
        row["generated_tools_visible"] = list(reversed_path)
        row["generated_tools_attempted"] = list(reversed_path)
        row["generated_tools_called"] = list(reversed_path)
        _write_jsonl(path, rows)
    _write_synthetic_trajectory(
        candidate_dir,
        scenario_name=scenario_name,
        outcome=1.0,
        generated_tools=reversed_path,
    )

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    evidence = next(
        row
        for row in report["working_generated_overlap_paths"]
        if row["scenario"] == scenario_name
    )
    assert report["status"] == "fail"
    assert evidence["selection_path_present"] is False
    assert evidence["trajectory_path_present"] is False
    assert "working_generated_overlap_gate_failed" in report["reasons"]


def test_development_cohort_rejects_unexpected_working_version_key(
    tmp_path: Path,
) -> None:
    search_root, _, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[8]
    extra_tool = "relative_day_time_to_timestamp"
    for filename in (
        "scenario_tool_selection.jsonl",
        "self_evolution_task_feedback.jsonl",
    ):
        path = candidate_dir / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        row = next(item for item in rows if item["scenario"] == scenario_name)
        row["generated_tool_versions"][extra_tool] = 1
        _write_jsonl(path, rows)

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    evidence = next(
        row
        for row in report["working_generated_overlap_paths"]
        if row["scenario"] == scenario_name
    )
    assert report["status"] == "fail"
    assert evidence["selection_path_present"] is False
    assert "working_generated_overlap_gate_failed" in report["reasons"]


def test_development_cohort_rejects_unbound_successor_contract(
    tmp_path: Path,
) -> None:
    search_root, run_root, _, _ = _development_artifacts(tmp_path, "dev10")
    scenario_name = verify_lifecycle_repair_run.DEV10_ORDER[8]
    checkpoint_dir = (
        run_root
        / "candidate"
        / "registry_checkpoints"
        / (
            "after_0009_"
            f"{verify_lifecycle_repair_run._safe_checkpoint_name(scenario_name)}"
        )
    )
    index = json.loads(
        (checkpoint_dir / "validation_contract_bindings.json").read_text()
    )
    contract_hash = index["bindings"][
        verify_lifecycle_repair_run.NEXT_WEEKDAY_TOOL_NAME
    ]["1"]["contract_hash"]
    (checkpoint_dir / "validation_contracts" / f"{contract_hash}.json").unlink()

    report = verify_lifecycle_repair_run.verify(search_root, 10)

    evidence = next(
        row
        for row in report["working_generated_overlap_paths"]
        if row["scenario"] == scenario_name
    )
    assert report["status"] == "fail"
    assert evidence["contract_bound_and_replayed"] is False
    assert evidence["passed"] is False
    assert "working_generated_overlap_gate_failed" in report["reasons"]


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
    assert "transfer_unrelated_native_preservation_gate_failed" in report["reasons"]


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
    search_root, run_root, candidate_dir, _ = _development_artifacts(tmp_path, "dev10")
    for filename in (
        "self_evolution_tool_repair_requests.jsonl",
        "self_evolution_tool_repair_acknowledgements.jsonl",
        "self_evolution_task_feedback.jsonl",
        "sage_run_events.jsonl",
    ):
        (candidate_dir / filename).write_text("", encoding="utf-8")
    _rewrite_protocol_event_journal(
        run_root,
        [
            {
                "event": "run_finished",
                "mode": "online_build_full",
                "run_root": str(run_root),
                "run_dir": str(candidate_dir),
            }
        ],
    )

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

    assert "unrelated_native_preservation_gate_failed" in report["reasons"]


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
