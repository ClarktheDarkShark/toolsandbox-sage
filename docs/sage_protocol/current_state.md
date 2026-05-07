# Current State

- Date: 2026-05-07
- Last completed step: `pre_final_hardening_chapter3_readiness`
- Last decision: `final preflight ready; best3 broad claim preserved; V2.6 expanded evidence remains secondary`
- Primary metric: outcome/task-completion
- Active frozen helpers: `relative_day_time_to_timestamp, resolve_search_window_or_bounds, select_record_by_timestamp_extreme`
- Active registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Final-run preflight: `scripts/preflight_final_run.py`
- Final-run preflight config: `docs/sage_protocol/final_run_preflight_config.json`
- Final statistical analysis report: `docs/sage_protocol/final_statistical_analysis_report.md`
- Final statistical analysis JSON: `artifacts/summaries/final_statistical_analysis/analysis.json`
- Chapter 3 methodology prep: `docs/sage_protocol/chapter3_methodology_prep.md`
- Versioned methodology heuristics: `docs/sage_protocol/protocol_heuristics_v1.json`
- Final frozen run requirements: generation OFF, control cache `use-if-eligible`, routing evidence `disabled` or explicitly `pinned`, no diagnostic force-call env vars, no low-quality override.
- Cache/feedback trace caveat: cached controls are score-complete for metrics, but cached-only synthetic rows are labeled trace-incomplete in feedback packets when historical trajectories are unavailable.
- Formal 100 run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
- Formal 100 dashboard: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/index.html`
- Formal 100 task focus dashboard: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428/dashboard/task_focus.html`
- Formal 100 outcome delta: `0.1347`
- Formal 100 relative outcome lift: `33.58%`
- Formal 100 exact successes: `control=16`, `SAGE=23`
- Formal 250 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Formal 250 dashboard: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/index.html`
- Formal 250 task focus dashboard: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/task_focus.html`
- Formal 250 outcome delta: `0.0806`
- Formal 250 relative outcome lift: `20.52%`
- Formal 250 exact successes: `control=31`, `SAGE=40`
- Formal 250 reference/canonical similarity delta: `0.0660`
- Formal 250 protocol gate: `True`
- Formal 250 route-mismatch-qualified: `False`
- Formal 250 runtime exceptions: `0`
- Helper side-effect incidents in contribution export: `0`
- Control cache mode: `use-if-eligible`; formal 100/250 controls were fresh because no compatible cached controls were eligible for the new manifest hashes.
- Summary artifact: `artifacts/summaries/v2_final_best3_formal_validation/summary.json`
- Final package: `artifacts/final_sage_praxis_package/`
- Main report: `docs/sage_protocol/v2_final_tool_pipeline_campaign_report.md`
- Next step: commit the coherent v1.0 repair/validation package, then begin a separate V2.0 campaign focused on autonomous shortfall-cluster birth for no-current-helper-fit tasks.
- Evidence lock report: `docs/sage_protocol/v2_formal250_evidence_lock_report.md`
- Metric audit report: `docs/sage_protocol/v2_formal250_metric_audit_report.md`
- Helper contribution audit: `docs/sage_protocol/v2_best3_helper_contribution_audit.md`
- Frozen claim registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Robustness 60 run: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441`
- Robustness 60 outcome delta: `0.0612`
- Robustness 60 relative outcome lift: `14.01%`
- Robustness 60 decision: `robustness confirmed`
- V2.0 plan: `docs/sage_protocol/v2_0_shortfall_birth_plan.md`
- V2.0 shortfall cluster report: `docs/sage_protocol/v2_0_shortfall_cluster_report.md`
- V2.0 cluster artifact: `artifacts/summaries/v2_0_shortfall_clusters/latest_shortfall_clusters.json`
- V2.0 cluster decision: `candidate found`
- V2.0 next step: build and run discovery-60 with generation ON in a copied candidate registry.

## V2.0 Discovery-60 Status
- Date: `2026-05-04T08:41:14.546936`
- Last completed V2.0 step: `discovery_60_generation_on` and `candidate_triage`
- V2.0 discovery run: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640`
- V2.0 discovery dashboards: `http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/task_focus.html`
- V2.0 candidate registry: `artifacts/registry_candidates/v2_0_discovery60_20260504_081357/registry_manifest.json`
- Frozen best3 registry modified: `no`
- Candidate registry restored after failed protocol gate: `yes`
- Discovery outcome delta: `0.0015`
- Discovery canonical/reference delta: `0.0289`
- Discovery exact successes: `control=4`, `SAGE=2`
- Discovery tool birth: `attempts=8`, `accepted=['next_dependency_precondition_call']`
- Accepted-but-uncalled: `['next_dependency_precondition_call']`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- V2.0 triage decision: `routing repair needed`
- V2.0 next step: repair dependency-helper routing/affordance and grading-accounting metadata, then rerun a focused fair-chance diagnostic before confirmation-60.


## V2.0 Dependency Fair-Chance Routing Status
- Date: `2026-05-04T17:15:00`
- Last completed V2.0 step: `dependency_fair_chance_routing_repair`
- Candidate registry: `artifacts/registry_candidates/v2_0_dependency_fair_chance20_20260504_165041/registry_manifest.json`
- Frozen best3 registry modified: `no`
- Final diagnostic run: `outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647`
- Final diagnostic dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/task_focus.html`
- Diagnostic manifest: `artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/cohort_manifest.json`
- Diagnostic summary: `artifacts/summaries/v2_0_dependency_fair_chance20_20260504_165041/diagnostic_summary.json`
- Outcome delta: `+0.0185`
- Canonical/reference delta: `+0.0553`
- Exact successes: `control=0`, `SAGE=2`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- `next_dependency_precondition_call`: visible `9`, called `0`, visible-not-called `9`, attempts `0`
- Fair-chance routing: `worked for exposure`; adoption still failed after dict-key affordance repair.
- Report: `docs/sage_protocol/v2_0_dependency_fair_chance_routing_report.md`
- Decision: `park dependency lane`
- V2.0 next step: return to shortfall mining and prioritize another no-current-helper-fit cluster; do not run confirmation-60 for `next_dependency_precondition_call`.

## V2.0 Dependency Schema Verification Status
- Date: `2026-05-04T17:34:40-04:00`
- Verification run: `outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556`
- Dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556/dashboard/task_focus.html`
- Outcome delta: `+0.1593`; canonical/reference delta: `+0.0803`; exact successes: `control=0`, `SAGE=3`; runtime exceptions: `0`.
- `next_dependency_precondition_call`: visible `9`, called `0`, visible-not-called `9`, attempts `0` after live model calls and OpenAI schema affordance repair.
- Root cause: accepted helper required an opaque `dependency_state` dict, making direct ToolSandbox setter/getter routes simpler than the helper.
- Repair: state/precondition candidate gate now rejects opaque dict input contracts; dependency birth prompt/examples now require concrete top-level scalar inputs.
- Frozen best3 registry check: `PASS`; stale candidate registry with `next_dependency_precondition_call`: expected `FAIL` on `state_helper_opaque_dict_input_contract`.
- Decision: `park dependency lane`.
- V2.0 next step: mine another no-current-helper-fit cluster; do not confirm `next_dependency_precondition_call` without a scalar-input successor and actual call evidence.

