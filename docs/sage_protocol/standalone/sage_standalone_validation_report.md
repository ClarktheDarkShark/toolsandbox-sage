# Standalone SAGE Validation Report

Status: development validation, not protected final-claim evidence.

Branch: `codex/sage-standalone-agent`

## Purpose

This report records the first complete standalone SAGE package slice. The goal
was to move SAGE toward an importable, environment-neutral agent that can be
used with ToolSandbox, CyberGym, and future environments through adapters rather
than through ToolSandbox-specific assumptions in the core lifecycle.

## What Was Added

The standalone package now lives under `src/sage_agent/`.

The core includes:

- `SAGEAgent`: environment-neutral lifecycle controller;
- `EnvironmentAdapter`: adapter contract for tasks, results, gap signals,
  validation cases, routing, and safety rules;
- `LocalSAGERegistry`: local generated-helper registry;
- `validate_helper_candidate`: syntax, AST-safety, runtime-smoke, and semantic
  validation;
- `TemplateHelperGenerator`: deterministic no-token generator for smoke tests;
- `OpenAIHelperGenerator`: optional `gpt-4o-mini` LLM-backed generator;
- lifecycle assessment for `watch`, `keep`, `refine`, `park`, and `scale`
  decisions.

The controller now supports validation repair and same-task retry after helper
birth. That means a generated helper can be validated, stored, routed back to
the task that revealed the gap, and measured immediately without a force-call.

The controller also enforces no-peeking integrity checks. Environment adapters
may privately score tasks, but SAGE-facing task specs, gap signals, and helper
candidates are scanned for hidden labels, expected answers, oracle fields,
answer keys, protected solutions, prior SAGE traces, and cache shortcuts before
generation or registry insertion.

## ToolSandbox Probe

Command:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env toolsandbox-probe \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/toolsandbox_probe_registry \
  --toolsandbox-scenario search_phone_number_with_name \
  --toolsandbox-scenario update_contact_with_id_and_phone_number
```

Result:

- environment: `toolsandbox`
- tasks seen: `2`
- tasks succeeded: `2`
- gaps observed: `1`
- tools born: `1`
- tools accepted: `1`
- tools reused: `2`
- integrity passed: `true`
- integrity issues: `0`
- birth-task retries: `1`
- birth-task retry successes: `1`
- lifecycle decision: `keep`

Interpretation: standalone SAGE can read real ToolSandbox scenario-registry
metadata, observe a missing reusable selector, generate and validate a helper,
retry the birth task with the helper, and reuse the helper on a second real
scenario-registry task. This is not a full ToolSandbox benchmark run.
The probe exposes scenario names, categories, and allowed tools only; expected
record IDs remain private adapter scoring state.

## CyberGym Probe

Command:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env cybergym \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/cybergym_subset_probe_registry \
  --cybergym-repo external/cybergym \
  --limit 3
```

Result:

- environment: `cybergym`
- tasks seen: `3`
- tasks succeeded: `3`
- gaps observed: `1`
- tools born: `1`
- tools accepted: `1`
- tools reused: `3`
- integrity passed: `true`
- integrity issues: `0`
- birth-task retries: `1`
- birth-task retry successes: `1`
- lifecycle decision: `keep`

Interpretation: standalone SAGE can operate against a CyberGym-shaped adapter,
using the cloned CyberGym repo and published subset-task IDs as task metadata.
It observes the missing verifier-output classification capability, generates a
side-effect-free classifier, validates sanitizer/timeout/clean minefields,
retries the birth task, and reuses the classifier. This does not download the
large CyberGym datasets and does not run Dockerized PoC verification yet.
The probe exposes visible verifier output but does not expose expected
classification labels to SAGE.

## Targeted Compatibility Tests

Commands run:

```bash
PYTHONPATH=src:. pytest -q tests/unit/test_sage_agent_standalone.py
PYTHONPATH=src:. pytest -q \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_registry_tools_are_available_to_toolsandbox_context \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_registry_tools_execute_through_toolsandbox_console \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_generated_tools_support_toolsandbox_name_scrambling
```

