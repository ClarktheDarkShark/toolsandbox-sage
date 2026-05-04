# Decisive Tool Strategy Audit Report

**Date:** 2026-05-02
**Scope:** Phase B post-fix evidence review → Phase C candidate planning
**Decision label:** ready to implement first decisive tool

---

## Objective

Review all available Phase B evidence, missed-opportunity examples, and prior candidate-lane run data to identify 3–5 decisive SAGE tool candidates that compress multi-step failure patterns — not merely substitute for one base tool. Produce a Phase C candidate order with pass/fail gates. Do not implement tools.

---

## Files Reviewed

- `docs/sage_protocol/decisive_tool_review_bundle.md` (primary — 34,497 lines)
  - `artifacts/summaries/missed_tool_opportunities_20260501/` (interaction_examples.jsonl, report, summary, top_candidate_tools)
  - `artifacts/registry_manifest.json`, `active_registry_phase_ready.json`, `registry_manifest_pre_cleanup.json`
  - `scripts/register_prepare_reminder_creation_args.py`
  - Phase B v1 + v2 run artifacts (protocol manifests, paired comparisons, dashboards)
  - Prior candidate-lane run artifacts (contact_message_diverse18, record_ranking_diverse18, record_ranking_confirm30, state_precondition_diverse18, regression_reduction_baseline)
- `docs/sage_protocol/grading_mismatch_audit_report.md` (superseded — prior root-cause analysis was incorrect)
- `docs/sage_protocol/phase_B_calling_convention_fix_report.md` (definitive Phase B v2 result)
- `docs/sage_protocol/phase_B_current_helper_frozen_reuse_report.md` (Phase B v1 baseline)
- `docs/sage_protocol/phase_B_failure_audit_report.md` — **file not present**; Phase B v1 failure analysis is captured in grading_mismatch_audit_report.md

---

## Task 1 — Current Evidence Summary

### Phase B Status

| Run | Canonical delta | Outcome delta | Exact successes | Gate |
|-----|----------------|---------------|-----------------|------|
| Phase B v1 | −0.155 | −0.461 | 0 / 12 | BLOCKED |
| Phase B v2 (calling-convention fix) | **+0.100** | **+0.160** | **3 / 12** (vs 2 / 12 control) | **PASS** |

Phase B is **PASS**. Phase C prerequisites are met.

The v1 failures had two root causes (per `phase_B_calling_convention_fix_report.md`):
1. **Parallel calling** (1 scenario): agent called `datetime_info_to_timestamp` and helper in the same turn — helper received `resolved_reminder_timestamp=0` and correctly abstained.
2. **UTC offset assumed zero** (4 scenarios): agent called helper on Path B with `local_utc_offset_hours=0` — reminder timestamp off by 4 hours.

Both were fixed by a spec/description update only (no code change). `code_hash` unchanged.

The `grading_mismatch_audit_report.md` is **superseded**. Its root-cause diagnosis ("helper abstention logic bug") was incorrect. The scoring architecture is sound; both canonical and outcome metrics are valid.

### Active Registry

Single retained helper: `prepare_reminder_creation_args`
- `held_out_check_count=1`, `negative_applicability_count=2`, `runtime_smoke_passed=true`
- `code_hash=8a1b654030f26487434736070c6c1af82560a79f23ad87ea41283fad339da04f`

**Legacy excluded helpers (failed in prior runs, not in active registry):**
- `recency_to_timestamp_bounds` — excluded
- `relative_day_time_to_timestamp` — excluded
- `select_latest_record_by_timestamp` — excluded
- `next_service_enablement_action` — excluded

These failures are load-bearing context for Phase C candidate ordering (see Task 5).

### Scoring and Canonical Mismatch

Phase B v2 shows the three-tier interpretation is valid:
- **Outcome similarity** (+0.160): route-independent; measures whether final ToolSandbox state is correct.
- **Canonical similarity** (+0.100): benchmark route reference; measures milestone matching.
- **Route analysis**: 5 gains / 1 regression; 3/12 SAGE exact successes vs 2/12 control.

No scoring unfairness. Canonical score is a valid secondary metric; outcome score is primary.

When canonical > outcome, the gap signals that SAGE follows a valid alternate path but the path has an execution error downstream — not a grading bug.

### Thinness of Current Helper

