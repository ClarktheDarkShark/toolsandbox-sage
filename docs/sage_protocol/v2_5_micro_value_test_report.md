# V2.5 Micro Value Test Report

## Objective
Test whether the first V2.5 tool-foundry candidates are callable, tool-driven, and plausibly additive over frozen best3 before any additive60 run.

## Files Changed
- `src/sage_ts/evaluation/control_baseline_cache.py`
- `tests/unit/test_control_baseline_cache.py`
- `scripts/build_v2_5_tool_foundry_artifacts.py`
- `artifacts/registry_candidates/v2_5_temperature_answer_scalar/registry_manifest.json`
- `docs/sage_protocol/v2_5_*`

## Cache Repair
Control cache compatibility is now task-level. `manifest_checksum` is still stored for provenance, but no longer resets eligibility. Compatibility still requires matching scenario checksum, initial-state checksum, model metadata, model parameters, prompt hashes, runner/scorer/ToolSandbox versions, and base-tool policy.

Evidence after repair:
- Best3-only micro: control source `mixed`, cached/fresh `17 / 3`.
- Payload answer-helper micro: control source `mixed`, cached/fresh `17 / 3`.
- Scalar repaired helper micro: control source `mixed`, cached/fresh `19 / 1`.

## Candidate Batch
- Batch summary: `artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/candidate_batch_summary.json`
- Batch registry: `artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/candidate_batch_registry/registry_manifest.json`
- Tools proposed / accepted / rejected: `2 / 2 / 0`
- Accepted: `resolve_temperature_answer_unit`, `prepare_temperature_conversion_args`

## Micro Runs

### Best3-only comparison
- Run: `outputs/v2_5_micro_temperature_best3_only_cached_20260506_113421/mechanism_40_20260506_113425`
- Dashboards: `http://127.0.0.1:5629/outputs/v2_5_micro_temperature_best3_only_cached_20260506_113421/mechanism_40_20260506_113425/dashboard/index.html`, `http://127.0.0.1:5629/outputs/v2_5_micro_temperature_best3_only_cached_20260506_113421/mechanism_40_20260506_113425/dashboard/task_focus.html`
- Control cache: `mixed`, cached/fresh `17 / 3`
- Outcome delta: `+0.0272`
- Canonical delta: `+0.0532`
- Exact successes: `4 -> 6`
- Outcome gains/regressions/preserved: `6 / 6 / 4`

### Payload-shaped `resolve_temperature_answer_unit`
- Run: `outputs/v2_5_micro_temperature_answer_only_cached_20260506_112638/mechanism_40_20260506_112641`
- Dashboards: `http://127.0.0.1:5628/outputs/v2_5_micro_temperature_answer_only_cached_20260506_112638/mechanism_40_20260506_112641/dashboard/index.html`, `http://127.0.0.1:5628/outputs/v2_5_micro_temperature_answer_only_cached_20260506_112638/mechanism_40_20260506_112641/dashboard/task_focus.html`
- Control cache: `mixed`, cached/fresh `17 / 3`
- Outcome delta: `+0.0916`
- Canonical delta: `+0.0829`
- Exact successes: `4 -> 7`
- Helper visible/called/VNC: `8 / 1 / 7`
- Called-subset outcome delta: `+0.3333`
- Blocker: callability/adoption. Trace showed the actor called the helper with only `target_unit`, omitting required `weather_payload`.

### Scalar repaired `resolve_temperature_answer_unit`
- Registry: `artifacts/registry_candidates/v2_5_temperature_answer_scalar/registry_manifest.json`
- Registry SHA-256: `854ec5fec66002dc14f64c60247e517c7f73b06a2cd63f1236f9be84afa5922a`
- Run: `outputs/v2_5_micro_temperature_scalar_repair_cached_20260506_114758/mechanism_40_20260506_114803`
- Dashboards: `http://127.0.0.1:5630/outputs/v2_5_micro_temperature_scalar_repair_cached_20260506_114758/mechanism_40_20260506_114803/dashboard/index.html`, `http://127.0.0.1:5630/outputs/v2_5_micro_temperature_scalar_repair_cached_20260506_114758/mechanism_40_20260506_114803/dashboard/task_focus.html`
- Control cache: `mixed`, cached/fresh `19 / 1`
- Outcome delta: `-0.0579`
- Canonical delta: `+0.0080`
- Exact successes: `4 -> 7`
- Outcome gains/regressions/preserved: `4 / 10 / 2`
- Helper visible/called/VNC: `8 / 5 / 3`
- Called-subset outcome delta: `-0.1428`
- Called-subset canonical delta: `-0.4033`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

## Interpretation
The scalar repair solved the callability blocker: the tool was naturally called with correct scalar arguments and returned usable conversions. Once callability was fair, the concept failed the primary metric. The helper is therefore a value failure, not merely a routing failure.

The outcome/canonical mismatch is documented: the helper can replace `unit_conversion`, but route substitution does not rescue a negative called-subset outcome. This candidate should not advance to additive60.

## Tests And Checks
- `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> `61 passed`
- `PYTHONPATH=src:. pytest tests/unit/test_dashboard_exporters.py -q` -> `11 passed`
- `PYTHONPATH=src:. python -m py_compile scripts/build_v2_5_tool_foundry_artifacts.py src/sage_ts/evaluation/control_baseline_cache.py src/sage_ts/dashboard/task_focus_template.py` -> `PASS`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_5_temperature_answer_scalar/registry_manifest.json` -> `PASS`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/candidate_batch_registry/registry_manifest.json` -> `PASS`

## Decision Label
`candidate concept negative`

## Exact Next Action
Park the temperature unit answer lane. Continue V2.5 only with a different non-parked cluster that has higher additive-over-best3 potential; do not run additive60 for `resolve_temperature_answer_unit` or `prepare_temperature_conversion_args`.
