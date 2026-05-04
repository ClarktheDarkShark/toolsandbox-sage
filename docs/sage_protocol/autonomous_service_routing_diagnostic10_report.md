# Autonomous Service Routing Diagnostic 10

## Objective
Test whether the parked `next_service_tool_call` candidate is actually adopted when frozen in a candidate registry, without online generation or active-registry promotion.

## State Read
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/autonomous_loop_generation_contract20_v3_report.md`
- `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `artifacts/summaries/failure_memory.json`

## Files Changed
- `artifacts/summaries/autonomous_service_routing_diagnostic10/cohort_manifest.json`
- `artifacts/summaries/autonomous_service_routing_diagnostic10/cohort_diversity_report.json`
- `artifacts/summaries/autonomous_service_routing_diagnostic10/summary.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `artifacts/summaries/failure_memory.json`
- `docs/sage_protocol/autonomous_service_routing_diagnostic10_report.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Tests Run
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
- Result: active 3-helper registry PASS; candidate 4-helper registry PASS.
- No unit tests were run because this loop made no code changes.

## Experiment Design
- Run root: `outputs/autonomous_service_routing_diagnostic10/mechanism_40_20260503_100727`
- Mode: `mechanism_40`
- Generation: `off`
- Candidate registry: `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
- Scenario count: `10`
- Cohort: 6 direct service-precondition positives, 2 service-adjacent complex negatives, 2 unrelated contact negatives.
- Dashboard: `outputs/autonomous_service_routing_diagnostic10/mechanism_40_20260503_100727/dashboard/index.html`
- Task focus dashboard: `outputs/autonomous_service_routing_diagnostic10/mechanism_40_20260503_100727/dashboard/task_focus.html`

## Diversity Note
- Positive service families covered location, wifi, and cellular, each with explicit and implicit variants.
- Negatives checked send-message-with-cellular-off and unrelated contact lookup routing.
- Largest family share: `0.20`; max cluster size: `2`.

## Registry State Before/After
- Active registry before and after: 3 helpers at `artifacts/registry_phaseE_portfolio/registry_manifest.json`.
- Candidate registry before and after: 4 helpers at `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`.
- Promotion decision: `not_promoted`.
- Reason: `adoption confirmed, but outcome effect is mixed and exact success did not improve`.

## Tools Proposed / Accepted / Rejected / Parked
- Proposed: `0` (generation OFF)
- Accepted: `0` new tools
- Rejected: `0` new tools
- Parked: `next_service_tool_call` remains candidate-only.

## Visible / Called / Adoption Summary
- Visible generated tools: `['next_service_tool_call']`
- Visible scenarios: `6`
- Called scenarios: `5`
- Visible-not-called scenarios: `1`
- Attempted scenarios: `5`
- Failed helper scenarios: `0`
- Helper call counts: `{'next_service_tool_call': 7}`
- Reuse count: `7`
- Hidden in negatives/complex non-targets: `4`

## Metrics
- Canonical/control mean: `0.885969`
- Canonical/candidate mean: `0.909739`
- Canonical delta: `+0.023770`
- Canonical relative lift: `2.68%`
- Outcome/control mean: `0.807111`
- Outcome/candidate mean: `0.815235`
- Outcome delta: `+0.008123`
- Outcome relative lift: `1.01%`
- Exact successes: control=`0`, SAGE=`0`, delta=`0`
- Canonical gains/regressions/preserved: `6` / `3` / `1`
- Outcome gains/regressions/preserved: `3` / `3` / `4`
- Runtime exceptions: `0`

## Service-Positive Subset
- Count: `6`
- Outcome gains/regressions/preserved: `2` / `2` / `2`
- Mean outcome delta: `+0.009116`

## Side-Effect Violations
- Runtime exceptions: `0`.
- Manual trace check: helper-called service scenarios still called original ToolSandbox setter tools downstream.
- No helper was exposed in unrelated contact negatives or service-adjacent send-message scenarios.
- No dedicated `side_effect_preservation_report.jsonl` was exported for this diagnostic.

## Route-Mismatch Note
- Canonical and outcome deltas were both positive but small.
- No route-mismatch adjustment is claimed.
- Exact success did not improve, so this is not promotion-grade evidence.

## Interpretation
The prior visible-not-called failure is not persistent under a frozen candidate registry: `next_service_tool_call` was visible in 6 direct service positives and called in 5 of them, with 7 total helper calls. It was hidden in the 4 negative/complex cases. Adoption is therefore confirmed.

The candidate is still not promotion-ready. Outcome impact is mixed: the service-positive subset had 2 gains, 2 regressions, and 2 preserved cases. The implicit location and wifi cases regressed, and exact success stayed flat. The likely remaining issue is validation/affordance quality: the helper can be used before all relevant service and low-battery state is known, leading to suboptimal or duplicate service sequencing.

## Decision Label
continue validation repair

## Exact Next Action
Repair the `next_service_tool_call` candidate contract/validation so it requires complete current service and low-battery state, or abstains when state is missing. Then rerun this same 10-scenario generation-off diagnostic before any active-registry promotion.
