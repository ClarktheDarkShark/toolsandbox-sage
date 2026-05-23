# SAGE Standalone Overview and Dataset Notes

Last updated: 2026-05-22

## SAGE high-level overview

SAGE is a self-adaptive agent layer for turning repeated, deterministic task
failures into reusable helper tools. It does not replace an environment,
benchmark, simulator, or grader. Instead, the environment adapter exposes a
sealed task stream, visible task artifacts, allowed actions, execution results,
gap signals, validation cases, helper routing, and private scoring.

The SAGE loop is:

1. Prepare the environment adapter and load an existing local registry.
2. Read a bounded task stream without selecting tasks by hidden answers,
   prior success, cache state, or labels.
3. Route a small set of accepted helper tools from the registry when their
   helper family and triggers match the visible task.
4. Run the task through the adapter and collect normalized success, score,
   outcome score, transcript, helper uses, visible artifacts, and errors.
5. Ask the adapter and generic gap miner whether failure evidence points to a
   reusable deterministic capability gap.
6. Generate a small typed Python helper for that gap.
7. Reject helpers that fail integrity checks, AST/runtime validation,
   schema expectations, side-effect constraints, or held-out validation cases.
8. Store accepted helpers in the local registry with birth metadata,
   validation evidence, code hash, use counts, success counts, and lifecycle
   status.
9. Optionally retry the same task with the newly accepted helper, then continue
   to later tasks where natural reuse can be measured.
10. Export run summaries, event logs, registry snapshots, and a Task Compare
    dashboard.

The current standalone boundary lives in `src/sage_agent/`. Existing adapters
cover ToolSandbox smoke/probe, CyberGym smoke/live submit paths, MiniGrid, and
BIG-Bench Hard. The controller is environment-neutral; benchmark-specific
logic belongs in adapters.

## Scope and limitations

SAGE is in scope when a failure reflects a reusable deterministic subproblem:
normalization, record selection, date/time computation, argument preparation,
visible-artifact parsing, structured input planning, grid/path planning,
candidate portfolio planning, or exact symbolic transformation.

SAGE is out of scope when improvement requires hidden labels, answer keys,
oracle solutions, reference trajectories, benchmark-specific task ID patches,
private scoring data, broad policy prose, arbitrary external research, or
unsafe side effects. The standalone integrity policy fails fast on leak-prone
fields such as `expected_answer`, `ground_truth`, `oracle`, `solution`, and
`answer_key` when those appear in SAGE-facing task metadata or generation
inputs.

Current evidence is strongest for ToolSandbox and small standalone adapter
checks. CyberGym live evidence is useful portability evidence but still limited
by low absolute success and benchmark-readiness constraints. New benchmark
claims require adapter implementation, a locked task protocol, matched
controls, cache policy disclosure, safety review, and dashboard/artifact
preservation.

## Research gaps SAGE targets

Static agent benchmarks usually measure whether a fixed agent succeeds, but do
not test whether the agent can convert repeated failure evidence into a durable
capability that transfers to later tasks.

Tool-calling work often assumes a fixed tool surface. SAGE studies the missing
middle: when the base toolset is fair but incomplete, the agent can create,
validate, retain, and later route small helper tools instead of relying only on
prompting.

Reflection and memory approaches often store natural-language lessons. SAGE
stores executable, typed, validation-backed helpers with explicit routing and
reuse telemetry, which makes the learned artifact auditable.

Program synthesis and code-generation benchmarks often grade one generated
program for one prompt. SAGE narrows generation to reusable side-effect-free
helpers and asks whether those helpers improve future agent task outcomes.

Long-horizon agent benchmarks expose compounding tool, state, and planning
errors, but many do not isolate which deterministic substeps are missing. SAGE
adds explicit gap packets, validation cases, lifecycle decisions, and registry
promotion/parking evidence.

## All SAGE-relevant datasets and benchmarks

