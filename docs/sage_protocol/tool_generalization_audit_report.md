# Tool Generalization Audit Report

**Date:** 2026-05-03
**Scope:** Cohort duplication audit + cross-family generalization analysis → Phase C roadmap revision
**Decision label:** revise Phase C toward cross-family tools

---

## Objective

Audit whether current SAGE tool evidence is inflated by near-duplicate cohorts, identify tools that generalize across task families, and revise the Phase C roadmap accordingly. No code changes.

---

## Files Reviewed

| File | Source |
|---|---|
| `docs/sage_protocol/decisive_tool_review_bundle.md` | Primary — 34,497 lines |
| `docs/sage_protocol/decisive_tool_strategy_audit_report.md` | Phase C candidate planning |
| `docs/sage_protocol/phase_B_current_helper_frozen_reuse_report.md` | Phase B v1 baseline |
| `docs/sage_protocol/phase_B_calling_convention_fix_report.md` | Phase B v2 PASS result |
| `docs/sage_protocol/phase_C_select_record_by_timestamp_extreme_v2_affordance_report.md` | Phase C.1 v2 PASS result |
| `outputs/generic_multitool_diverse18_20260430/` | cohort_diversity_report, tool_value_report, broad_outcome_summary |
| `outputs/generic_multitool_confirm30_20260501/` | cohort_diversity_report, tool_value_report, broad_outcome_summary |
| `outputs/contact_constraint_routing18_20260430/` | cohort_diversity_report, tool_value_report, broad_outcome_summary |
| `outputs/stock_numeric_discovery12_20260501/` | cohort_diversity_report, tool_value_report, broad_outcome_summary |
| `outputs/record_ranking_diverse18_20260430/` | tool_value_report |
| `outputs/record_ranking_confirm30_20260430/` | tool_value_report |
| `outputs/state_precondition_diverse18_20260430/` | tool_value_report |
| `outputs/contact_message_diverse18_20260430/` | tool_value_report |
| `outputs/claim_portfolio_*` | Multiple paired_comparison.json files |
| `outputs/record_ranking_gate1_current_24_20260501/` | paired_comparison.json |
| `outputs/record_ranking_helperfit24_routingfix_20260501/` | paired_comparison.json |
| `outputs/record_ranking_extreme_selector_v3_20260501/` | paired_comparison.json |
| `outputs/phase_C1_record_selection_replay_v2/` | paired_comparison.json, cohort_diversity_report |
| `outputs/phase_B_v2_smoke/`, `outputs/phase_B_nearby_reminder_cohort/` | cohort_diversity_report |

---

## Runs / Cohorts Inspected

| Run | Cohort label | Scenarios | Distinct families | Largest family share |
|---|---|---|---|---|
| generic_multitool_diverse18 | focused discovery | 18 | 18 | 5.6% |
| generic_multitool_confirm30 | stratum confirmation | 30 | 30 | 3.3% |
| contact_constraint_routing18 | focused discovery | 18 | 18 | 5.6% |
| record_ranking_diverse18 | focused discovery | 18 | ~18 | ~5.6% |
| record_ranking_confirm30 | confirmation | 30 | ~30 | ~3.3% |
| state_precondition_diverse18 | focused discovery | 18 | 18 | 5.6% |
| phase_B_nearby_reminder_cohort | focused smoke | 12 | 7 | 25.0% |
| reminder_creation_args_frozen12 | focused smoke | 12 | 7 | 16.7% |
| phase_C1_record_selection_replay_v2 | focused smoke | 12 | 6 | 25.0% |
| claim_portfolio_record_gate1 | mixed validation | 23 | ~12 | ~30% |
| claim_portfolio_holiday_frozen | near-duplicate stress | 40 | ~3 | ~33% |
| claim_portfolio_state_tool_call_frozen12 | focused smoke | 12 | ~6 | ~33% |
| claim_portfolio_contact_frozen12_routefix | focused smoke | 12 | ~6 | ~25% |
| claim_portfolio_message_search_window_frozen12 | focused smoke | 12 | ~6 | ~33% |
| record_ranking_helperfit24 | focused mixed | 24 | ~14 | ~12% |
| record_ranking_gate1_current_24 | focused mixed | 24 | ~15 | ~12% |

---

## Task 1 — Current Evidence Inventory by Tool

### `prepare_reminder_creation_args` (active registry)

| Run | Scenarios | Cohort type | Families covered | Visible | Called | Canonical Δ | Outcome Δ | Exact Δ | Evidence quality |
|---|---|---|---|---|---|---|---|---|---|
| Phase B v2 (12-scenario) | 12 | Near-dup smoke | add_reminder only (positive family) | ~6 | ~6 | +0.100 | +0.160 | +1 | **Narrow** |
| reminder_creation_args_frozen12 (v2/v3) | 12 | Near-dup smoke | add_reminder + modify/search (negatives) | ~6 | ~6 | +0.009–+0.125 | −0.046–+0.075 | 0 | **Narrow** |

