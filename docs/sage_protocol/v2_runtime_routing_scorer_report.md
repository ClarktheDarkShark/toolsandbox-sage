# V2 Runtime Routing Scorer Report

## Objective
Make runtime exposure primarily generic and bounded rather than primarily tool-name-specific.

## Files Changed
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/adapters/sage_run_adapter.py`
- `tests/unit/test_runtime_routing_scorer.py`

## Implementation
- Added generic runtime routing scorer using:
  - positive triggers
  - negative triggers
  - applicable task families
  - task strata / helper triggers
  - side-effect preservation metadata
  - abstain behavior
- Tool-name-specific rules remain only as compatibility fallback when generic score defers.
- Runtime generated-helper bundle is capped at `5` helpers.
- Visibility logs include `routing_decisions` explaining shown/hidden/deprioritized tools.

## Routing Decision Reasons
- `generic_relevance_score_passed`
- `blocked_by_negative_trigger`
- `generic_relevance_score_insufficient`
- `blocked_by_context_budget`
- compatibility fallback reasons where generic scoring defers

## Tests
- Positive trigger shows helper.
- Negative trigger hides helper.
- Runtime bundle cap deprioritizes excess helpers.
- Included in `73 passed` targeted suite.

## Commit Blocker
No commit created due unrelated dirty worktree.

## Decision Label
runtime routing ready
