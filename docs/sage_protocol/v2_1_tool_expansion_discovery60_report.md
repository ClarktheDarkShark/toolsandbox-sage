# V2.1 Tool Expansion Discovery60 Report

## Objective
Identify, generate, and validate 2-3 additional high-coverage candidate tools beyond frozen best3, using candidate registries only.

Frozen best3 registry was not modified: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.

## Files Changed
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/evaluation/task_strata.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `tests/unit/test_task_strata.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_state_helper_guidance.py`

## Framework Changes
- Added shortfall observations for visible-record constraint selection, recency/action target selection, and post-selection side-effect argument preparation.
- Added task-strata helper triggers and expected birth opportunities for the three V2.1 lanes.
- Strengthened generator guidance for selectors, recency action-target helpers, and post-selection side-effect preparers.
- Fixed generic runtime routing for composite helpers that return one `downstream_tool_name`: routing now requires any compatible downstream original tool, not every preserved tool.
- Added generic post-selection docstring affordance for composite helpers.
- Added safe missing-argument abstention for generated dict-output helpers with `abstain_reason`, so omitted required helper inputs return a structured abstain instead of a `TypeError`.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_state_helper_guidance.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_online_birth.py -q` -> `70 passed`
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_state_helper_guidance.py -q` -> `95 passed`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json` -> `PASS`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835/registry_manifest.json` -> `PASS`

## Cohort
- Manifest: `artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_diversity_report.json`
- Cohort quality: `PASS`
- Scenarios: `60`
- Distinct base task families: `20`
- Largest family share: `0.10`
- No-current-helper-fit share: `0.25`
- Main lanes: contact/message constraints, reminder/contact recency action workflows, search-plus-selection, side-effect prep, negatives/ambiguity.

## Commands Run
Best3-only:
```bash
OPENAI_API_KEY=$KEY PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_frozen_best3_claim --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_tool_expansion_best3_60_20260504_191835
```

Discovery:
```bash
SAGE_V2_EXPERIMENT_FEATURES=candidate_repair,contract_synthesis,evidence_routing,grading_accounting,live_validation OPENAI_API_KEY=$KEY PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835 --generation on --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_tool_expansion_discovery60_run_20260504_191835
```

Force diagnostics:
```bash
SAGE_DIAGNOSTIC_FORCE_TOOL_NAME=prepare_side_effect_args_from_selected_record SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL=select_record_by_timestamp_extreme OPENAI_API_KEY=$KEY PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/force_prepare_side_effect_args12_20260504_194436/cohort_manifest.json --mode mechanism_12 --registry-dir artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835 --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_tool_expansion_force_prepare_args12_abstain_20260504_201500
```

## Run Outputs
| Arm | Output | Dashboard |
|---|---|---|
| Best3 only | `outputs/v2_1_tool_expansion_best3_60_20260504_191835/mechanism_60_20260504_191910` | `outputs/v2_1_tool_expansion_best3_60_20260504_191835/mechanism_60_20260504_191910/dashboard/index.html` |
| Discovery | `outputs/v2_1_tool_expansion_discovery60_run_20260504_191835/mechanism_60_20260504_192907` | `outputs/v2_1_tool_expansion_discovery60_run_20260504_191835/mechanism_60_20260504_192907/dashboard/index.html` |
| Force after routing fix | `outputs/v2_1_tool_expansion_force_prepare_args12_routefix_20260504_195000/mechanism_12_20260504_195210` | `outputs/v2_1_tool_expansion_force_prepare_args12_routefix_20260504_195000/mechanism_12_20260504_195210/dashboard/index.html` |
| Force after abstain fix | `outputs/v2_1_tool_expansion_force_prepare_args12_abstain_20260504_201500/mechanism_12_20260504_200720` | `outputs/v2_1_tool_expansion_force_prepare_args12_abstain_20260504_201500/mechanism_12_20260504_200720/dashboard/index.html` |

Dashboards were opened by the runner for each run.

## Metrics
| Arm | Outcome Delta | Canonical Delta | Exact Successes | Outcome Gains/Regressions/Preserved | Runtime | Side Effects | Control Cache |
|---|---:|---:|---:|---:|---:|---:|---|
| Best3 only | `+0.1543` | `+0.0527` | `6 -> 10` | `22 / 9 / 24` | `0` | `0` | fresh, `0 cached / 60 fresh` |
| Discovery | `+0.1586` | `+0.1377` | `2 -> 9` | `20 / 9 / 26` | `0` | `0` | fresh, `0 cached / 60 fresh` |
| Force after abstain fix | `+0.2745` | `+0.2039` | `0 -> 2` | `5 / 4 / 3` | `0` | `0` | fresh, `0 cached / 12 fresh` |

Discovery aggregate was slightly above best3, but the new accepted candidate was naturally uncalled. The aggregate difference is therefore not claim-grade evidence for the new tool.

## Tool Birth Results
- Proposed/birth attempts: `5`
- Accepted: `prepare_side_effect_args_from_selected_record`
- Rejected: `select_visible_record_by_constraints` twice; `select_action_target_by_recency` twice
- Accepted-but-uncalled: `prepare_side_effect_args_from_selected_record`

Rejection reasons were substantive implementation/validation failures rather than missing basic contract fields:
- `select_visible_record_by_constraints`: positive example returned no record; tie negative selected a record instead of abstaining.
- `select_action_target_by_recency`: exact-output mismatches for tie candidates / selected id; later live validation hit `NameError: name 'all' is not defined`.

## Helper Contribution
| Helper | Discovery Visible / Called / VNC / Failed | Called-Subset Outcome Delta | Notes |
|---|---:|---:|---|
| `relative_day_time_to_timestamp` | `6 / 6 / 0 / 0` | `+0.4000` | best3 contribution |
| `resolve_search_window_or_bounds` | `20 / 6 / 14 / 0` | `+0.4096` | best3 contribution |
| `select_record_by_timestamp_extreme` | `21 / 14 / 7 / 0` | `+0.4472` | best3 contribution |
| `prepare_side_effect_args_from_selected_record` | `2 / 0 / 2 / 0` | n/a | accepted but naturally uncalled |

Force after missing-argument abstain repair:
- `prepare_side_effect_args_from_selected_record`: visible/called/VNC/failed `12 / 8 / 4 / 0`
- All observed calls returned `abstain_reason=missing_required_helper_inputs` because the model still did not provide `selected_record` and `updates`.
- The called-subset lift is confounded with co-called best3 helpers and is not evidence that this candidate itself added value.

## Interpretation
The V2.1 framework can now surface the right high-value lanes and produce accepted cluster-born candidates, but the generated tool contracts are still not model-callable enough for selection/action workflows. The best3 portfolio remains strong on this lane, while new candidates either fail exact validation or require inputs the acting model does not naturally have in callable form.

## Decision Label
`generation contract repair needed`

## Exact Next Action
Repair the generator/validator so selector and post-selection candidates use simpler callable inputs or explicit two-step selector outputs that the acting model can pass without constructing opaque records manually. Add live validation that requires a generated helper to produce non-abstain output on at least one positive model-callable example before another 60-scenario discovery.