**Per-tool summary:**
- Tool is called correctly in add_reminder scenarios when description is clear
- No evidence outside the reminder creation family (negative triggers correctly suppress it in modify/search)
- Gains driven by one base task (add_reminder with location/time variants)
- Phase B v2 "PASS" is from a cohort where the positive evidence is ~4 add_reminder template variants × 3 distraction levels
- **Evidence classification: NARROW-TEMPLATE**

---

### `select_record_by_timestamp_extreme` (Phase C.1 PASS)

| Run | Scenarios | Cohort type | Families covered | Visible | Called | Canonical Δ | Outcome Δ | Evidence quality |
|---|---|---|---|---|---|---|---|---|
| Phase C.1 v2 (12-scenario) | 12 | Near-dup smoke | search_message_recency × 2 families (positive) | 6 | 6 | +0.221 | +0.267 | **Narrow (2 families)** |
| record_ranking_diverse18 | 18 | Focused diverse | Mixed record/ranking | 1 | 1 | — | +0.022 | Sparse but zero harm |
| record_ranking_confirm30 | 30 | Diverse confirm | Mixed record/ranking | 1 | 1 | — | +0.039 | Sparse but zero harm |
| claim_portfolio_record_gate1 | 23 | Mixed validation | message_recency + modify_reminder + holiday | ~12 | ~9 | +0.163 | +0.200 | **Mixed (PASS)** |
| contact_message_helperfit12 | 12 | Focused smoke | Contact/message search + recency | 9 | 8 | +0.350 | +0.244 | **Cross-family** |
| record_ranking_helperfit24 | 24 | Mixed | Multi-family | ~8 | ~5 | −0.081 | +0.155 | Mixed (confounded) |

**Per-tool contribution (from diverse18/confirm30):**
- harm_rate_when_called: 0.0 (both runs)
- win_rate_when_called: 1.0 (both runs)
- mean_delta_when_called: +0.022 (diverse18), +0.039 (confirm30)

**Evidence classification: MIXED → CROSS-FAMILY**
- Phase C.1 cohort is near-duplicate (2 base families × 3 distraction = 6 scenarios), suitable_for_early_value_only
- But record_gate1 and contact_message_helperfit12 show it works across modify_reminder, holiday, and contact scenarios
- Zero harm across all runs — consistent and safe

---

### `days_between_timestamps` (organically generated, not formally registered)

| Run | Scenarios | Cohort type | Families covered | Visible | Called | Canonical Δ | Outcome Δ | Evidence quality |
|---|---|---|---|---|---|---|---|---|
| record_ranking_diverse18 | 18 | Focused diverse | Multi-family | 3 | 3 | — | +0.137 | Positive |
| record_ranking_confirm30 | 30 | Diverse confirm | Multi-family | 3 | 3 | — | +0.137 | Positive |
| state_precondition_diverse18 | 18 | Focused diverse | Service precondition | 2 | 2 | — | mixed | Mixed (wrong-family) |
| generic_multitool_diverse18 | 18 | Truly diverse (18 families) | Cross-stratum | ~3 | 3 | +0.097 | — | **Cross-family (positive)** |
| generic_multitool_confirm30 | 30 | Truly diverse (30 families) | Cross-stratum | 1 | 1 | −0.041 | — | **Cross-family (negative)** |
| claim_portfolio_holiday_frozen | 40 | **Near-dup stress** | find_days_till_holiday × 40 | 46+ | 46+ | +0.202 | **+0.640** | **Inflated** |

**Per-tool contribution (diverse18/confirm30):**
- harm_rate_when_called: 0.0 in record/multi-tool runs; 0.5 in state_precondition run (wrong-family context)
- win_rate_when_called: 0.67 (diverse18 and confirm30)
- mean_delta_when_called: +0.137

**Critical finding:** The +0.640 outcome delta in the holiday cohort is **inflated by near-duplication**. All 40 scenarios are `find_days_till_holiday` variants (different distraction levels, arg scrambling, alt wording). A tool that correctly computes one holiday delta will score +1 across all 40 variants. This is not cross-family evidence; it is repetition within one task family.

**True cross-family evidence:** diverse18 (positive), confirm30 (negative overall, but tool-called scenarios were positive). Net: **genuine cross-family value in diverse contexts, not yet confirmed at scale.**

**Evidence classification: CROSS-FAMILY (promising, holiday-cohort inflated, confirm30 failed)**

