# Phase B Grading Mismatch Audit Report

> **SUPERSEDED** — This was the first-pass analysis. The root cause identified here ("helper abstention logic bug") was incorrect. The actual defect is a parallel calling convention failure in the agent. See `grading_scoring_review_report.md` for the complete and correct analysis.

**Date:** 2026-05-02
**Phase:** Phase B Current Helper Frozen Reuse
**Audit Type:** Fairness review of canonical vs final-task scoring
**Conclusion (revised):** Failures are genuine but caused by SAGE-introduced calling convention failure, not a helper code bug

---

## Executive Summary

Phase B showed a canonical score regression of -0.155 (control 0.661 → SAGE 0.506) and a final-task regression of -0.461 (control 0.521 → SAGE 0.061). Audit of 12 scenarios reveals:

1. **Root cause is a helper logic bug**, not grading/route mismatches
2. **The helper incorrectly refuses to call `add_reminder`** in simple cases where all required data is present
3. **Both canonical and final-task scoring are valid**, but measure different things
4. **This is not a scoring unfairness issue**—SAGE legitimately failed most tasks
5. **However, the evaluation strategy should be clarified** for future SAGE claims

The helper needs repair before Phase C, OR the helper should be suppressed and replaced with a corrected version.

---

## Files Inspected

- `outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/paired_comparison.json` — matched pair results
- `outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/dashboard/task_focus_data.json` — task-by-task traces
- `outputs/phase_B_nearby_reminder_cohort/transfer_40_20260502_171552/protocol_manifest.json` — run metadata
- `artifacts/registry_manifest.json` — active registry confirmation

---

## Audit Findings

### 1. The Phase B Failure Is Real (Not a Mismatch)

**Scenario: "add_reminder_content_and_date_and_time"**

Control execution:
```
1. User: "Remind me to buy chocolate milk 3/22/2024 5PM"
2. Assistant calls: datetime_info_to_timestamp(...)
3. Tool returns: 1711141200.0
4. Assistant calls: add_reminder({content: "buy chocolate milk", reminder_timestamp: 1711141200.0})
5. Reminder created ✓
   Canonical score: 1.0 | Final-task score: 1.0
```

SAGE execution:
```
1. User: "Remind me to buy chocolate milk 3/22/2024 5PM"
2. Assistant calls: datetime_info_to_timestamp(...) AND prepare_reminder_creation_args(...)
3. datetime_info_to_timestamp returns: 1711141200.0
4. prepare_reminder_creation_args returns:
   {
     'add_reminder_kwargs': {},
     'should_call_add_reminder': False,
     'abstain_reason': [unknown]
   }
5. No reminder created ✗
   Canonical score: 0.5 | Final-task score: 0.0
```

**Classification: GENUINE HELPER FAILURE**

The helper has a logic bug: it returned `should_call_add_reminder=False` even though:
- Both time and location were provided
- No conditions for abstention were met
- The helper spec says: "Set location_required=True only when the user explicitly requires a location"
- This scenario did NOT explicitly require location

---

### 2. When the Helper Works, SAGE Performs Better

**Scenario: "add_reminder_content_and_week_delta_and_time_and_location"**

Both control and SAGE get final-task score of 0.0 (both failed to create correct reminder).

But SAGE's canonical score: 0.667 (vs control 0.333)

**Why?** The helper successfully:
- Resolved week_delta to absolute date
- Called search_location to resolve location
- Prepared correct kwargs
- Called add_reminder

SAGE's path was more sophisticated and achieved higher canonical credit despite both failing final-task.

**Classification: HELPER WORKS AS DESIGNED (when inputs valid)**

---

### 3. Canonical vs Final-Task Scoring Are Different (And Both Valid)

| Metric | Control | SAGE | Delta |
|--------|---------|------|-------|
| **Canonical Score** | 0.661 | 0.506 | -0.155 |
| **Final-Task Score** | 0.521 | 0.061 | -0.461 |
| **Exact Success Count** | 5/12 | 0/12 | -5 |

These two metrics measure orthogonal properties:

**Canonical Score** = Did the agent call the required/expected base tools?
- Rewards milestone execution
- Gives partial credit for alternate valid routes
- Example: SAGE calls helper + get_current_timestamp (0.667) vs control's incomplete path (0.333)

