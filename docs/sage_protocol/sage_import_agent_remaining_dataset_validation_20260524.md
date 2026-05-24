# SAGE Import Agent Remaining Dataset Validation

Status: development-stage portability evidence, not protected final-claim evidence.
Date: 2026-05-24.
Branch: `codex/sage-standalone-agent`.

## Purpose

This pass rechecked the remaining harness-backed datasets after replacing the
stale tau3 and ScienceAgentBench blockers with concrete runner/preflight paths.
It was then updated after `SAGEImportAgent` was expanded from a static
prompt-helper shim into the host-loop import boundary for the full SAGE
lifecycle: retained-helper routing, in-task helper refresh, action review when
the host can intercept side-effecting calls, post-task gap diagnosis, full
generate/validate/repair/retain, registry reuse, lifecycle accounting, and
optional same-task retry.

## Results

| Dataset | Run | Baseline | SAGE | Status | Interpretation |
|---|---|---:|---:|---|---|
| tau3-bench airline | `outputs/sage_official_live/import_agent_tau3_airline_full_import_action_review_official40_sys_20260524` | `16/40` | `18/40` | complete official40 | Full import-agent lifecycle now improves the tau3 airline window that previously regressed under static prompt helpers. Controls were `40 cached / 0 fresh`; SAGE was fresh. Paired result: gains `4`, regressions `2`, both-win `14`, both-fail `20`, integrity issues `0`. |
| tau3-bench airline old prompt-helper policy | `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524` | `16/40` | `12/40` | complete negative ablation | This is retained as the failure mode that motivated the import-agent repair. Static prompt helpers without in-task refresh/action review were harmful on this policy-heavy airline window: gains `1`, regressions `5`. |
| Terminal-Bench concrete-repair subset | `outputs/sage_official_live/import_agent_terminal_bench_concrete_repair_2_20260524` | `0/2` | `2/2` | complete official subset | Moving Terminal-Bench work to `/tmp/sage_benchmarks/terminal-bench` avoids iCloud file-copy/tar errors. The subset uses the official task parser/Docker path and shows import-mode value on a new environment: gains `2`, regressions `0`. A full 40 remains too slow for the current unattended budget. |
| Terminal-Bench old fast subset | `outputs/sage_official_live/import_agent_terminal_bench_tmp_fast4_20260524` | `1/4` | `1/4` | complete neutral ablation | Earlier repaired smoke before concrete execution-feedback helpers; gains `1`, regressions `1`. |
| ScienceAgentBench | `outputs/sage_official_live/import_agent_scienceagentbench_verified_artifact_preflight_20260523` | n/a | n/a | artifact gate | Verified Hugging Face inputs load. Official scoring still requires local `benchmark_verified.zip` artifacts: `datasets`, `eval_programs`, `gold_programs`, `scoring_rubrics`. |
| science-agent-bench alias | `outputs/sage_official_live/import_agent_science_agent_bench_verified_artifact_preflight_20260524` | n/a | n/a | artifact gate | Alias path behaves the same as `scienceagentbench`; selected verified input IDs `1-4` loaded, but official scoring remains gated on local protected artifacts. |

## What Was Fixed

- Tau3 is no longer blocked as a missing separate repo. The runner now treats it
  as `tau3-current-release` through the current `external/tau2-bench` checkout,
  with separate `tau3:*` task IDs and cache keys so tau2 and tau3 evidence do
  not mix.
- The tau3 import path now uses the real SAGE import lifecycle instead of a
  one-shot prompt helper:
  - `before_task(...)` selects retained helpers for the task.
  - `before_step(...)` refreshes helper outputs from the visible conversation
    inside host loops that rebuild prompts before each model turn.
  - `review_action(...)` gives compatible host loops a side-effect/precondition
    guard for proposed write/cancel/payment/compensation calls.
  - `after_task(...)` normalizes official scorer output and runs full
    helper birth, validation, repair, retention, reuse, and retry accounting.
- LiteLLM's import-time remote cost-map fetch is disabled for official live
  harnesses with `LITELLM_LOCAL_MODEL_COST_MAP=True`. This changes only cost
  metadata loading, not model calls, task scoring, or SAGE routing.
- ScienceAgentBench is no longer a vague missing-harness blocker. The runner
  proves that verified task inputs load and reports the exact missing official
  scoring artifact directories.
- Terminal-Bench's local filesystem issue was isolated. The previous iCloud
  checkout produced file-operation timeouts and tar-copy errors. A fresh
  non-iCloud clone under `/tmp/sage_benchmarks/terminal-bench` allowed the
  official harness to complete a subset run.

## Remaining Gaps

- tau3 still needs broader policy-action helper families. The repaired import
  agent is positive on the airline40 window, but the margin is modest and two
  regressions remain. The next work should classify the gain/regression traces
  and add environment-neutral policy helper generation for reservation changes,
  refunds, compensation, unsupported-account disputes, and confirmation gates.
- Terminal-Bench full40 remains a runtime-budget problem. The repaired path is
  viable, but a complete run should use the `/tmp` checkout, a preselected
  published task split, longer wall-clock budget, and a completed baseline
  cache.
- ScienceAgentBench official scoring cannot be ethically bypassed from previews
  alone. The protected benchmark artifact zip must be downloaded through an
  authenticated/working official link, then materialized with:

```bash
python scripts/prepare_scienceagentbench_artifacts.py \
  --artifact-zip /path/to/benchmark_verified.zip
```

After that, the next repair is to wire a true ScienceAgentBench generation and
evaluation loop through the existing `SAGEImportAgent` boundary.

## Machine Summary

- Summary artifact:
  `artifacts/sage_official_live/import_agent_full_lifecycle_repair_summary_20260524.json`
- Summary SHA-256:
  `8e03978fa2516f5a7ae9e891086ae4318d31de0473edc9d788b133b26dc7cbe8`
