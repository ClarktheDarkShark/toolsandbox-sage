# V2.2 Candidate Callability Report

## Objective

Fairly evaluate newly generated non-best3 candidates under masked-best3 conditions, including trace inspection, callability repairs, natural/fair-call diagnostics, and route-mismatch accounting.

## Files Changed

- `scripts/build_v2_2_masked_best3_artifacts.py`
- `src/sage_ts/adapters/sage_run_adapter.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/registry/promotion_gate.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/validation/live_candidate_check.py`
- `src/sage_ts/validation/output_normalization.py`
- `src/sage_ts/validation/sandbox_validator.py`
- `src/sage_ts/evaluation/helper_contribution.py`
- `tests/unit/test_helper_contribution.py`
- `tests/unit/test_output_normalization.py`
- `tests/unit/test_promotion_gate.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_sage_run_adapter.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_tool_generator.py`

## Tests And Registry Checks

- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_helper_contribution.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_output_normalization.py tests/unit/test_sage_run_adapter.py tests/unit/test_promotion_gate.py tests/unit/test_state_helper_guidance.py -q` -> `125 passed`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_masked_best3_discovery60_20260505_064113/registry_manifest.json` -> `PASS 3 entries`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_days_between_confirmation60_20260505_081500/registry_manifest.json` -> `PASS 1 entry`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json` -> `PASS 1 entry`

## Candidate Callability Summary

| Candidate | Natural evidence | Force/fair-call evidence | Decision |
|---|---|---|---|
| `select_visible_record_by_constraints` | After routing repair: visible `34`, called `0`, VNC `34`. Natural adoption stayed zero despite output-normalization, routing availability, and docstring affordance repairs. | Force-call: visible `34`, called `29`, called-subset outcome `0.053338674217560895`, canonical `-0.00848583118386031`. Latent value exists but natural adoption remains blocked. | Park for now; deeper actor-policy intervention would risk forcing calls rather than proving autonomous adoption. |
| `prepare_side_effect_args_from_selected_record` | Natural adoption weak; docfix run visible `14`, called `1`, but prior focused force diagnostic showed mixed/negative value. | Force-call diagnostic: called subset negative and produced side-effect incidents in earlier run. | Park; side-effect-prep concept remains too brittle. |
| `days_between_timestamps` | Naturally called in discovery and fair-chance runs; confirmation visible `14`, called `14`, VNC `0`. | Confirmation called-subset outcome `0.10714285714285714`, canonical `-0.2102519581336632`, route-mismatch accounting `True`. | Confirm as narrow V2.2 calendar-distance tool; not combined until 3-tool set exists. |

## Run Metrics

| Run | Path | Quality | Outcome delta | Canonical delta | Exact | Gate | Route mismatch | Control cache |
|---|---|---:|---:|---:|---:|---:|---:|---|
| discovery | `outputs/v2_2_masked_best3_discovery60_20260505_064113/mechanism_60_20260505_064202` | pass | -0.04352382861521391 | 0.02425068870542867 | 1 -> 4 | False | False | fresh 0/60 |
| fairchance_docfix | `outputs/v2_2_masked_best3_fairchance60_docfix_20260505_064113/mechanism_60_20260505_073523` | pass | 0.022483997632954004 | 0.023760311828535715 | 2 -> 3 | False | False | mixed 6/54 |
| selector_force | `outputs/v2_2_masked_best3_selector_force60_20260505_064113/mechanism_60_20260505_070818` | pass | 0.049526331686736265 | -0.02626863476999142 | 4 -> 3 | False | True | fresh 0/60 |
| prepare_force | `outputs/v2_2_masked_prepare_side_effect_force12_20260505_062500/mechanism_12_20260505_061609` | pass | -0.036353472026174935 | -0.03561547538593101 | 0 -> 0 | False | False | fresh 0/12 |
| days_confirmation | `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108` | pass | 0.08905168905168905 | -0.05996342339399075 | 4 -> 4 | False | False | fresh 0/60 |

## Key Finding

`select_visible_record_by_constraints` is valid and visible after repairs, but the acting model still does not naturally call it. That makes it an adoption/actor-policy blocker, not a validation blocker. In contrast, `days_between_timestamps` is naturally adopted and outcome-positive, but it incurs canonical accounting loss because the helper substitutes for route-level milestone evidence.

## Decision Label

`new toolset has 1 confirmed tool`