## V2.0 Dependency Lucrative/Force-Call Diagnostic
- Date: `2026-05-04T18:06:00-04:00`
- Diagnostic candidate registry: `artifacts/registry_candidates/v2_0_dependency_lucrative20_20260504_174000/registry_manifest.json`
- Candidate: scalar-input `next_dependency_precondition_call`
- Natural run: `outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438`
- Natural dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438/dashboard/task_focus.html`
- Natural result: outcome delta `+0.0552`, canonical delta `+0.0681`, dependency helper visible/called `10 / 0`, protocol gate FAIL.
- Forced-after-error run: `outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421`
- Forced dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421/dashboard/task_focus.html`
- Forced result: dependency helper visible/called `10 / 8`, called-subset outcome delta `-0.0285`, one side-effect preservation failure, overall outcome delta `-0.0002`, protocol gate FAIL.
- Diagnostic force-call support added: `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME` plus `SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR=1`.
- Decision: `park dependency lane`; keep force-call machinery for future concept tests, but do not promote this helper.


## V2.0 Selection-Action Discovery60 Status
- Date: `2026-05-04T19:09:36`
- Manifest: `artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_manifest.json`
- Frozen best3 registry modified: `no`
- Candidate registry: `artifacts/registry_candidates/v2_0_selection_action_discovery60_20260504_183108`
- Arm A best3-only run: `outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306`
- Arm A dashboards: `http://127.0.0.1:5520/outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306/dashboard/task_focus.html`
- Arm A outcome delta: `0.0989`; relative lift `18.96%`; canonical delta `0.1147`; exact `4 -> 8`
- Arm B discovery run: `outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638`
- Arm B dashboards: `http://127.0.0.1:5520/outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638/dashboard/task_focus.html`
- Arm B outcome delta: `0.0245`; relative lift `4.35%`; canonical delta `0.0552`; exact `5 -> 9`
- Generated candidate: `select_contact_field_by_constraint`; natural visible/called/VNC `2 / 0 / 2`
- Force diagnostic run: `outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512`
- Force diagnostic dashboards: `http://127.0.0.1:5520/outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512/dashboard/task_focus.html`
- Force result: selector visible/called `8 / 4`; called-subset outcome delta `-0.0132`; overall outcome delta `-0.1074`
- Runtime exceptions: discovery `0`, force `0`
- Helper side-effect incidents: discovery `0`, force `0`
- Reports: `docs/sage_protocol/v2_0_selection_action_discovery60_report.md`, `docs/sage_protocol/v2_0_selection_action_candidate_triage.md`
- Decision: `candidate concept negative`
- V2.0 next step: park this selector candidate and mine the next uncovered no-current-helper-fit cluster; do not run confirmation60 for this candidate.

## V2.1 Tool Expansion Discovery60 Status
- Date: `2026-05-04T20:11:44-04:00`
- Manifest: `artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json`
- Cohort quality: `PASS`; scenarios `60`; distinct base families `20`; largest family share `0.10`; no-current-helper-fit share `0.25`.
- Frozen best3 registry modified: `no`.
- Candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835/registry_manifest.json`.
- Best3-only run: `outputs/v2_1_tool_expansion_best3_60_20260504_191835/mechanism_60_20260504_191910`; outcome delta `+0.1543`; canonical delta `+0.0527`; exact `6 -> 10`; runtime/side-effect `0 / 0`.
- Discovery run: `outputs/v2_1_tool_expansion_discovery60_run_20260504_191835/mechanism_60_20260504_192907`; outcome delta `+0.1586`; canonical delta `+0.1377`; exact `2 -> 9`; runtime/side-effect `0 / 0`.
- Candidates: accepted `prepare_side_effect_args_from_selected_record`; rejected `select_visible_record_by_constraints`, `select_action_target_by_recency`.
- Accepted candidate natural visibility/calls/VNC: `2 / 0 / 2`.
- Final force diagnostic: `outputs/v2_1_tool_expansion_force_prepare_args12_abstain_20260504_201500/mechanism_12_20260504_200720`; candidate visible/called/VNC/failed `12 / 8 / 4 / 0`, but calls abstained with `missing_required_helper_inputs`.
- Repairs added: V2.1 cluster observations, task-strata triggers, generator guidance, composite one-of-many downstream routing, post-selection docstring affordance, missing-argument safe abstention.
- Tests: targeted V2 suite `95 passed`; candidate registry check-only PASS.
- Reports: `docs/sage_protocol/v2_1_tool_expansion_discovery60_report.md`, `docs/sage_protocol/v2_1_tool_expansion_candidate_triage.md`.
- Decision: `generation contract repair needed`.
- Next action: repair generated selector/composite contracts for model-callable inputs and non-abstaining positive live validation before another 60-scenario discovery; no confirmation60 for current candidates.

## V2.1 Tool Callability Repair Status
- Date: `2026-05-04T23:10:00-04:00`
- Frozen best3 registry modified: `no`.
- Candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/registry_manifest.json`.
- Repairs: optional `constraints` defaulting, action-selector usage guidance, recency-action routing suppression for non-recency tasks, selector one-of-many downstream routing, safe `all`/`any` builtins, post-selection trace chaining.
- Tests: targeted V2 suite `104 passed`; candidate registry check-only `PASS`.
- Force diagnostic: `outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829`; selector visible/called/VNC `9 / 5 / 4`; called-subset outcome delta `+0.6798`; runtime/side-effect `0 / 0`; protocol gate `PASS`.
- Natural diagnostic: `outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708`; selector visible/called/VNC `5 / 3 / 2`; called-subset outcome delta `+0.4828`; runtime/side-effect `0 / 0`; protocol gate `PASS`.
- Report: `docs/sage_protocol/v2_1_tool_callability_repair_report.md`.
- Decision: `candidate ready for confirmation60`.
- Next action: run frozen confirmation-60 best3-only vs best3 + `select_action_target_by_recency`; do not promote `prepare_side_effect_args_from_selected_record` from this evidence.

