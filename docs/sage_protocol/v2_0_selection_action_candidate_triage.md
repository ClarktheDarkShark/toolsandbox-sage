# V2.0 Selection-Action Candidate Triage

## Candidate Summary
| candidate | classification | natural visible/called/VNC | force visible/called | force called outcome delta | force called canonical delta | decision |
|---|---:|---:|---:|---:|---:|---|
| `select_contact_field_by_constraint` | `diagnostic_only` | `2 / 0 / 2` | `8 / 4` | `-0.0132` | `0.0020` | `park` |

## Evidence
- Candidate registry snapshot with generated selector: `outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512/registry_gate/registry_manifest_before_run.json` if present; discovery failed-gate snapshot: `outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638/registry_gate/registry_manifest_failed_gate.json`.
- Natural run accepted the candidate but called it `0` times.
- Diagnostic force-after-`search_contacts` called it on `4` scenarios.
- Called-subset outcome delta was negative: `-0.0132`.
- Overall force diagnostic outcome delta was negative: `-0.1074`.
- Runtime exceptions: `0`.
- Helper side-effect incidents: `0`.

## Triage Decision
`select_contact_field_by_constraint` should remain parked/diagnostic-only. It does not justify confirmation60 because it was naturally uncalled and force-call testing did not show positive task-completion value.

## Decision Label
`candidate concept negative`
