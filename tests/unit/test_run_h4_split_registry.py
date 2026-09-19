from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import run_h4_split_registry as runner
from scripts.research.h3_registry_ablation import ROBUSTNESS_SUFFIXES
from scripts.research.h4_split_registry import PILOT_THRESHOLD_CLEARED


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


def _append_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _benchmark(tmp_path: Path) -> tuple[Path, list[str]]:
    names = [
        f"task_{stem_index:03d}{suffix}"
        for stem_index in range(129)
        for suffix in ("", *ROBUSTNESS_SUFFIXES)
    ]
    path = tmp_path / "benchmark.json"
    _write_json(path, {"splits": {"full_benchmark": [{"name": n} for n in names]}})
    return path, names


def _pilot_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "pilot_manifest.json"
    _write_json(path, {"schema_version": 1, "pilot_id": "test-pilot"})
    return path


def _install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    run_root: Path,
    *,
    expose_masked: bool = False,
    nonempty_discovery_repair_state: bool = False,
) -> list[runner.SageRunConfig]:
    configs: list[runner.SageRunConfig] = []
    original_analyze = runner.analyze_paired_held_out

    def fast_analyze(*args: object, **kwargs: Any) -> dict[str, Any]:
        kwargs["bootstrap_iterations"] = 100
        return original_analyze(*args, **kwargs)

    def fake_resolve_scenarios(**kwargs: object) -> dict[str, _FakeScenario]:
        requested = list(kwargs["desired_scenario_names"])
        return {str(name): _FakeScenario() for name in requested}

    def fake_run(
        config: runner.SageRunConfig,
        *,
        generator: object,
        scenarios: dict[str, _FakeScenario],
    ) -> Path:
        assert (run_root / runner.DESIGN_FILENAME).is_file()
        assert list(scenarios) == list(config.scenario_names)
        assert runner.os.environ["SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS"] == "4"
        configs.append(config)
        config.output_dir.mkdir(parents=True)
        _write_json(
            config.output_dir / "sage_ts_run_manifest.json",
            {
                "agent": config.agent,
                "user": config.user,
                "agent_runtime": config.agent_runtime,
                "base_tool_policy": config.base_tool_policy,
                "processes": 1,
                "run_type": config.run_type,
                "scenario_names": list(config.scenario_names),
                "resume_from_dir": None,
                "resume_completed_limit": None,
                "fail_on_scenario_transform_error": True,
                "actor_selection_mode": "policy",
                "outcome_evaluator": dict(runner.PINNED_OUTCOME_EVALUATOR),
                "online_feedback_evaluator_version": "test",
                "timezone": "America/New_York",
                "git_sha": "test-sha",
            },
        )
        run_dir = config.output_dir / "run"
        run_dir.mkdir()

        if config.run_type == "h4_randomized_discovery":
            assert generator is not None
            assert config.online_feedback_mode == runner.ONLINE_FEEDBACK_ACTOR_VISIBLE
            assert not config.registry_masked_scenarios
            _write_json(config.registry_dir / "registry_manifest.json", {"tools": {}})
            _write_json(
                run_dir / "result_summary.json",
                {
                    "per_scenario_results": [
                        {
                            "name": name,
                            "outcome_similarity": 0.4,
                            "similarity": 0.4,
                            "exception_type": None,
                            "traceback": None,
                            "transient_retry_count": 0,
                            "transient_retry_archives": [],
                            "outcome_evaluator_version": (
                                runner.PINNED_OUTCOME_EVALUATOR["version"]
                            ),
                            "outcome_evaluator_contract_sha256": (
                                runner.PINNED_OUTCOME_EVALUATOR["contract_sha256"]
                            ),
                            "outcome_evaluator_source_sha256": (
                                runner.PINNED_OUTCOME_EVALUATOR["source_sha256"]
                            ),
                        }
                        for name in config.scenario_names
                    ]
                },
            )
            _append_jsonl(
                run_dir / "sage_run_events.jsonl",
                [
                    {
                        "event": "run_finished",
                        "online_feedback_mode": runner.ONLINE_FEEDBACK_ACTOR_VISIBLE,
                    }
                ],
            )
            _append_jsonl(
                run_dir / "online_birth_feedback_receipts.jsonl",
                [
                    {
                        "scenario": name,
                        "online_feedback_mode": runner.ONLINE_FEEDBACK_ACTOR_VISIBLE,
                        "online_birth_outcome_source": "withheld_actor_visible_only",
                        "score_fields_with_values": [],
                        "evaluator_private_fields_present": [],
                        "visible_message_count": 2,
                    }
                    for name in config.scenario_names
                ],
            )
            _write_json(
                run_dir / runner.POST_DEPLOYMENT_REPAIR_STATE_FILENAME,
                {
                    "schema_version": 1,
                    "pending_repair_requests": (
                        [{"request_id": "unexpected"}]
                        if nonempty_discovery_repair_state
                        else []
                    ),
                    "handled_repair_request_ids": [],
                    "canary_state_by_tool": {},
                    "repair_transactions_by_tool": {},
                    "last_completed_count": 0,
                },
            )
            return run_dir

        assert generator is None
        masked = bool(config.registry_masked_scenarios)
        expected_condition = "masked" if masked else "available"
        result_score = 0.50 if masked else 0.70
        result_rows: list[dict[str, object]] = []
        visibility_rows: list[dict[str, object]] = []
        selection_rows: list[dict[str, object]] = []
        for index, name in enumerate(config.scenario_names):
            generated = [] if masked else ["helper"]
            if masked and expose_masked and index == 0:
                generated = ["helper"]
            filtered = ["helper"] if not generated else []
            shortlisted = list(generated)
            result_rows.append(
                {
                    "name": name,
                    "outcome_similarity": result_score,
                    "similarity": result_score,
                    "exception_type": None,
                    "traceback": None,
                    "transient_retry_count": 0,
                    "transient_retry_archives": [],
                    "experimental_registry_condition": expected_condition,
                    "registry_assignment_id": config.registry_assignment_id,
                    "outcome_evaluator_version": runner.PINNED_OUTCOME_EVALUATOR[
                        "version"
                    ],
                    "outcome_evaluator_contract_sha256": (
                        runner.PINNED_OUTCOME_EVALUATOR["contract_sha256"]
                    ),
                    "outcome_evaluator_source_sha256": (
                        runner.PINNED_OUTCOME_EVALUATOR["source_sha256"]
                    ),
                }
            )
            visibility_rows.append(
                {
                    "scenario": name,
                    "base_tool_policy": runner.UPSTREAM_POLICY,
                    "experimental_registry_condition": expected_condition,
                    "registry_assignment_id": config.registry_assignment_id,
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
                    "experimental_registry_condition": expected_condition,
                    "registry_assignment_id": config.registry_assignment_id,
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
        _append_jsonl(run_dir / "scenario_tool_visibility.jsonl", visibility_rows)
        _append_jsonl(run_dir / "scenario_tool_selection.jsonl", selection_rows)
        _append_jsonl(
            run_dir / "sage_run_events.jsonl",
            [
                {
                    "event": "run_finished",
                    "registry_assignment_id": config.registry_assignment_id,
                    "lifecycle_finalization_count": 0,
                }
            ],
        )
        return run_dir

    monkeypatch.setattr(runner, "resolve_scenarios", fake_resolve_scenarios)
    monkeypatch.setattr(runner, "run_sage_with_registry", fake_run)
    monkeypatch.setattr(runner, "OpenAIChatAdapter", lambda **_kwargs: object())
    monkeypatch.setattr(runner, "ToolGenerator", lambda **_kwargs: object())
    monkeypatch.setattr(
        runner,
        "_publication_environment_preflight",
        lambda: {"test_preflight": True},
    )
    monkeypatch.setattr(runner, "seal_phase_inputs", lambda **_kwargs: None)
    monkeypatch.setattr(
        runner,
        "bind_h4_frozen_registry",
        lambda **kwargs: {
            "h4_frozen_registry": {
                "path": str(Path(kwargs["registry_dir"]).resolve()),
                "content_sha256": "c" * 64,
                "manifest_sha256": runner._file_sha256(
                    Path(kwargs["registry_dir"]) / "registry_manifest.json"
                ),
                "design_sha256": kwargs["design_sha256"],
                "discovery_run_dir": str(Path(kwargs["discovery_run_dir"]).resolve()),
            }
        },
    )
    monkeypatch.setattr(runner, "analyze_paired_held_out", fast_analyze)

    def fake_paired_arms(**kwargs: Any) -> tuple[Path, Path, dict[str, Any]]:
        scenario_names = tuple(kwargs["scenario_names"])
        scenarios = fake_resolve_scenarios(desired_scenario_names=list(scenario_names))
        available = runner._run_frozen_arm(
            scenario_names=scenario_names,
            scenarios=scenarios,
            output_dir=kwargs["run_root"] / "held_out_available",
            registry_dir=kwargs["available_registry"],
            benchmark_manifest_path=kwargs["benchmark_manifest_path"],
            assignment_id=kwargs["assignment_id"],
            masked=False,
            agent=kwargs["agent"],
            user=kwargs["user"],
        )
        masked = runner._run_frozen_arm(
            scenario_names=scenario_names,
            scenarios=scenarios,
            output_dir=kwargs["run_root"] / "held_out_masked",
            registry_dir=kwargs["masked_registry"],
            benchmark_manifest_path=kwargs["benchmark_manifest_path"],
            assignment_id=kwargs["assignment_id"],
            masked=True,
            agent=kwargs["agent"],
            user=kwargs["user"],
        )
        return (
            available,
            masked,
            {
                "mode": "unit_test_concurrent_process_receipt",
                "arms": {
                    "available": {"process_pid": 101},
                    "masked": {"process_pid": 202},
                },
                "overlap_monotonic_ns": 1,
                "overlap_seconds": 1e-9,
            },
        )

    monkeypatch.setattr(runner, "_run_paired_frozen_arms", fake_paired_arms)
    monkeypatch.setattr(
        runner,
        "_active_registry_roster",
        lambda _path: {
            "all": ["helper"],
            "active": ["helper"],
            "active_count": 1,
            "all_count": 1,
            "all_active_claim_grade": True,
        },
    )
    return configs


def _pin_test_benchmark(monkeypatch: pytest.MonkeyPatch, manifest: Path) -> None:
    monkeypatch.setattr(
        runner, "PINNED_BENCHMARK_SHA256", runner._file_sha256(manifest)
    )


def test_complete_h4_run_seals_design_freezes_registry_and_analyzes_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, _ = _benchmark(tmp_path)
    _pin_test_benchmark(monkeypatch, manifest)
    run_root = tmp_path / "h4_run"
    configs = _install_fake_runtime(monkeypatch, run_root)

    result = runner.run_h4_split_registry(
        benchmark_manifest_path=manifest,
        pilot_manifest_path=_pilot_manifest(tmp_path),
        run_root=run_root,
    )

    assert result["status"] == "complete"
    assert result["status_label"] == PILOT_THRESHOLD_CLEARED
    assert result["pilot_not_confirmatory"] is True
    assert result["design_sealed_before_model_execution"] is True
    assert result["execution_stage"] == "complete"
    assert result["h4_frozen_registry_binding"]["content_sha256"] == "c" * 64
    assert result["integrity"]["passed"] is True
    assert result["integrity"]["source_disjoint_stems"] is True
    assert result["integrity"]["immutable_equal_registry_copies"] is True
    assert result["integrity"]["masked_zero_generated_exposure"] is True
    assert result["integrity"]["masked_zero_generated_calls"] is True
    assert result["integrity"]["zero_runtime_exceptions"] is True
    assert result["analysis"]["counts"]["paired_scenarios"] == 520
    assert result["registry"]["started_empty"] is True
    assert [len(config.scenario_names) for config in configs] == [512, 520, 520]
    assert configs[0].online_feedback_mode == runner.ONLINE_FEEDBACK_ACTOR_VISIBLE
    assert configs[0].failure_memory_path is None
    assert configs[1].registry_masked_scenarios == frozenset()
    assert configs[2].registry_masked_scenarios == frozenset(configs[2].scenario_names)
    assert configs[1].scenario_names == configs[2].scenario_names
    assert configs[1].agent == configs[2].agent
    assert configs[1].agent_runtime == configs[2].agent_runtime
    assert configs[1].base_tool_policy == configs[2].base_tool_policy
    assert (run_root / runner.RESULT_FILENAME).is_file()
    assert (run_root / runner.DESIGN_FILENAME).is_file()
    assert (run_root / runner.ANALYSIS_FILENAME).is_file()


def test_h4_fails_closed_if_masked_task_exposes_a_generated_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, _ = _benchmark(tmp_path)
    _pin_test_benchmark(monkeypatch, manifest)
    run_root = tmp_path / "h4_bad_mask"
    _install_fake_runtime(monkeypatch, run_root, expose_masked=True)

    with pytest.raises(ValueError, match="Masked H4 task exposed"):
        runner.run_h4_split_registry(
            benchmark_manifest_path=manifest,
            pilot_manifest_path=_pilot_manifest(tmp_path),
            run_root=run_root,
        )

    failure = json.loads((run_root / runner.RESULT_FILENAME).read_text())
    assert failure["status"] == "failed_integrity"
    assert failure["status_label"] == runner.INTEGRITY_FAILURE
    assert failure["integrity"]["passed"] is False


def test_h4_allows_only_empty_disabled_discovery_repair_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, _ = _benchmark(tmp_path)
    _pin_test_benchmark(monkeypatch, manifest)
    run_root = tmp_path / "h4_nonempty_repair_state"
    _install_fake_runtime(
        monkeypatch,
        run_root,
        nonempty_discovery_repair_state=True,
    )

    with pytest.raises(ValueError, match="nonempty repair state"):
        runner.run_h4_split_registry(
            benchmark_manifest_path=manifest,
            pilot_manifest_path=_pilot_manifest(tmp_path),
            run_root=run_root,
        )


def test_h4_refuses_to_overwrite_an_existing_run_root(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="refusing to overwrite"):
        runner.run_h4_split_registry(
            benchmark_manifest_path=tmp_path / "unused.json",
            pilot_manifest_path=tmp_path / "unused-pilot-manifest.json",
            run_root=existing,
        )


def test_h4_result_roster_keeps_transient_retries_in_intention_to_treat() -> None:
    rows = [
        {
            "name": "task_a",
            "similarity": 0.5,
            "experimental_registry_condition": "available",
            "registry_assignment_id": "assignment",
            "transient_retry_count": 2,
            "transient_retry_archives": ["attempt_1", "attempt_2"],
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
    ]

    indexed, exception_count, retry_count = runner._result_roster_validation(
        rows,
        expected_order=("task_a",),
        condition="available",
        assignment_id="assignment",
        label="test arm",
    )

    assert tuple(indexed) == ("task_a",)
    assert exception_count == 0
    assert retry_count == 2
