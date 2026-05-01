from scripts.write_portfolio_selection import _status_for


def test_validated_tool_with_negative_mean_delta_is_not_portfolio_ready() -> None:
    status = _status_for(
        "select_record_by_timestamp_extreme",
        registry_tools={"select_record_by_timestamp_extreme": {}},
        quarantine={},
        audit={
            "select_record_by_timestamp_extreme": {
                "called_scenarios": 3,
                "gains_when_called": 2,
                "regressions_when_called": 1,
                "mean_canonical_delta_when_called": -0.19,
            }
        },
        missed={},
    )

    assert status == "validated_but_needs_adoption_evidence"


def test_validated_tool_with_positive_called_value_is_portfolio_ready() -> None:
    status = _status_for(
        "recency_to_timestamp_bounds",
        registry_tools={"recency_to_timestamp_bounds": {}},
        quarantine={},
        audit={
            "recency_to_timestamp_bounds": {
                "called_scenarios": 5,
                "gains_when_called": 5,
                "regressions_when_called": 0,
                "mean_canonical_delta_when_called": 0.25,
            }
        },
        missed={},
    )

    assert status == "portfolio_ready"
