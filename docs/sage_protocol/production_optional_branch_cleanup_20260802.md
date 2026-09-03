# SAGE Optional-Branch Cleanup - 2026-08-02

## Decision

**PASS.** This cleanup removed another 2,651 non-dashboard production lines while preserving the active SAGE methodology and its established performance distribution. Dashboard source was not changed.

## Scope

The increment targeted optional or retired production branches that were not part of the final SAGE protocol. The protected behavior remained:

- visible-evidence gap detection;
- autonomous `gpt-4o-mini` tool generation and model-authored repair;
- source, schema, runtime, held-out, negative, and native-action validation;
- registry persistence, routing, reuse, reflection, and contribution logging;
- natural generated-tool calls with no SAGE-only extra actor turns;
- native ToolSandbox actions for state changes;
- strict cached controls and a fresh SAGE arm;
- Task Compare and all other dashboard code.

## Removed Production Paths

The cleanup removed inactive actor-policy variants, independent generated-call batching, used-schema and dynamic-schema feature toggles, retired generated-tool payload branches, optional direct-status and deferred-native routing, runtime diagnostic force-call paths, old tool-usage note builders, generator matrix modes, generation and repair prompt caches, candidate-grading bypasses, optional birth/repair modes, zero-score retirement, reflection auto-stop branches, the generic OpenAI response-cache package, the retired live-candidate validator, v2 experiment flags, and obsolete run scripts.

Compatibility reads retained solely for analyzing completed historical artifacts are not executable task-solving routes. Control-task caching, run resume/checkpoint support, model timeout/retry settings, and dashboard load controls remain because they are current operational requirements rather than experimental treatment branches.

## Size Reduction

| Measure | Before | After | Change |
|---|---:|---:|---:|
| Non-dashboard `src/sage_ts` Python lines | 46,196 | 43,545 | -2,651 (-5.74%) |
| Non-dashboard Python files | 59 | 53 | -6 |
| Dashboard Python lines | 7,973 | 7,973 | unchanged |

The source diff contains 115 additions and 2,766 deletions. The pre-cleanup checkpoint is `artifacts/production_cleanup_20260802/checkpoints/pre_optional_branch_cleanup_src.tar.gz` with SHA-256 `321246b7a3eca9034546c8f3ca1a4da6c6abbac96613924ed43468e9fc821b91`.

## Deterministic Behavior Lock

The complete 1,032-task classifier surface was regenerated before and after cleanup. All 1,810 parsed observations matched exactly. All 1,810 generation prompts also matched exactly, with aggregate SHA-256 `a9e67f03f58c37838d36af7d35c660999bd09459f11afe24e984cb46315e6534`. All 1,810 repair prompts matched exactly, with aggregate SHA-256 `1604bcebc4c4037ffd00b0383889a54b0c2f5ff0851eaa7da1de9f8d1f02eb5d`.

This is stronger than a score-only comparison: the cleanup did not alter what gaps SAGE detects or what it sends to the model for tool generation and repair.

## Automated Validation

- `compileall`: PASS.
- Ruff undefined-name, unused-import, and unused-local checks: PASS.
- Unit suite: 429 passed.
- Generation group: 126 passed.
- Runtime group: 111 passed.
- Orchestration group: 41 passed.
- Evidence group: 87 passed.
- `git diff --check`: PASS.

The first cohort launch stopped before any LLM task work because the protected baseline cache required an explicit minimum-compatible-run value. The unchanged code was relaunched with the established `SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS=1` policy. The captured diagnostic is `artifacts/production_cleanup_20260802/optional_cleanup_validation_first_attempt_errors_20260802.log`.

## Representative Cohorts

Each cohort used an empty registry, fresh SAGE execution, strict cached controls, and `gpt-4o-mini` for actor, participant, and generation.

| Cohort | Baseline score | SAGE score | Baseline outcome | SAGE outcome | Outcome delta | Gate |
|---|---:|---:|---:|---:|---:|---|
| Generated-tool coverage 30 | 0.7525 | 0.8815 | 0.3374 | 0.9566 | +0.6191 | PASS |
| Native action / side effect 30 | 0.6675 | 0.9058 | 0.3598 | 0.8150 | +0.4552 | PASS |
| Recency / answer extraction 30 | 0.8163 | 0.8714 | 0.1979 | 0.8400 | +0.6421 | PASS |

All three exceeded their fixed pre-cleanup score, outcome, and outcome-delta floors. All protocol gates passed and all cohorts had zero runtime exceptions.

## Full-Dataset Validation

Run root: `outputs/production_cleanup_20260802/full_optional_cleanup_equivalence_20260802_172055/online_build_full_20260802_172101`

Dashboard: `http://127.0.0.1:63975/outputs/production_cleanup_20260802/full_optional_cleanup_equivalence_20260802_172055/online_build_full_20260802_172101/dashboard/task_compare.html`

The run used the formal 1,032-task manifest in standard order, 1,032 strict cached controls, an empty starting registry, fresh SAGE execution, and `gpt-4o-mini` for every LLM role. Model-authored generation and repair were enabled. Scenario-name birth/routing, synthetic bridge completions, diagnostic force calls, and OpenAI response caching were disabled or absent.

| Metric | Baseline | Cleaned SAGE | Delta | Lift |
|---|---:|---:|---:|---:|
| Canonical/reference score | 0.7335 | 0.7986 | +0.0651 | +8.88% |
| Task-completion outcome | 0.4573 | 0.7900 | +0.3326 | +72.73% |

The full run accepted 30 tools from an empty registry. Twenty-nine were naturally called across 768 scenarios, producing 1,878 reuse events. The run completed all 1,032 tasks with zero runtime exceptions.

## No-Degradation Assessment

The protected ten-run online-build campaign has mean score 0.797953 (SD 0.005408; range 0.787598-0.806645) and mean outcome 0.795407 (SD 0.011327; range 0.776052-0.809509). The cleaned run's score was 0.000668 above that mean. Its outcome was 0.005437 below the mean, or 0.48 standard deviations, and remained well inside the observed range.

The immediately preceding cleanup run was unusually strong at 0.807327 outcome. The new result is lower than that single run but is not evidence of systematic degradation: deterministic classifier/generation/repair inputs are exact, every fixed cohort passed, and both full-run metrics fall inside the protected replication distribution. The correct release claim is distributional equivalence, not identical reproduction of a stochastic outlier.

## Runtime And Safety Audit

The dashboard counted 44 generated-tool failed-selection scenarios: 42 for `apply_single_device_state_action` and two for `extract_distance_result`. This count is consistent with prior production replications, including two protected runs with 44 such scenarios. Most are applicability abstentions where another route completed the task; among the 42 rows with outcome measures, mean outcome was 0.8429 and 27 achieved exact outcome.

One side-effect-preservation alert was recorded for `plan_device_state_action_sequence_v3`. Cellular service was enabled successfully, a redundant follow-up generated action received an already-enabled error, and the requested message was then sent. The terminal state was correct, task outcome was 0.9091, and no harmful mutation occurred. The alert remains visible as a contract-preservation near-miss.

## Release Boundary

This increment is accepted as the next production checkpoint. Further reductions in the large actor bridge, classifier, generator, or ToolSandbox integration would cross into medium/high-risk restructuring and must begin from this checkpoint with the same deterministic locks, three parallel cohorts, and distributional full-run gate.

Machine-readable gate: `artifacts/production_cleanup_20260802/optional_branch_cleanup_gate.json`.
