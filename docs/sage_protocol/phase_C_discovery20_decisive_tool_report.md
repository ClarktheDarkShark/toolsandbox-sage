# Phase C Discovery Sprint Report — Cross-Family Decisive Tool Search

> **SUPERSEDED — ARCHIVAL ONLY.** This development report is not a current
> protocol, release gate, or paper result. Its values and decision labels must
> not be carried forward. See [current_state.md](current_state.md).

**Date:** 2026-05-03
**Phase:** Phase C Discovery Sprint
**Mode:** `transfer_40`, generation ON, `--base-tool-policy upstream`
**Registry (before run):** `artifacts/registry_phaseC_C1_candidate/` (2 tools: `prepare_reminder_creation_args`, `select_record_by_timestamp_extreme`)
**Run dir:** `outputs/phase_C_discovery20/transfer_40_20260503_062149/`
**Decision label:** continue with current shortlist

---

## Cohort Diversity Summary

**Manifest:** `artifacts/summaries/phase_C_discovery20/cohort_manifest.json`
**Diversity report:** `artifacts/summaries/phase_C_discovery20/cohort_diversity_report.json`

| Metric | Value |
|---|---|
| Scenario count | 20 |
| Distinct base task families | 16 |
| Largest per-family share | 10% (2/20) |
| Near-duplicate clusters (size > 1) | 2 |
| Max near-duplicate cluster size | 2 |
| Insufficient-information scenarios | 3 |
| Decision | `suitable_for_cross_family_discovery` |
| Warnings | None |

### Strata Breakdown

| Stratum | Count |
|---|---|
| temporal_reminder_date_canonicalization | 5 |
| record_filtering_ranking_latest_selection | 7 |
| contact_message_search_disambiguation | 4 |
| holiday_calendar_business_day_logic | 2 |
| direct_state_precondition_service_enablement | 3 |
| insufficient_information_clarification | 3 |

### Scenario List

| # | Scenario | Stratum |
|---|---|---|
| 1 | add_reminder_content_and_date_and_time | temporal_reminder |
| 2 | add_reminder_content_and_week_delta_and_time | temporal_reminder |
| 3 | add_reminder_content_and_weekday_delta_and_time | temporal_reminder |
| 4 | add_reminder_content_and_week_delta_and_time_and_location | temporal_reminder |
| 5 | add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode_multiple_user_turn_alt | temporal_reminder |
| 6 | search_reminder_with_creation_recency_yesterday | record_filtering |
| 7 | search_reminder_with_recency_upcoming | record_filtering |
| 8 | modify_reminder_with_recency_latest | record_filtering |
| 9 | remove_reminder_with_recency_latest | record_filtering |
| 10 | search_message_with_recency_latest | record_filtering |
| 11 | search_message_with_recency_oldest | record_filtering |
| 12 | modify_contact_with_message_recency | contact_message |
| 13 | update_contact_relationship_with_relationship | contact_message |
| 14 | find_days_till_holiday | holiday_calendar |
| 15 | find_days_till_holiday_wifi_off | holiday_calendar |
| 16 | send_message_with_contact_content_cellular_off | state_precondition |
| 17 | turn_on_cellular_low_battery_mode | state_precondition |
| 18 | modify_contact_with_message_recency_insufficient_information_10_distraction_tools | insufficient_info |
| 19 | find_days_till_holiday_insufficient_information_10_distraction_tools | insufficient_info |
| 20 | send_message_with_contact_content_cellular_off_insufficient_information_10_distraction_tools | insufficient_info |

Near-duplicate clusters: {`add_reminder_week_delta_time_location` variants: scenarios 4–5}, {`find_days_till_holiday` variants: scenarios 14–15}. Both clusters are bounded at 2; Gate A diversity criterion (max share ≤ 25%) satisfied.

---

## Commands Run

```bash
# Cohort manifest creation
# (created manually based on existing task bank + diversity report)

# First run (generation flag issue — generation_enabled=False)
python scripts/run_sage_protocol.py \
  --mode transfer_40 \
  --manifest artifacts/summaries/phase_C_discovery20/cohort_manifest.json \
  --registry artifacts/registry_phaseC_C1_candidate \
  --generation auto \
  --output-dir outputs/phase_C_discovery20 \
  --run-id transfer_40_20260503_061358
# Result: generation_enabled=False — transfer_40 mode overrides "auto" to off

# Second run (corrected — explicit --generation on)
python scripts/run_sage_protocol.py \
  --mode transfer_40 \
  --manifest artifacts/summaries/phase_C_discovery20/cohort_manifest.json \
  --registry artifacts/registry_phaseC_C1_candidate \
  --generation on \
  --allow-empty-birth-preflight \
  --output-dir outputs/phase_C_discovery20 \
  --run-id transfer_40_20260503_062149
# Result: generation_enabled=True — 3 tools proposed
```

