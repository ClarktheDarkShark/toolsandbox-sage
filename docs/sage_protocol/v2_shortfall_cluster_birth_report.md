# V2 Shortfall-Cluster Birth Report

## Objective
Make online birth cluster-aware so claim-grade generation is not driven by one-off or near-duplicate recurrence.

## Files Changed
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/generation/tool_generator.py`
- `tests/unit/test_online_birth.py`

## Implementation
- Online birth now tracks, per canonical shortfall mechanism:
  - scenarios
  - base task families
  - near-duplicate-only status
  - failed/repeated failed calls
  - inadequacy signals
  - current helper fit
  - positive/negative applicability example counts
- Generation prompt now receives `shortfall_cluster_context`.
- If a cluster is single-family / near-duplicate-only, generated candidates are marked `diagnostic_only=True` before validation/storage.
- Non-diagnostic birth requires recurrence plus at least two distinct base task families.
- Candidate gate already verifies non-diagnostic decisive specs cite shortfall-cluster evidence.
- Promotion gate already requires later adoption/value evidence.

## Tests
- Near-duplicate-only birth is stored as diagnostic-only.
- Existing online-birth recurrence/retry tests still pass.
- Included in `73 passed` targeted suite.

## Commit Blocker
No commit created due unrelated dirty worktree.

## Decision Label
cluster birth ready
