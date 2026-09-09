# SAGE Global Working Agreement

These rules apply throughout all phases and all coding-agent sessions.

## 1. Architectural Separation

- **SAGE** is the autonomous self-evolving ToolSandbox agent (tool generation + validation + registry + reuse pipeline).
- **Codex / Claude Code** are implementation assistants that help build SAGE and run phases.
- **Never** attribute coding-agent work directly to SAGE unless it came from the SAGE generation pipeline with full provenance (birth scenario, validation run, registry entry ID).

## 2. Phase-Gated Execution

- **One phase at a time.** Do not skip phases or proceed without explicit phase completion and human approval.
- **Report after each phase.** Write the required report file to `docs/sage_protocol/` before claiming phase completion.
- **No silent context drift.** If circumstances change, flag the change and ask before continuing.

## 3. Registry and Helper Management

- **Active registry must be claim-safe:** every PASS entry must have `held_out_check_count >= 1`, `negative_applicability_count >= 1`, and `runtime_smoke_passed=true` (unless frozen-reuse mode explicitly exempts a helper).
- **Frozen reuse requires generation OFF:** no new helpers are generated during frozen reuse runs; only existing registry entries are loaded and routed.
- **Every retained helper needs full provenance:** birth_scenario, acceptance timestamp, validation run ID, code hash, reuse counts, and any repair/legacy metadata.
- **Side-effect tools are sacred:** helpers must preserve the side-effect tools they claim (e.g., `prepare_reminder_creation_args` preserves `add_reminder`). No hidden-answer checkers.

## 4. Validation and Scoring

- **Canonical score** is the ToolSandbox milestone score (baseline requirement).
- **Final-task success score** is whether the agent completed the user's goal (additional evidence).
- **Matched comparison:** control and SAGE cohorts use the same scenario order, model, base tools, and cache policy.
- **Route-mismatch reporting:** log when a helper is routed (visible, called, filtered) and compare against expectations.
- **Route-mismatch = regression risk:** if reuse pattern diverges from design, flag and investigate before proceeding.

## 5. Code Integrity

- **No scenario-name overfitting:** helpers are generated for reusable inadequacy patterns, not one-off scenario patches.
- **No hidden edits during benchmark runs:** if a code change is needed, stop the run, fix it, then restart with generation or reuse settings as appropriate.
- **Test before claim:** every code change must pass lightweight type/lint checks and focused unit tests. Broad test suite is not required in every phase, but critical-path tests (registry proofing, generated tool injection, side-effect preservation) must pass.

## 6. Live Verification

- **Verify after every material change.** Do not assume a refactor, config change, or code fix works — run focused tests for the changed path (use `make test-core` for the publication-critical surface).
- **Report blockers transparently.** If a test fails, a dependency is missing, or a prerequisite is unmet, stop and report exactly what blocks progress (file path, line number, error message).

## 7. Codebase Coherence

- **Provenance consistency:** if a tool is retired, flagged legacy, or moved to a failed cohort, it must be explicitly excluded from future active registries.
- **Artifact paths:** registry manifests, run logs, dashboards, and evaluation artifacts must all point to the same version of the active registry.
- **Dashboard continuity:** every live run must generate a dashboard with the exact registry path, generation mode, and run ID so results are auditable.

## 8. Contradiction Resolution

If a rule in this agreement contradicts guidance in a phase file, **stop and flag it.** The global agreement takes precedence over phase guidance unless the phase file explicitly overrides it with a clear rationale.

---

**Last updated:** 2026-05-02
**Phase-gated enforcement:** All phases must acknowledge and respect this agreement.
