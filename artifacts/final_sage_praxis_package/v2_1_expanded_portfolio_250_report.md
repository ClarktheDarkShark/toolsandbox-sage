# V2.1 Frozen Best3 / Expanded Portfolio 250 Report

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
`conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --mode validate_250 --registry-dir artifacts/registry_candidates/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217 --output-root outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217 --artifact-root artifacts --generation off --parallel-arms --control-cache use-if-eligible'`

## Run Artifacts
- Run root: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Protocol manifest: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/protocol_manifest.json`
- Paired comparison: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/paired_comparison.json`
- Helper contribution: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/helper_contribution_summary.json`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/index.html`
- Task-focus dashboard: `http://127.0.0.1:5520/outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/task_focus.html`

## Cohort Quality
- Status: `pass`
- Failures: `[]`
- Warnings: `[]`
- Scenarios: `250`
- Distinct base families: `32`
- Largest family variant count/share: `8` / `3.20%`
- No-current-helper-fit share: `44.40%`

## Control Cache
- Mode: `use-if-eligible`
- Source: `fresh`
- Cached / fresh tasks: `0` / `250`
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | `0.3930` | `0.4736` | `0.0806` |
| Relative outcome lift |  |  | `20.52%` |
| Canonical/reference similarity | `0.6659` | `0.7319` | `0.0660` |
| Exact successes | `31` | `40` | `9` |

## Gains / Regressions / Preserved
- Canonical/reference: `102 / 53 / 95`
- Outcome/task-completion: `73 / 40 / 89`

## Safety and Accounting
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Route-mismatch qualified: `False`
- Protocol gate passed: `True`
- Protocol gate reasons: `[]`

## Helper Contribution
| Helper | Visible | Called | VNC | Failed | Called Outcome Delta | Called Canonical Delta | Side Effects | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 32 | 29 | 3 | 0 | `0.1389` | `0.0161` | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 42 | 30 | 0 | `0.2480` | `0.1616` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 27 | 5 | 0 | `0.1188` | `0.2746` | 0 | 0 |

## Interpretation
The primary task-completion metric is positive at this scale. Canonical/reference similarity is also positive. Protocol gate status is reported separately because it uses older absolute-threshold logic and, for larger runs, may fail despite a relative outcome lift above the project target.

## Exact Next Action
Use frozen best3 as the validated portfolio. Do not promote V2.1 generated candidates until a future candidate beats best3 with natural calls and positive called-subset outcome.
