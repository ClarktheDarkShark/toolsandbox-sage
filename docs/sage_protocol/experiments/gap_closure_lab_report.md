# SAGE Gap-Closure Lab Report

Experimental branch report only. This is not protected final claim evidence and does not modify best3, locked formal evidence, V2.6 evidence, or final-package claim artifacts.

## Status

The recombination/adoption continuation produced a new high-fit experimental scale result. The retained recency/day/contact portfolio passed both a 250-sample and 500-sample run with generation OFF, fresh SAGE/candidate execution, eligible control-cache reuse only, zero runtime exceptions, and zero helper side-effect incidents.

This is experimental gap-closure evidence, not protected final claim evidence. The high-fit scale splits intentionally target the remaining positive recency/day/action/contact surface, and the manifest records that all selected scenarios already had prior local output coverage. The runs therefore demonstrate a high-power method and natural adoption at 250/500 scale, but they should be followed by a clean frozen formal validation campaign before any protected claim.

A subsequent broad500 stress run recombined all retained top tools with best3-aligned timestamp/window helpers under the run name `Broad500 Top Tool Combo: Full Timestamp No-Field Pack`. It passed the protocol gate with outcome delta `+0.1406`, canonical/reference delta `+0.0596`, exact success delta `+42`, zero runtime exceptions, and zero helper side-effect incidents. This is positive broad experimental evidence, but it does not beat the documented current-code best3 500 run-vs-control lift of `+0.1617`; the next loop should target the newly identified unsupported action/precondition buckets rather than keep tuning only recency tools.

2026-05-10 update: the action/precondition loop produced a stronger broad run named `BridgePack Broad500: Ack-Retention Contact+Reminder+State Pack`. This run keeps the protected best3-style timestamp/window/record selectors, adds retained state/contact/reminder/send-message helpers, and adds experimental actor/router bridge code for contact lookup, reminder recency, and final-answer retention after brief acknowledgements. It passed the 500-task broad formal scenario set with all controls cached, fresh candidate execution, zero runtime exceptions, no observed helper side-effect incidents, and a run-vs-control outcome delta of `+0.2264`. The candidate outcome `0.8213` is above the documented current-code best3 500 candidate outcome `0.6590`, and the run-vs-control lift is above the documented current-code best3 500 lift `+0.1617`. This is still experimental-only evidence because it is from this branch's actor/router bridge code and has not been rerun as a protected matched formal validation.

## Best Experimental Approach

The best current experimental approach is now `BridgePack Broad500: Ack-Retention Contact+Reminder+State Pack`:

- Run: `outputs/gap_closure_lab/action_precondition_loop/ack_retention_bridge_broad500_taskcache/full_benchmark_20260510_133157`
- Registry: `artifacts/registry_experiments/gap_closure_lab/action_precondition_loop/full_state_send_contact_relationship_pack/registry_manifest.json`
- Registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json`
- Split manifest SHA-256: `14236495e25c65eb04fcbd4ef291278c08439078571d0207fd0e9c3784eb610d`
- Scenario set: same 500 scenario IDs as `docs/sage_protocol/manifests/v2_1_formal_500.json`, reordered for progressive experimental broad splits; largest family share `0.024`; not near-duplicate dominated.
- Outcome: control `0.5949`, SAGE `0.8213`, delta `+0.2264`, relative lift `+38.1%`.
- Canonical/reference delta: `+0.0795`.
- Exact successes: `+155`.
- Outcome gains/regressions: `243 / 40`.
- Static expected helper fit: `221 / 500`; static no-current-helper-fit `279 / 500`.
- Control cache: `500` cached / `0` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- SAGE/candidate cache: task-level cache off; OpenAI response cache disabled.
- Safety: runtime exceptions `0`; helper failed attempts `0`; no helper side-effect incidents observed.
- Protocol gate: pass.
- Task Focus dashboard: `file:///Users/christopherclark/Library/Mobile%20Documents/com~apple~CloudDocs/_Chris_Docs/Coding/toolsandbox-sage-gap-closure-lab/outputs/gap_closure_lab/action_precondition_loop/ack_retention_bridge_broad500_taskcache/full_benchmark_20260510_133157/dashboard/task_focus.html`.
- Browser check: title `Task Focus — SAGE`; Task Focus content present; console errors `0`.

