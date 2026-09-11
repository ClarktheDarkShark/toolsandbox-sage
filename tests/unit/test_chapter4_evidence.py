from __future__ import annotations

import base64
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

from scripts.research.chapter4_evidence import (
    RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION,
    RESEARCHER_SAMPLE_WAIVER_STATUS,
    _bootstrap_mean_ci,
    _h2_confirmatory_status,
    _randomization_p,
    _two_way_paired_outcome_bootstrap,
    build_evidence_data,
    load_run_evidence,
    verify_run_endpoint_measurements,
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


def _publication_renderer_payload(
    data: dict,
    *,
    with_frozen: bool,
) -> dict:
    payload = copy.deepcopy(data)
    payload["campaign"].update(
        {
            "status_label": "Complete",
            "manifest_status": "complete",
            "inference_complete": True,
            "endpoint_policy": "dual_scoped_outcome_endpoints",
            "excluded_completed_artifacts": 0,
            "completed_online_runs": 10,
            "completed_frozen_runs": 10 if with_frozen else 0,
            "completed_runs": 20 if with_frozen else 10,
            "expected_runs": 20 if with_frozen else 10,
            "audited_current_matched_observations": 10_320,
            "paper_comparable_matched_observations": 8_000,
            "tasks_per_run": 1_032,
        }
    )
    template = payload["runs"][0]
    template.update(
        {
            "baseline_outcome": payload["performance"]["baseline"],
            "online_sage_outcome": payload["performance"]["sage"],
            "online_outcome_lift_percent": payload["performance"][
                "outcome_lift_percent"
            ],
            "audited_current_outcome_lift_percent": payload["performance"][
                "outcome_lift_percent"
            ],
            "frozen_sage_outcome": payload["performance"]["frozen_sage"],
            "frozen_gain_retention_percent": payload["hypotheses"][0][
                "estimate_percent"
            ],
        }
    )
    runs = []
    for replication in range(1, 11):
        run = copy.deepcopy(template)
        run["replication"] = replication
        run["short_label"] = f"R{replication:02d}"
        run["online_inference_eligible"] = True
        run["frozen_inference_eligible"] = with_frozen
        if not with_frozen:
            run["frozen_sage_outcome"] = None
            run["frozen_gain_retention_percent"] = None
        runs.append(run)
    payload["runs"] = runs
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ordered_name_sha256(names: list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode()).hexdigest()


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


def _dual_endpoint_run_and_manifest(tmp_path: Path) -> tuple[Path, dict]:
    names = ["task_0", "task_1", "task_2"]
    paper_names = names[:2]
    control = [0.2, 0.5, 0.8]
    candidate = [0.4, 0.7, 0.9]
    paper_control = [0.25, 0.5]
    paper_candidate = [0.75, 0.75]
    audited_version = "test_outcome_v9"
    audited_contract = "a" * 64
    audited_source_path = (
        tmp_path / "src" / "sage_ts" / "evaluation" / "outcome_score.py"
    )
    audited_source_path.parent.mkdir(parents=True, exist_ok=True)
    audited_source_path.write_text("TEST_OUTCOME_VERSION = 'v9'\n", encoding="utf-8")
    audited_source_hash = _sha256(audited_source_path)
    paper_source_path = tmp_path / "paper_evaluator.py"
    paper_source_path.write_text("TEST_PAPER_VERSION = 'v1'\n", encoding="utf-8")
    paper_source_hash = _sha256(paper_source_path)
    benchmark_path = tmp_path / "benchmark.json"
    _write_json(
        benchmark_path,
        {"splits": {"full_benchmark": [{"name": name} for name in names]}},
    )

    run_root = tmp_path / "outputs" / "dual" / "run"
    control_dir = run_root / "control" / "control_run"
    candidate_dir = run_root / "candidate" / "candidate_run"
    registry = tmp_path / "artifacts" / "dual_registry"
    registry.mkdir(parents=True, exist_ok=True)

    def result_rows(values: list[float], paper_values: list[float]) -> list[dict]:
        return [
            {
                "name": name,
                "similarity": value,
                "outcome_similarity": value,
                "outcome_evaluator_version": audited_version,
                "outcome_evaluator_contract_sha256": audited_contract,
                "outcome_evaluator_source_sha256": audited_source_hash,
                "online_feedback_outcome_similarity": (
                    paper_values[index] if index < len(paper_values) else None
                ),
                "online_feedback_evaluator_version": (
                    "sage_paper_outcome_contracts_v1"
                    if index < len(paper_values)
                    else None
                ),
            }
            for index, (name, value) in enumerate(zip(names, values, strict=True))
        ]

    _write_json(
        control_dir / "result_summary.json",
        {"per_scenario_results": result_rows(control, paper_control)},
    )
    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": result_rows(candidate, paper_candidate)},
    )
    deltas = [
        {
            "scenario": name,
            "control_similarity": control[index],
            "candidate_similarity": candidate[index],
            "delta": candidate[index] - control[index],
            "control_outcome_similarity": control[index],
            "candidate_outcome_similarity": candidate[index],
            "outcome_delta": candidate[index] - control[index],
        }
        for index, name in enumerate(names)
    ]
    control_mean = sum(control) / len(control)
    candidate_mean = sum(candidate) / len(candidate)
    _write_json(
        run_root / "paired_comparison.json",
        {
            "scenario_count": len(names),
            "control_mean_similarity": control_mean,
            "candidate_mean_similarity": candidate_mean,
            "control_mean_outcome_similarity": control_mean,
            "candidate_mean_outcome_similarity": candidate_mean,
            "control": {
                "run_dir": str(control_dir.relative_to(tmp_path)),
                "run_status": "complete",
            },
            "candidate": {
                "run_dir": str(candidate_dir.relative_to(tmp_path)),
                "run_status": "complete",
            },
            "deltas": deltas,
            "runtime_exception_count": 0,
        },
    )
    _write_json(
        run_root / "protocol_manifest.json",
        {
            "scenario_count": len(names),
            "control_dir": str(control_dir.relative_to(tmp_path)),
            "candidate_dir": str(candidate_dir.relative_to(tmp_path)),
            "registry_dir": str(registry.relative_to(tmp_path)),
            "run_affecting_sage_env": {
                "SAGE_PRAXIS_BRIDGE_POLICY": "disabled",
                "SAGE_DISABLE_SCENARIO_NAME_BIRTH": "1",
                "SAGE_DISABLE_SCENARIO_NAME_ROUTING": "1",
            },
        },
    )
    _write_json(
        run_root / "dashboard" / "task_compare_data.json",
        {
            "summary": {
                "scenario_count": len(names),
                "balanced_completed": len(names),
                "accepted_tools": 0,
            },
            "pairs": [],
        },
    )
    (run_root / "dashboard" / "task_compare.html").write_text(
        "<html></html>", encoding="utf-8"
    )

    audited = {
        "metric_field": "outcome_similarity",
        "task_scope": "all_benchmark_tasks",
        "task_count": len(names),
        "ordered_task_name_sha256": _ordered_name_sha256(names),
        "evaluator_version": audited_version,
        "evaluator_contract_sha256": audited_contract,
        "evaluator_source_sha256": audited_source_hash,
    }
    paper = {
        "metric_field": "online_feedback_outcome_similarity",
        "task_scope": "non_null_metric_rows_in_full_benchmark_order",
        "task_count": len(paper_names),
        "ordered_task_name_sha256": _ordered_name_sha256(paper_names),
        "evaluator_version": "sage_paper_outcome_contracts_v1",
        "evaluator_source_path": str(paper_source_path.relative_to(tmp_path)),
        "evaluator_source_sha256": paper_source_hash,
    }
    thresholds_path = tmp_path / "thresholds_v3.json"
    _write_json(
        thresholds_path,
        {
            "schema_version": 3,
            "performance_endpoint_policy": "dual_scoped_outcome_endpoints",
            "canonical_metric_policy": "descriptive_only_never_a_release_gate",
            "benchmark": {
                "task_count": len(names),
                "manifest_sha256": _sha256(benchmark_path),
            },
            "performance_endpoints": {
                "audited_current_all_tasks": audited,
                "paper_comparable_historical_subset": paper,
            },
            "historical_reference": {
                "paper_comparable_candidate_outcome_mean": 0.74,
                "paper_comparable_candidate_outcome_minimum": 0.70,
                "paper_comparable_hybrid_control_outcome_mean": 0.46,
                "paper_comparable_pure_original_v140_control_outcome_mean": 0.45,
            },
        },
    )
    sample_path = tmp_path / "sample_report.json"
    _write_json(
        sample_path,
        {
            "status": "pass",
            "thresholds_path": str(thresholds_path.relative_to(tmp_path)),
            "thresholds_sha256": _sha256(thresholds_path),
        },
    )
    endpoint_plan = {
        endpoint_name: {
            "metric_field": declaration["metric_field"],
            "evaluator_version": declaration["evaluator_version"],
            "task_count_per_run": declaration["task_count"],
            "expected_matched_pairs": declaration["task_count"],
            "aggregate_statistics": None,
        }
        for endpoint_name, declaration in (
            ("audited_current_all_tasks", audited),
            ("paper_comparable_historical_subset", paper),
        )
    }
    manifest = {
        "campaign_id": "dual_endpoint_test",
        "status": "complete",
        "benchmark_manifest": str(benchmark_path.relative_to(tmp_path)),
        "benchmark_sha256": _sha256(benchmark_path),
        "expected_online_runs": 1,
        "expected_frozen_runs": 0,
        "expected_tasks_per_run": len(names),
        "sample_validation": {
            "status": "pass",
            "path": str(sample_path.relative_to(tmp_path)),
            "sha256": _sha256(sample_path),
        },
        "statistical_plan": {"performance_endpoints": endpoint_plan},
        "run_pairs": [
            {
                "replication": 1,
                "online": {
                    "run_root": str(run_root.relative_to(tmp_path)),
                    "search_root": str(run_root.parent.relative_to(tmp_path)),
                    "registry_dir": str(registry.relative_to(tmp_path)),
                },
                "frozen": {},
            }
        ],
    }
    online_entry = manifest["run_pairs"][0]["online"]
    online_entry.update(
        {
            "execution_status": "completed",
            "return_code": 0,
            "verification_status": "pass",
            "endpoint_measurements": verify_run_endpoint_measurements(
                repo_root=tmp_path,
                campaign_manifest=manifest,
                entry=online_entry,
            ),
        }
    )
    return candidate_dir / "result_summary.json", manifest


