#!/usr/bin/env python3
"""Strict H2 analysis for the one-replication SAGE hypothesis pilot.

The primary interval resamples the 129 original-scenario stems as paired
clusters, keeping each stem's eight ToolSandbox robustness variants together.
This is a pilot threshold assessment, not confirmatory hypothesis support.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
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

_base_task_family: Callable[[str], str] | None
try:
    from sage_ts.evaluation.task_strata import base_task_family
except ImportError:  # pragma: no cover - the current repository provides it
    _base_task_family = None
else:
    _base_task_family = base_task_family

ANALYSIS_SCHEMA_VERSION = 1
BOOTSTRAP_DRAWS = 50_000
BOOTSTRAP_SEED = 20260918
CONFIDENCE_LEVEL = 0.95
RELATIVE_LIFT_THRESHOLD = 0.10
EXPECTED_FAMILY_COUNT = 77

PILOT_THRESHOLD_CLEARED = "PILOT_THRESHOLD_CLEARED"
PILOT_THRESHOLD_NOT_CLEARED = "PILOT_THRESHOLD_NOT_CLEARED"
INTEGRITY_FAILURE = "INTEGRITY_FAILURE"

_EXPECTED_VARIANTS = frozenset(("base", *ROBUSTNESS_SUFFIXES))


@dataclass(frozen=True)
class ArmData:
    """Validated arm rows in their original ToolSandbox execution order."""

    names: tuple[str, ...]
    outcomes: NDArray[np.float64]
    canonical_similarities: NDArray[np.float64]
    exception_rows: tuple[str, ...]


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _input_metadata(path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {"path": str(path.resolve()), "sha256": None}
    if path.is_symlink():
        metadata["error"] = "symlink_forbidden"
    elif not path.is_file():
        metadata["error"] = "file_missing"
    else:
        try:
            metadata["sha256"] = _file_sha256(path)
            metadata["size_bytes"] = path.stat().st_size
        except OSError as exc:
            metadata["error"] = f"file_unreadable:{type(exc).__name__}"
    return metadata


def _strict_verification_receipt(
    *,
    run_root: Path,
    control_summary_path: Path,
    candidate_summary_path: Path,
    expect_reflection: str,
) -> dict[str, Any]:
    """Re-run the publication verifier and bind it to the analyzed files."""

    from scripts.verify_publication_run import verify_run

    verification = verify_run(
        run_root,
        expected_tasks=EXPECTED_SCENARIO_COUNT,
        expect_reflection=expect_reflection,
        gate_purpose="campaign-inclusion",
    )
    verified_root = Path(str(verification["run_root"])).resolve()
    if verified_root != run_root.resolve():
        raise ValueError("Strict verifier selected a different H2 run root.")
    protocol_path = verified_root / "protocol_manifest.json"
    protocol, protocol_errors = _load_object(protocol_path, "protocol")
    if protocol is None or protocol_errors:
        raise ValueError("H2 protocol manifest could not be loaded after verification.")
    declared_control = Path(str(protocol.get("control_dir") or "")).resolve()
    declared_candidate = Path(str(protocol.get("candidate_dir") or "")).resolve()
    if control_summary_path.resolve() != declared_control / "result_summary.json":
        raise ValueError(
            "H2 control summary is not the strictly verified control file."
        )
    if candidate_summary_path.resolve() != declared_candidate / "result_summary.json":
        raise ValueError(
            "H2 candidate summary is not the strictly verified candidate file."
        )
    comparison_path = verified_root / "paired_comparison.json"
    pilot_manifest_path = Path(str(protocol.get("hypothesis_pilot_manifest"))).resolve()
    return {
        "status": "pass",
        "run_root": str(verified_root),
        "protocol_manifest": {
            "path": str(protocol_path),
            "sha256": _file_sha256(protocol_path),
        },
        "paired_comparison": {
            "path": str(comparison_path),
            "sha256": _file_sha256(comparison_path),
        },
        "hypothesis_pilot_manifest": {
            "path": str(pilot_manifest_path),
            "sha256_at_verification": _file_sha256(pilot_manifest_path),
        },
        "verification": verification,
    }


def _load_object(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if path.is_symlink():
        return None, [f"{label}:summary_symlink_forbidden"]
    if not path.is_file():
        return None, [f"{label}:summary_missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{label}:summary_malformed:{type(exc).__name__}"]
    if not isinstance(payload, dict):
        errors.append(f"{label}:summary_must_be_object")
        return None, errors
    return payload, errors


def _validate_arm(payload: Mapping[str, Any], label: str) -> tuple[ArmData, list[str]]:
    errors: list[str] = []
    raw_rows = payload.get("per_scenario_results")
    if not isinstance(raw_rows, list):
        return (
            ArmData(
                (),
                np.asarray([], dtype=float),
                np.asarray([], dtype=float),
                (),
            ),
            [f"{label}:per_scenario_results_must_be_list"],
        )
    if len(raw_rows) != EXPECTED_SCENARIO_COUNT:
        errors.append(f"{label}:row_count:{len(raw_rows)}!={EXPECTED_SCENARIO_COUNT}")

    names: list[str] = []
    outcomes: list[float] = []
    canonical_similarities: list[float] = []
    exception_rows: list[str] = []
    seen: set[str] = set()
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            errors.append(f"{label}:row_{index}_must_be_object")
            continue
        raw_name = raw_row.get("name")
        if not isinstance(raw_name, str) or not raw_name:
            errors.append(f"{label}:row_{index}_name_invalid")
            continue
        names.append(raw_name)
        if raw_name in seen:
            errors.append(f"{label}:duplicate_scenario:{raw_name}")
        seen.add(raw_name)

        if "traceback" not in raw_row or "exception_type" not in raw_row:
            errors.append(f"{label}:exception_fields_missing:{raw_name}")
        traceback_value = raw_row.get("traceback")
        exception_value = raw_row.get("exception_type")
        if traceback_value not in (None, "") or exception_value not in (None, ""):
            exception_rows.append(raw_name)

        raw_outcome = raw_row.get("outcome_similarity")
        if isinstance(raw_outcome, bool) or not isinstance(raw_outcome, (int, float)):
            errors.append(f"{label}:outcome_not_numeric:{raw_name}")
            outcomes.append(math.nan)
            continue
        outcome = float(raw_outcome)
        if not math.isfinite(outcome) or not 0.0 <= outcome <= 1.0:
            errors.append(f"{label}:outcome_out_of_range:{raw_name}")
        outcomes.append(outcome)

        raw_similarity = raw_row.get("similarity")
        if isinstance(raw_similarity, bool) or not isinstance(
            raw_similarity, (int, float)
        ):
            errors.append(f"{label}:canonical_similarity_not_numeric:{raw_name}")
            canonical_similarities.append(math.nan)
            continue
        similarity = float(raw_similarity)
        if not math.isfinite(similarity) or not 0.0 <= similarity <= 1.0:
            errors.append(f"{label}:canonical_similarity_out_of_range:{raw_name}")
        canonical_similarities.append(similarity)

    if exception_rows:
        errors.append(f"{label}:runtime_exception_rows:{len(exception_rows)}")
    if len(names) != len(raw_rows):
        errors.append(f"{label}:not_all_rows_have_valid_names")
    if len(outcomes) != len(raw_rows):
        errors.append(f"{label}:not_all_rows_have_outcomes")
    if len(canonical_similarities) != len(raw_rows):
        errors.append(f"{label}:not_all_rows_have_canonical_similarity")
    return (
        ArmData(
            tuple(names),
            np.asarray(outcomes, dtype=float),
            np.asarray(canonical_similarities, dtype=float),
            tuple(exception_rows),
        ),
        errors,
    )


def _validate_stem_roster(
    names: Sequence[str],
) -> tuple[dict[str, list[int]], list[str]]:
    errors: list[str] = []
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(names):
        try:
            stem = scenario_stem(name)
        except ValueError as exc:
            errors.append(f"scenario_stem_invalid:{name}:{exc}")
            continue
        grouped[stem].append(index)
    if len(grouped) != EXPECTED_STEM_COUNT:
        errors.append(f"stem_count:{len(grouped)}!={EXPECTED_STEM_COUNT}")
    for stem, indices in sorted(grouped.items()):
        try:
            variants = {scenario_variant(names[index]) for index in indices}
        except ValueError as exc:  # pragma: no cover - guarded above
            errors.append(f"scenario_variant_invalid:{stem}:{exc}")
            continue
        if len(indices) != EXPECTED_VARIANTS_PER_STEM:
            errors.append(
                f"stem_variant_count:{stem}:{len(indices)}!="
                f"{EXPECTED_VARIANTS_PER_STEM}"
            )
        if variants != _EXPECTED_VARIANTS:
            missing = sorted(_EXPECTED_VARIANTS - variants)
            extra = sorted(variants - _EXPECTED_VARIANTS)
            errors.append(
                f"stem_variant_roster:{stem}:missing={missing!r}:extra={extra!r}"
            )
    return dict(grouped), errors


def _cluster_summaries(
    control: NDArray[np.float64],
    candidate: NDArray[np.float64],
    clusters: Mapping[str, Sequence[int]],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
    control_sums: list[float] = []
    candidate_sums: list[float] = []
    counts: list[int] = []
    for cluster in sorted(clusters):
        indices = np.asarray(clusters[cluster], dtype=np.int64)
        control_sums.append(float(control[indices].sum()))
        candidate_sums.append(float(candidate[indices].sum()))
        counts.append(len(indices))
    return (
        np.asarray(control_sums, dtype=float),
        np.asarray(candidate_sums, dtype=float),
        np.asarray(counts, dtype=np.int64),
    )


def _paired_cluster_bootstrap(
    control: NDArray[np.float64],
    candidate: NDArray[np.float64],
    clusters: Mapping[str, Sequence[int]],
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Percentile CI from paired resampling of whole task clusters."""

    if draws < 1:
        raise ValueError("Bootstrap draws must be positive.")
    if not clusters:
        raise ValueError("Bootstrap requires at least one cluster.")
    control_sums, candidate_sums, counts = _cluster_summaries(
        control, candidate, clusters
    )
    rng = np.random.default_rng(seed)
    differences: list[NDArray[np.float64]] = []
    relative_lifts: list[NDArray[np.float64]] = []
    remaining = draws
    while remaining:
        chunk_size = min(2_048, remaining)
        sampled = rng.integers(
            0, len(counts), size=(chunk_size, len(counts)), dtype=np.int64
        )
        sampled_counts = counts[sampled].sum(axis=1)
        sampled_control = control_sums[sampled].sum(axis=1) / sampled_counts
        sampled_candidate = candidate_sums[sampled].sum(axis=1) / sampled_counts
        difference = sampled_candidate - sampled_control
        differences.append(difference)
        relative = np.full(chunk_size, np.nan, dtype=float)
        np.divide(
            difference,
            sampled_control,
            out=relative,
            where=sampled_control > 0.0,
        )
        relative_lifts.append(relative)
        remaining -= chunk_size

    difference_samples = np.concatenate(differences)
    relative_samples = np.concatenate(relative_lifts)
    difference_quantiles = np.asarray(
        np.percentile(difference_samples, [2.5, 97.5], method="linear"),
        dtype=float,
    )
    finite_relative = relative_samples[np.isfinite(relative_samples)]
    relative_ci: dict[str, float] | None
    if len(finite_relative) != draws:
        relative_ci = None
    else:
        relative_quantiles = np.asarray(
            np.percentile(finite_relative, [2.5, 97.5], method="linear"),
            dtype=float,
        )
        relative_ci = {
            "lower": float(relative_quantiles[0]),
            "upper": float(relative_quantiles[1]),
        }
    return {
        "method": "paired_cluster_percentile_bootstrap",
        "confidence_level": CONFIDENCE_LEVEL,
        "draws": draws,
        "seed": seed,
        "cluster_count": len(clusters),
        "absolute_difference_ci": {
            "lower": float(difference_quantiles[0]),
            "upper": float(difference_quantiles[1]),
        },
        "relative_lift_ci": relative_ci,
        "zero_control_draw_count": int(draws - len(finite_relative)),
    }


