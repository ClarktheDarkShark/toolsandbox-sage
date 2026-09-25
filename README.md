# SAGE for ToolSandbox

This repository contains the executable research implementation of SAGE on
Apple's 1,032-task ToolSandbox benchmark. SAGE detects recurring capability
gaps, generates and validates reusable Python tools, stores accepted tools in a
registry, routes them to later tasks, and monitors their subsequent use.

This branch preserves the policy-directed configuration used for the reported
paper results. The policy selects among routed native and generated tools; the
model supplies arguments, consumes results, and produces the final response.
Later natural-selection experiments are not included.

## What is included

- `src/sage_ts/` — the complete SAGE runtime
- `tool_sandbox/` — the upstream benchmark/runtime required by SAGE
- `scripts/run_sage_protocol.py` — concurrent matched control/SAGE execution
- `scripts/run_native_action_4omini_ab.sh` — reproducible full-run launcher
- `src/sage_ts/dashboard/` — live run dashboards
- `scripts/research/` — Chapter 4 dashboard aggregation
- `docs/sage_protocol/manifests/` — the ordered 1,032-task benchmark manifest
- `artifacts/publication_cleanup_20260901/fixtures/` — the frozen read-only
  external-service fixture

Tests, superseded experiments, campaign orchestration, paper figures, table
renderers, and historical reports are intentionally excluded from this
application release.

## Installation

The validated environment is CPython 3.12.7 on Darwin/arm64:

```bash
./scripts/bootstrap_env.sh .venv-publication
source .venv-publication/bin/activate
```

The bootstrap script installs the exact dependency lock, installs this checkout
in editable mode, runs `pip check`, and verifies the environment and import
provenance. Set `OPENAI_API_KEY` before a live run. A local
`.secrets/env.sh` file is supported and must not be committed.

## Run SAGE

Run one complete matched pair (fresh ToolSandbox control and SAGE execute in
parallel):

```bash
make paper-online PORT=63105
```

The launcher uses:

- the fixed 1,032-task order;
- an empty run-local generated-tool registry;
- no application response, task, result, or control cache;
- the fixed ToolSandbox clock and hash-pinned read-only RapidAPI fixture;
- the same model configuration for the matched arms; and
- policy-directed actor selection, generation, validation, routing, lifecycle
  monitoring, and outcome evaluation.

It writes run data below `outputs/publication_validation/`, runtime artifacts
below `artifacts/publication_validation/`, and opens Task Compare in the
external browser before execution begins.

Evaluate an existing registry with generation disabled:

```bash
RESUME_REGISTRY_CHECKPOINT=/absolute/path/to/registry \
  make paper-frozen PORT=63106
```

The launcher requires a clean Git checkout so each run records an unambiguous
source identity.

## Dashboards

Every paired run produces three dashboards:

- `dashboard/task_compare.html` — control versus SAGE progress and outcomes
- `dashboard/task_focus.html` — task-level traces and tool activity
- `dashboard/index.html` — overall run and lifecycle status

Serve an existing dashboard directory with:

```bash
make dashboard ROOT=/absolute/path/to/run/dashboard PORT=63105
```

The retained Chapter 4 dashboard can be opened directly from
`artifacts/publication_evidence/chapter4_current/chapter4_evidence.html`.
Rebuild aggregate evidence from a compatible campaign manifest with:

```bash
sage-build-chapter4-evolution \
  --campaign-manifest /absolute/path/to/campaign_manifest.json \
  --output-dir /absolute/path/to/dashboard-output
```

## Package and source checks

These checks do not make model calls:

```bash
make compile
make package
python scripts/verify_publication_environment.py
```

## Core architecture

- `adapters/` — actor and ToolSandbox execution adapters
- `adequacy/` — gap classification and candidate admission
- `generation/` — reusable tool specification, generation, and repair
- `validation/` — schema, AST, sandbox, and behavioral validation
- `registry/` — retained-tool storage and manifests
- `runtime/` — task-conditioned routing, injection, and execution
- `orchestration/` — online tool birth and lifecycle reflection
- `evaluation/` — outcome feedback, metrics, and contribution accounting
- `dashboard/` — generated live dashboards and local server

The SAGE additions build on Apple's ToolSandbox. See `LICENSE`,
`ACKNOWLEDGEMENTS`, and `NOTICE.md` for attribution and license scope.
