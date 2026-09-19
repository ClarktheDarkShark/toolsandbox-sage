from __future__ import annotations

import copy

import pytest

from scripts.research.h3_registry_ablation import (
    ROBUSTNESS_SUFFIXES,
    analyze_registry_availability,
    assignment_by_scenario,
    build_registry_assignment,
    scenario_stem,
    scenario_variant,
    validate_registry_assignment,
)


def _control_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    variants = ("", *ROBUSTNESS_SUFFIXES)
    for stem_index in range(129):
        stem = f"task_{stem_index:03d}"
        for variant_index, suffix in enumerate(variants):
            rows.append(
                {
                    "scenario": f"{stem}{suffix}",
                    "control_outcome_similarity": (
                        0.2 + stem_index * 0.001 + variant_index * 0.00001
                    ),
                }
            )
    return rows


def test_scenario_stem_strips_only_complete_robustness_suffixes() -> None:
    scenario = "remove_contact_ambiguous_alt_3_distraction_tools_arg_type_scrambled"
    assert scenario_stem(scenario) == "remove_contact_ambiguous_alt"
    assert scenario_variant(scenario) == "_3_distraction_tools_arg_type_scrambled"
    assert (
        scenario_stem("remove_contact_ambiguous_alt") == "remove_contact_ambiguous_alt"
    )
    assert scenario_stem("literal_arg_type_scrambled") == "literal_arg_type_scrambled"


def test_assignment_is_reproducible_balanced_and_inherited_by_all_variants() -> None:
    control = _control_rows()
    first = build_registry_assignment(control, seed=731)
    second = build_registry_assignment(reversed(control), seed=731)

    assert first == second
    assert first["counts"] == {
        "stems": 129,
        "scenarios": 1032,
        "registry_available_stems": 65,
        "registry_masked_stems": 64,
        "registry_available_scenarios": 520,
        "registry_masked_scenarios": 512,
    }
    assert sum(block["size"] == 2 for block in first["blocks"]) == 63
    assert sum(block["size"] == 3 for block in first["blocks"]) == 1
    assert len(first["assignment_sha256"]) == 64
    assert len(first["design_sha256"]) == 64

    assignments = assignment_by_scenario(first)
    for stem_index in range(129):
        stem = f"task_{stem_index:03d}"
        inherited = {
            assignments[f"{stem}{suffix}"] for suffix in ("", *ROBUSTNESS_SUFFIXES)
        }
        assert len(inherited) == 1

    report = validate_registry_assignment(first, control_rows=iter(control))
    assert report["valid"] is True
    assert report["control_rows_verified"] is True


def test_assignment_seed_changes_the_frozen_allocation() -> None:
    control = _control_rows()
    first = build_registry_assignment(control, seed=100)
    second = build_registry_assignment(control, seed=101)
    assert first["assignment_sha256"] != second["assignment_sha256"]


def test_assignment_validation_rejects_hash_tampering() -> None:
    manifest = build_registry_assignment(_control_rows(), seed=200)
    tampered = copy.deepcopy(manifest)
    tampered["assignment_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="assignment hash"):
        validate_registry_assignment(tampered)


def test_assignment_rejects_an_incomplete_variant_roster() -> None:
    control = _control_rows()
    control.pop()
    with pytest.raises(ValueError, match="exactly 1032"):
        build_registry_assignment(control)


def test_itt_analysis_reports_effect_randomization_p_and_cluster_ci() -> None:
    control = _control_rows()
    manifest = build_registry_assignment(control, seed=919)
    assignment = assignment_by_scenario(manifest)
    control_by_scenario = {
        str(row["scenario"]): float(row["control_outcome_similarity"])
        for row in control
    }
    candidate = [
        {
            "scenario": scenario,
            "candidate_outcome_similarity": control_by_scenario[scenario]
            + (0.25 if arm == "registry_available" else 0.0),
        }
        for scenario, arm in assignment.items()
    ]

    result = analyze_registry_availability(
        candidate,
        iter(control),
        manifest,
        randomization_iterations=2_000,
        bootstrap_iterations=2_000,
        randomization_seed=991,
        bootstrap_seed=992,
    )

    assert result["integrity"]["complete_itt_roster"] is True
    assert result["counts"]["registry_available_scenarios"] == 520
    assert result["counts"]["registry_masked_scenarios"] == 512
    assert result["outcomes"]["absolute_difference"] > 0.24
    assert (
        result["uncertainty"]["restricted_randomization_one_sided_p_value"] <= 1 / 2_001
    )
    assert result["uncertainty"]["stem_cluster_percentile_bootstrap_95_ci"][0] > 0.20
    assert result["control_adjusted_sensitivity"]["difference"] == pytest.approx(0.25)
    assert result["analysis_sha256"]


def test_itt_analysis_requires_every_randomized_scenario() -> None:
    control = _control_rows()
    manifest = build_registry_assignment(control, seed=300)
    candidate = [
        {
            "scenario": row["scenario"],
            "candidate_outcome_similarity": row["control_outcome_similarity"],
        }
        for row in control[:-1]
    ]
    with pytest.raises(ValueError, match="every randomized scenario"):
        analyze_registry_availability(
            candidate,
            control,
            manifest,
            randomization_iterations=10,
            bootstrap_iterations=10,
        )
