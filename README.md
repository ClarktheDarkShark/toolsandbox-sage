# SAGE ToolSandbox Praxis

SAGE is a self-evolving tool-use research system. In this repository the current
primary implementation is the native ToolSandbox SAGE Praxis path: SAGE detects
task gaps, generates deterministic Python tools, validates and repairs them,
stores accepted tools in a registry, routes them into later tasks, and evaluates
matched control/SAGE outcomes with Task Compare dashboards.

The cleaned codebase intentionally focuses on the ToolSandbox implementation
used for Chapter 3 methodology and full-dataset evidence. Earlier standalone,
CyberGym, tau, MiniGrid, and BBH portability experiments are retained only as
methodology and future-work documents, not as active runtime code.

## Current Evidence

Canonical full standard run for SAGE:

- Run:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`
- Dashboard:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare.html`
- Score: `0.733214 -> 0.801186`, lift `+9.27%`
- Outcome: `0.454251 -> 0.757267`, lift `+66.71%`
- Accepted tools: `22`
- Called tools: `21`
- Generated-tool-called scenarios: `825`
- Tool reuse events: `1171`
- Generated-tool failures: `3`
- Side-effect preservation incidents: `1`
- Runtime exceptions: `0`
- Baseline LLM tokens: `10,465,294`
- SAGE LLM tokens: `17,245,671`

This run used `SAGE_PRAXIS_BRIDGE_POLICY=disabled`, `gpt-4o-mini` for actor,
user, and generation, cached controls, SAGE task cache off, OpenAI response
cache disabled, scenario-name-free tool birth/routing, and the Task Compare
dashboard. This repository treats the v061 method and evidence boundary as
`SAGE`.

## Primary Runner

Use `scripts/run_sage_protocol.py` for ToolSandbox SAGE runs.

Minimal full-dataset command shape:

```bash
PYTHONPATH=src:. \
SAGE_PRAXIS_BRIDGE_POLICY=disabled \
SAGE_SCENARIO_METADATA_POLICY=visible_context \
SAGE_DISABLE_SCENARIO_NAME_BIRTH=1 \
SAGE_DISABLE_SCENARIO_NAME_ROUTING=1 \
SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=0 \
SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY=0 \
SAGE_SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS=0 \
SAGE_GENERATED_TOOL_GUIDANCE_MODE=minimal \
SAGE_GENERATED_TOOL_DOCSTRING_MODE=compact \
SAGE_GENERATED_TOOL_FIRST_ATTEMPT_CHOICE=1 \
SAGE_GENERATED_TOOL_CONTINUATION_CHOICE=1 \
SAGE_GENERATED_TOOL_CONTRACT_RETRY_ATTEMPTS=0 \
SAGE_GENERATED_TOOL_SYNTHETIC_REPAIR=0 \
SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE=4 \
SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS=120 \
SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json \
POLARS_MAX_THREADS=1 \
python scripts/run_sage_protocol.py \
  --mode online_build_full \
  --manifest docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json \
  --registry-dir artifacts/sage/example_registry \
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
  --output-root outputs/sage/example_full \
  --artifact-root artifacts/sage/example_full_artifacts
```

The exact v061 run configuration is preserved in:

```bash
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json
```

## Active Code Surface

The retained implementation is organized around:

- `scripts/run_sage_protocol.py`: paired ToolSandbox control/SAGE runner.
- `src/sage_ts/adapters/`: ToolSandbox, OpenAI, role, and SAGE run adapters.
- `src/sage_ts/generation/`: tool specifications, prompt cache, and generator.
- `src/sage_ts/validation/`: AST, schema, sandbox, live, and output checks.
- `src/sage_ts/registry/`: registry manifest and store.
- `src/sage_ts/runtime/`: ToolSandbox tool injection, routing, base tool policy,
  and accepted-tool invocation utilities.
- `src/sage_ts/orchestration/online_birth.py`: online gap detection, birth,
  validation, repair, and retention logic.
- `src/sage_ts/evaluation/`: control cache, run metrics, task strata, outcome,
  tool contribution, and LLM usage accounting.
- `src/sage_ts/dashboard/`: Task Compare and Task Focus dashboards.
- `tool_sandbox/`: upstream benchmark environment, tools, roles, scenarios, and
  scoring.

## Validation

Fast structural validation:

```bash
make compile
```

Focused retained-path test suite:

```bash
make test-core
```

Full local unit/integration sweep:

```bash
make test
```

The historical full-dataset success is validated by the preserved run artifacts
and dashboard. Re-running the full sample is expensive and should be done only
as a deliberate evidence run.

## Chapter 3 Materials

Core methodology files:

- `docs/sage_protocol/chapter3_sage_methodology_latex_draft.tex`
- `docs/sage_protocol/chapter3_sage_methodology_markdown_draft.md`
- `docs/sage_protocol/chapter3_sage_methodology_outline.md`
- `docs/sage_protocol/chapter3_sage_methodology_system_architecture_v061.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/current_state.md`

Figure assets live under `docs/sage_protocol/figures/`. Regenerate current
Chapter 3 figures with:

```bash
python scripts/render_chapter3_sage_figures.py
```

## Evidence Boundary

For primary Chapter 3 claims, do not enable synthetic bridge completions or
route-around policies. The evidence boundary is autonomous tool generation,
validation/repair, registry retention, routing/reuse, same-task availability
of accepted generated tools without SAGE-only extra retry turns, tool-specific
actor guidance when generated tools are visible, and contribution logging.

Generated tools must not encode hidden labels, expected answers, scenario IDs,
or benchmark-specific answer strings. ToolSandbox side-effect tools remain
responsible for state mutation; generated SAGE tools should prepare arguments,
normalize values, select records, compute deterministic values, detect
insufficient information, or recommend benchmark-compatible next actions.
