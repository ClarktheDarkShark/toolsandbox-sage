import json
from pathlib import Path

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
            {"name": "a", "similarity": 1.0, "turn_count": 3},
            {"name": "b", "similarity": 0.0, "turn_count": 5},
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

    metrics = summarize_run(run_dir)

    assert metrics["scenario_count"] == 2
    assert metrics["success_count"] == 1
    assert metrics["accepted_tool_count"] == 1
    assert metrics["reuse_count"] == 1
    assert metrics["reused_tools"] == ["helper"]


def test_compare_runs_reports_gain_and_regression(tmp_path: Path) -> None:
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
        [
            {"name": "a", "similarity": 1.0, "turn_count": 3},
            {"name": "b", "similarity": 0.0, "turn_count": 5},
        ],
    )

    comparison = compare_runs(control_dir, candidate_dir)

    assert comparison["gain_count"] == 1
    assert comparison["regression_count"] == 1
    assert comparison["gains"][0]["scenario"] == "a"
    assert comparison["regressions"][0]["scenario"] == "b"
