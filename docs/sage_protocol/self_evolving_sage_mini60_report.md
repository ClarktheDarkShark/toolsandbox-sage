# Self-Evolving SAGE Mini60 Report

Status: experimental implementation proof, not protected final-claim evidence.

Date: 2026-05-11

Branch: `codex/self-evolving-sage-mini60`

## Objective

Implement the first executable slice of `praxis_next_gap_and_self_evolving_sage_plan.md` under a strict token-conservation setup:

- maximum sample size `60`
- agent model `gpt-4o-mini`
- user simulator model `gpt-4o-mini`
- generation model `gpt-4o-mini`
- baseline/control cache `use-if-eligible`
- candidate/SAGE task cache off
- OpenAI response cache disabled
- routing evidence disabled
- diagnostic force-call disabled

The goal was to prove that SAGE can start from an empty runtime generated-tool registry, observe a gap packet, choose a next gap, generate or materialize the needed helper set, and recover a high-lift natural-adoption result without force-calling tools or inspecting hidden labels.

## Implemented Slice

New implementation:

- `src/sage_ts/evaluation/gap_observer.py`
- `src/sage_ts/orchestration/self_evolving_campaign.py`
- `scripts/prepare_self_evolving_sage_mini60.py`
- `tests/unit/test_self_evolving_campaign.py`

The controller performs this initial loop:

```text
gap packet
  -> ranked gap buckets
  -> contact lookup/update/search bucket selected
  -> empty runtime registry written
  -> helper strategy applied
  -> generated/materialized helpers validated
  -> <=60 task manifest written
  -> natural SAGE run with cached controls and fresh candidate arm
```

Two strategies were tested:

1. `contact_action_v2`: one broad final-action-ready helper. It was safe, but adoption was poor.
2. `praxis_current_pack`: materialize the current validated Praxis recipe pack into the empty runtime registry. This restored natural calls and high lift.

This is best described as an early self-evolving controller with a recipe library, not as unconstrained novel tool invention. That distinction should remain explicit in methodology.

## Source Inputs

- Source gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_gap_packets.json`
- Source formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Selected bucket: `contact_lookup_update_search_crud`
- Recipe registry: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1`

No labels, expected answers, scenario-specific facts, or cache availability were used to select scenarios or build tool code. The materialized recipe registry does inherit some task-family trigger labels, such as contact lookup/update family names, as routing metadata. Those are not hidden labels or expected answers, but this remains an experimental routing-policy dependency that should be replaced with semantic trigger descriptors or explicitly audited before any protected claim.

## Failed First Attempt

Run:

`outputs/self_evolving_sage/mini60_contact_v1/transfer_60_20260511_203023`

Result:

- score delta: `-0.009128`
- outcome delta: `-0.001289`
- generated tools visible: `39`
- generated tools called: `2`
- visible-not-called: `37`
- runtime exceptions: `0`

Diagnosis: one broad helper did not get natural adoption. The failure was adoption/affordance and granularity, not safety.

## Passing Mini60 Proof

Preparation artifact:

- `artifacts/self_evolving_sage/current_mini60_praxis_pack/self_evolving_mini60_preparation.json`
- generated/runtime registry: `artifacts/self_evolving_sage/current_mini60_praxis_pack/registry/registry_manifest.json`
- registry SHA-256: `3ee0719ddc87a774fc18d48365c36e9dea7cce70f65f6f28574afd60ddc9e99c`
- manifest: `artifacts/self_evolving_sage/current_mini60_praxis_pack/self_evolving_mini60_manifest.json`
- manifest SHA-256: `e7278b67d682d3be59d764e59e73094548e7ea965ec25003bda8b6a41935a51a`

Run:

`outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904`

Dashboard:

`http://127.0.0.1:62618/outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904/dashboard/task_compare.html`

Metrics:

| Metric | Baseline | SAGE | Delta |
|---|---:|---:|---:|
| Canonical/reference score | `0.763821` | `0.845361` | `+0.081539` |
| Outcome/task completion | `0.536539` | `0.655421` | `+0.118882` |
| Exact successes | `13` | `22` | `+9` |
| Canonical gains / regressions | - | - | `35 / 11` |
| Outcome gains / regressions / preserved | - | - | `24 / 15 / 6` |

