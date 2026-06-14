# tau3 Last-Attempt SAGE Framework Recommendation - 2026-05-27

This note records the data-based recommendation for the final tau3 portability
attempt. It is experimental engineering guidance, not protected claim evidence.

## Summary

The remaining tau3 blocker is not basic SAGE portability. tau3 now supports the
core SAGE mechanics: helpers are generated as Python code, validated, stored in
the registry, routed into the official host loop as callable tools, naturally
called, tracked for gains/regressions, and sometimes bridged into official tau3
tool calls.

The blocker is that the generated helpers are too local for long multi-intent
conversations. They prepare one action or one field without maintaining the
whole episode objective. That works in ToolSandbox because many tasks are
shorter and the successful helpers were medium-grain, final-action-ready
deterministic bridges. In tau3, a locally valid next action can still fail the
episode by dropping an earlier goal, applying an action to the wrong reservation,
answering before all subgoals are complete, or continuing after a required
transfer/stop condition.

The final attempt should therefore add a general **episode-level action-state
compiler** and a stricter **causal promotion lifecycle**. Do not make another
round of narrow tau3-specific tools.

## Data Reviewed

| Run | Valid tasks | Baseline | SAGE | Generated-tool gains | Regressions | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `tau3_sageagent_duplicate_guard_first40_20260525` | 40 | 12 | 18 | 6 | 1 | Strongest tau3 signal; real helper gains, but one helper-linked regression. |
| `tau3_sageagent_guarded_retained20_20260527_01` | 18 | 7 | 9 | 3 | 1 | Positive but not clean enough to scale. |
| `tau3_sageagent_fresh20_option_repair_v6_20260527_01` | 15 | 6 | 8 | 1 | 0 | Clean but weaker; many infra artifacts. |
| `tau3_sageagent_contribution_lifecycle_v7_20260527_01` | 16 | 6 | 8 | 1 | 0 | Improved net score, but only one gain attributable to generated helpers. |
| `tau3_sageagent_final_bridge_routing20_v18_20260527_01` | 4 | 3 | 2 | 1 | 2 | Demonstrated real helper-attributed gain, then helper/context regressions. |
| `tau3_sageagent_contribution_suppression20_v19_20260527_01` | 3 | 2 | 1 | 0 | 1 | Stronger suppression reduced some risk but did not recover lift. |
| `tau3_sageagent_single_helper20_v20_20260527_01` | 3 | 2 | 1 | 0 | 1 | One-helper routing did not solve the issue. |

The important pattern is that visibility, callable injection, and direct bridge
mechanics are no longer the primary blockers. The same system can produce
generated-helper gains, but the helper quality and lifecycle are not stable
enough for tau3's longer conversational episodes.

## What Worked in ToolSandbox

The high-lift ToolSandbox runs used:

- medium-grain deterministic helpers, not broad policy prose;
- final-action-ready outputs;
- bounded routing;
- just-in-time birth and same-task retry;
- bridge behavior that preserved the official side-effect tool calls;
- strong safety checks and zero helper runtime failures;
- contribution accounting at task level.

The clean broad500 reproduction reported:

- score `0.656799 -> 0.854188` (`+30.05%`);
- outcome `0.494746 -> 0.880845` (`+78.04%`);
- generation from an empty generated registry;
- `16` accepted generated helpers;
- `297` naturally called generated-tool scenarios;
- runtime exceptions `0`.

Those gains came from helpers that made the actor's next deterministic step
easier and safer, while preserving the task's required action path.

## Why tau3 Is Different

tau3 has longer multi-turn user simulations and more compound tasks. A helper
that is locally correct can still be globally harmful. Examples observed in the
latest runs:

- a reservation-change helper produced a valid `update_reservation_flights`
  call but did not preserve the full multi-intent cancellation/lookup task;
- cancellation helpers prepared concrete `cancel_reservation` calls but the
  task later needed transfer, additional cancellation, or final aggregation;
- record lookup helpers were called frequently but did not convert failures;
- option/payment/action helpers were visible and called but often produced no
  paired gains;
- accepted helpers remained routable after early contribution regressions.

This means the final attempt should not be "more routing" or "more force-call."
It should change the kind of helper SAGE generates when an environment exhibits
long multi-intent trajectories.

## Recommended Final Attempt

