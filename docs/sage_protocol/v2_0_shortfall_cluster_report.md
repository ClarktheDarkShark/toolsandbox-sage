# V2.0 Shortfall Cluster Report

- Updated: `2026-05-04T08:08:59.371464`
- Decision label: `candidate found`
- Frozen best3 registry was not modified: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Machine artifact: `artifacts/summaries/v2_0_shortfall_clusters/latest_shortfall_clusters.json`

## Objective

Mine the locked formal 250 and independent robustness-60 artifacts for remaining no-current-helper-fit cases, regressions, exact-success misses, visible-not-called cases, and deterministic intermediate gaps. Clustering is mechanism-based, not scenario-name promotion.

## Source Artifacts

- `formal250`: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- `robustness60`: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441`

## Cluster Summary

| Cluster | Strong | Scenarios | Families | Mean outcome delta | Outcome regressions | No-fit | VNC | Recommended action |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `search_window_or_record_selection_residual` | `True` | 35 | 8 | `-0.0661` | 15 | 0 | 0 | `routing_or_affordance_repair_priority` |
| `service_precondition_sequencing` | `True` | 24 | 8 | `-0.1128` | 8 | 12 | 0 | `candidate_birth_priority` |
| `contact_message_constraint_selection` | `True` | 39 | 7 | `0.0180` | 5 | 39 | 0 | `candidate_birth_priority` |
| `insufficient_information_policy` | `True` | 66 | 13 | `0.0385` | 2 | 57 | 3 | `policy_or_gate_repair_priority` |
| `reminder_recency_side_effect_sequence` | `True` | 11 | 2 | `0.0000` | 1 | 0 | 6 | `candidate_birth_priority` |
| `no_current_helper_fit_other` | `False` | 26 | 4 | `-0.0828` | 9 | 26 | 0 | `diagnostic_only` |
| `visible_not_called_routing_affordance` | `False` | 7 | 3 | `-0.2893` | 4 | 0 | 7 | `routing_or_affordance_repair_priority` |
| `holiday_calendar_date_arithmetic` | `False` | 15 | 2 | `-0.2857` | 3 | 8 | 0 | `diagnostic_only` |
| `covered_but_regressed_or_missed` | `False` | 24 | 5 | `0.0179` | 1 | 0 | 0 | `diagnostic_only` |

## Strong Clusters

### `search_window_or_record_selection_residual`

- Mechanism: Search/ranking tasks still fail outcome despite best3 coverage, often from search-window or selected-record sequencing gaps.
- Tool suitability: medium: likely routing/affordance repair or combined planner, not necessarily a new broad helper.
- Candidate family: `routing_or_sequence_repair`
- Evidence: `35` shortfall rows, `8` base families, mean outcome delta `-0.06608733605880932`.
- Example scenarios:
  - `search_message_with_recency_latest_alt`
  - `search_message_with_recency_latest_alt_10_distraction_tools`
  - `search_message_with_recency_latest_alt_all_tools`
  - `search_message_with_recency_latest_multiple_user_turn`
  - `search_message_with_recency_latest_multiple_user_turn_10_distraction_tools`
  - `search_message_with_recency_latest_multiple_user_turn_alt`
  - `search_message_with_recency_latest_multiple_user_turn_alt_10_distraction_tools`
  - `search_message_with_recency_oldest`

### `service_precondition_sequencing`

- Mechanism: Tasks require deterministic state/precondition ordering before a downstream action, e.g. low battery, wifi, cellular, or location state before service-dependent tools.
- Tool suitability: high: a planner/checker can return one original ToolSandbox service-setting call or abstain, preserving downstream actions.
- Candidate family: `state_precondition_planner`
- Evidence: `24` shortfall rows, `8` base families, mean outcome delta `-0.11278531907342883`.
- Example scenarios:
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_10_distraction_tools`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_3_distraction_tools`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_3_distraction_tools_arg_description_scrambled`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_3_distraction_tools_arg_type_scrambled`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_3_distraction_tools_tool_description_scrambled`
  - `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt_3_distraction_tools_tool_name_scrambled`
  - `cellular_off`

