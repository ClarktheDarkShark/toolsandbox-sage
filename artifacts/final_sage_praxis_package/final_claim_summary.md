# Final Claim Summary

## Validated Broad Portfolio: Frozen Best3

The broad validated SAGE portfolio remains the frozen best3 claim registry:

- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`

## Best3 Broad Scale Evidence

| Scale | Outcome Control | Outcome SAGE | Delta | Relative Lift | Canonical Delta | Exact | Runtime | Side Effects | Quality | Protocol Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 100 | 0.4010 | 0.5357 | +0.1347 | +33.58% | +0.0911 | 16 -> 23 | 0 | 0 | pass | True |
| 250 | 0.3930 | 0.4736 | +0.0806 | +20.52% | +0.0660 | 31 -> 40 | 0 | 0 | pass | True |
| 500 | 0.4830 | 0.5523 | +0.0693 | +14.35% | +0.0331 | 60 -> 76 | 0 | 0 | pass | False |
| 1032 | 0.4324 | 0.4931 | +0.0608 | +14.05% | +0.0342 | 159 -> 195 | 0 | 0 | pass | False |

Best3 clears the primary relative task-completion lift target at 100, 250, 500, and 1,032 scenarios. The 500 and 1,032 runs do not clear the older absolute +0.08 protocol-gate threshold, so the broad claim is relative outcome/task-completion success with positive canonical/reference movement, not universal protocol-gate pass at every scale.

## V2.6 Expanded Contact-Scalar Candidate Portfolio

A separate V2.6 candidate portfolio adds three contact-scalar helpers to best3:

- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`

Registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## V2.6 Matched Gap-Closure Evidence

On a quality-gated, gap-enriched frozen250 manifest:

- Best3 run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`
- Expanded run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`
- Outcome: `0.6040 -> 0.6235`, delta `+0.0195`
- Canonical/reference: `0.7838 -> 0.8060`, delta `+0.0222`
- Exact successes: `59 -> 59`
- No-current-helper-fit: `55.2% -> 45.6%`, relative reduction `17.39%`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS for both arms

This supports a matched gap-enriched V2.6 gap-closure claim. It does not directly replace the original formal250 best3 claim or prove the original absolute `44.4% -> <=40.0%` target because the matched manifest was intentionally gap-enriched.

## V2.6 Original Formal250 Expanded Evidence

On the original formal250 manifest:

- Preserved best3 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Expanded clean rerun: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209`
- Expanded outcome vs control: `0.5986`, delta `+0.1982`
- Expanded vs preserved best3 outcome: `+0.1249`
- Expanded vs preserved best3 canonical/reference: `+0.0137`
- Exact successes best3 -> expanded: `40 -> 41`
- Feedback no-current-helper-fit: `52.0% -> 46.0%`, relative reduction `11.54%`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS

A later same-manifest best3 rerun scored `0.5626`, so the large preserved-best3 comparison should be interpreted with stochastic-run variance in mind. The direction remains positive versus both preserved best3 and later same-manifest best3 context.

## V2.6 Expanded 500 Evidence

On the non-external 500 manifest:

- Expanded run: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922`
- Expanded outcome vs control: `0.6822`, delta `+0.1596`
- Expanded canonical/reference delta vs control: `+0.0762`
- Exact successes: `42 -> 96`
- Expanded vs preserved best3 500 outcome: `+0.1299`
- Expanded vs preserved best3 500 canonical/reference: `+0.0326`
- Expanded vs preserved best3 exact successes: `+20`
- Feedback no-current-helper-fit: `67.6% -> 62.8%`, relative reduction `7.10%`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS

The expanded portfolio is scale-positive at 500. The broad 500 helper-fit reduction is positive but below 10% because the 500 manifest includes many no-fit lanes outside the contact-scalar scope.

## Final Interpretation

The frozen best3 portfolio remains the broad, locked claim portfolio. V2.6 adds strong secondary evidence that contact-scalar helpers can close a targeted helper-fit gap and generalize positively to original250 and 500-scale validation without runtime or side-effect harm. The expanded portfolio should be treated as a validated V2.6 candidate portfolio, not as a replacement for the protected best3 broad claim unless a future current-code best3 matched rerun and optional 1032 expanded validation are explicitly performed.

## Decision Label

`expanded portfolio scale-positive; best3 broad claim preserved`
