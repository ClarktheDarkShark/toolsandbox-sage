# SAGE Production Release Cleanup Plan

> **SUPERSEDED — ARCHIVAL CLEANUP LEDGER.** This file preserves earlier cleanup
> decisions and validation observations. Its commands, source inventory, metric
> values, and release gates are not current policy. See
> [current_state.md](current_state.md).

Status: preparation plan for sensitive cleanup after removal of unfair retry,
scenario-name routing, diagnostic force paths, and obsolete bridge-policy docs.

## Release Boundary

Production SAGE is the v061 evidence-line framework:

- autonomous generated-tool birth from visible task context;
- generated-tool validation and repair;
- registry storage with validation proof and hashes;
- visible-context routing and bounded generated-tool exposure;
- natural generated-tool use during the ordinary task turn;
- lifecycle feedback from scored outcomes;
- contribution and safety accounting.

Production SAGE excludes:

- synthetic completion paths;
- route-around behavior from benchmark code knowledge;
- hidden scenario-name birth/routing;
- diagnostic force calls;
- SAGE-only task retries or extra turns;
- answer-label or expected-answer leakage.

## Cleanup Validation Log

### 2026-06-19 - Dead Actor Helpers Removed

Removed private actor-side helpers that had no repository callers after the
current generated-tool flow was stabilized. This was a behavior-neutral cleanup:
it did not alter generated-tool birth, validation, routing, registry storage,
tool choice, lifecycle reflection, or result scoring.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/adapters/openai_toolsandbox_roles.py src/sage_ts/generation/tool_generator.py src/sage_ts/orchestration/online_birth.py src/sage_ts/runtime/toolsandbox_integration.py src/sage_ts/evaluation/task_strata.py`
- `PYTHONPATH=src:. pytest tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_online_birth.py tests/unit/test_tool_generator.py tests/unit/test_task_strata.py tests/unit/test_openai_toolsandbox_roles.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_dead_actor_cleanup_coverage30_p1/mechanism_40_20260619_123101`
  - score: `0.687970 -> 0.938808`, delta `+0.250837`
  - outcome: `0.465680 -> 0.880342`, delta `+0.414662`
  - runtime incidents: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_dead_actor_cleanup_action30_p1/mechanism_40_20260619_123101`
  - score: `0.711811 -> 0.910795`, delta `+0.198984`
  - outcome: `0.453970 -> 0.789407`, delta `+0.335437`
  - runtime incidents: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_dead_actor_cleanup_recency30_p1/mechanism_40_20260619_123101`
  - score: `0.619431 -> 0.907611`, delta `+0.288180`
  - outcome: `0.267642 -> 0.820000`, delta `+0.552358`
  - runtime incidents: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`

Decision: keep this cleanup.

### 2026-06-19 - Excess Blank-Line Normalization

