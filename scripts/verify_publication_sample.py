#!/usr/bin/env python3
"""Apply predeclared no-regression gates to one integrity-verified online run."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

try:
    _run_verifier = importlib.import_module("scripts.verify_publication_run")
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    _run_verifier = importlib.import_module("verify_publication_run")
verify_run = _run_verifier.verify_run
outcome_evaluator_manifest = _run_verifier.outcome_evaluator_manifest

DEFAULT_THRESHOLDS = Path(
    "docs/sage_protocol/publication_validation_thresholds_v5.json"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
NON_OUTCOME_RELEASE_GATES = frozenset(
    {
        "candidate_canonical_minimum",
        "minimum_accepted_tool_count",
        "minimum_tool_reuse_event_count",
        "minimum_generated_tool_called_scenario_count",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_historical_reference(reference: dict[str, Any]) -> None:
    for path_field, hash_field in (
        ("summary_path", "summary_sha256"),
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


def _number(mapping: dict[str, Any], field: str, label: str) -> float:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} does not contain numeric {field!r}.")
    return float(value)


def _integer(mapping: dict[str, Any], field: str, label: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} does not contain integer {field!r}.")
    return value


def verify_sample(
    search_root: Path,
    *,
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    output_path: Path | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    """Verify integrity first, then evaluate one sample against frozen gates."""
    thresholds = _read_object(thresholds_path)
    benchmark = thresholds.get("benchmark")
    integrity = thresholds.get("required_integrity")
    no_regression = thresholds.get("required_no_regression")
    historical = thresholds.get("historical_reference")
    report_only = thresholds.get("report_only")
    if (
        not isinstance(benchmark, dict)
        or not isinstance(integrity, dict)
        or not isinstance(no_regression, dict)
        or not isinstance(historical, dict)
        or not isinstance(report_only, dict)
    ):
        raise ValueError("Validation thresholds are missing required sections.")
    if thresholds.get("schema_version") != 2:
        raise ValueError("Validation thresholds schema version is not 2.")
    if thresholds.get("performance_endpoint") != "outcome_task_completion_similarity":
        raise ValueError("Validation thresholds do not declare the outcome endpoint.")
    expected_outcome_evaluator = outcome_evaluator_manifest()
    if thresholds.get("outcome_evaluator") != expected_outcome_evaluator:
        raise ValueError(
            "Validation thresholds do not pin the current outcome evaluator."
        )
    invalid_release_gates = sorted(
        (NON_OUTCOME_RELEASE_GATES & set(no_regression))
        | {
            str(key)
            for key in no_regression
            if any(token in str(key).lower() for token in ("canonical", "reference"))
        }
    )
    if invalid_release_gates:
        raise ValueError(
            "Non-outcome values must not be publication release gates: "
            + ", ".join(invalid_release_gates)
        )
    _verify_historical_reference(historical)

    expected_tasks = _integer(benchmark, "task_count", "benchmark")
    integrity_result = verify_run(
        search_root,
        expected_tasks=expected_tasks,
        expect_reflection="same-run-fresh",
        expected_fixture_sha256=str(integrity["validated_external_fixture_sha256"]),
        expected_benchmark_sha256=str(benchmark["manifest_sha256"]),
        expected_scenario_order_sha256=str(benchmark["ordered_task_name_sha256"]),
    )
    if integrity_result.get("outcome_evaluator") != expected_outcome_evaluator:
        raise ValueError(
            "Integrity verification did not use the threshold-pinned outcome evaluator."
        )
    run_root = Path(str(integrity_result["run_root"]))
    comparison = _read_object(run_root / "paired_comparison.json")
    if comparison.get("outcome_evaluator") != expected_outcome_evaluator:
        raise ValueError(
            "Paired comparison did not use the threshold-pinned outcome evaluator."
        )
    control = comparison.get("control")
    candidate = comparison.get("candidate")
    if not isinstance(control, dict) or not isinstance(candidate, dict):
        raise ValueError("Paired comparison is missing control/candidate summaries.")

    expected_outcome_tasks = _integer(
        benchmark,
        "outcome_scored_task_count",
        "benchmark",
    )
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

    for arm_name, arm in (("control", control), ("candidate", candidate)):
        gate(
            f"{arm_name}_run_complete",
            arm.get("run_status") == "complete",
            arm.get("run_status"),
            "complete",
        )
        gate(
            f"{arm_name}_scenario_count",
            _integer(arm, "scenario_count", arm_name) == expected_tasks,
            arm.get("scenario_count"),
            expected_tasks,
        )
        gate(
            f"{arm_name}_planned_scenario_count",
            _integer(arm, "planned_scenario_count", arm_name) == expected_tasks,
            arm.get("planned_scenario_count"),
            expected_tasks,
        )
        gate(
            f"{arm_name}_outcome_scored_count",
            _integer(arm, "outcome_score_available_count", arm_name)
            == expected_outcome_tasks,
            arm.get("outcome_score_available_count"),
            expected_outcome_tasks,
        )
        gate(
            f"{arm_name}_runtime_exceptions",
            _integer(arm, "exception_count", arm_name) == 0,
            arm.get("exception_count"),
            0,
        )
        gate(
            f"{arm_name}_repository_whole_response_replay_calls",
            _integer(arm, "llm_cached_call_count", arm_name) == 0,
            arm.get("llm_cached_call_count"),
            0,
        )

    control_outcome = _number(
        control,
        "mean_outcome_similarity",
        "control",
    )
    candidate_outcome = _number(
        candidate,
        "mean_outcome_similarity",
        "candidate",
    )
    if control_outcome <= 0:
        raise ValueError("Relative outcome lift is undefined for this control outcome.")
    outcome_lift_percent = (
        (candidate_outcome - control_outcome) / control_outcome * 100.0
    )

    outcome_floor = _number(
        no_regression,
        "candidate_outcome_minimum",
        "required_no_regression",
    )
    lift_floor = _number(
        no_regression,
        "minimum_relative_outcome_lift_percent_over_same_run_control",
        "required_no_regression",
    )
    gate(
        "candidate_outcome_no_regression",
        candidate_outcome >= outcome_floor,
        candidate_outcome,
        {"minimum": outcome_floor},
    )
    gate(
        "same_run_relative_outcome_lift",
        outcome_lift_percent >= lift_floor,
        outcome_lift_percent,
        {"minimum_percent": lift_floor},
    )
    historical_outcome_mean = _number(
        report_only,
        "compare_candidate_outcome_to_historical_mean",
        "report_only",
    )
    result = {
        "schema_version": 2,
        "status": "pass" if not failures else "fail",
        "purpose": thresholds.get("purpose"),
        "performance_endpoint": thresholds.get("performance_endpoint"),
        "outcome_evaluator": expected_outcome_evaluator,
        "run_root": str(run_root),
        "thresholds_path": str(thresholds_path),
        "thresholds_sha256": _sha256(thresholds_path),
        "integrity_verification": integrity_result,
        "metrics": {
            "control_outcome": control_outcome,
            "candidate_outcome": candidate_outcome,
            "same_run_relative_outcome_lift_percent": outcome_lift_percent,
            "candidate_outcome_minus_historical_mean": (
                candidate_outcome - historical_outcome_mean
            ),
        },
        "mechanism_diagnostics": {
            "release_gate": False,
            "accepted_tool_count": candidate.get("accepted_tool_count"),
            "tool_reuse_event_count": candidate.get("reuse_count"),
            "generated_tool_called_scenario_count": candidate.get(
                "generated_tool_called_scenarios"
            ),
        },
        "historical_reference": historical,
        "gates": gates,
        "failed_gates": failures,
        "interpretation": (
            "Engineering validation only; final paper inference remains pending "
            "the predeclared 10-pair strict fresh-control campaign."
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
