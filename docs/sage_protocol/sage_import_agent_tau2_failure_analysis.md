# SAGE Import Agent Tau2 Failure Analysis
Status: experimental portability diagnosis, not protected claim evidence.
Run: `outputs/sage_official_live/import_agent_tau2_airline_official_live40_gpt4omini_20260523`

Post-repair rerun: `outputs/sage_official_live/import_agent_tau2_airline_skip_infra_helper_live40_20260523`.

Machine-readable repair artifact: `artifacts/sage_official_live/tau2_import_agent_repair_artifacts_20260523.json`.

## Post-Repair Update

The first tau2 import run exposed a concrete SAGE lifecycle bug: the import layer
accepted a reusable prompt-guidance helper from a runner-side
`JSONDecodeError`. That helper was about avoiding malformed JSON, not about the
airline task policy, so it could pollute later tasks.

The import layer now classifies runner/parser/subprocess/Docker/authentication
and timeout failures as diagnostic artifacts, not helper-birth evidence. The
full official tau2 airline 40-task rerun used cached baseline controls
(`40 cached / 0 fresh`) and fresh SAGE. Result: baseline `9/40`, SAGE `10/40`,
with paired counts `5` gains, `4` regressions, `5` both-win, and `26`
both-fail. This is a narrow positive import-mode result, but not a strong tau2
claim. The remaining limitation is helper quality: prompt-guidance helpers are
not yet rich enough to serve as reliable domain-state/action-policy helpers for
policy-heavy simulators.

## Summary
- Official harness: tau2 airline simulator/scorer.
- Model: gpt-4o-mini.
- Baseline: 9/40 success; controls cached/fresh: {'policy': 'use-if-eligible', 'path': 'artifacts/sage_official_live/baseline_cache.json', 'cached': 25, 'fresh': 15, 'scope': 'official_baseline_control_only'}.
- SAGE: 8/40 success; tools born: 10; helper visibility events: 77.
- Paired counts: {'regression': 6, 'gain': 5, 'both_fail': 26, 'both_win': 3}.

## What This Shows
The import boundary works mechanically on a harness-owned benchmark: SAGE can inject first-class prompt-guidance helpers into the host agent loop, observe official scorer output, generate new helpers after failed tasks, and reuse them later. However, the generated helpers are too shallow for tau2. They are prompt snippets, not executable domain-policy tools, and they can regress early tasks by nudging the actor away from the baseline policy.

## Helper Visibility And Success
- `sage_tool_argument_guidance_4`: visible 21 times; SAGE succeeded 5 of those visible tasks.
- `sage_tool_argument_guidance_5`: visible 9 times; SAGE succeeded 2 of those visible tasks.
- `sage_tool_argument_guidance_6`: visible 9 times; SAGE succeeded 2 of those visible tasks.
- `sage_tool_argument_guidance_7`: visible 7 times; SAGE succeeded 2 of those visible tasks.
- `sage_task_completion_guidance_1`: visible 6 times; SAGE succeeded 1 of those visible tasks.
- `sage_tool_argument_guidance_1`: visible 6 times; SAGE succeeded 1 of those visible tasks.
- `sage_tool_argument_guidance_2`: visible 6 times; SAGE succeeded 0 of those visible tasks.
- `sage_tool_argument_guidance_3`: visible 6 times; SAGE succeeded 1 of those visible tasks.
- `sage_tool_argument_guidance_8`: visible 6 times; SAGE succeeded 2 of those visible tasks.
- `sage_missing_information_guidance_1`: visible 1 times; SAGE succeeded 0 of those visible tasks.

## Gains
- `tau2:airline:3` with helpers ['sage_task_completion_guidance_1', 'sage_tool_argument_guidance_1'].
- `tau2:airline:13` with helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_3'].
- `tau2:airline:15` with helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5'].
- `tau2:airline:18` with helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5'].
- `tau2:airline:36` with helpers ['sage_tool_argument_guidance_8', 'sage_tool_argument_guidance_7'].

## Regressions
- `tau2:airline:0` baseline succeeded but SAGE failed; helpers []; SAGE error `tau2_runner_error:JSONDecodeError`.
- `tau2:airline:1` baseline succeeded but SAGE failed; helpers ['sage_task_completion_guidance_1']; SAGE error `tau2_reward_below_1`.
- `tau2:airline:2` baseline succeeded but SAGE failed; helpers ['sage_task_completion_guidance_1', 'sage_missing_information_guidance_1']; SAGE error `tau2_reward_below_1`.
- `tau2:airline:4` baseline succeeded but SAGE failed; helpers ['sage_tool_argument_guidance_1', 'sage_task_completion_guidance_1']; SAGE error `tau2_reward_below_1`.
- `tau2:airline:5` baseline succeeded but SAGE failed; helpers ['sage_task_completion_guidance_1', 'sage_tool_argument_guidance_1']; SAGE error `tau2_reward_below_1`.
- `tau2:airline:6` baseline succeeded but SAGE failed; helpers ['sage_task_completion_guidance_1', 'sage_tool_argument_guidance_1']; SAGE error `tau2_reward_below_1`.

## Both Failed
- `tau2:airline:7` helpers ['sage_tool_argument_guidance_1', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:8` helpers ['sage_tool_argument_guidance_1', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:9` helpers ['sage_tool_argument_guidance_3', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:10` helpers ['sage_tool_argument_guidance_3', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:11` helpers ['sage_tool_argument_guidance_3', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:12` helpers ['sage_tool_argument_guidance_3', 'sage_tool_argument_guidance_2']; error `tau2_reward_below_1`.
- `tau2:airline:14` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_3']; error `tau2_reward_below_1`.
- `tau2:airline:16` helpers ['sage_tool_argument_guidance_5', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:17` helpers ['sage_tool_argument_guidance_5', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:19` helpers ['sage_tool_argument_guidance_5', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:20` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5']; error `tau2_reward_below_1`.
- `tau2:airline:21` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5']; error `tau2_reward_below_1`.
- `tau2:airline:22` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5']; error `tau2_reward_below_1`.
- `tau2:airline:23` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_5']; error `tau2_reward_below_1`.
- `tau2:airline:24` helpers ['sage_tool_argument_guidance_4', 'sage_tool_argument_guidance_6']; error `tau2_reward_below_1`.
- `tau2:airline:26` helpers ['sage_tool_argument_guidance_6', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:28` helpers ['sage_tool_argument_guidance_6', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:29` helpers ['sage_tool_argument_guidance_6', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:30` helpers ['sage_tool_argument_guidance_6', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- `tau2:airline:31` helpers ['sage_tool_argument_guidance_6', 'sage_tool_argument_guidance_4']; error `tau2_reward_below_1`.
- ... 6 more both-failed tasks in `artifacts/sage_official_live/tau2_failure_artifacts_20260523.json`.

## Root Cause Classification
- Import-agent plumbing: works.
- Dashboard-at-start and dashboard updates: works on shared port 62630.
- Current helper type: prompt guidance only; insufficient for tau2 policy-heavy workflows.
- Main failure mode: generated guidance is broad and policy-shaped but not a domain-specific deterministic planner/checker over reservations, refund eligibility, passenger edits, flight selection, payment allocation, and transfer preconditions.
- Research integrity: no labels or hidden expected actions were used in helper generation; the limitation is capability, not leakage.

## Next General SAGE Improvement
SAGE needs a richer import-mode helper class for harness-owned environments: domain-state/action-policy helpers that can read visible tool outputs and produce explicit next-action checks or argument plans. This should remain environment-agnostic by deriving schemas from visible tool calls and official feedback, then validating helpers on synthetic/minefield cases without expected labels.
