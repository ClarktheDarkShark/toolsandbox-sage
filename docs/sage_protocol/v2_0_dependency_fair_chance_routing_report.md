# V2.0 Dependency Fair-Chance Routing Report

## Objective
Repair the adoption path for the cluster-born dependency/precondition helper without modifying the frozen best3 claim registry.

## Files Changed
- src/sage_ts/validation/live_candidate_check.py
- src/sage_ts/runtime/routing_scorer.py
- src/sage_ts/runtime/toolsandbox_integration.py
- tests/unit/test_live_candidate_check.py
- tests/unit/test_runtime_routing_scorer.py
- tests/unit/test_state_helper_guidance.py
- artifacts/summaries/failure_memory.json
- docs/sage_protocol/current_state.md
- docs/sage_protocol/run_ledger.md
- docs/sage_protocol/v2_0_dependency_fair_chance_routing_report.md

## What Changed
- Grading accounting: missing `expected_milestone_calls_replaced` is now a live-validation warning, not a hard rejection, when final-state preservation and grading-accounting notes are present and examples produce usable output.
- Runtime routing: added bounded fair-chance routing for new non-diagnostic cluster-born helpers with strong trigger/family/cluster fit and no call history.
- Runtime routing: invalid contribution summaries from runs with runtime exceptions are ignored for adoption-risk evidence.
- Runtime routing: adoption-risk suppression now applies only when generic relevance score is otherwise sufficient.
- Downstream availability: helpers whose output schema can emit one of several original ToolSandbox tools are allowed when at least one emitted tool is available, instead of requiring every possible emitted tool.
- Affordance: generic state/precondition helper docs now explain when to call the helper, how to use returned original ToolSandbox calls, and how canonical-route substitution is accounted.
- Affordance: generated dict-input docs now expose literal keys inferred from generated code, e.g. `dependency_state` keys.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_live_candidate_check.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_state_helper_guidance.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> PASS, 62 passed.
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json` -> PASS, 3 active entries pass.
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_0_dependency_fair_chance20_20260504_165041/registry_manifest.json` -> PASS, 4 active entries pass.

## Diagnostic Design
- Manifest: `artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/cohort_diversity_report.json`
- Candidate registry: `artifacts/registry_candidates/v2_0_dependency_fair_chance20_20260504_165041/registry_manifest.json`
- Frozen best3 registry modified: no.
- Generation: OFF, to isolate fair-chance adoption of the prior generated candidate from turn 1.
- Control cache mode: `use-if-eligible`; final valid run used fresh controls `0 cached / 20 fresh`.
- Cohort quality: PASS; 20 scenarios, 18 base families, largest family variant count 2, no-current-helper-fit share 0.45.

## Diagnostic Command
```bash
SAGE_V2_EXPERIMENT_FEATURES=candidate_repair,contract_synthesis,dependency_logic,evidence_routing,grading_accounting,live_validation \
PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --manifest artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/cohort_manifest.json \
  --mode mechanism_40 \
  --registry-dir artifacts/registry_candidates/v2_0_dependency_fair_chance20_20260504_165041 \
  --output-root outputs/v2_0_dependency_fair_chance20_20260504_165041 \
  --artifact-root artifacts \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --generation off \
  --parallel-arms \
  --control-cache use-if-eligible
```

## Final Diagnostic Output
- Run root: `outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647`
- Dashboard: http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/index.html
- Task-focus dashboard: http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/task_focus.html
- Machine summary: `artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/diagnostic_summary.json`

## Metrics
- Outcome delta: `+0.0185`
- Canonical delta: `+0.0553`
- Exact successes: `control=0 -> SAGE=2`
- Outcome gains/regressions/preserved: `5 / 7 / 8`
- Canonical gains/regressions/preserved: `9 / 7 / 4`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: FAIL; reason `outcome_gains_do_not_exceed_regressions`
- Route-mismatch-qualified: `False`

## Candidate Visibility and Calls
- `next_dependency_precondition_call`: visible `9`, called `0`, visible-not-called `9`, attempts `0`.
- Fair-chance routing did work: the helper was exposed on strong dependency/precondition matches with `reason=fair_chance_cluster_fit` and `fair_chance_candidate=true`.
- The helper was still not adopted after improved state-helper docs and generated dict-key affordance.
- No helper-caused runtime or side-effect harm was observed because the helper was not called.

## Other Helper Contribution
- `resolve_search_window_or_bounds`: visible `3`, called `1`, called-subset outcome delta `+0.8847`.
- `select_record_by_timestamp_extreme`: visible `2`, called `2`, called-subset outcome delta `+0.5091`.
- `relative_day_time_to_timestamp`: visible/called `0 / 0` in this focused cohort.

## Interpretation
The blocker is no longer candidate validity or basic routing exposure. The system gave the generated dependency helper a fair adoption chance, including a second chance after generic dict-key affordance repair. The acting model still chose not to call it. That makes this specific dependency-helper lane diagnostic-only for now.

The likely root cause is the generated contract: it requires the model to construct a `dependency_state` dictionary and offers little advantage over direct ToolSandbox service setter calls. Future dependency/precondition candidates should use simpler scalar inputs or be born from observed failed setter/precondition traces where the helper clearly compresses a real multi-step failure.

## Decision Label
`park dependency lane`

## Exact Next Action
Return to V2.0 shortfall mining and prioritize a different no-current-helper-fit cluster. Do not run confirmation-60 for `next_dependency_precondition_call` unless a successor candidate first shows actual later-task calls and non-harmful called-subset contribution in a focused diagnostic.
