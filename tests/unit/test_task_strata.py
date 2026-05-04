from sage_ts.evaluation.task_strata import (
    base_task_family,
    classify_task_strata,
    cohort_policy_report,
    expected_birth_opportunities,
    expected_helper_fit,
)


def test_temporal_reminder_relative_time_fit() -> None:
    scenario = "add_reminder_content_and_week_delta_and_time_3_distraction_tools"

    assert "temporal_reminder_date_canonicalization" in classify_task_strata(
        scenario, ["MULTIPLE_TOOL_CALL"]
    )
    assert "relative_day_time_to_timestamp" in expected_helper_fit(scenario)


def test_latest_reminder_modification_matches_relative_time_fit() -> None:
    scenario = "modify_reminder_with_recency_latest_3_distraction_tools"

    assert "relative_day_time_to_timestamp" in expected_helper_fit(scenario)
    assert "canonicalizer:relative_day_time_timestamp" in (
        expected_birth_opportunities(scenario)
    )


def test_add_reminder_location_argument_prep_matches_birth_path() -> None:
    scenario = (
        "add_reminder_content_and_week_delta_and_time_and_location_3_distraction_tools"
    )

    assert "prepare_reminder_creation_args" in expected_helper_fit(scenario)
    assert "composite:prepare_reminder_creation_args" in expected_birth_opportunities(
        scenario
    )


def test_direct_contact_remove_by_phone_is_not_helper_opportunity() -> None:
    scenario = "remove_contact_by_phone_alt_3_distraction_tools"

    strata = classify_task_strata(scenario)

    assert "contact_message_search_disambiguation" in strata
    assert "direct_state_precondition_service_enablement" not in strata
    assert "select_contact_field_by_constraint" not in expected_helper_fit(scenario)
    assert expected_birth_opportunities(scenario) == []


def test_ambiguous_contact_lookup_is_not_birth_opportunity() -> None:
    scenario = "remove_contact_by_phone_ambiguous_3_distraction_tools"

    assert "select_contact_field_by_constraint" not in expected_helper_fit(scenario)
    assert expected_birth_opportunities(scenario) == []


def test_contact_search_tasks_have_birth_opportunity_and_retained_fit() -> None:
    scenario = "search_phone_number_with_name_3_distraction_tools"

    assert "select_contact_field_by_constraint" in expected_helper_fit(scenario)
    assert "search_filter:select_contact_field_by_constraint" in (
        expected_birth_opportunities(scenario)
    )


def test_raw_latest_message_matches_retrieval_window_and_selector() -> None:
    scenario = "search_message_with_recency_latest_multiple_user_turn_alt"

    assert "record_filtering_ranking_latest_selection" in classify_task_strata(scenario)
    assert "select_record_by_timestamp_extreme" in expected_helper_fit(scenario)
    assert "message_search_time_window" in expected_helper_fit(scenario)
    assert "resolve_search_window_or_bounds" in expected_helper_fit(scenario)
    assert "search_filter:select_record_by_timestamp_extreme" in (
        expected_birth_opportunities(scenario)
    )
    assert "derived_value:message_search_time_window" in (
        expected_birth_opportunities(scenario)
    )
    assert "derived_value:resolve_search_window_or_bounds" in (
        expected_birth_opportunities(scenario)
    )


def test_modify_contact_message_recency_matches_trace_compatible_helpers() -> None:
    scenario = "modify_contact_with_message_recency_3_distraction_tools"

    assert "contact_message_search_disambiguation" in classify_task_strata(scenario)
    assert "select_record_by_timestamp_extreme" in expected_helper_fit(scenario)
    assert "message_search_time_window" in expected_helper_fit(scenario)
    assert "search_filter:select_record_by_timestamp_extreme" in (
        expected_birth_opportunities(scenario)
    )
    assert "derived_value:message_search_time_window" in (
        expected_birth_opportunities(scenario)
    )


def test_oldest_message_matches_retrieval_window_and_selector() -> None:
    scenario = "search_message_with_recency_oldest_10_distraction_tools"

    assert "select_record_by_timestamp_extreme" in expected_helper_fit(scenario)
    assert "message_search_time_window" in expected_helper_fit(scenario)
    assert "resolve_search_window_or_bounds" in expected_helper_fit(scenario)
    assert "search_filter:select_record_by_timestamp_extreme" in (
        expected_birth_opportunities(scenario)
    )
    assert "derived_value:message_search_time_window" in (
        expected_birth_opportunities(scenario)
    )
    assert "derived_value:resolve_search_window_or_bounds" in (
        expected_birth_opportunities(scenario)
    )


