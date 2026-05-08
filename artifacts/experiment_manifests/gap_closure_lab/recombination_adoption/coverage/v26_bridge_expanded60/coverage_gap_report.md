# Coverage Gap Report

This report maps current retained helper coverage against prior 100/250 scenario mixes.

## Model Comparison Guard

- Mixed model warning: False
- Comparison keys: ['agent=gpt-4o-mini|generation=gpt-4o-mini|user=gpt-4o-mini']

## Stratum Summary

### generic_multi_tool_composition
- Scenarios: 52
- Mean delta: -0.0291
- Gains / regressions / preserved: 16 / 14 / 22
- Visible-tool scenarios: 9
- Called-tool scenarios: 7
- No-visible-tool regressions: 11
- Expected helper fit: {'no_current_helper_fit': 43, 'resolve_search_window_or_bounds': 5, 'select_record_by_timestamp_extreme': 2, 'plan_contact_lookup_query': 2, 'extract_contact_field_from_search_result': 2, 'days_between_timestamps': 2, 'recency_to_timestamp_bounds': 1, 'relative_day_time_to_timestamp': 1}

### record_filtering_ranking_latest_selection
- Scenarios: 37
- Mean delta: -0.0330
- Gains / regressions / preserved: 8 / 9 / 20
- Visible-tool scenarios: 8
- Called-tool scenarios: 7
- No-visible-tool regressions: 7
- Expected helper fit: {'no_current_helper_fit': 28, 'resolve_search_window_or_bounds': 5, 'select_record_by_timestamp_extreme': 2, 'plan_contact_lookup_query': 2, 'extract_contact_field_from_search_result': 2, 'days_between_timestamps': 2, 'recency_to_timestamp_bounds': 1, 'relative_day_time_to_timestamp': 1}

### insufficient_information_clarification
- Scenarios: 20
- Mean delta: -0.0968
- Gains / regressions / preserved: 2 / 3 / 15
- Visible-tool scenarios: 1
- Called-tool scenarios: 0
- No-visible-tool regressions: 3
- Expected helper fit: {'no_current_helper_fit': 19, 'days_between_timestamps': 1}

### direct_state_precondition_service_enablement
- Scenarios: 19
- Mean delta: -0.1679
- Gains / regressions / preserved: 2 / 9 / 8
- Visible-tool scenarios: 1
- Called-tool scenarios: 0
- No-visible-tool regressions: 8
- Expected helper fit: {'no_current_helper_fit': 19}

### contact_message_search_disambiguation
- Scenarios: 17
- Mean delta: 0.0033
- Gains / regressions / preserved: 10 / 4 / 3
- Visible-tool scenarios: 6
- Called-tool scenarios: 4
- No-visible-tool regressions: 2
- Expected helper fit: {'no_current_helper_fit': 13, 'select_record_by_timestamp_extreme': 2, 'resolve_search_window_or_bounds': 2, 'plan_contact_lookup_query': 2, 'extract_contact_field_from_search_result': 2}

### weather_location_current_city_distance
- Scenarios: 13
- Mean delta: -0.1843
- Gains / regressions / preserved: 1 / 6 / 6
- Visible-tool scenarios: 0
- Called-tool scenarios: 0
- No-visible-tool regressions: 6
- Expected helper fit: {'no_current_helper_fit': 13}

### temporal_reminder_date_canonicalization
- Scenarios: 11
- Mean delta: -0.0682
- Gains / regressions / preserved: 1 / 2 / 8
- Visible-tool scenarios: 4
- Called-tool scenarios: 3
- No-visible-tool regressions: 1
- Expected helper fit: {'no_current_helper_fit': 8, 'resolve_search_window_or_bounds': 3, 'recency_to_timestamp_bounds': 1, 'relative_day_time_to_timestamp': 1}

### holiday_calendar_business_day_logic
- Scenarios: 2
- Mean delta: 0.0034
- Gains / regressions / preserved: 1 / 0 / 1
- Visible-tool scenarios: 0
- Called-tool scenarios: 0
- No-visible-tool regressions: 0
- Expected helper fit: {'days_between_timestamps': 2}

### stock_market_numeric_normalization
- Scenarios: 2
- Mean delta: 0.2500
- Gains / regressions / preserved: 1 / 0 / 1
- Visible-tool scenarios: 0
- Called-tool scenarios: 0
- No-visible-tool regressions: 0
- Expected helper fit: {'no_current_helper_fit': 2}

### other_uncovered_clusters
- Scenarios: 2
- Mean delta: 0.0000
- Gains / regressions / preserved: 0 / 0 / 2
- Visible-tool scenarios: 0
- Called-tool scenarios: 0
- No-visible-tool regressions: 0
- Expected helper fit: {'no_current_helper_fit': 2}

## Helper Coverage Matrix

