# V2.2 New Toolset Registry Report

## Registry

- Registry path: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`
- Registry SHA-256: `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`
- Confirmation evidence: `artifacts/registry_candidates/v2_2_new_toolset/confirmation_evidence.json`
- Check-only: `PASS`

## Confirmed Tools

| Tool | Mechanism | Confirmation evidence | Status |
|---|---|---|---|
| `days_between_timestamps` | Calendar/holiday timestamp-distance calculation after current timestamp and holiday timestamp are visible. | `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`; visible/called `14 / 14`; called-subset outcome `0.10714285714285714`. | Confirmed narrow V2.2 candidate. |

## Not Included

- `select_visible_record_by_constraints`: valid/visible but naturally uncalled after repairs.
- `prepare_side_effect_args_from_selected_record`: force-call mixed/negative with side-effect risk.

## Decision Label

`new toolset has 1 confirmed tool`
