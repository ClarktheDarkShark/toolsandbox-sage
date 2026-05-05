# V2.1 Frozen Best3 / Expanded Portfolio 100 Report

## Decision Label
`scale gate passed; best3 remains validated portfolio`

## Portfolio Decision
Expanded V2.1 candidates did not confirm additive value over frozen best3. This run therefore scales the protected frozen best3 portfolio, not an expanded portfolio.

## Registry
- Registry path: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Generation mode: `OFF`
- Registry entries: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`

## Command
`conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_formal100_clean_20260504_025812/cohort_manifest.json --mode validate_100 --registry-dir artifacts/registry_candidates/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423 --output-root outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423 --artifact-root artifacts --generation off --parallel-arms --control-cache use-if-eligible'`

## Run Artifacts
- Run root: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
- Manifest: `artifacts/summaries/v2_formal100_clean_20260504_025812/cohort_manifest.json`
- Manifest SHA-256: `3133a0ff6a96f0a492e9e9b12e81bfaebbe8a228e075486e153a1b4850a1b707`
- Protocol manifest: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/protocol_manifest.json`
- Paired comparison: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/paired_comparison.json`
- Helper contribution: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/helper_contribution_summary.json`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/index.html`
- Task-focus dashboard: `http://127.0.0.1:5520/outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/task_focus.html`

## Cohort Quality
- Status: `pass`
- Failures: `[]`
- Warnings: `[]`
- Scenarios: `100`
- Distinct base families: `21`
- Largest family variant count/share: `5` / `5.00%`
- No-current-helper-fit share: `28.00%`

## Control Cache
- Mode: `use-if-eligible`
- Source: `fresh`
- Cached / fresh tasks: `0` / `100`
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | `0.4010` | `0.5357` | `0.1347` |
| Relative outcome lift |  |  | `33.58%` |
| Canonical/reference similarity | `0.7406` | `0.8317` | `0.0911` |
| Exact successes | `16` | `23` | `7` |

## Gains / Regressions / Preserved
- Canonical/reference: `50 / 14 / 36`
- Outcome/task-completion: `39 / 15 / 38`

## Safety and Accounting
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Route-mismatch qualified: `False`
- Protocol gate passed: `True`
- Protocol gate reasons: `[]`

## Helper Contribution
| Helper | Visible | Called | VNC | Failed | Called Outcome Delta | Called Canonical Delta | Side Effects | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 15 | 15 | 0 | 0 | `0.1398` | `0.0377` | 0 | 0 |
| `resolve_search_window_or_bounds` | 39 | 26 | 13 | 0 | `0.2775` | `0.2209` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 15 | 15 | 0 | 0 | `0.2408` | `0.2662` | 0 | 0 |

## Interpretation
The primary task-completion metric is positive at this scale. Canonical/reference similarity is also positive. Protocol gate status is reported separately because it uses older absolute-threshold logic and, for larger runs, may fail despite a relative outcome lift above the project target.

## Exact Next Action
Use frozen best3 as the validated portfolio. Do not promote V2.1 generated candidates until a future candidate beats best3 with natural calls and positive called-subset outcome.
