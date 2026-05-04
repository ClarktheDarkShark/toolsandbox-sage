# Decisive Tool Experiment 20/40 v2 Report

Date: 2026-05-03
Decision label: `useful decisive-tool signal`

## Objective

Repeat and expand the decisive-tool generation experiment after the prior 20-run showed positive aggregate lift but accepted low-value generated tools with zero calls. This v2 run tests whether the repaired framework works at 20 scenarios and still holds at 40 scenarios.

## What Changed In The Framework

- Added a stricter decisive-gate check for generated tools with decisive metadata.
- Rejected generic `applicable_task_families` labels such as `canonicalizer`, `state_precondition_helper`, and `timestamp_conversion`.
- Required decisive generated tools to include negative triggers and dict output schemas when returning dicts.
- Required derived-value decisive helpers to preserve a real downstream ToolSandbox tool path such as `search_*`, `modify_*`, `send_*`, `set_*`, or `add_*`.
- Kept active registry fixed at the three baseline helpers before each run, then preserved post-run registries separately.

## Files Changed

- `src/sage_ts/adequacy/candidate_gate.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_online_birth.py`

## Artifacts

- 20 manifest: `artifacts/summaries/decisive_tool_experiment20_v2/cohort_manifest.json`
- 20 diversity: `artifacts/summaries/decisive_tool_experiment20_v2/cohort_diversity_report.json`
- 20 run: `outputs/decisive_tool_experiment20_v2/mechanism_40_20260503_083141`
- 40 manifest: `artifacts/summaries/decisive_tool_experiment40_v2/cohort_manifest.json`
- 40 diversity: `artifacts/summaries/decisive_tool_experiment40_v2/cohort_diversity_report.json`
- 40 run: `outputs/decisive_tool_experiment40_v2/mechanism_40_20260503_083555`
- combined summary: `artifacts/summaries/decisive_tool_experiment20_40_v2/summary.json`
- accepted validation: `artifacts/summaries/decisive_tool_experiment20_40_v2/accepted_tool_validation.json`

## Commands Run

- `PYTHONPATH=src:. pytest tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json`
- `source .secrets/env.sh && PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment20_v2/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment20_v2`
- `source .secrets/env.sh && PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment40_v2/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment40_v2`

## Cohort Design

| Run | Scenarios | Buckets | Largest family share | Max cluster size | Warnings |
|---|---:|---|---:|---:|---|
| `20_v2` | 20 | reminder_search_window=4, record_timestamp_extreme=4, contact_message_constraints=4, service_preconditions=4, selected_record_side_effect_prep=4 | 0.10 | 2 | `[]` |
| `40_v2` | 40 | reminder_search_window=8, record_timestamp_extreme=8, contact_message_constraints=8, service_preconditions=8, selected_record_side_effect_prep=8 | 0.10 | 2 | `[]` |

Buckets used in both runs:
- `reminder_search_window`
- `record_timestamp_extreme`
- `contact_message_constraints`
- `service_preconditions`
- `selected_record_side_effect_prep`

## Headline Metrics

| Run | Canonical delta | Outcome delta | Exact successes | Outcome successes | Canonical G/R/P | Outcome G/R/P | Runtime exceptions |
|---|---:|---:|---|---|---|---|---:|
| `20_v2` | +0.1770 | +0.1285 | 0 -> 2 | 2 -> 5 | 14 / 5 / 1 | 6 / 4 / 10 | 0 |
| `40_v2` | +0.1239 | +0.1830 | 1 -> 4 | 3 -> 10 | 24 / 9 / 7 | 17 / 12 / 11 | 0 |

Interpretation: the framework-level lift replicated from 20 to 40. The 40-run retained positive outcome lift and positive canonical lift while exact successes improved from `1` to `4`.

## Birth Results

| Run | Proposed | Accepted | Rejected | Accepted tools |
|---|---:|---:|---:|---|
| `20_v2` | 8 | 1 | 7 | `message_search_time_window` |
| `40_v2` | 9 | 1 | 8 | `message_search_time_window` |

Rejected patterns:
- `20_v2`: `generic_applicable_task_family`=1, `missing_downstream_original_tool_call`=2, `missing_negative_triggers`=1, `missing_output_schema`=3
- `40_v2`: `generic_applicable_task_family`=1, `insufficient_applicable_task_families`=1, `missing_downstream_original_tool_call`=2, `missing_negative_triggers`=1, `missing_output_schema`=3

