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
    _generation_enabled_by_default,
    _protocol_gate_decision,
    _resolve_sage_policy_preset,
    _restore_registry_after_failed_gate,
    _route_mismatch_qualified,
    _snapshot_registry_for_gate,
    _validate_uncached_result_rows,
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


def test_protocol_gate_rejects_non_negative_mean_without_helper_value() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": 0.0,
            "exact_success_delta": 0,
            "gain_count": 1,
            "regression_count": 1,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 0,
                "generated_tool_called_scenarios": 0,
            },
        },
        scenario_count=12,
    )

    assert passed is False
    assert "non_positive_canonical_delta" in reasons
    assert "gains_do_not_exceed_regressions" in reasons


def test_protocol_gate_accepts_outcome_success_with_canonical_route_mismatch() -> None:
    comparison = {
        "mean_similarity_delta": -0.02,
        "mean_outcome_similarity_delta": 0.08,
        "exact_success_delta": 0,
        "gain_count": 1,
        "regression_count": 3,
        "outcome_gain_count": 5,
        "outcome_regression_count": 2,
        "runtime_exception_count": 0,
        "candidate": {
            "accepted_tool_count": 1,
            "generated_tool_called_scenarios": 3,
        },
    }

    passed, reasons = _protocol_gate_decision(comparison, scenario_count=20)

    assert _route_mismatch_qualified(comparison) is True
    assert passed is True
    assert reasons == []


def test_strict_publication_gate_ignores_canonical_and_exact_metrics() -> None:
    comparison = {
        "mean_similarity_delta": -1.0,
        "mean_outcome_similarity_delta": 0.20,
        "exact_success_delta": -100,
        "gain_count": 0,
        "regression_count": 100,
        "outcome_gain_count": 20,
        "outcome_regression_count": 1,
        "runtime_exception_count": 0,
        "candidate": {
            "accepted_tool_count": 1,
            "generated_tool_called_scenarios": 20,
        },
    }

    passed, reasons = _protocol_gate_decision(
        comparison,
        scenario_count=40,
        outcome_only=True,
    )

    assert passed is True
    assert reasons == []


def test_strict_publication_gate_fails_when_outcome_is_unavailable() -> None:
    comparison = {
        "mean_similarity_delta": 1.0,
        "mean_outcome_similarity_delta": None,
        "exact_success_delta": 100,
        "gain_count": 100,
        "regression_count": 0,
        "outcome_gain_count": 0,
        "outcome_regression_count": 0,
        "runtime_exception_count": 0,
        "candidate": {
            "accepted_tool_count": 10,
            "generated_tool_called_scenarios": 40,
        },
    }

    passed, reasons = _protocol_gate_decision(
        comparison,
        scenario_count=40,
        outcome_only=True,
    )

    assert passed is False
    assert "outcome_score_unavailable" in reasons
    assert all("canonical" not in reason for reason in reasons)


def test_protocol_gate_accepts_outcome_success_with_exact_canonical_accounting_loss() -> (
    None
):
    comparison = {
        "mean_similarity_delta": 0.02,
        "mean_outcome_similarity_delta": 0.16,
        "exact_success_delta": -1,
        "gain_count": 2,
        "regression_count": 4,
        "outcome_gain_count": 6,
        "outcome_regression_count": 2,
        "runtime_exception_count": 0,
        "candidate": {
            "accepted_tool_count": 1,
            "generated_tool_called_scenarios": 1,
        },
    }

    passed, reasons = _protocol_gate_decision(comparison, scenario_count=20)

    assert _route_mismatch_qualified(comparison) is True
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


def test_protocol_gate_accepts_positive_discovery_with_real_helper_activity() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": 0.05,
            "exact_success_delta": 1,
            "gain_count": 5,
            "regression_count": 2,
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


def test_protocol_gate_rejects_discovery_when_exact_successes_regress() -> None:
    passed, reasons = _protocol_gate_decision(
        {
            "mean_similarity_delta": 0.02,
            "exact_success_delta": -1,
            "gain_count": 5,
            "regression_count": 2,
            "runtime_exception_count": 0,
            "candidate": {
                "accepted_tool_count": 0,
                "generated_tool_called_scenarios": 3,
            },
        },
        scenario_count=12,
    )

    assert passed is False
    assert "exact_successes_regressed" in reasons


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
            "--resume-run-root",
            "old-run",
        ],
    )

    with pytest.raises(SystemExit, match="forbids --resume-run-root"):
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
