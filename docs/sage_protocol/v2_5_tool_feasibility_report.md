# V2.5 Tool Feasibility Report

## Objective

Score candidate designs before generation to avoid repeating known adoption, callability, value, and safety failures.

| Design | Cluster | Type | Score | Decision | Main advantage |
|---|---|---|---:|---|---|
| `resolve_temperature_answer_unit` | `temperature_unit_answer_resolution` | `answer-only scalar calculator` | 68 | `advance_to_generation` | Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads. |
| `prepare_temperature_conversion_args` | `temperature_unit_answer_resolution` | `argument preparer for canonical unit conversion` | 66 | `advance_to_generation` | Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call. |
| `format_distance_answer` | `distance_answer_resolution` | `scalar answer formatter` | 55 | `reject_before_generation` | Normalizes numeric distance precision and unit text after calculate_lat_lon_distance. |
| `normalize_currency_answer` | `currency_answer_normalization` | `scalar answer formatter` | 55 | `reject_before_generation` | Formats visible convert_currency output with correct currency code and precision. |

## Decision Label

`candidate designs ready`