| Dataset | Paper timing | Local clone | Minimal chapter 2 note | SAGE fit | Adapter status |
| --- | --- | --- | --- | --- | --- |
| ToolSandbox | 2024 paper; primary mature SAGE evidence base. | Built into this repo under `tool_sandbox/`; no external clone required. | Stateful, conversational, interactive tool-use benchmark with phone-like tools, user simulation, stateful databases, tool perturbations, and canonical milestone scoring. Local registry exposes `129` base scenarios and `1032` augmented scenarios. | Core evidence source for self-evolving helper birth, validation, registry retention, routing, reuse, matched controls, and outcome lift. | Runnable through the original protocol runner and standalone smoke/probe adapters: `toolsandbox` and `toolsandbox-probe`. |
| CyberGym | 2025/2026-era cybersecurity benchmark work used here as a portability stress test. | `external/cybergym` at commit `3ae9067`; local live task manifest `cybergym_data/tasks.json` has `1507` tasks. | Vulnerability-analysis and PoC-submission environment where agents inspect visible task artifacts, generate candidate inputs, and submit to a verifier. The lightweight smoke adapter exposes the published `10` subset IDs without full task downloads. | Good test for visible-artifact mining, execution-feedback mutation, candidate portfolio planning, safe retries, lifecycle parking/refinement, and verifier-backed task outcomes. | Runnable as `cybergym` smoke and through the separate live batched CyberGym runner; live benchmark claims still require controlled task selection and verifier policy. |
| MiniGrid | Earlier benchmark/environment; used as a third-domain standalone portability check. | `external/minigrid` at commit `90928729`. | Official grid-world navigation environments with reset/step APIs, visible grid state, agent pose, goal position, and discrete actions. Default adapter stream has `15` tasks from `3` environments times `5` seeds. | Tests whether SAGE can birth a reusable deterministic planner outside ToolSandbox and CyberGym. | Runnable as standalone `minigrid`. |
| BIG-Bench Hard | 2022 benchmark; used here as a symbolic exact-answer standalone check. | `external/BIG-Bench-Hard` at commit `9ee07bd`; repo has `27` BBH JSON task files. | Public exact-answer reasoning benchmark. The SAGE adapter defaults to four symbolic families: boolean expressions, multistep arithmetic, Dyck languages, and word sorting, yielding `1000` local tasks in the default adapter stream. | Tests reusable symbolic prompt-to-answer helpers while keeping targets private inside adapter scoring. | Runnable as standalone `bbh`. |
| `tau2-bench` / `tau3-bench` | Core `tau^2` paper submitted 2025; repo now also includes 2026 knowledge and voice extensions. | `external/tau2-bench` at commit `5a8fce3` | Conversational customer-service agent benchmark with domain policies, tools, user simulation, and verifiable task outcomes. Local task counts: airline `50`, retail `114`, telecom `2285` plus `20` small telecom tasks, banking knowledge `97`. | Good test for policy-aware tool use, state updates, user-agent coordination, and helper reuse around action validation, policy constraints, and structured task planning. | Runnable as `tau2-bench` or `tau3-bench` through a public-metadata probe adapter. Full benchmark scoring still needs a dedicated tau execution adapter. |
| `terminal-bench` | ICLR 2026 paper; arXiv submitted 2026-01-17. | `external/terminal-bench` at commit `1a6ffa9` | Terminal-agent benchmark with task instructions, sandboxed terminal environments, human-written solutions, and verification tests. Paper reports Terminal-Bench 2.0 has `89` hard tasks; local core registry `0.1.1` lists `80` tasks, and the cloned head includes `241` `original-tasks/*/task.yaml` files. | Good test for CLI workflows, file/state inspection, deterministic repair scripts, parsers, log analysis, and repeatable terminal subtasks. | Runnable as `terminal-bench` through a public task-metadata probe adapter. Full benchmark scoring still needs Harbor/Terminal-Bench harness integration and Docker/uv setup. |
| `ScienceAgentBench` | ICLR 2025 paper; arXiv v3 revised 2025-03-31. | `external/ScienceAgentBench` at commit `72220ee` | Scientific data-driven discovery benchmark with `102` tasks from `44` peer-reviewed publications across four disciplines; target output is a self-contained Python program evaluated by program, execution, cost, and rubric metrics. | Good test for helper birth around data loading, table/array transforms, plotting checks, scientific feature extraction, and self-debug repair loops. | Runnable as `scienceagentbench` or `science-agent-bench` through a public-metadata probe adapter. Full benchmark scoring still requires the separately distributed 2026 verified split/artifacts. |

All rows are now selectable from the standalone CLI. The last three rows are
metadata-probe integrations, not protected benchmark-score integrations.

## CLI setup

Standalone SAGE can now be run with dataset/sample wording:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --dataset minigrid \
  --samples 12 \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/minigrid_cli_registry \
  --no-dashboard-open
```

Equivalent Makefile entry:

```bash
make sage_agent SAGE_DATASET=minigrid SAGE_SAMPLES=12 DASHBOARD_OPEN=0
```

Currently runnable standalone dataset choices are `toolsandbox`,
`toolsandbox-probe`, `cybergym`, `minigrid`, `bbh`, `tau2-bench`, `tau3-bench`,
`terminal-bench`, `scienceagentbench`, and `science-agent-bench`. The newly
cloned 2025/2026 repositories use public-metadata probe adapters until full
benchmark harness adapters are implemented.
