# mypy: ignore-errors
import json
import os
import sys

import pytest

from scripts.run_sage_protocol import (
    DIAGNOSTIC_FORCE_ENV_VARS,
    SAGE_POLICY_AUTO,
    SAGE_POLICY_NONE,
    SAGE_POLICY_SELF_EVOLVING_PRAXIS,
    SELF_EVOLVING_PRAXIS_ENV_DEFAULTS,
    _apply_sage_policy_preset,
    _candidate_arm_name,
    _candidate_arm_root,
    _candidate_generation_enabled,
    _generation_enabled_by_default,
    _parallel_arm_execution_record,
    _protocol_gate_decision,
    _read_arm_status,
    _resolve_sage_policy_preset,
    _restore_registry_after_failed_gate,
    _snapshot_registry_for_gate,
    _stop_parallel_process,
    _validate_uncached_result_rows,
    _write_arm_status,
)
from scripts.run_sage_protocol import (
    main as run_protocol_main,
)


@pytest.fixture(autouse=True)
def _restore_sage_environment() -> None:
    tracked_keys = set(SELF_EVOLVING_PRAXIS_ENV_DEFAULTS)
    before = {key: os.environ.get(key) for key in tracked_keys}
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_discovery_manifest_enables_generation_in_transfer_mode() -> None:
    assert (
        _generation_enabled_by_default("transfer_40", "sage_diverse_cluster_discovery")
        is True
    )


def test_transfer_mode_stays_frozen_for_non_discovery_manifest() -> None:
    assert _generation_enabled_by_default("transfer_40", "frozen_transfer") is False


def test_mechanism_mode_enables_generation_by_default() -> None:
    assert _generation_enabled_by_default("mechanism_40", "anything") is True


def test_auto_actor_selection_uses_explicit_third_arm_label(tmp_path) -> None:
    assert _candidate_arm_name("policy") == "candidate"
    assert _candidate_arm_name("auto") == "sage_auto_selection"
    assert _candidate_arm_root(tmp_path, "policy") == tmp_path / "candidate"
    assert _candidate_arm_root(tmp_path, "auto") == tmp_path / "sage_auto_selection"


def test_arm_status_updates_are_atomic_and_preserve_process_start(tmp_path) -> None:
    _write_arm_status(
        tmp_path,
        "control",
        status="starting",
        process_pid=123,
        completed_count=0,
    )
    started = _read_arm_status(tmp_path, "control")
    _write_arm_status(
        tmp_path,
        "control",
        status="complete",
        process_pid=123,
        completed_count=2,
    )
    completed = _read_arm_status(tmp_path, "control")

    assert completed["process_pid"] == 123
    assert completed["started_at"] == started["started_at"]
    assert completed["started_monotonic_ns"] == started["started_monotonic_ns"]
    assert completed["completed_monotonic_ns"] > completed["started_monotonic_ns"]
    assert not list(tmp_path.glob(".*.tmp"))


def test_arm_status_reader_tolerates_interrupted_or_malformed_write(tmp_path) -> None:
    (tmp_path / "control_arm_status.json").write_text("{", encoding="utf-8")

    assert _read_arm_status(tmp_path, "control") == {}


def test_parallel_execution_record_requires_positive_process_overlap(tmp_path) -> None:
    statuses = {
        "control": (101, 1_000, 3_000),
        "candidate": (102, 2_000, 4_000),
    }
    for arm, (pid, started, completed) in statuses.items():
        (tmp_path / f"{arm}_arm_status.json").write_text(
            json.dumps(
                {
                    "arm": arm,
                    "status": "complete",
                    "process_pid": pid,
                    "started_at": "start",
                    "completed_at": "complete",
                    "started_monotonic_ns": started,
                    "completed_monotonic_ns": completed,
                }
            ),
            encoding="utf-8",
        )

    record = _parallel_arm_execution_record(tmp_path)

    assert record["positive_overlap_asserted"] is True
    assert record["overlap_monotonic_ns"] == 1_000


def test_parallel_process_cleanup_escalates_from_terminate_to_kill() -> None:
    class StubbornProcess:
        def __init__(self) -> None:
            self.alive = True
            self.calls: list[str] = []

        def is_alive(self) -> bool:
            return self.alive

        def terminate(self) -> None:
            self.calls.append("terminate")

        def join(self, timeout: float) -> None:
            self.calls.append(f"join:{timeout}")

        def kill(self) -> None:
            self.calls.append("kill")
            self.alive = False

    process = StubbornProcess()

    _stop_parallel_process(process, timeout_seconds=0.01)

    assert process.calls == ["terminate", "join:0.01", "kill", "join:0.01"]


