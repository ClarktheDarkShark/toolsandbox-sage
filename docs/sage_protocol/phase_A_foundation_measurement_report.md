# Phase A Foundation Measurement Report

**Objective:** Verify registry claim-safety, scoring/spine audibility, reporting exports, and live protocol smoke execution on clean registry with generation OFF.

## Commands run
1. `python scripts/migrate_registry.py --check-only --registry artifacts/registry_manifest.json`
2. `python scripts/migrate_registry.py --check-only --registry artifacts/registry_manifest_pre_cleanup.json` (baseline pre-clean trace)
3. `set -a; . ./.secrets/env.sh; set +a; PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode transfer_40 --manifest outputs/splits/state_steps_transfer_smoke_4.json --agent gpt-4o-mini --generation-model gpt-4o-mini --base-tool-policy upstream --registry-dir artifacts --generation off --cache-mode write_only --output-root outputs/phase_A_smoke_reported_20260502`
4. `PYTHONPATH=src:. python scripts/export_phase_a_reporting.py --protocol-run-root outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601 --output-dir outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601/phase_A_reports`
5. Focused tests:
   - `PYTHONPATH=src:. python -m pytest tests/unit/test_outcome_score.py tests/unit/test_toolsandbox_adapter.py tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_export_phase_a_reporting.py`

## Files changed
- `scripts/export_phase_a_reporting.py` (artifact path list now includes `adjudication_packet.jsonl`)
- `tests/unit/test_outcome_score.py` (intermediate-message over-credit guard test added/updated)
- `tests/unit/test_export_phase_a_reporting.py` (artifact assertions updated)
- `docs/sage_protocol/final_task_success_audit.md` (audit file)
- `docs/sage_protocol/phase_A_foundation_measurement_report.md` (this report)
- `docs/sage_protocol/01_phase_A_foundation_measurement_provenance.md` (report filename/gating wording updated)

## Tests run
- `tests/unit/test_outcome_score.py`: 5 passed
- `tests/unit/test_toolsandbox_adapter.py`: 2 passed
- `tests/integration/test_toolsandbox_generated_tool_injection.py`: 9 passed
- `tests/unit/test_export_phase_a_reporting.py`: 1 passed

Total: 35 passed.

## Artifacts created
- `outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601/phase_A_reports/`
  - `protocol_manifest.json`
  - `canonical_score.json`
  - `final_task_success_score.json`
  - `exact_success.json`
  - `gains_regressions_preserved.json`
  - `tool_visibility_and_call_report.json`
  - `tool_applicable_subset_report.json`
  - `non_applicable_subset_report.json`
  - `route_mismatch_report.json`
  - `runtime_exceptions.json`
  - `side_effect_preservation_report.jsonl`
  - `confidence_intervals.json`
  - `adjudication_packet.jsonl`
- `outputs/phase_A_smoke_20260502_2/.../phase_A_reports/` (earlier smoke run smoke export from Phase A cleanup pass)

## Active registry status
- `python scripts/migrate_registry.py --check-only --registry artifacts/registry_manifest.json`
  - PASS entries: 1 (`prepare_reminder_creation_args`)
  - FAIL entries: 0
- backup exists at `artifacts/registry_manifest_pre_cleanup.json`
- failed legacy helpers are absent from active manifest:
  - `recency_to_timestamp_bounds`
  - `relative_day_time_to_timestamp`
  - `select_latest_record_by_timestamp`
  - `next_service_enablement_action`

## Final-task scoring audit summary
- Canonical score and final-task success are now separate outputs in report bundle.
- Exact success is separate from mean similarity.
- Intermediate message over-credit is blocked by scoring path using only final AGENT→USER message.
- See `docs/sage_protocol/final_task_success_audit.md` for complete question/answer matrix.

## Route-mismatch reporting status
- `route_mismatch_report.json` exists and is generated.
- For the tiny smoke set, mismatch count is `0`.

## Side-effect reporting status
- `side_effect_preservation_report.jsonl` is produced in phase report output.
- Final state summary is included per-task in `adjudication_packet.jsonl`.

## Confidence interval status
- `confidence_intervals.json` is generated for canonical and final-task deltas using bootstrap estimates.
- Example: `canonical.estimate = -0.0137`, `final_task.estimate = -0.0219` on the tiny smoke sample.

## Adjudication packet status
- `adjudication_packet.jsonl` is present with per-task task ids, final answers, final state summaries, key helper trace signals, and labels.

## Dashboard / live-run status
- Latest tiny smoke manifest: `outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601/protocol_manifest.json`
  - `generation_enabled = false`
  - `registry_dir = artifacts`
  - `dashboard_url = http://127.0.0.1:5520/outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601/dashboard/index.html`
  - `dashboard_task_focus_url = http://127.0.0.1:5520/outputs/phase_A_smoke_reported_20260502/transfer_40_20260502_165601/dashboard/task_focus.html`
  - `registry_manifest_digest_after_run = 1a0fde57443fc93c885fb5220dd8e6d45096d45ffbe82d39bedfdf4416d6e5cf`
- In transfer runs, loaded tools were `prepare_reminder_creation_args` only (`registry_tools` list), confirming 4 legacy FAIL helpers are excluded.

## Blockers
- None blocking Phase A deliverables.
- Protocol gate on tiny smoke is `false` (non-positive canonical delta and more regressions than gains), but this is expected for a small diagnostic 4-task smoke sample and does not invalidate the reporting/registry claims.

## Recommendation
- Write artifacts and proceed to Phase B after human review.
- Next: use this cleaned registry and phase-A reporting outputs as the fixed baseline for Phase B frozen-transfer planning.

## Decision
pass
