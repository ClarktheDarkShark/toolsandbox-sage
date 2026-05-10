# Broad500 Top Tool Combo Gap Assessment

Experimental evidence only. This document is not protected final claim evidence and does not modify protected best3, locked formal evidence, V2.6 evidence, or final-package claim artifacts.

## Run Name

`Broad500 Top Tool Combo: Full Timestamp No-Field Pack`

## Run Summary

- Run: `outputs/gap_closure_lab/recombination_adoption/top_tool_combo/full_timestamp_no_field_broad500/full_benchmark_20260509_182714`
- Registry: `artifacts/registry_experiments/gap_closure_lab/recombination_adoption/top_tools_full_timestamp_no_field_extractor_pack`
- Registry SHA-256: `365fa28ecd476c1b3b4cd53b16b5d61b233bd3744e91d5a5d0c060c9a10f5e2b`
- Split manifest: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json` locally; compressed archive committed at `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json.gz`
- Machine-readable gap assessment: `artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad500_gap_assessment.json`
- Assessment SHA-256: `d64ebfd3430aa7e88480adc8a78df1e7721edd1d0c3853c77111e1034c7353c2`
- Task Focus dashboard: `http://127.0.0.1:62061/outputs/gap_closure_lab/recombination_adoption/top_tool_combo/full_timestamp_no_field_broad500/full_benchmark_20260509_182714/dashboard/task_focus.html`

Result:

- Sample: 500 broad experimental tasks, 54 base families, largest family share 0.024
- Outcome: control `0.5947`, SAGE `0.7353`, delta `+0.1406`
- Canonical/reference: control `0.6628`, SAGE `0.7224`, delta `+0.0596`
- Exact success delta: `+42`
- Outcome gains/regressions: `152 / 74`
- Runtime exceptions: `0`
- Protocol gate: pass
- Control cache: `45` cached / `455` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Candidate/SAGE cache: task-level cache off; OpenAI response cache disabled

The cohort warning was `low_expected_helper_fit_share`, which is the key interpretation point: the retained recency/date/contact tools worked where they fit, but the broad split contains many task families outside their current support surface.

## Comparison With 500 Best3

The documented current-code best3 500 run remains the stronger broad protected comparator by run-vs-control lift:

- Best3 500 report: `docs/sage_protocol/v2_6_current_code_500_matched_report.md`
- Best3 run root: `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553`
- Best3 manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Best3 run-vs-control outcome delta: `+0.1617`
- This broad top-tool-combo run-vs-control outcome delta: `+0.1406`

This run has a higher absolute candidate outcome (`0.7353`) than the documented best3 candidate outcome (`0.6590`), but the manifests differ. That absolute comparison is not a claim-quality result. On the defensible run-vs-control comparison, best3 performed better than this broad top-tool combo by about `0.0211` outcome points.

The strongest experimental result in this branch is still the targeted high-fit recency/day/contact scale500 run:

- Run: `outputs/gap_closure_lab/recombination_adoption/high_fit_recency_day_contact_scale500/full_benchmark_20260509_105941`
- Outcome delta: `+0.2488`
- Canonical/reference delta: `+0.1281`
- Exact success delta: `+83`

Interpretation: the current broad500 run is a useful stress test and is clearly positive, but it does not beat the documented current-code best3 500 lift. The targeted high-fit scale500 remains the best experimental lift, while best3 remains the stronger broad formal comparator until a same-manifest validation says otherwise.

## 2026-05-10 BridgePack Update

The action/precondition loop that followed this assessment closed the two largest actionable buckets requested for the next campaign and then recombined them into a stronger broad portfolio.

Closed narrow buckets:

- Reminder CRUD/scheduling confirm100: outcome delta `+0.2100`, about `+60%` relative lift, runtime exceptions `0`.
- Contact CRUD confirm100: control `0.5826`, SAGE `0.9129`, delta `+0.3303`, exact success delta `+56`, runtime exceptions `0`.
- Settings/device-state confirm100 also moved positively: control `0.7737`, SAGE `0.8683`, delta `+0.0946`.

Updated best broad experimental run:

- Name: `BridgePack Broad500: Ack-Retention Contact+Reminder+State Pack`
- Run: `outputs/gap_closure_lab/action_precondition_loop/ack_retention_bridge_broad500_taskcache/full_benchmark_20260510_133157`
- Registry: `artifacts/registry_experiments/gap_closure_lab/action_precondition_loop/full_state_send_contact_relationship_pack`
- Registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Scenario set: same 500 scenario IDs as `docs/sage_protocol/manifests/v2_1_formal_500.json`, reordered for the experimental split.
- Outcome: control `0.5949`, SAGE `0.8213`, delta `+0.2264`, relative lift `+38.1%`.
- Canonical/reference delta: `+0.0795`.
- Exact success delta: `+155`.
- Outcome gains/regressions: `243 / 40`.
- Control cache: `500` cached / `0` fresh, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- Candidate/SAGE cache: task-level cache off; OpenAI response cache disabled.
- Runtime exceptions: `0`; no observed helper side-effect incidents.
- Task Focus dashboard: `file:///Users/christopherclark/Library/Mobile%20Documents/com~apple~CloudDocs/_Chris_Docs/Coding/toolsandbox-sage-gap-closure-lab/outputs/gap_closure_lab/action_precondition_loop/ack_retention_bridge_broad500_taskcache/full_benchmark_20260510_133157/dashboard/task_focus.html`.

Interpretation: this supersedes the older top-tool broad500 stress result as the best broad experimental result in this branch. It beats the documented current-code best3 500 run-vs-control lift of `+0.1617` experimentally, but it is not protected final claim evidence because it includes branch-only actor/router bridge code and has not been rerun in a clean locked formal validation against best3 and V2.6.

## What Worked

| Lane | Sample | Exposure/calls | Mean outcome delta | Assessment |
| --- | ---: | --- | ---: | --- |
| Message/email search by recency | 24 | 24 called, 0 VNC | `+0.5646` | Strongest broad natural-adoption lane. Keep. |
| Reminder search/action by recency | 70 | 63 called, 7 VNC | `+0.2922` | Strong high-volume lane. Keep and reuse. |
| Contact lookup/scalar selection | 36 | 16 called, 20 VNC | `+0.1749` | Positive but adoption remains weak. Keep/refine routing and affordance. |
| Reminder week-delta creation/scheduling | 36 | 12 called, 24 no-visible | `+0.1852` | The week-delta slice works; date/weekday variants lack coverage. |
| Timestamp/search-window helpers | tool-level | `relative_day_time_to_timestamp` 45/51, `resolve_search_window_or_bounds` 66/106 | called-subset `+0.4699` and `+0.3228` | Core retained tools; still need tighter negative triggers. |

Minor positive tools remain relevant even when they are low frequency. `plan_contact_lookup_query`, `select_message_counterparty_for_contact_update`, `select_message_content_by_recency`, and the timestamp/window helpers all justify retention as part of a smaller routed portfolio because they solve concrete gaps when the matching task appears.

## Category Gaps Without Effective Tools

| Gap bucket | Sample | No visible helper | Visible-not-called | Called | Mean outcome delta | Diagnosis |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Safe insufficient-information / abstention | 119 | 111 | 4 | 4 | `-0.0035` | Largest unsupported bucket. Existing broad abstention tools were safe but not outcome-positive; next design must be narrower and final-answer-ready. |
| Settings / device-state preconditions and toggles | 124 | 80 | 13 | 31 | `+0.0392` | Large bucket with partial accidental help, but no dedicated safe state/precondition helper. Regressions concentrate in `get_wifi`, low-battery turn-on, and location/wifi state tasks. |
| Contact update / deletion / creation | 55 | 35 | 20 | 0 | `+0.0303` | No current tool receives natural calls for contact CRUD. Some base behavior is positive, but helper support is missing. |
| Reminder creation / modification / deletion / scheduling | 36 | 24 | 0 | 12 | `+0.1852` | Week-delta tasks get help; date/weekday and exact scheduling variants are unsupported. |
| Send-message composition / precondition | 8 | 8 | 0 | 0 | `-0.0408` | Fully unsupported in this portfolio. Likely needs recipient/content/precondition/action-spec validation without side effects. |
| Calendar/date arithmetic and windows | 20 | 7 | 1 | 12 | `0.0000` | `days_between_timestamps` is useful elsewhere, but this broad slice did not move outcome and canonical/reference fell; needs final-answer validation and better task-fit gating. |
| Generic search/selection | 8 | 0 | 7 | 1 | `+0.1557` | Potential exists, but adoption is the blocker. |

The best next bucket is not another recency-only selector. The broad lift is constrained by a combined action/precondition surface: settings/device-state, insufficient information, contact CRUD, reminder CRUD, and send-message preconditions. These buckets are large, recurring, and currently under-tooled.

