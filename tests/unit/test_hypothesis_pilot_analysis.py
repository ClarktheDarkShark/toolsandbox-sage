from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.research.hypothesis_pilot_analysis as pilot_analysis
from scripts.research.h3_registry_ablation import ROBUSTNESS_SUFFIXES
from scripts.research.hypothesis_pilot_analysis import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    INTEGRITY_FAILURE,
    PILOT_THRESHOLD_CLEARED,
    PILOT_THRESHOLD_NOT_CLEARED,
    _canonical_sha256,
    analyze_h2_pilot,
    write_h2_pilot_report,
)


@pytest.fixture(autouse=True)
def _strict_verifier_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pilot_analysis,
        "_strict_verification_receipt",
        lambda **kwargs: {
            "status": "pass",
            "run_root": str(Path(kwargs["run_root"]).resolve()),
            "verification": {"status": "pass"},
        },
    )


def _scenario_names() -> list[str]:
    # Seventy-seven broader task families. Fifty-two have a distinct ``_alt``
    # original-scenario stem, yielding the locked 129 stems. Every stem then
    # receives the base task plus all seven exact robustness variants.
    stems = [f"task_{index:03d}" for index in range(77)]
    stems.extend(f"task_{index:03d}_alt" for index in range(52))
    return [
        f"{stem}{suffix}" for stem in stems for suffix in ("", *ROBUSTNESS_SUFFIXES)
    ]


def _rows(*, candidate: bool, effect: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, name in enumerate(_scenario_names()):
        baseline = 0.35 + (index % 8) * 0.002 + (index // 8) * 0.0001
        rows.append(
            {
                "name": name,
                "outcome_similarity": baseline + (effect if candidate else 0.0),
                "similarity": baseline + (effect if candidate else 0.0),
                "traceback": None,
                "exception_type": None,
            }
        )
    return rows


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "per_scenario_results": rows,
                "category_summary": {"ignored_by_h2": True},
            },
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _paths(tmp_path: Path, *, effect: float) -> tuple[Path, Path]:
    control = tmp_path / "control_result_summary.json"
    candidate = tmp_path / "candidate_result_summary.json"
    _write_summary(control, _rows(candidate=False, effect=0.0))
    _write_summary(candidate, _rows(candidate=True, effect=effect))
    return control, candidate


def _rehash_report(report: dict[str, object]) -> str:
    clone = copy.deepcopy(report)
    hashes = clone["hashes"]
    assert isinstance(hashes, dict)
    declared = hashes.pop("analysis_payload_sha256")
    assert isinstance(declared, str)
    return _canonical_sha256(clone)


def test_h2_complete_pair_clears_locked_pilot_threshold(tmp_path: Path) -> None:
    control, candidate = _paths(tmp_path, effect=0.08)

    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )

    assert report["status"] == "observed"
    assert report["pilot_gate_label"] == PILOT_THRESHOLD_CLEARED
    assert report["pilot_gate"]["passed"] is True
    assert report["integrity"]["status"] == "pass"
    assert report["tasks"] == 1032
    assert report["stem_clusters"] == 129
    assert report["mean_difference"] == pytest.approx(0.08)
    assert report["relative_lift"] > 0.10
    assert report["cluster_ci_95"] == pytest.approx([0.08, 0.08])
    assert report["primary_bootstrap"]["draws"] == BOOTSTRAP_DRAWS
    assert report["primary_bootstrap"]["seed"] == BOOTSTRAP_SEED
    assert report["family_sensitivity"]["status"] == "reported"
    assert report["family_sensitivity"]["cluster_count"] == 77
    assert report["integrity"]["strict_verification_receipt"]["status"] == "pass"
    assert report["descriptive_canonical_similarity"] == {
        "role": "descriptive_not_primary",
        "control_mean": pytest.approx(report["control_mean"]),
        "integrated_sage_mean": pytest.approx(report["integrated_sage_mean"]),
        "mean_difference": pytest.approx(report["mean_difference"]),
    }
    assert len(report["inputs"]["control"]["sha256"]) == 64
    assert len(report["hashes"]["paired_outcomes_sha256"]) == 64
    assert report["hashes"]["analysis_payload_sha256"] == _rehash_report(report)