Protocol gate: `PASS`.

Controls:

- control cache mode: `use-if-eligible`
- cached controls: `33`
- fresh controls: `27`
- cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- cohort selection influenced by cache: `false`

Candidate/SAGE:

- task cache: off
- OpenAI response cache: disabled
- generation: off during the run after preparation
- routing evidence: disabled
- active diagnostic force env vars: none
- runtime exceptions: `0`
- helper failed attempts: `0`
- helper side-effect incidents: `0`

Leakage review:

- hidden labels inspected: no
- expected answers encoded: no
- scenario selection by cache availability: no
- diagnostic force-call path active: no
- exact scenario names present in split manifest: yes, as required for execution
- task-family trigger labels present in recipe metadata: yes, inherited from the current validated recipe registry and treated as an experimental routing-policy dependency

Model policy:

- agent: `gpt-4o-mini`
- user simulator: `gpt-4o-mini`
- generation model: `gpt-4o-mini`

Natural adoption:

- generated-tool visible scenarios: `36 / 60`
- generated-tool called scenarios: `23 / 60`
- generated-tool attempted scenarios: `23 / 60`
- generated-tool failed scenarios: `0`

Called positive tools:

| Helper | Visible | Called | VNC | Called-subset score delta | Called-subset outcome delta |
|---|---:|---:|---:|---:|---:|
| `plan_contact_lookup_query` | 11 | 8 | 3 | `+0.360822` | `+0.431630` |
| `plan_contact_relationship_batch_update` | 10 | 8 | 2 | `+0.191414` | `+0.252275` |
| `plan_send_message_contact_lookup` | 4 | 4 | 0 | `+0.015989` | `+0.064914` |
| `select_message_counterparty_for_contact_update` | 4 | 3 | 1 | `+0.291408` | `+0.805556` |

Visible-not-called positive support was also seen for `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`, `select_message_content_by_recency`, and `plan_contact_search_from_scalar_constraint`, which supports retaining sparse high-value helpers under small-bundle routing rather than judging value only by global call frequency.

## Interpretation

This run gets close to the previous combined-treatment formal500 score lift under much cheaper conditions:

- formal500 combined score delta: `+0.087344`
- self-evolving mini60 score delta: `+0.081539`

Outcome lift is positive but lower than the full combined formal500 treatment:

- formal500 combined outcome delta: `+0.245071`
- self-evolving mini60 outcome delta: `+0.118882`

That difference is expected because this run is capped at 60, uses `gpt-4o-mini` for all roles, and is focused on the selected contact gap rather than the full broad Praxis treatment. It is sufficient as an implementation proof of the self-evolving controller, but it is not a replacement for formal500 validation.

## Current SAGE Approach

The current SAGE approach should be maintained as:

1. Use the combined Praxis bridge-policy treatment as the current high-lift SAGE treatment under review.
2. Use the self-evolving controller to observe residual gap packets and select the next bucket.
3. Start each mini-campaign from an empty runtime generated-tool registry.
4. Prefer recipe-library materialization for validated helper families when token budget is constrained.
5. Use new freeform generation only after the gap observer identifies an unsupported bucket with no adequate recipe.
6. Run no more than 60 tasks for budgeted discovery unless explicitly approved.
7. Keep all roles on `gpt-4o-mini` for low-cost discovery campaigns when requested.

## Next Work

The next self-evolving increment is to add the missing automation layers around the controller:

- mine gap packets directly from a completed run root
- auto-rank opportunities across contact, reminder, settings/device-state, and abstention buckets
- synthesize candidate specs when no validated recipe exists
- generate minefield tests per bucket
- implement reflection decisions: `scale`, `refine`, `recombine`, `park`, `block`
- recombine generated packs into the combined Praxis treatment only after a natural-adoption positive mini60 gate

Protected final claims should not be updated from this branch. The result is an experimental proof that the self-evolving loop can reproduce near-current score lift on a capped gap-focused run under strict mini-model constraints.
