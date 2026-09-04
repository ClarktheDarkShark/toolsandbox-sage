#!/usr/bin/env python3
"""Re-score preserved historical trajectories with the current outcome evaluator.

This utility is deliberately read-only with respect to its inputs.  It evaluates
the frozen original-v140 trajectory set and the ten historical online SAGE
candidate sets, then writes a new, content-addressed report.  It does not replay
the historical experiment or make any claim about the feedback provenance that
produced those trajectories.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sage_ts.evaluation.outcome_score import (
    compute_outcome_score,
    outcome_evaluator_manifest,
)
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.tool_discovery import ToolBackend

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN_MANIFEST = Path(
    "artifacts/publication_cleanup_20260901/analysis/campaign_manifest.json"
)
DEFAULT_BASELINE_RECORDS = Path(
    "artifacts/publication_cleanup_20260901/baseline/"
    "original_v140_reference_records.jsonl"
)
DEFAULT_BASELINE_METADATA = Path(
    "artifacts/publication_cleanup_20260901/baseline/"
    "original_v140_reference_metadata.json"
)
EXPECTED_TASK_COUNT = 1032
EXPECTED_CANDIDATE_RUNS = 10
REPORT_SCHEMA_VERSION = 3
CONTENT_ADDRESS_ALGORITHM = "sha256(canonical-json(payload))"
HISTORICAL_TIMEZONE_ANCHOR_TOOL = "datetime_info_to_timestamp"
HISTORICAL_TIMEZONE_ARGUMENT_FIELDS = (
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
)
HISTORICAL_TIMEZONE_CANDIDATES = (
    "America/New_York",
    "America/Los_Angeles",
)
PROVENANCE_CAVEAT = (
    "This report re-scores preserved terminal trajectories only. It does not "
    "replay or validate the historical online feedback, baseline-cache, "
    "tool-birth, routing, or lifecycle provenance and cannot repair confounding "
    "in the superseded campaign. Historical manifests omitted the process "
    "timezone, so each arm's scenario-resolution timezone is inferred and "
    "fail-closed from every preserved complete, valid civil-time conversion "
    "trace in that arm. Evidence counts are raw trace occurrences, not a "
    "deduplicated anchor subset; the baseline and every candidate replication "
    "are inferred independently."
)


class HistoricalOutcomeRescoreError(RuntimeError):
    """Raised when a historical-rescoring invariant is not satisfied."""


ScenarioResolver = Callable[[Sequence[str]], Mapping[str, Any]]
ContextDecoder = Callable[[dict[str, Any]], Any]
OutcomeScorer = Callable[..., dict[str, Any]]
EvaluatorIdentityProvider = Callable[[], dict[str, Any]]


def _canonical_json_bytes(payload: Any, *, pretty: bool = False) -> bytes:
    options: dict[str, Any] = {
        "sort_keys": True,
        "ensure_ascii": False,
        "allow_nan": False,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return (json.dumps(payload, **options) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _resolve_path(repo_root: Path, raw_path: str | Path) -> Path:
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise HistoricalOutcomeRescoreError(
            f"Cannot read {label} at {path}: {exc}"
        ) from exc


def _file_record(
    repo_root: Path, path: Path, label: str
) -> tuple[bytes, dict[str, Any]]:
    raw = _read_bytes(path, label)
    return raw, {
        "path": _display_path(repo_root, path),
        "sha256": _sha256_bytes(raw),
        "size": len(raw),
    }


def _json_object_from_bytes(raw: bytes, path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalOutcomeRescoreError(
            f"Invalid {label} JSON object at {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise HistoricalOutcomeRescoreError(
            f"Expected {label} to be a JSON object: {path}"
        )
    return value


def _read_json_object(
    repo_root: Path,
    path: Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, record = _file_record(repo_root, path, label)
    return _json_object_from_bytes(raw, path, label), record


def _read_jsonl_objects(
    repo_root: Path,
    path: Path,
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw, record = _file_record(repo_root, path, label)
    rows: list[dict[str, Any]] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HistoricalOutcomeRescoreError(
            f"Invalid UTF-8 in {label} at {path}: {exc}"
        ) from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HistoricalOutcomeRescoreError(
                f"Invalid JSON in {label} at {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise HistoricalOutcomeRescoreError(
                f"Expected an object in {label} at {path}:{line_number}"
            )
        rows.append(value)
    return rows, record


def _string(mapping: Mapping[str, Any], field: str, label: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise HistoricalOutcomeRescoreError(
            f"{label} is missing non-empty string {field!r}"
        )
    return value


def _integer(mapping: Mapping[str, Any], field: str, label: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoricalOutcomeRescoreError(f"{label} is missing integer {field!r}")
    return value


def _ordered_task_names(benchmark: Mapping[str, Any]) -> list[str]:
    splits = benchmark.get("splits")
    if not isinstance(splits, dict):
        raise HistoricalOutcomeRescoreError("Benchmark is missing object 'splits'")
    rows = splits.get("full_benchmark")
    if not isinstance(rows, list):
        raise HistoricalOutcomeRescoreError(
            "Benchmark is missing list 'splits.full_benchmark'"
        )
    names: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise HistoricalOutcomeRescoreError(
                f"Benchmark task {index} is not an object"
            )
        names.append(_string(row, "name", f"benchmark task {index}"))
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        raise HistoricalOutcomeRescoreError(
            f"Benchmark contains duplicate task names: {duplicates[:5]}"
        )
    return names


def _names_sha256(names: Sequence[str]) -> str:
    return _sha256_bytes(("\n".join(names) + "\n").encode("utf-8"))


def _coverage(
    expected_names: Sequence[str],
    observed_names: Sequence[str],
    *,
    label: str,
) -> dict[str, Any]:
    counts = Counter(observed_names)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    expected = set(expected_names)
    observed = set(observed_names)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if (
        duplicates
        or missing
        or unexpected
        or len(observed_names) != len(expected_names)
    ):
        raise HistoricalOutcomeRescoreError(
            f"{label} does not exactly cover the benchmark: "
            f"observed={len(observed_names)}, missing={missing[:5]}, "
            f"unexpected={unexpected[:5]}, duplicates={duplicates[:5]}"
        )
    return {
        "expected_task_count": len(expected_names),
        "observed_task_count": len(observed_names),
        "unique_task_count": len(observed),
        "complete": True,
        "missing_tasks": [],
        "unexpected_tasks": [],
        "duplicate_tasks": [],
        "observed_order_sha256": _names_sha256(observed_names),
        "matches_benchmark_order": list(observed_names) == list(expected_names),
    }


def _validate_evaluator_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    version = _string(identity, "version", "outcome evaluator identity")
    contract_sha256 = _string(identity, "contract_sha256", "outcome evaluator identity")
    source_sha256 = _string(identity, "source_sha256", "outcome evaluator identity")
    for field, value in (
        ("contract_sha256", contract_sha256),
        ("source_sha256", source_sha256),
    ):
        if len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise HistoricalOutcomeRescoreError(
                f"Outcome evaluator {field} is not a lowercase SHA-256"
            )
    normalized: dict[str, Any] = {
        "version": version,
        "contract_sha256": contract_sha256,
        "source_sha256": source_sha256,
    }
    for field in (
        "insufficient_information_scenario_count",
        "scalar_scenario_count",
    ):
        value = identity.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise HistoricalOutcomeRescoreError(
                f"Outcome evaluator {field} is not an integer"
            )
        normalized[field] = value
    return normalized


def _assert_recorded_sha256(
    mapping: Mapping[str, Any],
    field: str,
    observed: str,
    *,
    label: str,
) -> None:
    expected = _string(mapping, field, label)
    if expected != observed:
        raise HistoricalOutcomeRescoreError(
            f"{label} {field} mismatch: expected {expected}, observed {observed}"
        )


@contextmanager
def _scenario_clock(timestamp: str, timezone_name: str) -> Iterator[None]:
    previous_timestamp = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")
    previous_timezone = os.environ.get("TZ")
    os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = timestamp
    os.environ["TZ"] = timezone_name
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        yield
    finally:
        if previous_timestamp is None:
            os.environ.pop("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", None)
        else:
            os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = previous_timestamp
        if previous_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_timezone
        if hasattr(time, "tzset"):
            time.tzset()


def _default_scenario_resolver(names: Sequence[str]) -> Mapping[str, Any]:
    return resolve_scenarios(
        desired_scenario_names=list(names),
        preferred_tool_backend=ToolBackend.DEFAULT,
    )


def _serialized_tool_traces(
    context_payload: Mapping[str, Any],
    *,
    source_label: str,
) -> Iterator[dict[str, Any]]:
    databases = context_payload.get("_dbs")
    if not isinstance(databases, dict):
        return
    sandbox_rows = databases.get("SANDBOX")
    if not isinstance(sandbox_rows, list):
        return
    for row in sandbox_rows:
        if not isinstance(row, dict):
            continue
        raw_traces = row.get("tool_trace")
        if not raw_traces:
            continue
        pending = raw_traces if isinstance(raw_traces, list) else [raw_traces]
        for raw_trace in pending:
            try:
                parsed = (
                    json.loads(raw_trace) if isinstance(raw_trace, str) else raw_trace
                )
            except (TypeError, json.JSONDecodeError) as exc:
                raise HistoricalOutcomeRescoreError(
                    f"Cannot parse preserved tool trace in {source_label}: {exc}"
                ) from exc
            traces = parsed if isinstance(parsed, list) else [parsed]
            for trace in traces:
                if not isinstance(trace, dict):
                    raise HistoricalOutcomeRescoreError(
                        f"Preserved tool trace in {source_label} is not an object"
                    )
                yield trace


def _complete_valid_civil_time(
    arguments: Any,
) -> dict[str, int] | None:
    """Return strictly typed, valid civil-time fields or ``None``.

    Historical traces also preserve rejected or partial tool calls. Those are
    not timezone evidence. A successful, complete call is evidence only when
    all six schema fields are integer-valued and form a valid naive datetime.
    """

    if not isinstance(arguments, Mapping):
        return None
    values: dict[str, int] = {}
    for field in HISTORICAL_TIMEZONE_ARGUMENT_FIELDS:
        value = arguments.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        values[field] = value
    try:
        dt.datetime(**values)
    except (TypeError, ValueError, OverflowError):
        return None
    return values


def _timestamp_for_timezone(arguments: Mapping[str, int], timezone_name: str) -> float:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HistoricalOutcomeRescoreError(
            f"Timezone candidate is not available: {timezone_name!r}"
        ) from exc
    return dt.datetime(**arguments, tzinfo=timezone).timestamp()


def _infer_historical_timezone(
    *,
    repo_root: Path,
    context_paths: Sequence[Path],
    label: str,
    timezone_candidates: Sequence[str],
) -> dict[str, Any]:
    if not timezone_candidates or len(set(timezone_candidates)) != len(
        timezone_candidates
    ):
        raise HistoricalOutcomeRescoreError(
            "Timezone candidates must be a non-empty unique sequence"
        )
    if not context_paths:
        raise HistoricalOutcomeRescoreError(
            f"{label} has no preserved trajectory contexts for timezone inference"
        )

    evidence: list[dict[str, Any]] = []
    evidence_source_files: dict[str, dict[str, Any]] = {}
    scanned_source_files: list[dict[str, Any]] = []
    named_trace_count = 0
    excluded_incomplete_or_invalid_trace_count = 0
    for context_path in context_paths:
        context_payload, context_file = _read_json_object(
            repo_root,
            context_path,
            f"{label} trajectory used for timezone inference",
        )
        scanned_source_files.append(context_file)
        for trace_index, trace in enumerate(
            _serialized_tool_traces(
                context_payload,
                source_label=str(context_file["path"]),
            )
        ):
            if trace.get("tool_name") != HISTORICAL_TIMEZONE_ANCHOR_TOOL:
                continue
            named_trace_count += 1
            arguments = _complete_valid_civil_time(trace.get("arguments"))
            raw_result = trace.get("result")
            if (
                arguments is None
                or isinstance(raw_result, bool)
                or not isinstance(raw_result, (int, float))
                or not math.isfinite(float(raw_result))
            ):
                excluded_incomplete_or_invalid_trace_count += 1
                continue
            observed_result = float(raw_result)
            expected_results = {
                timezone_name: _timestamp_for_timezone(arguments, timezone_name)
                for timezone_name in timezone_candidates
            }
            matching_timezones = [
                timezone_name
                for timezone_name, expected_result in expected_results.items()
                if math.isclose(
                    observed_result,
                    expected_result,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            ]
            evidence_item = {
                "trajectory_path": str(context_file["path"]),
                "trace_index": trace_index,
                "arguments": arguments,
                "observed_result": observed_result,
                "expected_results": expected_results,
                "matching_timezones": matching_timezones,
            }
            evidence.append(evidence_item)
            evidence_source_files[str(context_file["path"])] = context_file

    if not evidence:
        raise HistoricalOutcomeRescoreError(
            f"{label} has no complete, valid {HISTORICAL_TIMEZONE_ANCHOR_TOOL} "
            "trace for timezone inference"
        )
    unmatched = [item for item in evidence if not item["matching_timezones"]]
    ambiguous = [item for item in evidence if len(item["matching_timezones"]) > 1]
    if unmatched or ambiguous:
        raise HistoricalOutcomeRescoreError(
            f"{label} timezone evidence must match exactly one candidate per "
            f"complete valid trace: unmatched={len(unmatched)}, "
            f"ambiguous={len(ambiguous)}"
        )
    selected_timezones = {str(item["matching_timezones"][0]) for item in evidence}
    if len(selected_timezones) != 1:
        counts = Counter(str(item["matching_timezones"][0]) for item in evidence)
        raise HistoricalOutcomeRescoreError(
            f"{label} has conflicting timezone traces across the arm: "
            f"{dict(sorted(counts.items()))}"
        )
    selected_timezone = next(iter(selected_timezones))
    source_files = sorted(
        evidence_source_files.values(), key=lambda record: str(record["path"])
    )
    evidence_sha256 = _sha256_bytes(_canonical_json_bytes(evidence))
    return {
        "method": "all_preserved_complete_valid_civil_time_conversion_traces",
        "arm_scope": label,
        "manifest_timezone_recorded": False,
        "tool": HISTORICAL_TIMEZONE_ANCHOR_TOOL,
        "raw_trace_fields": ["tool_name", "arguments", "result"],
        "candidate_timezones": list(timezone_candidates),
        "evidence_granularity": (
            "all raw complete valid trace occurrences across the arm; repeated "
            "civil-time conversions are not deduplicated"
        ),
        "total_named_trace_occurrence_count": named_trace_count,
        "excluded_incomplete_or_invalid_trace_occurrence_count": (
            excluded_incomplete_or_invalid_trace_count
        ),
        "complete_valid_trace_occurrence_count": len(evidence),
        "matched_trace_occurrence_count": len(evidence),
        "ambiguous_trace_occurrence_count": 0,
        "unmatched_trace_occurrence_count": 0,
        "conflicting_trace_occurrence_count": 0,
        "evidence_sha256": evidence_sha256,
        "evidence_digest_algorithm": "sha256(sorted-json(evidence))",
        "scanned_trajectory_file_count": len(scanned_source_files),
        "scanned_trajectory_files_sha256": _input_tree_sha256(scanned_source_files),
        "evidence_source_file_count": len(source_files),
        "evidence_source_files_sha256": _input_tree_sha256(source_files),
        "evidence_source_files": source_files,
        "selected_timezone": selected_timezone,
    }


def _leaf_run_directory(candidate_root: Path, label: str) -> Path:
    if (candidate_root / "trajectories").is_dir():
        return candidate_root
    matches = sorted(path.parent for path in candidate_root.glob("*/trajectories"))
    if len(matches) != 1:
        raise HistoricalOutcomeRescoreError(
            f"{label} must contain exactly one completed leaf run; found {len(matches)}"
        )
    return matches[0]


def _trajectory_coverage(
    trajectory_root: Path,
    expected_names: Sequence[str],
    *,
    label: str,
) -> dict[str, Any]:
    names = sorted(
        path.parent.name for path in trajectory_root.glob("*/execution_context.json")
    )
    return _coverage(expected_names, names, label=label)


def _score_task(
    *,
    repo_root: Path,
    scenario_name: str,
    scenario: Any,
    context_path: Path,
    context_decoder: ContextDecoder,
    outcome_scorer: OutcomeScorer,
    evaluator_identity: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    context_payload, context_file = _read_json_object(
        repo_root,
        context_path,
        f"trajectory for {scenario_name}",
    )
    try:
        context = context_decoder(context_payload)
    except Exception as exc:
        raise HistoricalOutcomeRescoreError(
            f"Cannot reconstruct trajectory for {scenario_name} at {context_path}: {exc}"
        ) from exc
    try:
        outcome = outcome_scorer(
            scenario,
            context,
            scenario_name=scenario_name,
        )
    except Exception as exc:
        raise HistoricalOutcomeRescoreError(
            f"Outcome evaluation failed for {scenario_name}: {exc}"
        ) from exc
    for result_field, identity_field in (
        ("outcome_evaluator_version", "version"),
        ("outcome_evaluator_contract_sha256", "contract_sha256"),
        ("outcome_evaluator_source_sha256", "source_sha256"),
    ):
        if outcome.get(result_field) != evaluator_identity[identity_field]:
            raise HistoricalOutcomeRescoreError(
                f"Outcome identity mismatch for {scenario_name}: {result_field}"
            )
    raw_value = outcome.get("outcome_similarity")
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise HistoricalOutcomeRescoreError(
            f"Outcome evaluator returned no numeric value for {scenario_name}"
        )
    value = float(raw_value)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise HistoricalOutcomeRescoreError(
            f"Outcome evaluator returned an invalid value for {scenario_name}: {value!r}"
        )
    return {
        "task": scenario_name,
        "outcome_value": value,
        "exact_outcome_success": value == 1.0,
    }, context_file


def _summarize_outcomes(task_outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [float(row["outcome_value"]) for row in task_outcomes]
    exact = sum(bool(row["exact_outcome_success"]) for row in task_outcomes)
    return {
        "task_count": len(task_outcomes),
        "outcome_value_count": len(values),
        "outcome_mean": math.fsum(values) / len(values) if values else None,
        "exact_outcome_successes": exact,
        "non_exact_outcomes": len(values) - exact,
    }


def _input_tree_sha256(files: Sequence[Mapping[str, Any]]) -> str:
    ordered = sorted(
        (dict(record) for record in files), key=lambda record: str(record["path"])
    )
    return _sha256_bytes(_canonical_json_bytes(ordered))


def _score_run(
    *,
    repo_root: Path,
    label: str,
    expected_names: Sequence[str],
    coverage: Mapping[str, Any],
    trajectory_root: Callable[[str], Path],
    scenarios: Mapping[str, Any],
    context_decoder: ContextDecoder,
    outcome_scorer: OutcomeScorer,
    evaluator_identity: Mapping[str, Any],
    fixed_timestamp: str,
    timezone_name: str,
    initial_input_files: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    task_outcomes: list[dict[str, Any]] = []
    input_files = [dict(record) for record in initial_input_files]
    trajectory_input_files: list[dict[str, Any]] = []
    with _scenario_clock(fixed_timestamp, timezone_name):
        for scenario_name in expected_names:
            task_outcome, context_file = _score_task(
                repo_root=repo_root,
                scenario_name=scenario_name,
                scenario=scenarios[scenario_name],
                context_path=trajectory_root(scenario_name),
                context_decoder=context_decoder,
                outcome_scorer=outcome_scorer,
                evaluator_identity=evaluator_identity,
            )
            task_outcomes.append(task_outcome)
            input_files.append(context_file)
            trajectory_input_files.append(context_file)
    input_files.sort(key=lambda record: str(record["path"]))
    return {
        "label": label,
        "fixed_toolsandbox_timestamp": fixed_timestamp,
        "timezone": timezone_name,
        "coverage": dict(coverage),
        "results": _summarize_outcomes(task_outcomes),
        "task_outcomes": task_outcomes,
        "trajectory_input_file_count": len(trajectory_input_files),
        "trajectory_input_files_sha256": _input_tree_sha256(trajectory_input_files),
        "input_files_sha256": _input_tree_sha256(input_files),
        "input_files": input_files,
    }


def _assert_timezone_sources_unchanged(
    run_report: Mapping[str, Any],
    timezone_inference: Mapping[str, Any],
    *,
    label: str,
) -> None:
    if run_report.get("trajectory_input_file_count") != timezone_inference.get(
        "scanned_trajectory_file_count"
    ) or run_report.get("trajectory_input_files_sha256") != timezone_inference.get(
        "scanned_trajectory_files_sha256"
    ):
        raise HistoricalOutcomeRescoreError(
            f"{label} trajectory inputs changed between timezone inference and scoring"
        )


def _protocol_clock(
    protocol_manifest: Mapping[str, Any],
    *,
    label: str,
) -> str:
    return _string(
        protocol_manifest,
        "toolsandbox_fixed_now_timestamp",
        f"{label} protocol manifest",
    )


def build_historical_outcome_report(
    *,
    repo_root: Path = REPO_ROOT,
    campaign_manifest_path: Path = DEFAULT_CAMPAIGN_MANIFEST,
    baseline_records_path: Path = DEFAULT_BASELINE_RECORDS,
    baseline_metadata_path: Path = DEFAULT_BASELINE_METADATA,
    benchmark_manifest_path: Path | None = None,
    timezone_candidates: Sequence[str] = HISTORICAL_TIMEZONE_CANDIDATES,
    expected_task_count: int = EXPECTED_TASK_COUNT,
    expected_candidate_runs: int = EXPECTED_CANDIDATE_RUNS,
    scenario_resolver: ScenarioResolver = _default_scenario_resolver,
    context_decoder: ContextDecoder = ExecutionContext.from_dict,
    outcome_scorer: OutcomeScorer = compute_outcome_score,
    evaluator_identity_provider: EvaluatorIdentityProvider = outcome_evaluator_manifest,
) -> dict[str, Any]:
    """Build a deterministic historical endpoint-rescoring report in memory."""

    root = repo_root.resolve()
    campaign_path = _resolve_path(root, campaign_manifest_path)
    baseline_path = _resolve_path(root, baseline_records_path)
    baseline_metadata_resolved = _resolve_path(root, baseline_metadata_path)
    campaign, campaign_file = _read_json_object(
        root, campaign_path, "historical campaign manifest"
    )
    baseline_metadata, baseline_metadata_file = _read_json_object(
        root, baseline_metadata_resolved, "original-v140 metadata"
    )
    if benchmark_manifest_path is None:
        benchmark_manifest_path = Path(
            _string(campaign, "benchmark_manifest", "historical campaign manifest")
        )
    benchmark_path = _resolve_path(root, benchmark_manifest_path)
    benchmark, benchmark_file = _read_json_object(
        root, benchmark_path, "benchmark manifest"
    )
    _assert_recorded_sha256(
        campaign,
        "benchmark_sha256",
        str(benchmark_file["sha256"]),
        label="historical campaign manifest",
    )
    expected_names = _ordered_task_names(benchmark)
    if len(expected_names) != expected_task_count:
        raise HistoricalOutcomeRescoreError(
            f"Expected {expected_task_count} benchmark tasks, found {len(expected_names)}"
        )
    campaign_expected_tasks = _integer(
        campaign, "expected_tasks_per_run", "historical campaign manifest"
    )
    if campaign_expected_tasks != expected_task_count:
        raise HistoricalOutcomeRescoreError(
            "Campaign expected_tasks_per_run does not match the benchmark: "
            f"{campaign_expected_tasks} != {expected_task_count}"
        )

    evaluator_identity_before = _validate_evaluator_identity(
        evaluator_identity_provider()
    )
    rescorer_source = Path(__file__).resolve()
    _, rescorer_source_file = _file_record(root, rescorer_source, "rescorer source")

    baseline_records, baseline_records_file = _read_jsonl_objects(
        root, baseline_path, "original-v140 records"
    )
    _assert_recorded_sha256(
        baseline_metadata,
        "snapshot_sha256",
        str(baseline_records_file["sha256"]),
        label="original-v140 metadata",
    )
    baseline_names = [
        _string(record, "scenario_key", f"original-v140 record {index}")
        for index, record in enumerate(baseline_records)
    ]
    baseline_coverage = _coverage(
        expected_names, baseline_names, label="original-v140 records"
    )
    if _integer(baseline_metadata, "record_count", "original-v140 metadata") != len(
        baseline_records
    ):
        raise HistoricalOutcomeRescoreError(
            "Original-v140 metadata record_count does not match the frozen records"
        )
    if _integer(
        baseline_metadata, "unique_scenario_count", "original-v140 metadata"
    ) != len(set(baseline_names)):
        raise HistoricalOutcomeRescoreError(
            "Original-v140 metadata unique_scenario_count does not match the frozen records"
        )
    for index, record in enumerate(baseline_records):
        name = baseline_names[index]
        if (
            record.get("complete_run") is not True
            or record.get("valid_for_cache") is not True
        ):
            raise HistoricalOutcomeRescoreError(
                f"Original-v140 record is not complete and valid: {name}"
            )
    source_run_root = _resolve_path(
        root,
        _string(baseline_metadata, "source_run_root", "original-v140 metadata"),
    )
    baseline_protocol_path = source_run_root / "protocol_manifest.json"
    baseline_protocol, baseline_protocol_file = _read_json_object(
        root, baseline_protocol_path, "original-v140 protocol manifest"
    )
    baseline_timestamp = _protocol_clock(baseline_protocol, label="original-v140")
    metadata_source_control_dir = _resolve_path(
        root,
        _string(
            baseline_metadata,
            "source_control_dir",
            "original-v140 metadata",
        ),
    )
    record_run_dirs = {
        _resolve_path(
            root,
            _string(record, "run_dir", f"original-v140 record {index}"),
        )
        for index, record in enumerate(baseline_records)
    }
    if record_run_dirs != {metadata_source_control_dir}:
        raise HistoricalOutcomeRescoreError(
            "Original-v140 records do not all reference the frozen source control run"
        )

    baseline_context_paths = [
        metadata_source_control_dir / "trajectories" / name / "execution_context.json"
        for name in expected_names
    ]
    baseline_timezone_inference = _infer_historical_timezone(
        repo_root=root,
        context_paths=baseline_context_paths,
        label="original-v140",
        timezone_candidates=timezone_candidates,
    )
    baseline_timezone = str(baseline_timezone_inference["selected_timezone"])
    with _scenario_clock(baseline_timestamp, baseline_timezone):
        baseline_scenarios = scenario_resolver(expected_names)
    if set(baseline_scenarios) != set(expected_names):
        raise HistoricalOutcomeRescoreError(
            "Scenario resolver did not return exact benchmark coverage for original-v140"
        )
    baseline_report = _score_run(
        repo_root=root,
        label="original_v140",
        expected_names=expected_names,
        coverage=baseline_coverage,
        trajectory_root=lambda name: (
            metadata_source_control_dir
            / "trajectories"
            / name
            / "execution_context.json"
        ),
        scenarios=baseline_scenarios,
        context_decoder=context_decoder,
        outcome_scorer=outcome_scorer,
        evaluator_identity=evaluator_identity_before,
        fixed_timestamp=baseline_timestamp,
        timezone_name=baseline_timezone,
        initial_input_files=(baseline_protocol_file,),
    )
    _assert_timezone_sources_unchanged(
        baseline_report,
        baseline_timezone_inference,
        label="original-v140",
    )
    baseline_report["timezone_inference"] = baseline_timezone_inference
    baseline_report["source_run_root"] = _display_path(root, source_run_root)
    baseline_report["source_trajectory_root"] = _display_path(
        root, metadata_source_control_dir
    )

    run_pairs = campaign.get("run_pairs")
    if not isinstance(run_pairs, list) or len(run_pairs) != expected_candidate_runs:
        raise HistoricalOutcomeRescoreError(
            f"Expected {expected_candidate_runs} historical candidate runs, "
            f"found {len(run_pairs) if isinstance(run_pairs, list) else 'invalid'}"
        )
    expected_manifest_runs = _integer(
        campaign, "expected_online_runs", "historical campaign manifest"
    )
    if expected_manifest_runs != expected_candidate_runs:
        raise HistoricalOutcomeRescoreError(
            "Campaign expected_online_runs does not match requested run count: "
            f"{expected_manifest_runs} != {expected_candidate_runs}"
        )
    campaign_timestamp_raw = campaign.get("fixed_toolsandbox_timestamp")
    if isinstance(campaign_timestamp_raw, bool) or not isinstance(
        campaign_timestamp_raw, (int, float, str)
    ):
        raise HistoricalOutcomeRescoreError(
            "Historical campaign manifest has no fixed_toolsandbox_timestamp"
        )
    campaign_timestamp = str(campaign_timestamp_raw)
    candidate_reports: list[dict[str, Any]] = []
    replications: list[int] = []
    for run_index, run_pair in enumerate(run_pairs):
        if not isinstance(run_pair, dict):
            raise HistoricalOutcomeRescoreError(
                f"Campaign run pair {run_index} is not an object"
            )
        replication = _integer(run_pair, "replication", f"run pair {run_index}")
        replications.append(replication)
        online = run_pair.get("online")
        if not isinstance(online, dict):
            raise HistoricalOutcomeRescoreError(
                f"Run pair {replication} is missing object 'online'"
            )
        if (
            online.get("execution_status") != "completed"
            or online.get("return_code") != 0
        ):
            raise HistoricalOutcomeRescoreError(
                f"Historical candidate replication {replication} is not complete"
            )
        run_root = _resolve_path(
            root,
            _string(online, "run_root", f"candidate replication {replication}"),
        )
        protocol_path = run_root / "protocol_manifest.json"
        protocol, protocol_file = _read_json_object(
            root, protocol_path, f"candidate replication {replication} protocol"
        )
        run_timestamp = _protocol_clock(
            protocol, label=f"candidate replication {replication}"
        )
        if run_timestamp != campaign_timestamp:
            raise HistoricalOutcomeRescoreError(
                f"Candidate replication {replication} timestamp {run_timestamp!r} "
                f"does not match campaign timestamp {campaign_timestamp!r}"
            )
        candidate_root = run_root / "candidate"
        run_manifest_path = candidate_root / "sage_ts_run_manifest.json"
        run_manifest, run_manifest_file = _read_json_object(
            root,
            run_manifest_path,
            f"candidate replication {replication} run manifest",
        )
        manifest_names = run_manifest.get("scenario_names")
        if not isinstance(manifest_names, list) or not all(
            isinstance(name, str) and name for name in manifest_names
        ):
            raise HistoricalOutcomeRescoreError(
                f"Candidate replication {replication} has invalid scenario_names"
            )
        manifest_coverage = _coverage(
            expected_names,
            manifest_names,
            label=f"candidate replication {replication} manifest",
        )
        if manifest_names != expected_names:
            raise HistoricalOutcomeRescoreError(
                f"Candidate replication {replication} manifest task order differs "
                "from the benchmark"
            )
        leaf_run_dir = _leaf_run_directory(
            candidate_root, f"candidate replication {replication}"
        )
        trajectory_coverage = _trajectory_coverage(
            leaf_run_dir / "trajectories",
            expected_names,
            label=f"candidate replication {replication} trajectories",
        )
        context_paths = [
            leaf_run_dir / "trajectories" / name / "execution_context.json"
            for name in expected_names
        ]
        timezone_inference = _infer_historical_timezone(
            repo_root=root,
            context_paths=context_paths,
            label=f"candidate replication {replication}",
            timezone_candidates=timezone_candidates,
        )
        selected_timezone = str(timezone_inference["selected_timezone"])
        with _scenario_clock(run_timestamp, selected_timezone):
            candidate_scenarios = scenario_resolver(expected_names)
        if set(candidate_scenarios) != set(expected_names):
            raise HistoricalOutcomeRescoreError(
                "Scenario resolver did not return exact benchmark coverage for "
                f"candidate replication {replication}"
            )
        report = _score_run(
            repo_root=root,
            label=f"sage_online_rep{replication:02d}",
            expected_names=expected_names,
            coverage=trajectory_coverage,
            trajectory_root=lambda name, leaf=leaf_run_dir: (
                leaf / "trajectories" / name / "execution_context.json"
            ),
            scenarios=candidate_scenarios,
            context_decoder=context_decoder,
            outcome_scorer=outcome_scorer,
            evaluator_identity=evaluator_identity_before,
            fixed_timestamp=run_timestamp,
            timezone_name=selected_timezone,
            initial_input_files=(protocol_file, run_manifest_file),
        )
        _assert_timezone_sources_unchanged(
            report,
            timezone_inference,
            label=f"candidate replication {replication}",
        )
        report["timezone_inference"] = timezone_inference
        report["replication"] = replication
        report["source_run_root"] = _display_path(root, run_root)
        report["source_trajectory_root"] = _display_path(root, leaf_run_dir)
        report["manifest_coverage"] = manifest_coverage
        candidate_reports.append(report)

    expected_replications = list(range(1, expected_candidate_runs + 1))
    if sorted(replications) != expected_replications:
        raise HistoricalOutcomeRescoreError(
            "Candidate replication identities are not exactly "
            f"{expected_replications}: observed {sorted(replications)}"
        )
    candidate_reports.sort(key=lambda report: int(report["replication"]))
    means = [float(report["results"]["outcome_mean"]) for report in candidate_reports]
    exact_counts = [
        int(report["results"]["exact_outcome_successes"])
        for report in candidate_reports
    ]
    minimum_mean = min(means)
    minimum_exact = min(exact_counts)

    evaluator_identity_after = _validate_evaluator_identity(
        evaluator_identity_provider()
    )
    if evaluator_identity_after != evaluator_identity_before:
        raise HistoricalOutcomeRescoreError(
            "Outcome evaluator identity changed during historical rescoring"
        )

    payload: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_type": "historical_terminal_trajectory_outcome_rescore",
        "provenance_status": (
            "historical_terminal_trajectories_timezone_inferred_not_confirmatory"
        ),
        "provenance_caveat": PROVENANCE_CAVEAT,
        "metric": {
            "name": "outcome_task_completion_similarity",
            "range": [0.0, 1.0],
            "exact_outcome_success_definition": "outcome_value == 1.0",
        },
        "outcome_evaluator": evaluator_identity_before,
        "rescorer": {
            "source": rescorer_source_file,
            "input_mode": "read_only",
            "outcome_input_contract": ["resolved_scenario", "execution_context"],
            "stored_score_fields_consumed": False,
            "stored_result_summary_consumed": False,
            "timezone_inference": {
                "tool": HISTORICAL_TIMEZONE_ANCHOR_TOOL,
                "candidate_timezones": list(timezone_candidates),
                "scope": "all_complete_valid_traces_per_arm",
                "arm_independence": (
                    "baseline and every candidate replication are inferred from "
                    "their own raw trajectory traces"
                ),
                "selection_inputs": ["tool_name", "arguments", "result"],
                "arm_identity_or_replication_used_for_selection": False,
                "evidence_granularity": (
                    "trace occurrences, not deduplicated conversions"
                ),
                "failure_policy": (
                    "fail_closed_on_missing_unmatched_ambiguous_or_conflicting_evidence"
                ),
            },
        },
        "primary_input_files": [
            campaign_file,
            benchmark_file,
            baseline_metadata_file,
            baseline_records_file,
        ],
        "benchmark": {
            "task_count": len(expected_names),
            "unique_task_count": len(set(expected_names)),
            "ordered_task_names_sha256": _names_sha256(expected_names),
            "first_task": expected_names[0],
            "last_task": expected_names[-1],
            "ordered_task_names": expected_names,
        },
        "baseline": baseline_report,
        "candidates": candidate_reports,
        "candidate_summary": {
            "run_count": len(candidate_reports),
            "task_outcome_observation_count": len(candidate_reports)
            * len(expected_names),
            "mean_of_run_outcome_means": math.fsum(means) / len(means),
            "total_exact_outcome_successes": sum(exact_counts),
            "lower_envelope": {
                "minimum_run_outcome_mean": minimum_mean,
                "minimum_run_outcome_mean_replications": [
                    int(report["replication"])
                    for report, value in zip(candidate_reports, means, strict=True)
                    if value == minimum_mean
                ],
                "minimum_run_exact_outcome_successes": minimum_exact,
                "minimum_run_exact_outcome_success_replications": [
                    int(report["replication"])
                    for report, value in zip(
                        candidate_reports, exact_counts, strict=True
                    )
                    if value == minimum_exact
                ],
            },
        },
    }
    payload["primary_input_files"].sort(key=lambda record: str(record["path"]))
    content_sha256 = _sha256_bytes(_canonical_json_bytes(payload))
    return {
        "content_address": {
            "algorithm": CONTENT_ADDRESS_ALGORITHM,
            "sha256": content_sha256,
        },
        "payload": payload,
    }


def write_report_atomic(
    output_path: Path,
    report: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> None:
    """Atomically write a report, refusing an existing target by default."""

    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = _canonical_json_bytes(report, pretty=True)
    descriptor, raw_temporary_path = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary_path = Path(raw_temporary_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(report_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary_path, output)
        else:
            try:
                os.link(temporary_path, output)
            except FileExistsError as exc:
                raise HistoricalOutcomeRescoreError(
                    f"Refusing to overwrite existing report: {output}"
                ) from exc
            temporary_path.unlink()
        try:
            directory_descriptor = os.open(output.parent, os.O_RDONLY)
        except OSError:
            directory_descriptor = None
        if directory_descriptor is not None:
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New JSON report path (must not exist unless --overwrite is set).",
    )
    parser.add_argument(
        "--campaign-manifest", type=Path, default=DEFAULT_CAMPAIGN_MANIFEST
    )
    parser.add_argument(
        "--baseline-records", type=Path, default=DEFAULT_BASELINE_RECORDS
    )
    parser.add_argument(
        "--baseline-metadata", type=Path, default=DEFAULT_BASELINE_METADATA
    )
    parser.add_argument(
        "--benchmark-manifest",
        type=Path,
        help="Override the benchmark path recorded in the campaign manifest.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Atomically replace an existing output path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_historical_outcome_report(
        repo_root=REPO_ROOT,
        campaign_manifest_path=args.campaign_manifest,
        baseline_records_path=args.baseline_records,
        baseline_metadata_path=args.baseline_metadata,
        benchmark_manifest_path=args.benchmark_manifest,
    )
    write_report_atomic(args.output, report, overwrite=args.overwrite)
    print(f"Historical outcome report: {args.output.resolve()}")
    print(f"Content SHA-256: {report['content_address']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