Normalized excessive blank-line runs in large production modules after prior
code removals. This was formatting-only and did not alter executable logic.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/adapters/openai_toolsandbox_roles.py src/sage_ts/generation/tool_generator.py src/sage_ts/orchestration/online_birth.py src/sage_ts/runtime/toolsandbox_integration.py src/sage_ts/evaluation/task_strata.py src/sage_ts/adequacy/inadequacy_classifier.py`
- `PYTHONPATH=src:. pytest tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_online_birth.py tests/unit/test_tool_generator.py tests/unit/test_task_strata.py tests/unit/test_openai_toolsandbox_roles.py -q`
- `git diff --check`

Line count after this pass: `32,744` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - OpenAI Response Cache Retired To Compatibility Shim

Retired the active OpenAI response-cache implementation from production SAGE.
The final evidence path already runs with OpenAI response caching disabled, so
the SQLite cache and OpenAI monkeypatch layer were outside the release boundary.
The module now keeps a small compatibility surface for runner imports, context
metadata, and cache-key tests, but it no longer reads from or writes to an
OpenAI response cache.

This does not alter generated-tool birth, validation, registry storage,
visible-context routing, actor tool use, lifecycle reflection, or scoring.

Checks:

- `python -m py_compile src/sage_ts/cache/openai_response_cache.py scripts/run_sage_protocol.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_response_cache.py -q`
- `PYTHONPATH=src:. pytest tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_online_birth.py tests/unit/test_tool_generator.py tests/unit/test_task_strata.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_openai_response_cache.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_response_cache_retire_coverage30_p1/mechanism_40_20260619_124350`
  - score: `0.687970 -> 0.908027`, delta `+0.220057`
  - outcome: `0.465680 -> 0.843537`, delta `+0.377857`
  - runtime incidents: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_response_cache_retire_action30_p1/mechanism_40_20260619_124350`
  - score: `0.711811 -> 0.899915`, delta `+0.188104`
  - outcome: `0.453970 -> 0.846860`, delta `+0.392889`
  - runtime incidents: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_response_cache_retire_recency30_p1/mechanism_40_20260619_124350`
  - score: `0.619431 -> 0.908214`, delta `+0.288783`
  - outcome: `0.267642 -> 0.817712`, delta `+0.550070`
  - runtime incidents: `0`; side-effect incidents: `1`; failed generated-tool attempts: `0`

The recency side-effect incident count matches the original validation anchor
for this slice and did not increase.

Line count after this pass: `32,523` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Small Dead-Code Pass

Removed private definitions with no source, script, or test references:

- unused actor text/location helper definitions in
  `src/sage_ts/adapters/openai_toolsandbox_roles.py`;
- unused `GeneratedToolRepairFactory` protocol alias in
  `src/sage_ts/orchestration/online_birth.py`.

These definitions were unreachable and did not participate in generated-tool
birth, validation, routing, registry storage, actor tool choice, lifecycle
feedback, or scoring.

Checks:

- `python -m py_compile src/sage_ts/adapters/openai_toolsandbox_roles.py src/sage_ts/orchestration/online_birth.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_online_birth.py -q`
- `git diff --check`

Line count after this pass: `32,423` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Retired Default-Off Experiment Branches

Removed production code paths for retired experiment flags that were not part of
the validated SAGE evidence line:

- dependency-logic prompt variant;
- grading-accounting prompt and gate variant;
- medium-grain experiment prompt variant;
- optional live-validation call inside online birth.

The retained production feature flags are `contract_synthesis` and
`candidate_repair`. The runner preset now reports only those two active
production features in `SAGE_V2_EXPERIMENT_FEATURES`.

This preserves the current methodology boundary: SAGE still uses visible task
context, autonomous generated-tool birth, validation/repair, registry storage,
visible-context routing, actor tool use, lifecycle feedback, and contribution
accounting. It does not reintroduce scenario-name birth/routing, synthetic
bridge completions, force calls, or unfair retries.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/experiments/v2_flags.py src/sage_ts/adequacy/candidate_gate.py src/sage_ts/generation/tool_generator.py src/sage_ts/orchestration/online_birth.py`
- `PYTHONPATH=src:. pytest tests/unit/test_v2_flags.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_candidate_gate.py tests/unit/test_live_candidate_check.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_retired_experiment_cleanup_coverage30_p1/mechanism_40_20260619_125948`
  - score: `0.687970 -> 0.873029`, delta `+0.185059`
  - outcome: `0.465680 -> 0.884318`, delta `+0.418638`
  - accepted tools: `21`; generated-tool-called scenarios: `29`; reuse: `47`
  - generated-tool failed scenarios: `0`; runtime exceptions: `0`
  - side-effect incidents: `0`; runtime incidents: `0`
  - dashboard: `http://127.0.0.1:62670/outputs/production_cleanup_validation/post_retired_experiment_cleanup_coverage30_p1/mechanism_40_20260619_125948/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_retired_experiment_cleanup_action30_p1/mechanism_40_20260619_125948`
  - score: `0.711811 -> 0.885131`, delta `+0.173319`
  - outcome: `0.453970 -> 0.817960`, delta `+0.363989`
  - accepted tools: `15`; generated-tool-called scenarios: `29`; reuse: `54`
  - generated-tool failed scenarios: `0`; runtime exceptions: `0`
  - side-effect incidents: `0`; runtime incidents: `0`
  - dashboard: `http://127.0.0.1:62671/outputs/production_cleanup_validation/post_retired_experiment_cleanup_action30_p1/mechanism_40_20260619_125948/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_retired_experiment_cleanup_recency30_p1/mechanism_40_20260619_125948`
  - score: `0.619431 -> 0.897833`, delta `+0.278402`
  - outcome: `0.267642 -> 0.840000`, delta `+0.572358`
  - accepted tools: `12`; generated-tool-called scenarios: `29`; reuse: `44`
  - generated-tool failed scenarios: `0`; runtime exceptions: `0`
  - side-effect incidents: `1`; runtime incidents: `0`
  - dashboard: `http://127.0.0.1:62672/outputs/production_cleanup_validation/post_retired_experiment_cleanup_recency30_p1/mechanism_40_20260619_125948/dashboard/task_compare.html`

The recency side-effect incident count matches the original validation anchor
for this slice and did not increase.

Line count after this pass: `32,278` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Actor Token-Reduction Branch Cleanup