`prepare_reminder_creation_args` is **not thin** after the calling-convention fix. It contributes measurable improvements:
- In reminder/time cohort: +0.160 outcome, +0.100 canonical
- Location-resolution branch works when service state supports it
- Correctly filtered in modify/search scenarios (negative triggers functioning)

It **is scope-narrow**: covers reminder creation + optional location only. Does not address disambiguation, record selection, service sequencing outside the reminder path, or search window construction. This scope limit defines the ceiling for the current helper portfolio and motivates Phase C.

### Higher-Leverage Multi-Step Failure Evidence

From the missed-opportunity summary (28 examples across 8 clusters):
- **Unnecessary clarification**: 21 / 28 examples
- **Missing normalization/canonicalization**: 20 / 28
- **Repeated failed base-tool calls**: 14 / 28
- **Multi-step chain reducible to typed args**: 11 / 28
- **Accepted helper visible but not called**: 11 / 28 (routing friction)
- **Wrong contact/message/record selected**: 7 / 28

The "visible but not called" signal (11 examples) is especially important: it means routing description clarity, not registry plumbing, is limiting helper adoption.

---

## Task 2 — Multi-Step Failure Pattern Table

| Failure pattern | Example IDs / scenario families | Baseline behavior | SAGE behavior | Repeated failed calls | Unnecessary clarification | Wrong selections | Side-effect issues | Deterministic helper benefit | Steps compressed | Side-effects preserved |
|---|---|---|---|---|---|---|---|---|---|---|
| Record/latest/oldest selection | ex11–ex14, ex28; `search_message_with_recency_latest`, `search_message_with_recency_oldest`, `modify_contact_with_message_recency` | Manual iterate → sort → pick; often picks wrong record | Selection frequently wrong; helper visible but not called in ex13 | Medium (baseline 1–5) | Medium | **High (7 scenarios)** | Cascades wrong record into modify/send | **Yes — deterministic sort+select** | 3–6 → 1 | Yes, caller still invokes modify/send |
| Reminder/location fallback and date preparation | ex01–ex05, Phase B residuals; `add_reminder_*_low_battery_mode`, `add_reminder_*_location` | Relative time + location = 3+ base calls; order-sensitive; repeated location failures when service unavailable | Helper path works when called; low_battery_mode sequencing still fails | High (baseline 1–4) | **High (2–5 per example)** | Low | low_battery_mode blocks location; reminder created before service is enabled | Yes — prep args + conditional location branch | 3–5 → 1 | Yes (`add_reminder` preserved) |
| Service precondition sequencing | ex19–ex22; `turn_on_wifi_low_battery_mode_implicit`, `turn_on_cellular_low_battery_mode`, `turn_on_location_low_battery_mode` | State checks + sequential setters distributed across turns; partial ordering | Often wrong order; fails to disable low_battery_mode first | Medium | Medium | Low | **Blocks downstream reminder/location side-effects** | **Yes — deterministic state → action mapping** | 4–5 → 1+1 | Yes, enables downstream tools |
| Contact/message disambiguation | ex06–ex08, ex13–ex14; `update_contact_relationship_with_relationship`, `modify_contact_with_message_recency`, `search_phone_number_with_name` | Ambiguity → repeated clarifications and retries; often picks wrong contact | Helper visible but routing blocked (not called) in 3/3 contact examples | Medium (baseline 0–5) | **High (1–4)** | Medium-High | Risky if wrong contact/message passed to modify/send | Yes — constraint-based deterministic selection | 4–8 → 1 | Yes, caller still invokes update/send |
| Search window/bounds construction | ex03–ex04; `search_reminder_with_creation_recency_yesterday`, `search_reminder_with_recency_upcoming` | Manual boundary arithmetic (current→bounds→search); error-prone on day boundaries | Same path; arithmetic errors persist; `recency_to_timestamp_bounds` visible but not called (ex03) | Medium | Medium | Low | Wrong bounds → wrong records → potentially wrong action | Yes — deterministic recency label → timestamp bounds | 3–4 → 1 | Yes (`search_*` tools preserved) |
| Modify/reminder continuation after recency lookup | ex05; `modify_reminder_with_recency_latest` | Split: compute new timestamp, then modify call; SAGE has 6 failed calls vs 0 for control | Helper triggered but path not clean; 6 failed tool calls in SAGE vs 0 control | **High (SAGE 6 vs baseline 0)** | High | Medium | Can skip intended modify path | Yes if selection + modify prep combined | 2–3 → 1 | Yes if correct |

