# Run Ledger

## 2026-05-28

- `tau3 final-attempt framework repair probes` completed.
  - Branch: `codex/sage-standalone-agent`.
  - Objective: close the tau3 gap using general SAGE framework repairs while preserving the ToolSandbox-proven premise: generated Python helpers must be real callable tools, not prompt-only guidance, and success must be attributable to helper use/bridge behavior rather than stochastic LLM variance.
  - Repairs implemented: confirmation-aware action bridge across recent user turns; safe direct execution of generated read-only lookup actions; helper-output leakage prevention so SAGE helper outputs cannot be re-mined as visible record IDs; stricter transfer/escalation and policy-helper routing; router abstention when no helper has a positive contextual match.
  - Validation: `PYTHONPATH=src python -m py_compile src/sage_agent/import_agent.py src/sage_agent/generators.py scripts/run_tau3_sageagent_parity.py`; `PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q` passed `80` tests.
  - Probes stopped early by monitor:
    - `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v12_state_replay_policy_lookup_20260528_01`: stopped at 4 tasks, baseline `3`, SAGE `1`.
    - `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v15_safe_direct_lookup_20260528_01`: stopped at 7 tasks, baseline `6`, SAGE `5`, generated-helper calls `30`, direct helper actions `2`.
    - `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v16_routing_safe_direct_20260528_01`: stopped at 4 tasks, baseline `3`, SAGE `2`, generated-helper calls `18`.
    - `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v17_positive_route_floor_20260528_01`: stopped at 3 tasks, baseline `2`, SAGE `1`.
    - `outputs/sage_official_live/tau3_sageagent_manual_prototype20_v1_20260528_01`: manual-helper ablation stopped at 4 tasks, baseline `3`, SAGE `3`, one gain and one regression.
  - Best complete recent tau3 run remains `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v4_bounded_20260528_01`, baseline `8/20`, SAGE `9/20`, three gains and two regressions; not scale-ready.
  - Decision label: `TAU3_NOT_SCALE_READY: HOST_OWNED_DIALOGUE_HELPER_EXPOSURE_STILL_TOO_NOISY`.
  - Report: `docs/sage_protocol/tau3_final_attempt_framework_report_20260528.md`.

## 2026-05-25

- `tau3 SAGEAgent callable-helper parity repair` partially completed.
  - Branch: `codex/sage-standalone-agent`.
  - Objective: revisit the high-lift ToolSandbox v70/v71 mechanism and apply the same callable generated-helper lifecycle to tau3, rather than prompt-only import guidance.
  - ToolSandbox reference mechanism: empty generated registry; self-evolving Praxis preset; just-in-time helper birth; same-task fair retry; medium-grain helper families; generated helpers exposed as callable tools; bounded routing; cached controls; fresh SAGE; no force-calls.
  - tau3 root cause: prompt-only import mode was not equivalent to ToolSandbox SAGE. It produced broad policy/planning helpers and did not reliably execute generated Python helpers as first-class tools before official host actions.
  - General repairs: added medium-grain visible host-action subtype mining; prioritized concrete callable helpers over broad policy helpers; inserted concrete helper outputs into the post-helper host action prompt; sanitized mixed helper/host tool-call turns; allowed generated helper wrappers to accept structured keyword arguments; bounded per-task birth/retry budgets; made OpenAI generation/refinement timeout-safe; and made tau3 baseline cache seeds task-identity based rather than subset-position based.
  - tau3 fresh aggregate evidence before the final adapter-safety patch: `outputs/sage_official_live/tau3_sageagent_duplicate_guard_first40_20260525`, official tau3 airline baseline `12/40`, SAGE `18/40`, gains `7`, regressions `1`, tools born/accepted `14/14`, helper reuses `347`, integrity issues `0`.
  - tau3 seeded adapter diagnostic after the patch: `outputs/sage_official_live/tau3_sageagent_seeded_error_replay_cachefixed_norefine_25_44_20260525`, cached controls `2/2`, mature generated registry reused `27` helper calls, runner/message-shape/argument-wrapper errors `0`; task outcome `0/2`, so this is adapter-safety evidence only, not value evidence.
  - ToolSandbox maintenance verification after Python 3.9 cache fix: `outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy_py39fix2_20260525/mechanism_40_20260525_145447`, controls `20 cached / 0 fresh`, fresh SAGE score `0.728002 -> 0.868634`, outcome `0.454649 -> 0.887500`, accepted helpers `12`, natural generated-tool-called scenarios `10`, generated-tool failures `0`, runtime exceptions `0`, protocol gate `PASS`.
  - Post-priority diagnostic: `outputs/sage_official_live/tau3_sageagent_bounded_concrete_first20_20260525`, controls `20 cached / 0 fresh`, official tau3 airline SAGE `8/20` versus baseline `8/20`, gains `2`, regressions `2`, tools born/accepted/reused `16/15/243`, integrity issues `0`. This confirmed concrete helper birth/reuse but showed that task-success-only helper accounting overvalued helpers that merely preserved baseline successes.
  - Additional general repair: helper registry records now track paired `contribution_gains` and `contribution_regressions` when a matched baseline outcome is available; routing penalizes repeated paired regressions and rewards actual paired gains. Contribution counts are per helper per task, not per repeated helper call. This is dataset-neutral and applies to import-mode and adapter-owned SAGEAgent paths.
  - Decision label: `TOOLSANDBOX_HIGH_LIFT_MECHANISM_MAINTAINED; TAU3_CALLABLE_HELPER_PARITY_PRESENT; TAU3_VALUE_CALIBRATION_NEEDS_FRESH_40_TASK_RERUN_WITH_CONTRIBUTION_AWARE_ROUTING`.

## 2026-05-20

- `Standalone ToolSandbox self-evolving policy backtrace verify20` completed.
  - Branch: `codex/sage-standalone-agent`.
  - Objective: find why the standalone ToolSandbox verify20 run regressed while prior self-evolving broad500 runs had high lift, then recover the working mechanics without manually exposing tools.
  - Root cause: failed run `outputs/sage_agent_standalone/toolsandbox_real_verify20/mechanism_40_20260520_204549` used generic generation only. It did not enable the self-evolving Praxis runtime stack from v70/v71: just-in-time proactive birth, same-task fair chance, safe-abstain birth, combined Praxis actor bridge policy, transient retries, V2 contract/repair/dependency/medium-grain generation features, and task-level control-cache matching.
  - Code repair: `scripts/run_sage_protocol.py` now exposes `--sage-policy self-evolving-praxis`. The preset applies the high-lift defaults and records each value/source in `protocol_manifest.json`; explicit environment overrides are preserved.
  - Validation run: `outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy/mechanism_40_20260520_210531`.
  - Dashboard: `http://127.0.0.1:62630/outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy/mechanism_40_20260520_210531/dashboard/task_compare.html`.
  - Controls: `20 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; SAGE/candidate task cache off; OpenAI response cache disabled; routing evidence disabled.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Metrics: canonical/reference `0.728002 -> 0.908119`, delta `+0.180117`; outcome `0.454649 -> 0.920139`, delta `+0.465490`; exact successes `3 -> 16`.
  - Gains/regressions: canonical `14 / 2`; outcome `14 / 1`.
  - Generated helpers: `12` accepted from an empty generated-tool registry; `8` naturally called.
  - Safety: runtime exceptions `0`; helper side-effect preservation reports `0`; protocol gate `PASS`.
  - Machine summary: `artifacts/sage_standalone/toolsandbox_self_evolving_policy_backtrace_summary.json`, SHA-256 `3bc290fa823fb832ee024466147633e7b5b4f771143a081bbb275042db6fd112`.
  - Decision label: `ROOT_CAUSE_CONFIRMED_POLICY_PRESET_RESTORES_TOOLSANDBOX_LIFT_ON_CACHED_VERIFY20`.

## 2026-05-15

- `Self-evolving broad500 clean committed-tree reproduction v71` completed.
  - Branch: `codex/self-evolving-sage-mini60`.
  - Objective: reproduce the high-lift v70 self-evolving broad500 result from a clean committed runtime tree while starting from no generated helpers, keeping generation on, using cached controls, and letting SAGE choose births, retention, routing, and natural calls.
  - Launch git SHA: `53c1b4c21c60c85a96b11da1832341b42e8f8ad5`; working tree was clean at launch except for run-generated artifacts that were absent before execution.
  - Run: `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`.
  - Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356/dashboard/task_compare.html`.
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v71_clean_repro_summary.json`, SHA-256 `1b5bd2d162e9202bf63491935a1eae5d8f207b73aec2b4dcf498deb0f8b935db`.
  - Manifest: `artifacts/self_evolving_sage/current_formal500_live_generation_v54_outcome_bridge_repair/self_evolving_formal500_online_build_manifest.json`, SHA-256 `93f5597b09b7073fe718abd1aa8b416d3e8b440054c275031f8727809e39f08b`.
  - Registry: `artifacts/self_evolving_sage/current_formal500_live_generation_v71_clean_repro/formal500_registry/registry_manifest.json`, SHA-256 `6d48dd788b9d3d788710f0e7c17755aa481618fc76ac281c5feddea22d747f23`.
  - Starting registry: absent/empty generated registry; `manifest_existed_before_run=false`.
  - Controls: `500 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; control cache match policy `experimental_task_name_base_tool_policy_min3_model_user_bypassed`; SAGE/candidate task cache off; OpenAI response cache disabled; routing evidence disabled.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Runtime policy: `SAGE_PRAXIS_BRIDGE_POLICY=combined`; `SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time`; `SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=1`; frozen ToolSandbox clock; bounded transient scenario retry enabled with `SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS=4`; no diagnostic force-call env vars.
  - Metrics: canonical/reference `0.656799 -> 0.854188`, delta `+0.197389`, relative lift `+30.05%`; outcome `0.494746 -> 0.880845`, delta `+0.386099`, relative lift `+78.04%`; exact successes `20 -> 288`, delta `+268`.
  - Gains/regressions/preserved: canonical `395 / 48 / 57`; outcome `325 / 27 / 32`.
  - Generated helpers: `16` accepted from an empty starting registry; `14` naturally called; generated-tool visible/called/failed scenarios `453 / 297 / 0`; accepted-but-uncalled `constraint_to_action_planner`, `prepare_side_effect_args_from_selected_record`.
  - Safety: runtime exceptions `0`; generated-tool failures `0`; protocol gate `PASS`; route mismatch qualified `false`; helper side-effect preservation failures `1`.
  - Side-effect caveat: the single preservation failure was `select_action_target_by_recency` on the read-only `search_reminder_with_recency_yesterday_all_tools` task. The helper returned a hypothetical `remove_reminder` next action, but the actor did not call `remove_reminder`; no ToolSandbox state mutation occurred. This is classified as a helper-contract preservation near miss, not an actual side-effect incident.
  - Validation: registry check passed for all 16 active entries; dashboard HTML/JSON returned HTTP 200; protocol/cache assertions passed; `git diff --check` passed.
  - Decision label: `SELF_EVOLVING_BROAD500_METRICS_REPRODUCED_WITH_ONE_HELPER_CONTRACT_CAVEAT`.
  - Next action: repair read-only recency selection so action-target helpers either expose an answer-only mode or are hidden from read-only search tasks, then run targeted safety diagnostics before another clean broad500 if strict zero preservation failures are required.

## 2026-05-13

- `Self-evolving broad500 JIT same-task birth and retry repair` completed.
  - Branch: `codex/self-evolving-sage-mini60`.
  - Objective: restore and exceed the v50-level lift on the full broad500 while starting from no generated tools, keeping generation on, and letting SAGE choose births, retention, and routing. Also test the same-task JIT birth repair: a helper born from a task can be visible to that same task after validation, without force-calling it.
  - Run: `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`.
  - Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839/dashboard/task_compare.html`.
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v70_jit_birth_retry_repair_summary.json`, SHA-256 `1bfe8462066250de935f41110b0a112327ea60e3bb65d22dd5cf6e6b6e71a925`.
  - Registry: `artifacts/self_evolving_sage/current_formal500_live_generation_v70_jit_birth_retry_repair/formal500_registry/registry_manifest.json`, SHA-256 `ab932e9ca4448f1732299614866b74bc1217b81e7bb89fe1de35f41bb68c1a7b`.
  - Starting registry: absent/empty generated registry; `manifest_existed_before_run=false`.
  - Controls: `500 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; SAGE/candidate task cache off; OpenAI response cache disabled; routing evidence disabled.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Runtime policy: `SAGE_PRAXIS_BRIDGE_POLICY=combined`; `SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time`; `SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=1`; frozen ToolSandbox clock; bounded transient scenario retry enabled with `SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS=4`.
  - Metrics: canonical/reference `0.656799 -> 0.827506`, delta `+0.170706`, relative lift `+25.99%`; outcome `0.494746 -> 0.872782`, delta `+0.378036`, relative lift `+76.41%`; exact successes `20 -> 287`, delta `+267`.
  - Gains/regressions/preserved: canonical `371 / 71 / 58`; outcome `316 / 35 / 33`.
  - Generated helpers: `16` accepted from an empty starting registry; `14` naturally called; generated-tool visible/called/failed scenarios `453 / 295 / 0`; accepted-but-uncalled `constraint_to_action_planner`, `prepare_side_effect_args_from_selected_record`; same-task JIT availability events `11`.
  - Strong called helpers: `resolve_search_window_or_bounds` called `82` times with called-subset outcome delta `+0.582731`; `plan_device_state_action_sequence_v3` called `87` times with outcome delta `+0.126595`; `plan_contact_lookup_query` called `24` times with outcome delta `+0.546369`; `select_message_content_by_recency` called `20` times with outcome delta `+0.740473`.
  - Safety: runtime exceptions `0`; transient retries `0`; generated-tool failures `0`; helper side-effect preservation reports `0`; protocol gate `PASS`; route mismatch qualified `false`.
  - Reproducibility caveat: the harness recorded git SHA `d27fa6b96bd99b0a429ea8c5b2b92f80ae26ff18` because the run began before committing the same-task birth and transient-retry edits. The run-affecting working-tree diff SHA-256 is `87c290674cbd95af301a9030b0714ec60673374677279daf9742ea9a5f422f1a`; this commit records those changes.
  - Decision label: `SELF_EVOLVING_BROAD500_BEATS_CURRENT_BEST_LIST_WITH_EMPTY_REGISTRY_LIVE_BIRTH`.
  - Next action: reproduce once from a clean committed tree before treating this as locked final claim evidence. For methodology drafting, describe it as high-confidence experimental self-evolving evidence.

- `Self-evolving autonomous bucket route repair contact60` completed.
  - Branch: `codex/self-evolving-sage-mini60`.
  - Objective: perform one more improvement round using autonomous bucket targeting and repair, without manually exposing tools, and beat the current self-evolving lift list values before spending another broad500 run.
  - Repair mechanism: broad generated negative triggers no longer hide a helper when the same helper has a more specific positive matching task family, e.g. `remove_contact` no longer blocks a `remove_contact_by_phone` contact lookup planner. Minefield negatives such as `insufficient_information`, `missing`, and `ambiguous` remain hard blockers. Send-message policy now blocks guessed phone-number side effects when no phone number or visible contact lookup path exists.
  - Preparation: `artifacts/self_evolving_sage/current_formal500_live_generation_v50_auto_bucket_contact60_route_repair/self_evolving_mini60_preparation.json`.
  - Manifest: `artifacts/self_evolving_sage/current_formal500_live_generation_v50_auto_bucket_contact60_route_repair/self_evolving_mini60_manifest.json`, SHA-256 `e852ab5f31b763ada8ad3924ee2ea07554feff3179f9c89ad331aab9d09fccaf`.
  - Selected bucket: `contact_lookup_update_search_crud`; selected by the system from formal/broad gap packets; labels not inspected; no manual tool exposure list.
  - Run: `outputs/self_evolving_sage/live_generation_v50_auto_bucket_contact60_route_repair/mechanism_60_20260513_105138`.
  - Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/live_generation_v50_auto_bucket_contact60_route_repair/mechanism_60_20260513_105138/dashboard/task_compare.html`.
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v50_auto_bucket_contact60_route_repair_summary.json`, SHA-256 `1c5775fa3a038242721091fc809f575d17cd7dcfa2db2902c459ada482cf8b3e`.
  - Controls: `60 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; SAGE/candidate task cache off; OpenAI response cache disabled; routing evidence disabled.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Metrics: canonical/reference `0.740335 -> 0.911396`, delta `+0.171061`, relative lift `+23.11%`; outcome `0.437475 -> 0.758516`, delta `+0.321042`, relative lift `+73.39%`.
  - Gains/regressions/preserved: canonical `46 / 10 / 4`; outcome `36 / 9 / 0`.
  - Generated helpers: `8` accepted from an empty starting registry; `7` naturally called; generated-tool called scenarios `32`; generated-tool failures `2`, both nonfatal planner attempts; accepted-but-uncalled `prepare_side_effect_args_from_selected_record`.
  - Safety: runtime exceptions `0`; helper side-effect incidents `0`; runtime incidents `0`; protocol gate `PASS`.
  - Comparison to current list values: targeted contact60 score lift `+23.11%` exceeds self-evolving broad250 `+16.46%`, self-evolving broad500 `+12.31%`, and fixed Praxis formal500 `+13.04%`; outcome delta `+0.321042` exceeds the fixed Praxis formal500 outcome delta `+0.245071` and self-evolving broad500 outcome delta `+0.205052` on this selected bucket.
  - Decision label: `SELF_EVOLVING_AUTONOMOUS_BUCKET_REPAIR_BEATS_CURRENT_LIFT_LIST_ON_TARGETED_CONTACT_BUCKET`.
  - Next action: do not immediately spend a broad500. Run one 100/250 broad checkpoint only after the same autonomous bucket-selection/repair logic is committed and the next residual bucket is selected by the system, not by a hand-authored exposure list.

- `Self-evolving SAGE empty-registry broad250 and broad500 scale validation` completed.
  - Branch: `codex/self-evolving-sage-mini60`
  - Strategy: start from no accepted generated helpers, keep generation on, let the SAGE lifecycle/router decide helper birth, validation, retention, route repair, and visibility from natural run feedback. No force calls counted as evidence.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Runtime policy: `SAGE_PRAXIS_BRIDGE_POLICY=combined`, routing evidence `disabled`, candidate task cache `off`, OpenAI response cache `disabled`, control cache `strict`.
  - Broad250 run: `outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851`
  - Broad250 dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851/dashboard/task_compare.html`
  - Broad250 summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v37_broad250_system_lifecycle_keyfixed_summary.json`, SHA-256 `3f6aa9c7786fae16b16bc241d19ab5ff068a4c9bf89d77efba83ebc90a18a596`
  - Broad250 controls: `250 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; cohort selection influenced by cache: `false`.
  - Broad250 metrics: canonical/reference `0.669502 -> 0.779703`, delta `+0.110201`, relative lift `+16.46%`; outcome `0.509662 -> 0.685953`, delta `+0.176291`, relative lift `+34.59%`; exact successes `9 -> 91`; score gains/regressions/preserved `168 / 48 / 34`; outcome gains/regressions/preserved `120 / 47 / 23`; runtime exceptions `0`; helper side-effect incidents `0`; protocol gate `PASS`.
  - Broad250 generated helpers: accepted `15`; newly generated and naturally called `14`; accepted-but-uncalled `prepare_side_effect_args_from_selected_record`.
  - Broad500 run: `outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654`
  - Broad500 dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654/dashboard/task_compare.html`
  - Broad500 summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v38_broad500_system_lifecycle_keyfixed_summary.json`, SHA-256 `794414a8f7399c26d19daca4086778a637d2ed37ece72c7aa510e3f2bff83f94`
  - Broad500 residual gap profile: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v38_broad500_residual_gap_profile.json`, SHA-256 `5cd5bec795a947eb8d40bf47aab5fc484a76d1ca90cc66323f7330aa7c3a3aba`
  - Broad500 controls: `500 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; cohort selection influenced by cache: `false`.
  - Broad500 metrics: canonical/reference `0.657730 -> 0.738692`, delta `+0.080962`, relative lift `+12.31%`; outcome `0.495416 -> 0.700468`, delta `+0.205052`, relative lift `+41.39%`; exact success delta `+80`; score gains/regressions/preserved `318 / 114 / 68`; outcome gains/regressions/preserved `243 / 87 / 54`; runtime exceptions `0`; helper side-effect incidents `0`; protocol gate `PASS`.
  - Broad500 generated helpers: accepted `16`; newly generated and naturally called `15`; accepted-but-uncalled `prepare_side_effect_args_from_selected_record`. Top natural calls: `resolve_search_window_or_bounds` `70`, `plan_device_state_action_sequence_v3` `59`, `prepare_reminder_creation_args` `22`, `plan_contact_lookup_query` `19`, `select_message_content_by_recency` `15`.
  - Caveat and repair: Broad500 resumed after an OpenAI transport hang. The completed paired result is valid, but the self-evolution reflection/lifecycle state did not hydrate fully across the resume boundary. A tested runtime repair now hydrates cumulative lifecycle state from copied `self_evolution_task_feedback.jsonl` on resumed runs.
  - Transport repair: OpenAI ToolSandbox role clients and adapter clients now use bounded request timeouts via `SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS` to prevent unbounded socket hangs during long candidate arms.
  - Decision: `SELF_EVOLVING_SCALE_POSITIVE_WITH_RESUME_CAVEAT`; next action is a no-resume or resume-hydrated 100/250 confirmation before spending another broad500 run, then a broad500 rerun only if the checkpoint matches or exceeds the fixed Praxis trajectory.

## 2026-05-12

- `Self-evolving SAGE empty-registry live-generation 60` completed.
  - Branch: `codex/self-evolving-sage-mini60`
  - Report: `docs/sage_protocol/self_evolving_sage_mini60_report.md`
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v21_60_summary.json`
  - Summary SHA-256: `828ea32146a778f1b5b371bc837a683594967d1744ab7dce4bf9f285b1125de0`
  - Preparation: `artifacts/self_evolving_sage/current_mini60_live_generation_v21_60_safe_remove_bridge/self_evolving_mini60_preparation.json`
  - Preparation SHA-256: `db48663860cbddbf104feffb2158457b16e33ac6d63c00ae2ffb3a0b26eff5f9`
  - Manifest: `artifacts/self_evolving_sage/current_mini60_live_generation_v21_60_safe_remove_bridge/self_evolving_mini60_manifest.json`
  - Manifest SHA-256: `6038613ee3b254a4c6b2b1219feee39c9d8ac98052d9857b39f67cb06e577ced`
  - Starting registry: `artifacts/self_evolving_sage/current_mini60_live_generation_v21_60_safe_remove_bridge/registry/registry_manifest.json`
  - Starting registry SHA-256: `61468467448a94c5c6ced36d05894d7ba2e2f7501ca84270a30da1cd18a3c713`
  - Final generated registry SHA-256: `9e887a9199f53b5b1f28d7d76b158a2de6a397b617c1af8bb39932ac7bff6d0d`
  - Positive run: `outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507`
  - Dashboard: `http://127.0.0.1:62624/outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507/dashboard/task_compare.html`
  - Dashboard default/open policy: `task_compare.html` is the default run dashboard and is opened through macOS `open` in the external browser unless `--no-dashboard-open` is set.
  - Source plan: `docs/sage_protocol/praxis_next_gap_and_self_evolving_sage_plan.md`
  - Strategy: start from an empty generated-tool registry, keep generation on, generate tools online from gap observations, validate accepted tools, and use natural routing/calling without force calls.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Sample cap: `60`; matched contact scenarios: `60`.
  - Control cache: `use-if-eligible`, `60 cached / 0 fresh`, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`; cohort selection influenced by cache: `false`.
  - Candidate task cache: `off`; OpenAI response cache: `disabled`; routing evidence: `disabled`; diagnostic force env vars: none.
  - Generation: `on`.
  - Accepted live-born tools: `plan_contact_lookup_query`, `plan_contact_relationship_batch_update`, `plan_contact_update_from_id`, `prepare_side_effect_args_from_selected_record`, `select_action_target_by_recency`, `select_record_by_timestamp_extreme`.
  - Natural call evidence: `18` generated-tool called scenarios, `0` generated-tool failed scenarios.
  - Strongest tools: `plan_contact_lookup_query` called `8` times with called-subset outcome delta `+0.473296`; `plan_contact_relationship_batch_update` called `8` times with called-subset outcome delta `+0.436380`; `plan_contact_update_from_id` called `2` times with called-subset outcome delta `+0.166667`.
  - Canonical/reference score: `0.755622 -> 0.855260`, delta `+0.099638`, relative lift `+13.19%`.
  - Outcome score: `0.523942 -> 0.667092`, delta `+0.143150`.
  - Exact successes: `10 -> 26`, delta `+16`.
  - Runtime exceptions: `0`.
  - Helper side-effect incidents: `0`.
  - Protocol gate: `PASS`.
  - Treatment caveat: includes documented combined bridge-policy safe-abstention repair for remove-by-phone requests when `search_contacts` is unavailable; this is experimental implementation evidence, not protected final-claim evidence.
  - Decision: `SELF_EVOLVING_LIVE_GENERATION_60_POSITIVE_EXPERIMENTAL`; prepare broader matched validation after treatment definition is frozen.

## 2026-05-11

- `Self-evolving SAGE empty-registry live-generation diag24` completed.
  - Branch: `codex/self-evolving-sage-mini60`
  - Report: `docs/sage_protocol/self_evolving_sage_mini60_report.md`
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_live_generation_diag24_summary.json`
  - Summary SHA-256: `1807c4fb597199130acfe1861360591e1abbc315de79ec90e35c98778fa14d89`
  - Preparation: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_preparation.json`
  - Manifest: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_manifest.json`
  - Manifest SHA-256: `5337bf7bef2cb32679955bcf27b68cf06495d00c905a02c66766ae261b0176bc`
  - Starting registry: `artifacts/self_evolving_sage/current_mini60_live_generation_v2/registry/registry_manifest.json`
  - Starting registry SHA-256: `61468467448a94c5c6ced36d05894d7ba2e2f7501ca84270a30da1cd18a3c713`
  - Positive run: `outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431`
  - Dashboard: `http://127.0.0.1:62628/outputs/self_evolving_sage/live_generation_v6_diag24/mechanism_60_20260511_225431/dashboard/task_compare.html`
  - Source plan: `docs/sage_protocol/praxis_next_gap_and_self_evolving_sage_plan.md`
  - Strategy: start from an empty generated-tool registry, keep generation on, generate tools online from gap observations, validate accepted tools, and use natural routing/calling without force calls.
  - Models: agent/user/generation all `gpt-4o-mini`.
  - Sample cap: `60`; matched contact scenarios: `24`.
  - Control cache: `use-if-eligible`, `24 cached / 0 fresh`, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
  - Candidate task cache: `off`; OpenAI response cache: `disabled`; routing evidence: `disabled`; diagnostic force env vars: none.
  - Generation: `on`.
  - Accepted live-born tools: `plan_contact_relationship_batch_update`, `plan_contact_update_from_id`, `prepare_side_effect_args_from_selected_record`.
  - Natural call evidence: `plan_contact_relationship_batch_update` visible/called/VNC `3 / 3 / 0`, called-subset outcome delta `+0.342197`.
  - Canonical/reference delta: `+0.040569`.
  - Outcome delta: `+0.047045`.
  - Exact success delta: `+6`.
  - Runtime exceptions: `0`.
  - Helper side-effect incidents: `0`.
  - Protocol gate: `PASS`.
  - Safe-abstention diagnostic: `prepare_safe_action_or_abstain` generated and callable, but parked by default after v9 called-subset canonical delta `-0.505454` and outcome delta `-0.030562`; diagnostic opt-in is `SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1`.
  - Decision: `SELF_EVOLVING_LIVE_GENERATION_MECHANISM_POSITIVE_BUT_NOT_SCALE_READY`; not protected final-claim evidence.

