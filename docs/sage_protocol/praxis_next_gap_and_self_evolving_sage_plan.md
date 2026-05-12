# Praxis Next Gap And Self-Evolving SAGE Plan

Status: experimental review note, not protected final-claim evidence.

Date: 2026-05-11

Source run for interim gap analysis:

- Run: `outputs/praxis_combined_bridge_policy/formal500_order_first250_v2_bridge_repair_rapid_cache/validate_250_20260511_172919`
- Machine-readable gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_first250_gap_packets.json`
- Gap packet SHA-256: `c0b6c73ad6ab88ea87f277987f36751c13696a21201c1ebf2eb29fcc5f400926`
- Treatment: frozen Praxis registry plus feature-flagged combined bridge policy, `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- Controls: 250/250 task-level cached controls, `control-cache use-if-eligible`
- Candidate/SAGE cache: off
- OpenAI response cache: disabled
- RapidAPI: read-only external-service fixture, not task cache
- Runtime exceptions: 0
- Generated/helper tool failures: 0

Completed formal500 source for final gap update:

- Run: `outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`
- Machine-readable gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_gap_packets.json`
- Gap packet SHA-256: `708abc10ec97a2bc36f703a27702abbd50dcdf39b3dc4f265ff08a52dd03db60`
- Formal500 canonical/reference: `0.670025 -> 0.757369`, delta `+0.087344`, relative lift `+13.04%`
- Formal500 outcome/task completion: `0.594872 -> 0.839943`, delta `+0.245071`, relative lift `+41.20%`
- Runtime exceptions: 0
- Helper failures / side-effect incidents: `0 / 0`

Mini60 self-evolving live-generation implementation proof:

- Branch: `codex/self-evolving-sage-mini60`
- Report: `docs/sage_protocol/self_evolving_sage_mini60_report.md`
- Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_diag24_summary.json`
- Preparation: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_preparation.json`
- Starting registry: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/registry/registry_manifest.json`
- Starting registry SHA-256: `61468467448a94c5c6ced36d05894d7ba2e2f7501ca84270a30da1cd18a3c713`
- Manifest: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_manifest.json`
- Manifest SHA-256: `5337bf7bef2cb32679955bcf27b68cf06495d00c905a02c66766ae261b0176bc`
- Positive run: `outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431`
- Dashboard: `http://127.0.0.1:62628/outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431/dashboard/task_compare.html`
- Strategy: start from an empty generated-tool registry, keep generation on during the candidate run, generate tools from online inadequacy observations, validate them, and let natural routing/calling decide value.
- Models: agent/user/generation all `gpt-4o-mini`
- Sample cap: `60`; matched scenarios in this contact-gap manifest: `24`
- Baseline/control cache: `24 cached / 0 fresh`, `use-if-eligible`
- Candidate/SAGE cache: off
- OpenAI response cache: disabled
- Score delta: `+0.040569`
- Outcome/task completion delta: `+0.047045`
- Exact success delta: `+6`
- Natural generated-tool birth: accepted `plan_contact_relationship_batch_update`, `plan_contact_update_from_id`, and `prepare_side_effect_args_from_selected_record`
- Natural generated-tool adoption: `plan_contact_relationship_batch_update` visible/called/VNC `3 / 3 / 0`, called-subset outcome delta `+0.342197`
- Runtime exceptions / helper side-effect incidents: `0 / 0`
- Protocol gate: `PASS`
- Evidence status: experimental mechanism proof only, not protected final-claim evidence.
- Leakage note: no labels, expected answers, scenario IDs, or benchmark facts were encoded into generated tools or routing logic; scenario IDs appear only in the executable split manifest.

Superseded recipe-pack transfer result:

- Run: `outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904`
- Score delta: `+0.081539`; outcome delta: `+0.118882`; exact success delta: `+9`
- Status: useful transfer diagnostic, but no longer counted as the self-evolving proof because it materialized pre-existing Praxis recipe tools before the run and ran with generation off.

