# Phase C: Next Tools Micro-Loops

> **SUPERSEDED — ARCHIVAL ONLY.** This phase protocol predates the current
> outcome-only, concurrent fresh-control publication design. Do not use its
> commands, metric gates, or decisions. See [current_state.md](current_state.md).

**Objective:** Generate, validate, and accept 2–3 new deterministic helpers via micro-loops. Each micro-loop is self-contained: run a small cohort, observe inadequacy, generate a candidate, validate it, and either accept or reject before moving to the next helper.

**Entry condition:** Phase B report complete with status `READY_FOR_PHASE_C`.

**Exit condition:** Phase C report written; 2–3 new helpers accepted and added to active registry; all micro-loop artifacts stored.

---

## C.1 Identification Loop

Run a small generation-enabled cohort (6–12 tasks) to identify next inadequacy patterns:

```bash
make viability12 \
  CATEGORY=<reminder|contact|message|setting> \
  REGISTRY=artifacts/phase_B_frozen_registry.json \
  GENERATION_MODE=ON \
  CACHE_MODE=write_only
```

**Deliverable:** `outputs/phase_C_identification_<category>_<timestamp>/`
- Task transcripts
- Inadequacy gates triggered (if any)
- Candidate tools generated (if any)
- Tool validation reports (passed/failed)

**Review findings:**
- How many tasks triggered adequacy gates?
- How many candidate tools were generated?
- How many passed schema + AST + semantic checks?

If no candidates passed validation, choose a different category and retry.

---

## C.2 Micro-Loop Template (Repeat 2–3 times)

For each accepted helper candidate, follow this template:

### C.2a Candidate Review

Inspect the generated candidate from the identification run:

```bash
python -c "
import json
manifest = json.load(open('outputs/phase_C_identification_<category>_<timestamp>/generation_manifest.json'))
for tool in manifest['generated_tools']:
    if tool['validation']['accepted']:
        print(f\"Tool: {tool['name']}\")
        print(f\"  Code:\n{tool['code']}\")
        print(f\"  Validation: {tool['validation']}\")
"
```

**Evaluate:**
1. Does the tool solve a genuine deterministic transform (not scenario-specific)?
2. Does it have clear positive triggers (when to call it) and negative triggers (when not to)?
3. Does it preserve side-effect tools (if relevant)?
4. Is the code simple, readable, and safe (no imports, no side effects)?

**Decision:**
- **Accept:** candidate is reusable, add to registry
- **Reject:** candidate is too scenario-specific or flawed; try next category

### C.2b Acceptance

If accepted, add the tool to the active registry:

```bash
python scripts/migrate_registry.py \
  --accept-candidate outputs/phase_C_identification_<category>_<timestamp>/generation_manifest.json \
  --tool <tool_name> \
  --target artifacts/registry_manifest.json
```

Verify the tool is now in the active registry:

```bash
python scripts/migrate_registry.py --check-only
```

Should show the new tool with PASS status.

### C.2c Validation Smoke Test

Run a small smoke test cohort (3–6 tasks) with the new helper loaded:

```bash
make smoke4 \
  CATEGORY=<category> \
  REGISTRY=artifacts/registry_manifest.json \
  CACHE_MODE=write_only
```

**Verify:**
- Helper is routed correctly (visible when needed, filtered otherwise)
- No unintended side effects
- No crashes or import errors
- Canonical score does not regress vs Phase B

If regression detected, revert acceptance and investigate:
```bash
python scripts/migrate_registry.py --reject <tool_name> --target artifacts/registry_manifest.json
```

Then flag for later repair (Phase D or beyond).

### C.2d Documentation

Update provenance:
```bash
python -c "
from src.sage_ts.registry.registry_manager import update_helper_metadata
update_helper_metadata(
    registry_path='artifacts/registry_manifest.json',
    tool_name='<tool_name>',
    metadata={
        'smoke_tested': True,
        'smoke_test_run_id': 'outputs/phase_C_smoke_<category>_<timestamp>/',
    }
)
"
```

---

## C.3 Active Registry Consolidation

After all 2–3 micro-loops complete, verify the active registry:

```bash
python scripts/migrate_registry.py --check-only
```

**Expected state:**
- `prepare_reminder_creation_args` (from Phase B)
- 2–3 new tools (from Phase C micro-loops)
- All PASS status
- Full validation proofs for all

Copy updated registry to artifacts:
```bash
cp artifacts/registry_manifest.json artifacts/phase_C_registry_with_3_tools.json
```

---

## C.4 Portfolio-Level Coherence Check

Ensure the 3–5 tool portfolio is coherent:

1. **No trigger collisions:** No two tools should have overlapping positive triggers unless designed to cooperate.
2. **No redundancy:** No two tools should solve the same problem differently.
3. **Family diversity:** Tools should span 2–3 families (e.g., canonicalizer, record-selector, state-precondition).

Report any issues; if critical, adjust routing or reject a tool.

---

## C.5 Phase C Report

Write final report to `docs/sage_protocol/phase_C_completion_report.md`:

**Contents:**
- Identification cohorts run (categories, task counts)
- Candidates generated and validation results
- 2–3 helpers accepted (names, birth scenarios, triggers)
- Smoke test results per helper
- Consolidated active registry (path, tool count, PASS count)
- Portfolio coherence assessment
- Blockers or deviations
- Recommendation for Phase D entry

**Format example:**
```markdown
# Phase C Completion Report

**Date:** 2026-05-02
**Status:** [READY_FOR_PHASE_D | NEEDS_RETRY]

## Tools Accepted
1. helper_name_1 (birth: scenario_X)
2. helper_name_2 (birth: scenario_Y)
3. helper_name_3 (birth: scenario_Z)

## Active Registry
- Path: artifacts/registry_manifest.json
- Total tools: 4 (1 from Phase B + 3 from Phase C)
- All PASS: Yes

## Smoke Test Results
- helper_1: canonical ±0%, routes OK
- helper_2: canonical ±0%, routes OK
- helper_3: canonical ±1%, routes OK

## Portfolio Coherence
- No trigger collisions
- Family diversity: [list]
- Recommendation: [Proceed to Phase D]
```

---

## Phase C Completion Criteria

✓ 2–3 new candidates identified
✓ All candidates passed validation
✓ All candidates accepted into active registry
✓ Smoke tests passed (no regressions)
✓ Portfolio coherence verified
✓ Phase C report written

**Next:** Human review and approval → Phase D
