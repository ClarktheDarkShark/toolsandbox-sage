from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sage_ts.evaluation.actor_selection_comparison import (
    ActorSelectionVerificationError,
    _schema_bundle_is_exact,
    compare_outcome_values,
    validate_live_uncached_run,
    verify_matched_actor_selection_experiment,
)
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest

SCENARIOS = ("task_a", "task_b")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def test_tool_free_schema_bundle_matches_runtime_not_given_representation() -> None:
    assert _schema_bundle_is_exact(
        {
            "ordered_schemas": None,
            "native_schemas": [],
            "generated_schemas": [],
            "schema_classification": [],
        }
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_matching_result_summaries(
    run_dir: Path,
    result_summary: dict[str, object],
) -> None:
    _write_json(run_dir / "result_summary.json", result_summary)
    live_summary = json.loads(
        (run_dir / "live_result_summary.json").read_text(encoding="utf-8")
    )
    live_summary["per_scenario_results"] = result_summary["per_scenario_results"]
    _write_json(run_dir / "live_result_summary.json", live_summary)


def _tamper_outcome_row_identity(run_dir: Path) -> None:
    result = json.loads((run_dir / "result_summary.json").read_text(encoding="utf-8"))
    result["per_scenario_results"][0]["outcome_evaluator_contract_sha256"] = "0" * 64
    _write_matching_result_summaries(run_dir, result)


def _tamper_outcome_manifest_identity(run_dir: Path) -> None:
    manifest_path = run_dir.parent / "sage_ts_run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outcome_evaluator"]["source_sha256"] = "0" * 64
    _write_json(manifest_path, manifest)


def _schema_bundle() -> tuple[str, dict[str, object]]:
    native = {
        "type": "function",
        "function": {"name": "native_tool", "parameters": {"type": "object"}},
    }
    generated = {
        "type": "function",
        "function": {"name": "generated_tool", "parameters": {"type": "object"}},
    }
    bundle: dict[str, object] = {
        "ordered_schemas": [native, generated],
        "native_schemas": [native],
        "generated_schemas": [generated],
        "schema_classification": [
            {
                "schema_index": 0,
                "kind": "native",
                "agent_facing_name": "native_tool",
                "execution_facing_name": "native_tool",
            },
            {
                "schema_index": 1,
                "kind": "generated",
                "agent_facing_name": "generated_tool",
                "execution_facing_name": "generated_tool",
            },
        ],
    }
    return _canonical_sha256(bundle), bundle


