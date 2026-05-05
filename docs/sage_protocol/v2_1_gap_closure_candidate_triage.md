# V2.1 Gap Closure Candidate Triage

## Summary
No candidate qualifies for confirmation60 or promotion.

| candidate | source | natural evidence | force evidence | decision | reason |
|---|---|---:|---:|---|---|
| `select_visible_record_by_constraints` | discovery60 | rejected | not run | park | Rejected by live negative case: did not abstain on a negative example. |
| `prepare_side_effect_args_from_selected_record` | discovery60 | visible/called/VNC `27 / 0 / 27` in discovery60; `12 / 0 / 12` in natural diagnostic | pre-autofill force called `11/12`, outcome `+0.0644`; post-autofill force called `12/12`, outcome `-0.0316` | park | Correct calls were possible only under force on a narrow remove-contact subset; mixed forced and natural diagnostics were negative or uncalled. |

## Force-call diagnostics
### Pre-autofill force
- Run: `outputs/v2_1_gap_closure_force_prepare_args12_20260504_2230/mechanism_12_20260504_223723`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_force_prepare_args12_20260504_2230/mechanism_12_20260504_223723/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_force_prepare_args12_20260504_2230/mechanism_12_20260504_223723/dashboard/task_focus.html`
- Outcome delta: `0.0644`
- Canonical delta: `-0.1380`
- Helper visible/called/VNC: `12 / 11 / 1`
- Called-subset outcome: `0.1157`
- Route mismatch qualified: `True`
- Finding: aggregate positive, but trace review showed helper outputs still abstained with missing inputs; gains were not cleanly attributable to usable helper outputs.

### Post-autofill force
- Run: `outputs/v2_1_gap_closure_force_prepare_args12_post_autofill_20260504_2250/mechanism_12_20260504_224507`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_force_prepare_args12_post_autofill_20260504_2250/mechanism_12_20260504_224507/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_force_prepare_args12_post_autofill_20260504_2250/mechanism_12_20260504_224507/dashboard/task_focus.html`
- Outcome delta: `-0.0316`
- Canonical delta: `-0.0967`
- Helper visible/called/VNC: `12 / 12 / 0`
- Called-subset outcome: `-0.0316`
- Finding: autofill produced valid `remove_contact` kwargs in 4 cases, but the full forced subset regressed. Relationship-update cases still abstained because updates were not safely inferable.

### Natural post-routing diagnostic
- Run: `outputs/v2_1_gap_closure_natural_prepare_args12_post_routing_20260504_2300/mechanism_12_20260504_224921`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_natural_prepare_args12_post_routing_20260504_2300/mechanism_12_20260504_224921/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_gap_closure_natural_prepare_args12_post_routing_20260504_2300/mechanism_12_20260504_224921/dashboard/task_focus.html`
- Outcome delta: `-0.0510`
- Canonical delta: `-0.2304`
- Helper visible/called/VNC: `12 / 0 / 12`
- Finding: no natural adoption after routing/affordance repair; visible-not-called subset regressed.

## Candidate decision
`prepare_side_effect_args_from_selected_record` should not advance. The viable concept is narrower: a future generated tool should combine visible candidate selection plus side-effect kwargs preparation with simple list/scalar inputs, or specialize to unique search-result remove/update workflows. A selected-record-only post-selection helper is too hard for the acting model to call naturally and is not additive over direct ToolSandbox use on this evidence.

Decision label: `candidate parked`
