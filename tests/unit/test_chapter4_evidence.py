from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from scripts.research.chapter4_evidence import (
    build_evidence_data,
    load_run_evidence,
    write_evidence_dashboard,
)

RENDERER_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "render_chapter4_evidence_tables.py"
)
RENDERER_SPEC = importlib.util.spec_from_file_location(
    "render_chapter4_evidence_tables",
    RENDERER_PATH,
)
assert RENDERER_SPEC is not None and RENDERER_SPEC.loader is not None
renderer = importlib.util.module_from_spec(RENDERER_SPEC)
RENDERER_SPEC.loader.exec_module(renderer)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run(
    root: Path,
    *,
    control_outcomes: list[float],
    candidate_outcomes: list[float],
    called_indices: set[int],
    registry_dir: Path,
    generation_enabled: bool,
) -> None:
    scenarios = [f"task_{index}" for index in range(len(control_outcomes))]
    deltas = []
    pairs = []
    for index, scenario in enumerate(scenarios):
        control = control_outcomes[index]
        candidate = candidate_outcomes[index]
        deltas.append(
            {
                "scenario": scenario,
                "control_similarity": control,
                "candidate_similarity": candidate,
                "delta": candidate - control,
                "control_outcome_similarity": control,
                "candidate_outcome_similarity": candidate,
                "outcome_delta": candidate - control,
            }
        )
        generated = ["normalize_visible_record"] if index in called_indices else []
        pairs.append(
            {
                "scenario": scenario,
                "control": {"generated_tools": [], "generated_tool_events": []},
                "candidate": {
                    "generated_tools": generated,
                    "generated_tool_events": (
                        [{"kind": "called", "tool": generated[0]}] if generated else []
                    ),
                },
            }
        )
    control_mean = sum(control_outcomes) / len(control_outcomes)
    candidate_mean = sum(candidate_outcomes) / len(candidate_outcomes)
    _write_json(
        root / "paired_comparison.json",
        {
            "scenario_count": len(scenarios),
            "control_mean_similarity": control_mean,
            "candidate_mean_similarity": candidate_mean,
            "control_mean_outcome_similarity": control_mean,
            "candidate_mean_outcome_similarity": candidate_mean,
            "deltas": deltas,
            "runtime_exception_count": 0,
        },
    )
    _write_json(
        root / "dashboard" / "task_compare_data.json",
        {
            "summary": {
                "scenario_count": len(scenarios),
                "balanced_completed": len(scenarios),
                "balanced_control_mean_similarity": control_mean,
                "balanced_candidate_mean_similarity": candidate_mean,
                "balanced_control_mean_outcome_similarity": control_mean,
                "balanced_candidate_mean_outcome_similarity": candidate_mean,
                "accepted_tools": 1,
                "reuse_count": 3,
                "generated_tool_called_scenarios": len(called_indices),
                "generated_tool_failed_scenarios": 0,
                "current_exceptions": 0,
            },
            "pairs": pairs,
        },
    )
    _write_json(
        root / "helper_contribution_summary.json",
        {
            "helpers": {
                "normalize_visible_record": {
                    "visible_count": 2,
                    "called_count": len(called_indices),
                    "failed_attempt_count": 0,
                    "side_effect_incidents": [],
                    "called_subset": {
                        "mean_outcome_delta": 0.6,
                        "outcome_gains": len(called_indices),
                        "outcome_regressions": 0,
                        "outcome_preserved": 0,
                    },
                }
            }
        },
    )
    _write_json(
        root / "protocol_manifest.json",
        {
            "scenario_count": len(scenarios),
            "generation_enabled": generation_enabled,
            "native_action_tools_enabled": True,
            "registry_dir": str(registry_dir),
            "run_affecting_sage_env": {
                "SAGE_PRAXIS_BRIDGE_POLICY": "disabled",
                "SAGE_DISABLE_SCENARIO_NAME_BIRTH": "1",
                "SAGE_DISABLE_SCENARIO_NAME_ROUTING": "1",
                "SAGE_SCENARIO_METADATA_POLICY": "visible_context",
            },
        },
    )
    _write_json(
        registry_dir / "registry_manifest.json",
        {
            "tools": {
                "normalize_visible_record": {
                    "retired": False,
                    "reuse_count": 3,
                    "code_hash": "abc123",
                    "validation": {"accepted": True},
                }
            }
        },
    )
    (root / "dashboard" / "task_compare.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )


def test_builds_hypothesis_metrics_and_drilldowns(tmp_path: Path) -> None:
    online = tmp_path / "outputs" / "online" / "online_build_full_1"
    frozen = tmp_path / "outputs" / "frozen" / "full_benchmark_1"
    online_registry = tmp_path / "artifacts" / "online_registry"
    frozen_registry = tmp_path / "artifacts" / "frozen_registry"
    _run(
        online,
        control_outcomes=[0.2, 0.8],
        candidate_outcomes=[0.8, 0.8],
        called_indices={0},
        registry_dir=online_registry,
        generation_enabled=True,
    )
    _run(
        frozen,
        control_outcomes=[0.2, 0.8],
        candidate_outcomes=[0.68, 0.8],
        called_indices={0},
        registry_dir=frozen_registry,
        generation_enabled=False,
    )
    manifest = {
        "campaign_id": "test_campaign",
        "model": "gpt-4o-mini",
        "benchmark_label": "Synthetic test benchmark",
        "expected_online_runs": 1,
        "expected_frozen_runs": 1,
        "baseline_cache": "artifacts/baseline",
        "statistical_plan": {
            "hypothesis_1_threshold_percent": 70,
            "hypothesis_2_threshold_percent": 50,
            "hypothesis_3_threshold_percent": 250,
        },
        "run_pairs": [
            {
                "replication": 1,
                "online": {
                    "run_root": str(online),
                    "registry_dir": str(online_registry),
                },
                "frozen": {
                    "run_root": str(frozen),
                    "registry_dir": str(frozen_registry),
                },
            }
        ],
    }
    data = build_evidence_data(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        bootstrap_iterations=200,
        randomization_iterations=200,
        seed=7,
    )

    assert data["campaign"]["paired_observations"] == 2
    assert data["schema_version"] == 2
    assert data["performance"]["baseline"] == pytest.approx(0.5)
    assert data["performance"]["sage"] == pytest.approx(0.8)
    assert data["performance"]["frozen_sage"] == pytest.approx(0.74)
    assert data["performance"]["outcome_lift_label"] == "+60.0%"
    assert data["hypotheses"][0]["value_label"] == "80.0%"
    assert data["hypotheses"][0]["estimate_percent"] == pytest.approx(80.0)
    assert data["hypotheses"][0]["threshold_percent"] == pytest.approx(70.0)
    assert data["hypotheses"][0]["sample_size"] == 1
    assert data["hypotheses"][0]["decision_label"] == "Supported"
    assert data["hypotheses"][1]["value_label"] == "+60.0%"
    assert data["hypotheses"][2]["value_label"] == "+300.0%"
    assert data["hypotheses"][2]["baseline_mean"] == pytest.approx(0.2)
    assert data["hypotheses"][2]["sage_mean"] == pytest.approx(0.8)
    assert data["statistics"]["matched_task_observations"] == 2
    assert data["integrity"]["counts"]["shortcut_violations"] == 0
    assert data["tool_failure_summary"] == {
        "completed_online_runs": 1,
        "failed_scenarios": 0,
        "tools": [],
    }
    assert data["tool_metrics"][1]["value_label"] == "1"
    assert data["tools"][0]["later_calls"] == 3
    assert data["tools"][0]["failures"] == 0
    assert data["tools"][0]["detail"]["sections"]

    tables = {table["filename"]: table for table in renderer.build_tables(data)}
    campaign_rows = tables["table_4_1_evidence_campaign.png"]["rows"]
    assert campaign_rows[-2] == [
        "Performance endpoint",
        "Outcome / task completion",
        "Sole performance criterion: requested final result achieved.",
    ]
    assert campaign_rows[-1][0] == "Descriptive audit"
    assert "not an acceptance or performance criterion" in campaign_rows[-1][2]
    h1_rows = tables["table_4_3_h1_frozen_registry_retention.png"]["rows"]
    assert h1_rows[0][1] == "80.0%"
    assert h1_rows[0][2] == ">= 70%"
    assert h1_rows[1][1] == "[+80.0%, +80.0%]"
    assert h1_rows[2][1] == "1 paired online/frozen runs"
    h3_rows = tables["table_4_5_h3_generated_tool_attribution.png"]["rows"]
    assert h3_rows[0][1] == "1 observations"
    assert h3_rows[1][1] == "0.2000"
    assert h3_rows[2][1] == "0.8000"
    assert h3_rows[3][2] == ">= +250%"
    assert (
        "sole performance endpoint"
        in tables["table_4_4_h2_overall_task_completion.png"]["caption"]
    )
    validity_rows = tables["table_4_7_validity_checks.png"]["rows"]
    assert validity_rows[0][1] == "0 mismatches"
    failure_table = tables["table_4_9_generated_tool_failure_summary.png"]
    assert failure_table["rows"][-1][1] == "0"
    assert "1 complete Chapter 4 runs" in failure_table["subtitle"]


def test_renderer_requires_versioned_data_and_explicit_paths() -> None:
    with pytest.raises(ValueError, match="schema is too old"):
        renderer.build_tables({"schema_version": 1})

    args = renderer.parse_args(
        [
            "--data",
            "evidence.json",
            "--output-dir",
            "figures",
        ]
    )
    assert args.data == Path("evidence.json")
    assert args.output_dir == Path("figures")


def test_writes_dashboard_and_resolves_search_root(tmp_path: Path) -> None:
    run_root = tmp_path / "outputs" / "online" / "online_build_full_1"
    registry = tmp_path / "artifacts" / "registry"
    _run(
        run_root,
        control_outcomes=[0.4],
        candidate_outcomes=[0.7],
        called_indices={0},
        registry_dir=registry,
        generation_enabled=True,
    )
    entry = {
        "search_root": str(tmp_path / "outputs" / "online"),
        "registry_dir": str(registry),
    }
    evidence = load_run_evidence(tmp_path, entry)
    assert evidence is not None
    assert evidence.complete
    assert evidence.dashboard_url.endswith("/dashboard/task_compare.html")

    campaign_path = tmp_path / "campaign.json"
    _write_json(
        campaign_path,
        {
            "campaign_id": "write_test",
            "expected_online_runs": 1,
            "expected_frozen_runs": 0,
            "run_pairs": [{"replication": 1, "online": entry, "frozen": {}}],
        },
    )
    output_dir = tmp_path / "dashboard"
    write_evidence_dashboard(
        repo_root=tmp_path,
        campaign_manifest_path=campaign_path,
        output_dir=output_dir,
        bootstrap_iterations=100,
        randomization_iterations=100,
    )
    assert (output_dir / "chapter4_evidence.html").exists()
    payload = json.loads((output_dir / "chapter4_evidence_data.json").read_text())
    assert payload["campaign"]["completed_online_runs"] == 1
