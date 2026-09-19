"""Locked split design and paired analysis for the exploratory H4 pilot.

H4 is intentionally different from the H3 availability experiment.  The
complete benchmark is first randomized at the 129 task-stem level.  The first
64 stems are a discovery cohort on which generation is allowed.  The remaining
65 stems are never observed during discovery and form the held-out evaluation
cohort.  Every robustness variant stays with its stem.

The held-out evaluation is paired: the same 520 tasks are executed in the same
locked order once with the discovery registry available and once with that
identical registry completely masked.  Analysis is intention-to-treat over all
520 paired tasks and uncertainty resamples the 65 task stems.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from scripts.research.h3_registry_ablation import (
    EXPECTED_SCENARIO_COUNT,
    EXPECTED_STEM_COUNT,
    EXPECTED_VARIANTS_PER_STEM,
    ROBUSTNESS_SUFFIXES,
    scenario_stem,
    scenario_variant,
)

DESIGN_SCHEMA_VERSION = 1
ANALYSIS_SCHEMA_VERSION = 1
DEFAULT_SPLIT_SEED = 20260919
DEFAULT_BOOTSTRAP_SEED = DEFAULT_SPLIT_SEED + 1
DEFAULT_BOOTSTRAP_ITERATIONS = 50_000

DISCOVERY_STEM_COUNT = 64
HELD_OUT_STEM_COUNT = 65
DISCOVERY_SCENARIO_COUNT = DISCOVERY_STEM_COUNT * EXPECTED_VARIANTS_PER_STEM
HELD_OUT_SCENARIO_COUNT = HELD_OUT_STEM_COUNT * EXPECTED_VARIANTS_PER_STEM

HYPOTHESIS = (
    "A frozen registry built only on a randomized, disjoint discovery half "
    "improves mean outcome score over registry-masked SAGE on the held-out "
    "second half."
)

PILOT_THRESHOLD_CLEARED = "PILOT_THRESHOLD_CLEARED"
PILOT_THRESHOLD_NOT_CLEARED = "PILOT_THRESHOLD_NOT_CLEARED"
INTEGRITY_FAILURE = "INTEGRITY_FAILURE"

_EXPECTED_VARIANTS = frozenset(("base", *ROBUSTNESS_SUFFIXES))
_SCENARIO_KEYS = ("name", "scenario", "scenario_name")
_OUTCOME_KEYS = (
    "outcome_similarity",
    "outcome_score",
    "candidate_outcome_similarity",
)
REQUIRED_INTEGRITY_CHECKS = (
    "complete_rosters",
    "source_disjoint_stems",
    "design_hash_verified",
    "execution_order_hashes_verified",
    "immutable_equal_registry_copies",
    "identical_runtime_and_native_inventory",
    "masked_zero_generated_exposure",
    "masked_zero_generated_calls",
    "available_generated_exposure_positive",
    "held_out_arms_concurrent",
    "zero_runtime_exceptions",
    "frozen_phase_generation_repair_reflection_lifecycle_disabled",
)


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ordered_names_sha256(names: Sequence[str]) -> str:
    return _canonical_sha256(list(names))


def _required_seed(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _required_iterations(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Bootstrap iterations must be a positive integer.")
    return int(value)


def _benchmark_groups(scenario_names: Iterable[str]) -> dict[str, list[str]]:
    names = tuple(scenario_names)
    if len(names) != EXPECTED_SCENARIO_COUNT:
        raise ValueError(
            f"H4 requires exactly {EXPECTED_SCENARIO_COUNT} scenarios; "
            f"received {len(names)}."
        )
    if len(set(names)) != len(names):
        raise ValueError("H4 benchmark scenario names must be unique.")
    groups: dict[str, list[str]] = defaultdict(list)
    for name in names:
        if not isinstance(name, str) or not name:
            raise ValueError("H4 scenario names must be non-empty strings.")
        groups[scenario_stem(name)].append(name)
    if len(groups) != EXPECTED_STEM_COUNT:
        raise ValueError(
            f"H4 requires exactly {EXPECTED_STEM_COUNT} stems; received {len(groups)}."
        )
    for stem, scenarios in groups.items():
        variants = {scenario_variant(name) for name in scenarios}
        if (
            len(scenarios) != EXPECTED_VARIANTS_PER_STEM
            or variants != _EXPECTED_VARIANTS
        ):
            raise ValueError(
                f"H4 stem {stem!r} does not have the complete eight-variant roster."
            )
    return {stem: sorted(scenarios) for stem, scenarios in groups.items()}


def _construct_split_design(
    scenario_names: Iterable[str],
    *,
    seed: int,
) -> dict[str, Any]:
    groups = _benchmark_groups(scenario_names)
    rng = np.random.default_rng(seed)
    sorted_stems = sorted(groups)
    stem_indices = rng.permutation(len(sorted_stems))
    randomized_stems = [sorted_stems[int(index)] for index in stem_indices]
    discovery_stems = randomized_stems[:DISCOVERY_STEM_COUNT]
    held_out_stems = randomized_stems[DISCOVERY_STEM_COUNT:]

    discovery_pool = sorted(name for stem in discovery_stems for name in groups[stem])
    held_out_pool = sorted(name for stem in held_out_stems for name in groups[stem])
    discovery_order = [
        discovery_pool[int(index)] for index in rng.permutation(len(discovery_pool))
    ]
    held_out_order = [
        held_out_pool[int(index)] for index in rng.permutation(len(held_out_pool))
    ]

    stem_rows = [
        {
            "stem": stem,
            "randomized_position": position,
            "cohort": "discovery" if position < DISCOVERY_STEM_COUNT else "held_out",
            "scenario_count": EXPECTED_VARIANTS_PER_STEM,
        }
        for position, stem in enumerate(randomized_stems)
    ]
    scenario_rows = [
        {
            "scenario": name,
            "stem": stem,
            "cohort": ("discovery" if stem in set(discovery_stems) else "held_out"),
        }
        for stem in sorted(groups)
        for name in groups[stem]
    ]
    manifest: dict[str, Any] = {
        "schema_version": DESIGN_SCHEMA_VERSION,
        "hypothesis": HYPOTHESIS,
        "design": "randomized_disjoint_discovery_then_paired_frozen_registry",
        "analysis_principle": "paired_intention_to_treat_on_held_out_stems",
        "seed": seed,
        "random_generator": "numpy.random.Generator(PCG64)",
        "stem_definition": "remove_exactly_one_complete_robustness_suffix",
        "robustness_suffixes": list(ROBUSTNESS_SUFFIXES),
        "counts": {
            "all_stems": EXPECTED_STEM_COUNT,
            "all_scenarios": EXPECTED_SCENARIO_COUNT,
            "discovery_stems": DISCOVERY_STEM_COUNT,
            "discovery_scenarios": DISCOVERY_SCENARIO_COUNT,
            "held_out_stems": HELD_OUT_STEM_COUNT,
            "held_out_scenarios_per_arm": HELD_OUT_SCENARIO_COUNT,
        },
        "randomized_stems": randomized_stems,
        "discovery_stems": discovery_stems,
        "held_out_stems": held_out_stems,
        "stems": stem_rows,
        "scenarios": scenario_rows,
        "discovery_execution_order": discovery_order,
        "held_out_execution_order": held_out_order,
        "hashes": {
            "stem_randomization_sha256": _ordered_names_sha256(randomized_stems),
            "discovery_execution_order_sha256": _ordered_names_sha256(discovery_order),
            "held_out_execution_order_sha256": _ordered_names_sha256(held_out_order),
        },
    }
    manifest["design_sha256"] = _canonical_sha256(manifest)
    return manifest


def build_split_design(
    scenario_names: Iterable[str],
    *,
    seed: int = DEFAULT_SPLIT_SEED,
) -> dict[str, Any]:
    """Build and self-validate the H4 split and locked execution orders."""

    seed = _required_seed(seed, "H4 split seed")
    names = tuple(scenario_names)
    manifest = _construct_split_design(names, seed=seed)
    validate_split_design(manifest, scenario_names=names)
    return manifest


def validate_split_design(
    manifest: Mapping[str, Any],
    *,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Fail closed on split, variant, execution-order, or hash drift."""

    if not isinstance(manifest, Mapping):
        raise ValueError("H4 design manifest must be an object.")
    if manifest.get("schema_version") != DESIGN_SCHEMA_VERSION:
        raise ValueError("Unsupported H4 design schema version.")
    if manifest.get("hypothesis") != HYPOTHESIS:
        raise ValueError("H4 hypothesis text differs from the locked wording.")
    seed = _required_seed(manifest.get("seed"), "H4 split seed")
    if tuple(manifest.get("robustness_suffixes") or ()) != ROBUSTNESS_SUFFIXES:
        raise ValueError("H4 robustness suffix declaration changed.")

    raw_scenarios = manifest.get("scenarios")
    raw_stems = manifest.get("stems")
    randomized_stems = manifest.get("randomized_stems")
    discovery_stems = manifest.get("discovery_stems")
    held_out_stems = manifest.get("held_out_stems")
    discovery_order = manifest.get("discovery_execution_order")
    held_out_order = manifest.get("held_out_execution_order")
    if not all(
        isinstance(value, list)
        for value in (
            raw_scenarios,
            raw_stems,
            randomized_stems,
            discovery_stems,
            held_out_stems,
            discovery_order,
            held_out_order,
        )
    ):
        raise ValueError("H4 design lists are malformed or missing.")
    assert isinstance(raw_scenarios, list)
    assert isinstance(raw_stems, list)
    assert isinstance(randomized_stems, list)
    assert isinstance(discovery_stems, list)
    assert isinstance(held_out_stems, list)
    assert isinstance(discovery_order, list)
    assert isinstance(held_out_order, list)

    if (
        len(randomized_stems) != EXPECTED_STEM_COUNT
        or len(set(randomized_stems)) != EXPECTED_STEM_COUNT
    ):
        raise ValueError("H4 randomized stem roster must contain 129 unique stems.")
    if discovery_stems != randomized_stems[:DISCOVERY_STEM_COUNT]:
        raise ValueError("H4 discovery stems are not the first 64 randomized stems.")
    if held_out_stems != randomized_stems[DISCOVERY_STEM_COUNT:]:
        raise ValueError("H4 held-out stems are not the final 65 randomized stems.")
    if set(discovery_stems) & set(held_out_stems):
        raise ValueError("H4 discovery and held-out stems overlap.")

    row_names: list[str] = []
    row_groups: dict[str, list[str]] = defaultdict(list)
    row_cohort: dict[str, str] = {}
    for row in raw_scenarios:
        if not isinstance(row, Mapping):
            raise ValueError("H4 scenario records must be objects.")
        name = row.get("scenario")
        stem = row.get("stem")
        cohort = row.get("cohort")
        if not isinstance(name, str) or not name:
            raise ValueError("H4 scenario record has an invalid name.")
        if name in row_cohort:
            raise ValueError(f"Duplicate H4 scenario record: {name!r}.")
        if stem != scenario_stem(name):
            raise ValueError(f"H4 scenario record has the wrong stem: {name!r}.")
        expected_cohort = "discovery" if stem in set(discovery_stems) else "held_out"
        if cohort != expected_cohort:
            raise ValueError(f"H4 scenario record has the wrong cohort: {name!r}.")
        row_names.append(name)
        row_groups[str(stem)].append(name)
        row_cohort[name] = str(cohort)
    _benchmark_groups(row_names)
    if set(row_groups) != set(randomized_stems):
        raise ValueError("H4 scenario and stem rosters differ.")

    if len(raw_stems) != EXPECTED_STEM_COUNT:
        raise ValueError("H4 stem records must contain exactly 129 rows.")
    for position, row in enumerate(raw_stems):
        if not isinstance(row, Mapping):
            raise ValueError("H4 stem records must be objects.")
        if row.get("stem") != randomized_stems[position]:
            raise ValueError("H4 stem records do not preserve randomized order.")
        if row.get("randomized_position") != position:
            raise ValueError("H4 stem position declaration is inconsistent.")

    expected_discovery = {
        name for name, cohort in row_cohort.items() if cohort == "discovery"
    }
    expected_held_out = {
        name for name, cohort in row_cohort.items() if cohort == "held_out"
    }
    if (
        len(discovery_order) != DISCOVERY_SCENARIO_COUNT
        or set(discovery_order) != expected_discovery
    ):
        raise ValueError("H4 discovery execution order is not a 512-task roster.")
    if (
        len(held_out_order) != HELD_OUT_SCENARIO_COUNT
        or set(held_out_order) != expected_held_out
    ):
        raise ValueError("H4 held-out execution order is not a 520-task roster.")
    if len(set(discovery_order)) != len(discovery_order) or len(
        set(held_out_order)
    ) != len(held_out_order):
        raise ValueError("H4 execution orders contain duplicates.")

    expected_counts = {
        "all_stems": 129,
        "all_scenarios": 1032,
        "discovery_stems": 64,
        "discovery_scenarios": 512,
        "held_out_stems": 65,
        "held_out_scenarios_per_arm": 520,
    }
    if manifest.get("counts") != expected_counts:
        raise ValueError("H4 count declaration is inconsistent.")
    hashes = manifest.get("hashes")
    if not isinstance(hashes, Mapping):
        raise ValueError("H4 execution-order hashes are missing.")
    expected_hashes = {
        "stem_randomization_sha256": _ordered_names_sha256(randomized_stems),
        "discovery_execution_order_sha256": _ordered_names_sha256(discovery_order),
        "held_out_execution_order_sha256": _ordered_names_sha256(held_out_order),
    }
    if dict(hashes) != expected_hashes:
        raise ValueError("H4 execution-order hash mismatch.")
    unhashed = dict(manifest)
    declared_hash = unhashed.pop("design_sha256", None)
    if declared_hash != _canonical_sha256(unhashed):
        raise ValueError("H4 design hash mismatch.")

    if scenario_names is not None:
        supplied = tuple(scenario_names)
        _benchmark_groups(supplied)
        if set(supplied) != set(row_names):
            raise ValueError("H4 design and supplied benchmark rosters differ.")
        reproduced = _construct_split_design(supplied, seed=seed)
        if reproduced.get("design_sha256") != declared_hash:
            raise ValueError("H4 design cannot be reproduced from its seed and roster.")

    return {
        "valid": True,
        "design_sha256": declared_hash,
        **expected_counts,
        "source_disjoint_stems": True,
        "execution_order_hashes_verified": True,
    }


