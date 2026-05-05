# V2.1 Gap Closure Discovery60 Report

## Objective
Build a V2.1 gap atlas from remaining no-current-helper-fit and regression evidence, then run a quality-gated discovery60 focused on selection/action, visible-record constraint selection, and side-effect argument preparation after selection.

## Files changed
- `scripts/build_v2_1_gap_closure_artifacts.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_tool_generator.py`
- `tests/unit/test_state_helper_guidance.py`

## Artifacts
- Gap atlas: `artifacts/summaries/v2_1_gap_closure_20260504_221814/gap_atlas.json`
- Discovery manifest: `artifacts/summaries/v2_1_gap_closure_20260504_221814/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_1_gap_closure_20260504_221814/cohort_diversity_report.json`
- Discovery candidate registry: `artifacts/registry_candidates/v2_1_gap_closure_discovery60_20260504_221814/registry_manifest.json`
- Diagnostic candidate registry: `artifacts/registry_candidates/v2_1_gap_closure_force_prepare_side_effect_args12_20260504_2230/registry_manifest.json`
- Machine summary: `artifacts/summaries/v2_1_gap_closure_final/run_summary.json`

## Cohort quality
- Discovery60 scenarios: `60`
- Cohort quality: `PASS`
- Distinct base task families: `15`
- Largest family share: `0.1333`
- No-current-helper-fit share: `0.4167`
- Main lanes: `select_visible_record_by_constraints`, `prepare_side_effect_args_from_selected_record`, negative/no-helper cases.

## Commands run
```bash
python scripts/build_v2_1_gap_closure_artifacts.py --timestamp 20260504_221814
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_1_gap_closure_discovery60_20260504_221814/registry_manifest.json
SAGE_V2_EXPERIMENT_FEATURES=candidate_repair,contract_synthesis,evidence_routing,grading_accounting,live_validation python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_gap_closure_20260504_221814/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_candidates/v2_1_gap_closure_discovery60_20260504_221814 --generation on --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_gap_closure_discovery60_20260504_221814
PYTHONPATH=src:. pytest tests/unit/test_state_helper_guidance.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_candidate_gate.py -q
```

## Discovery60 result
- Run: `outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901/dashboard/task_focus.html`
- Control cache: `fresh`, cached `0`, fresh `60`
- Outcome delta: `0.0088`
- Canonical delta: `-0.0101`
- Exact successes: `3 -> 3`
- Runtime exceptions: `0`
- Protocol gate: `False`
- Gate reasons: `['outcome_gains_do_not_exceed_regressions', 'non_positive_canonical_delta', 'confirmation_outcome_delta_below_0_08', 'exact_successes_not_improved', 'gain_regression_ratio_below_1_4', 'helper_call_share_below_25_percent']`

## Tool birth and adoption
- Proposed/rejected: `select_visible_record_by_constraints` was rejected after live validation for `live_example_2_negative_not_abstained`. This is a substantive safety rejection, not a missing-field contract failure after the phone/name normalization repair.
- Accepted: `prepare_side_effect_args_from_selected_record`.
- Accepted helper natural contribution in discovery60: visible/called/VNC `27 / 0 / 27`; called-subset outcome `None`; visible-not-called outcome `0.0323`.
- Accepted-but-uncalled: `prepare_side_effect_args_from_selected_record`.

## Repairs made during this loop
- Strengthened generated visible-record selector contract to normalize both record values and expected values, including phone-number digit normalization.
- Added generic routing suppression for side-effect-preserving helpers on insufficient-information tasks.
- Added selected-record autofill from the latest original `search_*` trace only when the result is exactly one visible record.
- Added generic routing hard-block override so provisional stratum visibility cannot overrule negative/insufficient/post-selection action suppressions.
- Added generation guidance to prefer low-friction composite helper inputs instead of selected-record-only contracts when the intended call point is immediately after search.

## Interpretation
The gap atlas identified real uncovered selection/action lanes, but the discovery60 did not produce a promotion-grade new tool. `prepare_side_effect_args_from_selected_record` was accepted but not naturally adopted. That is not successful tool evolution.

Decision label: `candidate parked`
