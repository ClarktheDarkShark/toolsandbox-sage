# V2 Tool Adoption Diagnosis Report

## Objective
Diagnose why generated tools were visible but not called, repair framework-level adoption blockers, and rerun fair-chance confirmation so late-born tools are evaluated with sufficient opportunity.

## Files Changed
- `src/sage_ts/runtime/toolsandbox_integration.py`
  - Added downstream original-tool availability routing guard.
  - Fixed generic helper docstrings so non-reminder helpers describe actual output fields and downstream ToolSandbox calls.
  - Added positive/negative trigger guidance to generated helper docstrings.
- `src/sage_ts/adapters/sage_run_adapter.py`
  - Passes current scenario base-tool availability into runtime routing.
- `tests/unit/test_runtime_routing_scorer.py`
  - Covers hiding helpers when downstream original tools are unavailable.
- `tests/unit/test_state_helper_guidance.py`
  - Covers non-reminder helper docstrings and prevents reminder-specific affordance leakage.
- `scripts/run_v2_fair_chance_confirmation20.py`
  - Runs frozen generation-OFF confirmation from accepted discovery registries so late-born tools are available from turn 1.

## Adoption Failure Mechanisms Found
1. Late birth undercounting.
   - A helper born during a scenario cannot help that same scenario.
   - Same-cohort generation-ON metrics understate tool value unless followed by frozen confirmation.

2. Runtime overexposure.
   - Before repair, `message_search_time_window` was exposed on add-contact, holiday, and contact-only tasks even though it declares `search_messages` as the downstream original tool.
   - Fix: route helpers only when declared downstream original ToolSandbox tools are available.

3. Bad helper affordance.
   - Generic non-reminder docstrings incorrectly referenced `should_call_add_reminder` and `<tool>_kwargs` call paths.
   - This made helpers look irrelevant or unsafe to call.
   - Fix: docstrings now list actual output-schema fields and say to pass those fields into the declared downstream original tool.

4. Base-tool first tendency.
   - The model often tries direct base-tool calls before helpers when the base path looks plausible.
   - In `modify_contact_with_message_recency`, it called `search_messages` directly and got stuck.
   - After docstring repair and frozen replay, the helper was called on that previously missed simple case.

5. Over-broad stacks suppress value.
   - Combined stack retained too many overlapping tools and produced high visible-not-called counts.
   - Narrow `contract_synthesis` performed best.

## Focused Replay Verification
- Manifest: `artifacts/summaries/v2_tool_adoption_replay2/cohort_manifest.json`
- Registry: `artifacts/registry_candidates/v2_tool_adoption_replay2/registry_manifest.json`
- Run: `outputs/v2_tool_adoption_replay2/mechanism_40_20260503_225947/`
- Dashboards:
  - `outputs/v2_tool_adoption_replay2/mechanism_40_20260503_225947/dashboard/index.html`
  - `outputs/v2_tool_adoption_replay2/mechanism_40_20260503_225947/dashboard/task_focus.html`
- Generation: OFF
- Purpose: explicit 2-case adoption diagnostic, not claim-grade.
- Result: protocol PASS.
- Canonical delta: `+0.2109`
- Outcome delta: `+0.0000`
- Helper visible/called/VNC: `2 / 1 / 1`
- Called scenario: `modify_contact_with_message_recency`
- Side-effect/runtime incidents: `0 / 0`

## Fair-Chance Confirmation-20
- Script: `scripts/run_v2_fair_chance_confirmation20.py`
- Summary: `artifacts/summaries/v2_fair_chance_confirmation20/confirmation_summary.json`
- Manifest: `artifacts/summaries/v2_fair_chance_confirmation20/cohort_manifest.json`
- Generation: OFF
- Purpose: freeze each variant's accepted tools and rerun the same quality-gated 20-task cohort with tools available from turn 1.

| Variant | Outcome Delta | Canonical Delta | Exact C/S | Helper V/C/VNC | Called Tools | Sidefx | Runtime | Gate |
|---|---:|---:|---:|---:|---|---:|---:|---|
| `variant0_current_v2_baseline` | `+0.0052` | `+0.0870` | `1/2` | `10/4/6` | `recency_to_timestamp_bounds` | `0` | `0` | PASS |
| `variant1_grading_accounting` | `-0.0207` | `-0.0214` | `2/2` | `13/6/7` | `message_search_time_window`, `recency_to_timestamp_bounds` | `0` | `0` | FAIL |
| `variant2_dependency_logic` | `-0.0141` | `-0.0188` | `1/0` | `4/1/3` | `message_search_time_window` | `0` | `0` | FAIL |
| `variant4_candidate_repair` | `+0.0534` | `-0.0425` | `2/2` | `4/2/2` | `message_search_time_window` | `0` | `0` | FAIL |
| `variant5_contract_synthesis` | `+0.0617` | `+0.0979` | `0/2` | `4/3/1` | `message_search_time_window` | `0` | `0` | PASS |
| `variant6_evidence_routing` | `-0.0620` | `+0.0731` | `0/1` | `4/2/2` | `message_search_time_window` | `0` | `0` | FAIL |
| `variant7_combined_best_stack` | `-0.0756` | `-0.0733` | `2/1` | `18/4/14` | `message_search_time_window`, `select_record_by_timestamp_extreme` | `0` | `0` | FAIL |

## Interpretation
- The tools were not getting a fair chance in the original generation-ON matrix because accepted tools were born mid-run.
- Once availability was corrected, `contract_synthesis` became clearly positive and protocol-passing.
- The combined stack remains too broad and creates routing/context pollution.
- Grading accounting, dependency logic, evidence routing, and candidate repair should not be scaled together yet.
- The next V2 stack should be narrow: `contract_synthesis` plus the downstream-tool availability routing repair and fixed helper docstrings.

## Remaining Adoption Risks
- A helper can still be visible-not-called if the base path looks plausible.
- Some helpers improve outcome while hurting canonical route score; route-mismatch reporting is still needed.
- Accepted tools should be evaluated through a two-stage pattern: discovery run, then frozen confirmation run with tools available from the first scenario.
- Promotion should use frozen confirmation called-subset contribution, not generation-ON birth-run contribution alone.

## Recommended Next Step
Run a quality-gated readiness-20 with:
- generation ON for discovery
- `contract_synthesis` enabled
- downstream-tool availability routing repair active
- fixed helper docstrings active
- then immediately run frozen confirmation-20 from any accepted candidate registry before judging promotion readiness.

Do not start 60/100/250 until this two-stage readiness pattern passes.

## Decision Label
`rerun readiness-20 with two-stage confirmation`

## Final Validation
- Script compile: `python -m py_compile scripts/run_v2_experimental_matrix20.py scripts/run_v2_fair_chance_confirmation20.py` -> PASS.
- Full unit tests: `PYTHONPATH=src:. pytest tests/unit -q` -> `171 passed, 2 warnings`.
- Registry checks:
  - `artifacts/registry_candidates/v2_tool_adoption_replay2/registry_manifest.json` -> PASS.
  - `artifacts/registry_candidates/v2_fair_chance_confirmation20/variant5_contract_synthesis/registry_manifest.json` -> PASS.
- `git diff --check` -> PASS.
