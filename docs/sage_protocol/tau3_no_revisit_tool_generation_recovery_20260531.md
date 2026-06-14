# tau3 No-Revisit Tool Generation Recovery - 2026-05-31

This is an experimental engineering report, not protected final-claim
evidence.

## Objective

Test whether SAGE can recover the earlier `12/20` tau3 success pattern without
same-task retries by moving the useful retry behavior into first-pass generated
helper routing, validation, and repair.

## Main Result

- Run:
  `outputs/sage_official_live/tau3_no_revisit_recovery_gate60f_20260531_001355`
- Dashboard:
  `http://127.0.0.1:62746/outputs/sage_official_live/tau3_no_revisit_recovery_gate60f_20260531_001355/dashboard/task_compare.html`
- Requested sample: `60`; materialized airline tasks in this checkout: `50`.
- Baseline: `15/50`.
- SAGE: `29/50`.
- First 20 slice: baseline `8/20`, SAGE `15/20`.
- Absolute lift: `+14` tasks, `+28` percentage points.
- Relative success lift: `+93.33%` over baseline.
- Same-task retries: `0`.
- Generated tools born/accepted/reused: `22 / 22 / 1162`.
- Bridge activity: `144` direct helper actions, `77` official action repairs,
  `30` final-answer repairs.
- Paired gains:
  `1, 8, 11, 12, 13, 15, 18, 26, 28, 34, 38, 40, 43, 48`.
- Paired losses: none.
- Integrity issues: `0`.

This is the strongest tau3 no-revisit result so far. It exceeds the prior
`24/50` no-revisit reference and removes the earlier baseline-success losses.

## What Changed

The useful same-task retry behavior was moved into first-pass validation and
repair:

- visible update-payment repair: if `update_reservation_flights` proposes an
  invalid certificate payment for a visibly cheaper update, replace it with the
  reservation's original visible payment method;
- baggage entitlement lookup gating: in baggage/membership contexts, allow one
  first visible reservation lookup from the profile when no cabin-bearing
  reservation record is visible yet, while still suppressing broad reservation
  scans;
- existing direct-action, official-action, and final-answer bridges remained
  active under `--max-same-task-retries 0`.

## Interpretation

The lift is not prompt-only guidance. The run used accepted generated helpers
and first-pass structured bridges to constrain host actions and answers. The
important helper classes were:

- visible record lookup;
- visible option selection;
- reservation-change action argument preparation;
- booking/payment argument preparation;
- baggage entitlement final-answer computation;
- visible payment delta summarization;
- side-effect and required-field guards.

The remaining misses cluster in harder baseline-failed tasks, especially longer
booking/cancellation flows where helper quality and route timing still lag.
The current blocker is no longer basic callability or same-task retry
dependence.

## Validation

- `python -m py_compile` passed for SAGE core files and major runners.
- `PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q` passed:
  `160 passed`, with two dependency version warnings.
- `git diff --check` passed.
- `scripts/audit_sage_import_readiness.py` was attempted and failed because
  it is keyed to the import-agent boundary and event names. This run uses the
  `SAGEAgent EnvironmentAdapter` parity runner, not `SAGEImportAgent`; the
  failure is not treated as a run-integrity failure.

## Decision

`KEEP_AND_SCALE_NO_REVISIT_TAU3_HELPER_BRIDGE`

Next steps:

- run another clean 50/60 tau3 confirmation if budget permits;
- update the audit/export path so SAGEAgent parity runs have the same
  attribution audit coverage as import-agent runs;
- inspect remaining paired misses to identify the next general helper class;
- run CyberGym 20/40 or 60 to confirm CyberGym behavior was not disturbed;
- run ToolSandbox maintenance after cross-environment changes stabilize.
