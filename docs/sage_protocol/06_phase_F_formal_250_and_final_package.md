# Phase F: Formal 250-Task Run & Final Package

**Objective:** Execute formal 250-task canonical + final-task evaluation (the main claim). Package all artifacts for dissertation submission.

**Entry condition:** Phase E report complete with recommendation to proceed.

**Exit condition:** Phase F report written; 250-task runs complete; final package assembled and archived.

---

## F.1 Formal 250-Task Run (Control)

```bash
make confirm100 \
  MODE=control \
  REGISTRY=artifacts/empty_registry.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=write_only \
  TASK_LIMIT=250
```

Deliverable: `outputs/phase_F_control_250_<timestamp>/`

---

## F.2 Formal 250-Task Run (SAGE with 3–5 Tool Portfolio)

```bash
make confirm100 \
  MODE=evolve \
  REGISTRY=artifacts/registry_manifest.json \
  GENERATION_MODE=OFF \
  CACHE_MODE=read_write \
  TASK_LIMIT=250
```

Deliverable: `outputs/phase_F_sage_250_<timestamp>/`

---

## F.3 Comparative Analysis (Final Claim)

```bash
python scripts/export_sage_metrics.py \
  --control_run outputs/phase_F_control_250_<timestamp>/ \
  --sage_run outputs/phase_F_sage_250_<timestamp>/ \
  --report outputs/phase_F_final_comparison.json
```

Report:
- Canonical score delta (with 95% CI)
- Final-task success delta
- Effect size (Cohen's d or similar)
- Per-tool reuse and success flip metrics
- Ablation by tool (single-tool vs full portfolio)
- Route-mismatch analysis and reconciliation

---

## F.4 Final Package Assembly

Create dissertation submission artifact:

```bash
mkdir -p artifacts/phase_F_final_package_<date>
cp outputs/phase_F_control_250_<timestamp>/ artifacts/phase_F_final_package_<date>/
cp outputs/phase_F_sage_250_<timestamp>/ artifacts/phase_F_final_package_<date>/
cp outputs/phase_F_final_comparison.json artifacts/phase_F_final_package_<date>/
cp artifacts/registry_manifest.json artifacts/phase_F_final_package_<date>/final_active_registry.json
cp docs/sage_protocol/*.md artifacts/phase_F_final_package_<date>/protocol_docs/
```

Contents:
- Control and SAGE run outputs
- Comparative analysis report
- Final active registry (3–5 tools)
- All protocol documentation
- README for reproducibility

---

## F.5 Reproducibility Verification

Verify that all artifacts are sufficient to reproduce the claim:

```bash
cd artifacts/phase_F_final_package_<date>/
# Check that registry, dashboards, transcripts, and scores are present
find . -type f -name "*.json" | wc -l
```

Document:
- Exact scenario order (deterministic)
- Model and temperature (in run manifests)
- Cache policy (symmetric, reported)
- Seed / randomness (if applicable)
- External API versions (RapidAPI, OpenAI, etc.)

---

## F.6 Phase F Report

Write to `docs/sage_protocol/phase_F_completion_report.md`:

**Contents:**
- Control 250-task canonical score
- SAGE 250-task canonical score
- Canonical score delta and 95% CI
- Effect size (Cohen's d, etc.)
- Final-task success comparison
- Per-tool reuse and success-flip metrics
- Ablation results (if run)
- Route-mismatch reconciliation
- Reproducibility checklist (all required artifacts present)
- Dissertation readiness assessment
- Any blockers or caveats

**Format example:**
```markdown
# Phase F Completion Report

**Date:** 2026-05-XX
**Status:** DISSERTATION_READY

## Final Canonical Score Results
- Control (250 tasks): XX.X%
- SAGE (250 tasks): YY.Y%
- Delta: +Z.Z% (95% CI: ±W.W%)
- Effect size (Cohen's d): M

## Final-Task Success Results
- Control: XX.X%
- SAGE: YY.Y%

## Tool Portfolio (3–5 Tools)
1. prepare_reminder_creation_args: reuse_count=N, success_flips=0
2. [tool_2]: reuse_count=M, success_flips=0
3. [tool_3]: reuse_count=K, success_flips=0

## Reproducibility Checklist
- ✓ Scenario order deterministic
- ✓ Model/temperature in manifests
- ✓ Cache policy symmetric and reported
- ✓ Registry final_active_registry.json present
- ✓ All dashboards and transcripts archived
- ✓ Protocol documentation complete

## Dissertation Readiness
[Ready for submission / Requires X revision]

## Package Location
artifacts/phase_F_final_package_<date>/
```

---

## Phase F Completion Criteria

✓ Control 250-task run complete
✓ SAGE 250-task run complete
✓ Comparative analysis (canonical + final-task)
✓ Effect size calculated
✓ Final package assembled
✓ Reproducibility verified
✓ Phase F report written

**Final Decision:** Dissertation submission ready or requires revision.
