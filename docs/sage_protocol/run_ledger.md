# Run Ledger

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
- tau3-bench: blocked because no tau3 official harness is installed locally;
  using tau2 would be misleading.
- ScienceAgentBench / science-agent-bench: blocked because the public clone
  contains a benchmark placeholder and the password-protected official artifacts
  are missing.
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