Removed retired actor-side token-reduction experiment branches that were not
active in the validated SAGE evidence line:

- dynamic generated-tool schema pruning;
- drop-used generated-tool schemas;
- lean generated-tool handoff mode;
- independent generated-tool batch calls.

The validated production actor flow now presents the current generated-tool
bundle without these inactive branch points. This did not change generated-tool
birth, validation, registry storage, visible-context routing, lifecycle
reflection, or scoring.

Checks:

- `python -m py_compile src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/integration/test_toolsandbox_generated_tool_injection.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_actor_token_branch_cleanup_coverage30_20260619_143313/mechanism_40_20260619_143317`
  - score: `0.687970 -> 0.909024`, delta `+0.221054`
  - outcome: `0.465680 -> 0.838755`, delta `+0.373075`
  - accepted tools: `21`; generated-tool-called scenarios: `29`; reuse: `48`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_actor_token_branch_cleanup_action30_20260619_143313/mechanism_40_20260619_143317`
  - score: `0.711811 -> 0.843649`, delta `+0.131838`
  - outcome: `0.453970 -> 0.710405`, delta `+0.256435`
  - accepted tools: `15`; generated-tool-called scenarios: `29`; reuse: `53`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Action rerun:
  `outputs/production_cleanup_validation/post_actor_token_branch_cleanup_action30_rerun_20260619_144038/mechanism_40_20260619_144042`
  - score: `0.711811 -> 0.870284`, delta `+0.158472`
  - outcome: `0.453970 -> 0.709542`, delta `+0.255572`
  - accepted tools: `15`; generated-tool-called scenarios: `29`; reuse: `56`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_actor_token_branch_cleanup_recency30_20260619_143313/mechanism_40_20260619_143317`
  - score: `0.619431 -> 0.901250`, delta `+0.281819`
  - outcome: `0.267642 -> 0.880000`, delta `+0.612358`
  - accepted tools: `12`; generated-tool-called scenarios: `29`; reuse: `44`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`

Decision: keep this cleanup.

### 2026-06-19 - Visible-Context Classifier Dispatcher Refactor

Replaced the long visible-observation dispatcher chain in
`src/sage_ts/adequacy/inadequacy_classifier.py` with an ordered rule table.
The refactor preserved the same visible-signal predicates and observation
builders while making the dispatcher smaller and easier to audit.

Behavior lock:

- source manifest:
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- before snapshot:
  `artifacts/production_cleanup_validation/classifier_snapshot_before_phase3.json`
- after snapshot:
  `artifacts/production_cleanup_validation/classifier_snapshot_after_phase3_dispatcher.json`
- scenario count: `1032`
- observation count: `1607`
- SHA-256 before/after:
  `f60496aa8fec6844127916dee68b5c05173330dc98f178023eb61d08dcea6790`

Checks:

- `python -m py_compile src/sage_ts/adequacy/inadequacy_classifier.py`
- `PYTHONPATH=src:. pytest tests/unit/test_online_birth.py tests/unit/test_task_strata.py -q`
- `git diff --check`

Decision: keep this cleanup.

### 2026-06-19 - Evaluation Package Moved Out Of Production Core

Moved run comparison, baseline-cache, task-strata, outcome-score, helper
contribution, and LLM-usage reporting modules from `src/sage_ts/evaluation/`
to `src/sage_research/evaluation/`. These modules remain available to the
protocol runner, dashboards, and reports, but they are not part of the SAGE
production execution package.

This was an import-boundary move. It did not alter generated-tool birth,
validation, registry storage, visible-context routing, actor tool choice,
lifecycle feedback, or scoring logic.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_research/toolsandbox/openai_roles.py src/sage_research/toolsandbox/adapter.py src/sage_research/toolsandbox/sage_run_adapter.py src/sage_ts/orchestration/self_evolution_reflection.py src/sage_research/evaluation/*.py`
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py tests/unit/test_run_metrics.py tests/unit/test_helper_contribution.py tests/unit/test_outcome_score.py tests/unit/test_task_strata.py tests/unit/test_self_evolution_reflection.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_eval_package_move_coverage30_20260619_145703/mechanism_40_20260619_145707`
  - score: `0.687970 -> 0.922055`, delta `+0.234085`
  - outcome: `0.465680 -> 0.833464`, delta `+0.367784`
  - accepted tools: `21`; generated-tool-called scenarios: `29`; reuse: `47`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_eval_package_move_action30_20260619_145703/mechanism_40_20260619_145707`
  - score: `0.711811 -> 0.880578`, delta `+0.168767`
  - outcome: `0.453970 -> 0.751426`, delta `+0.297455`
  - accepted tools: `15`; generated-tool-called scenarios: `29`; reuse: `50`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_eval_package_move_recency30_20260619_145703/mechanism_40_20260619_145707`
  - score: `0.619431 -> 0.901897`, delta `+0.282466`
  - outcome: `0.267642 -> 0.840000`, delta `+0.572358`
  - accepted tools: `12`; generated-tool-called scenarios: `29`; reuse: `42`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`