## V2.1 Select Action Target Final Decision
- Date: `2026-05-04T23:55:00-04:00`
- Candidate: `select_action_target_by_recency`.
- Frozen best3 registry modified: `no`.
- Callability result: fixed. Optional `constraints` defaults eliminated `missing_required_helper_inputs`; helper returned usable selected records and preserved downstream `remove_reminder` in trace.
- Natural fair-chance diagnostic: visible/called/VNC `5 / 3 / 2`; called-subset outcome `+0.4828`; runtime/side-effect `0 / 0`.
- Confirmation60 after insufficient-info suppression: `outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336`.
- Confirmation60 selector contribution: visible/called/VNC `5 / 2 / 3`; called-subset outcome `-0.1667`; called-subset canonical `+0.1111`; runtime/side-effect `0 / 0`.
- Confirmation60 overall: outcome `+0.0907`; canonical `+0.0612`; exact success delta `+6`; protocol PASS.
- Decision: `candidate concept negative; park candidate`.
- Next action: keep framework callability repairs, do not promote selector, mine next uncovered cluster that is less redundant with `select_record_by_timestamp_extreme`.


## V2.1 Gap Closure Discovery and Triage
- Date: `2026-05-04T23:05:00-04:00`
- Frozen best3 registry modified: `no`.
- Gap atlas: `artifacts/summaries/v2_1_gap_closure_20260504_221814/gap_atlas.json`.
- Discovery60 manifest: `artifacts/summaries/v2_1_gap_closure_20260504_221814/cohort_manifest.json`; cohort quality `PASS`; scenarios `60`; no-current-helper-fit share `41.67%`.
- Discovery60 run: `outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901`; dashboards opened at `http://127.0.0.1:5520/outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901/dashboard/task_focus.html`.
- Discovery60 metrics: outcome delta `0.0088`; canonical delta `-0.0101`; exact `3 -> 3`; runtime exceptions `0`.
- Candidate accepted: `prepare_side_effect_args_from_selected_record`; natural visible/called/VNC `27 / 0 / 27`.
- Candidate rejected: `select_visible_record_by_constraints` for negative-case non-abstention after selector normalization repair.
- Repairs: unique original-search-result selected-record autofill, generic routing hard-block precedence, post-selection routing suppression, low-friction composite generation guidance.
- Post-repair natural diagnostic: `outputs/v2_1_gap_closure_natural_prepare_args12_post_routing_20260504_2300/mechanism_12_20260504_224921`; visible/called/VNC `12 / 0 / 12`; outcome delta `-0.0510`.
- Post-repair force diagnostic: `outputs/v2_1_gap_closure_force_prepare_args12_post_autofill_20260504_2250/mechanism_12_20260504_224507`; visible/called/VNC `12 / 12 / 0`; called-subset outcome `-0.0316`; overall outcome `-0.0316`.
- Reports: `docs/sage_protocol/v2_1_gap_closure_discovery60_report.md`, `docs/sage_protocol/v2_1_gap_closure_candidate_triage.md`, `docs/sage_protocol/v2_1_gap_closure_confirmation60_report.md`, `docs/sage_protocol/v2_1_expanded_portfolio_ablation60_report.md`.
- Decision: `best3 remains final portfolio`.
- Next action: do not promote selected-record-only side-effect prep; mine a different cluster or require future composite candidates to accept visible record lists/scalar constraints and prove natural adoption.

## V2.1 Scale Validation Status
- Date: `2026-05-05T04:45:00-04:00`
- Portfolio scaled: frozen best3 only. Expanded V2.1 candidates were not promoted.
- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Quality-gate repair: scale-aware variant cap for `>=500` scenario runs; dominant-family share remains capped at `8%`.
- Formal 100: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`; relative outcome lift `+33.58%`; canonical delta `+0.0911`; exact `16 -> 23`; runtime/side-effect `0 / 0`; protocol gate `PASS`.
- Formal 250: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`; relative outcome lift `+20.52%`; canonical delta `+0.0660`; exact `31 -> 40`; runtime/side-effect `0 / 0`; protocol gate `PASS`.
- Formal 500: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`; relative outcome lift `+14.35%`; canonical delta `+0.0331`; exact `60 -> 76`; runtime/side-effect `0 / 0`; cohort quality `PASS`; protocol gate `FAIL` on older absolute-delta threshold only.
- Formal 1000+: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905`; scenarios `1032`; relative outcome lift `+14.05%`; canonical delta `+0.0342`; exact `159 -> 195`; runtime/side-effect `0 / 0`; cohort quality `PASS`; external-service cases present and reported; protocol gate `FAIL` on older absolute-delta/helper-call-share thresholds.
- Reports: `docs/sage_protocol/v2_1_expanded_portfolio_100_report.md`, `docs/sage_protocol/v2_1_expanded_portfolio_250_report.md`, `docs/sage_protocol/v2_1_formal_500_report.md`, `docs/sage_protocol/v2_1_formal_1000_report.md`, `docs/sage_protocol/final_claim_summary.md`.
- Final package updated: `artifacts/final_sage_praxis_package/`.
- Decision: `full-benchmark 1000+ positive; best3 remains final portfolio`.
- Next action: write final dissertation-facing narrative around frozen best3; keep V2.1 generated candidates parked unless future work proves additive natural adoption over best3.


