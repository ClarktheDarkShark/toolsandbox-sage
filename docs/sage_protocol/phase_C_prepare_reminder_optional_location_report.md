# Phase C.3 Report — prepare_reminder_creation_args optional-location handling

> **SUPERSEDED — ARCHIVAL ONLY.** This development report is not a current
> protocol, release gate, or paper result. Its values and decision labels must
> not be carried forward. See [current_state.md](current_state.md).

Date: 2026-05-02
Candidate: `prepare_reminder_creation_args`
Decision label: `pass`

## Objective

Narrow and validate the kept reminder helper so it adds decisive value on optional-location reminder creation without broad route pollution.

## Files Changed

- `scripts/register_prepare_reminder_creation_args.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/evaluation/task_strata.py`
- `tests/integration/test_toolsandbox_generated_tool_injection.py`

## Validation

- Registry proof: PASS
- Focused tests:
  - `PYTHONPATH=src:. pytest tests/integration/test_toolsandbox_generated_tool_injection.py -q -k 'reminder_creation_args'`
  - `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py -q`

## Repair History

Initial C.3 implementation fixed location-state handling but exposed the helper too broadly on the plain relative no-location `week_delta_and_time` lane.

Observed failure:
- Cohort v1 outcome delta: `-0.1041`
- Exact successes: `control=6`, `SAGE=4`
- Two true regressions, both helper-caused:
  - `add_reminder_content_and_week_delta_and_time`
  - `add_reminder_content_and_week_delta_and_time_alt`

Root cause:
- The helper was visible on plain relative no-location reminder creation.
- In those scenarios, it pulled the model into a bad timestamp route and produced wrong reminder state.
- This was a routing/visibility problem, not a location-state-machine problem.

Single allowed repair applied:
- Narrow helper exposure.
- Hide `prepare_reminder_creation_args` on `add_reminder_content_and_week_delta_and_time*` scenarios when `_location` is absent.
- Keep it visible on location-bearing reminder creation and safe absolute-date reminder creation.
- No second logic rewrite was applied.

## Candidate Registry

- v1: `artifacts/registry_phaseC_C3_candidate/registry_manifest.json`
- v2 kept registry: `artifacts/registry_phaseC_C3_candidate_v2/registry_manifest.json`
- Active registry hash: `617f05d199f736a454da335dbf67bc773c666a970ae24ef0aa17c1d082f26593`

## Focused Replay v1

Run:
- `outputs/phase_C3_reminder_replay/transfer_40_20260502_230636/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_replay/transfer_40_20260502_230636/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_replay/transfer_40_20260502_230636/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.1397`
- Outcome delta: `+0.1284`
- Gains / regressions / preserved:
  - canonical: `4 / 0 / 4`
  - outcome: `2 / 0 / 6`
- Helper visible/called/not-called: `5 / 5 / 0`
- Runtime exceptions: `0`
- Side-effect violations: `0`

## Focused Cohort v1

Run:
- `outputs/phase_C3_reminder_cohort/transfer_40_20260502_231031/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_cohort/transfer_40_20260502_231031/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_cohort/transfer_40_20260502_231031/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.0030`
- Outcome delta: `-0.1041`
- Exact successes: `control=6`, `SAGE=4`
- Gains / regressions / preserved:
  - canonical: `4 / 2 / 10`
  - outcome: `1 / 2 / 13`
- Helper visible/called/not-called: `11 / 11 / 0`
- Runtime exceptions: `0`
- Side-effect violations: `0`

Decision after v1:
- `needs one general repair`

## Focused Replay v2

Run:
- `outputs/phase_C3_reminder_replay_v2/transfer_40_20260502_231813/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_replay_v2/transfer_40_20260502_231813/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_replay_v2/transfer_40_20260502_231813/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.1105`
- Outcome delta: `+0.1398`
- Gains / regressions / preserved:
  - canonical: `4 / 0 / 4`
  - outcome: `2 / 0 / 6`
- Helper visible/called/not-called: `3 / 3 / 0`
- Runtime exceptions: `0`
- Side-effect violations: `0`

## Focused Cohort v2

Run:
- `outputs/phase_C3_reminder_cohort_v2/transfer_40_20260502_232138/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_cohort_v2/transfer_40_20260502_232138/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C3_reminder_cohort_v2/transfer_40_20260502_232138/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.0970`
- Outcome delta: `+0.0850`
- Exact successes: `control=5`, `SAGE=6`
- Gains / regressions / preserved:
  - canonical: `5 / 0 / 11`
  - outcome: `2 / 0 / 14`
- Helper visible/called/not-called: `7 / 7 / 0`
- Runtime exceptions: `0`
- Side-effect violations: `0`

Interpretation:
- The repair removed the two helper-caused regressions.
- The helper is now used only where it is safe and useful.
- No visible-but-not-called friction remained in the repaired cohort.
- The helper still preserves `add_reminder` and never bypasses the side-effect tool.

## Pass/Fail Assessment

Passes:
- registry proof PASS
- helper called in relevant repaired positives
- helper hidden on the known harmful plain relative no-location lane
- positive replay outcome delta after repair
- positive cohort outcome delta after repair
- exact successes improved on repaired cohort
- side-effect violations = `0`
- runtime exceptions = `0`
- no visible-not-called cases in repaired replay or cohort

Limit retained:
- The helper is no longer treated as a broad reminder-creation helper.
- It is kept only as a narrowed helper for location-bearing reminder creation plus safe absolute-date reminder preparation contexts.

## Decision

Decision label: `pass`

Rationale:
- The candidate failed the first broad cohort, but the single allowed repair directly addressed the only true helper-caused regressions.
- The repaired cohort is positive on canonical and outcome similarity, improves exact successes, and remains clean on side effects and runtime stability.
- `prepare_reminder_creation_args` stays active in the Phase C portfolio, but only in its narrowed routing scope.
