# Chapter 3 Methodology Outline: SAGE

## 1. Research Design Overview

SAGE is a self-evolving tool-use system. The central intervention is not a static prompt; it is a lifecycle in which the system detects capability gaps, generates deterministic tools, validates and repairs those tools, stores accepted tools in a registry, routes relevant tools into later tasks, and measures whether tool use improves task outcomes.

## 2. System Objective

The study evaluates whether autonomous tool generation can improve agent task performance. The expected mechanism is that generated tools make recurring subproblems more reliable by turning fragile reasoning steps into validated, reusable computations or structured action preparation.

The methodology should distinguish two operating modes:

- Online-build mode: SAGE discovers gaps and creates tools during the run. This measures self-evolution but adds LLM cost.
- Frozen-registry reuse mode: SAGE reuses an already validated registry. This measures whether learned tools improve future tasks with less generation overhead.

## 3. SAGE Components

The implementation should be described as a pipeline of cooperating components:

- Task runner: presents tasks to the agent and records task-level outcomes.
- Actor: attempts the task using available tools.
- Gap detector: identifies repeated failures, missing operations, brittle reasoning steps, or visible-but-unused generated-tool opportunities.
- Tool generator: proposes deterministic generated tools for observed gaps.
- Validator and repair loop: checks syntax, schema, callability, output shape, side-effect boundaries, and contract behavior; repairs rejected candidates when possible.
- Registry: stores accepted tools with metadata, hashes, contracts, and usage history.
- Router: selects a small relevant generated-tool bundle for each future task.
- Execution bridge: exposes generated tools to the actor and passes generated-tool outputs back into the task attempt.
- Evidence logger: records visibility, calls, failures, gains, regressions, runtime exceptions, and cost metrics.
- Lifecycle decision layer: retains, refines, parks, or scales tools based on evidence.

## 4. SAGE Pipeline

The Chapter 3 prose can present the lifecycle as:

1. Load a task and the current tool registry.
2. Route relevant generated tools into the actor's tool set.
3. Let the actor attempt the task using original tools and generated tools.
4. Detect whether the attempt exposes a capability gap.
5. Generate a candidate tool for that gap.
6. Validate the tool against its contract and safety rules.
7. Repair and revalidate if needed.
8. Store accepted tools in the registry.
9. Reuse accepted tools on later tasks.
10. Log contribution evidence and update lifecycle decisions.

## 5. Generated Tool Methodology

Generated tools are deterministic tools. They should not encode task answers, scenario IDs, hidden labels, or benchmark-specific shortcuts. Their proper role is to help with reusable operations such as:

- selecting records from visible data,
- normalizing dates, times, units, or identifiers,
- preparing structured action arguments,
- detecting insufficient information,
- extracting fields from visible service responses,
- planning safe sequences of existing environment actions,
- summarizing visible evidence in a callable, structured form.

State-changing work remains the responsibility of the original environment tools unless a generated tool is explicitly validated as a safe planner or argument-preparation step.

## 6. Validation And Safety

The methodology should state that SAGE only promotes a generated tool after validation. Validation includes:

- compile and import checks,
- tool schema checks,
- callable execution checks,
- output-shape checks,
- positive and negative examples,
- side-effect boundary checks,
- repair and revalidation when a candidate fails,
- registry hashing and metadata capture.

Safety is treated as part of methodology, not post-hoc cleanup. A generated tool that changes state unexpectedly, relies on hidden answers, or bypasses the actor's task process is rejected or parked.

## 7. Evidence And Attribution

The evidence plan should not report only final task score. It should show whether gains came from generated tools:

- generated-tool visibility,
- generated-tool calls,
- visible-not-called cases,
- called-generated-tool task outcomes,
- generated-tool-attributed gains,
- generated-tool-attributed regressions,
- generated-tool failures,
- runtime exceptions,
- accepted/rejected/repaired generated-tool counts,
- LLM calls and token cost.

This distinction is important because SAGE is only successful for the praxis if gains are connected to autonomous tool generation and use.

## 8. Cache And Leakage Controls

The methodology should explain the boundary between valid reuse and leakage:

- Generated tools must not contain task answers or hidden labels.
- Evaluation tasks must not expose expected answers to the SAGE arm.
- Baseline caching, if used, is a measurement control and should be reported separately.
- Online-build SAGE and frozen-registry SAGE should be reported as different evidence modes.
- Force-call or diagnostic settings are development evidence, not final promotion evidence.
- External fixture caches may stabilize external service outputs but are not task-answer caches.

## 9. Metrics

Primary metrics:

- task-completion or outcome score,
- canonical/reference score where applicable,
- exact success rate where applicable,
- generated-tool-called subset performance,
- gain/regression/preserved task counts.

Operational metrics:

- tools generated,
- tools accepted,
- tools rejected,
- tools repaired,
- tool visibility and call counts,
- generated-tool runtime failures,
- side-effect incidents,
- runtime exceptions,
- LLM calls and token usage.

## 10. Analysis Plan

The analysis should use paired task comparisons where each task has a baseline result and a SAGE result. Report aggregate deltas and lifts, but also inspect family-level gains and regressions. Where sample size supports it, use paired bootstrap confidence intervals or paired randomization tests.

The final interpretation should not choose an implementation by score alone. A primary SAGE claim requires tool-driven lift, clean safety behavior, and a clear evidence trail.

## 11. Limitations

The methodology should acknowledge that online-build SAGE can increase LLM calls and tokens because it performs generation, validation, repair, and retry work during the run. Cost reduction is expected mainly in frozen-registry reuse mode after tools have already been validated.

The scope of the claim should be limited to self-evolving tool generation and tool-use orchestration. Improvements caused only by synthetic completions, benchmark-specific code paths, or hidden-answer leakage are outside the praxis.