def _write_run(
    run_dir: Path,
    *,
    mode: str,
    authority_mode: str,
    authority_tasks_sha256: str,
    outcomes: tuple[float, float],
    generated_called: int = 1,
) -> None:
    evaluator = outcome_evaluator_manifest()
    digest, bundle = _schema_bundle()
    ordered_schema_sha256 = _canonical_sha256(bundle["ordered_schemas"])
    audit_rows: list[dict[str, object]] = []
    usage_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    for index, scenario in enumerate(SCENARIOS, start=1):
        request_id = f"actor-request-{index:06d}"
        audit_rows.append(
            {
                "request_id": request_id,
                "scenario": scenario,
                "model": "gpt-4o-mini",
                "choice_mode": mode,
                "status": "complete",
                "messages_unchanged": True,
                "sent_schemas_unchanged": True,
                "named_tool_choice": None,
                "named_tool_choice_absent": True,
                "tool_choice": None,
                "schemas_exact": True,
                "routed_schema_catalog_sha256": digest,
                "sent_schema_catalog_sha256": digest,
                "routed_schemas_sha256": ordered_schema_sha256,
                "sent_schemas_sha256": ordered_schema_sha256,
                "native_schema_count": 1,
                "generated_schema_count": 1,
            }
        )
        usage_rows.append(
            {
                "scenario": scenario,
                "source": "toolsandbox_agent",
                "model": "gpt-4o-mini",
                "actor_request_id": request_id,
                "response_cache_status": "live",
                "usage_available": True,
                "prompt_tokens": 10,
                "provider_cached_prompt_tokens": 0,
                "completion_tokens": 2,
                "total_tokens": 12,
                "raw_usage": {
                    "prompt_tokens": 10,
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            }
        )
        called = ["generated_tool"] if index <= generated_called else []
        selection_rows.append(
            {
                "scenario": scenario,
                "generated_tools_visible": ["generated_tool"],
                "generated_tools_attempted": list(called),
                "generated_tools_failed": [],
                "generated_tools_called": called,
                "visible_generated_tool_count": 1,
                "attempted_generated_tool_count": len(called),
                "failed_generated_tool_count": 0,
                "called_generated_tool_count": len(called),
                "selection_status": (
                    "generated_tool_called"
                    if called
                    else "generated_tool_visible_not_called"
                ),
                "relevance_gating_hid_retained_tool": False,
            }
        )
    _write_jsonl(run_dir / "actor_request_audit.jsonl", audit_rows)
    _write_json(run_dir / "actor_schema_catalog.json", {"bundles": {digest: bundle}})
    _write_jsonl(
        run_dir / "actor_schema_catalog.jsonl",
        [{"schema_catalog_sha256": digest, "bundle": bundle}],
    )
    _write_json(
        run_dir / "actor_request_audit_summary.json",
        {
            "schema_version": 1,
            "finalized": True,
            "coverage_verified": True,
            "expected_actor_selection_mode": mode,
            "request_count": len(audit_rows),
            "persisted_event_count": len(audit_rows),
            "complete_request_count": len(audit_rows),
            "failed_request_count": 0,
            "linked_agent_call_count": len(usage_rows),
            "agent_call_count": len(usage_rows),
            "unlinked_agent_call_count": 0,
            "missing_usage_request_ids": [],
            "unexpected_usage_request_ids": [],
            "duplicate_usage_request_ids": [],
            "mode_mismatch_request_ids": [],
            "invariant_failure_request_ids": [],
        },
    )
    _write_jsonl(run_dir / "llm_usage_events.jsonl", usage_rows)
    source_summary = {
        "toolsandbox_agent": {
            "llm_call_count": len(usage_rows),
            "llm_live_call_count": len(usage_rows),
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 10 * len(usage_rows),
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": len(usage_rows),
            "llm_completion_tokens": 2 * len(usage_rows),
            "llm_total_tokens": 12 * len(usage_rows),
        }
    }
    _write_json(
        run_dir / "llm_usage_summary.json",
        {
            "schema_version": 2,
            "token_source": "openai_chat_completion_usage",
            "llm_usage_recorded": True,
            "llm_call_count": len(usage_rows),
            "llm_live_call_count": len(usage_rows),
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 10 * len(usage_rows),
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": len(usage_rows),
            "llm_completion_tokens": 2 * len(usage_rows),
            "llm_total_tokens": 12 * len(usage_rows),
            "llm_usage_available_count": len(usage_rows),
            "llm_usage_by_source": source_summary,
            "scenario_count_with_usage": len(SCENARIOS),
        },
    )
    per_scenario_source_summary = {
        "toolsandbox_agent": {
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 10,
            "llm_provider_cached_prompt_tokens": 0,
            "llm_provider_cached_prompt_call_count": 0,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 2,
            "llm_total_tokens": 12,
        }
    }
    _write_json(
        run_dir / "result_summary.json",
        {
            "per_scenario_results": [
                {
                    "name": scenario,
                    "outcome_similarity": outcome,
                    "outcome_evaluator_version": evaluator["version"],
                    "outcome_evaluator_contract_sha256": evaluator["contract_sha256"],
                    "outcome_evaluator_source_sha256": evaluator["source_sha256"],
                    "exception_type": None,
                    "traceback": None,
                    "transient_retry_count": 0,
                    "transient_retry_archives": [],
                    "transient_retry_failures": [],
                    "llm_usage_recorded": True,
                    "llm_call_count": 1,
                    "llm_live_call_count": 1,
                    "llm_cached_call_count": 0,
                    "llm_prompt_tokens": 10,
                    "llm_provider_cached_prompt_tokens": 0,
                    "llm_provider_cached_prompt_call_count": 0,
                    "llm_provider_cached_prompt_tokens_available_count": 1,
                    "llm_completion_tokens": 2,
                    "llm_total_tokens": 12,
                    "llm_usage_available_count": 1,
                    "llm_usage_by_source": per_scenario_source_summary,
                }
                for scenario, outcome in zip(SCENARIOS, outcomes)
            ]
        },
    )
    result_rows = json.loads(
        (run_dir / "result_summary.json").read_text(encoding="utf-8")
    )["per_scenario_results"]
    _write_json(
        run_dir / "live_result_summary.json",
        {
            "status": "complete",
            "completed_count": len(SCENARIOS),
            "scenario_count": len(SCENARIOS),
            "per_scenario_results": result_rows,
        },
    )
    _write_jsonl(run_dir / "scenario_tool_selection.jsonl", selection_rows)
    _write_json(
        run_dir.parent / "sage_ts_run_manifest.json",
        {"outcome_evaluator": evaluator},
    )
    _write_json(
        run_dir / "selection_summary.json",
        {
            "scenario_count": len(SCENARIOS),
            "generation_enabled": authority_mode == "capture",
            "actor_selection_mode": mode,
            "inventory_authority_mode": authority_mode,
            "inventory_authority_task_count": len(SCENARIOS),
            "inventory_authority_tasks_sha256": authority_tasks_sha256,
            "generated_tool_visible_scenarios": 2,
            "generated_tool_called_scenarios": generated_called,
            "generated_tool_attempted_scenarios": generated_called,
            "generated_tool_failed_scenarios": 0,
            "relevance_gate_hidden_scenarios": 0,
        },
    )


def _write_experiment(tmp_path: Path) -> tuple[Path, Path, Path]:
    policy_dir = tmp_path / "policy" / "run"
    auto_dir = tmp_path / "auto" / "run"
    authority_path = tmp_path / "authority" / "inventory_authority.json"
    tasks = []
    for index, scenario in enumerate(SCENARIOS):
        state_dir = Path("tasks") / f"{index + 1:04d}_{scenario}"
        (authority_path.parent / state_dir).mkdir(parents=True)
        tasks.append(
            {
                "order_index": index,
                "scenario": scenario,
                "state_dir": state_dir.as_posix(),
                "registry_manifest_present": False,
                "registry_manifest_sha256": None,
                "tool_lifecycle_present": False,
                "tool_lifecycle_sha256": None,
            }
        )
    shared_context = {
        "agent": "gpt-4o-mini",
        "user": "gpt-4o-mini",
        "generation_model": "gpt-4o-mini",
        "fixed_toolsandbox_timestamp": "1784832588",
    }
    authority_tasks_sha256 = _canonical_sha256(tasks)
    _write_json(
        authority_path,
        {
            "artifact_type": "sage_matched_inventory_authority",
            "schema_version": 2,
            "complete": True,
            "source_actor_selection_mode": "policy",
            "source_generation_enabled": True,
            "shared_context": shared_context,
            "shared_context_sha256": _canonical_sha256(shared_context),
            "scenario_names": list(SCENARIOS),
            "scenario_order_sha256": hashlib.sha256(
                ("\n".join(SCENARIOS) + "\n").encode("utf-8")
            ).hexdigest(),
            "expected_task_count": len(SCENARIOS),
            "task_count": len(SCENARIOS),
            "tasks_sha256": authority_tasks_sha256,
            "tasks": tasks,
        },
    )
    _write_run(
        policy_dir,
        mode="policy",
        authority_mode="capture",
        authority_tasks_sha256=authority_tasks_sha256,
        outcomes=(0.0, 0.25),
    )
    _write_run(
        auto_dir,
        mode="auto",
        authority_mode="replay",
        authority_tasks_sha256=authority_tasks_sha256,
        outcomes=(1.0, 0.25),
    )
    return policy_dir, auto_dir, authority_path


def test_matched_experiment_verifies_exact_schemas_and_outcomes(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )

    assert report["mechanism_counts_are_performance_gates"] is False
    assert report["outcome_evidence_complete"] is True
    assert report["performance_gate_applied"] is False
    assert report["integrity_gate_passed"] is True
    assert report["experiment_passed"] is True
    assert report["stability_gate_passed"] is True
    assert report["routed_schemas_identical_by_scenario"] is True
    assert report["persistent_response_cache_reuse"] is False
    outcomes = report["outcomes"]
    assert outcomes["canonical_similarity_included"] is False
    assert outcomes["outcome_evaluated_count"] == 2
    assert outcomes["outcome_not_evaluated_count"] == 0
    assert outcomes["policy_exact_outcome_successes"] == 0
    assert outcomes["auto_exact_outcome_successes"] == 1
    assert outcomes["auto_minus_policy_mean_outcome_delta"] == 0.5


def test_matched_experiment_rejects_auto_named_choice(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    rows = [
        json.loads(line)
        for line in (auto_dir / "actor_request_audit.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    rows[0]["named_tool_choice"] = "generated_tool"
    rows[0]["named_tool_choice_absent"] = False
    _write_jsonl(auto_dir / "actor_request_audit.jsonl", rows)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="used policy intervention",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_matched_experiment_recomputes_auto_schema_equality(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    catalog_path = auto_dir / "actor_schema_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    _original_digest, original_bundle = _schema_bundle()
    sent_bundle = json.loads(json.dumps(original_bundle))
    sent_bundle["ordered_schemas"][1]["function"]["description"] = "changed"
    sent_bundle["generated_schemas"][0]["function"]["description"] = "changed"
    sent_digest = _canonical_sha256(sent_bundle)
    catalog["bundles"][sent_digest] = sent_bundle
    _write_json(catalog_path, catalog)
    incremental_catalog = _read_jsonl(auto_dir / "actor_schema_catalog.jsonl")
    incremental_catalog.append(
        {"schema_catalog_sha256": sent_digest, "bundle": sent_bundle}
    )
    _write_jsonl(auto_dir / "actor_schema_catalog.jsonl", incremental_catalog)
    rows = _read_jsonl(auto_dir / "actor_request_audit.jsonl")
    rows[0]["sent_schema_catalog_sha256"] = sent_digest
    rows[0]["sent_schemas_sha256"] = _canonical_sha256(sent_bundle["ordered_schemas"])
    rows[0]["schemas_exact"] = True
    _write_jsonl(auto_dir / "actor_request_audit.jsonl", rows)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="schemas differ from routed schemas",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_matched_experiment_reconciles_actor_usage_links(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    usage_rows = _read_jsonl(auto_dir / "llm_usage_events.jsonl")
    usage_rows[0]["actor_request_id"] = "unknown-request"
    _write_jsonl(auto_dir / "llm_usage_events.jsonl", usage_rows)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="exactly one usage link",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_matched_experiment_recomputes_authority_task_digest(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["tasks"][0]["routed_inventory_sha256"] = "tampered"
    _write_json(authority_path, authority)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="task sequence or digest",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_matched_experiment_revalidates_authority_state_files(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    state_dir = authority_path.parent / authority["tasks"][0]["state_dir"]
    state_dir.rmdir()

    with pytest.raises(
        ActorSelectionVerificationError,
        match="state directory is missing",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


@pytest.mark.parametrize(
    ("invalid_outcome", "message"),
    [
        (None, "Missing outcome value"),
        (True, "Invalid outcome value"),
        ("0.5", "Invalid outcome value"),
        (float("nan"), "Out-of-range outcome value"),
    ],
)
def test_outcome_comparison_rejects_invalid_outcome(
    tmp_path: Path,
    invalid_outcome: object,
    message: str,
) -> None:
    policy_dir, auto_dir, _authority_path = _write_experiment(tmp_path)
    auto = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    auto["per_scenario_results"][1]["outcome_similarity"] = invalid_outcome
    _write_json(auto_dir / "result_summary.json", auto)

    with pytest.raises(
        ActorSelectionVerificationError,
        match=message,
    ):
        compare_outcome_values(
            policy_dir,
            auto_dir,
            expected_scenarios=SCENARIOS,
        )


@pytest.mark.parametrize("location", ["row", "manifest"])
def test_outcome_comparison_rejects_evaluator_identity_drift(
    tmp_path: Path,
    location: str,
) -> None:
    policy_dir, auto_dir, _authority_path = _write_experiment(tmp_path)
    if location == "row":
        _tamper_outcome_row_identity(auto_dir)
    else:
        _tamper_outcome_manifest_identity(auto_dir)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="wrong outcome evaluator|identity mismatch",
    ):
        compare_outcome_values(
            policy_dir,
            auto_dir,
            expected_scenarios=SCENARIOS,
        )


def test_generated_tool_execution_failures_are_diagnostic_only(
    tmp_path: Path,
) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    rows = _read_jsonl(auto_dir / "scenario_tool_selection.jsonl")
    rows[0].update(
        {
            "generated_tools_attempted": ["generated_tool"],
            "generated_tools_failed": ["generated_tool"],
            "generated_tools_called": [],
            "attempted_generated_tool_count": 1,
            "failed_generated_tool_count": 1,
            "called_generated_tool_count": 0,
            "selection_status": "generated_tool_attempt_failed",
        }
    )
    _write_jsonl(auto_dir / "scenario_tool_selection.jsonl", rows)
    selection = json.loads(
        (auto_dir / "selection_summary.json").read_text(encoding="utf-8")
    )
    selection["generated_tool_failed_scenarios"] = 1
    selection["generated_tool_called_scenarios"] = 0
    _write_json(auto_dir / "selection_summary.json", selection)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )

    assert report["mechanism_counts_are_performance_gates"] is False
    assert report["mechanism_diagnostics"]["affects_experiment_pass_fail"] is False
    assert report["mechanism_diagnostics"]["auto"] == {
        "generated_tool_called_scenarios": 0,
        "generated_tool_failed_scenarios": 1,
        "generated_tool_attempted_without_success_scenarios": 0,
    }
    assert report["integrity_gate_passed"] is True
    assert report["experiment_passed"] is True
    assert report["stability_gate_passed"] is True
    assert report["stability_gate_reasons"] == []


def test_pilot_gate_treats_native_followup_preservation_as_diagnostic(
    tmp_path: Path,
) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    summary = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    summary["per_scenario_results"][0]["side_effect_preservation_failures"] = [
        "generated_tool"
    ]
    _write_json(auto_dir / "result_summary.json", summary)
    live = json.loads(
        (auto_dir / "live_result_summary.json").read_text(encoding="utf-8")
    )
    live["per_scenario_results"] = summary["per_scenario_results"]
    _write_json(auto_dir / "live_result_summary.json", live)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )

    assert report["stability_gate_passed"] is True
    assert (
        "auto_side_effect_preservation_failures" not in report["stability_gate_reasons"]
    )
    assert report["auto_execution"]["side_effect_preservation_failure_count"] == 1


def test_selection_summary_counters_are_recomputed_from_raw_rows(
    tmp_path: Path,
) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    summary = json.loads(
        (auto_dir / "selection_summary.json").read_text(encoding="utf-8")
    )
    summary["generated_tool_called_scenarios"] = 2
    _write_json(auto_dir / "selection_summary.json", summary)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="does not match raw rows",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_selection_rows_must_follow_exact_authority_order(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    rows = _read_jsonl(auto_dir / "scenario_tool_selection.jsonl")
    _write_jsonl(auto_dir / "scenario_tool_selection.jsonl", list(reversed(rows)))

    with pytest.raises(
        ActorSelectionVerificationError,
        match="exact task order",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
        )


def test_pilot_generated_tool_attempt_without_success_is_diagnostic_only(
    tmp_path: Path,
) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    rows = _read_jsonl(auto_dir / "scenario_tool_selection.jsonl")
    rows[0].update(
        {
            "generated_tools_attempted": ["generated_tool"],
            "generated_tools_failed": [],
            "generated_tools_called": [],
            "attempted_generated_tool_count": 1,
            "failed_generated_tool_count": 0,
            "called_generated_tool_count": 0,
            "selection_status": "generated_tool_attempted_without_success",
        }
    )
    _write_jsonl(auto_dir / "scenario_tool_selection.jsonl", rows)
    summary = json.loads(
        (auto_dir / "selection_summary.json").read_text(encoding="utf-8")
    )
    summary["generated_tool_called_scenarios"] = 0
    _write_json(auto_dir / "selection_summary.json", summary)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )

    assert report["mechanism_diagnostics"]["auto"] == {
        "generated_tool_called_scenarios": 0,
        "generated_tool_failed_scenarios": 0,
        "generated_tool_attempted_without_success_scenarios": 1,
    }
    assert report["integrity_gate_passed"] is True
    assert report["experiment_passed"] is True
    assert report["stability_gate_passed"] is True
    assert report["stability_gate_reasons"] == []


def test_experiment_rejects_incomplete_outcome_evidence(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    result = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    result["per_scenario_results"][0]["outcome_similarity"] = None
    _write_matching_result_summaries(auto_dir, result)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="Missing outcome value",
    ):
        verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
            require_zero_generated_tool_failures=True,
        )


def test_outcome_difference_is_report_only_without_predeclared_threshold(
    tmp_path: Path,
) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    result = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    for row in result["per_scenario_results"]:
        row["outcome_similarity"] = 0.0
    _write_matching_result_summaries(auto_dir, result)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
    )

    assert report["outcomes"]["auto_minus_policy_mean_outcome_delta"] == -0.125
    assert report["outcome_evidence_complete"] is True
    assert report["performance_gate_applied"] is False
    assert report["experiment_passed"] is True


def test_runtime_exception_fails_integrity_and_overall_status(tmp_path: Path) -> None:
    policy_dir, auto_dir, authority_path = _write_experiment(tmp_path)
    result = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    result["per_scenario_results"][0]["exception_type"] = "RuntimeError"
    result["per_scenario_results"][0]["traceback"] = "synthetic traceback"
    _write_matching_result_summaries(auto_dir, result)

    report = verify_matched_actor_selection_experiment(
        policy_dir=policy_dir,
        auto_dir=auto_dir,
        authority_path=authority_path,
        require_zero_generated_tool_failures=True,
    )

    assert report["outcome_evidence_complete"] is True
    assert report["performance_gate_applied"] is False
    assert report["integrity_gate_passed"] is False
    assert report["integrity_gate_reasons"] == ["auto_runtime_exceptions"]
    assert report["experiment_passed"] is False
    assert report["stability_gate_passed"] is False


def test_live_run_rejects_cache_artifact(tmp_path: Path) -> None:
    policy_dir, _auto_dir, _authority_path = _write_experiment(tmp_path)
    _write_json(policy_dir / "openai_response_cache_metrics.json", {"hits": 0})

    with pytest.raises(
        ActorSelectionVerificationError,
        match="forbidden persistent response-cache artifact",
    ):
        validate_live_uncached_run(
            policy_dir,
            expected_scenarios=SCENARIOS,
        )


@pytest.mark.parametrize("arm_name", ["policy", "auto"])
def test_live_run_rejects_malformed_retry_count_in_both_arms(
    tmp_path: Path,
    arm_name: str,
) -> None:
    policy_dir, auto_dir, _authority_path = _write_experiment(tmp_path)
    run_dir = policy_dir if arm_name == "policy" else auto_dir
    result = json.loads((run_dir / "result_summary.json").read_text(encoding="utf-8"))
    result["per_scenario_results"][0]["transient_retry_count"] = True
    _write_matching_result_summaries(run_dir, result)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="invalid or missing transient_retry_count",
    ):
        validate_live_uncached_run(
            run_dir,
            expected_scenarios=SCENARIOS,
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_chain", "invalid exception_chain_type_names"),
        ("non_string_reason_kind", "reason outside the producer allowlist"),
        ("marker_absent", "does not contain its classified marker"),
        ("null_archive", "invalid or missing archive_path"),
        ("wrong_archive", "not the exact expected trajectory directory"),
    ],
)
def test_auto_live_run_rejects_malformed_retry_provenance(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    _policy_dir, auto_dir, _authority_path = _write_experiment(tmp_path)
    result = json.loads((auto_dir / "result_summary.json").read_text(encoding="utf-8"))
    row = result["per_scenario_results"][0]
    archive = auto_dir / "trajectories" / "task_a__transient_retry_failed_attempt_1"
    archive.mkdir(parents=True)
    failure = {
        "attempt": 1,
        "exception_type": "APIConnectionError",
        "exception_message": "connection reset",
        "traceback": "Traceback: openai.APIConnectionError: connection reset",
        "exception_chain_type_names": ["APIConnectionError"],
        "retry_reason": {
            "kind": "exception_chain_type",
            "identifier": "APIConnectionError",
        },
        "archive_path": str(archive),
    }
    row["transient_retry_count"] = 1
    row["transient_retry_archives"] = [str(archive)]
    row["transient_retry_failures"] = [failure]
    if case == "missing_chain":
        failure.pop("exception_chain_type_names")
    elif case == "non_string_reason_kind":
        failure["retry_reason"]["kind"] = []
    elif case == "marker_absent":
        failure["exception_type"] = "WrapperError"
        failure["exception_chain_type_names"] = ["WrapperError"]
        failure["retry_reason"] = {
            "kind": "traceback_marker",
            "identifier": "read_timeout",
        }
        failure["traceback"] = "Traceback: no transient marker"
    elif case == "null_archive":
        failure["archive_path"] = None
    elif case == "wrong_archive":
        wrong_archive = auto_dir / "trajectories" / "forged"
        wrong_archive.mkdir()
        failure["archive_path"] = str(wrong_archive)
        row["transient_retry_archives"] = [str(wrong_archive)]
    _write_matching_result_summaries(auto_dir, result)

    with pytest.raises(ActorSelectionVerificationError, match=message):
        validate_live_uncached_run(
            auto_dir,
            expected_scenarios=SCENARIOS,
            allow_generation_source=False,
        )


def test_live_run_reconciles_raw_usage_with_result_rows(tmp_path: Path) -> None:
    policy_dir, _auto_dir, _authority_path = _write_experiment(tmp_path)
    result = json.loads(
        (policy_dir / "result_summary.json").read_text(encoding="utf-8")
    )
    result["per_scenario_results"][0]["llm_prompt_tokens"] = 11
    _write_json(policy_dir / "result_summary.json", result)
    live = json.loads(
        (policy_dir / "live_result_summary.json").read_text(encoding="utf-8")
    )
    live["per_scenario_results"] = result["per_scenario_results"]
    _write_json(policy_dir / "live_result_summary.json", live)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="do not match the result row",
    ):
        validate_live_uncached_run(
            policy_dir,
            expected_scenarios=SCENARIOS,
        )


def test_live_run_reconciles_usage_summary_with_raw_events(tmp_path: Path) -> None:
    policy_dir, _auto_dir, _authority_path = _write_experiment(tmp_path)
    summary = json.loads(
        (policy_dir / "llm_usage_summary.json").read_text(encoding="utf-8")
    )
    summary["llm_total_tokens"] += 1
    _write_json(policy_dir / "llm_usage_summary.json", summary)

    with pytest.raises(
        ActorSelectionVerificationError,
        match="does not match raw events",
    ):
        validate_live_uncached_run(
            policy_dir,
            expected_scenarios=SCENARIOS,
        )


def test_auto_replay_rejects_arm_specific_generation_usage(tmp_path: Path) -> None:
    _policy_dir, auto_dir, _authority_path = _write_experiment(tmp_path)
    rows = _read_jsonl(auto_dir / "llm_usage_events.jsonl")
    rows[0]["source"] = "sage_generation"
    _write_jsonl(auto_dir / "llm_usage_events.jsonl", rows)

    with pytest.raises(ActorSelectionVerificationError, match="invalid source"):
        validate_live_uncached_run(
            auto_dir,
            expected_scenarios=SCENARIOS,
            allow_generation_source=False,
        )