### `contact_message_constraint_selection`

- Mechanism: Visible contact/message constraints are present, but the model must map name/relationship/phone/content constraints to the right record or action.
- Tool suitability: high: a deterministic selector can choose or abstain from visible candidates and preserve send/modify/remove tools.
- Candidate family: `constraint_based_record_selector`
- Evidence: `39` shortfall rows, `7` base families, mean outcome delta `0.017993702204228523`.
- Example scenarios:
  - `remove_contact_by_phone`
  - `remove_contact_by_phone_10_distraction_tools`
  - `remove_contact_by_phone_all_tools`
  - `remove_contact_by_phone_alt`
  - `remove_contact_by_phone_alt_10_distraction_tools`
  - `remove_contact_by_phone_ambiguous`
  - `remove_contact_by_phone_ambiguous_alt`
  - `remove_contact_by_phone_multiple_user_turn`

### `insufficient_information_policy`

- Mechanism: Insufficient-information tasks require abstention/clarification and avoiding tool overuse or unsafe helper exposure.
- Tool suitability: medium: may be better as routing/gate policy than a runtime helper.
- Candidate family: `abstention_policy_or_routing_gate`
- Evidence: `66` shortfall rows, `13` base families, mean outcome delta `0.03851203184688269`.
- Example scenarios:
  - `find_days_till_holiday_insufficient_information`
  - `find_days_till_holiday_insufficient_information_10_distraction_tools`
  - `find_days_till_holiday_insufficient_information_3_distraction_tools`
  - `find_days_till_holiday_insufficient_information_3_distraction_tools_arg_description_scrambled`
  - `find_days_till_holiday_insufficient_information_3_distraction_tools_arg_type_scrambled`
  - `find_days_till_holiday_insufficient_information_3_distraction_tools_tool_description_scrambled`
  - `find_days_till_holiday_insufficient_information_3_distraction_tools_tool_name_scrambled`
  - `find_days_till_holiday_insufficient_information_all_tools`

### `reminder_recency_side_effect_sequence`

- Mechanism: Remove/modify reminder recency tasks require search-window construction, record selection, then original side-effect preservation.
- Tool suitability: high but risky: helper must not remove/modify itself; should prepare selected record/action args only after visible search results.
- Candidate family: `side_effect_argument_preparer_after_selection`
- Evidence: `11` shortfall rows, `2` base families, mean outcome delta `0.0`.
- Example scenarios:
  - `modify_reminder_with_recency_latest_alt`
  - `remove_reminder_with_recency_latest`
  - `remove_reminder_with_recency_latest_10_distraction_tools`
  - `remove_reminder_with_recency_latest_3_distraction_tools`
  - `remove_reminder_with_recency_latest_3_distraction_tools_arg_description_scrambled`
  - `remove_reminder_with_recency_latest_3_distraction_tools_arg_type_scrambled`
  - `remove_reminder_with_recency_latest_3_distraction_tools_tool_description_scrambled`
  - `remove_reminder_with_recency_latest_all_tools`

## Interpretation

At least five clusters are tool-suitable enough for discovery. The strongest new-tool birth targets are service/precondition sequencing, contact/message constraint selection, and reminder recency side-effect sequencing. Search-window residuals and visible-not-called cases should be treated primarily as routing/affordance repair evidence, because they involve existing best3 helpers. Insufficient-information cases are better treated as abstention/routing policy unless trace review shows a deterministic helper can safely generalize.

## Next Action

Build a quality-gated V2.0 discovery-60 manifest emphasizing these clusters, copy the frozen best3 registry into a separate candidate registry, run generation ON, and triage any generated candidates based on validation proof, actual calls, called-subset contribution, and safety.

Decision label: `candidate found`
