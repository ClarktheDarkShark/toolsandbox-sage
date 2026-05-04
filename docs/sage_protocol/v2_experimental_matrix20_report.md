# V2 Experimental Matrix-20 Report

## Objective
Run a controlled, quality-gated 20-scenario matrix to identify which V2 framework ideas improve generated-tool validity, adoption, routing precision, task completion, and grading accounting without relying on retained helper reuse.

## Files Changed
- `src/sage_ts/experiments/v2_flags.py` and `src/sage_ts/experiments/__init__.py`: feature flags for matrix variants.
- `src/sage_ts/adequacy/candidate_gate.py`: grading-accounting feature gating for canonical-route substitution fields.
- `src/sage_ts/adequacy/inadequacy_classifier.py`: dependency/precondition shortfall observation behind feature flag.
- `src/sage_ts/generation/tool_generator.py`: gated grading-accounting prompt, dependency contract, trigger/tie/ambiguity synthesis, and structured repair prompt.
- `src/sage_ts/orchestration/online_birth.py`: gated live validation, candidate repair pass, and repair telemetry.
- `src/sage_ts/runtime/routing_scorer.py`: evidence-routing feature gate.
- `src/sage_ts/campaign/artifacts.py`: added `tool_repair_attempted` campaign event type.
- `scripts/run_v2_experimental_matrix20.py`: clean-registry matrix runner and summary export.
- `tests/unit/test_online_birth.py`: feature-flag and repair-pass coverage.
- `tests/unit/test_campaign_artifacts.py`: repair-event coverage.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_campaign_artifacts.py -q` -> `2 passed`.
- Full targeted and unit tests were run after report/state updates; see final state for final status.

## Cohort And Cache
- Manifest: `artifacts/summaries/v2_experimental_matrix20_clean/cohort_manifest.json`.
- Diversity: `20` scenarios, `15` base families, largest family share `0.10`, largest family variant count `2`, no-current-helper-fit share `0.40`; cohort quality PASS.
- Primary registry mode: clean empty candidate registry per variant. This matrix tests new tool birth/adoption, not retained helper reuse.
- Control cache status: all matrix variants reported `fresh` controls (`20` fresh, `0` cached). Cache was available but no eligible 3-run compatible baseline was used in these summaries.
- Dashboard opening: every completed variant dashboard and task-focus dashboard was opened from the recorded run path; stale guessed URLs caused the earlier 404s.

## Variant Metrics
| Variant | Features | Outcome delta | Canonical delta | Exact C/S | Outcome G/R/P | Accepted | Accepted tools | Newly generated called | Called/VNC | Sidefx | Runtime | Control |
|---|---:|---:|---:|---:|---|---:|---|---|---:|---:|---:|---|
| `v0_current_v2_baseline` | `default` | +0.1526 | +0.0308 | `2/1` | `[9, 3, 6]` | `2` | `recency_to_timestamp_bounds, next_dependency_precondition_call` | `recency_to_timestamp_bounds/1` | `9` | `0` | `0` |
| `v1_grading_accounting` | `grading_accounting` | +0.0783 | +0.0346 | `1/1` | `[6, 4, 8]` | `2` | `recency_to_timestamp_bounds, message_search_time_window` | `message_search_time_window, recency_to_timestamp_bounds/2` | `16` | `0` | `0` |
| `v2_dependency_logic` | `dependency_logic` | -0.0596 | +0.0460 | `1/3` | `[3, 3, 12]` | `2` | `recency_to_timestamp_bounds, message_search_time_window` | `recency_to_timestamp_bounds/1` | `15` | `1` | `0` |
| `v3_live_validation` | `live_validation` | -0.1330 | -0.0831 | `2/1` | `[3, 7, 8]` | `0` | `-` | `-/None` | `None` | `0` | `0` |
| `v4_candidate_repair` | `candidate_repair` | -0.0863 | +0.0478 | `2/2` | `[5, 7, 6]` | `2` | `recency_to_timestamp_bounds, message_search_time_window` | `recency_to_timestamp_bounds/1` | `17` | `1` | `0` |
| `v5_contract_synthesis` | `contract_synthesis` | +0.0932 | +0.0277 | `2/1` | `[8, 4, 6]` | `1` | `message_search_time_window` | `message_search_time_window/1` | `7` | `0` | `0` |
| `v6_evidence_routing` | `evidence_routing` | -0.0473 | -0.0504 | `3/2` | `[5, 8, 5]` | `1` | `message_search_time_window` | `-/0` | `0` | `0` | `0` |
| `v7_combined_best_stack` | `candidate_repair,contract_synthesis,evidence_routing,grading_accounting` | +0.0260 | +0.0506 | `2/2` | `[6, 5, 7]` | `3` | `recency_to_timestamp_bounds, select_record_by_timestamp_extreme, message_search_time_window` | `-/0` | `8` | `0` | `0` |

## Tool Birth And Adoption
- This report distinguishes `new births accepted` from `newly generated helper called later` and from retained generated-helper reuse.
- No retained helpers were counted as self-evolution evidence in the clean primary matrix.
- Best clean adoption signal: `variant5_contract_synthesis` accepted `message_search_time_window`, called it later, had `+0.0932` outcome delta, `+0.0277` canonical delta, `1/7` called/VNC, and `0` side-effect/runtime incidents.
- Highest outcome delta: `variant0_current_v2_baseline` at `+0.1526`, but it accepted `next_dependency_precondition_call` without later calls and had `9` visible-not-called exposures, so it is less clean as tool-evolution evidence.
- Combined stack after repair-event fix accepted three tools but called none later (`0/8` called/VNC), so the combined stack is not a winner despite positive aggregate scores.

## Rejections And Live Validation
- `variant0_current_v2_baseline`: rejections `{'search_filter_missing_tie_behavior': 2, 'live_example_2_negative_not_abstained': 2, 'live_missing_expected_milestone_calls_replaced': 2, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'missing_decisive_positive_triggers': 2}`; live validation `{'checked': 4, 'accepted': 2, 'rejected': 2}`; repair attempts `0`
- `variant1_grading_accounting`: rejections `{'search_filter_missing_tie_behavior': 2, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'missing_decisive_positive_triggers': 2}`; live validation `{}`; repair attempts `0`
- `variant2_dependency_logic`: rejections `{'missing_downstream_original_tool_call': 1, 'missing_downstream_tool_preservation': 2, 'missing_decisive_positive_triggers': 2, 'state_helper_not_runtime_actionable': 2}`; live validation `{}`; repair attempts `0`
- `variant3_live_validation`: rejections `{'missing_downstream_tool_preservation': 3, 'missing_downstream_original_tool_call': 1, 'live_example_2_negative_not_abstained': 2, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'missing_decisive_positive_triggers': 2}`; live validation `{'checked': 2, 'rejected': 2}`; repair attempts `0`
- `variant4_candidate_repair`: rejections `{'search_filter_missing_tie_behavior': 2, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'unresolved_failure_memory:state_precondition_visible_not_called': 2}`; live validation `{}`; repair attempts `6`
- `variant5_contract_synthesis`: rejections `{'missing_downstream_tool_preservation': 3, 'missing_downstream_original_tool_call': 1, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'unresolved_failure_memory:state_precondition_visible_not_called': 2}`; live validation `{}`; repair attempts `0`
- `variant6_evidence_routing`: rejections `{'missing_downstream_tool_preservation': 3, 'missing_downstream_original_tool_call': 1, 'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'missing_decisive_positive_triggers': 2}`; live validation `{}`; repair attempts `0`
- `variant7_combined_best_stack`: rejections `{'unresolved_failure_memory:search_filter_missing_tie_behavior': 1, 'unresolved_failure_memory:state_precondition_visible_not_called': 2}`; live validation `{}`; repair attempts `4`

## Dashboard Paths
- `variant0_current_v2_baseline`: `outputs/v2_experimental_matrix20_clean/variant0_current_v2_baseline/mechanism_40_20260503_214349/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant0_current_v2_baseline/mechanism_40_20260503_214349/dashboard/task_focus.html`
- `variant1_grading_accounting`: `outputs/v2_experimental_matrix20_clean/variant1_grading_accounting/mechanism_40_20260503_214928/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant1_grading_accounting/mechanism_40_20260503_214928/dashboard/task_focus.html`
- `variant2_dependency_logic`: `outputs/v2_experimental_matrix20_clean/variant2_dependency_logic/mechanism_40_20260503_215359/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant2_dependency_logic/mechanism_40_20260503_215359/dashboard/task_focus.html`
- `variant3_live_validation`: `outputs/v2_experimental_matrix20_clean/variant3_live_validation/mechanism_40_20260503_215856/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant3_live_validation/mechanism_40_20260503_215856/dashboard/task_focus.html`
- `variant4_candidate_repair`: `outputs/v2_experimental_matrix20_clean_repairfix/variant4_candidate_repair/mechanism_40_20260503_222846/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean_repairfix/variant4_candidate_repair/mechanism_40_20260503_222846/dashboard/task_focus.html`
- `variant5_contract_synthesis`: `outputs/v2_experimental_matrix20_clean/variant5_contract_synthesis/mechanism_40_20260503_220933/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant5_contract_synthesis/mechanism_40_20260503_220933/dashboard/task_focus.html`
- `variant6_evidence_routing`: `outputs/v2_experimental_matrix20_clean/variant6_evidence_routing/mechanism_40_20260503_221527/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean/variant6_evidence_routing/mechanism_40_20260503_221527/dashboard/task_focus.html`
- `variant7_combined_best_stack`: `outputs/v2_experimental_matrix20_clean_repairfix/variant7_combined_best_stack/mechanism_40_20260503_223211/dashboard/index.html`; task focus `outputs/v2_experimental_matrix20_clean_repairfix/variant7_combined_best_stack/mechanism_40_20260503_223211/dashboard/task_focus.html`

## Route-Mismatch And Grading Accounting
- `grading_accounting` made canonical substitution explicit and accepted/called two tools, but called-subset canonical delta was negative (`-0.0965`) and VNC was high (`16`). Keep the accounting fields in reports, but do not use this variant alone as the winning stack.
- `contract_synthesis` produced canonical-preserving candidates in this matrix and had the cleanest balance of outcome, canonical, adoption, and safety.
- `dependency_logic` showed canonical lift but outcome loss and one side-effect incident; it should not be scaled as-is.
- Candidate repair created repair telemetry after the event-schema fix, but standalone repair still produced negative outcome and a side-effect incident; do not include it in readiness.

## What Worked
- Stronger trigger, tie, ambiguity, and abstention contract synthesis produced the best clean generated-tool value.
- Clean-registry execution corrected the earlier methodological issue: the matrix now measures new generation/adoption rather than reuse of previous helpers.
- Grading-accounting metadata is useful for reporting, but not sufficient to drive quality by itself.

## What Failed
- Evidence routing alone over-suppressed exposure (`0` visible/called) and produced negative deltas.
- Live validation alone rejected all generated candidates and had negative outcome/canonical deltas; keep it minimal or only as a safety check after generation improves.
- Dependency/precondition logic remains too weak: non-adoption and side-effect risk persist.
- Candidate repair needs better repair-event handling now fixed, but the corrected rerun still did not improve quality.
- The automatic combined stack was too broad; combining individually weak ideas diluted the clean `contract_synthesis` signal.

## Recommended Winning Stack
Use only `contract_synthesis` for the next readiness-20 rerun.

Rationale:
- Positive outcome and canonical lift.
- Lower VNC than current default baseline.
- One accepted new tool was actually called later.
- No accepted-but-uncalled tools.
- No side-effect incidents.
- No runtime exceptions.

## Exact Next Action
Rerun readiness-20 with:

```bash
SAGE_V2_EXPERIMENT_FEATURES=contract_synthesis
python scripts/run_sage_protocol.py \
  --manifest artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json \
  --mode mechanism_40 \
  --registry-dir artifacts/registry_candidates/v2_readiness20_contract_synthesis \
  --output-root outputs/v2_readiness20_contract_synthesis \
  --artifact-root artifacts \
  --generation on \
  --parallel-arms \
  --control-cache use-if-eligible \
  --no-dashboard-open
```

Open both dashboards from `protocol_manifest.json` after the run completes.

## Decision Label
`rerun readiness-20 with winning stack`

## Post-Matrix Readiness Reruns

### Readiness: `contract_synthesis`
- Run: `outputs/v2_readiness20_contract_synthesis/mechanism_40_20260503_223710/`
- Dashboard: `outputs/v2_readiness20_contract_synthesis/mechanism_40_20260503_223710/dashboard/index.html`
- Task focus: `outputs/v2_readiness20_contract_synthesis/mechanism_40_20260503_223710/dashboard/task_focus.html`
- Outcome delta: `+0.0946`
- Canonical delta: `-0.0097`
- Exact successes: `control=2`, `SAGE=2`
- Helper: `message_search_time_window`, visible/called/VNC `8 / 1 / 7`
- Called-subset outcome/canonical: `+0.0000 / +0.0711`
- Side-effect/runtime incidents: `0 / 0`
- Protocol gate: FAIL, `non_positive_canonical_delta`, `gains_do_not_exceed_regressions`
- Interpretation: not claim-grade. The overall outcome lift was mostly not tool-driven; routing exposed the helper outside its downstream base-tool availability.

### Routing Repair
- Change: generic runtime routing now hides helpers when their declared `required_original_tool_calls` or `preserves_side_effect_tools` are unavailable in the current scenario's base tool set.
- This is framework-level, not tool-name-specific.

### Readiness: `contract_synthesis` After Routing Repair
- Run: `outputs/v2_readiness20_contract_synthesis_routingfix/mechanism_40_20260503_224320/`
- Dashboard: `outputs/v2_readiness20_contract_synthesis_routingfix/mechanism_40_20260503_224320/dashboard/index.html`
- Task focus: `outputs/v2_readiness20_contract_synthesis_routingfix/mechanism_40_20260503_224320/dashboard/task_focus.html`
- Outcome delta: `+0.0626`
- Canonical delta: `-0.0108`
- Exact successes: `control=1`, `SAGE=1`
- Helper: `message_search_time_window`, visible/called/VNC `2 / 1 / 1`
- Called-subset outcome/canonical: `+0.3947 / -0.1499`
- Side-effect/runtime incidents: `0 / 0`
- Protocol gate: FAIL, `non_positive_canonical_delta`, `gains_do_not_exceed_regressions`
- Interpretation: routing repair worked and produced a tool-driven outcome gain on the called case, but canonical still moved against SAGE.

### Readiness: `contract_synthesis,grading_accounting` After Routing Repair
- Run: `outputs/v2_readiness20_contract_synthesis_grading_routingfix/mechanism_40_20260503_224648/`
- Dashboard: `outputs/v2_readiness20_contract_synthesis_grading_routingfix/mechanism_40_20260503_224648/dashboard/index.html`
- Task focus: `outputs/v2_readiness20_contract_synthesis_grading_routingfix/mechanism_40_20260503_224648/dashboard/task_focus.html`
- Outcome delta: `-0.1475`
- Canonical delta: `+0.0442`
- Exact successes: `control=2`, `SAGE=1`
- Accepted-but-uncalled tools: `message_search_time_window`, `recency_to_timestamp_bounds`
- Newly generated helper calls: none
- Side-effect/runtime incidents: `0 / 0`
- Protocol gate: FAIL, `exact_successes_regressed`
- Interpretation: grading accounting made route substitution explicit but hurt adoption and task completion in this readiness sample.

## Updated Recommendation After Readiness
Do not proceed to 60 yet.

Keep the routing repair. The next blocker is generation/accounting affordance: SAGE can generate a useful helper, but the grading-accounted form is not adopted, and the contract-only form improves outcome while losing canonical credit. The next sprint should repair generated-helper affordances and route-mismatch accounting so outcome-positive, side-effect-safe substitutions are reportable without hiding canonical loss.

## Updated Decision Label
`repair generation then rerun matrix subset`

## Final Validation
- Targeted tests: `PYTHONPATH=src:. pytest tests/unit/test_runtime_routing_scorer.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_campaign_artifacts.py -q` -> `47 passed` after routing repair.
- Full unit tests: `PYTHONPATH=src:. pytest tests/unit -q` -> `170 passed, 2 warnings`.
- Registry checks: readiness candidate registries `v2_readiness20_contract_synthesis`, `v2_readiness20_contract_synthesis_routingfix`, and `v2_readiness20_contract_synthesis_grading_routingfix` all PASS check-only with zero active entries after failed-gate restore.

## Adoption Diagnosis Addendum
See `docs/sage_protocol/v2_tool_adoption_diagnosis_report.md`.

Key update: late birth was materially undercounting generated tools. A fair-chance frozen confirmation pass with accepted tools available from turn 1 showed `variant5_contract_synthesis` is the only protocol-passing positive stack: outcome `+0.0617`, canonical `+0.0979`, helper visible/called/VNC `4 / 3 / 1`, exact successes `0 -> 2`, side-effect/runtime `0 / 0`.

Updated decision: `rerun readiness-20 with two-stage confirmation`.

## Formal Validation Addendum - 2026-05-04T06:08:30.482096

After repairing helper affordance/routing and suppressing broad-harmful helpers, the winning validation portfolio was not the full combined matrix stack. It was the conservative best3 portfolio: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, and `select_record_by_timestamp_extreme`.

- Formal 100 outcome lift: `33.58%`; exact `control=16` -> `SAGE=23`; protocol pass `True`.
- Formal 250 outcome lift: `20.52%`; exact `control=31` -> `SAGE=40`; protocol pass `True`.
- Formal 250 reference/canonical similarity delta: `0.0660`.
- Runtime exceptions: `0`; helper side-effect incidents: `0`.
- Decision update: `rerun readiness-20 with winning stack` is superseded by formal 100 and 250 pass on the winning stack.