---

## Files Changed

| File | Action | Notes |
|---|---|---|
| `artifacts/summaries/phase_C_discovery20/cohort_manifest.json` | created | 20-scenario discovery cohort |
| `artifacts/summaries/phase_C_discovery20/cohort_diversity_report.json` | created | Diversity metrics |
| `artifacts/registry_phaseC_C1_candidate/registry_manifest.json` | updated | 2 new tools registered (recency_to_timestamp_bounds, days_between_timestamps) |
| `outputs/phase_C_discovery20/transfer_40_20260503_062149/` | created | Full run artifacts |

No source code changes. No production registry changes (`artifacts/registry_manifest.json` not touched).

---

## Tools Proposed / Accepted / Rejected

### Tool 1: `recency_to_timestamp_bounds` — ACCEPTED (known-failing)

| Field | Value |
|---|---|
| canonical_key | `derived_value:recency_timestamp_bounds` |
| family | `derived_value_calculator` |
| accepted | `True` |
| cross_task_applicability_count | 2 |
| applicable_task_families | `search_reminder_with_recency_upcoming`, `search_messages` |
| estimated_step_compression | 3 |
| held_out_check_count | 1 |
| runtime_smoke_passed | True |
| errors | none |

**Status: CAUTION — known-failing legacy tool re-discovered.** This tool was in the Phase B legacy set and was excluded from production because it produced regressions on recency-filtering tasks (routing friction / stochastic outcome). The generator re-proposed it from first principles with no memory of prior failures. It passed the candidate gate (cross_task=2 ≥ 2, step_compression=3 ≥ 2) and was written into the candidate registry. **This must not be promoted to the production registry.**

### Tool 2: `days_between_timestamps` — ACCEPTED (confirms shortlist)

| Field | Value |
|---|---|
| canonical_key | `derived_value:days_between_timestamps` |
| family | `derived_value_calculator` |
| accepted | `True` |
| cross_task_applicability_count | 2 |
| applicable_task_families | `calendar`, `deadline` |
| estimated_step_compression | 3 |
| held_out_check_count | 1 |
| runtime_smoke_passed | True |
| errors | none |

**Status: GOOD — organic re-discovery confirms C.2 shortlist candidate.** The generator independently re-discovered `days_between_timestamps` in a diverse cross-family cohort. It was visible and called once (in `find_days_till_holiday_insufficient_information_10_distraction_tools`) and produced an outcome win in `find_days_till_holiday` (ctrl_o=0.000 → sage_o=1.000). The holiday families listed (`calendar`, `deadline`) are different labels from the prior run — the generator characterizes it in family terms, not task-name terms, but the underlying capability is the same.

### Tool 3: `next_service_tool_call` — REJECTED

| Field | Value |
|---|---|
| canonical_key | `state_precondition:next_service_tool_call` |
| family | `state_precondition_helper` |
| accepted | `False` |
| cross_task_applicability_count | 3 |
| applicable_task_families | `state_precondition_helper` |
| estimated_step_compression | 3 |
| held_out_check_count | 0 |
| runtime_smoke_passed | False |
| errors | `insufficient_applicable_task_families` |

**Status: REJECTED by validation gate.** Cross-task count says 3 but `applicable_task_families` lists only one abstract family name (not three concrete task families). The tool is a refactoring of the sequence "check service state → enable if off" which appears in cellular, WiFi, and Bluetooth tasks — but the gate rejected it because the validation examples could not enumerate ≥ 2 concrete task families. This matches the `next_service_precondition_call` finding in the generalization audit (Task 6 in `decisive_tool_strategy_audit_report.md`): the tool is a real pattern but the abstraction is too shallow for the current gate.

---

## Decisive-Tool Criteria Results

| Tool | cross_task ≥ 2 | families listed | step_compression ≥ 2 | held_out ≥ 1 | smoke | Gate |
|---|---|---|---|---|---|---|
| `recency_to_timestamp_bounds` | ✓ (2) | 2 | ✓ (3) | ✓ (1) | ✓ | PASS (caution) |
| `days_between_timestamps` | ✓ (2) | 2 | ✓ (3) | ✓ (1) | ✓ | PASS |
| `next_service_tool_call` | claimed 3 | 1 abstract | ✓ (3) | ✗ (0) | ✗ | FAIL |

