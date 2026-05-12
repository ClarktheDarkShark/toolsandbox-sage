# Self-Evolving SAGE Mini60 Report

Status: experimental implementation proof, not protected final-claim evidence.

Date: 2026-05-11

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

## Positive Live-Generation Proof

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

The next self-evolving increment should focus on stability rather than scale:

- build a less near-duplicate <=60 manifest with later post-birth opportunities for `plan_contact_update_from_id`
- add reflection logic that keeps the relationship-batch planner and suppresses/parks abstention by default
- generate benchmark-faithful abstention phrasing tests before re-enabling `prepare_safe_action_or_abstain`
- extend the gap observer to choose between contact, reminder, settings/device-state, and send-message precondition buckets
- only after repeated <=60 positive gates, recombine retained live-born tools with the Praxis combined treatment for a broader 100/250 validation

Decision label:

`SELF_EVOLVING_LIVE_GENERATION_MECHANISM_POSITIVE_BUT_NOT_SCALE_READY`