Line count after this pass: `28,370` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Campaign And Retired Cache Support Moved Out Of Production Core

Moved campaign artifact helpers and the retired OpenAI response-cache
compatibility shim from `src/sage_ts/` into `src/sage_research/`. These modules
support the runner, artifact ledger, dashboards, and compatibility tests. They
are not part of SAGE's generated-tool lifecycle.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py scripts/campaign_artifacts.py src/sage_ts/dashboard/exporters.py src/sage_research/campaign/artifacts.py`
- `PYTHONPATH=src:. pytest tests/unit/test_campaign_artifacts.py -q`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_research/cache/openai_response_cache.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_response_cache.py -q`
- `git diff --check`

Line count after this pass: `27,900` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Dead Actor Constants And Retired Zero-Score Suppression Removed

Removed actor policy sentinel constants and compatibility constants that had no
runtime references after prior bridge/branch cleanup. Also removed an
always-false timestamp compatibility helper and simplified the two call sites
that used it.

Removed a default-off `SAGE_SELF_EVOLVING_SUPPRESS_ZERO_SCORE_TOOLS` branch from
`src/sage_ts/adapters/sage_run_adapter.py`. This branch retired generated tools
immediately after a zero-score task when explicitly enabled. It was not part of
the current SAGE methodology or validation settings. The retained lifecycle
mechanism is the scored self-evolution reflection controller.

Checks:

- `python -m py_compile src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/integration/test_toolsandbox_generated_tool_injection.py -q`
- `python -m py_compile src/sage_ts/adapters/sage_run_adapter.py`
- `PYTHONPATH=src:. pytest tests/unit/test_sage_run_adapter.py tests/unit/test_self_evolution_reflection.py -q`
- `python -m py_compile src/sage_research/campaign/artifacts.py`
- `PYTHONPATH=src:. pytest tests/unit/test_campaign_artifacts.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_coverage30_20260619_151056/mechanism_40_20260619_151100`
  - score: `0.687970 -> 0.925567`, delta `+0.237597`
  - outcome: `0.465680 -> 0.866054`, delta `+0.400374`
  - accepted tools: `21`; generated-tool-called scenarios: `29`; reuse: `48`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62687/outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_coverage30_20260619_151056/mechanism_40_20260619_151100/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_action30_20260619_151056/mechanism_40_20260619_151100`
  - score: `0.711811 -> 0.885384`, delta `+0.173573`
  - outcome: `0.453970 -> 0.733565`, delta `+0.279594`
  - accepted tools: `15`; generated-tool-called scenarios: `29`; reuse: `55`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62688/outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_action30_20260619_151056/mechanism_40_20260619_151100/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_recency30_20260619_151056/mechanism_40_20260619_151100`
  - score: `0.619431 -> 0.898635`, delta `+0.279204`
  - outcome: `0.267642 -> 0.830679`, delta `+0.563037`
  - accepted tools: `12`; generated-tool-called scenarios: `29`; reuse: `47`
  - runtime exceptions: `0`; side-effect incidents: `1`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62689/outputs/production_cleanup_validation/post_support_and_dead_branch_cleanup_recency30_20260619_151056/mechanism_40_20260619_151100/dashboard/task_compare.html`

The recency side-effect incident count matches the original validation anchor
for this slice and did not increase.

Line count after this pass: `27,815` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Scenario-Name Priming And Retired Experiment Flags Removed

Removed a no-op scenario-name priming path from online birth and collapsed
retired experiment switches into the current production behavior. The removed
scenario-name priming path did not create production tools in the current
configuration, but it was confusing because final SAGE evidence must not depend
on scenario names for tool birth or routing.

Also removed retired/default-off feature switches and locked in the production
behavior already used by the current SAGE evidence line:

- visible-context safe-abstain tool birth;
- direct-status lookup visibility when justified by visible task/tool context;
- JIT visible-context online birth;
- contract synthesis guidance;
- candidate repair after validation failure.

This cleanup does not add benchmark-specific knowledge, hidden labels, synthetic
bridge completions, force calls, or SAGE-only retry advantages.

Checks:

- `python -m py_compile src/sage_ts/adapters/sage_run_adapter.py src/sage_ts/orchestration/online_birth.py`
- `PYTHONPATH=src:. pytest tests/unit/test_online_birth.py tests/unit/test_sage_run_adapter.py -q`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/generation/tool_generator.py src/sage_ts/orchestration/online_birth.py src/sage_ts/adequacy/candidate_gate.py src/sage_ts/validation/live_candidate_check.py`
- `PYTHONPATH=src:. pytest tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_candidate_gate.py tests/unit/test_live_candidate_check.py tests/unit/test_protocol_generation_policy.py -q`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/adequacy/inadequacy_classifier.py src/sage_ts/runtime/toolsandbox_integration.py src/sage_ts/orchestration/online_birth.py`
- `PYTHONPATH=src:. pytest tests/unit/test_protocol_generation_policy.py tests/unit/test_online_birth.py tests/unit/test_tool_generator.py tests/integration/test_toolsandbox_generated_tool_injection.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_flag_simplification_coverage30_20260619_153018/mechanism_40_20260619_153022`
  - score: `0.687970 -> 0.881704`, delta `+0.193734`
  - outcome: `0.465680 -> 0.835835`, delta `+0.370156`
  - accepted tools: `21`; generated-tool-called scenarios: `30`; reuse: `47`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62690/outputs/production_cleanup_validation/post_flag_simplification_coverage30_20260619_153018/mechanism_40_20260619_153022/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_flag_simplification_action30_20260619_153018/mechanism_40_20260619_153022`
  - score: `0.711811 -> 0.879061`, delta `+0.167250`
  - outcome: `0.453970 -> 0.791477`, delta `+0.337507`
  - accepted tools: `15`; generated-tool-called scenarios: `30`; reuse: `56`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62691/outputs/production_cleanup_validation/post_flag_simplification_action30_20260619_153018/mechanism_40_20260619_153022/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_flag_simplification_recency30_20260619_153018/mechanism_40_20260619_153022`
  - score: `0.619431 -> 0.877295`, delta `+0.257864`
  - outcome: `0.267642 -> 0.830679`, delta `+0.563037`
  - accepted tools: `12`; generated-tool-called scenarios: `30`; reuse: `45`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62692/outputs/production_cleanup_validation/post_flag_simplification_recency30_20260619_153018/mechanism_40_20260619_153022/dashboard/task_compare.html`

Line count after this pass: `27,696` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Actor Choice Toggles And Generator Dispatch Refactored

Removed retired actor-side environment toggles for generated-tool first-attempt
choice, generated-tool continuation choice, and ephemeral actor-policy pruning.
The current production behavior always evaluates generated-tool first-attempt
and continuation choices; the removed switches were branch points around that
validated behavior.

Refactored deterministic tool-generation and repair selection into explicit
dispatch tables. This preserved the existing contract builders and repair
builders while making the generator easier to audit.

Checks:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_protocol_generation_policy.py -q`
- `python -m py_compile src/sage_ts/generation/tool_generator.py src/sage_ts/orchestration/online_birth.py`
- `PYTHONPATH=src:. pytest tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_coverage30_20260619_153948/mechanism_40_20260619_153952`
  - score: `0.687970 -> 0.915562`, delta `+0.227591`
  - outcome: `0.465680 -> 0.825424`, delta `+0.359744`
  - accepted tools: `21`; generated-tool-called scenarios: `30`; reuse: `49`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62693/outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_coverage30_20260619_153948/mechanism_40_20260619_153952/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_action30_20260619_153948/mechanism_40_20260619_153952`
  - score: `0.711811 -> 0.839754`, delta `+0.127942`
  - outcome: `0.453970 -> 0.728919`, delta `+0.274949`
  - accepted tools: `15`; generated-tool-called scenarios: `30`; reuse: `57`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62694/outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_action30_20260619_153948/mechanism_40_20260619_153952/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_recency30_20260619_153948/mechanism_40_20260619_153952`
  - score: `0.619431 -> 0.909480`, delta `+0.290049`
  - outcome: `0.267642 -> 0.880000`, delta `+0.612358`
  - accepted tools: `12`; generated-tool-called scenarios: `30`; reuse: `44`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62695/outputs/production_cleanup_validation/post_actor_choice_and_generator_dispatch_recency30_20260619_153948/mechanism_40_20260619_153952/dashboard/task_compare.html`

Line count after this pass: `27,625` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - Research Support Boundary Cleanup

Moved release/research support utilities out of the production `sage_ts`
package:

- promotion-gate evidence checks moved to `sage_research.registry`;
- split-manifest utilities moved to `sage_research.config`;
- two unused production local variables were removed from lifecycle reflection
  and ToolSandbox integration.

These changes do not alter generated-tool birth, validation/repair, registry
storage, visible-context routing, actor tool choice, lifecycle feedback, or
scoring. The promotion gate remains available for post-run evidence review, but
it is not part of the runtime generated-tool path.

Checks:

- `python -m py_compile scripts/check_promotion_gate.py src/sage_research/registry/promotion_gate.py src/sage_ts/registry/manifest.py src/sage_ts/registry/store.py`
- `PYTHONPATH=src:. pytest tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py -q`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_research/config/splits.py`
- `PYTHONPATH=src:. pytest tests/unit/test_splits.py tests/unit/test_protocol_generation_policy.py -q`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/orchestration/self_evolution_reflection.py src/sage_ts/runtime/toolsandbox_integration.py src/sage_research/registry/promotion_gate.py src/sage_research/config/splits.py`
- `PYTHONPATH=src:. pytest tests/unit/test_self_evolution_reflection.py tests/unit/test_splits.py tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py tests/integration/test_toolsandbox_generated_tool_injection.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_support_boundary_cleanup_coverage30_20260619_155221/mechanism_40_20260619_155225`
  - score: `0.687970 -> 0.888848`, delta `+0.200878`
  - outcome: `0.465680 -> 0.852133`, delta `+0.386454`
  - accepted tools: `21`; generated-tool-called scenarios: `30`; reuse: `47`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62696/outputs/production_cleanup_validation/post_support_boundary_cleanup_coverage30_20260619_155221/mechanism_40_20260619_155225/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_support_boundary_cleanup_action30_20260619_155221/mechanism_40_20260619_155225`
  - score: `0.711811 -> 0.862205`, delta `+0.150394`
  - outcome: `0.453970 -> 0.760838`, delta `+0.306868`
  - accepted tools: `15`; generated-tool-called scenarios: `30`; reuse: `50`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62697/outputs/production_cleanup_validation/post_support_boundary_cleanup_action30_20260619_155221/mechanism_40_20260619_155225/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_support_boundary_cleanup_recency30_20260619_155221/mechanism_40_20260619_155225`
  - score: `0.619431 -> 0.908646`, delta `+0.289215`
  - outcome: `0.267642 -> 0.900000`, delta `+0.632358`
  - accepted tools: `12`; generated-tool-called scenarios: `30`; reuse: `43`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62698/outputs/production_cleanup_validation/post_support_boundary_cleanup_recency30_20260619_155221/mechanism_40_20260619_155225/dashboard/task_compare.html`

