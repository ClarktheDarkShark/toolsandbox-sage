# Phase D Portfolio Ablation Report

> **SUPERSEDED — ARCHIVAL ONLY.** This development report is not a current
> protocol, release gate, or paper result. Its values and decision labels must
> not be carried forward. See [current_state.md](current_state.md).

Date: 2026-05-03
Decision label: `pass`

## Objective

Find the smallest positive frozen portfolio after Phase C by comparing each kept helper alone, the full portfolio, and leave-one-out variants on one fixed mixed cohort.

## Fixed Cohort

Manifest:
- `docs/sage_protocol/manifests/phase_D_mixed_30.json`

Model/config:
- mode: `transfer_40`
- generation: `OFF`
- agent/user/generation model: `gpt-4o-mini`
- base tool policy: `upstream`

## Frozen Registries

- full: `artifacts/phase_D_registries/full/registry_manifest.json`
- prepare only: `artifacts/phase_D_registries/prepare_only/registry_manifest.json`
- select only: `artifacts/phase_D_registries/select_only/registry_manifest.json`
- resolve only: `artifacts/phase_D_registries/resolve_only/registry_manifest.json`
- without prepare: `artifacts/phase_D_registries/without_prepare/registry_manifest.json`
- without select: `artifacts/phase_D_registries/without_select/registry_manifest.json`
- without resolve: `artifacts/phase_D_registries/without_resolve/registry_manifest.json`

## Arm Summary

| Arm | Run | Canonical delta | Outcome delta | Exact ctrl->sage | Gains/Reg | Outcome Gains/Reg | Called | Turns | Notes |
|---|---|---:|---:|---|---|---|---:|---:|---|
| full | `outputs/phase_D_full_v2/transfer_40_20260502_232844/` | `+0.1755` | `+0.1302` | `2 -> 5` | `18 / 5` | `12 / 6` | `14` | `437` | best outcome |
| prepare only | `outputs/phase_D_prepare_only/transfer_40_20260502_234029/` | `+0.0825` | `+0.0514` | `2 -> 2` | `11 / 4` | `7 / 7` | `4` | `391` | weak alone |
| select only | `outputs/phase_D_select_only/transfer_40_20260502_235136/` | `+0.1456` | `+0.1911` | `2 -> 5` | `9 / 9` | `12 / 3` | `6` | `314` | strong alone |
| resolve only | `outputs/phase_D_resolve_only/transfer_40_20260503_000343/` | `+0.1005` | `+0.0629` | `2 -> 5` | `14 / 7` | `10 / 6` | `9` | `384` | moderate alone |
| without prepare | `outputs/phase_D_without_prepare/transfer_40_20260503_001553/` | `+0.1993` | `+0.1157` | `2 -> 5` | `17 / 3` | `12 / 4` | `10` | `365` | slightly lower outcome than full |
| without select | `outputs/phase_D_without_select/transfer_40_20260503_003009/` | `+0.1065` | `+0.0266` | `3 -> 5` | `13 / 9` | `10 / 9` | `15` | `322` | large outcome drop |
| without resolve | `outputs/phase_D_without_resolve/transfer_40_20260503_004302/` | `+0.1500` | `+0.1204` | `2 -> 6` | `16 / 6` | `9 / 6` | `10` | `407` | near-full but slightly worse outcome |

## Interpretation

Primary metric is outcome similarity.

Observations:
- The full 3-helper portfolio has the highest outcome delta on the fixed mixed cohort: `+0.1302`.
- Removing `select_record_by_timestamp_extreme` materially hurts the portfolio: outcome falls to `+0.0266`.
- Removing `prepare_reminder_creation_args` slightly improves canonical but reduces outcome from `+0.1302` to `+0.1157`.
- Removing `resolve_search_window_or_bounds` stays close, but still trails the full portfolio on outcome: `+0.1204` vs `+0.1302`.
- `prepare_reminder_creation_args` is not the strongest individual helper, but it is still net-positive in the full portfolio on the primary metric.
- `select_record_by_timestamp_extreme` is the clearest decisive contributor.
- `resolve_search_window_or_bounds` is a moderate contributor that improves the mixed portfolio enough to retain.

## Pass Gate Assessment

Passes:
- full portfolio beats control on outcome similarity
- full portfolio beats control on canonical similarity
- gains exceed regressions on full portfolio
- runtime exceptions observed in dashboard summaries: `0`
- full portfolio helper calls observed: `14` relevant scenarios
- non-applicable subset not catastrophically harmed: mixed-arm full outcome remains positive with strong overall gain
- at least 3 tools show actual calls across the ablation matrix

## Phase E Portfolio Decision

Keep the full 3-helper portfolio for Phase E:
- `prepare_reminder_creation_args`
- `select_record_by_timestamp_extreme`
- `resolve_search_window_or_bounds`

Frozen Phase E registry:
- `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- SHA256: `e2ffb9d94ebffd0f96ac5fd6e1e1602deffbf3ede088ff1570534af319e760f3`

Rationale:
- Primary metric favors the full 3-helper portfolio over every smaller variant.
- The smaller variants improve some secondary properties, but none beat the full portfolio on the main outcome criterion.
- The full portfolio remains claim-safe and stable enough to take into Phase E.