- `Self-evolving SAGE mini60 praxis-pack proof` completed.
  - Status: superseded as the live self-evolving proof because it used pre-existing Praxis recipe tools and generation was off during the run. Retained as a recipe-pack transfer diagnostic.
  - Branch: `codex/self-evolving-sage-mini60`
  - Report: `docs/sage_protocol/self_evolving_sage_mini60_report.md`
  - Summary: `artifacts/self_evolving_sage/summary/self_evolving_mini60_praxis_pack_v2_summary.json`
  - Run: `outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904`
  - Dashboard: `http://127.0.0.1:62618/outputs/self_evolving_sage/mini60_praxis_pack_v2/transfer_60_20260511_204904/dashboard/task_compare.html`
  - Source plan: `docs/sage_protocol/praxis_next_gap_and_self_evolving_sage_plan.md`
  - Strategy: start from an empty runtime registry, select the contact gap from the formal500 gap packet, and materialize the current validated Praxis recipe pack under the self-evolving controller.
  - Registry: `artifacts/self_evolving_sage/current_mini60_praxis_pack/registry/registry_manifest.json`
  - Registry SHA-256: `3ee0719ddc87a774fc18d48365c36e9dea7cce70f65f6f28574afd60ddc9e99c`
  - Manifest: `artifacts/self_evolving_sage/current_mini60_praxis_pack/self_evolving_mini60_manifest.json`
  - Manifest SHA-256: `e7278b67d682d3be59d764e59e73094548e7ea965ec25003bda8b6a41935a51a`
  - Models: agent/user/generation all `gpt-4o-mini`
  - Sample size: `60`
  - Control cache: `use-if-eligible`, `33 cached / 27 fresh`, cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
  - Candidate task cache: `off`; OpenAI response cache: `disabled`; routing evidence: `disabled`; diagnostic force env vars: none.
  - Canonical/reference delta: `+0.081539` (`0.763821 -> 0.845361`)
  - Outcome delta: `+0.118882` (`0.536539 -> 0.655421`)
  - Exact successes: `13 -> 22`
  - Generated-tool natural visibility/calls/failures: `36 / 23 / 0`
  - Runtime exceptions: `0`
  - Helper side-effect incidents: `0`
  - Protocol gate: `PASS`
  - Decision: `self_evolving_controller_proof_positive`; not protected final-claim evidence.

## 2026-05-02

- `Phase B` passed after calling-convention repair for `prepare_reminder_creation_args`.
- `Phase C.1 v2` passed for `select_record_by_timestamp_extreme`.
  - Registry: `artifacts/registry_phaseC_C1_candidate/registry_manifest.json`
  - Run: `outputs/phase_C1_record_selection_replay_v2/transfer_40_20260502_215943/`
  - Canonical delta: `+0.221`
  - Outcome delta: `+0.267`
  - Exact successes: `control=1`, `SAGE=5`
  - Visible/called: `6/6`
  - Visible-not-called: `0`
  - Side-effect violations: `0`
  - Runtime exceptions: `0`
  - Decision: `keep`
- `Phase C.2` passed for `resolve_search_window_or_bounds`.
  - Registry: `artifacts/registry_phaseC_C2_candidate_v2/registry_manifest.json`
  - Replay run: `outputs/phase_C2_search_window_replay_v2/transfer_40_20260502_223759/`
  - Focused cohort: `outputs/phase_C2_search_window_cohort/transfer_40_20260502_224132/`
  - Replay canonical delta: `+0.3889`
  - Replay outcome delta: `+0.4868`
  - Cohort canonical delta: `+0.1444`
  - Cohort outcome delta: `+0.1682`
  - Cohort exact successes: `control=4`, `SAGE=5`
  - Resolve helper visible/called on cohort: `12/8`
  - Resolve helper visible-not-called on cohort: `4`
  - Runtime exceptions: `0`
  - Side-effect violations: `0`
  - Decision: `pass`
- `Phase C.3` passed for narrowed `prepare_reminder_creation_args` after one repair.
  - Registry: `artifacts/registry_phaseC_C3_candidate_v2/registry_manifest.json`
  - Replay v1: `outputs/phase_C3_reminder_replay/transfer_40_20260502_230636/`
  - Cohort v1: `outputs/phase_C3_reminder_cohort/transfer_40_20260502_231031/`
  - Replay v2: `outputs/phase_C3_reminder_replay_v2/transfer_40_20260502_231813/`
  - Cohort v2: `outputs/phase_C3_reminder_cohort_v2/transfer_40_20260502_232138/`
  - Repaired replay canonical delta: `+0.1105`
  - Repaired replay outcome delta: `+0.1398`
  - Repaired cohort canonical delta: `+0.0970`
  - Repaired cohort outcome delta: `+0.0850`
  - Repaired cohort exact successes: `control=5`, `SAGE=6`
  - Reminder helper visible/called on repaired cohort: `7/7`
  - Reminder helper visible-not-called on repaired cohort: `0`
  - Runtime exceptions: `0`
  - Side-effect violations: `0`
  - Decision: `pass`

## 2026-05-03

- `Phase D` passed for the full 3-helper portfolio.
  - Full arm: `outputs/phase_D_full_v2/transfer_40_20260502_232844/`
  - Prepare only: `outputs/phase_D_prepare_only/transfer_40_20260502_234029/`
  - Select only: `outputs/phase_D_select_only/transfer_40_20260502_235136/`
  - Resolve only: `outputs/phase_D_resolve_only/transfer_40_20260503_000343/`
  - Without prepare: `outputs/phase_D_without_prepare/transfer_40_20260503_001553/`
  - Without select: `outputs/phase_D_without_select/transfer_40_20260503_003009/`
  - Without resolve: `outputs/phase_D_without_resolve/transfer_40_20260503_004302/`
  - Full canonical delta: `+0.1755`
  - Full outcome delta: `+0.1302`
  - Full exact successes: `control=2`, `SAGE=5`
  - Decision: `pass`
  - Phase E frozen registry: `artifacts/registry_phaseE_portfolio/registry_manifest.json`
- Next execution target: `Phase E — mixed pilot and formal 100`
- `Phase E mixed pilot` failed on the broad mixed cohort.
  - Full portfolio pilot: `outputs/phase_E_mixed_pilot/transfer_40_20260503_010141/`
  - Select-only corrective pilot: `outputs/phase_E_mixed_pilot_select_only/transfer_40_20260503_012615/`
  - Without-prepare corrective pilot: `outputs/phase_E_mixed_pilot_without_prepare/transfer_40_20260503_013711/`
  - Full pilot outcome delta: `-0.1928`
  - Select-only pilot outcome delta: `+0.0024` with `0` helper calls
  - Without-prepare pilot outcome delta: `+0.0151` with `0` helper calls
  - Formal 100 not started
  - Phase F not started
  - Decision: `needs one general repair`
- `Decisive-tool experiment20` completed.
  - Registry used for run: `artifacts/registry_phaseE_portfolio/registry_manifest.json`
  - Run root: `outputs/decisive_tool_experiment20/mechanism_40_20260503_060322/`
  - Canonical delta: `+0.1344`
  - Outcome delta: `+0.1935`
  - Exact successes: `control=1`, `SAGE=2`
  - Proposed / accepted / rejected births: `7 / 2 / 5`
  - Accepted births: `recency_to_timestamp_bounds`, `message_search_time_window`
  - Accepted birth calls: `0`
  - Retained helper calls: `resolve_search_window_or_bounds=6`, `select_record_by_timestamp_extreme=2`
  - Runtime exceptions: `0`
  - Decision: `needs one general gate repair`
  - Report: `docs/sage_protocol/decisive_tool_experiment20_report.md`
- `Decisive-tool experiment20_40_v2` completed after one gate repair.
  - 20 run: `outputs/decisive_tool_experiment20_v2/mechanism_40_20260503_083141/`
  - 40 run: `outputs/decisive_tool_experiment40_v2/mechanism_40_20260503_083555/`
  - 20 canonical delta: `+0.1770`
  - 20 outcome delta: `+0.1285`
  - 20 exact successes: `control=0`, `SAGE=2`
  - 20 births proposed / accepted / rejected: `8 / 1 / 7`
  - 40 canonical delta: `+0.1239`
  - 40 outcome delta: `+0.1830`
  - 40 exact successes: `control=1`, `SAGE=4`
  - 40 births proposed / accepted / rejected: `9 / 1 / 8`
  - Accepted birth in both runs: `message_search_time_window`
  - Accepted birth calls: `1` in 20, `1` in 40
  - Decision: `useful decisive-tool signal`
  - Report: `docs/sage_protocol/decisive_tool_experiment20_40_v2_report.md`

- `Autonomous loop generation_contract20_v3` completed.
  - Run: `outputs/autonomous_loop_generation_contract20_v3_resume/mechanism_40_20260503_095138/`
  - Report: `docs/sage_protocol/autonomous_loop_generation_contract20_v3_report.md`
  - Summary: `artifacts/summaries/autonomous_loop_generation_contract20_v3/summary.json`
  - Canonical delta: `+0.0804`
  - Outcome delta: `+0.1276`
  - Outcome relative lift: `31.03%`
  - Exact successes: `control=0`, `SAGE=1`
  - Births proposed / accepted / rejected: `3 / 1 / 2`
  - Accepted candidate: `next_service_tool_call`, parked in `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
  - Accepted candidate visible/called: `4 / 0`
  - Runtime exceptions: `0`
  - Decision: `continue routing repair`

- `Autonomous service routing diagnostic10` completed.
  - Run: `outputs/autonomous_service_routing_diagnostic10/mechanism_40_20260503_100727/`
  - Report: `docs/sage_protocol/autonomous_service_routing_diagnostic10_report.md`
  - Summary: `artifacts/summaries/autonomous_service_routing_diagnostic10/summary.json`
  - Generation: `off`
  - Candidate registry: `artifacts/registry_candidates/autonomous_loop_generation_contract20_v3_service_candidate/registry_manifest.json`
  - Canonical delta: `+0.0238`
  - Outcome delta: `+0.0081`
  - Exact successes: `control=0`, `SAGE=0`
  - `next_service_tool_call` visible/called: `6 / 5`
  - Service-positive outcome gains/regressions/preserved: `2 / 2 / 2`
  - Runtime exceptions: `0`
  - Decision: `continue validation repair`

- `Decisive-tool experiment20 broad rerun` completed.
  - Run: `outputs/decisive_tool_experiment20_broad_rerun/mechanism_40_20260503_102645/`
  - Report: `docs/sage_protocol/decisive_tool_experiment20_report.md`
  - Summary: `artifacts/summaries/decisive_tool_experiment20/summary.json`
  - Generation: `on`
  - Canonical delta: `+0.1036`
  - Outcome delta: `+0.0171`
  - Exact successes: `control=0`, `SAGE=2`
  - Births proposed / accepted / rejected: `4 / 1 / 3`
  - Accepted birth: `next_service_tool_call` diagnostic only; missing positive triggers and side-effect preservation failure
  - Helper calls: `{'next_service_tool_call': 1, 'resolve_search_window_or_bounds': 6, 'select_record_by_timestamp_extreme': 2}`
  - Runtime exceptions: `0`
  - Active registry restored to 3 claim-safe helpers
  - Decision: `needs one general gate repair`

- `Decisive-tool experiment20 gate-repair rerun` completed.
  - Main action: `discovery run`
  - Report: `docs/sage_protocol/decisive_tool_experiment20_gate_repair_rerun_report.md`
  - Summary: `artifacts/summaries/decisive_tool_experiment20_gate_repair_rerun/summary.json`
  - Run: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/`
  - Dashboard: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/dashboard/index.html`
  - Task focus dashboard: `outputs/decisive_tool_experiment20_gate_repair_rerun/mechanism_40_20260503_103917/dashboard/task_focus.html`
  - Generation: `on`
  - Active registry: `artifacts/registry_phaseE_portfolio/registry_manifest.json`
  - Frozen confirmation registry: `artifacts/registry_frozen_decisive_gate_confirmation/registry_manifest.json`
  - Canonical delta: `+0.1671`
  - Outcome delta: `+0.1408`
  - Exact successes: `control=1`, `SAGE=3`
  - Canonical gains / regressions / preserved: `13 / 4 / 3`
  - Outcome gains / regressions / preserved: `7 / 4 / 9`
  - Births proposed / accepted / rejected: `4 / 0 / 4`
  - Rejected mechanisms: `missing_decisive_positive_triggers`, `search_filter_missing_tie_behavior`
  - Retained helper visible/called: `8 / 8`
  - Helper calls: `resolve_search_window_or_bounds=6`, `select_record_by_timestamp_extreme=2`
  - Side-effect violations: `0`
  - Runtime exceptions: `0`
  - Decision: `freeze registry for confirmation`

- `Phase E balanced formal 100` completed.
  - Report: `docs/sage_protocol/phase_E_formal_100_validation_report.md`
  - Summary: `artifacts/summaries/phase_E_balanced_formal_100/summary.json`
  - Run: `outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/`
  - Dashboard: `outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/dashboard/index.html`
  - Task focus dashboard: `outputs/phase_E_balanced_formal_100/validate_100_20260503_123038/dashboard/task_focus.html`
  - Generation: `off`
  - Registry: `artifacts/registry_phaseE_balanced_final/registry_manifest.json`
  - Registry hash: `385a0f7dbd65ce340f4edd97e26e89a67054cf1c661f01029692ca38547484b1`
  - Canonical delta: `+0.0778` (`+10.3%` relative)
  - Outcome delta: `+0.0798` (`+17.9%` relative)
  - Exact successes: `control=10`, `SAGE=13`
  - Outcome gains / regressions / preserved: `39 / 20 / 40`
  - Canonical gains / regressions / preserved: `56 / 24 / 20`
  - Helper visible/called: `61 / 52`
  - Helper calls: `prepare_reminder_creation_args=15`, `resolve_search_window_or_bounds=37`
  - Side-effect violations: `0`
  - Runtime exceptions: `0`
  - Decision: `qualified pass; proceed to Phase F`

- `Phase F balanced formal 250` completed.
  - Report: `docs/sage_protocol/phase_F_formal_250_and_final_package_report.md`
  - Summary: `artifacts/summaries/phase_F_balanced_formal_250/summary.json`
  - Run: `outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/`
  - Dashboard: `outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/dashboard/index.html`
  - Task focus dashboard: `outputs/phase_F_balanced_formal_250/validate_250_20260503_125133/dashboard/task_focus.html`
  - Generation: `off`
  - Registry: `artifacts/registry_phaseE_balanced_final/registry_manifest.json`
  - Outcome delta: `+0.0002` (`+0.04%` relative)
  - Canonical delta: `+0.0381` (`+5.09%` relative)
  - Exact successes: `control=23`, `SAGE=22`
  - Outcome gains / regressions / preserved: `70 / 66 / 110`
  - Canonical gains / regressions / preserved: `118 / 71 / 61`
  - Helper visible/called: `121 / 87`
  - Helper calls: `prepare_reminder_creation_args=26`, `resolve_search_window_or_bounds=61`
  - Failed helper attempts: `3`
  - Side-effect violations: `0`
  - Runtime exceptions: `0`
  - Decision: `large evaluation failed`

- `V2 architecture audit and partial repair` completed.
  - Reports:
    - `docs/sage_protocol/v2_architecture_audit_plan.md`
    - `docs/sage_protocol/v2_architecture_depth_audit_report.md`
    - `docs/sage_protocol/v2_cohort_quality_gate_report.md`
    - `docs/sage_protocol/v2_generation_contract_report.md`
    - `docs/sage_protocol/v2_gate_failure_memory_report.md`
    - `docs/sage_protocol/v2_routing_runtime_bundle_report.md`
    - `docs/sage_protocol/v2_reporting_contribution_report.md`
    - `docs/sage_protocol/v2_architecture_readiness_20_report.md`
  - Summary: `artifacts/summaries/v2_architecture_audit/summary.json`
  - Code repairs: mechanical cohort quality gate; generated-tool V2 contract fields; gate rejection for decisive non-diagnostic specs without cluster/failure evidence.
  - Tests: `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> `61 passed`.
  - Registry check: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_balanced_final/registry_manifest.json` -> PASS.
  - Existing formal 250 would now fail cohort quality for `near_duplicate_family_variants_above_limit` (`12` variants > max `8`).
  - Decisions: `architecture partially sufficient`; `cohort gate ready`; `generation contract ready`; `gating needs repair`; `runtime bundle needs repair`; `reporting needs repair`; readiness-20 `blocked`.
  - Next action: implement promotion evidence gate, failure-memory integration, generic runtime routing scorer, and contribution export before V2 readiness-20.

- `V2 blocker-repair sprint` completed through readiness attempt.
  - Contribution export report: `docs/sage_protocol/v2_contribution_export_repair_report.md`
  - Promotion gate report: `docs/sage_protocol/v2_promotion_gate_repair_report.md`
  - Failure memory report: `docs/sage_protocol/v2_failure_memory_integration_report.md`
  - Runtime routing report: `docs/sage_protocol/v2_runtime_routing_scorer_report.md`
  - Cluster birth report: `docs/sage_protocol/v2_shortfall_cluster_birth_report.md`
  - Readiness-20 report: `docs/sage_protocol/v2_architecture_readiness_20_report.md`
  - Summary: `artifacts/summaries/v2_architecture_readiness_20/summary.json`
  - Tests: `PYTHONPATH=src:. pytest tests/unit/test_helper_contribution.py tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> `73 passed`.
  - Registry check: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_phaseE_balanced_final/registry_manifest.json` -> PASS.
  - Readiness manifest: `artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json`.
  - Cohort quality: PASS, `20` scenarios, `15` base families, largest duplicate family size `2`, no-current-helper-fit share `0.4`.
  - Attempted run: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_193147/`.
  - Run log: `artifacts/summaries/v2_architecture_readiness_20/run.log`.
  - Run result: blocked before scenario execution because `OPENAI_API_KEY` is not set.
  - Decision: `blocked`.
  - Next action: set `OPENAI_API_KEY` and rerun readiness-20; do not launch full V2 campaign until it passes.

- `V2 architecture readiness-20 rerun with conda OpenAI key` completed.
  - Run: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/`
  - Dashboard: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/dashboard/index.html`
  - Task focus dashboard: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/dashboard/task_focus.html`
  - Report: `docs/sage_protocol/v2_architecture_readiness_20_report.md`
  - Summary: `artifacts/summaries/v2_architecture_readiness_20/summary.json`
  - Helper contribution: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/helper_contribution_summary.json`
  - Promotion gate result: `artifacts/summaries/v2_architecture_readiness_20/promotion_gate_result.json`
  - Cohort quality: PASS, `20` scenarios, `15` base families, largest duplicate family size `2`, no-current-helper-fit share `0.4`.
  - Canonical delta: `-0.0631`.
  - Outcome delta: `-0.0563`.
  - Exact successes: `control=3`, `SAGE=2`.
  - Canonical gains/regressions/preserved: `6 / 8 / 6`.
  - Outcome gains/regressions/preserved: `2 / 5 / 11`.
  - Tools proposed/accepted/rejected: `5 / 0 / 5`.
  - Rejections: `missing_downstream_tool_preservation`, `unresolved_failure_memory:search_filter_missing_tie_behavior`, `missing_decisive_positive_triggers`.
  - Selection visible/called/visible-not-called: `15 / 6 / 9`.
  - Runtime exceptions: `0`.
  - Side-effect incidents: `0`.
  - Decision: `not ready: repair cluster birth`.
  - Next action: repair cluster-birth/generation quality and routing evidence use before rerunning readiness-20; do not launch full V2 campaign.

- `V2 dependency/grading experimental sub-sprint` completed.
  - Report: `docs/sage_protocol/v2_dependency_grading_experiment_report.md`
  - Summary: `artifacts/summaries/v2_dependency_grading_experiment20/run_summary.json`
  - Run: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/`
  - Dashboard: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/dashboard/index.html`
  - Task focus dashboard: `outputs/v2_dependency_grading_experiment20/mechanism_40_20260503_203206/dashboard/task_focus.html`
  - Generation: `on`
  - Registry: `artifacts/registry_candidates/v2_dependency_grading_experiment20/registry_manifest.json`
  - Cohort quality: PASS, `20` scenarios, `15` base families, largest duplicate family size `2`.
  - Canonical delta: `+0.0801`.
  - Outcome delta: `+0.0731`.
  - Exact successes: `control=1`, `SAGE=2`.
  - Canonical gains/regressions/preserved: `8 / 6 / 6`.
  - Outcome gains/regressions/preserved: `3 / 5 / 10`.
  - Tools proposed/accepted/rejected: `6 / 1 / 5`.
  - Accepted candidate: `next_dependency_precondition_call`; diagnostic only because accepted-but-uncalled in this run.
  - Generated-helper visible/called/visible-not-called: `12 / 6 / 6`.
  - Runtime exceptions: `0`.
  - Side-effect incidents: `0`.
  - Tests: `PYTHONPATH=src:. pytest tests/unit -q` -> `166 passed, 2 warnings`.
  - Registry checks: readiness candidate registry PASS; dependency/grading candidate registry PASS.
  - Commit hygiene: `artifacts/baselines/control_task_baselines/index.jsonl` removed from git tracking so local cache rows do not commit broken pointers to ignored record files.
  - Decision: `rerun readiness-20`.
  - Next action: rerun readiness-20 with grading-accounting, live-validation, dependency-cluster, and routing changes; do not start 60/100/250 yet.

- `V2 experimental matrix-20 and readiness reruns` completed.
  - Report: `docs/sage_protocol/v2_experimental_matrix20_report.md`
  - Primary clean matrix summary: `artifacts/summaries/v2_experimental_matrix20_clean/matrix_summary.json`
  - Corrected candidate-repair/combined rerun summary: `artifacts/summaries/v2_experimental_matrix20_clean_repairfix/matrix_summary.json`
  - Matrix design: clean empty candidate registry per variant; generation ON; 20 quality-gated scenarios; control cache `use-if-eligible` but all controls fresh in summaries.
  - Matrix winner: `contract_synthesis` only.
  - Best matrix result: `variant5_contract_synthesis`, outcome delta `+0.0932`, canonical delta `+0.0277`, accepted/called `message_search_time_window`, visible/called/VNC `8 / 1 / 7`, side-effect/runtime `0 / 0`.
  - Bug fixed: `tool_repair_attempted` added as valid campaign event; corrected candidate-repair rerun remained non-winning.
  - Routing repair: generated helpers are hidden if declared downstream original ToolSandbox tools are unavailable in the scenario.
  - Readiness rerun 1: `outputs/v2_readiness20_contract_synthesis/mechanism_40_20260503_223710/`, outcome `+0.0946`, canonical `-0.0097`, visible/called/VNC `8 / 1 / 7`, protocol gate FAIL.
  - Readiness rerun 2 after routing repair: `outputs/v2_readiness20_contract_synthesis_routingfix/mechanism_40_20260503_224320/`, outcome `+0.0626`, canonical `-0.0108`, visible/called/VNC `2 / 1 / 1`, called-subset outcome `+0.3947`, side-effect/runtime `0 / 0`, protocol gate FAIL.
  - Readiness rerun 3 with grading accounting: `outputs/v2_readiness20_contract_synthesis_grading_routingfix/mechanism_40_20260503_224648/`, outcome `-0.1475`, canonical `+0.0442`, accepted-but-uncalled `message_search_time_window` and `recency_to_timestamp_bounds`, protocol gate FAIL.
  - Decision: `repair generation then rerun matrix subset`; do not start 60/100/250.

- `Generated-helper adoption diagnosis` completed.
  - Evidence: `message_search_time_window` was visible but not called in `modify_contact_with_message_recency`; it was called only after repeated failed `search_messages(...=null)` attempts in the distraction variant.
  - Root cause found: generic non-reminder helper docstrings advertised an impossible reminder-style call path using `should_call_add_reminder` and `<tool>_kwargs`.
  - Fix: non-reminder helper docstrings now include positive/negative triggers and describe actual output-schema fields for downstream original ToolSandbox calls.
  - Tests: `PYTHONPATH=src:. pytest tests/unit -q` -> `171 passed, 2 warnings`.

- `V2 generated-tool adoption diagnosis and fair-chance confirmation` completed.
  - Report: `docs/sage_protocol/v2_tool_adoption_diagnosis_report.md`
  - Focused replay summary: `outputs/v2_tool_adoption_replay2/mechanism_40_20260503_225947/`
  - Fair-chance summary: `artifacts/summaries/v2_fair_chance_confirmation20/confirmation_summary.json`
  - Dashboards opened for all confirmation variants.
  - Main fixes: downstream original-tool availability routing; generic helper docstring affordance repair; fair-chance confirmation runner.
  - Focused replay: helper visible/called/VNC `2 / 1 / 1`, canonical `+0.2109`, protocol PASS.
  - Fair-chance winner: `variant5_contract_synthesis`, outcome `+0.0617`, canonical `+0.0979`, exact successes `0 -> 2`, helper visible/called/VNC `4 / 3 / 1`, side-effect/runtime `0 / 0`, protocol PASS.
  - Combined stack failed: outcome `-0.0756`, canonical `-0.0733`, helper visible/called/VNC `18 / 4 / 14`.
  - Decision: `rerun readiness-20 with two-stage confirmation`; do not start 60/100/250 yet.