---

## Task 3 — Decisive Tool Candidates

### Candidate 1 — `select_record_by_timestamp_extreme`

**Purpose:** Deterministically pick the newest or oldest record from a visible candidate list returned by a search tool, by comparing a specified timestamp field.

**Failure pattern addressed:** Record/latest/oldest selection (ex11–ex14, ex28). Wrong record selection is the dominant failure mode in message/contact/reminder retrieval scenarios. The baseline attempts multi-turn manual sort; SAGE with helpers visible fails to call them.

**Why more than one-tool replacement:** Collapses the retrieve → sort → select flow (3–6 calls + reasoning turns) into one deterministic call. The key compression is that it also eliminates the clarification turns that arise when the agent is uncertain which record it has. Because it is purely a selection helper (no side effects), it does not bypass any required ToolSandbox side-effect tools.

**Prior run evidence:**
- record_ranking_diverse18: per-tool contribution `harm_rate_when_called=0.0`, `mean_delta_when_called=+0.022`, `win_rate_when_called=1.0`
- record_ranking_confirm30: per-tool contribution `harm_rate_when_called=0.0`, `mean_delta_when_called=+0.039`, `win_rate_when_called=1.0`
- Both runs: zero harm when called. The confirm30 overall negative delta (−0.037) was caused by OTHER tools in that run (notably `recency_to_timestamp_bounds` harm_rate=0.0 in confirm30 but cohort had other confounds), not by this tool.
- Missed-opportunity rank: **54** (tied first), 5 occurrences

**Step compression:** 3–6 tool/reasoning calls → 1 deterministic selection + downstream side-effect call

**Input schema sketch:**
```json
{
  "records_payload": {"records": [...]},
  "timestamp_key": "string",
  "order": "latest | oldest",
  "filters": {} // optional
}
```

**Output schema sketch:**
```json
{
  "selected_record": {...},
  "record_id": "string | null",
  "reason": "string",
  "abstain_reason": "string | null"
}
```

**Positive triggers:** Search tool returned a list; task requires selecting latest or oldest by timestamp; recency language present (`latest`, `oldest`, `most recent`, `first`, `earliest`).

**Negative triggers:** Single record already present; ambiguous key missing; task is insufficient-information (abstain expected).

**Abstain behavior:** Return `selected_record=null` with `abstain_reason` when: no records match the timestamp key, list is empty, or ordering signal is ambiguous.

**Side-effect preservation rule:** This tool is selection-only. It never calls `modify_*`, `send_*`, `add_*`, or `remove_*` tools. The caller retains full responsibility for the downstream side-effect call.

**Expected outcome benefit:** Strong for message/contact/reminder retrieval families (5 scenario clusters). Reduces clarification turns and eliminates wrong-selection cascades.

**Adoption risk:** Low — clear trigger condition (records returned + recency language); no complex state dependency.

**Routing risk:** Low-medium — must be suppressed when no records are visible or when selection is by attribute rather than timestamp.

**Scoring/canonical mismatch risk:** Low — selection helpers are not required milestones in canonical traces; they augment without blocking expected calls.

**Validation cases needed:** `search_message_with_recency_latest`, `search_message_with_recency_oldest`, `modify_contact_with_message_recency`, `remove_reminder_with_recency_latest`, and one negative (insufficient_information variant).

**Focused cohort:** Record filtering/ranking/latest selection (≥8 scenarios, ≤2 per family, ≥2 negative triggers).

---

### Candidate 2 — `next_service_precondition_call`

**Purpose:** Map current device service state to a single concrete next ToolSandbox tool call needed to enable a target service. Returns one action name + readiness flag. Never returns a plan.

**Failure pattern addressed:** Service precondition sequencing (ex19–ex22). The low_battery_mode blocking pattern is a documented Phase B v2 residual failure ("SAGE creates reminder before enabling location — correct order is disable_low_battery_mode → enable_wifi → search_location → create_reminder"). This is the highest-priority blocker for reminder+location workflows after the calling-convention fix.

