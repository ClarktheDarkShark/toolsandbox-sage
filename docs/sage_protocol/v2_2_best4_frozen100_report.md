# V2.2 Best4 Frozen100 Report

## Objective

Validate whether `days_between_timestamps` remains additive when combined with frozen best3 on the preserved formal100 manifest.

## Registry And Manifest

- Registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`
- Registry SHA-256: `e497d29b7b31b89b9368af7c9327679086a881f8e9c62a182ca07b25f18f7834`
- Manifest: `artifacts/summaries/v2_formal100_clean_20260504_025812/cohort_manifest.json`
- Generation mode: `OFF`
- Frozen best3 registry modified: `no`
- Best3 comparison run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
- Best4 run: `outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140`
- Dashboard: `http://127.0.0.1:5614/outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140/dashboard/index.html`
- Task focus dashboard: `http://127.0.0.1:5614/outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140/dashboard/task_focus.html`
- Control cache: `mixed`; cached `72`, fresh `28`
- Cohort quality gate: `pass`

## Metrics

| Portfolio | Candidate outcome | Outcome delta vs control | Canonical delta | Exact successes | Gains / regressions / preserved | Runtime exceptions |
|---|---:|---:|---:|---:|---:|---:|
| Best3 formal100 | 0.5357 | +0.1347 | +0.0911 | 16 -> 23 | 39 / 15 / 38 | 0 |
| Best4 frozen100 | 0.4685 | +0.0679 | +0.0696 | 14 -> 19 | 39 / 30 / 23 | 0 |

Best4 vs preserved best3 on the same formal100 manifest:

- Candidate outcome difference: `-0.0672`
- Outcome-delta difference: `-0.0668`
- Canonical-delta difference: `-0.0215`
- Exact-success difference: `-4`

## Helper Contribution

| Helper | Visible | Called | VNC | Called-subset outcome | Called-subset canonical | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `days_between_timestamps` | 3 | 3 | 0 | +0.1111 | -0.2601 | 0 | 0 |
| `relative_day_time_to_timestamp` | 15 | 15 | 0 | +0.2248 | +0.1515 | 0 | 0 |
| `resolve_search_window_or_bounds` | 39 | 28 | 11 | +0.1234 | +0.1674 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 15 | 14 | 1 | +0.3115 | +0.2950 | 0 | 0 |

## Route-Mismatch Accounting

`days_between_timestamps` retained the expected route-mismatch pattern: called-subset outcome was positive while called-subset canonical was negative. That is correctly accounted for as helper substitution, but it does not rescue the Best4 portfolio because the portfolio underperformed best3 on overall formal100 outcome and exact successes.

## Decision Label

`best4 not additive`

## Exact Next Action

Do not run frozen250 for Best4. Keep `days_between_timestamps` as a confirmed narrow V2.2 standalone tool, but do not promote it into the main validated portfolio. Preserve best3 as the final validated portfolio unless a future fresh gap atlas identifies a non-parked, additive candidate.
