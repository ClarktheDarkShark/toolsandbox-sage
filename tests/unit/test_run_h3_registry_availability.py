from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import run_h3_registry_availability as runner
from scripts.research.h3_registry_ablation import (
    ROBUSTNESS_SUFFIXES,
    assignment_by_scenario,
    build_registry_assignment,
)


class _FakeContext:
    def __init__(self) -> None:
        self.tool_allow_list = ["native_tool"]

    def get_available_tools(self, *, scrambling_allowed: bool) -> list[str]:
        assert scrambling_allowed is True
        return ["native_tool"]


class _FakeScenario:
    def __init__(self) -> None:
        self.starting_context = _FakeContext()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _inputs(tmp_path: Path) -> dict[str, Any]:
    variants = ("", *ROBUSTNESS_SUFFIXES)
    control_rows: list[dict[str, object]] = []
    names: list[str] = []
    for stem_index in range(129):
        stem = f"task_{stem_index:03d}"
        for variant_index, suffix in enumerate(variants):
            name = f"{stem}{suffix}"
            names.append(name)
            control_rows.append(
                {
                    "scenario": name,
                    "control_outcome_similarity": (
                        0.2 + stem_index * 0.001 + variant_index * 0.00001
                    ),
                }
            )
    assignment = build_registry_assignment(control_rows, seed=20260918)
    manifest_path = tmp_path / "benchmark.json"
    assignment_path = tmp_path / "assignment.json"
    control_path = tmp_path / "h2_control.json"
    registry_source = tmp_path / "registry_source"
    _write_json(
        manifest_path,
        {"splits": {"full_benchmark": [{"name": name} for name in names]}},
    )
    _write_json(assignment_path, assignment)
    _write_json(control_path, {"deltas": control_rows})
    _write_json(
        registry_source / "registry_manifest.json",
        {
            "tools": {
                "helper": {
                    "validation": {"accepted": True},
                    "retired": False,
                }
            }
        },
    )
    h2_report_path = tmp_path / "h2_report.json"
    _write_json(
        h2_report_path,
        {
            "inputs": {
                "control": {
                    "path": str(control_path.resolve()),
                    "sha256": runner._file_sha256(control_path),
                }
            }
        },
    )
    pilot_manifest_path = tmp_path / "pilot_manifest.json"
    _write_json(
        pilot_manifest_path,
        {
            "h2": {
                "source_report_path": str(h2_report_path.resolve()),
                "source_report_sha256": runner._file_sha256(h2_report_path),
            },
            "frozen_h123_registry": {
                "path": str(registry_source.resolve()),
                "content_sha256": runner._tree_hash(registry_source)["content_sha256"],
            },
        },
    )
    return {
        "names": names,
        "control_rows": control_rows,
        "assignment": assignment,
        "manifest_path": manifest_path,
        "assignment_path": assignment_path,
        "control_path": control_path,
        "registry_source": registry_source,
        "pilot_manifest_path": pilot_manifest_path,
    }


