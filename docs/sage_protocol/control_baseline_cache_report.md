# Control Baseline Cache Report

## Objective
Implement a conservative baseline/control-arm cache so unchanged control tasks stop consuming LLM/API calls once at least three compatible completed control runs exist. SAGE/candidate runs are never cached or bypassed.

## Files Changed
- `src/sage_ts/evaluation/control_baseline_cache.py`
- `scripts/run_sage_protocol.py`
- `src/sage_ts/dashboard/exporters.py`
- `src/sage_ts/dashboard/template.py`
- `tests/unit/test_control_baseline_cache.py`
- `tests/unit/test_dashboard_exporters.py`
- `docs/sage_protocol/control_baseline_cache_report.md`

## Cache Policy
Cache root:
- `artifacts/baselines/control_task_baselines/cache_manifest.json`
- `artifacts/baselines/control_task_baselines/index.jsonl`
- `artifacts/baselines/control_task_baselines/records/`

The cache directory and empty authoritative manifest/index were created. No
historical baseline scores were imported.

A cached control is eligible only when all compatibility fields match and at least 3 valid completed control records exist. Compatibility includes scenario checksum, initial-state checksum, agent/user model metadata, model parameter hash, prompt hashes, runner version, scorer version, ToolSandbox version, source manifest checksum, and base-tool policy.

Eligible cached controls use mean canonical and outcome scores across compatible records and retain count/variance metadata. Runtime-exception records and side-effect-violation records are ineligible. Final-state hashes use ToolSandbox `execution_context.json` when exported, with an explicit outcome-check fallback marker otherwise.

## Runner Flags
Implemented on `scripts/run_sage_protocol.py`:
- `--control-cache off`
- `--control-cache collect`
- `--control-cache use-if-eligible` default
- `--control-cache refresh`
- `--control-cache strict`
- `--control-cache-root <path>`

The cache is control-arm only. Candidate/SAGE arms always run normally.

## Reporting And Dashboard
Every protocol run now writes `control_cache_report.json` at the run root and control run directory. The protocol manifest, run ledger entry, paired comparison, and campaign events include cache source/count/hash fields.

Dashboard data now includes `control_cache` and per-scenario `control_cache_source`. The main dashboard displays `control source: cached` on cached control rows.

## Research Validity Protections
- No past pre-implementation scores are imported.
- Cached availability is not used for cohort selection.
- Cohort quality gates still run before cache use and remain independent.
- Strict compatibility invalidates cache use when model, prompt, scorer, runner, scenario, initial state, manifest, base-tool policy, or ToolSandbox version changes.
- Formal runs can be fresh, strict/frozen-cache, or clearly reported mixed; cached controls are never silent.
- Cached-control variance is exported so downstream confidence intervals can account for baseline variance.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py tests/unit/test_dashboard_exporters.py -q` -> 17 passed
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py -q` -> 6 passed after final cache-field tightening
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> 63 passed
- `PYTHONPATH=src:. pytest tests/unit/test_protocol_generation_policy.py -q` -> 8 passed
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/active_registry_phase_ready.json` -> PASS, 1 active entry, 0 FAIL
- `PYTHONPATH=src:. python -m py_compile scripts/run_sage_protocol.py src/sage_ts/evaluation/control_baseline_cache.py src/sage_ts/dashboard/exporters.py` -> PASS
- `PYTHONPATH=src:. python scripts/run_sage_protocol.py --help` -> PASS, cache flags present

## Git Note
No commit was created because the worktree contains many pre-existing unrelated modified/untracked files, including files also touched by this cache integration. Committing now would risk mixing unrelated prior work with this cache change.

## Decision Label
control baseline cache ready