def _family_sensitivity(
    names: Sequence[str],
    control: NDArray[np.float64],
    candidate: NDArray[np.float64],
) -> dict[str, Any]:
    if _base_task_family is None:
        return {
            "status": "omitted",
            "reason": "stable_base_task_family_helper_unavailable",
            "expected_family_count": EXPECTED_FAMILY_COUNT,
        }
    families: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(names):
        family = _base_task_family(name)
        if not isinstance(family, str) or not family:
            return {
                "status": "omitted",
                "reason": f"base_task_family_returned_invalid_label:{name}",
                "expected_family_count": EXPECTED_FAMILY_COUNT,
            }
        families[family].append(index)
    if len(families) != EXPECTED_FAMILY_COUNT:
        return {
            "status": "omitted",
            "reason": (
                f"base_task_family_count:{len(families)}!={EXPECTED_FAMILY_COUNT}"
            ),
            "expected_family_count": EXPECTED_FAMILY_COUNT,
            "observed_family_count": len(families),
        }
    interval = _paired_cluster_bootstrap(
        control,
        candidate,
        families,
        draws=BOOTSTRAP_DRAWS,
        seed=BOOTSTRAP_SEED,
    )
    helper_path_raw = inspect.getsourcefile(_base_task_family)
    helper_path = Path(helper_path_raw).resolve() if helper_path_raw else None
    return {
        "status": "reported",
        "role": "conservative_sensitivity_only",
        "cluster_definition": "sage_ts.evaluation.task_strata.base_task_family",
        "cluster_count": len(families),
        "scenario_weighted": True,
        "bootstrap": interval,
        "helper_source": {
            "path": str(helper_path) if helper_path else None,
            "sha256": (
                _file_sha256(helper_path)
                if helper_path is not None and helper_path.is_file()
                else None
            ),
        },
    }


