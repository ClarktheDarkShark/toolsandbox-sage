# V2.2 Masked-Best3 Discovery Loop 2 Report

## Objective

Continue masked-best3 discovery after confirming `days_between_timestamps`, seeking confirmed non-best3 tools #2 and #3 without modifying the frozen best3 registry or locked formal evidence.

## Protected Assets

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen best3 modified: `no`
- Masked best3 tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`
- Confirmed V2.2 tool before loop: `days_between_timestamps`
- V2.2 new-toolset registry: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`
- V2.2 new-toolset registry SHA-256: `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`

## Files Changed

- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `scripts/build_v2_2_loop2_artifacts.py`
- `tests/unit/test_openai_selector_actor_policy.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_tool_generator.py`

## Framework Repairs In This Loop

- Added bounded selector actor-policy guidance only after visible candidate records exist.
- Repaired routing so strong selector matches can receive fair exposure despite prior visible-not-called history, while harmful called-subset history still suppresses.
- Reclassified the missing-symbol stock live-validation example as negative applicability instead of positive unusable output.
- Preserved `negative_applicability` metadata through online birth into tool generation requests.
- Added derived-helper actor policy for deterministic extraction/normalization helpers after structured base-tool payloads are visible.
- Added generic trace-bridging for single-dict derived helpers so `extract_stock_symbol({})` can be autofilled from the latest matching `search_stock` payload.

## Cohort Artifacts

| Artifact | Path |
| --- | --- |
| Gap atlas | `artifacts/summaries/v2_2_loop2_20260505_164027/latest_gap_atlas.json` |
| Selector manifest | `artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_manifest.json` |
| Selector diversity | `artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_diversity_report.json` |
| Discovery60 manifest | `artifacts/summaries/v2_2_loop2_20260505_164027/discovery60_loop2_manifest.json` |
| Discovery60 diversity | `artifacts/summaries/v2_2_loop2_20260505_164027/discovery60_loop2_diversity_report.json` |
| Loop summary JSON | `artifacts/summaries/v2_2_loop2_20260505_164027/loop2_summary.json` |

## Cohort Quality

Discovery60 quality gate passed:

- Scenarios: `60`
- Distinct base task families: `20`
- Largest family share: `0.1167`
- No-current-helper-fit share: `0.80`
- Expected helper fit share: `0.20`
- Warnings: `external_service_cases_present`, `low_expected_helper_fit_share`

Selector diagnostic quality gate passed:

- Scenarios: `20`
- Distinct base task families: `10`
- Largest family share: `0.10`
- No-current-helper-fit share: `0.50`

## Commands Run

```bash
PYTHONPATH=src:. python scripts/build_v2_2_loop2_artifacts.py
PYTHONPATH=src:. OPENAI_API_KEY=<env> python scripts/run_v2_micro_experiment.py --manifest artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_manifest.json --registry artifacts/registry_candidates/v2_2_selector_actor_policy20_20260505_164027/registry_manifest.json --output-root outputs/v2_2_selector_actor_policy20_rerun_20260505_155948 --generation-mode off --control-cache use-if-eligible
PYTHONPATH=src:. OPENAI_API_KEY=<env> python scripts/run_v2_micro_experiment.py --manifest artifacts/summaries/v2_2_loop2_20260505_164027/discovery60_loop2_manifest.json --registry artifacts/registry_candidates/v2_2_masked_best3_discovery_loop2_20260505_164027/registry_manifest.json --output-root outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052 --generation-mode on --control-cache use-if-eligible --allow-contaminated-preflight
PYTHONPATH=src:. OPENAI_API_KEY=<env> SAGE_DIAGNOSTIC_FORCE_TOOL_NAME=extract_stock_symbol SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL=search_stock python scripts/run_v2_micro_experiment.py --manifest artifacts/summaries/v2_2_extract_stock_force20_20260505_170657/force20_manifest.json --registry artifacts/registry_candidates/v2_2_extract_stock_force20_20260505_170657/registry_manifest.json --output-root outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542 --generation-mode off --control-cache use-if-eligible --allow-contaminated-preflight
PYTHONPATH=src:. OPENAI_API_KEY=<env> python scripts/run_v2_micro_experiment.py --manifest artifacts/summaries/v2_2_extract_stock_force20_20260505_170657/force20_manifest.json --registry artifacts/registry_candidates/v2_2_extract_stock_force20_20260505_170657/registry_manifest.json --output-root outputs/v2_2_extract_stock_fairchance20_20260505_172237 --generation-mode off --control-cache use-if-eligible --allow-contaminated-preflight
PYTHONPATH=src:. pytest tests/unit/test_openai_selector_actor_policy.py tests/unit/test_state_helper_guidance.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q
PYTHONPATH=src:. python -m py_compile scripts/build_v2_2_loop2_artifacts.py
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json
```

## Tests and Registry Checks

- Targeted unit suite: `115 passed`
- Loop2 artifact builder compile: `PASS`
- V2.2 new-toolset registry check-only: `PASS`, `1` active entry, `0` FAIL entries

## Runs and Dashboards

