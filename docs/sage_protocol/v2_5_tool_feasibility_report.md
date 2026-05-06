# V2.5 Tool Feasibility Report

## Objective

Score candidate designs before generation to avoid repeating known adoption, callability, value, and safety failures.

| Design | Cluster | Type | Score | Decision | Main advantage |
|---|---|---|---:|---|---|
| `resolve_location_lookup_field` | `location_field_answer_resolution` | `narrow visible payload field resolver` | 70 | `reject_exhausted_or_parked_cluster` | Extracts only address or phone-number fields from visible location lookup payloads, avoiding broad service-answer extraction errors. |
| `resolve_temperature_answer_unit` | `temperature_unit_answer_resolution` | `answer-only scalar calculator` | 68 | `reject_exhausted_or_parked_cluster` | Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads. |
| `prepare_temperature_conversion_args` | `temperature_unit_answer_resolution` | `argument preparer for canonical unit conversion` | 66 | `reject_exhausted_or_parked_cluster` | Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call. |
| `format_calculated_distance_km` | `distance_answer_resolution` | `unit-safe scalar answer formatter` | 55 | `reject_exhausted_or_parked_cluster` | Formats calculate_lat_lon_distance output as kilometers by default and only converts units when explicitly requested, preventing freeform-unit mistakes. |
| `prepare_direct_contact_action_kwargs` | `direct_side_effect_no_helper` | `scalar side-effect kwargs preparer` | 53 | `reject_exhausted_or_parked_cluster` | Compiles explicit user-provided scalar action fields into the exact original ToolSandbox side-effect kwargs while preserving the final side-effect call. |
| `normalize_currency_answer` | `currency_answer_normalization` | `scalar answer formatter` | 51 | `reject_before_generation` | Formats visible convert_currency output with correct currency code and precision. |

## Decision Label

`needs new gap atlas`