## V2.2 Masked-Best3 Campaign Status
- Date: `2026-05-05T08:20:00-04:00`
- Frozen best3 registry modified: `no`.
- Masked tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`.
- Main discovery manifest: `artifacts/summaries/v2_2_masked_best3_discovery60_20260505_064113/cohort_manifest.json`.
- Main discovery run: `outputs/v2_2_masked_best3_discovery60_20260505_064113/mechanism_60_20260505_064202`.
- Selector fair-chance run: `outputs/v2_2_masked_best3_fairchance60_docfix_20260505_064113/mechanism_60_20260505_073523`; `select_visible_record_by_constraints` visible/called/VNC `34 / 0 / 34` after routing/docstring repairs.
- Selector force diagnostic: `outputs/v2_2_masked_best3_selector_force60_20260505_064113/mechanism_60_20260505_070818`; visible/called `34 / 29`, called-subset outcome `0.053338674217560895`; parked for natural-adoption failure.
- Confirmed V2.2 tool: `days_between_timestamps`.
- Confirmation run: `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`; outcome delta `+0.0891`, canonical delta `-0.0600`, exact successes `4 -> 4`.
- `days_between_timestamps` contribution: visible/called/VNC `14 / 14 / 0`, called-subset outcome `0.10714285714285714`, called-subset canonical `-0.2102519581336632`, helper-substitution route mismatch `True`.
- New toolset registry: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`.
- New toolset count: `1 / 3` confirmed.
- Reports: `docs/sage_protocol/v2_2_masked_best3_discovery_report.md`, `docs/sage_protocol/v2_2_candidate_callability_report.md`, `docs/sage_protocol/v2_2_candidate_confirmation_report.md`, `docs/sage_protocol/v2_2_new_toolset_registry_report.md`, `docs/sage_protocol/v2_2_combined_portfolio_ablation_report.md`.
- Decision: `new toolset has 1 confirmed tool`.
- Next action: do not combine portfolios yet; either continue masked discovery on a new tool-suitable non-best3 cluster or stop for review because selector, side-effect-prep, recency-action, and dependency/precondition lanes are parked by evidence.

## V2.2 Masked-Best3 Loop 2 Status
- Date: `2026-05-05T17:30:00-04:00`
- Frozen best3 registry modified: `no`.
- Masked tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`.
- Confirmed V2.2 tools before loop: `days_between_timestamps`.
- Confirmed V2.2 tools after loop: `days_between_timestamps` only.
- V2.2 new-toolset registry: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`.
- V2.2 new-toolset registry SHA-256: `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`.
- Gap atlas: `artifacts/summaries/v2_2_loop2_20260505_164027/latest_gap_atlas.json`.
- Selector diagnostic run: `outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951`; outcome `-0.0263`; canonical `-0.0172`; exact `2 -> 2`; selector visible/called/VNC `16 / 0 / 16`; runtime/side-effect `0 / 0`; decision `selector lane parked`.
- Discovery60 retry run: `outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056`; outcome `+0.0335`; canonical `-0.0018`; exact `14 -> 11`; accepted `extract_stock_symbol`; accepted-but-uncalled `extract_stock_symbol`; runtime/side-effect `0 / 0`.
- Extract-stock force diagnostic after trace-bridging: `outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542/mechanism_40_20260505_171545`; visible/called/VNC/failed `4 / 2 / 2 / 2`; called-subset outcome `-0.5000`.
- Extract-stock fair-chance diagnostic: `outputs/v2_2_extract_stock_fairchance20_20260505_172237/mechanism_40_20260505_172240`; outcome `+0.0534`; canonical `+0.0042`; exact `5 -> 6`; visible/called/VNC/failed `4 / 4 / 0 / 0`; called-subset outcome `-0.0772`; runtime/side-effect `0 / 0`; decision `candidate parked`.
- Framework repairs retained: bounded selector actor policy, fair-chance routing for strong selector matches, stock negative-applicability metadata, derived-value actor policy, and trace-bridging for single-dict derived helpers.
- Tests: targeted unit suite `115 passed`; V2.2 new-toolset registry check-only `PASS`.
- Reports: `docs/sage_protocol/v2_2_gap_atlas_loop2_report.md`, `docs/sage_protocol/v2_2_selector_actor_policy_diagnostic20_report.md`, `docs/sage_protocol/v2_2_masked_best3_discovery_loop2_report.md`, `docs/sage_protocol/v2_2_new_toolset_registry_report.md`.
- Decision: `continue masked discovery`.
- Next action: continue masked discovery on a new non-best3, non-parked cluster; do not run confirmation60 for `extract_stock_symbol`; do not run combined ablation yet.


## V2.3 Medium-Grain Deterministic Skill Experiment
- Date: `2026-05-05T19:05:00-04:00`
- Frozen best3 registry modified: `no`.
- Masked tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`.
- Initial discovery60: `outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755`; outcome `-0.0006`; canonical `0.0031`; exact delta `2`; generated candidates accepted `0`.
- Framework repairs: medium-grain feature flag, diverse cluster observation, generator downstream-preservation guidance, composite docstring affordance, records trace-bridging, live-positive-abstain rejection, composite output normalization.
- Diagnostic20 acceptance run: `outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213`; accepted `constraint_to_action_planner`; outcome `0.1715`; canonical `0.0085`; exact delta `1`; visible/called/VNC `6 / 0 / 6`; runtime/side-effect `0 / 0`.
- Force-call diagnostic: `outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852`; visible/called/VNC `15 / 13 / 2`; called-subset outcome `-0.13126404560161367`; canonical `-0.13004658549699968`; side-effect/runtime `9 / 0`.
- Reports: `docs/sage_protocol/v2_3_medium_grain_skill_experiment_report.md`, `docs/sage_protocol/v2_3_medium_grain_candidate_triage.md`, `docs/sage_protocol/v2_3_medium_grain_confirmation_report.md`.
- Decision: `medium-grain skill concept negative`.
- Next action: park `constraint_to_action_planner`; continue masked discovery on a different non-best3 cluster or redesign medium-grain contracts to separate answer-only resolution from side-effect action planning.

## V2.2 Best4 Additivity Check Status
- Date: `2026-05-06T09:05:00-04:00`
- Frozen best3 registry modified: `no`.
- Best4 candidate registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`.
- Best4 registry SHA-256: `e497d29b7b31b89b9368af7c9327679086a881f8e9c62a182ca07b25f18f7834`.
- Ablation60 manifest: `artifacts/summaries/v2_2_best4_ablation60_20260506_075831/cohort_manifest.json`; quality gate `PASS`; no external-service contamination; no-current-helper-fit share `0.40`.
- Ablation60 best3-only run: `outputs/v2_2_best4_ablation60_best3_20260506_075831/mechanism_60_20260506_075938`; outcome delta `+0.0504`; canonical delta `+0.0858`; exact `3 -> 5`; runtime/side-effect `0 / 0`.
- Ablation60 days-only run: `outputs/v2_2_best4_ablation60_days_only_20260506_075831/mechanism_60_20260506_081058`; outcome delta `+0.0261`; canonical delta `+0.0191`; exact `1 -> 4`; days visible/called/VNC `8 / 8 / 0`; runtime/side-effect `0 / 0`.
- Ablation60 best4 run: `outputs/v2_2_best4_ablation60_best4_20260506_075831/mechanism_60_20260506_082133`; raw outcome delta `-0.0103`; canonical delta `-0.0030`; exact `3 -> 4`; days visible/called/VNC `8 / 8 / 0`; runtime/side-effect `0 / 0`.
- Ablation common-control recalculation: Best4 candidate mean exceeded best3 by `+0.0118` over `52` numeric-outcome scenarios, so frozen100 was run as a conservative follow-up.
- Frozen100 Best4 run: `outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140`; dashboard `http://127.0.0.1:5614/outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140/dashboard/index.html`; task focus `http://127.0.0.1:5614/outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140/dashboard/task_focus.html`.
- Frozen100 Best4 metrics: outcome delta `+0.0679`; canonical delta `+0.0696`; exact `14 -> 19`; runtime/side-effect `0 / 0`.
- Preserved best3 formal100 comparison: outcome delta `+0.1347`; canonical delta `+0.0911`; exact `16 -> 23`.
- Best4 vs best3 formal100 candidate outcome difference: `-0.0672`; exact-success difference `-4`.
- Decision: `best4 not additive`; do not run Best4 frozen250; keep best3 as final validated portfolio. `days_between_timestamps` remains a confirmed narrow V2.2 standalone tool, not promoted into the main portfolio.
- Reports: `docs/sage_protocol/v2_2_best4_candidate_registry_report.md`, `docs/sage_protocol/v2_2_best4_ablation60_report.md`, `docs/sage_protocol/v2_2_best4_frozen100_report.md`.


