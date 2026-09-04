# Phase C Portfolio Candidates Report

> **SUPERSEDED — ARCHIVAL ONLY.** This development report is not a current
> protocol, release gate, or paper result. Its values and decision labels must
> not be carried forward. See [current_state.md](current_state.md).

Date: 2026-05-02
Decision label: `pass`

## Active Helpers

1. `prepare_reminder_creation_args`
2. `select_record_by_timestamp_extreme`
3. `resolve_search_window_or_bounds`

## Active Registry

- Path: `artifacts/registry_phaseC_C3_candidate_v2/registry_manifest.json`
- Hash: `617f05d199f736a454da335dbf67bc773c666a970ae24ef0aa17c1d082f26593`
- Proof status: `PASS` for all 3 active entries

## Helper Summary

| Helper | Proof | Focused replay | Focused cohort | Outcome delta | Canonical delta | Visible/called | Side effects | Runtime | Decision |
|---|---|---|---|---:|---:|---|---|---|---|
| `prepare_reminder_creation_args` | PASS | `outputs/phase_C3_reminder_replay_v2/transfer_40_20260502_231813/` | `outputs/phase_C3_reminder_cohort_v2/transfer_40_20260502_232138/` | `+0.1398` replay, `+0.0850` cohort | `+0.1105` replay, `+0.0970` cohort | replay `3/3`, cohort `7/7` | `0` violations | `0` exceptions | keep, narrowed |
| `select_record_by_timestamp_extreme` | PASS | `outputs/phase_C1_record_selection_replay_v2/transfer_40_20260502_215943/` | `outputs/phase_C1_record_selection_replay_v2/transfer_40_20260502_215943/` | `+0.267` | `+0.221` | `6/6` | `0` violations | `0` exceptions | keep |
| `resolve_search_window_or_bounds` | PASS | `outputs/phase_C2_search_window_replay_v2/transfer_40_20260502_223759/` | `outputs/phase_C2_search_window_cohort/transfer_40_20260502_224132/` | `+0.4868` replay, `+0.1682` cohort | `+0.3889` replay, `+0.1444` cohort | replay `6/4`, cohort `12/8` | `0` violations | `0` exceptions | keep |

## Phase C Completion Gate

Satisfied:
- at least 3 active helpers: `3`
- registry proof PASS: `yes`
- 0 active FAIL entries: `yes`
- actual helper calls in relevant positives: `yes`
- focused replay evidence: `yes`
- focused cohort evidence: `yes`
- no side-effect violations: `yes`
- no runtime exceptions: `yes`
- positive or neutral-positive outcome evidence across kept helpers: `yes`
- regressions resolved or documented as non-kept broad routing: `yes`
- no broad context pollution in the kept repaired portfolio: `yes`

## Recommended Phase D Portfolio

Use the following frozen three-helper portfolio for ablation:
- `prepare_reminder_creation_args` (narrowed repaired routing)
- `select_record_by_timestamp_extreme`
- `resolve_search_window_or_bounds`

## Notes

- `prepare_reminder_creation_args` is kept only after the single allowed repair that suppresses its harmful plain relative no-location lane.
- `select_record_by_timestamp_extreme` and `resolve_search_window_or_bounds` remain unchanged from their passing versions.
- Phase C is complete without starting C.4 or C.5 because the portfolio already contains 3 kept claim-safe helpers.