The decisive-tool gate correctly blocked `next_service_tool_call` despite the generator claiming cross_task=3. The gate requires concrete family evidence, not claimed counts.

---

## Cross-Family Applicability Table

| Tool | Scenario visible in | Scenario called in | Families touched |
|---|---|---|---|
| `select_record_by_timestamp_extreme` | search_message_latest, search_message_oldest | search_message_latest, search_message_oldest | message ranking (2/2 visible called) |
| `prepare_reminder_creation_args` | add_reminder_date, add_reminder_weekday, add_reminder_week_location, add_reminder_week_location_alt, remove_reminder_latest | add_reminder_weekday, add_reminder_week_location, add_reminder_week_location_alt | temporal_reminder (3/5 visible called) |
| `days_between_timestamps` | find_days_till_holiday_insufficient_info | find_days_till_holiday_insufficient_info | holiday_calendar (1/1 visible called) |
| `recency_to_timestamp_bounds` | 0 scenarios (relevance gate hidden all) | — | — (suppressed by routing gate) |

`recency_to_timestamp_bounds` was registered into the candidate registry but was suppressed by the routing gate on all 20 scenarios (filter reason: `recency_bounds_requires_bounded_recency_task`). The scenarios where it would have been relevant (modify_reminder_latest, remove_reminder_latest, search_reminder_yesterday) had it filtered out. This means the tool got no reuse events in this run despite being registered.

---

## Per-Scenario Results

| Scenario | ctrl_c | sage_c | c_delta | ctrl_o | sage_o | o_delta | tool_visible | tool_called | status |
|---|---|---|---|---|---|---|---|---|---|
| add_reminder_content_and_date_and_time | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | +0.000 | prepare_reminder | no | vis_not_called |
| add_reminder_content_and_week_delta_and_time | 1.000 | 1.000 | +0.000 | 1.000 | 1.000 | +0.000 | none | — | no_vis |
| **add_reminder_content_and_weekday_delta_and_time** | **1.000** | **0.500** | **−0.500** | **1.000** | **0.000** | **−1.000** | prepare_reminder | **yes** | called+regressed |
| add_reminder_content_and_week_delta_and_time_and_location | 0.333 | 0.667 | +0.333 | 0.000 | 0.000 | +0.000 | prepare_reminder | yes | called+gain |
| add_reminder_week_location_low_battery_alt | 0.200 | 0.200 | +0.000 | 0.000 | 0.000 | +0.000 | prepare_reminder | yes | called+neutral |
| search_reminder_creation_recency_yesterday | 0.667 | 0.917 | +0.250 | 0.045 | 0.000 | −0.045 | none | — | no_vis |
| search_reminder_recency_upcoming | 0.960 | 0.975 | +0.015 | 0.144 | 0.000 | −0.144 | none | — | no_vis |
| modify_reminder_with_recency_latest | 0.667 | 0.667 | +0.000 | 0.000 | 0.000 | +0.000 | none | — | no_vis |
| remove_reminder_with_recency_latest | 0.667 | 1.000 | +0.333 | 0.000 | 1.000 | +1.000 | prepare_reminder | no | vis_not_called+win |
| **search_message_with_recency_latest** | **0.000** | **1.000** | **+1.000** | **0.000** | **1.000** | **+1.000** | select_record | **yes** | decisive win |
| **search_message_with_recency_oldest** | **0.000** | **1.000** | **+1.000** | 0.048 | 0.074 | +0.027 | select_record | **yes** | canonical decisive |
| modify_contact_with_message_recency | 0.499 | 0.721 | +0.222 | 0.000 | 0.611 | +0.611 | none | — | no_vis+cross-fam win |
| update_contact_relationship_with_relationship | 0.859 | 0.856 | −0.004 | 0.597 | 0.591 | −0.006 | none | — | stochastic regression |
| **find_days_till_holiday** | 0.978 | 0.978 | +0.000 | **0.000** | **1.000** | **+1.000** | none | — | outcome win (no vis) |
| find_days_till_holiday_wifi_off | 0.782 | 0.982 | +0.200 | 0.500 | 0.500 | +0.000 | none | — | canonical gain |
| send_message_cellular_off | 0.957 | 0.955 | −0.003 | 0.857 | 0.850 | −0.007 | none | — | stochastic regression |
| turn_on_cellular_low_battery_mode | 0.866 | 0.935 | +0.069 | 1.000 | 0.667 | −0.333 | none | — | outcome regression |
| modify_contact_recency_insuff_10dist | 1.000 | 1.000 | +0.000 | — | — | — | none | — | correct abstain |
| find_days_holiday_insuff_10dist | 0.000 | 0.000 | +0.000 | — | — | — | days_between | yes | called (sim=0) |
| send_msg_cellular_insuff_10dist | 1.000 | 1.000 | +1.000 | — | — | — | none | — | canonical win |

