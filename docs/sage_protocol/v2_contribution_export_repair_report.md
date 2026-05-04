# V2 Contribution Export Repair Report

## Objective
Create claim-grade helper contribution evidence for promotion and reporting.

## Files Changed
- `src/sage_ts/evaluation/helper_contribution.py`
- `scripts/run_sage_protocol.py`
- `tests/unit/test_helper_contribution.py`

## Implementation
- Added `build_helper_contribution_summary` and `write_helper_contribution_summary`.
- Standard protocol runs now write:
  - `outputs/<run>/helper_contribution_summary.json`
  - `artifacts/summaries/<run_name>/helper_contribution_summary.json`
- Protocol manifests and run records include contribution summary paths and accepted-but-uncalled tools.

## Export Fields
Per helper:
- visible/called/visible-not-called/failed-attempt/hidden-no-call scenarios
- canonical and outcome deltas for called, visible-not-called, hidden/no-call, failed-attempt subsets
- gains/regressions/preserved for each subset
- side-effect incidents
- runtime incidents
- retained vs newly generated origin

Run-level:
- accepted-but-uncalled tools
- retained-helper called tools
- newly generated-helper called tools
- registry size
- runtime bundle size
- cache/token metrics when available

## Tests
- `PYTHONPATH=src:. pytest tests/unit/test_helper_contribution.py tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- Result: `73 passed`.

## Commit Blocker
The worktree contains many unrelated pre-existing modified/untracked files. No commit was created to avoid mixing unrelated changes.

## Decision Label
contribution export ready
