from pytest import MonkeyPatch

from sage_ts.experiments.v2_flags import CONTRACT_SYNTHESIS, enabled_features


def test_current_v2_defaults_use_fair_chance_winning_stack(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("SAGE_V2_EXPERIMENT_FEATURES", raising=False)

    assert enabled_features() == frozenset({CONTRACT_SYNTHESIS})