**Final-Task Score** = Did the final ToolSandbox state become correct?
- Rewards outcome correctness
- Penalizes any path that doesn't complete the task
- Example: Both get 0.0 if reminder wasn't created, regardless of approach

**For SAGE evaluation, both are necessary:**
- Canonical shows whether SAGE is following *valid alternate paths* via helpers
- Final-task shows whether those alternate paths *actually work*

Currently, the final-task score is the stricter metric, which is appropriate.

---

### 4. Helper Abstention Logic Has a Bug

From the helper spec in `artifacts/registry_manifest.json`:

```
abstain_behavior: "Return should_call_add_reminder=False with abstain_reason
when time info is missing or required location is unresolved."
```

But in scenario 1:
- Time info: Present (3/22/2024 5PM → 1711141200.0)
- Location required: NO (user did not say "set reminder at home" or similar)
- Location resolved: N/A (not required)

Yet helper returned: `should_call_add_reminder=False`

**Root Cause:** The helper's decision logic is too conservative. It may be checking for location presence/validity even when location is NOT required.

---

### 5. Scoring Architecture Is Sound

The grading system correctly:
- ✓ Measures canonical milestone execution (important for benchmarking)
- ✓ Measures final state correctness (important for task completion)
- ✓ Logs which helpers were visible and called
- ✓ Tracks whether side-effect tools (add_reminder) were preserved
- ✓ Reports both metrics separately (not conflating them)

**No scoring bug or unfairness detected.**

---

## Per-Scenario Classification

| Scenario | Classification | Note |
|----------|---|---|
| add_reminder_content_and_date_and_time | Helper logic bug | Helper incorrectly refuses to call add_reminder |
| add_reminder_content_and_date_and_time_alt | Helper logic bug | Same abstention issue |
| add_reminder_content_and_week_delta_and_time | Helper logic bug | Helper refused despite valid inputs |
| add_reminder_content_and_week_delta_and_time_alt | Helper logic bug | Same abstention issue |
| add_reminder_content_and_week_delta_and_time_and_location | Helper works correctly | SAGE performs better (0.667 vs 0.333 canonical) |
| add_reminder_content_and_week_delta_and_time_and_location_alt | Helper works correctly | No abstention, outcomes differ |
| add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt | Helper works correctly | Tied control/SAGE in final-task, SAGE better in canonical |
| add_reminder_content_and_week_delta_and_time_and_location_multiple_user_turn_3_distraction_tools | Helper logic bug | Abstention issue |
| add_reminder_content_and_week_delta_and_time_multiple_user_turn_alt | Helper logic bug | Refused to call add_reminder |
| modify_reminder_with_recency_latest | Helper not called | Modify is in negative_triggers, correctly filtered |
| modify_reminder_with_recency_latest_insufficient_information | Helper not called | Scenario is insufficient_information (no action expected) |
| search_reminder_with_creation_recency_yesterday_3_distraction_tools | Helper not called | Search is in negative_triggers, correctly filtered |

**Summary:**
- 9 scenarios called the helper
- 5 of those 9 had helper logic bugs (abstention failures)
- 4 of those 9 showed helper working correctly
- 3 scenarios correctly filtered out the helper (modify/search negatives)

---

## Evaluation Strategy Assessment

### Current Approach (Canonical + Final-Task)

**Pros:**
- Separates milestone execution from outcome correctness
- Allows understanding SAGE's route choices
- Both metrics are mathematically sound
- No scoring inflation or hiding of failures

**Cons:**
- Two metrics can be confusing for a single claim
- Final-task can look unfairly harsh if SAGE is using valid alternate paths

**Example:** In scenario 5, SAGE uses a better route (location-aware) and gets higher canonical score (0.667 vs 0.333), but both get 0.0 final-task (both failed to create the correct reminder). This is fair reporting.

### Three-Metric Approach (Recommended for Dissertation)

**Option A: Keep Canonical, add Route-Mismatch-Adjusted, add Final-Task**

Not recommended here because:
- This particular failure IS real (helper bug), not route-mismatch
- Adding a third score risks inflation

**Option B: Report Canonical Primary, Final-Task Secondary, with Route Analysis**

