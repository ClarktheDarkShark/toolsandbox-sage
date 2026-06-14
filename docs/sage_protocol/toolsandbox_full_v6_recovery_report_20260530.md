# ToolSandbox Full Dataset V6 Recovery Report - 2026-05-30

This report follows the SAGE global working agreement and treats SAGE as the
self-evolving research system under evaluation.

## Decision Label

`FULL_DATASET_RECOVERY_PASSES_MINIMUM_GATE_DOES_NOT_SUPERSEDE_FORMAL500_V6`

The standard full-dataset run recovered meaningful SAGE lift and passed the
minimum full-run target requested for this diagnostic: score lift exceeded 10%
and outcome lift exceeded 50%. It did not reproduce the formal500 v6 lift, and
it should not replace formal500 v6 or v71 as the strongest ToolSandbox evidence
without additional repair and an uncached confirmation run.

## Run Card - 2026-05-30 - full_v6

- Branch: `codex/sage-standalone-agent`
- Commit: `33d73692ec4c4f6c60b4cb6aa87d2350017e90e9` plus local changes
- Implementation: native ToolSandbox self-evolving Praxis
- Runner: `scripts/run_sage_protocol.py`
- Policy: `--sage-policy self-evolving-praxis`
- Mode: `online_build_full`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Manifest SHA-256: `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`
- Sample: `1032` scenarios
- Models: actor `gpt-4o-mini`; user `gpt-4o-mini`; generation `gpt-4o-mini`
- Cache policy: SAGE task cache off; OpenAI response cache disabled; control
  cache `use-if-eligible`
- Control source: mixed, `689` cached controls and `343` fresh controls
- Dashboard: `http://127.0.0.1:62624/outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256/dashboard/task_compare.html`
- Run path: `outputs/toolsandbox_recovery_ladder_20260530/full_v6/online_build_full_20260530_140256`
- Registry path: `artifacts/toolsandbox_recovery_ladder_20260530/full_registry_v6`
- Final registry digest: `2e56e2acacaba7c1b631b63cab038e4098e5a23fe294bfc869f9c4a5c7395e35`

Command shape:

```bash
PYTHONPATH=src:. SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json \
python scripts/run_sage_protocol.py \
  --mode online_build_full \
  --manifest docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json \
  --registry-dir artifacts/toolsandbox_recovery_ladder_20260530/full_registry_v6 \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --control-cache-root artifacts/baselines/control_task_baselines \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/toolsandbox_recovery_ladder_20260530/full_v6 \
  --artifact-root artifacts/toolsandbox_recovery_ladder_20260530/full_v6_artifacts
```

## Final Metrics

| Metric | Control | SAGE | Delta | Relative Lift |
| --- | ---: | ---: | ---: | ---: |
| Canonical/reference score | `0.693253` | `0.829701` | `+0.136448` | `+19.68%` |
| Outcome/task completion | `0.506399` | `0.788966` | `+0.282568` | `+55.80%` |
| Exact successes | `148` | `498` | `+350` | n/a |

Additional paired counts:

- Canonical gains/regressions/preserved: `626 / 166 / 240`
- Outcome gains/regressions/preserved: `508 / 93 / 199`
- Runtime exceptions: `0`
- Candidate stopped early: `false`
- Protocol gate: `PASS`
- Route mismatch qualified: `false`
- LLM usage: control `3,132` calls and `4,373,204` tokens; SAGE `6,852`
  calls and `10,150,002` tokens
- LLM cache accounting: `0` cached OpenAI calls recorded

## Tool Contribution And Safety

The run did exercise the self-evolving SAGE lifecycle. It accepted `17`
live-born helpers from an empty starting registry, made `556` generated-tool
calls in scenario contexts, and recorded `0` generated-tool runtime failures.
The dashboard contribution panel reports `459` generated-tool outcome-gain rows
and `52` generated-tool outcome-regression rows.

Top called helpers in the full run:

