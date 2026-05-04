# SAGE V2 Final Tool Pipeline Campaign Report

- Updated: `2026-05-04T06:08:30.482096`
- Decision label: `formal 250 passed`
- Active frozen helpers: `relative_day_time_to_timestamp, resolve_search_window_or_bounds, select_record_by_timestamp_extreme`
- Registry: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Summary artifact: `artifacts/summaries/v2_final_best3_formal_validation/summary.json`
- Final package: `artifacts/final_sage_praxis_package/`

## Objective

Repair and validate the SAGE V2 tool-generation/tool-use pipeline, with conservative accounting for generated tools that improve final task outcome even when they may bypass canonical milestone routes.

## What Changed

The campaign enabled the best-performing V2 stack rather than all experimental ideas. The final broad portfolio removed the harmful reminder creation helper and retained only helpers with called-subset value and safe behavior:

- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`
- `relative_day_time_to_timestamp`

Framework repairs included safer side-effect follow-up accounting, stricter routing/visibility, repaired non-reminder helper affordance text, contract-synthesis defaults, control-cache support, and route-mismatch-qualified reporting.

## Tests Run

- `PYTHONPATH=src:. pytest tests/unit/test_sage_run_adapter.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_control_baseline_cache.py tests/unit/test_protocol_generation_policy.py tests/unit/test_v2_flags.py tests/unit/test_v2_matrix_selection.py -q` -> `109 passed, 2 warnings`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_best3_resolve_select_relative/registry_manifest.json` -> `3 active entries pass, 0 FAIL`
- `PYTHONPATH=src:. python -m py_compile ...` -> PASS
- `git diff --check` -> PASS

## Formal 100

- Run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
- Dashboard: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/index.html`
- Task focus: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/task_focus.html`

- Control outcome: `0.4010`
- SAGE outcome: `0.5357`
- Outcome delta: `0.1347`
- Relative outcome lift: `33.58%`
- Reference similarity delta: `0.0911`
- Exact successes: `control=16`, `SAGE=23`
- Gains/regressions/preserved: `50 / 14 / 36`
- Outcome gains/regressions/preserved: `39 / 15 / 38`
- Protocol gate passed: `True`
- Route-mismatch-qualified: `False`
- Runtime exceptions: `0`

Control cache: `fresh`, cached `0`, fresh `100`.

## Formal 250

- Run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Dashboard: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/index.html`
- Task focus: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/task_focus.html`

- Control outcome: `0.3930`
- SAGE outcome: `0.4736`
- Outcome delta: `0.0806`
- Relative outcome lift: `20.52%`
- Reference similarity delta: `0.0660`
- Exact successes: `control=31`, `SAGE=40`
- Gains/regressions/preserved: `102 / 53 / 95`
- Outcome gains/regressions/preserved: `73 / 40 / 89`
- Protocol gate passed: `True`
- Route-mismatch-qualified: `False`
- Runtime exceptions: `0`

Control cache: `fresh`, cached `0`, fresh `250`. The cache was enabled but no compatible cached controls were eligible because this was a new formal manifest checksum.

## Cohort Quality

- Scenario count: `250`
- Distinct base families: `32`
- Largest family share: `3.20%`
- Quality gate: `pass`
- No-current-helper-fit share: `44.40%`

## Helper Contribution On 250

| Helper | Visible | Called | Visible-not-called | Called outcome delta | Called reference/canonical delta | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 32 | 29 | 3 | 0.1389 | 0.0161 | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 42 | 30 | 0.2480 | 0.1616 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 27 | 5 | 0.1188 | 0.2746 | 0 | 0 |

## Canonical/Outcome Accounting

The primary metric is outcome/task-completion. The formal 250 also improved reference similarity by `0.0660` and did not require route-mismatch qualification. Per-helper contribution export still records canonical/reference deltas separately so helper substitution can be audited without hiding canonical failures.

## What Worked

- Broad focused helpers with clear deterministic outputs and precise routing produced real adoption.
- `relative_day_time_to_timestamp` fixed the largest remaining negative lane after the best2 250 failed.
- Removing `prepare_reminder_creation_args` improved safety; it had real side-effect follow-up failures in broad validation.
- Dashboard data served correctly for both formal dashboards before opening.

## Remaining Risks

- 44.4% of the 250 cohort still had no current-helper fit, so V2.0 should improve shortfall-cluster birth and routing beyond this v1.0 portfolio.
- `resolve_search_window_or_bounds` still has visible-not-called cases on remove-reminder/message lanes; adoption repair remains useful.
- Control cache was enabled but not eligible for the new formal manifests, so savings will accrue only after compatible repeats.

## Exact Next Action

Freeze this v1.0 evidence package, commit the coherent repair/validation changes, then start a new V2.0 campaign focused on autonomous shortfall clustering and generated-tool adoption across the no-current-helper-fit portion of the 250.

Decision label: `formal 250 passed`