- `Formal best3-relative 100 and 250 validation` completed.
  - Date: `2026-05-04T06:08:30.482096`
  - Registry: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
  - Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
  - Helpers: `relative_day_time_to_timestamp, resolve_search_window_or_bounds, select_record_by_timestamp_extreme`
  - Formal 100 run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
  - Formal 100 outcome delta: `0.1347`; relative lift `33.58%`; exact `control=16` -> `SAGE=23`; protocol pass `True`.
  - Formal 250 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
  - Formal 250 outcome delta: `0.0806`; relative lift `20.52%`; exact `control=31` -> `SAGE=40`; protocol pass `True`.
  - Formal 250 reference/canonical similarity delta: `0.0660`; route-mismatch-qualified `False`.
  - Runtime exceptions: `0`; helper side-effect incidents: `0`.
  - Dashboards opened: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/index.html` and `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/task_focus.html`.
  - Tests: targeted unit suite `109 passed, 2 warnings`; registry check `3 active entries pass`; py_compile PASS; `git diff --check` PASS.
  - Report: `docs/sage_protocol/v2_final_tool_pipeline_campaign_report.md`
  - Summary: `artifacts/summaries/v2_final_best3_formal_validation/summary.json`
  - Decision: `formal 250 passed`.
  - Next action: freeze/commit v1.0 evidence package; start V2.0 campaign on autonomous tool birth coverage.


- `Post-formal-250 evidence lock and robustness sprint` completed.
  - Date: `2026-05-04T07:20:28.034191`
  - Evidence lock: `docs/sage_protocol/v2_formal250_evidence_lock_report.md`
  - Metric audit: `docs/sage_protocol/v2_formal250_metric_audit_report.md`
  - Helper contribution audit: `docs/sage_protocol/v2_best3_helper_contribution_audit.md`
  - Frozen claim registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
  - Robustness 60 run: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441`
  - Robustness 60 dashboard: `http://127.0.0.1:5520/outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/dashboard/index.html`
  - Robustness 60 task focus dashboard: `http://127.0.0.1:5520/outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/dashboard/task_focus.html`
  - Robustness 60 outcome delta: `0.0612`; relative lift `14.01%`; exact `4 -> 13`.
  - Robustness 60 protocol gate: `False`; reasons `['confirmation_outcome_delta_below_0_08', 'helper_call_share_below_25_percent']`.
  - Runtime exceptions: `0`; helper side-effect incidents: `0`.
  - Decision: `robustness confirmed`.
  - Next action: `start V2.0 candidate discovery` using separate candidate registries.


- `V2.0 shortfall clustering phase` completed.
  - Date: `2026-05-04T08:08:59.371464`
  - Sources: formal 250 and robustness 60 paired comparisons/helper contribution summaries.
  - Strong clusters: `5` of `9`.
  - Report: `docs/sage_protocol/v2_0_shortfall_cluster_report.md`
  - Artifact: `artifacts/summaries/v2_0_shortfall_clusters/latest_shortfall_clusters.json`
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Decision: `candidate found`.
  - Next action: run V2.0 discovery-60 with generation ON using a copied candidate registry.

- `V2.0 discovery-60 and candidate triage` completed.
  - Date: `2026-05-04T08:41:14.547747`
  - Run: `outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640`
  - Dashboards: `http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_discovery60_20260504_081357/mechanism_40_20260504_081640/dashboard/task_focus.html`
  - Cohort quality: `pass`; distinct families `27`; no-current-helper-fit share `0.31666666666666665`.
  - Control cache: `fresh`; cached `0`; fresh `60`; collected controls `60`.
  - Metrics: outcome delta `0.0015`; canonical delta `0.0289`; exact `control=4` -> `SAGE=2`; runtime exceptions `0`.
  - Tool birth: `8` attempts; accepted `['next_dependency_precondition_call']`; accepted-but-uncalled `['next_dependency_precondition_call']`.
  - Candidate triage: no candidate advanced to confirmation; `next_dependency_precondition_call` is diagnostic only because called count was 0.
  - Reports: `docs/sage_protocol/v2_0_discovery60_report.md`, `docs/sage_protocol/v2_0_candidate_triage_report.md`, `docs/sage_protocol/v2_0_confirmation60_report.md`.
  - Decision: `routing repair needed`.


- `V2.0 dependency fair-chance routing repair` completed.
  - Date: `2026-05-04T17:15:00`
  - Report: `docs/sage_protocol/v2_0_dependency_fair_chance_routing_report.md`
  - Candidate registry: `artifacts/registry_candidates/v2_0_dependency_fair_chance20_20260504_165041/registry_manifest.json`; frozen best3 registry untouched.
  - Final diagnostic run: `outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647`
  - Dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_20260504_165041/mechanism_40_20260504_170647/dashboard/task_focus.html`
  - Cohort quality: `pass`; control cache `fresh 0 cached / 20 fresh`.
  - Metrics: outcome delta `+0.0185`; canonical delta `+0.0553`; exact `0 -> 2`; runtime exceptions `0`; helper side-effect incidents `0`.
  - `next_dependency_precondition_call`: visible/called/VNC `9 / 0 / 9`; fair-chance exposure worked but adoption failed after one additional affordance repair.
  - Tests: targeted V2 suite `62 passed`; frozen best3 and candidate registry check-only both PASS.
  - Decision: `park dependency lane`.
  - Next action: mine a different no-current-helper-fit cluster; do not run confirmation-60 for this candidate without later call evidence.

- `V2.0 dependency schema-verification 20 and opaque-input repair` completed.
  - Date: `2026-05-04T17:34:40-04:00`
  - Run: `outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556`
  - Dashboards: `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556/dashboard/index.html` and `http://127.0.0.1:5520/outputs/v2_0_dependency_fair_chance20_schema_verify_20260504_172551/mechanism_40_20260504_172556/dashboard/task_focus.html`
  - Control cache: mixed, `15 cached / 5 fresh`; candidate arm cache `0 hits / 130 misses / 130 writes`.
  - Metrics: outcome delta `+0.1593`; canonical delta `+0.0803`; exact `control=0 -> SAGE=3`; runtime exceptions `0`; protocol gate `PASS`.
  - `next_dependency_precondition_call`: visible/called/VNC `9 / 0 / 9`; not called after fair routing and schema affordance repair.
  - Root cause: opaque `dependency_state` dict input adds a pre-call construction burden and does not beat direct ToolSandbox setter/getter use.
  - Repair: gate rejects opaque dict inputs for `state_precondition_helper`; generator and dependency observation now require scalar top-level state inputs.
  - Tests: targeted suite `61 passed`; frozen best3 registry check PASS; stale dependency candidate registry expected FAIL on `state_helper_opaque_dict_input_contract`.
  - Decision: `park dependency lane`; next action is shortfall mining for a different cluster or scalar-input successor.

- `V2.0 dependency lucrative/force-call diagnostic` completed.
  - Date: `2026-05-04T18:06:00-04:00`
  - Diagnostic registry: `artifacts/registry_candidates/v2_0_dependency_lucrative20_20260504_174000/registry_manifest.json`
  - Natural run: `outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438`; dashboards opened at `/dashboard/index.html` and `/dashboard/task_focus.html`.
  - Natural metrics: outcome `+0.0552`; canonical `+0.0681`; dependency helper visible/called/VNC `10 / 0 / 10`; protocol FAIL.
  - Forced-after-error run: `outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421`; dashboards opened at `/dashboard/index.html` and `/dashboard/task_focus.html`.
  - Forced metrics: outcome `-0.0002`; canonical `+0.0793`; dependency helper visible/called/VNC `10 / 8 / 2`; called-subset outcome `-0.0285`; runtime exceptions `0`; side-effect preservation failures `1`; protocol FAIL.
  - Fixes: added diagnostic OpenAI force-after-error mode and diagnostic routing override for adoption-risk suppression; tested scalar-input dependency successor.
  - Decision: `park dependency lane`; direct ToolSandbox route is better than this helper concept for now.


- `V2.0 selection-action discovery60 with fair-chance diagnostics` completed.
  - Date: `2026-05-04T19:09:36`
  - Manifest: `artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_manifest.json`
  - Cohort quality: PASS; `60` scenarios; role split `20 / 25 / 15`; no-current-helper-fit share `55.00%`.
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Arm A best3-only: `outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306`; outcome `0.0989`; relative lift `18.96%`; canonical `0.1147`; exact `4 -> 8`; runtime/side-effect `0 / 0`.
  - Arm B discovery: `outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638`; outcome `0.0245`; relative lift `4.35%`; canonical `0.0552`; exact `5 -> 9`; runtime/side-effect `0 / 0`.
  - Candidate born: `select_contact_field_by_constraint`, diagnostic-only; natural visible/called/VNC `2 / 0 / 2`.
  - Force-after-`search_contacts` diagnostic: `outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512`; selector visible/called `8 / 4`; called-subset outcome `-0.0132`; overall outcome `-0.1074`; runtime/side-effect `0 / 0`.
  - Fix added: diagnostic force can wait for a named base-tool call and can override explicit visible-not-called suppression only in force mode.
  - Tests: `87 passed`; registry checks PASS for frozen best3, discovery candidate, and force diagnostic registries.
  - Reports: `docs/sage_protocol/v2_0_selection_action_discovery60_report.md`, `docs/sage_protocol/v2_0_selection_action_candidate_triage.md`.
  - Decision: `candidate concept negative`.
  - Next action: park this candidate and mine the next uncovered no-current-helper-fit cluster; no confirmation60 for this candidate.

- `V2.1 tool expansion discovery60` completed.
  - Date: `2026-05-04T20:11:44-04:00`
  - Manifest: `artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json`
  - Cohort quality: PASS; `60` scenarios; distinct families `20`; largest family share `0.10`; no-current-helper-fit share `25.00%`.
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_discovery60_20260504_191835/registry_manifest.json`.
  - Arm A best3-only: `outputs/v2_1_tool_expansion_best3_60_20260504_191835/mechanism_60_20260504_191910`; dashboard `/dashboard/index.html`; outcome `+0.1543`; canonical `+0.0527`; exact `6 -> 10`; runtime/side-effect `0 / 0`.
  - Arm B discovery: `outputs/v2_1_tool_expansion_discovery60_run_20260504_191835/mechanism_60_20260504_192907`; dashboard `/dashboard/index.html`; outcome `+0.1586`; canonical `+0.1377`; exact `2 -> 9`; runtime/side-effect `0 / 0`.
  - Tool birth: proposed `5`; accepted `prepare_side_effect_args_from_selected_record`; rejected `select_visible_record_by_constraints`, `select_action_target_by_recency`; accepted-but-uncalled `prepare_side_effect_args_from_selected_record`.
  - Force diagnostics: after routing/affordance/abstain repairs final run `outputs/v2_1_tool_expansion_force_prepare_args12_abstain_20260504_201500/mechanism_12_20260504_200720`; candidate visible/called/VNC/failed `12 / 8 / 4 / 0`, but calls returned `missing_required_helper_inputs`, so no independent positive candidate evidence.
  - Fixes: added V2.1 shortfall observations/triggers/generator guidance; fixed one-of-many downstream routing for composite helpers; added post-selection affordance and missing-argument abstain safety.
  - Tests: `95 passed`; frozen best3 and V2.1 candidate registry checks PASS.
  - Reports: `docs/sage_protocol/v2_1_tool_expansion_discovery60_report.md`, `docs/sage_protocol/v2_1_tool_expansion_candidate_triage.md`.
  - Decision: `generation contract repair needed`; no confirmation60.

- `V2.1 tool callability repair` completed.
  - Date: `2026-05-04T23:10:00-04:00`
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/registry_manifest.json`.
  - Fixes: optional helper defaults for `constraints`, action-selector usage guidance, recency-action routing suppression on non-recency tasks, safe `all`/`any`, selector one-of-many downstream routing, post-selection trace chaining.
  - Tests: `104 passed`; candidate registry check-only PASS.
  - Force run: `outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829`; outcome `+0.2223`; canonical `+0.1471`; exact `+2`; selector visible/called/VNC `9 / 5 / 4`; called-subset outcome `+0.6798`; runtime/side-effect `0 / 0`; protocol PASS.
  - Natural run: `outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708`; outcome `+0.1167`; canonical `+0.0511`; exact `+1`; selector visible/called/VNC `5 / 3 / 2`; called-subset outcome `+0.4828`; runtime/side-effect `0 / 0`; protocol PASS.
  - Dashboards opened for both latest dashboard and task-focus URLs.
  - Report: `docs/sage_protocol/v2_1_tool_callability_repair_report.md`.
  - Decision: `candidate ready for confirmation60`.
  - Next action: frozen confirmation-60 for best3 + `select_action_target_by_recency` vs frozen best3 only.

- `V2.1 select_action_target_by_recency callability decision` completed.
  - Date: `2026-05-04T23:55:00-04:00`
  - Report: `docs/sage_protocol/v2_1_select_action_callability_report.md`
  - Frozen best3 registry untouched.
  - Confirmation registry: `artifacts/registry_candidates/v2_1_select_action_confirmation60_20260504_232500/registry_manifest.json`, SHA-256 `854ac053d6e3c0e96751cf3eddecd26f987f1d50484c68ea45cd3cd20ac82303`.
  - Force diagnostic proved callability: visible/called/VNC `9 / 5 / 4`, called-subset outcome `+0.6798`, side-effect/runtime `0 / 0`.
  - Natural diagnostic proved adoption after affordance repair: visible/called/VNC `5 / 3 / 2`, called-subset outcome `+0.4828`, side-effect/runtime `0 / 0`.
  - Confirmation60 after insufficient-info suppression: `outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336`; dashboard and task-focus opened.
  - Confirmation60 overall: outcome `+0.0907`, canonical `+0.0612`, exact delta `+6`, protocol PASS.
  - Selector contribution in confirmation60: visible/called/VNC `5 / 2 / 3`, called-subset outcome `-0.1667`, canonical `+0.1111`, side-effect/runtime `0 / 0`.
  - Decision: `candidate concept negative; park candidate`.
  - Next action: retain framework callability/routing fixes; mine next uncovered cluster rather than promoting this selector.


- `V2.1 gap closure discovery and candidate triage` completed.
  - Date: `2026-05-04T23:05:00-04:00`
  - Manifest: `artifacts/summaries/v2_1_gap_closure_20260504_221814/cohort_manifest.json`; cohort quality PASS; no-current-helper-fit share `41.67%`.
  - Discovery60: `outputs/v2_1_gap_closure_discovery60_20260504_221814/mechanism_60_20260504_221901`; dashboards opened at `/dashboard/index.html` and `/dashboard/task_focus.html`.
  - Discovery60 metrics: outcome `0.0088`; canonical `-0.0101`; exact `3 -> 3`; runtime exceptions `0`.
  - Accepted candidate: `prepare_side_effect_args_from_selected_record`, visible/called/VNC `27 / 0 / 27`; no natural adoption.
  - Force pre-autofill: `outputs/v2_1_gap_closure_force_prepare_args12_20260504_2230/mechanism_12_20260504_223723`; called `11/12`; outcome `0.0644`; route mismatch qualified `True`; trace review showed missing-input abstains.
  - Force post-autofill: `outputs/v2_1_gap_closure_force_prepare_args12_post_autofill_20260504_2250/mechanism_12_20260504_224507`; called `12/12`; outcome `-0.0316`; valid remove-contact kwargs in 4 cases but mixed subset regressed.
  - Natural post-routing diagnostic: `outputs/v2_1_gap_closure_natural_prepare_args12_post_routing_20260504_2300/mechanism_12_20260504_224921`; visible/called/VNC `12 / 0 / 12`; outcome `-0.0510`.
  - Fixes: selected-record autofill from unique original search trace, routing hard-block precedence over provisional visibility, composite suppression on non-action tasks, low-friction composite generation prompt, selector normalization prompt/tests.
  - Tests: targeted suite `74 passed`; diagnostic and discovery registry checks PASS.
  - Decision: `best3 remains final portfolio`; current generated candidate parked.

- `V2.1 scale validation to 100, 250, 500, and 1000+` completed.
  - Date: `2026-05-05T04:45:00-04:00`
  - Frozen registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
  - Reports: `docs/sage_protocol/v2_1_expanded_portfolio_100_report.md`, `docs/sage_protocol/v2_1_expanded_portfolio_250_report.md`, `docs/sage_protocol/v2_1_formal_500_report.md`, `docs/sage_protocol/v2_1_formal_1000_report.md`, `docs/sage_protocol/final_claim_summary.md`.
  - 100 run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`; outcome lift `+33.58%`; canonical delta `+0.0911`; exact `16 -> 23`; protocol PASS.
  - 250 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`; outcome lift `+20.52%`; canonical delta `+0.0660`; exact `31 -> 40`; protocol PASS.
  - 500 run: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`; outcome lift `+14.35%`; canonical delta `+0.0331`; exact `60 -> 76`; cohort quality PASS; protocol failed older absolute `+0.08` threshold.
  - 1000+ run: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905`; scenarios `1032`; outcome lift `+14.05%`; canonical delta `+0.0342`; exact `159 -> 195`; cohort quality PASS; external-service cases present; protocol failed older absolute/helper-call-share thresholds.
  - Dashboards opened for 100, 250, 500, and 1000+ dashboard and task-focus pages.
  - Runtime exceptions: `0` at all scales. Helper side-effect incidents: `0` at all scales.
  - Control cache mode: `use-if-eligible`; scale runs used fresh controls because manifest checksums differed under strict compatibility policy.
  - Decision: `full-benchmark 1000+ positive; best3 remains final portfolio`.


- `V2.2 masked-best3 discovery and first candidate confirmation` completed.
  - Date: `2026-05-05T08:20:00-04:00`
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Main discovery run: `outputs/v2_2_masked_best3_discovery60_20260505_064113/mechanism_60_20260505_064202`; generated/accepted candidates included `select_visible_record_by_constraints`, `prepare_side_effect_args_from_selected_record`, and `days_between_timestamps` across repair attempts.
  - Callability repairs: selector ambiguity output normalization, side-effect route accounting, search-filter routing availability, and post-search selector affordance guidance.
  - Selector fair-chance run: `outputs/v2_2_masked_best3_fairchance60_docfix_20260505_064113/mechanism_60_20260505_073523`; visible/called/VNC `34 / 0 / 34`.
  - Selector force diagnostic: `outputs/v2_2_masked_best3_selector_force60_20260505_064113/mechanism_60_20260505_070818`; visible/called `34 / 29`, called-subset outcome `0.053338674217560895`; not promoted because natural calls stayed zero.
  - Days confirmation run: `outputs/v2_2_days_between_confirmation60_resume_20260505_081500/mechanism_60_20260505_081108`; dashboard and task-focus opened on port `5592`.
  - Days metrics: outcome `+0.0891`, canonical `-0.0600`, exact `4 -> 4`, helper visible/called/VNC `14 / 14 / 0`, called-subset outcome `0.10714285714285714`, side-effect/runtime `0 / 0`.
  - Reporting repair: helper contribution export now flags called-subset route mismatch when outcome improves but canonical regresses.
  - Tests: targeted suite `125 passed`; registry checks PASS for V2.2 discovery, days confirmation, and new-toolset registries.
  - New toolset registry: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json` with `days_between_timestamps` only.
  - Reports: `docs/sage_protocol/v2_2_masked_best3_discovery_report.md`, `docs/sage_protocol/v2_2_candidate_callability_report.md`, `docs/sage_protocol/v2_2_candidate_confirmation_report.md`, `docs/sage_protocol/v2_2_new_toolset_registry_report.md`, `docs/sage_protocol/v2_2_combined_portfolio_ablation_report.md`.
  - Decision: `new toolset has 1 confirmed tool`.
  - Next action: continue masked discovery only on a non-parked, tool-suitable cluster; do not run combined ablation or scale validation yet.

- `V2.2 masked-best3 discovery loop 2` completed.
  - Date: `2026-05-05T17:30:00-04:00`
  - Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`.
  - Masked tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`.
  - Confirmed V2.2 registry unchanged: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`, SHA-256 `cb70568c3613c2a11c68f6d6182375e099569bde103bc36637b957602df760cd`; confirmed tools `1 / 3` with `days_between_timestamps` only.
  - Gap atlas: `artifacts/summaries/v2_2_loop2_20260505_164027/latest_gap_atlas.json`; loop summary: `artifacts/summaries/v2_2_loop2_20260505_164027/loop2_summary.json`.
  - Selector actor-policy diagnostic: `outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951`; dashboards opened at `http://127.0.0.1:5594/outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951/dashboard/index.html` and `/dashboard/task_focus.html`; outcome `-0.0263`; canonical `-0.0172`; exact `2 -> 2`; selector visible/called/VNC `16 / 0 / 16`; runtime/side-effect `0 / 0`; selector lane parked.
  - Discovery60 retry: `outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056`; dashboards opened at `http://127.0.0.1:5596/outputs/v2_2_masked_best3_discovery_loop2_retry_20260505_164052/mechanism_60_20260505_164056/dashboard/index.html` and `/dashboard/task_focus.html`; outcome `+0.0335`; canonical `-0.0018`; exact `14 -> 11`; accepted `extract_stock_symbol`, but natural calls `0 / 8`.
  - Force-call after trace bridge: `outputs/v2_2_extract_stock_force20_after_bridge_20260505_171542/mechanism_40_20260505_171545`; dashboards opened at port `5598`; helper visible/called/VNC/failed `4 / 2 / 2 / 2`; called-subset outcome `-0.5000`.
  - Natural fair-chance after derived actor policy: `outputs/v2_2_extract_stock_fairchance20_20260505_172237/mechanism_40_20260505_172240`; dashboards opened at port `5599`; outcome `+0.0534`; canonical `+0.0042`; exact `5 -> 6`; `extract_stock_symbol` visible/called/VNC/failed `4 / 4 / 0 / 0`; called-subset outcome `-0.0772`; runtime/side-effect `0 / 0`; candidate parked as concept-negative.
  - Repairs: selector actor policy, evidence-aware fair-chance selector routing, negative-applicability propagation for live validation, derived-value actor policy, and trace-bridging for single-dict derived helpers.
  - Tests: targeted unit suite `115 passed`; artifact builder compile PASS; V2.2 new-toolset registry check-only PASS.
  - Reports: `docs/sage_protocol/v2_2_gap_atlas_loop2_report.md`, `docs/sage_protocol/v2_2_selector_actor_policy_diagnostic20_report.md`, `docs/sage_protocol/v2_2_masked_best3_discovery_loop2_report.md`, `docs/sage_protocol/v2_2_new_toolset_registry_report.md`.
  - Decision: `continue masked discovery`; no confirmation60 for `extract_stock_symbol`; no combined ablation yet.


- `V2.3 medium-grain deterministic skill experiment` completed.
  - Date: `2026-05-05T19:05:00-04:00`
  - Frozen best3 registry untouched.
  - Initial discovery60: `outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755`; dashboards opened at `http://127.0.0.1:5602/outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755/dashboard/index.html` and `http://127.0.0.1:5602/outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755/dashboard/task_focus.html`; outcome `-0.0006`; canonical `0.0031`; exact delta `2`; accepted tools `0`.
  - Repairs: medium-grain feature flag, diverse cluster observation, generator preservation guidance, actor-policy/docstring affordance, trace bridge for `records`, live validation rejection for positive abstains, composite output normalization.
  - Diagnostic20: `outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213`; dashboards opened at `http://127.0.0.1:5604/outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213/dashboard/index.html` and `http://127.0.0.1:5604/outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213/dashboard/task_focus.html`; accepted `constraint_to_action_planner`; visible/called/VNC `6 / 0 / 6`; outcome `0.1715`; canonical `0.0085`; exact delta `1`; runtime/side-effect `0 / 0`.
  - Force20: `outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852`; dashboards opened at `http://127.0.0.1:5605/outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852/dashboard/index.html` and `http://127.0.0.1:5605/outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852/dashboard/task_focus.html`; forced after `search_contacts`; visible/called/VNC `15 / 13 / 2`; called-subset outcome `-0.13126404560161367`; called-subset canonical `-0.13004658549699968`; side-effect/runtime `9 / 0`.
  - Tests: targeted V2.3 unit suite `127 passed`; artifact builder compile PASS; candidate, V2.2 new-toolset, and frozen best3 registry checks PASS.
  - Reports: `docs/sage_protocol/v2_3_medium_grain_skill_experiment_report.md`, `docs/sage_protocol/v2_3_medium_grain_candidate_triage.md`, `docs/sage_protocol/v2_3_medium_grain_confirmation_report.md`.
  - Decision: `medium-grain skill concept negative`; no confirmation60; candidate parked.

- `V2.2 Best4 additivity check` completed.
  - Date: `2026-05-06T09:05:00-04:00`
  - Frozen best3 registry untouched.
  - Best4 candidate registry: `artifacts/registry_candidates/v2_2_best4_candidate/registry_manifest.json`, SHA-256 `e497d29b7b31b89b9368af7c9327679086a881f8e9c62a182ca07b25f18f7834`.
  - Registry checks: Best4, days-only, and frozen best3 all PASS.
  - Ablation60 manifest: `artifacts/summaries/v2_2_best4_ablation60_20260506_075831/cohort_manifest.json`; cohort quality PASS; largest family share `0.0833`; no-current-helper-fit share `0.40`; external contamination `0`.
  - Ablation60 best3-only: `outputs/v2_2_best4_ablation60_best3_20260506_075831/mechanism_60_20260506_075938`; dashboard/task-focus opened; outcome `+0.0504`; canonical `+0.0858`; exact `3 -> 5`; runtime/side-effect `0 / 0`.
  - Ablation60 days-only: `outputs/v2_2_best4_ablation60_days_only_20260506_075831/mechanism_60_20260506_081058`; dashboard/task-focus opened; outcome `+0.0261`; canonical `+0.0191`; exact `1 -> 4`; days visible/called/VNC `8 / 8 / 0`; runtime/side-effect `0 / 0`.
  - Ablation60 best4: `outputs/v2_2_best4_ablation60_best4_20260506_075831/mechanism_60_20260506_082133`; dashboard/task-focus opened; raw outcome `-0.0103`; canonical `-0.0030`; exact `3 -> 4`; days visible/called/VNC `8 / 8 / 0`; runtime/side-effect `0 / 0`.
  - Common-control recalculation across ablation arms: Best4 candidate mean exceeded Best3 by `+0.0118` over `52` numeric-outcome scenarios, so frozen100 follow-up was run.
  - Cached-control rerun attempt: `outputs/v2_2_best4_ablation60_best3_cached_20260506_075831/`; interrupted because partial cached-control synthesis did not reach candidate execution in a reasonable window; not used for decision.
  - Frozen100 Best4: `outputs/v2_2_best4_frozen100_20260506_075831/validate_100_20260506_084140`; dashboard/task-focus opened; control source mixed (`72` cached, `28` fresh); outcome `+0.0679`; canonical `+0.0696`; exact `14 -> 19`; days visible/called/VNC `3 / 3 / 0`; days called-subset outcome `+0.1111`; runtime/side-effect `0 / 0`.
  - Preserved best3 formal100 comparison: outcome `+0.1347`; canonical `+0.0911`; exact `16 -> 23`.
  - Decision: `best4 not additive`; do not run Best4 frozen250; best3 remains final validated portfolio.


