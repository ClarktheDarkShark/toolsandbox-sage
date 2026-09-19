"""Randomized registry-availability design and analysis for the H3 pilot.

The design deliberately randomizes *availability*, not generated-tool use.  A
scenario remains in its assigned arm whether or not the model calls a generated
tool, so the analysis is intention-to-treat (ITT).

Matching is performed only after the H2 control arm is complete and uses only
those pre-treatment outcome scores.  The 1,032 benchmark scenarios collapse to
129 stems by removing exactly one of the seven ToolSandbox robustness suffixes.
All eight variants of a stem inherit the same assignment.  Sorted stem means
are partitioned into 63 adjacent pairs and one adjacent triplet; the triplet
position minimizes total within-block squared error.  Randomization assigns one
stem per pair and two stems in the triplet to registry-available, producing
65 available and 64 masked stems (520 and 512 scenarios, respectively).
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

ASSIGNMENT_SCHEMA_VERSION = 1
ANALYSIS_SCHEMA_VERSION = 1
DEFAULT_ASSIGNMENT_SEED = 20260918
DEFAULT_RANDOMIZATION_ITERATIONS = 100_000
DEFAULT_BOOTSTRAP_ITERATIONS = 20_000

EXPECTED_STEM_COUNT = 129
EXPECTED_VARIANTS_PER_STEM = 8
EXPECTED_SCENARIO_COUNT = EXPECTED_STEM_COUNT * EXPECTED_VARIANTS_PER_STEM

# These are deliberately the complete robustness-variant suffixes.  In
# particular, ``_arg_type_scrambled`` is not stripped on its own; doing that
# recursively would make the stem definition less auditable.
ROBUSTNESS_SUFFIXES = (
    "_3_distraction_tools_arg_description_scrambled",
    "_3_distraction_tools_arg_type_scrambled",
    "_3_distraction_tools_tool_description_scrambled",
    "_3_distraction_tools_tool_name_scrambled",
    "_10_distraction_tools",
    "_3_distraction_tools",
    "_all_tools",
)

_EXPECTED_VARIANT_LABELS = frozenset(("base", *ROBUSTNESS_SUFFIXES))
_SCENARIO_KEYS = ("scenario", "scenario_name", "name")
_CONTROL_OUTCOME_KEYS = (
    "control_outcome_similarity",
    "control_outcome",
    "outcome_score",
    "outcome_similarity",
)
_CANDIDATE_OUTCOME_KEYS = (
    "candidate_outcome_similarity",
    "candidate_outcome",
    "outcome_score",
    "outcome_similarity",
)


def scenario_stem(scenario_name: str) -> str:
    """Return the H3 randomization stem for one benchmark scenario.

    Only one of the seven complete robustness suffixes is removed.  Labels
    such as ``_alt``, ``_ambiguous``, and ``_multiple_user_turn`` remain part of
    the stem because they define distinct benchmark tasks in this design.
    """

    if not isinstance(scenario_name, str) or not scenario_name:
        raise ValueError("Scenario names must be non-empty strings.")
    for suffix in ROBUSTNESS_SUFFIXES:
        if scenario_name.endswith(suffix):
            stem = scenario_name[: -len(suffix)]
            if not stem:
                raise ValueError(f"Scenario has an empty stem: {scenario_name!r}")
            return stem
    return scenario_name


def scenario_variant(scenario_name: str) -> str:
    """Return ``base`` or the one complete robustness suffix for a scenario."""

    stem = scenario_stem(scenario_name)
    if stem == scenario_name:
        return "base"
    return scenario_name[len(stem) :]


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_seed(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _required_iterations(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer.")
    return int(value)


def _first_present(row: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise ValueError(f"Row has no {label}; expected one of {tuple(keys)!r}.")


def _normalize_outcome_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    outcome_keys: Sequence[str],
    label: str,
) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} row {index} is not an object.")
        raw_scenario = _first_present(row, _SCENARIO_KEYS, "scenario name")
        if not isinstance(raw_scenario, str) or not raw_scenario:
            raise ValueError(f"{label} row {index} has an invalid scenario name.")
        if raw_scenario in normalized:
            raise ValueError(f"{label} contains duplicate scenario {raw_scenario!r}.")
        raw_outcome = _first_present(row, outcome_keys, "outcome score")
        if isinstance(raw_outcome, bool):
            raise ValueError(f"{label} outcome for {raw_scenario!r} is not numeric.")
        try:
            outcome = float(raw_outcome)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{label} outcome for {raw_scenario!r} is not numeric."
            ) from exc
        if not math.isfinite(outcome) or not 0.0 <= outcome <= 1.0:
            raise ValueError(
                f"{label} outcome for {raw_scenario!r} must be within [0, 1]."
            )
        normalized[raw_scenario] = outcome
    return normalized


def _validate_benchmark_shape(outcomes: Mapping[str, float]) -> dict[str, list[str]]:
    if len(outcomes) != EXPECTED_SCENARIO_COUNT:
        raise ValueError(
            "H3 requires exactly "
            f"{EXPECTED_SCENARIO_COUNT} scored scenarios; received {len(outcomes)}."
        )
    groups: dict[str, list[str]] = defaultdict(list)
    for scenario in outcomes:
        groups[scenario_stem(scenario)].append(scenario)
    if len(groups) != EXPECTED_STEM_COUNT:
        raise ValueError(
            f"H3 requires exactly {EXPECTED_STEM_COUNT} stems; received {len(groups)}."
        )
    for stem, scenarios in sorted(groups.items()):
        variants = {scenario_variant(scenario) for scenario in scenarios}
        if len(scenarios) != EXPECTED_VARIANTS_PER_STEM:
            raise ValueError(
                f"Stem {stem!r} has {len(scenarios)} scenarios; expected "
                f"{EXPECTED_VARIANTS_PER_STEM}."
            )
        if variants != _EXPECTED_VARIANT_LABELS:
            missing = sorted(_EXPECTED_VARIANT_LABELS - variants)
            extra = sorted(variants - _EXPECTED_VARIANT_LABELS)
            raise ValueError(
                f"Stem {stem!r} has an invalid robustness roster "
                f"(missing={missing!r}, extra={extra!r})."
            )
    return {stem: sorted(scenarios) for stem, scenarios in groups.items()}


def _control_rows_sha256(outcomes: Mapping[str, float]) -> str:
    return _canonical_sha256(
        [
            {"scenario": scenario, "control_outcome": outcomes[scenario]}
            for scenario in sorted(outcomes)
        ]
    )


def _assignment_sha256(scenarios: Sequence[Mapping[str, Any]]) -> str:
    rows = [
        {
            "scenario": str(row["scenario"]),
            "stem": str(row["stem"]),
            "block_id": str(row["block_id"]),
            "assignment": str(row["assignment"]),
        }
        for row in sorted(scenarios, key=lambda item: str(item["scenario"]))
    ]
    return _canonical_sha256(rows)


def _block_cost(values: Sequence[float]) -> float:
    array = np.asarray(values, dtype=float)
    return float(np.square(array - array.mean()).sum())


def _matched_blocks(
    stem_means: Mapping[str, float],
) -> tuple[list[list[str]], int, float]:
    ordered = sorted(stem_means, key=lambda stem: (stem_means[stem], stem))
    if len(ordered) != EXPECTED_STEM_COUNT:
        raise ValueError(
            f"Matching requires {EXPECTED_STEM_COUNT} stem means; got {len(ordered)}."
        )

    best: tuple[float, int, list[list[str]]] | None = None
    # A triplet may start only at an even index so the stems on both sides can
    # be partitioned into adjacent pairs.
    for triplet_start in range(0, len(ordered) - 2, 2):
        candidate: list[list[str]] = []
        cursor = 0
        while cursor < len(ordered):
            size = 3 if cursor == triplet_start else 2
            candidate.append(ordered[cursor : cursor + size])
            cursor += size
        cost = sum(
            _block_cost([stem_means[stem] for stem in block]) for block in candidate
        )
        key = (cost, triplet_start)
        if best is None or key < best[:2]:
            best = (cost, triplet_start, candidate)
    if best is None:  # pragma: no cover - protected by the exact stem count
        raise RuntimeError("Unable to construct matched H3 blocks.")
    cost, triplet_start, blocks = best
    if sum(len(block) == 2 for block in blocks) != 63:
        raise RuntimeError("Internal error: H3 matching did not produce 63 pairs.")
    if sum(len(block) == 3 for block in blocks) != 1:
        raise RuntimeError("Internal error: H3 matching did not produce one triplet.")
    return blocks, triplet_start, cost


def _construct_assignment(
    control_outcomes: Mapping[str, float],
    *,
    seed: int,
) -> dict[str, Any]:
    groups = _validate_benchmark_shape(control_outcomes)
    stem_means = {
        stem: float(np.mean([control_outcomes[name] for name in scenarios]))
        for stem, scenarios in groups.items()
    }
    matched_blocks, triplet_start, matching_cost = _matched_blocks(stem_means)
    rng = np.random.default_rng(seed)

    blocks: list[dict[str, Any]] = []
    stem_rows: list[dict[str, Any]] = []
    assignments: dict[str, tuple[str, str]] = {}
    for block_index, stems in enumerate(matched_blocks, start=1):
        block_id = f"B{block_index:03d}"
        if len(stems) == 2:
            available_indices = {int(rng.integers(0, 2))}
        else:
            masked_index = int(rng.integers(0, 3))
            available_indices = {index for index in range(3) if index != masked_index}
        available_stems = [
            stem for index, stem in enumerate(stems) if index in available_indices
        ]
        masked_stems = [
            stem for index, stem in enumerate(stems) if index not in available_indices
        ]
        blocks.append(
            {
                "block_id": block_id,
                "size": len(stems),
                "stems": list(stems),
                "control_means": [stem_means[stem] for stem in stems],
                "available_stems": available_stems,
                "masked_stems": masked_stems,
            }
        )
        for index, stem in enumerate(stems):
            assignment = (
                "registry_available"
                if index in available_indices
                else "registry_masked"
            )
            assignments[stem] = (block_id, assignment)
            stem_rows.append(
                {
                    "stem": stem,
                    "block_id": block_id,
                    "assignment": assignment,
                    "control_mean": stem_means[stem],
                    "scenario_count": len(groups[stem]),
                }
            )

    scenario_rows: list[dict[str, str]] = []
    for stem, scenarios in groups.items():
        block_id, assignment = assignments[stem]
        scenario_rows.extend(
            {
                "scenario": scenario,
                "stem": stem,
                "block_id": block_id,
                "assignment": assignment,
            }
            for scenario in scenarios
        )
    scenario_rows.sort(key=lambda row: row["scenario"])
    stem_rows.sort(key=lambda row: row["stem"])

    available_stem_count = sum(
        row["assignment"] == "registry_available" for row in stem_rows
    )
    masked_stem_count = len(stem_rows) - available_stem_count
    available_scenario_count = sum(
        row["assignment"] == "registry_available" for row in scenario_rows
    )
    masked_scenario_count = len(scenario_rows) - available_scenario_count

    manifest: dict[str, Any] = {
        "schema_version": ASSIGNMENT_SCHEMA_VERSION,
        "design": "matched_block_randomized_registry_availability",
        "analysis_principle": "intention_to_treat_by_assigned_availability",
        "seed": seed,
        "random_generator": "numpy.random.Generator(PCG64)",
        "matching": {
            "source": "h2_control_outcome_score_only",
            "algorithm": "sorted_adjacent_minimum_sse_63_pairs_one_triplet",
            "triplet_start_zero_based": triplet_start,
            "total_within_block_sse": matching_cost,
            "pair_count": 63,
            "triplet_count": 1,
        },
        "robustness_suffixes": list(ROBUSTNESS_SUFFIXES),
        "expected_variants_per_stem": EXPECTED_VARIANTS_PER_STEM,
        "counts": {
            "stems": len(stem_rows),
            "scenarios": len(scenario_rows),
            "registry_available_stems": available_stem_count,
            "registry_masked_stems": masked_stem_count,
            "registry_available_scenarios": available_scenario_count,
            "registry_masked_scenarios": masked_scenario_count,
        },
        "control_rows_sha256": _control_rows_sha256(control_outcomes),
        "blocks": blocks,
        "stems": stem_rows,
        "scenarios": scenario_rows,
    }
    manifest["assignment_sha256"] = _assignment_sha256(scenario_rows)
    manifest["design_sha256"] = _canonical_sha256(manifest)
    return manifest


def build_registry_assignment(
    control_rows: Iterable[Mapping[str, Any]],
    *,
    seed: int = DEFAULT_ASSIGNMENT_SEED,
) -> dict[str, Any]:
    """Create the frozen H3 assignment from completed H2 control rows."""

    seed = _required_seed(seed, "assignment seed")
    control_rows = tuple(control_rows)
    outcomes = _normalize_outcome_rows(
        control_rows,
        outcome_keys=_CONTROL_OUTCOME_KEYS,
        label="H2 control",
    )
    manifest = _construct_assignment(outcomes, seed=seed)
    validate_registry_assignment(manifest, control_rows=control_rows)
    return manifest


def validate_registry_assignment(
    manifest: Mapping[str, Any],
    *,
    control_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate assignment structure, hashes, balance, and optional provenance.

    A ``ValueError`` is raised on any failure.  The returned report is compact
    enough to embed directly in a run manifest or dashboard data file.
    """

    if not isinstance(manifest, Mapping):
        raise ValueError("H3 assignment manifest must be an object.")
    if manifest.get("schema_version") != ASSIGNMENT_SCHEMA_VERSION:
        raise ValueError("Unsupported H3 assignment schema version.")
    seed = _required_seed(manifest.get("seed"), "assignment seed")
    if tuple(manifest.get("robustness_suffixes") or ()) != ROBUSTNESS_SUFFIXES:
        raise ValueError("H3 robustness suffix declaration does not match the design.")

    raw_scenarios = manifest.get("scenarios")
    raw_stems = manifest.get("stems")
    raw_blocks = manifest.get("blocks")
    if not isinstance(raw_scenarios, list) or not isinstance(raw_stems, list):
        raise ValueError("H3 assignment must contain scenario and stem lists.")
    if not isinstance(raw_blocks, list):
        raise ValueError("H3 assignment must contain a block list.")
    if len(raw_scenarios) != EXPECTED_SCENARIO_COUNT:
        raise ValueError("H3 assignment does not contain exactly 1,032 scenarios.")
    if len(raw_stems) != EXPECTED_STEM_COUNT:
        raise ValueError("H3 assignment does not contain exactly 129 stems.")
    if len(raw_blocks) != 64:
        raise ValueError("H3 assignment must contain exactly 64 matched blocks.")

    scenario_names: set[str] = set()
    scenarios_by_stem: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in raw_scenarios:
        if not isinstance(row, Mapping):
            raise ValueError("H3 scenario assignment rows must be objects.")
        scenario = row.get("scenario")
        stem = row.get("stem")
        assignment = row.get("assignment")
        if not isinstance(scenario, str) or not scenario:
            raise ValueError("H3 scenario assignment has an invalid scenario name.")
        if scenario in scenario_names:
            raise ValueError(f"Duplicate H3 scenario assignment: {scenario!r}.")
        scenario_names.add(scenario)
        if stem != scenario_stem(scenario):
            raise ValueError(f"H3 scenario {scenario!r} has an incorrect stem.")
        if assignment not in {"registry_available", "registry_masked"}:
            raise ValueError(f"H3 scenario {scenario!r} has an invalid assignment.")
        scenarios_by_stem[str(stem)].append(row)

    stem_records: dict[str, Mapping[str, Any]] = {}
    for row in raw_stems:
        if not isinstance(row, Mapping) or not isinstance(row.get("stem"), str):
            raise ValueError("H3 stem assignment rows must name a stem.")
        stem = str(row["stem"])
        if stem in stem_records:
            raise ValueError(f"Duplicate H3 stem assignment: {stem!r}.")
        stem_records[stem] = row
    if set(stem_records) != set(scenarios_by_stem):
        raise ValueError("H3 stem and scenario assignment rosters differ.")
    for stem, rows in scenarios_by_stem.items():
        variants = {scenario_variant(str(row["scenario"])) for row in rows}
        assignments = {row.get("assignment") for row in rows}
        block_ids = {row.get("block_id") for row in rows}
        record = stem_records[stem]
        if (
            len(rows) != EXPECTED_VARIANTS_PER_STEM
            or variants != _EXPECTED_VARIANT_LABELS
        ):
            raise ValueError(
                f"H3 stem {stem!r} does not have the complete variant roster."
            )
        if assignments != {record.get("assignment")}:
            raise ValueError(
                f"H3 stem {stem!r} does not have one inherited assignment."
            )
        if block_ids != {record.get("block_id")}:
            raise ValueError(f"H3 stem {stem!r} does not have one inherited block.")

    block_stems: set[str] = set()
    pair_count = 0
    triplet_count = 0
    for block in raw_blocks:
        if not isinstance(block, Mapping):
            raise ValueError("H3 block rows must be objects.")
        stems = block.get("stems")
        available = block.get("available_stems")
        masked = block.get("masked_stems")
        if (
            not isinstance(stems, list)
            or not isinstance(available, list)
            or not isinstance(masked, list)
        ):
            raise ValueError("H3 block stem lists are malformed.")
        if len(stems) == 2:
            pair_count += 1
            if len(available) != 1 or len(masked) != 1:
                raise ValueError("Each H3 pair must allocate one stem to each arm.")
        elif len(stems) == 3:
            triplet_count += 1
            if len(available) != 2 or len(masked) != 1:
                raise ValueError(
                    "The H3 triplet must allocate two available and one masked."
                )
        else:
            raise ValueError("H3 blocks must be pairs or a triplet.")
        if set(stems) != set(available) | set(masked) or set(available) & set(masked):
            raise ValueError("H3 block assignments do not partition their stems.")
        if block_stems & set(stems):
            raise ValueError("A stem appears in more than one H3 block.")
        block_stems.update(str(stem) for stem in stems)
        block_id = block.get("block_id")
        for stem in stems:
            block_record = stem_records.get(str(stem))
            if block_record is None or block_record.get("block_id") != block_id:
                raise ValueError("H3 block and stem records disagree.")
            expected = "registry_available" if stem in available else "registry_masked"
            if block_record.get("assignment") != expected:
                raise ValueError("H3 block and stem assignments disagree.")
    if pair_count != 63 or triplet_count != 1 or block_stems != set(stem_records):
        raise ValueError("H3 assignment must contain 63 pairs and one triplet.")

    available_stems = sum(
        row.get("assignment") == "registry_available" for row in raw_stems
    )
    available_scenarios = sum(
        row.get("assignment") == "registry_available" for row in raw_scenarios
    )
    expected_counts = {
        "stems": 129,
        "scenarios": 1032,
        "registry_available_stems": 65,
        "registry_masked_stems": 64,
        "registry_available_scenarios": 520,
        "registry_masked_scenarios": 512,
    }
    if available_stems != 65 or available_scenarios != 520:
        raise ValueError(
            "H3 assignment arm counts are not 65/64 stems and 520/512 tasks."
        )
    if manifest.get("counts") != expected_counts:
        raise ValueError("H3 assignment count declaration is inconsistent.")
    if manifest.get("assignment_sha256") != _assignment_sha256(raw_scenarios):
        raise ValueError("H3 assignment hash does not match its scenario assignments.")
    without_design_hash = dict(manifest)
    declared_design_hash = without_design_hash.pop("design_sha256", None)
    if declared_design_hash != _canonical_sha256(without_design_hash):
        raise ValueError("H3 design hash does not match the assignment manifest.")

    if control_rows is not None:
        control_outcomes = _normalize_outcome_rows(
            control_rows,
            outcome_keys=_CONTROL_OUTCOME_KEYS,
            label="H2 control",
        )
        _validate_benchmark_shape(control_outcomes)
        if set(control_outcomes) != scenario_names:
            raise ValueError("H2 control and H3 assignment scenario rosters differ.")
        if manifest.get("control_rows_sha256") != _control_rows_sha256(
            control_outcomes
        ):
            raise ValueError(
                "H3 assignment does not match the supplied H2 control rows."
            )
        expected_manifest = _construct_assignment(control_outcomes, seed=seed)
        if expected_manifest.get("design_sha256") != manifest.get("design_sha256"):
            raise ValueError(
                "H3 assignment cannot be reproduced from its control rows and seed."
            )

    return {
        "valid": True,
        "assignment_sha256": manifest["assignment_sha256"],
        "design_sha256": manifest["design_sha256"],
        "control_rows_verified": control_rows is not None,
        "pair_count": pair_count,
        "triplet_count": triplet_count,
        **expected_counts,
    }