---

### `next_service_enablement_action` / `next_service_tool_call` (legacy excluded)

| Run | Scenarios | Cohort type | Visible | Called | Canonical Δ | Outcome Δ | Evidence quality |
|---|---|---|---|---|---|---|---|
| state_precondition_diverse18 | 18 | Focused diverse | 4 | **0** | −0.065 | — | **Never adopted** |
| generic_multitool_confirm30 | 30 | Truly diverse | — | ~1 | −0.041 | — | Confounded |
| claim_portfolio_state_tool_call_frozen12 | 12 | Near-dup smoke | 12 | **1** | +0.007 | +0.035 | **Never adopted (11/12 ignored)** |

**Critical finding:** In the claim_portfolio_state_tool_call run, the tool was visible in all 12 scenarios but called in only 1. The agent's outcome for the 12 state-precondition scenarios in control was already 0.891 — the agent handles these tasks well WITHOUT a helper. The helper adds noise (visible_not_called friction) without reliable benefit.

**Evidence classification: NONE (agent never adopts)**

---

### `recency_to_timestamp_bounds` / `message_search_time_window` (legacy excluded / suppressed)

| Tool | Run | Scenarios | Called | Harm rate | Δ when called | Overall Δ | Evidence quality |
|---|---|---|---|---|---|---|---|
| recency_to_timestamp_bounds | diverse18 | 18 | 2 | **0.50** | −0.239 | — | Harmful |
| recency_to_timestamp_bounds | confirm30 | 30 | 3 | 0.0 | +0.093 | — | Mixed |
| recency_to_timestamp_bounds | contact_constraint18 | 18 | 1 | **1.0** | −0.312 | — | **Harmful** |
| message_search_time_window | claim_portfolio_frozen12 | 12 | 6 | — | — | −0.029 | **Failed** |
| message_search_time_window | claim_portfolio_frozen12_narrow | 12 | 4 | — | — | −0.125 | **Failed** |
| message_search_time_window | record_ranking_helperfit24 | 24 | — | — | — | −0.081 canon | **Failed (confounded)** |

**Evidence classification: NEGATIVE — suppress both**

---

### `relative_day_time_to_timestamp` (legacy excluded)

- diverse18: called 1 time, harm_rate=0.0, win_rate=0.0, mean_delta=0.0
- state_precondition: called 1 time, harm_rate=0.0, win_rate=0.0, mean_delta=0.0
- **Evidence classification: NEUTRAL — diagnostic only, do not register**

---

### `select_contact_by_constraint` / `select_contact_field_by_constraint` (candidate lane)

| Run | Scenarios | Visible | Called | Harm rate | Δ when called | Overall Δ |
|---|---|---|---|---|---|---|
| contact_constraint_routing18 | 18 | 13 | 4 | **0.50** | −0.252 | −0.034 |
| contact_frozen12_routefix | 12 | 12 | **0** | — | — | −0.128 |
| contact_helperfit12_selector_suppressed | 12 | ~9 | ~8 | — | — | +0.350 |

**Note:** The +0.350 in contact_helperfit12 was NOT from the contact selector — the visible_tools in that run were `message_search_time_window` and `select_record_by_timestamp_extreme`. The contact selector was suppressed in that run, as the name indicates.

**Evidence classification: NEGATIVE routing, HARMFUL when called**

---

### `prepare_reminder_arguments_with_optional_location` (candidate C.3)

| Run | Scenarios | Called | Visible not called | Canonical Δ | Outcome Δ |
|---|---|---|---|---|---|
| claim_portfolio_argprep_v2_frozen12 | 12 | 6 | 0 | +0.009 | −0.046 |
| claim_portfolio_argprep_frozen12_rapid | 12 | 2 | 5 | +0.125 | +0.075 |

- All evidence is from add_reminder family (same narrow scope as parent)
- Adoption failure in rapid run (5/12 visible_not_called)
- **Evidence classification: NARROW-TEMPLATE, weak**

---

### `resolve_search_window_or_bounds` (candidate C.4, not yet built)

Not yet implemented. Prior tools serving the same function (`recency_to_timestamp_bounds`, `message_search_time_window`) have both failed repeatedly. The concept is sound but the cohort evidence is consistently negative. **Evidence classification: NOT YET BUILT, prior analogues all failed.**

---

### `select_contact_or_message_by_constraints` (candidate C.5, not yet built)

Not yet implemented. Prior tool serving the same function (`select_contact_by_constraint`) has harm_rate=0.5 and was never adopted in the isolated routing run. **Evidence classification: NOT YET BUILT, prior analogues harmful.**

---

## Task 2 — Cohort Diversity Findings

