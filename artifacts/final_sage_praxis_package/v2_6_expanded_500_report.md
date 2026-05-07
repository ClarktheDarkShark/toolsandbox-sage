# V2.6 Expanded 500 Report

## Scope

Run the V2.6 expanded contact-scalar candidate portfolio on the non-external 500-scenario scale manifest after locking matched-gap and original250 evidence. No new tools were generated and the frozen best3 registry was not modified.

## Registries

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Expanded registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Expanded registry SHA-256 before/after: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
- Expanded tools: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`, `plan_contact_search_from_scalar_constraint`
- Generation mode: `off`

## Manifest And Run

- Manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Manifest SHA-256: `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- Manifest type: `v2_1_formal_500_nonexternal_best3_scale`
- Expanded run: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922`
- Preserved best3 500 run: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`
- Cohort quality gate: PASS
- Cohort warning: `low_expected_helper_fit_share`

## Command

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode full_benchmark \
  --manifest docs/sage_protocol/manifests/v2_1_formal_500.json \
  --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_expanded_500 \
  --dashboard-port 5683
```

Feedback packet export:

```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py \
  --run-root outputs/v2_6_expanded_500/full_benchmark_20260507_090922 \
  --run-id v2_6_expanded_500 \
  --output-root artifacts/summaries/v2_6_feedback_packets
```

## Output Paths And Hashes

- Expanded paired comparison: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/paired_comparison.json`
- Expanded paired comparison SHA-256: `1387de1f78560bbc7dcd20eb9053f3a49aa29849b3987a55a162d34acbc53e67`
- Expanded protocol manifest: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/protocol_manifest.json`
- Expanded protocol manifest SHA-256: `9e932fee845913f28ba7d93c72acef0f5bcb476200d5268ea0e737da519c967f`
- Expanded helper contribution: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/helper_contribution_summary.json`
- Expanded helper contribution SHA-256: `50be58cffe1f42185e948f59068ec0a581abfebd29a6233b8faca874733269f3`
- Expanded control cache report: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/control_cache_report.json`
- Expanded control cache report SHA-256: `d9ad79d5e686b5b9ac735c62fe6af6b4f16ca3a5a7e1be634a5e83046b452f42`
- Feedback packets: `artifacts/summaries/v2_6_feedback_packets/v2_6_expanded_500/task_feedback.jsonl`
- Feedback packets SHA-256: `e2aed8f82f47f52c1ae85f22c885132d96e3110ce8473ea5584859fec38201d6`
- Feedback summary: `artifacts/summaries/v2_6_feedback_packets/v2_6_expanded_500/feedback_summary.json`
- Feedback summary SHA-256: `c8649286bf8c3b7fad6afddc53de9c766d3d75d62fb830e132c067645c025dfb`
- Preserved best3 500 paired comparison SHA-256: `7b55d76a2879953cf3184eb1cbda20b602ec7b479b3caed8a49cc1cff766d39d`

## Dashboards

- Main dashboard: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/dashboard/index.html`
- Task focus dashboard: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922/dashboard/task_focus.html`
- Both dashboards were opened and HTTP-checked on `http://127.0.0.1:5683/`.

## Control Cache

- Control source: mixed
- Cached controls: `179`
- Fresh controls: `321`
- Cache manifest SHA-256: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Estimated cached control turns avoided: `1826`
- Cache was used task-by-task for eligible baseline tasks. SAGE/candidate scenarios were never cached.
- Confidence intervals account for cached-control variance: true
- Cohort selection influenced by cache: false

## Metrics Versus Control

- Control outcome: `0.5226`
- Expanded outcome: `0.6822`
- Expanded outcome delta: `+0.1596`
- Control canonical/reference: `0.6521`
- Expanded canonical/reference: `0.7283`
- Expanded canonical/reference delta: `+0.0762`
- Exact successes: `42 -> 96`
- Gains/regressions/preserved: `241 / 121 / 138`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS
- Route-mismatch qualified: false

