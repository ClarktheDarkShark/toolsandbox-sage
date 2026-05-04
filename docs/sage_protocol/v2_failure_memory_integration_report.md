# V2 Failure Memory Integration Report

## Objective
Use failure memory mechanically in generation, candidate gating, and promotion without creating a name blacklist.

## Files Changed
- `src/sage_ts/adequacy/failure_memory.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/registry/promotion_gate.py`
- `tests/unit/test_failure_memory_integration.py`

## Implementation
- Generation prompt now receives relevant unresolved failure-memory context.
- Generated candidates must state mechanisms addressed and material repair rationale.
- Candidate gate can reject unresolved repeated mechanisms when given failure memory.
- Same-name rediscovery is allowed when the new spec explicitly addresses the mechanism with a material repair.
- Promotion gate blocks unresolved failure mechanisms.

## Tests
- Same-name rediscovery allowed when materially repaired.
- Unrepaired mechanism recurrence blocked.
- Promotion consults failure memory.
- Included in `73 passed` targeted suite.

## Commit Blocker
No commit created due unrelated dirty worktree.

## Decision Label
failure memory integrated
