# V2.2 Best4 Candidate Registry Report

## Objective

Create a candidate registry containing the protected frozen best3 portfolio plus the confirmed V2.2 `days_between_timestamps` tool, without modifying the frozen best3 claim registry.

## Registry

- Best4 candidate registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`
- Registry SHA-256: `e497d29b7b31b89b9368af7c9327679086a881f8e9c62a182ca07b25f18f7834`
- Source frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Source confirmed days registry: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`
- Frozen best3 registry modified: `no`

## Included Tools

- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`
- `days_between_timestamps`

## Validation Status

Registry check-only PASS:

- `days_between_timestamps`: PASS
- `relative_day_time_to_timestamp`: PASS
- `resolve_search_window_or_bounds`: PASS
- `select_record_by_timestamp_extreme`: PASS

Command:

```bash
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json artifacts/registry_candidates/v2_2_days_only_ablation/registry_manifest.json artifacts/registry_frozen_best3_claim/registry_manifest.json
```

## Confirmation Evidence For `days_between_timestamps`

- Prior confirmation run: `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`
- Overall outcome delta: `+0.0891`
- Called-subset outcome delta: `+0.10714285714285714`
- Visible/called/VNC: `14 / 14 / 0`
- Runtime incidents: `0`
- Side-effect incidents: `0`
- Canonical called-subset delta: `-0.2102519581336632`
- Route-mismatch accounting: helper-substitution route mismatch explicitly reported

## Decision Label

`best4 candidate registry ready`
