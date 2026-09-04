# Final-Task Success Audit

> **SUPERSEDED — ARCHIVAL ONLY.** This audit predates the route-independent
> all-task outcome evaluator. Its metric descriptions are not current
> publication policy. See [current_state.md](current_state.md).

## 1) What does canonical ToolSandbox score measure?
Canonical score (`canonical_score.json`) is route- and benchmark-task milestone score at task level. It summarizes base-task similarity/success behavior from task result summaries (not final answer quality), and is compared between control and candidate runs.

## 2) What does final-task success measure?
Final-task success (`final_task_success_score.json`) is `outcome_similarity` aggregated across tasks from `compute_outcome_score(...)` and corresponds to final response quality. It is separate from canonical milestone score.

## 3) Does final-task scoring use only the final assistant answer?
Yes after the fix. `_agent_messages()` now returns only the last AGENT→USER message (all prior intermediate assistant messages are discarded before final scoring).

## 4) Can final-task scoring over-credit intermediate messages?
It could previously over-credit, but no now.
- Test coverage added: `test_outcome_score_only_uses_final_agent_to_user_message`.
- Result: intermediate-only scoring cannot affect final `outcome_similarity`; only final assistant-to-user message is used.

## 5) Can final ToolSandbox state be scored for side-effect tasks?
There is no separate scalar “final side-effect score” metric yet, but the reporting spine carries final-state summaries in:
- `side_effect_preservation_report.jsonl` (current phase smoke output exists, empty in this tiny smoke because no side-effect-sensitive scenarios were selected),
- `adjudication_packet.jsonl` entries with `control_final_state` / `candidate_final_state`.

## 6) Is route mismatch separated from wrong final result?
Yes. Route mismatch is reported in `route_mismatch_report.json`, while wrong final outcomes are in final-task/canonical outcomes and adjudication labels. This separation is available in the same phase-A reporting pack.

## 7) Is exact success separate from mean similarity?
Yes. Exact outcomes and averages are separated:
- `exact_success.json` (`control_exact_success`, `candidate_exact_success`, `exact_success_delta`)
- `canonical_score.json` (`mean_similarity` etc.)

## 8) Can helper-caused regressions be separated from stochastic/non-helper regressions?
Partially. Current reporting separates gains/regressions and includes per-task tool trace visibility in `adjudication_packet.jsonl`; this supports manual/seeded separation, but does not yet guarantee fully automated causality classification.