Live-generation negative/parking diagnostic:

- Run: `outputs/self_evolving_sage/live_generation_v9_diag24/mechanism_60_20260511_233101`
- Generated helper: `prepare_safe_action_or_abstain`
- Called-subset canonical delta: `-0.505454`; called-subset outcome delta: `-0.030562`
- Decision: safe-abstention birth is parked by default pending benchmark-faithful phrasing and minefield validation; diagnostic opt-in is `SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1`.

## Interim Finding

The next plausible lift bucket is contact lookup/update/search, not another broad generic helper.

On the 250-task gate, the bucket remained net-positive, but it also had the largest residual regression mass. The completed formal500 gap packet confirms the same broad conclusion: contact lookup/update/search is still the largest remaining outcome-regression bucket.

Formal500 residual gap table:

| Bucket | N | Outcome regressions | Negative outcome mass | Score regressions | Negative score mass | No visible helper | No called helper |
|---|---:|---:|---:|---:|---:|---:|---:|
| Contact lookup/update/search CRUD | 140 | 17 | 4.606 | 32 | 8.565 | 62 | 98 |
| Reminder scheduling/search CRUD | 126 | 14 | 3.632 | 17 | 2.758 | 12 | 12 |
| Settings/device-state and preconditions | 103 | 10 | 1.580 | 14 | 2.758 | 13 | 79 |
| Reminder insufficient-info / abstention | 64 | 0 | 0.000 | 26 | 12.071 | 56 | 62 |
| Date/holiday computation | 32 | 0 | 0.000 | 25 | 7.157 | 7 | 8 |
| Date/holiday insufficient-info | 11 | 0 | 0.000 | 0 | 0.000 | 11 | 11 |

The older 250-task gate table is retained below for lineage. The key change at formal500 is that reminder scheduling/search is now the second-largest outcome-regression bucket, while insufficient-information and date/holiday lanes remain mostly canonical/reference issues rather than outcome-lift opportunities.

250-task gate residual gap table:

| Bucket | N | Outcome regressions | Negative outcome mass | Score regressions | Negative score mass | No visible helper | No called helper |
|---|---:|---:|---:|---:|---:|---:|---:|
| Contact lookup/update/search CRUD | 81 | 16 | 6.642 | 26 | 5.132 | 55 | 55 |
| Settings/device-state and preconditions | 53 | 6 | 2.086 | 8 | 2.479 | 35 | 35 |
| Reminder scheduling/search CRUD | 56 | 3 | 0.355 | 4 | 0.198 | 5 | 5 |
| Reminder insufficient-info / abstention | 35 | 0 | 0.000 | 16 | 7.591 | 34 | 34 |
| Date/holiday computation | 15 | 0 | 0.000 | 8 | 1.371 | 10 | 10 |
| Message search / send preconditions | 10 | 0 | 0.000 | 0 | 0.000 | 0 | 0 |

The highest-value residual cases are:

- `search_sender_phone_number_with_content_10_distraction_tools`, `search_phone_number_with_name`, and `search_phone_number_with_name_10_distraction_tools`: no helper was visible in the Task Compare export, with outcome regressions of `-1.000`, `-0.842`, and `-0.714`.
- `search_name_with_relationship` and 3-distraction variants: helper call sometimes improved canonical score while hurting outcome, suggesting the helper output is not final-answer-ready enough for the actor.
- `update_contact_relationship_with_relationship_twice_multiple_user_turn*`: relationship-batch planning is visible, but adoption is inconsistent and regressions remain.
- `add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt*`: remaining settings/device-state regressions appear to be composite action-plan failures, not pure timestamp failures.
- Insufficient-information lanes have many canonical regressions and no visible helper, but most have zero outcome opportunity because both arms score zero outcome. This is still relevant for peer-review canonical questions, but it is secondary to outcome lift.

Contact sub-bucket detail from the same 250-task gate:

