# SAGE V2.0 Candidate Triage Report

## Objective
Classify generated candidates from V2.0 discovery-60 and decide whether any can advance to frozen confirmation against best3.

## Source Run
- Run root: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640`
- Candidate run dir: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/candidate/mechanism_40_candidate_agent_gpt-4o-mini_user_gpt-4o-mini_05_04_2026_08_16_49`
- Candidate registry restored to pre-run best3: yes
- Failed-gate registry snapshot: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/registry_gate/registry_manifest_failed_gate.json`

## Triage Table
| candidate | classification | visible | called | visible-not-called | rationale |
|---|---|---:|---:|---:|---|
| `next_dependency_precondition_call` | diagnostic only | 2 | 0 | 2 | accepted by validation but called 0 times after visibility; cannot promote or confirm. |
| `next_service_tool_call` | reject |  |  |  | not accepted by validation/gating: unresolved_failure_memory:state_precondition_visible_not_called |
| `prepare_reminder_creation_args` | reject |  |  |  | not accepted by validation/gating: live_missing_expected_milestone_calls_replaced |
| `select_contact_field_by_constraint` | reject |  |  |  | not accepted by validation/gating: live_missing_expected_milestone_calls_replaced |
| `days_between_timestamps` | reject |  |  |  | not accepted by validation/gating: live_example_2_positive_unusable_output, live_missing_expected_milestone_calls_replaced |

## Decision
No candidate advances to confirmation-60. `next_dependency_precondition_call` is useful diagnostic evidence but cannot be promoted because it was accepted-but-uncalled. Rejected candidates did not pass validation/gating after one repair.

## Decision Label
`routing repair needed`

## Next Action
Repair routing/affordance for accepted dependency helpers and repair generation/live-validation grading-accounting metadata before the next discovery or fair-chance confirmation.
