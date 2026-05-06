# V2.5 Blocker-Aware Gap Atlas Report

## Objective

Build a blocker-aware gap atlas from best3 and V2.x evidence, separating adoption, callability, value, and safety failures before spending on new runs.

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Best3 failures | Best3 regressions | No-fit | Additive score | Prior blocker |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `best3_covered` | excluded_or_parked | 774 | 16 | 550 | 133 | 0 | 2114 | best3-covered |
| `visible_record_selector` | excluded_or_parked | 286 | 9 | 177 | 72 | 286 | 1309 | adoption failure |
| `dependency_precondition` | excluded_or_parked | 317 | 18 | 92 | 77 | 317 | 1154 | adoption/value/safety failure |
| `direct_side_effect_no_helper` | support_or_negative_not_primary | 104 | 4 | 24 | 29 | 104 | 304 |  |
| `temperature_unit_answer_resolution` | candidate_ranked | 32 | 3 | 32 | 9 | 32 | 270 |  |
| `insufficient_information_or_clarification` | support_or_negative_not_primary | 172 | 11 | 0 | 0 | 172 | 266 |  |
| `days_between_calendar_distance` | excluded_or_parked | 175 | 4 | 57 | 23 | 36 | 243 | non-additive over best3 |
| `other_no_current_helper_fit` | support_or_negative_not_primary | 72 | 2 | 30 | 15 | 72 | 198 |  |
| `distance_answer_resolution` | candidate_ranked | 24 | 1 | 21 | 7 | 24 | 196 |  |
| `currency_answer_normalization` | candidate_ranked | 16 | 2 | 0 | 0 | 16 | 91 |  |
| `recency_action_selector` | excluded_or_parked | 90 | 3 | 0 | 0 | 90 | 86 | value failure |
| `stock_symbol_extraction` | excluded_or_parked | 24 | 2 | 17 | 8 | 24 | 35 | value failure |

## Candidate Design Options

- `resolve_temperature_answer_unit` / `answer-only scalar calculator` in `temperature_unit_answer_resolution`: score `68`, advantage: Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads.
- `prepare_temperature_conversion_args` / `argument preparer for canonical unit conversion` in `temperature_unit_answer_resolution`: score `66`, advantage: Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call.
- `format_distance_answer` / `scalar answer formatter` in `distance_answer_resolution`: score `55`, advantage: Normalizes numeric distance precision and unit text after calculate_lat_lon_distance.
- `normalize_currency_answer` / `scalar answer formatter` in `currency_answer_normalization`: score `55`, advantage: Formats visible convert_currency output with correct currency code and precision.

## Artifact

- `artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/latest_gap_atlas.json`

## Decision Label

`tool-foundry ready`