| Contact sub-bucket | Count | Observed failure mode |
|---|---:|---|
| Modify contact from message recency | 10 | No helper on several insufficient-information variants; canonical regressions dominate. |
| Send message contact lookup/precondition | 10 | Some cellular-off insufficient-information cases regress canonically; needs action feasibility rather than direct send. |
| Relationship batch update | 9 | Helper exists but routing/adoption is inconsistent; some calls improve canonical wording while missing outcome-preserving updates. |
| Remove by phone / no-search variants | 15 | Mostly unsupported insufficient-information and missing-precondition cases; should abstain rather than fabricate target removal. |
| Add/remove contact direct ID/name/phone operations | 10 | Direct CRUD variants usually need a final action spec and explicit original side-effect call preservation. |
| Name/phone/relationship lookup | 15 | Largest outcome opportunity; several no-visible cases and some intermediate-only helper outputs. |
| Sender phone lookup from message content | 4 | High-value sparse bucket; helper should be retained even if infrequently called. |

The important pattern is that frequency alone is not the right retention criterion. A sparse helper is worth keeping if it solves a high-value, repeated family safely and the router can keep it out of unrelated contexts.

## Candidate For Next Tool Family

The next tool family should be a final-answer-ready contact/action bridge rather than another extractor:

`prepare_contact_lookup_or_update_action_v2`

Expected behavior:

- Inputs: scalar/list fields only where possible, such as `operation`, `lookup_field`, `lookup_value`, `target_name`, `target_phone_number`, `relationship`, `new_phone_number`, `message_recency`, and `allow_ambiguous`.
- Outputs: a typed action spec with `status`, `selected_contact_id`, `selected_display_name`, `selected_phone_number`, `selected_relationship`, `required_original_tool`, `required_original_arguments`, `final_answer`, and `abstain_reason`.
- It must never mutate state.
- It must explicitly state the original ToolSandbox side-effect tool that still has to be called later for update/remove operations.
- It must abstain on duplicate names, missing lookup values, missing update values, absent original side-effect tools, or ambiguous message/contact evidence.
- It must be compatible with scrambled tool names by describing intent and required arguments, not relying on brittle execution names.
- It must be route-triggered only for contact lookup/update/search cases and not exposed broadly.

Expected first tests:

- 20-task narrow natural adoption run focused on `search_phone_number_with_name`, `search_name_with_relationship`, `update_contact_relationship_with_relationship_twice_multiple_user_turn`, and their distraction/scrambled variants.
- Prepared seed manifest: `artifacts/praxis_combined_bridge_policy/manifests/contact_lookup_update_search_gap_loop20_seed.json`
- Seed manifest SHA-256: `74193b47d617c2328b44f34cc963b6f311cf007bd784f3ecbb22c16180a59e8d`
- Minefield tests: duplicate contact names, missing relationship, missing phone number, no contact match, multiple message-counterparty candidates, and side-effect tool absent.
- If positive, expand to a 60-task contact-focused run before recombining with Praxis for a broad 100/250 gate.

## Self-Evolving SAGE: Current State

The current system now has an initial live self-evolving slice:

- Registry-backed helper reuse.
- Tool generation and repair stages.
- Gap packet loading and bucket selection through `sage_ts.evaluation.gap_observer`.
- Empty generated-registry campaign preparation through `sage_ts.orchestration.self_evolving_campaign`.
- Online birth observations for contact relationship updates, contact-id updates, side-effect argument prep, and safe abstention.
- Routing, visibility, called/VNC, and contribution export.
- Progressive validation runs with baseline task cache and fresh SAGE arms.
- Dashboard views for per-task comparison and helper contribution.
- Safety checks for runtime exceptions, side-effect preservation, force-call exclusion, cache policy, and registry hashes.

The v6 diagnostic proves live birth from an empty generated registry can work. The system is still not fully self-evolving because the human operator is still doing several high-level campaign decisions:

- Identifying the next bucket from regressions and no-helper cases.
- Deciding which bucket deserves a new helper after a failed or marginal run.
- Turning some bucket diagnoses into robust, benchmark-faithful tool specs.
- Choosing the progressive run schedule.
- Deciding when to repair, park, recombine, or scale after mixed evidence.