## V2.4 Additive-Only Gap Closure Status
- Date: `2026-05-06T10:15:00-04:00`
- Frozen best3 registry modified: `no`.
- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
- Frozen best3 SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- `days_between_timestamps` remains confirmed standalone only; Best4 is not additive and no Best4 frozen250 was run.
- Additive gap atlas: `artifacts/summaries/v2_4_additive_gap_atlas/latest_gap_atlas.json`.
- Selected non-parked cluster: `external_service_answer_extraction`.
- Discovery manifest: `artifacts/summaries/v2_4_additive_discovery60_20260506_095428/cohort_manifest.json`; cohort quality `PASS`; external-service contamination allowed and reported; no low-quality override used.
- Discovery run: `outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500`.
- Candidate born: `extract_service_answer_field`.
- Candidate adoption: visible/called/VNC `49 / 5 / 44`.
- Discovery metrics: outcome delta `+0.0031`; relative outcome lift `+1.20%`; canonical delta `+0.0127`; exact `8 -> 7`; runtime/side-effect `0 / 0`.
- Candidate called-subset outcome: `-0.1804`; called-subset canonical `+0.1609`.
- Decision: `candidate concept negative`; no additive confirmation60; best3 remains final validated portfolio.
- Reports: `docs/sage_protocol/v2_4_additive_gap_atlas_report.md`, `docs/sage_protocol/v2_4_additive_discovery60_report.md`, `docs/sage_protocol/v2_4_additive_confirmation60_report.md`.
- Next action: stop additive promotion for this candidate; only resume discovery after a fresh atlas identifies a materially different non-parked mechanism with plausible additivity over best3.

## V2.5 Tool-Foundry Micro Status
- Date: `2026-05-06T12:05:00-04:00`
- Frozen best3 registry modified: `no`.
- Control cache repair: task-level baseline reuse implemented; `manifest_checksum` no longer resets compatibility. Cache still requires matching task/scenario checksum, initial-state checksum, model/prompt/scorer/runner/ToolSandbox/base-policy fields.
- Cache verification: V2.5 micro runs used mixed controls with cached/fresh counts `17/3`, `17/3`, and `19/1`.
- Foundry artifact: `artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/candidate_batch_summary.json`.
- Candidate batch: proposed/accepted/rejected `2 / 2 / 0`; accepted `resolve_temperature_answer_unit`, `prepare_temperature_conversion_args`.
- Repaired scalar registry: `artifacts/registry_candidates/v2_5_temperature_answer_scalar/registry_manifest.json`, SHA-256 `854ec5fec66002dc14f64c60247e517c7f73b06a2cd63f1236f9be84afa5922a`.
- Best3-only micro: `outputs/v2_5_micro_temperature_best3_only_cached_20260506_113421/mechanism_40_20260506_113425`; outcome delta `+0.0272`; canonical delta `+0.0532`; exact `4 -> 6`; control source mixed `17 cached / 3 fresh`.
- Payload answer-helper micro: `outputs/v2_5_micro_temperature_answer_only_cached_20260506_112638/mechanism_40_20260506_112641`; outcome delta `+0.0916`; helper visible/called/VNC `8 / 1 / 7`; callability blocker identified.
- Scalar repaired helper micro: `outputs/v2_5_micro_temperature_scalar_repair_cached_20260506_114758/mechanism_40_20260506_114803`; outcome delta `-0.0579`; canonical delta `+0.0080`; exact `4 -> 7`; helper visible/called/VNC `8 / 5 / 3`; called-subset outcome `-0.1428`; runtime/side-effect `0 / 0`.
- Decision: `candidate concept negative` for the temperature unit answer lane; do not run additive60 for these candidates.
- Next action: park temperature answer/conversion candidates and continue V2.5 only if a different non-parked cluster has credible additive-over-best3 potential.

