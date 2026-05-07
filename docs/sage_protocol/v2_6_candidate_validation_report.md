# V2.6 Candidate Validation Report

## Objective
Validate the accepted V2.6 candidate before broader runs, with special attention to schema, abstention, side-effect preservation, and canonical-route substitution accounting.

## Candidate
- Tool: `plan_contact_search_from_scalar_constraint`
- Registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## Validation Results
- Static/schema validation: PASS
- Output schema present: yes
- Positive triggers present: yes
- Negative triggers present: yes
- Held-out checks: 2
- Negative checks: 1
- Runtime smoke: PASS
- Live validation: accepted
- Positive usable outputs: 3
- Negative abstain outputs: 1
- Runtime incidents: 0
- Side-effect execution inside helper: 0
- Final side-effect ToolSandbox calls preserved: yes; helper only prepares `search_contacts` kwargs.

## Grading Accounting
- Classification: outcome-preserving but canonical-substituting.
- Canonical route risk: low.
- Live validation warning: `live_missing_expected_milestone_calls_replaced`.
- Interpretation: the helper may substitute deterministic query construction for intermediate canonical steps, but it preserves the downstream `search_contacts` route and does not execute final side effects.

## Callability Assessment
The accepted interface is intentionally simple:
- Required scalar inputs: `constraint_field`, `constraint_value`.
- No opaque dict payloads.
- Safe abstention when field or value is missing/unsupported.
- Output directly names `search_contacts` and kwargs only when safe.

## Pipeline Blocker Diagnosis
- Main blocker addressed: previous contact/action candidates were too broad and brittle.
- Remaining risk: adoption and VNC pollution, because the scalar search planner can be visible on many contact scenarios but may not always be called.

## Decision Label
`candidate ready for micro20`

## Exact Next Action
Run micro20 with best3 plus the scalar candidate, generation OFF, contribution export active, and negative cases included.
