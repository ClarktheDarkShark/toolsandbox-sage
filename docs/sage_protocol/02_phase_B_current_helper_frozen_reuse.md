# Phase B: Current Helper Frozen Reuse

**Objective:** Validate that `prepare_reminder_creation_args` can be reused in frozen mode (generation OFF) without regressing canonical score or final-task success. Establish the reuse baseline.

**Entry condition:** Phase A report complete with status `READY_FOR_PHASE_B`.

**Exit condition:** Phase B report written; reuse comparison stored in artifacts; decision on reuse outcome (proceed to Phase C or refine before proceeding).

---

## B.1 Frozen Registry Preparation

Create a frozen registry containing only `prepare_reminder_creation_args`:

```bash
python scripts/create_registry_subset.py \
  --source artifacts/registry_manifest.json \
  --tools prepare_reminder_creation_args \
  --output outputs/phase_B_frozen_registry_<timestamp>.json
```

Verify the frozen registry:
```bash
python scripts/migrate_registry.py --check-only --registry outputs/phase_B_frozen_registry_<timestamp>.json
```

**Success criteria:**
- `prepare_reminder_creation_args` shows PASS
- No FAIL entries in frozen registry
- `held_out_check_count >= 1`, `negative_applicability_count >= 2`, `runtime_smoke_passed=true`

Copy frozen registry to artifacts:
```bash
cp outputs/phase_B_frozen_registry_<timestamp>.json artifacts/phase_B_frozen_registry.json
```

---

## B.2 Frozen Reuse Cohort (12–18 Tasks)

Run the same task order as Phase A baseline, but load the frozen registry (generation OFF):

```bash
make confirm100 \
  MODE=evolve \
  REGISTRY=artifacts/phase_B_frozen_registry.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=read_write
```

This ensures:
- Helper is available and routed when relevant
- Generation is disabled (no new tools)
- Task scenario order matches Phase A baseline
- Cache policy is symmetric between Phase A and Phase B

**Deliverable:** `outputs/phase_B_frozen_reuse_<timestamp>/`
- Run manifest (generation_mode=OFF, registry_path, scenario order identical to Phase A)
- Task transcripts
- Per-task route logs (which helpers were visible, called, filtered)
- Canonical scores
- Final-task success rates
- Dashboard URL

---

## B.3 Route-Mismatch Analysis

Compare Phase B routes against Phase A baseline:

```bash
python scripts/export_sage_metrics.py \
  --control_run artifacts/phase_A_baseline_control_<timestamp>/ \
  --sage_run outputs/phase_B_frozen_reuse_<timestamp>/ \
  --compare-routes
```

**Expected findings:**
- Tasks involving reminder creation: `prepare_reminder_creation_args` should be visible and called
- Tasks not involving reminders: helper should be filtered (not visible)
- No unintended route mismatches

**Failure case:** If helper is called when it shouldn't be (negative trigger match), or filtered when it should be visible (positive trigger miss), document and adjust trigger logic before proceeding.

---

## B.4 Canonical Score Comparison

Compare canonical scores:

```bash
python scripts/export_sage_metrics.py \
  --control_run artifacts/phase_A_baseline_control_<timestamp>/ \
  --sage_run outputs/phase_B_frozen_reuse_<timestamp>/ \
  --compare-scores
```

**Expected outcomes:**

| Scenario | Action |
|----------|--------|
| Phase B canonical >= Phase A canonical | Proceed to Phase C (no regression, possible improvement) |
| Phase B canonical == Phase A canonical (within 1%) | Proceed to Phase C (frozen reuse is neutral) |
| Phase B canonical < Phase A canonical | **STOP.** Route-mismatch or helper error. Diagnose and repair before Phase C. |

---

## B.5 Final-Task Success Comparison

Compare final-task success rates:

```bash
python scripts/export_sage_metrics.py \
  --control_run artifacts/phase_A_baseline_control_<timestamp>/ \
  --sage_run outputs/phase_B_frozen_reuse_<timestamp>/ \
  --compare-final-task-success
```

**Acceptance criteria:**
- Phase B final-task success >= Phase A (or neutral)
- No unexpected success flips (tasks that passed in Phase A but fail in Phase B without explicit helper intervention)

---

## B.6 Reuse Metrics Update

Update the active registry with reuse counts and success flips:

```bash
python -c "
from src.sage_ts.registry.registry_manager import update_reuse_counts
update_reuse_counts(
    registry_path='artifacts/registry_manifest.json',
    phase_B_run_id='outputs/phase_B_frozen_reuse_<timestamp>/',
)
"
```

Verify the frozen registry manifest is updated with reuse counts and success_flips metrics.

---

## B.7 Phase B Report

Write final report to `docs/sage_protocol/phase_B_completion_report.md`:

**Contents:**
- Frozen registry path and hash
- Phase B canonical score (vs Phase A baseline)
- Phase B final-task success rate (vs Phase A baseline)
- Route-mismatch summary (expected vs observed helper calls)
- Reuse count increment for `prepare_reminder_creation_args`
- Success flip count (if any)
- Blockers or deviations
- Recommendation for Phase C entry

**Format example:**
```markdown
# Phase B Completion Report

**Date:** 2026-05-02
**Status:** [READY_FOR_PHASE_C | BLOCKED]

## Frozen Reuse Results
- Frozen registry: artifacts/phase_B_frozen_registry.json
- Phase A baseline canonical: XX.X%
- Phase B frozen reuse canonical: YY.Y%
- Canonical difference: ±Z.Z%

## Final-Task Success
- Phase A baseline: XX.X%
- Phase B frozen reuse: YY.Y%

## Route Analysis
- Helper visible in N tasks (expected)
- Helper called in M tasks (expected)
- Route mismatches: [list or none]

## Reuse Metrics
- `prepare_reminder_creation_args` reuse_count: N
- Success flips: [list or none]

## Recommendation
[Proceed to Phase C / Refine routing / Repair helper]
```

---

## Phase B Completion Criteria

✓ Frozen registry created and validated
✓ Frozen reuse cohort run (generation OFF)
✓ Routes match expected triggers (no regressions)
✓ Canonical score not regressed
✓ Final-task success not regressed
✓ Reuse metrics updated
✓ Phase B report written

**Next:** Human review and approval → Phase C