| Helper | Visible | Called | Called-Subset Outcome Delta | Outcome Gains | Outcome Regressions | Side-Effect Incidents |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `plan_device_state_action_sequence_v3` | `216` | `197` | `+0.101820` | `118` | `26` | `0` |
| `resolve_search_window_or_bounds` | `165` | `146` | `+0.511957` | `123` | `8` | `0` |
| `prepare_safe_action_or_abstain` | `223` | `65` | `-0.009626` | `7` | `9` | `0` |
| `select_message_content_by_recency` | `87` | `49` | `+0.625326` | `41` | `1` | `0` |
| `plan_contact_lookup_query` | `56` | `33` | `+0.524176` | `29` | `1` | `0` |
| `prepare_reminder_creation_args` | `100` | `28` | `+0.683325` | `21` | `1` | `2` |

Safety caveat: `side_effect_preservation_report.jsonl` contains two
preservation rows for `prepare_reminder_creation_args`, both on
`add_reminder_content_and_week_delta_and_time_multiple_user_turn_alt` variants.
There were no runtime exceptions, but these two rows require repair or
adjudication before promotion as final clean safety evidence.

## Formal500 V6 Comparison

The relevant successful 500-sample comparator is:

`outputs/toolsandbox_recovery_ladder_20260530/formal500_v6/online_build_500_20260530_125448`

| Run | Sample | Control Source | Score Delta | Score Lift | Outcome Delta | Outcome Lift | Exact Delta |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| formal500 v6 | `500` | `500` cached / `0` fresh | `+0.197257` | `+30.04%` | `+0.379470` | `+76.70%` | `+278` |
| full v6 | `1032` | `689` cached / `343` fresh | `+0.136448` | `+19.68%` | `+0.282568` | `+55.80%` | `+350` |

The full run therefore preserved substantial lift but lost about `10.35`
relative score-lift points and `20.90` relative outcome-lift points versus
formal500 v6.

## Why Formal500 V6 Was Successful

Formal500 v6 was successful because high-yield, generated-helper-friendly task
families carried a large share of the 500-sample manifest, and the generated
helpers were naturally called in those families.

Top formal500 score-lift drivers by family:

| Family | n | Score Delta/Task | Total Score Contribution | Outcome Delta/Task |
| --- | ---: | ---: | ---: | ---: |
| `search_reminder` | `96` | `+0.216` | `+20.74` | `+0.473` |
| `add_reminder` | `56` | `+0.341` | `+19.07` | `+0.571` |
| `search_message` | `24` | `+0.468` | `+11.23` | `+0.699` |
| `remove_reminder` | `19` | `+0.513` | `+9.75` | `+0.801` |
| `update_contact` | `27` | `+0.279` | `+7.52` | `+0.384` |
| `modify_contact` | `23` | `+0.311` | `+7.15` | `+0.829` |

The strongest formal500 helper calls match those families: in formal500 v6,
`resolve_search_window_or_bounds` was called `85` times with called-subset
outcome delta `+0.591680`, and `select_message_content_by_recency` was called
`21` times with called-subset outcome delta `+0.740847`.

## Why Lift Dropped On The Full Run - Reassessment

The drop is not explained by missing lifecycle settings or the wrong model. The
run manifest records self-evolving Praxis, generation on, SAGE cache off,
OpenAI response cache disabled, and `gpt-4o-mini` for actor, user, and
generation calls.

The revised assessment does not treat ceiling compression as a primary cause.
The full-run control means were low enough for substantial improvement:
canonical/reference `0.693253` and outcome/task completion `0.506399`. To reach
`29%` score lift on this full run, SAGE needed a candidate score of about
`0.894297`; the actual candidate score was `0.829701`. That is a shortfall of
about `0.064595` mean score, or `66.66` total score-points across `1032`
scenarios.

The actual causes are missing uplift in large task families, failed helper
birth/validation for useful candidates, low natural adoption of visible
helpers, and family-specific regressions.

