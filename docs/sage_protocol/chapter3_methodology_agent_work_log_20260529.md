# Chapter 3 Methodology Agent Work Log - 2026-05-29

## Run Restart - Full ToolSandbox v71-Style No-Cache Usage Run

- Prior mixed-cache run stopped at user request:
  `outputs/self_evolving_sage/full_toolsandbox_v71_20260529_183043/online_build_full_20260529_184527`.
- Cancellation log preserved:
  `artifacts/self_evolving_sage/full_toolsandbox_v71_20260529_183043_artifacts/restarted_by_user_cancelled_mixed_cache_20260529_194201.log`.
- Reason: restart without cached baseline so baseline LLM calls and token use can
  be measured directly.
- Usage sanity check before restart:
  `artifacts/self_evolving_sage/usage_sanity_20260529_194509`.
- Sanity result: direct actor call and generation call both used
  `gpt-4o-mini-2024-07-18`, recorded live call counts, and recorded token
  totals.
- Dashboard/usage patch validation:
  `conda run --no-capture-output -n toolsandbox-sage python -m py_compile ...`
  passed for the touched dashboard, adapter, usage, and runner modules.
- Focused tests:
  `PYTHONPATH=src:. conda run --no-capture-output -n toolsandbox-sage pytest tests/unit/test_run_metrics.py tests/unit/test_dashboard_exporters.py -q`
  passed, `19 passed`.

### Run Card - 20260529_194548 - full_toolsandbox_v71_nocache_usage

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369`
- Implementation: native ToolSandbox self-evolving Praxis, v71-style settings,
  fresh full-dataset baseline.
- Hypothesis: removing the control baseline cache allows direct measurement of
  baseline LLM calls and token use while retaining the validated native SAGE
  lifecycle configuration.
- Command: `scripts/run_sage_protocol.py --mode online_build_full --sage-policy self-evolving-praxis --agent gpt-4o-mini --user gpt-4o-mini --generation-model gpt-4o-mini --generation on --disable-openai-response-cache --cache-mode off --control-cache off --routing-evidence-mode disabled --freeze-toolsandbox-clock --allow-contaminated-preflight`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Manifest SHA-256:
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`
- Sample: full benchmark, `1032` scenarios.
- Models: actor `gpt-4o-mini`, user `gpt-4o-mini`, generation
  `gpt-4o-mini`.
- Cache policy: control baseline cache `off`; SAGE task cache `off`; OpenAI
  response cache disabled; RapidAPI fixture cache read-only.
- Run path:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554`
- Dashboard:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554/dashboard/task_compare.html`
- Live usage check: after 13 fresh control scenarios, dashboard/exported
  summary reported `43` live LLM calls, `0` cached LLM calls, and `42481`
  total tokens.
- Dashboard no-cache display repair: because `--control-cache off` does not
  naturally create a control-cache report, the live dashboard initially hid the
  cache-policy panel even though the run was configured correctly. An explicit
  no-cache report was added to the run root and the dashboard fallback now
  renders `0 cached / 1032 fresh`, `Mode off`, and `Source fresh`.
- Live display check after repair: task compare showed baseline `183/1032`
  running, SAGE `0/1032` pending, `1175` live LLM calls, `0` cached LLM calls,
  and no browser console errors.
- Per-task LLM usage accounting cache: added
  `scripts/cache_llm_usage_by_task.py` and started a watcher writing
  `llm_usage_task_cache.json` plus `llm_usage_task_cache.jsonl` in the run root.
  The cache policy is `write_completed_tasks_immediately_no_minimum_count`;
  it records counts/tokens only, not prompts or responses.
- Retroactive cache backfill: initial pass captured `186` completed control
  tasks, `1210` live LLM calls, `0` cached calls, and `1475567` total tokens.
  The watcher then advanced to `187` completed control tasks as the next task
  finished.
- Dashboard refresh hardening: task compare, task focus, and overview pages now
  tolerate transient partial JSON reads during active file writes and retry on
  the next refresh instead of surfacing browser console errors. A fresh browser
  tab verified task compare with no console errors after an auto-refresh cycle.
- Safety: pending run completion.
- Decision: running.
- Chapter 3 implication: this run is the direct token/call accounting companion
  to the prior high-lift v71 broad500 evidence.

### Live Disconnect Analysis - 2026-05-30 00:24 ET

- User concern: the live no-cache full run is not showing lift close to the
  prior v71 broad500 result.
- Current live status at the checkpoint: control `1032/1032` complete; SAGE
  candidate approximately `510/1032` complete; control LLM calls `8627`;
  candidate LLM calls approximately `3898`; all recorded OpenAI events use
  `gpt-4o-mini`; cached LLM calls remain `0`.
