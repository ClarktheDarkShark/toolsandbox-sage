# Phase E Mixed Pilot Report

Date: 2026-05-03
Decision label: `needs one general repair`

## Objective

Run a broader mixed pilot on the frozen Phase D portfolio before committing to formal 100.

## Attempt 1 — Full 3-helper portfolio

Registry:
- `artifacts/registry_phaseE_portfolio/registry_manifest.json`

Run:
- `outputs/phase_E_mixed_pilot/transfer_40_20260503_010141/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot/transfer_40_20260503_010141/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot/transfer_40_20260503_010141/dashboard/task_focus.html`

Metrics:
- Canonical delta: `+0.0225`
- Outcome delta: `-0.1928`
- Exact successes: `control=33`, `SAGE=26`
- Gains / regressions:
  - canonical: `21 / 18`
  - outcome: `3 / 16`
- Generated-tool called scenarios: `19`
- Runtime exceptions: `0`

Failure pattern:
- Broader pilot outcome collapsed despite positive Phase D.
- Helper-attributed regression concentrated in `prepare_reminder_creation_args`.
- Helper contribution audit on this pilot showed net negative contribution from `prepare_reminder_creation_args`.

Corrective action taken:
- Suppressed `prepare_reminder_creation_args` for a new pilot.

## Attempt 2 — Select-only corrective pilot

Registry:
- `artifacts/registry_phaseE_select_only/registry_manifest.json`

Run:
- `outputs/phase_E_mixed_pilot_select_only/transfer_40_20260503_012615/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot_select_only/transfer_40_20260503_012615/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot_select_only/transfer_40_20260503_012615/dashboard/task_focus.html`

Metrics:
- Canonical delta: `-0.0269`
- Outcome delta: `+0.0024`
- Exact successes: `control=32`, `SAGE=33`
- Gains / regressions:
  - canonical: `10 / 11`
  - outcome: `7 / 7`
- Generated-tool called scenarios: `0`
- Runtime exceptions: `0`

Interpretation:
- This pilot did not meaningfully improve outcomes.
- More importantly, the retained helper was not called at all on the broader mixed cohort.
- A visible-but-not-called or hidden-everywhere portfolio cannot support a Phase E claim.

Corrective action taken:
- Tried a second reduced pilot that preserved `select_record_by_timestamp_extreme` plus `resolve_search_window_or_bounds` while keeping `prepare_reminder_creation_args` suppressed.

## Attempt 3 — Without-prepare corrective pilot

Registry:
- `artifacts/registry_phaseE_without_prepare/registry_manifest.json`

Run:
- `outputs/phase_E_mixed_pilot_without_prepare/transfer_40_20260503_013711/`

Dashboards:
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot_without_prepare/transfer_40_20260503_013711/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/phase_E_mixed_pilot_without_prepare/transfer_40_20260503_013711/dashboard/task_focus.html`

Metrics:
- Canonical delta: `-0.0000`
- Outcome delta: `+0.0151`
- Exact successes: `control=32`, `SAGE=32`
- Gains / regressions:
  - canonical: `11 / 9`
  - outcome: `7 / 6`
- Generated-tool called scenarios: `0`
- Runtime exceptions: `0`

Interpretation:
- Outcome is barely positive and well below the Phase E pilot gate.
- No generated helper calls occurred on the broader mixed cohort.
- This means the retained helper portfolio is not broad enough, or not exposed/called robustly enough, to support a broad mixed claim.

## Decision

Phase E pilot failed.

Reasons:
- The original 3-helper portfolio failed the primary pilot gate on outcome.
- The two conservative corrective pilot reruns suppressed the harmful reminder helper, but both broader pilots then showed `0` actual helper calls.
- A portfolio that is not called on the broader mixed pilot cannot be advanced honestly to formal 100.

## Consequence

- `Phase E formal 100` was **not started**.
- `Phase F formal 250` was **not started**.

## Required Next Repair

One general repair is still needed before rerunning Phase E:
- broaden or repair routing/visibility so the retained helper portfolio is actually called on broader mixed cohorts, not only on tightly focused Phase C/D subsets.

The cleanest next target is:
- repair broad-cohort routing/adoption for `select_record_by_timestamp_extreme` and `resolve_search_window_or_bounds`
- then rerun the mixed pilot before any formal 100 attempt
