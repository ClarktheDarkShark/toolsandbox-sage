# V2.2 Best4 Ablation60 Report

## Objective

Determine whether confirmed V2.2 `days_between_timestamps` is additive to the frozen best3 portfolio before further masked-best3 discovery.

## Files And Registries

- Manifest: `artifacts/summaries/v2_2_best4_ablation60_20260506_075831/cohort_manifest.json`
- Manifest SHA-256: `e48d0cbf52c1e2e63c0135948f6a22f4c3d6fed43b49d1ca36e71444adea7cb9`
- Best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Days-only registry: `artifacts/registry_candidates/v2_2_days_only_ablation/registry_manifest.json`
- Best4 registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`
- Best4 registry SHA-256: `e497d29b7b31b89b9368af7c9327679086a881f8e9c62a182ca07b25f18f7834`
- Frozen best3 registry modified: `no`
- Summary artifact: `artifacts/summaries/v2_2_best4_decision_20260506_090500/summary.json`

## Cohort Quality

- Cohort quality gate: `PASS`
- Scenario count: `60`
- Distinct base families: `20`
- Largest family share: `0.0833`
- No-current-helper-fit share: `0.40`
- External-service contaminated scenarios: `0`
- Role mix: days positives `10`, best3 relative-time `8`, best3 search-window `8`, best3 record-selection `8`, days negatives/no-helper `4`, other no-helper negatives `22`

## Commands

```bash
PYTHONPATH=src:. python scripts/build_v2_2_best4_artifacts.py --timestamp 20260506_075831
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json artifacts/registry_candidates/v2_2_days_only_ablation/registry_manifest.json artifacts/registry_frozen_best3_claim/registry_manifest.json
conda run -n lifelong bash -lc 'source .secrets/env.sh; export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_2_best4_ablation60_20260506_075831/cohort_manifest.json --mode mechanism_60 --registry-dir <registry> --generation off --parallel-arms --control-cache use-if-eligible'
```

## Ablation Arms

| Arm | Run | Control cache | Candidate outcome | Outcome delta | Canonical delta | Exact successes | Gains / regressions / preserved | Runtime exceptions |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Best3 only | `outputs/v2_2_best4_ablation60_best3_20260506_075831/mechanism_60_20260506_075938` | fresh 0/60 | 0.4476 | +0.0504 | +0.0858 | 3 -> 5 | 12 / 8 / 32 | 0 |
| Days only | `outputs/v2_2_best4_ablation60_days_only_20260506_075831/mechanism_60_20260506_081058` | fresh 0/60 | 0.4821 | +0.0261 | +0.0191 | 1 -> 4 | 14 / 13 / 25 | 0 |
| Best3 + days | `outputs/v2_2_best4_ablation60_best4_20260506_075831/mechanism_60_20260506_082133` | fresh 0/60 | 0.4594 | -0.0103 | -0.0030 | 3 -> 4 | 14 / 15 / 23 | 0 |

## Common-Control Recalculation

The first three arms collected fresh controls, so raw outcome deltas are affected by baseline variance. After these arms, 32/60 scenarios were eligible for cached-control synthesis; 28 remained fresh because fewer than three compatible completed controls were considered valid under the cache policy. A cached-control rerun was attempted but blocked before candidate execution by slow partial-cache synthetic-control handling, so it was not used for the decision.

Common-control recalculation over the 52 scenarios with numeric outcome controls in the completed arms:

| Comparison | Mean candidate difference | N | Gains | Regressions |
|---|---:|---:|---:|---:|
| Best4 - Best3 | +0.0118 | 52 | 14 | 13 |
| Best4 - Days-only | -0.0228 | 52 | 9 | 16 |
| Days-only - Best3 | +0.0346 | 52 | 13 | 10 |

## Helper Contribution

Best4 helper contribution:

| Helper | Visible | Called | VNC | Called-subset outcome | Called-subset canonical | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `days_between_timestamps` | 8 | 8 | 0 | 0.0625 | -0.27143620830105897 | 0 | 0 |
| `relative_day_time_to_timestamp` | 4 | 4 | 0 | 0.0 | 0.0 | 0 | 0 |
| `resolve_search_window_or_bounds` | 16 | 6 | 10 | -0.06743603813020958 | 0.10501666103446966 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 8 | 8 | 0 | 0.24492752804215107 | 0.14216596906860657 | 0 | 0 |

## Interpretation

Ablation60 gave a weak positive Best4-vs-Best3 candidate-mean signal after correcting for control variance, and `days_between_timestamps` was naturally called on all visible days-between opportunities. Because the signal was small and exact successes were not better than best3, the correct next step was a frozen100 check rather than direct promotion.

## Decision Label

`best4 additive`

## Exact Next Action

Run frozen100 with generation OFF on the existing formal100 manifest and compare Best4 against the preserved best3 formal100 result.
