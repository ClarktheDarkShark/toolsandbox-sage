# SAGE Import Agent Remaining Dataset Validation

Status: development-stage portability evidence, not protected final-claim evidence.
Date: 2026-05-24.
Branch: `codex/sage-standalone-agent`.

## Purpose

This pass rechecked the remaining harness-backed datasets after replacing the
stale tau3 and ScienceAgentBench blockers with concrete runner/preflight paths.
The goal was to run real validation where the official harness and artifacts
were available, and to turn any remaining obstacle into a precise,
research-integrity-preserving setup requirement.

## Results

| Dataset | Run | Baseline | SAGE | Status | Interpretation |
|---|---|---:|---:|---|---|
| tau3-bench airline | `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524` | `16/40` | `12/40` | complete official40 | The tau3-current-release path works through the current tau-bench simulator/scorer. The result is negative for SAGE on this policy-heavy airline window: gains `1`, regressions `5`, both-win `11`, both-fail `23`. |
| Terminal-Bench fast official subset | `outputs/sage_official_live/import_agent_terminal_bench_tmp_fast4_20260524` | `1/4` | `1/4` | complete repaired smoke | Moving the Terminal-Bench checkout to `/tmp/sage_benchmarks/terminal-bench` avoids the iCloud file-copy/tar errors seen in the prior run. The small official subset completed with gains `1`, regressions `1`; a full 40 remains too slow for the current unattended budget. |
| ScienceAgentBench | `outputs/sage_official_live/import_agent_scienceagentbench_verified_artifact_preflight_20260523` | n/a | n/a | artifact gate | Verified Hugging Face inputs load. Official scoring still requires local `benchmark_verified.zip` artifacts: `datasets`, `eval_programs`, `gold_programs`, `scoring_rubrics`. |
| science-agent-bench alias | `outputs/sage_official_live/import_agent_science_agent_bench_verified_artifact_preflight_20260524` | n/a | n/a | artifact gate | Alias path behaves the same as `scienceagentbench`; selected verified input IDs `1-4` loaded, but official scoring remains gated on local protected artifacts. |

## What Was Fixed

- Tau3 is no longer blocked as a missing separate repo. The runner now treats it
  as `tau3-current-release` through the current `external/tau2-bench` checkout,
  with separate `tau3:*` task IDs and cache keys so tau2 and tau3 evidence do
  not mix.
- ScienceAgentBench is no longer a vague missing-harness blocker. The runner
  proves that verified task inputs load and reports the exact missing official
  scoring artifact directories.
- Terminal-Bench's local filesystem issue was isolated. The previous iCloud
  checkout produced file-operation timeouts and tar-copy errors. A fresh
  non-iCloud clone under `/tmp/sage_benchmarks/terminal-bench` allowed the
  official harness to complete a subset run.

## Remaining Gaps

- tau3/tau2 policy simulators need stronger environment-neutral policy/action
  helpers. Current import-mode prompt helpers are shallow and can hurt on
  policy-heavy tasks.
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
