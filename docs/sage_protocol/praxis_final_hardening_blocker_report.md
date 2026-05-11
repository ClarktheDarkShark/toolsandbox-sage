# Praxis Final-Hardening Blocker Report

Decision label: `BLOCKED: praxis_registry_only_side_effect_preservation_failures`

Praxis reproduced a positive registry-only outcome lift on matched formal500,
but the protected-base side-effect checker reported 13 helper side-effect
preservation failures. Per the final-hardening protocol, this stops promotion
review.

## Exact Failure Mode

- Run:
  `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731`
- Candidate side-effect report:
  `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731/candidate/full_benchmark_candidate_agent_gpt-4o-mini_user_GPT_4_o_2024_05_13_05_10_2026_22_38_10/side_effect_preservation_report.jsonl`
- Report SHA-256:
  `81bf6ee740368bc83f8444f5c608e108d352f5029533d52695d4b430d5fd1aaa`
- Runtime exceptions: `0`
- Helper side-effect preservation failures: `13`

## Failing Helpers And Scenarios

| Scenario | Helper |
| --- | --- |
| `modify_contact_with_message_recency` | `select_message_counterparty_for_contact_update` |
| `update_contact_relationship_with_relationship_3_distraction_tools` | `plan_contact_relationship_batch_update` |
| `update_contact_relationship_with_relationship_3_distraction_tools_arg_type_scrambled` | `plan_contact_relationship_batch_update` |
| `update_contact_relationship_with_relationship_twice_multiple_user_turn_3_distraction_tools_tool_description_scrambled` | `plan_contact_relationship_batch_update` |
| `add_reminder_content_and_weekday_delta_and_time_3_distraction_tools_tool_name_scrambled` | `next_weekday_time_to_timestamp` |
| `send_message_with_contact_content_cellular_off_3_distraction_tools_tool_name_scrambled` | `plan_send_message_contact_lookup` |
| `update_contact_relationship_with_relationship_3_distraction_tools_tool_name_scrambled` | `plan_contact_relationship_batch_update` |
| `update_contact_relationship_with_relationship_twice_multiple_user_turn_3_distraction_tools_tool_name_scrambled` | `plan_contact_relationship_batch_update` |
| `modify_contact_with_message_recency_all_tools` | `select_message_counterparty_for_contact_update` |
| `modify_contact_with_message_recency_alt` | `select_message_counterparty_for_contact_update` |
| `modify_contact_with_message_recency_alt_10_distraction_tools` | `select_message_counterparty_for_contact_update` |
| `modify_contact_with_message_recency_alt_3_distraction_tools` | `select_message_counterparty_for_contact_update` |
| `update_contact_relationship_with_relationship_alt_3_distraction_tools` | `plan_contact_relationship_batch_update` |

## Root Cause Classification

Root cause class: `helper_contract_or_bridge_policy_dependency`.

The frozen Praxis registry includes bridge-style helpers that produce selected
values or action plans for later original ToolSandbox calls. Under the
protected-base final-hardening runtime and side-effect checker, those helper
calls are treated as side-effect preservation failures in 13 scenarios. The
experimental source contains actor/router bridge and side-effect checker changes
that were intentionally not imported into this registry-only review. The result
therefore suggests one of two likely causes:

1. The helper contracts are not sufficiently pure/final-answer-ready for the
   protected-base checker to recognize preserved original side effects.
2. Praxis depends on experimental bridge/checker behavior and must be reviewed
   as a combined treatment rather than registry-only value.

No label leakage, expected-answer leakage, force-call leakage, or prior SAGE
trace reuse was found in the matched registry-only evidence path.

## Attempted Repairs In This Branch

No registry or runtime repair was applied after matched arms began. That was
intentional: code or registry changes after one formal arm would invalidate the
matched set. The branch stopped at classification and reporting.

Completed checks:

- Clean preflight before runs.
- Registry hash verification for best3, V2.6, and Praxis.
- Generation off.
- OpenAI response cache disabled.
- Candidate task cache off.
- Control cache used only for controls.
- Routing evidence disabled.
- Diagnostic force-call env vars absent.
- Matched formal500 arms completed with no code or registry changes between
  arms.

## Smallest Next Repair

Preferred registry-only repair:

1. Redesign the failing helpers to emit strictly side-effect-free, typed,
   final-action-ready outputs that make the subsequent original ToolSandbox
   side-effect call explicit and checker-visible.
2. Run narrow protected-base safety diagnostics on the failing scenario
   families only.
3. Require zero side-effect preservation failures before any new formal500.
4. Freeze the repaired registry and rerun matched best3/V2.6/repaired-Praxis
   validation from scratch.

Alternative combined-treatment review:

1. Import the minimum actor/router bridge and checker changes behind an
   explicit feature flag.
2. Audit the imported code for label access, scenario-ID hard-coding,
   expected-answer leakage, mtime-selected evidence, stale trace reuse, and
   force-call leakage.
3. Run ablations:
   best3 with bridge policy, V2.6 with bridge policy, Praxis with bridge
   policy, and Praxis with bridge policy disabled.
4. Rerun matched formal500 from scratch and require zero side-effect incidents.

Until one of those repairs succeeds, Praxis should remain promising but blocked
and should not be used for a protected final claim.
