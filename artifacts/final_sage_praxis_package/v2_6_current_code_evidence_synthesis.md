# V2.6 Current-Code Evidence Synthesis

## Scope

This synthesis integrates the current-code matched original250 and non-external500 validations with the preserved best3 broad evidence and locked V2.6 matched gap-enriched evidence.

No new tools were generated. The frozen best3 registry and expanded V2.6 registry were not modified.

## Current-Code Matched Run Set

| Run Set | Best3 Run | Expanded Run | Manifest | Decision |
|---|---|---|---|---|
| Original formal250 | `outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235` | `outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441` | `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json` | outcome-positive, variance-limited |
| Non-external500 | `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553` | `outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427` | `docs/sage_protocol/manifests/v2_1_formal_500.json` | outcome-positive, below 10% helper-fit closure |

## Main Current-Code Results

| Manifest | Best3 Outcome | Expanded Outcome | Outcome Delta | Best3 Canonical | Expanded Canonical | Canonical Delta | Exact Delta | No-Fit Share | Relative No-Fit Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Original250 | 0.6078 | 0.6179 | +0.0100 | 0.7679 | 0.7395 | -0.0283 | -8 | 52.0% -> 46.0% | 11.54% |
| Non-external500 | 0.6590 | 0.6692 | +0.0101 | 0.7137 | 0.7362 | +0.0225 | +1 | 67.6% -> 62.8% | 7.10% |

Safety:

- Runtime exceptions: 0 in all four current-code arms.
- Helper side-effect incidents: 0 in all four current-code arms.
- Protocol gate: PASS in all four current-code arms.
- Route-mismatch qualified: false in all four current-code arms.

## Interpretation

The expanded V2.6 contact-scalar portfolio is current-code outcome-positive on both required matched validations.

However, the 500 run does not meet the 10% helper-fit gap-closure target. The correct final framing is therefore:

1. Frozen best3 remains the broad protected claim portfolio.
2. V2.6 matched gap-enriched evidence remains the strongest helper-fit closure result: `55.2% -> 45.6%`, a 17.39% relative no-current-helper-fit reduction, with outcome `0.6040 -> 0.6235`.
3. Current-code original250 supports a positive but variance-limited expanded portfolio result: outcome improves by `+0.0100`, dynamic no-fit share improves by 11.54%, but canonical/reference and exact successes decline.
4. Current-code non-external500 supports a positive broad-scale outcome result: outcome improves by `+0.0101`, canonical/reference improves by `+0.0225`, exact successes improve by `+1`, but helper-fit reduction is 7.10%, below the 10% target.
5. The expanded portfolio should not be described as replacing best3 as the broad final portfolio. It should be described as a safe, current-code-positive, gap-improving candidate portfolio with its strongest claim on matched gap-enriched contact-scalar cohorts.

## Why The 500 Gap Target Was Not Met

The non-external500 sample has materially broader no-fit structure than the matched gap250:

- Matched gap250 has 80 contact-token scenarios and 48 message-token scenarios in 250 tasks, with explicit contact/message-positive roles.
- Non-external500 has 123 contact-token and 78 message-token scenarios in 500 tasks, but also 190 reminder-token scenarios, 119 insufficient-information-token scenarios, 56 battery-token scenarios, and 54 distinct base families.
- Contact-scalar helpers reduced feedback no-current-helper-fit by 24 tasks on 500, but the remaining no-fit pool is dominated by lanes outside the current contact-scalar abstraction.
- The broad 500 sample confirms non-harmful generalization and small outcome lift, but not enough coverage expansion for the 10% gap-closure criterion.

## Candidate Tool Findings

New contact-scalar helper behavior on 500:

| Helper | Visible | Called | VNC | Called Outcome Delta vs Control | Called Canonical Delta vs Control | Side Effect | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `plan_contact_lookup_query` | 24 | 13 | 11 | +0.5667 | +0.1070 | 0 | 0 |
| `extract_contact_field_from_search_result` | 24 | 6 | 18 | +0.4139 | +0.0055 | 0 | 0 |
| `plan_contact_search_from_scalar_constraint` | 40 | 14 | 26 | +0.3633 | +0.0124 | 0 | 0 |

Direct expanded-vs-best3 called-subset behavior on 500:

- `plan_contact_search_from_scalar_constraint` was positive: `+0.2649` mean outcome delta on its called subset.
- `plan_contact_lookup_query` and `extract_contact_field_from_search_result` were mixed/negative versus best3 on their called subsets despite positive contribution versus control.
- This suggests the scalar planner is the stronger additive design at 500, while the older two-step contact pack needs caution before any broad promotion claim.

## Deferred Runs

Matched gap250 current-code rerun was deferred.

Rationale:

- Locked matched-gap evidence already exists.
- The locked matched gap250 result showed expanded outcome `0.6235` vs best3 `0.6040`.
- No-current-helper-fit improved `55.2% -> 45.6%`.
- Relative gap reduction was `17.39%`.
- Both arms had runtime exceptions `0`, helper side-effect incidents `0`, and protocol PASS.
- The current-code original250 and 500 matched runs were the higher-value missing validations for the final report.

Expanded 1032 current-code validation was deferred.

Rationale:

- The current-code non-external500 matched run provides broad non-external scale evidence.
- 1032 includes sparse/external lanes not specifically targeted by the contact-scalar tools.
- Prior best3 1032 evidence remains the broad full-benchmark claim.
- A 1032 expanded matched pair would add substantial cost and is not necessary for the current final framing.

## Final Decision Label

`expanded portfolio non-harmful but variance-limited`

The final report should preserve best3 as the broad validated portfolio and present V2.6 as safe, current-code-positive, and gap-improving, with a matched gap-enriched helper-fit closure claim but no broad 500 claim that the 10% helper-fit closure target was met.
