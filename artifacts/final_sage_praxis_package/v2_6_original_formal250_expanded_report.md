# V2.6 Original Formal250 Expanded Registry Report

## Scope

Validate the V2.6 expanded contact-scalar candidate portfolio on the original formal250 manifest, without modifying the frozen best3 registry or locked best3 evidence.

## Registries

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Expanded registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Expanded registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
- Expanded tools: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`, `plan_contact_search_from_scalar_constraint`
- Generation mode: `off`

## Manifest And Runs

- Original formal250 manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Preserved best3 formal250 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Expanded clean rerun: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209`
- Initial expanded run not used for claims: `outputs/v2_6_original_formal250_expanded/validate_250_20260507_072858`
- Reason initial run was not used: four transient OpenAI API connection exceptions occurred in candidate best3-helper lanes; the clean rerun had zero runtime exceptions and is the claim run.

## Commands

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode validate_250 \
  --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json \
  --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_original_formal250_expanded_rerun \
  --dashboard-port 5682
```

Feedback packet export:

```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py \
  --run-root outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209 \
  --run-id v2_6_original_formal250_expanded_rerun \
  --output-root artifacts/summaries/v2_6_feedback_packets
```

## Output Paths And Hashes

- Expanded paired comparison: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/paired_comparison.json`
- Expanded paired comparison SHA-256: `71a23f42b61be15935247cedb0ebb55dc4eb11ac4c42ebb53754b3cdcc7af7a7`
- Expanded protocol manifest: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/protocol_manifest.json`
- Expanded protocol manifest SHA-256: `bda6b4c9b2ee633f309b4e4aa6087a9daac51c4326f00799780f7fa6b054c8b9`
- Expanded helper contribution: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/helper_contribution_summary.json`
- Expanded helper contribution SHA-256: `4b08b0f108434025c6df64e166185078aed29dd16339f07043d0690fb0ca5eac`
- Expanded control cache report: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/control_cache_report.json`
- Expanded control cache report SHA-256: `99dde18d15e532e9afce4812e90dba36e5123503df99fad741025bbf252651e0`
- Feedback packets: `artifacts/summaries/v2_6_feedback_packets/v2_6_original_formal250_expanded_rerun/task_feedback.jsonl`
- Feedback packets SHA-256: `aabbc772844bb3b55af68b32ea9bdfeb95c7132732f66375d5d1c73b7c3aa99d`
- Feedback summary: `artifacts/summaries/v2_6_feedback_packets/v2_6_original_formal250_expanded_rerun/feedback_summary.json`
- Feedback summary SHA-256: `6111beb584ef9fcaf91b137128fabc85a9cb52ef38d0aea7545c34ac047fad76`
- Preserved best3 paired comparison SHA-256: `8c967688a806ef276419d40a51fded941af13f5de9a5519714c560d5e0bb8f80`

## Dashboards

- Main dashboard: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/dashboard/index.html`
- Task focus dashboard: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209/dashboard/task_focus.html`
- Both dashboards were opened on `http://127.0.0.1:5682/`.

## Control Cache And Cohort Quality

- Control source: cached
- Cached controls: `250`
- Fresh controls: `0`
- Cache manifest SHA-256: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Cache was used task-by-task for eligible baseline tasks only; SAGE/candidate execution was not cached.
- Cohort quality gate: PASS

## Metrics Versus Control

- Control outcome: `0.4004`
- Expanded outcome: `0.5986`
- Expanded outcome delta: `+0.1982`
- Control canonical/reference: `0.6818`
- Expanded canonical/reference: `0.7456`
- Expanded canonical/reference delta: `+0.0637`
- Exact successes: `14 -> 41`
- Gains/regressions/preserved: `133 / 78 / 39`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS
- Route-mismatch qualified: false

## Comparison To Preserved Original Best3 Formal250

- Best3 outcome: `0.4736`
- Expanded outcome: `0.5986`
- Expanded vs best3 outcome delta: `+0.1249`
- Best3 canonical/reference: `0.7319`
- Expanded canonical/reference: `0.7456`
- Expanded vs best3 canonical/reference delta: `+0.0137`
- Best3 exact successes: `40`
- Expanded exact successes: `41`
- Exact success delta: `+1`
- Runtime exceptions: `0 -> 0`
- Helper side-effect incidents: `0 -> 0`

## Helper-Fit Feedback Metric

- Preserved best3 formal250 no-current-helper-fit share from V2.6 feedback packets: `52.0%` (`130 / 250`)
- Expanded original formal250 no-current-helper-fit share: `46.0%` (`115 / 250`)
- Relative reduction: `11.54%`
- Main mechanism movement: `contact_lookup_or_answer_field_resolution` no-fit count moved from `39` to `16`
- Safe insufficient-information no-fit count remained `48`; this remains a future gap and should not be hidden by contact-scalar claims.

## Helper Contribution

- `plan_contact_lookup_query`: visible/called/VNC `15 / 10 / 5`, called outcome `+0.4318`, called canonical `+0.2006`, side-effect/runtime `0 / 0`
- `extract_contact_field_from_search_result`: visible/called/VNC `15 / 5 / 10`, called outcome `+0.2967`, called canonical `+0.0006`, side-effect/runtime `0 / 0`
- `plan_contact_search_from_scalar_constraint`: visible/called/VNC `15 / 1 / 14`, called outcome `+0.0000`, called canonical `-0.0011`, side-effect/runtime `0 / 0`
- `relative_day_time_to_timestamp`: visible/called/VNC `32 / 27 / 5`, called outcome `+0.2033`, called canonical `+0.0947`, side-effect/runtime `0 / 0`
- `resolve_search_window_or_bounds`: visible/called/VNC `72 / 41 / 31`, called outcome `+0.3501`, called canonical `+0.1735`, side-effect/runtime `0 / 0`
- `select_record_by_timestamp_extreme`: visible/called/VNC `32 / 25 / 7`, called outcome `+0.2208`, called canonical `+0.2329`, side-effect/runtime `0 / 0`

## Same-Manifest Rerun Context

A later V2.5 same-manifest best3 rerun had higher stochastic candidate performance than the original locked formal250 best3 run:

- V2.5 same-manifest best3 rerun: `outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037`
- V2.5 same-manifest best3 outcome: `0.5626`
- V2.5 same-manifest contact-pack outcome: `0.5637`
- V2.6 expanded original250 outcome: `0.5986`

Therefore, the V2.6 original250 result is positive versus both the preserved original best3 evidence and the later same-manifest best3 rerun context, but the large `+0.1249` comparison to preserved best3 should be interpreted with stochastic-run variance in mind. The broader claim should emphasize protocol-clean safety, positive direction, helper-fit reduction, and follow-on 500 validation rather than treating one rerun delta as a deterministic effect size.

## Interpretation

The expanded contact-scalar portfolio generalizes positively to the original formal250 manifest. It improves outcome and canonical/reference versus the preserved original best3 formal250 result, preserves safety, and reduces V2.6 feedback no-current-helper-fit share by more than 10% relative on this manifest. The result is stronger than the matched gap-enriched result, but should still be reported as V2.6 candidate-portfolio evidence until the broader 500 validation is complete.

## Decision Label

`expanded portfolio generalizes to original250`

## Exact Next Action

Complete the already-launched expanded 500 validation with generation off, cache use-if-eligible, contribution export active, and dashboards opened. If expanded 500 is positive and safe, update final claim artifacts to include V2.6 as broader expanded-portfolio evidence; if not, keep the broader claim on frozen best3 and retain V2.6 as original250 plus matched gap-closure evidence.
