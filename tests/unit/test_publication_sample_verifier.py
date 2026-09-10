from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import scripts.verify_publication_sample as sample_verifier

AUDITED_VERSION = "test_outcome_contracts"
AUDITED_CONTRACT_HASH = "a" * 64
AUDITED_SOURCE_HASH = "b" * 64
PAPER_VERSION = "test_paper_contracts"
TASK_NAMES = ["task_a", "task_b"]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _ordered_hash(names: list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode()).hexdigest()


def _thresholds(tmp_path: Path) -> Path:
    path = tmp_path / "thresholds.json"
    campaign = tmp_path / "historical_campaign.json"
    evidence = tmp_path / "historical_evidence.json"
    benchmark = tmp_path / "benchmark.json"
    _write_json(campaign, {"historical": "campaign"})
    _write_json(evidence, {"historical": "evidence"})
    _write_json(
        benchmark,
        {"splits": {"full_benchmark": [{"name": name} for name in TASK_NAMES]}},
    )
    order_hash = _ordered_hash(TASK_NAMES)
    _write_json(
        path,
        {
            "schema_version": 3,
            "purpose": "test",
            "performance_endpoint_policy": "dual_scoped_outcome_endpoints",
            "canonical_metric_policy": "descriptive_only_never_a_release_gate",
            "benchmark": {
                "path": str(benchmark),
                "task_count": 2,
                "manifest_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
                "ordered_task_name_sha256": order_hash,
            },
            "performance_endpoints": {
                "audited_current_all_tasks": {
                    "metric_field": "outcome_similarity",
                    "task_scope": "all_benchmark_tasks",
                    "task_count": 2,
                    "ordered_task_name_sha256": order_hash,
                    "evaluator_version": AUDITED_VERSION,
                    "evaluator_contract_sha256": AUDITED_CONTRACT_HASH,
                    "evaluator_source_sha256": AUDITED_SOURCE_HASH,
                },
                "paper_comparable_historical_subset": {
                    "metric_field": "online_feedback_outcome_similarity",
                    "task_scope": "non_null_metric_rows_in_full_benchmark_order",
                    "subset_derivation": (
                        "sage_paper_outcome_contracts_v1_static_applicability"
                    ),
                    "task_count": 2,
                    "ordered_task_name_sha256": order_hash,
                    "evaluator_version": PAPER_VERSION,
                },
            },
            "required_integrity": {"validated_external_fixture_sha256": "fixture"},
            "required_no_regression": {
                "paper_comparable_candidate_outcome_minimum": 0.70,
                "audited_current_minimum_relative_outcome_lift_percent_over_same_run_control": (  # noqa: E501
                    10.0
                ),
                "minimum_accepted_tool_count": 1,
                "minimum_tool_reuse_event_count": 1,
                "minimum_generated_tool_called_scenario_count": 1,
            },
            "historical_reference": {
                "paper_comparable_candidate_outcome_mean": 0.75,
                "campaign_manifest": str(campaign),
                "campaign_manifest_sha256": hashlib.sha256(
                    campaign.read_bytes()
                ).hexdigest(),
                "evidence_data": str(evidence),
                "evidence_data_sha256": hashlib.sha256(
                    evidence.read_bytes()
                ).hexdigest(),
            },
            "report_only": {
                "paper_comparable_candidate_outcome_historical_mean": 0.75,
            },
        },
    )
    return path


def _row(
    name: str,
    *,
    audited_outcome: float,
    paper_outcome: float | None,
    paper_version: str = PAPER_VERSION,
) -> dict[str, Any]:
    return {
        "name": name,
        "outcome_similarity": audited_outcome,
        "outcome_evaluator_version": AUDITED_VERSION,
        "outcome_evaluator_contract_sha256": AUDITED_CONTRACT_HASH,
        "outcome_evaluator_source_sha256": AUDITED_SOURCE_HASH,
        "online_feedback_outcome_similarity": paper_outcome,
        "online_feedback_evaluator_version": paper_version,
    }


def _comparison(
    tmp_path: Path,
    *,
    audited_candidate_outcome: float = 0.80,
    paper_candidate_outcome: float = 0.80,
    candidate_canonical: float | None = 0.80,
    paper_version: str = PAPER_VERSION,
) -> Path:
    run_root = tmp_path / "run"
    control_dir = run_root / "control" / "control_run"
    candidate_dir = run_root / "candidate" / "candidate_run"
    control_rows = [
        _row(name, audited_outcome=0.50, paper_outcome=0.50) for name in TASK_NAMES
    ]
    candidate_rows = [
        _row(
            name,
            audited_outcome=audited_candidate_outcome,
            paper_outcome=paper_candidate_outcome,
            paper_version=paper_version,
        )
        for name in TASK_NAMES
    ]
    _write_json(
        control_dir / "result_summary.json", {"per_scenario_results": control_rows}
    )
    _write_json(
        candidate_dir / "result_summary.json",
        {"per_scenario_results": candidate_rows},
    )
    _write_json(
        run_root / "protocol_manifest.json",
        {"control_dir": str(control_dir), "candidate_dir": str(candidate_dir)},
    )
    common = {
        "scenario_count": 2,
        "planned_scenario_count": 2,
        "run_status": "complete",
        "outcome_score_available_count": 2,
        "exception_count": 0,
        "llm_cached_call_count": 0,
    }
    _write_json(
        run_root / "paired_comparison.json",
        {
            "control": {
                **common,
                "run_dir": str(control_dir),
                "mean_similarity": 0.60,
                "mean_outcome_similarity": 0.50,
            },
            "candidate": {
                **common,
                "run_dir": str(candidate_dir),
                "mean_similarity": candidate_canonical,
                "mean_outcome_similarity": audited_candidate_outcome,
                "accepted_tool_count": 2,
                "reuse_count": 3,
                "generated_tool_called_scenarios": 1,
            },
        },
    )
    return run_root


