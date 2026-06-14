# mypy: ignore-errors
import os

import pytest

from scripts.run_sage_protocol import (
    SAGE_POLICY_AUTO,
    SAGE_POLICY_NONE,
    SAGE_POLICY_SELF_EVOLVING_PRAXIS,
    SAGE_POLICY_SELF_EVOLVING_PRAXIS_COMBINED,
    SELF_EVOLVING_PRAXIS_COMBINED_ENV_DEFAULTS,
    SELF_EVOLVING_PRAXIS_ENV_DEFAULTS,
    _apply_sage_policy_preset,
    _generation_enabled_by_default,
    _protocol_gate_decision,
    _resolve_sage_policy_preset,
    _restore_registry_after_failed_gate,
    _route_mismatch_qualified,
    _snapshot_registry_for_gate,
)


@pytest.fixture(autouse=True)
def _restore_sage_environment() -> None:
    tracked_keys = set(SELF_EVOLVING_PRAXIS_COMBINED_ENV_DEFAULTS)
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
    assert applied["SAGE_PRAXIS_BRIDGE_POLICY"]["value"] == "disabled"


def test_self_evolving_praxis_policy_preserves_explicit_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "disabled")

    applied = _apply_sage_policy_preset(SAGE_POLICY_SELF_EVOLVING_PRAXIS)

    assert applied["SAGE_PRAXIS_BRIDGE_POLICY"] == {
        "value": "disabled",
        "source": "preexisting_environment",
    }


def test_self_evolving_praxis_policy_rejects_enabled_bridge_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SAGE_PRAXIS_BRIDGE_POLICY", "combined")

    with pytest.raises(ValueError, match="autonomous tool-generation policy"):
        _apply_sage_policy_preset(SAGE_POLICY_SELF_EVOLVING_PRAXIS)


def test_combined_praxis_policy_keeps_bridge_as_explicit_ablation(
    monkeypatch,
) -> None:
    for key in SELF_EVOLVING_PRAXIS_COMBINED_ENV_DEFAULTS:
        monkeypatch.delenv(key, raising=False)

    applied = _apply_sage_policy_preset(SAGE_POLICY_SELF_EVOLVING_PRAXIS_COMBINED)

    assert applied["SAGE_PRAXIS_BRIDGE_POLICY"] == {
        "value": "combined",
        "source": "preset_default",
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
