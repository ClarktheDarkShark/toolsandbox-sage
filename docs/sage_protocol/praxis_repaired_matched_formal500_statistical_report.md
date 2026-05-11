# Praxis Repaired Matched Formal500 Statistical Report

Status: repaired Praxis registry-only candidate passed matched formal500 safety and reproduced outcome lift over best3 and V2.6 under review conditions.

Outcome/task completion is primary. Canonical/reference and exact success are secondary.

## Formal500 Table

| Arm | Outcome | Run-vs-control outcome lift | Canonical | Exact successes | Runtime exceptions | Helper side-effect failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best3 reference | 0.659956 | 0.065084 | 0.704683 | 90 | 0 | 0 |
| V2.6 reference | 0.668039 | 0.073167 | 0.728769 | 97 | 0 | 0 |
| Praxis repaired registry-only BridgePack v2 | 0.706948 | 0.112076 | 0.724125 | 109 | 0 | 0 |

## Pairwise Candidate Comparisons

| Comparison | Outcome diff | 95% CI | p-value | Canonical diff | Exact diff |
| --- | ---: | --- | ---: | ---: | ---: |
| v2_6 minus best3 | 0.008083 | [-0.025245, 0.042178] | 0.6545 | 0.024086 | 0.014000 |
| praxis minus best3 | 0.046991 | [0.008387, 0.086278] | 0.0187 | 0.019441 | 0.038000 |
| praxis minus v2_6 | 0.038909 | [0.001856, 0.075806] | 0.0463 | -0.004644 | 0.024000 |

## Helper Visibility And Called-Subset Contribution

| Arm | Visible | Called | Visible-not-called | Route mismatch qualified | Top called helpers |
| --- | ---: | ---: | ---: | --- | --- |
| best3 reference | 203 | 132 | 71 | False | resolve_search_window_or_bounds: 45/94 called/visible, called outcome delta 0.1907; relative_day_time_to_timestamp: 44/51 called/visible, called outcome delta 0.2086; select_record_by_timestamp_extreme: 43/58 called/visible, called outcome delta 0.3611 |
| V2.6 reference | 291 | 161 | 130 | False | relative_day_time_to_timestamp: 45/51 called/visible, called outcome delta 0.3062; resolve_search_window_or_bounds: 44/94 called/visible, called outcome delta 0.1527; select_record_by_timestamp_extreme: 43/58 called/visible, called outcome delta 0.3072; plan_contact_lookup_query: 13/24 called/visible, called outcome delta -0.1331; plan_contact_search_from_scalar_constraint: 9/40 called/visible, called outcome delta -0.1410; extract_contact_field_from_search_result: 7/24 called/visible, called outcome delta -0.4188 |
| Praxis repaired registry-only BridgePack v2 | 530 | 193 | 337 | False | relative_day_time_to_timestamp: 45/51 called/visible, called outcome delta 0.3387; resolve_search_window_or_bounds: 39/106 called/visible, called outcome delta 0.1346; select_record_by_timestamp_extreme: 25/58 called/visible, called outcome delta 0.2058; days_between_timestamps: 24/24 called/visible, called outcome delta 0.0124; select_message_content_by_recency: 12/52 called/visible, called outcome delta 0.5134; plan_contact_lookup_query: 12/24 called/visible, called outcome delta 0.1688 |

No-current-helper-fit and detailed route-mismatch subset metrics were not emitted by this review runtime; the report records that absence rather than deriving them from labels or traces.

## Safety

- Runtime exceptions: best3=0, V2.6=0, Praxis=0.
- Helper side-effect preservation failures: best3=0, V2.6=0, Praxis=0.
- Safety conclusion: zero runtime exceptions and zero helper side-effect preservation failures for repaired Praxis, best3, and V2.6.

## Cache And Leakage

- Controls were served from the task-level control cache for all 500 tasks in every arm.
- Candidate/SAGE arms were fresh, OpenAI response cache was disabled, generation was off, and routing evidence was disabled.
- Diagnostic force-call environment variables were absent.
- No scenario selection was based on cache availability.

## Treatment Classification

Repaired Praxis is classified as a registry-only helper-contract repair under the protected-base final-hardening runtime. No actor/router bridge policy was imported for this matched formal500 run; routing evidence was disabled.