def test_message_helpers_do_not_fit_insufficient_information_tasks() -> None:
    scenario = "modify_contact_with_message_recency_insufficient_information"

    assert expected_helper_fit(scenario) == []
    assert expected_birth_opportunities(scenario) == []


def test_holiday_task_matches_day_distance_helper() -> None:
    scenario = "find_days_till_holiday_3_distraction_tools"

    assert "holiday_calendar_business_day_logic" in classify_task_strata(scenario)
    assert "days_between_timestamps" in expected_helper_fit(scenario)


def test_recency_bounds_match_creation_recency_not_due_recency() -> None:
    assert "recency_to_timestamp_bounds" in expected_helper_fit(
        "search_reminder_with_creation_recency_yesterday"
    )
    assert "recency_to_timestamp_bounds" not in expected_helper_fit(
        "search_reminder_with_recency_yesterday"
    )
    assert "recency_to_timestamp_bounds" not in expected_helper_fit(
        "search_reminder_with_creation_recency_yesterday_insufficient_information"
    )


def test_resolve_search_window_matches_reminder_and_message_recency() -> None:
    assert "resolve_search_window_or_bounds" in expected_helper_fit(
        "search_reminder_with_creation_recency_yesterday"
    )
    assert "resolve_search_window_or_bounds" in expected_helper_fit(
        "search_reminder_with_recency_upcoming"
    )
    assert "resolve_search_window_or_bounds" in expected_helper_fit(
        "search_message_with_recency_latest"
    )
    assert "resolve_search_window_or_bounds" not in expected_helper_fit(
        "search_reminder_with_creation_recency_yesterday_insufficient_information"
    )


def test_base_task_family_collapses_tool_robustness_variants() -> None:
    assert (
        base_task_family(
            "remove_contact_by_phone_ambiguous_alt_3_distraction_tools_arg_type_scrambled"
        )
        == "remove_contact_by_phone"
    )
    assert (
        base_task_family(
            "search_message_with_recency_oldest_multiple_user_turn_alt_all_tools"
        )
        == "search_message_with_recency_oldest"
    )


def test_stock_symbol_task_matches_extraction_birth_path() -> None:
    scenario = (
        "find_stock_symbol_with_company_name_low_battery_mode_10_distraction_tools"
    )

    assert "stock_market_numeric_normalization" in classify_task_strata(scenario)
    assert "extract_stock_symbol" in expected_helper_fit(scenario)
    assert "derived_value:extract_stock_symbol" in expected_birth_opportunities(
        scenario
    )


def test_state_tool_call_fits_direct_service_precondition_tasks() -> None:
    scenario = "turn_on_wifi_low_battery_mode_3_distraction_tools"

    assert "direct_state_precondition_service_enablement" in classify_task_strata(
        scenario
    )
    assert "next_service_tool_call" in expected_helper_fit(scenario)
    assert "state_precondition:next_service_tool_call" in (
        expected_birth_opportunities(scenario)
    )


def test_state_tool_call_fits_downstream_low_battery_tasks() -> None:
    scenario = "find_temperature_low_battery_mode_3_distraction_tools"

    assert "next_service_tool_call" in expected_helper_fit(scenario)
    assert "next_service_tool_call" not in expected_helper_fit(
        "find_current_city_low_battery_mode_insufficient_information"
    )