def _integrity_failure_report(
    *,
    control_metadata: dict[str, Any],
    candidate_metadata: dict[str, Any],
    errors: Sequence[str],
    checks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "report_type": "h2_integrated_sage_pilot_analysis",
        "analysis_role": "one_replication_pilot_not_confirmatory",
        "status": "failed_integrity",
        "pilot_gate_outcome": "integrity_failure",
        "pilot_gate_label": INTEGRITY_FAILURE,
        "inputs": {"control": control_metadata, "candidate": candidate_metadata},
        "locked_design": {
            "tasks_per_arm": EXPECTED_SCENARIO_COUNT,
            "stem_clusters": EXPECTED_STEM_COUNT,
            "variants_per_stem": EXPECTED_VARIANTS_PER_STEM,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "minimum_relative_lift": RELATIVE_LIFT_THRESHOLD,
            "absolute_difference_ci_lower_must_exceed": 0.0,
        },
        "integrity": {
            "status": "fail",
            "errors": sorted(set(errors)),
            "checks": list(checks),
        },
        "control_mean": None,
        "integrated_sage_mean": None,
        "mean_difference": None,
        "absolute_lift": None,
        "relative_lift": None,
        "cluster_ci_95": [None, None],
        "stem_clusters": None,
        "tasks": None,
        "primary_bootstrap": None,
        "descriptive_canonical_similarity": None,
        "family_sensitivity": {
            "status": "omitted",
            "reason": "primary_integrity_failure",
        },
        "hashes": {},
    }
    report["hashes"]["analysis_payload_hash_scope"] = (
        "canonical JSON after removing hashes.analysis_payload_sha256"
    )
    report["hashes"]["analysis_payload_sha256"] = _canonical_sha256(report)
    return report


