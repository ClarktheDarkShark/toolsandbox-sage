# Chapter 3 Full Standard SAGE Run Report - v258 - 2026-06-06

## Decision

This run completed the full standard ToolSandbox sample and should be kept as
current full-dataset evidence for the tool-generation-only SAGE line. It is not
yet a clean final promotion run because the outcome lift missed the 50 percent
target and the audit recorded side-effect preservation failures.

## Run Identity

- Run id: `v258_full_standard_resume_from_v257_polars1`
- Branch: `codex/sage-standalone-agent`
- Commit: `33d73692ec4c4f6c60b4cb6aa87d2350017e90e9`
- Run root:
  `outputs/chapter3_tool_generation_only_clean_primary/v258_full_standard_resume_from_v257_polars1/online_build_full_20260606_042103`
- Dashboard:
  `http://127.0.0.1:63114/outputs/chapter3_tool_generation_only_clean_primary/v258_full_standard_resume_from_v257_polars1/online_build_full_20260606_042103/dashboard/task_compare.html`
- Reproduction script:
  `artifacts/chapter3_tool_generation_only_clean_primary/run_v258_full_standard_resume_from_v257_polars1.sh`
- Resume source:
  `outputs/chapter3_tool_generation_only_clean_primary/v257_full_standard_resume_from_v256/online_build_full_20260606_014025`

## Configuration

- Mode: `online_build_full`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Policy: `self-evolving-praxis`
- Actor model: `gpt-4o-mini`
- User model: `gpt-4o-mini`
- Generation model: `gpt-4o-mini`
- Generation: on
- SAGE task cache: off
- OpenAI response cache: disabled
- Control cache: `use-if-eligible`, `1032` cached and `0` fresh
- Bridge policy: `SAGE_PRAXIS_BRIDGE_POLICY=disabled`
- Routing evidence mode: disabled
- Diagnostic force-call environment: none active
- ToolSandbox clock: frozen
- Runtime stability setting added for the final resume: `POLARS_MAX_THREADS=1`

## Final Metrics

- Completed paired tasks: `1032/1032`
- Score: baseline `0.692244` to SAGE `0.814618`
- Score delta/lift: `+0.122374`, `+17.68%`
- Outcome: baseline `0.495835` to SAGE `0.727857`
- Outcome delta/lift: `+0.232022`, `+46.79%`
- Exact successes: baseline `95`, SAGE `360`, delta `+265`
- Score gains/regressions/preserved: `612 / 223 / 197`
- Outcome gains/regressions/preserved: `511 / 147 / 142`
- Accepted tools: `22`
- Called accepted tools: `21`
- Accepted but uncalled tools: `constraint_to_action_planner`
- Tool reuse events: `1063`
- Scenarios with generated tool calls: `629`
- Generated-tool failed scenarios: `1`
- Runtime exceptions: `0`

## Tool-Driven Evidence

The strongest evidence is in the generated-tool-called subset. Across `629`
scenarios where SAGE actually called generated tools, the mean score delta was
`+0.158`; across the `580` outcome-scored scenarios in that subset, the mean
outcome delta was `+0.300`. That subset produced `410` outcome gains and `73`
outcome regressions.

The non-called buckets were much weaker. Generated tools were visible but not
called in `228` scenarios, with mean outcome delta `+0.060` across outcome
scored rows. No generated tool was visible in `175` scenarios, with mean outcome
delta `+0.048`. The aggregate run is therefore primarily supported by actual
generated tool use, not by a broad non-tool advantage.

## Major Blockers

The full-run outcome target was not met. The required minimum was a 50 percent
outcome lift; this run reached `46.79%`, short by `3.21` percentage points. The
score target of 10 percent was met.

The largest negative tool pattern is `next_weekday_time_to_timestamp`. It was
called in `32` scenarios, had total score delta `-0.779`, total outcome delta
`-3.724`, and produced no outcome gains. The associated
`add_reminder_content_and_weekday_delta_and_time` family was the worst aggregate
outcome-loss family.

The `next_service_tool_call` tool is noisy and low value in the current run. It
was called in `84` scenarios, had near-zero mean outcome delta, recorded `32`
outcome regressions, and accounted for `6` side-effect preservation failure
rows. It should be repaired, narrowed, or parked before a final claim run.

Device-state and service-condition tasks remain weak. The most important
negative families were `send_message_with_contact_content_cellular_off`,
`find_temperature_f_with_location_wifi_off`, `cellular_off`, `wifi_off`,
`turn_on_wifi_low_battery_mode_implicit`, and
`turn_on_location_low_battery_mode_implicit`.

The contribution audit recorded `14` side-effect preservation failure rows
across five tools: `next_service_tool_call`, `plan_message_counterparty_search`,
`prepare_reminder_creation_args`, `prepare_side_effect_args_from_selected_record`,
and `select_message_counterparty_for_contact_update`. Runtime incidents were
zero, but these preservation failures are a major evidence-boundary issue.

Early-window ceiling effects should still be considered for small prefixes, but
they are not the main explanation for this full run. The full-run baseline was
`0.692` on score and `0.496` on outcome, so there was substantial room for lift.

## Runtime Note

The v257 resume stalled at `976/1032` while processing
`turn_on_wifi_low_battery_mode_implicit`. Sampling showed the process was
spinning inside local Polars dataframe filtering rather than waiting on OpenAI
or executing generated tool code. A single-scenario diagnostic completed with
`POLARS_MAX_THREADS=1`, so v258 resumed from v257 with only that runtime
stability setting added. This changed run stability, not SAGE tool generation,
tool routing, or scoring logic.

## Next Repair Targets

Before another final full run, the major repair targets are:

1. Repair or park `next_weekday_time_to_timestamp`.
2. Narrow or replace `next_service_tool_call`.
3. Add stricter validation for side-effect preservation in message/contact and
   device-state planning tools.
4. Re-run the 40/60/250 ladder before another full run, with the same
   bridge-disabled, generated-tool-only evidence boundary.