First, some formal500 high-lift families were present in the full run but
underperformed their formal500 per-task deltas:

| Family | formal500 Score Delta | full Score Delta | formal500 Outcome Delta | full Outcome Delta |
| --- | ---: | ---: | ---: | ---: |
| `add_reminder` | `+0.341` | `+0.229` | `+0.571` | `+0.367` |
| `search_message` | `+0.468` | `+0.273` | `+0.699` | `+0.505` |
| `modify_contact` | `+0.311` | `+0.154` | `+0.829` | `+0.524` |
| `send_message` | `+0.011` | `-0.044` | `+0.100` | `+0.039` |
| `find_days` | `-0.044` | `-0.087` | `+0.271` | `+0.210` |

On the full sample size, those per-task shortfalls account for approximately
`41.83` score-points of the gap: `add_reminder` `+15.19`,
`search_message` `+12.47`, `modify_contact` `+7.54`, `send_message` `+3.04`,
and `find_days` `+2.76`.

Second, several full-only or expanded families did not get working,
task-specific helpers:

| Family | n | Control -> SAGE Score | Helper Evidence | Assessment |
| --- | ---: | ---: | --- | --- |
| `convert_currency` | `16` | `0.000 -> 0.000` | `extract_service_answer_field` visible `14`, called `0` | helper adoption/routing failure |
| `find_temperature` | `96` | `0.772 -> 0.785` | mostly `plan_device_state_action_sequence_v3`; no specific weather-answer helper | missing value-extraction/final-answer lane |
| `find_phone_number` | `8` | `0.886 -> 0.613` | no generated helper visible | no helper birth/routing for phone extraction |
| `find_current_location` | `16` | `0.625 -> 0.562` | `prepare_safe_action_or_abstain` visible `16`, called `0` | abstention helper not naturally adopted |

These are not ceiling cases. They are under-served lanes where the baseline was
either poor or only partially successful and SAGE failed to add enough new
capability.

Third, useful helper candidates were rejected or accepted but not adopted:

- `plan_send_message_contact_lookup` was rejected twice in `send_message`
  scenarios. The operational fields matched, but validation failed because
  advisory strings such as `next_step` and `final_answer_recommendation` were
  blank instead of exact expected text. This blocked a likely high-value
  send-message helper.
- `extract_service_answer_field` was accepted on `convert_currency`, but it was
  never called. That made the currency lane `0.000 -> 0.000`.
- `prepare_reminder_creation_args` was visible `100` times but called only `28`
  times. The worst add-reminder multi-turn alt family had the helper visible
  and not called across all variants.
- `prepare_safe_action_or_abstain` was visible `223` times and called only `65`
  times; its called-subset outcome delta was slightly negative
  (`-0.009626`). It did not solve the insufficient-information families where
  it was most needed.
- `extract_stock_symbol` was rejected twice for
  `insufficient_applicable_task_families`. This was smaller than the currency
  and weather failures, but it shows the same validation strictness pattern.

Fourth, several families were net score blockers in the full run:

| Family | n | Control -> SAGE Score | Total Score Contribution | Outcome Delta/Task | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `find_days` | `64` | `0.699 -> 0.612` | `-5.55` | `+0.210` | outcome improved, canonical score degraded |
| `send_message` | `56` | `0.886 -> 0.843` | `-2.45` | `+0.039` | contact-lookup helper rejected; cellular-off variants weak |
| `find_phone_number` | `8` | `0.886 -> 0.613` | `-2.18` | `+0.000` | direct score regression |
| `find_current_location` | `16` | `0.625 -> 0.562` | `-1.00` | n/a | insufficient-information variants |

Worst semantic blockers include
`add_reminder_content_and_date_and_time_multiple_user_turn_alt`, which dropped
from outcome `0.849 -> 0.143` across its grouped variants, and
`add_reminder_content_and_week_delta_and_time_and_location_multiple_user_turn_alt`,
which dropped from outcome `0.304 -> 0.000`. The contact/message
insufficient-information variants also created score losses, especially
`modify_contact_with_message_recency_insufficient_information_alt` and
`send_message_with_contact_content_cellular_off_insufficient_information_alt`.

