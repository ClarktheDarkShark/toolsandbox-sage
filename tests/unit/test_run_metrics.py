import json
import os
from pathlib import Path

import pytest

from sage_ts.evaluation.llm_usage import summarize_events
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
    assert summary["llm_completion_tokens"] == 0
    assert summary["llm_total_tokens"] == 0


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