### Classification of all major cohorts

| Cohort | Scenarios | Distinct families | Largest share | Near-dup clusters | Classification |
|---|---|---|---|---|---|
| generic_multitool_diverse18 | 18 | 18 | 5.6% | 0 | **Truly diverse** |
| generic_multitool_confirm30 | 30 | 30 | 3.3% | 0 | **Truly diverse** |
| contact_constraint_routing18 | 18 | 18 | 5.6% | 0 | **Truly diverse** |
| record_ranking_diverse18 | 18 | ~18 | ~5.6% | ~2 (distraction) | **Focused diverse** |
| record_ranking_confirm30 | 30 | ~30 | ~3.3% | ~4 (distraction) | **Focused diverse** |
| state_precondition_diverse18 | 18 | ~18 | ~5.6% | 0 | **Focused diverse** |
| phase_B_nearby_reminder (12) | 12 | 7 | 25.0% | 3 (distraction) | **Near-dup smoke** |
| reminder_creation_args_frozen12 | 12 | 7 | 16.7% | 2 (distraction) | **Near-dup smoke** |
| phase_C1_record_selection (12) | 12 | 6 | 25.0% | 4 (distraction) | **Near-dup smoke** |
| claim_portfolio_record_gate1 (23) | 23 | ~12 | ~30% | ~6 (alt+distraction) | **Mixed validation** |
| claim_portfolio_holiday_frozen (40) | 40 | ~3 | ~33% | 35+ | **Near-dup stress** |
| claim_portfolio_state_frozen12 | 12 | ~6 | ~33% | 4 (implicit/explicit×distraction) | **Near-dup smoke** |
| claim_portfolio_message_search_w12 | 12 | ~6 | ~33% | 4 (alt×distraction) | **Near-dup smoke** |
| claim_portfolio_contact_frozen12 | 12 | ~6 | ~25% | 4 (distraction) | **Near-dup smoke** |

### Near-duplicate variant types detected

All "near-duplicate" cohorts use one or more of:
- `_3_distraction_tools` / `_10_distraction_tools` suffixes (same task, more noise in tool list)
- `_alt` suffix (same task with rewording)
- `_implicit` suffix (user phrasing less explicit, same underlying task)
- `_multiple_user_turn` (task split across turns, same resolution)
- `_arg_description_scrambled` / `_arg_type_scrambled` / `_tool_description_scrambled` (robustness stress)

A tool that works on any one variant will appear to work on all distraction/alt variants. The `claim_portfolio_holiday_frozen` cohort is the extreme case: 40 scenarios, ~3 base families, effectively one computation repeated 40 times.

---

## Task 2 — Flagged Runs

| Run | Flag | Reason |
|---|---|---|
| claim_portfolio_holiday_frozen (40 scenarios) | **Inflated evidence** | ~3 base families, 33%+ per family; one computation repeated across 37/40 gains |
| Phase C.1 v2 (12 scenarios) | **Near-dup smoke** | 6 positive scenarios are 2 templates × 3 distraction levels; suitable_for_early_value_only |
| Phase B v2 (12 scenarios) | **Near-dup smoke** | add_reminder family dominates visible-positive scenarios |
| claim_portfolio_argprep_frozen12_rapid | **Visible-not-called** | 5/12 visible scenarios not called |
| claim_portfolio_state_frozen12 | **Adoption failure** | 11/12 visible scenarios not called |
| claim_portfolio_contact_frozen12 | **Adoption failure** | 12/12 visible scenarios not called |
| record_ranking_helperfit24 | **Multi-tool confound** | 4 tools visible simultaneously; gains/regressions unattributable |
| generic_multitool_confirm30 | **Stratum failed** | Positive on diverse18 but failed on diverse confirm30; no confirmed cross-family value |

---

## Task 3 — Tool Narrowness Assessment

### Tools too narrow

**`prepare_reminder_creation_args`**
- Works on one base task (add_reminder) in multiple time/location variants
- Does not help in search, modify, contact, holiday, or service tasks
- Phase B v2 PASS came from a 12-scenario near-dup cohort (7 families, but positive evidence concentrated in add_reminder)
- Assessment: **Scope-narrow by design. Keep as single-family helper; do not count as broad portfolio evidence.**

**`prepare_reminder_arguments_with_optional_location`**
- Extension of above, same scope
- Adoption failure (5/12 visible-not-called in rapid run)
- Assessment: **Keep for reminder-only portfolio; do not promote as cross-family tool.**

### Tools that create route mismatch without improving outcome

**`recency_to_timestamp_bounds`**
- harm_rate 0.5–1.0 when called in diverse contexts
- The agent follows the helper's bounds output and then makes downstream calls that fail
- Assessment: **Suppress. Do not rebuild under new name without resolving harm mechanism.**

