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

## Current-Code Matched Evidence

The current-code matched campaign reran best3 and expanded V2.6 from the same commit on the same manifests, generation OFF.

| Manifest | Best3 Outcome | Expanded Outcome | Delta | Best3 Canonical | Expanded Canonical | Delta | Exact Delta | Dynamic No-Fit | Relative No-Fit Reduction | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| Original250 | 0.6078 | 0.6179 | +0.0100 | 0.7679 | 0.7395 | -0.0283 | -8 | 52.0% -> 46.0% | 11.54% | positive, variance-limited |
| Non-external500 | 0.6590 | 0.6692 | +0.0101 | 0.7137 | 0.7362 | +0.0225 | +1 | 67.6% -> 62.8% | 7.10% | positive, below 10% gap target |

Safety in current-code matched runs:

- Runtime exceptions: `0` in all four arms.
- Helper side-effect incidents: `0` in all four arms.
- Protocol gate: PASS in all four arms.

The current-code evidence shows the expanded V2.6 portfolio is non-harmful and modestly outcome-positive on original250 and non-external500. It does not show broad 500 helper-fit closure at the 10% threshold.

## Final Interpretation

The frozen best3 portfolio remains the broad, locked claim portfolio.

V2.6 adds secondary evidence that contact-scalar helpers can close a targeted helper-fit gap and can generalize non-harmfully to current-code original250 and non-external500 validation. The expanded portfolio should be described as safe, current-code-positive, and gap-improving, but not as a replacement for the protected best3 broad claim because the broader 500 helper-fit reduction is `7.10%`, below the 10% target.

The final statistical supplement `docs/sage_protocol/final_statistical_analysis_report.md` reports paired bootstrap confidence intervals and paired randomization tests from the stored artifacts. Those intervals condition on stored baseline artifacts; task-level cached-control variance is summarized separately and should not be overclaimed as fully modeled stochastic uncertainty.

## Decision Label

`expanded portfolio non-harmful but variance-limited; best3 broad claim preserved`