- `V2.4 additive-only gap closure` completed.
  - Date: `2026-05-06T10:15:00-04:00`
  - Protected best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
  - State update: `days_between_timestamps` remains standalone only; Best4 not additive; no Best4 frozen250.
  - Gap atlas: `artifacts/summaries/v2_4_additive_gap_atlas/latest_gap_atlas.json`; selected cluster `external_service_answer_extraction`.
  - Discovery setup: `artifacts/summaries/v2_4_additive_discovery60_20260506_095428/setup_summary.json`; manifest `artifacts/summaries/v2_4_additive_discovery60_20260506_095428/cohort_manifest.json`; quality gate `PASS`; `--allow-contaminated-preflight` used for explicit external-service diagnostic; no low-quality override.
  - First pass: `outputs/v2_4_additive_discovery60_20260506_093603/mechanism_60_20260506_093702`; accepted candidate had placeholder `search_service_payload` and was hidden; treated as framework blocker.
  - Repairs: concrete producer-name birth evidence, placeholder original-tool contract rejection, derived multi-producer routing as any-match, list-result trace bridging.
  - Tests: targeted suite `116 passed`; registry check-only `PASS` for frozen best3 and clean V2.4 candidate registry.
  - Fair rerun: `outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500`; dashboards `http://127.0.0.1:5623/outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500/dashboard/index.html` and `http://127.0.0.1:5623/outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500/dashboard/task_focus.html`.
  - Metrics: outcome `+0.0031` (+1.20% relative), canonical `+0.0127`, exact `8 -> 7`, gains/regressions/preserved outcome `5/8/31`, canonical `18/17/25`, runtime/side-effect `0 / 0`.
  - Candidate `extract_service_answer_field`: visible/called/VNC `49 / 5 / 44`, called-subset outcome `-0.1804`, called-subset canonical `+0.1609`.
  - Decision: `candidate concept negative`; no confirmation60; best3 remains final validated portfolio.
  - Reports: `docs/sage_protocol/v2_4_additive_gap_atlas_report.md`, `docs/sage_protocol/v2_4_additive_discovery60_report.md`, `docs/sage_protocol/v2_4_additive_confirmation60_report.md`.

- `V2.5 tool-foundry micro value test and task-level control cache repair` completed.
  - Date: `2026-05-06T12:05:00-04:00`.
  - Cache repair: removed `manifest_checksum` from cache compatibility so completed controls are reused task-by-task; stored manifest hashes remain audit metadata.
  - Cache test: `PYTHONPATH=src:. pytest tests/unit/test_control_baseline_cache.py -q` -> `8 passed`.
  - Foundry artifact: `artifacts/summaries/v2_5_tool_foundry_v2_5_tool_foundry_scalar_temp_20260506_114557/candidate_batch_summary.json`.
  - Candidate batch: accepted `resolve_temperature_answer_unit` and `prepare_temperature_conversion_args`.
  - Registry checks: scalar repaired candidate registry PASS at `artifacts/registry_candidates/v2_5_temperature_answer_scalar/registry_manifest.json`.
  - Best3-only cached micro: `outputs/v2_5_micro_temperature_best3_only_cached_20260506_113421/mechanism_40_20260506_113425`; dashboard/task-focus opened; control source mixed `17 / 3`; outcome `+0.0272`; canonical `+0.0532`; exact `4 -> 6`.
  - Payload helper cached micro: `outputs/v2_5_micro_temperature_answer_only_cached_20260506_112638/mechanism_40_20260506_112641`; dashboard/task-focus opened; control source mixed `17 / 3`; outcome `+0.0916`; helper visible/called/VNC `8 / 1 / 7`; callability blocker was omitted `weather_payload`.
  - Scalar repaired helper cached micro: `outputs/v2_5_micro_temperature_scalar_repair_cached_20260506_114758/mechanism_40_20260506_114803`; dashboard/task-focus opened; control source mixed `19 / 1`; outcome `-0.0579`; canonical `+0.0080`; exact `4 -> 7`; helper visible/called/VNC `8 / 5 / 3`; called-subset outcome `-0.1428`; runtime/side-effect `0 / 0`.
  - Decision: `candidate concept negative`; park temperature answer/conversion lane and do not run additive60 for it.

## 2026-05-06 - V2.5 Foundry Loop 2-3 Micro Diagnostics
- Repaired derived-calculator gating/routing for producer-call preservation, insufficient-information suppression, and trigger/family exposure limits.
- Repaired derived payload callability bridge: scalar original results are wrapped as `{"result": value}` and a single dict payload input can be autofilled even when scalar selector inputs are present.
- Repaired derived actor policy for payload-plus-scalar helpers.
- Generated candidate registry: `artifacts/summaries/v2_5_tool_foundry_v2_5_loop3_location_bridge_20260506_132151/candidate_batch_registry/registry_manifest.json`, SHA `9e28d0c3c08ab7a774585a7ffbb708b432defecf34a0f5b98f8bf14bf8af8765`, check-only PASS.
- Distance micro: `outputs/v2_5_micro_distance_unitsafe_routingfix_cached_20260506_125948/mechanism_40_20260506_125953`; dashboards opened at port `5633`; helper visible/called/VNC `4 / 4 / 0`; called-subset outcome `+0.5556`; runtime/side-effect `0 / 0`.
- Distance best3 comparison: `outputs/v2_5_micro_distance_best3_only_cached_20260506_130801/mechanism_40_20260506_130805`; dashboards opened at port `5634`; controls all cached `20 / 0`; best3+distance vs best3 outcome `+0.0447` on same manifest.
- Location natural policy run: `outputs/v2_5_micro_location_field_policyrepair_cached_20260506_133006/mechanism_40_20260506_133010`; dashboards opened at port `5636`; visible/called/VNC `4 / 1 / 3`; called-subset outcome `0.0`.
- Location force-after-lookup: `outputs/v2_5_micro_location_field_force_after_lookup_20260506_133440/mechanism_40_20260506_133444`; dashboards opened at port `5637`; visible/called/VNC `4 / 4 / 0`; called-subset outcome `0.0`; canonical `+0.0368`; runtime/side-effect `0 / 0`; protocol PASS but candidate parked for primary-metric value failure.
- Control cache was task-level mixed/cached across runs and worked task-by-task; latest force run used `18 cached / 2 fresh`.
- Decision: `continue gap-closure loop`.

## 2026-05-06 - V2.5 Direct Side-Effect Dict-Payload Candidate
- Generated `prepare_direct_contact_action_kwargs` from `direct_side_effect_no_helper`; registry check-only PASS at `artifacts/summaries/v2_5_tool_foundry_v2_5_loop4_direct_aliasfix_20260506_134732/candidate_batch_registry/registry_manifest.json`.
- Natural micro: `outputs/v2_5_micro_direct_action_cached_20260506_134827/mechanism_40_20260506_134832`; dashboards opened on port `5638`; controls `19 cached / 1 fresh`; helper visible/called/VNC `8 / 0 / 8`.
- Force micro: `outputs/v2_5_micro_direct_action_force_20260506_135241/mechanism_40_20260506_135245`; dashboards opened on port `5639`; controls `19 cached / 1 fresh`; helper visible/called/VNC `8 / 8 / 0`; called-subset outcome `-0.1155`; side-effect incidents `1`.
- Decision: dict-payload design negative; next candidate should use flat scalar inputs if direct-side-effect lane is retried.

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

## 2026-05-06 - V2.5 Candidate Pack 2 Contact Lookup 100/250
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Candidate pack registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`, SHA-256 `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`; tools are best3 plus `plan_contact_lookup_query` and `extract_contact_field_from_search_result`.
- Tests: `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_role_factory.py tests/unit/test_state_helper_guidance.py tests/unit/test_sage_run_adapter.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_live_candidate_check.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q` -> `153 passed`.
- Registry check: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json` -> PASS, 5 active entries.
- Frozen100-style manifest: `artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json`; quality pass.
- Frozen100 best3 run: `outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940/validate_100_20260506_200945`; dashboards opened on port `5665`.
- Frozen100 pack run: `outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903/validate_100_20260506_202908`; dashboards opened on port `5666`.
- Direct frozen100 pack-vs-best3: outcome `+0.0255`; canonical `+0.0025`; exact `43 -> 48`; contact subset `+0.1527`; static no-current-helper-fit `48% -> 24%`; runtime/side-effect `0 / 0`.
- Broad250 manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`; quality pass; manifest SHA `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`.
- Broad250 best3 run: `outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037`; dashboards opened on port `5667`; cache mixed `211 cached / 39 fresh`; outcome `0.5626`; delta vs control `+0.1556`; exact delta `+19`; protocol PASS.
- Broad250 pack run: `outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840`; dashboards opened on port `5668`; cache `250 cached / 0 fresh`; outcome `0.5637`; delta vs control `+0.1636`; exact delta `+27`; protocol PASS.
- Direct broad250 pack-vs-best3: outcome `+0.0011`; canonical `+0.0156`; exact `68 -> 72`; contact subset `+0.2167`; static no-current-helper-fit `52.0% -> 46.0%`; relative reduction `11.54%`; runtime/side-effect `0 / 0`.
- Degradation analysis: smaller-run advantage persisted on called contact tasks, but broad250 aggregate was diluted by only 15 contact opportunities and by unrelated best3/no-helper lane regressions. Report: `docs/sage_protocol/v2_5_pack2_contact_lookup_degradation_report.md`.
- Decision label: `continue gap-closure loop`.
- Next action: tighten contact-helper routing/context exposure and continue foundry with another non-overlapping gap lane; Candidate Pack 2 is validated lane progress but not full final gap closure against the original `44.4% -> <=40.0%` reference.

## 2026-05-06 - V2.5 Contact Routing Repair
- Root cause: explicit contact-helper contracts could still fall through to broad provisional birth-family visibility after generic routing deferred, causing non-contact `all_tools` VNC/context pollution in broad250.
- Code repair: `src/sage_ts/runtime/toolsandbox_integration.py` now hides helpers with explicit positive triggers/applicable families when no trigger/family match exists.
- Test added: `tests/unit/test_runtime_routing_scorer.py::test_explicit_contact_lookup_contract_blocks_non_matching_all_tools`.
- Static route probe: `artifacts/summaries/v2_5_contact_routing_contract_repair/route_probe.json`.
- Diagnostic20 manifest: `artifacts/summaries/v2_5_contact_routing_repair20/cohort_manifest.json`; quality pass; 6 contact positives, 14 non-contact/negative cases.
- Diagnostic20 run: `outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721`; dashboards opened on port `5669`; controls `20 cached / 0 fresh`; protocol PASS.
- Diagnostic20 metrics: outcome delta `+0.2699`; canonical delta `+0.0837`; exact delta `+3`; runtime/side-effect `0 / 0`.
- Contact helper visibility after repair: `plan_contact_lookup_query` `6 / 5 / 1 / 14`; `extract_contact_field_from_search_result` `6 / 3 / 3 / 14`.
- Tests: focused routing suite `73 passed`; full targeted suite `154 passed, 2 warnings`; registry check-only PASS for `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`.
- Decision label: `continue gap-closure loop`.

## 2026-05-07 - V2.6 Feedback Packets and Contact Pack Rerun
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Added structured feedback packet exporter: `src/sage_ts/evaluation/feedback_packets.py`, `scripts/export_v2_6_feedback_packets.py`, `tests/unit/test_v2_6_feedback_packets.py`.
- Exported task feedback packets for formal100/250/500/1032, V2.5 broad250 best3/contact-pack, V2.5 contact-routing diagnostic20, and V2.6 contact rerun100 best3/pack under `artifacts/summaries/v2_6_feedback_packets/`.
- Feedback audit decision: `feedback sufficient for tool birth`; feedback mode decision: `feedback mode B wins`.
- Contact pack rerun best3: `outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133`; dashboards opened on port `5672`; control cache `100 cached / 0 fresh`; protocol PASS.
- Contact pack rerun candidate: `outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045`; dashboards opened on port `5673`; control cache `44 cached / 56 fresh` due initial-state-compatible task-level misses, then collected fresh controls; protocol PASS.
- Direct matched candidate-arm comparison over `88` scored scenarios: pack-vs-best3 outcome `-0.0178`, canonical `+0.0408`, exact `30 -> 29`.
- Contact subset comparison over `24` scenarios: outcome `+0.0563`, canonical `+0.1461`.
- Helper contribution: `plan_contact_lookup_query` visible/called/VNC `24 / 15 / 9`, called outcome `+0.5755`; `extract_contact_field_from_search_result` `24 / 9 / 15`, called outcome `+0.6851`; runtime/side-effect `0 / 0`.
- Feedback packet gap metric on rerun100: best3 no-fit `48.0%`, pack no-fit `24.0%`.
- Cross-task packet artifact: `artifacts/summaries/v2_6_cross_task_packets/latest_packets.json`, SHA `c4437da1dadfb9f96f625fdbfb1415fc9991545cc0bda2fed1142e3440415794`.
- User-flagged insufficient-info distance case recorded as a valid minefield zero; current helper-call guard designs are not promotion-ready because a helper call can still be a forbidden trajectory in those tasks.
- Decision label: `continue foundry loop`.
- Next action: score and validate one non-overlapping cross-task candidate design, then run micro20 before additive60.

## 2026-05-07 - V2.6 Unified Final Gap-Closure Matched 250
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded candidate registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`; registry check-only PASS with 6 active entries.
- Candidate-design reports written: `docs/sage_protocol/v2_6_candidate_design_batch_report.md`, `docs/sage_protocol/v2_6_candidate_validation_report.md`, `docs/sage_protocol/v2_6_micro20_feedback_report.md`, `docs/sage_protocol/v2_6_candidate_pack_additive60_report.md`, `docs/sage_protocol/v2_6_gap_closure_100_report.md`, `docs/sage_protocol/v2_6_gap_closure_250_report.md`.
- Generator repair: contact scalar phone normalization and abstain-output contract added to `src/sage_ts/generation/tool_generator.py`; tests updated in `tests/unit/test_tool_generator.py`.
- Accepted scalar candidate: `plan_contact_search_from_scalar_constraint`; micro20 visible/called/VNC `8 / 3 / 5`, called outcome `+0.4222`, runtime/side-effect `0 / 0`.
- Additive60 pack vs best3: outcome `+0.0740`, canonical `+0.0330`, exact `14 -> 13`; pack protocol PASS; no runtime/side-effect incidents.
- Frozen100 expanded vs best3: outcome `+0.0574`, canonical `+0.0538`, exact `29 -> 34`; no-current-helper-fit `64.0% -> 40.0%`; protocol PASS.
- Frozen250 manifest: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`, SHA `5019602d637362a03317ac4349b9b89a2a790ff69bd5a72203d8dad9516f60e6`; quality PASS; 250 scenarios, 33 base families, largest family share `3.2%`.
- Best3 frozen250 run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`; dashboards opened/checked on port `5679`; control cache mixed `190 / 60`; outcome `0.6040`; canonical `0.7838`; exact `59`; protocol PASS.
- Expanded frozen250 run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`; dashboards opened/checked on port `5680`; control cache mixed `222 / 28`; outcome `0.6235`; canonical `0.8060`; exact `59`; protocol PASS.
- Cache note: partial expanded run `outputs/v2_6_gap_closure_250_expanded/validate_250_20260507_032818` was interrupted and not used because it planned only `87 cached / 163 fresh`; rerun used the settled task-level cache plan `222 cached / 28 fresh`.
- Matched frozen250 expanded-vs-best3: outcome `+0.0195`; canonical `+0.0222`; exact `59 -> 59`; runtime exceptions `0`; helper side-effect incidents `0`.
- Feedback packet gap metric: best3 no-current-helper-fit `55.2%`, expanded `45.6%`, relative reduction `17.39%`; feedback insufficient count `0` in both arms.
- New helper contribution: `plan_contact_lookup_query` visible/called/VNC `24 / 15 / 9`, called outcome `+0.6527`; `extract_contact_field_from_search_result` `24 / 7 / 17`, called outcome `+0.6904`; `plan_contact_search_from_scalar_constraint` `74 / 12 / 62`, called outcome `+0.4279`; all side-effect/runtime `0 / 0`.
- Caveat: this is a matched gap-enriched frozen250 success, not a direct claim that the original formal250 absolute no-fit reference `44.4% -> <=40.0%` was met on the original formal cohort.
- Decision label: `gap closure target met`.
- Exact next action: lock final V2.6 matched-gap evidence; optionally run original-formal-manifest 250 or 500/1032 expanded validation if a broader final claim is required.

## 2026-05-07 - V2.6 Evidence Lock, Original250 Expanded Validation, and Expanded500
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`.
- Matched-gap evidence lock report: `docs/sage_protocol/v2_6_matched_gap_evidence_lock_report.md`; matched250 outcome `0.6040 -> 0.6235`; no-current-helper-fit `55.2% -> 45.6%`; relative gap reduction `17.39%`; runtime/side-effect `0 / 0`; protocol PASS.
- Routing audit and repair: `docs/sage_protocol/v2_6_contact_scalar_routing_audit.md`; `_family_match` now ignores connector words and requires stronger meaningful-part overlap; scalar contact planner hidden on unrelated contact/message tasks and shown on declared scalar-contact lookup/remove/search families.
- Original formal250 expanded run: `outputs/v2_6_original_formal250_expanded_rerun/validate_250_20260507_082209`; dashboards opened/checked on port `5682`; cache `250 / 0`; outcome `0.5986`; expanded vs preserved best3 outcome `+0.1249`; canonical vs best3 `+0.0137`; exact `40 -> 41`; feedback no-fit `52.0% -> 46.0%`; runtime/side-effect `0 / 0`; protocol PASS.
- Original formal250 report: `docs/sage_protocol/v2_6_original_formal250_expanded_report.md`; decision `expanded portfolio generalizes to original250`.
- Expanded500 run: `outputs/v2_6_expanded_500/full_benchmark_20260507_090922`; dashboards opened/checked on port `5683`; cache mixed `179 / 321`; outcome `0.6822`; expanded vs preserved best3 500 outcome `+0.1299`; canonical vs best3 `+0.0326`; exact `76 -> 96`; feedback no-fit `67.6% -> 62.8%`; runtime/side-effect `0 / 0`; protocol PASS.
- Expanded500 report: `docs/sage_protocol/v2_6_expanded_500_report.md`; decision `expanded portfolio scale-positive`.
- Feedback packets exported for original250 expanded and expanded500 under `artifacts/summaries/v2_6_feedback_packets/`.
- Final package updated: `artifacts/final_sage_praxis_package/`; added V2.6 reports, `final_evidence_index.md`, and updated limitations.
- Tests/registry checks: `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_v2_6_feedback_packets.py tests/unit/test_dashboard_exporters.py -q` -> `130 passed`; expanded registry check-only PASS; frozen best3 registry check-only PASS.
- Decision label: `expanded portfolio scale-positive; best3 broad claim preserved`.

## 2026-05-07 - V2.6 Current-Code Matched Evidence Campaign
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`.
- Expanded V2.6 registry unchanged: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA-256 `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`.
- Preflight: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json` -> PASS; targeted pytest suite -> `125 passed, 2 warnings`; `git diff --check` -> PASS.
- Original250 best3 command used `--mode validate_250 --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --registry-dir artifacts/registry_frozen_best3_claim --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_original250_best3 --dashboard-port 5684`.
- Original250 best3 run: `outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235`; paired SHA `bf94553bcf4b74eebb4d65dd14c192801a6fa96703a9ce4f79eabc1e8c650c8c`; helper contribution SHA `21ce0effb15f382961666f721d5daba71a91ac16f80317969ad609030a504545`; cache mixed `209 cached / 41 fresh`; outcome `0.6078`; canonical `0.7679`; exact `48`; runtime `0`; protocol PASS.
- Original250 expanded command used same manifest/settings with `--registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack --output-root outputs/v2_6_current_code_original250_expanded --dashboard-port 5685`.
- Original250 expanded run: `outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441`; paired SHA `1793ca3700fa75de42300b16021fd80b07f1b640d836940625119396cc5f74f3`; helper contribution SHA `4d65b558092d499e36c1ef7bcb085418713d0d18259eb9ac9ae59ee11929f533`; cache `250 cached / 0 fresh`; outcome `0.6179`; canonical `0.7395`; exact `40`; runtime `0`; protocol PASS.
- Original250 current-code matched result: expanded-vs-best3 outcome `+0.0100`; canonical `-0.0283`; exact `48 -> 40`; feedback no-current-helper-fit `52.0% -> 46.0%`; relative no-fit reduction `11.54%`; side-effect/runtime `0 / 0`.
- Non-external500 best3 command used `--mode full_benchmark --manifest docs/sage_protocol/manifests/v2_1_formal_500.json --registry-dir artifacts/registry_frozen_best3_claim --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_500_best3 --dashboard-port 5686`.
- Non-external500 best3 run: `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553`; paired SHA `fbfc2f86839d2221925f6eab05a957120c9b7e754659376d5f0d63ea68c2237d`; helper contribution SHA `e3a3a0cb0ac41c7d8da534ec65484762f21e3d69d572bc2fff73b3494d6f2da3`; cache mixed `435 cached / 65 fresh`; outcome `0.6590`; canonical `0.7137`; exact `92`; runtime `0`; protocol PASS.
- Non-external500 expanded command used same manifest/settings with `--registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack --output-root outputs/v2_6_current_code_500_expanded --dashboard-port 5687`.
- Non-external500 expanded run: `outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427`; paired SHA `3ac838638cb1a02188c8b981c2c53ecd4b74d79f241b79593a93582dc023e65e`; helper contribution SHA `e16a0720b94a91ab6017c078b82d745ed5b2cd3d0a39a3b66c19901e51c10351`; cache mixed `467 cached / 33 fresh`; outcome `0.6692`; canonical `0.7362`; exact `93`; runtime `0`; protocol PASS.
- Non-external500 current-code matched result: expanded-vs-best3 outcome `+0.0101`; canonical `+0.0225`; exact `92 -> 93`; feedback no-current-helper-fit `67.6% -> 62.8%`; relative no-fit reduction `7.10%`; side-effect/runtime `0 / 0`.
- Dashboard URLs were HTTP-checked and opened for both original250 arms and both non-external500 arms.
- Feedback packets exported for all four arms under `artifacts/summaries/v2_6_feedback_packets/`.
- Reports written: `docs/sage_protocol/v2_6_current_code_original250_matched_report.md`, `docs/sage_protocol/v2_6_current_code_500_matched_report.md`, `docs/sage_protocol/v2_6_current_code_evidence_synthesis.md`.
- Gap250 current-code rerun deferred because locked matched-gap evidence already exists; expanded 1032 current-code validation deferred for cost/scope because 500 provides broad non-external evidence and 1032 includes sparse/external lanes outside contact-scalar scope.
- Decision label: `expanded portfolio non-harmful but variance-limited`.

## 2026-05-07 - Pre-Final Hardening And Chapter 3 Readiness

- Objective: convert the final audit findings into final-run preflight hardening, reproducibility guardrails, statistical-readiness artifacts, cache/trace documentation, and Chapter 3 methodology preparation.
- Protected assets preserved: `artifacts/registry_frozen_best3_claim/registry_manifest.json`; locked best3/formal evidence; expanded V2.6 registry.
- Code changes:
  - Added final-run preflight: `scripts/preflight_final_run.py`.
  - Added statistical analysis generator: `scripts/write_final_statistical_analysis.py`.
  - Updated `scripts/run_sage_protocol.py` to block diagnostic force-call env leakage for frozen final runs, resolve final routing evidence to disabled by default, support pinned/disabled routing evidence, and record run-affecting `SAGE_*` env vars in `protocol_manifest.json`.
  - Updated `src/sage_ts/runtime/routing_scorer.py` to support explicit routing evidence modes: `auto`, `disabled`, and `pinned`.
  - Updated `src/sage_ts/evaluation/feedback_packets.py` to label cached-control trace completeness.
- Documentation/artifacts:
  - Final-run readiness report: `docs/sage_protocol/final_run_readiness_report.md`.
  - Final preflight config: `docs/sage_protocol/final_run_preflight_config.json`.
  - Versioned methodology heuristics: `docs/sage_protocol/protocol_heuristics_v1.json`.
  - Statistical report: `docs/sage_protocol/final_statistical_analysis_report.md`.
  - Statistical JSON: `artifacts/summaries/final_statistical_analysis/analysis.json`.
  - Chapter 3 methodology prep: `docs/sage_protocol/chapter3_methodology_prep.md`.
  - Trace-audited feedback exports: `artifacts/summaries/v2_6_feedback_packets_trace_audit/`.
- Validation so far:
  - `PYTHONPATH=src:. pytest tests/unit/test_final_run_preflight.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_v2_6_feedback_packets.py -q` -> `36 passed`.
  - `PYTHONPATH=src:. python scripts/write_final_statistical_analysis.py` -> PASS.
  - Development preflight with `--allow-dirty` -> PASS; clean-tree preflight should be rerun after commit with report output outside the repo.
- Decision: `final preflight ready; chapter 3 methodology package ready`.
- Next action: run full targeted validation, registry checks, `git diff --check`, commit, clean-tree preflight, and push.

## 2026-05-11 - Praxis Final-Hardening Registry-Only Formal500 Review

