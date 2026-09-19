from __future__ import annotations

import copy

import pytest

from scripts.research.h3_registry_ablation import ROBUSTNESS_SUFFIXES, scenario_stem
from scripts.research.h4_split_registry import (
    INTEGRITY_FAILURE,
    PILOT_THRESHOLD_CLEARED,
    PILOT_THRESHOLD_NOT_CLEARED,
    REQUIRED_INTEGRITY_CHECKS,
    analyze_paired_held_out,
    build_split_design,
    validate_split_design,
)


def _scenario_names() -> list[str]:
    return [
        f"task_{stem_index:03d}{suffix}"
        for stem_index in range(129)
        for suffix in ("", *ROBUSTNESS_SUFFIXES)
    ]


def _integrity(**overrides: bool) -> dict[str, bool]:
    values = {key: True for key in REQUIRED_INTEGRITY_CHECKS}
    values.update(overrides)
    return values


def _paired_rows(
    design: dict[str, object],
    *,
    available_score: float,
    masked_score: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    order = list(design["held_out_execution_order"])
    return (
        [{"name": name, "outcome_similarity": available_score} for name in order],
        [{"name": name, "outcome_similarity": masked_score} for name in order],
    )


def test_split_is_reproducible_disjoint_and_keeps_all_variants_together() -> None:
    names = _scenario_names()
    first = build_split_design(names, seed=20260919)
    second = build_split_design(reversed(names), seed=20260919)

    assert first == second
    assert first["counts"] == {
        "all_stems": 129,
        "all_scenarios": 1032,
        "discovery_stems": 64,
        "discovery_scenarios": 512,
        "held_out_stems": 65,
        "held_out_scenarios_per_arm": 520,
    }
    assert len(first["discovery_execution_order"]) == 512
    assert len(first["held_out_execution_order"]) == 520
    assert set(first["discovery_stems"]).isdisjoint(first["held_out_stems"])
    assert first["discovery_stems"] == first["randomized_stems"][:64]
    assert first["held_out_stems"] == first["randomized_stems"][64:]

    cohort_by_scenario = {row["scenario"]: row["cohort"] for row in first["scenarios"]}
    for stem_index in range(129):
        stem = f"task_{stem_index:03d}"
        cohorts = {
            cohort_by_scenario[f"{stem}{suffix}"]
            for suffix in ("", *ROBUSTNESS_SUFFIXES)
        }
        assert len(cohorts) == 1

    report = validate_split_design(first, scenario_names=iter(names))
    assert report["valid"] is True
    assert report["source_disjoint_stems"] is True
    assert report["execution_order_hashes_verified"] is True


def test_split_seed_changes_partition_and_execution_order() -> None:
    names = _scenario_names()
    first = build_split_design(names, seed=1)
    second = build_split_design(names, seed=2)
    assert first["design_sha256"] != second["design_sha256"]
    assert first["discovery_stems"] != second["discovery_stems"]
    assert (
        first["hashes"]["held_out_execution_order_sha256"]
        != second["hashes"]["held_out_execution_order_sha256"]
    )


def test_split_validation_rejects_partition_and_hash_tampering() -> None:
    design = build_split_design(_scenario_names())
    tampered = copy.deepcopy(design)
    tampered["discovery_stems"][0], tampered["held_out_stems"][0] = (
        tampered["held_out_stems"][0],
        tampered["discovery_stems"][0],
    )
    with pytest.raises(ValueError, match="first 64"):
        validate_split_design(tampered)

    tampered = copy.deepcopy(design)
    tampered["hashes"]["held_out_execution_order_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="execution-order hash"):
        validate_split_design(tampered)


def test_split_rejects_an_incomplete_variant_roster() -> None:
    names = _scenario_names()
    names.pop()
    with pytest.raises(ValueError, match="exactly 1032"):
        build_split_design(names)


def test_paired_analysis_clears_only_the_exploratory_gate() -> None:
    design = build_split_design(_scenario_names())
    available, masked = _paired_rows(design, available_score=0.70, masked_score=0.50)
    result = analyze_paired_held_out(
        available,
        masked,
        design,
        integrity_checks=_integrity(),
        bootstrap_iterations=1_000,
        bootstrap_seed=71,
    )

    assert result["status_label"] == PILOT_THRESHOLD_CLEARED
    assert result["pilot_gate"]["exploratory_not_confirmatory"] is True
    assert result["counts"]["held_out_stems"] == 65
    assert result["counts"]["paired_scenarios"] == 520
    assert result["outcomes"]["registry_available_mean"] == pytest.approx(0.70)
    assert result["outcomes"]["registry_masked_mean"] == pytest.approx(0.50)
    assert result["outcomes"]["absolute_difference"] == pytest.approx(0.20)
    assert result["outcomes"]["relative_lift"] == pytest.approx(0.40)
    assert result["uncertainty"]["mean_difference_ci"][0] > 0
    assert "supported" not in str(result).lower()
    assert "rejected" not in str(result).lower()


def test_paired_analysis_not_cleared_when_effect_threshold_is_missed() -> None:
    design = build_split_design(_scenario_names())
    available, masked = _paired_rows(design, available_score=0.52, masked_score=0.50)
    result = analyze_paired_held_out(
        available,
        masked,
        design,
        integrity_checks=_integrity(),
        bootstrap_iterations=100,
    )
    assert result["status_label"] == PILOT_THRESHOLD_NOT_CLEARED
    assert result["pilot_gate"]["integrity_passed"] is True
    assert result["pilot_gate"]["effect_threshold_met"] is False


def test_paired_analysis_integrity_failure_overrides_a_large_effect() -> None:
    design = build_split_design(_scenario_names())
    available, masked = _paired_rows(design, available_score=0.80, masked_score=0.40)
    result = analyze_paired_held_out(
        available,
        masked,
        design,
        integrity_checks=_integrity(masked_zero_generated_calls=False),
        bootstrap_iterations=100,
    )
    assert result["status_label"] == INTEGRITY_FAILURE
    assert result["pilot_gate"]["effect_threshold_met"] is True
    assert result["integrity"]["passed"] is False


def test_paired_analysis_requires_the_same_locked_order() -> None:
    design = build_split_design(_scenario_names())
    available, masked = _paired_rows(design, available_score=0.70, masked_score=0.50)
    masked[0], masked[1] = masked[1], masked[0]
    with pytest.raises(ValueError, match="locked held-out order"):
        analyze_paired_held_out(
            available,
            masked,
            design,
            integrity_checks=_integrity(),
            bootstrap_iterations=10,
        )


def test_all_held_out_rows_resolve_to_the_declared_held_out_stems() -> None:
    design = build_split_design(_scenario_names())
    held_out_stems = set(design["held_out_stems"])
    assert {
        scenario_stem(name) for name in design["held_out_execution_order"]
    } == held_out_stems