## V2.5 Foundry Loop 2-3 Checkpoint - 2026-05-06
- Protected best3 registry remains unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
- Distance candidate: `format_calculated_distance_km` accepted in candidate registry and naturally called on relevant positives. Repaired routing hides it on insufficient-information/minefield cases and unrelated triggerless tasks.
- Distance evidence: natural micro `outputs/v2_5_micro_distance_unitsafe_routingfix_cached_20260506_125948/mechanism_40_20260506_125953`; helper visible/called/VNC `4 / 4 / 0`; called-subset outcome `+0.5556`; best3+distance vs best3-only same-manifest outcome `+0.0447`. Status: micro-positive but too narrow to close gap alone.
- Location-field candidate: `resolve_location_lookup_field` accepted after payload-bridge repair. Natural adoption remained weak; force-after-lookup proved callability but not primary outcome value.
- Location evidence: force run `outputs/v2_5_micro_location_field_force_after_lookup_20260506_133440/mechanism_40_20260506_133444`; visible/called/VNC `4 / 4 / 0`; called-subset outcome `0.0`; canonical `+0.0368`; runtime/side-effect `0 / 0`. Status: parked as canonical-only/value failure.
- User insufficient-information finding incorporated: distance helpers must hide/abstain when current location is unavailable; calculating numeric distance in those scenarios is a minefield violation, not a scoring bug.
- Current summary artifact: `artifacts/summaries/v2_5_tool_foundry_loop2_3_micro_summary/summary.json`.
- Last report: `docs/sage_protocol/v2_5_micro_value_test_report.md`.
- Decision label: `continue gap-closure loop`.
- Next action: continue V2.5 with a materially different high-gap cluster, preferably a narrow scalar direct-side-effect argument-preparation design that preserves original side-effect tools and is distinct from selected-record-only prep.

## V2.5 Direct Side-Effect Dict-Payload Diagnostic - 2026-05-06
- Candidate: `prepare_direct_contact_action_kwargs` in `artifacts/summaries/v2_5_tool_foundry_v2_5_loop4_direct_aliasfix_20260506_134732/candidate_batch_registry/registry_manifest.json`, SHA `4fe3c539a8326e3c8e37cd5f47b2b83fe740ba9d6cf0756dae0ef6c93b6d4411`.
- Natural run: `outputs/v2_5_micro_direct_action_cached_20260506_134827/mechanism_40_20260506_134832`; visible/called/VNC `8 / 0 / 8`; not tool-driven.
- Force run: `outputs/v2_5_micro_direct_action_force_20260506_135241/mechanism_40_20260506_135245`; visible/called/VNC `8 / 8 / 0`; calls used `{}` and returned `missing_required_helper_inputs`; called-subset outcome `-0.1155`; side-effect preservation incidents `1`.
- Decision: park the dict-payload design as callability/value/safety failure. The direct-side-effect cluster is not exhausted; next materially different repair is a flat-scalar interface.
- Decision label: `continue gap-closure loop`.

## V2.5 Candidate Pack 1 Additive60 - 2026-05-06 15:17
- Frozen best3 registry unchanged.
- Flat-scalar direct-action candidate `prepare_direct_contact_action_args`: valid and force-callable, but parked; natural calls `0/8`, force calls `8/8`, called-subset outcome `-0.0816`, side-effect/runtime `0 / 0`.
- Candidate Pack 1 registry: `artifacts/registry_candidates/v2_5_candidate_pack1_distance/registry_manifest.json`, SHA `d599a8e56f024f978bcb572ca0df12abb4a4d2196639becf64ef826cbf5f73f4`.
- Additive60 manifest: `artifacts/summaries/v2_5_candidate_pack1_distance_additive60/cohort_manifest.json`; quality `pass`, best3 no-current-helper-fit proxy `0.600`.
- Best3 run: `outputs/v2_5_additive60_pack1_best3_20260506_144550/mechanism_60_20260506_144554`; outcome `0.4437`; canonical `0.8453`.
- Pack run: `outputs/v2_5_additive60_pack1_distance_20260506_150042/mechanism_60_20260506_150047`; outcome `0.5923`; canonical `0.7941`.
- Pack vs best3 outcome delta `+0.1486`; canonical delta `-0.0512`.
- `format_calculated_distance_km` visible/called/VNC `9 / 8 / 1`; called-subset outcome `+0.3125`; side-effect/runtime `0 / 0`.
- Gap reduction proxy `22.22%`.
- Decision label: `candidate pack ready for confirmation60`.
- Next action: run confirmation60 generation OFF with the frozen Candidate Pack 1 registry against best3-only.

## V2.5 Candidate Pack 1 Confirmation60 - 2026-05-06 16:07
- Frozen best3 registry unchanged.
- Confirmation manifest: `artifacts/summaries/v2_5_candidate_pack1_distance_confirmation60/cohort_manifest.json`; quality `pass`; best3 no-current-helper-fit proxy `0.600`.
- Best3 run: `outputs/v2_5_confirmation60_pack1_best3_20260506_152240/mechanism_60_20260506_152245`; outcome `0.4272`; canonical `0.7876`; protocol gate `False`.
- Pack run: `outputs/v2_5_confirmation60_pack1_distance_20260506_154608/mechanism_60_20260506_154613`; outcome `0.5068`; canonical `0.7707`; protocol gate `True`.
- Pack vs best3 outcome delta `+0.0796`; canonical delta `-0.0170`; exact successes `10 -> 10`.
- `format_calculated_distance_km` visible/called/VNC `8 / 7 / 1`; called-subset outcome vs best3 `+0.1429`; called-subset outcome vs control `+0.0000`.
- Runtime/helper side-effect incidents `0 / 0`.
- Gap reduction proxy `19.44%`.
- Decision label: `expanded portfolio ready for 100`.
- Next action: run frozen100 with best3 vs Candidate Pack 1 before any frozen250.

## V2.5 Candidate Pack 1 Frozen100 - 2026-05-06 17:08
- Frozen best3 registry unchanged.
- Manifest: `artifacts/summaries/v2_5_gap_closure_100_pack1_distance/cohort_manifest.json`; quality `pass`; external-service contamination explicitly allowed because this was a distance/location-service candidate validation; no low-quality override used.
- Best3 run: `outputs/v2_5_gap_closure_100_best3_20260506_161059/validate_100_20260506_161104`; outcome `0.5181`; canonical `0.7902`; exact `20`.
- Pack run: `outputs/v2_5_gap_closure_100_distance_20260506_164021/validate_100_20260506_164026`; outcome `0.5120`; canonical `0.7844`; exact `18`.
- Pack vs best3 outcome delta `-0.0061`; canonical delta `-0.0059`.
- `format_calculated_distance_km` visible/called/VNC `16 / 7 / 9`; called-subset outcome vs best3 `+0.1429`; helper side-effect/runtime `0 / 0`.
- Gap reduction proxy `10.94%` met, but outcome/exact guardrail failed; no frozen250 for this pack.
- Decision label: `continue gap-closure loop`.
- Next action: rebuild gap atlas and test a materially different candidate pack; distance remains useful-but-not-promoted.