- Current paired completed slice: canonical/reference approximately
  `0.7390 -> 0.7776`, delta `+0.0386`, lift `+5.23%`; outcome/task completion
  delta approximately `+0.0625`; accepted helpers `9`; generated-tool-called
  scenarios `206`; generated-tool failures `0`.
- This is not an apples-to-apples reproduction of v71 broad500. The prior v71
  result used `docs/sage_protocol/manifests/v2_1_formal_500.json`, whose first
  scenario is `remove_contact_by_phone`; this run uses
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`, whose
  first scenario is `add_contact_with_name_and_phone_number`.
- The no-cache control baseline is materially stronger than the v71 cached
  control. On the formal500 scenario names, v71 cached control was `0.656799`
  canonical and `0.494746` outcome, while this run's fresh control scores
  approximately `0.772797` canonical and `0.721944` outcome on the same names.
  This compresses the available lift.
- The full manifest order delays several of the v71 high-lift helper lanes. In
  the full manifest, `modify_contact_with_message_recency` starts at index
  `504`, `remove_contact_by_phone` at `576`, `search_message_with_recency_latest`
  at `688`, `search_message_with_recency_oldest` at `720`,
  `send_message_with_contact_content_cellular_off` at `880`, and
  `update_contact_relationship_with_relationship` at `984`. In the formal500
  run those same families appear near the beginning.
- Helper lifecycle confirms the ordering effect. v71 broad500 had 16 accepted
  helpers by 500 tasks. This full run had only 6 accepted helpers before the
  delayed contact/recency family began; it jumped to 9 accepted helpers shortly
  after reaching `modify_contact_with_message_recency` at index `504`.
- Preliminary conclusion: the smaller live lift is primarily explained by a
  stronger fresh baseline plus a different full-dataset ordering that delays
  high-yield helper birth opportunities. A secondary possibility remains code
  drift from the current dirty checkout versus the May 14 v71 artifacts, but no
  model/config mismatch has been observed so far.
- Dashboard data enrichment: added `scripts/patch_live_dashboard_data.py` and
  started a watcher for the active run. This does not alter execution or
  scoring; it patches `dashboard/task_compare_data.json` after runner writes so
  the tool drawer can show live visibility counts, called-subset deltas, and
  side-effect preservation rows before the final helper contribution export.
  At first enrichment, the dashboard showed 10 accepted tools, 7 naturally
  called tools, 10 visible tools, 77 outcome-gain rows, 29 outcome-regression
  rows, and 3 side-effect preservation rows.
- Additional implementation disconnect found: the current run rejected
  `resolve_search_window_or_bounds` twice under canonical key
  `derived_value:recency_timestamp_bounds` because the repaired broad helper was
  validated against obsolete bounds-only examples using `recency_label`. The
  error was `TypeError: resolve_search_window_or_bounds() got an unexpected
  keyword argument 'recency_label'`. In v71, this helper was accepted from
  `derived_value:resolve_search_window_or_bounds` and was one of the highest-use
  helpers (`83` called scenarios), so this lane failure is a real latest-code
  regression relative to the v71 artifact.
- Next-run repair: updated `src/sage_ts/orchestration/online_birth.py` so when a
  narrow `recency_timestamp_bounds` observation is repaired/upgraded to
  `resolve_search_window_or_bounds`, validation uses the broader search-plan
  contract examples. Added a focused unit test in
  `tests/unit/test_online_birth.py`. Validation:
  `PYTHONPATH=src:. pytest tests/unit/test_online_birth.py -q` passed,
  `44 passed, 2 warnings`. This source repair was made after the active run
  started and is not part of the active run's loaded execution path.

### Live Disconnect Analysis Update - 2026-05-30 00:45 ET

- Current live status: control `1032/1032`; SAGE candidate `615/1032`;
  canonical/reference `0.752282 -> 0.771548`, delta `+0.019266`, lift
  `+2.56%`; outcome/task completion `0.623709 -> 0.696125`, delta `+0.072415`.
- Usage accounting: control and completed candidate tasks have per-task usage
  rows; total recorded LLM calls `13098`, cached calls `0`, total tokens
  `17708691`. All inspected usage events use `gpt-4o-mini`.
- Formal500 overlap checkpoint: only `185/500` formal500 scenario names have
  completed in the full-manifest run. On that same subset, current fresh control
  is `0.808151` canonical and `0.735934` outcome, while v71's cached control on
  those same scenario names was `0.656123` canonical and `0.484067` outcome.
  The current SAGE arm is positive on outcome over fresh control
  (`+0.085785`) but negative on canonical/reference (`-0.022114`) for this
  partial formal-overlap slice; v71 on the same names had `+0.218223`
  canonical and `+0.435562` outcome. This confirms the disconnect is not only
  denominator compression; current-code behavior also differs from the v71
  artifact.
- Order effect quantified: the 500 formal scenarios are scattered across the
  1032-task full manifest (`min=0`, `median=723.5`, `max=1031`). High-yield
  v71 families that appeared in the first dozen formal500 tasks are delayed in
  the full manifest: `remove_contact_by_phone` from index `0` to `576`,
  `modify_contact_with_message_recency` from `5` to `504`,
  `search_message_with_recency_latest` from `6` to `688`,
  `send_message_with_contact_content_cellular_off` from `8` to `880`, and
  `update_contact_relationship_with_relationship` from `11` to `984`.
- Tool contribution checkpoint: current enriched dashboard shows `13` accepted
  tools, `9` naturally called tools, `13` visible tools, `84` outcome-gain rows,
  `29` outcome-regression rows, `4` side-effect preservation rows, and `0`
  runtime incidents. In v71, the top high-yield helper
  `resolve_search_window_or_bounds` had `83` calls with called-subset outcome
  delta `+0.588593`; in the active run it has only `8` calls so far and
  outcome delta `0.0` after the earlier validation mismatch delayed acceptance.
- Dashboard visibility repair: updated the task-compare dashboard template and
  live HTML patcher so the header now displays a live tool-contribution panel
  without requiring the drawer click path. The panel reports visible tools,
  called tools, outcome gain/regression rows, side-effect/runtime rows, and the
  top called helpers with visible/called counts and called-subset outcome
  deltas. Browser verification after reload showed the panel rendering at
  `648/1032` matched tasks with `13` visible tools, `9` called tools, `93`
  outcome-gain rows, `35` outcome-regression rows, `4` side-effect preservation
  rows, and `0` runtime incidents. Validation:
  `python -m py_compile scripts/patch_live_dashboard_refresh.py src/sage_ts/dashboard/task_compare_template.py`,
  `PYTHONPATH=src:. pytest tests/unit/test_dashboard_exporters.py -q`, and
  `git diff --check` passed.
- Fast-block dashboard note: when the runner entered fast recency blocks, it
  rewrote `task_compare_data.json` frequently enough that the five-second
  enrichment watcher could briefly fall behind and the dashboard would show
  reuse-event fallback rows. A one-second live enrichment watcher was started
  for the active run, restoring the visible contribution panel between runner
  writes.
- Recency/message checkpoint at about `698/1032`: `resolve_search_window_or_bounds`
  recovered to `42` visible / `32` called with called-subset outcome delta
  `+0.214359`; `select_message_content_by_recency` was born during
  `search_message_with_recency_latest` and reached `10` visible / `9` called
  with called-subset outcome delta `+0.206610`. Overall completed-slice outcome
  delta remained only about `+0.077621`, so the later helper recovery is real
  but not enough to recreate the v71 compounding effect.
- Family-level comparison after first message-recency tasks: current
  `search_message_with_recency_latest` is positive (`+0.254033` outcome) but
  much weaker than v71 (`+0.761378` outcome); current
  `modify_reminder_with_recency_latest` remains `+0.000000` outcome while v71
  was `+0.994949`; current `remove_reminder_with_recency_latest` is `+0.312500`
  outcome versus v71 `+0.803713`. This supports the conclusion that there is
  code-path drift in recency/action helper behavior in addition to the no-cache
  baseline and manifest-order changes.

### Live Disconnect Analysis Update - 2026-05-30 01:15 ET

- Current live status: control `1032/1032`; SAGE candidate approximately
  `781/1032`; completed-slice canonical/reference `0.757727 -> 0.786831`,
  delta `+0.029104`, lift `+3.84%`; outcome/task completion
  `0.632672 -> 0.714505`, delta `+0.081833`.
- Usage accounting remains clean for the requested no-cache measurement:
  recorded events are all `gpt-4o-mini`, cached LLM calls remain `0`, and the
  per-task usage cache is recording prompt/completion/total token counts for
  both arms.
- The current run should not be described as a v71 reproduction. It differs
  from v71 on three material axes:
  - v71 used the 500-task formal manifest with cached controls; this run uses
    the 1032-task full manifest with fresh controls.
  - v71's high-yield helper opportunities appeared in the first dozen tasks;
    in the full manifest, the same families are delayed hundreds of tasks, so
    helper compounding starts much later.
  - latest-code behavior differs from the May 14 v71 artifact. The clearest
    artifact-backed regression is the early rejection of
    `resolve_search_window_or_bounds` under the obsolete
    `recency_timestamp_bounds` validation signature.
- Formal500 overlap after the delayed recency block is still much weaker than
  v71. On completed formal500-overlap scenarios, current fresh controls are far
  stronger than v71 cached controls, and current SAGE gains are concentrated in
  fewer lanes. Example common-family deltas:
  `modify_contact_with_message_recency` current `+0.118047` outcome vs v71
  `+0.805666`; `search_message_with_recency_latest` current `+0.311702` vs v71
  `+0.761378`; `search_message_with_recency_oldest` current `-0.035258` vs v71
  `+0.455277`; `modify_reminder_with_recency_latest` current `+0.000000` vs
  v71 `+0.994949`.
- Top helper contribution comparison supports the same conclusion. In v71,
  `resolve_search_window_or_bounds` had `83` calls with called-subset outcome
  delta `+0.588593`; in the active run it has recovered to `80` calls but only
  about `+0.189286` called-subset outcome delta at this checkpoint.
  `select_message_content_by_recency` is similarly weaker (`+0.200565` current
  vs `+0.712039` v71). This is not just dashboard display; it is a different
  contribution profile.
- Provisional explanation to carry forward: the observed low lift is explained
  by a stronger fresh baseline, changed full-manifest ordering, and real
  latest-code drift in at least the recency-window helper path. The active run
  remains useful as a full-dataset no-cache usage and robustness measurement,
  but it should not be promoted as the strongest ToolSandbox SAGE evidence
  unless final results unexpectedly close the gap and contribution/safety
  audits support that promotion.
- Ruled-out cause: the active run did load the self-evolving Praxis lifecycle
  preset defaults. The event ledger records proactive birth `1`, proactive
  scope `just_in_time`, same-scenario fair chance `1`, safe-abstain birth `1`,
  Praxis bridge policy `combined`, and feature preset
  `contract_synthesis,candidate_repair,dependency_logic,medium_grain_skills`.
  Therefore the lower lift is not explained by accidentally disabling the
  lifecycle machinery.

### Live Disconnect Analysis Update - 2026-05-30 01:35 ET

- Current live status: control `1032/1032`; SAGE candidate approximately
  `907/1032`; completed-slice canonical/reference delta about `+0.043694`;
  outcome/task-completion delta about `+0.093913`; naturally called generated
  helper scenarios `443`.
- Dashboard enrichment status: the runner can still briefly overwrite
  `task_compare_data.json` with the base exporter during fast blocks, but the
  live patch watcher and manual patch restored the contribution panel. The
  restored panel at this checkpoint reports `167` outcome-gain rows, `61`
  outcome-regression rows, `4` side-effect preservation rows, and `0` runtime
  incidents.
- The strongest numeric explanation is now quantified on the formal500 overlap.
  Of the formal500 scenarios completed so far in the full run, `398/500` have
  completed SAGE results. On those same scenarios, the active fresh control
  scores `0.701393` outcome, while the v71 cached control scored `0.408984`.
  The active SAGE arm scores `0.803003`, while v71 SAGE scored `0.861516`.
  Thus the apparent lift shrinks mainly because the no-cache fresh baseline is
  about `+0.292409` outcome points stronger, with a smaller but real SAGE-side
  shortfall of about `-0.058513`.
- The manifest-order effect remains material. The formal500 scenario positions
  in the full manifest have min/median/max indices `0 / 723.5 / 1031`. Several
  high-yield v71 opportunities moved from the first dozen formal500 tasks to
  much later full-manifest positions: `remove_contact_by_phone` `0 -> 576`,
  `modify_contact_with_message_recency` `5 -> 504`,
  `search_message_with_recency_latest` `6 -> 688`,
  `search_message_with_recency_oldest` `7 -> 720`,
  `send_message_with_contact_content_cellular_off` `8 -> 880`, and
  `update_contact_relationship_with_relationship` `11 -> 984`.
- The clearest current-code regression is confirmed in `tool_birth_events.jsonl`:
  `resolve_search_window_or_bounds` was rejected twice for
  `derived_value:recency_timestamp_bounds` because the repaired broad helper was
  validated with obsolete `recency_label` examples:
  `TypeError: resolve_search_window_or_bounds() got an unexpected keyword
  argument 'recency_label'`. It was later accepted under
  `derived_value:resolve_search_window_or_bounds` at
  `modify_reminder_with_recency_latest`, after it had missed earlier
  compounding opportunities.

### Final Full-Dataset No-Cache Run Result - 2026-05-30 01:55 ET

- Run completed:
  `outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554`.
  Dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/full_toolsandbox_v71_nocache_usage_20260529_194548/online_build_full_20260529_194554/dashboard/task_compare.html`.