Fifth, `days_between_timestamps` likely improved task completion while hurting
canonical/reference score. The `find_days` family improved outcome
`0.724 -> 0.934` but degraded canonical/reference score `0.699 -> 0.612`.
That pattern suggests the helper helped the user-facing answer while replacing
or changing expected utility-call/final-format behavior used by the canonical
reference scorer. A repair should preserve expected ToolSandbox utility calls
or final-answer formatting while keeping the outcome gain.

Sixth, the formal500 manifest is not simply the first 500 tasks of the full
manifest. A manifest-position audit shows the 500 formal scenarios span full
positions `0` through `1031`, with median full position `723.5`. Several
high-yield formal500 opportunities are much later in the standard full order:
`modify_contact_with_message_recency` moves from formal position `5` to full
position `504`; `search_message_with_recency_latest` from `6` to `688`;
`search_message_with_recency_oldest` from `7` to `720`; and
`update_contact_relationship_with_relationship` from `11` to `984`.
This does not mean "order alone" caused the drop. It means the standard full
order changes helper birth timing and how much later reuse runway remains. The
more important issue is that the early full-order families did not generate or
adopt their own useful helpers.

## Assessment Of Suspected Causes

- Wrong SAGE version or disabled lifecycle: not supported. The full v6 manifest
  records native self-evolving Praxis, generation enabled, empty starting
  registry, and all models as `gpt-4o-mini`.
- Cache as the main explanation: not supported for this full-v6 comparison. The
  earlier uncached diagnostic showed stronger fresh controls, but this full run
  restarted with cached controls where eligible and still finished below
  formal500 v6. Cache policy remains an evidence caveat because the control arm
  is mixed, not because it explains the whole lift gap.
- Dataset order as the sole explanation: not supported. Order affects helper
  birth and reuse runway, but the stronger factual explanation is order plus
  missing helper coverage/adoption in early full-order families and specific
  blocker families.
- Tool-driven lift disappeared: not supported. The full run still accepted `17`
  helpers, called generated helpers in `556` scenario contexts, and produced
  `459` generated-tool outcome-gain rows against `52` generated-tool
  outcome-regression rows.

## Chapter 3 Implication

Chapter 3 should describe native ToolSandbox self-evolving Praxis as the
current primary SAGE implementation, with formal500 v6/v71 as the strongest
high-lift evidence and full_v6 as full-dataset recovery evidence. The full run
is useful because it shows the lifecycle still scales to the standard full
manifest and meets the minimum full-run lift gate, but it also identifies the
families that must be repaired before claiming formal500-level lift on the full
dataset:

- repair `prepare_reminder_creation_args` so no-location reminders do not
  produce `optional_location_lookup_pending_do_not_call_add_reminder`, and
  improve natural adoption on multi-turn add-reminder variants;
- relax or repair validation for `plan_send_message_contact_lookup`, where
  exact advisory text mismatches rejected otherwise useful operational output;
- split or strengthen `extract_service_answer_field` into callable
  currency/weather/phone/address extraction helpers and route them after service
  lookups;
- repair `find_days` so it preserves canonical utility-call/final-format
  behavior while retaining the outcome gain;
- make `prepare_safe_action_or_abstain` final-answer-ready and more naturally
  callable in insufficient-information tasks, or park it where it creates
  regressions;
- add current-location and phone-number abstention/extraction safeguards;
- adjudicate the two `prepare_reminder_creation_args` side-effect preservation
  rows before clean safety promotion.

The full_v6 run passes the requested minimum full-run lift threshold, but the
claim-safe next step is a targeted repair pass on the blocker families followed
by 60/250/500/full reproduction using the same manifest and model controls.