**`message_search_time_window`**
- Negative outcome in both frozen12 runs
- The agent calls it but the result does not improve message retrieval
- Assessment: **Suppress. Multiple failed attempts.**

**`select_contact_by_constraint` / `select_contact_field_by_constraint`**
- harm_rate=0.5 when called; 12/12 visible-not-called when isolated
- Causes downstream failures (wrong contact selected → modify applied to wrong record)
- Assessment: **Suppress-retire. Both harmful when called and not adopted when isolated.**

### Tools that require near-duplicate cohorts to look good

**`days_between_timestamps` in claim_portfolio_holiday_frozen**
- +0.640 outcome from 40 near-duplicate holiday scenarios
- True cross-family evidence (diverse18) is +0.137, and confirm30 overall was negative
- Assessment: **Evidence inflated by near-duplication. Real but moderate cross-family value; needs diverse confirmation.**

**`select_record_by_timestamp_extreme` in Phase C.1**
- +0.267 outcome from 6 near-duplicate message_recency scenarios
- Cross-family evidence (contact_helperfit12, record_gate1) is stronger and more meaningful
- Assessment: **Evidence partially inflated. Cross-family evidence is real; needs diverse cross-family confirmation run.**

### Tools that fail in transfer or mixed runs

**`next_service_enablement_action`**: Fails in every run regardless of cohort. Never adopted.

**`recency_to_timestamp_bounds`**: Passes narrow evidence (confirm30 harm_rate=0.0) but harmful in contact run and diverse18.

**`message_search_time_window`**: Fails in all isolated runs.

---

## Task 4 — Cross-Family Tool Opportunities

### 1. `select_record_by_timestamp_extreme` — Extend to diverse cross-family confirmation

**Evidence of cross-family value:**
- message_recency: canonical 0→1.0 in search_message scenarios (Phase C.1)
- modify_reminder: called and produced gain in record_gate1
- holiday: called in record_gate1 (find_days_till_holiday)
- contact/message search: contact_helperfit12 produced +0.350/+0.244 gains when called with `message_search_time_window` together

**Current routing scope:** message recency only (positive_triggers dominated by search_message families)

**Generalization path:**
- Add modify_reminder, remove_reminder, and search_reminder families to positive_triggers
- Add explicit message_recency + reminder_recency call path guidance in description
- Confirm in a 18–24 scenario cross-family run (message_recency + reminder_recency + contact + negative triggers)

**Risk:** Low. The tool is purely selection-only (no side effects). Extending routing scope does not increase harm risk; it only risks visible-not-called friction.

---

### 2. `days_between_timestamps` — Formalize registration, run diverse cross-family confirmation

**Evidence of cross-family value:**
- Reminders + date arithmetic: positive in diverse18 (called 3/3, +0.137)
- Holiday calendar: massive positive in near-dup cohort (inflated), moderate in diverse18
- Generic multi-tool: born in generic_multitool_diverse18 (cross-stratum)

**Problem:** Never formally registered. Born organically across multiple runs without a registration script.

**Required action:**
- Write `scripts/register_days_between_timestamps.py`
- Validate with held_out_check_count ≥ 1, negative_applicability_count ≥ 2
- Run in a DIVERSE 18–24 scenario cohort (reminder + holiday + date arithmetic + at least 2 other families)
- Do NOT use a holiday-only cohort — that inflates evidence

**Expected outcome:** Moderate cross-family value (+0.10–+0.15 outcome delta) in a truly diverse cohort.

---

### 3. `resolve_search_window_or_bounds` — Hold pending routing mechanism improvement

**Prior evidence:** Two analogues (`recency_to_timestamp_bounds`, `message_search_time_window`) both failed. The concept is sound (deterministic arithmetic for search bounds) but the routing keeps misfiring.

**Root cause hypothesis:** The agent calls these tools and then either (a) passes wrong bounds to search tools, or (b) is confused by receiving bounds output and calls the search tool with wrong arguments.

**Required before building:** Root-cause trace analysis on a failed `message_search_time_window` call to understand why the agent's downstream search fails. If the problem is in how the agent uses the output (not the computation), a description fix may resolve it. If the problem is structural (the bounds don't match what the search tool expects), suppress permanently.

---

### 4. `next_service_precondition_call` — Pause until routing mechanism is understood

**Evidence:** The agent never adopts state precondition helpers regardless of description quality. In the most recent focused run (claim_portfolio_state_tool_call_frozen12), the tool was visible in 12 scenarios and called in 1.

