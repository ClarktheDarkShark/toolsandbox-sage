# Phase D: Portfolio Ablation (3–5 Tool Validation)

**Objective:** Validate the 3–5 tool portfolio via matched control/SAGE pairs. Ensure each tool contributes positively (or is neutral) without causing regressions or triggering unexpected side effects.

**Entry condition:** Phase C report complete with 3–5 tools accepted.

**Exit condition:** Phase D report written; ablation study complete; decision on portfolio stability.

---

## D.1 Matched Control and SAGE Cohorts (30–36 Tasks)

Run paired 30–36 task cohorts with identical scenario order:

```bash
# Control (no helpers)
make transfer60 \
  CATEGORY=<primary_category> \
  REGISTRY=artifacts/empty_registry.json \
  MODE=control \
  CACHE_MODE=write_only

# SAGE (with 3–5 helpers)
make transfer60 \
  CATEGORY=<primary_category> \
  REGISTRY=artifacts/registry_manifest.json \
  MODE=evolve \
  GENERATION_MODE=OFF \
  CACHE_MODE=read_write
```

---

## D.2 Per-Tool Contribution Analysis

For each tool in the portfolio:

1. Create a registry variant with only that tool
2. Run a 6-task validation cohort
3. Measure canonical score vs control
4. Log which tasks benefited, which were unaffected

```bash
for tool in <tool_1> <tool_2> <tool_3>; do
  python scripts/create_registry_subset.py \
    --source artifacts/registry_manifest.json \
    --tools $tool \
    --output outputs/phase_D_single_tool_${tool}_registry.json

  make smoke4 \
    CATEGORY=<category> \
    REGISTRY=outputs/phase_D_single_tool_${tool}_registry.json
done
```

Report: per-tool contribution to canonical score.

---

## D.3 Regression Check (Route-Mismatch Analysis)

Compare control vs SAGE route logs:

```bash
python scripts/export_sage_metrics.py \
  --control_run <phase_D_control_run> \
  --sage_run <phase_D_sage_run> \
  --compare-routes
```

Flag any task where:
- Helper triggered unexpectedly (false positive)
- Helper filtered unexpectedly (false negative)
- Route logic diverged from design

---

## D.4 Canonical Score Comparison

Report canonical score delta:
- Phase D SAGE vs Phase D control
- Confidence intervals if available
- Per-task score breakdown

**Success criteria:**
- SAGE canonical >= control canonical (or ≥99% of control, within margin of error)
- No unexplained score degradation
- Score gains concentrated in tasks where helpers were designed to help

---

## D.5 Stability Report

Document portfolio stability:
- All 3–5 tools routed correctly
- No mutual interference (tool A doesn't break tool B)
- No regressions on non-target tasks
- Final-task success unchanged or improved

---

## D.6 Phase D Report

Write to `docs/sage_protocol/phase_D_completion_report.md`:

**Contents:**
- Portfolio size: N tools
- Control vs SAGE canonical scores
- Per-tool contribution table
- Route-mismatch summary (none expected; flag if found)
- Regression analysis result
- Recommendation for Phase E (proceed, refine, or stop)

---

## Phase D Completion Criteria

✓ Control and SAGE cohorts run (30–36 tasks each)
✓ Per-tool contribution measured
✓ No regressions (SAGE >= control)
✓ Route-mismatch analysis complete
✓ Phase D report written

**Next:** Human review and approval → Phase E
