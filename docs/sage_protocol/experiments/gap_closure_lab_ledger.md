# SAGE Gap-Closure Lab Ledger

Experimental evidence only. Nothing in this ledger modifies protected best3, formal, V2.6, or final-package evidence.

## Campaign State

- Branch: `exp/sage-gap-closure-lab`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/gap_closure_lab_splits.json`
- Split file SHA-256: `7843305bfee2e0d021ecd0ab429ea12f88cb381676615079538836c91e9f84c9`
- Split payload SHA-256: `41a9565960005007bdcc8a0e901b81a300e2e5c1c52c0b38e15e17fe83f983d4`
- Baseline cache manifest hashes observed: earlier campaign `df208500e1d1a2cbfafae05f2b73e1a75b8929d245506836acc17deeb463099d`; recombination continuation `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Candidate/SAGE arms: fresh runs with OpenAI response cache disabled for experimental comparisons.
- Dashboard discipline: each completed run with a dashboard was opened to the Task Focus dashboard; latest opened dashboard is `outputs/gap_closure_lab/recombination_adoption/selector_only_confirm100/confirm_100_20260508_095751/dashboard/task_focus.html`.

## Experiment Runs

| ID | Experiment | Sample | Registry / tools | Cache | Result | Decision |
| --- | --- | ---: | --- | --- | --- | --- |
| GCL-000 | Branch, manifest, and preflight setup | 0 | Split builder, preflight, protected-path checks | None | Preflight now ready; OpenAI API present; no protected assets modified | Complete |
| GCL-001 | Protected best3 reference copy | 20 unseen | `best3_reference_copy`, SHA `76de726d...` | 0 cached / 20 fresh | Outcome +0.1645, canonical +0.0218, gate false due helper-call gate | Baseline reference only |
| GCL-002 | Best3 + V2.6 contact-scalar reference copy | 20 unseen | `best3_v26_reference_copy`, SHA `ab5f5c36...` | 0 cached / 20 fresh | Outcome +0.0660, canonical +0.0300, gate false | Reference only |
| GCL-003 | Robust live generation with stronger generator | 20 unseen | `live_generation_working`, generated with `gpt-5-mini`, executed with `gpt-4o-mini` | 0 cached / 20 fresh | Outcome +0.2090, canonical +0.0127, gate true, 0 runtime/side-effect incidents | Freeze and retest |
| GCL-004 | Frozen live-generated candidate pack | 20 unseen | 12-tool frozen candidate pack | 7 cached / 13 fresh | Outcome +0.1377, canonical +0.0772, gate true, 0 incidents | Promising pilot; expand |
| GCL-005 | Force diagnostic: `next_service_tool_call` | 5 mechanism | Force-call diagnostic registry | 5 cached / 0 fresh | Outcome -0.0105, canonical +0.0334, 0 incidents | Park |
| GCL-006 | Force diagnostic: `next_dependency_precondition_call` | 4 mechanism | Force-call diagnostic registry | 4 cached / 0 fresh | Outcome +0.0289, canonical -0.0434, 1 side-effect incident | Park unsafe current form |
| GCL-007 | Force diagnostic: `select_action_target_by_recency` | 1 mechanism | Force-call diagnostic registry | 1 cached / 0 fresh | Outcome -0.0631, canonical +0.2197, 0 incidents | Keep only as design signal |
| GCL-008 | Force diagnostic: `extract_service_answer_field` | 2 single-task diagnostics | Force-call diagnostic registry | 2 cached / 0 fresh | Outcome 0.0, canonical small positive; force hook did not expose decisive value | Refine, not promote |
| GCL-009 | Frozen generated pack expanded pilot | 60 unseen | `live_generation_working` | 0 cached / 60 fresh | Outcome +0.0707, canonical +0.0628, but 2 side-effect incidents | Unsafe; remove risky helpers |
| GCL-010 | Refined candidate pack | 60 unseen | `refined_candidate_pack` | 0 cached / 60 fresh | Outcome -0.0566, canonical -0.1236, 0 incidents | Park broad pack |
| GCL-011 | Full pack minus unsafe state helpers | 60 unseen | `full_minus_unsafe_state_pack` | 0 cached / 60 fresh | Outcome -0.0048, canonical +0.0124, 0 incidents | Keep low-frequency positives, not scale |
| GCL-012 | Full pack plus abstention detector | 60 unseen | `full_plus_abstention_pack` | 27 cached / 33 fresh | Outcome -0.0655, canonical -0.0005, 0 incidents | Park abstention overlay |
| GCL-013 | Affordance-rich guard metadata | 60 unseen | `affordance_rich_guard_pack` | 60 cached / 0 fresh | Outcome -0.0710, canonical +0.0060, 0 incidents | Park metadata style |
| GCL-014 | Focused chain/router pack | 60 unseen | `focused_chain_pack` | 42 cached / 18 fresh | Outcome +0.0160, canonical -0.0014, 0 incidents; chain visible-not-called | Diagnose no-call |
| GCL-015 | Force-after-search diagnostic for repaired chain target | 2 mechanism | `focused_chain_pack`, forced `select_recency_target_and_prepare_action` | 1 cached / 1 fresh | Outcome +0.2931, canonical +0.1648, 0 incidents | Latent value; repair output shape/adoption |
| GCL-016 | Repaired chain, pre-safety-accounting expanded run | 60 unseen | `focused_chain_repaired_pack`, SHA `ed02d615...` | 42 cached / 18 fresh | Outcome -0.0200, canonical -0.0053, 0 incidents; wrapper had been repaired but adoption weak | Continue fair-chance diagnostic |
| GCL-017 | Natural two-task repaired-chain diagnostic | 2 mechanism | `focused_chain_repaired_pack` | 2 cached / 0 fresh | Outcome +0.1492, canonical +0.1110; selected record preserved; old safety accounting logged a false incident | Repair safety accounting |
| GCL-018 | Natural two-task repaired-chain safety diagnostic | 2 mechanism | `focused_chain_repaired_pack` | 2 cached / 0 fresh | Outcome +0.1460, canonical +0.2102, 0 side-effect/runtime incidents | Low-frequency positive; expand once |
| GCL-019 | Repaired chain expanded rerun | 60 unseen | `focused_chain_repaired_pack` | 42 cached / 18 fresh | Outcome -0.0189, canonical +0.0441, exact success +6, 0 incidents; helper call share below 25%, chain VNC 2/2 | Do not confirm/scale; retain pockets |
| GCL-020 | Recombination setup: focused recency/action registries | 20 targeted focus manifest | Five experimental registries under `registry_experiments/gap_closure_lab/recombination_adoption` | None | Created minimal, adoption-minimal, contact-bridge, best3-bridge, and V2.6-bridge packs; focus manifest SHA `930d11e8...` | Run focused adoption pilots |
| GCL-021 | Recombination minimal strict focus20 | 20 targeted unseen | `recency_action_minimal_strict_pack` | 0 cached / 20 fresh | Outcome +0.1518, canonical +0.1198, zero runtime exceptions; `resolve_search_window_or_bounds` called 8/14 visible with called-subset outcome +0.2971 | Retain recency window helper; test adoption variants |
| GCL-022 | Recombination adoption-minimal focus20 | 20 targeted unseen | `recency_action_adoption_minimal_pack` | 0 cached / 20 fresh | Outcome +0.1482, canonical +0.1597, zero runtime exceptions; composite bridge received one natural call | Retain; combine with prior successes |
| GCL-023 | Recombination contact bridge focus20 | 20 targeted unseen | `recency_action_contact_bridge_pack` | 0 cached / 20 fresh | Outcome +0.2695, canonical +0.2857; contact helpers not routed/called in the focus cohort | Keep contact helpers as separate low-frequency pockets, not source of this lift |
| GCL-024 | Recombination best3 bridge focus20 | 20 targeted unseen | `recency_action_best3_bridge_pack` | 20 cached / 0 fresh | Outcome +0.3530, canonical +0.2672; natural calls across best3 time selector, recency window, timestamp selector, and composite bridge | Promising targeted run; expand before confirmation |
| GCL-025 | Recombination V2.6 bridge focus20 | 20 targeted unseen | `recency_action_v26_bridge_pack` | 20 cached / 0 fresh | Outcome +0.5452, canonical +0.2976; strongest focus result; composite bridge called 5/14 visible with called-subset outcome +0.6116 | Most promising targeted run; expand before confirmation |
| GCL-026 | Recombination V2.6 bridge expanded60 | 60 unseen | `recency_action_v26_bridge_pack` | 0 cached / 60 fresh | Outcome +0.0050, canonical -0.0429, exact success delta 0, zero runtime exceptions, protocol gate failed; helper call share below 25%; composite bridge VNC 2/2 | Do not confirm; retain pocket only |
| GCL-027 | Recombination best3 bridge expanded60 | 60 unseen | `recency_action_best3_bridge_pack` | 0 cached / 60 fresh | Outcome -0.0734, canonical -0.0031, exact success delta 0, zero runtime exceptions, protocol gate failed; latest Task Focus dashboard rendered paired data with 0 console errors | Do not confirm; stop broad recombination campaign |
| GCL-028 | Recombination adoption-minimal expanded60 | 60 unseen | `recency_action_adoption_minimal_pack` | 0 cached / 60 fresh; OpenAI cache off | Outcome +0.0480, canonical -0.0551, exact success -2, runtime exceptions 0; selector called 1/2 visible with canonical +0.1808 and outcome preserved | Retain selector signal; resolver not enough for scale |
| GCL-029 | Action-only contact/selector expanded60 | 60 unseen | `recency_action_contact_update_action_only_pack`, SHA `b07d81a9...` | 0 cached / 60 fresh; OpenAI cache off | Outcome -0.0052, canonical -0.0829, exact success -6, runtime exceptions 0; no experimental tools called | Diagnose no-call; force contact helper |
| GCL-030 | Force-after-search contact diagnostic | 20 targeted diagnostic | `recency_action_contact_update_action_only_pack` with forced `prepare_contact_update_from_recent_message` | 0 cached / 20 fresh; OpenAI cache off | Outcome -0.0406, canonical -0.0368, runtime exceptions 0; contact helper forced 6/6 with called-subset outcome -0.0937; selector naturally called 4 with called-subset outcome +0.2500 | Park contact helper; keep selector pocket |
| GCL-031 | Selector-only expanded60 adoption run | 60 unseen | `recency_action_selector_only_pack`, SHA `761444d6...` | 0 cached / 60 fresh; OpenAI cache off | Outcome +0.0045, canonical -0.0487, exact success -4, runtime exceptions 0; selector visible 2/called 2/VNC 0, called-subset outcome +0.2478 and canonical +0.1026 | Expanded60 positive adoption achieved; run confirm100 because low-frequency value may matter |
| GCL-032 | Selector-only confirm100 | 100 unseen | `recency_action_selector_only_pack`, SHA `761444d6...` | 0 cached / 100 fresh; OpenAI cache off | Outcome -0.1004, canonical -0.0483, exact success -4, runtime exceptions 0; selector visible 5/called 2/VNC 3, called-subset outcome 0.0 and canonical -0.3333; one helper side-effect preservation incident | Do not scale/promote; retain expanded60 as potential but park current form pending side-effect and routing repair |

