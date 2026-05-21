# Standalone SAGE Architecture

Status: development architecture slice, not a protected final-claim artifact.

SAGE now has an importable environment-neutral package boundary at
`src/sage_agent/`. The existing ToolSandbox-specific research harness remains
under `src/sage_ts/`, but new environments should integrate through
`sage_agent` adapters rather than by copying ToolSandbox assumptions.

The standalone contract is:

```python
from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.generators import TemplateHelperGenerator

agent = SAGEAgent(
    adapter=my_environment_adapter,
    generator=TemplateHelperGenerator(),  # or an LLM-backed generator
    config=SAGEConfig(model="gpt-4o-mini", registry_dir=Path("my_registry")),
)
summary = agent.run(limit=20)
```

SAGE now supports the following generic lifecycle mechanics at this boundary:

- generate a helper from an adapter-provided gap signal;
- validate syntax, AST safety, callability, positive cases, and abstain cases;
- repair a rejected helper when the generator supports repair;
- store accepted helpers in a local environment-neutral registry;
- retry the task that produced the gap with the newly accepted helper when the
  adapter permits same-task reuse;
- record natural helper reuse and lifecycle decisions such as `watch`, `keep`,
  `refine`, `park`, or `scale`.
- enforce a research-integrity boundary that blocks label peeking, oracle
  metadata, answer keys, hidden solutions, prior SAGE traces, and cache
  shortcuts before generation begins.
- export an environment-neutral dashboard from generic run summary events and
  registry metadata.

## Core Boundary

The SAGE core knows only these concepts:

- environment profile
- task specification
- normalized task result
- observed gap signal
- validation cases
- helper candidate
- helper validation report
- local helper registry
- bounded helper routing

It does not know about contacts, reminders, ToolSandbox milestones, CyberGym
PoC submission, Docker, or sanitizer output. Those concepts live in adapters.

## Integrity Boundary

SAGE is allowed to inspect visible environment information: prompts, visible
files, public task metadata, allowed tool surfaces, current tool traces, and
adapter-provided validation cases for helper robustness. It is not allowed to
receive hidden labels, expected answers, oracle fields, answer keys, protected
solutions, prior SAGE traces, or cache-derived outcome shortcuts.

The boundary is implemented in `src/sage_agent/integrity.py` and enforced by
`SAGEAgent.run()` before the controller generates or repairs helpers:

1. environment-profile metadata is scanned;
2. every SAGE-visible `TaskSpec.metadata` and `TaskSpec.artifacts` key is
   scanned for leak-prone oracle fields;
3. every `GapSignal` is scanned before generation;
4. every generated or repaired helper candidate is scanned before validation
   and registry insertion;
5. helper code is checked for direct source-task-ID hard-coding.

Adapters may privately hold scoring logic. For example, the ToolSandbox smoke
adapter privately knows which selected record should score as correct, and the
CyberGym smoke adapter privately derives success from visible verifier output.
Those values are not placed in `TaskSpec.metadata`, are not included in the
generation prompt, and are not stored in helper metadata.

## Adapter Duties

An environment adapter must provide:

- a profile describing base tools, action tools, observable fields, helper
  families, and safety rules;
- a sealed task list or task stream;
- routing logic for selecting a small helper bundle from the registry;
- task execution or a controlled smoke execution;
- gap observation that converts failure/friction into reusable capability gaps;
- validation cases for a proposed helper.

The adapter is the place where environment-specific evidence becomes a generic
SAGE gap. That is the portability boundary.

Adapters must keep any scorer-only data private. They must not expose fields
such as `expected_answer`, `ground_truth`, `oracle`, `solution`, `answer_key`,
or prior traces through SAGE-facing task specs, gap signals, generation
directives, or helper metadata.

## Current Adapters

`ToolSandboxMiniAdapter` proves that the standalone package can operate against
ToolSandbox-shaped structured tasks. It observes a missing visible-record
selector, generates a side-effect-free helper, validates ambiguity behavior, and
reuses the accepted helper on a second task.

`ToolSandboxScenarioProbeAdapter` reads the real ToolSandbox scenario registry.
It does not run a full paired benchmark, but it verifies that standalone SAGE can
load real scenario names, categories, and tool-allow-list metadata, observe a
reusable helper gap, validate a generated helper, route it back to the birth
task, and reuse it on a second real scenario-registry task.
The adapter no longer exposes expected person IDs or match answers as task
metadata; those remain private to the adapter scorer.