def test_h2_positive_but_small_lift_does_not_clear_threshold(tmp_path: Path) -> None:
    control, candidate = _paths(tmp_path, effect=0.02)

    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )

    assert report["status"] == "observed"
    assert report["pilot_gate_label"] == PILOT_THRESHOLD_NOT_CLEARED
    criteria = {item["criterion"]: item for item in report["pilot_gate"]["criteria"]}
    assert criteria["relative_lift_at_least_10_percent"]["passed"] is False
    assert criteria["stem_cluster_ci_lower_above_zero"]["passed"] is True
    # A threshold miss is an observed pilot result, not an integrity failure.
    assert report["integrity"]["status"] == "pass"


def test_h2_rejects_nonidentical_scenario_order(tmp_path: Path) -> None:
    control_rows = _rows(candidate=False, effect=0.0)
    candidate_rows = _rows(candidate=True, effect=0.08)
    candidate_rows[0], candidate_rows[1] = candidate_rows[1], candidate_rows[0]
    control = tmp_path / "control.json"
    candidate = tmp_path / "candidate.json"
    _write_summary(control, control_rows)
    _write_summary(candidate, candidate_rows)

    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )

    assert report["pilot_gate_label"] == INTEGRITY_FAILURE
    assert "arm_scenario_order_mismatch" in report["integrity"]["errors"]
    assert report["cluster_ci_95"] == [None, None]


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda rows: rows.__setitem__(
                0, {**rows[0], "outcome_similarity": float("nan")}
            ),
            "candidate:outcome_out_of_range:",
        ),
        (
            lambda rows: rows.__setitem__(
                0,
                {
                    **rows[0],
                    "traceback": "Traceback (most recent call last)",
                    "exception_type": "RuntimeError",
                },
            ),
            "candidate:runtime_exception_rows:1",
        ),
        (
            lambda rows: rows.pop(),
            "candidate:row_count:1031!=1032",
        ),
    ],
)
def test_h2_integrity_failures_are_machine_readable(
    tmp_path: Path,
    mutation,
    expected_error: str,
) -> None:
    control_rows = _rows(candidate=False, effect=0.0)
    candidate_rows = _rows(candidate=True, effect=0.08)
    mutation(candidate_rows)
    control = tmp_path / "control.json"
    candidate = tmp_path / "candidate.json"
    _write_summary(control, control_rows)
    _write_summary(candidate, candidate_rows)

    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )

    assert report["status"] == "failed_integrity"
    assert report["pilot_gate_label"] == INTEGRITY_FAILURE
    assert any(
        error.startswith(expected_error) for error in report["integrity"]["errors"]
    )


def test_h2_rejects_incomplete_129_by_8_variant_roster(tmp_path: Path) -> None:
    control_rows = _rows(candidate=False, effect=0.0)
    candidate_rows = _rows(candidate=True, effect=0.08)
    replacement = "unexpected_new_stem"
    control_rows[-1]["name"] = replacement
    candidate_rows[-1]["name"] = replacement
    control = tmp_path / "control.json"
    candidate = tmp_path / "candidate.json"
    _write_summary(control, control_rows)
    _write_summary(candidate, candidate_rows)

    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )

    assert report["pilot_gate_label"] == INTEGRITY_FAILURE
    assert any(
        error.startswith(("stem_count:", "stem_variant_"))
        for error in report["integrity"]["errors"]
    )


def test_h2_report_writer_preserves_machine_readable_payload(tmp_path: Path) -> None:
    control, candidate = _paths(tmp_path, effect=0.08)
    report = analyze_h2_pilot(
        control_summary_path=control,
        candidate_summary_path=candidate,
        strict_run_root=tmp_path,
    )
    output = tmp_path / "analysis" / "h2_report.json"

    write_h2_pilot_report(report, output)

    assert json.loads(output.read_text(encoding="utf-8")) == report
