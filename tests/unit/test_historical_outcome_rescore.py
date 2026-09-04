from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from scripts.rescore_historical_outcomes import (
    HistoricalOutcomeRescoreError,
    _canonical_json_bytes,
    _infer_historical_timezone,
    build_historical_outcome_report,
    write_report_atomic,
)

IDENTITY = {
    "version": "fixture-outcomes-v1",
    "contract_sha256": "a" * 64,
    "source_sha256": "b" * 64,
    "insufficient_information_scenario_count": 0,
    "scalar_scenario_count": 0,
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _result_row(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "milestone_mapping": "poison: outcome rescorer must not read this",
        "minefield_similarity": {"poison": "outcome rescorer must not read this"},
    }


_CIVIL_TIME = {
    "year": 2024,
    "month": 3,
    "day": 22,
    "hour": 17,
    "minute": 0,
    "second": 0,
}


def _conversion_trace(
    timezone_name: str,
    *,
    result_delta: float = 0.0,
) -> dict[str, Any]:
    timestamp = datetime(**_CIVIL_TIME, tzinfo=ZoneInfo(timezone_name)).timestamp()
    return {
        "tool_name": "datetime_info_to_timestamp",
        "arguments": dict(_CIVIL_TIME),
        "result": timestamp + result_delta,
    }


def _write_context(
    root: Path,
    name: str,
    outcome: float,
    *,
    timezone_name: str,
    extra_traces: list[dict[str, Any]] | None = None,
) -> Path:
    traces = [_conversion_trace(timezone_name), *(extra_traces or [])]
    path = root / "trajectories" / name / "execution_context.json"
    _write_json(
        path,
        {
            "fixture_outcome": outcome,
            "_dbs": {
                "SANDBOX": [
                    {"tool_trace": [json.dumps(trace) for trace in traces]},
                ]
            },
        },
    )
    return path


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    names = ["task_a", "task_b"]
    benchmark = tmp_path / "benchmark.json"
    _write_json(
        benchmark,
        {"splits": {"full_benchmark": [{"name": name} for name in names]}},
    )

    baseline_root = tmp_path / "baseline_run"
    baseline_control = baseline_root / "control_leaf"
    _write_json(
        baseline_root / "protocol_manifest.json",
        {"toolsandbox_fixed_now_timestamp": "100"},
    )
    for name, value in zip(names, [0.0, 1.0], strict=True):
        _write_context(
            baseline_control,
            name,
            value,
            timezone_name="America/New_York",
        )
    baseline_records = tmp_path / "frozen" / "original_records.jsonl"
    baseline_records.parent.mkdir(parents=True)
    baseline_records.write_text(
        "".join(
            json.dumps(
                {
                    "scenario_key": name,
                    "complete_run": True,
                    "valid_for_cache": True,
                    "run_dir": baseline_control.relative_to(tmp_path).as_posix(),
                    "result_row": _result_row(name),
                }
            )
            + "\n"
            for name in names
        ),
        encoding="utf-8",
    )
    baseline_metadata = tmp_path / "frozen" / "original_metadata.json"
    _write_json(
        baseline_metadata,
        {
            "source_run_root": baseline_root.relative_to(tmp_path).as_posix(),
            "source_control_dir": baseline_control.relative_to(tmp_path).as_posix(),
            "snapshot_sha256": hashlib.sha256(
                baseline_records.read_bytes()
            ).hexdigest(),
            "record_count": len(names),
            "unique_scenario_count": len(names),
        },
    )

    run_pairs: list[dict[str, Any]] = []
    values_by_replication = {1: [1.0, 0.5], 2: [0.25, 1.0]}
    timezones_by_replication = {
        1: "America/Los_Angeles",
        2: "America/New_York",
    }
    for replication, values in values_by_replication.items():
        run_root = tmp_path / f"candidate_rep{replication:02d}"
        candidate_root = run_root / "candidate"
        leaf = candidate_root / "leaf"
        _write_json(
            run_root / "protocol_manifest.json",
            {"toolsandbox_fixed_now_timestamp": "200"},
        )
        _write_json(
            candidate_root / "sage_ts_run_manifest.json",
            {"scenario_names": names},
        )
        _write_json(
            leaf / "result_summary.json",
            {"per_scenario_results": [_result_row(name) for name in names]},
        )
        for name, value in zip(names, values, strict=True):
            _write_context(
                leaf,
                name,
                value,
                timezone_name=timezones_by_replication[replication],
            )
        run_pairs.append(
            {
                "replication": replication,
                "online": {
                    "run_root": run_root.relative_to(tmp_path).as_posix(),
                    "execution_status": "completed",
                    "return_code": 0,
                },
            }
        )

    campaign = tmp_path / "campaign.json"
    _write_json(
        campaign,
        {
            "benchmark_manifest": benchmark.relative_to(tmp_path).as_posix(),
            "benchmark_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
            "expected_tasks_per_run": len(names),
            "expected_online_runs": 2,
            "fixed_toolsandbox_timestamp": 200,
            "run_pairs": run_pairs,
        },
    )
    return {
        "campaign": campaign,
        "benchmark": benchmark,
        "baseline_records": baseline_records,
        "baseline_metadata": baseline_metadata,
    }


def _fake_scorer(
    _scenario: Any,
    context: dict[str, Any],
    *,
    scenario_name: str,
) -> dict[str, Any]:
    assert scenario_name in {"task_a", "task_b"}
    return {
        "outcome_similarity": context["fixture_outcome"],
        "outcome_evaluator_version": IDENTITY["version"],
        "outcome_evaluator_contract_sha256": IDENTITY["contract_sha256"],
        "outcome_evaluator_source_sha256": IDENTITY["source_sha256"],
    }


def _build_fixture_report(tmp_path: Path) -> dict[str, Any]:
    paths = _fixture_tree(tmp_path)
    observed_clocks: list[tuple[str | None, str | None]] = []

    def resolve(names: list[str]) -> dict[str, str]:
        observed_clocks.append(
            (os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"), os.environ.get("TZ"))
        )
        return {name: name for name in names}

    report = build_historical_outcome_report(
        repo_root=tmp_path,
        campaign_manifest_path=paths["campaign"],
        baseline_records_path=paths["baseline_records"],
        baseline_metadata_path=paths["baseline_metadata"],
        expected_task_count=2,
        expected_candidate_runs=2,
        scenario_resolver=resolve,
        context_decoder=lambda payload: payload,
        outcome_scorer=_fake_scorer,
        evaluator_identity_provider=lambda: dict(IDENTITY),
    )
    assert observed_clocks == [
        ("100", "America/New_York"),
        ("200", "America/Los_Angeles"),
        ("200", "America/New_York"),
    ]
    return report


def test_build_report_is_outcome_only_complete_and_content_addressed(
    tmp_path: Path,
) -> None:
    report = _build_fixture_report(tmp_path)
    payload = report["payload"]

    assert payload["benchmark"]["ordered_task_names"] == ["task_a", "task_b"]
    assert payload["baseline"]["coverage"]["complete"] is True
    assert payload["baseline"]["results"] == {
        "task_count": 2,
        "outcome_value_count": 2,
        "outcome_mean": 0.5,
        "exact_outcome_successes": 1,
        "non_exact_outcomes": 1,
    }
    assert [run["results"]["outcome_mean"] for run in payload["candidates"]] == [
        0.75,
        0.625,
    ]
    assert payload["candidate_summary"]["lower_envelope"] == {
        "minimum_run_outcome_mean": 0.625,
        "minimum_run_outcome_mean_replications": [2],
        "minimum_run_exact_outcome_successes": 1,
        "minimum_run_exact_outcome_success_replications": [1, 2],
    }
    assert "terminal trajectories only" in payload["provenance_caveat"]
    assert "canonical" not in json.dumps(payload).lower()
    assert payload["rescorer"]["outcome_input_contract"] == [
        "resolved_scenario",
        "execution_context",
    ]
    assert payload["rescorer"]["stored_score_fields_consumed"] is False
    assert payload["rescorer"]["stored_result_summary_consumed"] is False
    assert payload["baseline"]["timezone"] == "America/New_York"
    assert [candidate["timezone"] for candidate in payload["candidates"]] == [
        "America/Los_Angeles",
        "America/New_York",
    ]
    for arm in [payload["baseline"], *payload["candidates"]]:
        inference = arm["timezone_inference"]
        assert inference["complete_valid_trace_occurrence_count"] == 2
        assert inference["matched_trace_occurrence_count"] == 2
        assert inference["ambiguous_trace_occurrence_count"] == 0
        assert inference["unmatched_trace_occurrence_count"] == 0
        assert inference["conflicting_trace_occurrence_count"] == 0
        assert len(inference["evidence_sha256"]) == 64
        assert len(inference["evidence_source_files_sha256"]) == 64
        assert inference["evidence_source_file_count"] == 2
        assert "not deduplicated" in inference["evidence_granularity"]
        assert arm["trajectory_input_file_count"] == 2
        assert (
            arm["trajectory_input_files_sha256"]
            == inference["scanned_trajectory_files_sha256"]
        )
    assert (
        report["content_address"]["sha256"]
        == hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    )
    assert all(len(record["sha256"]) == 64 for record in payload["primary_input_files"])
    assert all(candidate["input_files_sha256"] for candidate in payload["candidates"])
    assert not any(
        record["path"].endswith("result_summary.json")
        for candidate in payload["candidates"]
        for record in candidate["input_files"]
    )


def test_atomic_writer_refuses_overwrite_unless_explicit(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "historical.json"
    first = {"content_address": {"sha256": "a" * 64}, "payload": {"value": 1}}
    second = {"content_address": {"sha256": "b" * 64}, "payload": {"value": 2}}

    write_report_atomic(output, first)
    first_bytes = output.read_bytes()
    with pytest.raises(HistoricalOutcomeRescoreError, match="Refusing to overwrite"):
        write_report_atomic(output, second)
    assert output.read_bytes() == first_bytes

    write_report_atomic(output, second, overwrite=True)
    assert json.loads(output.read_text(encoding="utf-8")) == second
    assert not list(output.parent.glob(".historical.json.*.tmp"))


def test_rescore_rejects_incomplete_baseline_coverage(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    lines = paths["baseline_records"].read_text(encoding="utf-8").splitlines()
    paths["baseline_records"].write_text(lines[0] + "\n", encoding="utf-8")
    metadata = json.loads(paths["baseline_metadata"].read_text(encoding="utf-8"))
    metadata["snapshot_sha256"] = hashlib.sha256(
        paths["baseline_records"].read_bytes()
    ).hexdigest()
    _write_json(paths["baseline_metadata"], metadata)

    with pytest.raises(HistoricalOutcomeRescoreError, match="does not exactly cover"):
        build_historical_outcome_report(
            repo_root=tmp_path,
            campaign_manifest_path=paths["campaign"],
            baseline_records_path=paths["baseline_records"],
            baseline_metadata_path=paths["baseline_metadata"],
            expected_task_count=2,
            expected_candidate_runs=2,
            scenario_resolver=lambda names: {name: name for name in names},
            context_decoder=lambda payload: payload,
            outcome_scorer=_fake_scorer,
            evaluator_identity_provider=lambda: dict(IDENTITY),
        )


def test_timezone_inference_counts_all_raw_trace_occurrences(tmp_path: Path) -> None:
    arm_root = tmp_path / "arm"
    incomplete_trace = {
        "tool_name": "datetime_info_to_timestamp",
        "arguments": {"year": 2024},
        "result": 0.0,
    }
    first = _write_context(
        arm_root,
        "task_a",
        1.0,
        timezone_name="America/New_York",
        extra_traces=[
            _conversion_trace("America/New_York"),
            incomplete_trace,
        ],
    )
    second = _write_context(
        arm_root,
        "task_b",
        1.0,
        timezone_name="America/New_York",
    )

    inference = _infer_historical_timezone(
        repo_root=tmp_path,
        context_paths=[first, second],
        label="fixture arm",
        timezone_candidates=("America/New_York", "America/Los_Angeles"),
    )

    assert inference["selected_timezone"] == "America/New_York"
    assert inference["total_named_trace_occurrence_count"] == 4
    assert inference["excluded_incomplete_or_invalid_trace_occurrence_count"] == 1
    assert inference["complete_valid_trace_occurrence_count"] == 3
    assert inference["matched_trace_occurrence_count"] == 3
    assert inference["evidence_source_file_count"] == 2


def test_timezone_inference_rejects_conflicting_arm_evidence(tmp_path: Path) -> None:
    arm_root = tmp_path / "arm"
    paths = [
        _write_context(
            arm_root,
            "task_a",
            1.0,
            timezone_name="America/New_York",
        ),
        _write_context(
            arm_root,
            "task_b",
            1.0,
            timezone_name="America/Los_Angeles",
        ),
    ]

    with pytest.raises(HistoricalOutcomeRescoreError, match="conflicting timezone"):
        _infer_historical_timezone(
            repo_root=tmp_path,
            context_paths=paths,
            label="fixture arm",
            timezone_candidates=("America/New_York", "America/Los_Angeles"),
        )


@pytest.mark.parametrize(
    ("trace_timezone", "result_delta", "timezone_candidates", "expected_counts"),
    [
        (
            "America/New_York",
            1.0,
            ("America/New_York", "America/Los_Angeles"),
            "unmatched=1, ambiguous=0",
        ),
        (
            "UTC",
            0.0,
            ("UTC", "Etc/UTC"),
            "unmatched=0, ambiguous=1",
        ),
    ],
)
def test_timezone_inference_rejects_unmatched_or_ambiguous_trace(
    tmp_path: Path,
    trace_timezone: str,
    result_delta: float,
    timezone_candidates: tuple[str, str],
    expected_counts: str,
) -> None:
    context_path = _write_context(
        tmp_path / "arm",
        "task_a",
        1.0,
        timezone_name=trace_timezone,
        extra_traces=[] if result_delta == 0.0 else None,
    )
    if result_delta:
        payload = json.loads(context_path.read_text(encoding="utf-8"))
        trace = json.loads(payload["_dbs"]["SANDBOX"][0]["tool_trace"][0])
        trace["result"] += result_delta
        payload["_dbs"]["SANDBOX"][0]["tool_trace"][0] = json.dumps(trace)
        _write_json(context_path, payload)

    with pytest.raises(HistoricalOutcomeRescoreError, match=expected_counts):
        _infer_historical_timezone(
            repo_root=tmp_path,
            context_paths=[context_path],
            label="fixture arm",
            timezone_candidates=timezone_candidates,
        )


def test_timezone_inference_rejects_zero_valid_evidence(tmp_path: Path) -> None:
    context_path = tmp_path / "arm" / "execution_context.json"
    _write_json(context_path, {"_dbs": {"SANDBOX": []}})

    with pytest.raises(HistoricalOutcomeRescoreError, match="no complete, valid"):
        _infer_historical_timezone(
            repo_root=tmp_path,
            context_paths=[context_path],
            label="fixture arm",
            timezone_candidates=("America/New_York", "America/Los_Angeles"),
        )


def test_timezone_inference_rejects_unparseable_preserved_trace(tmp_path: Path) -> None:
    context_path = _write_context(
        tmp_path / "arm",
        "task_a",
        1.0,
        timezone_name="America/New_York",
    )
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    payload["_dbs"]["SANDBOX"][0]["tool_trace"].append("{not-json")
    _write_json(context_path, payload)

    with pytest.raises(HistoricalOutcomeRescoreError, match="Cannot parse preserved"):
        _infer_historical_timezone(
            repo_root=tmp_path,
            context_paths=[context_path],
            label="fixture arm",
            timezone_candidates=("America/New_York", "America/Los_Angeles"),
        )


def test_outcomes_do_not_consume_stored_score_fields(tmp_path: Path) -> None:
    paths = _fixture_tree(tmp_path)
    baseline_records = [
        json.loads(line)
        for line in paths["baseline_records"].read_text(encoding="utf-8").splitlines()
    ]
    for record in baseline_records:
        record.pop("result_row")
    paths["baseline_records"].write_text(
        "".join(json.dumps(record) + "\n" for record in baseline_records),
        encoding="utf-8",
    )
    metadata = json.loads(paths["baseline_metadata"].read_text(encoding="utf-8"))
    metadata["snapshot_sha256"] = hashlib.sha256(
        paths["baseline_records"].read_bytes()
    ).hexdigest()
    _write_json(paths["baseline_metadata"], metadata)

    for replication in (1, 2):
        result_path = (
            tmp_path
            / f"candidate_rep{replication:02d}"
            / "candidate"
            / "leaf"
            / "result_summary.json"
        )
        result_path.unlink()

    report = build_historical_outcome_report(
        repo_root=tmp_path,
        campaign_manifest_path=paths["campaign"],
        baseline_records_path=paths["baseline_records"],
        baseline_metadata_path=paths["baseline_metadata"],
        expected_task_count=2,
        expected_candidate_runs=2,
        scenario_resolver=lambda names: {name: name for name in names},
        context_decoder=lambda payload: payload,
        outcome_scorer=_fake_scorer,
        evaluator_identity_provider=lambda: dict(IDENTITY),
    )

    assert report["payload"]["baseline"]["results"]["outcome_mean"] == 0.5
    assert [
        candidate["results"]["outcome_mean"]
        for candidate in report["payload"]["candidates"]
    ] == [0.75, 0.625]
