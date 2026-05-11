# Praxis Side-Effect Repair Report

Status: registry-only repair succeeded under matched formal500 review conditions.

This is a review/repair supplement. It does not modify protected final evidence,
the protected best3 registry, locked formal evidence, or final-package claim
artifacts.

## Branch And Inputs

- Repair branch: `repair/praxis-side-effect-zero`
- Base commit: `672af8ae6ea13770166e5f0e4e4dc01ece698497`
- Source review branch: `review/praxis-final-hardening`
- Experimental source commit reference only:
  `7793c8ca29ab4e121d302c777c4e4ad273226470`
- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Formal manifest SHA-256:
  `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- Repaired registry:
  `artifacts/praxis_safety_repair/registries/praxis_bridgepack_registry_only_repair_v2/registry_manifest.json`
- Repaired registry SHA-256:
  `24e5ca815c6f3c11a8b226f10abbfba3216f854a5dcb284df860c4131a01cc35`

Protected assets preserved: protected best3 registry, locked best3 evidence,
locked formal evidence, protected final summaries, and final-package claim
artifacts.

## Starting Blocker

The prior registry-only Praxis final-hardening review reproduced outcome lift
but reported 13 helper side-effect preservation failures:

- best3 outcome: `0.655285`
- V2.6 outcome: `0.664286`
- Praxis frozen outcome: `0.696169`
- Praxis-vs-best3 outcome diff: `+0.040884`, 95% CI
  `[0.004697, 0.078220]`, p `0.0283`
- Praxis runtime exceptions: `0`
- Praxis helper side-effect preservation failures: `13`

Promotion was correctly blocked until a zero-side-effect matched validation
could be run.

## Safety Autopsy

| Scenario group | Failing helper | Expected original side-effect tool | Actual helper output / subsequent calls | Preservation failure reason | Proposed repair | Registry-only possible |
| --- | --- | --- | --- | --- | --- | --- |
| `modify_contact_with_message_recency*` | `select_message_counterparty_for_contact_update` | `modify_contact` | Helper selected the message counterparty; actor later called `modify_contact`. | Helper contract was not checker-visible enough: selected target was useful, but downstream side-effect intent/arguments were not explicit enough for the protected-base checker. | Add scalar `update_fields_are_visible`, explicit `should_call_tool`, `downstream_tool_name=modify_contact`, selected `person_id`, and abstain when no visible update fields exist. | Yes |
| `update_contact_relationship_with_relationship*` | `plan_contact_relationship_batch_update` | `modify_contact` for each selected contact | Helper first emitted `search_required`; after `search_contacts`, actor called helper and multiple `modify_contact` calls in the same assistant tool-call batch. | Protected-base checker sees helper results after the assistant batch; same-batch `modify_contact` calls cannot satisfy a later side-effect preservation requirement. | v1 tried stronger metadata instructing helper-alone then modify-contact-next; natural actor still batched calls. v2 retired the helper for registry-only review. | No, not without bridge/checker policy |
| `add_reminder_content_and_weekday_delta_and_time_*tool_name_scrambled` | `next_weekday_time_to_timestamp` | `add_reminder` or `modify_reminder` | Scrambled execution name returned a resolved timestamp and actor called scrambled reminder tool. | Checker alias mismatch on scrambled tool-name variants. | Add explicit `should_call_tool` for normal calls and suppress helper on `tool_name_scrambled` variants for registry-only review. | Yes |
| `send_message_with_contact_content_cellular_off_*tool_name_scrambled` | `plan_send_message_contact_lookup` | `search_contacts`, then `send_message_with_phone_number`, then cellular enable/retry if needed | Scrambled helper planned contact lookup; actor searched contacts, attempted send, enabled cellular, and retried send. | Checker alias mismatch on scrambled tool-name variants. | Keep helper side-effect-free and suppress on `tool_name_scrambled` variants for registry-only review. | Yes |

Classification: the blocker was mixed `helper_contract_or_bridge_policy_dependency`.
Most failures were repairable by making helper contracts explicit and suppressing
scrambled-name alias-risk cases. The relationship batch helper exposed a
protected-base checker limitation around same-assistant batching, so it was
parked rather than silently importing bridge policy.

## Repair Iterations

### Repair v1

- Path:
  `artifacts/praxis_safety_repair/registries/praxis_bridgepack_registry_only_repair_v1/registry_manifest.json`
- SHA-256:
  `83ec3734dfda2b3ab756e6ba3ed947a3e6a9864b18508a9fa9d75e6dc14aa733`
- Added checker-visible downstream-action fields for the contact-update
  counterparty helper.
- Added explicit `should_call_tool` fields for reminder timestamp and
  relationship batch planning.
- Added negative triggers for scrambled tool-name variants.

v1 failed targeted safety because `plan_contact_relationship_batch_update`
still induced same-batch helper plus `modify_contact` calls.

### Repair v2

- Path:
  `artifacts/praxis_safety_repair/registries/praxis_bridgepack_registry_only_repair_v2/registry_manifest.json`
- SHA-256:
  `24e5ca815c6f3c11a8b226f10abbfba3216f854a5dcb284df860c4131a01cc35`
- Active entries: `12`
- Retired diagnostic entry: `plan_contact_relationship_batch_update`

v2 carried forward the checker-visible contract repairs, suppressed
scrambled-name alias-risk routes for registry-only review, and parked the
relationship batch helper as `retired=true` / `diagnostic_only=true`.

## Narrow Safety Diagnostics

| Diagnostic | Manifest / run | Result |
| --- | --- | --- |
| 20 minefield checks | `artifacts/praxis_safety_repair/repair_v2_minefield_checks.json` | 20/20 passed |
| Targeted77 family diagnostic | `outputs/praxis_safety_repair/registry_only_repair_v2_targeted77/mechanism_40_20260511_012403` | Runtime exceptions `0`; helper side-effect preservation failures `0`; candidate outcome `0.662101`; control cache `77 cached / 0 fresh` |
| Exact13 final-style diagnostic | `outputs/praxis_safety_repair/registry_only_repair_v2_exact13_disabled/mechanism_40_20260511_014626` | Runtime exceptions `0`; helper side-effect preservation failures `0`; candidate outcome `0.610709`; outcome delta `+0.264650`; control cache `13 cached / 0 fresh`; routing evidence disabled |

Minefield coverage included ambiguous contact matches, missing fields, duplicate
names, missing update values, missing relationship values, missing recipient or
message content, reminder missing date/time, scrambled tool-name variants,
original side-effect tool absence, and irrelevant task families.

## Matched Formal500 Validation

Clean preflight before matched arms:
`artifacts/praxis_safety_repair/preflight/preflight_registry_only_repair_v2_formal500.json`

Preflight SHA-256:
`0a1aa49d166009fac89dde025d0c2b44784cb9f6c6bdd70254d0093225c016fb`

Run controls:

- Generation: off.
- OpenAI response cache: disabled.
- Candidate/SAGE task cache: off.
- Control cache: `use-if-eligible`.
- Controls: `500 cached / 0 fresh` in every arm.
- Control cache manifest hash:
  `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Routing evidence: disabled.
