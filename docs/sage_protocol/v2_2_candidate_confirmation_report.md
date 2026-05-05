# V2.2 Candidate Confirmation Report

## Confirmed Candidate

`days_between_timestamps`

## Confirmation Run

- Run: `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`
- Manifest: `artifacts/summaries/v2_2_days_between_confirmation60_20260505_081500/cohort_manifest.json`
- Registry: `artifacts/registry_candidates/v2_2_days_between_confirmation60_20260505_081500/registry_manifest.json`
- Registry SHA-256: `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`
- Generation: `OFF`
- Best3 masked: yes
- Cohort quality: `PASS`
- Dashboard: `http://127.0.0.1:5592/outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108/dashboard/index.html`
- Task focus: `http://127.0.0.1:5592/outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108/dashboard/task_focus.html`
- Control cache: `fresh`, cached `0`, fresh `60`

## Metrics

- Outcome delta: `0.08905168905168905`
- Canonical/reference delta: `-0.05996342339399075`
- Exact successes: `4 -> 4`
- Protocol gate: `False`
- Protocol gate reasons: `['outcome_gains_do_not_exceed_regressions', 'non_positive_canonical_delta', 'gains_do_not_exceed_regressions', 'exact_successes_not_improved', 'gain_regression_ratio_below_1_4', 'helper_call_share_below_25_percent']`
- Route mismatch qualified at run level: `False`
- Helper route mismatch at called subset: `{'helper_substitution_likely': True, 'reason': 'called_subset_outcome_positive_but_canonical_negative_or_regressive'}`

## Helper Contribution

| `days_between_timestamps` | 14 | 14 | 0 | 0.10714285714285714 | -0.2102519581336632 | True | 0 | 0 |

## Decision

`days_between_timestamps` confirms under V2.2 candidate rules because it is naturally called, has positive called-subset outcome, positive overall outcome, zero runtime incidents, zero side-effect incidents, and safe hidden behavior on negatives. It does not produce a canonical benchmark pass; the canonical loss is reported as helper-substitution route-mismatch evidence.

## Decision Label

`candidate confirmed`
