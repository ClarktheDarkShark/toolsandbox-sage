# V2.5 Callability Validation Report

## Objective

Run offline schema/static validation and lightweight live validation before any micro-run.

## Accepted Candidates

- `plan_contact_lookup_query`: repair_attempted `False`, repair_succeeded `False`, validation `{'accepted': True, 'errors': (), 'source_example_count': 2, 'held_out_check_count': 1, 'negative_applicability_count': 1, 'runtime_smoke_passed': True}`, live `{'accepted': True, 'errors': [], 'grading_classification': 'canonical_preserving', 'canonical_route_substitution_risk': 'none', 'negative_abstain_count': 1, 'positive_usable_count': 3, 'warnings': []}`
- `extract_contact_field_from_search_result`: repair_attempted `False`, repair_succeeded `False`, validation `{'accepted': True, 'errors': (), 'source_example_count': 1, 'held_out_check_count': 1, 'negative_applicability_count': 1, 'runtime_smoke_passed': True}`, live `{'accepted': True, 'errors': [], 'grading_classification': 'canonical_preserving', 'canonical_route_substitution_risk': 'none', 'negative_abstain_count': 1, 'positive_usable_count': 2, 'warnings': []}`

## Parked Or Rejected Candidates

None

## Decision Label

`candidate ready for micro-run`
