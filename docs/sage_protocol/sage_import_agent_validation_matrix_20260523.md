# SAGE Import-Agent Validation Matrix

Status: development-stage portability evidence, not protected final-claim evidence.
Date: 2026-05-23, updated 2026-05-24.
Branch: `codex/sage-standalone-agent`.

## Purpose

This checkpoint tests whether SAGE can be imported into an existing benchmark
harness instead of forcing every benchmark to become a full `EnvironmentAdapter`.
The new `SAGEImportAgent` layer exposes:

- `before_task(...)`: select retained helpers and render harness-consumable
  prompt/tool/code guidance.
- `before_step(...)`: refresh retained-helper guidance from the visible
  transcript inside host loops that can rebuild prompts during a task.
- `review_action(...)`: optionally review proposed host tool calls before
  execution, blocking only when accepted helpers recommend abstention,
  transfer, escalation, or missing-precondition handling from visible context.
- `after_task(...)`: observe the official scorer result, generate bounded
  reusable helpers from visible failure evidence, update registry use/success
  accounting, and optionally recommend same-task retry when the host allows it.
- first-class helper types for deterministic callables, prompt guidance,
  action-planning helpers, and scorer-feedback repair helpers.

The import layer is intended for benchmarks such as tau2 and Terminal-Bench
where the benchmark already owns the runner, simulator, scorer, and agent loop.

## Current Live/Official Matrix

| Dataset | Status | Baseline | SAGE | Cache / run note | Dashboard / artifact |
|---|---:|---:|---:|---|---|
| ToolSandbox protocol40 | complete | score `0.648`, outcome `0.474`, exact `3/40` | score `0.870`, outcome `0.914`, exact `23/40` | `40 cached / 0 fresh` controls, fresh SAGE, runtime exceptions `0` | `outputs/sage_agent_standalone/import_agent_verify_toolsandbox40_20260523/mechanism_40_20260523_194131/dashboard/task_compare.html` |
| CyberGym live fixed-side40 | complete | `1/40` | `12/40` | real task generator, real submit server, real PoC verifier, fixed-side check enabled, `40 cached / 0 fresh` controls | `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523/dashboard/task_compare.html` |
| MiniGrid live40 | complete | `18/40` | `40/40` | cached LLM baseline controls, fresh SAGE, one reusable grid planner | `outputs/sage_agent_standalone/import_agent_openai_verify_minigrid40_20260523/dashboard/task_compare.html` |
| BBH live40 | complete | `16/40` | `40/40` | cached LLM baseline controls, fresh SAGE, one exact-answer helper; hidden targets remain inside scorer | `outputs/sage_agent_standalone/import_agent_openai_verify_bbh40_20260523/dashboard/task_compare.html` |
| tau2-bench airline official40, pre-repair | complete negative diagnosis | `9/40` | `8/40` | `25 cached / 15 fresh` controls; SAGE generated a bad generic JSON-error guidance helper from a runner failure | `outputs/sage_official_live/import_agent_tau2_airline_official_live40_gpt4omini_20260523/dashboard/task_compare.html` |
| tau2-bench airline official40, post-repair | complete narrow positive | `9/40` | `10/40` | `40 cached / 0 fresh` controls; infrastructure/runner failures no longer trigger helper birth | `outputs/sage_official_live/import_agent_tau2_airline_skip_infra_helper_live40_20260523/dashboard/task_compare.html` |
| Terminal-Bench official40 | blocked by runtime feasibility | partial `1/4` baseline, `1/3` SAGE | partial only | official Docker harness was started, but reached only 3 paired tasks after about 24 minutes; no valid 40-task baseline cache existed | `outputs/sage_official_live/import_agent_terminal_bench_official_live40_20260523/dashboard/task_compare.html` |
| Terminal-Bench concrete-repair subset | complete positive official subset | `0/2` | `2/2` | official task parser/Docker path on the repaired `/tmp/sage_benchmarks/terminal-bench` checkout; gains `2`, regressions `0`; demonstrates import-mode value on a new environment | `outputs/sage_official_live/import_agent_terminal_bench_concrete_repair_2_20260524/dashboard/task_compare.html` |
| Terminal-Bench repaired fast4 | complete neutral ablation | `1/4` | `1/4` | fresh non-iCloud checkout at `/tmp/sage_benchmarks/terminal-bench` avoided prior iCloud file-copy/tar failures; gains `1`, regressions `1` | `outputs/sage_official_live/import_agent_terminal_bench_tmp_fast4_20260524/dashboard/task_compare.html` |
| tau3-bench airline smoke1 | complete harness smoke | `1/1` | `1/1` | current `tau2-bench` checkout contains the tau3 release/task-fix layer; run is labeled `tau3-current-release` with `tau3:*` task IDs and separate baseline-cache keys | `outputs/sage_official_live/import_agent_tau3_airline_smoke1_20260523/dashboard/task_compare.html` |
| tau3-bench airline official40, static prompt-helper policy | complete negative ablation | `16/40` | `12/40` | full official tau3-current-release airline run; gains `1`, regressions `5`, both-win `11`, both-fail `23`; static prompt helpers are not enough for this policy-heavy window | `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524/dashboard/task_compare.html` |
| tau3-bench airline official40, full import lifecycle | complete positive | `16/40` | `18/40` | `40 cached / 0 fresh` controls, fresh SAGE; gains `4`, regressions `2`, both-win `14`, both-fail `20`; in-task helper refresh and action review repair the prior regression pattern | `outputs/sage_official_live/import_agent_tau3_airline_full_import_action_review_official40_sys_20260524/dashboard/task_compare.html` |
| ScienceAgentBench / science-agent-bench preflight | artifact-access gate, not vague missing-harness blocker | n/a | n/a | verified Hugging Face split loaded selected IDs `1-4`; official scoring still requires local `datasets`, `eval_programs`, `gold_programs`, and `scoring_rubrics` from `benchmark_verified.zip`; public SharePoint download attempt returned an authenticated sign-in page | `outputs/sage_official_live/import_agent_scienceagentbench_verified_artifact_preflight_20260523/dashboard/task_compare.html` |