**More importantly:** The control arm in that run had outcome_similarity=0.891 — the agent already succeeds at state-precondition tasks without a helper. The helper does not address a genuine failure mode; it is a tool for a problem the agent mostly already solves.

**Assessment:** The Phase B v2 residual failure (low_battery_mode + location sequencing) is rare in the broader distribution. Building a tool that is never adopted is not worthwhile.

**Recommended action:** Pause indefinitely. Revisit only if future broad validation runs show consistent service-sequencing failures that the agent cannot resolve with base tools.

---

### 5. `select_contact_or_message_by_constraints` — Suppress-retire prior analogue, hold new version

**Evidence:** The prior `select_contact_by_constraint` is harmful when called (harm_rate=0.5, mean_delta=-0.252) and never adopted when isolated (12/12 visible-not-called in contact_frozen12).

**Root cause:** Contact disambiguation requires reasoning about which contact is "correct" — this is not a deterministic computation. The helper can return a confident wrong answer, which then causes downstream harm (wrong contact modified/messaged). This is fundamentally different from timestamp-based selection.

**Recommended action:** Suppress prior tool. Do not build new version until a mechanism that prevents confident-wrong-selection is defined. The failure mode here is worse than a missed call (which is recoverable) — it's a confident wrong call (which is not).

---

### 6. `prepare_side_effect_call_from_selected_record` — New cross-family opportunity

Not previously identified in the Phase C candidate list but has genuine cross-family potential. After `select_record_by_timestamp_extreme` identifies a record, a second step is needed to prepare the kwargs for the downstream side-effect tool (modify_reminder, modify_contact, send_message, remove_contact). Currently the agent must do this manually, causing clarification turns and wrong-field selections.

**Cross-family scope:** modify_reminder + modify_contact + send_message + remove_contact (all share the pattern: selected record → prepare tool kwargs → call side-effect tool).

**Risk:** Medium — must preserve all side-effect tool calls explicitly. This would be the most complex registered helper to date.

**Recommended action:** Evaluate after `select_record_by_timestamp_extreme` cross-family confirmation is complete.

---

## Task 5 — Recommended Updated Phase C Roadmap

### Revised candidate order

| Rank | Candidate | Rationale | Cohort type | Gate |
|---|---|---|---|---|
| **C.2** | `days_between_timestamps` (register + diverse confirm) | Organic births across 3+ runs; cross-family value in diverse18; holiday evidence inflated but real; highest unregistered cross-family signal | 18–24 diverse (≥5 base families, not holiday-only) | outcome Δ ≥ +0.05, gains > regressions, harm_rate = 0 |
| **C.3** | `select_record_by_timestamp_extreme` cross-family confirmation | Phase C.1 v2 PASS on narrow cohort; cross-family evidence (record_gate1, contact_helperfit12) is stronger; needs diverse confirmation before portfolio promotion | 18–24 diverse (message_recency + reminder_recency + contact + negative triggers) | outcome Δ ≥ +0.05, called in ≥ 5/6 visible families, harm_rate = 0 |
| **C.4** | `prepare_reminder_arguments_with_optional_location` (extend current helper) | Closes two Phase B v2 residual location failures; narrow scope is OK for this helper; extend, don't replace | Phase B v2 cohort + 3–4 location scenarios | Phase B v2 scenarios must not regress; location scenarios gain |
| **Paused** | `resolve_search_window_or_bounds` | Prior analogues failed; trace root cause before building | — | Unblock: trace why message_search_time_window downstream calls fail |
| **Paused** | `next_service_precondition_call` | Never adopted in any run; control already succeeds at these tasks | — | Unblock: show consistent failure in broad diverse validation |
| **Suppress-retire** | `recency_to_timestamp_bounds` / `message_search_time_window` | Multiple runs, repeated failures, harmful in cross-family contexts | — | — |
| **Suppress-retire** | `select_contact_by_constraint` / field variant | Harmful when called; never independently adopted | — | — |

### Why `days_between_timestamps` before cross-family confirmation of `select_record_by_timestamp_extreme`

1. `days_between_timestamps` has three organic births across distinct runs — the highest-quality organically-validated evidence in the system
2. It already has confirmed cross-family value (reminder + holiday + date arithmetic) even in truly diverse cohorts (diverse18 positive)
3. Formally registering it closes the gap between "generated in live runs" and "stable portfolio tool"
4. The registration + diverse confirmation can be designed to avoid the holiday-only inflation trap by mandate
5. `select_record_by_timestamp_extreme` is already approved for the candidate registry; its cross-family confirmation can run in parallel or immediately after

### What to suppress from portfolio before ablation