- Final full-sample scores: canonical/reference `0.750138 -> 0.791681`,
  delta `+0.041543`, lift `+5.54%`; outcome/task completion
  `0.648824 -> 0.741156`, delta `+0.092332`.
- Usage accounting: control and SAGE both completed `1032/1032`; total recorded
  LLM calls `15,651`; prompt/completion/total tokens
  `21,066,079 / 390,872 / 21,456,951`; cached LLM calls `0`. All recorded
  model events used `gpt-4o-mini` (`8,627` control, `7,024` SAGE; sources:
  `8,534` actor, `7,096` user, `21` generation).
- Control discipline: baseline cache `off`, control source `fresh`,
  `0` cached controls and `1,032` fresh controls. OpenAI response cache was
  disabled. Manifest hash for the full run:
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`.
- Tool lifecycle and contribution: `26` birth rows; `17` accepted helpers,
  `9` rejected, `14` with repair attempts; `546` naturally called generated-tool
  scenarios; `17` visible tools, `14` called tools; `217` outcome-gain rows,
  `68` outcome-regression rows; `0` runtime incidents.
- Safety: `4` side-effect preservation rows remained for audit
  (`prepare_reminder_creation_args`, `next_weekday_time_to_timestamp`,
  `plan_device_state_action_sequence_v3`, and
  `select_message_counterparty_for_contact_update`). This is worse than the
  clean v70 safety-reference run and requires adjudication before claim
  promotion.
- Formal500 overlap final comparison: on all `500` formal500 scenarios, the
  active no-cache fresh-control run scored outcome `0.721944 -> 0.830761`
  (`+0.108816`), while v71 scored `0.494746 -> 0.880845` (`+0.386099`). The
  current control is `+0.227198` outcome points stronger than v71's cached
  control, and the current SAGE arm is `-0.050084` below v71 on the same
  scenario names.
- Final interpretation: this run is useful as a full-dataset, no-cache usage
  and robustness diagnostic, but it does not supersede v71. The low lift is
  explained by three interacting changes: fresh controls are much stronger than
  cached v71 controls, full-manifest order delays high-yield helper lanes, and
  latest-code behavior regressed at least the recency-window helper path.
- Validation after completion passed: `git diff --check`; py_compile for the
  runner/full-run prep/dashboard/birth files; and
  `PYTHONPATH=src:. pytest tests/unit/test_online_birth.py tests/unit/test_dashboard_exporters.py tests/unit/test_sage_agent_standalone.py tests/unit/test_rapid_api_cache.py -q`
  (`161 passed, 2 warnings`).

### Full-Dataset Recovery Run V6 - 2026-05-30

- Completed the standard full-dataset recovery run at
  `outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256`.
- Dashboard:
  `http://127.0.0.1:62624/outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256/dashboard/task_compare.html`.
