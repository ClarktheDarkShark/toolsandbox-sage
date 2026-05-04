# Grading and Scoring Deep-Review Report

**Date:** 2026-05-02
**Scope:** All scoring/grading issues visible in Phase B nearby-reminder cohort results
**Purpose:** Determine root cause, origin (benchmark vs. SAGE), and fair evaluation strategy for research-quality comparison
**Supersedes:** `grading_mismatch_audit_report.md` (first-pass analysis — incomplete, now archived)

---

## Executive Summary

Three distinct grading/scoring issues were found. Only one is a SAGE-introduced defect. The others are inherent benchmark properties or evaluation design choices working as intended.

| Issue | Origin | Status | Action Required |
|-------|--------|--------|-----------------|
| 1. Agent parallel-calls helper with incomplete args | SAGE-introduced | **Real defect** | Fix helper description |
| 2. Route-dependent canonical scoring | Original benchmark (ToolSandbox design) | Expected behavior | Report both metrics; document fairness limitation |
| 3. State milestone pass-through in outcome_score.py | SAGE evaluation design | Working as intended | No change needed |

**Primary recommendation:** Fix the helper description to prevent parallel calling, rerun Phase B, and report canonical + outcome scores with explicit route-mismatch analysis as the dissertation evaluation strategy.

---

## Issue 1 — Agent Parallel Calling Convention Failure (SAGE-Introduced)

### What Was Observed

In `add_reminder_content_and_date_and_time` (and similarly structured scenarios), the SAGE candidate trajectory shows:

```
Message 16: agent → [tool_call] datetime_info_to_timestamp({year:2024, month:3, day:22, hour:17, minute:0, second:0})
Message 16: agent → [tool_call] prepare_reminder_creation_args({
    content: "buy chocolate milk",
    resolved_reminder_timestamp: 0,
    current_timestamp: <valid>,
    day_offset: 0,
    hour: 17,
    minute: 0,
    time_fields_complete: False,   ← WRONG
    ...
})
Message 17: datetime_info_to_timestamp result: 1711141200.0
Message 18: prepare_reminder_creation_args result: {
    should_call_add_reminder: False,
    abstain_reason: "missing_time_info"
}
```

The agent issued both calls **in a single parallel batch** (one assistant turn). Because `datetime_info_to_timestamp` had not yet returned, the agent:
- Passed `resolved_reminder_timestamp=0` (the "not provided" sentinel)
- Passed `time_fields_complete=False` even though hour/minute/day_offset were populated — likely because it was uncertain whether the direct timestamp would be used

### Root Cause

The helper's abstain logic is correct and well-specified:

```python
if resolved_reminder_timestamp > 0:
    ts = resolved_reminder_timestamp
elif time_fields_complete:
    # compute from time fields
else:
    return {"should_call_add_reminder": False, "abstain_reason": "missing_time_info"}
```

The helper receives `resolved_reminder_timestamp=0` AND `time_fields_complete=False`, so it correctly abstains. **The helper code is not buggy.** The bug is that the agent calls the helper before having the timestamp result.

### Why This Happens

The helper description in `artifacts/registry_manifest.json` says:

> *"CALL THIS HELPER instead of datetime_info_to_timestamp + add_reminder. Call path: prepare_reminder_creation_args(…) → add_reminder(…). After get_current_timestamp, call this helper directly with the time fields — do not compute the timestamp manually first."*

This description says "instead of datetime_info_to_timestamp" — meaning the helper was designed to **replace** that call, not be paired with it. When the agent encounters a scenario where the user provides a specific date/time (not a relative offset), it calls `datetime_info_to_timestamp` for that absolute date AND simultaneously calls the helper (thinking both are needed). The description does not clearly forbid this parallel pattern.

### Classification

**SAGE-introduced defect.** The original ToolSandbox control agent does not have this helper and simply calls `datetime_info_to_timestamp` → `add_reminder` sequentially. SAGE introduced the helper and an ambiguous description that fails to prevent parallel invocation.

### Fix Required

The helper description must be revised to explicitly state the two valid call paths and forbid the hybrid pattern:

**Path A (date/time already known as absolute date):** Pass `resolved_reminder_timestamp` = result of `datetime_info_to_timestamp`. Call `datetime_info_to_timestamp` FIRST, then call this helper with the result. Do NOT call both in the same turn.

**Path B (relative offset known, e.g. "tomorrow at 5pm"):** Set `time_fields_complete=True` and provide all time fields. Do NOT call `datetime_info_to_timestamp` first.

The revised description must include the phrase: *"Never call datetime_info_to_timestamp and this helper in the same turn."*

---

## Issue 2 — Route-Dependent Canonical Scoring (Original Benchmark Property)

### What Was Observed

The dashboard showed `datetime_info_to_timestamp` milestone for SAGE as **"No matching evidence"** — score 0 — even in cases where the reminder was created correctly via the helper. This drove SAGE's canonical score below the control baseline.

