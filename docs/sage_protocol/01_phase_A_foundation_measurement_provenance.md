# Phase A: Foundation Measurement & Provenance

**Objective:** Establish baseline canonical scores, validate the scoring spine (canonical + final-task), and set up durable provenance infrastructure for all future runs.

**Entry condition:** Audit report complete (`audit_alignment_report.md`) with decision `ready for Phase A`.

**Exit condition:** Phase A report written; all phase A artifacts stored in `outputs/phase_A_<date>/`; human approval to proceed to Phase B.

---

## A.1 Baseline Measurement (Control Cohort)

Run 12–18 baseline control tasks (generation OFF, no helpers loaded):

```bash
make confirm100 MODE=control REGISTRY=artifacts/empty_registry.json CACHE_MODE=write_only
```

This establishes:
- Canonical milestone score on base tools only
- Per-task success/failure patterns
- Task trajectories for route-matching

**Deliverable:** `outputs/phase_A_baseline_control_<timestamp>/`
- Run manifest (scenario order, model, base tools, cache status)
- Task transcripts
- Canonical scores (per-task and aggregate)
- Final-task success rates
- Dashboard URL

Store run output in artifacts:
```bash
cp -r outputs/phase_A_baseline_control_<timestamp>/ artifacts/phase_A_baseline_control_<timestamp>/
```

---

## A.2 Validate Scoring Spine

Check that canonical score and final-task success are:
1. Independently computed (no accidental coupling)
2. Reported separately in dashboard and run manifest
3. Reproducible (identical scenario order, same model, same base tools)

**Command:**
```bash
python scripts/export_sage_metrics.py --run artifacts/phase_A_baseline_control_<timestamp>/ --check-scores
```

**Success criteria:**
- Canonical score != 0 (baseline is measurable)
- Final-task success score independently reported
- Per-task route logs present (for later route-mismatch analysis)

---

## A.3 Provenance Infrastructure

Set up provenance tracking for all retained helpers:

1. **Registry entry template:** Every PASS helper in the active registry must include:
   - `tool_name` and `schema_version`
   - `birth_scenario` (the task where inadequacy was first observed)
   - `accepted_at` (ISO timestamp)
   - `version` (incremented on repair)
   - `code_hash` (SHA-256 of code as accepted)
   - `validation.held_out_check_count`, `negative_applicability_count`, `runtime_smoke_passed`
   - `preserves_side_effect_tools` list
   - `required_original_tool_calls` list
   - `reuse_count` (incremented on each successful reuse)
   - `success_flips` (track behavior changes)
   - `legacy_diagnostic` flag (if manual repair applied)

2. **Validate active registry:**
```bash
python scripts/migrate_registry.py --check-only
```

Should show all PASS entries with full metadata. Report any FAIL entries and reason.

3. **Create a provenance manifest** at `artifacts/provenance_manifest.json`:
```json
{
  "phase": "A",
  "timestamp": "ISO_TIMESTAMP",
  "baseline_control_run_id": "...",
  "active_registry_path": "artifacts/registry_manifest.json",
  "active_registry_hash": "SHA-256_of_manifest",
  "helpers": {
    "prepare_reminder_creation_args": {
      "status": "PASS",
      "birth_scenario": "...",
      "validation_run_id": "...",
      "code_hash": "...",
      "preserves": ["add_reminder"],
      "reuse_ready": true
    }
  }
}
```

---

## A.4 Candidate Gate Review

Inspect the candidate gate definitions in `src/sage_ts/validation/candidate_gate.py`:

**Requirements:**
- All PASS helpers must meet candidate gate thresholds (no missing output schema, positive triggers, negative triggers, etc.).
- All FAIL helpers must have documented reasons (held_out_check_count, runtime_smoke_passed, output schema, etc.).

**Command:**
```bash
python -c "from src.sage_ts.validation import candidate_gate; print(candidate_gate.__doc__)"
```

Report any misconfigured thresholds.

---

## A.5 Dashboard and Live Run Setup

1. **Generate baseline dashboard:**
```bash
make dashboard RUN=artifacts/phase_A_baseline_control_<timestamp>/
```

2. **Verify dashboard includes:**
   - Canonical scores (per-task and aggregate)
   - Final-task success rates
   - Per-task route logs (which base tools were called)
   - Baseline task trajectories
   - No helpers loaded (verify "visible tools" includes only base tools)

3. **Store dashboard URL** in `artifacts/phase_A_dashboard_url.txt`

---

## A.6 Documentation

Document Phase A findings:
- Baseline canonical score
- Baseline final-task success rate
- Scoring spine validation result (PASS/FAIL)
- Provenance infrastructure completeness
- Active registry status summary
- `prepare_reminder_creation_args` status from active registry

No separate artifact file is required for this step; include these findings in the Phase A report.

---

## A.7 Phase A Report

Write the Phase A report to `docs/sage_protocol/phase_A_foundation_measurement_report.md`:

**Contents:**
- Baseline canonical score and final-task success rate
- Dashboard URL
- Provenance manifest path
- Active registry check result (PASS/FAIL)
- Candidate gate review result
- Blockers or deviations from protocol
- Recommendation for Phase B entry

**Format example:**
```markdown
# Phase A Completion Report

**Date:** 2026-05-02
**Decision label:** [pass | needs one general repair | blocked by evaluation or claim-safety issue]

## Baseline Scores
- Canonical score: XX.X%
- Final-task success: YY.Y%

## Provenance Setup
- Active registry: artifacts/registry_manifest.json
- Provenance manifest: artifacts/provenance_manifest.json
- Dashboard: [URL]

## Blockers (if any)
- [List any issues that prevent Phase B entry]

## Recommendation
[Proceed to Phase B / Stop and fix X / Review Y]
```

---

## Phase A Completion Criteria

✓ Baseline canonical score established
✓ Baseline final-task success rate established
✓ Scoring spine validated (independent reporting)
✓ Provenance infrastructure in place
✓ Active registry checked and claim-safe
✓ Dashboard generated and accessible
✓ Phase A report written

**Next:** Human review and approval → Phase B
