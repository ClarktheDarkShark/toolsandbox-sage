# SAGE Gap-Closure Lab Candidate Triage

Experimental evidence only. Generated tools listed here are not part of protected final evidence unless separately validated and promoted through a reviewed claim process.

## Summary

No candidate is promotion-ready. The strongest retained signal is not a broad portfolio lift; it is a low-frequency recency/selection/action bridge that showed safe latent value in force and natural mechanism diagnostics but was not adopted reliably in expanded60. Per the campaign clarification, low-frequency positives are retained as recombination candidates instead of being fully discounted.

## Triage Table

| Candidate / method | Source | Registry path | Validation | Natural calls | Force diagnosis | Called-subset outcome | VNC | Safety | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `select_recency_target_and_prepare_action` | Chain repair from recency side-effect failures | `artifacts/registry_experiments/gap_closure_lab/focused_chain_repaired_pack` | Registry check pass; runtime/synthetic checks pass | 2-task safety diagnostic: visible 2, called 1; expanded60: visible 2, called 0 | Force-after-search +0.293 outcome on 2-task diagnostic | Natural safety diagnostic called subset +0.292; expanded no called subset | 1/2 in mechanism, 2/2 in expanded | 0 runtime, 0 side-effect after accounting repair | Keep/refine as recombination candidate; do not scale alone |
| `resolve_search_window_or_bounds` | Search-window/final-answer-ready helper | `focused_chain_repaired_pack` | Registry check pass | Expanded60: visible 4, called 2 | Not force-promoted | Called subset +0.341 outcome, +0.062 canonical | 2 | 0 incidents | Keep for recombination; low-frequency positive |
| `plan_contact_lookup_query` | Contact lookup scalar planner | `focused_chain_repaired_pack` | Registry check pass | Expanded60: visible 2, called 2 | Not force-promoted | Called subset outcome 0.0, canonical +0.25 | 0 | 0 incidents | Keep as harmless canonical helper, not primary gap closer |
| `plan_contact_search_from_scalar_constraint` | Scalar contact search planner | `focused_chain_repaired_pack` | Registry check pass | Earlier repaired run: visible 3, called 1; final expanded visible 3, called 0 | Not force-promoted | Prior called subset +0.102 outcome; final expanded unresolved | 3 | 0 incidents | Refine adoption/metadata; keep as potential pocket |
| `select_record_by_timestamp_extreme` | Narrow recency selector | `focused_chain_repaired_pack` | Registry check pass | Expanded60: visible 3, called 2 | Related old force diagnostic was canonical-positive but outcome-negative | Called subset -0.099 outcome, +0.070 canonical | 1 | 0 incidents | Park current form; may be superseded by composite bridge |
| `relative_day_time_to_timestamp` | Relative-time conversion helper | `focused_chain_repaired_pack` | Registry check pass | Expanded60: visible 2, called 2 | Not force-promoted | Called subset outcome 0.0, canonical -0.292 | 0 | 0 incidents | Park/refine; avoid broad routing |
| `extract_contact_field_from_search_result` | Field extraction helper | `focused_chain_repaired_pack` | Registry check pass | Expanded60: visible 2, called 0 | Not force-promoted | None | 2 | 0 incidents | Refine affordance or input bridge |
| `extract_service_answer_field` | Service answer extraction | `focused_chain_repaired_pack` and force diagnostics | Registry check pass | Expanded60: visible 1, called 0 | Force hook did not expose decisive value; outcome 0 | None | 1 | 0 incidents | Refine; unresolved diagnosis, not true negative |
| `next_service_tool_call` | State precondition helper | force diagnostic registry | Force-call ran | Forced only | Outcome -0.0105 | Negative | n/a | 0 incidents | Park as true-low-value current form |
| `next_dependency_precondition_call` | Dependency/precondition helper | force diagnostic registry | Force-call ran | Forced only | Outcome +0.0289 but side-effect incident 1 | Weak positive with safety failure | n/a | 1 incident | Park unsafe current form; redesign non-side-effect-only |
| `select_action_target_by_recency` | Earlier recency action selector | force diagnostic registry | Force-call ran | Forced only | Outcome -0.063, canonical +0.220 | Outcome negative | n/a | 0 incidents | Park current form; design lessons folded into repaired bridge |
| `detect_insufficient_visible_records` | Abstention/guard helper | `full_plus_abstention_pack` / `affordance_rich_guard_pack` | Registry/routing checks pass | Rich guard expanded60: visible 20, called 2 | Not force-promoted | Broad run outcome -0.071 | High VNC | 0 incidents | Park broad guard; insufficient-info lane still needs narrower design |
| `constraint_to_action_planner` | Live-generated planner | `live_generation_working` | Accepted in live generation | Accepted but uncalled in pilot | Not force-promoted | None | unresolved | 0 incidents | Refine only if paired with clearer input bridge |
| `prepare_side_effect_args_from_selected_record` | Side-effect kwargs preparer | `live_generation_working` | Accepted in live generation | Accepted but uncalled in pilot | Chain concept later tested via composite repair | None | unresolved | 0 incidents | Superseded by repaired composite bridge |

## Diagnosis Labels Used

- Hidden by routing: `extract_*` and scalar planners on nonmatching families; this was intentional negative-trigger suppression in most cases.
- Visible but not called: recency bridge and field extractors remain the main adoption gap.
- Called with bad arguments / schema mismatch: old recency chain erased selected target when updates were omitted; repaired.
- Output not final-answer-ready: old selector and service extractor often produced intermediate values only.
- Unsafe side-effect risk: dependency/precondition helper caused one incident; broad live pack caused two incidents before pruning.
- Overlap/interference with best3: full and refined packs produced canonical gains without primary outcome lift.
- True negative value: `next_service_tool_call` current form and broad abstention overlay.

## Promotion Guardrail

No tool is promoted from force-call success alone. The repaired recency bridge is the main potential tool to combine with other tools later, but it still needs natural adoption and expanded outcome improvement before any confirmation or formal validation.