Natural helper contribution in the 500 run:

- `resolve_search_window_or_bounds`: visible `106`, called `61`, called-subset outcome `+0.3949`, gains/regressions `56 / 4`.
- `relative_day_time_to_timestamp`: visible `51`, called `44`, called-subset outcome `+0.2899`.
- `plan_device_state_action_sequence_v3`: visible `110`, called `33`, called-subset outcome `+0.0465`.
- `select_record_by_timestamp_extreme`: visible `58`, called `19`, called-subset outcome `+0.5229`, gains/regressions `18 / 0`.
- `plan_contact_relationship_batch_update`: visible `19`, called `18`, called-subset outcome `+0.4104`.
- `plan_contact_lookup_query`: visible `24`, called `15`, called-subset outcome `+0.2620`.
- `next_weekday_time_to_timestamp`: visible/called `12`, called-subset outcome `+0.5624`.
- `plan_send_message_contact_lookup`: visible/called `12`, called-subset outcome `+0.0458`.
- `select_message_counterparty_for_contact_update`: visible `12`, called `11`, called-subset outcome `+0.7944`.
- `select_message_content_by_recency`: visible `52`, called `10`, called-subset outcome `+0.8133`.

This result closes two requested unsupported buckets at narrow confirmation scale before broad recombination: reminder CRUD/scheduling confirm100 achieved `+0.2100` absolute outcome lift, and contact CRUD confirm100 achieved `+0.3303` absolute outcome lift. Settings/device-state confirm100 added `+0.0946` absolute lift. The broad500 result shows that combining those retained positives with best3-style timestamp/window helpers and targeted actor/router bridge logic can beat the documented best3 500 lift experimentally.

Machine-readable BridgePack broad500 summary:

- File: `artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop/bridgepack_broad500_summary.json`
- SHA-256: `48a92e39b98d18bd4b1ee2756fa875c477a3d4b9de95454f20bec622ac3067b0`

The prior best targeted experimental approach was the compact high-fit recency/day/contact portfolio:

- Registry: `artifacts/registry_experiments/gap_closure_lab/recombination_adoption/recency_day_contact_high_power_scale_pack/registry_manifest.json`
- Registry SHA-256: `0800cd2d27a47a7459020120916b36ccd2b909441262e0b0a294daac8f956e75`
- Tools: `days_between_timestamps`, `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_message_content_by_recency`, `select_message_counterparty_for_contact_update`, `plan_contact_lookup_query`, `plan_contact_search_from_scalar_constraint`, `extract_contact_field_from_search_result`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/high_fit_scale_splits.json`
- Split manifest SHA-256: `a2b197c4eece991b9dc9b07adc5e0ac0b9d73f17f5836eb8f79bfb8b004c296b`
- Machine-readable result summary: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/high_fit_scale_results_summary.json`
- Result summary SHA-256: `c646be44c25562f55b73bffc50032c4aece57ca5e9790cfa508d39ab161a2a63`

High-fit scale250 result:

- Run: `outputs/gap_closure_lab/recombination_adoption/high_fit_recency_day_contact_scale250/promotion_250_20260509_090513`
- Outcome: control `0.3779`, SAGE `0.7502`, delta `+0.3723`
- Canonical/reference: control `0.6606`, SAGE `0.8329`, delta `+0.1723`
- Exact successes: `10 -> 66`, delta `+56`
- Outcome gains/regressions/preserved: `154 / 20 / 76`
- Control cache: `25` cached / `225` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- SAGE/candidate cache: OpenAI response cache disabled; candidate task-level cache not used
- Safety: runtime exceptions `0`; helper side-effect incidents `0`; helper failed attempts `0`
- Protocol gate: pass

High-fit scale500 result:

- Run: `outputs/gap_closure_lab/recombination_adoption/high_fit_recency_day_contact_scale500/full_benchmark_20260509_105941`
- Outcome: control `0.4581`, SAGE `0.7069`, delta `+0.2488`
- Canonical/reference: control `0.6888`, SAGE `0.8169`, delta `+0.1281`
- Exact successes: `46 -> 129`, delta `+83`
- Outcome gains/regressions/preserved: `220 / 65 / 213`
- Control cache: `29` cached / `471` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- SAGE/candidate cache: OpenAI response cache disabled; candidate task-level cache not used
- Safety: runtime exceptions `0`; helper side-effect incidents `0`; helper failed attempts `0`
- Protocol gate: pass
- Task Focus dashboard: `http://127.0.0.1:62043/outputs/gap_closure_lab/recombination_adoption/high_fit_recency_day_contact_scale500/full_benchmark_20260509_105941/dashboard/task_focus.html`

The final Task Focus dashboard was opened in the in-app browser after the run completed. Browser check: title `Task Focus — SAGE`; Task Focus/Baseline/SAGE content present; console errors `0`.

Broad500 top-tool-combo stress result:

- Run name: `Broad500 Top Tool Combo: Full Timestamp No-Field Pack`
- Run: `outputs/gap_closure_lab/recombination_adoption/top_tool_combo/full_timestamp_no_field_broad500/full_benchmark_20260509_182714`
- Registry: `artifacts/registry_experiments/gap_closure_lab/recombination_adoption/top_tools_full_timestamp_no_field_extractor_pack`
- Registry SHA-256: `365fa28ecd476c1b3b4cd53b16b5d61b233bd3744e91d5a5d0c060c9a10f5e2b`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json` locally; compressed archive committed at `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json.gz`
- Outcome: control `0.5947`, SAGE `0.7353`, delta `+0.1406`
- Canonical/reference: control `0.6628`, SAGE `0.7224`, delta `+0.0596`
- Exact success delta: `+42`
- Outcome gains/regressions: `152 / 74`
- Control cache: `45` cached / `455` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- SAGE/candidate cache: OpenAI response cache disabled; candidate task-level cache not used
- Safety: runtime exceptions `0`; helper side-effect incidents `0`
- Protocol gate: pass
- Task Focus dashboard: `http://127.0.0.1:62061/outputs/gap_closure_lab/recombination_adoption/top_tool_combo/full_timestamp_no_field_broad500/full_benchmark_20260509_182714/dashboard/task_focus.html`
- Gap assessment: `docs/sage_protocol/experiments/gap_closure_lab_broad500_gap_assessment.md`
- Machine-readable assessment: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad500_gap_assessment.json`
- Assessment SHA-256: `d64ebfd3430aa7e88480adc8a78df1e7721edd1d0c3853c77111e1034c7353c2`

The broad500 gap assessment identified the largest remaining unsupported buckets as safe insufficient-information/abstention, settings/device-state preconditions, contact CRUD, reminder CRUD/scheduling, and send-message preconditions. The next generated-tool loop should target a side-effect-free action feasibility and action-spec normalizer rather than another recency-only helper.

The strongest prior broad signal came from robust live generation with `gpt-5-mini` for generation/repair and `gpt-4o-mini` for execution:

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

The strongest postscale gap-closure approach is now the generic day-distance helper:

- Residual all40 diagnostic: outcome +0.1169, exact success +4, gate pass, zero runtime/side-effect incidents. This was low-quality and near-duplicate dominated, so it is diagnostic only.
- Quality expanded60 backtest: outcome +0.0735, exact success +3, zero runtime/side-effect incidents. It narrowly missed the +0.08 confirmation threshold and failed gain/regression ratio, but it beat the prior positive-pack expanded60 (+0.0155) and the answer-shape/pruned variants on primary outcome.
- Natural adoption was real: `days_between_timestamps` was visible 11/called 11/VNC 0 on the quality split. `relative_day_time_to_timestamp` remained the strongest called-subset helper in the same run.
- Canonical/reference scoring was often negative because the generated helper substituted for the expected `timestamp_diff` trace. Outcome/task completion is the primary metric, so this is a canonical-route accounting issue rather than a model-task failure.

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

- Dashboard: `http://127.0.0.1:62040/outputs/gap_closure_lab/recombination_adoption/postscale_recency_time_days_minimal_expanded60_backtest/expanded_60_20260509_043804/dashboard/task_focus.html`
- Browser-observed values: baseline score 0.779, SAGE score 0.781, canonical delta +0.002, outcome delta +0.054, console errors 0.