def test_inventory_replay_suppresses_arm_specific_generation(tmp_path) -> None:
    assert _candidate_generation_enabled(True, None) is True
    assert _candidate_generation_enabled(False, None) is False
    assert _candidate_generation_enabled(True, tmp_path / "authority") is False


def test_failed_gate_restores_registry_and_lifecycle_bytes(tmp_path) -> None:
    run_root = tmp_path / "run"
    registry = tmp_path / "registry"
    registry.mkdir()
    original_manifest = b'{"tools":{"before":{}}}\n'
    original_lifecycle = b'{"tool_lifecycle":{"before":{}}}\n'
    (registry / "registry_manifest.json").write_bytes(original_manifest)
    (registry / "tool_lifecycle.json").write_bytes(original_lifecycle)

    snapshot = _snapshot_registry_for_gate(run_root, registry)
    (registry / "registry_manifest.json").write_text(
        '{"tools":{"after":{}}}\n', encoding="utf-8"
    )
    (registry / "tool_lifecycle.json").write_text(
        '{"tool_lifecycle":{"after":{}}}\n', encoding="utf-8"
    )

    restored = _restore_registry_after_failed_gate(
        run_root=run_root,
        registry_dir=registry,
        snapshot=snapshot,
    )

    assert (registry / "registry_manifest.json").read_bytes() == original_manifest
    assert (registry / "tool_lifecycle.json").read_bytes() == original_lifecycle
    assert restored["files"]["registry_manifest.json"]["failed_snapshot_path"]
    assert restored["files"]["tool_lifecycle.json"]["failed_snapshot_path"]


def test_protocol_cli_rejects_unknown_actor_selection_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sage_protocol.py",
            "--mode",
            "mechanism_40",
            "--manifest",
            "unused.json",
            "--actor-selection-mode",
            "unsupported",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_protocol_main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "--actor-selection-mode",
                "auto",
                "--inventory-authority-capture-dir",
                "authority",
            ],
            "capture-dir requires --actor-selection-mode policy",
        ),
        (
            ["--inventory-authority-replay-dir", "authority"],
            "replay-dir requires --actor-selection-mode auto",
        ),
        (
            [
                "--inventory-authority-capture-dir",
                "authority",
                "--resume-run-root",
                "prior-run",
            ],
            "capture/replay forbids --resume-run-root",
        ),
        (
            ["--inventory-authority-capture-dir", "authority"],
            "capture/replay requires --freeze-toolsandbox-clock",
        ),
    ],
)
def test_protocol_cli_rejects_invalid_inventory_authority_pairing(
    monkeypatch,
    arguments,
    message,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sage_protocol.py",
            "--mode",
            "mechanism_40",
            "--manifest",
            "unused.json",
            *arguments,
        ],
    )

    with pytest.raises(SystemExit, match=message):
        run_protocol_main()


def test_auto_sage_policy_uses_praxis_for_generation_enabled_runs() -> None:
    assert (
        _resolve_sage_policy_preset(SAGE_POLICY_AUTO, generation_enabled=True)
        == SAGE_POLICY_SELF_EVOLVING_PRAXIS
    )


def test_auto_sage_policy_stays_none_for_frozen_runs() -> None:
    assert (
        _resolve_sage_policy_preset(SAGE_POLICY_AUTO, generation_enabled=False)
        == SAGE_POLICY_NONE
    )


def test_explicit_sage_policy_override_is_preserved() -> None:
    assert (
        _resolve_sage_policy_preset(SAGE_POLICY_NONE, generation_enabled=True)
        == SAGE_POLICY_NONE
    )


def test_self_evolving_praxis_policy_sets_tool_generation_runtime_defaults(
    monkeypatch,
) -> None:
    for key in SELF_EVOLVING_PRAXIS_ENV_DEFAULTS:
        monkeypatch.delenv(key, raising=False)

    applied = _apply_sage_policy_preset(SAGE_POLICY_SELF_EVOLVING_PRAXIS)

    assert applied
    for key, expected in SELF_EVOLVING_PRAXIS_ENV_DEFAULTS.items():
        assert applied[key] == {"value": expected, "source": "preset_default"}