def test_dual_endpoint_verification_accepts_explicit_hashed_sample_waiver(
    tmp_path: Path,
) -> None:
    _, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    sample_path = tmp_path / manifest["sample_validation"]["path"]
    sample_report = json.loads(sample_path.read_text(encoding="utf-8"))
    manifest["sample_validation"] = {
        "status": RESEARCHER_SAMPLE_WAIVER_STATUS,
        "authorization": RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION,
        "required_gate": "release-sample",
        "reason": "Researcher directed immediate confirmatory campaign.",
        "authorized_at": "2026-09-11T00:00:00+00:00",
        "thresholds_path": sample_report["thresholds_path"],
        "thresholds_sha256": sample_report["thresholds_sha256"],
    }

    measurement = verify_run_endpoint_measurements(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        entry=manifest["run_pairs"][0]["online"],
    )

    assert measurement["status"] == "pass"


def test_dual_endpoint_verification_rejects_unauthorized_sample_waiver(
    tmp_path: Path,
) -> None:
    _, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    sample_path = tmp_path / manifest["sample_validation"]["path"]
    sample_report = json.loads(sample_path.read_text(encoding="utf-8"))
    manifest["sample_validation"] = {
        "status": RESEARCHER_SAMPLE_WAIVER_STATUS,
        "authorization": "not-explicit",
        "required_gate": "release-sample",
        "reason": "Researcher directed immediate confirmatory campaign.",
        "authorized_at": "2026-09-11T00:00:00+00:00",
        "thresholds_path": sample_report["thresholds_path"],
        "thresholds_sha256": sample_report["thresholds_sha256"],
    }

    with pytest.raises(ValueError, match="waiver is not authorized"):
        verify_run_endpoint_measurements(
            repo_root=tmp_path,
            campaign_manifest=manifest,
            entry=manifest["run_pairs"][0]["online"],
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
    assert data["campaign"]["expected_runs"] == 2
    assert data["campaign"]["completed_frozen_runs"] == 1
    assert data["campaign"]["status_label"] == "Legacy / non-confirmatory"
    assert data["campaign"]["inference_complete"] is False
    assert data["campaign"]["inference_exclusion_reason"] == (
        "missing_dual_endpoint_sample_and_run_attestations"
    )
    assert data["schema_version"] == 3
    assert data["performance"]["baseline"] == pytest.approx(0.5)
    assert data["performance"]["sage"] == pytest.approx(0.8)
    assert data["performance"]["frozen_sage"] == pytest.approx(0.74)
    assert data["performance"]["outcome_lift_label"] == "+60.0%"
    assert data["hypotheses"][0]["value_label"] == "80.0%"
    assert data["hypotheses"][0]["estimate_percent"] == pytest.approx(80.0)
    assert data["hypotheses"][0]["threshold_percent"] == pytest.approx(70.0)
    assert data["hypotheses"][0]["sample_size"] == 1
    assert data["hypotheses"][0]["decision_label"] == "Pending"
    assert data["hypotheses"][1]["value_label"] == "+60.0%"
    assert data["hypotheses"][1]["decision_label"] == "Pending"
    assert data["hypotheses"][2]["value_label"] == "+300.0%"
    assert data["hypotheses"][2]["baseline_mean"] == pytest.approx(0.2)
    assert data["hypotheses"][2]["sage_mean"] == pytest.approx(0.8)
    assert data["hypotheses"][2]["decision"] == "descriptive_only"
    assert data["hypotheses"][2]["causal_attribution_allowed"] is False
    assert data["hypotheses"][2]["decision_label"] == "Descriptive only"
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

    renderer_data = _publication_renderer_payload(data, with_frozen=True)
    excluded_run = copy.deepcopy(renderer_data["runs"][0])
    excluded_run.update(
        {
            "short_label": "EXCLUDED",
            "online_inference_eligible": False,
            "frozen_inference_eligible": False,
            "baseline_outcome": 99.0,
            "online_sage_outcome": 99.0,
            "frozen_sage_outcome": 99.0,
        }
    )
    renderer_data["runs"].append(excluded_run)
    tables = {
        table["filename"]: table for table in renderer.build_tables(renderer_data)
    }
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
    assert "No affirmative retention conclusion" in h1_rows[1][3]
    assert "remains above" not in h1_rows[1][3]
    assert h1_rows[2][1] == "1 paired online/frozen runs"
    replication_rows = tables["table_4_2_replication_results.png"]["rows"]
    assert all(row[0] != "EXCLUDED" for row in replication_rows)
    assert replication_rows[-1][1:3] == ["0.5000", "0.8000"]
    h3_rows = tables["table_4_5_h3_generated_tool_attribution.png"]["rows"]
    assert h3_rows[0][1] == "1 observations"
    assert h3_rows[1][1] == "0.2000"
    assert h3_rows[2][1] == "0.8000"
    assert h3_rows[3][2] == ">= +250% descriptive reference"
    assert (
        "selection-conditioned"
        in tables["table_4_5_h3_generated_tool_attribution.png"]["caption"]
    )
    assert (
        "sole performance endpoint"
        in tables["table_4_4_h2_overall_task_completion.png"]["caption"]
    )
    validity_rows = tables["table_4_7_validity_checks.png"]["rows"]
    assert validity_rows[0][1] == "0 mismatches"
    failure_table = tables["table_4_9_generated_tool_failure_summary.png"]
    assert failure_table["rows"][-1][1] == "0"
    assert "1 complete Chapter 4 runs" in failure_table["subtitle"]


def test_h2_never_uses_task_iid_precision_as_confirmatory_support() -> None:
    control_rows = [[0.5] * 10 for _ in range(10)]
    candidate_rows = [[0.56 if replicate < 9 else 0.50] * 10 for replicate in range(10)]
    task_contrasts = [
        candidate - 1.10 * control
        for controls, candidates in zip(control_rows, candidate_rows, strict=True)
        for control, candidate in zip(controls, candidates, strict=True)
    ]
    run_contrasts = [
        sum(row) / len(row)
        for row in (
            [
                candidate - 1.10 * control
                for control, candidate in zip(controls, candidates, strict=True)
            ]
            for controls, candidates in zip(control_rows, candidate_rows, strict=True)
        )
    ]
    task_iid_ci = _bootstrap_mean_ci(
        task_contrasts,
        iterations=5_000,
        seed=19,
    )
    run_ci = _bootstrap_mean_ci(run_contrasts, iterations=5_000, seed=20)
    two_way = _two_way_paired_outcome_bootstrap(
        control_rows,
        candidate_rows,
        threshold_percent=10,
        iterations=5_000,
        seed=21,
    )
    run_p = _randomization_p(run_contrasts, iterations=20_000, seed=22)

    assert task_iid_ci[0] > 0.0
    assert run_ci[0] < 0.0
    assert (
        _h2_confirmatory_status(
            lift_percent=10.8,
            threshold_percent=10,
            two_way_threshold_contrast_ci=two_way["threshold_contrast"],
            run_threshold_contrast_ci=run_ci,
            run_threshold_sign_flip_p=run_p,
            complete=True,
            alpha=0.05,
        )
        == "observed_pass"
    )


def test_h2_support_requires_and_accepts_consistent_run_level_target_gain() -> None:
    control_rows = [[0.5] * 5 for _ in range(10)]
    candidate_rows = [[0.6] * 5 for _ in range(10)]
    run_contrasts = [0.05] * 10
    run_ci = _bootstrap_mean_ci(run_contrasts, iterations=1_000, seed=23)
    two_way = _two_way_paired_outcome_bootstrap(
        control_rows,
        candidate_rows,
        threshold_percent=10,
        iterations=1_000,
        seed=24,
    )
    run_p = _randomization_p(run_contrasts, iterations=20_000, seed=25)

    assert two_way["threshold_contrast"][0] == pytest.approx(0.05)
    assert run_ci[0] == pytest.approx(0.05)
    assert run_p is not None and run_p < 0.05
    assert (
        _h2_confirmatory_status(
            lift_percent=20.0,
            threshold_percent=10,
            two_way_threshold_contrast_ci=two_way["threshold_contrast"],
            run_threshold_contrast_ci=run_ci,
            run_threshold_sign_flip_p=run_p,
            complete=True,
            alpha=0.05,
        )
        == "supported"
    )


def test_renderer_requires_versioned_data_and_explicit_paths() -> None:
    with pytest.raises(ValueError, match="schema is too old"):
        renderer.build_tables({"schema_version": 1})
    with pytest.raises(ValueError, match="exact dual-endpoint publication evidence"):
        renderer.build_tables(
            {
                "schema_version": 3,
                "campaign": {
                    "status_label": "Incomplete",
                    "inference_complete": False,
                },
            }
        )

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


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status_label", "Incomplete"),
        ("manifest_status", "running"),
        ("inference_complete", False),
        ("endpoint_policy", "legacy_single_endpoint"),
        ("excluded_completed_artifacts", 1),
        ("completed_online_runs", 9),
        ("audited_current_matched_observations", 10_319),
        ("paper_comparable_matched_observations", 7_999),
    ],
)
def test_renderer_rejects_every_publication_inference_gate_mutation(
    field: str,
    replacement: object,
) -> None:
    campaign_data = {
        "status_label": "Complete",
        "manifest_status": "complete",
        "inference_complete": True,
        "endpoint_policy": "dual_scoped_outcome_endpoints",
        "excluded_completed_artifacts": 0,
        "completed_online_runs": 10,
        "audited_current_matched_observations": 10_320,
        "paper_comparable_matched_observations": 8_000,
    }
    campaign_data[field] = replacement

    with pytest.raises(ValueError, match="exact dual-endpoint publication evidence"):
        renderer.build_tables(
            {
                "schema_version": 3,
                "campaign": campaign_data,
            }
        )


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
    assert evidence.dashboard_url.startswith("file://")
    assert evidence.dashboard_url.endswith("/dashboard/task_compare.html")
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["dashboard_task_compare_url"] = (
        "http://127.0.0.1:61234/dashboard/task_compare.html"
    )
    _write_json(protocol_path, protocol)
    evidence = load_run_evidence(tmp_path, entry)
    assert evidence is not None
    assert (
        evidence.dashboard_url == "http://127.0.0.1:61234/dashboard/task_compare.html"
    )

    campaign_path = tmp_path / "campaign.json"
    _write_json(
        campaign_path,
        {
            "campaign_id": "write_test",
            "expected_online_runs": 1,
            "expected_frozen_runs": 0,
            "expected_tasks_per_run": 1,
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
    assert payload["campaign"]["completed_frozen_runs"] == 0
    assert payload["campaign"]["expected_runs"] == 1
    assert payload["campaign"]["status_label"] == "Legacy / non-confirmatory"
    assert payload["campaign"]["inference_complete"] is False
    assert payload["campaign"]["progress_percent"] == 100.0
    html = (output_dir / "chapter4_evidence.html").read_text(encoding="utf-8")
    assert "__CHAPTER4_EVIDENCE_BASE64__" not in html
    match = re.search(r'const EMBEDDED_EVIDENCE_BASE64 = "([A-Za-z0-9+/=]+)";', html)
    assert match is not None
    embedded = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert embedded == payload
    assert 'window.location.protocol === "file:"' in html
    assert "setInterval(() => window.location.reload(), 30000)" in html
    assert 'campaign?.status_label !== "Complete"' not in html
    assert "run.online_inference_eligible === true" in html

    with pytest.raises(ValueError, match="exact dual-endpoint publication evidence"):
        renderer.build_tables(payload)

    publication_payload = _publication_renderer_payload(payload, with_frozen=False)
    tables = {
        table["filename"]: table for table in renderer.build_tables(publication_payload)
    }
    assert "table_4_3_h1_frozen_registry_retention.png" not in tables
    replication_table = tables["table_4_2_replication_results.png"]
    assert replication_table["columns"] == [
        "Run",
        "Baseline",
        "SAGE",
        "Outcome lift",
    ]
    assert replication_table["rows"][-1] == [
        "Mean",
        "0.4000",
        "0.7000",
        "+75.0%",
    ]
    summary_rows = tables["table_4_8_hypothesis_decision_summary.png"]["rows"]
    assert [row[0] for row in summary_rows] == ["H2", "H3"]
    publication_text = json.dumps(tables).lower()
    assert "fresh same-run matched controls" in publication_text
    assert "fixed matched baseline values" not in publication_text
    assert "frozen" not in publication_text
    assert "retention" not in publication_text
    assert "retained" not in publication_text

    original_rows = copy.deepcopy(replication_table["rows"])
    excluded_run = copy.deepcopy(publication_payload["runs"][0])
    excluded_run.update(
        {
            "short_label": "EXCLUDED",
            "online_inference_eligible": False,
            "baseline_outcome": 99.0,
            "online_sage_outcome": 99.0,
            "online_outcome_lift_percent": 99.0,
        }
    )
    publication_payload["runs"].append(excluded_run)
    filtered_tables = {
        table["filename"]: table for table in renderer.build_tables(publication_payload)
    }
    assert filtered_tables["table_4_2_replication_results.png"]["rows"] == original_rows


def test_dual_endpoints_are_separate_and_historical_comparison_is_v1_only(
    tmp_path: Path,
) -> None:
    _, manifest = _dual_endpoint_run_and_manifest(tmp_path)

    data = build_evidence_data(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        bootstrap_iterations=100,
        randomization_iterations=100,
        seed=9,
    )

    audited = data["performance_endpoints"]["audited_current_all_tasks"]
    paper = data["performance_endpoints"]["paper_comparable_historical_subset"]
    assert data["campaign"]["endpoint_policy"] == "dual_scoped_outcome_endpoints"
    assert data["campaign"]["audited_current_matched_observations"] == 3
    assert data["campaign"]["paper_comparable_matched_observations"] == 2
    assert audited["evaluator_version"] == "test_outcome_v9"
    assert audited["matched_task_observations"] == 3
    assert audited["baseline"] == pytest.approx(0.5)
    assert audited["sage"] == pytest.approx(2.0 / 3.0)
    assert paper["evaluator_version"] == "sage_paper_outcome_contracts_v1"
    assert paper["matched_task_observations"] == 2
    assert paper["baseline"] == pytest.approx(0.375)
    assert paper["sage"] == pytest.approx(0.75)
    assert paper["historical_sage_mean"] == pytest.approx(0.74)
    assert paper["candidate_minus_historical_mean"] == pytest.approx(0.01)
    assert data["hypotheses"][1]["baseline_mean"] == audited["baseline"]
    assert data["hypotheses"][1]["sage_mean"] == audited["sage"]
    assert data["runs"][0]["paper_comparable_sage_outcome"] == pytest.approx(0.75)
    verification = verify_run_endpoint_measurements(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        entry=manifest["run_pairs"][0]["online"],
    )
    assert verification["status"] == "pass"
    assert verification["audited_current_all_tasks"]["task_count"] == 3
    assert verification["paper_comparable_historical_subset"]["task_count"] == 2
    assert verification["performance_floors_applied"] is False
    assert verification["canonical_metric_checked_as_gate"] is False


def test_extra_unverified_pair_prevents_complete_campaign_label(tmp_path: Path) -> None:
    _, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    manifest["run_pairs"].append({"replication": 2, "online": {}, "frozen": {}})

    data = build_evidence_data(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        bootstrap_iterations=20,
        randomization_iterations=20,
    )

    assert data["campaign"]["completed_online_runs"] == 1
    assert data["campaign"]["status_label"] == "Incomplete"
    assert data["campaign"]["inference_complete"] is False


def test_dual_endpoint_loader_rejects_wrong_v9_identity(tmp_path: Path) -> None:
    candidate_summary, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    payload = json.loads(candidate_summary.read_text(encoding="utf-8"))
    payload["per_scenario_results"][1]["outcome_evaluator_version"] = "wrong"
    _write_json(candidate_summary, payload)

    with pytest.raises(ValueError, match="audited evaluator version is not exact"):
        build_evidence_data(repo_root=tmp_path, campaign_manifest=manifest)


def test_dual_endpoint_loader_rejects_changed_v1_subset_order(tmp_path: Path) -> None:
    candidate_summary, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    payload = json.loads(candidate_summary.read_text(encoding="utf-8"))
    rows = payload["per_scenario_results"]
    rows[1]["online_feedback_outcome_similarity"] = None
    rows[1]["online_feedback_evaluator_version"] = None
    rows[2]["online_feedback_outcome_similarity"] = 0.75
    rows[2]["online_feedback_evaluator_version"] = "sage_paper_outcome_contracts_v1"
    _write_json(candidate_summary, payload)

    with pytest.raises(
        ValueError, match="paper-comparable task subset or order changed"
    ):
        build_evidence_data(repo_root=tmp_path, campaign_manifest=manifest)


def test_dual_endpoint_loader_rejects_out_of_range_value(tmp_path: Path) -> None:
    candidate_summary, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    payload = json.loads(candidate_summary.read_text(encoding="utf-8"))
    payload["per_scenario_results"][0]["outcome_similarity"] = 1.01
    _write_json(candidate_summary, payload)

    with pytest.raises(ValueError, match=r"finite and within \[0, 1\]"):
        build_evidence_data(repo_root=tmp_path, campaign_manifest=manifest)


def test_unattested_completed_artifact_is_excluded_from_all_inference(
    tmp_path: Path,
) -> None:
    _, manifest = _dual_endpoint_run_and_manifest(tmp_path)
    manifest["run_pairs"][0]["online"]["verification_status"] = "failed"

    data = build_evidence_data(
        repo_root=tmp_path,
        campaign_manifest=manifest,
        bootstrap_iterations=20,
        randomization_iterations=20,
    )

    assert data["campaign"]["status_label"] == "Incomplete"
    assert data["campaign"]["inference_complete"] is False
    assert data["campaign"]["completed_online_runs"] == 0
    assert data["campaign"]["excluded_completed_artifacts"] == 1
    assert data["campaign"]["audited_current_matched_observations"] == 0
    assert data["campaign"]["paper_comparable_matched_observations"] == 0
    assert data["performance_endpoints"]["audited_current_all_tasks"]["sage"] is None
    assert (
        data["performance_endpoints"]["paper_comparable_historical_subset"]["sage"]
        is None
    )
    assert all(item["decision"] == "pending" for item in data["hypotheses"])
    assert data["runs"][0]["status_label"] == "Excluded from inference"
    assert data["runs"][0]["online_inference_eligible"] is False
    assert data["runs"][0]["audited_current_outcome_lift_percent"] is None
    assert data["runs"][0]["online_outcome_lift_percent"] is None
    assert data["runs"][0]["baseline_outcome"] is None
    assert data["runs"][0]["online_sage_outcome"] is None


def test_concurrent_dashboard_writes_leave_one_complete_consistent_snapshot(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "outputs" / "concurrent" / "run"
    registry = tmp_path / "artifacts" / "concurrent_registry"
    _run(
        run_root,
        control_outcomes=[0.4],
        candidate_outcomes=[0.8],
        called_indices={0},
        registry_dir=registry,
        generation_enabled=True,
    )
    entry = {"run_root": str(run_root), "registry_dir": str(registry)}
    output_dir = tmp_path / "dashboard"
    manifests: list[Path] = []
    for index in range(8):
        path = tmp_path / f"campaign_{index}.json"
        _write_json(
            path,
            {
                "campaign_id": f"concurrent_{index}",
                "expected_online_runs": 1,
                "expected_frozen_runs": 0,
                "expected_tasks_per_run": 1,
                "run_pairs": [{"replication": 1, "online": entry, "frozen": {}}],
            },
        )
        manifests.append(path)

    def write(path: Path) -> None:
        write_evidence_dashboard(
            repo_root=tmp_path,
            campaign_manifest_path=path,
            output_dir=output_dir,
            bootstrap_iterations=10,
            randomization_iterations=10,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write, manifests))

    payload = json.loads((output_dir / "chapter4_evidence_data.json").read_text())
    html = (output_dir / "chapter4_evidence.html").read_text(encoding="utf-8")
    match = re.search(r'const EMBEDDED_EVIDENCE_BASE64 = "([A-Za-z0-9+/=]+)";', html)
    assert match is not None
    embedded = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert embedded == payload
    assert not list(output_dir.glob(".*.tmp"))