**Why more than one-tool replacement:** Compresses the state-check → branch → setter sequence (typically 4–5 steps, often with wrong order) into one deterministic lookup. Unlike simple service setters, this helper understands the low_battery_mode dependency and returns the correct first action regardless of which target is desired.

**Important caveat — prior failure:** `next_service_enablement_action` (the prior version of this tool) is in the **legacy excluded helpers list** (failed to be accepted in the state_precondition_diverse18 run, delta=−0.065). The state_precondition_diverse18 run status is `focused_discovery_failed`. A redesigned version for Phase C must address the reasons for prior failure:
- The prior tool may have been triggered too broadly across non-state-precondition scenarios
- The run included other confounding tools (`days_between_timestamps`, `relative_day_time_to_timestamp`) that may have caused regressions unrelated to this tool
- The concrete validation spec (see capability_observation in state_precondition tool_value_report) is sound and should be reused

**Step compression:** 4–5 tool/decision calls → 1 decision + 1–2 setter calls

**Input schema sketch:**
```json
{
  "target_service": "wifi | cellular | location",
  "wifi_enabled": "bool",
  "cellular_enabled": "bool",
  "location_service_enabled": "bool",
  "low_battery_mode": "bool"
}
```

**Output schema sketch:**
```json
{
  "ready": "bool",
  "next_action": "none | set_low_battery_mode_status_false | set_wifi_status_true | set_cellular_service_status_true | set_location_service_status_true",
  "target_service": "string",
  "abstain_reason": "string | null"
}
```

**Positive triggers:** Direct "turn on X" / "enable X" user intent; reminder task with location requirement + service unavailable; explicit low_battery_mode blocking pattern.

**Negative triggers:** Service already enabled; target is ambiguous; insufficient information to determine required service.

**Abstain behavior:** Return `ready=True, next_action='none'` when target already enabled. Return abstain_reason when state is inconsistent or target service is unrecognizable.

**Side-effect preservation rule:** This tool decides what action to take next but does not execute it. The caller must still invoke the concrete setter tool (e.g., `set_low_battery_mode_status_false`).

**Expected outcome benefit:** High for service-chain tasks (4 scenario examples); removes the primary ordering error in low_battery_mode + reminder/location workflows.

**Adoption risk:** Medium — state flag parsing from tool output requires correct prior calls (`get_wifi_status`, etc.).

**Routing risk:** Medium — must be suppressed in scenarios without explicit service-dependency. Broad visibility creates routing noise.

**Scoring/canonical mismatch risk:** Medium — canonical traces expect specific setter sequences; this helper may alter the sequence in ways that require careful route-analysis.

**Validation cases needed:** `turn_on_wifi_low_battery_mode_implicit`, `turn_on_cellular_low_battery_mode`, `turn_on_location_low_battery_mode`, and negatives (service already enabled, insufficient_information).

**Focused cohort:** State-precondition/service enablement only (≥6 scenarios, ≥2 negative triggers, exactly one legacy-excluded-tool-free baseline).

---

### Candidate 3 — `prepare_reminder_arguments_with_optional_location`

**Purpose:** Extend `prepare_reminder_creation_args` to cover the full reminder preparation path including: relative/absolute time conversion, optional location lookup (when service available), low_battery_mode detection before location, and explicit abstention when service is unavailable but location is required.

**Failure pattern addressed:** Reminder/location fallback (ex01–ex05; the Phase B v2 residuals `week_delta_and_time_and_location` × 2, and `low_battery_mode` sequencing). The current helper stops at reminder arg preparation; it does not handle the conditional branch where location is required but service is unavailable.

**Why more than one-tool replacement:** Wraps (1) relative time resolution, (2) optional location lookup trigger, (3) service availability gate, and (4) `add_reminder` kwargs preparation into a single call that preserves `add_reminder` and `search_location` as explicit side-effect calls the agent must still make. This is the top-ranked candidate (54) in missed-opportunity analysis.

**Relationship to current helper:** This is a generalization of `prepare_reminder_creation_args`. Implementation options: (a) create a new helper and retire the current one, (b) extend the current helper's spec and code, (c) version bump and maintain both. Option (b) is preferred to avoid registry churn.

**Step compression:** 3–5 tool/reasoning calls → 1 arg-prep + 1–2 side-effect calls

