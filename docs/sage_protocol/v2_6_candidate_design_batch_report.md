# V2.6 Candidate Design Batch Report

## Objective
Generate and choose candidate designs from enriched structured feedback packets, favoring cross-task abstractions that could reduce no-current-helper-fit beyond frozen best3 without side-effect harm.

## Files Changed
- `src/sage_ts/generation/tool_generator.py`
- `tests/unit/test_tool_generator.py`
- `artifacts/summaries/v2_6_cross_task_packets/latest_packets.json`
- `artifacts/summaries/v2_6_candidate_contact_action_lookup_generate/candidate_batch_summary.json`
- `artifacts/summaries/v2_6_candidate_contact_action_lookup_generate_second_pass/candidate_batch_summary.json`
- `artifacts/summaries/v2_6_candidate_contact_scalar_search_generate/candidate_batch_summary.json`
- `artifacts/summaries/v2_6_candidate_contact_scalar_search_casefix_generate/candidate_batch_summary.json`
- `artifacts/summaries/v2_6_candidate_contact_scalar_search_promptfix_generate/candidate_batch_summary.json`

## Feedback Mode Used
Mode B: enriched structured feedback packets. Mode B was selected because it produced actionable missing-capability, input, output, negative-case, and callability context without the cost of full execution-aware repair loops for every candidate.

## Candidate Designs Tested
1. `plan_contact_action_lookup_query`
   - Intended abstraction: contact/action lookup planner before side-effect tasks.
   - Rejected after two generated attempts.
   - Main failures: raw vs normalized phone handling, nonempty downstream search fields on abstain, and ambiguous downstream action labels.
   - Decision: split into a simpler scalar contact-search planner.

2. `plan_contact_search_from_scalar_constraint`
   - Intended abstraction: normalize scalar contact constraints into safe `search_contacts` kwargs.
   - Inputs: `constraint_field`, `constraint_value`.
   - Outputs: `should_call_search`, `search_tool_name`, `search_kwargs`, normalized fields, abstain reason.
   - Accepted after generation prompt repair.

## Generation Repair
The generator prompt now explicitly instructs contact scalar candidates to:
- Preserve E.164 phone normalization: strip non-digits; 11 digits starting with `1` -> `+` plus 11 digits; 10 digits -> `+1` plus 10 digits; never prepend `+1` to an 11-digit US number already starting with `1`.
- Preserve name and relationship case/spacing except trimming.
- Return an empty `search_tool_name` and empty kwargs when abstaining.

## Candidate Accepted
- Tool: `plan_contact_search_from_scalar_constraint`
- Source artifact: `artifacts/summaries/v2_6_candidate_contact_scalar_search_promptfix_generate/candidate_batch_summary.json`
- Candidate registry source: `artifacts/summaries/v2_6_candidate_contact_scalar_search_promptfix_generate/candidate_batch_registry/registry_manifest.json`
- Expanded pack registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## Pipeline Blocker Diagnosis
- Main blocker: bad tool schema/normalization detail in generated contracts.
- Repaired variable: candidate design and generator prompt specificity for scalar contact constraints.
- Not a benchmark patch: no scenario-name logic or hardcoded task outcomes were added.

## Decision Label
`candidate designs ready`

## Exact Next Action
Run callability/live validation and micro20 for the accepted scalar contact-search candidate before scaling.
