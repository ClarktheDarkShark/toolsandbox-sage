# V2 Cohort Quality Gate Report

## Objective
Make cohort quality mechanical so future 20/60/100/250 runs cannot silently pass with near-duplicate easy-task dominance.

## Files Changed
- `src/sage_ts/evaluation/task_strata.py`
- `scripts/run_sage_protocol.py`
- `tests/unit/test_task_strata.py`

## What Changed
- Added mechanical quality gate fields to `cohort_policy_report`:
  - `should_block_quality`
  - `quality_gate_status`
  - `quality_gate_failures`
  - `max_allowed_family_share`
  - `largest_family_variant_count`
  - `max_allowed_family_variants`
  - `no_current_helper_fit_share`
  - `largest_helper_lane_share`
- Added runner blocking for low-quality cohorts unless `--allow-low-quality-cohort` is explicitly passed.
- Runner now records quality gate status/failures in run events and protocol manifests.

## Enforced Thresholds
- For `20-29` scenario runs: at least `5` base families, max family share `25%`, max variants per base family `2`.
- For `30-59` scenario runs: at least `6` base families, max family share `20%`, max variants per base family `4`.
- For `60+` scenario runs: at least `8` base families, max family share `20%`, max variants per base family `8`.
- For `20+` scenario registry-backed runs: no-current-helper-fit coverage must be at least `20%`.
- For `20+` scenario runs: one known helper lane may not cover more than `60%` of the sample.

## Existing Manifest Check
- The previous formal 250 preflight would now fail quality with `near_duplicate_family_variants_above_limit`.
- Example: largest base family variant count was `12`, new max for `250` is `8`.
- This directly addresses the observed issue that easy reminder variants can dominate while looking superficially diverse.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- Result: `61 passed`.

## Registry Check
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_balanced_final/registry_manifest.json`
- Result: `2 active entries PASS`, `0 FAIL`.

## Answers
- Can a run mostly composed of minor variants pass unnoticed? No, for 20+ runs it now fails quality unless explicitly overridden for diagnostics.
- What thresholds are enforced or flagged? See enforced thresholds above.
- Which existing manifests would pass/warn/fail? The formal 250 would now fail for near-duplicate variants; smaller diagnostics remain allowed when below broad-run thresholds.
- Are 20, 60, 100, and 250 manifests covered? Yes. Thresholds explicitly cover `20+`, `30+`, and `60+`, including 100/250.

## Decision Label
cohort gate ready