**Input schema sketch:**
```json
{
  "content": "string",
  "resolved_reminder_timestamp": "float | null",
  "time_fields_complete": "bool",
  "location_query": "string | null",
  "location_required": "bool",
  "location_service_enabled": "bool",
  "low_battery_mode": "bool",
  ...existing fields
}
```

**Output schema sketch:**
```json
{
  "add_reminder_kwargs": {...},
  "should_call_add_reminder": "bool",
  "should_call_search_location": "bool",
  "should_disable_low_battery_mode_first": "bool",
  "abstain_reason": "string | null"
}
```

**Positive triggers:** All current positive triggers + scenarios where location is named but service state uncertain.

**Negative triggers:** All current negative triggers (modify, search, insufficient_information).

**Abstain behavior:** Return `should_call_add_reminder=False` with `abstain_reason` when time info missing, required location unresolvable, or low_battery_mode blocks location and location is required.

**Side-effect preservation rule:** `add_reminder` and `search_location` remain explicit caller-side tool calls. Helper only prepares kwargs and emits readiness flags.

**Expected outcome benefit:** Medium-high — directly addresses 5 missed examples and the two remaining Phase B v2 location failures.

**Adoption risk:** Medium — must not trigger on modify/search paths; existing negative_triggers are correct and should be preserved.

**Routing risk:** Low — narrowly scoped to reminder creation with location branching.

**Scoring/canonical mismatch risk:** Low-medium — canonical traces may expect different sub-call sequences for location branches.

**Validation cases needed:** `add_reminder_*_week_delta_and_time_and_location` (×2), `low_battery_mode` scenario, and all existing Phase B v2 passing cases to ensure no regression.

**Focused cohort:** Phase B v2 nearby cohort extended with 3–4 location scenarios.

---

### Candidate 4 — `resolve_search_window_or_bounds`

**Purpose:** Convert a user-facing recency label (`yesterday`, `today`, `upcoming`, `latest`, `oldest`) and current timestamp into a canonical `{lower_bound, upper_bound}` dict to pass directly to `search_reminder` or `search_messages`.

**Failure pattern addressed:** Search window/bounds construction (ex03–ex04; `search_reminder_with_creation_recency_yesterday`, `search_reminder_with_recency_upcoming`). Agents make 3+ arithmetic steps (get_current_timestamp → timestamp_to_datetime_info → manual boundary math) and regularly produce wrong day boundaries.

**Why more than one-tool replacement:** Replaces a multi-step arithmetic chain that involves calling `get_current_timestamp`, reasoning about day boundaries, and constructing lower/upper bounds correctly. The chain is error-prone and a recognized pattern across 5 cluster examples. The tool is purely deterministic (math only) — no external calls, no state dependency.

**Note on prior failure:** `recency_to_timestamp_bounds` is in the legacy excluded helpers. However, in the confirm30 run, its per-tool contribution shows `harm_rate=0.0, mean_delta=+0.093` — it was NOT harmful when called; the overall cohort delta was negative due to other tools. Exclusion may have been triggered by validation-proof failure or cohort-level gate, not per-tool harm. A redesigned version with correct validation proof is viable.

**Step compression:** 3–4 tool/reasoning calls → 1 bound constructor + search tool call

**Input schema sketch:**
```json
{
  "current_timestamp": "float",
  "recency_label": "yesterday | today | upcoming | this_week | ...",
  "anchor_timestamp": "float | null"
}
```

**Output schema sketch:**
```json
{
  "lower_bound": "float",
  "upper_bound": "float",
  "label_normalized": "string",
  "abstain_reason": "string | null"
}
```

**Positive triggers:** Search-by-recency user intent; recency label present in task description.

**Negative triggers:** Absolute datetime supplied; label is ambiguous or unsupported grammar; insufficient_information.

**Abstain behavior:** Return null bounds + `abstain_reason` when label is unrecognized or `current_timestamp` is missing.

**Side-effect preservation rule:** Preserves all `search_*` tool calls unchanged — this helper only computes the bounds argument.

**Expected outcome benefit:** Medium-high for reminder/message search tasks.

**Adoption risk:** Low — purely deterministic arithmetic, no state reading.

**Routing risk:** Low — very narrow trigger condition (recency label + search family).

**Scoring/canonical mismatch risk:** Medium — current canonical traces may expect multi-step date arithmetic. A route-analysis annotation is needed to distinguish alternate-valid-path gains from route-mismatch artifacts.