- Diagnostic force-call env vars: absent.
- Low-quality override: absent.
- No code or registry changes occurred between matched arms.

| Arm | Run root | Outcome | Run-vs-control outcome lift | Canonical | Exact successes | Runtime exceptions | Helper side-effect failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best3 reference | `outputs/praxis_safety_repair/formal500_registry_only_v2/best3_reference_formal500/full_benchmark_20260511_015634` | 0.659956 | 0.065084 | 0.704683 | 90 | 0 | 0 |
| V2.6 reference | `outputs/praxis_safety_repair/formal500_registry_only_v2/v2_6_reference_formal500/full_benchmark_20260511_034215` | 0.668039 | 0.073167 | 0.728769 | 97 | 0 | 0 |
| Praxis repaired registry-only v2 | `outputs/praxis_safety_repair/formal500_registry_only_v2/praxis_repair_v2_formal500/full_benchmark_20260511_064006` | 0.706948 | 0.112076 | 0.724125 | 109 | 0 | 0 |

Pairwise outcome:

- Praxis-vs-best3: `+0.046991`, 95% CI `[0.008387, 0.086278]`, p `0.0187`.
- Praxis-vs-V2.6: `+0.038909`, 95% CI `[0.001856, 0.075806]`, p `0.0463`.

Full statistics:
`docs/sage_protocol/praxis_repaired_matched_formal500_statistical_report.md`
and
`artifacts/praxis_safety_repair/praxis_repaired_matched_formal500_statistics.json`.

## Dashboard Checks

- Repaired Praxis standard dashboard opened in the in-app browser with zero
  console errors.
- Repaired Praxis Task Focus dashboard opened in the in-app browser with zero
  console errors.
- Task Compare was not generated by this run.

## Safety And Leakage

- Runtime exceptions: `0` for best3, V2.6, and repaired Praxis.
- Helper side-effect preservation failures: `0` for best3, V2.6, and repaired
  Praxis.
- Helper runtime incidents: none reported in contribution summaries.
- Candidate/SAGE arms were fresh.
- Control cache was used only for control arms.
- No prior SAGE traces were reused as candidate outcome evidence.
- No label, scenario-ID, expected-answer, task-string, mtime-selected routing
  evidence, or force-call leakage was found.

## Decision

Registry-only repair succeeded. Combined actor/router bridge-policy review was
not needed for this repair branch because the repaired registry passed matched
formal500 safety and outcome checks under protected-base runtime.

Recommendation: protected-claim update review is now justified for repaired
Praxis as a registry-only helper-contract repair. This branch does not itself
modify protected final claim artifacts.