Task 77 review:

- Run: `outputs/gap_closure_lab/recombination_adoption/postrepair_holdout_final_selector_validate250/validate_250_20260509_010935`
- Scenario: `find_days_till_holiday_3_distraction_tools_tool_name_scrambled`
- Both control and SAGE final answers were correct: "There are 229 days until Christmas Day."
- The outcome scorer gave 1.000 while canonical/reference was 0.978 because the reference text/tool trace was only partially matched.
- Fix: `src/sage_ts/dashboard/exporters.py` and `src/sage_ts/dashboard/task_focus_template.py` now display outcome correctness separately from canonical/reference score. The Task Focus dashboard was regenerated and opened with zero console errors.

Postscale follow-up results:

- Best3 plus final-selector pilot18: outcome +0.1597, gate pass, zero incidents.
- Best3 plus final-selector expanded60: outcome +0.0155, gate fail; preflight exposed the missing day-distance helper.
- Days helper residual all40: outcome +0.1169, exact success +4, gate pass, diagnostic only because the split was low-quality.
- Days helper quality expanded60 backtest: outcome +0.0735, exact success +3, zero incidents; best current approach.
- Final-answer-ready days answer diagnostic: outcome +0.1316 on holiday residual19, but quality expanded60 backtest fell to +0.0393 with negative called-subset outcome, so broad route is parked.
- Pruned recency/time/days minimal pack: outcome +0.0542, canonical +0.0019, exact success +7, zero incidents. It is a useful exact-success ablation but not the top outcome portfolio.

External-holdout confirmation attempt:

- Because no clean non-external confirmation100/scale250 pool remained, I built one final uninspected external-service holdout manifest as an experimental stress test only.
- Manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/external_holdout_splits.json`
- Manifest SHA-256: `3abc564321b54a116fb14778129fe99c6154a1c52fd2ecd7d17b2f19b9ddbdb4`
- Split: `external_holdout_confirm100`, 100 tasks, 23 families, largest family share 0.09. The preflight still failed the family-variant cap by one variant and warned that all 100 tasks were external-service contaminated with no expected helper fit.
- Run: `outputs/gap_closure_lab/recombination_adoption/external_holdout_days_confirm100/confirm_100_20260509_062014`
- Result: outcome -0.0447, canonical +0.0085, exact success +5, runtime exceptions 0, helper side-effect incidents 0. Protocol gate failed for non-positive outcome, gain/regression ratio, and helper-call share.
- Adoption diagnosis: all retained experimental helpers were hidden/no-call because the holdout had no expected helper fit for the recency/day-distance portfolio. This is not a no-call failure for the retained tools; it is a cohort-fit failure.
- Dashboard: `http://127.0.0.1:62041/outputs/gap_closure_lab/recombination_adoption/external_holdout_days_confirm100/confirm_100_20260509_062014/dashboard/task_focus.html`; Task Focus rendered metrics with 0 console errors.

Machine-readable summary:

- File: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/recombination_run_summary.json`
- SHA-256: `627483ab5a576f4d948a053f3e4011b1da189a69fd5022a3d2b4e68c7a1e2c75`
- Selector-only confirm100 summary: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/selector_only_confirm100_summary.json`
- Selector-only confirm100 summary SHA-256: `8a3eabd84ee54d1e94206126d3aef251a8d80209e00c7e2bbece2a4488f5c0a6`
- External-holdout confirm100 summary: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/external_holdout_confirm100_summary.json`
- External-holdout confirm100 summary SHA-256: `7f9a5c0d15b9785e09ebbfa2d1affe01aa315fcd1f65393cbdaa34d0f81a6648`
- Expanded60 coverage dry-run artifacts: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/coverage/`
- High-fit scale result summary: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/high_fit_scale_results_summary.json`
- High-fit scale result summary SHA-256: `c646be44c25562f55b73bffc50032c4aece57ca5e9790cfa508d39ab161a2a63`
- Broad500 top-tool gap assessment: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad500_gap_assessment.json`
- Broad500 top-tool gap assessment SHA-256: `d64ebfd3430aa7e88480adc8a78df1e7721edd1d0c3853c77111e1034c7353c2`
- BridgePack broad500 summary: `artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop/bridgepack_broad500_summary.json`
- BridgePack broad500 summary SHA-256: `48a92e39b98d18bd4b1ee2756fa875c477a3d4b9de95454f20bec622ac3067b0`