- Objective: audit and reproduce the frozen Praxis BridgePack result against protected best3 and V2.6 under matched final-hardening review conditions.
- Review branch: `review/praxis-final-hardening`.
- Protected-base commit: `2898c7e502ec75ad5e1fc65c5ffe7a80f5605f4a`.
- Experimental source commit: `7793c8ca29ab4e121d302c777c4e4ad273226470`.
- Setup commit used for matched formal runs: `cfe35647dbbb703b4508a709f75dfee0f1f85036`.
- Protected assets preserved: protected best3 registry, locked best3 evidence, locked formal evidence, and final-package claim artifacts were not modified.
- Imported review inputs: best3 reference copy, V2.6 reference copy, Praxis frozen candidate copy, locked Praxis experimental summary, and control-arm task-level baseline cache policy.
- Intentionally not imported: Praxis actor/router bridge policy, final-answer retention changes, scrambled tool-name compatibility changes, side-effect checker changes, scoring changes, and dashboard/export changes.
- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`, SHA `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`.
- Registry hashes:
  - best3 reference: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
  - V2.6 reference: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
  - Praxis frozen BridgePack: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Preflight: `artifacts/praxis_final_hardening/preflight/preflight_registry_only_formal500.json`, SHA `f4913869aa740e2c80fbaf0f50523bff2c1f8b10e8a784574278df2d05e86786`; clean git, registry hashes matched, routing evidence disabled, diagnostic force env vars absent.
- Run controls: generation off; OpenAI response cache disabled; SAGE/candidate task cache off; control cache `use-if-eligible`; routing evidence disabled; no low-quality override; no code or registry changes between matched arms.
- Control cache: `500 cached / 0 fresh` in every arm; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- best3 formal500 run: `outputs/praxis_final_hardening/registry_only/best3_reference_formal500/full_benchmark_20260510_223731`; outcome `0.655285`; run-vs-control outcome lift `0.060413`; canonical `0.722734`; exact successes `94`; runtime exceptions `0`; helper side-effect failures `0`.
- V2.6 formal500 run: `outputs/praxis_final_hardening/registry_only/v2_6_reference_formal500/full_benchmark_20260510_223731`; outcome `0.664286`; run-vs-control outcome lift `0.069414`; canonical `0.713519`; exact successes `89`; runtime exceptions `0`; helper side-effect failures `0`.
- Praxis formal500 run: `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731`; outcome `0.696169`; run-vs-control outcome lift `0.101297`; canonical `0.722681`; exact successes `105`; runtime exceptions `0`; helper side-effect failures `13`.
- Pairwise result: Praxis-vs-best3 outcome diff `+0.040884`, 95% CI `[0.004697, 0.078220]`, p `0.0283`; Praxis-vs-V2.6 outcome diff `+0.031883`, 95% CI `[-0.009376, 0.072576]`, p `0.1199`.
- Safety blocker: Praxis side-effect report `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731/candidate/full_benchmark_candidate_agent_gpt-4o-mini_user_GPT_4_o_2024_05_13_05_10_2026_22_38_10/side_effect_preservation_report.jsonl`, SHA `81bf6ee740368bc83f8444f5c608e108d352f5029533d52695d4b430d5fd1aaa`.
- Reports: `docs/sage_protocol/praxis_final_hardening_review.md`, `docs/sage_protocol/praxis_treatment_dependency_audit.md`, `docs/sage_protocol/praxis_matched_formal500_statistical_report.md`, `docs/sage_protocol/praxis_methodology_delta.md`, `docs/sage_protocol/praxis_final_hardening_blocker_report.md`.
- Machine-readable summary: `artifacts/praxis_final_hardening/praxis_final_hardening_summary.json`.
- Dashboard checks: Praxis standard dashboard and Task Focus dashboard opened in the in-app browser with zero console errors; Task Compare was not generated.
- Treatment classification: registry-only outcome lift reproduced, but not protected-claim ready because helper side-effect preservation failed. A combined registry plus bridge-policy/checker treatment remains plausible but unvalidated.
- Decision label: `BLOCKED: praxis_registry_only_side_effect_preservation_failures`.
- Next action: do not update protected final claim. Redesign failing bridge helpers or audit an explicit combined bridge-policy treatment, then rerun matched formal validation from scratch with zero side-effect failures.

## 2026-05-11 - Praxis Registry-Only Side-Effect Repair And Matched Formal500

- Objective: resolve the Praxis promotion blocker by attempting registry-only helper-contract repair before any combined actor/router bridge-policy treatment.
- Repair branch: `repair/praxis-side-effect-zero`.
- Base commit: `672af8ae6ea13770166e5f0e4e4dc01ece698497`.
- Source review branch: `review/praxis-final-hardening`.
- Experimental source commit reference only: `7793c8ca29ab4e121d302c777c4e4ad273226470`.
- Protected assets preserved: protected best3 registry, locked best3 evidence, locked formal evidence, protected final reports, and final-package claim artifacts were not modified.
- Safety autopsy root cause: mixed `helper_contract_or_bridge_policy_dependency`; contact-update, reminder, and send-message failures were repairable with checker-visible contracts and scrambled-name suppression; relationship batch helper required bridge/checker behavior because natural calls batched planner plus `modify_contact` in the same assistant tool-call message.
- Repair v1 registry: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_registry_only_repair_v1/registry_manifest.json`, SHA `83ec3734dfda2b3ab756e6ba3ed947a3e6a9864b18508a9fa9d75e6dc14aa733`; failed targeted safety because `plan_contact_relationship_batch_update` still triggered same-batch side-effect preservation failure.
- Repair v2 registry: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_registry_only_repair_v2/registry_manifest.json`, SHA `24e5ca815c6f3c11a8b226f10abbfba3216f854a5dcb284df860c4131a01cc35`; 12 active helpers; retired diagnostic helper `plan_contact_relationship_batch_update`.
- Minefield checks: `artifacts/praxis_safety_repair/repair_v2_minefield_checks.json`; 20/20 passed.
- Targeted77 diagnostic: `outputs/praxis_safety_repair/registry_only_repair_v2_targeted77/mechanism_40_20260511_012403`; runtime exceptions `0`; helper side-effect preservation failures `0`; control cache `77 cached / 0 fresh`; outcome delta `+0.244654`.
- Exact13 final-style diagnostic: `outputs/praxis_safety_repair/registry_only_repair_v2_exact13_disabled/mechanism_40_20260511_014626`; runtime exceptions `0`; helper side-effect preservation failures `0`; control cache `13 cached / 0 fresh`; routing evidence disabled; outcome delta `+0.264650`.
- Clean formal preflight: `artifacts/praxis_safety_repair/preflight/preflight_registry_only_repair_v2_formal500.json`, SHA `0a1aa49d166009fac89dde025d0c2b44784cb9f6c6bdd70254d0093225c016fb`.
- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`, SHA `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`.
- Run controls for matched formal500: generation off; OpenAI response cache disabled; candidate/SAGE task cache off; control cache `use-if-eligible`; routing evidence disabled; diagnostic force-call env vars absent; no low-quality override; no code or registry changes between arms.
- Control cache: `500 cached / 0 fresh` in every arm; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- best3 formal500 run: `outputs/praxis_safety_repair/formal500_registry_only_v2/best3_reference_formal500/full_benchmark_20260511_015634`; outcome `0.659956`; run-vs-control outcome lift `0.065084`; canonical `0.704683`; exact successes `90`; runtime/side-effect `0 / 0`.
- V2.6 formal500 run: `outputs/praxis_safety_repair/formal500_registry_only_v2/v2_6_reference_formal500/full_benchmark_20260511_034215`; outcome `0.668039`; run-vs-control outcome lift `0.073167`; canonical `0.728769`; exact successes `97`; runtime/side-effect `0 / 0`.
- Repaired Praxis v2 formal500 run: `outputs/praxis_safety_repair/formal500_registry_only_v2/praxis_repair_v2_formal500/full_benchmark_20260511_064006`; outcome `0.706948`; run-vs-control outcome lift `0.112076`; canonical `0.724125`; exact successes `109`; runtime/side-effect `0 / 0`.
- Pairwise statistics: repaired Praxis-vs-best3 outcome diff `+0.046991`, 95% CI `[0.008387, 0.086278]`, p `0.0187`; repaired Praxis-vs-V2.6 outcome diff `+0.038909`, 95% CI `[0.001856, 0.075806]`, p `0.0463`.
- Helper exposure/calls: best3 visible/called/VNC `203 / 132 / 71`; V2.6 `291 / 161 / 130`; repaired Praxis `530 / 193 / 337`.
- Dashboard checks: repaired Praxis standard and Task Focus dashboards opened in the in-app browser with zero console errors; Task Compare was not generated.
- Reports written: `docs/sage_protocol/praxis_side_effect_repair_report.md`, `docs/sage_protocol/praxis_treatment_classification_final.md`, `docs/sage_protocol/praxis_repaired_matched_formal500_statistical_report.md`.
- Machine-readable artifacts: `artifacts/praxis_safety_repair/praxis_safety_repair_summary.json` SHA `12a6ad783ff62937ba55d70422891a49affca5b1b8ee558fcfab432996b3bfa3`; stats JSON SHA `c5e56fdf6a335c78410a5c8d1bb839484a21ea09421272a74041ef0e03b6c4fb`.
- Treatment classification: registry-only helper-contract repair; no experimental bridge policy, checker behavior, scoring change, or mtime-selected routing evidence was imported.
- Decision label: `READY_FOR_PROTECTED_REVIEW: registry_only_praxis_repair_v2`.
- Next action: prepare a protected final-claim update review for repaired Praxis v2; do not claim the retired relationship batch helper or experimental bridge policy.

## 2026-05-11 - Praxis Combined Bridge-Policy Recovery Diagnostics

- Objective: recover the earlier high-lift Praxis behavior without force calls or leakage by testing the frozen high-lift registry as an explicit registry plus feature-flagged actor/checker bridge-policy treatment.
- Branch: `repair/praxis-combined-bridge-policy`.
- Treatment: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1/registry_manifest.json`, SHA `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`, with `SAGE_PRAXIS_BRIDGE_POLICY=combined`.
- Integrity controls: generation off; candidate task cache off; OpenAI response cache disabled; control cache `use-if-eligible`; routing evidence disabled; no diagnostic force-call env vars; no force calls counted as evidence.
- Dashboard update: imported Task Compare dashboard and made it the default dashboard for future runs. It reports dark-mode run progress, total tasks, paired completed tasks as `min(baseline completed, SAGE completed)`, score lift, outcome lift, and clickable generated-tool contribution details.
- Exact13 safety diagnostic: `outputs/praxis_combined_bridge_policy/exact13_safety/mechanism_40_20260511_100905`; control cache `13 cached / 0 fresh`; runtime exceptions `0`; generated-tool failures `0`; no side-effect preservation report emitted; canonical delta `+0.188655`; outcome delta `+0.352609`.
- Broad60 diagnostic: `outputs/praxis_combined_bridge_policy/formal500_order_broad60/mechanism_60_20260511_101421`; control cache `60 cached / 0 fresh`; canonical `0.695 -> 0.782`, delta `+0.087`, relative lift `+12.5%`; outcome `0.606 -> 0.751`, delta `+0.145`, relative lift `+24.0%`; natural generated-tool called scenarios `26`; runtime exceptions `0`; generated-tool failures `0`.
- Broad60 safety note: this run started before the setter-`None` actor-policy/checker repair and emitted one side-effect checker row for `plan_device_state_action_sequence_v3` on `cellular_off`. Autopsy found the original setter had succeeded and returned `None`; the actor misread this as failure and retried. A repaired checker fallback reclassifies that existing trajectory as not a preservation failure, but the run itself remains pre-repair and should not be used as claim evidence.
- Setter safety diagnostic after repair: `outputs/praxis_combined_bridge_policy/cellular_off_safety1/mechanism_12_20260511_102820`; control cache `1 cached / 0 fresh`; SAGE canonical `0.937`; SAGE outcome `1.000`; no generated-tool call; runtime exceptions `0`; side-effect preservation rows `0`.
- Formal-order 61-100 holdout40 after repair: `outputs/praxis_combined_bridge_policy/formal500_order_061_100_broad40/mechanism_40_20260511_102941`; control cache `40 cached / 0 fresh`; canonical `0.592 -> 0.618`, delta `+0.026`, relative lift `+4.4%`; outcome `0.599 -> 0.763`, delta `+0.164`, relative lift `+27.3%`; natural generated-tool called scenarios `15`; runtime/side-effect `0 / 0`.
- Disjoint first100 aggregate: canonical `0.654 -> 0.716`, delta `+0.063`, relative lift `+9.6%`; outcome `0.603 -> 0.756`, delta `+0.153`, relative lift `+25.3%`; natural generated-tool called scenarios `41`; runtime exceptions `0`.
- Machine summary: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_first100_summary.json`, SHA `9f0447a7e4fbab38a3fd8e4b13ee3aaffa5502aed93ffb34d7b4ec99ecde211c`.
- Clean broad60 v2 policy-repair run: `outputs/praxis_combined_bridge_policy/formal500_order_broad60_v2_policy_repair/mechanism_60_20260511_113538`; control cache `60 cached / 0 fresh`; canonical `0.695 -> 0.751`, delta `+0.056`, relative lift `+8.0%`; outcome `0.606 -> 0.783`, delta `+0.177`, relative lift `+29.2%`; natural generated-tool called scenarios `24`; runtime/side-effect `0 / 0`.
- Clean formal-order 61-100 holdout40 v2 policy-repair run: `outputs/praxis_combined_bridge_policy/formal500_order_061_100_broad40_v2_policy_repair/mechanism_40_20260511_115212`; control cache `40 cached / 0 fresh`; canonical `0.592 -> 0.681`, delta `+0.089`, relative lift `+15.1%`; outcome `0.599 -> 0.656`, delta `+0.057`, relative lift `+9.4%`; natural generated-tool called scenarios `15`; runtime/side-effect `0 / 0`.
- Clean first100 v2 same-code aggregate: canonical `0.654 -> 0.723`, delta `+0.069`, relative lift `+10.6%`; outcome `0.604 -> 0.737`, delta `+0.133`, relative lift `+22.0%`; exact successes `5 -> 20`; canonical gains/regressions `59 / 28`; outcome gains/regressions `40 / 16`; runtime exceptions `0`; no side-effect preservation reports found.
- Machine summary v2: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_first100_v2_same_code_summary.json`, SHA `fd279d109437c4bc361595efb8b52efdfe4b2c83829dbe1ec5017e54260d6ae3`.
- Validation: registry hashes matched for best3 reference copy, V2.6 reference copy, and Praxis combined registry; registry check-only PASS for 22 active entries; focused unit tests `35 passed, 2 warnings`; dashboard browser check showed Task Compare dark mode with `Run Progress 40/40` and zero console errors; `git diff --check` PASS.
- Report: `docs/sage_protocol/praxis_combined_bridge_policy_recovery_report.md`.
- Decision label: `PROMISING_BUT_NOT_CLAIM_READY: combined_treatment_requires_clean_formal_rerun`.
- Next action: commit the dashboard/bridge/checker repairs, then run a clean same-code formal100 or formal500 with Task Compare default and zero side-effect rows before any claim update.

## 2026-05-11 - Praxis Bridge-Policy RapidAPI Cache Recovery Gate

- Objective: continue the combined-treatment recovery after the quota-limited RapidAPI path blocked location-reminder tasks, while keeping SAGE/candidate task evidence fresh and non-forced.
- External-service cache installed locally at ignored path `.secrets/rapid_api_cache.json` from `../toolsandbox-sage-gap-closure-lab/.secrets/rapid_api_cache.json`; SHA-256 `3ed7732443c44d7d26e0f46ac32fa2e09fc773278368c6f13131021afafdbf25`; entry count `71`.
- Integrity classification: ToolSandbox external-service response fixture only. It is not SAGE task cache, does not contain labels or expected answers, and was used in `read_only` mode so misses fail visibly rather than falling through to live RapidAPI calls.
- Verified exact no-key cache hit: `search_location_around_lat_lon("Whole Foods on Stevens Creek")` returned `Whole Foods Market, 20955 Stevens Creek Blvd, Cupertino, CA 95014`.
- Gap12 v3 bridge-repair run: `outputs/praxis_combined_bridge_policy/bridge_recovery_gap12_v3_bridge_repair_rapid_cache/mechanism_12_20260511_164415`; control cache `12 cached / 0 fresh`; canonical `0.644 -> 0.886`, delta `+0.242`, relative lift `+37.6%`; outcome `0.348 -> 0.869`, delta `+0.520`, relative lift `+149.3%`; visible/called generated-tool scenarios `11 / 11`; runtime/generated-tool failures `0 / 0`.
- Formal-order broad60 v4 run: `outputs/praxis_combined_bridge_policy/formal500_order_broad60_v4_bridge_repair_rapid_cache/mechanism_60_20260511_164637`; control cache `60 cached / 0 fresh`; generation off; candidate task cache off; OpenAI response cache disabled; routing evidence disabled; diagnostic force env vars absent.
- Broad60 v4 metrics: canonical `0.695 -> 0.821`, delta `+0.126`, relative lift `+18.1%`; outcome `0.606 -> 0.916`, delta `+0.310`, relative lift `+51.2%`; canonical gains/regressions/preserved `43 / 9 / 8`; outcome gains/regressions/preserved `37 / 3 / 7`; generated-tool visible/called/attempted scenarios `39 / 27 / 27`; runtime/generated-tool failures `0 / 0`.
- Broad60 v4 dashboard default: `http://127.0.0.1:62538/outputs/praxis_combined_bridge_policy/formal500_order_broad60_v4_bridge_repair_rapid_cache/mechanism_60_20260511_164637/dashboard/task_compare.html`.
- Machine summary: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_broad60_v4_bridge_repair_rapid_cache_summary.json`, SHA-256 `c58b45cd67f5b6ff714f3f7569fc3c5e71752880e763eedebdd54abf9f89ea07`.
- Same-slice comparison: prior high Praxis formal500 on these same 60 formal-order tasks had canonical lift `+9.3%` and outcome lift `+46.4%`; the v4 broad60 gate exceeded both while preserving zero runtime/generated-tool failures.
- Validation: focused role/policy/RapidAPI-cache tests `35 passed, 2 warnings`; cache smoke passed without `RAPID_API_KEY`.
- Decision label: `ON_TRACK_FOR_SCALE_GATE: combined_treatment_broad60_exceeds_prior_high_same60`.
- Next action: update docs and commit; next spend should be a clean same-code 100 or 250 gate, not an immediate formal500, unless budget and preflight are explicitly cleared.

## 2026-05-11 - Praxis Combined Bridge-Policy Formal500 V2

- Objective: validate whether restoring the declared SAGE bridge policy recovers the prior high-lift Praxis behavior without force calls, label leakage, scenario hard-coding, or candidate task-cache reuse.
- Branch: `repair/praxis-combined-bridge-policy`.
- Treatment classification: frozen Praxis registry plus feature-flagged actor/checker bridge policy; not registry-only.
- Registry: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1/registry_manifest.json`, SHA `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`.
- Runtime flag: `SAGE_PRAXIS_BRIDGE_POLICY=combined`.
- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`.
- Run root: `outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`.
- Dashboard default: `http://127.0.0.1:62543/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html`.
- Integrity controls: generation off; candidate task cache off; OpenAI response cache disabled; control cache `use-if-eligible`; routing evidence disabled; diagnostic force env vars absent; RapidAPI external-service cache read-only; `POLARS_MAX_THREADS=1` used after a diagnostic showed a prior local Polars stall.
- Control cache: `500 cached / 0 fresh`; cache manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- Formal500 metrics: canonical `0.670025 -> 0.757369`, delta `+0.087344`, relative lift `+13.04%`; outcome `0.594872 -> 0.839943`, delta `+0.245071`, relative lift `+41.20%`.
- Prior high-run comparison: exceeded the cited prior `0.670 -> 0.751` canonical (`+12.1%`) and `0.595 -> 0.813` outcome (`+0.219`) dashboard result.
- Paired run-vs-control statistics: canonical delta 95% bootstrap CI `[+0.063776, +0.111818]`, sign-flip p `<0.0001`; outcome delta 95% bootstrap CI `[+0.213219, +0.276059]`, sign-flip p `<0.0001`.
- Gains/regressions/preserved: canonical `316 / 114 / 70`; outcome `252 / 41 / 91`.
- Helper usage: natural helper-called scenarios `230`; helper-attempted scenarios `208`; helper failures `0`; runtime exceptions `0`; helper side-effect incidents `0`.
- Machine-readable summary: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_bridge_repair_rapid_cache_polars1_summary.json`, SHA `060d3ba14ae1b8b8d15290d8286092a68053347fd207e46ade89c5fba0cc61e6`.
- Machine-readable statistics: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_statistics.json`, SHA `e064e9f3cec303d2a657063132549e8cfda2fdb1a946e0405649449ca21ddf6f`.
- Gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_gap_packets.json`, SHA `708abc10ec97a2bc36f703a27702abbd50dcdf39b3dc4f265ff08a52dd03db60`.
- Leading residual bucket after formal500: `contact_lookup_update_search_crud` with 140 tasks, 17 outcome regressions, negative outcome mass `4.606`, 32 canonical regressions, negative canonical mass `8.565`, and 62 no-visible-helper cases.
- Next candidate tool family: `prepare_contact_lookup_or_update_action_v2`, with minefields for duplicate names, missing phone/relationship fields, missing update values, ambiguous message-counterparty evidence, and absent original side-effect tools.
- Reports updated: `docs/sage_protocol/praxis_combined_bridge_policy_recovery_report.md`, `docs/sage_protocol/praxis_bridge_policy_methodology.md`, `docs/sage_protocol/praxis_combined_bridge_policy_formal500_report.md`, `docs/sage_protocol/praxis_next_gap_and_self_evolving_sage_plan.md`, and `docs/sage_protocol/current_state.md`.
- Decision label: `PROMISING_COMBINED_TREATMENT_FORMAL500_POSITIVE_NOT_PROTECTED_CLAIM_READY`.
- Next action: run a dedicated matched ablation under the same committed runtime with best3, V2.6, Praxis registry-only repair v2, and Praxis combined bridge-policy v2 before any protected final-claim update.

## 2026-05-13 - Chapter 3 SAGE Praxis Figure Package

- Objective: prepare Chapter 3 and peer-review visual methodology assets for the current SAGE Praxis self-evolving system; first sketch-level figures were replaced with architecture-grade system-design diagrams.
- Branch: `codex/self-evolving-sage-mini60`.
- Status comment: SAGE Praxis with true self-evolution working is the current main SAGE system going forward for methodology drafting and future validation campaigns; protected final claims remain separate until locked matched review.
- Figure renderer: `scripts/render_sage_methodology_diagrams.py`.
- Figure index: `docs/sage_protocol/chapter3_methodology_figures.md`.
- Generated assets:
  - `docs/sage_protocol/figures/sage_toolsandbox_system_overview.svg` and `.png`
  - `docs/sage_protocol/figures/sage_internal_components_zoom.svg` and `.png`
  - `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.svg` and `.png`
  - `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg` and `.png`
- Documentation updated: `README.md`, `docs/sage_protocol/chapter3_methodology_prep.md`, and `docs/sage_protocol/current_state.md`.
- Decision label: `METHODOLOGY_FIGURE_PACKAGE_READY_FOR_CHAPTER_3_DRAFTING`.

## 2026-05-21 - Standalone SAGE CyberGym Batched Live Portability Smoke

- Objective: verify that standalone SAGE can operate on a new benchmark environment using bounded four-task batches, without CyberGym-specific generated-helper hard-coding or hidden-label/reference-PoC access.
- Branch: `codex/sage-standalone-agent`.
- Run root: `outputs/cybergym_live_sage/batched20_generic_visible_v2_20260521_102125`.
- Dashboard: `outputs/cybergym_live_sage/batched20_generic_visible_v2_20260521_102125/dashboard/task_compare.html`.
- Registry: `artifacts/cybergym_live_sage/batched20_registry_generic_visible_v2/sage_registry.json`, SHA-256 `93a6444a7a1225d4f4aab79a8237d5add07ed082176618ec4fa4823b440437e7`.
- Machine-readable summary: `artifacts/sage_standalone/cybergym_batched20_generic_visible_v2_summary.json`, SHA-256 `20bab3b048ccda1a21600f775dbd411d855ef7878a697af2dd68b1c5333edbb6`.
- Run summary SHA-256: `84bc00e440ea620a401340bf69d880bdfe67003e88cc9d4345673489368d7759`; batched summary SHA-256 `fb491016ee5b26b5081e15fdfa8be6986d148439ca22a825a06406e6bc36143d`; dashboard data SHA-256 `03b9af70d54966bf82ea4c75d188057c97dc6938559e0aae97e9a8a9a5777233`.
- Execution mode: `cybergym_live_level1_submit_vul_batched`; official task assets generated with CyberGym's own task generator; live local `/submit-vul` verifier used; fix-side verification not run.
- Batch method: `20` tasks in five batches of `4`; batch work directories and runner Docker images cleared by default after each batch.
- Baseline policy: fixed four-byte PoC, `1/20` success.
- SAGE policy: empty generated-helper registry at start; deterministic generic `visible_text_candidate_planner`; no OpenAI generation calls; configured model metadata `gpt-4o-mini`; SAGE `4/20` success.
- Lift: absolute task-completion lift `+15.0 pp`; relative lift `+300.0%` over the fixed-PoC baseline.
- Lifecycle: gaps observed `17`; tools born/accepted/reused `1 / 1 / 20`; birth-task retries/successes `1 / 1`; retained helper decision `refine`.
- Leakage controls: helper received only visible descriptions, visible README/instructions, bounded summaries from visible `repo-vul.tar.gz` source artifacts, and prior live submit feedback. It did not receive hidden labels, reference PoCs, expected answers, task-specific helper constants, or hard-coded CyberGym task IDs.
- Integrity: integrity passed; issues `0`; helper side effects `0`; generated helper only prepared candidate strings, while the adapter retained responsibility for environment submissions.
- Interpretation: meaningful portability proof for the standalone SAGE loop, not final CyberGym benchmark evidence. The next generalization work should add environment-general source/harness inventory, input-format inference, feedback classification, mutation/minimization, and repair policy rather than CyberGym-specific branches.
- Decision label: `PORTABILITY_SMOKE_POSITIVE_REFINE_FOR_BROADER_CYBERGYM_VALIDATION`.

## 2026-05-21 - Standalone SAGE Candidate-Feedback 20-Task CyberGym Check

- Objective: respond to the observation that 8 samples are too few to observe
  self-evolution, then test whether helper birth, repair, retention, and reuse
  produce a stronger signal across 20 CyberGym live tasks.
- Branch: `codex/sage-standalone-agent`.
- Run root:
  `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521`.
- Dashboard:
  `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521/dashboard/task_compare.html`.
- Machine summary:
  `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521/batched_live_summary.json`,
  SHA-256 `01ea9a4ea84ac0086ea758ee6a96fe24a423aa6a6a44fef60a9a84187bf04d2d`.
- Baseline cache: `artifacts/cybergym_live_sage/baseline_cache.json`,
  SHA-256 `64f7a49421730d029783fcb66bb3e7f0cedd6ce74f60e86550586d37fe10945a`;
  controls `20 cached / 0 fresh`; SAGE fresh.
- Baseline policy: cached `gpt-4o-mini` visible-artifact LLM baseline,
  same task IDs and candidate budget.
- SAGE policy: empty generated-helper registry at start, deterministic generic
  helper generation, no hidden labels, no reference PoCs, no expected answers,
  no task-specific hard-coded constants.
- Result: baseline `1/20`; SAGE `4/20`; absolute task-completion lift
  `+15.0 pp`.
- Lifecycle: tools born/accepted/reused `7 / 7 / 116`; repair
  attempts/refined tools `4 / 4`; birth-task retries `11`; integrity issues
  `0`.
- Interpretation: the earlier 8-task checks were too short to judge evolution.
  The 20-task run shows useful lift emerging late after multiple birth and repair
  cycles. This remains experimental live `/submit-vul` evidence, not official
  CyberGym final evidence because fix-side verification is not yet run.
- Decision label:
  `CYBERGYM_EVOLUTION_SIGNAL_REQUIRES_20_TASK_MINIMUM_CONTINUE_GENERAL_REPAIR`.

## 2026-05-21 - Standalone SAGE Maintenance Checks After CyberGym Repair

- Objective: verify that the CyberGym candidate-feedback and lifecycle changes
  did not regress the other standalone environments.
- MiniGrid run:
  `outputs/sage_agent_standalone/minigrid_lift_maintenance_12_20260521`;
  dashboard
  `outputs/sage_agent_standalone/minigrid_lift_maintenance_12_20260521/dashboard/task_compare.html`;
  summary SHA-256
  `5a5c0af188ee31773e251963fbb3888fcbb7ec84d6a5fad2d043ef43c5979b95`.
- MiniGrid result: LLM baseline `4/12`; SAGE `12/12`; tools
  born/accepted/reused `1 / 1 / 12`; integrity passed.
- ToolSandbox adapter smoke run:
  `outputs/sage_agent_standalone/toolsandbox_lift_maintenance_3_20260521_smoke`;
  dashboard
  `outputs/sage_agent_standalone/toolsandbox_lift_maintenance_3_20260521_smoke/dashboard/task_compare.html`;
  summary SHA-256
  `fea45a95f1cb6c211ef2d01afbd57a969fb925393be79045e73aa60895a45841`.
- ToolSandbox result: smoke baseline `0/2`; SAGE `2/2`; one helper born and
  reused; birth-task retry success `1`; integrity passed. The standalone smoke
  runner does not yet implement an LLM baseline for this mini adapter, so this is
  lifecycle preservation evidence only.
- Validation: Python compile passed; `pytest` standalone/protocol tests
  `27 passed`; `ruff check` passed; `ruff format --check` passed; `git diff
  --check` passed.
- Decision label:
  `CYBERGYM_REPAIR_PRESERVES_MINIGRID_AND_TOOLSANDBOX_STANDALONE_SMOKES`.

## 2026-05-21 - Standalone SAGE Four-Environment Live40 Validation

- Objective: add one more benchmark and verify that the importable standalone
  SAGE agent can run against four different environments with real baseline and
  SAGE arms where available: ToolSandbox, CyberGym, MiniGrid, and BIG-Bench
  Hard.
- Branch: `codex/sage-standalone-agent`.
- New benchmark: BIG-Bench Hard from the public repository
  `https://github.com/suzgunmirac/BIG-Bench-Hard`, cloned locally under
  `external/BIG-Bench-Hard` at commit
  `9ee07bd481feebf959a6b59d61ea57bdcf30964d`.
