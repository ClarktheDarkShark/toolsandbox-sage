import json
from pathlib import Path

from sage_ts.dashboard.exporters import write_protocol_dashboard


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
    )


def test_write_protocol_dashboard_exports_paired_data(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    control = run_root / "control" / "control_run"
    candidate = run_root / "candidate" / "candidate_run"
    registry = run_root / "registry"
    registry.mkdir(parents=True)
    _write_summary(
        control,
        [
            {
                "name": "a",
                "similarity": 0.2,
                "turn_count": 6,
                "categories": ["CANONICALIZATION"],
            },
            {"name": "b", "similarity": 1.0, "turn_count": 4, "categories": []},
        ],
    )
    _write_summary(
        candidate,
        [
            {
                "name": "a",
                "similarity": 1.0,
                "turn_count": 4,
                "categories": ["CANONICALIZATION"],
            },
            {"name": "b", "similarity": 0.5, "turn_count": 5, "categories": []},
        ],
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        json.dumps({"scenario": "a", "tool_name": "helper"}) + "\n",
        encoding="utf-8",
    )

    index = write_protocol_dashboard(
        run_root,
        mode="mechanism_40",
        status="complete",
        phase="comparison",
        agent="gpt-5-mini",
        user="GPT_4_o_2024_05_13",
        generation_enabled=True,
        base_tool_policy="recency_reduced",
        scenario_count=2,
        control_dir=control,
        candidate_dir=candidate,
        registry_dir=registry,
    )

    assert index.exists()
    data = json.loads((index.parent / "data.json").read_text(encoding="utf-8"))
    assert data["comparison"]["gain_count"] == 1
    assert data["comparison"]["regression_count"] == 1
    assert data["candidate"]["accepted_tool_count"] == 1
    assert data["candidate"]["reuse_count"] == 1
    assert data["scenarios"][0]["reused_tools"] == ["helper"]
