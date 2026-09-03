# SAGE Production Cleanup Execution - 2026-08-01

## Decision

**PASS.** The static checks, representative-subset gates, and final 1,032-task cleanup-equivalence gate all pass. The cleaned implementation preserves the protected SAGE result level while removing 19,419 non-dashboard production lines.

**Publication correction (2026-09-01):** This PASS is retained as a historical
engineering cleanup-equivalence decision, not as confirmatory paper evidence.
The baseline then labeled v140 was an expanded 1,182-record hybrid over 1,032
tasks: 75 tasks had three compatible records that were averaged. The online
self-evolution reflection controller also read those hybrid values. The
original v140 outcome sensitivity value (`0.4528026204750015`) would increase,
not decrease, the historical H2 relative-lift point estimate, so the hybrid did
not inflate that headline. It nevertheless invalidates the campaign as final
evidence because provenance, control replication, and online decisions were not
strictly fresh and one-to-one. Final inference is pending the strict
fresh-control ten-pair rerun.

## Scope and Protected Reference

The cleanup scope is production Python under `src/sage_ts`, excluding dashboard code. Tests, documentation, dashboards, and preserved run artifacts are not counted in the production-line target.

The historical engineering reference is the completed ten-replication Chapter 4 campaign in `artifacts/chapter4_evidence/chapter4_final_claim_10x_20260730`. Across 10,320 matched online-build tasks, the campaign reported hybrid-cache baseline outcome 0.4573, mean SAGE outcome 0.7954, and mean outcome lift 73.9 percent. Individual full-run SAGE outcomes ranged from approximately 0.776 to 0.810, with no runtime exceptions. These values define only the archived cleanup comparison range.

Cleanup validation historically used the same `gpt-4o-mini` actor, participant,
and generation model; the same fixed ToolSandbox clock; the expanded hybrid
task-level baseline cache; an empty SAGE registry; model-authored generation;
OpenAI response caching disabled; and synthetic bridge and scenario-name
behavior removed. This configuration comparison is not the corrected
publication protocol.

## Validation Strategy

1. Preserve source backups before each major reduction.
2. Run compile, undefined-name, unused-import, and focused unit/integration checks.
3. Run three independent 30-task cohorts from empty registries:
   - generated-tool coverage across varied task families;
   - native-action and side-effect preservation;
   - recency, selection, and answer behavior.
4. Compare each cohort with fixed pre-cleanup floors for SAGE score, SAGE outcome, and outcome delta. Do not change thresholds after seeing results.
5. Promote only passing increments. Start one full 1,032-task equivalence run only after all three representative cohorts pass.
6. Compare the full run with the ten protected full runs, including matched-prefix comparisons during execution and final run-level comparison at completion.

This design limits API cost while still exercising the major generated-tool families before a full benchmark is attempted.

## Production Reduction

| Production area | Before | After | Removed | Main removal |
|---|---:|---:|---:|---|
| ToolSandbox actor bridge | 21,220 | 12,690 | 8,530 | Unreachable synthetic bridge completions, dead policy builders, and unused actor-guidance variants |
| Model tool generator | 10,576 | 4,174 | 6,402 | Retired deterministic tool factory/template branch; retained model-authored generation and repair |
| Inadequacy classifier | 8,575 | 6,439 | 2,136 | Scenario-name planning/classification and functions made unreachable by its removal |
| Online tool birth | 3,293 | 2,048 | 1,245 | Disabled example synthesis and scenario-name proactive birth |
| Routing scorer | 648 | 82 | 566 | Scenario-name scoring; retained live routing contracts |
| ToolSandbox integration | 3,998 | 3,529 | 469 | Scenario/family compatibility routing and inactive visibility logic |
| SAGE run adapter | 1,400 | 1,329 | 71 | Scenario-name fallback and runtime-dead side-effect predicates |
| Obsolete safety diagnostic script | 336 | 0 | 336 | Sole remaining caller of removed scenario-name scoring |

Package total, excluding dashboard code: **65,615 to 46,196 lines**, a reduction of **19,419 lines (29.6 percent)**. Formatting and small supporting changes mean the package-level delta is the authoritative total rather than the sum of rounded component deltas.

## Behavior Retained

- visible-task and execution-trace gap detection;
- autonomous model-authored tool generation;
- static, schema, runtime, held-out, negative, and native-action validation;
- model-authored candidate repair;
- registry persistence, hashing, routing, and lifecycle feedback;
- natural generated-tool selection and calls;
- native ToolSandbox side-effect execution;
- generated-tool contribution and safety logging;
- historical hybrid-cached-control comparison with a fresh SAGE arm;
- Task Compare dashboard generation and live refresh.