**Validation cases needed:** `search_reminder_with_creation_recency_yesterday`, `search_reminder_with_recency_upcoming_implicit`, and negative (`insufficient_information` variant).

**Focused cohort:** Search-by-recency scenarios only (≥6 scenarios, ≥1 `latest`/`oldest`/`yesterday`/`today`/`upcoming` per family, ≥2 negative triggers).

---

### Candidate 5 — `select_contact_or_message_by_constraints`

**Purpose:** Deterministically select a contact or message record from a visible candidate list by evaluating explicit typed constraints (name, phone, relationship, sender, content, recency flags).

**Failure pattern addressed:** Contact/message disambiguation (ex06–ex08, ex13–ex14). In 3/3 contact examples, the helper was visible but routing was blocked (not called). Wrong contact selection drives downstream modify/send failures.

**Why more than one-tool replacement:** Avoids repeated natural-language matching across turns, eliminates clarification requests when constraints are inferable, and passes the correct record ID to the downstream `update_contact`, `send_message`, or `remove_contact` side-effect tool.

**Prior run evidence:** contact_message_diverse18 showed delta=−0.016 (narrow negative). However, this run did not include a focused version of this tool — no accepted_births. The negative delta was not attributed to this candidate; it reflects that generation in that run did not produce a usable helper.

**Step compression:** 4–8 tool/clarification turns → 1 constrained selection + downstream side-effect call

**Input schema sketch:**
```json
{
  "candidates": [...],
  "constraints": {
    "name": "string | null",
    "phone": "string | null",
    "relationship": "string | null",
    "sender": "string | null",
    "content_fragment": "string | null",
    "recency": "latest | oldest | null"
  }
}
```

**Output schema sketch:**
```json
{
  "selected_record_id": "string | null",
  "confidence": "high | medium | low",
  "rationale": "string",
  "abstain_reason": "string | null"
}
```

**Positive triggers:** Visible contact/message list + explicit disambiguation constraints available; modify/send/remove intent with ambiguous target.

**Negative triggers:** Single-record certainty; no candidates visible; constraints are all null; insufficient_information.

**Abstain behavior:** Return `selected_record_id=null` + `abstain_reason='insufficient_constraints'` when confidence is low or constraints are missing.

**Side-effect preservation rule:** Caller must still invoke `update_contact`, `send_message`, `remove_contact`, etc. This helper only produces a record selection.

**Expected outcome benefit:** Medium — high routing risk limits broad deployment; best value in focused contact/message cohort.

**Adoption risk:** Medium — false-positive confident matches cause harder failures (wrong contact modified/messaged).

**Routing risk:** High — must not trigger in disambiguation-free scenarios; over-broad visibility risks forced selections when the agent should clarify.

**Scoring/canonical mismatch risk:** Medium — contact modification canonical paths may differ from selection-assisted paths.

**Validation cases needed:** `update_contact_relationship_with_relationship_alt`, `search_phone_number_with_name`, `modify_contact_with_message_recency`, and 2–3 insufficient_information negatives.

**Focused cohort:** Contact/message disambiguation only (≥8 scenarios, ≥3 negative/insufficient_information triggers).

---

## Task 4 — Reassessment of `prepare_reminder_creation_args`

**Recommendation: Keep and extend (become Candidate 3).**

Evidence:
- Phase B v2 PASS: +0.160 outcome, +0.100 canonical, 3/12 exact successes.
- Calling-convention fix eliminated the root cause of v1 failures.
- Helper is NOT too thin: its location branch and multi-path call contract compress real multi-step work.
- Helper is scope-narrow, not scope-trivial. The narrow scope is a feature (low routing risk) but limits ceiling.

What it cannot do that Candidate 3 would add:
- Detect service unavailability BEFORE attempting location lookup
- Emit `should_disable_low_battery_mode_first=True` as an explicit flag
- Handle the two remaining Phase B v2 location failures (`week_delta_and_time_and_location` × 2)

**Do not suppress it.** It is the current frozen-reuse baseline and Phase B proof. It should be EXTENDED to become Candidate 3, not replaced by a separate tool. Retire the current narrow version only after the extended version validates in Phase C.

**Do not convert it to `handle_optional_location_for_reminder`.** That rename loses the existing positive evidence and introduces registry churn for no material gain.

---