### 1. Add an Episode Action-State Compiler Helper Family

Add a new generated helper family, tentatively:

`episode_action_state_compiler`

Inputs should remain environment-neutral:

- task prompt;
- visible transcript;
- recent tool results;
- available host tool schemas;
- visible policy text if the adapter exposes it;
- optional environment profile capability flags.

The helper output should be structured:

- `active_goals: list[dict]`
- `completed_goals: list[dict]`
- `blocked_goals: list[dict]`
- `current_target_record_id: str`
- `required_verifications: list[str]`
- `next_host_tool_name: str`
- `next_host_tool_kwargs: dict`
- `should_call_next_tool: bool`
- `should_transfer: bool`
- `should_stop: bool`
- `final_response_requirements: list[str]`
- `risk_flags: list[str]`
- `abstain_reason: str`

This should be deterministic Python code, not a prompt snippet. It should parse
visible transcript/tool-result facts and compile the next safe host action only
when it can preserve the whole episode objective.

### 2. Use It as a Preflight Gate, Not a Replacement Actor

For long-horizon host benchmarks, run the compiler before risky host actions.
The actor can still decide naturally, but SAGE should:

- expose only the compiler plus at most one subtype helper;
- bridge direct action only when the compiler says the action is complete,
  matches the active goal, and does not conflict with completed/blocked goals;
- block or ask for regeneration when a subtype helper proposes an action that
  conflicts with the compiler state.

This keeps the change general: ToolSandbox, tau3, CyberGym, MiniGrid, BBH, and
future adapters can all expose transcript/tool-result state without hard-coding
tau3 policy.

### 3. Change Accepted Helper Lifecycle

Accepted validation should no longer mean broadly routable. Use lifecycle states:

- `accepted_shadow`: passed static/schema/minefield validation but not exposed
  broadly;
- `active_candidate`: allowed on same-task retry or similar diagnostic tasks;
- `active_retained`: has at least one paired/generated-helper gain and no
  unresolved helper-attributed regression;
- `quarantined`: any early helper-attributed regression before offsetting gains;
- `retired`: repeated no-gain/no-call or unsafe behavior.

For tau3-like environments, default to shadow mode for newly accepted helpers
unless they were born from an immediate same-task failure and are used in that
same task retry.

### 4. Require Causal Promotion

Do not promote a helper because a task succeeded. Promote only when:

- baseline failed and SAGE succeeded;
- the generated helper was called or bridged;
- the helper output directly informed the successful official host action or
  final response;
- no helper-attributed regression is pending.

This protects against the exact issue seen in tau3 v18/v19: helpers can preserve
some tasks or appear useful while still introducing regressions.

### 5. Validate on Known Hard tau3 Buckets First

Targeted diagnostics should use tasks with known failure modes but no hidden
label peeking:

- multi-intent cancellation plus transfer;
- reservation change followed by cancellation;
- option selection from search results;
- record disambiguation across multiple reservations;
- compensation/certificate eligibility with required policy checks;
- final aggregation after intermediate side effects.

Success threshold before scaling:

- 20-task tau3 slice;
- valid SAGE success >= baseline +2;
- generated-helper-attributed gains >= 2;
- helper-attributed regressions = 0;
- runtime exceptions = 0;
- infra exclusions reported separately;
- all SAGE tasks live with `gpt-4o-mini`;
- baseline cache used where eligible.

Only then run 40/60.

## Why This Is the Best Final Attempt

The data rules out the simpler fixes:

- Helper visibility is not the main issue; helpers were visible and called
  hundreds of times.
- Direct host-tool bridging is not the main issue; it can fire, but local
  action specs can still harm the episode.
- Single-helper routing is not enough; it reduced helper use but did not recover
  lift.
- Broad policy/planning helpers are not enough; they do not create the
  ToolSandbox-style deterministic lift.

The remaining missing capability is a general way for SAGE to compile visible
episode state into safe next actions while preserving all outstanding goals.
That is a small conceptual extension of the ToolSandbox-success pattern:
move from "prepare the next deterministic action" to "prepare the next
deterministic action in the context of the whole episode state."

## Decision

Recommended final implementation:

`IMPLEMENT_EPISODE_ACTION_STATE_COMPILER_PLUS_CAUSAL_PROMOTION`

Do not run a larger tau3 validation until this is implemented.