## V2.5 Candidate Pack 2 Contact Lookup - 2026-05-06
- Protected frozen best3 registry remains unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Candidate pack registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`, SHA-256 `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`.
- Candidate tools: `plan_contact_lookup_query`, `extract_contact_field_from_search_result` plus best3.
- Framework repairs enabling fair testing: generated-helper signature ordering, pre-search contact lookup actor policy, answer-retention final-response repair, contact-helper task-strata accounting.
- Tests: targeted suite `153 passed`; candidate registry check-only PASS with 5 active entries.
- Frozen100-style manifest: `artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json`; quality pass; best3 no-current-helper-fit `48%`, pack `24%`.
- Frozen100-style best3 run: `outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940/validate_100_20260506_200945`; outcome `0.6235`; canonical `0.8449`; exact successes `43`.
- Frozen100-style pack run: `outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903/validate_100_20260506_202908`; outcome `0.6490`; canonical `0.8474`; exact successes `48`.
- Direct 100 pack-vs-best3: outcome `+0.0255`; canonical `+0.0025`; exact `43 -> 48`; contact subset `+0.1527`; runtime/side-effect `0 / 0`.
- Broad250 manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`; quality pass; largest family share `0.032`.
- Broad250 best3 run: `outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037`; outcome `0.5626`; control `0.4070`; exact delta `+19`; protocol PASS; cache mixed `211 / 39`.
- Broad250 pack run: `outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840`; outcome `0.5637`; control `0.4001`; exact delta `+27`; protocol PASS; cache `250 / 0`.
- Direct 250 pack-vs-best3: outcome `+0.0011`; canonical `+0.0156`; exact `68 -> 72`; gains/regressions/preserved `51 / 56 / 95`; runtime/side-effect `0 / 0`.
- Contact lookup 250 subset: best3 `0.5629`, pack `0.7796`, delta `+0.2167`; exact `8 -> 11`.
- Registry-aware 250 no-current-helper-fit: best3 `52.0%`, pack `46.0%`, relative reduction `11.54%`. This does not reach the original formal reference target of `<=40.0%`, so the campaign remains open.
- Degradation analysis: `docs/sage_protocol/v2_5_pack2_contact_lookup_degradation_report.md`; machine artifact `artifacts/summaries/v2_5_pack2_contact_degradation_analysis_250/analysis.json`.
- Decision label: `continue gap-closure loop`.
- Next action: keep Candidate Pack 2 as a validated contact-lookup lane, tighten routing to reduce cross-lane VNC/context interference, and mine another non-overlapping high-gap candidate lane before any final expanded-portfolio claim.

## V2.5 Contact Routing Repair - 2026-05-06
- Repair: explicit generated-tool contracts now block provisional birth-family exposure when positive triggers/applicable families do not match.
- Test added: `test_explicit_contact_lookup_contract_blocks_non_matching_all_tools`.
- Static route probe: `artifacts/summaries/v2_5_contact_routing_contract_repair/route_probe.json`.
- Diagnostic manifest: `artifacts/summaries/v2_5_contact_routing_repair20/cohort_manifest.json`; quality `pass`.
- Diagnostic run: `outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721`; dashboards opened at port `5669`.
- Metrics: outcome delta `+0.2699`; canonical delta `+0.0837`; exact delta `+3`; runtime `0`; protocol PASS; controls `20 cached / 0 fresh`.
- Planner visible/called/VNC/hidden: `6 / 5 / 1 / 14`; extractor `6 / 3 / 3 / 14`; new-helper side-effect/runtime `0 / 0`.
- Tests after repair: full targeted suite `154 passed`; registry check-only PASS.
- Decision label: `continue gap-closure loop`.
- Next action: rerun a broader candidate-pack validation with the routing repair, or combine this contact lane with another non-overlapping gap-lane candidate before another 250-scale proof attempt.

## V2.6 Unified Final Gap-Closure Status
- Date: `2026-05-07T01:05:00-04:00`
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- V2.6 feedback packets implemented and exported for formal100, formal250, formal500, formal1032, V2.5 broad250 best3/pack, V2.5 routing diagnostic20, and V2.6 contact rerun100 best3/pack.
- Feedback schema: `docs/sage_protocol/v2_6_feedback_packet_schema.md`.
- Feedback audit: `docs/sage_protocol/v2_6_feedback_sufficiency_audit.md`; decision `feedback sufficient for tool birth`.
- Feedback mode decision: `feedback mode B wins`; enriched structured packets are the default V2.6 birth context.
- Contact pack rerun100 after routing repair: best3 run `outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133`; pack run `outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045`.
- Contact rerun direct pack-vs-best3: overall outcome `-0.0178`, canonical `+0.0408`, exact `30 -> 29`; contact subset outcome `+0.0563`; gap share `48.0% -> 24.0%`; runtime/side-effect `0 / 0`.
- Contact pack decision: `contact pack retained`, but not sufficient alone for final frozen250 target.
- Cross-task packets: `artifacts/summaries/v2_6_cross_task_packets/latest_packets.json`; decision `cross-task packets ready`.
- Key blocker: remaining gap needs a second non-overlapping candidate; insufficient-information is high coverage but current helper-call designs are risky because helper calls can still be part of forbidden trajectories.
- Exact next action: score candidate designs from cross-task packets, favor `device_service_state_resolution_v2_6` or a materially narrowed external answer-ready resolver, then run callability-first micro20 before any additive60/100/250.