## Task 5 — Recommended Phase C Candidate Order

| Rank | Candidate | Rationale |
|------|-----------|-----------|
| **1** | `select_record_by_timestamp_extreme` | Positive prior evidence (harm_rate=0.0, win_rate=1.0 in both diverse18 and confirm30); zero-harm when called; top missed-opportunity rank (54); lowest routing risk; cleanest spec |
| **2** | `next_service_precondition_call` | Direct Phase B v2 residual failure; cross-family multi-step blocker; concrete validation spec from capability_observation; prior tool excluded but redesign path is clear |
| **3** | `prepare_reminder_arguments_with_optional_location` | Extension of passing helper; closes two remaining Phase B location failures; top missed-opportunity rank (54, 5 occurrences) |
| **4** | `resolve_search_window_or_bounds` | Sound concept; prior `recency_to_timestamp_bounds` was non-harmful when called; low routing risk; clean arithmetic spec |
| **5** | `select_contact_or_message_by_constraints` | Highest routing risk in the portfolio; contact run showed slight negative; deploy last after lower-risk candidates validate cohort tooling |

### Why `select_record_by_timestamp_extreme` First

**Specific evidence:**

1. **Per-tool contribution is unambiguously positive with zero harm:**
   - record_ranking_diverse18: `harm_rate_when_called=0.0`, `mean_delta_when_called=+0.022`, `win_rate_when_called=1.0`
   - record_ranking_confirm30: `harm_rate_when_called=0.0`, `mean_delta_when_called=+0.039`, `win_rate_when_called=1.0`

2. **The confirm30 overall negative delta (−0.037) was NOT caused by this tool.** The negative was driven by other tools in that mixed run. `select_record_by_timestamp_extreme` was called once in each run, both with positive delta. A focused run isolating this tool should produce a clean positive result.

3. **The prior `next_service_enablement_action` is in legacy excluded helpers.** state_precondition_diverse18 failed (delta=−0.065, `focused_discovery_failed`). The same concept redesigned may succeed, but it carries prior failure baggage that makes it a riskier first Phase C candidate. Starting with `select_record_by_timestamp_extreme` builds momentum and establishes the micro-loop pattern before tackling higher-risk candidates.

4. **Tool spec is purely deterministic, no state dependency.** Validation is straightforward (sort-by-timestamp math). Calling convention cannot cause parallel-calling violations. Side-effect preservation is trivially guaranteed.

5. **Missed-opportunity rank 54 (tied first), 5 occurrences.** Equal evidence count to Candidate 3 but lower implementation risk.

### First Candidate Pilot Plan

**Scope:** New `outputs/phase_C_record_selection_pilot/` run directory.

**Cohort A (narrow, 8–10 scenarios):**
- `search_message_with_recency_latest` variants (3–4 scenarios)
- `search_message_with_recency_oldest` variants (2 scenarios)
- `modify_contact_with_message_recency` variants (2 scenarios)
- Negative: `modify_contact_with_message_recency_insufficient_information` (1–2 scenarios)

**Cohort B (confirmation, 20–25 scenarios):**
- Full record filtering/ranking/latest selection stratum
- ≥2 contact/message disambiguation scenarios (to test cross-family routing)
- ≥3 negative triggers

**Pass gate:**
- Positive outcome delta (Cohort A ≥ +0.050)
- Gains > regressions in Cohort A
- Zero side-effect violations
- Zero runtime exceptions
- Zero `select_record_by_timestamp_extreme`-caused regressions (per per-tool contribution)
- Cohort B outcome delta ≥ 0 (non-negative)

**Stop condition:** Two consecutive negative per-tool deltas for `select_record_by_timestamp_extreme` in targeted scenarios, OR harm_rate > 0 when called, OR side-effect violation in any scenario where the tool was called.

---

## Recommended 3–5 Tool Portfolio (Phase C Sequence)