Line count after this pass: `27,360` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

### 2026-06-19 - ToolSandbox Adapter Moved Out Of Reusable SAGE Core

Moved the ToolSandbox/OpenAI research adapter layer from `src/sage_ts/` to
`src/sage_research/toolsandbox/`:

- OpenAI ToolSandbox actor/user roles;
- ToolSandbox role factory;
- baseline ToolSandbox runner adapter;
- SAGE ToolSandbox run adapter;
- ToolSandbox generated-tool injection/integration adapter.

This is a package-boundary cleanup, not a behavior change. The reusable SAGE
core now contains tool generation, validation/repair, registry storage,
visible-context inadequacy detection, routing scoring, online birth,
self-evolution reflection, and generic runtime invocation. The ToolSandbox
evidence adapter remains in the repository and is still used by
`scripts/run_sage_protocol.py` for Chapter 3 validation runs.

Checks before validation:

- `python -m py_compile scripts/run_sage_protocol.py src/sage_research/toolsandbox/openai_roles.py src/sage_research/toolsandbox/role_factory.py src/sage_research/toolsandbox/adapter.py src/sage_research/toolsandbox/sage_run_adapter.py src/sage_research/toolsandbox/integration.py src/sage_research/cache/openai_response_cache.py src/sage_research/evaluation/control_baseline_cache.py`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_toolsandbox_adapter.py tests/unit/test_sage_run_adapter.py tests/integration/test_toolsandbox_generated_tool_injection.py -q`
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py tests/unit/test_openai_response_cache.py tests/unit/test_protocol_generation_policy.py -q`
- `git diff --check`

Parallel validation slices:

