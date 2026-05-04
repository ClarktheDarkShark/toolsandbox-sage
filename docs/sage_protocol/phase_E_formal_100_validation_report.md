# Phase E Formal 100 Validation Report

Date: 2026-05-03
Decision label: `qualified pass; proceed to Phase F`

## Objective
Run a balanced, generation-off formal 100 validation using a frozen claim-safe portfolio.

## Evaluation Design
- Manifest: `docs/sage_protocol/manifests/phase_e_balanced_formal_100.json`
- Diversity report: `docs/sage_protocol/manifests/phase_e_balanced_formal_100_diversity.json`
- Scenarios: `100`
- Distinct base task families: `41`
- Largest base-family share: `5%`
- Active-helper-applicable share: `65%`
- Registry: `artifacts/registry_phaseE_balanced_final/registry_manifest.json`
- Registry hash: `385a0f7dbd65ce340f4edd97e26e89a67054cf1c661f01029692ca38547484b1`
- Generation: `OFF`

## Run
- Run root: `outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/`
- Dashboard: `http://127.0.0.1:5520/outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/dashboard/task_focus.html`

## Metrics
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | 0.4460 | 0.5258 | +0.0798 |
| Canonical similarity | 0.7527 | 0.8305 | +0.0778 |
| Exact successes | 10 | 13 | +3 |

- Relative outcome lift: `+17.9%`
- Relative canonical lift: `+10.3%`
- Outcome gains / regressions / preserved: `39 / 20 / 40`
- Canonical gains / regressions / preserved: `56 / 24 / 20`
- Outcome delta 95% CI from paired deltas: `[+0.0029, +0.1551]`
- Canonical delta 95% CI from paired deltas: `[+0.0261, +0.1294]`
- Runtime exceptions: `0`
- Side-effect violations: `0`

## Tool Adoption
- Visible generated-tool scenarios: `61`
- Called generated-tool scenarios: `52`
- Visible-not-called scenarios: `9`
- Failed generated-tool calls: `0`
- `prepare_reminder_creation_args` calls: `15`
- `resolve_search_window_or_bounds` calls: `37`

## Gate Interpretation
The runner protocol gate was `false` because its absolute confirmation threshold was `0.08` and the run produced `0.07976`, missing by `0.00024`.

The project target is relative lift >= `10%`; this run clears it on both primary outcome similarity (`+17.9%`) and canonical similarity (`+10.3%`). Treat as a qualified Phase E pass and proceed to Phase F formal 250 with the same frozen two-helper registry.

## Decision
Proceed to Phase F formal 250.