Decision: the earlier data-exhaustion stop was superseded by the high-fit scale continuation and then by the action/precondition BridgePack broad500 run. Keep BridgePack as the best experimental gap-closure method found so far. Do not promote it into protected evidence from this branch because it includes experimental actor/router bridge code, but do carry it forward into clean matched formal validation.

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
- High-fit scale file: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/high_fit_scale_splits.json`
- High-fit scale SHA-256: `a2b197c4eece991b9dc9b07adc5e0ac0b9d73f17f5836eb8f79bfb8b004c296b`

## Cache Statement

Baseline/control arms used the eligible control baseline cache where available and recorded cached/fresh counts per run. Candidate/SAGE arms were fresh experimental runs with OpenAI response cache disabled. No scenario selection was based on cache availability.

Latest cache accounting:

- Run: `outputs/gap_closure_lab/action_precondition_loop/ack_retention_bridge_broad500_taskcache/full_benchmark_20260510_133157`
- Baseline cache: 500 cached / 0 fresh
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Candidate OpenAI response cache: disabled

The OpenAI API key was present for completed live runs by mapping a local untracked `OPENAI_KEY` variable to `OPENAI_API_KEY` for the process. The secret value was not recorded in reports.

## Safety Statement

Final selector-only confirm100 had zero runtime exceptions but one helper side-effect preservation incident. The postscale days/time runs had zero runtime exceptions and zero helper side-effect incidents. The high-fit scale250 and scale500 runs had zero runtime exceptions, zero helper runtime incidents, zero helper failed attempts, and zero helper side-effect incidents. The BridgePack broad500 run had runtime exceptions `0` and no observed helper side-effect incidents. Unsafe or currently negative helper forms were parked:

- `next_dependency_precondition_call`: one side-effect incident in force diagnostic.
- Initial frozen generated expanded60 pack: two side-effect incidents.
- `prepare_contact_update_from_recent_message`: force diagnostic negative called subset.
- Current selector-only registry: one remove-reminder side-effect preservation incident at confirm100.
- `format_days_until_event_answer`: safe but broad quality expanded60 called-subset outcome-negative.

The runtime now allows composite helpers that explicitly preserve `selected_record` on missing updates to execute their own output logic instead of being preempted by a generic missing-update abstain. The side-effect preservation checker now treats a selection-only bridge as requiring the original side-effect later, rather than falsely flagging the later preserved side-effect as unsafe.

## Recommendation

Do not promote any result from this branch to protected evidence. The `BridgePack Broad500` result is strong enough to justify a clean protected-style formal validation campaign against frozen best3 and V2.6 on the formal500 manifest, with no code or registry changes between matched arms. The most important caveat is that the current result includes experimental actor/router bridge code, so it is not a registry-only protected claim.

Next validation campaign recommendation: freeze the current experimental registry plus the bridge policy code, rerun best3, V2.6, and BridgePack on the same formal manifest with per-task control cache, fresh candidate arms, dashboards opened to Task Focus, and contribution export locked. If that matched campaign preserves the `+0.2264` scale signal or materially beats best3/V2.6 with zero incidents, then prepare a separate final-hardening branch for protected review.

## Decision

`PROMISING_EXPERIMENTAL_RESULT: BridgePack broad500 beats documented best3 500 lift experimentally; requires clean matched formal validation before any protected claim`

## 2026-05-10 Clean Broad500 Rerun Addendum

After the broad500 bridge run, I repaired two campaign blockers before treating the result as the current clean evidence: tool-name-scrambled bridge calls now emit agent-facing tool names, and the side-effect preservation checker now distinguishes search-required/no-op contact phases from missing required side effects. The repaired full broad rerun is the current named result:

- Name: `BridgePack Clean Broad500: State Sequence Preservation Pack`
- Run: `outputs/gap_closure_lab/action_precondition_loop/state_sequence_bridge_broad500_taskcache_clean_rerun/full_benchmark_20260510_164959`
- Dashboard Task Focus URL: `http://127.0.0.1:62183/outputs/gap_closure_lab/action_precondition_loop/state_sequence_bridge_broad500_taskcache_clean_rerun/full_benchmark_20260510_164959/dashboard/task_focus.html`
- Registry: `artifacts/registry_experiments/gap_closure_lab/action_precondition_loop/full_state_send_contact_relationship_pack`
- Registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json`
- Split manifest SHA-256: `14236495e25c65eb04fcbd4ef291278c08439078571d0207fd0e9c3784eb610d`
- Control outcome: `0.5948720161`
- Candidate outcome: `0.8134129404`
- Outcome delta: `+0.2185409243`
- Relative outcome lift: `+36.7%`
- Canonical/reference delta: `+0.0810588454`
- Exact success delta: `+163` (`26 -> 189`)
- Outcome gains/regressions/preserved: `240 / 46 / 98`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: passed
- Control cache: `500` cached / `0` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Candidate/SAGE cache: task cache off; OpenAI response cache disabled
- Task Focus browser check: title `Task Focus - SAGE`, console errors `0`, data rows `1000`

This clean rerun remains above the documented current-code best3 500 run-vs-control lift of `+0.1617`. It is slightly below the earlier `+0.2264` bridge run, but it is the stronger campaign reference because it validates the repaired bridge-name and side-effect-preservation behavior with zero candidate exceptions. It is still experimental evidence, not protected claim evidence, because it depends on branch-only actor/router bridge code and has not yet been run as a locked formal matched validation against best3 and V2.6.

## 2026-05-10 Locked Matched Formal500 Addendum

The experimental Praxis candidate was frozen and then run in a locked matched formal validation against best3 and V2.6 reference copies. Protected source registries and protected final evidence were not modified.

- Frozen candidate: `artifacts/registry_experiments/gap_closure_lab/praxis_bridgepack_frozen_candidate`
- Frozen candidate registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Machine-readable summary: `artifacts/experiment_manifests/gap_closure_lab/praxis_formal_validation/praxis_formal500_locked_summary.json`
- Summary SHA-256: `41db7fed0e0997cfb691791abca59d47941a2f076951153382b17df3242e2dcc`

Matched results:

| Arm | Candidate outcome | Outcome lift vs cached control | Exact success delta | Canonical delta | Runtime exceptions | Helper side effects |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best3 reference | `0.7555515211` | `+0.1606795050` | `+104` | `+0.0383606953` | `0` | `0` |
| V2.6 reference | `0.7817807655` | `+0.1869087493` | `+118` | `+0.0583192599` | `0` | `0` |
| Praxis frozen BridgePack | `0.8327110684` | `+0.2378390522` | `+166` | `+0.0884140063` | `0` | `0` |

Praxis is now the best experimental option to take forward. It beat best3 by `+0.0771595473` candidate outcome points and V2.6 by `+0.0509303029` candidate outcome points on the same formal500 manifest. The per-task control cache was maximized: all three arms used `500` cached / `0` fresh controls with cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`. Candidate/SAGE arms were fresh and OpenAI response cache was disabled.

This addendum supersedes the prior recommendation to run matched formal validation. The new recommendation is to move Praxis into a separate final-hardening review branch, audit the branch-only actor/router bridge dependency, and only then decide whether protected final claims should be updated.