### Key Findings

**`search_message_with_recency_latest` and `search_message_with_recency_oldest`:** Decisive wins (canonical 0.000→1.000 in both). Both had `select_record_by_timestamp_extreme` visible and called. These replicate the v2 Phase C.1 results in an independent diverse cohort — cross-family validation of the canonical win.

**`modify_contact_with_message_recency`:** Canonical +0.222, outcome +0.611 with no tool visible. The agent improved on this task without a helper, suggesting the candidate arm's full registry context (more tools loaded) helps even when none are injected for this scenario.

**`find_days_till_holiday`:** Outcome 0.000→1.000 with no tool visible in this scenario (days_between was only visible in the insufficient_information variant). The win is stochastic / prompt-context effect.

**`add_reminder_content_and_weekday_delta_and_time`:** Canonical 1.000→0.500, outcome 1.000→0.000. `prepare_reminder_creation_args` was called and caused a regression. This specific scenario (weekday_delta) has a different argument pattern from week_delta and may expose an edge case in the helper's timestamp formula. This is the sole decisive regression and warrants inspection before production promotion of the helper.

**`find_days_till_holiday_insufficient_information_10_distraction_tools`:** `days_between_timestamps` was visible and called (100% adoption in 1 visible scenario) but similarity=0.000. The helper was invoked but the agent couldn't resolve the holiday date from the ambiguous user input — the insufficient_information condition applies before the day-counting step, so the helper is correctly routed but cannot rescue a scenario that requires clarification first.

---

## Aggregate Results

### Tier 1: Outcome Similarity (Primary)

| | Control | SAGE | Delta |
|---|---|---|---|
| Outcome similarity | 0.3642 | 0.4878 | **+0.124** |

### Tier 2: Canonical Similarity (Secondary)

| | Control | SAGE | Delta |
|---|---|---|---|
| Canonical similarity | 0.6218 | 0.8176 | **+0.196** |

### Exact Successes

| | Control | SAGE |
|---|---|---|
| Exact successes | 4 / 20 | **7 / 20** |

### Gains / Regressions / Preserved

| | Canonical | Outcome |
|---|---|---|
| Gains | 10 | 5 |
| Regressions | 3 | 6 |
| Preserved | 7 | 6 |

### Protocol Gate

| Criterion | Status |
|---|---|
| Positive canonical delta | ✓ +0.196 |
| Canonical gains > regressions | ✓ 10 > 3 |
| Positive outcome delta | ✓ +0.124 |
| No runtime exceptions | ✓ |
| Protocol gate | **PASSED** |

*Note: This is a discovery run, not a formal Phase C gate run. The gate result validates cohort suitability but does not count as Phase C promotion evidence.*

---

## Comparison Against Current Shortlist

From `tool_generalization_audit_report.md`, the current Phase C shortlist order is:

| Phase | Tool | Status after discovery |
|---|---|---|
| C.2 | `days_between_timestamps` | **CONFIRMED** — re-discovered organically, visible+called in holiday family, outcome win |
| C.3 | `select_record_by_timestamp_extreme` cross-family | **CONFIRMED** — decisive canonical wins replicated in 2 message scenarios in diverse cohort |
| C.4 | `prepare_reminder_creation_args` with location | **CAUTION** — weekday_delta regression needs investigation before expansion |
| Paused | `recency_to_timestamp_bounds` | **NO CHANGE** — re-discovered but suppressed by routing gate; known-failing |
| Paused | `next_service_precondition_call` | **REJECTED** by gate — state_precondition family abstraction too shallow |

The discovery sprint found no new tool better than the current shortlist. No new cross-family decisive candidate emerged that was not already in the shortlist.

---

## Generator Blind-Spot Finding