| Run | Dashboard | Task Focus |
| --- | --- | --- |
| Selector diagnostic | `http://127.0.0.1:5594/outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951/dashboard/index.html` | `http://127.0.0.1:5594/outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951/dashboard/task_focus.html` |
| Discovery60 retry | `http://127.0.0.1:5596/outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056/dashboard/index.html` | `http://127.0.0.1:5596/outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056/dashboard/task_focus.html` |
| Extract-stock force after bridge | `http://127.0.0.1:5598/outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542/mechanism_40_20260505_171545/dashboard/index.html` | `http://127.0.0.1:5598/outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542/mechanism_40_20260505_171545/dashboard/task_focus.html` |
| Extract-stock fairchance | `http://127.0.0.1:5599/outputs/v2_2_extract_stock_fairchance20_20260505_172237/mechanism_40_20260505_172240/dashboard/index.html` | `http://127.0.0.1:5599/outputs/v2_2_extract_stock_fairchance20_20260505_172237/mechanism_40_20260505_172240/dashboard/task_focus.html` |

## Selector Actor-Policy Diagnostic

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951` |
| Outcome delta | `-0.0263` |
| Canonical/reference delta | `-0.0172` |
| Exact successes | `2 -> 2` |
| Runtime exceptions | `0` |
| Helper side-effect incidents | `0` |
| `select_visible_record_by_constraints` visible/called/VNC/failed | `16 / 0 / 16 / 0` |

Interpretation: routing exposure was repaired, but natural adoption stayed zero. This is not a hidden suppression bug anymore. The acting model generally used the direct base-tool result without calling the selector. Selector remains parked until a deeper actor-policy redesign is justified.

## Discovery60 Results

Initial discovery before live-example repair:

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_masked_best3_discovery_loop2_20260505_160727/mechanism_60_20260505_160731` |
| Outcome delta | `+0.0669` |
| Canonical/reference delta | `-0.0505` |
| Exact successes | `10 -> 11` |
| Accepted tools | none |
| Rejection reason | `extract_stock_symbol` rejected because missing-symbol example was incorrectly treated as positive unusable output |

Discovery retry after generation/live-validation metadata repair:

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056` |
| Outcome delta | `+0.0335` |
| Canonical/reference delta | `-0.0018` |
| Exact successes | `14 -> 11` |
| Runtime exceptions | `0` |
| Helper side-effect incidents | `0` |
| Route-mismatch qualified | `true` |
| Accepted tools | `extract_stock_symbol` |
| Accepted-but-uncalled | `extract_stock_symbol` |
| `extract_stock_symbol` visible/called/VNC/failed | `8 / 0 / 8 / 0` |

The accepted candidate passed substantive validation after the negative-applicability repair:

- Tool: `extract_stock_symbol`
- Family: `derived_value_calculator`
- Source/held-out/negative examples: `1 / 1 / 1`
- Runtime smoke: `PASS`
- Estimated step compression: `3`
- Cross-task applicability count: `2`
- Canonical route substitution risk: `low`

## Force-Call and Fair-Chance Diagnostics

Force-call after trace-bridging:

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542/mechanism_40_20260505_171545` |
| Outcome delta | `-0.1116` |
| Canonical/reference delta | `-0.0011` |
| Exact successes | `4 -> 4` |
| `extract_stock_symbol` visible/called/VNC/failed | `4 / 2 / 2 / 2` |
| Called-subset outcome delta | `-0.5000` |
| Called-subset canonical delta | `+0.0057` |

The two failed attempts were force artifacts on low-battery error paths where `search_stock` failed before a structured payload existed. Trace-bridging worked for valid `search_stock` payloads.

Natural fair-chance after derived actor policy:

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_extract_stock_fairchance20_20260505_172237/mechanism_40_20260505_172240` |
| Outcome delta | `+0.0534` |
| Canonical/reference delta | `+0.0042` |
| Exact successes | `5 -> 6` |
| Runtime exceptions | `0` |
| Helper side-effect incidents | `0` |
| `extract_stock_symbol` visible/called/VNC/failed | `4 / 4 / 0 / 0` |
| Called-subset outcome delta | `-0.0772` |
| Called-subset canonical delta | `+0.0021` |

Interpretation: the tool was given a fair chance and was called correctly. It is not blocked by callability anymore. Its called-subset outcome contribution is negative, so the concept is parked and should not be confirmed.

## Candidate Fate

| Candidate | Status | Evidence |
| --- | --- | --- |
| `select_visible_record_by_constraints` | parked | Fair exposure after routing repair, but natural calls `0 / 16`; no called-subset value. |
| `extract_stock_symbol` | parked | Valid and naturally called after trace-bridging/actor-policy repair, but called-subset outcome `-0.0772`. |

## Route-Mismatch Accounting

`extract_stock_symbol` is a deterministic derived-value helper with low canonical-route substitution risk. The framework now reports it as outcome-preserving/canonical-substituting when appropriate. In the fair-chance run, canonical was slightly positive while called-subset outcome was negative, so route-mismatch accounting does not rescue the candidate.

## Decision

No second V2.2 non-best3 tool was confirmed in Loop 2. The loop produced useful framework repairs for future candidates, but neither tested lane qualifies for confirmation60.

## Exact Next Action

Continue masked discovery only on a new non-best3, non-parked shortfall cluster. Do not run confirmation60 for `extract_stock_symbol`; do not add it to the V2.2 new-toolset registry. The next loop should avoid selector, dependency/precondition, selected-record side-effect prep, recency-action, and stock-symbol extraction unless there is materially new evidence or actor-policy design.

## Decision Label

`continue masked discovery`
