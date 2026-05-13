# Self-Evolving SAGE Mini60 Report

Status: experimental implementation proof, not protected final-claim evidence.

Date: 2026-05-12

Branch: `codex/self-evolving-sage-mini60`

## Objective

Implement and test the first executable slice of `praxis_next_gap_and_self_evolving_sage_plan.md` under a strict token-conservation setup:

- maximum sample size `60`
- agent model `gpt-4o-mini`
- user simulator model `gpt-4o-mini`
- generation model `gpt-4o-mini`
- baseline/control cache `use-if-eligible`
- candidate/SAGE task cache off
- OpenAI response cache disabled
- routing evidence disabled
- diagnostic force-call disabled

The corrected objective is stronger than the earlier recipe-pack proof: SAGE must start with no generated tools, keep generation on during the run, observe gaps online, generate and validate tools during the run, and reuse accepted tools naturally. Pre-generated tools plus generation off are not sufficient evidence for this mechanism.

## Corrected Mechanism

New implementation and repairs:

- `src/sage_ts/evaluation/gap_observer.py`
- `src/sage_ts/orchestration/self_evolving_campaign.py`
- `scripts/prepare_self_evolving_sage_mini60.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/evaluation/task_strata.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/validation/output_normalization.py`

The active live-generation loop is:

```text
gap packet
  -> ranked gap buckets
  -> contact lookup/update/search bucket selected
  -> empty generated-tool registry written
  -> natural candidate run starts with generation ON
  -> gap observations trigger online candidate births
  -> generated candidates pass static/schema/runtime validation
  -> accepted tools enter the registry
  -> routing exposes the accepted tools on later matching tasks
  -> natural calls decide whether the tool is retained, refined, or parked
```

This is now a true live tool-birth mechanism proof. The candidate registry starts as:

```json
{
  "tools": {}
}
```

Starting registry path:

`artifacts/self_evolving_sage/current_mini60_live_generation_v2/registry/registry_manifest.json`

Starting registry SHA-256:

`61468467448a94c5c6ced36d05894d7ba2e2f7501ca84270a30da1cd18a3c713`

Preparation artifact:

`artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_preparation.json`

Manifest:

`artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_manifest.json`

Manifest SHA-256:

`5337bf7bef2cb32679955bcf27b68cf06495d00c905a02c66766ae261b0176bc`

Only 24 scenarios matched the selected contact gap under the current capped manifest builder. This is therefore a `diag24` mechanism proof under the <=60 requirement, not a full 60-task claim.

## Source Inputs

- Source gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_gap_packets.json`
- Source formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Selected bucket: `contact_lookup_update_search_crud`

No labels, expected answers, hidden benchmark facts, or cache availability were used to generate tool code or select scenarios. Scenario IDs appear in the split manifest because the harness requires executable scenario names, but they are not encoded into generated tools, routing rules, or repair logic.

## Current 60-Task Live-Generation Proof

Run:

`outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507`

Dashboard:

`http://127.0.0.1:62624/outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507/dashboard/task_compare.html`

Dashboard opening policy:

- `scripts/run_sage_protocol.py` opens `task_compare.html` as the default dashboard for each run.
- `src/sage_ts/dashboard/exporters.py` starts the localhost dashboard server and, on macOS, calls `open <dashboard-url>` so the new Task Compare dashboard opens in the external browser.
- The run writes `dashboard_urls.json` with `default_dashboard: "task_compare"`.

Controls:

- control cache mode: `use-if-eligible`
- cached controls: `60`
- fresh controls: `0`
- cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- cohort selection influenced by cache: `false`

Candidate/SAGE:

- starting generated registry: empty
- starting generated registry SHA-256: `61468467448a94c5c6ced36d05894d7ba2e2f7501ca84270a30da1cd18a3c713`
- final generated registry SHA-256: `9e887a9199f53b5b1f28d7d76b158a2de6a397b617c1af8bb39932ac7bff6d0d`
- manifest SHA-256: `6038613ee3b254a4c6b2b1219feee39c9d8ac98052d9857b39f67cb06e577ced`
- generation: on
- candidate task cache: off
- OpenAI response cache: disabled
- routing evidence: disabled
- active diagnostic force env vars: none
- agent/user/generation model: `gpt-4o-mini`
- runtime exceptions: `0`
- helper side-effect incidents: `0`

Metrics:

| Metric | Baseline | SAGE | Delta |
|---|---:|---:|---:|
| Canonical/reference score | `0.755622` | `0.855260` | `+0.099638` |
| Canonical/reference lift | n/a | n/a | `+13.19%` |
| Outcome/task completion | `0.523942` | `0.667092` | `+0.143150` |
| Exact successes | `10` | `26` | `+16` |
| Canonical gains / regressions / preserved | n/a | n/a | `36 / 14 / 10` |
| Outcome gains / regressions / preserved | n/a | n/a | `26 / 12 / 7` |

Protocol gate: `PASS`.

Live accepted tools:

| Helper | Visible | Called | VNC | Called-subset canonical delta | Called-subset outcome delta | Decision |
|---|---:|---:|---:|---:|---:|---|
| `plan_contact_lookup_query` | 20 | 8 | 12 | `+0.360822` | `+0.473296` | Keep; strongest live-born lookup planner |
| `plan_contact_relationship_batch_update` | 8 | 8 | 0 | `+0.227465` | `+0.436380` | Keep; strongest live-born relationship update planner |
| `plan_contact_update_from_id` | 2 | 2 | 0 | `+0.119360` | `+0.166667` | Keep; positive called subset |
| `prepare_side_effect_args_from_selected_record` | 8 | 0 | 8 | n/a | n/a | Retain as unresolved; not promoted from this run |
| `select_action_target_by_recency` | 1 | 0 | 1 | n/a | n/a | Retain as unresolved; not promoted from this run |
| `select_record_by_timestamp_extreme` | 2 | 0 | 2 | n/a | n/a | Retain as unresolved; not promoted from this run |

The v21 run is the current positive self-evolving proof. It starts from no generated tools, keeps generation on, accepts six live-born tools, naturally calls generated tools on 18 scenarios, records zero generated-tool failures, and produces positive canonical and outcome lift under a low-cost `gpt-4o-mini` setup.

The safe remove-by-phone bridge used in this run is a documented bridge-policy repair, not a forced call path. It uses only visible tool availability and user text to avoid an invalid side-effect call when `remove_contact` is visible but `search_contacts` is unavailable and the user supplies only a phone number. It does not inspect labels, scenario IDs, expected answers, prior SAGE traces, or hidden benchmark facts.

This is experimental implementation evidence, not protected final-claim evidence. The next formal step is a broader matched validation that keeps the same treatment definition fixed.

Machine-readable summary:

`artifacts/self_evolving_sage/summary/self_evolving_live_generation_v21_60_summary.json`

Summary SHA-256:

`828ea32146a778f1b5b371bc837a683594967d1744ab7dce4bf9f285b1125de0`

## Initial Positive Live-Generation Proof

Run:

`outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431`

Dashboard:

`http://127.0.0.1:62628/outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431/dashboard/task_compare.html`

Controls:

- control cache mode: `use-if-eligible`
- cached controls: `24`
- fresh controls: `0`
- cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

Candidate/SAGE:

- starting generated registry: empty
- generation: on
- candidate task cache: off
- OpenAI response cache: disabled
- routing evidence: disabled
- active diagnostic force env vars: none
- agent/user/generation model: `gpt-4o-mini`
- runtime exceptions: `0`
- helper side-effect incidents: `0`

Metrics:

| Metric | Delta |
|---|---:|
| Canonical/reference score | `+0.040569` |
| Outcome/task completion | `+0.047045` |
| Canonical gains / regressions | `13 / 7` |
| Outcome gains / regressions | `9 / 5` |
| Exact successes | `+6` |

Protocol gate: `PASS`.

Live accepted tools:

| Helper | Visible | Called | VNC | Called-subset canonical delta | Called-subset outcome delta | Decision |
|---|---:|---:|---:|---:|---:|---|
| `plan_contact_relationship_batch_update` | 3 | 3 | 0 | `+0.102694` | `+0.342197` | Keep and retest on broader relationship/update opportunities |
| `plan_contact_update_from_id` | 0 | 0 | 0 | n/a | n/a | Retain as accepted but unresolved; needs later post-birth exposure |
| `prepare_side_effect_args_from_selected_record` | 4 | 0 | 4 | n/a | n/a | Retain as unresolved; not promoted from this run |

This run answers the core objection: no generated tools existed at the start, generation was on, accepted tools were born online, one generated tool was naturally called, and the run produced positive canonical and outcome lift without force calls.

## Negative Birth And Parking

The live loop also generated a safe insufficient-information / abstention candidate:

`prepare_safe_action_or_abstain`

Diagnostic run:

`outputs/self_evolving_sage/live_generation_v9_diag24/mechanism_60_20260511_233101`

Called-subset result:

- visible/called/VNC: `8 / 6 / 2`
- called-subset canonical delta: `-0.505454`
- called-subset outcome delta: `-0.030562`

Diagnosis: the helper was safe and callable, but generic abstention wording scored poorly against the benchmark's original canonical/reference answers on these insufficient-information cases. It is a real generated candidate, but not a retained default tool.

Repair:

- default behavior now parks safe-abstention birth with reason `insufficient_information_safe_abstain_birth_parked_pending_benchmark_phrasing`
- explicit diagnostic opt-in: `SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1`

Follow-up run after parking:

`outputs/self_evolving_sage/live_generation_v10_diag24/mechanism_60_20260511_233833`

Result:

- starting generated registry: empty
- generation: on
- controls: `24 cached / 0 fresh`
- canonical delta: `-0.018825`
- outcome delta: `-0.011708`
- runtime exceptions: `0`
- side-effect incidents: `0`
- protocol gate: `FAIL`

