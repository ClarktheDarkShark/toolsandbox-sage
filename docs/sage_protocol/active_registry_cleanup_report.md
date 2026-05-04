# Active Registry Cleanup Report

**Date:** 2026-05-02
**Objective:** Clean the active registry by removing 4 FAIL legacy entries, leaving only `prepare_reminder_creation_args` in a claim-safe state.
**Status:** ✓ SUCCESS

---

## Commands Run

1. **Backup original registry:**
   ```bash
   cp artifacts/registry_manifest.json artifacts/registry_manifest_pre_cleanup.json
   ```

2. **Create clean registry (Python script):**
   ```python
   import json
   with open('artifacts/registry_manifest.json', 'r') as f:
       data = json.load(f)
   clean_data = {
       "tools": {
           "prepare_reminder_creation_args": data["tools"]["prepare_reminder_creation_args"]
       }
   }
   with open('artifacts/active_registry_phase_ready.json', 'w') as f:
       json.dump(clean_data, f, indent=2)
   ```

3. **Verify clean registry:**
   ```bash
   python scripts/migrate_registry.py --check-only artifacts/active_registry_phase_ready.json
   ```
   Result: ✓ 1 PASS entry, 0 FAIL entries

4. **Swap into active use:**
   ```bash
   cp artifacts/registry_manifest.json artifacts/registry_manifest_pre_cleanup.json
   cp artifacts/active_registry_phase_ready.json artifacts/registry_manifest.json
   python scripts/migrate_registry.py --check-only artifacts/registry_manifest.json
   ```

5. **Run lightweight verification tests:**
   - 6 focused tests on registry integrity, validation proof, and backup

---

## Files Changed / Created

| File | Action | Status |
|------|--------|--------|
| `artifacts/registry_manifest_pre_cleanup.json` | Created (backup) | ✓ exists |
| `artifacts/active_registry_phase_ready.json` | Created (intermediate) | ✓ exists |
| `artifacts/registry_manifest.json` | Replaced | ✓ clean (1 PASS, 0 FAIL) |

---

## Registry Backup Path

```
artifacts/registry_manifest_pre_cleanup.json
```

Contains the original 5-entry registry (1 PASS + 4 FAIL).

---

## Clean Registry Path

```
artifacts/registry_manifest.json
```

Now contains only `prepare_reminder_creation_args` (PASS).

---

## Active Registry Entries After Cleanup

**File:** `artifacts/registry_manifest.json`
**Total entries:** 1
**PASS:** 1
**FAIL:** 0

```
Registry: artifacts/registry_manifest.json  (1 entries)
  PASS     prepare_reminder_creation_args  schema_version=2
```

---

## Proof Status for `prepare_reminder_creation_args`

| Attribute | Value | Status |
|-----------|-------|--------|
| Schema version | 2 | ✓ valid |
| Validation accepted | True | ✓ yes |
| Held-out check count | 1 | ✓ ≥1 |
| Negative applicability count | 2 | ✓ ≥1 |
| Runtime smoke passed | True | ✓ yes |
| Preserves side-effect tools | ["add_reminder"] | ✓ yes |
| Required original tool calls | ["add_reminder"] | ✓ yes |
| Version | 3 | ✓ valid (repaired version) |
| Code hash | 8a1b654030f26487... | ✓ present |
| Birth scenario | add_reminder_content_and_time_location | ✓ logged |
| Accepted at | 2026-05-02T01:36:19.597947+00:00 | ✓ timestamp |
| Reuse count | 0 | ✓ ready for Phase B |

**Overall:** ✓ CLAIM-SAFE. Ready for frozen reuse.

---

## Confirmation: FAIL Entries No Longer Active

**Removed entries:**
1. ✓ `recency_to_timestamp_bounds` (runtime_smoke_passed=false, held_out_check_count=0)
2. ✓ `relative_day_time_to_timestamp` (runtime_smoke_passed=false, held_out_check_count=0)
3. ✓ `select_latest_record_by_timestamp` (runtime_smoke_passed=false, held_out_check_count=0, missing_output_schema)
4. ✓ `next_service_enablement_action` (runtime_smoke_passed=false, held_out_check_count=0, missing_output_schema)

**Verification:** All 4 entries are absent from the active registry at `artifacts/registry_manifest.json`.

---

