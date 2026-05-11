# Praxis Matched Formal500 Statistical Report

Status: blocked for protected-claim promotion because the Praxis registry-only run produced helper side-effect preservation failures under the protected-base checker.

Outcome/task completion is primary. Canonical/reference and exact success are secondary.

## Formal500 Table

| Arm | Outcome | Run-vs-control outcome lift | Canonical | Exact successes | Runtime exceptions | Helper side-effect failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best3 reference | 0.655285 | 0.060413 | 0.722734 | 94 | 0 | 0 |
| V2.6 reference | 0.664286 | 0.069414 | 0.713519 | 89 | 0 | 0 |
| Praxis frozen BridgePack | 0.696169 | 0.101297 | 0.722681 | 105 | 0 | 13 |

## Pairwise Candidate Comparisons

| Comparison | Outcome diff | 95% CI | p-value | Canonical diff | Exact diff |
| --- | ---: | --- | ---: | ---: | ---: |
| v2_6 minus best3 | 0.009002 | [-0.026157, 0.043690] | 0.6029 | -0.009215 | -0.010000 |
| praxis minus best3 | 0.040884 | [0.004697, 0.078220] | 0.0283 | -0.000054 | 0.022000 |
| praxis minus v2_6 | 0.031883 | [-0.009376, 0.072576] | 0.1199 | 0.009162 | 0.032000 |

## Helper Visibility And Called-Subset Contribution

| Arm | Visible | Called | Visible-not-called | Route mismatch qualified | Top called helpers |
| --- | ---: | ---: | ---: | --- | --- |
| best3 reference | 203 | 123 | 80 | False | relative_day_time_to_timestamp: 45/51 called/visible, called outcome delta 0.2275; resolve_search_window_or_bounds: 41/94 called/visible, called outcome delta 0.1154; select_record_by_timestamp_extreme: 37/58 called/visible, called outcome delta 0.3354 |
| V2.6 reference | 291 | 163 | 128 | False | relative_day_time_to_timestamp: 47/51 called/visible, called outcome delta 0.2607; resolve_search_window_or_bounds: 43/94 called/visible, called outcome delta 0.1631; select_record_by_timestamp_extreme: 42/58 called/visible, called outcome delta 0.2805; plan_contact_search_from_scalar_constraint: 13/40 called/visible, called outcome delta 0.0588; plan_contact_lookup_query: 11/24 called/visible, called outcome delta 0.3186; extract_contact_field_from_search_result: 7/24 called/visible, called outcome delta 0.1372 |
| Praxis frozen BridgePack | 552 | 205 | 347 | False | relative_day_time_to_timestamp: 46/51 called/visible, called outcome delta 0.2354; resolve_search_window_or_bounds: 36/106 called/visible, called outcome delta 0.0854; days_between_timestamps: 24/24 called/visible, called outcome delta 0.0124; select_record_by_timestamp_extreme: 20/58 called/visible, called outcome delta 0.0752; plan_contact_relationship_batch_update: 16/19 called/visible, called outcome delta 0.2552; plan_contact_lookup_query: 14/24 called/visible, called outcome delta 0.0455 |

No-current-helper-fit and detailed route-mismatch subset metrics were not emitted by this review runtime; the report records that absence rather than deriving them from labels or traces.

## Safety

- Runtime exceptions: best3=0, V2.6=0, Praxis=0.
- Helper side-effect preservation failures: best3=0, V2.6=0, Praxis=13.
- Because Praxis has nonzero helper side-effect preservation failures, this review classifies Praxis as not protected-claim ready in registry-only form.

## Cache And Leakage

- Controls were served from the task-level control cache for all 500 tasks in every arm.
- Candidate/SAGE arms were fresh, OpenAI response cache was disabled, generation was off, and routing evidence was disabled.
- Diagnostic force-call environment variables were absent.
- No scenario selection was based on cache availability.

## Treatment Classification

Praxis shows registry-only outcome lift under the protected-base final-hardening runtime, but the same run has side-effect preservation failures. The result is therefore promising but blocked for protected review until the failing helpers are redesigned or an explicitly audited bridge-policy/checker treatment is validated with zero side-effect incidents.
