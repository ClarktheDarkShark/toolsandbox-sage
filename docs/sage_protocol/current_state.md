# Current State

- Date: 2026-05-04
- Last completed step: `formal_250_best3_relative_validation`
- Last decision: `formal 250 passed`
- Primary metric: outcome/task-completion
- Active frozen helpers: `relative_day_time_to_timestamp, resolve_search_window_or_bounds, select_record_by_timestamp_extreme`
- Active registry: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
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
