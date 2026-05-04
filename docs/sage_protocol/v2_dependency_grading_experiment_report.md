# V2 Dependency/Grading Experiment Report

## Objective
Test whether SAGE can accept outcome-preserving deterministic helpers that intentionally substitute for canonical milestone routes while still preserving final state, side effects, and explicit grading accounting. Also test generic dependency/precondition birth logic, lightweight live validation, and routing suppression for helpers with poor visible-not-called history.

## Files Changed
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/validation/live_candidate_check.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_tool_generator.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_live_candidate_check.py`
- `artifacts/baselines/control_task_baselines/index.jsonl` removed from git tracking only; local cache contents remain ignored/local to avoid committing broken pointers to ignored record files.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_live_candidate_check.py -q` -> `44 passed`
- `PYTHONPATH=src:. pytest tests/unit/test_helper_contribution.py tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_live_candidate_check.py -q` -> `78 passed`
- `PYTHONPATH=src:. pytest tests/unit -q` -> `166 passed, 2 warnings`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_architecture_readiness_20/registry_manifest.json` -> PASS
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_dependency_grading_experiment20/registry_manifest.json` -> PASS, 3 active entries PASS

## Experiment Design
- Manifest: `artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json`
- Scenarios: exactly `20`
- Cohort quality: PASS, 15 base families, largest duplicate family size 2
- Generation: ON
- Candidate registry: `artifacts/registry_candidates/v2_dependency_grading_experiment20/registry_manifest.json`
- Active/frozen registry was not promoted from this diagnostic.
- Control cache mode: `use-if-eligible`; source was fresh controls (`cached=0`, `fresh=20`).
- Command:

```bash
conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json --mode mechanism_40 --registry-dir artifacts/registry_candidates/v2_dependency_grading_experiment20 --output-root outputs/v2_dependency_grading_experiment20 --artifact-root artifacts --generation on --parallel-arms'
```

## Output Paths
- Run root: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/`
- Dashboard: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/dashboard/index.html`
- Task focus dashboard: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/dashboard/task_focus.html`
- Paired comparison: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/paired_comparison.json`
- Helper contribution: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/helper_contribution_summary.json`
- Machine summary: `artifacts/summaries/v2_dependency_grading_experiment20/run_summary.json`
- Run log: `artifacts/summaries/v2_dependency_grading_experiment20/run.log`

## Candidate Rejection Reasons Before/After
Before this repair, readiness-20 rejected generated candidates for missing downstream preservation and did not distinguish final-state preservation from canonical-route preservation.

After this repair:
- Tools proposed: `6`
- Tools accepted: `1`
- Tools rejected: `5`
- No candidate was rejected solely for canonical-route substitution.
- Rejection reasons were contract/safety issues: `search_filter_missing_tie_behavior`, `unresolved_failure_memory:search_filter_missing_tie_behavior`, and `missing_decisive_positive_triggers`.

## Canonical-Preserving vs Canonical-Substituting Candidates
- Canonical-preserving accepted candidates: `0`
- Outcome-preserving but canonical-substituting accepted candidates: `1`
- Accepted candidate: `next_dependency_precondition_call`
- Classification: `outcome_preserving_but_canonical_substituting`
- Substitution risk: `low`
- Expected milestone calls replaced: `set_low_battery_mode_status`, `set_cellular_service_status`
- Lightweight live validation: accepted; positives usable `2`, negatives abstained `1`

## Metrics
- Control mean canonical: `0.7620`
- SAGE mean canonical: `0.8421`
- Canonical delta: `+0.0801`
- Control mean outcome: `0.4396`
- SAGE mean outcome: `0.5127`
- Outcome delta: `+0.0731`
- Exact successes: control `1`, SAGE `2`
- Canonical gains/regressions/preserved: `8 / 6 / 6`
- Outcome gains/regressions/preserved: `3 / 5 / 10`
- Runtime exceptions: `0`
- Side-effect incidents: `0`

## Visibility And Routing
Prior readiness-20 generated-helper exposure was `15 visible / 6 called / 9 visible-not-called`.

This run:
- `resolve_search_window_or_bounds`: visible `12`, called `6`, visible-not-called `6`
- `prepare_reminder_creation_args`: visible `0`, called `0`
- `next_dependency_precondition_call`: visible `0`, called `0`
- Routing reasons included `blocked_by_visible_not_called_adoption_risk=16`, `generic_relevance_score_passed=12`, and `blocked_by_negative_trigger=6`.

Interpretation: routing suppression reduced broad exposure and kept the newly accepted diagnostic dependency helper out of unrelated tasks. The accepted tool was not called later in the same run, so it is diagnostic evidence only and must not be promoted yet.

## Dependency/Precondition Logic Assessment
Generic dependency/precondition clustering is promising. The system generated and accepted `next_dependency_precondition_call` from service/precondition shortfalls without hardcoding a named campaign tool. The accepted candidate declared canonical substitution risk, final-state preservation, and grading accounting, and passed lightweight live validation.

Remaining gap: adoption evidence is still missing. The next readiness run should test whether the accepted candidate is reused/called in later relevant tasks rather than merely accepted at the end of discovery.

## Live Validation Assessment
The lightweight live check caught the intended requirements:
- candidate code executed without runtime error
- positive examples returned usable deterministic output
- negative example abstained
- canonical substitution required explicit milestone replacement and grading-accounting fields

No live-validation blocker was observed.

## Route-Mismatch Note
This sprint deliberately separates task outcome from canonical route evidence. The gate now permits declared helper substitution when final-state/side-effect preservation is documented, but reports the substitution separately. This avoids rejecting valid task-completion helpers solely because they may replace benchmark-expected intermediate calls.

## Commit Issue Resolution
The diagnostic run appended local control-cache rows to tracked `artifacts/baselines/control_task_baselines/index.jsonl`, while the referenced record JSON files are intentionally ignored. Committing only the index would create broken cache references. The fix is to remove `index.jsonl` from git tracking and keep it as a runtime-local ignored cache file. The cache code still creates it automatically when needed.

## Recommendation
Rerun readiness-20 with the new grading-accounting, live-validation, dependency-cluster, and routing changes. Do not promote `next_dependency_precondition_call` from this diagnostic alone. Treat it as candidate evidence until a later run shows actual calls and non-harmful contribution.

## Decision Label
`rerun readiness-20`
