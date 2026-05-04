# V2 Generation Contract Report

## Objective
Repair generated-tool contracts so accepted candidates carry enough evidence to support autonomous tool-evolution claims.

## Files Changed
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `tests/unit/test_tool_generator.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_online_birth.py`

## Contract Additions
Generated specs now support and prompt for:
- `diagnostic_only`
- `shortfall_cluster_evidence`
- `known_failure_mechanisms_addressed`

The generation prompt now distinguishes diagnostic candidates from claim-grade candidates. Non-diagnostic decisive candidates must name recurring cluster evidence and concrete failure mechanisms.

## Gate Additions
The candidate gate now rejects decisive non-diagnostic specs that lack:
- shortfall-cluster evidence
- known failure mechanisms addressed

Diagnostic decisive specs may lack cluster evidence, but they are not promotion evidence by themselves.

## Cache Safety
Tool generation cache key was bumped from `tool_generation_v5` to `tool_generation_v6` so stale completions do not satisfy the new contract accidentally.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- Result: `61 passed`.

## Decision Label
generation contract ready