def _first_present(row: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise ValueError(f"H4 {label} row is missing one of {tuple(keys)!r}.")


def _normalize_outcome_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    label: str,
) -> tuple[list[str], dict[str, float]]:
    order: list[str] = []
    outcomes: dict[str, float] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"H4 {label} row {index} is not an object.")
        raw_name = _first_present(row, _SCENARIO_KEYS, label)
        if not isinstance(raw_name, str) or not raw_name:
            raise ValueError(f"H4 {label} row {index} has an invalid scenario name.")
        if raw_name in outcomes:
            raise ValueError(f"H4 {label} has duplicate scenario {raw_name!r}.")
        raw_score = _first_present(row, _OUTCOME_KEYS, label)
        if isinstance(raw_score, bool):
            raise ValueError(f"H4 {label} score for {raw_name!r} is not numeric.")
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"H4 {label} score for {raw_name!r} is not numeric."
            ) from exc
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(
                f"H4 {label} score for {raw_name!r} must be within [0, 1]."
            )
        order.append(raw_name)
        outcomes[raw_name] = score
    return order, outcomes


def _paired_stem_bootstrap_ci(
    stem_deltas: Sequence[float],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float]:
    values = np.asarray(stem_deltas, dtype=float)
    rng = np.random.default_rng(seed)
    samples: list[NDArray[np.float64]] = []
    remaining = iterations
    while remaining:
        size = min(2_048, remaining)
        indices = rng.integers(0, len(values), size=(size, len(values)))
        samples.append(values[indices].mean(axis=1))
        remaining -= size
    quantiles = np.asarray(
        np.quantile(np.concatenate(samples), [0.025, 0.975]), dtype=float
    )
    return float(quantiles[0]), float(quantiles[1])


