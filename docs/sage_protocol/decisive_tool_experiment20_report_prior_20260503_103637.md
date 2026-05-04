# Decisive Tool Experiment 20 Report

Date: 2026-05-03
Decision label: `needs one general gate repair`

## Objective

Run one lightweight 20-scenario generation-on experiment after adding a minimal decisive-tool gate so births are encouraged only when they claim 3+ step compression and 2+ task-family applicability.

## Files Changed

Code and tests:
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/orchestration/online_birth.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_tool_generator.py`
- `tests/unit/test_online_birth.py`

Experiment artifacts:
- `artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json`
- `artifacts/summaries/decisive_tool_experiment20/cohort_diversity_report.json`
- `artifacts/summaries/decisive_tool_experiment20/accepted_tool_validation.json`
- `artifacts/summaries/decisive_tool_experiment20/registry_manifest_after_run.json`
- `artifacts/summaries/decisive_tool_experiment20/registry_check_after_run.log`
- `artifacts/summaries/decisive_tool_experiment20/registry_check_restored.log`
- `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/`

## Cohort Diversity Summary

Manifest:
- `artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json`

Diversity report:
- `artifacts/summaries/decisive_tool_experiment20/cohort_diversity_report.json`

Summary:
- scenario count: `20`
- buckets: `5 x 4`
- largest base-family share: `0.10`
- max near-duplicate cluster size: `2`
- preflight warnings: `[]`

Buckets:
- `reminder_search_window`: 4
- `record_timestamp_extreme`: 4
- `contact_message_constraints`: 4
- `service_preconditions`: 4
- `selected_record_side_effect_prep`: 4

## Commands Run

- `PYTHONPATH=src:. pytest tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json`
- First run failed due missing shell API key:
  - `PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment20`
- Successful rerun:
  - `source .secrets/env.sh && PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode mechanism_40 --manifest artifacts/summaries/decisive_tool_experiment20/cohort_manifest.json --generation on --registry-dir artifacts/registry_phaseE_portfolio --parallel-arms -o outputs/decisive_tool_experiment20`
- Post-run registry checks:
  - `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_portfolio/registry_manifest.json`

## Output Paths

- run root: `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/`
- control run: `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/control/mechanism_40_control_agent_gpt-4o-mini_user_GPT_4_o_2024_05_13_05_03_2026_06_03_28/`
- candidate run: `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/candidate/mechanism_40_candidate_agent_gpt-4o-mini_user_GPT_4_o_2024_05_13_05_03_2026_06_03_28/`
- paired comparison: `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/paired_comparison.json`
- dashboard: `http://127.0.0.1:5520/outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/dashboard/index.html`
- task focus: `http://127.0.0.1:5520/outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/dashboard/task_focus.html`
- run log: `outputs/decisive_tool_experiment20/logs/run.log`

## Aggregate Metrics

- canonical delta: `+0.1344`
- outcome_similarity delta: `+0.1935`
- exact successes: `control=1`, `SAGE=2`
- canonical gains / regressions / preserved: `13 / 2 / 5`
- outcome gains / regressions / preserved: `6 / 3 / 11`
- runtime exceptions: `0`
- side-effect violations observed in available artifacts: `0`

## Tools Proposed / Accepted / Rejected

- proposed births: `7`
- accepted births: `2`
- rejected births: `5`

Accepted:
- `recency_to_timestamp_bounds`
- `message_search_time_window`

Rejected:
- `select_contact_field_by_constraint` x2: `missing_output_schema`
- `next_service_tool_call` x2: `missing_negative_triggers`, `missing_output_schema`
- `relative_day_time_to_timestamp` x1: `missing_downstream_tool_preservation`

## Step Compression And Applicability Claims

All 7 proposed births claimed:
- `estimated_step_compression >= 3`
- `cross_task_applicability_count >= 2`

Observed issue:
- self-reported decisive metadata was not sufficient to guarantee actual decisive value
- accepted births still skewed toward timestamp/window calculators
- rejected births showed the gate is catching claim-safety/schema gaps, but not yet filtering thin derived-value helpers aggressively enough

## Accepted Tool Validation

Validation artifact:
- `artifacts/summaries/decisive_tool_experiment20/accepted_tool_validation.json`

| Tool | Output schema | Positive triggers | Negative triggers | Held-out | Negative applicability | Runtime smoke | Experiment bar |
|---|---:|---:|---:|---:|---:|---:|---:|
| `recency_to_timestamp_bounds` | yes | yes | yes | 1 | 0 | yes | fail |
| `message_search_time_window` | yes | yes | yes | 1 | 1 | yes | pass |

Registry proof:
- Experimental 5-entry manifest passed check-only and was preserved at `artifacts/summaries/decisive_tool_experiment20/registry_manifest_after_run.json`
- Active registry was then restored to the pre-run 3-helper snapshot to avoid contaminating later phase work

## Visible / Called Counts

Retained helpers:
- `resolve_search_window_or_bounds`: visible `8`, called `6`, visible-not-called `2`
- `select_record_by_timestamp_extreme`: visible `2`, called `2`, visible-not-called `0`
- `prepare_reminder_creation_args`: visible `0`, called `0`

Accepted births:
- `recency_to_timestamp_bounds`: visible `0`, called `0`
- `message_search_time_window`: visible `2`, called `0`, visible-not-called `2`

Interpretation:
- the run improved overall
- the accepted births did not drive the improvement
- gains came from existing retained helpers plus baseline model variance on contact/service tasks

## Near-Duplicate Vs Cross-Family Performance

Bucket means:
- `contact_message_constraints`: canonical `+0.2873`, outcome `+0.6250`
- `record_timestamp_extreme`: canonical `+0.2558`, outcome `+0.2065`
- `reminder_search_window`: canonical `+0.1045`, outcome `+0.0563`
- `service_preconditions`: canonical `+0.0135`, outcome `+0.0799`
- `selected_record_side_effect_prep`: canonical `+0.0109`, outcome `+0.0000`

Interpretation:
- reminder and record gains align with already-kept helpers being called
- contact bucket gains did not come from accepted births; `select_contact_field_by_constraint` failed validation twice
- side-effect-prep scenarios exposed the strongest weakness: `message_search_time_window` was visible twice and called zero times
- cross-family reuse from new births was not demonstrated

## Recommendation For Phase C Roadmap

Do not promote either accepted birth into the kept portfolio.

One general gate repair is warranted before another experiment:
- require `applicable_task_families` to be concrete scenario-family labels, not generic helper-family labels
- require experiment-grade negative applicability evidence for all newly accepted derived-value helpers, not only current claim-safe families
- explicitly reject timestamp/window calculators that do not show downstream adoption beyond the already-kept retained helpers
- keep the next candidate focus on `select_contact_field_by_constraint` or a stronger contact/message selector, because that bucket improved materially while the generated candidate failed schema validation

## Conclusion

The experiment produced a useful signal, but not a useful new helper.

What worked:
- the lightweight gate metadata is now recorded end-to-end in tool birth events and registry specs
- the run remained stable and improved on aggregate outcome/canonical metrics
- the gate blocked several unsafe or incomplete proposals

What did not work:
- accepted births were low-value
- accepted births were not actually called
- one accepted birth failed the stronger experiment validation bar
- decisive value is still being inferred from self-reported metadata too easily
