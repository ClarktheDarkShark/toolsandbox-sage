# Autonomous Tool-Evolution Loop: Generation Contract + Routing Diagnostic

## Objective
Improve SAGE framework behavior without hand-building tools: suppress redundant narrow births, tighten generated-tool contracts for contact/service shortfalls, and test whether accepted candidates are validated, visible, adopted, and value-producing.

## State Read
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/decisive_tool_experiment20_40_v2_report.md`
- `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json` (missing before this loop)
- `artifacts/summaries/failure_memory.json` (missing before this loop)

## Files Changed
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/campaign/artifacts.py`
- `tests/unit/test_online_birth.py`
- `artifacts/registry_phaseE_portfolio/registry_manifest.json` restored to 3 active helpers
- `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
- `artifacts/summaries/autonomous_loop_generation_contract20_v3/summary.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `artifacts/summaries/failure_memory.json`

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- Result: `30 passed`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json`
- Result: 3 active entries PASS after restore
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
- Result: 4 candidate entries PASS

## Experiment Design
- Run root: `outputs/autonomous_loop_generation_contract20_v3_resume/mechanism_40_20260503_095138`
- Mode: `mechanism_40`
- Scenario count: `20`
- Generation: `on`
- Cohort focus: contact/message constraints, service preconditions, selected-record downstream use
- Manifest: `artifacts/summaries/autonomous_loop_generation_contract20_v3/cohort_manifest.json`
- Dashboard: `outputs/autonomous_loop_generation_contract20_v3_resume/mechanism_40_20260503_095138/dashboard/index.html`
- Task focus dashboard: `outputs/autonomous_loop_generation_contract20_v3_resume/mechanism_40_20260503_095138/dashboard/task_focus.html`

## Diversity Note
- 20 scenarios across contact/message constraints, service preconditions, and selected-record downstream-use cases.
- Largest base family share in cohort report: `0.20`.
- Max near-duplicate cluster size in cohort report: `2`.

## Registry State Before/After
- Active before loop: 3 proved helpers.
- During generation: `next_service_tool_call` was accepted and temporarily written by the online birth path.
- Active after loop: restored to 3 proved helpers at `artifacts/registry_phaseE_portfolio/registry_manifest.json`.
- Candidate registry: `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json` with 4 proof-passing entries.
- Candidate parked reason: `accepted and proof-passing but visible in 4 scenarios and called in 0`.

## Tools Proposed / Accepted / Rejected / Parked
- Proposed: `3`
- Accepted: `1` (`next_service_tool_call`)
- Rejected: `2` (`select_contact_field_by_constraint` twice)
- Parked: `next_service_tool_call` because it had proof but no adoption.
- Rejection reason: `select_contact_field_by_constraint` failed `search_filter_missing_tie_behavior` twice.
- Bloat control: redundant `recency_timestamp_bounds` and `message_search_time_window` births were skipped because `resolve_search_window_or_bounds` already has current proof.

## Visible / Called / Adoption Summary
- Accepted generated tools: `['next_service_tool_call']`
- Visible generated scenarios: `4`
- Called generated scenarios: `0`
- Visible-not-called scenarios: `4`
- Helper call counts from candidate transcripts: `{}`
- Interpretation: score lift is not tool-driven because no retained or newly accepted helper call was observed.

## Metrics
- Canonical/control mean: `0.698407`
- Canonical/candidate mean: `0.778811`
- Canonical delta: `+0.080404`
- Canonical relative lift: `11.51%`
- Outcome/control mean: `0.411288`
- Outcome/candidate mean: `0.538920`
- Outcome delta: `+0.127632`
- Outcome relative lift: `31.03%`
- Exact successes: control=`0`, SAGE=`1`, delta=`1`
- Canonical gains/regressions/preserved: `11` / `6` / `3`
- Outcome gains/regressions/preserved: `7` / `4` / `9`
- Runtime exceptions: `0`
- Protocol gate: `True`

## Side-Effect Violations
- Candidate-attributable side-effect violations observed: `0`.
- Caution: no dedicated `side_effect_preservation_report.jsonl` was exported for this run; because the accepted candidate was never called, no candidate side-effect harm can be attributed.

## Route-Mismatch Note
- Canonical and outcome metrics both improved in aggregate.
- No manual route-mismatch adjudication was performed for this loop.
- The lift should not be claimed as helper-driven because helper adoption was zero.

## Interpretation
The framework repair did two useful things: it blocked redundant narrow search-window births when a broader retained helper already has proof, and it produced one proof-passing service-precondition candidate. However, the accepted service helper was visible but uncalled in all 4 relevant visible scenarios. That means this loop is not promotion evidence. It is routing evidence: SAGE can generate a valid candidate for the service-precondition cluster, but the model/routing layer does not yet use it.

The contact-selector lane remains blocked at validation: generated specs still omit explicit tie/ambiguity behavior, so the gate correctly rejects them.

## Decision Label
continue routing repair

## Exact Next Action
Run a generation-off candidate-registry routing diagnostic for `next_service_tool_call` on 8-12 service-precondition scenarios using `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`. If visible-not-called persists, repair affordance/routing for state-precondition helpers. Separately tighten the contact selector generation contract to force explicit tie behavior before retesting contact selection.
