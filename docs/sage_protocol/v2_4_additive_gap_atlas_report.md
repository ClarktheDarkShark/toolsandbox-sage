# V2.4 Additive Gap Atlas Report

## Objective

Rebuild the gap atlas with a stricter additive-over-best3 rule. Masked-best3 evidence is no longer sufficient for candidate advancement.

## Sources

- `formal100_best3`: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/paired_comparison.json`
- `formal250_best3`: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/paired_comparison.json`
- `formal500_best3`: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/paired_comparison.json`
- `formal1032_best3`: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/paired_comparison.json`
- `robustness60_best3`: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/paired_comparison.json`
- `best4_ablation_best3`: `outputs/v2_2_best4_ablation60_best3_20260506_075831/mechanism_60_20260506_075938/paired_comparison.json`
- `best4_ablation_best4`: `outputs/v2_2_best4_ablation60_best4_20260506_075831/mechanism_60_20260506_082133/paired_comparison.json`
- `best4_frozen100`: `outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140/paired_comparison.json`

## Excluded Or Downranked Lanes

- `best3_covered`
- `broad_constraint_action_planner`
- `days_between_calendar_distance`
- `dependency_precondition`
- `recency_action_selector`
- `selected_record_side_effect_prep`
- `stock_symbol_extraction`
- `visible_record_selector`

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Best3 failures | Best3 regressions | No-helper-fit | Additive score |
|---|---|---:|---:|---:|---:|---:|---:|
| best3_covered | excluded_or_parked | 798 | 16 | 568 | 138 | 0 | 2191 |
| visible_record_selector | excluded_or_parked | 294 | 9 | 181 | 74 | 294 | 1348 |
| dependency_precondition | excluded_or_parked | 317 | 18 | 92 | 77 | 317 | 1157 |
| external_service_answer_extraction | candidate_ranked | 88 | 8 | 68 | 16 | 88 | 484 |
| other_no_current_helper_fit | support_or_negative_not_primary | 94 | 3 | 37 | 21 | 94 | 287 |
| insufficient_information_or_clarification | support_or_negative_not_primary | 172 | 11 | 0 | 0 | 172 | 267 |
| days_between_calendar_distance | excluded_or_parked | 189 | 4 | 60 | 24 | 38 | 263 |
| direct_side_effect_no_helper | support_or_negative_not_primary | 96 | 3 | 22 | 30 | 96 | 262 |
| recency_action_selector | excluded_or_parked | 90 | 3 | 0 | 0 | 90 | 89 |
| stock_symbol_extraction | excluded_or_parked | 24 | 2 | 17 | 8 | 24 | 38 |

## Selected Cluster

`external_service_answer_extraction`

The top non-parked cluster is selected only because it has answer-only deterministic extraction potential, scalar/dict output inputs, no final side-effect execution, and a plausible additive gap beside best3. It is still speculative and must prove actual additivity in best3-active discovery and confirmation.

## Decision Label

`additive discovery ready`