- Coverage slice:
  `outputs/production_cleanup_validation/post_toolsandbox_boundary_move_coverage30_20260619_161004/mechanism_40_20260619_161008`
  - score: `0.687970 -> 0.898503`, delta `+0.210533`
  - outcome: `0.465680 -> 0.867256`, delta `+0.401576`
  - accepted tools: `21`; generated-tool-called scenarios: `30`; reuse: `50`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62705/outputs/production_cleanup_validation/post_toolsandbox_boundary_move_coverage30_20260619_161004/mechanism_40_20260619_161008/dashboard/task_compare.html`
- Action/side-effect slice:
  `outputs/production_cleanup_validation/post_toolsandbox_boundary_move_action30_20260619_161004/mechanism_40_20260619_161008`
  - score: `0.711811 -> 0.885335`, delta `+0.173523`
  - outcome: `0.453970 -> 0.826868`, delta `+0.372897`
  - accepted tools: `15`; generated-tool-called scenarios: `30`; reuse: `51`
  - runtime exceptions: `0`; side-effect incidents: `0`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62706/outputs/production_cleanup_validation/post_toolsandbox_boundary_move_action30_20260619_161004/mechanism_40_20260619_161008/dashboard/task_compare.html`
- Recency/answer slice:
  `outputs/production_cleanup_validation/post_toolsandbox_boundary_move_recency30_20260619_161004/mechanism_40_20260619_161008`
  - score: `0.619431 -> 0.910251`, delta `+0.290820`
  - outcome: `0.267642 -> 0.805560`, delta `+0.537918`
  - accepted tools: `12`; generated-tool-called scenarios: `30`; reuse: `47`
  - runtime exceptions: `0`; side-effect incidents: `1`; failed generated-tool attempts: `0`
  - dashboard: `http://127.0.0.1:62707/outputs/production_cleanup_validation/post_toolsandbox_boundary_move_recency30_20260619_161004/mechanism_40_20260619_161008/dashboard/task_compare.html`

The recency side-effect incident count matches the original validation anchor
for this slice and did not increase.

Follow-up checks after validation:

- `make compile`
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py tests/unit/test_protocol_generation_policy.py -q`
- `git diff --check`

Line count after this pass: `14,981` non-dashboard `src/sage_ts` lines.

Decision: keep this cleanup.

## 4.4 OpenAI And ToolSandbox Policy Boundary Move - 2026-06-22

Moved remaining integration-specific code out of the reusable `src/sage_ts`
core:

- `src/sage_ts/adapters/openai_agent_adapter.py` moved to
  `src/sage_research/openai/chat_adapter.py`.
- `src/sage_ts/config/models.py` moved to
  `src/sage_research/config/models.py`.
- `src/sage_ts/runtime/base_toolset.py` moved to
  `src/sage_research/toolsandbox/base_toolset.py`.
- Added `src/sage_ts/generation/chat.py` with the provider-neutral
  `ChatRequest` dataclass used by `ToolGenerator`.
- Removed now-empty `src/sage_ts/adapters` and `src/sage_ts/config` package
  marker files.

Rationale: OpenAI chat execution, model metadata, and ToolSandbox reduced base
tool policies are research harness concerns. The production SAGE core should
retain the self-evolution mechanism: inadequacy detection, tool generation,
validation, registry storage, routing, tool invocation, lifecycle reflection,
and output normalization.

Line count after this pass: `14,768` non-dashboard `src/sage_ts` lines across
`26` Python files.

Static validation:

- `PYTHONPATH=src:. python -m py_compile scripts/run_sage_protocol.py ...`
  passed for touched runner, SAGE, OpenAI, config, and ToolSandbox modules.
- `PYTHONPATH=src:. ruff check src/sage_ts src/sage_research
  scripts/run_sage_protocol.py --select F401,F841,F811,F821 --exclude
  src/sage_ts/dashboard` passed.
- Focused tests passed:
  - `tests/unit/test_model_config.py`
  - `tests/unit/test_base_toolset.py`
  - `tests/unit/test_tool_generator.py`
  - `tests/unit/test_protocol_generation_policy.py`
  - `tests/unit/test_control_baseline_cache.py`
  - `tests/unit/test_openai_toolsandbox_roles.py`
  - `tests/unit/test_toolsandbox_adapter.py`
  - `tests/unit/test_sage_run_adapter.py`
  - `tests/integration/test_toolsandbox_generated_tool_injection.py`

Behavior validation used three cached-control 30-task slices with
`SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generation enabled, response cache off,
and `gpt-4o-mini` for actor, user, and generation.