- Code changes: added `BBHAdapter`, exported it from `sage_agent.adapters`,
  added a BBH exact-answer LLM baseline path to `scripts/run_sage_agent_smoke.py`,
  and added a fixture-based BBH unit test proving private targets are not
  exposed through SAGE-facing task specs.
- Machine-readable summary:
  `artifacts/sage_agent_standalone/final_four_env_live40_summary_20260521.json`,
  SHA-256
  `5987f4c09d845ac34c9c89e9acb8139cc5e116a0d2774ab0b978fc526065a2b2`.
- ToolSandbox run:
  `outputs/sage_agent_standalone/toolsandbox_verify40_self_evolving_policy_20260521/mechanism_40_20260521_175250`;
  dashboard
  `outputs/sage_agent_standalone/toolsandbox_verify40_self_evolving_policy_20260521/mechanism_40_20260521_175250/dashboard/task_compare.html`.
- ToolSandbox result: `40 cached / 0 fresh` controls; fresh SAGE; score
  `0.647929 -> 0.874999`, delta `+0.227070`; outcome
  `0.473734 -> 0.907297`, delta `+0.433562`; exact successes `3 -> 24`;
  generated registry size `14`; runtime exceptions `0`.
- CyberGym run:
  `outputs/cybergym_live_sage/final_agent_cybergym_live40_20260521`;
  dashboard
  `outputs/cybergym_live_sage/final_agent_cybergym_live40_20260521/dashboard/task_compare.html`.
- CyberGym result: ten four-task live `/submit-vul` batches; cached LLM
  baseline `1/40` with `40 cached / 0 fresh` controls; fresh SAGE `4/40`;
  tools born/accepted/reused `12 / 12 / 237`; repair attempts/refined tools
  `9 / 9`; integrity issues `0`. This remains portability evidence rather
  than final CyberGym benchmark evidence because fix-side verification is not
  run.
- MiniGrid run:
  `outputs/sage_agent_standalone/minigrid_live40_20260521`; dashboard
  `outputs/sage_agent_standalone/minigrid_live40_20260521/dashboard/task_compare.html`.
- MiniGrid result: LLM baseline `21/40`; SAGE `40/40`; tools
  born/accepted/reused `1 / 1 / 40`; integrity issues `0`.
- BIG-Bench Hard run:
  `outputs/sage_agent_standalone/bbh_live40_20260521`; dashboard
  `outputs/sage_agent_standalone/bbh_live40_20260521/dashboard/task_compare.html`.
- BIG-Bench Hard result: LLM exact-answer baseline `16/40`; SAGE `40/40`;
  tools born/accepted/reused `1 / 1 / 40`; integrity issues `0`. The 40-task
  mix included `10` each from `boolean_expressions`,
  `multistep_arithmetic_two`, `dyck_languages`, and `word_sorting`. One helper
  was expected because the generated symbolic exact-answer helper generalized
  across those visible public formats; target answers remained private inside
  the adapter scorer.
- Default run conditions: standalone smoke and live scripts keep
  `gpt-4o-mini` as the enforced default model and open Task Compare at run
  start unless `--no-dashboard-open` is explicitly supplied. ToolSandbox
  generation-enabled runs use `--sage-policy self-evolving-praxis` or `auto`,
  which records the high-lift self-evolving defaults.
- Leakage controls: SAGE-facing task specs, gap signals, helper code, and
  registry metadata did not include hidden labels, expected answers, reference
  PoCs, or prior SAGE traces. BBH targets are private to the adapter scorer;
  CyberGym helpers receive only visible task assets and live submit feedback.
- Decision label:
  `STANDALONE_SAGE_FOUR_ENVIRONMENT_AGENT_BASE_READY_FOR_METHOD_CHAPTER_WITH_CYBERGYM_LIMITATION`.

## 2026-05-21 - Source-Artifact CyberGym Repair And Fixed-Side Verification Smoke

- Objective: improve CyberGym performance through an environment-general
  source-artifact candidate-planning capability, while maintaining ToolSandbox,
  MiniGrid, and BBH behavior and adding fixed-side verification for CyberGym
  scoring.
- Branch: `codex/sage-standalone-agent`.
- OpenAI API status: `OPENAI_API_KEY` was available from a local env file and
  was used for the fresh LLM baseline in the fixed-side two-task CyberGym smoke.
  The secret was not printed.
- Code changes: added generic gap key
  `source_boundary_value_candidate_planning`; added helper family
  `source_boundary_candidate_planner`; added fixed-side CyberGym scoring via
  `--fixed-side-check`; separated fixed-side baseline cache keys from legacy
  vulnerable-only cache entries; fixed dashboard zero-baseline lift display to
  show an approximate relative lift using a documented `0.100` denominator
  floor.
- Machine-readable summary:
  `artifacts/sage_agent_standalone/source_boundary_fixed_side_maintenance_summary_20260521.json`.
  SHA-256 `6ffda4082984fe19c52d9d818e040a086a4739732d3986cb55cd34b7b42c66ce`.
- CyberGym fixed-side OpenAI-key smoke:
  `outputs/cybergym_live_sage/openai_key_fixed_side_smoke2_20260521`;
  dashboard
  `outputs/cybergym_live_sage/openai_key_fixed_side_smoke2_20260521/dashboard/task_compare.html`.
- CyberGym fixed-side OpenAI-key result: LLM baseline `0/2`, SAGE `1/2`;
  baseline cache `off`; fixed-side verification `true`; tools
  born/accepted/reused `5 / 5 / 23`; repair attempts/refined tools `1 / 1`;
  birth-task retry successes `1`; integrity issues `0`.
- CyberGym fixed-side cached-control smoke:
  `outputs/cybergym_live_sage/source_boundary_fixed_side_direct_v1_4_20260521`;
  result baseline `0/4`, SAGE `1/4`; fixed-side verification `true`;
  integrity issues `0`.
- Maintenance checks: ToolSandbox smoke
  `outputs/sage_agent_standalone/toolsandbox_source_boundary_maintenance_2_20260521`
  SAGE `2/2`; MiniGrid
  `outputs/sage_agent_standalone/minigrid_source_boundary_maintenance_12_20260521`
  baseline `7/12`, SAGE `12/12`; BBH
  `outputs/sage_agent_standalone/bbh_source_boundary_maintenance_12_20260521`
  baseline `5/12`, SAGE `12/12`.
- Validation: standalone unit tests `13 passed`; Python compile passed for the
  touched SAGE files and CyberGym runner; `git diff --check` passed.
- Decision label:
  `SOURCE_ARTIFACT_PLANNER_IMPROVES_CYBERGYM_FIXED_SIDE_SMOKE_WITH_GENERALIZATION_MAINTAINED`.

## 2026-05-21 - CyberGym Fixed-Side Validate20 And Image Cache Speed Repair

- Objective: scale the fixed-side CyberGym check beyond the initial smoke while
  keeping validation accurate and reducing repeated Docker setup cost.
- Branch: `codex/sage-standalone-agent`.
- Completed run:
  `outputs/cybergym_live_sage/source_boundary_fixed_side_validate20_20260521`;
  dashboard:
  `outputs/cybergym_live_sage/source_boundary_fixed_side_validate20_20260521/dashboard/task_compare.html`.
- Protocol: `gpt-4o-mini`; baseline `llm`; baseline cache
  `use-if-eligible`; fixed-side verification `true`; generation starts from an
  empty generated-helper registry via `--reset-registry`; SAGE candidate arm
  fresh; visible CyberGym task assets only; live submit feedback only.
- Result: baseline `2/20`, SAGE `5/20`; absolute lift `+15.0 pp`; relative
  lift `+150.0%`; baseline cache `4 cached / 16 fresh`; tools
  born/accepted/reused `5 / 5 / 95`; repair attempts/refined tools `1 / 1`;
  birth-task retry successes `1`; integrity issues `0`.
- Interpretation: larger fixed-side validation confirms real CyberGym lift, but
  absolute success is still low and helper lifecycle marks the generated
  CyberGym helpers as `refine`, not `scale`.
- Speed repair: `scripts/run_cybergym_live_batched_sage.py` now retains Docker
  images by default, skips exact existing images, and pulls the batch's
  vulnerable/fixed images in parallel with `--image-pull-workers`. This is an
  environment setup cache only; it does not expose labels, reference PoCs,
  expected answers, or hidden task facts to SAGE.
- Post-repair real-task verification:
  `outputs/cybergym_live_sage/image_cache_speed_verify4_20260521` completed
  on four official CyberGym Level 1 tasks with live task generation, live
  submit server, fixed-side scoring, cached baseline controls, and a fresh
  empty generated-helper registry. Result: baseline `0/4`, SAGE `1/4`; tools
  born/accepted/reused `5 / 5 / 31`; birth-task retry successes `1`;
  integrity issues `0`. A direct image-cache probe confirmed retained images
  were detected as cached for `n132/arvo:1065-vul` and `n132/arvo:1065-fix`.
- Machine-readable summary:
  `artifacts/sage_agent_standalone/cybergym_fixed_side_validate20_speed_repair_summary_20260521.json`.
  SHA-256 `329996c1020f1f2cd0c76d6e1f13e78261f87970c84e30e55910540da08cfca7`.
- Validation: standalone unit tests `14 passed`; Python compile passed for the
  touched runner/SAGE files; Ruff check and format check passed for the touched
  Python files; `git diff --check` passed.
- Decision label:
  `CYBERGYM_FIXED_SIDE_VALIDATE20_CONFIRMS_LIFT_AND_IMAGE_CACHE_SPEED_REPAIR_READY_FOR_VALIDATION`.

## 2026-05-22 - CyberGym Evidence-Weighted Routing Phase

- Objective: test whether SAGE can improve CyberGym generalization by using its
  own natural-use contribution evidence for helper routing, without manually
  exposing tools or adding CyberGym-specific hidden knowledge.
- Branch: `codex/sage-standalone-agent`.
- Code changes: candidate-helper routing now ranks by public task fit plus
  SAGE's own winning-candidate helper evidence; validation also supports
  fragment-based candidate-list assertions for helpers that preserve visible
  source or artifact fragments inside longer candidates.
- Negative gate: `outputs/cybergym_live_sage/next_phase_evidence_weighted_probe8_20260522`
  tested task-relevance ranking as part of the balanced default and regressed
  to SAGE `1/8`, so that ranking was not promoted.
- Negative gate: `outputs/cybergym_live_sage/next_phase_context_aware_probe8_20260522`
  tested task-relevance ranking as explicit `context-aware` and also scored
  SAGE `1/8`, so it remains an experiment only.
- Positive preservation gate:
  `outputs/cybergym_live_sage/next_phase_route_only_validate20_20260522`;
  dashboard:
  `outputs/cybergym_live_sage/next_phase_route_only_validate20_20260522/dashboard/task_compare.html`.
- Protocol: `gpt-4o-mini`; baseline `llm`; baseline cache
  `use-if-eligible`; fixed-side verification `true`; generation starts from an
  empty generated-helper registry via `--reset-registry`; SAGE candidate arm
  fresh; visible CyberGym task assets and live submit feedback only.
- Result: baseline `1/20`, SAGE `5/20`; absolute lift `+20.0 pp`; relative
  lift `+400.0%`; baseline cache `20 cached / 0 fresh`; tools
  born/accepted/reused `13 / 13 / 158`; rejected tools `0`; repair/refine
  `3 / 1`; birth-task retry successes `1`; integrity issues `0`.
- Maintenance checks: ToolSandbox standalone smoke
  `outputs/sage_agent_standalone/next_phase_preserve_toolsandbox_20_20260522`
  SAGE `2/2`; MiniGrid
  `outputs/sage_agent_standalone/next_phase_preserve_minigrid_20_20260522`
  SAGE `20/20`; BBH
  `outputs/sage_agent_standalone/next_phase_preserve_bbh_20_20260522`
  SAGE `15/20`; all had integrity issues `0`.
- Machine-readable summary:
  `artifacts/sage_agent_standalone/next_phase_evidence_weighted_routing_summary_20260522.json`.
  SHA-256 `14fd07eda48120b85c4f53214aff1264f52c5d7bff3f19e4fb7ed8b6897f2ba5`.
- Interpretation: evidence-weighted routing is safe and preserves the known
  CyberGym first-20 fixed-side curve, but it does not exceed it. The remaining
  bottleneck is candidate quality and candidate-budget allocation, not helper
  visibility or initial gap detection.
- Decision label:
  `EVIDENCE_WEIGHTED_ROUTING_PRESERVES_CYBERGYM_REFERENCE_BUT_DOES_NOT_CLOSE_NEXT_GAP`.

## 2026-05-23 - CyberGym Public Execution-Search Gap-Closure Phase

- Objective: close the next CyberGym portability gap by improving candidate
  quality through a general public execution-search helper class, while keeping
  SAGE free of labels, reference PoCs, fixed-side discovery, scenario-ID
  hard-coding, or prior-outcome leakage.
- Branch: `codex/sage-standalone-agent`.
- Code changes: `src/sage_agent/adapters/cybergym_live.py` now builds bounded
  public vulnerable-side search corpora from generated candidates, direct
  visible fixtures, nested public seed archives, and generic format probes; it
  supports libFuzzer, Honggfuzz, and AFL handoff through public wrapper/runtime
  inspection. `scripts/run_cybergym_live_batched_sage.py` now rejects
  incomplete materialized task caches with zero-byte `repo-vul.tar.gz` and
  redownloads visible public source archives.
- Primary run:
  `outputs/cybergym_live_sage/cybergym_public_search_validcache_first20_20260523`;
  dashboard:
  `outputs/cybergym_live_sage/cybergym_public_search_validcache_first20_20260523/dashboard/task_compare.html`.
- Primary result: cached baseline `1/20`, SAGE `7/20`; absolute lift `+30.0`
  percentage points; relative lift `+600.0%`; tools born/accepted/reused
  `19 / 19 / 221`; rejected tools `0`; repair attempts `2`;
  birth-task retry successes `1`; integrity issues `0`; zero-byte public source
  archives in run output `0`.
- Larger validation:
  `outputs/cybergym_live_sage/cybergym_public_search_validcache_first40_20260523`;
  dashboard:
  `outputs/cybergym_live_sage/cybergym_public_search_validcache_first40_20260523/dashboard/task_compare.html`.
- Larger result: cached baseline `1/40`, SAGE `10/40`; absolute lift `+22.5`
  percentage points; relative lift `+900.0%`; controls `40 cached / 0 fresh`;
  tools born/accepted/reused `21 / 21 / 399`; rejected tools `0`; repair
  attempts `2`; birth-task retry successes `1`; integrity issues `0`;
  zero-byte public source archives in run output `0`.
- Prior same-window reference:
  `outputs/cybergym_live_sage/next_phase_route_only_validate20_20260522`;
  cached baseline `1/20`, SAGE `5/20`; integrity issues `0`.
- Harder offset-window probe:
  `outputs/cybergym_live_sage/cybergym_public_search_validcache_offset20_probe20_20260523`;
  cached baseline `0/20`, SAGE `3/20`; tools born/accepted/reused
  `18 / 18 / 212`; rejected tools `0`; repair attempts `2`; integrity
  issues `0`; zero-byte public source archives in run output `0`.
- Machine-readable summary:
  `artifacts/sage_agent_standalone/cybergym_public_execution_search_gap_closure_20260523.json`.
- Report:
  `docs/sage_protocol/cybergym_public_execution_search_gap_closure_20260523.md`.
- Validation: focused standalone unit tests passed
  `12 passed, 57 deselected`; Python compile passed for the touched CyberGym
  adapter and batched runner.
- Interpretation: the public execution-search helper class is the first clear
  CyberGym improvement beyond the `5/20` fixed-side first-window reference.
  The offset-window result remains low, so the next bottleneck is deeper
  source-guided candidate quality and candidate-budget allocation for harder
  source families.
- Decision label:
  `PUBLIC_EXECUTION_SEARCH_IMPROVES_CYBERGYM_FIRST20_WITH_GENERAL_FRAMEWORK_REPAIR`.

## 2026-05-23 - Source-Guided Candidate-Quality Follow-Up

- Objective: test the diagnosed next bottleneck, deeper source-guided candidate
  quality and candidate-budget allocation on harder CyberGym source families,
  while checking that the general SAGE agent still holds on MiniGrid, BBH, and
  ToolSandbox.
- Branch: `codex/sage-standalone-agent`.
- Code changes: source-guided public vulnerable-side search budget now deepens
  only from visible hard-source cues; public format-probe seeds now cover XML,
  AAC/audio, HTSlib SAM/BAM/CRAM, libssh/KEX, PCRE/regex, PE modules,
  FreeType/CFF, libsepol/SELinux, and AFL/filter-style parsers; wrapper-first
  target selection permits visible hint-matched fuzz-target fallback.
- CyberGym run:
  `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523`;
  dashboard:
  `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523/dashboard/task_compare.html`.
- CyberGym result: cached baseline `1/40`, SAGE `12/40`; absolute lift `+27.5`
  percentage points; relative lift `+1100.0%`; same-window improvement over the
  prior first40 public-search run `10/40 -> 12/40`; fixed-side verification
  enabled; official success verifier used; integrity issues `0`; tools
  born/accepted/reused `21 / 21 / 399`; birth-task retry successes `2 / 10`.
- MiniGrid maintenance:
  `outputs/sage_agent_standalone/minigrid_cross_validation40_satisfied_source_budget_20260523`;
  baseline `18/40`, SAGE `40/40`, integrity issues `0`.
- BBH maintenance:
  `outputs/sage_agent_standalone/bbh_cross_validation40_source_budget_20260523`;
  baseline `16/40`, SAGE `40/40`, integrity issues `0`.
- ToolSandbox comparable formal first-40 maintenance:
  `outputs/sage_agent_standalone/toolsandbox_verify40_post_source_family_20260523/mechanism_40_20260523_182940`;
  score `0.648 -> 0.848`, delta `+0.200`, lift `+30.9%`; outcome
  `0.474 -> 0.887`, delta `+0.414`; controls `40 cached / 0 fresh`; SAGE
  cache off; OpenAI response cache disabled; runtime exceptions `0`;
  generated tools accepted `14`; generated-tool called scenarios `23`;
  generated-tool failed scenarios `0`. This corrects the earlier lower
  ToolSandbox diagnostic interpretation: the `toolsandbox_protocol_mechanism40_source_budget_v2`
  run used a different diagnostic split with `27 cached / 13 fresh` controls
  and an external-service cohort warning, so it was not comparable to the
  previous high-lift first-40 checks.
- CyberGym later-window evolution follow-up:
  `outputs/cybergym_live_sage/cybergym_source_family_offset20_20260523`;
  cached baseline `0/20`, SAGE `5/20`, improving the prior offset20 probe
  from `3/20`; fixed-side verification enabled; official success verifier
  used; integrity issues `0`; tools born/accepted/reused `20 / 20 / 214`;
  batch wins `2, 1, 1, 1, 0`; tools born by batch `12, 4, 3, 0, 1`.
  Interpretation: evolution now continues past the first batch, but most
  source-family specialists remain `refine`, so the next bottleneck is
  specialist strategy quality and candidate-budget allocation.
- Machine-readable summary updated:
  `artifacts/sage_agent_standalone/cybergym_public_execution_search_gap_closure_20260523.json`.
- Report updated:
  `docs/sage_protocol/cybergym_public_execution_search_gap_closure_20260523.md`.
- Validation: focused source-guided/source-family unit tests
  `7 passed, 66 deselected`; full standalone unit suite `73 passed`; Ruff
  check passed for touched Python files; JSON validation and `git diff --check`
  passed.
- Interpretation: source-guided budget allocation produced a real CyberGym
  improvement without hidden labels or fixed-side discovery and did not regress
  MiniGrid, BBH, or ToolSandbox maintenance behavior. The remaining CyberGym
  bottleneck is richer source-family strategy generation and budget allocation,
  not visibility or simple gap detection.
- Decision label:
  `SOURCE_FAMILY_EVOLUTION_REPAIR_IMPROVES_CYBERGYM_LATER_WINDOW_AND_RETAINS_TOOLSANDBOX_LIFT`.

## 2026-05-23 - Import-Agent Portability Matrix And Tau2 Repair

- Objective: make SAGE usable as an importable agent inside host-owned
  benchmark harnesses without rewriting those harnesses around
  `EnvironmentAdapter`, then validate the boundary on known-good and new
  datasets.
- Branch: `codex/sage-standalone-agent`.
- Code changes: added `SAGEImportAgent`, `ImportTaskContext`,
  `ImportTaskObservation`, `SAGEGuidance`, and `SAGEImportUpdate`; added
  first-class helper types; added official harness runner support for tau2 and
  Terminal-Bench; added baseline-control cache support for official harnesses;
  added import-mode integrity checks and same-task retry policy controls.
- Tau2 failure repair: the initial official tau2 run showed SAGE accepted a
  reusable helper from a runner-side `JSONDecodeError`. Import mode now treats
  runner/parser/subprocess/Docker/authentication/timeout failures as diagnostics
  and emits `tool_birth_skipped` instead of birthing helpers.
- ToolSandbox protocol40:
  `outputs/sage_agent_standalone/import_agent_verify_toolsandbox40_20260523/mechanism_40_20260523_194131`;
  score `0.648 -> 0.870`; outcome `0.474 -> 0.914`; exact successes
  `3 -> 23`; controls `40 cached / 0 fresh`; runtime exceptions `0`.
- CyberGym live fixed-side40:
  `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523`;
  cached baseline `1/40`, SAGE `12/40`; real task generator, real submit server,
  real PoC verifier, fixed-side check enabled; integrity issues `0`.
- MiniGrid live40:
  `outputs/sage_agent_standalone/import_agent_openai_verify_minigrid40_20260523`;
  cached baseline `18/40`, SAGE `40/40`; one reusable grid planner.
- BBH live40:
  `outputs/sage_agent_standalone/import_agent_openai_verify_bbh40_20260523`;
  cached baseline `16/40`, SAGE `40/40`; hidden answer targets remained private
  inside the adapter scorer.
- Tau2 official40 pre-repair:
  `outputs/sage_official_live/import_agent_tau2_airline_official_live40_gpt4omini_20260523`;
  baseline `9/40`, SAGE `8/40`; controls `25 cached / 15 fresh`; paired gains
  `5`, regressions `6`, both-win `3`, both-fail `26`.
- Tau2 official40 post-repair:
  `outputs/sage_official_live/import_agent_tau2_airline_skip_infra_helper_live40_20260523`;
  baseline `9/40`, SAGE `10/40`; controls `40 cached / 0 fresh`; paired gains
  `5`, regressions `4`, both-win `5`, both-fail `26`; no SAGE runner JSON error.
- Terminal-Bench official40:
  `outputs/sage_official_live/import_agent_terminal_bench_official_live40_20260523`;
  stopped as runtime-feasibility blocker after about 24 minutes, with only
  `3` paired tasks complete and no valid prior 40-task baseline cache. The run is
  partial evidence only, not a completed validation.
- tau3-bench smoke:
  `outputs/sage_official_live/import_agent_tau3_airline_smoke1_20260523`;
  baseline `1/1`, SAGE `1/1`. This uses the current `external/tau2-bench`
  checkout, which now contains the tau3 release/task-fix layer, and labels the
  run as `tau3-current-release` with `tau3:*` task IDs so tau2 and tau3 evidence
  remain separated.
- tau3-bench airline official40:
  `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524`;
  baseline `16/40`, SAGE `12/40`; gains `1`, regressions `5`, both-win `11`,
  both-fail `23`; eight prompt helpers born and five parked. Decision: complete
  negative validation for current import-mode prompt-helper policy.
- Terminal-Bench repaired fast4:
  `outputs/sage_official_live/import_agent_terminal_bench_tmp_fast4_20260524`;
  baseline `1/4`, SAGE `1/4`; gains `1`, regressions `1`. This used a fresh
  non-iCloud checkout at `/tmp/sage_benchmarks/terminal-bench`, which avoided
  the previous file-copy/tar errors. Full40 remains runtime-budget blocked.
- ScienceAgentBench / science-agent-bench preflight:
  `outputs/sage_official_live/import_agent_scienceagentbench_verified_artifact_preflight_20260523`;
  verified Hugging Face split loaded selected IDs `1-4`; official scoring remains
  gated on local `datasets`, `eval_programs`, `gold_programs`, and
  `scoring_rubrics` from `benchmark_verified.zip`. The public SharePoint download
  attempt returned an authenticated sign-in page. New helper:
  `scripts/prepare_scienceagentbench_artifacts.py`.
- science-agent-bench alias preflight:
  `outputs/sage_official_live/import_agent_science_agent_bench_verified_artifact_preflight_20260524`;
  same verified-input/artifact-gate result as `scienceagentbench`.
- Reports/artifacts:
  `docs/sage_protocol/sage_import_agent_validation_matrix_20260523.md`,
  `docs/sage_protocol/sage_import_agent_tau2_failure_analysis.md`, and
  `artifacts/sage_official_live/tau2_import_agent_repair_artifacts_20260523.json`.
- Validation: targeted import-agent unit tests `4 passed`; Ruff passed for
  `src/sage_agent/import_agent.py` and the import-agent tests. Full standalone
  test file hung after several tests in the current local environment and was
  stopped; rerun in a clean environment before protected review.
- Decision label:
  `IMPORT_AGENT_BOUNDARY_WORKS_WITH_TAU2_REPAIR_BUT_POLICY_HARNESS_HELPER_QUALITY_REMAINS_NEXT_GAP`.