def analyze_paired_held_out(
    available_rows: Iterable[Mapping[str, Any]],
    masked_rows: Iterable[Mapping[str, Any]],
    design_manifest: Mapping[str, Any],
    *,
    integrity_checks: Mapping[str, bool],
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Analyze all held-out tasks and apply the exploratory pilot gate."""

    bootstrap_iterations = _required_iterations(bootstrap_iterations)
    bootstrap_seed = _required_seed(bootstrap_seed, "H4 bootstrap seed")
    design_validation = validate_split_design(design_manifest)
    expected_order = [str(name) for name in design_manifest["held_out_execution_order"]]
    available_order, available = _normalize_outcome_rows(
        tuple(available_rows), label="registry-available"
    )
    masked_order, masked = _normalize_outcome_rows(
        tuple(masked_rows), label="registry-masked"
    )
    if available_order != expected_order:
        raise ValueError(
            "H4 registry-available rows do not preserve the locked held-out order."
        )
    if masked_order != expected_order:
        raise ValueError(
            "H4 registry-masked rows do not preserve the locked held-out order."
        )
    if set(available) != set(masked) or len(available) != HELD_OUT_SCENARIO_COUNT:
        raise ValueError("H4 paired arms do not contain the complete held-out roster.")

    held_out_stems = [str(stem) for stem in design_manifest["held_out_stems"]]
    deltas_by_stem: dict[str, float] = {}
    for stem in held_out_stems:
        scenarios = [name for name in expected_order if scenario_stem(name) == stem]
        if len(scenarios) != EXPECTED_VARIANTS_PER_STEM:
            raise ValueError(f"H4 held-out stem {stem!r} lacks eight paired variants.")
        deltas_by_stem[stem] = float(
            np.mean([available[name] - masked[name] for name in scenarios])
        )

    available_mean = float(np.mean(list(available.values())))
    masked_mean = float(np.mean(list(masked.values())))
    difference = available_mean - masked_mean
    relative_lift = difference / masked_mean if masked_mean > 0 else None
    ci_low, ci_high = _paired_stem_bootstrap_ci(
        [deltas_by_stem[stem] for stem in held_out_stems],
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )

    normalized_integrity: dict[str, bool] = {}
    for key in REQUIRED_INTEGRITY_CHECKS:
        value = integrity_checks.get(key)
        if not isinstance(value, bool):
            raise ValueError(f"H4 integrity check {key!r} must be a boolean.")
        normalized_integrity[key] = value
    integrity_passed = all(normalized_integrity.values())
    effect_threshold_met = bool(
        relative_lift is not None and relative_lift >= 0.10 and ci_low > 0.0
    )
    if not integrity_passed:
        decision = INTEGRITY_FAILURE
    elif effect_threshold_met:
        decision = PILOT_THRESHOLD_CLEARED
    else:
        decision = PILOT_THRESHOLD_NOT_CLEARED

    result: dict[str, Any] = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "hypothesis": HYPOTHESIS,
        "status_label": decision,
        "estimand": (
            "paired intention-to-treat mean outcome difference, frozen registry "
            "available minus registry masked, on all held-out tasks"
        ),
        "counts": {
            "held_out_stems": HELD_OUT_STEM_COUNT,
            "scenarios_per_arm": HELD_OUT_SCENARIO_COUNT,
            "paired_scenarios": HELD_OUT_SCENARIO_COUNT,
            "bootstrap_iterations": bootstrap_iterations,
        },
        "outcomes": {
            "registry_available_mean": available_mean,
            "registry_masked_mean": masked_mean,
            "absolute_difference": difference,
            "relative_lift": relative_lift,
        },
        "uncertainty": {
            "method": "paired_stem_cluster_percentile_bootstrap",
            "cluster_count": HELD_OUT_STEM_COUNT,
            "seed": bootstrap_seed,
            "confidence_level": 0.95,
            "mean_difference_ci": [ci_low, ci_high],
        },
        "pilot_gate": {
            "exploratory_not_confirmatory": True,
            "minimum_relative_lift": 0.10,
            "requires_ci_lower_above_zero": True,
            "effect_threshold_met": effect_threshold_met,
            "integrity_passed": integrity_passed,
            "decision": decision,
        },
        "integrity": {
            **normalized_integrity,
            "passed": integrity_passed,
            "design_validation": design_validation,
        },
        "design_sha256": design_manifest["design_sha256"],
    }
    result["analysis_sha256"] = _canonical_sha256(result)
    return result