### Root Cause

ToolSandbox's canonical scorer evaluates milestones against the actual tool-call trace. If a milestone expects `datetime_info_to_timestamp` to be called and the agent did not call it (because the helper computed the timestamp internally), the grader correctly scores it 0 — there is literally no matching evidence in the trace.

This is documented in the ToolSandbox evaluation design: canonical scoring is **route-dependent** by construction. The benchmark was designed for a fixed tool set with a fixed call graph, not for a SAGE-style system that may substitute composite helpers.

### Is This a Bug?

No — it is an inherent limitation of canonical scoring for any system that takes alternate valid routes. The benchmark is measuring "did the agent call the tools we expected" not "did the task succeed." For a vanilla agent, these are equivalent. For SAGE, they diverge.

### Classification

**Original benchmark property.** Not introduced by SAGE. However, SAGE's design (substituting helpers for base tools) makes this limitation materially visible in a way that baseline evaluation does not.

### Implication for Fairness

When SAGE's helper successfully computes a timestamp and creates a reminder without calling `datetime_info_to_timestamp`, the canonical scorer penalizes SAGE for not calling a tool it was explicitly designed to bypass. This creates systematic downward pressure on SAGE's canonical score even when task outcomes are equivalent.

This does **not** make canonical scores invalid — they accurately measure canonical route adherence. But they must not be used as the sole metric for comparing SAGE to baseline, because SAGE is architecturally designed to deviate from those routes.

### Correct Treatment

Report canonical score as a secondary/diagnostic metric, not the primary outcome metric. See Evaluation Strategy section below.

---

## Issue 3 — State Milestone Pass-Through in outcome_score.py (Working as Intended)

### What Was Observed

`outcome_score.py` excludes route-only milestones (`included=False` for `kind=route`) but passes state milestones through the canonical score unchanged:

```python
if _has_state_target(milestone):
    checks.append({
        "index": index,
        "kind": "state",
        "included": True,
        "score": float(canonical_milestone_scores.get(index, 0.0)),  # ← canonical passthrough
    })
```

For scenarios where the reminder was never created, the REMINDER state milestone has canonical score 0, which flows into outcome_score as 0. This means outcome_similarity is 0 even though route milestones were excluded.

### Is This a Bug?

No. If the reminder was not created, the final database state is wrong regardless of how the agent arrived there. The state milestone should score 0. Passing the canonical state score through is correct: canonical scoring evaluates whether the REMINDER table contains the expected row — that check does not depend on which route was taken.

### Classification

**Working as intended.** The outcome scorer correctly separates route accountability (excluded) from state accountability (kept) and answer accountability (re-evaluated). This design is sound.

### Implication

The large final-task regression in Phase B (`-0.461`) reflects genuine task failures — in most SAGE scenarios, the reminder was never created because the helper abstained (due to Issue 1). These are real failures, not scoring artifacts.

---

## Relationship Between the Three Issues

```
User asks: "Remind me to buy chocolate milk 3/22/2024 5PM"
                        │
         SAGE agent: parallel call batch
         ├── datetime_info_to_timestamp(date=3/22/2024, time=5PM)
         └── prepare_reminder_creation_args(resolved_ts=0, time_fields_complete=False, ...)
                        │
         Issue 1:  helper abstains (correctly, given bad args)
         Issue 2:  canonical grader: datetime_info_to_timestamp milestone → "No matching evidence" → 0
         Issue 3:  state milestone (REMINDER row) → 0 (correct, reminder not created)
                        │
         Result: canonical 0.5, outcome_similarity 0.0
         Root cause: Issue 1 (parallel calling) → Issues 2 and 3 are consequences
```

Issues 2 and 3 would surface independently even if Issue 1 were fixed — but they would produce **different outcomes**: Issue 2 would still penalize canonical score when the helper bypasses `datetime_info_to_timestamp`, and Issue 3 would correctly score 1.0 when the reminder is actually created.

---

## Evaluation Strategy Recommendation

### For Research-Quality Comparison (Dissertation)

Three-tier reporting is recommended:

#### Tier 1 (Primary): Outcome Similarity

**`outcome_similarity`** (from `outcome_score.py`) is the fairest metric for comparing SAGE to baseline because:
- Route-only milestones are excluded — SAGE is not penalized for using a helper instead of base tools
- State milestones are kept — task completion is still required
- Answer milestones are independently re-evaluated — not route-locked

**Use this as the headline metric** for SAGE vs. control comparisons.

#### Tier 2 (Secondary): Canonical Similarity

**`mean_similarity`** (ToolSandbox canonical) is the reference metric. It:
- Shows how closely SAGE follows expected tool-call routes
- Is comparable to published ToolSandbox results (external validity)
- Will show downward pressure on SAGE by design (route substitution)

**Use this as a benchmark-reference metric** with explicit note that it underrepresents SAGE's route-taking capability.

#### Tier 3 (Explanatory): Route Mismatch Analysis