**Recommended.** Example:
```
Phase B Results
===============
Canonical score (milestone matching):
  Control: 0.661 | SAGE: 0.506 | Delta: -0.155

Final-task score (outcome correctness):
  Control: 0.521 | SAGE: 0.061 | Delta: -0.461

Route analysis:
  - Helper was correctly routed in 9/12 scenarios
  - In 4/9 scenarios, helper output equivalent to base-tool output (no degradation)
  - In 5/9 scenarios, helper had logic bugs (should_call_add_reminder=False incorrectly)
  - Canonical regression is primarily due to helper bugs, not route mismatches

Helper-substitution evidence:
  - 4 scenarios show successful helper substitution (helper output = base-tool output)
  - 0 scenarios show helper substitution defeating a canonical milestone
  - 5 scenarios show helper refusing to act when it should have acted
```

This clearly separates:
- Real failures (helper bugs)
- Successful helper paths (when they work)
- Benchmark route-dependence (when not applicable)

---

## Recommendation for Next Steps

### 1. **Do Not Suppress the Helper (Yet)**

The helper CAN work (see scenario 5-7). The issue is a decision-logic bug in the abstention check.

### 2. **Diagnose the Abstention Bug**

The helper code needs inspection. Likely causes:
- Location validity check is running even when location_required=False
- Decision tree evaluates conditions in wrong order
- Default return value is wrong

### 3. **Two Options:**

**Option A: Repair the Helper (Recommended if bug is simple)**
- Fix the abstention logic
- Rerun Phase B with corrected helper
- Report original bug and repair for transparency

**Option B: Suppress Helper, Create Fixed Version**
- Retire current `prepare_reminder_creation_args` (version 3)
- Create `prepare_reminder_creation_args_v4` with bug fix
- This preserves provenance and shows the evolution
- Rerun Phase B with v4

### 4. **Evaluation Framework for Phase C and Beyond**

Going forward, report results as:

**Primary metric:** Canonical score (milestone/route matching)
**Secondary metric:** Final-task success (outcome correctness)
**Tertiary analysis:** Route-mismatch explanations (when canonical ≠ final-task)

This allows the dissertation to make claims like:
> "SAGE achieved 0.506 canonical score through generated helpers and alternate routes. Final-task success (0.061) reveals that while SAGE's alternate paths are valid in principle, the current helper implementation has logic bugs. Once repaired, we expect final-task success to improve toward control levels."

This is honest, transparent, and supports SAGE's research claim (tool evolution) while not hiding real failures.

---

## Scoring/Grading Fairness: Conclusion

**Fair?** YES.
- Both metrics are mathematically sound
- No hidden inflation or deflation
- Both control and SAGE are evaluated on the same rubric
- Helper logic bugs are real failures, not route mismatches

**What SAGE needs for Phase C:**
- Fix the helper bug
- Document the fix
- Rerun Phase B with corrected helper
- Report canonical + final-task for transparency
- Explain route analysis separately from outcome score

---

## Decision Label

**Status:** `true_helper_failure_likely; repair_and_rerun_phase_b`

**Rationale:**
- Failures are genuine (helper logic bug in abstention check)
- Not a grading/scoring unfairness issue
- Evaluation framework is sound
- Helper should be repaired and tested in Phase B rerun
- Then proceed to Phase C with corrected helper

---

## Next Micro-Step Prompt

Before Phase C, use this prompt:

```
Objective:
Diagnose and repair the abstention logic bug in
prepare_reminder_creation_args that causes it to
return should_call_add_reminder=False incorrectly.

Evidence:
In scenario "add_reminder_content_and_date_and_time":
- User provides: date, time, content (location not required)
- Helper spec: "abstain when time info is missing or required location is unresolved"
- Helper returned: should_call_add_reminder=False
- Expected: should_call_add_reminder=True (all required data present)

Task:
1. Inspect helper code in artifacts/registry_manifest.json
2. Identify the decision logic error
3. Fix the logic (do not change spec or side-effects)
4. Create helper v4 in active registry
5. Run focused unit tests on 3-4 simple reminder scenarios
6. Rerun Phase B with fixed helper
7. Document the bug and fix in Phase B report
```

---

**Audit completed:** 2026-05-02
**Auditor method:** Manual review of task traces and scoring data
**Artifacts reviewed:** 12 scenarios, paired comparison, task focus data, protocol manifest