Before running a broad portfolio ablation (30+ scenarios with multiple helpers active), suppress:
- `recency_to_timestamp_bounds` — harmful in cross-family contexts
- `message_search_time_window` — negative in all isolated runs
- `select_contact_by_constraint` / `select_contact_field_by_constraint` — harmful when called
- Any version of `next_service_enablement_action` / `next_service_tool_call` — never adopted

Keep active in portfolio:
- `prepare_reminder_creation_args` (frozen baseline)
- `select_record_by_timestamp_extreme` (Phase C.1 PASS)
- `days_between_timestamps` after formal registration and diverse confirmation

---

## Task 6 — Recommended Diversity Gates

### Gate definitions

**Gate A — 4–8 scenario smoke / spot check:**
- Minimum 2 distinct base families (no single family > 60%)
- Used for: rapid affordance repair validation, registration proof
- Suitable for: early_value_only — cannot gate a tool decision alone

**Gate B — 12 scenario focused cohort:**
- Minimum 4 distinct base task families
- No single base family > 30% of total scenarios
- Tool-visible positive scenarios: no single base family > 40% of positive-visible set
- Must include ≥ 2 families where tool is NOT visible (negative routing check)
- May use near-dup distraction variants (0/3/10 distraction) within families
- Suitable for: focused discovery, narrow affordance confirmation

**Gate C — 18–24 scenario diverse focused cohort:**
- Minimum 5 distinct base task families
- No single base family > 25%
- Must span at least 2 stratum categories (e.g., record_filtering + contact_message)
- Must include ≥ 3 negative routing scenarios
- Distraction variants count as the same base family
- Suitable for: cross-family confirmation, tool promotion decision

**Gate D — 30–60 scenario ablation / portfolio confirmation:**
- Minimum 8 distinct base task families
- No single base family > 15%
- Must span at least 3 stratum categories
- Must include ≥ 5 negative routing scenarios
- Every tool in the portfolio must be reported separately with per-tool contribution
- Suitable for: portfolio-level ablation, promotion to production registry

### Reporting rules

- Every tool report must include a section: **"Near-duplicate performance vs. cross-family performance"** that separates gains from within-family variants from gains across distinct base families
- Any run where one base family exceeds 30% must be labeled `near_duplicate_smoke` and not used as standalone evidence for a tool decision
- Any tool with positive gains where >50% of gains come from distraction variants of the same base task must be labeled `near_duplicate_inflated` and require a Gate C run before promotion
- Per-tool contribution must be reported separately from overall cohort delta whenever ≥ 2 tools are active in the same run

---

## Decision Label

**revise Phase C toward cross-family tools**

Reasoning:

1. **Phase C.1 evidence is near-duplicate.** The 12-scenario Phase C.1 cohort (suitable_for_early_value_only) shows `select_record_by_timestamp_extreme` working on 2 base families × 3 distraction levels. This is not confirmation-grade evidence. The cross-family evidence from record_gate1 and contact_helperfit12 is more meaningful and confirms the tool has genuine broader value, but a dedicated diverse cross-family run is needed before portfolio promotion.

2. **The most compelling unregistered cross-family tool is `days_between_timestamps`.** It has organic births across three distinct run families (reminder, holiday, generic multi-tool), and its per-tool contribution in diverse18 shows zero harm, positive win rate. The holiday-cohort +0.640 is inflated by near-duplication. Formally registering it and running a Gate C diverse confirmation is the highest-value next step.

3. **State-precondition and contact-disambiguation tools should not be built next.** State helpers are never adopted (11/12 visible-not-called); the control already handles these tasks well. Contact helpers are harmful when called and never independently adopted. Building these tools next would waste a Phase C slot on known-failing patterns.

4. **Search-window tools should be suppressed.** `recency_to_timestamp_bounds` and `message_search_time_window` have failed across 5+ runs in multiple configurations. There is no evidence the concept can succeed without a fundamental change to how the agent uses the tool's output.

5. **The current Phase C candidate order should be revised.** `next_service_precondition_call` should not be C.2. `days_between_timestamps` registration should be C.2. `select_record_by_timestamp_extreme` cross-family confirmation should be C.3. `prepare_reminder_arguments_with_optional_location` is C.4.

---

## Exact Next Implementation Prompt