def test_self_evolving_praxis_policy_preserves_explicit_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS", "240")

    applied = _apply_sage_policy_preset(SAGE_POLICY_SELF_EVOLVING_PRAXIS)

    assert applied["SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS"] == {
        "value": "240",
        "source": "preexisting_environment",
    }


def test_protocol_gate_requires_outcome_values_even_when_canonical_is_positive() -> (
    None
):
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": 1.0,
            "mean_outcome_similarity_delta": None,
            "exact_success_delta": 100,
            "gain_count": 100,
            "regression_count": 0,
            "outcome_gain_count": 0,
            "outcome_regression_count": 0,
            "outcome_scenario_count": 0,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 10,
                "generated_tool_called_scenarios": 40,
            },
        },
        scenario_count=40,
    )

    assert passed is False
    assert "outcome_score_unavailable" in reasons
    assert "outcome_score_coverage_incomplete" in reasons
    assert all("canonical" not in reason for reason in reasons)


@pytest.mark.parametrize(
    ("canonical_delta", "exact_delta", "canonical_gains", "canonical_regressions"),
    [(-1.0, -100, 0, 100), (1.0, 100, 100, 0)],
)
def test_protocol_gate_is_invariant_to_canonical_and_exact_metrics(
    canonical_delta: float,
    exact_delta: int,
    canonical_gains: int,
    canonical_regressions: int,
) -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": canonical_delta,
            "exact_success_delta": exact_delta,
            "gain_count": canonical_gains,
            "regression_count": canonical_regressions,
            "mean_outcome_similarity_delta": 0.20,
            "outcome_gain_count": 20,
            "outcome_regression_count": 1,
            "outcome_scenario_count": 40,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 1,
                "generated_tool_called_scenarios": 20,
            },
        },
        scenario_count=40,
    )

    assert passed is True
    assert reasons == []


def test_protocol_gate_rejects_negative_outcome_even_when_canonical_improves() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": 0.05,
            "mean_outcome_similarity_delta": -0.03,
            "exact_success_delta": 1,
            "gain_count": 5,
            "regression_count": 1,
            "outcome_gain_count": 1,
            "outcome_regression_count": 4,
            "outcome_scenario_count": 20,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 1,
                "generated_tool_called_scenarios": 3,
            },
        },
        scenario_count=20,
    )

    assert passed is False
    assert "non_positive_outcome_delta" in reasons


def test_protocol_gate_rejects_partial_outcome_coverage() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_outcome_similarity_delta": 0.20,
            "outcome_gain_count": 19,
            "outcome_regression_count": 1,
            "outcome_scenario_count": 39,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 1,
                "generated_tool_called_scenarios": 20,
            },
        },
        scenario_count=40,
    )

    assert passed is False
    assert "outcome_score_coverage_incomplete" in reasons


def test_protocol_gate_accepts_positive_discovery_with_helper_activity() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": -1.0,
            "mean_outcome_similarity_delta": 0.20,
            "exact_success_delta": -1,
            "gain_count": 0,
            "regression_count": 10,
            "outcome_gain_count": 5,
            "outcome_regression_count": 2,
            "outcome_scenario_count": 12,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 1,
                "generated_tool_called_scenarios": 3,
            },
        },
        scenario_count=12,
    )

    assert passed is True
    assert reasons == []


def test_protocol_gate_is_invariant_to_helper_activity() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_outcome_similarity_delta": 0.20,
            "outcome_gain_count": 5,
            "outcome_regression_count": 2,
            "outcome_scenario_count": 12,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 0,
                "generated_tool_called_scenarios": 2,
            },
        },
        scenario_count=12,
    )

    assert passed is True
    assert reasons == []


def test_protocol_confirmation_gate_is_invariant_to_helper_call_share() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_outcome_similarity_delta": 0.20,
            "outcome_gain_count": 20,
            "outcome_regression_count": 1,
            "outcome_scenario_count": 40,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 0,
                "generated_tool_called_scenarios": 0,
            },
        },
        scenario_count=40,
    )

    assert passed is True
    assert reasons == []