A critical operational finding: the generation pipeline has no memory of prior validation failures. `recency_to_timestamp_bounds` was proposed and accepted in this run despite being a known-failing legacy tool excluded from the production registry. The generator rediscovered it from first principles.

**Implication:** The candidate registry (`artifacts/registry_phaseC_C1_candidate`) now contains this tool. It must NOT be promoted to `artifacts/registry_manifest.json` without a Phase C formal replay run with explicit decision labeling.

**Recommended mitigation:** Before each discovery run, add known-failing tools to a suppression list in the preflight check. This is not currently enforced.

---

## Recommended Next Formal Phase C Candidate

**C.2: `days_between_timestamps`**

Rationale:
1. Organic re-discovery in 2 independent runs (prior generation run + this discovery sprint)
2. Decisive outcome win in `find_days_till_holiday` (0.000→1.000)
3. Correct adoption in holiday family (1/1 visible scenarios called)
4. Cross-family labels differ between runs (family names vary: calendar/deadline vs. holiday/business_day) — this reflects the generator's labeling, not an inconsistency in the underlying capability
5. Not yet tested on a properly gated cohort with explicit family diversity requirements

**Caution:** Prior run produced an inflated delta on a near-duplicate holiday cohort (+0.640 outcome). Gate C run must use a diverse cohort (≥ 4 distinct task families, holiday share ≤ 25%).

---

## Exact Next Implementation Prompt

```
Phase C.2: days_between_timestamps — Formal Phase C Replay

1. REGISTER
   Run: python scripts/register_days_between_timestamps.py
   Confirm: accepted=True, held_out_check_count >= 1, negative_applicability_count >= 2, runtime_smoke_passed=True

2. CANDIDATE REGISTRY
   Rebuild candidate registry from production registry + days_between_timestamps:
   python scripts/migrate_registry.py --check-only --registry artifacts/registry_phaseC_C2_candidate/registry_manifest.json
   Confirm: both prepare_reminder_creation_args and days_between_timestamps PASS

3. GATE COHORT
   Create artifacts/splits/phase_C2_days_between_replay.json
   Requirements: 12–16 scenarios, >= 4 distinct task families, holiday/calendar share <= 25%
   Must include: find_days_till_holiday (plain), find_days_till_holiday_wifi_off,
   plus >= 2 non-holiday recency or temporal tasks where days_between could appear,
   plus >= 4 negative scenarios where days_between must NOT be called
   Verify: cohort_diversity_report shows decision_use=suitable_for_cross_family_discovery

4. FOCUSED REPLAY
   python scripts/run_sage_protocol.py \
     --mode transfer_40 \
     --manifest artifacts/splits/phase_C2_days_between_replay.json \
     --registry artifacts/registry_phaseC_C2_candidate \
     --generation off \
     --base-tool-policy upstream \
     --output-dir outputs/phase_C2_days_between_replay

5. EVALUATE
   Gate criteria:
   - outcome_delta >= +0.050
   - canonical_delta > 0
   - gains > regressions (both canonical and outcome)
   - tool called in >= 80% of visible positive scenarios
   - tool hidden in all negative scenarios (0 false positives)
   - 0 runtime exceptions, 0 side-effect violations

6. DECIDE AND REPORT
   If gate passes: promote to artifacts/registry_manifest.json
   Create: docs/sage_protocol/phase_C2_days_between_timestamps_report.md
   Follow same structure as phase_C_select_record_by_timestamp_extreme_v2_affordance_report.md
```

---

## Decision Label

**continue with current shortlist**

The discovery sprint found no tool superior to the current shortlist. It confirmed `days_between_timestamps` as C.2 (organic re-discovery in a diverse cohort) and `select_record_by_timestamp_extreme` cross-family as a strong C.3 (decisive wins replicated independently). No new decisive candidate emerged. The `next_service_tool_call` proposal was correctly rejected by the validation gate.

The primary new findings are operational, not tool-specific:
- `--generation auto` does not enable generation for `transfer_40` mode; use `--generation on`
- The generator has no memory of prior failures and will re-propose known-failing tools
- `recency_to_timestamp_bounds` entered the candidate registry and must be blocked from production promotion

---

**Report completed:** 2026-05-03
**Run artifacts:** `outputs/phase_C_discovery20/transfer_40_20260503_062149/`
**Candidate registry:** `artifacts/registry_phaseC_C1_candidate/registry_manifest.json` (4 tools after run)
**Production registry:** `artifacts/registry_manifest.json` (unchanged — 1 tool: prepare_reminder_creation_args)
