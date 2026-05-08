# SAGE Gap-Closure Lab Report

Experimental branch report only. This is not protected final claim evidence and does not modify best3, locked formal evidence, V2.6 evidence, or final-package claim artifacts.

## Status

Stop condition 2 is met for this campaign. All required experiment families received fair-chance diagnostic or expanded-pilot treatment, including repair and force diagnostics where appropriate. No approach produced scalable primary outcome value with zero safety findings and sufficient natural adoption.

## Best Experimental Approach

The strongest broad signal came from robust live generation with `gpt-5-mini` for generation/repair and `gpt-4o-mini` for execution:

- Live generation pilot20: outcome +0.2090, canonical +0.0127, gate pass, zero runtime/side-effect incidents.
- Frozen generated pilot20: outcome +0.1377, canonical +0.0772, gate pass, zero runtime/side-effect incidents.
- Expanded60 of the frozen pack: outcome +0.0707, canonical +0.0628, but two side-effect incidents, so it was not safe for promotion.

The strongest low-frequency tool signal was `select_recency_target_and_prepare_action`:

- Force-after-search diagnostic on 2 recency side-effect tasks: outcome +0.2931, canonical +0.1648, zero incidents.
- Repaired natural safety diagnostic on the same 2-task mechanism split: outcome +0.1460, canonical +0.2102, zero incidents.
- Expanded60 rerun: canonical +0.0441 and exact successes +6, but primary outcome -0.0189 and the chain was visible-not-called on both target recency tasks.

That means the recency bridge has real potential but is not a standalone scale candidate.

## Failed Or Parked Families

- Many small deterministic tools: full/refined/minus-unsafe packs did not produce stable outcome lift at 60.
- Tool chaining: repaired chain showed latent value, but natural adoption remained too sparse in expanded60.
- Regular refinement/adaptive repair: fixed a real wrapper/output-shape blocker and a safety-accounting false positive, but did not change broad outcome.
- Robust generation: best pilot family, but expanded safety incidents blocked promotion.
- Pain-point synthesis: useful for designs, but shared tools did not generalize into broad unseen lift.
- Actor-policy/affordance: richer descriptions and guard metadata did not improve adoption or outcome.
- Router/composer/bandit-style exposure: routing suppressed unsafe overexposure, but could not overcome no-call and low helper-call share.
- Insufficient-information detector: safe but outcome-negative; broad abstention overlay is parked.
- Final-answer-ready transformation: recency bridge improved, service-answer extraction remains unresolved.
- Contrastive generation: useful for avoiding known failures; no scalable outcome lift.
- Leave-family-out: no held-out-family evidence justified confirmation or scale.
- Portfolio ablation: best broad outcome signals either failed safety or regressed primary outcome.
- Synthetic validation lab: useful as harness coverage, not claim evidence.
- Metadata compression/richness: rich metadata did not beat focused trigger metadata.
- Oracle-free pain-point classifier: useful diagnostic layer, not a standalone lift.

## Leakage Statement

Seed/dev labels were allowed only for the 8-task `seed_dev_labeled` split. Unseen pilot, expanded, confirm, and scale splits were not inspected for truth labels before sealed runs. No tools or routers encode scenario IDs, expected answers, hidden truth labels, benchmark facts, or final labels. Force diagnostics were used only for diagnosis and repair, not promotion.

Split manifest:

- File: `artifacts/experiment_manifests/gap_closure_lab/gap_closure_lab_splits.json`
- File SHA-256: `7843305bfee2e0d021ecd0ab429ea12f88cb381676615079538836c91e9f84c9`
- Payload SHA-256: `41a9565960005007bdcc8a0e901b81a300e2e5c1c52c0b38e15e17fe83f983d4`

## Cache Statement

Baseline/control arms used the eligible control baseline cache where available and recorded cached/fresh counts per run. Candidate/SAGE arms were fresh experimental runs with OpenAI response cache disabled. No scenario selection was based on cache availability.

Latest expanded60 cache accounting:

- Run: `outputs/gap_closure_lab/focused_chain_repaired_bridge_expanded60/expanded_60_20260508_005703`
- Baseline cache: 42 cached / 18 fresh
- Cache manifest hash: `df208500e1d1a2cbfafae05f2b73e1a75b8929d245506836acc17deeb463099d`
- Candidate OpenAI response cache: disabled

## Safety Statement

Final repaired-chain expanded60 had zero runtime exceptions and zero helper side-effect incidents. Unsafe helper forms were parked:

- `next_dependency_precondition_call`: one side-effect incident in force diagnostic.
- Initial frozen generated expanded60 pack: two side-effect incidents.

The runtime now allows composite helpers that explicitly preserve `selected_record` on missing updates to execute their own output logic instead of being preempted by a generic missing-update abstain. The side-effect preservation checker now treats a selection-only bridge as requiring the original side-effect later, rather than falsely flagging the later preserved side-effect as unsafe.

## Recommendation

Do not promote any result from this branch to protected evidence. The best candidate for a later campaign is a recombined focused pack centered on:

- `select_recency_target_and_prepare_action`
- `resolve_search_window_or_bounds`
- selected contact scalar/search planners

The next campaign should target adoption rather than more broad generation: test a tiny recency/action bundle where `select_record_by_timestamp_extreme` is removed or deprioritized, add clearer actor affordances for when to call the composite bridge, and run another 20-task mechanism/pilot before any 60-task rerun. Formal validation is not warranted until that bundle shows positive primary outcome on unseen confirmation with natural calls and zero incidents.

## Decision

`STOP: required experiment families received fair-chance treatment; no scalable safe outcome-positive approach found`
