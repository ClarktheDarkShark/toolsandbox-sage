# V2.6 Contact-Scalar Routing Audit

## Scope

Audit contact-scalar helper visibility before running the expanded registry on the original formal250 manifest. No tool logic or frozen best3 registry was changed.

## Helpers Audited

- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`

## Finding

The matched250 helper contribution summary showed acceptable targeted exposure for `plan_contact_lookup_query` and `extract_contact_field_from_search_result`, but high visible-not-called exposure for `plan_contact_search_from_scalar_constraint`.

Matched250 visible/called/VNC:

- `plan_contact_lookup_query`: `24 / 15 / 9`
- `extract_contact_field_from_search_result`: `24 / 7 / 17`
- `plan_contact_search_from_scalar_constraint`: `74 / 12 / 62`

`plan_contact_search_from_scalar_constraint` was visible on declared contact lookup/remove/send-contact families, but also on unrelated or weakly related tasks including contact creation, ID-only contact workflows, message recency, and send-by-phone-number tasks.

## Root Cause

The generic runtime scorer matched applicable task families against task strata using raw underscore tokens. Connector words such as `with` and `by`, plus broad domain terms such as `contact` and `message`, allowed long family labels to match unrelated tasks through weak two-token overlap.

Example before repair:

- Helper family: `send_message_with_contact_content_cellular_off`
- Scenario: `add_contact_with_name_and_phone_number`
- Shared weak terms through strata: `contact` plus connector/domain overlap
- Result: helper shown as `generic_relevance_score_passed`

## Repair

Changed `src/sage_ts/runtime/routing_scorer.py` so `_family_match`:

- removes connector stopwords before overlap matching
- requires stronger overlap for labels with more than two meaningful parts
- still preserves exact full-family/scenario substring matching

This is a generic routing repair, not a tool-name-specific suppression.

## Post-Repair Probe

For `plan_contact_search_from_scalar_constraint`:

- Hidden on `add_contact_with_name_and_phone_number`: `generic_relevance_score_insufficient`
- Hidden on `remove_contact_with_id`: `generic_relevance_score_insufficient`
- Hidden on `update_contact_with_id_and_phone_number`: `generic_relevance_score_insufficient`
- Hidden on `search_message_with_recency_latest`: `generic_relevance_score_insufficient`
- Hidden on `search_sender_phone_number_with_content`: `generic_relevance_score_insufficient`
- Hidden on `send_message_with_phone_number_and_content`: `generic_relevance_score_insufficient`
- Shown on `remove_contact_by_phone`: `generic_relevance_score_passed`
- Shown on `search_phone_number_with_name`: `generic_relevance_score_passed`
- Shown on `search_relationship_with_phone_number`: `generic_relevance_score_passed`
- Shown on `send_message_with_contact_content_cellular_off`: `generic_relevance_score_passed`

## Tests And Checks

```bash
PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_v2_6_feedback_packets.py -q
# 117 passed

PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json
# PASS: 6 active entries

PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json
# PASS: 3 active entries
```

## Decision Label

`routing repaired for original250`