def assignment_by_scenario(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Return the runtime-facing scenario-to-availability assignment map."""

    validate_registry_assignment(manifest)
    return {
        str(row["scenario"]): str(row["assignment"]) for row in manifest["scenarios"]
    }


def _stem_means(outcomes: Mapping[str, float]) -> dict[str, float]:
    groups: dict[str, list[float]] = defaultdict(list)
    for scenario, value in outcomes.items():
        groups[scenario_stem(scenario)].append(value)
    return {stem: float(np.mean(values)) for stem, values in groups.items()}


def _cluster_bootstrap_ci(
    values: Mapping[str, float],
    assignments: Mapping[str, str],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float]:
    available = np.asarray(
        [
            values[stem]
            for stem in sorted(values)
            if assignments[stem] == "registry_available"
        ],
        dtype=float,
    )
    masked = np.asarray(
        [
            values[stem]
            for stem in sorted(values)
            if assignments[stem] == "registry_masked"
        ],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    samples: list[NDArray[np.float64]] = []
    remaining = iterations
    while remaining:
        size = min(2_048, remaining)
        available_indices = rng.integers(0, len(available), size=(size, len(available)))
        masked_indices = rng.integers(0, len(masked), size=(size, len(masked)))
        samples.append(
            available[available_indices].mean(axis=1)
            - masked[masked_indices].mean(axis=1)
        )
        remaining -= size
    quantiles = np.asarray(
        np.quantile(np.concatenate(samples), [0.025, 0.975]), dtype=float
    ).reshape(-1)
    return float(quantiles[0]), float(quantiles[1])


def _restricted_randomization_p(
    values: Mapping[str, float],
    blocks: Sequence[Mapping[str, Any]],
    assignments: Mapping[str, str],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float, int]:
    available_values = [
        values[stem]
        for stem, assignment in assignments.items()
        if assignment == "registry_available"
    ]
    masked_values = [
        values[stem]
        for stem, assignment in assignments.items()
        if assignment == "registry_masked"
    ]
    observed = float(np.mean(available_values) - np.mean(masked_values))

    pair_values: list[tuple[float, float]] = []
    triplet_values: tuple[float, float, float] | None = None
    for block in blocks:
        stems = [str(stem) for stem in block["stems"]]
        block_values = tuple(values[stem] for stem in stems)
        if len(stems) == 2:
            pair_values.append((block_values[0], block_values[1]))
        else:
            triplet_values = (block_values[0], block_values[1], block_values[2])
    if len(pair_values) != 63 or triplet_values is None:
        raise ValueError("Restricted randomization requires 63 pairs and one triplet.")

    pair_array = np.asarray(pair_values, dtype=float)
    triple_array = np.asarray(triplet_values, dtype=float)
    total_sum = float(pair_array.sum() + triple_array.sum())
    rng = np.random.default_rng(seed)
    extreme = 0
    processed = 0
    while processed < iterations:
        size = min(4_096, iterations - processed)
        selected = rng.integers(0, 2, size=(size, len(pair_array)))
        pair_available = pair_array[np.arange(len(pair_array)), selected].sum(axis=1)
        triple_masked_index = rng.integers(0, 3, size=size)
        triple_masked = triple_array[triple_masked_index]
        available_sum = pair_available + triple_array.sum() - triple_masked
        masked_sum = total_sum - available_sum
        permuted = available_sum / 65.0 - masked_sum / 64.0
        extreme += int(np.count_nonzero(permuted >= observed - 1e-15))
        processed += size
    # The plus-one correction is valid for a Monte Carlo randomization test and
    # prevents a reported p-value of zero.
    p_value = (extreme + 1) / (iterations + 1)
    return observed, float(p_value), extreme


def analyze_registry_availability(
    candidate_rows: Iterable[Mapping[str, Any]],
    control_rows: Iterable[Mapping[str, Any]],
    assignment_manifest: Mapping[str, Any],
    *,
    randomization_iterations: int = DEFAULT_RANDOMIZATION_ITERATIONS,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    randomization_seed: int | None = None,
    bootstrap_seed: int | None = None,
) -> dict[str, Any]:
    """Analyze the randomized mixed-arm run under the ITT principle.

    The primary estimate is the registry-available minus registry-masked mean
    outcome score.  The p-value uses the restricted block randomization, and
    the percentile confidence interval resamples the 129 task stems as clusters
    within assigned arm.  A control-adjusted gain contrast is reported only as
    a precision/sensitivity result; it does not replace the primary ITT effect.
    """

    randomization_iterations = _required_iterations(
        randomization_iterations, "randomization iterations"
    )
    bootstrap_iterations = _required_iterations(
        bootstrap_iterations, "bootstrap iterations"
    )
    candidate_rows = tuple(candidate_rows)
    control_rows = tuple(control_rows)
    assignment_seed = _required_seed(assignment_manifest.get("seed"), "assignment seed")
    if randomization_seed is None:
        randomization_seed = assignment_seed + 1
    if bootstrap_seed is None:
        bootstrap_seed = assignment_seed + 2
    randomization_seed = _required_seed(randomization_seed, "randomization seed")
    bootstrap_seed = _required_seed(bootstrap_seed, "bootstrap seed")

    control_outcomes = _normalize_outcome_rows(
        control_rows,
        outcome_keys=_CONTROL_OUTCOME_KEYS,
        label="H2 control",
    )
    candidate_outcomes = _normalize_outcome_rows(
        candidate_rows,
        outcome_keys=_CANDIDATE_OUTCOME_KEYS,
        label="H3 candidate",
    )
    validation = validate_registry_assignment(
        assignment_manifest,
        control_rows=control_rows,
    )
    assigned_scenarios = {
        str(row["scenario"]) for row in assignment_manifest["scenarios"]
    }
    if set(candidate_outcomes) != assigned_scenarios:
        missing = sorted(assigned_scenarios - set(candidate_outcomes))
        extra = sorted(set(candidate_outcomes) - assigned_scenarios)
        raise ValueError(
            "H3 ITT analysis requires every randomized scenario exactly once "
            f"(missing={missing[:5]!r}, extra={extra[:5]!r})."
        )
    if set(control_outcomes) != assigned_scenarios:
        raise ValueError("H2 control and H3 candidate scenario rosters differ.")

    stem_assignment = {
        str(row["stem"]): str(row["assignment"]) for row in assignment_manifest["stems"]
    }
    candidate_stem_means = _stem_means(candidate_outcomes)
    control_stem_means = _stem_means(control_outcomes)
    gain_stem_means = {
        stem: candidate_stem_means[stem] - control_stem_means[stem]
        for stem in candidate_stem_means
    }
    available_stems = [
        stem
        for stem, assignment in stem_assignment.items()
        if assignment == "registry_available"
    ]
    masked_stems = [
        stem
        for stem, assignment in stem_assignment.items()
        if assignment == "registry_masked"
    ]

    def arm_mean(values: Mapping[str, float], stems: Sequence[str]) -> float:
        return float(np.mean([values[stem] for stem in stems]))

    available_mean = arm_mean(candidate_stem_means, available_stems)
    masked_mean = arm_mean(candidate_stem_means, masked_stems)
    estimate, p_value, extreme_count = _restricted_randomization_p(
        candidate_stem_means,
        assignment_manifest["blocks"],
        stem_assignment,
        iterations=randomization_iterations,
        seed=randomization_seed,
    )
    cluster_ci = _cluster_bootstrap_ci(
        candidate_stem_means,
        stem_assignment,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    adjusted_estimate = arm_mean(gain_stem_means, available_stems) - arm_mean(
        gain_stem_means, masked_stems
    )
    adjusted_ci = _cluster_bootstrap_ci(
        gain_stem_means,
        stem_assignment,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed + 1,
    )
    control_balance = arm_mean(control_stem_means, available_stems) - arm_mean(
        control_stem_means, masked_stems
    )

    result: dict[str, Any] = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "hypothesis": (
            "Randomized availability of the frozen generated registry improves "
            "mean outcome score over registry-masked SAGE."
        ),
        "status": "observed_pilot_estimate",
        "estimand": "intention_to_treat_available_minus_masked_mean_outcome_score",
        "analysis_unit": "task_stem_cluster_with_eight_robustness_variants",
        "integrity": {
            "complete_itt_roster": True,
            "conditions_defined_by_assignment_not_tool_call": True,
            "assignment_validation": validation,
        },
        "counts": dict(assignment_manifest["counts"]),
        "outcomes": {
            "registry_available_mean": available_mean,
            "registry_masked_mean": masked_mean,
            "absolute_difference": estimate,
            "relative_difference_percent": (
                (estimate / masked_mean * 100.0) if masked_mean else None
            ),
        },
        "uncertainty": {
            "stem_cluster_percentile_bootstrap_95_ci": list(cluster_ci),
            "bootstrap_iterations": bootstrap_iterations,
            "bootstrap_seed": bootstrap_seed,
            "restricted_randomization_alternative": "available_greater_than_masked",
            "restricted_randomization_one_sided_p_value": p_value,
            "randomization_iterations": randomization_iterations,
            "randomization_seed": randomization_seed,
            "randomization_extreme_count": extreme_count,
            "monte_carlo_plus_one_correction": True,
        },
        "control_adjusted_sensitivity": {
            "available_mean_candidate_minus_control": arm_mean(
                gain_stem_means, available_stems
            ),
            "masked_mean_candidate_minus_control": arm_mean(
                gain_stem_means, masked_stems
            ),
            "difference": adjusted_estimate,
            "stem_cluster_percentile_bootstrap_95_ci": list(adjusted_ci),
        },
        "randomization_balance": {
            "available_h2_control_mean": arm_mean(control_stem_means, available_stems),
            "masked_h2_control_mean": arm_mean(control_stem_means, masked_stems),
            "available_minus_masked_h2_control_mean": control_balance,
        },
        "assignment_sha256": assignment_manifest["assignment_sha256"],
        "design_sha256": assignment_manifest["design_sha256"],
        "candidate_rows_sha256": _canonical_sha256(
            [
                {
                    "scenario": scenario,
                    "candidate_outcome": candidate_outcomes[scenario],
                }
                for scenario in sorted(candidate_outcomes)
            ]
        ),
    }
    result["analysis_sha256"] = _canonical_sha256(result)
    return result