## Target Architecture

SAGE should own that loop explicitly.

```text
run completed comparison
  -> gap observer extracts regressions, no-fit, no-visible, VNC, unsafe calls
  -> bucket synthesizer clusters failures into reusable pain points
  -> opportunity scorer estimates possible lift and safety risk
  -> tool spec generator proposes helper families and minefield tests
  -> static and live safety validator rejects unsafe/leaky specs
  -> narrow natural adoption run tests visibility, callability, and value
  -> repair controller diagnoses hidden / visible-not-called / bad args / bad output
  -> expanded pilot confirms downstream value
  -> portfolio composer recombines retained tools with routing controls
  -> formal validation freezes candidate and runs matched arms
  -> promotion controller labels registry-only, policy-only, or combined treatment
```

## Required New Components

1. Gap Observer

Inputs: paired comparison JSON, task-compare JSON, helper contribution summary, side-effect reports, cache reports, and run manifests.

Outputs: machine-readable gap packets with:

- bucket label
- scenarios
- outcome and canonical regression mass
- no-visible / visible-not-called / called-negative counts
- helper candidates already tried
- suspected root cause
- safety/cost risk

2. Bucket Synthesizer

Clusters gap packets without truth-label peeking. It should group by task text, scenario family, visible tools, action type, failed state transition, and output requirements.

3. Opportunity Scorer

Ranks buckets by expected lift:

- outcome regression mass first
- canonical regression mass second
- number of unsupported/no-visible cases
- historical natural adoption
- safety risk
- expected token/run cost

4. Tool Spec Generator

Produces typed helper specs plus negative examples and minefield tests. It must not emit scenario IDs, expected answers, hidden labels, or benchmark-specific strings into tool code or metadata.

5. Safety And Leakage Gate

Blocks candidates with:

- side effects
- hidden-label access
- scenario-ID or expected-answer constants
- diagnostic force-call leakage
- candidate cache use
- mtime-selected routing evidence
- ambiguous original side-effect preservation

6. Fair-Chance Evaluator

Automates the current campaign discipline:

- narrow 20
- expanded 60
- confirmation 100
- scale 250
- formal 500 only after strong gates

Baseline/control arms use task-level cache where eligible. Candidate/SAGE arms stay fresh.

7. Reflection Controller

Every run should produce a decision:

- `scale`: outcome-positive, called-subset-positive, safe
- `refine`: latent value but poor adoption/schema/output
- `recombine`: low-frequency but high-value helper belongs in a smaller routed portfolio
- `park`: repeated outcome-negative or unsafe
- `block`: leakage, side effect, or architectural issue

## Implementation Map

The system already has most primitives, but they are not wired into one autonomous controller.