## V2.6 Matched Frozen250 Gap Closure - 2026-05-07
- Protected best3 registry remains unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded V2.6 candidate registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`.
- Expanded tools: frozen best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`, `plan_contact_search_from_scalar_constraint`.
- V2.6 frozen250 manifest: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`, SHA-256 `5019602d637362a03317ac4349b9b89a2a790ff69bd5a72203d8dad9516f60e6`.
- Best3 run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`; control cache mixed `190 cached / 60 fresh`; protocol PASS; dashboard and task-focus opened on port `5679`.
- Expanded run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`; control cache mixed `222 cached / 28 fresh`; protocol PASS; dashboard and task-focus opened on port `5680`.
- Interrupted partial expanded run not used: `outputs/v2_6_gap_closure_250_expanded/validate_250_20260507_032818`; restarted because cache planning initially used only `87 cached / 163 fresh`, while a settled task-level plan used `222 cached / 28 fresh`.
- Matched 250 result: expanded outcome `0.6235` vs best3 `0.6040`, delta `+0.0195`; canonical `0.8060` vs `0.7838`, delta `+0.0222`; exact successes `59 -> 59`; runtime exceptions `0`; helper side-effect incidents `0`.
- Matched no-current-helper-fit: best3 `55.2%`, expanded `45.6%`, relative reduction `17.39%`; this meets the matched-manifest 10% gap-closure target.
- Caveat: the original formal250 absolute reference target was `44.4% -> <=40.0%`; this gap-enriched frozen250 is not directly comparable, so the direct absolute `<=40.0%` claim is not made from this run.
- Helper contribution on expanded frozen250: `plan_contact_lookup_query` visible/called/VNC `24 / 15 / 9`, called outcome `+0.6527`; `extract_contact_field_from_search_result` `24 / 7 / 17`, called outcome `+0.6904`; `plan_contact_search_from_scalar_constraint` `74 / 12 / 62`, called outcome `+0.4279`; all new helpers side-effect/runtime `0 / 0`.
- Decision label: `gap closure target met` for matched gap-enriched frozen250.
- Exact next action: lock V2.6 matched-gap evidence in final package; if making a broader formal claim, run an original-formal-manifest 250 or 500/1032 expanded validation with the same frozen registry.


## V2.6 Evidence Lock And Broader Expanded Validation
- Date: `2026-05-07`
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded V2.6 registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`.
- Expanded tools: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`, `plan_contact_search_from_scalar_constraint`.
- Matched gap-enriched frozen250 evidence locked: `docs/sage_protocol/v2_6_matched_gap_evidence_lock_report.md`; outcome `0.6040 -> 0.6235`; no-current-helper-fit `55.2% -> 45.6%`; relative gap reduction `17.39%`; runtime/side-effect `0 / 0`; protocol PASS.
- Contact-scalar routing audit: `docs/sage_protocol/v2_6_contact_scalar_routing_audit.md`; generic family-match repair reduced scalar planner overexposure without tool-name suppression; decision `routing repaired for original250`.
- Original formal250 expanded clean rerun: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209`; dashboards opened on port `5682`; control cache `250 cached / 0 fresh`; outcome `0.5986`; expanded vs preserved best3 outcome `+0.1249`; exact `40 -> 41`; feedback no-current-helper-fit `52.0% -> 46.0%`; runtime/side-effect `0 / 0`; protocol PASS.
- Expanded 500 run: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922`; dashboards opened on port `5683`; control cache mixed `179 cached / 321 fresh`; outcome `0.6822`; expanded vs preserved best3 500 outcome `+0.1299`; exact `76 -> 96`; feedback no-current-helper-fit `67.6% -> 62.8%`; runtime/side-effect `0 / 0`; protocol PASS.
- Final package updated under `artifacts/final_sage_praxis_package/`; final claim separates frozen best3 broad evidence from V2.6 matched gap-closure and expanded scale-positive evidence.
- 1032 expanded run deferred: 500 provides broad non-external scale evidence, while 1032 would add substantial live-candidate cost over sparse/external lanes not targeted by contact-scalar helpers.
- Decision: `expanded portfolio scale-positive; best3 broad claim preserved`.
- Next action: optional current-code best3 500 rerun or expanded 1032 only if publication scope requires stronger matched-code comparison; otherwise preserve current final package.

## V2.6 Current-Code Matched Evidence Campaign - 2026-05-07
- Commit: `f7aaffa5c02cff26a355dfcb4a540e33b91fde7d`; branch `sage/init-toolsandbox`.
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded V2.6 registry unchanged: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`.
- Preflight: registry check PASS; targeted tests `125 passed, 2 warnings`; `git diff --check` PASS; generation OFF for all current-code matched arms.
- Original250 current-code best3 run: `outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235`; dashboards opened/checked on port `5684`; control cache mixed `209 cached / 41 fresh`; outcome `0.6078`; canonical `0.7679`; exact `48`; protocol PASS.
- Original250 current-code expanded run: `outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441`; dashboards opened/checked on port `5685`; control cache `250 cached / 0 fresh`; outcome `0.6179`; canonical `0.7395`; exact `40`; protocol PASS.
- Original250 direct expanded-vs-best3: outcome `+0.0100`; canonical `-0.0283`; exact `48 -> 40`; no-current-helper-fit `52.0% -> 46.0%`, relative reduction `11.54%`; runtime/side-effect `0 / 0`.
- Non-external500 current-code best3 run: `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553`; dashboards opened/checked on port `5686`; control cache mixed `435 cached / 65 fresh`; outcome `0.6590`; canonical `0.7137`; exact `92`; protocol PASS.
- Non-external500 current-code expanded run: `outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427`; dashboards opened/checked on port `5687`; control cache mixed `467 cached / 33 fresh`; outcome `0.6692`; canonical `0.7362`; exact `93`; protocol PASS.
- Non-external500 direct expanded-vs-best3: outcome `+0.0101`; canonical `+0.0225`; exact `92 -> 93`; no-current-helper-fit `67.6% -> 62.8%`, relative reduction `7.10%`; runtime/side-effect `0 / 0`.
- 500 interpretation: expanded V2.6 is current-code positive and safe, but helper-fit reduction does not meet the 10% broad 500 target. The gap not closed at 500 is mainly sample/coverage: the 500 manifest includes 54 base families, 190 reminder-token tasks, 119 insufficient-information-token tasks, and many no-fit lanes outside contact-scalar scope.
- Reports added: `docs/sage_protocol/v2_6_current_code_original250_matched_report.md`, `docs/sage_protocol/v2_6_current_code_500_matched_report.md`, `docs/sage_protocol/v2_6_current_code_evidence_synthesis.md`.
- Final docs updated to preserve best3 as broad claim and present V2.6 as safe, current-code-positive, gap-improving but variance-limited.
- Decision label: `expanded portfolio non-harmful but variance-limited; best3 broad claim preserved`.
- Next action: if continuing research, target non-contact no-fit lanes instead of over-tuning the contact-scalar pack.
