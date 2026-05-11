# Praxis Treatment Dependency Audit

Status: registry-only outcome lift reproduced; protected-claim review blocked
by side-effect preservation failures.

This is a final-hardening review artifact only. It does not modify protected
best3 evidence, locked formal evidence, final-package claim artifacts, or the
protected best3 registry.

## Branch Lineage

- Review branch: `review/praxis-final-hardening`
- Base commit: `2898c7e502ec75ad5e1fc65c5ffe7a80f5605f4a`
- Experimental source commit: `7793c8ca29ab4e121d302c777c4e4ad273226470`
- Setup commit used for matched validation:
  `cfe35647dbbb703b4508a709f75dfee0f1f85036`
- Lineage manifest: `artifacts/praxis_final_hardening/lineage_manifest.json`

## Imported Review Inputs

| Input | Review path | SHA-256 |
| --- | --- | --- |
| best3 reference copy | `artifacts/praxis_final_hardening/registries/best3_reference/registry_manifest.json` | `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf` |
| V2.6 reference copy | `artifacts/praxis_final_hardening/registries/v2_6_reference/registry_manifest.json` | `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582` |
| Praxis frozen candidate | `artifacts/praxis_final_hardening/registries/praxis_bridgepack_frozen_candidate/registry_manifest.json` | `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349` |
| Locked experimental summary | `artifacts/praxis_final_hardening/source_summaries/praxis_formal500_locked_summary.json` | `41db7fed0e0997cfb691791abca59d47941a2f076951153382b17df3242e2dcc` |

The review branch also imports the task-level control-baseline cache policy from
the experimental source. This is a cache/harness dependency, not a candidate
tool treatment. It is control-arm-only, requires at least three valid completed
control records per task, and matches on task name, agent model, user model, and
base tool policy.

## Intentionally Not Imported

- Experimental `scripts/run_sage_protocol.py` changes. The protected-base
  script retains final-hardening safeguards for routing-evidence controls and
  diagnostic-force checks.
- Experimental actor/router bridge policy in
  `src/sage_ts/adapters/openai_toolsandbox_roles.py`.
- Experimental final-answer retention and bridge-follow-up policy.
- Experimental scrambled tool-name compatibility changes.
- Experimental side-effect preservation checker changes.
- Experimental scoring changes in `src/sage_ts/evaluation/outcome_score.py`.
- Experimental routing/contribution changes that alter routing evidence
  behavior.
- Experimental dashboard/export changes.

These exclusions make the matched formal500 run a registry-only treatment test
under the protected-base final-hardening runtime.

## Praxis Registry Contents

The frozen Praxis registry contains 13 active retained helpers:

- `days_between_timestamps`
- `next_weekday_time_to_timestamp`
- `plan_contact_lookup_query`
- `plan_contact_relationship_batch_update`
- `plan_contact_search_from_scalar_constraint`
- `plan_device_state_action_sequence_v3`
- `plan_send_message_contact_lookup`
- `relative_day_time_to_timestamp`
- `relative_weeks_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_message_content_by_recency`
- `select_message_counterparty_for_contact_update`
- `select_record_by_timestamp_extreme`

This includes best3/V2.6 inherited helpers plus recency, scheduling,
device-state, send-message precondition, and contact bridge helpers.

## Experimental Diff Findings

- Actor/router bridge changes exist in the experimental source. They add
  domain-specific actor policy text, scrambled tool-name compatibility, device
  state bridge completions, CRUD bridge behavior, and final-response retention
  behavior.
- Side-effect preservation checker changes exist in the experimental source,
  mostly around trace-based follow-up validation and selection-only bridges.
- Cache/scoring changes exist in the experimental source. The review branch
  imports only the task-level control-cache change.
- Routing evidence safeguards are preserved from the protected base and final
  validation uses `--routing-evidence-mode disabled`.
- Diagnostic force-call paths are blocked by preflight and were not used.
- No hard-coded expected answers, truth labels, or prior SAGE trace outcomes
  were found in the imported registry copies or the imported cache policy.

## Leakage Review

The frozen registries contain provenance fields such as `birth_scenario` and
task-family labels. The runtime uses scenario names for existing retained-tool
visibility heuristics in the same way for best3, V2.6, and Praxis. This is not
truth-label or expected-answer access, but it is recorded as a routing
dependency and limitation. No tool code was found to contain expected answers,
hidden truth labels, or prior SAGE trace outcomes. The formal comparison used
the same frozen manifest and scenario order for all arms, with no scenario
selection based on cache availability.

## Matched Formal500 Classification

Praxis reproduced an outcome lift under the registry-only treatment:

- Praxis outcome minus best3 outcome: `+0.040884`
- Praxis outcome minus V2.6 outcome: `+0.031883`
- Praxis runtime exceptions: `0`
- Praxis helper side-effect preservation failures: `13`

The side-effect failures are concentrated in bridge-style helpers:

- `select_message_counterparty_for_contact_update`
- `plan_contact_relationship_batch_update`
- `next_weekday_time_to_timestamp`
- `plan_send_message_contact_lookup`

This indicates either helper contract mismatch against the protected-base
checker or a dependency on the experimental bridge/checker behavior that was
not imported into the registry-only review.

## Treatment Answer

Praxis is not classifiable as protected-claim-ready registry-only value.

The correct classification after this review is:

1. Registry-only outcome lift: reproduced.
2. Actor/router bridge-policy improvement: not imported in this run.
3. Registry plus bridge-policy treatment: plausible but unvalidated.
4. Harness/scoring/cache artifact: control-cache policy was imported and used
   only for controls; candidate-vs-candidate comparisons still show Praxis
   positive against best3 and V2.6, so the observed candidate lift is not solely
   a run-vs-control cache artifact.
5. Safety status: blocked by protected-base side-effect preservation failures.

Any future protected review must either repair the registry-only helpers or
explicitly validate a combined registry plus bridge-policy/checker treatment
with zero side-effect incidents.
