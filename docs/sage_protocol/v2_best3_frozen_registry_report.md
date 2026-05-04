# V2 Best3 Frozen Registry Report

- Updated: `2026-05-04T07:02:15.534203`
- Decision label: `best3 registry frozen`

## Frozen Registry

- Source registry: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
- Source SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Frozen claim registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen claim SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Active entries: `3`
- Registry check-only: PASS before formal 250 and PASS after evidence lock.

## Entry Metadata Audit

| Tool | Schema version | Validation accepted | Runtime smoke | Output schema/annotation | Positive triggers | Negative triggers | Retired |
|---|---:|---:|---:|---:|---:|---:|---:|
| `resolve_search_window_or_bounds` | `2` | `True` | `True` | `True` | `True` | `True` | `False` |
| `select_record_by_timestamp_extreme` | `2` | `True` | `True` | `True` | `True` | `True` | `False` |
| `relative_day_time_to_timestamp` | `2` | `True` | `True` | `True` | `False` | `False` | `False` |

`relative_day_time_to_timestamp` uses a scalar `output_annotation` rather than a JSON object `output_schema`, and its trigger metadata is sparse because it is a legacy accepted helper. This is preserved as-is in the frozen claim registry to avoid altering the passed evidence. Future V2.0 metadata repair should occur in a separate candidate registry, not in this frozen claim registry.

Decision label: `best3 registry frozen`