## Mechanism: Failed Entries Cannot Be Injected

The runtime loading mechanism uses `RegistryStore.load_entries()` which reads the manifest file and returns only entries present in the JSON:

```python
def load_entries(self) -> dict[str, RegistryEntry]:
    if not self.manifest_path.exists():
        return {}
    payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
    return {
        name: RegistryEntry.from_json(entry)
        for name, entry in payload.get("tools", {}).items()
    }
```

**Result:** Since the 4 FAIL entries are no longer in `artifacts/registry_manifest.json`, they cannot be loaded or injected into any run. They are completely excluded from frozen-reuse, transfer, Phase A baseline, and all subsequent phase runs.

---

## Protocol Consistency Check

✓ All 9 protocol files exist:
- `docs/sage_protocol/00_global_working_agreement.md`
- `docs/sage_protocol/01_phase_A_foundation_measurement_provenance.md`
- `docs/sage_protocol/02_phase_B_current_helper_frozen_reuse.md`
- `docs/sage_protocol/03_phase_C_next_tools_micro_loops.md`
- `docs/sage_protocol/04_phase_D_portfolio_ablation.md`
- `docs/sage_protocol/05_phase_E_pilot_and_formal_100.md`
- `docs/sage_protocol/06_phase_F_formal_250_and_final_package.md`
- `CLAUDE.md`
- `AGENTS.md`

✓ **Phase-gating language confirmed:** All files consistently enforce:
- One phase/micro-step at a time
- Report required after each phase
- Human review required before proceeding
- No automatic continuation between phases

✓ **No protocol violations found:** No file instructs to "automatically proceed," "do not stop," or "continue without human review."

---

## Tests Run and Results

| Test | Scope | Result |
|------|-------|--------|
| Active registry count | Registry has 1 entry | ✓ PASS |
| prepare_reminder_creation_args present | Tool is in registry and accepted | ✓ PASS |
| Validation proof (3 checks) | held_out≥1, negative≥1, runtime_smoke=true | ✓ PASS (all 3) |
| Side-effect preservation | add_reminder in preserves and requires lists | ✓ PASS |
| FAIL entries excluded | All 4 FAIL entries absent from active registry | ✓ PASS |
| Backup exists | artifacts/registry_manifest_pre_cleanup.json present | ✓ PASS |
| **Total** | 6 focused tests | **6/6 PASS** |

---

## Blockers: None

All steps completed successfully. No issues encountered. Registry is claim-safe and ready for Phase A.

---

## Recommendation for Next Step

**Next:** Phase A (Foundation Measurement & Provenance)

**Entry conditions verified:**
- ✓ Active registry is claim-safe (1 PASS, 0 FAIL)
- ✓ `prepare_reminder_creation_args` is ready for frozen reuse
- ✓ Phase A protocol file exists (`docs/sage_protocol/01_phase_A_foundation_measurement_provenance.md`)
- ✓ Resident guidance files exist (`CLAUDE.md`, `AGENTS.md`)
- ✓ All phase instructions follow phase-gated execution model

---

## Summary

**Cleanup Status:** ✓ COMPLETE
**Files created/changed:** 3 (1 backup, 1 intermediate, 1 active)
**Registry entries before:** 5 (1 PASS + 4 FAIL)
**Registry entries after:** 1 (1 PASS + 0 FAIL)
**Tests passed:** 6/6
**Blockers:** 0

The active registry is now claim-safe and ready for Phase A execution.

---

## Final Decision Label

**Status:** `ready for Phase A`

**Rationale:**
- Active registry cleanup successfully completed
- All 4 FAIL legacy entries removed
- Single PASS entry (`prepare_reminder_creation_args`) retained and verified
- Validation proof: held_out_check_count=1, negative_applicability_count=2, runtime_smoke_passed=true
- Side-effect preservation: add_reminder correctly preserved and required
- FAIL entries mechanically excluded from runtime loading (cannot be injected)
- Protocol consistency verified (no violations found)
- All 6 lightweight verification tests passed
- No blockers remain

**Immediate next step:** Proceed to Phase A execution per `docs/sage_protocol/01_phase_A_foundation_measurement_provenance.md`

---

**Cleanup completed:** 2026-05-02
**Auditor:** Codex (registry cleanup micro-step)
**Review status:** Awaiting human approval to proceed to Phase A
