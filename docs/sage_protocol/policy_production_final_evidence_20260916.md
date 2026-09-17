# Final Policy-Production Evidence Cohort

## Decision

**READY_FOR_PAPER_UPDATE**

The publication cohort is complete: ten integrity-valid online-build runs and
ten integrity-valid frozen-registry runs. All selected executions used the
clean policy-directed runtime below and passed the strict campaign-inclusion
gate.

## Runtime identity

- Git commit: `4ce1c6de0ab36dd59e1a319f4e56e298133f4a79`
- Git tree: `4640019c7a054d4af6a500e7327ebbd0a507bfc5`
- Model: `gpt-4o-mini`
- Benchmark tasks per run: `1,032`
- Ordered task-name SHA-256:
  `fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176`
- Environment lock SHA-256:
  `5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`
- External distribution count/hash: `108` /
  `006191cd1efca9e244c6b5d6fb6a8c91fb95c279959cc91c9eada316f904fc9d`
- Frozen ToolSandbox timestamp: `1784832588`
- Sanitized external fixture SHA-256:
  `eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`

## Selected cohort

The selection rule was integrity-only and was fixed without consulting the
replacement run's performance.

- Online: original replications 01–03, technical replacement `rep04r1`, and
  original replications 05–10.
- Frozen: original replications 01–04, technical replacement `rep05r1`, and
  original replications 06–10.
- Excluded online `rep04`: one candidate-side `JSONDecodeError`.
- Excluded frozen `rep05`: one control-side `JSONDecodeError`.
- Both failed originals remain preserved.
- All 20 selected runs have zero control and candidate exceptions.
- All controls were executed fresh; cached control tasks and cached model
  responses are zero.
- All ten frozen registries were immutable during evaluation.

The original incomplete campaign manifest was not rewritten. Its SHA-256 is
`062f770aaa35561bc984a57e832a1fcc31a23bb0a677752841872f05a50f6c3d`.
The derived selected-cohort manifest SHA-256 is
`8cd359bebdc0f3576643d6d4850f0abe09fd3c05dafd50a62fc07d62c6425192`.

## Outcome results

Canonical ToolSandbox similarity is descriptive only and is excluded from all
release and hypothesis decisions.

| Cohort and endpoint | Control mean | SAGE mean | Absolute difference | Relative lift | SAGE range |
|---|---:|---:|---:|---:|---:|
| Online, audited v9 (1,032 tasks/run) | 0.586176 | 0.783543 | +0.197368 | +33.67% | 0.767846–0.799903 |
| Online, paper-comparable v1 (800 tasks/run) | 0.497535 | 0.800336 | +0.302801 | +60.86% | 0.784749–0.814361 |
| Frozen, audited v9 (1,032 tasks/run) | 0.582154 | 0.776195 | +0.194041 | +33.33% | 0.767765–0.795300 |
| Frozen, paper-comparable v1 (800 tasks/run) | 0.490666 | 0.795533 | +0.304867 | +62.13% | 0.778076–0.810195 |

The audited online analysis contains 10,320 matched observations. The exact
paper-comparable analysis contains 8,000 matched observations. The current v1
SAGE mean is `+0.004929` above the archived paper SAGE mean of `0.795407`.

## Hypothesis-facing values

- H1 frozen-registry gain retention: `96.28%`; run-paired bootstrap 95% CI
  `[92.54%, 100.01%]`; predeclared threshold `80%`; supported.
- H2 audited all-task outcome lift: `33.67%`; two-way run/task bootstrap 95% CI
  `[28.06%, 39.80%]`; run-level threshold-contrast sign-flip `p = .001953`;
  predeclared threshold `10%`; supported.
- Generated-tool-called task association: `47.17%` relative lift on 8,225
  observations. This is selection-conditioned and descriptive, not a causal
  attribution claim.

## Evidence artifacts

The full trajectories remain local because benchmark run outputs are not part
of the source distribution. The final evidence is under:

`artifacts/chapter4_evidence/chapter4_final_policy_online_frozen_20260911_4ce1c6d/technical_replacement/final_selected_cohort/`

Key local artifacts and hashes:

- `selected_cohort_manifest.json`:
  `8cd359bebdc0f3576643d6d4850f0abe09fd3c05dafd50a62fc07d62c6425192`
- `selected_cohort_verification.json`:
  `b1f563452b404b21949cae6c4783bc6777cdad5ba0a471b7bd16f250e8dd0b90`
- `dashboard/chapter4_evidence_data.json`:
  `927fc879d342a557a9304812905ce6852d4684cf445ee2334d0a9aead61325e6`
- `dashboard/chapter4_evidence.html`:
  `daee976d84e52a76087d6260b9efa40aa95ff7ec9e929018367ceff6c728ab77`
- `paper_tables/index.html`:
  `42eb6adfa4d3ae9ad365bfb65288188dfcccf09c208595e3e940dfaf880d4f14`

The dashboard reports 20 of 20 verified runs, ten online and ten frozen,
`inference_complete=true`, zero excluded selected artifacts, and zero runtime
exceptions.
