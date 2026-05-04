# Phase E: Pilot & Formal 100-Task Run

**Objective:** Conduct a pilot mini run (18 tasks) to verify pipeline stability, then execute formal 100-task canonical + final-task evaluation.

**Entry condition:** Phase D report complete with no blockers.

**Exit condition:** Phase E report written; 100-task run complete; baseline data for dissertation.

---

## E.1 Pilot Run (18 Tasks)

Run a 18-task pilot to verify:
- All helpers route correctly
- No crashes or import errors
- Dashboard generation works
- Scoring pipeline produces valid output

```bash
make confirm100 \
  MODE=evolve \
  REGISTRY=artifacts/registry_manifest.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=read_write \
  TASK_LIMIT=18
```

If pilot succeeds, proceed. If failures, stop and diagnose.

---

## E.2 Formal 100-Task Run (Control)

```bash
make confirm100 \
  MODE=control \
  REGISTRY=artifacts/empty_registry.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=write_only
```

Deliverable: `outputs/phase_E_control_100_<timestamp>/`
- 100-task canonical scores
- Per-task final-task success
- Dashboard at main endpoint

---

## E.3 Formal 100-Task Run (SAGE)

```bash
make confirm100 \
  MODE=evolve \
  REGISTRY=artifacts/registry_manifest.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=read_write
```

Deliverable: `outputs/phase_E_sage_100_<timestamp>/`
- 100-task canonical scores
- Per-task final-task success
- Helper routing logs
- Dashboard at main endpoint

---

## E.4 Comparative Analysis

```bash
python scripts/export_sage_metrics.py \
  --control_run outputs/phase_E_control_100_<timestamp>/ \
  --sage_run outputs/phase_E_sage_100_<timestamp>/ \
  --report outputs/phase_E_comparison_report.json
```

Report:
- Canonical score (control vs SAGE, delta, CI)
- Final-task success (control vs SAGE, delta, CI)
- Per-tool reuse counts
- Route-mismatch summary
- Confidence in conclusion

---

## E.5 Phase E Report

Write to `docs/sage_protocol/phase_E_completion_report.md`:

**Contents:**
- Pilot result (PASS/FAIL)
- Control 100-task canonical score
- SAGE 100-task canonical score
- Canonical score delta and confidence
- Final-task success comparison
- Helper routing summary
- Recommendation for Phase F (proceed with formal 250, or stop)

---

## Phase E Completion Criteria

✓ Pilot run successful
✓ Control 100-task run complete
✓ SAGE 100-task run complete
✓ Comparative analysis done
✓ Dashboard generated and accessible
✓ Phase E report written

**Next:** Human review and approval → Phase F
