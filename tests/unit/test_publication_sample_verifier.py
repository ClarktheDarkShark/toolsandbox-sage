from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import scripts.verify_publication_sample as sample_verifier


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _thresholds(tmp_path: Path) -> Path:
    path = tmp_path / "thresholds.json"
    summary = tmp_path / "historical_outcome_summary.json"
    campaign = tmp_path / "historical_campaign.json"
    evidence = tmp_path / "historical_evidence.json"
    _write_json(summary, {"historical": "outcome summary"})
    _write_json(campaign, {"historical": "campaign"})
    _write_json(evidence, {"historical": "evidence"})
    _write_json(
        path,
        {
            "schema_version": 2,
            "purpose": "test",
            "performance_endpoint": "outcome_task_completion_similarity",
            "outcome_evaluator": sample_verifier.outcome_evaluator_manifest(),
            "benchmark": {
                "task_count": 2,
                "outcome_scored_task_count": 2,
                "manifest_sha256": "benchmark",
                "ordered_task_name_sha256": "order",
            },
            "required_integrity": {"validated_external_fixture_sha256": "fixture"},
            "required_no_regression": {
                "candidate_outcome_minimum": 0.70,
                "minimum_relative_outcome_lift_percent_over_same_run_control": 10.0,
            },
            "historical_reference": {
                "candidate_outcome_mean": 0.75,
                "summary_path": str(summary),
                "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
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
                "compare_candidate_outcome_to_historical_mean": 0.75,
            },
        },
    )
    return path


def _comparison(
    tmp_path: Path,
    *,
    candidate_outcome: float = 0.80,
    candidate_canonical: float | None = 0.80,
) -> Path:
    run_root = tmp_path / "run"
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
            "outcome_evaluator": sample_verifier.outcome_evaluator_manifest(),
            "control": {
                **common,
                "mean_similarity": 0.60,
                "mean_outcome_similarity": 0.50,
            },
            "candidate": {
                **common,
                "mean_similarity": candidate_canonical,
                "mean_outcome_similarity": candidate_outcome,
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
            "outcome_evaluator": sample_verifier.outcome_evaluator_manifest(),
        },
    )


def test_sample_verifier_passes_outcome_gate_and_reports_mean_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)

    result = sample_verifier.verify_sample(
        tmp_path,
        thresholds_path=_thresholds(tmp_path),
    )

    assert result["status"] == "pass"
    assert result["outcome_evaluator"] == sample_verifier.outcome_evaluator_manifest()
    assert result["metrics"]["same_run_relative_outcome_lift_percent"] == pytest.approx(
        60.0
    )
    assert all("canonical" not in name for name in result["metrics"])
    assert "canonical_metric_policy" not in result
    assert result["mechanism_diagnostics"] == {
        "release_gate": False,
        "accepted_tool_count": 2,
        "tool_reuse_event_count": 3,
        "generated_tool_called_scenario_count": 1,
    }
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
    assert all("canonical" not in name for name in result["metrics"])
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
    assert all("canonical" not in name for name in result["metrics"])


def test_sample_verifier_rejects_threshold_evaluator_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    thresholds_path = _thresholds(tmp_path)
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    thresholds["outcome_evaluator"]["source_sha256"] = "0" * 64
    _write_json(thresholds_path, thresholds)

    with pytest.raises(ValueError, match="do not pin the current outcome evaluator"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=thresholds_path,
        )


def test_sample_verifier_rejects_comparison_evaluator_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    comparison_path = run_root / "paired_comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["outcome_evaluator"]["contract_sha256"] = "0" * 64
    _write_json(comparison_path, comparison)

    with pytest.raises(ValueError, match="Paired comparison did not use"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )


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

    with pytest.raises(ValueError, match="must not be publication release gates"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=thresholds_path,
        )


@pytest.mark.parametrize(
    "field",
    [
        "minimum_accepted_tool_count",
        "minimum_tool_reuse_event_count",
        "minimum_generated_tool_called_scenario_count",
    ],
)
def test_sample_verifier_rejects_non_outcome_mechanism_release_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    run_root = _comparison(tmp_path)
    _stub_integrity(monkeypatch, run_root)
    thresholds_path = _thresholds(tmp_path)
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    thresholds["required_no_regression"][field] = 1
    _write_json(thresholds_path, thresholds)

    with pytest.raises(ValueError, match="must not be publication release gates"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=thresholds_path,
        )


def test_sample_verifier_fails_without_retry_and_preserves_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = _comparison(tmp_path, candidate_outcome=0.65)
    _stub_integrity(monkeypatch, run_root)

    with pytest.raises(ValueError, match="candidate_outcome_no_regression"):
        sample_verifier.verify_sample(
            tmp_path,
            thresholds_path=_thresholds(tmp_path),
        )

    report = json.loads(
        (run_root / "publication_validation_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "fail"
    assert report["failed_gates"] == ["candidate_outcome_no_regression"]
