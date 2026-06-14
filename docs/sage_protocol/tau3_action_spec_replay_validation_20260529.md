# tau3 Action-Spec Replay Validation Update - 2026-05-29

## Objective

Strengthen tau3 portability around the ToolSandbox-like control point: generated
helpers must be callable, side-effect-free, and action-spec-ready rather than
broad prompt guidance.

## Code Changes

- Added generic action-spec semantic validation in `src/sage_agent/validation.py`.
  The validator now rejects helpers that claim `should_call_tool=true` while
  abstaining, omitting tool/argument structure, carrying missing arguments, or
  returning inconsistent `next_action` and legacy `downstream_tool_*` fields.
- Allowed read-only evidence-gathering host calls such as `get_*`, `search_*`,
  and `lookup_*` to carry unresolved side-effect preconditions. This preserves
  policy-guard workflows where a helper first fetches a visible record before
  deciding whether a write action is safe.
- Updated generator prompts and core visible-action gap schemas to request
  `status`, `reason`, and `next_action` in addition to legacy action fields.
- Updated the tau3 SAGEAgent bridge to consume `next_action` as a fallback when
  generated helpers return it.
- Added unit coverage for rejecting missing-argument action specs, accepting
  consistent `next_action` specs, allowing read-only policy lookup specs, and
  rejecting mismatched `next_action`/legacy specs.

## Validation

- `python -m py_compile src/sage_agent/controller.py src/sage_agent/import_agent.py src/sage_agent/gap_mining.py src/sage_agent/generators.py src/sage_agent/registry.py src/sage_agent/validation.py scripts/run_cybergym_live_batched_sage.py scripts/run_tau3_sageagent_parity.py scripts/run_sage_protocol.py`
- `PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q`
  - Result: `85 passed, 2 warnings`.
- Focused CyberGym/SAGE planner subset:
  - `8 passed, 76 deselected`.
- `git diff --check`
  - Passed.

## tau3 Diagnostics

### `tau3_generalization20_20260529_183539`

- Dashboard: `outputs/sage_official_live/tau3_generalization20_20260529_183539/dashboard/task_compare.html`
- Stopped after 2 SAGE task records.
- Partial result: baseline cache `8/20`, SAGE `1/2`, tools born/accepted/reused
  `1 / 0 / 0`.
- Reason stopped: the new validator incorrectly rejected a read-only
  policy-guard lookup with unresolved side-effect preconditions.
- Decision: diagnostic only; fixed by allowing read-only lookups with
  `missing_preconditions`.

### `tau3_generalization20_action_spec_v2_20260529_184112`

- Dashboard: `outputs/sage_official_live/tau3_generalization20_action_spec_v2_20260529_184112/dashboard/task_compare.html`
- Error log: `artifacts/tau3_errors_20260529_185534.log`
- Stopped after 7 SAGE task records due suspected runtime/generation stall.
- Partial result: baseline cache `8/20`; SAGE `3/7` counted by controller;
  tools born/accepted/reused `14 / 11 / 31`; birth-task retries `3`, retry
  successes `1`; integrity issues `0`.
- Observed positive signal: task `tau3:airline:0` failed initially, birthed
  action helpers, and succeeded on same-task retry. Task `tau3:airline:1` was a
  baseline-failed/SAGE-succeeded row with generated helper use.
- Observed negative signal: among completed rows, approximate paired accounting
  showed one helper-used gain and two helper-used regressions
  (`tau3:airline:2`, `tau3:airline:4`), plus additional baseline-won/SAGE-lost
  rows without helper calls.

## Interpretation

The stricter core action-spec validator is useful: it caught incomplete or
unsafe helper outputs and forced a real read-only lookup exception that maps to
tau3 policy-guard behavior. The tau3 bridge now has a cleaner structured action
contract.

The partial v2 run is not clean enough to scale. It shows generated-helper
birth, routing, use, and same-task retry success, but helper quality/routing is
still unstable and the run did not complete the 20-task gate. Current blocker is
a mix of helper candidate quality, over-broad routing into baseline-winnable
tasks, and generation/runtime latency after repeated post-failure gap handling.

## Decision

`BLOCKED: tau3_action_spec_helpers_not_clean_20_ready`

## Next Action

- Add a runner-level `--max-gap-signals-per-task` or lower tau3 default to cap
  expensive post-failure generation.
- Strengthen replay acceptance so newly accepted host-action helpers must pass
  exact failure-turn or read-only lookup replay before routing broadly.
- Route freshly born helpers in shadow mode until they produce a retry win or
  replay proof; do not expose broad action helpers to baseline-winnable tasks
  without positive evidence.
- Rerun tau3 20 only after those routing/replay gates are in place.