The v10 result confirms the system can park a harmful birth, but it did not reproduce the v6 positive gate. The current evidence is therefore: live generation works in v6, safe-abstention is parked, and the next required improvement is stabilizing retention/reuse across broader and less near-duplicate manifests.

## Superseded Recipe-Pack Result

Earlier run:

`outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904`

This run achieved a strong mini60 result:

- canonical delta: `+0.081539`
- outcome delta: `+0.118882`
- exact successes: `+9`

But it used recipe-pack materialization before the run and generation was off during the run. It remains useful as a low-cost recipe-library transfer diagnostic, but it is no longer presented as proof of autonomous live tool birth.

## Interpretation

The corrected mechanism is promising but early:

- It can start from an empty registry.
- It can generate valid tools online using only `gpt-4o-mini`.
- It can naturally call a live-born helper and produce positive lift.
- It can diagnose and park a generated helper that is safe but outcome/canonical negative.

The limits are also clear:

- The current contact manifest has only 24 matching scenarios and is near-duplicate dominated.
- Tool birth order matters: some accepted tools had no later exposure after birth.
- The safe-abstention lane needs benchmark-faithful final-answer phrasing before it can be enabled by default.
- This is not formal evidence and should not update protected claims.

## Scale Update

After the mini60 proof, the same self-evolving mechanism was scaled to broad formal-order samples with no accepted generated helpers at run start, generation on, all models set to `gpt-4o-mini`, strict per-task cached controls, SAGE/candidate task cache off, OpenAI response cache disabled, and routing evidence disabled.

Broad250:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851`
- Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851/dashboard/task_compare.html`
- Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v37_broad250_system_lifecycle_keyfixed_summary.json`
- Canonical/reference: `0.669502 -> 0.779703`, delta `+0.110201`, relative lift `+16.46%`
- Outcome: `0.509662 -> 0.685953`, delta `+0.176291`, relative lift `+34.59%`
- Exact successes: `9 -> 91`
- Generated helpers: `15` accepted, `14` naturally called
- Controls: `250 cached / 0 fresh`
- Safety: runtime exceptions `0`, helper side-effect incidents `0`

Broad500:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654`
- Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654/dashboard/task_compare.html`
- Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v38_broad500_system_lifecycle_keyfixed_summary.json`
- Residual gap profile: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v38_broad500_residual_gap_profile.json`
- Canonical/reference: `0.657730 -> 0.738692`, delta `+0.080962`, relative lift `+12.31%`
- Outcome: `0.495416 -> 0.700468`, delta `+0.205052`, relative lift `+41.39%`
- Exact success delta: `+80`
- Generated helpers: `16` accepted, `15` naturally called
- Top natural calls: `resolve_search_window_or_bounds` `70`, `plan_device_state_action_sequence_v3` `59`, `prepare_reminder_creation_args` `22`, `plan_contact_lookup_query` `19`, `select_message_content_by_recency` `15`
- Controls: `500 cached / 0 fresh`
- Safety: runtime exceptions `0`, helper side-effect incidents `0`

The broad500 result reaches the previous fixed Praxis relative outcome-lift band while starting from no accepted generated helpers and paying the online discovery cost inside the run. It remains slightly below the fixed Praxis canonical/reference relative lift (`+12.31%` versus `+13.04%`). The run also resumed after an OpenAI transport hang; the paired result is valid, but the lifecycle reflection state did not fully hydrate across the resume boundary. The runtime now has a tested resume-hydration repair that reloads cumulative lifecycle state from copied task feedback, so future resumed scale runs preserve system-driven routing and retention evidence.

## Current SAGE Approach

The current self-evolving SAGE approach is:

1. Start discovery campaigns from an empty generated-tool registry.
2. Keep generation on during the candidate run.
3. Use `gpt-4o-mini` for agent, user simulator, and generation in budgeted discovery.
4. Use cached controls where eligible.
5. Keep SAGE/candidate task cache off and OpenAI response cache disabled.
6. Generate tools from observed gap packets and online inadequacy observations.
7. Retain a generated tool only if natural calls or downstream diagnostics show safe value.
8. Park generated tools that are safe but scoring-negative until their contract/phrasing is repaired.
9. Treat recipe-pack materialization as a separate transfer mode, not as evidence of live self-evolution.

## Next Work

The next self-evolving increment should focus on confirming the scale result without wasting another immediate 500-run:

- run a no-resume or resume-hydrated 100/250 confirmation under the same committed runtime
- verify that lifecycle routing remains cumulative through an intentional resume smoke test
- use the completed broad500 residual gap profile to improve system-generated repair prompts for oldest-message recency, low-battery reminder scheduling, contact modification by message recency, device-state reads, and holiday/date calculations
- only spend another broad500 run when the 100/250 checkpoint matches or exceeds the fixed Praxis trajectory

Decision label:

`SELF_EVOLVING_SCALE_POSITIVE_WITH_RESUME_CAVEAT`
