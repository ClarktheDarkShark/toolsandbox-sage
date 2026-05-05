# V2.1 Formal 500 Report

## Decision Label
`formal 500 positive; proceed to full-benchmark 1000+`

## Portfolio Decision
Expanded V2.1 candidates did not confirm additive value over frozen best3. This run therefore scales the protected frozen best3 portfolio, not an expanded portfolio.

## Registry
- Registry path: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Generation mode: `OFF`
- Registry entries: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`

## Command
`conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest docs/sage_protocol/manifests/v2_1_formal_500.json --mode full_benchmark --registry-dir artifacts/registry_frozen_best3_claim --output-root outputs/v2_1_formal500_best3_parallel_20260504_232126 --artifact-root artifacts --generation off --parallel-arms --resume-run-root outputs/v2_1_formal500_best3_20260504_231332/full_benchmark_20260504_231335 --control-cache use-if-eligible'`

## Run Artifacts
- Run root: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Manifest note: committed manifest is compacted to scenario names but preserves the exact scenario set.
- Manifest SHA-256: `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- Protocol manifest: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/protocol_manifest.json`
- Paired comparison: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/paired_comparison.json`
- Helper contribution: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/helper_contribution_summary.json`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/dashboard/index.html`
- Task-focus dashboard: `http://127.0.0.1:5520/outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130/dashboard/task_focus.html`

## Cohort Quality
- Status: `pass`
- Failures: `[]`
- Warnings: `[]`
- Scenarios: `500`
- Distinct base families: `54`
- Largest family variant count/share: `12` / `2.40%`
- No-current-helper-fit share: `40.00%`

## Control Cache
- Mode: `use-if-eligible`
- Source: `fresh`
- Cached / fresh tasks: `0` / `500`
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | `0.4830` | `0.5523` | `0.0693` |
| Relative outcome lift |  |  | `14.35%` |
| Canonical/reference similarity | `0.6626` | `0.6957` | `0.0331` |
| Exact successes | `60` | `76` | `16` |

## Gains / Regressions / Preserved
- Canonical/reference: `184 / 117 / 199`
- Outcome/task-completion: `126 / 88 / 170`

## Safety and Accounting
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Route-mismatch qualified: `False`
- Protocol gate passed: `False`
- Protocol gate reasons: `['confirmation_outcome_delta_below_0_08']`

## Helper Contribution
| Helper | Visible | Called | VNC | Failed | Called Outcome Delta | Called Canonical Delta | Side Effects | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 51 | 47 | 4 | 0 | `-0.0310` | `-0.0348` | 0 | 0 |
| `resolve_search_window_or_bounds` | 94 | 41 | 53 | 0 | `0.1751` | `0.1879` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 58 | 42 | 16 | 0 | `0.4332` | `0.3691` | 0 | 0 |

## Interpretation
The primary task-completion metric is positive at this scale. Canonical/reference similarity is also positive. Protocol gate status is reported separately because it uses older absolute-threshold logic and, for larger runs, may fail despite a relative outcome lift above the project target.

## Exact Next Action
Use frozen best3 as the validated portfolio. Do not promote V2.1 generated candidates until a future candidate beats best3 with natural calls and positive called-subset outcome.
