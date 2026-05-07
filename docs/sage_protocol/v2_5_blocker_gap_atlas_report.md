# V2.5 Blocker-Aware Gap Atlas Report

## Objective

Build a blocker-aware gap atlas from best3 and V2.x evidence, separating adoption, callability, value, and safety failures before spending on new runs.

## Ranked Clusters

| Cluster | Status | Scenarios | Families | Best3 failures | Best3 regressions | No-fit | Additive score | Prior blocker |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `best3_covered` | excluded_or_parked | 774 | 16 | 550 | 133 | 0 | 2114 | best3-covered |
| `visible_record_selector` | candidate_ranked | 286 | 9 | 177 | 72 | 286 | 1486 | adoption failure |
| `dependency_precondition` | excluded_or_parked | 317 | 18 | 92 | 77 | 317 | 1154 | adoption/value/safety failure |
| `direct_side_effect_no_helper` | candidate_ranked | 104 | 4 | 24 | 29 | 104 | 473 |  |
| `insufficient_information_or_clarification` | excluded_or_parked | 172 | 11 | 0 | 0 | 172 | 331 | canonical-only/value failure after routing repair |
| `days_between_calendar_distance` | excluded_or_parked | 175 | 4 | 57 | 23 | 36 | 243 | non-additive over best3 |
| `other_no_current_helper_fit` | support_or_negative_not_primary | 72 | 2 | 30 | 15 | 72 | 198 |  |
| `temperature_unit_answer_resolution` | excluded_or_parked | 32 | 3 | 32 | 9 | 32 | 170 | value failure after callability repair |
| `distance_answer_resolution` | excluded_or_parked | 24 | 1 | 21 | 7 | 24 | 96 | useful called subset but non-additive portfolio at frozen100 |
| `currency_answer_normalization` | candidate_ranked | 16 | 2 | 0 | 0 | 16 | 87 |  |
| `recency_action_selector` | excluded_or_parked | 90 | 3 | 0 | 0 | 90 | 86 | value failure |
| `location_field_answer_resolution` | excluded_or_parked | 16 | 2 | 15 | 0 | 16 | 51 | canonical-only/value failure after fair callability test |

## Candidate Design Options

- `plan_contact_lookup_query` / `pre-search scalar lookup planner` in `visible_record_selector`: score `77`, advantage: Before search_contacts is called, deterministically converts visible scalar contact constraints into safe original search kwargs and the exact answer field needed after lookup.
- `extract_contact_field_from_search_result` / `post-search scalar field extractor` in `visible_record_selector`: score `66`, advantage: After search_contacts returns a visible contact, extracts the exact requested scalar field without the actor manually copying, reformatting, or over-answering.
- `normalize_contact_phone_number` / `answer-only scalar normalizer` in `direct_side_effect_no_helper`: score `69`, advantage: Normalizes visible phone-number strings into the leading-plus digits format expected by contact/search/send ToolSandbox calls without preparing or executing the side effect.
- `prepare_direct_contact_action_args` / `flat-scalar side-effect kwargs preparer` in `direct_side_effect_no_helper`: score `62`, advantage: Uses top-level scalar inputs instead of an opaque payload, so the acting model can call the helper with the exact user-provided action fields and receive safe original ToolSandbox kwargs.
- `prepare_direct_contact_action_kwargs` / `scalar side-effect kwargs preparer` in `direct_side_effect_no_helper`: score `53`, advantage: Compiles explicit user-provided scalar action fields into the exact original ToolSandbox side-effect kwargs while preserving the final side-effect call.
- `detect_missing_information_before_minefield` / `insufficient-information abstention guard` in `insufficient_information_or_clarification`: score `65`, advantage: Turns a visible missing-information tool failure into an explicit abstain/clarification plan before the actor calls forbidden downstream minefield tools such as distance calculation without current location.
- `resolve_temperature_answer_unit` / `answer-only scalar calculator` in `temperature_unit_answer_resolution`: score `68`, advantage: Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads.
- `prepare_temperature_conversion_args` / `argument preparer for canonical unit conversion` in `temperature_unit_answer_resolution`: score `66`, advantage: Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call.
- `format_calculated_distance_km` / `unit-safe scalar answer formatter` in `distance_answer_resolution`: score `55`, advantage: Formats calculate_lat_lon_distance output as kilometers by default and only converts units when explicitly requested, preventing freeform-unit mistakes.
- `normalize_currency_answer` / `scalar answer formatter` in `currency_answer_normalization`: score `51`, advantage: Formats visible convert_currency output with correct currency code and precision.
- `resolve_location_lookup_field` / `narrow visible payload field resolver` in `location_field_answer_resolution`: score `70`, advantage: Extracts only address or phone-number fields from visible location lookup payloads, avoiding broad service-answer extraction errors.

## Artifact

- `artifacts/summaries/v2_5_tool_foundry_v2_5_loop17_contact_lookup_planner_generate/latest_gap_atlas.json`

## Decision Label

`tool-foundry ready`
