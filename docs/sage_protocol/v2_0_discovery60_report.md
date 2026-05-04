# SAGE V2.0 Discovery-60 Report

## Objective
Run a quality-gated discovery-60 with generation ON, frozen best3 copied into a separate candidate registry, and candidate births driven by Phase 1 shortfall clusters.

## Files Changed
- `artifacts/summaries/v2_0_discovery60_20260504_081357/cohort_manifest.json`
- `artifacts/summaries/v2_0_discovery60_20260504_081357/cohort_diversity_report.json`
- `artifacts/summaries/v2_0_discovery60_20260504_081357/discovery_summary.json`
- `artifacts/registry_candidates/v2_0_discovery60_20260504_081357/registry_manifest.json` (restored to best3 after failed protocol gate)
- `docs/sage_protocol/v2_0_discovery60_report.md`
- `docs/sage_protocol/v2_0_candidate_triage_report.md`
- `docs/sage_protocol/v2_0_confirmation60_report.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Commands Run
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_0_discovery60_20260504_081357/registry_manifest.json`
- `python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_0_discovery60_20260504_081357/cohort_manifest.json --mode mechanism_40 --registry-dir artifacts/registry_candidates/v2_0_discovery60_20260504_081357 --output-root outputs/v2_0_discovery60_20260504_081357 --artifact-root artifacts --agent gpt-4o-mini --user gpt-4o-mini --generation-model gpt-4o-mini --generation on --parallel-arms --control-cache use-if-eligible`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_0_discovery60_20260504_081357/registry_manifest.json`

## Cohort Quality
- Manifest: `artifacts/summaries/v2_0_discovery60_20260504_081357/cohort_manifest.json`
- Run root: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640`
- Quality gate: `pass`
- Quality failures: `[]`
- Distinct base families: `27`
- Largest family share: `0.1`
- No-current-helper-fit share: `0.31666666666666665`
- External contamination: `0`

## Dashboards
- Main: http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/index.html
- Task focus: http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/task_focus.html
- Both returned HTTP 200 and were opened.

## Registry
- Frozen best3 source: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Candidate registry: `artifacts/registry_candidates/v2_0_discovery60_20260504_081357/registry_manifest.json`
- Frozen best3 modified: no
- Candidate registry was restored after failed protocol gate: yes
- Failed-gate candidate snapshot: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/registry_gate/registry_manifest_failed_gate.json`

## Control Cache
- Source: `fresh`
- Cached control tasks: `0`
- Fresh control tasks: `60`
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Collected control records: `60`

## Metrics
- Scenario count: `60`
- Outcome: control `0.4339`, SAGE `0.4354`, delta `0.0015`
- Canonical/reference: control `0.6896`, SAGE `0.7185`, delta `0.0289`
- Exact successes: control `4`, SAGE `2`, delta `-2`
- Canonical gains/regressions/preserved: `21` / `21` / `18`
- Outcome gains/regressions/preserved: `19` / `16` / `21`
- Runtime exceptions: `0`
- Route-mismatch-qualified: `True`
- Protocol gate: `False`
- Protocol gate reasons: `['confirmation_outcome_delta_below_0_08', 'gain_regression_ratio_below_1_4', 'helper_call_share_below_25_percent']`

## Tool Birth Results
| canonical key | attempts | accepted | tools | errors | repair attempts |
|---|---:|---:|---|---|---:|
| `state_precondition:next_service_tool_call` | 2 | 0 | `next_service_tool_call` | `unresolved_failure_memory:state_precondition_visible_not_called` | 2 |
| `state_precondition:dependency_precondition_tool_call` | 1 | 1 | `next_dependency_precondition_call` | none | 0 |
| `composite:prepare_reminder_creation_args` | 1 | 0 | `prepare_reminder_creation_args` | `live_missing_expected_milestone_calls_replaced` | 1 |
| `search_filter:select_contact_field_by_constraint` | 2 | 0 | `select_contact_field_by_constraint` | `live_missing_expected_milestone_calls_replaced` | 2 |
| `derived_value:days_between_timestamps` | 2 | 0 | `days_between_timestamps` | `live_example_2_positive_unusable_output`, `live_missing_expected_milestone_calls_replaced` | 2 |

## Helper Contribution
| helper | origin | visible | called | visible-not-called | called outcome delta | called canonical delta | side-effect incidents | runtime incidents |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `next_dependency_precondition_call` | newly_generated | 2 | 0 | 2 | None | None | 0 | 0 |
| `relative_day_time_to_timestamp` | retained | 6 | 5 | 1 | 0.0 | -0.2 | 0 | 0 |
| `resolve_search_window_or_bounds` | retained | 0 | 0 | 0 | None | None | 0 | 0 |
| `select_record_by_timestamp_extreme` | retained | 14 | 9 | 5 | -0.040806581606512245 | 0.13458472732364618 | 0 | 0 |

## Interpretation
- The run produced one valid cluster-born candidate, `next_dependency_precondition_call`, but it was accepted-but-uncalled: visible on 2 later scenarios, called 0 times. That is not promotion evidence.
- The run did not show broad additive improvement over best3: outcome delta was effectively flat at `+0.0015`; exact successes decreased `4 -> 2`; canonical/reference improved `+0.0289`.
- The result is route-mismatch-qualified because canonical improved and outcome was slightly positive despite the protocol gate failing, but this is not a validation pass.
- The dominant blocker is adoption/routing for the accepted dependency helper. Secondary blocker: generation/live-validation contract still rejects contact, reminder, and holiday candidates for missing grading-accounting metadata such as `expected_milestone_calls_replaced`.
- Side-effect and runtime safety were clean.

## Decision Label
`routing repair needed`

## Next Action
Repair routing/affordance for cluster-born dependency helpers and repair the generated-tool grading-accounting contract that causes `live_missing_expected_milestone_calls_replaced`, then rerun a focused fair-chance diagnostic before confirmation-60.