## tau2 Failure And Repair

The first official tau2 import run exposed a real portability failure. SAGE did
not fail because the import boundary was unavailable; it failed because the
initial import-mode helper lifecycle treated an infrastructure parser error as
reusable task evidence. The generated helper told later tasks to avoid malformed
JSON, which was irrelevant to the airline policy tasks and could interfere with
baseline behavior.

Repair implemented:

- `SAGEImportAgent.after_task(...)` now classifies runner, parser, subprocess,
  Docker, authentication, and timeout failures as diagnostic artifacts.
- These failures emit `tool_birth_skipped` instead of creating reusable helpers.
- Reusable helper generation is reserved for visible task-outcome failures with
  enough task evidence to teach future behavior.

Post-repair result:

- Pre-repair tau2 official40: baseline `9/40`, SAGE `8/40`; paired counts:
  gains `5`, regressions `6`, both-win `3`, both-fail `26`; SAGE errors
  included one `tau2_runner_error:JSONDecodeError`.
- Post-repair tau2 official40: baseline `9/40`, SAGE `10/40`; paired counts:
  gains `5`, regressions `4`, both-win `5`, both-fail `26`; all SAGE failures
  were official `tau2_reward_below_1`, not runner JSON errors.

Machine-readable repair artifact:

- `artifacts/sage_official_live/tau2_import_agent_repair_artifacts_20260523.json`

## Interpretation

The import boundary is now demonstrated on real host-owned harnesses, but the
result is mixed:

- Strong positive portability evidence: ToolSandbox, CyberGym, MiniGrid, BBH.
- Narrow positive official-host evidence: tau2 after the infrastructure-failure
  helper-birth guard.
- Tau3 is no longer classified as missing-harness in this checkout. It runs
  through the current tau-bench release in `external/tau2-bench`, with separate
  `tau3` labels so it is not conflated with tau2 evidence. The first full
  airline40 result is retained as a negative static-prompt-helper ablation, but
  the full import lifecycle repair is positive on the same 40-task window.
- ScienceAgentBench verified inputs are reachable, but official outcome scoring
  remains gated by the authors' non-redistributable artifact zip. The new
  preflight and `scripts/prepare_scienceagentbench_artifacts.py` make the gate
  exact and reproducible instead of treating the repository clone as unusable.
- Remaining limitation: policy-heavy simulators still need richer,
  environment-neutral state/action-policy helper families. The repaired tau3
  result is positive, but not saturated; gains and regressions should drive the
  next generation of reusable confirmation, refund, compensation, unsupported
  request, and transfer/escalation helpers.
- Terminal-Bench requires a different execution strategy before 40-task runs are
  practical: valid baseline cache creation, longer unattended run budgeting, and
  task-family sampling that is documented up front.

## Decision

`FULL_IMPORT_AGENT_BOUNDARY_READY_FOR_NEXT_PORTABILITY_ITERATION`: keep the
import-agent boundary, keep the infrastructure-failure birth guard, keep the
in-task refresh/action-review hooks, and next improve helper quality for
harness-owned policy/action environments rather than adding benchmark-specific
adapters first.
