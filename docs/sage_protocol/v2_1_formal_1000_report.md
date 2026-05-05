# V2.1 Formal 1000+ Full-Benchmark Report

## Decision Label
`full-benchmark 1000+ positive; best3 remains final portfolio`

## Portfolio Decision
Expanded V2.1 candidates did not confirm additive value over frozen best3. This run therefore scales the protected frozen best3 portfolio, not an expanded portfolio.

## Registry
- Registry path: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Generation mode: `OFF`
- Registry entries: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`

## Command
`conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json --mode full_benchmark --registry-dir artifacts/registry_frozen_best3_claim --output-root outputs/v2_1_formal1000_best3_full_20260505_004901 --artifact-root artifacts --generation off --parallel-arms --control-cache use-if-eligible --allow-contaminated-preflight'`

## Run Artifacts
- Run root: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Manifest note: committed manifest is compacted to scenario names but preserves the exact scenario set.
- Manifest SHA-256: `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`
- Protocol manifest: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/protocol_manifest.json`
- Paired comparison: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/paired_comparison.json`
- Helper contribution: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/helper_contribution_summary.json`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/dashboard/index.html`
- Task-focus dashboard: `http://127.0.0.1:5520/outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905/dashboard/task_focus.html`

## Cohort Quality
- Status: `pass`
- Failures: `[]`
- Warnings: `['external_service_cases_present']`
- Scenarios: `1032`
- Distinct base families: `77`
- Largest family variant count/share: `48` / `4.65%`
- No-current-helper-fit share: `43.41%`
- External-service warning: present and explicitly allowed for full-benchmark coverage; this run should be interpreted as broader but less controlled than the non-external 500.


## Control Cache
- Mode: `use-if-eligible`
- Source: `fresh`
- Cached / fresh tasks: `0` / `1032`
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | `0.4324` | `0.4931` | `0.0608` |
| Relative outcome lift |  |  | `14.05%` |
| Canonical/reference similarity | `0.6935` | `0.7277` | `0.0342` |
| Exact successes | `159` | `195` | `36` |

## Gains / Regressions / Preserved
- Canonical/reference: `377 / 249 / 406`
- Outcome/task-completion: `258 / 184 / 358`

## Safety and Accounting
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Route-mismatch qualified: `False`
- Protocol gate passed: `False`
- Protocol gate reasons: `['confirmation_outcome_delta_below_0_08', 'helper_call_share_below_25_percent']`

## Helper Contribution
| Helper | Visible | Called | VNC | Failed | Called Outcome Delta | Called Canonical Delta | Side Effects | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 96 | 85 | 11 | 0 | `0.1948` | `0.0787` | 0 | 0 |
| `resolve_search_window_or_bounds` | 144 | 42 | 102 | 0 | `0.0973` | `0.1562` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 128 | 94 | 34 | 0 | `0.2675` | `0.2562` | 0 | 0 |

## Interpretation
The primary task-completion metric is positive at this scale. Canonical/reference similarity is also positive. Protocol gate status is reported separately because it uses older absolute-threshold logic and, for larger runs, may fail despite a relative outcome lift above the project target.

## Exact Next Action
Use frozen best3 as the validated portfolio. Do not promote V2.1 generated candidates until a future candidate beats best3 with natural calls and positive called-subset outcome.