Results:

- standalone unit tests: `6 passed`
- targeted ToolSandbox generated-tool integration tests: `3 passed`

Broader targeted test set:

```bash
PYTHONPATH=src:. pytest -q \
  tests/unit/test_sage_agent_standalone.py \
  tests/unit/test_online_birth.py \
  tests/unit/test_toolsandbox_adapter.py \
  tests/unit/test_tool_generator.py \
  tests/integration/test_toy_mechanism.py \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_registry_tools_are_available_to_toolsandbox_context \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_registry_tools_execute_through_toolsandbox_console \
  tests/integration/test_toolsandbox_generated_tool_injection.py::test_generated_tools_support_toolsandbox_name_scrambling
```

Result:

- `70 passed`

Additional integrity-specific coverage:

- the ToolSandbox and CyberGym adapters pass task-spec leak checks;
- a deliberately leaky adapter exposing `expected_answer` is blocked before
  generation;
- accepted helper candidates are scanned before validation and registry
  insertion.
- the environment-neutral dashboard exporter writes generic SAGE summary,
  registry, and dashboard artifacts for CyberGym and ToolSandbox-shaped runs.

Dashboard smoke:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env cybergym \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/cybergym_dashboard5_registry \
  --cybergym-repo external/cybergym \
  --limit 5 \
  --output-root outputs/sage_agent_standalone \
  --run-id cybergym_dashboard5
```

Result: no-helper baseline `0/5`, SAGE `5/5`, absolute lift `+100.0 pp`,
relative lift `n/a` because the baseline was zero, `1` helper born and
accepted, `5` helper reuses, lifecycle decision `scale`, integrity `PASS`, and
dashboard opened at
`outputs/sage_agent_standalone/cybergym_dashboard5/dashboard/index.html`.

Additional local checks:

```bash
python3 -m py_compile src/sage_agent/*.py src/sage_agent/adapters/*.py scripts/run_sage_agent_smoke.py
PYTHONPATH=src:. mypy --follow-imports=skip src/sage_agent scripts/run_sage_agent_smoke.py
git diff --check
```

Results: all passed. Raw `mypy` without `--follow-imports=skip` did not
complete promptly in this local environment; the skipped-import check is the
recorded static type check for this slice. `ruff` is configured in the repo but
is not installed in the active shell environment, so it was not run.

## Assessment Checkpoints

Checkpoint 1: the initial package boundary worked, but it was too shallow. It
proved imports, registry storage, and adapter smoke behavior only.

Checkpoint 2: adding repair and same-task retry made the lifecycle closer to
the self-evolving SAGE mechanism. A helper can now be generated, rejected,
repaired, accepted, routed back to the birth task, and measured.

Checkpoint 3: the ToolSandbox probe now uses the real scenario registry rather
than only synthetic task names. This is a better compatibility proof without
spending model tokens or running a full benchmark.

Checkpoint 4: the CyberGym probe now uses published subset IDs and
CyberGym-shaped verifier outputs. It is still a probe, but it exercises a real
new environment boundary.

Checkpoint 5: the standalone boundary now distinguishes visible environment
information from scorer-only oracle data. Smoke adapters still privately score
their controlled tasks, but SAGE cannot see hidden expected answers or labels.

## Remaining Work

The next layer should connect full ToolSandbox online-birth machinery behind
the standalone adapter interface and add a real CyberGym subset executor:

1. CyberGym subset data bootstrap and availability check.
2. CyberGym server lifecycle manager.
3. Task directory generation through `cybergym.task.gen_task`.
4. Agent shell/file action trace extraction.
5. PoC submission and verifier result ingestion.
6. Cyber-specific gap buckets for crash-log parsing, input-format discovery,
   patch-diff reasoning, minimization, and mutation planning.
7. LLM-backed `gpt-4o-mini` generation run on a very small CyberGym subset once
   the deterministic probe path remains stable.

The current result is a working standalone architecture slice, not yet a full
CyberGym benchmark campaign.
