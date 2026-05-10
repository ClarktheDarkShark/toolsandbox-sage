# Next Loop Prep: `prepare_safe_action_or_abstain`

Experimental planning only. No long SAGE execution is started by this document.

## Target

Generate and test a side-effect-free tool family that prepares a safe next-action specification or recommends abstention when the task lacks information, lacks an available tool, violates a precondition, or has ambiguous targets.

This loop should address the largest remaining unsupported buckets:

| Bucket | Prior unsupported count | Design target |
| --- | ---: | --- |
| Safe insufficient-information / abstention | 119 tasks, 111 no visible helper | Missing-info and impossible-action classification. |
| Settings/device-state | 124 tasks, 80 no visible | Precondition sequence normalization. |
| Contact CRUD | 55 tasks, 35 no visible, 0 calls | Lookup/update/delete target readiness. |
| Reminder CRUD/scheduling | 36 tasks, 24 no visible | Recency/date/action-spec readiness. |
| Send-message preconditions | 8 tasks, all unsupported | Contact lookup, service state, and final send spec. |

## Proposed Tool Family

### `prepare_safe_action_or_abstain`

Input should be scalar/list oriented where possible:

- `task_intent`: short natural-language task summary visible to the agent.
- `available_actions`: list of visible side-effect tool names.
- `known_targets`: list of candidate record summaries, if any.
- `required_fields`: list such as `phone_number`, `person_id`, `timestamp`, `content`.
- `state_flags`: list of strings such as `wifi_off`, `cellular_off`, `low_battery_mode_on`.
- `constraints`: list of scalar constraints from the task.

Output should be final-answer-ready and machine-checkable:

```json
{
  "status": "ready|missing_information|blocked_by_state|unsupported_tool|ambiguous_target|not_applicable",
  "recommended_action": "tool_name_or_none",
  "required_preconditions": ["..."],
  "action_arguments": {"field": "value"},
  "abstain_reason": "short user-facing reason",
  "confidence": "high|medium|low"
}
```

### Narrow Siblings

- `prepare_contact_crud_action_or_abstain`
- `prepare_reminder_action_or_abstain`
- `prepare_send_message_action_or_abstain`
- `prepare_settings_state_action_or_abstain`

Siblings should be tested only if the general tool is too broad or undercalled.

## Safety Rules

- No side effects.
- No direct database writes.
- No hidden labels, scenario IDs, expected answers, or task-specific benchmark facts.
- Strong negative behavior when required fields or side-effect tools are missing.
- Never claim success; return only action readiness or abstain reason.
- Treat force-call diagnostics as diagnosis only, not promotion.

## Synthetic Minefield

Before any natural run, validate:

- Missing contact and no search tool available.
- Ambiguous contact with duplicate names.
- Cellular off before send-message.
- Requested contact deletion but no delete/remove tool visible.
- Reminder update with multiple latest candidates.
- Reminder scheduling with missing date or time.
- Impossible external-service lookup.
- Irrelevant task family where tool must return `not_applicable`.
- Tool-name scrambled variants where available action names are opaque.
- Empty records and wrong units.

## Progressive Run Plan

1. Build synthetic cases and static validation.
2. Targeted20 on two buckets only, preferably insufficient-info and send-message/settings preconditions.
3. If hidden or VNC, run force-exposure/force-call diagnostics on safe examples.
4. Repair metadata, schema, or output shape.
5. Expanded60 narrow run after natural calls appear.
6. Narrow100 only if expanded60 is positive and incidents remain zero.
7. Combine with Praxis only after narrow100 shows at least `+0.30` outcome lift on a bucket or clear positive rare-bucket called-subset evidence.
8. Broad validation only after the combined pack preserves Praxis-level safety and avoids context pollution.

## Success Criteria

- Natural calls, not only force calls.
- Positive called-subset outcome.
- Outcome lift on targeted bucket, with canonical/reference treated as secondary.
- Runtime exceptions `0`.
- Helper side-effect incidents `0`.
- Safe abstain behavior on missing-info minefields.
- No broad over-answering or false success claims.

## Initial Artifacts To Create Later

- Registry path: `artifacts/registry_experiments/gap_closure_lab/safe_action_or_abstain_loop/`
- Split path: `artifacts/experiment_manifests/gap_closure_lab/safe_action_or_abstain_loop/`
- Report path: `docs/sage_protocol/experiments/gap_closure_lab_safe_action_or_abstain_report.md`
- Synthetic validation path: `artifacts/experiment_manifests/gap_closure_lab/safe_action_or_abstain_loop/synthetic_minefield.json`