- Configuration: native ToolSandbox self-evolving Praxis, `online_build_full`,
  actor/user/generation all `gpt-4o-mini`, generation on, SAGE cache off,
  OpenAI response cache disabled, empty starting registry, control cache
  `use-if-eligible`.
- Control source: mixed, `689` cached controls and `343` fresh controls.
- Final result: canonical/reference `0.693253 -> 0.829701` (`+0.136448`,
  `+19.68%`); outcome/task completion `0.506399 -> 0.788966` (`+0.282568`,
  `+55.80%`); exact successes `148 -> 498`; runtime exceptions `0`; protocol
  gate `PASS`.
- Lifecycle evidence: `17` live-born helpers accepted; generated helpers called
  in `556` scenario contexts; dashboard contribution rows `459` outcome gains
  and `52` outcome regressions; generated-tool runtime failures `0`.
- Safety caveat: `2` side-effect preservation rows for
  `prepare_reminder_creation_args`, both on
  `add_reminder_content_and_week_delta_and_time_multiple_user_turn_alt`
  variants.
- Blocker reassessment added to
  `docs/sage_protocol/toolsandbox_full_v6_recovery_report_20260530.md`: ceiling
  compression is not a primary explanation because the full-run control means
  were low enough for substantial improvement. The lift gap versus formal500 v6
  is better explained by missing helper coverage/adoption in full-only
  service-answer lanes, rejection of `plan_send_message_contact_lookup` on exact
  advisory text mismatches, weak natural adoption of
  `extract_service_answer_field`, `prepare_reminder_creation_args`, and
  `prepare_safe_action_or_abstain`, canonical-score loss from `find_days`, and
  add-reminder multi-turn timestamp/location regressions.