def _stub_integrity(
    monkeypatch: pytest.MonkeyPatch,
    run_root: Path,
) -> None:
    monkeypatch.setattr(
        sample_verifier,
        "verify_run",
        lambda *args, **kwargs: {
            "status": "pass",
            "run_root": str(run_root),
            "scenario_count": 2,
        },
    )
    monkeypatch.setattr(
        sample_verifier,
        "_expected_paper_subset_names",
        lambda *args, **kwargs: list(TASK_NAMES),
    )


def test_sample_verifier_separates_audited_lift_from_paper_historical_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(
        tmp_path,
        audited_candidate_outcome=0.78,
        paper_candidate_outcome=0.80,
    )
    _stub_integrity(monkeypatch, run_root)

    result = sample_verifier.verify_sample(
        tmp_path,
        thresholds_path=_thresholds(tmp_path),
    )

    assert result["status"] == "pass"
    assert result["metrics"]["audited_current_all_tasks"][
        "same_run_relative_lift_percent"
    ] == pytest.approx(56.0)
    assert result["metrics"]["paper_comparable_historical_subset"][
        "candidate_mean"
    ] == pytest.approx(0.80)
    assert all("canonical" not in name for name in result["gates"])
    assert (run_root / "publication_validation_report.json").is_file()


def test_sample_verifier_never_uses_canonical_as_a_release_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, candidate_canonical=0.0)
    _stub_integrity(monkeypatch, run_root)

    result = sample_verifier.verify_sample(
        tmp_path,
        thresholds_path=_thresholds(tmp_path),
    )

    assert result["status"] == "pass"
    assert result["metrics"]["report_only_canonical"]["candidate_mean"] == 0.0
    assert all("canonical" not in name for name in result["gates"])


def test_sample_verifier_does_not_require_canonical_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, candidate_canonical=None)
    _stub_integrity(monkeypatch, run_root)

    result = sample_verifier.verify_sample(
        tmp_path,
        thresholds_path=_thresholds(tmp_path),
    )

    assert result["status"] == "pass"
    assert result["metrics"]["report_only_canonical"]["candidate_mean"] is None


def test_sample_verifier_rejects_canonical_release_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    thresholds_path = _thresholds(tmp_path)
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    thresholds["required_no_regression"]["candidate_canonical_minimum"] = 0.0
    _write_json(thresholds_path, thresholds)

    with pytest.raises(ValueError, match="must not be a release gate"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=thresholds_path,
        )


def test_sample_verifier_fails_paper_floor_without_retry_and_preserves_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, paper_candidate_outcome=0.65)
    _stub_integrity(monkeypatch, run_root)

    with pytest.raises(
        ValueError, match="paper_comparable_candidate_outcome_historical_floor"
    ):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )

    report = json.loads(
        (run_root / "publication_validation_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "fail"
    assert report["failed_gates"] == [
        "paper_comparable_candidate_outcome_historical_floor"
    ]


def test_sample_verifier_rejects_wrong_paper_evaluator_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, paper_version="wrong")
    _stub_integrity(monkeypatch, run_root)

    with pytest.raises(ValueError, match="paper_comparable_evaluator_version"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )


def test_sample_verifier_rejects_duplicate_task_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    protocol = json.loads(
        (run_root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    summary_path = Path(protocol["candidate_dir"]) / "result_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["per_scenario_results"][1]["name"] = TASK_NAMES[0]
    _write_json(summary_path, summary)

    with pytest.raises(ValueError, match="audited_current_unique_task_names"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )


def test_sample_verifier_rejects_nonfinite_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, paper_candidate_outcome=float("nan"))
    _stub_integrity(monkeypatch, run_root)

    with pytest.raises(ValueError, match="finite numeric"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )


def test_sample_verifier_rejects_arm_path_outside_same_run_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["candidate_dir"] = protocol["control_dir"]
    _write_json(protocol_path, protocol)

    with pytest.raises(ValueError, match="escapes its same-run arm directory"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )


def test_frozen_paper_subset_is_statically_derived_from_evaluator_applicability() -> (
    None
):
    thresholds = json.loads(
        sample_verifier.DEFAULT_THRESHOLDS.read_text(encoding="utf-8")
    )
    paper = thresholds["performance_endpoints"]["paper_comparable_historical_subset"]

    names = sample_verifier._expected_paper_subset_names(thresholds["benchmark"], paper)

    assert len(names) == 800
    assert len(set(names)) == 800
    assert _ordered_hash(names) == (
        "e296668682aca636c6812d5d730d52610b97eab65129357cb297d14f4391af8c"
    )