| Slice | Run path | Score | Outcome | Accepted tools | Generated-tool-called scenarios | Runtime exceptions | Generated-tool failures | Side-effect incidents |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Coverage | `outputs/production_cleanup_validation/post_openai_base_policy_boundary_move_coverage30_20260622_192552/mechanism_40_20260622_192557` | `0.687970 -> 0.907205` (`+0.219235`) | `0.465680 -> 0.890727` (`+0.425047`) | 21 | 30 | 0 | 0 | 0 |
| Action | `outputs/production_cleanup_validation/post_openai_base_policy_boundary_move_action30_20260622_192552/mechanism_40_20260622_192557` | `0.711811 -> 0.872748` (`+0.160937`) | `0.453970 -> 0.822710` (`+0.368740`) | 15 | 30 | 0 | 0 | 0 |
| Recency | `outputs/production_cleanup_validation/post_openai_base_policy_boundary_move_recency30_20260622_192552/mechanism_40_20260622_192557` | `0.619431 -> 0.908781` (`+0.289350`) | `0.267642 -> 0.880000` (`+0.612358`) | 12 | 30 | 0 | 0 | 0 |

Decision: keep this cleanup.

## 5. Large Module Reduction Plan

### `src/sage_research/toolsandbox/openai_roles.py`

Current issue: one large module still owns actor policy assembly, generated-tool
choice, continuation choice, transcript parsing, schema filtering, and model
inference hooks.

Safe split order:

1. Move pure transcript/payload parsing helpers into
   `src/sage_research/toolsandbox/tool_result_parsing.py`.
2. Move generated-tool choice rules into
   `src/sage_research/toolsandbox/generated_tool_choice.py`.
3. Move generated-tool schema filtering and compact actor-facing projections into
   `src/sage_research/toolsandbox/generated_tool_prompting.py`.
4. Leave the OpenAI role class and model call override in
   `openai_roles.py`.

Validation gate after each extraction:

- import/compile check;
- focused role tests;
- one 20-task cached-control smoke if tool-choice code moved;
- 60-task validation before any full run.

Do not delete active generated-tool choice rules without matched metric evidence.

### `src/sage_ts/generation/tool_generator.py`

Current issue: generation prompts, repair prompts, deterministic repair builders,
contract builders, and generated-code templates are still in one large file.

Safe split order:

1. Move request/response prompt construction into
   `src/sage_ts/generation/prompts.py`.
2. Move deterministic contract builders into
   `src/sage_ts/generation/contract_builders/`.
3. Move deterministic repair selectors into
   `src/sage_ts/generation/repair_rules.py`.
4. Keep `ToolGenerator` orchestration in `tool_generator.py`.

Validation gate after each extraction:

- all tool-generator unit tests;
- validation/sandbox tests;
- 20-task online-build smoke;
- 60-task online-build validation before promotion.

Do not simplify or remove deterministic builders until a matched run proves no
loss in accepted tools, generated-tool-called scenarios, outcome lift, safety,
or runtime stability.

## 6. Package And Release Identity

Current issue: package metadata still identifies the repository as upstream
ToolSandbox even though the release product is SAGE built on ToolSandbox.

Safe steps:

1. Decide whether release packaging is `sage-toolsandbox` or a research repo
   with both upstream ToolSandbox and SAGE modules.
2. Update `pyproject.toml` name, description, authorship, URLs, and classifiers.
3. Add console entry points only for stable SAGE commands, especially the
   protocol runner and preflight.
4. Preserve upstream ToolSandbox attribution and license notices.
5. Run secret scan and package build checks before publishing.

Validation gate:

- `python -m build` or local equivalent;
- import smoke for `tool_sandbox` and `sage_ts`;
- `scripts/check_no_secrets.py`;
- no `outputs/`, `artifacts/`, `.secrets/`, caches, or logs in release package.

## 7. Script And Release Surface Reduction

Current issue: the repo still contains exploratory scripts, old dashboards,
historical renderers, and campaign utilities that are not part of production
SAGE.

Keep as production or near-production:

- `scripts/run_sage_protocol.py`
- `scripts/preflight_final_run.py`
- retired whole-dataset preflight launcher (removed)
- `scripts/export_sage_metrics.py`
- `scripts/cache_llm_usage_by_task.py`
- `scripts/check_no_secrets.py`
- current figure renderers

Move, delete, or archive after review:

- old campaign-specific split builders;
- obsolete dashboard patch scripts;
- old final-hardening report writers;
- bridge-policy or force-call diagnostic utilities;
- one-off audit scripts not referenced by the current v061 methodology.

Validation gate:

- `rg` for deleted script names in Makefile, README, docs, and tests;
- `make test`;
- `git diff --check`;
- one current SAGE smoke run before release tagging.

## Metric Preservation Rule

Any code movement that touches generation, validation, routing, actor tool
choice, or registry accounting must preserve the current SAGE behavior before it
is accepted. For small pure extraction refactors, unit tests and compile checks
are sufficient. For behavior-adjacent refactors, require at least a 20-task
smoke and a 60-task validation. For changes to generation or routing decisions,
run a 250-task validation before a full-dataset run.
