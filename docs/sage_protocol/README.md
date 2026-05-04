# SAGE Protocol Documentation

This directory contains durable, phase-gated instructions for executing SAGE experiments. Each phase is self-contained, executable within a single coding-agent session or multiple focused sessions.

## Files

- `00_global_working_agreement.md` — Non-negotiable rules applying across all phases
- `01_phase_A_foundation_measurement_provenance.md` — Baseline measurement, canonical score, provenance setup
- `02_phase_B_current_helper_frozen_reuse.md` — Frozen reuse of `prepare_reminder_creation_args` with generation OFF
- `03_phase_C_next_tools_micro_loops.md` — Generate, validate, and accept 2–3 new tools via micro-loops
- `04_phase_D_portfolio_ablation.md` — Validate the 3–5 tool portfolio via matched control/SAGE pairs
- `05_phase_E_pilot_and_formal_100.md` — Pilot phase; then formal 100-task canonical + final-task runs
- `06_phase_F_formal_250_and_final_package.md` — Formal 250-task runs and packaging for dissertation
- `audit_alignment_report.md` — Initial audit of component readiness (phase-gated execution blocker)
- `grading_scoring_review_report.md` — Deep grading/scoring review; root-cause analysis and evaluation strategy for SAGE vs. baseline comparison (supersedes `grading_mismatch_audit_report.md`)
- `phase_B_calling_convention_fix_report.md` — Phase B v2 rerun after helper description fix; gate PASSED
- `grading_mismatch_audit_report.md` — First-pass grading audit (SUPERSEDED by `grading_scoring_review_report.md`)

## Phase-Gated Execution

Each phase:
1. Has explicit entry conditions (prior phase complete, report written)
2. Produces a report at the end
3. Requires explicit human approval before moving to the next phase
4. Does not proceed to the next phase without that approval

This prevents context drift, scope creep, and accidental skipping of validation steps.
