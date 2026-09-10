#!/usr/bin/env python3
"""Apply predeclared, explicitly scoped outcome gates to one verified run."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any

from sage_ts.evaluation.online_feedback_score import (
    _answer_templates,
    _has_state_target,
    _is_route_only,
)
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.tool_discovery import ToolBackend

try:
    _run_verifier = importlib.import_module("scripts.verify_publication_run")
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    _run_verifier = importlib.import_module("verify_publication_run")
verify_run = _run_verifier.verify_run

DEFAULT_THRESHOLDS = Path(
    "docs/sage_protocol/publication_validation_thresholds_v3.json"
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ordered_name_sha256(names: list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


def _verify_historical_reference(reference: dict[str, Any]) -> None:
    for path_field, hash_field in (
        ("campaign_manifest", "campaign_manifest_sha256"),
        ("evidence_data", "evidence_data_sha256"),
    ):
        raw_path = reference.get(path_field)
        expected = reference.get(hash_field)
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"Historical reference is missing {path_field!r}.")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"Historical reference is missing {hash_field!r}.")
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.is_file():
            raise ValueError(f"Historical reference input is missing: {path}")
        if _sha256(path) != expected:
            raise ValueError(f"Historical reference input changed: {path}")


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _object(mapping: dict[str, Any], field: str, label: str) -> dict[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{label} is missing object {field!r}.")
    return value


def _number(mapping: dict[str, Any], field: str, label: str) -> float:
    value = mapping.get(field)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"{label} does not contain finite numeric {field!r}.")
    return float(value)


def _unit_interval_number(mapping: dict[str, Any], field: str, label: str) -> float:
    value = _number(mapping, field, label)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label}.{field} is outside the closed interval [0, 1].")
    return value


def _optional_unit_interval_number(
    mapping: dict[str, Any], field: str, label: str
) -> float | None:
    if mapping.get(field) is None:
        return None
    return _unit_interval_number(mapping, field, label)


def _integer(mapping: dict[str, Any], field: str, label: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} does not contain integer {field!r}.")
    return value


def _string(mapping: dict[str, Any], field: str, label: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} does not contain non-empty string {field!r}.")
    return value


def _resolve_declared_run_dir(
    run_root: Path,
    raw: Any,
    label: str,
    required_parent: Path,
) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Run metadata does not declare {label}.")
    declared = Path(raw)
    candidates = (
        [declared]
        if declared.is_absolute()
        else [
            REPO_ROOT / declared,
            Path.cwd() / declared,
            run_root / declared,
        ]
    )
    existing = sorted(
        {candidate.resolve() for candidate in candidates if candidate.exists()}
    )
    if len(existing) != 1:
        raise ValueError(
            f"Declared {label} is {'ambiguous' if existing else 'missing'}: {raw!r}."
        )
    resolved = existing[0]
    if not resolved.is_relative_to(required_parent.resolve()):
        raise ValueError(f"Declared {label} escapes its same-run arm directory.")
    if not resolved.is_dir():
        raise ValueError(f"Declared {label} is not a directory: {resolved}.")
    return resolved


def _scenario_rows(
    run_dir: Path,
    arm_name: str,
) -> tuple[list[dict[str, Any]], Path]:
    summary_path = run_dir / "result_summary.json"
    summary = _read_object(summary_path)
    raw_rows = summary.get("per_scenario_results")
    if not isinstance(raw_rows, list):
        raise ValueError(f"{arm_name} result summary has no scenario-result list.")
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            raise ValueError(f"{arm_name} scenario result {index} is not an object.")
        _string(raw_row, "name", f"{arm_name} scenario result {index}")
        rows.append(raw_row)
    return rows, summary_path


def _expected_paper_subset_names(
    benchmark: dict[str, Any],
    paper: dict[str, Any],
) -> list[str]:
    """Derive evaluator applicability from frozen scenarios, never result rows."""
    raw_source_path = _string(paper, "evaluator_source_path", "paper endpoint")
    source_path = Path(raw_source_path)
    if not source_path.is_absolute():
        source_path = REPO_ROOT / source_path
    if not source_path.is_file() or _sha256(source_path) != _string(
        paper, "evaluator_source_sha256", "paper endpoint"
    ):
        raise ValueError("Paper-comparable evaluator source bytes changed.")
    raw_path = _string(benchmark, "path", "benchmark")
    path = Path(raw_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file() or _sha256(path) != _string(
        benchmark, "manifest_sha256", "benchmark"
    ):
        raise ValueError("Benchmark bytes for paper-subset derivation changed.")
    payload = _read_object(path)
    splits = payload.get("splits")
    full = splits.get("full_benchmark") if isinstance(splits, dict) else None
    if not isinstance(full, list):
        raise ValueError("Benchmark has no full_benchmark list.")
    names: list[str] = []
    for index, item in enumerate(full):
        if not isinstance(item, dict):
            raise ValueError(f"Benchmark task {index} is not an object.")
        names.append(_string(item, "name", f"benchmark task {index}"))
    if len(names) != len(set(names)):
        raise ValueError("Benchmark task names are not unique.")
    if len(names) != _integer(benchmark, "task_count", "benchmark"):
        raise ValueError("Benchmark task count changed.")
    if _ordered_name_sha256(names) != _string(
        benchmark, "ordered_task_name_sha256", "benchmark"
    ):
        raise ValueError("Benchmark ordered task names changed.")

    scenarios = resolve_scenarios(
        desired_scenario_names=names,
        preferred_tool_backend=ToolBackend.DEFAULT,
    )
    selected: list[str] = []
    for name in names:
        scenario = scenarios[name]
        milestones = scenario.evaluation.milestone_matcher.milestones
        if any(
            not _is_route_only(milestone)
            and bool(_answer_templates(milestone) or _has_state_target(milestone))
            for milestone in milestones
        ):
            selected.append(name)
    if len(selected) != _integer(paper, "task_count", "paper endpoint"):
        raise ValueError("Statically derived paper-comparable task count changed.")
    if _ordered_name_sha256(selected) != _string(
        paper, "ordered_task_name_sha256", "paper endpoint"
    ):
        raise ValueError("Statically derived paper-comparable task order changed.")
    return selected


def _endpoint_declaration(
    thresholds: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    endpoints = _object(thresholds, "performance_endpoints", "validation thresholds")
    return _object(endpoints, name, "performance_endpoints")


def _observed_identity(rows: list[dict[str, Any]], field: str) -> list[Any]:
    values = {json.dumps(row.get(field), sort_keys=True) for row in rows}
    return [json.loads(value) for value in sorted(values)]


def verify_sample(
    search_root: Path,
    *,
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    output_path: Path | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    """Verify integrity, then gate the audited and paper-comparable endpoints."""
    thresholds = _read_object(thresholds_path)
    benchmark = _object(thresholds, "benchmark", "validation thresholds")
    integrity = _object(thresholds, "required_integrity", "validation thresholds")
    no_regression = _object(
        thresholds, "required_no_regression", "validation thresholds"
    )
    historical = _object(thresholds, "historical_reference", "validation thresholds")
    report_only = _object(thresholds, "report_only", "validation thresholds")
    if thresholds.get("schema_version") != 3:
        raise ValueError("Validation thresholds schema version is not 3.")
    if thresholds.get("performance_endpoint_policy") != "dual_scoped_outcome_endpoints":
        raise ValueError("Validation thresholds do not declare dual scoped endpoints.")
    if (
        thresholds.get("canonical_metric_policy")
        != "descriptive_only_never_a_release_gate"
    ):
        raise ValueError("Validation thresholds do not make canonical report-only.")
    if any("canonical" in field for field in no_regression):
        raise ValueError("Canonical/reference similarity must not be a release gate.")
    _verify_historical_reference(historical)

    expected_tasks = _integer(benchmark, "task_count", "benchmark")
    audited = _endpoint_declaration(thresholds, "audited_current_all_tasks")
    paper = _endpoint_declaration(thresholds, "paper_comparable_historical_subset")
    if _string(audited, "metric_field", "audited endpoint") != "outcome_similarity":
        raise ValueError("Audited endpoint metric field is not outcome_similarity.")
    if _string(audited, "task_scope", "audited endpoint") != "all_benchmark_tasks":
        raise ValueError("Audited endpoint scope is not all benchmark tasks.")
    if _integer(audited, "task_count", "audited endpoint") != expected_tasks:
        raise ValueError("Audited endpoint task count disagrees with the benchmark.")
    if _string(audited, "ordered_task_name_sha256", "audited endpoint") != _string(
        benchmark, "ordered_task_name_sha256", "benchmark"
    ):
        raise ValueError("Audited endpoint task order disagrees with the benchmark.")
    if (
        _string(paper, "metric_field", "paper-comparable endpoint")
        != "online_feedback_outcome_similarity"
    ):
        raise ValueError(
            "Paper-comparable endpoint is not online_feedback_outcome_similarity."
        )
    if (
        _string(paper, "task_scope", "paper-comparable endpoint")
        != "non_null_metric_rows_in_full_benchmark_order"
    ):
        raise ValueError("Paper-comparable endpoint subset rule is not exact.")
    if (
        _string(paper, "subset_derivation", "paper-comparable endpoint")
        != "sage_paper_outcome_contracts_v1_static_applicability"
    ):
        raise ValueError("Paper-comparable endpoint derivation is not exact.")

    integrity_result = verify_run(
        search_root,
        expected_tasks=expected_tasks,
        expect_reflection="same-run-fresh",
        expected_fixture_sha256=str(integrity["validated_external_fixture_sha256"]),
        expected_benchmark_sha256=str(benchmark["manifest_sha256"]),
        expected_scenario_order_sha256=str(benchmark["ordered_task_name_sha256"]),
    )
    run_root = Path(str(integrity_result["run_root"]))
    comparison = _read_object(run_root / "paired_comparison.json")
    protocol = _read_object(run_root / "protocol_manifest.json")
    control = _object(comparison, "control", "paired comparison")
    candidate = _object(comparison, "candidate", "paired comparison")
    control_dir = _resolve_declared_run_dir(
        run_root,
        protocol.get("control_dir"),
        "protocol control_dir",
        run_root / "control",
    )
    candidate_dir = _resolve_declared_run_dir(
        run_root,
        protocol.get("candidate_dir"),
        "protocol candidate_dir",
        run_root / "candidate",
    )
    comparison_control_dir = _resolve_declared_run_dir(
        run_root,
        control.get("run_dir"),
        "paired comparison control.run_dir",
        run_root / "control",
    )
    comparison_candidate_dir = _resolve_declared_run_dir(
        run_root,
        candidate.get("run_dir"),
        "paired comparison candidate.run_dir",
        run_root / "candidate",
    )
    if (
        control_dir != comparison_control_dir
        or candidate_dir != comparison_candidate_dir
    ):
        raise ValueError(
            "Paired comparison arm directories do not match the verified protocol."
        )
    control_rows, control_summary_path = _scenario_rows(control_dir, "control")
    candidate_rows, candidate_summary_path = _scenario_rows(candidate_dir, "candidate")

    failures: list[str] = []
    gates: dict[str, dict[str, Any]] = {}

    def gate(name: str, passed: bool, observed: Any, required: Any) -> None:
        gates[name] = {
            "passed": passed,
            "observed": observed,
            "required": required,
        }
        if not passed:
            failures.append(name)

    for arm_name, arm, rows in (
        ("control", control, control_rows),
        ("candidate", candidate, candidate_rows),
    ):
        gate(
            f"{arm_name}_run_complete",
            arm.get("run_status") == "complete",
            arm.get("run_status"),
            "complete",
        )
        for field, gate_suffix in (
            ("scenario_count", "paired_comparison_scenario_count"),
            ("planned_scenario_count", "paired_comparison_planned_scenario_count"),
            ("outcome_score_available_count", "audited_current_scored_task_count"),
        ):
            observed = _integer(arm, field, arm_name)
            gate(
                f"{arm_name}_{gate_suffix}",
                observed == expected_tasks,
                observed,
                expected_tasks,
            )
        gate(
            f"{arm_name}_audited_current_result_row_count",
            len(rows) == expected_tasks,
            len(rows),
            expected_tasks,
        )
        gate(
            f"{arm_name}_runtime_exception_count",
            _integer(arm, "exception_count", arm_name) == 0,
            arm.get("exception_count"),
            0,
        )
        gate(
            f"{arm_name}_repository_whole_response_replay_call_count",
            _integer(arm, "llm_cached_call_count", arm_name) == 0,
            arm.get("llm_cached_call_count"),
            0,
        )

    expected_all_order_hash = _string(
        audited, "ordered_task_name_sha256", "audited endpoint"
    )
    all_names_by_arm: dict[str, list[str]] = {}
    audited_values_by_arm: dict[str, list[float]] = {}
    paper_names_by_arm: dict[str, list[str]] = {}
    paper_values_by_arm: dict[str, list[float]] = {}
    audited_version = _string(audited, "evaluator_version", "audited endpoint")
    audited_contract_hash = _string(
        audited, "evaluator_contract_sha256", "audited endpoint"
    )
    audited_source_hash = _string(
        audited, "evaluator_source_sha256", "audited endpoint"
    )
    paper_version = _string(paper, "evaluator_version", "paper endpoint")
    expected_paper_count = _integer(paper, "task_count", "paper endpoint")
    expected_paper_order_hash = _string(
        paper, "ordered_task_name_sha256", "paper endpoint"
    )
    expected_paper_names = _expected_paper_subset_names(benchmark, paper)

    for arm_name, rows in (("control", control_rows), ("candidate", candidate_rows)):
        names = [_string(row, "name", f"{arm_name} scenario row") for row in rows]
        all_names_by_arm[arm_name] = names
        gate(
            f"{arm_name}_audited_current_unique_task_names",
            len(set(names)) == len(names),
            len(set(names)),
            len(names),
        )
        observed_all_order_hash = _ordered_name_sha256(names)
        gate(
            f"{arm_name}_audited_current_ordered_task_name_sha256",
            observed_all_order_hash == expected_all_order_hash,
            observed_all_order_hash,
            expected_all_order_hash,
        )

        audited_values = [
            _unit_interval_number(row, "outcome_similarity", f"{arm_name} row")
            for row in rows
        ]
        audited_values_by_arm[arm_name] = audited_values
        for field, expected_identity, suffix in (
            ("outcome_evaluator_version", audited_version, "evaluator_version"),
            (
                "outcome_evaluator_contract_sha256",
                audited_contract_hash,
                "evaluator_contract_sha256",
            ),
            (
                "outcome_evaluator_source_sha256",
                audited_source_hash,
                "evaluator_source_sha256",
            ),
        ):
            observed_identity = _observed_identity(rows, field)
            gate(
                f"{arm_name}_audited_current_{suffix}",
                observed_identity == [expected_identity],
                observed_identity,
                [expected_identity],
            )

        paper_rows = [
            row
            for row in rows
            if row.get("online_feedback_outcome_similarity") is not None
        ]
        paper_names = [
            _string(row, "name", f"{arm_name} paper-comparable row")
            for row in paper_rows
        ]
        paper_names_by_arm[arm_name] = paper_names
        paper_values_by_arm[arm_name] = [
            _unit_interval_number(
                row,
                "online_feedback_outcome_similarity",
                f"{arm_name} paper-comparable row",
            )
            for row in paper_rows
        ]
        gate(
            f"{arm_name}_paper_comparable_scored_task_count",
            len(paper_rows) == expected_paper_count,
            len(paper_rows),
            expected_paper_count,
        )
        gate(
            f"{arm_name}_paper_comparable_unique_task_names",
            len(set(paper_names)) == len(paper_names),
            len(set(paper_names)),
            len(paper_names),
        )
        observed_paper_order_hash = _ordered_name_sha256(paper_names)
        gate(
            f"{arm_name}_paper_comparable_ordered_task_name_sha256",
            observed_paper_order_hash == expected_paper_order_hash
            and paper_names == expected_paper_names,
            observed_paper_order_hash,
            expected_paper_order_hash,
        )
        observed_paper_versions = _observed_identity(
            paper_rows, "online_feedback_evaluator_version"
        )
        gate(
            f"{arm_name}_paper_comparable_evaluator_version",
            observed_paper_versions == [paper_version],
            observed_paper_versions,
            [paper_version],
        )

    gate(
        "audited_current_control_candidate_exact_task_order",
        all_names_by_arm["control"] == all_names_by_arm["candidate"],
        _ordered_name_sha256(all_names_by_arm["candidate"]),
        _ordered_name_sha256(all_names_by_arm["control"]),
    )
    gate(
        "paper_comparable_control_candidate_exact_subset_and_order",
        paper_names_by_arm["control"] == paper_names_by_arm["candidate"],
        _ordered_name_sha256(paper_names_by_arm["candidate"]),
        _ordered_name_sha256(paper_names_by_arm["control"]),
    )

    audited_control_mean = sum(audited_values_by_arm["control"]) / len(
        audited_values_by_arm["control"]
    )
    audited_candidate_mean = sum(audited_values_by_arm["candidate"]) / len(
        audited_values_by_arm["candidate"]
    )
    if audited_control_mean <= 0:
        raise ValueError("Audited relative outcome lift is undefined for zero control.")
    audited_lift_percent = (
        (audited_candidate_mean - audited_control_mean) / audited_control_mean * 100.0
    )
    paper_control_mean = sum(paper_values_by_arm["control"]) / len(
        paper_values_by_arm["control"]
    )
    paper_candidate_mean = sum(paper_values_by_arm["candidate"]) / len(
        paper_values_by_arm["candidate"]
    )

    for arm_name, arm, observed_mean in (
        ("control", control, audited_control_mean),
        ("candidate", candidate, audited_candidate_mean),
    ):
        paired_mean = _unit_interval_number(
            arm, "mean_outcome_similarity", f"paired comparison {arm_name}"
        )
        gate(
            f"{arm_name}_audited_current_mean_matches_paired_comparison",
            math.isclose(observed_mean, paired_mean, rel_tol=0.0, abs_tol=1e-12),
            observed_mean,
            paired_mean,
        )

    paper_floor = _unit_interval_number(
        no_regression,
        "paper_comparable_candidate_outcome_minimum",
        "required_no_regression",
    )
    audited_lift_floor = _number(
        no_regression,
        "audited_current_minimum_relative_outcome_lift_percent_over_same_run_control",
        "required_no_regression",
    )
    gate(
        "paper_comparable_candidate_outcome_historical_floor",
        paper_candidate_mean >= paper_floor,
        paper_candidate_mean,
        {"minimum": paper_floor},
    )
    gate(
        "audited_current_same_run_relative_outcome_lift",
        audited_lift_percent >= audited_lift_floor,
        audited_lift_percent,
        {"minimum_percent": audited_lift_floor},
    )
    for field, threshold_field in (
        ("accepted_tool_count", "minimum_accepted_tool_count"),
        ("reuse_count", "minimum_tool_reuse_event_count"),
        (
            "generated_tool_called_scenarios",
            "minimum_generated_tool_called_scenario_count",
        ),
    ):
        minimum = _integer(no_regression, threshold_field, "required_no_regression")
        observed = _integer(candidate, field, "candidate")
        gate(field, observed >= minimum, observed, {"minimum": minimum})

    historical_paper_mean = _unit_interval_number(
        report_only,
        "paper_comparable_candidate_outcome_historical_mean",
        "report_only",
    )
    result = {
        "schema_version": 3,
        "status": "pass" if not failures else "fail",
        "purpose": thresholds.get("purpose"),
        "performance_endpoint_policy": thresholds.get("performance_endpoint_policy"),
        "canonical_metric_policy": thresholds.get("canonical_metric_policy"),
        "run_root": str(run_root),
        "result_summaries": {
            "control": str(control_summary_path),
            "candidate": str(candidate_summary_path),
        },
        "thresholds_path": str(thresholds_path),
        "thresholds_sha256": _sha256(thresholds_path),
        "integrity_verification": integrity_result,
        "metrics": {
            "audited_current_all_tasks": {
                "metric_field": "outcome_similarity",
                "evaluator_version": audited_version,
                "task_count": expected_tasks,
                "control_mean": audited_control_mean,
                "candidate_mean": audited_candidate_mean,
                "candidate_minus_control": (
                    audited_candidate_mean - audited_control_mean
                ),
                "same_run_relative_lift_percent": audited_lift_percent,
            },
            "paper_comparable_historical_subset": {
                "metric_field": "online_feedback_outcome_similarity",
                "evaluator_version": paper_version,
                "task_count": expected_paper_count,
                "ordered_task_name_sha256": expected_paper_order_hash,
                "control_mean": paper_control_mean,
                "candidate_mean": paper_candidate_mean,
                "candidate_minus_control": paper_candidate_mean - paper_control_mean,
                "candidate_minus_historical_mean": (
                    paper_candidate_mean - historical_paper_mean
                ),
            },
            "report_only_canonical": {
                "control_mean": _optional_unit_interval_number(
                    control, "mean_similarity", "control"
                ),
                "candidate_mean": _optional_unit_interval_number(
                    candidate, "mean_similarity", "candidate"
                ),
            },
        },
        "historical_reference": historical,
        "gates": gates,
        "failed_gates": failures,
        "interpretation": (
            "Engineering validation only; final paper inference remains pending "
            "the predeclared 10-pair strict fresh-control campaign. Audited v9 "
            "all-task outcomes define current same-run lift; the exact 800-task "
            "paper evaluator subset alone is compared with historical outcomes."
        ),
    }
    destination = output_path or (run_root / "publication_validation_report.json")
    if write_report:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["report_path"] = str(destination)
    if failures:
        raise ValueError(
            "Publication sample failed predeclared gates: " + ", ".join(failures)
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=DEFAULT_THRESHOLDS,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = verify_sample(
            args.search_root,
            thresholds_path=args.thresholds,
            output_path=args.output,
        )
    except ValueError as exc:
        raise SystemExit(f"publication_sample_verification=failed\n{exc}") from exc
    print("publication_sample_verification=pass")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
