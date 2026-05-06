# V2.2 New Toolset Registry Report

## Registry

- Registry path: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`
- Registry SHA-256: `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`
- Confirmation evidence: `artifacts/registry_candidates/v2_2_new_toolset/confirmation_evidence.json`
- Check-only: `PASS`
- Active entries: `1`
- Active FAIL entries: `0`
- Frozen best3 registry modified: `no`

## Confirmed Tools

| Tool | Mechanism | Confirmation evidence | Status |
|---|---|---|---|
| `days_between_timestamps` | Calendar/holiday timestamp-distance calculation after current timestamp and holiday timestamp are visible. | `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`; visible/called `14 / 14`; called-subset outcome `0.10714285714285714`. | Confirmed narrow V2.2 candidate. |

## Loop 2 Candidate Decisions

| Candidate | Decision | Reason |
| --- | --- | --- |
| `select_visible_record_by_constraints` | Not included | Routing exposure repaired, but natural calls stayed `0 / 16`; selector lane parked. |
| `extract_stock_symbol` | Not included | Valid and naturally called after trace-bridging, but called-subset outcome was negative (`-0.0772`). |
| `prepare_side_effect_args_from_selected_record` | Not included | Previously parked: force-call mixed/negative with side-effect risk. |
| Dependency/precondition helpers | Not included | Previously parked: force-call negative or side-effect risky. |

## New Toolset Count

- Confirmed non-best3 tools: `1 / 3`
- Current confirmed set: `days_between_timestamps`
- Combined ablation status: not justified yet; requires at least two confirmed new tools and preferably three.

## Decision Label

`new toolset has 1 confirmed tool`


## Best4 Additivity Check Update

- Best4 candidate registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`
- Ablation60 report: `docs/sage_protocol/v2_2_best4_ablation60_report.md`
- Frozen100 report: `docs/sage_protocol/v2_2_best4_frozen100_report.md`
- Result: `days_between_timestamps` remains confirmed as a narrow standalone V2.2 tool, but Best4 did not beat preserved best3 on formal100.
- Decision: do not promote `days_between_timestamps` into the main frozen portfolio; do not run Best4 frozen250.