## 2026-05-24 - Full Import-Agent Lifecycle Repair And Tau3 Revalidation

- Objective: fix the portability gap where `SAGEImportAgent` behaved like a
  shallow prompt-helper shim inside host-owned benchmark loops instead of the
  full SAGE lifecycle.
- Code changes:
  - `src/sage_agent/import_agent.py` now supports in-task `before_step(...)`
    helper refresh from visible transcripts, `review_action(...)` for host
    loops that can inspect proposed tool calls before execution, full
    helper birth/validation/repair/retain for import mode, deterministic helper
    execution into rendered guidance, and optional same-task retry after helper
    birth or failed visible-helper context refresh.
  - `src/sage_agent/interfaces.py` adds `SAGEActionReview`.
  - `src/sage_agent/generators.py` strengthens the generic policy-action
    precondition helper used by tau-style host simulators. It handles current
    user-turn focus, transfer/escalation cues, compensation scope, unsupported
    insurance/account disputes, and host-visible tool availability without
    labels, scenario IDs, or expected answers.
  - `scripts/run_sage_official_live.py` wires tau host loops to the import
    agent through per-turn guidance refresh and action review. It also forces
    LiteLLM to use the local cost map during official live runs so import-time
    cost metadata fetching cannot block before task execution.
- Tau3 official40 repaired import-lifecycle run:
  `outputs/sage_official_live/import_agent_tau3_airline_full_import_action_review_official40_sys_20260524`;
  official tau current-release simulator/scorer, `gpt-4o-mini`, cached controls
  `40 cached / 0 fresh`, fresh SAGE, no candidate cache. Result: baseline
  `16/40`, SAGE `18/40`; gains `4`, regressions `2`, both-win `14`,
  both-fail `20`; accepted helpers `1`; helper reuse events `61`; integrity
  issues `0`.
- Tau3 negative ablation retained:
  `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524`;
  baseline `16/40`, static prompt-helper SAGE `12/40`; gains `1`,
  regressions `5`. This is now the documented failure mode that the full import
  lifecycle repaired.
- Terminal-Bench import-mode value check:
  `outputs/sage_official_live/import_agent_terminal_bench_concrete_repair_2_20260524`;
  official task parser/Docker path on repaired `/tmp/sage_benchmarks` checkout,
  cached baseline `0/2`, fresh SAGE `2/2`; gains `2`, regressions `0`;
  integrity issues `0`. Full40 remains a runtime-budget item, not a SAGE
  boundary blocker.
- Maintenance evidence carried forward:
  MiniGrid live40 `outputs/sage_agent_standalone/minigrid_import_agent_maintenance40_wide_20260524`
  retained cached baseline `18/40` and SAGE `40/40`; BBH live40
  `outputs/sage_agent_standalone/bbh_import_agent_maintenance40_20260524`
  retained cached baseline `16/40` and SAGE `40/40`; ToolSandbox and CyberGym
  high-lift adapter runs remain documented in `docs/sage_protocol/current_state.md`.
- Validation:
  - `python -m py_compile src/sage_agent/interfaces.py src/sage_agent/import_agent.py src/sage_agent/generators.py scripts/run_sage_official_live.py`
  - `python -m ruff check src/sage_agent/interfaces.py src/sage_agent/import_agent.py src/sage_agent/generators.py scripts/run_sage_official_live.py`
  - local import-agent action-review smoke accepted a policy helper and blocked
    an unsafe reservation-update style action when the helper recommended
    transfer/escalation.
- Decision label:
  `FULL_IMPORT_AGENT_LIFECYCLE_REPAIRS_TAU3_AND_TERMINAL_BENCH_SHOWS_IMPORT_MODE_VALUE`.

## 2026-05-27 - Tau3 SAGEAgent Parity Option-Repair Run

- Objective: test whether tau3 can use the same high-lift SAGE behavior proven
  on ToolSandbox: identify deterministic gaps, generate real callable helpers,
  validate/repair them, store them, route them into later tasks, and count only
  gains attributable to generated helper use.
- Runner: `scripts/run_tau3_sageagent_parity.py`, official tau3-current-release
  airline host loop, `gpt-4o-mini`, cached baseline controls where eligible,
  fresh SAGE execution, no candidate task cache.
- Code repairs in this pass:
  - import-helper sandbox now permits `enumerate` for accepted deterministic
    helpers;
  - source-record lookup templates can continue past already-visible records to
    find the actual related source reservation/date;
  - host-action templates can prepare visible cancellation, booking,
    reservation-change, direct/one-stop search, and partial allowed-action
    specs from visible data;
  - option-selection templates now parse explicit option-number choices such as
    "Option 2" and expose selected flight codes/dates.
- Fresh20 run:
  `outputs/sage_official_live/tau3_sageagent_fresh20_option_repair_v6_20260527_01`;
  dashboard:
  `outputs/sage_official_live/tau3_sageagent_fresh20_option_repair_v6_20260527_01/dashboard/task_compare.html`.
- Hashes: dashboard data
  `07a89205e9b4d27991b4ba57d026f6d5c3dc1eea01f6002ca8679005e71a19e8`;
  registry
  `5db233a4efb5bdc33fbe78a42d773d171547fce2bb5f615a44975c6557e8cc8d`.
- Result on valid non-infra rows: baseline `6/15`, SAGE `8/15`; net `+2`;
  generated-tool-attributed gains `1`; generated-tool-attributed regressions
  `0`; infra rows `5`.
- Tool lifecycle: tools born `28`, accepted `17`, rejected `11`, reused `252`;
  birth-task retries `7`, retry successes `1`.
- Attribution: `tau3:airline:13` is the valid helper-attributed gain, using
  `prepare_visible_baggage_entitlement_action_args`. `tau3:airline:1` was a
  SAGE gain but not helper-attributed and is not counted as generated-tool
  evidence.
- Interpretation: tau3 now has real callable-helper parity mechanics, not only
  prompt guidance, and the option repair removed the prior valid regression.
  The result is still not ToolSandbox-scale; broad scale should wait for a
  general candidate-quality and candidate-budget repair that increases
  helper-attributed gains across hard tau3 families.
- Decision label:
  `PARTIAL_TAU3_SAGEAGENT_PARITY_REAL_CALLABLE_HELPER_GAIN_NOT_SCALE_READY`.

## 2026-05-29 - Tau3 Action-Spec Validation Diagnostic

- Objective: continue tau3 SAGEAgent portability by strengthening the generated
  helper action-spec contract in SAGE core and checking whether tau3 20 can
  produce clean generated-helper-attributed lift.
- Code changes:
  - core validation rejects inconsistent action specs and mismatched
    `next_action`/legacy action fields;
  - read-only lookup actions can be called while side-effect preconditions
    remain unresolved;
  - generation prompts and visible-action schemas request `status`, `reason`,
    and `next_action`;
  - tau3 bridge consumes `next_action` as a fallback.
- Validation:
  - py_compile on SAGE core, tau3 runner, CyberGym runner, and ToolSandbox
    protocol runner passed;
  - standalone unit suite passed `85 passed, 2 warnings`;
  - focused CyberGym planner subset passed `8 passed`;
  - `git diff --check` passed.
- First diagnostic:
  `outputs/sage_official_live/tau3_generalization20_20260529_183539`;
  stopped after 2 SAGE task records because the initial strict contract rejected
  a valid read-only policy lookup. Partial: baseline cache `8/20`, SAGE `1/2`,
  born/accepted/reused `1 / 0 / 0`.
- Second diagnostic:
  `outputs/sage_official_live/tau3_generalization20_action_spec_v2_20260529_184112`;
  stopped after 7 SAGE task records due suspected runtime/generation stall.
  Partial: baseline cache `8/20`; SAGE controller success `3/7`;
  born/accepted/reused `14 / 11 / 31`; retries `3`, retry successes `1`;
  integrity issues `0`.
- Attribution notes: v2 showed one same-task retry success on `tau3:airline:0`
  and one helper-used gain on `tau3:airline:1`, but also helper-used
  regressions in the completed partial slice.
- Error log: `artifacts/tau3_errors_20260529_185534.log`.
- Focused report:
  `docs/sage_protocol/tau3_action_spec_replay_validation_20260529.md`.
- Decision label: `BLOCKED: tau3_action_spec_helpers_not_clean_20_ready`.
- Next action: add stricter replay/shadow routing and a tau3 gap-generation
  budget cap before rerunning tau3 20.

## 2026-05-29 - Full ToolSandbox v71-Style No-Cache Usage Run

- Objective: rerun the complete ToolSandbox full benchmark with the native
  self-evolving Praxis implementation while disabling the control baseline cache
  so LLM calls and token use are measured directly.
- Prior mixed-cache run
  `outputs/self_evolving_sage/full_toolsandbox_v71_20260529_183043/online_build_full_20260529_184527`
  was stopped at user request and preserved under its original output/artifact
  directories.
- Active run:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554`.
- Dashboard:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554/dashboard/task_compare.html`.
- Configuration: `online_build_full`, full `1032`-scenario manifest, native
  ToolSandbox self-evolving Praxis, actor/user/generation model all
  `gpt-4o-mini`, generation on, control cache off, SAGE task cache off, OpenAI
  response cache disabled, RapidAPI fixture cache read-only.
- Manifest SHA-256:
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`.
- Usage sanity check before launch:
  `artifacts/self_evolving_sage/usage_sanity_20260529_194509`, confirming
  actor and generation calls record live call counts and token totals with
  `gpt-4o-mini-2024-07-18`.
- Live early check: after 13 fresh control scenarios, exported usage showed
  `43` live LLM calls, `0` cached LLM calls, and `42481` total tokens.
- Dashboard repair: added an explicit no-cache control-cache report for this
  run and updated dashboard fallback rendering so no-cache runs display
  `0 cached / 1032 fresh`, `Mode off`, and `Source fresh` instead of hiding the
  cache panel.
- Per-task usage cache:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554/llm_usage_task_cache.json`
  and companion `.jsonl` are being updated by
  `scripts/cache_llm_usage_by_task.py`. The policy is immediate write per
  completed task with no minimum-count gate.
- Dashboard hardening: live dashboard refresh now ignores transient partial
  JSON reads during writes and retries on the next poll; verified in a fresh
  browser tab with task compare still showing no-cache and LLM usage panels.
- Live disconnect analysis at approximately `510/1032` SAGE candidate tasks:
  current paired completed lift is much smaller than v71 broad500
  (`+0.0386` canonical, `+0.0625` outcome at the checkpoint), but the run is
  not comparable to the v71 headline on a single axis. v71 used the 500-task
  formal manifest with cached control baselines; this run uses the 1032-task
  full manifest with fresh controls. On the formal500 names, the fresh control
  baseline in this run scores about `0.7728` canonical and `0.7219` outcome,
  versus v71 cached control `0.6568` canonical and `0.4947` outcome. The full
  manifest also delays high-gain contact/message/recency families: for example,
  `modify_contact_with_message_recency` begins at full-manifest index `504`,
  `remove_contact_by_phone` at `576`, `search_message_with_recency_latest` at
  `688`, `send_message_with_contact_content_cellular_off` at `880`, and
  `update_contact_relationship_with_relationship` at `984`. Helper birth counts
  match this explanation: accepted helpers rose from 6 before that segment to 9
  shortly after index `504`, while v71 broad500 had 16 accepted helpers by 500
  tasks.
- Live dashboard data enrichment was added with
  `scripts/patch_live_dashboard_data.py` so the active dashboard surfaces
  visibility counts, called-subset deltas, and side-effect preservation rows
  before the final helper contribution export. The patcher only rewrites
  dashboard JSON after runner exports and does not affect task execution,
  scoring, tool routing, or transcripts. Initial enrichment surfaced 10
  accepted tools, 7 naturally called tools, 10 visible tools, and 3
  side-effect preservation rows for audit.
- Latest-code regression relative to v71 found during monitoring:
  `resolve_search_window_or_bounds` was rejected twice in the active run under
  `derived_value:recency_timestamp_bounds` because the repaired broad search
  helper was validated against obsolete bounds-only examples containing
  `recency_label`. v71 accepted this helper and called it in 83 scenarios, so
  the missing lane is a concrete contributor to lower lift beyond cache/sample
  effects. A next-run source repair was added to validate the upgraded helper
  against broad search-plan examples; `tests/unit/test_online_birth.py` passed
  `44 passed, 2 warnings`. This repair was applied after the active run started
  and is not part of the active run's loaded code.
- Updated checkpoint at `615/1032` SAGE candidate tasks: full-run completed
  slice is `0.752282 -> 0.771548` canonical/reference, delta `+0.019266`, and
  `0.623709 -> 0.696125` outcome/task completion, delta `+0.072415`.
  Formal500 overlap is only `185/500` scenarios so far. On those same scenario
  names, the current fresh control is much stronger than the v71 cached control
  (`0.808151` vs `0.656123` canonical; `0.735934` vs `0.484067` outcome), and
  v71's SAGE arm was still much stronger on the same subset (`+0.218223`
  canonical, `+0.435562` outcome). This supports a three-part explanation:
  fresh no-cache controls compress lift, the 1032-task manifest delays the
  high-yield v71 helper lanes, and latest-code behavior has at least one
  concrete regression in the recency-window helper path.
- Dashboard update during the active run: added a visible live tool-contribution
  panel to task compare and restarted the HTML patch watcher. Browser
  verification at `648/1032` matched tasks showed LLM calls/tokens, cache status,
  and top helper contribution rows visible in the page header. Focused dashboard
  validation passed: `13 passed in 2.46s`.
- Live recency checkpoint around `698/1032`: the active run has begun recovering
  generated-helper contribution in the delayed recency/message segment
  (`resolve_search_window_or_bounds` `42` visible / `32` called, called-subset
  outcome delta `+0.214359`; `select_message_content_by_recency` `10` visible /
  `9` called, called-subset outcome delta `+0.206610`). The overall completed
  slice remains far below v71 (`+0.077621` outcome delta), and family-level
  comparison shows current recency/message gains are still much weaker than the
  v71 artifact. The current run should therefore be treated as a no-cache full
  dataset diagnostic and usage-measurement run, not as a clean reproduction of
  the v71 broad500 lift.
- Updated disconnect checkpoint around `781/1032`: completed-slice
  canonical/reference delta is approximately `+0.029104`; outcome/task
  completion delta is approximately `+0.081833`; total recorded cached LLM
  calls remain `0`. The run is operationally healthy, but it is not matching
  v71 because the comparison changed from cached formal500 controls to fresh
  full-dataset controls, high-yield helper lanes are delayed by the full
  manifest order, and latest-code behavior differs from the v71 artifact.
  The clearest regression is the early double rejection of
  `resolve_search_window_or_bounds` due to obsolete `recency_label` validation
  examples when the helper had been upgraded to the broader search-plan
  contract. A next-run repair exists in
  `src/sage_ts/orchestration/online_birth.py`, but it is not loaded in the
  already-running process.
- Lifecycle preset parity check: the active run's event ledger confirms that
  self-evolving Praxis defaults were applied (`SAGE_SELF_EVOLVING_PROACTIVE_BIRTH=1`,
  `SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time`,
  `SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=1`,
  `SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1`, `SAGE_PRAXIS_BRIDGE_POLICY=combined`).
  Missing lifecycle flags are therefore not the explanation for the low lift.
- Updated no-cache disconnect checkpoint around `907/1032`: completed-slice
  canonical/reference delta is approximately `+0.043694`; outcome/task
  completion delta is approximately `+0.093913`; naturally called generated
  helper scenarios are `443`; LLM cached calls remain `0`. The formal500
  overlap confirms that most of the v71 lift gap comes from the requested
  no-cache fresh baseline: on the `398` completed formal500-overlap scenarios,
  active fresh control outcome is `0.701393` versus v71 cached control
  `0.408984`, while active SAGE is `0.803003` versus v71 SAGE `0.861516`.
  The run also confirms latest-code drift: the high-yield
  `resolve_search_window_or_bounds` helper was rejected twice early under the
  old `recency_label` validation contract and only accepted later under the
  broader helper key.
- Final no-cache full-dataset result:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554`.
  Canonical/reference score `0.750138 -> 0.791681` (`+0.041543`, `+5.54%`);
  outcome/task completion `0.648824 -> 0.741156` (`+0.092332`). Usage accounting
  recorded `15,651` total LLM calls and `21,456,951` total tokens
  (`21,066,079` prompt, `390,872` completion); cached LLM calls `0`; every
  recorded event used `gpt-4o-mini`. Tool lifecycle: `26` birth rows, `17`
  accepted, `9` rejected, `14` repair-attempted, `546` naturally called
  generated-tool scenarios, `217` outcome-gain rows, `68` outcome-regression
  rows, `4` side-effect preservation rows, and `0` runtime incidents.
- Final formal500 overlap: active no-cache/fresh-control outcome
  `0.721944 -> 0.830761` (`+0.108816`) versus v71 cached-control outcome
  `0.494746 -> 0.880845` (`+0.386099`). The active fresh control is `+0.227198`
  outcome points above the v71 cached control, while the active SAGE arm is
  `-0.050084` below v71 on the same scenario names.
- Final interpretation: retain v71 as the strongest ToolSandbox evidence and
  v70 as the clean safety-reference run. Treat this run as a no-cache
  full-dataset usage/robustness diagnostic. It confirms that the low observed
  lift is driven by stronger fresh controls, delayed full-manifest helper
  compounding, and latest-code drift in the recency-window helper path.
- Validation: `git diff --check`, py_compile, and the focused unit suite passed
  (`161 passed, 2 warnings`).
- Decision label: `COMPLETED_FULL_TOOLSANDBOX_NOCACHE_USAGE_DIAGNOSTIC_DO_NOT_PROMOTE_OVER_V71`.

## 2026-05-29 - Tau3 Shadow Helper Bridge Repair

- Objective: make tau3 SAGEAgent behave more like ToolSandbox SAGE by exposing
  generated helpers as callable/structured control points, not hidden telemetry
  or broad prompt guidance.
- Code changes:
  - fixed shadow mode so helper preflight outputs are injected into the actor
    context by default; `--direct-only-shadow-helpers` is now an explicit
    ablation;
  - added bounded helper execution timeouts and retryable tau2 official-runner
    exception handling;
  - tightened contribution accounting so sanitized abstain outputs cannot create
    false helper-attributed regressions;
  - added active cancellation/refund intent gating so "the airline canceled my
    flight" does not authorize `cancel_reservation`;
  - added regression tests for booking-intent, cancellation-intent,
    action-spec, stale reservation, helper timeout, and contribution accounting
    behavior.
- Best completed diagnostic:
  `outputs/sage_official_live/tau3_shadow_cancel_gate20_20260529_224218`.
- Dashboard:
  `outputs/sage_official_live/tau3_shadow_cancel_gate20_20260529_224218/dashboard/task_compare.html`.
- Result: baseline `8/20`, final SAGE `11/20`, initial SAGE `9/20`;
  tools born/accepted/reused `12 / 12 / 120`; birth retries `8`, retry
  successes `4`; integrity issues `0`.
- Strict attribution: one clean callable-helper gain on `tau3:airline:11`.
  Other final gains are logged as non-strict because helper outputs were absent
  or non-actionable.
- Safety: zero helper-attributed final regressions. The earlier
  `prepare_visible_cancellation_refund_action_args` regression was reproduced,
  diagnosed, and repaired with the active intent gate.
- Parked ablation:
  `outputs/sage_official_live/tau3_shadow_route_gate20_20260529_231249` scored
  SAGE `7/20` vs baseline `8/20`; hard route suppression starved useful helper
  exposure and is not the scaling path.
- Focused report:
  `docs/sage_protocol/tau3_shadow_bridge_repair_20260529.md`.
- Validation: py_compile passed; standalone unit suite passed
  `94 passed, 2 warnings`; `git diff --check` passed.
- Decision label:
  `PROMISING_TAU3_SHADOW_BRIDGE_ONE_STRICT_CALLABLE_GAIN_REFINE_BEFORE_60`.
- Next action: improve exact payment/option-selection helpers and lifecycle
  parking for repeated non-gain record lookup calls, then rerun tau3 20 before
  considering tau3 60.

## 2026-05-30 - Tau3 Medium-Grain Replay/Action Repair

- Best completed run:
  `outputs/sage_official_live/tau3_medium_grain_generalization20_20260530_022037`.
- Dashboard:
  `outputs/sage_official_live/tau3_medium_grain_generalization20_20260530_022037/dashboard/task_compare.html`.
- Command:
  `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62639 --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 --max-same-task-retries 1 --max-refinements 2 --transient-retries 2 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_medium_grain_generalization20_20260530_022037`.
- Result: cached baseline `8/20`, final SAGE `12/20`; tools
  born/accepted/reused `22 / 19 / 103`; birth retries `9`, retry successes
  `2`; integrity issues `0`.
- Generated-tool attribution: registry recorded `2` contribution gains on
  `prepare_visible_reservation_change_action_args`; strict final
  helper-attributed regressions `0`.
- Lifecycle: non-actionable option helper exposure regression was parked;
  two initial baseline-success/SAGE-fail cases were rescued by same-task retry.
- Follow-up diagnostics:
  - `outputs/sage_official_live/tau3_retry_bundle_task8_20260530_025232`
    confirmed the retry-bundle fix carried record lookup, booking/payment, and
    option helpers into task `8`; it still failed due copied free baggage.
  - `outputs/sage_official_live/tau3_baggage_repair_task8_20260530_025823`
    and
    `outputs/sage_official_live/tau3_baggage_repair_task8_rerun_20260530_025900`
    are invalid infrastructure reruns: OpenAI/LiteLLM DNS/connectivity failed
    before helper behavior could be tested.
- Code validation: py_compile for SAGE core/runners passed; standalone unit
  suite passed `106` tests with `2` dependency warnings.
- Decision label:
  `PROMISING_TAU3_MEDIUM_GRAIN_HELPERS_POSITIVE_20_REFINE_AFTER_API_RECOVERY`.
- Next action: rerun task `tau3:airline:8` after OpenAI chat sanity recovers,
  then rerun tau3 20 and gate tau3 60 on clean generated-tool-attributed gains.

## 2026-05-30 - ToolSandbox Full Dataset Recovery V6

- Completed run:
  `outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256/dashboard/task_compare.html`.
- Configuration: native ToolSandbox self-evolving Praxis,
  `online_build_full`, `gpt-4o-mini` actor/user/generation, generation on,
  SAGE cache off, OpenAI response cache disabled, empty starting registry,
  full manifest SHA-256
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`.
- Control cache: `use-if-eligible`, mixed source with `689` cached and `343`
  fresh controls.
- Final full metrics: canonical/reference `0.693253 -> 0.829701`
  (`+0.136448`, `+19.68%`); outcome/task completion
  `0.506399 -> 0.788966` (`+0.282568`, `+55.80%`); exact successes
  `148 -> 498`; runtime exceptions `0`; protocol gate `PASS`.
- Tool lifecycle: accepted `17` live-born helpers; generated helpers called in
  `556` scenario contexts; dashboard contribution rows `459` outcome gains and
  `52` outcome regressions; generated-tool runtime failures `0`.
- Safety caveat: `2` side-effect preservation rows, both for
  `prepare_reminder_creation_args` on
  `add_reminder_content_and_week_delta_and_time_multiple_user_turn_alt`
  variants.
- Formal500 comparison: formal500 v6 scored `+30.04%` canonical lift and
  `+76.70%` outcome lift, while full_v6 scored `+19.68%` and `+55.80%`. The
  full run meets the requested minimum full-dataset gate but does not supersede
  formal500 v6 or v71 as the strongest ToolSandbox evidence.
- Revised blocker assessment: ceiling compression is not a primary explanation;
  the control means were low enough for substantial improvement. The actual
  blockers are missing helper coverage/adoption in full-only service-answer
  lanes (`convert_currency`, `find_temperature`, `find_phone_number`,
  `find_current_location`), rejection of `plan_send_message_contact_lookup` on
  exact advisory text mismatches, weak natural adoption of
  `extract_service_answer_field`, `prepare_reminder_creation_args`, and
  `prepare_safe_action_or_abstain`, canonical-score loss from `find_days`, and
  add-reminder multi-turn timestamp/location regressions. Wrong model or
  missing self-evolving Praxis lifecycle settings are ruled out by the
  manifest.
- Report:
  `docs/sage_protocol/toolsandbox_full_v6_recovery_report_20260530.md`.
- Decision label:
  `FULL_DATASET_RECOVERY_PASSES_MINIMUM_GATE_DOES_NOT_SUPERSEDE_FORMAL500_V6`.

## 2026-05-31 - tau3 No-Revisit Helper Bridge Recovery

- Completed run:
  `outputs/sage_official_live/tau3_no_revisit_recovery_gate60f_20260531_001355`.
- Dashboard:
  `http://127.0.0.1:62746/outputs/sage_official_live/tau3_no_revisit_recovery_gate60f_20260531_001355/dashboard/task_compare.html`.
- Command:
  `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 60 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62746 --max-helpers 48 --active-helpers 6 --helper-pool-size 12 --max-tools-per-task 9 --max-same-task-retries 0 --max-refinements 2 --transient-retries 4 --generation-timeout-sec 120 --direct-only-shadow-helpers --enable-direct-actions --proactive-helper-bootstrap --proactive-bootstrap-limit 9 --run-id tau3_no_revisit_recovery_gate60f_20260531_001355`.
- Sample/window: requested `60`; materialized first `50` airline tasks in this
  checkout.
- Baseline cache: `use-if-eligible`, `50/50` cached.
- SAGE cache: off/fresh SAGE arm.
- Model: `gpt-4o-mini`.
- Generation model: `gpt-5`.
- Result: baseline `15/50`, SAGE `29/50`; first 20 slice `8/20` baseline,
  `15/20` SAGE; absolute lift `+14` tasks (`+28` percentage points),
  relative success lift `+93.33%`.
- Same-task retries: `0`; this was a no-revisit run.
- Generated tools born/accepted/reused: `22 / 22 / 1162`.
- Bridge activity: `144` direct helper actions, `77` official action repairs,
  `30` final-answer repairs.
- Paired gains:
  `tau3:airline:1`, `8`, `11`, `12`, `13`, `15`, `18`, `26`, `28`, `34`,
  `38`, `40`, `43`, `48`.
- Paired losses: none.
- Runtime/helper incidents: `0`; integrity issues `0`.
- Leakage/safety notes: no hidden labels, expected answers, reference
  trajectories, or scorer internals inspected. Baseline/control used cached
  records; SAGE arm was fresh.
- Validation: SAGE core/runners py_compile passed; standalone unit suite
  passed `160` tests with `2` dependency warnings; `git diff --check` passed.
- Audit note: import-readiness audit is specific to `SAGEImportAgent` and
  failed on this SAGEAgent parity run for boundary/event-name reasons; not used
  as an integrity blocker for this run.
- Report:
  `docs/sage_protocol/tau3_no_revisit_tool_generation_recovery_20260531.md`.
