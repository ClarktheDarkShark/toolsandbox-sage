from sage_ts.experiments.v2_flags import CANDIDATE_REPAIR, CONTRACT_SYNTHESIS
from scripts.run_v2_experimental_matrix20 import _select_combined_features


def _summary(
    variant_id: str,
    features: str,
    *,
    outcome: float,
    canonical: float,
    called: int,
    visible: int,
    vnc: int,
    route_mismatch: bool = False,
) -> dict[str, object]:
    return {
        "variant": {"id": variant_id, "features": features},
        "failed": False,
        "outcome_delta": outcome,
        "canonical_delta": canonical,
        "route_mismatch_qualified": route_mismatch,
        "runtime_exceptions": 0,
        "helpers": {
            "called_count": called,
            "visible_count": visible,
            "visible_not_called_count": vnc,
            "side_effect_incidents": 0,
        },
    }


def test_combined_features_keeps_only_called_positive_low_pollution_variants() -> None:
    selected = _select_combined_features(
        [
            _summary(
                "variant0_current_v2_baseline",
                "default",
                outcome=0.0,
                canonical=0.0,
                called=0,
                visible=0,
                vnc=0,
            ),
            _summary(
                "variant4_candidate_repair",
                CANDIDATE_REPAIR,
                outcome=0.03,
                canonical=0.02,
                called=1,
                visible=8,
                vnc=7,
            ),
            _summary(
                "variant5_contract_synthesis",
                CONTRACT_SYNTHESIS,
                outcome=0.06,
                canonical=0.09,
                called=3,
                visible=4,
                vnc=1,
            ),
        ]
    )

    assert selected == CONTRACT_SYNTHESIS


def test_combined_features_allows_outcome_win_with_qualified_canonical_mismatch() -> (
    None
):
    selected = _select_combined_features(
        [
            _summary(
                "variant1_grading_accounting",
                "grading_accounting",
                outcome=0.05,
                canonical=-0.02,
                called=2,
                visible=3,
                vnc=1,
                route_mismatch=True,
            )
        ]
    )

    assert selected == "grading_accounting"
