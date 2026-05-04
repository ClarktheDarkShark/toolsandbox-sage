# V2 Promotion Gate Repair Report

## Objective
Prevent proof-passing but idle, diagnostic-only, harmful, or unresolved-failure candidates from being promoted by path convention.

## Files Changed
- `src/sage_ts/registry/promotion_gate.py`
- `scripts/check_promotion_gate.py`
- `tests/unit/test_promotion_gate.py`

## Implementation
- Added mechanical promotion decisions for `candidate`, `active`, and `frozen` lifecycle targets.
- Added CLI: `scripts/check_promotion_gate.py <registry> <helper_contribution_summary>`.
- Gate evaluates every registry entry against validation proof, contribution evidence, side-effect/runtime incidents, and failure memory.

## Promotion Requirements Enforced
- current validation proof pass
- non-diagnostic spec
- shortfall-cluster evidence
- positive and negative triggers
- safe abstain behavior
- downstream side-effect preservation when required
- actual later-task calls
- called-subset outcome delta non-negative when available
- visible-not-called rate <= `0.5`
- no runtime/side-effect incidents
- no unresolved failure-memory block

## Rejections/Parking
The gate parks accepted-but-uncalled, visible-but-never-called, harmful called-subset, diagnostic-only, and failure-memory-blocked tools.

## Tests
- Included in `73 passed` targeted suite.

## Commit Blocker
No commit created due unrelated dirty worktree.

## Decision Label
promotion gate ready