## Representative Runtime Gate

Run root: `outputs/production_cleanup_20260801/post_legacy_only_fixed_20260801_190343`

| Cohort | Baseline score | SAGE score | Baseline outcome | SAGE outcome | Outcome delta | Accepted / called tools | Incidents | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Coverage 30 | 0.7525 | 0.9080 | 0.3374 | 0.8472 | +0.5098 | 19 / 17 | 0 | PASS |
| Action 30 | 0.6675 | 0.8758 | 0.3598 | 0.8500 | +0.4902 | 10 / 9 | 0 | PASS |
| Recency 30 | 0.8163 | 0.9277 | 0.1979 | 0.9681 | +0.7702 | 12 / 10 | 0 | PASS |

The machine-readable decision is in `artifacts/production_cleanup_20260801/post_legacy_only_gate.json`.

## Static and Test Results

- Production source compilation: PASS.
- Ruff undefined-name, unused-import, and unused-local checks: PASS.
- Final focused retained-path suite covering admission, normalization, complete-tool contracts, side-effect preservation, visible-signal birth, native-action repair, and actor routing: **135 passed**.
- Actor suite: **65 passed, 1 known pre-existing assertion failure** in `test_helper_answer_retention_policy_does_not_repeat_private_lookup`. The assertion expects different privacy-retention wording and was present before this cleanup increment.
- Static private-function audit: zero unreferenced private top-level production functions remain.

## Full Equivalence Gate

Run root: `outputs/production_cleanup_20260801/full_equivalence_20260801_192900/online_build_full_20260801_192922`

Dashboard: `http://127.0.0.1:63971/outputs/production_cleanup_20260801/full_equivalence_20260801_192900/online_build_full_20260801_192922/dashboard/task_compare.html`

Configuration:

- manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`;
- manifest SHA-256: `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`;
- sample: 1,032 tasks in standard order;
- models: `gpt-4o-mini` for actor, participant, and generation;
- controls: 1,032 rows synthesized from the expanded hybrid cache and 0 fresh;
- SAGE registry: empty at start;
- SAGE task cache: off;
- OpenAI response cache: disabled;
- generation and repair: enabled;
- synthetic bridge completions: disabled;
- scenario-name birth and routing: absent from production code.

Results:

| Metric | Baseline | Cleaned SAGE | Delta | Lift |
|---|---:|---:|---:|---:|
| Canonical/reference score | 0.7335 | 0.8022 | +0.0687 | +9.37% |
| Task-completion outcome | 0.4573 | 0.8073 | +0.3500 | +76.53% |

The protected ten-run campaign had mean SAGE score 0.7980 and mean SAGE outcome 0.7954. The cleaned run was +0.0043 above the protected score mean and +0.0119 above the protected outcome mean. Its score remained inside the protected full-run range of 0.7876 to 0.8066. Its outcome remained inside the protected range of 0.7761 to 0.8095 and ranked second among the cleaned run and the ten protected runs.

Tool and safety results:

- 29 tools were autonomously generated and accepted from an empty registry;
- 28 accepted tools were naturally called across 767 scenarios;
- called-tool rows contained 727 outcome gains and 75 outcome regressions;
- generated-tool runtime incidents: 0;
- side-effect preservation alerts: 2.

Both side-effect alerts were audited from their complete trajectories. They were contract-preservation near-misses for `plan_device_state_action_sequence_v3`, not harmful state mutations. In `cellular_off_all_tools`, the planner emitted a final redundant cellular-off action after cellular was already off; the task still achieved 1.0 outcome. In `find_distance_with_location_name_all_tools`, the planner proposed enabling location at the final turn, but no native state-changing action followed and no state changed. The alerts remain reported rather than being reclassified out of the evidence.

The machine-readable decision is in `artifacts/production_cleanup_20260801/full_equivalence_gate.json`.

## Release Conclusion

The cleanup increment is accepted as a historical engineering reduction. The
full benchmark result was at least equivalent to the archived engineering
range, tool generation and natural reuse remained active, and no runtime or
harmful side-effect incident was observed. This conclusion does not reinstate
the campaign as paper evidence. Further high-risk reduction should begin as a
separate increment and use the corrected strict fresh-control protocol.