Key gate result: `recency_to_timestamp_bounds` was rejected in both runs with `missing_downstream_original_tool_call`, which fixes the prior false-positive acceptance pattern.

## Accepted Tool Adoption

| Run | Tool | Visible | Called | Adoption rate | Validation bar |
|---|---|---:|---:|---:|---|
| `20_v2` | `message_search_time_window` | 2 | 1 | 0.500 | `False` |
| `40_v2` | `message_search_time_window` | 8 | 1 | 0.125 | `False` |

Interpretation: `message_search_time_window` passes registry proof but should not be promoted. Its adoption dropped from `1/2` visible cases at 20 to `1/8` at 40.

## Retained Helper Adoption

| Run | Helper | Visible | Called | Visible-not-called |
|---|---|---:|---:|---:|
| `20_v2` | `resolve_search_window_or_bounds` | 8 | 6 | 2 |
| `20_v2` | `select_record_by_timestamp_extreme` | 2 | 2 | 0 |
| `40_v2` | `resolve_search_window_or_bounds` | 16 | 12 | 4 |
| `40_v2` | `select_record_by_timestamp_extreme` | 4 | 4 | 0 |

What is working: `select_record_by_timestamp_extreme` scaled cleanly with no visible-not-called cases. `resolve_search_window_or_bounds` continued to be used heavily, though still with some non-calls.

## Bucket Performance

### 20_v2

| Bucket | Mean canonical delta | Mean outcome delta | Canonical gains/regressions | Outcome gains/regressions |
|---|---:|---:|---|---|
| `contact_message_constraints` | +0.1751 | +0.3657 | 3 / 1 | 2 / 0 |
| `record_timestamp_extreme` | +0.5010 | +0.2490 | 4 / 0 | 2 / 1 |
| `reminder_search_window` | +0.2060 | -0.0486 | 4 / 0 | 1 / 2 |
| `selected_record_side_effect_prep` | +0.0237 | +0.0000 | 2 / 1 | 0 / 0 |
| `service_preconditions` | -0.0210 | +0.0763 | 1 / 3 | 1 / 1 |

### 40_v2

| Bucket | Mean canonical delta | Mean outcome delta | Canonical gains/regressions | Outcome gains/regressions |
|---|---:|---:|---|---|
| `contact_message_constraints` | -0.0722 | +0.2387 | 3 / 4 | 2 / 2 |
| `record_timestamp_extreme` | +0.4411 | +0.1976 | 7 / 0 | 4 / 3 |
| `reminder_search_window` | +0.2503 | +0.3653 | 8 / 0 | 6 / 2 |
| `selected_record_side_effect_prep` | -0.0108 | +0.0477 | 3 / 2 | 2 / 2 |
| `service_preconditions` | +0.0113 | +0.0657 | 3 / 3 | 3 / 3 |

## Conclusions

What worked:
- The repaired gate blocked the prior low-value recency/timestamp helper.
- The 20-run lift replicated at 40 on both outcome and canonical metrics.
- Existing record-selection and search-window helpers remain the strongest evidence-backed mechanisms.
- Contact/message constraints remain promising on outcome, but the generated contact selector is still failing schema validation.

What did not work:
- The only accepted new birth, `message_search_time_window`, was not adopted enough to count as useful reuse.
- Service-precondition births still fail validation because generated specs omit negative triggers or output schema.
- Side-effect-prep cases remain weak; the framework needs a selector/preparation helper that is actually called downstream.

What might be working:
- The approach of rejecting thin timestamp helpers while preserving retained helper routing appears stable from 20 to 40.
- The contact/message lane is still worth a targeted schema/affordance repair because outcome lift appears in both 20 and 40 despite failed generated selector births.
- Service-precondition tooling may be viable only after the generation prompt forces the exact output contract and negative triggers.

## Recommendation

Do not promote `message_search_time_window`. Keep the active registry at the restored three-helper baseline.

Next best move: make one targeted generation-prompt/schema repair for `select_contact_field_by_constraint` and `next_service_tool_call` output contracts, then rerun a 20-scenario diagnostic focused on those two families before any broader validation.

## Registry State

- 20 post-run registry preserved: `artifacts/summaries/decisive_tool_experiment20_v2/registry_manifest_after_run.json`
- 40 post-run registry preserved: `artifacts/summaries/decisive_tool_experiment40_v2/registry_manifest_after_run.json`
- Active registry restored: `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- Active registry check-only: PASS, 3 active entries
