# V2.2 Gap Atlas Loop 2

## Objective

Rebuild the masked-best3 V2.2 gap atlas after confirming `days_between_timestamps`, excluding parked lanes and best3-adjacent mechanisms.

## Protected Assets

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Masked best3 tools: `relative_day_time_to_timestamp, resolve_search_window_or_bounds, select_record_by_timestamp_extreme`
- Confirmed V2.2 tools: `days_between_timestamps`
- Parked lanes: `dependency_precondition, recency_action_target_selector, side_effect_argument_preparer_after_selection`

## Sources

- `formal250`: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/paired_comparison.json`
- `robustness60`: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/paired_comparison.json`
- `formal500`: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/paired_comparison.json`
- `formal1032`: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/paired_comparison.json`
- `v2_2_masked_discovery60`: `outputs/v2_2_masked_best3_discovery60_20260505_064113/mechanism_60_20260505_064202/paired_comparison.json`
- `v2_2_days_confirmation60`: `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108/paired_comparison.json`

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Regressions | Score |
| --- | --- | ---: | ---: | ---: | ---: |
| parked_dependency_precondition | excluded_parked | 276 | 11 | 65 | 397 |
| other_no_current_helper_fit | candidate_discovery_ready | 196 | 12 | 53 | 387 |
| best3_adjacent_or_covered | excluded_best3_adjacent | 720 | 22 | 94 | 338 |
| parked_side_effect_argument_preparer_after_selection | excluded_parked | 212 | 5 | 66 | 324 |
| location_lookup_answer_extraction | candidate_discovery_ready | 88 | 7 | 21 | 177 |
| selector_actor_policy_diagnostic_lane | diagnostic_pending_actor_policy | 100 | 4 | 14 | 156 |
| insufficient_information_or_negative | negative_or_abstention_support | 80 | 7 | 0 | 98 |
| stock_symbol_extraction | candidate_discovery_ready | 24 | 2 | 8 | 72 |
| confirmed_days_between_timestamps_covered | excluded_confirmed | 182 | 4 | 25 | 19 |
| parked_recency_action_target_selector | excluded_parked | 84 | 3 | 0 | -6 |

## Recommendation

Run the bounded selector actor-policy diagnostic first. If selector natural adoption remains zero, keep it parked and run loop-2 discovery on stock-symbol extraction plus location/answer-extraction and negative support lanes; do not repeat dependency/precondition or selected-record side-effect-prep lanes.

## Decision Label

`discovery loop2 ready`

## Loop 2 Outcome Update

The loop executed the recommended selector diagnostic and masked-best3 discovery. Selector exposure was repaired, but natural calls remained `0 / 16`, so the selector lane remains parked. Discovery accepted `extract_stock_symbol` after generation/live-validation metadata repair, but it was initially accepted-but-uncalled. After trace-bridging and derived-helper actor-policy repair, the helper became naturally callable (`4 / 4`) in the focused fair-chance diagnostic, but called-subset outcome was negative (`-0.0772`). Therefore no second V2.2 tool was confirmed from this atlas.

Next atlas iteration should avoid repeating selector, dependency/precondition, selected-record side-effect prep, and stock-symbol extraction unless there is materially new actor-policy or concept evidence.
