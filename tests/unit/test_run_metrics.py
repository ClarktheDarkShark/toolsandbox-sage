import json
import os
from pathlib import Path

import pytest

import sage_ts.evaluation.run_metrics as run_metrics
from sage_ts.evaluation.llm_usage import (
    _usage_payload,
    audit_actor_request,
    record_chat_completion_usage,
    reset_llm_usage,
    summarize_events,
    write_llm_usage_artifacts,
)
from sage_ts.evaluation.run_metrics import compare_runs, summarize_run


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
    )


def test_summarize_run_counts_birth_and_reuse_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_summary(
        run_dir,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
                "turn_count": 3,
            },
            {
                "name": "b",
                "similarity": 0.0,
                "outcome_similarity": 0.75,
                "turn_count": 5,
            },
        ],
    )
    (run_dir / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "reuse_events.jsonl").write_text(
        json.dumps({"scenario": "b", "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "scenario_tool_selection.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "scenario": "a",
                        "generated_tools_visible": [],
                        "generated_tools_called": [],
                        "selection_status": "no_visible_generated_tools",
                        "similarity": 1.0,
                        "outcome_similarity": 1.0,
                        "failure_after_selection": False,
                        "failure_after_outcome_selection": False,
                    }
                ),
                json.dumps(
                    {
                        "scenario": "b",
                        "generated_tools_visible": ["helper"],
                        "generated_tools_called": ["helper"],
                        "selection_status": "generated_tool_called",
                        "similarity": 0.0,
                        "outcome_similarity": 0.75,
                        "failure_after_selection": True,
                        "failure_after_outcome_selection": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = summarize_run(run_dir)

    assert metrics["scenario_count"] == 2
    assert metrics["success_count"] == 1
    assert metrics["outcome_score_available_count"] == 2
    assert metrics["mean_outcome_similarity"] == 0.875
    assert metrics["accepted_tool_count"] == 1
    assert metrics["reuse_count"] == 1
    assert metrics["reused_tools"] == ["helper"]
    assert metrics["generated_tool_visible_scenarios"] == 1
    assert metrics["generated_tool_called_scenarios"] == 1
    assert metrics["generated_tool_visible_not_called_scenarios"] == 0
    assert metrics["generated_tool_selection_failures"][0]["scenario"] == "b"
    assert metrics["generated_tool_outcome_selection_failures"][0]["scenario"] == "b"


def test_summarize_run_aggregates_llm_usage_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_summary(
        run_dir,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "turn_count": 3,
                "llm_usage_recorded": True,
                "llm_call_count": 2,
                "llm_live_call_count": 2,
                "llm_cached_call_count": 0,
                "llm_prompt_tokens": 100,
                "llm_provider_cached_prompt_tokens": 64,
                "llm_provider_cached_prompt_call_count": 1,
                "llm_provider_cached_prompt_tokens_available_count": 2,
                "llm_completion_tokens": 30,
                "llm_total_tokens": 130,
                "llm_usage_available_count": 2,
            },
            {
                "name": "b",
                "similarity": 0.0,
                "turn_count": 5,
                "llm_usage_recorded": True,
                "llm_call_count": 1,
                "llm_live_call_count": 0,
                "llm_cached_call_count": 1,
                "llm_prompt_tokens": 40,
                "llm_provider_cached_prompt_tokens": 0,
                "llm_provider_cached_prompt_call_count": 0,
                "llm_provider_cached_prompt_tokens_available_count": 1,
                "llm_completion_tokens": 10,
                "llm_total_tokens": 50,
                "llm_usage_available_count": 1,
            },
        ],
    )

    metrics = summarize_run(run_dir)

    assert metrics["llm_usage_recorded"] is True
    assert metrics["llm_call_count"] == 3
    assert metrics["llm_live_call_count"] == 2
    assert metrics["llm_cached_call_count"] == 1
    assert metrics["llm_prompt_tokens"] == 140
    assert metrics["llm_provider_cached_prompt_tokens"] == 64
    assert metrics["llm_provider_cached_prompt_call_count"] == 1
    assert metrics["llm_provider_cached_prompt_tokens_available_count"] == 3
    assert metrics["llm_completion_tokens"] == 40
    assert metrics["llm_total_tokens"] == 180
    assert metrics["llm_usage_available_count"] == 3


def test_summarize_run_exports_wall_time_seconds(tmp_path: Path) -> None:
    run_dir = tmp_path / "control" / "control_run"
    _write_summary(
        run_dir,
        [{"name": "a", "similarity": 1.0, "turn_count": 3}],
    )
    (run_dir.parent / "sage_ts_run_manifest.json").write_text(
        json.dumps({"started_at": "2026-05-31T12:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "live_result_summary.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-31T12:02:30+00:00",
                "per_scenario_results": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = summarize_run(run_dir)

    assert metrics["wall_time_seconds"] == pytest.approx(150.0)


def test_summarize_run_adds_checkpoint_resume_wall_time(tmp_path: Path) -> None:
    previous_dir = tmp_path / "previous" / "candidate" / "previous_run"
    current_dir = tmp_path / "current" / "candidate" / "current_run"
    _write_summary(
        previous_dir,
        [
            {"name": "a", "similarity": 1.0, "turn_count": 3},
            {"name": "b", "similarity": 1.0, "turn_count": 3},
        ],
    )
    _write_summary(
        current_dir,
        [
            {"name": "a", "similarity": 1.0, "turn_count": 3},
            {"name": "b", "similarity": 1.0, "turn_count": 3},
            {"name": "c", "similarity": 1.0, "turn_count": 3},
        ],
    )
    (previous_dir.parent / "sage_ts_run_manifest.json").write_text(
        json.dumps({"started_at": "2026-05-31T12:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    checkpoint = (
        previous_dir / "registry_checkpoints" / "after_0002_b" / "checkpoint.json"
    )
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(
        json.dumps({"completed_count": 2, "scenario": "b"}) + "\n",
        encoding="utf-8",
    )
    checkpoint_time = 1_780_228_980.0
    checkpoint.touch()
    os.utime(checkpoint, (checkpoint_time, checkpoint_time))
    (current_dir.parent / "sage_ts_run_manifest.json").write_text(
        json.dumps(
            {
                "started_at": "2026-05-31T13:00:00+00:00",
                "resume_from_dir": str(previous_dir),
                "resume_completed_limit": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (current_dir / "live_result_summary.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-05-31T13:05:00+00:00",
                "per_scenario_results": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = summarize_run(current_dir)

    previous_started_at = 1_780_228_800.0
    assert metrics["wall_time_seconds"] == pytest.approx(
        (checkpoint_time - previous_started_at) + 300.0
    )
    assert metrics["wall_time_resume_offset_seconds"] == pytest.approx(
        checkpoint_time - previous_started_at
    )


def test_empty_llm_usage_snapshot_exports_explicit_zero_counts() -> None:
    summary = summarize_events([])

    assert summary["llm_usage_recorded"] is False
    assert summary["llm_call_count"] == 0
    assert summary["llm_live_call_count"] == 0
    assert summary["llm_cached_call_count"] == 0
    assert summary["llm_prompt_tokens"] == 0
    assert summary["llm_provider_cached_prompt_tokens"] == 0
    assert summary["llm_provider_cached_prompt_call_count"] == 0
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 0
    assert summary["llm_completion_tokens"] == 0
    assert summary["llm_total_tokens"] == 0


def test_usage_payload_separates_provider_prefix_cache_from_response_replay() -> None:
    payload = _usage_payload(
        {
            "usage": {
                "prompt_tokens": 256,
                "completion_tokens": 12,
                "total_tokens": 268,
                "prompt_tokens_details": {"cached_tokens": 128},
            }
        }
    )

    assert payload["provider_cached_prompt_tokens"] == 128
    assert payload["prompt_tokens"] == 256


def test_llm_usage_artifact_schema_records_provider_prefix_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_TS_CURRENT_SCENARIO", "task_a")
    reset_llm_usage(run_dir=tmp_path, arm="control")
    record_chat_completion_usage(
        source="toolsandbox_agent",
        model="gpt-4o-mini",
        messages=[],
        response={
            "usage": {
                "prompt_tokens": 256,
                "completion_tokens": 12,
                "total_tokens": 268,
                "prompt_tokens_details": {"cached_tokens": 128},
            }
        },
    )
    write_llm_usage_artifacts()
    summary = json.loads(
        (tmp_path / "llm_usage_summary.json").read_text(encoding="utf-8")
    )

    assert summary["schema_version"] == 2
    assert summary["llm_provider_cached_prompt_tokens"] == 128
    assert summary["llm_provider_cached_prompt_call_count"] == 1
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 1
    reset_llm_usage()


def test_expected_auto_actor_usage_without_request_audit_fails_closed(
    tmp_path: Path,
) -> None:
    reset_llm_usage(
        run_dir=tmp_path,
        arm="sage_auto_selection",
        expected_actor_selection_mode="auto",
    )
    record_chat_completion_usage(
        source="toolsandbox_agent",
        model="gpt-4o-mini",
        messages=[],
        response={"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    )

    with pytest.raises(AssertionError, match="does not cover agent inference"):
        write_llm_usage_artifacts(finalize=False)

    summary = json.loads(
        (tmp_path / "actor_request_audit_summary.json").read_text(encoding="utf-8")
    )
    assert summary["expected_actor_selection_mode"] == "auto"
    assert summary["coverage_verified"] is False
    assert summary["agent_call_count"] == 1
    assert summary["unlinked_agent_call_count"] == 1
    reset_llm_usage()


def test_expected_auto_actor_mode_rejects_linked_policy_audit(
    tmp_path: Path,
) -> None:
    reset_llm_usage(
        run_dir=tmp_path,
        arm="sage_auto_selection",
        expected_actor_selection_mode="auto",
    )
    with audit_actor_request(
        choice_mode="policy",
        model="gpt-4o-mini",
        messages=[],
        routed_schemas=[],
        routed_native_schemas=[],
        routed_generated_schemas=[],
        routed_schema_classification=[],
        sent_schemas=[],
        sent_native_schemas=[],
        sent_generated_schemas=[],
        sent_schema_classification=[],
        named_tool_choice=None,
    ):
        record_chat_completion_usage(
            source="toolsandbox_agent",
            model="gpt-4o-mini",
            messages=[],
            tools=[],
            response={"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )

    with pytest.raises(AssertionError, match="mode_mismatches"):
        write_llm_usage_artifacts(finalize=True)

    summary = json.loads(
        (tmp_path / "actor_request_audit_summary.json").read_text(encoding="utf-8")
    )
    assert summary["coverage_verified"] is False
    assert summary["mode_mismatch_request_ids"] == ["actor-request-000001"]
    reset_llm_usage()


def test_legacy_policy_actor_usage_without_request_audit_remains_supported(
    tmp_path: Path,
) -> None:
    reset_llm_usage(
        run_dir=tmp_path,
        arm="legacy_policy",
        expected_actor_selection_mode="policy",
    )
    record_chat_completion_usage(
        source="toolsandbox_agent",
        model="legacy-alias",
        messages=[],
        response={"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    )

    write_llm_usage_artifacts(finalize=True)

    summary = json.loads(
        (tmp_path / "actor_request_audit_summary.json").read_text(encoding="utf-8")
    )
    assert summary["expected_actor_selection_mode"] == "policy"
    assert summary["coverage_verified"] is False
    assert summary["agent_call_count"] == 1
    assert summary["unlinked_agent_call_count"] == 1
    reset_llm_usage()


def test_llm_usage_summary_exposes_partial_provider_metadata() -> None:
    summary = summarize_events(
        [
            {
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "provider_cached_prompt_tokens": 64,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
            },
            {
                "response_cache_status": "live",
                "prompt_tokens": 50,
                "provider_cached_prompt_tokens": None,
                "completion_tokens": 5,
                "total_tokens": 55,
                "usage_available": True,
            },
        ]
    )

    assert summary["llm_call_count"] == 2
    assert summary["llm_provider_cached_prompt_tokens"] == 64
    assert summary["llm_provider_cached_prompt_call_count"] == 1
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_nonempty_usage_without_provider_metadata_reports_unavailable() -> None:
    summary = summarize_events(
        [
            {
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 50,
                "completion_tokens": 5,
                "total_tokens": 55,
                "usage_available": True,
            }
        ]
    )

    assert summary["llm_provider_cached_prompt_tokens"] is None
    assert summary["llm_provider_cached_prompt_call_count"] is None
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 0
    source = summary["llm_usage_by_source"]["toolsandbox_agent"]
    assert source["llm_provider_cached_prompt_tokens"] is None
    assert source["llm_provider_cached_prompt_call_count"] is None
    assert source["llm_provider_cached_prompt_tokens_available_count"] == 0


def test_summarize_run_backfills_legacy_provider_metadata_from_raw_events(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "legacy_run"
    _write_summary(
        run_dir,
        [
            {
                "name": "task_a",
                "similarity": 1.0,
                "turn_count": 2,
                "llm_usage_recorded": True,
                "llm_call_count": 1,
                "llm_live_call_count": 1,
                "llm_cached_call_count": 0,
                "llm_prompt_tokens": 256,
                "llm_completion_tokens": 12,
                "llm_total_tokens": 268,
                "llm_usage_available_count": 1,
            }
        ],
    )
    (run_dir / "llm_usage_events.jsonl").write_text(
        json.dumps(
            {
                "scenario": "task_a",
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 256,
                "completion_tokens": 12,
                "total_tokens": 268,
                "usage_available": True,
                "raw_usage": {
                    "prompt_tokens": 256,
                    "completion_tokens": 12,
                    "total_tokens": 268,
                    "prompt_tokens_details": {"cached_tokens": 128},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = summarize_run(run_dir)

    assert metrics["llm_provider_cached_prompt_tokens"] == 128
    assert metrics["llm_provider_cached_prompt_call_count"] == 1
    assert metrics["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_legacy_source_summary_is_replaced_by_reconciled_event_summary(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "legacy_source_run"
    rows = [
        {
            "name": "task_a",
            "similarity": 1.0,
            "llm_usage_recorded": True,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 100,
            "llm_provider_cached_prompt_tokens": 64,
            "llm_provider_cached_prompt_call_count": 1,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 110,
            "llm_usage_available_count": 1,
        }
    ]
    _write_summary(run_dir, rows)
    (run_dir / "llm_usage_summary.json").write_text(
        json.dumps(
            {
                "llm_usage_by_source": {
                    "toolsandbox_agent": {
                        "llm_call_count": 1,
                        "llm_prompt_tokens": 100,
                        "llm_provider_cached_prompt_tokens": None,
                        "llm_provider_cached_prompt_call_count": None,
                        "llm_provider_cached_prompt_tokens_available_count": 0,
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "llm_usage_events.jsonl").write_text(
        json.dumps(
            {
                "scenario": "task_a",
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "provider_cached_prompt_tokens": 64,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_metrics._llm_usage_summary(rows, run_dir)

    source = summary["llm_usage_by_source"]["toolsandbox_agent"]
    assert source["llm_provider_cached_prompt_tokens"] == 64
    assert source["llm_provider_cached_prompt_call_count"] == 1
    assert source["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_legacy_source_backfill_never_downgrades_known_provider_values(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "legacy_richer_source_run"
    rows = [
        {
            "name": "task_a",
            "llm_usage_recorded": True,
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": 100,
            "llm_provider_cached_prompt_tokens": 64,
            "llm_provider_cached_prompt_call_count": 1,
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": 10,
            "llm_total_tokens": 110,
            "llm_usage_available_count": 1,
        }
    ]
    _write_summary(run_dir, rows)
    (run_dir / "llm_usage_summary.json").write_text(
        json.dumps(
            {
                "llm_usage_by_source": {
                    "toolsandbox_agent": {
                        "llm_call_count": 1,
                        "llm_provider_cached_prompt_tokens": 64,
                        "llm_provider_cached_prompt_call_count": 1,
                        "llm_provider_cached_prompt_tokens_available_count": 1,
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "llm_usage_events.jsonl").write_text(
        json.dumps(
            {
                "scenario": "task_a",
                "source": "toolsandbox_agent",
                "response_cache_status": "live",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "usage_available": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_metrics._llm_usage_summary(rows, run_dir)

    source = summary["llm_usage_by_source"]["toolsandbox_agent"]
    assert source["llm_provider_cached_prompt_tokens"] == 64
    assert source["llm_provider_cached_prompt_call_count"] == 1
    assert source["llm_provider_cached_prompt_tokens_available_count"] == 1


def test_missing_event_backfill_never_downgrades_known_provider_values(
    tmp_path: Path,
) -> None:
    summary = run_metrics._llm_usage_summary(
        [
            {
                "name": "task_a",
                "llm_usage_recorded": True,
                "llm_call_count": 1,
                "llm_live_call_count": 1,
                "llm_cached_call_count": 0,
                "llm_prompt_tokens": 100,
                "llm_provider_cached_prompt_tokens": 64,
                "llm_provider_cached_prompt_call_count": 1,
                "llm_provider_cached_prompt_tokens_available_count": 0,
                "llm_completion_tokens": 10,
                "llm_total_tokens": 110,
                "llm_usage_available_count": 1,
            }
        ],
        tmp_path,
    )

    assert summary["llm_provider_cached_prompt_tokens"] == 64
    assert summary["llm_provider_cached_prompt_call_count"] == 1
    assert summary["llm_provider_cached_prompt_tokens_available_count"] == 0


def test_current_provider_fields_do_not_parse_cumulative_usage_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_read(_path: Path) -> list[dict[str, object]]:
        raise AssertionError(
            "current provider fields must not trigger event-log parsing"
        )

    monkeypatch.setattr(run_metrics, "_read_jsonl", fail_if_read)
    summary = run_metrics._llm_usage_summary(
        [
            {
                "name": "task_a",
                "llm_usage_recorded": True,
                "llm_call_count": 1,
                "llm_live_call_count": 1,
                "llm_cached_call_count": 0,
                "llm_prompt_tokens": 100,
                "llm_provider_cached_prompt_tokens": 64,
                "llm_provider_cached_prompt_call_count": 1,
                "llm_provider_cached_prompt_tokens_available_count": 1,
                "llm_completion_tokens": 10,
                "llm_total_tokens": 110,
                "llm_usage_available_count": 1,
            }
        ],
        tmp_path,
    )

    assert summary["llm_provider_cached_prompt_tokens"] == 64


def test_compare_runs_reports_gain_and_regression(tmp_path: Path) -> None:
    control_dir = tmp_path / "control"
    candidate_dir = tmp_path / "candidate"
    _write_summary(
        control_dir,
        [
            {
                "name": "a",
                "similarity": 0.0,
                "outcome_similarity": 0.8,
                "turn_count": 4,
                "llm_call_count": 2,
                "llm_total_tokens": 100,
            },
            {
                "name": "b",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
                "turn_count": 4,
            },
        ],
    )
    _write_summary(
        candidate_dir,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "outcome_similarity": 1.0,
                "turn_count": 3,
                "llm_call_count": 3,
                "llm_total_tokens": 150,
            },
            {
                "name": "b",
                "similarity": 0.0,
                "outcome_similarity": 1.0,
                "turn_count": 5,
            },
        ],
    )

    comparison = compare_runs(control_dir, candidate_dir)

    assert comparison["gain_count"] == 1
    assert comparison["regression_count"] == 1
    assert comparison["gains"][0]["scenario"] == "a"
    assert comparison["regressions"][0]["scenario"] == "b"
    assert comparison["outcome_gain_count"] == 1
    assert comparison["outcome_regression_count"] == 0
    assert comparison["outcome_preserved_count"] == 1
    assert comparison["mean_outcome_similarity_delta"] == pytest.approx(0.1)
    assert comparison["outcome_gains"][0]["scenario"] == "a"
    assert comparison["gains"][0]["control_llm_call_count"] == 2
    assert comparison["gains"][0]["candidate_llm_total_tokens"] == 150


def test_compare_runs_rejects_unmatched_or_partial_arms(tmp_path: Path) -> None:
    control_dir = tmp_path / "control"
    candidate_dir = tmp_path / "candidate"
    _write_summary(
        control_dir,
        [
            {"name": "a", "similarity": 0.0, "turn_count": 4},
            {"name": "b", "similarity": 1.0, "turn_count": 4},
        ],
    )
    _write_summary(
        candidate_dir,
        [{"name": "a", "similarity": 1.0, "turn_count": 3}],
    )

    with pytest.raises(ValueError, match="paired_run_mismatch"):
        compare_runs(control_dir, candidate_dir)


def test_compare_runs_can_compare_partial_shared_prefix_for_live_dashboard(
    tmp_path: Path,
) -> None:
    control_dir = tmp_path / "control"
    candidate_dir = tmp_path / "candidate"
    _write_summary(
        control_dir,
        [
            {"name": "a", "similarity": 0.0, "turn_count": 4},
            {"name": "b", "similarity": 1.0, "turn_count": 4},
        ],
    )
    _write_summary(
        candidate_dir,
        [{"name": "a", "similarity": 1.0, "turn_count": 3}],
    )

    comparison = compare_runs(
        control_dir,
        candidate_dir,
        require_complete_match=False,
    )

    assert comparison["scenario_count"] == 1
    assert comparison["gain_count"] == 1
    assert comparison["gains"][0]["scenario"] == "a"
