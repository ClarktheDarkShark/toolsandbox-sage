# Decisive Tool Experiment20 Gate Repair Rerun Report

## Objective
Run one bounded discovery loop to verify whether the repaired decisive-tool gate rejects invalid service-precondition births while retained claim-safe helpers continue to improve diverse task completion.

## State Read
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/decisive_tool_experiment20_report.md`
- `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `artifacts/summaries/failure_memory.json`
- `artifacts/summaries/decisive_tool_experiment20/summary.json`
- `artifacts/summaries/decisive_tool_experiment20/cohort_diversity_report.json`

## Main Action
Discovery run.

## Loop Hypothesis
The repaired decisive-tool gate should reject invalid service-precondition births that lack decisive positive triggers while preserving the retained helper signal from `resolve_search_window_or_bounds` and `select_record_by_timestamp_extreme`.

Evidence motivating this loop: the previous broad 20 run accepted `next_service_tool_call` even though it was diagnostic-only, missing positive triggers, and had side-effect preservation risk.

## Files Changed
- `docs/sage_protocol/decisive_tool_experiment20_gate_repair_rerun_report.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/cohort_manifest.json`
- `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/cohort_diversity_report.json`
- `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/summary.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `artifacts/summaries/failure_memory.json`
- `artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.json`
- `artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.sha256`

No source code was changed in this loop. The prior gate repair was verified.

## Tests Run
```bash
PYTHONPATH=src:. pytest tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.json
```

Results:
- Unit tests: `32 passed`
- Active registry check-only: `PASS`
- Frozen confirmation registry check-only: `PASS`

## Experiment Design
- Cohort: 20 scenarios, 5 buckets x 4 scenarios.
- Manifest: `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/cohort_manifest.json`
- Diversity report: `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/cohort_diversity_report.json`
- Generation mode: `on`
- Registry: `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- Output root: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/`
- Dashboard: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/dashboard/index.html`
- Task focus dashboard: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/dashboard/task_focus.html`

Command:
```bash
PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment20_gate_repair_rerun
```

## Diversity Note
- Scenario count: `20`
- Bucket counts: `4` each across reminder/search-window, record latest-oldest, contact/message constraints, service preconditions, and side-effect-after-selection.
- Largest base task family share: `0.10`
- Max near-duplicate cluster size: `2`
- Diversity warnings: none.

## Registry State
Before run:
- Active helpers: `prepare_reminder_creation_args`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`
- Registry path: `artifacts/registry_phaseE_portfolio/registry_manifest.json`

After run:
- Active helpers unchanged: `3`
- Active registry hash: `1aeebf43652f7e2899d018d9cc99d08285db508f2477591cf361b12bf48ce711`
- Frozen confirmation registry: `artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.json`
- Frozen registry hash: `1aeebf43652f7e2899d018d9cc99d08285db508f2477591cf361b12bf48ce711`
- Frozen registry check-only: `PASS`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Canonical mean | 0.7069 | 0.8740 | +0.1671 |
| Outcome similarity mean | 0.3015 | 0.4423 | +0.1408 |
| Exact successes | 1 | 3 | +2 |

Additional counts:
- Canonical gains / regressions / preserved: `13 / 4 / 3`
- Outcome gains / regressions / preserved: `7 / 4 / 9`
- Runtime exceptions: `0`
- Protocol gate passed: `true`

## Tools Proposed / Accepted / Rejected
- Proposed births: `4`
- Accepted births: `0`
- Rejected births: `4`

Rejected candidates:
- `select_contact_field_by_constraint`: rejected for `missing_decisive_positive_triggers`
- `select_contact_field_by_constraint`: rejected for `search_filter_missing_tie_behavior`
- `next_service_tool_call`: rejected for `missing_decisive_positive_triggers`
- `next_service_tool_call`: rejected for `missing_decisive_positive_triggers`

Interpretation: the repaired gate blocked the prior invalid service-precondition acceptance mechanism.

## Visible / Called / Adoption Summary
- Visible generated-tool scenarios: `8`
- Called generated-tool scenarios: `8`
- Visible-not-called scenarios: `0`
- Generated-tool failed scenarios: `0`
- Reuse count: `8`

Helper calls:
- `resolve_search_window_or_bounds`: `6`
- `select_record_by_timestamp_extreme`: `2`

No newly accepted tool was called because no new birth was accepted.

## Side-Effect and Runtime Analysis
- Side-effect violation count: `0`
- Side-effect report paths: none emitted for this run
- Runtime exceptions: `0`

## Route-Mismatch Note
Canonical and outcome similarity both improved. No route-mismatch-adjusted credit is claimed in this loop.

## Tool-Driven Assessment
The gain is plausibly retained-helper-driven, not new-birth-driven:
- No new tools were accepted.
- Retained helpers were visible and called in all 8 visible scenarios.
- The two called retained helpers are already claim-safe and registry-validated.

This is not yet final validation evidence because generation was on and the run was only 20 scenarios.

## Updated Shortfall / Failure Memory
- `state_precondition_gate_gap`: marked cleared for this mechanism because service-helper proposals were rejected after the repair.
- `retained_search_helpers_positive_signal`: marked `freeze_for_confirmation` because retained helpers showed adoption and outcome lift.
- `contact_selector_missing_tie_behavior`: retained as a generation-contract bottleneck.
- Failure memory records the service-precondition gate issue as cleared and records retained-search-helper confirmation as diagnostic pending frozen confirmation.

## Decision Label
freeze registry for confirmation

## Exact Next Action
Run a generation-off frozen confirmation on this 20-scenario cohort or a slightly broader 30-40 mixed cohort using `artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.json` before any larger validation.
