# Phase F Formal 250 And Final Package Report

Date: 2026-05-03
Decision label: `large evaluation failed`

## Objective
Run formal 250 balanced validation with the frozen Phase E two-helper registry and package v1 evidence.

## Run
- Manifest: `docs/sage_protocol/manifests/phase_f_balanced_formal_250.json`
- Diversity: `docs/sage_protocol/manifests/phase_f_balanced_formal_250_diversity.json`
- Registry: `artifacts/registry_phaseE_balanced_final/registry_manifest.json`
- Registry hash: `385a0f7dbd65ce340f4edd97e26e89a67054cf1c661f01029692ca38547484b1`
- Generation: `OFF`
- Run root: `outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/`
- Dashboard: `http://127.0.0.1:5520/outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/dashboard/task_focus.html`

## Results
| Metric | Control | SAGE | Delta |
|---|---:|---:|---:|
| Outcome similarity | 0.4579 | 0.4581 | +0.0002 |
| Canonical similarity | 0.7491 | 0.7872 | +0.0381 |
| Exact successes | 23 | 22 | -1 |

- Relative outcome lift: `+0.04%`
- Relative canonical lift: `+5.09%`
- Outcome gains / regressions / preserved: `70 / 66 / 110`
- Canonical gains / regressions / preserved: `118 / 71 / 61`
- Outcome 95% CI: `[-0.0474, +0.0477]`
- Canonical 95% CI: `[+0.0044, +0.0718]`
- Runtime exceptions: `0`
- Side-effect violations: `0`

## Tool Adoption
- Visible scenarios: `121`
- Called scenarios: `87`
- Visible-not-called scenarios: `31`
- Attempt-failed scenarios: `3`
- `prepare_reminder_creation_args` calls: `26`
- `resolve_search_window_or_bounds` calls: `61`

## Failure Taxonomy
- `resolve_search_window_or_bounds` remained positive on called scenarios: mean outcome delta about `+0.111`.
- `prepare_reminder_creation_args` was negative on called scenarios: mean outcome delta about `-0.128`.
- Visible-not-called scenarios were negative: mean outcome delta about `-0.113`.
- No-helper scenarios were roughly flat.
- The formal 250 failure is a real task-completion failure, not a canonical route-mismatch issue.

## V2 Artifact Notes
- V2 should generate tools from diverse shortfall clusters across 3-20 non-near-duplicate tasks.
- Tool birth should require mechanism-level shortfall evidence, cross-family applicability, adoption evidence, and no side-effect replacement.
- See `artifacts/summaries/v2_improvement_backlog/initial_v2_backlog.md`.

## Final Package
- Package root: `artifacts/final_sage_praxis_package/`
- Machine summary: `artifacts/summaries/phase_F_balanced_formal_250/summary.json`

## Decision
Formal 250 failed the primary task-completion target. Do not claim final v1 250-task success. Use v1 as a promising baseline for v2.