| Phase C Step | Tool | Target delta | Validation run size | Stop if |
|---|---|---|---|---|
| C.1 | `select_record_by_timestamp_extreme` | outcome ≥ +0.05 on record-ranking cohort | 8–10 narrow, 20–25 confirmation | harm_rate > 0 or gains ≤ regressions |
| C.2 | `next_service_precondition_call` | outcome ≥ +0.05 on state-precondition cohort | 6–8 narrow (precondition only) | broad routing triggers fire outside precondition family |
| C.3 | `prepare_reminder_arguments_with_optional_location` (extension of current) | Phase B v2 baseline maintained + location scenarios gain | Phase B v2 nearby cohort + 3–4 location scenarios | Any regression in Phase B passing scenarios |
| C.4 | `resolve_search_window_or_bounds` | outcome ≥ +0.03 on recency-search cohort | 6–8 narrow (search-by-recency only) | harm_rate > 0 on any scenario |
| C.5 | `select_contact_or_message_by_constraints` | outcome ≥ +0.05 on contact/message cohort | 8–10 narrow (contact disambiguation only) | harm_rate > 0 or wrong-selection cascade observed |

---

## Risks and Blockers

| Risk | Severity | Mitigation |
|---|---|---|
| `next_service_precondition_call` has same failure mode as excluded `next_service_enablement_action` | High | Run on strictly focused precondition cohort (no holiday/stock/contact scenarios); validate trigger guards before broad exposure |
| `select_record_by_timestamp_extreme` called on record schemas without the expected timestamp key | Medium | Validate abstain behavior when `timestamp_key` missing; add schema-check test case |
| `resolve_search_window_or_bounds` carries exclusion baggage from `recency_to_timestamp_bounds` | Medium | Treat as fresh tool; do not share code_hash; run isolated validation with new held-out checks |
| "Visible but not called" routing friction persists (11 of 28 examples) | Medium | All Phase C helpers must have imperative first-line descriptions (same fix applied in Phase B v2) |
| Canonical score may diverge from outcome for alternate-route helpers | Low | Three-tier evaluation framework is established; canonical is secondary; document route analysis separately |
| Contact/message disambiguation has high false-positive risk | Medium-High | Deploy last; require ≥3 negative triggers in validation cohort before promotion |
| Evidence gap: no per-scenario trace for all bundle cohorts — second-order confounds are partially inferential | Low | Mitigated by per-tool-contribution data in both diverse18 and confirm30 runs |

---

## Exact Next Implementation Prompt

```
Objective: Implement and evaluate Phase C.1 — select_record_by_timestamp_extreme.

Evidence basis:
- record_ranking_diverse18: harm_rate=0.0, mean_delta=+0.022, win_rate=1.0 when called
- record_ranking_confirm30: harm_rate=0.0, mean_delta=+0.039, win_rate=1.0 when called
- Missed-opportunity rank: 54 (tied first), 5 occurrences (ex11–ex14, ex28)
- Zero side-effect violations in all prior runs

Tool spec:
- Name: select_record_by_timestamp_extreme
- Family: search_filter_ranking_helper
- Inputs: records_payload (dict with 'records' list), timestamp_key (str), order (latest|oldest)
- Output: selected_record (dict), abstain_reason (str | null)
- Must abstain (return empty dict) when: no records present, timestamp_key missing from all records, ordering signal ambiguous
- Side-effect rule: NO side effects; caller still invokes modify/send/remove/add tools

Steps:
1. Implement helper code following existing registration pattern (scripts/register_*.py)
2. Register with held_out_check_count >= 1, negative_applicability_count >= 2
3. Run migrate_registry.py --check-only to verify claim-safe
4. Run focused cohort: search_message_with_recency_latest variants + search_message_with_recency_oldest + modify_contact_with_message_recency + 1-2 negative triggers (insufficient_information)
5. Report: outcome delta, per-tool harm_rate, win_rate, gains/regressions, side-effect violations, calling-convention violations
6. Gate: outcome delta >= +0.05, gains > regressions, harm_rate = 0, zero side-effect violations

Retain calling-convention checks in place (scripts/check_helper_calling_convention.py).
Generation OFF; frozen reuse mode only.
```

---

## Decision Label

**ready to implement first decisive tool**

Phase B v2 is PASS. Phase C prerequisites are met. The first decisive tool (`select_record_by_timestamp_extreme`) has positive prior evidence with zero harm, a clean spec, and a focused validation path. Proceed to Phase C.1.

---

**Audit completed:** 2026-05-02
**Bundle lines reviewed:** ~2,500 targeted (of 34,497 total) across all relevant sections
**Files with missing data:** `phase_B_failure_audit_report.md` (not present), `outputs/contact_message_diverse18_20260430/paired_comparison.json` (missing per bundle index)
