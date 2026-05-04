# Phase C.2 Report — resolve_search_window_or_bounds

Date: 2026-05-02
Candidate: `resolve_search_window_or_bounds`
Decision label: `pass`

## Objective

Implement and validate a decisive helper that converts bounded recency language into original `search_reminder` or `search_messages` kwargs without replacing the downstream search tool.

## Files Changed

- `scripts/register_resolve_search_window_or_bounds.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/evaluation/task_strata.py`
- `tests/unit/test_resolve_search_window_or_bounds.py`
- `tests/unit/test_task_strata.py`
- `tests/integration/test_toolsandbox_generated_tool_injection.py`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Validation

- Registry proof: PASS
- Held-out checks: `1`
- Negative applicability checks: `2`
- Runtime smoke: PASS
- Focused tests:
  - `pytest tests/unit/test_resolve_search_window_or_bounds.py tests/unit/test_task_strata.py -q`
  - `pytest tests/integration/test_toolsandbox_generated_tool_injection.py -q -k 'resolve_search_window'`

## Repair History

Initial replay exposed one general issue:
- false side-effect preservation failures because the helper advertised `required_original_tool_calls` for non-side-effect search tools
- weaker ordering guidance when visible beside `select_record_by_timestamp_extreme`

One general repair was applied:
- removed `required_original_tool_calls`
- strengthened description ordering: helper first, then original search, then later selector

No code-path logic changed in the helper implementation during the repair.

## Focused Replay v2

Run:
- `outputs/phase_C2_search_window_replay_v2/transfer_40_20260502_223759/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C2_search_window_replay_v2/transfer_40_20260502_223759/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C2_search_window_replay_v2/transfer_40_20260502_223759/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.3889`
- Outcome delta: `+0.4868`
- Exact successes: `control=1`, `SAGE=3`
- Gains / regressions / preserved:
  - canonical: `6 / 1 / 1`
  - outcome: `6 / 0 / 2`
- Turns: `76 -> 62` (`-14`)
- `resolve_search_window_or_bounds` visible/called/not-called: `6 / 4 / 2`
- Runtime exceptions: `0`
- Side-effect violations: `0`

Interpretation:
- The helper was called in all 4 reminder-search positives and materially improved them.
- In the 2 raw message-recency cases, `select_record_by_timestamp_extreme` remained the called helper after the original message search path was formed; `resolve_search_window_or_bounds` was visible but not chosen.
- Negatives remained clean.

## Focused Cohort

Run:
- `outputs/phase_C2_search_window_cohort/transfer_40_20260502_224132/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_C2_search_window_cohort/transfer_40_20260502_224132/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_C2_search_window_cohort/transfer_40_20260502_224132/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.1444`
- Outcome delta: `+0.1682`
- Exact successes: `control=4`, `SAGE=5`
- Gains / regressions / preserved:
  - canonical: `10 / 3 / 3`
  - outcome: `7 / 6 / 3`
- Turns: `207 -> 168` (`-39`)
- `resolve_search_window_or_bounds` visible/called/not-called: `12 / 8 / 4`
- Runtime exceptions: `0`
- Side-effect violations: `0`

Interpretation:
- The helper consistently improved the reminder-search lane, including creation-recency, due-recency, implicit, and distraction variants.
- Message-recency scenarios remained primarily solved by the already-kept selector lane; `resolve_search_window_or_bounds` was visible there but not adopted.
- The helper stayed hidden on the service/contact negatives in this cohort.

## Pass/Fail Assessment

Passes:
- registry proof PASS
- helper called in relevant reminder positives
- hidden in negatives used for C.2
- no runtime exceptions
- no side-effect violations after the single repair
- positive outcome delta on replay and cohort
- positive canonical delta on replay and cohort
- gains exceed regressions on canonical and narrowly exceed on outcome in the focused cohort

Limit noted:
- Message-recency adoption is still secondary to `select_record_by_timestamp_extreme`; this helper currently behaves as a decisive reminder-search helper first, with message support available but not reliably selected.

## Decision

Decision label: `pass`

Rationale:
- The helper clears the C.2 gate after one general repair.
- It is claim-safe, improves primary outcome on both replay and cohort, reduces turns, and introduces no runtime or side-effect instability.
- It should be kept active in the candidate portfolio for Phase C.3, with the message-recency non-adoption documented rather than hidden.
