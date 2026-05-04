# Decisive Tool Experiment 20 Broad Rerun

## Files Changed
- `src/sage_ts/adequacy/candidate_gate.py`
- `tests/unit/test_candidate_gate.py`
- `artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json`
- `artifacts/summaries/decisive_tool_experiment20/cohort_diversity_report.json`
- `artifacts/summaries/decisive_tool_experiment20/summary.json`
- `artifacts/summaries/failure_memory.json`
- `artifacts/summaries/shortfall_clusters/latest_shortfall_clusters.json`
- `docs/sage_protocol/decisive_tool_experiment20_report.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Cohort Diversity Summary
- Scenario count: `20`
- Bucket counts: `{'reminder_search_window_or_optional_location': 4, 'record_message_latest_oldest_selection': 4, 'contact_message_constraint_selection': 4, 'service_precondition_sequencing': 4, 'side_effect_preparation_after_selected_record': 4}`
- Largest family share: `0.1`
- Max cluster size: `2`
- Warnings: `[]`

## Command Run
```bash
PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment20_broad_rerun
```

## Output Paths
- Run root: `outputs/decisive_tool_experiment20_broad_rerun/mechanism_40_20260503_102645`
- Dashboard: `outputs/decisive_tool_experiment20_broad_rerun/mechanism_40_20260503_102645/dashboard/index.html`
- Task focus dashboard: `outputs/decisive_tool_experiment20_broad_rerun/mechanism_40_20260503_102645/dashboard/task_focus.html`
- Summary: `artifacts/summaries/decisive_tool_experiment20/summary.json`
- Diagnostic candidate registry: `artifacts/registry_candidates/decisive_tool_experiment20_broad_rerun/registry_manifest.json`
- Active registry restored: `artifacts/registry_phaseE_portfolio/registry_manifest.json`

## Tools Proposed / Accepted / Rejected
- Proposed: `4`
- Accepted: `1`
- Rejected: `3`
- `select_contact_field_by_constraint`: accepted=`False`, family=`search_filter_ranking_helper`, step_compression=`3`, cross_task=`2`, families=`['search_relationship_with_phone_number', 'search_relationship_with_name']`, errors=`['search_filter_missing_tie_behavior']`
- `select_contact_field_by_constraint`: accepted=`False`, family=`search_filter_ranking_helper`, step_compression=`3`, cross_task=`2`, families=`['search_name_with_relationship', 'search_contact_by_phone']`, errors=`['search_filter_missing_tie_behavior']`
- `next_service_tool_call`: accepted=`True`, family=`state_precondition_helper`, step_compression=`3`, cross_task=`3`, families=`['enable_wifi_service', 'enable_cellular_service', 'enable_location_service']`, errors=`[]`
- `relative_day_time_to_timestamp`: accepted=`False`, family=`canonicalizer`, step_compression=`3`, cross_task=`2`, families=`['modify_reminder_with_recency_latest_alt', 'schedule_event_with_recency']`, errors=`['denied_node:Import']`

## Decisive Metadata Checks
- Tools meeting 3+ step compression: `['select_contact_field_by_constraint', 'select_contact_field_by_constraint', 'next_service_tool_call', 'relative_day_time_to_timestamp']`
- Tools applying to 2+ task families: `['select_contact_field_by_constraint', 'select_contact_field_by_constraint', 'next_service_tool_call', 'relative_day_time_to_timestamp']`
- Accepted tool post-run validation: `{'output_schema_present': True, 'positive_triggers_present': False, 'negative_triggers_present': True, 'held_out_check_count_gte_1': True, 'negative_applicability_count_gte_1': True, 'runtime_smoke_passed': True, 'check_only_passes_after_gate_repair': False, 'side_effect_replacement_or_preservation_failure': True}`

## Visible / Called Counts
- Visible generated tools: `['next_service_tool_call', 'resolve_search_window_or_bounds', 'select_record_by_timestamp_extreme']`
- Visible scenarios: `10`
- Called scenarios: `9`
- Visible-not-called: `1`
- Helper call counts: `{'next_service_tool_call': 1, 'resolve_search_window_or_bounds': 6, 'select_record_by_timestamp_extreme': 2}`
- Reused tools: `['next_service_tool_call', 'resolve_search_window_or_bounds', 'select_record_by_timestamp_extreme']`

## Metrics
- Outcome similarity delta: `+0.017078`
- Canonical delta: `+0.103566`
- Exact successes: control=`0`, SAGE=`2`
- Canonical gains/regressions/preserved: `10` / `6` / `4`
- Outcome gains/regressions/preserved: `6` / `7` / `7`
- Runtime exceptions: `0`

## Near-Duplicate vs Cross-Family Performance
- `reminder_search_window_or_optional_location`: n=`4`, outcome delta=`+0.1109`, canonical delta=`+0.2013`, outcome g/r/p=`3/1/0`
- `record_message_latest_oldest_selection`: n=`4`, outcome delta=`+0.2640`, canonical delta=`+0.4979`, outcome g/r/p=`2/2/0`
- `contact_message_constraint_selection`: n=`4`, outcome delta=`+0.0109`, canonical delta=`-0.1267`, outcome g/r/p=`1/0/3`
- `service_precondition_sequencing`: n=`4`, outcome delta=`-0.0944`, canonical delta=`-0.0112`, outcome g/r/p=`0/2/2`
- `side_effect_preparation_after_selected_record`: n=`4`, outcome delta=`-0.2060`, canonical delta=`-0.0435`, outcome g/r/p=`0/2/2`

## Side-Effect Violations
- Side-effect preservation rows: `[{'generated_tools_called': ['next_service_tool_call'], 'scenario': 'turn_on_wifi_low_battery_mode', 'side_effect_preservation_failures': ['next_service_tool_call']}]`
- The accepted `next_service_tool_call` failed side-effect preservation in `turn_on_wifi_low_battery_mode`.
- Root cause: it could emit `set_low_battery_mode_status` but did not list that setter in preserved/required original calls.

## Interpretation
The broad run shows useful retained-helper signal, especially in reminder/search-window and message latest/oldest families. However, the only newly accepted generated tool is not valid under the stricter post-run checks: it had no positive triggers and caused a side-effect preservation failure. Active registry was restored to the 3 claim-safe helpers; the 4-tool post-run registry is retained only as diagnostic evidence.

A minimal gate repair was applied after the run and tested: decisive candidates now require positive triggers, and state-precondition helpers must preserve and require every setter they can emit. Under this repaired gate, the diagnostic candidate registry fails as expected.

## Recommendation for Phase C Roadmap
- Keep the 3 active helpers frozen for claim-safe work.
- Do not promote `next_service_tool_call`.
- Rerun this same 20-scenario discovery after the gate repair if more discovery evidence is needed.
- Continue a separate contact-selector generation repair for explicit tie/ambiguity behavior.

## Decision Label
needs one general gate repair
