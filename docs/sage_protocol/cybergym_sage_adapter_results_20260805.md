# CyberGym SAGE Adapter Results - 2026-08-05

> Archival record: the CyberGym adapter and runner described here were removed
> from the publication product during the 2026-09-01 R1 cleanup. Paths below
> document the historical experiment and are not current commands.

## Purpose

This note records the first isolated CyberGym implementation pass for SAGE after
the ToolSandbox production implementation was stabilized. The goal was to create
a separate filesystem path for CyberGym rather than mixing CyberGym logic into
the ToolSandbox adapter.

## Implementation Added

CyberGym-specific code now lives under:

- `src/sage_cybergym/`
- `scripts/cybergym/`
- `tests/sage_cybergym/`

The adapter follows the same high-level SAGE lifecycle used in ToolSandbox:

1. load a benchmark task stream;
2. run a non-learning baseline candidate process;
3. detect a reusable gap when the baseline fails;
4. birth a deterministic generated-tool strategy;
5. validate the strategy output shape before use;
6. store accepted strategies in a registry;
7. route accepted strategies into later tasks;
8. score baseline and SAGE on matched tasks;
9. export a static dashboard.

The implementation does not add task-ID-specific candidate logic and does not
use hidden labels. Raw benchmark text, source snippets, candidate bytes, and
verifier output remain in local artifacts and are not surfaced in the dashboard
except through hashes, pass/fail status, exit code, and aggregate metrics.

## Local Execution Boundary

The initial CyberGym package server path had dependency drift in the local base
environment. To avoid that blocker, the adapter uses a direct local Docker
evaluation path for locally available `arvo` tasks. This keeps the verifier
boundary intact while avoiding the FastAPI server as an extra moving part.

The current evaluator supports available `arvo` Docker images. The next
extension should add the same direct wrapper for other CyberGym task families
after the `arvo` path is stable.

## Runs Completed

### Run 1

- Run: `outputs/sage_cybergym/validation4_source_20260805_192336`
- Sample: 4 local `arvo` tasks, offset 0
- Baseline: 0 / 4
- SAGE: 1 / 4
- Absolute lift: +0.250
- Tools born: 4
- Tools accepted: 4
- Tool-used tasks: 4
- Dashboard: `outputs/sage_cybergym/validation4_source_20260805_192336/dashboard/task_compare.html`

### Run 2

- Run: `outputs/sage_cybergym/validation4_offset4_20260805_193123`
- Sample: 4 local `arvo` tasks, offset 4
- Baseline: 1 / 4
- SAGE: 1 / 4
- Absolute lift: +0.000
- Tools born: 3
- Tools accepted: 3
- Tool-used tasks: 3
- Dashboard: `outputs/sage_cybergym/validation4_offset4_20260805_193123/dashboard/task_compare.html`

## Aggregate Across Initial Validation Runs

- Total tasks: 8
- Baseline successes: 1 / 8
- SAGE successes: 2 / 8
- Baseline success rate: 0.125
- SAGE success rate: 0.250
- Absolute lift: +0.125
- Generated-tool-used tasks: 7 / 8
- Tools born across runs: 7

## Larger Diagnostic Run

### Run 3

- Run: `outputs/sage_cybergym/validation20_nohang_20260805_201836`
- Sample: 20 local `arvo` tasks, offset 0
- Baseline: 3 / 20
- SAGE: 5 / 20
- Baseline success rate: 0.150
- SAGE success rate: 0.250
- Absolute lift: +0.100
- Relative lift: +66.67%
- Tools born: 6
- Tools accepted: 6
- Generated-tool-used tasks: 17 / 20
- SAGE-only wins: 2
- Baseline-only wins: 0
- Shared baseline/SAGE wins: 3
- SAGE misses after generated-tool use: 15
- Dashboard: `outputs/sage_cybergym/validation20_nohang_20260805_201836/dashboard/task_compare.html`

The two SAGE-only wins were generated-tool attributed. The accepted
`literal_token_candidates` strategy produced one success on its birth task and
one later reuse success. Baseline successes were preserved by SAGE, so this
sample produced no regressions relative to baseline.

## Interpretation

This is a working CyberGym integration and a positive diagnostic signal, not a
finished benchmark claim. The implementation demonstrates that the SAGE
generated-tool lifecycle can be connected to CyberGym and can produce
tool-attributed improvement on real local verifier executions. The 20-task run
showed a +10 percentage point absolute lift, but most generated-tool-used tasks
still missed. The effect is therefore useful evidence for portability and future
work, but it should not be presented as a strong cross-benchmark claim until the
strategy lifecycle improves and the result holds on larger samples.

## Next Steps

1. Add a more efficient candidate-budget scheduler so each task does not spend
   equally across weak strategies.
2. Promote strategies based on observed verifier success and suppress strategies
   that repeatedly produce clean exits.
3. Add an `oss-fuzz` direct evaluator path.
4. Run 20-task and 40-task CyberGym samples only after the 8-task aggregate
   shows stable lift above the matched baseline.
5. Keep CyberGym results separate from ToolSandbox results in Chapter 4 unless
   the larger CyberGym validation remains positive.