`CyberGymAdapter` proves that the same SAGE package can operate against a new
CyberGym-shaped environment. It reads the cloned CyberGym repo, uses the
published subset-task IDs as task metadata, models verifier submission results,
observes the missing execution-log classifier, validates crash/timeout/clean
output minefields, retries the birth task, and reuses the accepted helper on
additional subset-shaped tasks.
The adapter exposes visible verifier output but does not expose an expected
classification label to SAGE.

The CyberGym smoke does not download the 130GB-10TB benchmark assets and does
not run Docker. It is intentionally a low-cost adapter proof. A full CyberGym
campaign should add a real task launcher, server lifecycle manager, PoC
submission trace extractor, and verifier-backed scoring under the same adapter
interface.

## Token Policy

The current development smoke uses deterministic template generation while
recording `gpt-4o-mini` as the configured model. This avoids spending model
tokens while testing package mechanics. Future LLM-backed generation should use
the same `HelperGenerator` protocol and default to `gpt-4o-mini` unless a run
protocol explicitly authorizes a stronger model.

An LLM-backed generator is available as `sage_agent.OpenAIHelperGenerator` and
can be selected in the smoke runner with `--generator openai`. It is not used by
default because the current portability validation is testing package mechanics
and adapter boundaries, not model quality.

## Environment-Neutral Dashboard

Standalone SAGE runs export a dashboard through `src/sage_agent/dashboard.py`.
The exporter writes:

- `summary.json`: the generic `SAGERunSummary`;
- `dashboard_data.json`: summary plus registry payload;
- `dashboard/task_compare_data.json`: dashboard-local copy of the same generic
  payload;
- `registry.json`: a run-local copy of accepted helper metadata;
- `dashboard/task_compare.html`: the default self-contained dark-mode Task
  Compare dashboard;
- `dashboard/index.html`: compatibility copy of the same dashboard.

The dashboard deliberately avoids ToolSandbox-specific assumptions. It renders
generic task events, baseline records, SAGE task scores, transcripts/artifacts
when the adapter exports them, gap events, helper birth/repair/retry events,
integrity status, lifecycle decisions, and registry tools. Its visual structure
matches the main Task Compare dashboard: run-level metric tiles, a compact task
sidebar, task-level score/outcome lift, generated-tool events near the top, full
baseline/SAGE transactions, and registry/lifecycle details. Any future
environment adapter that returns the same `SAGERunSummary` and optional
baseline-result shape can use the same dashboard.

For smoke runs, `scripts/run_sage_agent_smoke.py` also records a matched
no-generated-helper baseline over the same adapter task stream. This lets the
dashboard show baseline success, SAGE success, absolute lift in percentage
points, and relative lift when the baseline rate is nonzero. If the baseline is
zero, the dashboard reports relative lift as `n/a` instead of manufacturing an
infinite percentage.

The same export now includes run-mode metadata. A dashboard must state whether
the run is benchmark-ready or only an adapter probe, how many tasks were
available, whether the requested limit was satisfied, and whether real task
generation, submission-server execution, and verifier-backed scoring were used.
For CyberGym today, the dashboard must report `cybergym_synthetic_probe` because
the adapter uses CyberGym-shaped verifier samples instead of `cybergym.task`
generated task directories, a running PoC server, submitted PoCs, and real
verifier results. This keeps the portability smoke useful while preventing the
result from being mistaken for CyberGym benchmark evidence.

## Next Work

The ToolSandbox protocol runner now exposes the existing self-evolving
online-birth machinery as `--sage-policy self-evolving-praxis`, which is the
bridge from the historical ToolSandbox-specific system into the broader SAGE
agent work. The remaining architecture work is to make this policy shape
native to the environment-neutral adapter interface instead of expressing it
through ToolSandbox environment variables. After that, CyberGym can add fuller
execution support:

1. subset data bootstrap,
2. PoC server lifecycle,
3. task directory generation,
4. agent filesystem/shell action tracing,
5. verifier result ingestion,
6. cyber-specific gap bucketing,
7. generated helper validation against synthetic and real logs.

## CyberGym Live Submit Smoke

`src/sage_agent/adapters/cybergym_live.py` adds the first real CyberGym
submission adapter. Unlike `CyberGymAdapter`, it does not use synthetic verifier
records. It expects task directories generated by `cybergym.task.gen_task`,
reads only the visible `README.md` and `description.txt`, and sends candidate
PoC files through each task's generated `submit.sh` script. The side effect
remains environment-owned: generated helpers can propose candidate content, but
they cannot run shell commands or submit PoCs.