def test_cohort_policy_report_blocks_empty_generation_with_no_birth_path() -> None:
    report = cohort_policy_report(
        ["unsupported_miscellaneous_task"],
        categories_by_name={"unsupported_miscellaneous_task": []},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["should_block"] is True
    assert "generation_enabled_but_no_expected_birth_path" in report["warnings"]


def test_cohort_policy_report_allows_stock_extraction_birth_path() -> None:
    scenario = "find_stock_symbol_with_company_name_3_distraction_tools"
    report = cohort_policy_report(
        [scenario],
        categories_by_name={scenario: ["MULTIPLE_TOOL_CALL"]},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["should_block"] is False
    assert report["contaminated_external_service_scenarios"] == [scenario]
    assert "external_service_cases_present" in report["warnings"]
    assert report["expected_birth_opportunity_counts"] == {
        "derived_value:extract_stock_symbol": 1
    }


def test_cohort_policy_report_marks_location_lookup_as_contaminated() -> None:
    scenario = "find_current_location_low_battery_mode_insufficient_information"
    report = cohort_policy_report(
        [scenario],
        categories_by_name={scenario: ["STATE_DEPENDENCY"]},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["contaminated_external_service_scenarios"] == [scenario]
    assert "external_service_cases_present" in report["warnings"]


def test_cohort_policy_report_marks_currency_conversion_as_contaminated() -> None:
    scenario = "convert_currency_3_distraction_tools"
    report = cohort_policy_report(
        [scenario],
        categories_by_name={scenario: ["CANONICALIZATION", "SINGLE_TOOL_CALL"]},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["contaminated_external_service_scenarios"] == [scenario]
    assert "external_service_cases_present" in report["warnings"]


def test_cohort_policy_report_tracks_post_birth_reuse_opportunity() -> None:
    scenarios = [
        "modify_contact_with_message_recency",
        "modify_contact_with_message_recency_3_distraction_tools",
        "modify_contact_with_message_recency_10_distraction_tools",
    ]
    report = cohort_policy_report(
        scenarios,
        categories_by_name={scenario: ["MULTIPLE_TOOL_CALL"] for scenario in scenarios},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["has_post_birth_reuse_opportunity"] is True
    reuse = report["post_birth_reuse_opportunities"][
        "derived_value:message_search_time_window"
    ]
    assert reuse["first_birth_scenario"] == "modify_contact_with_message_recency"
    assert reuse["later_fit_count"] == 2


def test_cohort_policy_report_warns_when_birth_has_no_later_reuse() -> None:
    scenario = "modify_contact_with_message_recency"
    report = cohort_policy_report(
        [scenario],
        categories_by_name={scenario: ["MULTIPLE_TOOL_CALL"]},
        generation_enabled=True,
        registry_tool_count=0,
    )

    assert report["has_expected_birth_path"] is True
    assert report["has_post_birth_reuse_opportunity"] is False
    assert (
        "generation_enabled_but_no_post_birth_reuse_opportunity" in report["warnings"]
    )


def test_cohort_policy_report_warns_when_helper_fit_is_too_sparse() -> None:
    scenarios = [
        "search_message_with_recency_latest",
        "find_stock_symbol_with_company_name",
        "add_contact_with_name_and_phone_number",
        "send_message_with_phone_number_and_content",
        "find_current_location_insufficient_information",
        "find_phone_number_with_location_name",
        "remove_contact_with_id",
        "remove_contact_by_phone_no_search_contacts_insufficient_information",
        "find_stock_symbol_with_company_name_low_battery_mode",
        "find_thanksgiving_timestamp",
        "search_reminder_with_creation_recency_yesterday",
        "remove_reminder_with_recency_latest_insufficient_information",
    ]
    report = cohort_policy_report(
        scenarios,
        categories_by_name={scenario: [] for scenario in scenarios},
        generation_enabled=True,
        registry_tool_count=3,
    )

    assert report["expected_helper_fit_share"] < 0.5
    assert "low_expected_helper_fit_share" in report["warnings"]


def test_cohort_policy_report_fails_near_duplicate_dominated_20() -> None:
    repeated = [
        "add_reminder_content_and_week_delta_and_time_and_location",
        "add_reminder_content_and_week_delta_and_time_and_location_3_distraction_tools",
        "add_reminder_content_and_week_delta_and_time_and_location_10_distraction_tools",
    ]
    diverse_fill = [f"uncovered_task_family_{index}" for index in range(17)]
    scenarios = repeated + diverse_fill

    report = cohort_policy_report(
        scenarios,
        categories_by_name={scenario: [] for scenario in scenarios},
        generation_enabled=False,
        registry_tool_count=0,
    )

    assert report["should_block_quality"] is True
    assert (
        "near_duplicate_family_variants_above_limit" in report["quality_gate_failures"]
    )
    assert report["decision_use"] == "suitable_for_early_value_only"


def test_cohort_policy_report_fails_broad_known_lane_overrepresentation() -> None:
    scenarios = [
        f"search_reminder_with_creation_recency_yesterday_variant_{index}"
        for index in range(17)
    ] + [f"uncovered_task_family_{index}" for index in range(3)]

    report = cohort_policy_report(
        scenarios,
        categories_by_name={scenario: [] for scenario in scenarios},
        generation_enabled=False,
        registry_tool_count=2,
    )

    assert report["should_block_quality"] is True
    assert "weak_negative_no_helper_coverage" in report["quality_gate_failures"]
    assert "known_helper_lane_overrepresented" in report["quality_gate_failures"]
