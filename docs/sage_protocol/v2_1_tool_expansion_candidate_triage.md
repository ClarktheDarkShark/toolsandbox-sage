# V2.1 Tool Expansion Candidate Triage

## Objective
Triage V2.1 generated candidates for confirmation eligibility while preserving the frozen best3 claim registry.

## Registry
- Candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835/registry_manifest.json`
- Registry check-only: `PASS`
- Frozen best3 registry modified: `no`

## Candidate Summary
| Candidate | Status | Natural Evidence | Force Evidence | Decision |
|---|---|---|---|---|
| `prepare_side_effect_args_from_selected_record` | accepted | visible/called/VNC `2 / 0 / 2` | after repairs visible/called/VNC/failed `12 / 8 / 4 / 0`; calls abstained with `missing_required_helper_inputs` | park; no confirmation60 |
| `select_visible_record_by_constraints` | rejected | n/a | n/a | reject; exact validation failed |
| `select_action_target_by_recency` | rejected | n/a | n/a | reject; exact validation and live validation failed |

## Triage Details
### `prepare_side_effect_args_from_selected_record`
- Family: `composite_workflow_helper`
- Intended value: prepare downstream ToolSandbox side-effect kwargs after a target record is selected.
- Natural discovery: accepted but uncalled.
- Initial force diagnostic found routing bug: hidden as `blocked_by_missing_downstream_original_tool` because composite helpers were treated as requiring every preserved downstream tool.
- Routing repair allowed one-of-many downstream tools.
- Second force diagnostic exposed the helper but calls failed with missing `selected_record` and `updates` arguments.
- Affordance repair added generic post-selection docstring guidance.
- Runtime safety repair converted missing required arguments into structured abstain outputs for abstain-capable generated helpers.
- Final force diagnostic produced calls but all inspected calls returned `missing_required_helper_inputs`; no usable downstream kwargs were produced.

Decision: park. The helper is not confirmation-ready because it has no natural calls and no positive non-abstaining force-call evidence.

### `select_visible_record_by_constraints`
- Family: `search_filter_ranking_helper`
- Failure: implementation did not satisfy deterministic validation examples.
- Positive mismatch: returned no record despite a matching visible contact.
- Negative mismatch: selected a record in an ambiguous tie case instead of abstaining.

Decision: reject. The tool idea remains plausible, but generated implementation quality is insufficient.

### `select_action_target_by_recency`
- Family: `search_filter_ranking_helper`
- Failure: exact validation mismatches for `tie_candidates` and `selected_id`.
- Live validation later failed with `NameError: name 'all' is not defined`.

Decision: reject. The lane remains plausible, but generation must produce safer, simpler selector code.

## Confirmation60 Decision
No candidate advances to confirmation60.

Reason: no candidate has both real adoption and positive, non-harmful called-subset evidence over frozen best3. The only accepted candidate was naturally uncalled and force-call diagnostics showed abstention, not successful side-effect argument preparation.

## What Worked
- Cohort quality gate held: broad 60, no near-duplicate dominance.
- Shortfall observations targeted the intended V2.1 lanes.
- Candidate repair and gate rejected bad selectors for substantive behavior issues.
- Runtime routing now handles one-of-many downstream side-effect tools for composite helpers.
- Missing-argument helper calls no longer become tool-call failures; they abstain safely.

## What Did Not Work
- Selector code generation still fails exact positive/tie validation.
- Composite side-effect-prep helpers require `selected_record` and `updates`, but the acting model does not pass them naturally.
- Force-call positive aggregate scores were confounded by best3 helper use; the new candidate did not show independent value.

## Decision Label
`generation contract repair needed`

## Exact Next Action
Do not run confirmation60. Repair V2.1 generation so selection/action helpers expose model-callable contracts, preferably by generating a selector that returns a compact `selected_record` payload and a downstream prep helper that can consume exactly that payload, with live validation requiring a non-abstaining positive call before acceptance.
