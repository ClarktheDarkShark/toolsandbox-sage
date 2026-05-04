# CLAUDE.md: Coding-Agent Collaboration Guide for SAGE

This file contains durable collaboration rules for coding-agent sessions working on SAGE.

## 1. SAGE Is Not Coding-Agent Work

- **SAGE** = the autonomous self-evolving ToolSandbox agent (tool generation + validation + registry + reuse pipeline running in `make` commands)
- **Coding-agent work** = building, testing, fixing, and documenting SAGE (using Codex/Claude to help)
- **Never claim the coding-agent did SAGE's work.** Example: "Generated a new helper tool" is only true if it came from the SAGE pipeline (generation phase), passed validation, and was accepted into the registry. Building the pipeline is not SAGE generating tools.

## 2. Work Within Phase Protocols

- Phase instructions live in `docs/sage_protocol/<phase_number>_*.md`
- Each phase file is self-contained and runnable in a single or few sessions
- **Do not skip phases.** Each phase produces a report that gates the next phase.
- **Do not edit code during a benchmark run** (e.g., no mid-run hotfixes). Stop, fix, verify with lightweight tests, then restart.
- Read the relevant phase file at the start of each session to understand what work is in scope.

## 3. Lightweight Verification After Code Changes

- After editing any core module (generation, validation, registry, runtime, evaluation), run:
  ```bash
  python scripts/migrate_registry.py --check-only
  ```
  This verifies the active registry is claim-safe (no broken manifests, all PASS entries have validation proof).

- Do not assume a refactor works. Run the command; if it fails, fix it and re-run.
- Type checking (`mypy src/sage_ts/`) is optional per-session but must pass before submission.

## 4. Registry Integrity

- The active registry at `artifacts/registry_manifest.json` is the source of truth for retained helpers.
- Every PASS entry must have:
  - `held_out_check_count >= 1` and `negative_applicability_count >= 2` (validation proof)
  - `runtime_smoke_passed=true` (runtime verification)
  - `preserves_side_effect_tools` list (if applicable)
  - `code_hash` (immutable reference)
  - `accepted_at` timestamp and `birth_scenario`
- Any edit to the registry must be via `python scripts/migrate_registry.py`, not direct JSON edits.

## 5. Frozen Reuse Baseline

- `prepare_reminder_creation_args` is currently the single frozen-reuse baseline helper.
- It preserves `add_reminder` (side-effect tool).
- In frozen-reuse runs, generation is OFF; only this helper is loaded and routed.
- Do not add new helpers to frozen-reuse mode without Phase C completion.

## 6. Dashboard and Live Run Artifacts

- Every run (control, evolve, smoke, etc.) generates a dashboard at `outputs/<run_id>/dashboard.html`
- Dashboard URL is written to `outputs/<run_id>/manifest.json` under `dashboard_url`
- Before claiming a run is complete, open the dashboard and verify:
  - Canonical scores present
  - Final-task success rates present
  - Route logs showing which tools were visible/called
  - No obvious errors in transcripts

## 7. Commit and Documentation

- Commit code changes with clear messages:
  ```
  fix(generation): remove debug print from tool_generator

  Prevents noise in validation logs without affecting logic.
  ```
- Do not commit phase reports directly into the repo (`docs/sage_protocol/*_report.md` are for human review, not version control).
- Only commit phase instruction files, code changes, and metadata (registry, manifests).

## 8. Blockers and Escalation

- If a test fails, a dependency is missing, or a protocol rule is violated, **stop and report**:
  - Exact error message or assertion failure
  - File path and line number (if applicable)
  - What was expected vs. what happened
  - Recommended next step (fix, skip, or escalate)
- Do not work around a blocker with a temporary hack (e.g., `--no-verify` on git, manual JSON edits to registry).

---

**Last updated:** 2026-05-02
**Scope:** All phases, all sessions