def test_failed_gate_restores_existing_registry_manifest(tmp_path) -> None:
    run_root = tmp_path / "run"
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    manifest = registry_dir / "registry_manifest.json"
    manifest.write_text('{"tools": {"kept": {}}}\n')

    snapshot = _snapshot_registry_for_gate(run_root, registry_dir)
    manifest.write_text('{"tools": {"kept": {}, "failed": {}}}\n')

    result = _restore_registry_after_failed_gate(
        run_root=run_root,
        registry_dir=registry_dir,
        snapshot=snapshot,
    )

    assert result["restored"] is True
    assert manifest.read_text() == '{"tools": {"kept": {}}}\n'
    assert (run_root / "registry_gate" / "registry_manifest_failed_gate.json").exists()


def test_failed_gate_removes_new_registry_manifest_when_none_existed(tmp_path) -> None:
    run_root = tmp_path / "run"
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()

    snapshot = _snapshot_registry_for_gate(run_root, registry_dir)
    manifest = registry_dir / "registry_manifest.json"
    manifest.write_text('{"tools": {"failed": {}}}\n')

    result = _restore_registry_after_failed_gate(
        run_root=run_root,
        registry_dir=registry_dir,
        snapshot=snapshot,
    )

    assert result["restored"] is True
    assert not manifest.exists()
    assert (run_root / "registry_gate" / "registry_manifest_failed_gate.json").exists()


def test_strict_fresh_rows_require_exact_uncached_task_mapping(tmp_path) -> None:
    run_dir = tmp_path / "control"
    run_dir.mkdir()
    rows = [
        {
            "name": "task_a",
            "similarity": 0.25,
            "outcome_similarity": 0.5,
            "llm_cached_call_count": 0,
        },
        {
            "name": "task_b",
            "similarity": 1.0,
            "outcome_similarity": 1.0,
            "llm_cached_call_count": 0,
        },
    ]
    (run_dir / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
    )

    mapped = _validate_uncached_result_rows(
        run_dir,
        expected_scenarios=("task_a", "task_b"),
        arm="control",
        require_complete=True,
    )

    assert list(mapped) == ["task_a", "task_b"]
    assert mapped["task_a"]["outcome_similarity"] == 0.5


def test_strict_publication_mode_rejects_every_partial_resume(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sage_protocol.py",
            "--mode",
            "full_benchmark",
            "--manifest",
            "unused.json",
            "--require-fresh-control",
            "--parallel-arms",
            "--resume-run-root",
            "old-run",
        ],
    )

    with pytest.raises(SystemExit, match="forbids --resume-run-root"):
        run_protocol_main()


def test_strict_publication_mode_requires_concurrent_arms(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sage_protocol.py",
            "--mode",
            "full_benchmark",
            "--manifest",
            "unused.json",
            "--require-fresh-control",
        ],
    )

    with pytest.raises(SystemExit, match="requires --parallel-arms"):
        run_protocol_main()


@pytest.mark.parametrize("force_name", DIAGNOSTIC_FORCE_ENV_VARS)
def test_strict_publication_mode_rejects_diagnostic_force_environment(
    monkeypatch,
    force_name,
) -> None:
    monkeypatch.setenv(force_name, "forced_tool")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sage_protocol.py",
            "--mode",
            "online_build_full",
            "--manifest",
            "unused.json",
            "--require-fresh-control",
            "--parallel-arms",
            "--diagnostic-force-allowed",
        ],
    )

    with pytest.raises(SystemExit, match="forbidden during a strict publication"):
        run_protocol_main()


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"name": "task_a"}, "Duplicate control result"),
        (
            {
                "name": "task_b",
                "control_cache_source": "cached",
            },
            "cache sourced",
        ),
        (
            {"name": "task_b", "llm_cached_call_count": 1},
            "repository whole-response replay",
        ),
    ],
)
def test_strict_fresh_rows_reject_cache_or_duplicates(
    tmp_path,
    mutation,
    match,
) -> None:
    run_dir = tmp_path / "control"
    run_dir.mkdir()
    first = {
        "name": "task_a",
        "similarity": 0.0,
        "llm_cached_call_count": 0,
    }
    second = {
        "name": "task_b",
        "similarity": 1.0,
        "llm_cached_call_count": 0,
    }
    second.update(mutation)
    (run_dir / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": [first, second]}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=match):
        _validate_uncached_result_rows(
            run_dir,
            expected_scenarios=("task_a", "task_b"),
            arm="control",
            require_complete=True,
        )