- Decision label:
  `KEEP_AND_SCALE_NO_REVISIT_TAU3_HELPER_BRIDGE`.
- Next action: update audit/export coverage for SAGEAgent parity attribution,
  inspect remaining misses for the next general helper class, then run CyberGym
  and ToolSandbox maintenance checks.

## 2026-05-31 - ToolSandbox Fullprefix500 Reference Resume

- Active run:
  `/tmp/toolsandbox-sage-local-run/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_r11_launchd_reference_20260531_140308/online_build_500_20260531_140312`.
- Dashboard:
  `http://127.0.0.1:62679/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_r11_launchd_reference_20260531_140308/online_build_500_20260531_140312/dashboard/task_compare.html`.
- Correct dataset: ToolSandbox `online_build_500` with manifest
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/full_standard_prefix500.json`.
- Launch/resume: direct launchd script
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_direct_reference_launchd.sh`
  running from `/tmp/toolsandbox-sage-local-run`; resumed from the best local
  partial at `413/500`.
- Live status at 2026-05-31 14:07 EDT: `417/500` matched tasks, control
  `500/500` complete, SAGE running; canonical score `0.685114 -> 0.898871`
  (`+31.20%`), outcome `0.521966 -> 0.888864`, accepted helpers `7`,
  reuse events `267`, generated-tool-called scenarios `142`, current
  exceptions `0`, generated-tool failures `0`, runtime incidents `0`,
  side-effect incidents `0`.
- Process hygiene: stopped off-track focused20/mechanism diagnostic PIDs
  `17152` and `18977` because they used `focused_regression20_r12.json` /
  `mechanism_40` and conflicted with the requested fullprefix500 comparison.
- Decision: keep running and monitor through
  `check-fullprefix500-sage-comparison`; once the reference reaches `500/500`,
  launch the same-manifest GPT-5-generation comparison with a fresh registry.

## 2026-05-31 - ToolSandbox Fullprefix500 Current-Impl GPT-5 Comparison

- Active run:
  `/tmp/toolsandbox-sage-local-run/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_20260531_141546/online_build_500_20260531_141550`.
- Dashboard:
  `http://127.0.0.1:62680/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_20260531_141546/online_build_500_20260531_141550/dashboard/task_compare.html`.
- Correct dataset: same ToolSandbox `online_build_500` manifest as the
  reference, `artifacts/toolsandbox_recovery_ladder_20260531_v60/full_standard_prefix500.json`.
- Launch: direct launchd script
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_current_impl_gpt5_launchd.sh`
  running from `/tmp/toolsandbox-sage-local-run`.
- Configuration: fresh registry
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_registry_20260531_141546`,
  actor/user `gpt-4o-mini`, generation model `gpt-5`, generation on, SAGE
  cache off, OpenAI response cache disabled, strict control cache.
- Final status at 2026-05-31 15:16 EDT: complete, control `500/500`, SAGE
  `500/500`.
- Final metrics: reference canonical `0.711718 -> 0.897120` (`+26.05%`
  lift), outcome `0.549273 -> 0.866160`, outcome delta `+0.316886`;
  GPT-5 comparison canonical `0.711718 -> 0.904691` (`+27.11%` lift),
  outcome `0.549273 -> 0.867849`, outcome delta `+0.318575`.
- Difference: GPT-5 comparison improved SAGE canonical score by `+0.007570`,
  canonical lift by `+1.06` percentage points, and outcome delta by
  `+0.001689`.
- Helper/safety counts: reference accepted `7`, called scenarios `181`, reuse
  `356`; GPT-5 comparison accepted `7`, called scenarios `164`, reuse `278`;
  both had `0` current exceptions, generated-tool failed scenarios, runtime
  incidents, and side-effect incidents.
- Comparison artifacts:
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_reference_vs_current_impl_gpt5_comparison_20260531_151627.json`
  and
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_reference_vs_current_impl_gpt5_comparison_20260531_151627.md`.
- Decision: keep / analyze helper attribution and residual misses before
  making a stronger mechanism claim.

## 2026-06-06 - Chapter 3 Tool-Generation-Only Full Standard v258

- Run:
  `outputs/chapter3_tool_generation_only_clean_primary/v258_full_standard_resume_from_v257_polars1/online_build_full_20260606_042103`.
- Dashboard:
  `http://127.0.0.1:63114/outputs/chapter3_tool_generation_only_clean_primary/v258_full_standard_resume_from_v257_polars1/online_build_full_20260606_042103/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  `self-evolving-praxis`, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, control cache
  `1032` cached / `0` fresh, `SAGE_PRAXIS_BRIDGE_POLICY=disabled`,
  routing evidence disabled, no diagnostic force-call environment active.
- Resume/runtime note: v257 stalled at `976/1032` in local Polars dataframe
  filtering; v258 resumed from v257 with `POLARS_MAX_THREADS=1` as a runtime
  stability setting only.
- Final status: complete, control `1032/1032`, SAGE `1032/1032`.
- Final metrics: score `0.692244 -> 0.814618`, delta `+0.122374`, lift
  `+17.68%`; outcome `0.495835 -> 0.727857`, delta `+0.232022`, lift
  `+46.79%`; exact successes `95 -> 360`.
- Tool evidence: `22` accepted tools, `21` called tools, `1063` reuse events,
  generated-tool-called scenarios `629`, generated-tool failed scenarios `1`.
- Safety/runtime: runtime exceptions `0`; runtime incidents `0`; side-effect
  preservation failure rows `14`.
- Major blockers: `next_weekday_time_to_timestamp`, noisy
  `next_service_tool_call`, device-state/service-condition tasks, and
  side-effect preservation failures in message/contact/device planning tools.
- Report:
  `docs/sage_protocol/chapter3_full_standard_v258_report_20260606.md`.
- Decision: keep as completed full-dataset evidence, but do not promote as the
  final clean claim run until the side-effect preservation failures are repaired
  and the outcome target is re-tested.

## 2026-06-06 - Core Implementation Cleanup

- Scope: narrowed active runtime code to the native ToolSandbox SAGE Praxis
  implementation used for Chapter 3 evidence.
- Retained: `scripts/run_sage_protocol.py`, full-run preparation, Chapter 3
  figure rendering, `src/sage_ts/`, `tool_sandbox/`, and focused retained-path
  unit/integration tests.
- Removed: standalone/import-agent runtime package, CyberGym/tau active runtime
  scripts, older v2 campaign/matrix/feedback-packet scripts, one-off static
  registration scripts, toy mechanism modules, and tests tied only to retired
  experiment paths.
- Package boundary: `pyproject.toml` now includes `tool_sandbox*` and
  `sage_ts*`; `sage_agent*` is no longer an install target.
- Evidence boundary preserved: autonomous tool generation, validation/repair,
  registry retention, routing/reuse, same-task fair chance, tool-specific actor
  guidance, contribution logging, and Task Compare dashboards. Primary evidence
  remains `SAGE_PRAXIS_BRIDGE_POLICY=disabled`.
- Accounting fix: generated-tool failures are excluded from the successful
  generated-tool-called set for the same scenario in
  `src/sage_ts/adapters/sage_run_adapter.py`.
- Validation: `make compile` passed; `make test-core` passed with `306 passed,
  4 warnings`; `make test` passed with `623 passed, 4 warnings`; stale-reference
  scan for retired active code paths returned no matches.
- Manifest:
  `docs/sage_protocol/core_implementation_cleanup_manifest_20260606.md`.
- Decision: keep cleanup. The next exact-success validation is a deliberate
  full ToolSandbox evidence run, not a cleanup smoke check.

## 2026-06-06 - Chapter 3 Cost/Lift Repair v271 Full Standard

- Run:
  `outputs/chapter3_cost_lift_repair/v271_improved_full_standard_validation/online_build_full_20260606_125800`.
- Dashboard:
  `http://127.0.0.1:63137/outputs/chapter3_cost_lift_repair/v271_improved_full_standard_validation/online_build_full_20260606_125800/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  `self-evolving-praxis`, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, control cache
  `1032` cached / `0` fresh, `SAGE_PRAXIS_BRIDGE_POLICY=disabled`,
  `SAGE_GENERATED_TOOL_GUIDANCE_MODE=legacy`, synthetic repair off,
  visible-not-called retry off, routing evidence disabled, frozen
  ToolSandbox clock.
- Final status: complete, control `1032/1032`, SAGE `1032/1032`.
- Final metrics: score `0.692244 -> 0.811489`, delta `+0.119246`, lift
  `+17.23%`; outcome `0.495835 -> 0.748297`, delta `+0.252462`, lift
  `+50.92%`; exact successes `95 -> 343`.
- Tool evidence: `22` accepted tools, `21` called tools, `1053` reuse events,
  generated-tool-called scenarios `564`, generated-tool failed scenarios `1`.
- Safety/runtime: runtime exceptions `0`; generated-tool runtime failures were
  nonfatal.
- Cost: candidate `11,404` LLM calls and `18,068,841` tokens; control `4,649`
  LLM calls and `6,205,340` tokens.
- Attribution: generated-tool-called subset showed score lift `+30.97%` and
  outcome lift `+88.44%`; overall score remained below `20%` because late
  noncalled and weakly served task families added enough regressions.
- Decision: retain as one of the best clean full-dataset, bridge-disabled SAGE
  runs to date. Continue cost/lift repair before treating it as the final
  Chapter 3 claim run.

## 2026-06-09 - Clean Fair v078 500 Standard-Order Validation

- Run:
  `outputs/chapter3_clean_fair_primary/v078_500_standard_order/online_build_500_20260608_231904`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/chapter3_clean_fair_primary/v078_500_standard_order/online_build_500_20260608_231904/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_500`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_500.json`, self-evolving Praxis,
  actor/user/generation `gpt-4o-mini`, generation on, SAGE cache off, OpenAI
  response cache disabled, control cache `500` cached / `0` fresh,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  generated-tool contract retry attempts `0`, synthetic repair off,
  side-effect fair-chance extra turns off, runtime generated-tool bundle cap
  `4`, frozen ToolSandbox clock.
- Final status: complete, control `500/500`, SAGE `500/500`.
- Final metrics: score `0.660480 -> 0.878402`, delta `+0.217921`, lift
  `+32.99%`; outcome `0.491010 -> 0.702091`, delta `+0.211082`, lift
  `+42.99%`; exact successes `36 -> 219`.
- Generated-tool evidence: `19` accepted tools, `17` called accepted tools,
  `773` reuse events, generated-tool-called scenarios `419`, generated-tool
  failed scenarios `0`.
- Safety/runtime: runtime exceptions `0`; API exceptions `0`.
- Attribution: generated-tool-called subset showed score lift `+42.67%` and
  outcome lift `+65.35%`. Rows without generated-tool calls were net negative
  and pulled down overall outcome lift.
- Main blockers: no-visible/direct-status rows (`get_wifi`, `get_cellular`),
  direct state-changing rows without generated-tool coverage
  (`remove_contact_with_id`, `send_message_with_phone_number_and_content`),
  selected relationship/message/reminder recency perturbations, and a small
  set of holiday/date rows with milestone-credit misses.
- Methods tracker:
  `docs/sage_protocol/chapter3_clean_sage_methods_tracker.md`.
- Decision: keep as the current primary clean 500 evidence version for the
  no-extra-turn, bridge-disabled methodology. Next full-dataset run should use
  this clean v078 path unless another change improves generated-tool coverage
  through autonomous tool generation and natural tool use.

## 2026-06-09 - Clean Fair v080 Full Standard Paused Checkpoint

- Run:
  `outputs/chapter3_clean_fair_primary/v080_full_direct_status_action_completion_allow_external/online_build_full_20260609_090841`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/chapter3_clean_fair_primary/v080_full_direct_status_action_completion_allow_external/online_build_full_20260609_090841/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  self-evolving Praxis, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, cached controls,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  generated-tool contract retry attempts `0`, synthetic repair off,
  side-effect fair-chance extra turns off, runtime generated-tool bundle cap
  `4`, frozen ToolSandbox clock, RapidAPI fixture cache read-only.
- Pause status: deliberately paused at 414/1032 completed SAGE rows after
  `find_temperature_f_with_location_and_time_diff_low_battery_mode_multiple_user_turn_3_distraction_tools_tool_description_scrambled`.
- Checkpoint metrics: score `0.681699 -> 0.833450`, delta/lift `+0.151752 /
  +22.26%`; outcome `0.360279 -> 0.529744`, delta/lift `+0.169464 /
  +47.04%`.
- Generated-tool-called checkpoint subset: 332 rows, score lift `+28.42%`,
  outcome lift `+66.12%`.
- Safety/runtime at pause: 10 tools born, 9 called, generated-tool failures
  `0`, runtime exceptions `0`, side-effect incidents `0`.
- Resume script:
  `artifacts/chapter3_clean_fair_primary/run_v080_resume_after_0414.sh`.
- Resume seed:
  `artifacts/chapter3_clean_fair_primary/v080_resume_after_0414_registry_seed`.
- Decision: resume from the copied `after_0414` registry checkpoint with
  `--resume-run-root` and `--resume-completed-limit 414`. Do not reuse the
  live registry directory from the interrupted process, because the interrupt
  occurred during the next scenario's OpenAI call.

## 2026-06-09 - Clean Fair v082 Full Resume Before Status Block

- Run:
  `outputs/chapter3_clean_fair_primary/v082_full_resume_before_get_cellular_20260609_200356/online_build_full_20260609_200401`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/chapter3_clean_fair_primary/v082_full_resume_before_get_cellular_20260609_200356/online_build_full_20260609_200401/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  self-evolving Praxis, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, cached controls,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  generated-tool contract retry attempts `0`, synthetic repair off,
  side-effect fair-chance extra turns off, runtime generated-tool bundle cap
  `4`, frozen ToolSandbox clock, RapidAPI fixture cache read-only.
- Resume source:
  `outputs/chapter3_clean_fair_primary/v081_full_resume_after_0414_20260609_192213/online_build_full_20260609_192219`.
- Resume checkpoint: copied registry checkpoint after row 488
  (`after_0488_find_thanksgiving_timestamp_all_tools`) into
  `artifacts/chapter3_clean_fair_primary/v082_resume_before_get_cellular_registry_seed`.
- Corrective method: generated-tool answer completion takes precedence over
  generated-tool adoption guidance after a generated tool returns a final answer
  recommendation; SAGE selects original `end_conversation` when visible on
  post-completion drift turns.
- Validation before run: `python -m py_compile
  src/sage_ts/adapters/openai_toolsandbox_roles.py` passed; focused actor-policy
  suite passed with `25 passed`.
- First audit point: all 8 completed `get_cellular*` rows and all 8 completed
  `get_wifi*` rows reached SAGE score `1.0` and SAGE outcome `1.0`, with
  generated `plan_device_status_lookup` called in every row.
- Status: in progress as of 2026-06-09 20:10 PT. Final metrics pending.

## 2026-06-09 - Clean Fair v083 Full Resume Paused at Row 515

- Run:
  `outputs/chapter3_clean_fair_primary/v083_full_resume_clean_reminder_fix_20260609_204358/online_build_full_20260609_204403`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/chapter3_clean_fair_primary/v083_full_resume_clean_reminder_fix_20260609_204358/online_build_full_20260609_204403/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  self-evolving Praxis, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, cached controls,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  generated-tool contract retry attempts `0`, synthetic repair off,
  side-effect fair-chance extra turns off, runtime generated-tool bundle cap
  `4`, frozen ToolSandbox clock, RapidAPI fixture cache read-only.
- Resume source:
  `outputs/chapter3_clean_fair_primary/v081_full_resume_after_0414_20260609_192213/online_build_full_20260609_192219`.
- Resume checkpoint for v083 start: row 488 from the v081 run.
- Corrective method added before v083: selected-record generated tools are not
  considered ready until visible record evidence exists; reminder-recency tool
  choice keeps original timestamp/context tools in the visible chain before
  generated timestamp conversion and original reminder mutation; generated
  final-answer completion remains ahead of additional tool adoption guidance.
- Pause status: deliberately paused at 515/1032 completed paired rows on
  2026-06-09 20:58 PT. The interrupt occurred during
  `modify_contact_with_message_recency_alt_3_distraction_tools_arg_description_scrambled`;
  that in-flight row is not part of the resume checkpoint.
- Last completed row:
  `modify_contact_with_message_recency_alt_3_distraction_tools`.
- Checkpoint metrics: score `0.707514 -> 0.847946`, delta/lift `+0.140432 /
  +19.85%`; outcome `0.492576 -> 0.697381`, delta/lift `+0.204805 /
  +41.58%`.
- Generated-tool evidence at pause: 17 accepted tools, 692 reuse events, 424
  generated-tool-called scenarios, 1 generated-tool failed scenario.
- Runtime/safety at pause: 0 runtime exceptions in dashboard summary. The stop
  traceback was the intentional keyboard interrupt, not a run failure pattern.
- Resume script:
  `artifacts/chapter3_clean_fair_primary/run_v084_resume_after_0515.sh`.
- Resume seed:
  `outputs/chapter3_clean_fair_primary/v083_full_resume_clean_reminder_fix_20260609_204358/online_build_full_20260609_204403/candidate/online_build_full_candidate_agent_gpt-4o-mini_user_gpt-4o-mini_06_09_2026_20_44_14/registry_checkpoints/after_0515_modify_contact_with_message_recency_alt_3_distraction_tools`.
- Decision: resume shortly from row 515 using v084 script. Do not seed from the
  live registry directory after interruption; use the row-515 registry
  checkpoint.

## 2026-06-11 - Clean Fair v111 Scenario-Name-Free 500

- Run:
  `outputs/chapter3_clean_fair_primary/v111_visible_context_no_scenario_names_direct_route_guard_500/online_build_500_20260611_003844`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/chapter3_clean_fair_primary/v111_visible_context_no_scenario_names_direct_route_guard_500/online_build_500_20260611_003844/dashboard/task_compare.html`.
- Configuration: ToolSandbox `online_build_500`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_500.json`, self-evolving Praxis,
  actor/user/generation `gpt-4o-mini`, generation on, SAGE cache off, OpenAI
  response cache disabled, cached controls, `SAGE_SCENARIO_METADATA_POLICY=visible_context`,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  generated-tool contract retry attempts `0`, synthetic repair off,
  side-effect fair-chance extra turns off, frozen ToolSandbox clock, RapidAPI
  fixture cache read-only.
- Method change: ToolSandbox scenario names are not used for generated-tool birth
  or routing. SAGE uses visible request text, available tool schemas, derived
  visible capability signals, and visible capability-family labels. Online
  reflection remains enabled as explicit task feedback for lifecycle decisions.
- Controls: 500 cached / 0 fresh.
- Score: `0.660480 -> 0.757465`, delta/lift `+0.096984 / +14.68%`.
- Outcome: `0.491010 -> 0.756004`, delta/lift `+0.264994 / +53.97%`.
- Generated-tool evidence: 20 accepted tools, 430 reuse events, 261
  generated-tool-called scenarios in the dashboard summary, 37 generated-tool
  failed scenarios, 0 runtime exceptions.
- Safety/evidence audit: 0 runtime incidents, 0 side-effect preservation
  incidents, and 0 exact ToolSandbox scenario-name findings across scanned
  registry and lifecycle artifacts.
- Attribution finding: generated-tool-called rows remain strongly positive
  while visible-not-called and no-visible-generated-tool rows are slightly
  negative on score. The remaining score gap is therefore not hidden bridge
  behavior; it is concentrated in natural tool adoption, contract robustness,
  and scorer-milestone mismatch cases.
- Decision: promote v111 as the current clean 500-task candidate for the
  scenario-name-free Chapter 3 methodology. Do not restore scenario-name
  routing, bridge completions, or SAGE-only retry turns.

## 2026-06-12 - Pre-Final Full Dataset Uncached Parallel Run v140

- Run:
  `outputs/chapter3_clean_fair_primary/v140_prefinal_full_uncached_parallel/online_build_full_20260612_065229`.
- Dashboard:
  `http://127.0.0.1:62650/outputs/chapter3_clean_fair_primary/v140_prefinal_full_uncached_parallel/online_build_full_20260612_065229/dashboard/task_compare.html`.
- Purpose: pre-final full-dataset data collection with a fresh uncached baseline
  and fresh SAGE arm running in parallel.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  self-evolving Praxis, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, control cache `off`,
  `--parallel-arms`, `SAGE_SCENARIO_METADATA_POLICY=visible_context`,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  birth-scenario fair chance off, side-effect fair-chance extra turns off,
  generated-tool contract retry attempts `0`, synthetic repair off, runtime
  generated-tool bundle cap `4`, frozen ToolSandbox clock, RapidAPI fixture
  cache read-only. Live dashboard refresh uses
  `SAGE_DASHBOARD_LOAD_TASK_MESSAGES=0` to avoid serializing full transcripts
  during long parallel runs.
- Baseline/SAGE execution discipline: both arms are live OpenAI calls; no
  cached controls are eligible; dashboard comparison uses paired completed rows
  while the two arms progress independently.
- Initial live check at 63 paired rows: score `0.788826 -> 1.000000`,
  delta/lift `+0.211174 / +26.77%`; outcome `0.613270 -> 1.000000`,
  delta/lift `+0.386730 / +63.06%`; 5 accepted tools, 53
  generated-tool-called scenarios, 0 generated-tool failures, 0 runtime
  exceptions; usage summaries showed 0 cached LLM calls in both arms.
- Mid-run live check at 145 paired rows: score `0.585372 -> 0.784893`,
  lift `+34.08%`; outcome `0.271628 -> 0.585808`, lift `+115.67%`; 6
  accepted tools, 131 generated-tool-called scenarios, 0 generated-tool
  failures, 0 runtime exceptions; usage summaries still showed 0 cached LLM
  calls in both arms.
- Fast-dashboard live check at 302 paired rows: score lift `+15.59%`;
  outcome lift `+62.90%`; 10 accepted tools, 200 generated-tool-called
  scenarios, 0 generated-tool failures, 0 runtime exceptions, and 0 cached LLM
  calls in both arms. Interpretation at this point: outcome lift remains above
  the Chapter 3 minimum, while canonical/reference score lift has diluted below
  20% as the manifest enters rows with weaker generated-tool coverage and/or
  milestone accounting mismatch.
- Fast-dashboard live check at 502 paired rows: score lift `+8.73%`; outcome
  lift `+52.11%`; 13 accepted tools, 330 generated-tool-called scenarios, 0
  generated-tool failures, 0 runtime exceptions, and 0 cached LLM calls in both
  arms. Interpretation at this point: outcome lift recovered slightly above the
  Chapter 3 minimum, but canonical/reference score lift remains well below the
  desired score target.
- 500-row diagnostic: generated-tool-called rows were materially stronger than
  not-called rows. Called rows had mean score delta about `+0.089` and mean
  outcome delta about `+0.279`; not-called rows had mean score delta about
  `+0.029` and mean outcome delta about `+0.071`. The main drag at this point
  was not tool failure; it was weaker coverage or regressions in temperature,
  days-till/date, and some distance/current-location rows.
- Fast-dashboard live check at 759 paired rows: score lift `+7.73%`; outcome
  lift `+63.07%`; 20 accepted tools, 455 generated-tool-called scenarios, 0
  generated-tool failures, 0 runtime exceptions, and 0 cached LLM calls in both
  arms. Baseline/control had completed all 1,032 tasks by this point; SAGE was
  still running. Interpretation: outcome lift remained strong, while
  canonical/reference score lift stayed below the score target.
- Final result: score `0.733175 -> 0.782680`, delta/lift
  `+0.049505 / +6.75%`; outcome `0.452803 -> 0.655135`, delta/lift
  `+0.202333 / +44.68%`.
- Final lifecycle evidence: 22 accepted tools, 534 generated-tool-called
  scenarios, 14 generated-tool failed scenarios, 0 runtime exceptions.
- Final usage evidence: baseline `9,489` live LLM calls and `10,455,939`
  tokens; SAGE `10,655` live LLM calls and `16,389,805` tokens; cached LLM
  calls `0 / 0`.
- Final attribution split: generated-tool-called rows drove the observed lift.
  Called rows had mean score delta about `+0.096` and mean outcome delta about
  `+0.341`; not-called rows had mean score delta about `-0.001` and mean
  outcome delta about `+0.012`.
- Final caveats: outcome lift was positive but below the `50%` target; score
  lift was positive but below the desired score target. The 14 generated-tool
  failed rows all involved `relative_day_time_to_timestamp` on reminder
  recency/yesterday search variants. Contribution audit reported 5
  side-effect-preservation flags: 2 for `plan_device_state_action_sequence_v3`
  and 3 for `select_action_target_by_recency`; these require adjudication
  before treating this run as final claim evidence.
- Status: complete.
- Dashboard note: the original parent dashboard exporter became stale around
  row 221 because full transcript serialization was too heavy for live refresh.
  A separate fast live-dashboard refresher was started with
  `SAGE_DASHBOARD_LOAD_TASK_MESSAGES=0`; this changes dashboard payload size
  only and does not affect scoring, tool generation, routing, LLM calls, or
  task execution.

## 2026-06-13 - Canonical SAGE Full Dataset v061

- Run:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`.
- Dashboard:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare.html`.
- Protocol manifest:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json`.
- Configuration: ToolSandbox `online_build_full`, manifest
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`,
  self-evolving Praxis, actor/user/generation `gpt-4o-mini`, generation on,
  SAGE cache off, OpenAI response cache disabled, cached controls,
  `SAGE_PRAXIS_BRIDGE_POLICY=disabled`,
  `SAGE_SCENARIO_METADATA_POLICY=visible_context`,
  `SAGE_DISABLE_SCENARIO_NAME_BIRTH=1`,
  `SAGE_DISABLE_SCENARIO_NAME_ROUTING=1`, generated-tool guidance `minimal`,
  generated-tool docstrings `compact`, visible-not-called retry off,
  side-effect fair-chance extra turns off, generated-tool contract retry
  attempts `0`, generated-tool synthetic repair off, runtime generated-tool
  bundle cap `4`, frozen ToolSandbox clock, RapidAPI fixture cache read-only.
- Completed paired tasks: `1032/1032`.
- Score: `0.733214 -> 0.801186`, delta/lift `+0.067971 / +9.27%`.
- Outcome: `0.454251 -> 0.757267`, delta/lift `+0.303016 / +66.71%`.
- Exact successes: baseline `201`, SAGE `406`.
- Generated-tool evidence: 22 accepted/generated tools in registry, 21 called
  tools, 1,171 reuse events, 825 generated-tool-called scenarios, 3
  generated-tool failure rows.
- Runtime/safety: 0 runtime exceptions, 0 runtime incidents, 1 side-effect
  preservation incident.
- LLM usage: baseline `10,465,294` tokens; SAGE `17,245,671` tokens.
- Decision: preserve v061 as the canonical SAGE publication configuration.
  Earlier v70/v71/v111/v140/v258 runs remain historical comparison evidence,
  but v061 is now the implementation and evidence boundary referred to as
  "SAGE" in the repository.
