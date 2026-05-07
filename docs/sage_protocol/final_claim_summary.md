# Final Claim Summary

## Current Validated Portfolio
- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Expanded V2.1 candidates were tested and parked; frozen best3 remains the validated portfolio.

## Scale Evidence
| Scale | Outcome Control | Outcome SAGE | Delta | Relative Lift | Canonical Delta | Exact | Runtime | Side Effects | Quality | Protocol Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 100 | 0.4010 | 0.5357 | +0.1347 | +33.58% | +0.0911 | 16 -> 23 | 0 | 0 | pass | True |
| 250 | 0.3930 | 0.4736 | +0.0806 | +20.52% | +0.0660 | 31 -> 40 | 0 | 0 | pass | True |
| 500 | 0.4830 | 0.5523 | +0.0693 | +14.35% | +0.0331 | 60 -> 76 | 0 | 0 | pass | False |
| 1032 | 0.4324 | 0.4931 | +0.0608 | +14.05% | +0.0342 | 159 -> 195 | 0 | 0 | pass | False |

## Claim
SAGE best3 clears the primary relative task-completion lift target at 100, 250, 500, and 1,032 scenarios. The 500 and 1,032 runs do not clear the older absolute +0.08 protocol-gate threshold, so the final claim should be framed as relative outcome/task-completion success with positive canonical/reference movement, not as universal protocol-gate pass at every scale.

## Limitations
- Control-cache compatibility remained strict; scale runs used fresh controls because manifest checksums differed.
- The 1,032 full-benchmark run includes external-service lanes and should be separated from the non-external 500 evidence.
- No V2.1 generated candidate is promoted; accepted-but-uncalled or negative force-call candidates remain parked.

## Decision Label
`full-benchmark 1000+ positive; best3 remains final portfolio`

## V2.6 Expanded Portfolio Matched Gap-Closure Evidence

A separate V2.6 candidate portfolio was validated on a quality-gated, gap-enriched frozen250 manifest. This does not modify the protected best3 formal evidence.

### Expanded Candidate Portfolio
- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`
- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`

Registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

### Matched Frozen250 Result
- Manifest: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`
- Best3 run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`
- Expanded run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`
- Outcome: `0.6040 -> 0.6235`, delta `+0.0195`
- Canonical/reference: `0.7838 -> 0.8060`, delta `+0.0222`
- Exact successes: `59 -> 59`
- No-current-helper-fit: `55.2% -> 45.6%`, relative reduction `17.39%`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS for both arms

### Interpretation
The V2.6 expanded portfolio meets the matched gap-enriched frozen250 gap-closure target while preserving task-completion outcome versus best3. It should be described as matched-manifest gap-closure evidence, not as a replacement for the original formal250 best3 claim. The original absolute formal250 helper-fit target `44.4% -> <=40.0%` was not directly tested by this gap-enriched 250 run.