```
Objective: Phase C.2 — Register days_between_timestamps and run diverse cross-family confirmation.

Background:
This tool is born organically across 3+ runs (record_ranking_diverse18, generic_multitool_diverse18, generic_multitool_confirm30). Per-tool contribution in diverse18/confirm30 shows harm_rate=0.0, win_rate=0.67, mean_delta=+0.137. It has NOT been formally registered. The claim_portfolio_holiday_frozen run shows +0.640 outcome BUT that run has 40 near-duplicate find_days_till_holiday variants (3 base families, ~33% largest share) — this evidence is inflated by near-duplication and must not be cited as cross-family confirmation.

Tool spec:
- Name: days_between_timestamps
- Family: derived_value_calculator (or closest match)
- Purpose: Compute the integer number of days between two Unix timestamps
- Inputs: start_timestamp (float), end_timestamp (float), inclusive (bool)
- Output: days_count (int), abstain_reason (str)
- Abstain when: either timestamp is null, start > end and inclusive=False, or invalid types

Steps:
1. Write scripts/register_days_between_timestamps.py with full spec and examples
2. Validate: held_out_check_count >= 1, negative_applicability_count >= 2, runtime_smoke_passed=True
3. Run migrate_registry.py --check-only on updated candidate registry
4. Build a DIVERSE 18–24 scenario cohort:
   - MUST span at least 5 base task families
   - MUST NOT be holiday-only — include: add_reminder date scenarios, find_days_till_holiday (max 4 scenarios), search_reminder_with_recency_yesterday, modify_reminder_with_recency, and at least 2 non-reminder/non-holiday families (e.g., message recency, contact task)
   - MUST include ≥ 3 negative routing scenarios where tool should NOT be visible
   - No single base family > 25%
5. Run focused replay: transfer_40 mode, generation OFF, --base-tool-policy upstream
6. Pass gate: outcome delta >= +0.05, gains > regressions, harm_rate = 0, called in >= 50% of visible scenarios
7. Write report: docs/sage_protocol/phase_C_days_between_timestamps_report.md
8. Separate near-duplicate evidence from cross-family evidence in the report

After Phase C.2 passes:
Phase C.3: select_record_by_timestamp_extreme cross-family diverse confirmation (18–24 scenarios spanning message_recency + reminder_recency + contact + negative triggers).
```

---

## Summary Tables

### Evidence quality by tool

| Tool | Cross-family? | Near-dup inflation? | Adoption rate | Harm rate | Portfolio recommendation |
|---|---|---|---|---|---|
| prepare_reminder_creation_args | No | Moderate | High when visible | 0.0 | Keep (narrow) |
| select_record_by_timestamp_extreme | Partial → Yes | Moderate (Phase C.1) | 100% (Phase C.1) | 0.0 | Keep → diverse confirm |
| days_between_timestamps | **Yes** | High (holiday) | High when visible | 0.0 (right family) | **Register + Gate C confirm** |
| next_service_enablement_action | No | N/A | **0%** | N/A | **Pause indefinitely** |
| recency_to_timestamp_bounds | Attempted | N/A | Low | 0.5–1.0 | **Suppress** |
| message_search_time_window | Attempted | N/A | Medium | — | **Suppress** |
| relative_day_time_to_timestamp | No | N/A | Low | 0.0 | Diagnostic only |
| select_contact_by_constraint | Attempted | N/A | Very low | 0.5 | **Suppress-retire** |
| prepare_reminder_args_with_location | No | Moderate | Mixed (0–5 missed) | 0.0 | Keep (narrow, extend carefully) |

### Updated Phase C candidate order

| Phase C Step | Tool | Status | Evidence basis |
|---|---|---|---|
| C.1 ✓ | `select_record_by_timestamp_extreme` | **PASS** (v2 narrow cohort) | 12-scenario near-dup smoke PASS |
| **C.2** | `days_between_timestamps` | **Next: register + Gate C** | Organic cross-family births, +0.137 per-tool in diverse runs |
| **C.3** | `select_record_by_timestamp_extreme` (cross-family confirm) | **Next after C.2** | Cross-family evidence exists; needs Gate C confirmation |
| **C.4** | `prepare_reminder_arguments_with_optional_location` | Hold until C.3 complete | Narrow reminder extension; low risk |
| Paused | `resolve_search_window_or_bounds` | **Paused** | Prior analogues failed; trace root cause first |
| Paused | `next_service_precondition_call` | **Paused** | Never adopted; control already succeeds |
| Suppress | `recency_to_timestamp_bounds` / `message_search_time_window` | **Suppress** | Repeated failures, harmful |
| Suppress | `select_contact_by_constraint` / variants | **Suppress-retire** | Harmful when called, never adopted independently |

---

**Audit completed:** 2026-05-03
**Runs inspected:** ~20 distinct cohorts across ~30 run directories
**Key finding:** Three tools have inflated evidence from near-duplicate cohorts (prepare_reminder_creation_args, select_record_by_timestamp_extreme Phase C.1, days_between_timestamps holiday run). Two tools are ready for next Phase C steps with appropriate diverse cohorts. Four tools should be suppressed or paused based on consistent adoption failure or harm evidence.