For each scenario where canonical < outcome, document:
- Which route milestones were missed (e.g., `datetime_info_to_timestamp`)
- Whether the helper was used instead (substitution)
- Whether the final state was achieved (outcome)

This allows the dissertation to make the claim: *"SAGE successfully substituted generated helpers for base tools. Route-dependent canonical scoring systematically underestimates SAGE's task completion. After route-adjustment, SAGE achieves X% task completion vs. Y% for baseline."*

### Reporting Template for Phase C+

```
Evaluation Results
==================
Primary metric: Outcome similarity (route-independent)
  Control: [value] | SAGE: [value] | Delta: [value]

Reference metric: Canonical similarity (route-dependent, ToolSandbox standard)
  Control: [value] | SAGE: [value] | Delta: [value]

Route mismatch analysis:
  Scenarios where canonical < outcome: [N]
  Scenarios where helper substituted expected route tools: [N]
  Scenarios where helper correctly produced equivalent outcome: [N]
  Scenarios where helper failed (abstain, error, wrong output): [N]

Exact success rate (outcome_similarity = 1.0):
  Control: [N]/[total] | SAGE: [N]/[total]
```

---

## Required Actions Before Phase B Rerun

### Action 1: Revise Helper Description (Required)

Edit `artifacts/registry_manifest.json`, field `tools.prepare_reminder_creation_args.spec.description`.

Current:
> "CALL THIS HELPER instead of datetime_info_to_timestamp + add_reminder. Call path: prepare_reminder_creation_args(…) → add_reminder(**result['add_reminder_kwargs']). After get_current_timestamp, call this helper directly with the time fields — do not compute the timestamp manually first."

Replace with a description that:
1. States both valid call paths explicitly (Path A: pre-resolved timestamp from datetime call; Path B: time fields directly)
2. Explicitly forbids calling `datetime_info_to_timestamp` and this helper in the same turn
3. Makes clear that `time_fields_complete=True` requires ALL four fields (day_offset, hour, minute, local_utc_offset_hours) to be known and provided

After editing the description, re-hash and update `code_hash` if the helper code itself changes, or note that only the spec was updated.

### Action 2: Validate Against Smoke Scenarios (Required)

Before rerunning the full cohort, run the 6-scenario tiny smoke benchmark:
- Confirm helper is called (not bypassed)
- Confirm `should_call_add_reminder=True` in simple date+time scenarios
- Confirm `datetime_info_to_timestamp` is NOT called in the same parallel batch as the helper

### Action 3: Rerun Phase B Nearby Cohort (Required)

With corrected description, rerun:
```
python scripts/run_sage_protocol.py \
  --mode transfer_40 \
  --manifest outputs/splits/phase_B_nearby_reminder12.json \
  --agent gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --base-tool-policy upstream \
  --registry-dir artifacts \
  --generation off \
  --cache-mode write_only \
  --output-root outputs/phase_B_v2_corrected_description \
  --dashboard-port 5520
```

Report results using three-tier evaluation template above.

### Action 4: Update Grading Mismatch Audit Report

`docs/sage_protocol/grading_mismatch_audit_report.md` (first-pass report) concluded "helper logic bug in abstention check." This was incorrect — the helper logic is correct; the agent calling convention is the defect. That report should be marked superseded by this document.

---

## Assessment of Phase B Results Under Correct Framing

Given what we know now, the Phase B nearby-cohort results (`-0.155` canonical, `-0.461` final-task) reflect:

| Scenario group | Count | True cause of failure |
|---------------|-------|----------------------|
| Helper abstained due to parallel calling | ~5 | Issue 1 (SAGE defect, fixable) |
| Helper worked correctly | ~4 | No failure — SAGE better or equal |
| Helper correctly not called (modify/search) | 3 | Correct behavior |

After fixing Issue 1, we expect:
- The ~5 abstention failures to become successes (or at least not abstentions)
- Canonical score will still be depressed for scenarios where helper bypasses `datetime_info_to_timestamp` (Issue 2)
- Outcome score will improve significantly once reminders are actually created

The Phase B "suppress/retire candidate" decision was based on the uncorrected run. It should not be finalized until the corrected rerun is complete.

---

## Conclusion

**Is the grading system fair?** Yes, with one caveat: canonical scoring systematically underestimates SAGE when helpers substitute route tools. This is a known property of the benchmark, not a bug. Using `outcome_similarity` as the primary metric resolves this.

**Is the Phase B failure real?** Partially. ~5 of 9 failures are caused by a fixable SAGE defect (parallel calling convention). ~4 scenarios showed the helper working as designed.

**What needs to change?**
1. Helper description → prevent parallel calling
2. Evaluation reporting → use outcome_similarity primary, canonical secondary
3. Phase B rerun → with corrected description

**Status:** `true_calling_convention_failure; fix_description_and_rerun_phase_b`

---

**Report completed:** 2026-05-02
**Supersedes:** `grading_mismatch_audit_report.md`