## Most Important Missing Tool Type

The next big tool should be a side-effect-free task feasibility and action-spec normalizer.

Working name: `prepare_safe_action_or_abstain`.

Purpose:

- Decide whether the requested task is actionable with the available state, search results, and service affordances.
- Normalize final action requirements into a final-answer-ready plan without executing side effects.
- Return a safe abstain reason when information, capability, target identity, or device state is insufficient.
- Preserve side-effect discipline: no mutations, no service calls, no hard-coded scenario IDs, no hidden labels.

Required output shape:

- `status`: `ready`, `missing_information`, `blocked_by_state`, `unsupported_capability`, `ambiguous_target`, or `not_applicable`
- `task_family`: settings, contact, reminder, message, search, date, or other
- `required_fields`: concise list
- `missing_fields`: concise list
- `selected_target_summary`: scalar string or empty
- `action_argument_summary`: scalar/list fields ready for the actor
- `final_response_recommendation`: short safe answer/action phrasing
- `abstain_reason`: short reason when not ready

This should be tested as a small routed bundle, not exposed globally.

## Iterative Loop Prepared

Use the broad500 assessment as a repair/design split only. Do not use these tasks as final claim evidence after tool design.

Loop 01 should test three variants:

1. Minimal feasibility classifier: only reports ready/missing/blocked/unsupported/ambiguous.
2. Action-spec normalizer: converts visible target, time, contact, reminder, and message fields into final-answer-ready argument summaries.
3. Chain variant: feasibility classifier -> existing timestamp/recency helper -> action-spec normalizer.

Initial targeted diagnostic split:

- 20 tasks total, no label inspection before sealed run.
- 5 settings/device-state tasks.
- 5 insufficient-information tasks.
- 4 contact CRUD tasks.
- 4 reminder CRUD/scheduling tasks.
- 2 send-message precondition tasks.

Progression:

- Run targeted20 natural adoption for each variant.
- If hidden or visible-not-called, run force-exposure/force-call diagnostics on a safe seed/dev-only subset.
- Repair schema/metadata only if force diagnostics show latent value and no side-effect risk.
- Run expanded60 with the best natural-adoption variant.
- If expanded60 is positive with natural calls, run broad100 against the current top combo and best3 reference on the same manifest.
- Scale only if broad100 beats the relevant comparison by outcome, with zero runtime exceptions and zero helper side-effect incidents.

Comparison portfolios for the loop:

- best3 reference only.
- current high-fit retained portfolio.
- current broad top-tool combo.
- broad top-tool combo plus `prepare_safe_action_or_abstain`.
- broad top-tool combo minus low-value field extractor plus `prepare_safe_action_or_abstain`.

Primary success criterion remains outcome/task completion. Canonical/reference is secondary and should be interpreted carefully when a generated helper replaces a reference intermediate route.

## Decision

Keep the original broad top-tool combo as a positive historical stress result, not a best3 replacement. The subsequent BridgePack broad500 result is the current best experimental candidate and should move to clean matched formal validation before any protected claim. The remaining improvement surface is no longer whether contact/reminder/state buckets can move narrow runs; it is whether the bridge-policy dependency can be formalized safely and whether the remaining insufficient-information and low-battery/settings regressions can be reduced without weakening the broad lift.

## 2026-05-10 Clean Rerun Update

The latest full rerun after bridge-name and side-effect-accounting repairs is now the current clean broad reference:

- Name: `BridgePack Clean Broad500: State Sequence Preservation Pack`
- Run: `outputs/gap_closure_lab/action_precondition_loop/state_sequence_bridge_broad500_taskcache_clean_rerun/full_benchmark_20260510_164959`
- Outcome: control `0.5949`, SAGE `0.8134`, delta `+0.2185`, relative lift `+36.7%`.
- Exact success delta: `+163` (`26 -> 189`).
- Canonical/reference delta: `+0.0811`.
- Outcome gains/regressions/preserved: `240 / 46 / 98`.
- Runtime exceptions: `0`.
- Helper side-effect incidents: `0`.
- Control cache: `500` cached / `0` fresh; candidate fresh, OpenAI response cache off.

This clean rerun still beats the documented current-code best3 500 run-vs-control lift (`+0.1617`) and supersedes the earlier broad500 diagnostic runs as the safety-clean campaign reference. The remaining gap assessment is unchanged: the best next formal step is not more local prompt tweaking, but a locked same-manifest validation against best3 and V2.6 with the bridge-policy dependency declared.