def _install_fake_execution(
    monkeypatch: pytest.MonkeyPatch,
    inputs: dict[str, Any],
    *,
    expose_on_masked: bool = False,
    retry_first: bool = False,
    exception_first: bool = False,
    hide_on_available: bool = False,
) -> dict[str, Any]:
    scenario_names = tuple(inputs["names"])
    assignment = assignment_by_scenario(inputs["assignment"])
    assignment_id = inputs["assignment"]["assignment_sha256"]
    control_by_name = {
        str(row["scenario"]): float(row["control_outcome_similarity"])
        for row in inputs["control_rows"]
    }
    captured: dict[str, Any] = {}
    original_analyze = runner.analyze_registry_availability

    def fast_analyze(*args: object, **kwargs: Any) -> dict[str, Any]:
        kwargs["randomization_iterations"] = 100
        kwargs["bootstrap_iterations"] = 100
        return original_analyze(*args, **kwargs)

    def fake_resolve_scenarios(**kwargs: object) -> dict[str, _FakeScenario]:
        assert kwargs["desired_scenario_names"] == list(scenario_names)
        return {name: _FakeScenario() for name in scenario_names}

    def fake_run(
        config: runner.SageRunConfig,
        *,
        generator: object,
        scenarios: dict[str, _FakeScenario],
    ) -> Path:
        assert generator is None
        assert tuple(scenarios) == scenario_names
        assert config.scenario_names == scenario_names
        assert config.registry_assignment_id == assignment_id
        assert len(config.registry_masked_scenarios) == 512
        assert config.online_feedback_mode == runner.ONLINE_FEEDBACK_ACTOR_VISIBLE
        assert config.failure_memory_path is None
        assert config.reflection_control_rows is None
        assert config.resume_from_dir is None
        assert config.fail_on_scenario_transform_error is True
        assert runner.os.environ["SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS"] == str(
            runner.PINNED_TRANSIENT_SCENARIO_RETRY_ATTEMPTS
        )
        captured["config"] = config

        config.output_dir.mkdir(parents=True)
        run_dir = config.output_dir / "run"
        run_dir.mkdir()
        _write_json(
            run_dir / "sage_ts_run_manifest.json",
            {
                "agent": config.agent,
                "user": config.user,
                "agent_runtime": config.agent_runtime,
                "base_tool_policy": config.base_tool_policy,
                "run_type": config.run_type,
                "processes": 1,
                "fail_on_scenario_transform_error": True,
                "actor_selection_mode": "policy",
                "timezone": "America/New_York",
                "resume_from_dir": None,
                "resume_completed_limit": None,
                "scenario_names": list(config.scenario_names),
                "outcome_evaluator": dict(runner.PINNED_OUTCOME_EVALUATOR),
            },
        )
        result_rows: list[dict[str, object]] = []
        visibility_rows: list[dict[str, object]] = []
        selection_rows: list[dict[str, object]] = []
        first_masked = next(
            name for name in scenario_names if assignment[name] == "registry_masked"
        )
        for name in scenario_names:
            masked = assignment[name] == "registry_masked"
            condition = "masked" if masked else "available"
            generated = [] if masked else ["helper"]
            if hide_on_available and not masked:
                generated = []
            if expose_on_masked and name == first_masked:
                generated = ["helper"]
            filtered = ["helper"] if not generated else []
            shortlisted = list(generated)
            result_row: dict[str, object] = {
                "name": name,
                "outcome_similarity": control_by_name[name]
                + (0.2 if not masked else 0.0),
                "similarity": control_by_name[name] + (0.2 if not masked else 0.0),
                "experimental_registry_condition": condition,
                "registry_assignment_id": assignment_id,
                "transient_retry_count": 0,
                "transient_retry_archives": [],
                "exception_type": None,
                "traceback": None,
                "outcome_evaluator_version": runner.PINNED_OUTCOME_EVALUATOR["version"],
                "outcome_evaluator_contract_sha256": runner.PINNED_OUTCOME_EVALUATOR[
                    "contract_sha256"
                ],
                "outcome_evaluator_source_sha256": runner.PINNED_OUTCOME_EVALUATOR[
                    "source_sha256"
                ],
            }
            if name == scenario_names[0] and retry_first:
                result_row["transient_retry_count"] = 1
                result_row["transient_retry_archives"] = ["attempt-1"]
            if name == scenario_names[0] and exception_first:
                result_row["exception_type"] = "RuntimeError"
                result_row["traceback"] = "Traceback ..."
            result_rows.append(result_row)
            visibility_rows.append(
                {
                    "scenario": name,
                    "base_tool_policy": runner.UPSTREAM_POLICY,
                    "experimental_registry_condition": condition,
                    "registry_assignment_id": assignment_id,
                    "retained_tools_loaded": ["helper"],
                    "filtered_out_generated_tools": filtered,
                    "shortlisted_generated_tools": shortlisted,
                    "tool_allow_list": [*generated, "native_tool"],
                    "available_tools": sorted([*generated, "native_tool"]),
                    "generated_tools": generated,
                }
            )
            selection_rows.append(
                {
                    "scenario": name,
                    "base_tool_policy": runner.UPSTREAM_POLICY,
                    "experimental_registry_condition": condition,
                    "registry_assignment_id": assignment_id,
                    "retained_tools_loaded": ["helper"],
                    "filtered_out_generated_tools": filtered,
                    "shortlisted_generated_tools": shortlisted,
                    "generated_tools_visible": generated,
                    "generated_tools_attempted": [],
                    "generated_tools_failed": [],
                    "generated_tools_called": [],
                    "selection_status": (
                        "registry_masked_by_random_assignment"
                        if masked
                        else "generated_tool_visible_not_called"
                    ),
                }
            )
        _write_json(
            run_dir / "result_summary.json", {"per_scenario_results": result_rows}
        )
        (run_dir / "scenario_tool_visibility.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in visibility_rows),
            encoding="utf-8",
        )
        (run_dir / "scenario_tool_selection.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in selection_rows),
            encoding="utf-8",
        )
        (run_dir / "sage_run_events.jsonl").write_text(
            json.dumps(
                {"event": "registry_load", "registry_assignment_id": assignment_id}
            )
            + "\n"
            + json.dumps(
                {
                    "event": "run_finished",
                    "registry_assignment_id": assignment_id,
                    "lifecycle_finalization_count": 0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return run_dir

    monkeypatch.setattr(runner, "resolve_scenarios", fake_resolve_scenarios)
    monkeypatch.setattr(runner, "run_sage_with_registry", fake_run)
    monkeypatch.setattr(runner, "analyze_registry_availability", fast_analyze)
    monkeypatch.setattr(
        runner,
        "_publication_environment_preflight",
        lambda: {"test_preflight": True},
    )
    monkeypatch.setattr(runner, "seal_phase_inputs", lambda **_kwargs: None)
    monkeypatch.setattr(
        runner, "PINNED_BENCHMARK_SHA256", runner._file_sha256(inputs["manifest_path"])
    )
    monkeypatch.setattr(
        runner,
        "PINNED_SCENARIO_ORDER_SHA256",
        runner._ordered_names_sha256(scenario_names),
    )
    return captured


def test_complete_h3_run_is_frozen_itt_and_writes_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    source_before = (inputs["registry_source"] / "registry_manifest.json").read_bytes()
    captured = _install_fake_execution(monkeypatch, inputs)
    run_root = tmp_path / "h3_run"

    result = runner.run_h3_registry_availability(
        benchmark_manifest_path=inputs["manifest_path"],
        assignment_path=inputs["assignment_path"],
        h2_control_path=inputs["control_path"],
        registry_source=inputs["registry_source"],
        pilot_manifest_path=inputs["pilot_manifest_path"],
        run_root=run_root,
    )

    assert result["status"] == "complete"
    assert result["scenario_count"] == 1032
    assert result["assignment_id"] == inputs["assignment"]["assignment_sha256"]
    assert result["integrity"]["passed"] is True
    assert result["integrity"]["complete_itt_roster"] is True
    assert result["integrity"]["identical_wrapper_and_native_inventory"] is True
    assert result["integrity"]["registry_copy_unchanged"] is True
    assert result["analysis"]["estimand"].startswith("intention_to_treat")
    assert result["analysis"]["counts"]["registry_available_scenarios"] == 520
    assert result["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert result["pilot_gate_outcome"] == "cleared"
    assert result["practical_effect_ge_0_05"] is True
    assert result["registry_available_mean"] > result["registry_masked_mean"]
    assert result["itt_mean_difference"] == result["itt_difference"]
    assert result["cluster_ci_95"] == result["itt_cluster_bootstrap_95_ci"]
    assert result["p_value"] == result["one_sided_randomization_p_value"]
    assert result["available_tasks"] == 520
    assert result["masked_tasks"] == 512
    assert result["stem_clusters"] == 129
    assert result["allocation"]["seed"] == 20260918
    assert result["allocation"]["sha256"] == result["assignment_id"]
    assert result["allocation_counts"]["registry_available_scenarios"] == 520
    assert result["integrity"]["transient_retry_report"]["total_retry_count"] == 0
    assert captured["config"].registry_dir == run_root / "frozen_registry"
    assert captured["config"].user == runner.DEFAULT_MODEL
    assert captured["config"].registry_dir != inputs["registry_source"]
    assert (
        inputs["registry_source"] / "registry_manifest.json"
    ).read_bytes() == source_before
    assert (run_root / runner.RESULT_FILENAME).is_file()
    assert (run_root / runner.ANALYSIS_FILENAME).is_file()
    assert (run_root / "inputs" / "h3_assignment.json").is_file()


def test_h3_fails_closed_when_a_masked_task_exposes_a_registry_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    _install_fake_execution(monkeypatch, inputs, expose_on_masked=True)
    run_root = tmp_path / "h3_bad_exposure"

    with pytest.raises(ValueError, match="Masked H3 task exposed"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=inputs["manifest_path"],
            assignment_path=inputs["assignment_path"],
            h2_control_path=inputs["control_path"],
            registry_source=inputs["registry_source"],
            pilot_manifest_path=inputs["pilot_manifest_path"],
            run_root=run_root,
        )

    failure = json.loads((run_root / runner.RESULT_FILENAME).read_text())
    assert failure["status"] == "failed_integrity"
    assert failure["integrity"]["passed"] is False
    assert "Masked H3 task exposed" in failure["error"]["message"]
    assert failure["provenance"]["registry_copy_at_failure"]["sha256"]


def test_h3_rejects_incomplete_benchmark_before_model_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    shortened = inputs["names"][:-1]
    _write_json(
        inputs["manifest_path"],
        {"splits": {"full_benchmark": [{"name": name} for name in shortened]}},
    )
    called = False

    def forbidden_run(*_args: object, **_kwargs: object) -> Path:
        nonlocal called
        called = True
        raise AssertionError("model execution must not begin")

    monkeypatch.setattr(runner, "run_sage_with_registry", forbidden_run)
    monkeypatch.setattr(
        runner,
        "_publication_environment_preflight",
        lambda: {"test_preflight": True},
    )
    monkeypatch.setattr(runner, "seal_phase_inputs", lambda **_kwargs: None)
    monkeypatch.setattr(
        runner, "PINNED_BENCHMARK_SHA256", runner._file_sha256(inputs["manifest_path"])
    )
    monkeypatch.setattr(
        runner,
        "PINNED_SCENARIO_ORDER_SHA256",
        runner._ordered_names_sha256(shortened),
    )
    run_root = tmp_path / "h3_incomplete"
    with pytest.raises(ValueError, match="1,032 unique"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=inputs["manifest_path"],
            assignment_path=inputs["assignment_path"],
            h2_control_path=inputs["control_path"],
            registry_source=inputs["registry_source"],
            pilot_manifest_path=inputs["pilot_manifest_path"],
            run_root=run_root,
        )
    assert called is False
    failure = json.loads((run_root / runner.RESULT_FILENAME).read_text())
    assert failure["status"] == "failed_integrity"
    assert failure["pilot_gate_label"] == "INTEGRITY_FAILURE"


def test_h3_retains_protocol_permitted_transient_retry_in_itt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    _install_fake_execution(monkeypatch, inputs, retry_first=True)
    result = runner.run_h3_registry_availability(
        benchmark_manifest_path=inputs["manifest_path"],
        assignment_path=inputs["assignment_path"],
        h2_control_path=inputs["control_path"],
        registry_source=inputs["registry_source"],
        pilot_manifest_path=inputs["pilot_manifest_path"],
        run_root=tmp_path / "h3_retry",
    )
    retry_report = result["integrity"]["transient_retry_report"]
    assert result["status"] == "complete"
    assert retry_report["policy_attempt_limit"] == 4
    assert retry_report["retried_scenario_count"] == 1
    assert retry_report["total_retry_count"] == 1
    assert retry_report["retry_archive_count"] == 1


def test_h3_final_task_exception_fails_integrity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    _install_fake_execution(monkeypatch, inputs, exception_first=True)
    run_root = tmp_path / "h3_exception"
    with pytest.raises(ValueError, match="ended with an exception"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=inputs["manifest_path"],
            assignment_path=inputs["assignment_path"],
            h2_control_path=inputs["control_path"],
            registry_source=inputs["registry_source"],
            pilot_manifest_path=inputs["pilot_manifest_path"],
            run_root=run_root,
        )
    failure = json.loads((run_root / runner.RESULT_FILENAME).read_text())
    assert failure["pilot_gate_label"] == "INTEGRITY_FAILURE"


def test_h3_refuses_to_overwrite_an_existing_run_root(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="refusing to overwrite"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=tmp_path / "unused-manifest",
            assignment_path=tmp_path / "unused-assignment",
            h2_control_path=tmp_path / "unused-control",
            registry_source=tmp_path / "unused-registry",
            pilot_manifest_path=tmp_path / "unused-pilot-manifest",
            run_root=existing,
        )


def test_h3_refuses_run_root_inside_registry_source(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    registry.mkdir()
    with pytest.raises(ValueError, match="may not be inside"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=tmp_path / "unused-manifest",
            assignment_path=tmp_path / "unused-assignment",
            h2_control_path=tmp_path / "unused-control",
            registry_source=registry,
            pilot_manifest_path=tmp_path / "unused-pilot-manifest",
            run_root=registry / "nested-run",
        )


def test_h3_fails_closed_when_available_arm_receives_no_generated_exposure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    _install_fake_execution(monkeypatch, inputs, hide_on_available=True)
    run_root = tmp_path / "h3_no_treatment_delivery"

    with pytest.raises(ValueError, match="no generated-tool exposure"):
        runner.run_h3_registry_availability(
            benchmark_manifest_path=inputs["manifest_path"],
            assignment_path=inputs["assignment_path"],
            h2_control_path=inputs["control_path"],
            registry_source=inputs["registry_source"],
            pilot_manifest_path=inputs["pilot_manifest_path"],
            run_root=run_root,
        )

    failure = json.loads((run_root / runner.RESULT_FILENAME).read_text())
    assert failure["status"] == "failed_integrity"
    assert "no generated-tool exposure" in failure["error"]["message"]


def test_dashboard_projection_keeps_pilot_gate_and_practical_flag_separate() -> None:
    fields = runner._dashboard_result_fields(
        {
            "outcomes": {
                "registry_available_mean": 0.51,
                "registry_masked_mean": 0.49,
                "absolute_difference": 0.02,
            },
            "uncertainty": {
                "restricted_randomization_one_sided_p_value": 0.03,
                "stem_cluster_percentile_bootstrap_95_ci": [0.001, 0.039],
            },
            "counts": {
                "stems": 129,
                "registry_available_scenarios": 520,
                "registry_masked_scenarios": 512,
            },
        },
        integrity_passed=True,
        assignment_manifest={"seed": 7, "assignment_sha256": "a" * 64},
    )
    assert fields["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert fields["pilot_gate_passed"] is True
    assert fields["practical_effect_ge_0_05"] is False

    not_cleared = runner._dashboard_result_fields(
        {
            "outcomes": {
                "registry_available_mean": 0.50,
                "registry_masked_mean": 0.49,
                "absolute_difference": 0.01,
            },
            "uncertainty": {
                "restricted_randomization_one_sided_p_value": 0.08,
                "stem_cluster_percentile_bootstrap_95_ci": [-0.01, 0.03],
            },
            "counts": {},
        },
        integrity_passed=True,
    )
    assert not_cleared["pilot_gate_label"] == "PILOT_THRESHOLD_NOT_CLEARED"
    assert not_cleared["pilot_gate_outcome"] == "not_cleared"
