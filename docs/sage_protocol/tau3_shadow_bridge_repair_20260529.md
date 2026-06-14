# Tau3 Shadow Helper Bridge Repair - 2026-05-29

This is an experimental engineering report, not protected final-claim evidence.

## Objective

Repair tau3 SAGEAgent portability so generated helpers are exposed as real
callable or structured control points in the host-owned loop, while avoiding the
prompt-only over-perturbation that hurt earlier import-mode runs.

## Implementation Summary

- Shadow helper mode now injects structured helper preflight outputs into the
  actor context by default. The old behavior, where helpers were executed but
  hidden unless direct actions were enabled, is preserved only behind
  `--direct-only-shadow-helpers`.
- Official tau2 runner exceptions are treated as transient infrastructure
  failures so `--transient-retries` is honored.
- Generated helper execution is bounded by a helper timeout.
- Contribution accounting ignores sanitized abstain/non-actionable helper
  outputs for gain/regression attribution.
- Active cancellation/refund intent gating prevents a past airline-canceled
  flight compensation request from authorizing `cancel_reservation`.

## Best Diagnostic Run

- Run: `outputs/sage_official_live/tau3_shadow_cancel_gate20_20260529_224218`
- Dashboard:
  `outputs/sage_official_live/tau3_shadow_cancel_gate20_20260529_224218/dashboard/task_compare.html`
- Baseline: `8/20`
- Final SAGE: `11/20`
- Initial SAGE: `9/20`
- Tools born/accepted/reused: `12 / 12 / 120`
- Birth-task retries: `8`
- Birth-task retry successes: `4`
- Integrity issues: `0`

Strict generated-tool attribution is still limited. The clean callable-helper
gain is `tau3:airline:11`, where `prepare_visible_record_field_lookup` and
`prepare_visible_reservation_change_action_args` produced actionable lookup and
update specs on the successful retry. Other final gains were not counted as
strict helper evidence because helper outputs were absent or non-actionable.

## Safety and Regressions

The earlier helper-caused regression was reproduced and repaired:
`prepare_visible_cancellation_refund_action_args` misread a compensation request
for a flight already canceled by the airline as permission to call
`cancel_reservation`. The active cancellation/refund intent gate now blocks that
side-effect class unless the user directly asks to cancel/refund a booking.

The best run had zero helper-attributed final regressions. Its remaining final
regression (`tau3:airline:2`) had no generated-helper calls/actionable helper
outputs and should not be counted against generated-tool attribution.

## Parked Ablation

`outputs/sage_official_live/tau3_shadow_route_gate20_20260529_231249` tested a
hard cancellation route gate. It scored SAGE `7/20` vs baseline `8/20` and
produced no strict callable-helper gains. The hard route gate is parked because
it starved useful helper exposure and did not improve the tool-attributed
signal.

## Validation

- `python -m py_compile` on SAGE core, tau3, CyberGym, and ToolSandbox runners:
  passed.
- `PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q`:
  `94 passed, 2 warnings`.
- `git diff --check`: passed.

## Decision

`PROMISING_TAU3_SHADOW_BRIDGE_ONE_STRICT_CALLABLE_GAIN_REFINE_BEFORE_60`

Do not scale to tau3 60 yet. The next implementation target is candidate
quality: exact payment/option-selection helpers and lifecycle parking for
repeated non-gain record lookup calls.
