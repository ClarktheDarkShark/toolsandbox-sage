# Phase B Current Helper Frozen Reuse

## Objective
Validate frozen-registry reuse for `prepare_reminder_creation_args` under transfer_40 with generation OFF.

## Commands Run
1. `python scripts/migrate_registry.py --check-only --registry artifacts/registry_manifest.json`
2. `python scripts/run_sage_protocol.py --mode transfer_40 --manifest outputs/splits/prepare_reminder_creation_args_replay6.json --agent gpt-4o-mini --generation-model gpt-4o-mini --base-tool-policy upstream --registry-dir artifacts --generation off --cache-mode write_only --output-root outputs/phase_B_tiny_reminder_replay6 --dashboard-port 5520`
3. `python scripts/run_sage_protocol.py --mode transfer_40 --manifest outputs/splits/phase_B_nearby_reminder12.json --agent gpt-4o-mini --generation-model gpt-4o-mini --base-tool-policy upstream --registry-dir artifacts --generation off --cache-mode write_only --output-root outputs/phase_B_nearby_reminder_cohort --dashboard-port 5520`

## Files Changed
- `docs/sage_protocol/phase_B_current_helper_frozen_reuse_report.md` (new)

No source code changes were made during benchmark runs.

## Tests and Validation Run
- Frozen preflight proof checked via `migrate_registry.py --check-only`.
- Tiny smoke benchmark executed (6 scenarios).
- Nearby frozen cohort benchmark executed (12 scenarios).
- No focused unit/integration tests run in this phase since no code changes were made.

## Artifacts Created
- Tiny smoke: `outputs/phase_B_tiny_reminder_replay6/transfer_40_20260502_171214/`
- Nearby cohort: `outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/`
- Included files: `protocol_manifest.json`, `paired_comparison.json`, `cohort_preflight_report.json`, `cohort_diversity_report.json`, `dashboard_urls.json`, and run manifests.

## Dashboard URLs
- Tiny smoke dashboard: `http://127.0.0.1:5520/outputs/phase_B_tiny_reminder_replay6/transfer_40_20260502_171214/dashboard/index.html`
- Tiny smoke task-focus dashboard: `http://127.0.0.1:5520/outputs/phase_B_tiny_reminder_replay6/transfer_40_20260502_171214/dashboard/task_focus.html`
- Nearby cohort dashboard: `http://127.0.0.1:5520/outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/dashboard/index.html`
- Nearby cohort task-focus dashboard: `http://127.0.0.1:5520/outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/dashboard/task_focus.html`

## Active Registry Status
- Preflight check result: PASS
- PASS entries: `1`
- FAIL entries: `0`
- Active helper present: `prepare_reminder_creation_args`
- Legacy failed helpers remain excluded (`recency_to_timestamp_bounds`, `relative_day_time_to_timestamp`, `select_latest_record_by_timestamp`, `next_service_enablement_action`).

## Generation Mode
- `generation` set to `off` for all phase B protocol runs.

## Frozen Reuse Preflight
- Registry check passed for `artifacts/registry_manifest.json`.
- `has_current_validation_proof` satisfied at check time.
- Active registry snapshot captured and restored automatically in run gates.
- Cohort preflight report generated and passed quality checks (`should_block: false`, `decision_use: suitable_for_early_value_only`).

## Tiny Frozen Smoke Result
- Output: `outputs/phase_B_tiny_reminder_replay6/transfer_40_20260502_171214`
- Cohort type: 6-scenario reminder-focused smoke.
- Canonical control score: `0.45`
- Canonical SAGE score: `0.7572141144`
- Canonical delta: `+0.3072141144`
- Final-task control score: `0.0148589066`
- Final-task SAGE score: `0.2617114455`
- Final-task delta: `+0.2468525389`
- Exact successes control: `0`
- Exact successes SAGE: `0`
- Gains/regressions/preserved: `4 / 2 / 0`
- Helper visible count: `4`
- Helper called count: `3`
- Visible-but-not-called count: `1`
- Modify/search hidden count: `2` (modify/search negatives were not in helper list)
- Runtime exceptions: `0`
- Side-effect violations: `0`
- Route mismatch: no mismatch-report artifact emitted by this run (no explicit mismatch section in phase artifacts).

## Nearby Frozen Cohort Result
- Output: `outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552`
- Manifest type: `prepare_reminder_creation_args_replay`
- Scenario count: `12`
- Cohort diversity summary: `suitable_for_early_value_only` (7 distinct base families, max family share 0.25).
- Control scenario: `12`
- Candidate scenario: `12`
- Canonical control score: `0.6611111111`
- Canonical SAGE score: `0.5064634211`
- Canonical delta: `-0.1546476900`
- Final-task control score: `0.5214375731`
- Final-task SAGE score: `0.0606060606`
- Final-task delta: `-0.4608315125`
- Exact successes control: `5`
- Exact successes SAGE: `0`
- Gains: `4`
- Regressions: `5`
- Preserved: `3`
- Helper visible count: `9`
- Helper called count: `9`
- Visible-but-not-called count: `0`
- Modify/search hidden count: `2`
- Runtime exceptions: `0`
- Side-effect violations: `0`
- Turn change: candidate total turns `143`, control total turns `166` (`-23` turns)
- Failed tool calls avoided: `0` (`generated_tool_failed_scenarios: 0`)
- Helper-caused regressions: 5 in helper-attributed creation positives
- Non-helper/stochastic regressions: not observed separately in this run
- Route mismatch summary: no explicit route-mismatch report file; no dedicated mismatch tags beyond normal category diagnostics

## Recommendation
- `prepare_reminder_creation_args` is reused in relevant reminder-creation contexts, but large nearby-registry cohort regressions outweigh gains.
- Canonical and final-task deltas are negative, with 5 exact-success regressions against 0 exact-success gains.
- This run does not meet frozen reuse keep criteria.

## Blockers
- Failing criterion: `non_positive_canonical_delta`
- Failing criterion: `gains_do_not_exceed_regressions`
- Failing criterion: `exact_successes_regressed`

## Recommendation for Next Phase
- Do not promote/expand active portfolio from this phase without a general routing or helper contract repair.
- Per Phase C prerequisites, do not start Phase C until Phase B is pass.

## Decision
suppress/retire candidate
