# V2.2 Masked-Best3 Discovery Report

## Objective

Mask the frozen best3 tools and discover new non-best3 helper candidates from remaining uncovered task space, without modifying frozen best3 evidence.

## Protected And Masked Tools

- Protected registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Masked tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`

## Cohort Design

- Main manifest: `artifacts/summaries/v2_2_masked_best3_discovery60_20260505_064113/cohort_manifest.json`
- Quality gate: `PASS`
- Structure: 20 early positives, 25 held-out reuse opportunities, 15 negative/ambiguity/no-helper cases.
- Dominant lanes were contact/message selection, side-effect prep after selection, service/state negatives, and holiday/calendar distance.

## Commands Run

- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_helper_contribution.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_output_normalization.py tests/unit/test_sage_run_adapter.py tests/unit/test_promotion_gate.py tests/unit/test_state_helper_guidance.py -q` -> `125 passed`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_masked_best3_discovery60_20260505_064113/registry_manifest.json` -> `PASS 3 entries`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_days_between_confirmation60_20260505_081500/registry_manifest.json` -> `PASS 1 entry`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json` -> `PASS 1 entry`

## Discovery And Diagnostics

| Run | Path | Quality | Outcome delta | Canonical delta | Exact | Gate | Route mismatch | Control cache |
|---|---|---:|---:|---:|---:|---:|---:|---|
| discovery | `outputs/v2_2_masked_best3_discovery60_20260505_064113/mechanism_60_20260505_064202` | pass | -0.04352382861521391 | 0.02425068870542867 | 1 -> 4 | False | False | fresh 0/60 |
| fairchance_docfix | `outputs/v2_2_masked_best3_fairchance60_docfix_20260505_064113/mechanism_60_20260505_073523` | pass | 0.022483997632954004 | 0.023760311828535715 | 2 -> 3 | False | False | mixed 6/54 |
| selector_force | `outputs/v2_2_masked_best3_selector_force60_20260505_064113/mechanism_60_20260505_070818` | pass | 0.049526331686736265 | -0.02626863476999142 | 4 -> 3 | False | True | fresh 0/60 |
| prepare_force | `outputs/v2_2_masked_prepare_side_effect_force12_20260505_062500/mechanism_12_20260505_061609` | pass | -0.036353472026174935 | -0.03561547538593101 | 0 -> 0 | False | False | fresh 0/12 |
| days_confirmation | `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108` | pass | 0.08905168905168905 | -0.05996342339399075 | 4 -> 4 | False | False | fresh 0/60 |

## Generated Candidates

| Candidate | Birth/validation result | Adoption | Outcome interpretation | Fate |
|---|---|---|---|---|
| `select_visible_record_by_constraints` | Repaired from ambiguity/tie contract failure using output normalization and generator tie guidance. | Natural `34 / 0` visible/called after routing/docstring repair. | Force-call outcome was positive, but natural adoption stayed zero. | Park until a generic actor-policy mechanism can prove natural use without forcing. |
| `prepare_side_effect_args_from_selected_record` | Accepted after side-effect preservation accounting repair. | Natural weak; force-call mixed/negative. | Side-effect incidents and negative called-subset in focused diagnostic. | Park. |
| `days_between_timestamps` | Accepted and naturally called. | Confirmation `14 / 14` visible/called. | Overall outcome `+0.0891`; called-subset outcome `+0.1071`; canonical called-subset `-0.2103`, now flagged as helper-substitution route mismatch. | Confirm as one narrow new V2.2 tool. |

## Decision Label

`new toolset has 1 confirmed tool`