### days_between_timestamps
- Trigger strata: ['holiday_calendar_business_day_logic']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### relative_day_time_to_timestamp
- Trigger strata: ['temporal_reminder_date_canonicalization']
- Visible by stratum: {'temporal_reminder_date_canonicalization': 2, 'record_filtering_ranking_latest_selection': 2, 'insufficient_information_clarification': 1, 'generic_multi_tool_composition': 1}
- Called by stratum: {'temporal_reminder_date_canonicalization': 1, 'record_filtering_ranking_latest_selection': 1, 'generic_multi_tool_composition': 1}
- Mean delta when called by stratum: {'temporal_reminder_date_canonicalization': 0.0, 'record_filtering_ranking_latest_selection': 0.0, 'generic_multi_tool_composition': 0.0}

### recency_to_timestamp_bounds
- Trigger strata: ['temporal_reminder_date_canonicalization', 'record_filtering_ranking_latest_selection']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### resolve_search_window_or_bounds
- Trigger strata: ['temporal_reminder_date_canonicalization', 'record_filtering_ranking_latest_selection', 'contact_message_search_disambiguation']
- Visible by stratum: {'record_filtering_ranking_latest_selection': 5, 'generic_multi_tool_composition': 5, 'temporal_reminder_date_canonicalization': 3, 'contact_message_search_disambiguation': 2}
- Called by stratum: {'temporal_reminder_date_canonicalization': 2, 'record_filtering_ranking_latest_selection': 2, 'generic_multi_tool_composition': 2}
- Mean delta when called by stratum: {'temporal_reminder_date_canonicalization': 0.12477939438436486, 'record_filtering_ranking_latest_selection': 0.12477939438436486, 'generic_multi_tool_composition': 0.12477939438436486}

### select_latest_record_by_timestamp
- Trigger strata: ['record_filtering_ranking_latest_selection', 'contact_message_search_disambiguation']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### select_record_by_timestamp_extreme
- Trigger strata: ['record_filtering_ranking_latest_selection', 'contact_message_search_disambiguation']
- Visible by stratum: {'record_filtering_ranking_latest_selection': 3, 'generic_multi_tool_composition': 3, 'contact_message_search_disambiguation': 2, 'temporal_reminder_date_canonicalization': 1}
- Called by stratum: {'contact_message_search_disambiguation': 2, 'record_filtering_ranking_latest_selection': 2, 'generic_multi_tool_composition': 2}
- Mean delta when called by stratum: {'contact_message_search_disambiguation': 0.12260000315857614, 'record_filtering_ranking_latest_selection': 0.12260000315857614, 'generic_multi_tool_composition': 0.12260000315857614}

### select_visible_record_by_constraints
- Trigger strata: ['contact_message_search_disambiguation', 'record_filtering_ranking_latest_selection']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### select_action_target_by_recency
- Trigger strata: ['record_filtering_ranking_latest_selection', 'contact_message_search_disambiguation', 'temporal_reminder_date_canonicalization']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### prepare_side_effect_args_from_selected_record
- Trigger strata: ['generic_multi_tool_composition', 'contact_message_search_disambiguation', 'record_filtering_ranking_latest_selection']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### constraint_to_action_planner
- Trigger strata: ['generic_multi_tool_composition', 'contact_message_search_disambiguation', 'record_filtering_ranking_latest_selection']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### next_service_tool_call
- Trigger strata: ['direct_state_precondition_service_enablement']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### recover_from_tool_error
- Trigger strata: ['direct_state_precondition_service_enablement']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### next_service_enablement_action
- Trigger strata: ['direct_state_precondition_service_enablement']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### prepare_reminder_creation_args
- Trigger strata: ['temporal_reminder_date_canonicalization', 'generic_multi_tool_composition']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### extract_service_answer_field
- Trigger strata: ['weather_location_current_city_distance']
- Visible by stratum: {}
- Called by stratum: {}
- Mean delta when called by stratum: {}

### plan_contact_lookup_query
- Trigger strata: ['contact_message_search_disambiguation', 'generic_multi_tool_composition']
- Visible by stratum: {'contact_message_search_disambiguation': 2, 'record_filtering_ranking_latest_selection': 2, 'generic_multi_tool_composition': 2}
- Called by stratum: {'contact_message_search_disambiguation': 2, 'record_filtering_ranking_latest_selection': 2, 'generic_multi_tool_composition': 2}
- Mean delta when called by stratum: {'contact_message_search_disambiguation': 0.08689575844733483, 'record_filtering_ranking_latest_selection': 0.08689575844733483, 'generic_multi_tool_composition': 0.08689575844733483}

### extract_contact_field_from_search_result
- Trigger strata: ['contact_message_search_disambiguation']
- Visible by stratum: {'contact_message_search_disambiguation': 2, 'record_filtering_ranking_latest_selection': 2, 'generic_multi_tool_composition': 2}
- Called by stratum: {}
- Mean delta when called by stratum: {}

## Campaign Implication

- Do not run another broad 100/250 gate until uncovered high-frequency strata have discovery runs.
- Prioritize contact/message disambiguation and record filtering/ranking because they recur often and current helper coverage is thin.
- Treat broad validation as a regression/generalization test after registry coverage expands, not as the primary proof for the current four tools.