`scripts/run_cybergym_live_sage.py` performs a matched smoke comparison:

- baseline submits one fixed four-byte PoC;
- SAGE starts from an empty registry;
- after the first failure, SAGE can generate a side-effect-free visible seed
  candidate planner;
- the adapter submits SAGE's candidate strings through the live local
  `/submit-vul` server;
- success is counted only when the live verifier returns a nonzero vulnerable
  execution exit code.

This is a real submit-path smoke, but it is not final CyberGym benchmark
evidence. It currently omits fix-side re-verification and uses a deliberately
small candidate planner. The next cyber-specific SAGE layer needs actual
analysis actions: source unpacking, harness discovery, crash-log interpretation,
targeted mutation, candidate minimization, and repair from failed submissions.

`scripts/run_cybergym_live_batched_sage.py` extends this into a bounded
environment-runner pattern:

- select a fixed visible task list from CyberGym metadata;
- download only visible assets needed for the current batch;
- generate task directories with CyberGym's own task generator;
- run the same baseline and SAGE lifecycle through each task's `submit.sh`;
- preserve the SAGE registry across batches;
- clear batch work directories and pulled runner images after each batch.

This is the preferred pattern for new heavy environments: the adapter owns
environment setup and side effects, while SAGE sees only normalized task text,
visible artifacts, execution feedback, gap signals, helper validation cases,
and registry metadata.

The first batched CyberGym helper used a CyberGym-shaped seed-planner template.
That was useful for wiring, but it was too environment-specific for the
standalone SAGE claim. The current live adapter now routes a generic
`visible_text_candidate_planner` family instead. The helper receives only
adapter-normalized visible fields:

- task description;
- task README/instructions;
- a bounded summary of visible source artifacts from `repo-vul.tar.gz`;
- prior live submission feedback;
- a candidate limit.

The adapter-owned artifact summarizer extracts file names, short source lines,
and string literals from visible source files, while skipping reference PoCs,
solutions, hidden labels, and scorer fields. The generated helper remains
side-effect-free: it returns candidate input strings only. The adapter performs
all `submit.sh` calls and scoring privately. This pattern is the intended
generalization boundary for new benchmark datasets: environment adapters may
summarize visible resources and own side effects, but SAGE helper generation,
validation, retention, routing, and lifecycle decisions remain environment
neutral.

The standalone controller now also supports bounded retained-helper
refinement. If a helper was accepted and naturally routed but later
underperforms, SAGE can ask a repair-capable generator for an updated helper
under the same static, semantic, and integrity checks. Repaired helpers are
only retained when their code changes and validation passes; force-calls remain
diagnostic-only and are not part of the live CyberGym runner.

## Baseline Semantics

Standalone adapter smoke runs are not automatically benchmark comparisons. The
`scripts/run_sage_agent_smoke.py` no-helper path is a lifecycle baseline used
to verify that helper birth, validation, registry storage, routing, and reuse
work through an adapter. Unless a runner explicitly marks
`baseline.comparison_valid: true`, dashboards must not report lift from that
baseline.

The generic dashboard therefore supports two modes:

- `comparison_valid: true`: show baseline success, absolute lift, and relative
  lift for a real matched control.
- `comparison_valid: false`: label the value as `Probe baseline` and suppress
  lift.

This distinction matters most for ToolSandbox. A `toolsandbox-probe` adapter can
exercise real scenario metadata without running the protected benchmark actor
and scorer. Its no-helper baseline may be useful for lifecycle debugging, but
it is not a real ToolSandbox control arm.

## Generic Gap Handling

The first CyberGym live adapter originally generated a CyberGym-named seed
candidate helper. That has been replaced by a generic
`visible_text_candidate_planner` helper family. The helper reads only visible
task descriptions, visible instructions, visible source-artifact summaries, and
prior execution feedback, then returns side-effect-free candidate input strings
for the adapter to submit.

This is still a shallow capability. Its purpose is to prove the env-general
loop:

1. observe visible task context and execution feedback;
2. emit a normalized gap signal;
3. generate a side-effect-free helper;
4. validate it with static, schema, and minefield cases;
5. retain it in the registry;
6. route it naturally on later tasks;
7. classify lifecycle status from observed use and success.

The next architecture step is to make the same pattern richer without hard
coding CyberGym facts: stronger environment inventory tools, artifact
summarizers, format-inference helpers, feedback classifiers, mutation planners,
and repair policies that operate on adapter-normalized observations rather than
hidden labels or task IDs.
