# Chapter 3 Working Setup: Current SAGE Methodology

> **SUPERSEDED — ARCHIVAL V061 MATERIAL.** The “current” wording below is
> historical. Do not use its paths, settings, or values for a publication run.
> See [current_state.md](current_state.md).

Status: current working setup for the v061 SAGE evidence boundary.

## Primary Implementation

Use the generation-enabled ToolSandbox protocol path as the Chapter 3 SAGE
implementation:

- Runner: `scripts/run_sage_protocol.py`
- Policy preset: `--sage-policy self-evolving-praxis`
- Reusable SAGE core: `src/sage_ts/`
- ToolSandbox SAGE execution adapter: `src/sage_research/toolsandbox/sage_run_adapter.py`
- ToolSandbox integration: `src/sage_research/toolsandbox/integration.py`
- Tool generation: `src/sage_ts/generation/tool_generator.py`
- Tool validation: `src/sage_ts/validation/`
- Registry and manifests: `src/sage_ts/registry/manifest.py`
- Actor/tool-use policy: `src/sage_research/toolsandbox/openai_roles.py`
- Dashboard: `src/sage_ts/dashboard/task_compare_template.py`

## Current Evidence Boundary

From this point forward, SAGE means the v061 method unless a later validated
run explicitly replaces it:

- Full run:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`
- Dashboard:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare.html`
- Protocol manifest:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json`
- Registry:
  `artifacts/chapter3_token_reduction/v061_finish_v059_registry`

The v061 boundary uses autonomous tool generation, validation/repair, registry
retention, visible-context routing, natural generated-tool use, lifecycle
feedback, contribution accounting, and matched baseline comparison.

It excludes:

- synthetic bridge completions;
- route-around behavior from code-based task knowledge;
- hidden scenario-name birth or routing;
- diagnostic force calls;
- answer-label or expected-answer leakage.

## Current Result

The v061 full-dataset run reported:

- Score: `0.733214 -> 0.801186`, lift `+9.27%`
- Outcome/task completion: `0.454251 -> 0.757267`, lift `+66.71%`
- Generated-tool-called scenarios: `825`
- Accepted generated tools: `21`
- Runtime exceptions: `0`
- Generated-tool failures: `3`
- Side-effect preservation incidents: `1`

Outcome/task completion is the primary measure. Canonical/reference score is
secondary because generated tools can complete the task while bypassing
route-specific scoring milestones.

## Chapter 3 Source Of Truth

Use this document for the detailed methodology draft:

```text
docs/sage_protocol/chapter3_sage_methodology_system_architecture_v061.md
```

Use this document for current implementation state:

```text
docs/sage_protocol/current_state.md
```
