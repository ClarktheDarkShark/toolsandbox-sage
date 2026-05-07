# V2.5 Tool Feasibility Report

## Objective

Score candidate designs before generation to avoid repeating known adoption, callability, value, and safety failures.

| Design | Cluster | Type | Score | Decision | Main advantage |
|---|---|---|---:|---|---|
| `plan_contact_lookup_query` | `visible_record_selector` | `pre-search scalar lookup planner` | 77 | `advance_to_generation` | Before search_contacts is called, deterministically converts visible scalar contact constraints into safe original search kwargs and the exact answer field needed after lookup. |
| `resolve_location_lookup_field` | `location_field_answer_resolution` | `narrow visible payload field resolver` | 70 | `reject_exhausted_or_parked_cluster` | Extracts only address or phone-number fields from visible location lookup payloads, avoiding broad service-answer extraction errors. |
| `normalize_contact_phone_number` | `direct_side_effect_no_helper` | `answer-only scalar normalizer` | 69 | `reject_exhausted_or_parked_cluster` | Normalizes visible phone-number strings into the leading-plus digits format expected by contact/search/send ToolSandbox calls without preparing or executing the side effect. |
| `resolve_temperature_answer_unit` | `temperature_unit_answer_resolution` | `answer-only scalar calculator` | 68 | `reject_exhausted_or_parked_cluster` | Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads. |
| `extract_contact_field_from_search_result` | `visible_record_selector` | `post-search scalar field extractor` | 66 | `advance_to_generation` | After search_contacts returns a visible contact, extracts the exact requested scalar field without the actor manually copying, reformatting, or over-answering. |
| `prepare_temperature_conversion_args` | `temperature_unit_answer_resolution` | `argument preparer for canonical unit conversion` | 66 | `reject_exhausted_or_parked_cluster` | Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call. |
| `detect_missing_information_before_minefield` | `insufficient_information_or_clarification` | `insufficient-information abstention guard` | 65 | `reject_exhausted_or_parked_cluster` | Turns a visible missing-information tool failure into an explicit abstain/clarification plan before the actor calls forbidden downstream minefield tools such as distance calculation without current location. |
| `prepare_direct_contact_action_args` | `direct_side_effect_no_helper` | `flat-scalar side-effect kwargs preparer` | 62 | `reject_exhausted_or_parked_cluster` | Uses top-level scalar inputs instead of an opaque payload, so the acting model can call the helper with the exact user-provided action fields and receive safe original ToolSandbox kwargs. |
| `format_calculated_distance_km` | `distance_answer_resolution` | `unit-safe scalar answer formatter` | 55 | `reject_exhausted_or_parked_cluster` | Formats calculate_lat_lon_distance output as kilometers by default and only converts units when explicitly requested, preventing freeform-unit mistakes. |
| `prepare_direct_contact_action_kwargs` | `direct_side_effect_no_helper` | `scalar side-effect kwargs preparer` | 53 | `reject_exhausted_or_parked_cluster` | Compiles explicit user-provided scalar action fields into the exact original ToolSandbox side-effect kwargs while preserving the final side-effect call. |
| `normalize_currency_answer` | `currency_answer_normalization` | `scalar answer formatter` | 51 | `reject_before_generation` | Formats visible convert_currency output with correct currency code and precision. |

## Decision Label

`candidate designs ready`