## Comparison To Preserved Best3 500

- Preserved best3 500 outcome: `0.5523`
- Expanded 500 outcome: `0.6822`
- Expanded vs preserved best3 outcome delta: `+0.1299`
- Preserved best3 500 canonical/reference: `0.6957`
- Expanded 500 canonical/reference: `0.7283`
- Expanded vs preserved best3 canonical/reference delta: `+0.0326`
- Preserved best3 exact successes: `76`
- Expanded exact successes: `96`
- Exact success delta: `+20`
- Preserved best3 runtime exceptions: `0`
- Expanded runtime exceptions: `0`

## Helper-Fit Feedback Metric

- Preserved best3 500 no-current-helper-fit share: `67.6%` (`338 / 500`)
- Expanded 500 no-current-helper-fit share: `62.8%` (`314 / 500`)
- Relative reduction: `7.10%`
- Main mechanism movement: `contact_lookup_or_answer_field_resolution` no-fit count moved from `107` to `67`
- Safe insufficient-information no-fit count remained `119`; the expanded contact-scalar pack does not address that lane.
- Visible-not-called packets increased from `59` to `100`, mainly because contact helpers add exposure on contact-related tasks. This did not create outcome or side-effect harm in this run, but remains a routing watch item.

## Helper Contribution

- `plan_contact_lookup_query`: visible/called/VNC `24 / 14 / 10`, called outcome `+0.7238`, called canonical `+0.1398`, side-effect/runtime `0 / 0`
- `extract_contact_field_from_search_result`: visible/called/VNC `24 / 6 / 18`, called outcome `+0.5806`, called canonical `+0.0055`, side-effect/runtime `0 / 0`
- `plan_contact_search_from_scalar_constraint`: visible/called/VNC `40 / 14 / 26`, called outcome `+0.3135`, called canonical `+0.0092`, side-effect/runtime `0 / 0`
- `relative_day_time_to_timestamp`: visible/called/VNC `51 / 46 / 5`, called outcome `+0.4188`, called canonical `+0.2341`, side-effect/runtime `0 / 0`
- `resolve_search_window_or_bounds`: visible/called/VNC `94 / 43 / 51`, called outcome `+0.3029`, called canonical `+0.1869`, side-effect/runtime `0 / 0`
- `select_record_by_timestamp_extreme`: visible/called/VNC `58 / 44 / 14`, called outcome `+0.2655`, called canonical `+0.3087`, side-effect/runtime `0 / 0`

## Interpretation

The expanded V2.6 contact-scalar portfolio is scale-positive on the 500-scenario manifest: it clears the protocol gate, improves outcome and canonical/reference versus control, and exceeds the preserved best3 500 candidate score. The broad 500 helper-fit reduction is positive but below the 10% relative gap-closure threshold because this manifest is not gap-enriched and contains many safe-insufficient-information and unclassified no-fit lanes outside the contact-scalar scope.

A current-code best3 500 rerun was not executed in this campaign. Therefore, the broad 500 result should be framed as expanded-portfolio scale-positive evidence against control and preserved best3 evidence, with stochastic-run variance acknowledged. The matched gap-enriched 250 and original formal250 runs remain the cleaner helper-fit gap-closure evidence.

## 1032 Deferral

A 1032 expanded run was not launched in this campaign. Rationale: the objective was to preserve the V2.6 matched win and test broader generalization; the 500 result provides broad non-external scale evidence, while a 1032 run would add substantial live-candidate cost and includes external/sparse lanes that the contact-scalar pack does not target. This should be revisited only if a full expanded-portfolio final claim beyond best3 is required.

## Decision Label

`expanded portfolio scale-positive`

## Exact Next Action

Update the final claim summary, evidence index, limitations, final package artifacts, current state, and run ledger to separate best3 broad validation from V2.6 matched gap closure, original250 expanded validation, and expanded 500 scale-positive evidence.
