# V2.1 Gap Atlas Report

## Objective

Rank the remaining post-best3 shortfall clusters and build the next quality-gated discovery60 manifest without modifying frozen best3 evidence.

## Sources

- Formal 250: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/paired_comparison.json`
- Robustness 60: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/paired_comparison.json`
- Select-action confirmation60: `outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336/paired_comparison.json`
- Protected registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`

## Ranked Clusters

| Cluster | Scenarios | Families | Outcome regressions | No best3 fit | Mean outcome delta | Rank score |
|---|---:|---:|---:|---:|---:|---:|
| constraint_visible_record_selector | 72 | 9 | 12 | 72 | 0.0253 | 146 |
| search_plus_selection_or_window_residual | 90 | 14 | 23 | 12 | 0.1424 | 121 |
| service_precondition_or_state_parked | 42 | 12 | 12 | 34 | -0.0526 | 78 |
| other_no_helper_or_direct | 70 | 9 | 6 | 30 | 0.0918 | 74 |
| holiday_calendar_distance | 30 | 4 | 4 | 30 | 0.0000 | 62 |
| recency_action_target_selector_parked | 66 | 6 | 6 | 29 | 0.1869 | 43 |

## Decision

The next run should test `constraint_visible_record_selector` and `side_effect_argument_preparer_after_selection`. These are higher value than another recency-action test because the recency-action selector was callable but negative in confirmation60. Dependency/precondition remains parked because force-call diagnostics were non-positive and had one side-effect preservation failure.

## Discovery60 Manifest

- Manifest type: `sage_v2_1_gap_closure_discovery60`
- Scenario count: `60`
- Role counts: `{'early_cluster_positive': 20, 'held_out_reuse': 16, 'negative_or_ambiguity': 24}`
- Quality gate: `pass`
- Distinct base families: `15`
- Largest family share: `0.133`
- No-current-helper-fit share: `0.417`

## Decision Label

`candidate discovery ready`