## Required Family Status

| Family | Fair-chance evidence | Decision |
| --- | --- | --- |
| 1. Many small deterministic tools | Live-generated and frozen/refined packs tested at 20 and 60; ablations removed unsafe helpers. | No broad lift; keep small positive helpers for recombination. |
| 2. Tool chaining | Chain pack, force-after-search, output-shape repair, safety-accounting repair, and expanded rerun completed. | Latent recency value, but natural adoption too sparse for scale. |
| 3. Regular refinement loop | Underperforming/no-call tools went through route visibility, force diagnostics, repair, and rerun. | Refinement helped diagnosis but not broad outcome. |
| 4. Robust generation/validation/repair loop | `gpt-5-mini` generation plus static, schema, registry, synthetic, and live execution checks. | Strongest pilot source, but expanded safety/outcome blocked promotion. |
| 5. Diverse-task pain-point synthesis | Seed/dev analysis drove shared pain points: preconditions, recency selection, field extraction, insufficient-info. | Useful for tool design; downstream unseen results mixed. |
| 6. Larger generator / smaller executor | `gpt-5-mini` generator with `gpt-4o-mini` executor recorded in all generated runs. | Viable generation setup, not sufficient alone. |
| 7. Actor-policy and affordance | Rich metadata, guard metadata, trigger-focused descriptions, and ordering were tested. | Did not improve broad outcome; adoption remains a blocker. |
| 8. Router/composer | Trigger/family routing, negative-trigger suppression, focused packs, and contribution-aware pruning were tested. | Router prevented most unsafe overexposure but still produced VNC/no-call pockets. |
| 9. Safe insufficient-information detector | Guard/abstention pack and insufficient-info blocks in expanded60 tested. | Safe but outcome-negative; park broad guard. |
| 10. Final-answer-ready transformation tools | Output-shape repair for recency chain and service-answer extraction diagnostics tested. | Keep recency bridge; service extraction unresolved. |
| 11. Contrastive generation packets | Positive/negative packets from best3/V2.6/live/force diagnostics informed refined packs. | Helped identify what not to build; no scalable lift. |
| 12. Leave-family-out validation | Seed families excluded from unseen splits; recency/contact/reminder diagnostics held out across families. | Prevented near-duplicate claims; no confirm-positive result. |
| 13. Portfolio ablation/interactions | best3, best3+V2.6, live pack, minus unsafe, plus abstention, focused chain, repaired chain compared. | Interference and sparse adoption dominate; no additive scale candidate. |
| 14. Adaptive repair from failed calls | Missing updates, schema/output readiness, and side-effect accounting repairs completed. | Repairs clarified latent value but did not lift expanded outcome. |
| 15. Synthetic validation lab | Runtime and side-effect preservation tests added for repaired selection-only bridge. | Useful harness addition; not claim evidence. |
| 16. Bandit/exploration-aware routing | Fair-chance/priority injection and focused routing gave under-tested helpers exposure. | Exposure alone did not solve adoption or broad value. |
| 17. Description compression/richness | Minimal, affordance-rich, guard-rich, and chain-oriented metadata variants tested. | Rich metadata did not improve outcome; concise trigger metadata remains preferred. |
| 18. Oracle-free pain-point classifier | Trace/task-text pain categories used for routing and repair without unseen labels. | Useful diagnosis layer; no standalone scalable lift. |

## Stop Decision

Stop condition 2 remains met for the full branch campaign. The focused recombination continuation did achieve the requested expanded60 positive natural-adoption signal for `select_recency_target_and_prepare_action`, but confirm100 failed on broad outcome and safety, so no approach is currently promotion-ready. Minor positive tools are not discarded; the selector remains a design/refinement pocket, not scale evidence.