def analyze_h2_pilot(
    *,
    control_summary_path: Path,
    candidate_summary_path: Path,
    strict_run_root: Path,
    expect_reflection: str = "same-run-fresh",
) -> dict[str, Any]:
    """Load, validate, and analyze one complete H2 control/candidate pair."""

    control_metadata = _input_metadata(control_summary_path)
    candidate_metadata = _input_metadata(candidate_summary_path)
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    strict_receipt: dict[str, Any] | None = None
    try:
        strict_receipt = _strict_verification_receipt(
            run_root=strict_run_root,
            control_summary_path=control_summary_path,
            candidate_summary_path=candidate_summary_path,
            expect_reflection=expect_reflection,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        errors.append(
            f"strict_publication_verification_failed:{type(exc).__name__}:{exc}"
        )
    checks.append(
        {
            "label": "Strict publication verifier and exact input binding",
            "status": "pass" if strict_receipt is not None else "fail",
            "detail": (
                str(strict_receipt["run_root"])
                if strict_receipt is not None
                else errors[-1]
            ),
        }
    )
    control_payload, control_load_errors = _load_object(control_summary_path, "control")
    candidate_payload, candidate_load_errors = _load_object(
        candidate_summary_path, "candidate"
    )
    errors.extend(control_load_errors)
    errors.extend(candidate_load_errors)
    if control_payload is None or candidate_payload is None:
        checks.append(
            {
                "label": "Both result summaries load as JSON objects",
                "status": "fail",
                "detail": "; ".join(errors),
            }
        )
        return _integrity_failure_report(
            control_metadata=control_metadata,
            candidate_metadata=candidate_metadata,
            errors=errors,
            checks=checks,
        )

    control, control_errors = _validate_arm(control_payload, "control")
    candidate, candidate_errors = _validate_arm(candidate_payload, "candidate")
    errors.extend(control_errors)
    errors.extend(candidate_errors)
    checks.extend(
        [
            {
                "label": "Exactly 1,032 rows per arm",
                "status": (
                    "pass"
                    if len(control.names)
                    == len(candidate.names)
                    == EXPECTED_SCENARIO_COUNT
                    else "fail"
                ),
                "detail": (
                    f"control={len(control.names)}, candidate={len(candidate.names)}"
                ),
            },
            {
                "label": "Unique scenario names",
                "status": (
                    "pass"
                    if len(set(control.names)) == len(control.names)
                    and len(set(candidate.names)) == len(candidate.names)
                    else "fail"
                ),
                "detail": "duplicates are forbidden in either arm",
            },
            {
                "label": "Zero runtime exception or traceback rows",
                "status": (
                    "pass"
                    if not control.exception_rows and not candidate.exception_rows
                    else "fail"
                ),
                "detail": (
                    f"control={len(control.exception_rows)}, "
                    f"candidate={len(candidate.exception_rows)}"
                ),
            },
        ]
    )
    if control.names != candidate.names:
        errors.append("arm_scenario_order_mismatch")
    checks.append(
        {
            "label": "Identical scenario order across arms",
            "status": "pass" if control.names == candidate.names else "fail",
            "detail": "paired analysis requires position-wise identical names",
        }
    )
    finite_and_bounded = (
        len(control.outcomes) == EXPECTED_SCENARIO_COUNT
        and len(candidate.outcomes) == EXPECTED_SCENARIO_COUNT
        and bool(np.isfinite(control.outcomes).all())
        and bool(np.isfinite(candidate.outcomes).all())
        and bool(((0.0 <= control.outcomes) & (control.outcomes <= 1.0)).all())
        and bool(((0.0 <= candidate.outcomes) & (candidate.outcomes <= 1.0)).all())
    )
    checks.append(
        {
            "label": "Finite outcome_similarity values in [0,1]",
            "status": "pass" if finite_and_bounded else "fail",
            "detail": "all 2,064 outcome values are required",
        }
    )
    canonical_finite_and_bounded = (
        len(control.canonical_similarities) == EXPECTED_SCENARIO_COUNT
        and len(candidate.canonical_similarities) == EXPECTED_SCENARIO_COUNT
        and bool(np.isfinite(control.canonical_similarities).all())
        and bool(np.isfinite(candidate.canonical_similarities).all())
        and bool(
            (
                (0.0 <= control.canonical_similarities)
                & (control.canonical_similarities <= 1.0)
            ).all()
        )
        and bool(
            (
                (0.0 <= candidate.canonical_similarities)
                & (candidate.canonical_similarities <= 1.0)
            ).all()
        )
    )
    checks.append(
        {
            "label": "Finite canonical ToolSandbox similarity values in [0,1]",
            "status": "pass" if canonical_finite_and_bounded else "fail",
            "detail": "all 2,064 descriptive canonical values are required",
        }
    )

    stem_groups: dict[str, list[int]] = {}
    if len(control.names) == EXPECTED_SCENARIO_COUNT:
        stem_groups, stem_errors = _validate_stem_roster(control.names)
        errors.extend(stem_errors)
    else:
        errors.append("stem_roster_not_evaluable_due_to_row_count")
    stem_valid = (
        len(stem_groups) == EXPECTED_STEM_COUNT
        and all(
            len(indices) == EXPECTED_VARIANTS_PER_STEM
            for indices in stem_groups.values()
        )
        and not any(error.startswith("stem_") for error in errors)
    )
    checks.append(
        {
            "label": "Exact 129 stems × 8 robustness variants",
            "status": "pass" if stem_valid else "fail",
            "detail": f"observed_stems={len(stem_groups)}",
        }
    )
    if errors:
        return _integrity_failure_report(
            control_metadata=control_metadata,
            candidate_metadata=candidate_metadata,
            errors=errors,
            checks=checks,
        )

    control_mean = float(control.outcomes.mean())
    candidate_mean = float(candidate.outcomes.mean())
    difference = candidate_mean - control_mean
    if control_mean <= 0.0:
        errors.append("control_mean_not_positive_relative_lift_undefined")
        checks.append(
            {
                "label": "Positive control mean for relative lift",
                "status": "fail",
                "detail": f"control_mean={control_mean}",
            }
        )
        return _integrity_failure_report(
            control_metadata=control_metadata,
            candidate_metadata=candidate_metadata,
            errors=errors,
            checks=checks,
        )
    relative_lift = difference / control_mean
    canonical_control_mean = float(control.canonical_similarities.mean())
    canonical_candidate_mean = float(candidate.canonical_similarities.mean())
    primary_bootstrap = _paired_cluster_bootstrap(
        control.outcomes,
        candidate.outcomes,
        stem_groups,
        draws=BOOTSTRAP_DRAWS,
        seed=BOOTSTRAP_SEED,
    )
    ci = primary_bootstrap["absolute_difference_ci"]
    lift_gate = relative_lift >= RELATIVE_LIFT_THRESHOLD
    ci_gate = float(ci["lower"]) > 0.0
    cleared = lift_gate and ci_gate
    gate_label = PILOT_THRESHOLD_CLEARED if cleared else PILOT_THRESHOLD_NOT_CLEARED
    gate_criteria = [
        {
            "criterion": "relative_lift_at_least_10_percent",
            "passed": lift_gate,
            "observed": relative_lift,
            "threshold": RELATIVE_LIFT_THRESHOLD,
            "operator": ">=",
        },
        {
            "criterion": "stem_cluster_ci_lower_above_zero",
            "passed": ci_gate,
            "observed": float(ci["lower"]),
            "threshold": 0.0,
            "operator": ">",
        },
    ]
    family_sensitivity = _family_sensitivity(
        control.names, control.outcomes, candidate.outcomes
    )
    ordered_names_hash = _canonical_sha256(list(control.names))
    paired_outcomes_hash = _canonical_sha256(
        [
            {
                "name": name,
                "control_outcome_similarity": float(control.outcomes[index]),
                "candidate_outcome_similarity": float(candidate.outcomes[index]),
            }
            for index, name in enumerate(control.names)
        ]
    )
    control_metadata.update(
        {
            "row_count": len(control.names),
            "ordered_scenario_names_sha256": ordered_names_hash,
            "outcome_vector_sha256": _canonical_sha256(
                [float(value) for value in control.outcomes]
            ),
        }
    )
    candidate_metadata.update(
        {
            "row_count": len(candidate.names),
            "ordered_scenario_names_sha256": ordered_names_hash,
            "outcome_vector_sha256": _canonical_sha256(
                [float(value) for value in candidate.outcomes]
            ),
        }
    )
    report: dict[str, Any] = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "report_type": "h2_integrated_sage_pilot_analysis",
        "analysis_role": "one_replication_pilot_not_confirmatory",
        "status": "observed",
        "pilot_gate_outcome": "cleared" if cleared else "not_cleared",
        "pilot_gate_label": gate_label,
        "pilot_gate": {
            "passed": cleared,
            "label": gate_label,
            "criteria": gate_criteria,
        },
        "inputs": {"control": control_metadata, "candidate": candidate_metadata},
        "locked_design": {
            "tasks_per_arm": EXPECTED_SCENARIO_COUNT,
            "stem_clusters": EXPECTED_STEM_COUNT,
            "variants_per_stem": EXPECTED_VARIANTS_PER_STEM,
            "robustness_suffixes": list(ROBUSTNESS_SUFFIXES),
            "bootstrap_method": "paired_stem_cluster_percentile",
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "confidence_level": CONFIDENCE_LEVEL,
            "minimum_relative_lift": RELATIVE_LIFT_THRESHOLD,
            "absolute_difference_ci_lower_must_exceed": 0.0,
        },
        "integrity": {
            "status": "pass",
            "errors": [],
            "checks": checks,
            "strict_verification_receipt": strict_receipt,
        },
        # Dashboard-ready summary fields.
        "control_mean": control_mean,
        "integrated_sage_mean": candidate_mean,
        "mean_difference": difference,
        "absolute_lift": difference,
        "relative_lift": relative_lift,
        "relative_lift_percent": relative_lift * 100.0,
        "descriptive_canonical_similarity": {
            "role": "descriptive_not_primary",
            "control_mean": canonical_control_mean,
            "integrated_sage_mean": canonical_candidate_mean,
            "mean_difference": canonical_candidate_mean - canonical_control_mean,
        },
        "cluster_ci_95": [float(ci["lower"]), float(ci["upper"])],
        "stem_clusters": len(stem_groups),
        "tasks": len(control.names),
        # Full reproducibility fields.
        "primary_bootstrap": primary_bootstrap,
        "family_sensitivity": family_sensitivity,
        "hashes": {
            "ordered_scenario_names_sha256": ordered_names_hash,
            "paired_outcomes_sha256": paired_outcomes_hash,
        },
        "method_note": (
            "All 1,032 paired tasks are included. The 95% interval resamples "
            "129 original-scenario stems with all eight robustness variants "
            "kept together. This one-replication result is a pilot estimate."
        ),
    }
    report["hashes"]["analysis_payload_hash_scope"] = (
        "canonical JSON after removing hashes.analysis_payload_sha256"
    )
    report["hashes"]["analysis_payload_sha256"] = _canonical_sha256(report)
    return report


def write_h2_pilot_report(report: Mapping[str, Any], output_path: Path) -> None:
    """Atomically write a machine-readable H2 report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output_path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-summary", type=Path, required=True)
    parser.add_argument("--candidate-summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expect-reflection",
        choices=("same-run-fresh", "actor-visible-only"),
        default="same-run-fresh",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = analyze_h2_pilot(
        control_summary_path=args.control_summary,
        candidate_summary_path=args.candidate_summary,
        strict_run_root=args.run_root,
        expect_reflection=args.expect_reflection,
    )
    write_h2_pilot_report(report, args.output)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 2 if report["pilot_gate_label"] == INTEGRITY_FAILURE else 0


if __name__ == "__main__":
    raise SystemExit(main())
