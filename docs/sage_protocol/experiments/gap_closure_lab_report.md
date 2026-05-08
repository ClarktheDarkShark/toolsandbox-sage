# SAGE Gap-Closure Lab Report

Experimental branch report only. This is not protected final claim evidence and does not modify best3, locked formal evidence, V2.6 evidence, or final-package claim artifacts.

## Status

Stop condition 2 remains met for the full campaign. All required experiment families received fair-chance diagnostic or expanded-pilot treatment, including repair and force diagnostics where appropriate. The focused recombination continuation did produce an expanded60 natural-adoption signal for the retained selector, but confirm100 failed broad outcome and safety, so no approach is promotion-ready.

## Best Experimental Approach

The strongest broad signal came from robust live generation with `gpt-5-mini` for generation/repair and `gpt-4o-mini` for execution:

- Live generation pilot20: outcome +0.2090, canonical +0.0127, gate pass, zero runtime/side-effect incidents.
- Frozen generated pilot20: outcome +0.1377, canonical +0.0772, gate pass, zero runtime/side-effect incidents.
- Expanded60 of the frozen pack: outcome +0.0707, canonical +0.0628, but two side-effect incidents, so it was not safe for promotion.

The strongest low-frequency tool signal was `select_recency_target_and_prepare_action`:

- Force-after-search diagnostic on 2 recency side-effect tasks: outcome +0.2931, canonical +0.1648, zero incidents.
- Repaired natural safety diagnostic on the same 2-task mechanism split: outcome +0.1460, canonical +0.2102, zero incidents.
- Expanded60 rerun: canonical +0.0441 and exact successes +6, but primary outcome -0.0189 and the chain was visible-not-called on both target recency tasks.
- Selector-only expanded60 continuation: outcome +0.0045, canonical -0.0487, visible 2/called 2/VNC 0, called-subset outcome +0.2478, zero runtime exceptions.
- Selector-only confirm100: outcome -0.1004, canonical -0.0483, visible 5/called 2/VNC 3, called-subset outcome 0.0, and one helper side-effect preservation incident.

That means the recency bridge has real potential on rare eligible tasks, but the current registry is not a standalone scale candidate.

## Recombination And Adoption Follow-Up

Per the follow-on instruction, the retained low-frequency positives were recombined into smaller recency/action portfolios and tested specifically for natural adoption and routing. Frequency was not treated as the main value criterion; a tool can remain useful if it solves a rare critical gap safely and is available when that gap appears again.

Focus20 targeted recency/action results were positive:

- Minimal strict pack: outcome +0.1518, canonical +0.1198; `resolve_search_window_or_bounds` was called 8/14 visible with called-subset outcome +0.2971.
- Adoption-minimal pack: outcome +0.1482, canonical +0.1597; `resolve_search_window_or_bounds` was called 9/20 visible with called-subset outcome +0.5213, and `select_recency_target_and_prepare_action` received one natural call.
- Contact bridge pack: outcome +0.2695, canonical +0.2857; lift came from the recency/action core, not contact helper calls.
- Best3 bridge pack: outcome +0.3530, canonical +0.2672; `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`, and `select_recency_target_and_prepare_action` all received natural calls with positive called-subset outcome.
- V2.6 bridge pack: outcome +0.5452, canonical +0.2976; strongest targeted result, again driven by recency/action calls rather than contact helper calls.

The targeted focus20 manifest is intentionally mechanism-focused, not broad claim evidence:

- File: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/recombination_focus20_manifest.json`
- SHA-256: `930d11e8e399def1cba17d8683a52d5047b03d4f153ceff8ea2fe26cf0eca065`
- Quality note: targeted recency/action cohort; useful for adoption diagnostics, but not diverse enough for promotion.

The first broad expanded60 bridge results did not justify confirmation100:

- V2.6 bridge expanded60: outcome +0.0050, canonical -0.0429, exact success delta 0, zero runtime exceptions, protocol gate failed. Helper-call share was below 25%; `select_recency_target_and_prepare_action` was visible 2 times and called 0 times.
- Best3 bridge expanded60: outcome -0.0734, canonical -0.0031, exact success delta 0, zero runtime exceptions, protocol gate failed. Helper-call share was below 25%; `select_recency_target_and_prepare_action` was visible 2 times and called 0 times.

Per the later campaign instruction, the positive but low-frequency selector was not discarded. I tested smaller recency/action variants focused on natural adoption:

- Adoption-minimal expanded60: outcome +0.0480, canonical -0.0551; selector called 1/2 visible with canonical +0.1808 and outcome preserved, but the resolver called subset was negative.
- Action-only contact/selector expanded60: outcome -0.0052, canonical -0.0829; contact helper visible 1/called 0 and selector visible 2/called 0.
- Force-after-search contact diagnostic: outcome -0.0406, canonical -0.0368; forced contact helper called subset -0.0937 outcome, so the contact helper was parked. The selector still showed called-subset outcome +0.2500 on four natural calls.
- Selector-only expanded60: outcome +0.0045, canonical -0.0487; selector visible 2/called 2/VNC 0 with called-subset outcome +0.2478 and canonical +0.1026. This met the focused expanded60 adoption objective, though not the formal broad gate.
- Selector-only confirm100: outcome -0.1004, canonical -0.0483, exact success -4; selector visible 5/called 2/VNC 3 with called-subset outcome 0.0 and one side-effect preservation incident. This blocks scale and promotion.

All recombination dashboards were opened to the Task Focus view. The latest Task Focus browser check rendered paired data with no console errors:

- Dashboard: `http://127.0.0.1:62005/outputs/gap_closure_lab/recombination_adoption/selector_only_confirm100/confirm_100_20260508_095751/dashboard/task_focus.html`
- Browser-observed values: baseline score 0.761, SAGE score 0.713, canonical delta -0.048, outcome delta -0.100, console errors 0.

Machine-readable summary:

- File: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/recombination_run_summary.json`
- SHA-256: `627483ab5a576f4d948a053f3e4011b1da189a69fd5022a3d2b4e68c7a1e2c75`
- Selector-only confirm100 summary: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/selector_only_confirm100_summary.json`
- Selector-only confirm100 summary SHA-256: `8a3eabd84ee54d1e94206126d3aef251a8d80209e00c7e2bbece2a4488f5c0a6`
- Expanded60 coverage dry-run artifacts: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/coverage/`

Decision: keep the expanded60 selector result as experimental potential, but park the current selector-only registry from scale. Any next attempt must repair side-effect preservation on remove-reminder actions and improve natural adoption on visible action targets before another confirmation run.

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

Latest confirmation cache accounting:

- Run: `outputs/gap_closure_lab/recombination_adoption/selector_only_confirm100/confirm_100_20260508_095751`
- Baseline cache: 0 cached / 100 fresh
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Candidate OpenAI response cache: disabled

## Safety Statement

Final selector-only confirm100 had zero runtime exceptions but one helper side-effect preservation incident. Unsafe or currently negative helper forms were parked:

- `next_dependency_precondition_call`: one side-effect incident in force diagnostic.
- Initial frozen generated expanded60 pack: two side-effect incidents.
- `prepare_contact_update_from_recent_message`: force diagnostic negative called subset.
- Current selector-only registry: one remove-reminder side-effect preservation incident at confirm100.

The runtime now allows composite helpers that explicitly preserve `selected_record` on missing updates to execute their own output logic instead of being preempted by a generic missing-update abstain. The side-effect preservation checker now treats a selection-only bridge as requiring the original side-effect later, rather than falsely flagging the later preserved side-effect as unsafe.

## Recommendation

Do not promote any result from this branch to protected evidence. The selector-only expanded60 result deserves later design attention, not formal validation. The next campaign should repair the selector for side-effect preservation, keep it narrowly routed to post-search action tasks, and rerun an expanded60 adoption test before any new confirmation. Formal validation is not warranted until confirmation is positive with natural calls and zero incidents.

## Decision

`STOP: required experiment families received fair-chance treatment; no scalable safe outcome-positive approach found`