| Need | Existing code to build on | Missing work |
|---|---|---|
| Extract run deltas, gains, regressions, and cache status | `src/sage_ts/evaluation/run_metrics.py`, `src/sage_ts/dashboard/exporters.py`, `src/sage_ts/evaluation/helper_contribution.py`, `src/sage_ts/evaluation/gap_observer.py` | Extend the observer from prepared gap packets to direct run-root mining. |
| Classify task pain points without labels | `src/sage_ts/adequacy/inadequacy_classifier.py`, `src/sage_ts/evaluation/feedback_packets.py` | Broaden heuristic classifications into bucket objects with regression mass, no-visible/VNC/called-negative counts, and safety risk. |
| Choose the next tool family | `src/sage_ts/adequacy/failure_memory.py`, `scripts/build_v2_5_tool_foundry_artifacts.py`, `src/sage_ts/orchestration/self_evolving_campaign.py` | Add an opportunity scorer that ranks buckets by expected outcome lift first, canonical lift second, then adoption feasibility and cost. |
| Generate candidate specs | `src/sage_ts/generation/tool_generator.py`, `src/sage_ts/generation/tool_spec.py`, `src/sage_ts/adequacy/inadequacy_classifier.py` | Feed gap packets directly into generation with negative examples and minefield requirements across contact, reminder, settings, send-message, and abstention buckets. |
| Reject unsafe or leaky helpers | `src/sage_ts/validation/ast_safety.py`, `src/sage_ts/validation/schema_check.py`, `src/sage_ts/validation/live_candidate_check.py`, `src/sage_ts/adequacy/candidate_gate.py` | Add policy checks for scenario-ID/task-string leakage, side-effect action substitution, and force-call leakage before a helper reaches any natural run. |
| Route a small relevant bundle | `src/sage_ts/runtime/routing_scorer.py`, `src/sage_ts/runtime/toolsandbox_integration.py` | Add bucket-aware routing constraints so low-frequency high-value helpers are retained without polluting broad context. |
| Run progressive fair-chance gates | `scripts/run_sage_protocol.py`, `src/sage_ts/campaign/artifacts.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | Add a campaign controller that automatically launches 20/60/100/250 gates, uses cached controls, and keeps candidate arms fresh. |
| Decide scale/refine/park/recombine | `src/sage_ts/registry/promotion_gate.py`, `scripts/check_promotion_gate.py` | Add a reflection controller that writes decisions and next actions after every run. |

Minimal implementation sequence:

1. Extend `sage_ts.evaluation.gap_observer` from prepared gap packets to direct run-root mining.
2. Extend `sage_ts.orchestration.self_evolving_campaign` from a contact-only mini-campaign to multi-bucket campaign planning.
3. Add minefield generation from the selected bucket before the helper is exposed broadly.
4. Add progressive gate orchestration with hard controls: cached baseline only, fresh candidate, generation policy explicit, routing evidence disabled or pinned.
5. Add a dashboard panel and report export that shows the system's chosen bucket, generated candidate, fair-chance decision, and next action.

This would let SAGE perform the same loop now being done manually: detect unsupported buckets, estimate lift, generate a targeted helper, validate safety, test natural adoption, repair if needed, and recombine only when evidence supports it.

## Pseudocode

```python
def self_evolve_sage(seed_registry, validation_manifest):
    registry = seed_registry
    while budget.remaining() and not stop_condition_met():
        run = run_progressive_gate(registry, validation_manifest)
        gaps = observe_gaps(run)
        buckets = synthesize_buckets(gaps)
        ranked = score_opportunities(buckets)

        for bucket in ranked:
            specs = generate_tool_specs(bucket)
            candidates = []
            for spec in specs:
                if safety_gate_passes(spec):
                    candidate = build_candidate_tool(spec)
                    if synthetic_minefields_pass(candidate, bucket):
                        candidates.append(candidate)

            for candidate in candidates:
                diagnostic = run_narrow_natural_adoption(candidate, bucket)
                if diagnostic.hidden_or_visible_not_called:
                    candidate = repair_affordance_or_route(candidate, diagnostic)
                    diagnostic = rerun_narrow(candidate, bucket)
                if diagnostic.called_negative_or_unsafe:
                    park(candidate, diagnostic)
                    continue
                if diagnostic.outcome_positive_and_safe:
                    registry = recombine_portfolio(registry, candidate)
                    break

        if registry_changed(registry):
            continue
        break

    return freeze_and_validate_if_promising(registry)
```

## Immediate Next Action

The formal500 confirms the combined bridge-policy lift with zero safety incidents. The first self-evolving controller slice is now implemented and has passed a capped all-`gpt-4o-mini` mechanism proof with an empty generated registry and generation on during the run.

The next action is to stabilize and generalize this controller:

1. mine gap packets directly from a run root,
2. rank contact, reminder, settings/device-state, and abstention opportunities,
3. generate minefield tests per selected bucket,
4. keep generation on during discovery campaigns,
5. park safe-but-negative births automatically and only re-enable them after repair,
6. keep discovery runs capped at 60 unless explicitly approved.
